"""
BidVex Profiles Router
User profile management, seller profiles, ratings, tax info,
Stripe Connect onboarding, and GDPR data management.
"""

from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
import uuid
import os
import logging
import stripe

logger = logging.getLogger(__name__)

profiles_router = APIRouter(tags=["Profiles"])
security = HTTPBearer(auto_error=False)

_db = None
_get_current_user = None


def set_profiles_db(db_instance):
    global _db
    _db = db_instance


def set_profiles_auth(get_current_user_func):
    global _get_current_user

    async def wrapper(credentials):
        class MockRequest:
            cookies = {}
        return await get_current_user_func(MockRequest(), credentials)

    _get_current_user = wrapper


def get_db():
    return _db


async def _require_auth(credentials):
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    return await _get_current_user(credentials)


# ========== MODELS ==========


class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    company_name: Optional[str] = None
    tax_number: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    language: Optional[str] = None
    picture: Optional[str] = None
    personalized_recommendations: Optional[bool] = None


class AuctionRating(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    auction_id: str
    auction_type: str
    rater_user_id: str
    target_user_id: str
    rating: int = Field(ge=1, le=5)
    comment: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ========== USER LOOKUP ==========


@profiles_router.get("/users/{user_id}")
async def get_user(user_id: str):
    from deps import User
    user_doc = await _db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    if isinstance(user_doc.get("created_at"), str):
        user_doc["created_at"] = datetime.fromisoformat(user_doc["created_at"])
    return User(**user_doc)


@profiles_router.get("/users/{user_id}/profile-summary")
async def get_user_profile_summary(user_id: str):
    """Get auctioneer profile summary for display on auction cards."""
    try:
        user_doc = await _db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user_doc:
            raise HTTPException(status_code=404, detail="User not found")

        total_single = await _db.listings.count_documents({"seller_id": user_id})
        total_lots = await _db.multi_item_listings.count_documents({"seller_id": user_id})

        completed_single = await _db.listings.count_documents(
            {"seller_id": user_id, "status": {"$in": ["sold", "ended"]}}
        )
        completed_lots = await _db.multi_item_listings.count_documents(
            {"seller_id": user_id, "status": {"$in": ["ended", "completed"]}}
        )

        return {
            "user_id": user_id,
            "name": user_doc.get("name", "Anonymous"),
            "picture": user_doc.get("picture"),
            "company_name": user_doc.get("company_name"),
            "account_type": user_doc.get("account_type", "personal"),
            "city": user_doc.get("address", "").split(",")[0] if user_doc.get("address") else None,
            "subscription_tier": user_doc.get("subscription_tier", "free"),
            "is_tax_registered": user_doc.get("is_tax_registered", False),
            "stats": {
                "total_auctions": total_single + total_lots,
                "completed_auctions": completed_single + completed_lots,
                "member_since": user_doc.get("created_at"),
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching profile summary: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch profile summary")


# ========== PROFILE UPDATE ==========


@profiles_router.put("/users/me")
async def update_user_me(
    updates: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Update current user's profile.
    Validates preferred_language (en/fr), bio length, privacy settings, currency lock.
    """
    current_user = await _require_auth(credentials)

    allowed_fields = [
        "name", "phone", "address", "company_name", "tax_number",
        "bank_details", "language", "picture", "preferred_language",
        "preferred_currency", "subscription_tier", "bio", "bio_fr",
        "privacy_settings", "personalized_recommendations",
    ]
    update_data = {k: v for k, v in updates.items() if k in allowed_fields}

    if "bio" in update_data and update_data["bio"] and len(update_data["bio"]) > 500:
        raise HTTPException(status_code=400, detail="Bio must be 500 characters or less")
    if "bio_fr" in update_data and update_data["bio_fr"] and len(update_data["bio_fr"]) > 500:
        raise HTTPException(status_code=400, detail="French bio must be 500 characters or less")

    if "privacy_settings" in update_data:
        if not isinstance(update_data["privacy_settings"], dict):
            raise HTTPException(status_code=400, detail="Privacy settings must be an object")
        valid_keys = {"show_email", "show_phone", "show_address"}
        if not all(k in valid_keys for k in update_data["privacy_settings"].keys()):
            raise HTTPException(status_code=400, detail="Invalid privacy setting keys")

    if "preferred_language" in update_data and update_data["preferred_language"] not in ["en", "fr"]:
        raise HTTPException(status_code=400, detail="Language must be 'en' or 'fr'")

    if "preferred_currency" in update_data:
        if update_data["preferred_currency"] not in ["CAD", "USD"]:
            raise HTTPException(status_code=400, detail="Currency must be 'CAD' or 'USD'")
        if current_user.currency_locked and update_data["preferred_currency"] != current_user.enforced_currency:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "currency_locked",
                    "message": "Currency is determined by your location to comply with local tax rules.",
                    "enforced_currency": current_user.enforced_currency,
                    "appeal_link": "/api/currency-appeal",
                },
            )

    if "subscription_tier" in update_data:
        if update_data["subscription_tier"] not in ["free", "premium", "vip"]:
            raise HTTPException(status_code=400, detail="Subscription tier must be 'free', 'premium', or 'vip'")

    if update_data:
        await _db.users.update_one({"id": current_user.id}, {"$set": update_data})
    return {"message": "Profile updated successfully"}


@profiles_router.put("/profile")
async def update_profile_model(
    updates: ProfileUpdate,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Update profile via ProfileUpdate model (name, phone, picture, etc.)."""
    current_user = await _require_auth(credentials)
    update_data = {k: v for k, v in updates.model_dump().items() if v is not None}
    if update_data:
        await _db.users.update_one({"id": current_user.id}, {"$set": update_data})
    updated_user = await _db.users.find_one({"id": current_user.id}, {"_id": 0, "password": 0})
    return updated_user


# ========== USER STATS ==========


@profiles_router.get("/users/me/stats")
async def get_user_stats(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get user's 12-month transaction statistics."""
    current_user = await _require_auth(credentials)
    try:
        twelve_months_ago = datetime.now(timezone.utc) - timedelta(days=365)

        user_bids = await _db.bids.find(
            {"bidder_id": current_user.id, "created_at": {"$gte": twelve_months_ago.isoformat()}},
            {"_id": 0},
        ).to_list(1000)

        total_bid_volume = sum(bid.get("amount", 0) for bid in user_bids)

        user_purchases = await _db.transactions.find(
            {"buyer_id": current_user.id, "status": "completed", "created_at": {"$gte": twelve_months_ago.isoformat()}},
            {"_id": 0},
        ).to_list(500)

        total_purchase_volume = sum(t.get("amount", 0) for t in user_purchases)
        annual_volume = max(total_bid_volume, total_purchase_volume, 0)

        if annual_volume == 0:
            annual_volume = 10000  # Default estimate for active users

        return {
            "annual_volume": annual_volume,
            "total_bids": len(user_bids),
            "auctions_won": len(user_purchases),
            "total_purchase_volume": total_purchase_volume,
            "period": "last_12_months",
        }
    except Exception as e:
        logger.warning(f"Failed to get user stats: {e}")
        return {"annual_volume": 0, "total_bids": 0, "auctions_won": 0, "total_purchase_volume": 0, "period": "last_12_months"}


# ========== RATINGS ==========


@profiles_router.post("/ratings")
async def create_rating(
    rating_data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Create a rating for a seller/auctioneer (one per auction per buyer)."""
    current_user = await _require_auth(credentials)
    try:
        for field in ["auction_id", "auction_type", "target_user_id", "rating"]:
            if field not in rating_data:
                raise HTTPException(status_code=400, detail=f"Missing required field: {field}")

        if not (1 <= rating_data["rating"] <= 5):
            raise HTTPException(status_code=400, detail="Rating must be between 1 and 5")
        if rating_data["auction_type"] not in ["single", "multi"]:
            raise HTTPException(status_code=400, detail="Auction type must be 'single' or 'multi'")

        existing = await _db.ratings.find_one(
            {"auction_id": rating_data["auction_id"], "rater_user_id": current_user.id}
        )
        if existing:
            raise HTTPException(status_code=400, detail="You have already rated this auction")

        if rating_data["auction_type"] == "single":
            auction = await _db.listings.find_one({"id": rating_data["auction_id"]})
            bid_coll = "listing_id"
        else:
            auction = await _db.multi_item_listings.find_one({"id": rating_data["auction_id"]})
            bid_coll = "multi_item_listing_id"

        if not auction:
            raise HTTPException(status_code=404, detail="Auction not found")

        user_bid = await _db.bids.find_one({bid_coll: rating_data["auction_id"], "bidder_id": current_user.id})
        if not user_bid:
            raise HTTPException(status_code=403, detail="You must participate in the auction to rate it")

        if current_user.id == rating_data["target_user_id"]:
            raise HTTPException(status_code=400, detail="You cannot rate yourself")

        rating = AuctionRating(
            auction_id=rating_data["auction_id"],
            auction_type=rating_data["auction_type"],
            rater_user_id=current_user.id,
            target_user_id=rating_data["target_user_id"],
            rating=rating_data["rating"],
            comment=rating_data.get("comment"),
        )

        rating_dict = rating.model_dump()
        rating_dict["timestamp"] = rating_dict["timestamp"].isoformat()
        rating_dict["created_at"] = rating_dict["created_at"].isoformat()
        await _db.ratings.insert_one(rating_dict)

        return {"message": "Rating submitted successfully", "rating": rating_dict}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating rating: {e}")
        raise HTTPException(status_code=500, detail="Failed to create rating")


@profiles_router.get("/users/{user_id}/ratings")
async def get_user_ratings(user_id: str):
    """Get aggregated ratings for a user."""
    try:
        ratings = await _db.ratings.find({"target_user_id": user_id}).to_list(length=None)

        if not ratings:
            return {
                "user_id": user_id,
                "average_rating": 0,
                "total_ratings": 0,
                "ratings_breakdown": {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0},
                "recent_ratings": [],
            }

        average_rating = round(sum(r["rating"] for r in ratings) / len(ratings), 2)
        breakdown = {"1": 0, "2": 0, "3": 0, "4": 0, "5": 0}
        for r in ratings:
            breakdown[str(r["rating"])] += 1

        recent = sorted(ratings, key=lambda x: x.get("timestamp", ""), reverse=True)[:10]
        for r in recent:
            r.pop("_id", None)
            r.pop("rater_user_id", None)

        return {
            "user_id": user_id,
            "average_rating": average_rating,
            "total_ratings": len(ratings),
            "ratings_breakdown": breakdown,
            "recent_ratings": recent,
        }
    except Exception as e:
        logger.error(f"Error fetching ratings: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch ratings")


# ========== SELLER PROFILES & TRUST SCORE ==========


@profiles_router.get("/sellers/{seller_id}/trust-score")
async def get_seller_trust_score(seller_id: str):
    """Comprehensive trust score: automated metrics + buyer ratings."""
    try:
        ratings = await _db.ratings.find({"target_user_id": seller_id}).to_list(length=None)

        completed_transactions = await _db.handshakes.find(
            {"seller_id": seller_id, "status": "picked_up"}
        ).to_list(length=None)

        # Automated pickup speed
        pickup_scores = []
        for t in completed_transactions:
            if t.get("marked_picked_up_at") and t.get("auction_end_date"):
                try:
                    pickup = datetime.fromisoformat(t["marked_picked_up_at"].replace("Z", "+00:00"))
                    end = datetime.fromisoformat(t["auction_end_date"].replace("Z", "+00:00"))
                    days = (pickup - end).days
                    pickup_scores.append(5 if days <= 3 else 4 if days <= 7 else 3 if days <= 14 else 2)
                except Exception:
                    pass

        avg_pickup_speed = sum(pickup_scores) / len(pickup_scores) if pickup_scores else 0

        metrics = {"pickup_speed": [], "item_accuracy": [], "communication": []}
        for r in ratings:
            if r.get("metrics"):
                for key in metrics:
                    if r["metrics"].get(key):
                        metrics[key].append(r["metrics"][key])

        avg_item = sum(metrics["item_accuracy"]) / len(metrics["item_accuracy"]) if metrics["item_accuracy"] else 0
        avg_comm = sum(metrics["communication"]) / len(metrics["communication"]) if metrics["communication"] else 0
        final_pickup = sum(metrics["pickup_speed"]) / len(metrics["pickup_speed"]) if metrics["pickup_speed"] else avg_pickup_speed

        if ratings:
            overall_score = round(sum(r["rating"] for r in ratings) / len(ratings), 2)
        elif completed_transactions:
            overall_score = round(avg_pickup_speed, 2)
        else:
            overall_score = 0

        return {
            "seller_id": seller_id,
            "overall_score": overall_score,
            "total_ratings": len(ratings),
            "total_transactions": len(completed_transactions),
            "metrics": {
                "pickup_speed": round(final_pickup, 2),
                "item_accuracy": round(avg_item, 2),
                "communication": round(avg_comm, 2),
            },
            "is_trusted": overall_score >= 4.5,
            "badge": "BidVex Trusted Seller" if overall_score >= 4.5 else None,
        }
    except Exception as e:
        logger.error(f"Error calculating trust score: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate trust score")


@profiles_router.get("/sellers/{seller_id}")
async def get_seller_profile(
    seller_id: str,
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
):
    """Get seller profile with privacy-aware contact information."""
    from jose import jwt, JWTError

    try:
        current_user = None
        jwt_secret = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
        token = request.cookies.get("session_token") or (credentials.credentials if credentials else None)

        if token:
            try:
                payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
                uid = payload.get("sub")
                if uid:
                    from deps import User
                    user_doc = await _db.users.find_one({"id": uid}, {"_id": 0, "password": 0})
                    if user_doc:
                        if isinstance(user_doc.get("created_at"), str):
                            user_doc["created_at"] = datetime.fromisoformat(user_doc["created_at"])
                        current_user = User(**user_doc)
            except (JWTError, Exception):
                pass

        seller_doc = await _db.users.find_one({"id": seller_id}, {"_id": 0, "password": 0})
        if not seller_doc:
            raise HTTPException(status_code=404, detail="Seller not found")

        ratings = await _db.ratings.find({"target_user_id": seller_id}).to_list(length=None)
        avg_rating = round(sum(r["rating"] for r in ratings) / len(ratings), 2) if ratings else 0

        single_count = await _db.listings.count_documents({"seller_id": seller_id, "status": "active"})
        multi_count = await _db.multi_item_listings.count_documents({"seller_id": seller_id, "status": {"$in": ["active", "upcoming"]}})

        profile = {
            "id": seller_id,
            "name": seller_doc.get("name"),
            "company_name": seller_doc.get("company_name"),
            "account_type": seller_doc.get("account_type"),
            "picture": seller_doc.get("picture"),
            "bio": seller_doc.get("bio"),
            "bio_fr": seller_doc.get("bio_fr"),
            "subscription_tier": seller_doc.get("subscription_tier", "free"),
            "member_since": seller_doc.get("created_at"),
            "average_rating": avg_rating,
            "total_ratings": len(ratings),
            "total_active_listings": single_count + multi_count,
        }

        privacy = seller_doc.get("privacy_settings", {"show_email": True, "show_phone": True, "show_address": True})
        if current_user:
            if privacy.get("show_email", True):
                profile["email"] = seller_doc.get("email")
            if privacy.get("show_phone", True):
                profile["phone"] = seller_doc.get("phone")
            if privacy.get("show_address", True):
                profile["address"] = seller_doc.get("address")

        return profile

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching seller profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch seller profile")


# ========== TAX PROFILE ==========


@profiles_router.put("/users/me/tax-profile")
async def update_tax_profile(
    tax_data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Update user's tax profile for CRA/Revenu Quebec compliance."""
    current_user = await _require_auth(credentials)

    seller_type = tax_data.get("seller_type")
    if seller_type == "individual":
        for field in ["tax_id", "date_of_birth"]:
            if not tax_data.get(field):
                raise HTTPException(status_code=422, detail=f"Missing required field: {field}")
    elif seller_type == "business":
        for field in ["tax_id", "gst_number", "legal_business_name", "business_province"]:
            if not tax_data.get(field):
                raise HTTPException(status_code=422, detail=f"Missing required field: {field}")
        province = tax_data.get("business_province", "")
        if province in ["QC", "Quebec", "Québec"]:
            if not tax_data.get("neq_number"):
                raise HTTPException(status_code=422, detail="NEQ is required for Quebec businesses")
            if not tax_data.get("qst_number"):
                raise HTTPException(status_code=422, detail="QST registration number is required for Quebec businesses")

    update_data = {
        "seller_type": seller_type,
        "tax_id": tax_data.get("tax_id"),
        "tax_onboarding_completed": True,
        "tax_verification_status": "pending",
    }
    if seller_type == "individual":
        update_data.update({
            "date_of_birth": tax_data.get("date_of_birth"),
            "address": tax_data.get("address"),
            "is_tax_registered": False,
        })
    else:
        update_data.update({
            "neq_number": tax_data.get("neq_number"),
            "gst_number": tax_data.get("gst_number"),
            "qst_number": tax_data.get("qst_number"),
            "legal_business_name": tax_data.get("legal_business_name"),
            "registered_office_address": tax_data.get("registered_office_address"),
            "business_province": tax_data.get("business_province"),
            "is_tax_registered": True,
            "account_type": "business",
        })

    await _db.users.update_one({"id": current_user.id}, {"$set": update_data})
    return {"success": True, "message": "Tax profile updated successfully"}


@profiles_router.get("/users/me/tax-info")
async def get_my_tax_info(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get current user's tax and business registration info."""
    current_user = await _require_auth(credentials)
    user = await _db.users.find_one({"id": current_user.id}, {"_id": 0})
    return {
        "is_business": user.get("is_business", False),
        "is_tax_registered": user.get("is_tax_registered", False),
        "tax_id": user.get("tax_id"),
        "business_name": user.get("business_name"),
        "business_address": user.get("business_address"),
        "account_type": user.get("account_type", "personal"),
        "stripe_connect_account_id": user.get("stripe_connect_account_id"),
        "stripe_connect_onboarding_complete": user.get("stripe_connect_onboarding_complete", False),
    }


@profiles_router.put("/users/me/tax-info")
async def update_my_tax_info(
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Update current user's tax and business registration info."""
    current_user = await _require_auth(credentials)
    update_data = {}
    if "is_business" in data:
        update_data["is_business"] = data["is_business"]
        update_data["account_type"] = "business" if data["is_business"] else "personal"
    for field in ["is_tax_registered", "tax_id", "business_name", "business_address"]:
        if field in data:
            update_data[field] = data[field]
    if update_data:
        update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        await _db.users.update_one({"id": current_user.id}, {"$set": update_data})
    return await get_my_tax_info(credentials)


# ========== STRIPE CONNECT ONBOARDING ==========


@profiles_router.post("/users/me/stripe-connect/onboard")
async def create_stripe_connect_account(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Create or retrieve Stripe Connect account and generate onboarding link."""
    current_user = await _require_auth(credentials)

    user = await _db.users.find_one({"id": current_user.id})
    connect_id = user.get("stripe_connect_account_id")

    if not connect_id:
        account = stripe.Account.create(
            type="express",
            country="CA",
            email=current_user.email,
            capabilities={"card_payments": {"requested": True}, "transfers": {"requested": True}},
            business_type="individual",
            metadata={"user_id": current_user.id, "platform": "bidvex"},
            settings={
                "payouts": {
                    "schedule": {
                        "interval": "daily",
                        "delay_days": 2,
                    }
                }
            },
        )
        connect_id = account.id
        await _db.users.update_one(
            {"id": current_user.id},
            {"$set": {
                "stripe_connect_account_id": connect_id,
                "stripe_connect_onboarding_complete": False,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

    base_url = os.environ.get("REACT_APP_BACKEND_URL", str(request.base_url).rstrip("/"))
    link = stripe.AccountLink.create(
        account=connect_id,
        refresh_url=f"{base_url}/seller/settings?stripe_refresh=true",
        return_url=f"{base_url}/seller/settings?stripe_onboard=success",
        type="account_onboarding",
    )

    return {
        "connect_account_id": connect_id,
        "onboarding_url": link.url,
        "expires_at": datetime.fromtimestamp(link.expires_at, tz=timezone.utc).isoformat(),
    }


@profiles_router.get("/users/me/stripe-connect/status")
async def get_stripe_connect_status(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get Stripe Connect account status and capabilities."""
    current_user = await _require_auth(credentials)

    user = await _db.users.find_one({"id": current_user.id})
    connect_id = user.get("stripe_connect_account_id")

    if not connect_id:
        return {"has_account": False, "onboarding_complete": False, "payouts_enabled": False, "charges_enabled": False}

    try:
        account = stripe.Account.retrieve(connect_id)

        if account.details_submitted and not user.get("stripe_connect_onboarding_complete"):
            await _db.users.update_one(
                {"id": current_user.id},
                {"$set": {"stripe_connect_onboarding_complete": True, "updated_at": datetime.now(timezone.utc).isoformat()}},
            )

        return {
            "has_account": True,
            "account_id": connect_id,
            "onboarding_complete": account.details_submitted,
            "payouts_enabled": account.payouts_enabled,
            "charges_enabled": account.charges_enabled,
            "capabilities": {
                "card_payments": account.capabilities.get("card_payments", "inactive") if account.capabilities else "inactive",
                "transfers": account.capabilities.get("transfers", "inactive") if account.capabilities else "inactive",
            },
            "requirements": {
                "currently_due": list(account.requirements.currently_due) if account.requirements else [],
                "eventually_due": list(account.requirements.eventually_due) if account.requirements else [],
            },
        }
    except stripe.StripeError as e:
        logger.error(f"Stripe Connect status error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@profiles_router.post("/users/me/stripe-connect/dashboard-link")
async def get_stripe_connect_dashboard_link(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Generate a login link to the Stripe Express Dashboard."""
    current_user = await _require_auth(credentials)

    user = await _db.users.find_one({"id": current_user.id})
    connect_id = user.get("stripe_connect_account_id")

    if not connect_id:
        raise HTTPException(status_code=400, detail="No Stripe Connect account found.")

    try:
        link = stripe.Account.create_login_link(connect_id)
        return {"url": link.url}
    except stripe.StripeError as e:
        logger.error(f"Stripe dashboard link error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ========== GDPR / PIPEDA DATA MANAGEMENT ==========


@profiles_router.post("/user/request-data-deletion")
async def request_data_deletion(
    reason: Optional[str] = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Request account and data deletion (GDPR / PIPEDA)."""
    current_user = await _require_auth(credentials)
    try:
        req = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "user_email": current_user.email,
            "user_name": current_user.name,
            "reason": reason,
            "status": "pending",
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "process_by": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat(),
            "completed_at": None,
        }
        await _db.data_deletion_requests.insert_one(req)
        await _db.users.update_one(
            {"id": current_user.id},
            {"$set": {"deletion_requested": True, "deletion_request_date": datetime.now(timezone.utc).isoformat()}},
        )
        return {
            "success": True,
            "message": "Data deletion request submitted successfully",
            "request_id": req["id"],
            "process_by": req["process_by"],
            "details": "Your request will be processed within 30 days as per GDPR/PIPEDA regulations.",
        }
    except Exception as e:
        logger.error(f"Error creating deletion request: {e}")
        raise HTTPException(status_code=500, detail="Failed to submit deletion request")


@profiles_router.get("/user/data-deletion-status")
async def get_data_deletion_status(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Check the status of any pending data deletion requests."""
    current_user = await _require_auth(credentials)
    try:
        req = await _db.data_deletion_requests.find_one(
            {"user_id": current_user.id, "status": {"$in": ["pending", "processing"]}},
            {"_id": 0},
        )
        return {"has_pending_request": bool(req), "request": req}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@profiles_router.post("/user/cancel-data-deletion")
async def cancel_data_deletion(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Cancel a pending data deletion request."""
    current_user = await _require_auth(credentials)
    try:
        result = await _db.data_deletion_requests.update_one(
            {"user_id": current_user.id, "status": "pending"},
            {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc).isoformat()}},
        )
        if result.modified_count > 0:
            await _db.users.update_one(
                {"id": current_user.id},
                {"$unset": {"deletion_requested": "", "deletion_request_date": ""}},
            )
            return {"success": True, "message": "Data deletion request cancelled"}
        return {"success": False, "message": "No pending deletion request found"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@profiles_router.get("/user/export-data")
async def export_user_data(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Export all user data (GDPR Right to Access / PIPEDA)."""
    current_user = await _require_auth(credentials)
    try:
        user_data = await _db.users.find_one({"id": current_user.id}, {"_id": 0, "password": 0})
        bids = await _db.bids.find({"bidder_id": current_user.id}, {"_id": 0}).to_list(1000)
        listings = await _db.listings.find({"seller_id": current_user.id}, {"_id": 0}).to_list(100)
        multi_listings = await _db.multi_item_listings.find({"seller_id": current_user.id}, {"_id": 0}).to_list(100)
        messages = await _db.messages.find(
            {"$or": [{"sender_id": current_user.id}, {"receiver_id": current_user.id}]},
            {"_id": 0},
        ).to_list(500)

        return {
            "export_date": datetime.now(timezone.utc).isoformat(),
            "user_id": current_user.id,
            "personal_information": user_data,
            "bidding_history": bids,
            "listings_created": listings,
            "multi_item_auctions": multi_listings,
            "messages": messages,
            "data_categories": ["Account Information", "Bidding Activity", "Listing Data", "Communication Records"],
        }
    except Exception as e:
        logger.error(f"Error exporting user data: {e}")
        raise HTTPException(status_code=500, detail="Failed to export data")


# ========== DOCUMENT UPLOAD ==========


@profiles_router.post("/upload-document")
async def upload_document(
    file_data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Upload a document (PDF or image) as base64 with 10MB validation."""
    import base64

    await _require_auth(credentials)

    filename = file_data.get("filename", "")
    content_type = file_data.get("content_type", "")
    base64_content = file_data.get("base64_content", "")

    allowed_types = ["application/pdf", "image/png", "image/jpeg", "image/jpg"]
    if content_type not in allowed_types:
        raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed: PDF, PNG, JPG. Got: {content_type}")

    if not base64_content:
        raise HTTPException(status_code=400, detail="No file content provided")

    try:
        if "base64," in base64_content:
            base64_content = base64_content.split("base64,")[1]
        decoded = base64.b64decode(base64_content)
        size_mb = len(decoded) / (1024 * 1024)
        if size_mb > 10:
            raise HTTPException(status_code=400, detail=f"File too large. Max 10MB. Got: {size_mb:.2f}MB")
        return {"success": True, "filename": filename, "content_type": content_type, "size_mb": round(size_mb, 2), "base64_content": base64_content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 content: {e}")
