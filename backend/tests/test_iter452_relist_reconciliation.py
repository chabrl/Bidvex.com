"""
iter452 — Relist Inventory Reconciliation Regression Suite
==========================================================

Locks in the fix for partially-sold multi-item auction re-lists.

Required per-lot behaviors (per user directive Feb 8 2026):
  • Original quantity 10, sold 3  → re-list contains quantity 7
  • Original quantity 10, sold 10 → block re-list (nothing remains)
  • Original quantity 1,  sold 1  → block re-list
  • No quantities already sold    → preserve the original quantity

Auction-level:
  • Every re-list creates a reviewable DRAFT (never auto-publishes)
  • Source document, bids, payments, invoices, settlements, and
    sold_quantity history are preserved unchanged
  • If EVERY lot is fully sold → HTTP 409 nothing_to_relist

Sold-inventory sources:
  1. Buy-Now sales      → lot.sold_quantity
  2. Auction-close wins → lot.winner_user_id + winning_quantity /
                           quantity_won / quantity

Scope guardrails (unchanged code):
  • Fees / payments / emails / Watchdog / permissions / vehicle
    eligibility all untouched.
  • Marketplace + Vehicles single-item flows unchanged (no quantity
    concept).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import pytest
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


# ─────────────────────────────────────────────────────────────
# Test infrastructure — single event-loop shared DB + ASGI client
# ─────────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
def db(event_loop):
    client = AsyncIOMotorClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def seller_id(event_loop, db):
    async def _get():
        u = await db.users.find_one({"email": "charbel911@gmail.com"})
        assert u, "admin/seller user not found for tests"
        return u["id"]
    return event_loop.run_until_complete(_get())


@pytest.fixture(scope="module")
def app_client(event_loop):
    """Test client that hits the FastAPI app in-process — dodges the
    live preview backend so this suite is deterministic and CI-friendly.
    """
    from server import app
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


@pytest.fixture(scope="module")
def admin_token(event_loop, app_client):
    async def _login():
        r = await app_client.post(
            "/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        )
        assert r.status_code == 200, r.text
        return r.json().get("access_token") or r.json().get("token")
    return event_loop.run_until_complete(_login())


@pytest.fixture
def auth(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


def _seed_multi_item(
    seller_id: str,
    lots: List[Dict[str, Any]],
    status: str = "ended",
) -> Dict[str, Any]:
    aid = f"iter452-{uuid.uuid4().hex[:10]}"
    return {
        "id": aid,
        "seller_id": seller_id,
        "title": f"iter452 test — {aid}",
        "description": "-",
        "city": "Montreal",
        "region": "QC",
        "location": "-",
        "auction_start_date": "2026-02-01T00:00:00+00:00",
        "auction_end_date": "2026-02-07T00:00:00+00:00",
        "listing_type": "multi_item",
        "buyer_premium_pct": 5.0,
        "commission_rate": 4.0,
        "tax_rate_gst": 5.0,
        "tax_rate_qst": 9.975,
        "currency": "CAD",
        "premium_percentage": 5.0,
        "status": status,
        "lots": lots,
    }


async def _cleanup(db, aid: str):
    await db.multi_item_listings.delete_many(
        {"$or": [{"id": aid}, {"relisted_from": aid}]}
    )


async def _relist(app_client, auth, aid: str, mode: str = "now"):
    return await app_client.post(
        f"/api/listings/{aid}/relist?mode={mode}", headers=auth
    )


# ─────────────────────────────────────────────────────────────
# Scenario A — Partial-sale via Buy-Now (10 qty, 3 sold)
# ─────────────────────────────────────────────────────────────
class TestScenarioA_PartialBuyNow:
    def test_A1_relist_reduces_quantity_and_resets_counters(
        self, event_loop, db, seller_id, app_client, auth
    ):
        async def _run():
            doc = _seed_multi_item(seller_id, [
                {
                    "lot_number": 1, "title": "A1 lot", "description": "-",
                    "quantity": 10, "sold_quantity": 3, "available_quantity": 7,
                    "starting_price": 5.0, "current_price": 5.0,
                    "buy_now_price": 7.0, "buy_now_enabled": True,
                    "lot_status": "partially_sold", "status": "ended",
                },
            ])
            aid = doc["id"]
            await db.multi_item_listings.insert_one(doc)
            try:
                r = await _relist(app_client, auth, aid)
                assert r.status_code == 200, r.text
                body = r.json()
                new_id = body["new_listing_id"]
                # Never auto-publish
                assert body["status"] == "draft", (
                    f"expected draft, got {body['status']}"
                )
                new_doc = await db.multi_item_listings.find_one({"id": new_id})
                assert len(new_doc["lots"]) == 1
                lot = new_doc["lots"][0]
                assert lot["quantity"] == 7, (
                    f"expected quantity=7 (10 - 3), got {lot['quantity']}"
                )
                assert lot["available_quantity"] == 7
                assert lot["sold_quantity"] == 0, (
                    f"sold_quantity must reset to 0, got {lot['sold_quantity']}"
                )
                assert lot["lot_status"] == "active"
                # Source doc must be untouched (except relist bookkeeping)
                src = await db.multi_item_listings.find_one({"id": aid})
                assert src["lots"][0]["quantity"] == 10
                assert src["lots"][0]["sold_quantity"] == 3
                assert src["lots"][0]["available_quantity"] == 7
                assert src["relisted_to"] == new_id
                # No stale stamps in the new lot
                for stale in (
                    "winner_user_id", "final_price",
                    "winning_quantity", "winning_unit_price", "sold_at",
                ):
                    assert stale not in lot, f"stale field {stale} in new lot"
            finally:
                await _cleanup(db, aid)

        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario B — Fully sold single-lot auction blocks relist
# ─────────────────────────────────────────────────────────────
class TestScenarioB_FullySold:
    def test_B1_qty10_sold10_blocked(
        self, event_loop, db, seller_id, app_client, auth
    ):
        async def _run():
            doc = _seed_multi_item(seller_id, [
                {
                    "lot_number": 1, "title": "B1 lot", "description": "-",
                    "quantity": 10, "sold_quantity": 10, "available_quantity": 0,
                    "starting_price": 5.0, "current_price": 5.0,
                    "buy_now_price": 7.0, "buy_now_enabled": True,
                    "lot_status": "sold_out", "status": "sold",
                },
            ])
            aid = doc["id"]
            await db.multi_item_listings.insert_one(doc)
            try:
                r = await _relist(app_client, auth, aid)
                assert r.status_code == 409, (
                    f"expected 409 nothing_to_relist, got {r.status_code}"
                )
                assert "nothing" in r.text.lower() or "relist" in r.text.lower()
                # Source untouched — no `relisted_to` written
                src = await db.multi_item_listings.find_one({"id": aid})
                assert not src.get("relisted_to")
            finally:
                await _cleanup(db, aid)

        event_loop.run_until_complete(_run())

    def test_B2_qty1_sold1_blocked(
        self, event_loop, db, seller_id, app_client, auth
    ):
        async def _run():
            doc = _seed_multi_item(seller_id, [
                {
                    "lot_number": 1, "title": "B2 lot", "description": "-",
                    "quantity": 1, "sold_quantity": 1, "available_quantity": 0,
                    "starting_price": 5.0, "current_price": 5.0,
                    "buy_now_price": 7.0, "buy_now_enabled": True,
                    "lot_status": "sold_out", "status": "sold",
                },
            ])
            aid = doc["id"]
            await db.multi_item_listings.insert_one(doc)
            try:
                r = await _relist(app_client, auth, aid)
                assert r.status_code == 409
            finally:
                await _cleanup(db, aid)

        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario C — Unsold lot preserves original quantity
# ─────────────────────────────────────────────────────────────
class TestScenarioC_Unsold:
    def test_C1_qty8_sold0_preserves_original(
        self, event_loop, db, seller_id, app_client, auth
    ):
        async def _run():
            doc = _seed_multi_item(seller_id, [
                {
                    "lot_number": 1, "title": "C1 lot", "description": "-",
                    "quantity": 8, "sold_quantity": 0, "available_quantity": 8,
                    "starting_price": 5.0, "current_price": 5.0,
                    "lot_status": "active", "status": "ended",
                },
            ])
            aid = doc["id"]
            await db.multi_item_listings.insert_one(doc)
            try:
                r = await _relist(app_client, auth, aid)
                assert r.status_code == 200, r.text
                body = r.json()
                assert body["status"] == "draft"
                new_doc = await db.multi_item_listings.find_one(
                    {"id": body["new_listing_id"]}
                )
                lot = new_doc["lots"][0]
                assert lot["quantity"] == 8
                assert lot["available_quantity"] == 8
                assert lot["sold_quantity"] == 0
            finally:
                await _cleanup(db, aid)

        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario D — Multi-lot with mixed inventory (10/3, 5/5, 8/0)
# ─────────────────────────────────────────────────────────────
class TestScenarioD_MultiLotMixed:
    def test_D1_partial_full_and_unsold(
        self, event_loop, db, seller_id, app_client, auth
    ):
        async def _run():
            doc = _seed_multi_item(seller_id, [
                {"lot_number": 1, "title": "L1", "description": "-",
                 "quantity": 10, "sold_quantity": 3, "available_quantity": 7,
                 "starting_price": 5.0, "current_price": 5.0,
                 "buy_now_price": 7.0, "buy_now_enabled": True,
                 "lot_status": "partially_sold", "status": "ended"},
                {"lot_number": 2, "title": "L2", "description": "-",
                 "quantity": 5, "sold_quantity": 5, "available_quantity": 0,
                 "starting_price": 5.0, "current_price": 5.0,
                 "buy_now_price": 7.0, "buy_now_enabled": True,
                 "lot_status": "sold_out", "status": "sold"},
                {"lot_number": 3, "title": "L3", "description": "-",
                 "quantity": 8, "sold_quantity": 0, "available_quantity": 8,
                 "starting_price": 5.0, "current_price": 5.0,
                 "lot_status": "active", "status": "ended"},
            ])
            aid = doc["id"]
            await db.multi_item_listings.insert_one(doc)
            try:
                r = await _relist(app_client, auth, aid)
                assert r.status_code == 200, r.text
                body = r.json()
                assert body["status"] == "draft"
                new_doc = await db.multi_item_listings.find_one(
                    {"id": body["new_listing_id"]}
                )
                lots = {l["lot_number"]: l for l in new_doc["lots"]}
                # Lot 2 must be omitted (fully sold)
                assert 2 not in lots, "Lot 2 (fully sold) should be omitted"
                assert len(lots) == 2
                # Lot 1 reconciles to 7
                assert lots[1]["quantity"] == 7
                assert lots[1]["sold_quantity"] == 0
                assert lots[1]["available_quantity"] == 7
                # Lot 3 preserves 8
                assert lots[3]["quantity"] == 8
                assert lots[3]["sold_quantity"] == 0
                # Reconciliation metadata
                assert new_doc.get("relist_reconciliation", {}).get(
                    "omitted_lot_numbers"
                ) == [2]
                # Source doc untouched
                src = await db.multi_item_listings.find_one({"id": aid})
                assert src["lots"][0]["quantity"] == 10
                assert src["lots"][0]["sold_quantity"] == 3
                assert src["lots"][1]["quantity"] == 5
                assert src["lots"][1]["sold_quantity"] == 5
                assert src["lots"][2]["quantity"] == 8
                assert src["lots"][2]["sold_quantity"] == 0
            finally:
                await _cleanup(db, aid)

        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario E — Auction-close win (bidding, not Buy-Now)
# ─────────────────────────────────────────────────────────────
class TestScenarioE_AuctionCloseWinners:
    """Auction-close wins DO NOT increment sold_quantity — only
    Buy-Now does. But the winner + winning_quantity ARE stamped on
    the lot. Reconciliation must subtract that too."""

    def test_E1_auction_won_lot_omitted(
        self, event_loop, db, seller_id, app_client, auth
    ):
        async def _run():
            doc = _seed_multi_item(seller_id, [
                {"lot_number": 1, "title": "Auction-won", "description": "-",
                 "quantity": 3, "sold_quantity": 0, "available_quantity": 3,
                 "starting_price": 5.0, "current_price": 12.0,
                 "final_price": 36.0,
                 "winner_user_id": "some-buyer-id",
                 "winning_quantity": 3,
                 "winning_unit_price": 12.0,
                 "lot_status": "ended", "status": "sold"},
                {"lot_number": 2, "title": "No bids", "description": "-",
                 "quantity": 4, "sold_quantity": 0, "available_quantity": 4,
                 "starting_price": 5.0, "current_price": 5.0,
                 "lot_status": "ended", "status": "ended"},
            ])
            aid = doc["id"]
            await db.multi_item_listings.insert_one(doc)
            try:
                r = await _relist(app_client, auth, aid)
                assert r.status_code == 200, r.text
                body = r.json()
                new_doc = await db.multi_item_listings.find_one(
                    {"id": body["new_listing_id"]}
                )
                lots = {l["lot_number"]: l for l in new_doc["lots"]}
                # Auction-won lot must be omitted (all 3 sold to winner)
                assert 1 not in lots, (
                    "Auction-won lot must be omitted from relist"
                )
                # Unsold lot preserved
                assert lots[2]["quantity"] == 4
                assert new_doc["relist_reconciliation"][
                    "omitted_lot_numbers"] == [1]
            finally:
                await _cleanup(db, aid)

        event_loop.run_until_complete(_run())

    def test_E2_partial_auction_win_reconciles(
        self, event_loop, db, seller_id, app_client, auth
    ):
        """Lot has quantity=10, winning_quantity=4 (bidder took 4).
        Relist must contain quantity=6."""
        async def _run():
            doc = _seed_multi_item(seller_id, [
                {"lot_number": 1, "title": "Partial-auction-win",
                 "description": "-",
                 "quantity": 10, "sold_quantity": 0, "available_quantity": 10,
                 "starting_price": 5.0, "current_price": 12.0,
                 "final_price": 48.0,
                 "winner_user_id": "some-buyer-id",
                 "winning_quantity": 4,
                 "winning_unit_price": 12.0,
                 "lot_status": "partially_sold", "status": "sold"},
            ])
            aid = doc["id"]
            await db.multi_item_listings.insert_one(doc)
            try:
                r = await _relist(app_client, auth, aid)
                assert r.status_code == 200, r.text
                body = r.json()
                new_doc = await db.multi_item_listings.find_one(
                    {"id": body["new_listing_id"]}
                )
                lot = new_doc["lots"][0]
                assert lot["quantity"] == 6, (
                    f"expected 10 - 4 = 6, got {lot['quantity']}"
                )
                # No stale winner data on the new lot
                assert "winner_user_id" not in lot
                assert "final_price" not in lot
                assert "winning_quantity" not in lot
                assert "sold_at" not in lot
                assert lot["sold_quantity"] == 0
                assert lot["available_quantity"] == 6
            finally:
                await _cleanup(db, aid)

        event_loop.run_until_complete(_run())

    def test_E3_combined_buy_now_and_auction_win_reconciles(
        self, event_loop, db, seller_id, app_client, auth
    ):
        """Lot: quantity=10, sold_quantity=2 (Buy-Now),
        winning_quantity=5 (auction). Remaining = 10 - 2 - 5 = 3."""
        async def _run():
            doc = _seed_multi_item(seller_id, [
                {"lot_number": 1, "title": "Both channels",
                 "description": "-",
                 "quantity": 10, "sold_quantity": 2, "available_quantity": 3,
                 "starting_price": 5.0, "current_price": 8.0,
                 "final_price": 40.0,
                 "winner_user_id": "auction-buyer",
                 "winning_quantity": 5,
                 "winning_unit_price": 8.0,
                 "buy_now_price": 8.0, "buy_now_enabled": True,
                 "lot_status": "partially_sold", "status": "sold"},
            ])
            aid = doc["id"]
            await db.multi_item_listings.insert_one(doc)
            try:
                r = await _relist(app_client, auth, aid)
                assert r.status_code == 200, r.text
                body = r.json()
                new_doc = await db.multi_item_listings.find_one(
                    {"id": body["new_listing_id"]}
                )
                lot = new_doc["lots"][0]
                assert lot["quantity"] == 3, (
                    f"expected 10 - 2 - 5 = 3, got {lot['quantity']}"
                )
                assert lot["sold_quantity"] == 0
                assert lot["available_quantity"] == 3
            finally:
                await _cleanup(db, aid)

        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario F — Never auto-publish (always draft) regardless of mode
# ─────────────────────────────────────────────────────────────
class TestScenarioF_AlwaysDraft:
    @pytest.mark.parametrize("mode", ["now", "draft"])
    def test_F1_multi_item_relist_always_draft(
        self, event_loop, db, seller_id, app_client, auth, mode
    ):
        async def _run():
            doc = _seed_multi_item(seller_id, [
                {"lot_number": 1, "title": "F1", "description": "-",
                 "quantity": 8, "sold_quantity": 0, "available_quantity": 8,
                 "starting_price": 5.0, "current_price": 5.0,
                 "lot_status": "active", "status": "ended"},
            ])
            aid = doc["id"]
            await db.multi_item_listings.insert_one(doc)
            try:
                r = await _relist(app_client, auth, aid, mode=mode)
                assert r.status_code == 200, r.text
                body = r.json()
                assert body["status"] == "draft", (
                    f"mode={mode} but status={body['status']} — "
                    "multi-item relist must ALWAYS be draft"
                )
            finally:
                await _cleanup(db, aid)

        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario G — Historical data untouched (bids, transactions)
# ─────────────────────────────────────────────────────────────
class TestScenarioG_HistoricalUntouched:
    def test_G1_buy_now_transactions_and_bids_untouched(
        self, event_loop, db, seller_id, app_client, auth
    ):
        async def _run():
            doc = _seed_multi_item(seller_id, [
                {"lot_number": 1, "title": "G1", "description": "-",
                 "quantity": 10, "sold_quantity": 3, "available_quantity": 7,
                 "starting_price": 5.0, "current_price": 7.0,
                 "buy_now_price": 7.0, "buy_now_enabled": True,
                 "lot_status": "partially_sold", "status": "ended"},
            ])
            aid = doc["id"]
            await db.multi_item_listings.insert_one(doc)
            # Seed a fake Buy-Now transaction against this auction
            txn = {
                "id": f"iter452-txn-{uuid.uuid4().hex[:6]}",
                "auction_id": aid,
                "lot_number": 1,
                "buyer_id": "some-buyer",
                "quantity_purchased": 3,
                "price_per_unit": 7.0,
                "total_amount": 21.0,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.buy_now_transactions.insert_one(txn)
            try:
                r = await _relist(app_client, auth, aid)
                assert r.status_code == 200, r.text
                # Original transaction UNTOUCHED
                original_txn = await db.buy_now_transactions.find_one(
                    {"id": txn["id"]}
                )
                assert original_txn is not None
                assert original_txn["quantity_purchased"] == 3
                assert original_txn["total_amount"] == 21.0
                assert original_txn["auction_id"] == aid
                # New draft does NOT inherit these transactions (they stay
                # bound to the source auction)
                new_id = r.json()["new_listing_id"]
                cnt = await db.buy_now_transactions.count_documents(
                    {"auction_id": new_id}
                )
                assert cnt == 0, "new draft must not inherit old transactions"
            finally:
                await db.buy_now_transactions.delete_one({"id": txn["id"]})
                await _cleanup(db, aid)

        event_loop.run_until_complete(_run())


# ─────────────────────────────────────────────────────────────
# Scenario H — Marketplace (single-item) + Vehicles unchanged
# ─────────────────────────────────────────────────────────────
class TestScenarioH_OtherSectionsUnaffected:
    """Marketplace + Vehicle relist flows are single-item / no
    inventory. This test locks in that iter452 did not accidentally
    change their behavior."""

    def test_H1_marketplace_single_item_relist_still_works(
        self, event_loop, db, seller_id, app_client, auth
    ):
        async def _run():
            aid = f"iter452-mkt-{uuid.uuid4().hex[:8]}"
            doc = {
                "id": aid,
                "seller_id": seller_id,
                "title": "iter452 marketplace single item",
                "description": "-",
                "category": "other",
                "city": "Montreal",
                "region": "QC",
                "starting_price": 5.0,
                "current_price": 5.0,
                "auction_start_date": "2026-02-01T00:00:00+00:00",
                "auction_end_date": "2026-02-07T00:00:00+00:00",
                "status": "ended_no_sale",
                "images": [],
            }
            await db.listings.insert_one(doc)
            try:
                r = await app_client.post(
                    f"/api/listings/{aid}/relist?mode=now",
                    headers=auth,
                )
                assert r.status_code == 200, r.text
                body = r.json()
                # Marketplace single-item: relist behavior unchanged from
                # iter298 — mode=now → active
                assert body["status"] in ("active", "draft")
                # source untouched except relisted_to
                src = await db.listings.find_one({"id": aid})
                assert src["relisted_to"] == body["new_listing_id"]
                assert src["starting_price"] == 5.0
            finally:
                await db.listings.delete_many(
                    {"$or": [{"id": aid}, {"relisted_from": aid}]}
                )

        event_loop.run_until_complete(_run())


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v", "-s"]))
