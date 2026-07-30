"""iter432 — Sales & Performance analytics backend tests.

Covers GET /api/vehicles/my/analytics:
  - 30/60/90 windows return correct shape
  - Invalid window clamps to 30
  - Auth guard (401/403 without token)
  - Non-seller guard (403 without vehicle_sellers row)
  - Totals math (conversion_rate = round(bids/views, 4))
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
DEALER_EMAIL = "testdealer@bidvex.com"
DEALER_PASSWORD = "TestDealer2026!"
BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PASSWORD = "TestBuyer2026!"


@pytest.fixture(scope="module")
def dealer_headers():
    r = None
    for _ in range(3):
        try:
            r = requests.post(f"{BASE_URL}/api/auth/login",
                              json={"email": DEALER_EMAIL, "password": DEALER_PASSWORD}, timeout=60)
            break
        except requests.exceptions.RequestException:
            continue
    assert r is not None and r.status_code == 200, f"dealer login failed: {getattr(r,'status_code',None)} {getattr(r,'text','')}"
    tok = r.json()["access_token"]
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def buyer_headers():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": BUYER_EMAIL, "password": BUYER_PASSWORD}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"buyer login failed: {r.status_code}")
    tok = r.json()["access_token"]
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _shape_assertions(data, expected_window):
    assert data["window_days"] == expected_window
    assert "start_date" in data and "end_date" in data
    assert "totals" in data
    t = data["totals"]
    for k in ("views", "bids", "revenue", "sold_count", "conversion_rate"):
        assert k in t, f"missing totals.{k}"
    assert "daily_series" in data and isinstance(data["daily_series"], list)
    assert "granularity" in data
    assert "has_data" in data


# ---- 30 day window: daily granularity, testdealer seed values ----
def test_analytics_30d(dealer_headers):
    r = requests.get(f"{BASE_URL}/api/vehicles/my/analytics?window_days=30",
                     headers=dealer_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    _shape_assertions(data, 30)
    assert data["granularity"] == "day"
    assert len(data["daily_series"]) == 30
    # Seed data assertions (per review request)
    t = data["totals"]
    print(f"[30d] totals={t}")
    assert t["bids"] == 11, f"expected 11 bids, got {t['bids']}"
    # Revenue from sold listing (~10 days ago, $22500)
    assert t["revenue"] == 22500 or t["revenue"] == 22500.0, f"expected 22500 revenue, got {t['revenue']}"
    assert t["sold_count"] == 1
    # conversion_rate = round(bids/views, 4) when views > 0
    if t["views"] > 0:
        expected_cr = round(t["bids"] / t["views"], 4)
        assert t["conversion_rate"] == expected_cr, f"cr math mismatch: {t['conversion_rate']} vs {expected_cr}"
    else:
        assert t["conversion_rate"] == 0.0
    assert data["has_data"] is True


# ---- 60 day window: weekly granularity ----
def test_analytics_60d(dealer_headers):
    r = requests.get(f"{BASE_URL}/api/vehicles/my/analytics?window_days=60",
                     headers=dealer_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    _shape_assertions(data, 60)
    assert data["granularity"] == "week"
    # num_weeks = window_days // 7 = 8
    assert len(data["daily_series"]) == 60 // 7, f"expected 8 weekly buckets, got {len(data['daily_series'])}"
    # Each row has bids+sold ints
    for row in data["daily_series"]:
        assert "date" in row and "bids" in row and "sold" in row


# ---- 90 day window: weekly granularity ----
def test_analytics_90d(dealer_headers):
    r = requests.get(f"{BASE_URL}/api/vehicles/my/analytics?window_days=90",
                     headers=dealer_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    _shape_assertions(data, 90)
    assert data["granularity"] == "week"
    assert len(data["daily_series"]) == 90 // 7  # 12


# ---- Invalid window clamps to 30 ----
def test_analytics_invalid_window_clamps(dealer_headers):
    r = requests.get(f"{BASE_URL}/api/vehicles/my/analytics?window_days=42",
                     headers=dealer_headers, timeout=20)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["window_days"] == 30, f"expected clamp to 30, got {data['window_days']}"
    assert data["granularity"] == "day"


# ---- Requires auth ----
def test_analytics_requires_auth():
    r = requests.get(f"{BASE_URL}/api/vehicles/my/analytics?window_days=30", timeout=20)
    assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"


# ---- Non-seller (buyer) gets 403 ----
def test_analytics_forbidden_for_non_seller(buyer_headers):
    r = requests.get(f"{BASE_URL}/api/vehicles/my/analytics?window_days=30",
                     headers=buyer_headers, timeout=20)
    assert r.status_code == 403, f"expected 403 for non-seller, got {r.status_code} {r.text}"
