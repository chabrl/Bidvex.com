#!/usr/bin/env python3
"""
Seed Homepage Banner - "Discover. Bid. Win." 
Adds the main hero banner to the database for admin editing
"""
import asyncio
import os
import sys
from datetime import datetime
from uuid import uuid4
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'backend'))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / 'backend' / '.env')

from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'bazario_db')

async def seed_homepage_banner():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    print("🎨 Seeding homepage banner...")
    
    # Check if banners already exist
    existing_banners = await db.banners.count_documents({})
    
    if existing_banners > 0:
        print(f"⚠️  Found {existing_banners} existing banner(s).")
        print("🔄 Updating main banner...")
    
    # Main "Discover. Bid. Win." Banner
    main_banner = {
        "id": "discover-bid-win",
        "title": "Discover. Bid. Win.",
        "subtitle": "Experience the thrill of live auctions. Join thousands of bidders competing for unique items at unbeatable prices.",
        "description": "Experience the thrill of live auctions. Join thousands of bidders competing for unique items at unbeatable prices.",
        "image_url": "https://images.unsplash.com/photo-1556742049-0cfed4f6a45d?w=1200&h=600&fit=crop&q=80",
        "cta_text": "Browse Auctions",
        "cta_url": "/marketplace",
        "cta2_text": "How It Works",
        "cta2_url": "/how-it-works",
        "is_active": True,
        "priority": 100,
        "start_date": None,
        "end_date": None,
        "gradient": "from-blue-600 via-blue-500 to-cyan-500",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    # Upsert main banner
    await db.banners.update_one(
        {"id": "discover-bid-win"},
        {"$set": main_banner},
        upsert=True
    )
    print("✅ Main banner 'Discover. Bid. Win.' created/updated!")
    
    # Additional banners
    additional_banners = [
        {
            "id": "start-bidding-today",
            "title": "Start Bidding Today",
            "subtitle": "Discover rare finds and exclusive deals in our trusted marketplace",
            "description": "Discover rare finds and exclusive deals in our trusted marketplace",
            "image_url": "https://images.unsplash.com/photo-1607083206869-4c7672e72a8a?w=1200&h=600&fit=crop&q=80",
            "cta_text": "Browse Auctions",
            "cta_url": "/marketplace",
            "cta2_text": "How It Works",
            "cta2_url": "/how-it-works",
            "is_active": True,
            "priority": 90,
            "start_date": None,
            "end_date": None,
            "gradient": "from-blue-600 via-blue-500 to-cyan-500",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        },
        {
            "id": "sell-your-items",
            "title": "Sell Your Items",
            "subtitle": "Reach thousands of buyers and get the best price for your items",
            "description": "Reach thousands of buyers and get the best price for your items",
            "image_url": "https://images.unsplash.com/photo-1556742111-a301076d9d18?w=1200&h=600&fit=crop&q=80",
            "cta_text": "Create Listing",
            "cta_url": "/create-listing",
            "cta2_text": "Learn More",
            "cta2_url": "/how-it-works",
            "is_active": True,
            "priority": 80,
            "start_date": None,
            "end_date": None,
            "gradient": "from-purple-600 via-purple-500 to-pink-500",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }
    ]
    
    for banner in additional_banners:
        await db.banners.update_one(
            {"id": banner["id"]},
            {"$set": banner},
            upsert=True
        )
        print(f"✅ Banner '{banner['title']}' created/updated!")
    
    print("\n📊 Summary:")
    total_banners = await db.banners.count_documents({})
    active_banners = await db.banners.count_documents({"is_active": True})
    print(f"   - Total banners: {total_banners}")
    print(f"   - Active banners: {active_banners}")
    print("   - Admin Panel: Edit banners in Settings → Banners")
    print("\n🎉 Homepage banners ready!")
    
    client.close()

if __name__ == "__main__":
    asyncio.run(seed_homepage_banner())
