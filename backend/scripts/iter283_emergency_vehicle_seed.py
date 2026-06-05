"""
iter283-emergency — Direct DB-write seed for /vehicle-auctions.

The fast-track + general listings query already work in code, but the
preview environment has zero published vehicles. This script inserts
two canonical active vehicles directly into `db.listings` (the
universal-listings collection that the /api/vehicles endpoint
unions in via VEHICLE_TYPES + section). Idempotent (upserts by id).

Usage:
    python -m scripts.iter283_emergency_vehicle_seed
"""
from __future__ import annotations

import os
import asyncio
from datetime import datetime, timezone, timedelta

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()


SHERBROOKE = {
    "city": "Sherbrooke",
    "province": "QC",
    "coordinates": [-71.8929, 45.4042],
    "type": "Point",
}
MONTREAL = {
    "city": "Montreal",
    "province": "QC",
    "coordinates": [-73.5673, 45.5017],
    "type": "Point",
}


def _vehicle(_id: str, title: str, make: str, model: str, year: int,
             price: float, city: str, postal: str, loc: dict) -> dict:
    now = datetime.now(timezone.utc)
    end = now + timedelta(days=10)
    return {
        "id": _id,
        "title": title,
        "title_en": title,
        "title_fr": title,
        "description": (
            f"{year} {make} {model} — verified pre-launch vehicle "
            "listing. Clean title, professional inspection on file. "
            "Bidding open."
        ),
        "description_fr": (
            f"{make} {model} {year} — annonce de véhicule pré-lancement "
            "vérifiée. Titre propre, inspection professionnelle "
            "au dossier. Enchères ouvertes."
        ),
        "status": "active",
        "listing_type": "vehicle_auction",
        "section": "vehicles",
        "category": "Vehicles",
        "condition": "Used - Excellent",
        "make": make,
        "model": model,
        "year": year,
        "starting_price": price,
        "current_price": price,
        "current_bid": price,
        "bid_count": 0,
        "auction_end_date": end,
        "created_at": now,
        "updated_at": now,
        "seller_id": "iter283-emergency-seller",
        "seller_name": "BidVex Verified Dealer",
        "city": city,
        "region": "QC",
        "province": "QC",
        "country": "CA",
        "postal_code": postal,
        # Listing model expects `location` as STRING. The structured
        # GeoJSON Point lives under `geo` (iter237 canonical shape).
        "location": f"{city}, QC",
        "geo": {
            "type": "Point",
            "coordinates": loc["coordinates"],
            "city": city,
            "province": "QC",
            "source": "emergency_seed",
        },
        "visibility": "public",
        "images": [],
        "iter283_emergency_seed": True,
    }


SEED = [
    _vehicle(
        "iter283-emergency-vehicle-1",
        "2020 Honda CR-V EX-L AWD",
        "Honda", "CR-V EX-L AWD", 2020, 18500.0,
        "Sherbrooke", "J1H 1B1", SHERBROOKE,
    ),
    _vehicle(
        "iter283-emergency-vehicle-2",
        "2019 Ford F-150 XLT SuperCrew",
        "Ford", "F-150 XLT SuperCrew", 2019, 24900.0,
        "Montreal", "H2X 1Y4", MONTREAL,
    ),
]


async def main() -> None:
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    for v in SEED:
        await db.listings.update_one({"id": v["id"]}, {"$set": v}, upsert=True)
    count = await db.listings.count_documents(
        {"iter283_emergency_seed": True, "status": "active"}
    )
    print(f"[iter283-emergency] active emergency vehicles in db.listings: {count}")


if __name__ == "__main__":
    asyncio.run(main())
