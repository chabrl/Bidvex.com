"""
iter309 D1 — DRY RUN: Multi-Lot Category Restructure Migration Analysis

Reports counts of affected multi-lot auctions BEFORE writing anything.

Specifically reports:
  - Total multi-item listings in db.multi_item_listings
  - How many already have at least one lot carrying a `category` field
  - How many would be backfilled (lot.category copied from auction-level)
  - How many are MIXED (some lots already have category, some don't) — DANGER
  - How many auctions where a lot's existing category != auction-level — DANGER

Run:
  python /app/backend/scripts/iter309_d1_dryrun_multilot_categories.py
"""
import asyncio
import os
import sys
from collections import Counter

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


async def main():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        raise SystemExit("MONGO_URL and DB_NAME must be set")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    total = 0
    all_lots_categorized = 0
    no_lots_categorized = 0
    partial_lot_categorized = 0
    mismatched_categories = 0  # DANGER: at least one lot has category != auction-level
    mismatch_samples = []
    total_lots = 0
    lots_with_category = 0
    lots_without_category = 0
    distinct_auction_categories = Counter()

    async for doc in db.multi_item_listings.find({}, {"_id": 0, "id": 1, "title": 1, "category": 1, "lots": 1}):
        total += 1
        auction_cat = (doc.get("category") or "").strip()
        distinct_auction_categories[auction_cat] += 1
        lots = doc.get("lots") or []
        lot_cats = []
        for lot in lots:
            total_lots += 1
            lc = (lot.get("category") or "").strip() if isinstance(lot, dict) else ""
            lot_cats.append(lc)
            if lc:
                lots_with_category += 1
            else:
                lots_without_category += 1
        any_cat = any(c for c in lot_cats)
        all_cat = bool(lot_cats) and all(c for c in lot_cats)
        if all_cat:
            all_lots_categorized += 1
        elif not any_cat:
            no_lots_categorized += 1
        else:
            partial_lot_categorized += 1

        # Check for mismatched categories (existing lot.category != auction-level)
        for c in lot_cats:
            if c and auction_cat and c != auction_cat:
                mismatched_categories += 1
                if len(mismatch_samples) < 5:
                    mismatch_samples.append({
                        "auction_id": doc.get("id"),
                        "title": doc.get("title", "")[:60],
                        "auction_category": auction_cat,
                        "lot_category": c,
                    })
                break

    print("=" * 70)
    print("ITER309 D1 — DRY RUN REPORT: Multi-Lot Category Restructure")
    print("=" * 70)
    print(f"DB: {db_name}")
    print()
    print(f"Total multi_item_listings docs:          {total}")
    print(f"Total lots across all docs:              {total_lots}")
    print(f"Lots WITH existing category field:       {lots_with_category}")
    print(f"Lots WITHOUT existing category field:    {lots_without_category}")
    print()
    print("Per-auction breakdown:")
    print(f"  Auctions where ALL lots have category:        {all_lots_categorized}")
    print(f"  Auctions where NO lots have category:         {no_lots_categorized}")
    print(f"  Auctions with PARTIAL lot categorization:     {partial_lot_categorized}")
    print()
    print(f"⚠️  Auctions with MISMATCHED lot.category != auction-level: {mismatched_categories}")
    if mismatch_samples:
        print("  Samples (first 5):")
        for s in mismatch_samples:
            print(f"    - {s['auction_id']}: '{s['title']}' (auction='{s['auction_category']}', lot='{s['lot_category']}')")
    print()
    print("Top auction-level categories (distinct):")
    for cat, n in distinct_auction_categories.most_common(15):
        print(f"  {cat or '(blank)':40s}  {n}")
    print()
    print("=" * 70)
    print("PROPOSED BACKFILL:")
    print(f"  • Auctions to receive lot.category backfill (no existing lot.category):  {no_lots_categorized}")
    print(f"  • Lots to update (currently missing category):                            {lots_without_category}")
    print(f"  • Auctions to leave untouched (already fully categorized):                {all_lots_categorized}")
    print(f"  • Auctions needing review (partial / mismatch):                           {partial_lot_categorized + mismatched_categories}")
    print("=" * 70)

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
