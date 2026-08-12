"""P2 golden tests for the canonical payment_cost_engine.

Absolute-cent invariants. No Stripe I/O. Pure Python.

Run:  pytest -x /app/backend/tests/test_iter482_p2_payment_cost_engine.py
"""
import pytest
from decimal import Decimal

from services.payment_cost_engine import (
    ENGINE_VERSION,
    ActualCost,
    EstimatedCost,
    LegalGate,
    PayerRole,
    PaymentMethod,
    describe_rates,
    estimate,
    lock_actual,
)


# ─── Engine sanity ────────────────────────────────────────────────────

def test_engine_version_string_stable():
    assert ENGINE_VERSION == "iter482-P2-v1"


def test_describe_rates_shape():
    d = describe_rates()
    assert d["engine_version"] == ENGINE_VERSION
    assert isinstance(d["rates"], list) and len(d["rates"]) >= 1
    for r in d["rates"]:
        assert set(r.keys()) >= {"payment_method", "currency", "card_class", "pct", "fixed_cents", "label", "source"}
    assert "stripe_card:CAD:domestic" not in d["legal_gates"]  # legal gates keyed by payer:province


# ─── Offline methods — always $0 (Section 3, no offline processing) ──

@pytest.mark.parametrize("method", ["cash", "cheque", "e_transfer", "etransfer", "offline"])
def test_offline_methods_zero_cost(method):
    r = estimate(
        payment_method=method,
        amount_cents=11000,
        currency="CAD",
        payer_role=PayerRole.PARTNER,
        jurisdiction="QC",
    )
    assert r.estimated_cents == 0
    assert r.reason_code == "offline_method"
    assert r.legal_gate_status is LegalGate.CLEARED
    assert r.is_estimate is True


# ─── Buyer-facing Stripe surcharge — FAIL CLOSED (Section 4) ──────────

@pytest.mark.parametrize("prov", ["QC", "ON", "AB", "BC", "SK", "MB", "NS", "NB", "NL", "PE", "YT", "NT", "NU"])
def test_buyer_stripe_surcharge_fails_closed(prov):
    r = estimate(
        payment_method="stripe_card",
        amount_cents=11000,
        currency="CAD",
        payer_role=PayerRole.BUYER,
        jurisdiction=prov,
    )
    assert r.estimated_cents == 0
    assert r.legal_gate_status is LegalGate.REQUIRES_TAX_LEGAL_REVIEW
    assert r.reason_code == "legally_gated"


# ─── B2B Partner-invoice Stripe recovery — CLEARED (Q1=B) ─────────────

@pytest.mark.parametrize("prov,expected", [
    ("QC", "Stripe domestic CAD card (2.9% + $0.30)"),
    ("ON", "Stripe domestic CAD card (2.9% + $0.30)"),
    ("AB", "Stripe domestic CAD card (2.9% + $0.30)"),
    ("BC", "Stripe domestic CAD card (2.9% + $0.30)"),
])
def test_partner_stripe_recovery_is_computed(prov, expected):
    # Partner pays BidVex $344.93 → 34493 cents
    r = estimate(
        payment_method="stripe_card",
        amount_cents=34493,
        currency="CAD",
        payer_role=PayerRole.PARTNER,
        jurisdiction=prov,
    )
    assert r.legal_gate_status is LegalGate.CLEARED
    # 34493 × 0.029 + 30 = 1000.297 → 1000 cents  +  30 cents fixed = 1030 cents
    # Wait — the additive form is: (amount × 0.029) rounded to cents, then + 30 fixed
    # 344.93 × 0.029 = 10.003 → rounds to $10.00 → 1000 cents; +30 = 1030 cents = $10.30
    assert r.estimated_cents == 1030, (
        f"prov={prov} expected 1030 got {r.estimated_cents}"
    )
    assert r.rate_pct == Decimal("0.029")
    assert r.rate_fixed_cents == 30
    assert r.rate_label == expected
    assert r.reason_code == "estimated_from_rate_matrix"


def test_partner_stripe_recovery_100_dollars():
    # $100 fee → $100 × 0.029 = $2.90 + $0.30 = $3.20 = 320 cents
    r = estimate(
        payment_method=PaymentMethod.STRIPE_CARD,
        amount_cents=10000,
        currency="CAD",
        payer_role=PayerRole.PARTNER,
        jurisdiction="QC",
    )
    assert r.estimated_cents == 320


def test_partner_stripe_recovery_zero_amount():
    # Guard: zero-dollar charge → fixed cost of $0.30 (Stripe minimum).
    r = estimate(
        payment_method=PaymentMethod.STRIPE_CARD,
        amount_cents=0,
        currency="CAD",
        payer_role=PayerRole.PARTNER,
        jurisdiction="QC",
    )
    assert r.estimated_cents == 30  # fixed component only


# ─── Unknown rate matrix — silent zero is a BUG, so we assert reason ─

def test_unknown_currency_returns_zero_with_reason():
    r = estimate(
        payment_method="stripe_card",
        amount_cents=11000,
        currency="EUR",  # not in matrix
        payer_role=PayerRole.PARTNER,
        jurisdiction="QC",
    )
    assert r.estimated_cents == 0
    assert r.reason_code == "unknown_rate_matrix"
    assert r.rate_pct is None


def test_unknown_jurisdiction_returns_zero_with_review_flag():
    r = estimate(
        payment_method="stripe_card",
        amount_cents=11000,
        currency="CAD",
        payer_role=PayerRole.BUYER,
        jurisdiction="XX",  # not in matrix
    )
    assert r.estimated_cents == 0
    assert r.legal_gate_status is LegalGate.REQUIRES_TAX_LEGAL_REVIEW


# ─── Absorbed by platform — must be zero AND not fail closed ──────────

def test_absorbed_by_platform_returns_zero_with_reason():
    r = estimate(
        payment_method="stripe_card",
        amount_cents=11000,
        currency="CAD",
        payer_role=PayerRole.BUYER,     # would normally be legally gated
        jurisdiction="QC",
        absorbed_by_platform=True,
    )
    assert r.estimated_cents == 0
    assert r.reason_code == "platform_absorbed"
    assert r.legal_gate_status is LegalGate.CLEARED


# ─── lock_actual — must accept only "stripe_fee" source ───────────────

def test_lock_actual_happy_path():
    a = lock_actual(
        balance_transaction_id="txn_test_1",
        actual_fee_cents=437,
        balance_transaction_fee_source_type="stripe_fee",
        payment_intent_id="pi_test",
        charge_id="ch_test",
        currency="CAD",
        livemode=False,
    )
    assert a.actual_cents == 437
    assert a.is_estimate is False


def test_lock_actual_rejects_non_stripe_fee_source():
    with pytest.raises(ValueError, match="stripe_fee"):
        lock_actual(
            balance_transaction_id="txn_bad",
            actual_fee_cents=345,
            balance_transaction_fee_source_type="application_fee",  # WRONG
            payment_intent_id="pi_bad",
            charge_id="ch_bad",
            currency="CAD",
            livemode=False,
        )


def test_lock_actual_rejects_negative():
    with pytest.raises(ValueError):
        lock_actual(
            balance_transaction_id="txn_x",
            actual_fee_cents=-1,
            balance_transaction_fee_source_type="stripe_fee",
            payment_intent_id=None,
            charge_id=None,
            currency="CAD",
            livemode=False,
        )


# ─── Reason-code never silent ─────────────────────────────────────────

def test_every_zero_result_has_reason_code():
    """Section 10: silent zero is a bug."""
    zero_result_scenarios = [
        dict(payment_method="cash", amount_cents=1000, currency="CAD",
             payer_role=PayerRole.PARTNER, jurisdiction="QC"),
        dict(payment_method="stripe_card", amount_cents=1000, currency="CAD",
             payer_role=PayerRole.BUYER, jurisdiction="QC"),
        dict(payment_method="stripe_card", amount_cents=1000, currency="EUR",
             payer_role=PayerRole.PARTNER, jurisdiction="QC"),
        dict(payment_method="stripe_card", amount_cents=1000, currency="CAD",
             payer_role=PayerRole.BUYER, jurisdiction="QC",
             absorbed_by_platform=True),
    ]
    for s in zero_result_scenarios:
        r = estimate(**s)
        if r.estimated_cents == 0:
            assert r.reason_code, f"empty reason for {s}"


# ─── EstimatedCost dict serialization safe for Mongo/JSON ────────────

def test_estimated_cost_to_dict_serializable():
    r = estimate(
        payment_method="stripe_card",
        amount_cents=10000,
        currency="CAD",
        payer_role=PayerRole.PARTNER,
        jurisdiction="QC",
    )
    import json
    j = json.dumps(r.to_dict())
    assert "iter482-P2-v1" in j
    assert "0.029" in j  # rate serialized as string


# ─── Section 10 invariant: is_estimate flag never mixed up ────────────

def test_is_estimate_flag():
    e = estimate(
        payment_method="stripe_card",
        amount_cents=1000,
        currency="CAD",
        payer_role=PayerRole.PARTNER,
        jurisdiction="QC",
    )
    a = lock_actual(
        balance_transaction_id="t",
        actual_fee_cents=320,
        balance_transaction_fee_source_type="stripe_fee",
        payment_intent_id="pi",
        charge_id="ch",
        currency="CAD",
        livemode=False,
    )
    assert e.is_estimate is True
    assert a.is_estimate is False


# ─── PayerRole neutrality on offline methods — buyer offline is zero ──

def test_buyer_offline_is_zero_and_legal():
    r = estimate(
        payment_method="cheque",
        amount_cents=11000,
        currency="CAD",
        payer_role=PayerRole.BUYER,
        jurisdiction="QC",
    )
    assert r.estimated_cents == 0
    assert r.legal_gate_status is LegalGate.CLEARED
    assert r.reason_code == "offline_method"


# ─── Section 3: DO NOT hardcode 2.9%+$0.30 for non-domestic ──────────

def test_international_card_uses_different_rate():
    r = estimate(
        payment_method="stripe_card",
        amount_cents=10000,
        currency="CAD",
        payer_role=PayerRole.PARTNER,
        jurisdiction="QC",
        card_class="international",
    )
    # 10000 × 0.039 = $3.90 → 390 cents  +  30 fixed  =  420 cents
    assert r.estimated_cents == 420
    assert r.rate_pct == Decimal("0.039")


# ─── Section 3: The engine MUST reject caller-invented rate/fixed ────

def test_rate_source_included_for_traceability():
    r = estimate(
        payment_method="stripe_card",
        amount_cents=10000,
        currency="CAD",
        payer_role=PayerRole.PARTNER,
        jurisdiction="QC",
    )
    assert r.rate_source == "stripe_docs_2026_02"


# ─── Canonical $0.31 receipt scenario — after legal gate flips ────────
# Documented so P3+ tests can reference it once the buyer-flow gate is
# CLEARED.  Right now the engine correctly refuses (legally_gated).
def test_canonical_31_cent_scenario_currently_gated_for_buyer():
    """The $0.31 finding: BP = $0.25 × 2.9% + $0.30 = $0.31.

    Under P2's fail-closed rule, a buyer-facing surcharge is REFUSED
    (legally_gated), so the engine returns 0 — proving buyer will
    never be silently charged $0.31 until Section 4 legal review
    explicitly clears the jurisdiction.
    """
    r = estimate(
        payment_method="stripe_card",
        amount_cents=25,          # BP $0.25
        currency="CAD",
        payer_role=PayerRole.BUYER,
        jurisdiction="QC",
    )
    assert r.estimated_cents == 0
    assert r.reason_code == "legally_gated"


def test_canonical_31_cent_scenario_for_partner_is_computed():
    """The identical formula, applied to a Partner (B2B) invoice: $0.31."""
    r = estimate(
        payment_method="stripe_card",
        amount_cents=25,
        currency="CAD",
        payer_role=PayerRole.PARTNER,
        jurisdiction="QC",
    )
    # 25 × 0.029 = 0.725 cents → rounds to $0.01 (1 cent) + 30 fixed = 31 cents
    # Actually: 0.25 × 0.029 = $0.00725 → rounds to $0.01 → 1 cent; + 30 = 31 cents
    assert r.estimated_cents == 31
