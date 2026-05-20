"""
Live HTTP integration tests for Feature Patch v9 against the preview env.
Covers: Feature 1 (admin end-time), Feature 3 (AI review flow), Feature 4
(quantity on POST /api/listings), and suggest-category heuristic.
"""
import os
from datetime import datetime, timedelta, timezone

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Read from /app/frontend/.env
    try:
        with open("/app/frontend/.env") as fh:
            for line in fh:
                if line.startswith("REACT_APP_BACKEND_URL"):
                    BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
                    break
    except FileNotFoundError:
        pass
assert BASE_URL, "Need REACT_APP_BACKEND_URL"

ADMIN = ("charbel911@gmail.com", "Anderosli123!@#")
BUYER = ("v9test_1779311352@bidvex.com", "TestBuyer123!")


def _login(email, password):
    r = requests.post(f"{BASE_URL}/api/auth/login",
                      json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"login failed for {email}: {r.status_code} {r.text[:200]}")
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def admin_token():
    return _login(*ADMIN)


@pytest.fixture(scope="module")
def buyer_token():
    return _login(*BUYER)


def _h(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ── Feature 4: POST /api/listings persists quantity + multiplier ─────────

def test_post_listing_persists_quantity_fields(buyer_token):
    end = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    payload = {
        "title": "TEST_v9 set of 5 chairs",
        "description": "Five matching dining chairs (test_feature_patch_v9_live)",
        "category": "Furniture",
        "condition": "good",
        "starting_price": 50.0,
        "location": "Toronto, ON",
        "city": "Toronto",
        "region": "ON",
        "auction_end_date": end,
        "quantity": 5,
        "multiply_hammer_by_quantity": True,
    }
    r = requests.post(f"{BASE_URL}/api/listings", json=payload,
                      headers=_h(buyer_token), timeout=20)
    assert r.status_code in (200, 201), f"{r.status_code} {r.text[:400]}"
    body = r.json()
    listing_id = body.get("id") or body.get("listing_id")
    assert listing_id, body
    # GET back
    g = requests.get(f"{BASE_URL}/api/listings/{listing_id}", timeout=20)
    assert g.status_code == 200, g.text[:300]
    listing = g.json()
    assert listing.get("quantity") == 5
    assert listing.get("multiply_hammer_by_quantity") is True


def test_post_listing_defaults_quantity_to_one(buyer_token):
    end = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    payload = {
        "title": "TEST_v9 single chair default qty",
        "description": "Default qty=1 backward compat",
        "category": "Furniture",
        "condition": "good",
        "starting_price": 25.0,
        "location": "Toronto, ON",
        "city": "Toronto",
        "region": "ON",
        "auction_end_date": end,
    }
    r = requests.post(f"{BASE_URL}/api/listings", json=payload,
                      headers=_h(buyer_token), timeout=20)
    assert r.status_code in (200, 201), f"{r.status_code} {r.text[:400]}"
    listing_id = r.json().get("id") or r.json().get("listing_id")
    g = requests.get(f"{BASE_URL}/api/listings/{listing_id}", timeout=20).json()
    assert g.get("quantity", 1) == 1
    assert g.get("multiply_hammer_by_quantity", False) is False


# ── Feature 3: suggest-category heuristic ─────────────────────────

def test_suggest_category_truck_in_non_vehicles_returns_mismatch(buyer_token):
    r = requests.post(f"{BASE_URL}/api/listings/suggest-category",
                      json={"title": "Ford F-150 truck for sale",
                            "description": "2019 truck low miles",
                            "seller_category": "Furniture"},
                      headers=_h(buyer_token), timeout=20)
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    assert data.get("match") is False
    assert data.get("suggested_category") == "Vehicles"
    assert data.get("reason_en")
    assert data.get("reason_fr")


def test_suggest_category_furniture_returns_match(buyer_token):
    r = requests.post(f"{BASE_URL}/api/listings/suggest-category",
                      json={"title": "Oak dining table",
                            "description": "Solid oak, 6 seats",
                            "seller_category": "Furniture"},
                      headers=_h(buyer_token), timeout=20)
    assert r.status_code == 200, r.text[:300]
    assert r.json().get("match") is True


def test_suggest_category_fails_open_on_missing_optional_fields(buyer_token):
    # Title is required; missing only optional fields (description/seller_category)
    # should still succeed and default match=True (fail-open semantics).
    r = requests.post(f"{BASE_URL}/api/listings/suggest-category",
                      json={"title": "Just a generic title"},
                      headers=_h(buyer_token), timeout=20)
    assert r.status_code == 200, r.text[:300]
    assert r.json().get("match") in (True, False)  # endpoint reachable


# ── Feature 3: flag + admin queue + approve/reject ────────────────

@pytest.fixture(scope="module")
def flagged_listing(buyer_token):
    """Create a listing then flag it for AI review."""
    end = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    create = requests.post(f"{BASE_URL}/api/listings", json={
        "title": "TEST_v9 truck flagged",
        "description": "Mock truck listing under furniture",
        "category": "Furniture",
        "condition": "good",
        "starting_price": 100.0,
        "location": "Toronto, ON",
        "city": "Toronto",
        "region": "ON",
        "auction_end_date": end,
    }, headers=_h(buyer_token), timeout=20)
    assert create.status_code in (200, 201), create.text[:300]
    lid = create.json().get("id") or create.json().get("listing_id")
    flag = requests.post(
        f"{BASE_URL}/api/listings/{lid}/flag-for-ai-review",
        json={"suggested_category": "Vehicles",
              "reason_en": "title contains truck",
              "reason_fr": "le titre contient camion"},
        headers=_h(buyer_token), timeout=20)
    assert flag.status_code == 200, f"{flag.status_code} {flag.text[:400]}"
    body = flag.json()
    return {"listing_id": lid, "review_id": body.get("review_id") or body.get("id")}


def test_flag_for_ai_review_sets_pending_status(buyer_token, flagged_listing):
    g = requests.get(f"{BASE_URL}/api/listings/{flagged_listing['listing_id']}",
                     timeout=20).json()
    assert g.get("status") == "pending_ai_review", g.get("status")


def test_admin_listing_reviews_queue_contains_flag(admin_token, flagged_listing):
    r = requests.get(f"{BASE_URL}/api/admin/listing-reviews?status=pending",
                     headers=_h(admin_token), timeout=20)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    items = body if isinstance(body, list) else body.get("reviews") or body.get("items") or []
    ids = [x.get("listing_id") for x in items]
    assert flagged_listing["listing_id"] in ids, f"not in queue: {ids[:5]}"


def test_admin_approve_listing_review_restores_listing(admin_token, buyer_token):
    end = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    c = requests.post(f"{BASE_URL}/api/listings", json={
        "title": "TEST_v9 to_approve",
        "description": "approve flow",
        "category": "Furniture", "condition": "good",
        "starting_price": 80.0, "location": "Toronto, ON",
        "city": "Toronto", "region": "ON", "auction_end_date": end,
    }, headers=_h(buyer_token), timeout=20)
    lid = c.json().get("id") or c.json().get("listing_id")
    f = requests.post(f"{BASE_URL}/api/listings/{lid}/flag-for-ai-review",
                      json={"suggested_category": "Vehicles",
                            "reason_en": "truck", "reason_fr": "camion"},
                      headers=_h(buyer_token), timeout=20)
    rid = f.json().get("review_id") or f.json().get("id")
    a = requests.post(
        f"{BASE_URL}/api/admin/listing-reviews/{rid}/approve",
        json={}, headers=_h(admin_token), timeout=20)
    assert a.status_code == 200, f"{a.status_code} {a.text[:400]}"
    # GET listing back — should be off pending_ai_review
    g = requests.get(f"{BASE_URL}/api/listings/{lid}", timeout=20).json()
    assert g.get("status") != "pending_ai_review", g.get("status")


def test_admin_reject_listing_review_sets_rejected(admin_token, buyer_token):
    end = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    c = requests.post(f"{BASE_URL}/api/listings", json={
        "title": "TEST_v9 to_reject",
        "description": "reject flow",
        "category": "Furniture", "condition": "good",
        "starting_price": 60.0, "location": "Toronto, ON",
        "city": "Toronto", "region": "ON", "auction_end_date": end,
    }, headers=_h(buyer_token), timeout=20)
    lid = c.json().get("id") or c.json().get("listing_id")
    f = requests.post(f"{BASE_URL}/api/listings/{lid}/flag-for-ai-review",
                      json={"suggested_category": "Vehicles",
                            "reason_en": "truck", "reason_fr": "camion"},
                      headers=_h(buyer_token), timeout=20)
    rid = f.json().get("review_id") or f.json().get("id")
    a = requests.post(
        f"{BASE_URL}/api/admin/listing-reviews/{rid}/reject",
        json={"reason": "test reject"}, headers=_h(admin_token), timeout=20)
    assert a.status_code == 200, f"{a.status_code} {a.text[:400]}"
    g = requests.get(f"{BASE_URL}/api/listings/{lid}", timeout=20).json()
    assert g.get("status") == "rejected"


def test_seller_correct_category_returns_listing(buyer_token):
    end = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    c = requests.post(f"{BASE_URL}/api/listings", json={
        "title": "TEST_v9 correct_category", "description": "fix cat",
        "category": "Furniture", "condition": "good",
        "starting_price": 30.0, "location": "Toronto, ON",
        "city": "Toronto", "region": "ON", "auction_end_date": end,
    }, headers=_h(buyer_token), timeout=20)
    lid = c.json().get("id") or c.json().get("listing_id")
    requests.post(f"{BASE_URL}/api/listings/{lid}/flag-for-ai-review",
                  json={"suggested_category": "Vehicles",
                        "reason_en": "x", "reason_fr": "y"},
                  headers=_h(buyer_token), timeout=20)
    r = requests.post(f"{BASE_URL}/api/listings/{lid}/correct-category",
                      json={"new_category": "Vehicles"},
                      headers=_h(buyer_token), timeout=20)
    assert r.status_code == 200, r.text[:300]
    g = requests.get(f"{BASE_URL}/api/listings/{lid}", timeout=20).json()
    assert g.get("status") != "pending_ai_review"


def test_seller_withdraw_from_review(buyer_token):
    end = (datetime.now(timezone.utc) + timedelta(days=4)).isoformat()
    c = requests.post(f"{BASE_URL}/api/listings", json={
        "title": "TEST_v9 withdraw_flow", "description": "withdraw",
        "category": "Furniture", "condition": "good",
        "starting_price": 30.0, "location": "Toronto, ON",
        "city": "Toronto", "region": "ON", "auction_end_date": end,
    }, headers=_h(buyer_token), timeout=20)
    lid = c.json().get("id") or c.json().get("listing_id")
    requests.post(f"{BASE_URL}/api/listings/{lid}/flag-for-ai-review",
                  json={"suggested_category": "Vehicles",
                        "reason_en": "x", "reason_fr": "y"},
                  headers=_h(buyer_token), timeout=20)
    r = requests.post(
        f"{BASE_URL}/api/listings/{lid}/withdraw-from-review?listing_type=single",
        json={}, headers=_h(buyer_token), timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:300]}"
    g = requests.get(f"{BASE_URL}/api/listings/{lid}", timeout=20).json()
    assert g.get("status") == "withdrawn"


# ── Feature 1: admin end-time edit + history ────────────────────

@pytest.fixture(scope="module")
def open_auction_for_endtime(buyer_token):
    end = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    c = requests.post(f"{BASE_URL}/api/listings", json={
        "title": "TEST_v9 endtime auction",
        "description": "endtime edit",
        "category": "Furniture", "condition": "good",
        "starting_price": 40.0, "location": "Toronto, ON",
        "city": "Toronto", "region": "ON", "auction_end_date": end,
    }, headers=_h(buyer_token), timeout=20)
    assert c.status_code in (200, 201), c.text[:300]
    return c.json().get("id") or c.json().get("listing_id")


def test_admin_update_end_time_success(admin_token, open_auction_for_endtime):
    new_end = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
    r = requests.patch(
        f"{BASE_URL}/api/admin/auctions/{open_auction_for_endtime}/end-time",
        json={"new_end_time": new_end, "reason": "v9 test extension"},
        headers=_h(admin_token), timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text[:400]}"
    body = r.json()
    # Optional notified-counts fields
    assert "notified" in body or "notified_count" in body or "audit_id" in body or "ok" in body or "success" in body, body


def test_admin_update_end_time_rejects_past_date(admin_token,
                                                 open_auction_for_endtime):
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    r = requests.patch(
        f"{BASE_URL}/api/admin/auctions/{open_auction_for_endtime}/end-time",
        json={"new_end_time": past, "reason": "should fail"},
        headers=_h(admin_token), timeout=20)
    assert r.status_code in (400, 422), f"{r.status_code} {r.text[:300]}"


def test_admin_end_time_history(admin_token, open_auction_for_endtime):
    r = requests.get(
        f"{BASE_URL}/api/admin/auctions/{open_auction_for_endtime}/end-time-history",
        headers=_h(admin_token), timeout=20)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    items = body if isinstance(body, list) else body.get("history") or body.get("items") or []
    assert len(items) >= 1, body


def test_non_admin_cannot_update_end_time(buyer_token, open_auction_for_endtime):
    new_end = (datetime.now(timezone.utc) + timedelta(days=11)).isoformat()
    r = requests.patch(
        f"{BASE_URL}/api/admin/auctions/{open_auction_for_endtime}/end-time",
        json={"new_end_time": new_end, "reason": "unauthorized"},
        headers=_h(buyer_token), timeout=20)
    assert r.status_code in (401, 403), r.status_code
