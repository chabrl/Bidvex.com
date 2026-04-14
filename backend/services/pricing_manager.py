"""
BidVex — PricingManager
Unified pricing engine for Draft Invoice generation & test emails.
Wraps vehicle_pricing.py tax engine + Stripe fee recovery.
"""

from decimal import Decimal, ROUND_HALF_UP
from dataclasses import dataclass, asdict
from typing import Dict, Any

from services.vehicle_pricing import (
    calculate_buyer_pricing,
    calculate_seller_pricing,
    calculate_taxes,
    SubscriptionTier,
    PLATFORM_FEE_RATE,
    BUYER_PREMIUM_RATES,
    SELLER_COMMISSION_RATES,
)
from shared import STRIPE_PERCENTAGE_FEE, STRIPE_FIXED_FEE


def _r(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _f(d) -> float:
    return float(d) if isinstance(d, Decimal) else d


@dataclass
class DraftInvoice:
    """Complete dual-sided invoice for admin test emails."""

    # Header
    hammer_price: float
    category: str
    buyer_province: str
    buyer_tier: str
    seller_tier: str

    # Buyer side
    buyer_premium_rate: float
    buyer_premium: float
    buyer_platform_fee: float
    buyer_stripe_fee: float
    buyer_subtotal: float
    buyer_tax_type: str
    buyer_tax_label: str
    buyer_tax_rate: float
    buyer_gst: float
    buyer_qst: float
    buyer_hst: float
    buyer_pst: float
    buyer_total_tax: float
    buyer_total: float
    buyer_discount: float

    # Seller side
    seller_commission_rate: float
    seller_commission: float
    seller_platform_fee: float
    seller_stripe_fee: float
    seller_subtotal_deductions: float
    seller_tax_type: str
    seller_tax_label: str
    seller_tax_rate: float
    seller_gst: float
    seller_qst: float
    seller_hst: float
    seller_pst: float
    seller_total_tax: float
    seller_net_payout: float
    seller_discount: float

    # BidVex revenue
    bidvex_revenue: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_template_data(self) -> Dict[str, str]:
        """Format all values as display strings for email template."""
        d = {}
        for k, v in asdict(self).items():
            if isinstance(v, float):
                if "rate" in k:
                    d[k] = f"{v * 100:.2f}%"
                else:
                    d[k] = f"${v:,.2f}"
            else:
                d[k] = str(v)
        d["hammer_price_raw"] = f"{self.hammer_price:,.2f}"
        return d


class PricingManager:
    """
    Unified pricing calculator. Produces a DraftInvoice for any category.

    Usage:
        pm = PricingManager()
        invoice = pm.calculate(
            hammer_price=25000.00,
            category="vehicle",
            buyer_province="QC",
            buyer_tier="free",
            seller_tier="free",
        )
    """

    TIER_MAP = {
        "free": SubscriptionTier.BASIC,
        "basic": SubscriptionTier.BASIC,
        "starter": SubscriptionTier.BASIC,
        "premium": SubscriptionTier.PREMIUM,
        "vip": SubscriptionTier.VIP_ELITE,
        "vip_elite": SubscriptionTier.VIP_ELITE,
    }

    @staticmethod
    def _stripe_fee_recovery(desired_net: Decimal) -> Decimal:
        """How much extra to charge so Stripe's 2.9% + $0.30 is covered."""
        fixed = Decimal(str(STRIPE_FIXED_FEE))
        pct = Decimal(str(STRIPE_PERCENTAGE_FEE))
        total = (desired_net + fixed) / (Decimal("1") - pct)
        return _r(total - desired_net)

    def _resolve_tier(self, tier: str) -> SubscriptionTier:
        return self.TIER_MAP.get(tier.lower(), SubscriptionTier.BASIC)

    def calculate(
        self,
        hammer_price: float,
        category: str = "vehicle",
        buyer_province: str = "QC",
        buyer_tier: str = "free",
        seller_tier: str = "free",
    ) -> DraftInvoice:
        hp = Decimal(str(hammer_price))
        b_tier = self._resolve_tier(buyer_tier)
        s_tier = self._resolve_tier(seller_tier)

        # ── Buyer side ──────────────────────────────────────
        b_premium_rate = BUYER_PREMIUM_RATES[b_tier]
        b_premium = _r(hp * b_premium_rate)
        b_platform_fee = _r(hp * PLATFORM_FEE_RATE)

        # Stripe fee recovery on buyer's total pre-tax charges
        b_stripe_base = hp + b_premium + b_platform_fee
        b_stripe_fee = self._stripe_fee_recovery(b_stripe_base)

        b_subtotal = b_stripe_base + b_stripe_fee
        b_tax = calculate_taxes(b_subtotal, buyer_province)
        b_total = _r(b_subtotal + b_tax.total_tax)

        # Buyer discount vs basic
        basic_premium = _r(hp * BUYER_PREMIUM_RATES[SubscriptionTier.BASIC])
        b_discount = _r(basic_premium - b_premium)

        # Tax label
        b_tax_label = self._tax_label(b_tax.tax_type, buyer_province)

        # ── Seller side ─────────────────────────────────────
        s_commission_rate = SELLER_COMMISSION_RATES[s_tier]
        s_commission = _r(hp * s_commission_rate)
        s_platform_fee = _r(hp * PLATFORM_FEE_RATE)

        # Stripe fee on seller deductions (commission + platform fee)
        s_deduction_base = s_commission + s_platform_fee
        s_stripe_fee = self._stripe_fee_recovery(s_deduction_base)

        s_total_deductions = s_deduction_base + s_stripe_fee

        # Tax on seller deductions (BidVex services)
        s_tax = calculate_taxes(s_total_deductions, buyer_province)
        s_net_payout = _r(hp - s_total_deductions - s_tax.total_tax)
        s_tax_label = self._tax_label(s_tax.tax_type, buyer_province)

        # Seller discount vs basic
        basic_commission = _r(hp * SELLER_COMMISSION_RATES[SubscriptionTier.BASIC])
        s_discount = _r(basic_commission - s_commission)

        # BidVex revenue = buyer premium + seller commission + platform fees
        bidvex_rev = _r(b_premium + s_commission + b_platform_fee + s_platform_fee)

        return DraftInvoice(
            hammer_price=_f(hp),
            category=category,
            buyer_province=buyer_province.upper(),
            buyer_tier=buyer_tier,
            seller_tier=seller_tier,
            buyer_premium_rate=_f(b_premium_rate),
            buyer_premium=_f(b_premium),
            buyer_platform_fee=_f(b_platform_fee),
            buyer_stripe_fee=_f(b_stripe_fee),
            buyer_subtotal=_f(b_subtotal),
            buyer_tax_type=b_tax.tax_type,
            buyer_tax_label=b_tax_label,
            buyer_tax_rate=_f(b_tax.total_rate),
            buyer_gst=_f(b_tax.gst_amount),
            buyer_qst=_f(b_tax.qst_amount),
            buyer_hst=_f(b_tax.hst_amount),
            buyer_pst=_f(b_tax.pst_amount),
            buyer_total_tax=_f(b_tax.total_tax),
            buyer_total=_f(b_total),
            buyer_discount=_f(b_discount),
            seller_commission_rate=_f(s_commission_rate),
            seller_commission=_f(s_commission),
            seller_platform_fee=_f(s_platform_fee),
            seller_stripe_fee=_f(s_stripe_fee),
            seller_subtotal_deductions=_f(s_total_deductions),
            seller_tax_type=s_tax.tax_type,
            seller_tax_label=s_tax_label,
            seller_tax_rate=_f(s_tax.total_rate),
            seller_gst=_f(s_tax.gst_amount),
            seller_qst=_f(s_tax.qst_amount),
            seller_hst=_f(s_tax.hst_amount),
            seller_pst=_f(s_tax.pst_amount),
            seller_total_tax=_f(s_tax.total_tax),
            seller_net_payout=_f(s_net_payout),
            seller_discount=_f(s_discount),
            bidvex_revenue=_f(bidvex_rev),
        )

    @staticmethod
    def _tax_label(tax_type: str, province: str) -> str:
        p = province.upper()
        if tax_type == "HST":
            return f"HST ({p})"
        if tax_type == "GST+QST":
            return f"GST + QST ({p})"
        if tax_type == "GST+PST":
            return f"GST + PST ({p})"
        return f"GST ({p})"
