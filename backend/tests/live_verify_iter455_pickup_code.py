"""
iter455 — Live preview end-to-end verifier for the pickup-code fix.

Seeds a held escrow with a canonical BVX-XXXXXXXX code, logs in as
admin, and hits `POST /api/escrow/seller/confirm-pickup` with:

  Step 1. The EXACT code shown to the buyer  → expect release
  Step 2. Wrong code                          → expect 400 (fresh escrow)
  Step 3. Lowercase / unhyphenated variant    → expect release (fresh escrow)
  Step 4. Legacy 6-char code                  → expect release (fresh escrow)
  Step 5. Reused code on already-released     → expect 4xx
  Step 6. Expired code                        → expect 410

Stripe transfers are mocked at the DB layer by removing the seller's
stripe_connect_account_id so the endpoint short-circuits (skips the
transfer). This proves the CODE VALIDATION side without moving funds.

The script cleans up all seeded documents on exit.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PW = "Anderosli123!@#"


async def _seed(db, *, auction_id, seller_id, buyer_id, code,
                status="held", expires_delta=timedelta(hours=48)):
    now = datetime.now(timezone.utc)
    doc = {
        "auction_id": auction_id,
        "listing_id": auction_id,
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "hammer_price_cents": 1400,
        "total_charged_cents": 1500,
        "application_fee_cents": 100,
        "stripe_payment_intent_id": f"pi_iter455_live_{auction_id}",
        "stripe_transfer_id": None,
        "escrow_status": status,
        "pickup_code": code,
        "pickup_code_expires_at": (now + expires_delta).isoformat(),
        "pickup_code_entered_at": None,
        "pickup_confirmed_at": None,
        "funds_released_at": None,
        "auto_release_scheduled_at": (now + expires_delta).isoformat(),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "item_type": "non_vehicle",
        "province": "QC",
    }
    await db.escrow_transactions.insert_one(doc)


async def _cleanup(db, prefix: str):
    await db.escrow_transactions.delete_many(
        {"auction_id": {"$regex": f"^{prefix}"}}
    )
    await db.pickup_attempt_log.delete_many(
        {"auction_id": {"$regex": f"^{prefix}"}}
    )


async def _confirm(http, auth, auction_id, code):
    return await http.post(
        f"{BASE_URL}/api/escrow/seller/confirm-pickup",
        headers=auth,
        json={"auction_id": auction_id, "code": code},
    )


async def main():
    client_db = AsyncIOMotorClient(MONGO_URL)
    db = client_db[DB_NAME]

    admin = await db.users.find_one({"email": ADMIN_EMAIL})
    seller_id = admin["id"]
    # Snapshot admin's stripe_connect_account_id — we blank it during the
    # test so the transfer step short-circuits (no real funds move).
    original_connect_id = admin.get("stripe_connect_account_id")
    prefix = f"iter455-live-{uuid.uuid4().hex[:8]}"
    buyer_id = f"{prefix}-buyer"

    print(f"\n[iter455-live] Base: {BASE_URL}")
    print(f"[iter455-live] Prefix: {prefix}\n")

    # Blank the seller's connect id so the endpoint's transfer step is
    # skipped (transfer_id stays None). Restored in the finally block.
    await db.users.update_one(
        {"id": seller_id}, {"$unset": {"stripe_connect_account_id": ""}}
    )

    checks: list[tuple[str, bool]] = []

    try:
        async with httpx.AsyncClient(timeout=60.0, verify=True) as http:
            r = await http.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PW},
            )
            token = r.json().get("access_token") or r.json().get("token")
            auth = {"Authorization": f"Bearer {token}"}
            print("[iter455-live] ✓ admin logged in\n")

            # STEP 1 — Exact BVX code
            aid = f"{prefix}-01"
            code = "BVX-ARKC661T"
            await _seed(db, auction_id=aid, seller_id=seller_id,
                        buyer_id=buyer_id, code=code)
            r = await _confirm(http, auth, aid, code)
            ok = r.status_code == 200 and r.json().get("status") == "released"
            checks.append((f"Step 1 — Exact code {code!r} releases", ok))
            print(f"  Step 1 → {r.status_code} {r.text[:100]}")

            # STEP 2 — Wrong code (fresh escrow)
            aid = f"{prefix}-02"
            await _seed(db, auction_id=aid, seller_id=seller_id,
                        buyer_id=buyer_id, code="BVX-CORRECT8")
            r = await _confirm(http, auth, aid, "BVX-WRONGCOD")
            ok = r.status_code == 400
            checks.append((f"Step 2 — Wrong code returns 400 (got {r.status_code})", ok))
            print(f"  Step 2 → {r.status_code} {r.text[:100]}")

            # STEP 3 — Lowercase / unhyphenated variant
            aid = f"{prefix}-03"
            canonical = "BVX-VARIANT2"
            await _seed(db, auction_id=aid, seller_id=seller_id,
                        buyer_id=buyer_id, code=canonical)
            r = await _confirm(http, auth, aid, "bvxvariant2")
            ok = r.status_code == 200 and r.json().get("status") == "released"
            checks.append((f"Step 3 — Lowercase/unhyphenated variant releases (got {r.status_code})", ok))
            print(f"  Step 3 → {r.status_code} {r.text[:100]}")

            # STEP 4 — Legacy 6-char code still validates
            aid = f"{prefix}-04"
            legacy = "ARKC66"
            await _seed(db, auction_id=aid, seller_id=seller_id,
                        buyer_id=buyer_id, code=legacy)
            r = await _confirm(http, auth, aid, legacy)
            ok = r.status_code == 200 and r.json().get("status") == "released"
            checks.append((f"Step 4 — Legacy 6-char code {legacy!r} releases (got {r.status_code})", ok))
            print(f"  Step 4 → {r.status_code} {r.text[:100]}")

            # STEP 5 — Reused code on already-released escrow
            r = await _confirm(http, auth, aid, legacy)  # aid still refers to step 4
            ok = r.status_code == 404
            checks.append((f"Step 5 — Reuse on released escrow returns 404 (got {r.status_code})", ok))
            print(f"  Step 5 → {r.status_code} {r.text[:100]}")

            # STEP 6 — Expired code (fresh escrow with past expiry)
            aid = f"{prefix}-06"
            code = "BVX-EXPIRED8"
            await _seed(db, auction_id=aid, seller_id=seller_id,
                        buyer_id=buyer_id, code=code,
                        expires_delta=-timedelta(hours=1))
            r = await _confirm(http, auth, aid, code)
            ok = r.status_code == 410
            checks.append((f"Step 6 — Expired code returns 410 (got {r.status_code})", ok))
            print(f"  Step 6 → {r.status_code} {r.text[:100]}")

    finally:
        # Restore the seller's connect id
        if original_connect_id is not None:
            await db.users.update_one(
                {"id": seller_id},
                {"$set": {"stripe_connect_account_id": original_connect_id}},
            )
        await _cleanup(db, prefix)
        client_db.close()

    print("\n[iter455-live] === Summary ===")
    all_ok = True
    for label, ok in checks:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {label}")
        if not ok:
            all_ok = False
    if all_ok:
        print("\n[iter455-live] ✅ ALL LIVE E2E CHECKS PASSED\n")
    else:
        print("\n[iter455-live] ❌ FAILURES ABOVE\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
