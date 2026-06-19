"""
iter311 — perf-baseline seeder
Seeds synthetic admin listings across all 4 collections so the
`/admin/listings/all-collections` benchmark has realistic data.
Idempotent — only runs when each collection is below a target floor.
"""
import os
import uuid
from datetime import datetime, timezone, timedelta

from pymongo import MongoClient
from dotenv import load_dotenv


load_dotenv("/app/backend/.env")
db = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

ADMIN_ID = "8940074d-da97-43ca-9a0b-c59d39411ed6"
ADMIN_EMAIL = "charbel911@gmail.com"
TAG = "iter311-perf-seed"
now = datetime.now(timezone.utc)


def seed(coll_name: str, count: int, doc_factory):
    existing = db[coll_name].count_documents({"_seed_tag": TAG})
    if existing >= count:
        print(f"  ↻ {coll_name}: {existing} already seeded (target {count}) — skip")
        return 0
    to_add = count - existing
    docs = [doc_factory(i) for i in range(existing, count)]
    db[coll_name].insert_many(docs)
    print(f"  + {coll_name}: inserted {to_add} (total now {count})")
    return to_add


def marketplace_doc(i: int) -> dict:
    return {
        "_seed_tag": TAG,
        "id": f"{TAG}-mp-{i:04d}-{uuid.uuid4().hex[:8]}",
        "title": f"iter311 marketplace synthetic #{i}",
        "description": "synthetic seed",
        "category": "collectibles",
        "condition": "used",
        "starting_price": 100.0 + i,
        "current_bid": 100.0 + i,
        "status": "active" if i % 4 else "ended",
        "seller_id": ADMIN_ID,
        "user_email": ADMIN_EMAIL,
        "city": "Toronto",
        "region": "ON",
        "is_featured": (i % 10 == 0),
        "created_at": (now - timedelta(hours=i)),
        "auction_end_date": (now + timedelta(days=3)),
    }


def vehicle_doc(i: int) -> dict:
    return {
        "_seed_tag": TAG,
        "id": f"{TAG}-veh-{i:04d}-{uuid.uuid4().hex[:8]}",
        "make": "Honda",
        "model": "Civic",
        "year": 2020 + (i % 5),
        "status": "active" if i % 3 else "draft",
        "seller_id": ADMIN_ID,
        "seller_email": ADMIN_EMAIL,
        "city": "Montréal",
        "province": "QC",
        "current_bid": 8000 + i * 100,
        "starting_price": 8000 + i * 100,
        "is_featured": (i % 12 == 0),
        "created_at": (now - timedelta(hours=i * 2)),
        "auction_end_date": (now + timedelta(days=7)),
    }


def vehicle_multi_doc(i: int) -> dict:
    lots = [{"id": f"{TAG}-vm-{i:04d}-lot-{j}", "make": "Ford", "model": f"F-{j}"} for j in range(5)]
    return {
        "_seed_tag": TAG,
        "id": f"{TAG}-vm-{i:04d}-{uuid.uuid4().hex[:8]}",
        "title": f"iter311 multi-lot event #{i}",
        "status": "active" if i % 5 else "draft",
        "seller_id": ADMIN_ID,
        "seller_email": ADMIN_EMAIL,
        "lots": lots,
        "bids": [],
        "is_featured": False,
        "created_at": (now - timedelta(hours=i)),
        "start_time": (now + timedelta(days=1)),
        "end_time":   (now + timedelta(days=10)),
    }


def multi_item_doc(i: int) -> dict:
    lots = [{"id": f"{TAG}-mi-{i:04d}-lot-{j}", "title": f"lot {j}"} for j in range(3)]
    return {
        "_seed_tag": TAG,
        "id": f"{TAG}-mi-{i:04d}-{uuid.uuid4().hex[:8]}",
        "title": f"iter311 multi-item parent #{i}",
        "status": "active" if i % 3 else "ended",
        "seller_id": ADMIN_ID,
        "seller_email": ADMIN_EMAIL,
        "lots": lots,
        "city": "Vancouver",
        "region": "BC",
        "is_featured": (i % 8 == 0),
        "created_at": (now - timedelta(hours=i * 3)),
        "auction_end_date": (now + timedelta(days=5)),
    }


print("iter311 perf-baseline seeding...")
seed("listings",                       250, marketplace_doc)
seed("vehicle_listings",               150, vehicle_doc)
seed("vehicle_multi_lot_auctions",     150, vehicle_multi_doc)
seed("multi_item_listings",            100, multi_item_doc)

print("\nFINAL COUNTS:")
for c in ("listings", "vehicle_listings", "vehicle_multi_lot_auctions", "multi_item_listings"):
    print(f"  {c}: total={db[c].count_documents({})}  seeded={db[c].count_documents({'_seed_tag': TAG})}")
