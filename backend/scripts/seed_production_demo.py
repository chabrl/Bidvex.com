"""
iter306 — Production Demo Seed Script
======================================
Idempotent — running this twice does NOT create duplicates. Uses email as
the unique key for users; uses a deterministic `seed_demo_id` field on every
listing/auction so re-runs find existing docs and skip insertion.

USAGE:
  Dry run (default — prints what would be created):
    python seed_production_demo.py

  Execute (actually writes to DB):
    python seed_production_demo.py --execute

⚠️ NEVER run on production without the --execute flag confirmation.

What's created:
  • 3 test users (testbuyer, testseller, testdealer) with the credentials
    specified in iter306 spec
  • 2 ended Marketplace listings (one paid, one payment_pending)
  • 1 ended Lots auction with winner
  • 1 ended Storage auction with winner
  • 1 active Vehicle listing (live, accepting bids)
  • 1 upcoming Vehicle listing (scheduled, not yet live)
  • 1 completed Multi-Lot Vehicle Auction with 3 lots
"""
import asyncio
import argparse
import os
import sys
import uuid
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from passlib.context import CryptContext


def _ensure_path():
    here = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.dirname(here)
    if backend_dir not in sys.path:
        sys.path.insert(0, backend_dir)


_ensure_path()
load_dotenv()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


TEST_USERS = [
    {
        "email": "testbuyer@bidvex.com",
        "password": "TestBuyer2026!",
        "first_name": "Test",
        "last_name": "Buyer",
        "name": "Test Buyer",
        "phone": "5145550101",
        "province": "QC",
        "role": "user",
        "preferred_language": "en",
    },
    {
        "email": "testseller@bidvex.com",
        "password": "TestSeller2026!",
        "first_name": "Test",
        "last_name": "Seller",
        "name": "Test Seller",
        "phone": "5145550102",
        "province": "QC",
        "role": "user",
        "trusted_seller": True,
        "preferred_language": "en",
    },
    {
        "email": "testdealer@bidvex.com",
        "password": "TestDealer2026!",
        "first_name": "Test",
        "last_name": "Dealer",
        "name": "Test Dealer",
        "phone": "5145550103",
        "province": "QC",
        "role": "user",
        "is_vehicle_dealer": True,
        "vehicle_dealer_verified": True,
        "seller_type": "dealer",
        "preferred_language": "fr",
    },
]


def _seed_demo_id(label: str) -> str:
    """Deterministic id for idempotent inserts — same label produces same id."""
    return "demo-" + hashlib.sha1(label.encode()).hexdigest()[:24]


async def upsert_user(db, doc: dict, dry_run: bool, log) -> Optional[str]:
    existing = await db.users.find_one({"email": doc["email"]})
    if existing:
        log(f"  ↩  user already exists: {doc['email']} (id={existing['id']})")
        return existing["id"]
    new_id = doc.get("id") or str(uuid.uuid4())
    user_doc = {
        "id": new_id,
        "email": doc["email"].lower(),
        "password_hash": pwd_context.hash(doc["password"]),
        "first_name": doc.get("first_name", ""),
        "last_name": doc.get("last_name", ""),
        "name": doc.get("name") or doc.get("email"),
        "phone": doc.get("phone", ""),
        "province": doc.get("province", "ON"),
        "role": doc.get("role", "user"),
        "preferred_language": doc.get("preferred_language", "en"),
        "trusted_seller": bool(doc.get("trusted_seller")),
        "is_vehicle_dealer": bool(doc.get("is_vehicle_dealer")),
        "vehicle_dealer_verified": bool(doc.get("vehicle_dealer_verified")),
        "seller_type": doc.get("seller_type", "individual"),
        "is_verified": True,
        "email_verified": True,
        "phone_verified": False,
        "created_at": datetime.now(timezone.utc),
        "_seed_demo_v1": True,
    }
    log(f"  + create user: {doc['email']} ({doc['role']})")
    if not dry_run:
        await db.users.insert_one(user_doc)
    return new_id


async def upsert_vehicle_seller_profile(db, dealer_id: str, dry_run: bool, log):
    """iter313 — Ensure testdealer has an approved vehicle_sellers record
    so the /vehicle-auctions/create dealer-gate lets them in."""
    existing = await db.vehicle_sellers.find_one({"user_id": dealer_id})
    if existing:
        if existing.get("verification_status") != "approved":
            log(f"  ↻  upgrading vehicle_sellers to approved for dealer (id={existing.get('id')})")
            if not dry_run:
                await db.vehicle_sellers.update_one(
                    {"user_id": dealer_id},
                    {"$set": {"verification_status": "approved",
                              "approved_at": datetime.now(timezone.utc),
                              "updated_at": datetime.now(timezone.utc)}}
                )
        else:
            log(f"  ↩  vehicle_sellers already approved (id={existing.get('id')})")
        return existing.get("id")
    sid = str(uuid.uuid4())
    doc = {
        "id": sid,
        "user_id": dealer_id,
        "seller_type": "dealer",
        "business_name": "Test Dealer Auto Corp.",
        "business_address": "123 Test Rd, Montreal QC",
        "business_phone": "5145550103",
        "license_number": "OMVIC-TEST-001",
        "license_province": "QC",
        "tax_id": "123456789",
        "description": "Test dealer for E2E (seeded).",
        "verification_status": "approved",
        "approved_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
        "resubmission_count": 0,
        "max_resubmissions": 3,
        "rejection_history": [],
        "_seed_demo_v1": True,
    }
    log(f"  + create vehicle_sellers approved record for dealer (id={sid})")
    if not dry_run:
        await db.vehicle_sellers.insert_one(doc)
    return sid


async def upsert_marketplace_listing(db, label: str, seller_id: str, winner_id: str, payment_status: str, dry_run: bool, log):
    sid = _seed_demo_id(f"mkt-{label}")
    existing = await db.listings.find_one({"id": sid})
    if existing:
        log(f"  ↩  marketplace listing already exists: {label} (id={sid})")
        return sid
    doc = {
        "id": sid,
        "seller_id": seller_id,
        "title": f"Demo Marketplace Item — {label}",
        "title_fr": f"Article de marché démo — {label}",
        "description": "Seeded demo listing for iter306 settlement-flow testing.",
        "category": "electronics",
        "starting_price": 100.0,
        "current_bid": 250.0,
        "winning_bid": 250.0,
        "bid_count": 3,
        "status": "ended",
        "listing_type": "auction",
        "winner_user_id": winner_id,
        "payment_status": payment_status,  # 'paid' or 'pending'
        "ended_at": datetime.now(timezone.utc) - timedelta(days=1),
        "created_at": datetime.now(timezone.utc) - timedelta(days=7),
        "_seed_demo_v1": True,
    }
    log(f"  + create marketplace listing: {label} (payment={payment_status})")
    if not dry_run:
        await db.listings.insert_one(doc)
    return sid


async def upsert_lot_auction(db, label: str, seller_id: str, winner_id: str, dry_run: bool, log):
    sid = _seed_demo_id(f"lots-{label}")
    existing = await db.listings.find_one({"id": sid})
    if existing:
        log(f"  ↩  lots auction already exists: {label}")
        return sid
    doc = {
        "id": sid,
        "seller_id": seller_id,
        "title": f"Demo Lots Auction — {label}",
        "title_fr": f"Vente de lots démo — {label}",
        "description": "Seeded demo lots auction.",
        "category": "lots",
        "starting_price": 50.0,
        "current_bid": 175.0,
        "winning_bid": 175.0,
        "bid_count": 5,
        "status": "ended",
        "listing_type": "lot_auction",
        "winner_user_id": winner_id,
        "payment_status": "paid",
        "ended_at": datetime.now(timezone.utc) - timedelta(hours=12),
        "created_at": datetime.now(timezone.utc) - timedelta(days=5),
        "_seed_demo_v1": True,
    }
    log(f"  + create lots auction: {label}")
    if not dry_run:
        await db.listings.insert_one(doc)
    return sid


async def upsert_storage_auction(db, label: str, seller_id: str, winner_id: str, dry_run: bool, log):
    sid = _seed_demo_id(f"storage-{label}")
    existing = await db.listings.find_one({"id": sid})
    if existing:
        log(f"  ↩  storage auction already exists: {label}")
        return sid
    doc = {
        "id": sid,
        "seller_id": seller_id,
        "title": f"Demo Storage Auction — {label}",
        "description": "Seeded demo storage locker auction.",
        "category": "storage",
        "starting_price": 75.0,
        "current_bid": 320.0,
        "winning_bid": 320.0,
        "bid_count": 4,
        "status": "ended",
        "listing_type": "storage_locker",
        "winner_user_id": winner_id,
        "payment_status": "pending",
        "ended_at": datetime.now(timezone.utc) - timedelta(hours=18),
        "created_at": datetime.now(timezone.utc) - timedelta(days=10),
        "_seed_demo_v1": True,
    }
    log(f"  + create storage auction: {label}")
    if not dry_run:
        await db.listings.insert_one(doc)
    return sid


async def upsert_vehicle_listing(db, label: str, seller_id: str, status: str, dry_run: bool, log):
    sid = _seed_demo_id(f"veh-{label}")
    existing = await db.vehicle_listings.find_one({"id": sid})
    if existing:
        log(f"  ↩  vehicle listing already exists: {label}")
        return sid
    is_upcoming = (status == "upcoming")
    doc = {
        "id": sid,
        "seller_id": seller_id,
        "vin": "1HGBH41JXMN1091" + ("21" if is_upcoming else "86"),
        "year": 2020,
        "make": "Toyota",
        "model": "Camry" if is_upcoming else "RAV4",
        "trim": "XSE",
        "body_type": "sedan" if is_upcoming else "suv",
        "mileage": 50000,
        "engine_size": "2.5L I4",
        "transmission": "automatic",
        "drivetrain": "fwd" if is_upcoming else "awd",
        "fuel_type": "gasoline",
        "title": f"Demo Vehicle {label}",
        "title_fr": f"Véhicule démo {label}",
        "description": "Seeded demo vehicle listing.",
        "starting_price": 8000.0,
        "current_bid": 8000.0,
        "bid_count": 0,
        "bid_increment": 100,
        "status": status,
        "location_city": "Montréal",
        "location_province": "QC",
        "title_status": "clean",
        "condition_rating": "good",
        "media": [],
        "start_time": datetime.now(timezone.utc) + (timedelta(days=2) if is_upcoming else timedelta(days=-1)),
        "created_at": datetime.now(timezone.utc) - timedelta(days=2),
        "_seed_demo_v1": True,
    }
    log(f"  + create vehicle listing: {label} ({status})")
    if not dry_run:
        await db.vehicle_listings.insert_one(doc)
    return sid


async def upsert_multi_lot_event(db, label: str, seller_id: str, winner_id: str, dry_run: bool, log):
    sid = _seed_demo_id(f"ml-{label}")
    existing = await db.vehicle_multi_lot_auctions.find_one({"id": sid})
    if existing:
        log(f"  ↩  multi-lot event already exists: {label}")
        return sid
    lots = []
    for i in range(3):
        lot_id = _seed_demo_id(f"ml-{label}-lot-{i}")
        sold = (i < 2)  # 2 sold, 1 no-sale
        lots.append({
            "id": lot_id,
            "event_id": sid,
            "vin": f"DEMOMLVIN{label}LOT{i}".upper().ljust(17, "X")[:17],
            "year": 2020 - i,
            "make": "Ford",
            "model": ["F-150", "Escape", "Transit"][i],
            "title": f"Multi-lot {label} — lot #{i+1}",
            "title_fr": f"Multi-lots {label} — lot n°{i+1}",
            "starting_price": 5000 + i * 500,
            "current_bid": (8000 + i * 500) if sold else (5000 + i * 500),
            "bid_count": 4 if sold else 0,
            "status": "sold" if sold else "no_sale",
            "winner_user_id": (winner_id if sold else None),
            "location_city": "Montréal",
            "location_province": "QC",
            "ended_at": datetime.now(timezone.utc) - timedelta(hours=2 + i),
            "_seed_demo_v1": True,
        })
    doc = {
        "id": sid,
        "seller_id": seller_id,
        "title": f"Demo Multi-Lot Event {label}",
        "description": "Seeded demo multi-lot vehicle auction event.",
        "timing_mode": "sequential",
        "start_time": datetime.now(timezone.utc) - timedelta(hours=6),
        "lot_duration_seconds": 120,
        "status": "ended",
        "lots": lots,
        "lot_count": len(lots),
        "sold_count": sum(1 for l in lots if l["status"] == "sold"),
        "no_sale_count": sum(1 for l in lots if l["status"] == "no_sale"),
        "created_at": datetime.now(timezone.utc) - timedelta(days=3),
        "_seed_demo_v1": True,
    }
    log(f"  + create multi-lot event: {label} (3 lots, 2 sold)")
    if not dry_run:
        await db.vehicle_multi_lot_auctions.insert_one(doc)
    return sid


async def main():
    parser = argparse.ArgumentParser(description="Seed production demo content")
    parser.add_argument("--execute", action="store_true", help="Actually write to DB. Default is dry-run.")
    parser.add_argument("--mongo-url", default=None, help="Override MONGO_URL")
    parser.add_argument("--db-name", default=None, help="Override DB_NAME")
    args = parser.parse_args()

    mongo_url = args.mongo_url or os.environ.get("MONGO_URL")
    db_name = args.db_name or os.environ.get("DB_NAME")
    if not mongo_url or not db_name:
        print("❌ MONGO_URL and DB_NAME must be set (.env or --mongo-url/--db-name).")
        sys.exit(1)

    dry_run = not args.execute
    mode = "DRY RUN (no writes)" if dry_run else "EXECUTE (writing to DB)"
    print(f"\n🌱 iter306 production demo seed — {mode}")
    print(f"   Target DB: {db_name}\n")
    if not dry_run:
        print("⚠️  --execute flag detected. Writes WILL happen. Press Ctrl+C in 3 sec to abort.")
        await asyncio.sleep(3)

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    log = print
    log("👤 Users")
    user_ids = {}
    for u in TEST_USERS:
        uid = await upsert_user(db, u, dry_run, log)
        user_ids[u["email"]] = uid

    buyer_id = user_ids["testbuyer@bidvex.com"]
    seller_id = user_ids["testseller@bidvex.com"]
    dealer_id = user_ids["testdealer@bidvex.com"]

    log("\n🛒 Marketplace listings (ended)")
    await upsert_marketplace_listing(db, "paid-001", seller_id, buyer_id, "paid", dry_run, log)
    await upsert_marketplace_listing(db, "pending-001", seller_id, buyer_id, "pending", dry_run, log)

    log("\n📦 Lots auction (ended)")
    await upsert_lot_auction(db, "ended-001", seller_id, buyer_id, dry_run, log)

    log("\n🔐 Storage auction (ended)")
    await upsert_storage_auction(db, "ended-001", seller_id, buyer_id, dry_run, log)

    log("\n🚗 Vehicle listings")
    await upsert_vehicle_seller_profile(db, dealer_id, dry_run, log)
    await upsert_vehicle_listing(db, "live-001", dealer_id, "active", dry_run, log)
    await upsert_vehicle_listing(db, "upcoming-001", dealer_id, "upcoming", dry_run, log)

    log("\n🏷️  Multi-Lot Vehicle Auction (completed)")
    await upsert_multi_lot_event(db, "ended-001", dealer_id, buyer_id, dry_run, log)

    print(f"\n✅ Done. Mode: {mode}\n")
    if dry_run:
        print("Re-run with --execute to actually write these records.")


if __name__ == "__main__":
    asyncio.run(main())
