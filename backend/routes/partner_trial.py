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

    # Admins may activate trials for any user_id; otherwise users may
    # only activate for themselves.
    is_admin = getattr(current_user, "role", None) == "admin" or getattr(current_user, "is_admin", False)
    if not is_admin and body.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="cannot activate trial for another user")

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


__all__ = ["partner_trial_router"]
