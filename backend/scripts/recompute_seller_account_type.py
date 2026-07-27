"""iter393 — One-off migration: recompute + overwrite persisted
`seller_account_type` on every listing.

Reads each doc in `listings`, `multi_item_listings`, and `vehicle_listings`,
loads the corresponding seller from `db.users`, runs
`services.listing_seller_enrichment.resolve_seller_account_type(seller, context)`
with the collection-appropriate context, and writes the result back to the
persisted `seller_account_type` field. Also mirrors the derived boolean
sibling fields (`seller_is_partner`, `seller_is_vehicle_dealer`,
`seller_is_storage_facility`) that `enrich_listing_with_seller` maintains, so
the persisted snapshot stays consistent.

Emits a per-collection summary at the end:

    ═══════════════════════════════════════════════════════════════════
    SELLER_ACCOUNT_TYPE RECOMPUTE SUMMARY  (dry_run=False)
    ═══════════════════════════════════════════════════════════════════
    [listings]
      docs_scanned           = 42
      docs_updated           = 3
      docs_unchanged         = 38
      docs_skipped_no_seller = 1
      transitions            = {'business→individual': 2, 'None→partner': 1}
    ...
    TOTALS  scanned=…  updated=…  unchanged=…  skipped=…

Behaviour:
  • `--dry-run` — walk + report only, no writes.
  • `--collection <name>` — scope to one of the three collections.
  • `--limit N` — process first N docs (for smoke tests on prod).
  • Idempotent: re-running finds nothing to update once the sweep is clean.
  • Failure-tolerant: a single doc raising doesn't stop the sweep;
    it's counted under `docs_error` with the exception name.
  • Exit code 0 always (report is written to stdout + logger).

Usage:
    cd /app/backend
    python -m scripts.recompute_seller_account_type --dry-run
    python -m scripts.recompute_seller_account_type
    python -m scripts.recompute_seller_account_type --collection multi_item_listings
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from typing import Any, Dict, List, Optional

# Make `services.*` and this script importable when run directly.
_HERE    = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.dirname(_HERE)
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from dotenv import load_dotenv  # noqa: E402
load_dotenv(os.path.join(_BACKEND, ".env"))

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

from services.listing_seller_enrichment import resolve_seller_account_type  # noqa: E402


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("recompute_seller_account_type")


# ── Which collection gets which listing_context ──────────────────────
COLLECTIONS: Dict[str, Dict[str, Any]] = {
    "listings":            {"context": "general"},
    "multi_item_listings": {"context": "lots"},
    "vehicle_listings":    {"context": "vehicle"},
}


# ── Derived boolean sibling fields kept consistent with account_type ──
def _derive_sibling_fields(new_account_type: str) -> Dict[str, Any]:
    return {
        "seller_account_type":         new_account_type,
        "seller_is_partner":           new_account_type == "partner",
        "seller_is_vehicle_dealer":    new_account_type == "vehicle_dealer",
        "seller_is_storage_facility":  new_account_type == "storage_facility",
    }


async def _seller_for(db, listing: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    seller_id = (
        listing.get("seller_id")
        or listing.get("owner_id")
        or listing.get("user_id")
    )
    if not seller_id:
        return None
    return await db.users.find_one({"id": seller_id}, {"_id": 0})


async def recompute_collection(
    db,
    coll_name: str,
    *,
    context: str,
    dry_run: bool,
    limit: Optional[int] = None,
) -> Dict[str, Any]:
    stats: Dict[str, Any] = {
        "docs_scanned":           0,
        "docs_updated":           0,
        "docs_unchanged":         0,
        "docs_skipped_no_seller": 0,
        "docs_error":             0,
        "transitions":            {},   # {"old→new": count}
        "errors":                 {},   # {"ExceptionName": count}
    }
    logger.info("─── %s (context=%s, dry_run=%s) ───", coll_name, context, dry_run)

    projection = {
        "_id": 0,
        "id": 1,
        "seller_id": 1,
        "owner_id": 1,
        "user_id": 1,
        "seller_account_type": 1,
    }
    cursor = db[coll_name].find({}, projection)
    if limit:
        cursor = cursor.limit(int(limit))

    async for doc in cursor:
        stats["docs_scanned"] += 1
        listing_id = doc.get("id")
        if not listing_id:
            stats["docs_error"] += 1
            stats["errors"]["missing_id"] = stats["errors"].get("missing_id", 0) + 1
            continue

        try:
            seller = await _seller_for(db, doc)
            if seller is None:
                stats["docs_skipped_no_seller"] += 1
                continue

            old_type = doc.get("seller_account_type")
            new_type = (resolve_seller_account_type(seller, context) or "individual").lower()

            if (old_type or "").lower() == new_type:
                stats["docs_unchanged"] += 1
                continue

            transition_key = f"{old_type!r}→{new_type!r}"
            stats["transitions"][transition_key] = stats["transitions"].get(transition_key, 0) + 1

            if not dry_run:
                update_fields = _derive_sibling_fields(new_type)
                await db[coll_name].update_one(
                    {"id": listing_id},
                    {"$set": update_fields},
                )
            stats["docs_updated"] += 1

            if stats["docs_updated"] <= 20 or stats["docs_updated"] % 100 == 0:
                logger.info(
                    "  %s.%s : %s → %s%s",
                    coll_name, listing_id, old_type, new_type,
                    "  (dry-run)" if dry_run else "",
                )

        except Exception as e:  # noqa: BLE001 — never let one bad doc block the sweep
            stats["docs_error"] += 1
            name = type(e).__name__
            stats["errors"][name] = stats["errors"].get(name, 0) + 1
            logger.warning("  %s.%s errored: %s: %s", coll_name, listing_id, name, e)

    return stats


async def _run(args) -> int:
    mongo_url = os.environ["MONGO_URL"]
    db_name   = os.environ["DB_NAME"]
    client    = AsyncIOMotorClient(mongo_url)
    db        = client[db_name]

    target = (args.collection or "").strip()
    if target and target not in COLLECTIONS:
        logger.error("Unknown collection %r. Valid: %s", target, list(COLLECTIONS))
        return 2

    targets = [target] if target else list(COLLECTIONS)

    per_coll: Dict[str, Dict[str, Any]] = {}
    grand = {
        "docs_scanned": 0, "docs_updated": 0, "docs_unchanged": 0,
        "docs_skipped_no_seller": 0, "docs_error": 0,
    }

    try:
        for coll_name in targets:
            ctx = COLLECTIONS[coll_name]["context"]
            stats = await recompute_collection(
                db, coll_name, context=ctx,
                dry_run=args.dry_run, limit=args.limit,
            )
            per_coll[coll_name] = stats
            for k in grand:
                grand[k] += stats.get(k, 0)

        # ── Per-collection summary ───────────────────────────────────
        logger.info("═" * 68)
        logger.info(
            "SELLER_ACCOUNT_TYPE RECOMPUTE SUMMARY  (dry_run=%s)",
            args.dry_run,
        )
        logger.info("═" * 68)
        for coll_name, s in per_coll.items():
            logger.info("[%s]", coll_name)
            logger.info("  docs_scanned           = %d", s["docs_scanned"])
            logger.info("  docs_updated           = %d", s["docs_updated"])
            logger.info("  docs_unchanged         = %d", s["docs_unchanged"])
            logger.info("  docs_skipped_no_seller = %d", s["docs_skipped_no_seller"])
            if s["docs_error"]:
                logger.info("  docs_error             = %d  reasons=%s",
                            s["docs_error"], dict(s["errors"]))
            if s["transitions"]:
                logger.info("  transitions            = %s", dict(s["transitions"]))
        logger.info("─" * 68)
        logger.info(
            "TOTALS  scanned=%d  updated=%d  unchanged=%d  skipped_no_seller=%d  errors=%d",
            grand["docs_scanned"], grand["docs_updated"], grand["docs_unchanged"],
            grand["docs_skipped_no_seller"], grand["docs_error"],
        )
        logger.info("═" * 68)
    finally:
        client.close()

    return 0 if grand["docs_error"] == 0 else 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report only; never write to MongoDB.")
    parser.add_argument("--collection", type=str, default=None,
                        help=f"Scope to one collection {sorted(COLLECTIONS)}.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Process at most N docs per collection.")
    args = parser.parse_args()
    exit_code = asyncio.run(_run(args))
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
