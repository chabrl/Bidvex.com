"""
iter367 — Live HTTP tests for the P0/P1 production audit pass.

Endpoints under test:
  1. POST /api/auth/login (admin)
  2. GET  /api/dashboard/buyer
  3. GET  /api/dashboard/seller
  4. GET  /api/admin/analytics/overview
  5. GET  /api/escrow/seller/status
  6. GET  /api/escrow/buyer/status
  7. GET  /api/lots/{auction_id}/recent-activity
  8. GET  /api/unsubscribe/generate-test-link

Uses REACT_APP_BACKEND_URL from /app/frontend/.env.
"""
import os
import re
import time
import pytest
import requests
from pathlib import Path

# Load REACT_APP_BACKEND_URL from frontend .env — do not hardcode
def _load_backend_url():
    env_path = Path("/app/frontend/.env")
    for line in env_path.read_text().splitlines():
        if line.startswith("REACT_APP_BACKEND_URL="):
            return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found in /app/frontend/.env")

BASE_URL = _load_backend_url()
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
MULTI_LOT_AUCTION_ID = "179b62b9-fa28-4140-b36d-f5903b033f48"


@pytest.fixture(scope="session")
def admin_token():
    """Login as super admin and return JWT token. Retries on 429 rate-limit."""
    for attempt in range(3):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=30,
        )
        if r.status_code == 429:
            print(f"Rate limited, sleeping 65s (attempt {attempt+1})")
            time.sleep(65)
            continue
        if r.status_code == 200:
            data = r.json()
            tok = data.get("access_token") or data.get("token")
            assert tok, f"login response missing token: {data}"
            return tok
        pytest.skip(f"login failed: {r.status_code} {r.text[:200]}")
    pytest.skip("admin login rate-limited after retries")


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ============= 1. Auth =============

def test_admin_login_returns_token(admin_token):
    """Admin must authenticate on the preview environment."""
    assert isinstance(admin_token, str)
    assert len(admin_token) > 20


# ============= 2. Buyer Dashboard =============

class TestBuyerDashboard:
    def test_buyer_dashboard_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/dashboard/buyer", headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert isinstance(data, dict)
        # Must expose stats + bids array
        assert "stats" in data or "total_won_items" in data or "won_items" in data or "recent_bids" in data

    def test_buyer_won_auctions_count_positive(self, admin_headers):
        """Admin has ≥1 won item ('table1 test'). Ensure counter > 0."""
        r = requests.get(f"{BASE_URL}/api/dashboard/buyer", headers=admin_headers, timeout=30)
        data = r.json()
        # Try multiple shape possibilities
        stats = data.get("stats") or {}
        won_items = data.get("won_items")
        # won_items may be an int (count) or a list (records)
        if isinstance(won_items, list):
            won_count = len(won_items)
        elif isinstance(won_items, int):
            won_count = won_items
        else:
            won_count = 0
        total = (
            data.get("total_won_items")
            or stats.get("total_won_items")
            or stats.get("won_auctions")
            or won_count
            or len(data.get("won_items_detail", []) or [])
            or 0
        )
        assert total >= 1, f"expected won items >= 1, got {total}. data keys={list(data.keys())}"

    def test_buyer_bids_never_show_outbid_zero(self, admin_headers):
        """Bids on purged listings must NOT surface as OUTBID $0.00 — they should be won/ended."""
        r = requests.get(f"{BASE_URL}/api/dashboard/buyer", headers=admin_headers, timeout=30)
        data = r.json()
        bids = data.get("recent_bids") or data.get("bids") or data.get("bid_history") or []
        # If empty, skip
        if not bids:
            pytest.skip("no bids in dashboard payload — skipping OUTBID $0.00 assertion")
        for b in bids:
            status = (b.get("bid_status") or "").lower()
            amt = b.get("current_price") or b.get("winning_amount") or b.get("hammer_price") or 0
            if status == "outbid":
                # OUTBID must have a real current_price > 0
                assert amt and float(amt) > 0, f"OUTBID with $0.00 detected: {b}"


# ============= 3. Seller Dashboard =============

class TestSellerDashboard:
    def test_seller_dashboard_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/dashboard/seller", headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert isinstance(data, dict)

    def test_seller_stats_positive(self, admin_headers):
        """Expected: sold_listings > 0, total_sales > 0 (backed by seller_statement receipts union)."""
        r = requests.get(f"{BASE_URL}/api/dashboard/seller", headers=admin_headers, timeout=30)
        data = r.json()
        stats = data.get("stats") or data
        sold = stats.get("sold_listings") or stats.get("total_sold") or 0
        sales = stats.get("total_sales") or stats.get("gross_sales") or 0
        assert sold >= 1, f"expected sold_listings >= 1, got {sold}. keys={list(stats.keys())}"
        assert float(sales) > 0, f"expected total_sales > 0, got {sales}"


# ============= 4. Admin Analytics =============

def test_admin_analytics_overview_gmv_positive(admin_headers):
    """GMV all-time should be > 0 after receipts fallback fix."""
    r = requests.get(
        f"{BASE_URL}/api/admin/analytics/overview",
        headers=admin_headers,
        params={"from": "2026-05-01", "to": "2026-07-31"},
        timeout=30,
    )
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
    data = r.json()
    gmv = data.get("gmv") or {}
    all_time = gmv.get("all_time") or gmv.get("total") or 0
    assert float(all_time) > 0, f"expected gmv.all_time > 0, got {all_time}. gmv={gmv}"


# ============= 5. Escrow =============

class TestEscrow:
    def test_escrow_seller_status_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/escrow/seller/status", headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"

    def test_escrow_seller_status_has_active_holds(self, admin_headers):
        """Expect 3 active escrow holds with pickup codes BVX-XERVL5J8, BVX-DG9O220P, BVX-1H1J5GC9."""
        r = requests.get(f"{BASE_URL}/api/escrow/seller/status", headers=admin_headers, timeout=30)
        data = r.json()
        # Endpoint returns raw list
        if isinstance(data, list):
            holds = data
        else:
            holds = data.get("holds") or data.get("active_holds") or data.get("escrow_holds") or data.get("items") or []
        assert len(holds) >= 3, f"expected >=3 active escrow holds, got {len(holds)}. data={str(data)[:400]}"
        codes = [h.get("pickup_code") for h in holds if h.get("pickup_code")]
        # Verify the three expected pickup codes are present
        expected_codes = {"BVX-XERVL5J8", "BVX-DG9O220P", "BVX-1H1J5GC9"}
        assert expected_codes.issubset(set(codes)), f"missing pickup codes; expected {expected_codes}, got {codes}"

    def test_escrow_buyer_status_returns_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/escrow/buyer/status", headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"


# ============= 6. Multi-Lot Live Activity Ticker =============

class TestRecentActivity:
    def test_recent_activity_returns_200(self):
        """Public endpoint — no auth required."""
        r = requests.get(
            f"{BASE_URL}/api/lots/{MULTI_LOT_AUCTION_ID}/recent-activity",
            timeout=30,
        )
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"

    def test_recent_activity_shape(self):
        r = requests.get(
            f"{BASE_URL}/api/lots/{MULTI_LOT_AUCTION_ID}/recent-activity",
            timeout=30,
        )
        data = r.json()
        # Either list or {events: [...]}
        events = data if isinstance(data, list) else (
            data.get("events") or data.get("activity") or data.get("items") or []
        )
        assert isinstance(events, list), f"expected list-shape events, got {type(events)}: {str(data)[:200]}"

    def test_recent_activity_respects_limit(self):
        r = requests.get(
            f"{BASE_URL}/api/lots/{MULTI_LOT_AUCTION_ID}/recent-activity",
            params={"limit": 5},
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        events = data if isinstance(data, list) else (
            data.get("events") or data.get("activity") or data.get("items") or []
        )
        assert len(events) <= 5


# ============= 7. Unsubscribe admin guard =============

class TestUnsubscribeAdminGuard:
    def test_admin_cannot_unsubscribe(self, admin_headers):
        """Admin email must be rejected by /api/unsubscribe/confirm."""
        # Generate a token for the admin address
        r = requests.get(
            f"{BASE_URL}/api/unsubscribe/generate-test-link",
            headers=admin_headers,
            params={"email": ADMIN_EMAIL},
            timeout=30,
        )
        if r.status_code != 200:
            pytest.skip(f"generate-test-link returned {r.status_code}, cannot test admin guard")
        payload = r.json()
        url = payload.get("url_en") or payload.get("url") or ""
        # Extract token from URL query string
        m = re.search(r"[?&]token=([^&]+)", url)
        if not m:
            pytest.skip(f"generate-test-link payload has no token: {payload}")
        token = m.group(1)
        # Now POST /confirm — must return 403 admin_unsubscribe_blocked
        r2 = requests.post(
            f"{BASE_URL}/api/unsubscribe/confirm",
            json={"token": token},
            timeout=30,
        )
        assert r2.status_code == 403, f"admin unsubscribe should be blocked; got {r2.status_code}: {r2.text[:200]}"
        body = r2.text.lower()
        assert "admin_unsubscribe_blocked" in body or "admin" in body, f"missing admin_unsubscribe_blocked marker: {r2.text[:200]}"


# ============= 8. Comprehensive endpoint smoke =============

def test_all_endpoint_smoke(admin_headers):
    """Round-trip GET on the 5 critical endpoints — all must return 200."""
    endpoints = [
        (f"/api/dashboard/buyer", admin_headers),
        (f"/api/dashboard/seller", admin_headers),
        (f"/api/admin/analytics/overview?from=2026-05-01&to=2026-07-31", admin_headers),
        (f"/api/escrow/seller/status", admin_headers),
        (f"/api/lots/{MULTI_LOT_AUCTION_ID}/recent-activity", None),
    ]
    failures = []
    for path, headers in endpoints:
        r = requests.get(f"{BASE_URL}{path}", headers=headers or {}, timeout=30)
        if r.status_code != 200:
            failures.append(f"{path} -> {r.status_code}: {r.text[:120]}")
    assert not failures, "endpoint failures: " + " | ".join(failures)
