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




@admin_ops_router.get("/admin/listings/all")
async def get_all_listings_admin(current_user: User = Depends(require_admin)):
    """Admin: Get all single listings"""
    db = get_db()
    listings = await db.listings.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
    return listings



@admin_ops_router.get("/admin/multi-item-listings/all")
async def get_all_multi_listings_admin(current_user: User = Depends(require_admin)):
    """Admin: Get all multi-item listings"""
    db = get_db()
    listings = await db.multi_item_listings.find({}, {"_id": 0}).sort("created_at", -1).to_list(None)
    return listings




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
    db = get_db()
    is_featured = data.get("is_featured", False)
    await db.listings.update_one({"id": listing_id}, {"$set": {"is_featured": is_featured}})
    return {"message": f"Listing {'featured' if is_featured else 'unfeatured'}"}

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
async def admin_set_affiliate_status(user_id: str, data: Dict[str, bool], current_user: User = Depends(require_admin)):
    db = get_db()
    is_affiliate = data.get("is_affiliate", False)
    if is_affiliate:
        affiliate_code = str(uuid.uuid4())[:8]
        await db.affiliates.insert_one({
            "id": str(uuid.uuid4()),
            "user_id": user_id,
            "affiliate_code": affiliate_code,
            "total_earnings": 0.0,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    else:
        await db.affiliates.delete_one({"user_id": user_id})
    
    return {"message": f"Affiliate status {'enabled' if is_affiliate else 'disabled'}"}



@admin_ops_router.get("/admin/users/filter")
async def admin_filter_users(account_type: str = None, current_user: User = Depends(require_admin)):
    db = get_db()
    query = {}
    if account_type:
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
    """Return all pending single-item + multi-item listings, newest first."""
    db = get_db()
    pending_single = await db.listings.find(
        {"status": "pending"}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    pending_multi = await db.multi_item_listings.find(
        {"status": "pending"}, {"_id": 0}
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
    if listing.get("status") != "pending":
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
    if listing.get("status") != "pending":
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
    """Admin: Update single listing status (active, paused, archived, cancelled)."""
    db = get_db()
    new_status = data.get("status")
    if new_status not in ("active", "paused", "archived", "cancelled", "ended"):
        raise HTTPException(status_code=400, detail=f"Invalid status: {new_status}")
    result = await db.listings.update_one(
        {"id": listing_id},
        {"$set": {"status": new_status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Listing not found")
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": f"listing_status_{new_status}",
        "admin_id": current_user.id, "target_id": listing_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "message": f"Listing status updated to {new_status}"}


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



# ============= OPC PERMIT VERIFICATION (Admin) ========================

class OPCVerificationUpdate(BaseModel):
    opc_permit_number: Optional[str] = None
    opc_permit_verified: bool

@admin_ops_router.put("/admin/users/{user_id}/opc-verify")
async def admin_opc_verify(user_id: str, data: OPCVerificationUpdate, current_user: User = Depends(require_admin)):
    """Admin: Toggle OPC permit verification for a seller."""
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "name": 1})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    update_fields = {
        "opc_permit_verified": data.opc_permit_verified,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    if data.opc_permit_number is not None:
        update_fields["opc_permit_number"] = data.opc_permit_number
    
    await db.users.update_one({"id": user_id}, {"$set": update_fields})
    
    await db.audit_logs.insert_one({
        "action": "opc_permit_verification",
        "admin_id": current_user.id,
        "target_user_id": user_id,
        "target_email": user_doc.get("email"),
        "opc_permit_verified": data.opc_permit_verified,
        "opc_permit_number": data.opc_permit_number,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    
    return {"success": True, "message": f"OPC verification {'enabled' if data.opc_permit_verified else 'disabled'} for {user_doc.get('email', user_id)}"}


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
    test_user_ids = [u["id"] for u in test_user_docs]

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
    test_user_ids = [u["id"] for u in test_user_docs]

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
