"""
Verify Stripe key and migrate users with null stripe_customer_id.
"""
import os
import sys
import asyncio

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'), override=True)

import stripe
from motor.motor_asyncio import AsyncIOMotorClient

stripe.api_key = os.environ.get("STRIPE_API_KEY")

# Step 1: Verify key
print("=" * 50)
print("STEP 1: Verifying Stripe API Key")
print("=" * 50)

try:
    balance = stripe.Balance.retrieve()
    print(f"Key is VALID.")
    print(f"  Available balance: {balance.available}")
    print(f"  Pending balance:   {balance.pending}")
    print(f"  Livemode:          {balance.livemode}")
except Exception as e:
    print(f"Key verification FAILED: {e}")
    sys.exit(1)

# Step 2: Migrate users
print()
print("=" * 50)
print("STEP 2: Migrating users with null stripe_customer_id")
print("=" * 50)

async def migrate():
    mongo_url = os.environ.get("MONGO_URL")
    db_name = os.environ.get("DB_NAME", "bazario_db")
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    query = {
        "$or": [
            {"stripe_customer_id": None},
            {"stripe_customer_id": ""},
            {"stripe_customer_id": {"$exists": False}}
        ]
    }

    users = await db.users.find(query, {"_id": 0, "id": 1, "email": 1, "name": 1, "username": 1}).to_list(None)
    print(f"Found {len(users)} user(s) without a Stripe customer ID.\n")

    for user in users:
        email = user.get("email", "")
        name = user.get("name") or user.get("username") or email
        user_id = user.get("id")

        try:
            customer = stripe.Customer.create(
                email=email,
                name=name,
                metadata={"user_id": user_id, "platform": "bidvex"}
            )
            await db.users.update_one(
                {"id": user_id},
                {"$set": {"stripe_customer_id": customer.id}}
            )
            print(f"  ✓ {email} → {customer.id}")
        except Exception as e:
            print(f"  ✗ {email} → FAILED: {e}")

    print(f"\nMigration complete.")
    client.close()

asyncio.run(migrate())
