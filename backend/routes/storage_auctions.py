"""
BidVex Storage Auction Routes — iteration 169
=============================================
All endpoints under the /api prefix:

PUBLIC
  GET  /api/storage-auctions                    list active (filterable, sortable)
  GET  /api/storage-auctions/provinces          province counts
  GET  /api/storage-auctions/{id}               single auction detail
  GET  /api/storage-auctions/{id}/bids          anonymized bid history
  GET  /api/storage-facilities/{id}             public facility profile

BUYER (auth)
  POST /api/storage-auctions/{id}/bid           place proxy bid
  GET  /api/storage-auctions/my-bids            my active bids
  GET  /api/storage-auctions/won                my won auctions
  POST /api/storage-auctions/{id}/payment       record payment intent

FACILITY (auth)
  POST /api/storage-facilities/register         register as facility
  GET  /api/storage-facilities/me               my profile + status
  POST /api/storage-facilities/auctions         create new auction
  GET  /api/storage-facilities/my-auctions      my listed auctions
  PUT  /api/storage-facilities/auctions/{id}    edit (only before start)
  DELETE /api/storage-facilities/auctions/{id}  cancel (only before start)
  GET  /api/storage-facilities/auctions/{id}/bids   bids on my auction
  GET  /api/storage-facilities/dashboard        revenue + stats

ADMIN
  GET  /api/admin/storage-facilities            list all
  POST /api/admin/storage-facilities/{id}/verify    approve
  PUT  /api/admin/storage-facilities/{id}/suspend   suspend
  GET  /api/admin/storage-auctions              list all
  PUT  /api/admin/storage-auctions/{id}/cancel  admin cancel
"""
import logging
import os
import re
import shutil
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, BackgroundTasks, Request
)
from fastapi.responses import FileResponse

from deps import User, get_current_user, get_current_user_optional, get_db, jwt_secret, security
from fastapi.security import HTTPAuthorizationCredentials
from jose import jwt, JWTError, ExpiredSignatureError
from rate_limit import limiter as _limiter
from models.storage_auction import (
    StorageFacilityRegister, StorageAuctionCreate, StorageBidPayload, StorageDepositRequest,
    UNIT_SIZES, UNIT_TYPES, PAYMENT_METHODS, AUCTION_STATUSES, CANADIAN_PROVINCES,
    REGISTRATION_TYPES,
)
from services.storage_pricing import calculate_storage_pricing
from services.storage_auction_service import place_bid as _place_bid_proxy
from services.storage_deposit_service import (
    create_deposit_hold,
    get_existing_deposit,
    release_deposits_on_close,
    forfeit_deposit,
)
from services.visible_content_tags import (
    sanitize_visible_content_tags as _sanitize_visible_content_tags_inline,
    ALLOWED_CONTENT_TAGS as _ALLOWED_CONTENT_TAGS,
)

logger = logging.getLogger(__name__)

storage_router = APIRouter()

UPLOAD_ROOT = "/app/uploads/storage-auctions"
ALLOWED_PHOTO_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_PHOTO_BYTES = 8 * 1024 * 1024  # 8 MB per photo
MAX_PHOTOS_PER_AUCTION = 10

# iter212 — Storage Facility Business-Registration documents
# iter273 — PRIMARY upload root moved to `/app/uploads/storage_facilities/`
#           (persistent mount per iter267) so files survive container
#           redeployments. The legacy `/app/backend/uploads/...` path is
#           kept as a search-only candidate to serve docs uploaded
#           before iter273.
FACILITY_DOC_ROOT_PERSISTENT = Path("/app/uploads/storage_facilities")
FACILITY_DOC_ROOT_REL = Path("uploads/storage_facilities")           # legacy, relative
FACILITY_DOC_ROOT_ABS = Path("/app/backend/uploads/storage_facilities")  # legacy, absolute
ALLOWED_FACILITY_DOC_MIME = {
    "application/pdf",
    "image/png", "image/jpeg", "image/jpg", "image/webp",
}
MAX_FACILITY_DOC_BYTES = 10 * 1024 * 1024  # 10 MB


# ─────────────────────────────────────────────────────────────
# helpers
# ─────────────────────────────────────────────────────────────

async def _require_admin(current_user: User = Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def _facility_for_user(db, user_id: str):
    return await db.storage_facilities.find_one({"owner_user_id": user_id}, {"_id": 0})


async def _require_verified_facility(current_user: User = Depends(get_current_user)):
    db = get_db()
    fac = await _facility_for_user(db, current_user.id)
    if not fac:
        raise HTTPException(status_code=403, detail="No facility profile found for this account")
    if fac.get("status") != "verified":
        raise HTTPException(
            status_code=403,
            detail={
                "error": "facility_not_verified",
                "message_en": "Your facility account is not yet verified by BidVex.",
                "message_fr": "Votre compte de facilité n'est pas encore vérifié par BidVex.",
            },
        )
    # iter212 — Provincial Business Registration must also be verified.
    # Existing facilities are grandfathered: the absence of this field in the
    # doc (legacy data) is treated as already-verified so we don't lock them
    # out retroactively. Only NEW facilities that registered after iter212
    # get the explicit `False` → blocked behaviour.
    reg_verified = fac.get("company_registration_verified")
    if reg_verified is False:  # explicit False — set on registration after iter212
        raise HTTPException(
            status_code=403,
            detail={
                "error": "company_registration_not_verified",
                "message_en": (
                    "Your business-registration document is awaiting admin review. "
                    "You'll be able to list units once it is verified."
                ),
                "message_fr": (
                    "Votre document d'enregistrement d'entreprise est en attente d'examen "
                    "par l'administrateur. Vous pourrez lister des unités une fois qu'il sera vérifié."
                ),
                "settings_url": "/storage-auctions/register-facility",
            },
        )
    return fac


def _now():
    return datetime.now(timezone.utc)


def _parse_dt(v):
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _resolve_status(auction: dict) -> str:
    """Compute live status from time fields.

    iter222 — Defensive: storage lockers from the `listings` collection
    don't carry `start_time` (they go live immediately on create); accept
    `auction_end_date` as an end-time substitute and treat missing
    `start_time` as "already started". Never raises.
    """
    persisted = auction.get("status")
    if persisted in {"sold", "cancelled", "ended"}:
        return persisted
    now = _now()
    try:
        start_raw = auction.get("start_time") or auction.get("created_at")
        end_raw = auction.get("end_time") or auction.get("auction_end_date")
        if not end_raw:
            return persisted or "active"
        end = _parse_dt(end_raw)
        if now >= end:
            return "ended"
        if start_raw:
            start = _parse_dt(start_raw)
            if now < start:
                return "upcoming"
        return "active"
    except Exception:
        return persisted or "active"


# ─────────────────────────────────────────────────────────────
# PUBLIC ROUTES
# ─────────────────────────────────────────────────────────────

@storage_router.get("/storage-auctions/stats/public")
async def storage_public_stats():
    """
    Public (unauthenticated) stats for the browse page marquee.
    Returns zero-safe counts; frontend hides cards that equal 0.
    """
    db = get_db()
    now_iso = _now().isoformat()
    total_sold = await db.storage_auctions.count_documents({"status": "sold"})
    active_auctions = await db.storage_auctions.count_documents(
        {"status": "active", "end_time": {"$gt": now_iso}}
    )
    active_facilities = await db.storage_facilities.count_documents(
        {"status": "verified", "verified": True}
    )
    bids_agg = await db.storage_auctions.aggregate(
        [{"$group": {"_id": None, "total": {"$sum": "$bid_count"}}}]
    ).to_list(1)
    total_bids = int((bids_agg[0] or {}).get("total", 0)) if bids_agg else 0
    return {
        "total_sold": total_sold,
        "active_facilities": active_facilities,
        "active_auctions": active_auctions,
        "total_bids_placed": total_bids,
    }


@storage_router.get("/storage-auctions/provinces")
async def list_provinces():
    """Province → active-auction count.

    iter283-hotfix Mission 1 — Aggregate provinces from BOTH the legacy
    `storage_auctions` collection AND the iter222 `listings` collection
    (where storage units land via the general create-form). Empty
    province codes are skipped and case is normalized to upper.
    """
    db = get_db()
    now = _now().isoformat()
    counts: dict = {}

    # Source 1 — legacy storage_auctions collection.
    try:
        pipe = [
            {"$match": {"status": "active", "end_time": {"$gt": now}}},
            {"$group": {"_id": "$facility_province", "count": {"$sum": 1}}},
        ]
        async for r in db.storage_auctions.aggregate(pipe):
            prov = (r.get("_id") or "").strip().upper()
            if prov:
                counts[prov] = counts.get(prov, 0) + int(r.get("count") or 0)
    except Exception:  # noqa: BLE001
        pass

    # Source 2 — listings collection (iter283 STORAGE_TYPES aliases).
    try:
        from services.listing_sections import STORAGE_TYPES
        pipe = [
            {"$match": {
                "status": "active",
                "$or": [
                    {"listing_type": {"$in": list(STORAGE_TYPES)}},
                    {"section": "storage"},
                ],
            }},
            {"$group": {"_id": "$region", "count": {"$sum": 1}}},
        ]
        async for r in db.listings.aggregate(pipe):
            prov = (r.get("_id") or "").strip().upper()
            if prov:
                counts[prov] = counts.get(prov, 0) + int(r.get("count") or 0)
    except Exception:  # noqa: BLE001
        pass

    rows = sorted(
        ({"province": p, "count": c} for p, c in counts.items()),
        key=lambda x: x["count"],
        reverse=True,
    )
    return {"provinces": rows}


@storage_router.get("/storage-auctions")
async def list_storage_auctions(
    province: Optional[str] = None,
    city: Optional[str] = None,
    unit_size: Optional[str] = None,
    unit_type: Optional[str] = None,
    is_lien_unit: Optional[bool] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None,
    status: Optional[str] = None,         # "active" | "ending_soon" | "upcoming"
    sort: str = "ending_soon",            # ending_soon | newest | price_low | most_bids
    limit: int = 24,
    skip: int = 0,
    # iter219 — Visible Content Tags filter + free-text search.
    tags: Optional[str] = None,
    search: Optional[str] = None,
    # iter223 — Demo sandbox owner-self-include
    current_user: Optional[User] = Depends(get_current_user_optional),
):
    db = get_db()
    now = _now()

    # iter211 P4 — exclude demo facilities' auctions from public list
    # iter223 — also exclude `is_demo_sandbox` listings from public view
    query = {
        "status": {"$in": ["active", "upcoming"]},
        "is_demo": {"$ne": True},
        "is_demo_sandbox": {"$ne": True},
    }
    if province:
        # iter283-hotfix Mission 1 — case-insensitive match so users
        # selecting "QC" find facilities stored as "qc" too.
        _prov = province.strip()
        query["facility_province"] = {
            "$regex": f"^{re.escape(_prov)}$",
            "$options": "i",
        }
    if city:
        query["facility_city"] = {"$regex": city, "$options": "i"}
    if unit_size:
        query["unit_size"] = unit_size
    if unit_type:
        query["unit_type"] = unit_type
    if is_lien_unit is not None:
        query["is_lien_unit"] = is_lien_unit
    if min_price is not None:
        query["current_bid"] = {"$gte": min_price}
    if max_price is not None:
        query.setdefault("current_bid", {})["$lte"] = max_price

    # iter219 — Visible Content Tags filter (canonical slug $in)
    if tags:
        tag_list = _sanitize_visible_content_tags_inline(
            [t.strip() for t in str(tags).split(",") if t.strip()]
        )
        if tag_list:
            query["visible_content_tags"] = {"$in": tag_list}

    # iter219 — Free-text search across description, facility, unit#, AND
    # the visible_content_tags array elements. Buyers typing "Meubles" or
    # "Furniture" surface every locker carrying that tag, in either language.
    if search:
        s = str(search).strip()
        if s:
            safe = re.escape(s)
            # Also match if the search term aligns with a canonical tag slug
            # or one of its bilingual aliases. We sanitize the query to a
            # canonical list so MongoDB can use the indexed `$in`.
            tag_hits = _sanitize_visible_content_tags_inline([s])
            or_clauses = [
                {"description_en":      {"$regex": safe, "$options": "i"}},
                {"description_fr":      {"$regex": safe, "$options": "i"}},
                {"facility_name":       {"$regex": safe, "$options": "i"}},
                {"unit_number":         {"$regex": safe, "$options": "i"}},
                {"visible_content_tags": {"$regex": safe, "$options": "i"}},
            ]
            if tag_hits:
                or_clauses.append({"visible_content_tags": {"$in": tag_hits}})
            query["$or"] = or_clauses

    if status == "ending_soon":
        # iter298 BUG 1 — window widened 1h → 24h to match the
        # platform-wide "Ending Soon" definition (computed dynamically).
        cutoff = (now + timedelta(hours=24)).isoformat()
        query["end_time"] = {"$lte": cutoff, "$gt": now.isoformat()}
        query["status"] = "active"
    elif status == "upcoming":
        query["start_time"] = {"$gt": now.isoformat()}
        query["status"] = "upcoming"

    sort_map = {
        "ending_soon": [("end_time", 1)],
        "newest": [("created_at", -1)],
        "price_low": [("current_bid", 1)],
        "most_bids": [("bid_count", -1)],
    }
    base_sort = sort_map.get(sort, sort_map["ending_soon"])
    # Promoted auctions always surface first; tier weight breaks ties.
    sort_spec = [("is_promoted", -1), ("promotion_tier_weight", -1)] + base_sort
    cursor = db.storage_auctions.find(query, {"_id": 0}).sort(sort_spec).skip(skip).limit(limit)
    auctions = await cursor.to_list(limit)
    total = await db.storage_auctions.count_documents(query)

    # iter222 Repair 1 / iter283 expansion — Storage units created via the
    # general `/create-listing` form (or admin tooling) write to the
    # `listings` collection. iter283 now accepts EVERY storage alias
    # (`storage_locker`, `storage_auction`, `storage`, `unit`,
    # `unit_auction`) so the UNIT 205 case appears on `/storage-auctions`
    # regardless of which authoring flow created it.
    from services.listing_sections import STORAGE_TYPES
    listings_query = {
        "status": "active",
        "$or": [
            {"listing_type": {"$in": list(STORAGE_TYPES)}},
            {"section": "storage"},
        ],
        "is_demo": {"$ne": True},
        "is_demo_sandbox": {"$ne": True},
    }
    if province:
        # The listings collection stores province under `region`.
        # iter283-hotfix Mission 1 — case-insensitive match so a user
        # selecting "QC" still finds listings stored as "qc" or with
        # surrounding whitespace.
        _prov = province.strip()
        listings_query["region"] = {
            "$regex": f"^{re.escape(_prov)}$",
            "$options": "i",
        }
    if city:
        listings_query["city"] = {"$regex": city, "$options": "i"}
    if tags:
        tag_list = _sanitize_visible_content_tags_inline(
            [t.strip() for t in str(tags).split(",") if t.strip()]
        )
        if tag_list:
            listings_query["visible_content_tags"] = {"$in": tag_list}
    if search:
        s = str(search).strip()
        if s:
            safe = re.escape(s)
            listings_query["$or"] = [
                {"title":       {"$regex": safe, "$options": "i"}},
                {"description": {"$regex": safe, "$options": "i"}},
                {"visible_content_tags": {"$regex": safe, "$options": "i"}},
            ]

    # iter283-hotfix — sort by newest first so a freshly-created listing
    # surfaces predictably within the first page (closes a flakiness in
    # the iter222 tag-filter regression test).
    listing_locker_docs = await db.listings.find(
        listings_query, {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    listings_total = await db.listings.count_documents(listings_query)

    for ld in listing_locker_docs:
        meta = ld.get("storage_metadata") or {}
        # Synthesize storage-card schema from the marketplace listing doc.
        ld.setdefault("facility_name",      meta.get("facility_name") or ld.get("seller_name") or "")
        ld.setdefault("facility_city",      ld.get("city") or "")
        ld.setdefault("facility_province",  ld.get("region") or "")
        ld.setdefault("facility_address",   meta.get("facility_address") or "")
        ld.setdefault("unit_number",        meta.get("locker_number") or "")
        ld.setdefault("unit_size",          meta.get("locker_size") or "")
        ld.setdefault("current_bid",        ld.get("current_price") or ld.get("starting_price") or 0)
        ld.setdefault("starting_bid",       ld.get("starting_price") or 0)
        ld.setdefault("end_time",           ld.get("auction_end_date"))
        ld.setdefault("description_en",     ld.get("description") or "")
        ld.setdefault("description_fr",     ld.get("description") or "")
        ld.setdefault("source",             "listings")
        # iter284 — Field-name normalization. Marketplace listings store
        # photos in the `images` array; storage cards read from `photos`.
        # Without this mapping, the storage browse grid + homepage banner
        # render the lock-emoji placeholder for every cross-collection
        # storage unit (UNIT 205 production bug). Default to whatever
        # the listing exposed and fall back to `images` so we never lose
        # the original media.
        if not ld.get("photos"):
            _imgs = ld.get("images") or []
            if _imgs:
                ld["photos"] = _imgs
        ld["live_status"] = _resolve_status(ld)

    auctions = auctions + listing_locker_docs
    total = total + listings_total

    # iter223 — Owner-self-include: demo creator sees their own sandbox
    # storage entries inside the real /storage-auctions feed.
    if current_user is not None:
        try:
            udoc = await db.users.find_one(
                {"id": current_user.id},
                {"_id": 0, "is_demo_account": 1},
            )
            if udoc and udoc.get("is_demo_account"):
                own_sandbox = await db.listings.find(
                    {
                        "status": "active",
                        "listing_type": "storage_locker",
                        "seller_id": current_user.id,
                        "is_demo_sandbox": True,
                    },
                    {"_id": 0},
                ).limit(50).to_list(50)
                for ld in own_sandbox:
                    meta = ld.get("storage_metadata") or {}
                    ld.setdefault("facility_name", meta.get("facility_name") or "")
                    ld.setdefault("facility_city", ld.get("city") or "")
                    ld.setdefault("facility_province", ld.get("region") or "")
                    ld.setdefault("unit_number", meta.get("locker_number") or "")
                    ld.setdefault("unit_size", meta.get("locker_size") or "")
                    ld.setdefault("current_bid", ld.get("current_price") or ld.get("starting_price") or 0)
                    ld.setdefault("end_time", ld.get("auction_end_date"))
                    ld.setdefault("source", "listings")
                    ld["is_demo_sandbox"] = True
                    ld["live_status"] = _resolve_status(ld)
                # Avoid dupes
                seen_ids = {a.get("id") for a in auctions}
                auctions = auctions + [s for s in own_sandbox if s.get("id") not in seen_ids]
                total = total + len(own_sandbox)
        except Exception as e:
            logger.warning(f"[demo-sandbox] storage owner-self-include failed: {e}")

    # Live status reconciliation
    for a in auctions:
        if "live_status" not in a:
            a["live_status"] = _resolve_status(a)
    return {
        "total":              total,
        "auctions":           auctions,
        "limit":              limit,
        "skip":               skip,
        "sort":               sort,
        "applied_tags":       list(_sanitize_visible_content_tags_inline(
                                  [t.strip() for t in (tags or "").split(",") if t.strip()]
                              )) if tags else [],
        "available_tags":     list(_ALLOWED_CONTENT_TAGS),
    }


@storage_router.get("/storage-auctions/my-bids")
async def my_storage_bids(current_user: User = Depends(get_current_user)):
    """Auctions where THIS user has a bid recorded."""
    db = get_db()
    cursor = db.storage_auctions.find(
        {"bids.bidder_id": current_user.id, "status": {"$in": ["active", "ended", "sold"]}},
        {"_id": 0},
    ).sort("end_time", 1).limit(100)
    rows = await cursor.to_list(100)
    for a in rows:
        a["live_status"] = _resolve_status(a)
        a["my_max_bid"] = max(
            (b["max_bid"] for b in a.get("bids", []) if b["bidder_id"] == current_user.id),
            default=0,
        )
        a["am_i_winning"] = a.get("winning_bidder_id") == current_user.id
    return {"total": len(rows), "auctions": rows}


@storage_router.get("/storage-auctions/won")
async def my_won_storage_auctions(current_user: User = Depends(get_current_user)):
    db = get_db()
    cursor = db.storage_auctions.find(
        {"winning_bidder_id": current_user.id, "status": {"$in": ["ended", "sold"]}},
        {"_id": 0},
    ).sort("end_time", -1).limit(100)
    rows = await cursor.to_list(100)
    return {"total": len(rows), "auctions": rows}


@storage_router.get("/storage-auctions/{auction_id}")
async def get_storage_auction(auction_id: str):
    db = get_db()
    a = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
    if not a:
        # iter284 — Dual-visibility fallback. Storage units authored via
        # the general `/create-listing` flow live in `db.listings`. The
        # browse grid already merges both collections (see list endpoint
        # above) — without this fallback the card links open and 404 with
        # the "Auction not found" toast (production UNIT 205 bug).
        from services.listing_sections import STORAGE_TYPES
        ld = await db.listings.find_one(
            {
                "id": auction_id,
                "$or": [
                    {"listing_type": {"$in": list(STORAGE_TYPES)}},
                    {"section": "storage"},
                ],
            },
            {"_id": 0},
        )
        if not ld:
            raise HTTPException(status_code=404, detail="Auction not found")
        meta = ld.get("storage_metadata") or {}
        ld.setdefault("facility_id",       ld.get("seller_id") or "")
        ld.setdefault("facility_name",     meta.get("facility_name") or ld.get("seller_name") or "")
        ld.setdefault("facility_city",     ld.get("city") or "")
        ld.setdefault("facility_province", ld.get("region") or "")
        ld.setdefault("facility_address",  meta.get("facility_address") or "")
        ld.setdefault("unit_number",       meta.get("locker_number") or "")
        ld.setdefault("unit_size",         meta.get("locker_size") or "")
        ld.setdefault("unit_type",         meta.get("unit_type") or "standard")
        ld.setdefault("current_bid",       ld.get("current_price") or ld.get("starting_price") or 0)
        ld.setdefault("starting_price",    ld.get("starting_price") or 0)
        ld.setdefault("bid_increment",     ld.get("bid_increment") or 5)
        ld.setdefault("start_time",        ld.get("auction_start_date") or ld.get("created_at"))
        ld.setdefault("end_time",          ld.get("auction_end_date"))
        ld.setdefault("description_en",    ld.get("description") or ld.get("title") or "")
        ld.setdefault("description_fr",    ld.get("description_fr") or ld.get("description") or "")
        ld.setdefault("bid_count",         ld.get("bid_count") or 0)
        ld.setdefault("bids",              ld.get("bids") or [])
        ld.setdefault("source",            "listings")
        # Normalize images → photos so the gallery renders the uploaded media.
        if not ld.get("photos"):
            _imgs = ld.get("images") or []
            if _imgs:
                ld["photos"] = _imgs
        ld["live_status"] = _resolve_status(ld)
        ld["facility"] = {
            "id":           ld.get("facility_id"),
            "company_name": ld.get("facility_name"),
            "city":         ld.get("facility_city"),
            "province":     ld.get("facility_province"),
            "verified":     True,
        }
        return ld
    a["live_status"] = _resolve_status(a)
    fac = await db.storage_facilities.find_one({"id": a["facility_id"]}, {"_id": 0, "id": 1, "company_name": 1, "company_name_fr": 1, "city": 1, "province": 1, "verified": 1})
    a["facility"] = fac or {}
    return a


@storage_router.get("/storage-auctions/{auction_id}/bids")
async def get_anonymized_bid_history(auction_id: str):
    """Public bid history with anonymized bidder labels (Bidder #1, #2, …)."""
    db = get_db()
    a = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0, "bids": 1})
    if not a:
        # iter284 — Dual-visibility fallback. A storage unit created via
        # `/create-listing` lives in `db.listings`; surface an empty bid
        # history rather than a 404 so the detail page renders cleanly.
        from services.listing_sections import STORAGE_TYPES
        ld = await db.listings.find_one(
            {
                "id": auction_id,
                "$or": [
                    {"listing_type": {"$in": list(STORAGE_TYPES)}},
                    {"section": "storage"},
                ],
            },
            {"_id": 0, "bids": 1},
        )
        if ld is None:
            raise HTTPException(status_code=404, detail="Auction not found")
        a = ld
    bids = a.get("bids", []) or []
    aliases: dict = {}
    out = []
    for b in bids:
        bid_user = b.get("bidder_id")
        if bid_user not in aliases:
            aliases[bid_user] = f"Bidder #{len(aliases) + 1}"
        out.append({
            "bidder_label": aliases[bid_user],
            "amount": b.get("amount"),
            "placed_at": b.get("placed_at"),
        })
    return {"bids": out, "total_bids": len(out)}


@storage_router.get("/storage-facilities/{facility_id}")
async def get_facility_profile(facility_id: str):
    db = get_db()
    fac = await db.storage_facilities.find_one(
        {"id": facility_id},
        {"_id": 0, "id": 1, "company_name": 1, "company_name_fr": 1, "city": 1, "province": 1, "verified": 1, "status": 1, "total_units_sold": 1, "average_sale_price": 1, "created_at": 1},
    )
    if not fac:
        raise HTTPException(status_code=404, detail="Facility not found")
    return fac


# ─────────────────────────────────────────────────────────────
# BUYER ROUTES
# ─────────────────────────────────────────────────────────────

@storage_router.post("/storage-auctions/{auction_id}/bid")
@_limiter.limit("10/minute")
async def place_storage_bid(
    request: Request,
    auction_id: str,
    payload: StorageBidPayload,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    db = get_db()

    # iter300 P1 — suspended buyers cannot bid (overdue-payment escalation).
    from services.bid_guard import ensure_bidding_allowed
    await ensure_bidding_allowed(db, current_user.id)

    # ── Deposit guard ──
    # iter285 — Use the dual-visibility bridge so cross-collection storage
    # units (authored via /create-listing) load correctly here too.
    from services.storage_auction_service import _ensure_storage_auction_row
    auction = await _ensure_storage_auction_row(db, auction_id)
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    if auction.get("deposit_required") and float(auction.get("deposit_amount", 0)) > 0:
        existing = await get_existing_deposit(db, auction_id, current_user.id)
        if not existing:
            amt = float(auction["deposit_amount"])
            raise HTTPException(
                status_code=402,
                detail={
                    "error": "deposit_required",
                    "deposit_amount": amt,
                    "message_en": f"A deposit of ${amt:.2f} CAD is required to participate in this auction.",
                    "message_fr": f"Un dépôt de {amt:.2f} $ CAD est requis pour participer à cette enchère.",
                    "action": "pay_deposit",
                },
            )

    result = await _place_bid_proxy(db, auction_id, current_user.id, float(payload.max_bid))

    # Send bid-confirmation + outbid emails (non-blocking)
    try:
        from services.emails.email_marketplace import (
            send_storage_bid_placed_email,
            send_storage_outbid_email,
        )
        a = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
        user_payload = current_user.model_dump() if hasattr(current_user, "model_dump") else (current_user.dict() if hasattr(current_user, "dict") else dict(current_user))
        background_tasks.add_task(send_storage_bid_placed_email, user_payload, a, result)
        if result.get("outbid_user_id"):
            outbid = await db.users.find_one({"id": result["outbid_user_id"]}, {"_id": 0})
            if outbid:
                background_tasks.add_task(send_storage_outbid_email, outbid, a, result["current_bid"])
    except Exception as e:
        logger.error(f"[STORAGE] bid-email schedule failed: {e}")

    return result


@storage_router.post("/storage-auctions/{auction_id}/deposit")
async def pay_storage_deposit(
    auction_id: str,
    payload: StorageDepositRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Buyer authorizes the participation deposit (held via Stripe with capture_method=manual).
    Idempotent — returns the existing 'held' deposit if already paid.
    """
    db = get_db()
    auction = await db.storage_auctions.find_one(
        {"id": auction_id},
        {"_id": 0, "deposit_required": 1, "deposit_amount": 1, "status": 1},
    )
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    if not auction.get("deposit_required") or float(auction.get("deposit_amount", 0)) <= 0:
        raise HTTPException(status_code=400, detail="No deposit required for this auction.")
    if auction.get("status") not in ("active", "upcoming"):
        raise HTTPException(status_code=400, detail="Auction not accepting deposits.")

    deposit = await create_deposit_hold(
        db,
        auction_id=auction_id,
        buyer_id=current_user.id,
        buyer_email=current_user.email,
        amount=float(auction["deposit_amount"]),
        payment_method_id=payload.payment_method_id,
    )
    return {"success": True, "deposit": deposit}


@storage_router.get("/storage-auctions/{auction_id}/deposit/status")
async def storage_deposit_status(
    auction_id: str,
    current_user: User = Depends(get_current_user),
):
    """Returns whether the current user has a valid deposit for this storage auction."""
    db = get_db()
    auction = await db.storage_auctions.find_one(
        {"id": auction_id},
        {"_id": 0, "deposit_required": 1, "deposit_amount": 1},
    )
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    required = bool(auction.get("deposit_required"))
    amount = float(auction.get("deposit_amount") or 0)
    if not required or amount <= 0:
        return {
            "has_deposit": True,
            "deposit_required": False,
            "deposit_amount": 0,
            "status": None,
            "created_at": None,
        }

    deposit = await db.storage_deposits.find_one(
        {"auction_id": auction_id, "buyer_id": current_user.id},
        {"_id": 0, "status": 1, "amount": 1, "stripe_payment_intent_id": 1, "created_at": 1},
    )
    active = deposit and deposit.get("status") in ("held", "authorized", "requires_capture", "succeeded")
    return {
        "has_deposit": bool(active),
        "deposit_required": True,
        "deposit_amount": amount,
        "status": deposit.get("status") if deposit else None,
        "created_at": deposit.get("created_at") if deposit else None,
    }


@storage_router.post("/storage-auctions/{auction_id}/payment")
async def record_storage_payment(
    auction_id: str,
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    """Buyer reports they've paid (or initiated Stripe payment) the facility."""
    db = get_db()
    a = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    if a.get("winning_bidder_id") != current_user.id:
        raise HTTPException(status_code=403, detail="You did not win this auction")
    method = (payload.get("payment_method") or "").lower()
    if method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail="Invalid payment method")
    await db.storage_auctions.update_one(
        {"id": auction_id},
        {"$set": {
            "payment_method": method,
            "payment_status": "pending" if method != "cash" else "paid",
            "payment_recorded_at": _now().isoformat(),
        }},
    )
    return {"success": True, "payment_method": method, "auction_id": auction_id}


# ─────────────────────────────────────────────────────────────
# FACILITY (SELLER) ROUTES
# ─────────────────────────────────────────────────────────────

@storage_router.post("/storage-facilities/register")
async def register_facility(
    payload: StorageFacilityRegister,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    if not payload.accepted_terms:
        raise HTTPException(status_code=400, detail="You must accept the BidVex Storage Auction terms.")
    if payload.province.upper() not in CANADIAN_PROVINCES:
        raise HTTPException(status_code=400, detail="Province must be a valid Canadian province code.")

    db = get_db()
    existing = await db.storage_facilities.find_one({"owner_user_id": current_user.id}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "facility_already_registered",
                "message_en": "You already have a facility registered.",
                "message_fr": "Vous avez déjà une facilité enregistrée.",
            },
        )

    # ── Create Stripe Connect Express account so BidVex can charge facility ──
    stripe_account_id = None
    onboarding_url = None
    try:
        import stripe as _stripe
        _stripe.api_key = os.environ.get("STRIPE_API_KEY")
        if _stripe.api_key:
            acct = _stripe.Account.create(
                type="express",
                country="CA",
                email=payload.email,
                capabilities={
                    "card_payments": {"requested": True},
                    "transfers": {"requested": True},
                },
                business_type="company",
                business_profile={
                    "name": payload.company_name,
                    "mcc": "4225",  # public warehousing & storage
                },
                metadata={
                    "platform": "bidvex_storage",
                    "owner_user_id": current_user.id,
                },
            )
            stripe_account_id = acct.id
            base_url = os.environ.get("FRONTEND_URL") or os.environ.get("REACT_APP_BACKEND_URL") or "https://bidvex.com"
            link = _stripe.AccountLink.create(
                account=stripe_account_id,
                refresh_url=f"{base_url}/storage-auctions/register-facility?refresh=true",
                return_url=f"{base_url}/storage-dashboard?onboarding=complete",
                type="account_onboarding",
            )
            onboarding_url = link.url
    except Exception as e:
        logger.error(f"[STORAGE] Stripe Connect Express creation failed: {e}")
        # Don't block registration on Stripe outage — admin can re-issue link later

    fac_id = str(uuid.uuid4())
    # iter212 — Provincial Business Registration validation (new facilities only)
    reg_type = (payload.company_registration_type or "").strip().lower() or None
    reg_num = (payload.company_registration_number or "").strip() or None
    reg_doc = (payload.company_registration_document_url or "").strip() or None
    if reg_type and reg_type not in REGISTRATION_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_registration_type",
                "message_en": f"Registration type must be one of {REGISTRATION_TYPES}.",
                "message_fr": f"Le type d'enregistrement doit être l'un de {REGISTRATION_TYPES}.",
            },
        )
    # New facility registrations require the trio: type + number + document.
    # (Existing facilities lacking these fields are grandfathered — they keep
    #  `company_registration_verified=True` set by the migration script.)
    if not (reg_type and reg_num and reg_doc):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "registration_required",
                "message_en": (
                    "Business registration is now required. Please pick a registration type, "
                    "enter the registration number, and upload a proof-of-registration document."
                ),
                "message_fr": (
                    "L'enregistrement d'entreprise est maintenant obligatoire. Veuillez choisir un type, "
                    "saisir le numéro d'enregistrement et téléverser un document de preuve."
                ),
            },
        )

    doc = {
        "id": fac_id,
        "owner_user_id": current_user.id,
        "company_name": payload.company_name,
        "company_name_fr": payload.company_name_fr or payload.company_name,
        "contact_name": payload.contact_name,
        "email": payload.email,
        "phone": payload.phone,
        "address": payload.address,
        "city": payload.city,
        "province": payload.province.upper(),
        "postal_code": payload.postal_code,
        "units_available": payload.units_available,
        "referral_source": payload.referral_source,
        "business_registration_number": payload.business_registration_number,
        "opc_permit_number": payload.opc_permit_number,
        # iter212 — Provincial registration fields
        "company_registration_type": reg_type,
        "company_registration_number": reg_num,
        "company_registration_document_url": reg_doc,
        "company_registration_verified": False,   # admin must verify
        "company_registration_verified_at": None,
        "company_registration_verified_by": None,
        "company_registration_rejection_reason": None,
        "verified": False,
        "status": "pending_verification",
        "seller_tier": "storage_facility",  # always 5% commission
        "stripe_account_id": stripe_account_id,
        "stripe_onboarding_complete": False,
        "total_units_sold": 0,
        "average_sale_price": 0.0,
        "created_at": _now().isoformat(),
        "updated_at": _now().isoformat(),
    }
    await db.storage_facilities.insert_one(doc.copy())

    # iter212 — flag the user as a storage facility so frontend nav/dashboard
    # gating works immediately after registration. The `verified` flag stays
    # False until an admin approves the documents.
    try:
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {
                "is_storage_facility": True,
                "account_type": "storage_facility",
                "storage_facility_id": fac_id,
            }},
        )
    except Exception as e:
        logger.error(f"[STORAGE] user-flag update failed for {current_user.id}: {e}")

    # Notify admin (non-blocking)
    try:
        from services.emails.email_marketplace import (
            send_storage_facility_registration_admin_alert,
            send_storage_facility_pending_user_email,
        )
        background_tasks.add_task(send_storage_facility_registration_admin_alert, doc)
        background_tasks.add_task(send_storage_facility_pending_user_email, doc)
    except Exception as e:
        logger.error(f"[STORAGE] registration email failed: {e}")

    doc.pop("_id", None)
    return {
        "facility_id": fac_id,
        "status": "pending_verification",
        "stripe_onboarding_url": onboarding_url,
        "message_en": "Registered successfully. Complete Stripe onboarding to receive payouts. Verification takes 24–48 hours.",
        "message_fr": "Inscription réussie. Complétez l'intégration Stripe pour recevoir des paiements. Vérification sous 24 à 48 heures.",
        **doc,
    }


@storage_router.get("/storage-facilities/me")
async def get_my_facility(current_user: User = Depends(get_current_user)):
    db = get_db()
    fac = await _facility_for_user(db, current_user.id)
    if not fac:
        raise HTTPException(status_code=404, detail="No facility profile found")
    return fac


@storage_router.post("/storage-facilities/auctions")
async def create_storage_auction(
    payload: StorageAuctionCreate,
    facility=Depends(_require_verified_facility),
):
    if payload.unit_size not in UNIT_SIZES:
        raise HTTPException(status_code=400, detail=f"unit_size must be one of {UNIT_SIZES}")
    if payload.unit_type not in UNIT_TYPES:
        raise HTTPException(status_code=400, detail=f"unit_type must be one of {UNIT_TYPES}")
    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")
    if payload.payment_method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail=f"payment_method must be one of {PAYMENT_METHODS}")
    if payload.deposit_required and (not payload.deposit_amount or payload.deposit_amount <= 0):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "deposit_amount_required",
                "message_en": "You must set a deposit amount when requiring a deposit.",
                "message_fr": "Vous devez définir un montant de dépôt lorsqu'un dépôt est requis.",
            },
        )
    # iter216 P1 — Mandatory legal-notice confirmation
    if not payload.accepted_legal_notice:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "legal_notice_required",
                "message_en": "You must confirm the legal-notification process before publishing this auction.",
                "message_fr": "Vous devez confirmer le processus de notification légale avant de publier cette enchère.",
            },
        )

    # iter217 — Quebec Bill 96 compliance — French description required for QC facilities.
    # Storage auctions have description_en/description_fr (no title field), so we
    # validate the description side only.
    from services.qc_bilingual_validator import assert_qc_bilingual_titles
    assert_qc_bilingual_titles(
        title=payload.description_en or "",
        title_fr=payload.description_fr,
        description=payload.description_en,
        description_fr=payload.description_fr,
        region=facility.get("province"),
        city=facility.get("city"),
        content_language="en",
    )


    db = get_db()
    auction_id = str(uuid.uuid4())
    cleanup_deadline = payload.end_time + timedelta(hours=payload.cleanup_deadline_hours)
    starting = float(payload.starting_price)

    doc = {
        "id": auction_id,
        "facility_id": facility["id"],
        "facility_name": facility["company_name"],
        "facility_city": facility["city"],
        "facility_province": facility["province"],
        "unit_number": payload.unit_number,
        "unit_size": payload.unit_size,
        "unit_type": payload.unit_type,
        "is_lien_unit": payload.is_lien_unit,
        "past_due_balance": payload.past_due_balance,
        "description_en": payload.description_en,
        "description_fr": payload.description_fr or payload.description_en,
        "photos": payload.photos[:MAX_PHOTOS_PER_AUCTION],
        "video_url": payload.video_url,
        "starting_price": starting,
        "current_bid": starting,
        "reserve_price": payload.reserve_price,
        "reserve_met": False if payload.reserve_price else True,
        "bid_increment": float(payload.bid_increment),
        "start_time": payload.start_time.isoformat(),
        "end_time": payload.end_time.isoformat(),
        "soft_close_enabled": payload.soft_close_enabled,
        "soft_close_extension_minutes": payload.soft_close_extension_minutes,
        "status": "upcoming" if payload.start_time > _now() else "active",
        "winning_bidder_id": None,
        "winning_bid": None,
        "bid_count": 0,
        "bids": [],
        # Single facility-chosen payment method (legacy multi-select kept for compat readers)
        "payment_method": payload.payment_method,
        "payment_methods_accepted": [payload.payment_method],
        "payment_status": "pending",
        # Optional participation deposit
        "deposit_required": bool(payload.deposit_required),
        "deposit_amount": float(payload.deposit_amount) if payload.deposit_amount else 0.0,
        "deposit_type": (payload.deposit_type or "fixed") if payload.deposit_required else None,
        # Spec compatibility — settlement reads listing.requires_deposit
        "requires_deposit": bool(payload.deposit_required),
        "deposit_description_en": payload.deposit_description_en,
        "deposit_description_fr": payload.deposit_description_fr,
        # Currency (Spec Global Rule 1)
        "currency": (payload.currency or "CAD").upper(),
        "cleanup_deadline": cleanup_deadline.isoformat(),
        # iter216 P1 — Buyer's Premium captured at listing time
        "buyer_premium_pct": float(payload.buyer_premium_pct or 0.0),
        "accepted_legal_notice": bool(payload.accepted_legal_notice),
        "accepted_legal_notice_at": _now().isoformat() if payload.accepted_legal_notice else None,
        # iter219 — Visible Content Tags (optional bilingual content guide)
        "visible_content_tags": _sanitize_visible_content_tags_inline(payload.visible_content_tags),
        "created_at": _now().isoformat(),
        "updated_at": _now().isoformat(),
    }
    # iter211 P4 — tag demo facility's auctions
    from services.demo_filter import tag_listing_if_demo
    await tag_listing_if_demo(db, facility.get("user_id") or facility.get("id"), doc)

    await db.storage_auctions.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc


@storage_router.get("/storage-facilities/my-auctions")
async def my_facility_auctions(current_user: User = Depends(get_current_user)):
    """List of the facility's own auctions.

    iter213 — soft-gated so unverified-registration facilities can still see
    the (empty) list in their dashboard without a 403.
    """
    db = get_db()
    facility = await _facility_for_user(db, current_user.id)
    if not facility:
        raise HTTPException(
            status_code=403,
            detail={"error": "no_facility_profile", "message_en": "No facility profile.", "message_fr": "Aucun profil."},
        )
    rows = await db.storage_auctions.find(
        {"facility_id": facility["id"]}, {"_id": 0}
    ).sort("created_at", -1).limit(200).to_list(200)
    for a in rows:
        a["live_status"] = _resolve_status(a)
    return {"total": len(rows), "auctions": rows}


@storage_router.put("/storage-facilities/auctions/{auction_id}")
async def edit_facility_auction(
    auction_id: str,
    payload: dict,
    facility=Depends(_require_verified_facility),
):
    db = get_db()
    a = await db.storage_auctions.find_one({"id": auction_id, "facility_id": facility["id"]}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    if _parse_dt(a["start_time"]) <= _now():
        raise HTTPException(status_code=400, detail="Cannot edit an auction that has already started")
    EDITABLE = {
        "description_en", "description_fr", "starting_price", "reserve_price",
        "bid_increment", "start_time", "end_time", "cleanup_deposit", "photos",
        "video_url", "soft_close_enabled", "soft_close_extension_minutes",
    }
    updates = {k: payload[k] for k in EDITABLE if k in payload}
    if "starting_price" in updates:
        updates["current_bid"] = float(updates["starting_price"])
    updates["updated_at"] = _now().isoformat()
    await db.storage_auctions.update_one({"id": auction_id}, {"$set": updates})
    return {"success": True, "updated": list(updates.keys())}


@storage_router.delete("/storage-facilities/auctions/{auction_id}")
async def cancel_facility_auction(auction_id: str, facility=Depends(_require_verified_facility)):
    db = get_db()
    a = await db.storage_auctions.find_one({"id": auction_id, "facility_id": facility["id"]}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    if _parse_dt(a["start_time"]) <= _now():
        raise HTTPException(status_code=400, detail="Cannot cancel an auction that has already started")
    await db.storage_auctions.update_one({"id": auction_id}, {"$set": {"status": "cancelled", "updated_at": _now().isoformat()}})
    return {"success": True, "auction_id": auction_id, "status": "cancelled"}


@storage_router.get("/storage-facilities/auctions/{auction_id}/bids")
async def my_auction_bids(auction_id: str, facility=Depends(_require_verified_facility)):
    """Facility view — actual bidder IDs disclosed (their listing)."""
    db = get_db()
    a = await db.storage_auctions.find_one({"id": auction_id, "facility_id": facility["id"]}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    bidder_ids = list({b["bidder_id"] for b in a.get("bids", [])})
    bidders = {}
    if bidder_ids:
        async for u in db.users.find({"id": {"$in": bidder_ids}}, {"_id": 0, "id": 1, "name": 1, "email": 1}):
            bidders[u["id"]] = u
    return {"auction_id": auction_id, "bids": a.get("bids", []), "bidders": bidders}


@storage_router.get("/storage-facilities/dashboard")
async def facility_dashboard(current_user: User = Depends(get_current_user)):
    """Storage facility owner dashboard.

    iter213 — this endpoint deliberately does NOT use the strict
    `_require_verified_facility` gate so that a facility whose
    business-registration document is awaiting (or has been rejected by)
    admin review can still see their dashboard *with* the verification
    progress banner. Listing-creation endpoints retain the strict gate.
    """
    db = get_db()
    facility = await _facility_for_user(db, current_user.id)
    if not facility:
        raise HTTPException(
            status_code=403,
            detail={
                "error": "no_facility_profile",
                "message_en": "No facility profile found for this account.",
                "message_fr": "Aucun profil de facilité trouvé pour ce compte.",
            },
        )
    fid = facility["id"]
    now = _now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    active = await db.storage_auctions.count_documents({"facility_id": fid, "status": "active"})
    upcoming = await db.storage_auctions.count_documents({"facility_id": fid, "status": "upcoming"})
    sold = await db.storage_auctions.count_documents({"facility_id": fid, "status": "sold"})

    # Revenue this month — sum of winning_bid for sold auctions ended this month
    pipe = [
        {"$match": {"facility_id": fid, "status": "sold", "end_time": {"$gte": month_start}}},
        {"$group": {"_id": None, "revenue": {"$sum": "$winning_bid"}, "count": {"$sum": 1}}},
    ]
    rev_doc = await db.storage_auctions.aggregate(pipe).to_list(1)
    revenue_month = float(rev_doc[0]["revenue"]) if rev_doc else 0.0

    # Total commission owed (unpaid seller invoices)
    commission_pipe = [
        {"$match": {"facility_id": fid, "status": "sold"}},
        {"$group": {"_id": None, "owed": {"$sum": {"$multiply": ["$winning_bid", 0.05]}}}},
    ]
    com_doc = await db.storage_auctions.aggregate(commission_pipe).to_list(1)
    commission_owed = float(com_doc[0]["owed"]) if com_doc else 0.0

    return {
        "active_auctions": active,
        "upcoming_auctions": upcoming,
        "total_sold": sold,
        "revenue_this_month": round(revenue_month, 2),
        "commission_owed": round(commission_owed, 2),
        "facility": facility,
    }


# ─────────────────────────────────────────────────────────────
# PHOTO UPLOAD (local disk, per spec)
# ─────────────────────────────────────────────────────────────

@storage_router.post("/storage-facilities/upload-photo")
async def upload_facility_photo(
    file: UploadFile = File(...),
    facility=Depends(_require_verified_facility),
):
    """Upload a photo for one of the facility's auctions. Returns public URL."""
    if file.content_type not in ALLOWED_PHOTO_MIME:
        raise HTTPException(status_code=400, detail="Photo must be PNG/JPEG/WebP")
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(payload) > MAX_PHOTO_BYTES:
        raise HTTPException(status_code=413, detail="Photo exceeds 8 MB limit")

    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", file.filename or "photo")
    key = f"{facility['id']}/{uuid.uuid4().hex[:8]}_{safe_name}"
    target_dir = os.path.join(UPLOAD_ROOT, facility["id"])
    os.makedirs(target_dir, exist_ok=True)
    target_path = os.path.join(UPLOAD_ROOT, key)
    with open(target_path, "wb") as f:
        f.write(payload)
    public_url = f"/api/storage-auctions/photo/{key}"
    return {"url": public_url, "filename": file.filename, "bytes": len(payload)}


# ─────────────────────────────────────────────────────────────
# iter212 — Storage Facility Business-Registration upload + serve
# ─────────────────────────────────────────────────────────────

@storage_router.post("/storage-facilities/upload-registration-doc")
async def upload_facility_registration_doc(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """Upload (or replace) a facility's business-registration proof document.

    Auth: any authenticated user (the doc is namespaced under their user_id;
    only the owner or an admin can read it back).

    Returns: `{url}` where `url` is `/api/uploads/storage_facilities/{filename}`.
    The frontend stores that URL in the registration payload as
    `company_registration_document_url`.
    """
    if file.content_type not in ALLOWED_FACILITY_DOC_MIME:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_mime",
                "message_en": "Document must be PDF, JPEG, PNG, or WebP.",
                "message_fr": "Le document doit être au format PDF, JPEG, PNG ou WebP.",
            },
        )
    payload = await file.read()
    if not payload:
        raise HTTPException(status_code=400, detail="Empty file")
    if len(payload) > MAX_FACILITY_DOC_BYTES:
        raise HTTPException(
            status_code=413,
            detail={
                "error": "file_too_large",
                "message_en": "Document exceeds the 10 MB size limit.",
                "message_fr": "Le document dépasse la limite de 10 Mo.",
            },
        )

    # Preserve extension; strip everything else
    ext = ""
    original = (file.filename or "doc").lower()
    for candidate in (".pdf", ".png", ".jpg", ".jpeg", ".webp"):
        if original.endswith(candidate):
            ext = candidate
            break
    if not ext:
        # Fall back to MIME → ext
        ext = {
            "application/pdf": ".pdf",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/webp": ".webp",
        }.get(file.content_type, ".bin")

    fname = f"reg_{current_user.id}_{uuid.uuid4().hex[:8]}{ext}"
    # iter273 — Persist to the persistent uploads root so the file
    # survives container redeployments. Also write a legacy-path mirror
    # so old `FileResponse` lookups still find it during the rollover.
    FACILITY_DOC_ROOT_PERSISTENT.mkdir(parents=True, exist_ok=True)
    target = FACILITY_DOC_ROOT_PERSISTENT / fname
    with open(target, "wb") as f:
        f.write(payload)
    # Best-effort legacy mirror — never block the upload if it fails.
    try:
        FACILITY_DOC_ROOT_ABS.mkdir(parents=True, exist_ok=True)
        with open(FACILITY_DOC_ROOT_ABS / fname, "wb") as f:
            f.write(payload)
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"[facility-doc-upload] legacy mirror skipped: {exc}")

    rel_url = f"/api/uploads/storage_facilities/{fname}"
    return {
        "url": rel_url,
        "filename": fname,
        "bytes": len(payload),
        "mime": file.content_type,
    }


@storage_router.get("/uploads/storage_facilities/{filename}")
async def serve_facility_registration_doc(
    filename: str,
    request: Request,
    token: Optional[str] = Query(None),
):
    """Serve a facility's uploaded business-registration document.

    Auth modes (priority order):
      1. Cookie / Authorization header (normal API caller).
      2. `?token=<jwt>` query param — required when an admin opens the URL
         in a new tab.

    Owner (filename prefix `reg_{user_id}_*`) may read their own doc.
    Admins / super_admins may read any doc.

    Mirrors the iter211 partner-doc structured-404 recovery pattern so the
    admin UI can render a "Request resubmission" CTA when files are missing
    after a pod redeploy.
    """
    db = get_db()

    # ── Auth ───────────────────────────────────────────────────────
    current_user = None
    try:
        creds: Optional[HTTPAuthorizationCredentials] = await security(request)
        current_user = await get_current_user(request, creds)
    except HTTPException:
        current_user = None

    if current_user is None and token:
        try:
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
            user_id = payload.get("sub")
            if user_id:
                user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
                if user_doc:
                    current_user = User(**user_doc)
        except (JWTError, ExpiredSignatureError):
            current_user = None

    if current_user is None:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # ── Defensive filename normalisation (peel legacy prefixes) ────
    bare = filename
    for prefix in (
        "/api/uploads/storage_facilities/", "/uploads/storage_facilities/",
        "api/uploads/storage_facilities/", "uploads/storage_facilities/",
    ):
        if bare.startswith(prefix):
            bare = bare[len(prefix):]
    if ".." in bare or "/" in bare or bare.startswith("."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    # ── Permission check ──────────────────────────────────────────
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0, "role": 1})
    is_owner = bare.startswith(f"reg_{current_user.id}_") or bare.startswith(f"reg_{current_user.id}.")
    is_admin = (user_doc or {}).get("role") in {"admin", "super_admin"}
    if not is_owner and not is_admin:
        raise HTTPException(status_code=403, detail="Access denied")

    # ── Search every known upload root ────────────────────────────
    # iter273 — Persistent mount first (current canonical), then the
    # two legacy locations for files uploaded before the cutover.
    candidates = [
        FACILITY_DOC_ROOT_PERSISTENT / bare,
        FACILITY_DOC_ROOT_REL / bare,
        FACILITY_DOC_ROOT_ABS / bare,
    ]
    found = next((p for p in candidates if p.exists() and p.is_file()), None)
    if found is None:
        logger.warning(
            f"[facility_docs] missing file: {bare} requested by user={current_user.id} "
            f"role={'admin' if is_admin else 'owner'}"
        )
        owner_email = None
        owner_id = None
        owner_status = None
        m = re.match(r"^reg_([0-9a-f-]{8,})", bare)
        try:
            if m:
                owner_doc = await db.users.find_one(
                    {"id": m.group(1)},
                    {"_id": 0, "id": 1, "email": 1},
                )
                if owner_doc:
                    owner_email = owner_doc.get("email")
                    owner_id = owner_doc.get("id")
                fac_doc = await db.storage_facilities.find_one(
                    {"owner_user_id": m.group(1)},
                    {"_id": 0, "status": 1, "company_registration_verified": 1},
                )
                if fac_doc:
                    owner_status = fac_doc.get("status")
        except Exception:
            pass
        raise HTTPException(
            status_code=404,
            detail={
                "error_code": "file_missing_on_disk",
                "filename": bare,
                "message_en": (
                    "This document is no longer available on the server. "
                    "Files uploaded before the most recent redeployment may have been lost. "
                    "Please ask the facility to re-upload their registration proof."
                ),
                "message_fr": (
                    "Ce document n'est plus disponible sur le serveur. "
                    "Les fichiers téléversés avant le dernier redéploiement ont peut-être été perdus. "
                    "Veuillez demander à la facilité de téléverser à nouveau sa preuve d'enregistrement."
                ),
                "owner_email": owner_email,
                "owner_user_id": owner_id,
                "owner_status": owner_status,
            },
        )

    return FileResponse(str(found))


@storage_router.get("/storage-auctions/photo/{facility_id}/{photo_name}")
async def serve_facility_photo(facility_id: str, photo_name: str):
    """Public photo serve."""
    from fastapi.responses import FileResponse
    safe_name = re.sub(r"[^a-zA-Z0-9._-]", "_", photo_name)
    path = os.path.join(UPLOAD_ROOT, facility_id, safe_name)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Photo not found")
    return FileResponse(path)


# ─────────────────────────────────────────────────────────────
# ADMIN ROUTES
# ─────────────────────────────────────────────────────────────

@storage_router.get("/admin/storage-facilities")
async def admin_list_facilities(current_user: User = Depends(_require_admin)):
    db = get_db()
    rows = await db.storage_facilities.find({}, {"_id": 0}).sort("created_at", -1).limit(500).to_list(500)
    return {"total": len(rows), "facilities": rows}


@storage_router.post("/admin/storage-facilities/{facility_id}/verify")
async def admin_verify_facility(
    facility_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(_require_admin),
):
    db = get_db()
    fac = await db.storage_facilities.find_one({"id": facility_id}, {"_id": 0})
    if not fac:
        raise HTTPException(status_code=404, detail="Facility not found")
    await db.storage_facilities.update_one(
        {"id": facility_id},
        {"$set": {
            "verified": True, "status": "verified",
            "verified_at": _now().isoformat(), "verified_by": current_user.id,
            # iter212 — flipping the global verify also marks the registration
            # as verified so admins don't have to click twice when both arrive
            # together. If they want to verify only the registration without
            # promoting the facility yet, use /verify-registration below.
            "company_registration_verified": True,
            "company_registration_verified_at": _now().isoformat(),
            "company_registration_verified_by": current_user.id,
            "company_registration_rejection_reason": None,
        }},
    )
    # Phase 6.2 hotfix — Mirror the role flip onto the OWNING user record so
    # the session-state check on /api/auth/me reflects facility approval the
    # moment the page is reloaded (previously the user doc was never updated,
    # which is why the "Are you a storage facility?" CTA kept showing for
    # already-approved accounts). Linkage field is `owner_user_id`.
    owner_id = fac.get("owner_user_id") or fac.get("user_id")
    if owner_id:
        await db.users.update_one(
            {"id": owner_id},
            {"$set": {
                "account_type": "storage_facility",
                "is_storage_facility": True,
                "storage_facility_approved": True,
                "facility_id": facility_id,
                "facility_verified": True,
            }},
        )
    try:
        from services.emails.email_marketplace import send_storage_facility_approved_email
        background_tasks.add_task(send_storage_facility_approved_email, fac)
    except Exception as e:
        logger.error(f"[STORAGE] approve email failed: {e}")

    # iter308 — Web push notification + admin audit log
    if owner_id:
        try:
            from services.push_dispatcher import dispatch_push
            owner = await db.users.find_one({"id": owner_id}, {"_id": 0, "preferred_language": 1})
            fr = ((owner or {}).get("preferred_language") or "").startswith("fr")
            preview = ("Votre installation a été vérifiée — vous pouvez maintenant lister des encans."
                       if fr else "Your facility has been verified — you can now list storage auctions.")
            await dispatch_push(
                db, user_id=owner_id, kind="new_message",
                sender_name="BidVex", preview=preview, url="/dashboard",
            )
        except Exception as e:
            logger.warning(f"[iter308] storage facility push failed: {e}")
    try:
        await db.admin_logs.insert_one({
            "id": __import__("uuid").uuid4().hex,
            "action": "storage_facility_verified",
            "admin_id": current_user.id, "admin_email": current_user.email,
            "target_user_id": owner_id,
            "details": {"facility_id": facility_id, "business_name": fac.get("business_name")},
            "timestamp": _now().isoformat(),
        })
    except Exception:
        pass

    return {"success": True, "facility_id": facility_id, "status": "verified"}


# ─────────────────────────────────────────────────────────────
# iter212 — Admin verify / reject the BUSINESS REGISTRATION (separate from
# the global facility verify above). These are surfaced as dedicated
# Verify/Reject buttons in the Admin storage-facilities table.
# ─────────────────────────────────────────────────────────────

@storage_router.post("/admin/storage-facilities/{facility_id}/verify-registration")
async def admin_verify_facility_registration(
    facility_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(_require_admin),
):
    """Mark only the company-registration document as verified.

    Does NOT auto-promote the facility's overall `status`. Use the legacy
    /verify endpoint to flip both at once.
    """
    db = get_db()
    fac = await db.storage_facilities.find_one({"id": facility_id}, {"_id": 0})
    if not fac:
        raise HTTPException(status_code=404, detail="Facility not found")
    await db.storage_facilities.update_one(
        {"id": facility_id},
        {"$set": {
            "company_registration_verified": True,
            "company_registration_verified_at": _now().isoformat(),
            "company_registration_verified_by": current_user.id,
            "company_registration_rejection_reason": None,
        }},
    )
    # Best-effort bilingual email notice
    try:
        from services.emails.email_marketplace import (
            send_storage_facility_registration_verified_email,
        )
        background_tasks.add_task(send_storage_facility_registration_verified_email, fac)
    except Exception as e:
        logger.warning(f"[STORAGE] verify-registration email failed: {e}")
    return {"success": True, "facility_id": facility_id, "company_registration_verified": True}


@storage_router.post("/admin/storage-facilities/{facility_id}/reject-registration")
async def admin_reject_facility_registration(
    facility_id: str,
    payload: dict,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(_require_admin),
):
    """Reject the company-registration document with a specific reason.

    The reason is emailed to the facility along with a deep link back to the
    registration form so they can resubmit a corrected document.
    """
    db = get_db()
    reason = (payload or {}).get("reason") or ""
    reason = reason.strip()
    if not reason:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "reason_required",
                "message_en": "A rejection reason is required so the facility knows what to fix.",
                "message_fr": "Un motif de rejet est requis pour que la facilité sache quoi corriger.",
            },
        )
    fac = await db.storage_facilities.find_one({"id": facility_id}, {"_id": 0})
    if not fac:
        raise HTTPException(status_code=404, detail="Facility not found")
    await db.storage_facilities.update_one(
        {"id": facility_id},
        {"$set": {
            "company_registration_verified": False,
            "company_registration_rejection_reason": reason,
            "company_registration_rejected_at": _now().isoformat(),
            "company_registration_rejected_by": current_user.id,
        }},
    )
    try:
        from services.emails.email_marketplace import (
            send_storage_facility_registration_rejected_email,
        )
        background_tasks.add_task(send_storage_facility_registration_rejected_email, fac, reason)
    except Exception as e:
        logger.warning(f"[STORAGE] reject-registration email failed: {e}")
    return {"success": True, "facility_id": facility_id, "company_registration_verified": False, "reason": reason}


@storage_router.post("/admin/storage-facilities/{facility_id}/request-resubmission")
async def admin_request_facility_resubmission(
    facility_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(_require_admin),
):
    """iter273 — Admin clicks "Request resubmission" on a facility whose
    registration document is missing on disk (lost in redeploy). Resets
    the `company_registration_verified` flag back to False, stamps
    `resubmission_requested_at` + `_by`, and fires a bilingual email to
    the facility owner with a deep link to the registration form so
    they can re-upload.

    Idempotent — safe to call multiple times. Never raises on email
    failure (admin still gets HTTP 200 with `email_sent: false`)."""
    db = get_db()
    fac = await db.storage_facilities.find_one({"id": facility_id}, {"_id": 0})
    if not fac:
        raise HTTPException(status_code=404, detail="Facility not found")

    now_iso = _now().isoformat()
    await db.storage_facilities.update_one(
        {"id": facility_id},
        {"$set": {
            "company_registration_verified": False,
            "company_registration_rejection_reason": (
                "Document missing on server — please re-upload your "
                "business registration proof so we can verify your facility."
            ),
            "company_registration_resubmission_requested_at": now_iso,
            "company_registration_resubmission_requested_by": current_user.id,
        }},
    )

    email_sent = False
    try:
        from services.emails.email_marketplace import (
            send_storage_facility_registration_rejected_email,
        )
        reason = (
            "Your previously uploaded business registration document is no "
            "longer available on our servers (it may have been lost during a "
            "recent platform redeployment). Please log in to your facility "
            "dashboard and re-upload your registration proof so we can "
            "complete your verification.\n\n"
            "Votre document d'enregistrement d'entreprise précédemment "
            "téléversé n'est plus disponible sur nos serveurs (il a peut-être "
            "été perdu lors d'un redéploiement récent de la plateforme). "
            "Veuillez vous connecter au tableau de bord de votre facilité et "
            "téléverser à nouveau votre preuve d'enregistrement afin que nous "
            "puissions compléter votre vérification."
        )
        background_tasks.add_task(send_storage_facility_registration_rejected_email, fac, reason)
        email_sent = True
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[STORAGE iter273] resubmission email failed: {exc}")

    return {
        "success":                  True,
        "facility_id":              facility_id,
        "email_sent":               email_sent,
        "requested_at":             now_iso,
        "owner_email":              fac.get("email"),
        "message_en":               "Resubmission request sent — the facility has been notified to re-upload their registration document.",
        "message_fr":               "Demande de soumission envoyée — la facilité a été notifiée pour téléverser à nouveau son document d'enregistrement.",
    }


@storage_router.get("/admin/storage-auctions")
async def admin_list_auctions(
    current_user: User = Depends(_require_admin),
    status: Optional[str] = None,
):
    db = get_db()
    q = {"status": status} if status else {}
    rows = await db.storage_auctions.find(q, {"_id": 0}).sort("created_at", -1).limit(500).to_list(500)
    for a in rows:
        a["live_status"] = _resolve_status(a)
    return {"total": len(rows), "auctions": rows}


@storage_router.put("/admin/storage-auctions/{auction_id}/cancel")
async def admin_cancel_auction(auction_id: str, current_user: User = Depends(_require_admin)):
    db = get_db()
    res = await db.storage_auctions.update_one(
        {"id": auction_id},
        {"$set": {"status": "cancelled", "cancelled_at": _now().isoformat(), "cancelled_by": current_user.id}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Auction not found")
    # Release any held deposits — losers get refunded, no winner exists
    try:
        await release_deposits_on_close(db, auction_id, winner_buyer_id=None)
    except Exception as e:
        logger.error(f"[STORAGE] release deposits on cancel failed: {e}")
    return {"success": True, "auction_id": auction_id, "status": "cancelled"}


@storage_router.post("/admin/storage-auctions/{auction_id}/release-deposits")
async def admin_release_deposits(auction_id: str, current_user: User = Depends(_require_admin)):
    """Manually trigger deposit release for an ended auction."""
    db = get_db()
    a = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0, "winning_bidder_id": 1})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    return await release_deposits_on_close(db, auction_id, a.get("winning_bidder_id"))


# iter290 — Admin hard-delete for storage auctions (parity with the
# vehicle delete added in iter287). The Manage All Auctions panel
# DELETE button now lands here when the row's `_section === 'storage'`.
@storage_router.delete("/admin/storage-auctions/{auction_id}")
async def admin_delete_storage_auction(
    auction_id: str,
    current_user: User = Depends(_require_admin),
):
    """Hard-delete a storage auction + cascade related rows.

    Drops the auction from `storage_auctions`, removes any cross-
    collection mirror in `listings`, and clears watchlist entries.
    Returns the deletion counts so the FE can confirm.
    """
    db = get_db()
    a = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0, "id": 1})
    cross = await db.listings.find_one({"id": auction_id}, {"_id": 0, "id": 1})
    if not a and not cross:
        raise HTTPException(status_code=404, detail="Storage auction not found")

    r_sa = await db.storage_auctions.delete_one({"id": auction_id})
    r_lst = await db.listings.delete_one({"id": auction_id})
    r_wl = await db.watchlists.delete_many({"listing_id": auction_id})
    return {
        "message": "Storage auction deleted",
        "id":       auction_id,
        "deleted":  {
            "storage_auctions": int(r_sa.deleted_count or 0),
            "listings_mirror":  int(r_lst.deleted_count or 0),
            "watchlists":       int(r_wl.deleted_count or 0),
        },
    }


@storage_router.post("/admin/storage-auctions/{auction_id}/forfeit-deposit")
async def admin_forfeit_deposit(
    auction_id: str,
    payload: dict,
    current_user: User = Depends(_require_admin),
):
    """Capture the held deposit as penalty (winner failed to pay)."""
    db = get_db()
    buyer_id = payload.get("buyer_id")
    reason = payload.get("reason") or "Payment deadline missed"
    if not buyer_id:
        raise HTTPException(status_code=400, detail="buyer_id required")
    return await forfeit_deposit(db, auction_id, buyer_id, reason)


@storage_router.post("/admin/storage-auctions")
async def admin_create_storage_auction(
    payload: StorageAuctionCreate,
    facility_id: str = Query(...),
    current_user: User = Depends(_require_admin),
):
    """
    Admin creates an auction on behalf of any facility. Bypasses the
    'must be verified facility' owner guard; admin takes responsibility.
    """
    db = get_db()
    facility = await db.storage_facilities.find_one({"id": facility_id}, {"_id": 0})
    if not facility:
        raise HTTPException(status_code=404, detail="Facility not found")

    # Reuse the same validation
    if payload.unit_size not in UNIT_SIZES:
        raise HTTPException(status_code=400, detail=f"unit_size must be one of {UNIT_SIZES}")
    if payload.unit_type not in UNIT_TYPES:
        raise HTTPException(status_code=400, detail=f"unit_type must be one of {UNIT_TYPES}")
    if payload.start_time >= payload.end_time:
        raise HTTPException(status_code=400, detail="end_time must be after start_time")
    if payload.payment_method not in PAYMENT_METHODS:
        raise HTTPException(status_code=400, detail=f"payment_method must be one of {PAYMENT_METHODS}")
    if payload.deposit_required and (not payload.deposit_amount or payload.deposit_amount <= 0):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "deposit_amount_required",
                "message_en": "You must set a deposit amount when requiring a deposit.",
                "message_fr": "Vous devez définir un montant de dépôt lorsqu'un dépôt est requis.",
            },
        )

    auction_id = str(uuid.uuid4())
    cleanup_deadline = payload.end_time + timedelta(hours=payload.cleanup_deadline_hours)
    starting = float(payload.starting_price)

    doc = {
        "id": auction_id,
        "facility_id": facility["id"],
        "facility_name": facility.get("company_name"),
        "facility_city": facility.get("city"),
        "facility_province": facility.get("province"),
        "unit_number": payload.unit_number,
        "unit_size": payload.unit_size,
        "unit_type": payload.unit_type,
        "is_lien_unit": payload.is_lien_unit,
        "past_due_balance": payload.past_due_balance,
        "description_en": payload.description_en,
        "description_fr": payload.description_fr or payload.description_en,
        "photos": payload.photos[:MAX_PHOTOS_PER_AUCTION],
        "video_url": payload.video_url,
        "starting_price": starting,
        "current_bid": starting,
        "reserve_price": payload.reserve_price,
        "reserve_met": False if payload.reserve_price else True,
        "bid_increment": float(payload.bid_increment),
        "start_time": payload.start_time.isoformat(),
        "end_time": payload.end_time.isoformat(),
        "soft_close_enabled": payload.soft_close_enabled,
        "soft_close_extension_minutes": payload.soft_close_extension_minutes,
        "status": "upcoming" if payload.start_time > _now() else "active",
        "winning_bidder_id": None,
        "winning_bid": None,
        "bid_count": 0,
        "bids": [],
        "payment_method": payload.payment_method,
        "payment_methods_accepted": [payload.payment_method],
        "payment_status": "pending",
        "deposit_required": bool(payload.deposit_required),
        "deposit_amount": float(payload.deposit_amount) if payload.deposit_amount else 0.0,
        "deposit_type": (payload.deposit_type or "fixed") if payload.deposit_required else None,
        "requires_deposit": bool(payload.deposit_required),
        "currency": (payload.currency or "CAD").upper(),
        "cleanup_deadline": cleanup_deadline.isoformat(),
        "created_by_admin": current_user.id,
        "created_at": _now().isoformat(),
        "updated_at": _now().isoformat(),
    }
    await db.storage_auctions.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc


# User-facing: list user's own deposits (iter172)
@storage_router.get("/my-storage-deposits")
async def my_storage_deposits(current_user: User = Depends(get_current_user)):
    """Return the current user's deposit history for the My Deposits profile tab."""
    db = get_db()
    rows = await db.storage_deposits.find(
        {"buyer_id": current_user.id},
        {"_id": 0},
    ).sort("created_at", -1).limit(200).to_list(200)

    # Enrich with auction unit_number/facility
    auction_ids = list({r.get("auction_id") for r in rows if r.get("auction_id")})
    auctions = {}
    if auction_ids:
        async for a in db.storage_auctions.find(
            {"id": {"$in": auction_ids}},
            {"_id": 0, "id": 1, "unit_number": 1, "facility_name": 1, "facility_city": 1, "facility_province": 1},
        ):
            auctions[a["id"]] = a
    for r in rows:
        a = auctions.get(r.get("auction_id", ""), {})
        r["auction_unit_number"] = a.get("unit_number", "—")
        r["facility_name"] = a.get("facility_name", "—")
        r["facility_city"] = a.get("facility_city")
        r["facility_province"] = a.get("facility_province")
    return {"total": len(rows), "deposits": rows}


# ─────────────────────────────────────────────────────────────
# STORAGE PROMOTION TIERS (iter172)
# ─────────────────────────────────────────────────────────────
STORAGE_PROMOTION_TIERS = {
    "basic": {
        "name_en": "Basic Boost",
        "name_fr": "Promotion de base",
        "price_cad": 9.99,
        "duration_days": 7,
        "features_en": ["Homepage stats bar priority", "Search result boost"],
        "features_fr": ["Priorité sur la barre de statistiques", "Améliore les résultats de recherche"],
    },
    "featured": {
        "name_en": "Featured Unit",
        "name_fr": "Unité en vedette",
        "price_cad": 24.99,
        "duration_days": 14,
        "features_en": ["Featured badge on card", "Homepage section priority", "Email blast to local buyers"],
        "features_fr": ["Badge vedette sur la carte", "Priorité section accueil", "Courriel aux acheteurs locaux"],
    },
    "premium": {
        "name_en": "Premium Spotlight",
        "name_fr": "Mise en vedette premium",
        "price_cad": 49.99,
        "duration_days": 30,
        "features_en": ["Top placement in all views", "Banner on storage browse", "Email blast to all buyers", "Social media feature"],
        "features_fr": ["Placement au sommet", "Bannière sur navigation", "Courriel à tous les acheteurs", "Promotion sur réseaux sociaux"],
    },
}


@storage_router.get("/storage-promotion-tiers")
async def get_storage_promotion_tiers():
    """Public — frontend pricing table."""
    return {"tiers": STORAGE_PROMOTION_TIERS}


@storage_router.post("/storage-auctions/{auction_id}/promote")
async def facility_promote_auction(
    auction_id: str,
    payload: dict,
    facility=Depends(_require_verified_facility),
):
    """
    Facility buys a promotion tier for one of their auctions.
    Returns a Stripe PaymentIntent client_secret so frontend can confirm payment.
    On successful payment, webhook (or manual confirmation) marks the auction
    with the promotion_tier + promoted_until timestamp.
    """
    tier = (payload.get("tier") or "").lower()
    if tier not in STORAGE_PROMOTION_TIERS:
        raise HTTPException(status_code=400, detail=f"tier must be one of {list(STORAGE_PROMOTION_TIERS.keys())}")

    db = get_db()
    auction = await db.storage_auctions.find_one(
        {"id": auction_id, "facility_id": facility["id"]},
        {"_id": 0},
    )
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found or not yours")

    spec = STORAGE_PROMOTION_TIERS[tier]
    price_cents = int(round(spec["price_cad"] * 100))

    # Create Stripe PaymentIntent
    try:
        import stripe as _stripe
        _stripe.api_key = os.environ.get("STRIPE_API_KEY")
        from services.stripe_circuit_breaker import safe_stripe_call_blocking
        pi = await safe_stripe_call_blocking(
            lambda: _stripe.PaymentIntent.create(
                amount=price_cents,
                currency="cad",
                automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                description=f"BidVex storage promotion: {tier} — auction {auction_id[:8]}",
                metadata={
                    "type": "storage_promotion",
                    "auction_id": auction_id,
                    "facility_id": facility["id"],
                    "tier": tier,
                    "duration_days": str(spec["duration_days"]),
                },
            ),
            operation_name="storage_promotion_payment_intent_create",
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[STORAGE_PROMOTION] PI create failed: {e}")
        raise HTTPException(status_code=502, detail=f"Stripe payment init failed: {e}")

    # Record the purchase intent
    await db.storage_promotion_purchases.insert_one({
        "auction_id": auction_id,
        "facility_id": facility["id"],
        "tier": tier,
        "price_cad": spec["price_cad"],
        "duration_days": spec["duration_days"],
        "stripe_payment_intent_id": pi.id,
        "status": "pending",
        "created_at": _now().isoformat(),
    })
    return {
        "payment_intent_id": pi.id,
        "client_secret": pi.client_secret,
        "amount_cad": spec["price_cad"],
        "tier": tier,
    }


@storage_router.post("/storage-auctions/{auction_id}/promote/confirm")
async def facility_confirm_promotion(
    auction_id: str,
    payload: dict,
    facility=Depends(_require_verified_facility),
):
    """
    Called by frontend after Stripe confirmCardPayment resolves with status=succeeded.
    Activates the promotion on the auction.
    """
    pi_id = payload.get("payment_intent_id")
    if not pi_id:
        raise HTTPException(status_code=400, detail="payment_intent_id required")

    # Verify with Stripe
    try:
        import stripe as _stripe
        _stripe.api_key = os.environ.get("STRIPE_API_KEY")
        pi = _stripe.PaymentIntent.retrieve(pi_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Stripe verify failed: {e}")

    if pi.status != "succeeded":
        raise HTTPException(status_code=402, detail=f"Payment not succeeded (status={pi.status})")

    db = get_db()
    purchase = await db.storage_promotion_purchases.find_one(
        {"stripe_payment_intent_id": pi_id, "facility_id": facility["id"]},
        {"_id": 0},
    )
    if not purchase:
        raise HTTPException(status_code=404, detail="Promotion purchase not found")

    tier = purchase["tier"]
    duration = int(purchase["duration_days"])
    promoted_until = (_now() + timedelta(days=duration)).isoformat()

    await db.storage_auctions.update_one(
        {"id": auction_id},
        {"$set": {
            "promotion_tier": tier,
            "promoted_until": promoted_until,
            "is_featured": tier in ("featured", "premium"),
            "updated_at": _now().isoformat(),
        }},
    )
    await db.storage_promotion_purchases.update_one(
        {"stripe_payment_intent_id": pi_id},
        {"$set": {"status": "active", "promoted_until": promoted_until, "confirmed_at": _now().isoformat()}},
    )
    return {"success": True, "auction_id": auction_id, "tier": tier, "promoted_until": promoted_until}


@storage_router.post("/admin/storage-auctions/{auction_id}/grant-promotion")
async def admin_grant_promotion(
    auction_id: str,
    payload: dict,
    current_user: User = Depends(_require_admin),
):
    """Admin comps a promotion for free (e.g. launch partner)."""
    tier = (payload.get("tier") or "").lower()
    days = int(payload.get("duration_days") or STORAGE_PROMOTION_TIERS.get(tier, {}).get("duration_days", 7))
    if tier not in STORAGE_PROMOTION_TIERS:
        raise HTTPException(status_code=400, detail=f"tier must be one of {list(STORAGE_PROMOTION_TIERS.keys())}")
    db = get_db()
    promoted_until = (_now() + timedelta(days=days)).isoformat()
    res = await db.storage_auctions.update_one(
        {"id": auction_id},
        {"$set": {
            "promotion_tier": tier,
            "promoted_until": promoted_until,
            "is_featured": tier in ("featured", "premium"),
            "promotion_granted_by": current_user.id,
            "promotion_granted_at": _now().isoformat(),
            "updated_at": _now().isoformat(),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Auction not found")
    return {"success": True, "auction_id": auction_id, "tier": tier, "promoted_until": promoted_until}


@storage_router.post("/admin/storage-auctions/{auction_id}/revoke-promotion")
async def admin_revoke_promotion(auction_id: str, current_user: User = Depends(_require_admin)):
    """Remove a promotion immediately."""
    db = get_db()
    res = await db.storage_auctions.update_one(
        {"id": auction_id},
        {"$set": {
            "promotion_tier": None,
            "promoted_until": None,
            "is_featured": False,
            "promotion_revoked_by": current_user.id,
            "promotion_revoked_at": _now().isoformat(),
        }},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Auction not found")
    return {"success": True, "auction_id": auction_id}


# ─────────────────────────────────────────────────────────────
# ADMIN STORAGE AUCTION + FACILITY CONTROLS (iter172)
# ─────────────────────────────────────────────────────────────

@storage_router.post("/admin/storage-facilities/{facility_id}/reject")
async def admin_reject_facility(
    facility_id: str,
    payload: dict,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(_require_admin),
):
    db = get_db()
    reason = payload.get("reason") or "Does not meet verification requirements."
    fac = await db.storage_facilities.find_one({"id": facility_id}, {"_id": 0})
    if not fac:
        raise HTTPException(status_code=404, detail="Facility not found")
    await db.storage_facilities.update_one(
        {"id": facility_id},
        {"$set": {
            "status": "rejected", "verified": False,
            "rejected_at": _now().isoformat(), "rejected_by": current_user.id,
            "rejection_reason": reason,
        }},
    )

    # iter308 — Email + push + admin audit
    owner_id = fac.get("owner_user_id") or fac.get("user_id")
    if owner_id:
        owner = await db.users.find_one({"id": owner_id}, {"_id": 0, "email": 1, "name": 1, "preferred_language": 1})
        if owner and owner.get("email"):
            try:
                subject = "Your facility verification was not approved / Vérification non approuvée"
                body = (
                    f"<p>Hello {owner.get('name','')},</p>"
                    f"<p>Your storage facility application was not approved.</p>"
                    f"<p><b>Reason:</b> {reason}</p>"
                    f"<p>To appeal or resubmit: <a href=\"mailto:support@bidvex.com\">support@bidvex.com</a></p>"
                    f"<hr><p>Bonjour {owner.get('name','')},</p>"
                    f"<p>Votre demande d'installation de stockage n'a pas été approuvée.</p>"
                    f"<p><b>Raison :</b> {reason}</p>"
                    f"<p>Pour faire appel : <a href=\"mailto:support@bidvex.com\">support@bidvex.com</a></p>"
                )
                from services.emails._email_core import send_email
                background_tasks.add_task(send_email, owner["email"], subject, body)
            except Exception as e:
                logger.warning(f"[iter308] facility reject email failed: {e}")
        try:
            from services.push_dispatcher import dispatch_push
            fr = ((owner or {}).get("preferred_language") or "").startswith("fr")
            preview = (f"Votre vérification d'installation n'a pas été approuvée. Raison : {reason[:80]}"
                       if fr else f"Your facility verification was not approved. Reason: {reason[:80]}")
            await dispatch_push(
                db, user_id=owner_id, kind="new_message",
                sender_name="BidVex", preview=preview, url="/dashboard",
            )
        except Exception as e:
            logger.warning(f"[iter308] facility reject push failed: {e}")
    try:
        await db.admin_logs.insert_one({
            "id": __import__("uuid").uuid4().hex,
            "action": "storage_facility_rejected",
            "admin_id": current_user.id, "admin_email": current_user.email,
            "target_user_id": owner_id,
            "details": {"facility_id": facility_id, "reason": reason},
            "timestamp": _now().isoformat(),
        })
    except Exception:
        pass

    return {"success": True, "facility_id": facility_id, "status": "rejected"}


@storage_router.post("/admin/storage-facilities/{facility_id}/suspend")
async def admin_suspend_facility(facility_id: str, current_user: User = Depends(_require_admin)):
    db = get_db()
    res = await db.storage_facilities.update_one(
        {"id": facility_id},
        {"$set": {"status": "suspended", "suspended_at": _now().isoformat(), "suspended_by": current_user.id}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Facility not found")
    await db.storage_auctions.update_many(
        {"facility_id": facility_id, "status": "active"},
        {"$set": {"status": "suspended", "updated_at": _now().isoformat()}},
    )
    return {"success": True, "facility_id": facility_id, "status": "suspended"}


@storage_router.post("/admin/storage-facilities/{facility_id}/unsuspend")
async def admin_unsuspend_facility(facility_id: str, current_user: User = Depends(_require_admin)):
    db = get_db()
    res = await db.storage_facilities.update_one(
        {"id": facility_id},
        {"$set": {"status": "verified", "verified": True, "unsuspended_at": _now().isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Facility not found")
    await db.storage_auctions.update_many(
        {"facility_id": facility_id, "status": "suspended"},
        {"$set": {"status": "active", "updated_at": _now().isoformat()}},
    )
    return {"success": True, "facility_id": facility_id, "status": "verified"}


@storage_router.delete("/admin/storage-facilities/{facility_id}")
async def admin_delete_facility(facility_id: str, current_user: User = Depends(_require_admin)):
    db = get_db()
    fac = await db.storage_facilities.find_one({"id": facility_id}, {"_id": 0, "id": 1})
    if not fac:
        raise HTTPException(status_code=404, detail="Facility not found")
    await db.storage_auctions.delete_many({"facility_id": facility_id})
    await db.storage_facilities.delete_one({"id": facility_id})
    return {"success": True, "facility_id": facility_id, "deleted": True}


@storage_router.post("/admin/storage-auctions/{auction_id}/pause")
async def admin_pause_auction(auction_id: str, current_user: User = Depends(_require_admin)):
    db = get_db()
    res = await db.storage_auctions.update_one(
        {"id": auction_id},
        {"$set": {"status": "paused", "paused_at": _now().isoformat(), "paused_by": current_user.id}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Auction not found")
    return {"success": True, "auction_id": auction_id, "status": "paused"}


@storage_router.post("/admin/storage-auctions/{auction_id}/resume")
async def admin_resume_auction(auction_id: str, current_user: User = Depends(_require_admin)):
    db = get_db()
    res = await db.storage_auctions.update_one(
        {"id": auction_id, "status": "paused"},
        {"$set": {"status": "active", "resumed_at": _now().isoformat()}},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Auction not found or not paused")
    return {"success": True, "auction_id": auction_id, "status": "active"}


@storage_router.put("/admin/storage-auctions/{auction_id}")
async def admin_edit_auction(
    auction_id: str,
    payload: dict,
    current_user: User = Depends(_require_admin),
):
    db = get_db()
    updates = {}
    for field in ("unit_number", "description_en", "description_fr", "reserve_price",
                  "starting_price", "bid_increment", "payment_method",
                  "deposit_required", "deposit_amount", "promotion_tier"):
        if field in payload:
            updates[field] = payload[field]
    if "end_time" in payload and payload["end_time"]:
        updates["end_time"] = payload["end_time"]
    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")
    updates["updated_at"] = _now().isoformat()
    updates["updated_by_admin"] = current_user.id
    res = await db.storage_auctions.update_one({"id": auction_id}, {"$set": updates})
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Auction not found")
    return {"success": True, "updated_fields": list(updates.keys())}


@storage_router.delete("/admin/storage-auctions/{auction_id}")
async def admin_delete_auction(auction_id: str, current_user: User = Depends(_require_admin)):
    db = get_db()
    a = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    try:
        await release_deposits_on_close(db, auction_id, winner_buyer_id=None)
    except Exception as e:
        logger.error(f"[STORAGE] release deposits on delete failed: {e}")
    await db.storage_auctions.delete_one({"id": auction_id})
    return {"success": True, "auction_id": auction_id, "deleted": True}


@storage_router.post("/admin/storage-auctions/{auction_id}/override-winner")
async def admin_override_winner(
    auction_id: str,
    payload: dict,
    current_user: User = Depends(_require_admin),
):
    db = get_db()
    new_winner_id = payload.get("winner_id")
    reason = (payload.get("reason") or "").strip()
    if not new_winner_id or not reason:
        raise HTTPException(status_code=400, detail="winner_id and reason required")
    a = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    has_bid = any(b.get("bidder_id") == new_winner_id for b in a.get("bids", []))
    if not has_bid:
        raise HTTPException(status_code=400, detail="Target user has no bid on this auction")
    await db.storage_auctions.update_one(
        {"id": auction_id},
        {"$set": {
            "winning_bidder_id": new_winner_id,
            "override_winner_by": current_user.id,
            "override_winner_at": _now().isoformat(),
            "override_winner_reason": reason,
            "updated_at": _now().isoformat(),
        }},
    )
    return {"success": True, "auction_id": auction_id, "new_winner_id": new_winner_id}


@storage_router.post("/admin/storage-auctions/{auction_id}/force-close")
async def admin_force_close(
    auction_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(_require_admin),
):
    db = get_db()
    a = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    if a.get("status") not in ("active", "paused"):
        raise HTTPException(status_code=400, detail=f"Cannot force-close auction with status={a.get('status')}")
    from services.scheduled_jobs import process_ended_storage_auctions
    await db.storage_auctions.update_one(
        {"id": auction_id},
        {"$set": {"end_time": _now().isoformat(), "status": "active"}},
    )
    result = await process_ended_storage_auctions(db)
    return {"success": True, "auction_id": auction_id, "close_result": result}


# ─────────────────────────────────────────────────────────────
# DIGITAL PICKUP CODE (iter172)
# ─────────────────────────────────────────────────────────────

@storage_router.post("/storage-facilities/verify-pickup-code")
async def facility_verify_pickup_code(
    payload: dict,
    facility=Depends(_require_verified_facility),
):
    """
    Facility enters a buyer's pickup code to verify → returns winner + unit.
    Does NOT mark it used. Call /mark-picked-up after identity verification.
    """
    code = (payload.get("pickup_code") or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="pickup_code required")

    db = get_db()
    auction = await db.storage_auctions.find_one(
        {"pickup_code": code, "facility_id": facility["id"]},
        {"_id": 0},
    )
    if not auction:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "pickup_code_invalid",
                "message_en": "Pickup code not found for this facility.",
                "message_fr": "Code de récupération introuvable pour cette facilité.",
            },
        )
    if auction.get("pickup_code_used"):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "pickup_code_already_used",
                "used_at": auction.get("pickup_code_used_at"),
                "message_en": "This pickup code has already been used.",
                "message_fr": "Ce code de récupération a déjà été utilisé.",
            },
        )

    winner = {}
    if auction.get("winning_bidder_id"):
        winner = await db.users.find_one(
            {"id": auction["winning_bidder_id"]},
            {"_id": 0, "id": 1, "name": 1, "full_name": 1, "email": 1, "phone": 1},
        ) or {}

    return {
        "auction_id": auction["id"],
        "unit_number": auction.get("unit_number"),
        "unit_size": auction.get("unit_size"),
        "winning_bid": auction.get("winning_bid"),
        "payment_method": auction.get("payment_method"),
        "winner": winner,
        "pickup_code": code,
        "cleanup_deadline": auction.get("cleanup_deadline"),
    }


@storage_router.post("/storage-facilities/mark-picked-up")
async def facility_mark_picked_up(
    payload: dict,
    facility=Depends(_require_verified_facility),
):
    """Facility marks a pickup code as used after verifying the buyer."""
    code = (payload.get("pickup_code") or "").strip().upper()
    if not code:
        raise HTTPException(status_code=400, detail="pickup_code required")

    db = get_db()
    result = await db.storage_auctions.update_one(
        {"pickup_code": code, "facility_id": facility["id"], "pickup_code_used": False},
        {
            "$set": {
                "pickup_code_used": True,
                "pickup_code_used_at": _now().isoformat(),
                "pickup_verified_by": facility["owner_user_id"],
            }
        },
    )
    if result.matched_count == 0:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "pickup_code_not_found_or_used",
                "message_en": "Code not found or already used.",
                "message_fr": "Code introuvable ou déjà utilisé.",
            },
        )
    return {"success": True, "pickup_code": code, "used_at": _now().isoformat()}


@storage_router.post("/admin/storage-auctions/{auction_id}/regenerate-pickup-code")
async def admin_regenerate_pickup_code(
    auction_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(_require_admin),
):
    """Admin regenerates a pickup code (e.g. user lost it). Sends new email to winner."""
    db = get_db()
    auction = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    if auction.get("status") != "sold":
        raise HTTPException(status_code=400, detail="Pickup codes exist only for sold auctions")

    from services.scheduled_jobs import generate_pickup_code
    new_code = generate_pickup_code()
    await db.storage_auctions.update_one(
        {"id": auction_id},
        {"$set": {"pickup_code": new_code, "pickup_code_used": False, "pickup_code_used_at": None}},
    )
    # Re-fire the winner email with the new code (best effort)
    try:
        from services.emails.email_marketplace import send_storage_auction_won_email
        buyer = await db.users.find_one({"id": auction["winning_bidder_id"]}, {"_id": 0}) or {}
        facility = await db.storage_facilities.find_one({"id": auction["facility_id"]}, {"_id": 0}) or {}
        auction["pickup_code"] = new_code
        background_tasks.add_task(send_storage_auction_won_email, buyer, auction, facility, None)
    except Exception as e:
        logger.error(f"[STORAGE] regenerate pickup code email failed: {e}")
    return {"success": True, "pickup_code": new_code}


# ─────────────────────────────────────────────────────────────
# PICKUP QR CODE (iter173)
# ─────────────────────────────────────────────────────────────

def _generate_pickup_qr_png_bytes(pickup_code: str) -> bytes:
    """Render a high-contrast PNG QR encoding the pickup code. Returns raw bytes."""
    import io
    import qrcode
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_H,
        box_size=10,
        border=2,
    )
    qr.add_data(pickup_code)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="#FFFFFF")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@storage_router.get("/storage-auctions/{auction_id}/pickup-qr")
async def get_pickup_qr(
    auction_id: str,
    current_user: User = Depends(get_current_user),
):
    """
    Returns a PNG QR code encoding the pickup_code for this auction.
    Accessible ONLY to:
      • the winning bidder
      • the facility that owns the auction
      • an admin
    The QR encodes just the pickup code string (BV-XXXX-XXXX).
    """
    from fastapi.responses import Response

    db = get_db()
    auction = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    pickup_code = auction.get("pickup_code")
    if not pickup_code:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "no_pickup_code",
                "message_en": "No pickup code available for this auction yet.",
                "message_fr": "Aucun code de récupération disponible pour cette enchère.",
            },
        )

    # Authorization
    is_winner = auction.get("winning_bidder_id") == current_user.id
    is_admin = current_user.role == "admin"
    is_facility_owner = False
    if not is_winner and not is_admin:
        fac = await db.storage_facilities.find_one(
            {"id": auction.get("facility_id"), "owner_user_id": current_user.id},
            {"_id": 0, "id": 1},
        )
        is_facility_owner = bool(fac)

    if not (is_winner or is_admin or is_facility_owner):
        raise HTTPException(status_code=403, detail="Not authorized to view this pickup code")

    png_bytes = _generate_pickup_qr_png_bytes(pickup_code)
    return Response(
        content=png_bytes,
        media_type="image/png",
        headers={
            "Cache-Control": "private, max-age=300",
            "X-Pickup-Code": pickup_code,
        },
    )


# ─────────────────────────────────────────────────────────────
# ADMIN DEPOSITS DASHBOARD (iter171)
# ─────────────────────────────────────────────────────────────

@storage_router.get("/admin/storage-deposits")
async def admin_list_deposits(
    current_user: User = Depends(_require_admin),
    status: Optional[str] = Query(None),
):
    """
    Returns deposit stats + a flat list of all deposits (enriched with
    bidder name / auction unit number / facility name for the UI table).
    """
    db = get_db()

    # Count by status (4 KPI cards). Stripe stores 'held' after authorization,
    # but the spec labels this as 'Active Holds' (authorized). We count BOTH
    # 'held' and 'authorized' for safety.
    pipe = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}]
    by_status = {}
    async for r in db.storage_deposits.aggregate(pipe):
        by_status[r["_id"]] = r["count"]

    stats = {
        "active_holds": by_status.get("held", 0) + by_status.get("authorized", 0),
        "applied": by_status.get("applied", 0),
        "refunded": by_status.get("refunded", 0),
        "forfeited": by_status.get("forfeited", 0),
    }

    # Rows
    q = {}
    if status:
        # Accept 'active' as an alias for held + authorized
        if status == "active":
            q["status"] = {"$in": ["held", "authorized"]}
        else:
            q["status"] = status
    rows = await db.storage_deposits.find(q, {"_id": 0}).sort("created_at", -1).limit(500).to_list(500)

    # Enrich
    buyer_ids = list({r.get("buyer_id") for r in rows if r.get("buyer_id")})
    auction_ids = list({r.get("auction_id") for r in rows if r.get("auction_id")})

    buyers = {}
    if buyer_ids:
        async for u in db.users.find({"id": {"$in": buyer_ids}}, {"_id": 0, "id": 1, "name": 1, "full_name": 1, "email": 1}):
            buyers[u["id"]] = u

    auctions = {}
    fac_ids_set = set()
    if auction_ids:
        async for a in db.storage_auctions.find(
            {"id": {"$in": auction_ids}},
            {"_id": 0, "id": 1, "unit_number": 1, "facility_id": 1, "facility_name": 1, "current_bid": 1},
        ):
            auctions[a["id"]] = a
            if a.get("facility_id"):
                fac_ids_set.add(a["facility_id"])

    facilities = {}
    if fac_ids_set:
        async for f in db.storage_facilities.find(
            {"id": {"$in": list(fac_ids_set)}},
            {"_id": 0, "id": 1, "company_name": 1},
        ):
            facilities[f["id"]] = f

    enriched = []
    for r in rows:
        auc = auctions.get(r.get("auction_id", ""), {})
        fac = facilities.get(auc.get("facility_id", ""), {})
        buyer = buyers.get(r.get("buyer_id", ""), {})
        enriched.append({
            **r,
            "bidder_name": buyer.get("full_name") or buyer.get("name") or buyer.get("email") or "—",
            "bidder_email": buyer.get("email") or "—",
            "auction_unit_number": auc.get("unit_number", "—"),
            "facility_name": fac.get("company_name") or auc.get("facility_name") or "—",
        })

    return {"stats": stats, "total": len(enriched), "deposits": enriched}


# ─────────────────────────────────────────────────────────────
# PRICING PREVIEW (used by detail page + dashboard)
# ─────────────────────────────────────────────────────────────

@storage_router.get("/storage-auctions/{auction_id}/pricing")
async def auction_pricing_preview(
    auction_id: str,
    payment_method: str = Query(None),
    deposit_amount: float = Query(None),
):
    db = get_db()
    a = await db.storage_auctions.find_one(
        {"id": auction_id},
        {"_id": 0, "current_bid": 1, "facility_province": 1, "payment_method": 1, "deposit_required": 1, "deposit_amount": 1},
    )
    if not a:
        # iter284 — Dual-visibility fallback. Storage listings created via
        # /create-listing live in `db.listings`. Synthesize the same shape
        # so the detail page's `/pricing` call resolves successfully.
        from services.listing_sections import STORAGE_TYPES
        ld = await db.listings.find_one(
            {
                "id": auction_id,
                "$or": [
                    {"listing_type": {"$in": list(STORAGE_TYPES)}},
                    {"section": "storage"},
                ],
            },
            {"_id": 0, "current_price": 1, "starting_price": 1, "region": 1, "requires_deposit": 1, "deposit_amount": 1},
        )
        if not ld:
            raise HTTPException(status_code=404, detail="Auction not found")
        a = {
            "current_bid":       ld.get("current_price") or ld.get("starting_price") or 0,
            "facility_province": ld.get("region") or "",
            "payment_method":    "stripe",
            "deposit_required":  bool(ld.get("requires_deposit") or False),
            "deposit_amount":    float(ld.get("deposit_amount") or 0),
        }
    pm = (payment_method or a.get("payment_method") or "stripe").lower()
    dep = deposit_amount if deposit_amount is not None else (
        float(a.get("deposit_amount") or 0) if a.get("deposit_required") else 0
    )
    return calculate_storage_pricing(
        a.get("current_bid", 0),
        a.get("facility_province", ""),
        pm,
        deposit_amount=dep,
    )
