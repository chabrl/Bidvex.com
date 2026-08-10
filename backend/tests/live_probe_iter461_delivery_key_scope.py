"""
iter461 STEP 1 — Test-only probe of settlement-email delivery-key scope.

DOES NOT CHANGE PRODUCTION CODE.

Goal: prove whether the current delivery key
    (kind, auction_id, user_id)
can suppress a genuinely-separate second settlement email of the same
kind within one auction.

Probes:

    A. Fail-then-succeed for the same buyer + auction.
       Different email KINDS (`payment_failed` → `buyer_receipt`) —
       must NOT be blocked by the ledger.

    B. Two distinct per-lot settlement completions for the same buyer +
       auction that settle at different points in time (mimics vehicle
       multi-lot lots closing sequentially, or cash-payment trickle).
       Same email kind on different lots — the CURRENT key blocks the
       second legitimate settlement.

    C. Retries of the SAME lot's SAME event.
       Must remain blocked.

    D. Two separate auctions for the same buyer + same kind.
       Each auction fires its own email (different auction_id).

Cleans up all seeded ledger rows on exit (both PASS and FAIL paths).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path
from typing import List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]

PREFIX = f"iter461probe-{uuid.uuid4().hex[:8]}"


async def main():
    client_db = AsyncIOMotorClient(MONGO_URL)
    db = client_db[DB_NAME]

    from services.settlement_email_dedup import (
        claim_settlement_email,
        ensure_indexes,
        COLLECTION,
    )
    await ensure_indexes(db)

    checks: List[tuple] = []

    auction_1 = f"{PREFIX}-A"
    auction_2 = f"{PREFIX}-B"
    buyer = f"{PREFIX}-buyer"
    seller = f"{PREFIX}-seller"

    try:
        # ── Probe A: fail → success on same buyer + auction ──
        # Simulates the exact user scenario: buyer's card fails at
        # settlement close (payment_failed email), buyer then pays via
        # the payment link (buyer_receipt email). Different KINDS.
        a1 = await claim_settlement_email(
            db, kind="payment_failed",
            auction_id=auction_1, user_id=buyer,
        )
        a2 = await claim_settlement_email(
            db, kind="buyer_receipt",
            auction_id=auction_1, user_id=buyer,
        )
        checks.append(("Probe A.1 — first payment_failed claim succeeds (email would fire)", a1 is True))
        checks.append(("Probe A.2 — later buyer_receipt for SAME buyer/auction NOT blocked "
                       "(different kind → different key slot)", a2 is True))

        # ── Probe B: two distinct per-lot settlements, SAME kind ──
        # Mirrors "buyer pays for lot 1 today, cash for lot 2 arrives
        # 3 days later" or "vehicle multi-lot event where lots close at
        # different times". Each is a legitimate distinct settlement.
        b1 = await claim_settlement_email(
            db, kind="buyer_receipt",
            auction_id=auction_1, user_id=buyer,
        )
        # This one is the CRITICAL check: same key today, is it blocked?
        checks.append(("Probe B.1 — SECOND buyer_receipt for SAME buyer/auction with the "
                       "CURRENT key is BLOCKED (this is the over-suppression we must fix)",
                       b1 is False))

        # ── Probe C: retries of the SAME event stay blocked ──
        c1 = await claim_settlement_email(
            db, kind="payment_failed",
            auction_id=auction_1, user_id=buyer,
        )
        checks.append(("Probe C.1 — retry of first payment_failed claim is blocked "
                       "(protects against real retries)", c1 is False))

        # ── Probe D: two separate auctions, SAME kind, SAME buyer ──
        d1 = await claim_settlement_email(
            db, kind="buyer_receipt",
            auction_id=auction_2, user_id=buyer,
        )
        checks.append(("Probe D — new auction fires its own buyer_receipt (different "
                       "auction_id → independent claim)", d1 is True))

        # Print rows persisted, as a sanity check
        rows = await db[COLLECTION].find(
            {"auction_id": {"$in": [auction_1, auction_2]}}
        ).to_list(20)
        print("\n[iter461-probe] Ledger rows persisted:")
        for r in rows:
            r.pop("_id", None)
            print(f"  {r.get('kind'):<25} auction={r.get('auction_id')} user={r.get('user_id')} at={r.get('sent_at')}")

    finally:
        # Cleanup: remove every seeded ledger row.
        try:
            await db[COLLECTION].delete_many({
                "auction_id": {"$regex": f"^{PREFIX}"}
            })
            print("\n[iter461-probe] ✓ cleaned up seeded ledger rows")
        except Exception as e:  # noqa: BLE001
            print(f"[iter461-probe] cleanup warning: {e}")
        client_db.close()

    print("\n[iter461-probe] === Summary ===")
    all_ok = True
    for label, ok in checks:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {label}")
        if not ok:
            all_ok = False

    # This probe is DIAGNOSTIC — it PASSES when the current key is
    # provably too narrow (Probe B.1 blocked). If Probe B.1 is NOT
    # blocked the assumption is wrong and no fix is needed.
    if all_ok:
        print("\n[iter461-probe] ✅ VERIFIED: The current delivery key over-suppresses "
              "legitimate SECOND per-lot settlement emails within one auction.\n"
              "   → Recommendation: extend key with an event_key (e.g. lot_number) "
              "for per-lot kinds so distinct legitimate settlements each fire once.")
    else:
        print("\n[iter461-probe] ❌ probe outcome different than expected — inspect above.")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
