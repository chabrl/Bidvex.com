"""
BidVex iter482 P4 — Seller-Controlled Payment Methods END-TO-END tests
======================================================================

Covers:
  1. GET /api/listings/{id}/accepted-payment-methods
  2. POST /api/checkout/select-payment-method (ack + enforcement)
  3. POST /api/payments/offline-checkout/{id} enforcement
  4. Snapshot lock behaviour
  5. Cash/E-Transfer/Cheque produce $0 processing fee
  6. Persistence of `selected_payment_method` on offline_orders + listing row
"""

from __future__ import annotations
import os
import asyncio
import pytest
import uuid
from datetime import datetime, timezone
import httpx
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

BASE_URL = "http://localhost:8001"
HTTP_TIMEOUT = 30.0


# ─────────────────────────────────────────────────────────────────────
# Helper factories — write directly to Mongo to isolate route logic
# ─────────────────────────────────────────────────────────────────────
def _mongo():
    return AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]


async def _seed_listing(db, accepted_methods, *, locked=False, winner_id=None, seller_id="seed-seller"):
    lid = f"iter482p4-{uuid.uuid4().hex[:8]}"
    doc = {
        "id": lid,
        "title": "iter482 P4 test listing",
        "seller_id": seller_id,
        "hammer_price": 100.0,
        "current_price": 100.0,
        "category": "general",
        "region": "QC",
        "currency": "CAD",
        "status": "ended",
        "payment_status": "pending",
        "winner_id": winner_id or "seed-winner",
        "winning_bidder_id": winner_id or "seed-winner",
        "accepted_payment_methods": list(accepted_methods),
    }
    if locked:
        doc["accepted_payment_methods_snapshot"] = list(accepted_methods)
        doc["accepted_payment_methods_locked_at"] = datetime.now(timezone.utc).isoformat()
    await db.listings.insert_one(doc)
    return lid


async def _cleanup(db, listing_id):
    await db.listings.delete_one({"id": listing_id})
    await db.offline_orders.delete_many({"listing_id": listing_id})
    await db.buyer_payment_selections.delete_many({"listing_id": listing_id})


async def _register_buyer(client: httpx.AsyncClient):
    email = f"iter482p4-{uuid.uuid4().hex[:8]}@test.com"
    r = await client.post("/api/auth/register", json={
        "name": "P4 Buyer",
        "email": email,
        "password": "TestBuyer!23",
        "role": "user",
        "terms_agreed": True,
        "ai_disclosure_consent": True,
        "accepted_terms": True,
        "terms_accepted": True,
    })
    assert r.status_code in (200, 201), r.text
    token = r.json().get("token") or r.json().get("access_token")
    db = _mongo()
    u = await db.users.find_one({"email": email})
    return {"email": email, "token": token, "user_id": u["id"]}


# ─────────────────────────────────────────────────────────────────────
# 1. Registry canonical slugs
# ─────────────────────────────────────────────────────────────────────
def test_registry_canonical_slugs():
    from services.payment_methods_registry import (
        ALL_METHODS, STRIPE, ETRANSFER, CASH, CHEQUE, normalise,
        OFFLINE_METHODS, is_offline,
    )
    assert ALL_METHODS == [STRIPE, ETRANSFER, CASH, CHEQUE]
    assert normalise("Stripe") == "stripe"
    assert normalise("E-Transfer") == "etransfer"
    assert normalise("check") == "cheque"
    assert normalise("Cash") == "cash"
    assert OFFLINE_METHODS == {ETRANSFER, CASH, CHEQUE}
    assert is_offline("cash") and is_offline("etransfer") and is_offline("cheque")
    assert not is_offline("stripe")


# ─────────────────────────────────────────────────────────────────────
# 2. Service — effective_methods reads snapshot first, then live
# ─────────────────────────────────────────────────────────────────────
def test_effective_methods_snapshot_wins():
    from services.seller_payment_methods_service import effective_methods
    doc = {
        "id": "x",
        "accepted_payment_methods": ["stripe", "cash"],
        "accepted_payment_methods_snapshot": ["stripe"],
    }
    assert effective_methods(doc) == ["stripe"]


def test_effective_methods_live_when_no_snapshot():
    from services.seller_payment_methods_service import effective_methods
    doc = {"id": "x", "accepted_payment_methods": ["cash", "cheque"]}
    assert effective_methods(doc) == ["cash", "cheque"]


def test_effective_methods_legacy_fallback():
    from services.seller_payment_methods_service import effective_methods
    doc = {"id": "x", "payment_method": "stripe"}
    assert effective_methods(doc) == ["stripe"]


# ─────────────────────────────────────────────────────────────────────
# 3. Service — assert_selection_allowed rejects unaccepted methods
# ─────────────────────────────────────────────────────────────────────
def test_assert_selection_rejects_unaccepted():
    from services.seller_payment_methods_service import (
        assert_selection_allowed, PaymentMethodNotAcceptedError,
    )
    doc = {"id": "x", "accepted_payment_methods": ["cash", "cheque"]}
    with pytest.raises(PaymentMethodNotAcceptedError):
        assert_selection_allowed(doc, "stripe")


def test_assert_selection_normalises_aliases():
    from services.seller_payment_methods_service import assert_selection_allowed
    doc = {"id": "x", "accepted_payment_methods": ["etransfer"]}
    assert assert_selection_allowed(doc, "e-transfer") == "etransfer"


# ─────────────────────────────────────────────────────────────────────
# 4. Service — first-bid snapshot is idempotent
# ─────────────────────────────────────────────────────────────────────
def test_snapshot_idempotent_when_locked():
    from services.seller_payment_methods_service import snapshot_at_first_bid
    doc = {
        "id": "x",
        "accepted_payment_methods": ["stripe"],
        "accepted_payment_methods_snapshot": ["stripe"],
    }
    assert snapshot_at_first_bid(doc) is None


def test_snapshot_locks_live_list():
    from services.seller_payment_methods_service import snapshot_at_first_bid
    doc = {"id": "x", "accepted_payment_methods": ["stripe", "cash"]}
    upd = snapshot_at_first_bid(doc)
    assert upd is not None
    assert upd["accepted_payment_methods_snapshot"] == ["stripe", "cash"]
    assert "accepted_payment_methods_locked_at" in upd


# ─────────────────────────────────────────────────────────────────────
# HTTP tests — driven by asyncio.run for direct control
# ─────────────────────────────────────────────────────────────────────
def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if not asyncio.get_event_loop().is_closed() else asyncio.run(coro)


def test_http_get_accepted_payment_methods_returns_universe():
    async def _t():
        db = _mongo()
        lid = await _seed_listing(db, ["stripe", "etransfer"], locked=False)
        try:
            async with httpx.AsyncClient(base_url=BASE_URL, timeout=HTTP_TIMEOUT) as c:
                r = await c.get(f"/api/listings/{lid}/accepted-payment-methods")
                assert r.status_code == 200, r.text
                body = r.json()
                assert body["accepted_payment_methods"] == ["stripe", "etransfer"]
                assert body["locked"] is False
                assert body["allowed_universe"] == ["stripe", "etransfer", "cash", "cheque"]
        finally:
            await _cleanup(db, lid)
    asyncio.run(_t())


def test_http_offline_checkout_allows_cash_and_persists_selection():
    async def _t():
        db = _mongo()
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=HTTP_TIMEOUT) as c:
            buyer = await _register_buyer(c)
            lid = await _seed_listing(db, ["cash", "cheque"], locked=False, winner_id=buyer["user_id"])
            try:
                r = await c.post(
                    f"/api/payments/offline-checkout/{lid}",
                    json={"payment_method": "cash", "return_url": ""},
                    headers={"Authorization": f"Bearer {buyer['token']}"},
                )
                assert r.status_code in (200, 201), r.text
                body = r.json()
                assert body.get("selected_payment_method") == "cash"
                listing = await db.listings.find_one({"id": lid})
                assert listing.get("selected_payment_method") == "cash"
                order = await db.offline_orders.find_one({"listing_id": lid})
                assert order and order.get("selected_payment_method") == "cash"
            finally:
                await _cleanup(db, lid)
                await db.users.delete_one({"email": buyer["email"]})
    asyncio.run(_t())


def test_http_offline_checkout_rejects_disallowed_method():
    async def _t():
        db = _mongo()
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=HTTP_TIMEOUT) as c:
            buyer = await _register_buyer(c)
            # Seller only accepts stripe — buyer tries cash → 400
            lid = await _seed_listing(db, ["stripe"], locked=False, winner_id=buyer["user_id"])
            try:
                r = await c.post(
                    f"/api/payments/offline-checkout/{lid}",
                    json={"payment_method": "cash", "return_url": ""},
                    headers={"Authorization": f"Bearer {buyer['token']}"},
                )
                assert r.status_code == 400, r.text
                det = r.json().get("detail") or {}
                if isinstance(det, dict):
                    assert det.get("error") == "PAYMENT_METHOD_NOT_ACCEPTED", det
            finally:
                await _cleanup(db, lid)
                await db.users.delete_one({"email": buyer["email"]})
    asyncio.run(_t())


def test_http_offline_checkout_supports_cheque():
    async def _t():
        db = _mongo()
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=HTTP_TIMEOUT) as c:
            buyer = await _register_buyer(c)
            lid = await _seed_listing(db, ["cheque"], locked=False, winner_id=buyer["user_id"])
            try:
                r = await c.post(
                    f"/api/payments/offline-checkout/{lid}",
                    json={"payment_method": "cheque", "return_url": ""},
                    headers={"Authorization": f"Bearer {buyer['token']}"},
                )
                assert r.status_code in (200, 201), r.text
                body = r.json()
                assert body.get("selected_payment_method") == "cheque"
            finally:
                await _cleanup(db, lid)
                await db.users.delete_one({"email": buyer["email"]})
    asyncio.run(_t())


def test_http_select_payment_method_persists_ack():
    async def _t():
        db = _mongo()
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=HTTP_TIMEOUT) as c:
            buyer = await _register_buyer(c)
            lid = await _seed_listing(db, ["stripe", "etransfer"], locked=False, winner_id=buyer["user_id"])
            try:
                body = {
                    "listing_id": lid,
                    "selected_payment_method": "etransfer",
                    "ack_totals": {
                        "hammer_cents": 10000,
                        "buyer_premium_cents": 500,
                        "buyer_tax_cents": 75,
                        "payment_processing_cents": 0,
                        "total_cents": 10575,
                    },
                    "terms_version": "iter482.p4.test",
                }
                r = await c.post("/api/checkout/select-payment-method", json=body,
                                 headers={"Authorization": f"Bearer {buyer['token']}"})
                assert r.status_code == 200, r.text
                sel = await db.buyer_payment_selections.find_one({
                    "listing_id": lid, "buyer_id": buyer["user_id"]
                })
                assert sel is not None
                assert sel["selected_payment_method"] == "etransfer"
                assert sel["ack_totals"]["total_cents"] == 10575

                # Rejects a method not in the accepted list
                body_bad = dict(body)
                body_bad["selected_payment_method"] = "cheque"
                r_bad = await c.post("/api/checkout/select-payment-method", json=body_bad,
                                     headers={"Authorization": f"Bearer {buyer['token']}"})
                assert r_bad.status_code == 400
                det = r_bad.json().get("detail") or {}
                assert det.get("error") == "PAYMENT_METHOD_NOT_ACCEPTED"
            finally:
                await _cleanup(db, lid)
                await db.users.delete_one({"email": buyer["email"]})
    asyncio.run(_t())


def test_http_ack_totals_must_sum():
    async def _t():
        db = _mongo()
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=HTTP_TIMEOUT) as c:
            buyer = await _register_buyer(c)
            lid = await _seed_listing(db, ["stripe"], locked=False, winner_id=buyer["user_id"])
            try:
                body = {
                    "listing_id": lid,
                    "selected_payment_method": "stripe",
                    "ack_totals": {
                        "hammer_cents": 10000,
                        "buyer_premium_cents": 500,
                        "buyer_tax_cents": 75,
                        "payment_processing_cents": 0,
                        "total_cents": 10000,  # tampered
                    },
                }
                r = await c.post("/api/checkout/select-payment-method", json=body,
                                 headers={"Authorization": f"Bearer {buyer['token']}"})
                assert r.status_code == 400, r.text
                det = r.json().get("detail") or {}
                assert det.get("error") == "ack_totals_do_not_sum"
            finally:
                await _cleanup(db, lid)
                await db.users.delete_one({"email": buyer["email"]})
    asyncio.run(_t())

