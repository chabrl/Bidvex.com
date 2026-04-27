"""
One-shot migration: rename "Farm Equipment" / "farm_equipment" → "Heavy Equipment" / "heavy_equipment"
Affects: listings, multi_item_listings, lots within multi-item listings, categories collection.

Run from /app/backend:
    python -m scripts.migrate_farm_equipment
"""
import asyncio
import os
import sys
from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "bazario_db")
    if not mongo_url:
        print("MONGO_URL not set. Aborting.")
        sys.exit(1)

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    rename_map = [
        ("Farm Equipment", "Heavy Equipment"),
        ("farm_equipment", "heavy_equipment"),
        ("farm equipment", "heavy equipment"),
        ("Farm equipment", "Heavy equipment"),
        ("Équipement agricole", "Équipement lourd"),
    ]

    summary = {}

    # 1. Single-item listings
    for old, new in rename_map:
        r = await db.listings.update_many({"category": old}, {"$set": {"category": new}})
        summary[f"listings:{old}->{new}"] = r.modified_count

    # 2. Multi-item listings (top-level category)
    for old, new in rename_map:
        r = await db.multi_item_listings.update_many({"category": old}, {"$set": {"category": new}})
        summary[f"multi_item_listings:{old}->{new}"] = r.modified_count

    # 3. Multi-item listings nested lots category
    for old, new in rename_map:
        r = await db.multi_item_listings.update_many(
            {"lots.category": old},
            {"$set": {"lots.$[elem].category": new}},
            array_filters=[{"elem.category": old}],
        )
        summary[f"multi_item_listings.lots:{old}->{new}"] = r.modified_count

    # 4. Categories collection — delete farm_equipment / Farm Equipment if a Heavy Equipment counterpart exists, else rename.
    farm_docs = await db.categories.find(
        {"$or": [
            {"slug": {"$in": ["farm_equipment", "farm-equipment"]}},
            {"name_en": {"$in": ["Farm Equipment", "farm equipment"]}},
            {"nameEn": {"$in": ["Farm Equipment", "farm equipment"]}},
        ]},
        {"_id": 0}
    ).to_list(50)
    for doc in farm_docs:
        # Check whether a Heavy Equipment record already exists
        heavy = await db.categories.find_one({
            "$or": [
                {"slug": {"$in": ["heavy_equipment", "heavy-equipment"]}},
                {"name_en": "Heavy Equipment"},
                {"nameEn": "Heavy Equipment"},
            ]
        }, {"_id": 0})
        if heavy:
            # Drop the duplicate farm record
            r = await db.categories.delete_one({"id": doc.get("id")})
            summary[f"categories:deleted_farm_id={doc.get('id')}"] = r.deleted_count
        else:
            # Rename in-place
            updates = {}
            if doc.get("name_en"):
                updates["name_en"] = "Heavy Equipment"
            if doc.get("nameEn"):
                updates["nameEn"] = "Heavy Equipment"
            if doc.get("name_fr"):
                updates["name_fr"] = "Équipement lourd"
            if doc.get("nameFr"):
                updates["nameFr"] = "Équipement lourd"
            if doc.get("slug"):
                updates["slug"] = "heavy_equipment"
            r = await db.categories.update_one({"id": doc.get("id")}, {"$set": updates})
            summary[f"categories:renamed_id={doc.get('id')}"] = r.modified_count

    print("=== Farm Equipment → Heavy Equipment migration complete ===")
    for k, v in summary.items():
        print(f"  {k}: {v}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
