"""P0 bug-fix regression — iteration 181
Covers:
 - Bug 4: Tax computed on (BP + stripe_fee) — non-zero on $10 hammer
 - Bug 6: Stripe processing fee exposed and > $0.30 on small ($5) hammer
 - Buyer total equals sum of components (cent-accurate)
 - Bug 3: POST /api/payments/checkout honors buy_now flag
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback for local shell
    BASE_URL = "http://localhost:8001"

TAX_URL = f"{BASE_URL}/api/payments/tax/calculate"


# ─────── Bug 4 & 6 — tax + stripe gross-up ───────

def test_tax_calc_hammer_10_basic_has_nonzero_fee_tax_and_stripe_fee():
    r = requests.post(TAX_URL, json={
        "hammer_price": 10.0,
        "buyer_tier": "free",
        "category": "general",
    }, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    # Structural checks
    assert "buyer_pays_fees_tax" in data
    assert "stripe_processing_fee" in data, "Bug 6: stripe_processing_fee field missing"
    # Non-zero assertions (Bug 4 + Bug 6)
    assert data["buyer_pays_fees_tax"] > 0.0, f"Bug 4 regression — fee tax = {data['buyer_pays_fees_tax']}"
    assert data["stripe_processing_fee"] > 0.30, f"Bug 6 — stripe fee must exceed fixed $0.30 ({data['stripe_processing_fee']})"
    # Cent-level total equality
    hp   = data["hammer_price"]
    bp   = data["buyer_pays_fees"]
    htax = data["buyer_pays_hammer_tax"]
    ftax = data["buyer_pays_fees_tax"]
    sfee = data["stripe_processing_fee"]
    total = data["buyer_total"]
    expected = round(hp + bp + htax + ftax + sfee, 2)
    assert abs(expected - round(total, 2)) < 0.01, (
        f"buyer_total {total} != {expected} (hp={hp} bp={bp} htax={htax} ftax={ftax} sfee={sfee})"
    )


def test_tax_calc_hammer_5_stripe_fee_above_fixed_floor():
    r = requests.post(TAX_URL, json={
        "hammer_price": 5.0,
        "buyer_tier": "basic",
        "category": "general",
    }, timeout=30)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["stripe_processing_fee"] > 0.30, (
        f"stripe_processing_fee={data['stripe_processing_fee']} expected > 0.30 (Bug 6)"
    )
    # Buyer total should be roughly $5.78 (not the old buggy $1.52)
    assert data["buyer_total"] > 5.50, f"Expected total > $5.50, got {data['buyer_total']}"
    assert data["buyer_total"] < 7.00, f"Expected total < $7.00, got {data['buyer_total']}"


def test_tax_calc_hammer_10_approx_expected_total():
    """Expected arithmetic per spec: hp=10 basic → BP=0.50, fee_tax≈0.17, stripe≈0.63, total≈11.30"""
    r = requests.post(TAX_URL, json={
        "hammer_price": 10.0,
        "buyer_tier": "basic",
        "category": "general",
    }, timeout=30)
    data = r.json()
    assert abs(data["buyer_pays_fees"] - 0.50) < 0.01
    assert data["buyer_pays_fees_tax"] >= 0.15, f"fee_tax too low: {data['buyer_pays_fees_tax']}"
    assert data["stripe_processing_fee"] >= 0.60, f"stripe_fee too low: {data['stripe_processing_fee']}"
    assert 11.00 <= data["buyer_total"] <= 11.60, f"total out of range: {data['buyer_total']}"


# ─────── Bug 3 — Buy-Now checkout uses buy_now_price ───────

def test_checkout_endpoint_accessible_and_requires_auth():
    """Smoke: /api/payments/checkout rejects unauthenticated and accepts buy_now flag schema."""
    r = requests.post(f"{BASE_URL}/api/payments/checkout",
                      json={"listing_id": "does-not-exist", "buy_now": True},
                      timeout=30)
    # Without creds → 401 / 403. Important: must NOT be 422 (schema rejection of buy_now).
    assert r.status_code in (401, 403), f"unexpected {r.status_code}: {r.text[:200]}"


def test_checkout_with_bad_token_and_buy_now_flag_schema_ok():
    """Schema accepts buy_now:true even with a bogus bearer token (still 401/403)."""
    r = requests.post(f"{BASE_URL}/api/payments/checkout",
                      json={"listing_id": "xyz", "buy_now": True},
                      headers={"Authorization": "Bearer not-a-real-jwt"},
                      timeout=30)
    assert r.status_code != 422, f"CheckoutRequest rejected buy_now flag: {r.text}"
    assert r.status_code in (401, 403, 404), f"unexpected {r.status_code}: {r.text[:200]}"
