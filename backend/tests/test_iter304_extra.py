"""
iter304 — Extended tests:
  • Lot Templates max-20 enforcement (POST 21st must return 400 max_templates_reached)
  • Email-to-Friend invalid email format → 400
"""
import os
import uuid
import pytest
import requests

BASE_URL = (os.environ.get("REACT_APP_BACKEND_URL") or "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{API}/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


def _clear_templates(headers):
    r = requests.get(f"{API}/lot-templates", headers=headers, timeout=15)
    if r.status_code == 200:
        for it in r.json().get("items", []):
            requests.delete(f"{API}/lot-templates/{it['id']}", headers=headers, timeout=10)


def test_lot_templates_max_20_enforcement(admin_token):
    h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    _clear_templates(h)

    created_ids = []
    try:
        for i in range(20):
            body = {
                "name": f"pytest-cap-{i}-{uuid.uuid4().hex[:4]}",
                "fields": {"make": "Ford", "model": "F-150"},
            }
            r = requests.post(f"{API}/lot-templates", headers=h, json=body, timeout=10)
            assert r.status_code == 200, f"failed at #{i}: {r.text}"
            created_ids.append(r.json()["id"])

        # 21st must fail
        r21 = requests.post(
            f"{API}/lot-templates",
            headers=h,
            json={"name": "pytest-cap-21", "fields": {}},
            timeout=10,
        )
        assert r21.status_code == 400, r21.text
        detail = r21.json().get("detail")
        # detail can be a dict {"code": "max_templates_reached"} or a string
        if isinstance(detail, dict):
            assert detail.get("code") == "max_templates_reached"
        else:
            assert "max" in str(detail).lower() or "20" in str(detail)
    finally:
        # cleanup
        for tid in created_ids:
            requests.delete(f"{API}/lot-templates/{tid}", headers=h, timeout=10)


def test_email_to_friend_invalid_email_format(admin_token):
    h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    # Use a real-looking-but-invalid format; payload has min_length=3
    r = requests.post(
        f"{API}/vehicles/some-fake-id/email-to-friend",
        headers=h,
        json={"recipient_email": "not-an-email"},
        timeout=10,
    )
    # 400 from custom validator (before 404 lookup)
    assert r.status_code == 400, r.text
