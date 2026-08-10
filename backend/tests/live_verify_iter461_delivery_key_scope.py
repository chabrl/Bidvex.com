"""
iter461 STEP 2 — Acceptance test for the extended delivery-key scope.

Confirms:
  A. Fail → success within same buyer/auction ships both intended emails
     (payment_failed then buyer_receipt — different kinds).
  B. Two DISTINCT per-lot settlements for the same buyer + auction each
     fire their OWN buyer_receipt email exactly once (this is the
     scenario the previous iter460 key over-suppressed).
  C. Retries of the SAME lot's SAME event stay blocked.
  D. Two separate auctions for the same buyer fire independently.
  E. Once-per-auction kinds (`auction_won` at multi-item close) with
     `event_key=""` still de-dupe as before (aggregation preserved).

Cleans up all seeded ledger rows on exit.
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

PREFIX = f"iter461acc-{uuid.uuid4().hex[:8]}"


async def main():
    client_db = AsyncIOMotorClient(MONGO_URL)
    db = client_db[DB_NAME]

    from services.settlement_email_dedup import (
        claim_settlement_email, ensure_indexes, COLLECTION,
    )
    await ensure_indexes(db)

    checks: List[tuple] = []
    auction_1 = f"{PREFIX}-A"
    auction_2 = f"{PREFIX}-B"
    buyer = f"{PREFIX}-buyer"
    seller = f"{PREFIX}-seller"

    try:
        # ─── A. Fail → success (different kinds) ───
        a1 = await claim_settlement_email(
            db, kind="payment_failed", auction_id=auction_1, user_id=buyer,
            event_key="lot:1",
        )
        a2 = await claim_settlement_email(
            db, kind="buyer_receipt", auction_id=auction_1, user_id=buyer,
            event_key="lot:1",
        )
        checks.append(("A.1 First payment_failed for lot 1 fires", a1 is True))
        checks.append(("A.2 Later buyer_receipt for same lot 1 NOT blocked "
                       "(different kind)", a2 is True))

        # ─── B. Two DISTINCT per-lot settlements, same kind ───
        b_lot2 = await claim_settlement_email(
            db, kind="buyer_receipt", auction_id=auction_1, user_id=buyer,
            event_key="lot:2",
        )
        b_lot3 = await claim_settlement_email(
            db, kind="buyer_receipt", auction_id=auction_1, user_id=buyer,
            event_key="lot:3",
        )
        checks.append(("B.1 Second lot's legitimate buyer_receipt (lot:2) fires "
                       "(the previous over-suppression is fixed)", b_lot2 is True))
        checks.append(("B.2 Third lot's legitimate buyer_receipt (lot:3) fires",
                       b_lot3 is True))

        # ─── B'. Seller side — one seller_statement per lot ───
        b_seller_lot1 = await claim_settlement_email(
            db, kind="seller_statement", auction_id=auction_1, user_id=seller,
            event_key="lot:1",
        )
        b_seller_lot2 = await claim_settlement_email(
            db, kind="seller_statement", auction_id=auction_1, user_id=seller,
            event_key="lot:2",
        )
        checks.append(("B.3 Seller statement fires for lot 1", b_seller_lot1 is True))
        checks.append(("B.4 Seller statement fires for lot 2 (distinct settlement)",
                       b_seller_lot2 is True))

        # ─── C. Retries of the SAME lot's SAME event stay blocked ───
        c_retry_a = await claim_settlement_email(
            db, kind="payment_failed", auction_id=auction_1, user_id=buyer,
            event_key="lot:1",
        )
        c_retry_b = await claim_settlement_email(
            db, kind="buyer_receipt", auction_id=auction_1, user_id=buyer,
            event_key="lot:2",
        )
        c_retry_c = await claim_settlement_email(
            db, kind="seller_statement", auction_id=auction_1, user_id=seller,
            event_key="lot:1",
        )
        checks.append(("C.1 Retry of payment_failed lot 1 → BLOCKED", c_retry_a is False))
        checks.append(("C.2 Retry of buyer_receipt lot 2 → BLOCKED", c_retry_b is False))
        checks.append(("C.3 Retry of seller_statement lot 1 → BLOCKED", c_retry_c is False))

        # ─── D. Two separate auctions ───
        d1 = await claim_settlement_email(
            db, kind="buyer_receipt", auction_id=auction_2, user_id=buyer,
            event_key="lot:1",
        )
        checks.append(("D.1 New auction's buyer_receipt fires independently", d1 is True))

        # ─── E. Once-per-auction kinds (auction_won for multi-item aggregate) ───
        e1 = await claim_settlement_email(
            db, kind="auction_won", auction_id=auction_1, user_id=buyer,
        )
        e2 = await claim_settlement_email(
            db, kind="auction_won", auction_id=auction_1, user_id=buyer,
        )
        checks.append(("E.1 auction_won (event_key='') first claim fires", e1 is True))
        checks.append(("E.2 auction_won retry (event_key='') BLOCKED — "
                       "aggregation preserved", e2 is False))

        # Same buyer, DIFFERENT event_key on auction_won: this is the
        # vehicle-multi-lot per-lot pattern; each lot legitimately fires.
        e3 = await claim_settlement_email(
            db, kind="auction_won", auction_id=auction_1, user_id=buyer,
            event_key="lot:99",
        )
        checks.append(("E.3 auction_won with a DIFFERENT event_key on same "
                       "(auction, buyer) fires (vehicle-multi-lot behaviour)",
                       e3 is True))

        # ─── Row inventory ───
        rows = await db[COLLECTION].find(
            {"auction_id": {"$regex": f"^{PREFIX}"}}
        ).to_list(50)
        print(f"\n[iter461-acc] Ledger rows persisted: {len(rows)}")
        for r in rows:
            r.pop("_id", None)
            print(f"  {r.get('kind'):<25} auction={r.get('auction_id')} "
                  f"user={r.get('user_id')} event={r.get('event_key')!r}")

    finally:
        try:
            await db[COLLECTION].delete_many({"auction_id": {"$regex": f"^{PREFIX}"}})
            print("\n[iter461-acc] ✓ cleaned up seeded ledger rows")
        except Exception as e:  # noqa: BLE001
            print(f"[iter461-acc] cleanup warning: {e}")
        client_db.close()

    print("\n[iter461-acc] === Summary ===")
    all_ok = True
    for label, ok in checks:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {label}")
        if not ok:
            all_ok = False
    if all_ok:
        print(f"\n[iter461-acc] ✅ ALL {len(checks)} ACCEPTANCE CHECKS PASSED\n")
    else:
        print("\n[iter461-acc] ❌ FAILURES ABOVE\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
