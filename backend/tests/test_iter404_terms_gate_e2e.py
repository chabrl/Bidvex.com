"""
iter404 — Backend integration tests for the platform-terms Trust Gate flow.

Verifies over real HTTP against REACT_APP_BACKEND_URL:
  1. POST /api/bids returns 403 trust_required with 'terms' in missing when
     the buyer's platform_terms_accepted_at is null.
  2. POST /api/users/me/accept-platform-terms returns 200 + timestamp and
     persists platform_terms_accepted_at on the users doc.
  3. The endpoint is idempotent — a second call returns the ORIGINAL
     acceptance timestamp.
  4. After acceptance, retrying the same bid endpoint no longer returns a
     trust_required 403 with 'terms' in missing (may 403 for OTHER pillars
     like phone/payment, or 400/404 for domain errors — but NOT terms).
"""
import os
import time
import uuid
import asyncio

import pytest
import pytest_asyncio
import requests
from motor.motor_asyncio import AsyncIOMotorClient


def _load_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as fh:
            for line in fh:
                if "=" not in line or line.startswith("#"):
                    continue
                k, _, v = line.strip().partition("=")
                if k and v and k not in os.environ:
                    os.environ[k] = v
    fe_env = "/app/frontend/.env"
    if os.path.exists(fe_env):
        with open(fe_env) as fh:
            for line in fh:
                if "=" not in line or line.startswith("#"):
                    continue
                k, _, v = line.strip().partition("=")
                if k and v and k not in os.environ:
                    os.environ[k] = v


_load_env()
BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
API = f"{BASE_URL}/api"

BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PASSWORD = "TestBuyer2026!"


@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    d = client[os.environ["DB_NAME"]]
    yield d
    client.close()


def _login(email, password):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": password}, timeout=30)
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text[:300]}"
    return r.json().get("token") or r.json().get("access_token")


async def _reset_terms(db, email):
    await db.users.update_one(
        {"email": email},
        {"$unset": {"platform_terms_accepted_at": "", "platform_terms_version": "", "platform_terms_last_seen_at": ""}},
    )


async def _ensure_test_listing(db):
    """Insert a minimal active listing if none exists so the bid test can run."""
    lst = await db.listings.find_one({"status": "active"}, {"_id": 0, "id": 1, "current_price": 1, "starting_price": 1})
    if lst:
        return lst
    from datetime import datetime, timezone, timedelta
    lid = f"iter404-test-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    doc = {
        "id": lid,
        "title": "iter404 Trust Gate Test Listing",
        "description": "seeded for iter404 backend test",
        "seller_id": "iter404-seller",
        "starting_price": 10.0,
        "current_price": 10.0,
        "reserve_price": 0,
        "status": "active",
        "listing_type": "auction",
        "created_at": now.isoformat(),
        "start_time": now.isoformat(),
        "end_time": (now + timedelta(days=7)).isoformat(),
        "category": "other",
        "quantity": 1,
        "images": [],
    }
    await db.listings.insert_one(doc)
    return doc


@pytest.mark.asyncio
async def test_bid_returns_403_terms_missing(db):
    await _reset_terms(db, BUYER_EMAIL)
    token = _login(BUYER_EMAIL, BUYER_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    # Find or seed an active listing to bid on
    await _ensure_test_listing(db)
    listings = await db.listings.find({"status": "active"}, {"_id": 0, "id": 1, "current_price": 1, "starting_price": 1}).to_list(5)
    assert listings, "no active listings available for test"
    listing = listings[0]
    cur = listing.get("current_price") or listing.get("starting_price") or 1
    payload = {"listing_id": listing["id"], "amount": float(cur) + 1000}

    r = requests.post(f"{API}/bids", json=payload, headers=headers, timeout=30)
    assert r.status_code == 403, f"expected 403; got {r.status_code}: {r.text[:400]}"
    detail = r.json().get("detail")
    assert isinstance(detail, dict), f"detail should be dict: {detail}"
    assert detail.get("error") == "trust_required"
    assert "terms" in detail.get("missing", []), f"'terms' missing from {detail.get('missing')}"
    assert "message_en" in detail and "message_fr" in detail


@pytest.mark.asyncio
async def test_accept_platform_terms_persists_and_idempotent(db):
    await _reset_terms(db, BUYER_EMAIL)
    token = _login(BUYER_EMAIL, BUYER_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    r1 = requests.post(f"{API}/users/me/accept-platform-terms", json={"version": "v1"}, headers=headers, timeout=30)
    assert r1.status_code == 200, f"{r1.status_code}: {r1.text}"
    d1 = r1.json()
    assert d1.get("success") is True
    assert d1.get("platform_terms_version") == "v1"
    ts1 = d1.get("platform_terms_accepted_at")
    assert ts1

    # Verify DB persistence
    row = await db.users.find_one({"email": BUYER_EMAIL}, {"_id": 0, "platform_terms_accepted_at": 1})
    assert row and row.get("platform_terms_accepted_at") == ts1

    # Idempotency — same timestamp preserved
    time.sleep(1)
    r2 = requests.post(f"{API}/users/me/accept-platform-terms", json={"version": "v1"}, headers=headers, timeout=30)
    assert r2.status_code == 200
    assert r2.json().get("platform_terms_accepted_at") == ts1, "acceptance must be idempotent"


@pytest.mark.asyncio
async def test_bid_no_longer_reports_terms_after_acceptance(db):
    # Ensure terms accepted (from prior test, or set now)
    token = _login(BUYER_EMAIL, BUYER_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}
    requests.post(f"{API}/users/me/accept-platform-terms", json={"version": "v1"}, headers=headers, timeout=30)

    await _ensure_test_listing(db)
    listings = await db.listings.find({"status": "active"}, {"_id": 0, "id": 1, "current_price": 1, "starting_price": 1}).to_list(5)
    assert listings
    listing = listings[0]
    cur = listing.get("current_price") or listing.get("starting_price") or 1
    payload = {"listing_id": listing["id"], "amount": float(cur) + 1000}

    r = requests.post(f"{API}/bids", json=payload, headers=headers, timeout=30)
    # Could be 200 success, or 403 for OTHER pillars, or 400 domain error.
    # CRUCIAL: 'terms' must not be in missing[] anymore.
    if r.status_code == 403:
        detail = r.json().get("detail")
        if isinstance(detail, dict) and detail.get("error") == "trust_required":
            assert "terms" not in detail.get("missing", []), (
                f"'terms' should not be in missing after acceptance; got {detail.get('missing')}"
            )
    # else: any other status is fine, terms gate passed


@pytest.mark.asyncio
async def test_storage_auction_bid_403_contract(db):
    """Verify /api/storage-auctions/:id/bid emits same trust_required 403 shape."""
    await _reset_terms(db, BUYER_EMAIL)
    token = _login(BUYER_EMAIL, BUYER_PASSWORD)
    headers = {"Authorization": f"Bearer {token}"}

    st = await db.storage_auctions.find_one({"status": "active"}, {"_id": 0, "id": 1, "current_price": 1, "starting_price": 1, "bid_increment": 1})
    if not st:
        pytest.skip("no active storage auction available")
    cur = st.get("current_price") or st.get("starting_price") or 1
    inc = st.get("bid_increment") or 10
    payload = {"amount": float(cur) + float(inc) * 5}
    r = requests.post(f"{API}/storage-auctions/{st['id']}/bid", json=payload, headers=headers, timeout=30)
    assert r.status_code == 403, f"expected 403; got {r.status_code}: {r.text[:400]}"
    detail = r.json().get("detail")
    assert isinstance(detail, dict) and detail.get("error") == "trust_required"
    assert "terms" in detail.get("missing", [])
