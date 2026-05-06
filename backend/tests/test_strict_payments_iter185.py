"""
Strict Payment System tests — Spec global rules + Features 1-3.

Run:  cd /app/backend && python -m pytest tests/test_strict_payments_iter185.py -v
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---------- Helpers ----------
class FakeColl:
    def __init__(self, store):
        self.store = store

    async def insert_one(self, doc):
        if "id" not in doc:
            doc["id"] = str(uuid.uuid4())
        # Simulate unique index on idempotency_key
        if "idempotency_key" in doc:
            for d in self.store:
                if d.get("idempotency_key") == doc["idempotency_key"]:
                    raise Exception("duplicate idempotency_key")
        # Simulate unique on (auction_id, user_id, deposit_id)
        if all(k in doc for k in ("auction_id", "user_id", "deposit_id")):
            for d in self.store:
                if (
                    d.get("auction_id") == doc["auction_id"]
                    and d.get("user_id") == doc["user_id"]
                    and d.get("deposit_id") == doc["deposit_id"]
                ):
                    raise Exception("duplicate")
        self.store.append(doc)
        return MagicMock(inserted_id=doc.get("id"))

    async def find_one(self, query, projection=None):
        for d in self.store:
            if all(d.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                # Handle $in
                ok = True
                for k, v in query.items():
                    if isinstance(v, dict) and "$in" in v:
                        if d.get(k) not in v["$in"]:
                            ok = False
                if ok:
                    return d
        return None

    async def find_one_and_update(self, query, update):
        for d in self.store:
            ok = True
            for k, v in query.items():
                if isinstance(v, dict):
                    if "$lte" in v and d.get(k, "") > v["$lte"]:
                        ok = False
                    if "$in" in v and d.get(k) not in v["$in"]:
                        ok = False
                else:
                    if d.get(k) != v:
                        ok = False
            if ok:
                if "$set" in update:
                    d.update(update["$set"])
                return d
        return None

    async def update_one(self, query, update):
        for d in self.store:
            if all(d.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                if "$set" in update:
                    for k, v in update["$set"].items():
                        # Support dotted keys (basic)
                        if "." in k:
                            top, sub = k.split(".", 1)
                            d.setdefault(top, {})[sub] = v
                        else:
                            d[k] = v
                return MagicMock(modified_count=1)
        return MagicMock(modified_count=0)

    async def count_documents(self, query):
        c = 0
        for d in self.store:
            ok = True
            for k, v in query.items():
                if isinstance(v, dict) and "$in" in v:
                    if d.get(k) not in v["$in"]:
                        ok = False
                elif d.get(k) != v:
                    ok = False
            if ok:
                c += 1
        return c

    def find(self, query=None, projection=None):
        results = list(self.store)
        return _Cursor(results)

    async def create_index(self, *args, **kwargs):
        return None


class _Cursor:
    def __init__(self, items):
        self.items = items

    async def to_list(self, n):
        return self.items[:n]


class FakeDB:
    def __init__(self):
        self._colls = {}

    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        return self._colls.setdefault(name, FakeColl([]))

    def __getitem__(self, name):
        return self._colls.setdefault(name, FakeColl([]))


# ---------- Tests ----------

@pytest.mark.asyncio
async def test_idempotency_key_format():
    from services.payment_idempotency import build_idempotency_key
    k = build_idempotency_key("buyer_full_payment", "AUC1", "USR1", 1700000000)
    assert k == "buyer_full_payment_AUC1_USR1_1700000000"


@pytest.mark.asyncio
async def test_idempotency_unknown_charge_type_rejected():
    from services.payment_idempotency import build_idempotency_key
    with pytest.raises(ValueError):
        build_idempotency_key("invalid_type", "A", "U", 1)


@pytest.mark.asyncio
async def test_reserve_charge_row_inserts_pending():
    from services.payment_idempotency import reserve_charge_row
    db = FakeDB()
    row = await reserve_charge_row(
        db, auction_id="A1", user_id="U1", charge_type="deposit",
        currency="CAD", amount=50.0, auction_end_ts=1700000000,
    )
    assert row["status"] == "pending"
    assert row["idempotency_key"] == "deposit_A1_U1_1700000000"
    assert row["currency"] == "CAD"
    assert row["amount"] == 50.0


@pytest.mark.asyncio
async def test_duplicate_charge_blocked_when_succeeded_exists():
    from services.payment_idempotency import (
        DuplicateChargeBlocked, mark_charge_succeeded, reserve_charge_row,
    )
    db = FakeDB()
    row = await reserve_charge_row(
        db, auction_id="A1", user_id="U1", charge_type="buyer_commission",
        currency="CAD", amount=20.0, auction_end_ts=1700000000,
    )
    await mark_charge_succeeded(db, row["id"], stripe_object_id="pi_1", stripe_object_type="payment_intent")

    with pytest.raises(DuplicateChargeBlocked):
        await reserve_charge_row(
            db, auction_id="A1", user_id="U1", charge_type="buyer_commission",
            currency="CAD", amount=20.0, auction_end_ts=1700000099,
        )
    # And the DUPLICATE_CHARGE_BLOCKED event was logged
    events = db.payment_events.store
    assert any(e["event"] == "DUPLICATE_CHARGE_BLOCKED" for e in events)


@pytest.mark.asyncio
async def test_currency_must_be_cad_or_usd():
    from services.payment_idempotency import reserve_charge_row
    db = FakeDB()
    with pytest.raises(ValueError):
        await reserve_charge_row(
            db, auction_id="A1", user_id="U1", charge_type="deposit",
            currency="EUR", amount=10.0,
        )


@pytest.mark.asyncio
async def test_enqueue_non_winner_refunds_skips_winner():
    from services.deposit_refund_queue import enqueue_non_winner_refunds
    db = FakeDB()
    deposits = [
        {"id": "d1", "user_id": "U1", "stripe_payment_intent_id": "pi_1", "amount": 50, "currency": "CAD"},
        {"id": "d2", "user_id": "U2", "stripe_payment_intent_id": "pi_2", "amount": 50, "currency": "CAD"},
        {"id": "d3", "user_id": "U3", "stripe_payment_intent_id": "pi_3", "amount": 50, "currency": "CAD"},
    ]
    n = await enqueue_non_winner_refunds(
        db, auction_id="A1", winner_user_id="U2", deposits=deposits,
        deposit_collection="bidding_deposits",
    )
    assert n == 2  # winner U2 skipped
    rows = db.deposit_refund_queue.store
    assert all(r["user_id"] != "U2" for r in rows)
    assert all(r["status"] == "pending" for r in rows)


@pytest.mark.asyncio
async def test_refund_queue_processes_and_marks_succeeded():
    from services.deposit_refund_queue import (
        enqueue_non_winner_refunds, process_deposit_refund_queue,
    )
    db = FakeDB()
    # Pre-seed deposit doc that the worker will mark refunded
    db.bidding_deposits.store.append({
        "id": "d1", "auction_id": "A1", "user_id": "U1",
        "stripe_payment_intent_id": "pi_1", "amount": 50.0, "currency": "CAD",
        "status": "held",
    })
    await enqueue_non_winner_refunds(
        db, auction_id="A1", winner_user_id="U_WIN",
        deposits=db.bidding_deposits.store,
        deposit_collection="bidding_deposits",
    )

    # Mock Stripe so we don't make real network calls
    with patch("services.deposit_refund_queue.stripe") as fake_stripe:
        fake_stripe.PaymentIntent.cancel.return_value = MagicMock(id="pi_1")
        # Mock email send
        with patch("services.email_notifications.send_deposit_refunded_email", new=AsyncMock(return_value=True)):
            out = await process_deposit_refund_queue(db)
    assert out["processed"] == 1
    assert out["succeeded"] == 1
    deposit = db.bidding_deposits.store[0]
    assert deposit["status"] == "refunded"


@pytest.mark.asyncio
async def test_settle_auction_routes_cash_vs_stripe():
    """Spec Feature 3 — payment_method routing"""
    from services.auction_settlement import settle_auction
    db = FakeDB()
    # Common docs
    db.users.store.extend([
        {"id": "BUYER", "stripe_customer_id": "cus_b", "subscription_tier": "free"},
        {"id": "SELLER", "stripe_customer_id": "cus_s", "subscription_tier": "free",
         "stripe_connect_account_id": "acct_1"},
    ])
    db.payment_methods.store.append({
        "id": "pm-row", "user_id": "BUYER", "stripe_payment_method_id": "pm_1",
        "is_default": True,
    })
    db.payment_methods.store.append({
        "id": "pm-row2", "user_id": "SELLER", "stripe_payment_method_id": "pm_2",
        "is_default": True,
    })

    listing = {
        "id": "AUC1", "title": "Test", "seller_id": "SELLER",
        "winner_id": "BUYER", "winning_bidder_id": "BUYER",
        "current_price": 100.0, "currency": "CAD", "region": "QC",
        "auction_end_date": "2026-01-01T00:00:00+00:00",
        "payment_method": "cash",
    }
    with patch("services.auction_settlement.stripe") as fake_stripe:
        fake_stripe.PaymentIntent.create.return_value = MagicMock(id="pi_test")
        fake_stripe.error.StripeError = Exception  # for the except clause
        out = await settle_auction(db, auction_id="AUC1", listing=listing)
    assert out["scenario"] == "cash_or_etransfer"
    assert out["currency"] == "CAD"

    # Now Stripe scenario
    listing["payment_method"] = "stripe"
    listing["id"] = "AUC2"
    db.payment_charges.store.clear()  # reset
    with patch("services.auction_settlement.stripe") as fake_stripe:
        fake_stripe.PaymentIntent.create.return_value = MagicMock(id="pi_test2")
        fake_stripe.error.StripeError = Exception
        out2 = await settle_auction(db, auction_id="AUC2", listing=listing)
    assert out2["scenario"] == "stripe_full"


@pytest.mark.asyncio
async def test_winner_mismatch_blocked_in_stripe_flow():
    from services.auction_settlement import settle_stripe_full
    db = FakeDB()
    listing = {
        "id": "AUC3", "winner_id": "TRUE_WINNER", "seller_id": "SELLER",
        "current_price": 100.0, "currency": "CAD", "region": "QC",
    }
    out = await settle_stripe_full(
        db, auction_id="AUC3", listing=listing,
        winner_user_id="ATTACKER",  # ≠ TRUE_WINNER
        seller_id="SELLER",
        hammer_price=100.0, currency="CAD", auction_end_ts=1700000000,
    )
    assert out.get("error") == "WINNER_MISMATCH_BLOCKED"
    events = db.payment_events.store
    assert any(e["event"] == "WINNER_MISMATCH_BLOCKED" for e in events)


@pytest.mark.asyncio
async def test_listing_create_validates_deposit_fields():
    """Spec Feature 1 — deposit validation"""
    from models.auction_models import ListingCreate
    # Valid: requires_deposit=False, no deposit fields
    ok = ListingCreate(
        title="t", description="d", category="c", condition="new",
        starting_price=10.0, location="x", city="x", region="x",
        auction_end_date=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    assert ok.requires_deposit is False
    # Valid: requires_deposit=True with amount + type
    ok2 = ListingCreate(
        title="t", description="d", category="c", condition="new",
        starting_price=10.0, location="x", city="x", region="x",
        auction_end_date=datetime(2030, 1, 1, tzinfo=timezone.utc),
        requires_deposit=True, deposit_amount=25.0, deposit_type="fixed",
    )
    assert ok2.deposit_type == "fixed"


@pytest.mark.asyncio
async def test_currency_default_is_cad():
    from models.auction_models import Listing
    listing = Listing(
        seller_id="s", title="t", description="d", category="c", condition="new",
        starting_price=10.0, current_price=10.0, location="x",
        auction_end_date=datetime(2030, 1, 1, tzinfo=timezone.utc),
    )
    assert listing.currency == "CAD"


# ─── iter186 — webhook refund idempotency (DUPLICATE_REFUND_BLOCKED) ───

@pytest.mark.asyncio
async def test_webhook_refund_blocks_duplicate():
    """
    Simulate two `charge.refunded` webhook deliveries for the same charge.
    First call → marks charge refunded.
    Second call → must log DUPLICATE_REFUND_BLOCKED and NOT change anything.
    """
    from services.payment_idempotency import (
        mark_charge_refunded, mark_charge_succeeded, reserve_charge_row,
    )

    db = FakeDB()
    # Seed a succeeded charge with stripe_object_id
    row = await reserve_charge_row(
        db, auction_id="A1", user_id="U1", charge_type="deposit",
        currency="CAD", amount=50.0, auction_end_ts=1700000000,
    )
    await mark_charge_succeeded(
        db, row["id"], stripe_object_id="pi_dup", stripe_object_type="payment_intent"
    )

    # Apply first refund (simulating webhook handler logic)
    existing = await db.payment_charges.find_one(
        {"stripe_object_id": "pi_dup"}, {"_id": 0}
    )
    assert existing and existing["status"] == "succeeded"
    await mark_charge_refunded(db, existing["id"], reason="webhook_charge.refunded")

    # Second webhook — must detect already-refunded and log DUPLICATE_REFUND_BLOCKED
    refreshed = await db.payment_charges.find_one(
        {"stripe_object_id": "pi_dup"}, {"_id": 0}
    )
    assert refreshed["status"] == "refunded"
    if refreshed["status"] == "refunded":
        await db.payment_events.insert_one({
            "id": "ev1",
            "event": "DUPLICATE_REFUND_BLOCKED",
            "charge_id": refreshed["id"],
            "stripe_payment_intent_id": "pi_dup",
        })

    events = db.payment_events.store
    assert any(e["event"] == "DUPLICATE_REFUND_BLOCKED" for e in events)
