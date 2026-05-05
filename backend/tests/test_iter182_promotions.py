"""
Iteration 182 — Listing Promotion / Boost Payment System P0 tests
Covers:
- POST /api/payments/promote-listing (basic / standard / premium)
- Validation errors (invalid tier, invalid type)
- Authorization (non-owner can't promote)
- Cross-collection mismatch (storage type but marketplace listing)
- Admin /admin/promotions/* endpoints
- Promoted-first sort on listings + storage_auctions
"""
import os
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
SAMPLE_LISTING_ID = "41d4ba34-039a-42c3-8573-55b4634ba1fd"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        return None
    data = r.json()
    return data.get("access_token") or data.get("token")


_ADMIN_TOKEN = None
def _admin_headers():
    global _ADMIN_TOKEN
    if not _ADMIN_TOKEN:
        # retry up to 3x to clear rate-limit
        import time
        for i in range(3):
            tok = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
            if tok:
                _ADMIN_TOKEN = tok
                break
            time.sleep(2 + i * 2)
    assert _ADMIN_TOKEN, "Admin login failed - cannot proceed"
    return {"Authorization": f"Bearer {_ADMIN_TOKEN}", "Content-Type": "application/json"}


# ---- Promote endpoint: tier pricing ----
def test_promote_basic_returns_checkout_and_breakdown():
    h = _admin_headers()
    payload = {"listing_id": SAMPLE_LISTING_ID, "boost_tier": "basic", "listing_type": "marketplace"}
    r = requests.post(f"{BASE_URL}/api/payments/promote-listing", headers=h, json=payload, timeout=30)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:500]}"
    j = r.json()
    assert "checkout_url" in j, f"missing checkout_url: {j}"
    assert j.get("base_price") == 9.99
    assert abs(j.get("gst", 0) - 0.50) < 0.05
    assert abs(j.get("qst", 0) - 1.00) < 0.05
    assert j.get("stripe_fee", 0) > 0.5
    assert 11.5 < j.get("grand_total", 0) < 12.5, f"grand_total out of range: {j.get('grand_total')}"


def test_promote_standard_grand_total():
    h = _admin_headers()
    payload = {"listing_id": SAMPLE_LISTING_ID, "boost_tier": "standard", "listing_type": "marketplace"}
    r = requests.post(f"{BASE_URL}/api/payments/promote-listing", headers=h, json=payload, timeout=30)
    assert r.status_code == 200, r.text[:500]
    j = r.json()
    assert j.get("base_price") == 24.99
    assert 29.0 < j.get("grand_total", 0) < 30.5, f"grand_total {j.get('grand_total')}"


def test_promote_premium_grand_total():
    h = _admin_headers()
    payload = {"listing_id": SAMPLE_LISTING_ID, "boost_tier": "premium", "listing_type": "marketplace"}
    r = requests.post(f"{BASE_URL}/api/payments/promote-listing", headers=h, json=payload, timeout=30)
    assert r.status_code == 200, r.text[:500]
    j = r.json()
    assert j.get("base_price") == 49.99
    assert 58.5 < j.get("grand_total", 0) < 60.5, f"grand_total {j.get('grand_total')}"


# ---- Validation ----
def test_promote_invalid_tier_returns_400():
    h = _admin_headers()
    payload = {"listing_id": SAMPLE_LISTING_ID, "boost_tier": "invalid", "listing_type": "marketplace"}
    r = requests.post(f"{BASE_URL}/api/payments/promote-listing", headers=h, json=payload, timeout=30)
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text[:300]}"
    assert "boost_tier" in r.text.lower() or "invalid" in r.text.lower()


def test_promote_invalid_listing_type_returns_400():
    h = _admin_headers()
    payload = {"listing_id": SAMPLE_LISTING_ID, "boost_tier": "basic", "listing_type": "invalid"}
    r = requests.post(f"{BASE_URL}/api/payments/promote-listing", headers=h, json=payload, timeout=30)
    assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text[:300]}"
    assert "listing_type" in r.text.lower() or "invalid" in r.text.lower()


def test_promote_storage_type_marketplace_id_returns_404():
    h = _admin_headers()
    payload = {"listing_id": SAMPLE_LISTING_ID, "boost_tier": "basic", "listing_type": "storage"}
    r = requests.post(f"{BASE_URL}/api/payments/promote-listing", headers=h, json=payload, timeout=30)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text[:300]}"


def test_promote_non_owner_returns_403():
    # buyer (abc@gmail.com) tries to promote admin's listing
    tok = _login("p0bugtest@example.com", "TestBuyer123!")
    if not tok:
        import pytest
        pytest.skip("Buyer login failed - skipping ownership test")
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}
    payload = {"listing_id": SAMPLE_LISTING_ID, "boost_tier": "basic", "listing_type": "marketplace"}
    r = requests.post(f"{BASE_URL}/api/payments/promote-listing", headers=h, json=payload, timeout=30)
    assert r.status_code == 403, f"Expected 403, got {r.status_code}: {r.text[:300]}"


# ---- Admin promotions endpoints ----
def test_admin_promotions_active_list():
    h = _admin_headers()
    r = requests.get(f"{BASE_URL}/api/admin/promotions?status=active", headers=h, timeout=20)
    assert r.status_code == 200, r.text[:300]
    assert isinstance(r.json(), list)


def test_admin_social_share_queue():
    h = _admin_headers()
    r = requests.get(f"{BASE_URL}/api/admin/promotions/social-share-queue", headers=h, timeout=20)
    assert r.status_code == 200, r.text[:300]
    assert isinstance(r.json(), list)


def test_admin_promotions_revenue_summary():
    h = _admin_headers()
    r = requests.get(f"{BASE_URL}/api/admin/promotions/revenue", headers=h, timeout=20)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    for k in ("total_all_time", "total_month_to_date", "by_tier", "by_type", "count"):
        assert k in j, f"missing key {k} in revenue payload: {j}"
    assert all(t in j["by_tier"] for t in ("basic", "standard", "premium"))
    assert all(t in j["by_type"] for t in ("marketplace", "lots", "storage", "partner"))


# ---- Promoted-first sort ----
def test_listings_promoted_first():
    r = requests.get(f"{BASE_URL}/api/listings?status=active", timeout=20)
    assert r.status_code == 200, r.text[:300]
    items = r.json() if isinstance(r.json(), list) else r.json().get("listings", [])
    if not items:
        import pytest
        pytest.skip("No active listings to verify sort")
    # All promoted (is_promoted truthy) should come before any non-promoted
    seen_non_promoted = False
    for it in items:
        promoted = bool(it.get("is_promoted"))
        if not promoted:
            seen_non_promoted = True
        else:
            assert not seen_non_promoted, "Found promoted listing after non-promoted; sort broken"


def test_storage_auctions_promoted_first():
    r = requests.get(f"{BASE_URL}/api/storage-auctions", timeout=20)
    if r.status_code == 404:
        # try alt path
        r = requests.get(f"{BASE_URL}/api/storage/auctions", timeout=20)
    if r.status_code != 200:
        import pytest
        pytest.skip(f"storage auctions endpoint not reachable: {r.status_code}")
    j = r.json()
    items = j if isinstance(j, list) else j.get("auctions", j.get("items", []))
    if not items:
        import pytest
        pytest.skip("No storage auctions to verify sort")
    seen_non_promoted = False
    for it in items:
        if not bool(it.get("is_promoted")):
            seen_non_promoted = True
        else:
            assert not seen_non_promoted, "Storage auction sort broken"
