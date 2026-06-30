"""
BidVex Production Pricing Configuration
Single source of truth for all platform pricing, commissions, and fee structures.
"""

from decimal import Decimal

# ============= PLATFORM COMMISSIONS =============

# Platform fee on winning hammer price (charged via application_fee_amount)
PLATFORM_FEE_GENERAL = Decimal("0.03")    # 3.0% on general items
PLATFORM_FEE_VEHICLE = Decimal("0.025")   # 2.5% on vehicles

# Stripe processing fee (passed through to buyer)
STRIPE_PROCESSING_RATE = Decimal("0.029")  # 2.9%
STRIPE_PROCESSING_FIXED = Decimal("0.30")  # $0.30 CAD

# ============= USER TIER RATES =============

BUYER_PREMIUM_RATES = {
    "free":        Decimal("0.05"),   # 5.0%  — Standard
    "basic":       Decimal("0.05"),   # 5.0%  — Standard (alias)
    "standard":    Decimal("0.05"),   # 5.0%  — Standard (alias)
    "premium":     Decimal("0.035"),  # 3.5%  — Premium ($180/yr)
    "partner":     Decimal("0.05"),   # 5.0%  — Partner ($100/yr, same buyer rate)
    "partner_pro": Decimal("0.0375"), # 3.75% — Partner Pro ($240/yr)
    "vip":         Decimal("0.03"),   # 3.0%  — VIP Elite ($300/yr)
    "vip_elite":   Decimal("0.03"),   # 3.0%  — VIP Elite (alias)
}

SELLER_COMMISSION_RATES = {
    "free":        Decimal("0.04"),   # 4.0%
    "basic":       Decimal("0.04"),   # 4.0%
    "standard":    Decimal("0.04"),   # 4.0%
    "premium":     Decimal("0.025"),  # 2.5%
    "partner":     Decimal("0.04"),   # 4.0%  — Partner ($100/yr, same seller rate)
    "partner_pro": Decimal("0.03"),   # 3.0%
    "vip":         Decimal("0.02"),   # 2.0%
    "vip_elite":   Decimal("0.02"),   # 2.0%
}

# ============= SUBSCRIPTION PRICING =============
#
# iter328 — Stripe-Sync Lock.
#
# These values MIRROR the live BidVex Stripe Product/Price objects.
# DO NOT EDIT in code without first updating the corresponding
# Stripe Price in the BidVex Stripe account, then mirroring here.
# Subscription pricing is Stripe-driven going forward; no code-side overrides.

SUBSCRIPTION_TIERS = {
    "free":        {"amount_cents": 0,     "currency": "cad", "interval": "year", "label": "Free"},
    "partner":     {"amount_cents": 10000, "currency": "cad", "interval": "year", "label": "$100.00 CAD/year"},
    "premium":     {"amount_cents": 18000, "currency": "cad", "interval": "year", "label": "$180.00 CAD/year"},
    "partner_pro": {"amount_cents": 24000, "currency": "cad", "interval": "year", "label": "$240.00 CAD/year"},
    "vip":         {"amount_cents": 30000, "currency": "cad", "interval": "year", "label": "$300.00 CAD/year"},
}

# ============= LISTING PROMOTIONS =============

PROMOTION_TIERS = {
    "basic": {
        "price_cents": 999,     # $9.99
        "duration_days": 7,
        "label": "Basic Boost",
        "features": ["Featured badge", "Top of category"],
    },
    "standard": {
        "price_cents": 2499,    # $24.99
        "duration_days": 14,
        "label": "Standard Boost",
        "features": ["Featured badge", "Top of category", "Homepage feature"],
    },
    "premium": {
        "price_cents": 4999,    # $49.99
        "duration_days": 30,
        "label": "Premium Boost",
        "features": ["Featured badge", "Top of category", "Homepage feature", "Email blast"],
    },
}

# ============= EMAIL MARKETING CREDITS =============

EMAIL_CREDIT_TIERS = [
    {"min_qty": 1,     "max_qty": 1000,  "per_email_cents": 2,  "label": "$0.018/email"},  # rounded to 2¢
    {"min_qty": 1001,  "max_qty": 5000,  "per_email_cents": 2,  "label": "$0.015/email"},  # rounded to 2¢
    {"min_qty": 5001,  "max_qty": 10000, "per_email_cents": 1,  "label": "$0.012/email"},  # rounded to 1¢
    {"min_qty": 10001, "max_qty": None,  "per_email_cents": 1,  "label": "$0.010/email"},  # rounded to 1¢
]

# Exact per-email rates in dollars (for precise calculation)
EMAIL_RATES_DOLLARS = [
    {"min_qty": 1,     "max_qty": 1000,  "rate": Decimal("0.018")},
    {"min_qty": 1001,  "max_qty": 5000,  "rate": Decimal("0.015")},
    {"min_qty": 5001,  "max_qty": 10000, "rate": Decimal("0.012")},
    {"min_qty": 10001, "max_qty": None,  "rate": Decimal("0.010")},
]

# ============= HIGH-VALUE AUCTION DEPOSIT =============

DEPOSIT_THRESHOLD_CAD = 10000   # Auctions starting above $10k CAD require deposit
DEPOSIT_AMOUNT_CENTS = 100000   # $1,000.00 CAD pre-auth hold
DEPOSIT_AMOUNT_DOLLARS = 1000

# ============= AFFILIATE REFERRAL =============

AFFILIATE_COMMISSION_RATE = Decimal("0.15")  # 15% of BidVex's commission goes to affiliate

# ============= TAX RATES (Quebec / Canada) =============

GST_RATE = Decimal("0.05")      # 5% Federal
QST_RATE = Decimal("0.09975")   # 9.975% Quebec
COMBINED_TAX_RATE = GST_RATE + QST_RATE  # ~14.975%


def calculate_email_credit_cost(quantity: int) -> int:
    """Calculate total cost in cents for a given email credit quantity."""
    for tier in EMAIL_RATES_DOLLARS:
        max_q = tier["max_qty"]
        if max_q is None or quantity <= max_q:
            total = Decimal(str(quantity)) * tier["rate"]
            return int((total * 100).to_integral_value())
    # Fallback to lowest rate
    total = Decimal(str(quantity)) * Decimal("0.010")
    return int((total * 100).to_integral_value())


def get_platform_fee_rate(category: str) -> Decimal:
    """Get the platform fee rate for a given auction category."""
    cat = category.lower() if category else "general"
    if cat in ("vehicle", "car", "auto", "automobile", "truck", "motorcycle"):
        return PLATFORM_FEE_VEHICLE
    return PLATFORM_FEE_GENERAL


def get_buyer_premium_rate(tier: str) -> Decimal:
    """Get buyer premium rate for a subscription tier."""
    return BUYER_PREMIUM_RATES.get(tier.lower(), Decimal("0.05"))


def get_seller_commission_rate(tier: str) -> Decimal:
    """Get seller commission rate for a subscription tier."""
    return SELLER_COMMISSION_RATES.get(tier.lower(), Decimal("0.04"))
