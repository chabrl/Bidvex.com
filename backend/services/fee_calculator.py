"""
BidVex Fee & Cost Calculation Engine — iter350 CANONICAL SOURCE OF TRUTH

Per the /app/memory/PAYMENT_INFRASTRUCTURE.md v2 specification (CRA-compliant).

Three universal rules (enforced by this module):

1. **Stripe recovery is on BidVex fees only.**
   Formula: `stripe_recovery = (bidvex_fee × 0.029) + $0.30`.
   Never applied to hammer price, subscription base, or deposit amount.

2. **Taxes follow the recipient of each service (CRA Place-of-Supply rule).**
   Each BidVex fee is a distinct "supply of a service" under ETA §142.1:
     - Buyer premium         → taxed at BUYER's province
     - Seller commission     → taxed at SELLER's province
     - Partner 3% fee        → taxed at PARTNER's province
     - Vehicle 2.5% fee      → taxed at BUYER's province (buyer pays it)
     - Storage 5% BP         → taxed at BUYER's province (iter443 — buyer pays)
     - Broker's BidVex 2.5%  → taxed at BUYER's province
     - International recipient → 0% (Sched. VI Part V §7 zero-rated)

3. **Every calculation flows through `calculate_fee()`.**
   No caller anywhere in the codebase may compute rates inline.
   Tax rates come from `services.tax_rate_config` (DB-backed, admin editable).

Account-type routing:
    individual/enterprise → buyer-tier BP + seller-tier commission
    partner               → partner-set BP (buyer) + 3% platform fee (partner pays)
    vehicle_dealer        → 2.5% buyer fee, $0 to dealer per transaction
    storage_facility      → 5% buyer premium (BUYER pays), $0 to facility (iter443)
    broker                → 2.5% BidVex fee + broker's own fee (both buyer-paid)

Every result carries `fee_model_version="iter350"` for audit reproducibility.
Legacy `FeeCalculator` class + `PricingManager` class remain below for the
non-fee helpers still consumed by tax_engine / vehicle_invoice / vehicle_pricing.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Optional

from services.tax_rate_config import (
    get_tax_rate_sync,
    normalize_province,
    BOOTSTRAP_RATES,
)


# ═══════════════════════════════════════════════════════════════════════════
# iter350 — Canonical constants (admin-configurable via Pricing Engine)
# ═══════════════════════════════════════════════════════════════════════════

# Buyer premium (% of hammer) — Individual & Enterprise sellers, by BUYER tier
INDIVIDUAL_BUYER_RATES: Dict[str, Decimal] = {
    "standard":  Decimal("0.050"),
    "premium":   Decimal("0.035"),
    "vip_elite": Decimal("0.030"),
}
# Seller commission (% of hammer) — Individual & Enterprise, by SELLER tier
INDIVIDUAL_SELLER_RATES: Dict[str, Decimal] = {
    "standard":  Decimal("0.040"),
    "premium":   Decimal("0.025"),
    "vip_elite": Decimal("0.020"),
}
# Legacy tier aliases — kept for back-compat as existing users carry these
TIER_ALIASES: Dict[str, str] = {
    "free":     "standard",
    "starter":  "standard",
    "basic":    "standard",
    "vip":      "vip_elite",
    "partner":  "standard",         # partner accounts default to standard for
                                    # buyer premium display only (partners pay
                                    # a flat 3% platform fee, not tier-based)
}

PARTNER_PLATFORM_RATE     = Decimal("0.030")   # 3% of hammer → BidVex
VEHICLE_DEALER_BUYER_RATE = Decimal("0.025")   # 2.5% of hammer → BidVex (buyer pays)
STORAGE_FACILITY_RATE     = Decimal("0.050")   # 5% of hammer → BidVex (iter443 — BUYER pays)
BROKER_PLATFORM_RATE      = Decimal("0.025")   # 2.5% of hammer → BidVex (buyer pays)

# Stripe processing — Stripe recovery = (fee × 2.9%) + $0.30 on BidVex fee ONLY
STRIPE_PROCESSING_RATE  = Decimal("0.029")
STRIPE_FIXED_FEE        = Decimal("0.30")

# Contractor / Affiliate
CONTRACTOR_RATE_MIN     = Decimal("0.05")
CONTRACTOR_RATE_MAX     = Decimal("0.20")
AFFILIATE_DEFAULT_RATE  = Decimal("0.10")

# Vehicle deposit — pre-authorized on Stripe with capture_method="manual"
VEHICLE_DEPOSIT_CAD     = Decimal("500.00")

# iter365 — Broker annual membership (launch 50% discount → $250 for 180 days)
BROKER_ANNUAL_FEE_CAD         = Decimal("500.00")   # base
BROKER_ANNUAL_FEE_DISCOUNTED  = Decimal("250.00")   # after 50% launch discount

# QC-specific for invoice line breakout (GST + QST reported separately per RQ IN-203-V)
QC_GST_RATE = Decimal("0.05")
QC_QST_RATE = Decimal("0.09975")

# Iter350 model version — stamped on every result for audit reproducibility
FEE_MODEL_VERSION = "iter350"


# ═══════════════════════════════════════════════════════════════════════════
# iter340/341 — Campaign promo codes (kept from legacy — do not touch)
# ═══════════════════════════════════════════════════════════════════════════
PROMO_CODES: Dict[str, Dict] = {
    "summer2026": {
        "expiry": "2026-08-31T23:59:59+00:00",
        "flags": {"first_listing_free": True, "first_month_free": True},
    },
    "canada-day": {
        "expiry": "2026-07-01T23:59:59+00:00",
        "flags": {"first_listing_free": True, "first_month_free": True},
    },
}


def get_promo_definition(code: Optional[str]) -> Optional[Dict]:
    return PROMO_CODES.get((code or "").strip().lower())


def promo_code_active(code: Optional[str], now) -> bool:
    d = get_promo_definition(code)
    if not d:
        return False
    from datetime import datetime as _dt
    return now <= _dt.fromisoformat(d["expiry"])


def promo_first_listing_waiver_applies(user_doc: Optional[dict]) -> bool:
    if not user_doc:
        return False
    return bool(user_doc.get("first_listing_free")) and not bool(user_doc.get("first_listing_free_used"))


def promo_first_month_waiver_applies(user_doc: Optional[dict]) -> bool:
    if not user_doc:
        return False
    return bool(user_doc.get("first_month_free")) and not bool(user_doc.get("trial_redeemed_at"))


# ═══════════════════════════════════════════════════════════════════════════
# iter350 legacy STRIPE_RATES — kept for LEGACY `_stripe_gross_up()` callers
# only (vehicle_invoice / tax_engine flows). The canonical iter350 formula
# is `calculate_stripe_recovery()` below and it MUST be used by any new code.
# ═══════════════════════════════════════════════════════════════════════════
STRIPE_RATES: Dict[str, Decimal] = {
    "domestic":      Decimal("0.029"),
    "international": Decimal("0.039"),
    "conversion":    Decimal("0.059"),
}


# ═══════════════════════════════════════════════════════════════════════════
# Rounding helpers
# ═══════════════════════════════════════════════════════════════════════════
_CENT = Decimal("0.01")


def _q(x: Decimal) -> Decimal:
    """Round Decimal → 2dp Decimal (bankers' rounding half-up per CRA)."""
    return x.quantize(_CENT, rounding=ROUND_HALF_UP)


def _r(value: Decimal) -> float:
    """Round Decimal → 2dp → float (consumer-facing presentation)."""
    return float(_q(value))


def _normalize_tier(tier: Optional[str]) -> str:
    if not tier:
        return "standard"
    t = tier.strip().lower()
    return TIER_ALIASES.get(t, t)


# ═══════════════════════════════════════════════════════════════════════════
# iter350 CANONICAL FORMULA #1 — Stripe recovery on BidVex fee ONLY
# ═══════════════════════════════════════════════════════════════════════════
def calculate_stripe_recovery(fee_amount) -> Decimal:
    """
    Compute Stripe processing-cost recovery on a BidVex fee amount.

        stripe_recovery = (fee × 2.9%) + $0.30

    Applied ONLY on BidVex fees. NEVER on hammer price, subscription
    base, or deposit amount.

    Returns a Decimal quantized to 2dp.

    iter482 P3 note — this legacy helper is retained for the seller-side
    Stripe recovery paths (Partner platform fee, Individual seller
    commission) that ARE cleared under the B2B recipient rule.  It MUST
    NOT be used for buyer-facing surcharges — those route through
    ``services.payment_cost_engine.estimate(...)`` with
    ``payer_role=BUYER``, which fail-closes to $0 until L-1 legal review
    clears the jurisdiction.
    """
    fee = Decimal(str(fee_amount))
    if fee <= 0:
        return Decimal("0.00")
    return _q(fee * STRIPE_PROCESSING_RATE + STRIPE_FIXED_FEE)


# ═══════════════════════════════════════════════════════════════════════════
# iter482 P3 — Canonical buyer-facing Stripe recovery via payment_cost_engine
# ═══════════════════════════════════════════════════════════════════════════
def _canonical_buyer_stripe_recovery(
    base_amount: Decimal,
    buyer_prov: str,
    payment: str = "stripe",
    card_type: str = "domestic",
) -> tuple[Decimal, Dict[str, object]]:
    """Return (amount, snapshot) for the buyer-facing Stripe surcharge.

    The amount is sourced ONLY from ``services.payment_cost_engine`` with
    ``payer_role=BUYER``.  Fail-closed to $0.00 until L-1 legal review
    clears the jurisdiction (per Master Payment Remediation §3, §4).

    The returned snapshot dict is the canonical
    ``payment_processing.v1`` shape and MUST be persisted on every
    receipt / invoice / PDF alongside the numeric recovery.
    """
    from services.payment_cost_engine import (
        estimate as _pce_estimate,
        PayerRole as _PCE_Payer,
    )
    amount_cents = int((base_amount * Decimal(100)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    method = "stripe_card" if (payment or "").lower() in ("stripe", "stripe_card", "card") else (payment or "offline")
    est = _pce_estimate(
        payment_method=method,
        amount_cents=max(0, amount_cents),
        currency="CAD",
        payer_role=_PCE_Payer.BUYER,
        jurisdiction=(buyer_prov or "").upper() or "XX",
        card_class=(card_type or "domestic"),
    )
    snapshot = est.to_dict()
    snapshot["amount_cents"] = int(est.estimated_cents)
    snapshot["field_version"] = "payment_processing.v1"
    amount = (Decimal(est.estimated_cents) / Decimal(100)).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    return amount, snapshot


# ═══════════════════════════════════════════════════════════════════════════
# iter350 CANONICAL FORMULA #2 — Tax on (fee + stripe_recovery) using
# Place-of-Supply routing (DB-backed rates via tax_rate_config)
# ═══════════════════════════════════════════════════════════════════════════
def tax_on(amount, province: str) -> Dict[str, Decimal | str]:
    """Compute Canadian tax on `amount` for a recipient in `province`.

    Returns a dict:
        {
          "province": "QC" | ... | "INTL",
          "gst": Decimal, "qst": Decimal, "hst": Decimal,
          "combined_rate": Decimal, "total": Decimal, "label": str,
        }

    Rates come from db.tax_rate_config (bootstrap fallback if DB empty).
    """
    amt = Decimal(str(amount))
    code = normalize_province(province)
    row = get_tax_rate_sync(code)
    gst_rate = Decimal(str(row["gst"]))
    qst_rate = Decimal(str(row["qst"]))
    hst_rate = Decimal(str(row["hst"]))
    combined_rate = Decimal(str(row["combined"]))
    gst = _q(amt * gst_rate)
    qst = _q(amt * qst_rate)
    hst = _q(amt * hst_rate)
    total = _q(amt * combined_rate)
    return {
        "province": code,
        "gst": gst,
        "qst": qst,
        "hst": hst,
        "combined_rate": combined_rate,
        "total": total,
        "label": str(row["label"]),
    }


# ═══════════════════════════════════════════════════════════════════════════
# iter350 CANONICAL FORMULA #3 — Contractor commission (% of BidVex fee)
# ═══════════════════════════════════════════════════════════════════════════
def calculate_contractor_commission(bidvex_fee_collected, contractor_rate) -> Decimal:
    """Contractor commission = BidVex fee × contractor's rate.
    Rate MUST be clamped to [CONTRACTOR_RATE_MIN, CONTRACTOR_RATE_MAX] by
    the caller before invoking this — this function performs no clamp.
    """
    fee = Decimal(str(bidvex_fee_collected))
    rate = Decimal(str(contractor_rate))
    return _q(fee * rate)


# ═══════════════════════════════════════════════════════════════════════════
# iter350 legacy Stripe gross-up — kept ONLY for legacy vehicle_invoice /
# tax_engine flows that haven't migrated yet. NEW CODE MUST NOT USE THIS.
# ═══════════════════════════════════════════════════════════════════════════
def _stripe_gross_up(subtotal: Decimal, card_type: str) -> Decimal:
    """LEGACY exact gross-up: (subtotal + 0.30) / (1 - rate) - subtotal.
    Under iter350 spec, use `calculate_stripe_recovery(fee)` instead."""
    rate = STRIPE_RATES.get((card_type or "domestic").lower(), STRIPE_RATES["domestic"])
    if subtotal <= 0:
        return Decimal("0")
    return ((subtotal + STRIPE_FIXED_FEE) / (Decimal("1") - rate)) - subtotal


# ═══════════════════════════════════════════════════════════════════════════
# FeeResult dataclass — shape of every `calculate_fee()` return
# ═══════════════════════════════════════════════════════════════════════════
@dataclass
class FeeResult:
    auction_type: str
    seller_type: str
    hammer_price: float

    # ── Buyer side (buyer premium + buyer's Stripe recovery + buyer tax) ──
    buyer_premium: float
    buyer_premium_rate: float
    buyer_stripe_recovery: float
    buyer_gst: float
    buyer_qst: float
    buyer_hst: float
    buyer_taxes: float
    buyer_tax_label: str
    buyer_tax_province: str
    buyer_subtotal: float          # hammer + BP + tax + Stripe recovery
    buyer_total_charged: float     # what BidVex charges the buyer's card
    buyer_stripe_cents: int

    # ── Seller side (seller commission + seller's Stripe rec + seller tax) ──
    seller_commission: float
    seller_commission_rate: float
    seller_stripe_recovery: float
    seller_gst: float
    seller_qst: float
    seller_hst: float
    seller_taxes: float
    seller_tax_label: str
    seller_tax_province: str
    seller_payout: float           # hammer − commission − recovery − tax

    # ── Platform metrics ──
    bidvex_revenue: float          # buyer_premium + seller_commission (pre-tax)

    # ── Routing flags ──
    charge_buyer_via_stripe: bool
    charge_seller_via_stripe: bool
    charge_seller_card_separately: bool

    # ── Meta ──
    fee_model_version: str = FEE_MODEL_VERSION
    notes: str = ""

    # ── Legacy fields kept for back-compat with existing consumers ──
    tax_province: str = ""
    tax_type: str = ""
    tax_rate: float = 0.0
    # legacy stripe-fee gross-up field name (kept so downstream consumers
    # don't break — populated with buyer_stripe_recovery)
    buyer_stripe_fee: float = 0.0
    seller_stripe_fee: float = 0.0
    seller_commission_total: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


# ═══════════════════════════════════════════════════════════════════════════
# iter350 PUBLIC API — calculate_fee()
# ═══════════════════════════════════════════════════════════════════════════
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
    # ── iter350 new params for CRA Place-of-Supply ──
    buyer_province: Optional[str] = None,
    seller_province: Optional[str] = None,
    partner_province: Optional[str] = None,
    facility_province: Optional[str] = None,
) -> dict:
    """iter350 canonical fee calculation — dispatcher by seller_account_type.

    All province params default to the caller's or 'INTL' (zero-rated) if
    absent — never to the highest rate (avoids CRA over-collection risk).

    Returns a dict (FeeResult.to_dict()) with `fee_model_version="iter350"`.
    """
    hammer = Decimal(str(hammer_price))
    if hammer < 0:
        raise ValueError("hammer_price must be >= 0")

    seller_type = (seller_account_type or "").strip().lower()
    buyer_tier_n = _normalize_tier(buyer_tier)
    seller_tier_n = _normalize_tier(seller_tier)
    payment = (payment_method or "stripe").strip().lower()

    # ── Province routing per CRA Place-of-Supply ──
    b_prov = normalize_province(buyer_province)
    s_prov = normalize_province(seller_province)
    p_prov = normalize_province(partner_province or seller_province)
    f_prov = normalize_province(facility_province or seller_province)

    if seller_type in ("individual", "enterprise"):
        return _iter350_individual(
            hammer, buyer_tier_n, seller_tier_n, b_prov, s_prov,
            payment, auction_type, seller_type
        )
    if seller_type == "partner":
        return _iter350_partner(
            hammer, Decimal(str(partner_bp_rate or 0)), p_prov, b_prov,
            payment, auction_type
        )
    if seller_type == "vehicle_dealer":
        return _iter350_vehicle(hammer, b_prov, auction_type)
    if seller_type == "storage_facility":
        return _iter350_storage(hammer, f_prov, b_prov, payment, auction_type)

    raise ValueError(f"Unsupported seller_account_type: {seller_account_type!r}")


# ─── iter350 route: individual / enterprise seller ──────────────────────
def _iter350_individual(
    hammer: Decimal,
    buyer_tier: str,
    seller_tier: str,
    buyer_prov: str,
    seller_prov: str,
    payment: str,
    auction_type: str,
    seller_type: str,
) -> dict:
    """Buyer premium taxed at BUYER's province.
    Seller commission taxed at SELLER's province.
    Two separate Stripe recovery calcs (one per fee)."""
    bp_rate = INDIVIDUAL_BUYER_RATES.get(buyer_tier, INDIVIDUAL_BUYER_RATES["standard"])
    sc_rate = INDIVIDUAL_SELLER_RATES.get(seller_tier, INDIVIDUAL_SELLER_RATES["standard"])

    # ── Buyer side (taxed at buyer's province) ──
    buyer_premium = _q(hammer * bp_rate)
    # iter482 P3 — buyer surcharge sourced ONLY from payment_cost_engine.
    # Fail-closed to $0 until L-1 legal review clears the jurisdiction.
    buyer_sr, buyer_pp = _canonical_buyer_stripe_recovery(
        buyer_premium, buyer_prov, payment=payment
    )
    buyer_tax_bd  = tax_on(buyer_premium + buyer_sr, buyer_prov)
    # iter482 P3.1 — Use per-line GST+QST+HST sum for buyer_taxes so
    # gst + qst + hst == taxes exactly.  Matches CRA/RQ remittance
    # practice and reconciles cent-exact with `calculate_general_checkout`.
    buyer_tax_total = _q(buyer_tax_bd["gst"] + buyer_tax_bd["qst"] + buyer_tax_bd["hst"])
    buyer_total   = _q(hammer + buyer_premium + buyer_sr + buyer_tax_total)

    # ── Seller side (taxed at seller's province) ──
    seller_commission = _q(hammer * sc_rate)
    seller_sr         = calculate_stripe_recovery(seller_commission)
    seller_tax_bd     = tax_on(seller_commission + seller_sr, seller_prov)
    seller_tax_total  = _q(seller_tax_bd["gst"] + seller_tax_bd["qst"] + seller_tax_bd["hst"])
    seller_payout     = _q(hammer - seller_commission - seller_sr - seller_tax_total)

    # Routing flags
    charge_buyer_via_stripe = payment == "stripe"
    charge_seller_card_separately = payment in ("cash", "e_transfer", "etransfer")

    result = FeeResult(
        auction_type=auction_type,
        seller_type=seller_type,
        hammer_price=_r(hammer),
        buyer_premium=_r(buyer_premium),
        buyer_premium_rate=float(bp_rate),
        buyer_stripe_recovery=_r(buyer_sr),
        buyer_gst=_r(buyer_tax_bd["gst"]),
        buyer_qst=_r(buyer_tax_bd["qst"]),
        buyer_hst=_r(buyer_tax_bd["hst"]),
        buyer_taxes=_r(buyer_tax_total),
        buyer_tax_label=str(buyer_tax_bd["label"]),
        buyer_tax_province=str(buyer_tax_bd["province"]),
        buyer_subtotal=_r(buyer_total if charge_buyer_via_stripe else buyer_premium + buyer_sr + buyer_tax_total),
        buyer_total_charged=_r(buyer_total if charge_buyer_via_stripe else buyer_premium + buyer_sr + buyer_tax_total),
        buyer_stripe_cents=int(((buyer_total if charge_buyer_via_stripe else buyer_premium + buyer_sr + buyer_tax_total) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        seller_commission=_r(seller_commission),
        seller_commission_rate=float(sc_rate),
        seller_stripe_recovery=_r(seller_sr),
        seller_gst=_r(seller_tax_bd["gst"]),
        seller_qst=_r(seller_tax_bd["qst"]),
        seller_hst=_r(seller_tax_bd["hst"]),
        seller_taxes=_r(seller_tax_total),
        seller_tax_label=str(seller_tax_bd["label"]),
        seller_tax_province=str(seller_tax_bd["province"]),
        seller_payout=_r(seller_payout),
        bidvex_revenue=_r(buyer_premium + seller_commission),
        charge_buyer_via_stripe=charge_buyer_via_stripe,
        charge_seller_via_stripe=False,
        charge_seller_card_separately=charge_seller_card_separately,
        notes=(
            f"{seller_type.capitalize()} — buyer_tier={buyer_tier} ({float(bp_rate)*100:.1f}% BP @ {buyer_prov}), "
            f"seller_tier={seller_tier} ({float(sc_rate)*100:.1f}% SC @ {seller_prov})."
        ),
        # Legacy compat
        tax_province=buyer_prov,
        tax_type=("GST+QST" if buyer_prov == "QC" else ("HST" if buyer_tax_bd["hst"] > 0 else ("GST" if buyer_tax_bd["gst"] > 0 else "ZERO"))),
        tax_rate=float(buyer_tax_bd["combined_rate"]),
        buyer_stripe_fee=_r(buyer_sr),
        seller_stripe_fee=_r(seller_sr),
        seller_commission_total=_r(seller_commission + seller_sr + seller_tax_total),
    )
    out = result.to_dict()
    # iter482 P3 — attach canonical payment_processing.v1 snapshot.
    # Single source of truth for the payer-facing Stripe surcharge.
    out["payment_processing"] = buyer_pp
    return out


# ─── iter350 route: partner seller ──────────────────────────────────────
def _iter350_partner(
    hammer: Decimal,
    partner_bp_rate: Decimal,
    partner_prov: str,
    buyer_prov: str,
    payment: str,
    auction_type: str,
) -> dict:
    """Partner is the recipient of BidVex's 3% platform fee → taxed at PARTNER's province.
    BidVex charges the buyer $0 in partner transactions."""
    if partner_bp_rate < 0:
        raise ValueError("partner_bp_rate must be >= 0")

    partner_bp_revenue = _q(hammer * partner_bp_rate)  # → to partner
    bidvex_fee         = _q(hammer * PARTNER_PLATFORM_RATE)  # → to BidVex
    stripe_recovery    = calculate_stripe_recovery(bidvex_fee)
    tax_bd             = tax_on(bidvex_fee + stripe_recovery, partner_prov)
    partner_owes       = _q(bidvex_fee + stripe_recovery + tax_bd["total"])

    result = FeeResult(
        auction_type=auction_type,
        seller_type="partner",
        hammer_price=_r(hammer),
        buyer_premium=_r(partner_bp_revenue),  # what buyer pays partner (100% → partner)
        buyer_premium_rate=float(partner_bp_rate),
        buyer_stripe_recovery=0.0,             # buyer pays BidVex $0
        buyer_gst=0.0, buyer_qst=0.0, buyer_hst=0.0, buyer_taxes=0.0,
        buyer_tax_label="N/A — Partner charges directly",
        buyer_tax_province=buyer_prov,
        buyer_subtotal=_r(hammer + partner_bp_revenue),
        buyer_total_charged=_r(hammer + partner_bp_revenue),
        buyer_stripe_cents=int(((hammer + partner_bp_revenue) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        seller_commission=_r(bidvex_fee),
        seller_commission_rate=float(PARTNER_PLATFORM_RATE),
        seller_stripe_recovery=_r(stripe_recovery),
        seller_gst=_r(tax_bd["gst"]), seller_qst=_r(tax_bd["qst"]), seller_hst=_r(tax_bd["hst"]),
        seller_taxes=_r(tax_bd["total"]),
        seller_tax_label=str(tax_bd["label"]),
        seller_tax_province=str(tax_bd["province"]),
        seller_payout=_r(partner_owes),   # note: this is what the PARTNER OWES BidVex
        bidvex_revenue=_r(bidvex_fee),
        charge_buyer_via_stripe=(payment == "stripe"),
        charge_seller_via_stripe=False,
        charge_seller_card_separately=payment in ("cash", "e_transfer", "etransfer"),
        notes=(
            "Partner Stripe: buyer pays partner directly (hammer + partner BP). "
            f"BidVex charges partner {float(PARTNER_PLATFORM_RATE)*100:.1f}% + Stripe recovery + tax "
            f"({tax_bd['label']} @ {partner_prov})."
        ),
        tax_province=partner_prov,
        tax_type=("GST+QST" if partner_prov == "QC" else ("HST" if tax_bd["hst"] > 0 else ("GST" if tax_bd["gst"] > 0 else "ZERO"))),
        tax_rate=float(tax_bd["combined_rate"]),
        buyer_stripe_fee=0.0,
        seller_stripe_fee=_r(stripe_recovery),
        seller_commission_total=_r(partner_owes),
    )
    out = result.to_dict()
    # ── iter480 Phase 3 canonical BidVex Platform Fee split ──
    # The Partner Platform Fee has always been $3 (=3% × hammer) but was
    # persisted under the `seller_commission` field name because the
    # FeeResult dataclass predates the canonical separation.  These
    # additive keys expose the same numeric value under its correct
    # economic name so downstream persistence + PDF renderers can
    # display "BidVex Platform Fee" instead of "Seller Commission".
    # No financial value changes; ``seller_commission`` remains
    # populated for backward compatibility with iter476 receipts,
    # existing PDF paths, and every legacy consumer.
    out["bidvex_platform_fee_rate"]   = float(PARTNER_PLATFORM_RATE)
    out["bidvex_platform_fee_amount"] = _r(bidvex_fee)
    out["bidvex_platform_fee_gst"]    = _r(tax_bd["gst"])
    out["bidvex_platform_fee_qst"]    = _r(tax_bd["qst"])
    # Canonical "true" seller commission for Partner sales is $0 —
    # exposed here so callers building the new normalized receipt
    # (iter480+) can persist seller_commission=0 while keeping the
    # legacy field populated.  Auction settlement DOES NOT read this
    # in Phase 3 (backward compat wins); it is available for Phase 4.
    out["canonical_seller_commission_for_partner"] = 0.0
    # iter482 P3 — attach canonical payment_processing.v1 snapshot for
    # the buyer.  In Model A₁ the buyer bears NO Stripe surcharge
    # (Partner is merchant of record via on_behalf_of), so the snapshot
    # reflects a platform-absorbed $0 cost.
    _, out["payment_processing"] = _canonical_buyer_stripe_recovery(
        Decimal("0"), buyer_prov, payment=payment
    )
    return out


# ─── iter350 route: vehicle dealer (non-custodial) ──────────────────────
def _iter350_vehicle(
    hammer: Decimal,
    buyer_prov: str,
    auction_type: str,
) -> dict:
    """Buyer pays BidVex 2.5% + Stripe recovery + tax on buyer's province.
    Dealer pays $0 per transaction — hammer goes directly dealer↔buyer.
    A separate deposit is pre-authorized on Stripe with capture_method="manual"."""
    platform_fee    = _q(hammer * VEHICLE_DEALER_BUYER_RATE)
    # iter482 P3 — buyer surcharge sourced ONLY from payment_cost_engine.
    stripe_recovery, buyer_pp = _canonical_buyer_stripe_recovery(
        platform_fee, buyer_prov, payment="stripe"
    )
    tax_bd          = tax_on(platform_fee + stripe_recovery, buyer_prov)
    buyer_pays      = _q(platform_fee + stripe_recovery + tax_bd["total"])

    result = FeeResult(
        auction_type=auction_type,
        seller_type="vehicle_dealer",
        hammer_price=_r(hammer),
        buyer_premium=_r(platform_fee),
        buyer_premium_rate=float(VEHICLE_DEALER_BUYER_RATE),
        buyer_stripe_recovery=_r(stripe_recovery),
        buyer_gst=_r(tax_bd["gst"]), buyer_qst=_r(tax_bd["qst"]), buyer_hst=_r(tax_bd["hst"]),
        buyer_taxes=_r(tax_bd["total"]),
        buyer_tax_label=str(tax_bd["label"]),
        buyer_tax_province=str(tax_bd["province"]),
        buyer_subtotal=_r(buyer_pays),
        buyer_total_charged=_r(buyer_pays),
        buyer_stripe_cents=int((buyer_pays * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        seller_commission=0.0,
        seller_commission_rate=0.0,
        seller_stripe_recovery=0.0,
        seller_gst=0.0, seller_qst=0.0, seller_hst=0.0, seller_taxes=0.0,
        seller_tax_label="N/A",
        seller_tax_province=str(tax_bd["province"]),
        seller_payout=_r(hammer),  # dealer collects full hammer directly
        bidvex_revenue=_r(platform_fee),
        charge_buyer_via_stripe=True,
        charge_seller_via_stripe=False,
        charge_seller_card_separately=False,
        notes=(
            f"Vehicle dealer: buyer pays {float(VEHICLE_DEALER_BUYER_RATE)*100:.1f}% platform fee + Stripe recovery + tax "
            f"({tax_bd['label']} @ {buyer_prov}). Hammer paid directly dealer↔buyer. "
            "$500 refundable deposit pre-authorized via Stripe PaymentIntent(capture_method='manual')."
        ),
        tax_province=buyer_prov,
        tax_type=("GST+QST" if buyer_prov == "QC" else ("HST" if tax_bd["hst"] > 0 else ("GST" if tax_bd["gst"] > 0 else "ZERO"))),
        tax_rate=float(tax_bd["combined_rate"]),
        buyer_stripe_fee=_r(stripe_recovery),
        seller_stripe_fee=0.0,
        seller_commission_total=0.0,
    )
    out = result.to_dict()
    # iter482 P3 — attach canonical payment_processing.v1 snapshot.
    out["payment_processing"] = buyer_pp
    return out


# ─── iter350 route: storage facility ────────────────────────────────────
def _iter350_storage(
    hammer: Decimal,
    facility_prov: str,
    buyer_prov: str,
    payment: str,
    auction_type: str,
) -> dict:
    """iter443 CORRECTED MODEL — BidVex charges the BUYER 5% buyer's premium
    on the hammer price. The storage facility is NEVER charged.

    Stripe path: buyer pays hammer + 5% BP + Stripe recovery + tax on the
    5%+recovery via card. Facility receives the full hammer.
    Cash/E-Transfer path: buyer pays hammer to facility OFFLINE. BidVex
    separately charges the buyer's card on file for 5% BP + Stripe
    recovery + tax on the 5%+recovery. Facility receives full hammer
    offline and is never invoiced by BidVex.

    Tax is applied at the BUYER's province (Place-of-Supply: buyer is the
    recipient of BidVex's supply-of-service under CRA §142.1).
    """
    buyer_premium   = _q(hammer * STORAGE_FACILITY_RATE)  # 5% of hammer → BidVex
    # iter482 P3 — buyer surcharge sourced ONLY from payment_cost_engine.
    stripe_recovery, buyer_pp = _canonical_buyer_stripe_recovery(
        buyer_premium, buyer_prov, payment=payment
    )
    tax_bd          = tax_on(buyer_premium + stripe_recovery, buyer_prov)
    buyer_bidvex    = _q(buyer_premium + stripe_recovery + tax_bd["total"])  # BidVex portion

    is_stripe = payment == "stripe"
    if is_stripe:
        # Buyer's Stripe charge = hammer + BP + recovery + tax. Facility gets full hammer.
        buyer_total = _q(hammer + buyer_bidvex)
    else:
        # Cash/E-Transfer: buyer pays hammer OFFLINE to facility. BidVex charges
        # only the BidVex portion (BP + recovery + tax) to the buyer's card.
        buyer_total = buyer_bidvex

    result = FeeResult(
        auction_type=auction_type,
        seller_type="storage_facility",
        hammer_price=_r(hammer),
        buyer_premium=_r(buyer_premium),
        buyer_premium_rate=float(STORAGE_FACILITY_RATE),
        buyer_stripe_recovery=_r(stripe_recovery),
        buyer_gst=_r(tax_bd["gst"]), buyer_qst=_r(tax_bd["qst"]), buyer_hst=_r(tax_bd["hst"]),
        buyer_taxes=_r(tax_bd["total"]),
        buyer_tax_label=str(tax_bd["label"]),
        buyer_tax_province=str(tax_bd["province"]),
        buyer_subtotal=_r(buyer_total),
        buyer_total_charged=_r(buyer_total),
        buyer_stripe_cents=int((buyer_total * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP)),
        # Facility side — ZERO. Facility receives 100% of hammer.
        seller_commission=0.0,
        seller_commission_rate=0.0,
        seller_stripe_recovery=0.0,
        seller_gst=0.0, seller_qst=0.0, seller_hst=0.0, seller_taxes=0.0,
        seller_tax_label="N/A — facility never charged by BidVex",
        seller_tax_province=facility_prov,
        seller_payout=_r(hammer),  # full hammer to facility
        bidvex_revenue=_r(buyer_premium),
        charge_buyer_via_stripe=True,   # always charge buyer via Stripe (BP for cash/etransfer too)
        charge_seller_via_stripe=False,
        charge_seller_card_separately=False,  # facility never billed
        notes=(
            f"iter443 Storage facility model: BUYER pays {float(STORAGE_FACILITY_RATE)*100:.1f}% BP "
            f"+ Stripe recovery + tax ({tax_bd['label']} @ {buyer_prov}). "
            f"Facility receives full hammer (${_r(hammer):.2f}) and is never charged."
        ),
        tax_province=buyer_prov,
        tax_type=("GST+QST" if buyer_prov == "QC" else ("HST" if tax_bd["hst"] > 0 else ("GST" if tax_bd["gst"] > 0 else "ZERO"))),
        tax_rate=float(tax_bd["combined_rate"]),
        buyer_stripe_fee=_r(stripe_recovery),
        seller_stripe_fee=0.0,
        seller_commission_total=0.0,
    )
    out = result.to_dict()
    # iter482 P3 — attach canonical payment_processing.v1 snapshot.
    out["payment_processing"] = buyer_pp
    return out


# ═══════════════════════════════════════════════════════════════════════════
# iter350 — Broker transaction (buyer pays BidVex 2.5% + broker's own fee)
# ═══════════════════════════════════════════════════════════════════════════
def calculate_broker_transaction(
    hammer_price,
    broker_fee_structure: Dict,
    buyer_province: str,
) -> Dict:
    """Broker deal — buyer pays hammer + BidVex 2.5% + broker's own fee.
    Both BidVex-fee and broker-fee are taxed at the BUYER's province
    (both are B2C supplies to the buyer under CRA Place-of-Supply).

    broker_fee_structure = {
      "type": "fixed" | "percentage",
      "fixed_amount_cad": Decimal,   # if type == "fixed"
      "percentage_rate":  Decimal,   # if type == "percentage" (0..1)
      "min_fee_cad":      Decimal,   # optional floor
      "max_fee_cad":      Decimal,   # optional ceiling
    }
    """
    hammer = Decimal(str(hammer_price))
    if hammer < 0:
        raise ValueError("hammer_price must be >= 0")

    bidvex_fee = _q(hammer * BROKER_PLATFORM_RATE)

    fs = broker_fee_structure or {}
    ftype = (fs.get("type") or "percentage").lower()
    if ftype == "fixed":
        broker_fee = _q(Decimal(str(fs.get("fixed_amount_cad", 0))))
    else:
        broker_fee = _q(hammer * Decimal(str(fs.get("percentage_rate", 0))))

    if "min_fee_cad" in fs:
        broker_fee = max(broker_fee, _q(Decimal(str(fs["min_fee_cad"]))))
    if "max_fee_cad" in fs:
        broker_fee = min(broker_fee, _q(Decimal(str(fs["max_fee_cad"]))))

    combined_fees   = _q(bidvex_fee + broker_fee)
    stripe_recovery = calculate_stripe_recovery(combined_fees)
    tax_bd          = tax_on(combined_fees + stripe_recovery, buyer_province)
    total_due       = _q(hammer + combined_fees + stripe_recovery + tax_bd["total"])
    buyer_pays_bidvex_only = _q(combined_fees + stripe_recovery + tax_bd["total"])

    return {
        "fee_model_version":         FEE_MODEL_VERSION,
        "seller_type":               "broker",
        "buyer_province":            str(tax_bd["province"]),
        "hammer_price":              _r(hammer),
        "bidvex_platform_fee":       _r(bidvex_fee),
        "bidvex_platform_rate":      float(BROKER_PLATFORM_RATE),
        "broker_fee":                _r(broker_fee),
        "combined_fees":             _r(combined_fees),
        "stripe_recovery":           _r(stripe_recovery),
        "gst":                       _r(tax_bd["gst"]),
        "qst":                       _r(tax_bd["qst"]),
        "hst":                       _r(tax_bd["hst"]),
        "tax_total":                 _r(tax_bd["total"]),
        "tax_label":                 str(tax_bd["label"]),
        "total_due_from_buyer":      _r(total_due),
        "buyer_pays_bidvex_only":    _r(buyer_pays_bidvex_only),
    }


# ═══════════════════════════════════════════════════════════════════════════
# LEGACY BACK-COMPAT SHIMS — kept so older tests / imports still resolve.
# iter350 canonical code SHOULD NOT use these.
# ═══════════════════════════════════════════════════════════════════════════

def _resolve_province(prov: Optional[str], fallback: str = "QC") -> str:
    """Legacy shim — iter350 code uses `tax_rate_config.normalize_province`."""
    code = normalize_province(prov)
    if code == "INTL":
        return fallback  # legacy contract defaulted unknown → QC
    return code


# Legacy PROVINCE_TAX_REGIME map kept as a static snapshot of the iter211
# constants for callers that read from it (older tests). New code MUST NOT
# import from here — use `tax_rate_config.get_tax_rate_sync()` instead.
_PROVINCE_TAX_REGIME = {
    "QC": {"type": "GST+QST", "gst": Decimal("0.05"), "qst": Decimal("0.09975"), "hst": Decimal("0"), "combined": Decimal("0.14975")},
    "ON": {"type": "HST", "gst": Decimal("0"), "qst": Decimal("0"), "hst": Decimal("0.13"), "combined": Decimal("0.13")},
    "NB": {"type": "HST", "gst": Decimal("0"), "qst": Decimal("0"), "hst": Decimal("0.15"), "combined": Decimal("0.15")},
    "NS": {"type": "HST", "gst": Decimal("0"), "qst": Decimal("0"), "hst": Decimal("0.15"), "combined": Decimal("0.15")},
    "PE": {"type": "HST", "gst": Decimal("0"), "qst": Decimal("0"), "hst": Decimal("0.15"), "combined": Decimal("0.15")},
    "NL": {"type": "HST", "gst": Decimal("0"), "qst": Decimal("0"), "hst": Decimal("0.15"), "combined": Decimal("0.15")},
    "AB": {"type": "GST", "gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"), "combined": Decimal("0.05")},
    "BC": {"type": "GST", "gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"), "combined": Decimal("0.05")},
    "SK": {"type": "GST", "gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"), "combined": Decimal("0.05")},
    "MB": {"type": "GST", "gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"), "combined": Decimal("0.05")},
    "NT": {"type": "GST", "gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"), "combined": Decimal("0.05")},
    "NU": {"type": "GST", "gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"), "combined": Decimal("0.05")},
    "YT": {"type": "GST", "gst": Decimal("0.05"), "qst": Decimal("0"), "hst": Decimal("0"), "combined": Decimal("0.05")},
}
PROVINCE_TAX_REGIME = _PROVINCE_TAX_REGIME


def calculate_partner_taxes(amount: Decimal, province: str) -> Dict[str, Decimal]:
    """Legacy shim — kept so iter211 tests still pass under iter350 semantics.
    Returns the OLD-format dict for back-compat. New code uses `tax_on()`."""
    code = _resolve_province(province)  # legacy fallback → QC
    regime = _PROVINCE_TAX_REGIME[code]
    return {
        "province": code,
        "type": regime["type"],
        "gst": _q(Decimal(str(amount)) * regime["gst"]),
        "qst": _q(Decimal(str(amount)) * regime["qst"]),
        "hst": _q(Decimal(str(amount)) * regime["hst"]),
        "combined_rate": regime["combined"],
        "total": _q(Decimal(str(amount)) * regime["combined"]),
    }




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
AFFILIATE_COMMISSION_RATE = Decimal("0.03")  # iter338 — 3% of BidVex platform profit

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
        """Affiliate payout = 3% of BidVex's platform fee revenue (iter338)."""
        rev = Decimal(str(bidvex_revenue))
        return _pm_f(_pm_round(rev * AFFILIATE_COMMISSION_RATE))
