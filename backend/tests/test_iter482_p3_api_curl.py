"""iter482 P3 - API-level curl tests for /api/fees/v2/preview
Verifies buyer_stripe_recovery=0.0 and payment_processing.legal gate.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Read from frontend .env if not exported
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


def _assert_pp_legally_gated(d):
    pp = d.get("payment_processing")
    assert pp is not None, f"payment_processing snapshot missing: {d}"
    assert pp.get("amount_cents") == 0, f"amount_cents!=0: {pp}"
    assert pp.get("legal_gate_status") == "REQUIRES_TAX_LEGAL_REVIEW", pp
    assert pp.get("reason_code") == "legally_gated", pp
    assert pp.get("field_version") == "payment_processing.v1", pp


def _assert_buyer_stripe_zero(d):
    assert d.get("buyer_stripe_recovery") == 0.0, (
        f"buyer_stripe_recovery not 0: {d.get('buyer_stripe_recovery')}"
    )


# ---- Individual QC $100 basic/premium/vip_elite ----
@pytest.mark.parametrize("tier", ["standard", "premium", "vip_elite"])
def test_individual_100_qc_tiers(tier):
    d = _get(hammer_price=100, auction_type="marketplace",
             seller_account_type="individual", seller_tier=tier,
             buyer_tier="standard", buyer_province="QC", seller_province="QC")
    _assert_buyer_stripe_zero(d)
    _assert_pp_legally_gated(d)


# ---- Historical $7.00 hammer premium tier: must be 7.29 NOT 7.64 ----
def test_historical_7dollar_hammer_premium_no_phantom_031():
    d = _get(hammer_price=7, auction_type="marketplace",
             seller_account_type="individual", seller_tier="premium",
             buyer_tier="premium", buyer_province="QC", seller_province="QC")
    assert d["buyer_total_charged"] == 7.29, (
        f"REGRESSION: buyer_total_charged={d['buyer_total_charged']} "
        f"expected 7.29 (must NEVER be 7.64)"
    )
    assert d["buyer_total_charged"] != 7.64
    _assert_buyer_stripe_zero(d)


# ---- Partner $100 QC with 10% BP: E-10 neutrality ----
@pytest.mark.parametrize("buyer_tier", ["standard", "premium", "vip_elite"])
def test_partner_100_qc_e10_neutrality(buyer_tier):
    d = _get(hammer_price=100, auction_type="marketplace",
             seller_account_type="partner", partner_bp_rate=0.10,
             buyer_tier=buyer_tier, buyer_province="QC", seller_province="QC")
    assert d["buyer_total_charged"] == 110.00, d
    assert d["buyer_premium"] == 10.00, d
    assert d.get("bidvex_platform_fee_amount") == 3.00, d
    _assert_buyer_stripe_zero(d)


# ---- Storage facility $100 QC: seller keeps 100% ----
def test_storage_facility_100_qc():
    d = _get(hammer_price=100, auction_type="storage",
             seller_account_type="storage_facility",
             buyer_province="QC", seller_province="QC")
    assert d.get("seller_payout") == 100.00, d
    _assert_buyer_stripe_zero(d)


# ---- Vehicle dealer $100 QC ----
def test_vehicle_dealer_100_qc():
    d = _get(hammer_price=100, auction_type="vehicle",
             seller_account_type="vehicle_dealer",
             buyer_province="QC", seller_province="QC")
    _assert_buyer_stripe_zero(d)


# ---- Offline payment methods ----
@pytest.mark.parametrize("pm", ["cash", "e_transfer", "cheque"])
def test_offline_payment_methods(pm):
    d = _get(hammer_price=100, auction_type="marketplace",
             seller_account_type="individual", seller_tier="standard",
             payment_method=pm, buyer_province="QC", seller_province="QC")
    _assert_buyer_stripe_zero(d)


# ---- Quantity smoke: $7×1, $7×2, $7×10 ----
@pytest.mark.parametrize("mult", [1, 2, 10])
def test_quantity_smoke_7_dollar(mult):
    d = _get(hammer_price=7 * mult, auction_type="marketplace",
             seller_account_type="individual", seller_tier="premium",
             buyer_province="QC", seller_province="QC")
    _assert_buyer_stripe_zero(d)
    _assert_pp_legally_gated(d)
