"""iter344 — Seed a live vehicle multi-lot event + verify feeds decompose per lot."""
import asyncio, os, uuid
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv('/app/backend/.env')

async def main():
    db = AsyncIOMotorClient(os.environ['MONGO_URL'])[os.environ['DB_NAME']]
    now = datetime.now(timezone.utc)
    seller = await db.users.find_one({"email": "testdealer@bidvex.com"}, {"_id": 0, "id": 1})
    seller_id = seller["id"] if seller else "seed-dealer"
    lots = []
    for i, (yr, mk, md) in enumerate([(2019, "Ford", "F-150"), (2021, "Toyota", "RAV4"), (2018, "Honda", "Civic")]):
        lots.append({
            "id": str(uuid.uuid4()),
            "lot_number": i + 1,
            "vin": f"1FTEW1EP{i}KFA0000{i}",
            "year": yr, "make": mk, "model": md,
            "title": f"{yr} {mk} {md}",
            "description": f"Seeded {yr} {mk} {md} for iter344 feed verification.",
            "mileage": 50000 + i * 10000,
            "location_city": "Montreal",
            "location_province": "QC",
            "location_postal_code": "H2X 3L7",
            "starting_price": 5000.0 + i * 1000,
            "reserve_price": None,
            "bid_increment": 250.0,
            "media": [{"type": "photo", "url": f"https://bidvex-media.s3.amazonaws.com/seeds/vml-{i}.jpg", "category": "exterior"}],
            "current_bid": 0.0,
            "bid_count": 0,
            "status": "live" if i == 0 else "upcoming",
            "start_time": now if i == 0 else None,
            "end_time": (now + timedelta(days=2)) if i == 0 else None,
        })
    event = {
        "id": "iter344-vml-feed-test",
        "title": "iter344 Dealer Fleet Liquidation",
        "description": "Seeded event for per-lot feed decomposition verification.",
        "seller_id": seller_id,
        "timing_mode": "sequential",
        "start_time": now,
        "lot_duration_seconds": 172800,
        "stagger_offset_seconds": 0,
        "status": "live",
        "current_active_lot_index": 0,
        "lot_sequence": [l["id"] for l in lots],
        "lots": lots,
        "bids": [],
        "created_at": now,
        "updated_at": now,
    }
    await db.vehicle_multi_lot_auctions.delete_many({"id": "iter344-vml-feed-test"})
    await db.vehicle_multi_lot_auctions.insert_one(event)
    print("seeded VML event iter344-vml-feed-test with", len(lots), "lots; lot ids:", [l["id"][:8] for l in lots])

asyncio.run(main())
