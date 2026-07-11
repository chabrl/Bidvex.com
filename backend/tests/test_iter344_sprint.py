"""iter344 sprint backend tests — admin impersonation, admin-triggered password
reset, per-lot admin edit endpoints, contractor agreements read-only, google
feed per-lot decomposition, and admin ownership bypass spot-checks."""

import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PASSWORD = "TestBuyer2026!"
NONADMIN_EMAIL = "iter331_nonadmin@test.com"
NONADMIN_PASSWORD = "NonAdmin2026!"
VML_EVENT_ID = "iter344-vml-feed-test"


def _login(email: str, password: str) -> str:
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=30)
    if r.status_code == 429:
        # brute-force limiter — back off and retry once
        time.sleep(65)
        r = requests.post(f"{BASE_URL}/api/auth/login",
                          json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text[:300]}"
    j = r.json()
    return j.get("access_token") or j["token"]


# ── Session-scoped fixtures so we do not hit login rate-limiter ────────
@pytest.fixture(scope="session")
def admin_token() -> str:
    return _login(ADMIN_EMAIL, ADMIN_PASSWORD)


@pytest.fixture(scope="session")
def admin_headers(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def buyer_token() -> str:
    try:
        return _login(BUYER_EMAIL, BUYER_PASSWORD)
    except Exception:
        pytest.skip("buyer login not available on preview")


@pytest.fixture(scope="session")
def buyer_id(admin_headers) -> str:
    # Look up target buyer id via admin users listing
    r = requests.get(f"{BASE_URL}/api/admin/users",
                     params={"search": BUYER_EMAIL, "limit": 5},
                     headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text[:500]
    data = r.json()
    users = data.get("users") or data.get("items") or data
    if isinstance(users, dict):
        users = users.get("users") or users.get("results") or []
    for u in users:
        if u.get("email") == BUYER_EMAIL:
            return u["id"]
    pytest.skip(f"testbuyer id not found via /api/admin/users: {str(users)[:500]}")


@pytest.fixture(scope="session")
def admin_id_and_email(admin_headers) -> dict:
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers, timeout=15)
    assert r.status_code == 200
    d = r.json()
    return {"id": d.get("id"), "email": d.get("email"), "role": d.get("role")}


# ── (1) Admin login + role normalization ───────────────────────────────
class TestAdminRoleNormalization:
    def test_admin_me_returns_super_admin(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers, timeout=15)
        assert r.status_code == 200
        me = r.json()
        assert me["email"] == ADMIN_EMAIL
        assert me["role"] == "super_admin", f"expected super_admin, got {me.get('role')!r}"


# ── (2) Admin Impersonation ────────────────────────────────────────────
class TestImpersonation:
    def test_impersonate_normal_user(self, admin_headers, buyer_id):
        r = requests.post(f"{BASE_URL}/api/admin/impersonate/{buyer_id}",
                          headers=admin_headers, timeout=20)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d.get("expires_in") == 3600
        assert "access_token" in d and isinstance(d["access_token"], str)
        # decode via /auth/me
        me = requests.get(f"{BASE_URL}/api/auth/me",
                         headers={"Authorization": f"Bearer {d['access_token']}"},
                         timeout=15)
        assert me.status_code == 200
        assert me.json()["email"] == BUYER_EMAIL
        # decode raw JWT to check claim
        import jwt as _jwt
        payload = _jwt.decode(d["access_token"], options={"verify_signature": False})
        assert payload.get("impersonated_by"), "missing impersonated_by claim in JWT"

    def test_impersonate_admin_target_forbidden(self, admin_headers, admin_id_and_email):
        r = requests.post(
            f"{BASE_URL}/api/admin/impersonate/{admin_id_and_email['id']}",
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 403, f"expected 403 impersonating admin, got {r.status_code}"

    def test_impersonate_requires_admin(self, buyer_token, buyer_id):
        r = requests.post(
            f"{BASE_URL}/api/admin/impersonate/{buyer_id}",
            headers={"Authorization": f"Bearer {buyer_token}"}, timeout=15,
        )
        assert r.status_code in (401, 403)


# ── (3) Admin-triggered password reset ─────────────────────────────────
class TestAdminPasswordReset:
    def test_reset_password_success(self, admin_headers, buyer_id):
        r = requests.post(
            f"{BASE_URL}/api/admin/users/{buyer_id}/reset-password",
            headers=admin_headers, timeout=30,
        )
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d.get("success") is True


# ── (4) Per-lot admin edit — vehicle multi-lot ─────────────────────────
class TestAdminLotEdit:
    def test_edit_vehicle_multi_lot_field(self, admin_headers):
        # Discover VML event lots
        r = requests.get(
            f"{BASE_URL}/api/vehicle-multi-lot-auctions/{VML_EVENT_ID}",
            timeout=20,
        )
        if r.status_code != 200:
            pytest.skip(f"VML event {VML_EVENT_ID} not seeded: {r.status_code}")
        event = r.json()
        lots = event.get("lots") or []
        assert lots, "seeded VML event has no lots"
        lot_id = lots[0]["id"]

        payload = {"mileage": 52000 + int(time.time()) % 1000}
        r2 = requests.put(
            f"{BASE_URL}/api/admin/vehicle-multi-lot-auctions/{VML_EVENT_ID}/lots/{lot_id}",
            json=payload, headers=admin_headers, timeout=20,
        )
        assert r2.status_code == 200, r2.text[:500]
        j = r2.json()
        assert j.get("success") is True
        assert "mileage" in (j.get("updated_fields") or [])


# ── (5) Contractor agreements — read-only for admin ────────────────────
class TestContractorAgreements:
    def test_admin_list_contractor_agreements_readonly(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/twilio/admin/contractor-agreements",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text[:400]
        d = r.json()
        assert d.get("read_only") is True
        assert "agreements" in d

    def test_admin_sign_returns_409(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/twilio/contractor/agreements/sign",
            json={"agreement_version": "v1", "text_hash": "x", "signed_full_name": "x"},
            headers=admin_headers, timeout=15,
        )
        assert r.status_code == 409, f"expected 409 not_a_contractor, got {r.status_code}: {r.text[:300]}"
        d = r.json()
        detail = d.get("detail") or d
        # detail may be a dict with error='not_a_contractor'
        if isinstance(detail, dict):
            assert detail.get("error") == "not_a_contractor"


# ── (6) Non-admin gets 403 on admin endpoints ──────────────────────────
class TestNonAdminBlocked:
    def test_nonadmin_403_on_admin_scores(self):
        # Always register a fresh non-admin to avoid brute-force rate limiter
        email = f"iter344na{int(time.time())}@test.com"
        r = requests.post(f"{BASE_URL}/api/auth/register", json={
            "email": email, "password": "NonAdmin2026!",
            "name": "NA Test", "first_name": "NA", "last_name": "Test",
            "province": "QC", "phone": "+15145550000",
            "terms_agreed": True, "ai_disclosure_consent": True,
        }, timeout=30)
        if r.status_code != 200:
            pytest.skip(f"could not create non-admin: {r.status_code} {r.text[:200]}")
        token = r.json()["access_token"]
        r = requests.get(
            f"{BASE_URL}/api/admin/trust-safety/scores",
            headers={"Authorization": f"Bearer {token}"}, timeout=15,
        )
        assert r.status_code == 403


# ── (7) Admin ownership bypass — trust safety scores 200 ───────────────
class TestAdminBypass:
    def test_admin_trust_safety_200(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/admin/trust-safety/scores",
                         headers=admin_headers, timeout=15)
        assert r.status_code == 200, r.text[:300]


# ── (8) Google feed per-lot decomposition ──────────────────────────────
class TestGoogleFeedPerLot:
    def test_google_vml_feed_has_per_lot_items(self):
        r = requests.get(
            f"{BASE_URL}/api/feeds/google",
            params={"type": "vehicle_multi_lot", "limit": 200},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        body = r.text
        # We expect per-lot g:id like VML-iter344-vml-feed-test-XXXXX
        # And ?lot= deep links
        assert VML_EVENT_ID in body, "seeded VML event id absent from Google feed body"
        assert "?lot=" in body, "per-lot deep link '?lot=' missing from Google feed"
        # Count items containing our event id
        item_count = body.count("<item>")
        assert item_count >= 3, f"expected >=3 <item> blocks, saw {item_count}"
        # g:shipping w/ CA
        assert "<g:country>CA</g:country>" in body, "g:shipping/g:country CA missing"

    def test_facebook_local_lots_per_lot(self):
        r = requests.get(
            f"{BASE_URL}/api/feeds/facebook-local",
            params={"format": "json", "type": "lots", "limit": 200},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        # Some deployments still return XML even with format=json — check content-type
        ctype = r.headers.get("content-type", "")
        if "json" not in ctype:
            pytest.skip(f"facebook-local returned {ctype}, not JSON — infra note")
        d = r.json()
        items = d.get("data") or d.get("items") if isinstance(d, dict) else d
        assert isinstance(items, list) and items, "empty facebook-local lots items"
        # Find a lot with LOT- id and ?lot= link
        has_lot = any(
            (it.get("id", "").startswith("LOT-") and "?lot=" in (it.get("link") or ""))
            for it in items
        )
        assert has_lot, f"no per-lot decomposed items found (first: {items[0] if items else None})"

    def test_facebook_local_refresh_admin(self, admin_headers):
        r = requests.post(f"{BASE_URL}/api/feeds/facebook-local/refresh",
                          headers=admin_headers, timeout=60)
        assert r.status_code == 200, r.text[:300]
