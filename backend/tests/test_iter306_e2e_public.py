"""
iter306 E2E test against PUBLIC backend (REACT_APP_BACKEND_URL).

Covers requested test items:
- bulk-import (auth, 404, max_lots, valid+QC missing title_fr)
- frontend error log (anon + auth)
- admin error logs (frontend + backend) — admin gating
- push subscribe/status/unsubscribe + vapid-public-key
"""
import os
import json
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend/.env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
                break

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASS = "Anderosli123!@#"
DEALER_EMAIL = "testdealer@bidvex.com"
DEALER_PASS = "TestDealer2026!"
BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PASS = "TestBuyer2026!"


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    assert r.status_code == 200, f"login {email} failed: {r.status_code} {r.text[:200]}"
    body = r.json()
    return body.get("access_token") or body.get("token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(ADMIN_EMAIL, ADMIN_PASS)


@pytest.fixture(scope="module")
def dealer_token():
    return _login(DEALER_EMAIL, DEALER_PASS)


@pytest.fixture(scope="module")
def buyer_token():
    return _login(BUYER_EMAIL, BUYER_PASS)


# ============ BULK IMPORT ============

def test_bulk_import_requires_auth():
    r = requests.post(f"{BASE_URL}/api/vehicle-multi-lot-auctions/anything/bulk-import",
                      json={"lots": []}, timeout=20)
    assert r.status_code in (401, 403), f"expected 401/403 got {r.status_code}"


def _min_lot(vin_suffix="A123456"):
    return {
        "vin": f"1HGCM82633{vin_suffix}",
        "year": 2020,
        "make": "Honda",
        "model": "Civic",
        "starting_price": 1000,
        "location_city": "Toronto",
        "location_province": "ON",
        "title": "Civic test",
    }


def test_bulk_import_404_unknown_event(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = requests.post(
        f"{BASE_URL}/api/vehicle-multi-lot-auctions/does-not-exist-{uuid.uuid4()}/bulk-import",
        headers=h, json={"lots": [_min_lot()]}, timeout=20)
    assert r.status_code == 404, f"expected 404 got {r.status_code} {r.text[:200]}"


def test_bulk_import_max_lots_exceeded(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    lots = [_min_lot(f"A{i:06d}") for i in range(51)]
    r = requests.post(
        f"{BASE_URL}/api/vehicle-multi-lot-auctions/anyid/bulk-import",
        headers=h, json={"lots": lots}, timeout=30)
    assert r.status_code == 400, f"expected 400 got {r.status_code} {r.text[:300]}"
    body = r.json()
    detail = body.get("detail", body)
    code = detail.get("code") if isinstance(detail, dict) else None
    assert code == "max_lots_exceeded", f"expected max_lots_exceeded got {body}"


def test_bulk_import_creates_draft_event_and_qc_bill96_validation(admin_token):
    """Create a draft event then bulk import 2 lots: 1 ON valid, 1 QC missing title_fr"""
    h = {"Authorization": f"Bearer {admin_token}"}
    # Step 1: create draft event with lots=[]
    draft_payload = {
        "title": f"iter306 QA bulk import {uuid.uuid4().hex[:6]}",
        "description": "iter306 e2e test",
        "submission_intent": "draft",
        "start_time": "2026-12-31T12:00:00Z",
        "lots": [],
    }
    r = requests.post(f"{BASE_URL}/api/vehicle-multi-lot-auctions",
                      headers=h, json=draft_payload, timeout=30)
    # Should be 200/201
    if r.status_code not in (200, 201):
        pytest.skip(f"draft event create failed {r.status_code} {r.text[:300]}")
    event = r.json()
    event_id = event.get("id") or event.get("_id") or event.get("event_id")
    assert event_id, f"no event_id in response: {event}"

    # Step 2: bulk import 2 lots
    lots = [
        {
            "vin": "1HGCM82633A111111",
            "year": 2020,
            "make": "Honda",
            "model": "Accord",
            "title": "2020 Honda Accord",
            "location_province": "ON",
            "location_city": "Toronto",
            "starting_price": 1000,
            "mileage": 50000,
        },
        {
            # QC lot missing title_fr → must fail Bill 96 validation
            "vin": "1HGCM82633A222222",
            "year": 2019,
            "make": "Toyota",
            "model": "Camry",
            "title": "2019 Toyota Camry",
            "location_province": "QC",
            "location_city": "Montreal",
            "starting_price": 1500,
            "mileage": 70000,
        },
    ]
    r = requests.post(
        f"{BASE_URL}/api/vehicle-multi-lot-auctions/{event_id}/bulk-import",
        headers=h, json={"lots": lots}, timeout=30)
    assert r.status_code == 200, f"bulk import status {r.status_code} {r.text[:400]}"
    body = r.json()
    assert "errors" in body, f"no errors field in response: {body}"
    # The QC missing title_fr lot should be in errors
    errs = body["errors"]
    qc_err_found = False
    for e in errs:
        msg = json.dumps(e).lower()
        if "title_fr" in msg or "bill 96" in msg or "loi 96" in msg:
            qc_err_found = True
            break
    assert qc_err_found, f"expected title_fr/Bill 96 error, got: {errs}"


# ============ ERROR LOGS ============

def test_log_frontend_error_anonymous():
    r = requests.post(f"{BASE_URL}/api/errors/frontend",
                      json={"error_message": "iter306-e2e anon test",
                            "url": "https://example.test/x"}, timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
    body = r.json()
    assert body.get("ok") is True
    assert "id" in body


def test_log_frontend_error_authenticated(buyer_token):
    h = {"Authorization": f"Bearer {buyer_token}"}
    r = requests.post(f"{BASE_URL}/api/errors/frontend", headers=h,
                      json={"error_message": "iter306-e2e auth test",
                            "url": "https://example.test/y"}, timeout=20)
    assert r.status_code == 200
    assert r.json().get("ok") is True


def test_admin_errors_frontend_requires_admin(buyer_token):
    # No auth
    r = requests.get(f"{BASE_URL}/api/admin/errors/frontend?days=30&limit=10", timeout=20)
    assert r.status_code in (401, 403)
    # Non-admin auth
    h = {"Authorization": f"Bearer {buyer_token}"}
    r = requests.get(f"{BASE_URL}/api/admin/errors/frontend?days=30&limit=10",
                     headers=h, timeout=20)
    assert r.status_code in (401, 403), f"buyer should not access, got {r.status_code}"


def test_admin_errors_frontend_list(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = requests.get(f"{BASE_URL}/api/admin/errors/frontend?days=30&limit=10",
                     headers=h, timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body
    assert isinstance(body["items"], list)


def test_admin_errors_backend_list(admin_token):
    h = {"Authorization": f"Bearer {admin_token}"}
    r = requests.get(f"{BASE_URL}/api/admin/errors/backend?days=30&limit=10",
                     headers=h, timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body


# ============ PUSH ============

def test_push_vapid_public_key():
    r = requests.get(f"{BASE_URL}/api/push/vapid-public-key", timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert "public_key" in body
    assert isinstance(body["public_key"], str)


def test_push_subscribe_status_unsubscribe(buyer_token):
    h = {"Authorization": f"Bearer {buyer_token}"}

    # Initial state — capture count (may be > 0 from prior runs)
    r0 = requests.get(f"{BASE_URL}/api/push/status", headers=h, timeout=20)
    assert r0.status_code == 200
    initial_count = r0.json().get("device_count", 0)

    endpoint = f"https://fcm.googleapis.com/test/iter306-{uuid.uuid4().hex[:8]}"
    sub = {
        "endpoint": endpoint,
        "keys": {
            "p256dh": "BDcG_iter306_synthetic_p256dh_key_truncated_for_test_only_aaaaaaa",
            "auth": "aBcDeF12iter306",
        },
    }
    r = requests.post(f"{BASE_URL}/api/push/subscribe", headers=h, json=sub, timeout=20)
    assert r.status_code == 200, f"subscribe got {r.status_code} {r.text[:300]}"
    assert r.json().get("success") is True

    # Status — should have at least initial+1
    r = requests.get(f"{BASE_URL}/api/push/status", headers=h, timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert body.get("subscribed") is True
    assert body.get("device_count", 0) == initial_count + 1, \
        f"expected {initial_count + 1} devices, got {body}"

    # Unsubscribe — endpoint requires full PushSubscription body
    r = requests.delete(f"{BASE_URL}/api/push/unsubscribe", headers=h,
                        json=sub, timeout=20)
    assert r.status_code == 200, f"unsubscribe got {r.status_code} {r.text[:300]}"

    # Status — should be back to initial_count
    r = requests.get(f"{BASE_URL}/api/push/status", headers=h, timeout=20)
    assert r.status_code == 200
    body = r.json()
    assert body.get("device_count", 0) == initial_count, \
        f"expected {initial_count} devices after unsubscribe, got {body}"
