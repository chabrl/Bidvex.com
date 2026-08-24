"""
BidVex - Admin Operations (Reports, Listings, Users, Finance)
Auto-extracted from server.py during P2 refactoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect, BackgroundTasks
from deps import get_db, get_current_user, get_current_user_optional, require_admin, User
from services.sanitizer import sanitize_string, safe_regex
from shared import (
    DEFAULT_EMAIL_TEMPLATES, EMAIL_TEMPLATE_CATEGORIES,
    DEFAULT_MARKETPLACE_SETTINGS, AFFILIATE_COMMISSION_RATE,
    generate_affiliate_code, get_email_templates, get_email_template_id,
    get_marketplace_settings, get_epoch_timestamp, get_server_timestamp,
    calculate_buyer_fees, calculate_seller_fees, calculate_stripe_fee_recovery,
    calculate_partner_checkout, calculate_standard_checkout,
    FeeCalculation, UserCreate, Category, Invoice, PaddleNumber,
    PaymentTransaction, SessionCreate, get_minimum_increment,
    STANDARD_BUYER_PREMIUM_RATE, STANDARD_SELLER_COMMISSION_RATE,
    PARTNER_PLATFORM_FEE_RATE, PARTNER_ANNUAL_ACCESS_FEE,
    STRIPE_PERCENTAGE_FEE, STRIPE_FIXED_FEE,
)
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from pathlib import Path
import logging
import uuid
import os as _os
import json as _json

logger = logging.getLogger(__name__)

from services.email_service import get_email_service
import stripe
import csv
import io
from starlette.responses import StreamingResponse

admin_ops_router = APIRouter(tags=["Admin Operations"])


# ============= SCHEDULER HEALTH (Admin Dashboard) =============

@admin_ops_router.get("/admin/scheduler/status")
async def get_scheduler_status(current_user: User = Depends(require_admin)):
    """Show last run time / status / duration for every scheduled job.

    Used by the Admin Dashboard `Scheduler Status` card.
    """
    from services.scheduled_jobs import get_job_status_snapshot

    statuses = get_job_status_snapshot()

    # Merge in APScheduler-reported metadata (next_run_time) if available
    jobs_out = []
    try:
        from server import scheduler as ap_scheduler
        ap_jobs = {j.id: j for j in ap_scheduler.get_jobs()}
    except Exception:
        ap_jobs = {}

    # Also include the standalone vehicle scheduler jobs
    try:
        from services.scheduler import scheduler as vehicle_scheduler
        if vehicle_scheduler is not None:
            for j in vehicle_scheduler.get_jobs():
                ap_jobs.setdefault(j.id, j)
    except Exception:
        pass

    all_job_ids = set(statuses.keys()) | set(ap_jobs.keys())
    for jid in sorted(all_job_ids):
        s = statuses.get(jid, {})
        ap_j = ap_jobs.get(jid)
        jobs_out.append({
            "name": jid,
            "last_run": s.get("last_run"),
            "last_status": s.get("last_status", "pending"),
            "last_duration_ms": s.get("last_duration_ms"),
            "last_error": s.get("last_error"),
            "next_run": ap_j.next_run_time.isoformat() if ap_j and ap_j.next_run_time else None,
        })

    return {
        "jobs": jobs_out,
        "total_jobs": len(jobs_out),
        "scheduler_running": bool(ap_jobs),
    }


@admin_ops_router.get("/admin/reports")
async def admin_get_reports(current_user: User = Depends(require_admin)):
    db = get_db()
    reports = await db.reports.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return reports


# ============= PROMOTIONS MANAGEMENT =============

@admin_ops_router.get("/admin/promotions")
async def admin_list_promotions(
    status: str = "active",
    current_user: User = Depends(require_admin),
):
    """Admin: list active or expired promotions across all listing types."""
    db = get_db()
    query = {}
    if status == "active":
        query["status"] = "active"
    elif status == "expired":
        query["status"] = "expired"
    elif status == "all":
        pass
    promos = await db.promotions.find(query, {"_id": 0}).sort("created_at", -1).limit(500).to_list(500)
    for p in promos:
        try:
            coll = db.storage_auctions if p.get("listing_type") == "storage" else db.listings
            lst = await coll.find_one({"id": p.get("listing_id")}, {"_id": 0, "title": 1})
            if lst:
                p["listing_title"] = lst.get("title", "")
            u = await db.users.find_one({"id": p.get("seller_id")}, {"_id": 0, "name": 1, "email": 1})
            if u:
                p["seller_name"] = u.get("name", "")
                p["seller_email"] = u.get("email", "")
        except Exception:
            pass
    return promos


@admin_ops_router.post("/admin/promotions/{promo_id}/cancel")
async def admin_cancel_promotion(
    promo_id: str,
    current_user: User = Depends(require_admin),
):
    db = get_db()
    p = await db.promotions.find_one({"id": promo_id}, {"_id": 0})
    if not p:
        raise HTTPException(status_code=404, detail="Promotion not found")
    now_iso = datetime.now(timezone.utc).isoformat()
    listing_type = p.get("listing_type", "marketplace")
    coll = db.storage_auctions if listing_type == "storage" else db.listings
    await coll.update_one(
        {"id": p["listing_id"]},
        {"$set": {
            "is_promoted": False, "is_featured": False,
            "promotion_tier": None, "promotion_tier_weight": 0,
            "promotion_expired_at": now_iso,
        }},
    )
    await db.promotions.update_one(
        {"id": promo_id},
        {"$set": {"status": "cancelled", "cancelled_at": now_iso, "cancelled_by": current_user.id}},
    )
    return {"ok": True}


@admin_ops_router.get("/admin/promotions/social-share-queue")
async def admin_social_share_queue(current_user: User = Depends(require_admin)):
    db = get_db()
    items = await db.social_share_queue.find({"status": "pending"}, {"_id": 0}).sort("requested_at", 1).limit(200).to_list(200)
    for it in items:
        try:
            coll = db.storage_auctions if it.get("listing_type") == "storage" else db.listings
            lst = await coll.find_one({"id": it.get("listing_id")}, {"_id": 0, "title": 1})
            if lst:
                it["listing_title"] = lst.get("title", "")
            u = await db.users.find_one({"id": it.get("seller_id")}, {"_id": 0, "name": 1})
            if u:
                it["seller_name"] = u.get("name", "")
        except Exception:
            pass
    return items


@admin_ops_router.post("/admin/promotions/social-share-queue/{item_id}/mark-shared")
async def admin_mark_social_shared(
    item_id: str,
    current_user: User = Depends(require_admin),
):
    db = get_db()
    r = await db.social_share_queue.update_one(
        {"id": item_id},
        {"$set": {
            "status": "shared",
            "shared_at": datetime.now(timezone.utc).isoformat(),
            "shared_by": current_user.id,
        }},
    )
    if r.matched_count == 0:
        raise HTTPException(status_code=404, detail="Queue item not found")
    return {"ok": True}


@admin_ops_router.get("/admin/promotions/revenue")
async def admin_promotion_revenue(current_user: User = Depends(require_admin)):
    db = get_db()
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    cursor = db.promotions.find(
        {"status": {"$in": ["active", "expired", "cancelled"]}},
        {"_id": 0, "grand_total": 1, "created_at": 1, "tier": 1, "listing_type": 1},
    )
    rows = await cursor.to_list(10000)
    total_all = 0.0
    total_mtd = 0.0
    by_tier = {"basic": 0.0, "standard": 0.0, "premium": 0.0}
    by_type = {"marketplace": 0.0, "lots": 0.0, "storage": 0.0, "partner": 0.0}
    for r in rows:
        amt = float(r.get("grand_total", 0) or 0)
        total_all += amt
        if r.get("created_at", "") >= month_start:
            total_mtd += amt
        by_tier[r.get("tier", "basic")] = by_tier.get(r.get("tier", "basic"), 0) + amt
        by_type[r.get("listing_type", "marketplace")] = by_type.get(r.get("listing_type", "marketplace"), 0) + amt
    return {
        "total_all_time": round(total_all, 2),
        "total_month_to_date": round(total_mtd, 2),
        "by_tier": {k: round(v, 2) for k, v in by_tier.items()},
        "by_type": {k: round(v, 2) for k, v in by_type.items()},
        "count": len(rows),
    }





@admin_ops_router.get("/admin/listings/all")
async def get_all_listings_admin(current_user: User = Depends(require_admin)):
    """
    Admin: Get all single listings across every directory collection.

    iter290 — Previously this only queried `db.listings`, hiding every
    vehicle + storage auction from the "Manage All Auctions" panel.
    Now we aggregate:

      • db.listings           → `_section='marketplace'`
      • db.vehicle_listings   → `_section='vehicle'`
      • db.storage_auctions   → `_section='storage'`

    Each row is tagged with `_section` + `_collection` so the frontend
    can render the right badge and route the View / Edit / End /
    Feature / Pause / Archive / Delete CTAs at the proper detail
    page + collection.
    """
    db = get_db()
    merged: list = []

    # ── 1) Marketplace listings ─────────────────────────────────
    marketplace = await db.listings.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
    for d in marketplace:
        d["_section"]    = "marketplace"
        d["_collection"] = "listings"
        merged.append(d)

    # ── 2) Vehicle auctions ────────────────────────────────────
    try:
        vehicles = await db.vehicle_listings.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
    except Exception:
        vehicles = []
    for d in vehicles:
        d["_section"]    = "vehicle"
        d["_collection"] = "vehicle_listings"
        # Synthesize a display `title` when the wizard didn't set one.
        if not d.get("title"):
            parts = [str(d.get("year") or ""), d.get("make") or "", d.get("model") or ""]
            d["title"] = " ".join(p for p in parts if p).strip() or "Vehicle Listing"
        # The card reads `auction_end_date` / `current_price`. Surface
        # the vehicle-collection field names under those keys so the
        # UI row renders cleanly without touching the frontend code.
        d.setdefault("auction_end_date", d.get("end_time"))
        d.setdefault("current_price",    d.get("current_bid"))
        d.setdefault("category",         "Vehicle")
        d.setdefault("city",             d.get("location_city") or "")
        d.setdefault("region",           d.get("location_province") or "")
        merged.append(d)

    # ── 3) Storage auctions ────────────────────────────────────
    try:
        storage = await db.storage_auctions.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
    except Exception:
        storage = []
    for d in storage:
        d["_section"]    = "storage"
        d["_collection"] = "storage_auctions"
        if not d.get("title"):
            d["title"] = (
                f"Storage Unit #{d.get('unit_number') or '—'} · "
                f"{d.get('facility_name') or d.get('facility_city') or 'Facility'}"
            )
        d.setdefault("auction_end_date", d.get("end_time"))
        d.setdefault("current_price",    d.get("current_bid"))
        d.setdefault("category",         "Storage")
        d.setdefault("city",             d.get("facility_city") or "")
        d.setdefault("region",           d.get("facility_province") or "")
        merged.append(d)

    # Sort newest-first across collections.
    merged.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return merged



@admin_ops_router.get("/admin/multi-item-listings/all")
async def get_all_multi_listings_admin(current_user: User = Depends(require_admin)):
    """Admin: Get all multi-item listings AND multi-lot vehicle auctions.

    iter290 — Tag every row with `_section='lots'` + `_collection` so the
    Manage All Auctions UI can render the orange 'Lots' badge and route
    the View / Edit / Delete CTAs at the multi_item_listings table.

    iter293 — Surface vehicle_multi_lot_auctions here too so admins see
    every multi-row event from one panel. Each row is tagged with
    `_section='vehicle_multi_lot'` so the frontend can render a
    "Vehicle Multi-Lot" badge and route the View CTA at
    `/vehicle-multi-lot/:id`.
    """
    db = get_db()
    merged: list = []

    listings = await db.multi_item_listings.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
    for d in listings:
        d["_section"]    = "lots"
        d["_collection"] = "multi_item_listings"
        merged.append(d)

    try:
        ml_events = await db.vehicle_multi_lot_auctions.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
    except Exception:
        ml_events = []
    for d in ml_events:
        d["_section"]    = "vehicle_multi_lot"
        d["_collection"] = "vehicle_multi_lot_auctions"
        # The Manage All Auctions card reads `auction_end_date` /
        # `current_price`. Surface the event-level end_time + first
        # active lot's current_bid so the row renders cleanly.
        lots = d.get("lots") or []
        active = lots[d.get("current_active_lot_index", 0)] if lots and 0 <= d.get("current_active_lot_index", -1) < len(lots) else (lots[0] if lots else {})
        d.setdefault("auction_end_date", active.get("end_time") or d.get("start_time"))
        d.setdefault("current_price",    active.get("current_bid") or 0)
        d.setdefault("category",         f"Multi-Lot · {len(lots)} vehicle(s)")
        d.setdefault("city",             active.get("location_city") or "")
        d.setdefault("region",           active.get("location_province") or "")
        d.setdefault("bid_count",        sum((l.get("bid_count") or 0) for l in lots))
        merged.append(d)

    merged.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return merged




@admin_ops_router.get("/admin/deletion-requests")
async def get_deletion_requests(current_user: User = Depends(require_admin)):
    """Admin: Get all pending deletion requests"""
    db = get_db()
    requests = await db.deletion_requests.find(
        {"status": "pending"},
        {"_id": 0}
    ).sort("requested_at", -1).to_list(None)
    
    return requests



@admin_ops_router.post("/admin/deletion-requests/{request_id}/approve")
async def approve_deletion_request(
    request_id: str,
    current_user: User = Depends(require_admin)
):
    """Admin: Approve and execute deletion request"""
    db = get_db()
    request_doc = await db.deletion_requests.find_one({"id": request_id})
    if not request_doc:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Delete the actual listing
    if request_doc["listing_type"] == "single":
        await db.listings.delete_one({"id": request_doc["listing_id"]})
    else:
        await db.multi_item_listings.delete_one({"id": request_doc["listing_id"]})
    
    # Mark request as approved
    await db.deletion_requests.update_one(
        {"id": request_id},
        {"$set": {
            "status": "approved",
            "reviewed_at": datetime.now(timezone.utc),
            "reviewed_by": current_user.id,
            "reviewed_by_email": current_user.email
        }}
    )
    
    return {"success": True, "message": "Listing deleted successfully"}



@admin_ops_router.post("/admin/deletion-requests/{request_id}/reject")
async def reject_deletion_request(
    request_id: str,
    current_user: User = Depends(require_admin)
):
    """Admin: Reject deletion request and notify the user."""
    db = get_db()
    request_doc = await db.deletion_requests.find_one({"id": request_id})
    if not request_doc:
        raise HTTPException(status_code=404, detail="Request not found")
    
    # Remove pending flag from listing
    if request_doc["listing_type"] == "single":
        await db.listings.update_one(
            {"id": request_doc["listing_id"]},
            {"$set": {"deletion_request_pending": False}}
        )
    else:
        await db.multi_item_listings.update_one(
            {"id": request_doc["listing_id"]},
            {"$set": {"deletion_request_pending": False}}
        )
    
    # Mark request as rejected
    await db.deletion_requests.update_one(
        {"id": request_id},
        {"$set": {
            "status": "rejected",
            "reviewed_at": datetime.now(timezone.utc),
            "reviewed_by": current_user.id,
            "reviewed_by_email": current_user.email
        }}
    )

    # Notify the user via in-app notification
    user_id = request_doc.get("user_id") or request_doc.get("seller_id")
    if user_id:
        await db.notifications.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "type": "deletion_rejected",
            "title": "Deletion Request Rejected",
            "message": "Your request to delete listing has been reviewed and rejected by an administrator.",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    
    return {"success": True, "message": "Deletion request rejected"}






@admin_ops_router.put("/admin/listings/{listing_id}/moderate")
async def admin_moderate_listing_legacy(listing_id: str, data: Dict[str, str], current_user: User = Depends(require_admin)):
    """DEPRECATED: kept for backwards compatibility. Prefer /approve and /reject endpoints."""
    db = get_db()
    action = data.get("action")
    if action == "approve":
        await db.listings.update_one({"id": listing_id}, {"$set": {"status": "active"}})
    elif action == "reject":
        await db.listings.update_one({"id": listing_id}, {"$set": {"status": "rejected"}})
    elif action == "remove":
        await db.listings.delete_one({"id": listing_id})
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    return {"message": f"Listing {action}d successfully"}



@admin_ops_router.get("/admin/transactions")
async def admin_get_transactions(current_user: User = Depends(require_admin), limit: int = 50):
    db = get_db()
    transactions = await db.payment_transactions.find({}, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return transactions



@admin_ops_router.get("/admin/analytics")
async def admin_get_analytics(current_user: User = Depends(require_admin)):
    db = get_db()
    active_listings = await db.listings.count_documents({"status": "active"})
    total_users = await db.users.count_documents({})
    
    # Calculate total revenue from paid transactions
    paid_transactions = await db.payment_transactions.find({"payment_status": "paid"}, {"_id": 0, "amount": 1}).to_list(1000)
    total_revenue = sum([tx.get("amount", 0) for tx in paid_transactions])
    
    return {
        "active_listings": active_listings,
        "total_users": total_users,
        "total_revenue": total_revenue
    }



@admin_ops_router.get("/admin/promotions")
async def admin_get_promotions(current_user: User = Depends(require_admin)):
    db = get_db()
    promotions = await db.promotions.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return promotions



@admin_ops_router.post("/admin/promotions/create")
async def admin_create_promotion(data: Dict[str, Any], current_user: User = Depends(require_admin)):
    db = get_db()
    promotion = {
        "id": str(uuid.uuid4()),
        "listing_id": data.get("listing_id"),
        "promotion_type": data.get("promotion_type"),
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "end_date": data.get("end_date")
    }
    await db.promotions.insert_one(promotion)
    await db.listings.update_one({"id": data.get("listing_id")}, {"$set": {"is_promoted": True}})
    return promotion



@admin_ops_router.delete("/admin/promotions/{promotion_id}")
async def admin_delete_promotion(promotion_id: str, current_user: User = Depends(require_admin)):
    db = get_db()
    promotion = await db.promotions.find_one({"id": promotion_id})
    if promotion:
        await db.listings.update_one({"id": promotion.get("listing_id")}, {"$set": {"is_promoted": False}})
        await db.promotions.delete_one({"id": promotion_id})
    return {"message": "Promotion deleted"}



@admin_ops_router.put("/admin/listings/{listing_id}/feature")
async def admin_feature_listing(listing_id: str, data: Dict[str, bool], current_user: User = Depends(require_admin)):
    """iter290 — Cross-collection feature toggle. The Manage All
    Auctions table can promote vehicles + storage rows; route the
    update to whichever collection owns the listing id."""
    db = get_db()
    is_featured = data.get("is_featured", False)
    for coll_name in ("listings", "vehicle_listings", "storage_auctions", "multi_item_listings", "vehicle_multi_lot_auctions"):
        try:
            r = await db[coll_name].update_one({"id": listing_id}, {"$set": {"is_featured": is_featured}})
        except Exception:
            r = None
        if r and r.matched_count:
            return {"message": f"Listing {'featured' if is_featured else 'unfeatured'}", "collection": coll_name}
    raise HTTPException(status_code=404, detail="Listing not found")

# CATEGORY MANAGEMENT


@admin_ops_router.post("/admin/categories")
async def admin_create_category(data: Dict[str, Any], current_user: User = Depends(require_admin)):
    db = get_db()
    category = {
        "id": str(uuid.uuid4()),
        "name_en": data.get("name_en"),
        "name_fr": data.get("name_fr"),
        "icon": data.get("icon", ""),
        "order": data.get("order", 0),
        "parent_id": data.get("parent_id"),  # null = top-level, id = subcategory
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.categories.insert_one(category)
    category.pop("_id", None)
    return category



@admin_ops_router.put("/admin/categories/{category_id}")
async def admin_update_category(category_id: str, data: Dict[str, Any], current_user: User = Depends(require_admin)):
    db = get_db()
    await db.categories.update_one({"id": category_id}, {"$set": data})
    return {"message": "Category updated"}



@admin_ops_router.delete("/admin/categories/{category_id}")
async def admin_delete_category(category_id: str, current_user: User = Depends(require_admin)):
    db = get_db()
    await db.categories.delete_one({"id": category_id})
    return {"message": "Category deleted"}

# AUCTION LIFECYCLE CONTROL


@admin_ops_router.get("/admin/auctions")
async def admin_get_auctions(status: str = None, current_user: User = Depends(require_admin)):
    db = get_db()
    query = {}
    if status:
        query["status"] = status
    
    listings = await db.listings.find(query, {"_id": 0}).sort("created_at", -1).limit(100).to_list(100)
    return listings



@admin_ops_router.put("/admin/auctions/{listing_id}/pause")
async def admin_pause_auction(listing_id: str, current_user: User = Depends(require_admin)):
    db = get_db()
    await db.listings.update_one({"id": listing_id}, {"$set": {"status": "paused"}})
    return {"message": "Auction paused"}



@admin_ops_router.put("/admin/auctions/{listing_id}/resume")
async def admin_resume_auction(listing_id: str, current_user: User = Depends(require_admin)):
    db = get_db()
    await db.listings.update_one({"id": listing_id}, {"$set": {"status": "active"}})
    return {"message": "Auction resumed"}



@admin_ops_router.put("/admin/auctions/{listing_id}/extend")
async def admin_extend_auction(listing_id: str, data: Dict[str, Any], current_user: User = Depends(require_admin)):
    db = get_db()
    new_end_date = data.get("new_end_date")
    await db.listings.update_one({"id": listing_id}, {"$set": {"auction_end_date": new_end_date}})
    return {"message": "Auction extended"}



@admin_ops_router.delete("/admin/auctions/{listing_id}/cancel")
async def admin_cancel_auction(listing_id: str, current_user: User = Depends(require_admin)):
    db = get_db()
    await db.listings.update_one({"id": listing_id}, {"$set": {"status": "cancelled"}})
    return {"message": "Auction cancelled"}

# AFFILIATE PROGRAM MANAGEMENT


@admin_ops_router.get("/admin/affiliates")
async def admin_get_affiliates(current_user: User = Depends(require_admin)):
    db = get_db()
    affiliates = await db.affiliates.find({}, {"_id": 0}).to_list(100)
    return affiliates



@admin_ops_router.put("/admin/users/{user_id}/affiliate")
async def admin_set_affiliate_status_legacy(user_id: str, data: Dict[str, bool], current_user: User = Depends(require_admin)):
    """iter501 — DEPRECATED shim.

    The old flow inserted a decorative row into ``db.affiliates`` and had
    NO effect on commission awarding.  It is now a thin adapter over the
    canonical ``POST /api/affiliate/admin/set-status`` endpoint, which
    persists ``affiliate_status`` directly on the user document (the
    single source of truth).  The legacy ``db.affiliates`` collection is
    no longer written to.
    """
    from routes.affiliate import admin_set_affiliate_status
    is_affiliate = bool(data.get("is_affiliate", False))
    payload = {
        "user_id": user_id,
        "status": "active" if is_affiliate else "revoked",
    }
    return await admin_set_affiliate_status(payload, current_user)



@admin_ops_router.get("/admin/users/filter")
async def admin_filter_users(account_type: str = None, current_user: User = Depends(require_admin)):
    """iter215 — Filterable by the 6 buckets the admin Users tab uses:

        all              → every user
        personal | individual → account_type=personal (without partner/dealer/facility flags)
        business              → account_type=business
        partner               → is_licensed_partner=True
        vehicle_dealer        → is_vehicle_dealer=True
        storage_facility      → is_storage_facility=True
        demo                  → is_demo_account=True
    """
    db = get_db()
    query = {}
    if account_type and account_type not in ("", "all"):
        bucket = account_type.lower()
        if bucket in ("individual",):
            query = {
                "account_type": "personal",
                "is_licensed_partner": {"$ne": True},
                "is_vehicle_dealer": {"$ne": True},
                "is_storage_facility": {"$ne": True},
                "is_demo_account": {"$ne": True},
            }
        elif bucket == "partner":
            query["is_licensed_partner"] = True
        elif bucket == "vehicle_dealer":
            query["is_vehicle_dealer"] = True
        elif bucket == "storage_facility":
            query["is_storage_facility"] = True
        elif bucket == "demo":
            query["is_demo_account"] = True
        else:
            # Legacy: passthrough on `account_type` (personal | business)
            query["account_type"] = account_type

    users = await db.users.find(query, {"_id": 0, "password": 0}).to_list(200)
    return users



@admin_ops_router.put("/admin/users/{user_id}/verify")
async def admin_verify_user(user_id: str, data: Dict[str, bool], current_user: User = Depends(require_admin)):
    db = get_db()
    is_verified = data.get("is_verified", False)
    await db.users.update_one({"id": user_id}, {"$set": {"verified": is_verified, "verified_at": datetime.now(timezone.utc).isoformat()}})
    return {"message": f"User {'verified' if is_verified else 'unverified'}"}



@admin_ops_router.get("/admin/analytics/users")
async def admin_user_analytics(current_user: User = Depends(require_admin)):
    db = get_db()
    personal_users = await db.users.count_documents({"account_type": "personal"})
    business_users = await db.users.count_documents({"account_type": "business"})
    
    return {
        "personal": personal_users,
        "business": business_users,
        "total": personal_users + business_users
    }

# LOTS AUCTION MODERATION


@admin_ops_router.get("/admin/lots/pending")
async def admin_get_pending_lots(current_user: User = Depends(require_admin)):
    db = get_db()
    lots = await db.multi_item_listings.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return lots



@admin_ops_router.put("/admin/lots/{lot_id}/moderate")
async def admin_moderate_lot(lot_id: str, data: Dict[str, str], current_user: User = Depends(require_admin)):
    db = get_db()
    action = data.get("action")
    if action == "approve":
        await db.multi_item_listings.update_one({"id": lot_id}, {"$set": {"status": "active"}})
    elif action == "reject":
        await db.multi_item_listings.update_one({"id": lot_id}, {"$set": {"status": "rejected"}})
    else:
        raise HTTPException(status_code=400, detail="Invalid action")
    
    return {"message": f"Lot {action}d successfully"}


# ============================================================================
# SINGLE-ITEM LISTINGS MODERATION (require_approval_new_sellers gate)
# ----------------------------------------------------------------------------
# - GET  /api/admin/listings/pending          → all pending listings (single + multi)
# - POST /api/admin/listings/{id}/approve      → status → active, notify seller
# - POST /api/admin/listings/{id}/reject       → status → rejected + reason, notify seller
# Listing type ('single' or 'multi') is auto-detected from which collection
# holds the listing — no extra type query param needed.
# ============================================================================


async def _find_pending_listing(db, listing_id: str):
    """Find a pending listing in either listings or multi_item_listings collection."""
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if listing:
        return listing, "single"
    listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    if listing:
        return listing, "multi"
    return None, None


@admin_ops_router.get("/admin/listings/pending")
async def admin_get_pending_listings(current_user: User = Depends(require_admin)):
    """Return all pending single-item + multi-item listings, newest first.

    iter217 Phase 3 — expanded to include `manual_review` and `pending_review`
    statuses (AI-moderator outputs). Frontend can filter the combined list."""
    db = get_db()
    PENDING_STATUSES = ["pending", "manual_review", "pending_review"]
    pending_single = await db.listings.find(
        {"status": {"$in": PENDING_STATUSES}}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    pending_multi = await db.multi_item_listings.find(
        {"status": {"$in": PENDING_STATUSES}}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    # Tag each with its listing_type for the UI router/buttons
    for item in pending_single:
        item["_listing_type"] = "single"
    for item in pending_multi:
        item["_listing_type"] = "multi"

    # Enrich with seller email + name for the moderation UI
    seller_ids = list({lst.get("seller_id") for lst in (pending_single + pending_multi) if lst.get("seller_id")})
    sellers = {}
    if seller_ids:
        async for u in db.users.find(
            {"id": {"$in": seller_ids}}, {"_id": 0, "id": 1, "email": 1, "name": 1, "company_name": 1}
        ):
            sellers[u["id"]] = u
    for item in (pending_single + pending_multi):
        s = sellers.get(item.get("seller_id"), {})
        item["_seller_email"] = s.get("email", "")
        item["_seller_name"] = s.get("name") or s.get("company_name") or ""

    combined = sorted(
        pending_single + pending_multi,
        key=lambda lst: lst.get("created_at", ""),
        reverse=True,
    )
    return {
        "total": len(combined),
        "single_count": len(pending_single),
        "multi_count": len(pending_multi),
        "listings": combined,
    }


class _ModerateAction(BaseModel):
    reason: Optional[str] = None  # required for reject, ignored on approve


@admin_ops_router.post("/admin/listings/{listing_id}/approve")
async def admin_approve_listing(
    listing_id: str,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
):
    """Approve a pending listing — set status to active and email the seller."""
    db = get_db()
    listing, kind = await _find_pending_listing(db, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    # iter217 Phase 3 — accept the full pending-status set (pending / manual_review / pending_review)
    if listing.get("status") not in ("pending", "manual_review", "pending_review"):
        raise HTTPException(status_code=400, detail=f"Listing is not pending (current status: {listing.get('status')})")

    coll = db.listings if kind == "single" else db.multi_item_listings
    now_iso = datetime.now(timezone.utc).isoformat()
    await coll.update_one(
        {"id": listing_id},
        {"$set": {
            "status": "active",
            "moderated_at": now_iso,
            "moderated_by": current_user.id,
            "moderation_decision": "approved",
        }, "$unset": {"rejection_reason": ""}},
    )

    # Audit log
    await db.admin_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "listing_approved",
        "target_type": kind,
        "target_id": listing_id,
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "timestamp": now_iso,
    })

    # Invalidate marketplace cache so the listing appears immediately
    try:
        from services.api_cache import invalidate_listing_caches
        invalidate_listing_caches()
    except Exception:
        pass

    # Email seller (non-blocking) — uses existing template send_listing_approved_email
    seller = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0})
    if seller:
        try:
            from services.email_service import send_listing_approved_email
            background_tasks.add_task(
                send_listing_approved_email,
                seller,
                listing_id,
                listing.get("title", ""),
            )
        except Exception as e:
            logger.error(f"[MODERATION] Approve email schedule failed: {e}")

    logger.info(f"[MODERATION] Listing {listing_id} ({kind}) APPROVED by {current_user.email}")
    return {"success": True, "message": "Listing approved", "listing_id": listing_id, "type": kind}


@admin_ops_router.post("/admin/listings/{listing_id}/reject")
async def admin_reject_listing(
    listing_id: str,
    payload: _ModerateAction,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(require_admin),
):
    """Reject a pending listing — set status to rejected and email the seller with the reason."""
    reason = (payload.reason or "").strip()
    if not reason:
        raise HTTPException(status_code=400, detail="A rejection reason is required so the seller knows what to fix.")
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="Rejection reason must be at least 5 characters.")

    db = get_db()
    listing, kind = await _find_pending_listing(db, listing_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    # iter217 Phase 3 — accept the full pending-status set (pending / manual_review / pending_review)
    if listing.get("status") not in ("pending", "manual_review", "pending_review"):
        raise HTTPException(status_code=400, detail=f"Listing is not pending (current status: {listing.get('status')})")

    coll = db.listings if kind == "single" else db.multi_item_listings
    now_iso = datetime.now(timezone.utc).isoformat()
    await coll.update_one(
        {"id": listing_id},
        {"$set": {
            "status": "rejected",
            "rejection_reason": reason,
            "moderated_at": now_iso,
            "moderated_by": current_user.id,
            "moderation_decision": "rejected",
        }},
    )

    await db.admin_audit_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "listing_rejected",
        "target_type": kind,
        "target_id": listing_id,
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "reason": reason,
        "timestamp": now_iso,
    })

    # Email seller with the reason (non-blocking)
    seller = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0})
    if seller:
        try:
            from services.email_service import send_listing_rejected_email
            background_tasks.add_task(
                send_listing_rejected_email,
                seller,
                listing_id,
                listing.get("title", ""),
                reason,
            )
        except Exception as e:
            logger.error(f"[MODERATION] Reject email schedule failed: {e}")

    logger.info(f"[MODERATION] Listing {listing_id} ({kind}) REJECTED by {current_user.email}: {reason}")
    return {"success": True, "message": "Listing rejected", "listing_id": listing_id, "type": kind, "reason": reason}

# REPORT ENHANCEMENTS


@admin_ops_router.put("/admin/reports/{report_id}/update")
async def admin_update_report(report_id: str, data: Dict[str, Any], current_user: User = Depends(require_admin)):
    db = get_db()
    update_data = {}
    if "status" in data:
        update_data["status"] = data["status"]
    if "admin_notes" in data:
        update_data["admin_notes"] = data["admin_notes"]
    if "assigned_to" in data:
        update_data["assigned_to"] = data["assigned_to"]
    if "resolution" in data:
        update_data["resolution"] = data["resolution"]
    
    await db.reports.update_one({"id": report_id}, {"$set": update_data})
    return {"message": "Report updated"}



@admin_ops_router.get("/admin/reports/filter")
async def admin_filter_reports(category: str = None, severity: str = None, status: str = None, current_user: User = Depends(require_admin)):
    db = get_db()
    query = {}
    if category:
        query["category"] = category
    if severity:
        query["severity"] = severity
    if status:
        query["status"] = status
    
    reports = await db.reports.find(query, {"_id": 0}).sort("created_at", -1).to_list(100)
    return reports

# ADVANCED ANALYTICS


@admin_ops_router.get("/admin/analytics/revenue")
async def admin_revenue_analytics(
    current_user: User = Depends(require_admin),
    days: int = Query(30, ge=1, le=730),
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
):
    """
    Daily-grouped revenue from paid `payment_transactions`.

    Date filter (highest-priority first):
      • If both `start_date` and `end_date` (ISO date YYYY-MM-DD) are passed,
        they are used directly (inclusive on both ends, UTC).
      • Otherwise falls back to last `days` (default 30, max 730).
    """
    db = get_db()
    now = datetime.now(timezone.utc)

    if start_date and end_date:
        try:
            start_dt = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
            end_dt = datetime.fromisoformat(end_date).replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
        except ValueError:
            raise HTTPException(status_code=400, detail="invalid start_date or end_date (expected YYYY-MM-DD)")
        if end_dt < start_dt:
            raise HTTPException(status_code=400, detail="end_date must be >= start_date")
    else:
        start_dt = now - timedelta(days=days)
        end_dt = now

    transactions = await db.payment_transactions.find(
        {
            "payment_status": "paid",
            "created_at": {
                "$gte": start_dt.isoformat(),
                "$lte": end_dt.isoformat(),
            },
        },
        {"_id": 0, "amount": 1, "created_at": 1},
    ).to_list(5000)

    daily_revenue: Dict[str, float] = {}
    for tx in transactions:
        date = (tx.get("created_at") or "")[:10]
        if date:
            daily_revenue[date] = daily_revenue.get(date, 0) + float(tx.get("amount") or 0)

    return [{"date": d, "revenue": rev} for d, rev in sorted(daily_revenue.items())]



@admin_ops_router.get("/admin/analytics/listings")
async def admin_listing_analytics(current_user: User = Depends(require_admin)):
    db = get_db()
    active = await db.listings.count_documents({"status": "active"})
    sold = await db.listings.count_documents({"status": "sold"})
    pending = await db.listings.count_documents({"status": "pending"})
    cancelled = await db.listings.count_documents({"status": "cancelled"})
    
    return {
        "active": active,
        "sold": sold,
        "pending": pending,
        "cancelled": cancelled
    }


# ============================================================================
# ADVANCED ANALYTICS — Top sellers, top categories, conversion rate
# ----------------------------------------------------------------------------
# GET /api/admin/analytics/advanced?days=30
#
# Sales attribution = paid payment_transactions + paid buy_now_transactions
# (option 1.a: actual money movement only, not pending settlement).
#
# Visitor→bidder uses cumulative `listings.views` counter (option 2.a).
#
# Cached for 60 s in-process to keep page load fast.
# ============================================================================

_ADVANCED_ANALYTICS_CACHE: Dict[str, Dict[str, Any]] = {}
_ADVANCED_ANALYTICS_TTL_SEC = 60


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    entry = _ADVANCED_ANALYTICS_CACHE.get(key)
    if not entry:
        return None
    if (datetime.now(timezone.utc) - entry["ts"]).total_seconds() > _ADVANCED_ANALYTICS_TTL_SEC:
        _ADVANCED_ANALYTICS_CACHE.pop(key, None)
        return None
    return entry["payload"]


def _cache_set(key: str, payload: Dict[str, Any]) -> None:
    _ADVANCED_ANALYTICS_CACHE[key] = {"ts": datetime.now(timezone.utc), "payload": payload}


async def _build_listing_seller_map(db) -> Dict[str, str]:
    """
    Map listing_id → seller_id across `listings`, `multi_item_listings`,
    and `vehicle_listings`. Built once per request — small dataset.
    """
    out: Dict[str, str] = {}
    async for d in db.listings.find({}, {"_id": 0, "id": 1, "seller_id": 1, "category": 1}):
        if d.get("id") and d.get("seller_id"):
            out[d["id"]] = d["seller_id"]
    async for d in db.multi_item_listings.find({}, {"_id": 0, "id": 1, "seller_id": 1}):
        if d.get("id") and d.get("seller_id"):
            out[d["id"]] = d["seller_id"]
    async for d in db.vehicle_listings.find({}, {"_id": 0, "id": 1, "seller_id": 1}):
        if d.get("id") and d.get("seller_id"):
            out[d["id"]] = d["seller_id"]
    return out


async def _aggregate_top_sellers(db, cutoff_iso: str, listing_seller_map: Dict[str, str]) -> List[Dict[str, Any]]:
    """Top 10 sellers by total revenue from PAID transactions in the window."""
    revenue_by_seller: Dict[str, Dict[str, Any]] = {}

    # 1. Standard auction settlements
    cursor = db.payment_transactions.find(
        {"payment_status": "paid", "created_at": {"$gte": cutoff_iso}},
        {"_id": 0, "listing_id": 1, "amount": 1, "currency": 1},
    )
    async for tx in cursor:
        seller_id = listing_seller_map.get(tx.get("listing_id"))
        if not seller_id:
            continue
        bucket = revenue_by_seller.setdefault(seller_id, {"revenue": 0.0, "items_sold": 0})
        bucket["revenue"] += float(tx.get("amount") or 0)
        bucket["items_sold"] += 1

    # 2. Buy Now transactions
    cursor = db.buy_now_transactions.find(
        {"payment_status": "paid", "transaction_date": {"$gte": cutoff_iso}},
        {"_id": 0, "auction_id": 1, "total_amount": 1, "quantity_purchased": 1},
    )
    async for tx in cursor:
        seller_id = listing_seller_map.get(tx.get("auction_id"))
        if not seller_id:
            continue
        bucket = revenue_by_seller.setdefault(seller_id, {"revenue": 0.0, "items_sold": 0})
        bucket["revenue"] += float(tx.get("total_amount") or 0)
        bucket["items_sold"] += int(tx.get("quantity_purchased") or 1)

    if not revenue_by_seller:
        return []

    seller_ids = list(revenue_by_seller.keys())
    sellers_meta: Dict[str, Dict[str, Any]] = {}
    async for u in db.users.find(
        {"id": {"$in": seller_ids}},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "company_name": 1},
    ):
        sellers_meta[u["id"]] = u

    rows: List[Dict[str, Any]] = []
    for sid, stats in revenue_by_seller.items():
        meta = sellers_meta.get(sid, {})
        items_sold = stats["items_sold"]
        revenue = round(stats["revenue"], 2)
        rows.append({
            "seller_id": sid,
            "name": meta.get("name") or meta.get("company_name") or "(unknown)",
            "email": meta.get("email") or "",
            "items_sold": items_sold,
            "total_revenue": revenue,
            "avg_sale_price": round(revenue / items_sold, 2) if items_sold else 0.0,
        })
    rows.sort(key=lambda r: r["total_revenue"], reverse=True)
    return rows[:10]


async def _aggregate_top_categories(db, cutoff_iso: str) -> List[Dict[str, Any]]:
    """
    Top 10 categories by total listings in the window, with sold-count and revenue.
    Sold attribution = listings.status='sold' OR vehicle_listings.status='sold'.
    """
    categories: Dict[str, Dict[str, Any]] = {}

    async for lst in db.listings.find(
        {"created_at": {"$gte": cutoff_iso}},
        {"_id": 0, "id": 1, "category": 1, "status": 1, "current_price": 1, "starting_price": 1, "views": 1},
    ):
        cat = (lst.get("category") or "(uncategorized)").lower()
        bucket = categories.setdefault(cat, {"total_listings": 0, "sold_count": 0, "total_revenue": 0.0, "total_views": 0})
        bucket["total_listings"] += 1
        bucket["total_views"] += int(lst.get("views") or 0)
        if lst.get("status") == "sold":
            bucket["sold_count"] += 1
            bucket["total_revenue"] += float(lst.get("current_price") or lst.get("starting_price") or 0)

    async for v in db.vehicle_listings.find(
        {"created_at": {"$gte": cutoff_iso}},
        {"_id": 0, "category": 1, "status": 1, "starting_price": 1, "final_price": 1},
    ):
        cat = (v.get("category") or "vehicles").lower()
        bucket = categories.setdefault(cat, {"total_listings": 0, "sold_count": 0, "total_revenue": 0.0, "total_views": 0})
        bucket["total_listings"] += 1
        if v.get("status") == "sold":
            bucket["sold_count"] += 1
            bucket["total_revenue"] += float(v.get("final_price") or v.get("starting_price") or 0)

    rows: List[Dict[str, Any]] = []
    for cat, stats in categories.items():
        total = stats["total_listings"]
        sold = stats["sold_count"]
        rows.append({
            "category": cat,
            "total_listings": total,
            "sold_count": sold,
            "total_revenue": round(stats["total_revenue"], 2),
            "sell_through_rate": round(sold / total, 4) if total else 0.0,
            "total_views": stats["total_views"],
        })
    rows.sort(key=lambda r: r["total_listings"], reverse=True)
    return rows[:10]


async def _compute_conversion_rates(db, cutoff_iso: str) -> Dict[str, Any]:
    """Three conversion metrics for the analytics period."""
    # 1. Listing → Sale  (listings created in window that ended in 'sold')
    total_listings = await db.listings.count_documents({"created_at": {"$gte": cutoff_iso}})
    sold_listings = await db.listings.count_documents({"created_at": {"$gte": cutoff_iso}, "status": "sold"})
    listing_to_sale = {
        "total_listings": total_listings,
        "sold_listings": sold_listings,
        "rate": round(sold_listings / total_listings, 4) if total_listings else 0.0,
    }

    # 2. Visitor → Bidder  (cumulative listings.views vs total bids in window)
    total_views_pipeline = [
        {"$match": {"created_at": {"$gte": cutoff_iso}}},
        {"$group": {"_id": None, "total_views": {"$sum": {"$ifNull": ["$views", 0]}}}},
    ]
    total_views_doc = await db.listings.aggregate(total_views_pipeline).to_list(1)
    total_views = total_views_doc[0]["total_views"] if total_views_doc else 0
    total_bids = await db.bids.count_documents({"created_at": {"$gte": cutoff_iso}})
    visitor_to_bidder = {
        "total_views": total_views,
        "total_bids": total_bids,
        "rate": round(total_bids / total_views, 4) if total_views else 0.0,
    }

    # 3. Signup → Action  (new users in window who placed a bid OR created a listing)
    new_user_ids: List[str] = []
    async for u in db.users.find({"created_at": {"$gte": cutoff_iso}}, {"_id": 0, "id": 1}):
        if u.get("id"):
            new_user_ids.append(u["id"])
    new_users = len(new_user_ids)

    users_with_action = 0
    if new_user_ids:
        bidders = await db.bids.distinct("bidder_id", {"bidder_id": {"$in": new_user_ids}})
        listers = await db.listings.distinct("seller_id", {"seller_id": {"$in": new_user_ids}})
        users_with_action = len(set(bidders) | set(listers))

    signup_to_action = {
        "new_users": new_users,
        "users_with_action": users_with_action,
        "rate": round(users_with_action / new_users, 4) if new_users else 0.0,
    }

    return {
        "listing_to_sale": listing_to_sale,
        "visitor_to_bidder": visitor_to_bidder,
        "signup_to_action": signup_to_action,
    }


@admin_ops_router.get("/admin/analytics/advanced")
async def admin_advanced_analytics(
    days: int = Query(30, ge=1, le=730),
    current_user: User = Depends(require_admin),
):
    """
    Advanced platform analytics: top sellers, top categories, conversion rates.
    Cached in-process for 60s per `days` window.
    """
    cache_key = f"advanced:{days}"
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    db = get_db()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_iso = cutoff.isoformat()

    listing_seller_map = await _build_listing_seller_map(db)

    top_sellers = await _aggregate_top_sellers(db, cutoff_iso, listing_seller_map)
    top_categories = await _aggregate_top_categories(db, cutoff_iso)
    conversion = await _compute_conversion_rates(db, cutoff_iso)

    payload = {
        "period_days": days,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "top_sellers": top_sellers,
        "top_categories": top_categories,
        "conversion": conversion,
    }
    # iter299 — merge the GMV / platform-revenue block from the new
    # deep-dive analytics so /advanced also exposes a non-empty `gmv`
    # field (required by scripts/verify_production_iter299.py).
    try:
        from routes.admin_analytics import get_admin_analytics as _iter299_overview
        overview = await _iter299_overview(admin=current_user)
        payload["gmv"] = overview.get("gmv")
        payload["platform_revenue"] = overview.get("platform_revenue")
    except Exception as _e:  # noqa: BLE001
        logger.warning(f"[advanced-analytics] gmv merge failed: {_e}")
    _cache_set(cache_key, payload)
    return payload



@admin_ops_router.get("/admin/finance/transactions/export")
async def export_transactions_csv(
    partner_only: bool = False,
    search: Optional[str] = None,
    current_user: User = Depends(require_admin)
):
    """Admin: Export all transactions as CSV for accounting."""
    query = {}
    if partner_only:
        query["is_partner_transaction"] = True
    if search:
        try:
            search = sanitize_string(search)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid search query")
        _safe = safe_regex(search)
        query["$or"] = [
            {"listing_title": {"$regex": _safe, "$options": "i"}},
            {"buyer_email": {"$regex": _safe, "$options": "i"}},
            {"seller_email": {"$regex": _safe, "$options": "i"}},
            {"partner_company": {"$regex": _safe, "$options": "i"}},
        ]
    
    db = get_db()
    transactions = await db.transactions.find(query, {"_id": 0}).sort("created_at", -1).to_list(10000)
    
    output = io.StringIO()
    writer = csv.writer(output)
    
    # Header row
    writer.writerow([
        "Date", "Item", "Buyer Email", "Seller Email", "Type",
        "Hammer Price", "Buyer Premium", "Platform Fee", "Processing Fee",
        "Partner Payout", "Stripe Charge ID", "Partner Company"
    ])
    
    for tx in transactions:
        writer.writerow([
            tx.get("created_at", ""),
            tx.get("listing_title", tx.get("listing_id", "")),
            tx.get("buyer_email", ""),
            tx.get("seller_email", ""),
            "Partner" if tx.get("is_partner_transaction") else "Standard",
            tx.get("hammer_price", 0),
            tx.get("buyer_premium", 0),
            tx.get("application_fee", tx.get("platform_fee", 0)),
            tx.get("processing_fee", 0),
            tx.get("partner_payout", tx.get("seller_payout", 0)),
            tx.get("stripe_charge_id", ""),
            tx.get("partner_company", ""),
        ])
    
    csv_content = output.getvalue()
    output.close()
    
    from starlette.responses import Response
    return Response(
        content=csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=bidvex_transactions_{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"}
    )





@admin_ops_router.get("/admin/finance/revenue-summary")
async def admin_revenue_summary(current_user: User = Depends(require_admin)):
    """Admin: Revenue dashboard — collected fees, partner fees, standard commissions."""
    db = get_db()
    # Aggregate from transactions collection
    pipeline = [
        {"$match": {"status": {"$in": ["completed", "paid", "succeeded"]}}},
        {"$group": {
            "_id": None,
            "total_hammer_volume": {"$sum": "$hammer_price"},
            "total_platform_fees": {"$sum": "$platform_fee"},
            "total_buyer_premiums": {"$sum": "$buyer_premium"},
            "total_processing_fees": {"$sum": "$processing_fee"},
            "total_transactions": {"$sum": 1},
        }}
    ]
    results = await db.transactions.aggregate(pipeline).to_list(1)
    agg = results[0] if results else {}
    
    # Partner-specific stats
    partner_pipeline = [
        {"$match": {"status": {"$in": ["completed", "paid", "succeeded"]}, "is_partner_transaction": True}},
        {"$group": {
            "_id": None,
            "partner_hammer_volume": {"$sum": "$hammer_price"},
            "partner_platform_fees": {"$sum": "$platform_fee"},
            "partner_buyer_premiums": {"$sum": "$buyer_premium"},
            "partner_transaction_count": {"$sum": 1},
        }}
    ]
    partner_results = await db.transactions.aggregate(partner_pipeline).to_list(1)
    partner_agg = partner_results[0] if partner_results else {}
    
    # User counts
    total_users = await db.users.count_documents({})
    active_partners = await db.users.count_documents({"is_partner": True, "partner_verification_status": "verified"})
    pending_partners = await db.users.count_documents({"partner_verification_status": "pending"})
    
    # Active auction stats
    active_auctions = await db.listings.count_documents({"status": "active"})
    total_listings = await db.listings.count_documents({})
    partner_listings = await db.listings.count_documents({"is_partner_listing": True, "status": "active"})
    
    # Subscription revenue
    sub_invoices = await db.subscription_invoices.find(
        {"status": "paid"}, {"_id": 0, "total": 1}
    ).to_list(1000)
    subscription_revenue = sum(inv.get("total", 0) for inv in sub_invoices)
    
    return {
        "revenue": {
            "total_hammer_volume": agg.get("total_hammer_volume", 0),
            "total_platform_fees": agg.get("total_platform_fees", 0),
            "total_buyer_premiums": agg.get("total_buyer_premiums", 0),
            "total_processing_fees": agg.get("total_processing_fees", 0),
            "total_transactions": agg.get("total_transactions", 0),
            "subscription_revenue": subscription_revenue,
        },
        "partner_revenue": {
            "hammer_volume": partner_agg.get("partner_hammer_volume", 0),
            "platform_fees_collected": partner_agg.get("partner_platform_fees", 0),
            "buyer_premiums": partner_agg.get("partner_buyer_premiums", 0),
            "transaction_count": partner_agg.get("partner_transaction_count", 0),
        },
        "users": {
            "total": total_users,
            "active_partners": active_partners,
            "pending_partners": pending_partners,
        },
        "auctions": {
            "active": active_auctions,
            "total": total_listings,
            "partner_active": partner_listings,
        }
    }




@admin_ops_router.get("/admin/finance/transactions")
async def admin_transaction_logs(
    page: int = 1,
    limit: int = 25,
    partner_only: bool = False,
    search: Optional[str] = None,
    current_user: User = Depends(require_admin)
):
    """Admin: Searchable transaction history with partner/BidVex fee split."""
    db = get_db()
    query = {}
    if partner_only:
        query["is_partner_transaction"] = True
    if search:
        try:
            search = sanitize_string(search)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid search query")
        _safe = safe_regex(search)
        query["$or"] = [
            {"listing_title": {"$regex": _safe, "$options": "i"}},
            {"buyer_email": {"$regex": _safe, "$options": "i"}},
            {"seller_email": {"$regex": _safe, "$options": "i"}},
            {"partner_company": {"$regex": _safe, "$options": "i"}},
        ]
    
    skip = (page - 1) * limit
    total = await db.transactions.count_documents(query)
    transactions = await db.transactions.find(
        query, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    return {
        "transactions": transactions,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    }




@admin_ops_router.post("/admin/users/{user_id}/pause")
async def admin_pause_user(user_id: str, current_user: User = Depends(require_admin)):
    """Admin: Pause (suspend) a user account."""
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_status = "paused" if user_doc.get("status") != "paused" else "active"
    await db.users.update_one({"id": user_id}, {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}})
    
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": f"user_{new_status}",
        "admin_id": current_user.id, "target_user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "new_status": new_status}




@admin_ops_router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, current_user: User = Depends(require_admin)):
    """Admin: Hard-delete a user and ALL related data (cascade)."""
    db = get_db()
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    deleted = {}
    # Cascade delete all related data
    for col, field in [
        ("listings", "seller_id"), ("multi_item_listings", "seller_id"),
        ("bids", "user_id"), ("notifications", "user_id"),
        ("messages", "sender_id"), ("messages", "receiver_id"),
        ("watchlist", "user_id"), ("payment_methods", "user_id"),
        ("community_questions", "author_id"), ("community_replies", "author_id"),
        ("escrow_transactions", "buyer_id"), ("escrow_transactions", "seller_id"),
        ("seller_payouts", "seller_id"), ("affiliate_referrals", "affiliate_id"),
        ("marketing_contacts", "user_id"), ("lifecycle_email_log", "user_id"),
    ]:
        r = await db[col].delete_many({field: user_id})
        if r.deleted_count > 0:
            deleted[col] = deleted.get(col, 0) + r.deleted_count

    # Delete the user
    await db.users.delete_one({"id": user_id})
    deleted["users"] = 1

    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "user_hard_deleted",
        "admin_id": current_user.id, "target_user_id": user_id,
        "target_email": user.get("email", ""),
        "cascade_deleted": deleted,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "message": "User and all related data deleted.", "deleted": deleted}




@admin_ops_router.get("/admin/listings-promotions")
async def get_admin_listings_promotions(current_user: User = Depends(require_admin)):
    """Get all listings with their promotion levels (admin only)"""
    db = get_db()
    # Get all active/upcoming listings with promotion info
    listings = await db.multi_item_listings.find(
        {"status": {"$in": ["active", "upcoming", "pending"]}},
        {
            "_id": 0, 
            "id": 1, 
            "title": 1, 
            "seller_id": 1,
            "status": 1,
            "is_promoted": 1, 
            "promotion_tier": 1,
            "promotion_start": 1,
            "promotion_end": 1,
            "is_featured": 1,
            "total_impressions": 1,
            "total_clicks": 1,
            "created_at": 1
        }
    ).sort("created_at", -1).to_list(500)
    
    # Enrich with seller info
    for listing in listings:
        seller = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0, "name": 1, "email": 1})
        listing["seller_name"] = seller.get("name") if seller else "Unknown"
        listing["seller_email"] = seller.get("email") if seller else "N/A"
    
    # Calculate revenue stats
    promotion_revenue = {
        "premium": await db.multi_item_listings.count_documents({"promotion_tier": "premium"}) * 25,
        "elite": await db.multi_item_listings.count_documents({"promotion_tier": "elite"}) * 50
    }
    
    return {
        "listings": listings,
        "stats": {
            "total_promoted": sum(1 for lst in listings if lst.get("is_promoted")),
            "premium_count": sum(1 for lst in listings if lst.get("promotion_tier") == "premium"),
            "elite_count": sum(1 for lst in listings if lst.get("promotion_tier") == "elite"),
            "promotion_revenue": promotion_revenue["premium"] + promotion_revenue["elite"]
        }
    }




@admin_ops_router.get("/admin/users/{user_id}/detail")
async def get_admin_user_detail(user_id: str, current_user: User = Depends(require_admin)):
    """Get comprehensive user details for admin panel"""
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get verification status
    sms_verification = await db.sms_verifications.find_one(
        {"user_id": user_id, "verified": True}, 
        {"_id": 0}
    )
    
    # Get payment methods count
    payment_methods_count = await db.payment_methods.count_documents({"user_id": user_id})
    
    # Get activity stats
    total_bids = await db.bids.count_documents({"bidder_id": user_id})
    total_listings = await db.listings.count_documents({"seller_id": user_id})
    total_multi_listings = await db.multi_item_listings.count_documents({"seller_id": user_id})
    
    # Build comprehensive contact card
    contact_card = {
        "identity": {
            "full_name": user_doc.get("name"),
            "email": user_doc.get("email"),
            "email_verified": user_doc.get("email_verified", False),
            "picture": user_doc.get("picture")
        },
        "phone": {
            "number": user_doc.get("phone"),
            "verified": user_doc.get("phone_verified", False),
            "verification_timestamp": sms_verification.get("verified_at") if sms_verification else None
        },
        "logistics": {
            "address": user_doc.get("address"),
            "city": user_doc.get("city"),
            "region": user_doc.get("region"),
            "postal_code": user_doc.get("postal_code"),
            "country": user_doc.get("country")
        },
        "account": {
            "role": user_doc.get("role", "user"),
            "account_type": user_doc.get("account_type", "personal"),
            "company_name": user_doc.get("company_name"),
            "tax_number": user_doc.get("tax_number"),
            "subscription_tier": user_doc.get("subscription_tier", "free"),
            "created_at": user_doc.get("created_at")
        },
        "verification_status": {
            "phone_verified": user_doc.get("phone_verified", False),
            "has_payment_method": payment_methods_count > 0,
            "payment_methods_count": payment_methods_count,
            "is_fully_verified": user_doc.get("phone_verified", False) and payment_methods_count > 0
        },
        "activity": {
            "total_bids": total_bids,
            "total_listings": total_listings + total_multi_listings,
            "preferred_language": user_doc.get("preferred_language", "en"),
            "preferred_currency": user_doc.get("preferred_currency", "CAD")
        }
    }
    
    return contact_card





# ============================================================
# MARKETPLACE LISTING MANAGEMENT (Delete, Archive, Status)
# ============================================================

@admin_ops_router.delete("/admin/listings/{listing_id}")
async def admin_delete_listing(listing_id: str, current_user: User = Depends(require_admin)):
    """Admin: Permanently delete a single listing and ALL related data (cascade)."""
    db = get_db()
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0, "title": 1, "seller_id": 1})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    deleted = {}
    # Cascade: bids, watchlist, escrows, notifications, images, reports
    for col, field in [
        ("bids", "listing_id"), ("watchlist", "listing_id"),
        ("escrow_transactions", "auction_id"), ("notifications", "listing_id"),
        ("listing_images", "listing_id"), ("reports", "listing_id"),
        ("deletion_requests", "listing_id"),
    ]:
        r = await db[col].delete_many({field: listing_id})
        if r.deleted_count > 0:
            deleted[col] = r.deleted_count

    await db.listings.delete_one({"id": listing_id})
    deleted["listings"] = 1

    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "listing_cascade_deleted",
        "admin_id": current_user.id, "target_id": listing_id,
        "target_title": listing.get("title", ""),
        "cascade_deleted": deleted,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "message": "Listing and all related data deleted.", "deleted": deleted}


@admin_ops_router.delete("/admin/multi-item-listings/{listing_id}")
async def admin_delete_multi_item_listing(listing_id: str, current_user: User = Depends(require_admin)):
    """Admin: Permanently delete a multi-item listing, lots, and ALL related data (cascade)."""
    db = get_db()
    listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0, "title": 1})
    if not listing:
        raise HTTPException(status_code=404, detail="Multi-item listing not found")

    deleted = {}
    # Get lot IDs for bid cascade
    lots = await db.lots.find({"listing_id": listing_id}, {"_id": 0, "id": 1}).to_list(1000)
    lot_ids = [lot["id"] for lot in lots]

    # Delete bids on individual lots
    if lot_ids:
        r = await db.bids.delete_many({"lot_id": {"$in": lot_ids}})
        if r.deleted_count > 0:
            deleted["bids"] = r.deleted_count

    for col, field in [
        ("lots", "listing_id"), ("watchlist", "listing_id"),
        ("escrow_transactions", "auction_id"), ("notifications", "listing_id"),
        ("listing_images", "listing_id"), ("reports", "listing_id"),
        ("deletion_requests", "listing_id"),
    ]:
        r = await db[col].delete_many({field: listing_id})
        if r.deleted_count > 0:
            deleted[col] = deleted.get(col, 0) + r.deleted_count

    await db.multi_item_listings.delete_one({"id": listing_id})
    deleted["multi_item_listings"] = 1

    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "multi_listing_cascade_deleted",
        "admin_id": current_user.id, "target_id": listing_id,
        "target_title": listing.get("title", ""),
        "cascade_deleted": deleted,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "message": "Multi-item listing, lots, and all related data deleted.", "deleted": deleted}


@admin_ops_router.put("/admin/listings/{listing_id}/status")
async def admin_update_listing_status(listing_id: str, data: Dict[str, Any], current_user: User = Depends(require_admin)):
    """Admin: Update single listing status (active, paused, archived, cancelled).

    iter290 — Multi-collection dispatch. Vehicle + storage rows surface
    in the same Manage All Auctions table; their Pause / Archive /
    Cancel CTAs hit this endpoint with their UUID. Walk every directory
    collection so the action lands on the right table.
    """
    db = get_db()
    new_status = data.get("status")
    if new_status not in ("active", "paused", "archived", "cancelled", "ended"):
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")

    updated_collection = None
    for coll_name in ("listings", "vehicle_listings", "storage_auctions", "multi_item_listings", "vehicle_multi_lot_auctions"):
        try:
            r = await db[coll_name].update_one(
                {"id": listing_id},
                {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}},
            )
        except Exception:
            r = None
        if r and r.matched_count:
            updated_collection = coll_name
            break

    if not updated_collection:
        raise HTTPException(status_code=404, detail="Listing not found")

    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": f"listing_status_{new_status}",
        "admin_id": current_user.id, "target_id": listing_id,
        "collection": updated_collection,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "collection": updated_collection,
            "message": f"Listing status updated to {new_status}"}


@admin_ops_router.put("/admin/multi-item-listings/{listing_id}/status")
async def admin_update_multi_listing_status(listing_id: str, data: Dict[str, Any], current_user: User = Depends(require_admin)):
    """Admin: Update multi-item listing status."""
    db = get_db()
    new_status = data.get("status")
    if new_status not in ("active", "paused", "archived", "cancelled", "ended", "upcoming"):
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")
    result = await db.multi_item_listings.update_one(
        {"id": listing_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Multi-item listing not found")
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": f"multi_listing_status_{new_status}",
        "admin_id": current_user.id, "target_id": listing_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "message": f"Multi-item listing status updated to {new_status}"}


# ============================================================
# USER SUSPEND (with JWT revocation + login block)
# ============================================================

@admin_ops_router.put("/admin/users/{user_id}/suspend")
async def admin_suspend_user(user_id: str, data: Dict[str, Any], current_user: User = Depends(require_admin)):
    """Admin: Suspend or unsuspend a user account. Revokes active sessions on suspend."""
    db = get_db()
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot suspend your own account")
    user_doc = await db.users.find_one({"id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    suspend = data.get("suspended", True)
    new_status = "suspended" if suspend else "active"
    update_fields = {
        "status": new_status,
        "suspended_at": datetime.now(timezone.utc).isoformat() if suspend else None,
        "suspended_by": current_user.id if suspend else None,
        "suspension_reason": data.get("reason", "Admin action") if suspend else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.users.update_one({"id": user_id}, {"$set": update_fields})

    if suspend:
        # Revoke all active sessions to force immediate logout
        await db.sessions.delete_many({"user_id": user_id})
        # Add to suspended tokens set for JWT validation
        await db.suspended_users.update_one(
            {"user_id": user_id},
            {"$set": {"user_id": user_id, "suspended_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True
        )
    else:
        await db.suspended_users.delete_one({"user_id": user_id})

    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": f"user_{new_status}",
        "admin_id": current_user.id, "target_user_id": user_id,
        "reason": data.get("reason", ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "new_status": new_status, "message": f"User {'suspended' if suspend else 'reactivated'} successfully"}


# ============================================================
# AFFILIATE PAYOUTS
# ============================================================

@admin_ops_router.get("/admin/affiliate/payouts")
async def admin_get_affiliate_payouts(current_user: User = Depends(require_admin)):
    """Admin: Get all affiliate payout requests."""
    db = get_db()
    payouts = await db.affiliate_payouts.find({}, {"_id": 0}).sort("created_at", -1).to_list(200)
    # Enrich with user info
    for payout in payouts:
        user = await db.users.find_one({"id": payout.get("user_id")}, {"_id": 0, "name": 1, "email": 1})
        payout["user_name"] = user.get("name") if user else "Unknown"
        payout["user_email"] = user.get("email") if user else "N/A"
    return payouts


@admin_ops_router.put("/admin/affiliate/payouts/{payout_id}/approve")
async def admin_approve_affiliate_payout(payout_id: str, current_user: User = Depends(require_admin)):
    """Admin: Approve an affiliate payout request."""
    db = get_db()
    payout = await db.affiliate_payouts.find_one({"id": payout_id})
    if not payout:
        raise HTTPException(status_code=404, detail="Payout request not found")
    if payout.get("status") == "approved":
        raise HTTPException(status_code=400, detail="Payout already approved")

    await db.affiliate_payouts.update_one(
        {"id": payout_id},
        {"$set": {
            "status": "approved",
            "approved_by": current_user.id,
            "approved_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    return {"success": True, "message": "Payout approved"}


# ============================================================
# SUBCATEGORY SUPPORT
# ============================================================

@admin_ops_router.get("/admin/categories")
async def admin_get_categories(current_user: User = Depends(require_admin)):
    """Admin: Get all categories including subcategories."""
    db = get_db()
    categories = await db.categories.find({}, {"_id": 0}).sort("order", 1).to_list(200)
    return categories



# ============= DEALER LICENCE VERIFICATION (Admin) =====================
# iter201 — Renamed from "OPC PERMIT VERIFICATION" to province-aware language.
# LEGACY: opc_permit → migrated to dealer_license_* — kept for back-compat only.

class OPCVerificationUpdate(BaseModel):
    """LEGACY name retained for client back-compat. Maps to dealer_license_verified."""
    opc_permit_number: Optional[str] = None
    opc_permit_verified: bool


@admin_ops_router.put("/admin/users/{user_id}/dealer-license-verify")
async def admin_dealer_license_verify(user_id: str, data: OPCVerificationUpdate, current_user: User = Depends(require_admin)):
    """iter201 — Phase 3 / 3D — Admin: Toggle dealer-licence verification for a seller (province-aware).

    Replaces the legacy `/opc-verify` endpoint. Writes BOTH legacy and new fields
    so callers reading either path see the same truth.
    """
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "name": 1})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    update_fields = {
        "opc_permit_verified": data.opc_permit_verified,            # LEGACY
        "dealer_license_verified": data.opc_permit_verified,        # NEW
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if data.opc_permit_verified:
        update_fields["dealer_license_verified_at"] = datetime.now(timezone.utc).isoformat()
        update_fields["dealer_license_verified_by"] = getattr(current_user, "email", None) or getattr(current_user, "id", None)
    if data.opc_permit_number is not None:
        update_fields["opc_permit_number"] = data.opc_permit_number     # LEGACY
        update_fields["dealer_license_number"] = data.opc_permit_number # NEW

    await db.users.update_one({"id": user_id}, {"$set": update_fields})

    await db.audit_logs.insert_one({
        "action": "dealer_license_verification",
        "admin_id": current_user.id,
        "target_user_id": user_id,
        "target_email": user_doc.get("email"),
        "dealer_license_verified": data.opc_permit_verified,
        "dealer_license_number": data.opc_permit_number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "success": True,
        "message": f"Dealer-licence verification {'enabled' if data.opc_permit_verified else 'disabled'} for {user_doc.get('email', user_id)}",
    }


@admin_ops_router.put("/admin/users/{user_id}/opc-verify")
async def admin_opc_verify(user_id: str, data: OPCVerificationUpdate, current_user: User = Depends(require_admin)):
    """LEGACY ALIAS — calls /dealer-license-verify. Logs a deprecation warning."""
    import logging
    logging.getLogger(__name__).warning(
        "DEPRECATED: opc-verify called, use dealer-license-verify"
    )
    return await admin_dealer_license_verify(user_id, data, current_user)


# ============= iter201 Phase 3 / 3B — BUYER VERIFICATION QUEUE =====================

class BuyerVerificationDecision(BaseModel):
    decision: str  # "approve" | "reject"
    rejection_reason: Optional[str] = None


@admin_ops_router.get("/admin/buyer-verifications/pending")
async def admin_list_pending_buyer_verifications(current_user: User = Depends(require_admin)):
    """List buyer-verification submissions in pending_review state (restricted provinces)."""
    db = get_db()
    cursor = db.users.find(
        {"vehicle_buyer_verification.status": "pending_review"},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "province": 1, "vehicle_buyer_verification": 1},
    )
    items = []
    async for u in cursor:
        bv = u.get("vehicle_buyer_verification") or {}
        items.append({
            "user_id": u.get("id"),
            "email": u.get("email"),
            "name": u.get("name"),
            "province": bv.get("province") or u.get("province"),
            "type": bv.get("type"),
            "license_number": bv.get("license_number"),
            "dealer_business_name": bv.get("dealer_business_name"),
            "document_path": bv.get("document_path"),
            "submitted_at": bv.get("submitted_at"),
        })
    return {"total": len(items), "items": items}


@admin_ops_router.post("/admin/buyer-verifications/{user_id}/decision")
async def admin_decide_buyer_verification(
    user_id: str,
    decision: BuyerVerificationDecision,
    current_user: User = Depends(require_admin),
):
    """Approve or reject a buyer-verification submission."""
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "name": 1, "vehicle_buyer_verification": 1, "preferred_language": 1})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    bv = user_doc.get("vehicle_buyer_verification") or {}
    if (bv.get("status") or "") != "pending_review":
        raise HTTPException(status_code=400, detail="Submission is not in pending_review state")

    now_iso = datetime.now(timezone.utc).isoformat()
    if decision.decision == "approve":
        bv.update({
            "verified": True,
            "verified_at": now_iso,
            "verified_by": getattr(current_user, "email", None) or getattr(current_user, "id", None),
            "status": "approved",
            "rejection_reason": None,
        })
        action = "buyer_verification_approved"
    elif decision.decision == "reject":
        if not (decision.rejection_reason or "").strip():
            raise HTTPException(status_code=400, detail="rejection_reason required for reject")
        bv.update({
            "verified": False,
            "status": "rejected",
            "rejection_reason": decision.rejection_reason.strip()[:500],
            "verified_by": getattr(current_user, "email", None) or getattr(current_user, "id", None),
        })
        action = "buyer_verification_rejected"
    else:
        raise HTTPException(status_code=400, detail="decision must be 'approve' or 'reject'")

    await db.users.update_one({"id": user_id}, {"$set": {"vehicle_buyer_verification": bv, "updated_at": now_iso}})
    await db.audit_logs.insert_one({
        "action": action,
        "admin_id": getattr(current_user, "id", None),
        "target_user_id": user_id,
        "target_email": user_doc.get("email"),
        "rejection_reason": bv.get("rejection_reason"),
        "timestamp": now_iso,
    })

    # Fire bilingual email (best-effort)
    try:
        from services.emails.email_vehicles import send_buyer_verification_decision_email
        await send_buyer_verification_decision_email(
            recipient=user_doc,
            decision=decision.decision,
            province=bv.get("province"),
            rejection_reason=bv.get("rejection_reason"),
            verification_type=bv.get("type"),
        )
    except Exception:
        pass

    return {"success": True, "decision": decision.decision, "user_id": user_id}


# ============= iter201 Phase 3 / 3B — COMPLIANCE ALERTS PANEL =====================

@admin_ops_router.get("/admin/compliance-alerts")
async def admin_compliance_alerts(current_user: User = Depends(require_admin)):
    """Aggregate compliance alerts surfaced to the admin Dealer Verification tab.

    Returns 4 buckets:
      • expired — licenses expired or expiring within 30 days
      • high_fraud_score — vehicle listings with fraud_score > 0.6
      • unreviewed_manual_review — listings stuck in manual_review > 24 h
      • territory_bids — recent bid attempts from YT/NT/NU
    """
    db = get_db()
    now = datetime.now(timezone.utc)
    soon = now + timedelta(days=30)
    yesterday = now - timedelta(hours=24)

    expired = []
    async for u in db.users.find(
        {"dealer_license_verified": True, "dealer_license_expiry_date": {"$exists": True, "$ne": None}},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "dealer_license_province": 1, "dealer_license_expiry_date": 1},
    ).limit(200):
        exp = u.get("dealer_license_expiry_date")
        if isinstance(exp, str):
            try:
                exp_dt = datetime.fromisoformat(exp.replace("Z", "+00:00"))
            except Exception:
                continue
        else:
            exp_dt = exp
        if exp_dt and exp_dt <= soon:
            expired.append({
                "user_id": u["id"],
                "email": u.get("email"),
                "name": u.get("name"),
                "province": u.get("dealer_license_province"),
                "expiry_date": exp_dt.isoformat(),
                "expired": exp_dt < now,
            })

    high_fraud = []
    async for v in db.vehicle_listings.find(
        {"fraud_score": {"$gt": 0.6}},
        {"_id": 0, "id": 1, "title": 1, "fraud_score": 1, "moderation_flags": 1, "seller_id": 1},
    ).limit(50):
        high_fraud.append({
            "vehicle_id": v["id"],
            "title": v.get("title"),
            "fraud_score": v.get("fraud_score"),
            "flags": v.get("moderation_flags") or [],
            "seller_id": v.get("seller_id"),
        })

    unreviewed = []
    async for v in db.vehicle_listings.find(
        {"status": "manual_review", "created_at": {"$lt": yesterday.isoformat()}},
        {"_id": 0, "id": 1, "title": 1, "created_at": 1, "seller_id": 1},
    ).limit(50):
        unreviewed.append({
            "vehicle_id": v["id"],
            "title": v.get("title"),
            "created_at": v.get("created_at"),
            "seller_id": v.get("seller_id"),
        })

    territory_bids = []
    async for log in db.audit_logs.find(
        {"action": "territory_vehicle_bid", "timestamp": {"$gte": (now - timedelta(days=7)).isoformat()}},
        {"_id": 0},
    ).sort("timestamp", -1).limit(50):
        territory_bids.append(log)

    # iter206 — Pending-review moderation queue (auto-paused vehicle listings)
    # Surfaces every listing the watchdog/scanner/cleanup auto-paused so admins
    # can approve or reject from the UI without DB queries.
    pending_review_queue = []
    seller_cache: dict = {}
    for collection_name in ("listings", "multi_item_listings"):
        async for doc in db[collection_name].find(
            {"status": "pending_review"},
            {"_id": 0, "id": 1, "title": 1, "category": 1, "seller_id": 1,
             "compliance_signals": 1, "compliance_strength": 1, "paused_by": 1,
             "paused_at": 1, "paused_reason": 1, "previous_status": 1,
             "images": 1, "starting_price": 1, "current_price": 1,
             "location_city": 1, "location_province": 1, "created_at": 1},
        ).sort("paused_at", -1).limit(100):
            seller_id = doc.get("seller_id")
            if seller_id and seller_id not in seller_cache:
                seller_cache[seller_id] = await db.users.find_one(
                    {"id": seller_id},
                    {"_id": 0, "id": 1, "email": 1, "name": 1,
                     "seller_type": 1, "dealer_license_verified": 1,
                     "dealer_license_province": 1},
                ) or {}
            seller = seller_cache.get(seller_id, {})
            pending_review_queue.append({
                "listing_id": doc["id"],
                "collection": collection_name,
                "title": doc.get("title"),
                "category": doc.get("category"),
                "first_image": (doc.get("images") or [None])[0],
                "starting_price": doc.get("starting_price"),
                "current_price": doc.get("current_price"),
                "city": doc.get("location_city"),
                "province": doc.get("location_province"),
                "seller_id": seller_id,
                "seller_email": seller.get("email"),
                "seller_name": seller.get("name"),
                "seller_type": seller.get("seller_type"),
                "seller_dealer_verified": bool(seller.get("dealer_license_verified")),
                "compliance_signals": doc.get("compliance_signals") or [],
                "compliance_strength": doc.get("compliance_strength"),
                "paused_by": doc.get("paused_by"),
                "paused_at": doc.get("paused_at"),
                "paused_reason": doc.get("paused_reason"),
                "previous_status": doc.get("previous_status"),
                "created_at": doc.get("created_at"),
            })

    # iter217 Phase 3 — Unpaid annual-fee subscriptions (dealers + partners)
    # Surfaces accounts that have completed admin verification but whose
    # annual subscription is not active (or has lapsed).
    unpaid_dealers = []
    async for u in db.users.find(
        {"is_vehicle_dealer": True, "dealer_verification_status": {"$in": ["verified", "approved"]},
         "$or": [{"dealer_subscription_active": {"$ne": True}}, {"dealer_subscription_active": {"$exists": False}}]},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "company_name": 1,
         "dealer_license_province": 1, "dealer_subscription_active": 1,
         "dealer_subscription_renewal_date": 1},
    ).limit(100):
        unpaid_dealers.append({
            "user_id": u["id"],
            "email": u.get("email"),
            "name": u.get("name") or u.get("company_name") or "",
            "province": u.get("dealer_license_province"),
            "renewal_date": u.get("dealer_subscription_renewal_date"),
            "alert_type": "dealer_subscription_unpaid",
        })

    unpaid_partners = []
    async for u in db.users.find(
        {"is_partner": True, "partner_verification_status": {"$in": ["verified", "approved"]},
         "$or": [{"partner_subscription_active": {"$ne": True}}, {"partner_subscription_active": {"$exists": False}}]},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "partner_company_name": 1,
         "partner_subscription_active": 1, "partner_subscription_renewal_date": 1},
    ).limit(100):
        unpaid_partners.append({
            "user_id": u["id"],
            "email": u.get("email"),
            "name": u.get("name") or u.get("partner_company_name") or "",
            "renewal_date": u.get("partner_subscription_renewal_date"),
            "alert_type": "partner_subscription_unpaid",
        })

    # iter217 Phase 3 — Storage facilities with unverified registration
    unverified_facilities = []
    async for f in db.storage_facilities.find(
        {"verification_status": {"$nin": ["verified", "approved"]}},
        {"_id": 0, "id": 1, "facility_name": 1, "owner_id": 1, "owner_email": 1,
         "verification_status": 1, "created_at": 1},
    ).limit(100):
        unverified_facilities.append({
            "facility_id": f.get("id"),
            "name": f.get("facility_name"),
            "owner_email": f.get("owner_email"),
            "status": f.get("verification_status"),
            "created_at": f.get("created_at"),
            "alert_type": "storage_facility_unverified",
        })

    return {
        "expired": expired,
        "high_fraud_score": high_fraud,
        "unreviewed_manual_review": unreviewed,
        "territory_bids": territory_bids,
        # iter206
        "pending_review_queue": pending_review_queue,
        # iter217 Phase 3
        "unpaid_dealers": unpaid_dealers,
        "unpaid_partners": unpaid_partners,
        "unverified_facilities": unverified_facilities,
        "checked_at": now.isoformat(),
    }


# ============= iter206 — MODERATION ACTIONS (Approve / Reject) ==========
class ModerationActionRequest(BaseModel):
    note: Optional[str] = None  # admin's reason for the override


@admin_ops_router.post("/admin/compliance/listings/{listing_id}/approve")
async def admin_approve_paused_listing(
    listing_id: str,
    payload: ModerationActionRequest,
    current_user: User = Depends(require_admin),
):
    """iter206 — Admin override: re-publishes a `pending_review` listing.

    Used in two contexts:
      • A false-positive (the listing wasn't actually a vehicle)
      • An override the admin is willing to take responsibility for
    Always writes a `compliance_signals_overridden` audit log with the
    admin user_id, signals that fired, and the optional note — preserving
    full evidence for any future regulator audit.
    """
    db = get_db()
    for collection in ("listings", "multi_item_listings"):
        listing = await db[collection].find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            continue
        if listing.get("status") != "pending_review":
            raise HTTPException(
                status_code=400,
                detail=f"Listing is in status='{listing.get('status')}', not pending_review",
            )
        previous_status = listing.get("previous_status") or "active"
        await db[collection].update_one(
            {"id": listing_id},
            {"$set": {
                "status": previous_status,
                "approved_at": datetime.now(timezone.utc).isoformat(),
                "approved_by": current_user.id,
                "approval_note": (payload.note or "")[:500],
                "compliance_overridden": True,
            }, "$unset": {"paused_at": "", "paused_reason": "", "paused_by": ""}},
        )
        await db.audit_logs.insert_one({
            "action": "compliance_signals_overridden",
            "decision": "approved",
            "collection": collection,
            "listing_id": listing_id,
            "admin_id": current_user.id,
            "admin_email": current_user.email,
            "previous_status": previous_status,
            "compliance_signals": listing.get("compliance_signals") or [],
            "compliance_strength": listing.get("compliance_strength"),
            "note": payload.note,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await db.admin_notifications.update_many(
            {"listing_id": listing_id, "resolved": False},
            {"$set": {"resolved": True, "resolved_by": current_user.id,
                      "resolved_at": datetime.now(timezone.utc).isoformat(),
                      "resolution": "approved"}},
        )
        # Notify the seller — listing back online
        try:
            from services.compliance_notifier import notify_seller_of_resolution
            await notify_seller_of_resolution(
                db, listing=listing, decision="approved",
                admin_email=current_user.email, note=payload.note,
                collection=collection,
            )
        except Exception:
            pass
        return {"ok": True, "decision": "approved", "listing_id": listing_id, "restored_status": previous_status}
    raise HTTPException(status_code=404, detail="Listing not found")


@admin_ops_router.post("/admin/compliance/listings/{listing_id}/reject")
async def admin_reject_paused_listing(
    listing_id: str,
    payload: ModerationActionRequest,
    current_user: User = Depends(require_admin),
):
    """iter206 — Admin confirms the violation: status → 'rejected' (terminal)."""
    db = get_db()
    for collection in ("listings", "multi_item_listings"):
        listing = await db[collection].find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            continue
        await db[collection].update_one(
            {"id": listing_id},
            {"$set": {
                "status": "rejected",
                "rejected_at": datetime.now(timezone.utc).isoformat(),
                "rejected_by": current_user.id,
                "rejection_note": (payload.note or "")[:500],
            }},
        )
        await db.audit_logs.insert_one({
            "action": "compliance_listing_rejected",
            "decision": "rejected",
            "collection": collection,
            "listing_id": listing_id,
            "admin_id": current_user.id,
            "admin_email": current_user.email,
            "compliance_signals": listing.get("compliance_signals") or [],
            "compliance_strength": listing.get("compliance_strength"),
            "note": payload.note,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        await db.admin_notifications.update_many(
            {"listing_id": listing_id, "resolved": False},
            {"$set": {"resolved": True, "resolved_by": current_user.id,
                      "resolved_at": datetime.now(timezone.utc).isoformat(),
                      "resolution": "rejected"}},
        )
        try:
            from services.compliance_notifier import notify_seller_of_resolution
            await notify_seller_of_resolution(
                db, listing=listing, decision="rejected",
                admin_email=current_user.email, note=payload.note,
                collection=collection,
            )
        except Exception:
            pass
        return {"ok": True, "decision": "rejected", "listing_id": listing_id}
    raise HTTPException(status_code=404, detail="Listing not found")


# iter206 — One-click cleanup runner (admin-only) so the user can trigger
# the watchdog from the browser instead of SSHing into the server.
@admin_ops_router.post("/admin/compliance/run-cleanup")
async def admin_run_compliance_cleanup(current_user: User = Depends(require_admin)):
    """Trigger an on-demand watchdog scan (same code path as the 60-min cron).
    Useful right after deploying a detection-vocabulary update."""
    db = get_db()
    from services.safety_watchdog import cleanup_existing_violations
    summary = await cleanup_existing_violations(db)
    return summary


@admin_ops_router.get("/admin/compliance-alerts/count")
async def admin_compliance_alerts_count(current_user: User = Depends(require_admin)):
    """Lightweight counter for the Admin Home triage card (iter197 pattern)."""
    data = await admin_compliance_alerts(current_user)
    return {"total": (
        len(data.get("expired") or [])
        + len(data.get("high_fraud_score") or [])
        + len(data.get("unreviewed_manual_review") or [])
        + len(data.get("pending_review_queue") or [])  # iter206
        + len(data.get("unpaid_dealers") or [])  # iter217 Phase 3
        + len(data.get("unpaid_partners") or [])
        + len(data.get("unverified_facilities") or [])
    )}


# ============= iter203 — COMPLIANCE HEALTH KPI ==========================
@admin_ops_router.get("/admin/compliance/health")
async def admin_compliance_health(current_user: User = Depends(require_admin)):
    """iter203 — Compliance Health traffic-light KPI for Admin Home.

    Status bands (green / yellow / red) reflect the health of the three-layer
    vehicle-listing defence system:

      • green  → All systems nominal: 0 pending_review, AI scanner healthy in
                 the last hour, watchdog ran in the last 90 minutes
      • yellow → 1+ pending_review awaiting moderator OR watchdog hasn't run
                 in 90+ minutes (still under 4 h)
      • red    → 5+ pending_review (queue is backing up) OR watchdog hasn't
                 run in 4+ hours OR AI scanner has failed 3+ times in the last
                 hour (Gemini outage / quota exhausted)

    Counters returned:
      • pending_review            — listings waiting for human review
      • blocked_today             — vehicle_listing_blocked audit-log entries today
      • paused_by_ai_today        — AI-scanner-paused listings today
      • paused_by_watchdog_today  — watchdog-paused listings today
      • ai_unavailable_last_hour  — AI scanner failures in the last 60 min
      • last_watchdog_run         — ISO timestamp + minutes since
      • status                    — green | yellow | red
      • status_reasons            — list of human-readable reasons (admin tooltip)
    """
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    one_hour_ago = now - timedelta(hours=1)
    db = get_db()

    # Pending review (single + multi-item listings) — both require admin action
    pending_single = await db.listings.count_documents({"status": "pending_review"})
    pending_multi = await db.multi_item_listings.count_documents({"status": "pending_review"})
    pending_review = pending_single + pending_multi

    # Today's audit log counters
    blocked_today = await db.audit_logs.count_documents({
        "action": "vehicle_listing_blocked",
        "timestamp": {"$gte": today_start.isoformat()},
    })
    paused_by_ai_today = await db.audit_logs.count_documents({
        "action": "vehicle_listing_paused_by_ai_scanner",
        "timestamp": {"$gte": today_start.isoformat()},
    })
    paused_by_watchdog_today = await db.audit_logs.count_documents({
        "action": "vehicle_listing_paused_by_watchdog",
        "timestamp": {"$gte": today_start.isoformat()},
    })

    # AI scanner failures (last 60 min) — flag if too many
    ai_unavailable_last_hour = await db.listing_scans.count_documents({
        "status": "ai_unavailable",
        "scanned_at": {"$gte": one_hour_ago.isoformat()},
    })

    # Last watchdog run
    last_run_doc = await db.audit_logs.find_one(
        {"action": "watchdog_run"},
        {"_id": 0, "timestamp": 1, "total_examined": 1, "total_paused": 1, "triggered_by": 1},
        sort=[("timestamp", -1)],
    )
    last_watchdog_run_iso = last_run_doc.get("timestamp") if last_run_doc else None
    if last_watchdog_run_iso:
        try:
            ts = datetime.fromisoformat(last_watchdog_run_iso.replace("Z", "+00:00"))
            minutes_since_run = max(0, int((now - ts).total_seconds() / 60))
        except Exception:
            minutes_since_run = None
    else:
        minutes_since_run = None

    # iter205 P0 — False-negative scan: detect active listings that LOOK
    # like vehicles (any brand/model/strong signal hit) but were never paused.
    # This catches the case where the watchdog ran but its detection logic
    # missed a violation (e.g. "ford f150" before the iter205 vocabulary
    # update). It is the KPI's independent observability layer — it does NOT
    # share code with the watchdog, so it can flag a drift between detection
    # rules and reality.
    # Implementation: re-run the latest is_vehicle_listing() against every
    # active listing, with a permissive threshold (2 — any single signal).
    from services.vehicle_listing_guard import is_vehicle_listing
    suspicious_active: list[dict] = []
    cursor = db.listings.find(
        {"status": {"$in": ["active", "upcoming"]}},
        {"_id": 0, "id": 1, "seller_id": 1, "category": 1, "title": 1,
         "description": 1, "compliance_signals": 1},
    ).limit(2000)
    async for listing in cursor:
        is_v, signals, strength = is_vehicle_listing(
            listing.get("category"),
            listing.get("title"),
            listing.get("description"),
            threshold=2,  # permissive — flag anything with ANY brand/model/year hit
        )
        if not is_v:
            continue
        # If the listing was already flagged during a watchdog pause but
        # somehow remained active, surface it. Otherwise, also surface fresh
        # detections — these are exactly the slip-throughs the user reported.
        suspicious_active.append({
            "id": listing.get("id"),
            "seller_id": listing.get("seller_id"),
            "title": (listing.get("title") or "")[:120],
            "category": listing.get("category"),
            "signals": signals,
            "strength": strength,
        })
    suspicious_active_count = len(suspicious_active)

    # Determine traffic-light status
    reasons: list[str] = []
    status = "green"

    # RED conditions (worst tier wins)
    if pending_review >= 5:
        reasons.append(f"{pending_review} listings stuck in pending_review")
        status = "red"
    if minutes_since_run is None:
        reasons.append("Watchdog has never run on this deployment")
        status = "red"
    elif minutes_since_run > 240:
        reasons.append(f"Watchdog hasn't run in {minutes_since_run} minutes (>4h)")
        status = "red"
    if ai_unavailable_last_hour >= 3:
        reasons.append(f"{ai_unavailable_last_hour} AI scanner failures in the last hour")
        status = "red"
    # iter205 — false-negative / drift detection
    if suspicious_active_count >= 1:
        reasons.append(
            f"⚠️ {suspicious_active_count} active listing(s) match vehicle signals but were "
            "NOT paused — possible detection drift (run cleanup script)"
        )
        # 1+ suspicious active = at least yellow; 3+ = red because the safety
        # net has clearly missed something blatant
        status = "red" if suspicious_active_count >= 3 else (status if status == "red" else "yellow")
    # iter205 — watchdog "missed run" detection (interval is 60 min — if last
    # run was more than 75 minutes ago AND scheduler should have ticked, that's
    # a missed run — yellow at minimum, escalates to red the longer it goes)
    if minutes_since_run is not None and 75 <= minutes_since_run <= 240:
        reasons.append(f"Watchdog missed scheduled run ({minutes_since_run} min ago, expected ≤60)")
        status = "red" if status == "red" else "yellow"

    # YELLOW conditions (only escalate if not already red)
    if status != "red":
        if pending_review >= 1:
            reasons.append(f"{pending_review} listing(s) awaiting human review")
            status = "yellow"
        if minutes_since_run is not None and 75 < minutes_since_run <= 240:
            # Already covered above, but kept for clarity
            pass
        if ai_unavailable_last_hour >= 1:
            reasons.append(f"{ai_unavailable_last_hour} AI scanner error(s) in the last hour")
            status = "yellow"

    # Green default
    if status == "green" and not reasons:
        reasons.append("All systems nominal")

    return {
        "status": status,
        "status_reasons": reasons,
        "pending_review": pending_review,
        "pending_review_breakdown": {
            "single_listings": pending_single,
            "multi_item_listings": pending_multi,
        },
        "blocked_today": blocked_today,
        "paused_by_ai_today": paused_by_ai_today,
        "paused_by_watchdog_today": paused_by_watchdog_today,
        "ai_unavailable_last_hour": ai_unavailable_last_hour,
        "last_watchdog_run": last_watchdog_run_iso,
        "minutes_since_last_watchdog": minutes_since_run,
        # iter205 — false-negative / detection-drift observability
        "suspicious_active_count": suspicious_active_count,
        "suspicious_active_samples": suspicious_active[:5],
        "checked_at": now.isoformat(),
    }


# ============= CFIA SOIL DECLARATION CATEGORIES ========================

CFIA_TRIGGER_CATEGORIES = [
    "heavy equipment", "heavy_equipment", "tractors", "excavators",
    "heavy_construction", "bulldozers", "skid_steers", "combines",
    "industrial_machinery", "construction & excavation", "material handling (forklifts)",
    "tillage & seeding", "harvesting (combines)", "livestock & dairy",
]



# ============= RESEND WELCOME EMAIL (Admin) ========================

class ResendWelcomeRequest(BaseModel):
    email: str

@admin_ops_router.post("/admin/resend-welcome-email")
async def admin_resend_welcome_email(data: ResendWelcomeRequest, current_user: User = Depends(require_admin)):
    """Admin: Resend bilingual welcome email to any user."""
    db = get_db()
    user_doc = await db.users.find_one(
        {"email": data.email.lower().strip()},
        {"_id": 0, "name": 1, "email": 1, "preferred_language": 1, "language_preference": 1}
    )
    if not user_doc:
        raise HTTPException(status_code=404, detail=f"No user found with email: {data.email}")
    
    from services.email_service import send_welcome_email as send_welcome_template
    success = await send_welcome_template(user_doc)
    
    return {
        "success": success,
        "message": f"Welcome email {'sent' if success else 'failed'} for {user_doc['email']}"
    }


# ============= COMMUNITY MODERATION (Admin) ========================

@admin_ops_router.delete("/admin/comments/question/{question_id}")
async def admin_delete_question(question_id: str, current_user: User = Depends(require_admin)):
    """Admin: Delete a community question and all its replies."""
    db = get_db()
    question = await db.community_questions.find_one({"id": question_id}, {"_id": 0, "title": 1})
    if not question:
        raise HTTPException(status_code=404, detail="Question not found")

    deleted = {}
    r = await db.community_replies.delete_many({"question_id": question_id})
    if r.deleted_count > 0:
        deleted["community_replies"] = r.deleted_count
    await db.community_questions.delete_one({"id": question_id})
    deleted["community_questions"] = 1

    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "community_question_deleted",
        "admin_id": current_user.id, "target_id": question_id,
        "target_title": question.get("title", ""),
        "cascade_deleted": deleted,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "message": "Question and replies deleted.", "deleted": deleted}


@admin_ops_router.delete("/admin/comments/reply/{reply_id}")
async def admin_delete_reply(reply_id: str, current_user: User = Depends(require_admin)):
    """Admin: Delete a single community reply."""
    db = get_db()
    reply = await db.community_replies.find_one({"id": reply_id}, {"_id": 0, "question_id": 1})
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")

    await db.community_replies.delete_one({"id": reply_id})
    # Decrement reply count on parent question
    await db.community_questions.update_one(
        {"id": reply["question_id"]},
        {"$inc": {"reply_count": -1}}
    )

    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "community_reply_deleted",
        "admin_id": current_user.id, "target_id": reply_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "message": "Reply deleted."}


# ============= ADMIN COMMUNITY LIST (for moderation panel) ========================

@admin_ops_router.get("/admin/community/questions")
async def admin_list_community_questions(
    limit: int = 50,
    skip: int = 0,
    search: Optional[str] = None,
    current_user: User = Depends(require_admin),
):
    """Admin: List all community questions for moderation."""
    db = get_db()
    query = {}
    if search:
        try:
            search = sanitize_string(search)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid search query")
        _safe = safe_regex(search)
        query["$or"] = [
            {"title": {"$regex": _safe, "$options": "i"}},
            {"body": {"$regex": _safe, "$options": "i"}},
            {"author_name": {"$regex": _safe, "$options": "i"}},
        ]
    total = await db.community_questions.count_documents(query)
    questions = await db.community_questions.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"questions": questions, "total": total}


@admin_ops_router.get("/admin/community/questions/{question_id}/replies")
async def admin_list_replies(question_id: str, current_user: User = Depends(require_admin)):
    """Admin: Get all replies for a specific question."""
    db = get_db()
    replies = await db.community_replies.find({"question_id": question_id}, {"_id": 0}).sort("created_at", 1).to_list(500)
    return {"replies": replies}


# ============= PLATFORM CLEANUP (Admin) ========================

TEST_DATA_EMAIL_PATTERNS = ["test", "demo", "qa", "fake", "spam", "example.com", "mailinator"]

@admin_ops_router.get("/admin/platform-cleanup/preview")
async def admin_cleanup_preview(current_user: User = Depends(require_admin)):
    """Admin: Preview what test data would be deleted (dry run)."""
    db = get_db()
    pattern_filter = {"$or": [{"email": {"$regex": p, "$options": "i"}} for p in TEST_DATA_EMAIL_PATTERNS]}

    # Exclude admin's own email
    admin_email = current_user.email.lower()
    safe_filter = {"$and": [
        pattern_filter,
        {"email": {"$ne": admin_email}},
        {"role": {"$ne": "admin"}},
        {"role": {"$ne": "super_admin"}},
    ]}
    safe_test_users = await db.users.count_documents(safe_filter)

    # Find IDs of test users
    test_user_docs = await db.users.find(safe_filter, {"_id": 0, "id": 1}).to_list(5000)
    test_user_ids = [u["id"] for u in test_user_docs if u.get("id")]

    # Count related data
    preview = {
        "test_users": safe_test_users,
        "test_listings": await db.listings.count_documents({"seller_id": {"$in": test_user_ids}}) if test_user_ids else 0,
        "test_multi_listings": await db.multi_item_listings.count_documents({"seller_id": {"$in": test_user_ids}}) if test_user_ids else 0,
        "test_bids": await db.bids.count_documents({"user_id": {"$in": test_user_ids}}) if test_user_ids else 0,
        "test_messages": await db.messages.count_documents({"$or": [{"sender_id": {"$in": test_user_ids}}, {"receiver_id": {"$in": test_user_ids}}]}) if test_user_ids else 0,
        "test_notifications": await db.notifications.count_documents({"user_id": {"$in": test_user_ids}}) if test_user_ids else 0,
        "test_payment_methods": await db.payment_methods.count_documents({"user_id": {"$in": test_user_ids}}) if test_user_ids else 0,
        "test_escrows": await db.escrow_transactions.count_documents({"$or": [{"buyer_id": {"$in": test_user_ids}}, {"seller_id": {"$in": test_user_ids}}]}) if test_user_ids else 0,
        "test_community_questions": await db.community_questions.count_documents({"author_id": {"$in": test_user_ids}}) if test_user_ids else 0,
        "test_community_replies": await db.community_replies.count_documents({"author_id": {"$in": test_user_ids}}) if test_user_ids else 0,
        "test_watchlist": await db.watchlist.count_documents({"user_id": {"$in": test_user_ids}}) if test_user_ids else 0,
    }
    preview["total_records"] = sum(preview.values())
    return preview


@admin_ops_router.post("/admin/platform-cleanup")
async def admin_platform_cleanup(current_user: User = Depends(require_admin)):
    """Admin: Delete all test/demo data from the platform. Protects admin and real user accounts."""
    db = get_db()
    pattern_filter = {"$or": [{"email": {"$regex": p, "$options": "i"}} for p in TEST_DATA_EMAIL_PATTERNS]}
    admin_email = current_user.email.lower()

    safe_filter = {"$and": [
        pattern_filter,
        {"email": {"$ne": admin_email}},
        {"role": {"$ne": "admin"}},
        {"role": {"$ne": "super_admin"}},
    ]}

    test_user_docs = await db.users.find(safe_filter, {"_id": 0, "id": 1, "email": 1}).to_list(5000)
    test_user_ids = [u["id"] for u in test_user_docs if u.get("id")]

    if not test_user_ids:
        return {"success": True, "message": "No test data found. Platform is clean.", "deleted": {}}

    deleted = {}
    # Cascade delete all related data for test users
    collections_to_clean = [
        ("listings", "seller_id"), ("multi_item_listings", "seller_id"),
        ("bids", "user_id"), ("notifications", "user_id"),
        ("watchlist", "user_id"), ("payment_methods", "user_id"),
        ("community_questions", "author_id"), ("community_replies", "author_id"),
        ("escrow_transactions", "buyer_id"), ("escrow_transactions", "seller_id"),
        ("seller_payouts", "seller_id"), ("affiliate_referrals", "affiliate_id"),
        ("marketing_contacts", "user_id"), ("lifecycle_email_log", "user_id"),
        ("sessions", "user_id"), ("suspended_users", "user_id"),
    ]

    for col, field in collections_to_clean:
        try:
            r = await db[col].delete_many({field: {"$in": test_user_ids}})
            if r.deleted_count > 0:
                deleted[col] = deleted.get(col, 0) + r.deleted_count
        except Exception:
            pass  # Collection may not exist

    # Delete messages (sender or receiver)
    try:
        r = await db.messages.delete_many({"$or": [
            {"sender_id": {"$in": test_user_ids}},
            {"receiver_id": {"$in": test_user_ids}},
        ]})
        if r.deleted_count > 0:
            deleted["messages"] = r.deleted_count
    except Exception:
        pass

    # Delete test users themselves
    r = await db.users.delete_many({"id": {"$in": test_user_ids}})
    deleted["users"] = r.deleted_count

    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "platform_cleanup",
        "admin_id": current_user.id,
        "test_users_deleted": len(test_user_ids),
        "test_emails": [u.get("email", "") for u in test_user_docs[:20]],
        "cascade_deleted": deleted,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    return {
        "success": True,
        "message": f"Platform cleanup complete. {len(test_user_ids)} test users and all related data removed.",
        "deleted": deleted,
    }
