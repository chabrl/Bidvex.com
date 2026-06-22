"""
iter310 — Mark QA seed sellers as `is_demo_account=true` so the
`validate_payment_method_for_listing` guard short-circuits during testing
agent flows. This unblocks the previously-skipped D1 multi-item create
e2e test without attaching a real card to a live Stripe customer.

Idempotent — re-runnable safely.

Run:
  python /app/backend/scripts/iter310_mark_testseller_demo.py
"""
import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402

QA_EMAILS = [
    "testseller@bidvex.com",
    "testdealer@bidvex.com",
    "iter302seller@test.com",
]


async def main():
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = cli[os.environ["DB_NAME"]]
    flipped = []
    for email in QA_EMAILS:
        u = await db.users.find_one({"email": email}, {"_id": 0, "id": 1, "is_demo_account": 1, "phone_verified": 1})
        if not u:
            print(f"⏭️  {email} — not found, skipping")
            continue
        already = bool(u.get("is_demo_account"))
        res = await db.users.update_one(
            {"email": email},
            {"$set": {
                "is_demo_account":  True,
                "has_payment_method": True,
                "phone_verified":   True,  # also skip phone verify gate
                "is_demo_sandbox":  True,
            }},
        )
        flipped.append((email, already, bool(res.modified_count)))
        print(f"{'✅' if res.modified_count else '✓'} {email}  was_demo={already}  modified={res.modified_count}")
    cli.close()
    print()
    print(f"Done — flipped {sum(1 for _, _, m in flipped if m)} users to demo+verified.")


if __name__ == "__main__":
    asyncio.run(main())
