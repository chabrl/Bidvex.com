#!/usr/bin/env python3
"""
iter330 — CI Code↔DB Subscription Plan Drift Guard.

Sister script to verify_stripe_sync.py. Closes the third leg of the
Stripe ↔ Code ↔ DB triangle by verifying that the MongoDB
`subscription_plans` collection rows match
`services.subscription_pricing.DEFAULT_PLANS`.

Exits 0 on sync, exits 1 on drift (so CI fails the build).

USAGE
-----
    cd /app/backend && python scripts/verify_db_subscription_sync.py
    # or with auto-fix (use with care — overwrites DB rows):
    cd /app/backend && python scripts/verify_db_subscription_sync.py --fix

CI INTEGRATION (read-only mode)
-------------------------------
    python /app/backend/scripts/verify_db_subscription_sync.py || exit 1

Compared fields per plan: price_monthly, price_yearly,
original_price_monthly, original_price_yearly, name, monthly_listing_limit,
buyer_premium_discount, seller_commission_discount, is_active.
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Make backend/ importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Load .env if MONGO_URL isn't already set.
if "MONGO_URL" not in os.environ:
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if env_file.exists():
        for raw in env_file.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402
from datetime import datetime, timezone  # noqa: E402

from services.subscription_pricing import DEFAULT_PLANS  # noqa: E402


COMPARE_FIELDS = (
    "price_monthly", "price_yearly",
    "original_price_monthly", "original_price_yearly",
    "name", "monthly_listing_limit",
    "buyer_premium_discount", "seller_commission_discount",
    "is_active",
)


def _drift_between(canonical: Dict[str, Any], db_row: Dict[str, Any]) -> List[Tuple[str, Any, Any]]:
    """Return a list of (field, code_value, db_value) tuples where they differ."""
    out: List[Tuple[str, Any, Any]] = []
    for field in COMPARE_FIELDS:
        code_v = canonical.get(field)
        db_v = db_row.get(field)
        if code_v is None and db_v is None:
            continue
        if code_v != db_v:
            out.append((field, code_v, db_v))
    return out


async def main(argv: List[str]) -> int:
    auto_fix = "--fix" in argv
    print("BidVex Code↔DB Subscription Plan Drift Guard (iter330)")
    print("=" * 70)

    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    coll = db.subscription_plans

    total_drift_rows = 0
    total_fixed = 0
    total_missing_in_db = 0
    extra_in_db: List[str] = []

    # Plans in CODE → check against DB.
    for plan_id, canonical in DEFAULT_PLANS.items():
        db_row = await coll.find_one({"plan_id": plan_id}, {"_id": 0})
        if db_row is None:
            total_missing_in_db += 1
            if auto_fix:
                doc = dict(canonical)
                doc["created_at"] = datetime.now(timezone.utc).isoformat()
                doc["updated_at"] = datetime.now(timezone.utc).isoformat()
                await coll.insert_one(doc)
                print(f"   🔧 {plan_id:<14} missing in DB — INSERTED from DEFAULT_PLANS")
            else:
                print(f"   ❌ {plan_id:<14} missing in DB (code has it, DB does not)")
            continue

        drifts = _drift_between(canonical, db_row)
        if not drifts:
            print(f"   ✅ {plan_id:<14} in sync")
            continue

        total_drift_rows += 1
        print(f"   ❌ {plan_id:<14} DRIFT ({len(drifts)} fields):")
        for field, code_v, db_v in drifts:
            print(f"         {field}: code={code_v!r}   db={db_v!r}")

        if auto_fix:
            updates = {field: canonical.get(field) for field, _, _ in drifts}
            updates["updated_at"] = datetime.now(timezone.utc).isoformat()
            await coll.update_one({"plan_id": plan_id}, {"$set": updates})
            total_fixed += 1
            print(f"         🔧 Auto-fixed {len(drifts)} field(s) → DB")

    # Plans in DB that AREN'T in code — surface as orphan rows.
    async for db_row in coll.find({}, {"_id": 0, "plan_id": 1}):
        pid = db_row.get("plan_id")
        if pid and pid not in DEFAULT_PLANS:
            extra_in_db.append(pid)

    if extra_in_db:
        print(
            f"\n   ⚠️  {len(extra_in_db)} orphan plan(s) in DB not present in DEFAULT_PLANS: "
            f"{', '.join(extra_in_db)}"
        )
        if auto_fix:
            for pid in extra_in_db:
                await coll.delete_one({"plan_id": pid})
                print(f"         🔧 Removed orphan plan_id={pid!r}")

    print("=" * 70)
    client.close()

    if auto_fix:
        print(f"\n🔧 Auto-fix complete — {total_fixed} updated, "
              f"{total_missing_in_db} inserted, {len(extra_in_db)} orphans removed.")
        return 0

    if total_drift_rows or total_missing_in_db or extra_in_db:
        print(
            f"\nDRIFT DETECTED — build should fail.\n"
            f"  rows with drift: {total_drift_rows}\n"
            f"  missing in DB:   {total_missing_in_db}\n"
            f"  orphans in DB:   {len(extra_in_db)}\n\n"
            f"Resolution: either update DEFAULT_PLANS in code, OR run this script "
            f"with --fix to overwrite DB rows from canonical code values:\n"
            f"  python {Path(__file__).name} --fix"
        )
        return 1
    print("\n✅ Code ↔ DB subscription_plans fully in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1:])))
