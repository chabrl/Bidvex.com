"""
iter308 — Re-seed test fixtures referenced by iter299→iter308 regression suite
==============================================================================

Some test files reference accounts that have drifted (re-seeded on a different
DB, or password reset). This script makes the DB match the canonical fixtures
documented in `/app/memory/test_credentials.md`:

  • iter225buyer@bidvex.com / TestBuyer225!  (used by test_iter301_review_request)
  • iter302buyer@test.com / TestBuyer123!    (referenced in test_credentials.md)
  • testseller@bidvex.com / TestSeller2026!  (re-asserted)
  • testdealer@bidvex.com / TestDealer2026!  (re-asserted)
  • testbuyer@bidvex.com  / TestBuyer2026!   (re-asserted)

Idempotent — runs as `python iter308_reseed_test_fixtures.py`.
"""
import asyncio
import os
import uuid
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
from passlib.context import CryptContext


load_dotenv("/app/backend/.env")
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


FIXTURES = [
    {
        "email": "iter225buyer@bidvex.com",
        "password": "TestBuyer225!",
        "first_name": "Iter225",
        "last_name": "Buyer",
        "name": "Iter225 Buyer",
        "phone": "+15145550199",
        "phone_verified": True,
        "province": "QC",
        "role": "user",
        "preferred_language": "en",
        "id": "85b3ce59-f264-4d43-8d12-19b3449ec8b3",
    },
    {
        "email": "iter302buyer@test.com",
        "password": "TestBuyer123!",
        "first_name": "Iter302",
        "last_name": "Buyer",
        "name": "Iter302 Buyer",
        "phone": "+15145550299",
        "phone_verified": True,
        "email_verified": True,
        "id_verified": True,
        "province": "QC",
        "role": "user",
        "preferred_language": "en",
        "id": "eaf07e4e-052c-4ee9-932c-14609fa65743",
    },
    {
        "email": "testbuyer@bidvex.com",
        "password": "TestBuyer2026!",
        "first_name": "Test", "last_name": "Buyer", "name": "Test Buyer",
        "province": "QC", "role": "user", "preferred_language": "en",
    },
    {
        "email": "testseller@bidvex.com",
        "password": "TestSeller2026!",
        "first_name": "Test", "last_name": "Seller", "name": "Test Seller",
        "province": "QC", "role": "user", "preferred_language": "en",
        "trusted_seller": True,
    },
    {
        "email": "testdealer@bidvex.com",
        "password": "TestDealer2026!",
        "first_name": "Test", "last_name": "Dealer", "name": "Test Dealer",
        "province": "QC", "role": "user", "preferred_language": "fr",
        "is_vehicle_dealer": True, "vehicle_dealer_verified": True,
        "seller_type": "dealer",
    },
]


async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]

    for fx in FIXTURES:
        existing = await db.users.find_one({"email": fx["email"]})
        now = datetime.now(timezone.utc)
        if existing:
            # Reset password + optional flags so login works
            updates = {
                "password_hash": pwd_context.hash(fx["password"]),
                "_seed_demo_v1": True,
                "password_reset_at": now,
            }
            for opt in ("phone_verified", "email_verified", "id_verified",
                        "trusted_seller", "is_vehicle_dealer",
                        "vehicle_dealer_verified", "seller_type"):
                if opt in fx:
                    updates[opt] = fx[opt]
            await db.users.update_one({"email": fx["email"]}, {"$set": updates})
            print(f"  ↻  reset password for {fx['email']} (id={existing['id']})")
        else:
            uid = fx.get("id") or str(uuid.uuid4())
            user_doc = {
                "id": uid,
                "email": fx["email"].lower(),
                "password_hash": pwd_context.hash(fx["password"]),
                "first_name": fx.get("first_name", ""),
                "last_name": fx.get("last_name", ""),
                "name": fx.get("name") or fx["email"],
                "phone": fx.get("phone", ""),
                "phone_verified": bool(fx.get("phone_verified")),
                "email_verified": bool(fx.get("email_verified", True)),
                "id_verified": bool(fx.get("id_verified")),
                "province": fx.get("province", "ON"),
                "role": fx.get("role", "user"),
                "preferred_language": fx.get("preferred_language", "en"),
                "trusted_seller": bool(fx.get("trusted_seller")),
                "is_vehicle_dealer": bool(fx.get("is_vehicle_dealer")),
                "vehicle_dealer_verified": bool(fx.get("vehicle_dealer_verified")),
                "seller_type": fx.get("seller_type", "individual"),
                "is_verified": True,
                "terms_accepted": True,
                "ai_disclosure_accepted": True,
                "created_at": now,
                "_seed_demo_v1": True,
            }
            await db.users.insert_one(user_doc)
            print(f"  +  created {fx['email']} (id={uid})")

    cli.close()


if __name__ == "__main__":
    asyncio.run(main())
