"""
Phase 2 admin panel audit (iteration 155).

Covers:
- 2 new endpoints in routes/admin_deposits.py:
    POST /api/admin/vehicle-invoices/{invoice_id}/mark-paid
    POST /api/admin/vehicle-invoices/{invoice_id}/send-reminder
- 3 Phase-1 gap endpoints now consumed by admin UI:
    GET /api/vehicle-admin/invoices
    PUT /api/admin/users/{user_id}/opc-verify
    PUT /api/admin/listings/{id}/feature
- Analytics smoke: /api/admin/analytics, /revenue, /listings
- Quick regression of Phase-1 admin routes to ensure no breakage.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(api):
    r = api.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=30)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    data = r.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"No token in login response: {data}"
    return tok


@pytest.fixture(scope="session")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ───────────────────────── AUTH ─────────────────────────
class TestAuth:
    def test_admin_login_returns_token(self, admin_token):
        assert isinstance(admin_token, str) and len(admin_token) > 10


# ───────────────────── VEHICLE INVOICES LIST ─────────────────
class TestVehicleInvoicesList:
    def test_list_happy_path(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/vehicle-admin/invoices?limit=3", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert "invoices" in body and isinstance(body["invoices"], list)
        assert "stats" in body and isinstance(body["stats"], dict)
        for k in ("pending", "overdue", "paid"):
            assert k in body["stats"], f"missing stats.{k}"
            assert isinstance(body["stats"][k], int)

    def test_list_with_status_filter_paid(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/vehicle-admin/invoices?status=paid&limit=5", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        # every returned invoice (if any) should be paid
        for inv in body.get("invoices", []):
            assert inv.get("payment_status") == "paid"

    def test_list_with_invoice_type_filter(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/vehicle-admin/invoices?invoice_type=buyer_fee&limit=5", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text[:300]

    def test_list_without_auth(self, api):
        r = requests.get(f"{BASE_URL}/api/vehicle-admin/invoices?limit=1", timeout=30)
        assert r.status_code in (401, 403), r.text[:200]


# ───────────────────── MARK INVOICE PAID ─────────────────────
class TestMarkInvoicePaid:
    def test_mark_paid_nonexistent_returns_404(self, api, auth_headers):
        r = api.post(
            f"{BASE_URL}/api/admin/vehicle-invoices/nonexistent/mark-paid",
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 404, f"Expected 404 for nonexistent, got {r.status_code} {r.text[:200]}"

    def test_mark_paid_without_auth_returns_401(self, api):
        r = requests.post(
            f"{BASE_URL}/api/admin/vehicle-invoices/nonexistent/mark-paid",
            timeout=30,
        )
        # FastAPI+HTTPBearer returns 401 (or 403 if bearer enforcer configured that way)
        assert r.status_code in (401, 403), f"Expected 401/403 unauth, got {r.status_code} {r.text[:200]}"


# ───────────────────── SEND INVOICE REMINDER ────────────────
class TestSendInvoiceReminder:
    def test_send_reminder_nonexistent_returns_404(self, api, auth_headers):
        r = api.post(
            f"{BASE_URL}/api/admin/vehicle-invoices/nonexistent/send-reminder",
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code} {r.text[:200]}"

    def test_send_reminder_without_auth_returns_401(self, api):
        r = requests.post(
            f"{BASE_URL}/api/admin/vehicle-invoices/nonexistent/send-reminder",
            timeout=30,
        )
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code} {r.text[:200]}"


# ───────────────────── OPC VERIFY ───────────────────────────
class TestOPCVerify:
    def test_opc_verify_nonexistent_returns_404(self, api, auth_headers):
        r = api.put(
            f"{BASE_URL}/api/admin/users/nonexistent/opc-verify",
            headers=auth_headers,
            json={"opc_permit_verified": False},
            timeout=30,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code} {r.text[:200]}"

    def test_opc_verify_without_auth_returns_401(self, api):
        r = requests.put(
            f"{BASE_URL}/api/admin/users/nonexistent/opc-verify",
            json={"opc_permit_verified": False},
            timeout=30,
        )
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code} {r.text[:200]}"

    def test_opc_verify_happy_path_and_persists(self, api, auth_headers):
        # pick a non-admin user
        ur = api.get(f"{BASE_URL}/api/admin/users?limit=50", headers=auth_headers, timeout=30)
        assert ur.status_code == 200, ur.text[:200]
        payload = ur.json()
        users = payload.get("users") if isinstance(payload, dict) else payload
        assert isinstance(users, list) and users, "no users returned"
        target = next((u for u in users if u.get("email") != ADMIN_EMAIL and (u.get("role") or "").lower() != "admin"), None)
        if not target:
            pytest.skip("No non-admin user available to toggle OPC verification")
        user_id = target.get("id") or target.get("_id")
        assert user_id, f"no id on user {target}"

        # enable
        r = api.put(
            f"{BASE_URL}/api/admin/users/{user_id}/opc-verify",
            headers=auth_headers,
            json={"opc_permit_verified": True, "opc_permit_number": "TEST_1234"},
            timeout=30,
        )
        assert r.status_code == 200, f"OPC enable failed: {r.status_code} {r.text[:200]}"
        body = r.json()
        assert body.get("success") is True

        # verify via GET user detail
        g = api.get(f"{BASE_URL}/api/admin/users/{user_id}/detail", headers=auth_headers, timeout=30)
        if g.status_code == 200:
            detail = g.json()
            u = detail.get("user") if isinstance(detail, dict) and "user" in detail else detail
            assert u.get("opc_permit_verified") is True, f"opc_permit_verified not persisted: {u}"
            assert u.get("opc_permit_number") == "TEST_1234", f"opc_permit_number not persisted: {u}"

        # cleanup — disable
        r2 = api.put(
            f"{BASE_URL}/api/admin/users/{user_id}/opc-verify",
            headers=auth_headers,
            json={"opc_permit_verified": False},
            timeout=30,
        )
        assert r2.status_code == 200, r2.text[:200]


# ───────────────────── LISTINGS FEATURE TOGGLE ──────────────
class TestListingsFeature:
    def test_feature_nonexistent_not_forbidden(self, api, auth_headers):
        r = api.put(
            f"{BASE_URL}/api/admin/listings/nonexistent-id-xyz/feature",
            headers=auth_headers,
            json={"is_featured": True},
            timeout=30,
        )
        # should NOT be 403 for admin — either 200 (if creates) or 404 (missing)
        assert r.status_code != 403, f"Admin got 403 on listings/feature: {r.text[:200]}"
        assert r.status_code in (200, 404, 400), f"Unexpected status {r.status_code}: {r.text[:200]}"


# ───────────────────── ANALYTICS ────────────────────────────
class TestAnalytics:
    def test_analytics_overview(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/admin/analytics?days=30", headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"analytics: {r.status_code} {r.text[:200]}"

    def test_analytics_revenue(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/admin/analytics/revenue?days=7", headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"analytics/revenue: {r.status_code} {r.text[:200]}"

    def test_analytics_listings(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/admin/analytics/listings", headers=auth_headers, timeout=30)
        assert r.status_code == 200, f"analytics/listings: {r.status_code} {r.text[:200]}"


# ───────────────────── PHASE-1 REGRESSION ───────────────────
class TestPhase1Regression:
    def test_vehicle_deposits_admin(self, api, auth_headers):
        r = api.get(f"{BASE_URL}/api/admin/vehicle-deposits", headers=auth_headers, timeout=30)
        assert r.status_code == 200, r.text[:200]
        body = r.json()
        assert "deposits" in body

    def test_site_mode_put(self, api, auth_headers):
        r = api.put(
            f"{BASE_URL}/api/admin/site-mode",
            headers=auth_headers,
            json={"mode": "live", "message": "ok", "message_fr": "ok"},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:200]

    def test_users_status_nonexistent(self, api, auth_headers):
        r = api.put(
            f"{BASE_URL}/api/admin/users/nonexistent/status",
            headers=auth_headers,
            json={"status": "suspended", "reason": "test"},
            timeout=30,
        )
        assert r.status_code == 404, r.text[:200]
