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
            buyer_tier=request.buyer_tier
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
            seller_info=seller_info
        )
        return {
            "payment_type": "general",
            "description": "General auction - full amount charged via Stripe",
            **result.to_dict()
        }


@payments_router.get("/tax/vehicle")
async def calculate_vehicle_payment_with_tax(
    price: float,
    buyer_tier: str = "basic"
):
    """
    Calculate vehicle auction payment with Quebec taxes
    
    IMPORTANT: For vehicles, only BidVex fees are charged through Stripe.
    The hammer price is paid directly to seller via Bank Draft.
    
    Stripe charges: (Buyer Premium + Platform Fee) + 14.975% Tax
    
    Example for $10,000 vehicle (basic tier):
    - Buyer Premium (5%): $500
    - Platform Fee (2.5%): $250
    - Subtotal: $750
    - GST (5%): $37.50
    - QST (9.975%): $74.81
    - Total Stripe Charge: $862.31
    - Balance due to seller (Bank Draft): $10,000
    """
    result = calculate_vehicle_payment(
        hammer_price=price,
        buyer_tier=buyer_tier
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
