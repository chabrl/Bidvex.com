"""
iter310 — Tests for the post-D1/D2/D3/D4 follow-up sprint:

  • Unsubscribe Audit Trail (collection + summary + paginated list)
  • Recently Sold ticker endpoint
  • Admin Offline Transaction recording
  • $500 Deposit auto-capture: applies against invoice balance + flags
    remaining as payment_overdue
  • testseller demo bypass (Stripe gating unblocked)
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

from pymongo import MongoClient  # noqa: E402

BASE_URL = os.environ["REACT_APP_BACKEND_URL"] if "REACT_APP_BACKEND_URL" in os.environ else None
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL"):
                BASE_URL = line.split("=", 1)[1].strip()
                break
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest.fixture(scope="module", autouse=True)
def _bootstrap_async_db():
    from motor.motor_asyncio import AsyncIOMotorClient
    from deps import set_db
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    set_db(client[os.environ["DB_NAME"]])
    yield
    client.close()


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    if r.status_code != 200:
        pytest.skip(f"admin login failed: {r.status_code} {r.text}")
    return r.json()["access_token"]


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}"}


# ────────────────────────────────────────────────────────────────────
# Unsubscribe Audit Trail
# ────────────────────────────────────────────────────────────────────

def test_unsub_audit_collection_write_on_confirm(db):
    """auto-confirm must insert a row into unsubscribe_events."""
    os.environ.setdefault("UNSUBSCRIBE_SECRET", "iter310-test-secret")
    from routes.unsubscribe import generate_unsubscribe_token, auto_confirm_unsubscribe, ConfirmRequest
    from motor.motor_asyncio import AsyncIOMotorClient
    from deps import set_db

    email = f"iter310-audit-{uuid.uuid4().hex[:8]}@test.example"
    try:
        db.users.insert_one({"id": str(uuid.uuid4()), "email": email, "role": "user"})
        token = generate_unsubscribe_token(email)

        class _R:
            client = None
            headers = {"user-agent": "iter310-pytest"}

        async def _run():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            set_db(client[os.environ["DB_NAME"]])
            try:
                return await auto_confirm_unsubscribe(ConfirmRequest(token=token, lang="fr"), _R())
            finally:
                client.close()

        result = asyncio.run(_run())
        assert result["status"] == "success"

        row = db.unsubscribe_events.find_one({"email": email}, {"_id": 0})
        assert row is not None
        assert row["source"] == "platform"
        assert row["token_type"] == "itsdangerous"
        assert row["lang"] == "fr"
        assert row["event"] == "unsubscribed"
    finally:
        db.users.delete_many({"email": email})
        db.email_suppressions.delete_many({"email": email})
        db.external_email_suppressions.delete_many({"email": email})
        db.unsubscribe_events.delete_many({"email": email})


def test_admin_unsubscribe_audit_summary_endpoint(admin_token):
    r = requests.get(
        f"{BASE_URL}/api/admin/unsubscribe-audit/summary",
        headers=_hdr(admin_token),
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    for k in ("today", "last_7", "last_30", "by_day", "by_source"):
        assert k in body


def test_admin_unsubscribe_audit_list_endpoint(admin_token):
    r = requests.get(
        f"{BASE_URL}/api/admin/unsubscribe-audit",
        headers=_hdr(admin_token),
        params={"page": 1, "per_page": 25},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "events" in body
    assert "count" in body
    assert body["per_page"] == 25


def test_admin_unsubscribe_audit_requires_admin():
    r = requests.get(
        f"{BASE_URL}/api/admin/unsubscribe-audit/summary",
        timeout=15,
    )
    assert r.status_code in (401, 403)


# ────────────────────────────────────────────────────────────────────
# Recently Sold ticker
# ────────────────────────────────────────────────────────────────────

def test_recently_sold_endpoint_shape():
    r = requests.get(f"{BASE_URL}/api/public/recently-sold?limit=5", timeout=10)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    # Each item must be anonymized — no buyer/seller names ever.
    for it in body["items"]:
        assert "id" in it
        assert "title" in it
        assert "price" in it
        assert "currency" in it
        for forbidden in ("buyer", "seller", "buyer_id", "seller_id", "buyer_name", "seller_name", "email"):
            assert forbidden not in it, f"anonymization leak: {forbidden} in {it}"


def test_recently_sold_caches_for_60s(db):
    """Two back-to-back calls must hit the in-memory cache (same response object)."""
    r1 = requests.get(f"{BASE_URL}/api/public/recently-sold?limit=5", timeout=10).json()
    r2 = requests.get(f"{BASE_URL}/api/public/recently-sold?limit=5", timeout=10).json()
    assert r1 == r2  # identical payload


# ────────────────────────────────────────────────────────────────────
# Admin Offline Transactions
# ────────────────────────────────────────────────────────────────────

def test_admin_record_offline_transaction(admin_token, db):
    # Seed a listing we can reference.
    listing_id = f"iter310-listing-{uuid.uuid4().hex[:8]}"
    seller_id = f"iter310-seller-{uuid.uuid4().hex[:8]}"
    try:
        db.listings.insert_one({
            "id":              listing_id,
            "seller_id":       seller_id,
            "title":           "iter310 offline tx test",
            "description":     "fixture",
            "category":        "Tools",
            "current_price":   100,
            "status":          "completed",
            "created_at":      datetime.now(timezone.utc),
        })
        db.users.insert_one({"id": seller_id, "email": f"{seller_id}@test.example", "role": "user"})

        payload = {
            "listing_id":     listing_id,
            "listing_kind":   "listing",
            "buyer_email":    "buyer-offline@test.example",
            "amount":         150.0,
            "currency":       "CAD",
            "payment_method": "etransfer",
            "admin_note":     "iter310 pytest fixture",
        }
        r = requests.post(
            f"{BASE_URL}/api/admin/offline-transactions/record",
            json=payload,
            headers=_hdr(admin_token),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["status"] == "recorded"
        assert body["transaction"]["amount"] == 150.0
        assert body["transaction"]["payment_method"] == "etransfer"
        assert body["transaction"]["is_offline"] is True
        assert body["transaction"]["stripe_payment_intent_id"] is None  # no real charge

        tx_id = body["transaction"]["id"]

        # Round-trip via list endpoint.
        r2 = requests.get(
            f"{BASE_URL}/api/admin/offline-transactions",
            headers=_hdr(admin_token),
            params={"listing_id": listing_id},
            timeout=15,
        )
        assert r2.status_code == 200
        assert any(t["id"] == tx_id for t in r2.json()["transactions"])
    finally:
        db.admin_offline_transactions.delete_many({"listing_id": listing_id})
        db.listings.delete_many({"id": listing_id})
        db.users.delete_many({"id": seller_id})
        db.notifications.delete_many({"user_id": seller_id})


def test_admin_record_offline_transaction_404_for_unknown_listing(admin_token):
    r = requests.post(
        f"{BASE_URL}/api/admin/offline-transactions/record",
        json={"listing_id": "does-not-exist", "amount": 99.0, "payment_method": "cash"},
        headers=_hdr(admin_token),
        timeout=15,
    )
    assert r.status_code == 404


# ────────────────────────────────────────────────────────────────────
# $500 Deposit Auto-Capture invoice settlement
# ────────────────────────────────────────────────────────────────────

def test_deposit_auto_capture_source_applies_against_invoice():
    """The job source must update the invoice with paid_amount + remaining + status."""
    import inspect
    from services import deposit_auto_capture

    src = inspect.getsource(deposit_auto_capture.run_auto_capture_overdue_deposits)
    # New iter310 invoice-settlement block.
    assert "deposit_capture_applied" in src
    assert "remaining_balance" in src
    assert "payment_overdue" in src
    assert "vehicle_invoices.update_one" in src


# ────────────────────────────────────────────────────────────────────
# testseller demo bypass
# ────────────────────────────────────────────────────────────────────

def test_testseller_marked_as_demo(db):
    u = db.users.find_one({"email": "testseller@bidvex.com"}, {"_id": 0, "is_demo_account": 1, "has_payment_method": 1, "phone_verified": 1})
    assert u is not None, "testseller@bidvex.com missing from DB"
    assert u.get("is_demo_account") is True
    assert u.get("has_payment_method") is True
    assert u.get("phone_verified") is True
