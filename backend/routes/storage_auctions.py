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
    StorageFacilityRegister, StorageAuctionCreate, StorageBidPayload, StorageDepositRequest,
    UNIT_SIZES, UNIT_TYPES, PAYMENT_METHODS, AUCTION_STATUSES, CANADIAN_PROVINCES,
)
from services.storage_pricing import calculate_storage_pricing
from services.storage_auction_service import place_bid as _place_bid_proxy
from services.storage_deposit_service import (
    create_deposit_hold,
    get_existing_deposit,
    release_deposits_on_close,
    forfeit_deposit,
)

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

    # ── Deposit guard ──
    auction = await db.storage_auctions.find_one(
        {"id": auction_id},
        {"_id": 0, "deposit_required": 1, "deposit_amount": 1, "status": 1},
    )
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
        from services.email_notifications import send_storage_bid_placed_email, send_storage_outbid_email
        a = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
        background_tasks.add_task(send_storage_bid_placed_email, current_user.dict() if hasattr(current_user, "dict") else dict(current_user), a, result)
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
        "deposit_description_en": payload.deposit_description_en,
        "deposit_description_fr": payload.deposit_description_fr,
        "cleanup_deadline": cleanup_deadline.isoformat(),
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
        raise HTTPException(status_code=404, detail="Auction not found")
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
