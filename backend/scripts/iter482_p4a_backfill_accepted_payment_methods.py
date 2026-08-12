"""
iter482 P4A — Backfill accepted_payment_methods on pre-P4 listings
==================================================================

**READ-ONLY on production** — this script must be run explicitly, is
idempotent, and never touches historical financial records
(transactions / receipts / seller_payouts).  It only adds the new
``accepted_payment_methods`` field to listing / auction documents that
predate the P4A schema.

Behaviour per collection:
    ``listings``, ``multi_item_listings``, ``vehicle_listings``,
    ``storage_auctions``, ``partner_listings``:

    For each row where ``accepted_payment_methods`` is missing/empty:
        1. Read the legacy singleton ``payment_method`` (if any).
        2. Canonicalise via ``services.payment_methods_registry.normalise``.
        3. Default to ``["stripe"]`` when no legacy singleton exists.
        4. Insert both ``accepted_payment_methods`` and
           ``accepted_payment_methods_snapshot_source`` = ``"backfill"``.
        5. **DO NOT** set the immutable snapshot yet — snapshotting
           happens at first bid, and pre-P4 rows may still be
           accepting bids.  If a row already has a bid history (i.e.
           ``bid_count > 0``), the snapshot IS locked at backfill
           time and the row also receives
           ``accepted_payment_methods_locked_at``.

Guardrails honoured:
  * No historical financial records mutated.
  * Idempotent — safe to re-run; only touches rows missing the field.
  * Dry-run supported via ``--dry-run``.
  * Preview-only — do not point at production without explicit
    approval per Master Payment Remediation §17.

Usage:
    python /app/backend/scripts/iter482_p4a_backfill_accepted_payment_methods.py --dry-run
    python /app/backend/scripts/iter482_p4a_backfill_accepted_payment_methods.py
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from services.payment_methods_registry import (  # noqa: E402
    normalise,
    InvalidPaymentMethodError,
    STRIPE,
)

COLLECTIONS: List[str] = [
    "listings",
    "multi_item_listings",
    "vehicle_listings",
    "storage_auctions",
    "partner_listings",
]


def _default_methods(legacy_singleton: str | None) -> list[str]:
    """Pick the initial accepted_payment_methods list for a pre-P4 row.
    Legacy singleton wins if canonicalisable; otherwise default to
    ``[STRIPE]`` (matches historical behaviour before P4A)."""
    if legacy_singleton:
        try:
            return [normalise(legacy_singleton)]
        except InvalidPaymentMethodError:
            pass
    return [STRIPE]


async def backfill_collection(db, collection: str, *, dry_run: bool) -> dict:
    coll = db[collection]
    query = {
        "$or": [
            {"accepted_payment_methods": {"$exists": False}},
            {"accepted_payment_methods": None},
            {"accepted_payment_methods": []},
        ]
    }
    scanned = 0
    to_update = 0
    updated = 0
    now = datetime.now(timezone.utc).isoformat()
    cursor = coll.find(query, {
        "_id": 1, "id": 1, "payment_method": 1, "bid_count": 1,
        "current_price": 1, "starting_price": 1,
    })
    async for doc in cursor:
        scanned += 1
        methods = _default_methods(doc.get("payment_method"))
        update: dict = {
            "accepted_payment_methods": methods,
            "accepted_payment_methods_source": "backfill_iter482_p4a",
        }
        # If the row already had bids at backfill time, lock the
        # snapshot in with the current list.  Snapshot source clearly
        # records this was a retroactive lock.
        has_bid = (doc.get("bid_count") or 0) > 0 or (
            (doc.get("current_price") or 0) > (doc.get("starting_price") or 0)
        )
        if has_bid:
            update["accepted_payment_methods_snapshot"] = methods
            update["accepted_payment_methods_locked_at"] = now
            update["accepted_payment_methods_snapshot_reason"] = (
                "backfill_locked_pre_first_bid_detected"
            )
        to_update += 1
        if not dry_run:
            await coll.update_one(
                {"_id": doc["_id"]},
                {"$set": update},
            )
            updated += 1
    return {
        "collection": collection,
        "scanned": scanned,
        "to_update": to_update,
        "updated": updated if not dry_run else 0,
    }


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report only; do not write.")
    args = parser.parse_args()

    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        print("MONGO_URL / DB_NAME must be set in the environment", file=sys.stderr)
        return 2

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print(f"=== iter482 P4A backfill — {'DRY RUN' if args.dry_run else 'WRITE'} ===")
    print(f"Database: {db_name}")
    total_scanned = 0
    total_touched = 0
    for coll in COLLECTIONS:
        report = await backfill_collection(db, coll, dry_run=args.dry_run)
        total_scanned += report["scanned"]
        total_touched += report["to_update"]
        print(
            f"  {report['collection']:<24} scanned={report['scanned']:>6} "
            f"needs_backfill={report['to_update']:>6}  "
            f"written={report['updated']:>6}"
        )
    print(f"— total scanned: {total_scanned}")
    print(f"— total needing backfill: {total_touched}")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
