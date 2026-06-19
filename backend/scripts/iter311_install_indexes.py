"""
iter311 — Admin all-collections compound indexes
=================================================
Adds the recommended compound indexes on the 4 listing collections so
the `$unionWith` aggregation in `/api/admin/listings/all-collections`
can serve the default `?sort=created_at_desc&status=<x>` queries
straight off the B-tree instead of doing an in-memory sort.

Indexes installed (all `background=True`, idempotent — re-runs are safe):

  listings                       : {status: 1, created_at: -1}
  vehicle_listings               : {status: 1, created_at: -1}
  vehicle_multi_lot_auctions     : {status: 1, created_at: -1}
  multi_item_listings            : {status: 1, created_at: -1}

We also add a single-field index on `seller_id` per collection so the
admin's "filter by one seller" path is constant-time.

Expected delta: server `perf_ms` drops from ~39 ms → <10 ms for the
typical "active, newest first" admin query (matches the iter311
finish-tool prediction).

Run:
    python /app/backend/scripts/iter311_install_indexes.py
"""
from __future__ import annotations

import os
from typing import List, Tuple

from pymongo import ASCENDING, DESCENDING, MongoClient
from dotenv import load_dotenv


load_dotenv("/app/backend/.env")
client = MongoClient(os.environ["MONGO_URL"])
db = client[os.environ["DB_NAME"]]


LISTING_COLLECTIONS: Tuple[str, ...] = (
    "listings",
    "vehicle_listings",
    "vehicle_multi_lot_auctions",
    "multi_item_listings",
)


def _install(coll_name: str) -> List[str]:
    """Install the iter311 indexes on a single collection. Returns the
    list of index names actually created (may be empty if everything
    was already in place)."""
    coll = db[coll_name]
    created: List[str] = []

    # Pre-iter311 inventory — used to skip dup creates
    existing_keys = {
        tuple(idx["key"].items()) for idx in coll.list_indexes()
    }

    targets = [
        (
            [("status", ASCENDING), ("created_at", DESCENDING)],
            "iter311_status_1_created_at_-1",
        ),
        (
            [("seller_id", ASCENDING)],
            "iter311_seller_id_1",
        ),
    ]
    for spec, name in targets:
        key_tuple = tuple(spec)
        if key_tuple in existing_keys:
            print(f"  · {coll_name}.{name} already present")
            continue
        try:
            actual = coll.create_index(
                spec, name=name, background=True,
            )
            created.append(actual)
            print(f"  ✓ {coll_name}.{actual} created")
        except Exception as exc:  # pragma: no cover
            # Duplicate name in the existing index list (different spec
            # under same name) — not fatal, just report.
            print(f"  ! {coll_name}.{name} skipped: {exc}")

    return created


def main():
    print("iter311 — Installing admin/all-collections compound indexes")
    print(f"  target DB: {db.name}")
    print(f"  collections: {', '.join(LISTING_COLLECTIONS)}\n")

    total_created = 0
    for coll in LISTING_COLLECTIONS:
        new = _install(coll)
        total_created += len(new)
        print()

    print(f"iter311 indexes complete — {total_created} new index(es) created across "
          f"{len(LISTING_COLLECTIONS)} collection(s).")

    # Verification — print the final index inventory per collection
    print("\nFinal index inventory:")
    for coll_name in LISTING_COLLECTIONS:
        names = [idx["name"] for idx in db[coll_name].list_indexes()]
        print(f"  {coll_name}: {names}")


if __name__ == "__main__":
    main()
