"""iter364 — Live HTTP tests against preview.

Covers:
- Hero phone assets served with 200 + PNG content-type
- /static/placeholder.png publicly accessible
- Admin notification summary auth-gated (401/403 without token, 200 with super_admin)
"""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") or "https://prod-verify-2.preview.emergentagent.com"
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PWD = "Anderosli123!@#"


@pytest.fixture(scope="session")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PWD},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"Admin login failed: {r.status_code} {r.text[:200]}")
    tok = r.json().get("access_token") or r.json().get("token")
    if not tok:
        pytest.skip(f"No token in login response: {r.json()}")
    return tok


# ── Hero assets ─────────────────────────────────────────────
@pytest.mark.parametrize("lang", ["en", "fr"])
def test_hero_phone_asset_200(lang):
    r = requests.get(f"{BASE_URL}/assets/hero-phone-{lang}.png", timeout=15)
    assert r.status_code == 200, f"hero-phone-{lang}.png returned {r.status_code}"
    assert r.headers.get("content-type", "").startswith("image/"), (
        f"expected image/*, got {r.headers.get('content-type')}"
    )
    assert len(r.content) > 100_000, f"asset < 100KB (got {len(r.content)})"


def test_placeholder_png_200():
    r = requests.get(f"{BASE_URL}/static/placeholder.png", timeout=15)
    assert r.status_code == 200, f"placeholder.png returned {r.status_code}"


# ── Admin notification summary ─────────────────────────────
def test_notification_summary_unauth_blocked():
    r = requests.get(f"{BASE_URL}/api/admin/notifications/summary", timeout=15)
    assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}: {r.text[:200]}"


def test_notification_summary_auth_ok(admin_token):
    r = requests.get(
        f"{BASE_URL}/api/admin/notifications/summary",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text[:200]}"
    data = r.json()
    # Expect numeric fields (4 categories + total or similar)
    numeric_fields = [k for k, v in data.items() if isinstance(v, (int, float))]
    assert len(numeric_fields) >= 4, (
        f"expected ≥4 numeric fields, got {numeric_fields}. payload={data}"
    )


def test_notification_summary_bad_token_blocked():
    r = requests.get(
        f"{BASE_URL}/api/admin/notifications/summary",
        headers={"Authorization": "Bearer invalid.token.here"},
        timeout=15,
    )
    assert r.status_code in (401, 403), f"expected 401/403, got {r.status_code}"
