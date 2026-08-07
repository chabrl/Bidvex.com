"""
iter445 — Storage Buyer's Premium Reconciliation
=================================================
One-shot idempotent migration that:

  1. Clears any per-listing `custom_buyer_premium_rate` set on
     legacy storage listings (`category=='storage_locker' OR
     listing_type=='storage_locker'`). The fixed 5 % platform BP
     now applies unconditionally to every storage sale.
  2. Rewrites `buyer_premium_pct` on `storage_auctions` docs from
     the legacy 0–20 range to a fixed `5.0` so the value is
     internally consistent with the new policy.
  3. Prints a summary of what changed so you can eyeball it in prod.

Run:  python /app/backend/scripts/iter445_reconcile_storage_bp.py
"""
import asyncio
import os
import sys
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")
sys.path.insert(0, "/app/backend")

from motor.motor_asyncio import AsyncIOMotorClient


async def main() -> None:
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    # ── 1) listings collection — storage_locker rows ────────────────
    filter_listings = {
        "$and": [
            {"$or": [
                {"category": "storage_locker"},
                {"listing_type": "storage_locker"},
            ]},
            {"custom_buyer_premium_rate": {"$ne": None}},
        ],
    }
    to_fix_listings = await db.listings.count_documents(filter_listings)
    res_listings = await db.listings.update_many(
        filter_listings,
        {"$set": {"custom_buyer_premium_rate": None}},
    )
    print(f"[listings] storage rows with legacy custom_buyer_premium_rate: {to_fix_listings}")
    print(f"[listings] updated → custom_buyer_premium_rate=None on {res_listings.modified_count} rows")

    # ── 2) storage_auctions collection — buyer_premium_pct field ────
    filter_sa = {"buyer_premium_pct": {"$ne": 5.0}}
    to_fix_sa = await db.storage_auctions.count_documents(filter_sa)
    res_sa = await db.storage_auctions.update_many(
        filter_sa,
        {"$set": {"buyer_premium_pct": 5.0}},
    )
    print(f"[storage_auctions] rows with non-5.0 buyer_premium_pct: {to_fix_sa}")
    print(f"[storage_auctions] updated → buyer_premium_pct=5.0 on {res_sa.modified_count} rows")

    print("\niter445 reconciliation complete. Buyer's premium is now fixed at 5 % across every storage auction.")


if __name__ == "__main__":
    asyncio.run(main())
