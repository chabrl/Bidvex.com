"""
BidVex Tax & Compliance Engine
Handles Quebec tax calculations and legal compliance for auctions

TAX RATES (Quebec):
- GST (Federal): 5%
- QST (Quebec): 9.975%
- Combined: 14.975%

VEHICLE Auctions (Stripe charges BidVex fees only):
- Stripe charges: (Buyer Premium + Platform Fee) + 14.975% Tax
- Hammer Price: Paid directly to seller via Bank Draft (NOT through Stripe)

GENERAL Auctions:
- BidVex Fees: Always taxed at 14.975%
- Hammer Price Tax:
  - If seller.is_business == False: $0 tax on hammer
  - If seller.is_business == True: +14.975% tax (routed to seller via Stripe Connect)

INVOICE REQUIREMENTS:
- Split "Platform Service Fees" (with BidVex GST/QST #s)
- Split "Item Sale Price" (with Seller's info)
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass, asdict, field
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)


# ============= TAX CONSTANTS (QUEBEC) =============

GST_RATE = Decimal("0.05")          # 5% Federal GST
QST_RATE = Decimal("0.09975")       # 9.975% Quebec QST
COMBINED_TAX_RATE = Decimal("0.14975")  # 14.975% Combined

# BidVex Tax Registration Numbers (Quebec)
BIDVEX_GST_NUMBER = "706766367RT0001"  # Federal GST/HST Registration
BIDVEX_QST_NUMBER = "1233530880TQ0001"  # Quebec QST Registration
BIDVEX_LEGAL_NAME = "BidVex Inc."
BIDVEX_ADDRESS = "103-761 Chalifoux Street, Sherbrooke, QC, J1G 0A8"


class AuctionCategory(str, Enum):
    """Auction category determining fee structure"""
    VEHICLE = "vehicle"
    GENERAL = "general"


class SubscriptionTier(str, Enum):
    """User subscription tier"""
    BASIC = "basic"
    STANDARD = "standard"
    PREMIUM = "premium"
    VIP_ELITE = "vip_elite"
    VIP = "vip"


# ============= FEE RATES BY TIER =============

BUYER_PREMIUM_RATES = {
    SubscriptionTier.BASIC: Decimal("0.05"),
    SubscriptionTier.STANDARD: Decimal("0.05"),
    SubscriptionTier.PREMIUM: Decimal("0.035"),
    SubscriptionTier.VIP_ELITE: Decimal("0.03"),
    SubscriptionTier.VIP: Decimal("0.03"),
}

SELLER_COMMISSION_RATES = {
    SubscriptionTier.BASIC: Decimal("0.04"),
    SubscriptionTier.STANDARD: Decimal("0.04"),
    SubscriptionTier.PREMIUM: Decimal("0.025"),
    SubscriptionTier.VIP_ELITE: Decimal("0.02"),
    SubscriptionTier.VIP: Decimal("0.02"),
}

VEHICLE_PLATFORM_FEE_RATE = Decimal("0.025")  # 2.5%
PARTNER_PLATFORM_FEE_RATE = Decimal("0.03")   # 3% — overrides all subscription discounts


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
class TaxBreakdown:
    """Tax calculation breakdown"""
    taxable_amount: float
    taxable_amount_cents: int
    gst_rate: float
    gst_amount: float
    gst_amount_cents: int
    qst_rate: float
    qst_amount: float
    qst_amount_cents: int
    total_tax: float
    total_tax_cents: int
    total_with_tax: float
    total_with_tax_cents: int


@dataclass
class SellerInfo:
    """Seller information for tax purposes"""
    seller_id: str = ""
    seller_name: str = ""
    is_business: bool = False
    business_name: Optional[str] = None
    gst_number: Optional[str] = None
    qst_number: Optional[str] = None
    address: Optional[str] = None


@dataclass
class VehiclePaymentResult:
    """
    Vehicle auction payment calculation
    NOTE: Only BidVex fees are charged through Stripe
    Hammer price is paid directly to seller via Bank Draft
    """
    # Input values
    hammer_price: float
    hammer_price_cents: int
    category: str
    buyer_tier: str
    
    # BidVex Fees (charged on Stripe)
    buyer_premium_rate: float
    buyer_premium: float
    buyer_premium_cents: int
    platform_fee_rate: float
    platform_fee: float
    platform_fee_cents: int
    bidvex_fees_subtotal: float
    bidvex_fees_subtotal_cents: int
    
    # Tax on BidVex fees (always 14.975%)
    bidvex_fees_gst: float
    bidvex_fees_gst_cents: int
    bidvex_fees_qst: float
    bidvex_fees_qst_cents: int
    bidvex_fees_tax_total: float
    bidvex_fees_tax_total_cents: int
    
    # Total charged on Stripe (BidVex fees + tax)
    stripe_charge_total: float
    stripe_charge_total_cents: int
    
    # Amount due to seller (via Bank Draft)
    seller_balance_due: float
    seller_balance_due_cents: int
    
    # Instructions
    next_steps_message: str
    
    # Invoice line items
    invoice_lines: list = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class GeneralPaymentResult:
    """
    General auction payment calculation
    Full amount charged through Stripe with tax logic based on seller type
    """
    # Input values
    hammer_price: float
    hammer_price_cents: int
    category: str
    buyer_tier: str
    seller_tier: str
    seller_is_business: bool
    
    # BidVex Fees
    buyer_premium_rate: float
    buyer_premium: float
    buyer_premium_cents: int
    seller_commission_rate: float
    seller_commission: float
    seller_commission_cents: int
    bidvex_fees_subtotal: float
    bidvex_fees_subtotal_cents: int
    
    # Tax on BidVex fees (always 14.975%)
    bidvex_fees_gst: float
    bidvex_fees_gst_cents: int
    bidvex_fees_qst: float
    bidvex_fees_qst_cents: int
    bidvex_fees_tax_total: float
    bidvex_fees_tax_total_cents: int
    
    # Tax on Hammer Price (only if seller is business)
    hammer_tax_applicable: bool
    hammer_gst: float
    hammer_gst_cents: int
    hammer_qst: float
    hammer_qst_cents: int
    hammer_tax_total: float
    hammer_tax_total_cents: int
    
    # Buyer totals
    buyer_pays_hammer: float
    buyer_pays_hammer_cents: int
    buyer_pays_fees: float
    buyer_pays_fees_cents: int
    buyer_pays_hammer_tax: float
    buyer_pays_hammer_tax_cents: int
    buyer_pays_fees_tax: float
    buyer_pays_fees_tax_cents: int
    buyer_total: float
    buyer_total_cents: int
    
    # Seller totals (what they receive via Stripe Connect)
    seller_receives_hammer: float
    seller_receives_hammer_cents: int
    seller_receives_hammer_tax: float  # Tax collected for seller (if business)
    seller_receives_hammer_tax_cents: int
    seller_pays_commission: float
    seller_pays_commission_cents: int
    seller_net_payout: float
    seller_net_payout_cents: int
    
    # BidVex revenue
    bidvex_revenue: float
    bidvex_revenue_cents: int
    bidvex_tax_collected: float
    bidvex_tax_collected_cents: int
    
    # Stripe parameters
    stripe_amount_cents: int
    stripe_application_fee_cents: int  # BidVex fees + BidVex tax
    stripe_transfer_amount_cents: int  # Seller payout + seller tax (if any)

    # Bug 6 — Stripe processing fee passed to buyer (gross-up)
    stripe_processing_fee: float = 0.0
    stripe_processing_fee_cents: int = 0

    # Invoice line items
    invoice_lines: list = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_tax(amount: Decimal) -> TaxBreakdown:
    """Calculate GST and QST on an amount — **QUEBEC-ONLY LEGACY HELPER**.

    P6.2 Gate 4 DEPRECATION NOTICE
    ------------------------------
    This helper hardcodes GST 5% + QST 9.975% (14.975% combined) and
    IGNORES caller province. It exists only to serve the QC-preview
    endpoints in ``routes/payments_fees.py`` (``/api/tax/calculate``,
    ``/api/tax/general``, ``/api/tax/vehicle``) which are explicitly
    labelled "Quebec taxes" in their docstrings.

    NEW CODE MUST USE
        ``calculate_taxes_for_recipient(subtotal, province, currency)``
    which reads DB-backed rates via ``services.tax_rate_config`` and
    fails closed to INTL (0%) on unknown / missing province.

    The settlement hot path (`fee_calculator.calculate_fee`) NEVER
    calls this function — verified in P6.1.1 §10 Claim A.
    """
    gst = _round_currency(amount * GST_RATE)
    qst = _round_currency(amount * QST_RATE)
    total_tax = gst + qst
    total_with_tax = amount + total_tax
    
    return TaxBreakdown(
        taxable_amount=float(amount),
        taxable_amount_cents=_to_cents(amount),
        gst_rate=float(GST_RATE),
        gst_amount=float(gst),
        gst_amount_cents=_to_cents(gst),
        qst_rate=float(QST_RATE),
        qst_amount=float(qst),
        qst_amount_cents=_to_cents(qst),
        total_tax=float(total_tax),
        total_tax_cents=_to_cents(total_tax),
        total_with_tax=float(total_with_tax),
        total_with_tax_cents=_to_cents(total_with_tax),
    )


def calculate_vehicle_payment(
    hammer_price: float,
    buyer_tier: str = "basic",
    buyer_premium_rate_override: Optional[float] = None
) -> VehiclePaymentResult:
    """
    Calculate vehicle auction payment
    
    IMPORTANT: For vehicles, only BidVex fees are charged through Stripe.
    The hammer price is paid directly to seller via Bank Draft.
    
    Stripe charges: (Buyer Premium + Platform Fee) + 14.975% Tax
    
    If buyer_premium_rate_override is provided (listing-level premium), it takes
    precedence over the tier-based default.
    """
    hp = Decimal(str(hammer_price))
    b_tier = _normalize_tier(buyer_tier)
    
    # Calculate BidVex fees — listing override takes precedence
    if buyer_premium_rate_override is not None:
        buyer_premium_rate = Decimal(str(buyer_premium_rate_override))
    else:
        buyer_premium_rate = BUYER_PREMIUM_RATES[b_tier]
    buyer_premium = _round_currency(hp * buyer_premium_rate)
    platform_fee = _round_currency(hp * VEHICLE_PLATFORM_FEE_RATE)
    bidvex_fees_subtotal = buyer_premium + platform_fee
    
    # Calculate tax on BidVex fees (always 14.975%)
    fees_tax = calculate_tax(bidvex_fees_subtotal)
    
    # Total charged on Stripe
    stripe_charge_total = Decimal(str(fees_tax.total_with_tax))
    
    # Create invoice lines
    invoice_lines = [
        {
            "description": "BidVex Buyer Premium",
            "rate": f"{float(buyer_premium_rate) * 100:.1f}%",
            "amount": float(buyer_premium),
            "tax_included": False
        },
        {
            "description": "BidVex Platform Fee",
            "rate": "2.5%",
            "amount": float(platform_fee),
            "tax_included": False
        },
        {
            "description": "GST (5%)",
            "rate": "5%",
            "amount": fees_tax.gst_amount,
            "tax_included": True,
            "tax_number": BIDVEX_GST_NUMBER
        },
        {
            "description": "QST (9.975%)",
            "rate": "9.975%",
            "amount": fees_tax.qst_amount,
            "tax_included": True,
            "tax_number": BIDVEX_QST_NUMBER
        },
        {
            "description": "Balance Due to Seller (via Bank Draft)",
            "rate": "100%",
            "amount": float(hp),
            "tax_included": False,
            "payment_method": "Bank Draft"
        }
    ]
    
    next_steps = (
        f"BidVex fees paid. Balance of ${float(hp):,.2f} CAD to be paid directly "
        f"to Seller via Bank Draft. Please contact the seller within 14 days to "
        f"arrange payment and vehicle pickup/delivery."
    )
    
    return VehiclePaymentResult(
        hammer_price=float(hp),
        hammer_price_cents=_to_cents(hp),
        category="vehicle",
        buyer_tier=b_tier.value,
        
        buyer_premium_rate=float(buyer_premium_rate),
        buyer_premium=float(buyer_premium),
        buyer_premium_cents=_to_cents(buyer_premium),
        platform_fee_rate=float(VEHICLE_PLATFORM_FEE_RATE),
        platform_fee=float(platform_fee),
        platform_fee_cents=_to_cents(platform_fee),
        bidvex_fees_subtotal=float(bidvex_fees_subtotal),
        bidvex_fees_subtotal_cents=_to_cents(bidvex_fees_subtotal),
        
        bidvex_fees_gst=fees_tax.gst_amount,
        bidvex_fees_gst_cents=fees_tax.gst_amount_cents,
        bidvex_fees_qst=fees_tax.qst_amount,
        bidvex_fees_qst_cents=fees_tax.qst_amount_cents,
        bidvex_fees_tax_total=fees_tax.total_tax,
        bidvex_fees_tax_total_cents=fees_tax.total_tax_cents,
        
        stripe_charge_total=float(stripe_charge_total),
        stripe_charge_total_cents=_to_cents(stripe_charge_total),
        
        seller_balance_due=float(hp),
        seller_balance_due_cents=_to_cents(hp),
        
        next_steps_message=next_steps,
        invoice_lines=invoice_lines,
    )


def calculate_general_payment(
    hammer_price: float,
    buyer_tier: str = "basic",
    seller_tier: str = "basic",
    seller_is_business: bool = False,
    seller_info: Optional[SellerInfo] = None,
    buyer_premium_rate_override: Optional[float] = None
) -> GeneralPaymentResult:
    """
    Calculate general auction payment
    
    Tax Logic:
    - BidVex fees: Always taxed at 14.975%
    - Hammer price: 
      - If seller is NOT a business: $0 tax
      - If seller IS a business: +14.975% tax (collected for seller)
    
    If buyer_premium_rate_override is provided (listing-level premium), it takes
    precedence over the tier-based default.
    """
    hp = Decimal(str(hammer_price))
    b_tier = _normalize_tier(buyer_tier)
    s_tier = _normalize_tier(seller_tier)
    
    # BidVex fees — listing override takes precedence
    if buyer_premium_rate_override is not None:
        buyer_premium_rate = Decimal(str(buyer_premium_rate_override))
    else:
        buyer_premium_rate = BUYER_PREMIUM_RATES[b_tier]
    buyer_premium = _round_currency(hp * buyer_premium_rate)
    
    seller_commission_rate = SELLER_COMMISSION_RATES[s_tier]
    seller_commission = _round_currency(hp * seller_commission_rate)
    
    bidvex_fees_subtotal = buyer_premium + seller_commission
    
    # Tax on BidVex fees (always 14.975%)
    fees_tax = calculate_tax(bidvex_fees_subtotal)
    
    # Tax on hammer price (only if seller is business)
    if seller_is_business:
        hammer_tax = calculate_tax(hp)
        hammer_gst = Decimal(str(hammer_tax.gst_amount))
        hammer_qst = Decimal(str(hammer_tax.qst_amount))
        hammer_tax_total = hammer_gst + hammer_qst
    else:
        hammer_gst = Decimal("0")
        hammer_qst = Decimal("0")
        hammer_tax_total = Decimal("0")
    
    # Buyer pays
    buyer_pays_hammer = hp
    buyer_pays_fees = buyer_premium  # Buyer only pays buyer premium
    buyer_pays_hammer_tax = hammer_tax_total
    buyer_pays_fees_tax = Decimal(str(fees_tax.total_tax))
    
    # ===== BUG 4 FIX =====
    # Tax must be computed on (buyer_premium + stripe_processing_fee) — the
    # SAME base Stripe actually charges. Earlier code taxed `buyer_premium`
    # alone which rounded to $0.00 for small bids (e.g. $0.03 premium → $0
    # GST / $0 QST) while Stripe showed real tax — that deceived users with
    # a lower displayed total than the Stripe charge.
    from services.fee_calculator import gross_up_stripe_fee as _gross_up_stripe
    # First-pass gross-up on hammer + premium
    _sr = _gross_up_stripe(hp + buyer_premium)
    _bp_taxable = buyer_premium + _sr
    _bp_tax = calculate_tax(_bp_taxable)
    # Second-pass gross-up once taxes are known so Stripe covers taxes too
    _sr = _gross_up_stripe(hp + buyer_premium + Decimal(str(_bp_tax.total_tax)))
    _bp_taxable = buyer_premium + _sr
    _bp_tax = calculate_tax(_bp_taxable)
    stripe_processing_fee = _sr
    buyer_pays_fees_tax = Decimal(str(_bp_tax.total_tax))
    
    buyer_total = (
        buyer_pays_hammer
        + buyer_pays_fees
        + buyer_pays_hammer_tax
        + buyer_pays_fees_tax
        + stripe_processing_fee
    )
    
    # Seller receives
    seller_receives_hammer = hp
    seller_receives_hammer_tax = hammer_tax_total  # Tax collected on their behalf
    seller_pays_commission = seller_commission
    seller_net_payout = seller_receives_hammer - seller_pays_commission + seller_receives_hammer_tax
    
    # BidVex revenue (buyer premium + seller commission + tax on those)
    bidvex_revenue = buyer_premium + seller_commission
    bidvex_tax_collected = Decimal(str(fees_tax.total_tax))
    
    # Stripe parameters
    stripe_amount_cents = _to_cents(buyer_total)
    stripe_application_fee_cents = _to_cents(bidvex_revenue + bidvex_tax_collected)
    stripe_transfer_amount_cents = _to_cents(seller_net_payout)
    
    # Invoice lines
    invoice_lines = [
        {
            "section": "Item Sale",
            "description": "Hammer Price",
            "amount": float(hp),
            "tax_applicable": seller_is_business,
            "seller_info": asdict(seller_info) if seller_info else None
        },
    ]
    
    if seller_is_business:
        invoice_lines.extend([
            {
                "section": "Item Sale Tax",
                "description": "GST on Item (Seller)",
                "rate": "5%",
                "amount": float(hammer_gst),
                "tax_number": seller_info.gst_number if seller_info else "Seller GST#"
            },
            {
                "section": "Item Sale Tax",
                "description": "QST on Item (Seller)",
                "rate": "9.975%",
                "amount": float(hammer_qst),
                "tax_number": seller_info.qst_number if seller_info else "Seller QST#"
            },
        ])
    
    invoice_lines.extend([
        {
            "section": "Platform Service Fees",
            "description": "BidVex Buyer Premium",
            "rate": f"{float(buyer_premium_rate) * 100:.1f}%",
            "amount": float(buyer_premium),
            "provider": BIDVEX_LEGAL_NAME
        },
        {
            "section": "Platform Service Fees Tax",
            "description": "GST on Platform Fees",
            "rate": "5%",
            "amount": _bp_tax.gst_amount,
            "tax_number": BIDVEX_GST_NUMBER
        },
        {
            "section": "Platform Service Fees Tax",
            "description": "QST on Platform Fees",
            "rate": "9.975%",
            "amount": _bp_tax.qst_amount,
            "tax_number": BIDVEX_QST_NUMBER
        },
    ])
    
    return GeneralPaymentResult(
        hammer_price=float(hp),
        hammer_price_cents=_to_cents(hp),
        category="general",
        buyer_tier=b_tier.value,
        seller_tier=s_tier.value,
        seller_is_business=seller_is_business,
        
        buyer_premium_rate=float(buyer_premium_rate),
        buyer_premium=float(buyer_premium),
        buyer_premium_cents=_to_cents(buyer_premium),
        seller_commission_rate=float(seller_commission_rate),
        seller_commission=float(seller_commission),
        seller_commission_cents=_to_cents(seller_commission),
        bidvex_fees_subtotal=float(bidvex_fees_subtotal),
        bidvex_fees_subtotal_cents=_to_cents(bidvex_fees_subtotal),
        
        bidvex_fees_gst=fees_tax.gst_amount,
        bidvex_fees_gst_cents=fees_tax.gst_amount_cents,
        bidvex_fees_qst=fees_tax.qst_amount,
        bidvex_fees_qst_cents=fees_tax.qst_amount_cents,
        bidvex_fees_tax_total=fees_tax.total_tax,
        bidvex_fees_tax_total_cents=fees_tax.total_tax_cents,
        
        hammer_tax_applicable=seller_is_business,
        hammer_gst=float(hammer_gst),
        hammer_gst_cents=_to_cents(hammer_gst),
        hammer_qst=float(hammer_qst),
        hammer_qst_cents=_to_cents(hammer_qst),
        hammer_tax_total=float(hammer_tax_total),
        hammer_tax_total_cents=_to_cents(hammer_tax_total),
        
        buyer_pays_hammer=float(buyer_pays_hammer),
        buyer_pays_hammer_cents=_to_cents(buyer_pays_hammer),
        buyer_pays_fees=float(buyer_pays_fees),
        buyer_pays_fees_cents=_to_cents(buyer_pays_fees),
        buyer_pays_hammer_tax=float(buyer_pays_hammer_tax),
        buyer_pays_hammer_tax_cents=_to_cents(buyer_pays_hammer_tax),
        buyer_pays_fees_tax=float(buyer_pays_fees_tax),
        buyer_pays_fees_tax_cents=_to_cents(buyer_pays_fees_tax),
        buyer_total=float(buyer_total),
        buyer_total_cents=_to_cents(buyer_total),
        
        seller_receives_hammer=float(seller_receives_hammer),
        seller_receives_hammer_cents=_to_cents(seller_receives_hammer),
        seller_receives_hammer_tax=float(seller_receives_hammer_tax),
        seller_receives_hammer_tax_cents=_to_cents(seller_receives_hammer_tax),
        seller_pays_commission=float(seller_pays_commission),
        seller_pays_commission_cents=_to_cents(seller_pays_commission),
        seller_net_payout=float(seller_net_payout),
        seller_net_payout_cents=_to_cents(seller_net_payout),
        
        bidvex_revenue=float(bidvex_revenue),
        bidvex_revenue_cents=_to_cents(bidvex_revenue),
        bidvex_tax_collected=float(bidvex_tax_collected),
        bidvex_tax_collected_cents=_to_cents(bidvex_tax_collected),
        
        stripe_amount_cents=stripe_amount_cents,
        stripe_application_fee_cents=stripe_application_fee_cents,
        stripe_transfer_amount_cents=stripe_transfer_amount_cents,

        # Bug 6 — Stripe processing fee (pass-through to buyer, gross-up)
        stripe_processing_fee=float(stripe_processing_fee),
        stripe_processing_fee_cents=_to_cents(stripe_processing_fee),

        invoice_lines=invoice_lines,
    )


def get_tax_structure_summary() -> Dict[str, Any]:
    """Get summary of tax structure for documentation"""
    return {
        "jurisdiction": "Quebec, Canada",
        "tax_rates": {
            "gst": {
                "name": "Goods and Services Tax (Federal)",
                "rate": "5%",
                "registration": BIDVEX_GST_NUMBER
            },
            "qst": {
                "name": "Quebec Sales Tax (Provincial)",
                "rate": "9.975%",
                "registration": BIDVEX_QST_NUMBER
            },
            "combined": {
                "name": "Total Quebec Tax",
                "rate": "14.975%"
            }
        },
        "vehicle_auctions": {
            "stripe_charges": "BidVex Fees + 14.975% Tax only",
            "hammer_price": "Paid directly to seller via Bank Draft",
            "tax_on_hammer": "Not collected through platform"
        },
        "general_auctions": {
            "private_seller": {
                "hammer_tax": "No tax on hammer price",
                "fees_tax": "14.975% on BidVex fees"
            },
            "business_seller": {
                "hammer_tax": "14.975% collected and routed to seller",
                "fees_tax": "14.975% on BidVex fees"
            }
        },
        "bidvex_info": {
            "legal_name": BIDVEX_LEGAL_NAME,
            "address": BIDVEX_ADDRESS,
            "gst_number": BIDVEX_GST_NUMBER,
            "qst_number": BIDVEX_QST_NUMBER
        }
    }


def calculate_gst_qst(subtotal: float, currency: str = "CAD") -> Dict[str, Any]:
    """Simple GST/QST calculator for invoices and templates — **QUEBEC-ONLY**.

    P6.2 Gate 4 DEPRECATION NOTICE
    ------------------------------
    This is a QC-scoped back-compat wrapper. It ALWAYS bills the
    QC combined rate (GST 5% + QST 9.975% = 14.975%) regardless of
    caller. It is retained for legacy SendGrid template variables
    (``{{gst_amount}}`` / ``{{qst_amount}}``) that assume QC context.

    NEW CODE MUST USE
        ``calculate_taxes_for_recipient(subtotal, province, currency)``
    which returns the same shape but reads DB-backed rates via
    ``services.tax_rate_config`` — GST for non-QC provinces, HST for
    ON/NB/NL/NS/PE, zero-rated for US/INTL/unknown.
    """
    return calculate_taxes_for_recipient(subtotal, "QC", currency)


def calculate_taxes_for_recipient(
    subtotal: float,
    province: str,
    currency: str = "CAD",
) -> Dict[str, Any]:
    """iter350 — CRA Place-of-Supply-compliant tax calculation for a supply
    to a recipient in `province`. Reads rates from db.tax_rate_config (via
    the tax_rate_config synchronous cache) so a legislative change requires
    ZERO code changes — just an admin edit at /api/admin/pricing/tax-rates.

    Returns the same shape as legacy `calculate_gst_qst()` for drop-in
    compatibility with SendGrid templates ({{gst_amount}}, {{qst_amount}}).
    """
    from services.tax_rate_config import get_tax_rate_sync, normalize_province
    prov_code = normalize_province(province)
    row = get_tax_rate_sync(prov_code)
    gst_rate = Decimal(str(row["gst"]))
    qst_rate = Decimal(str(row["qst"]))
    hst_rate = Decimal(str(row["hst"]))
    combined = Decimal(str(row["combined"]))
    tax_label = str(row["label"])

    if currency != "CAD":
        return {
            "subtotal": round(subtotal, 2),
            "province": prov_code,
            "gst_rate": 0.0, "gst_amount": 0.0,
            "qst_rate": 0.0, "qst_amount": 0.0,
            "hst_rate": 0.0, "hst_amount": 0.0,
            "total_tax": 0.0,
            "total_with_tax": round(subtotal, 2),
            "currency": currency,
            "tax_label": "N/A (non-CAD)",
            "gst_registration": BIDVEX_GST_NUMBER,
            "qst_registration": BIDVEX_QST_NUMBER,
        }

    amt = Decimal(str(subtotal))
    gst = _round_currency(amt * gst_rate)
    qst = _round_currency(amt * qst_rate)
    hst = _round_currency(amt * hst_rate)
    total_tax = gst + qst + hst
    total_with_tax = _round_currency(amt + total_tax)

    return {
        "subtotal": float(_round_currency(amt)),
        "province": prov_code,
        "gst_rate": float(gst_rate),
        "gst_amount": float(gst),
        "qst_rate": float(qst_rate),
        "qst_amount": float(qst),
        "hst_rate": float(hst_rate),
        "hst_amount": float(hst),
        "combined_rate": float(combined),
        "total_tax": float(total_tax),
        "total_with_tax": float(total_with_tax),
        "currency": "CAD",
        "tax_label": tax_label,
        "gst_registration": BIDVEX_GST_NUMBER,
        "qst_registration": BIDVEX_QST_NUMBER,
    }


def get_tax_rates_for_currency(currency: str) -> Dict[str, float]:
    """Get applicable tax rates based on currency (CAD → GST+QST, else zero)."""
    if currency == "CAD":
        return {"tax_rate_gst": float(GST_RATE) * 100, "tax_rate_qst": float(QST_RATE) * 100}
    return {"tax_rate_gst": 0.0, "tax_rate_qst": 0.0}


def invoice_tax_lines(subtotal: float, currency: str = "CAD") -> list:
    """
    Generate tax line items for invoice templates and SendGrid dynamic data.

    Returns a list of dicts each with {label, rate, amount, registration}.
    """
    tax = calculate_gst_qst(subtotal, currency)
    if currency != "CAD":
        return []

    return [
        {
            "label": "GST (TPS)",
            "rate": "5%",
            "amount": f"{tax['gst_amount']:.2f}",
            "amount_raw": tax["gst_amount"],
            "registration": BIDVEX_GST_NUMBER,
        },
        {
            "label": "QST (TVQ)",
            "rate": "9.975%",
            "amount": f"{tax['qst_amount']:.2f}",
            "amount_raw": tax["qst_amount"],
            "registration": BIDVEX_QST_NUMBER,
        },
    ]


# ============= EXPORTS =============

__all__ = [
    "AuctionCategory",
    "SubscriptionTier",
    "TaxBreakdown",
    "SellerInfo",
    "VehiclePaymentResult",
    "GeneralPaymentResult",
    "calculate_tax",
    "calculate_gst_qst",
    "calculate_taxes_for_recipient",
    "get_tax_rates_for_currency",
    "invoice_tax_lines",
    "calculate_vehicle_payment",
    "calculate_general_payment",
    "get_tax_structure_summary",
    "GST_RATE",
    "QST_RATE",
    "COMBINED_TAX_RATE",
    "BIDVEX_GST_NUMBER",
    "BIDVEX_QST_NUMBER",
    "BIDVEX_LEGAL_NAME",
    "BIDVEX_ADDRESS",
]
