"""
Migration: Add vehicle settlement fields to existing collections.
Run once: python migrations/add_vehicle_settlement_fields.py
"""
import asyncio
import os
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone

MONGO_URL = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.environ.get("DB_NAME", "bidvex")


async def migrate():
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()

    # 1. Add settlement fields to vehicle_listings that are already "sold"
    result = await db.vehicle_listings.update_many(
        {"status": "sold", "settlement_status": {"$exists": False}},
        {"$set": {
            "settlement_status": "PENDING_CLOSE",
            "contact_revealed": False,
        }}
    )
    print(f"Updated {result.modified_count} sold vehicle listings with settlement fields")

    # 2. Add ai_disclosure_consent to existing users who don't have it
    result2 = await db.users.update_many(
        {"ai_disclosure_consent": {"$exists": False}},
        {"$set": {
            "ai_disclosure_consent": False,
            "ai_consent_timestamp": None,
            "ai_consent_ip": None,
        }}
    )
    print(f"Updated {result2.modified_count} users with ai_disclosure_consent field")

    # LEGACY: opc_permit → migrated to dealer_license_* (iter201) — do not expose to users.
    # Kept for backwards-compat read-side migration only; new code uses dealer_license_* fields.
    # 3. Add legacy opc_permit fields to existing users who don't have them
    result3 = await db.users.update_many(
        {"opc_permit_number": {"$exists": False}},
        {"$set": {
            "opc_permit_number": None,
            "opc_permit_verified": False,
        }}
    )
    print(f"Updated {result3.modified_count} users with legacy opc_permit fields (read-only since iter201)")

    # 4. Create index on vehicle_settlements
    await db.vehicle_settlements.create_index(
        [("auction_id", 1), ("buyer_id", 1)],
        unique=True,
        name="idx_settlement_auction_buyer",
        sparse=True,
    )
    await db.vehicle_settlements.create_index(
        [("stripe_payment_intent_id", 1)],
        name="idx_settlement_pi",
        sparse=True,
    )
    print("Created vehicle_settlements indexes")

    # 5. Add cfia_soil_declaration to listings that don't have it
    result4 = await db.listings.update_many(
        {"cfia_soil_declaration": {"$exists": False}},
        {"$set": {"cfia_soil_declaration": None}}
    )
    print(f"Updated {result4.modified_count} listings with cfia_soil_declaration field")

    client.close()
    print("Migration complete.")


if __name__ == "__main__":
    asyncio.run(migrate())
