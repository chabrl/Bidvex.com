"""iter471 — Seed multi-scenario buyer dashboard data for a screenshot.

Uses `testbuyer@bidvex.com` (id from test_credentials.md) so the UI
already renders after a normal login. Cleanup via `--cleanup`."""
from __future__ import annotations
import argparse, asyncio, os, sys, uuid
from datetime import datetime, timezone
from pathlib import Path
BACKEND = Path("/app/backend")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
from dotenv import load_dotenv  # type: ignore
load_dotenv(BACKEND / ".env")
from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore

BUYER_ID_QUERY = {"email": "testbuyer@bidvex.com"}
PREFIX = "iter471ui-"


def now_iso():
    return datetime.now(timezone.utc).isoformat()


async def seed(db):
    buyer = await db.users.find_one(BUYER_ID_QUERY, {"_id": 0, "id": 1})
    if not buyer:
        print("[iter471ui] testbuyer not found — abort")
        return
    buyer_id = buyer["id"]
    # Ensure buyer is fully verified so dashboard renders
    await db.users.update_one({"id": buyer_id}, {"$set": {
        "phone_verified": True, "phone": "+15145550101",
        "email_verified": True, "id_verified": True,
    }})

    # A. Single-item paid marketplace
    lid_a = f"{PREFIX}mkt-{uuid.uuid4().hex[:8]}"
    await db.listings.insert_one({
        "id": lid_a, "title": "iter471 · Vintage Bicycle",
        "final_price": 250.00, "current_price": 250.00, "status": "sold",
        "winner_user_id": buyer_id, "seller_id": f"{PREFIX}seller-mkt",
        "sold_at": now_iso(), "iter471ui_seed": True,
    })
    _short = lid_a.replace("-", "")[:8].upper()
    await db.receipts.insert_one({
        "id": str(uuid.uuid4()), "type": "buyer_receipt", "user_id": buyer_id,
        "section": "marketplace", "listing_id": lid_a, "lot_number": None,
        "listing_title": "iter471 · Vintage Bicycle",
        "hammer_price": 250.00, "platform_fee": 12.50, "taxes": 32.50,
        "processing_fee": 0.0, "total_charged": 295.00, "net_payout": 237.50,
        "currency": "CAD", "order_number": f"BVX-{_short}",
        "pickup_code": "BVX-IT471UIA", "created_at": now_iso(),
        "iter471ui_seed": True,
    })

    # B. Multi-lot lots auction — buyer wins lots 1, 2, 3
    lid_b = f"{PREFIX}lot-{uuid.uuid4().hex[:8]}"
    await db.multi_item_listings.insert_one({
        "id": lid_b, "title": "iter471 · Estate Sale Batch #47",
        "status": "ended",
        "lots": [
            {"lot_number": 1, "title": "Vintage Radio 1958", "description": "RCA Victor",
             "quantity": 1, "current_price": 45.0, "starting_price": 20.0, "condition": "good"},
            {"lot_number": 2, "title": "Copper Kettle Set", "description": "3-piece",
             "quantity": 3, "current_price": 60.0, "starting_price": 30.0, "condition": "good"},
            {"lot_number": 3, "title": "Antique Toolbox", "description": "Wooden",
             "quantity": 1, "current_price": 85.0, "starting_price": 40.0, "condition": "used"},
        ],
        "seller_id": f"{PREFIX}seller-lots", "iter471ui_seed": True,
    })
    _short_b = lid_b.replace("-", "")[:8].upper()
    for ln, hammer in [(1, 45.0), (2, 60.0), (3, 85.0)]:
        await db.receipts.insert_one({
            "id": str(uuid.uuid4()), "type": "buyer_receipt", "user_id": buyer_id,
            "section": "lots", "listing_id": lid_b, "lot_number": ln,
            "listing_title": f"receipt fallback lot {ln}",
            "hammer_price": hammer, "platform_fee": 2.25, "taxes": hammer * 0.14975,
            "processing_fee": 0.0, "total_charged": round(hammer + 2.25 + hammer * 0.14975, 2),
            "net_payout": hammer - 2.25, "currency": "CAD",
            "order_number": f"BVX-{_short_b}",
            "pickup_code": f"BVX-IT471L{ln}", "created_at": now_iso(),
            "iter471ui_seed": True,
        })

    # C. Vehicle multi-lot — buyer wins lot 1
    lid_c = f"{PREFIX}veh-{uuid.uuid4().hex[:8]}"
    await db.vehicle_listings.insert_one({
        "id": lid_c, "title": "iter471 · Dealer Vehicle Auction March",
        "status": "ended",
        "lots": [
            {"lot_number": 1, "title": "2019 Ford F-150 XLT", "description": "Crew Cab",
             "vin": "1FTEW1E52KFA12345", "quantity": 1},
            {"lot_number": 2, "title": "2020 Chevrolet Silverado", "description": "LT",
             "vin": "3GCUYDED4LG500002", "quantity": 1},
        ],
        "seller_id": f"{PREFIX}seller-veh", "iter471ui_seed": True,
    })
    _short_c = lid_c.replace("-", "")[:8].upper()
    await db.receipts.insert_one({
        "id": str(uuid.uuid4()), "type": "buyer_receipt", "user_id": buyer_id,
        "section": "vehicles", "listing_id": lid_c, "lot_number": 1,
        "listing_title": "veh receipt fallback lot 1",
        "hammer_price": 27500.0, "platform_fee": 275.0, "taxes": 27500 * 0.14975,
        "processing_fee": 0.0, "total_charged": round(27500 + 275 + 27500 * 0.14975, 2),
        "net_payout": 27225.0, "currency": "CAD",
        "order_number": f"BVX-{_short_c}",
        "pickup_code": "BVX-IT471V01", "created_at": now_iso(),
        "iter471ui_seed": True,
    })

    # D. Storage auction — single unit
    lid_d = f"{PREFIX}sto-{uuid.uuid4().hex[:8]}"
    await db.storage_auctions.insert_one({
        "id": lid_d, "title": "iter471 · Storage Unit #A147 · Montreal",
        "status": "ended", "seller_id": f"{PREFIX}seller-sto",
        "iter471ui_seed": True,
    })
    _short_d = lid_d.replace("-", "")[:8].upper()
    await db.receipts.insert_one({
        "id": str(uuid.uuid4()), "type": "buyer_receipt", "user_id": buyer_id,
        "section": "storage", "listing_id": lid_d, "lot_number": None,
        "listing_title": "storage receipt fallback",
        "hammer_price": 385.0, "platform_fee": 19.25, "taxes": 385 * 0.14975,
        "processing_fee": 0.0, "total_charged": round(385 + 19.25 + 385 * 0.14975, 2),
        "net_payout": 365.75, "currency": "CAD",
        "order_number": f"BVX-{_short_d}", "created_at": now_iso(),
        "iter471ui_seed": True,
    })
    print(f"[iter471ui] seeded 6 rows: single ({lid_a}), 3 lots ({lid_b}), 1 vehicle ({lid_c}), 1 storage ({lid_d})")


async def cleanup(db):
    targets = [
        ("receipts", {"iter471ui_seed": True}),
        ("listings", {"iter471ui_seed": True}),
        ("multi_item_listings", {"iter471ui_seed": True}),
        ("vehicle_listings", {"iter471ui_seed": True}),
        ("storage_auctions", {"iter471ui_seed": True}),
        ("won_auctions", {"listing_id": {"$regex": f"^{PREFIX}"}}),
    ]
    removed = {}
    for coll, q in targets:
        r = await db[coll].delete_many(q)
        removed[coll] = r.deleted_count
    print(f"[iter471ui] cleanup: {removed}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], tz_aware=True)
    db = client[os.environ["DB_NAME"]]
    if args.cleanup:
        await cleanup(db)
    else:
        await cleanup(db)
        await seed(db)


if __name__ == "__main__":
    asyncio.run(main())
