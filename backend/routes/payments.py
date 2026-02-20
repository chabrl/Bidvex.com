"""
BidVex Payments Router
Handles Stripe payment operations:
- Checkout sessions
- Subscription management
- Payment methods
- Promotions
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import logging
import uuid
import os

logger = logging.getLogger(__name__)

payments_router = APIRouter(prefix="/payments", tags=["Payments"])
security = HTTPBearer(auto_error=False)

# Database and service instances
_db = None
_get_current_user = None


def set_payments_db(db_instance):
    """Set database instance"""
    global _db
    _db = db_instance


def set_payments_auth(get_current_user_func):
    """Set authentication function"""
    global _get_current_user
    _get_current_user = get_current_user_func


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


# ========== CHECKOUT ENDPOINTS ==========

class CheckoutRequest(BaseModel):
    price_id: str
    success_url: str
    cancel_url: str


@payments_router.post("/checkout")
async def create_checkout_session(
    data: CheckoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create Stripe checkout session for subscription"""
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    
    # Get or create Stripe customer
    user = await db.users.find_one({"id": current_user.id})
    customer_id = user.get("stripe_customer_id")
    
    if not customer_id:
        # Create new Stripe customer
        customer = stripe.Customer.create(
            email=current_user.email,
            name=current_user.name,
            metadata={"user_id": current_user.id}
        )
        customer_id = customer.id
        
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"stripe_customer_id": customer_id}}
        )
    
    # Create checkout session
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{
            "price": data.price_id,
            "quantity": 1
        }],
        mode="subscription",
        success_url=data.success_url,
        cancel_url=data.cancel_url,
        metadata={"user_id": current_user.id}
    )
    
    return {
        "session_id": session.id,
        "url": session.url
    }


@payments_router.get("/status/{session_id}")
async def get_checkout_status(session_id: str):
    """Get checkout session status"""
    import stripe
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return {
            "status": session.status,
            "payment_status": session.payment_status,
            "customer": session.customer,
            "subscription": session.subscription
        }
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== SUBSCRIPTION STATUS ==========

@payments_router.get("/subscription/status")
async def get_subscription_status(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get current user's subscription status"""
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    
    user = await db.users.find_one({"id": current_user.id})
    
    result = {
        "tier": user.get("subscription_tier", "free"),
        "source": user.get("subscription_source", "manual"),
        "status": user.get("subscription_status", "inactive"),
        "start_date": user.get("subscription_start_date"),
        "end_date": user.get("subscription_end_date")
    }
    
    # If Stripe subscription, get live status
    if user.get("stripe_subscription_id"):
        try:
            sub = stripe.Subscription.retrieve(user["stripe_subscription_id"])
            result["stripe_status"] = sub.status
            result["stripe_current_period_end"] = datetime.fromtimestamp(
                sub.current_period_end,
                tz=timezone.utc
            ).isoformat()
        except stripe.error.StripeError:
            result["stripe_status"] = "error"
    
    return result


# ========== PAYMENT METHODS ==========

@payments_router.post("/payment-methods")
async def add_payment_method(
    data: Dict[str, str],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Add a payment method to user's account"""
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    
    payment_method_id = data.get("payment_method_id")
    if not payment_method_id:
        raise HTTPException(status_code=400, detail="Payment method ID required")
    
    user = await db.users.find_one({"id": current_user.id})
    customer_id = user.get("stripe_customer_id")
    
    if not customer_id:
        # Create customer first
        customer = stripe.Customer.create(
            email=current_user.email,
            name=current_user.name
        )
        customer_id = customer.id
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"stripe_customer_id": customer_id}}
        )
    
    # Attach payment method
    stripe.PaymentMethod.attach(
        payment_method_id,
        customer=customer_id
    )
    
    # Set as default
    stripe.Customer.modify(
        customer_id,
        invoice_settings={"default_payment_method": payment_method_id}
    )
    
    return {"status": "success", "payment_method_id": payment_method_id}


@payments_router.get("/payment-methods")
async def get_payment_methods(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get user's saved payment methods"""
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    
    user = await db.users.find_one({"id": current_user.id})
    customer_id = user.get("stripe_customer_id")
    
    if not customer_id:
        return {"payment_methods": []}
    
    methods = stripe.PaymentMethod.list(
        customer=customer_id,
        type="card"
    )
    
    return {
        "payment_methods": [
            {
                "id": pm.id,
                "brand": pm.card.brand,
                "last4": pm.card.last4,
                "exp_month": pm.card.exp_month,
                "exp_year": pm.card.exp_year
            }
            for pm in methods.data
        ]
    }


@payments_router.delete("/payment-methods/{method_id}")
async def delete_payment_method(
    method_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete a payment method"""
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        stripe.PaymentMethod.detach(method_id)
        return {"status": "deleted"}
    except stripe.error.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== PROMOTIONS ==========

@payments_router.post("/promote")
async def create_promotion(
    data: Dict[str, Any],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Create a listing promotion (featured/highlighted)"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    
    listing_id = data.get("listing_id")
    promotion_type = data.get("type", "featured")  # featured, highlighted
    duration_days = data.get("duration_days", 7)
    
    # Verify listing ownership
    listing = await db.listings.find_one({
        "id": listing_id,
        "seller_id": current_user.id
    })
    
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found or not owned by you")
    
    now = datetime.now(timezone.utc)
    
    promotion = {
        "id": str(uuid.uuid4()),
        "listing_id": listing_id,
        "user_id": current_user.id,
        "type": promotion_type,
        "start_date": now.isoformat(),
        "end_date": (now + timedelta(days=duration_days)).isoformat(),
        "status": "pending_payment",
        "created_at": now.isoformat()
    }
    
    await db.promotions.insert_one(promotion)
    
    return {
        "promotion_id": promotion["id"],
        "status": "created"
    }


@payments_router.get("/promotions/my")
async def get_my_promotions(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get user's active promotions"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    
    promotions = await db.promotions.find(
        {"user_id": current_user.id},
        {"_id": 0}
    ).to_list(100)
    
    return {"promotions": promotions}


# ========== FEE CALCULATIONS ==========

@payments_router.get("/fees/calculate-buyer-cost")
async def calculate_buyer_cost(
    price: float,
    tier: str = "free"
):
    """Calculate total buyer cost including fees"""
    # Buyer premium rates
    rates = {
        "free": 0.10,      # 10%
        "premium": 0.08,   # 8%
        "vip": 0.05        # 5%
    }
    
    rate = rates.get(tier, rates["free"])
    buyer_premium = price * rate
    total = price + buyer_premium
    
    return {
        "base_price": price,
        "buyer_premium": round(buyer_premium, 2),
        "buyer_premium_rate": rate,
        "total_cost": round(total, 2)
    }


@payments_router.get("/fees/calculate-seller-net")
async def calculate_seller_net(
    price: float,
    tier: str = "free"
):
    """Calculate seller net after commission"""
    # Commission rates
    rates = {
        "free": 0.04,      # 4%
        "premium": 0.025,  # 2.5%
        "vip": 0.02        # 2%
    }
    
    rate = rates.get(tier, rates["free"])
    commission = price * rate
    net = price - commission
    
    return {
        "sale_price": price,
        "commission": round(commission, 2),
        "commission_rate": rate,
        "seller_net": round(net, 2)
    }


@payments_router.get("/fees/subscription-benefits")
async def get_subscription_benefits():
    """Get subscription tier benefits breakdown"""
    return {
        "free": {
            "commission_rate": 0.04,
            "buyer_premium": 0.10,
            "email_sends_monthly": 0,
            "contact_limit": 50,
            "features": ["Basic listings", "Standard support"]
        },
        "premium": {
            "commission_rate": 0.025,
            "buyer_premium": 0.08,
            "email_sends_monthly": 5000,
            "contact_limit": 5000,
            "features": [
                "Lower commission",
                "Email marketing (500/day)",
                "Priority support",
                "Analytics dashboard"
            ]
        },
        "vip": {
            "commission_rate": 0.02,
            "buyer_premium": 0.05,
            "email_sends_monthly": 50000,
            "contact_limit": 25000,
            "features": [
                "Lowest commission",
                "Email marketing (2000/day)",
                "Priority sending",
                "Dedicated support",
                "Advanced analytics"
            ]
        }
    }


from datetime import timedelta
