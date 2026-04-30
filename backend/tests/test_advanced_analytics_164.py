"""
Iteration 164 — Advanced Analytics Aggregation (P1)
Covers: GET /api/admin/analytics/advanced
- Auth guards (no auth → 401/403, non-admin → 403)
- Response shape (top_sellers, top_categories, conversion)
- days query param validation (ge=1, le=730)
- Cache behavior (60s in-process, cache hit keeps generated_at)
- Seeded data correctness (5 sold demo-* listings, 5 paid demo-tx-*)
- Empty window behavior (no errors, zeros)
"""
import os
import time
import uuid
import pytest
import requests
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
# Fallback: load the frontend .env for REACT_APP_BACKEND_URL (per system guidelines, use this URL)
load_dotenv(Path(__file__).parent.parent.parent / "frontend" / ".env", override=False)

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


# ----------------------------- Fixtures -----------------------------

@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    d = r.json()
    tok = d.get("access_token") or d.get("token")
    assert tok, f"No token in response: {d}"
    return tok


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def regular_user_token():
    """Register a brand-new non-admin user and return token."""
    email = f"iter164_{uuid.uuid4().hex[:8]}@example.com"
    payload = {
        "email": email,
        "password": "TestPass123!",
        "name": "Iter164 Tester",
        "terms_agreed": True,
        "ai_disclosure_consent": True,
    }
    r = requests.post(f"{API}/auth/register", json=payload, timeout=30)
    if r.status_code not in (200, 201):
        pytest.skip(f"Could not register regular user: {r.status_code} {r.text}")
    d = r.json()
    tok = d.get("access_token") or d.get("token")
    if not tok:
        # Try login fallback
        lr = requests.post(f"{API}/auth/login", json={"email": email, "password": "TestPass123!"}, timeout=30)
        if lr.status_code == 200:
            tok = lr.json().get("access_token") or lr.json().get("token")
    if not tok:
        pytest.skip("Could not obtain token for non-admin user")
    return tok


# ----------------------------- Auth guards -----------------------------

class TestAuthGuards:
    def test_no_auth_401_or_403(self):
        r = requests.get(f"{API}/admin/analytics/advanced", timeout=20)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code} body={r.text[:200]}"

    def test_non_admin_403(self, regular_user_token):
        r = requests.get(
            f"{API}/admin/analytics/advanced",
            headers={"Authorization": f"Bearer {regular_user_token}"},
            timeout=20,
        )
        assert r.status_code == 403, f"Expected 403 for non-admin, got {r.status_code} body={r.text[:200]}"


# ----------------------------- Days validation -----------------------------

class TestDaysValidation:
    def test_days_zero_422(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/advanced?days=0", headers=admin_headers, timeout=20)
        assert r.status_code == 422, f"Expected 422 for days=0, got {r.status_code}"

    def test_days_negative_422(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/advanced?days=-1", headers=admin_headers, timeout=20)
        assert r.status_code == 422, f"Expected 422 for days=-1, got {r.status_code}"

    def test_days_too_large_422(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/advanced?days=731", headers=admin_headers, timeout=20)
        assert r.status_code == 422, f"Expected 422 for days=731, got {r.status_code}"

    def test_days_boundary_730_ok(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/advanced?days=730", headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"Expected 200 for days=730, got {r.status_code}"


# ----------------------------- Shape -----------------------------

class TestResponseShape:
    def test_admin_200_and_top_keys(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/advanced?days=30", headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"status={r.status_code} body={r.text[:200]}"
        d = r.json()
        for key in ("period_days", "generated_at", "top_sellers", "top_categories", "conversion"):
            assert key in d, f"Missing key: {key}"
        assert d["period_days"] == 30
        assert isinstance(d["top_sellers"], list)
        assert isinstance(d["top_categories"], list)
        assert isinstance(d["conversion"], dict)

    def test_top_sellers_shape(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/advanced?days=30", headers=admin_headers, timeout=30)
        d = r.json()
        top_sellers = d["top_sellers"]
        assert len(top_sellers) <= 10, "top_sellers must be capped at 10"
        for s in top_sellers:
            for key in ("seller_id", "name", "email", "items_sold", "total_revenue", "avg_sale_price"):
                assert key in s, f"Missing seller field: {key}"
            assert isinstance(s["items_sold"], int)
            assert isinstance(s["total_revenue"], (int, float))
            assert isinstance(s["avg_sale_price"], (int, float))
        # Sorted desc by revenue
        revenues = [s["total_revenue"] for s in top_sellers]
        assert revenues == sorted(revenues, reverse=True), f"top_sellers not sorted desc: {revenues}"

    def test_top_categories_shape(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/advanced?days=30", headers=admin_headers, timeout=30)
        d = r.json()
        top_cats = d["top_categories"]
        assert len(top_cats) <= 10, "top_categories must be capped at 10"
        for c in top_cats:
            for key in ("category", "total_listings", "sold_count", "total_revenue", "sell_through_rate", "total_views"):
                assert key in c, f"Missing category field: {key}"
            assert isinstance(c["sell_through_rate"], (int, float))
            assert 0.0 <= c["sell_through_rate"] <= 1.0, f"sell_through_rate out of bounds: {c}"
            assert isinstance(c["total_listings"], int)
            assert isinstance(c["sold_count"], int)
        # Sorted desc by total_listings
        listings_counts = [c["total_listings"] for c in top_cats]
        assert listings_counts == sorted(listings_counts, reverse=True), f"top_categories not sorted desc: {listings_counts}"

    def test_conversion_shape(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/advanced?days=30", headers=admin_headers, timeout=30)
        d = r.json()
        conv = d["conversion"]
        for key in ("listing_to_sale", "visitor_to_bidder", "signup_to_action"):
            assert key in conv, f"Missing conversion key: {key}"
            block = conv[key]
            assert "rate" in block
            assert isinstance(block["rate"], (int, float))
            assert 0.0 <= block["rate"] <= 1.0, f"{key}.rate out of bounds: {block['rate']}"
        assert "total_listings" in conv["listing_to_sale"]
        assert "sold_listings" in conv["listing_to_sale"]
        assert "total_views" in conv["visitor_to_bidder"]
        assert "total_bids" in conv["visitor_to_bidder"]
        assert "new_users" in conv["signup_to_action"]
        assert "users_with_action" in conv["signup_to_action"]


# ----------------------------- Seeded data correctness -----------------------------

class TestSeededData:
    """
    Seeded: 10 demo-* listings (5 sold: $1280+$890+$320+$220+$410 ; 5 active)
    5 paid demo-tx-* payment_transactions.
    Expected (days=30):
      - Charbel Admin: 4 items, $2800 (1280+890+220+410)
      - Other seller: 1 item, $320
      - Listing→Sale = 5/10 = 0.5
      - Top category by listings = electronics (3 listings, 2 sold, rate≈0.6667)
    """

    def test_charbel_top_seller(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/advanced?days=30", headers=admin_headers, timeout=30)
        assert r.status_code == 200
        d = r.json()
        top = d["top_sellers"]
        assert len(top) >= 1, "Expected at least 1 seller from seeded data"
        # The top seller should be Charbel Admin with 4 items and $2800 revenue
        first = top[0]
        assert first["items_sold"] == 4, f"Expected 4 items sold for top seller, got {first['items_sold']}: {first}"
        assert abs(first["total_revenue"] - 2800.0) < 0.01, f"Expected $2800 revenue, got {first['total_revenue']}: {first}"
        assert abs(first["avg_sale_price"] - 700.0) < 0.01, f"Expected avg $700, got {first['avg_sale_price']}"

    def test_second_seller_320(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/advanced?days=30", headers=admin_headers, timeout=30)
        d = r.json()
        top = d["top_sellers"]
        if len(top) < 2:
            pytest.skip("Only 1 seller available")
        second = top[1]
        assert second["items_sold"] == 1, f"Expected 1 item for 2nd seller, got {second['items_sold']}"
        assert abs(second["total_revenue"] - 320.0) < 0.01, f"Expected $320 revenue for 2nd seller, got {second['total_revenue']}"

    def test_listing_to_sale_rate(self, admin_headers):
        """With 10 demo listings (5 sold), plus any real listings created in 30d window, rate should be >0."""
        r = requests.get(f"{API}/admin/analytics/advanced?days=30", headers=admin_headers, timeout=30)
        d = r.json()
        lts = d["conversion"]["listing_to_sale"]
        # Exact check: if only demo data, rate=0.5. With extra non-sold listings, rate decreases.
        # We at minimum expect 5 sold listings from seeded data.
        assert lts["sold_listings"] >= 5, f"Expected >=5 sold listings, got {lts['sold_listings']}"
        assert lts["total_listings"] >= 10, f"Expected >=10 total listings, got {lts['total_listings']}"
        assert 0.0 < lts["rate"] <= 1.0

    def test_electronics_top_category(self, admin_headers):
        r = requests.get(f"{API}/admin/analytics/advanced?days=30", headers=admin_headers, timeout=30)
        d = r.json()
        cats = d["top_categories"]
        cat_names = [c["category"] for c in cats]
        assert "electronics" in cat_names, f"Expected 'electronics' in categories, got {cat_names}"
        electronics = next(c for c in cats if c["category"] == "electronics")
        # Seeded: electronics has 3 listings (2 sold)
        assert electronics["total_listings"] >= 3
        assert electronics["sold_count"] >= 2


# ----------------------------- Days param honored -----------------------------

class TestDaysHonored:
    def test_period_days_reflects(self, admin_headers):
        for dd in (7, 30, 90):
            r = requests.get(f"{API}/admin/analytics/advanced?days={dd}", headers=admin_headers, timeout=30)
            assert r.status_code == 200, f"days={dd} failed: {r.status_code}"
            assert r.json()["period_days"] == dd

    def test_different_windows_produce_cache_keys(self, admin_headers):
        """days=7 and days=90 can legitimately have different totals or same if all data is recent."""
        r7 = requests.get(f"{API}/admin/analytics/advanced?days=7", headers=admin_headers, timeout=30).json()
        r90 = requests.get(f"{API}/admin/analytics/advanced?days=90", headers=admin_headers, timeout=30).json()
        # At minimum listings count in 7d should be <= 90d
        t7 = r7["conversion"]["listing_to_sale"]["total_listings"]
        t90 = r90["conversion"]["listing_to_sale"]["total_listings"]
        assert t7 <= t90, f"7d listings ({t7}) should be <= 90d listings ({t90})"


# ----------------------------- Cache behavior -----------------------------

class TestCacheBehavior:
    def test_cache_hit_same_generated_at(self, admin_headers):
        """Two consecutive calls within 60s should return the same generated_at (cache hit).
        Use days=45 to avoid colliding with other tests that may warm days=30."""
        r1 = requests.get(f"{API}/admin/analytics/advanced?days=45", headers=admin_headers, timeout=30)
        assert r1.status_code == 200
        g1 = r1.json()["generated_at"]
        time.sleep(1)
        r2 = requests.get(f"{API}/admin/analytics/advanced?days=45", headers=admin_headers, timeout=30)
        assert r2.status_code == 200
        g2 = r2.json()["generated_at"]
        assert g1 == g2, f"Cache hit expected same generated_at, got {g1} vs {g2}"

    def test_different_days_different_cache(self, admin_headers):
        """Different days param must be separate cache entries (different generated_at)."""
        # Use 2 fresh keys unlikely to be warm
        r_a = requests.get(f"{API}/admin/analytics/advanced?days=123", headers=admin_headers, timeout=30).json()
        r_b = requests.get(f"{API}/admin/analytics/advanced?days=456", headers=admin_headers, timeout=30).json()
        assert r_a["generated_at"] != r_b["generated_at"], \
            f"Different days should have different generated_at but got same: {r_a['generated_at']}"
        assert r_a["period_days"] == 123
        assert r_b["period_days"] == 456


# ----------------------------- Empty window -----------------------------

class TestEmptyWindow:
    def test_days_1_no_errors(self, admin_headers):
        """days=1 should not error; when empty, lists = [] and rates = 0.0."""
        r = requests.get(f"{API}/admin/analytics/advanced?days=1", headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"days=1 failed: {r.status_code} {r.text[:200]}"
        d = r.json()
        assert isinstance(d["top_sellers"], list)
        assert isinstance(d["top_categories"], list)
        conv = d["conversion"]
        # All rates must be in [0,1]
        for k in ("listing_to_sale", "visitor_to_bidder", "signup_to_action"):
            assert 0.0 <= conv[k]["rate"] <= 1.0
        # No divide-by-zero error: if no listings, rate should be 0.0
        if conv["listing_to_sale"]["total_listings"] == 0:
            assert conv["listing_to_sale"]["rate"] == 0.0
        if conv["visitor_to_bidder"]["total_views"] == 0:
            assert conv["visitor_to_bidder"]["rate"] == 0.0
        if conv["signup_to_action"]["new_users"] == 0:
            assert conv["signup_to_action"]["rate"] == 0.0
