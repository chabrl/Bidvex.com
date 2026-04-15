"""
BidVex Listings Router
Handles all listing CRUD operations for both single-item and multi-item auctions,
including terms management and deletion requests.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from deps import User, get_current_user
import logging
import uuid

from models import (
    Listing, ListingCreate,
    MultiItemListing, MultiItemListingCreate,
)
from utils import (
    get_marketplace_settings,
    detect_currency_from_location,
    get_tax_rates_for_currency,
)

logger = logging.getLogger(__name__)


async def _translate_listing_bg(db, listing_id: str, title: str, description: str, source_lang: str = "en"):
    """Background task: translate listing fields and update DB."""
    try:
        from services.translation_service import translate_listing_fields
        fields = await translate_listing_fields(title, description, source_lang)
        await db.listings.update_one({"id": listing_id}, {"$set": fields})
        logger.info(f"[i18n] Translated single listing {listing_id}")
        from services.api_cache import invalidate_listing_caches
        invalidate_listing_caches()
    except Exception as e:
        logger.error(f"[i18n] Background translation failed for listing {listing_id}: {e}")


async def _translate_multi_listing_bg(db, listing_id: str, title: str, description: str, lots: list, source_lang: str = "en"):
    """Background task: translate multi-item listing + lots fields and update DB."""
    try:
        from services.translation_service import translate_listing_fields, translate_lot_fields
        fields = await translate_listing_fields(title, description, source_lang)

        if lots:
            translated_lots = await translate_lot_fields(
                [{"title": l.get("title", ""), "description": l.get("description", "")} for l in lots],
                source_lang,
            )
            for i, tl in enumerate(translated_lots):
                for key in ["title_en", "title_fr", "description_en", "description_fr"]:
                    if key in tl:
                        fields[f"lots.{i}.{key}"] = tl[key]

        await db.multi_item_listings.update_one({"id": listing_id}, {"$set": fields})
        logger.info(f"[i18n] Translated multi listing {listing_id} ({len(lots)} lots)")
        from services.api_cache import invalidate_listing_caches
        invalidate_listing_caches()
    except Exception as e:
        logger.error(f"[i18n] Background translation failed for multi-listing {listing_id}: {e}")

listings_router = APIRouter(tags=["Listings"])

# Database instance — injected from server.py at startup
_db = None
_db_read = None


def set_listings_db(db_instance):
    global _db
    _db = db_instance


def set_listings_read_db(db_instance):
    global _db_read
    _db_read = db_instance


def get_db():
    if _db is None:
        raise RuntimeError("Listings DB not initialised")
    return _db


def get_read_db():
    return _db_read if _db_read is not None else _db


# ── Multi-item listings cache (30s TTL) ──
import time as _time
_multi_cache = {"data": None, "ts": 0, "ttl": 30}

# ── Single listing cache (30s TTL) ──
_listing_cache = {}
_LISTING_CACHE_TTL = 30


# ========== SINGLE-ITEM LISTINGS ==========

@listings_router.get("/sellers/{seller_id}/listings")
async def get_seller_listings(seller_id: str, limit: int = 20, skip: int = 0):
    """Get active listings for a specific seller (both single-item and multi-lot auctions)."""
    db = get_db()
    try:
        single_listings = await db.listings.find(
            {"seller_id": seller_id, "status": "active"},
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

        multi_listings = await db.multi_item_listings.find(
            {"seller_id": seller_id, "status": {"$in": ["active", "upcoming"]}},
            {"_id": 0}
        ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)

        for listing in single_listings:
            if isinstance(listing.get("created_at"), str):
                listing["created_at"] = datetime.fromisoformat(listing["created_at"])
            if isinstance(listing.get("auction_end_date"), str):
                listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])

        for listing in multi_listings:
            if isinstance(listing.get("created_at"), str):
                listing["created_at"] = datetime.fromisoformat(listing["created_at"])
            if isinstance(listing.get("auction_end_date"), str):
                listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
            if isinstance(listing.get("auction_start_date"), str):
                listing["auction_start_date"] = datetime.fromisoformat(listing["auction_start_date"])

        return {
            "single_listings": single_listings,
            "multi_listings": multi_listings,
            "total": len(single_listings) + len(multi_listings)
        }
    except Exception as e:
        logger.error(f"Error fetching seller listings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch seller listings")


@listings_router.post("/listings", response_model=Listing)
async def create_listing(
    listing_data: ListingCreate,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    from services.listings_service import (
        validate_seller, build_agreement_metadata, apply_partner_tags, persist_listing,
    )
    db = get_db()

    await validate_seller(db, current_user, listing_data.agreement_accepted)

    # Category restriction: OPC-verified dealers only for vehicle listings
    if listing_data.category and listing_data.category.lower() in ["vehicle", "vehicles", "vehicle parts", "road_vehicles"]:
        user_id = getattr(current_user, 'id', None)
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "seller_type": 1, "opc_permit_verified": 1})
        seller_type = (user_doc or {}).get("seller_type", "individual")
        opc_verified = (user_doc or {}).get("opc_permit_verified", False)
        
        if seller_type == "individual" or not opc_verified:
            # Log blocked attempt
            await db.audit_logs.insert_one({
                "action": "vehicle_listing_blocked",
                "user_id": user_id,
                "category": listing_data.category,
                "seller_type": seller_type,
                "opc_permit_verified": opc_verified,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            raise HTTPException(
                status_code=403,
                detail=(
                    "Vehicle listings require a verified OPC permit. Individual sellers are not permitted to list road vehicles on BidVex. "
                    "/ Les annonces de véhicules nécessitent un permis OPC vérifié. Les vendeurs individuels ne sont pas autorisés à lister des véhicules routiers sur BidVex."
                )
            )

    client_ip = request.client.host if request else "unknown"
    user_agent = request.headers.get("user-agent", "unknown") if request else "unknown"
    agreement_metadata = build_agreement_metadata(current_user, client_ip, user_agent)

    listing = Listing(
        seller_id=current_user.id, title=listing_data.title, description=listing_data.description,
        category=listing_data.category, condition=listing_data.condition,
        starting_price=listing_data.starting_price, current_price=listing_data.starting_price,
        buy_now_price=listing_data.buy_now_price, images=listing_data.images,
        location=listing_data.location, city=listing_data.city, region=listing_data.region,
        country=listing_data.country, postal_code=listing_data.postal_code,
        latitude=listing_data.latitude, longitude=listing_data.longitude,
        auction_end_date=listing_data.auction_end_date,
        shipping_info=listing_data.shipping_info,
        visit_availability=listing_data.visit_availability,
        currency=listing_data.currency if listing_data.currency else detect_currency_from_location(
            city=listing_data.city, region=listing_data.region, country=listing_data.country
        ),
        title_en=listing_data.title_en,
        title_fr=listing_data.title_fr,
        description_en=listing_data.description_en,
        description_fr=listing_data.description_fr,
    )
    listing_dict = listing.model_dump()

    # OPC certification: check seller and apply BP to listing
    seller_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0, "is_opc_certified": 1})
    if seller_doc and seller_doc.get("is_opc_certified"):
        listing_dict["is_opc_certified"] = True
        # OPC sellers can set BP rate (0-25%), stored as percent on listing
        if listing_data.buyers_premium_rate is not None:
            listing_dict["buyers_premium_percent"] = min(listing_data.buyers_premium_rate * 100, 25)
        else:
            listing_dict["buyers_premium_percent"] = 0
    
    # Seller payment method preference
    if listing_data.payment_method:
        listing_dict["payment_method"] = listing_data.payment_method

    await apply_partner_tags(db, current_user, listing_dict, listing_data.buyers_premium_rate)
    result = await persist_listing(db, listing_dict, agreement_metadata)

    # Background translation — if _en/_fr not already provided
    if not listing_data.title_en or not listing_data.title_fr:
        import asyncio as _aio
        _aio.ensure_future(_translate_listing_bg(db, result["id"], listing_data.title, listing_data.description, listing_data.content_language or "en"))

    return result


@listings_router.get("/listings", response_model=List[Listing])
async def get_listings(
    category: Optional[str] = None, city: Optional[str] = None, region: Optional[str] = None,
    condition: Optional[str] = None, min_price: Optional[float] = None, max_price: Optional[float] = None,
    search: Optional[str] = None, sort: str = "created_at", limit: int = 50, skip: int = 0,
    currency: Optional[str] = None,
):
    db = get_db()
    query = {"status": "active"}
    if category:
        query["category"] = category
    if city:
        query["city"] = city
    if region:
        query["region"] = region
    if condition:
        query["condition"] = condition
    if currency:
        query["currency"] = currency
    if min_price is not None:
        query["current_price"] = {"$gte": min_price}
    if max_price is not None:
        if "current_price" in query:
            query["current_price"]["$lte"] = max_price
        else:
            query["current_price"] = {"$lte": max_price}
    if search:
        query["$or"] = [{"title": {"$regex": search, "$options": "i"}}, {"description": {"$regex": search, "$options": "i"}}]
    sort_order = -1 if sort.startswith("-") else 1
    sort_field = sort.lstrip("-")
    listings = await db.listings.find(query, {"_id": 0}).sort(sort_field, sort_order).skip(skip).limit(limit).to_list(limit)

    # Also include individual lots from multi-item listings as independent items
    multi_query = {"status": "active"}
    if category:
        multi_query["category"] = category
    if city:
        multi_query["city"] = city
    if region:
        multi_query["region"] = region
    if search:
        multi_query["$or"] = [{"title": {"$regex": search, "$options": "i"}}, {"description": {"$regex": search, "$options": "i"}}]

    multi_listings = await db.multi_item_listings.find(multi_query, {"_id": 0}).sort(sort_field, sort_order).limit(limit).to_list(limit)

    for ml in multi_listings:
        for lot in ml.get("lots", []):
            lot_listing = {
                "id": f"{ml['id']}_lot_{lot.get('lot_number', 0)}",
                "title": lot.get("title", ml.get("title", "")),
                "description": lot.get("description", ml.get("description", "")),
                "category": ml.get("category", ""),
                "condition": lot.get("condition", ml.get("condition", "used")),
                "starting_price": lot.get("starting_price", 0),
                "current_price": lot.get("current_bid", lot.get("starting_price", 0)),
                "images": lot.get("images", ml.get("images", [])),
                "seller_id": ml.get("seller_id", ""),
                "status": "active",
                "city": ml.get("city", ""),
                "region": ml.get("region", ""),
                "country": ml.get("country", "CA"),
                "currency": ml.get("currency", "CAD"),
                "auction_end_date": ml.get("end_time", ml.get("auction_end_date")),
                "created_at": ml.get("created_at"),
                "listing_type": "multi_lot",
                "parent_auction_id": ml["id"],
                "parent_auction_title": ml.get("title", ""),
                "lot_number": lot.get("lot_number", 0),
                "total_lots": len(ml.get("lots", [])),
                "badge_en": "Part of Auction",
                "badge_fr": "Partie d'une enchère",
                "views": ml.get("views", 0),
                "bids": lot.get("bid_count", 0),
            }
            # Apply price filters
            if min_price is not None and lot_listing["current_price"] < min_price:
                continue
            if max_price is not None and lot_listing["current_price"] > max_price:
                continue
            if condition and lot_listing["condition"] != condition:
                continue
            listings.append(lot_listing)

    # Sort combined results
    reverse = sort_order == -1
    listings.sort(key=lambda x: x.get(sort_field, ""), reverse=reverse)
    listings = listings[:limit]

    for listing in listings:
        if isinstance(listing.get("created_at"), str):
            listing["created_at"] = datetime.fromisoformat(listing["created_at"])
        if isinstance(listing.get("auction_end_date"), str):
            listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
    return [Listing(**listing) for listing in listings]


@listings_router.get("/listings/{listing_id}", response_model=Listing)
async def get_listing(listing_id: str):
    now = _time.time()
    cached = _listing_cache.get(listing_id)
    if cached and (now - cached["ts"]) < _LISTING_CACHE_TTL:
        return cached["data"]

    db = get_read_db()
    listing_doc = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing_doc:
        raise HTTPException(status_code=404, detail="Listing not found")
    # Increment views on the primary DB (write operation)
    await get_db().listings.update_one({"id": listing_id}, {"$inc": {"views": 1}})
    if isinstance(listing_doc.get("created_at"), str):
        listing_doc["created_at"] = datetime.fromisoformat(listing_doc["created_at"])
    if isinstance(listing_doc.get("auction_end_date"), str):
        listing_doc["auction_end_date"] = datetime.fromisoformat(listing_doc["auction_end_date"])
    result = Listing(**listing_doc)
    _listing_cache[listing_id] = {"data": result, "ts": now}
    return result


@listings_router.put("/listings/{listing_id}", response_model=Listing)
async def update_listing(listing_id: str, updates: Dict[str, Any], current_user: User = Depends(get_current_user)):
    db = get_db()
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    allowed_fields = ["title", "description", "category", "condition", "images", "location", "city", "region", "country", "postal_code", "status",
                      "title_en", "title_fr", "description_en", "description_fr"]
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}

    # If title or description changed but no explicit translations, re-translate
    needs_retranslation = ("title" in update_data or "description" in update_data) and not ("title_en" in update_data and "title_fr" in update_data)

    if update_data:
        await db.listings.update_one({"id": listing_id}, {"$set": update_data})
        from services.api_cache import invalidate_listing_caches
        invalidate_listing_caches()

        if needs_retranslation:
            import asyncio as _aio
            _aio.ensure_future(_translate_listing_bg(
                db, listing_id,
                update_data.get("title", listing.get("title", "")),
                update_data.get("description", listing.get("description", "")),
                "en"
            ))
    updated_listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if isinstance(updated_listing.get("created_at"), str):
        updated_listing["created_at"] = datetime.fromisoformat(updated_listing["created_at"])
    if isinstance(updated_listing.get("auction_end_date"), str):
        updated_listing["auction_end_date"] = datetime.fromisoformat(updated_listing["auction_end_date"])
    return Listing(**updated_listing)


@listings_router.delete("/listings/{listing_id}")
async def delete_listing(listing_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    listing = await db.listings.find_one({"id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    await db.listings.delete_one({"id": listing_id})
    return {"message": "Listing deleted successfully"}


# ========== MULTI-ITEM LISTINGS ==========

@listings_router.post("/multi-item-listings")
async def create_multi_item_listing(
    listing_data: MultiItemListingCreate,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    from services.listings_service import (
        validate_seller, build_agreement_metadata,
        resolve_multi_item_status, compute_promotion,
        build_lots_with_end_time, serialise_datetimes,
    )
    db = get_db()

    await validate_seller(db, current_user, listing_data.agreement_accepted)

    # Category restriction: Only Partner role users can list vehicles in multi-item
    if listing_data.category and listing_data.category.lower() in ["vehicle", "vehicles"]:
        user_role = getattr(current_user, 'role', 'starter')
        if user_role not in ["partner", "admin"]:
            raise HTTPException(
                status_code=403,
                detail="Only Partner-tier accounts can list vehicles. Upgrade your account."
            )

    client_ip = request.client.host if request else "unknown"
    user_agent = request.headers.get("user-agent", "unknown") if request else "unknown"
    agreement_metadata = build_agreement_metadata(current_user, client_ip, user_agent)

    # ========== ENFORCE MARKETPLACE SETTINGS ==========
    settings = await get_marketplace_settings(db)

    if not settings.get("allow_all_users_multi_lot", True):
        if current_user.account_type != "business":
            raise HTTPException(
                status_code=403,
                detail="Multi-lot auctions are restricted to business accounts. Please upgrade your account or contact support."
            )

    max_active = settings.get("max_active_auctions_per_user", 20)
    active_count = await db.multi_item_listings.count_documents({
        "seller_id": current_user.id,
        "status": {"$in": ["active", "upcoming"]}
    })
    if active_count >= max_active:
        raise HTTPException(
            status_code=400,
            detail=f"You have reached the maximum limit of {max_active} active auctions. Please wait for current auctions to end."
        )

    max_lots = settings.get("max_lots_per_auction", 50)
    if len(listing_data.lots) > max_lots:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {max_lots} lots allowed per auction. You submitted {len(listing_data.lots)} lots."
        )

    status = await resolve_multi_item_status(db, current_user, listing_data, settings)

    currency = listing_data.currency
    if not currency:
        currency = detect_currency_from_location(city=listing_data.city, region=listing_data.region)
    tax_rates = get_tax_rates_for_currency(currency)

    promo = compute_promotion(current_user, listing_data)
    lots_with_end_time = build_lots_with_end_time(listing_data.lots, listing_data.auction_end_date)

    listing = MultiItemListing(
        seller_id=current_user.id,
        title=listing_data.title,
        description=listing_data.description,
        category=listing_data.category,
        location=listing_data.location,
        city=listing_data.city,
        region=listing_data.region,
        country=listing_data.country,
        postal_code=listing_data.postal_code,
        auction_end_date=listing_data.auction_end_date,
        auction_start_date=listing_data.auction_start_date,
        lots=lots_with_end_time,
        total_lots=len(listing_data.lots),
        status=status,
        currency=currency,
        tax_rate_gst=tax_rates["tax_rate_gst"],
        tax_rate_qst=tax_rates["tax_rate_qst"],
        is_featured=promo["is_featured"],
        promotion_expiry=promo["promotion_expiry"],
        is_promoted=promo["is_promoted"],
        promotion_tier=promo["promotion_tier"],
        promotion_start=promo["promotion_start"],
        promotion_end=promo["promotion_end"],
        documents=listing_data.documents,
        shipping_info=listing_data.shipping_info,
        visit_availability=listing_data.visit_availability,
        auction_terms_en=listing_data.auction_terms_en,
        auction_terms_fr=listing_data.auction_terms_fr,
        title_en=listing_data.title_en,
        title_fr=listing_data.title_fr,
        description_en=listing_data.description_en,
        description_fr=listing_data.description_fr,
    )

    listing_dict = listing.model_dump()
    listing_dict["agreement_metadata"] = agreement_metadata
    serialise_datetimes(listing_dict)

    await db.multi_item_listings.insert_one(listing_dict)
    listing_dict.pop("_id", None)

    # Background translation — if _en/_fr not already provided
    if not listing_data.title_en or not listing_data.title_fr:
        import asyncio as _aio
        raw_lots = [l.model_dump() if hasattr(l, "model_dump") else l for l in listing_data.lots]
        _aio.ensure_future(_translate_multi_listing_bg(
            db, listing.id, listing_data.title, listing_data.description,
            raw_lots, listing_data.content_language or "en"
        ))

    return listing


@listings_router.get("/multi-item-listings")
async def get_multi_item_listings(
    limit: int = 50,
    skip: int = 0,
    status: Optional[str] = None,
    category: Optional[str] = None,
    region: Optional[str] = None,
    city: Optional[str] = None,
    currency: Optional[str] = None,
    search: Optional[str] = None,
    seller_id: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
):
    db = get_read_db()
    has_filters = any([category, region, city, currency, search, seller_id, min_price, max_price])

    # Use cache for default (unfiltered) requests
    now = _time.time()
    if not has_filters and status is None and _multi_cache["data"] is not None and now < _multi_cache["ts"] + _multi_cache["ttl"]:
        cached = _multi_cache["data"]
        return cached[skip:skip + limit]

    query = {}
    if status:
        query["status"] = status
    else:
        query["status"] = {"$in": ["active", "upcoming"]}

    if category:
        query["category"] = category
    if region:
        query["region"] = region
    if city:
        query["city"] = city
    if currency:
        query["currency"] = currency

    if seller_id:
        ids = [s.strip() for s in seller_id.split(",") if s.strip()]
        if len(ids) == 1:
            query["seller_id"] = ids[0]
        elif len(ids) > 1:
            query["seller_id"] = {"$in": ids}

    if search:
        query["$or"] = [
            {"title": {"$regex": search, "$options": "i"}},
            {"description": {"$regex": search, "$options": "i"}}
        ]

    fetch_limit = min(limit, 50) if has_filters else 100
    logger.info(f"[multi-item] Fetching with query={query}, limit={fetch_limit}")
    listings = await db.multi_item_listings.find(query, {"_id": 0}).sort("created_at", -1).skip(skip if has_filters else 0).limit(fetch_limit).to_list(fetch_limit)
    logger.info(f"[multi-item] Got {len(listings)} docs from DB")

    for listing in listings:
        from services.listings_service import parse_listing_dates
        parse_listing_dates(listing)

    logger.info(f"[multi-item] Processed, returning {len(listings)} listings")

    # Cache unfiltered results (store raw dicts)
    if not has_filters and status is None:
        _multi_cache["data"] = listings
        _multi_cache["ts"] = now

    if has_filters:
        return listings
    return listings[skip:skip + limit]


@listings_router.get("/multi-item-listings/{listing_id}")
async def get_multi_item_listing(listing_id: str):
    db = get_db()
    listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if isinstance(listing.get("created_at"), str):
        from services.listings_service import parse_listing_dates
        parse_listing_dates(listing)

    return MultiItemListing(**listing)


@listings_router.get("/multi-item-listings/{listing_id}/terms/pdf")
async def export_auction_terms_pdf(listing_id: str):
    """Export auction terms as a PDF file."""
    from fastapi.responses import FileResponse
    from weasyprint import HTML
    import os

    db = get_db()
    try:
        listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            raise HTTPException(status_code=404, detail="Auction not found")

        seller = await db.users.find_one({"id": listing["seller_id"]}, {"_id": 0, "password": 0})
        seller_name = seller.get("company_name") or seller.get("name", "Unknown Seller")

        terms_en = listing.get("auction_terms_en", "")
        terms_fr = listing.get("auction_terms_fr", "")

        if not terms_en and not terms_fr:
            raise HTTPException(status_code=404, detail="No auction terms available")

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <style>
                @page {{ size: A4; margin: 2cm; }}
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .header {{ text-align: center; margin-bottom: 30px; padding-bottom: 20px; border-bottom: 2px solid #2563eb; }}
                .header h1 {{ color: #2563eb; margin: 0 0 10px 0; }}
                .header p {{ margin: 5px 0; color: #666; }}
                .section {{ margin: 30px 0; }}
                .section-title {{ font-size: 20px; font-weight: bold; color: #2563eb; margin-bottom: 15px; padding-bottom: 5px; border-bottom: 1px solid #ddd; }}
                .terms-content {{ margin: 15px 0; }}
                .footer {{ margin-top: 50px; padding-top: 20px; border-top: 1px solid #ddd; text-align: center; font-size: 12px; color: #666; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>BidVex Auction Platform</h1>
                <p style="font-size: 18px; font-weight: bold;">{listing.get('title', 'Auction')}</p>
                <p>Hosted by: {seller_name}</p>
                <p>Auction ID: {listing_id}</p>
            </div>
        """

        if terms_en:
            html_content += f"""
            <div class="section">
                <div class="section-title">Terms & Conditions (English)</div>
                <div class="terms-content">{terms_en}</div>
            </div>
            """

        if terms_fr:
            html_content += f"""
            <div class="section">
                <div class="section-title">Termes et Conditions (Fran\u00e7ais)</div>
                <div class="terms-content">{terms_fr}</div>
            </div>
            """

        html_content += """
            <div class="footer">
                <p>This document was generated by BidVex Auction Platform</p>
                <p>For questions, please contact the auctioneer listed above</p>
            </div>
        </body>
        </html>
        """

        pdf_dir = "/app/temp_pdfs"
        os.makedirs(pdf_dir, exist_ok=True)
        pdf_filename = f"auction_terms_{listing_id}.pdf"
        pdf_path = os.path.join(pdf_dir, pdf_filename)

        HTML(string=html_content).write_pdf(pdf_path)

        return FileResponse(
            path=pdf_path,
            filename=pdf_filename,
            media_type="application/pdf",
            headers={"Content-Disposition": f"attachment; filename={pdf_filename}"}
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating auction terms PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


# ========== AUCTION AGREEMENT PERSISTENCE ==========

@listings_router.post("/multi-item-listings/{listing_id}/accept-terms")
async def accept_auction_terms(listing_id: str, current_user: User = Depends(get_current_user)):
    """Record that a user has accepted the auction terms for a specific auction."""
    db = get_db()
    listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0, "id": 1, "title": 1})
    if not listing:
        raise HTTPException(status_code=404, detail="Auction not found")

    agreement_key = f"auction_agreements.{listing_id}"
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {agreement_key: datetime.now(timezone.utc).isoformat()}}
    )

    return {
        "success": True,
        "message": "Auction terms accepted",
        "auction_id": listing_id,
        "accepted_at": datetime.now(timezone.utc).isoformat()
    }


@listings_router.get("/multi-item-listings/{listing_id}/terms-status")
async def get_auction_terms_status(listing_id: str, current_user: User = Depends(get_current_user)):
    """Check if the user has already accepted terms for this auction."""
    db = get_db()
    user = await db.users.find_one({"id": current_user.id}, {"_id": 0, "auction_agreements": 1})
    auction_agreements = user.get("auction_agreements", {}) if user else {}

    has_accepted = listing_id in auction_agreements
    accepted_at = auction_agreements.get(listing_id) if has_accepted else None

    return {
        "auction_id": listing_id,
        "has_accepted": has_accepted,
        "accepted_at": accepted_at
    }


# ========== LISTING DELETION REQUESTS ==========

@listings_router.post("/listings/{listing_id}/request-deletion")
async def request_listing_deletion(
    listing_id: str,
    request_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Seller requests deletion of their listing."""
    db = get_db()
    listing = await db.listings.find_one({"id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not your listing")

    deletion_request = {
        "id": str(uuid.uuid4()),
        "listing_id": listing_id,
        "listing_type": "single",
        "listing_title": listing["title"],
        "seller_id": current_user.id,
        "seller_name": current_user.name,
        "seller_email": current_user.email,
        "reason": request_data.get("reason"),
        "status": "pending",
        "requested_at": datetime.now(timezone.utc),
        "reviewed_at": None,
        "reviewed_by": None
    }

    await db.deletion_requests.insert_one(deletion_request)
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {"deletion_request_pending": True}}
    )

    return {"success": True, "message": "Deletion request submitted"}


@listings_router.post("/multi-item-listings/{listing_id}/request-deletion")
async def request_multi_listing_deletion(
    listing_id: str,
    request_data: dict,
    current_user: User = Depends(get_current_user)
):
    """Seller requests deletion of their multi-item listing."""
    db = get_db()
    listing = await db.multi_item_listings.find_one({"id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not your listing")

    deletion_request = {
        "id": str(uuid.uuid4()),
        "listing_id": listing_id,
        "listing_type": "multi",
        "listing_title": listing["title"],
        "total_lots": len(listing.get("lots", [])),
        "seller_id": current_user.id,
        "seller_name": current_user.name,
        "seller_email": current_user.email,
        "reason": request_data.get("reason"),
        "status": "pending",
        "requested_at": datetime.now(timezone.utc),
        "reviewed_at": None,
        "reviewed_by": None
    }

    await db.deletion_requests.insert_one(deletion_request)
    await db.multi_item_listings.update_one(
        {"id": listing_id},
        {"$set": {"deletion_request_pending": True}}
    )

    return {"success": True, "message": "Deletion request submitted"}


# ========== TRANSLATION MANAGEMENT ==========

@listings_router.put("/listings/{listing_id}/translations")
async def update_listing_translations(
    listing_id: str,
    translations: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Seller manually overrides translations for a single listing."""
    db = get_db()
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    allowed = ["title_en", "title_fr", "description_en", "description_fr"]
    update_data = {k: v for k, v in translations.items() if k in allowed and v}
    if update_data:
        await db.listings.update_one({"id": listing_id}, {"$set": update_data})
        from services.api_cache import invalidate_listing_caches
        invalidate_listing_caches()

    return {"success": True, "updated_fields": list(update_data.keys())}


@listings_router.put("/multi-item-listings/{listing_id}/translations")
async def update_multi_listing_translations(
    listing_id: str,
    translations: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Seller manually overrides translations for a multi-item listing and its lots."""
    db = get_db()
    listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")

    allowed = ["title_en", "title_fr", "description_en", "description_fr"]
    update_data = {k: v for k, v in translations.items() if k in allowed and v}

    # Handle lot-level translations: lots[0].title_fr, etc.
    lot_translations = translations.get("lots", [])
    for i, lot_t in enumerate(lot_translations):
        for key in allowed:
            if key in lot_t and lot_t[key]:
                update_data[f"lots.{i}.{key}"] = lot_t[key]

    if update_data:
        await db.multi_item_listings.update_one({"id": listing_id}, {"$set": update_data})
        from services.api_cache import invalidate_listing_caches
        invalidate_listing_caches()

    return {"success": True, "updated_fields": list(update_data.keys())}


@listings_router.post("/admin/backfill-translations")
async def admin_backfill_translations(current_user: User = Depends(get_current_user)):
    """Admin-only: backfill translations for all existing listings."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_db()
    import asyncio as _aio
    from services.translation_service import backfill_listing_translations

    # Run in background to avoid timeout
    _aio.ensure_future(backfill_listing_translations(db))

    return {"success": True, "message": "Backfill started in background. Check server logs for progress."}
