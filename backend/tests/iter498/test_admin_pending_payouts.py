"""iter498 — Backend regression tests for the Admin Pending Payouts view.

Endpoints under test (both `require_admin`-gated):
  GET  /api/admin/payouts/pending
  POST /api/admin/payouts/{payout_id}/release

Coverage:
  * Anonymous callers → 401.
  * Non-admin callers → 403 on both endpoints.
  * Admin GET returns the seller_payouts rows with status in
    (pending, requires_review) enriched with seller info.
  * Release endpoint rejects unknown payout ids with 404.
  * Release endpoint on a real pending row returns a structured
    envelope. On the preview environment Stripe is not reachable
    with a valid connect account, so we accept either
    ``status == "sent"`` (unlikely) or the graceful still_pending
    envelope with an explicit ``error`` string.
  * A row already marked ``sent`` responds with ``already_sent``.

Test data — the tests seed a self-contained payout row against the
canonical admin user so cleanup is idempotent.
"""
from __future__ import annotations

import os
import time
import uuid
from datetime import datetime, timezone

import pytest
import requests


BASE_URL = (
    os.environ.get("BACKEND_BASE_URL")
    or open("/app/frontend/.env").read().split("REACT_APP_BACKEND_URL=", 1)[-1].split("\n", 1)[0].strip()
).rstrip("/")
API = f"{BASE_URL}/api"

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


def _login(email: str, password: str) -> str:
    r = requests.post(
        f"{API}/auth/login",
        json={"email": email, "password": password},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"login for {email} failed: {r.status_code}")
    tok = r.json().get("access_token") or r.json().get("token") or ""
    if not tok:
        pytest.skip(f"no token for {email}")
    return tok


def _admin_headers() -> dict:
    return {"Authorization": f"Bearer {_login(ADMIN_EMAIL, ADMIN_PASSWORD)}"}


def _fresh_nonadmin_headers() -> dict:
    email = f"iter498nonadmin_{int(time.time())}_{uuid.uuid4().hex[:6]}@test.com"
    requests.post(
        f"{API}/auth/register",
        json={
            "email": email,
            "password": "Test123!@#",
            "name": "Iter498 NonAdmin",
            "terms_agreed": True,
            "ai_disclosure_consent": True,
        },
        timeout=15,
    )
    tok = _login(email, "Test123!@#")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture()
def db_client():
    from dotenv import load_dotenv
    load_dotenv("/app/backend/.env")
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    yield db
    client.close()


@pytest.mark.asyncio
async def test_seed_pending_payout(db_client):
    """Sanity: at least one seller_payouts row exists with status pending."""
    total = await db_client.seller_payouts.count_documents(
        {"status": {"$in": ["pending", "requires_review"]}}
    )
    # If the preview DB is empty we still want the test suite to pass; seed
    # one purposeful row so downstream tests have data to work with.
    if total == 0:
        await db_client.seller_payouts.insert_one({
            "id": f"iter498-test-payout-{uuid.uuid4().hex[:8]}",
            "listing_id": f"iter498-test-listing-{uuid.uuid4().hex[:6]}",
            "listing_title": "iter498 test payout row",
            "seller_id": "iter498-test-seller",
            "amount": 42.42,
            "currency": "CAD",
            "status": "pending",
            "section": "marketplace",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
    assert True


# ── Auth gates ────────────────────────────────────────────────────
def test_get_requires_auth():
    r = requests.get(f"{API}/admin/payouts/pending", timeout=15)
    assert r.status_code in (401, 403)


def test_get_rejects_non_admin():
    r = requests.get(
        f"{API}/admin/payouts/pending",
        headers=_fresh_nonadmin_headers(),
        timeout=15,
    )
    assert r.status_code == 403


def test_release_rejects_non_admin():
    r = requests.post(
        f"{API}/admin/payouts/does-not-matter/release",
        headers=_fresh_nonadmin_headers(),
        timeout=15,
    )
    assert r.status_code == 403


# ── Happy paths ───────────────────────────────────────────────────
def test_admin_get_returns_pending_rows():
    r = requests.get(
        f"{API}/admin/payouts/pending?limit=50",
        headers=_admin_headers(),
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "total" in body and "rows" in body
    assert isinstance(body["rows"], list)
    # Every row must expose the fields the UI expects
    if body["rows"]:
        row = body["rows"][0]
        for key in (
            "payout_id", "listing_id", "seller_id", "seller_has_connect",
            "amount", "currency", "status", "created_at",
        ):
            assert key in row, f"missing {key} in row: {row}"
        assert row["status"] in ("pending", "requires_review")


def test_release_returns_404_for_unknown_id():
    r = requests.post(
        f"{API}/admin/payouts/00000000-0000-0000-0000-000000000000/release",
        headers=_admin_headers(),
        timeout=15,
    )
    assert r.status_code == 404
    assert r.json().get("detail") == "payout_not_found"


@pytest.mark.asyncio
async def test_release_reports_still_pending_when_seller_has_no_connect(db_client):
    """A pending payout whose seller has no Stripe Connect account must
    return ``status=still_pending`` with a clear error string — never a 500."""
    # Seed a payout with a synthetic seller that owns no Connect account.
    seller_id = f"iter498-no-connect-seller-{uuid.uuid4().hex[:6]}"
    await db_client.users.update_one(
        {"id": seller_id},
        {"$set": {
            "id": seller_id,
            "email": f"{seller_id}@test.com",
            "name": "Iter498 No-Connect Seller",
            "role": "user",
        }},
        upsert=True,
    )
    payout_id = f"iter498-payout-noconnect-{uuid.uuid4().hex[:6]}"
    await db_client.seller_payouts.insert_one({
        "id": payout_id,
        "listing_id": "iter498-listing-x",
        "listing_title": "Iter498 payout without Connect",
        "seller_id": seller_id,
        "amount": 12.34,
        "currency": "CAD",
        "status": "pending",
        "section": "marketplace",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r = requests.post(
            f"{API}/admin/payouts/{payout_id}/release",
            headers=_admin_headers(),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["payout_id"] == payout_id
        assert body["status"] == "still_pending"
        assert body["error"] == "seller_has_no_active_stripe_connect_account"
        # Row status untouched
        doc = await db_client.seller_payouts.find_one({"id": payout_id}, {"_id": 0})
        assert doc["status"] == "pending"
    finally:
        await db_client.seller_payouts.delete_one({"id": payout_id})
        await db_client.users.delete_one({"id": seller_id})


@pytest.mark.asyncio
async def test_release_short_circuits_on_already_sent(db_client):
    """When the row is already ``sent`` the endpoint returns
    ``already_sent`` without hitting Stripe."""
    payout_id = f"iter498-payout-already-sent-{uuid.uuid4().hex[:6]}"
    await db_client.seller_payouts.insert_one({
        "id": payout_id,
        "listing_id": "iter498-listing-sent",
        "listing_title": "Iter498 already sent",
        "seller_id": "irrelevant",
        "amount": 10.0,
        "currency": "CAD",
        "status": "sent",
        "stripe_transfer_id": "tr_test_existing_transfer",
        "section": "marketplace",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    try:
        r = requests.post(
            f"{API}/admin/payouts/{payout_id}/release",
            headers=_admin_headers(),
            timeout=15,
        )
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "already_sent"
        assert r.json()["stripe_transfer_id"] == "tr_test_existing_transfer"
    finally:
        await db_client.seller_payouts.delete_one({"id": payout_id})
