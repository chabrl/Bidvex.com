"""
Fee calculation routes - buyer cost, seller net, subscription benefits
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from typing import Optional
from decimal import Decimal
from deps import get_current_user, get_db, User
from rate_limit import limiter as _limiter
import logging

logger = logging.getLogger(__name__)

fees_router = APIRouter(tags=["Fees"])


# ─── Live Fee Estimate (public — for front-end cost breakdown preview) ───

@fees_router.get("/fees/estimate")
@_limiter.limit("60/minute")
async def fees_estimate(
    request: Request,
    hammer_price: float = Query(..., gt=0, description="Bid / Buy-now price in CAD"),
    auction_type: str = Query("marketplace", description="marketplace | lots | storage | vehicle"),
    user_id: Optional[str] = Query(None, description="Buyer user id — used to look up subscription tier"),
    buyer_province: str = Query("QC", description="Buyer's province (affects QST eligibility)"),
    card_type: str = Query("domestic", description="domestic | international | conversion — defaults to domestic"),
):
    """Live cost-breakdown preview for the bidder UI.

    - Public (amounts are not sensitive, no user data leaked).
    - Rate-limited to 60 req/min per IP (for debounced typing at ~400ms that
      still leaves headroom for a human bidder).
    - Uses the same gross-up Stripe formula as the real checkout, so what
      the buyer sees here exactly matches what Stripe will charge.
    """
    from services.pricing_manager import PricingManager, gross_up_stripe_fee, _r
    from decimal import Decimal as D

    # Look up buyer's subscription tier when user_id is supplied. Silent
    # fallback to "free" when the lookup fails (public endpoint — never 500).
    buyer_tier = "free"
    if user_id:
        try:
            db = get_db()
            _user = await db.users.find_one({"id": user_id}, {"_id": 0, "subscription_tier": 1})
            if _user:
                buyer_tier = _user.get("subscription_tier", "free")
        except Exception:
            pass

    at = (auction_type or "marketplace").lower()
    hp = D(str(hammer_price))

    try:
        if at == "vehicle":
            pr = PricingManager.vehicle_auction(hp, buyer_province)
            # Vehicle: platform_fee (2.5%) + tax on fee + Stripe on fee only.
            buyer_premium_rate = 0.025
            buyer_premium = float(pr.buyer_invoice.fees_subtotal or 0)
            total_taxes = float(pr.buyer_invoice.tax_amount or 0)
            subtotal = buyer_premium + total_taxes
            # Gross-up using requested card_type (defaults to domestic)
            stripe_fee = float(gross_up_stripe_fee(D(str(subtotal)), card_type=card_type))
        else:
            # Marketplace / Lots / Storage — standard "non_vehicle_stripe" path
            pr = PricingManager.non_vehicle_stripe(hp, buyer_province, buyer_tier, "free")
            buyer_premium = float(pr.buyer_invoice.fees_subtotal or 0)
            total_taxes = float(pr.buyer_invoice.tax_amount or 0)
            subtotal = float(hp) + buyer_premium + total_taxes
            # Re-compute Stripe gross-up using caller's card_type so the preview
            # can show what an international / conversion card would cost.
            stripe_fee = float(gross_up_stripe_fee(D(str(subtotal)), card_type=card_type))
            # Infer rate
            buyer_premium_rate = (buyer_premium / float(hp)) if float(hp) > 0 else 0.0

        grand_total = subtotal + stripe_fee
        # Split GST / QST for display using the standard Quebec ratios
        gst_rate = 0.05
        qst_rate = 0.09975
        combined = gst_rate + qst_rate
        gst = round(total_taxes * (gst_rate / combined), 2) if combined > 0 else 0.0
        qst = round(total_taxes - gst, 2)

        return {
            "hammer_price":        float(hp),
            "auction_type":        at,
            "buyer_tier":          buyer_tier,
            "buyer_premium_rate":  round(buyer_premium_rate, 4),
            "buyer_premium":       buyer_premium,
            "gst":                 gst,
            "qst":                 qst,
            "total_taxes":         total_taxes,
            "subtotal":            round(subtotal, 2),
            "stripe_fee_estimate": stripe_fee,
            "card_type":           card_type,
            "grand_total":         round(grand_total, 2),
            "stripe_amount_cents": int(round(grand_total * 100)),
            "currency":            "CAD",
        }
    except Exception as e:
        logger.exception(f"/fees/estimate failed: {e}")
        raise HTTPException(status_code=400, detail=f"Could not calculate fee estimate: {e}")


def _round_cents(v: float) -> float:
    """Round to 2 decimal places, handling floating-point drift cleanly."""
    return round(v + 1e-9, 2)


@fees_router.get("/fees/calculate-buyer-cost")
async def calculate_buyer_cost(
    amount: float,
    region: str = "QC",
    seller_is_business: bool = False,
    current_user: User = Depends(get_current_user)
):
    """Calculate buyer's total out-of-pocket cost BEFORE bid confirmation"""
    try:
        from services.fee_calculator import calculate_buyer_total
        db = get_db()
        buyer_tier = current_user.subscription_tier or "free"

        calculation = calculate_buyer_total(
            amount=amount,
            tier=buyer_tier,
            region=region,
            seller_is_business=seller_is_business
        )

        explanation = f"Your total cost includes: ${calculation['hammer_price']:.2f} hammer price"
        if seller_is_business:
            explanation += f" + ${calculation['buyer_premium']:.2f} buyer premium ({calculation['buyer_premium_percent']}%) + ${calculation['tax']:.2f} taxes = ${calculation['total']:.2f} total"
        else:
            explanation += f" (no tax on private sale!) + ${calculation['buyer_premium']:.2f} buyer premium ({calculation['buyer_premium_percent']}%) + ${calculation['tax_on_premium']:.2f} tax on premium = ${calculation['total']:.2f} total"
            if calculation.get('tax_savings', 0) > 0:
                explanation += f" | YOU SAVE ${calculation['tax_savings']:.2f} compared to business sellers!"

        return {"success": True, **calculation, "explanation": explanation}
    except Exception as e:
        logger.error(f"Error calculating buyer cost: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate cost")


@fees_router.get("/fees/calculate-seller-net")
async def calculate_seller_net_endpoint(
    amount: float,
    current_user: User = Depends(get_current_user)
):
    """Calculate seller's net payout after commission"""
    try:
        from services.fee_calculator import calculate_seller_net
        seller_tier = current_user.subscription_tier or "free"
        calculation = calculate_seller_net(amount=amount, tier=seller_tier)
        return {
            "success": True,
            **calculation,
            "explanation": f"You will receive: ${calculation['hammer_price']:.2f} - ${calculation['seller_commission']:.2f} commission ({calculation['seller_commission_percent']}%) = ${calculation['net_payout']:.2f} net payout"
        }
    except Exception as e:
        logger.error(f"Error calculating seller net: {e}")
        raise HTTPException(status_code=500, detail="Failed to calculate net")


@fees_router.get("/fees/subscription-benefits")
async def get_subscription_benefits():
    """Public endpoint showing fee benefits for each subscription tier"""
    return {
        "success": True,
        "tiers": {
            "free": {
                "name": "Starter (Free)",
                "price": "$0",
                "buyer_premium": "5%",
                "seller_commission": "4%",
                "features": ["Basic bidding", "Standard support", "Wishlist access"]
            },
            "premium": {
                "name": "BidVex Premium",
                "price": "$180 CAD/year + taxes",
                "price_note": "Billed annually",
                "buyer_premium": "3.5%",
                "seller_commission": "2.5%",
                "discount": "1.5% buyer discount + 1.5% seller discount",
                "features": [
                    "1.5% lower buyer fees (5% → 3.5%)",
                    "1.5% lower seller fees (4% → 2.5%)",
                    "Auto-Bid Bot",
                    "Priority notifications",
                    "Premium Seller badge",
                    "3-day listing promotion"
                ]
            },
            "vip": {
                "name": "BidVex VIP",
                "price": "$300 CAD/year + taxes",
                "price_note": "Billed annually",
                "buyer_premium": "3%",
                "seller_commission": "2%",
                "discount": "2% buyer discount + 2% seller discount",
                "features": [
                    "2% lower buyer fees (5% → 3%)",
                    "2% lower seller fees (4% → 2%)",
                    "Auto-Bid Bot",
                    "Priority notifications",
                    "VIP Seller badge",
                    "7-day listing promotion",
                    "24h early access to auctions",
                    "Advanced analytics dashboard",
                    "Dedicated support"
                ]
            }
        }
    }


@fees_router.post("/fees/estimate-transaction")
async def estimate_full_transaction(
    hammer_price: float,
    buyer_id: Optional[str] = None,
    seller_id: Optional[str] = None,
    region: str = "QC",
    current_user: User = Depends(get_current_user)
):
    """Estimate complete transaction costs for both buyer and seller"""
    try:
        from services.fee_calculator import FeeCalculator
        db = get_db()
        buyer_tier = "free"
        seller_tier = "free"
        seller_is_business = False

        if buyer_id:
            buyer = await db.users.find_one({"id": buyer_id})
            if buyer:
                buyer_tier = buyer.get("subscription_tier", "free")
        if seller_id:
            seller = await db.users.find_one({"id": seller_id})
            if seller:
                seller_tier = seller.get("subscription_tier", "free")
                seller_is_business = seller.get("is_tax_registered", False)

        transaction = FeeCalculator.calculate_full_transaction(
            hammer_price=Decimal(str(hammer_price)),
            buyer_tier=buyer_tier,
            seller_tier=seller_tier,
            region=region,
            seller_is_business=seller_is_business
        )
        return {"success": True, **transaction}
    except Exception as e:
        logger.error(f"Error estimating transaction: {e}")
        raise HTTPException(status_code=500, detail="Failed to estimate transaction")
