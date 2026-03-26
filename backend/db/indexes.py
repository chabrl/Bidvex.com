from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger("server")

async def create_all_indexes(db: AsyncIOMotorDatabase):
    try:
        # Fix for the /api/site-config timeout causing the empty site
        await db.hero_banners.create_index([("active", 1), ("order", 1)])
        
        # Performance for Marketplace and Announcements
        await db.listings.create_index([("status", 1), ("end_time", 1)])
        await db.announcements.create_index([("is_active", 1)])
        
        logger.info("[indexes] All database indexes verified/created")
    except Exception as e:
        logger.error(f"[indexes] Failed to create indexes: {e}")
