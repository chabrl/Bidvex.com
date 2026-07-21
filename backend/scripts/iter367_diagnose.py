"""
iter367 — Dashboard Analytics Diagnostic
Reveals the DB state that's causing the "OUTBID $0.00" bug on Buyer/Seller/Admin dashboards.
"""
import asyncio
import os
import sys
sys.path.insert(0, '/app/backend')
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
load_dotenv('/app/backend/.env')

MONGO_URL = os.environ['MONGO_URL']
DB_NAME = os.environ['DB_NAME']


async def diagnose():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    print("=" * 80)
    print("BidVex Dashboard Analytics — Live DB Diagnostic")
    print("=" * 80)

    # 1) Status distribution across ALL auction collections
    print("\n[1] LISTINGS COLLECTION — status distribution")
    pipe = [{"$group": {"_id": "$status", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    async for row in db.listings.aggregate(pipe):
        print(f"  status={row['_id']!r:30} count={row['count']}")

    print("\n[2] LISTINGS COLLECTION — payment_status distribution (ended/sold/completed)")
    pipe = [
        {"$match": {"status": {"$in": ["ended", "sold", "completed", "payment_collected"]}}},
        {"$group": {"_id": "$payment_status", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
    ]
    async for row in db.listings.aggregate(pipe):
        print(f"  payment_status={row['_id']!r:30} count={row['count']}")

    print("\n[3] LISTINGS — winner_user_id vs winner_id vs highest_bidder_id (which one is populated?)")
    total = await db.listings.count_documents({"status": {"$in": ["sold", "ended", "completed"]}})
    with_winner_user_id = await db.listings.count_documents({"status": {"$in": ["sold", "ended", "completed"]}, "winner_user_id": {"$exists": True, "$ne": None}})
    with_winner_id = await db.listings.count_documents({"status": {"$in": ["sold", "ended", "completed"]}, "winner_id": {"$exists": True, "$ne": None}})
    with_hb_id = await db.listings.count_documents({"status": {"$in": ["sold", "ended", "completed"]}, "highest_bidder_id": {"$exists": True, "$ne": None}})
    print(f"  Total ended/sold/completed: {total}")
    print(f"  With winner_user_id:        {with_winner_user_id}")
    print(f"  With winner_id:             {with_winner_id}")
    print(f"  With highest_bidder_id:     {with_hb_id}")

    print("\n[4] LISTINGS — final_price vs current_price vs hammer_price on ended items")
    with_final = await db.listings.count_documents({"status": {"$in": ["sold", "ended", "completed"]}, "final_price": {"$exists": True, "$ne": None, "$ne": 0}})
    with_current = await db.listings.count_documents({"status": {"$in": ["sold", "ended", "completed"]}, "current_price": {"$exists": True, "$ne": None, "$ne": 0}})
    with_hammer = await db.listings.count_documents({"status": {"$in": ["sold", "ended", "completed"]}, "hammer_price": {"$exists": True, "$ne": None, "$ne": 0}})
    print(f"  With final_price > 0:       {with_final}")
    print(f"  With current_price > 0:     {with_current}")
    print(f"  With hammer_price > 0:      {with_hammer}")

    print("\n[5] Sample 5 ended/sold listings (verbatim keys)")
    docs = await db.listings.find({"status": {"$in": ["sold", "ended", "completed"]}}, {"_id": 0}).sort("ended_at", -1).limit(5).to_list(5)
    for d in docs:
        keys_of_interest = {k: d.get(k) for k in [
            "id", "title", "status", "payment_status",
            "winner_user_id", "winner_id", "highest_bidder_id",
            "final_price", "current_price", "hammer_price",
            "seller_id", "sold_at", "ended_at", "payment_collected_at",
            "payment_link_url", "receipt_id"
        ] if k in d}
        print(f"  {keys_of_interest}")

    print("\n[6] RECEIPTS COLLECTION — count by type")
    pipe = [{"$group": {"_id": "$type", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    async for row in db.receipts.aggregate(pipe):
        print(f"  type={row['_id']!r:30} count={row['count']}")

    print("\n[7] Sample 5 buyer receipts")
    docs = await db.receipts.find({"type": "buyer_receipt"}, {"_id": 0}).sort("created_at", -1).limit(5).to_list(5)
    for d in docs:
        keys = {k: d.get(k) for k in ["id", "user_id", "listing_id", "amount", "total_paid_cad", "hammer_price", "final_price", "created_at"] if k in d}
        print(f"  {keys}")

    print("\n[8] BIDS COLLECTION — count and sample")
    total_bids = await db.bids.count_documents({})
    print(f"  Total bids: {total_bids}")
    docs = await db.bids.find({}, {"_id": 0}).sort("created_at", -1).limit(3).to_list(3)
    for d in docs:
        keys = {k: d.get(k) for k in ["id", "listing_id", "bidder_id", "amount", "status", "created_at"] if k in d}
        print(f"  {keys}")

    print("\n[9] ESCROW COLLECTION — check what buyers see")
    total_escrow = await db.escrow_holds.count_documents({})
    print(f"  Total escrow_holds: {total_escrow}")
    if total_escrow > 0:
        docs = await db.escrow_holds.find({}, {"_id": 0}).limit(3).to_list(3)
        for d in docs:
            keys = {k: d.get(k) for k in ["id", "user_id", "buyer_id", "listing_id", "amount", "status", "released_at"] if k in d}
            print(f"  {keys}")

    print("\n[10] SETTLEMENTS COLLECTION")
    for coll_name in ["settlements", "transactions", "orders", "purchase_orders"]:
        try:
            cnt = await db[coll_name].count_documents({})
            print(f"  {coll_name}: {cnt}")
        except Exception as e:
            print(f"  {coll_name}: ERROR {e}")

    print("\n[11] Test buyer (charbel911@gmail.com) — won listings and dashboard shape")
    admin = await db.users.find_one({"email": "charbel911@gmail.com"}, {"_id": 0, "id": 1, "email": 1, "role": 1})
    print(f"  Admin doc: {admin}")
    if admin:
        won = await db.listings.count_documents({
            "status": {"$in": ["sold", "ended", "completed"]},
            "$or": [
                {"winner_user_id": admin["id"]},
                {"winner_id": admin["id"]},
                {"highest_bidder_id": admin["id"]},
            ],
        })
        print(f"  Listings won by admin: {won}")
        bids_by_admin = await db.bids.count_documents({"bidder_id": admin["id"]})
        print(f"  Bids placed by admin: {bids_by_admin}")

    print("\n[12] LOTS COLLECTION — multi-lot auction items")
    for coll in ["lots", "vehicle_multi_lot_auctions", "multi_item_listings"]:
        try:
            cnt = await db[coll].count_documents({})
            sample = await db[coll].find_one({}, {"_id": 0})
            print(f"  {coll}: {cnt} docs")
            if sample:
                sample_keys = list(sample.keys())[:20]
                print(f"    sample keys: {sample_keys}")
        except Exception as e:
            print(f"  {coll}: ERROR {e}")

    print("\n" + "=" * 80)
    client.close()


if __name__ == "__main__":
    asyncio.run(diagnose())
