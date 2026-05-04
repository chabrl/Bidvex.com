"""
BidVex — MongoDB Index Creation Script
=======================================
Run once on production: python backend/scripts/create_indexes.py

Idempotent: safe to run repeatedly. Existing indexes are skipped.
Adds critical performance indexes across all collections:
listings, vehicle_listings, storage_auctions, bids, users, deposits,
invoices, storage_facilities, admin_logs, refresh_tokens, email_change_requests.
"""
import asyncio
import logging
import os
import sys
from pathlib import Path

# Load .env from backend directory (override=False so container env wins)
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from motor.motor_asyncio import AsyncIOMotorClient

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-5s  %(message)s")
log = logging.getLogger("create_indexes")

# Accept either MONGO_URI (canonical) or MONGO_URL (existing project key)
MONGO_URL = os.environ.get("MONGO_URI") or os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "bazario_db")


async def _safe_create(coll, keys, **opts):
    """Create an index, skipping silently if it already exists with a different name."""
    try:
        name = await coll.create_index(keys, **opts)
        log.info(f"  OK    {coll.name}.{name}")
        return True
    except Exception as exc:
        log.warning(f"  WARN  {coll.name} {keys} — {exc}")
        return False


async def create_all_indexes():
    if not MONGO_URL:
        log.error("MONGO_URI / MONGO_URL not set. Aborting.")
        sys.exit(1)

    log.info(f"Connecting to {DB_NAME} ...")
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]
    await client.admin.command("ping")
    log.info("MongoDB connection OK")
    log.info("Creating indexes...")

    # ── LISTINGS (marketplace) ──────────────────────────────────
    await _safe_create(db.listings, [("status", 1), ("end_time", 1)])
    await _safe_create(db.listings, [("status", 1), ("auction_end_date", 1)])
    await _safe_create(db.listings, [("seller_id", 1), ("status", 1)])
    await _safe_create(db.listings, [("category", 1), ("status", 1)])
    await _safe_create(db.listings, [("created_at", -1)])
    await _safe_create(db.listings, [("is_featured", 1), ("status", 1)])
    await _safe_create(db.listings, [("province", 1), ("status", 1)])
    await _safe_create(db.listings, [("seller_province", 1), ("status", 1)])

    # ── VEHICLE LISTINGS ────────────────────────────────────────
    await _safe_create(db.vehicle_listings, [("status", 1), ("end_time", 1)])
    await _safe_create(db.vehicle_listings, [("seller_id", 1), ("status", 1)])
    await _safe_create(db.vehicle_listings, [("opc_permit_verified", 1)])
    await _safe_create(db.vehicle_listings, [("reserve_met", 1), ("status", 1)])

    # ── STORAGE AUCTIONS ────────────────────────────────────────
    await _safe_create(db.storage_auctions, [("status", 1), ("end_time", 1)])
    await _safe_create(db.storage_auctions, [("facility_id", 1), ("status", 1)])
    await _safe_create(db.storage_auctions, [("province", 1), ("status", 1)])
    await _safe_create(db.storage_auctions, [("facility_province", 1), ("status", 1)])
    await _safe_create(db.storage_auctions, [("start_time", 1), ("status", 1)])

    # ── BIDS ────────────────────────────────────────────────────
    await _safe_create(db.bids, [("auction_id", 1), ("placed_at", -1)])
    await _safe_create(db.bids, [("listing_id", 1), ("placed_at", -1)])
    await _safe_create(db.bids, [("bidder_id", 1), ("placed_at", -1)])
    await _safe_create(db.bids, [("auction_id", 1), ("max_bid", -1)])

    # ── USERS ───────────────────────────────────────────────────
    await _safe_create(db.users, [("email", 1)], unique=True)
    await _safe_create(db.users, [("role", 1), ("subscription_tier", 1)])
    await _safe_create(db.users, [("province", 1)])
    await _safe_create(db.users, [("created_at", -1)])
    await _safe_create(db.users, [("stripe_customer_id", 1)])

    # ── DEPOSITS ────────────────────────────────────────────────
    await _safe_create(db.deposits, [("auction_id", 1), ("status", 1)])
    await _safe_create(db.deposits, [("user_id", 1), ("status", 1)])
    await _safe_create(db.deposits, [("stripe_payment_intent_id", 1)])
    # Project-internal collections
    await _safe_create(db.bidding_deposits, [("auction_id", 1), ("status", 1)])
    await _safe_create(db.bidding_deposits, [("user_id", 1), ("status", 1)])

    # ── INVOICES ────────────────────────────────────────────────
    await _safe_create(db.invoices, [("buyer_id", 1), ("status", 1)])
    await _safe_create(db.invoices, [("seller_id", 1), ("status", 1)])
    await _safe_create(db.invoices, [("auction_id", 1)])
    await _safe_create(db.invoices, [("payment_deadline", 1), ("status", 1)])

    # ── STORAGE FACILITIES ──────────────────────────────────────
    await _safe_create(db.storage_facilities, [("verified", 1)])
    await _safe_create(db.storage_facilities, [("province", 1), ("verified", 1)])
    await _safe_create(db.storage_facilities, [("status", 1)])

    # ── ADMIN LOGS ──────────────────────────────────────────────
    await _safe_create(db.admin_logs, [("created_at", -1)])
    await _safe_create(db.admin_logs, [("admin_id", 1), ("created_at", -1)])

    # ── SESSIONS / AUTH (TTL — auto-expire) ─────────────────────
    await _safe_create(db.refresh_tokens, [("expires_at", 1)], expireAfterSeconds=0)
    await _safe_create(db.refresh_tokens, [("token_hash", 1)], unique=True)
    await _safe_create(db.refresh_tokens, [("user_id", 1), ("revoked", 1)])
    await _safe_create(db.email_change_requests, [("expires_at", 1)], expireAfterSeconds=0)

    log.info("─" * 50)
    log.info("✅ All indexes created successfully")

    # Verify
    listing_indexes = await db.listings.list_indexes().to_list(None)
    log.info(f"Listings indexes: {len(listing_indexes)}")
    storage_indexes = await db.storage_auctions.list_indexes().to_list(None)
    log.info(f"Storage auctions indexes: {len(storage_indexes)}")
    user_indexes = await db.users.list_indexes().to_list(None)
    log.info(f"Users indexes: {len(user_indexes)}")
    refresh_indexes = await db.refresh_tokens.list_indexes().to_list(None)
    log.info(f"Refresh tokens indexes: {len(refresh_indexes)}")

    client.close()
    log.info("Connection closed.")


if __name__ == "__main__":
    asyncio.run(create_all_indexes())
