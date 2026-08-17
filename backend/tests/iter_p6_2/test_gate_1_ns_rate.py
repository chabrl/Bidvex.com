"""P6.2 Gate 1 — Nova Scotia rate correction regression tests.

Verifies:
* BOOTSTRAP_RATES["NS"] combined == 0.14 (CRA Notice 342).
* `get_tax_rate_sync("NS")` returns the corrected row.
* `calculate_taxes_for_recipient(amount, "NS")` computes 14% at cent grid.
* `fee_calculator.tax_on(amount, "NS")` computes 14% at cent grid.
* `seed_bootstrap_rates` reconciles a legacy 15% DB row → 14% and
  snapshots the old row to `tax_rate_config_history`.
"""
from __future__ import annotations

import os
import sys
from decimal import Decimal

import pytest

sys.path.insert(0, "/app/backend")

from services.tax_rate_config import BOOTSTRAP_RATES, get_tax_rate_sync  # noqa: E402
from services.tax_engine import calculate_taxes_for_recipient  # noqa: E402
from services.fee_calculator import tax_on  # noqa: E402


NS_TEST_GRID = [
    (Decimal("0.01"), Decimal("0.00")),
    (Decimal("1"),    Decimal("0.14")),
    (Decimal("100"),  Decimal("14.00")),
    (Decimal("1000"), Decimal("140.00")),
    (Decimal("500000"), Decimal("70000.00")),
]


def test_bootstrap_ns_is_14_percent():
    row = BOOTSTRAP_RATES["NS"]
    assert Decimal(str(row["hst"])) == Decimal("0.14"), row
    assert Decimal(str(row["combined"])) == Decimal("0.14"), row
    assert row["label"] == "HST (14%)"


def test_get_tax_rate_sync_ns_is_14_percent():
    row = get_tax_rate_sync("NS")
    assert Decimal(str(row["hst"])) == Decimal("0.14")
    assert Decimal(str(row["combined"])) == Decimal("0.14")


@pytest.mark.parametrize("amount,expected", NS_TEST_GRID)
def test_calculate_taxes_for_recipient_ns(amount, expected):
    r = calculate_taxes_for_recipient(float(amount), "NS")
    assert Decimal(str(r["total_tax"])) == expected


@pytest.mark.parametrize("amount,expected", NS_TEST_GRID)
def test_fee_calculator_tax_on_ns(amount, expected):
    r = tax_on(amount, "NS")
    assert Decimal(str(r["total"])) == expected


@pytest.mark.asyncio
async def test_seed_bootstrap_rates_reconciles_legacy_ns_15_pct(monkeypatch):
    """If a legacy DB row still has NS=15%, `seed_bootstrap_rates` must
    upsert to 14% AND snapshot the old row into history."""
    from services.tax_rate_config import seed_bootstrap_rates
    from motor.motor_asyncio import AsyncIOMotorClient

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        pytest.skip("no MongoDB in this environment")

    client = AsyncIOMotorClient(mongo_url)
    test_db = client[f"{db_name}_p6_2_gate1_test"]
    await test_db.tax_rate_config.delete_many({})
    await test_db.tax_rate_config_history.delete_many({})

    # Simulate a legacy NS=15% row
    await test_db.tax_rate_config.insert_one({
        "province": "NS",
        "gst": "0",
        "qst": "0",
        "hst": "0.15",
        "combined": "0.15",
        "label": "HST (15%)",
        "effective_from": "2024-01-01T00:00:00+00:00",
        "source": "legacy",
    })

    await seed_bootstrap_rates(test_db)

    ns_row = await test_db.tax_rate_config.find_one({"province": "NS"}, {"_id": 0})
    assert ns_row is not None
    assert Decimal(str(ns_row["combined"])) == Decimal("0.14"), ns_row
    assert Decimal(str(ns_row["hst"])) == Decimal("0.14")

    history = await test_db.tax_rate_config_history.find(
        {"province": "NS"}, {"_id": 0}
    ).to_list(length=10)
    assert any(
        Decimal(str(h.get("combined", "0"))) == Decimal("0.15") for h in history
    ), "legacy 15% must be snapshotted to history"

    # cleanup
    await client.drop_database(f"{db_name}_p6_2_gate1_test")
    client.close()
