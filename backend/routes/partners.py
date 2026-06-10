"""
BidVex - Partner Account System
Auto-extracted from server.py during P2 refactoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from deps import get_db, get_current_user, get_current_user_optional, User
from shared import (
    DEFAULT_EMAIL_TEMPLATES, EMAIL_TEMPLATE_CATEGORIES,
    DEFAULT_MARKETPLACE_SETTINGS, AFFILIATE_COMMISSION_RATE,
    generate_affiliate_code, get_email_templates, get_email_template_id,
    get_marketplace_settings, get_epoch_timestamp, get_server_timestamp,
    calculate_buyer_fees, calculate_seller_fees, calculate_stripe_fee_recovery,
    calculate_partner_checkout, calculate_standard_checkout,
    FeeCalculation, UserCreate, Category, Invoice, PaddleNumber,
    PaymentTransaction, SessionCreate, get_minimum_increment,
    STANDARD_BUYER_PREMIUM_RATE, STANDARD_SELLER_COMMISSION_RATE,
    PARTNER_PLATFORM_FEE_RATE, PARTNER_ANNUAL_ACCESS_FEE,
    STRIPE_PERCENTAGE_FEE, STRIPE_FIXED_FEE,
)
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from pathlib import Path
import logging
import uuid
import os as _os
import json as _json

logger = logging.getLogger(__name__)

import stripe
from starlette.responses import FileResponse

# Helpers defined in admin module
async def _get_sendgrid_config():
    """Fetch SendGrid config from site_config collection."""
    _db = get_db()
    config = await _db.site_config.find_one({"key": "sendgrid"}, {"_id": 0})
    if not config or not config.get("api_key"):
        return None
    return config

async def _get_or_create_partner_fee_price():
    """Get or create Stripe Price for the partner annual fee."""
    _db = get_db()
    config = await _db.site_config.find_one({"key": "partner_fee_price_id"}, {"_id": 0})
    if config and config.get("price_id"):
        return config["price_id"]
    product = stripe.Product.create(name="BidVex Partner Annual Access", metadata={"type": "partner_annual_fee"})
    price = stripe.Price.create(unit_amount=10000, currency="cad", recurring={"interval": "year"}, product=product.id)
    await _db.site_config.update_one({"key": "partner_fee_price_id"}, {"$set": {"key": "partner_fee_price_id", "price_id": price.id}}, upsert=True)
    return price.id


# iter257 — Stripe Coupon mirror cache. We map each BidVex promotion_id
# to a Stripe Coupon object so partial discounts surface natively on
# the Stripe Checkout page (the user sees the reduced total before
# clicking Subscribe). The cache lives in-process — Stripe's own
# coupon API is idempotent on `id`, so a re-creation is a no-op.
_STRIPE_COUPON_CACHE: Dict[str, str] = {}


def _ensure_stripe_coupon_for_promotion(
    promotion_id: str,
    discount_percent: float,
    coupon_label: str,
) -> Optional[str]:
    """Return a Stripe Coupon id mirroring the given BidVex promotion.

    Idempotent: re-creating a coupon with the same id raises
    `InvalidRequestError`, in which case we trust the existing object.
    Returns None if the discount is out of range (Stripe rejects
    percent_off <= 0 or > 100).
    """
    pct = max(0.0, min(100.0, float(discount_percent or 0.0)))
    if pct <= 0.0:
        return None
    cache_key = f"{promotion_id}:{int(round(pct))}"
    if cache_key in _STRIPE_COUPON_CACHE:
        return _STRIPE_COUPON_CACHE[cache_key]
    stripe_coupon_id = f"bidvex_promo_{promotion_id[:24]}_{int(round(pct))}"
    try:
        stripe.Coupon.create(
            id=stripe_coupon_id,
            percent_off=pct,
            duration="once",
            name=f"BidVex {coupon_label or 'Promo'} — {int(round(pct))}% off",
            metadata={"bidvex_promotion_id": promotion_id, "label": coupon_label or ""},
        )
    except stripe.InvalidRequestError as exc:
        # The coupon already exists — that's fine, we re-use it.
        if "already exists" not in str(exc).lower() and "resource_already_exists" not in str(exc).lower():
            logger.warning(f"Stripe coupon create failed for {stripe_coupon_id}: {exc}")
            return None
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Stripe coupon create failed for {stripe_coupon_id}: {exc}")
        return None
    _STRIPE_COUPON_CACHE[cache_key] = stripe_coupon_id
    return stripe_coupon_id


partners_router = APIRouter(tags=["Partners"])


@partners_router.post("/partner/apply")
async def apply_for_partner(
    company_name: str = Form(...),
    neq_number: str = Form(...),
    neq_document: UploadFile = File(...),
    certification_documents: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Submit a partner application with mandatory federal/provincial business registration and professional certifications.
    Sets partner_verification_status to 'pending'.
    """
    # Check not already partner or pending
    _db = get_db()
    user_doc = await _db.users.find_one({"id": current_user.id}, {"_id": 0})
    if user_doc and user_doc.get("is_partner"):
        raise HTTPException(status_code=400, detail="Account is already a verified partner.")
    if user_doc and user_doc.get("partner_verification_status") == "pending":
        raise HTTPException(status_code=400, detail="You already have a pending partner application.")

    # Validate file types (PDF, JPG, PNG only)
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp']
    
    if neq_document.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="NEQ document must be PDF, JPG, PNG, or WebP.")
    
    for cert_doc in certification_documents:
        if cert_doc.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Certification file '{cert_doc.filename}' must be PDF, JPG, PNG, or WebP.")

    # Store files. URLs are stored as RELATIVE PATHS only — the frontend always
    # prepends its own REACT_APP_BACKEND_URL (iter208). This permanently kills
    # the legacy localhost-leak bug where a missing backend env var caused
    # documents to be stored as http://localhost:8001/...
    upload_dir = Path("uploads/partner_docs")
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Save NEQ document
    neq_contents = await neq_document.read()
    if len(neq_contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="NEQ document must be less than 10MB.")
    neq_ext = neq_document.filename.split('.')[-1] if '.' in neq_document.filename else 'pdf'
    neq_filename = f"neq_{current_user.id}_{uuid.uuid4().hex[:8]}.{neq_ext}"
    with open(upload_dir / neq_filename, "wb") as f:
        f.write(neq_contents)
    neq_url = f"/api/uploads/partner_docs/{neq_filename}"

    # Save certification documents
    cert_urls = []
    for cert_doc in certification_documents:
        cert_contents = await cert_doc.read()
        if len(cert_contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"File '{cert_doc.filename}' must be less than 10MB.")
        cert_ext = cert_doc.filename.split('.')[-1] if '.' in cert_doc.filename else 'pdf'
        cert_filename = f"cert_{current_user.id}_{uuid.uuid4().hex[:8]}.{cert_ext}"
        with open(upload_dir / cert_filename, "wb") as f:
            f.write(cert_contents)
        cert_urls.append(f"/api/uploads/partner_docs/{cert_filename}")

    # Update user document
    now = datetime.now(timezone.utc).isoformat()
    await _db.users.update_one(
        {"id": current_user.id},
        {"$set": {
            "is_partner": False,
            "partner_verification_status": "pending",
            "partner_company_name": company_name,
            "partner_neq": neq_number,
            "partner_neq_document": neq_url,
            "partner_certifications": cert_urls,
            "partner_applied_at": now,
            "updated_at": now,
        }}
    )

    # Log the application for admin audit
    await _db.admin_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "partner_application_submitted",
        "user_id": current_user.id,
        "user_email": current_user.email,
        "details": {
            "company_name": company_name,
            "neq_number": neq_number,
            "num_certifications": len(cert_urls),
        },
        "timestamp": now,
    })

    # ===== AUTOMATED EMAIL ONBOARDING (Task 5) =====
    try:
        _sg_config = None
        try:
            _sg_config = await _get_sendgrid_config()
        except Exception:
            pass
        if _sg_config:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            sg = sendgrid.SendGridAPIClient(api_key=_sg_config["api_key"])
            from_email = Email(_sg_config["from_email"], _sg_config["from_name"])
            
            # 1) Applicant auto-reply
            applicant_html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; color: #1e293b;">
              <h2 style="color: #2563eb;">Thank You for Applying</h2>
              <p>Dear {current_user.email.split('@')[0].title()},</p>
              <p>Thank you for applying to the <strong>BidVex Partner Network</strong>. Our team is currently reviewing your NEQ and professional credentials.</p>
              <p><strong>Expected turnaround: 24-48 hours.</strong></p>
              <p>If we need additional information, we will reach out to you directly.</p>
              <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
              <p style="color: #64748b; font-size: 13px;">Application Summary:</p>
              <ul style="color: #475569; font-size: 13px;">
                <li>Company: <strong>{company_name}</strong></li>
                <li>NEQ: <strong>{neq_number}</strong></li>
                <li>Documents: {len(cert_urls)} certification(s) + business registration document</li>
              </ul>
              <p style="color: #64748b; font-size: 12px; margin-top: 20px;">
                Questions? Contact us at <a href="mailto:partners@bidvex.ca" style="color: #2563eb;">partners@bidvex.ca</a>
              </p>
            </div>
            """
            applicant_mail = Mail(
                from_email=from_email,
                to_emails=To(current_user.email),
                subject="BidVex Partner Application — Under Review",
                html_content=Content("text/html", applicant_html)
            )
            sg.client.mail.send.post(request_body=applicant_mail.get())
            
            # 2) Internal alert to charbel911@gmail.com (BidVex ops inbox)
            # Phase 6.0 hotfix — recipient hardcoded to the authoritative admin
            # mailbox so partner-application alerts surface immediately even if
            # env-var routing is reconfigured.
            _email_base = (_os.environ.get("FRONTEND_URL") or _os.environ.get("REACT_APP_BACKEND_URL") or "https://bidvex.com").rstrip("/")
            _abs_neq = neq_url if neq_url.startswith("http") else f"{_email_base}{neq_url}"
            _abs_certs = [u if u.startswith("http") else f"{_email_base}{u}" for u in cert_urls]
            cert_links = "".join([f'<li><a href="{u}">{u.split("/")[-1]}</a></li>' for u in _abs_certs])
            internal_html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #1e293b;">
              <h2 style="color: #dc2626;">New Partner Application</h2>
              <table style="font-size: 14px; border-collapse: collapse;">
                <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Applicant:</td><td>{current_user.email}</td></tr>
                <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Company:</td><td>{company_name}</td></tr>
                <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">NEQ:</td><td>{neq_number}</td></tr>
                <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Applied At:</td><td>{now}</td></tr>
              </table>
              <h3 style="margin-top: 16px;">Submitted Documents:</h3>
              <ul>
                <li><a href="{_abs_neq}">Federal or Provincial Business Registration Document</a></li>
                {cert_links}
              </ul>
              <p style="margin-top: 16px;"><a href="{_email_base}/admin" style="color: #2563eb; font-weight: bold;">Review in Admin Panel</a></p>
            </div>
            """
            internal_mail = Mail(
                from_email=from_email,
                to_emails=To("charbel911@gmail.com"),
                subject=f"[ACTION REQUIRED] New Partner Application: {company_name}",
                html_content=Content("text/html", internal_html)
            )
            sg.client.mail.send.post(request_body=internal_mail.get())
            
            logger.info(f"Partner onboarding emails sent for {current_user.email}")
        else:
            logger.info("SendGrid not configured — partner onboarding emails skipped. Configure via Admin > Email Settings.")
    except Exception as e:
        logger.warning(f"Failed to send partner onboarding emails: {e}")
        # Don't block the application submission if email fails

    return {
        "success": True,
        "message": "Partner application submitted. Our team will review your documents and reach out at partners@bidvex.ca.",
        "verification_status": "pending"
    }




@partners_router.get("/partner/status")
async def get_partner_status(current_user: User = Depends(get_current_user)):
    """Get the current user's partner account status."""
    db = get_db()
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "is_partner": user_doc.get("is_partner", False),
        "verification_status": user_doc.get("partner_verification_status", "unverified"),
        "company_name": user_doc.get("partner_company_name"),
        "neq_number": user_doc.get("partner_neq"),
        "applied_at": user_doc.get("partner_applied_at"),
        "verified_at": user_doc.get("partner_verified_at"),
        "rejection_reason": user_doc.get("partner_rejection_reason"),
        "custom_premium_rate": user_doc.get("custom_premium_rate"),
        # iter209 — resubmission counters surfaced to the frontend
        "resubmission_count": int(user_doc.get("resubmission_count") or 0),
        "max_resubmissions": 3,
        "rejection_history": user_doc.get("rejection_history") or [],
    }




@partners_router.get("/uploads/partner_docs/{filename}")
async def serve_partner_document(
    filename: str,
    request: Request,
    token: Optional[str] = Query(None),
):
    """Serve uploaded partner documents.

    Auth modes (in priority order):
      1. Cookie / Authorization header (normal API caller).
      2. `?token=<jwt>` query param — required for browsers opening the URL
         in a new tab (`<a target="_blank">`) because the browser cannot
         attach the `Authorization` header on a plain navigation.

    Owners (filename prefix `neq_{user_id}` / `cert_{user_id}`) may read
    their own docs. Admins / super_admins may read any.

    iter211 — `File not found` rewrite:
      • Returns structured JSON `{error_code, message_en, message_fr, ...}`
        instead of a flat string so the admin UI can render a useful CTA.
      • Strips legacy URL prefixes from `filename` defensively so old DB
        rows that stored absolute paths (`/api/uploads/...`) still work.
      • Searches BOTH common upload roots (`uploads/partner_docs` relative to
        backend CWD, and `/app/backend/uploads/partner_docs` absolute) to
        survive cwd drift across deployments.
    """
    from jose import jwt, JWTError, ExpiredSignatureError
    from deps import jwt_secret, security
    from fastapi.security import HTTPAuthorizationCredentials

    db = get_db()

    # ── Auth ──────────────────────────────────────────────────────────
    current_user = None
    try:
        creds: Optional[HTTPAuthorizationCredentials] = await security(request)
        current_user = await get_current_user(request, creds)
    except HTTPException:
        current_user = None

    if current_user is None and token:
        try:
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
            user_id = payload.get("sub")
            if user_id:
                user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
                if user_doc:
                    current_user = User(**user_doc)
        except (JWTError, ExpiredSignatureError):
            current_user = None

    if current_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # ── Defensive filename normalisation ─────────────────────────────
    # If the DB row stored an absolute URL prefix (legacy or migrated),
    # peel it off so `Path(...) / filename` resolves correctly.
    bare = filename
    for prefix in ("/api/uploads/partner_docs/", "/uploads/partner_docs/",
                   "api/uploads/partner_docs/", "uploads/partner_docs/"):
        if bare.startswith(prefix):
            bare = bare[len(prefix):]
    # Block path-traversal attempts post-strip
    if ".." in bare or "/" in bare or bare.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # ── Permission check ────────────────────────────────────────────
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    is_owner = bare.startswith(f"neq_{current_user.id}") or bare.startswith(f"cert_{current_user.id}")
    is_admin = (user_doc or {}).get("role") in ["admin", "super_admin"]
    if not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    # ── Search both upload roots ─────────────────────────────────────
    candidates = [
        Path("uploads/partner_docs") / bare,             # relative (uvicorn cwd = /app/backend)
        Path("/app/backend/uploads/partner_docs") / bare,  # absolute (kube cwd drift)
    ]
    found = next((p for p in candidates if p.exists() and p.is_file()), None)

    if found is None:
        # iter211 — structured error so the admin UI can render a "request
        # resubmission" CTA instead of a cryptic JSON. The owner field tells
        # the admin which partner to email.
        logger.warning(
            f"[partner_docs] missing file: {bare} requested by user={current_user.id} "
            f"role={'admin' if is_admin else 'owner'}"
        )
        # Try to find the owner so the admin can prompt resubmission
        owner_email = None
        owner_id = None
        owner_status = None
        # Extract user_id from filename pattern `neq_{user_id}_*` or `cert_{user_id}_*`
        import re
        m = re.match(r"^(?:neq|cert)_([0-9a-f-]{8,})", bare)
        try:
            if m:
                owner_doc = await db.users.find_one(
                    {"id": m.group(1)},
                    {"_id": 0, "id": 1, "email": 1, "partner_verification_status": 1},
                )
                if owner_doc:
                    owner_email = owner_doc.get("email")
                    owner_id = owner_doc.get("id")
                    owner_status = owner_doc.get("partner_verification_status")
        except Exception:
            pass
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "file_missing_on_disk",
                "filename": bare,
                "message_en": (
                    "This document is no longer available on the server. "
                    "Files uploaded before the most recent redeployment may have been lost. "
                    "Please ask the partner to resubmit their application."
                ),
                "message_fr": (
                    "Ce document n'est plus disponible sur le serveur. "
                    "Les fichiers téléversés avant le dernier redéploiement ont peut-être été perdus. "
                    "Veuillez demander au partenaire de soumettre à nouveau sa candidature."
                ),
                "owner_email": owner_email,
                "owner_user_id": owner_id,
                "owner_status": owner_status,
            },
        )

    return FileResponse(str(found))



# ── iter211 — Admin "request resubmission" + missing-files audit ─────────
@partners_router.post("/admin/partners/{user_id}/request-resubmission")
async def request_partner_resubmission(
    user_id: str,
    request: Request,
    current_user: User = Depends(get_current_user),
):
    """Admin-only. Resets a partner's verification status to `rejected` and
    emails them a bilingual notice asking to resubmit their application.

    Use case: an admin opens a document link in the admin queue and gets the
    `file_missing_on_disk` 404 (files lost in a redeploy). One click here
    resets the partner so they can use the existing Resubmit panel to re-upload.
    """
    db = get_db()
    # Authorize admin
    me = await db.users.find_one({"id": current_user.id}, {"_id": 0, "role": 1})
    if (me or {}).get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="admin_required")

    partner = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not partner:
        raise HTTPException(status_code=404, detail="partner_not_found")

    now = datetime.now(timezone.utc).isoformat()
    reason_en = "Your previously submitted documents are no longer available on our server (lost during a system update). Please resubmit your application — it only takes a minute."
    reason_fr = "Vos documents précédemment soumis ne sont plus disponibles sur notre serveur (perdus lors d'une mise à jour système). Veuillez soumettre à nouveau votre candidature — cela ne prend qu'une minute."

    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "partner_verification_status": "rejected",
            "partner_rejection_reason": reason_en,
            "partner_rejected_at": now,
            "partner_rejected_by": current_user.id,
            "partner_neq_document": None,
            "partner_certifications": [],
        }},
    )

    # Best-effort bilingual email
    try:
        from services.email_notifications import send_email
        frontend_url = _os.environ.get("FRONTEND_URL", "https://bidvex.com")
        applicant_lang = (partner.get("preferred_language") or "en").lower()
        is_fr = applicant_lang.startswith("fr")
        subject = "Action required — please resubmit your BidVex partner application" if not is_fr else "Action requise — soumettez à nouveau votre candidature partenaire BidVex"
        body = reason_fr if is_fr else reason_en
        cta = (f"<a href='{frontend_url}/become-partner' style='background:#0f172a;color:#fff;padding:10px 18px;border-radius:8px;text-decoration:none;display:inline-block;margin-top:12px;'>"
               f"{'Soumettre à nouveau' if is_fr else 'Resubmit application'}</a>")
        html = f"<p>{body}</p>{cta}<p style='font-size:12px;color:#64748b;margin-top:18px;'>BidVex · partners@bidvex.ca</p>"
        send_email(to_email=partner["email"], subject=subject, html_content=html)
    except Exception as exc:
        logger.warning(f"[partner-resubmission-req] email failed for {partner.get('email')}: {exc}")

    # Audit
    try:
        await db.admin_logs.insert_one({
            "id": str(uuid.uuid4()),
            "action": "request_partner_resubmission",
            "actor_id": current_user.id,
            "target_user_id": user_id,
            "reason": "documents_missing_on_disk",
            "created_at": now,
        })
    except Exception:
        pass

    return {
        "success": True,
        "user_id": user_id,
        "email": partner.get("email"),
        "new_status": "rejected",
    }


@partners_router.get("/admin/partners/missing-documents-audit")
async def audit_missing_partner_documents(
    current_user: User = Depends(get_current_user),
):
    """Admin-only. Walks every partner with a stored document path and checks
    whether the file actually exists on disk. Returns a per-partner report so
    admins can batch-trigger resubmissions for affected users (e.g. after a
    redeploy wipes the ephemeral uploads directory)."""
    db = get_db()
    me = await db.users.find_one({"id": current_user.id}, {"_id": 0, "role": 1})
    if (me or {}).get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="admin_required")

    def _bare(p):
        if not p:
            return None
        for prefix in ("/api/uploads/partner_docs/", "/uploads/partner_docs/",
                       "api/uploads/partner_docs/", "uploads/partner_docs/"):
            if p.startswith(prefix):
                return p[len(prefix):]
        return p

    def _exists(bare):
        if not bare:
            return False
        return (Path("uploads/partner_docs") / bare).exists() or \
               (Path("/app/backend/uploads/partner_docs") / bare).exists()

    cursor = db.users.find(
        {"$or": [
            {"partner_neq_document": {"$exists": True, "$ne": None}},
            {"partner_certifications": {"$exists": True, "$ne": []}},
        ]},
        {"_id": 0, "id": 1, "email": 1, "partner_company_name": 1,
         "partner_verification_status": 1, "partner_neq_document": 1,
         "partner_certifications": 1, "partner_applied_at": 1},
    )

    rows = []
    missing_count = 0
    healthy_count = 0
    async for u in cursor:
        neq_b = _bare(u.get("partner_neq_document"))
        neq_ok = _exists(neq_b) if neq_b else None
        cert_files = []
        for c in (u.get("partner_certifications") or []):
            b = _bare(c)
            cert_files.append({"filename": b, "exists": _exists(b) if b else False})
        partner_missing = (neq_b and not neq_ok) or any(not f["exists"] for f in cert_files)
        if partner_missing:
            missing_count += 1
        else:
            healthy_count += 1
        rows.append({
            "user_id": u["id"],
            "email": u.get("email"),
            "company": u.get("partner_company_name"),
            "status": u.get("partner_verification_status"),
            "applied_at": (u.get("partner_applied_at").isoformat() if hasattr(u.get("partner_applied_at"), "isoformat") else u.get("partner_applied_at")),
            "neq_filename": neq_b,
            "neq_exists": neq_ok,
            "cert_files": cert_files,
            "is_affected": partner_missing,
        })

    return {
        "total_partners_with_docs": len(rows),
        "affected": missing_count,
        "healthy": healthy_count,
        "rows": rows,
    }





@partners_router.post("/partner/resubmit")
async def resubmit_partner_application(
    company_name: str = Form(...),
    neq_number: str = Form(...),
    neq_document: UploadFile = File(...),
    certification_documents: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """iter209 Step 2 — Partner application resubmission.

    Rules:
      - status must currently be 'rejected'
      - max 3 attempts (returns 403 with bilingual message on 4th)
      - files always re-uploaded (no pre-fill on documents)
      - text fields (company_name, neq_number) accepted from FormData
    """
    from services.resubmission_service import resubmit_application

    db = get_db()

    # Re-use the upload helper from /partner/apply: save files first, build relative URLs
    upload_dir = Path("uploads/partner_docs")
    upload_dir.mkdir(parents=True, exist_ok=True)

    neq_contents = await neq_document.read()
    if len(neq_contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="NEQ document must be less than 10MB.")
    neq_ext = neq_document.filename.split('.')[-1] if '.' in neq_document.filename else 'pdf'
    neq_filename = f"neq_{current_user.id}_{uuid.uuid4().hex[:8]}.{neq_ext}"
    with open(upload_dir / neq_filename, "wb") as f:
        f.write(neq_contents)
    neq_url = f"/api/uploads/partner_docs/{neq_filename}"

    cert_urls: List[str] = []
    for cert_doc in certification_documents:
        cert_contents = await cert_doc.read()
        if len(cert_contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"File '{cert_doc.filename}' must be less than 10MB.")
        cert_ext = cert_doc.filename.split('.')[-1] if '.' in cert_doc.filename else 'pdf'
        cert_filename = f"cert_{current_user.id}_{uuid.uuid4().hex[:8]}.{cert_ext}"
        with open(upload_dir / cert_filename, "wb") as f:
            f.write(cert_contents)
        cert_urls.append(f"/api/uploads/partner_docs/{cert_filename}")

    payload = {
        "partner_company_name": (company_name or "").strip(),
        "partner_neq": (neq_number or "").strip(),
        "partner_neq_document": neq_url,
        "partner_certifications": cert_urls,
    }

    result = await resubmit_application(
        db,
        flavor="partner",
        user_id=current_user.id,
        user_email=current_user.email,
        payload=payload,
    )
    return result


@partners_router.get("/partner/payment-status")
async def get_partner_payment_status(current_user: User = Depends(get_current_user)):
    """Get current partner's payment status and checkout URL if needed."""
    db = get_db()
    if not current_user.is_partner and current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=400, detail="Not a partner account")
    
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    
    result = {
        "is_partner": True,
        "platform_fee_paid": user_doc.get("platform_fee_paid", False),
        "partner_verification_status": user_doc.get("partner_verification_status"),
        "partner_subscription_id": user_doc.get("partner_subscription_id"),
        "checkout_url": user_doc.get("partner_checkout_url"),
    }
    return result




class PartnerCheckoutPayload(BaseModel):
    """iter253 — Optional body for `/partner/create-checkout`.
    When `coupon_code` resolves to a 100% waiver via the promotion
    engine, Stripe is bypassed entirely — the partner's annual fee is
    marked paid in-place and a `promotion_usage` row is logged."""
    coupon_code: Optional[str] = None


@partners_router.post("/partner/create-checkout")
async def create_partner_checkout(
    payload: Optional[PartnerCheckoutPayload] = None,
    current_user: User = Depends(get_current_user),
):
    """Create a new Stripe Checkout Session for partner fee payment.

    iter253 — When `payload.coupon_code` resolves to a 100% waiver (e.g.
    BIDVEX-PARTNERS for partner_launch_offer), the Stripe redirect is
    skipped, the user's `platform_fee_paid` + `partner_subscription_active`
    flags are flipped in-place, and a `promotion_usage` row is recorded.
    """
    db = get_db()
    if not current_user.is_partner and current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=400, detail="Not a partner account")
    if current_user.platform_fee_paid:
        raise HTTPException(status_code=400, detail="Annual fee already paid")

    # iter257 — Coupon bypass + partial-discount pipeline. The annual
    # partner fee anchors at $100 (iter256 ledger correction). A 100%
    # waiver skips Stripe entirely; a partial discount creates a Stripe
    # Coupon on-the-fly and attaches it to the Checkout Session via the
    # `discounts` parameter so the user sees the reduced total directly
    # on Stripe (no more "Stripe charged me full price" bug).
    coupon = (payload.coupon_code if payload else None) or ""
    coupon = coupon.strip().upper()
    applied_stripe_coupon_id: Optional[str] = None
    if coupon:
        try:
            from services.promotion_runtime import compute_promotion_discount
            from routes.admin_promotions import record_promotion_usage
            base_fee = float(_os.environ.get("BIDVEX_PARTNER_ANNUAL_FEE_CAD", "100.0"))
            discount = await compute_promotion_discount(
                db=db,
                user_id=current_user.id,
                transaction_type="listing_fee",
                listing_type="vehicles",
                base_amount_cad=base_fee,
                coupon_code=coupon,
            )
            if getattr(discount, "applies", False) and getattr(discount, "is_full_waiver", False):
                # 100% waiver — skip Stripe, mark the partner as paid.
                # iter257 — Call record_promotion_usage DIRECTLY (the
                # previous `apply_and_record_discount(discount=...)`
                # call passed an invalid kwarg and silently raised
                # TypeError, falling through to full-price Stripe).
                now = datetime.now(timezone.utc).isoformat()
                try:
                    await record_promotion_usage(
                        db=db,
                        promotion_id=discount.promotion_id,
                        user_id=current_user.id,
                        transaction_type="listing_fee",
                        saved_amount=float(discount.discount_amount or base_fee),
                    )
                except Exception as usage_exc:  # noqa: BLE001
                    logger.warning(f"record_promotion_usage failed (non-fatal): {usage_exc}")
                await db.users.update_one(
                    {"id": current_user.id},
                    {"$set": {
                        "platform_fee_paid": True,
                        "partner_subscription_active": True,
                        "partner_subscription_promo_id": discount.promotion_id,
                        "partner_subscription_coupon_code": coupon,
                        "partner_subscription_activated_at": now,
                    }},
                )
                # iter272 — Free-activation is still a tier upgrade; bump
                # the originating external campaign's premium_upgrades
                # counter so admins see ROI on the coupon-driven cohort.
                try:
                    from routes.auth import record_premium_upgrade
                    await record_premium_upgrade(current_user.id)
                except Exception as upg_exc:  # noqa: BLE001
                    logger.warning(f"[iter272 premium-upgrade] partner free-activation non-fatal: {upg_exc}")
                base_url = _os.environ.get("REACT_APP_BACKEND_URL", "https://www.bidvex.com")
                return {
                    "free_activation": True,
                    "checkout_url": None,
                    "redirect_url": f"{base_url}/partner/dashboard?partner_payment=success&promo={coupon}",
                    "promotion_id": discount.promotion_id,
                    "coupon_code": coupon,
                    "discount_amount_cad": float(getattr(discount, "discount_amount", base_fee) or base_fee),
                    "final_amount_cad": 0.0,
                    "message_en": "🚀 Free Listing Activated! Your annual partner fee has been fully waived.",
                    "message_fr": "🚀 Annonce gratuite activée ! Vos frais annuels de partenaire ont été entièrement remboursés.",
                }
            # iter257 — Partial discount path. Create (or reuse) a Stripe
            # Coupon mirroring the promo's discount_percent and attach it
            # to the Checkout Session so Stripe renders the reduced total.
            if getattr(discount, "applies", False) and getattr(discount, "discount_percent", 0) > 0:
                applied_stripe_coupon_id = _ensure_stripe_coupon_for_promotion(
                    promotion_id=discount.promotion_id,
                    discount_percent=float(discount.discount_percent),
                    coupon_label=coupon,
                )
        except HTTPException:
            raise
        except Exception as exc:  # noqa: BLE001 — fall back to Stripe on any error
            logger.warning(f"Partner checkout coupon bypass failed: {exc}")

    try:
        price_id = await _get_or_create_partner_fee_price()
        base_url = _os.environ.get("REACT_APP_BACKEND_URL", "https://www.bidvex.com")
        
        customer_id = current_user.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.name,
                metadata={"user_id": current_user.id, "type": "partner"}
            )
            customer_id = customer.id
            await db.users.update_one({"id": current_user.id}, {"$set": {"stripe_customer_id": customer_id}})

        session_kwargs: Dict[str, Any] = dict(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"user_id": current_user.id, "type": "partner_activation", "business_name": current_user.company_name or current_user.name},
            success_url=f"{base_url}/partner/dashboard?session_id={{CHECKOUT_SESSION_ID}}&partner_payment=success",
            cancel_url=f"{base_url}/partner/dashboard?partner_payment=cancelled",
            subscription_data={
                "metadata": {"user_id": current_user.id, "type": "partner_annual_fee"}
            },
        )
        # iter257 — Attach the Stripe Coupon for partial discounts so
        # the checkout page renders the discounted total directly.
        if applied_stripe_coupon_id:
            session_kwargs["discounts"] = [{"coupon": applied_stripe_coupon_id}]
            session_kwargs["metadata"]["partner_coupon_code"] = coupon
            session_kwargs["metadata"]["stripe_coupon_id"] = applied_stripe_coupon_id
        session = stripe.checkout.Session.create(**session_kwargs)
        
        await db.users.update_one({"id": current_user.id}, {"$set": {
            "partner_checkout_session_id": session.id,
            "partner_checkout_url": session.url,
        }})
        
        return {
            "checkout_url": session.url,
            "applied_coupon_code": coupon if applied_stripe_coupon_id else None,
            "stripe_coupon_id": applied_stripe_coupon_id,
        }
    except Exception as e:
        logger.error(f"Failed to create partner checkout: {e}")
        raise HTTPException(status_code=500, detail="Failed to create payment session")




@partners_router.post("/partner/manage-billing")
async def create_partner_billing_portal(current_user: User = Depends(get_current_user)):
    """Create a Stripe Customer Portal session for partner billing management.
    Partners can download invoices (with GST/QST), update payment methods, and manage subscriptions."""
    db = get_db()
    if not current_user.is_partner and current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=400, detail="Not a partner account")
    
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    customer_id = user_doc.get("stripe_customer_id") if user_doc else None
    if not customer_id:
        raise HTTPException(status_code=400, detail="No billing account found. Please complete your initial payment first.")
    
    try:
        base_url = _os.environ.get("REACT_APP_BACKEND_URL", "https://www.bidvex.com")
        
        # Configure portal to open on invoices/billing history page
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{base_url}/partner/dashboard",
            flow_data={
                "type": "subscription_update_confirm",
            } if False else None,  # No flow_data — default portal view shows invoices
        )
        return {"url": session.url}
    except Exception as e:
        logger.error(f"Failed to create billing portal session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create billing portal session")




# iter216 — Lightweight status endpoint for the partner annual-fee banner
# polling. Kept separate from the heavy /dashboard endpoint so the frontend
# can poll every 60 s without re-running the full aggregation.

@partners_router.get("/partner/subscription/status")
async def get_partner_subscription_status(current_user: User = Depends(get_current_user)):
    """Returns the partner's annual-subscription status.

    Mirrors the same active-detection logic the dashboard uses so the banner
    polling never disagrees with the dashboard. Returns 200 even when the
    user is not a partner — `active` is just False in that case.
    """
    db = get_db()
    user_doc = await db.users.find_one({"id": current_user.id}, {
        "_id": 0, "platform_fee_paid": 1,
        "partner_subscription_active": 1,
        "partner_subscription_paid_at": 1,
        "partner_subscription_renewal_date": 1,
        "partner_payment_method": 1,
        "partner_fee_paid_at": 1,
    }) or {}
    active = bool(
        user_doc.get("platform_fee_paid")
        or user_doc.get("partner_subscription_active")
    )
    renewal = user_doc.get("partner_subscription_renewal_date")
    days_left = None
    if renewal:
        try:
            renewal_dt = datetime.fromisoformat(renewal.replace("Z", "+00:00"))
            days_left = max(0, (renewal_dt - datetime.now(timezone.utc)).days)
        except Exception:
            days_left = None
    return {
        "active": active,
        "renewal_date": renewal,
        "payment_method": user_doc.get("partner_payment_method"),
        "paid_at": user_doc.get("partner_subscription_paid_at") or user_doc.get("partner_fee_paid_at"),
        "days_until_renewal": days_left,
    }



@partners_router.get("/partner/dashboard")
async def get_partner_dashboard(current_user: User = Depends(get_current_user)):
    """Get aggregated dashboard data for partner accounts. Admins can also access."""
    db = get_db()
    if not current_user.is_partner and current_user.role not in ["admin", "super_admin"]:
        raise HTTPException(status_code=400, detail="Not a partner account")
    
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0, "password": 0})
    
    # Listing stats
    active_listings = await db.listings.count_documents({"seller_id": current_user.id, "status": "active"})
    total_listings = await db.listings.count_documents({"seller_id": current_user.id})
    active_multi = await db.multi_item_listings.count_documents({"seller_id": current_user.id, "status": "active"})
    total_multi = await db.multi_item_listings.count_documents({"seller_id": current_user.id})
    
    # Bid stats
    bid_pipeline = [
        {"$match": {"seller_id": current_user.id}},
        {"$group": {"_id": None, "total_bids": {"$sum": "$bid_count"}}},
    ]
    bid_results = await db.listings.aggregate(bid_pipeline).to_list(1)
    total_bids = bid_results[0]["total_bids"] if bid_results else 0
    
    # Subscription info from Stripe if available
    subscription_info = None
    sub_id = user_doc.get("partner_subscription_id")
    if sub_id:
        try:
            sub = stripe.Subscription.retrieve(sub_id)
            subscription_info = {
                "status": sub.status,
                "current_period_start": datetime.fromtimestamp(sub.current_period_start, tz=timezone.utc).isoformat(),
                "current_period_end": datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc).isoformat(),
                "cancel_at_period_end": sub.cancel_at_period_end,
                "plan_amount": sub.items.data[0].price.unit_amount / 100 if sub.items.data else 100,
                "plan_currency": sub.items.data[0].price.currency if sub.items.data else "cad",
                "plan_interval": sub.items.data[0].price.recurring.interval if sub.items.data else "year",
            }
        except Exception as e:
            logger.warning(f"Failed to retrieve partner subscription {sub_id}: {e}")
    
    # Recent activity (last 5 listing actions)
    recent_listings = await db.listings.find(
        {"seller_id": current_user.id},
        {"_id": 0, "id": 1, "title": 1, "status": 1, "created_at": 1, "bid_count": 1, "current_price": 1}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    recent_multi = await db.multi_item_listings.find(
        {"seller_id": current_user.id},
        {"_id": 0, "id": 1, "title": 1, "status": 1, "created_at": 1, "lots": 1}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    for m in recent_multi:
        m["lot_count"] = len(m.pop("lots", []))
    
    return {
        "partner": {
            "company_name": user_doc.get("partner_company_name"),
            "email": user_doc.get("email"),
            "verified_at": user_doc.get("partner_verified_at"),
            "custom_premium_rate": user_doc.get("custom_premium_rate"),
            # iter216 — `platform_fee_paid` is the legacy paid-via-Stripe flag.
            # `partner_subscription_active` is the modern unified flag set by the
            # admin "Manual Settle" action (for e-Transfer / cash / cheque).
            # Either is sufficient to show "Active" on the dashboard.
            "platform_fee_paid": bool(
                user_doc.get("platform_fee_paid")
                or user_doc.get("partner_subscription_active")
            ),
            "partner_fee_paid_at": user_doc.get("partner_fee_paid_at") or user_doc.get("partner_subscription_paid_at"),
            "partner_subscription_active": bool(user_doc.get("partner_subscription_active")),
            "partner_subscription_renewal_date": user_doc.get("partner_subscription_renewal_date"),
            "partner_payment_method": user_doc.get("partner_payment_method"),
            "stripe_connect_status": user_doc.get("stripe_connect_status"),
        },
        "subscription": subscription_info or (
            # iter216 — Synthesise a subscription block when admin manual-settled
            # so the partner dashboard's `subscription?.status === 'active'` check
            # still resolves to `active`.
            {
                "status": "active",
                "current_period_end": user_doc.get("partner_subscription_renewal_date"),
                "current_period_start": user_doc.get("partner_subscription_paid_at"),
                "cancel_at_period_end": False,
                "plan_amount": 100,
                "plan_currency": "cad",
                "plan_interval": "year",
                "manual_settled": True,
                "payment_method": user_doc.get("partner_payment_method"),
            } if user_doc.get("partner_subscription_active") else None
        ),
        "stats": {
            "active_listings": active_listings + active_multi,
            "total_listings": total_listings + total_multi,
            "active_single": active_listings,
            "active_multi": active_multi,
            "total_bids_received": total_bids,
        },
        "recent_listings": recent_listings,
        "recent_multi_auctions": recent_multi,
    }




@partners_router.get("/partner/fee-preview")
async def partner_fee_preview(
    hammer_price: float,
    custom_buyer_premium_rate: float = 0.0,
    current_user: User = Depends(get_current_user)
):
    """
    Preview the fee breakdown for a partner listing.
    Shows: Hammer, Buyer Premium, Platform Fee (3%), Stripe Recovery, Total.
    """
    if hammer_price <= 0:
        raise HTTPException(status_code=400, detail="Hammer price must be positive.")
    
    breakdown = calculate_partner_checkout(hammer_price, custom_buyer_premium_rate)
    return breakdown





@partners_router.get("/partner/stats")
async def get_partner_stats_endpoint(current_user: User = Depends(get_current_user)):
    """
    Partner metrics. Admin gets platform-wide data; partners get their own.
    Includes: active listings, total bids received, and projected revenue.
    """
    db = get_db()
    is_admin = current_user.role in ("admin", "super_admin")

    if not is_admin:
        user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
        if not user_doc or not user_doc.get("is_partner"):
            raise HTTPException(status_code=403, detail="Partner or admin access required")

    from services.partner_service import get_partner_stats
    platform_stats = await get_partner_stats(db)

    # Per-partner stats: scoped to the caller's own listings
    partner_id = current_user.id
    active_listings = await db.listings.count_documents(
        {"seller_id": partner_id, "status": "active"}
    )
    total_listings = await db.listings.count_documents(
        {"seller_id": partner_id}
    )

    # Total bids received across all partner's listings
    partner_listing_ids_cursor = db.listings.find(
        {"seller_id": partner_id}, {"_id": 0, "id": 1}
    )
    partner_listing_ids = [doc["id"] async for doc in partner_listing_ids_cursor]

    total_bids_received = 0
    projected_revenue = 0.0
    if partner_listing_ids:
        total_bids_received = await db.bids.count_documents(
            {"listing_id": {"$in": partner_listing_ids}}
        )
        # Projected revenue = sum of current_price on active listings
        revenue_cursor = db.listings.find(
            {"seller_id": partner_id, "status": "active"},
            {"_id": 0, "current_price": 1, "starting_price": 1},
        )
        async for listing in revenue_cursor:
            price = listing.get("current_price") or listing.get("starting_price") or 0
            projected_revenue += price

    # ── Partner Benefit: premiums retained this month via PARTNER_FLOW ──
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    benefit_pipeline = [
        {"$match": {
            "seller_id": partner_id,
            "flow_type": "PARTNER_FLOW",
            "payment_status": {"$in": ["paid", "completed", "succeeded"]},
            "created_at": {"$gte": month_start},
        }},
        {"$group": {
            "_id": None,
            "total_premium_retained": {"$sum": "$partner_premium_retained"},
            "count": {"$sum": 1},
        }},
    ]
    benefit_result = await db.payment_transactions.aggregate(benefit_pipeline).to_list(1)
    partner_benefit = {
        "premiums_retained_this_month": round(benefit_result[0]["total_premium_retained"], 2) if benefit_result else 0,
        "transactions_this_month": benefit_result[0]["count"] if benefit_result else 0,
    }

    return {
        **platform_stats,
        "my_active_listings": active_listings,
        "my_total_listings": total_listings,
        "my_total_bids_received": total_bids_received,
        "my_projected_revenue": round(projected_revenue, 2),
        "partner_benefit": partner_benefit,
    }


@partners_router.get("/partner/badge/{user_id}")
async def get_partner_badge(user_id: str):
    """
    Public endpoint returning the badge type for a given user.
    Returns null badge_type if user has no badge.
    """
    db = get_db()
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from services.partner_service import get_badge_type, is_verified_firm, get_partner_tier
    return {
        "user_id": user_id,
        "badge_type": get_badge_type(user),
        "is_verified_firm": is_verified_firm(user),
        "partner_tier": get_partner_tier(user),
    }
