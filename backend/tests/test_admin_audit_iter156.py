"""
Iteration 156 — Phase 3 admin audit.
Tests:
  - Bulk admin listings actions
  - Admin listing edit (single + multi)
  - Invoice PDF bilingual query param (regression for NameError bug)
  - Quick regression on Phase 1/2 admin endpoints
  - Role canonicalization check
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
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
    assert r.status_code == 200, f"Login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    token = data.get("access_token") or data.get("token")
    assert token, f"No token field in response: {list(data.keys())}"
    return token


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def admin_user(api, admin_headers):
    r = api.get(f"{BASE_URL}/api/auth/me", headers=admin_headers)
    assert r.status_code == 200, r.text
    return r.json()


# ========== AUTH & ROLE ==========
class TestAuthRole:
    def test_login_returns_token(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 10

    def test_role_is_admin(self, admin_user):
        role = admin_user.get("role")
        assert role in ("admin", "super_admin"), f"unexpected role: {role}"
        # Per PRD, charbel911 is role='admin'
        assert role == "admin", f"expected 'admin' but got '{role}'"


# ========== BULK ACTION ==========
class TestBulkAction:
    URL = "/api/admin/listings/bulk-action"

    def test_no_auth_returns_401_or_403(self, api):
        r = api.post(f"{BASE_URL}{self.URL}", json={"action": "pause", "listing_ids": ["x"]})
        assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"

    def test_empty_listing_ids_returns_422(self, api, admin_headers):
        r = api.post(f"{BASE_URL}{self.URL}", headers=admin_headers,
                     json={"action": "pause", "listing_ids": []})
        assert r.status_code == 422, f"expected 422, got {r.status_code} {r.text[:200]}"

    def test_pause_nonexistent_id(self, api, admin_headers):
        r = api.post(f"{BASE_URL}{self.URL}", headers=admin_headers,
                     json={"action": "pause", "listing_ids": ["nonexistent-id-xyz"]})
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert data["succeeded_count"] == 0
        assert data["failed_count"] == 1
        assert data["action"] == "pause"
        assert data["total"] == 1
        failed = data["failed"]
        assert isinstance(failed, list) and len(failed) == 1
        assert failed[0]["id"] == "nonexistent-id-xyz"
        assert failed[0]["reason"] == "not found"

    def test_delete_unknown_id_no_500(self, api, admin_headers):
        r = api.post(f"{BASE_URL}{self.URL}", headers=admin_headers,
                     json={"action": "delete", "listing_ids": ["nonexistent-del-id"]})
        assert r.status_code == 200, f"got {r.status_code}: {r.text[:300]}"
        data = r.json()
        assert data["failed_count"] == 1
        assert data["succeeded_count"] == 0

    def test_invalid_action(self, api, admin_headers):
        r = api.post(f"{BASE_URL}{self.URL}", headers=admin_headers,
                     json={"action": "nuke", "listing_ids": ["x"]})
        assert r.status_code == 422

    def test_feature_unknown(self, api, admin_headers):
        r = api.post(f"{BASE_URL}{self.URL}", headers=admin_headers,
                     json={"action": "feature", "listing_ids": ["no-such-id-1"]})
        assert r.status_code == 200
        data = r.json()
        assert data["failed_count"] == 1


# ========== EDIT LISTING ==========
class TestEditListing:
    def test_put_nonexistent_returns_404(self, api, admin_headers):
        r = api.put(f"{BASE_URL}/api/admin/listings/nonexistent",
                    headers=admin_headers, json={"title": "t"})
        assert r.status_code == 404, f"got {r.status_code}: {r.text[:300]}"

    def test_put_no_auth_returns_401_or_403(self, api):
        r = api.put(f"{BASE_URL}/api/admin/listings/anything",
                    json={"title": "t"})
        assert r.status_code in (401, 403), f"got {r.status_code}"

    def test_put_negative_starting_price_returns_400(self, api, admin_headers):
        # Use a nonexistent id — spec says negative price → 400.
        # But 404 check runs first. Need a real or bypass. Let's create then edit.
        # Create a real listing first.
        payload = {
            "title": "TEST_bulk_edit_listing",
            "description": "temp",
            "category": "Other",
            "starting_price": 10,
            "city": "Montreal",
            "region": "QC",
        }
        c = api.post(f"{BASE_URL}/api/listings", headers=admin_headers, json=payload)
        if c.status_code not in (200, 201):
            pytest.skip(f"cannot create test listing to verify 400 path: {c.status_code}")
        lid = c.json().get("id") or c.json().get("_id")
        if not lid:
            pytest.skip(f"no id returned on create: {c.text[:200]}")
        try:
            r = api.put(f"{BASE_URL}/api/admin/listings/{lid}",
                        headers=admin_headers, json={"starting_price": -5})
            assert r.status_code == 400, f"got {r.status_code}: {r.text[:200]}"
        finally:
            api.post(f"{BASE_URL}/api/admin/listings/bulk-action",
                     headers=admin_headers,
                     json={"action": "delete", "listing_ids": [lid]})

    def test_put_multi_nonexistent_returns_404(self, api, admin_headers):
        r = api.put(f"{BASE_URL}/api/admin/multi-item-listings/nonexistent",
                    headers=admin_headers, json={"title": "t"})
        assert r.status_code == 404, f"got {r.status_code}: {r.text[:300]}"


# ========== INVOICE PDF ==========
class TestInvoicePDF:
    def test_nonexistent_pdf_fr_returns_404(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/vehicle-invoices/NX/pdf?lang=fr", headers=admin_headers)
        # Must be 404 (invoice not found), NOT 500 (was the bug)
        assert r.status_code == 404, f"got {r.status_code}: {r.text[:300]}"

    def test_nonexistent_pdf_en_returns_404(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/vehicle-invoices/NX2/pdf?lang=en", headers=admin_headers)
        assert r.status_code == 404

    def test_nonexistent_pdf_invalid_lang_returns_404(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/vehicle-invoices/NX3/pdf?lang=xx", headers=admin_headers)
        assert r.status_code == 404, f"got {r.status_code}: {r.text[:200]}"

    def test_no_auth_returns_401_or_403(self, api):
        r = api.get(f"{BASE_URL}/api/vehicle-invoices/NX/pdf?lang=fr")
        assert r.status_code in (401, 403)


# ========== REGRESSION: Phase 1/2 admin endpoints ==========
class TestRegressionPhase12:
    def test_site_mode_accessible(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/admin/site-mode", headers=admin_headers)
        assert r.status_code in (200, 404), f"got {r.status_code}"

    def test_vehicle_deposits_list(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/admin/vehicle-deposits", headers=admin_headers)
        assert r.status_code in (200, 404), f"got {r.status_code}"

    def test_analytics_overview(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/admin/analytics/overview", headers=admin_headers)
        assert r.status_code in (200, 404), f"got {r.status_code}"

    def test_users_ban_status(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/admin/users/ban-status/fake_user_xyz", headers=admin_headers)
        # either 404 user not found, or 200 with status payload
        assert r.status_code in (200, 404), f"got {r.status_code}: {r.text[:200]}"

    def test_invoice_mark_paid_not_found(self, api, admin_headers):
        r = api.post(f"{BASE_URL}/api/admin/vehicle-invoices/NX/mark-paid",
                     headers=admin_headers, json={})
        assert r.status_code in (404, 400, 422), f"got {r.status_code}"

    def test_opc_verify_not_found(self, api, admin_headers):
        # endpoint may use PATCH/PUT; regression check = any non-auth, non-500 code
        r = api.post(f"{BASE_URL}/api/admin/opc-verify/NX",
                     headers=admin_headers, json={})
        # Must NOT be 401/403 (auth works) and NOT 500 (server error)
        assert r.status_code not in (401, 403, 500), f"got {r.status_code}"


# ========== Role canonicalization source scan ==========
class TestRoleCanonicalization:
    def test_no_superadmin_literal_in_routes_or_services(self):
        import subprocess
        result = subprocess.run(
            ["grep", "-rn", "-w", "superadmin",
             "/app/backend/routes/", "/app/backend/services/"],
            capture_output=True, text=True
        )
        # grep returns 1 when no matches (good), 0 when matches (bad)
        assert result.returncode == 1, f"Found 'superadmin' literals:\n{result.stdout}"
