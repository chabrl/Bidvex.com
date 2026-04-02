"""
BidVex Carousel & Stats Router
Homepage data endpoints: ending soon, featured, new listings,
recently sold, top sellers, hot items.
"""

from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone, timedelta
import logging

from services.api_cache import cache_get, cache_set, LISTINGS_NS

logger = logging.getLogger(__name__)

carousel_router = APIRouter(tags=["Carousel & Stats"])

_db = None


def set_carousel_db(db_instance):
    global _db
    _db = db_instance


def get_db():
    if _db is None:
        raise RuntimeError("Carousel database not initialized")
    return _db


@carousel_router.get("/carousel/ending-soon")
async def get_ending_soon_listings(limit: int = 12):
    """Get listings ending soon (within next 24 hours)"""
    try:
        db = get_db()
        current_time = datetime.now(timezone.utc)
        twenty_four_hours_later = current_time + timedelta(hours=24)

        listings = await db.listings.find(
            {
                "status": "active",
                "auction_end_date": {
                    "$gte": current_time.isoformat(),
                    "$lte": twenty_four_hours_later.isoformat(),
                },
            },
            {"_id": 0},
        ).sort("auction_end_date", 1).limit(limit).to_list(limit)

        return listings

    except Exception as e:
        logger.error(f"Error fetching ending soon listings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch ending soon listings")


@carousel_router.get("/carousel/featured")
async def get_featured_listings(limit: int = 12):
    """Get featured/promoted listings"""
    try:
        db = get_db()
        listings = await db.listings.find(
            {"status": "active", "is_promoted": True},
            {"_id": 0},
        ).sort("created_at", -1).limit(limit).to_list(limit)

        return listings

    except Exception as e:
        logger.error(f"Error fetching featured listings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch featured listings")


@carousel_router.get("/carousel/new-listings")
async def get_new_listings(limit: int = 12):
    """Get newest listings (created in last 7 days) — cached 60s"""
    cache_key = f"{LISTINGS_NS}new:{limit}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        db = get_db()
        seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
        listings = await db.listings.find(
            {"status": "active", "created_at": {"$gte": seven_days_ago.isoformat()}},
            {"_id": 0},
        ).sort("created_at", -1).limit(limit).to_list(limit)
        await cache_set(cache_key, listings, 60)
        return listings
    except Exception as e:
        logger.error(f"Error fetching new listings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch new listings")


@carousel_router.get("/carousel/recently-sold")
async def get_recently_sold(limit: int = 12):
    """Get recently sold items — cached 60s"""
    cache_key = f"{LISTINGS_NS}sold:{limit}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached
    try:
        db = get_db()
        listings = await db.listings.find(
            {"status": "sold"}, {"_id": 0}
        ).sort("sold_at", -1).limit(limit).to_list(limit)
        await cache_set(cache_key, listings, 60)
        return listings
    except Exception as e:
        logger.error(f"Error fetching recently sold: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch recently sold")


@carousel_router.get("/stats/top-sellers")
async def get_top_sellers(limit: int = 10):
    """Top sellers — cached 60s"""
    cache_key = f"{LISTINGS_NS}top_sellers:{limit}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached
    db = get_db()
    pipeline = [
        {"$match": {"status": "sold"}},
        {"$group": {"_id": "$seller_id", "total_sales": {"$sum": "$current_price"}, "count": {"$sum": 1}}},
        {"$sort": {"total_sales": -1}},
        {"$limit": limit},
    ]
    results = await db.listings.aggregate(pipeline).to_list(limit)

    sellers = []
    for result in results:
        user = await db.users.find_one({"id": result["_id"]}, {"_id": 0, "password": 0})
        if user:
            sellers.append({
                "user": user,
                "total_sales": result["total_sales"],
                "items_sold": result["count"],
            })
    await cache_set(cache_key, sellers, 60)
    return sellers


@carousel_router.get("/stats/hot-items")
async def get_hot_items(limit: int = 10):
    """Hot items by views"""
    db = get_db()
    listings = await db.listings.find(
        {"status": "active"},
        {"_id": 0},
    ).sort("views", -1).limit(limit).to_list(limit)

    return listings
