"""
iter214 P2 — Admin User Management Actions
============================================
Two endpoints used by the Admin → Users tab:

  • POST /api/admin/users/{user_id}/send-notification
      Body: {
        notification_type: "upload_required" | "invoice" | "warning"
                          | "approval" | "rejection" | "general",
        subject:           str,
        body_en:           str,
        body_fr:           Optional[str],
        attached_transaction_id: Optional[str],
        send_via:          "email" | "in_app" | "both",
      }
      Sends bilingual email via SendGrid + creates an in-app notification.
      Logs the action to admin_actions for audit.

  • POST /api/admin/users/{user_id}/request-documents
      Body: {
        document_types:  list[str],   # ["government_id", "business_registration", ...]
        deadline:        ISO date,
        message:         Optional[str],
      }
      Sends bilingual email + creates an in-app notification.
      Stores the request in user_document_requests for the "Documents Overdue"
      badge logic.
"""
from datetime import datetime, timezone
from typing import List, Optional
import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import User, get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/users", tags=["admin-user-actions"])


# ───────────────────────────────────────────────────────────────────────
# Helpers
# ───────────────────────────────────────────────────────────────────────

async def _require_admin(user: User = Depends(get_current_user)) -> User:
    if getattr(user, "role", None) not in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def _record_admin_action(db, *, admin_id: str, admin_email: str, action: str, target_user_id: str, content: dict) -> None:
    """Append to admin_actions audit log. Non-fatal."""
    try:
        await db.admin_actions.insert_one({
            "id": str(uuid.uuid4()),
            "admin_id": admin_id,
            "admin_email": admin_email,
            "action": action,
            "target_user_id": target_user_id,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as e:
        logger.warning(f"[admin_action_log] failed: {e}")


# ───────────────────────────────────────────────────────────────────────
# Send Notification
# ───────────────────────────────────────────────────────────────────────

class SendNotificationPayload(BaseModel):
    notification_type: str = Field(...)  # upload_required|invoice|warning|approval|rejection|general
    subject: str = Field(..., min_length=2, max_length=200)
    body_en: str = Field(..., min_length=2)
    body_fr: Optional[str] = None
    attached_transaction_id: Optional[str] = None
    send_via: str = Field("both")  # email|in_app|both
    # iter266 Mission 3D — Optional attachment-request fields.
    requires_attachment: bool = False
    attachment_request_label: Optional[str] = None
    attachment_request_label_fr: Optional[str] = None
    attachment_types: Optional[str] = "PDF, JPG, PNG"
    attachment_max_mb: Optional[float] = 1.0


_VALID_TYPES = {
    "upload_required", "invoice", "warning",
    "approval", "rejection", "general",
}


@router.post("/{user_id}/send-notification")
async def admin_send_notification(
    user_id: str,
    payload: SendNotificationPayload,
    current_user: User = Depends(_require_admin),
):
    if payload.notification_type not in _VALID_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_type",
                "message_en": f"notification_type must be one of {sorted(_VALID_TYPES)}",
                "message_fr": f"notification_type doit être l'un de {sorted(_VALID_TYPES)}",
            },
        )

    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    sent_email = False
    in_app_id = None

    # ── In-app notification ──
    if payload.send_via in {"in_app", "both"}:
        in_app_id = str(uuid.uuid4())
        # iter217 Phase 3 — Write BOTH `message` (the canonical field read by
        # NotificationCenter) and `message_en`/`message_fr` (for templating).
        # iter266 Mission 3D — Carry optional attachment-request fields so
        # the centered detail modal can render an upload widget.
        await db.notifications.insert_one({
            "id": in_app_id,
            "user_id": user_id,
            "type": f"admin_{payload.notification_type}",
            "title": payload.subject,
            "title_fr": payload.subject,
            "message": payload.body_en,
            "body": payload.body_en,
            "body_fr": payload.body_fr or payload.body_en,
            "message_en": payload.body_en,
            "message_fr": payload.body_fr or payload.body_en,
            "data": {
                "attached_transaction_id": payload.attached_transaction_id,
            },
            "attached_transaction_id": payload.attached_transaction_id,
            "action_url": None,
            "action_type": None,
            "is_read": False,
            "read": False,
            "sender_name": "BidVex Admin",
            "color_type": "action_required" if payload.requires_attachment else "info",
            "requires_attachment": bool(payload.requires_attachment),
            "attachment_request_label": payload.attachment_request_label or "",
            "attachment_request_label_fr": payload.attachment_request_label_fr or "",
            "attachment_types": payload.attachment_types or "PDF, JPG, PNG",
            "attachment_max_mb": float(payload.attachment_max_mb or 1.0),
            "attachment_submitted": False,
            "attachment_url": None,
            "attachment_submitted_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by_admin": current_user.id,
        })
        # iter267 Mission 4 — Real-time push to the recipient's bell.
        try:
            from routes.notifications import broadcast_notification_to_user
            await broadcast_notification_to_user(user_id, {
                "id":      in_app_id,
                "user_id": user_id,
                "type":    f"admin_{payload.notification_type}",
                "title":   payload.subject,
                "title_fr": payload.subject,
                "message": payload.body_en,
                "body":    payload.body_en,
                "body_fr": payload.body_fr or payload.body_en,
                "sender_name": "BidVex Admin",
                "color_type": "action_required" if payload.requires_attachment else "info",
                "requires_attachment": bool(payload.requires_attachment),
                "attachment_request_label":    payload.attachment_request_label or "",
                "attachment_request_label_fr": payload.attachment_request_label_fr or "",
                "attachment_types":  payload.attachment_types or "PDF, JPG, PNG",
                "attachment_max_mb": float(payload.attachment_max_mb or 1.0),
                "read":    False,
                "is_read": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
        except Exception:  # noqa: BLE001
            pass

    # ── Email via SendGrid ──
    if payload.send_via in {"email", "both"} and user_doc.get("email"):
        try:
            from services.emails._email_core import send_email
            body_fr = payload.body_fr or payload.body_en
            html = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f8fafc;border-radius:12px;">
              <div style="padding:20px;background:white;border-radius:8px;">
                <h2 style="color:#1e40af;margin:0 0 12px;">{payload.subject}</h2>
                <div style="color:#334155;line-height:1.6;white-space:pre-wrap;">{payload.body_en}</div>
                <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">
                <div style="color:#334155;line-height:1.6;white-space:pre-wrap;">{body_fr}</div>
                <p style="color:#64748b;font-size:11px;margin-top:24px;">
                  BidVex Inc. — Sent by an administrator · Envoyé par un administrateur
                </p>
              </div>
            </div>
            """
            await send_email(to_email=user_doc["email"], subject=payload.subject, html_content=html)
            sent_email = True
        except Exception as e:
            logger.warning(f"[admin_send_notification] email failed: {e}")

    await _record_admin_action(
        db,
        admin_id=current_user.id,
        admin_email=current_user.email,
        action=f"send_notification:{payload.notification_type}",
        target_user_id=user_id,
        content={
            "subject": payload.subject,
            "send_via": payload.send_via,
            "email_sent": sent_email,
            "in_app_id": in_app_id,
        },
    )

    return {
        "success": True,
        "email_sent": sent_email,
        "in_app_id": in_app_id,
    }


# ───────────────────────────────────────────────────────────────────────
# Request Documents
# ───────────────────────────────────────────────────────────────────────

class RequestDocumentsPayload(BaseModel):
    document_types: List[str] = Field(..., min_length=1)
    deadline: str = Field(...)  # ISO date string
    message: Optional[str] = None


_DOC_TYPE_LABELS = {
    "government_id":           ("Government-issued ID", "Pièce d'identité gouvernementale"),
    "business_registration":   ("Business registration certificate", "Certificat d'enregistrement d'entreprise"),
    "dealer_licence":          ("Dealer licence", "Permis de concessionnaire"),
    "neq_proof":               ("NEQ proof", "Preuve NEQ"),
    "insurance_certificate":   ("Insurance certificate", "Certificat d'assurance"),
    "other":                   ("Other document", "Autre document"),
}


@router.post("/{user_id}/request-documents")
async def admin_request_documents(
    user_id: str,
    payload: RequestDocumentsPayload,
    current_user: User = Depends(_require_admin),
):
    # Validate document types
    unknown = [t for t in payload.document_types if t not in _DOC_TYPE_LABELS]
    if unknown:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "unknown_document_types",
                "unknown": unknown,
                "message_en": f"Unknown document types: {unknown}. Valid: {sorted(_DOC_TYPE_LABELS)}",
                "message_fr": f"Types de documents inconnus : {unknown}",
            },
        )

    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    # ── Persist the request ──
    req_id = str(uuid.uuid4())
    await db.user_document_requests.insert_one({
        "id": req_id,
        "user_id": user_id,
        "document_types": payload.document_types,
        "deadline": payload.deadline,
        "message": payload.message,
        "status": "pending",         # pending | fulfilled | overdue
        "created_by_admin": current_user.id,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # iter217 Phase 3 — Stamp the active deadline onto the user doc so the
    # admin user list can compute the Overdue badge in one query.
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "active_document_request_id": req_id,
            "document_request_deadline": payload.deadline,
            "document_request_status": "pending",
        }},
    )

    # ── In-app notification ──
    titles = [_DOC_TYPE_LABELS[t][0] for t in payload.document_types]
    titles_fr = [_DOC_TYPE_LABELS[t][1] for t in payload.document_types]
    body_en = (
        f"Please upload: {', '.join(titles)}. Deadline: {payload.deadline}.\n\n"
        f"{payload.message or ''}"
    ).strip()
    body_fr = (
        f"Veuillez téléverser : {', '.join(titles_fr)}. Date limite : {payload.deadline}.\n\n"
        f"{payload.message or ''}"
    ).strip()
    await db.notifications.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "type": "admin_document_request",
        "title": "Action Required — Document Upload Needed",
        "message": body_en,
        "message_en": body_en,
        "message_fr": body_fr,
        "is_read": False,
        "read": False,
        "action_url": "/settings?tab=documents",
        "action_type": "navigate",
        "doc_request_id": req_id,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by_admin": current_user.id,
    })

    # ── Email ──
    try:
        from services.emails._email_core import send_email
        list_html_en = "".join(f"<li>{t}</li>" for t in titles)
        list_html_fr = "".join(f"<li>{t}</li>" for t in titles_fr)
        msg_block = f"<p>{payload.message}</p>" if payload.message else ""
        html = f"""
        <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f8fafc;border-radius:12px;">
          <div style="padding:20px;background:white;border-radius:8px;">
            <h2 style="color:#b45309;margin:0 0 12px;">📁 Action Required — Document Upload Needed</h2>
            <p>Please upload the following document(s) by <strong>{payload.deadline}</strong>:</p>
            <ul>{list_html_en}</ul>
            {msg_block}
            <p>You can upload from your <a href="https://www.bidvex.com/settings">Profile Settings</a>.</p>
            <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">
            <h2 style="color:#b45309;margin:0 0 12px;">📁 Action requise — Téléchargement de document nécessaire</h2>
            <p>Veuillez téléverser le(s) document(s) suivant(s) avant le <strong>{payload.deadline}</strong> :</p>
            <ul>{list_html_fr}</ul>
            <p>Téléversez depuis vos <a href="https://www.bidvex.com/settings">Paramètres du profil</a>.</p>
          </div>
        </div>
        """
        await send_email(
            to_email=user_doc["email"],
            subject="Action Required — Document Upload Needed · Action requise",
            html_content=html,
        )
    except Exception as e:
        logger.warning(f"[admin_request_documents] email failed: {e}")

    await _record_admin_action(
        db,
        admin_id=current_user.id,
        admin_email=current_user.email,
        action="request_documents",
        target_user_id=user_id,
        content={
            "document_types": payload.document_types,
            "deadline": payload.deadline,
            "request_id": req_id,
        },
    )

    return {"success": True, "request_id": req_id}


@router.get("/{user_id}/document-requests")
async def admin_list_user_document_requests(
    user_id: str,
    current_user: User = Depends(_require_admin),
):
    """Return all document requests on a user (used by the Overdue badge)."""
    db = get_db()
    rows = await db.user_document_requests.find({"user_id": user_id}, {"_id": 0})\
        .sort("created_at", -1).limit(50).to_list(50)
    today = datetime.now(timezone.utc).date().isoformat()
    out = []
    for r in rows:
        is_overdue = (r.get("status") == "pending") and (r.get("deadline", "") < today)
        out.append({**r, "is_overdue": is_overdue})
    return {"requests": out, "overdue_count": sum(1 for r in out if r["is_overdue"])}


# ───────────────────────────────────────────────────────────────────────
# iter215 — Additional admin actions (Edit Profile, Reset Password,
# Change Tier, Convert to Demo, View Transactions, View Subscription)
# ───────────────────────────────────────────────────────────────────────

class EditProfilePayload(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    province: Optional[str] = None
    account_type: Optional[str] = None  # personal | business | partner | vehicle_dealer | storage_facility


@router.patch("/{user_id}/profile")
async def admin_edit_user_profile(
    user_id: str,
    payload: EditProfilePayload,
    current_user: User = Depends(_require_admin),
):
    """Admin edits a user's basic profile data. Email change is allowed but
    enforces uniqueness."""
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    update = {k: v for k, v in payload.model_dump(exclude_none=True).items() if v != ""}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Email uniqueness
    if update.get("email") and update["email"] != user_doc.get("email"):
        existing = await db.users.find_one({"email": update["email"]}, {"_id": 0, "id": 1})
        if existing and existing.get("id") != user_id:
            raise HTTPException(status_code=409, detail={"error": "email_taken", "message": "Email already in use"})

    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    update["updated_by_admin"] = current_user.id
    await db.users.update_one({"id": user_id}, {"$set": update})
    await _record_admin_action(
        db, admin_id=current_user.id, admin_email=current_user.email,
        action="edit_profile", target_user_id=user_id, content=update,
    )
    return {"success": True, "updated_fields": list(update.keys())}


@router.post("/{user_id}/reset-password")
async def admin_reset_password(
    user_id: str,
    current_user: User = Depends(_require_admin),
):
    """Send a password-reset email to the user. Re-uses the public
    `/api/auth/forgot-password` flow so the user gets a single tokenised link."""
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc or not user_doc.get("email"):
        raise HTTPException(status_code=404, detail="User not found or no email on file")

    sent = False
    try:
        # Try to call the existing password-reset service
        from services import password_reset_service as prs  # type: ignore
        if hasattr(prs, "send_password_reset_email"):
            await prs.send_password_reset_email(db, user_doc["email"])
            sent = True
    except Exception as e:
        logger.warning(f"[admin_reset_password] dedicated service unavailable: {e}")

    # Fallback: generate a one-time reset token + send a SendGrid email
    if not sent:
        try:
            import secrets
            token = secrets.token_urlsafe(32)
            await db.password_reset_tokens.insert_one({
                "id": str(uuid.uuid4()),
                "user_id": user_id,
                "token": token,
                "expires_at": datetime.now(timezone.utc).isoformat(),
                "issued_by_admin": current_user.id,
            })
            from services.emails._email_core import send_email
            url = f"https://www.bidvex.com/reset-password?token={token}"
            html = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f8fafc;border-radius:12px;">
              <div style="padding:20px;background:white;border-radius:8px;">
                <h2 style="color:#1e40af;margin:0 0 12px;">Reset your BidVex password</h2>
                <p>An administrator has issued a password reset for your account.</p>
                <div style="text-align:center;margin:20px 0;">
                  <a href="{url}" style="display:inline-block;padding:12px 28px;background:#2563eb;color:white;text-decoration:none;border-radius:8px;font-weight:600;">
                    Reset password · Réinitialiser
                  </a>
                </div>
                <p style="color:#64748b;font-size:11px;text-align:center;">
                  If you did not expect this email, contact support@bidvex.com.
                </p>
              </div>
            </div>
            """
            await send_email(
                to_email=user_doc["email"],
                subject="Reset your BidVex password · Réinitialiser votre mot de passe",
                html_content=html,
            )
            sent = True
        except Exception as e:
            logger.error(f"[admin_reset_password] fallback email failed: {e}")

    await _record_admin_action(
        db, admin_id=current_user.id, admin_email=current_user.email,
        action="reset_password", target_user_id=user_id, content={"email_sent": sent},
    )
    return {"success": sent, "email_sent": sent}


class ChangeTierPayload(BaseModel):
    tier: str  # standard | premium | vip_elite


_VALID_TIERS = {"standard", "premium", "vip_elite"}


@router.post("/{user_id}/change-tier")
async def admin_change_buyer_tier(
    user_id: str,
    payload: ChangeTierPayload,
    current_user: User = Depends(_require_admin),
):
    """Change an individual user's buyer tier."""
    if payload.tier not in _VALID_TIERS:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_tier",
                "message_en": f"Tier must be one of {sorted(_VALID_TIERS)}",
                "message_fr": f"Le niveau doit être l'un de {sorted(_VALID_TIERS)}",
            },
        )
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "buyer_tier": 1, "email": 1})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    prev = user_doc.get("buyer_tier") or "standard"
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "buyer_tier": payload.tier,
            "buyer_tier_updated_at": datetime.now(timezone.utc).isoformat(),
            "buyer_tier_updated_by": current_user.id,
        }},
    )
    await _record_admin_action(
        db, admin_id=current_user.id, admin_email=current_user.email,
        action="change_tier", target_user_id=user_id,
        content={"from": prev, "to": payload.tier},
    )
    return {"success": True, "from": prev, "to": payload.tier}


@router.post("/{user_id}/convert-to-demo")
async def admin_convert_to_demo(
    user_id: str,
    current_user: User = Depends(_require_admin),
):
    """Flip is_demo_account on a user (and back). Idempotent."""
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "is_demo_account": 1})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    new_value = not bool(user_doc.get("is_demo_account"))
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "is_demo_account": new_value,
            "demo_toggled_at": datetime.now(timezone.utc).isoformat(),
            "demo_toggled_by": current_user.id,
        }},
    )
    await _record_admin_action(
        db, admin_id=current_user.id, admin_email=current_user.email,
        action="convert_to_demo", target_user_id=user_id,
        content={"is_demo_account": new_value},
    )
    return {"success": True, "is_demo_account": new_value}


@router.get("/{user_id}/transactions")
async def admin_user_transactions(
    user_id: str,
    limit: int = 50,
    current_user: User = Depends(_require_admin),
):
    """List transactions (buyer + seller side) for the user."""
    db = get_db()
    rows = await db.transactions.find(
        {"$or": [{"buyer_id": user_id}, {"seller_id": user_id}]},
        {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(limit)
    return {"total": len(rows), "transactions": rows}


@router.get("/{user_id}/subscription-status")
async def admin_user_subscription_status(
    user_id: str,
    current_user: User = Depends(_require_admin),
):
    """Compose a snapshot of the user's subscription flags for the admin
    "View Subscription Status" modal. Works for dealer, partner, and
    storage-facility accounts."""
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {
        "_id": 0,
        # Dealer
        "dealer_subscription_active": 1, "dealer_subscription_status": 1,
        "dealer_subscription_renewal": 1, "dealer_subscription_start": 1,
        "dealer_subscription_manual_method": 1, "dealer_subscription_manual_reference": 1,
        "vehicle_dealer_suspended": 1,
        # Partner
        "partner_subscription_active": 1, "partner_subscription_status": 1,
        "partner_subscription_renewal": 1, "partner_subscription_start": 1,
        # Storage facility
        "storage_subscription_active": 1, "storage_subscription_status": 1,
        "storage_subscription_renewal": 1,
        # Account flags
        "is_vehicle_dealer": 1, "is_licensed_partner": 1, "is_storage_facility": 1,
        "buyer_tier": 1, "account_type": 1,
    }) or {}
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    return user_doc


# ───────────────────────────────────────────────────────────────────────
# iter216 P3 — Admin visibility + control over the 6-email onboarding journey
# ───────────────────────────────────────────────────────────────────────


@router.get("/{user_id}/email-journey")
async def admin_get_user_email_journey(
    user_id: str,
    current_user: User = Depends(_require_admin),
):
    """Returns the full journey doc for the admin user-detail panel."""
    db = get_db()
    j = await db.user_email_journey.find_one({"user_id": user_id}, {"_id": 0})
    if not j:
        return {"journey": None, "status": "not_enrolled"}
    return {"journey": j, "status": "enrolled" if j.get("journey_active") else "completed"}


@router.post("/{user_id}/email-journey/trigger/{email_number}")
async def admin_trigger_journey_email(
    user_id: str,
    email_number: int,
    current_user: User = Depends(_require_admin),
):
    """Admin manually fires one of the 6 emails NOW (re-sends if already
    sent — useful for support cases)."""
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    if email_number not in {1, 2, 3, 4, 5, 6}:
        raise HTTPException(status_code=400, detail="email_number must be 1–6")
    from services.email_journey import dispatch_journey_email
    ok = await dispatch_journey_email(db, user_doc, email_number=email_number)
    await _record_admin_action(
        db, admin_id=current_user.id, admin_email=current_user.email,
        action="journey_manual_trigger", target_user_id=user_id,
        content={"email_number": email_number, "success": ok},
    )
    return {"success": ok, "email_number": email_number}


@router.post("/{user_id}/email-journey/cancel")
async def admin_cancel_journey(
    user_id: str,
    current_user: User = Depends(_require_admin),
):
    """Cancel the remaining journey emails for a user."""
    db = get_db()
    res = await db.user_email_journey.update_one(
        {"user_id": user_id},
        {"$set": {
            "journey_active": False,
            "journey_cancelled_at": datetime.now(timezone.utc).isoformat(),
            "journey_cancelled_by": current_user.id,
        }},
    )
    await _record_admin_action(
        db, admin_id=current_user.id, admin_email=current_user.email,
        action="journey_cancel", target_user_id=user_id,
        content={"matched": res.matched_count},
    )
    return {"success": True, "matched": res.matched_count}


@router.post("/{user_id}/email-journey/reset")
async def admin_reset_journey(
    user_id: str,
    current_user: User = Depends(_require_admin),
):
    """Delete the existing journey + re-enrol from Email 1."""
    db = get_db()
    await db.user_email_journey.delete_one({"user_id": user_id})
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    from services.email_journey import schedule_journey_for_user
    journey_id = await schedule_journey_for_user(db, user_doc)
    await _record_admin_action(
        db, admin_id=current_user.id, admin_email=current_user.email,
        action="journey_reset", target_user_id=user_id,
        content={"new_journey_id": journey_id},
    )
    return {"success": True, "journey_id": journey_id}

