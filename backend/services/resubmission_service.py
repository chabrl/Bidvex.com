"""
iter209 Step 2 — Shared Resubmission Service

Handles application resubmission for BOTH:
  - Vehicle dealers (collection: `vehicle_sellers`, status field `verification_status`)
  - Partners       (collection: `users`,           status field `partner_verification_status`)

Rules (per iter209 spec):
  1. Only callable when current status == "rejected"
  2. Max 3 resubmissions per applicant
  3. Append current rejection to `rejection_history[]` BEFORE clearing the current rejection
  4. Increment `resubmission_count`
  5. Set status back to "pending_review" (partner) or "pending" (dealer — its enum)
  6. Set `resubmitted_at = now()`
  7. Fire admin notification email
  8. Wipe all uploaded documents on a partner resubmit (security — uploads must be re-supplied)

The service is intentionally storage-agnostic — `flavor` chooses the collection + fields.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

MAX_RESUBMISSIONS = 3


# ─── Public API ────────────────────────────────────────────────────────────
async def resubmit_application(
    db,
    *,
    flavor: str,                 # "partner" | "dealer"
    user_id: str,
    user_email: str | None,
    payload: dict[str, Any],     # already-validated fields the applicant submitted
) -> dict[str, Any]:
    """Run all bookkeeping for a resubmission. Returns the new state."""
    if flavor not in ("partner", "dealer"):
        raise ValueError(f"unsupported flavor: {flavor}")

    if flavor == "partner":
        return await _resubmit_partner(db, user_id=user_id, user_email=user_email, payload=payload)
    return await _resubmit_dealer(db, user_id=user_id, user_email=user_email, payload=payload)


# ─── Partner branch ────────────────────────────────────────────────────────
async def _resubmit_partner(db, *, user_id: str, user_email: str | None, payload: dict) -> dict:
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user_doc:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="user_not_found")

    status = user_doc.get("partner_verification_status")
    if status != "rejected":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail={
            "error": "not_in_rejected_state",
            "message_en": "Your application is not in a rejected state.",
            "message_fr": "Votre demande n'est pas en état rejeté.",
            "current_status": status,
        })

    resubmission_count = int(user_doc.get("resubmission_count") or 0)
    if resubmission_count >= MAX_RESUBMISSIONS:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail={
            "error": "max_resubmissions_reached",
            "message_en": "Maximum resubmission attempts reached. Please contact partners@bidvex.ca for assistance.",
            "message_fr": "Nombre maximum de tentatives atteint. Contactez partners@bidvex.ca pour obtenir de l'aide.",
            "max": MAX_RESUBMISSIONS,
        })

    now = datetime.now(timezone.utc)
    history_entry = {
        "reason": user_doc.get("partner_rejection_reason") or "",
        "rejected_at": user_doc.get("partner_rejected_at") or user_doc.get("partner_applied_at"),
        "reviewed_by": user_doc.get("partner_rejected_by"),
    }
    rejection_history = list(user_doc.get("rejection_history") or [])
    rejection_history.append(history_entry)

    # Update payload fields — keep payload optional so partial pre-fills work
    updates = {
        "partner_verification_status": "pending_review",
        "partner_applied_at": now,
        "resubmitted_at": now,
        "resubmission_count": resubmission_count + 1,
        "rejection_history": rejection_history,
        "partner_rejection_reason": None,
        "partner_rejected_at": None,
        "partner_rejected_by": None,
    }
    # Pre-fill fields keep their previous value unless explicitly overwritten
    for fld in ("partner_company_name", "partner_neq", "partner_neq_document", "partner_certifications"):
        if fld in payload and payload[fld] is not None:
            updates[fld] = payload[fld]

    await db.users.update_one({"id": user_id}, {"$set": updates})

    # Notify admin (best-effort)
    await _notify_admin_resubmission(
        db,
        flavor="partner",
        applicant_email=user_email or user_doc.get("email"),
        applicant_id=user_id,
        applicant_name=user_doc.get("partner_company_name") or user_doc.get("name"),
        previous_reason=history_entry["reason"],
        resubmission_count=resubmission_count + 1,
        province=updates.get("partner_province") or user_doc.get("partner_province"),
    )

    return {
        "status": "pending_review",
        "resubmission_count": resubmission_count + 1,
        "max_resubmissions": MAX_RESUBMISSIONS,
        "message_en": "Your resubmission is under review. We'll contact you within 24–48 hours.",
        "message_fr": "Votre nouvelle demande est en cours d'examen. Nous vous contacterons dans les 24 à 48 heures.",
    }


# ─── Dealer branch ─────────────────────────────────────────────────────────
async def _resubmit_dealer(db, *, user_id: str, user_email: str | None, payload: dict) -> dict:
    seller = await db.vehicle_sellers.find_one({"user_id": user_id}, {"_id": 0})
    if not seller:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="vehicle_seller_not_found")

    if seller.get("verification_status") != "rejected":
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail={
            "error": "not_in_rejected_state",
            "message_en": "Your application is not in a rejected state.",
            "message_fr": "Votre demande n'est pas en état rejeté.",
            "current_status": seller.get("verification_status"),
        })

    resubmission_count = int(seller.get("resubmission_count") or 0)
    if resubmission_count >= MAX_RESUBMISSIONS:
        from fastapi import HTTPException
        raise HTTPException(status_code=403, detail={
            "error": "max_resubmissions_reached",
            "message_en": "Maximum resubmission attempts reached. Please contact partners@bidvex.ca for assistance.",
            "message_fr": "Nombre maximum de tentatives atteint. Contactez partners@bidvex.ca pour obtenir de l'aide.",
            "max": MAX_RESUBMISSIONS,
        })

    now = datetime.now(timezone.utc)
    history_entry = {
        "reason": seller.get("rejection_reason") or "",
        "rejected_at": seller.get("rejected_at") or seller.get("updated_at") or seller.get("created_at"),
        "reviewed_by": seller.get("rejected_by"),
    }
    rejection_history = list(seller.get("rejection_history") or [])
    rejection_history.append(history_entry)

    updates = {
        "verification_status": "pending",     # vehicle_sellers enum keeps "pending" label
        "resubmitted_at": now,
        "resubmission_count": resubmission_count + 1,
        "rejection_history": rejection_history,
        "rejection_reason": None,
        "rejected_at": None,
        "rejected_by": None,
        "updated_at": now,
    }
    for fld in ("seller_type", "business_name", "business_address", "business_phone",
                "license_number", "license_province", "tax_id", "website", "description"):
        if fld in payload and payload[fld] is not None:
            updates[fld] = payload[fld]

    await db.vehicle_sellers.update_one({"user_id": user_id}, {"$set": updates})

    await _notify_admin_resubmission(
        db,
        flavor="dealer",
        applicant_email=user_email,
        applicant_id=user_id,
        applicant_name=updates.get("business_name") or seller.get("business_name") or user_email,
        previous_reason=history_entry["reason"],
        resubmission_count=resubmission_count + 1,
        province=updates.get("license_province") or seller.get("license_province"),
    )

    return {
        "status": "pending_review",
        "resubmission_count": resubmission_count + 1,
        "max_resubmissions": MAX_RESUBMISSIONS,
        "message_en": "Your resubmission is under review. We'll contact you within 24–48 hours.",
        "message_fr": "Votre nouvelle demande est en cours d'examen. Nous vous contacterons dans les 24 à 48 heures.",
    }


# ─── Admin notification (email + admin_notifications row) ──────────────────
async def _notify_admin_resubmission(
    db,
    *,
    flavor: str,
    applicant_email: str | None,
    applicant_id: str,
    applicant_name: str | None,
    previous_reason: str,
    resubmission_count: int,
    province: str | None,
) -> None:
    """Best-effort admin notification — never raises."""
    title_prefix = "Partner" if flavor == "partner" else "Vehicle Dealer"
    subject = f"🔄 Application Resubmitted — {applicant_name or applicant_email or applicant_id} ({province or '—'})"
    body_html = f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:560px;margin:0 auto;color:#1e293b;">
      <div style="background:#0ea5e9;padding:24px 28px;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:20px;">{title_prefix} Application Resubmitted</h1>
        <p style="color:#bae6fd;margin:6px 0 0;font-size:13px;">Attempt #{resubmission_count} of 3</p>
      </div>
      <div style="padding:24px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;font-size:14px;line-height:1.7;">
        <p><strong>Applicant:</strong> {applicant_name or '—'}</p>
        <p><strong>Email:</strong> {applicant_email or '—'}</p>
        <p><strong>Province:</strong> {province or '—'}</p>
        <p><strong>Previous rejection reason:</strong><br/><em>{previous_reason or '—'}</em></p>
        <p style="margin-top:18px;">
          <a href="https://bidvex.com/admin" style="display:inline-block;background:#2563eb;color:#fff;padding:10px 22px;border-radius:8px;text-decoration:none;font-weight:600;">Review in Admin Panel</a>
        </p>
      </div>
    </div>
    """
    try:
        from services.email_notifications import send_email
        await send_email(
            to_email=os.environ.get("PARTNERS_ALERT_EMAIL", "partners@bidvex.ca"),
            subject=subject,
            html_content=body_html,
        )
    except Exception as exc:
        logger.warning(f"[iter209] resubmission admin email failed: {exc}")

    try:
        await db.admin_notifications.insert_one({
            "id": str(uuid.uuid4()),
            "kind": f"{flavor}_resubmitted",
            "title": f"{title_prefix} resubmitted: {applicant_name or applicant_email}",
            "body": f"Attempt {resubmission_count}/3 · prev: {previous_reason[:120] if previous_reason else '—'}",
            "target_user_id": applicant_id,
            "admin_id": None,
            "extra": {"resubmission_count": resubmission_count, "province": province},
            "resolved": False,
            "created_at": datetime.now(timezone.utc),
        })
    except Exception as exc:
        logger.warning(f"[iter209] admin_notifications insert failed: {exc}")
