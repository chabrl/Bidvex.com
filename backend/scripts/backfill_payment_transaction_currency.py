"""
One-time migration: backfill `currency` field on legacy payment_transactions
that pre-date the Strict Payment System (iter185).

Spec Global Rule 1: "All Stripe charges must pass the correct currency code".
Existing pre-iter185 rows often have no currency or only nested in description.
This script sets `currency = "cad"` (Stripe-style lowercase) on every row
where the field is missing or empty.

Usage:
    cd /app/backend && python -m scripts.backfill_payment_transaction_currency

Output: prints scanned/updated counts; safe to re-run (idempotent).
"""
from __future__ import annotations

import asyncio
import os
import sys

# Allow running from /app/backend as a script
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


async def main() -> None:
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        raise SystemExit("MONGO_URL or DB_NAME missing in environment")

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # ── 1) payment_transactions
    scanned_pt = await db.payment_transactions.count_documents({})
    res_pt = await db.payment_transactions.update_many(
        {"$or": [{"currency": {"$exists": False}}, {"currency": None}, {"currency": ""}]},
        {"$set": {"currency": "cad"}},
    )

    # ── 2) listings (Marketplace) — backfill currency=CAD at the auction-level
    scanned_l = await db.listings.count_documents({})
    res_l = await db.listings.update_many(
        {"$or": [{"currency": {"$exists": False}}, {"currency": None}, {"currency": ""}]},
        {"$set": {"currency": "CAD"}},
    )

    # ── 3) storage_auctions
    scanned_sa = await db.storage_auctions.count_documents({})
    res_sa = await db.storage_auctions.update_many(
        {"$or": [{"currency": {"$exists": False}}, {"currency": None}, {"currency": ""}]},
        {"$set": {"currency": "CAD"}},
    )

    # ── 4) vehicle_listings
    scanned_v = await db.vehicle_listings.count_documents({})
    res_v = await db.vehicle_listings.update_many(
        {"$or": [{"currency": {"$exists": False}}, {"currency": None}, {"currency": ""}]},
        {"$set": {"currency": "CAD"}},
    )

    # ── 5) multi_item_listings
    scanned_mi = await db.multi_item_listings.count_documents({})
    res_mi = await db.multi_item_listings.update_many(
        {"$or": [{"currency": {"$exists": False}}, {"currency": None}, {"currency": ""}]},
        {"$set": {"currency": "CAD"}},
    )

    print("============================================================")
    print("Strict Payment System — Currency Backfill (iter185 hardening)")
    print("============================================================")
    print(f"payment_transactions: scanned={scanned_pt}, updated={res_pt.modified_count} → currency='cad'")
    print(f"listings            : scanned={scanned_l}, updated={res_l.modified_count} → currency='CAD'")
    print(f"storage_auctions    : scanned={scanned_sa}, updated={res_sa.modified_count} → currency='CAD'")
    print(f"vehicle_listings    : scanned={scanned_v}, updated={res_v.modified_count} → currency='CAD'")
    print(f"multi_item_listings : scanned={scanned_mi}, updated={res_mi.modified_count} → currency='CAD'")
    print("============================================================")

    # Sanity: confirm no rows remain without a currency in any collection
    remaining = {
        "payment_transactions": await db.payment_transactions.count_documents(
            {"$or": [{"currency": {"$exists": False}}, {"currency": None}, {"currency": ""}]}
        ),
        "listings": await db.listings.count_documents(
            {"$or": [{"currency": {"$exists": False}}, {"currency": None}, {"currency": ""}]}
        ),
        "storage_auctions": await db.storage_auctions.count_documents(
            {"$or": [{"currency": {"$exists": False}}, {"currency": None}, {"currency": ""}]}
        ),
        "vehicle_listings": await db.vehicle_listings.count_documents(
            {"$or": [{"currency": {"$exists": False}}, {"currency": None}, {"currency": ""}]}
        ),
        "multi_item_listings": await db.multi_item_listings.count_documents(
            {"$or": [{"currency": {"$exists": False}}, {"currency": None}, {"currency": ""}]}
        ),
    }
    print(f"Remaining rows without currency (should all be 0): {remaining}")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
