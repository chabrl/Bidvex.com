"""
iter201 — Phase 1 / Migration: silent rename of legacy `opc_permit_*` fields to
the province-aware `dealer_license_*` fields on existing user documents.

Per CEO directive Q2=(a): "Migrate them silently into the new dealer_license_* fields
on first read. Lossless rename. Do not drop the old fields yet — mark them deprecated."

This migration:
  • Backfills `dealer_license_number` from `opc_permit_number` if missing.
  • Backfills `dealer_license_verified` from `opc_permit_verified` if missing.
  • Initializes `dealer_license_province`, `dealer_license_type`, `neq`,
    `vehicle_buyer_verification` to None for users that don't have them.
  • Leaves the legacy fields untouched.

Idempotent — safe to re-run.

Run:
    cd /app/backend && python migrations/migrate_dealer_license_fields.py
"""
import asyncio
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv()


async def migrate(verbose: bool = True) -> dict:
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    coll = db.users

    total = await coll.count_documents({})
    backfill_number = 0
    backfill_verified = 0
    init_new_fields = 0

    cursor = coll.find(
        {},
        {
            "_id": 0,
            "id": 1,
            "opc_permit_number": 1,
            "opc_permit_verified": 1,
            "dealer_license_number": 1,
            "dealer_license_verified": 1,
            "dealer_license_province": 1,
            "dealer_license_type": 1,
            "neq": 1,
            "vehicle_buyer_verification": 1,
        },
    )

    async for doc in cursor:
        if not doc.get("id"):
            continue  # skip legacy docs without canonical id field
        sets: dict = {}

        # Backfill dealer_license_number from legacy opc_permit_number
        if "dealer_license_number" not in doc and doc.get("opc_permit_number") is not None:
            sets["dealer_license_number"] = doc["opc_permit_number"]
            backfill_number += 1
        elif "dealer_license_number" not in doc:
            sets["dealer_license_number"] = None

        # Backfill dealer_license_verified from legacy opc_permit_verified
        if "dealer_license_verified" not in doc:
            legacy_v = doc.get("opc_permit_verified")
            sets["dealer_license_verified"] = bool(legacy_v) if legacy_v is not None else False
            if legacy_v:
                backfill_verified += 1

        # Initialize new fields if absent
        for new_field in ("dealer_license_province", "dealer_license_type", "neq", "vehicle_buyer_verification"):
            if new_field not in doc:
                sets[new_field] = None
                init_new_fields += 1

        if sets:
            sets["updated_at"] = datetime.now(timezone.utc).isoformat()
            await coll.update_one({"id": doc["id"]}, {"$set": sets})

    if verbose:
        print(f"[migrate_dealer_license_fields] users scanned: {total}")
        print(f"  backfilled dealer_license_number from legacy: {backfill_number}")
        print(f"  backfilled dealer_license_verified=True from legacy: {backfill_verified}")
        print(f"  initialized new field assignments (counted across users): {init_new_fields}")

    cli.close()
    return {
        "total_users": total,
        "backfilled_number": backfill_number,
        "backfilled_verified": backfill_verified,
        "initialized_new_fields": init_new_fields,
    }


if __name__ == "__main__":
    res = asyncio.run(migrate())
    print("✅ dealer_license_* migration complete.")
