"""
iter288 — Listing Change-Request Pipeline regression tests.

Covers the user-self-service workflow (edit / delete request) and the
admin triage inbox introduced in `routes/listing_requests.py`.

Endpoints under test:
  POST   /api/listings/{id}/request-change
  GET    /api/listing-requests/mine
  GET    /api/admin/listing-requests
  POST   /api/admin/listing-requests/{rid}/approve
  POST   /api/admin/listing-requests/{rid}/reject

All endpoints respect the FastAPI auth layer; non-admin callers
attempting admin endpoints must get a 403.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("PUBLIC_BACKEND_URL", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def admin_token():
    import time as _t
    last = None
    for _attempt in range(8):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=15,
        )
        last = r
        if r.status_code == 200:
            return r.json().get("access_token") or r.json().get("token")
        _t.sleep(min(2 ** _attempt, 16))
    raise AssertionError(f"admin login failed: {last.status_code} {last.text[:200]}")


@pytest.fixture(scope="module")
def buyer_token_and_id(db):
    """Stable iter286 test buyer. Returns (token, user_id)."""
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "iter286-buyer-1780788613@test.bidvex.com", "password": "TestPassw0rd!"},
        timeout=10,
    )
    if r.status_code != 200:
        pytest.skip("stable buyer unavailable")
    body = r.json()
    token = body.get("access_token") or body.get("token")
    # Look up the user id (used in fixture seeding so seller_id matches).
    user = db.users.find_one({"email": "iter286-buyer-1780788613@test.bidvex.com"})
    return token, str(user["id"]) if user else None


@pytest.fixture()
def seeded_vehicle_owned_by_buyer(db, buyer_token_and_id):
    """Vehicle listing whose `seller_id` is the buyer test account."""
    _token, user_id = buyer_token_and_id
    if not user_id:
        pytest.skip("no buyer user id")
    vid = f"iter288-v-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    db.vehicle_listings.insert_one({
        "id":           vid,
        "seller_id":    user_id,
        "title":        "iter288 owned vehicle",
        "make":         "Toyota",
        "model":        "Camry",
        "year":         2020,
        "starting_price": 1000,
        "current_bid":  1000,
        "status":       "active",
        "end_time":     now + timedelta(days=3),
        "created_at":   now.isoformat(),
    })
    yield vid
    db.vehicle_listings.delete_one({"id": vid})
    db.listing_requests.delete_many({"listing_id": vid})


# ── User-side: submit request ────────────────────────────────────────


def test_user_submits_delete_request_on_owned_vehicle(seeded_vehicle_owned_by_buyer, buyer_token_and_id, db):
    token, _ = buyer_token_and_id
    vid = seeded_vehicle_owned_by_buyer
    r = requests.post(
        f"{BASE_URL}/api/listings/{vid}/request-change",
        headers={"Authorization": f"Bearer {token}"},
        json={"request_type": "delete", "reason": "Listed by mistake — should be removed."},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    req = r.json()["request"]
    assert req["status"] == "pending"
    assert req["request_type"] == "delete"
    assert req["listing_type"] == "vehicle"
    assert req["listing_id"] == vid
    # Persisted under db.listing_requests.
    saved = db.listing_requests.find_one({"listing_id": vid, "status": "pending"})
    assert saved is not None


def test_user_submits_edit_request_with_payload_delta(seeded_vehicle_owned_by_buyer, buyer_token_and_id):
    token, _ = buyer_token_and_id
    vid = seeded_vehicle_owned_by_buyer
    r = requests.post(
        f"{BASE_URL}/api/listings/{vid}/request-change",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "request_type": "edit",
            "reason": "Typo in VIN — last digit should be 9.",
            "current_payload_delta": {"vin": "1HGBH41JXMN109189"},
        },
        timeout=10,
    )
    assert r.status_code == 200, r.text
    req = r.json()["request"]
    assert req["request_type"] == "edit"
    assert req["current_payload_delta"] == {"vin": "1HGBH41JXMN109189"}


def test_user_duplicate_pending_request_409s(seeded_vehicle_owned_by_buyer, buyer_token_and_id):
    """A user can have at most ONE pending request per listing."""
    token, _ = buyer_token_and_id
    vid = seeded_vehicle_owned_by_buyer
    requests.post(
        f"{BASE_URL}/api/listings/{vid}/request-change",
        headers={"Authorization": f"Bearer {token}"},
        json={"request_type": "delete", "reason": "first request"},
        timeout=10,
    )
    r = requests.post(
        f"{BASE_URL}/api/listings/{vid}/request-change",
        headers={"Authorization": f"Bearer {token}"},
        json={"request_type": "delete", "reason": "second duplicate"},
        timeout=10,
    )
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["code"] == "duplicate_pending_request"


def test_user_cannot_submit_request_on_someone_elses_listing(buyer_token_and_id, db):
    """Sellers can only request changes on their own listings."""
    token, _ = buyer_token_and_id
    # Seed a vehicle owned by another seller.
    vid = f"iter288-v-{uuid.uuid4().hex[:8]}"
    db.vehicle_listings.insert_one({
        "id": vid, "seller_id": "different-seller-id",
        "title": "not owned", "status": "active",
    })
    try:
        r = requests.post(
            f"{BASE_URL}/api/listings/{vid}/request-change",
            headers={"Authorization": f"Bearer {token}"},
            json={"request_type": "delete", "reason": "trying to delete a stranger's listing"},
            timeout=10,
        )
        assert r.status_code == 403, r.text
    finally:
        db.vehicle_listings.delete_one({"id": vid})


def test_user_request_404s_on_unknown_listing(buyer_token_and_id):
    token, _ = buyer_token_and_id
    r = requests.post(
        f"{BASE_URL}/api/listings/this-does-not-exist-iter288/request-change",
        headers={"Authorization": f"Bearer {token}"},
        json={"request_type": "delete", "reason": "ghost listing"},
        timeout=10,
    )
    assert r.status_code == 404


def test_user_request_rejects_invalid_request_type(seeded_vehicle_owned_by_buyer, buyer_token_and_id):
    token, _ = buyer_token_and_id
    vid = seeded_vehicle_owned_by_buyer
    r = requests.post(
        f"{BASE_URL}/api/listings/{vid}/request-change",
        headers={"Authorization": f"Bearer {token}"},
        json={"request_type": "purge", "reason": "invalid type"},
        timeout=10,
    )
    assert r.status_code == 400


def test_user_get_mine_returns_own_requests(seeded_vehicle_owned_by_buyer, buyer_token_and_id):
    token, _ = buyer_token_and_id
    vid = seeded_vehicle_owned_by_buyer
    requests.post(
        f"{BASE_URL}/api/listings/{vid}/request-change",
        headers={"Authorization": f"Bearer {token}"},
        json={"request_type": "delete", "reason": "for me"},
        timeout=10,
    )
    r = requests.get(
        f"{BASE_URL}/api/listing-requests/mine",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] >= 1
    assert any(req["listing_id"] == vid for req in body["requests"])


# ── Admin-side: triage ────────────────────────────────────────────────


def test_admin_inbox_lists_pending_requests(seeded_vehicle_owned_by_buyer, buyer_token_and_id, admin_token):
    token, _ = buyer_token_and_id
    vid = seeded_vehicle_owned_by_buyer
    requests.post(
        f"{BASE_URL}/api/listings/{vid}/request-change",
        headers={"Authorization": f"Bearer {token}"},
        json={"request_type": "delete", "reason": "for admin inbox"},
        timeout=10,
    )
    r = requests.get(
        f"{BASE_URL}/api/admin/listing-requests?status=pending",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pending_count"] >= 1
    assert any(req["listing_id"] == vid for req in body["requests"])


def test_admin_approves_delete_soft_cancels_listing(seeded_vehicle_owned_by_buyer, buyer_token_and_id, admin_token, db):
    token, _ = buyer_token_and_id
    vid = seeded_vehicle_owned_by_buyer
    req = requests.post(
        f"{BASE_URL}/api/listings/{vid}/request-change",
        headers={"Authorization": f"Bearer {token}"},
        json={"request_type": "delete", "reason": "approve me"},
        timeout=10,
    ).json()["request"]

    r = requests.post(
        f"{BASE_URL}/api/admin/listing-requests/{req['id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["request"]["status"] == "approved"
    # Listing soft-cancelled.
    doc = db.vehicle_listings.find_one({"id": vid})
    assert doc is not None
    assert doc["status"] == "cancelled"
    assert doc["is_visible"] is False


def test_admin_approves_edit_merges_delta(seeded_vehicle_owned_by_buyer, buyer_token_and_id, admin_token, db):
    token, _ = buyer_token_and_id
    vid = seeded_vehicle_owned_by_buyer
    req = requests.post(
        f"{BASE_URL}/api/listings/{vid}/request-change",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "request_type": "edit",
            "reason": "fix model name",
            "current_payload_delta": {"model": "Camry XSE"},
        },
        timeout=10,
    ).json()["request"]

    r = requests.post(
        f"{BASE_URL}/api/admin/listing-requests/{req['id']}/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    doc = db.vehicle_listings.find_one({"id": vid})
    assert doc["model"] == "Camry XSE"
    assert doc.get("status") != "cancelled"  # edit must NOT cancel


def test_admin_rejects_request_leaves_listing_untouched(seeded_vehicle_owned_by_buyer, buyer_token_and_id, admin_token, db):
    token, _ = buyer_token_and_id
    vid = seeded_vehicle_owned_by_buyer
    req = requests.post(
        f"{BASE_URL}/api/listings/{vid}/request-change",
        headers={"Authorization": f"Bearer {token}"},
        json={"request_type": "delete", "reason": "reject me"},
        timeout=10,
    ).json()["request"]

    before = db.vehicle_listings.find_one({"id": vid})
    r = requests.post(
        f"{BASE_URL}/api/admin/listing-requests/{req['id']}/reject",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    assert r.status_code == 200, r.text
    assert r.json()["request"]["status"] == "rejected"
    after = db.vehicle_listings.find_one({"id": vid})
    # Listing untouched.
    assert after["status"] == before["status"]
    assert after.get("is_visible") in (None, True)


def test_admin_inbox_403s_for_non_admin(buyer_token_and_id):
    token, _ = buyer_token_and_id
    r = requests.get(
        f"{BASE_URL}/api/admin/listing-requests",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    assert r.status_code == 403


def test_admin_approve_404s_on_unknown_request(admin_token):
    r = requests.post(
        f"{BASE_URL}/api/admin/listing-requests/iter288-bogus-request/approve",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=10,
    )
    assert r.status_code == 404


# ── Vehicle-AutoBid wiring sanity (Part 3 — no logical deadlock) ──────


def test_vehicle_autobid_endpoint_wiring_intact():
    """The iter287 auto-bid endpoint must remain registered with the
    same path the FE checkbox dispatches to. Catches a regression where
    a future refactor renames or removes the endpoint."""
    r = requests.options(
        f"{BASE_URL}/api/vehicles/iter288-anything/auto-bid",
        timeout=10,
    )
    # FastAPI returns 405 for OPTIONS on undeclared methods on a path
    # that DOES exist, and 404 if the path itself isn't registered.
    assert r.status_code != 404
