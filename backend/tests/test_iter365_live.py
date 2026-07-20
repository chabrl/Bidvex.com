"""
iter365 — Live HTTP verification against preview host.
Covers:
  - GET /api/admin/pricing-engine (super_admin) returns 3 keys, all 180d
  - Broker row values: 500/50%/180d → 250 effective
  - GET /api/pricing-engine/public/broker_annual_fee — no Stripe internals leaked
"""
import os
import time
import pytest
import requests
from dotenv import load_dotenv

load_dotenv("/app/frontend/.env")
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")

SUPER_ADMIN_EMAIL = "charbel911@gmail.com"
SUPER_ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="module")
def super_admin_token():
    """Login once per module to avoid rate limit (5 fails → 429/60s)."""
    resp = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": SUPER_ADMIN_EMAIL, "password": SUPER_ADMIN_PASSWORD},
        timeout=30,
    )
    if resp.status_code == 429:
        pytest.skip("Rate limited — try again in 60s")
    assert resp.status_code == 200, f"Login failed: {resp.status_code} {resp.text}"
    data = resp.json()
    token = (
        data.get("access_token")
        or data.get("token")
        or (data.get("user") or {}).get("access_token")
    )
    assert token, f"No token in login response: {data}"
    return token


# ── Item 1 + Item 2 — Admin pricing-engine endpoint ─────────────────────
def test_admin_pricing_engine_returns_all_three_keys(super_admin_token):
    resp = requests.get(
        f"{BASE_URL}/api/admin/pricing-engine",
        headers={"Authorization": f"Bearer {super_admin_token}"},
        timeout=30,
    )
    assert resp.status_code == 200, f"{resp.status_code} {resp.text[:400]}"
    data = resp.json()

    # response can be either {"items":[…]} or a list; normalize
    rows = data.get("items") if isinstance(data, dict) and "items" in data else data
    if isinstance(rows, dict):
        # maybe keyed by key
        rows = list(rows.values())
    assert isinstance(rows, list), f"Unexpected shape: {type(rows)} {data}"

    by_key = {}
    for r in rows:
        k = r.get("key")
        if k:
            by_key[k] = r

    for key in ("partner_annual_fee", "vehicle_dealer_annual_fee", "broker_annual_fee"):
        assert key in by_key, f"missing key {key}. Got: {list(by_key.keys())}"
        assert by_key[key].get("launch_window_days") == 180, (
            f"{key} launch_window_days={by_key[key].get('launch_window_days')}"
        )


def test_admin_pricing_engine_broker_row_values(super_admin_token):
    resp = requests.get(
        f"{BASE_URL}/api/admin/pricing-engine",
        headers={"Authorization": f"Bearer {super_admin_token}"},
        timeout=30,
    )
    assert resp.status_code == 200
    data = resp.json()
    rows = data.get("items") if isinstance(data, dict) and "items" in data else data
    if isinstance(rows, dict):
        rows = list(rows.values())

    broker = next((r for r in rows if r.get("key") == "broker_annual_fee"), None)
    assert broker, f"broker_annual_fee row missing. Rows: {rows}"
    assert float(broker.get("base_price_cad")) == 500.0, broker
    assert int(broker.get("launch_discount_percent")) == 50, broker
    assert int(broker.get("launch_window_days")) == 180, broker
    assert float(broker.get("effective_price_cad")) == 250.0, broker


# ── Item 1 — Public broker pricing endpoint ─────────────────────────────
def test_public_broker_annual_fee_endpoint():
    resp = requests.get(
        f"{BASE_URL}/api/pricing-engine/public/broker_annual_fee",
        timeout=30,
    )
    assert resp.status_code == 200, f"{resp.status_code} {resp.text[:400]}"
    data = resp.json()

    assert float(data.get("effective_price_cad")) == 250.0, data
    assert float(data.get("base_price_cad")) == 500.0, data
    # is_within_launch_window should be true (row seeded now)
    assert data.get("is_within_launch_window") is True, data

    # Stripe internals MUST NOT be leaked publicly
    forbidden = {
        "stripe_price_id",
        "stripe_coupon_id",
        "stripe_product_id",
        "stripe_promotion_code_id",
    }
    leaked = forbidden & set(data.keys())
    assert not leaked, f"Stripe internals leaked in public response: {leaked}"


def test_public_pricing_endpoints_for_all_three_keys():
    """Sanity: all 3 public endpoints respond 200 with 180d launch window."""
    for key in ("partner_annual_fee", "vehicle_dealer_annual_fee", "broker_annual_fee"):
        resp = requests.get(f"{BASE_URL}/api/pricing-engine/public/{key}", timeout=30)
        assert resp.status_code == 200, f"{key}: {resp.status_code} {resp.text[:200]}"
        d = resp.json()
        assert int(d.get("launch_window_days")) == 180, f"{key} → {d}"
