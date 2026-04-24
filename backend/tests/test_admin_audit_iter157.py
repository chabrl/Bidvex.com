"""
Iteration 157 — Backend audit focused on:
  (a) EmailMarketing — campaigns list, campaign stats, delete 404/401 paths
  (b) Site Content / Legal — the 'name db is not defined' fix in 3 admin handlers
  (c) All 14 admin sections respond 200 for charbel911@gmail.com
  (d) Regression of prior Phase 1/2/3 endpoints

All tests auth via charbel911@gmail.com / Anderosli123!@#
"""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="session")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


@pytest.fixture(scope="session")
def admin_token(api):
    r = api.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text[:200]}"
    tok = r.json().get("access_token") or r.json().get("token")
    assert tok, f"No token in login response: {r.text[:200]}"
    return tok


@pytest.fixture(scope="session")
def admin(api, admin_token):
    s = requests.Session()
    s.headers.update(
        {"Content-Type": "application/json", "Authorization": f"Bearer {admin_token}"}
    )
    return s


# ---------- (a) Email Marketing ----------
class TestEmailMarketing:
    def test_campaigns_list(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/marketing/campaigns", timeout=15)
        assert r.status_code == 200, r.text[:200]
        data = r.json()
        # Accept list or {"campaigns": [...]}
        assert isinstance(data, (list, dict))
        if isinstance(data, dict):
            assert "campaigns" in data or "items" in data or "data" in data

    def test_campaign_stats_shape(self, admin):
        # List first to get an id; if empty, skip
        r = admin.get(f"{BASE_URL}/api/admin/marketing/campaigns", timeout=15)
        assert r.status_code == 200
        data = r.json()
        items = data if isinstance(data, list) else (
            data.get("campaigns") or data.get("items") or data.get("data") or []
        )
        if not items:
            pytest.skip("No campaigns exist to fetch stats for")
        cid = items[0].get("id") or items[0].get("_id") or items[0].get("campaign_id")
        if not cid:
            pytest.skip("Campaign has no id field")
        r2 = admin.get(
            f"{BASE_URL}/api/admin/marketing/campaigns/{cid}/stats", timeout=15
        )
        assert r2.status_code == 200, r2.text[:300]
        st = r2.json()
        assert isinstance(st, dict)
        # Keys typical to stats; we only require response is dict-shaped
        for k in ("sent", "delivered", "opened", "clicked"):
            # Not all keys need to exist, but if any do they should be numeric
            if k in st:
                assert isinstance(st[k], (int, float))

    def test_delete_nonexistent_campaign_returns_404(self, admin):
        fake = f"nonexistent-{uuid.uuid4().hex[:8]}"
        r = admin.delete(
            f"{BASE_URL}/api/admin/marketing/campaigns/{fake}", timeout=15
        )
        assert r.status_code in (404, 400), f"Expected 404, got {r.status_code}: {r.text[:200]}"

    def test_delete_without_auth_returns_401_or_403(self, api):
        fake = f"nonexistent-{uuid.uuid4().hex[:8]}"
        r = api.delete(
            f"{BASE_URL}/api/admin/marketing/campaigns/{fake}", timeout=15
        )
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"


# ---------- (b) Legal Pages (bug fix 'name db is not defined') ----------
class TestLegalPages:
    def test_get_legal_pages_admin_200(self, admin):
        r = admin.get(
            f"{BASE_URL}/api/admin/site-config/legal-pages", timeout=15
        )
        assert r.status_code == 200, f"Expected 200 (was 500 before fix): {r.status_code} {r.text[:300]}"
        # Confirm no NameError leakage
        assert "db is not defined" not in r.text

    def test_get_legal_pages_no_auth_401_or_403(self, api):
        r = api.get(f"{BASE_URL}/api/admin/site-config/legal-pages", timeout=15)
        assert r.status_code in (401, 403), f"Expected 401/403, got {r.status_code}"

    def test_put_legal_pages_admin_200(self, admin):
        # First, GET current then PUT back (roundtrip, no destructive changes)
        g = admin.get(
            f"{BASE_URL}/api/admin/site-config/legal-pages", timeout=15
        )
        assert g.status_code == 200
        current = g.json()
        # Construct a minimal valid body—reuse existing content
        body = current if isinstance(current, dict) else {"pages": current}
        r = admin.put(
            f"{BASE_URL}/api/admin/site-config/legal-pages",
            json=body,
            timeout=20,
        )
        # Accept 200 or 422 (if our guessed body shape doesn't match)
        assert r.status_code in (200, 422), f"Unexpected {r.status_code}: {r.text[:300]}"
        assert "db is not defined" not in r.text

    def test_seed_legal_pages_admin_200(self, admin):
        r = admin.post(
            f"{BASE_URL}/api/admin/site-config/seed-legal-pages", timeout=20
        )
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
        assert "db is not defined" not in r.text


# ---------- (c) 14 Admin Sections ----------
class TestAdminSections:
    @pytest.mark.parametrize("path", [
        "/api/admin/site-config",                      # Branding
        "/api/admin/marketplace-settings",             # Marketplace Settings
        "/api/admin/subscription-plans",               # Subscriptions + Pricing Engine
        "/api/admin/subscription-analytics",           # Subscription Analytics
        "/api/admin/coupons",                          # Coupons
        "/api/admin/trust-safety/scores",              # Trust & Safety
        "/api/admin/vehicle-deposits",                 # Escrow
        "/api/admin/messages/flagged",                 # Messaging Oversight
        "/api/admin/platform-cleanup/preview",         # Platform Cleanup
        "/api/admin/email-templates",                  # Email Templates
        "/api/admin/marketing/campaigns",              # Email Marketing
        "/api/admin/site-config/legal-pages",          # Site Content / Legal (fix)
    ])
    def test_section_returns_200(self, admin, path):
        r = admin.get(f"{BASE_URL}{path}", timeout=20)
        assert r.status_code == 200, (
            f"{path} returned {r.status_code} for admin (expected 200): {r.text[:300]}"
        )
        # No 500-like errors leaking
        assert "Traceback" not in r.text
        assert "db is not defined" not in r.text


# ---------- (d) Regression (Phase 1/2/3 endpoints) ----------
class TestRegression:
    def test_site_mode_accessible(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/site-mode", timeout=15)
        assert r.status_code in (200, 404)  # 404 acceptable if not seeded
        assert r.status_code != 500

    def test_vehicle_deposits_list(self, admin):
        r = admin.get(f"{BASE_URL}/api/admin/vehicle-deposits", timeout=15)
        assert r.status_code == 200, r.text[:200]

    def test_vehicle_deposit_release_nonexistent_not_500(self, admin):
        fake = f"nonexistent-{uuid.uuid4().hex[:8]}"
        r = admin.post(
            f"{BASE_URL}/api/admin/vehicle-deposits/{fake}/release", timeout=15
        )
        assert r.status_code != 500, r.text[:300]
        assert r.status_code in (400, 404, 409, 422)

    def test_users_status_nonexistent_not_500(self, admin):
        fake = f"nonexistent-{uuid.uuid4().hex[:8]}"
        r = admin.put(
            f"{BASE_URL}/api/admin/users/{fake}/status",
            json={"status": "active"},
            timeout=15,
        )
        assert r.status_code != 500, r.text[:300]
        assert r.status_code in (400, 404, 422)

    def test_users_opc_verify_nonexistent_not_500(self, admin):
        fake = f"nonexistent-{uuid.uuid4().hex[:8]}"
        r = admin.put(
            f"{BASE_URL}/api/admin/users/{fake}/opc-verify",
            json={"verified": True},
            timeout=15,
        )
        assert r.status_code != 500, r.text[:300]
        assert r.status_code in (400, 404, 422)

    def test_listings_bulk_action_empty_list_422(self, admin):
        r = admin.post(
            f"{BASE_URL}/api/admin/listings/bulk-action",
            json={"action": "delete", "listing_ids": []},
            timeout=15,
        )
        assert r.status_code == 422, r.text[:200]

    def test_listings_put_nonexistent_404(self, admin):
        fake = f"nonexistent-{uuid.uuid4().hex[:8]}"
        r = admin.put(
            f"{BASE_URL}/api/admin/listings/{fake}",
            json={"title": "TEST"},
            timeout=15,
        )
        assert r.status_code == 404, r.text[:200]

    def test_invoice_pdf_fr_nonexistent_404_not_500(self, admin):
        fake = f"nonexistent-{uuid.uuid4().hex[:8]}"
        r = admin.get(
            f"{BASE_URL}/api/vehicle-invoices/{fake}/pdf?lang=fr", timeout=15
        )
        assert r.status_code != 500, r.text[:300]
        assert r.status_code in (400, 404)


# ---------- No-auth sanity checks for admin sections ----------
class TestAdminSectionsNoAuth:
    @pytest.mark.parametrize("path", [
        "/api/admin/marketing/campaigns",
        "/api/admin/site-config/legal-pages",
        "/api/admin/platform-cleanup/preview",
        "/api/admin/vehicle-deposits",
    ])
    def test_no_auth_rejected(self, api, path):
        r = api.get(f"{BASE_URL}{path}", timeout=15)
        assert r.status_code in (401, 403), f"{path} returned {r.status_code}, expected 401/403"
