"""BidVex Canonical Payment-Cost Engine (iter482 P2).

**Single source of truth for payment-processing costs across the platform.**

Design principles (per Master Payment Remediation Section 3, 4, 5, 7, 10)
-----------------------------------------------------------------------
1. **No duplicated 2.9%+$0.30 formulas anywhere else.**  Every payment-cost
   calculation on the platform MUST route through this module.

2. **Distinguish estimated vs actual processing cost.**
   `estimate(...)` returns an `EstimatedCost` object with a computed
   `estimated_cents` and `is_estimate=True`.  Once the transaction
   settles, `lock_actual(...)` records the Stripe-reported actual fee
   from the connected account's BalanceTransaction; only then does
   `actual_cents` become authoritative.

3. **Legal-gate for buyer-facing surcharges — FAIL CLOSED.**
   When the `payer_role == "buyer"` and the jurisdiction / payment
   method combination has not been legally cleared, `estimated_cents=0`
   and `legal_gate_status = "REQUIRES_TAX_LEGAL_REVIEW"`.  The caller
   MUST NOT surface the charge to the buyer in that state.

4. **Payment-method + currency + jurisdiction awareness.**
   The engine does not hardcode 2.9%+$0.30 as universal.  It reads the
   applicable rate from a per-(method, currency, region) matrix.
   Unknown combinations fail closed.

5. **Never invent a tax rule.**  This engine reports the processing
   COST only.  Tax-on-processing (if applicable in a jurisdiction) is
   the tax engine's job, not this module's.

6. **Immutable snapshots.**  A `PaymentCostSnapshot` object captures the
   inputs, formula version, engine version, and result.  It is
   suitable for persistence on `payment_charges` / `receipts`.

7. **Never claim an estimate is an actual.**  Any caller that renders
   the estimate to the payer MUST also render the phrase "estimated"
   until the actual is locked from Stripe.

8. **Silent zero is a bug.**  If the engine returns `cents=0` it must
   also return a non-empty `reason_code` explaining why (e.g.
   `payer_absorbed`, `legally_gated`, `unknown_method`).

Public API
----------
    PaymentMethod    — Enum: STRIPE_CARD, CASH, CHEQUE, E_TRANSFER, INTERAC
    PayerRole        — Enum: BUYER, PARTNER, SELLER, PLATFORM, SUBSCRIBER
    LegalGate        — Enum: CLEARED, REQUIRES_TAX_LEGAL_REVIEW, PROHIBITED
    EstimatedCost    — dataclass returned by `estimate(...)`
    ActualCost       — dataclass returned by `lock_actual(...)`
    PaymentCostSnapshot — persistable record of (inputs + result)
    estimate(...)          — returns EstimatedCost
    lock_actual(...)       — returns ActualCost given Stripe BalanceTransaction data
    describe_rates()       — returns the rate matrix for admin display
    ENGINE_VERSION         — "iter482-P2-v1"
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
from typing import Any, Dict, Optional


ENGINE_VERSION = "iter482-P2-v1"


# ─── Enums ────────────────────────────────────────────────────────────

class PaymentMethod(str, Enum):
    STRIPE_CARD = "stripe_card"       # domestic or international card via Stripe
    CASH = "cash"                      # offline cash payment
    CHEQUE = "cheque"                  # offline cheque
    E_TRANSFER = "e_transfer"          # Interac e-Transfer (offline)
    OFFLINE = "offline"                # generic offline placeholder

    @classmethod
    def coerce(cls, v):
        if isinstance(v, cls):
            return v
        if not v:
            return cls.OFFLINE
        s = str(v).lower().replace("-", "_")
        if s in ("stripe", "stripe_card", "card"):
            return cls.STRIPE_CARD
        if s in ("interac", "e_transfer", "etransfer"):
            return cls.E_TRANSFER
        try:
            return cls(s)
        except ValueError:
            return cls.OFFLINE


class PayerRole(str, Enum):
    BUYER = "buyer"
    PARTNER = "partner"
    SELLER = "seller"
    PLATFORM = "platform"       # BidVex itself absorbing the cost
    SUBSCRIBER = "subscriber"   # subscription payment


class LegalGate(str, Enum):
    CLEARED = "CLEARED"
    REQUIRES_TAX_LEGAL_REVIEW = "REQUIRES_TAX_LEGAL_REVIEW"
    PROHIBITED = "PROHIBITED"


# ─── Rate matrix (per Section 3: NOT a universal 2.9%+$0.30) ──────────
#
# Rates below are stub, single-authoritative-source values for CAD-based
# BidVex flows.  Any change to Stripe pricing (e.g. Interac Debit,
# non-domestic card, foreign currency) MUST be encoded here — not
# duplicated in a caller.

# Percentage rate (Decimal) + fixed cents (int) — never floats.
@dataclass(frozen=True)
class RateRule:
    pct: Decimal            # e.g. Decimal("0.029")
    fixed_cents: int        # e.g. 30
    label: str              # e.g. "Stripe domestic CAD card 2.9% + $0.30"
    source: str             # e.g. "stripe_docs_2026_02"


_RATE_MATRIX: Dict[tuple, RateRule] = {
    # (method, currency, card_class)
    (PaymentMethod.STRIPE_CARD, "CAD", "domestic"): RateRule(
        pct=Decimal("0.029"),
        fixed_cents=30,
        label="Stripe domestic CAD card (2.9% + $0.30)",
        source="stripe_docs_2026_02",
    ),
    (PaymentMethod.STRIPE_CARD, "CAD", "international"): RateRule(
        pct=Decimal("0.039"),
        fixed_cents=30,
        label="Stripe international CAD card (3.9% + $0.30)",
        source="stripe_docs_2026_02",
    ),
    (PaymentMethod.STRIPE_CARD, "USD", "domestic"): RateRule(
        pct=Decimal("0.029"),
        fixed_cents=30,
        label="Stripe domestic USD card (2.9% + $0.30)",
        source="stripe_docs_2026_02",
    ),
}

# Offline methods have zero processing cost.
_ZERO_METHODS = {
    PaymentMethod.CASH,
    PaymentMethod.CHEQUE,
    PaymentMethod.E_TRANSFER,
    PaymentMethod.OFFLINE,
}


# ─── Legal gate matrix — FAIL CLOSED default (Section 4) ──────────────
#
# For each (payer_role, jurisdiction), specify whether a payment-cost
# surcharge on the payer is legally cleared.  Unknown combinations
# default to REQUIRES_TAX_LEGAL_REVIEW and DO NOT surface a charge.
#
# The B2B Partner-invoice case is separately gated (per user Q1=B
# answer): Partner paying BidVex is a B2B scenario where Section 3
# explicitly permits recovery.

_LEGAL_GATE_MATRIX: Dict[tuple, LegalGate] = {
    # B2B: Partner pays BidVex their 3% platform fee → recovery permitted
    (PayerRole.PARTNER, "QC"): LegalGate.CLEARED,
    (PayerRole.PARTNER, "ON"): LegalGate.CLEARED,
    (PayerRole.PARTNER, "AB"): LegalGate.CLEARED,
    (PayerRole.PARTNER, "BC"): LegalGate.CLEARED,
    (PayerRole.PARTNER, "SK"): LegalGate.CLEARED,
    (PayerRole.PARTNER, "MB"): LegalGate.CLEARED,
    (PayerRole.PARTNER, "NS"): LegalGate.CLEARED,
    (PayerRole.PARTNER, "NB"): LegalGate.CLEARED,
    (PayerRole.PARTNER, "NL"): LegalGate.CLEARED,
    (PayerRole.PARTNER, "PE"): LegalGate.CLEARED,
    (PayerRole.PARTNER, "YT"): LegalGate.CLEARED,
    (PayerRole.PARTNER, "NT"): LegalGate.CLEARED,
    (PayerRole.PARTNER, "NU"): LegalGate.CLEARED,

    # Business subscribers paying BidVex → cleared for now (subject to
    # Section 4 legal review before deployment).
    (PayerRole.SUBSCRIBER, "QC"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.SUBSCRIBER, "ON"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.SUBSCRIBER, "AB"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.SUBSCRIBER, "BC"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,

    # BUYER-facing surcharge — fail closed everywhere until legal review
    (PayerRole.BUYER, "QC"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.BUYER, "ON"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.BUYER, "AB"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.BUYER, "BC"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.BUYER, "SK"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.BUYER, "MB"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.BUYER, "NS"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.BUYER, "NB"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.BUYER, "NL"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.BUYER, "PE"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.BUYER, "YT"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.BUYER, "NT"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,
    (PayerRole.BUYER, "NU"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,

    # Seller charge is a rare / edge case — fail closed
    (PayerRole.SELLER, "QC"): LegalGate.REQUIRES_TAX_LEGAL_REVIEW,

    # Platform "self-pay" (BidVex absorbing) is not gated legally
    (PayerRole.PLATFORM, "QC"): LegalGate.CLEARED,
    (PayerRole.PLATFORM, "ON"): LegalGate.CLEARED,
    (PayerRole.PLATFORM, "AB"): LegalGate.CLEARED,
    (PayerRole.PLATFORM, "BC"): LegalGate.CLEARED,
    (PayerRole.PLATFORM, "*"):  LegalGate.CLEARED,
}


# ─── Dataclasses ──────────────────────────────────────────────────────

@dataclass(frozen=True)
class EstimatedCost:
    """Pre-charge estimate.  Never claim this as the actual Stripe fee."""
    estimated_cents: int
    is_estimate: bool                 # always True
    payment_method: PaymentMethod
    payer_role: PayerRole
    currency: str
    jurisdiction: str
    amount_cents: int
    rate_pct: Optional[Decimal]
    rate_fixed_cents: Optional[int]
    rate_label: Optional[str]
    rate_source: Optional[str]
    legal_gate_status: LegalGate
    reason_code: str
    engine_version: str = ENGINE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Normalize Decimal + Enum for JSON friendliness
        if d.get("rate_pct") is not None:
            d["rate_pct"] = str(d["rate_pct"])
        d["payment_method"] = self.payment_method.value
        d["payer_role"] = self.payer_role.value
        d["legal_gate_status"] = self.legal_gate_status.value
        return d


@dataclass(frozen=True)
class ActualCost:
    """Locked cost — populated from Stripe BalanceTransaction after settlement."""
    actual_cents: int
    is_estimate: bool                 # always False
    balance_transaction_id: str
    balance_transaction_fee_source_type: str  # "stripe_fee" (from Stripe BT fee_details)
    payment_intent_id: Optional[str]
    charge_id: Optional[str]
    currency: str
    livemode: bool
    engine_version: str = ENGINE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PaymentCostSnapshot:
    """Persistable audit record.  Belongs on `payment_charges` or `receipts`.

    A caller creates this at charge-time with `estimate=EstimatedCost(...)`
    and `actual=None`.  Post-webhook, the settlement path fills in
    `actual=ActualCost(...)`.  Both fields are immutable once set.
    """
    estimate: EstimatedCost
    actual: Optional[ActualCost] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "estimate": self.estimate.to_dict(),
            "actual": self.actual.to_dict() if self.actual else None,
            "engine_version": ENGINE_VERSION,
        }


# ─── Helpers ─────────────────────────────────────────────────────────

def _resolve_legal_gate(payer_role: PayerRole, jurisdiction: str) -> LegalGate:
    key = (payer_role, jurisdiction.upper())
    if key in _LEGAL_GATE_MATRIX:
        return _LEGAL_GATE_MATRIX[key]
    # PLATFORM wildcard
    if payer_role == PayerRole.PLATFORM:
        return _LEGAL_GATE_MATRIX.get((PayerRole.PLATFORM, "*"), LegalGate.REQUIRES_TAX_LEGAL_REVIEW)
    return LegalGate.REQUIRES_TAX_LEGAL_REVIEW  # FAIL CLOSED


def _resolve_rate(method: PaymentMethod, currency: str, card_class: str) -> Optional[RateRule]:
    return _RATE_MATRIX.get((method, currency.upper(), (card_class or "domestic").lower()))


# ─── Public API ──────────────────────────────────────────────────────

def estimate(
    *,
    payment_method,
    amount_cents: int,
    currency: str,
    payer_role,
    jurisdiction: str,
    card_class: str = "domestic",
    absorbed_by_platform: bool = False,
) -> EstimatedCost:
    """Return a pre-charge estimate of the payment-processing cost.

    Args:
        payment_method: `PaymentMethod` (or a string coerced by
            `PaymentMethod.coerce`).  Offline methods (cash / cheque /
            e-transfer) always return cost = 0.
        amount_cents: The gross amount being charged, in cents.  Used
            to compute the percentage component of the rate.
        currency: ISO 4217, e.g. "CAD".
        payer_role: Who is paying.  Buyer-facing surcharge is
            fail-closed by default.
        jurisdiction: Two-letter province code, e.g. "QC".  Legal-gate
            lookup is (payer_role, jurisdiction).
        card_class: "domestic" | "international" (for Stripe cards).
        absorbed_by_platform: When True, the cost is returned as 0
            with `reason_code="platform_absorbed"` — used to record
            "BidVex is bearing this rail cost" on the payer's ledger
            so that receipts do not falsely display a surcharge.

    Returns:
        EstimatedCost.  A `legal_gate_status != CLEARED` result will
        have `estimated_cents = 0` and `reason_code = "legally_gated"`.
    """
    if amount_cents < 0:
        raise ValueError("amount_cents must be >= 0")

    method = PaymentMethod.coerce(payment_method)
    payer = PayerRole(payer_role) if not isinstance(payer_role, PayerRole) else payer_role
    juris = (jurisdiction or "").upper()
    cur = (currency or "").upper()

    if absorbed_by_platform:
        return EstimatedCost(
            estimated_cents=0,
            is_estimate=True,
            payment_method=method,
            payer_role=payer,
            currency=cur,
            jurisdiction=juris,
            amount_cents=amount_cents,
            rate_pct=None,
            rate_fixed_cents=None,
            rate_label=None,
            rate_source=None,
            legal_gate_status=LegalGate.CLEARED,
            reason_code="platform_absorbed",
        )

    # Offline methods — always $0.
    if method in _ZERO_METHODS:
        return EstimatedCost(
            estimated_cents=0,
            is_estimate=True,
            payment_method=method,
            payer_role=payer,
            currency=cur,
            jurisdiction=juris,
            amount_cents=amount_cents,
            rate_pct=None,
            rate_fixed_cents=None,
            rate_label=f"Offline ({method.value}) — no processing cost",
            rate_source="internal",
            legal_gate_status=LegalGate.CLEARED,
            reason_code="offline_method",
        )

    # Legal gate check — FAIL CLOSED
    gate = _resolve_legal_gate(payer, juris)
    if gate is LegalGate.REQUIRES_TAX_LEGAL_REVIEW:
        return EstimatedCost(
            estimated_cents=0,
            is_estimate=True,
            payment_method=method,
            payer_role=payer,
            currency=cur,
            jurisdiction=juris,
            amount_cents=amount_cents,
            rate_pct=None,
            rate_fixed_cents=None,
            rate_label=None,
            rate_source=None,
            legal_gate_status=gate,
            reason_code="legally_gated",
        )
    if gate is LegalGate.PROHIBITED:
        return EstimatedCost(
            estimated_cents=0,
            is_estimate=True,
            payment_method=method,
            payer_role=payer,
            currency=cur,
            jurisdiction=juris,
            amount_cents=amount_cents,
            rate_pct=None,
            rate_fixed_cents=None,
            rate_label=None,
            rate_source=None,
            legal_gate_status=gate,
            reason_code="prohibited",
        )

    # Resolve rate — never guess
    rate = _resolve_rate(method, cur, card_class)
    if rate is None:
        return EstimatedCost(
            estimated_cents=0,
            is_estimate=True,
            payment_method=method,
            payer_role=payer,
            currency=cur,
            jurisdiction=juris,
            amount_cents=amount_cents,
            rate_pct=None,
            rate_fixed_cents=None,
            rate_label=None,
            rate_source=None,
            legal_gate_status=LegalGate.CLEARED,
            reason_code="unknown_rate_matrix",
        )

    # Compute additive fee (Stripe standard): pct × amount + fixed
    # (Additive form is used when we know the buyer will bear ONLY the
    # rate, not gross-up.  For gross-up scenarios the caller decides.)
    amount_d = Decimal(amount_cents) / Decimal(100)
    fee = (amount_d * rate.pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    fee_cents = int(fee * 100) + rate.fixed_cents

    return EstimatedCost(
        estimated_cents=fee_cents,
        is_estimate=True,
        payment_method=method,
        payer_role=payer,
        currency=cur,
        jurisdiction=juris,
        amount_cents=amount_cents,
        rate_pct=rate.pct,
        rate_fixed_cents=rate.fixed_cents,
        rate_label=rate.label,
        rate_source=rate.source,
        legal_gate_status=LegalGate.CLEARED,
        reason_code="estimated_from_rate_matrix",
    )


def lock_actual(
    *,
    balance_transaction_id: str,
    actual_fee_cents: int,
    balance_transaction_fee_source_type: str,
    payment_intent_id: Optional[str],
    charge_id: Optional[str],
    currency: str,
    livemode: bool,
) -> ActualCost:
    """Record the *actual* Stripe processing fee after settlement.

    Callers MUST source `actual_fee_cents` from the corresponding
    Stripe `BalanceTransaction.fee_details[*].amount` where
    `fee_details[*].type == "stripe_fee"`, and pass
    `balance_transaction_fee_source_type = "stripe_fee"` to prove it.

    Any other source (e.g. an application_fee reversal on the partner
    side) is NOT the Stripe processing rail fee and MUST NOT be locked
    here.
    """
    if actual_fee_cents < 0:
        raise ValueError("actual_fee_cents must be >= 0")
    if balance_transaction_fee_source_type != "stripe_fee":
        raise ValueError(
            "balance_transaction_fee_source_type must be 'stripe_fee' — "
            "any other value is not the Stripe processing rail cost."
        )
    return ActualCost(
        actual_cents=int(actual_fee_cents),
        is_estimate=False,
        balance_transaction_id=balance_transaction_id,
        balance_transaction_fee_source_type=balance_transaction_fee_source_type,
        payment_intent_id=payment_intent_id,
        charge_id=charge_id,
        currency=(currency or "").upper(),
        livemode=bool(livemode),
    )


def describe_rates() -> Dict[str, Any]:
    """Admin-facing description of the current rate matrix.
    UI must display these values dynamically — not hardcode them."""
    return {
        "engine_version": ENGINE_VERSION,
        "rates": [
            {
                "payment_method": k[0].value,
                "currency": k[1],
                "card_class": k[2],
                "pct": str(v.pct),
                "fixed_cents": v.fixed_cents,
                "label": v.label,
                "source": v.source,
            }
            for k, v in _RATE_MATRIX.items()
        ],
        "legal_gates": {
            f"{k[0].value}:{k[1]}": v.value
            for k, v in _LEGAL_GATE_MATRIX.items()
        },
        "zero_cost_methods": [m.value for m in _ZERO_METHODS],
    }


__all__ = [
    "ENGINE_VERSION",
    "PaymentMethod",
    "PayerRole",
    "LegalGate",
    "RateRule",
    "EstimatedCost",
    "ActualCost",
    "PaymentCostSnapshot",
    "estimate",
    "lock_actual",
    "describe_rates",
]
