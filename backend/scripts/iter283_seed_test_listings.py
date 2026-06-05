"""
iter283 — Test-listing seed for verification matrix (Mission 6).

Inserts (idempotently — `id` is reused) ONE listing per section so
the integration matrix can confirm dual-visibility. Listings are
marked with `status: "test_only"` AFTER the verification run so
they don't pollute the public surfaces but remain in the audit
trail.

Run:
    python -m scripts.iter283_seed_test_listings
"""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()


SHERBROOKE_GEO = {
    "type": "Point",
    "coordinates": [-71.8929, 45.4042],
    "city": "Sherbrooke",
    "province": "QC",
    "source": "test_seed",
}

NOW = datetime.now(timezone.utc)
END_IN_7D = NOW + timedelta(days=7)


def _common(_id: str, title: str) -> dict:
    return {
        "id": _id,
        "title": title,
        "title_en": title,
        "title_fr": title,
        "description": "Auto-seeded iter283 verification listing. Not for bidding.",
        "description_fr": "Annonce de vérification iter283 (semence automatique).",
        "status": "active",
        "location": "Sherbrooke, QC",
        "city": "Sherbrooke",
        "region": "QC",
        "province": "QC",
        "country": "CA",
        "postal_code": "J1H 1B1",
        "auction_end_date": END_IN_7D,
        "created_at": NOW,
        "updated_at": NOW,
        "seller_id": "iter283-seed-seller",
        "seller_name": "iter283 Seed Seller",
        "images": [],
        "geo": SHERBROOKE_GEO,
        "iter283_test_seed": True,
    }


def listings_seed() -> list[dict]:
    """Return the 4 canonical test listings (one per section)."""
    return [
        {
            **_common("iter283-test-marketplace", "Test Marketplace Item — Laptop Dell XPS"),
            "listing_type": "marketplace",
            "section": "marketplace",
            "category": "Electronics",
            "condition": "Good",
            "starting_price": 150.0,
            "current_price": 150.0,
            "current_bid": 150.0,
        },
        {
            **_common("iter283-test-lot", "Test Lot — 10 Office Chairs"),
            "listing_type": "lot_auction",
            "section": "lots",
            "category": "Business & Industrial",
            "condition": "Good",
            "starting_price": 50.0,
            "current_price": 50.0,
            "current_bid": 50.0,
            "quantity": 10,
            "price_multiplied_by_quantity": True,
        },
        {
            **_common("iter283-test-storage", "Test Storage Unit — Unit 101"),
            "listing_type": "storage_locker",
            "section": "storage",
            "category": "Storage",
            "condition": "Unknown",
            "starting_price": 1.0,
            "current_price": 1.0,
            "current_bid": 1.0,
        },
        {
            **_common("iter283-test-vehicle", "Test Vehicle — 2019 Honda Civic"),
            "listing_type": "vehicle_auction",
            "section": "vehicles",
            "category": "Vehicles",
            "condition": "Good",
            "starting_price": 5000.0,
            "current_price": 5000.0,
            "current_bid": 5000.0,
            "requires_broker": True,
        },
    ]


async def upsert_all(mark_test_only: bool = False) -> dict:
    """Upsert the 4 seed listings. When `mark_test_only=True`, flip
    `status="test_only"` so they disappear from public surfaces
    while remaining in the database for audit."""
    db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
    results: dict = {}
    for doc in listings_seed():
        if mark_test_only:
            doc["status"] = "test_only"
        await db.listings.update_one(
            {"id": doc["id"]},
            {"$set": doc},
            upsert=True,
        )
        results[doc["id"]] = doc["status"]
    return results


async def main() -> None:
    mark_test = "--retire" in sys.argv
    out = await upsert_all(mark_test_only=mark_test)
    print(f"[iter283] seeded {len(out)} listings (retired={mark_test}):")
    for k, v in out.items():
        print(f"  • {k} → {v}")


if __name__ == "__main__":
    asyncio.run(main())
