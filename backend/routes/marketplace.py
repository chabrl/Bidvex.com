"""
BidVex Marketplace Router
Handles all marketplace browsing, searching, and filtering:
- Decomposed marketplace items (multi-item lots + single listings)
- Marketplace filter counts (auctioneers, categories, locations)
- Location-based search
- Promoted listings for homepage
- Click tracking for analytics
"""

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime, timezone, timedelta
from deps import get_current_user_optional, User
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

# iter217 Bug 10 — Province / city normalization for location filters.
# Frontend may send the full name ("Quebec"), the abbreviation ("QC"),
# or a localised variant; data may be stored either way.
_PROVINCE_ALIASES = {
    "qc": "qc", "quebec": "qc", "québec": "qc",
    "on": "on", "ontario": "on",
    "bc": "bc", "british columbia": "bc", "colombie-britannique": "bc",
    "ab": "ab", "alberta": "ab",
    "mb": "mb", "manitoba": "mb",
    "sk": "sk", "saskatchewan": "sk",
    "ns": "ns", "nova scotia": "ns", "nouvelle-écosse": "ns",
    "nb": "nb", "new brunswick": "nb", "nouveau-brunswick": "nb",
    "nl": "nl", "newfoundland and labrador": "nl", "newfoundland": "nl", "terre-neuve-et-labrador": "nl",
    "pe": "pe", "prince edward island": "pe", "île-du-prince-édouard": "pe",
    "yt": "yt", "yukon": "yt",
    "nt": "nt", "northwest territories": "nt", "territoires du nord-ouest": "nt",
    "nu": "nu", "nunavut": "nu",
}


def _normalize_region(v):
    if not v:
        return ""
    key = str(v).strip().lower()
    return _PROVINCE_ALIASES.get(key, key)


def _normalize_city(v):
    if not v:
        return ""
    return str(v).strip().lower().replace("é", "e").replace("è", "e").replace("ê", "e")


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
    # Seller-type pricing/badge/geo-sort fields (iteration 165 spec)
    "seller_type": 1, "partner_bp_rate": 1,
    "seller_province": 1, "seller_city": 1,
    # iter217 Phase 4 — BP fields needed for partner card display
    "buyer_premium_rate": 1, "premium_percentage": 1,
    "custom_buyer_premium_rate": 1, "buyers_premium_percent": 1,
    # iter283 — Section routing so marketplace cards can show
    # "Storage / Vehicles / Lots" badges.
    "listing_type": 1, "section": 1,
}
_MULTI_PROJECTION = {
    "_id": 0, "id": 1, "title": 1, "description": 1, "category": 1,
    "lots": 1, "auction_end_date": 1, "auction_start_date": 1,
    "status": 1, "seller_id": 1, "is_promoted": 1, "promotion_tier": 1,
    "is_featured": 1, "is_partner_listing": 1, "city": 1, "region": 1, "country": 1,
    "created_at": 1,
    "title_en": 1, "title_fr": 1, "description_en": 1, "description_fr": 1,
    # Seller-type pricing/badge/geo-sort fields (iteration 165 spec)
    "seller_type": 1, "partner_bp_rate": 1,
    "seller_province": 1, "seller_city": 1,
    # iter217 Phase 4 — BP fields needed for partner card display
    "buyer_premium_rate": 1, "premium_percentage": 1,
    "custom_buyer_premium_rate": 1, "buyers_premium_percent": 1,
    # iter283 — Section routing.
    "listing_type": 1, "section": 1,
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
    # Exclude vehicles from general marketplace (they have their own dedicated page)
    VEHICLE_CATEGORIES = ["vehicles", "vehicle", "car", "auto", "automobile", "truck", "motorcycle"]
    
    auctions = await db.multi_item_listings.find(
        {"status": {"$in": ["active", "upcoming"]}, "category": {"$nin": VEHICLE_CATEGORIES}, "is_demo": {"$ne": True}, "is_demo_sandbox": {"$ne": True}}, _MULTI_PROJECTION
    ).sort("auction_end_date", 1).limit(500).to_list(500)

    single_listings = await db.listings.find(
        {
            "status": "active",
            "category": {"$nin": VEHICLE_CATEGORIES},
            # iter283 — Marketplace now shows ALL listing types
            # (storage / vehicles / lots / marketplace). Section pages
            # add their own filter. Section badges on the cards help
            # buyers distinguish. Per the spec: "every listing must
            # appear in the Marketplace AND in its specific section".
            "is_demo": {"$ne": True},
            "is_demo_sandbox": {"$ne": True},
        },
        _LISTING_PROJECTION,
    ).sort("auction_end_date", 1).limit(500).to_list(500)

    # iter217 Phase 4 — Batch-fetch FULL seller record so we can compute
    # `seller_account_type` (Partner / Vehicle Dealer / Storage / Individual)
    # for the cached marketplace items. The previous version only fetched
    # `is_tax_registered` → all partner listings rendered as "Vente privée".
    all_seller_ids = list(set(
        [a.get("seller_id") for a in auctions if a.get("seller_id")] +
        [sl.get("seller_id") for sl in single_listings if sl.get("seller_id")]
    ))
    sellers_full = {}
    sellers = {}
    if all_seller_ids:
        seller_docs = await db.users.find(
            {"id": {"$in": all_seller_ids}},
            {
                "_id": 0,
                "id": 1,
                "is_tax_registered": 1,
                "is_partner": 1,
                "partner_verification_status": 1,
                "partner_company_name": 1,
                "partner_buyer_premium_pct": 1,
                "is_vehicle_dealer": 1,
                "is_storage_facility": 1,
                "account_type": 1,
                "platform_fee_paid": 1,
                "partner_subscription_active": 1,
                "is_top_seller": 1,
            }
        ).to_list(len(all_seller_ids))
        sellers_full = {s["id"]: s for s in seller_docs}
        sellers = {s["id"]: s.get("is_tax_registered", False) for s in seller_docs}

    from services.listing_seller_enrichment import (
        resolve_seller_account_type, _coerce_rate_to_fraction,
    )

    def _enrich_seller_fields(target_doc, source_listing, context="general"):
        """Mutates target_doc to include seller_* enrichment fields."""
        seller = sellers_full.get(source_listing.get("seller_id"), {})
        acct = resolve_seller_account_type(seller, context)
        target_doc["seller_account_type"] = acct
        target_doc["seller_is_top_seller"] = bool(seller.get("is_top_seller"))
        target_doc["seller_is_partner"] = acct == "partner"
        target_doc["seller_is_vehicle_dealer"] = acct == "vehicle_dealer"
        target_doc["seller_is_storage_facility"] = acct == "storage_facility"
        target_doc["seller_is_business"] = bool(
            seller.get("is_tax_registered")
            or acct in ("partner", "vehicle_dealer", "storage_facility")
        )
        target_doc["seller_partner_company_name"] = (
            seller.get("partner_company_name") if acct == "partner" else None
        )
        # Canonical buyer's premium rate (fraction)
        rate = (
            _coerce_rate_to_fraction(source_listing.get("buyer_premium_rate"))
            or _coerce_rate_to_fraction(source_listing.get("custom_buyer_premium_rate"))
            or _coerce_rate_to_fraction(source_listing.get("premium_percentage"))
            or _coerce_rate_to_fraction(source_listing.get("buyers_premium_percent"))
            or _coerce_rate_to_fraction(source_listing.get("partner_bp_rate"))
        )
        if rate is None and acct == "partner":
            rate = _coerce_rate_to_fraction(seller.get("partner_buyer_premium_pct"))
        target_doc["buyer_premium_rate"] = rate

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

            item_doc = {
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
                "seller_type": auction.get("seller_type", "individual"),
                "partner_bp_rate": auction.get("partner_bp_rate"),
                "seller_province": auction.get("seller_province") or auction.get("region"),
                "seller_city": auction.get("seller_city") or auction.get("city"),
                "city": auction.get("city"),
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
            }
            # iter217 Phase 4 — surface seller_account_type + canonical BP.
            # The lot inherits the parent auction's BP fields via `auction`.
            _enrich_seller_fields(item_doc, auction, "general")
            items.append(item_doc)

    for listing in single_listings:
        current_price = listing.get("current_price", listing.get("starting_price", 0))
        single_doc = {
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
            "seller_type": listing.get("seller_type", "individual"),
            "partner_bp_rate": listing.get("partner_bp_rate"),
            "seller_province": listing.get("seller_province") or listing.get("region"),
            "seller_city": listing.get("seller_city") or listing.get("city"),
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
            # iter283 — Section routing badge on marketplace cards.
            "listing_type": listing.get("listing_type"),
            "section": listing.get("section"),
        }
        # iter217 Phase 4 — surface seller_account_type + canonical BP.
        # iter283 — Use per-listing inferred context so a multi-flagged
        # seller's storage row shows a storage badge.
        from services.listing_sections import infer_seller_context
        _enrich_seller_fields(single_doc, listing, infer_seller_context(listing))
        items.append(single_doc)

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
    categories: Optional[str] = None,
    region: Optional[str] = None,
    regions: Optional[str] = None,
    city: Optional[str] = None,
    cities: Optional[str] = None,
    seller_id: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    condition: Optional[str] = None,
    zero_fee_only: Optional[str] = None,
    province: Optional[str] = None,
    no_taxes: Optional[str] = None,
    tax_status: Optional[str] = None,        # "partner" | "standard"
    private_sales_only: Optional[str] = None,  # iter217 Phase 4
    partner_only: Optional[str] = None,        # iter217 Phase 4
    lots_auction_only: Optional[str] = None,   # iter217 Phase 4 — items from multi-lot auctions
    ending_soon: Optional[str] = None,         # iter298 BUG 1 — active items ending within 24h (dynamic)
    buyer_province: Optional[str] = None,    # for "nearby_first" geo-sort
    sort: str = "nearby_first",
    limit: int = Query(20, ge=1, le=100),
    skip: int = Query(0, ge=0),
    cursor: Optional[str] = None,
    track_impression: bool = False,
    # iter223 — Owner-self-include for demo sandbox. When the requester is a
    # demo account, their own `is_demo_sandbox` listings are tail-merged
    # into the cached public feed so they can see their creations inside
    # the real product surfaces.
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    """
    Marketplace view: Redis-cached, paginated, with stale-while-revalidate.
    Cold cache returns empty list with loading=True flag.
    """
    global _refreshing_items

    cached_items = await cache_get(f"{MARKETPLACE_ITEMS_NS}all")

    # iter220 Task 1 — Hydration Ghost Fix.
    # OLD behaviour: cold cache returned `{items:[], total:0, cache_warming:true}`
    # — the buyer saw an empty grid until React Query retried 2s later. On
    # production this caused the "5 items in counter / 0 in grid" ghost-load
    # bug because counters use a separate endpoint that doesn't share the
    # same cache key.
    # NEW behaviour: on cold cache we BUILD INLINE (with a 5s ceiling),
    # serve the result this request, and only fall back to the warming
    # response if the build itself fails or times out. This adds ~200-500ms
    # latency on the very first request after a Redis flush, but eliminates
    # the empty-grid hydration race entirely.
    if cached_items is None:
        try:
            cached_items = await asyncio.wait_for(_build_marketplace_items(), timeout=5.0)
            try:
                await cache_set(f"{MARKETPLACE_ITEMS_NS}all", cached_items, ITEMS_TTL)
            except Exception as cache_err:
                logger.warning(f"[cache] inline-build cache_set failed: {cache_err}")
            _refreshing_items = False
        except (asyncio.TimeoutError, Exception) as inline_err:
            logger.warning(f"[cache] inline build failed/slow, falling back to async: {inline_err}")
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

    # iter223 — Demo sandbox owner-self-include. When the requester is a demo
    # account, tail-merge their own `is_demo_sandbox=true` listings so they
    # see their creations inside the real marketplace frame. The PUBLIC cache
    # never contains these; we fetch them on-demand from MongoDB.
    if current_user is not None:
        try:
            _db = get_db()
            _user = await _db.users.find_one(
                {"id": current_user.id},
                {"_id": 0, "is_demo_account": 1},
            )
            if _user and _user.get("is_demo_account"):
                own_sandbox = await _db.listings.find(
                    {
                        "status": "active",
                        "seller_id": current_user.id,
                        "is_demo_sandbox": True,
                        # iter283 — sandbox owner sees ALL their own listings
                        # (including storage) in marketplace per dual-visibility.
                    },
                    _LISTING_PROJECTION,
                ).sort("auction_end_date", 1).limit(100).to_list(100)
                # Mark each so the FE can render a "SANDBOX" pill.
                for s in own_sandbox:
                    s["is_demo_sandbox"] = True
                # Avoid dupes (paranoia — public cache should never contain these).
                existing_ids = {i.get("id") for i in items}
                items = list(items) + [s for s in own_sandbox if s.get("id") not in existing_ids]
        except Exception as e:
            logger.warning(f"[demo-sandbox] owner-self-include failed: {e}")

    if search:
        s_lower = search.lower()
        items = [i for i in items if s_lower in (i.get("title") or "").lower()
                 or s_lower in (i.get("description") or "").lower()]
    if category:
        c_norm = (category or "").strip().casefold()
        items = [i for i in items if (i.get("category") or "").strip().casefold() == c_norm]
    if categories:
        cat_list = [c.strip().casefold() for c in categories.split(",") if c.strip()]
        if cat_list:
            items = [i for i in items if (i.get("category") or "").strip().casefold() in cat_list]
    if region or regions:
        region_list = []
        if region:
            region_list.append(region)
        if regions:
            region_list.extend([r.strip() for r in regions.split(",") if r.strip()])
        if region_list:
            # iter217 — case-insensitive + trim; also accept synonyms ("Quebec"/"QC").
            norm_set = {_normalize_region(r) for r in region_list if r}
            items = [i for i in items if _normalize_region(i.get("region") or i.get("province")) in norm_set]
    if city or cities:
        city_list = []
        if city:
            city_list.append(city)
        if cities:
            city_list.extend([c.strip() for c in cities.split(",") if c.strip()])
        if city_list:
            norm_cities = {_normalize_city(c) for c in city_list if c}
            items = [i for i in items if _normalize_city(i.get("city")) in norm_cities
                     or any(_normalize_city(c) in _normalize_city(i.get("location") or "") for c in city_list)]
    if seller_id:
        seller_ids = [s.strip() for s in seller_id.split(",") if s.strip()]
        items = [i for i in items if i.get("seller_id") in seller_ids]
    if zero_fee_only and zero_fee_only.lower() == 'true':
        items = [i for i in items if i.get("is_opc_certified") and i.get("buyers_premium_percent", 99) == 0]
    if min_price is not None:
        items = [i for i in items if (i.get("current_price") or 0) >= min_price]
    if max_price is not None:
        items = [i for i in items if (i.get("current_price") or 0) <= max_price]
    if condition:
        items = [i for i in items if i.get("condition") == condition]
    if province:
        norm_prov = _normalize_region(province)
        items = [i for i in items if _normalize_region(i.get("region") or i.get("province")) == norm_prov]
    if no_taxes and no_taxes.lower() == 'true':
        # iter217 Phase 4 — "No Taxes" pill = TRUE private sales only.
        items = [i for i in items if i.get("seller_account_type") == "individual"]

    # iter220 Task 1 — Hide auctions that have already passed their end_time.
    # Cron status-flip runs every 60s; this defensive in-memory filter ensures
    # buyers never see expired auctions even in the worst-case 60s lag window.
    # Listings remain visible 100% of the time until end_time elapses, exactly
    # per directive: "Listings remain visible until end_time countdown <= 0."
    _now_iso = datetime.now(timezone.utc).isoformat()
    items = [
        i for i in items
        if not i.get("auction_end_date")
        or str(i.get("auction_end_date")) > _now_iso
    ]

    # iter217 Phase 4 — Private sales pill
    if private_sales_only and str(private_sales_only).lower() == 'true':
        items = [i for i in items if i.get("seller_account_type") == "individual"]

    # iter217 Phase 4 — Partner Auctions pill
    if partner_only and str(partner_only).lower() == 'true':
        items = [i for i in items if i.get("seller_account_type") == "partner"]

    # iter217 Phase 4 — Lot Auction pill (only items that come from multi-lot auctions)
    if lots_auction_only and str(lots_auction_only).lower() == 'true':
        items = [i for i in items if i.get("auction_id")]

    # iter298 BUG 1 — "Ending Soon" filter, computed DYNAMICALLY at
    # query time from `auction_end_date` (never a scheduler flag):
    # active listings ending within the next 24 hours.
    if ending_soon and str(ending_soon).lower() == 'true':
        _es_cutoff = (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat()
        items = [
            i for i in items
            if i.get("auction_end_date")
            and _now_iso < str(i.get("auction_end_date")) <= _es_cutoff
        ]
        # Soonest-ending first.
        items = sorted(items, key=lambda x: str(x.get("auction_end_date") or ""))

    # ── Tax Status filter (partner vs standard listings) ──
    if tax_status == "partner":
        items = [i for i in items if i.get("seller_account_type") == "partner"]
    elif tax_status == "standard":
        items = [i for i in items if i.get("seller_account_type") in ("individual", "vehicle_dealer")]

    # Re-sort if not default (cache is already sorted by ending_soon)
    if sort == "nearby_first":
        from services.geo_sort import geo_priority_value
        items = sorted(items, key=lambda x: (
            geo_priority_value(x.get("seller_province") or x.get("region"), buyer_province or ""),
            -(x.get("created_at").timestamp() if isinstance(x.get("created_at"), datetime) else 0),
        ))
    elif sort == "price":
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
    elif sort == "most_bids":
        items = sorted(items, key=lambda x: -(x.get("bid_count", 0) or 0))
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
        # iter301 P2 — spec-compliant aliases (total_count + page) alongside
        # the legacy keys so existing consumers don't break.
        "total_count": total_items,
        "page": (offset // limit) + 1 if limit else 1,
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
    # iter211 P4 — exclude demo listings from public location search.
    # iter283 — Marketplace location search includes storage + vehicle
    # listings (universal dual-visibility).
    query = {
        "status": "active",
        "is_demo": {"$ne": True},
    }
    
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

        # Category counts (single + multi combined) — exclude vehicles (they have their own page)
        VEHICLE_CATEGORIES = ["vehicles", "vehicle", "car", "auto", "automobile", "truck", "motorcycle"]
        cat_pipeline = [
            {"$match": {"status": "active", "category": {"$nin": VEHICLE_CATEGORIES}}},
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

        total_active = await db.listings.count_documents({"status": "active", "category": {"$nin": VEHICLE_CATEGORIES}})

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
# iter239 — Legacy `/promoted-listings` endpoint moved to
# `routes/promotions.py` with the new section-scoped semantics
# (`?section=marketplace|lots|storage|vehicles|homepage`). The legacy
# multi_item_listings-only handler was removed here to resolve a routing
# collision; tests that asserted a 200 still pass because the new endpoint
# answers on the same path with a richer shape (`{items, total, section}`).

