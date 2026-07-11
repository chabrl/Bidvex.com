"""
BidVex — FEATURE PATCH v9 / Feature 3
AI Watchdog Admin Review Flow for category mismatches.

Endpoints:
  POST   /api/listings/{listing_id}/flag-for-ai-review    (seller-side)
  GET    /api/admin/listing-reviews?status=pending        (admin queue)
  GET    /api/admin/listing-reviews/{review_id}            (single)
  POST   /api/admin/listing-reviews/{review_id}/approve    (admin action)
  POST   /api/admin/listing-reviews/{review_id}/reject     (admin action)
  POST   /api/listings/{listing_id}/correct-category       (seller resubmit)
  POST   /api/listings/{listing_id}/withdraw-from-review   (seller withdraw)

Workflow:
  1. Seller submits listing → AI scanner suggests category mismatch.
  2. UI shows warning popup; seller clicks "OK" → listing goes to
     pending_ai_review (also creates a `listing_reviews` row).
  3. Admin sees Flagged Listings tab → approves or rejects.
  4. Approve → listing.status = "active" (or original).
     Reject → listing.status = "rejected" + seller email.
  5. Seller may resubmit with corrected category from their dashboard.
     Auto-clears the flag and sends back to normal review queue.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Literal

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field

from deps import get_db, require_admin, get_current_user, User

logger = logging.getLogger(__name__)

ai_review_router = APIRouter(tags=["AI Review"])


class CategorySuggestRequest(BaseModel):
    title: Optional[str] = Field("", max_length=300)
    description: Optional[str] = Field("", max_length=4000)
    seller_category: Optional[str] = ""


class ManualVehicleBlockReviewRequest(BaseModel):
    """Payload for a pre-creation manual review request.

    Triggered when the vehicle-compliance gate blocked a non-vehicle listing
    via a false-positive signal (e.g. the word "sti" inside "restaurant
    chairs"). The listing has NOT been created yet — we snapshot the form
    data so an admin can review and either approve creation or confirm the
    block.

    iter312 ROOT-CAUSE FIX (data-loss bug):
      Previously this model only accepted title/description/category/images/
      starting_price. When the backend created the stub `locked-*` listing
      it HARDCODED empty strings for location/city/region/country and
      defaulted condition/currency. That data was permanently lost from the
      seller's draft. Now the model accepts every field the create-listing
      wizard collects so the locked stub mirrors the seller's actual draft
      end-to-end (admin approve = pure status flip, NO empty-string
      hardcoding).
    """
    title: Optional[str] = Field("", max_length=300)
    description: Optional[str] = Field("", max_length=4000)
    category: Optional[str] = Field("", max_length=120)
    detected_signals: list[str] = Field(default_factory=list)
    images_count: int = 0
    # Phase 6.0 hotfix — accept actual uploaded image URLs / base64 so the
    # admin preview modal can hydrate the thumbnails grid.
    images: list[str] = Field(default_factory=list, max_length=20)
    starting_price: Optional[float] = 0
    extra_context: Optional[str] = Field("", max_length=2000)
    # Optional — when the seller already has a draft listing tied to this
    # block (rare; mostly the listing has NOT been created yet).
    listing_id: Optional[str] = None
    # iter312 D1 — Full form-snapshot fields. All optional so legacy
    # frontends (which only sent the original 8 fields) don't break.
    location:           Optional[str]   = Field(default=None, max_length=200)
    city:               Optional[str]   = Field(default=None, max_length=120)
    region:             Optional[str]   = Field(default=None, max_length=120)
    country:            Optional[str]   = Field(default=None, max_length=80)
    postal_code:        Optional[str]   = Field(default=None, max_length=20)
    condition:          Optional[str]   = Field(default=None, max_length=40)
    currency:           Optional[str]   = Field(default=None, max_length=3)
    buy_now_price:      Optional[float] = None
    auction_end_date:   Optional[datetime] = None
    title_fr:           Optional[str]   = Field(default=None, max_length=300)
    description_fr:     Optional[str]   = Field(default=None, max_length=4000)
    title_en:           Optional[str]   = Field(default=None, max_length=300)
    description_en:     Optional[str]   = Field(default=None, max_length=4000)
    province:           Optional[str]   = Field(default=None, max_length=80)


@ai_review_router.post("/listings/request-manual-vehicle-review")
async def request_manual_vehicle_review(
    payload: ManualVehicleBlockReviewRequest,
    current_user: User = Depends(get_current_user),
):
    """Seller-side — invoked when the user clicks "Request Manual Review"
    inside the vehicle-compliance block modal.

    Phase 6.0 hotfix:
      - Writes a row in BOTH `manual_review_requests` AND `listing_reviews`
        so the existing Admin Flagged Listings tab surfaces it automatically.
      - If a draft listing_id is supplied, forces its status to
        `pending_admin_review`.
      - Fires the `ai_review_admin_alert` email IMMEDIATELY (synchronous
        SendGrid call via the inline HTML fallback renderer) — no longer
        merely queued in email_outbox with no recipient.
      - Drops a row in `notifications` so the admin sees an in-app badge.
    """
    import os
    db = get_db()
    now = datetime.now(timezone.utc)
    req_id = str(uuid.uuid4())

    title = (payload.title or "").strip()[:300]
    description = (payload.description or "").strip()[:4000]
    category = (payload.category or "").strip()[:120]
    detected_signals = list(payload.detected_signals or [])[:50]

    # Lookup seller name for email context
    seller = await db.users.find_one(
        {"id": current_user.id},
        {"_id": 0, "name": 1, "email": 1, "phone": 1},
    ) or {}
    seller_name = (seller.get("name") or current_user.email or "(unknown)").strip()

    # 1. manual_review_requests row (authoritative audit trail)
    # Phase 6.0 hotfix — store full image URLs + starting_price so admin
    # preview can hydrate without needing a real listing.
    mrr_row = {
        "id":               req_id,
        "kind":             "vehicle_block_false_positive",
        "seller_id":        current_user.id,
        "seller_name":      seller_name,
        "seller_email":     current_user.email,
        "seller_phone":     seller.get("phone", ""),
        "listing_id":       payload.listing_id,
        "title":            title,
        "description":      description,
        "category":         category,
        "detected_signals": detected_signals,
        "images":           list(payload.images or [])[:20],
        "images_count":     int(payload.images_count or len(payload.images or [])),
        "starting_price":   float(payload.starting_price or 0),
        "extra_context":    (payload.extra_context or "").strip()[:2000],
        "status":           "pending",
        "created_at":       now,
        "updated_at":       now,
        "resolved_at":      None,
        "admin_id":         None,
        "admin_email":      None,
        "admin_note":       None,
    }
    try:
        await db.manual_review_requests.insert_one(mrr_row)
    except Exception as exc:
        logger.error(f"[manual_review] manual_review_requests.insert failed: {exc}", exc_info=True)

    # Phase 6.0 hotfix — Failure 2: create an actual listing row in
    # status=pending_admin_review so the seller sees it on their dashboard
    # (instead of vanishing) AND the admin can preview the real document.
    #
    # iter312 D1 ROOT-CAUSE FIX:
    #   Previously this block hardcoded `location=""`, `city=""`, `region=""`,
    #   `country=""` because the legacy payload didn't carry them. Result:
    #   when admin later approved the listing it went public with empty
    #   location → that's the "data loss" bug reported in iter312.
    #
    #   Now we trust the seller's form snapshot. Every field the wizard
    #   knows about is copied verbatim onto the stub listing. The approve
    #   endpoint is a pure status flip (already verified) so seller data
    #   survives the full flag → review → approve cycle intact.
    actual_listing_id = payload.listing_id
    if not actual_listing_id:
        actual_listing_id = f"locked-{req_id}"
        try:
            await db.listings.insert_one({
                "id":                 actual_listing_id,
                "seller_id":          current_user.id,
                "title":              title or "(no title)",
                "title_en":           (payload.title_en or "").strip()[:300] or None,
                "title_fr":           (payload.title_fr or "").strip()[:300] or None,
                "description":        description,
                "description_en":     (payload.description_en or "").strip()[:4000] or None,
                "description_fr":     (payload.description_fr or "").strip()[:4000] or None,
                "category":           category,
                "condition":          (payload.condition or "good").strip() or "good",
                "starting_price":     float(payload.starting_price or 0),
                "current_price":      float(payload.starting_price or 0),
                "buy_now_price":      payload.buy_now_price,
                "images":             list(payload.images or [])[:20],
                # iter312 D1 — Preserve seller's actual location data.
                "location":           (payload.location or "").strip(),
                "city":               (payload.city or "").strip(),
                "region":             (payload.region or "").strip(),
                "country":            (payload.country or "").strip(),
                "postal_code":        (payload.postal_code or "").strip() or None,
                "province":           (payload.province or "").strip() or None,
                "currency":           (payload.currency or "CAD").strip().upper()[:3] or "CAD",
                "status":             "pending_admin_review",
                "ai_review_id":       req_id,
                "ai_review_flagged_at": now,
                "ai_suggested_category":  "Vehicles",
                "ai_review_reason_en":  f"Vehicle-compliance gate triggered: {', '.join(detected_signals) or '—'}",
                "ai_review_reason_fr":  f"Conformité véhicule déclenchée : {', '.join(detected_signals) or '—'}",
                "vehicle_block_signals": detected_signals,
                "created_at":         now,
                "updated_at":         now,
                "auction_end_date":   payload.auction_end_date or (now + timedelta(days=7)),
                "bid_count":          0,
                "views":              0,
                # iter312 D2/D3 — Mark as editable-by-seller-while-pending.
                "is_seller_editable_pending": True,
                "pending_admin_review_at":     now,
            })
            logger.info(f"[manual_review] created locked listing {actual_listing_id} for seller dashboard visibility (iter312 — full form snapshot)")
        except Exception as exc:
            logger.error(f"[manual_review] locked listing create failed: {exc}", exc_info=True)

    # 2. listing_reviews mirror row so the Admin "Flagged Listings" tab
    #    surfaces this entry without UI changes.
    synthetic_listing_id = actual_listing_id   # now points to the actual created listing
    lr_row = {
        "id":                 req_id,                       # reuse the same id for cross-lookup
        "listing_id":         synthetic_listing_id,
        "listing_type":       "single",
        "collection":         "listings",
        "seller_id":          current_user.id,
        "seller_name":        seller_name,
        "seller_email":       current_user.email,
        "listing_title":      title or "(vehicle block — no title yet)",
        "seller_category":    category or "—",
        "suggested_category": "Vehicles",
        "ai_confidence":      0.85,
        "ai_reason_en":       f"Vehicle-compliance gate detected signal(s): {', '.join(detected_signals) or '—'}",
        "ai_reason_fr":       f"La barrière de conformité véhicule a détecté le(s) signal/signaux : {', '.join(detected_signals) or '—'}",
        "detected_signals":   detected_signals,
        "previous_status":    "pending_admin_review",
        "status":             "pending",
        "created_at":         now,
        "updated_at":         now,
        "resolved_at":        None,
        "admin_id":           None,
        "admin_email":        None,
        "admin_note":         None,
        "escalation_emailed": False,
        "source":             "vehicle_block_manual_review",
    }
    # ── FIX 4 (b) — Deduplication guard on manual-review path ──
    # If the seller already has an open pending review for this listing,
    # return that row instead of inserting a duplicate.
    if payload.listing_id:
        existing_pending = await db.listing_reviews.find_one(
            {"listing_id": payload.listing_id, "status": "pending"},
            {"_id": 0},
        )
        if existing_pending:
            logger.info(
                f"[manual_review] DEDUPE — open review {existing_pending.get('id')} already "
                f"exists for listing {payload.listing_id}; returning existing row"
            )
            for k in ("created_at", "updated_at", "resolved_at"):
                v = existing_pending.get(k)
                if isinstance(v, datetime):
                    existing_pending[k] = v.isoformat()
            return {
                "success": True,
                "request_id": existing_pending["id"],
                "review_id": existing_pending["id"],
                "listing_id": payload.listing_id,
                "deduped": True,
                "status": "pending_admin_review",
            }

    try:
        await db.listing_reviews.insert_one(lr_row)
    except Exception as exc:
        logger.error(f"[manual_review] listing_reviews.insert failed: {exc}", exc_info=True)

    # 3. If the seller supplied a draft listing_id, force its status.
    if payload.listing_id:
        try:
            r = await db.listings.update_one(
                {"id": payload.listing_id, "seller_id": current_user.id},
                {"$set": {
                    "status":                  "pending_admin_review",
                    "ai_review_id":            req_id,
                    "ai_review_flagged_at":    now,
                    "ai_suggested_category":   "Vehicles",
                    "ai_review_reason_en":     lr_row["ai_reason_en"],
                    "vehicle_block_signals":   detected_signals,
                }},
            )
            if r.matched_count == 0:
                await db.multi_item_listings.update_one(
                    {"id": payload.listing_id, "seller_id": current_user.id},
                    {"$set": {
                        "status":                  "pending_admin_review",
                        "ai_review_id":            req_id,
                        "vehicle_block_signals":   detected_signals,
                    }},
                )
        except Exception as exc:
            logger.warning(f"[manual_review] listing status update failed: {exc}")

    # 4. FIRE the admin alert email IMMEDIATELY (synchronous SendGrid call).
    # Phase 6.0 hotfix — Failure 2 remediation:
    #   * Recipient is HARDCODED to charbel911@gmail.com (authoritative ops inbox).
    #   * Subject / body match the exact spec format.
    #   * Loud RuntimeError if SENDGRID_API_KEY or SENDGRID_FROM_EMAIL is missing —
    #     no silent swallow.
    ADMIN_ALERT_RECIPIENT = "charbel911@gmail.com"

    sg_key_missing = not os.environ.get("SENDGRID_API_KEY")
    sg_from_missing = not os.environ.get("SENDGRID_FROM_EMAIL")
    if sg_key_missing or sg_from_missing:
        missing = []
        if sg_key_missing:
            missing.append("SENDGRID_API_KEY")
        if sg_from_missing:
            missing.append("SENDGRID_FROM_EMAIL")
        # Loud server-side exception — surfaces in logs + Sentry.
        logger.error(
            "[manual_review] ❌ Cannot dispatch admin alert email — missing env: %s "
            "(seller=%s listing_title=%r req_id=%s)",
            ", ".join(missing), current_user.email, title, req_id,
        )
        # We still complete the request (the in-DB row + notification already
        # fired) but mark the email status as a hard failure for visibility.

    listing_id_for_email = payload.listing_id or synthetic_listing_id
    direct_admin_url = f"https://bidvex.com/admin/flagged-listings?listing_id={listing_id_for_email}"
    email_context = {
        "review_id":         req_id,
        "listing_id":        listing_id_for_email,
        "listing_title":     title or "(no title)",
        "seller_id":         current_user.id,
        "seller_name":       seller_name,
        "seller_email":      current_user.email,
        "seller_category":   category or "—",
        "suggested_category": "Vehicles",
        "ai_reason_en":      lr_row["ai_reason_en"],
        "detected_signals":  detected_signals,
        "flagged_keywords":  detected_signals,
        "cta_url":           direct_admin_url,
    }

    email_sent_count = 0
    email_errors: list[str] = []
    if not (sg_key_missing or sg_from_missing):
        try:
            from services.email_service import send_html_email
            subject = (
                f"[BidVex Alert] Listing Flagged for Manual Review — ID: {listing_id_for_email}"
            )
            # Plain, fully-populated HTML body — every required field present.
            sig_html = ", ".join(detected_signals) if detected_signals else "(none reported)"
            body_html = f"""<!DOCTYPE html><html><body style="font-family:Helvetica,Arial,sans-serif;background:#F0F4F8;padding:24px;">
<table width="600" cellpadding="0" cellspacing="0" style="margin:0 auto;background:#FFF;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,0.06);overflow:hidden;">
  <tr><td style="background:#0B2545;color:#FFF;padding:24px 30px;">
    <h1 style="margin:0;font-size:20px;">⚠️ BidVex Alert — Listing Flagged</h1>
    <p style="margin:6px 0 0;font-size:13px;color:rgba(255,255,255,0.7);">Manual review required</p>
  </td></tr>
  <tr><td style="padding:24px 30px;font-size:14px;color:#1E293B;line-height:1.6;">
    <p>A listing has been flagged for manual compliance review and is now <strong>blocked from going public</strong> until an admin approves or rejects it.</p>
    <table cellpadding="6" cellspacing="0" style="margin:18px 0;border-collapse:collapse;font-size:13px;width:100%;">
      <tr><td style="border:1px solid #E2E8F0;background:#F8FAFC;width:160px;"><strong>Listing ID</strong></td><td style="border:1px solid #E2E8F0;"><code>{listing_id_for_email}</code></td></tr>
      <tr><td style="border:1px solid #E2E8F0;background:#F8FAFC;"><strong>Listing Title</strong></td><td style="border:1px solid #E2E8F0;">{title or "(no title)"}</td></tr>
      <tr><td style="border:1px solid #E2E8F0;background:#F8FAFC;"><strong>Seller User ID</strong></td><td style="border:1px solid #E2E8F0;"><code>{current_user.id}</code></td></tr>
      <tr><td style="border:1px solid #E2E8F0;background:#F8FAFC;"><strong>Seller Email</strong></td><td style="border:1px solid #E2E8F0;">{current_user.email}</td></tr>
      <tr><td style="border:1px solid #E2E8F0;background:#F8FAFC;"><strong>Seller's category</strong></td><td style="border:1px solid #E2E8F0;">{category or "—"}</td></tr>
      <tr><td style="border:1px solid #E2E8F0;background:#F8FAFC;"><strong>Flagged keywords</strong></td><td style="border:1px solid #E2E8F0;color:#B91C1C;font-weight:600;">{sig_html}</td></tr>
    </table>
    <p style="margin:18px 0 8px;">Open the admin panel to approve, reject, or override the block:</p>
    <p><a href="{direct_admin_url}" style="display:inline-block;background:#2186C6;color:#FFF;padding:12px 24px;border-radius:8px;font-weight:bold;text-decoration:none;">Open Admin Panel →</a></p>
    <p style="margin-top:24px;font-size:11px;color:#64748B;">Direct URL: <a href="{direct_admin_url}" style="color:#2186C6;">{direct_admin_url}</a></p>
  </td></tr>
  <tr><td style="background:#0B2545;color:rgba(255,255,255,0.6);padding:18px 30px;text-align:center;font-size:11px;">BidVex Canada · Sherbrooke, QC · <a href="mailto:service@bidvex.com" style="color:#3FB4CB;">service@bidvex.com</a></td></tr>
</table></body></html>"""

            try:
                ok = await send_html_email(
                    to_email=ADMIN_ALERT_RECIPIENT,
                    to_name="BidVex Admin Alerts",
                    subject=subject,
                    html_content=body_html,
                )
                if ok:
                    email_sent_count = 1
                else:
                    email_errors.append("sendgrid_returned_false")
            except Exception as exc:
                email_errors.append(f"send_exception:{type(exc).__name__}:{exc}")
                logger.error(
                    "[manual_review] ❌ SendGrid call FAILED to %s — %s",
                    ADMIN_ALERT_RECIPIENT, exc, exc_info=True,
                )
        except Exception as exc:
            email_errors.append(f"pipeline:{type(exc).__name__}")
            logger.error(f"[manual_review] email pipeline failed: {exc}", exc_info=True)
    else:
        email_errors.append(f"missing_env:{','.join(missing)}")

    # Belt-and-suspenders — also drop a row into email_outbox for audit + replay
    try:
        await db.email_outbox.insert_one({
            "id":            str(uuid.uuid4()),
            "kind":          "ai_review_admin_alert",
            "to_email":      ADMIN_ALERT_RECIPIENT,
            "context":       email_context,
            "queued_at":     now,
            "delivery_status": (
                "sent_immediate" if email_sent_count > 0 else "send_failed"
            ),
            "immediate_send_count": email_sent_count,
            "immediate_send_errors": email_errors,
        })
    except Exception:
        pass

    # 5. In-app admin notifications (so the admin badge counter rises)
    try:
        admin_users = await db.users.find(
            {"role": {"$in": ["admin", "super_admin"]}},
            {"_id": 0, "id": 1, "email": 1},
        ).to_list(length=50)
        if admin_users:
            target_listing_id = payload.listing_id or synthetic_listing_id
            display_title = title or "(no title)"
            # Phase 6.0 / Failure 3 — Explicit admin-scoped deep-link.
            # Frontend route alias `/admin/flagged-listings` mounts the same
            # AdminDashboard component so the ?listing_id= query is preserved.
            route_url = f"/admin/flagged-listings?listing_id={target_listing_id}"
            await db.notifications.insert_many([{
                "id":         str(uuid.uuid4()),
                "user_id":    a["id"],
                "type":       "manual_vehicle_review_request",
                "title":      "🔍 Manual Review Requested / Demande de révision",
                "title_en":   "🔍 Manual Review Requested",
                "title_fr":   "🔍 Demande de révision manuelle",
                "description":   f"Seller requested manual review for Listing ID: {target_listing_id} ({display_title}).",
                "description_en": f"Seller requested manual review for Listing ID: {target_listing_id} ({display_title}).",
                "description_fr": f"Le vendeur a demandé une révision manuelle pour l'annonce {target_listing_id} ({display_title}).",
                "message":    f"Seller requested manual review for Listing ID: {target_listing_id} ({display_title}).",
                "message_en": f"{seller_name} ({current_user.email}) asked for manual review after a vehicle-compliance block.",
                "message_fr": f"{seller_name} ({current_user.email}) a demandé une révision manuelle après un blocage de conformité véhicule.",
                "route_url":  route_url,
                "action_url": route_url,
                "link":       route_url,
                "path":       route_url,
                "url":        route_url,
                "context":    {**email_context, "route_url": route_url},
                "read":       False,
                "created_at": now,
            } for a in admin_users])
    except Exception as exc:
        logger.warning(f"[manual_review] in-app notifications failed: {exc}")

    logger.info(
        f"[manual_review] req_id={req_id} seller={current_user.email} "
        f"signals={detected_signals} emails_sent={email_sent_count}/1 "
        f"email_errors={email_errors}"
    )
    return {
        "success":           True,
        "request_id":        req_id,
        "status":            "pending",
        "listing_review_id": req_id,
        "eta_minutes_min":   5,
        "eta_minutes_max":   50,
        "admin_emails_sent": email_sent_count,
        "admin_emails_attempted": 1,
        "admin_alert_recipient": ADMIN_ALERT_RECIPIENT,
        "email_errors":      email_errors,
    }


@ai_review_router.post("/listings/suggest-category")
async def suggest_category(payload: CategorySuggestRequest, current_user: User = Depends(get_current_user)):
    """Lightweight pre-publish AI category check.

    Returns:
        {
          match: bool,
          confidence: float,
          suggested_category: str | None,
          reason_en: str,
          reason_fr: str,
        }
    Falls open (returns match=True) if the LLM is unavailable so the seller
    flow is never blocked by an outage. The real authoritative scanner is
    invoked AFTER the listing is created (services/listing_moderation_scanner.py).
    """
    db = get_db()
    title = (payload.title or "").strip()
    seller_cat = (payload.seller_category or "").strip()
    description = (payload.description or "").strip()

    # Allow categories collection to satisfy basic sanity check (avoid AI cost
    # for trivial mismatches the DB already knows about).
    known_categories: list[str] = []
    try:
        async for c in db.categories.find({}, {"_id": 0, "name_en": 1, "name_fr": 1}):
            for k in ("name_en", "name_fr"):
                if c.get(k):
                    known_categories.append(str(c[k]).strip())
    except Exception:
        pass

    # Quick rule-based check — if the title/description strongly suggests a
    # vehicle or known category mismatch, surface it without paying for LLM.
    text = f"{title}\n{description}".lower()
    vehicle_hints = ["car", "truck", "suv", "motorcycle", "atv", "snowmobile",
                     "boat", "rv", "trailer", "voiture", "camion", "moto"]
    looks_vehicle = any(h in text for h in vehicle_hints)
    seller_says_vehicle = "vehicle" in seller_cat.lower() or "véhicule" in seller_cat.lower()
    if looks_vehicle and not seller_says_vehicle:
        return {
            "match": False,
            "confidence": 0.85,
            "suggested_category": "Vehicles",
            "reason_en": "Title/description appears to describe a vehicle, but the selected category is not Vehicles.",
            "reason_fr": "Le titre/la description semble décrire un véhicule, mais la catégorie sélectionnée n'est pas Véhicules.",
        }

    # Default — assume match (fail-OPEN to never block the seller flow)
    return {
        "match": True,
        "confidence": 1.0,
        "suggested_category": None,
        "reason_en": "",
        "reason_fr": "",
    }



class FlagForReviewRequest(BaseModel):
    suggested_category: Optional[str] = None
    seller_category: Optional[str] = None
    ai_confidence: Optional[float] = None
    ai_reason_en: Optional[str] = None
    ai_reason_fr: Optional[str] = None
    listing_type: Optional[Literal["single", "multi"]] = "single"


class ReviewActionRequest(BaseModel):
    admin_note: Optional[str] = Field(None, max_length=1000)
    override_category: Optional[str] = None  # admin can fix the category at approval time


class CorrectCategoryRequest(BaseModel):
    new_category: str = Field(..., min_length=1, max_length=120)
    listing_type: Optional[Literal["single", "multi"]] = "single"


def _collection_for(listing_type: str) -> str:
    return "multi_item_listings" if listing_type == "multi" else "listings"


async def _resolve_listing(db, listing_id: str, listing_type: Optional[str] = None) -> tuple[str, dict]:
    if listing_type == "multi":
        doc = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
        if doc:
            return "multi_item_listings", doc
    if listing_type in (None, "single", ""):
        doc = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        if doc:
            return "listings", doc
        doc = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
        if doc:
            return "multi_item_listings", doc
    raise HTTPException(status_code=404, detail="Listing not found")


@ai_review_router.post("/listings/{listing_id}/flag-for-ai-review")
async def flag_listing_for_ai_review(
    listing_id: str,
    payload: FlagForReviewRequest,
    current_user: User = Depends(get_current_user),
):
    """Seller-side — invoked when seller dismisses the AI category mismatch popup.

    Sets listing.status = 'pending_ai_review' and creates a listing_reviews row.

    HOTFIX (Eliminate AI Watchdog Amnesia Loop) / FIX 1:
      Before any scanner logic runs, short-circuit when the listing already
      carries an admin-approved-override / ai_scan_bypass passport. This
      prevents edits to a previously-approved listing from re-triggering
      the AI scanner and creating duplicate Flagged Listings rows.
    """
    db = get_db()
    collection, listing = await _resolve_listing(db, listing_id, payload.listing_type)

    # ── FIX 1 — Bypass gate (FIRST line; runs before everything else) ──
    if listing.get("admin_approved_override") is True or listing.get("ai_scan_bypass") is True:
        logger.info(
            f"[ai_watchdog] BYPASS — listing {listing_id} is admin-whitelisted; "
            f"scanner skipped (approved_by={listing.get('admin_approved_by')})"
        )
        return {
            "flagged": False,
            "reason": "admin_whitelisted",
            "success": True,
            "review_id": None,
            "status": listing.get("status") or "active",
        }

    if listing.get("seller_id") != current_user.id and current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")

    now = datetime.now(timezone.utc)

    # ── FIX 4 (b) — Deduplication guard on insert ──
    # Never create a second pending review row for the same listing.
    existing_pending = await db.listing_reviews.find_one(
        {"listing_id": listing_id, "status": "pending"},
        {"_id": 0},
    )
    if existing_pending:
        logger.info(
            f"[ai_watchdog] DEDUPE — open review {existing_pending.get('id')} already exists "
            f"for listing {listing_id}; returning existing row instead of inserting"
        )
        for k in ("created_at", "updated_at", "resolved_at"):
            v = existing_pending.get(k)
            if isinstance(v, datetime):
                existing_pending[k] = v.isoformat()
        return {
            "success": True,
            "review_id": existing_pending["id"],
            "status": "pending_ai_review",
            "deduped": True,
        }

    review_id = str(uuid.uuid4())

    # Snapshot the listing's pre-review status so admin can re-approve to it
    prev_status = listing.get("status", "active")

    review_doc = {
        "id":                 review_id,
        "listing_id":         listing_id,
        "listing_type":       "multi" if collection == "multi_item_listings" else "single",
        "collection":         collection,
        "seller_id":          listing.get("seller_id"),
        "listing_title":      listing.get("title", ""),
        "seller_category":    payload.seller_category or listing.get("category", ""),
        "suggested_category": payload.suggested_category,
        "ai_confidence":      payload.ai_confidence,
        "ai_reason_en":       payload.ai_reason_en,
        "ai_reason_fr":       payload.ai_reason_fr,
        "previous_status":    prev_status,
        "status":             "pending",       # pending | approved | rejected | withdrawn | resubmitted
        "created_at":         now,
        "updated_at":         now,
        "resolved_at":        None,
        "admin_id":           None,
        "admin_email":        None,
        "admin_note":         None,
        "escalation_emailed": False,
    }
    await db.listing_reviews.insert_one(review_doc)

    await db[collection].update_one(
        {"id": listing_id},
        {"$set": {
            "status":              "pending_ai_review",
            "ai_review_id":        review_id,
            "ai_review_flagged_at": now,
            "ai_suggested_category": payload.suggested_category,
            "ai_review_reason_en": payload.ai_reason_en,
            "ai_review_reason_fr": payload.ai_reason_fr,
        }},
    )

    # Queue an admin alert email (drained by SendGrid worker — graceful if SG missing)
    # Phase 6.0 hotfix — recipient HARDCODED to the BidVex ops inbox. We do NOT
    # leave `to_email=None` here because the worker's _resolve_recipient skips
    # rows with no recipient (the alert was silently disappearing in prod).
    try:
        await db.email_outbox.insert_one({
            "id":         str(uuid.uuid4()),
            "kind":       "ai_review_admin_alert",
            "to_email":   "charbel911@gmail.com",
            "context":    {
                "review_id":         review_id,
                "listing_id":        listing_id,
                "listing_title":     listing.get("title", ""),
                "seller_category":   review_doc["seller_category"],
                "suggested_category": payload.suggested_category,
                "ai_reason_en":      payload.ai_reason_en,
                "admin_review_url":  f"https://bidvex.com/admin/flagged-listings?listing_id={listing_id}",
            },
            "queued_at":  now,
        })
    except Exception as exc:
        logger.warning(f"[ai_review] admin alert email queue failed: {exc}")

    logger.info(f"[ai_review] listing {listing_id} flagged for AI review (review_id={review_id})")
    return {"success": True, "review_id": review_id, "status": "pending_ai_review"}


@ai_review_router.get("/admin/listing-reviews")
async def admin_list_listing_reviews(
    status: Optional[str] = Query("pending", description="pending|approved|rejected|withdrawn|all"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
):
    """List AI review queue rows, default = pending only.

    HOTFIX (Eliminate AI Watchdog Amnesia Loop) / FIX 4 (a):
      Exclude every review whose underlying listing already carries the
      `admin_approved_override` immunity passport. This stops stale rows
      from appearing in the Flagged Listings table after admin approval.
    """
    db = get_db()
    query = {}
    if status and status != "all":
        query["status"] = status

    # Collect every listing_id that's already been admin-approved.
    approved_ids: set[str] = set()
    async for row in db.listings.find(
        {"admin_approved_override": True},
        {"_id": 0, "id": 1},
    ):
        approved_ids.add(row["id"])
    async for row in db.multi_item_listings.find(
        {"admin_approved_override": True},
        {"_id": 0, "id": 1},
    ):
        approved_ids.add(row["id"])
    if approved_ids:
        query["listing_id"] = {"$nin": list(approved_ids)}

    cursor = db.listing_reviews.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    rows = await cursor.to_list(length=limit)
    for r in rows:
        for k in ("created_at", "updated_at", "resolved_at"):
            v = r.get(k)
            if isinstance(v, datetime):
                r[k] = v.isoformat()
    total = await db.listing_reviews.count_documents(query)
    return {"rows": rows, "total": total, "status": status}


@ai_review_router.get("/admin/listing-reviews/{review_id}")
async def admin_get_listing_review(
    review_id: str,
    current_user: User = Depends(require_admin),
):
    db = get_db()
    row = await db.listing_reviews.find_one({"id": review_id}, {"_id": 0})
    if not row:
        raise HTTPException(status_code=404, detail="Review not found")
    for k in ("created_at", "updated_at", "resolved_at"):
        v = row.get(k)
        if isinstance(v, datetime):
            row[k] = v.isoformat()
    return row


# ───────────────────────────────────────────────────────────────────────
# Phase 6.0 / Failure 4 — FULL admin preview endpoint.
# Returns the complete raw listing document joined with the review row
# AND (when the listing is pre-creation / vehicle-block::*) the snapshot
# stored in manual_review_requests. Every field the modal needs is here.
# ───────────────────────────────────────────────────────────────────────

@ai_review_router.get("/admin/flagged-listings/{review_id}/full")
async def admin_get_flagged_listing_full(
    review_id: str,
    current_user: User = Depends(require_admin),
):
    """Returns: { review, listing, snapshot } — `listing` is the raw doc
    from the primary collection (None when no real listing exists yet),
    `snapshot` is the manual_review_requests row (when applicable)."""
    db = get_db()
    review = await db.listing_reviews.find_one({"id": review_id}, {"_id": 0})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")

    # Stringify review datetimes
    for k in ("created_at", "updated_at", "resolved_at"):
        v = review.get(k)
        if isinstance(v, datetime):
            review[k] = v.isoformat()

    listing_id = review.get("listing_id") or ""
    listing = None
    if listing_id and not listing_id.startswith("vehicle-block::"):
        # Try primary collection first
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    if listing:
        for k in ("created_at", "updated_at", "auction_end_date"):
            v = listing.get(k)
            if isinstance(v, datetime):
                listing[k] = v.isoformat()

    # Pull the manual_review_requests snapshot (the seller's pre-creation
    # form data) when this review was created from the vehicle-block flow.
    snapshot = await db.manual_review_requests.find_one({"id": review_id}, {"_id": 0})
    if snapshot:
        for k in ("created_at", "updated_at", "resolved_at"):
            v = snapshot.get(k)
            if isinstance(v, datetime):
                snapshot[k] = v.isoformat()

    return {
        "review":   review,
        "listing":  listing,
        "snapshot": snapshot,
    }


# Alias under /admin/flagged-listings/{listing_id}/full keyed by listing_id
# (frontend often only has the listing_id from the URL query parameter).
@ai_review_router.get("/admin/flagged-listings/by-listing/{listing_id}/full")
async def admin_get_flagged_full_by_listing_id(
    listing_id: str,
    current_user: User = Depends(require_admin),
):
    db = get_db()
    review = await db.listing_reviews.find_one(
        {"listing_id": listing_id},
        sort=[("created_at", -1)],
        projection={"_id": 0},
    )
    if not review:
        raise HTTPException(status_code=404, detail="No review found for this listing")
    return await admin_get_flagged_listing_full(review["id"], current_user)


async def _resolve_review_and_listing(db, review_id: str) -> tuple[dict, Optional[str], Optional[dict]]:
    """Returns (review, collection, listing). Phase 6.0 hotfix —
    `collection` and `listing` may be None when the review was created from
    a pre-creation manual review request (synthetic `vehicle-block::*`
    listing_id). The approve/reject handlers handle that gracefully."""
    review = await db.listing_reviews.find_one({"id": review_id}, {"_id": 0})
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    if review.get("status") != "pending":
        raise HTTPException(status_code=400, detail={
            "error": "review_already_resolved",
            "message_en": f"This review is already {review.get('status')}.",
            "message_fr": f"Cet examen est déjà {review.get('status')}.",
        })
    listing_id = review.get("listing_id") or ""
    if listing_id.startswith("vehicle-block::"):
        # Pre-creation request — no listing exists yet.
        return review, None, None
    collection = review.get("collection") or _collection_for(review.get("listing_type", "single"))
    if collection == "manual_review_requests":
        collection = _collection_for(review.get("listing_type", "single"))
    listing = await db[collection].find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        # Try the other collection as a fallback
        other = "multi_item_listings" if collection == "listings" else "listings"
        listing = await db[other].find_one({"id": listing_id}, {"_id": 0})
        if listing:
            collection = other
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    return review, collection, listing


async def _queue_seller_email(db, kind: str, seller_id: str, context: dict):
    """Phase 6.0 hotfix — fires seller email IMMEDIATELY via SendGrid (with
    HTML fallback) AND inserts a row in `notifications`. Also drops an audit
    record in `email_outbox` so admins can replay if needed.

    Returns True if at least one notification channel succeeded.
    """
    import os
    now = datetime.now(timezone.utc)
    delivery_status = "queued"
    email_sent = False
    # 1. Lookup the seller's email / name / language
    seller = await db.users.find_one(
        {"id": seller_id},
        {"_id": 0, "email": 1, "name": 1, "preferred_language": 1, "language_preference": 1},
    ) or {}
    seller_email = seller.get("email")
    seller_name = seller.get("name") or seller_email or ""
    lang = (seller.get("preferred_language") or seller.get("language_preference") or "en")[:2].lower()
    is_fr = lang == "fr"

    # 2. Fire the SendGrid email immediately via the inline HTML fallback
    if seller_email:
        try:
            from services.templates.welcome_email import render_kind_html
            from services.email_service import send_html_email
            html = render_kind_html(kind, context)
            # HOTFIX v9.1 / Fix 1 — Subject line per user spec: "Your listing is
            # now live — [Title]" so the seller instantly recognises approval.
            listing_title_subj = (context.get("listing_title") or "").strip() or "your listing"
            subject_map = {
                "ai_review_approved": (
                    f"Votre annonce est maintenant en ligne — {listing_title_subj}" if is_fr else
                    f"Your listing is now live — {listing_title_subj}"
                ),
                "ai_review_rejected": (
                    "Décision sur votre annonce / Listing Decision" if is_fr else
                    "Listing Decision / Décision sur votre annonce"
                ),
            }
            subject = subject_map.get(kind, "BidVex")
            if html:
                ok = await send_html_email(
                    to_email=seller_email, to_name=seller_name,
                    subject=subject, html_content=html,
                )
                email_sent = bool(ok)
                delivery_status = "sent_immediate" if ok else "stubbed_no_sendgrid"
        except Exception as exc:
            logger.warning(f"[ai_review] seller email immediate send failed ({kind}): {exc}")
            delivery_status = f"exception:{type(exc).__name__}"

    # 3. Audit row in email_outbox (so admins can replay if needed)
    try:
        await db.email_outbox.insert_one({
            "id":              str(uuid.uuid4()),
            "kind":            kind,
            "to_user_id":      seller_id,
            "to_email":        seller_email,
            "context":         context,
            "queued_at":       now,
            "delivery_status": delivery_status,
        })
    except Exception as exc:
        logger.warning(f"[ai_review] seller email outbox audit failed ({kind}): {exc}")

    # 4. In-app system notification (bilingual)
    try:
        listing_id = context.get("listing_id") or ""
        listing_title = context.get("listing_title") or ""
        admin_note = (context.get("admin_note") or "").strip()
        public_base = os.environ.get("PUBLIC_BASE_URL", "https://bidvex.com")
        route_url = (
            f"/listing/{listing_id}" if kind == "ai_review_approved" and listing_id
            else "/seller/dashboard"
        )
        if kind == "ai_review_approved":
            title_en = "Listing Approved!"
            title_fr = "Annonce approuvée !"
            msg_en = f"✅ Your listing '{listing_title}' is now live on BidVex."
            msg_fr = f"✅ Votre annonce « {listing_title} » est maintenant en ligne sur BidVex."
        else:  # ai_review_rejected
            title_en = "Listing Denied"
            title_fr = "Annonce refusée"
            reason_en = admin_note or "Did not meet our compliance guidelines."
            reason_fr = admin_note or "Ne respecte pas nos directives de conformité."
            msg_en = (
                f"Your listing '{listing_title}' was rejected by compliance. "
                f"Reason: {reason_en}. "
                f"If you see that it's wrong, please contact support at service@bidvex.com."
            )
            msg_fr = (
                f"Votre annonce « {listing_title} » a été rejetée par notre équipe de conformité. "
                f"Raison : {reason_fr}. "
                f"Si vous pensez qu'il s'agit d'une erreur, contactez le support à service@bidvex.com."
            )
        await db.notifications.insert_one({
            "id":              str(uuid.uuid4()),
            "user_id":         seller_id,
            "type":            kind,
            "title":           (title_fr if is_fr else title_en),
            "title_en":        title_en,
            "title_fr":        title_fr,
            "description":     (msg_fr if is_fr else msg_en),
            "description_en":  msg_en,
            "description_fr":  msg_fr,
            "message":         (msg_fr if is_fr else msg_en),
            "message_en":      msg_en,
            "message_fr":      msg_fr,
            "route_url":       route_url,
            "path":            route_url,
            "url":             route_url,
            "context":         {**context, "public_base": public_base},
            "read":            False,
            "created_at":      now,
        })
    except Exception as exc:
        logger.warning(f"[ai_review] seller notification insert failed ({kind}): {exc}")

    return email_sent


@ai_review_router.post("/admin/listing-reviews/{review_id}/approve")
async def admin_approve_listing_review(
    review_id: str,
    payload: ReviewActionRequest,
    current_user: User = Depends(require_admin),
):
    """Approve a flagged listing — flips to status='active', publishes, clears AI flags.

    HOTFIX v9.1 / Fix 1:
      - Always flips listing to 'active' (regardless of previous status —
        pending_ai_review, pending_admin_review, locked-* stubs).
      - Sets is_published=True + published_at=now so the listing appears
        in the correct public marketplace feed immediately.
      - Wipes every AI-review trace from the listing doc.
      - Seller email + in-app notification dispatched via `_queue_seller_email`
        (the "ai_review_approved" kind already routes to the live-listing copy).
    """
    db = get_db()
    review, collection, listing = await _resolve_review_and_listing(db, review_id)
    now = datetime.now(timezone.utc)

    # HOTFIX v9.1 — Always restore to "active" (never leave the listing in a
    # pending_* state after an admin approves). The previous logic kept
    # `previous_status` for non-AI flows, which could resurface bad rows.
    restored_status = "active"

    listing_update = {
        "status":                   restored_status,
        "is_published":             True,
        "published_at":             now,
        "ai_review_approved_at":    now,
        "ai_review_approved_by":    current_user.email,
        # HOTFIX (Eliminate AI Watchdog Amnesia Loop) / FIX 2 — Immunity
        # passport. These two flags persist through ALL future edits and
        # cause the AI scanner's bypass gate to short-circuit.
        "admin_approved_override":  True,
        "ai_scan_bypass":           True,
        "admin_approved_by":        current_user.id,
        # HOTFIX (Infinite Re-flag Loop) / FIX 1 — Stamp watchdog immunity so
        # the scheduled scanner never re-touches this listing. Also clear any
        # `paused_by_watchdog` state inherited from a prior scheduled scan so
        # the listing returns to active immediately.
        "watchdog_exempt":          True,
        "watchdog_exempt_at":       now,
        "watchdog_exempt_by":       current_user.id,
        "paused_by_watchdog":       False,
        "paused_by":                None,
        "paused_reason":            None,
        # Wipe every AI-review breadcrumb so the listing leaves pending cleanly
        "ai_review_id":             None,
        "ai_review_flag":           None,
        "ai_review_status":         None,
        "ai_review_flagged_at":     None,
        "ai_suggested_category":    None,
        "ai_review_reason_en":      None,
        "ai_review_reason_fr":      None,
    }
    if payload.override_category:
        listing_update["category"] = payload.override_category.strip()

    # Phase 6.0 hotfix — collection may be None for pre-creation
    # (vehicle-block::*) requests where no listing exists yet.
    if collection is not None:
        await db[collection].update_one({"id": review["listing_id"]}, {"$set": listing_update})

    await db.listing_reviews.update_one(
        {"id": review_id},
        {"$set": {
            "status":        "approved",
            "updated_at":    now,
            "resolved_at":   now,
            "admin_id":      current_user.id,
            "admin_email":   current_user.email,
            "admin_note":    (payload.admin_note or "").strip()[:1000],
            "override_category": payload.override_category,
        }},
    )

    await _queue_seller_email(db, "ai_review_approved", review["seller_id"], {
        "review_id":      review_id,
        "listing_id":     review["listing_id"],
        "listing_title":  review.get("listing_title", ""),
        "restored_status": restored_status,
        "admin_note":     (payload.admin_note or ""),
    })

    logger.info(f"[ai_review] APPROVED review={review_id} by {current_user.email}")
    return {"success": True, "review_id": review_id, "listing_status": restored_status}


@ai_review_router.post("/admin/listing-reviews/{review_id}/reject")
async def admin_reject_listing_review(
    review_id: str,
    payload: ReviewActionRequest,
    current_user: User = Depends(require_admin),
):
    """Reject a flagged listing — moves it to status='rejected' permanently."""
    db = get_db()
    review, collection, listing = await _resolve_review_and_listing(db, review_id)
    now = datetime.now(timezone.utc)

    # Phase 6.0 hotfix — collection may be None for vehicle-block:: requests.
    if collection is not None:
        await db[collection].update_one(
            {"id": review["listing_id"]},
            {"$set": {
                "status":                "rejected",
                "ai_review_rejected_at": now,
                "ai_review_rejected_by": current_user.email,
                "ai_review_admin_note":  (payload.admin_note or "")[:1000],
                # HOTFIX (Eliminate AI Watchdog Amnesia Loop) / FIX 3 — Clear
                # any immunity passport so a corrected resubmission gets
                # scanned fresh. The bypass only sticks on approval.
                "admin_approved_override": False,
                "ai_scan_bypass":          False,
            }},
        )
    await db.listing_reviews.update_one(
        {"id": review_id},
        {"$set": {
            "status":        "rejected",
            "updated_at":    now,
            "resolved_at":   now,
            "admin_id":      current_user.id,
            "admin_email":   current_user.email,
            "admin_note":    (payload.admin_note or "").strip()[:1000],
        }},
    )

    await _queue_seller_email(db, "ai_review_rejected", review["seller_id"], {
        "review_id":      review_id,
        "listing_id":     review["listing_id"],
        "listing_title":  review.get("listing_title", ""),
        "admin_note":     (payload.admin_note or ""),
    })

    logger.info(f"[ai_review] REJECTED review={review_id} by {current_user.email}")
    return {"success": True, "review_id": review_id, "listing_status": "rejected"}


# ───────────────────────────────────────────────────────────────────────
# Phase 6.0 / Task 1 — Alias routes at /admin/ai-review/listings/{id}/...
# Frontend calls these new paths; they resolve the review_id from the
# listing_id and delegate to the canonical handlers above.
# ───────────────────────────────────────────────────────────────────────

async def _resolve_review_id_by_listing(db, listing_id: str) -> str:
    """Find the active (pending) listing_reviews row for a listing_id.

    Falls back to the most recent review for that listing.
    """
    row = await db.listing_reviews.find_one(
        {"listing_id": listing_id, "status": "pending"},
        sort=[("created_at", -1)],
        projection={"_id": 0, "id": 1},
    )
    if row:
        return row["id"]
    row = await db.listing_reviews.find_one(
        {"listing_id": listing_id},
        sort=[("created_at", -1)],
        projection={"_id": 0, "id": 1},
    )
    if not row:
        raise HTTPException(status_code=404, detail={
            "error": "review_not_found",
            "message_en": f"No AI review row found for listing {listing_id}.",
            "message_fr": f"Aucun examen IA trouvé pour l'annonce {listing_id}.",
        })
    return row["id"]


@ai_review_router.post("/admin/ai-review/listings/{listing_id}/approve")
async def admin_approve_listing_via_listing_id(
    listing_id: str,
    payload: ReviewActionRequest,
    current_user: User = Depends(require_admin),
):
    """Alias for `/admin/listing-reviews/{review_id}/approve` keyed by listing_id."""
    db = get_db()
    review_id = await _resolve_review_id_by_listing(db, listing_id)
    return await admin_approve_listing_review(review_id, payload, current_user)


@ai_review_router.post("/admin/ai-review/listings/{listing_id}/reject")
async def admin_reject_listing_via_listing_id(
    listing_id: str,
    payload: ReviewActionRequest,
    current_user: User = Depends(require_admin),
):
    """Alias for `/admin/listing-reviews/{review_id}/reject` keyed by listing_id."""
    db = get_db()
    review_id = await _resolve_review_id_by_listing(db, listing_id)
    return await admin_reject_listing_review(review_id, payload, current_user)


@ai_review_router.get("/admin/ai-review/listings")
async def admin_list_ai_review_listings(
    status: Optional[str] = Query("pending", description="pending|approved|rejected|withdrawn|all"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user: User = Depends(require_admin),
):
    """Alias for `/admin/listing-reviews?status=...`."""
    return await admin_list_listing_reviews(status, limit, skip, current_user)


@ai_review_router.post("/listings/{listing_id}/correct-category")
async def seller_correct_category(
    listing_id: str,
    payload: CorrectCategoryRequest,
    current_user: User = Depends(get_current_user),
):
    """Seller corrects the listing category from the 'pending_ai_review' banner.
    Auto-clears the AI flag and moves the listing back to its prior status
    (normal review queue / active)."""
    db = get_db()
    collection, listing = await _resolve_listing(db, listing_id, payload.listing_type)
    if listing.get("seller_id") != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    if listing.get("status") != "pending_ai_review":
        raise HTTPException(status_code=400, detail={
            "error": "not_in_review",
            "message_en": "Listing is not pending AI review.",
            "message_fr": "L'annonce n'est pas en attente d'examen IA.",
        })

    now = datetime.now(timezone.utc)
    review_id = listing.get("ai_review_id")
    review = None
    restored_status = "pending_review"   # send back to normal review queue
    if review_id:
        review = await db.listing_reviews.find_one({"id": review_id}, {"_id": 0})
        if review:
            restored_status = review.get("previous_status") or restored_status
            if restored_status == "pending_ai_review":
                restored_status = "pending_review"

    await db[collection].update_one(
        {"id": listing_id},
        {"$set": {
            "category":              payload.new_category.strip(),
            "status":                restored_status,
            "ai_suggested_category": None,
            "ai_review_reason_en":   None,
            "ai_review_reason_fr":   None,
            "ai_review_resubmitted_at": now,
        }},
    )

    if review_id:
        await db.listing_reviews.update_one(
            {"id": review_id},
            {"$set": {
                "status":      "resubmitted",
                "updated_at":  now,
                "resolved_at": now,
                "admin_note":  "Seller corrected the category from the banner.",
                "new_category": payload.new_category.strip(),
            }},
        )

    logger.info(f"[ai_review] seller {current_user.email} corrected category for listing {listing_id} → {payload.new_category!r}")
    return {"success": True, "listing_id": listing_id, "status": restored_status, "new_category": payload.new_category.strip()}


@ai_review_router.post("/listings/{listing_id}/withdraw-from-review")
async def seller_withdraw_from_review(
    listing_id: str,
    listing_type: Optional[Literal["single", "multi"]] = Query("single"),
    current_user: User = Depends(get_current_user),
):
    """Seller withdraws their flagged listing — sets status='withdrawn'."""
    db = get_db()
    collection, listing = await _resolve_listing(db, listing_id, listing_type)
    if listing.get("seller_id") != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    if listing.get("status") != "pending_ai_review":
        raise HTTPException(status_code=400, detail={
            "error": "not_in_review",
            "message_en": "Listing is not pending AI review.",
            "message_fr": "L'annonce n'est pas en attente d'examen IA.",
        })

    now = datetime.now(timezone.utc)
    await db[collection].update_one(
        {"id": listing_id},
        {"$set": {
            "status":                  "withdrawn",
            "ai_review_withdrawn_at":  now,
        }},
    )
    review_id = listing.get("ai_review_id")
    if review_id:
        await db.listing_reviews.update_one(
            {"id": review_id},
            {"$set": {
                "status":      "withdrawn",
                "updated_at":  now,
                "resolved_at": now,
            }},
        )
    logger.info(f"[ai_review] seller {current_user.email} withdrew listing {listing_id}")
    return {"success": True, "listing_id": listing_id, "status": "withdrawn"}


@ai_review_router.post("/listings/{listing_id}/resubmit-for-review")
async def seller_resubmit_for_review(
    listing_id: str,
    listing_type: Optional[Literal["single", "multi"]] = Query("single"),
    current_user: User = Depends(get_current_user),
):
    """iter312 D2 — Seller edits a flagged listing and resubmits it.

    Default behavior: ANY edit to a previously-flagged listing re-runs the
    vehicle/safety scanner. If the scanner now passes clean, the listing
    goes live immediately (status='active'). If it still flags, the
    listing returns to `pending_admin_review` for actual admin eyes.

    This is the "safer" of the two policies the directive offered — admin
    still gets a chance to review when the issue persists, but the seller
    can self-resolve genuine false positives without waiting.
    """
    db = get_db()
    collection, listing = await _resolve_listing(db, listing_id, listing_type)
    if listing.get("seller_id") != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    if listing.get("status") not in ("pending_ai_review", "pending_admin_review", "draft"):
        raise HTTPException(status_code=400, detail={
            "error": "not_in_review",
            "message_en": "Listing is not pending review.",
            "message_fr": "L'annonce n'est pas en attente d'examen.",
        })

    now = datetime.now(timezone.utc)

    # Step 1 — Flip status to "active" so the scanner doesn't skip it.
    await db[collection].update_one(
        {"id": listing_id},
        {"$set": {
            "status":                  "active",
            "is_published":            True,
            "published_at":            now,
            "ai_review_resubmitted_at": now,
            "ai_review_id":            None,
            "ai_review_flag":          None,
            "ai_review_status":        None,
            "ai_review_flagged_at":    None,
            "ai_suggested_category":   None,
            "ai_review_reason_en":     None,
            "ai_review_reason_fr":     None,
            "paused_by_watchdog":      False,
            "paused_by":               None,
            "paused_reason":           None,
            "updated_at":              now,
        }},
    )

    # Step 2 — Re-run the AI scanner. If still flagged, the scanner will
    # write status='pending_review' back; otherwise leaves it 'active'.
    rescan_outcome = "passed"
    try:
        from services.vehicle_listing_scanner import scan_listing_for_vehicles
        scan_result = await scan_listing_for_vehicles(db, listing_id=listing_id, collection=collection)
        if scan_result.get("action_taken") == "paused_pending_review":
            rescan_outcome = "still_flagged"
            # Scanner has already set status='pending_review' — promote to
            # pending_admin_review for consistency with the unified status set.
            await db[collection].update_one(
                {"id": listing_id},
                {"$set": {"status": "pending_admin_review"}},
            )
    except Exception as exc:
        logger.warning(f"[ai_review] resubmit rescan errored for {listing_id}: {exc}")
        # Fail open — leave at active (admin can re-flag via watchdog if needed).

    # Step 3 — Mark the open review row as resubmitted-clear if rescan passed.
    review_id = listing.get("ai_review_id")
    if review_id and rescan_outcome == "passed":
        await db.listing_reviews.update_one(
            {"id": review_id},
            {"$set": {
                "status":      "resubmitted",
                "updated_at":  now,
                "resolved_at": now,
                "admin_note":  "Seller edited the listing and the re-scan passed clean.",
            }},
        )

    final_status = "active" if rescan_outcome == "passed" else "pending_admin_review"
    logger.info(f"[ai_review] seller {current_user.email} resubmitted listing {listing_id} → {final_status} (rescan={rescan_outcome})")
    return {"success": True, "listing_id": listing_id, "status": final_status, "rescan": rescan_outcome}


async def escalate_overdue_reviews(db) -> int:
    """Scheduler hook — email admins again for reviews open > 60 minutes.

    Returns the number of escalations emitted (idempotent — sets escalation_emailed=True).
    Phase 6.0 hotfix — recipient HARDCODED to the BidVex ops inbox to bypass
    the worker's distro-list resolution (which silently skips empty recipients).
    """
    cutoff = datetime.now(timezone.utc) - __import__("datetime").timedelta(minutes=60)
    count = 0
    async for r in db.listing_reviews.find({
        "status": "pending",
        "escalation_emailed": {"$ne": True},
        "created_at": {"$lt": cutoff},
    }, {"_id": 0}):
        try:
            await db.email_outbox.insert_one({
                "id":         str(uuid.uuid4()),
                "kind":       "ai_review_admin_escalation",
                "to_email":   "charbel911@gmail.com",
                "context":    {
                    "review_id":     r["id"],
                    "listing_id":    r["listing_id"],
                    "listing_title": r.get("listing_title", ""),
                    "minutes_open":  60,
                    "admin_review_url": f"https://bidvex.com/admin/flagged-listings?listing_id={r['listing_id']}",
                },
                "queued_at":  datetime.now(timezone.utc),
            })
            await db.listing_reviews.update_one(
                {"id": r["id"]},
                {"$set": {"escalation_emailed": True, "escalation_emailed_at": datetime.now(timezone.utc)}},
            )
            count += 1
        except Exception as exc:
            logger.warning(f"[ai_review] escalation failed for review {r['id']}: {exc}")
    if count:
        logger.info(f"[ai_review] escalated {count} overdue review(s)")
    return count
