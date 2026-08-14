"""
iter484.2 Gate 2 — Vehicle reserve UI test seed.

Creates three vehicle listings covering the three buyer-facing reserve
states, PLUS one vehicle multi-lot event with three lots covering the
same states.  Preview only.  Idempotent — re-running upserts.

Usage:
    python -m scripts.seed_iter484_2_gate2_vehicles
"""
from __future__ import annotations
import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME")

client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]


NOW = datetime.now(timezone.utc)
END_1D = NOW + timedelta(days=1)


VEHICLE_FIXTURES = [
    {
        "id": "iter484-2-gate2-no-reserve",
        "seller_id": "iter484-2-gate2-seed-seller",
        "title": "2022 Ford F-150 (No Reserve) — TEST",
        "make": "Ford",
        "model": "F-150",
        "year": 2022,
        "vin": "TESTGATE2NORES00001",
        "mileage": 42000,
        "body_type": "truck",
        "transmission": "auto",
        "fuel_type": "gas",
        "drivetrain": "4wd",
        "exterior_color": "white",
        "interior_color": "black",
        "condition_status": "used_good",
        "location_province": "QC",
        "location_city": "Montréal",
        "starting_price": 20000,
        "current_bid": 22500,
        "bid_increment": 250,
        "bid_count": 3,
        "reserve_price": 0,
        "reserve_met": False,
        "status": "active",
        "auction_type": "timed",
        "visibility": "public",
        "auction_access": "public",
        "created_at": NOW,
        "start_time": NOW,
        "end_time": END_1D,
        "auction_end_date": END_1D,
        "media": [],
        "views_count": 0,
        "accepted_payment_methods": ["stripe", "etransfer"],
        "is_demo": False,
    },
    {
        "id": "iter484-2-gate2-reserve-not-met",
        "seller_id": "iter484-2-gate2-seed-seller",
        "title": "2023 Honda Civic (Reserve Not Met) — TEST",
        "make": "Honda",
        "model": "Civic",
        "year": 2023,
        "vin": "TESTGATE2NOTMET0001",
        "mileage": 15000,
        "body_type": "sedan",
        "transmission": "auto",
        "fuel_type": "gas",
        "drivetrain": "fwd",
        "exterior_color": "silver",
        "interior_color": "black",
        "condition_status": "used_like_new",
        "location_province": "QC",
        "location_city": "Montréal",
        "starting_price": 18000,
        "current_bid": 19500,
        "bid_increment": 100,
        "bid_count": 4,
        "reserve_price": 25000,   # ← above current bid
        "reserve_met": False,
        "status": "active",
        "auction_type": "timed",
        "visibility": "public",
        "auction_access": "public",
        "created_at": NOW,
        "start_time": NOW,
        "end_time": END_1D,
        "auction_end_date": END_1D,
        "media": [],
        "views_count": 0,
        "accepted_payment_methods": ["stripe", "cash", "etransfer"],
        "is_demo": False,
    },
    {
        "id": "iter484-2-gate2-reserve-met",
        "seller_id": "iter484-2-gate2-seed-seller",
        "title": "2020 Toyota RAV4 (Reserve Met) — TEST",
        "make": "Toyota",
        "model": "RAV4",
        "year": 2020,
        "vin": "TESTGATE2MET0000001",
        "mileage": 65000,
        "body_type": "suv",
        "transmission": "auto",
        "fuel_type": "gas",
        "drivetrain": "awd",
        "exterior_color": "blue",
        "interior_color": "gray",
        "condition_status": "used_good",
        "location_province": "ON",
        "location_city": "Toronto",
        "starting_price": 15000,
        "current_bid": 22000,     # ← above reserve
        "bid_increment": 250,
        "bid_count": 7,
        "reserve_price": 20000,
        "reserve_met": True,      # ← authoritative flag
        "status": "active",
        "auction_type": "timed",
        "visibility": "public",
        "auction_access": "public",
        "created_at": NOW,
        "start_time": NOW,
        "end_time": END_1D,
        "auction_end_date": END_1D,
        "media": [],
        "views_count": 0,
        "accepted_payment_methods": ["stripe", "cheque"],
        "is_demo": False,
    },
]


VEHICLE_SELLER_FIXTURE = {
    "id": "iter484-2-gate2-seed-seller",
    "user_id": "iter484-2-gate2-seed-user",
    "seller_type": "dealer",
    "business_name": "Iter484.2 Gate 2 Test Dealer",
    "average_rating": 5.0,
    "total_sold": 42,
    "verification_status": "approved",
    "dealer_license_verified": True,
    "dealer_license_number": "TEST-GATE2",
    "dealer_license_province": "QC",
}


VML_EVENT_FIXTURE = {
    "id": "iter484-2-gate2-vml-event",
    "dealer_seller_id": "iter484-2-gate2-seed-seller",
    "title": "Gate 2 Multi-Lot Reserve Test Event",
    "location": "Test Yard, QC",
    "location_city": "Montréal",
    "location_province": "QC",
    "status": "live",
    "start_time": NOW,
    "end_time": END_1D,
    "created_at": NOW,
    "updated_at": NOW,
    "timing_mode": "individual",
    "bid_increment": 100,
    "accepted_payment_methods": ["stripe", "etransfer"],
    "lots": [
        {
            "id": "iter484-2-gate2-vml-lot-none",
            "lot_number": 1,
            "vin": "TESTVMLNONE00000001",
            "year": 2020,
            "make": "Chevrolet",
            "model": "Silverado",
            "title": "Silverado (No Reserve) — TEST",
            "description": "seed",
            "mileage": 55000,
            "starting_price": 15000,
            "current_bid": 18000,
            "bid_increment": 100,
            "bid_count": 3,
            "reserve_price": None,
            "reserve_met": False,
            "status": "live",
            "location_city": "Montréal",
            "location_province": "QC",
            "end_time": END_1D,
        },
        {
            "id": "iter484-2-gate2-vml-lot-notmet",
            "lot_number": 2,
            "vin": "TESTVMLNOTMET000002",
            "year": 2021,
            "make": "Jeep",
            "model": "Grand Cherokee",
            "title": "Grand Cherokee (Reserve Not Met) — TEST",
            "description": "seed",
            "mileage": 40000,
            "starting_price": 20000,
            "current_bid": 22500,
            "bid_increment": 100,
            "bid_count": 4,
            "reserve_price": 30000,
            "reserve_met": False,
            "status": "live",
            "location_city": "Montréal",
            "location_province": "QC",
            "end_time": END_1D,
        },
        {
            "id": "iter484-2-gate2-vml-lot-met",
            "lot_number": 3,
            "vin": "TESTVMLMET000000003",
            "year": 2019,
            "make": "Nissan",
            "model": "Rogue",
            "title": "Rogue (Reserve Met) — TEST",
            "description": "seed",
            "mileage": 78000,
            "starting_price": 10000,
            "current_bid": 15000,
            "bid_increment": 100,
            "bid_count": 6,
            "reserve_price": 12000,
            "reserve_met": True,
            "status": "live",
            "location_city": "Montréal",
            "location_province": "QC",
            "end_time": END_1D,
        },
    ],
    "sequence": [
        "iter484-2-gate2-vml-lot-none",
        "iter484-2-gate2-vml-lot-notmet",
        "iter484-2-gate2-vml-lot-met",
    ],
    "bids": [],
}


async def main():
    inserted, updated = 0, 0
    for v in VEHICLE_FIXTURES:
        r = await db.vehicle_listings.replace_one({"id": v["id"]}, v, upsert=True)
        if r.upserted_id is not None:
            inserted += 1
        else:
            updated += 1
    await db.vehicle_sellers.replace_one(
        {"id": VEHICLE_SELLER_FIXTURE["id"]},
        VEHICLE_SELLER_FIXTURE,
        upsert=True,
    )
    r = await db.vehicle_multi_lot_auctions.replace_one(
        {"id": VML_EVENT_FIXTURE["id"]},
        VML_EVENT_FIXTURE,
        upsert=True,
    )
    print(f"Seeded vehicle_listings: inserted={inserted}, updated={updated}")
    print(f"Seeded vehicle_sellers: 1 (dealer)")
    print(f"Seeded vehicle_multi_lot_auctions: {'inserted' if r.upserted_id else 'updated'}")
    for v in VEHICLE_FIXTURES:
        print(f"  → /vehicles/{v['id']}  (reserve_price={v['reserve_price']}, reserve_met={v['reserve_met']})")
    print(f"  → /vehicle-multi-lot-auctions/{VML_EVENT_FIXTURE['id']}  (3 lots)")


if __name__ == "__main__":
    asyncio.run(main())
