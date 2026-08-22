"""iter500 — Accept Below Reserve endpoint tests

Covers:
  * Happy path (seller): eligibility=True → POST re-uses the existing
    bypass_reserve settlement path (settle_stripe_full mocked) and
    the request row flips to ``approved``.
  * Missing saved payment method → 400 NO_SAVED_PAYMENT_METHOD, no
    settlement, no side effects.
  * Wrong status (not reserve_not_met) → 409 STATUS_NOT_RESERVE_NOT_MET.
  * Non-owner non-admin → 403.
  * Lot-scoped happy path (multi-item).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException

from routes import accept_below_reserve as abr
from services import auction_requests_service as ars

from tests.test_iter483_live_edit import FakeDb, SELLER, OTHER, ADMIN
from tests.test_iter483_3_lot_and_requests import (  # noqa: F401  — install positional-op patch
    _patched_update_one,
)

# A stand-in for FastAPI's HTTPAuthorizationCredentials — anything
# non-None is fine because our test auth callback ignores the value
# and returns the user directly.
_FAKE_CREDS = type("_Creds", (), {"scheme": "Bearer", "credentials": "x"})()


def _ret(user):
    """Wrap a user dict into an async callable that ignores its arg."""
    async def _cb(_c):
        return user
    return _cb


# ─────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────

def _seed_listing(db, coll="listings", **kw):
    doc = {
        "id":         kw.get("id", "rnm-1"),
        "seller_id":  kw.get("seller_id", SELLER["id"]),
        "title":      kw.get("title", "Reserve Not Met Item"),
        "status":     kw.get("status", "reserve_not_met"),
        "reserve_price":     kw.get("reserve_price", 100.0),
        "current_price":     kw.get("current_price", 55.0),
        "final_price":       kw.get("final_price", 55.0),
        "winner_user_id":    kw.get("winner_user_id", "buyer-1"),
        "sold_quantity":     kw.get("sold_quantity", 0),
        "currency":          "CAD",
        "payment_method":    "stripe",
        "auction_end_date": (
            datetime.now(timezone.utc) - timedelta(hours=1)
        ).isoformat(),
    }
    if "lots" in kw:
        doc["lots"] = kw["lots"]
    db[coll]._docs.append(doc)
    return doc


def _seed_buyer_with_pm(db, buyer_id="buyer-1", pm_id="pm_test_123"):
    db.users._docs.append({
        "id": buyer_id,
        "email": f"{buyer_id}@x.com",
        "name": "Buyer One",
    })
    db.payment_methods._docs.append({
        "user_id": buyer_id,
        "stripe_payment_method_id": pm_id,
        "is_default": True,
    })


def _seed_buyer_no_pm(db, buyer_id="buyer-1"):
    db.users._docs.append({
        "id": buyer_id,
        "email": f"{buyer_id}@x.com",
        "name": "Buyer One",
    })


# ─────────────────────────────────────────────────────────────────────
# _extract_context
# ─────────────────────────────────────────────────────────────────────

def test_extract_context_top_level():
    doc = {
        "status": "reserve_not_met",
        "sold_quantity": 0,
        "winner_user_id": "buyer-1",
        "final_price": 55.0,
        "reserve_price": 100.0,
        "title": "Widget",
        "currency": "CAD",
    }
    ctx = abr._extract_context(doc, None)
    assert ctx["status"] == "reserve_not_met"
    assert ctx["winner_user_id"] == "buyer-1"
    assert ctx["hammer_price"] == 55.0
    assert ctx["target"] == "auction"


def test_extract_context_lot_wins():
    doc = {"title": "Parent", "lots": [
        {"lot_number": 3, "status": "reserve_not_met",
         "current_price": 44.0, "winner_user_id": "buyer-2",
         "sold_quantity": 0, "title": "Lot 3"},
    ], "currency": "CAD"}
    ctx = abr._extract_context(doc, 3)
    assert ctx["target"] == "3"
    assert ctx["lot_number"] == 3
    assert ctx["hammer_price"] == 44.0
    assert ctx["winner_user_id"] == "buyer-2"


# ─────────────────────────────────────────────────────────────────────
# GET eligibility
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_eligibility_true_when_all_conditions_met():
    db = FakeDb()
    _seed_listing(db, id="rnm-1")
    _seed_buyer_with_pm(db)
    ctx = abr._extract_context(
        await db["listings"].find_one({"id": "rnm-1"}), None
    )
    has_pm = await abr._has_saved_payment_method(db, ctx["winner_user_id"])
    assert has_pm is True
    assert ctx["status"] == "reserve_not_met"
    assert ctx["sold_quantity"] == 0


@pytest.mark.asyncio
async def test_eligibility_false_when_no_saved_payment_method():
    db = FakeDb()
    _seed_listing(db, id="rnm-1")
    _seed_buyer_no_pm(db)
    has_pm = await abr._has_saved_payment_method(db, "buyer-1")
    assert has_pm is False


# ─────────────────────────────────────────────────────────────────────
# POST /accept-below-reserve
# ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_accept_below_reserve_happy_path_seller():
    """Seller triggers → bypass_reserve settlement runs, row approved."""
    db = FakeDb()
    _seed_listing(db, id="rnm-1")
    _seed_buyer_with_pm(db)

    abr.set_db(db)
    abr.set_auth(_ret(SELLER))

    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock(return_value={"buyer_charge": {"amount": 55}})) as mock_stripe, \
         patch("services.payment_collection.finalize_auction_payment",
               new=AsyncMock(return_value={"payment_status": "payment_collected"})) as mock_final:
        result = await abr.accept_below_reserve(
            auction_id="rnm-1",
            body=abr.AcceptBody(lot_number=None),
            credentials=_FAKE_CREDS,
        )

    assert result["success"] is True
    assert result["auction_id"] == "rnm-1"
    assert result["hammer_price"] == 55.0
    # Underlying pipeline invoked exactly once (bypass path)
    assert mock_stripe.await_count == 1
    assert mock_final.await_count == 1

    # Approval flipped the reserve_not_met request row to 'approved'
    row = await db[ars.COLLECTION].find_one(
        {"auction_id": "rnm-1", "request_type": "reserve_not_met"},
    )
    assert row is not None
    assert row["status"] == "approved"
    assert row["reviewed_by"] == SELLER["id"]

    # Auction status was flipped to 'ended' by the shared side-effect
    doc = await db["listings"].find_one({"id": "rnm-1"})
    assert doc["status"] == "ended"


@pytest.mark.asyncio
async def test_accept_below_reserve_missing_saved_payment_method():
    """400 error when buyer has no saved PM; NO settlement fires."""
    db = FakeDb()
    _seed_listing(db, id="rnm-2")
    _seed_buyer_no_pm(db)

    abr.set_db(db)
    abr.set_auth(_ret(SELLER))

    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock()) as mock_stripe, \
         patch("services.payment_collection.finalize_auction_payment",
               new=AsyncMock()) as mock_final:
        with pytest.raises(HTTPException) as exc:
            await abr.accept_below_reserve(
                auction_id="rnm-2",
                body=abr.AcceptBody(lot_number=None),
                credentials=_FAKE_CREDS,
            )

    assert exc.value.status_code == 400
    assert exc.value.detail["error"] == "NO_SAVED_PAYMENT_METHOD"
    # NO side effects
    mock_stripe.assert_not_called()
    mock_final.assert_not_called()


@pytest.mark.asyncio
async def test_accept_below_reserve_wrong_status_409():
    db = FakeDb()
    _seed_listing(db, id="rnm-3", status="active")
    _seed_buyer_with_pm(db)

    abr.set_db(db)
    abr.set_auth(_ret(SELLER))

    with pytest.raises(HTTPException) as exc:
        await abr.accept_below_reserve(
            auction_id="rnm-3",
            body=abr.AcceptBody(lot_number=None),
            credentials=_FAKE_CREDS,
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["error"] == "STATUS_NOT_RESERVE_NOT_MET"


@pytest.mark.asyncio
async def test_accept_below_reserve_non_owner_403():
    db = FakeDb()
    _seed_listing(db, id="rnm-4")
    _seed_buyer_with_pm(db)

    abr.set_db(db)
    abr.set_auth(_ret(OTHER))  # not seller, not admin

    with pytest.raises(HTTPException) as exc:
        await abr.accept_below_reserve(
            auction_id="rnm-4",
            body=abr.AcceptBody(lot_number=None),
            credentials=_FAKE_CREDS,
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_accept_below_reserve_admin_bypasses_ownership():
    """Admin (non-seller) is permitted to accept the sale."""
    db = FakeDb()
    _seed_listing(db, id="rnm-5")
    _seed_buyer_with_pm(db)

    abr.set_db(db)
    abr.set_auth(_ret(ADMIN))

    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock(return_value={"buyer_charge": {"amount": 55}})), \
         patch("services.payment_collection.finalize_auction_payment",
               new=AsyncMock(return_value={"payment_status": "payment_collected"})):
        result = await abr.accept_below_reserve(
            auction_id="rnm-5",
            body=abr.AcceptBody(lot_number=None),
            credentials=_FAKE_CREDS,
        )
    assert result["success"] is True
    row = await db[ars.COLLECTION].find_one(
        {"auction_id": "rnm-5", "request_type": "reserve_not_met"},
    )
    assert row["status"] == "approved"
    assert row["reviewed_by"] == ADMIN["id"]


@pytest.mark.asyncio
async def test_accept_below_reserve_lot_scoped_happy_path():
    """Lot-scoped path settles the specific lot, flips lot status to sold."""
    db = FakeDb()
    _seed_listing(
        db,
        coll="multi_item_listings",
        id="mi-1",
        status="active",  # parent stays 'active' while other lots run
        lots=[
            {"lot_number": 1, "status": "reserve_not_met",
             "reserve_price": 100.0, "current_price": 60.0,
             "winner_user_id": "buyer-1", "sold_quantity": 0,
             "title": "Lot 1"},
        ],
    )
    _seed_buyer_with_pm(db)

    abr.set_db(db)
    abr.set_auth(_ret(SELLER))

    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock(return_value={"buyer_charge": {"amount": 60}})), \
         patch("services.payment_collection.finalize_auction_payment",
               new=AsyncMock(return_value={"payment_status": "payment_collected"})):
        result = await abr.accept_below_reserve(
            auction_id="mi-1",
            body=abr.AcceptBody(lot_number=1),
            credentials=_FAKE_CREDS,
        )
    assert result["success"] is True
    assert result["lot_number"] == 1
    assert result["hammer_price"] == 60.0

    doc = await db["multi_item_listings"].find_one({"id": "mi-1"})
    lot = next(l for l in doc["lots"] if l["lot_number"] == 1)
    assert lot["status"] == "sold"
    assert lot["winner_user_id"] == "buyer-1"


@pytest.mark.asyncio
async def test_accept_below_reserve_already_sold_409():
    db = FakeDb()
    _seed_listing(db, id="rnm-6", sold_quantity=1)
    _seed_buyer_with_pm(db)

    abr.set_db(db)
    abr.set_auth(_ret(SELLER))

    with pytest.raises(HTTPException) as exc:
        await abr.accept_below_reserve(
            auction_id="rnm-6",
            body=abr.AcceptBody(lot_number=None),
            credentials=_FAKE_CREDS,
        )
    assert exc.value.status_code == 409
    assert exc.value.detail["error"] == "ALREADY_SOLD"


@pytest.mark.asyncio
async def test_accept_below_reserve_unauthenticated_401():
    db = FakeDb()
    _seed_listing(db, id="rnm-7")
    _seed_buyer_with_pm(db)

    abr.set_db(db)
    abr.set_auth(None)

    with pytest.raises(HTTPException) as exc:
        await abr.accept_below_reserve(
            auction_id="rnm-7",
            body=abr.AcceptBody(lot_number=None),
            credentials=None,
        )
    assert exc.value.status_code == 401
