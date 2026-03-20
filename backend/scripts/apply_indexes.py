#!/usr/bin/env python3
"""
BidVex Production Index Script — scripts/apply_indexes.py

Idempotent: safe to run repeatedly. Checks existing indexes before creation.
Uses AsyncIOMotorClient with connection params from backend/.env.

Usage:
    cd /app/backend && python scripts/apply_indexes.py
"""

import asyncio
import os
import sys
import logging
from pathlib import Path

# Load .env from backend directory
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ASCENDING

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-5s  %(message)s")
log = logging.getLogger("apply_indexes")

MONGO_URL = os.environ.get("MONGO_URL")
DB_NAME = os.environ.get("DB_NAME", "bazario_db")

if not MONGO_URL:
    log.error("MONGO_URL not set. Aborting.")
    sys.exit(1)

# ── Index definitions ────────────────────────────────────────────────
# Format: (collection, [(field, direction), ...], index_name, unique)
INDEXES = [
    # ── Auctions ─────────────────────────────────────────────────────
    ("auctions", [("status", ASCENDING), ("endDate", ASCENDING)],
     "idx_auctions_status_endDate", False),
    ("auctions", [("category", ASCENDING)],
     "idx_auctions_category", False),

    # ── Users ────────────────────────────────────────────────────────
    ("users", [("email", ASCENDING)],
     "idx_users_email_unique", True),

    # ── Listings (high-traffic queries) ──────────────────────────────
    ("listings", [("status", ASCENDING), ("created_at", ASCENDING)],
     "idx_listings_status_created", False),
    ("listings", [("status", ASCENDING), ("category", ASCENDING)],
     "idx_listings_status_category", False),
    ("listings", [("status", ASCENDING), ("auction_end_date", ASCENDING)],
     "idx_listings_status_enddate", False),
    ("listings", [("seller_id", ASCENDING), ("status", ASCENDING)],
     "idx_listings_seller_status", False),
    ("listings", [("id", ASCENDING)],
     "idx_listings_id_unique", True),
    ("listings", [("category", ASCENDING)],
     "idx_listings_category", False),

    # ── Users (additional) ───────────────────────────────────────────
    ("users", [("id", ASCENDING)],
     "idx_users_id_unique", True),
    ("users", [("role", ASCENDING)],
     "idx_users_role", False),

    # ── Bids ─────────────────────────────────────────────────────────
    ("bids", [("listing_id", ASCENDING)],
     "idx_bids_listing_id", False),
    ("lot_bids", [("listing_id", ASCENDING), ("lot_number", ASCENDING)],
     "idx_lot_bids_listing_lot", False),
    ("auto_bids", [("user_id", ASCENDING), ("listing_id", ASCENDING), ("is_active", ASCENDING)],
     "idx_auto_bids_user_listing", False),

    # ── Invoices ─────────────────────────────────────────────────────
    ("invoices", [("user_id", ASCENDING)],
     "idx_invoices_user_id", False),
    ("subscription_invoices", [("user_id", ASCENDING)],
     "idx_sub_invoices_user_id", False),

    # ── Transactions ─────────────────────────────────────────────────
    ("transactions", [("status", ASCENDING), ("created_at", ASCENDING)],
     "idx_transactions_status_created", False),
    ("transactions", [("buyer_id", ASCENDING)],
     "idx_transactions_buyer", False),
    ("transactions", [("seller_id", ASCENDING)],
     "idx_transactions_seller", False),

    # ── Notifications / Messages ─────────────────────────────────────
    ("notifications", [("user_id", ASCENDING), ("is_read", ASCENDING), ("created_at", ASCENDING)],
     "idx_notifications_user_read_date", False),
    ("messages", [("conversation_id", ASCENDING), ("created_at", ASCENDING)],
     "idx_messages_conversation_date", False),

    # ── Multi-item listings ──────────────────────────────────────────
    ("multi_item_listings", [("status", ASCENDING), ("created_at", ASCENDING)],
     "idx_multi_listings_status_created", False),
    ("multi_item_listings", [("id", ASCENDING)],
     "idx_multi_listings_id_unique", True),

    # ── Partner Pro ──────────────────────────────────────────────────
    ("featured_listings", [("user_id", ASCENDING)],
     "idx_featured_user", False),
    ("featured_listings", [("user_id", ASCENDING), ("featured_at", ASCENDING)],
     "idx_featured_user_date", False),
    ("scheduled_emails", [("scheduled_for", ASCENDING), ("sent", ASCENDING)],
     "idx_sched_emails_for_sent", False),
    ("storefronts", [("user_id", ASCENDING)],
     "idx_storefronts_user", True),
]


async def main():
    log.info(f"Connecting to {DB_NAME} ...")
    client = AsyncIOMotorClient(MONGO_URL, serverSelectionTimeoutMS=10000)
    db = client[DB_NAME]

    # Verify connectivity
    await client.admin.command("ping")
    log.info("MongoDB connection OK")

    # ── 1. Ensure collections exist ──────────────────────────────────
    existing_collections = set(await db.list_collection_names())
    required = {"auctions", "users"}
    for coll in required:
        if coll not in existing_collections:
            await db.create_collection(coll)
            log.info(f"  Created collection: {coll}")
        else:
            log.info(f"  Collection exists:  {coll}")

    # ── 2. Apply indexes (idempotent) ────────────────────────────────
    created = 0
    skipped = 0
    errors = 0

    for coll_name, keys, name, unique in INDEXES:
        try:
            existing = await db[coll_name].index_information()
            if name in existing:
                log.info(f"  SKIP  {coll_name}.{name} (already exists)")
                skipped += 1
                continue

            await db[coll_name].create_index(keys, name=name, unique=unique, background=True)
            label = " [UNIQUE]" if unique else ""
            log.info(f"  OK    {coll_name}.{name}{label}")
            created += 1
        except Exception as exc:
            log.warning(f"  WARN  {coll_name}.{name} — {exc}")
            errors += 1

    # ── 3. Summary ───────────────────────────────────────────────────
    log.info("─" * 50)
    log.info(f"Done.  Created: {created}  |  Skipped: {skipped}  |  Warnings: {errors}")

    # ── 4. Verify by listing all indexes ─────────────────────────────
    log.info("")
    log.info("Verification — all indexes on key collections:")
    for coll_name in sorted({c for c, *_ in INDEXES}):
        indexes = await db[coll_name].index_information()
        log.info(f"  {coll_name} ({len(indexes)} indexes):")
        for idx_name, idx_info in sorted(indexes.items()):
            keys_str = ", ".join(f"{k}:{d}" for k, d in idx_info["key"])
            unique_str = " UNIQUE" if idx_info.get("unique") else ""
            log.info(f"    {idx_name}: ({keys_str}){unique_str}")

    client.close()
    log.info("Connection closed.")


if __name__ == "__main__":
    asyncio.run(main())
