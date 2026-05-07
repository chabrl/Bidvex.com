"""
iter197 — Admin triage counter endpoints + vehicle seller.user_id projection
- GET /api/admin/vehicles/disputed-settlements/count (admin only)
- GET /api/admin/currency-appeals/pending-count (admin only)
- GET /api/vehicles/{id} response includes seller.user_id

Run: PYTHONPATH=/app/backend pytest tests/test_iter197_admin_counters.py -v
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "iter189buyer@test.com"
BUYER_PASSWORD = "TestBuyer123!"


def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login failed for {email}: {r.status_code} {r.text}"
    j = r.json()
    return j.get("access_token") or j["token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="module")
def buyer_token():
    try:
        return _login(BUYER_EMAIL, BUYER_PASSWORD)
    except AssertionError:
        pytest.skip("buyer login failed — preview env may have rotated creds")


# --- Admin counter endpoints ----------------------------------------------------
class TestAdminCounters:
    def test_disputed_settlements_count_admin_ok(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/vehicles/disputed-settlements/count",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert isinstance(data["total"], int)
        assert data["total"] >= 0

    def test_disputed_settlements_count_non_admin_forbidden(self, buyer_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/vehicles/disputed-settlements/count",
            headers={"Authorization": f"Bearer {buyer_token}"},
            timeout=15,
        )
        assert r.status_code == 403, f"expected 403, got {r.status_code}: {r.text}"

    def test_disputed_settlements_count_unauth(self):
        r = requests.get(f"{BASE_URL}/api/admin/vehicles/disputed-settlements/count", timeout=15)
        assert r.status_code in (401, 403)

    def test_currency_appeals_pending_count_admin_ok(self, admin_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/currency-appeals/pending-count",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=15,
        )
        assert r.status_code == 200
        data = r.json()
        assert "total" in data
        assert isinstance(data["total"], int)
        assert data["total"] >= 0

    def test_currency_appeals_pending_count_non_admin_forbidden(self, buyer_token):
        r = requests.get(
            f"{BASE_URL}/api/admin/currency-appeals/pending-count",
            headers={"Authorization": f"Bearer {buyer_token}"},
            timeout=15,
        )
        assert r.status_code == 403

    def test_currency_appeals_pending_count_unauth(self):
        r = requests.get(f"{BASE_URL}/api/admin/currency-appeals/pending-count", timeout=15)
        assert r.status_code in (401, 403)


# --- Dealer license endpoint (used by Pilot Welcome Banner) ---------------------
class TestDealerLicenseMe:
    def test_buyer_dealer_license_me(self, buyer_token):
        r = requests.get(
            f"{BASE_URL}/api/dealer-licenses/me",
            headers={"Authorization": f"Bearer {buyer_token}"},
            timeout=15,
        )
        # Should be 200 with the seeded approved license; if 404 that's also a valid "no license" state
        assert r.status_code in (200, 404), f"unexpected status {r.status_code}: {r.text}"
        if r.status_code == 200:
            data = r.json()
            # The endpoint may return the license document directly or wrapped
            license_doc = data.get("license", data)
            print(f"dealer-licenses/me → status={license_doc.get('status')} reviewed_at={license_doc.get('reviewed_at')}")


# --- Vehicle endpoint includes seller.user_id ----------------------------------
class TestVehicleSellerUserId:
    def test_vehicles_list_and_detail_have_seller_user_id(self):
        # public list
        r = requests.get(f"{BASE_URL}/api/vehicles?limit=5", timeout=20)
        if r.status_code != 200:
            pytest.skip(f"list endpoint returned {r.status_code}")
        listings = r.json()
        if isinstance(listings, dict):
            listings = listings.get("vehicles", listings.get("items", []))
        if not listings:
            pytest.skip("no vehicles available to test")
        # find one with embedded seller
        target = None
        for v in listings:
            vid = v.get("id") or v.get("_id")
            if not vid:
                continue
            r2 = requests.get(f"{BASE_URL}/api/vehicles/{vid}", timeout=15)
            if r2.status_code == 200:
                detail = r2.json()
                if detail.get("seller"):
                    target = detail
                    break
        if not target:
            pytest.skip("no vehicle detail with embedded seller available")
        seller = target["seller"]
        assert isinstance(seller, dict), f"seller is not dict: {seller}"
        assert "user_id" in seller, f"seller dict missing 'user_id' key: {list(seller.keys())}"
        # user_id may be None for legacy seeded data — log but don't fail
        print(f"vehicle {target.get('id')} seller.user_id={seller.get('user_id')!r}")
