"""
iter304 — "Email to Friend" share endpoint for Vehicle listings
================================================================
POST /api/vehicles/{vehicle_id}/email-to-friend

Body: {
  recipient_email: str,
  message: Optional[str]
}

Rate limit: max 5 sends per user per day (24h sliding window).
Uses the iter299 Outlook-safe email helper.

Per-user/per-day quota is enforced via the `email_to_friend_log`
collection (TTL not used here; we just count rows for last 24h).
"""
from datetime import datetime, timezone, timedelta
import uuid
import re
import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

from deps import User, get_current_user, get_db
from services.emails.email_vehicles import send_vehicle_email_to_friend

logger = logging.getLogger(__name__)

router = APIRouter(tags=["share"])

DAILY_LIMIT = 5
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class EmailToFriendBody(BaseModel):
    recipient_email: str = Field(..., min_length=3, max_length=200)
    message: Optional[str] = Field(None, max_length=500)


async def _enforce_daily_limit(db, user_id: str):
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    count = await db.email_to_friend_log.count_documents({
        "sender_id": user_id,
        "sent_at": {"$gte": since},
    })
    if count >= DAILY_LIMIT:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limit_exceeded",
                "message_en": f"Daily limit reached ({DAILY_LIMIT} emails per 24h).",
                "message_fr": f"Limite quotidienne atteinte ({DAILY_LIMIT} courriels par 24h).",
            },
        )


@router.post("/vehicles/{vehicle_id}/email-to-friend")
async def vehicle_email_to_friend(
    vehicle_id: str,
    body: EmailToFriendBody,
    current_user: User = Depends(get_current_user),
):
    db = get_db()
    if not EMAIL_RE.match(body.recipient_email.strip()):
        raise HTTPException(status_code=400, detail="Invalid recipient email")

    listing = await db.vehicle_listings.find_one({"id": vehicle_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle listing not found")

    await _enforce_daily_limit(db, current_user.id)

    sender_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    sender_first_name = (sender_doc or {}).get("first_name") or (sender_doc or {}).get("name") or "A friend"

    # Send bilingual email — recipient lang default = sender's preferred_language
    lang = ((sender_doc or {}).get("preferred_language") or "en").lower()
    if not lang.startswith("fr"):
        lang = "en"
    else:
        lang = "fr"

    await send_vehicle_email_to_friend(
        recipient_email=body.recipient_email.strip(),
        sender_first_name=sender_first_name,
        listing=listing,
        message=(body.message or "").strip(),
        lang=lang,
    )
    await db.email_to_friend_log.insert_one({
        "id": str(uuid.uuid4()),
        "sender_id": current_user.id,
        "recipient_email": body.recipient_email.strip().lower(),
        "vehicle_id": vehicle_id,
        "sent_at": datetime.now(timezone.utc),
    })
    return {
        "ok": True,
        "remaining_today": DAILY_LIMIT - 1 - await db.email_to_friend_log.count_documents({
            "sender_id": current_user.id,
            "sent_at": {"$gte": datetime.now(timezone.utc) - timedelta(hours=24)},
        }) + 1,
    }
