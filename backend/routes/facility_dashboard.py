"""
BidVex — Phase 6.2 Task 6
Storage Facility Manager Dashboard backend.

Exposes:
  GET  /api/facility/overview          → header counts + facility profile
  GET  /api/facility/auctions          → my-auctions with status filters + counts
  GET  /api/facility/analytics         → metric cards + chart data (cached 5 min)
  GET  /api/facility/promotions        → list active + past promotions
  GET  /api/facility/ratings           → ratings for this facility
  POST /api/facility/ratings/{id}/reply → one reply per review

Public-facing (no auth):
  GET  /api/facility/public/{facility_id} → public profile snapshot
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from deps import get_db, get_current_user, User

logger = logging.getLogger(__name__)

facility_router = APIRouter(prefix="/api/facility", tags=["Facility Dashboard"])


def _is_facility(user: User) -> bool:
    """Storage-facility role gate. Admins bypass via `_is_admin`."""
    return (
        getattr(user, "account_type", "") == "storage_facility"
        or getattr(user, "is_storage_facility", False)
        or _is_admin(user)
    )


def _is_admin(user: User) -> bool:
    return (getattr(user, "role", "") or "").lower() in ("admin", "superadmin")


async def _require_facility(user: User = Depends(get_current_user)) -> User:
    if not _is_facility(user):
        raise HTTPException(status_code=403, detail={
            "error": "facility_role_required",
            "message_en": "Only verified storage facility accounts can access this dashboard.",
            "message_fr": "Seuls les comptes d'installation de stockage vérifiés peuvent accéder à ce tableau de bord.",
        })
    return user


# ── In-process analytics cache (5 minutes) ──
_ANALYTICS_CACHE: Dict[str, Dict[str, Any]] = {}
_ANALYTICS_TTL = 300  # 5 minutes


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    entry = _ANALYTICS_CACHE.get(key)
    if not entry:
        return None
    if time.time() > entry["expires_at"]:
        _ANALYTICS_CACHE.pop(key, None)
        return None
    return entry["data"]


def _cache_set(key: str, data: Dict[str, Any]):
    _ANALYTICS_CACHE[key] = {"data": data, "expires_at": time.time() + _ANALYTICS_TTL}


_PENDING_STATUSES = ("pending_ai_review", "pending_admin_review", "pending_review")
_ENDED_STATUSES = ("closed", "settled", "ended", "expired", "completed")


@facility_router.get("/overview")
async def get_facility_overview(current_user: User = Depends(_require_facility)):
    """Header bar + 4 quick-stat cards."""
    db = get_db()
    seller_id = current_user.id
    now = datetime.now(timezone.utc)

    # Pull every listing this facility owns from both single + multi collections
    single = await db.listings.find(
        {"seller_id": seller_id, "listing_type": "storage_locker"},
        {"_id": 0, "id": 1, "status": 1, "start_time": 1, "auction_end_date": 1, "title": 1},
    ).to_list(2000)
    multi = await db.multi_item_listings.find(
        {"seller_id": seller_id, "listing_type": "storage_locker"},
        {"_id": 0, "id": 1, "status": 1, "start_time": 1, "end_time": 1, "title": 1},
    ).to_list(2000)
    all_rows = single + multi

    def _is_upcoming(r):
        if r.get("status") not in ("active", "upcoming"):
            return False
        st = r.get("start_time")
        if isinstance(st, datetime):
            return st > now
        return False

    counts = {
        "live":     sum(1 for r in all_rows if r.get("status") == "active" and not _is_upcoming(r)),
        "upcoming": sum(1 for r in all_rows if _is_upcoming(r)),
        "ended":    sum(1 for r in all_rows if r.get("status") in _ENDED_STATUSES),
        "drafts":   sum(1 for r in all_rows if r.get("status") in ("draft", *_PENDING_STATUSES)),
    }

    # Facility profile (verified badge from users collection)
    user_row = await db.users.find_one(
        {"id": seller_id},
        {"_id": 0, "name": 1, "company_name": 1, "facility_verified": 1, "picture": 1, "city": 1, "region": 1},
    ) or {}

    return {
        "counts": counts,
        "facility": {
            "id": seller_id,
            "name": user_row.get("company_name") or user_row.get("name") or "My Facility",
            "verified": bool(user_row.get("facility_verified")),
            "picture": user_row.get("picture"),
            "city": user_row.get("city"),
            "region": user_row.get("region"),
        },
    }


@facility_router.get("/auctions")
async def list_facility_auctions(
    status: Optional[str] = None,  # drafts|upcoming|live|ended
    current_user: User = Depends(_require_facility),
):
    """My Auctions tab — returns auctions for the facility with status filters
    and the per-tab counts."""
    db = get_db()
    seller_id = current_user.id
    now = datetime.now(timezone.utc)

    single = await db.listings.find(
        {"seller_id": seller_id, "listing_type": "storage_locker"},
        {"_id": 0},
    ).to_list(2000)
    multi = await db.multi_item_listings.find(
        {"seller_id": seller_id, "listing_type": "storage_locker"},
        {"_id": 0},
    ).to_list(2000)
    rows = single + multi

    def _bucket(r) -> str:
        s = r.get("status")
        if s in ("draft", *_PENDING_STATUSES):
            return "drafts"
        if s in _ENDED_STATUSES:
            return "ended"
        if s == "active":
            st = r.get("start_time")
            if isinstance(st, datetime) and st > now:
                return "upcoming"
            return "live"
        if s == "upcoming":
            return "upcoming"
        return "drafts"

    for r in rows:
        r["_bucket"] = _bucket(r)
        # Normalize datetime serialization
        for k in ("created_at", "start_time", "end_time", "auction_end_date"):
            v = r.get(k)
            if isinstance(v, datetime):
                r[k] = v.isoformat()

    counts = {
        "drafts":   sum(1 for r in rows if r["_bucket"] == "drafts"),
        "upcoming": sum(1 for r in rows if r["_bucket"] == "upcoming"),
        "live":     sum(1 for r in rows if r["_bucket"] == "live"),
        "ended":    sum(1 for r in rows if r["_bucket"] == "ended"),
    }

    if status in counts:
        rows = [r for r in rows if r["_bucket"] == status]
    return {"auctions": rows, "counts": counts}


def _parse_range(range_key: str) -> Optional[datetime]:
    """Translate "7d" / "30d" / "90d" / "all" to a cutoff datetime."""
    now = datetime.now(timezone.utc)
    if range_key == "7d":
        return now - timedelta(days=7)
    if range_key == "30d":
        return now - timedelta(days=30)
    if range_key == "90d":
        return now - timedelta(days=90)
    return None  # all-time


@facility_router.get("/analytics")
async def get_facility_analytics(
    range: str = "30d",
    current_user: User = Depends(_require_facility),
):
    """Analytics tab — metric cards + chart data. Cached 5 min."""
    cache_key = f"facility-analytics:{current_user.id}:{range}"
    cached = _cache_get(cache_key)
    if cached:
        return cached

    db = get_db()
    seller_id = current_user.id
    since = _parse_range(range)

    listing_q: Dict[str, Any] = {"seller_id": seller_id, "listing_type": "storage_locker"}
    if since:
        listing_q["created_at"] = {"$gte": since}

    listings = await db.listings.find(listing_q, {"_id": 0}).to_list(5000)
    multi = await db.multi_item_listings.find(listing_q, {"_id": 0}).to_list(5000)
    rows = listings + multi

    # Settled / ended rows
    settled = [r for r in rows if r.get("status") in _ENDED_STATUSES]
    completed_count = len(settled)
    total_revenue = sum(float(r.get("hammer_price") or r.get("current_price") or 0) for r in settled)
    avg_hammer = (total_revenue / completed_count) if completed_count else 0

    # Bids
    listing_ids = [r["id"] for r in rows]
    bids_q: Dict[str, Any] = {"listing_id": {"$in": listing_ids}}
    if since:
        bids_q["created_at"] = {"$gte": since}
    total_bids = await db.bids.count_documents(bids_q) if listing_ids else 0
    avg_bids_per_unit = (total_bids / max(1, len(rows)))

    # Deposit forfeitures
    forfeit_q: Dict[str, Any] = {"facility_id": seller_id, "status": "forfeited"}
    if since:
        forfeit_q["forfeited_at"] = {"$gte": since}
    forfeited_count = await db.storage_cleanout_holds.count_documents(forfeit_q)

    # ── Chart 1: revenue over time (grouped by week or month) ──
    bucket = "month" if range in ("90d", "all") else "week"
    revenue_series: Dict[str, float] = {}
    for r in settled:
        ts = r.get("ended_at") or r.get("settled_at") or r.get("created_at")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                continue
        if not isinstance(ts, datetime):
            continue
        key = ts.strftime("%Y-%m") if bucket == "month" else ts.strftime("%Y-W%W")
        revenue_series[key] = revenue_series.get(key, 0) + float(r.get("hammer_price") or r.get("current_price") or 0)
    revenue_chart = sorted(
        [{"bucket": k, "revenue": round(v, 2)} for k, v in revenue_series.items()],
        key=lambda d: d["bucket"],
    )

    # ── Chart 2: status donut ──
    status_donut = {
        "draft":     sum(1 for r in rows if r.get("status") == "draft"),
        "pending":   sum(1 for r in rows if r.get("status") in _PENDING_STATUSES),
        "upcoming":  sum(1 for r in rows if r.get("status") == "upcoming"),
        "live":      sum(1 for r in rows if r.get("status") == "active"),
        "ended":     sum(1 for r in rows if r.get("status") in _ENDED_STATUSES),
        "cancelled": sum(1 for r in rows if r.get("status") == "cancelled"),
    }

    # ── Chart 3: top 5 units by hammer price ──
    top_units = sorted(
        [
            {"id": r["id"], "title": r.get("title", "Unit"), "hammer": float(r.get("hammer_price") or r.get("current_price") or 0)}
            for r in settled
        ],
        key=lambda d: d["hammer"],
        reverse=True,
    )[:5]

    result = {
        "range": range,
        "metrics": {
            "total_revenue":     round(total_revenue, 2),
            "completed_auctions": completed_count,
            "avg_hammer_price":  round(avg_hammer, 2),
            "total_bids":        total_bids,
            "avg_bids_per_unit": round(avg_bids_per_unit, 1),
            "deposit_forfeited": forfeited_count,
        },
        "charts": {
            "revenue_over_time": revenue_chart,
            "status_donut":      status_donut,
            "top_units":         top_units,
        },
        "cached_at": datetime.now(timezone.utc).isoformat(),
    }
    _cache_set(cache_key, result)
    return result


# ── Promotions tab ──
@facility_router.get("/promotions")
async def list_facility_promotions(current_user: User = Depends(_require_facility)):
    """Return all promotions the facility has activated — active + past."""
    db = get_db()
    cur = db.facility_promotions.find(
        {"facility_id": current_user.id}, {"_id": 0}
    ).sort("created_at", -1).limit(200)
    rows = await cur.to_list(length=200)
    for r in rows:
        for k in ("created_at", "started_at", "expires_at"):
            v = r.get(k)
            if isinstance(v, datetime):
                r[k] = v.isoformat()
    return {"promotions": rows}


class PromotionCreateRequest(BaseModel):
    listing_id: str
    type: str  # "featured" | "email_blast" | "reduced_reserve"
    duration_hours: Optional[int] = 24


@facility_router.post("/promotions")
async def create_facility_promotion(
    payload: PromotionCreateRequest,
    current_user: User = Depends(_require_facility),
):
    """Activate a promotion. Stripe charge happens at activation time —
    implemented via existing `/api/promote-listing` route. Here we just
    record the activation. Pricing comes from the same config endpoint
    the frontend already consumes (`GET /api/promote-config`)."""
    db = get_db()
    listing = await db.listings.find_one({"id": payload.listing_id}, {"_id": 0}) or \
              await db.multi_item_listings.find_one({"id": payload.listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("seller_id") != current_user.id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Not your listing")

    duration = payload.duration_hours or 24
    now = datetime.now(timezone.utc)
    promo = {
        "id": __import__("uuid").uuid4().hex,
        "facility_id": current_user.id,
        "listing_id": payload.listing_id,
        "listing_title": listing.get("title"),
        "type": payload.type,
        "duration_hours": duration,
        "status": "active",
        "started_at": now,
        "expires_at": now + timedelta(hours=duration),
        "created_at": now,
    }
    await db.facility_promotions.insert_one(promo)
    # If it's a "featured" boost, flip the listing's flags so the existing
    # marketplace sort surfaces it. Charge plumbing reuses /api/promote-listing.
    if payload.type == "featured":
        coll = "listings" if listing.get("listing_type") != "multi_lot" else "multi_item_listings"
        await db[coll].update_one(
            {"id": payload.listing_id},
            {"$set": {
                "is_promoted": True,
                "is_featured": True,
                "promoted_until": now + timedelta(hours=duration),
                "promotion_tier": "facility_boost",
                "promotion_tier_weight": 5,
            }},
        )
    return {"promotion": {**promo, "started_at": now.isoformat(), "expires_at": (now + timedelta(hours=duration)).isoformat(), "created_at": now.isoformat()}}


# ── Ratings tab ──
@facility_router.get("/ratings")
async def get_facility_ratings(current_user: User = Depends(_require_facility)):
    """Owner-facing — list every rating left for this facility."""
    db = get_db()
    cur = db.facility_ratings.find(
        {"facility_id": current_user.id}, {"_id": 0, "buyer_user_id": 0}
    ).sort("created_at", -1).limit(500)
    rows = await cur.to_list(length=500)
    for r in rows:
        v = r.get("created_at")
        if isinstance(v, datetime):
            r["created_at"] = v.isoformat()
        rv = r.get("reply", {})
        if isinstance(rv, dict):
            rt = rv.get("replied_at")
            if isinstance(rt, datetime):
                rv["replied_at"] = rt.isoformat()
    # Stats
    stars = [int(r.get("rating", 0)) for r in rows if r.get("rating")]
    avg_rating = round(sum(stars) / len(stars), 1) if stars else 0
    distribution = {n: stars.count(n) for n in (1, 2, 3, 4, 5)}
    total = len(stars)
    distribution_pct = {n: round((distribution[n] / total) * 100) if total else 0 for n in (1, 2, 3, 4, 5)}

    return {
        "ratings": rows,
        "summary": {
            "avg_rating": avg_rating,
            "total_reviews": total,
            "distribution": distribution,
            "distribution_pct": distribution_pct,
        },
    }


class FacilityReplyRequest(BaseModel):
    reply_text: str


@facility_router.post("/ratings/{rating_id}/reply")
async def reply_to_rating(
    rating_id: str,
    payload: FacilityReplyRequest,
    current_user: User = Depends(_require_facility),
):
    """One reply per review. Replies cannot be edited after 24h (enforced
    on subsequent calls)."""
    db = get_db()
    rating = await db.facility_ratings.find_one({"id": rating_id}, {"_id": 0})
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    if rating.get("facility_id") != current_user.id and not _is_admin(current_user):
        raise HTTPException(status_code=403, detail="Not your rating to reply to")

    existing_reply = rating.get("reply") or {}
    if existing_reply.get("reply_text"):
        # Check 24h edit window
        replied_at = existing_reply.get("replied_at")
        if isinstance(replied_at, str):
            try:
                replied_at = datetime.fromisoformat(replied_at.replace("Z", "+00:00"))
            except ValueError:
                replied_at = None
        if isinstance(replied_at, datetime):
            # Normalize: Mongo strips tz on round-trip — treat naive as UTC.
            if replied_at.tzinfo is None:
                replied_at = replied_at.replace(tzinfo=timezone.utc)
            elapsed_h = (datetime.now(timezone.utc) - replied_at).total_seconds() / 3600
            if elapsed_h > 24:
                raise HTTPException(status_code=400, detail={
                    "error": "edit_window_expired",
                    "message_en": "Replies cannot be edited more than 24 hours after posting.",
                    "message_fr": "Les réponses ne peuvent pas être modifiées plus de 24 heures après la publication.",
                })

    text = (payload.reply_text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Reply text cannot be empty")
    reply = {
        "reply_text": text,
        "replied_at": datetime.now(timezone.utc),
        "replied_by_facility_id": current_user.id,
    }
    await db.facility_ratings.update_one({"id": rating_id}, {"$set": {"reply": reply}})
    return {"success": True, "reply": {**reply, "replied_at": reply["replied_at"].isoformat()}}


# ── Public facility profile (no auth required) ──
public_facility_router = APIRouter(prefix="/api/facility/public", tags=["Facility Public"])


@public_facility_router.get("/{facility_id}")
async def public_facility_profile(facility_id: str):
    """Public profile page — exposes only safe-for-public fields."""
    db = get_db()
    user = await db.users.find_one(
        {"id": facility_id, "account_type": "storage_facility"},
        {"_id": 0, "name": 1, "company_name": 1, "facility_verified": 1, "picture": 1, "city": 1, "region": 1},
    )
    if not user:
        raise HTTPException(status_code=404, detail="Facility not found")

    now = datetime.now(timezone.utc)
    active = await db.listings.find(
        {"seller_id": facility_id, "listing_type": "storage_locker", "status": "active"},
        {"_id": 0, "id": 1, "title": 1, "images": 1, "current_price": 1, "auction_end_date": 1, "city": 1, "region": 1},
    ).limit(20).to_list(20)
    upcoming = await db.listings.find(
        {"seller_id": facility_id, "listing_type": "storage_locker", "status": "upcoming"},
        {"_id": 0, "id": 1, "title": 1, "images": 1, "starting_price": 1, "start_time": 1, "city": 1, "region": 1},
    ).limit(20).to_list(20)

    # Reviews (latest 3) + summary
    reviews = await db.facility_ratings.find(
        {"facility_id": facility_id}, {"_id": 0, "buyer_user_id": 0}
    ).sort("created_at", -1).limit(3).to_list(3)
    for r in reviews:
        v = r.get("created_at")
        if isinstance(v, datetime):
            r["created_at"] = v.isoformat()

    all_stars = [int(r.get("rating", 0)) for r in await db.facility_ratings.find(
        {"facility_id": facility_id}, {"_id": 0, "rating": 1}
    ).to_list(5000) if r.get("rating")]
    avg_rating = round(sum(all_stars) / len(all_stars), 1) if all_stars else 0

    # Normalize datetimes in listings
    for coll in (active, upcoming):
        for r in coll:
            for k in ("auction_end_date", "start_time", "created_at"):
                v = r.get(k)
                if isinstance(v, datetime):
                    r[k] = v.isoformat()

    return {
        "facility": {
            "id": facility_id,
            "name": user.get("company_name") or user.get("name") or "Storage Facility",
            "verified": bool(user.get("facility_verified")),
            "picture": user.get("picture"),
            "city": user.get("city"),
            "region": user.get("region"),
        },
        "summary": {"avg_rating": avg_rating, "total_reviews": len(all_stars)},
        "active_auctions": active,
        "upcoming_auctions": upcoming,
        "recent_reviews": reviews,
    }
