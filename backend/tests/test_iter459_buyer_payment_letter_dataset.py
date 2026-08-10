"""
iter459 — Pytest regression suite for the buyer payment-letter dataset.

Verifies that `_build_settled_buyer_dataset` in `routes/invoices.py`:
  • Filters lots to ONLY those the given buyer won (never placeholder lots).
  • Excludes another buyer's lots and unsold lots.
  • Computes hammer_total = sum(unit_price × quantity) via
    services.hammer_total.resolve_hammer_total (not manually).
  • Reads buyer_premium / stripe_recovery / taxes / totals verbatim from
    services.fee_calculator.calculate_fee (no local recomputation).
  • Returns real paddle number from the paddle_numbers collection.
  • Raises 400 when the buyer won no lots.

Uses an in-memory FakeDB so no live network/mongo/backend is required.
Run with: pytest -q tests/test_iter459_buyer_payment_letter_dataset.py
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List

import pytest
from fastapi import HTTPException


# ─── Minimal FakeDB compatible with the helper's `find_one` / `find` usage ──
class FakeCursor:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    def __aiter__(self):
        self._i = 0
        return self

    async def __anext__(self):
        if self._i >= len(self._rows):
            raise StopAsyncIteration
        row = self._rows[self._i]
        self._i += 1
        return row


class FakeCollection:
    def __init__(self, rows: List[Dict[str, Any]]):
        self._rows = rows

    async def find_one(self, query: Dict[str, Any], projection=None):
        for r in self._rows:
            if all(r.get(k) == v for k, v in query.items()):
                return dict(r)
        return None

    def find(self, query: Dict[str, Any], projection=None):
        matches = [dict(r) for r in self._rows if all(r.get(k) == v for k, v in query.items())]
        return FakeCursor(matches)


class FakeDB:
    def __init__(self, users, paddles):
        self.users = FakeCollection(users)
        self.paddle_numbers = FakeCollection(paddles)


AUCTION_ID = "auc-iter459-pytest"
SELLER_ID = "seller-iter459"
BUYER_A = "buyer-A-iter459"
BUYER_B = "buyer-B-iter459"


def _mk_auction(lots=None):
    return {
        "id": AUCTION_ID,
        "title": "Iter459 Pytest Auction",
        "city": "Montréal",
        "region": "QC",
        "location_province": "QC",
        "seller_id": SELLER_ID,
        "listing_type": "lots",
        "auction_type": "lots",
        "status": "ended",
        "currency": "CAD",
        "auction_end_date": datetime.now(timezone.utc).isoformat(),
        "lots": lots or [],
    }


def _fixture_lots():
    """Buyer A wins Lot 1 (single) + Lot 2 (multi-qty); Buyer B wins Lot 3;
    Lot 4 is unsold."""
    return [
        {"lot_number": 1, "title": "Solo", "status": "sold",
         "winner_user_id": BUYER_A, "final_price": 100.0,
         "winning_quantity": 1, "quantity": 1},
        {"lot_number": 2, "title": "MultiQty3", "status": "sold",
         "winner_user_id": BUYER_A, "final_price": 7.0,
         "winning_quantity": 3, "quantity": 3,
         "multiply_hammer_by_quantity": True},
        {"lot_number": 3, "title": "MultiQty2", "status": "sold",
         "winner_user_id": BUYER_B, "final_price": 50.0,
         "winning_quantity": 2, "quantity": 2,
         "multiply_hammer_by_quantity": True},
        {"lot_number": 4, "title": "Unsold", "status": "ended",
         "winner_user_id": None, "final_price": 0.0, "quantity": 1},
    ]


def _fixture_users():
    return [
        {"id": SELLER_ID, "province": "QC", "subscription_tier": "free",
         "account_type": "individual"},
        {"id": BUYER_A, "province": "QC", "subscription_tier": "free",
         "account_type": "individual",
         "name": "BuyerA Pytest", "full_name": "BuyerA Pytest",
         "email": "a@a.a", "phone": "1", "billing_address": "1 Main"},
        {"id": BUYER_B, "province": "QC", "subscription_tier": "free",
         "account_type": "individual",
         "name": "BuyerB Pytest", "full_name": "BuyerB Pytest",
         "email": "b@b.b", "phone": "2", "billing_address": "2 Main"},
    ]


def _fixture_paddles():
    return [
        {"auction_id": AUCTION_ID, "user_id": BUYER_A, "paddle_number": 12001},
        {"auction_id": AUCTION_ID, "user_id": BUYER_B, "paddle_number": 12002},
    ]


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ────────────────────────────── Tests ──────────────────────────────────────

def test_buyer_a_dataset_contains_only_buyer_a_lots():
    """Regression A: Buyer A's payment-letter dataset must include ONLY
    Buyer A's real won lots (Lot 1 + Lot 2) with correct multi-qty math."""
    from routes.invoices import _build_settled_buyer_dataset
    db = FakeDB(_fixture_users(), _fixture_paddles())

    ds = _run(_build_settled_buyer_dataset(db, _mk_auction(_fixture_lots()), BUYER_A))

    assert len(ds["lots"]) == 2, "Only Buyer A's 2 won lots must appear"
    lot_numbers = sorted([l["lot_number"] for l in ds["lots"]])
    assert lot_numbers == [1, 2], "Only Lot 1 and Lot 2 (Buyer A's lots)"

    # Multi-qty math: unit × qty = line_total
    lot2 = next(l for l in ds["lots"] if l["lot_number"] == 2)
    assert lot2["unit_price"] == 7.0
    assert lot2["quantity"] == 3
    assert lot2["line_total"] == 21.0, f"3 × $7 must equal $21 (got {lot2['line_total']})"

    # Hammer_total = $100 + $21 = $121
    assert ds["hammer_total"] == 121.0

    # Real paddle 12001 — no placeholder
    assert ds["paddle_number"] == 12001

    # Real buyer name — no placeholder
    assert ds["buyer_name"] == "BuyerA Pytest"


def test_buyer_a_dataset_never_contains_buyer_b_or_unsold():
    """Regression B: Buyer B's lot and unsold lots MUST be absent."""
    from routes.invoices import _build_settled_buyer_dataset
    db = FakeDB(_fixture_users(), _fixture_paddles())
    ds = _run(_build_settled_buyer_dataset(db, _mk_auction(_fixture_lots()), BUYER_A))
    lot_numbers = {l["lot_number"] for l in ds["lots"]}
    assert 3 not in lot_numbers, "Buyer B's lot MUST NOT appear in Buyer A's letter"
    assert 4 not in lot_numbers, "Unsold lot MUST NOT appear in any buyer's letter"


def test_buyer_b_dataset_contains_only_buyer_b_lot():
    """Regression C: Buyer B's payment-letter dataset must include ONLY
    Buyer B's lot (Lot 3, $50 × 2 = $100)."""
    from routes.invoices import _build_settled_buyer_dataset
    db = FakeDB(_fixture_users(), _fixture_paddles())
    ds = _run(_build_settled_buyer_dataset(db, _mk_auction(_fixture_lots()), BUYER_B))
    assert len(ds["lots"]) == 1
    assert ds["lots"][0]["lot_number"] == 3
    assert ds["lots"][0]["unit_price"] == 50.0
    assert ds["lots"][0]["quantity"] == 2
    assert ds["lots"][0]["line_total"] == 100.0
    assert ds["hammer_total"] == 100.0
    assert ds["paddle_number"] == 12002


def test_dataset_raises_400_when_no_lots_won():
    """Regression D: A user who won zero lots must not be allowed to
    receive a payment letter — the helper must raise HTTPException(400)."""
    from routes.invoices import _build_settled_buyer_dataset
    db = FakeDB(_fixture_users(), _fixture_paddles())
    with pytest.raises(HTTPException) as exc_info:
        _run(_build_settled_buyer_dataset(db, _mk_auction(_fixture_lots()), "nobody-id"))
    assert exc_info.value.status_code == 400
    assert "No lots won" in str(exc_info.value.detail)


def test_dataset_uses_fee_engine_outputs_verbatim():
    """Regression E: buyer_premium, stripe_recovery, taxes, and
    buyer_total_charged in the dataset MUST equal the fee-engine values
    for the same hammer/tier/province — never recomputed locally."""
    from routes.invoices import _build_settled_buyer_dataset
    from services.fee_calculator import calculate_fee

    db = FakeDB(_fixture_users(), _fixture_paddles())
    ds = _run(_build_settled_buyer_dataset(db, _mk_auction(_fixture_lots()), BUYER_A))

    expected = calculate_fee(
        hammer_price=121.0,
        auction_type="lots",
        seller_account_type="individual",
        seller_tier="free",
        buyer_account_type="individual",
        buyer_tier="free",
        payment_method="stripe",
        card_type="domestic",
        buyer_province="QC",
        seller_province="QC",
    )
    assert ds["buyer_premium"] == round(expected["buyer_premium"], 2)
    assert ds["buyer_stripe_recovery"] == round(expected["buyer_stripe_recovery"], 2)
    assert ds["buyer_taxes"] == round(expected["buyer_taxes"], 2)
    assert ds["buyer_total_charged"] == round(expected["buyer_total_charged"], 2)
    # BP rate = 5% (individual/free tier default)
    assert ds["buyer_premium_rate_pct"] == 5.0


def test_dataset_returns_none_paddle_when_missing():
    """Regression F: If no paddle is recorded for this buyer + auction,
    the helper returns paddle_number=None (route layer decides whether to
    mint one). NEVER invent a fake paddle in the dataset itself."""
    from routes.invoices import _build_settled_buyer_dataset
    db = FakeDB(_fixture_users(), [])  # no paddle rows
    ds = _run(_build_settled_buyer_dataset(db, _mk_auction(_fixture_lots()), BUYER_A))
    assert ds["paddle_number"] is None


def test_dataset_tax_lines_only_include_engine_positive_amounts():
    """Regression G: buyer_tax_lines contains ONLY components the engine
    returned a positive amount for. For a QC buyer this is GST + QST;
    HST must be absent."""
    from routes.invoices import _build_settled_buyer_dataset
    db = FakeDB(_fixture_users(), _fixture_paddles())
    ds = _run(_build_settled_buyer_dataset(db, _mk_auction(_fixture_lots()), BUYER_A))
    kinds = {tl["kind"] for tl in ds["buyer_tax_lines"]}
    assert "gst" in kinds and "qst" in kinds
    assert "hst" not in kinds, "QC buyer must not receive an HST line"
    for tl in ds["buyer_tax_lines"]:
        assert tl["amount"] > 0, "No zero-amount tax lines allowed"
