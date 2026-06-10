"""
iter296 P0 — Emergency fixes for auction-end propagation, winner +
seller emails, bilingual platform notifications, and seller dashboard
counters.

Covers:
  BUG 1 - Auction end → status transitions across 4 collections
  BUG 2 - Winner email triggered on end (marketplace + vehicle)
  BUG 3 - Seller notification triggered on end
  BUG 4 - Platform notification body non-empty in EN AND FR
  BUG 5 - Seller dashboard counters reflect ended/sold within 1 tick
"""
import os
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

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


# ── BUG 4 / notifications_i18n ─────────────────────────────────────────

def test_bilingual_notification_helper_has_both_languages():
    """`build_notification` must always produce non-empty EN + FR fields,
    even for unknown notification kinds (fallback path)."""
    from services.notifications_i18n import build_notification

    # Known kind
    n = build_notification(
        user_id="u-1", kind="auction_won",
        params={"title": "Vintage Lamp", "amount": 250.0},
    )
    assert n["title"]      == "You Won!"
    assert n["title_en"]   == "You Won!"
    assert n["title_fr"]   == "Vous avez gagné !"
    assert "Vintage Lamp"  in n["message"]
    assert "Vintage Lamp"  in n["message_en"]
    assert "Vintage Lamp"  in n["message_fr"]
    # No empty fields
    for k in ("title", "title_en", "title_fr", "message", "message_en", "message_fr"):
        assert n[k] and isinstance(n[k], str)

    # Every public kind must render bilingually
    for kind in [
        "auction_won", "auction_ended", "auction_ended_no_winner",
        "outbid", "ending_soon", "deposit_required",
        "broker_request_received", "broker_request_approved", "broker_request_rejected",
        "new_bid", "winner_payment_due",
    ]:
        m = build_notification(user_id="u", kind=kind, params={
            "title": "X", "amount": 1, "days": 14,
            "new_bid": 2, "buyer_name": "Y", "broker_name": "Z", "bidder_alias": "A",
        })
        assert m["title_fr"], f"{kind} missing title_fr"
        assert m["message_fr"], f"{kind} missing message_fr"
        assert m["title_en"], f"{kind} missing title_en"
        assert m["message_en"], f"{kind} missing message_en"

    # Unknown kind — must NOT produce empty body
    fb = build_notification(user_id="u-1", kind="some_unknown_thing")
    assert fb["title_en"] == "Update"
    assert fb["title_fr"] == "Mise à jour"
    assert fb["message_en"]
    assert fb["message_fr"]


# ── BUG 1 / Auction end status — Marketplace + Lots ────────────────────

@pytest.mark.asyncio
async def test_marketplace_listing_transitions_to_ended_and_stamps_winner(db):
    """Active marketplace listing whose auction_end_date has passed and
    has a `highest_bidder_id` must transition to status=ended with
    `winner_user_id`, `sold_at`, `final_price` set in a single update."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from routes.auctions import process_ended_auctions, set_db

    mdb = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
    set_db(mdb)

    seller_id = f"iter296-seller-{uuid.uuid4().hex[:8]}"
    winner_id = f"iter296-winner-{uuid.uuid4().hex[:8]}"
    listing_id = f"iter296-listing-{uuid.uuid4().hex[:8]}"
    past = datetime.now(timezone.utc) - timedelta(minutes=5)

    await mdb.users.insert_one({"id": seller_id, "email": "s@t.com", "name": "Seller"})
    await mdb.users.insert_one({"id": winner_id, "email": "w@t.com", "name": "Winner B",
                                "subscription_tier": "free", "province": "ON"})
    await mdb.listings.insert_one({
        "id": listing_id, "title": "iter296 Repro Item",
        "seller_id": seller_id, "status": "active",
        "auction_end_date": past, "current_price": 42.50,
        "highest_bidder_id": winner_id, "category": "Furniture",
        "payment_method": "cash",
    })

    try:
        # Patch the offline-invoice fee_calculator branch + emails so the
        # test focuses on the status transition (Bug 1) without making
        # real Stripe/SendGrid calls.
        with patch("services.email_notifications.send_auction_won_email", new=AsyncMock(return_value={"ok": True})), \
             patch("services.email_notifications.send_seller_auction_sold_email", new=AsyncMock(return_value={"ok": True})), \
             patch("services.email_notifications.send_buyer_pickup_code_email", new=AsyncMock(return_value={"ok": True})), \
             patch("services.email_notifications.send_seller_pickup_instructions_email", new=AsyncMock(return_value={"ok": True})), \
             patch("services.auction_settlement.settle_auction", new=AsyncMock(return_value={"scenario": "skipped"})):
            await process_ended_auctions()

        doc = await mdb.listings.find_one({"id": listing_id}, {"_id": 0})
        assert doc["status"] == "ended"
        assert doc["ended_at"] is not None
        # iter296 P0 stamp set — required by Bug 5 dashboard counter
        assert doc["winner_user_id"] == winner_id
        assert doc["sold_at"] is not None
        assert float(doc["final_price"]) == 42.50

        # Bug 4 — bilingual notifications inserted
        notifs = await mdb.notifications.find(
            {"data.listing_id": listing_id},
            {"_id": 0},
        ).to_list(10)
        assert len(notifs) >= 2
        for n in notifs:
            assert n.get("title_en") and n.get("title_fr"), f"missing bilingual: {n}"
            assert n.get("message_en") and n.get("message_fr")
        types = sorted({n["type"] for n in notifs})
        assert "auction_won" in types and "auction_ended" in types
    finally:
        await mdb.listings.delete_one({"id": listing_id})
        await mdb.notifications.delete_many({"data.listing_id": listing_id})
        await mdb.users.delete_many({"id": {"$in": [seller_id, winner_id]}})


@pytest.mark.asyncio
async def test_multi_item_listing_transitions_with_per_lot_winner(db):
    """A multi-item listing whose auction_end_date passed and that has
    at least one lot with `highest_bidder_id` must:
      • flip the parent doc to status=ended + stamp sold_at
      • per-lot stamp winner_user_id, sold_at, final_price, status=sold
      • emit bilingual auction_won + auction_ended notifications
    """
    from motor.motor_asyncio import AsyncIOMotorClient
    from routes.auctions import process_ended_auctions, set_db

    mdb = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
    set_db(mdb)

    seller_id = f"iter296-mlseller-{uuid.uuid4().hex[:8]}"
    winner_id = f"iter296-mlwinner-{uuid.uuid4().hex[:8]}"
    listing_id = f"iter296-ml-{uuid.uuid4().hex[:8]}"
    past = datetime.now(timezone.utc) - timedelta(minutes=5)

    await mdb.users.insert_one({"id": seller_id, "email": "ms@t.com", "name": "Seller M"})
    await mdb.users.insert_one({"id": winner_id, "email": "mw@t.com", "name": "Winner ML"})
    await mdb.multi_item_listings.insert_one({
        "id": listing_id, "title": "iter296 Lots Auction",
        "seller_id": seller_id, "status": "active",
        "auction_end_date": past,
        "lots": [
            {"lot_number": 1, "current_price": 100.0, "highest_bidder_id": winner_id,
             "title": "Lot 1"},
            {"lot_number": 2, "current_price": 0.0, "highest_bidder_id": None,
             "title": "Lot 2"},   # no winner
        ],
    })

    try:
        with patch("services.email_notifications.send_auction_won_email", new=AsyncMock(return_value={"ok": True})), \
             patch("services.email_notifications.send_seller_auction_sold_email", new=AsyncMock(return_value={"ok": True})):
            await process_ended_auctions()

        doc = await mdb.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
        assert doc["status"] == "ended"
        assert doc["sold_at"] is not None    # at least one lot sold
        lots = {l["lot_number"]: l for l in doc["lots"]}
        # Lot 1 — sold
        assert lots[1]["winner_user_id"] == winner_id
        assert lots[1]["status"] == "sold"
        assert float(lots[1]["final_price"]) == 100.0
        # Lot 2 — ended (no winner)
        assert lots[2].get("winner_user_id") is None

        notifs = await mdb.notifications.find(
            {"data.listing_id": listing_id},
            {"_id": 0},
        ).to_list(10)
        assert len(notifs) >= 2
        for n in notifs:
            assert n.get("title_fr") and n.get("message_fr")
    finally:
        await mdb.multi_item_listings.delete_one({"id": listing_id})
        await mdb.notifications.delete_many({"data.listing_id": listing_id})
        await mdb.users.delete_many({"id": {"$in": [seller_id, winner_id]}})


# ── BUG 5 / Seller dashboard counters ──────────────────────────────────

def test_seller_dashboard_counters_union_both_end_conventions(db):
    """`/api/listings/my-listings` `counts.sold` must include listings
    with `status: ended` AND `winner_user_id` set (marketplace flow)
    in addition to `status: sold` (vehicle/storage flow)."""
    r_login = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=15,
    )
    assert r_login.status_code == 200
    token = r_login.json().get("access_token") or r_login.json().get("token")

    r = requests.get(
        f"{BASE_URL}/api/listings/my-listings",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text[:300]
    data = r.json()
    counts = data["counts"]
    # The actual seller has ≥1 ended-with-winner item ("table test"),
    # which must show in BOTH `ended` and `sold` counters.
    assert counts["ended"] >= 1, f"counts={counts}"
    assert counts["sold"]  >= 1, f"counts={counts}"


# ── BUG 1 / iter296_data_repair backfill ───────────────────────────────

@pytest.mark.asyncio
async def test_iter296_repair_backfills_missing_winner_user_id(db):
    """One-shot startup repair must stamp `winner_user_id`/`sold_at`/
    `final_price` on legacy ended listings that have `highest_bidder_id`
    but no iter296 fields. Idempotent — second run is a no-op."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from services.iter296_data_repair import run_iter296_listing_repair

    mdb = AsyncIOMotorClient(MONGO_URL)[DB_NAME]
    listing_id = f"iter296-legacy-{uuid.uuid4().hex[:8]}"
    winner = f"iter296-legacy-winner-{uuid.uuid4().hex[:8]}"
    # No winner_user_id / sold_at / final_price — simulates a pre-iter296
    # legacy ended listing.
    await mdb.listings.insert_one({
        "id": listing_id, "title": "legacy",
        "seller_id": "seller", "status": "ended",
        "highest_bidder_id": winner, "current_price": 5.5,
        "ended_at": "2026-01-01T00:00:00+00:00",
    })

    try:
        out = await run_iter296_listing_repair(mdb)
        assert out["marketplace"] >= 1

        fixed = await mdb.listings.find_one({"id": listing_id}, {"_id": 0})
        assert fixed["winner_user_id"] == winner
        assert fixed["sold_at"]
        assert float(fixed["final_price"]) == 5.5

        # Idempotent: re-running should not double-update.
        out2 = await run_iter296_listing_repair(mdb)
        # Either marketplace stays at 0 OR the doc is not in the cursor.
        assert out2["marketplace"] == 0
    finally:
        await mdb.listings.delete_one({"id": listing_id})


# ── BUG 1 / Stripe SDK compat ──────────────────────────────────────────

def test_stripe_error_references_use_modern_sdk():
    """`stripe.error.StripeError` is removed in Stripe SDK v8+. None of
    the production files may import via the legacy path or the
    AttributeError crash returns at settlement time."""
    import re
    import pathlib

    root = pathlib.Path("/app/backend")
    bad = []
    for p in root.rglob("*.py"):
        if "/tests/" in str(p) or "__pycache__" in str(p):
            continue
        text = p.read_text()
        for m in re.finditer(r"stripe\.error\.([A-Z][A-Za-z]+)", text):
            # Skip comments / docstrings — only flag real attribute access.
            line_start = text.rfind("\n", 0, m.start()) + 1
            line = text[line_start:text.find("\n", m.end())]
            if line.lstrip().startswith("#"):
                continue
            bad.append((str(p), m.group(0)))
    assert not bad, f"legacy stripe.error.* usages still present: {bad}"
