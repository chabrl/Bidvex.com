"""
One-shot migration: ensure every user doc has `marketing_unsubscribed` default=False
and create the unique index on email_suppressions.email.

Run from /app/backend:
    python -m scripts.migrate_unsubscribe_fields
"""
import asyncio
import os
import sys

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient


async def main():
    load_dotenv(override=True)
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "bazario_db")
    if not mongo_url:
        print("MONGO_URL not set. Aborting.")
        sys.exit(1)

    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    # Backfill marketing_unsubscribed: default False for existing users
    r = await db.users.update_many(
        {"marketing_unsubscribed": {"$exists": False}},
        {"$set": {"marketing_unsubscribed": False}},
    )
    print(f"[MIGRATION] users.marketing_unsubscribed backfilled: {r.modified_count} docs")

    # email_suppressions collection — unique index on email
    try:
        await db.email_suppressions.create_index("email", unique=True)
        print("[MIGRATION] email_suppressions.email unique index created/verified")
    except Exception as e:
        print(f"[MIGRATION] index warning (probably already exists): {e}")

    # Backfill suppression table from existing marketing_unsubscribed users
    async for u in db.users.find(
        {"marketing_unsubscribed": True}, {"_id": 0, "email": 1, "marketing_unsubscribed_at": 1, "marketing_unsubscribed_source": 1}
    ):
        if not u.get("email"):
            continue
        await db.email_suppressions.update_one(
            {"email": u["email"]},
            {"$set": {
                "email": u["email"].lower(),
                "unsubscribed_at": u.get("marketing_unsubscribed_at"),
                "source": u.get("marketing_unsubscribed_source", "legacy_backfill"),
            }},
            upsert=True,
        )

    total = await db.email_suppressions.count_documents({})
    print(f"[MIGRATION] email_suppressions total after backfill: {total}")

    client.close()


if __name__ == "__main__":
    asyncio.run(main())
