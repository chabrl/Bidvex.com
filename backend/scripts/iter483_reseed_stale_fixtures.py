"""iter483 seed — restores stale test fixtures used by iter482 P4 e2e
and iter482+ CSV public-export tests.

Idempotent: safe to run multiple times.
Seeds:
  * iter482p4-e2e-multi-1d5c7d     (listings, [stripe, etransfer, cash])
  * iter482p4-e2e-cheque-only-a09e60 (listings, [cheque])
  * iter482p4-e2e-stripe-only-456890 (listings, [stripe])
  * iter474ui-veh-c2c08eb2         (vehicle_listings, public read)
"""
import os
import asyncio
from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


load_dotenv()


async def seed():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]

    testseller = await db.users.find_one({"email": "testseller@bidvex.com"},
                                         {"id": 1})
    if not testseller:
        raise SystemExit("testseller@bidvex.com missing — run iter308_reseed first")
    seller_id = testseller["id"]

    now = datetime.now(timezone.utc)
    end_dt = now + timedelta(days=7)

    fixtures = [
        {
            "collection": "listings",
            "id": "iter482p4-e2e-multi-1d5c7d",
            "methods": ["stripe", "etransfer", "cash"],
            "title": "iter482 P4 E2E — Multi-method Test Lot",
        },
        {
            "collection": "listings",
            "id": "iter482p4-e2e-cheque-only-a09e60",
            "methods": ["cheque"],
            "title": "iter482 P4 E2E — Cheque-only Test Lot",
        },
        {
            "collection": "listings",
            "id": "iter482p4-e2e-stripe-only-456890",
            "methods": ["stripe"],
            "title": "iter482 P4 E2E — Stripe-only Test Lot",
        },
    ]

    for f in fixtures:
        doc = {
            "id": f["id"],
            "seller_id": seller_id,
            "title": f["title"],
            "description": "Auto-seeded fixture for iter482 P4 e2e tests. Read-only.",
            "category": "test",
            "condition": "new",
            "starting_price": 10.0,
            "current_price": 10.0,
            "status": "active",
            "accepted_payment_methods": f["methods"],
            "accepted_payment_methods_source": "seed_fixture_iter483",
            "location": "Montreal, QC",
            "province": "QC",
            "country": "CA",
            "auction_start_date": now.isoformat(),
            "auction_end_date": end_dt.isoformat(),
            "created_at": now.isoformat(),
            "images": ["https://cdn.example/seed.jpg"],
            "seed_source": "iter483_reseed_stale_fixtures",
        }
        await db[f["collection"]].update_one(
            {"id": f["id"]}, {"$set": doc}, upsert=True)
        print(f"  ✓ upserted {f['collection']}/{f['id']} methods={f['methods']}")

    # ── iter474ui-veh-c2c08eb2 — vehicle_listings public read fixture ──
    veh_id = "iter474ui-veh-c2c08eb2"
    veh_doc = {
        "id": veh_id,
        "seller_id": seller_id,
        "seller_user_id": seller_id,
        "title": "iter474 UI — Public vehicle read fixture",
        "description": "Auto-seeded vehicle for iter482+ CSV public-export test.",
        "make": "Toyota",
        "model": "Corolla",
        "year": 2020,
        "vin": "TEST474UI0000C2C08",
        "starting_price": 5000.0,
        "current_price": 5000.0,
        "status": "active",
        "run_status": "active",
        "auction_access": "public",
        "province": "QC",
        "country": "CA",
        "location": "Montreal, QC",
        "auction_start_date": now.isoformat(),
        "auction_end_date": end_dt.isoformat(),
        "created_at": now.isoformat(),
        "images": ["https://cdn.example/veh-seed.jpg"],
        "category": "vehicle",
        "condition": "used",
        "seed_source": "iter483_reseed_stale_fixtures",
    }
    await db.vehicle_listings.update_one(
        {"id": veh_id}, {"$set": veh_doc}, upsert=True)
    print(f"  ✓ upserted vehicle_listings/{veh_id}")

    print("\nDone.  Fixtures ready for iter482 P4 e2e + CSV public export tests.")


if __name__ == "__main__":
    asyncio.run(seed())
