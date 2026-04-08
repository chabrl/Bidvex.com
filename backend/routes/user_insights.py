"""
BidVex User Insights & Behavioral Tracking
- Logs user interactions (clicks, bids, views) to user_interests collection
- Provides personalized recommendations data
- Winner's Circle persistence (won auctions)
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone
import logging
import uuid as uuid_mod

from deps import get_current_user, User

logger = logging.getLogger(__name__)

insights_router = APIRouter(tags=["User Insights"])

_db = None


def set_insights_db(db_instance):
    global _db
    _db = db_instance


def set_insights_auth(get_current_user_func):
    """Set the authentication dependency for protected routes (kept for compatibility)."""
    pass  # Not needed since we import from deps directly


def get_db():
    if _db is None:
        raise RuntimeError("Insights database not initialized")
    return _db


# ========== MODELS ==========

class TrackEventRequest(BaseModel):
    event_type: str  # "view", "click", "bid", "search", "wishlist"
    listing_id: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    search_query: Optional[str] = None
    region: Optional[str] = None
    city: Optional[str] = None
    metadata: Optional[dict] = None


# ========== EVENT TRACKING ==========

@insights_router.post("/insights/track")
async def track_user_event(event: TrackEventRequest, current_user=None):
    """Log a user interaction event for profiling."""
    db = get_db()

    # Allow anonymous tracking with session-based ID
    user_id = current_user.id if current_user else "anonymous"

    doc = {
        "id": str(uuid_mod.uuid4()),
        "user_id": user_id,
        "event_type": event.event_type,
        "listing_id": event.listing_id,
        "category": event.category,
        "price": event.price,
        "search_query": event.search_query,
        "region": event.region,
        "city": event.city,
        "metadata": event.metadata or {},
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = await db.user_interests.insert_one(doc)
        logger.info(f"[Insights] Tracked event: {event.event_type}, inserted_id={result.inserted_id}")
    except Exception as e:
        logger.error(f"[Insights] Failed to insert: {e}")
        return {"success": False, "error": str(e)}
    return {"success": True}


@insights_router.post("/insights/track-batch")
async def track_batch_events(events: List[TrackEventRequest], current_user=None):
    """Log multiple user events in one request."""
    db = get_db()
    user_id = current_user.id if current_user else "anonymous"

    docs = []
    for event in events:
        docs.append({
            "id": str(uuid_mod.uuid4()),
            "user_id": user_id,
            "event_type": event.event_type,
            "listing_id": event.listing_id,
            "category": event.category,
            "price": event.price,
            "search_query": event.search_query,
            "region": event.region,
            "city": event.city,
            "metadata": event.metadata or {},
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

    if docs:
        await db.user_interests.insert_many(docs)
    return {"success": True, "tracked": len(docs)}


@insights_router.get("/insights/profile/{user_id}")
async def get_user_profile(user_id: str):
    """Get aggregated user interest profile for personalization."""
    db = get_db()

    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": None,
            "total_events": {"$sum": 1},
            "categories": {"$push": "$category"},
            "regions": {"$push": "$region"},
            "max_bid": {"$max": "$price"},
            "avg_price": {"$avg": "$price"},
            "bid_count": {"$sum": {"$cond": [{"$eq": ["$event_type", "bid"]}, 1, 0]}},
            "view_count": {"$sum": {"$cond": [{"$eq": ["$event_type", "view"]}, 1, 0]}},
            "click_count": {"$sum": {"$cond": [{"$eq": ["$event_type", "click"]}, 1, 0]}},
        }}
    ]

    results = await db.user_interests.aggregate(pipeline).to_list(1)
    if not results:
        return {"user_id": user_id, "total_events": 0, "top_categories": [], "top_regions": [], "price_sensitivity": {}}

    profile = results[0]

    # Count category frequency
    cat_freq = {}
    for c in profile.get("categories", []):
        if c:
            cat_freq[c] = cat_freq.get(c, 0) + 1
    top_categories = sorted(cat_freq.items(), key=lambda x: x[1], reverse=True)[:5]

    # Count region frequency (location demand)
    reg_freq = {}
    for r in profile.get("regions", []):
        if r:
            reg_freq[r] = reg_freq.get(r, 0) + 1
    top_regions = sorted(reg_freq.items(), key=lambda x: x[1], reverse=True)[:5]

    return {
        "user_id": user_id,
        "total_events": profile.get("total_events", 0),
        "top_categories": [{"name": c, "count": n} for c, n in top_categories],
        "top_regions": [{"name": r, "count": n} for r, n in top_regions],
        "price_sensitivity": {
            "max_bid": profile.get("max_bid"),
            "avg_price": round(profile.get("avg_price", 0) or 0, 2),
        },
        "activity": {
            "bids": profile.get("bid_count", 0),
            "views": profile.get("view_count", 0),
            "clicks": profile.get("click_count", 0),
        },
    }


# ========== WINNER'S CIRCLE ==========

@insights_router.get("/winners/my-wins")
async def get_my_won_auctions(current_user: User = Depends(get_current_user)):
    """Get user's won auctions (persisted for 30 days)."""
    db = get_db()

    wins = await db.won_auctions.find(
        {"winner_id": current_user.id},
        {"_id": 0}
    ).sort("won_at", -1).limit(50).to_list(50)

    return {"wins": wins, "total": len(wins)}


async def persist_auction_winner(db, listing_id: str, winner_id: str, winning_bid: float, listing_data: dict):
    """Called when auction ends — persists winner for 30 days."""
    doc = {
        "id": str(uuid_mod.uuid4()),
        "listing_id": listing_id,
        "winner_id": winner_id,
        "winning_bid": winning_bid,
        "listing_title": listing_data.get("title", ""),
        "listing_category": listing_data.get("category", ""),
        "listing_image": listing_data.get("images", [None])[0] if listing_data.get("images") else None,
        "currency": listing_data.get("currency", "CAD"),
        "won_at": datetime.now(timezone.utc).isoformat(),
        "status": "won",
        "archived": False,
    }
    await db.won_auctions.insert_one(doc)
    logger.info(f"Winner persisted: user={winner_id}, listing={listing_id}, bid={winning_bid}")
    return doc


# ========== REGIONAL TRENDS (Seller Analytics) ==========

@insights_router.get("/insights/regional-trends")
async def get_regional_trends(current_user: User = Depends(get_current_user)):
    """
    Aggregate user_interests data to surface regional demand trends.
    Returns top categories, regions, and notable demand shifts for seller dashboard.
    """
    db = get_db()
    from datetime import timedelta

    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    two_weeks_ago = (now - timedelta(days=14)).isoformat()

    # Top categories searched/viewed this week
    pipeline_categories = [
        {"$match": {"created_at": {"$gte": week_ago}, "event_type": {"$in": ["view", "search", "click", "bid"]}}},
        {"$group": {"_id": "$metadata.category", "count": {"$sum": 1}}},
        {"$match": {"_id": {"$ne": None}}},
        {"$sort": {"count": -1}},
        {"$limit": 8},
    ]
    cat_results = await db.user_interests.aggregate(pipeline_categories).to_list(8)

    # Top regions with activity this week
    pipeline_regions = [
        {"$match": {"created_at": {"$gte": week_ago}, "event_type": {"$in": ["view", "click", "bid"]}}},
        {"$group": {"_id": "$metadata.region", "count": {"$sum": 1}}},
        {"$match": {"_id": {"$ne": None}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    region_results = await db.user_interests.aggregate(pipeline_regions).to_list(5)

    # 0% BP interest (users clicking/viewing zero-fee items)
    zero_bp_this_week = await db.user_interests.count_documents({
        "created_at": {"$gte": week_ago},
        "metadata.zero_fee": True,
    })
    zero_bp_prev_week = await db.user_interests.count_documents({
        "created_at": {"$gte": two_weeks_ago, "$lt": week_ago},
        "metadata.zero_fee": True,
    })

    # Category-region cross (top combo)
    pipeline_cross = [
        {"$match": {"created_at": {"$gte": week_ago}, "event_type": {"$in": ["view", "click", "bid"]}}},
        {"$group": {"_id": {"category": "$metadata.category", "region": "$metadata.region"}, "count": {"$sum": 1}}},
        {"$match": {"_id.category": {"$ne": None}, "_id.region": {"$ne": None}}},
        {"$sort": {"count": -1}},
        {"$limit": 5},
    ]
    cross_results = await db.user_interests.aggregate(pipeline_cross).to_list(5)

    # Build insights
    insights = []
    for cr in cross_results:
        cat = cr["_id"]["category"]
        reg = cr["_id"]["region"]
        cnt = cr["count"]
        insights.append({
            "type": "regional_demand",
            "message": f"High Demand in {reg}: Searches for '{cat}' — {cnt} interactions this week.",
            "category": cat,
            "region": reg,
            "count": cnt,
        })

    if zero_bp_this_week > 0:
        pct_change = round(((zero_bp_this_week - zero_bp_prev_week) / max(zero_bp_prev_week, 1)) * 100)
        direction = "up" if pct_change > 0 else "down" if pct_change < 0 else "stable"
        insights.append({
            "type": "zero_bp_interest",
            "message": f"Top Interest: Users prioritizing 0% BP Vehicles — {zero_bp_this_week} views ({'+' if pct_change > 0 else ''}{pct_change}% vs last week).",
            "count": zero_bp_this_week,
            "change_pct": pct_change,
            "direction": direction,
        })

    return {
        "period": "last_7_days",
        "top_categories": [{"category": r["_id"], "count": r["count"]} for r in cat_results],
        "top_regions": [{"region": r["_id"], "count": r["count"]} for r in region_results],
        "insights": insights,
    }
