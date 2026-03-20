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
import asyncio
import time
import logging
import base64
import json

logger = logging.getLogger(__name__)

marketplace_router = APIRouter(tags=["Marketplace"])

_db = None


def set_marketplace_db(db_instance):
    """Set database instance"""
    global _db
    _db = db_instance


def get_db():
    if _db is None:
        raise RuntimeError("Marketplace database not initialized")
    return _db


# ========== STALE-WHILE-REVALIDATE CACHE (5-min TTL) ==========
_filter_counts_cache = {
    "data": None,
    "fresh_until": 0,       # epoch — data is considered fresh until this time
    "refreshing": False,    # guard to prevent concurrent refresh tasks
}
_CACHE_TTL = 300  # 5 minutes


class LocationSearchParams(BaseModel):
    latitude: float
    longitude: float
    radius_km: float = 50.0
    category: Optional[str] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None


# ========== MARKETPLACE ITEMS ==========

@marketplace_router.get("/marketplace/items")
async def get_marketplace_items(
    search: Optional[str] = None,
    category: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    condition: Optional[str] = None,
    sort: str = "-promoted",
    limit: int = 50,
    skip: int = 0,
    cursor: Optional[str] = None,
    track_impression: bool = False
):
    """
    Decomposed marketplace view: Returns individual items from multi-item lots.
    Features:
    - Item-centric discovery (not lot-centric)
    - Promoted items appear first
    - Each item has individual Buy Now price, bid, and staggered end time
    - Tracks impressions for promoted items
    """
    db = get_db()
    
    # Query active multi-item auctions
    query = {"status": "active"}
    if category:
        query["category"] = category
    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    
    auctions = await db.multi_item_listings.find(query, {"_id": 0}).to_list(None)
    
    # Fetch single listings
    single_query = {"status": "active"}
    if category:
        single_query["category"] = category
    if search:
        single_query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]
    
    single_listings = await db.listings.find(single_query, {"_id": 0}).to_list(None)
    
    # Cache seller tax status
    seller_tax_cache = {}
    
    items = []
    
    for auction in auctions:
        seller_id = auction.get("seller_id")
        if seller_id not in seller_tax_cache:
            seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "is_tax_registered": 1})
            seller_tax_cache[seller_id] = seller.get("is_tax_registered", False) if seller else False
        
        seller_is_business = seller_tax_cache[seller_id]
        
        if auction.get("is_promoted") and track_impression:
            await db.multi_item_listings.update_one(
                {"id": auction["id"]},
                {"$inc": {"total_impressions": 1}}
            )
        
        for lot in auction.get("lots", []):
            if lot.get("lot_status") == "sold_out":
                continue
            
            current_price = lot.get("current_price", lot.get("starting_price", 0))
            if min_price is not None and current_price < min_price:
                continue
            if max_price is not None and current_price > max_price:
                continue
            if condition and lot.get("condition") != condition:
                continue
            
            base_end_time = auction.get("auction_end_date")
            if isinstance(base_end_time, str):
                base_end_time = datetime.fromisoformat(base_end_time)
            
            lot_end_time = lot.get("lot_end_time")
            if not lot_end_time and base_end_time:
                stagger_seconds = lot["lot_number"] * 60
                lot_end_time = base_end_time + timedelta(seconds=stagger_seconds)
            elif isinstance(lot_end_time, str):
                lot_end_time = datetime.fromisoformat(lot_end_time)
            
            item = {
                "id": f"{auction['id']}_lot{lot['lot_number']}",
                "auction_id": auction["id"],
                "lot_number": lot["lot_number"],
                "title": lot["title"],
                "description": lot["description"],
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
                "created_at": auction.get("created_at")
            }
            items.append(item)
    
    # Add single listings
    for listing in single_listings:
        current_price = listing.get("current_price", listing.get("starting_price", 0))
        if min_price is not None and current_price < min_price:
            continue
        if max_price is not None and current_price > max_price:
            continue
        if condition and listing.get("condition") != condition:
            continue
        
        seller_id = listing.get("seller_id")
        if seller_id not in seller_tax_cache:
            seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "is_tax_registered": 1})
            seller_tax_cache[seller_id] = seller.get("is_tax_registered", False) if seller else False
        
        seller_is_business = seller_tax_cache[seller_id]
        
        item = {
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
            "seller_is_business": seller_is_business,
            "is_partner_listing": listing.get("is_partner_listing", False),
            "city": listing.get("city"),
            "region": listing.get("region"),
            "country": listing.get("country"),
            "created_at": listing.get("created_at")
        }
        items.append(item)
    
    # Sorting
    now = datetime.now(timezone.utc)
    
    if sort == "-promoted":
        promotion_weight = {"premium": 3, "standard": 2, "basic": 1, None: 0}
        
        def get_urgency_score(item):
            if item.get("auction_end_date"):
                end_time = datetime.fromisoformat(item["auction_end_date"].replace("Z", "+00:00")) if isinstance(item["auction_end_date"], str) else item["auction_end_date"]
                if end_time.tzinfo is None:
                    end_time = end_time.replace(tzinfo=timezone.utc)
                time_remaining = (end_time - now).total_seconds()
                if 0 < time_remaining <= 3600:
                    return 1000 - time_remaining
            return 0
        
        items.sort(
            key=lambda x: (
                -1 if x.get("is_featured") else 0,
                -get_urgency_score(x),
                -promotion_weight.get(x.get("promotion_tier"), 0),
                -(x.get("created_at").timestamp() if isinstance(x.get("created_at"), datetime) else 0)
            )
        )
    elif sort == "price":
        items.sort(key=lambda x: x.get("current_price", 0))
    elif sort == "-price":
        items.sort(key=lambda x: -x.get("current_price", 0))
    elif sort == "ending_soon":
        items.sort(
            key=lambda x: (
                0 if x.get("is_featured") else 1,
                datetime.fromisoformat(x["auction_end_date"].replace("Z", "+00:00")) if x.get("auction_end_date") else datetime.max
            )
        )
    else:
        items.sort(
            key=lambda x: -(x.get("created_at").timestamp() if isinstance(x.get("created_at"), datetime) else 0)
        )
    
    total_items = len(items)
    
    # Cursor-based pagination: decode cursor to get offset, or use skip
    offset = skip
    if cursor:
        try:
            decoded = json.loads(base64.b64decode(cursor))
            offset = decoded.get("offset", 0)
        except Exception:
            offset = skip
    
    paginated_items = items[offset:offset + limit]
    has_more = (offset + limit) < total_items
    
    # Build next_cursor
    next_cursor = None
    if has_more:
        cursor_data = {"offset": offset + limit}
        next_cursor = base64.b64encode(json.dumps(cursor_data).encode()).decode()
    
    return {
        "items": paginated_items,
        "total": total_items,
        "limit": limit,
        "skip": offset,
        "has_more": has_more,
        "next_cursor": next_cursor
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
    """Background task: recompute filter counts and update the cache."""
    global _filter_counts_cache
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

        _filter_counts_cache["data"] = result
        _filter_counts_cache["fresh_until"] = time.time() + _CACHE_TTL
        logger.info("Filter counts cache refreshed")

    except Exception as e:
        logger.error(f"Background filter-counts refresh failed: {e}")
    finally:
        _filter_counts_cache["refreshing"] = False


@marketplace_router.get("/marketplace/filter-counts")
async def marketplace_filter_counts():
    """
    Dynamic filter counts for marketplace sidebar.
    Stale-While-Revalidate: serves cached data instantly
    and refreshes in the background when stale.
    """
    now = time.time()
    cache = _filter_counts_cache

    # FRESH — return immediately
    if cache["data"] and cache["fresh_until"] > now:
        return cache["data"]

    # STALE — return stale data, kick off background refresh
    if cache["data"]:
        if not cache["refreshing"]:
            cache["refreshing"] = True
            asyncio.ensure_future(_refresh_filter_counts())
        return cache["data"]

    # COLD (first request ever) — must wait for data
    await _refresh_filter_counts()
    return cache["data"] or {"auctioneers": [], "categories": [], "locations": [], "total_active_items": 0}


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
