"""
BidVex Fee & Cost Calculation Engine — iter209 SINGLE SOURCE OF TRUTH

The entry point for ALL fee math is `calculate_fee()` at the top of this file.
Account-type routing:
    individual         → buyer-tier BP + seller-tier commission
    partner            → partner-set BP (buyer) + 3% commission (seller)
    vehicle_dealer     → 2.5% buyer fee, $0 to seller (annual sub charged separately)
    storage_facility   → $0 buyer fee, 5% facility commission (buyer pays facility direct)

Taxes (Quebec / QC) per iter209 spec:
    GST = 5%  applied to the BidVex platform charge (BP or commission)
    QST = 9.975% applied to the BidVex platform charge (NOT compounded on GST)
    Taxes are NEVER applied to the hammer price (handled by seller-of-record).

Stripe gross-up (per spec 2C):
    domestic       2.9% + $0.30
    international  3.9% + $0.30
    conversion     5.9% + $0.30
    Formula: gross_up = (subtotal + 0.30) / (1 - rate) - subtotal
    Default to `domestic` when card type is unknown at checkout time.

Legacy `FeeCalculator` class below is preserved for now; older callers will be
migrated to `calculate_fee()` in iter209 Step 2+.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional


# ─── iter209 spec constants ────────────────────────────────────────────────
INDIVIDUAL_BUYER_RATES: Dict[str, Decimal] = {
    "standard":  Decimal("0.050"),
    "premium":   Decimal("0.035"),
    "vip_elite": Decimal("0.030"),
}
INDIVIDUAL_SELLER_RATES: Dict[str, Decimal] = {
    "standard":  Decimal("0.040"),
    "premium":   Decimal("0.025"),
    "vip_elite": Decimal("0.020"),
}
# Legacy → spec tier aliases (back-compat: existing users may still carry "free"/"vip")
TIER_ALIASES: Dict[str, str] = {
    "free":     "standard",
    "starter":  "standard",
    "vip":      "vip_elite",
}

PARTNER_PLATFORM_RATE   = Decimal("0.030")    # 3% of hammer to BidVex
VEHICLE_DEALER_BUYER_RATE = Decimal("0.025")  # 2.5% buyer fee
STORAGE_FACILITY_RATE   = Decimal("0.050")    # 5% facility commission

QC_GST_RATE = Decimal("0.05")
QC_QST_RATE = Decimal("0.09975")

STRIPE_RATES: Dict[str, Decimal] = {
    "domestic":      Decimal("0.029"),
    "international": Decimal("0.039"),
    "conversion":    Decimal("0.059"),
}
STRIPE_FIXED_FEE = Decimal("0.30")


# ─── Rounding helper (banker-safe to cents) ────────────────────────────────
def _r(value: Decimal) -> float:
    """Round Decimal → 2dp → float (consumer-facing presentation)."""
    return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def _normalize_tier(tier: Optional[str]) -> str:
    if not tier:
        return "standard"
    t = tier.strip().lower()
    return TIER_ALIASES.get(t, t)


def _stripe_gross_up(subtotal: Decimal, card_type: str) -> Decimal:
    """`(subtotal + 0.30) / (1 - rate) - subtotal` — exact spec formula."""
    rate = STRIPE_RATES.get((card_type or "domestic").lower(), STRIPE_RATES["domestic"])
    if subtotal <= 0:
        return Decimal("0")
    return ((subtotal + STRIPE_FIXED_FEE) / (Decimal("1") - rate)) - subtotal


# ─── FeeResult dataclass ───────────────────────────────────────────────────
@dataclass
class FeeResult:
    auction_type: str
    hammer_price: float

    # Buyer side
    buyer_premium: float
    buyer_premium_rate: float
    buyer_gst: float
    buyer_qst: float
    buyer_taxes: float
    buyer_subtotal: float
    buyer_stripe_fee: float
    buyer_total_charged: float
    buyer_stripe_cents: int

    # Seller side
    seller_commission: float
    seller_commission_rate: float
    seller_gst: float
    seller_qst: float
    seller_commission_total: float
    seller_stripe_fee: float
    seller_payout: float

    # Platform
    bidvex_revenue: float

    # Routing flags
    charge_buyer_via_stripe: bool
    charge_seller_via_stripe: bool
    charge_seller_card_separately: bool

    # Meta
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ─── PUBLIC API: calculate_fee ─────────────────────────────────────────────
def calculate_fee(
    hammer_price: float,
    auction_type: str,
    seller_account_type: str,
    seller_tier: Optional[str] = None,
    buyer_account_type: str = "individual",
    buyer_tier: str = "standard",
    partner_bp_rate: float = 0.0,
    payment_method: str = "stripe",
    card_type: str = "domestic",
) -> dict:
    """Compute the full fee breakdown for a single auction transaction.

    See module docstring for routing logic. Returns a plain dict (FeeResult.to_dict()).
    """
    hammer = Decimal(str(hammer_price))
    if hammer < 0:
        raise ValueError("hammer_price must be >= 0")

    seller_type = (seller_account_type or "").strip().lower()
    buyer_tier_norm = _normalize_tier(buyer_tier)
    seller_tier_norm = _normalize_tier(seller_tier)
    payment = (payment_method or "stripe").strip().lower()

    # Defaults — every code path overwrites what it needs
    buyer_premium = Decimal("0")
    buyer_premium_rate = Decimal("0")
    seller_commission = Decimal("0")
    seller_commission_rate = Decimal("0")
    charge_buyer_via_stripe = False
    charge_seller_via_stripe = False
    charge_seller_card_separately = False
    notes = ""

    # ── Route 1: PARTNER seller ──────────────────────────────────────────
    if seller_type == "partner":
        rate = Decimal(str(partner_bp_rate or 0))
        if rate < 0:
            raise ValueError("partner_bp_rate must be >= 0")
        buyer_premium_rate = rate
        buyer_premium = (hammer * rate)
        seller_commission_rate = PARTNER_PLATFORM_RATE
        seller_commission = hammer * PARTNER_PLATFORM_RATE

        if payment in ("cash", "e_transfer", "etransfer"):
            charge_buyer_via_stripe = False
            charge_seller_card_separately = True
            notes = "Partner cash/e-transfer: buyer pays partner directly; BidVex auto-charges 3% to partner card on file."
        else:
            charge_buyer_via_stripe = True
            charge_seller_via_stripe = False  # deducted from buyer payment in escrow split
            notes = "Partner Stripe: buyer charged hammer + partner BP + taxes; 3% deducted from partner payout."

    # ── Route 2: VEHICLE DEALER seller ───────────────────────────────────
    elif seller_type == "vehicle_dealer":
        buyer_premium_rate = VEHICLE_DEALER_BUYER_RATE
        buyer_premium = hammer * VEHICLE_DEALER_BUYER_RATE
        seller_commission = Decimal("0")
        seller_commission_rate = Decimal("0")
        charge_buyer_via_stripe = True
        charge_seller_card_separately = False
        notes = "Vehicle dealer: 2.5% buyer fee. Dealer pays $0 per transaction (annual $100 platform fee billed separately)."

    # ── Route 3: STORAGE FACILITY seller ─────────────────────────────────
    elif seller_type == "storage_facility":
        buyer_premium = Decimal("0")
        buyer_premium_rate = Decimal("0")
        seller_commission_rate = STORAGE_FACILITY_RATE
        seller_commission = hammer * STORAGE_FACILITY_RATE
        charge_buyer_via_stripe = False  # buyer pays facility directly (cash on site etc.)
        charge_seller_card_separately = True
        notes = "Storage facility: buyer pays facility directly. BidVex auto-charges 5% commission to facility card on file."

    # ── Route 4: INDIVIDUAL seller ───────────────────────────────────────
    elif seller_type == "individual":
        buyer_premium_rate = INDIVIDUAL_BUYER_RATES.get(buyer_tier_norm, INDIVIDUAL_BUYER_RATES["standard"])
        buyer_premium = hammer * buyer_premium_rate
        seller_commission_rate = INDIVIDUAL_SELLER_RATES.get(seller_tier_norm, INDIVIDUAL_SELLER_RATES["standard"])
        seller_commission = hammer * seller_commission_rate
        charge_buyer_via_stripe = True
        charge_seller_card_separately = False  # commission deducted from payout
        notes = f"Individual: buyer={buyer_tier_norm} ({float(buyer_premium_rate)*100:.1f}% BP), seller={seller_tier_norm} ({float(seller_commission_rate)*100:.1f}% comm)."

    else:
        raise ValueError(f"Unsupported seller_account_type: {seller_account_type!r}")

    # ── Taxes — GST + QST on platform-side amounts only (per spec) ──────
    # iter209: round each tax to the cent BEFORE summing so the buyer's
    # displayed invoice lines (BP / GST / QST) always sum to the subtotal.
    # Spec worked example: $3.50 BP → GST $0.18 + QST $0.35 = $0.53 → total $104.03.
    _D_CENT = Decimal("0.01")

    def _q(x: Decimal) -> Decimal:
        return x.quantize(_D_CENT, rounding=ROUND_HALF_UP)

    buyer_premium = _q(buyer_premium)
    buyer_gst = _q(buyer_premium * QC_GST_RATE)
    buyer_qst = _q(buyer_premium * QC_QST_RATE)
    buyer_taxes = buyer_gst + buyer_qst
    buyer_subtotal = (hammer + buyer_premium + buyer_taxes) if charge_buyer_via_stripe else Decimal("0")

    seller_commission = _q(seller_commission)
    seller_gst = _q(seller_commission * QC_GST_RATE)
    seller_qst = _q(seller_commission * QC_QST_RATE)
    seller_commission_total = seller_commission + seller_gst + seller_qst

    # ── Stripe gross-up routing ──────────────────────────────────────────
    buyer_stripe_fee = _stripe_gross_up(buyer_subtotal, card_type) if charge_buyer_via_stripe else Decimal("0")
    buyer_total_charged = buyer_subtotal + buyer_stripe_fee
    buyer_stripe_cents = int((buyer_total_charged * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

    seller_stripe_fee = _stripe_gross_up(seller_commission_total, card_type) if charge_seller_card_separately else Decimal("0")

    # ── Seller payout (only meaningful when charge_buyer_via_stripe) ────
    if seller_type == "partner" and charge_buyer_via_stripe:
        # Buyer pays hammer + partner BP via Stripe → escrow → partner gets hammer + BP - 3% - taxes
        seller_payout = (hammer + buyer_premium) - seller_commission_total
    elif seller_type == "individual" and charge_buyer_via_stripe:
        seller_payout = hammer - seller_commission_total
    elif seller_type == "vehicle_dealer":
        seller_payout = hammer  # dealer always gets full hammer
    elif seller_type == "storage_facility":
        seller_payout = Decimal("0")  # buyer pays facility directly outside Stripe
    elif seller_type == "partner" and charge_seller_card_separately:
        seller_payout = Decimal("0")  # buyer paid partner directly, BidVex only charges commission
    else:
        seller_payout = hammer

    # ── BidVex revenue (net, pre-tax) ───────────────────────────────────
    bidvex_revenue = buyer_premium + seller_commission

    result = FeeResult(
        auction_type=auction_type,
        hammer_price=_r(hammer),
        buyer_premium=_r(buyer_premium),
        buyer_premium_rate=float(buyer_premium_rate),
        buyer_gst=_r(buyer_gst),
        buyer_qst=_r(buyer_qst),
        buyer_taxes=_r(buyer_taxes),
        buyer_subtotal=_r(buyer_subtotal),
        buyer_stripe_fee=_r(buyer_stripe_fee),
        buyer_total_charged=_r(buyer_total_charged),
        buyer_stripe_cents=buyer_stripe_cents,
        seller_commission=_r(seller_commission),
        seller_commission_rate=float(seller_commission_rate),
        seller_gst=_r(seller_gst),
        seller_qst=_r(seller_qst),
        seller_commission_total=_r(seller_commission_total),
        seller_stripe_fee=_r(seller_stripe_fee),
        seller_payout=_r(seller_payout),
        bidvex_revenue=_r(bidvex_revenue),
        charge_buyer_via_stripe=charge_buyer_via_stripe,
        charge_seller_via_stripe=charge_seller_via_stripe,
        charge_seller_card_separately=charge_seller_card_separately,
        notes=notes,
    )
    return result.to_dict()


# ──────────────────────────────────────────────────────────────────────────
# Legacy FeeCalculator class — preserved for back-compat. iter209 Step 2+
# will migrate every caller to `calculate_fee()` and remove this section.
# ──────────────────────────────────────────────────────────────────────────

# Global fee constants - No cap, percentage-based
DEFAULT_BUYER_PREMIUM = Decimal("0.05")  # 5%
DEFAULT_SELLER_COMMISSION = Decimal("0.04")  # 4%

# Subscription tier fee structure - Updated for yearly billing
# Free: 4% Seller / 5% Buyer
# Premium: 2.5% Seller / 3.5% Buyer (1.5% reduction)
# VIP: 2% Seller / 3% Buyer (2% reduction)
SUBSCRIPTION_FEES = {
    "free": {
        "buyer_premium": Decimal("0.05"),  # 5%
        "seller_commission": Decimal("0.04")  # 4%
    },
    "starter": {
        "buyer_premium": Decimal("0.05"),  # 5%
        "seller_commission": Decimal("0.04")  # 4%
    },
    "premium": {
        "buyer_premium": Decimal("0.035"),  # 3.5% (1.5% discount)
        "seller_commission": Decimal("0.025")  # 2.5% (1.5% discount)
    },
    "vip": {
        "buyer_premium": Decimal("0.03"),  # 3.0% (2% discount)
        "seller_commission": Decimal("0.02")  # 2.0% (2% discount)
    }
}

# Tax rates by region — Master Pricing Structure Rule 5
TAX_RATES = {
    "QC": {
        "gst": Decimal("0.05"),  # 5% GST
        "qst": Decimal("0.09975"),  # 9.975% QST
        "combined": Decimal("0.14975"),
        "name": "GST + QST (14.975%)"
    },
    "ON": {
        "hst": Decimal("0.13"),  # 13% HST
        "combined": Decimal("0.13"),
        "name": "HST (13%)"
    },
    "NB": {"hst": Decimal("0.15"), "combined": Decimal("0.15"), "name": "HST (15%)"},
    "NL": {"hst": Decimal("0.15"), "combined": Decimal("0.15"), "name": "HST (15%)"},
    "NS": {"hst": Decimal("0.15"), "combined": Decimal("0.15"), "name": "HST (15%)"},
    "PE": {"hst": Decimal("0.15"), "combined": Decimal("0.15"), "name": "HST (15%)"},
    "AB": {"gst": Decimal("0.05"), "combined": Decimal("0.05"), "name": "GST (5%)"},
    "BC": {"gst": Decimal("0.05"), "combined": Decimal("0.05"), "name": "GST (5%)"},
    "MB": {"gst": Decimal("0.05"), "combined": Decimal("0.05"), "name": "GST (5%)"},
    "SK": {"gst": Decimal("0.05"), "combined": Decimal("0.05"), "name": "GST (5%)"},
    "YT": {"gst": Decimal("0.05"), "combined": Decimal("0.05"), "name": "GST (5%)"},
    "NT": {"gst": Decimal("0.05"), "combined": Decimal("0.05"), "name": "GST (5%)"},
    "NU": {"gst": Decimal("0.05"), "combined": Decimal("0.05"), "name": "GST (5%)"},
    "US": {"sales_tax": Decimal("0.00"), "combined": Decimal("0"), "name": "Exported Service"},
}


class FeeCalculator:
    """Calculate all fees, taxes, and net amounts for BidVex transactions"""
    
    @staticmethod
    def get_buyer_premium(subscription_tier: str) -> Decimal:
        """Get buyer premium percentage based on subscription tier"""
        tier = subscription_tier.lower() if subscription_tier else "free"
        return SUBSCRIPTION_FEES.get(tier, SUBSCRIPTION_FEES["free"])["buyer_premium"]
    
    @staticmethod
    def get_seller_commission(subscription_tier: str) -> Decimal:
        """Get seller commission percentage based on subscription tier"""
        tier = subscription_tier.lower() if subscription_tier else "free"
        return SUBSCRIPTION_FEES.get(tier, SUBSCRIPTION_FEES["free"])["seller_commission"]
    
    @staticmethod
    def calculate_buyer_total(
        hammer_price: Decimal,
        buyer_tier: str = "free",
        region: str = "QC",
        include_tax: bool = True,
        seller_is_business: bool = False
    ) -> Dict:
        """
        Calculate buyer's total out-of-pocket cost
        
        CRITICAL TAX LOGIC:
        - Individual Sellers (seller_is_business=False): 
          * NO tax on hammer price (individuals cannot collect tax)
          * Tax ONLY on buyer premium (BidVex is a business)
        - Business Sellers (seller_is_business=True):
          * Tax on hammer price (collected by seller via BidVex)
          * Tax on buyer premium (BidVex's fee)
        
        Returns:
            {
                "hammer_price": Decimal,
                "buyer_premium": Decimal,
                "buyer_premium_percent": Decimal,
                "subtotal": Decimal,
                "tax": Decimal,
                "tax_on_hammer": Decimal,
                "tax_on_premium": Decimal,
                "tax_breakdown": Dict,
                "total": Decimal,
                "seller_type": str
            }
        """
        hammer_price = Decimal(str(hammer_price))
        buyer_premium_rate = FeeCalculator.get_buyer_premium(buyer_tier)
        
        # Calculate buyer premium
        buyer_premium = hammer_price * buyer_premium_rate
        subtotal = hammer_price + buyer_premium
        
        # Initialize tax variables
        tax_on_hammer = Decimal("0")
        tax_on_premium = Decimal("0")
        tax_amount = Decimal("0")
        tax_breakdown = {}
        
        if include_tax:
            tax_rates = TAX_RATES.get(region, TAX_RATES["QC"])
            
            # CRITICAL: Tax logic based on seller type
            if seller_is_business:
                # Business Seller: Tax on BOTH hammer price and premium
                taxable_amount = subtotal
            else:
                # Individual Seller: Tax ONLY on buyer premium (hammer price is tax-free)
                taxable_amount = buyer_premium
            
            # Calculate taxes
            if "gst" in tax_rates and "qst" in tax_rates:
                # Quebec: GST on taxable amount, QST on taxable amount + GST
                gst = taxable_amount * tax_rates["gst"]
                qst = (taxable_amount + gst) * tax_rates["qst"]
                tax_amount = gst + qst
                
                # Break down tax between hammer and premium
                if seller_is_business:
                    # Tax applied to full subtotal
                    hammer_ratio = hammer_price / subtotal
                    tax_on_hammer = tax_amount * hammer_ratio
                    tax_on_premium = tax_amount * (Decimal("1") - hammer_ratio)
                else:
                    # All tax is on premium only
                    tax_on_premium = tax_amount
                    tax_on_hammer = Decimal("0")
                
                tax_breakdown = {
                    "gst": float(gst),
                    "qst": float(qst),
                    "gst_rate": float(tax_rates["gst"]),
                    "qst_rate": float(tax_rates["qst"]),
                    "tax_on_hammer": float(tax_on_hammer),
                    "tax_on_premium": float(tax_on_premium)
                }
            elif "hst" in tax_rates:
                # Ontario: HST on taxable amount
                hst = taxable_amount * tax_rates["hst"]
                tax_amount = hst
                
                if seller_is_business:
                    hammer_ratio = hammer_price / subtotal
                    tax_on_hammer = tax_amount * hammer_ratio
                    tax_on_premium = tax_amount * (Decimal("1") - hammer_ratio)
                else:
                    tax_on_premium = tax_amount
                    tax_on_hammer = Decimal("0")
                
                tax_breakdown = {
                    "hst": float(hst),
                    "hst_rate": float(tax_rates["hst"]),
                    "tax_on_hammer": float(tax_on_hammer),
                    "tax_on_premium": float(tax_on_premium)
                }
            elif "gst" in tax_rates and "pst" in tax_rates:
                # BC: GST + PST on taxable amount
                gst = taxable_amount * tax_rates["gst"]
                pst = taxable_amount * tax_rates["pst"]
                tax_amount = gst + pst
                
                if seller_is_business:
                    hammer_ratio = hammer_price / subtotal
                    tax_on_hammer = tax_amount * hammer_ratio
                    tax_on_premium = tax_amount * (Decimal("1") - hammer_ratio)
                else:
                    tax_on_premium = tax_amount
                    tax_on_hammer = Decimal("0")
                
                tax_breakdown = {
                    "gst": float(gst),
                    "pst": float(pst),
                    "gst_rate": float(tax_rates["gst"]),
                    "pst_rate": float(tax_rates["pst"]),
                    "tax_on_hammer": float(tax_on_hammer),
                    "tax_on_premium": float(tax_on_premium)
                }
            elif "gst" in tax_rates:
                # Alberta: GST only on taxable amount
                gst = taxable_amount * tax_rates["gst"]
                tax_amount = gst
                
                if seller_is_business:
                    hammer_ratio = hammer_price / subtotal
                    tax_on_hammer = tax_amount * hammer_ratio
                    tax_on_premium = tax_amount * (Decimal("1") - hammer_ratio)
                else:
                    tax_on_premium = tax_amount
                    tax_on_hammer = Decimal("0")
                
                tax_breakdown = {
                    "gst": float(gst),
                    "gst_rate": float(tax_rates["gst"]),
                    "tax_on_hammer": float(tax_on_hammer),
                    "tax_on_premium": float(tax_on_premium)
                }
            elif "vat" in tax_rates:
                # EU: VAT on taxable amount
                vat = taxable_amount * tax_rates["vat"]
                tax_amount = vat
                
                if seller_is_business:
                    hammer_ratio = hammer_price / subtotal
                    tax_on_hammer = tax_amount * hammer_ratio
                    tax_on_premium = tax_amount * (Decimal("1") - hammer_ratio)
                else:
                    tax_on_premium = tax_amount
                    tax_on_hammer = Decimal("0")
                
                tax_breakdown = {
                    "vat": float(vat),
                    "vat_rate": float(tax_rates["vat"]),
                    "tax_on_hammer": float(tax_on_hammer),
                    "tax_on_premium": float(tax_on_premium)
                }
        
        total = subtotal + tax_amount
        
        # Calculate savings for individual seller
        savings = Decimal("0")
        if not seller_is_business and include_tax:
            # Calculate what tax WOULD have been on hammer price
            tax_rates_data = TAX_RATES.get(region, TAX_RATES["QC"])
            if "gst" in tax_rates_data and "qst" in tax_rates_data:
                would_be_gst = hammer_price * tax_rates_data["gst"]
                would_be_qst = (hammer_price + would_be_gst) * tax_rates_data["qst"]
                savings = would_be_gst + would_be_qst
        
        return {
            "hammer_price": float(hammer_price),
            "buyer_premium": float(buyer_premium),
            "buyer_premium_percent": float(buyer_premium_rate * 100),
            "subtotal": float(subtotal),
            "tax": float(tax_amount),
            "tax_on_hammer": float(tax_on_hammer),
            "tax_on_premium": float(tax_on_premium),
            "tax_breakdown": tax_breakdown,
            "total": float(total),
            "region": region,
            "tier": buyer_tier,
            "seller_type": "business" if seller_is_business else "individual",
            "tax_savings": float(savings) if savings > 0 else 0
        }
    
    @staticmethod
    def calculate_seller_net(
        hammer_price: Decimal,
        seller_tier: str = "free"
    ) -> Dict:
        """
        Calculate seller's net payout after commission
        
        Returns:
            {
                "hammer_price": Decimal,
                "seller_commission": Decimal,
                "seller_commission_percent": Decimal,
                "net_payout": Decimal
            }
        """
        hammer_price = Decimal(str(hammer_price))
        commission_rate = FeeCalculator.get_seller_commission(seller_tier)
        
        # Calculate commission
        commission = hammer_price * commission_rate
        net_payout = hammer_price - commission
        
        return {
            "hammer_price": float(hammer_price),
            "seller_commission": float(commission),
            "seller_commission_percent": float(commission_rate * 100),
            "net_payout": float(net_payout),
            "tier": seller_tier
        }
    
    @staticmethod
    def calculate_full_transaction(
        hammer_price: Decimal,
        buyer_tier: str = "free",
        seller_tier: str = "free",
        region: str = "QC",
        seller_is_business: bool = False
    ) -> Dict:
        """
        Calculate complete transaction breakdown for buyer and seller
        """
        buyer_calc = FeeCalculator.calculate_buyer_total(
            hammer_price, buyer_tier, region, True, seller_is_business
        )
        seller_calc = FeeCalculator.calculate_seller_net(
            hammer_price, seller_tier
        )
        
        return {
            "hammer_price": float(hammer_price),
            "buyer": buyer_calc,
            "seller": seller_calc,
            "platform_revenue": buyer_calc["buyer_premium"] + seller_calc["seller_commission"],
            "seller_type": "business" if seller_is_business else "individual"
        }


# Helper function for quick calculations
def calculate_buyer_total(amount: float, tier: str = "free", region: str = "QC", seller_is_business: bool = False) -> Dict:
    """Quick helper to calculate buyer total"""
    return FeeCalculator.calculate_buyer_total(Decimal(str(amount)), tier, region, True, seller_is_business)


def calculate_seller_net(amount: float, tier: str = "free") -> Dict:
    """Quick helper to calculate seller net"""
    return FeeCalculator.calculate_seller_net(Decimal(str(amount)), tier)
