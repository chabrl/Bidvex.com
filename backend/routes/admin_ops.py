"""
BidVex - Admin Operations (Reports, Listings, Users, Finance)
Auto-extracted from server.py during P2 refactoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from deps import get_db, get_current_user, get_current_user_optional, require_admin, User
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






@admin_ops_router.get("/admin/listings/pending")
async def admin_get_pending_listings(current_user: User = Depends(require_admin)):
    db = get_db()
    listings = await db.listings.find({"status": "pending"}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return [dict(**listing) for listing in listings]



@admin_ops_router.put("/admin/listings/{listing_id}/moderate")
async def admin_moderate_listing(listing_id: str, data: Dict[str, str], current_user: User = Depends(require_admin)):
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
async def admin_revenue_analytics(current_user: User = Depends(require_admin)):
    db = get_db()
    # Get transactions from last 30 days grouped by date
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    transactions = await db.payment_transactions.find(
        {"payment_status": "paid", "created_at": {"$gte": thirty_days_ago.isoformat()}},
        {"_id": 0, "amount": 1, "created_at": 1}
    ).to_list(1000)
    
    # Group by date
    daily_revenue = {}
    for tx in transactions:
        date = tx["created_at"][:10]
        daily_revenue[date] = daily_revenue.get(date, 0) + tx.get("amount", 0)
    
    return [{"date": date, "revenue": revenue} for date, revenue in sorted(daily_revenue.items())]



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
        query["$or"] = [
            {"listing_title": {"$regex": search, "$options": "i"}},
            {"buyer_email": {"$regex": search, "$options": "i"}},
            {"seller_email": {"$regex": search, "$options": "i"}},
            {"partner_company": {"$regex": search, "$options": "i"}},
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
        query["$or"] = [
            {"listing_title": {"$regex": search, "$options": "i"}},
            {"buyer_email": {"$regex": search, "$options": "i"}},
            {"seller_email": {"$regex": search, "$options": "i"}},
            {"partner_company": {"$regex": search, "$options": "i"}},
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
    return {"success": True, "message": f"User and all related data deleted.", "deleted": deleted}




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
            "total_promoted": sum(1 for l in listings if l.get("is_promoted")),
            "premium_count": sum(1 for l in listings if l.get("promotion_tier") == "premium"),
            "elite_count": sum(1 for l in listings if l.get("promotion_tier") == "elite"),
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
    """Admin: Permanently delete a single listing."""
    db = get_db()
    result = await db.listings.delete_one({"id": listing_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Listing not found")
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "listing_deleted",
        "admin_id": current_user.id, "target_id": listing_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "message": "Listing deleted permanently"}


@admin_ops_router.delete("/admin/multi-item-listings/{listing_id}")
async def admin_delete_multi_item_listing(listing_id: str, current_user: User = Depends(require_admin)):
    """Admin: Permanently delete a multi-item listing and its lots."""
    db = get_db()
    result = await db.multi_item_listings.delete_one({"id": listing_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Multi-item listing not found")
    await db.lots.delete_many({"listing_id": listing_id})
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "multi_item_listing_deleted",
        "admin_id": current_user.id, "target_id": listing_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    return {"success": True, "message": "Multi-item listing and lots deleted permanently"}


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
    "farm equipment", "farm_equipment", "tractors", "excavators",
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
