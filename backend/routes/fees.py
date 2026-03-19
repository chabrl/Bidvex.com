"""
Fee calculation routes - buyer cost, seller net, subscription benefits
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Optional
from decimal import Decimal
from deps import get_current_user, get_db, User
import logging

logger = logging.getLogger(__name__)

fees_router = APIRouter(tags=["Fees"])


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
