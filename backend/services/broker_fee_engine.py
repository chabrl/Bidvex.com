"""
iter217 Phase 5 Hotfix v5b — Broker fee engine.

Computes the post-auction fee breakdown for a broker-mediated vehicle deal.
Sits ALONGSIDE the platform's `services/fee_calculator.py`; the standard
BidVex 2.5% platform fee is still calculated here, so a single call to
`calculate_broker_transaction()` returns the complete buyer-facing
breakdown without the caller needing to coordinate two services.

Formula reference:
    bidvex_platform_fee = hammer × 0.025
    broker_fee          = fixed_amount  OR  hammer × percentage_rate
                          (then clamped to [min_fee_cad, max_fee_cad])
    taxable_base        = bidvex_platform_fee + broker_fee
    gst                 = taxable_base × 0.05
    qst                 = taxable_base × 0.09975   (QC only)
    stripe_fee          = gross-up so the final total covers the
                          standard Stripe 2.9% + $0.30 processing fee
    total               = hammer + bidvex + broker + gst + qst + stripe
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


# Constants — keep in sync with services/fee_calculator.py.
BIDVEX_PLATFORM_FEE_RATE = 0.025
GST_RATE                 = 0.05
QST_RATE                 = 0.09975
STRIPE_PCT               = 0.029
STRIPE_FIXED_CAD         = 0.30


@dataclass
class BrokerFeeBreakdown:
    hammer_price_cad:        float
    bidvex_platform_fee_cad: float
    broker_fee_cad:          float
    gst_cad:                 float
    qst_cad:                 float
    stripe_fee_cad:          float
    total_cad:               float

    def as_dict(self) -> Dict[str, float]:
        return {
            "hammer_price_cad":        round(self.hammer_price_cad, 2),
            "bidvex_platform_fee_cad": round(self.bidvex_platform_fee_cad, 2),
            "broker_fee_cad":          round(self.broker_fee_cad, 2),
            "gst_cad":                 round(self.gst_cad, 2),
            "qst_cad":                 round(self.qst_cad, 2),
            "stripe_fee_cad":          round(self.stripe_fee_cad, 2),
            "total_cad":               round(self.total_cad, 2),
        }


def _clamp(v: float, lo: Optional[float], hi: Optional[float]) -> float:
    if lo is not None:
        v = max(v, lo)
    if hi is not None:
        v = min(v, hi)
    return v


def _broker_fee(hammer: float, fee_structure: Dict[str, Any]) -> float:
    t = (fee_structure or {}).get("type", "fixed")
    if t == "percentage":
        rate = float(fee_structure.get("percentage_rate", 0) or 0)
        fee = hammer * rate
    else:
        fee = float(fee_structure.get("fixed_amount_cad", 0) or 0)
    return _clamp(fee, fee_structure.get("min_fee_cad"), fee_structure.get("max_fee_cad"))


def _stripe_gross_up(net_target: float) -> float:
    """Returns the Stripe processing fee such that after Stripe deducts
    its (2.9% + $0.30) fee, `net_target` lands cleanly in the merchant
    account.

    Stripe takes `gross * 0.029 + 0.30`. We solve for `gross`:
        gross = (net_target + 0.30) / (1 - 0.029)
    The processing fee charged is `gross - net_target`.
    """
    if net_target <= 0:
        return 0.0
    gross = (net_target + STRIPE_FIXED_CAD) / (1 - STRIPE_PCT)
    return max(0.0, gross - net_target)


def calculate_broker_transaction(
    *,
    hammer_price:          float,
    broker_fee_structure:  Dict[str, Any],
    buyer_province:        Optional[str] = None,
) -> BrokerFeeBreakdown:
    """Return the full buyer-facing fee breakdown for a broker-mediated
    vehicle sale.

    Args:
        hammer_price:         Winning bid amount in CAD.
        broker_fee_structure: Dict with `type`, `fixed_amount_cad`,
                              `percentage_rate`, `min_fee_cad`, `max_fee_cad`.
        buyer_province:       2-letter CA code. QST is only charged for "QC".
    """
    hammer  = max(0.0, float(hammer_price or 0))
    bidvex  = hammer * BIDVEX_PLATFORM_FEE_RATE
    broker  = _broker_fee(hammer, broker_fee_structure or {})

    taxable_base = bidvex + broker
    province = (buyer_province or "").strip().upper()
    gst = taxable_base * GST_RATE
    qst = taxable_base * QST_RATE if province == "QC" else 0.0

    pre_stripe = hammer + bidvex + broker + gst + qst
    stripe_fee = _stripe_gross_up(pre_stripe)
    total      = pre_stripe + stripe_fee

    return BrokerFeeBreakdown(
        hammer_price_cad        = hammer,
        bidvex_platform_fee_cad = bidvex,
        broker_fee_cad          = broker,
        gst_cad                 = gst,
        qst_cad                 = qst,
        stripe_fee_cad          = stripe_fee,
        total_cad               = total,
    )
