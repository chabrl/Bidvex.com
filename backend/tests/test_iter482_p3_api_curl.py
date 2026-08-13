"""iter482 P3 - API-level curl tests for /api/fees/v2/preview

Post-P5 canonical:
  * Stripe-card default → buyer_stripe_recovery > 0 (payer bears fee).
  * payment_processing.legal_gate_status == "CLEARED" and amount_cents > 0
    when a Stripe-processed method is in effect.
  * Offline methods (cash / e_transfer / cheque) → recovery_cents == 0 and
    reason_code == "offline_method"; L-1 gate implicitly satisfied because
    no Stripe processing occurs.

The $7.00 QC premium/premium canonical:
    hammer $7.00 + BP $0.25 + bp_tax $0.03 + stripe_recovery $0.53 = $7.81
    (via Stripe)  →  buyer_stripe_cents == 781.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

API = f"{BASE_URL}/api/fees/v2/preview"


def _get(**params):
    r = requests.get(API, params=params, timeout=20)
    assert r.status_code == 200, f"HTTP {r.status_code}: {r.text}"
    return r.json()


def _assert_pp_cleared_stripe(d):
    """Post-P5: Stripe-card default → L-1 CLEARED with recovery cents populated."""
    pp = d.get("payment_processing")
    assert pp is not None, f"payment_processing snapshot missing: {d}"
    assert pp.get("legal_gate_status") == "CLEARED", pp
    assert pp.get("amount_cents", 0) > 0, pp
    assert pp.get("recovery_cents", 0) > 0, pp
    assert pp.get("payment_method") == "stripe_card", pp
    assert pp.get("field_version") == "payment_processing.v2", pp


def _assert_pp_offline_gated(d):
    """Offline payment methods → recovery == 0, reason_code == offline_method."""
    pp = d.get("payment_processing")
    assert pp is not None, f"payment_processing snapshot missing: {d}"
    assert pp.get("amount_cents") == 0, pp
    assert pp.get("recovery_cents") == 0, pp
    assert pp.get("reason_code") == "offline_method", pp


def _assert_buyer_stripe_recovery_positive(d):
    assert d.get("buyer_stripe_recovery", 0) > 0, (
        f"buyer_stripe_recovery must be > 0 (post-P5 payer-bears-fee): "
        f"{d.get('buyer_stripe_recovery')}"
    )


def _assert_buyer_stripe_recovery_zero(d):
    assert d.get("buyer_stripe_recovery", 0) == 0.0, (
        f"buyer_stripe_recovery must be 0 for offline methods: "
        f"{d.get('buyer_stripe_recovery')}"
    )


# ---- Individual QC $100 basic/premium/vip_elite (Stripe default) ----
@pytest.mark.parametrize("tier", ["standard", "premium", "vip_elite"])
def test_individual_100_qc_tiers(tier):
    d = _get(hammer_price=100, auction_type="marketplace",
             seller_account_type="individual", seller_tier=tier,
             buyer_tier="standard", buyer_province="QC", seller_province="QC")
    _assert_buyer_stripe_recovery_positive(d)
    _assert_pp_cleared_stripe(d)


# ---- Historical $7.00 hammer premium tier (post-P5 canonical) ----
def test_historical_7dollar_hammer_premium_post_p5_781():
    """Post-P5 canonical: $7 hammer buyer/premium/seller/premium QC = $7.81
    (hammer $7.00 + BP $0.25 + bp_tax $0.03 + stripe_recovery $0.53).
    NEVER 7.28 (pre-P5 stale), NEVER 7.64 (phantom $0.31)."""
    d = _get(hammer_price=7, auction_type="marketplace",
             seller_account_type="individual", seller_tier="premium",
             buyer_tier="premium", buyer_province="QC", seller_province="QC")
    assert d["buyer_total_charged"] == 7.81, (
        f"REGRESSION: buyer_total_charged={d['buyer_total_charged']} "
        f"expected 7.81 (post-P5 canonical)"
    )
    assert d["buyer_stripe_cents"] == 781, d
    # Recovery must be present and non-zero
    _assert_buyer_stripe_recovery_positive(d)
    # Phantom / pre-P5 values must never reappear
    assert d["buyer_total_charged"] != 7.64  # phantom $0.31
    assert d["buyer_total_charged"] != 7.28  # pre-P5 stale


# ---- Partner $100 QC with 10% BP: E-10 neutrality (partner exempt) ----
@pytest.mark.parametrize("buyer_tier", ["standard", "premium", "vip_elite"])
def test_partner_100_qc_e10_neutrality(buyer_tier):
    d = _get(hammer_price=100, auction_type="marketplace",
             seller_account_type="partner", partner_bp_rate=0.10,
             buyer_tier=buyer_tier, buyer_province="QC", seller_province="QC")
    assert d["buyer_premium"] == 10.00, d
    assert d.get("bidvex_platform_fee_amount") == 3.00, d


# ---- Storage facility $100 QC: seller keeps 100% (Stripe default) ----
def test_storage_facility_100_qc():
    d = _get(hammer_price=100, auction_type="storage",
             seller_account_type="storage_facility",
             buyer_province="QC", seller_province="QC")
    assert d.get("seller_payout") == 100.00, d


# ---- Vehicle dealer $100 QC (Stripe default) ----
def test_vehicle_dealer_100_qc():
    d = _get(hammer_price=100, auction_type="vehicle",
             seller_account_type="vehicle_dealer",
             buyer_province="QC", seller_province="QC")
    _assert_pp_cleared_stripe(d)


# ---- Offline payment methods (buyer bears NO Stripe fee) ----
@pytest.mark.parametrize("pm", ["cash", "e_transfer", "cheque"])
def test_offline_payment_methods(pm):
    d = _get(hammer_price=100, auction_type="marketplace",
             seller_account_type="individual", seller_tier="standard",
             payment_method=pm, buyer_province="QC", seller_province="QC")
    _assert_buyer_stripe_recovery_zero(d)
    _assert_pp_offline_gated(d)


# ---- Quantity smoke: $7×1, $7×2, $7×10 (Stripe default) ----
@pytest.mark.parametrize("mult", [1, 2, 10])
def test_quantity_smoke_7_dollar(mult):
    d = _get(hammer_price=7 * mult, auction_type="marketplace",
             seller_account_type="individual", seller_tier="premium",
             buyer_province="QC", seller_province="QC")
    _assert_buyer_stripe_recovery_positive(d)
    _assert_pp_cleared_stripe(d)
