"""
BidVex Marketplace Router
Handles all marketplace browsing, searching, and filtering:
- Decomposed marketplace items (multi-item lots + single listings)
- Marketplace filter counts (auctioneers, categories, locations)
- Location-based search
- Promoted listings for homepage
- Click tracking for analytics
"""

from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from services.api_cache import (
    cache_get, cache_set, invalidate_prefix,
    make_cache_key, MARKETPLACE_ITEMS_NS, FILTER_COUNTS_NS,
    ITEMS_TTL, FILTER_TTL,
)
import asyncio
import time
import logging
import base64
import json

logger = logging.getLogger(__name__)

marketplace_router = APIRouter(tags=["Marketplace"])

_db = None
_db_read = None


def set_marketplace_db(db_instance):
    """Set database instance"""
    global _db
    _db = db_instance


def set_marketplace_read_db(db_instance):
    global _db_read
    _db_read = db_instance


def get_db():
    if _db is None:
        raise RuntimeError("Marketplace database not initialized")
    return _db


def get_read_db():
    return _db_read if _db_read is not None else _db


# ========== CACHE STATE (in-process guards for stale-while-revalidate) ==========
_refreshing_items = False
_refreshing_filters = False


class LocationSearchParams(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = 50.0
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None


# ── Projection: only fields the frontend actually uses ──
_LISTING_PROJECTION = {
    "_id": 0, "id": 1, "title": 1, "description": 1, "category": 1,
    "condition": 1, "images": 1, "starting_price": 1, "current_price": 1,
    "buy_now_price": 1, "bid_count": 1, "highest_bidder_id": 1,
    "auction_end_date": 1, "status": 1, "seller_id": 1,
    "is_promoted": 1, "promotion_tier": 1, "is_featured": 1,
    "is_partner_listing": 1, "city": 1, "region": 1, "country": 1,
    "created_at": 1,
    "title_en": 1, "title_fr": 1, "description_en": 1, "description_fr": 1,
}
_MULTI_PROJECTION = {
    "_id": 0, "id": 1, "title": 1, "description": 1, "category": 1,
    "lots": 1, "auction_end_date": 1, "auction_start_date": 1,
    "status": 1, "seller_id": 1, "is_promoted": 1, "promotion_tier": 1,
    "is_featured": 1, "is_partner_listing": 1, "region": 1, "country": 1,
    "created_at": 1,
    "title_en": 1, "title_fr": 1, "description_en": 1, "description_fr": 1,
}


async def _build_marketplace_items():
    """Build the full sorted marketplace items list (called from cache refresh).
    
    High-Velocity Sorting Algorithm:
    1. Primary: auction_end_date ASC (ending soonest first)
    2. Secondary: created_at DESC (newest among non-urgent)
    3. Ended auctions pushed to bottom
    """
    db = get_read_db()
    now = datetime.now(timezone.utc)

    # Fetch with projection and limit — cap at 500 each
    auctions = await db.multi_item_listings.find(
        {"status": {"$in": ["active", "upcoming"]}}, _MULTI_PROJECTION
    ).sort("auction_end_date", 1).limit(500).to_list(500)

    single_listings = await db.listings.find(
        {"status": "active"}, _LISTING_PROJECTION
    ).sort("auction_end_date", 1).limit(500).to_list(500)

    # Batch-fetch seller tax status
    all_seller_ids = list(set(
        [a.get("seller_id") for a in auctions if a.get("seller_id")] +
        [sl.get("seller_id") for sl in single_listings if sl.get("seller_id")]
    ))
    sellers = {}
    if all_seller_ids:
        seller_docs = await db.users.find(
            {"id": {"$in": all_seller_ids}},
            {"_id": 0, "id": 1, "is_tax_registered": 1}
        ).to_list(len(all_seller_ids))
        sellers = {s["id"]: s.get("is_tax_registered", False) for s in seller_docs}

    items = []

    for auction in auctions:
        seller_is_business = sellers.get(auction.get("seller_id"), False)
        base_end_time = auction.get("auction_end_date")
        if isinstance(base_end_time, str):
            base_end_time = datetime.fromisoformat(base_end_time)

        for lot in auction.get("lots", []):
            if lot.get("lot_status") == "sold_out":
                continue
            current_price = lot.get("current_price", lot.get("starting_price", 0))
            lot_end_time = lot.get("lot_end_time")
            if not lot_end_time and base_end_time:
                lot_end_time = base_end_time + timedelta(seconds=lot["lot_number"] * 60)
            elif isinstance(lot_end_time, str):
                lot_end_time = datetime.fromisoformat(lot_end_time)

            items.append({
                "id": f"{auction['id']}_lot{lot['lot_number']}",
                "auction_id": auction["id"],
                "lot_number": lot["lot_number"],
                "title": lot["title"],
                "description": lot.get("description", ""),
                "category": auction.get("category"),
                "condition": lot.get("condition"),
                "images": lot.get("images", []),
                "starting_price": lot.get("starting_price"),
                "current_price": current_price,
                "buy_now_price": lot.get("buy_now_price"),
                "buy_now_enabled": lot.get("buy_now_enabled", False),
                "quantity": lot.get("quantity", 1),
                "available_quantity": lot.get("available_quantity", lot.get("quantity", 1)),
                "sold_quantity": lot.get("sold_quantity", 0),
                "bid_count": lot.get("bid_count", 0),
                "highest_bidder_id": lot.get("highest_bidder_id"),
                "auction_end_date": lot_end_time.isoformat() if lot_end_time else None,
                "extension_count": lot.get("extension_count", 0),
                "lot_status": lot.get("lot_status", "active"),
                "pricing_mode": lot.get("pricing_mode", "multiplied"),
                "is_promoted": auction.get("is_promoted", False),
                "promotion_tier": auction.get("promotion_tier"),
                "is_featured": auction.get("is_featured", False),
                "parent_auction_title": auction.get("title"),
                "total_lots_in_auction": len(auction.get("lots", [])),
                "seller_id": auction.get("seller_id"),
                "seller_is_business": seller_is_business,
                "is_partner_listing": auction.get("is_partner_listing", False),
                "region": auction.get("region"),
                "country": auction.get("country"),
                "created_at": auction.get("created_at"),
                # i18n fields — lot-level overrides, fallback to auction-level
                "title_en": lot.get("title_en") or auction.get("title_en"),
                "title_fr": lot.get("title_fr") or auction.get("title_fr"),
                "description_en": lot.get("description_en") or auction.get("description_en"),
                "description_fr": lot.get("description_fr") or auction.get("description_fr"),
                "parent_auction_title_en": auction.get("title_en"),
                "parent_auction_title_fr": auction.get("title_fr"),
            })

    for listing in single_listings:
        current_price = listing.get("current_price", listing.get("starting_price", 0))
        items.append({
            "id": listing["id"],
            "auction_id": None,
            "lot_number": None,
            "title": listing["title"],
            "description": listing.get("description"),
            "category": listing.get("category"),
            "condition": listing.get("condition"),
            "images": listing.get("images", []),
            "starting_price": listing.get("starting_price"),
            "current_price": current_price,
            "buy_now_price": listing.get("buy_now_price"),
            "buy_now_enabled": listing.get("buy_now_price") is not None,
            "quantity": 1,
            "available_quantity": 1,
            "sold_quantity": 0,
            "bid_count": listing.get("bid_count", 0),
            "highest_bidder_id": listing.get("highest_bidder_id"),
            "auction_end_date": listing.get("auction_end_date"),
            "extension_count": 0,
            "lot_status": listing.get("status", "active"),
            "pricing_mode": "fixed",
            "is_promoted": listing.get("is_promoted", False),
            "promotion_tier": listing.get("promotion_tier"),
            "is_featured": listing.get("is_featured", False),
            "parent_auction_title": None,
            "total_lots_in_auction": 0,
            "seller_id": listing.get("seller_id"),
            "seller_is_business": sellers.get(listing.get("seller_id"), False),
            "is_partner_listing": listing.get("is_partner_listing", False),
            "city": listing.get("city"),
            "region": listing.get("region"),
            "country": listing.get("country"),
            "created_at": listing.get("created_at"),
            # i18n fields
            "title_en": listing.get("title_en"),
            "title_fr": listing.get("title_fr"),
            "description_en": listing.get("description_en"),
            "description_fr": listing.get("description_fr"),
            "parent_auction_title_en": None,
            "parent_auction_title_fr": None,
        })

    # ── High-Velocity Sort ──
    # Primary: ending soonest first (active items ahead of ended)
    # Secondary: newest first for items with the same urgency tier
    now_iso = now.isoformat()
    far_future = "9999-12-31T23:59:59+00:00"

    def _parse_end(item):
        """Parse auction_end_date to a comparable ISO string."""
        end = item.get("auction_end_date")
        if not end:
            return far_future
        if isinstance(end, datetime):
            return end.isoformat()
        return str(end)

    def _parse_created(item):
        """Parse created_at to a timestamp for descending sort."""
        c = item.get("created_at")
        if isinstance(c, datetime):
            return c.timestamp()
        return 0

    def high_velocity_sort_key(item):
        end_str = _parse_end(item)
        is_ended = end_str <= now_iso
        is_featured = item.get("is_featured", False)
        is_promoted = item.get("is_promoted", False)

        # Sort order: (ended_flag, -featured, -promoted, end_date_asc, -created_desc)
        return (
            1 if is_ended else 0,       # Ended items go to bottom
            0 if is_featured else 1,     # Featured first among actives
            0 if is_promoted else 1,     # Promoted next
            end_str,                     # Ending soonest first
            -_parse_created(item),       # Newest first as tiebreaker
        )

    items.sort(key=high_velocity_sort_key)

    return items


async def _refresh_items_cache():
    """Background task: rebuild and cache the marketplace items in Redis."""
    global _refreshing_items
    try:
        items = await _build_marketplace_items()
        await cache_set(f"{MARKETPLACE_ITEMS_NS}all", items, ITEMS_TTL)
        logger.info(f"[cache] Marketplace items refreshed: {len(items)} items")
    except Exception as e:
        logger.error(f"[cache] Marketplace items refresh failed: {e}")
    finally:
        _refreshing_items = False


async def _warm_marketplace_cache():
    """Called from server startup to pre-warm the cache."""
    global _refreshing_items
    _refreshing_items = True
    await _refresh_items_cache()


# ========== MARKETPLACE ITEMS ==========

@marketplace_router.get("/marketplace/items")
async def get_marketplace_items(
    search: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    condition: Optional[str] = None,
    sort: str = "ending_soon",
    limit: int = 20,
    skip: int = 0,
    cursor: Optional[str] = None,
    track_impression: bool = False
):
    """
    Marketplace view: Redis-cached, paginated, with stale-while-revalidate.
    Cold cache returns empty list with loading=True flag.
    """
    global _refreshing_items

    cached_items = await cache_get(f"{MARKETPLACE_ITEMS_NS}all")

    # If cache is cold (first request ever), kick off background build
    if cached_items is None:
        if not _refreshing_items:
            _refreshing_items = True
            asyncio.ensure_future(_refresh_items_cache())
        return {"items": [], "total": 0, "limit": limit, "skip": 0,
                "has_more": False, "next_cursor": None, "cache_warming": True}

    # Stale-while-revalidate: always refresh in background on every hit
    # (Redis TTL handles expiry; this ensures near-real-time data)
    if not _refreshing_items:
        _refreshing_items = True
        asyncio.ensure_future(_refresh_items_cache())

    # Filter the cached items
    items = cached_items

    if search:
        s_lower = search.lower()
        items = [i for i in items if s_lower in (i.get("title") or "").lower()
                 or s_lower in (i.get("description") or "").lower()]
    if category:
        items = [i for i in items if i.get("category") == category]
    if min_price is not None:
        items = [i for i in items if (i.get("current_price") or 0) >= min_price]
    if max_price is not None:
        items = [i for i in items if (i.get("current_price") or 0) <= max_price]
    if condition:
        items = [i for i in items if i.get("condition") == condition]

    # Re-sort if not default (cache is already sorted by ending_soon)
    if sort == "price":
        items = sorted(items, key=lambda x: x.get("current_price", 0))
    elif sort == "-price":
        items = sorted(items, key=lambda x: -x.get("current_price", 0))
    elif sort == "-promoted":
        # Legacy: featured/promoted first, then by creation date
        promo_w = {"premium": 3, "standard": 2, "basic": 1, None: 0}
        items = sorted(items, key=lambda x: (
            0 if x.get("is_featured") else 1,
            -promo_w.get(x.get("promotion_tier"), 0),
            -(x.get("created_at").timestamp() if isinstance(x.get("created_at"), datetime) else 0),
        ))
    elif sort == "newest":
        items = sorted(items, key=lambda x: -(x.get("created_at").timestamp() if isinstance(x.get("created_at"), datetime) else 0))
    # "ending_soon" is the default — already sorted by cache builder

    total_items = len(items)

    # Cursor-based or offset pagination
    offset = skip
    if cursor:
        try:
            decoded = json.loads(base64.b64decode(cursor))
            offset = decoded.get("offset", 0)
        except Exception:
            offset = skip

    paginated_items = items[offset:offset + limit]
    has_more = (offset + limit) < total_items

    next_cursor = None
    if has_more:
        next_cursor = base64.b64encode(json.dumps({"offset": offset + limit}).encode()).decode()

    return {
        "items": paginated_items,
        "total": total_items,
        "limit": limit,
        "skip": offset,
        "has_more": has_more,
        "next_cursor": next_cursor,
    }


# ========== CLICK TRACKING ==========

@marketplace_router.post("/marketplace/items/{item_id}/track-click")
async def track_item_click(item_id: str):
    """Track clicks on marketplace items for promoted listings analytics"""
    db = get_db()
    if "_lot" not in item_id:
        return {"success": False, "message": "Invalid item ID"}
    
    auction_id = item_id.split("_lot")[0]
    await db.multi_item_listings.update_one(
        {"id": auction_id, "is_promoted": True},
        {"$inc": {"total_clicks": 1}}
    )
    return {"success": True}


# ========== LOCATION SEARCH ==========

@marketplace_router.post("/listings/search/location")
async def search_by_location(params: LocationSearchParams):
    db = get_db()
    query = {"status": "active"}
    
    if params.category:
        query["category"] = params.category
    if params.min_price is not None:
        query["current_price"] = {"$gte": params.min_price}
    if params.max_price is not None:
        if "current_price" in query:
            query["current_price"]["$lte"] = params.max_price
        else:
            query["current_price"] = {"$lte": params.max_price}
    
    if params.latitude and params.longitude:
        radius_in_radians = params.radius_km / 6371.0
        query["$or"] = [
            {
                "latitude": {
                    "$gte": params.latitude - radius_in_radians * 57.2958,
                    "$lte": params.latitude + radius_in_radians * 57.2958
                },
                "longitude": {
                    "$gte": params.longitude - radius_in_radians * 57.2958,
                    "$lte": params.longitude + radius_in_radians * 57.2958
                }
            },
            {"latitude": None}
        ]
    
    listings = await db.listings.find(query, {"_id": 0}).limit(50).to_list(50)
    
    for listing in listings:
        if isinstance(listing.get("created_at"), str):
            listing["created_at"] = datetime.fromisoformat(listing["created_at"])
        if isinstance(listing.get("auction_end_date"), str):
            listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
    
    return listings


# ========== FILTER COUNTS ==========

async def _refresh_filter_counts():
    """Background task: recompute filter counts and store in Redis."""
    global _refreshing_filters
    try:
        db = get_db()

        # Auctioneer counts
        auctioneer_pipeline = [
            {"$match": {"status": "active", "is_partner_listing": True}},
            {"$group": {"_id": "$seller_id", "count": {"$sum": 1}}},
        ]
        auctioneer_results = await db.listings.aggregate(auctioneer_pipeline).to_list(100)

        auctioneers = []
        for a in auctioneer_results:
            seller = await db.users.find_one(
                {"id": a["_id"], "is_partner": True},
                {"_id": 0, "partner_company_name": 1, "id": 1}
            )
            if seller and seller.get("partner_company_name"):
                auctioneers.append({
                    "id": seller["id"],
                    "name": seller["partner_company_name"],
                    "count": a["count"],
                })

        # Category counts (single + multi combined)
        cat_pipeline = [
            {"$match": {"status": "active"}},
            {"$group": {"_id": "$category", "count": {"$sum": 1}}},
            {"$sort": {"count": -1}},
        ]
        category_results = await db.listings.aggregate(cat_pipeline).to_list(100)
        categories = [{"name": c["_id"], "count": c["count"]} for c in category_results if c["_id"]]

        multi_cat_results = await db.multi_item_listings.aggregate(cat_pipeline).to_list(100)
        for mc in multi_cat_results:
            if mc["_id"]:
                existing = next((c for c in categories if c["name"] == mc["_id"]), None)
                if existing:
                    existing["count"] += mc["count"]
                else:
                    categories.append({"name": mc["_id"], "count": mc["count"]})
        categories.sort(key=lambda x: x["count"], reverse=True)

        # Location counts
        loc_pipeline = [
            {"$match": {"status": "active", "region": {"$ne": None}}},
            {"$group": {"_id": {"region": "$region", "city": "$city"}, "count": {"$sum": 1}}},
        ]
        loc_results = await db.listings.aggregate(loc_pipeline).to_list(200)

        regions = {}
        for loc in loc_results:
            region = loc["_id"].get("region", "Other")
            city = loc["_id"].get("city")
            if region not in regions:
                regions[region] = {"count": 0, "cities": {}}
            regions[region]["count"] += loc["count"]
            if city:
                regions[region]["cities"][city] = regions[region]["cities"].get(city, 0) + loc["count"]

        locations = [
            {"region": r, "count": data["count"], "cities": [{"name": c, "count": cnt} for c, cnt in data["cities"].items()]}
            for r, data in sorted(regions.items(), key=lambda x: x[1]["count"], reverse=True)
        ]

        total_active = await db.listings.count_documents({"status": "active"})

        result = {
            "auctioneers": auctioneers,
            "categories": categories,
            "locations": locations,
            "total_active_items": total_active,
        }

        await cache_set(f"{FILTER_COUNTS_NS}all", result, FILTER_TTL)
        logger.info("Filter counts cache refreshed")

    except Exception as e:
        logger.error(f"Background filter-counts refresh failed: {e}")
    finally:
        _refreshing_filters = False


@marketplace_router.get("/marketplace/filter-counts")
async def marketplace_filter_counts():
    """
    Dynamic filter counts for marketplace sidebar.
    Stale-While-Revalidate: serves cached data instantly
    and refreshes in the background when stale.
    """
    global _refreshing_filters

    cached = await cache_get(f"{FILTER_COUNTS_NS}all")

    # FRESH — return immediately (Redis TTL handles staleness)
    if cached:
        if not _refreshing_filters:
            _refreshing_filters = True
            asyncio.ensure_future(_refresh_filter_counts())
        return cached

    # COLD (first request ever) — must wait for data
    await _refresh_filter_counts()
    result = await cache_get(f"{FILTER_COUNTS_NS}all")
    return result or {"auctioneers": [], "categories": [], "locations": [], "total_active_items": 0}


# ========== PROMOTED LISTINGS ==========

@marketplace_router.get("/promoted-listings")
async def get_promoted_listings(limit: int = 12, tier: Optional[str] = None):
    """Get promoted listings for homepage Hot Items carousel"""
    db = get_db()
    now = datetime.now(timezone.utc)
    
    query = {
        "status": {"$in": ["active", "upcoming"]},
        "is_promoted": True,
        "$or": [
            {"promotion_end": None},
            {"promotion_end": {"$gte": now.isoformat()}}
        ]
    }
    if tier:
        query["promotion_tier"] = tier
    
    sort_order = [
        ("promotion_tier", -1),
        ("promotion_start", -1)
    ]
    
    listings = await db.multi_item_listings.find(query, {"_id": 0}).sort(sort_order).limit(limit).to_list(limit)
    
    for listing in listings:
        seller = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0, "name": 1, "picture": 1})
        listing["seller_name"] = seller.get("name") if seller else "Unknown Seller"
        listing["seller_picture"] = seller.get("picture") if seller else None
        
        await db.multi_item_listings.update_one(
            {"id": listing["id"]},
            {"$inc": {"total_impressions": 1}}
        )
    
    return {"listings": listings, "total": len(listings)}
