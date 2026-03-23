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
    db = get_db()

    # ========== MANDATORY: SELLER BINDING AGREEMENT VALIDATION ==========
    if not listing_data.agreement_accepted:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "agreement_required",
                "msg": "You must accept the binding agreement to sell before creating a listing. This agreement certifies you are the legal owner and will honor the winning bid.",
                "field": "agreement_accepted"
            }
        )

    client_ip = request.client.host if request else "unknown"
    user_agent = request.headers.get("user-agent", "unknown") if request else "unknown"
    agreement_metadata = {
        "accepted": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip_address": client_ip,
        "user_agent": user_agent,
        "user_id": current_user.id,
        "user_email": current_user.email
    }

    # ========== HIGH-TRUST GATEKEEPING ==========
    if current_user.role != 'admin':
        # Partner fee check
        if current_user.is_partner and not current_user.platform_fee_paid:
            raise HTTPException(
                status_code=403,
                detail="Your annual partner fee is required to create listings. Please complete your payment to activate your account."
            )
        if not current_user.phone_verified:
            raise HTTPException(
                status_code=403,
                detail="Phone verification required. Please verify your phone number before creating listings."
            )
        payment_methods = await db.payment_methods.count_documents({"user_id": current_user.id})
        if payment_methods == 0:
            raise HTTPException(
                status_code=403,
                detail="Payment method required. Please add a payment card before creating listings."
            )

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
        visit_availability=listing_data.visit_availability
    )
    listing_dict = listing.model_dump()

    # Auto-tag partner listings & set buyer premium
    seller_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if seller_doc and seller_doc.get("is_partner") and seller_doc.get("partner_verification_status") == "verified":
        listing_dict["is_partner_listing"] = True
        listing_dict["is_verified_firm"] = seller_doc.get("is_verified_firm", False)
        # Listing-level premium: use form value → org default → None
        if listing_data.buyers_premium_rate is not None:
            listing_dict["custom_buyer_premium_rate"] = listing_data.buyers_premium_rate
        else:
            listing_dict["custom_buyer_premium_rate"] = seller_doc.get("custom_premium_rate")
    else:
        listing_dict["is_partner_listing"] = False
        listing_dict["is_verified_firm"] = False
        # Non-partner: use form value if provided, else None (tier default applies at calc time)
        if listing_data.buyers_premium_rate is not None:
            listing_dict["custom_buyer_premium_rate"] = listing_data.buyers_premium_rate
        else:
            listing_dict["custom_buyer_premium_rate"] = None

    listing_dict["agreement_metadata"] = agreement_metadata
    listing_dict["auction_end_date"] = listing_dict["auction_end_date"].isoformat()
    listing_dict["created_at"] = listing_dict["created_at"].isoformat()
    await db.listings.insert_one(listing_dict)
    listing_dict.pop("_id", None)
    
    # Invalidate public caches on new listing
    from services.api_cache import invalidate_listing_caches
    invalidate_listing_caches()
    
    return listing_dict


@listings_router.get("/listings", response_model=List[Listing])
async def get_listings(
    category: Optional[str] = None, city: Optional[str] = None, region: Optional[str] = None,
    condition: Optional[str] = None, min_price: Optional[float] = None, max_price: Optional[float] = None,
    search: Optional[str] = None, sort: str = "created_at", limit: int = 50, skip: int = 0
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
    allowed_fields = ["title", "description", "category", "condition", "images", "location", "city", "region", "country", "postal_code", "status"]
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}
    if update_data:
        await db.listings.update_one({"id": listing_id}, {"$set": update_data})
        # Invalidate public caches on listing update
        from services.api_cache import invalidate_listing_caches
        invalidate_listing_caches()
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
    db = get_db()

    # ========== MANDATORY: SELLER BINDING AGREEMENT VALIDATION ==========
    if not listing_data.agreement_accepted:
        raise HTTPException(
            status_code=422,
            detail={
                "type": "agreement_required",
                "msg": "You must accept the binding agreement to sell before creating a listing. This agreement certifies you are the legal owner and will honor the winning bid.",
                "field": "agreement_accepted"
            }
        )

    client_ip = request.client.host if request else "unknown"
    user_agent = request.headers.get("user-agent", "unknown") if request else "unknown"
    agreement_metadata = {
        "accepted": True,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "ip_address": client_ip,
        "user_agent": user_agent,
        "user_id": current_user.id,
        "user_email": current_user.email
    }

    # ========== PARTNER FEE GATEKEEPING ==========
    if current_user.is_partner and not current_user.platform_fee_paid:
        raise HTTPException(
            status_code=403,
            detail="Your annual partner fee is required to create listings. Please complete your payment to activate your account."
        )

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

    now = datetime.now(timezone.utc)
    status = "active"

    if settings.get("require_approval_new_sellers", False):
        completed_count = await db.multi_item_listings.count_documents({
            "seller_id": current_user.id,
            "status": "completed"
        })
        if completed_count < 1:
            status = "pending"
            logger.info(f"New seller {current_user.email} listing set to PENDING for approval")

    if listing_data.auction_start_date:
        if listing_data.auction_start_date > now and status != "pending":
            status = "upcoming"

    currency = listing_data.currency
    if not currency:
        currency = detect_currency_from_location(
            city=listing_data.city,
            region=listing_data.region
        )

    tax_rates = get_tax_rates_for_currency(currency)

    is_featured = False
    promotion_expiry = None
    if current_user.subscription_tier == "premium":
        is_featured = True
        promotion_expiry = now + timedelta(days=3)
    elif current_user.subscription_tier == "vip":
        is_featured = True
        promotion_expiry = now + timedelta(days=7)

    promotion_tier = listing_data.promotion_tier
    is_promoted = listing_data.is_promoted
    promotion_start = None
    promotion_end = None

    if promotion_tier in ['premium', 'elite']:
        is_promoted = True
        promotion_start = now
        if promotion_tier == 'premium':
            promotion_end = now + timedelta(days=7)
        elif promotion_tier == 'elite':
            promotion_end = now + timedelta(days=14)
            is_featured = True
        logger.info(f"Seller promoted listing: tier={promotion_tier}, ends={promotion_end}")

    auction_end = listing_data.auction_end_date
    lots_with_end_time = []
    for idx, lot in enumerate(listing_data.lots):
        lot_dict = lot.model_dump()
        lot_dict['lot_end_time'] = auction_end + timedelta(minutes=idx)
        lots_with_end_time.append(lot_dict)

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
        is_featured=is_featured,
        promotion_expiry=promotion_expiry,
        is_promoted=is_promoted,
        promotion_tier=promotion_tier,
        promotion_start=promotion_start,
        promotion_end=promotion_end,
        documents=listing_data.documents,
        shipping_info=listing_data.shipping_info,
        visit_availability=listing_data.visit_availability,
        auction_terms_en=listing_data.auction_terms_en,
        auction_terms_fr=listing_data.auction_terms_fr
    )

    listing_dict = listing.model_dump()
    listing_dict["agreement_metadata"] = agreement_metadata
    listing_dict["auction_end_date"] = listing_dict["auction_end_date"].isoformat()
    listing_dict["created_at"] = listing_dict["created_at"].isoformat()
    if listing_dict["auction_start_date"]:
        listing_dict["auction_start_date"] = listing_dict["auction_start_date"].isoformat()
    if listing_dict["promotion_expiry"]:
        listing_dict["promotion_expiry"] = listing_dict["promotion_expiry"].isoformat()
    if listing_dict.get("promotion_start"):
        listing_dict["promotion_start"] = listing_dict["promotion_start"].isoformat()
    if listing_dict.get("promotion_end"):
        listing_dict["promotion_end"] = listing_dict["promotion_end"].isoformat()

    for lot in listing_dict.get("lots", []):
        if lot.get("lot_end_time"):
            lot["lot_end_time"] = lot["lot_end_time"].isoformat()

    await db.multi_item_listings.insert_one(listing_dict)
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
        if isinstance(listing.get("created_at"), str):
            listing["created_at"] = datetime.fromisoformat(listing["created_at"])
        if isinstance(listing.get("auction_end_date"), str):
            listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
        if isinstance(listing.get("auction_start_date"), str):
            listing["auction_start_date"] = datetime.fromisoformat(listing["auction_start_date"])
        for lot in listing.get("lots", []):
            if isinstance(lot.get("lot_end_time"), str):
                lot["lot_end_time"] = datetime.fromisoformat(lot["lot_end_time"])

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
        listing["created_at"] = datetime.fromisoformat(listing["created_at"])
    if isinstance(listing.get("auction_end_date"), str):
        listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])
    if isinstance(listing.get("auction_start_date"), str):
        listing["auction_start_date"] = datetime.fromisoformat(listing["auction_start_date"])
    for lot in listing.get("lots", []):
        if isinstance(lot.get("lot_end_time"), str):
            lot["lot_end_time"] = datetime.fromisoformat(lot["lot_end_time"])

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
