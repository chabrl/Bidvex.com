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
from typing import List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Query, UploadFile, File, Form, BackgroundTasks
)

from deps import User, get_current_user, get_db
from models.storage_auction import (
    StorageFacilityRegister, StorageAuctionCreate, StorageBidPayload,
    UNIT_SIZES, UNIT_TYPES, PAYMENT_METHODS, AUCTION_STATUSES, CANADIAN_PROVINCES,
)
from services.storage_pricing import calculate_storage_pricing
from services.storage_auction_service import place_bid as _place_bid_proxy

logger = logging.getLogger(__name__)

storage_router = APIRouter()

UPLOAD_ROOT = "/app/uploads/storage-auctions"
ALLOWED_PHOTO_MIME = {"image/png", "image/jpeg", "image/jpg", "image/webp"}
MAX_PHOTO_BYTES = 8 * 1024 * 1024  # 8 MB per photo
MAX_PHOTOS_PER_AUCTION = 10


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
    return fac


def _now():
    return datetime.now(timezone.utc)


def _parse_dt(v):
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _resolve_status(auction: dict) -> str:
    """Compute live status from time fields."""
    now = _now()
    start = _parse_dt(auction["start_time"])
    end = _parse_dt(auction["end_time"])
    persisted = auction.get("status")
    if persisted in {"sold", "cancelled"}:
        return persisted
    if now < start:
        return "upcoming"
    if now >= end:
        return "ended"
    return "active"


# ─────────────────────────────────────────────────────────────
# PUBLIC ROUTES
# ─────────────────────────────────────────────────────────────

@storage_router.get("/storage-auctions/provinces")
async def list_provinces():
    """Province → active-auction count."""
    db = get_db()
    now = _now().isoformat()
    pipe = [
        {"$match": {"status": "active", "end_time": {"$gt": now}}},
        {"$group": {"_id": "$facility_province", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    results = await db.storage_auctions.aggregate(pipe).to_list(20)
    return {
        "provinces": [{"province": r["_id"], "count": r["count"]} for r in results if r["_id"]]
    }


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
):
    db = get_db()
    now = _now()

    query = {"status": {"$in": ["active", "upcoming"]}}
    if province:
        query["facility_province"] = province.upper()
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

    if status == "ending_soon":
        cutoff = (now + timedelta(hours=1)).isoformat()
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
    sort_spec = sort_map.get(sort, sort_map["ending_soon"])
    cursor = db.storage_auctions.find(query, {"_id": 0}).sort(sort_spec).skip(skip).limit(limit)
    auctions = await cursor.to_list(limit)
    total = await db.storage_auctions.count_documents(query)

    # Live status reconciliation
    for a in auctions:
        a["live_status"] = _resolve_status(a)
    return {"total": total, "auctions": auctions, "limit": limit, "skip": skip, "sort": sort}


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
        raise HTTPException(status_code=404, detail="Auction not found")
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
        raise HTTPException(status_code=404, detail="Auction not found")
    bids = a.get("bids", [])
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
async def place_storage_bid(
    auction_id: str,
    payload: StorageBidPayload,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
):
    db = get_db()
    result = await _place_bid_proxy(db, auction_id, current_user.id, float(payload.max_bid))

    # Send bid-confirmation + outbid emails (non-blocking)
    try:
        from services.email_notifications import send_storage_bid_placed_email, send_storage_outbid_email
        auction = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
        background_tasks.add_task(send_storage_bid_placed_email, current_user.dict() if hasattr(current_user, "dict") else dict(current_user), auction, result)
        if result.get("outbid_user_id"):
            outbid = await db.users.find_one({"id": result["outbid_user_id"]}, {"_id": 0})
            if outbid:
                background_tasks.add_task(send_storage_outbid_email, outbid, auction, result["current_bid"])
    except Exception as e:
        logger.error(f"[STORAGE] bid-email schedule failed: {e}")

    return result


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
        raise HTTPException(status_code=400, detail="A facility profile already exists for this account.")

    fac_id = str(uuid.uuid4())
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
        "verified": False,
        "status": "pending_verification",
        "seller_tier": "storage_facility",  # always 5% commission
        "stripe_account_id": None,
        "total_units_sold": 0,
        "average_sale_price": 0.0,
        "created_at": _now().isoformat(),
        "updated_at": _now().isoformat(),
    }
    await db.storage_facilities.insert_one(doc.copy())

    # Notify admin (non-blocking)
    try:
        from services.email_notifications import (
            send_storage_facility_registration_admin_alert,
            send_storage_facility_pending_user_email,
        )
        background_tasks.add_task(send_storage_facility_registration_admin_alert, doc)
        background_tasks.add_task(send_storage_facility_pending_user_email, doc)
    except Exception as e:
        logger.error(f"[STORAGE] registration email failed: {e}")

    doc.pop("_id", None)
    return doc


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
    invalid_methods = [m for m in payload.payment_methods_accepted if m not in PAYMENT_METHODS]
    if invalid_methods:
        raise HTTPException(status_code=400, detail=f"Invalid payment methods: {invalid_methods}")

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
        "payment_method": None,
        "payment_status": "pending",
        "cleanup_deadline": cleanup_deadline.isoformat(),
        "cleanup_deposit": float(payload.cleanup_deposit),
        "payment_methods_accepted": payload.payment_methods_accepted,
        "created_at": _now().isoformat(),
        "updated_at": _now().isoformat(),
    }
    await db.storage_auctions.insert_one(doc.copy())
    doc.pop("_id", None)
    return doc


@storage_router.get("/storage-facilities/my-auctions")
async def my_facility_auctions(facility=Depends(_require_verified_facility)):
    db = get_db()
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
async def facility_dashboard(facility=Depends(_require_verified_facility)):
    db = get_db()
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
        {"$set": {"verified": True, "status": "verified", "verified_at": _now().isoformat(), "verified_by": current_user.id}},
    )
    try:
        from services.email_notifications import send_storage_facility_approved_email
        background_tasks.add_task(send_storage_facility_approved_email, fac)
    except Exception as e:
        logger.error(f"[STORAGE] approve email failed: {e}")
    return {"success": True, "facility_id": facility_id, "status": "verified"}


@storage_router.put("/admin/storage-facilities/{facility_id}/suspend")
async def admin_suspend_facility(facility_id: str, current_user: User = Depends(_require_admin)):
    db = get_db()
    res = await db.storage_facilities.update_one(
        {"id": facility_id}, {"$set": {"status": "suspended", "verified": False, "suspended_at": _now().isoformat()}}
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Facility not found")
    return {"success": True, "facility_id": facility_id, "status": "suspended"}


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
    return {"success": True, "auction_id": auction_id, "status": "cancelled"}


# ─────────────────────────────────────────────────────────────
# PRICING PREVIEW (used by detail page + dashboard)
# ─────────────────────────────────────────────────────────────

@storage_router.get("/storage-auctions/{auction_id}/pricing")
async def auction_pricing_preview(
    auction_id: str,
    payment_method: str = Query("stripe"),
):
    db = get_db()
    a = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0, "current_bid": 1, "facility_province": 1})
    if not a:
        raise HTTPException(status_code=404, detail="Auction not found")
    return calculate_storage_pricing(a.get("current_bid", 0), a.get("facility_province", ""), payment_method)
