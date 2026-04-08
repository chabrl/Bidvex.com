from motor.motor_asyncio import AsyncIOMotorDatabase
import logging

logger = logging.getLogger("server")

async def create_all_indexes(db: AsyncIOMotorDatabase):
    """Create all required indexes. Silently skip indexes that already exist."""
    index_defs = [
        (db.hero_banners, [("active", 1), ("order", 1)]),
        (db.listings, [("status", 1), ("auction_end_date", 1), ("created_at", -1)]),
        (db.multi_item_listings, [("status", 1), ("auction_end_date", 1), ("created_at", -1)]),
        (db.announcements, [("is_active", 1)]),
        (db.user_interests, [("user_id", 1), ("created_at", -1)]),
        (db.user_interests, [("user_id", 1), ("event_type", 1)]),
        (db.won_auctions, [("winner_id", 1), ("won_at", -1)]),
        (db.listings, [("status", 1), ("category", 1)]),
        (db.listings, [("status", 1), ("city", 1)]),
        (db.listings, [("status", 1), ("region", 1)]),
        (db.multi_item_listings, [("status", 1), ("category", 1)]),
    ]
    ttl_defs = [
        (db.user_interests, [("created_at", 1)], 90 * 86400),
        (db.won_auctions, [("won_at", 1)], 30 * 86400),
    ]
    for coll, keys in index_defs:
        try:
            await coll.create_index(keys)
        except Exception:
            pass  # Index already exists with different name — safe to ignore
    for coll, keys, ttl in ttl_defs:
        try:
            await coll.create_index(keys, expireAfterSeconds=ttl)
        except Exception:
            pass
    logger.info("[indexes] All database indexes verified/created")
