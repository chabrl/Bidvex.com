"""
Re-migrate users: create LIVE Stripe customers to replace test-mode ones.
"""
import os, sys, asyncio
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'), override=True)

import stripe
from motor.motor_asyncio import AsyncIOMotorClient

stripe.api_key = os.environ.get("STRIPE_API_KEY")

print(f"Using key: {stripe.api_key[:12]}...")
print(f"Livemode: {stripe.api_key.startswith('sk_live')}")

async def migrate():
    client = AsyncIOMotorClient(os.environ.get("MONGO_URL"))
    db = client[os.environ.get("DB_NAME", "bazario_db")]

    # Find ALL users (even those with test-mode customer IDs)
    users = await db.users.find({}, {"_id": 0, "id": 1, "email": 1, "name": 1, "username": 1, "stripe_customer_id": 1}).to_list(None)
    print(f"Found {len(users)} total users.\n")

    migrated = 0
    for user in users:
        email = user.get("email", "")
        name = user.get("name") or user.get("username") or email
        user_id = user.get("id")
        old_cid = user.get("stripe_customer_id", "")

        # Check if current customer_id works with the live key
        if old_cid:
            try:
                stripe.Customer.retrieve(old_cid)
                print(f"  SKIP {email} → {old_cid} (already valid in live mode)")
                continue
            except Exception:
                pass  # Customer doesn't exist in live mode, need to recreate

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
            print(f"  ✓ {email} → {customer.id} (replaced {old_cid or 'null'})")
            migrated += 1
        except Exception as e:
            print(f"  ✗ {email} → FAILED: {e}")

    print(f"\nMigration complete. {migrated} users updated.")
    client.close()

asyncio.run(migrate())
