"""
BidVex Listings Router
Handles all listing CRUD operations for both single-item and multi-item auctions,
including terms management and deletion requests.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, BackgroundTasks, UploadFile, File, Query
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
from services.s3_service import (
    upload_base64_to_s3,
    is_base64_image,
    is_marketplace_s3_url,
)


async def _promote_base64_images_to_s3(images: list, listing_id: str) -> list:
    """iter213 — Walk an image array and upload any base64 entry to S3.

    Already-uploaded https URLs (S3 or otherwise) and stale Facebook redirects
    are returned as-is (we never destructively overwrite). Failures fall back
    to the original base64 string so the listing still has *something* visible
    to the seller in the dashboard even when S3 hiccups.
    """
    if not images:
        return []
    out: list = []
    for idx, img in enumerate(images or []):
        if not isinstance(img, str) or not img:
            continue
        if is_marketplace_s3_url(img) or (img.startswith("https://") and not is_base64_image(img)):
            out.append(img)
            continue
        if is_base64_image(img):
            try:
                out.append(await upload_base64_to_s3(img, listing_id, idx))
                continue
            except Exception as exc:
                logger.warning(
                    "[listing-create] S3 promote failed for %s img %d: %s",
                    listing_id, idx, exc,
                )
        out.append(img)
    return out


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

@listings_router.get("/listings/my-listings")
async def get_my_listings(current_user: User = Depends(get_current_user)):
    """HOTFIX v9.1 / Fix 3 — Seller's own listings + filter-tab counts.

    Returns:
      { listings: [...], counts: { total, active, pending_review, draft, ended, sold } }
    """
    db = get_db()
    single = await db.listings.find({"seller_id": current_user.id}, {"_id": 0}).to_list(1000)
    multi = await db.multi_item_listings.find({"seller_id": current_user.id}, {"_id": 0}).to_list(1000)
    all_listings = single + multi

    _PENDING = ("pending_ai_review", "pending_admin_review", "pending_review")
    # iter298 BUG 2/5 — zero-bid `ended_no_sale` + storage `unsold` join
    # the ended bucket.
    _ENDED = ("sold", "ended", "expired", "completed", "ended_no_sale", "unsold")

    # iter296 P0 BUG 5 — sold counter unions both end-state conventions
    # so the marketplace flow (`status: "ended"` + `winner_user_id`)
    # counts alongside vehicle/storage (`status: "sold"`).
    def _is_sold(l: dict) -> bool:
        if l.get("status") == "sold":
            return True
        if l.get("status") == "ended" and l.get("winner_user_id"):
            return True
        return False

    counts = {
        "total":          len(all_listings),
        "active":         sum(1 for l in all_listings if l.get("status") == "active"),
        "pending_review": sum(1 for l in all_listings if l.get("status") in _PENDING),
        "draft":          sum(1 for l in all_listings if l.get("status") == "draft"),
        "ended":          sum(1 for l in all_listings if l.get("status") in _ENDED),
        "sold":           sum(1 for l in all_listings if _is_sold(l)),
    }
    return {"listings": all_listings, "counts": counts}


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

    # iter223 — Demo Sandbox: demo accounts can NOW create listings, but each
    # is force-stamped `is_demo_sandbox=True` and invisible to the public.
    # The demo user sees their own sandbox items live in the real product
    # frames; everyone else sees an unchanged marketplace.
    user_demo_row = await db.users.find_one(
        {"id": current_user.id},
        {"_id": 0, "is_demo_account": 1, "account_type": 1},
    )
    _is_demo_creator = bool(user_demo_row and user_demo_row.get("is_demo_account"))

    # iter217 — Quebec Bill 96 compliance — French title required for QC listings
    # Phase 6.0 hotfix — admins bypass the hard validator (master role override).
    # iter310 — Auto-translate missing French copy via Gemini 2.5 Flash before
    # the hard-gate runs. Runs for EVERYONE (incl. admins) so the resulting
    # MongoDB row always has clean bilingual copy.
    _is_admin_role = (getattr(current_user, "role", "") or "").lower() in ("admin", "super_admin")
    from services.bill96_autofill import autofill_qc_french_copy
    _bill96_autofill_result = await autofill_qc_french_copy(listing_data)
    if not _is_admin_role:
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

    # iter389 — Hard-reject base64 image payloads. See _reject_base64_in_images.
    _reject_base64_in_images(getattr(listing_data, "images", None) or [], "images")

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

    # Phase 6.0 / Task 3 — Storage Locker validation + quantity policy override.
    # Storage lockers sell as ONE absolute lot block — quantity is forced to 1.
    if (listing_data.listing_type or "").lower() == "storage_locker":
        from services.storage_locker import (
            normalize_storage_metadata, storage_quantity_policy,
        )
        # Phase 6.0 hotfix — Admin power-user override: admins skip the
        # `facility_name required` validation and any other client-side
        # gates so they can list a unit on behalf of a facility manager.
        is_admin = (getattr(current_user, "role", "") or "").lower() in ("admin", "super_admin")

        # Phase 6.2 Task 2 — Role gate: only `storage_facility` accounts may
        # create storage_locker listings. Admins bypass.
        is_facility = (
            getattr(current_user, "account_type", "") == "storage_facility"
            or getattr(current_user, "is_storage_facility", False)
        )
        if not (is_admin or is_facility):
            raise HTTPException(status_code=403, detail={
                "error": "facility_role_required",
                "message_en": "Storage locker auctions can only be created by verified storage facility accounts. Please apply for a facility account from your profile.",
                "message_fr": "Les enchères de casier de stockage ne peuvent être créées que par les comptes d'installation de stockage vérifiés. Demandez un compte d'installation depuis votre profil.",
            })
        try:
            listing_data.storage_metadata = normalize_storage_metadata(
                listing_data.storage_metadata,
                allow_missing_required=is_admin,
            )
        except ValueError as ve:
            if not is_admin:
                raise HTTPException(status_code=400, detail={
                    "error": "invalid_storage_metadata",
                    "message_en": str(ve),
                    "message_fr": "Métadonnées du casier de stockage invalides : " + str(ve),
                })
            # Admin override: fall back to a minimal placeholder so the row
            # still passes Pydantic. Admins can edit the row post-creation.
            listing_data.storage_metadata = {
                "facility_name":           "(admin-created — pending facility manager attachment)",
                "facility_address":        "",
                "locker_size":             "",
                "locker_number":           "",
                "cleanout_deadline_hours": 72,
                "security_deposit_amount": 100.00,
                "lien_compliance_verified": True,   # admins bear responsibility
                "facility_manager_email":  "",
                "facility_manager_phone":  "",
                "notes":                   "",
                "admin_created":           True,
                "admin_created_by":        current_user.email,
            }
            logger.info(
                f"[storage_locker] admin override — {current_user.email} created a locker "
                f"with missing facility_name (reason: {ve})"
            )
        qty, multiplier = storage_quantity_policy(listing_data.quantity)
        listing_data.quantity = qty
        listing_data.multiply_hammer_by_quantity = multiplier
        # iter233 — Storage lockers sell as a single absolute lot block, so
        # the display multiplier never applies regardless of seller input.
        listing_data.price_multiplied_by_quantity = False

    client_ip = request.client.host if request else "unknown"
    user_agent = request.headers.get("user-agent", "unknown") if request else "unknown"
    agreement_metadata = build_agreement_metadata(current_user, client_ip, user_agent)

    listing_id_for_images = str(uuid.uuid4())

    # iter213 — Auto-promote any base64-encoded image to S3 so the DB never
    # stores base64 (and the Meta feed never falls back to the placeholder).
    # Images that are already https:// URLs are passed through untouched.
    promoted_images = await _promote_base64_images_to_s3(
        compress_image_list(listing_data.images),
        listing_id_for_images,
    )

    listing = Listing(
        id=listing_id_for_images,
        seller_id=current_user.id, title=listing_data.title, description=listing_data.description,
        category=listing_data.category, condition=listing_data.condition,
        starting_price=listing_data.starting_price, current_price=listing_data.starting_price,
        buy_now_price=listing_data.buy_now_price, images=promoted_images,
        location=listing_data.location, city=listing_data.city, region=listing_data.region,
        country=listing_data.country, postal_code=listing_data.postal_code,
        latitude=listing_data.latitude, longitude=listing_data.longitude,
        auction_end_date=listing_data.auction_end_date,
        shipping_info=listing_data.shipping_info,
        visit_availability=listing_data.visit_availability,
        # FEATURE PATCH v9 / Feature 4 — quantity field
        quantity=max(1, int(listing_data.quantity or 1)),
        multiply_hammer_by_quantity=bool(listing_data.multiply_hammer_by_quantity) and max(1, int(listing_data.quantity or 1)) > 1,
        # iter233 — Display-only "Lot price × Quantity" toggle.
        price_multiplied_by_quantity=bool(listing_data.price_multiplied_by_quantity) and max(1, int(listing_data.quantity or 1)) > 1,
        # Phase 6.0 / Task 3 — Storage Locker support
        listing_type=listing_data.listing_type or None,
        storage_metadata=listing_data.storage_metadata,
        currency=listing_data.currency if listing_data.currency else detect_currency_from_location(
            city=listing_data.city, region=listing_data.region, country=listing_data.country
        ),
        title_en=listing_data.title_en,
        title_fr=listing_data.title_fr,
        description_en=listing_data.description_en,
        description_fr=listing_data.description_fr,
    )
    listing_dict = listing.model_dump()

    # iter250 — Sanitize broker-supplied HTML in description fields BEFORE
    # persistence. Strips <script>, <iframe>, on*=, javascript:, … while
    # preserving the standard transactional formatting tags.
    from services.html_sanitizer import sanitize_user_html, sanitize_inline
    for _f in ("description", "description_en", "description_fr"):
        if listing_dict.get(_f):
            listing_dict[_f] = sanitize_user_html(listing_dict[_f])
    # Titles are render-safe text only — strip every tag.
    for _f in ("title", "title_en", "title_fr"):
        if listing_dict.get(_f):
            listing_dict[_f] = sanitize_inline(listing_dict[_f])


    # Phase 6.3 Task 2 — Storage locker sanitization. The frontend hides the
    # condition / quantity / deposit / shipping / visit fields for
    # storage_locker, but defend-in-depth here too: strip any legacy values
    # that may arrive from older clients or admin tooling so the DB schema
    # stays clean.
    if (listing_data.listing_type or "").lower() == "storage_locker":
        # For storage_locker, condition is meaningless — set to "as_is"
        # sentinel rather than None (the Listing model requires str).
        listing_dict["condition"] = "as_is"
        listing_dict["quantity"] = 1
        listing_dict["multiply_hammer_by_quantity"] = False
        listing_dict["shipping_info"] = None
        listing_dict["visit_availability"] = None
        listing_dict["requires_deposit"] = False
        listing_dict["deposit_amount"] = None
        listing_dict["deposit_type"] = None
        # iter219 — Hardcode `category="storage_locker"` so the facility
        # operator is never prompted to pick a retail niche. All storage
        # listings index under one canonical category for routing + analytics.
        listing_dict["category"] = "storage_locker"
        # iter219 — Buy Now Price is not supported on storage-locker auctions
        # (abandoned-property auctions are open-ended bidding only).
        listing_dict["buy_now_price"] = None

    # iter219 — Storage Locker visible content tags. Sanitize on the way in;
    # unknown values are dropped silently so the tag system stays OPTIONAL.
    from services.visible_content_tags import sanitize_visible_content_tags
    listing_dict["visible_content_tags"] = sanitize_visible_content_tags(
        getattr(listing_data, "visible_content_tags", None)
    )

    # iter283 — Universal section auto-tagging.
    # Stamp BOTH `listing_type` (if missing or non-canonical) AND `section`
    # so every listing routes to the right marketplace surface. This closes
    # the UNIT 205 bug: a storage unit created via the general create-form
    # used to land in `db.listings` with `listing_type=null`, which made it
    # invisible to /storage-auctions.
    from services.listing_sections import (
        infer_section,
        CANONICAL_TYPE,
        STORAGE_TYPES,
        VEHICLE_TYPES,
        LOT_TYPES,
    )
    _inferred_section = infer_section(listing_dict)
    listing_dict["section"] = _inferred_section
    # Only overwrite listing_type when it's missing OR when the current
    # value is incompatible with the inferred section (e.g. category=Storage
    # but listing_type=marketplace).
    _current_lt = (listing_dict.get("listing_type") or "").strip().lower()
    _aliases_by_section = {
        "storage":     STORAGE_TYPES,
        "vehicles":    VEHICLE_TYPES,
        "lots":        LOT_TYPES,
        "marketplace": ("marketplace",),
    }
    _allowed_aliases = _aliases_by_section.get(_inferred_section, ())
    if not _current_lt or _current_lt not in _allowed_aliases:
        canonical_key = {"storage": "storage", "vehicles": "vehicle",
                         "lots": "lots", "marketplace": "marketplace"}[_inferred_section]
        listing_dict["listing_type"] = CANONICAL_TYPE[canonical_key]

    # iter237/iter282 — auto-populate GeoJSON Point with seller-pin accuracy.
    # Priority chain (per iter282 Change 4):
    #   1. postal_code → Nominatim (most accurate; FSA-precise)
    #   2. city → CITY_COORDS centroid (rough fallback)
    #   3. neither resolves → leave `geo` UNSET so the listing is
    #      silently skipped on the map (never plotted at 0,0 or
    #      the map default — that would mislead buyers about
    #      seller location).
    # The `geo` field is indexed by 2dsphere and consumed by
    # /api/marketplace/items/geo via `$geoWithin`, which inherently
    # excludes documents missing the field.
    try:
        _geo = None
        _postal = (getattr(listing_data, "postal_code", "") or "").strip()
        if _postal:
            from services.geo_resolver import resolve_postal_code
            _coords = await resolve_postal_code(_postal)
            if _coords:
                _geo = {
                    "type": "Point",
                    "coordinates": [_coords["lng"], _coords["lat"]],
                    "city": listing_data.city or "",
                    "province": listing_data.region or "",
                    "source": "nominatim_postal",
                }
        if not _geo:
            from utils import build_geo_point
            _city_geo = build_geo_point(listing_data.city, province=listing_data.region)
            if _city_geo:
                _geo = {**_city_geo, "source": "city_centroid"}
        if _geo:
            listing_dict["geo"] = _geo
        # else: deliberately leave `geo` unset — map silently skips it.
    except Exception as _e:  # noqa: BLE001
        logger.warning(f"[iter282-geo] enrichment skipped for new listing: {_e}")

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

    # iter223 — Sandbox stamp. Demo creators' listings stay invisible to the
    # public marketplace; only the demo user themselves can see them inside
    # the real product surfaces.
    if _is_demo_creator:
        listing_dict["is_demo_sandbox"] = True
        listing_dict["is_demo"] = True  # legacy public-exclusion flag

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

    # iter265 Mission 1.4 — Non-blocking geo notification fan-out. Only
    # fires for listings that resolved real coordinates AND are publicly
    # visible (status=active). Demo/sandbox listings are skipped because
    # `is_demo_sandbox` excludes them from the public marketplace.
    # iter283 hotfix — `location` is a STRING per the Listing model
    # ("Montreal, QC"); coordinates live under `geo.coordinates` (iter237
    # GeoJSON Point). The old `(result.get("location") or {}).get(...)`
    # crashed with AttributeError on every new listing.
    _geo = result.get("geo")
    _has_coords = bool(
        isinstance(_geo, dict)
        and isinstance(_geo.get("coordinates"), (list, tuple))
        and len(_geo.get("coordinates") or []) == 2
    )
    if (
        result.get("status") == "active"
        and not result.get("is_demo_sandbox")
        and _has_coords
    ):
        try:
            from services.geo_notifications import notify_nearby_users
            import asyncio as _aio
            _aio.create_task(notify_nearby_users(result["id"], result, db))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[geo-notify] skipped for {result.get('id')}: {e}")

    # iter300 P2 — "Follow Seller" fan-out: alert followers when this
    # seller's listing goes live immediately (active). Pending-review
    # listings notify on admin approval instead (routes/admin_moderation.py).
    if result.get("status") == "active" and not result.get("is_demo_sandbox"):
        try:
            from services.follower_notify import notify_followers
            background_tasks.add_task(
                notify_followers, db,
                seller_id=current_user.id,
                listing_id=result["id"],
                listing_title=result.get("title", "New listing"),
                section="marketplace",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[follow-notify] skipped for {result.get('id')}: {e}")

    return result


@listings_router.get("/listings", response_model=List[Listing])
async def get_listings(
    category: Optional[str] = None, city: Optional[str] = None, region: Optional[str] = None,
    condition: Optional[str] = None, min_price: Optional[float] = None, max_price: Optional[float] = None,
    search: Optional[str] = None, sort: str = "created_at",
    limit: int = Query(50, ge=1, le=100), skip: int = Query(0, ge=0),
    currency: Optional[str] = None,
    tax_status: Optional[str] = None,        # "partner" | "standard" — UI filter
    buyer_province: Optional[str] = None,    # for "nearby_first" geo-sort
):
    db = get_db()
    # iter283 — Marketplace shows ALL listing types. Storage / vehicle
    # / lots listings are no longer walled off; section badges on the
    # cards help buyers distinguish. Section-specific surfaces filter
    # by their own listing_type list.
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

    # iter283 — Multi-item listings also surface in marketplace. Storage
    # walls were removed for universal dual-visibility per the spec.
    multi_query = {"status": "active"}
    if category:
        # iter309 D1 — Multi-lot category filter:
        # match any auction whose `categories[]` aggregate OR primary
        # `category` OR a nested lot.category contains the requested value.
        multi_query["$or"] = [
            {"category":            category},
            {"categories":          category},
            {"lots.category":       category},
        ]
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
        search_or = [{"title": {"$regex": _safe, "$options": "i"}}, {"description": {"$regex": _safe, "$options": "i"}}]
        if category:
            # Combine category $or + search $or with $and.
            existing_or = multi_query.pop("$or", [])
            multi_query["$and"] = [{"$or": existing_or}, {"$or": search_or}]
        else:
            multi_query["$or"] = search_or
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
                return (0, "", 0.0)
            # Normalise mixed datetime/string/number values so `<` is consistent
            # across heterogeneous rows. Returns a (type-bucket, str, num) tuple.
            if isinstance(v, datetime):
                try:
                    return (1, "", v.timestamp())
                except Exception:
                    return (1, "", 0.0)
            if isinstance(v, str):
                # Try ISO-8601 → epoch; otherwise compare lexically as string.
                try:
                    return (1, "", datetime.fromisoformat(v.replace("Z", "+00:00")).timestamp())
                except Exception:
                    return (2, v, 0.0)
            if isinstance(v, (int, float)):
                return (3, "", float(v))
            return (4, str(v), 0.0)
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
async def get_listing(listing_id: str, background_tasks: BackgroundTasks):
    """iter240 — Single round-trip listing fetch.

    Before: 3 sequential awaits (find_one → update_one views → users.find_one).
    After: 1 aggregation pipeline that $lookups the seller in the same RTT;
    the views increment is shipped to a BackgroundTask so it never blocks
    the response. p50 detail-page latency drops from ~600ms → ~80ms.
    """
    now = _time.time()
    cached = _listing_cache.get(listing_id)
    if cached and (now - cached["ts"]) < _LISTING_CACHE_TTL:
        return cached["data"]

    db = get_read_db()
    pipeline = [
        {"$match": {"id": listing_id}},
        {"$lookup": {
            "from": "users",
            "localField": "seller_id",
            "foreignField": "id",
            "as": "_seller",
            "pipeline": [{"$project": {
                "_id": 0,
                "is_partner": 1,
                "partner_verification_status": 1,
                "partner_company_name": 1,
                "partner_buyer_premium_pct": 1,
                "is_vehicle_dealer": 1,
                "is_storage_facility": 1,
                "is_tax_registered": 1,
                "account_type": 1,
                "subscription_tier": 1,
                "platform_fee_paid": 1,
                "partner_subscription_active": 1,
                # iter283 — Public seller-info fields surfaced on the
                # listing detail "Seller Information" card.
                "website": 1,
                "company_name": 1,
                "province": 1,
                "city": 1,
            }}],
        }},
        {"$project": {"_id": 0}},
        {"$limit": 1},
    ]
    docs = await db.listings.aggregate(pipeline).to_list(length=1)
    if not docs:
        raise HTTPException(status_code=404, detail="Listing not found")
    listing_doc = docs[0]
    seller_arr = listing_doc.pop("_seller", []) or []
    seller = seller_arr[0] if seller_arr else {}

    if isinstance(listing_doc.get("created_at"), str):
        listing_doc["created_at"] = datetime.fromisoformat(listing_doc["created_at"])
    if isinstance(listing_doc.get("auction_end_date"), str):
        listing_doc["auction_end_date"] = datetime.fromisoformat(listing_doc["auction_end_date"])

    # In-process enrichment using the seller doc already loaded by $lookup.
    # iter283 — infer the listing context (storage / vehicle / general)
    # from listing shape so a multi-flagged seller (e.g. admin who is
    # is_vehicle_dealer AND is_storage_facility) gets the badge that
    # matches the LISTING, not their most-aggressive seller flag.
    from services.listing_seller_enrichment import enrich_listing_with_seller
    from services.listing_sections import infer_seller_context
    listing_doc = enrich_listing_with_seller(
        listing_doc, seller, infer_seller_context(listing_doc),
    )

    # iter283-emergency-detail — Defensive coercion before Pydantic
    # validation. The Listing model expects `location` as a STRING
    # ("City, Province") but some seed paths (and historical imports)
    # have written it as a GeoJSON-shaped dict. The structured shape
    # belongs under `geo` per iter237. Reshape inline so we never 500
    # on a single-listing fetch.
    _loc = listing_doc.get("location")
    if isinstance(_loc, dict):
        _city = _loc.get("city") or listing_doc.get("city") or ""
        _prov = _loc.get("province") or listing_doc.get("region") or ""
        listing_doc["location"] = (
            f"{_city}, {_prov}".strip(", ") if (_city or _prov) else ""
        )

    # Fire-and-forget view increment — never blocks the response.
    background_tasks.add_task(_increment_listing_views, listing_id)

    result = Listing(**listing_doc)
    _listing_cache[listing_id] = {"data": result, "ts": now}
    return result


async def _increment_listing_views(listing_id: str) -> None:
    """iter240 — Best-effort view counter. Swallows errors so a transient
    Mongo blip on the write path never propagates to a user-facing 5xx."""
    try:
        await get_db().listings.update_one(
            {"id": listing_id}, {"$inc": {"views": 1}}
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[iter240] view-increment failed for {listing_id}: {e}")


@listings_router.put("/listings/{listing_id}", response_model=Listing)
async def update_listing(listing_id: str, updates: Dict[str, Any], current_user: User = Depends(get_current_user)):
    db = get_db()
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing["seller_id"] != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Not authorized")
    allowed_fields = ["title", "description", "category", "condition", "images", "location", "city", "region", "country", "postal_code", "status",
                      "title_en", "title_fr", "description_en", "description_fr"]
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}

    # iter250 — Sanitize broker-supplied HTML in description fields BEFORE
    # persistence (UPDATE path).
    from services.html_sanitizer import sanitize_user_html, sanitize_inline
    for _f in ("description", "description_en", "description_fr"):
        if update_data.get(_f):
            update_data[_f] = sanitize_user_html(update_data[_f])
    for _f in ("title", "title_en", "title_fr"):
        if update_data.get(_f):
            update_data[_f] = sanitize_inline(update_data[_f])

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
    if listing["seller_id"] != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
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

    if listing.get("seller_id") != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
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


# ========== iter389 · STATELESS S3 IMAGE UPLOAD ==========
# The multi-item / vehicle / general listing CREATE flows can now upload
# each dropped image to S3 BEFORE calling the JSON create endpoint,
# collecting the returned public URLs and shipping them (never raw base64)
# in the create payload. This closes the base64-in-Mongo escape hatch
# nightly sweeps kept flagging.
LISTING_IMAGE_UPLOAD_MAX_BYTES = 8 * 1024 * 1024  # 8 MB per file


@listings_router.post("/uploads/listing-image")
async def upload_listing_image_stateless(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload a single image to S3 and return its public URL.

    Contract:
        Request:  multipart/form-data · one `file` field
        Response: `{ "url": "https://bidvex-marketplace-images.s3.us-…/staged/<userid>/<idx>-<rand>.jpg" }`

    Used by CREATE flows that don't yet have a listing_id (multi-item,
    vehicle, or single-item listing wizards). The frontend uploads each
    dropped image with a POST here, collects the resulting URLs, and
    ships them as `lot.images: [<url>, …]` in the JSON create payload.

    Server never writes base64 to MongoDB — the create endpoint hard-
    rejects any base64 that sneaks into an image array (see
    `_reject_base64_in_images` below).
    """
    if not file:
        raise HTTPException(status_code=400, detail={"error": "no_file"})
    if file.content_type and not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail={
            "error": "not_an_image",
            "message_en": "Uploaded file must be an image (JPEG, PNG, or WebP).",
            "message_fr": "Le fichier doit être une image (JPEG, PNG ou WebP).",
        })

    from services.s3_service import upload_image_to_s3
    # Namespace staged uploads under the caller's user id so orphaned
    # uploads can be pruned later without touching real listings.
    staged_id = f"staged-{current_user.id}"
    idx = int(datetime.now(timezone.utc).timestamp() * 1000) % 100000

    try:
        url = await upload_image_to_s3(file, staged_id, idx)
    except ValueError as e:
        raise HTTPException(status_code=400, detail={"error": "invalid_image", "detail": str(e)})
    except Exception as e:
        logger.error("[uploads/listing-image] S3 upload failed: %s", e)
        raise HTTPException(status_code=502, detail={"error": "s3_upload_failed"})

    return {"url": url}


# ========== iter389 · BASE64-IN-IMAGES API GUARDRAIL ==========
def _looks_like_base64_image(value: Any) -> bool:
    """Return True if `value` is a base64-encoded image (data URL or raw)."""
    if not isinstance(value, str) or not value:
        return False
    # Data URL is unambiguous — reject on sight.
    if value.startswith("data:image/") or value.startswith("data:application/"):
        return True
    # Not-a-URL long strings that look like base64 payloads.
    if value.startswith("http://") or value.startswith("https://") or value.startswith("/"):
        return False
    # Anything longer than 500 chars that isn't a URL is almost certainly base64.
    if len(value) > 500:
        return True
    return False


def _reject_base64_in_images(images: Any, path: str) -> None:
    """Raise HTTP 400 if any element of `images` is a base64 payload.

    iter389 — Hard guardrail against the "base64 in Mongo" regression. The
    frontend MUST upload images to `/api/uploads/listing-image` first and
    ship the returned S3 URLs. If ANY element in an image array looks
    like base64, we refuse the whole create request with a clear message.
    """
    if not images:
        return
    if not isinstance(images, (list, tuple)):
        return
    for i, entry in enumerate(images):
        if _looks_like_base64_image(entry):
            raise HTTPException(status_code=400, detail={
                "error": "base64_image_rejected",
                "message_en": (
                    "Image at "
                    f"{path}[{i}] was submitted as base64 data. "
                    "Upload images to /api/uploads/listing-image first and "
                    "submit the returned S3 URLs instead."
                ),
                "message_fr": (
                    "L'image à "
                    f"{path}[{i}] a été soumise en base64. "
                    "Téléversez d'abord les images vers /api/uploads/listing-image "
                    "puis soumettez les URL S3 retournées."
                ),
                "path": f"{path}[{i}]",
            })


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

    # iter395 — Two-pillar Trust Gate: creating a listing requires phone
    # verified AND card on file, identical to the single-item listing
    # flow (see services.listings_service::validate_listing_permissions).
    from services.trust_gate import require_trust_verified
    await require_trust_verified(db, current_user, action="list")

    # iter223 — Demo Sandbox (multi-item creation). Same isolated-visibility
    # treatment as single-listing flow.
    user_demo_row = await db.users.find_one(
        {"id": current_user.id},
        {"_id": 0, "is_demo_account": 1, "account_type": 1},
    )
    _is_demo_creator_multi = bool(user_demo_row and user_demo_row.get("is_demo_account"))

    # iter217 — Quebec Bill 96 compliance — French title required for QC listings
    # iter310 — Auto-translate missing French copy before the hard-gate runs.
    from services.bill96_autofill import autofill_qc_french_copy
    _bill96_autofill_result_multi = await autofill_qc_french_copy(listing_data)
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

    # iter389 — Hard-reject any base64 image payloads. The frontend must
    # upload images to /api/uploads/listing-image first and submit S3 URLs.
    _reject_base64_in_images(getattr(listing_data, "images", None) or [], "images")
    for _lidx, _lot in enumerate(listing_data.lots or []):
        _lot_imgs = getattr(_lot, "images", None) if not isinstance(_lot, dict) else _lot.get("images")
        _reject_base64_in_images(_lot_imgs or [], f"lots[{_lidx}].images")

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

    # iter309 D1 — Aggregate per-lot categories into the parent listing.
    # Primary `category` field falls back to the most common lot category
    # (or the seller-supplied auction-level value, or "Other") for legacy
    # search/sort. `categories` is the distinct set for tag rendering.
    from collections import Counter as _Counter
    _lot_cat_counts = _Counter()
    for _lot in lots_with_end_time:
        _lc = (_lot.get("category") or "").strip() if isinstance(_lot, dict) else ""
        if _lc:
            _lot_cat_counts[_lc] += 1
    _categories_aggregate = sorted({c for c in _lot_cat_counts}, key=lambda c: -_lot_cat_counts[c])
    if not _categories_aggregate and listing_data.category:
        _categories_aggregate = [listing_data.category]
    _primary_category = (
        listing_data.category
        or (_categories_aggregate[0] if _categories_aggregate else "Other")
    )
    # Backfill lot.category from the primary when missing — keeps every lot
    # tagged so faceted filters can rely on lot.category alone.
    for _lot in lots_with_end_time:
        if isinstance(_lot, dict) and not (_lot.get("category") or "").strip():
            _lot["category"] = _primary_category
    if _primary_category and _primary_category not in _categories_aggregate:
        _categories_aggregate.insert(0, _primary_category)

    listing = MultiItemListing(
        seller_id=current_user.id,
        title=listing_data.title,
        description=listing_data.description,
        category=_primary_category,
        categories=_categories_aggregate,
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
        # iter233 — Display-only "Lot price × Quantity" toggle (listing-level).
        quantity=max(1, int(listing_data.quantity or 1)),
        multiply_hammer_by_quantity=bool(listing_data.multiply_hammer_by_quantity) and max(1, int(listing_data.quantity or 1)) > 1,
        price_multiplied_by_quantity=bool(listing_data.price_multiplied_by_quantity) and max(1, int(listing_data.quantity or 1)) > 1,
    )

    listing_dict = listing.model_dump()

    listing_dict = listing.model_dump()

    # iter250 — Sanitize broker-supplied HTML on multi-item listings too.
    from services.html_sanitizer import (
        sanitize_user_html as _sanitize_html_mi,
        sanitize_inline as _sanitize_text_mi,
    )
    for _f in ("description", "description_en", "description_fr"):
        if listing_dict.get(_f):
            listing_dict[_f] = _sanitize_html_mi(listing_dict[_f])
    for _f in ("title", "title_en", "title_fr"):
        if listing_dict.get(_f):
            listing_dict[_f] = _sanitize_text_mi(listing_dict[_f])
    # Lot-level descriptions also originate from broker input.
    for _lot in listing_dict.get("lots", []) or []:
        if isinstance(_lot, dict):
            if _lot.get("description"):
                _lot["description"] = _sanitize_html_mi(_lot["description"])
            if _lot.get("title"):
                _lot["title"] = _sanitize_text_mi(_lot["title"])

    listing_dict["agreement_metadata"] = agreement_metadata
    serialise_datetimes(listing_dict)

    # iter211 P4 — tag demo accounts' multi-item listings
    from services.demo_filter import tag_listing_if_demo
    await tag_listing_if_demo(db, current_user.id, listing_dict)

    # iter223 — Sandbox stamp for multi-item. Public feeds exclude
    # `is_demo_sandbox: true`; the demo creator still sees their own.
    if _is_demo_creator_multi:
        listing_dict["is_demo_sandbox"] = True
        listing_dict["is_demo"] = True

    # iter343 BUG-1 — geo enrichment (city centroid) so multi-lot auctions
    # appear in "Search by Map". Parity with single-listing creation.
    try:
        from utils import build_geo_point
        _geo = build_geo_point(listing_dict.get("city"), province=listing_dict.get("region"))
        if _geo:
            listing_dict["geo"] = {**_geo, "source": "city_centroid"}
    except Exception as _ge:  # noqa: BLE001
        logger.warning(f"[iter343-geo] multi-item geo enrichment skipped: {_ge}")

    # iter394 — Enrich with the live seller record so seller_account_type
    # + sibling booleans are stamped correctly from day one. Prevents the
    # persistence drift class of bugs (iter392) that made individual-seller
    # lots incorrectly appear "Taxable" in the fees-preview popover.
    try:
        from services.listing_seller_enrichment import enrich_listing_async
        listing_dict = await enrich_listing_async(db, listing_dict, "lots")
    except Exception as _ee:  # noqa: BLE001 — never block a create on enrichment failure
        logger.warning(f"[iter394] multi-item seller enrichment skipped: {_ee}")

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
        raw_lots = [lot_item.model_dump() if hasattr(lot_item, "model_dump") else lot_item for lot_item in listing_data.lots]
        background_tasks.add_task(
            _translate_multi_listing_bg,
            db, listing.id, listing_data.title, listing_data.description,
            raw_lots, listing_data.content_language or "en",
        )

    # iter300 P2 — "Follow Seller" fan-out for immediately-active lots.
    if listing_dict.get("status") == "active" and not listing_dict.get("is_demo_sandbox"):
        try:
            from services.follower_notify import notify_followers
            background_tasks.add_task(
                notify_followers, db,
                seller_id=current_user.id,
                listing_id=listing.id,
                listing_title=listing_dict.get("title", "New listing"),
                section="lots",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[follow-notify] skipped for {listing.id}: {e}")

        # iter401 — Flow 1 Buyer Interest emails (real-time). Fires only
        # when the listing goes live immediately (status="active") and
        # never for demo sandbox lots. Rate-limited to 1/user/hour inside
        # the dispatcher itself.
        try:
            from services.marketing_flows import dispatch_buyer_interest_emails
            background_tasks.add_task(
                dispatch_buyer_interest_emails, db,
                listing_id=listing.id,
                listing_type="multi_item",
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[iter401 buyer-interest] skipped for {listing.id}: {e}")

    return listing


@listings_router.get("/multi-item-listings")
async def get_multi_item_listings(
    limit: int = Query(50, ge=1, le=100),
    skip: int = Query(0, ge=0),
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
    ending_soon: bool = False,  # iter298 BUG 1 — active lots ending within 24h (dynamic)
):
    db = get_read_db()
    has_filters = any([category, region, city, currency, search, seller_id, min_price, max_price, seller_account_type, promoted_first, ending_soon])

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

    # Phase 6.2 Task 1 — Storage locker auctions are walled off from the
    # multi-item listings feed. Visible only on /storage-auctions.
    query["listing_type"] = {"$ne": "storage_locker"}

    # iter298 BUG 1 — "Ending Soon": active events whose auction_end_date
    # falls within the next 24 hours. Computed dynamically at query time
    # (handles both ISO-string and datetime storage conventions).
    if ending_soon:
        _es_now = datetime.now(timezone.utc)
        _es_cutoff = _es_now + timedelta(hours=24)
        query["status"] = "active"
        query["$and"] = (query.get("$and") or []) + [{
            "$or": [
                {"auction_end_date": {"$gt": _es_now.isoformat(), "$lte": _es_cutoff.isoformat()}},
                {"auction_end_date": {"$gt": _es_now, "$lte": _es_cutoff}},
            ]
        }]

    if category:
        # Phase 5 Hotfix v5 — support comma-separated list + case/whitespace
        # tolerant matching. Sidebar emits `name_en` values which historically
        # had stray whitespace (e.g. "Furniture "). Normalize on both sides.
        from re import escape as _re_escape
        cat_list = [c.strip() for c in str(category).split(",") if c.strip()]
        if cat_list:
            query["category"] = {
                "$regex": "|".join(f"^\\s*{_re_escape(c)}\\s*$" for c in cat_list),
                "$options": "i",
            }
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
async def get_multi_item_listing(listing_id: str, background_tasks: BackgroundTasks):
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

    # iter405 — Fire-and-forget view increment (parity with the single-item
    # GET endpoint above); never blocks the response.
    background_tasks.add_task(_increment_multi_item_listing_views, listing_id)

    return MultiItemListing(**listing)


async def _increment_multi_item_listing_views(listing_id: str) -> None:
    """iter405 — Best-effort multi-item view counter. Mirrors
    ``_increment_listing_views``; swallows errors so a transient Mongo blip
    on the write path never propagates to a user-facing 5xx."""
    try:
        await get_db().multi_item_listings.update_one(
            {"id": listing_id}, {"$inc": {"views": 1}}
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[iter405] multi-item view-increment failed for {listing_id}: {e}")


# iter367 P1 — Live activity ticker for multi-lot auction pages.
# Returns the newest bid events across all lots in an auction so the
# redesigned detail page can show a "who bid on what, when" ticker.
@listings_router.get("/lots/{auction_id}/recent-activity")
async def get_multi_lot_recent_activity(auction_id: str, limit: int = 10):
    """Return the last N bid events across all lots in a multi-lot auction.

    Each row includes lot_id, lot_title, amount, bidder_alias (privacy-safe
    display name — never the full name), timestamp (ISO), and time_ago
    (human string). Sorted newest first. Frontend polls every 15s.
    """
    from datetime import datetime, timezone
    db = get_db()
    limit = max(1, min(50, int(limit)))
    listing = await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0, "id": 1, "lots": 1})
    if not listing:
        raise HTTPException(status_code=404, detail="Auction not found")
    lots = listing.get("lots") or []
    lot_titles = {
        int(lot.get("lot_number", 0)): (lot.get("title") or f"Lot #{lot.get('lot_number')}")
        for lot in lots
    }

    # Pull recent bids for this multi-lot auction.
    # REGRESSION FIX (iter376) — multi-lot bids are stored in `db.lot_bids`
    # keyed by `listing_id`, not in the single-item `db.bids` collection
    # keyed by `auction_id`. Reading the wrong collection meant the ticker
    # always showed "No recent bids — be the first!" for multi-lot auctions.
    bid_docs = await db.lot_bids.find(
        {"listing_id": auction_id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(limit)

    # Enrich with masked bidder aliases (privacy-first: first name +
    # initial only; fall back to "Bidder ####" derived from the last 4
    # chars of their id if no name).
    bidder_ids = list({b.get("bidder_id") for b in bid_docs if b.get("bidder_id")})
    aliases: dict[str, str] = {}
    if bidder_ids:
        async for u in db.users.find(
            {"id": {"$in": bidder_ids}},
            {"_id": 0, "id": 1, "name": 1, "first_name": 1},
        ):
            uid = u.get("id")
            name = (u.get("first_name") or (u.get("name") or "").split(" ")[0] or "").strip()
            if name:
                aliases[uid] = f"{name[0].upper()}{name[1:2].lower()}{'*' * max(0, len(name) - 2)}"
            else:
                aliases[uid] = f"Bidder {uid[-4:].upper()}" if uid else "Bidder"

    now = datetime.now(timezone.utc)
    events = []
    for b in bid_docs:
        lot_num = b.get("lot_number")
        try:
            lot_num_int = int(lot_num) if lot_num is not None else None
        except (TypeError, ValueError):
            lot_num_int = None
        ts = b.get("created_at")
        ts_dt = None
        if isinstance(ts, str):
            try:
                ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                ts_dt = None
        elif isinstance(ts, datetime):
            ts_dt = ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)

        seconds_ago = int((now - ts_dt).total_seconds()) if ts_dt else 0
        if seconds_ago < 60:
            time_ago = f"{max(seconds_ago, 1)}s"
        elif seconds_ago < 3600:
            time_ago = f"{seconds_ago // 60}m"
        elif seconds_ago < 86400:
            time_ago = f"{seconds_ago // 3600}h"
        else:
            time_ago = f"{seconds_ago // 86400}d"

        events.append({
            "lot_id": lot_num_int,
            "lot_number": lot_num_int,
            "lot_title": lot_titles.get(lot_num_int, f"Lot #{lot_num_int}" if lot_num_int is not None else "—"),
            "amount": float(b.get("amount") or 0),
            "bidder_alias": aliases.get(b.get("bidder_id"), "Bidder"),
            "timestamp": ts if isinstance(ts, str) else (ts_dt.isoformat() if ts_dt else None),
            "time_ago": time_ago,
        })

    return {
        "auction_id": auction_id,
        "events": events,
        "generated_at": now.isoformat(),
    }


@listings_router.get("/multi-item-listings/{listing_id}/terms/pdf")
async def export_auction_terms_pdf(listing_id: str):
    """iter371 — Export auction terms as a PDF using reportlab.

    The previous implementation depended on weasyprint (which needs Pango /
    Cairo / GDK-Pixbuf system packages that aren't in this container image).
    Rewritten in pure reportlab so the endpoint works out of the box in every
    environment.
    """
    from fastapi.responses import Response
    from io import BytesIO
    from html import unescape
    import re

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, HRFlowable,
    )
    from reportlab.lib.enums import TA_CENTER

    db = get_db()
    try:
        listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            raise HTTPException(status_code=404, detail="Auction not found")

        seller = await db.users.find_one({"id": listing["seller_id"]}, {"_id": 0, "password": 0}) or {}
        seller_name = seller.get("company_name") or seller.get("name") or "Unknown Seller"

        terms_en = listing.get("auction_terms_en", "") or ""
        terms_fr = listing.get("auction_terms_fr", "") or ""

        if not terms_en and not terms_fr:
            raise HTTPException(status_code=404, detail="No auction terms available")

        # ---- Sanitize + tag-strip helper --------------------------------
        # We can't render raw HTML in reportlab paragraphs, so we normalise
        # markdown-ish input into plain paragraphs while keeping <b>/<i>/<br>
        # (reportlab understands those). Strips scripts/styles first.
        def _clean(html_text: str) -> str:
            if not html_text:
                return ""
            # Kill script/style blocks entirely
            html_text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_text,
                                flags=re.IGNORECASE | re.DOTALL)
            # Convert block-level tags to line breaks so structure survives.
            html_text = re.sub(r"</?(?:p|div|section|article|header|footer|ul|ol|table|tr|td|th|h[1-6])[^>]*>",
                                "<br/>", html_text, flags=re.IGNORECASE)
            html_text = re.sub(r"<li[^>]*>", "&#8226; ", html_text, flags=re.IGNORECASE)
            html_text = re.sub(r"</li>", "<br/>", html_text, flags=re.IGNORECASE)
            # Whitelist inline tags that reportlab supports natively.
            keep = ("br", "b", "i", "u", "strong", "em")
            def replace_tag(match: "re.Match") -> str:
                tag = match.group(1).lower()
                # normalize <strong>/<em> aliases
                if tag in keep:
                    slash = "/" if match.group(0).startswith("</") else ""
                    return f"<{slash}{tag}/>" if tag == "br" else f"<{slash}{tag}>"
                return ""
            html_text = re.sub(r"</?([a-zA-Z][a-zA-Z0-9]*)[^>]*>", replace_tag, html_text)
            html_text = unescape(html_text)
            # Collapse runs of whitespace / consecutive <br/> to at most two.
            html_text = re.sub(r"(\s*<br\s*/?>\s*){3,}", "<br/><br/>", html_text)
            html_text = re.sub(r"[\r\n\t]+", " ", html_text)
            html_text = re.sub(r" {2,}", " ", html_text)
            return html_text.strip()

        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=A4,
            leftMargin=2 * cm, rightMargin=2 * cm,
            topMargin=2 * cm, bottomMargin=2 * cm,
            title=f"BidVex Auction Terms – {listing.get('title', listing_id)}",
        )

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TitleBidVex", parent=styles["Title"],
            textColor=colors.HexColor("#2563eb"), fontName="Helvetica-Bold",
            fontSize=20, alignment=TA_CENTER, spaceAfter=8,
        )
        subtitle_style = ParagraphStyle(
            "SubtitleBidVex", parent=styles["Normal"],
            fontSize=13, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4,
        )
        meta_style = ParagraphStyle(
            "MetaBidVex", parent=styles["Normal"],
            fontSize=10, textColor=colors.HexColor("#555555"),
            alignment=TA_CENTER, spaceAfter=2,
        )
        section_style = ParagraphStyle(
            "SectionBidVex", parent=styles["Heading2"],
            textColor=colors.HexColor("#2563eb"), fontName="Helvetica-Bold",
            fontSize=15, spaceBefore=18, spaceAfter=10,
        )
        body_style = ParagraphStyle(
            "BodyBidVex", parent=styles["BodyText"],
            fontSize=10.5, leading=15, spaceAfter=6,
        )
        footer_style = ParagraphStyle(
            "FooterBidVex", parent=styles["Normal"],
            fontSize=9, textColor=colors.HexColor("#777777"),
            alignment=TA_CENTER, spaceBefore=20,
        )

        story = [
            Paragraph("BidVex Auction Platform", title_style),
            Paragraph(listing.get("title", "Auction"), subtitle_style),
            Paragraph(f"Hosted by: {seller_name}", meta_style),
            Paragraph(f"Auction ID: {listing_id}", meta_style),
            Spacer(1, 6),
            HRFlowable(width="100%", thickness=1.5, color=colors.HexColor("#2563eb")),
            Spacer(1, 14),
        ]

        if terms_en:
            story.append(Paragraph("Terms &amp; Conditions (English)", section_style))
            for block in _clean(terms_en).split("<br/><br/>"):
                block = block.strip()
                if not block:
                    continue
                story.append(Paragraph(block, body_style))
                story.append(Spacer(1, 4))

        if terms_fr:
            story.append(Spacer(1, 8))
            story.append(Paragraph("Termes et Conditions (Fran\u00e7ais)", section_style))
            for block in _clean(terms_fr).split("<br/><br/>"):
                block = block.strip()
                if not block:
                    continue
                story.append(Paragraph(block, body_style))
                story.append(Spacer(1, 4))

        story.append(Spacer(1, 12))
        story.append(HRFlowable(width="100%", thickness=0.6, color=colors.HexColor("#dddddd")))
        story.append(Paragraph(
            "This document was generated by BidVex Auction Platform. "
            "For questions, please contact the auctioneer listed above.",
            footer_style,
        ))

        doc.build(story)
        pdf_bytes = buffer.getvalue()
        buffer.close()

        safe_filename = re.sub(r"[^a-z0-9_-]+", "-", (listing.get("title") or listing_id).lower())[:60]
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="bidvex-terms-{safe_filename}.pdf"'},
        )
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error generating auction terms PDF: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate PDF: {str(e)}")


# ========== AUCTION AGREEMENT PERSISTENCE ==========

@listings_router.post("/multi-item-listings/{listing_id}/accept-terms")
async def accept_auction_terms(listing_id: str, current_user: User = Depends(get_current_user)):
    """Record that a user has accepted the auction terms for a specific auction.

    iter400 — Accepting ANY listing T&C now ALSO satisfies the platform-level
    Trust Gate terms pillar. Rationale: the platform T&C is a strict subset
    of every seller's per-auction T&C (both bind the user to the same
    marketplace-wide obligations). If a user is legally accepting the more
    specific per-auction terms, they are implicitly accepting the platform
    terms; there is no coherent state where a user has accepted an auction
    T&C but is still refused for lacking a global acceptance.

    We stamp `platform_terms_accepted_at` (idempotent — only on first accept)
    so the Trust Gate `terms_accepted` pillar flips to True in one shot.
    """
    db = get_db()
    listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0, "id": 1, "title": 1})
    if not listing:
        raise HTTPException(status_code=404, detail="Auction not found")

    now_iso = datetime.now(timezone.utc).isoformat()
    agreement_key = f"auction_agreements.{listing_id}"

    # iter400 — atomic update: stamp per-auction agreement AND (only if
    # missing) stamp platform_terms_accepted_at + version. Using $set on
    # the auction key and a conditional $setOnInsert-style guard via
    # two-step so we don't overwrite an earlier platform acceptance.
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {agreement_key: now_iso}},
    )
    # Only stamp platform_terms_accepted_at if it isn't already set — this
    # preserves the ORIGINAL acceptance timestamp for audit purposes.
    await db.users.update_one(
        {"id": current_user.id,
         "$or": [
             {"platform_terms_accepted_at": {"$exists": False}},
             {"platform_terms_accepted_at": None},
             {"platform_terms_accepted_at": ""},
         ]},
        {"$set": {
            "platform_terms_accepted_at":  now_iso,
            "platform_terms_version":      "v1",
            "platform_terms_last_seen_at": now_iso,
            "platform_terms_source":       f"listing_accept:{listing_id}",
        }},
    )

    return {
        "success": True,
        "message": "Auction terms accepted",
        "auction_id": listing_id,
        "accepted_at": now_iso,
        "platform_terms_accepted": True,
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
    if listing["seller_id"] != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
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
    if listing["seller_id"] != current_user.id and getattr(current_user, "role", None) not in ("admin", "super_admin"):
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
    if listing["seller_id"] != current_user.id and current_user.role not in ("admin", "super_admin"):
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
    if listing["seller_id"] != current_user.id and current_user.role not in ("admin", "super_admin"):
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
    if current_user.role not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")

    db = get_db()
    import asyncio as _aio
    from services.translation_service import backfill_listing_translations

    # Run in background to avoid timeout
    _aio.ensure_future(backfill_listing_translations(db))

    return {"success": True, "message": "Backfill started in background. Check server logs for progress."}
