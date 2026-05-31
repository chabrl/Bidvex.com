"""
BidVex Hybrid Fee Calculation Engine
Handles differentiated fee structures for VEHICLE vs GENERAL auctions

VEHICLE Auctions:
- Buyer pays: Bid + (Bid * Tier Buyer Premium) + (Bid * 2.5% Platform Fee)
- Seller receives: 100% of Final Bid
- BidVex keeps: (Bid * Tier Buyer Premium) + (Bid * 2.5% Platform Fee)

GENERAL Auctions:
- Buyer pays: Bid + (Bid * Tier Buyer Premium)
- Seller receives: Bid - (Bid * Tier Seller Commission)
- BidVex keeps: (Bid * Tier Buyer Premium) + (Bid * Tier Seller Commission)

All Stripe amounts must be in cents (int(amount * 100))
"""

from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class AuctionCategory(str, Enum):
    """Auction category determining fee structure"""
    VEHICLE = "vehicle"
    GENERAL = "general"


class SubscriptionTier(str, Enum):
    """User subscription tier"""
    BASIC = "basic"
    STANDARD = "standard"  # Alias for basic
    PREMIUM = "premium"
    VIP_ELITE = "vip_elite"
    VIP = "vip"  # Alias for vip_elite


# ============= FEE RATES BY TIER =============

# Buyer Premium Rates (applied to all auctions)
BUYER_PREMIUM_RATES = {
    SubscriptionTier.BASIC: Decimal("0.05"),       # 5%
    SubscriptionTier.STANDARD: Decimal("0.05"),    # 5%
    SubscriptionTier.PREMIUM: Decimal("0.035"),    # 3.5%
    SubscriptionTier.VIP_ELITE: Decimal("0.03"),   # 3%
    SubscriptionTier.VIP: Decimal("0.03"),         # 3%
}

# Seller Commission Rates (GENERAL auctions only)
SELLER_COMMISSION_RATES = {
    SubscriptionTier.BASIC: Decimal("0.04"),       # 4%
    SubscriptionTier.STANDARD: Decimal("0.04"),    # 4%
    SubscriptionTier.PREMIUM: Decimal("0.025"),    # 2.5%
    SubscriptionTier.VIP_ELITE: Decimal("0.02"),   # 2%
    SubscriptionTier.VIP: Decimal("0.02"),         # 2%
}

# Platform Fee (VEHICLE auctions only)
VEHICLE_PLATFORM_FEE_RATE = Decimal("0.025")  # 2.5%


def _round_currency(amount: Decimal) -> Decimal:
    """Round to 2 decimal places for currency"""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_cents(amount: Decimal) -> int:
    """Convert decimal amount to cents (integer) for Stripe"""
    return int(_round_currency(amount) * 100)


def _normalize_tier(tier: str) -> SubscriptionTier:
    """Normalize tier string to SubscriptionTier enum"""
    tier_lower = tier.lower().strip() if tier else "basic"
    
    tier_map = {
        "basic": SubscriptionTier.BASIC,
        "standard": SubscriptionTier.STANDARD,
        "free": SubscriptionTier.BASIC,
        "premium": SubscriptionTier.PREMIUM,
        "vip": SubscriptionTier.VIP_ELITE,
        "vip_elite": SubscriptionTier.VIP_ELITE,
        "elite": SubscriptionTier.VIP_ELITE,
    }
    
    return tier_map.get(tier_lower, SubscriptionTier.BASIC)


def _normalize_category(category: str) -> AuctionCategory:
    """Normalize category string to AuctionCategory enum"""
    if not category:
        return AuctionCategory.GENERAL
    
    category_lower = category.lower().strip()
    
    vehicle_keywords = ["vehicle", "car", "auto", "automobile", "truck", "motorcycle", "suv", "van"]
    
    for keyword in vehicle_keywords:
        if keyword in category_lower:
            return AuctionCategory.VEHICLE
    
    return AuctionCategory.GENERAL


@dataclass
class FeeCalculationResult:
    """Complete fee calculation result for Stripe integration"""
    
    # Input values
    hammer_price: float
    hammer_price_cents: int
    category: str
    buyer_tier: str
    seller_tier: str
    
    # Buyer side
    buyer_premium_rate: float
    buyer_premium: float
    buyer_premium_cents: int
    platform_fee_rate: float
    platform_fee: float
    platform_fee_cents: int
    buyer_total: float
    buyer_total_cents: int
    
    # Seller side
    seller_commission_rate: float
    seller_commission: float
    seller_commission_cents: int
    seller_net_payout: float
    seller_net_payout_cents: int
    
    # BidVex revenue
    bidvex_revenue: float
    bidvex_revenue_cents: int
    
    # Stripe parameters
    stripe_amount_cents: int  # Amount to charge buyer
    stripe_application_fee_cents: int  # BidVex's cut
    stripe_transfer_amount_cents: int  # Amount to transfer to seller
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


def calculate_fees(
    hammer_price: float,
    category: str,
    buyer_tier: str = "basic",
    seller_tier: str = "basic"
) -> FeeCalculationResult:
    """
    Calculate all fees for an auction transaction
    
    Args:
        hammer_price: Winning bid amount (in dollars)
        category: Auction category ("vehicle" or "general")
        buyer_tier: Buyer's subscription tier
        seller_tier: Seller's subscription tier
    
    Returns:
        FeeCalculationResult with all amounts in dollars and cents
    """
    # Normalize inputs
    hp = Decimal(str(hammer_price))
    auction_category = _normalize_category(category)
    b_tier = _normalize_tier(buyer_tier)
    s_tier = _normalize_tier(seller_tier)
    
    # Get rates
    buyer_premium_rate = BUYER_PREMIUM_RATES[b_tier]
    seller_commission_rate = SELLER_COMMISSION_RATES[s_tier]
    
    # Calculate amounts based on category
    if auction_category == AuctionCategory.VEHICLE:
        # VEHICLE: Buyer pays premium + platform fee, Seller gets 100%
        buyer_premium = _round_currency(hp * buyer_premium_rate)
        platform_fee = _round_currency(hp * VEHICLE_PLATFORM_FEE_RATE)
        seller_commission = Decimal("0")
        
        buyer_total = hp + buyer_premium + platform_fee
        seller_net_payout = hp  # Seller gets 100% of hammer price
        bidvex_revenue = buyer_premium + platform_fee
        
        platform_fee_rate_float = float(VEHICLE_PLATFORM_FEE_RATE)
        seller_commission_rate_float = 0.0
        
    else:
        # GENERAL: Buyer pays premium only, Seller pays commission
        buyer_premium = _round_currency(hp * buyer_premium_rate)
        platform_fee = Decimal("0")
        seller_commission = _round_currency(hp * seller_commission_rate)
        
        buyer_total = hp + buyer_premium
        seller_net_payout = hp - seller_commission
        bidvex_revenue = buyer_premium + seller_commission
        
        platform_fee_rate_float = 0.0
        seller_commission_rate_float = float(seller_commission_rate)
    
    # Convert all to cents for Stripe
    hp_cents = _to_cents(hp)
    buyer_premium_cents = _to_cents(buyer_premium)
    platform_fee_cents = _to_cents(platform_fee)
    seller_commission_cents = _to_cents(seller_commission)
    buyer_total_cents = _to_cents(buyer_total)
    seller_net_payout_cents = _to_cents(seller_net_payout)
    bidvex_revenue_cents = _to_cents(bidvex_revenue)
    
    # Stripe parameters
    stripe_amount_cents = buyer_total_cents  # Total amount to charge buyer
    stripe_application_fee_cents = bidvex_revenue_cents  # BidVex's application fee
    stripe_transfer_amount_cents = seller_net_payout_cents  # Transfer to seller
    
    result = FeeCalculationResult(
        # Input values
        hammer_price=float(hp),
        hammer_price_cents=hp_cents,
        category=auction_category.value,
        buyer_tier=b_tier.value,
        seller_tier=s_tier.value,
        
        # Buyer side
        buyer_premium_rate=float(buyer_premium_rate),
        buyer_premium=float(buyer_premium),
        buyer_premium_cents=buyer_premium_cents,
        platform_fee_rate=platform_fee_rate_float,
        platform_fee=float(platform_fee),
        platform_fee_cents=platform_fee_cents,
        buyer_total=float(buyer_total),
        buyer_total_cents=buyer_total_cents,
        
        # Seller side
        seller_commission_rate=seller_commission_rate_float,
        seller_commission=float(seller_commission),
        seller_commission_cents=seller_commission_cents,
        seller_net_payout=float(seller_net_payout),
        seller_net_payout_cents=seller_net_payout_cents,
        
        # BidVex revenue
        bidvex_revenue=float(bidvex_revenue),
        bidvex_revenue_cents=bidvex_revenue_cents,
        
        # Stripe parameters
        stripe_amount_cents=stripe_amount_cents,
        stripe_application_fee_cents=stripe_application_fee_cents,
        stripe_transfer_amount_cents=stripe_transfer_amount_cents,
    )
    
    logger.debug(
        f"Fee calculation: category={auction_category.value}, "
        f"hp=${hammer_price:.2f}, buyer_total=${float(buyer_total):.2f}, "
        f"seller_net=${float(seller_net_payout):.2f}, bidvex=${float(bidvex_revenue):.2f}"
    )
    
    return result


async def calculate_fees_with_promotions(
    *,
    db,
    user_id: str,
    hammer_price: float,
    category: str,
    listing_type: str = "marketplace",
    buyer_tier: str = "basic",
    seller_tier: str = "basic",
    coupon_code: Optional[str] = None,
    record_usage: bool = False,
) -> Dict[str, Any]:
    """iter243 Mission 3 — Fee calculation with active-promotion overrides.

    Wraps the sync `calculate_fees()` then applies up-to-two promotion
    discounts:
      - One for `buyer_premium` (matches the buyer's `user_id`).
      - One for `seller_commission` (matches the seller's `user_id` —
        callers must invoke this twice, once per side, OR pass the
        seller_id separately. For simplicity here we apply ONLY the
        buyer-side discount; seller-side is computed in a sister
        function below.)

    The returned dict contains:
      - `base`: the raw FeeCalculationResult.to_dict()
      - `buyer_discount`: PromotionDiscount block (or `{applies: False}`)
      - `adjusted_buyer_premium`: post-discount buyer_premium
      - `adjusted_buyer_total`: post-discount buyer_total
      - `promotion_id` / `coupon_code`: for invoice metadata
    """
    from services.promotion_runtime import apply_and_record_discount

    base = calculate_fees(
        hammer_price=hammer_price,
        category=category,
        buyer_tier=buyer_tier,
        seller_tier=seller_tier,
    )

    discount = await apply_and_record_discount(
        db=db,
        user_id=user_id,
        transaction_type="buyer_premium",
        base_amount_cad=float(base.buyer_premium),
        listing_type=listing_type,
        coupon_code=coupon_code,
        record_usage=record_usage,
    )

    adj_buyer_premium = discount.final_amount if discount.applies else float(base.buyer_premium)
    adj_buyer_total = float(base.buyer_total) - (float(base.buyer_premium) - adj_buyer_premium)

    return {
        "base": {
            "buyer_premium": float(base.buyer_premium),
            "buyer_total": float(base.buyer_total),
            "seller_commission": float(base.seller_commission),
            "seller_net_payout": float(base.seller_net_payout),
            "bidvex_revenue": float(base.bidvex_revenue),
        },
        "buyer_discount": discount.to_dict(),
        "adjusted_buyer_premium": round(adj_buyer_premium, 2),
        "adjusted_buyer_total": round(max(0.0, adj_buyer_total), 2),
        "promotion_id": discount.promotion_id,
        "coupon_code": discount.coupon_code,
        "discount_amount": discount.discount_amount,
        "is_full_waiver": discount.is_full_waiver,
    }


async def calculate_seller_commission_with_promotions(
    *,
    db,
    seller_id: str,
    hammer_price: float,
    category: str,
    listing_type: str = "marketplace",
    seller_tier: str = "basic",
    coupon_code: Optional[str] = None,
    record_usage: bool = False,
) -> Dict[str, Any]:
    """iter243 Mission 3 — Seller-side commission discount override."""
    from services.promotion_runtime import apply_and_record_discount

    base = calculate_fees(
        hammer_price=hammer_price,
        category=category,
        seller_tier=seller_tier,
    )

    discount = await apply_and_record_discount(
        db=db,
        user_id=seller_id,
        transaction_type="seller_commission",
        base_amount_cad=float(base.seller_commission),
        listing_type=listing_type,
        coupon_code=coupon_code,
        record_usage=record_usage,
    )

    adj_commission = discount.final_amount if discount.applies else float(base.seller_commission)
    adj_payout = float(base.seller_net_payout) + (float(base.seller_commission) - adj_commission)

    return {
        "base": {
            "seller_commission": float(base.seller_commission),
            "seller_net_payout": float(base.seller_net_payout),
        },
        "seller_discount": discount.to_dict(),
        "adjusted_seller_commission": round(adj_commission, 2),
        "adjusted_seller_payout": round(adj_payout, 2),
        "promotion_id": discount.promotion_id,
        "coupon_code": discount.coupon_code,
        "discount_amount": discount.discount_amount,
        "is_full_waiver": discount.is_full_waiver,
    }


def calculate_vehicle_fees(
    hammer_price: float,
    buyer_tier: str = "basic"
) -> FeeCalculationResult:
    """
    Convenience function for vehicle auction fees
    
    VEHICLE Fee Structure:
    - Buyer pays: Bid + (Bid * Tier Buyer Premium) + (Bid * 2.5% Platform Fee)
    - Seller receives: 100% of Final Bid
    - BidVex keeps: Buyer Premium + Platform Fee
    """
    return calculate_fees(
        hammer_price=hammer_price,
        category="vehicle",
        buyer_tier=buyer_tier,
        seller_tier="basic"  # Seller tier irrelevant for vehicles
    )


def calculate_general_fees(
    hammer_price: float,
    buyer_tier: str = "basic",
    seller_tier: str = "basic"
) -> FeeCalculationResult:
    """
    Convenience function for general auction fees
    
    GENERAL Fee Structure:
    - Buyer pays: Bid + (Bid * Tier Buyer Premium)
    - Seller receives: Bid - (Bid * Tier Seller Commission)
    - BidVex keeps: Buyer Premium + Seller Commission
    """
    return calculate_fees(
        hammer_price=hammer_price,
        category="general",
        buyer_tier=buyer_tier,
        seller_tier=seller_tier
    )


def get_fee_structure_summary() -> Dict[str, Any]:
    """
    Get summary of fee structures for both auction types
    Useful for displaying fee information to users
    """
    return {
        "vehicle": {
            "description": "Vehicle Auctions (Cars, Trucks, Motorcycles, etc.)",
            "buyer_fees": {
                "buyer_premium": {
                    "basic": "5.0%",
                    "premium": "3.5%",
                    "vip_elite": "3.0%"
                },
                "platform_fee": "2.5%",
                "note": "Buyer pays hammer price + buyer premium + platform fee"
            },
            "seller_fees": {
                "commission": "0%",
                "note": "Seller receives 100% of the hammer price"
            },
            "bidvex_revenue": "Buyer premium + Platform fee"
        },
        "general": {
            "description": "General Auctions (Collectibles, Electronics, Art, etc.)",
            "buyer_fees": {
                "buyer_premium": {
                    "basic": "5.0%",
                    "premium": "3.5%",
                    "vip_elite": "3.0%"
                },
                "platform_fee": "0%",
                "note": "Buyer pays hammer price + buyer premium only"
            },
            "seller_fees": {
                "commission": {
                    "basic": "4.0%",
                    "premium": "2.5%",
                    "vip_elite": "2.0%"
                },
                "note": "Seller receives hammer price minus commission"
            },
            "bidvex_revenue": "Buyer premium + Seller commission"
        }
    }


def create_stripe_payment_intent_params(
    fee_result: FeeCalculationResult,
    seller_stripe_account_id: str,
    currency: str = "cad"
) -> Dict[str, Any]:
    """
    Generate Stripe PaymentIntent parameters from fee calculation
    
    Args:
        fee_result: FeeCalculationResult from calculate_fees()
        seller_stripe_account_id: Seller's Stripe Connect account ID
        currency: Currency code (default: cad)
    
    Returns:
        Dictionary ready to pass to stripe.PaymentIntent.create()
    """
    return {
        "amount": fee_result.stripe_amount_cents,
        "currency": currency,
        "application_fee_amount": fee_result.stripe_application_fee_cents,
        "transfer_data": {
            "destination": seller_stripe_account_id
        },
        "metadata": {
            "category": fee_result.category,
            "hammer_price": str(fee_result.hammer_price),
            "buyer_premium": str(fee_result.buyer_premium),
            "platform_fee": str(fee_result.platform_fee),
            "seller_commission": str(fee_result.seller_commission),
            "seller_net": str(fee_result.seller_net_payout),
            "bidvex_revenue": str(fee_result.bidvex_revenue),
        }
    }


def create_stripe_checkout_params(
    fee_result: FeeCalculationResult,
    seller_stripe_account_id: str,
    success_url: str,
    cancel_url: str,
    product_name: str,
    currency: str = "cad"
) -> Dict[str, Any]:
    """
    Generate Stripe Checkout Session parameters from fee calculation
    
    Args:
        fee_result: FeeCalculationResult from calculate_fees()
        seller_stripe_account_id: Seller's Stripe Connect account ID
        success_url: URL to redirect after successful payment
        cancel_url: URL to redirect if payment cancelled
        product_name: Name of the auction item
        currency: Currency code (default: cad)
    
    Returns:
        Dictionary ready to pass to stripe.checkout.Session.create()
    """
    return {
        "mode": "payment",
        "line_items": [{
            "price_data": {
                "currency": currency,
                "unit_amount": fee_result.stripe_amount_cents,
                "product_data": {
                    "name": product_name,
                    "description": f"Auction winning bid: ${fee_result.hammer_price:.2f}"
                }
            },
            "quantity": 1
        }],
        "payment_intent_data": {
            "application_fee_amount": fee_result.stripe_application_fee_cents,
            "transfer_data": {
                "destination": seller_stripe_account_id
            }
        },
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": {
            "category": fee_result.category,
            "hammer_price_cents": str(fee_result.hammer_price_cents),
            "buyer_total_cents": str(fee_result.buyer_total_cents),
            "application_fee_cents": str(fee_result.stripe_application_fee_cents),
        }
    }


# ============= EXPORTS =============

__all__ = [
    "AuctionCategory",
    "SubscriptionTier",
    "FeeCalculationResult",
    "calculate_fees",
    "calculate_vehicle_fees",
    "calculate_general_fees",
    "get_fee_structure_summary",
    "create_stripe_payment_intent_params",
    "create_stripe_checkout_params",
    "BUYER_PREMIUM_RATES",
    "SELLER_COMMISSION_RATES",
    "VEHICLE_PLATFORM_FEE_RATE",
]
