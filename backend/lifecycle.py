"""
BidVex — Application Lifecycle Events (startup / shutdown)
Extracted from server.py (Phase 4 refactor).
All functions are registered as FastAPI on_event handlers by server.py.
"""

import asyncio
import logging
import uuid
import httpx

logger = logging.getLogger(__name__)


async def check_redis_connection():
    """Startup: ping Redis and log CRITICAL if unreachable."""
    from services.api_cache import startup_redis_check
    result = await startup_redis_check()
    logger.info(f"Redis startup result: {result}")


async def log_db_status(db):
    """Log DB connectivity and document counts (non-blocking)."""
    async def _check():
        try:
            count = await db.categories.count_documents({})
            logger.info(f"DB connected — categories found: {count}")
            users = await db.users.count_documents({})
            logger.info(f"DB connected — users found: {users}")
        except Exception as e:
            logger.warning(f"DB status check failed (non-fatal): {e}")
    asyncio.ensure_future(_check())


async def prewarm_caches(db):
    """Pre-warm frequently-accessed data so first user never waits."""
    async def _warm():
        try:
            from services.subscription_pricing import get_pricing_service
            ps = get_pricing_service(db)
            await ps.get_all_plans()
            logger.info("[prewarm] Subscription plans cached")
        except Exception as e:
            logger.warning(f"[prewarm] subscription plans: {e}")
        try:
            cats = await db.categories.find({}, {"_id": 0}).to_list(100)
            logger.info(f"[prewarm] {len(cats)} categories loaded")
        except Exception as e:
            logger.warning(f"[prewarm] categories: {e}")
        try:
            count = await db.listings.count_documents({"status": "active"})
            logger.info(f"[prewarm] {count} active listings counted")
        except Exception as e:
            logger.warning(f"[prewarm] listing count: {e}")
        try:
            await asyncio.sleep(2)
            async with httpx.AsyncClient(base_url="http://127.0.0.1:8001", timeout=15) as c:
                r = await c.get("/api/marketplace/items?limit=1")
                logger.info(f"[prewarm] Marketplace items -> {r.status_code} ({r.elapsed.total_seconds():.2f}s)")
                r2 = await c.get("/api/multi-item-listings?limit=1")
                logger.info(f"[prewarm] Multi-item listings -> {r2.status_code} ({r2.elapsed.total_seconds():.2f}s)")
        except Exception as e:
            logger.warning(f"[prewarm] marketplace: {e}")
    asyncio.ensure_future(_warm())


async def init_cloud_storage():
    """Initialise the S3/R2 client (non-blocking)."""
    async def _init():
        try:
            from services.cloud_storage import _get_s3
            _get_s3()
        except Exception as e:
            logger.error(f"Cloud storage init failed (non-fatal): {e}")
    asyncio.ensure_future(_init())


async def seed_categories(db):
    """Insert default categories if the collection is empty."""
    async def _seed():
        try:
            if await db.categories.count_documents({}) == 0:
                categories = [
                    {"id": str(uuid.uuid4()), "name_en": "Electronics", "name_fr": "Electronique", "icon": "laptop"},
                    {"id": str(uuid.uuid4()), "name_en": "Fashion", "name_fr": "Mode", "icon": "shirt"},
                    {"id": str(uuid.uuid4()), "name_en": "Home & Garden", "name_fr": "Maison & Jardin", "icon": "home"},
                    {"id": str(uuid.uuid4()), "name_en": "Sports", "name_fr": "Sports", "icon": "dumbbell"},
                    {"id": str(uuid.uuid4()), "name_en": "Vehicles", "name_fr": "Vehicules", "icon": "car"},
                    {"id": str(uuid.uuid4()), "name_en": "Art & Collectibles", "name_fr": "Art & Objets de collection", "icon": "palette"},
                    {"id": str(uuid.uuid4()), "name_en": "Books & Media", "name_fr": "Livres & Medias", "icon": "book"},
                    {"id": str(uuid.uuid4()), "name_en": "Toys & Games", "name_fr": "Jouets & Jeux", "icon": "gamepad-2"},
                ]
                await db.categories.insert_many(categories)
                logger.info("Categories seeded")
        except Exception as e:
            logger.error(f"Startup error: {e}")
    asyncio.ensure_future(_seed())


async def create_database_indexes(db):
    """Create MongoDB indexes for performance (non-blocking)."""
    async def _create():
        try:
            from pymongo import ASCENDING
            from db.indexes import create_all_indexes
            indexes = [
                ("bids", [("listing_id", ASCENDING)], "idx_bids_listing_id", False),
                ("lot_bids", [("listing_id", ASCENDING), ("lot_number", ASCENDING)], "idx_lot_bids_listing_lot", False),
                ("auto_bids", [("user_id", ASCENDING), ("listing_id", ASCENDING), ("is_active", ASCENDING)], "idx_auto_bids_user_listing", False),
                ("invoices", [("user_id", ASCENDING)], "idx_invoices_user_id", False),
                ("subscription_invoices", [("user_id", ASCENDING)], "idx_sub_invoices_user_id", False),
                ("listings", [("status", ASCENDING), ("created_at", ASCENDING)], "idx_listings_status_created", False),
                ("listings", [("status", ASCENDING), ("category", ASCENDING)], "idx_listings_status_category", False),
                ("listings", [("status", ASCENDING), ("auction_end_date", ASCENDING)], "idx_listings_status_enddate", False),
                ("listings", [("seller_id", ASCENDING), ("status", ASCENDING)], "idx_listings_seller_status", False),
                ("listings", [("id", ASCENDING)], "idx_listings_id_unique", True),
                ("users", [("email", ASCENDING)], "idx_users_email_unique", True),
                ("users", [("role", ASCENDING)], "idx_users_role", False),
                ("users", [("id", ASCENDING)], "idx_users_id_unique", True),
                ("transactions", [("status", ASCENDING), ("created_at", ASCENDING)], "idx_transactions_status_created", False),
                ("transactions", [("buyer_id", ASCENDING)], "idx_transactions_buyer", False),
                ("transactions", [("seller_id", ASCENDING)], "idx_transactions_seller", False),
                ("notifications", [("user_id", ASCENDING), ("is_read", ASCENDING), ("created_at", ASCENDING)], "idx_notifications_user_read_date", False),
                ("messages", [("conversation_id", ASCENDING), ("created_at", ASCENDING)], "idx_messages_conversation_date", False),
                ("multi_item_listings", [("status", ASCENDING), ("created_at", ASCENDING)], "idx_multi_listings_status_created", False),
                ("multi_item_listings", [("id", ASCENDING)], "idx_multi_listings_id_unique", True),
                # Escrow system indexes
                ("escrow_transactions", [("auction_id", ASCENDING)], "idx_escrow_auction_unique", True),
                ("escrow_transactions", [("pickup_code", ASCENDING)], "idx_escrow_pickup_code", False),
                ("escrow_transactions", [("escrow_status", ASCENDING)], "idx_escrow_status", False),
                ("escrow_transactions", [("auto_release_scheduled_at", ASCENDING)], "idx_escrow_auto_release", False),
                ("escrow_transactions", [("buyer_id", ASCENDING)], "idx_escrow_buyer", False),
                ("escrow_transactions", [("seller_id", ASCENDING)], "idx_escrow_seller", False),
            ]
            for coll, keys, name, unique in indexes:
                await db[coll].create_index(keys, background=True, unique=unique, name=name)
            logger.info("Database indexes created")
            await create_all_indexes(db)
        except Exception as e:
            logger.warning(f"Index creation note (non-fatal): {e}")
    asyncio.ensure_future(_create())
