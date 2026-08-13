"""iter482 P3.1 API-level smoke — Path A cent-exact reconciliation.

Post-P5 canonical:
  * Stripe-card default → buyer_stripe_recovery > 0 (payer bears the Stripe fee).
  * payment_processing.legal_gate_status == "CLEARED" and amount_cents > 0 for
    Stripe-processed charges.
  * buyer_total_charged = hammer + BP + bp_tax + buyer_stripe_recovery.

Historical $7 QC premium/premium canonical: $7.81 (781 cents).
"""
import os
import requests
import pytest


def _resolve_base() -> str:
    val = os.environ.get("REACT_APP_BACKEND_URL")
    if not val:
        # Fall back to reading frontend/.env for pytest-only invocation
        try:
            with open("/app/frontend/.env") as f:
                for line in f:
                    if line.startswith("REACT_APP_BACKEND_URL="):
                        val = line.split("=", 1)[1].strip()
                        break
        except OSError:
            pass
    if not val:
        pytest.skip("REACT_APP_BACKEND_URL not set — skipping live API smoke")
    return val.rstrip("/")


BASE = _resolve_base()

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
def test_payment_processing_p5_cleared(hp, bt, st):
    """Post-P5: Stripe-card default → L-1 CLEARED with recovery cents > 0."""
    data = _preview(hp, bt, st)
    pp = data.get("payment_processing") or {}
    assert pp.get("amount_cents", 0) > 0, f"P5 gate broken; got {pp.get('amount_cents')}"
    assert pp.get("legal_gate_status") == "CLEARED", pp
    assert pp.get("recovery_cents", 0) > 0, pp
    assert pp.get("payment_method") == "stripe_card", pp


@pytest.mark.parametrize("hp,bt,st", SCENARIOS)
def test_buyer_math_cent_exact(hp, bt, st):
    """buyer_total_charged*100 == buyer_stripe_cents; buyer_total = hammer+BP+bp_tax+stripe_recovery."""
    data = _preview(hp, bt, st)
    bt_dollars = data["buyer_total_charged"]
    bt_cents = data["buyer_stripe_cents"]
    assert round(bt_dollars * 100) == bt_cents, f"total mismatch {bt_dollars} vs {bt_cents}"
    # Post-P5: buyer bears BP+bp_tax + stripe_recovery. Total = hammer + BP + bp_tax + stripe_recovery.
    hp_v = data["hammer_price"]
    bp = data["buyer_premium"]
    bp_tax = data["buyer_taxes"]
    stripe_rec = data.get("buyer_stripe_recovery", 0.0)
    computed = round((hp_v + bp + bp_tax + stripe_rec) * 100)
    assert computed == bt_cents, (
        f"buyer math mismatch: {hp_v}+{bp}+{bp_tax}+{stripe_rec}={computed/100} "
        f"vs total={bt_dollars}"
    )


def test_historical_seven_dollar_case_exact_post_p5():
    """Historical $7 case buyer/premium/premium (Stripe default, QC): $7.81 = 781 cents.
    NEVER 7.28 (pre-P5), NEVER 7.64 (phantom $0.31), NEVER 731/729."""
    data = _preview(7.00, "premium", "premium")
    assert data["buyer_stripe_cents"] == 781, (
        f"Historical case: expected 781 (post-P5 canonical), "
        f"got {data['buyer_stripe_cents']}"
    )
    assert data["buyer_total_charged"] == 7.81
    # explicitly refuse pre-P5 and phantom regressions
    assert data["buyer_stripe_cents"] != 728  # pre-P5 stale
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
