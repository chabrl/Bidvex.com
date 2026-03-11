"""
BidVex Users Router
Handles user profile, ratings, seller profiles, and user data management
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import logging
import uuid
import os

from models.user_models import UpdateUserTaxInfo, DEFAULT_USER_TAX_FIELDS

logger = logging.getLogger(__name__)

users_router = APIRouter(prefix="/users", tags=["Users"])
security = HTTPBearer(auto_error=False)

# Database instance (injected from main app)
_db = None
_get_current_user = None


def set_users_db(db_instance):
    """Set database instance from main app"""
    global _db
    _db = db_instance


def set_users_auth(get_current_user_func):
    """Set authentication function from main app"""
    global _get_current_user
    _get_current_user = get_current_user_func


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


# ========== USER PROFILE ENDPOINTS ==========

@users_router.get("/{user_id}")
async def get_user(user_id: str):
    """Get user by ID"""
    db = get_db()
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


@users_router.get("/{user_id}/profile-summary")
async def get_user_profile_summary(user_id: str):
    """Get public profile summary for a user"""
    db = get_db()
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Get seller stats
    listings_count = await db.listings.count_documents({"seller_id": user_id})
    sold_count = await db.listings.count_documents({"seller_id": user_id, "status": "sold"})
    
    # Get ratings
    ratings = await db.ratings.find({"seller_id": user_id}).to_list(100)
    avg_rating = sum(r.get("rating", 0) for r in ratings) / len(ratings) if ratings else 0
    
    # Check privacy settings
    privacy = user.get("privacy_settings", {})
    
    return {
        "id": user["id"],
        "name": user.get("name", "Anonymous"),
        "picture": user.get("picture"),
        "account_type": user.get("account_type", "personal"),
        "member_since": user.get("created_at"),
        "email": user.get("email") if privacy.get("show_email", False) else None,
        "phone": user.get("phone") if privacy.get("show_phone", False) else None,
        "address": user.get("address") if privacy.get("show_address", False) else None,
        "bio": user.get("bio"),
        "listings_count": listings_count,
        "sold_count": sold_count,
        "rating": round(avg_rating, 1),
        "ratings_count": len(ratings),
        "admin_verified": user.get("admin_verified", False),
        "subscription_tier": user.get("subscription_tier", "free")
    }


@users_router.put("/me")
async def update_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update current user's profile"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    data = await request.json()
    allowed_fields = [
        "name", "phone", "address", "company_name", "preferred_language",
        "preferred_currency", "bio", "bio_fr", "picture", "privacy_settings"
    ]
    
    update_data = {k: v for k, v in data.items() if k in allowed_fields}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": update_data}
    )
    
    updated_user = await db.users.find_one(
        {"id": current_user.id},
        {"_id": 0, "password_hash": 0}
    )
    
    return updated_user


@users_router.get("/me/stats")
async def get_user_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get current user's statistics"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    user_id = current_user.id
    
    # Get various stats
    listings_count = await db.listings.count_documents({"seller_id": user_id})
    active_listings = await db.listings.count_documents({"seller_id": user_id, "status": "active"})
    sold_listings = await db.listings.count_documents({"seller_id": user_id, "status": "sold"})
    
    bids_placed = await db.bids.count_documents({"bidder_id": user_id})
    auctions_won = await db.listings.count_documents({"winning_bidder_id": user_id})
    
    # Calculate total sales
    sold = await db.listings.find(
        {"seller_id": user_id, "status": "sold"},
        {"current_price": 1}
    ).to_list(None)
    total_sales = sum(l.get("current_price", 0) for l in sold)
    
    return {
        "listings": {
            "total": listings_count,
            "active": active_listings,
            "sold": sold_listings
        },
        "bidding": {
            "bids_placed": bids_placed,
            "auctions_won": auctions_won
        },
        "financials": {
            "total_sales": total_sales
        }
    }


# ========== RATINGS ENDPOINTS ==========

class RatingCreate(BaseModel):
    seller_id: str
    listing_id: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None


@users_router.post("/ratings")
async def create_rating(
    rating_data: RatingCreate,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a rating for a seller"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    # Check if already rated
    existing = await db.ratings.find_one({
        "buyer_id": current_user.id,
        "listing_id": rating_data.listing_id
    })
    if existing:
        raise HTTPException(status_code=400, detail="You have already rated this transaction")
    
    rating = {
        "id": str(uuid.uuid4()),
        "seller_id": rating_data.seller_id,
        "buyer_id": current_user.id,
        "buyer_name": current_user.name,
        "listing_id": rating_data.listing_id,
        "rating": rating_data.rating,
        "comment": rating_data.comment,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.ratings.insert_one(rating)
    return {k: v for k, v in rating.items() if k != "_id"}


@users_router.get("/{user_id}/ratings")
async def get_user_ratings(user_id: str, limit: int = 20, skip: int = 0):
    """Get ratings for a user (as seller)"""
    db = get_db()
    
    ratings = await db.ratings.find(
        {"seller_id": user_id},
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    total = await db.ratings.count_documents({"seller_id": user_id})
    
    # Calculate average
    all_ratings = await db.ratings.find({"seller_id": user_id}, {"rating": 1}).to_list(None)
    avg_rating = sum(r.get("rating", 0) for r in all_ratings) / len(all_ratings) if all_ratings else 0
    
    return {
        "ratings": ratings,
        "total": total,
        "average": round(avg_rating, 1)
    }


# ========== SELLER PROFILE ENDPOINTS ==========

@users_router.get("/sellers/{seller_id}/trust-score")
async def get_seller_trust_score(seller_id: str):
    """Get trust score breakdown for a seller"""
    db = get_db()
    
    user = await db.users.find_one({"id": seller_id})
    if not user:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # Calculate components
    ratings = await db.ratings.find({"seller_id": seller_id}).to_list(None)
    avg_rating = sum(r.get("rating", 0) for r in ratings) / len(ratings) if ratings else 0
    
    completed_sales = await db.listings.count_documents({
        "seller_id": seller_id,
        "status": "sold"
    })
    
    # Trust score formula
    rating_score = (avg_rating / 5) * 40  # 40% weight
    volume_score = min(completed_sales / 100, 1) * 30  # 30% weight, max at 100 sales
    verification_score = (
        (10 if user.get("email_verified") else 0) +
        (10 if user.get("phone_verified") else 0) +
        (10 if user.get("admin_verified") else 0)
    )  # 30% weight
    
    total_score = rating_score + volume_score + verification_score
    
    return {
        "seller_id": seller_id,
        "total_score": round(total_score, 1),
        "components": {
            "rating": round(rating_score, 1),
            "volume": round(volume_score, 1),
            "verification": round(verification_score, 1)
        },
        "details": {
            "average_rating": round(avg_rating, 1),
            "total_ratings": len(ratings),
            "completed_sales": completed_sales,
            "email_verified": user.get("email_verified", False),
            "phone_verified": user.get("phone_verified", False),
            "admin_verified": user.get("admin_verified", False)
        }
    }


@users_router.get("/sellers/{seller_id}")
async def get_seller_profile(seller_id: str):
    """Get public seller profile"""
    db = get_db()
    
    user = await db.users.find_one({"id": seller_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # Get stats
    listings = await db.listings.find({"seller_id": seller_id}).to_list(None)
    active = [l for l in listings if l.get("status") == "active"]
    sold = [l for l in listings if l.get("status") == "sold"]
    
    # Get ratings
    ratings = await db.ratings.find({"seller_id": seller_id}).to_list(None)
    avg_rating = sum(r.get("rating", 0) for r in ratings) / len(ratings) if ratings else 0
    
    privacy = user.get("privacy_settings", {})
    
    return {
        "id": user["id"],
        "name": user.get("name", "Anonymous"),
        "picture": user.get("picture"),
        "account_type": user.get("account_type", "personal"),
        "company_name": user.get("company_name") if user.get("account_type") == "business" else None,
        "bio": user.get("bio"),
        "member_since": user.get("created_at"),
        "email": user.get("email") if privacy.get("show_email", False) else None,
        "phone": user.get("phone") if privacy.get("show_phone", False) else None,
        "location": user.get("address") if privacy.get("show_address", False) else None,
        "stats": {
            "total_listings": len(listings),
            "active_listings": len(active),
            "sold_items": len(sold),
            "average_rating": round(avg_rating, 1),
            "total_ratings": len(ratings)
        },
        "verification": {
            "email_verified": user.get("email_verified", False),
            "phone_verified": user.get("phone_verified", False),
            "admin_verified": user.get("admin_verified", False)
        },
        "subscription_tier": user.get("subscription_tier", "free")
    }


@users_router.get("/sellers/{seller_id}/listings")
async def get_seller_listings(
    seller_id: str,
    status: Optional[str] = None,
    limit: int = 20,
    skip: int = 0
):
    """Get listings from a specific seller"""
    db = get_db()
    
    query = {"seller_id": seller_id}
    if status:
        query["status"] = status
    
    listings = await db.listings.find(
        query,
        {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    
    total = await db.listings.count_documents(query)
    
    return {
        "listings": listings,
        "total": total
    }


# ========== DATA PRIVACY ENDPOINTS ==========

@users_router.post("/request-data-deletion")
async def request_data_deletion(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Request GDPR-compliant data deletion"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    data = await request.json()
    
    # Check if request already exists
    existing = await db.data_deletion_requests.find_one({
        "user_id": current_user.id,
        "status": {"$in": ["pending", "processing"]}
    })
    if existing:
        raise HTTPException(status_code=400, detail="A deletion request is already in progress")
    
    deletion_request = {
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "user_email": current_user.email,
        "reason": data.get("reason", ""),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scheduled_deletion_date": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()
    }
    
    await db.data_deletion_requests.insert_one(deletion_request)
    
    return {
        "status": "success",
        "message": "Data deletion request submitted. Your data will be deleted in 30 days.",
        "request_id": deletion_request["id"],
        "scheduled_deletion_date": deletion_request["scheduled_deletion_date"]
    }


@users_router.get("/data-deletion-status")
async def get_data_deletion_status(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get status of data deletion request"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    request = await db.data_deletion_requests.find_one(
        {"user_id": current_user.id},
        {"_id": 0}
    )
    
    if not request:
        return {"status": "none", "message": "No deletion request found"}
    
    return request


@users_router.post("/cancel-data-deletion")
async def cancel_data_deletion(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Cancel pending data deletion request"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    result = await db.data_deletion_requests.update_one(
        {"user_id": current_user.id, "status": "pending"},
        {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="No pending deletion request found")
    
    return {"status": "success", "message": "Data deletion request cancelled"}


@users_router.get("/export-data")
async def export_user_data(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Export all user data (GDPR compliance)"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    user_id = current_user.id
    
    # Gather all user data
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    listings = await db.listings.find({"seller_id": user_id}, {"_id": 0}).to_list(None)
    bids = await db.bids.find({"bidder_id": user_id}, {"_id": 0}).to_list(None)
    messages = await db.messages.find(
        {"$or": [{"sender_id": user_id}, {"recipient_id": user_id}]},
        {"_id": 0}
    ).to_list(None)
    ratings_given = await db.ratings.find({"buyer_id": user_id}, {"_id": 0}).to_list(None)
    ratings_received = await db.ratings.find({"seller_id": user_id}, {"_id": 0}).to_list(None)
    
    return {
        "export_date": datetime.now(timezone.utc).isoformat(),
        "user_profile": user,
        "listings": listings,
        "bids": bids,
        "messages": messages,
        "ratings_given": ratings_given,
        "ratings_received": ratings_received
    }


# ========== SELLER TAX & BUSINESS INFO ENDPOINTS ==========

@users_router.get("/me/tax-info")
async def get_my_tax_info(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get current user's tax and business registration info"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    user = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    
    return {
        "is_business": user.get("is_business", False),
        "is_tax_registered": user.get("is_tax_registered", False),
        "tax_id": user.get("tax_id"),
        "business_name": user.get("business_name"),
        "business_address": user.get("business_address"),
        "account_type": user.get("account_type", "personal"),
        "stripe_connect_account_id": user.get("stripe_connect_account_id"),
        "stripe_connect_onboarding_complete": user.get("stripe_connect_onboarding_complete", False)
    }


@users_router.put("/me/tax-info")
async def update_my_tax_info(
    tax_info: UpdateUserTaxInfo,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Update current user's tax and business registration info"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    # Build update dict with only provided fields
    update_data = {}
    
    if tax_info.is_business is not None:
        update_data["is_business"] = tax_info.is_business
        update_data["account_type"] = "business" if tax_info.is_business else "personal"
    
    if tax_info.is_tax_registered is not None:
        update_data["is_tax_registered"] = tax_info.is_tax_registered
    
    if tax_info.tax_id is not None:
        update_data["tax_id"] = tax_info.tax_id
    
    if tax_info.business_name is not None:
        update_data["business_name"] = tax_info.business_name
    
    if tax_info.business_address is not None:
        update_data["business_address"] = tax_info.business_address
    
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": update_data}
        )
    
    # Return updated info
    return await get_my_tax_info(credentials)


# ========== STRIPE CONNECT ENDPOINTS ==========

@users_router.post("/me/stripe-connect/onboard")
async def create_stripe_connect_account(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create or retrieve Stripe Connect account and generate onboarding link
    
    This enables sellers to receive payouts via Stripe Connect destination charges.
    """
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    user = await db.users.find_one({"id": current_user.id})
    
    # Check if user already has a Connect account
    connect_account_id = user.get("stripe_connect_account_id")
    
    if not connect_account_id:
        # Create new Connect account
        account = stripe.Account.create(
            type="express",
            country="CA",
            email=current_user.email,
            capabilities={
                "card_payments": {"requested": True},
                "transfers": {"requested": True}
            },
            business_type="individual",
            metadata={
                "user_id": current_user.id,
                "platform": "bidvex"
            }
        )
        connect_account_id = account.id
        
        # Save to database
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {
                "stripe_connect_account_id": connect_account_id,
                "stripe_connect_onboarding_complete": False,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
    
    # Generate onboarding link
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "https://bidvex.com")
    
    account_link = stripe.AccountLink.create(
        account=connect_account_id,
        refresh_url=f"{base_url}/seller/settings?stripe_refresh=true",
        return_url=f"{base_url}/seller/settings?stripe_onboard=success",
        type="account_onboarding"
    )
    
    return {
        "connect_account_id": connect_account_id,
        "onboarding_url": account_link.url,
        "expires_at": datetime.fromtimestamp(account_link.expires_at, tz=timezone.utc).isoformat()
    }


@users_router.get("/me/stripe-connect/status")
async def get_stripe_connect_status(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get Stripe Connect account status and capabilities
    """
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    user = await db.users.find_one({"id": current_user.id})
    connect_account_id = user.get("stripe_connect_account_id")
    
    if not connect_account_id:
        return {
            "has_account": False,
            "onboarding_complete": False,
            "payouts_enabled": False,
            "charges_enabled": False
        }
    
    try:
        account = stripe.Account.retrieve(connect_account_id)
        
        # Update onboarding status in database if changed
        if account.details_submitted and not user.get("stripe_connect_onboarding_complete"):
            await db.users.update_one(
                {"id": current_user.id},
                {"$set": {
                    "stripe_connect_onboarding_complete": True,
                    "updated_at": datetime.now(timezone.utc).isoformat()
                }}
            )
        
        return {
            "has_account": True,
            "account_id": connect_account_id,
            "onboarding_complete": account.details_submitted,
            "payouts_enabled": account.payouts_enabled,
            "charges_enabled": account.charges_enabled,
            "capabilities": {
                "card_payments": account.capabilities.get("card_payments", "inactive"),
                "transfers": account.capabilities.get("transfers", "inactive")
            },
            "requirements": {
                "currently_due": list(account.requirements.currently_due) if account.requirements else [],
                "eventually_due": list(account.requirements.eventually_due) if account.requirements else []
            }
        }
    except stripe.StripeError as e:
        logger.error(f"Stripe Connect status error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@users_router.post("/me/stripe-connect/dashboard-link")
async def get_stripe_connect_dashboard_link(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Generate a login link to the Stripe Express Dashboard
    """
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    user = await db.users.find_one({"id": current_user.id})
    connect_account_id = user.get("stripe_connect_account_id")
    
    if not connect_account_id:
        raise HTTPException(status_code=400, detail="No Stripe Connect account found. Please complete onboarding first.")
    
    try:
        login_link = stripe.Account.create_login_link(connect_account_id)
        return {"dashboard_url": login_link.url}
    except stripe.StripeError as e:
        logger.error(f"Stripe dashboard link error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

