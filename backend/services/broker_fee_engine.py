"""
iter217 Phase 5 Hotfix v7 — Broker fee engine (LEGAL COMPLIANCE REWRITE).

CRITICAL LEGAL RULE
═══════════════════
BidVex is a SOFTWARE marketplace, not a vehicle dealer / financial
intermediary. Under provincial law (Quebec OPC + SAAQ, Ontario OMVIC,
Alberta AMVIC, BC VSA) only a licensed dealer / broker may handle the
monetary settlement of a vehicle. Therefore:

    ╔═══════════════════════════════════════════════════════════╗
    ║  BidVex Stripe NEVER processes the vehicle hammer price.  ║
    ║  The hammer is INFORMATIONAL ONLY — printed on invoices,  ║
    ║  but settled directly buyer ↔ broker outside the          ║
    ║  platform (wire / certified cheque / broker trust).       ║
    ╚═══════════════════════════════════════════════════════════╝

What BidVex Stripe DOES charge:
    • BidVex platform service fee (2.5% of hammer — taxable service)
    • Broker service fee (fixed $ or % of hammer — taxable service)
    • GST 5% on (platform + broker fee)
    • QST 9.975% on (platform + broker fee) — Quebec only
    • Stripe processing fee gross-up so we land net-100% whole

What BidVex Stripe NEVER charges:
    ✗ The vehicle hammer price
    ✗ Vehicle sales taxes (QST on the vehicle asset, PST, etc.) —
      those are remitted by the broker at provincial title transfer.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


# Constants — keep in sync with services/fee_calculator.py
BIDVEX_PLATFORM_FEE_RATE = 0.025
GST_RATE                 = 0.05
QST_RATE                 = 0.09975
STRIPE_PCT               = 0.029
STRIPE_FIXED_CAD         = 0.30


def _r(x: float) -> float:
    """Round half-up to 2 decimals."""
    return round(float(x) + 1e-9, 2)


def _clamp(v: float, lo: Optional[float], hi: Optional[float]) -> float:
    if lo is not None:
        v = max(v, lo)
    if hi is not None:
        v = min(v, hi)
    return v


def _compute_broker_fee(hammer: float, fs: Dict[str, Any]) -> tuple[float, Dict[str, Any]]:
    """Returns (broker_fee, details_dict)."""
    fs = fs or {}
    t = fs.get("type", "fixed")
    if t == "percentage":
        rate = float(fs.get("percentage_rate", 0) or 0)
        fee  = hammer * rate
        details = {"type": "percentage", "rate_value": rate}
    else:
        fee = float(fs.get("fixed_amount_cad", 0) or 0)
        details = {"type": "fixed", "rate_value": fee}
    fee = _clamp(fee, fs.get("min_fee_cad"), fs.get("max_fee_cad"))
    return fee, details


def _stripe_gross_up(net: float) -> tuple[float, float]:
    """Stripe takes 2.9% + $0.30 from the GROSS amount.
    Solve gross = (net + 0.30) / (1 - 0.029) so net lands clean.
    Returns (gross_total, processing_fee).
    """
    if net <= 0:
        return 0.0, 0.0
    gross = (net + STRIPE_FIXED_CAD) / (1 - STRIPE_PCT)
    return gross, gross - net


def calculate_broker_transaction(
    *,
    hammer_price:           float,
    broker_fee_structure:   Dict[str, Any],
    buyer_province:         Optional[str] = None,
    deposit_held_cad:       float = 500.0,
    quantity:               int = 1,
    multiply_hammer_by_quantity: bool = False,
) -> Dict[str, Any]:
    """Return the full fee breakdown for a broker-mediated vehicle deal.

    HAMMER PRICE IS DISPLAY-ONLY. It is NEVER added into the Stripe charge.

    ── FEATURE PATCH v9 / Feature 4 — Quantity-aware base_amount ──
    `base_amount` = `hammer_price * quantity` when `multiply_hammer_by_quantity=True`,
    otherwise `base_amount` = `hammer_price` (single-unit pricing).  All service
    fee percentages (platform 2.5%, broker percentage rate, GST, QST) and the
    Stripe gross-up run on `base_amount`-derived service fees only.  The vehicle
    hammer total displayed to the buyer also reflects the same multiplier.

    Output structure (per Senior Architect Directive v7):

        {
          "hammer_price":            float,   # display only
          "hammer_settlement":       "direct",
          "hammer_settlement_note":  str,

          "platform_fee":            float,   # 2.5% of hammer (BidVex)
          "broker_fee_details":      {"type": ..., "rate_value": ...},
          "broker_fee":              float,
          "subtotal_taxable":        float,   # platform_fee + broker_fee

          "gst":                     float,   # 5% on subtotal_taxable
          "qst":                     float,   # 9.975% on subtotal_taxable (QC only)

          "stripe_subtotal":         float,   # subtotal_taxable + gst + qst
          "stripe_processing_fee":   float,
          "stripe_total_charged":    float,   # → BidVex Stripe charge

          "deposit_held":            float,

          "summary": {
            "buyer_pays_stripe":     float,   # via BidVex Stripe
            "buyer_pays_direct":     float,   # hammer, paid to broker direct
            "buyer_total_cost":      float,
            "bidvex_earns":          float,   # platform fee net of taxes
            "broker_earns":          float,   # broker fee net of taxes
          },
        }
    """
    hammer = max(0.0, float(hammer_price or 0))
    # Quantity is always an integer >= 1; sane bounds prevent absurd math.
    try:
        qty = max(1, int(quantity or 1))
    except Exception:
        qty = 1
    multiplier = qty if multiply_hammer_by_quantity else 1
    base_amount = hammer * multiplier
    hammer_total_for_buyer = base_amount   # what the buyer settles directly with broker

    # 1. Platform fee + broker fee — computed on `base_amount`, not raw hammer.
    platform_fee = base_amount * BIDVEX_PLATFORM_FEE_RATE
    broker_fee, broker_fee_details = _compute_broker_fee(base_amount, broker_fee_structure)

    subtotal_taxable = platform_fee + broker_fee

    # 2. Taxes on SERVICE fees only (never on hammer) — P6.2 Gate 6
    # Route through the authoritative province-aware tax engine so HST
    # provinces (ON, NB, NL, NS, PE) are correctly charged HST, GST-only
    # provinces are charged 5% GST, and US/INTL/unknown fail closed to 0%.
    # Previously this branch charged GST 5% + (QST 9.975% only if QC),
    # under-collecting HST provinces by ~8-10 percentage points.
    from services.fee_calculator import tax_on as _tax_on
    _tax_bd = _tax_on(subtotal_taxable, buyer_province or "")
    gst = float(_tax_bd["gst"])
    qst = float(_tax_bd["qst"])
    hst = float(_tax_bd["hst"])

    # 3. Stripe gross-up — never includes hammer
    stripe_subtotal = subtotal_taxable + gst + qst + hst
    stripe_total_charged, stripe_processing_fee = _stripe_gross_up(stripe_subtotal)

    # 4. Round once at the boundary
    return {
        # ─── Hammer (informational only) ──────────────────────────
        "hammer_price":              _r(hammer),
        "quantity":                  qty,
        "multiply_hammer_by_quantity": bool(multiply_hammer_by_quantity and qty > 1),
        "base_amount":               _r(base_amount),
        "hammer_total":              _r(hammer_total_for_buyer),
        "hammer_settlement":         "direct",
        "hammer_settlement_note":    (
            "To be settled directly between buyer and broker via bank wire, "
            "certified cheque, or broker trust account. BidVex does not "
            "process this amount."
        ),

        # ─── Service fees (Stripe-charged) ────────────────────────
        "platform_fee":              _r(platform_fee),
        "broker_fee_details":        broker_fee_details,
        "broker_fee":                _r(broker_fee),
        "subtotal_taxable":          _r(subtotal_taxable),

        "gst":                       _r(gst),
        "qst":                       _r(qst),
        "hst":                       _r(hst),  # P6.2 Gate 6 — was 0 for ON/NS/NB/NL/PE

        "stripe_subtotal":           _r(stripe_subtotal),
        "stripe_processing_fee":     _r(stripe_processing_fee),
        "stripe_total_charged":      _r(stripe_total_charged),

        # ─── Deposit ──────────────────────────────────────────────
        "deposit_held":              _r(deposit_held_cad),

        # ─── Buyer-facing summary ─────────────────────────────────
        "summary": {
            "buyer_pays_stripe":     _r(stripe_total_charged),
            "buyer_pays_direct":     _r(hammer_total_for_buyer),
            "buyer_total_cost":      _r(stripe_total_charged + hammer_total_for_buyer),
            "bidvex_earns":          _r(platform_fee),
            "broker_earns":          _r(broker_fee),
        },
    }


# ── Backwards-compat shim ──────────────────────────────────────────────
# Older call-sites that imported `BrokerFeeBreakdown` or accessed dataclass
# attributes (`bd.hammer_price_cad`, `bd.total_cad`, `bd.as_dict()`) still
# work via this thin wrapper. We map the new dict shape onto the legacy
# field names so the test suite, the invoice model, and dashboards do not
# break while consumers migrate.

class BrokerFeeBreakdown:
    """Legacy adapter. New code should consume the dict directly."""
    __slots__ = ("_d",)

    def __init__(self, d: Dict[str, Any]):
        self._d = d

    # Legacy attribute access
    @property
    def hammer_price_cad(self) -> float:        return self._d["hammer_price"]
    @property
    def bidvex_platform_fee_cad(self) -> float: return self._d["platform_fee"]
    @property
    def broker_fee_cad(self) -> float:          return self._d["broker_fee"]
    @property
    def gst_cad(self) -> float:                 return self._d["gst"]
    @property
    def qst_cad(self) -> float:                 return self._d["qst"]
    @property
    def stripe_fee_cad(self) -> float:          return self._d["stripe_processing_fee"]
    @property
    def total_cad(self) -> float:
        """Legacy field: total CAD a buyer must pay (Stripe charge ONLY —
        no longer includes hammer per v7 legal compliance refactor)."""
        return self._d["stripe_total_charged"]

    def as_dict(self) -> Dict[str, Any]:
        # New consumers get the rich v7 dict.
        return self._d


def calculate_broker_transaction_legacy(
    *,
    hammer_price:          float,
    broker_fee_structure:  Dict[str, Any],
    buyer_province:        Optional[str] = None,
    quantity:              int = 1,
    multiply_hammer_by_quantity: bool = False,
) -> BrokerFeeBreakdown:
    """Legacy API surface — returns a BrokerFeeBreakdown adapter wrapping the
    new dict. Used by code paths that still use dataclass attribute access.
    """
    return BrokerFeeBreakdown(calculate_broker_transaction(
        hammer_price          = hammer_price,
        broker_fee_structure  = broker_fee_structure,
        buyer_province        = buyer_province,
        quantity              = quantity,
        multiply_hammer_by_quantity = multiply_hammer_by_quantity,
    ))
