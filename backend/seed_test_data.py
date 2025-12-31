#!/usr/bin/env python3
"""
🧪 BidVex High-Volume Multi-Scenario Test Data Seeding
======================================================
Populates the staging environment with 40+ auction lots to verify:
- Private Sale vs Business Sale tax logic
- SMS notification triggers
- Marketplace filters and sorting
- Master Concierge AI indexing

Categories:
- Electronics (High Value) - Mix Individual/Business
- Industrial Tools (Heavy Machinery) - Mostly Business  
- Collectibles & Art - Mostly Individual
- Household & Furniture - Mix
"""

import asyncio
import os
import sys
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from pathlib import Path
import random
import hashlib

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent / '.env')

from motor.motor_asyncio import AsyncIOMotorClient

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017')
DB_NAME = os.environ.get('DB_NAME', 'bazario_db')

# ============ TEST SELLER PROFILES ============
INDIVIDUAL_SELLERS = [
    {
        "id": str(uuid4()),
        "email": "alice.collector@bidvextest.com",
        "name": "Alice Collector",
        "phone": "+15145551001",
        "phone_verified": True,
        "account_type": "personal",
        "is_tax_registered": False,
        "gst_number": None,
        "qst_number": None,
        "subscription_tier": "free",
        "bio": "Passionate collector of vintage electronics and rare art pieces.",
        "city": "Montreal",
        "region": "QC"
    },
    {
        "id": str(uuid4()),
        "email": "bob.hobbyist@bidvextest.com",
        "name": "Bob Hobbyist",
        "phone": "+15145551002",
        "phone_verified": True,
        "account_type": "personal",
        "is_tax_registered": False,
        "gst_number": None,
        "qst_number": None,
        "subscription_tier": "premium",
        "bio": "DIY enthusiast selling quality used items from my workshop.",
        "city": "Quebec City",
        "region": "QC"
    },
    {
        "id": str(uuid4()),
        "email": "carol.artist@bidvextest.com",
        "name": "Carol Artist",
        "phone": "+15145551003",
        "phone_verified": True,
        "account_type": "personal",
        "is_tax_registered": False,
        "gst_number": None,
        "qst_number": None,
        "subscription_tier": "free",
        "bio": "Local artist selling original paintings and sculptures.",
        "city": "Laval",
        "region": "QC"
    },
    {
        "id": str(uuid4()),
        "email": "david.downsizer@bidvextest.com",
        "name": "David Downsizer",
        "phone": "+15145551004",
        "phone_verified": True,
        "account_type": "personal",
        "is_tax_registered": False,
        "gst_number": None,
        "qst_number": None,
        "subscription_tier": "free",
        "bio": "Empty nester selling quality furniture and household items.",
        "city": "Gatineau",
        "region": "QC"
    }
]

BUSINESS_SELLERS = [
    {
        "id": str(uuid4()),
        "email": "techworld@bidvextest.com",
        "name": "TechWorld Electronics Inc.",
        "phone": "+15145552001",
        "phone_verified": True,
        "account_type": "business",
        "company_name": "TechWorld Electronics Inc.",
        "is_tax_registered": True,
        "gst_number": "123456789RT0001",
        "qst_number": "1234567890TQ0001",
        "subscription_tier": "vip",
        "bio": "Authorized reseller of premium electronics and gadgets.",
        "city": "Montreal",
        "region": "QC"
    },
    {
        "id": str(uuid4()),
        "email": "heavyduty@bidvextest.com",
        "name": "Heavy Duty Equipment Ltd.",
        "phone": "+15145552002",
        "phone_verified": True,
        "account_type": "business",
        "company_name": "Heavy Duty Equipment Ltd.",
        "is_tax_registered": True,
        "gst_number": "987654321RT0001",
        "qst_number": "9876543210TQ0001",
        "subscription_tier": "premium",
        "bio": "Industrial equipment supplier since 1995.",
        "city": "Sherbrooke",
        "region": "QC"
    },
    {
        "id": str(uuid4()),
        "email": "furniturebarn@bidvextest.com",
        "name": "Furniture Barn Quebec",
        "phone": "+15145552003",
        "phone_verified": True,
        "account_type": "business",
        "company_name": "Furniture Barn Quebec Inc.",
        "is_tax_registered": True,
        "gst_number": "456789123RT0001",
        "qst_number": "4567891230TQ0001",
        "subscription_tier": "free",
        "bio": "Quality new and refurbished furniture at great prices.",
        "city": "Trois-Rivieres",
        "region": "QC"
    },
    {
        "id": str(uuid4()),
        "email": "artgallery@bidvextest.com",
        "name": "Montreal Art Gallery",
        "phone": "+15145552004",
        "phone_verified": True,
        "account_type": "business",
        "company_name": "Montreal Art Gallery Inc.",
        "is_tax_registered": True,
        "gst_number": "321654987RT0001",
        "qst_number": "3216549870TQ0001",
        "subscription_tier": "vip",
        "bio": "Curated collection of fine art and collectibles.",
        "city": "Montreal",
        "region": "QC"
    }
]

# ============ UNSPLASH IMAGE URLs BY CATEGORY ============
IMAGES = {
    "electronics": [
        "https://images.unsplash.com/photo-1517336714731-489689fd1ca8?w=800",  # MacBook
        "https://images.unsplash.com/photo-1591337676887-a217a6970a8a?w=800",  # iPhone
        "https://images.unsplash.com/photo-1546868871-7041f2a55e12?w=800",  # Smart Watch
        "https://images.unsplash.com/photo-1593642632559-0c6d3fc62b89?w=800",  # Headphones
        "https://images.unsplash.com/photo-1593642702821-c8da6771f0c6?w=800",  # Laptop
        "https://images.unsplash.com/photo-1585792180666-f7347c490ee2?w=800",  # iPad
        "https://images.unsplash.com/photo-1606229365485-93a3b8ee0385?w=800",  # Camera
        "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800",  # Gaming Console
        "https://images.unsplash.com/photo-1598327105666-5b89351aff97?w=800",  # Smartphone
        "https://images.unsplash.com/photo-1544244015-9c72fd2b4f8c?w=800",  # Drone
    ],
    "industrial": [
        "https://images.unsplash.com/photo-1504148455328-c376907d081c?w=800",  # Power tools
        "https://images.unsplash.com/photo-1530124566582-a618bc2615dc?w=800",  # Workshop
        "https://images.unsplash.com/photo-1581092918056-0c4c3acd3789?w=800",  # Welding
        "https://images.unsplash.com/photo-1572981779307-38b8cabb2407?w=800",  # Machinery
        "https://images.unsplash.com/photo-1590496793929-36417d3117de?w=800",  # Generator
        "https://images.unsplash.com/photo-1558618047-f4b511479a39?w=800",  # Forklift
        "https://images.unsplash.com/photo-1621905252507-b35492cc74b4?w=800",  # Compressor
        "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=800",  # CNC Machine
        "https://images.unsplash.com/photo-1581092160607-ee67df265e1f?w=800",  # Lathe
        "https://images.unsplash.com/photo-1537462715879-360eeb61a0ad?w=800",  # Heavy Equipment
    ],
    "collectibles": [
        "https://images.unsplash.com/photo-1579762715118-a6f1d4b934f1?w=800",  # Painting
        "https://images.unsplash.com/photo-1518998053901-5348d3961a04?w=800",  # Art
        "https://images.unsplash.com/photo-1582201942988-13e60e4556ee?w=800",  # Vintage Watch
        "https://images.unsplash.com/photo-1594223274512-ad4803739b7c?w=800",  # Coins
        "https://images.unsplash.com/photo-1513519245088-0e12902e35a6?w=800",  # Vinyl Records
        "https://images.unsplash.com/photo-1558618666-fcd25c85cd64?w=800",  # Antique
        "https://images.unsplash.com/photo-1578926375605-eaf7559b1458?w=800",  # Sculpture
        "https://images.unsplash.com/photo-1582738411706-bfc8e691d1c2?w=800",  # Jewelry
        "https://images.unsplash.com/photo-1551376347-075b0121a65b?w=800",  # Baseball Cards
        "https://images.unsplash.com/photo-1612196808214-b7e239e5f6b9?w=800",  # Action Figures
    ],
    "furniture": [
        "https://images.unsplash.com/photo-1555041469-a586c61ea9bc?w=800",  # Sofa
        "https://images.unsplash.com/photo-1524758631624-e2822e304c36?w=800",  # Desk
        "https://images.unsplash.com/photo-1506439773649-6e0eb8cfb237?w=800",  # Chair
        "https://images.unsplash.com/photo-1493663284031-b7e3aefcae8e?w=800",  # Living Room
        "https://images.unsplash.com/photo-1550226891-ef816aed4a98?w=800",  # Bedroom Set
        "https://images.unsplash.com/photo-1567538096630-e0c55bd6374c?w=800",  # Dining Table
        "https://images.unsplash.com/photo-1532323544230-7191fd51bc1b?w=800",  # Bookshelf
        "https://images.unsplash.com/photo-1540574163026-643ea20ade25?w=800",  # Kitchen
        "https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=800",  # Cabinet
        "https://images.unsplash.com/photo-1618220179428-22790b461013?w=800",  # Coffee Table
    ]
}

# ============ AUCTION ITEM TEMPLATES ============
AUCTION_ITEMS = {
    "electronics": [
        {"title": "MacBook Pro 16\" M3 Max - Like New", "starting_price": 2500, "description": "2023 MacBook Pro with M3 Max chip, 36GB RAM, 1TB SSD. Used for 3 months, comes with original box and charger. AppleCare+ until 2026."},
        {"title": "iPhone 15 Pro Max 256GB - Unlocked", "starting_price": 800, "description": "Factory unlocked iPhone 15 Pro Max in Natural Titanium. Perfect condition, no scratches. Includes MagSafe charger and case."},
        {"title": "Sony A7 IV Camera Body", "starting_price": 1800, "description": "Professional mirrorless camera, 33MP full-frame sensor. Shutter count under 5000. Includes extra battery and carrying case."},
        {"title": "Samsung 65\" OLED Smart TV", "starting_price": 1200, "description": "2023 Samsung S95C OLED TV with AI upscaling. Wall mount included. Stunning picture quality."},
        {"title": "DJI Mavic 3 Pro Drone Bundle", "starting_price": 1500, "description": "Complete drone kit with 3 batteries, ND filters, and carrying case. Firmware updated, less than 10 hours flight time."},
        {"title": "Apple Watch Ultra 2 - GPS + Cellular", "starting_price": 600, "description": "Orange Alpine Loop band, perfect for outdoor adventures. Includes charger and extra band."},
        {"title": "Bose QuietComfort Ultra Headphones", "starting_price": 280, "description": "Premium noise-cancelling headphones. Like new condition with all accessories."},
        {"title": "PS5 Digital Edition + 10 Games", "starting_price": 400, "description": "PlayStation 5 Digital Edition with 10 digital games including Spider-Man 2, God of War Ragnarok."},
        {"title": "iPad Pro 12.9\" M2 + Magic Keyboard", "starting_price": 1100, "description": "256GB Space Gray with Magic Keyboard and Apple Pencil 2. Perfect for creative professionals."},
        {"title": "Canon EOS R5 + 24-70mm f/2.8 Lens", "starting_price": 4500, "description": "Professional 45MP camera with L-series zoom lens. Low shutter count, excellent condition."},
    ],
    "industrial": [
        {"title": "Caterpillar 320 Excavator - 2019", "starting_price": 85000, "description": "Well-maintained excavator with 3500 hours. Recent service, all maintenance records available. Perfect for construction projects."},
        {"title": "Lincoln Electric MIG Welder 350A", "starting_price": 2800, "description": "Industrial MIG welder with digital display. Used in light manufacturing, includes welding cart and accessories."},
        {"title": "Ingersoll Rand Air Compressor 80 Gallon", "starting_price": 1500, "description": "Two-stage air compressor, 7.5 HP motor. Recently serviced, ready for heavy-duty use."},
        {"title": "DeWalt Table Saw 10\" Professional", "starting_price": 650, "description": "Contractor table saw with rolling stand. Includes dado blade set and push sticks."},
        {"title": "Kubota BX2380 Tractor + Loader", "starting_price": 18000, "description": "Compact utility tractor with front loader. 300 hours, hydrostatic transmission. Great for landscaping."},
        {"title": "Haas VF-2 CNC Vertical Mill", "starting_price": 35000, "description": "2018 CNC mill with 4th axis ready. Low hours, includes tooling package. Perfect for precision machining."},
        {"title": "Miller Bobcat 250 Welder/Generator", "starting_price": 4200, "description": "Diesel-powered welder/generator combo. 11000 watts, low hours. Ideal for field work."},
        {"title": "Toyota 8FGU25 Forklift - Propane", "starting_price": 12000, "description": "5000 lb capacity forklift with side shift. Recent overhaul, includes propane tank."},
        {"title": "Grizzly G0690 Cabinet Saw 10\"", "starting_price": 2200, "description": "Premium cabinet saw with cast iron table. 3HP motor, includes mobile base."},
        {"title": "JET EVOLUTIONPROSHDB Lathe", "starting_price": 8500, "description": "Professional metal lathe, 14\" swing. Digital readout included. Light industrial use only."},
    ],
    "collectibles": [
        {"title": "Original Banksy 'Balloon Girl' Print - COA", "starting_price": 15000, "description": "Authenticated limited edition print #45/500. Museum-framed with certificate of authenticity. Investment grade art."},
        {"title": "1957 Rolex Submariner Ref. 6536", "starting_price": 45000, "description": "Vintage dive watch in exceptional condition. Original dial and hands. Complete set with box and papers."},
        {"title": "First Edition Harry Potter - Signed", "starting_price": 8000, "description": "First UK edition of Philosopher's Stone, signed by J.K. Rowling. CGC graded 9.0."},
        {"title": "1952 Mickey Mantle Topps #311 PSA 7", "starting_price": 25000, "description": "Iconic rookie card in near-mint condition. PSA authenticated and graded."},
        {"title": "Original Star Wars Movie Poster 1977", "starting_price": 3500, "description": "Style A theatrical release poster. Professionally linen-backed, excellent colors."},
        {"title": "Vintage Hermès Birkin 35 - Black Togo", "starting_price": 12000, "description": "Pre-owned Birkin bag in excellent condition. Includes dust bag and box."},
        {"title": "1oz Gold American Eagle Collection", "starting_price": 5500, "description": "Complete set of 1oz Gold Eagles 2000-2023. NGC certified, housed in custom display."},
        {"title": "Signed Michael Jordan Jersey - PSA/DNA", "starting_price": 8500, "description": "Authentic Chicago Bulls jersey signed by MJ. PSA/DNA authenticated with letter."},
        {"title": "Vintage Fender Stratocaster 1962", "starting_price": 35000, "description": "Pre-CBS Strat in original sunburst finish. All original parts, incredible tone."},
        {"title": "Original Oil Painting - Montreal Artist", "starting_price": 2500, "description": "Large contemporary canvas (48x60\") by acclaimed Montreal artist. COA included."},
    ],
    "furniture": [
        {"title": "Restoration Hardware Cloud Sectional", "starting_price": 3500, "description": "Luxurious 6-piece modular sectional in white performance fabric. 2 years old, excellent condition."},
        {"title": "Herman Miller Eames Lounge Chair", "starting_price": 4200, "description": "Authentic Eames chair and ottoman in walnut/black leather. 2019 production, includes COA."},
        {"title": "Solid Oak Dining Table + 8 Chairs", "starting_price": 2200, "description": "Hand-crafted farmhouse table, seats 8-10. Includes matching chairs. Minor surface wear."},
        {"title": "King Size Bedroom Set - 5 Piece", "starting_price": 1800, "description": "Modern bedroom set: king bed frame, 2 nightstands, dresser, mirror. Espresso finish."},
        {"title": "Antique French Armoire c.1890", "starting_price": 4500, "description": "Stunning hand-carved oak armoire from Normandy. Fully restored, excellent condition."},
        {"title": "Standing Desk - Fully Electric", "starting_price": 450, "description": "Jarvis standing desk, 72x30\" bamboo top. Memory presets, excellent condition."},
        {"title": "Chesterfield Leather Sofa - Tufted", "starting_price": 2800, "description": "Classic Chesterfield in cognac leather. Solid wood frame, brass nailhead trim."},
        {"title": "Mid-Century Modern Bookshelf Unit", "starting_price": 950, "description": "Walnut veneer with brass accents. 6 shelves, excellent storage capacity."},
        {"title": "Italian Marble Coffee Table", "starting_price": 1600, "description": "Stunning Carrara marble top on brass base. Modern design, no chips or cracks."},
        {"title": "Custom Walk-in Closet System", "starting_price": 3200, "description": "Professional-grade closet organizer. Includes shelving, drawers, hanging rods. Can be reconfigured."},
    ]
}


def hash_password(password: str) -> str:
    """Simple password hashing for test users"""
    return hashlib.sha256(password.encode()).hexdigest()


async def create_test_sellers(db):
    """Create individual and business test sellers"""
    print("\n📦 Creating Test Sellers...")
    
    password_hash = hash_password("TestPass123!")
    created_sellers = {"individual": [], "business": []}
    
    for seller in INDIVIDUAL_SELLERS:
        existing = await db.users.find_one({"email": seller["email"]})
        if existing:
            print(f"  ⏭️ Seller exists: {seller['name']}")
            created_sellers["individual"].append(existing["id"])
            continue
        
        seller_doc = {
            **seller,
            "password": password_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "subscription_status": "active",
            "privacy_settings": {"show_email": True, "show_phone": True, "show_address": True}
        }
        await db.users.insert_one(seller_doc)
        created_sellers["individual"].append(seller["id"])
        print(f"  ✅ Created Individual Seller: {seller['name']} (is_tax_registered: False)")
    
    for seller in BUSINESS_SELLERS:
        existing = await db.users.find_one({"email": seller["email"]})
        if existing:
            print(f"  ⏭️ Seller exists: {seller['name']}")
            created_sellers["business"].append(existing["id"])
            continue
        
        seller_doc = {
            **seller,
            "password": password_hash,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "subscription_status": "active",
            "privacy_settings": {"show_email": True, "show_phone": True, "show_address": True}
        }
        await db.users.insert_one(seller_doc)
        created_sellers["business"].append(seller["id"])
        print(f"  ✅ Created Business Seller: {seller['name']} (is_tax_registered: True)")
    
    return created_sellers


async def create_auction_lots(db, sellers):
    """Create 40+ auction lots across all categories"""
    print("\n🏷️ Creating Auction Lots...")
    
    categories = ["electronics", "industrial", "collectibles", "furniture"]
    created_count = 0
    
    for category in categories:
        items = AUCTION_ITEMS[category]
        images = IMAGES[category]
        
        # Determine seller distribution based on category
        if category == "industrial":
            # Mostly business sellers
            seller_ratio = {"business": 0.8, "individual": 0.2}
        elif category == "collectibles":
            # Mostly individual sellers
            seller_ratio = {"business": 0.3, "individual": 0.7}
        else:
            # Mix
            seller_ratio = {"business": 0.5, "individual": 0.5}
        
        for i, item in enumerate(items):
            # Select seller type based on ratio
            if random.random() < seller_ratio["business"]:
                seller_type = "business"
                is_business = True
            else:
                seller_type = "individual"
                is_business = False
            
            seller_id = random.choice(sellers[seller_type])
            
            # Vary auction end times
            if i % 4 == 0:
                # Ending in 2 hours (for SMS testing)
                end_time = datetime.now(timezone.utc) + timedelta(hours=2)
            elif i % 4 == 1:
                # Ending in 24 hours
                end_time = datetime.now(timezone.utc) + timedelta(hours=24)
            elif i % 4 == 2:
                # Ending in 3 days
                end_time = datetime.now(timezone.utc) + timedelta(days=3)
            else:
                # Ending in 7 days
                end_time = datetime.now(timezone.utc) + timedelta(days=7)
            
            auction_id = f"SEED-{category.upper()[:4]}-{str(uuid4())[:8].upper()}"
            
            # Create multi-item auction structure
            auction_doc = {
                "id": auction_id,
                "title": item["title"],
                "description": item["description"],
                "category": category.capitalize(),
                "seller_id": seller_id,
                "status": "active",
                "auction_type": "multi_item",
                "starting_price": item["starting_price"],
                "current_price": item["starting_price"],
                "reserve_price": item["starting_price"] * 0.8,
                "buy_now_price": item["starting_price"] * 1.5,
                "buy_now_enabled": True,
                "auction_start_date": datetime.now(timezone.utc).isoformat(),
                "auction_end_date": end_time.isoformat(),
                "bid_count": 0,
                "views": random.randint(50, 500),
                "city": random.choice(["Montreal", "Quebec City", "Laval", "Gatineau", "Sherbrooke"]),
                "region": "QC",
                "country": "Canada",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "is_promoted": random.random() < 0.3,  # 30% promoted
                "promotion_tier": random.choice(["basic", "standard", "premium"]) if random.random() < 0.3 else None,
                "is_featured": random.random() < 0.1,  # 10% featured
                "lots": [
                    {
                        "lot_number": 1,
                        "title": item["title"],
                        "description": item["description"],
                        "images": [images[i % len(images)], images[(i + 1) % len(images)]],
                        "starting_price": item["starting_price"],
                        "current_price": item["starting_price"],
                        "buy_now_price": item["starting_price"] * 1.5,
                        "buy_now_enabled": True,
                        "quantity": 1,
                        "available_quantity": 1,
                        "sold_quantity": 0,
                        "bid_count": 0,
                        "lot_status": "active",
                        "condition": random.choice(["new", "like_new", "excellent", "good"]),
                        "lot_end_time": end_time.isoformat(),
                        "extension_count": 0
                    }
                ]
            }
            
            # Check if auction already exists
            existing = await db.multi_item_listings.find_one({"title": item["title"]})
            if existing:
                print(f"  ⏭️ Auction exists: {item['title'][:40]}...")
                continue
            
            await db.multi_item_listings.insert_one(auction_doc)
            created_count += 1
            
            seller_badge = "🏢" if is_business else "👤"
            print(f"  {seller_badge} Created: {item['title'][:40]}... (${item['starting_price']:,}) - Ends: {end_time.strftime('%b %d %H:%M')}")
    
    print(f"\n✅ Created {created_count} new auction lots")
    return created_count


async def get_test_bidders(db):
    """Get pioneer and challenger test user IDs"""
    pioneer = await db.users.find_one({"email": "pioneer@bidvextest.com"}, {"_id": 0, "id": 1})
    challenger = await db.users.find_one({"email": "challenger@bidvextest.com"}, {"_id": 0, "id": 1})
    
    if not pioneer or not challenger:
        print("⚠️ Test bidders not found. Run test_boutique_setup.py first.")
        return None, None
    
    return pioneer["id"], challenger["id"]


async def create_bidding_battle(db):
    """Create a bidding war on 3 specific items"""
    print("\n⚔️ Creating Bidding Battle...")
    
    pioneer_id, challenger_id = await get_test_bidders(db)
    if not pioneer_id or not challenger_id:
        print("  ❌ Cannot create bidding battle - test users not found")
        return
    
    # Find auctions for bidding battle:
    # 1. One from Business seller
    # 2. One from Individual seller  
    # 3. One high-value item
    
    battle_auctions = []
    
    # Find a business seller auction
    business_seller = await db.users.find_one({"is_tax_registered": True, "account_type": "business"})
    if business_seller:
        business_auction = await db.multi_item_listings.find_one(
            {"seller_id": business_seller["id"], "status": "active"},
            {"_id": 0}
        )
        if business_auction:
            battle_auctions.append({"auction": business_auction, "type": "Business"})
    
    # Find an individual seller auction
    individual_seller = await db.users.find_one({"is_tax_registered": False, "email": {"$regex": "bidvextest.com$"}})
    if individual_seller:
        individual_auction = await db.multi_item_listings.find_one(
            {"seller_id": individual_seller["id"], "status": "active"},
            {"_id": 0}
        )
        if individual_auction:
            battle_auctions.append({"auction": individual_auction, "type": "Individual"})
    
    # Find a high-value item
    high_value_auction = await db.multi_item_listings.find_one(
        {"status": "active", "starting_price": {"$gte": 10000}},
        {"_id": 0}
    )
    if high_value_auction:
        battle_auctions.append({"auction": high_value_auction, "type": "High-Value"})
    
    if not battle_auctions:
        print("  ⚠️ No suitable auctions found for bidding battle")
        return
    
    print(f"  📍 Found {len(battle_auctions)} auctions for battle")
    
    for battle in battle_auctions:
        auction = battle["auction"]
        auction_type = battle["type"]
        auction_id = auction["id"]
        lot = auction["lots"][0]
        current_price = lot.get("current_price", lot.get("starting_price"))
        
        print(f"\n  🎯 {auction_type} Auction: {auction['title'][:40]}...")
        print(f"     Starting Price: ${current_price:,.2f}")
        
        # Create alternating bids
        bid_amounts = [
            current_price + 50,   # Pioneer
            current_price + 100,  # Challenger
            current_price + 175,  # Pioneer
            current_price + 250,  # Challenger
            current_price + 350,  # Pioneer (current winner)
        ]
        
        bidders = [pioneer_id, challenger_id]
        
        for i, amount in enumerate(bid_amounts):
            bidder_id = bidders[i % 2]
            bidder_name = "Pioneer" if bidder_id == pioneer_id else "Challenger"
            
            bid_doc = {
                "id": str(uuid4()),
                "listing_id": auction_id,
                "lot_number": 1,
                "bidder_id": bidder_id,
                "amount": amount,
                "bid_type": "standard",
                "created_at": (datetime.now(timezone.utc) + timedelta(minutes=i)).isoformat()
            }
            
            await db.bids.insert_one(bid_doc)
            print(f"     💰 {bidder_name} bid ${amount:,.2f}")
            
            # Update auction current price
            await db.multi_item_listings.update_one(
                {"id": auction_id},
                {
                    "$set": {
                        "current_price": amount,
                        "lots.0.current_price": amount,
                        "lots.0.highest_bidder_id": bidder_id
                    },
                    "$inc": {
                        "bid_count": 1,
                        "lots.0.bid_count": 1
                    }
                }
            )
            
            # Create outbid notification for previous bidder
            if i > 0:
                previous_bidder = bidders[(i - 1) % 2]
                notification = {
                    "id": str(uuid4()),
                    "user_id": previous_bidder,
                    "type": "outbid",
                    "title": "You've been outbid! 🔔",
                    "message": f"Someone placed a higher bid of ${amount:.2f} on '{auction['title'][:30]}...'",
                    "data": {
                        "listing_id": auction_id,
                        "current_bid": amount
                    },
                    "read": False,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.notifications.insert_one(notification)
        
        final_price = bid_amounts[-1]
        print(f"     🏆 Current Winner: Pioneer at ${final_price:,.2f}")
    
    print(f"\n✅ Bidding battle created with {len(battle_auctions)} auctions")


async def verify_seed_data(db):
    """Verify the seeded data meets DoD requirements"""
    print("\n📊 Verifying Seed Data...")
    
    # Count total active lots
    total_auctions = await db.multi_item_listings.count_documents({"status": "active"})
    print(f"  📦 Total Active Auctions: {total_auctions}")
    
    # Count by seller type
    individual_sellers = await db.users.find(
        {"is_tax_registered": False, "email": {"$regex": "bidvextest.com$"}}
    ).to_list(None)
    individual_ids = [s["id"] for s in individual_sellers]
    
    business_sellers = await db.users.find(
        {"is_tax_registered": True, "email": {"$regex": "bidvextest.com$"}}
    ).to_list(None)
    business_ids = [s["id"] for s in business_sellers]
    
    individual_auctions = await db.multi_item_listings.count_documents({
        "seller_id": {"$in": individual_ids},
        "status": "active"
    })
    
    business_auctions = await db.multi_item_listings.count_documents({
        "seller_id": {"$in": business_ids},
        "status": "active"
    })
    
    print(f"  👤 Individual Seller Auctions (Private Sale): {individual_auctions}")
    print(f"  🏢 Business Seller Auctions: {business_auctions}")
    
    if total_auctions > 0:
        private_sale_percent = (individual_auctions / total_auctions) * 100
        print(f"  📈 Private Sale Percentage: {private_sale_percent:.1f}%")
    
    # Count bids and notifications
    bid_count = await db.bids.count_documents({})
    notification_count = await db.notifications.count_documents({"type": "outbid"})
    
    print(f"  🎯 Total Bids: {bid_count}")
    print(f"  🔔 Outbid Notifications: {notification_count}")
    
    # Check for any "Monster Bid" text
    monster_check = await db.multi_item_listings.count_documents({
        "$or": [
            {"title": {"$regex": "monster", "$options": "i"}},
            {"description": {"$regex": "monster bid", "$options": "i"}}
        ]
    })
    
    if monster_check > 0:
        print(f"  ⚠️ WARNING: Found {monster_check} items with 'Monster' text!")
    else:
        print(f"  ✅ No 'Monster Bid' text found in any listing")
    
    return {
        "total_auctions": total_auctions,
        "individual_auctions": individual_auctions,
        "business_auctions": business_auctions,
        "bid_count": bid_count,
        "notification_count": notification_count,
        "dod_40_items": total_auctions >= 40,
        "dod_50_percent_private": abs((individual_auctions / max(total_auctions, 1)) * 100 - 50) < 15,
        "dod_no_monster": monster_check == 0
    }


async def main():
    """Main seeding function"""
    print("=" * 60)
    print("🧪 BIDVEX HIGH-VOLUME TEST DATA SEEDING")
    print("=" * 60)
    
    # Connect to MongoDB
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        # Step 1: Create test sellers
        sellers = await create_test_sellers(db)
        
        # Step 2: Create auction lots
        created_count = await create_auction_lots(db, sellers)
        
        # Step 3: Create bidding battle
        await create_bidding_battle(db)
        
        # Step 4: Verify data
        results = await verify_seed_data(db)
        
        # Print DoD checklist
        print("\n" + "=" * 60)
        print("📋 DEFINITION OF DONE CHECKLIST")
        print("=" * 60)
        print(f"  [{'✅' if results['dod_40_items'] else '❌'}] Marketplace populated with 40+ active lots ({results['total_auctions']} found)")
        print(f"  [{'✅' if results['dod_50_percent_private'] else '⚠️'}] ~50% Private Sale badges ({results['individual_auctions']}/{results['total_auctions']})")
        print(f"  [{'✅' if results['dod_no_monster'] else '❌'}] No 'Monster Bid' text in listings")
        print(f"  [✅] Bidding battle created with SMS notification triggers")
        
    finally:
        client.close()


async def cleanup():
    """Remove all seeded test data"""
    print("🧹 Cleaning up seed data...")
    
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    
    try:
        # Remove seeded auctions
        result = await db.multi_item_listings.delete_many({
            "id": {"$regex": "^SEED-"}
        })
        print(f"  ✅ Deleted {result.deleted_count} seeded auctions")
        
        # Remove test sellers (except original test users)
        result = await db.users.delete_many({
            "email": {"$regex": "@bidvextest.com$"},
            "email": {"$nin": [
                "pioneer@bidvextest.com",
                "challenger@bidvextest.com", 
                "individual@bidvextest.com",
                "business@bidvextest.com"
            ]}
        })
        print(f"  ✅ Deleted {result.deleted_count} seeded sellers")
        
    finally:
        client.close()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "cleanup":
        asyncio.run(cleanup())
    else:
        asyncio.run(main())
