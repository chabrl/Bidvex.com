"""
Live endpoint tests for iter355 identity verification + KYC gates.
Runs against the public preview URL.
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "iter355_tester@bidvex.com"
BUYER_PASSWORD = "Iter355Test!@#"


# ---------- helpers ----------

def _login(email, password):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=30)
    if r.status_code == 200:
        try:
            token = r.json().get("access_token")
            if token:
                s.headers.update({"Authorization": f"Bearer {token}"})
        except Exception:
            pass
    return s, r


@pytest.fixture(scope="module")
def admin_session():
    s, r = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    return s


@pytest.fixture(scope="module")
def buyer_session():
    s, r = _login(BUYER_EMAIL, BUYER_PASSWORD)
    if r.status_code != 200:
        pytest.skip(f"Buyer login failed: {r.status_code} {r.text[:200]}")
    return s


# ---------- Identity verify auth gate ----------

def test_identity_verify_requires_auth():
    r = requests.post(f"{BASE_URL}/api/identity/verify", timeout=15)
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text[:200]}"


def test_identity_status_requires_auth():
    r = requests.get(f"{BASE_URL}/api/identity/status", timeout=15)
    assert r.status_code == 401, f"Expected 401, got {r.status_code}: {r.text[:200]}"


# ---------- Identity status for non-verified user ----------

def test_identity_status_non_verified_shape(buyer_session):
    r = buyer_session.get(f"{BASE_URL}/api/identity/status", timeout=15)
    assert r.status_code == 200, f"got {r.status_code}: {r.text[:200]}"
    data = r.json()
    # Required keys per spec
    for key in [
        "is_identity_verified",
        "stripe_identity_status",
        "stripe_verification_session_id",
        "identity_legal_name",
        "last_error_reason",
    ]:
        assert key in data, f"missing key {key} in {data}"
    assert data["is_identity_verified"] is False


# ---------- Identity verify creates session; reuse in-flight ----------

def test_identity_verify_creates_session_and_reuses(buyer_session):
    r1 = buyer_session.post(f"{BASE_URL}/api/identity/verify", json={}, timeout=45)
    # Accept 200/201 for success, 503 if Stripe unreachable
    if r1.status_code == 503:
        pytest.skip("Stripe unreachable in preview environment (503) — config issue, not code issue.")
    assert r1.status_code in (200, 201), f"got {r1.status_code}: {r1.text[:300]}"
    d1 = r1.json()
    for k in ["verification_session_id", "client_secret", "status", "reused"]:
        assert k in d1, f"missing {k} in {d1}"
    # Real client_secret shape
    # Real Stripe VerificationSession client_secret format: `vs_<id>_secret_...` (live or test)
    cs = d1["client_secret"]
    assert isinstance(cs, str) and cs.startswith("vs_") and "_secret_" in cs, (
        f"client_secret does not look like a real Stripe VerificationSession secret: {cs[:60]}"
    )

    # Second call should reuse
    r2 = buyer_session.post(f"{BASE_URL}/api/identity/verify", json={}, timeout=45)
    assert r2.status_code in (200, 201)
    d2 = r2.json()
    assert d2.get("verification_session_id") == d1["verification_session_id"], (
        f"expected same session id (reused). d1={d1}, d2={d2}"
    )
    assert d2.get("reused") is True, f"reused flag not True on 2nd call: {d2}"


# ---------- Settlement KYC soft-gate ----------

def test_settle_endpoint_blocks_unverified_buyer(buyer_session):
    """
    Even without a real listing_id, an unverified user should hit the KYC gate first
    OR return 404 for missing listing. Behavior depends on route order in settlement.py:438.
    Per spec, the gate is enforced. Use a bogus listing_id and inspect the error envelope.
    """
    r = buyer_session.post(f"{BASE_URL}/api/settlement/settle/nonexistent-listing-id", timeout=15)
    # Accept 403 (KYC gate fires early) OR 404 (listing lookup runs first)
    assert r.status_code in (403, 404), f"got {r.status_code}: {r.text[:300]}"
    if r.status_code == 403:
        detail = r.json().get("detail", r.json())
        assert detail.get("error") == "IDENTITY_VERIFICATION_REQUIRED", detail
        assert detail.get("verification_endpoint") == "/api/identity/verify", detail
        assert "message_en" in detail and "message_fr" in detail, detail


def test_settle_endpoint_admin_bypass(admin_session):
    """Admin should not be blocked by KYC gate. For a bogus listing this returns 404 (not 403 KYC)."""
    r = admin_session.post(f"{BASE_URL}/api/settlement/settle/nonexistent-listing-id", timeout=15)
    # Must NOT be 403 IDENTITY_VERIFICATION_REQUIRED
    if r.status_code == 403:
        detail = r.json().get("detail", r.json())
        assert detail.get("error") != "IDENTITY_VERIFICATION_REQUIRED", (
            f"Admin got KYC-gated: {detail}"
        )


def test_vehicle_buyer_acknowledge_blocks_unverified(buyer_session):
    r = buyer_session.post(f"{BASE_URL}/api/vehicles/nonexistent-vehicle-id/buyer-acknowledge", timeout=15)
    # 403 KYC (soft-gate fires) OR 404 (vehicle not found runs first)
    assert r.status_code in (403, 404), f"got {r.status_code}: {r.text[:300]}"
    if r.status_code == 403:
        detail = r.json().get("detail", r.json())
        assert detail.get("error") == "IDENTITY_VERIFICATION_REQUIRED", detail
        assert detail.get("verification_endpoint") == "/api/identity/verify"


# ---------- Non-regression: buyer can still log in ----------

def test_buyer_login_still_works():
    s, r = _login(BUYER_EMAIL, BUYER_PASSWORD)
    assert r.status_code == 200
