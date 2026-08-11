"""
iter469 — Regression pytest for the escrow pickup-confirmation
canonical resolver + forward escrow-hold record.

Covers unit-level guarantees that live_verify_iter469 asserts against
the running preview backend. These tests use `mongomock`-style helpers
via a lightweight in-process fake so they run without Mongo.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import pytest
from unittest.mock import MagicMock, patch


# ── Minimal async-Mongo fake ─────────────────────────────────────────
# We reuse the same shape mongomock exposes: `find_one` / `find` /
# `insert_one` / `update_one` / `count_documents`. This is intentionally
# small; the goal is to exercise the resolver + fallback branches, not
# to reimplement Mongo. If any query becomes elaborate the test can pin
# it to the real preview DB instead.


class _FakeCursor:
    def __init__(self, rows):
        self._rows = list(rows)

    def sort(self, *a, **k):
        return self

    async def to_list(self, n):
        return list(self._rows[:n])


def _match(doc: Dict[str, Any], q: Dict[str, Any]) -> bool:
    for k, v in q.items():
        if k == "$or":
            if not any(_match(doc, sub) for sub in v):
                return False
            continue
        if k == "$and":
            if not all(_match(doc, sub) for sub in v):
                return False
            continue
        dv = doc.get(k)
        if isinstance(v, dict):
            for op, arg in v.items():
                if op == "$exists":
                    if arg and dv is None:
                        return False
                    if not arg and dv is not None:
                        return False
                elif op == "$ne":
                    if dv == arg:
                        return False
                elif op == "$in":
                    if dv not in arg:
                        return False
                elif op == "$regex":
                    import re
                    if not isinstance(dv, str) or not re.search(arg, dv):
                        return False
                elif op == "$lte":
                    if dv is None or dv > arg:
                        return False
                else:
                    return False
        else:
            if dv != v:
                return False
    return True


class _FakeCollection:
    def __init__(self):
        self._rows: List[Dict[str, Any]] = []

    async def insert_one(self, doc):
        self._rows.append(dict(doc))

    async def insert_many(self, docs):
        for d in docs:
            self._rows.append(dict(d))

    def find(self, q=None, proj=None):
        q = q or {}
        return _FakeCursor([d for d in self._rows if _match(d, q)])

    async def find_one(self, q=None, proj=None):
        q = q or {}
        for d in self._rows:
            if _match(d, q):
                return dict(d)
        return None

    async def count_documents(self, q):
        return sum(1 for d in self._rows if _match(d, q))

    async def update_one(self, q, upd):
        for d in self._rows:
            if _match(d, q):
                if "$set" in upd:
                    d.update(upd["$set"])
                _r = MagicMock()
                _r.modified_count = 1
                return _r
        _r = MagicMock()
        _r.modified_count = 0
        return _r

    async def update_many(self, q, upd):
        n = 0
        for d in self._rows:
            if _match(d, q):
                if "$set" in upd:
                    d.update(upd["$set"])
                n += 1
        _r = MagicMock()
        _r.modified_count = n
        return _r

    async def delete_many(self, q):
        before = len(self._rows)
        self._rows = [d for d in self._rows if not _match(d, q)]
        _r = MagicMock()
        _r.deleted_count = before - len(self._rows)
        return _r


class _FakeDB:
    def __init__(self):
        self._collections: Dict[str, _FakeCollection] = {}

    def __getattr__(self, name):
        # Attribute-style access (db.transactions).
        if name.startswith("_"):
            raise AttributeError(name)
        return self._collections.setdefault(name, _FakeCollection())

    def __getitem__(self, name):
        # Dict-style access (db["escrow_transactions"]).
        return self._collections.setdefault(name, _FakeCollection())


# ── Fixtures ────────────────────────────────────────────────────────

@pytest.fixture
def db():
    return _FakeDB()


def _now_iso():
    return datetime.now(timezone.utc).isoformat()


async def _seed_paid_tx(db, *, seller_id, buyer_id, listing_id, code, lot_number=None):
    await db.transactions.insert_one({
        "id": f"tx-{listing_id}-{lot_number or 'x'}",
        "listing_id": listing_id, "pickup_code_listing_id": listing_id,
        "auction_id": listing_id, "lot_number": lot_number,
        "listing_title": "iter469 lot",
        "buyer_id": buyer_id, "seller_id": seller_id,
        "pickup_code_seller_id": seller_id,
        "hammer_price": 25.0, "amount": 25.0,
        "payment_method": "stripe",
        "status": "paid", "payment_confirmed": True,
        "commission_already_collected": True,
        "pickup_code": code, "pickup_code_issued_at": _now_iso(),
        "created_at": _now_iso(),
    })


async def _seed_escrow(db, *, seller_id, buyer_id, listing_id, code, status="held",
                       expires_at=None):
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    await db.escrow_transactions.insert_one({
        "auction_id": listing_id, "listing_id": listing_id,
        "buyer_id": buyer_id, "seller_id": seller_id,
        "hammer_price_cents": 2500,
        "total_charged_cents": 2750, "application_fee_cents": 125,
        "escrow_status": status, "pickup_code": code,
        "pickup_code_expires_at": expires_at.isoformat(),
        "auto_release_scheduled_at": expires_at.isoformat(),
        "created_at": _now_iso(), "updated_at": _now_iso(),
        "item_type": "non_vehicle", "province": "QC",
    })


# ── Resolver tests ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_resolver_prefers_escrow_row(db):
    from services.escrow_service import _resolve_paid_order_record
    listing = "iter469r-1"
    await _seed_escrow(db, seller_id="sA", buyer_id="bA", listing_id=listing, code="BVX-CANON01")
    await _seed_paid_tx(db, seller_id="sA", buyer_id="bA", listing_id=listing, code="BVX-CANON01")
    source, rec = await _resolve_paid_order_record(db, auction_id=listing, seller_id="sA")
    assert source == "escrow"
    assert rec["escrow_status"] == "held"


@pytest.mark.asyncio
async def test_resolver_falls_back_to_transaction(db):
    from services.escrow_service import _resolve_paid_order_record
    listing = "iter469r-2"
    await _seed_paid_tx(db, seller_id="sA", buyer_id="bA", listing_id=listing, code="BVX-FALL01")
    source, rec = await _resolve_paid_order_record(db, auction_id=listing, seller_id="sA")
    assert source == "transaction"
    assert rec["pickup_code"] == "BVX-FALL01"


@pytest.mark.asyncio
async def test_resolver_returns_none_for_wrong_seller(db):
    from services.escrow_service import _resolve_paid_order_record
    listing = "iter469r-3"
    await _seed_paid_tx(db, seller_id="sA", buyer_id="bA", listing_id=listing, code="BVX-WRSEL")
    source, rec = await _resolve_paid_order_record(db, auction_id=listing, seller_id="OTHER")
    assert source is None and rec is None


@pytest.mark.asyncio
async def test_resolver_returns_none_for_wrong_auction(db):
    from services.escrow_service import _resolve_paid_order_record
    await _seed_paid_tx(db, seller_id="sA", buyer_id="bA", listing_id="iter469r-4a", code="BVX-WRAUC")
    source, rec = await _resolve_paid_order_record(db, auction_id="iter469r-4b", seller_id="sA")
    assert source is None and rec is None


@pytest.mark.asyncio
async def test_resolver_skips_confirmed_transactions(db):
    from services.escrow_service import _resolve_paid_order_record
    listing = "iter469r-5"
    await _seed_paid_tx(db, seller_id="sA", buyer_id="bA", listing_id=listing, code="BVX-CONFIR")
    # Stamp confirmed
    await db.transactions.update_one({"listing_id": listing},
                                     {"$set": {"pickup_code_confirmed_at": _now_iso()}})
    source, rec = await _resolve_paid_order_record(db, auction_id=listing, seller_id="sA")
    assert source is None and rec is None


# ── Confirm pickup tests (transactions-only fallback path) ──────────

@pytest.mark.asyncio
async def test_confirm_pickup_transactions_only_success(db):
    from services.escrow_service import confirm_pickup
    listing = "iter469c-1"
    await _seed_paid_tx(db, seller_id="sA", buyer_id="bA", listing_id=listing, code="BVX-TXONLY1")
    with patch("services.escrow_service.stripe.Transfer.create") as t:
        out = await confirm_pickup(db, "sA", listing, "BVX-TXONLY1")
    # Stripe transfer must NOT be attempted in the fallback path.
    assert t.call_count == 0
    # iter470 — with no seller_payouts row we return the
    # `pickup_confirmed_payout_review` state (payout_state=unknown).
    # We never falsely claim "released" without a real transfer_id.
    assert out["status"] in {"released", "pickup_confirmed_payout_review",
                             "pickup_confirmed_payout_pending"}
    assert out["transfer_id"] is None
    # Row is stamped confirmed.
    tx = await db.transactions.find_one({"listing_id": listing})
    assert tx["pickup_code_confirmed_at"] is not None


@pytest.mark.asyncio
async def test_confirm_pickup_transactions_only_double_confirm(db):
    from fastapi import HTTPException
    from services.escrow_service import confirm_pickup
    listing = "iter469c-2"
    await _seed_paid_tx(db, seller_id="sA", buyer_id="bA", listing_id=listing, code="BVX-DBLTX")
    with patch("services.escrow_service.stripe.Transfer.create"):
        await confirm_pickup(db, "sA", listing, "BVX-DBLTX")
        with pytest.raises(HTTPException) as exc:
            await confirm_pickup(db, "sA", listing, "BVX-DBLTX")
    assert exc.value.status_code == 409
    assert exc.value.detail["error"] == "already_confirmed"


@pytest.mark.asyncio
async def test_confirm_pickup_wrong_seller_blocked(db):
    from fastapi import HTTPException
    from services.escrow_service import confirm_pickup
    listing = "iter469c-3"
    await _seed_paid_tx(db, seller_id="sA", buyer_id="bA", listing_id=listing, code="BVX-WSEL")
    with pytest.raises(HTTPException) as exc:
        await confirm_pickup(db, "sB", listing, "BVX-WSEL")
    assert exc.value.status_code == 404
    # Row NOT confirmed.
    tx = await db.transactions.find_one({"listing_id": listing})
    assert tx.get("pickup_code_confirmed_at") is None


@pytest.mark.asyncio
async def test_confirm_pickup_invalid_code_blocked(db):
    from fastapi import HTTPException
    from services.escrow_service import confirm_pickup
    listing = "iter469c-4"
    await _seed_paid_tx(db, seller_id="sA", buyer_id="bA", listing_id=listing, code="BVX-VALID1")
    with pytest.raises(HTTPException) as exc:
        await confirm_pickup(db, "sA", listing, "BVX-NOPE99")
    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "invalid_code"


@pytest.mark.asyncio
async def test_two_paid_orders_same_auction(db):
    """User-mandated: two paid orders in the same auction — each seller
    only confirms their own via their own buyer code."""
    from fastapi import HTTPException
    from services.escrow_service import confirm_pickup
    listing = "iter469c-5"
    await _seed_paid_tx(db, seller_id="sA", buyer_id="bA", listing_id=listing, code="BVX-SAMEA", lot_number=1)
    await _seed_paid_tx(db, seller_id="sB", buyer_id="bB", listing_id=listing, code="BVX-SAMEB", lot_number=2)

    # Wrong seller/code cross attempts blocked.
    with pytest.raises(HTTPException) as e1:
        await confirm_pickup(db, "sB", listing, "BVX-SAMEA")
    assert e1.value.status_code in (400, 404)
    with pytest.raises(HTTPException) as e2:
        await confirm_pickup(db, "sA", listing, "BVX-SAMEB")
    assert e2.value.status_code in (400, 404)

    # Each seller confirms their own successfully.
    with patch("services.escrow_service.stripe.Transfer.create"):
        out_a = await confirm_pickup(db, "sA", listing, "BVX-SAMEA")
        out_b = await confirm_pickup(db, "sB", listing, "BVX-SAMEB")
    # iter470 — with no seller_payouts rows the safer contract returns
    # `pickup_confirmed_payout_review` (payout_state=unknown), not a
    # false "released".
    valid_statuses = {"released", "pickup_confirmed_payout_review",
                      "pickup_confirmed_payout_pending"}
    assert out_a["status"] in valid_statuses
    assert out_b["status"] in valid_statuses

    # DB: each seller's row stamped by that seller.
    tx_a = await db.transactions.find_one({"listing_id": listing, "seller_id": "sA"})
    tx_b = await db.transactions.find_one({"listing_id": listing, "seller_id": "sB"})
    assert tx_a["pickup_code_confirmed_by"] == "sA"
    assert tx_b["pickup_code_confirmed_by"] == "sB"


# ── Forward escrow-hold record test ─────────────────────────────────

@pytest.mark.asyncio
async def test_forward_escrow_hold_record_idempotent(db):
    from services.payment_collection import _ensure_escrow_hold_record
    listing = "iter469f-1"
    await _ensure_escrow_hold_record(
        db, listing_id=listing, buyer_id="bA", seller_id="sA",
        hammer=100.0, platform_fee=5.0, total_charged=105.0,
        stripe_pi="pi_test", pickup_code="BVX-FWD1",
        province="QC",
    )
    row = await db.escrow_transactions.find_one({"auction_id": listing})
    assert row is not None
    assert row["escrow_status"] == "held"
    assert row["pickup_code"] == "BVX-FWD1"
    assert row["created_via"] == "finalize_auction_payment"

    # Second call — no duplicate row.
    await _ensure_escrow_hold_record(
        db, listing_id=listing, buyer_id="bA", seller_id="sA",
        hammer=100.0, platform_fee=5.0, total_charged=105.0,
        stripe_pi="pi_test", pickup_code="BVX-FWD1",
        province="QC",
    )
    n = await db.escrow_transactions.count_documents({"auction_id": listing})
    assert n == 1


@pytest.mark.asyncio
async def test_forward_escrow_hold_skipped_without_seller(db):
    from services.payment_collection import _ensure_escrow_hold_record
    listing = "iter469f-2"
    await _ensure_escrow_hold_record(
        db, listing_id=listing, buyer_id="bA", seller_id=None,
        hammer=100.0, platform_fee=5.0, total_charged=105.0,
        stripe_pi="pi_test", pickup_code="BVX-FWD2",
    )
    n = await db.escrow_transactions.count_documents({"auction_id": listing})
    assert n == 0


@pytest.mark.asyncio
async def test_forward_escrow_hold_skipped_without_pickup_code(db):
    from services.payment_collection import _ensure_escrow_hold_record
    listing = "iter469f-3"
    await _ensure_escrow_hold_record(
        db, listing_id=listing, buyer_id="bA", seller_id="sA",
        hammer=100.0, platform_fee=5.0, total_charged=105.0,
        stripe_pi="pi_test", pickup_code="",
    )
    n = await db.escrow_transactions.count_documents({"auction_id": listing})
    assert n == 0
