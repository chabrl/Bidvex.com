"""
iter309 D1 — BACKFILL: Multi-Lot Category Restructure

Copies the auction-level `category` onto every lot that's missing one and
computes the new `categories[]` aggregate on each multi-item listing.

Idempotent: re-running is a no-op once every lot has a category.

Run:
  python /app/backend/scripts/iter309_d1_backfill_multilot_categories.py

Add --dry-run to see counts without writing.
"""
import argparse
import asyncio
import os
import sys
from collections import Counter

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


async def main(dry_run: bool):
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        raise SystemExit("MONGO_URL and DB_NAME must be set")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    total = 0
    docs_updated = 0
    lots_backfilled = 0
    categories_aggregate_set = 0
    skipped_clean = 0

    async for doc in db.multi_item_listings.find({}, {"_id": 0, "id": 1, "category": 1, "lots": 1, "categories": 1}):
        total += 1
        auction_cat = (doc.get("category") or "").strip()
        existing_aggregate = list(doc.get("categories") or [])
        lots = doc.get("lots") or []
        if not isinstance(lots, list):
            continue

        modified = False
        updated_lots = []
        cat_counter = Counter()
        for lot in lots:
            if not isinstance(lot, dict):
                updated_lots.append(lot)
                continue
            lc = (lot.get("category") or "").strip()
            if not lc and auction_cat:
                lot = {**lot, "category": auction_cat}
                lc = auction_cat
                modified = True
                lots_backfilled += 1
            if lc:
                cat_counter[lc] += 1
            updated_lots.append(lot)

        # Compute the new categories aggregate.
        new_aggregate = sorted({c for c in cat_counter}, key=lambda c: -cat_counter[c])
        if auction_cat and auction_cat not in new_aggregate:
            new_aggregate.insert(0, auction_cat)
        # Only write categories[] if it differs from what's already on the doc.
        if new_aggregate != existing_aggregate:
            modified = True
            categories_aggregate_set += 1

        if not modified:
            skipped_clean += 1
            continue

        if dry_run:
            docs_updated += 1
            continue

        update_payload = {
            "lots":       updated_lots,
            "categories": new_aggregate,
        }
        # Backfill auction-level category if missing.
        if not auction_cat and new_aggregate:
            update_payload["category"] = new_aggregate[0]

        res = await db.multi_item_listings.update_one(
            {"id": doc["id"]},
            {"$set": update_payload},
        )
        if res.modified_count:
            docs_updated += 1

    print("=" * 70)
    print(f"ITER309 D1 — Backfill {'DRY-RUN' if dry_run else 'EXECUTE'}")
    print("=" * 70)
    print(f"Total multi_item_listings docs scanned:        {total}")
    print(f"Docs {'TO BE updated' if dry_run else 'updated'}:                          {docs_updated}")
    print(f"Lots backfilled with auction-level category:   {lots_backfilled}")
    print(f"Docs with refreshed categories[] aggregate:    {categories_aggregate_set}")
    print(f"Docs already clean (skipped):                  {skipped_clean}")
    print("=" * 70)
    client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Report counts only — no DB writes")
    args = parser.parse_args()
    asyncio.run(main(args.dry_run))
