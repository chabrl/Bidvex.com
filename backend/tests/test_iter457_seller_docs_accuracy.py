"""iter457 — Regression tests for seller-document data accuracy.

Guards against re-introducing the placeholder buyer / arbitrary-first-lot /
silent-zero-fee bugs in `_build_settled_seller_dataset`.

Run:
    cd /app/backend && python -m pytest tests/test_iter457_seller_docs_accuracy.py -v
"""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
load_dotenv("/app/backend/.env")


@pytest.fixture()
def db():
    # Per-function scope prevents cross-test event-loop closure with motor.
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


def _auction(
    seller_id: str,
    lots: List[Dict[str, Any]],
    location_province: str = "QC",
) -> Dict[str, Any]:
    return {
        "id": f"iter457-test-{seller_id}",
        "title": "iter457 pytest auction",
        "seller_id": seller_id,
        "listing_type": "lots",
        "location_province": location_province,
        "lots": lots,
    }


@pytest.mark.asyncio
async def test_zero_fee_never_from_missing_config(db):
    """Fee rate MUST come from the fee engine — never a silent zero because
    `auction.commission_rate` was missing."""
    from routes.invoices import _build_settled_seller_dataset

    auction = _auction(
        "iter457-nonexistent-seller",  # no user doc → defaults to individual/QC
        [
            {"lot_number": 1, "title": "L1", "description": "-",
             "status": "sold", "winner_user_id": "nobody",
             "final_price": 200.0, "quantity": 1},
        ],
    )
    r = await _build_settled_seller_dataset(db, auction, "iter457-nonexistent-seller")

    # Individual/QC/free tier → seller commission rate = 4.0%.
    assert r["commission_rate_pct"] == 4.0, r
    assert r["commission_rate_source"] == "fee_engine"
    # QC → GST 5% + QST 9.975% on the fee.
    assert r["tax_rate_gst_pct"] == 5.0
    assert r["tax_rate_qst_pct"] == 9.975
    # Fee amount = 4% of $200 = $8.00 (before Stripe recovery rounding).
    assert abs(r["total_platform_fee"] - 8.0) < 0.01
    # Tax on fee must be non-zero for QC.
    assert r["total_tax_on_fee"] > 1.0


@pytest.mark.asyncio
async def test_unsold_lot_has_no_buyer_and_no_fee(db):
    from routes.invoices import _build_settled_seller_dataset

    auction = _auction(
        "iter457-unsold-seller",
        [
            {"lot_number": 1, "title": "Sold", "description": "-",
             "status": "sold", "winner_user_id": "iter457-buyer",
             "final_price": 100.0, "quantity": 1},
            {"lot_number": 2, "title": "Unsold", "description": "-",
             "status": "ended", "winner_user_id": None,
             "final_price": 0.0, "quantity": 1},
        ],
    )
    r = await _build_settled_seller_dataset(db, auction, "iter457-unsold-seller")

    assert len(r["sold_lots"]) == 1
    assert len(r["unsold_lots"]) == 1
    unsold = r["unsold_lots"][0]
    # Placeholder-safety: unsold lot MUST NOT carry any buyer/paddle data.
    assert unsold["buyer_name"] is None
    assert unsold["paddle_number"] is None
    # And MUST NOT contribute to the totals.
    assert unsold["platform_fee"] == 0.0
    assert unsold["net_payout"] == 0.0
    assert unsold["hammer_price"] == 0.0
    # Sold-lot arithmetic is exact.
    assert r["sold_lots"][0]["hammer_price"] == 100.0


@pytest.mark.asyncio
async def test_multi_quantity_lot_uses_unit_times_qty(db):
    from routes.invoices import _build_settled_seller_dataset

    auction = _auction(
        "iter457-multi-seller",
        [
            {"lot_number": 1, "title": "Multi3", "description": "-",
             "status": "sold", "winner_user_id": "iter457-buyer",
             "final_price": 7.0, "quantity": 3,
             "multiply_hammer_by_quantity": True},
        ],
    )
    r = await _build_settled_seller_dataset(db, auction, "iter457-multi-seller")

    # unit × quantity ⇒ 7 × 3 = 21.
    assert r["total_hammer"] == 21.0
    assert r["sold_lots"][0]["quantity"] == 3
    assert r["sold_lots"][0]["unit_price"] == 7.0


@pytest.mark.asyncio
async def test_totals_reconcile_exactly_to_lot_lines(db):
    from routes.invoices import _build_settled_seller_dataset

    auction = _auction(
        "iter457-reconcile-seller",
        [
            {"lot_number": 1, "title": "A", "description": "-",
             "status": "sold", "winner_user_id": "b1",
             "final_price": 100.0, "quantity": 1},
            {"lot_number": 2, "title": "B", "description": "-",
             "status": "sold", "winner_user_id": "b2",
             "final_price": 50.0, "quantity": 2,
             "multiply_hammer_by_quantity": True},
        ],
    )
    r = await _build_settled_seller_dataset(db, auction, "iter457-reconcile-seller")

    sum_hammer = sum(l["hammer_price"] for l in r["sold_lots"])
    sum_fee = sum(l["platform_fee"] for l in r["sold_lots"])
    sum_tax = sum(l["seller_tax_on_fee"] for l in r["sold_lots"])
    sum_net = sum(l["net_payout"] for l in r["sold_lots"])

    assert r["total_hammer"] == round(sum_hammer, 2)
    assert r["total_platform_fee"] == round(sum_fee, 2)
    assert r["total_tax_on_fee"] == round(sum_tax, 2)
    assert r["total_net_payout"] == round(sum_net, 2)


@pytest.mark.asyncio
async def test_no_placeholder_test_buyer(db):
    """The helper must not synthesize placeholder buyer names or paddle
    numbers when a lot lacks a real winner_user_id."""
    from routes.invoices import _build_settled_seller_dataset

    auction = _auction(
        "iter457-nowinner-seller",
        [
            {"lot_number": 1, "title": "No winner but positive price",
             "description": "-", "status": "ended",
             "winner_user_id": None,
             "final_price": 55.0, "quantity": 1},
        ],
    )
    r = await _build_settled_seller_dataset(db, auction, "iter457-nowinner-seller")

    # Absent winner ⇒ not sold, no synthesized buyer/paddle.
    assert r["sold_lots"] == []
    l = r["lots"][0]
    assert l["status"] == "unsold"
    assert l["buyer_name"] is None
    assert l["paddle_number"] is None
