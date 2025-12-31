"""
BidVex Boutique Test Drive - Automated Test Setup
Creates controlled test environment for tax logic, bidding, and notifications
"""

import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timedelta
from passlib.context import CryptContext
import uuid
import os
from dotenv import load_dotenv

load_dotenv()

mongo_url = os.environ['MONGO_URL']
db_name = os.environ['DB_NAME']
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Test configuration
TEST_AUCTIONS = [
    {
        "id": "TEST-01",
        "title": "MacBook Pro M2 - 16GB RAM, 512GB SSD",
        "description": "Gently used MacBook Pro, excellent condition. Private seller.",
        "seller_type": "individual",
        "starting_price": 1000.00,
        "current_price": 1000.00,
        "category": "Electronics",
        "images": ["https://via.placeholder.com/400x300?text=MacBook+Pro"],
        "tax_status": "non_registered"
    },
    {
        "id": "TEST-02",
        "title": "Industrial Cordless Drill Set - Professional Grade",
        "description": "Complete drill set with case, batteries, and accessories. Business seller.",
        "seller_type": "business",
        "starting_price": 500.00,
        "current_price": 500.00,
        "category": "Tools",
        "images": ["https://via.placeholder.com/400x300?text=Drill+Set"],
        "tax_status": "registered"
    },
    {
        "id": "TEST-03",
        "title": "Vintage Rolex Submariner - 1980s Classic",
        "description": "Authentic vintage Rolex, serviced and certified. Private collector.",
        "seller_type": "individual",
        "starting_price": 5000.00,
        "current_price": 5000.00,
        "category": "Watches",
        "images": ["https://via.placeholder.com/400x300?text=Rolex+Watch"],
        "tax_status": "non_registered"
    },
    {
        "id": "TEST-04",
        "title": "Premium Office Furniture Set - Desk, Chair, Cabinet",
        "description": "Modern office furniture, like new condition. Business liquidation.",
        "seller_type": "business",
        "starting_price": 200.00,
        "current_price": 200.00,
        "category": "Furniture",
        "images": ["https://via.placeholder.com/400x300?text=Office+Furniture"],
        "tax_status": "registered"
    }
]

TEST_USERS = [
    {
        "id": "test-user-a-pioneer",
        "email": "pioneer@bidvextest.com",
        "full_name": "Test User A (Pioneer)",
        "name": "Pioneer Tester",
        "password": "TestPass123!",
        "phone": "+15145551001",
        "phone_number": "+15145551001",
        "role": "user",
        "subscription_tier": "free",
        "phone_verified": True,
        "email_verified": True,
        "has_payment_method": True,
        "is_tax_registered": False
    },
    {
        "id": "test-user-b-challenger",
        "email": "challenger@bidvextest.com",
        "full_name": "Test User B (Challenger)",
        "name": "Challenger Tester",
        "password": "TestPass123!",
        "phone": "+15145551002",
        "phone_number": "+15145551002",
        "role": "user",
        "subscription_tier": "free",
        "phone_verified": True,
        "email_verified": True,
        "has_payment_method": True,
        "is_tax_registered": False
    },
    {
        "id": "test-seller-individual",
        "email": "individual@bidvextest.com",
        "full_name": "Individual Seller (Private)",
        "name": "Private Seller",
        "password": "TestPass123!",
        "phone": "+15145551003",
        "phone_number": "+15145551003",
        "role": "user",
        "subscription_tier": "free",
        "phone_verified": True,
        "email_verified": True,
        "has_payment_method": True,
        "is_tax_registered": False,
        "account_type": "personal"
    },
    {
        "id": "test-seller-business",
        "email": "business@bidvextest.com",
        "full_name": "Business Seller Inc.",
        "name": "Business Corp",
        "password": "TestPass123!",
        "phone": "+15145551004",
        "phone_number": "+15145551004",
        "role": "user",
        "subscription_tier": "premium",
        "phone_verified": True,
        "email_verified": True,
        "has_payment_method": True,
        "is_tax_registered": True,
        "gst_number": "123456789RT0001",
        "qst_number": "1234567890TQ0001",
        "business_name": "BidVex Test Business Inc.",
        "account_type": "business"
    }
]


async def setup_test_environment():
    """Create complete test environment with users and auctions"""
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("=" * 60)
    print("🧪 BIDVEX BOUTIQUE TEST DRIVE - SETUP")
    print("=" * 60)
    print()
    
    # Step 1: Create test users
    print("📋 Step 1: Creating Test Users")
    print("-" * 60)
    
    for user_data in TEST_USERS:
        # Check if user exists
        existing = await db.users.find_one({"email": user_data["email"]})
        
        if existing:
            print(f"  ⚠️  User already exists: {user_data['email']}")
            continue
        
        # Hash password
        user_doc = {
            **user_data,
            "password": pwd_context.hash(user_data["password"]),
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "preferred_language": "en",
            "language": "en",
            "preferred_currency": "CAD",
            "monster_bids_used": {}
        }
        
        await db.users.insert_one(user_doc)
        print(f"  ✅ Created: {user_data['email']} ({user_data['full_name']})")
    
    print()
    
    # Step 2: Create test auctions
    print("📋 Step 2: Creating Test Auctions")
    print("-" * 60)
    
    auction_end_time = datetime.utcnow() + timedelta(hours=24)
    
    for auction_data in TEST_AUCTIONS:
        # Check if auction exists
        existing = await db.auctions.find_one({"id": auction_data["id"]})
        
        if existing:
            print(f"  ⚠️  Auction already exists: {auction_data['id']}")
            continue
        
        # Determine seller
        if auction_data["seller_type"] == "individual":
            seller = await db.users.find_one({"email": "individual@bidvextest.com"})
        else:
            seller = await db.users.find_one({"email": "business@bidvextest.com"})
        
        if not seller:
            print(f"  ❌ Seller not found for {auction_data['id']}")
            continue
        
        auction_doc = {
            "id": auction_data["id"],
            "title": auction_data["title"],
            "description": auction_data["description"],
            "seller_id": seller["id"],
            "seller_email": seller["email"],
            "seller_name": seller["name"],
            "seller_is_business": seller.get("is_tax_registered", False),
            "starting_price": auction_data["starting_price"],
            "current_price": auction_data["current_price"],
            "current_bid": auction_data["current_price"],
            "starting_bid": auction_data["starting_price"],
            "category": auction_data["category"],
            "images": auction_data["images"],
            "status": "active",
            "auction_type": "single_item",
            "auction_end_date": auction_end_time,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "bid_count": 0,
            "watchers": [],
            "shipping_available": False,
            "location": "Montreal, QC",
            "condition": "Like New",
            "minimum_bid_increment": 10.00,
            "tax_status": auction_data["tax_status"]
        }
        
        await db.auctions.insert_one(auction_doc)
        
        seller_badge = "🏢 Business" if auction_doc["seller_is_business"] else "👤 Individual"
        tax_badge = "💰 Tax on Item" if auction_doc["seller_is_business"] else "🎉 Tax-Free Item"
        
        print(f"  ✅ Created: {auction_data['id']} - {auction_data['title']}")
        print(f"     {seller_badge} | {tax_badge} | Starting: ${auction_data['starting_price']:.2f}")
    
    print()
    
    # Step 3: Generate test summary
    print("=" * 60)
    print("✅ TEST ENVIRONMENT READY")
    print("=" * 60)
    print()
    print("📊 TEST ACCOUNTS:")
    print("-" * 60)
    print("User A (Pioneer):    pioneer@bidvextest.com    | TestPass123!")
    print("User B (Challenger): challenger@bidvextest.com | TestPass123!")
    print("Individual Seller:   individual@bidvextest.com | TestPass123!")
    print("Business Seller:     business@bidvextest.com   | TestPass123!")
    print()
    print("📦 TEST AUCTIONS:")
    print("-" * 60)
    for auction in TEST_AUCTIONS:
        seller_type = "👤 Individual" if auction["seller_type"] == "individual" else "🏢 Business"
        tax_status = "🎉 No Tax on Item" if auction["tax_status"] == "non_registered" else "💰 Tax Applies"
        print(f"{auction['id']}: {auction['title']}")
        print(f"           {seller_type} | {tax_status} | ${auction['starting_price']:.2f}")
    
    print()
    print("🧪 READY FOR TESTING!")
    print("=" * 60)
    
    client.close()


async def cleanup_test_environment():
    """Remove all test data"""
    
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]
    
    print("🧹 Cleaning up test environment...")
    
    # Delete test users
    result = await db.users.delete_many({
        "email": {"$regex": "@bidvextest.com$"}
    })
    print(f"  ✅ Deleted {result.deleted_count} test users")
    
    # Delete test auctions
    result = await db.auctions.delete_many({
        "id": {"$regex": "^TEST-"}
    })
    print(f"  ✅ Deleted {result.deleted_count} test auctions")
    
    # Delete test bids
    result = await db.bids.delete_many({
        "listing_id": {"$regex": "^TEST-"}
    })
    print(f"  ✅ Deleted {result.deleted_count} test bids")
    
    print("✅ Cleanup complete!")
    
    client.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        asyncio.run(cleanup_test_environment())
    else:
        asyncio.run(setup_test_environment())
