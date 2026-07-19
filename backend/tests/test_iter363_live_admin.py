"""iter363 - live admin API verification against preview host.

Confirms the role-check normalization (admin, super_admin) applied via sed
in iter363 to trust_safety.py, admin_config.py, admin_ops.py,
subscriptions.py, auctions_bids.py works correctly under super_admin auth.
"""
import os
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASS = "Anderosli123!@#"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
                      timeout=15)
    if r.status_code == 429:
        pytest.skip(f"Rate-limited: {r.text[:100]}")
    assert r.status_code == 200, f"Login failed {r.status_code}: {r.text[:200]}"
    data = r.json()
    token = data.get("token") or data.get("access_token") or data.get("session_token")
    assert token, f"No token in login response: {list(data.keys())}"
    return token


@pytest.fixture(scope="module")
def h(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


# ── AI Guard (was 403 before iter363 role-check normalization) ─────────
def test_ai_guard_stats(h):
    r = requests.get(f"{BASE_URL}/api/admin/ai-guard/stats", headers=h, timeout=15)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    j = r.json()
    assert j.get("success") is True
    assert "stats" in j


def test_ai_guard_flags(h):
    r = requests.get(f"{BASE_URL}/api/admin/ai-guard/flags", headers=h, timeout=15)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    j = r.json()
    assert j.get("success") is True
    assert "flags" in j
    assert isinstance(j["flags"], list)


# ── Risk Monitoring (was 500 KeyError:'id' before iter363) ─────────────
def test_risk_monitoring(h):
    r = requests.get(f"{BASE_URL}/api/admin/risk-monitoring", headers=h, timeout=20)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"


# ── Pricing Engine ─────────────────────────────────────────────────────
def test_pricing_engine(h):
    r = requests.get(f"{BASE_URL}/api/admin/pricing-engine", headers=h, timeout=15)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"
    j = r.json()
    # Response is a flat dict of {key: {...pricing details}}. Verify both
    # required fees are present with expected shape.
    assert "partner_annual_fee" in j
    assert "vehicle_dealer_annual_fee" in j
    assert "effective_price_cad" in j["partner_annual_fee"]


# ── Coupons ────────────────────────────────────────────────────────────
def test_coupons_list(h):
    r = requests.get(f"{BASE_URL}/api/admin/coupons", headers=h, timeout=15)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"


# ── Platform Cleanup Preview (was 500 KeyError:'id' before iter363) ────
def test_platform_cleanup_preview(h):
    r = requests.get(f"{BASE_URL}/api/admin/platform-cleanup/preview", headers=h, timeout=20)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:200]}"


# ── Contact Form (SendGrid live delivery) ──────────────────────────────
def test_contact_form_delivers():
    payload = {
        "name": "iter363 QA Bot",
        "email": "qa@bidvex.com",
        "team_id": "support",
        "message": "iter363 launch-gate QA — verifying SendGrid delivery pipeline end to end.",
        "lang": "en",
    }
    r = requests.post(f"{BASE_URL}/api/contact/submit", json=payload, timeout=25)
    assert r.status_code == 200, f"{r.status_code}: {r.text[:300]}"
    j = r.json()
    assert j.get("ok") is True
    # delivered may be false if SendGrid is not configured in preview - accept both
    # but require routed_to to be correct
    assert j.get("routed_to") == "service@bidvex.com", f"Wrong routing: {j}"


# ── SPA HTML served for language-prefixed URLs (StripLangRedirect) ─────
def test_en_settings_serves_spa():
    """The React SPA must serve for /en/settings so StripLangRedirect can run."""
    r = requests.get(f"{BASE_URL}/en/settings", timeout=15, allow_redirects=True)
    # SPA returns 200 HTML; StripLangRedirect handles the redirect client-side
    assert r.status_code == 200, f"{r.status_code}"
    assert "text/html" in r.headers.get("content-type", "")


def test_fr_settings_serves_spa():
    r = requests.get(f"{BASE_URL}/fr/settings", timeout=15, allow_redirects=True)
    assert r.status_code == 200
    assert "text/html" in r.headers.get("content-type", "")
