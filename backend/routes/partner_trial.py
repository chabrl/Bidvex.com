"""
iter258 Mission 4 — Partner Trial activation.

POST /api/promotions/partner-trial
  Body:
    user_id, partner_type ("dealer"|"broker"|"storage"),
    company_name, licence_number (req. for broker),
    province, phone

  Inserts a `partner_trials` doc, flips relevant flags on the user,
  and sends the `partner_welcome` email.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import get_db, get_current_user, User

logger = logging.getLogger(__name__)

partner_trial_router = APIRouter(prefix="/promotions", tags=["Partner Trial"])


_TRIAL_DURATIONS = {
    "dealer":  30,
    "broker":  60,
    "storage": 45,
}

_TRIAL_FEATURED_QUOTAS = {
    "dealer":  3,
    "broker":  99,  # "unlimited" — capped via UI
    "storage": 5,
}


class PartnerTrialBody(BaseModel):
    user_id: str
    partner_type: str = Field(..., pattern="^(dealer|broker|storage)$")
    company_name: str = Field(..., min_length=2, max_length=200)
    licence_number: Optional[str] = None
    province: str = Field(..., min_length=2, max_length=4)
    phone: str = Field(..., min_length=7, max_length=40)


@partner_trial_router.post("/partner-trial")
async def activate_partner_trial(
    body: PartnerTrialBody,
    current_user: User = Depends(get_current_user),
):
    db = get_db()

    # iter259 — Admin-only. The public landing page is gone; partner
    # trials are now activated exclusively from the Admin Promotions
    # Engine by a privileged operator (one user_id at a time).
    is_admin = getattr(current_user, "role", None) == "admin" or getattr(current_user, "is_admin", False)
    if not is_admin:
        raise HTTPException(
            status_code=403,
            detail="Admin only — partner trials are activated by BidVex staff",
        )

    target = await db.users.find_one({"id": body.user_id}, {"_id": 0})
    if not target:
        raise HTTPException(status_code=404, detail="user not found")

    if body.partner_type == "broker" and not (body.licence_number and body.licence_number.strip()):
        raise HTTPException(
            status_code=400,
            detail="licence_number is required for broker partner type",
        )

    existing = await db.partner_trials.find_one(
        {"user_id": body.user_id, "status": "active"},
        {"_id": 0},
    )
    if existing:
        raise HTTPException(status_code=409, detail="user already has an active partner trial")

    duration = _TRIAL_DURATIONS[body.partner_type]
    quota = _TRIAL_FEATURED_QUOTAS[body.partner_type]
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=duration)

    doc = {
        "id": str(uuid.uuid4()),
        "user_id": body.user_id,
        "partner_type": body.partner_type,
        "company_name": body.company_name.strip(),
        "licence_number": (body.licence_number or "").strip() or None,
        "province": body.province.upper(),
        "phone": body.phone.strip(),
        "status": "active",
        "trial_expires_at": expires_at.isoformat(),
        "featured_listings_remaining": quota,
        "created_at": now.isoformat(),
    }
    await db.partner_trials.insert_one(doc)

    user_updates = {
        "partner_type": body.partner_type,
        "partner_trial_active": True,
        "partner_trial_expires_at": expires_at.isoformat(),
    }
    if body.partner_type == "broker":
        user_updates["is_broker_partner"] = True
    await db.users.update_one({"id": body.user_id}, {"$set": user_updates})

    try:
        from services.email_notifications import send_unified_email
        await send_unified_email(
            user=dict(target),
            email_type="partner_welcome",
            data={
                "partner_type": body.partner_type,
                "trial_duration": str(duration),
                "trial_expires_at": expires_at.strftime("%Y-%m-%d"),
            },
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"partner_welcome email dispatch failed: {exc}")

    # Best-effort notification.
    try:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": body.user_id,
            "type": "partner_welcome",
            "title": "🎉 Partner trial activated",
            "body": f"Your {duration}-day {body.partner_type} trial is now live.",
            "link": "/dashboard",
            "is_read": False,
            "created_at": now.isoformat(),
        })
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"partner_welcome notification failed: {exc}")

    return {
        "success": True,
        "trial_id": doc["id"],
        "partner_type": body.partner_type,
        "trial_expires_at": doc["trial_expires_at"],
        "featured_listings_remaining": doc["featured_listings_remaining"],
    }


# ─── iter259 — Admin management endpoints ────────────────────────────


def _require_admin(user: User) -> None:
    if getattr(user, "role", None) != "admin" and not getattr(user, "is_admin", False):
        raise HTTPException(status_code=403, detail="Admin only")


admin_partner_trials_router = APIRouter(prefix="/admin", tags=["Admin Partner Trials"])


@admin_partner_trials_router.get("/partner-trials")
async def list_partner_trials(
    page: int = 1,
    limit: int = 20,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    page = max(1, int(page or 1))
    limit = max(1, min(100, int(limit or 20)))
    skip = (page - 1) * limit

    cursor = db.partner_trials.find({}, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit)
    items = await cursor.to_list(length=limit)
    total = await db.partner_trials.count_documents({})

    # iter259 — Hydrate each row with the linked user's email + name
    # so the admin table can render without a per-row roundtrip.
    user_ids = [it.get("user_id") for it in items if it.get("user_id")]
    user_map = {}
    if user_ids:
        async for u in db.users.find(
            {"id": {"$in": user_ids}},
            {"_id": 0, "id": 1, "email": 1, "name": 1},
        ):
            user_map[u["id"]] = u
    for it in items:
        u = user_map.get(it.get("user_id"))
        it["user_email"] = (u or {}).get("email")
        it["user_name"] = (u or {}).get("name")

    return {"items": items, "total": total, "page": page, "limit": limit}


@admin_partner_trials_router.patch("/partner-trials/{trial_id}/extend")
async def extend_partner_trial(
    trial_id: str,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    doc = await db.partner_trials.find_one({"id": trial_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="trial not found")
    if doc.get("status") != "active":
        raise HTTPException(status_code=400, detail=f"cannot extend a {doc.get('status')!r} trial")
    try:
        current_expiry = datetime.fromisoformat(str(doc["trial_expires_at"]).replace("Z", "+00:00"))
    except Exception:
        current_expiry = datetime.now(timezone.utc)
    new_expiry = max(current_expiry, datetime.now(timezone.utc)) + timedelta(days=30)
    await db.partner_trials.update_one(
        {"id": trial_id},
        {"$set": {"trial_expires_at": new_expiry.isoformat()}},
    )
    await db.users.update_one(
        {"id": doc.get("user_id")},
        {"$set": {"partner_trial_expires_at": new_expiry.isoformat()}},
    )
    return {"success": True, "trial_id": trial_id, "trial_expires_at": new_expiry.isoformat()}


@admin_partner_trials_router.delete("/partner-trials/{trial_id}")
async def revoke_partner_trial(
    trial_id: str,
    current_user: User = Depends(get_current_user),
):
    _require_admin(current_user)
    db = get_db()
    doc = await db.partner_trials.find_one({"id": trial_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="trial not found")
    now = datetime.now(timezone.utc)
    await db.partner_trials.update_one(
        {"id": trial_id},
        {"$set": {"status": "revoked", "revoked_at": now.isoformat()}},
    )
    user_unset = {
        "partner_trial_active": False,
        "partner_trial_expires_at": None,
    }
    if doc.get("partner_type") == "broker":
        user_unset["is_broker_partner"] = False
    await db.users.update_one(
        {"id": doc.get("user_id")},
        {"$set": user_unset},
    )
    # Best-effort revocation email.
    try:
        target = await db.users.find_one({"id": doc.get("user_id")}, {"_id": 0})
        if target:
            from services.email_notifications import send_unified_email
            await send_unified_email(
                user=dict(target),
                email_type="trial_revoked",
                data={
                    "partner_type": doc.get("partner_type", "partner"),
                },
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"trial_revoked email dispatch failed: {exc}")
    return {"success": True, "trial_id": trial_id, "status": "revoked"}


__all__ = ["partner_trial_router", "admin_partner_trials_router"]
