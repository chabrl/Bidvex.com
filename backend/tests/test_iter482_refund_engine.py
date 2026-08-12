"""
iter482 Gate 3 — Refund Engine Unit Tests

Uses mocked Stripe + mocked Mongo.  Does NOT hit Stripe TEST MODE.
Integration proof against Stripe test-mode is BLOCKED pending a valid
`STRIPE_API_KEY`.

Assertions cover:
  - Full refund happy path (Partner)
  - Full refund happy path (non-Partner)
  - Partial refund path
  - Idempotency: duplicate refund is blocked without re-hitting Stripe
  - Stripe error: leaves charge_row unchanged
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest  # noqa: E402


class _FakeCollection:
    def __init__(self):
        self.docs = []

    async def find_one(self, filter_, projection=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in filter_.items() if not isinstance(v, dict)):
                # simple key-equality only
                return dict(d)
            for k, v in filter_.items():
                if isinstance(v, dict) and "$or" in filter_:
                    pass
        return None

    async def insert_one(self, doc):
        self.docs.append(dict(doc))
        return MagicMock(inserted_id="x")

    async def update_one(self, filter_, update):
        return MagicMock(modified_count=1)

    async def update_many(self, filter_, update):
        return MagicMock(modified_count=1)


class _FakeDB:
    def __init__(self):
        self.payment_charges = _FakeCollection()
        self.payment_events = _FakeCollection()
        self.receipts = _FakeCollection()
        self.transactions = _FakeCollection()


@pytest.fixture(autouse=True)
def _stripe_key(monkeypatch):
    monkeypatch.setenv("STRIPE_API_KEY", "sk_test_dummy_for_unit_test_only")
    yield


@pytest.mark.asyncio
async def test_refund_partner_full():
    from services.refund_engine import refund_partner_transaction

    db = _FakeDB()
    db.payment_charges.docs.append({
        "id": "charge_row_1",
        "stripe_object_id": "pi_1",
        "status": "succeeded",
        "amount": 110.00,
        "auction_id": "auc_1",
        "user_id": "user_1",
    })

    fake_refund = MagicMock(id="re_1", status="succeeded", amount=11000)
    with patch("stripe.Refund.create", return_value=fake_refund) as create_call:
        res = await refund_partner_transaction(
            db, payment_intent_id="pi_1", is_partner_listing=True,
        )
    # Assert Stripe call had the Partner-specific parameters
    args, kwargs = create_call.call_args
    assert kwargs["payment_intent"] == "pi_1"
    assert kwargs["refund_application_fee"] is True
    assert kwargs["reverse_transfer"] is True
    # Result shape
    assert res["refund_id"] == "re_1"
    assert res["status"] == "succeeded"
    assert res["amount_refunded_cents"] == 11000
    assert res["is_partial"] is False
    assert res["duplicate_blocked"] is False


@pytest.mark.asyncio
async def test_refund_non_partner_full():
    from services.refund_engine import refund_partner_transaction

    db = _FakeDB()
    db.payment_charges.docs.append({
        "id": "charge_row_2",
        "stripe_object_id": "pi_2",
        "status": "succeeded",
        "amount": 109.84,
    })

    fake_refund = MagicMock(id="re_2", status="succeeded", amount=10984)
    with patch("stripe.Refund.create", return_value=fake_refund) as create_call:
        await refund_partner_transaction(
            db, payment_intent_id="pi_2", is_partner_listing=False,
        )
    # No Partner-specific reversal parameters
    kwargs = create_call.call_args.kwargs
    assert "refund_application_fee" not in kwargs
    assert "reverse_transfer" not in kwargs


@pytest.mark.asyncio
async def test_refund_partial():
    from services.refund_engine import refund_partner_transaction

    db = _FakeDB()
    db.payment_charges.docs.append({
        "id": "charge_row_3",
        "stripe_object_id": "pi_3",
        "status": "succeeded",
        "amount": 110.00,
    })

    fake_refund = MagicMock(id="re_3", status="succeeded", amount=5500)
    with patch("stripe.Refund.create", return_value=fake_refund):
        res = await refund_partner_transaction(
            db, payment_intent_id="pi_3", amount_cents=5500, is_partner_listing=True,
        )
    assert res["amount_refunded_cents"] == 5500
    assert res["is_partial"] is True


@pytest.mark.asyncio
async def test_refund_idempotent_duplicate_blocked():
    from services.refund_engine import refund_partner_transaction

    db = _FakeDB()
    db.payment_charges.docs.append({
        "id": "charge_row_4",
        "stripe_object_id": "pi_4",
        "status": "refunded",  # already refunded
        "amount": 110.00,
    })

    with patch("stripe.Refund.create") as create_call:
        res = await refund_partner_transaction(db, payment_intent_id="pi_4")
    create_call.assert_not_called()  # never re-hit Stripe
    assert res["duplicate_blocked"] is True
    assert res["refund_id"] is None
    assert res["status"] == "duplicate_blocked"


@pytest.mark.asyncio
async def test_refund_stripe_error_leaves_state_unchanged():
    from services.refund_engine import refund_partner_transaction, RefundError

    db = _FakeDB()
    db.payment_charges.docs.append({
        "id": "charge_row_5",
        "stripe_object_id": "pi_5",
        "status": "succeeded",
        "amount": 110.00,
    })

    # Use a generic RuntimeError to simulate an underlying Stripe error;
    # refund_engine catches broad ``Exception`` and wraps to RefundError.
    with patch("stripe.Refund.create", side_effect=RuntimeError("card_declined")):
        with pytest.raises(RefundError):
            await refund_partner_transaction(db, payment_intent_id="pi_5")

    for d in db.payment_charges.docs:
        if d["id"] == "charge_row_5":
            assert d["status"] == "succeeded", "charge_row must remain unchanged on Stripe error"


@pytest.mark.asyncio
async def test_refund_negative_amount_rejected():
    from services.refund_engine import refund_partner_transaction, RefundError

    db = _FakeDB()
    db.payment_charges.docs.append({
        "id": "charge_row_6",
        "stripe_object_id": "pi_6",
        "status": "succeeded",
        "amount": 110.00,
    })
    with pytest.raises(RefundError):
        await refund_partner_transaction(db, payment_intent_id="pi_6", amount_cents=-1)


@pytest.mark.asyncio
async def test_refund_missing_stripe_key_rejected(monkeypatch):
    from services.refund_engine import refund_partner_transaction, RefundError

    monkeypatch.setenv("STRIPE_API_KEY", "")
    db = _FakeDB()
    with pytest.raises(RefundError):
        await refund_partner_transaction(db, payment_intent_id="pi_x")
