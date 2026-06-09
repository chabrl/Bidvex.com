"""
Upcoming Notify Subscribers — iter293 Directive P1
==================================================

Lets a buyer subscribe to a single-vehicle / multi-lot vehicle auction
that is currently `upcoming`, then triggers a SendGrid email when the
auction status flips to `live`.

Endpoints (mounted under /api):
    POST  /upcoming-notify/subscribe   { listing_id, listing_type }
    GET   /upcoming-notify/me          (list my subscriptions)
    DELETE /upcoming-notify/{id}       (unsubscribe)

Collection: `upcoming_notify_subscribers`
    { id, user_id, user_email, listing_id, listing_type, created_at,
      notified_at: Optional[iso] }

The "flip to live" trigger is a scheduler job (registered in server.py)
that polls vehicle_listings + vehicle_multi_lot_auctions every 30s and
emails any subscriber whose listing just turned live.
"""
from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from datetime import datetime, timezone, timedelta
from typing import Literal, Optional
import logging
import os
import uuid

logger = logging.getLogger("upcoming_notify")
security = HTTPBearer(auto_error=False)
upcoming_notify_router = APIRouter(prefix="/api/upcoming-notify", tags=["upcoming-notify"])

_db = None

def set_upcoming_notify_db(database):
    global _db
    _db = database


class _SubscribeRequest(BaseModel):
    listing_id: str = Field(..., min_length=4)
    listing_type: Literal["vehicle", "vehicle_multi_lot", "marketplace", "lots", "storage"] = "vehicle"


async def _get_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    from jose import jwt, JWTError
    secret = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
    try:
        payload = jwt.decode(credentials.credentials, secret, algorithms=["HS256"])
        uid = payload.get("sub") or payload.get("user_id")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await _db.users.find_one({"id": uid}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


@upcoming_notify_router.post("/subscribe")
async def subscribe(req: _SubscribeRequest, user: dict = Depends(_get_user)):
    """Subscribe the current user to "notify me when this auction goes live"."""
    existing = await _db.upcoming_notify_subscribers.find_one({
        "user_id":     user["id"],
        "listing_id":  req.listing_id,
        "notified_at": None,
    })
    if existing:
        return {"ok": True, "already_subscribed": True}
    row = {
        "id":           str(uuid.uuid4()),
        "user_id":      user["id"],
        "user_email":   user.get("email"),
        "listing_id":   req.listing_id,
        "listing_type": req.listing_type,
        "created_at":   _now(),
        "notified_at":  None,
    }
    await _db.upcoming_notify_subscribers.insert_one(row)
    return {"ok": True, "id": row["id"]}


@upcoming_notify_router.get("/me")
async def my_subscriptions(user: dict = Depends(_get_user)):
    rows = await _db.upcoming_notify_subscribers.find(
        {"user_id": user["id"], "notified_at": None}, {"_id": 0}
    ).to_list(length=200)
    for r in rows:
        for k in ("created_at", "notified_at"):
            if isinstance(r.get(k), datetime):
                r[k] = r[k].isoformat()
    return {"data": rows, "total": len(rows)}


@upcoming_notify_router.delete("/{sub_id}")
async def unsubscribe(sub_id: str, user: dict = Depends(_get_user)):
    r = await _db.upcoming_notify_subscribers.delete_one(
        {"id": sub_id, "user_id": user["id"]}
    )
    if r.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Subscription not found")
    return {"ok": True}


# ── Scheduler tick — fire emails on live transitions ─────────────────

async def fire_live_transitions_once(db) -> int:
    """Find every pending subscription whose target listing just went
    LIVE, send a SendGrid 'auction is open' email, and mark the
    subscription notified.

    iter294 P1 — Also fires a 15-minute pre-start warning email exactly
    once per subscription so subscribers don't miss the kickoff.
    """
    now = _now()
    pending = await db.upcoming_notify_subscribers.find(
        {"notified_at": None}
    ).to_list(length=500)
    if not pending:
        return 0

    sent = 0
    try:
        from services import email_notifications as _en  # local import to avoid cycles
    except Exception:
        _en = None

    for sub in pending:
        lid  = sub["listing_id"]
        ltyp = sub.get("listing_type", "vehicle")
        live = False
        starting_soon = False
        title = None
        link = None
        if ltyp == "vehicle":
            doc = await db.vehicle_listings.find_one({"id": lid})
            if doc and doc.get("status") == "active":
                start = doc.get("start_time")
                if isinstance(start, str):
                    try:
                        start = datetime.fromisoformat(start.replace("Z", "+00:00"))
                    except Exception:
                        start = None
                if isinstance(start, datetime) and start.tzinfo is None:
                    start = start.replace(tzinfo=timezone.utc)
                if not start or start <= now:
                    live = True
                # 15-min pre-start warning window (once per subscriber).
                elif start - now <= timedelta(minutes=15) and not sub.get("warned_at"):
                    starting_soon = True
                title = doc.get("title") or f"{doc.get('year', '')} {doc.get('make', '')} {doc.get('model', '')}".strip()
                link  = f"/vehicle-auctions/{lid}"
        elif ltyp == "vehicle_multi_lot":
            doc = await db.vehicle_multi_lot_auctions.find_one({"id": lid})
            if doc:
                if doc.get("status") == "live":
                    live = True
                elif doc.get("status") == "upcoming":
                    start = doc.get("start_time")
                    if isinstance(start, str):
                        try:
                            start = datetime.fromisoformat(start.replace("Z", "+00:00"))
                        except Exception:
                            start = None
                    if isinstance(start, datetime) and start.tzinfo is None:
                        start = start.replace(tzinfo=timezone.utc)
                    if isinstance(start, datetime) and start - now <= timedelta(minutes=15) and not sub.get("warned_at"):
                        starting_soon = True
                title = doc.get("title")
                link  = f"/vehicle-multi-lot/{lid}"

        # 15-min pre-start warning (independent of live-flip)
        if starting_soon:
            try:
                if _en and hasattr(_en, "send_unified_email"):
                    await _en.send_unified_email(
                        "generic",
                        user={"email": sub["user_email"], "first_name": ""},
                        data={
                            "subject":      f"Starts in 15 minutes: {title}",
                            "preheader":    "An auction you're watching is about to open.",
                            "headline":     "Starting soon",
                            "body_html":    f"<p><strong>{title}</strong> opens for bidding in 15 minutes.</p><p><a href='{link}'>Open auction →</a></p>",
                        },
                    )
            except Exception as e:
                logger.warning(f"upcoming_notify pre-start send error sub={sub['id']}: {e}")
            await db.upcoming_notify_subscribers.update_one(
                {"id": sub["id"]},
                {"$set": {"warned_at": now}},
            )

        if not live:
            continue

        # Send live-now email (best-effort; subscription still gets
        # marked so we never spam the user with a stale reminder).
        try:
            if _en and hasattr(_en, "send_unified_email"):
                await _en.send_unified_email(
                    "generic",
                    user={"email": sub["user_email"], "first_name": ""},
                    data={
                        "subject":   f"Bidding open: {title}",
                        "preheader": "An auction you're watching is now open.",
                        "headline":  "Bidding is open",
                        "body_html": f"<p>The auction you asked us to watch is now open for bidding.</p><p><a href='{link}'>Open auction →</a></p>",
                    },
                )
        except Exception as e:
            logger.warning(f"upcoming_notify send error sub={sub['id']}: {e}")

        await db.upcoming_notify_subscribers.update_one(
            {"id": sub["id"]},
            {"$set": {"notified_at": now}},
        )
        sent += 1
    return sent
