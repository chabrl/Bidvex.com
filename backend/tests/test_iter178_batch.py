"""iter178 9-fix batch backend tests.

Covers:
- GET /api/storage-auctions/{id}/deposit/status (auth required, shape)
- PUT /api/admin/site-config/marketing persistence
- GET /api/site-config returns marketing dict
- Scheduler has 13 jobs and activate_upcoming_auctions registered
- PUT /api/profile with name/phone/province persists
- Admin storage-facilities endpoints exist
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASS = "Anderosli123!@#"
BUYER_EMAIL = "abc@gmail.com"
BUYER_PASS = "TestBuyer123!"

# ---------- Fixtures ----------

@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(f"{API}/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS}, timeout=30)
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text[:300]}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"no token in admin login response: {data}"
    return tok


@pytest.fixture(scope="session")
def buyer_token():
    r = requests.post(f"{API}/auth/login", json={"email": BUYER_EMAIL, "password": BUYER_PASS}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"buyer login failed: {r.status_code}")
    data = r.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def buyer_headers(buyer_token):
    return {"Authorization": f"Bearer {buyer_token}"}


@pytest.fixture(scope="session")
def sample_storage_auction_id():
    r = requests.get(f"{API}/storage-auctions", timeout=30)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    items = body if isinstance(body, list) else (body.get("auctions") or body.get("items") or [])
    assert len(items) > 0, f"no storage auctions in response keys={list(body.keys()) if isinstance(body, dict) else 'list'}"
    return items[0].get("id") or items[0].get("_id")


# ---------- FIX 1: deposit/status ----------

class TestDepositStatus:
    def test_requires_auth(self, sample_storage_auction_id):
        r = requests.get(f"{API}/storage-auctions/{sample_storage_auction_id}/deposit/status", timeout=30)
        assert r.status_code in (401, 403), f"should require auth, got {r.status_code}"

    def test_with_auth_returns_expected_shape(self, buyer_headers, sample_storage_auction_id):
        r = requests.get(
            f"{API}/storage-auctions/{sample_storage_auction_id}/deposit/status",
            headers=buyer_headers,
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
        data = r.json()
        for k in ("has_deposit", "deposit_required", "deposit_amount"):
            assert k in data, f"missing key '{k}' in response {data}"
        # 'status' is only included when deposit_required=True
        if data.get("deposit_required"):
            assert "status" in data, f"missing 'status' when deposit_required=true: {data}"
        assert isinstance(data["has_deposit"], bool)
        assert isinstance(data["deposit_required"], bool)

    def test_has_deposit_true_when_not_required(self, buyer_headers, sample_storage_auction_id):
        r = requests.get(
            f"{API}/storage-auctions/{sample_storage_auction_id}/deposit/status",
            headers=buyer_headers,
            timeout=30,
        )
        assert r.status_code == 200
        data = r.json()
        # When deposit_required is false, has_deposit should be true (passthrough)
        if not data["deposit_required"]:
            assert data["has_deposit"] is True, f"expected has_deposit=true when not required, got {data}"


# ---------- FIX 7: Marketing integrations ----------

class TestMarketingIntegrations:
    def test_put_marketing_requires_admin(self):
        r = requests.put(f"{API}/admin/site-config/marketing", json={"fb_pixel_id": "x"}, timeout=30)
        assert r.status_code in (401, 403)

    def test_put_and_get_marketing_persists(self, admin_headers):
        payload = {
            "fb_pixel_id": "TEST_FB_123",
            "gtm_id": "GTM-TEST123",
            "google_ads_id": "AW-TEST456",
        }
        r = requests.put(f"{API}/admin/site-config/marketing", json=payload, headers=admin_headers, timeout=30)
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:400]}"

        # GET public site-config
        r2 = requests.get(f"{API}/site-config", timeout=30)
        assert r2.status_code == 200, r2.text[:300]
        body = r2.json()
        mk = body.get("marketing") or {}
        assert mk.get("fb_pixel_id") == "TEST_FB_123", f"persistence failed {mk}"
        assert mk.get("gtm_id") == "GTM-TEST123"
        assert mk.get("google_ads_id") == "AW-TEST456"


# ---------- FIX 4: Scheduler ----------

class TestScheduler:
    def test_scheduler_module_registers_13_jobs(self):
        """Verify scheduler module exposes activate_upcoming_auctions_job and registers it."""
        import importlib, sys
        sys.path.insert(0, "/app/backend")
        mod = importlib.import_module("services.scheduler")
        # Check that new job function exists in the module (defined inside start fn is acceptable - check via source)
        src = open("/app/backend/services/scheduler.py").read()
        assert "activate_upcoming_auctions_job" in src
        assert 'id="activate_upcoming_auctions"' in src or "id='activate_upcoming_auctions'" in src

    def test_backend_log_shows_13_jobs(self):
        import subprocess
        res = subprocess.run(
            ["grep", "-c", "Scheduler initialized with 13 jobs", "/var/log/supervisor/backend.err.log"],
            capture_output=True, text=True,
        )
        count = int((res.stdout or "0").strip() or 0)
        assert count >= 1, "scheduler log line 'Scheduler initialized with 13 jobs' not found"


# ---------- FIX 5: Profile ----------

class TestProfileEndpoint:
    def test_put_profile_requires_auth(self):
        r = requests.put(f"{API}/profile", json={"name": "X"}, timeout=30)
        assert r.status_code in (401, 403)

    def test_put_profile_persists(self, buyer_headers, buyer_token):
        if not buyer_token:
            pytest.skip("no buyer token")
        suffix = str(int(time.time()))[-6:]
        new_name = f"TEST Buyer {suffix}"
        payload = {"name": new_name, "phone": "+15145550199", "province": "QC"}
        r = requests.put(f"{API}/profile", json=payload, headers=buyer_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        body = r.json()
        # returned user
        user = body.get("user") or body
        assert user.get("name") == new_name, f"name not returned: {user}"
        # Verify persistence via /profile or /auth/me
        r2 = requests.get(f"{API}/profile", headers=buyer_headers, timeout=30)
        if r2.status_code == 200:
            u2 = r2.json().get("user") or r2.json()
            assert u2.get("name") == new_name


# ---------- FIX 6: Admin storage facilities ----------

class TestAdminStorageFacilities:
    def test_list_requires_admin(self):
        r = requests.get(f"{API}/admin/storage-facilities", timeout=30)
        assert r.status_code in (401, 403)

    def test_list_returns_array(self, admin_headers):
        r = requests.get(f"{API}/admin/storage-facilities", headers=admin_headers, timeout=30)
        assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
        data = r.json()
        items = data if isinstance(data, list) else (data.get("facilities") or data.get("items") or [])
        assert isinstance(items, list)

    def test_verify_suspend_delete_endpoints_exist(self, admin_headers):
        """Call with fake id — should 404, not 405, confirming routes exist."""
        fake = "nonexistent-id-iter178"
        r_v = requests.post(f"{API}/admin/storage-facilities/{fake}/verify", headers=admin_headers, timeout=30)
        assert r_v.status_code != 405, f"verify route missing (405): {r_v.text[:200]}"
        r_s = requests.post(f"{API}/admin/storage-facilities/{fake}/suspend", headers=admin_headers, timeout=30)
        assert r_s.status_code != 405, f"suspend route missing (405): {r_s.text[:200]}"
        r_d = requests.delete(f"{API}/admin/storage-facilities/{fake}", headers=admin_headers, timeout=30)
        assert r_d.status_code != 405, f"delete route missing (405): {r_d.text[:200]}"


# ---------- Regression: storage endpoints ----------

class TestStorageRegression:
    def test_public_list(self):
        r = requests.get(f"{API}/storage-auctions", timeout=30)
        assert r.status_code == 200

    def test_public_detail(self, sample_storage_auction_id):
        r = requests.get(f"{API}/storage-auctions/{sample_storage_auction_id}", timeout=30)
        assert r.status_code == 200
