"""
iter196 — HTTP-level Messaging Gate Tests
Hits the public preview URL with the buyer JWT to verify each gate code
returns 403 with detail = {code, message_en, message_fr}.

Seeds the necessary listing docs directly in MongoDB.

Run:
  PYTHONPATH=/app/backend pytest tests/test_messaging_gate_iter196_http.py -v
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

load_dotenv("/app/frontend/.env")
load_dotenv("/app/backend/.env", override=False)

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
BUYER_EMAIL = "iter189buyer@test.com"
BUYER_PASSWORD = "TestBuyer123!"
BUYER_ID = "93aa21c2-4e41-4235-a382-d4b8c8836d41"


@pytest.fixture(scope="module")
def buyer_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": BUYER_EMAIL, "password": BUYER_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"Buyer login failed: {r.status_code} {r.text[:200]}")
    return r.json().get("token") or r.json().get("access_token")


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


def _post_message(token, payload):
    return requests.post(
        f"{BASE_URL}/api/messages",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=20,
    )


def _assert_bilingual(detail, expected_code):
    assert isinstance(detail, dict), f"detail not a dict: {detail!r}"
    assert detail.get("code") == expected_code, detail
    assert detail.get("message_en"), detail
    assert detail.get("message_fr"), detail
    assert detail["message_en"] != detail["message_fr"], "EN==FR (suspicious)"


# ── Gate code: thread_requires_listing_context ────────────────────────────
def test_no_listing_id_returns_thread_requires_listing(buyer_token):
    r = _post_message(buyer_token, {"receiver_id": "stranger-no-listing", "content": "hi"})
    assert r.status_code == 403, r.text
    _assert_bilingual(r.json()["detail"], "thread_requires_listing_context")


# ── Gate code: listing_not_found ──────────────────────────────────────────
def test_unknown_listing_returns_listing_not_found(buyer_token):
    r = _post_message(buyer_token, {
        "receiver_id": "anyone",
        "content": "hi",
        "listing_id": f"does-not-exist-{uuid.uuid4().hex[:8]}",
    })
    assert r.status_code == 403, r.text
    _assert_bilingual(r.json()["detail"], "listing_not_found")


# ── Gate code: auction_not_ended ──────────────────────────────────────────
def test_active_marketplace_returns_auction_not_ended(buyer_token, db):
    lid = f"itergate-active-{uuid.uuid4().hex[:6]}"
    db.listings.insert_one({
        "id": lid,
        "seller_id": "seller-x",
        "winner_id": None,
        "status": "active",
        "end_time": (datetime.now(timezone.utc) + timedelta(days=2)).isoformat(),
    })
    try:
        r = _post_message(buyer_token, {"receiver_id": "seller-x", "content": "hi", "listing_id": lid})
        assert r.status_code == 403, r.text
        _assert_bilingual(r.json()["detail"], "auction_not_ended")
    finally:
        db.listings.delete_one({"id": lid})


# ── Gate code: not_party_to_transaction (ended but buyer is outsider) ─────
def test_ended_marketplace_outsider_returns_not_party(buyer_token, db):
    lid = f"itergate-ended-{uuid.uuid4().hex[:6]}"
    db.listings.insert_one({
        "id": lid,
        "seller_id": "some-seller",
        "winner_id": "some-other-winner",  # buyer is NOT the winner
        "status": "ended",
        "end_time": (datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    })
    try:
        r = _post_message(buyer_token, {"receiver_id": "some-seller", "content": "hi", "listing_id": lid})
        assert r.status_code == 403, r.text
        _assert_bilingual(r.json()["detail"], "not_party_to_transaction")
    finally:
        db.listings.delete_one({"id": lid})


# ── Gate code: vehicle_unlock_fee_unpaid ──────────────────────────────────
def test_vehicle_unpaid_returns_unlock_fee_unpaid(buyer_token, db):
    lid = f"itergate-veh-unpaid-{uuid.uuid4().hex[:6]}"
    sid = f"vs-{uuid.uuid4().hex[:6]}"
    db.vehicle_sellers.insert_one({"id": sid, "user_id": "veh-seller-user-X"})
    db.vehicle_listings.insert_one({
        "id": lid,
        "seller_id": sid,
        "winner_id": BUYER_ID,         # buyer IS the winner
        "unlock_paid_at": None,
        "status": "ended",
    })
    try:
        r = _post_message(buyer_token, {"receiver_id": "veh-seller-user-X", "content": "hi", "listing_id": lid})
        assert r.status_code == 403, r.text
        _assert_bilingual(r.json()["detail"], "vehicle_unlock_fee_unpaid")
    finally:
        db.vehicle_listings.delete_one({"id": lid})
        db.vehicle_sellers.delete_one({"id": sid})


# ── Allowed: vehicle paid, winner→seller succeeds ────────────────────────
def test_vehicle_paid_winner_to_seller_allowed(buyer_token, db):
    lid = f"itergate-veh-paid-{uuid.uuid4().hex[:6]}"
    sid = f"vs-{uuid.uuid4().hex[:6]}"
    seller_user_id = f"veh-seller-user-{uuid.uuid4().hex[:6]}"
    db.vehicle_sellers.insert_one({"id": sid, "user_id": seller_user_id})
    db.users.insert_one({
        "id": seller_user_id,
        "email": f"TEST_{uuid.uuid4().hex[:6]}@example.com",
        "name": "Test Veh Seller",
        "preferred_language": "en",
    })
    db.vehicle_listings.insert_one({
        "id": lid,
        "seller_id": sid,
        "winner_id": BUYER_ID,
        "unlock_paid_at": datetime.now(timezone.utc).isoformat(),
        "status": "ended",
    })
    try:
        r = _post_message(buyer_token, {
            "receiver_id": seller_user_id,
            "content": "Hello — iter196 test (offline email expected)",
            "listing_id": lid,
        })
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        body = r.json()
        assert body.get("id"), body
        assert body.get("conversation_id"), body
    finally:
        db.vehicle_listings.delete_one({"id": lid})
        db.vehicle_sellers.delete_one({"id": sid})
        db.users.delete_one({"id": seller_user_id})
        # cleanup conversation/messages
        cid = "_".join(sorted([BUYER_ID, seller_user_id]))
        db.conversations.delete_one({"id": cid})
        db.messages.delete_many({"conversation_id": cid})
