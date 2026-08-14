"""iter484 — Reserve Price at Auction Close settlement tests.

Covers:
  * reserve_price_gate helper (pure function correctness)
  * settle_auction returns ``reason="reserve_not_met"`` when hammer <
    reserve and DOES NOT create any Stripe charge
  * settle_auction proceeds when hammer >= reserve
  * settle_auction proceeds when no reserve set (None / 0)
  * ``bypass_reserve=True`` skips the gate
  * create_system_reserve_not_met_request is idempotent
  * approving a ``reserve_not_met`` request re-runs settlement with
    ``bypass_reserve=True`` and flips lot / listing status to reflect
    the accepted sale
  * denying a ``reserve_not_met`` request flips listing/lot status to
    ``ended_reserve_not_met`` with no financial actions
  * payment_collection.finalize_auction_payment short-circuits when
    settlement carries ``reason="reserve_not_met"``
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest

from services import auction_requests_service as ars
from services.reserve_price_gate import (
    is_reserve_met, resolve_reserve_price,
)
from services.auction_settlement import settle_auction

from tests.test_iter483_live_edit import (
    FakeDb, FakeCollection, SELLER, ADMIN,
)

# Bring in the positional-op patch that iter483.3 tests install so
# ``lots.$.<field>`` updates behave sensibly on the FakeDb.
from tests.test_iter483_3_lot_and_requests import (  # noqa: F401
    _patched_update_one,
)


# ═════════════════════════════════════════════════════════════════════
# reserve_price_gate — pure helpers
# ═════════════════════════════════════════════════════════════════════

def test_resolve_reserve_none_when_missing():
    assert resolve_reserve_price({}, lot=None) is None
    assert resolve_reserve_price({"reserve_price": None}) is None
    assert resolve_reserve_price({"reserve_price": 0}) is None
    assert resolve_reserve_price({"reserve_price": -5}) is None
    assert resolve_reserve_price({"reserve_price": "bad"}) is None


def test_resolve_reserve_lot_wins_over_auction():
    listing = {"reserve_price": 100}
    lot = {"reserve_price": 250}
    assert resolve_reserve_price(listing, lot=lot) == 250.0


def test_resolve_reserve_falls_back_to_auction_when_lot_missing():
    listing = {"reserve_price": 100}
    lot = {"reserve_price": None}
    assert resolve_reserve_price(listing, lot=lot) == 100.0


def test_is_reserve_met_no_reserve_returns_true():
    assert is_reserve_met(50, None) is True
    assert is_reserve_met(0, None) is True


def test_is_reserve_met_equal_or_above_returns_true():
    assert is_reserve_met(100, 100) is True
    assert is_reserve_met(101, 100) is True


def test_is_reserve_met_below_returns_false():
    assert is_reserve_met(99, 100) is False
    assert is_reserve_met(0, 1) is False


# ═════════════════════════════════════════════════════════════════════
# settle_auction — reserve gate integration
# ═════════════════════════════════════════════════════════════════════

def _base_listing(**overrides):
    doc = {
        "id":              "rn-1",
        "title":           "Reserve Test",
        "seller_id":       "seller-1",
        "winner_id":       "buyer-1",
        "current_price":   50.0,
        "final_price":     50.0,
        "reserve_price":   100.0,
        "payment_method":  "stripe",
        "currency":        "CAD",
        "auction_end_date": (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(),
        "listing_type":    "lots",
    }
    doc.update(overrides)
    return doc


@pytest.mark.asyncio
async def test_settle_auction_halts_when_reserve_not_met():
    """Below-reserve hammer must NEVER reach the Stripe settle helpers."""
    db = FakeDb()
    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock(return_value={})) as _mock_stripe, \
         patch("services.auction_settlement.settle_cash_or_etransfer",
               new=AsyncMock(return_value={})) as _mock_offline:
        out = await settle_auction(
            db, auction_id="rn-1", listing=_base_listing(),
        )
    assert out["settled"] is False
    assert out["reason"] == "reserve_not_met"
    assert out["reserve_price"] == 100.0
    assert out["hammer_price"] == 50.0
    _mock_stripe.assert_not_called()
    _mock_offline.assert_not_called()


@pytest.mark.asyncio
async def test_settle_auction_proceeds_when_hammer_equals_reserve():
    db = FakeDb()
    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock(return_value={"buyer_charge": {"amount": 100}})) as _mock:
        out = await settle_auction(
            db, auction_id="rn-1",
            listing=_base_listing(current_price=100.0, final_price=100.0),
        )
    assert out.get("settled") is True
    _mock.assert_called_once()


@pytest.mark.asyncio
async def test_settle_auction_proceeds_when_no_reserve_set():
    db = FakeDb()
    listing = _base_listing()
    listing.pop("reserve_price", None)
    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock(return_value={"buyer_charge": {"amount": 50}})) as _mock:
        out = await settle_auction(db, auction_id="rn-1", listing=listing)
    assert out.get("settled") is True
    _mock.assert_called_once()


@pytest.mark.asyncio
async def test_settle_auction_proceeds_when_reserve_is_zero():
    db = FakeDb()
    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock(return_value={"buyer_charge": {"amount": 50}})) as _mock:
        out = await settle_auction(
            db, auction_id="rn-1",
            listing=_base_listing(reserve_price=0),
        )
    assert out.get("settled") is True
    _mock.assert_called_once()


@pytest.mark.asyncio
async def test_settle_auction_bypass_reserve_skips_gate():
    """Admin re-run must charge even when hammer < reserve."""
    db = FakeDb()
    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock(return_value={"buyer_charge": {"amount": 50}})) as _mock:
        out = await settle_auction(
            db, auction_id="rn-1",
            listing=_base_listing(),
            bypass_reserve=True,
        )
    assert out.get("settled") is True
    _mock.assert_called_once()


@pytest.mark.asyncio
async def test_settle_auction_lot_reserve_overrides_auction_reserve():
    db = FakeDb()
    listing = _base_listing(reserve_price=10.0)
    lot = {"reserve_price": 500.0, "lot_number": 1}
    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock(return_value={"buyer_charge": {}})) as _mock:
        out = await settle_auction(
            db, auction_id="rn-1", listing=listing, lot=lot,
        )
    # Hammer $50 vs lot-level reserve $500 → not met, even though
    # auction-level ($10) would have passed.
    assert out["settled"] is False
    assert out["reason"] == "reserve_not_met"
    assert out["reserve_price"] == 500.0
    _mock.assert_not_called()


@pytest.mark.asyncio
async def test_settle_auction_reserve_price_override_wins():
    db = FakeDb()
    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock(return_value={"buyer_charge": {}})) as _mock:
        # Listing has reserve $10 (would pass), but caller says $999.
        out = await settle_auction(
            db, auction_id="rn-1",
            listing=_base_listing(reserve_price=10.0),
            reserve_price_override=999.0,
        )
    assert out["settled"] is False
    assert out["reserve_price"] == 999.0
    _mock.assert_not_called()


# ═════════════════════════════════════════════════════════════════════
# create_system_reserve_not_met_request — idempotency + shape
# ═════════════════════════════════════════════════════════════════════

def _seed_listing(db, coll="listings", **kw):
    """Insert an ``active`` listing so resolve_auction succeeds."""
    doc = {
        "id":         kw.get("id", "rn-1"),
        "seller_id":  kw.get("seller_id", "seller-1"),
        "title":      kw.get("title", "Reserve Test"),
        "status":     kw.get("status", "active"),
        "reserve_price": kw.get("reserve_price"),
        "auction_end_date": (
            datetime.now(timezone.utc) + timedelta(days=1)
        ).isoformat(),
    }
    if "lots" in kw:
        doc["lots"] = kw["lots"]
    db[coll]._docs.append(doc)
    return doc


@pytest.mark.asyncio
async def test_create_reserve_not_met_row_persists_shape():
    db = FakeDb()
    _seed_listing(db, id="rn-1", reserve_price=100.0)
    row = await ars.create_system_reserve_not_met_request(
        db,
        auction_id="rn-1",
        target="auction",
        hammer_price=50.0,
        reserve_price=100.0,
        winner_user_id="buyer-1",
    )
    assert row["request_type"] == "reserve_not_met"
    assert row["target"] == "auction"
    assert row["status"] == "pending"
    assert row["submitted_by"] == "system"
    assert row["payload"]["hammer_price"] == 50.0
    assert row["payload"]["reserve_price"] == 100.0
    assert row["payload"]["winner_user_id"] == "buyer-1"
    assert "hammer" in row["reason"].lower()


@pytest.mark.asyncio
async def test_create_reserve_not_met_row_is_idempotent():
    """Two calls for the same (auction, target) must reuse the row."""
    db = FakeDb()
    _seed_listing(db, id="rn-1", reserve_price=100.0)
    r1 = await ars.create_system_reserve_not_met_request(
        db, auction_id="rn-1", target="auction",
        hammer_price=50.0, reserve_price=100.0,
        winner_user_id="buyer-1",
    )
    r2 = await ars.create_system_reserve_not_met_request(
        db, auction_id="rn-1", target="auction",
        hammer_price=50.0, reserve_price=100.0,
        winner_user_id="buyer-1",
    )
    assert r1["id"] == r2["id"]
    rows = await db[ars.COLLECTION].find(
        {"auction_id": "rn-1", "request_type": "reserve_not_met"},
    ).to_list(10)
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_create_reserve_not_met_row_per_lot_is_scoped():
    """Different lot targets must produce distinct pending rows."""
    db = FakeDb()
    _seed_listing(
        db, coll="multi_item_listings", id="mi-1",
        lots=[{"lot_number": 1, "reserve_price": 100.0},
              {"lot_number": 2, "reserve_price": 200.0}],
    )
    r1 = await ars.create_system_reserve_not_met_request(
        db, auction_id="mi-1", target="1",
        hammer_price=50, reserve_price=100,
        winner_user_id="buyer-1", lot_number=1,
        collection="multi_item_listings",
    )
    r2 = await ars.create_system_reserve_not_met_request(
        db, auction_id="mi-1", target="2",
        hammer_price=150, reserve_price=200,
        winner_user_id="buyer-1", lot_number=2,
        collection="multi_item_listings",
    )
    assert r1["id"] != r2["id"]
    rows = await db[ars.COLLECTION].find(
        {"auction_id": "mi-1", "request_type": "reserve_not_met"},
    ).to_list(10)
    assert len(rows) == 2


@pytest.mark.asyncio
async def test_create_reserve_not_met_queues_admin_and_buyer_emails():
    db = FakeDb()
    _seed_listing(db, id="rn-1", reserve_price=100.0)
    await ars.create_system_reserve_not_met_request(
        db, auction_id="rn-1", target="auction",
        hammer_price=50.0, reserve_price=100.0,
        winner_user_id="buyer-1",
    )
    outbox = await db.email_outbox.find({}).to_list(10)
    kinds = {r["kind"] for r in outbox}
    assert "auction_request_submitted:reserve_not_met" in kinds
    assert "reserve_not_met_buyer_under_review" in kinds

    # Buyer email context must NOT include the reserve amount.
    buyer_row = next(
        r for r in outbox if r["kind"] == "reserve_not_met_buyer_under_review"
    )
    assert "reserve_price" not in buyer_row["context"]
    assert buyer_row["to_user_id"] == "buyer-1"


# ═════════════════════════════════════════════════════════════════════
# Approve / deny lifecycle
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_admin_approve_reserve_not_met_rerun_settlement_with_bypass():
    """Approve → settle_auction called with bypass_reserve=True."""
    db = FakeDb()
    _seed_listing(db, id="rn-1", reserve_price=100.0)
    row = await ars.create_system_reserve_not_met_request(
        db, auction_id="rn-1", target="auction",
        hammer_price=50.0, reserve_price=100.0,
        winner_user_id="buyer-1",
    )
    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock(return_value={"buyer_charge": {"amount": 50}})) as mock_stripe, \
         patch("services.payment_collection.finalize_auction_payment",
               new=AsyncMock(return_value={"payment_status": "payment_collected"})) as mock_final:
        await ars.approve_request(db, row["id"], ADMIN, admin_note="ok")

    assert mock_stripe.await_count == 1  # was allowed through (bypass)
    assert mock_final.await_count == 1

    # Listing status must reflect the accepted sale.
    doc = await db["listings"].find_one({"id": "rn-1"})
    assert doc["status"] == "ended"

    # Request row is now approved.
    resolved = await db[ars.COLLECTION].find_one({"id": row["id"]})
    assert resolved["status"] == "approved"


@pytest.mark.asyncio
async def test_admin_deny_reserve_not_met_marks_ended_and_no_charges():
    """Deny → status flips to ``ended_reserve_not_met``; no Stripe."""
    db = FakeDb()
    _seed_listing(db, id="rn-1", reserve_price=100.0)
    row = await ars.create_system_reserve_not_met_request(
        db, auction_id="rn-1", target="auction",
        hammer_price=50.0, reserve_price=100.0,
        winner_user_id="buyer-1",
    )
    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock(return_value={})) as mock_stripe, \
         patch("services.payment_collection.finalize_auction_payment",
               new=AsyncMock(return_value={})) as mock_final:
        await ars.deny_request(db, row["id"], ADMIN, admin_note="reject")

    mock_stripe.assert_not_called()
    mock_final.assert_not_called()
    doc = await db["listings"].find_one({"id": "rn-1"})
    assert doc["status"] == "ended_reserve_not_met"
    assert doc.get("end_reason") == "reserve_not_met"
    resolved = await db[ars.COLLECTION].find_one({"id": row["id"]})
    assert resolved["status"] == "denied"


@pytest.mark.asyncio
async def test_admin_approve_lot_scoped_reserve_not_met_flips_lot_status():
    db = FakeDb()
    _seed_listing(
        db, coll="multi_item_listings", id="mi-1",
        lots=[{"lot_number": 1, "reserve_price": 100.0, "status": "reserve_not_met"}],
    )
    row = await ars.create_system_reserve_not_met_request(
        db, auction_id="mi-1", target="1",
        hammer_price=50.0, reserve_price=100.0,
        winner_user_id="buyer-1", lot_number=1,
        collection="multi_item_listings",
    )
    with patch("services.auction_settlement.settle_stripe_full",
               new=AsyncMock(return_value={"buyer_charge": {"amount": 50}})), \
         patch("services.payment_collection.finalize_auction_payment",
               new=AsyncMock(return_value={})):
        await ars.approve_request(db, row["id"], ADMIN)

    doc = await db["multi_item_listings"].find_one({"id": "mi-1"})
    lot = next(l for l in doc["lots"] if l["lot_number"] == 1)
    assert lot["status"] == "sold"
    assert lot["winner_user_id"] == "buyer-1"


@pytest.mark.asyncio
async def test_admin_deny_lot_scoped_reserve_not_met_flips_lot_status():
    db = FakeDb()
    _seed_listing(
        db, coll="multi_item_listings", id="mi-2",
        lots=[{"lot_number": 2, "reserve_price": 200.0, "status": "reserve_not_met"}],
    )
    row = await ars.create_system_reserve_not_met_request(
        db, auction_id="mi-2", target="2",
        hammer_price=150.0, reserve_price=200.0,
        winner_user_id="buyer-1", lot_number=2,
        collection="multi_item_listings",
    )
    await ars.deny_request(db, row["id"], ADMIN)
    doc = await db["multi_item_listings"].find_one({"id": "mi-2"})
    lot = next(l for l in doc["lots"] if l["lot_number"] == 2)
    assert lot["status"] == "ended_reserve_not_met"


# ═════════════════════════════════════════════════════════════════════
# Registration checks
# ═════════════════════════════════════════════════════════════════════

def test_request_types_includes_reserve_not_met():
    assert "reserve_not_met" in ars.REQUEST_TYPES
    assert "reserve_not_met" in ars.SYSTEM_GENERATED_TYPES


# ═════════════════════════════════════════════════════════════════════
# payment_collection short-circuit
# ═════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_finalize_auction_payment_short_circuits_on_reserve_not_met():
    """finalize must not create any stamps / receipts / payouts when
    the settlement result carries reason=reserve_not_met."""
    from services.payment_collection import finalize_auction_payment

    db = FakeDb()
    listing = {
        "id": "rn-1",
        "title": "T",
        "seller_id": "seller-1",
        "winner_user_id": "buyer-1",
        "current_price": 50.0,
    }
    settlement = {
        "settled": False,
        "reason": "reserve_not_met",
        "reserve_price": 100.0,
        "hammer_price": 50.0,
    }
    out = await finalize_auction_payment(
        db, listing=listing, collection="listings",
        settlement=settlement, section="marketplace",
        hammer_override=50.0, winner_override="buyer-1",
    )
    assert out.get("payment_status") == "reserve_not_met"
    # No receipts, no transactions, no payouts should have been touched.
    assert (await db.transactions.find({}).to_list(10)) == []
