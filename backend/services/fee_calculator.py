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
    # iter211 P0 fix: payment_method routes WHO pays the BidVex fee.
    #   cash / e_transfer → buyer pays hammer to facility direct; BidVex
    #     auto-charges facility card 5% + GST/QST + Stripe gross-up.
    #   stripe           → buyer pays HAMMER ONLY via Stripe (no buyer BP,
    #     no buyer tax); BidVex deducts 5% + GST/QST from facility payout.
    # In BOTH scenarios the BUYER NEVER pays a BidVex fee.
    elif seller_type == "storage_facility":
        buyer_premium = Decimal("0")
        buyer_premium_rate = Decimal("0")
        seller_commission_rate = STORAGE_FACILITY_RATE
        seller_commission = hammer * STORAGE_FACILITY_RATE
        if payment in ("cash", "e_transfer", "etransfer"):
            charge_buyer_via_stripe = False  # buyer pays facility directly
            charge_seller_card_separately = True
            notes = "Storage cash/e-transfer: buyer pays facility direct. BidVex auto-charges 5% + GST/QST + Stripe gross-up to facility card."
        else:
            # Stripe payment → buyer pays hammer only via Stripe; facility receives
            # hammer minus (5% + GST + QST) from BidVex.
            charge_buyer_via_stripe = True
            charge_seller_card_separately = False
            notes = "Storage Stripe: buyer pays hammer via Stripe (no BP, no buyer fees). 5% commission + GST/QST deducted from facility payout."

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

    # iter211 P0 fix: storage_facility on Stripe payment → buyer pays hammer
    # ONLY (no BP, no buyer tax, no buyer Stripe gross-up). All BidVex revenue
    # flows from the seller-side commission deduction.
    is_storage_stripe = (seller_type == "storage_facility" and charge_buyer_via_stripe)
    if is_storage_stripe:
        buyer_subtotal = hammer  # exactly hammer
    else:
        buyer_subtotal = (hammer + buyer_premium + buyer_taxes) if charge_buyer_via_stripe else Decimal("0")

    seller_commission = _q(seller_commission)
    seller_gst = _q(seller_commission * QC_GST_RATE)
    seller_qst = _q(seller_commission * QC_QST_RATE)
    seller_commission_total = seller_commission + seller_gst + seller_qst

    # ── Stripe gross-up routing ──────────────────────────────────────────
    # iter211 P0 fix: storage-Stripe → buyer pays exactly hammer, NO gross-up.
    if is_storage_stripe:
        buyer_stripe_fee = Decimal("0")
    else:
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
        # iter211 P0 fix: payment_method determines payout shape.
        #   cash/e-transfer → buyer paid facility direct, BidVex collects from
        #     facility card → no BidVex-side payout owed.
        #   stripe → buyer paid hammer via BidVex Stripe → facility net is
        #     hammer minus (5% + GST + QST on commission).
        if is_storage_stripe:
            seller_payout = hammer - seller_commission_total
        else:
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
    
    # iter210 Step 7 — `calculate_full_transaction` deleted (callers migrated
    # to `calculate_fee()`). The other FeeCalculator helpers are still used by
    # the public Fee Helpers section and by `calculate_buyer_total` / `calculate_seller_net`
    # one-shot helpers below — they remain until those are migrated next sprint.


# Helper function for quick calculations
def calculate_buyer_total(amount: float, tier: str = "free", region: str = "QC", seller_is_business: bool = False) -> Dict:
    """Quick helper to calculate buyer total"""
    return FeeCalculator.calculate_buyer_total(Decimal(str(amount)), tier, region, True, seller_is_business)


def calculate_seller_net(amount: float, tier: str = "free") -> Dict:
    """Quick helper to calculate seller net"""
    return FeeCalculator.calculate_seller_net(Decimal(str(amount)), tier)



# ══════════════════════════════════════════════════════════════════════════
# iter211 — Legacy PricingManager (relocated from services/pricing_manager.py)
# Math is BIT-IDENTICAL to the original module. Only changes:
#   • internal `_r` → `_pm_round` (to avoid collision with fee_calculator's
#     existing `_r` which returns float instead of Decimal)
#   • module-level constants and helpers moved here so callers have a single
#     import surface
# All consumers (routes/payments.py, routes/auctions.py, routes/webhooks.py,
# routes/admin_config.py, routes/subscriptions.py, routes/fees.py,
# services/vehicle_invoice.py, services/connect_payment_engine.py,
# services/tax_engine.py, routes/payments_promotions.py) now import from
# this module. The original services/pricing_manager.py is DELETED in iter211.
# ══════════════════════════════════════════════════════════════════════════

from dataclasses import field as _pm_field, asdict as _pm_asdict
from services.vehicle_pricing import calculate_taxes as _pm_calculate_taxes, TaxBreakdown as _PmTaxBreakdown

# ─── PricingManager constants ────────────────────────────────────────────
STRIPE_PCT = Decimal("0.029")
STRIPE_FIXED = Decimal("0.30")
VEHICLE_PLATFORM_FEE_RATE = Decimal("0.025")
PARTNER_SELLER_COMMISSION_RATE = Decimal("0.03")
AFFILIATE_COMMISSION_RATE = Decimal("0.10")  # 10% of BidVex platform fee

BUYER_PREMIUM_RATES = {
    "free": Decimal("0.05"), "basic": Decimal("0.05"), "standard": Decimal("0.05"),
    "premium": Decimal("0.035"),
    "vip": Decimal("0.03"), "vip_elite": Decimal("0.03"),
    "partner": Decimal("0"),
}
SELLER_COMMISSION_RATES = {
    "free": Decimal("0.04"), "basic": Decimal("0.04"), "standard": Decimal("0.04"),
    "premium": Decimal("0.025"),
    "vip": Decimal("0.02"), "vip_elite": Decimal("0.02"),
    "partner": Decimal("0.03"),
}

STRIPE_DOMESTIC_PCT      = Decimal("0.029")
STRIPE_INTERNATIONAL_PCT = Decimal("0.039")
STRIPE_CONVERSION_PCT    = Decimal("0.059")

_PM_CARD_TYPE_RATES: Dict[str, Decimal] = {
    "domestic":      STRIPE_DOMESTIC_PCT,
    "international": STRIPE_INTERNATIONAL_PCT,
    "conversion":    STRIPE_CONVERSION_PCT,
}


def _pm_round(v: Decimal) -> Decimal:
    """Round Decimal → 2dp Decimal. Public alias `_r` is exported below for
    routes/fees.py compatibility (original PricingManager export)."""
    return v.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _pm_f(v):
    return float(v) if isinstance(v, Decimal) else v


def stripe_recovery(fees_subtotal: Decimal) -> Decimal:
    """Legacy additive formula — `(fees_subtotal × 0.029) + 0.30`.
    Under-recovers Stripe's actual cost by ~3%. Kept for back-compat;
    new code should use `gross_up_stripe_fee`."""
    if fees_subtotal <= 0:
        return Decimal("0")
    return _pm_round(fees_subtotal * STRIPE_PCT + STRIPE_FIXED)


def _pm_resolve_stripe_pct(card_type: Optional[str]) -> Decimal:
    return _PM_CARD_TYPE_RATES.get((card_type or "domestic").lower(), STRIPE_DOMESTIC_PCT)


def gross_up_stripe_fee(net_amount: Decimal,
                        card_type: Optional[str] = None,
                        pct: Optional[Decimal] = None,
                        fixed: Decimal = STRIPE_FIXED) -> Decimal:
    """Exact gross-up — `charge_total = (net + fixed) / (1 - pct)`.
    Returns the extra to add so net is preserved after Stripe deducts."""
    if net_amount <= 0:
        return Decimal("0")
    effective_pct = pct if pct is not None else _pm_resolve_stripe_pct(card_type)
    denom = Decimal("1") - effective_pct
    charge_total = (net_amount + fixed) / denom
    fee = charge_total - net_amount
    return _pm_round(fee)


def _pm_tier(raw: str) -> str:
    return (raw or "free").lower().strip()


def _pm_tax_label(tb: _PmTaxBreakdown) -> str:
    t = tb.tax_type
    if t == "HST":
        return f"HST ({_pm_f(tb.total_rate * 100):.0f}%)"
    if t == "GST+QST":
        return "GST + QST (14.975%)"
    if t == "GST":
        return f"GST ({_pm_f(tb.total_rate * 100):.0f}%)"
    return t


# ─── PricingManager result dataclasses ──────────────────────────────────

@dataclass
class InvoiceLine:
    description: str
    amount: float
    line_type: str  # fee, stripe, tax, hammer, deduction
    rate: Optional[float] = None


@dataclass
class SideInvoice:
    """One side of a split invoice (buyer OR seller)."""
    lines: list = _pm_field(default_factory=list)
    fees_subtotal: float = 0.0
    stripe_recovery: float = 0.0
    tax_amount: float = 0.0
    tax_rate: float = 0.0
    tax_type: str = ""
    tax_label: str = ""
    total: float = 0.0

    def to_dict(self):
        d = _pm_asdict(self)
        d["lines"] = [_pm_asdict(ln) for ln in self.lines]
        return d


@dataclass
class PricingResult:
    transaction_type: str  # vehicle, non_vehicle_stripe, non_vehicle_cash, subscription
    hammer_price: float = 0.0
    buyer_invoice: SideInvoice = _pm_field(default_factory=SideInvoice)
    seller_invoice: Optional[SideInvoice] = None
    buyer_tier: str = "free"
    seller_tier: str = "free"
    province: str = ""
    bidvex_revenue: float = 0.0

    def to_dict(self):
        d = {
            "transaction_type": self.transaction_type,
            "hammer_price": self.hammer_price,
            "buyer_tier": self.buyer_tier,
            "seller_tier": self.seller_tier,
            "province": self.province,
            "bidvex_revenue": self.bidvex_revenue,
            "buyer_invoice": self.buyer_invoice.to_dict(),
        }
        if self.seller_invoice:
            d["seller_invoice"] = self.seller_invoice.to_dict()
        return d


# ─── PricingManager class (UNCHANGED MATH) ──────────────────────────────

class PricingManager:
    """Canonical legacy pricing engine. Math identical to the original
    services/pricing_manager.py before iter211 relocation. Province-aware
    (HST/GST+QST/GST) via vehicle_pricing.calculate_taxes()."""

    @staticmethod
    def vehicle_auction(
        hammer_price: float,
        buyer_province: str,
        buyer_tier: str = "free",
    ) -> PricingResult:
        hp = Decimal(str(hammer_price))
        platform_fee = _pm_round(hp * VEHICLE_PLATFORM_FEE_RATE)

        sr = stripe_recovery(platform_fee)
        taxable = platform_fee + sr
        tax = _pm_calculate_taxes(taxable, buyer_province)

        total = _pm_round(platform_fee + sr + tax.total_tax)

        buyer = SideInvoice(
            lines=[
                InvoiceLine("Vehicle Platform Fee (2.5%)", _pm_f(platform_fee), "fee", 0.025),
                InvoiceLine("Stripe Processing Fee", _pm_f(sr), "stripe"),
                InvoiceLine(f"Tax — {_pm_tax_label(tax)}", _pm_f(tax.total_tax), "tax", _pm_f(tax.total_rate)),
            ],
            fees_subtotal=_pm_f(platform_fee),
            stripe_recovery=_pm_f(sr),
            tax_amount=_pm_f(tax.total_tax),
            tax_rate=_pm_f(tax.total_rate),
            tax_type=tax.tax_type,
            tax_label=_pm_tax_label(tax),
            total=_pm_f(total),
        )

        return PricingResult(
            transaction_type="vehicle",
            hammer_price=hammer_price,
            buyer_invoice=buyer,
            seller_invoice=None,
            buyer_tier=buyer_tier,
            seller_tier="n/a",
            province=buyer_province.upper(),
            bidvex_revenue=_pm_f(platform_fee),
        )

    @staticmethod
    def non_vehicle_stripe(
        hammer_price: float,
        buyer_province: str,
        buyer_tier: str = "free",
        seller_tier: str = "free",
    ) -> PricingResult:
        hp = Decimal(str(hammer_price))
        bt = _pm_tier(buyer_tier)
        st = _pm_tier(seller_tier)

        bp_rate = BUYER_PREMIUM_RATES.get(bt, BUYER_PREMIUM_RATES["free"])
        sc_rate = SELLER_COMMISSION_RATES.get(st, SELLER_COMMISSION_RATES["free"])

        bp = _pm_round(hp * bp_rate)
        sc = _pm_round(hp * sc_rate)

        # Bug 6: gross-up Stripe fee so buyer covers EXACT cost (iterate once)
        b_sr = gross_up_stripe_fee(hp + bp)
        b_taxable = bp + b_sr
        b_tax = _pm_calculate_taxes(b_taxable, buyer_province)
        b_sr = gross_up_stripe_fee(hp + bp + b_tax.total_tax)
        b_taxable = bp + b_sr
        b_tax = _pm_calculate_taxes(b_taxable, buyer_province)
        b_total = _pm_round(hp + bp + b_sr + b_tax.total_tax)

        buyer = SideInvoice(
            lines=[
                InvoiceLine("Hammer Price", _pm_f(hp), "hammer"),
                InvoiceLine(f"Buyer Premium ({_pm_f(bp_rate * 100):.1f}%)", _pm_f(bp), "fee", _pm_f(bp_rate)),
                InvoiceLine("Stripe Processing Fee", _pm_f(b_sr), "stripe"),
                InvoiceLine(f"Tax — {_pm_tax_label(b_tax)}", _pm_f(b_tax.total_tax), "tax", _pm_f(b_tax.total_rate)),
            ],
            fees_subtotal=_pm_f(bp),
            stripe_recovery=_pm_f(b_sr),
            tax_amount=_pm_f(b_tax.total_tax),
            tax_rate=_pm_f(b_tax.total_rate),
            tax_type=b_tax.tax_type,
            tax_label=_pm_tax_label(b_tax),
            total=_pm_f(b_total),
        )

        s_sr = stripe_recovery(sc)
        s_taxable = sc + s_sr
        s_tax = _pm_calculate_taxes(s_taxable, buyer_province)
        s_net = _pm_round(hp - sc - s_sr - s_tax.total_tax)

        seller = SideInvoice(
            lines=[
                InvoiceLine("Hammer Price (Gross)", _pm_f(hp), "hammer"),
                InvoiceLine(f"Seller Commission ({_pm_f(sc_rate * 100):.1f}%)", -_pm_f(sc), "deduction", _pm_f(sc_rate)),
                InvoiceLine("Stripe Transfer Fee", -_pm_f(s_sr), "stripe"),
                InvoiceLine(f"Tax on Fees — {_pm_tax_label(s_tax)}", -_pm_f(s_tax.total_tax), "tax", _pm_f(s_tax.total_rate)),
            ],
            fees_subtotal=_pm_f(sc),
            stripe_recovery=_pm_f(s_sr),
            tax_amount=_pm_f(s_tax.total_tax),
            tax_rate=_pm_f(s_tax.total_rate),
            tax_type=s_tax.tax_type,
            tax_label=_pm_tax_label(s_tax),
            total=_pm_f(s_net),
        )

        return PricingResult(
            transaction_type="non_vehicle_stripe",
            hammer_price=hammer_price,
            buyer_invoice=buyer,
            seller_invoice=seller,
            buyer_tier=bt,
            seller_tier=st,
            province=buyer_province.upper(),
            bidvex_revenue=_pm_f(bp + sc),
        )

    @staticmethod
    def non_vehicle_cash(
        hammer_price: float,
        buyer_province: str,
        buyer_tier: str = "free",
        seller_tier: str = "free",
    ) -> PricingResult:
        hp = Decimal(str(hammer_price))
        bt = _pm_tier(buyer_tier)
        st = _pm_tier(seller_tier)

        bp_rate = BUYER_PREMIUM_RATES.get(bt, BUYER_PREMIUM_RATES["free"])
        sc_rate = SELLER_COMMISSION_RATES.get(st, SELLER_COMMISSION_RATES["free"])

        bp = _pm_round(hp * bp_rate)
        sc = _pm_round(hp * sc_rate)

        b_sr = stripe_recovery(bp)
        b_taxable = bp + b_sr
        b_tax = _pm_calculate_taxes(b_taxable, buyer_province)
        b_total = _pm_round(bp + b_sr + b_tax.total_tax)

        buyer = SideInvoice(
            lines=[
                InvoiceLine(f"Buyer Premium ({_pm_f(bp_rate * 100):.1f}%)", _pm_f(bp), "fee", _pm_f(bp_rate)),
                InvoiceLine("Stripe Processing Fee", _pm_f(b_sr), "stripe"),
                InvoiceLine(f"Tax — {_pm_tax_label(b_tax)}", _pm_f(b_tax.total_tax), "tax", _pm_f(b_tax.total_rate)),
            ],
            fees_subtotal=_pm_f(bp),
            stripe_recovery=_pm_f(b_sr),
            tax_amount=_pm_f(b_tax.total_tax),
            tax_rate=_pm_f(b_tax.total_rate),
            tax_type=b_tax.tax_type,
            tax_label=_pm_tax_label(b_tax),
            total=_pm_f(b_total),
        )

        s_sr = stripe_recovery(sc)
        s_taxable = sc + s_sr
        s_tax = _pm_calculate_taxes(s_taxable, buyer_province)
        s_total = _pm_round(sc + s_sr + s_tax.total_tax)

        seller = SideInvoice(
            lines=[
                InvoiceLine(f"Seller Commission ({_pm_f(sc_rate * 100):.1f}%)", _pm_f(sc), "fee", _pm_f(sc_rate)),
                InvoiceLine("Stripe Processing Fee", _pm_f(s_sr), "stripe"),
                InvoiceLine(f"Tax — {_pm_tax_label(s_tax)}", _pm_f(s_tax.total_tax), "tax", _pm_f(s_tax.total_rate)),
            ],
            fees_subtotal=_pm_f(sc),
            stripe_recovery=_pm_f(s_sr),
            tax_amount=_pm_f(s_tax.total_tax),
            tax_rate=_pm_f(s_tax.total_rate),
            tax_type=s_tax.tax_type,
            tax_label=_pm_tax_label(s_tax),
            total=_pm_f(s_total),
        )

        return PricingResult(
            transaction_type="non_vehicle_cash",
            hammer_price=hammer_price,
            buyer_invoice=buyer,
            seller_invoice=seller,
            buyer_tier=bt,
            seller_tier=st,
            province=buyer_province.upper(),
            bidvex_revenue=_pm_f(bp + sc),
        )

    @staticmethod
    def flat_purchase(
        base_price: float,
        buyer_province: str,
        label: str = "Subscription",
    ) -> PricingResult:
        price = Decimal(str(base_price))
        sr = stripe_recovery(price)
        taxable = price + sr
        tax = _pm_calculate_taxes(taxable, buyer_province)
        total = _pm_round(price + sr + tax.total_tax)

        buyer = SideInvoice(
            lines=[
                InvoiceLine(label, _pm_f(price), "fee"),
                InvoiceLine("Stripe Processing Fee", _pm_f(sr), "stripe"),
                InvoiceLine(f"Tax — {_pm_tax_label(tax)}", _pm_f(tax.total_tax), "tax", _pm_f(tax.total_rate)),
            ],
            fees_subtotal=_pm_f(price),
            stripe_recovery=_pm_f(sr),
            tax_amount=_pm_f(tax.total_tax),
            tax_rate=_pm_f(tax.total_rate),
            tax_type=tax.tax_type,
            tax_label=_pm_tax_label(tax),
            total=_pm_f(total),
        )

        return PricingResult(
            transaction_type="flat_purchase",
            hammer_price=0,
            buyer_invoice=buyer,
            seller_invoice=None,
            province=buyer_province.upper(),
            bidvex_revenue=_pm_f(price),
        )

    @staticmethod
    def partner_auction(
        hammer_price: float,
        buyer_province: str,
        partner_bp_rate: float = 0.0,
    ) -> PricingResult:
        hp = Decimal(str(hammer_price))
        partner_bp_d = Decimal(str(partner_bp_rate or 0))
        partner_bp = _pm_round(hp * partner_bp_d)

        partner_bp_pct = _pm_f(partner_bp_d * 100)
        buyer = SideInvoice(
            lines=[
                InvoiceLine("Hammer Price", _pm_f(hp), "hammer"),
                InvoiceLine(
                    f"Buyer's Premium ({partner_bp_pct:.1f}% — set by auctioneer)",
                    _pm_f(partner_bp), "fee", _pm_f(partner_bp_d),
                ),
                InvoiceLine("BidVex Platform Fee", 0.0, "fee", 0.0),
            ],
            fees_subtotal=0.0,
            stripe_recovery=0.0,
            tax_amount=0.0,
            tax_rate=0.0,
            tax_type="N/A",
            tax_label="N/A",
            total=_pm_f(_pm_round(hp + partner_bp)),
        )

        sc = _pm_round(hp * PARTNER_SELLER_COMMISSION_RATE)
        sr = stripe_recovery(sc)
        taxable = sc + sr
        tax = _pm_calculate_taxes(taxable, buyer_province)
        s_total = _pm_round(sc + sr + tax.total_tax)

        seller = SideInvoice(
            lines=[
                InvoiceLine("Seller Commission (3.0% flat — Partner)", _pm_f(sc), "fee", 0.03),
                InvoiceLine("Stripe Processing Fee", _pm_f(sr), "stripe"),
                InvoiceLine(f"Tax — {_pm_tax_label(tax)}", _pm_f(tax.total_tax), "tax", _pm_f(tax.total_rate)),
            ],
            fees_subtotal=_pm_f(sc),
            stripe_recovery=_pm_f(sr),
            tax_amount=_pm_f(tax.total_tax),
            tax_rate=_pm_f(tax.total_rate),
            tax_type=tax.tax_type,
            tax_label=_pm_tax_label(tax),
            total=_pm_f(s_total),
        )

        return PricingResult(
            transaction_type="partner_auction",
            hammer_price=hammer_price,
            buyer_invoice=buyer,
            seller_invoice=seller,
            buyer_tier="partner",
            seller_tier="partner",
            province=buyer_province.upper(),
            bidvex_revenue=_pm_f(sc),
        )

    @staticmethod
    def calculate_fees(
        hammer_price: float,
        seller_type: str,
        buyer_province: str,
        buyer_tier: str = "free",
        seller_tier: str = "free",
        payment_method: str = "stripe",
        partner_bp_rate: float = 0.0,
    ) -> PricingResult:
        """Dispatcher — routes by seller_type. Identical to legacy module."""
        st = (seller_type or "individual").lower().strip()

        if st == "partner":
            return PricingManager.partner_auction(
                hammer_price=hammer_price,
                buyer_province=buyer_province,
                partner_bp_rate=partner_bp_rate,
            )

        if st not in ("individual", "enterprise"):
            raise ValueError(f"Unknown seller_type: '{seller_type}'")

        pm = (payment_method or "stripe").lower().strip()
        if pm in ("cash", "etransfer", "e-transfer"):
            return PricingManager.non_vehicle_cash(
                hammer_price=hammer_price,
                buyer_province=buyer_province,
                buyer_tier=buyer_tier,
                seller_tier=seller_tier,
            )
        return PricingManager.non_vehicle_stripe(
            hammer_price=hammer_price,
            buyer_province=buyer_province,
            buyer_tier=buyer_tier,
            seller_tier=seller_tier,
        )

    @staticmethod
    def affiliate_commission(bidvex_revenue: float) -> float:
        """Affiliate payout = 10% of BidVex's platform fee revenue."""
        rev = Decimal(str(bidvex_revenue))
        return _pm_f(_pm_round(rev * AFFILIATE_COMMISSION_RATE))
