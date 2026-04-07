"""
BidVex Payments — Fee Calculations & Tax Compliance Sub-Router
Extracted from payments.py for modularity.
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional

from services.fee_calculation_engine import (
    calculate_fees,
    calculate_vehicle_fees,
    calculate_general_fees,
    get_fee_structure_summary,
)
from services.tax_engine import (
    calculate_vehicle_payment,
    calculate_general_payment,
    get_tax_structure_summary,
    SellerInfo,
    GST_RATE,
    QST_RATE,
    BIDVEX_GST_NUMBER,
    BIDVEX_QST_NUMBER,
)
from services.stripe_connect_service import (
    STRIPE_PERCENTAGE_FEE,
    STRIPE_FIXED_FEE,
)

fees_sub_router = APIRouter()


# ========== FEE CALCULATIONS ==========

class FeeCalculationRequest(BaseModel):
    hammer_price: float = Field(..., gt=0, description="Winning bid amount in dollars")
    category: str = Field(default="general", description="Auction category: 'vehicle' or 'general'")
    buyer_tier: str = Field(default="basic", description="Buyer subscription tier")
    seller_tier: str = Field(default="basic", description="Seller subscription tier")


@fees_sub_router.post("/fees/calculate")
async def calculate_auction_fees(request: FeeCalculationRequest):
    """Calculate complete fee breakdown for an auction transaction."""
    result = calculate_fees(
        hammer_price=request.hammer_price,
        category=request.category,
        buyer_tier=request.buyer_tier,
        seller_tier=request.seller_tier,
    )
    return result.to_dict()


@fees_sub_router.get("/fees/calculate-hybrid")
async def calculate_hybrid_fees(
    price: float,
    category: str = "general",
    buyer_tier: str = "basic",
    seller_tier: str = "basic",
):
    """GET endpoint for fee calculation (alternative to POST)."""
    result = calculate_fees(
        hammer_price=price,
        category=category,
        buyer_tier=buyer_tier,
        seller_tier=seller_tier,
    )
    return result.to_dict()


@fees_sub_router.get("/fees/vehicle")
async def calculate_vehicle_auction_fees(price: float, buyer_tier: str = "basic"):
    """Calculate fees specifically for vehicle auctions."""
    result = calculate_vehicle_fees(hammer_price=price, buyer_tier=buyer_tier)
    return {
        "auction_type": "vehicle",
        "hammer_price": result.hammer_price,
        "buyer": {
            "premium_rate": f"{result.buyer_premium_rate * 100:.1f}%",
            "premium_amount": result.buyer_premium,
            "platform_fee_rate": f"{result.platform_fee_rate * 100:.1f}%",
            "platform_fee_amount": result.platform_fee,
            "total_cost": result.buyer_total,
            "total_cost_cents": result.buyer_total_cents,
        },
        "seller": {
            "commission_rate": "0%",
            "commission_amount": 0.0,
            "net_payout": result.seller_net_payout,
            "net_payout_cents": result.seller_net_payout_cents,
        },
        "bidvex": {"revenue": result.bidvex_revenue, "revenue_cents": result.bidvex_revenue_cents},
        "stripe": {
            "amount_cents": result.stripe_amount_cents,
            "application_fee_cents": result.stripe_application_fee_cents,
            "transfer_amount_cents": result.stripe_transfer_amount_cents,
        },
    }


@fees_sub_router.get("/fees/general")
async def calculate_general_auction_fees(
    price: float, buyer_tier: str = "basic", seller_tier: str = "basic"
):
    """Calculate fees specifically for general auctions."""
    result = calculate_general_fees(hammer_price=price, buyer_tier=buyer_tier, seller_tier=seller_tier)
    return {
        "auction_type": "general",
        "hammer_price": result.hammer_price,
        "buyer": {
            "premium_rate": f"{result.buyer_premium_rate * 100:.1f}%",
            "premium_amount": result.buyer_premium,
            "platform_fee_rate": "0%",
            "platform_fee_amount": 0.0,
            "total_cost": result.buyer_total,
            "total_cost_cents": result.buyer_total_cents,
        },
        "seller": {
            "commission_rate": f"{result.seller_commission_rate * 100:.1f}%",
            "commission_amount": result.seller_commission,
            "net_payout": result.seller_net_payout,
            "net_payout_cents": result.seller_net_payout_cents,
        },
        "bidvex": {"revenue": result.bidvex_revenue, "revenue_cents": result.bidvex_revenue_cents},
        "stripe": {
            "amount_cents": result.stripe_amount_cents,
            "application_fee_cents": result.stripe_application_fee_cents,
            "transfer_amount_cents": result.stripe_transfer_amount_cents,
        },
    }


@fees_sub_router.get("/fees/structure")
async def get_fee_structures():
    """Get complete fee structure documentation for both auction types."""
    return get_fee_structure_summary()


@fees_sub_router.get("/fees/calculate-buyer-cost")
async def calculate_buyer_cost(price: float, tier: str = "free"):
    """Calculate total buyer cost including fees (legacy endpoint)."""
    rates = {"free": 0.10, "premium": 0.08, "vip": 0.05}
    rate = rates.get(tier, rates["free"])
    buyer_premium = price * rate
    total = price + buyer_premium
    return {
        "base_price": price,
        "buyer_premium": round(buyer_premium, 2),
        "buyer_premium_rate": rate,
        "total_cost": round(total, 2),
    }


@fees_sub_router.get("/fees/calculate-seller-net")
async def calculate_seller_net(price: float, tier: str = "free"):
    """Calculate seller net after commission (legacy endpoint)."""
    rates = {"free": 0.04, "premium": 0.025, "vip": 0.02}
    rate = rates.get(tier, rates["free"])
    commission = price * rate
    net = price - commission
    return {
        "sale_price": price,
        "commission": round(commission, 2),
        "commission_rate": rate,
        "seller_net": round(net, 2),
    }


@fees_sub_router.get("/fees/subscription-benefits")
async def get_subscription_benefits():
    """Get subscription tier benefits breakdown."""
    return {
        "free": {
            "commission_rate": 0.04,
            "buyer_premium": 0.10,
            "email_sends_monthly": 0,
            "contact_limit": 50,
            "features": ["Basic listings", "Standard support"],
        },
        "premium": {
            "commission_rate": 0.025,
            "buyer_premium": 0.08,
            "email_sends_monthly": 5000,
            "contact_limit": 5000,
            "features": ["Lower commission", "Email marketing (500/day)", "Priority support", "Analytics dashboard"],
        },
        "vip": {
            "commission_rate": 0.02,
            "buyer_premium": 0.05,
            "email_sends_monthly": 50000,
            "contact_limit": 25000,
            "features": ["Lowest commission", "Email marketing (2000/day)", "Priority sending", "Dedicated support", "Advanced analytics"],
        },
    }


@fees_sub_router.get("/fees/processing")
async def get_processing_fee_info():
    """Get Stripe processing fee information."""
    return {
        "percentage_rate": float(STRIPE_PERCENTAGE_FEE),
        "percentage_display": "2.9%",
        "fixed_fee": float(STRIPE_FIXED_FEE),
        "fixed_fee_display": "$0.30",
        "description": "Card processing fee (2.9% + $0.30)",
        "gross_up_formula": "gross_amount = (net_amount + 0.30) / (1 - 0.029)",
        "example": {"net_to_receive": 100.00, "gross_charge": 103.30, "stripe_fee": 3.30},
    }


# ========== TAX & COMPLIANCE ENDPOINTS ==========

class TaxCalculationRequest(BaseModel):
    hammer_price: float = Field(..., gt=0, description="Winning bid amount in dollars")
    category: str = Field(default="general", description="Auction category")
    buyer_tier: str = Field(default="basic", description="Buyer subscription tier")
    seller_tier: str = Field(default="basic", description="Seller subscription tier")
    seller_is_business: bool = Field(default=False, description="Whether seller is a registered business")
    seller_gst_number: Optional[str] = Field(default=None)
    seller_qst_number: Optional[str] = Field(default=None)
    buyers_premium_rate: Optional[float] = Field(default=None, description="Listing-level buyer premium rate override")


@fees_sub_router.post("/tax/calculate")
async def calculate_payment_with_tax(request: TaxCalculationRequest):
    """Calculate complete payment breakdown with Quebec taxes (GST/QST)."""
    category_lower = request.category.lower()

    if category_lower in ["vehicle", "car", "auto", "automobile", "truck", "motorcycle"]:
        result = calculate_vehicle_payment(
            hammer_price=request.hammer_price,
            buyer_tier=request.buyer_tier,
            buyer_premium_rate_override=request.buyers_premium_rate,
        )
        return {"payment_type": "vehicle", "description": "Vehicle auction - BidVex fees charged via Stripe, hammer price paid directly to seller", **result.to_dict()}
    else:
        seller_info = (
            SellerInfo(is_business=request.seller_is_business, gst_number=request.seller_gst_number, qst_number=request.seller_qst_number)
            if request.seller_is_business
            else None
        )
        result = calculate_general_payment(
            hammer_price=request.hammer_price,
            buyer_tier=request.buyer_tier,
            seller_tier=request.seller_tier,
            seller_is_business=request.seller_is_business,
            seller_info=seller_info,
            buyer_premium_rate_override=request.buyers_premium_rate,
        )
        return {"payment_type": "general", "description": "General auction - full amount charged via Stripe", **result.to_dict()}


@fees_sub_router.get("/tax/vehicle")
async def calculate_vehicle_payment_with_tax(
    price: float, buyer_tier: str = "basic", buyers_premium_rate: Optional[float] = None
):
    """Calculate vehicle auction payment with Quebec taxes."""
    result = calculate_vehicle_payment(hammer_price=price, buyer_tier=buyer_tier, buyer_premium_rate_override=buyers_premium_rate)
    return {"auction_type": "vehicle", "payment_method": "hybrid", "description": "BidVex fees charged via Stripe, hammer price via Bank Draft to seller", **result.to_dict()}


@fees_sub_router.get("/tax/general")
async def calculate_general_payment_with_tax(
    price: float, buyer_tier: str = "basic", seller_tier: str = "basic", seller_is_business: bool = False
):
    """Calculate general auction payment with Quebec taxes."""
    result = calculate_general_payment(
        hammer_price=price, buyer_tier=buyer_tier, seller_tier=seller_tier, seller_is_business=seller_is_business
    )
    return {
        "auction_type": "general",
        "payment_method": "stripe_full",
        "description": "Full amount charged via Stripe" + (" (tax collected on behalf of business seller)" if seller_is_business else ""),
        **result.to_dict(),
    }


@fees_sub_router.get("/tax/structure")
async def get_tax_structure():
    """Get Quebec tax structure documentation."""
    return get_tax_structure_summary()


@fees_sub_router.get("/tax/rates")
async def get_tax_rates():
    """Get current Quebec tax rates."""
    return {
        "jurisdiction": "Quebec, Canada",
        "gst": {"name": "Goods and Services Tax (Federal)", "rate": float(GST_RATE), "rate_display": "5%", "registration": BIDVEX_GST_NUMBER},
        "qst": {"name": "Quebec Sales Tax (Provincial)", "rate": float(QST_RATE), "rate_display": "9.975%", "registration": BIDVEX_QST_NUMBER},
        "combined": {"name": "Total Quebec Tax", "rate": float(GST_RATE) + float(QST_RATE), "rate_display": "14.975%"},
    }
