"""
BidVex Payments — Promotions & Email Credits Sub-Router
Extracted from payments.py for modularity.
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime, timezone
import logging
import uuid
import stripe

from routes.payments_shared import get_db, get_current_user_wrapper, security

logger = logging.getLogger(__name__)

promotions_sub_router = APIRouter()


def _get_current_user():
    return get_current_user_wrapper()


# ========== PROMOTIONS ==========

@promotions_sub_router.post("/promote")
async def create_promotion(
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Create a listing promotion with Stripe Checkout."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user()(credentials)
    db = get_db()

    listing_id = data.get("listing_id")
    tier = data.get("tier", "basic")
    origin_url = data.get("origin_url", "https://bidvex.com")

    listing = await db.listings.find_one({"id": listing_id, "seller_id": current_user.id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found or not owned by you")

    user = await db.users.find_one({"id": current_user.id})
    customer_id = user.get("stripe_customer_id") if user else None
    if not customer_id:
        customer = stripe.Customer.create(email=current_user.email, metadata={"user_id": current_user.id})
        customer_id = customer.id
        await db.users.update_one({"id": current_user.id}, {"$set": {"stripe_customer_id": customer_id}})

    from services.connect_payment_engine import create_promotion_checkout

    result = create_promotion_checkout(
        customer_id=customer_id,
        listing_id=listing_id,
        user_id=current_user.id,
        tier=tier,
        success_url=f"{origin_url}/payment/success?type=promotion&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{origin_url}/listing/{listing_id}",
    )

    from services.pricing_config import PROMOTION_TIERS

    promo_config = PROMOTION_TIERS.get(tier, PROMOTION_TIERS["basic"])
    now = datetime.now(timezone.utc)

    promotion = {
        "id": str(uuid.uuid4()),
        "listing_id": listing_id,
        "user_id": current_user.id,
        "tier": tier,
        "session_id": result["session_id"],
        "duration_days": promo_config["duration_days"],
        "features": promo_config["features"],
        "price_cents": promo_config["price_cents"],
        "start_date": None,
        "end_date": None,
        "status": "pending_payment",
        "created_at": now.isoformat(),
    }
    await db.promotions.insert_one(promotion)

    return {
        "promotion_id": promotion["id"],
        "checkout_url": result["checkout_url"],
        "session_id": result["session_id"],
        "tier": tier,
        "price": result["price"],
    }


@promotions_sub_router.get("/promotions/my")
async def get_my_promotions(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get user's active promotions."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user()(credentials)
    db = get_db()

    promotions = await db.promotions.find({"user_id": current_user.id}, {"_id": 0}).to_list(100)
    return {"promotions": promotions}


# ========== EMAIL MARKETING CREDITS ==========

class EmailCreditsRequest(BaseModel):
    quantity: int = Field(..., ge=100, le=100000, description="Number of email credits to purchase")
    origin_url: Optional[str] = "https://bidvex.com"


@promotions_sub_router.post("/email-credits/purchase")
async def purchase_email_credits(
    data: EmailCreditsRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Purchase email marketing credits (pay-as-you-go)."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user()(credentials)
    db = get_db()

    user = await db.users.find_one({"id": current_user.id})
    customer_id = user.get("stripe_customer_id") if user else None
    if not customer_id:
        customer = stripe.Customer.create(email=current_user.email, metadata={"user_id": current_user.id})
        customer_id = customer.id
        await db.users.update_one({"id": current_user.id}, {"$set": {"stripe_customer_id": customer_id}})

    from services.connect_payment_engine import create_email_credits_checkout

    result = create_email_credits_checkout(
        customer_id=customer_id,
        user_id=current_user.id,
        quantity=data.quantity,
        success_url=f"{data.origin_url}/payment/success?type=email_credits&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{data.origin_url}/email-marketing",
    )

    return {
        "checkout_url": result["checkout_url"],
        "session_id": result["session_id"],
        "quantity": result["quantity"],
        "total_amount": result["total_cents"] / 100,
        "per_email": round(result["total_cents"] / result["quantity"] / 100, 4),
    }


@promotions_sub_router.get("/email-credits/balance")
async def get_email_credit_balance(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Get the current user's email credit balance."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user()(credentials)
    db = get_db()

    user = await db.users.find_one({"id": current_user.id}, {"_id": 0, "email_credits": 1})
    return {"credits": user.get("email_credits", 0) if user else 0}


@promotions_sub_router.get("/pricing-config")
async def get_pricing_config():
    """Public endpoint returning current platform pricing for UI display."""
    from services.pricing_config import (
        BUYER_PREMIUM_RATES,
        SELLER_COMMISSION_RATES,
        SUBSCRIPTION_TIERS,
        PROMOTION_TIERS,
        EMAIL_CREDIT_TIERS,
        DEPOSIT_THRESHOLD_CAD,
        DEPOSIT_AMOUNT_DOLLARS,
        PLATFORM_FEE_GENERAL,
        PLATFORM_FEE_VEHICLE,
    )

    return {
        "commissions": {"general": float(PLATFORM_FEE_GENERAL), "vehicle": float(PLATFORM_FEE_VEHICLE)},
        "buyer_premiums": {k: float(v) for k, v in BUYER_PREMIUM_RATES.items()},
        "seller_commissions": {k: float(v) for k, v in SELLER_COMMISSION_RATES.items()},
        "subscriptions": SUBSCRIPTION_TIERS,
        "promotions": PROMOTION_TIERS,
        "email_credits": EMAIL_CREDIT_TIERS,
        "deposit": {"threshold_cad": DEPOSIT_THRESHOLD_CAD, "amount_dollars": DEPOSIT_AMOUNT_DOLLARS},
    }
