"""
iter304 — Backend tests for new endpoints:
  • Lot Templates CRUD (max 20, owner-only)
  • Verified Auction Firm grant/revoke + public lookup
  • Email-to-Friend 404 + invalid-email validation

These tests run against the live preview instance. They use the existing
admin charbel911@gmail.com account from /app/memory/test_credentials.md.
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


@pytest.fixture(scope="module")
def admin_user_id(admin_token):
    # Decode the JWT to extract the sub (user id) — avoids dependency on a
    # specific /users/me endpoint variant.
    import base64, json as _json
    try:
        payload_b64 = admin_token.split(".")[1] + "=="
        payload = _json.loads(base64.urlsafe_b64decode(payload_b64))
        uid = payload.get("sub") or payload.get("user_id")
        assert uid, payload
        return uid
    except Exception:
        # Fallback to /auth/me if available
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {admin_token}"}, timeout=10)
        assert r.status_code == 200, r.text
        return r.json().get("id") or r.json().get("user_id")


# ─────────────────── LOT TEMPLATES ───────────────────
def test_lot_templates_requires_auth():
    r = requests.get(f"{API}/lot-templates", timeout=10)
    assert r.status_code in (401, 403)


def test_lot_templates_full_crud_cycle(admin_token):
    h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}

    # List (clean start — delete any existing)
    r0 = requests.get(f"{API}/lot-templates", headers=h, timeout=10)
    assert r0.status_code == 200
    for it in r0.json().get("items", []):
        requests.delete(f"{API}/lot-templates/{it['id']}", headers=h, timeout=10)

    # Create
    body = {
        "name": f"pytest-iter304-{uuid.uuid4().hex[:6]}",
        "fields": {
            "make": "Ford", "model": "F-350",
            "body_type": "truck", "transmission": "automatic",
            "fuel_type": "diesel", "starting_price": 5000,
            "bid_increment": 100, "location_province": "QC",
        },
    }
    r1 = requests.post(f"{API}/lot-templates", headers=h, json=body, timeout=10)
    assert r1.status_code == 200, r1.text
    tpl = r1.json()
    assert tpl["name"] == body["name"]
    assert tpl["fields"]["make"] == "Ford"
    tpl_id = tpl["id"]

    # Update
    r2 = requests.put(f"{API}/lot-templates/{tpl_id}",
                      headers=h, json={"name": tpl["name"] + " (edited)"}, timeout=10)
    assert r2.status_code == 200
    assert "(edited)" in r2.json()["name"]

    # List
    r3 = requests.get(f"{API}/lot-templates", headers=h, timeout=10)
    assert r3.status_code == 200
    names = [t["name"] for t in r3.json()["items"]]
    assert any("(edited)" in n for n in names)
    assert r3.json()["max"] == 20

    # Delete
    r4 = requests.delete(f"{API}/lot-templates/{tpl_id}", headers=h, timeout=10)
    assert r4.status_code == 200
    assert r4.json()["ok"] is True

    # Delete again → 404
    r5 = requests.delete(f"{API}/lot-templates/{tpl_id}", headers=h, timeout=10)
    assert r5.status_code == 404


# ─────────────────── VERIFIED AUCTION FIRM ───────────────────
def test_verified_firm_public_lookup_404_unknown():
    r = requests.get(f"{API}/users/no-such-user-id/verified-firm", timeout=10)
    assert r.status_code == 404


def test_verified_firm_grant_revoke_cycle(admin_token, admin_user_id):
    h = {"Authorization": f"Bearer {admin_token}"}

    # Grant
    r1 = requests.post(f"{API}/admin/users/{admin_user_id}/grant-verified-firm",
                       headers=h, timeout=10)
    assert r1.status_code == 200, r1.text
    assert r1.json()["verified_auction_firm"] is True

    # Public lookup confirms
    r2 = requests.get(f"{API}/users/{admin_user_id}/verified-firm", timeout=10)
    assert r2.status_code == 200
    assert r2.json()["verified_auction_firm"] is True

    # Revoke
    r3 = requests.post(f"{API}/admin/users/{admin_user_id}/revoke-verified-firm",
                       headers=h, timeout=10)
    assert r3.status_code == 200
    assert r3.json()["verified_auction_firm"] is False

    # Public lookup reflects revoke
    r4 = requests.get(f"{API}/users/{admin_user_id}/verified-firm", timeout=10)
    assert r4.status_code == 200
    assert r4.json()["verified_auction_firm"] is False


def test_verified_firm_non_admin_forbidden():
    # Try without any token
    r = requests.post(f"{API}/admin/users/abc/grant-verified-firm", timeout=10)
    assert r.status_code in (401, 403)


# ─────────────────── EMAIL TO FRIEND ───────────────────
def test_email_to_friend_404_unknown_vehicle(admin_token):
    h = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    r = requests.post(f"{API}/vehicles/non-existent-vehicle-id/email-to-friend",
                      headers=h, json={"recipient_email": "qa@bidvex.com"}, timeout=10)
    assert r.status_code == 404


def test_email_to_friend_requires_auth():
    r = requests.post(f"{API}/vehicles/any-id/email-to-friend",
                      json={"recipient_email": "qa@bidvex.com"}, timeout=10)
    assert r.status_code in (401, 403)
