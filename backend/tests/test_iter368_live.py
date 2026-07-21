"""
iter368 — Live HTTP tests for multi-lot UX refinement + regression.

Coverage:
  1. GET /api/multi-item-listings/{id}/increment-info — dynamic tiered (8 rows) for seed
  2. GET /api/multi-item-listings/{id}/next-bid?current=X — suggestions derived from schedule
  3. GET /api/lots/{id}/recent-activity — iter367 endpoint preserved
  4. Iter367 regression: /api/dashboard/buyer (won>0), /api/escrow/seller/status (3 holds)
  5. Admin unsubscribe guard still returns 403
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
SEED_LISTING_ID = "179b62b9-fa28-4140-b36d-f5903b033f48"
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def admin_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text[:200]}")
    return r.json().get("access_token") or r.json().get("token")


# ----- 1. Dynamic Bid Increment Info (tiered → 8 rows) -----

def test_increment_info_returns_tiered_8_rows(api):
    r = api.get(f"{BASE_URL}/api/multi-item-listings/{SEED_LISTING_ID}/increment-info")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["increment_option"] == "tiered"
    assert data["fixed_increment"] is None
    assert isinstance(data["schedule"], list)
    assert len(data["schedule"]) == 8, f"expected 8 tiers, got {len(data['schedule'])}"


def test_increment_info_first_tier_shape(api):
    r = api.get(f"{BASE_URL}/api/multi-item-listings/{SEED_LISTING_ID}/increment-info")
    row0 = r.json()["schedule"][0]
    for key in ("min", "max", "step", "range_label", "increment_label"):
        assert key in row0, f"missing {key}"
    assert row0["min"] == 0.0
    assert row0["step"] == 5.0
    assert "$5" in row0["increment_label"]


def test_increment_info_top_tier_open_ended(api):
    r = api.get(f"{BASE_URL}/api/multi-item-listings/{SEED_LISTING_ID}/increment-info")
    last = r.json()["schedule"][-1]
    assert last["min"] == 100000.0
    assert last["max"] is None
    assert last["step"] == 1000.0


# ----- 2. next-bid endpoint -----

def test_next_bid_at_250_returns_10_step_suggestions(api):
    r = api.get(f"{BASE_URL}/api/multi-item-listings/{SEED_LISTING_ID}/next-bid",
                params={"current": 250})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["current"] == 250.0
    assert data["increment"] == 10.0
    assert data["suggestions"] == [260.0, 270.0, 280.0]
    assert data["increment_option"] == "tiered"


def test_next_bid_ladder_matches_utils_tiered(api):
    """iter368 RETEST — /next-bid now imports get_minimum_increment from
    utils.py (was shared.py). Verify the tiered ladder matches utils.py
    exactly at every tier boundary. Per utils.get_minimum_increment_tiered:
      $0-99.99   → +$5
      $100-499.99→ +$10
      $500-999.99→ +$25
      $1000-4999.99 → +$50
      $5000-9999.99 → +$100
      $10000-49999.99 → +$250
      $50000-99999.99 → +$500
      $100000+   → +$1000
    """
    expected = [
        (0, 5.0), (50, 5.0), (99.99, 5.0),
        (100, 10.0), (250, 10.0), (499.99, 10.0),
        (500, 25.0), (999.99, 25.0),
        (1000, 50.0), (4999.99, 50.0),
        (5000, 100.0), (9999.99, 100.0),
        (10000, 250.0), (49999.99, 250.0),
        (50000, 500.0), (99999.99, 500.0),
        (100000, 1000.0), (500000, 1000.0),
    ]
    for current, want_step in expected:
        r = api.get(f"{BASE_URL}/api/multi-item-listings/{SEED_LISTING_ID}/next-bid",
                    params={"current": current})
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["increment"] == want_step, (
            f"LADDER DRIFT — at current=${current} expected step=${want_step} but got ${data['increment']}"
        )


def test_next_bid_matches_increment_info_schedule(api):
    """iter368 — /next-bid and /increment-info must return IDENTICAL steps
    at every tier boundary. This is the SINGLE SOURCE OF TRUTH contract."""
    info = api.get(f"{BASE_URL}/api/multi-item-listings/{SEED_LISTING_ID}/increment-info").json()
    schedule = info["schedule"]
    assert len(schedule) == 8, f"expected 8 tiered rows, got {len(schedule)}"
    for row in schedule:
        probe = float(row["min"])
        r = api.get(f"{BASE_URL}/api/multi-item-listings/{SEED_LISTING_ID}/next-bid",
                    params={"current": probe})
        assert r.status_code == 200
        got_step = r.json()["increment"]
        assert got_step == row["step"], (
            f"LADDER DRIFT — at tier min=${probe}: increment-info says ${row['step']} but /next-bid says ${got_step}"
        )


def test_next_bid_at_1500_returns_50_step_suggestions(api):
    r = api.get(f"{BASE_URL}/api/multi-item-listings/{SEED_LISTING_ID}/next-bid",
                params={"current": 1500})
    assert r.status_code == 200
    data = r.json()
    assert data["increment"] == 50.0
    assert data["suggestions"][0] == 1550.0


# ----- 3. iter367 recent-activity endpoint preserved -----

def test_recent_activity_endpoint_preserved(api):
    r = api.get(f"{BASE_URL}/api/lots/{SEED_LISTING_ID}/recent-activity")
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, (list, dict))


# ----- 4. iter367 regression -----

def test_buyer_dashboard_won_positive(api, admin_token):
    r = api.get(f"{BASE_URL}/api/dashboard/buyer",
                headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    # accept either "won_items" or "won_auctions" field
    won = data.get("won_items") or data.get("won_auctions") or 0
    if isinstance(won, list):
        won = len(won)
    assert won and won > 0, f"expected won>0, got {won}"


def test_escrow_seller_status_returns_holds(api, admin_token):
    r = api.get(f"{BASE_URL}/api/escrow/seller/status",
                headers={"Authorization": f"Bearer {admin_token}"})
    assert r.status_code == 200, r.text
    data = r.json()
    if isinstance(data, list):
        holds = data
    else:
        holds = data.get("holds") or data.get("active_holds") or data.get("items") or []
    assert isinstance(holds, list)
    # iter367 report says exactly 3
    assert len(holds) >= 3, f"expected >=3 escrow holds, got {len(holds)}"


def test_admin_unsubscribe_guard_403(api, admin_token):
    # Generate a token for admin, then POST confirm — must return 403.
    r = api.get(f"{BASE_URL}/api/unsubscribe/generate-test-link",
                headers={"Authorization": f"Bearer {admin_token}"},
                params={"email": ADMIN_EMAIL})
    if r.status_code != 200:
        pytest.skip(f"generate-test-link returned {r.status_code}")
    import re as _re
    payload = r.json()
    url = payload.get("url_en") or payload.get("url") or ""
    m = _re.search(r"[?&]token=([^&]+)", url)
    if not m:
        pytest.skip(f"no token in url: {payload}")
    token = m.group(1)
    r2 = api.post(f"{BASE_URL}/api/unsubscribe/confirm", json={"token": token})
    assert r2.status_code == 403, f"expected 403 admin guard, got {r2.status_code} {r2.text[:200]}"
    assert "admin_unsubscribe_blocked" in r2.text.lower() or "admin" in r2.text.lower()


# ----- 5. Multi-item listing detail still loads -----

def test_multi_item_listing_detail_loads(api):
    r = api.get(f"{BASE_URL}/api/multi-item-listings/{SEED_LISTING_ID}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data.get("id") == SEED_LISTING_ID or data.get("_id") == SEED_LISTING_ID or "title" in data
    lots = data.get("lots") or []
    assert len(lots) >= 20, f"expected >=20 lots, got {len(lots)}"
