"""
routes/relist.py — iter298 BUG 2

Relist flow for auctions that ended with zero bids.

POST /api/listings/{listing_id}/relist?mode=now|draft

  • mode=now   ("Relist Now")    — duplicate the listing with
        start_time=now, end_time=now+original_duration, bid history
        reset, status=active (vehicles from non-trusted sellers go
        through the standard approval workflow → status=draft).
  • mode=draft ("Edit & Relist") — same duplicate but status=draft;
        the frontend opens the edit form pre-populated so the seller
        can adjust title / price / duration / photos before publishing.

Eligible source statuses: ended_no_sale, unsold, expired, or
ended/sold-less docs with no winner. Resolver walks all 4 directory
collections. Seller-only (admin override allowed).
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from deps import get_db, get_current_user

logger = logging.getLogger(__name__)
relist_router = APIRouter(tags=["relist"])

_NO_SALE_STATUSES = {"ended_no_sale", "unsold", "expired", "ended", "no_bids"}

_COLLECTIONS = (
    ("listings", "marketplace"),
    ("multi_item_listings", "lots"),
    ("storage_auctions", "storage"),
    ("vehicle_listings", "vehicles"),
)

# Fields that must NEVER be copied into the relisted document.
_RESET_FIELDS = (
    "_id", "bids", "bid_count", "highest_bidder_id", "highest_bidder_name",
    "winner_id", "winner_user_id", "winning_bidder_id", "winning_bid",
    "final_price", "sold_at", "ended_at", "closed_at", "end_reason",
    "payment_status", "payment_collected_at", "payment_failed_at",
    "payment_deadline", "payment_link_url", "payment_transaction_id",
    "buyer_receipt_id", "seller_statement_id", "net_payout_amount",
    "pickup_code", "pickup_code_used", "pickup_code_used_at",
    "pickup_confirmed", "pickup_confirmed_at", "extension_count",
    "relisted_to", "no_sale_notified_at", "settled_at",
    "is_promoted", "promotion_tier", "promotion_tier_weight",
    "promoted_until", "promotion_end", "is_featured",
)


def _parse_dt(v) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def _original_duration(doc: Dict[str, Any]) -> timedelta:
    """Original auction duration (start → end). Defaults to 7 days."""
    start = (_parse_dt(doc.get("auction_start_date")) or _parse_dt(doc.get("start_time"))
             or _parse_dt(doc.get("created_at")))
    end = _parse_dt(doc.get("auction_end_date")) or _parse_dt(doc.get("end_time"))
    if start and end and end > start:
        dur = end - start
        if timedelta(hours=1) <= dur <= timedelta(days=60):
            return dur
    return timedelta(days=7)


async def _resolve(db, listing_id: str):
    for coll_name, section in _COLLECTIONS:
        doc = await db[coll_name].find_one({"id": listing_id}, {"_id": 0})
        if doc:
            return coll_name, section, doc
    return None, None, None


def _is_trusted_vehicle_seller(user_doc: Dict[str, Any]) -> bool:
    return bool(
        user_doc.get("role") in ("admin", "super_admin")
        or user_doc.get("is_partner")
        or user_doc.get("is_vehicle_dealer")
        or user_doc.get("is_storage_facility")
        or user_doc.get("partner_verification_status") == "verified"
    )


@relist_router.post("/listings/{listing_id}/relist")
async def relist_listing(
    listing_id: str,
    mode: str = Query("now", pattern="^(now|draft)$"),
    user=Depends(get_current_user),
):
    db = get_db()
    user_id = user.id if hasattr(user, "id") else user.get("id")
    is_admin = getattr(user, "role", None) in ("admin", "super_admin")

    coll_name, section, doc = await _resolve(db, listing_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Listing not found")

    owner_id = doc.get("seller_id") or doc.get("facility_owner_id") or doc.get("seller_user_id")
    if owner_id != user_id and not is_admin:
        raise HTTPException(status_code=403, detail="Only the listing owner can relist")

    status = (doc.get("status") or "").lower()
    has_winner = bool(doc.get("winner_user_id") or doc.get("winner_id")
                      or doc.get("winning_bidder_id"))
    if status not in _NO_SALE_STATUSES or has_winner:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "not_relistable",
                "message": "Only ended listings without a winner can be relisted.",
                "status": status,
            },
        )
    if doc.get("relisted_to"):
        raise HTTPException(
            status_code=409,
            detail={"code": "already_relisted", "new_listing_id": doc["relisted_to"]},
        )

    now = datetime.now(timezone.utc)
    duration = _original_duration(doc)
    new_id = str(uuid.uuid4())

    new_doc = {k: v for k, v in doc.items() if k not in _RESET_FIELDS}
    new_doc.update({
        "id": new_id,
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "relisted_from": listing_id,
        "relist_count": int(doc.get("relist_count") or 0) + 1,
        "current_price": doc.get("starting_price") or doc.get("current_price") or 0,
        "bid_count": 0,
    })

    # Per-collection time + status conventions.
    if coll_name == "listings":
        new_doc["auction_start_date"] = now.isoformat()
        new_doc["auction_end_date"] = (now + duration).isoformat()
        new_doc["status"] = "active" if mode == "now" else "draft"
    elif coll_name == "multi_item_listings":
        new_doc["auction_start_date"] = now.isoformat()
        new_doc["auction_end_date"] = (now + duration).isoformat()
        new_doc["status"] = "active" if mode == "now" else "draft"
        # Reset per-lot bid state.
        lots = []
        for lot in doc.get("lots") or []:
            clean = {k: v for k, v in lot.items() if k not in _RESET_FIELDS}
            clean["current_price"] = lot.get("starting_price") or 0
            clean["bid_count"] = 0
            clean["status"] = "active"
            clean["lot_end_time"] = (now + duration).isoformat()
            lots.append(clean)
        new_doc["lots"] = lots
    elif coll_name == "storage_auctions":
        new_doc["start_time"] = now.isoformat()
        new_doc["end_time"] = (now + duration).isoformat()
        new_doc["current_bid"] = doc.get("starting_bid") or 0
        new_doc["bids"] = []
        new_doc["status"] = "active" if mode == "now" else "draft"
    else:  # vehicle_listings
        new_doc["start_time"] = now
        new_doc["end_time"] = now + duration
        # Vehicles: untrusted sellers go through the standard approval flow.
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0}) or {}
        if mode == "draft":
            new_doc["status"] = "draft"
        elif _is_trusted_vehicle_seller(user_doc) or is_admin:
            new_doc["status"] = "active"
            new_doc["approved_at"] = now
            new_doc["approved_by"] = "relist_fast_track"
        else:
            new_doc["status"] = "draft"
            new_doc["pending_approval"] = True

    await db[coll_name].insert_one({**new_doc})
    new_doc.pop("_id", None)
    await db[coll_name].update_one(
        {"id": listing_id},
        {"$set": {"relisted_to": new_id, "relisted_at": now.isoformat()}},
    )

    logger.info(f"[relist] {section} {listing_id} → {new_id} (mode={mode}, status={new_doc['status']})")
    return {
        "success": True,
        "new_listing_id": new_id,
        "section": section,
        "status": new_doc["status"],
        "mode": mode,
        "end_time": (now + duration).isoformat(),
    }
