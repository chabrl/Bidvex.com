"""
Live HTTP integration tests for Feature Patch v9 — relies on seeded listings
to bypass payment-method / dealer-license gates on POST /api/listings.

Listings are seeded directly into MongoDB by the seed script in iteration 201.
"""
import os
from datetime import datetime, timedelta, timezone

import pytest
import requests

with open("/app/frontend/.env") as fh:
    for line in fh:
        if line.startswith("REACT_APP_BACKEND_URL"):
            BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
            break

ADMIN = ("charbel911@gmail.com", "Anderosli123!@#")
BUYER = ("v9test_1779311352@bidvex.com", "TestBuyer123!")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"login failed: {email} {r.status_code}")
    j = r.json()
    return j.get("access_token") or j.get("token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def buyer_token():
    return _login(*BUYER)


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# These IDs were seeded in MongoDB before this run.
SEEDED = {
    "endtime":  "TEST_V9_endtime_c849efd4",
    "flag":     "TEST_V9_flag_e39bd5df",
    "approve":  "TEST_V9_approve_3d1174a4",
    "reject":   "TEST_V9_reject_a3bfdf13",
    "correct":  "TEST_V9_correct_b6187344",
    "withdraw": "TEST_V9_withdraw_f62537c6",
}


@pytest.fixture(scope="module", autouse=True)
def discover_seeded():
    """No-op: SEEDED has hardcoded IDs from the iteration-201 seed."""
    yield


# ── Feature 1: admin end-time edit + history ──────────────────────────

def test_admin_update_end_time_success(admin_token):
    lid = SEEDED["endtime"]
    assert lid, "endtime listing not seeded"
    new_end = (datetime.now(timezone.utc) + timedelta(days=12)).isoformat()
    r = requests.patch(
        f"{BASE_URL}/api/admin/auctions/{lid}/end-time",
        json={"new_end_time": new_end, "reason": "v9 extension"},
        headers=_h(admin_token), timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"


def test_admin_update_end_time_rejects_past(admin_token):
    lid = SEEDED["endtime"]
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r = requests.patch(
        f"{BASE_URL}/api/admin/auctions/{lid}/end-time",
        json={"new_end_time": past, "reason": "bad"},
        headers=_h(admin_token), timeout=20)
    assert r.status_code in (400, 422), r.status_code


def test_admin_end_time_history(admin_token):
    lid = SEEDED["endtime"]
    r = requests.get(
        f"{BASE_URL}/api/admin/auctions/{lid}/end-time-history",
        headers=_h(admin_token), timeout=20)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    items = body if isinstance(body, list) else body.get("history") or body.get("items") or []
    assert len(items) >= 1


def test_non_admin_cannot_update_end_time(buyer_token):
    lid = SEEDED["endtime"]
    new_end = (datetime.now(timezone.utc) + timedelta(days=20)).isoformat()
    r = requests.patch(
        f"{BASE_URL}/api/admin/auctions/{lid}/end-time",
        json={"new_end_time": new_end, "reason": "unauthorized"},
        headers=_h(buyer_token), timeout=20)
    assert r.status_code in (401, 403)


# ── Feature 3: full AI-review lifecycle on seeded listings ─────────────

def _flag(buyer_token, lid):
    return requests.post(
        f"{BASE_URL}/api/listings/{lid}/flag-for-ai-review",
        json={"suggested_category": "Vehicles",
              "seller_category": "Furniture",
              "ai_reason_en": "title contains truck",
              "ai_reason_fr": "le titre contient camion",
              "listing_type": "single"},
        headers=_h(buyer_token), timeout=20)


def test_flag_for_ai_review_sets_pending(buyer_token):
    lid = SEEDED["flag"]
    r = _flag(buyer_token, lid)
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    g = requests.get(f"{BASE_URL}/api/listings/{lid}", timeout=20).json()
    assert g.get("status") == "pending_ai_review"


def test_admin_queue_lists_pending(admin_token, buyer_token):
    # ensure at least one pending exists
    _flag(buyer_token, SEEDED["flag"])
    r = requests.get(f"{BASE_URL}/api/admin/listing-reviews?status=pending",
                     headers=_h(admin_token), timeout=20)
    assert r.status_code == 200
    body = r.json()
    items = body if isinstance(body, list) else body.get("rows") or body.get("reviews") or body.get("items") or []

    assert len(items) >= 1

def test_admin_approve_restores_listing(admin_token, buyer_token):
    lid = SEEDED["approve"]
    f = _flag(buyer_token, lid)
    assert f.status_code == 200, f.text[:200]
    rid = f.json().get("review_id")
    a = requests.post(
        f"{BASE_URL}/api/admin/listing-reviews/{rid}/approve",
        json={}, headers=_h(admin_token), timeout=20)
    assert a.status_code == 200, f"{a.status_code} {a.text[:300]}"
    g = requests.get(f"{BASE_URL}/api/listings/{lid}", timeout=20).json()
    assert g.get("status") != "pending_ai_review"


def test_admin_reject_marks_rejected(admin_token, buyer_token):
    lid = SEEDED["reject"]
    f = _flag(buyer_token, lid)
    rid = f.json().get("review_id")
    a = requests.post(
        f"{BASE_URL}/api/admin/listing-reviews/{rid}/reject",
        json={"admin_note": "v9 rejection test"},
        headers=_h(admin_token), timeout=20)
    assert a.status_code == 200, f"{a.status_code} {a.text[:300]}"
    g = requests.get(f"{BASE_URL}/api/listings/{lid}", timeout=20).json()
    assert g.get("status") == "rejected"


def test_seller_correct_category(buyer_token):
    lid = SEEDED["correct"]
    _flag(buyer_token, lid)
    r = requests.post(f"{BASE_URL}/api/listings/{lid}/correct-category",
                      json={"new_category": "Vehicles", "listing_type": "single"},
                      headers=_h(buyer_token), timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    g = requests.get(f"{BASE_URL}/api/listings/{lid}", timeout=20).json()
    assert g.get("status") != "pending_ai_review"


def test_seller_withdraw_from_review(buyer_token):
    lid = SEEDED["withdraw"]
    _flag(buyer_token, lid)
    r = requests.post(
        f"{BASE_URL}/api/listings/{lid}/withdraw-from-review?listing_type=single",
        json={}, headers=_h(buyer_token), timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    g = requests.get(f"{BASE_URL}/api/listings/{lid}", timeout=20).json()
    assert g.get("status") == "withdrawn"


# ── Feature 3: suggest-category heuristic (already verified) ──────────

def test_suggest_category_mismatch(buyer_token):
    r = requests.post(f"{BASE_URL}/api/listings/suggest-category",
                      json={"title": "Ford F-150 truck",
                            "description": "2019 truck low miles",
                            "seller_category": "Furniture"},
                      headers=_h(buyer_token), timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert d.get("match") is False
    assert d.get("suggested_category") == "Vehicles"
    assert d.get("reason_en") and d.get("reason_fr")


def test_suggest_category_match(buyer_token):
    r = requests.post(f"{BASE_URL}/api/listings/suggest-category",
                      json={"title": "Oak dining table",
                            "description": "Solid oak, 6 seats",
                            "seller_category": "Furniture"},
                      headers=_h(buyer_token), timeout=20)
    assert r.status_code == 200
    assert r.json().get("match") is True
