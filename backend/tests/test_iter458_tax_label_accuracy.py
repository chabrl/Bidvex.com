"""iter458 — Tax-label accuracy regression tests.

Verifies that `_build_seller_tax_lines` faithfully reflects the existing
tax engine output for every supported province variant, WITHOUT inventing
or converting tax types.

Coverage (province → expected tax lines from the existing engine):
  QC      → GST + QST      (two rows)
  NS      → HST            (one row, never labeled GST)
  ON      → HST            (one row)
  AB      → GST            (one row, never HST)
  BC      → GST            (one row — PST is NOT computed by the current
                            engine; the test asserts this limitation)
  INTL    → zero tax       (no rows at all — no misleading label/amount)

Run:
    cd /app/backend && python -m pytest tests/test_iter458_tax_label_accuracy.py -v
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
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


def _one_sold_lot_auction(seller_id: str, province: str) -> Dict[str, Any]:
    return {
        "id": f"iter458-{province}-{seller_id}",
        "title": f"iter458 tax-label {province}",
        "seller_id": seller_id,
        "listing_type": "lots",
        "location_province": province,
        "lots": [
            {"lot_number": 1, "title": "L1", "description": "-",
             "status": "sold", "winner_user_id": "iter458-buyer",
             "final_price": 200.0, "quantity": 1},
        ],
    }


async def _seed_seller(db, seller_id: str, province: str) -> None:
    await db.users.delete_many({"id": seller_id})
    await db.users.insert_one({
        "id": seller_id,
        "email": f"{seller_id}@example.test",
        "name": f"VerifySeller {province}",
        "full_name": f"VerifySeller {province}",
        "province": province,
        "subscription_tier": "free",
        "account_type": "individual",
    })


async def _cleanup(db, seller_id: str) -> None:
    await db.users.delete_many({"id": seller_id})


@pytest.mark.asyncio
async def test_qc_returns_gst_and_qst_lines(db):
    from routes.invoices import _build_settled_seller_dataset
    seller_id = "iter458-qc-seller"
    await _seed_seller(db, seller_id, "QC")
    try:
        r = await _build_settled_seller_dataset(db, _one_sold_lot_auction(seller_id, "QC"), seller_id)
        lines = r["seller_tax_lines"]
        kinds = [l["kind"] for l in lines]
        assert kinds == ["gst", "qst"], f"QC must return exactly [gst, qst], got {kinds}"
        # No HST label anywhere for QC.
        for l in lines:
            assert l["label_en"] != "HST"
            assert l["label_fr"] != "TVH"
        # Bilingual mapping correct.
        assert lines[0]["label_en"] == "GST" and lines[0]["label_fr"] == "TPS"
        assert lines[1]["label_en"] == "QST" and lines[1]["label_fr"] == "TVQ"
        # Amounts are positive + sum matches engine's total_tax_on_fee.
        for l in lines:
            assert l["amount"] > 0
        assert abs(sum(l["amount"] for l in lines) - r["total_tax_on_fee"]) < 0.01
    finally:
        await _cleanup(db, seller_id)


@pytest.mark.asyncio
async def test_ns_returns_hst_line_never_gst(db):
    from routes.invoices import _build_settled_seller_dataset
    seller_id = "iter458-ns-seller"
    await _seed_seller(db, seller_id, "NS")
    try:
        r = await _build_settled_seller_dataset(db, _one_sold_lot_auction(seller_id, "NS"), seller_id)
        lines = r["seller_tax_lines"]
        kinds = [l["kind"] for l in lines]
        # Must be exactly [hst] — never GST/QST when engine returns HST.
        assert kinds == ["hst"], f"NS must return [hst] only, got {kinds}"
        assert lines[0]["label_en"] == "HST"
        assert lines[0]["label_fr"] == "TVH"
        assert lines[0]["amount"] > 0
        # Engine total reconciles.
        assert abs(lines[0]["amount"] - r["total_tax_on_fee"]) < 0.01
    finally:
        await _cleanup(db, seller_id)


@pytest.mark.asyncio
async def test_on_returns_hst_line_never_gst_plus_pst(db):
    from routes.invoices import _build_settled_seller_dataset
    seller_id = "iter458-on-seller"
    await _seed_seller(db, seller_id, "ON")
    try:
        r = await _build_settled_seller_dataset(db, _one_sold_lot_auction(seller_id, "ON"), seller_id)
        lines = r["seller_tax_lines"]
        kinds = [l["kind"] for l in lines]
        # Must be exactly [hst] — engine never splits HST into GST+PST.
        assert kinds == ["hst"], f"ON must return [hst] only, got {kinds}"
        assert lines[0]["label_en"] == "HST"
        assert lines[0]["amount"] > 0
    finally:
        await _cleanup(db, seller_id)


@pytest.mark.asyncio
async def test_ab_returns_gst_only(db):
    from routes.invoices import _build_settled_seller_dataset
    seller_id = "iter458-ab-seller"
    await _seed_seller(db, seller_id, "AB")
    try:
        r = await _build_settled_seller_dataset(db, _one_sold_lot_auction(seller_id, "AB"), seller_id)
        lines = r["seller_tax_lines"]
        kinds = [l["kind"] for l in lines]
        # Must be exactly [gst] — never HST, never QST.
        assert kinds == ["gst"], f"AB must return [gst] only, got {kinds}"
        assert lines[0]["label_en"] == "GST"
        assert lines[0]["label_fr"] == "TPS"
        assert lines[0]["amount"] > 0
    finally:
        await _cleanup(db, seller_id)


@pytest.mark.asyncio
async def test_bc_returns_only_what_engine_returns_no_pst_synthesis(db):
    """
    Existing engine limitation (documented in services/tax_rate_config.py):
    BC is bootstrapped as GST-only for B2B service place-of-supply. The
    engine does NOT compute a separate PST component. This test enforces
    that we NEVER synthesize a PST label from the seller's province.
    """
    from routes.invoices import _build_settled_seller_dataset
    seller_id = "iter458-bc-seller"
    await _seed_seller(db, seller_id, "BC")
    try:
        r = await _build_settled_seller_dataset(db, _one_sold_lot_auction(seller_id, "BC"), seller_id)
        lines = r["seller_tax_lines"]
        kinds = [l["kind"] for l in lines]
        # Only what the engine actually returned.
        assert kinds == ["gst"], f"BC engine returns GST only today; got {kinds}"
        # Anti-invention guard: no PST kind anywhere.
        for l in lines:
            assert l["kind"] != "pst"
            assert "PST" not in l["label_en"].upper()
            assert "TVP" not in l["label_fr"].upper()
    finally:
        await _cleanup(db, seller_id)


@pytest.mark.asyncio
async def test_intl_zero_tax_returns_no_lines(db):
    from routes.invoices import _build_settled_seller_dataset
    seller_id = "iter458-intl-seller"
    await _seed_seller(db, seller_id, "INTL")
    try:
        r = await _build_settled_seller_dataset(db, _one_sold_lot_auction(seller_id, "INTL"), seller_id)
        # Zero tax → empty list. Templates use this to suppress the tax
        # section entirely (no misleading $0 GST row).
        assert r["seller_tax_lines"] == [], r["seller_tax_lines"]
        # And the engine's total_tax_on_fee must indeed be zero.
        assert r["total_tax_on_fee"] == 0.0
    finally:
        await _cleanup(db, seller_id)


@pytest.mark.asyncio
async def test_multi_lot_aggregates_engine_components_by_kind(db):
    """
    Confirms that when multiple lots settle in the same province,
    per-lot engine tax amounts are summed by component (never by rate),
    and the tax_lines reflect the actual engine components only.
    """
    from routes.invoices import _build_settled_seller_dataset
    seller_id = "iter458-multi-seller"
    await _seed_seller(db, seller_id, "QC")
    try:
        auction = {
            "id": f"iter458-multi-{seller_id}",
            "title": "iter458 multi-lot QC",
            "seller_id": seller_id,
            "listing_type": "lots",
            "location_province": "QC",
            "lots": [
                {"lot_number": 1, "title": "A", "description": "-",
                 "status": "sold", "winner_user_id": "b1",
                 "final_price": 100.0, "quantity": 1},
                {"lot_number": 2, "title": "B", "description": "-",
                 "status": "sold", "winner_user_id": "b2",
                 "final_price": 50.0, "quantity": 2,
                 "multiply_hammer_by_quantity": True},
                {"lot_number": 3, "title": "Unsold", "description": "-",
                 "status": "ended", "winner_user_id": None,
                 "final_price": 0.0, "quantity": 1},
            ],
        }
        r = await _build_settled_seller_dataset(db, auction, seller_id)
        lines = r["seller_tax_lines"]
        kinds = [l["kind"] for l in lines]
        # QC: exactly GST + QST regardless of number of sold lots.
        assert kinds == ["gst", "qst"]
        # Sum of engine per-lot GST amounts equals aggregated line.
        gst_line = [l for l in lines if l["kind"] == "gst"][0]
        qst_line = [l for l in lines if l["kind"] == "qst"][0]
        sum_gst = round(sum(l.get("seller_gst_amount", 0.0) for l in r["sold_lots"]), 2)
        sum_qst = round(sum(l.get("seller_qst_amount", 0.0) for l in r["sold_lots"]), 2)
        assert abs(gst_line["amount"] - sum_gst) < 0.01
        assert abs(qst_line["amount"] - sum_qst) < 0.01
        # Unsold lot contributes nothing to any tax component.
        unsold = r["unsold_lots"][0]
        assert unsold["seller_gst_amount"] == 0.0
        assert unsold["seller_qst_amount"] == 0.0
        assert unsold["seller_hst_amount"] == 0.0
    finally:
        await _cleanup(db, seller_id)


@pytest.mark.asyncio
async def test_no_calc_engine_side_effect(db):
    """
    Sanity: the helper must not mutate seller_commission, hammer_price,
    seller_payout, or seller_taxes values coming from the engine.
    We compare `total_platform_fee`, `total_net_payout`, `total_tax_on_fee`
    against a direct fee-engine call to prove no override happened.
    """
    from routes.invoices import _build_settled_seller_dataset
    from services.fee_calculator import calculate_fee
    seller_id = "iter458-noop-seller"
    await _seed_seller(db, seller_id, "QC")
    try:
        r = await _build_settled_seller_dataset(db, _one_sold_lot_auction(seller_id, "QC"), seller_id)
        fee = calculate_fee(
            hammer_price=200.0, auction_type="lots",
            seller_account_type="individual", seller_tier="free",
            buyer_account_type="individual", buyer_tier="free",
            payment_method="stripe", card_type="domestic",
            buyer_province="QC", seller_province="QC",
        )
        assert abs(r["total_platform_fee"] - float(fee["seller_commission"])) < 0.01
        assert abs(r["total_tax_on_fee"] - float(fee["seller_taxes"])) < 0.01
        assert abs(r["total_net_payout"] - float(fee["seller_payout"])) < 0.01
    finally:
        await _cleanup(db, seller_id)
