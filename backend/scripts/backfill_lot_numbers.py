"""
BidVex — Migration: backfill `lot_number` on every multi-item listing.

Why: the platform now auto-assigns Lot 1..N at create time (industry standard).
Older listings created before this enforcement may have missing or arbitrary
`lot_number` values. This script walks every multi_item_listings document and
rewrites `lots[i].lot_number = i + 1` so the entire dataset is uniform.

Idempotent — safe to run repeatedly.

Run:
    python backend/scripts/backfill_lot_numbers.py
"""
import asyncio
import logging
import os
from pathlib import Path

env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())

from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-5s  %(message)s")
log = logging.getLogger("backfill-lot-numbers")

MONGO = os.environ.get("MONGO_URI") or os.environ.get("MONGO_URL")
DB = os.environ.get("DB_NAME", "bazario_db")


async def main():
    if not MONGO:
        log.error("MONGO_URI / MONGO_URL not set"); return
    client = AsyncIOMotorClient(MONGO, serverSelectionTimeoutMS=10000)
    db = client[DB]
    await client.admin.command("ping")

    cursor = db.multi_item_listings.find({}, {"_id": 0, "id": 1, "lots": 1})
    listings = await cursor.to_list(None)
    log.info(f"Scanning {len(listings)} multi-item listings...")

    updated = 0
    for listing in listings:
        lots = listing.get("lots") or []
        if not lots:
            continue
        # Rewrite lot_number 1..N — no-op when already correct
        needs_update = any(
            lot.get("lot_number") != idx + 1 for idx, lot in enumerate(lots)
        )
        if not needs_update:
            continue

        for idx, lot in enumerate(lots):
            lot["lot_number"] = idx + 1

        await db.multi_item_listings.update_one(
            {"id": listing["id"]},
            {"$set": {"lots": lots, "total_lots": len(lots)}},
        )
        updated += 1

    log.info(f"✅ Backfill complete — updated {updated}/{len(listings)} listings")
    client.close()


if __name__ == "__main__":
    asyncio.run(main())
