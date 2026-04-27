"""
BidVex - Miscellaneous Endpoints (Categories, Affiliate, Tracking, etc.)
Auto-extracted from server.py during P2 refactoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from deps import get_db, get_current_user, get_current_user_optional, User
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
    CurrencyAppeal,
)
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from pathlib import Path
import logging
import uuid
import os
import json as _json

logger = logging.getLogger(__name__)

from services.tax_engine import calculate_gst_qst

misc_router = APIRouter(tags=["Misc"])


@misc_router.get("/categories", response_model=List[Category])
async def get_categories():
    db = get_db()
    from services.api_cache import cache_get, cache_set, CATEGORIES_NS
    cache_key = f"{CATEGORIES_NS}all"
    cached = await cache_get(cache_key)
    if cached is not None:
        return cached
    categories = await db.categories.find({}, {"_id": 0}).to_list(100)
    result = [Category(**cat) for cat in categories]
    await cache_set(cache_key, result, 300)
    return result



@misc_router.post("/categories", response_model=Category)
async def create_category(category: Category, current_user: User = Depends(get_current_user)):
    db = get_db()
    cat_dict = category.model_dump()
    await db.categories.insert_one(cat_dict)
    return category




@misc_router.get("/config/google-maps-key")
async def get_google_maps_key():
    api_key = os.environ.get("GOOGLE_MAPS_API_KEY", "")
    if api_key and api_key != "your-google-maps-api-key-here":
        return {"api_key": api_key, "enabled": True}
    else:
        return {"api_key": "", "enabled": False}


@misc_router.get("/stats/public")
async def get_public_stats():
    """Lightweight public counter for the homepage hero. Returns 0 if nothing live.
    Cached at the DB layer is sufficient — this is one indexed count_documents call.
    """
    db = get_db()
    try:
        # Count active single-listing auctions + active multi-item lots
        single_active = await db.listings.count_documents({"status": "active"})
        multi_active = await db.multi_item_listings.count_documents({"status": "active"})
        return {
            "active_auctions": int(single_active + multi_active),
        }
    except Exception:
        return {"active_auctions": 0}




@misc_router.get("/affiliate/stats")
async def get_affiliate_stats(current_user: User = Depends(get_current_user)):
    db = get_db()
    referrals = await db.affiliate_referrals.find({"affiliate_id": current_user.id}, {"_id": 0}).to_list(1000)
    # Fallback to legacy referrals collection
    if not referrals:
        referrals = await db.referrals.find({"affiliate_id": current_user.id}, {"_id": 0}).to_list(1000)
    
    total_referrals = len(referrals)
    active_referrals = len([r for r in referrals if r.get("status") in ("active", "converted")])
    
    earnings = await db.affiliate_earnings.find({"affiliate_id": current_user.id}, {"_id": 0}).to_list(1000)
    total_earnings = sum(e.get("commission_amount", 0) for e in earnings)
    pending_earnings = sum(e.get("commission_amount", 0) for e in earnings if e.get("status") == "pending")
    paid_earnings = sum(e.get("commission_amount", 0) for e in earnings if e.get("status") in ("paid", "transferred"))
    
    frontend_url = os.environ.get('FRONTEND_URL', os.environ.get('REACT_APP_BACKEND_URL', 'http://localhost:3000'))
    
    return {
        "affiliate_code": current_user.affiliate_code,
        "referral_link": f"{frontend_url}/?ref={current_user.affiliate_code}",
        "total_referrals": total_referrals,
        "active_referrals": active_referrals,
        "total_earnings": total_earnings,
        "pending_earnings": pending_earnings,
        "paid_earnings": paid_earnings,
        "commission_rate": "10%",
        "commission_description": "10% of BidVex platform fees",
        "payout_delay_days": 7,
        "earnings_history": earnings,
        "referrals": referrals
    }



@misc_router.post("/affiliate/withdraw")
async def request_withdrawal(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    db = get_db()
    amount = data.get("amount")
    method = data.get("method", "bank_transfer")
    
    earnings = await db.affiliate_earnings.find({
        "affiliate_id": current_user.id,
        "status": "pending"
    }).to_list(1000)
    
    available = sum(e.get("commission_amount", 0) for e in earnings)
    
    if amount > available:
        raise HTTPException(status_code=400, detail="Insufficient balance")
    
    withdrawal_request = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "amount": amount,
        "method": method,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.withdrawal_requests.insert_one(withdrawal_request)
    
    return {"message": "Withdrawal request submitted", "request_id": withdrawal_request["id"]}




@misc_router.get("/admin/tax/pending")
async def get_pending_tax_verifications(current_user: User = Depends(get_current_user)):
    """Admin: Get all users with pending tax verification"""
    db = get_db()
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    users = await db.users.find({
        "tax_verification_status": {"$in": ["pending", "pending_manual_review"]},
        "tax_onboarding_completed": True
    }, {"_id": 0}).sort("created_at", -1).to_list(None)
    
    # Mask sensitive data for display
    for user in users:
        if user.get("tax_id"):
            # Mask SIN/BN - show only last 4 digits
            user["tax_id_masked"] = "****" + user["tax_id"][-4:] if len(user["tax_id"]) >= 4 else "****"
            del user["tax_id"]  # Remove actual value from response
    
    return users



@misc_router.get("/admin/tax/{user_id}")
async def get_user_tax_details(user_id: str, current_user: User = Depends(get_current_user)):
    """Admin: Get full tax details for a specific user (compliance officer only)"""
    db = get_db()
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Mask sensitive data unless super admin
    admin_email = os.environ.get('ADMIN_EMAIL', 'admin@bidvex.com')
    is_super_admin = current_user.role == "admin" and current_user.email == admin_email
    
    if not is_super_admin and user.get("tax_id"):
        user["tax_id_masked"] = "****" + user["tax_id"][-4:]
        del user["tax_id"]
    
    return user



@misc_router.post("/admin/tax/{user_id}/approve")
async def approve_tax_verification(
    user_id: str, 
    approval_data: dict,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Admin: Approve user's tax information"""
    db = get_db()
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "tax_verification_approved",
        "user_id": user_id,
        "user_email": user["email"],
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "admin_ip": request.client.host if request else "unknown",
        "notes": approval_data.get("notes", ""),
        "timestamp": datetime.now(timezone.utc),
        "before_status": user.get("tax_verification_status"),
        "after_status": "verified"
    }
    await db.tax_audit_logs.insert_one(audit_log)
    
    # Update user status
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "tax_verification_status": "verified",
            "tax_verified_at": datetime.now(timezone.utc),
            "tax_verified_by": current_user.id
        }}
    )
    
    # Send notification to user
    # TODO: Email notification
    
    return {"success": True, "message": "Tax information approved"}



@misc_router.post("/admin/tax/{user_id}/reject")
async def reject_tax_verification(
    user_id: str,
    rejection_data: dict,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Admin: Reject user's tax information"""
    db = get_db()
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if not rejection_data.get("reason"):
        raise HTTPException(status_code=422, detail="Rejection reason required")
    
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Create audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "tax_verification_rejected",
        "user_id": user_id,
        "user_email": user["email"],
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "admin_ip": request.client.host if request else "unknown",
        "rejection_reason": rejection_data.get("reason"),
        "notes": rejection_data.get("notes", ""),
        "timestamp": datetime.now(timezone.utc),
        "before_status": user.get("tax_verification_status"),
        "after_status": "rejected"
    }
    await db.tax_audit_logs.insert_one(audit_log)
    
    # Update user status
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "tax_verification_status": "rejected",
            "tax_rejection_reason": rejection_data.get("reason"),
            "tax_rejected_at": datetime.now(timezone.utc),
            "tax_rejected_by": current_user.id
        }}
    )
    
    # TODO: Email notification
    
    return {"success": True, "message": "Tax information rejected"}



@misc_router.post("/admin/tax/{user_id}/reset")
async def reset_tax_status(
    user_id: str,
    current_user: User = Depends(get_current_user),
    request: Request = None
):
    """Admin: Reset tax verification status to allow resubmission"""
    db = get_db()
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    # Audit log
    audit_log = {
        "id": str(uuid.uuid4()),
        "action": "tax_status_reset",
        "user_id": user_id,
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "timestamp": datetime.now(timezone.utc)
    }
    await db.tax_audit_logs.insert_one(audit_log)
    
    # Reset status
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "tax_verification_status": "pending",
            "tax_onboarding_completed": False
        }}
    )
    
    return {"success": True, "message": "Tax status reset - user can resubmit"}





@misc_router.get("/fee-calculator")
async def calculate_fees_endpoint(
    hammer_price: float,
    user_type: str = "buyer",  # "buyer" or "seller"
    current_user: User = Depends(get_current_user_optional)
):
    """
    Calculate fees for a given hammer price based on user's subscription tier.
    Returns detailed fee breakdown for transparency.
    NO CAP - Percentage-based fees only.
    """
    subscription_tier = current_user.subscription_tier if current_user else "free"
    
    if user_type == "buyer":
        fees = calculate_buyer_fees(hammer_price, subscription_tier)
        return {
            "user_type": "buyer",
            "hammer_price": hammer_price,
            "buyers_premium_percentage": fees.fee_percentage,
            "buyers_premium_amount": fees.fee_amount,
            "total_out_of_pocket": fees.total_amount,
            "is_premium_member": fees.is_premium_member,
            "discount_applied": fees.discount_applied,
            "standard_rate": "5%",
            "premium_rate": "3.5%",
            "vip_rate": "3%"
        }
    else:
        fees = calculate_seller_fees(hammer_price, subscription_tier)
        return {
            "user_type": "seller",
            "hammer_price": hammer_price,
            "commission_percentage": fees.fee_percentage,
            "commission_amount": fees.fee_amount,
            "net_payout": fees.total_amount,
            "is_premium_member": fees.is_premium_member,
            "discount_applied": fees.discount_applied,
            "standard_rate": "4%",
            "premium_rate": "2.5%",
            "vip_rate": "2%"
        }



@misc_router.get("/admin/affiliate/payouts")
async def admin_get_payout_requests(current_user: User = Depends(get_current_user)):
    db = get_db()
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    payouts = await db.payout_requests.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return payouts



@misc_router.put("/admin/affiliate/payouts/{payout_id}/approve")
async def admin_approve_payout(payout_id: str, current_user: User = Depends(get_current_user)):
    db = get_db()
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    await db.payout_requests.update_one({"id": payout_id}, {"$set": {"status": "approved"}})
    return {"message": "Payout approved"}



@misc_router.post("/promotions")
async def create_promotion(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    db = get_db()
    listing_id = data.get("listing_id")
    if not listing_id:
        raise HTTPException(status_code=400, detail="listing_id is required")
    
    # Verify listing exists and belongs to user
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    if listing["seller_id"] != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to promote this listing")
    
    promotion_id = str(uuid.uuid4())
    current_time = datetime.now(timezone.utc).isoformat()
    
    promotion_doc = {
        "id": promotion_id,
        "listing_id": listing_id,
        "seller_id": current_user.id,
        "promotion_type": data.get("promotion_type"),
        "price": data.get("price"),
        "start_date": current_time,
        "end_date": data.get("end_date"),
        "targeting": data.get("targeting", {}),
        "impressions": 0,
        "clicks": 0,
        "status": "pending",
        "payment_status": "pending",
        "created_at": current_time
    }
    
    await db.promotions.insert_one(promotion_doc)
    
    # Return a clean response without MongoDB fields
    return {
        "id": promotion_id,
        "listing_id": listing_id,
        "seller_id": current_user.id,
        "promotion_type": data.get("promotion_type"),
        "price": data.get("price"),
        "start_date": current_time,
        "end_date": data.get("end_date"),
        "targeting": data.get("targeting", {}),
        "impressions": 0,
        "clicks": 0,
        "status": "pending",
        "payment_status": "pending",
        "created_at": current_time
    }



@misc_router.get("/promotions/my")
async def get_my_promotions(current_user: User = Depends(get_current_user)):
    db = get_db()
    promotions = await db.promotions.find(
        {"seller_id": current_user.id},
        {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    return promotions



@misc_router.post("/tracking/view/{listing_id}")
async def track_listing_view(listing_id: str, current_user: User = Depends(get_current_user)):
    """Track a listing view for logged-in users"""
    db = get_db()
    try:
        # Check if listing exists
        listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        
        # Check if already viewed recently (within last 24 hours)
        recent_view = await db.recently_viewed.find_one({
            "user_id": current_user.id,
            "listing_id": listing_id
        })
        
        current_time = datetime.now(timezone.utc).isoformat()
        
        if recent_view:
            # Update timestamp
            await db.recently_viewed.update_one(
                {"user_id": current_user.id, "listing_id": listing_id},
                {"$set": {"viewed_at": current_time}}
            )
        else:
            # Add new view record
            view_record = {
                "id": str(uuid.uuid4()),
                "user_id": current_user.id,
                "listing_id": listing_id,
                "viewed_at": current_time
            }
            await db.recently_viewed.insert_one(view_record)
        
        return {"message": "View tracked", "success": True}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error tracking view: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to track view")



@misc_router.get("/tracking/recently-viewed")
async def get_recently_viewed(limit: int = 10, current_user: User = Depends(get_current_user)):
    """Get user's recently viewed listings"""
    db = get_db()
    try:
        # Get recently viewed records
        viewed_records = await db.recently_viewed.find(
            {"user_id": current_user.id},
            {"_id": 0}
        ).sort("viewed_at", -1).limit(limit).to_list(limit)
        
        if not viewed_records:
            return []
        
        # Get listing IDs
        listing_ids = [record["listing_id"] for record in viewed_records]
        
        # Fetch listing details
        listings = await db.listings.find(
            {"id": {"$in": listing_ids}, "status": {"$ne": "deleted"}},
            {"_id": 0}
        ).to_list(limit)
        
        # Create a map for quick lookup
        listings_map = {listing["id"]: listing for listing in listings}
        
        # Return listings in the order they were viewed
        result = []
        for record in viewed_records:
            listing = listings_map.get(record["listing_id"])
            if listing:
                result.append({
                    **listing,
                    "viewed_at": record["viewed_at"]
                })
        
        return result
        
    except Exception as e:
        logger.error(f"Error fetching recently viewed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch recently viewed")

# Carousel Data Endpoints


@misc_router.post("/currency-appeal")
async def submit_currency_appeal(
    requested_currency: str,
    reason: str,
    proof_documents: Optional[List[str]] = None,
    current_location: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Submit an appeal to change currency when it's locked
    
    Returns:
        Success message with appeal ID
    """
    db = get_db()
    if requested_currency not in ["CAD", "USD"]:
        raise HTTPException(status_code=400, detail="Currency must be 'CAD' or 'USD'")
    
    if not current_user.currency_locked:
        raise HTTPException(status_code=400, detail="Currency is not locked, you can change it directly")
    
    appeal = CurrencyAppeal(
        user_id=current_user.id,
        requested_currency=requested_currency,
        reason=reason,
        proof_documents=proof_documents or [],
        current_location=current_location
    )
    
    appeal_dict = appeal.model_dump()
    appeal_dict["submitted_at"] = appeal_dict["submitted_at"].isoformat()
    
    await db.currency_appeals.insert_one(appeal_dict)
    
    return {
        "success": True,
        "message": "Your appeal has been submitted and will be reviewed by our team within 24-48 hours.",
        "appeal_id": appeal.id
    }



@misc_router.get("/currency-appeals")
async def get_user_appeals(current_user: User = Depends(get_current_user)):
    """Get all appeals for current user"""
    db = get_db()
    appeals = await db.currency_appeals.find(
        {"user_id": current_user.id},
        {"_id": 0}
    ).sort("submitted_at", -1).to_list(10)
    
    return {"appeals": appeals}



@misc_router.post("/admin/currency-appeals/{appeal_id}/review")
async def review_currency_appeal(
    appeal_id: str,
    status: str,
    admin_notes: Optional[str] = None,
    current_user: User = Depends(get_current_user)
):
    """
    Admin endpoint to review and approve/reject currency appeals
    
    Args:
        appeal_id: The appeal ID to review
        status: 'approved' or 'rejected'
        admin_notes: Optional notes from admin
        
    Returns:
        Success message
    """
    db = get_db()
    if getattr(current_user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if status not in ["approved", "rejected"]:
        raise HTTPException(status_code=400, detail="Status must be 'approved' or 'rejected'")
    
    appeal = await db.currency_appeals.find_one({"id": appeal_id})
    if not appeal:
        raise HTTPException(status_code=404, detail="Appeal not found")
    
    # Update appeal status
    await db.currency_appeals.update_one(
        {"id": appeal_id},
        {
            "$set": {
                "status": status,
                "admin_notes": admin_notes,
                "reviewed_at": datetime.now(timezone.utc).isoformat()
            }
        }
    )
    
    # If approved, unlock currency and update user
    if status == "approved":
        await db.users.update_one(
            {"id": appeal['user_id']},
            {
                "$set": {
                    "preferred_currency": appeal['requested_currency'],
                    "enforced_currency": appeal['requested_currency'],
                    "currency_locked": False
                }
            }
        )
    
    return {
        "success": True,
        "message": f"Appeal {status}",
        "appeal_id": appeal_id
    }



@misc_router.get("/multi-item-listings/{listing_id}/increment-info")
async def get_increment_info(listing_id: str):
    """Get increment information for an auction"""
    db = get_db()
    try:
        listing = await db.multi_item_listings.find_one({"id": listing_id})
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")
        
        increment_option = listing.get("increment_option", "tiered")
        
        # Get increment schedule
        if increment_option == "simplified":
            schedule = [
                {"range": "$0-$100", "increment": "$1"},
                {"range": "$100-$1,000", "increment": "$5"},
                {"range": "$1,000-$10,000", "increment": "$25"},
                {"range": "$10,000+", "increment": "$100"}
            ]
        else:
            schedule = [
                {"range": "$0-$99.99", "increment": "$5"},
                {"range": "$100-$499.99", "increment": "$10"},
                {"range": "$500-$999.99", "increment": "$25"},
                {"range": "$1,000-$4,999.99", "increment": "$50"},
                {"range": "$5,000-$9,999.99", "increment": "$100"},
                {"range": "$10,000-$49,999.99", "increment": "$250"},
                {"range": "$50,000-$99,999.99", "increment": "$500"},
                {"range": "$100,000+", "increment": "$1,000"}
            ]
        
        return {
            "increment_option": increment_option,
            "schedule": schedule
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



@misc_router.get("/checkout/fee-breakdown")
async def checkout_fee_breakdown(
    listing_id: str,
    current_user: User = Depends(get_current_user)
):
    """
    Get the full fee breakdown for a listing checkout.
    Auto-detects partner vs standard listing and applies correct fee model.
    """
    db = get_db()
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    hammer_price = listing.get("current_price", 0)
    is_partner = listing.get("is_partner_listing", False)
    
    if is_partner:
        custom_rate = listing.get("custom_buyer_premium_rate", 0.0) or 0.0
        breakdown = calculate_partner_checkout(hammer_price, custom_rate)
        breakdown["fee_model"] = "partner"
    else:
        # Get buyer's subscription tier for discount
        buyer_doc = await db.users.find_one({"id": current_user.id})
        buyer_tier = buyer_doc.get("subscription_tier", "free") if buyer_doc else "free"
        breakdown = calculate_standard_checkout(hammer_price, buyer_tier)
        breakdown["fee_model"] = "standard"
    
    return breakdown



