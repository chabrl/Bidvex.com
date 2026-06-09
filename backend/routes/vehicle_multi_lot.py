"""
Multi-Lot Vehicle Auction Routes — iter293 Directive 2
======================================================

Endpoints (mounted under /api):
    POST   /vehicle-multi-lot-auctions             — create event
    GET    /vehicle-multi-lot-auctions             — list (filters: status, seller_id)
    GET    /vehicle-multi-lot-auctions/{event_id}  — get event + lots
    POST   /vehicle-multi-lot-auctions/{event_id}/lots/{lot_id}/bid — place bid
    POST   /vehicle-multi-lot-auctions/{event_id}/activate — admin/dealer activate
    POST   /vehicle-multi-lot-auctions/{event_id}/cancel   — dealer cancel
    POST   /vehicle-multi-lot-auctions/scheduler/tick — internal: progress lots

Scheduler-driven lot transitions live in
`services/vehicle_multi_lot_scheduler.py` — bumped every 15 s by the
existing APScheduler.
"""
from fastapi import APIRouter, HTTPException, Depends, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import uuid
import logging

from models.vehicle_multi_lot_models import (
    MultiLotAuctionCreate, MultiLotBidCreate,
    MultiLotEventStatus, MultiLotItemStatus, MultiLotTimingMode,
)

logger = logging.getLogger("vehicle_multi_lot")
security = HTTPBearer(auto_error=False)

vehicle_multi_lot_router = APIRouter(prefix="/api", tags=["vehicle-multi-lot"])

# Database injected by server.py via set_vehicle_multi_lot_db()
_db = None

def set_vehicle_multi_lot_db(database):
    global _db
    _db = database


# ── Auth helpers ─────────────────────────────────────────────────────

async def _get_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    from jose import jwt, JWTError
    import os as _os
    jwt_secret = _os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
    try:
        payload = jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
        uid = payload.get("sub") or payload.get("user_id")
        if not uid:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await _db.users.find_one({"id": uid})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def _require_dealer(user: dict) -> None:
    """Multi-lot vehicle auctions are dealer-only. Admins also allowed."""
    if user.get("role") in ("admin", "super_admin"):
        return
    if user.get("is_vehicle_dealer") is True:
        return
    raise HTTPException(
        status_code=403,
        detail="Only verified vehicle dealers can run multi-lot auctions.",
    )


# ── Helpers ──────────────────────────────────────────────────────────

def _now() -> datetime:
    return datetime.now(timezone.utc)


def _serialise(event: dict) -> dict:
    """Strip Mongo `_id` + coerce datetimes for JSON serialisation."""
    if not event:
        return event
    event.pop("_id", None)
    for key in ("start_time", "end_time", "created_at", "updated_at"):
        v = event.get(key)
        if isinstance(v, datetime):
            event[key] = v.isoformat()
    for lot in event.get("lots", []) or []:
        for key in ("start_time", "end_time"):
            v = lot.get(key)
            if isinstance(v, datetime):
                lot[key] = v.isoformat()
    return event


# ── CREATE ───────────────────────────────────────────────────────────

@vehicle_multi_lot_router.post("/vehicle-multi-lot-auctions")
async def create_multi_lot_auction(
    payload: MultiLotAuctionCreate,
    user: dict = Depends(_get_user),
):
    """Create a new multi-lot vehicle auction event.

    iter293 — Directive 3 alignment: `submission_intent` chooses
    Draft / Schedule / Live. Draft keeps the event hidden; Schedule
    requires future start_time; Live overrides start_time to now.
    """
    _require_dealer(user)

    intent = (payload.submission_intent or "live").lower()
    now = _now()
    start_time = payload.start_time
    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
    if start_time.tzinfo is None:
        start_time = start_time.replace(tzinfo=timezone.utc)

    if intent == "live":
        start_time = now
        event_status = MultiLotEventStatus.LIVE.value
    elif intent == "schedule":
        if start_time <= now + timedelta(minutes=1):
            raise HTTPException(
                status_code=422,
                detail="Schedule (Upcoming) requires a Start Time at least 1 minute in the future.",
            )
        event_status = MultiLotEventStatus.UPCOMING.value
    else:  # draft
        event_status = MultiLotEventStatus.DRAFT.value

    event_id = str(uuid.uuid4())
    lots: List[Dict[str, Any]] = []
    sequence: List[str] = []
    for idx, lot_in in enumerate(payload.lots):
        lot_id = str(uuid.uuid4())
        lot_doc = {
            "id":               lot_id,
            "lot_number":       idx + 1,
            "vin":              lot_in.vin,
            "year":             lot_in.year,
            "make":             lot_in.make,
            "model":            lot_in.model,
            "title":            lot_in.title,
            "description":      lot_in.description,
            "mileage":          lot_in.mileage,
            "body_type":        lot_in.body_type,
            "transmission":     lot_in.transmission,
            "fuel_type":        lot_in.fuel_type,
            "drivetrain":       lot_in.drivetrain,
            "exterior_color":   lot_in.exterior_color,
            "interior_color":   lot_in.interior_color,
            "ownership_status": lot_in.ownership_status,
            "title_status":     lot_in.title_status,
            "lien_status":      lot_in.lien_status,
            "location_city":    lot_in.location_city,
            "location_province": lot_in.location_province,
            "location_postal_code": lot_in.location_postal_code,
            "starting_price":   lot_in.starting_price,
            "reserve_price":    lot_in.reserve_price,
            "bid_increment":    lot_in.bid_increment,
            "media":            lot_in.media,
            "condition_report": lot_in.condition_report,
            # Runtime
            "current_bid":      0.0,
            "winner_user_id":   None,
            "winner_bid_id":    None,
            "bid_count":        0,
            "status":           MultiLotItemStatus.UPCOMING.value,
            "start_time":       None,
            "end_time":         None,
        }

        # Pre-compute start time for staggered mode so the public detail
        # page can render per-lot countdowns without waiting for the
        # scheduler to flip the first lot.
        if payload.timing_mode == MultiLotTimingMode.STAGGERED:
            offset = idx * payload.stagger_offset_seconds
            lot_doc["start_time"] = start_time + timedelta(seconds=offset)
            lot_doc["end_time"] = lot_doc["start_time"] + timedelta(seconds=payload.lot_duration_seconds)

        lots.append(lot_doc)
        sequence.append(lot_id)

    # Sequential mode — activate ONLY lot 1 at start_time.
    if payload.timing_mode == MultiLotTimingMode.SEQUENTIAL and lots:
        lots[0]["start_time"] = start_time
        lots[0]["end_time"]   = start_time + timedelta(seconds=payload.lot_duration_seconds)

    # If we're going LIVE right now and the first lot is supposed to
    # already be running, mark it LIVE so the public surface picks it
    # up instantly.
    if event_status == MultiLotEventStatus.LIVE.value and lots:
        lots[0]["status"]      = MultiLotItemStatus.LIVE.value
        lots[0]["start_time"]  = lots[0]["start_time"] or now
        lots[0]["end_time"]    = lots[0]["end_time"] or (now + timedelta(seconds=payload.lot_duration_seconds))

    event_doc = {
        "id":                       event_id,
        "title":                    payload.title,
        "description":              payload.description,
        "seller_id":                user["id"],
        "seller_email":             user.get("email"),
        "timing_mode":              payload.timing_mode.value,
        "start_time":               start_time,
        "lot_duration_seconds":     payload.lot_duration_seconds,
        "stagger_offset_seconds":   payload.stagger_offset_seconds,
        "status":                   event_status,
        "current_active_lot_index": 0 if event_status == MultiLotEventStatus.LIVE.value else -1,
        "lot_sequence":             sequence,
        "lots":                     lots,
        "bids":                     [],
        "created_at":               now,
        "updated_at":               now,
    }

    await _db.vehicle_multi_lot_auctions.insert_one(event_doc)
    return _serialise(event_doc)


# ── LIST ─────────────────────────────────────────────────────────────

@vehicle_multi_lot_router.get("/vehicle-multi-lot-auctions")
async def list_multi_lot_auctions(
    status: Optional[str] = Query(None),
    seller_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
):
    """Public list — only `upcoming` / `live` / `ended` events. Drafts
    are excluded from the public surface; the dealer's drafts dashboard
    queries with `?seller_id=me&status=draft` instead."""
    q: Dict[str, Any] = {}
    if status:
        q["status"] = status
    else:
        q["status"] = {"$in": ["upcoming", "live", "ended"]}
    if seller_id:
        q["seller_id"] = seller_id

    cursor = _db.vehicle_multi_lot_auctions.find(q, {"_id": 0}).sort(
        "start_time", -1
    ).skip(skip).limit(limit)
    rows = await cursor.to_list(length=limit)
    for r in rows:
        _serialise(r)
    return {"data": rows, "total": len(rows)}


@vehicle_multi_lot_router.get("/vehicle-multi-lot-auctions/my-drafts")
async def list_my_multi_lot_drafts(user: dict = Depends(_get_user)):
    """Dealer drafts dashboard hook."""
    rows = await _db.vehicle_multi_lot_auctions.find(
        {"seller_id": user["id"], "status": "draft"},
        {"_id": 0},
    ).sort("created_at", -1).to_list(length=200)
    for r in rows:
        _serialise(r)
    return {"data": rows, "total": len(rows)}


# ── DETAIL ───────────────────────────────────────────────────────────

@vehicle_multi_lot_router.get("/vehicle-multi-lot-auctions/{event_id}")
async def get_multi_lot_auction(event_id: str):
    doc = await _db.vehicle_multi_lot_auctions.find_one({"id": event_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Multi-lot event not found")
    return _serialise(doc)


# ── BID ──────────────────────────────────────────────────────────────

@vehicle_multi_lot_router.post("/vehicle-multi-lot-auctions/{event_id}/lots/{lot_id}/bid")
async def place_lot_bid(
    event_id: str,
    lot_id: str,
    payload: MultiLotBidCreate,
    user: dict = Depends(_get_user),
):
    """Place a bid on one lot inside a multi-lot event.

    Soft-close: bids placed in the last 120s of a lot extend the lot
    by an additional 120s. The next lot waits for the extension to
    drain before activating.

    No fee logic here — that runs at settlement time via the existing
    vehicle fee pipeline (BP=0%, platform fee=2.5%).
    """
    event = await _db.vehicle_multi_lot_auctions.find_one({"id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Multi-lot event not found")
    if event.get("status") not in ("live", "upcoming"):
        raise HTTPException(status_code=409, detail="Event is not accepting bids")

    # Resolve the lot
    lot = next((l for l in event.get("lots", []) if l.get("id") == lot_id), None)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found inside this event")

    now = _now()
    lot_start = lot.get("start_time")
    lot_end   = lot.get("end_time")
    if isinstance(lot_start, str):
        lot_start = datetime.fromisoformat(lot_start.replace("Z", "+00:00"))
    if isinstance(lot_end, str):
        lot_end = datetime.fromisoformat(lot_end.replace("Z", "+00:00"))
    # iter293 — Mongo returns naïve UTC datetimes; force-tz so the
    # compare doesn't raise `can't compare offset-naive and
    # offset-aware datetimes`.
    if isinstance(lot_start, datetime) and lot_start.tzinfo is None:
        lot_start = lot_start.replace(tzinfo=timezone.utc)
    if isinstance(lot_end, datetime) and lot_end.tzinfo is None:
        lot_end = lot_end.replace(tzinfo=timezone.utc)

    if lot.get("status") in ("ended", "sold"):
        raise HTTPException(status_code=409, detail="Lot has already ended")
    if lot_start and lot_start > now:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "lot_not_started",
                "message_en": "This lot hasn't opened for bidding yet.",
                "start_time": lot_start.isoformat(),
            },
        )
    if lot_end and lot_end <= now:
        raise HTTPException(status_code=409, detail="Lot has ended")

    # Self-bid guard
    if user["id"] == event.get("seller_id"):
        raise HTTPException(status_code=403, detail="Sellers cannot bid on their own event")

    # Validate amount > current + bid_increment
    current = float(lot.get("current_bid") or 0)
    if current <= 0:
        # First bid must be ≥ starting_price
        min_required = float(lot.get("starting_price") or 0)
    else:
        min_required = current + float(lot.get("bid_increment") or 100)
    if payload.amount < min_required:
        raise HTTPException(
            status_code=400,
            detail=f"Bid must be at least {min_required:.2f}",
        )

    # Build the bid record
    bid_id = str(uuid.uuid4())
    bid_record = {
        "id":         bid_id,
        "lot_id":     lot_id,
        "user_id":    user["id"],
        "user_email": user.get("email"),
        "amount":     payload.amount,
        "created_at": now,
    }

    # Soft-close: if within last 120s, extend the lot end_time by +120s
    new_lot_end = lot_end
    if lot_end and (lot_end - now).total_seconds() <= 120:
        new_lot_end = now + timedelta(seconds=120)

    # Atomic update — push bid, increment counter, set winner + extend.
    await _db.vehicle_multi_lot_auctions.update_one(
        {"id": event_id, "lots.id": lot_id},
        {
            "$set": {
                "lots.$.current_bid":    payload.amount,
                "lots.$.winner_user_id": user["id"],
                "lots.$.winner_bid_id":  bid_id,
                "lots.$.end_time":       new_lot_end,
                "updated_at":            now,
            },
            "$inc": {"lots.$.bid_count": 1},
            "$push": {"bids": bid_record},
        },
    )

    return {
        "ok":            True,
        "bid":           {**bid_record, "created_at": now.isoformat()},
        "new_lot_end":   new_lot_end.isoformat() if new_lot_end else None,
        "extended":      new_lot_end != lot_end,
    }


# ── ACTIVATE (dealer publishes a draft) ──────────────────────────────

@vehicle_multi_lot_router.post("/vehicle-multi-lot-auctions/{event_id}/activate")
async def activate_event(
    event_id: str,
    intent: str = Query("live", regex="^(live|schedule)$"),
    start_time: Optional[datetime] = Query(None),
    user: dict = Depends(_get_user),
):
    """Promote a draft event to live or upcoming. Used by the dealer
    drafts dashboard."""
    event = await _db.vehicle_multi_lot_auctions.find_one({"id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.get("seller_id") != user["id"] and user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Only the seller (or admin) can activate this event")
    if event.get("status") != "draft":
        raise HTTPException(status_code=409, detail="Only draft events can be activated")

    now = _now()
    if intent == "live":
        new_status = "live"
        new_start  = now
    else:
        if not start_time or start_time <= now + timedelta(minutes=1):
            raise HTTPException(
                status_code=422,
                detail="Schedule requires a future start_time at least 1 minute ahead.",
            )
        new_status = "upcoming"
        new_start  = start_time
        if new_start.tzinfo is None:
            new_start = new_start.replace(tzinfo=timezone.utc)

    # Reschedule lots based on timing mode
    lots = event.get("lots") or []
    duration = int(event.get("lot_duration_seconds") or 120)
    stagger  = int(event.get("stagger_offset_seconds") or 60)
    timing   = event.get("timing_mode") or "sequential"

    for idx, lot in enumerate(lots):
        if timing == "staggered":
            ls = new_start + timedelta(seconds=idx * stagger)
            lot["start_time"] = ls
            lot["end_time"]   = ls + timedelta(seconds=duration)
            lot["status"]     = "live" if (new_status == "live" and ls <= now) else "upcoming"
        else:
            if idx == 0:
                lot["start_time"] = new_start
                lot["end_time"]   = new_start + timedelta(seconds=duration)
                lot["status"]     = "live" if new_status == "live" else "upcoming"
            else:
                lot["start_time"] = None
                lot["end_time"]   = None
                lot["status"]     = "upcoming"

    await _db.vehicle_multi_lot_auctions.update_one(
        {"id": event_id},
        {"$set": {
            "status":     new_status,
            "start_time": new_start,
            "lots":       lots,
            "current_active_lot_index": 0 if new_status == "live" else -1,
            "updated_at": now,
        }},
    )
    return {"ok": True, "status": new_status}


# ── CANCEL ───────────────────────────────────────────────────────────

@vehicle_multi_lot_router.post("/vehicle-multi-lot-auctions/{event_id}/cancel")
async def cancel_event(event_id: str, user: dict = Depends(_get_user)):
    event = await _db.vehicle_multi_lot_auctions.find_one({"id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.get("seller_id") != user["id"] and user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Only the seller (or admin) can cancel this event")
    if event.get("status") in ("ended", "cancelled"):
        raise HTTPException(status_code=409, detail="Event is already finalised")
    await _db.vehicle_multi_lot_auctions.update_one(
        {"id": event_id},
        {"$set": {"status": "cancelled", "updated_at": _now()}},
    )
    return {"ok": True}


# ── DELETE DRAFT ─────────────────────────────────────────────────────

@vehicle_multi_lot_router.delete("/vehicle-multi-lot-auctions/{event_id}")
async def delete_draft(event_id: str, user: dict = Depends(_get_user)):
    event = await _db.vehicle_multi_lot_auctions.find_one({"id": event_id})
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if event.get("seller_id") != user["id"] and user.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Only the seller (or admin) can delete this event")
    if event.get("status") not in ("draft", "cancelled"):
        raise HTTPException(status_code=409, detail="Only draft or cancelled events can be deleted")
    await _db.vehicle_multi_lot_auctions.delete_one({"id": event_id})
    return {"ok": True}
