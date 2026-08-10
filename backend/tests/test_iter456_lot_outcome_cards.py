"""
iter456 — Lot-level outcome cards regression suite.

Locks in the fix so future work can never re-collapse a multi-item
Sold/No Sale card into one ambiguous parent row.

Coverage:
  A. Mixed-outcome multi-item (sold + partially-sold + unsold) →
     one lot_outcomes entry per lot with the right outcome_status,
     lot_title, parent_title, quantity_sold/remaining, hammer_total.
  B. Single-listing outcome → one row, listing_type="single".
  C. Orphan seller_statement receipt → row with is_historical=True,
     listing_type="historical", receipt_id set.
  D. Ended-tab split counts (sold / no_sale / payment_collected /
     payment_failed / completed) derived from lot_outcomes match the
     dashboard `counts` object exactly.
  E. Payment Collected is a SUBSET of Sold.
  F. Historical settlements NEVER labeled "Lot 1".
  G. Bilingual invariant — /api/dashboard/seller?lang=en and ?lang=fr
     return identical counts and identical outcome_status values.
"""
from __future__ import annotations
import asyncio, os, sys, uuid
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


@pytest.fixture(scope="module")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()
    asyncio.set_event_loop(policy.new_event_loop())


@pytest.fixture(scope="module")
def db(event_loop):
    c = AsyncIOMotorClient(MONGO_URL)
    yield c[DB_NAME]
    c.close()


@pytest.fixture(scope="module")
def app_client():
    from server import app
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


@pytest.fixture(scope="module")
def admin(event_loop, db):
    async def _f():
        return await db.users.find_one({"email": "charbel911@gmail.com"})
    return event_loop.run_until_complete(_f())


@pytest.fixture(scope="module")
def token(event_loop, app_client):
    async def _f():
        r = await app_client.post(
            "/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        )
        assert r.status_code == 200, r.text
        return r.json().get("access_token") or r.json().get("token")
    return event_loop.run_until_complete(_f())


@pytest.fixture
def auth(token):
    return {"Authorization": f"Bearer {token}"}


async def _clear(db):
    await db.multi_item_listings.delete_many({"id": {"$regex": "^iter456-"}})
    await db.listings.delete_many({"id": {"$regex": "^iter456-"}})
    await db.receipts.delete_many({"id": {"$regex": "^iter456-"}})


def _multi(seller_id, lots, **extra):
    d = {
        "id": f"iter456-{uuid.uuid4().hex[:10]}",
        "seller_id": seller_id,
        "title": "iter456 multi",
        "description": "-",
        "city": "Montreal", "region": "QC", "location": "-",
        "auction_start_date": "2026-02-01T00:00:00+00:00",
        "auction_end_date":   "2026-02-07T00:00:00+00:00",
        "listing_type": "multi_item",
        "buyer_premium_pct": 5.0, "commission_rate": 4.0,
        "tax_rate_gst": 5.0, "tax_rate_qst": 9.975,
        "currency": "CAD", "premium_percentage": 5.0,
        "multiply_hammer_by_quantity": True,
        "status": "ended",
        "lots": lots,
    }
    d.update(extra)
    return d


# ─── Scenarios ─────────────────────────────────────────────

class TestScenarioA_MixedMultiItem:
    def test_A1_one_row_per_lot_with_correct_shape(
        self, event_loop, db, admin, app_client, auth
    ):
        async def _run():
            await _clear(db)
            doc = _multi(admin["id"], [
                {"lot_number": 1, "title": "Wrenches",
                 "description": "SAE + metric",
                 "quantity": 1, "sold_quantity": 0,
                 "starting_price": 5.0, "current_price": 45.0,
                 "final_price": 45.0, "winning_unit_price": 45.0,
                 "winner_user_id": "buyer-A",
                 "winning_quantity": 1,
                 "payment_status": "payment_collected",
                 "lot_status": "sold", "status": "sold"},
                {"lot_number": 2, "title": "Screwdrivers",
                 "description": "12-piece",
                 "quantity": 5, "sold_quantity": 2, "available_quantity": 3,
                 "starting_price": 5.0, "current_price": 8.0,
                 "buy_now_price": 8.0, "buy_now_enabled": True,
                 "lot_status": "partially_sold", "status": "ended"},
                {"lot_number": 3, "title": "Level",
                 "description": "24-inch",
                 "quantity": 1, "sold_quantity": 0,
                 "starting_price": 20.0, "current_price": 20.0,
                 "lot_status": "ended", "status": "ended"},
            ])
            await db.multi_item_listings.insert_one(doc)
            try:
                r = await app_client.get(
                    "/api/dashboard/seller", headers=auth)
                data = r.json()
                outs = [o for o in data["lot_outcomes"]
                        if o.get("listing_id") == doc["id"]]
                assert len(outs) == 3
                m = {o["lot_number"]: o for o in outs}
                # Lot 1 - Sold + Payment Collected
                assert m[1]["outcome_status"] == "sold"
                assert m[1]["lot_title"] == "Wrenches"
                assert m[1]["parent_title"] == "iter456 multi"
                assert m[1]["payment_status"] == "payment_collected"
                assert m[1]["quantity_sold"] == 1
                assert m[1]["hammer_total"] == 45.00
                assert m[1]["listing_type"] == "multi_item"
                # Lot 2 - Sold via Buy-Now (partial)
                assert m[2]["outcome_status"] == "sold"
                assert m[2]["quantity_sold"] == 2
                assert m[2]["quantity_remaining"] == 3
                assert m[2]["hammer_total"] == 16.00   # $8 × 2
                # Lot 3 - No Sale
                assert m[3]["outcome_status"] == "no_sale"
                assert m[3]["hammer_total"] == 0.0
                assert m[3]["lot_title"] == "Level"
            finally:
                await _clear(db)
        event_loop.run_until_complete(_run())


class TestScenarioB_SingleListing:
    def test_B1_single_listing_produces_one_outcome_row(
        self, event_loop, db, admin, app_client, auth
    ):
        async def _run():
            await _clear(db)
            d = {
                "id": f"iter456-single-{uuid.uuid4().hex[:8]}",
                "seller_id": admin["id"],
                "title": "iter456 single",
                "description": "-",
                "category": "other", "condition": "used",
                "location": "Montreal, QC",
                "city": "Montreal", "region": "QC",
                "starting_price": 50.0, "current_price": 75.0,
                "final_price": 75.0,
                "auction_start_date": "2026-02-01T00:00:00+00:00",
                "auction_end_date":   "2026-02-07T00:00:00+00:00",
                "status": "sold",
                "winner_user_id": "buyer-B",
                "payment_status": "payment_collected",
                "images": [],
            }
            await db.listings.insert_one(d)
            try:
                r = await app_client.get(
                    "/api/dashboard/seller", headers=auth)
                outs = [o for o in r.json()["lot_outcomes"]
                        if o.get("listing_id") == d["id"]]
                assert len(outs) == 1
                o = outs[0]
                assert o["listing_type"] == "single"
                assert o["lot_number"] is None
                assert o["outcome_status"] == "sold"
                assert o["payment_status"] == "payment_collected"
                assert o["hammer_total"] == 75.00
                assert o["lot_title"] == "iter456 single"
            finally:
                await _clear(db)
        event_loop.run_until_complete(_run())


class TestScenarioC_HistoricalReceipt:
    def test_C1_orphan_receipt_becomes_historical_row(
        self, event_loop, db, admin, app_client, auth
    ):
        async def _run():
            await _clear(db)
            rid = f"iter456-r-{uuid.uuid4().hex[:6]}"
            await db.receipts.insert_one({
                "id": rid,
                "type": "seller_statement",
                "user_id": admin["id"],
                "listing_id": f"iter456-purged-{uuid.uuid4().hex[:6]}",
                "listing_title": "iter456 purged auction",
                "buyer_id": "hist-buyer",
                "hammer_price": 250.00,
                "total_charged": 262.50,
                "net_payout": 240.00,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            try:
                r = await app_client.get(
                    "/api/dashboard/seller", headers=auth)
                outs = [o for o in r.json()["lot_outcomes"]
                        if o.get("receipt_id") == rid]
                assert len(outs) == 1
                o = outs[0]
                assert o["listing_type"] == "historical"
                assert o["is_historical"] is True
                assert o["outcome_status"] == "sold"
                # Historical rows must NEVER be labeled "Lot 1".
                assert o["lot_number"] is None
                assert "Historical settlement" == o["lot_title"]
                assert o["net_payout_amount"] == 240.0
            finally:
                await _clear(db)
        event_loop.run_until_complete(_run())


class TestScenarioD_CountsMatchOutcomes:
    def test_D1_ended_split_counts_from_outcomes(
        self, event_loop, db, admin, app_client, auth
    ):
        async def _run():
            await _clear(db)
            doc = _multi(admin["id"], [
                {"lot_number": 1, "title": "A", "description": "-",
                 "quantity": 1, "sold_quantity": 0,
                 "starting_price": 5.0, "current_price": 45.0,
                 "final_price": 45.0, "winner_user_id": "buyer-x",
                 "winning_quantity": 1,
                 "payment_status": "payment_collected",
                 "lot_status": "sold", "status": "sold"},
                {"lot_number": 2, "title": "B", "description": "-",
                 "quantity": 1, "sold_quantity": 0,
                 "starting_price": 5.0, "current_price": 20.0,
                 "final_price": 20.0, "winner_user_id": "buyer-y",
                 "winning_quantity": 1,
                 "payment_status": "payment_failed",
                 "lot_status": "sold", "status": "sold"},
                {"lot_number": 3, "title": "C", "description": "-",
                 "quantity": 1, "sold_quantity": 0,
                 "starting_price": 5.0, "current_price": 5.0,
                 "lot_status": "ended", "status": "ended"},
            ])
            await db.multi_item_listings.insert_one(doc)
            try:
                r = await app_client.get(
                    "/api/dashboard/seller", headers=auth)
                data = r.json()
                outs = data["lot_outcomes"]
                counts = data["counts"]
                # Derived counts using the same predicates as frontend
                sold_ct = sum(1 for o in outs if o["outcome_status"] in ("sold", "completed"))
                pc_ct = sum(1 for o in outs
                            if o["outcome_status"] in ("sold", "completed")
                            and o.get("payment_status") == "payment_collected")
                pf_ct = sum(1 for o in outs
                            if o["outcome_status"] in ("sold", "completed")
                            and o.get("payment_status") in ("payment_failed",
                                                            "payment_failed_final"))
                ns_ct = sum(1 for o in outs if o["outcome_status"] == "no_sale")
                comp_ct = sum(1 for o in outs
                              if o["outcome_status"] == "completed"
                              or (o.get("pickup_confirmed")
                                  and o.get("payment_status") == "payment_collected"))
                assert counts["sold"] == sold_ct
                assert counts["ended_no_sale"] == ns_ct
                assert counts["payment_collected"] == pc_ct
                assert counts["payment_failed"] == pf_ct
                assert counts["completed"] == comp_ct
                assert counts["ended"] == len(outs)
                # Payment Collected ⊆ Sold
                pc_ids = {o["outcome_id"] for o in outs
                          if o["outcome_status"] in ("sold", "completed")
                          and o.get("payment_status") == "payment_collected"}
                sold_ids = {o["outcome_id"] for o in outs
                            if o["outcome_status"] in ("sold", "completed")}
                assert pc_ids.issubset(sold_ids)
            finally:
                await _clear(db)
        event_loop.run_until_complete(_run())


class TestScenarioE_BilingualStable:
    def test_E1_lang_agnostic_outcomes(
        self, event_loop, db, admin, app_client, auth
    ):
        async def _run():
            await _clear(db)
            doc = _multi(admin["id"], [
                {"lot_number": 1, "title": "Wrenches", "description": "-",
                 "quantity": 1, "sold_quantity": 0,
                 "starting_price": 5.0, "current_price": 45.0,
                 "final_price": 45.0, "winner_user_id": "buyer-z",
                 "winning_quantity": 1,
                 "payment_status": "payment_collected",
                 "lot_status": "sold", "status": "sold"},
            ])
            await db.multi_item_listings.insert_one(doc)
            try:
                r_en = await app_client.get(
                    "/api/dashboard/seller?lang=en", headers=auth)
                r_fr = await app_client.get(
                    "/api/dashboard/seller?lang=fr", headers=auth)
                en = r_en.json()
                fr = r_fr.json()
                assert en["counts"] == fr["counts"]
                # outcome_id / outcome_status / hammer_total / quantity fields
                # must be identical
                en_out = {o["outcome_id"]: o for o in en["lot_outcomes"]}
                fr_out = {o["outcome_id"]: o for o in fr["lot_outcomes"]}
                assert set(en_out) == set(fr_out)
                for k in en_out:
                    assert en_out[k]["outcome_status"] == fr_out[k]["outcome_status"]
                    assert en_out[k]["hammer_total"]   == fr_out[k]["hammer_total"]
                    assert en_out[k]["quantity_sold"]  == fr_out[k]["quantity_sold"]
                    assert en_out[k]["payment_status"] == fr_out[k]["payment_status"]
            finally:
                await _clear(db)
        event_loop.run_until_complete(_run())


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
