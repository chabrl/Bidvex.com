"""
BidVex Listings Router
Handles all listing CRUD operations for both single-item and multi-item auctions,
including terms management and deletion requests.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks, UploadFile, File
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
from services.image_compression import compress_image_list
from services.sanitizer import sanitize_string, safe_regex

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
                [{"title": lot_item.get("title", ""), "description": lot_item.get("description", "")} for lot_item in lots],
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
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    from services.listings_service import (
        validate_seller, build_agreement_metadata, apply_partner_tags, persist_listing,
        resolve_listing_status,
    )
    from services.stripe_customer_service import validate_payment_method_for_listing
    db = get_db()

    # iter210 Step 5 — Demo accounts cannot place real bids / payments.
    # Hoisted ABOVE the Bill 96 validator (Phase 5 Hotfix v2) so demo users
    # get a clear 403 regardless of whether their payload is bilingual —
    # account status takes precedence over content validation.
    user_demo_row = await db.users.find_one({"id": current_user.id}, {"_id": 0, "is_demo_account": 1})
    if user_demo_row and user_demo_row.get("is_demo_account"):
        raise HTTPException(status_code=403, detail={
            "error": "demo_mode_payments_disabled",
            "message_en": "Demo mode — payments disabled. This account is for demonstration purposes only.",
            "message_fr": "Mode démo — paiements désactivés. Ce compte est uniquement à des fins de démonstration.",
        })

    # iter217 — Quebec Bill 96 compliance — French title required for QC listings
    from services.qc_bilingual_validator import assert_qc_bilingual_titles
    assert_qc_bilingual_titles(
        title=listing_data.title,
        title_fr=listing_data.title_fr,
        description=listing_data.description,
        description_fr=listing_data.description_fr,
        region=listing_data.region,
        city=listing_data.city,
        content_language=listing_data.content_language,
    )

    # ── iter203 P0 — Hard-coded vehicle/dealer compliance gate (FIRST line of defence) ──
    # This runs BEFORE payment-method validation so a non-dealer attempting a
    # vehicle listing receives the clear bilingual 403 immediately, regardless
    # of card status. The synchronous check is backed up by:
    #   • an AI scanner background task (right after listing insertion)
    #   • a 60-minute safety watchdog cron job (services/safety_watchdog.py)
    # Three layers, no single point of failure.
    from services.vehicle_listing_guard import enforce_vehicle_dealer_gate
    await enforce_vehicle_dealer_gate(
        db,
        current_user,
        category=listing_data.category,
        title=listing_data.title,
        description=listing_data.description,
        surface="single_listing",
    )

    # Sticky Card Guard: require valid payment method
    await validate_payment_method_for_listing(db, current_user)

    # iter209 Step 3 — Partner offering cash/e-transfer MUST have a saved card on file.
    # The 3% platform commission is auto-charged to that card when the auction closes.
    chosen_pm = (listing_data.payment_method or "").strip().lower().replace("-", "_")
    if chosen_pm in ("cash", "e_transfer", "etransfer"):
        user_row = await db.users.find_one({"id": current_user.id}, {"_id": 0, "partner_stripe_payment_method_id": 1, "partner_verification_status": 1, "is_partner": 1})
        is_partner = (user_row or {}).get("is_partner") or (user_row or {}).get("partner_verification_status") == "verified"
        if is_partner and not (user_row or {}).get("partner_stripe_payment_method_id"):
            raise HTTPException(status_code=403, detail={
                "error": "partner_card_required",
                "message_en": "A card on file is required to offer cash or e-transfer payment. Add your card in Payment Settings.",
                "message_fr": "Une carte enregistrée est requise pour offrir le paiement en espèces ou par virement. Ajoutez votre carte dans les paramètres de paiement.",
                "settings_url": "/partner/payment-settings",
            })

    await validate_seller(db, current_user, listing_data.agreement_accepted)

    client_ip = request.client.host if request else "unknown"
    user_agent = request.headers.get("user-agent", "unknown") if request else "unknown"
    agreement_metadata = build_agreement_metadata(current_user, client_ip, user_agent)

    listing = Listing(
        seller_id=current_user.id, title=listing_data.title, description=listing_data.description,
        category=listing_data.category, condition=listing_data.condition,
        starting_price=listing_data.starting_price, current_price=listing_data.starting_price,
        buy_now_price=listing_data.buy_now_price, images=compress_image_list(listing_data.images),
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

    # LEGACY: opc_permit → migrated to dealer_license_* (iter201). Field kept for back-compat.
    # Dealer-certified seller check + buyer-premium rate
    seller_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0, "is_opc_certified": 1})
    if seller_doc and seller_doc.get("is_opc_certified"):
        listing_dict["is_opc_certified"] = True
        # Dealer-certified sellers can set BP rate (0-25%), stored as percent on listing
        if listing_data.buyers_premium_rate is not None:
            listing_dict["buyers_premium_percent"] = min(listing_data.buyers_premium_rate * 100, 25)
        else:
            listing_dict["buyers_premium_percent"] = 0
    
    # Seller payment method preference
    if listing_data.payment_method:
        listing_dict["payment_method"] = listing_data.payment_method

    # ── Deposit (Spec Feature 1) — single field, ONE flow ──
    if listing_data.requires_deposit:
        if not listing_data.deposit_amount or listing_data.deposit_amount <= 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "deposit_amount_required",
                    "message_en": "Deposit amount is required when requires_deposit is true.",
                    "message_fr": "Le montant du dépôt est requis lorsque le dépôt est activé.",
                },
            )
        if listing_data.deposit_type not in ("fixed", "percentage"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_deposit_type",
                    "message_en": "deposit_type must be 'fixed' or 'percentage'.",
                    "message_fr": "deposit_type doit être 'fixed' ou 'percentage'.",
                },
            )
        listing_dict["requires_deposit"] = True
        listing_dict["deposit_amount"] = float(listing_data.deposit_amount)
        listing_dict["deposit_type"] = listing_data.deposit_type
    else:
        listing_dict["requires_deposit"] = False
        listing_dict["deposit_amount"] = None
        listing_dict["deposit_type"] = None

    await apply_partner_tags(db, current_user, listing_dict, listing_data.buyers_premium_rate)

    # ── Moderation gate for single-item listings ──
    # Mirrors resolve_multi_item_status: when require_approval_new_sellers is ON
    # and the seller has zero completed listings, mark as pending so admins moderate.
    settings = await get_marketplace_settings(db)
    listing_dict["status"] = await resolve_listing_status(db, current_user, settings)

    result = await persist_listing(db, listing_dict, agreement_metadata)

    # ── iter203 P0 — AI Scanner background task (secondary defence) ──
    # Even if the synchronous hard gate above missed something (e.g. an
    # extremely creative title), the AI scanner re-reads the listing
    # asynchronously and pauses it to status="pending_review" if it looks
    # like a vehicle from a non-dealer. Fail-OPEN: if Gemini is down, the
    # listing is left as-is — the watchdog cron will catch it within 60 min.
    try:
        from services.vehicle_listing_scanner import scan_listing_for_vehicles
        background_tasks.add_task(
            scan_listing_for_vehicles,
            db,
            listing_id=result["id"],
            collection="listings",
        )
    except Exception as e:
        logger.error(f"[AI_SCANNER] Failed to schedule vehicle scan for {result.get('id')}: {e}")

    # iter214 P5 — General-purpose moderation scan (prohibited items) running
    # in parallel to the vehicle scanner. Fail-OPEN — if Gemini is unavailable
    # the listing is left as-is.
    try:
        from services.listing_moderation_scanner import scan_listing_for_violations
        background_tasks.add_task(
            scan_listing_for_violations,
            db,
            listing_id=result["id"],
            collection="listings",
        )
    except Exception as e:
        logger.error(f"[AI_MODERATION] Failed to schedule moderation scan for {result.get('id')}: {e}")

    # Notify admin when a listing needs moderation (non-blocking)
    if listing_dict["status"] == "pending":
        try:
            from services.admin_notifications import notify_admin_new_listing
            background_tasks.add_task(notify_admin_new_listing, result)
        except Exception as e:
            logger.error(f"[MODERATION] Failed to schedule admin notify for {result.get('id')}: {e}")

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
    tax_status: Optional[str] = None,        # "partner" | "standard" — UI filter
    buyer_province: Optional[str] = None,    # for "nearby_first" geo-sort
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
        try:
            search = sanitize_string(search)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid search query")
        _safe = safe_regex(search)
        query["$or"] = [{"title": {"$regex": _safe, "$options": "i"}}, {"description": {"$regex": _safe, "$options": "i"}}]

    # ── Tax Status filter (partner vs standard listings) ──
    if tax_status == "partner":
        query["seller_type"] = "partner"
    elif tax_status == "standard":
        query["seller_type"] = {"$in": ["individual", "enterprise"]}

    # ── Sort handling: special "nearby_first" geo-sort ──
    is_geo_sort = sort == "nearby_first"
    sort_order = -1 if sort.startswith("-") else 1
    sort_field = sort.lstrip("-") if not is_geo_sort else "created_at"

    # Promoted listings always surface first — boosted listings beat any
    # other sort. Tier weight breaks ties (premium > standard > basic).
    sort_spec = [
        ("is_promoted", -1),
        ("promotion_tier_weight", -1),
        (sort_field, sort_order),
    ]

    listings = await db.listings.find(query, {"_id": 0}).sort(sort_spec).skip(skip).limit(limit).to_list(limit)

    # Also include individual lots from multi-item listings as independent items
    multi_query = {"status": "active"}
    if category:
        multi_query["category"] = category
    if city:
        multi_query["city"] = city
    if region:
        multi_query["region"] = region
    if search:
        try:
            search = sanitize_string(search)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid search query")
        _safe = safe_regex(search)
        multi_query["$or"] = [{"title": {"$regex": _safe, "$options": "i"}}, {"description": {"$regex": _safe, "$options": "i"}}]
    # Tax Status filter applies to multi-item too
    if tax_status == "partner":
        multi_query["seller_type"] = "partner"
    elif tax_status == "standard":
        multi_query["seller_type"] = {"$in": ["individual", "enterprise"]}

    multi_listings = await db.multi_item_listings.find(multi_query, {"_id": 0}).sort(sort_spec).limit(limit).to_list(limit)

    # Deduplicate: collect parent auction IDs to exclude from standard listings
    multi_parent_ids = {ml["id"] for ml in multi_listings}
    listings = [item for item in listings if item.get("id") not in multi_parent_ids]

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
                "location": ml.get("location") or ", ".join(filter(None, [ml.get("city", ""), ml.get("region", "")])) or "—",
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
                # Propagate seller-type pricing context onto synthesized lot items
                "seller_type": ml.get("seller_type", "individual"),
                "partner_bp_rate": ml.get("partner_bp_rate"),
                "seller_province": ml.get("seller_province"),
                "seller_city": ml.get("seller_city"),
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
    if is_geo_sort:
        # Geo-sort: same province → adjacent → other; tiebreak by created_at desc
        from services.geo_sort import geo_priority_value
        listings.sort(key=lambda x: (
            geo_priority_value(x.get("seller_province"), buyer_province or ""),
            -(x.get("created_at").timestamp() if hasattr(x.get("created_at"), "timestamp")
              else 0)
        ))
    else:
        reverse = sort_order == -1
        def _sort_key(x):
            v = x.get(sort_field)
            if v is None:
                return "" if isinstance(sort_field, str) and sort_field != "current_price" else 0
            return v
        listings.sort(key=_sort_key, reverse=reverse)
    listings = listings[:limit]

    for listing in listings:
        if isinstance(listing.get("created_at"), str):
            listing["created_at"] = datetime.fromisoformat(listing["created_at"])
        if isinstance(listing.get("auction_end_date"), str):
            listing["auction_end_date"] = datetime.fromisoformat(listing["auction_end_date"])

    # iter217 — Bulk seller enrichment so listing cards can render Partner /
    # Dealer / Storage / Private-Sale badges. Lot-synthesised items inherit
    # their parent auction's seller_id so this works for them too.
    from services.listing_seller_enrichment import enrich_listings_bulk_async
    await enrich_listings_bulk_async(db, listings)

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
    # iter217 — enrich with seller-account flags so the frontend can render
    # the correct badge + canonical buyer's premium rate.
    from services.listing_seller_enrichment import enrich_listing_async
    listing_doc = await enrich_listing_async(get_db(), listing_doc)
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


# ── Phase 5 Hotfix v4 — S3 multipart image upload ─────────────────────
# Replaces the legacy base64-in-MongoDB pattern. Accepts up to 15 files
# per request, processes them through `services/s3_service.py` (resize +
# compress + JPEG re-encode), and appends the resulting public HTTPS URLs
# to the listing's `images` array. Never writes raw base64 to the DB.
LISTING_IMAGES_MAX = 15


@listings_router.post("/listings/{listing_id}/images")
async def upload_listing_images(
    listing_id: str,
    files: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload one or more listing photos to S3.

    Body: multipart/form-data with one or more `files` parts.
    Validation:
      • Listing must exist and belong to current_user.
      • At most 15 images allowed (existing + new).
      • Each file is processed (resize/compress) and uploaded to S3.
      • Returns the updated `images` array (HTTPS URLs only).
    """
    db = get_db()

    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail={
            "error": "no_files",
            "message_en": "No files were provided.",
            "message_fr": "Aucun fichier fourni.",
        })

    # Try `listings` first, then `multi_item_listings` so the endpoint
    # works for both single and multi-lot listings owned by the user.
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    collection = "listings"
    if not listing:
        listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
        collection = "multi_item_listings"
    if not listing:
        raise HTTPException(status_code=404, detail={
            "error": "listing_not_found",
            "message_en": "Listing not found.",
            "message_fr": "Annonce introuvable.",
        })

    if listing.get("seller_id") != current_user.id:
        raise HTTPException(status_code=403, detail={
            "error": "not_authorized",
            "message_en": "You are not authorized to upload images to this listing.",
            "message_fr": "Vous n'êtes pas autorisé à téléverser des images pour cette annonce.",
        })

    existing_images = list(listing.get("images") or [])
    total_after = len(existing_images) + len(files)
    if total_after > LISTING_IMAGES_MAX:
        raise HTTPException(status_code=400, detail={
            "error": "too_many_images",
            "message_en": f"At most {LISTING_IMAGES_MAX} images per listing — current {len(existing_images)}, attempted to add {len(files)}.",
            "message_fr": f"Maximum {LISTING_IMAGES_MAX} images par annonce — actuellement {len(existing_images)}, tentative d'ajout {len(files)}.",
        })

    from services.s3_service import upload_image_to_s3

    uploaded_urls: List[str] = []
    failures: List[Dict[str, Any]] = []
    for idx, file in enumerate(files, start=len(existing_images)):
        if file.content_type and not file.content_type.startswith("image/"):
            failures.append({"filename": file.filename, "reason": "not_an_image"})
            continue
        try:
            url = await upload_image_to_s3(file, listing_id, idx)
            uploaded_urls.append(url)
        except ValueError as e:
            failures.append({"filename": file.filename, "reason": str(e)})
        except Exception as e:
            logger.error("S3 upload failed for %s: %s", file.filename, e)
            failures.append({"filename": file.filename, "reason": "upload_failed"})

    if not uploaded_urls:
        raise HTTPException(status_code=400, detail={
            "error": "all_uploads_failed",
            "failures": failures,
        })

    new_images = existing_images + uploaded_urls
    await db[collection].update_one(
        {"id": listing_id},
        {"$set": {"images": new_images}},
    )

    return {
        "success":         True,
        "uploaded_count":  len(uploaded_urls),
        "uploaded_urls":   uploaded_urls,
        "images":          new_images,
        "failures":        failures,
    }


# ========== MULTI-ITEM LISTINGS ==========

@listings_router.post("/multi-item-listings")
async def create_multi_item_listing(
    listing_data: MultiItemListingCreate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    from services.listings_service import (
        validate_seller, build_agreement_metadata,
        resolve_multi_item_status, compute_promotion,
        build_lots_with_end_time, serialise_datetimes,
    )
    from services.stripe_customer_service import validate_payment_method_for_listing
    db = get_db()

    # iter210 Step 5 — Demo accounts cannot place real bids / payments.
    # Hoisted ABOVE the Bill 96 validator (Phase 5 Hotfix v2) so demo users
    # get a clear 403 regardless of payload language.
    user_demo_row = await db.users.find_one({"id": current_user.id}, {"_id": 0, "is_demo_account": 1})
    if user_demo_row and user_demo_row.get("is_demo_account"):
        raise HTTPException(status_code=403, detail={
            "error": "demo_mode_payments_disabled",
            "message_en": "Demo mode — payments disabled. This account is for demonstration purposes only.",
            "message_fr": "Mode démo — paiements désactivés. Ce compte est uniquement à des fins de démonstration.",
        })

    # iter217 — Quebec Bill 96 compliance — French title required for QC listings
    from services.qc_bilingual_validator import assert_qc_bilingual_titles
    assert_qc_bilingual_titles(
        title=getattr(listing_data, "title", None),
        title_fr=getattr(listing_data, "title_fr", None),
        description=getattr(listing_data, "description", None),
        description_fr=getattr(listing_data, "description_fr", None),
        region=getattr(listing_data, "region", None),
        city=getattr(listing_data, "city", None),
        content_language=getattr(listing_data, "content_language", None),
    )

    # ── Deposit field validation (Spec Feature 1) — runs BEFORE sticky-card guard
    # so negative-path tests can reach 400 with bilingual error before 402-no-card.
    if listing_data.requires_deposit:
        if not listing_data.deposit_amount or float(listing_data.deposit_amount) <= 0:
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "deposit_amount_required",
                    "message_en": "Deposit amount is required when requires_deposit is true.",
                    "message_fr": "Le montant du dépôt est requis lorsque le dépôt est activé.",
                },
            )
        if listing_data.deposit_type not in ("fixed", "percentage"):
            raise HTTPException(
                status_code=400,
                detail={
                    "error": "invalid_deposit_type",
                    "message_en": "deposit_type must be 'fixed' or 'percentage'.",
                    "message_fr": "deposit_type doit être 'fixed' ou 'percentage'.",
                },
            )

    # Sticky Card Guard
    await validate_payment_method_for_listing(db, current_user)

    await validate_seller(db, current_user, listing_data.agreement_accepted)

    # ── iter203 P0 — Hard-coded vehicle/dealer compliance gate ──
    # Replaces the legacy narrow "Partner-only" rule. Detects vehicle-shaped
    # listings via category + title + description AND scans every lot. Non-
    # dealer sellers receive 403 + bilingual message.
    from services.vehicle_listing_guard import enforce_vehicle_dealer_gate
    await enforce_vehicle_dealer_gate(
        db,
        current_user,
        category=listing_data.category,
        title=listing_data.title,
        description=listing_data.description,
        surface="multi_item_listing",
    )
    # Each lot must also pass — protects against the parent looking benign
    # while one of the lots is a hidden vehicle.
    for lot in (listing_data.lots or []):
        await enforce_vehicle_dealer_gate(
            db,
            current_user,
            category=listing_data.category,
            title=getattr(lot, "title", None),
            description=getattr(lot, "description", None),
            surface="multi_item_lot",
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

    max_lots = settings.get("max_lots_per_auction", 500)
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

    # Compress images on every lot to reduce DB + bandwidth
    for _lot in lots_with_end_time:
        if isinstance(_lot, dict) and _lot.get("images"):
            _lot["images"] = compress_image_list(_lot["images"])

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
        payment_method=listing_data.payment_method or "stripe",
        requires_deposit=bool(listing_data.requires_deposit),
        deposit_amount=float(listing_data.deposit_amount) if (listing_data.requires_deposit and listing_data.deposit_amount) else None,
        deposit_type=(listing_data.deposit_type or "fixed") if listing_data.requires_deposit else None,
    )

    listing_dict = listing.model_dump()

    listing_dict = listing.model_dump()
    listing_dict["agreement_metadata"] = agreement_metadata
    serialise_datetimes(listing_dict)

    # iter211 P4 — tag demo accounts' multi-item listings
    from services.demo_filter import tag_listing_if_demo
    await tag_listing_if_demo(db, current_user.id, listing_dict)

    await db.multi_item_listings.insert_one(listing_dict)
    listing_dict.pop("_id", None)

    # ── iter203 P0 — AI Scanner background task (secondary defence) ──
    try:
        from services.vehicle_listing_scanner import scan_listing_for_vehicles
        background_tasks.add_task(
            scan_listing_for_vehicles,
            db,
            listing_id=listing.id,
            collection="multi_item_listings",
        )
    except Exception as e:
        logger.error(f"[AI_SCANNER] Failed to schedule vehicle scan for {listing.id}: {e}")

    # iter214 P5 — General moderation scan (prohibited items)
    try:
        from services.listing_moderation_scanner import scan_listing_for_violations
        background_tasks.add_task(
            scan_listing_for_violations,
            db,
            listing_id=listing.id,
            collection="multi_item_listings",
        )
    except Exception as e:
        logger.error(f"[AI_MODERATION] Failed to schedule moderation scan for {listing.id}: {e}")

    # Background translation — if _en/_fr not already provided
    if not listing_data.title_en or not listing_data.title_fr:
        import asyncio as _aio
        raw_lots = [lot_item.model_dump() if hasattr(lot_item, "model_dump") else lot_item for lot_item in listing_data.lots]
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
    seller_account_type: Optional[str] = None,  # iter217 — partner / vehicle_dealer / storage_facility / individual
    promoted_first: bool = False,
):
    db = get_read_db()
    has_filters = any([category, region, city, currency, search, seller_id, min_price, max_price, seller_account_type, promoted_first])

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
    # iter217 Bug 10 — Case-insensitive region match using a regex (works
    # for cached docs that stored "QC" while the UI sends "Quebec" or vice versa).
    if region:
        from routes.marketplace import _normalize_region, _PROVINCE_ALIASES
        norm = _normalize_region(region)
        synonyms = sorted({k for k, v in _PROVINCE_ALIASES.items() if v == norm} | {norm}) if norm else [region]
        query["$or"] = [
            {"region": {"$in": [s for s in synonyms] + [s.upper() for s in synonyms]}},
            {"province": {"$in": [s for s in synonyms] + [s.upper() for s in synonyms]}},
        ]
    if city:
        from routes.marketplace import _normalize_city as _nc
        # Use a case-insensitive regex on `city` AND `location` so partial match works.
        try:
            from re import escape as _re_escape
            cre = {"$regex": _re_escape(city), "$options": "i"}
            query["$and"] = (query.get("$and") or []) + [{"$or": [{"city": cre}, {"location": cre}]}]
            _ = _nc(city)  # avoid unused import
        except Exception:
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
        try:
            search = sanitize_string(search)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid search query")
        _safe = safe_regex(search)
        query["$or"] = [
            {"title": {"$regex": _safe, "$options": "i"}},
            {"description": {"$regex": _safe, "$options": "i"}}
        ]

    fetch_limit = min(limit, 50) if has_filters else 100
    logger.info(f"[multi-item] Fetching with query={query}, limit={fetch_limit}")
    listings = await db.multi_item_listings.find(query, {"_id": 0}).sort("created_at", -1).skip(skip if has_filters else 0).limit(fetch_limit).to_list(fetch_limit)
    logger.info(f"[multi-item] Got {len(listings)} docs from DB")

    for listing in listings:
        from services.listings_service import parse_listing_dates
        parse_listing_dates(listing)

    # iter217 — Bulk seller enrichment for badge display on cards.
    from services.listing_seller_enrichment import enrich_listings_bulk_async
    await enrich_listings_bulk_async(db, listings)

    # iter217 Phase 3 — seller_account_type filter (applied AFTER enrichment
    # because account-type is computed at GET time from the seller's User doc).
    if seller_account_type:
        wanted = [s.strip() for s in seller_account_type.split(",") if s.strip()]
        listings = [l for l in listings if l.get("seller_account_type") in wanted]

    # iter217 Phase 3 — promoted listings first (then preserve created_at desc).
    if promoted_first:
        listings.sort(key=lambda l: (
            0 if l.get("is_promoted") else 1,
            -(l.get("promotion_tier_weight") or 0),
        ))

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

    # iter217 — enrich with seller-account flags so the frontend can render
    # the correct badge + canonical buyer's premium rate.
    from services.listing_seller_enrichment import enrich_listing_async
    listing = await enrich_listing_async(db, listing)

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
