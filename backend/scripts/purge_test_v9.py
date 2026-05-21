"""
BidVex — Phase 6.0 hotfix maintenance script
Purges agent/test-seeded rows containing "TEST_V9" or other mock markers from
the production-facing collections. Safe to run repeatedly (idempotent).

Usage:
    cd /app/backend && python -m scripts.purge_test_v9
    cd /app/backend && python -m scripts.purge_test_v9 --apply        # actually delete
    cd /app/backend && python -m scripts.purge_test_v9 --dry-run       # default

Or call programmatically via the admin endpoint
    POST /api/admin/maintenance/purge-test-data
    body: {"dry_run": false}
"""
from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from motor.motor_asyncio import AsyncIOMotorClient

logger = logging.getLogger("purge_test_v9")

# Collections + the regex/match strategy applied. Each tuple is
# (collection_name, list_of_$or_clauses).
PURGE_TARGETS: list[tuple[str, list[Dict[str, Any]]]] = [
    ("listings", [
        {"title":       {"$regex": "TEST_V9",   "$options": "i"}},
        {"title":       {"$regex": "TEST_v9",   "$options": "i"}},
        {"description": {"$regex": "TEST_V9",   "$options": "i"}},
        {"title":       {"$regex": "^E2E_TEST", "$options": "i"}},
        {"id":          {"$regex": "^vehicle-block::"}},   # synthetic ids leaked from earlier flow
        {"seller_id":   {"$regex": "^test-seller", "$options": "i"}},
    ]),
    ("multi_item_listings", [
        {"title":       {"$regex": "TEST_V9",   "$options": "i"}},
        {"description": {"$regex": "TEST_V9",   "$options": "i"}},
    ]),
    ("manual_review_requests", [
        {"title":       {"$regex": "TEST_V9",   "$options": "i"}},
        {"description": {"$regex": "TEST_V9",   "$options": "i"}},
        {"category":    {"$regex": "TEST_V9",   "$options": "i"}},
        {"extra_context": {"$regex": "TEST_V9", "$options": "i"}},
        # Agent test artefacts also include detected_signals labelled "TEST_V9"
        {"detected_signals": {"$in": ["TEST_V9", "test_v9"]}},
    ]),
    ("listing_reviews", [
        {"listing_title":  {"$regex": "TEST_V9", "$options": "i"}},
        {"ai_reason_en":   {"$regex": "TEST_V9", "$options": "i"}},
        {"listing_id":     {"$regex": "^vehicle-block::"}},
        {"source":         "vehicle_block_manual_review",
         "listing_title": {"$regex": "TEST", "$options": "i"}},
    ]),
    ("broker_invoices", [
        {"listing_title": {"$regex": "TEST_V9", "$options": "i"}},
        {"buyer_email":   {"$regex": "test_v9", "$options": "i"}},
        {"id":            {"$regex": "^test-invoice-"}},
        {"id":            {"$regex": "^TEST_V9"}},
    ]),
    ("bids", [
        {"bidder_id":     {"$regex": "^test-", "$options": "i"}},
    ]),
    ("email_outbox", [
        {"context.listing_title": {"$regex": "TEST_V9", "$options": "i"}},
    ]),
]


async def purge_test_data(db, dry_run: bool = True) -> Dict[str, Any]:
    """Delete or count matching rows across PURGE_TARGETS. Returns a dict
    {collection -> matched_count or deleted_count}. dry_run=True only counts."""
    report: Dict[str, Any] = {"dry_run": dry_run, "counts": {}, "total_deleted": 0}

    for collection, clauses in PURGE_TARGETS:
        if not clauses:
            continue
        query = {"$or": clauses}
        try:
            matched = await db[collection].count_documents(query)
            if matched == 0:
                report["counts"][collection] = 0
                continue
            if dry_run:
                report["counts"][collection] = matched
                logger.info(f"[purge:{collection}] DRY-RUN would delete {matched} row(s)")
            else:
                result = await db[collection].delete_many(query)
                report["counts"][collection] = result.deleted_count
                report["total_deleted"] += result.deleted_count
                logger.info(f"[purge:{collection}] deleted {result.deleted_count} row(s)")
        except Exception as exc:
            logger.error(f"[purge:{collection}] failed: {exc}", exc_info=True)
            report["counts"][collection] = f"error:{type(exc).__name__}"
    return report


async def _main():
    apply = "--apply" in sys.argv
    dry_run = not apply
    db_name = os.environ.get("DB_NAME") or "bidvex_local"
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[db_name]
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    report = await purge_test_data(db, dry_run=dry_run)
    print("\n=== PURGE REPORT ===")
    print(f"DB: {db_name}")
    print(f"Mode: {'DRY-RUN (use --apply to delete)' if dry_run else 'APPLIED'}")
    for col, count in report["counts"].items():
        print(f"  {col:30s}  {count}")
    print(f"  total_deleted: {report['total_deleted']}")
    client.close()


if __name__ == "__main__":
    asyncio.run(_main())
