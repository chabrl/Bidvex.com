"""
BidVex Vehicle Auction - Pricing & Tax Engine
Complete financial calculation system for vehicle auctions

Fee Structure:
- Seller Commission: 4% (Standard), 2.5% (Premium), 2% (VIP Elite)
- Buyer Premium: 5% (Standard), 3.5% (Premium), 3% (VIP Elite)
- Platform Fee: 2.5%

Canadian Tax Rates:
- GST: 5% (Federal)
- QST: 9.975% (Quebec)
- PST: BC 7%, SK 6%, MB 8%
- HST: ON 13%, NS/NB/NL/PEI 15%
"""

from typing import Dict, Any, Optional, Literal
from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum


class SubscriptionTier(str, Enum):
    BASIC = "basic"
    PREMIUM = "premium"
    VIP_ELITE = "vip_elite"


class Province(str, Enum):
    # HST Provinces
    ONTARIO = "ON"
    NOVA_SCOTIA = "NS"
    NEW_BRUNSWICK = "NB"
    NEWFOUNDLAND = "NL"
    PEI = "PE"
    # GST + PST Provinces
    BRITISH_COLUMBIA = "BC"
    SASKATCHEWAN = "SK"
    MANITOBA = "MB"
    # GST + QST Province
    QUEBEC = "QC"
    # GST Only
    ALBERTA = "AB"
    YUKON = "YT"
    NORTHWEST_TERRITORIES = "NT"
    NUNAVUT = "NU"


# ============= FEE STRUCTURE =============

SELLER_COMMISSION_RATES = {
    SubscriptionTier.BASIC: Decimal("0.04"),      # 4%
    SubscriptionTier.PREMIUM: Decimal("0.025"),   # 2.5%
    SubscriptionTier.VIP_ELITE: Decimal("0.02"),  # 2%
}

BUYER_PREMIUM_RATES = {
    SubscriptionTier.BASIC: Decimal("0.05"),      # 5%
    SubscriptionTier.PREMIUM: Decimal("0.035"),   # 3.5%
    SubscriptionTier.VIP_ELITE: Decimal("0.03"),  # 3%
}

PLATFORM_FEE_RATE = Decimal("0.025")  # 2.5%

# ============= TAX RATES =============

# Federal GST
GST_RATE = Decimal("0.05")  # 5%

# Provincial taxes
PROVINCIAL_TAX_RATES = {
    # HST Provinces (combined federal + provincial)
    Province.ONTARIO: {"type": "HST", "rate": Decimal("0.13")},
    Province.NOVA_SCOTIA: {"type": "HST", "rate": Decimal("0.15")},
    Province.NEW_BRUNSWICK: {"type": "HST", "rate": Decimal("0.15")},
    Province.NEWFOUNDLAND: {"type": "HST", "rate": Decimal("0.15")},
    Province.PEI: {"type": "HST", "rate": Decimal("0.15")},
    
    # GST + PST Provinces
    Province.BRITISH_COLUMBIA: {"type": "GST+PST", "gst": GST_RATE, "pst": Decimal("0.07")},
    Province.SASKATCHEWAN: {"type": "GST+PST", "gst": GST_RATE, "pst": Decimal("0.06")},
    Province.MANITOBA: {"type": "GST+PST", "gst": GST_RATE, "pst": Decimal("0.07")},  # RST 7%
    
    # GST + QST Province
    Province.QUEBEC: {"type": "GST+QST", "gst": GST_RATE, "qst": Decimal("0.09975")},
    
    # GST Only
    Province.ALBERTA: {"type": "GST", "gst": GST_RATE},
    Province.YUKON: {"type": "GST", "gst": GST_RATE},
    Province.NORTHWEST_TERRITORIES: {"type": "GST", "gst": GST_RATE},
    Province.NUNAVUT: {"type": "GST", "gst": GST_RATE},
}

# Late payment penalty
LATE_PAYMENT_MONTHLY_RATE = Decimal("0.02")  # 2% per month
PAYMENT_DEADLINE_DAYS = 14


@dataclass
class TaxBreakdown:
    """Tax calculation breakdown"""
    province: str
    tax_type: str
    gst_amount: Decimal = Decimal("0")
    gst_rate: Decimal = Decimal("0")
    pst_amount: Decimal = Decimal("0")
    pst_rate: Decimal = Decimal("0")
    qst_amount: Decimal = Decimal("0")
    qst_rate: Decimal = Decimal("0")
    hst_amount: Decimal = Decimal("0")
    hst_rate: Decimal = Decimal("0")
    total_tax: Decimal = Decimal("0")
    total_rate: Decimal = Decimal("0")


@dataclass
class BuyerPricingBreakdown:
    """Complete pricing breakdown for buyer"""
    hammer_price: Decimal
    buyer_premium: Decimal
    buyer_premium_rate: Decimal
    platform_fee: Decimal
    platform_fee_rate: Decimal
    subtotal_before_tax: Decimal
    tax_breakdown: TaxBreakdown
    total_payable: Decimal
    subscription_tier: str
    discount_applied: Decimal  # Amount saved vs basic tier


@dataclass
class SellerPricingBreakdown:
    """Complete pricing breakdown for seller"""
    hammer_price: Decimal
    seller_commission: Decimal
    seller_commission_rate: Decimal
    net_payout: Decimal
    subscription_tier: str
    discount_applied: Decimal  # Amount saved vs basic tier


def _round_currency(amount: Decimal) -> Decimal:
    """Round to 2 decimal places for currency"""
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def get_subscription_tier(user: dict) -> SubscriptionTier:
    """Extract subscription tier from user profile"""
    tier = user.get("subscription_tier", "basic")
    if tier in ["premium", "Premium"]:
        return SubscriptionTier.PREMIUM
    elif tier in ["vip_elite", "vip", "VIP", "VIP Elite", "elite"]:
        return SubscriptionTier.VIP_ELITE
    return SubscriptionTier.BASIC


def calculate_taxes(taxable_amount: Decimal, province_code: str) -> TaxBreakdown:
    """
    Calculate taxes based on buyer's province
    Applies to: Hammer Price + Buyer Premium + Platform Fee
    """
    try:
        province = Province(province_code.upper())
    except ValueError:
        # Default to Alberta (GST only) for unknown provinces
        province = Province.ALBERTA
    
    tax_info = PROVINCIAL_TAX_RATES.get(province, PROVINCIAL_TAX_RATES[Province.ALBERTA])
    tax_type = tax_info["type"]
    
    breakdown = TaxBreakdown(
        province=province_code.upper(),
        tax_type=tax_type
    )
    
    if tax_type == "HST":
        # Combined HST
        breakdown.hst_rate = tax_info["rate"]
        breakdown.hst_amount = _round_currency(taxable_amount * breakdown.hst_rate)
        breakdown.total_tax = breakdown.hst_amount
        breakdown.total_rate = breakdown.hst_rate
        
    elif tax_type == "GST+PST":
        # Separate GST and PST
        breakdown.gst_rate = tax_info["gst"]
        breakdown.pst_rate = tax_info["pst"]
        breakdown.gst_amount = _round_currency(taxable_amount * breakdown.gst_rate)
        breakdown.pst_amount = _round_currency(taxable_amount * breakdown.pst_rate)
        breakdown.total_tax = breakdown.gst_amount + breakdown.pst_amount
        breakdown.total_rate = breakdown.gst_rate + breakdown.pst_rate
        
    elif tax_type == "GST+QST":
        # Quebec: GST + QST (QST calculated on pre-tax amount)
        breakdown.gst_rate = tax_info["gst"]
        breakdown.qst_rate = tax_info["qst"]
        breakdown.gst_amount = _round_currency(taxable_amount * breakdown.gst_rate)
        breakdown.qst_amount = _round_currency(taxable_amount * breakdown.qst_rate)
        breakdown.total_tax = breakdown.gst_amount + breakdown.qst_amount
        breakdown.total_rate = breakdown.gst_rate + breakdown.qst_rate
        
    else:  # GST only
        breakdown.gst_rate = tax_info["gst"]
        breakdown.gst_amount = _round_currency(taxable_amount * breakdown.gst_rate)
        breakdown.total_tax = breakdown.gst_amount
        breakdown.total_rate = breakdown.gst_rate
    
    return breakdown


def calculate_buyer_pricing(
    hammer_price: float,
    buyer_province: str,
    buyer_subscription_tier: SubscriptionTier = SubscriptionTier.BASIC
) -> BuyerPricingBreakdown:
    """
    Calculate complete buyer pricing breakdown
    
    Components:
    1. Hammer Price (winning bid)
    2. Buyer Premium (5%, 3.5%, or 3% based on tier)
    3. Platform Fee (2.5%)
    4. Taxes (province-based)
    
    Returns complete breakdown with all amounts
    """
    hp = Decimal(str(hammer_price))
    
    # Get buyer premium rate based on subscription
    premium_rate = BUYER_PREMIUM_RATES[buyer_subscription_tier]
    basic_premium_rate = BUYER_PREMIUM_RATES[SubscriptionTier.BASIC]
    
    # Calculate amounts
    buyer_premium = _round_currency(hp * premium_rate)
    platform_fee = _round_currency(hp * PLATFORM_FEE_RATE)
    
    # Subtotal before tax
    subtotal = hp + buyer_premium + platform_fee
    
    # Calculate taxes on subtotal
    tax_breakdown = calculate_taxes(subtotal, buyer_province)
    
    # Total payable
    total = subtotal + tax_breakdown.total_tax
    
    # Calculate discount vs basic tier
    basic_premium = _round_currency(hp * basic_premium_rate)
    discount = basic_premium - buyer_premium
    
    return BuyerPricingBreakdown(
        hammer_price=hp,
        buyer_premium=buyer_premium,
        buyer_premium_rate=premium_rate,
        platform_fee=platform_fee,
        platform_fee_rate=PLATFORM_FEE_RATE,
        subtotal_before_tax=subtotal,
        tax_breakdown=tax_breakdown,
        total_payable=_round_currency(total),
        subscription_tier=buyer_subscription_tier.value,
        discount_applied=discount
    )


def calculate_seller_pricing(
    hammer_price: float,
    seller_subscription_tier: SubscriptionTier = SubscriptionTier.BASIC
) -> SellerPricingBreakdown:
    """
    Calculate seller commission and net payout
    
    Commission Rates:
    - Basic: 4%
    - Premium: 2.5%
    - VIP Elite: 2%
    
    Net Payout = Hammer Price - Commission
    """
    hp = Decimal(str(hammer_price))
    
    # Get commission rate based on subscription
    commission_rate = SELLER_COMMISSION_RATES[seller_subscription_tier]
    basic_commission_rate = SELLER_COMMISSION_RATES[SubscriptionTier.BASIC]
    
    # Calculate commission
    commission = _round_currency(hp * commission_rate)
    
    # Net payout
    net_payout = hp - commission
    
    # Calculate discount vs basic tier
    basic_commission = _round_currency(hp * basic_commission_rate)
    discount = basic_commission - commission
    
    return SellerPricingBreakdown(
        hammer_price=hp,
        seller_commission=commission,
        seller_commission_rate=commission_rate,
        net_payout=net_payout,
        subscription_tier=seller_subscription_tier.value,
        discount_applied=discount
    )


def calculate_late_penalty(
    original_amount: float,
    days_overdue: int
) -> Dict[str, Any]:
    """
    Calculate late payment penalty
    2% monthly interest on outstanding balance
    """
    amount = Decimal(str(original_amount))
    
    if days_overdue <= 0:
        return {
            "original_amount": float(amount),
            "penalty_amount": 0.0,
            "total_due": float(amount),
            "days_overdue": 0,
            "monthly_rate": float(LATE_PAYMENT_MONTHLY_RATE)
        }
    
    # Calculate months overdue (partial months count as full)
    months_overdue = (days_overdue + 29) // 30  # Round up to nearest month
    
    # Compound interest calculation
    penalty_rate = (1 + LATE_PAYMENT_MONTHLY_RATE) ** months_overdue - 1
    penalty_amount = _round_currency(amount * penalty_rate)
    
    return {
        "original_amount": float(amount),
        "penalty_amount": float(penalty_amount),
        "total_due": float(amount + penalty_amount),
        "days_overdue": days_overdue,
        "months_overdue": months_overdue,
        "monthly_rate": float(LATE_PAYMENT_MONTHLY_RATE)
    }


def get_pricing_estimate(
    starting_price: float,
    buyer_province: str,
    buyer_tier: str = "basic",
    seller_tier: str = "basic"
) -> Dict[str, Any]:
    """
    Get pricing estimate for auction listing page
    Shows potential fees before bidding
    """
    # Parse tiers
    try:
        b_tier = SubscriptionTier(buyer_tier.lower())
    except ValueError:
        b_tier = SubscriptionTier.BASIC
        
    try:
        s_tier = SubscriptionTier(seller_tier.lower())
    except ValueError:
        s_tier = SubscriptionTier.BASIC
    
    buyer_breakdown = calculate_buyer_pricing(starting_price, buyer_province, b_tier)
    seller_breakdown = calculate_seller_pricing(starting_price, s_tier)
    
    return {
        "estimate_based_on": float(starting_price),
        "buyer": {
            "premium_rate": f"{float(buyer_breakdown.buyer_premium_rate) * 100:.1f}%",
            "premium_amount": float(buyer_breakdown.buyer_premium),
            "platform_fee": float(buyer_breakdown.platform_fee),
            "taxes": float(buyer_breakdown.tax_breakdown.total_tax),
            "tax_breakdown": {
                "type": buyer_breakdown.tax_breakdown.tax_type,
                "gst": float(buyer_breakdown.tax_breakdown.gst_amount),
                "pst": float(buyer_breakdown.tax_breakdown.pst_amount),
                "qst": float(buyer_breakdown.tax_breakdown.qst_amount),
                "hst": float(buyer_breakdown.tax_breakdown.hst_amount),
            },
            "total_estimated": float(buyer_breakdown.total_payable),
            "subscription_discount": float(buyer_breakdown.discount_applied)
        },
        "seller": {
            "commission_rate": f"{float(seller_breakdown.seller_commission_rate) * 100:.1f}%",
            "commission_amount": float(seller_breakdown.seller_commission),
            "net_payout": float(seller_breakdown.net_payout),
            "subscription_discount": float(seller_breakdown.discount_applied)
        }
    }


# ============= EXPORT FUNCTIONS =============

__all__ = [
    "SubscriptionTier",
    "Province",
    "TaxBreakdown",
    "BuyerPricingBreakdown",
    "SellerPricingBreakdown",
    "calculate_buyer_pricing",
    "calculate_seller_pricing",
    "calculate_taxes",
    "calculate_late_penalty",
    "get_pricing_estimate",
    "get_subscription_tier",
    "PAYMENT_DEADLINE_DAYS",
    "LATE_PAYMENT_MONTHLY_RATE",
]
