"""iter482 P3.1 API-level smoke: Path A cent-exact + payment_processing L-1 gated."""
import os
import requests
import pytest

BASE = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

# (hammer_price_dollars, buyer_tier, seller_tier)
SCENARIOS = [
    (7.00, "premium", "premium"),
    (7.00, "standard", "standard"),
    (100.00, "standard", "standard"),
    (100.00, "premium", "premium"),
    (100.00, "vip_elite", "vip_elite"),
    (250.50, "standard", "premium"),
    (250.50, "premium", "vip_elite"),
    (1000.00, "standard", "standard"),
    (1000.00, "premium", "premium"),
    (1000.00, "vip_elite", "vip_elite"),
    (12345.67, "standard", "standard"),
    (12345.67, "premium", "premium"),
    (12345.67, "vip_elite", "vip_elite"),
]


def _preview(hp, bt, st):
    r = requests.get(
        f"{BASE}/api/fees/v2/preview",
        params={"hammer_price": hp, "buyer_tier": bt, "seller_tier": st,
                "buyer_province": "QC", "seller_province": "QC"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()


@pytest.mark.parametrize("hp,bt,st", SCENARIOS)
def test_payment_processing_l1_gated(hp, bt, st):
    """L-1 gate: payment_processing.amount_cents must be 0 for all scenarios."""
    data = _preview(hp, bt, st)
    pp = data.get("payment_processing") or {}
    assert pp.get("amount_cents") == 0, f"L-1 gate broken; got {pp.get('amount_cents')}"
    assert pp.get("legal_gate_status") == "REQUIRES_TAX_LEGAL_REVIEW"


@pytest.mark.parametrize("hp,bt,st", SCENARIOS)
def test_buyer_math_cent_exact(hp, bt, st):
    """buyer_total_charged*100 == buyer_stripe_cents; buyer_total = hammer+BP+bp_tax."""
    data = _preview(hp, bt, st)
    bt_dollars = data["buyer_total_charged"]
    bt_cents = data["buyer_stripe_cents"]
    assert round(bt_dollars * 100) == bt_cents, f"total mismatch {bt_dollars} vs {bt_cents}"
    # buyer bears tax only on BP (their own service). hammer + BP + bp_taxes
    hp_v = data["hammer_price"]
    bp = data["buyer_premium"]
    bp_tax = data["buyer_taxes"]
    computed = round((hp_v + bp + bp_tax) * 100)
    assert computed == bt_cents, f"buyer math mismatch: {hp_v}+{bp}+{bp_tax}={computed/100} vs total={bt_dollars}"


def test_historical_seven_dollar_case_exact():
    """Historical $7 case buyer/premium/premium: MUST be $7.28 cents (728). NEVER 764/731/729."""
    data = _preview(7.00, "premium", "premium")
    assert data["buyer_stripe_cents"] == 728, f"Historical case: expected 728, got {data['buyer_stripe_cents']}"
    assert data["buyer_total_charged"] == 7.28
    # explicitly refuse regressions
    assert data["buyer_stripe_cents"] != 764  # phantom $0.31
    assert data["buyer_stripe_cents"] != 731  # double-tax
    assert data["buyer_stripe_cents"] != 729  # combined-rate rounding


@pytest.mark.parametrize("hp,bt,st", SCENARIOS)
def test_seller_math(hp, bt, st):
    """seller_payout = hammer - SC - sc_tax_total (- stripe_recovery)."""
    data = _preview(hp, bt, st)
    payout = data["seller_payout"]
    hp_v = data["hammer_price"]
    sc = data["seller_commission"]
    sc_tax = data["seller_taxes"]
    stripe_rec = data.get("seller_stripe_recovery", 0.0)
    expected = round((hp_v - sc - sc_tax - stripe_rec) * 100)
    got = round(payout * 100)
    assert got == expected, f"seller_payout {payout} != {hp_v}-{sc}-{sc_tax}-{stripe_rec} (expected {expected/100})"
