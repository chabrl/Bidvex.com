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
import stripe

# Configure Stripe API key
stripe.api_key = os.environ.get('STRIPE_API_KEY', '')

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
    """
    Set authentication function
    
    Note: The passed function expects (Request, credentials) but most routes
    only have access to credentials. We create a wrapper that works with credentials only.
    """
    global _get_current_user
    
    async def wrapper(credentials):
        """Wrapper that creates a mock request for cookie-less auth"""
        # Create a minimal mock request since we're using Bearer token auth
        # The real function checks cookies first, then credentials
        class MockRequest:
            cookies = {}
        return await get_current_user_func(MockRequest(), credentials)
    
    _get_current_user = wrapper


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


# ========== CHECKOUT ENDPOINTS ==========

class CheckoutRequest(BaseModel):
    # Subscription checkout fields
    price_id: Optional[str] = None
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None
    # Legacy listing checkout fields
    listing_id: Optional[str] = None
    origin_url: Optional[str] = None


@payments_router.post("/checkout")
async def create_checkout_session(
    data: CheckoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Unified checkout endpoint.
    - With price_id → subscription checkout
    - With listing_id → listing purchase checkout
    """
    import stripe

    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user(credentials)
    db = get_db()

    user = await db.users.find_one({"id": current_user.id})
    customer_id = user.get("stripe_customer_id") if user else None

    if not customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=getattr(current_user, "name", current_user.email),
            metadata={"user_id": current_user.id},
        )
        customer_id = customer.id
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"stripe_customer_id": customer_id}},
        )

    # ── Listing purchase checkout ──
    if data.listing_id:
        listing = await db.listings.find_one({"id": data.listing_id}, {"_id": 0})
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

        buyer_fee = 0.05 if getattr(current_user, "account_type", "personal") == "personal" else 0.045
        total_amount = listing["current_price"] * (1 + buyer_fee)
        amount_cents = int(round(total_amount * 100))

        origin = data.origin_url or "https://bidvex.com"
        session = stripe.checkout.Session.create(
            customer=customer_id,
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "cad",
                    "unit_amount": amount_cents,
                    "product_data": {"name": listing.get("title", "Auction Purchase")},
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/listing/{data.listing_id}",
            metadata={
                "user_id": current_user.id,
                "listing_id": data.listing_id,
                "buyer_fee": str(buyer_fee),
                "type": "listing_purchase",
            },
        )

        # Record transaction
        txn = {
            "id": str(uuid.uuid4()),
            "session_id": session.id,
            "user_id": current_user.id,
            "listing_id": data.listing_id,
            "amount": total_amount,
            "currency": "cad",
            "payment_status": "pending",
            "metadata": {"buyer_fee": str(buyer_fee)},
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.payment_transactions.insert_one(txn)

        return {"url": session.url, "session_id": session.id}

    # ── Subscription checkout ──
    if not data.price_id or not data.success_url:
        raise HTTPException(status_code=400, detail="price_id and success_url are required for subscription checkout")

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": data.price_id, "quantity": 1}],
        mode="subscription",
        success_url=data.success_url,
        cancel_url=data.cancel_url or data.success_url,
        metadata={"user_id": current_user.id},
    )

    return {"session_id": session.id, "url": session.url}


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
    except stripe.StripeError as e:
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
            sub_data = dict(sub)
            result["stripe_status"] = sub_data.get("status", "unknown")
            start_ts = sub_data.get("start_date") or sub_data.get("billing_cycle_anchor")
            if start_ts:
                end_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc).replace(
                    year=datetime.fromtimestamp(start_ts, tz=timezone.utc).year + 1
                )
                result["stripe_current_period_end"] = end_dt.isoformat()
        except stripe.StripeError:
            result["stripe_status"] = "error"
    
    return result


# ========== PAYMENT METHODS ==========

@payments_router.post("/setup-intent")
async def create_setup_intent(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create a Stripe SetupIntent for collecting payment method
    
    This is used for Trust Status verification - a valid payment method
    automatically verifies the user and allows them to place bids.
    
    Returns:
        client_secret: For use with Stripe Elements/Checkout
    """
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    
    user = await db.users.find_one({"id": current_user.id})
    customer_id = user.get("stripe_customer_id")
    
    # Create customer if doesn't exist
    if not customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=getattr(current_user, 'name', current_user.email),
            metadata={"user_id": current_user.id, "platform": "bidvex"}
        )
        customer_id = customer.id
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"stripe_customer_id": customer_id}}
        )
    
    # Create SetupIntent
    setup_intent = stripe.SetupIntent.create(
        customer=customer_id,
        payment_method_types=["card"],
        metadata={
            "user_id": current_user.id,
            "purpose": "trust_verification"
        }
    )
    
    return {
        "client_secret": setup_intent.client_secret,
        "setup_intent_id": setup_intent.id,
        "customer_id": customer_id
    }


@payments_router.post("/setup-intent/confirm")
async def confirm_setup_intent(
    data: Dict[str, str],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Confirm that a SetupIntent was successful and update trust status
    
    Called by frontend after Stripe Elements confirms the payment method.
    This is a backup in case the webhook doesn't fire immediately.
    """
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    setup_intent_id = data.get("setup_intent_id")
    if not setup_intent_id:
        raise HTTPException(status_code=400, detail="SetupIntent ID required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    
    # Retrieve and verify the SetupIntent
    try:
        setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
        
        if setup_intent.status != "succeeded":
            raise HTTPException(
                status_code=400, 
                detail="SetupIntent not successful"
            )
        
        # Verify this belongs to the current user
        if setup_intent.metadata.get("user_id") != current_user.id:
            raise HTTPException(status_code=403, detail="SetupIntent does not belong to this user")
        
        payment_method_id = setup_intent.payment_method
        
        # Set as default payment method
        stripe.Customer.modify(
            setup_intent.customer,
            invoice_settings={"default_payment_method": payment_method_id}
        )
        
        # Update user trust status
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {
                "trust_status": "verified",
                "trust_verified_at": datetime.now(timezone.utc).isoformat(),
                "default_payment_method_id": payment_method_id,
                "has_payment_method": True,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Store payment method record
        pm = stripe.PaymentMethod.retrieve(payment_method_id)
        await db.payment_methods.update_one(
            {"user_id": current_user.id, "stripe_payment_method_id": payment_method_id},
            {"$set": {
                "user_id": current_user.id,
                "stripe_payment_method_id": payment_method_id,
                "brand": pm.card.brand,
                "last4": pm.card.last4,
                "exp_month": pm.card.exp_month,
                "exp_year": pm.card.exp_year,
                "is_default": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            }},
            upsert=True
        )
        
        return {
            "status": "success",
            "trust_status": "verified",
            "payment_method": {
                "id": payment_method_id,
                "brand": pm.card.brand,
                "last4": pm.card.last4
            }
        }
        
    except stripe.StripeError as e:
        logger.error(f"Stripe error confirming SetupIntent: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@payments_router.get("/trust-status")
async def get_trust_status(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current user's trust verification status
    
    Returns:
        trust_status: "verified", "pending", or "unverified"
        has_payment_method: Boolean
        payment_method: Default payment method details (if exists)
    """
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _get_current_user(credentials)
    db = get_db()
    
    user = await db.users.find_one({"id": current_user.id})
    
    trust_status = user.get("trust_status", "unverified")
    has_payment_method = user.get("has_payment_method", False)
    phone_verified = user.get("phone_verified", False)
    
    # Get default payment method
    payment_method = None
    customer_id = user.get("stripe_customer_id")
    
    if customer_id and has_payment_method:
        try:
            methods = stripe.PaymentMethod.list(customer=customer_id, type="card", limit=1)
            if methods.data:
                pm = methods.data[0]
                payment_method = {
                    "id": pm.id,
                    "brand": pm.card.brand,
                    "last4": pm.card.last4,
                    "exp_month": pm.card.exp_month,
                    "exp_year": pm.card.exp_year
                }
        except stripe.StripeError:
            pass
    
    return {
        "trust_status": trust_status,
        "is_verified": trust_status == "verified",
        "has_payment_method": has_payment_method,
        "phone_verified": phone_verified,
        "payment_method": payment_method,
        "trust_verified_at": user.get("trust_verified_at"),
        "can_bid": trust_status == "verified"
    }


@payments_router.post("/payment-methods")
async def add_payment_method(
    data: Dict[str, str],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Add a payment method, store in DB, and update trust status."""
    import stripe

    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user(credentials)
    db = get_db()

    payment_method_id = data.get("payment_method_id")
    if not payment_method_id:
        raise HTTPException(status_code=400, detail="Payment method ID required")

    try:
        user = await db.users.find_one({"id": current_user.id})
        customer_id = user.get("stripe_customer_id") if user else None

        if not customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=getattr(current_user, 'name', current_user.email),
                metadata={"user_id": current_user.id, "platform": "bidvex"},
            )
            customer_id = customer.id
            await db.users.update_one(
                {"id": current_user.id},
                {"$set": {"stripe_customer_id": customer_id}},
            )

        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
        stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)

        stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": payment_method_id},
        )

        pm_doc = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "stripe_payment_method_id": payment_method_id,
            "card_brand": payment_method.card.brand if payment_method.card else "unknown",
            "last4": payment_method.card.last4 if payment_method.card else "****",
            "exp_month": payment_method.card.exp_month if payment_method.card else 0,
            "exp_year": payment_method.card.exp_year if payment_method.card else 0,
            "is_verified": True,
            "is_default": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await db.payment_methods.insert_one(pm_doc)

        # Update user trust status
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {
                "trust_status": "verified",
                "has_payment_method": True,
                "default_payment_method_id": payment_method_id,
                "trust_verified_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

        del pm_doc["_id"]  # MongoDB adds _id after insert
        return pm_doc

    except stripe.StripeError as e:
        logger.error(f"Stripe error in add_payment_method: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Payment method error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@payments_router.get("/payment-methods")
async def get_payment_methods(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get user's saved payment methods from DB."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user(credentials)
    db = get_db()

    methods = await db.payment_methods.find(
        {"user_id": current_user.id}, {"_id": 0}
    ).to_list(100)
    return methods


@payments_router.delete("/payment-methods/{method_id}")
async def delete_payment_method(
    method_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete a payment method from Stripe and DB."""
    import stripe

    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user(credentials)
    db = get_db()

    method = await db.payment_methods.find_one(
        {"id": method_id, "user_id": current_user.id}
    )
    if not method:
        raise HTTPException(status_code=404, detail="Payment method not found")

    try:
        stripe.PaymentMethod.detach(method["stripe_payment_method_id"])
    except Exception:
        pass

    await db.payment_methods.delete_one({"id": method_id})
    return {"message": "Payment method deleted"}


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

# Import the hybrid fee calculation engine
from services.fee_calculation_engine import (
    calculate_fees,
    calculate_vehicle_fees,
    calculate_general_fees,
    get_fee_structure_summary,
    FeeCalculationResult
)


class FeeCalculationRequest(BaseModel):
    """Request model for fee calculation"""
    hammer_price: float = Field(..., gt=0, description="Winning bid amount in dollars")
    category: str = Field(default="general", description="Auction category: 'vehicle' or 'general'")
    buyer_tier: str = Field(default="basic", description="Buyer subscription tier")
    seller_tier: str = Field(default="basic", description="Seller subscription tier")


@payments_router.post("/fees/calculate")
async def calculate_auction_fees(request: FeeCalculationRequest):
    """
    Calculate complete fee breakdown for an auction transaction
    
    Supports two fee structures:
    - VEHICLE: Buyer pays premium + 2.5% platform fee, Seller gets 100%
    - GENERAL: Buyer pays premium, Seller pays commission
    
    All amounts returned in both dollars and cents (for Stripe)
    """
    result = calculate_fees(
        hammer_price=request.hammer_price,
        category=request.category,
        buyer_tier=request.buyer_tier,
        seller_tier=request.seller_tier
    )
    
    return result.to_dict()


@payments_router.get("/fees/calculate-hybrid")
async def calculate_hybrid_fees(
    price: float,
    category: str = "general",
    buyer_tier: str = "basic",
    seller_tier: str = "basic"
):
    """
    GET endpoint for fee calculation (alternative to POST)
    
    Args:
        price: Hammer price (winning bid) in dollars
        category: 'vehicle' or 'general'
        buyer_tier: Buyer's subscription tier
        seller_tier: Seller's subscription tier
    """
    result = calculate_fees(
        hammer_price=price,
        category=category,
        buyer_tier=buyer_tier,
        seller_tier=seller_tier
    )
    
    return result.to_dict()


@payments_router.get("/fees/vehicle")
async def calculate_vehicle_auction_fees(
    price: float,
    buyer_tier: str = "basic"
):
    """
    Calculate fees specifically for vehicle auctions
    
    Vehicle Fee Structure:
    - Buyer pays: Price + Buyer Premium + 2.5% Platform Fee
    - Seller receives: 100% of hammer price
    - BidVex keeps: Buyer Premium + Platform Fee
    """
    result = calculate_vehicle_fees(
        hammer_price=price,
        buyer_tier=buyer_tier
    )
    
    return {
        "auction_type": "vehicle",
        "hammer_price": result.hammer_price,
        "buyer": {
            "premium_rate": f"{result.buyer_premium_rate * 100:.1f}%",
            "premium_amount": result.buyer_premium,
            "platform_fee_rate": f"{result.platform_fee_rate * 100:.1f}%",
            "platform_fee_amount": result.platform_fee,
            "total_cost": result.buyer_total,
            "total_cost_cents": result.buyer_total_cents
        },
        "seller": {
            "commission_rate": "0%",
            "commission_amount": 0.0,
            "net_payout": result.seller_net_payout,
            "net_payout_cents": result.seller_net_payout_cents
        },
        "bidvex": {
            "revenue": result.bidvex_revenue,
            "revenue_cents": result.bidvex_revenue_cents
        },
        "stripe": {
            "amount_cents": result.stripe_amount_cents,
            "application_fee_cents": result.stripe_application_fee_cents,
            "transfer_amount_cents": result.stripe_transfer_amount_cents
        }
    }


@payments_router.get("/fees/general")
async def calculate_general_auction_fees(
    price: float,
    buyer_tier: str = "basic",
    seller_tier: str = "basic"
):
    """
    Calculate fees specifically for general auctions
    
    General Fee Structure:
    - Buyer pays: Price + Buyer Premium
    - Seller receives: Price - Commission
    - BidVex keeps: Buyer Premium + Seller Commission
    """
    result = calculate_general_fees(
        hammer_price=price,
        buyer_tier=buyer_tier,
        seller_tier=seller_tier
    )
    
    return {
        "auction_type": "general",
        "hammer_price": result.hammer_price,
        "buyer": {
            "premium_rate": f"{result.buyer_premium_rate * 100:.1f}%",
            "premium_amount": result.buyer_premium,
            "platform_fee_rate": "0%",
            "platform_fee_amount": 0.0,
            "total_cost": result.buyer_total,
            "total_cost_cents": result.buyer_total_cents
        },
        "seller": {
            "commission_rate": f"{result.seller_commission_rate * 100:.1f}%",
            "commission_amount": result.seller_commission,
            "net_payout": result.seller_net_payout,
            "net_payout_cents": result.seller_net_payout_cents
        },
        "bidvex": {
            "revenue": result.bidvex_revenue,
            "revenue_cents": result.bidvex_revenue_cents
        },
        "stripe": {
            "amount_cents": result.stripe_amount_cents,
            "application_fee_cents": result.stripe_application_fee_cents,
            "transfer_amount_cents": result.stripe_transfer_amount_cents
        }
    }


@payments_router.get("/fees/structure")
async def get_fee_structures():
    """
    Get complete fee structure documentation for both auction types
    """
    return get_fee_structure_summary()


# Legacy endpoints (kept for backward compatibility)
@payments_router.get("/fees/calculate-buyer-cost")
async def calculate_buyer_cost(
    price: float,
    tier: str = "free"
):
    """Calculate total buyer cost including fees (legacy endpoint)"""
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
    """Calculate seller net after commission (legacy endpoint)"""
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

# Import the tax engine for Quebec-compliant calculations
from services.tax_engine import (
    calculate_vehicle_payment,
    calculate_general_payment,
    get_tax_structure_summary,
    SellerInfo,
    VehiclePaymentResult,
    GeneralPaymentResult,
    GST_RATE,
    QST_RATE,
    BIDVEX_GST_NUMBER,
    BIDVEX_QST_NUMBER,
)


# ========== TAX & COMPLIANCE ENDPOINTS ==========

class TaxCalculationRequest(BaseModel):
    """Request model for tax-inclusive payment calculation"""
    hammer_price: float = Field(..., gt=0, description="Winning bid amount in dollars")
    category: str = Field(default="general", description="Auction category: 'vehicle' or 'general'")
    buyer_tier: str = Field(default="basic", description="Buyer subscription tier")
    seller_tier: str = Field(default="basic", description="Seller subscription tier")
    seller_is_business: bool = Field(default=False, description="Whether seller is a registered business")
    seller_gst_number: Optional[str] = Field(default=None, description="Seller's GST registration number")
    seller_qst_number: Optional[str] = Field(default=None, description="Seller's QST registration number")
    buyers_premium_rate: Optional[float] = Field(default=None, description="Listing-level buyer premium rate (e.g. 0.15 for 15%)")


@payments_router.post("/tax/calculate")
async def calculate_payment_with_tax(request: TaxCalculationRequest):
    """
    Calculate complete payment breakdown with Quebec taxes (GST/QST)
    
    Quebec Tax Rates:
    - GST (Federal): 5%
    - QST (Provincial): 9.975%
    - Combined: 14.975%
    
    Tax Logic:
    - VEHICLE auctions: Only BidVex fees are charged via Stripe (with tax).
      Hammer price is paid directly to seller via Bank Draft.
    - GENERAL auctions: Full amount through Stripe.
      - Private seller: No tax on hammer price
      - Business seller: 14.975% tax on hammer price (collected for seller)
    """
    category_lower = request.category.lower()
    
    if category_lower in ["vehicle", "car", "auto", "automobile", "truck", "motorcycle"]:
        # Vehicle payment - only fees through Stripe
        result = calculate_vehicle_payment(
            hammer_price=request.hammer_price,
            buyer_tier=request.buyer_tier,
            buyer_premium_rate_override=request.buyers_premium_rate
        )
        return {
            "payment_type": "vehicle",
            "description": "Vehicle auction - BidVex fees charged via Stripe, hammer price paid directly to seller",
            **result.to_dict()
        }
    else:
        # General payment - full amount through Stripe
        seller_info = SellerInfo(
            is_business=request.seller_is_business,
            gst_number=request.seller_gst_number,
            qst_number=request.seller_qst_number
        ) if request.seller_is_business else None
        
        result = calculate_general_payment(
            hammer_price=request.hammer_price,
            buyer_tier=request.buyer_tier,
            seller_tier=request.seller_tier,
            seller_is_business=request.seller_is_business,
            seller_info=seller_info,
            buyer_premium_rate_override=request.buyers_premium_rate
        )
        return {
            "payment_type": "general",
            "description": "General auction - full amount charged via Stripe",
            **result.to_dict()
        }


@payments_router.get("/tax/vehicle")
async def calculate_vehicle_payment_with_tax(
    price: float,
    buyer_tier: str = "basic",
    buyers_premium_rate: Optional[float] = None
):
    """
    Calculate vehicle auction payment with Quebec taxes
    
    IMPORTANT: For vehicles, only BidVex fees are charged through Stripe.
    The hammer price is paid directly to seller via Bank Draft.
    
    Stripe charges: (Buyer Premium + Platform Fee) + 14.975% Tax
    
    If buyers_premium_rate is provided, overrides the tier default.
    """
    result = calculate_vehicle_payment(
        hammer_price=price,
        buyer_tier=buyer_tier,
        buyer_premium_rate_override=buyers_premium_rate
    )
    
    return {
        "auction_type": "vehicle",
        "payment_method": "hybrid",
        "description": "BidVex fees charged via Stripe, hammer price via Bank Draft to seller",
        **result.to_dict()
    }


@payments_router.get("/tax/general")
async def calculate_general_payment_with_tax(
    price: float,
    buyer_tier: str = "basic",
    seller_tier: str = "basic",
    seller_is_business: bool = False
):
    """
    Calculate general auction payment with Quebec taxes
    
    Tax Logic:
    - BidVex fees: Always taxed at 14.975%
    - Hammer price:
      - Private seller (is_business=false): NO tax on hammer price
      - Business seller (is_business=true): 14.975% tax (collected for seller via Stripe Connect)
    
    Example for $1,000 item (basic tier, private seller):
    - Hammer price: $1,000
    - Buyer Premium (5%): $50
    - GST on fees (5%): $2.50
    - QST on fees (9.975%): $4.99
    - Total buyer pays: $1,057.49
    
    Example for $1,000 item (basic tier, business seller):
    - Hammer price: $1,000
    - GST on item (5%): $50
    - QST on item (9.975%): $99.75
    - Buyer Premium (5%): $50
    - GST on fees (5%): $2.50
    - QST on fees (9.975%): $4.99
    - Total buyer pays: $1,207.24
    """
    result = calculate_general_payment(
        hammer_price=price,
        buyer_tier=buyer_tier,
        seller_tier=seller_tier,
        seller_is_business=seller_is_business
    )
    
    return {
        "auction_type": "general",
        "payment_method": "stripe_full",
        "description": "Full amount charged via Stripe" + (
            " (tax collected on behalf of business seller)" if seller_is_business else ""
        ),
        **result.to_dict()
    }


@payments_router.get("/tax/structure")
async def get_tax_structure():
    """
    Get Quebec tax structure documentation
    
    Returns:
    - Tax rates (GST, QST, combined)
    - BidVex registration numbers
    - Vehicle vs General auction tax treatment
    - Private vs Business seller tax logic
    """
    return get_tax_structure_summary()


@payments_router.get("/tax/rates")
async def get_tax_rates():
    """
    Get current Quebec tax rates
    """
    return {
        "jurisdiction": "Quebec, Canada",
        "gst": {
            "name": "Goods and Services Tax (Federal)",
            "rate": float(GST_RATE),
            "rate_display": "5%",
            "registration": BIDVEX_GST_NUMBER
        },
        "qst": {
            "name": "Quebec Sales Tax (Provincial)",
            "rate": float(QST_RATE),
            "rate_display": "9.975%",
            "registration": BIDVEX_QST_NUMBER
        },
        "combined": {
            "name": "Total Quebec Tax",
            "rate": float(GST_RATE) + float(QST_RATE),
            "rate_display": "14.975%"
        }
    }



# ========== CHECKOUT ENDPOINTS WITH FULL BREAKDOWN ==========

from services.stripe_connect_service import (
    calculate_general_checkout,
    calculate_vehicle_checkout,
    calculate_partner_listing_checkout,
    create_destination_charge,
    create_vehicle_payment_session,
    STRIPE_PERCENTAGE_FEE,
    STRIPE_FIXED_FEE
)


class AuctionCheckoutRequest(BaseModel):
    """Request model for auction checkout"""
    listing_id: str = Field(..., description="Listing/auction ID")
    return_url: str = Field(..., description="URL to redirect after checkout")


@payments_router.post("/checkout/auction")
async def create_auction_checkout(
    request: AuctionCheckoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create checkout session for auction purchase
    
    This handles both GENERAL and VEHICLE auctions:
    - GENERAL: Destination charge to seller's Stripe Connect account
    - VEHICLE: Direct charge for BidVex fees only (hammer paid offline)
    
    Returns checkout URL and complete breakdown for display.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    # Get listing
    listing = await db.listings.find_one({"id": request.listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Verify buyer is the winner
    if listing.get("winning_bidder_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Only the winning bidder can checkout")
    
    # Check if already paid
    if listing.get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="This auction has already been paid")
    
    # Get seller info
    seller = await db.users.find_one({"id": listing["seller_id"]})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # Determine if this is a vehicle auction
    category = listing.get("category", "").lower()
    is_vehicle = any(keyword in category for keyword in ["vehicle", "car", "auto", "truck", "motorcycle"])
    is_partner = listing.get("is_partner_listing", False)
    
    hammer_price = listing.get("current_price", listing.get("starting_price", 0))
    
    if is_partner:
        # Partner listing — 3% platform fee, custom buyer premium, destination charge
        seller_connect_id = seller.get("stripe_connect_account_id")
        if not seller_connect_id:
            raise HTTPException(
                status_code=400, 
                detail="Partner has not completed Stripe Connect onboarding."
            )
        
        custom_bp_rate = listing.get("custom_buyer_premium_rate", 0.0) or 0.0
        partner_is_tax_registered = seller.get("is_tax_registered", False)
        
        breakdown = calculate_partner_listing_checkout(
            hammer_price=hammer_price,
            custom_buyer_premium_rate=custom_bp_rate,
            partner_is_tax_registered=partner_is_tax_registered,
            include_processing_fee=True
        )
        
        result = await create_destination_charge(
            db=db,
            listing_id=request.listing_id,
            buyer_id=current_user.id,
            breakdown=breakdown,
            return_url=request.return_url,
            seller_connect_account_id=seller_connect_id
        )
        
        return {
            "checkout_type": "partner",
            **result
        }
    elif is_vehicle:
        # Vehicle auction - only BidVex fees via Stripe
        breakdown = calculate_vehicle_checkout(
            hammer_price=hammer_price,
            buyer_tier=current_user.subscription_tier if hasattr(current_user, 'subscription_tier') else "basic"
        )
        
        result = await create_vehicle_payment_session(
            db=db,
            auction_id=request.listing_id,
            buyer_id=current_user.id,
            breakdown=breakdown,
            return_url=request.return_url
        )
        
        return {
            "checkout_type": "vehicle",
            **result
        }
    else:
        # General auction - destination charge to seller
        seller_connect_id = seller.get("stripe_connect_account_id")
        
        if not seller_connect_id:
            raise HTTPException(
                status_code=400, 
                detail="Seller has not completed Stripe Connect onboarding. Please contact seller."
            )
        
        breakdown = calculate_general_checkout(
            hammer_price=hammer_price,
            buyer_tier=current_user.subscription_tier if hasattr(current_user, 'subscription_tier') else "basic",
            seller_tier=seller.get("subscription_tier", "basic"),
            seller_is_tax_registered=seller.get("is_tax_registered", False),
            include_processing_fee=True
        )
        
        result = await create_destination_charge(
            db=db,
            listing_id=request.listing_id,
            buyer_id=current_user.id,
            breakdown=breakdown,
            return_url=request.return_url,
            seller_connect_account_id=seller_connect_id
        )
        
        return {
            "checkout_type": "general",
            **result
        }


@payments_router.get("/checkout/preview/{listing_id}")
async def preview_checkout_breakdown(
    listing_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get checkout breakdown preview without creating a session
    
    Use this to display the cost breakdown in the UI before checkout.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    # Get listing
    listing = await db.listings.find_one({"id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Get seller info
    seller = await db.users.find_one({"id": listing["seller_id"]})
    
    category = listing.get("category", "").lower()
    is_vehicle = any(keyword in category for keyword in ["vehicle", "car", "auto", "truck", "motorcycle"])
    is_partner = listing.get("is_partner_listing", False)
    
    hammer_price = listing.get("current_price", listing.get("starting_price", 0))
    
    buyer_tier = "basic"
    if hasattr(current_user, 'subscription_tier'):
        buyer_tier = current_user.subscription_tier
    
    if is_partner:
        # Partner listing — custom buyer premium, 3% platform fee
        custom_bp_rate = listing.get("custom_buyer_premium_rate", 0.0) or 0.0
        partner_is_tax_registered = seller.get("is_tax_registered", False) if seller else False
        
        breakdown = calculate_partner_listing_checkout(
            hammer_price=hammer_price,
            custom_buyer_premium_rate=custom_bp_rate,
            partner_is_tax_registered=partner_is_tax_registered,
            include_processing_fee=True
        )
        
        bp_label = f"Buyer's Premium ({custom_bp_rate*100:.1f}%)" if custom_bp_rate > 0 else "Buyer's Premium"
        
        return {
            "checkout_type": "partner",
            "breakdown": breakdown.to_dict(),
            "is_partner_listing": True,
            "partner_company": seller.get("partner_company_name") if seller else None,
            "seller_is_tax_registered": partner_is_tax_registered,
            "fee_model_label": "Partner Auction",
        }
    elif is_vehicle:
        breakdown = calculate_vehicle_checkout(
            hammer_price=hammer_price,
            buyer_tier=buyer_tier
        )
        
        return {
            "checkout_type": "vehicle",
            "breakdown": breakdown.to_dict(),
            "stripe_charge_description": "BidVex Fees Only",
            "hammer_price_note": "Hammer price ($" + f"{float(breakdown.hammer_price):,.2f}" + ") paid directly to seller via Bank Draft",
            "seller_is_tax_registered": False
        }
    else:
        seller_tier = seller.get("subscription_tier", "basic") if seller else "basic"
        seller_is_tax_registered = seller.get("is_tax_registered", False) if seller else False
        
        breakdown = calculate_general_checkout(
            hammer_price=hammer_price,
            buyer_tier=buyer_tier,
            seller_tier=seller_tier,
            seller_is_tax_registered=seller_is_tax_registered,
            include_processing_fee=True
        )
        
        return {
            "checkout_type": "general",
            "breakdown": breakdown.to_dict(),
            "stripe_charge_description": "Full Payment via Stripe",
            "seller_is_tax_registered": seller_is_tax_registered,
            "tax_on_item_note": "Tax on item (14.975%)" if seller_is_tax_registered else "No tax on item (private seller)"
        }


# ========== INVOICE DOWNLOAD ENDPOINT ==========

from fastapi.responses import FileResponse

@payments_router.get("/invoices/download/{invoice_id}")
async def download_invoice(invoice_id: str):
    """
    Download PDF invoice by ID
    
    Checks for invoice in /tmp/invoices directory
    """
    storage_dir = "/tmp/invoices"
    
    # Try marketplace invoice first
    filepath = os.path.join(storage_dir, f"marketplace_{invoice_id}.pdf")
    if os.path.exists(filepath):
        return FileResponse(
            filepath,
            media_type="application/pdf",
            filename=f"invoice_{invoice_id[:8]}.pdf"
        )
    
    # Try vehicle invoice
    filepath = os.path.join(storage_dir, f"vehicle_{invoice_id}.pdf")
    if os.path.exists(filepath):
        return FileResponse(
            filepath,
            media_type="application/pdf",
            filename=f"invoice_vehicle_{invoice_id[:8]}.pdf"
        )
    
    raise HTTPException(status_code=404, detail="Invoice not found")


@payments_router.get("/fees/processing")
async def get_processing_fee_info():
    """
    Get Stripe processing fee information
    
    Processing fee (2.9% + $0.30) is passed to buyer using gross-up formula.
    """
    return {
        "percentage_rate": float(STRIPE_PERCENTAGE_FEE),
        "percentage_display": "2.9%",
        "fixed_fee": float(STRIPE_FIXED_FEE),
        "fixed_fee_display": "$0.30",
        "description": "Card processing fee (2.9% + $0.30)",
        "gross_up_formula": "gross_amount = (net_amount + 0.30) / (1 - 0.029)",
        "example": {
            "net_to_receive": 100.00,
            "gross_charge": 103.30,
            "stripe_fee": 3.30
        }
    }



# ========== SUBSCRIPTION ENDPOINTS ==========

from services.subscription_service import (
    get_all_tiers,
    get_tier_benefits,
    create_subscription_checkout,
    get_user_subscription_status,
    STRIPE_PRICE_IDS,
    BUYER_PREMIUM_RATES,
    SELLER_COMMISSION_RATES,
)


@payments_router.get("/subscriptions/tiers")
async def get_subscription_tiers():
    """
    Get all available subscription tiers with pricing and benefits
    
    Returns:
        List of tiers: Free, Premium ($180/mo), VIP ($300/mo)
        Fee comparison table
    """
    return get_all_tiers()


@payments_router.get("/subscriptions/my-status")
async def get_my_subscription_status(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current user's subscription status and benefits
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    return await get_user_subscription_status(db, current_user.id)


class SubscriptionUpgradeRequest(BaseModel):
    tier: str = Field(..., description="Target tier: 'premium' or 'vip'")
    return_url: str = Field(..., description="URL to redirect after checkout")


@payments_router.post("/subscriptions/upgrade")
async def upgrade_subscription(
    request: SubscriptionUpgradeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create checkout session for subscription upgrade
    
    Args:
        tier: Target subscription tier ('premium' or 'vip')
        return_url: URL to redirect after checkout
    
    Returns:
        Stripe Checkout URL for subscription payment
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if request.tier.lower() not in ["premium", "vip"]:
        raise HTTPException(status_code=400, detail="Invalid tier. Must be 'premium' or 'vip'")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    result = await create_subscription_checkout(
        db=db,
        user_id=current_user.id,
        tier=request.tier.lower(),
        return_url=request.return_url
    )
    
    return result


@payments_router.get("/subscriptions/fee-rates")
async def get_fee_rates(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get fee rates for current user's subscription tier
    
    Used by tax calculation endpoints to apply correct rates.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    user = await db.users.find_one({"id": current_user.id})
    tier = user.get("subscription_tier", "free") if user else "free"
    
    return {
        "tier": tier,
        "buyer_premium_rate": BUYER_PREMIUM_RATES.get(tier, 0.05),
        "buyer_premium_display": f"{BUYER_PREMIUM_RATES.get(tier, 0.05) * 100:.1f}%",
        "seller_commission_rate": SELLER_COMMISSION_RATES.get(tier, 0.04),
        "seller_commission_display": f"{SELLER_COMMISSION_RATES.get(tier, 0.04) * 100:.1f}%",
        "all_rates": {
            "free": {"buyer": "5.0%", "seller": "4.0%"},
            "premium": {"buyer": "3.5%", "seller": "2.5%"},
            "vip": {"buyer": "3.0%", "seller": "2.0%"}
        }
    }


# ========== SELLER EARNINGS DASHBOARD ==========

@payments_router.get("/seller/earnings")
async def get_seller_earnings(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get seller earnings dashboard data
    
    Returns:
        - Total earned
        - Pending payouts
        - Available balance
        - Recent transactions
    """
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    user = await db.users.find_one({"id": current_user.id})
    connect_account_id = user.get("stripe_connect_account_id") if user else None
    
    if not connect_account_id:
        return {
            "has_connect_account": False,
            "message": "Please complete seller onboarding to view earnings",
            "onboarding_required": True
        }
    
    try:
        # Get Stripe Connect account balance
        balance = stripe.Balance.retrieve(stripe_account=connect_account_id)
        
        # Get available balance
        available = sum(
            b.get("amount", 0) 
            for b in balance.get("available", []) 
            if b.get("currency") == "cad"
        )
        
        # Get pending balance
        pending = sum(
            b.get("amount", 0) 
            for b in balance.get("pending", []) 
            if b.get("currency") == "cad"
        )
        
        # Get recent payouts
        payouts = stripe.Payout.list(
            limit=10,
            stripe_account=connect_account_id
        )
        
        recent_payouts = [
            {
                "id": p.id,
                "amount": p.amount / 100,
                "currency": p.currency.upper(),
                "status": p.status,
                "arrival_date": datetime.fromtimestamp(p.arrival_date, tz=timezone.utc).isoformat() if p.arrival_date else None,
                "created": datetime.fromtimestamp(p.created, tz=timezone.utc).isoformat()
            }
            for p in payouts.data
        ]
        
        # Get total earned from database
        total_earned_cursor = db.invoices.aggregate([
            {"$match": {"seller_id": current_user.id, "type": "marketplace_purchase"}},
            {"$group": {"_id": None, "total": {"$sum": "$breakdown.seller_payout"}}}
        ])
        total_earned_result = await total_earned_cursor.to_list(length=1)
        total_earned = total_earned_result[0]["total"] if total_earned_result else 0
        
        # Get account status
        account = stripe.Account.retrieve(connect_account_id)
        
        return {
            "has_connect_account": True,
            "account_id": connect_account_id,
            "payouts_enabled": account.payouts_enabled,
            "charges_enabled": account.charges_enabled,
            "financial_metrics": {
                "total_earned": total_earned,
                "total_earned_display": f"${total_earned:,.2f}",
                "pending_payouts": pending / 100,
                "pending_payouts_display": f"${pending / 100:,.2f}",
                "available_balance": available / 100,
                "available_balance_display": f"${available / 100:,.2f}",
                "currency": "CAD"
            },
            "recent_payouts": recent_payouts,
            "requirements": {
                "currently_due": list(account.requirements.currently_due) if account.requirements else [],
                "past_due": list(account.requirements.past_due) if account.requirements else []
            }
        }
        
    except stripe.StripeError as e:
        logger.error(f"Stripe error getting seller earnings: {e}")
        return {
            "has_connect_account": True,
            "error": "Unable to retrieve earnings data",
            "message": str(e)
        }


@payments_router.get("/seller/transactions")
async def get_seller_transactions(
    limit: int = 20,
    offset: int = 0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get seller's transaction history
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _get_current_user(credentials)
    
    # Get invoices where user is seller
    invoices_cursor = db.invoices.find(
        {"seller_id": current_user.id}
    ).sort("created_at", -1).skip(offset).limit(limit)
    
    invoices = await invoices_cursor.to_list(length=limit)
    
    transactions = []
    for inv in invoices:
        breakdown = inv.get("breakdown", {})
        transactions.append({
            "id": inv.get("id"),
            "type": inv.get("type", "sale"),
            "listing_id": inv.get("listing_id"),
            "auction_id": inv.get("auction_id"),
            "hammer_price": breakdown.get("hammer_price", 0),
            "seller_commission": breakdown.get("seller_commission", 0),
            "seller_payout": breakdown.get("seller_payout", 0),
            "created_at": inv.get("created_at"),
            "pdf_url": inv.get("pdf_url")
        })
    
    # Get total count
    total_count = await db.invoices.count_documents({"seller_id": current_user.id})
    
    return {
        "transactions": transactions,
        "total_count": total_count,
        "limit": limit,
        "offset": offset
    }
