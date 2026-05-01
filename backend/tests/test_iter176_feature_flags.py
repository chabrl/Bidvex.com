"""iter176 — Feature Flags + Vehicle Waitlist backend tests."""
import os
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
FLAG_KEY = "vehicle_auctions_enabled"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed {r.status_code} {r.text}")
    tok = r.json().get("token") or r.json().get("access_token")
    assert tok
    return tok


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def user_token():
    email = f"TEST_ff_{uuid.uuid4().hex[:8]}@example.com"
    r = requests.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "TestPass123!", "full_name": "FF Tester"}, timeout=30)
    if r.status_code not in (200, 201):
        pytest.skip(f"register failed {r.status_code}")
    data = r.json()
    return data.get("token") or data.get("access_token")


# ── Public flag endpoints ──
class TestPublicFlag:
    def test_default_flag_value(self):
        r = requests.get(f"{BASE_URL}/api/feature-flags/{FLAG_KEY}", timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["key"] == FLAG_KEY
        assert "enabled" in data
        assert isinstance(data["enabled"], bool)

    def test_cache_control(self):
        r = requests.get(f"{BASE_URL}/api/feature-flags/{FLAG_KEY}", timeout=15)
        cc = r.headers.get("Cache-Control", "")
        assert "max-age=60" in cc, f"expected max-age=60 got {cc!r}"

    def test_bogus_flag_404(self):
        r = requests.get(f"{BASE_URL}/api/feature-flags/bogus_key_xyz", timeout=15)
        assert r.status_code == 404


# ── Admin flag endpoints ──
class TestAdminFlag:
    def test_admin_list_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/feature-flags", timeout=15)
        assert r.status_code in (401, 403)

    def test_admin_list_returns_flags(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/feature-flags", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "flags" in data
        assert isinstance(data["flags"], list)
        assert any(f["key"] == FLAG_KEY for f in data["flags"])
        target = next(f for f in data["flags"] if f["key"] == FLAG_KEY)
        assert "description_en" in target
        assert "description_fr" in target

    def test_non_admin_forbidden(self, user_token):
        if not user_token:
            pytest.skip("no user token")
        r = requests.get(f"{BASE_URL}/api/admin/feature-flags", headers={"Authorization": f"Bearer {user_token}"}, timeout=15)
        assert r.status_code in (401, 403)

    def test_patch_unknown_flag_404(self, admin_headers):
        r = requests.patch(f"{BASE_URL}/api/admin/feature-flags/unknown_flag", json={"enabled": True}, headers=admin_headers, timeout=15)
        assert r.status_code == 404

    def test_patch_toggle_and_verify_public(self, admin_headers):
        # Toggle ON
        r = requests.patch(f"{BASE_URL}/api/admin/feature-flags/{FLAG_KEY}", json={"enabled": True}, headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["enabled"] is True
        assert data["updated_by"] == ADMIN_EMAIL

        pub = requests.get(f"{BASE_URL}/api/feature-flags/{FLAG_KEY}", timeout=15).json()
        assert pub["enabled"] is True

        # Toggle OFF (restore default per agent note)
        r2 = requests.patch(f"{BASE_URL}/api/admin/feature-flags/{FLAG_KEY}", json={"enabled": False}, headers=admin_headers, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["enabled"] is False

        pub2 = requests.get(f"{BASE_URL}/api/feature-flags/{FLAG_KEY}", timeout=15).json()
        assert pub2["enabled"] is False


# ── Waitlist ──
class TestWaitlist:
    email = f"test_waitlist_{uuid.uuid4().hex[:8]}@example.com"

    def test_signup_default_lang(self):
        r = requests.post(f"{BASE_URL}/api/waitlist/vehicle-auctions", json={"email": self.email}, timeout=15)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["success"] is True
        assert data["already_on_list"] is False
        assert data["lang"] == "en"

    def test_signup_duplicate_upsert(self):
        r = requests.post(f"{BASE_URL}/api/waitlist/vehicle-auctions", json={"email": self.email, "lang": "fr"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["already_on_list"] is True

    def test_signup_bad_lang_normalized(self):
        em = f"test_badlang_{uuid.uuid4().hex[:8]}@example.com"
        r = requests.post(f"{BASE_URL}/api/waitlist/vehicle-auctions", json={"email": em, "lang": "zz"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["lang"] == "en"

    def test_signup_bad_email_422(self):
        r = requests.post(f"{BASE_URL}/api/waitlist/vehicle-auctions", json={"email": "not-an-email"}, timeout=15)
        assert r.status_code in (400, 422)

    def test_admin_count(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/waitlist/vehicle-auctions/count", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        assert r.json()["count"] >= 1

    def test_admin_count_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/waitlist/vehicle-auctions/count", timeout=15)
        assert r.status_code in (401, 403)

    def test_admin_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/waitlist/vehicle-auctions", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        data = r.json()
        assert "items" in data and "count" in data
        assert isinstance(data["items"], list)
        # ObjectId should be excluded
        for item in data["items"][:5]:
            assert "_id" not in item

    def test_admin_list_requires_auth(self):
        r = requests.get(f"{BASE_URL}/api/admin/waitlist/vehicle-auctions", timeout=15)
        assert r.status_code in (401, 403)


# ── Regression: scheduler + storage smoke ──
class TestRegression:
    def test_scheduler_jobs(self, admin_headers):
        # Best-effort; skip if endpoint missing
        r = requests.get(f"{BASE_URL}/api/admin/scheduler/jobs", headers=admin_headers, timeout=15)
        if r.status_code == 404:
            pytest.skip("scheduler endpoint not exposed")
        assert r.status_code == 200
        data = r.json()
        jobs = data.get("jobs", data) if isinstance(data, dict) else data
        if isinstance(jobs, list):
            assert len(jobs) >= 12, f"expected >=12 jobs got {len(jobs)}"
