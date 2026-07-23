"""
iter376 regression test — bid_count + bid history for multi-lot listings.

Reproduces and verifies the fix for THREE bugs:

  Bug A — POST /api/multi-item-listings/{id}/lots/{n}/bid must $inc
          the lot's bid_count so lot cards show the correct total.
  Bug B1 — GET /api/lots/{id}/recent-activity must return the newly
           placed bid (reads db.lot_bids, not the wrong db.bids).
  Bug B2 — GET /api/multi-item-listings/{id}/lots/{n}/bids-public must
           return the masked bid list (same collection swap as B1).

The test creates a fresh multi-lot listing with 2 lots, places bids on
BOTH lots as two different bidders, and asserts every visible surface
reflects the current state (including "leading" status flip).
"""

import asyncio
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get(
    "TEST_BASE_URL",
    "https://prod-verify-2.preview.emergentagent.com",
).rstrip("/")

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "test_database")


# ─── Helpers ──────────────────────────────────────────────────────────

async def _db():
    # Load MONGO_URL / DB_NAME from backend/.env at test-time so we hit the
    # same database the running API is using (Mongo Atlas in preview).
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if os.path.exists(env_path):
        with open(env_path) as fh:
            for line in fh:
                if "=" not in line or line.startswith("#"):
                    continue
                key, _, val = line.strip().partition("=")
                if key and val and key not in os.environ:
                    os.environ[key] = val
    mongo_url = os.environ.get("MONGO_URL") or MONGO_URL
    db_name = os.environ.get("DB_NAME") or DB_NAME
    client = AsyncIOMotorClient(mongo_url)
    return client[db_name], client


async def _register(client: httpx.AsyncClient, email: str, name: str) -> str:
    """Return a fresh JWT for a brand-new user."""
    pwd = "TestPass!2026"
    r = await client.post(
        f"{BASE_URL}/api/auth/register",
        json={
            "email": email, "password": pwd, "name": name, "role": "buyer",
            "terms_agreed": True, "ai_disclosure_consent": True,
        },
        timeout=15,
    )
    if r.status_code == 400 and "already" in (r.text or "").lower():
        # user already exists (previous run) — fall back to login
        r = await client.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": email, "password": pwd},
            timeout=15,
        )
    assert r.status_code == 200, f"auth failed for {email}: {r.status_code} {r.text}"
    body = r.json()
    return body.get("access_token") or body.get("token")


async def _seed_multi_lot(db, seller_id: str) -> str:
    """Insert a 2-lot multi-item listing straight into Mongo and return its id."""
    listing_id = f"iter376-{uuid.uuid4().hex[:10]}"
    end = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    lots = [
        {
            "lot_number": 1, "title": "Iter376 lot A",
            "starting_price": 10.0, "current_price": 10.0,
            "highest_bidder_id": None, "bid_count": 0,
            "lot_end_time": end, "extension_count": 0,
            "lot_status": "active",
        },
        {
            "lot_number": 2, "title": "Iter376 lot B",
            "starting_price": 20.0, "current_price": 20.0,
            "highest_bidder_id": None, "bid_count": 0,
            "lot_end_time": end, "extension_count": 0,
            "lot_status": "active",
        },
    ]
    doc = {
        "id": listing_id,
        "title": "iter376 regression listing",
        "listing_type": "lots",
        "status": "active",
        "seller_id": seller_id,
        "seller_account_type": "individual",
        "currency": "CAD",
        "auction_end_time": end,
        "increment_option": "fixed",
        "fixed_increment": 5.0,
        "lots": lots,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.multi_item_listings.insert_one(doc)
    return listing_id


async def _cleanup(db, listing_id: str, emails: list[str]):
    await db.multi_item_listings.delete_many({"id": listing_id})
    await db.lot_bids.delete_many({"listing_id": listing_id})
    if emails:
        await db.users.delete_many({"email": {"$in": emails}})


# ─── Test ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_iter376_bid_count_and_history_regression():
    db, mongo_client = await _db()
    try:
        # Register a "seller" user we can attribute the listing to (so buyers
        # aren't blocked by the "no self-bid" check).
        async with httpx.AsyncClient(follow_redirects=True) as client:
            seller_email = f"iter376-seller-{uuid.uuid4().hex[:6]}@bidvex-qa.com"
            _seller_tok = await _register(client, seller_email, "Iter376 Seller")
            seller = await db.users.find_one({"email": seller_email}, {"_id": 0, "id": 1})
            assert seller, "seller user should exist"
            seller_id = seller["id"]

            # Two bidders
            b1_email = f"iter376-bid1-{uuid.uuid4().hex[:6]}@bidvex-qa.com"
            b2_email = f"iter376-bid2-{uuid.uuid4().hex[:6]}@bidvex-qa.com"
            b1_tok = await _register(client, b1_email, "Iter376 Bid One")
            b2_tok = await _register(client, b2_email, "Iter376 Bid Two")

            listing_id = await _seed_multi_lot(db, seller_id)

            # Sanity: recent-activity is EMPTY before any bids.
            r = await client.get(
                f"{BASE_URL}/api/lots/{listing_id}/recent-activity?limit=10",
                timeout=15,
            )
            assert r.status_code == 200
            assert r.json().get("events") == [], "expected zero events before any bid"

            # ── Place bids ──
            # Bidder 1 bids $15 on lot 1 (start=$10, step=$5 → min $15)
            r = await client.post(
                f"{BASE_URL}/api/multi-item-listings/{listing_id}/lots/1/bid",
                headers={"Authorization": f"Bearer {b1_tok}"},
                json={"amount": 15.0, "bid_type": "normal"},
                timeout=15,
            )
            assert r.status_code == 200, f"lot1 first bid failed: {r.status_code} {r.text}"

            # Bidder 2 outbids on lot 1 at $20
            r = await client.post(
                f"{BASE_URL}/api/multi-item-listings/{listing_id}/lots/1/bid",
                headers={"Authorization": f"Bearer {b2_tok}"},
                json={"amount": 20.0, "bid_type": "normal"},
                timeout=15,
            )
            assert r.status_code == 200, f"lot1 outbid failed: {r.status_code} {r.text}"

            # Bidder 1 bids $25 on lot 2 (start=$20, step=$5 → min $25)
            r = await client.post(
                f"{BASE_URL}/api/multi-item-listings/{listing_id}/lots/2/bid",
                headers={"Authorization": f"Bearer {b1_tok}"},
                json={"amount": 25.0, "bid_type": "normal"},
                timeout=15,
            )
            assert r.status_code == 200, f"lot2 first bid failed: {r.status_code} {r.text}"

            # ── Bug A: bid_count on each lot must reflect real totals ──
            listing = await db.multi_item_listings.find_one({"id": listing_id})
            lots_by_num = {lot["lot_number"]: lot for lot in listing["lots"]}
            assert lots_by_num[1]["bid_count"] == 2, (
                f"lot 1 bid_count should be 2 (2 bids placed), got {lots_by_num[1]['bid_count']}"
            )
            assert lots_by_num[2]["bid_count"] == 1, (
                f"lot 2 bid_count should be 1, got {lots_by_num[2]['bid_count']}"
            )
            assert lots_by_num[1]["current_price"] == 20.0
            assert lots_by_num[2]["current_price"] == 25.0

            # ── Bug B1: /recent-activity must show all 3 events ──
            r = await client.get(
                f"{BASE_URL}/api/lots/{listing_id}/recent-activity?limit=10",
                timeout=15,
            )
            assert r.status_code == 200
            events = r.json().get("events") or []
            assert len(events) == 3, (
                f"recent-activity should return 3 events, got {len(events)}: {events}"
            )
            amounts_seen = sorted(e["amount"] for e in events)
            assert amounts_seen == [15.0, 20.0, 25.0], (
                f"unexpected bid amounts: {amounts_seen}"
            )
            # Newest-first ordering
            assert events[0]["amount"] == 25.0, (
                f"expected newest bid first ($25), got {events[0]}"
            )
            # Aliases are non-empty (privacy-safe display names)
            for e in events:
                assert e.get("bidder_alias"), f"bidder_alias missing on {e}"
                assert e.get("time_ago"), f"time_ago missing on {e}"
                assert e.get("lot_title"), f"lot_title missing on {e}"

            # ── Bug B2: /bids-public per-lot must return masked history ──
            r = await client.get(
                f"{BASE_URL}/api/multi-item-listings/{listing_id}/lots/1/bids-public",
                timeout=15,
            )
            assert r.status_code == 200
            body = r.json()
            assert body.get("total_bids") == 2, (
                f"lot 1 total_bids should be 2, got {body}"
            )
            bids_arr = body.get("bids") or []
            assert len(bids_arr) == 2, f"lot 1 masked bids array wrong: {bids_arr}"
            # The $20 (newest) row is the current leader
            assert bids_arr[0]["amount"] == 20.0
            assert bids_arr[0]["status"] == "leading"
            assert bids_arr[1]["status"] == "outbid"
            assert body.get("unique_bidders") == 2

            r = await client.get(
                f"{BASE_URL}/api/multi-item-listings/{listing_id}/lots/2/bids-public",
                timeout=15,
            )
            assert r.status_code == 200
            body = r.json()
            assert body.get("total_bids") == 1
            assert body["bids"][0]["amount"] == 25.0
            assert body["bids"][0]["status"] == "leading"

        # ── Cleanup ──
        await _cleanup(db, listing_id, [seller_email, b1_email, b2_email])
    finally:
        mongo_client.close()
