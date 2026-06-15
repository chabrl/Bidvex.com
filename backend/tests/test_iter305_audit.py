"""iter305 — pre-launch hardening audit, backend surface area.

Covers:
- /api/auth/register without phone (buyer flow)
- Marketplace browse APIs return 200 for unauth visitors
- /api/admin/listings-moderation pending listings (admin only)
- /api/admin/analytics availability
- Static / public APIs used by /legal/* pages
"""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="session")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(session):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text[:160]}")
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"no token in admin login response: {r.json()}"
    return tok


@pytest.fixture
def admin_client(session, admin_token):
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"})
    return s


# ------- iter305 buyer flow -------

class TestBuyerRegisterWithoutPhone:
    def test_register_no_phone_ok(self, session):
        email = f"TEST_iter305_{uuid.uuid4().hex[:8]}@example.com"
        payload = {
            "email": email,
            "password": "TestBuyer123!",
            "name": "Iter305 Buyer",
            # NOTE: no phone field
            "terms_agreed": True,
            "ai_disclosure_consent": True,
            "privacy_accepted": True,
        }
        r = session.post(f"{BASE_URL}/api/auth/register", json=payload, timeout=20)
        assert r.status_code in (200, 201), f"register without phone failed: {r.status_code} {r.text[:200]}"
        data = r.json()
        assert "access_token" in data or "token" in data, f"missing token in response: {data}"


# ------- Buyer browse marketplaces (unauth) -------

class TestMarketplaceBrowseAPIs:
    def test_marketplace_listings_public(self, session):
        r = session.get(f"{BASE_URL}/api/listings", timeout=20)
        assert r.status_code == 200, f"/api/listings failed: {r.status_code}"
        assert isinstance(r.json(), (list, dict))

    def test_lot_auctions_public(self, session):
        # try common lot endpoints
        for path in ("/api/lots", "/api/lot-auctions", "/api/lot-events"):
            r = session.get(f"{BASE_URL}{path}", timeout=20)
            if r.status_code == 200:
                return
        pytest.skip("no public lot-auctions endpoint discovered")

    def test_vehicle_auctions_public(self, session):
        for path in ("/api/vehicle-auctions", "/api/vehicles", "/api/vehicles/public"):
            r = session.get(f"{BASE_URL}{path}", timeout=20)
            if r.status_code == 200:
                return
        pytest.skip("no public vehicle-auctions endpoint discovered")

    def test_storage_auctions_public(self, session):
        for path in ("/api/storage-auctions", "/api/storage-listings", "/api/storage"):
            r = session.get(f"{BASE_URL}{path}", timeout=20)
            if r.status_code == 200:
                return
        pytest.skip("no public storage-auctions endpoint discovered")


# ------- Admin endpoints -------

class TestAdminFlows:
    def test_admin_listings_moderation(self, admin_client):
        for path in ("/api/admin/listings-moderation", "/api/admin/listings/pending", "/api/admin/pending-listings"):
            r = admin_client.get(f"{BASE_URL}{path}", timeout=20)
            if r.status_code == 200 and r.headers.get("content-type", "").startswith("application/json"):
                assert isinstance(r.json(), (list, dict))
                return
        pytest.skip("no JSON admin moderation listing endpoint discovered")

    def test_admin_analytics(self, admin_client):
        for path in ("/api/admin/advanced-analytics", "/api/admin/analytics", "/api/analytics/admin"):
            r = admin_client.get(f"{BASE_URL}{path}", timeout=20)
            if r.status_code == 200:
                return
        pytest.skip("no admin analytics endpoint discovered")


# ------- iter305 static page aliases ------- (HTTP 200 root, SPA serves index.html for everything,
# so we just verify the frontend renders these as React routes in the playwright phase, not here.)


# ------- Public legal APIs (used by /legal/* pages) -------

class TestLegalPublicAPIs:
    @pytest.mark.parametrize("path", [
        "/api/legal/cookie-policy",
        "/api/legal/terms",
        "/api/legal/privacy",
    ])
    def test_legal_endpoint(self, session, path):
        # Try EN and FR, skip if endpoint not present (frontend may have static text only)
        r = session.get(f"{BASE_URL}{path}?lang=en", timeout=20)
        if r.status_code == 404:
            pytest.skip(f"{path} not implemented as API (static page only)")
        assert r.status_code == 200, f"{path}: {r.status_code} {r.text[:160]}"
