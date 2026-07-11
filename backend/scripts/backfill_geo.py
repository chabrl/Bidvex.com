"""
iter343 BUG-1 — Idempotent geo backfill.

Sets the GeoJSON `geo` field (city-centroid) on every publicly searchable
document that is missing coordinates, across all 5 map-search collections.
Safe to re-run: docs that already carry valid geo.coordinates are skipped.

Run:  cd /app/backend && python3 scripts/backfill_geo.py
"""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from motor.motor_asyncio import AsyncIOMotorClient
from utils import build_geo_point

# (collection, city fields in priority order, province fields)
SOURCES = [
    ("listings",                   ["city"],                       ["region", "province"]),
    ("multi_item_listings",        ["city"],                       ["region", "province"]),
    ("vehicle_listings",           ["city"],                       ["region", "province"]),
    ("vehicle_multi_lot_auctions", [],                             []),   # city lives on lots
    ("storage_auctions",           ["facility_city", "city"],      ["facility_province", "province"]),
]

VALID_GEO = {
    "geo.coordinates.1": {"$exists": True},
}


def _first(doc, fields):
    for f in fields:
        v = doc.get(f)
        if v:
            return v
    return None


async def main():
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    grand_total = 0
    for coll_name, city_fields, prov_fields in SOURCES:
        coll = db[coll_name]
        query = {"$or": [
            {"geo": {"$exists": False}},
            {"geo": None},
            {"geo.coordinates": None},
        ]}
        fixed = scanned = 0
        async for doc in coll.find(query, {"_id": 1, "id": 1, "city": 1, "region": 1,
                                           "province": 1, "facility_city": 1,
                                           "facility_province": 1, "lots.location_city": 1,
                                           "lots.location_province": 1}):
            scanned += 1
            city = _first(doc, city_fields)
            prov = _first(doc, prov_fields)
            if not city and coll_name == "vehicle_multi_lot_auctions":
                lots = doc.get("lots") or []
                for l in lots:
                    if l.get("location_city"):
                        city, prov = l["location_city"], l.get("location_province")
                        break
            if not city:
                continue
            geo = build_geo_point(city, province=prov)
            if not geo:
                continue
            geo["source"] = "backfill_city_centroid"
            await coll.update_one({"_id": doc["_id"]}, {"$set": {"geo": geo}})
            fixed += 1
        grand_total += fixed
        print(f"{coll_name}: scanned {scanned} missing-geo docs, backfilled {fixed}")
    print(f"TOTAL backfilled: {grand_total}")


if __name__ == "__main__":
    asyncio.run(main())
