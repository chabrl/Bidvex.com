"""iter316-C live E2E smoke tests against preview backend.

Verifies:
  - Admin can POST /api/twilio/admin/contractors → invite_token returned
  - GET /api/twilio/admin/contractors now lists the new contractor
  - GET /api/twilio/admin/contractors/{id}/profile returns profile object
  - GET /api/twilio/calls?agent_user_id=X works for admin
  - Non-admin (testbuyer) blocked (403) on:
      GET /api/twilio/admin/contractors
      POST /api/twilio/admin/contractors
      GET /api/twilio/admin/contractors/{id}/profile
      GET /api/twilio/calls?agent_user_id=X
  - Promote-then-demote round-trip on testbuyer (then clean up).
"""
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PWD = "Anderosli123!@#"
BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PWD = "TestBuyer2026!"


def _login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=20)
    assert r.status_code == 200, f"Login failed for {email}: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PWD)


@pytest.fixture(scope="module")
def buyer_token():
    return _login(BUYER_EMAIL, BUYER_PWD)


@pytest.fixture(scope="module")
def buyer_user_id(buyer_token):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers={"Authorization": f"Bearer {buyer_token}"}, timeout=20)
    assert r.status_code == 200
    return r.json()["id"]


def _hdr(t):
    return {"Authorization": f"Bearer {t}", "Content-Type": "application/json"}


# ─────────────── Admin happy paths ───────────────
def test_admin_creates_new_contractor(admin_token):
    email = f"itc-e2e-{uuid.uuid4().hex[:8]}@bidvex.test"
    payload = {"email": email, "full_name": "E2E Contractor", "phone": "+14155550111",
               "province": "QC", "default_commission_rate": 0.22}
    r = requests.post(f"{BASE_URL}/api/twilio/admin/contractors", json=payload, headers=_hdr(admin_token), timeout=20)
    assert r.status_code in (200, 201), r.text
    data = r.json()
    assert "invite_token" in data or "invite_link" in data or "user_id" in data, f"unexpected body: {data}"
    contractor_id = data.get("user_id") or data.get("id") or data.get("contractor_id")
    assert contractor_id, f"no contractor id in {data}"
    # GET list — must include it
    lst = requests.get(f"{BASE_URL}/api/twilio/admin/contractors", headers=_hdr(admin_token), timeout=20)
    assert lst.status_code == 200
    ids = [c.get("id") or c.get("user_id") for c in lst.json().get("items", [])]
    assert contractor_id in ids, f"new contractor {contractor_id} not in list: {ids}"
    # store globally so the demote test can clean up
    pytest._created_contractor_id = contractor_id


def test_admin_profile_drill_in(admin_token):
    cid = getattr(pytest, "_created_contractor_id", None)
    if not cid:
        pytest.skip("no contractor created in previous test")
    r = requests.get(f"{BASE_URL}/api/twilio/admin/contractors/{cid}/profile", headers=_hdr(admin_token), timeout=20)
    assert r.status_code == 200, r.text
    body = r.json()
    # Profile must expose contractor identity + snapshot counters
    assert "contractor" in body, body.keys()
    assert "calls_total" in body or "ai_summary" in body
    assert "commission_history" in body or "earnings" in body


def test_admin_calls_filter_by_agent_user_id(admin_token, buyer_user_id):
    r = requests.get(f"{BASE_URL}/api/twilio/calls?agent_user_id={buyer_user_id}",
                     headers=_hdr(admin_token), timeout=20)
    assert r.status_code == 200, r.text
    assert isinstance(r.json().get("items", r.json()), (list, dict))


# ─────────────── Negative paths ───────────────
def test_non_admin_blocked_from_list(buyer_token):
    r = requests.get(f"{BASE_URL}/api/twilio/admin/contractors", headers=_hdr(buyer_token), timeout=20)
    assert r.status_code == 403, r.text


def test_non_admin_blocked_from_create(buyer_token):
    r = requests.post(f"{BASE_URL}/api/twilio/admin/contractors",
                      json={"email": "x@y.com", "full_name": "X"}, headers=_hdr(buyer_token), timeout=20)
    assert r.status_code == 403, r.text


def test_non_admin_blocked_from_profile(buyer_token):
    r = requests.get(f"{BASE_URL}/api/twilio/admin/contractors/0442f96d-f54d-41fe-afb1-fe3085c7840d/profile",
                     headers=_hdr(buyer_token), timeout=20)
    assert r.status_code == 403, r.text


def test_non_admin_blocked_from_calls_filter(buyer_token, buyer_user_id):
    r = requests.get(f"{BASE_URL}/api/twilio/calls?agent_user_id={buyer_user_id}",
                     headers=_hdr(buyer_token), timeout=20)
    assert r.status_code == 403, r.text


# ─────────────── Promote / demote round-trip ───────────────
def test_promote_then_demote_round_trip(admin_token, buyer_user_id):
    # Promote
    r = requests.post(f"{BASE_URL}/api/twilio/admin/users/{buyer_user_id}/promote-to-contractor",
                      json={}, headers=_hdr(admin_token), timeout=20)
    assert r.status_code in (200, 201), r.text
    # Verify it's now in the list
    lst = requests.get(f"{BASE_URL}/api/twilio/admin/contractors", headers=_hdr(admin_token), timeout=20).json()
    ids = [c.get("id") or c.get("user_id") for c in lst.get("items", [])]
    assert buyer_user_id in ids, f"buyer {buyer_user_id} not in contractor list after promote: {ids}"
    # Demote
    r = requests.post(f"{BASE_URL}/api/twilio/admin/users/{buyer_user_id}/demote-from-contractor",
                      json={}, headers=_hdr(admin_token), timeout=20)
    assert r.status_code in (200, 204), r.text
    lst2 = requests.get(f"{BASE_URL}/api/twilio/admin/contractors", headers=_hdr(admin_token), timeout=20).json()
    ids2 = [c.get("id") or c.get("user_id") for c in lst2.get("items", [])]
    assert buyer_user_id not in ids2


# ─────────────── Cleanup: demote any contractor we created ───────────────
def test_zzz_cleanup_created_contractor(admin_token):
    cid = getattr(pytest, "_created_contractor_id", None)
    if not cid:
        pytest.skip("nothing to clean up")
    r = requests.post(f"{BASE_URL}/api/twilio/admin/users/{cid}/demote-from-contractor",
                      json={}, headers=_hdr(admin_token), timeout=20)
    # We accept 200/204/404 (already removed)
    assert r.status_code in (200, 204, 404), r.text
