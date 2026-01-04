"""
Fix lot_end_time for all existing multi-item listings.
This script updates lot_end_time to be based on auction_end_date instead of start date.
"""
import asyncio
from datetime import datetime, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
import os

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "bidvex")

async def fix_lot_end_times():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    # Get all multi-item listings
    cursor = db.multi_item_listings.find({})
    listings = await cursor.to_list(length=1000)
    
    fixed_count = 0
    
    for listing in listings:
        auction_end_date = listing.get("auction_end_date")
        
        if not auction_end_date:
            print(f"Skipping {listing.get('id')} - no auction_end_date")
            continue
        
        # Convert to datetime if string
        if isinstance(auction_end_date, str):
            auction_end_date = datetime.fromisoformat(auction_end_date.replace('Z', '+00:00'))
        
        # Update each lot's end time
        lots = listing.get("lots", [])
        updated_lots = []
        
        for idx, lot in enumerate(lots):
            # Calculate new lot_end_time based on auction_end_date
            new_lot_end_time = auction_end_date + timedelta(minutes=idx)
            lot["lot_end_time"] = new_lot_end_time.isoformat()
            updated_lots.append(lot)
        
        # Update the listing in database
        await db.multi_item_listings.update_one(
            {"id": listing["id"]},
            {"$set": {"lots": updated_lots}}
        )
        
        fixed_count += 1
        print(f"Fixed {listing.get('id')}: {len(lots)} lots updated to end at {auction_end_date}")
    
    print(f"\n✅ Fixed {fixed_count} listings")
    client.close()

if __name__ == "__main__":
    asyncio.run(fix_lot_end_times())
