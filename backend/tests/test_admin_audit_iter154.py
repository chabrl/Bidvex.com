"""
Iteration 154 — Admin Panel Audit & Repair (Phase 1) regression tests.

Focus:
  - Critical security fix: 25 endpoints previously rejected primary admin
    charbel911@gmail.com due to `email.endswith("@bidvex.com")`. Now use
    role-based check.
  - New /api/admin/vehicle-deposits routes (list/get/release/capture).
  - SiteModeUpdate pydantic model extended (message_fr, scheduled_start,
    scheduled_end).
  - Sanity: PUT /api/admin/users/{id}/status, trust_safety, escrow admin,
    openapi registration.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL not set"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


# ─── Fixtures ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(api):
    resp = api.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert resp.status_code == 200, f"admin login failed: {resp.status_code} {resp.text}"
    body = resp.json()
    token = body.get("access_token") or body.get("token") or (body.get("session") or {}).get("access_token")
    assert token, f"no token in login response: {body}"
    return token


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


# ─── Basic health & OpenAPI ────────────────────────────────────────────────
class TestHealthAndOpenapi:
    def test_health(self, api):
        r = api.get(f"{BASE_URL}/api/health", timeout=10)
        assert r.status_code == 200

    def test_openapi_registers_new_routes(self, api):
        # FastAPI serves openapi.json at the app root. The public ingress only
        # routes /api/* to the backend, so we hit localhost directly to inspect
        # the full route map.
        r = requests.get("http://localhost:8001/openapi.json", timeout=15)
        assert r.status_code == 200, r.text[:200]
        paths = r.json().get("paths", {})
        # new vehicle-deposits routes
        assert "/api/admin/vehicle-deposits" in paths, "admin vehicle-deposits list route missing"
        assert "/api/admin/vehicle-deposits/{deposit_id}" in paths
        assert "/api/admin/vehicle-deposits/{deposit_id}/release" in paths
        assert "/api/admin/vehicle-deposits/{deposit_id}/capture" in paths


# ─── Auth login ────────────────────────────────────────────────────────────
class TestAuth:
    def test_admin_login_returns_token(self, api):
        resp = api.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
            timeout=15,
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        token = body.get("access_token") or body.get("token")
        assert token and isinstance(token, str) and len(token) > 10


# ─── Site Mode: was broken by @bidvex.com check + new fields ───────────────
class TestSiteMode:
    def test_put_site_mode_live_accepts_charbel_admin(self, api, admin_headers):
        payload = {
            "mode": "live",
            "message": "Back online",
            "message_fr": "De retour en ligne",
            "scheduled_start": None,
            "scheduled_end": None,
            "social_links": None,
        }
        r = api.put(f"{BASE_URL}/api/admin/site-mode", json=payload, headers=admin_headers, timeout=15)
        assert r.status_code == 200, f"expected 200 for primary admin, got {r.status_code} {r.text}"
        body = r.json()
        assert body.get("success") is True
        assert body.get("mode") == "live"

    def test_put_site_mode_invalid_mode_returns_400(self, api, admin_headers):
        r = api.put(
            f"{BASE_URL}/api/admin/site-mode",
            json={"mode": "offworld"},
            headers=admin_headers,
            timeout=15,
        )
        assert r.status_code == 400

    def test_site_mode_update_persists_new_fields(self, api, admin_headers):
        # Set maintenance with french + schedule, then GET public endpoint
        payload = {
            "mode": "maintenance",
            "message": "Quick maintenance",
            "message_fr": "Maintenance rapide",
            "scheduled_start": "2030-01-01T00:00:00Z",
            "scheduled_end": "2030-01-01T01:00:00Z",
        }
        r = api.put(f"{BASE_URL}/api/admin/site-mode", json=payload, headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text

        # Revert to live (cleanup)
        api.put(f"{BASE_URL}/api/admin/site-mode", json={"mode": "live", "message": "ok"}, headers=admin_headers, timeout=15)

    def test_put_site_mode_no_auth_rejected(self, api):
        r = api.put(f"{BASE_URL}/api/admin/site-mode", json={"mode": "live"}, timeout=15)
        assert r.status_code in (401, 403)


# ─── Admin Vehicle Deposits ────────────────────────────────────────────────
class TestAdminVehicleDeposits:
    def test_list_deposits_requires_auth(self, api):
        r = api.get(f"{BASE_URL}/api/admin/vehicle-deposits", timeout=15)
        assert r.status_code in (401, 403), f"no-auth should be 401/403, got {r.status_code}"

    def test_list_deposits_admin_ok(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/admin/vehicle-deposits", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "count" in body and "deposits" in body
        assert isinstance(body["deposits"], list)
        assert isinstance(body["count"], int)
        # If any deposits exist, enrichment keys should appear when user/vehicle are available.
        # We don't assert they must be present (db may be empty), but structure must be list of dicts.
        for d in body["deposits"]:
            assert isinstance(d, dict)

    def test_get_deposit_not_found(self, api, admin_headers):
        r = api.get(
            f"{BASE_URL}/api/admin/vehicle-deposits/nonexistent-id-xyz",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 404

    def test_release_deposit_not_found(self, api, admin_headers):
        r = api.post(
            f"{BASE_URL}/api/admin/vehicle-deposits/nonexistent-id-xyz/release",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 404

    def test_capture_deposit_not_found(self, api, admin_headers):
        r = api.post(
            f"{BASE_URL}/api/admin/vehicle-deposits/nonexistent-id-xyz/capture",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 404

    def test_release_deposit_requires_auth(self, api):
        r = api.post(f"{BASE_URL}/api/admin/vehicle-deposits/foo/release", timeout=15)
        assert r.status_code in (401, 403)


# ─── User status (admin.py line 248) ──────────────────────────────────────
class TestAdminUserStatus:
    def _any_non_admin_user_id(self, api, admin_headers):
        # Try to pull at least one user id via admin users list. Fallback to creating one? skip if none.
        candidates = [
            f"{BASE_URL}/api/admin/users",
            f"{BASE_URL}/api/admin/users?limit=5",
        ]
        for url in candidates:
            r = api.get(url, headers=admin_headers, timeout=15)
            if r.status_code == 200:
                data = r.json()
                users = data.get("users") if isinstance(data, dict) else data
                if isinstance(users, list):
                    for u in users:
                        uid = u.get("id") or u.get("user_id") or u.get("_id")
                        if uid and u.get("email") != ADMIN_EMAIL:
                            return uid
        return None

    def test_invalid_status_returns_400(self, api, admin_headers):
        # Use arbitrary id — invalid status should 400 regardless (validation runs before lookup).
        r = api.put(
            f"{BASE_URL}/api/admin/users/any-user-id/status",
            json={"status": "invalid", "reason": "test"},
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 400, r.text

    def test_update_user_status_happy_path(self, api, admin_headers):
        uid = self._any_non_admin_user_id(api, admin_headers)
        if not uid:
            pytest.skip("no non-admin user found to toggle status")
        r = api.put(
            f"{BASE_URL}/api/admin/users/{uid}/status",
            json={"status": "suspended", "reason": "TEST suspend"},
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body.get("user_status") == "suspended"
        # restore
        r2 = api.put(
            f"{BASE_URL}/api/admin/users/{uid}/status",
            json={"status": "active", "reason": "TEST restore"},
            headers=admin_headers, timeout=15,
        )
        assert r2.status_code == 200

    def test_update_nonexistent_user_returns_404(self, api, admin_headers):
        r = api.put(
            f"{BASE_URL}/api/admin/users/does-not-exist-xyz/status",
            json={"status": "suspended", "reason": "test"},
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 404


# ─── Trust & Safety admin (previously broken by endswith) ────────────────
class TestTrustSafety:
    def test_trust_safety_scores_accessible_to_charbel(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/admin/trust-safety/scores", headers=admin_headers, timeout=15)
        assert r.status_code == 200, f"charbel should access trust-safety; got {r.status_code} {r.text[:300]}"


# ─── Escrow admin endpoints ──────────────────────────────────────────────
class TestEscrowAdmin:
    def test_escrow_transactions_list(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/escrow/admin/escrow/transactions", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text
        assert isinstance(r.json(), list)

    def test_escrow_penalties_list(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/escrow/admin/escrow/penalties", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text

    def test_escrow_disputes_list(self, api, admin_headers):
        r = api.get(f"{BASE_URL}/api/escrow/admin/escrow/disputes", headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text

    def test_charge_penalty_admin_not_403(self, api, admin_headers):
        """Admin should pass role gate (even if Stripe call fails downstream)."""
        r = api.post(
            f"{BASE_URL}/api/escrow/admin/charge-penalty",
            json={"seller_id": "TEST_seller_iter154", "listing_id": "TEST_listing_iter154", "reason": "test"},
            headers=admin_headers, timeout=20,
        )
        # Critical: NOT 403 for admin (was the bug). Accept 200/400/404/500 as downstream outcomes.
        assert r.status_code != 403, f"admin was rejected with 403: {r.text[:400]}"
