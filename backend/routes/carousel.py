"""
BidVex Carousel & Stats Router
Homepage data endpoints: ending soon, featured, new listings,
recently sold, top sellers, hot items.
AI Personalization: ending-soon re-sorted by user interest affinity.
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Optional
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
async def get_ending_soon_listings(limit: int = 12, user_id: Optional[str] = Query(None)):
    """Get listings ending soon. If user_id is provided, re-sort by interest affinity."""
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
        ).sort("auction_end_date", 1).limit(limit * 2).to_list(limit * 2)

        # AI Personalization: boost categories the user has shown interest in
        if user_id and listings:
            try:
                week_ago = (current_time - timedelta(days=7)).isoformat()
                pipeline = [
                    {"$match": {"user_id": user_id, "created_at": {"$gte": week_ago}}},
                    {"$group": {"_id": "$metadata.category", "score": {"$sum": 1}}},
                    {"$match": {"_id": {"$ne": None}}},
                    {"$sort": {"score": -1}},
                    {"$limit": 5},
                ]
                prefs = await db.user_interests.aggregate(pipeline).to_list(5)
                pref_map = {p["_id"].lower(): p["score"] for p in prefs if p["_id"]}

                if pref_map:
                    for item in listings:
                        cat = (item.get("category") or "").lower()
                        item["_affinity"] = pref_map.get(cat, 0)
                    # Stable sort: affinity DESC, then original order (end time ASC)
                    listings.sort(key=lambda x: -x.get("_affinity", 0))
                    for item in listings:
                        item.pop("_affinity", None)
            except Exception as e:
                logger.warning(f"AI personalization skipped: {e}")

        return listings[:limit]

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


@carousel_router.get("/carousel/recently-sold-ticker")
async def get_recently_sold_ticker(limit: int = 30):
    """
    Unified rolling ticker (iter175) — combines sold auctions across all three
    surfaces:
      • marketplace (`db.listings`)         status=sold
      • storage     (`db.storage_auctions`) status=sold
      • vehicle     (`db.vehicle_listings`) status=sold

    Per spec, the ticker is hidden until the platform has >= 10 completed
    auctions in TOTAL across all three sources. The endpoint returns
        { visible: bool, total: int, items: [...] }
    where each item is a normalized:
        { kind, price, currency, city, province, label_en, label_fr, sold_at }

    Cached 60s.
    """
    cache_key = f"{LISTINGS_NS}sold_ticker:{limit}"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached

    db = get_db()
    out = []

    try:
        # 1. Marketplace
        async for x in db.listings.find(
            {"status": "sold"},
            {
                "_id": 0, "id": 1, "title": 1, "title_fr": 1, "category": 1,
                "current_price": 1, "currency": 1, "city": 1, "province": 1,
                "sold_at": 1, "ended_at": 1,
            },
        ).sort("sold_at", -1).limit(limit):
            label_en = x.get("title") or x.get("category") or "Marketplace lot"
            label_fr = x.get("title_fr") or x.get("title") or x.get("category") or "Lot Marketplace"
            out.append({
                "kind": "marketplace",
                "price": float(x.get("current_price") or 0),
                "currency": x.get("currency") or "CAD",
                "city": x.get("city") or "",
                "province": x.get("province") or "",
                "label_en": label_en,
                "label_fr": label_fr,
                "sold_at": x.get("sold_at") or x.get("ended_at"),
            })
    except Exception as e:
        logger.error(f"[ticker] marketplace failed: {e}")

    try:
        # 2. Storage
        async for x in db.storage_auctions.find(
            {"status": "sold"},
            {
                "_id": 0, "id": 1, "unit_number": 1, "unit_type": 1, "unit_size": 1,
                "current_bid": 1, "facility_city": 1, "facility_province": 1,
                "ended_at": 1, "end_time": 1, "city": 1, "province": 1,
            },
        ).sort("ended_at", -1).limit(limit):
            unit_size = x.get("unit_size") or ""
            unit_type = (x.get("unit_type") or "").replace("_", " ")
            label_en = f"Storage unit {unit_size} ({unit_type})".strip()
            label_fr = f"Unité d'entreposage {unit_size} ({unit_type})".strip()
            out.append({
                "kind": "storage",
                "price": float(x.get("current_bid") or 0),
                "currency": "CAD",
                "city": x.get("facility_city") or x.get("city") or "",
                "province": x.get("facility_province") or x.get("province") or "",
                "label_en": label_en,
                "label_fr": label_fr,
                "sold_at": x.get("ended_at") or x.get("end_time"),
            })
    except Exception as e:
        logger.error(f"[ticker] storage failed: {e}")

    try:
        # 3. Vehicle
        async for x in db.vehicle_listings.find(
            {"status": "sold"},
            {
                "_id": 0, "id": 1, "year": 1, "make": 1, "model": 1, "trim": 1,
                "current_bid": 1, "final_price": 1, "city": 1, "province": 1,
                "ended_at": 1, "sold_at": 1,
            },
        ).sort("sold_at", -1).limit(limit):
            yr = x.get("year") or ""
            make = x.get("make") or ""
            model = x.get("model") or ""
            label_en = f"{yr} {make} {model}".strip() or "Vehicle"
            label_fr = label_en
            price = x.get("final_price") or x.get("current_bid") or 0
            out.append({
                "kind": "vehicle",
                "price": float(price),
                "currency": "CAD",
                "city": x.get("city") or "",
                "province": x.get("province") or "",
                "label_en": label_en,
                "label_fr": label_fr,
                "sold_at": x.get("sold_at") or x.get("ended_at"),
            })
    except Exception as e:
        logger.error(f"[ticker] vehicle failed: {e}")

    # Sort by sold_at desc, take top `limit`
    def _sort_key(it):
        v = it.get("sold_at")
        return v or ""
    out.sort(key=_sort_key, reverse=True)
    items = out[:limit]
    total = len(out)

    payload = {
        "visible": total >= 10,
        "total": total,
        "threshold": 10,
        "items": items,
    }
    await cache_set(cache_key, payload, 60)
    return payload


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
