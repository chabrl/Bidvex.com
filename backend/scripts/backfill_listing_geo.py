"""
iter237 — One-time backfill: populate the `geo` (GeoJSON Point) field on
every listing that has a known city but no geo data yet.

Run:
    cd /app/backend && python scripts/backfill_listing_geo.py

Idempotent — re-runs are safe; already-geo-tagged listings are skipped.
"""
from __future__ import annotations

import asyncio
import os
import sys
from typing import Any, Dict, Tuple

# Path glue so this script can be executed standalone.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from utils import build_geo_point, resolve_city_coords  # noqa: E402


async def _backfill_collection(db, coll_name: str) -> Tuple[int, int, int]:
    """Returns (updated, skipped_unknown_city, already_tagged)."""
    coll = db[coll_name]
    updated = 0
    skipped_unknown = 0
    already_tagged = 0

    # Find docs whose geo field is missing OR malformed (no .coordinates array).
    needs_geo_filter = {
        "$or": [
            {"geo": {"$exists": False}},
            {"geo": None},
            {"geo.type": {"$ne": "Point"}},
            {"geo.coordinates": {"$exists": False}},
            {"geo.coordinates": None},
        ]
    }
    cursor = coll.find(needs_geo_filter, {"_id": 1, "id": 1, "title": 1, "city": 1, "region": 1})
    async for doc in cursor:
        city = (doc.get("city") or "").strip()
        province = (doc.get("region") or doc.get("province") or "").strip()
        if not city:
            skipped_unknown += 1
            continue
        geo = build_geo_point(city, province=province)
        if not geo:
            print(f"  ⚠️  skipping {coll_name}:{doc.get('id') or doc.get('_id')} "
                  f"— unknown city {city!r}")
            skipped_unknown += 1
            continue
        result = await coll.update_one({"_id": doc["_id"]}, {"$set": {"geo": geo}})
        if result.modified_count:
            updated += 1
            lng, lat = geo["coordinates"]
            print(f"  ✓ {coll_name} — updated {doc.get('id') or doc.get('_id')}: "
                  f"{(doc.get('title') or '')[:48]!r} → [{lng}, {lat}]")
    # Count already-tagged separately (a follow-up scan after the update).
    already_tagged = await coll.count_documents({"geo.coordinates": {"$type": "array"}})
    already_tagged -= updated  # subtract the ones we just tagged in this run
    if already_tagged < 0:
        already_tagged = 0
    return updated, skipped_unknown, already_tagged


async def main() -> Dict[str, Any]:
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    print(f"iter237 — backfilling geo on bazario_db:{db_name}…\n")

    totals: Dict[str, Tuple[int, int, int]] = {}
    for coll in ("listings", "multi_item_listings"):
        try:
            print(f"=== Collection: {coll} ===")
            totals[coll] = await _backfill_collection(db, coll)
            u, s, a = totals[coll]
            print(f"  · updated={u}, skipped_unknown={s}, already_tagged_before={a}\n")
        except Exception as e:  # noqa: BLE001
            print(f"  ⚠️  {coll} backfill failed: {e}")
            totals[coll] = (0, 0, 0)

    print("=== Migration complete ===")
    total_updated = sum(u for u, _, _ in totals.values())
    total_skipped = sum(s for _, s, _ in totals.values())
    total_already = sum(a for _, _, a in totals.values())
    print(f"  Total updated     : {total_updated}")
    print(f"  Skipped (no city) : {total_skipped}")
    print(f"  Already had coords: {total_already}")

    # Ensure the 2dsphere index exists on the `geo` field as the spec requires.
    print("\n=== Index check ===")
    try:
        idx_name = await db.listings.create_index(
            [("geo", "2dsphere")],
            sparse=True,
            background=True,
            name="geo_2dsphere",
        )
        print(f"  · listings — index ensured: {idx_name}")
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠️  listings index error: {e}")
    try:
        idx_name = await db.multi_item_listings.create_index(
            [("geo", "2dsphere")],
            sparse=True,
            background=True,
            name="geo_2dsphere",
        )
        print(f"  · multi_item_listings — index ensured: {idx_name}")
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠️  multi_item_listings index error: {e}")

    return {"totals": totals, "total_updated": total_updated}


if __name__ == "__main__":
    asyncio.run(main())
