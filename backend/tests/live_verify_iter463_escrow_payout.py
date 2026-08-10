"""
iter463 — Controlled escrow payout verification.

Runs the ACTUAL `services.escrow_service.confirm_pickup` code path with
the real Stripe test secret key (STRIPE_TEST_SECRET_KEY) so
`stripe.Transfer.create` really executes against Stripe's test API. The
running backend's env still uses the placeholder `sk_test_emergent`; we
patch the escrow_service module's `stripe.api_key` in-process only for
the duration of this test — nothing is deployed and no shared config
is written.

What this verifies:
  1. A REAL Stripe test transfer reference (`tr_...`) is created for the
     internal Stripe test connected seller (`acct_1TML5nBfqgL1wEwf`).
  2. The transfer amount = total_charged_cents − application_fee_cents,
     currency=CAD, destination=internal test connected seller.
  3. The persisted `escrow_transactions.stripe_transfer_id` matches the
     Stripe-side transfer id.
  4. Reusing the SAME pickup code cannot create a second transfer:
       • The escrow row status is now `released`, so the endpoint returns
         404 for the same auction_id+code (no second Stripe.Transfer call).
       • Verified additionally by counting Stripe transfers with the same
         auction_id in metadata — must be exactly ONE.
  5. All BidVex-side test records are removed on exit (regardless of
     pass/fail): `escrow_transactions`, `pickup_attempt_log`. Any Stripe
     test transfer stays in Stripe's test-mode history (Stripe does not
     let us delete transfers — this is expected and does not affect
     production data).

Fixture:
  Fresh single escrow row with:
    total_charged_cents  = 1500   ($15.00 CAD)
    application_fee_cents = 100   ($1.00  CAD)
  Expected transfer amount = 1400 ($14.00 CAD)

  seller_id = admin id (already has real internal test
                        stripe_connect_account_id="acct_1TML5nBfqgL1wEwf")
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")

MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
STRIPE_TEST_SECRET_KEY = os.environ["STRIPE_TEST_SECRET_KEY"]
ADMIN_EMAIL = "charbel911@gmail.com"

# The internal Stripe test connected seller referenced in the handoff.
INTERNAL_TEST_CONNECT_ID = "acct_1TML5nBfqgL1wEwf"

PREFIX = f"iter463-{uuid.uuid4().hex[:8]}"


def _fresh(kind: str) -> str:
    return f"{PREFIX}-{kind}-{uuid.uuid4().hex[:6]}"


async def _cleanup(db, prefix: str, extra_ids: List[str]):
    """Remove every seeded BidVex-side record."""
    q = {"$regex": f"^{prefix}"}
    await db.escrow_transactions.delete_many({"auction_id": q})
    await db.pickup_attempt_log.delete_many({"auction_id": q})
    if extra_ids:
        await db.escrow_transactions.delete_many({"auction_id": {"$in": extra_ids}})
        await db.pickup_attempt_log.delete_many({"auction_id": {"$in": extra_ids}})


async def main():
    client_db = AsyncIOMotorClient(MONGO_URL)
    db = client_db[DB_NAME]

    checks: List[tuple] = []
    seeded_ids: List[str] = []

    print(f"\n[iter463] Prefix: {PREFIX}")
    print(f"[iter463] Using Stripe test key prefix: {STRIPE_TEST_SECRET_KEY[:12]}...")

    try:
        # ── Patch escrow_service.stripe with the REAL test key ───────
        import services.escrow_service as escrow_service
        import stripe as _stripe_module
        _original_key = _stripe_module.api_key
        _stripe_module.api_key = STRIPE_TEST_SECRET_KEY
        escrow_service.stripe.api_key = STRIPE_TEST_SECRET_KEY

        # Verify balance is Available (per user directive) BEFORE we try
        # to transfer — this is a paranoia sanity check.
        try:
            bal = _stripe_module.Balance.retrieve()
            avail_cad = sum(
                b.amount for b in bal.available if b.currency == "cad"
            )
            print(f"[iter463] Stripe available CAD balance: ${avail_cad / 100:.2f}")
            checks.append((
                f"Pre-flight: Stripe available CAD balance is > 0 "
                f"(got ${avail_cad / 100:.2f})",
                avail_cad > 0,
            ))
        except Exception as exc:  # noqa: BLE001
            checks.append((f"Pre-flight: Stripe balance retrieve failed: {exc}", False))
            raise

        # Verify the internal connect account is reachable in this test key.
        try:
            acct = _stripe_module.Account.retrieve(INTERNAL_TEST_CONNECT_ID)
            checks.append((
                f"Pre-flight: Internal test connect account "
                f"{INTERNAL_TEST_CONNECT_ID} is retrievable in Stripe test mode",
                acct.id == INTERNAL_TEST_CONNECT_ID,
            ))
        except Exception as exc:  # noqa: BLE001
            checks.append((f"Pre-flight: connect account retrieve failed: {exc}", False))
            raise

        # ── Fetch admin (real internal test seller) ──
        admin = await db.users.find_one({"email": ADMIN_EMAIL})
        seller_id = admin["id"]
        connect_id_from_db = admin.get("stripe_connect_account_id")
        checks.append((
            f"Admin user has stripe_connect_account_id matching internal "
            f"test seller (got {connect_id_from_db})",
            connect_id_from_db == INTERNAL_TEST_CONNECT_ID,
        ))

        # ── Seed a FRESH removable escrow row ──
        auction_id = _fresh("auction")
        seeded_ids.append(auction_id)
        buyer_id = _fresh("buyer")
        pickup_code = f"BVX-{uuid.uuid4().hex[:8].upper()}"
        now = datetime.now(timezone.utc)
        await db.escrow_transactions.insert_one({
            "auction_id": auction_id,
            "listing_id": auction_id,
            "buyer_id": buyer_id,
            "seller_id": seller_id,
            "hammer_price_cents": 1400,
            "total_charged_cents": 1500,      # $15.00
            "application_fee_cents": 100,     # $1.00
            "stripe_payment_intent_id": f"pi_iter463_test_{auction_id}",
            "stripe_transfer_id": None,
            "escrow_status": "held",
            "pickup_code": pickup_code,
            "pickup_code_expires_at": (now + timedelta(hours=48)).isoformat(),
            "pickup_code_entered_at": None,
            "pickup_confirmed_at": None,
            "funds_released_at": None,
            "auto_release_scheduled_at": (now + timedelta(hours=48)).isoformat(),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "item_type": "non_vehicle",
            "province": "QC",
        })
        print(f"[iter463] ✓ seeded escrow {auction_id} with pickup code {pickup_code}")

        # ── FIRST call: pickup-code confirmation should create real transfer ──
        from services.escrow_service import confirm_pickup
        result = await confirm_pickup(db, seller_id, auction_id, pickup_code)

        transfer_id = result.get("transfer_id")
        amount_released = result.get("amount_released")
        checks.append((
            f"1st confirm-pickup returned status='released' "
            f"(got {result.get('status')!r})",
            result.get("status") == "released",
        ))
        checks.append((
            f"1st confirm-pickup returned a real Stripe test transfer id "
            f"(got {transfer_id!r})",
            isinstance(transfer_id, str) and transfer_id.startswith("tr_"),
        ))
        checks.append((
            f"1st confirm-pickup returned amount_released == '$14.00 CAD' "
            f"(got {amount_released!r})",
            amount_released == "$14.00 CAD",
        ))

        # ── Verify the transfer server-side via Stripe API ──
        transfer_obj = _stripe_module.Transfer.retrieve(transfer_id)
        checks.append((
            f"Stripe transfer amount = 1400 cents (got {transfer_obj.amount})",
            transfer_obj.amount == 1400,
        ))
        checks.append((
            f"Stripe transfer currency = 'cad' (got {transfer_obj.currency!r})",
            transfer_obj.currency.lower() == "cad",
        ))
        checks.append((
            f"Stripe transfer destination = internal test connect id "
            f"(got {transfer_obj.destination!r})",
            transfer_obj.destination == INTERNAL_TEST_CONNECT_ID,
        ))
        checks.append((
            f"Stripe transfer metadata.auction_id matches seeded auction",
            (transfer_obj.metadata or {}).get("auction_id") == auction_id,
        ))
        checks.append((
            "Stripe transfer metadata.type == 'escrow_release'",
            (transfer_obj.metadata or {}).get("type") == "escrow_release",
        ))
        checks.append((
            "Stripe transfer metadata.pickup_code matches the code we used",
            (transfer_obj.metadata or {}).get("pickup_code") == pickup_code,
        ))

        # ── Verify BidVex-side row is updated ──
        row_after = await db.escrow_transactions.find_one({"auction_id": auction_id})
        checks.append((
            f"BidVex row escrow_status='released' (got {row_after.get('escrow_status')!r})",
            row_after.get("escrow_status") == "released",
        ))
        checks.append((
            f"BidVex row stripe_transfer_id == returned transfer_id",
            row_after.get("stripe_transfer_id") == transfer_id,
        ))
        checks.append((
            "BidVex row funds_released_at was stamped",
            row_after.get("funds_released_at") is not None,
        ))

        # ── SECOND call with SAME pickup code must NOT create a second transfer ──
        second_error = None
        try:
            await confirm_pickup(db, seller_id, auction_id, pickup_code)
        except Exception as exc:  # noqa: BLE001
            second_error = exc
        checks.append((
            f"2nd confirm-pickup with same code raises HTTPException "
            f"(got {type(second_error).__name__ if second_error else 'None'})",
            second_error is not None,
        ))
        if second_error is not None:
            # Should be 404 (escrow row now 'released' so the initial
            # find_one({escrow_status:'held'}) misses it).
            status_code = getattr(second_error, "status_code", None)
            checks.append((
                f"2nd confirm-pickup returned 404 not_found "
                f"(got status_code={status_code})",
                status_code == 404,
            ))

        # ── Verify Stripe side: ONLY ONE transfer exists with our metadata ──
        transfers_for_auction = _stripe_module.Transfer.list(
            limit=10,
            transfer_group=None,
        )
        matching = [
            t for t in transfers_for_auction.auto_paging_iter()
            if (t.metadata or {}).get("auction_id") == auction_id
        ]
        checks.append((
            f"Stripe side: exactly ONE transfer exists for auction_id "
            f"(got {len(matching)})",
            len(matching) == 1,
        ))

        # ── Also verify BidVex row is unchanged after the 2nd call ──
        row_final = await db.escrow_transactions.find_one({"auction_id": auction_id})
        checks.append((
            "BidVex row.stripe_transfer_id unchanged after blocked 2nd call",
            row_final.get("stripe_transfer_id") == transfer_id,
        ))

    finally:
        # Restore stripe api key
        try:
            _stripe_module.api_key = _original_key
        except Exception:
            pass

        # Clean up BidVex-side records (Stripe test transfers can't be
        # deleted — that's expected and does not affect prod).
        try:
            await _cleanup(db, PREFIX, seeded_ids)
            print(f"\n[iter463] ✓ cleaned up all BidVex-side seeded records")
            # Verify cleanup
            rem = await db.escrow_transactions.count_documents(
                {"auction_id": {"$regex": f"^{PREFIX}"}}
            )
            print(f"[iter463] escrow_transactions remaining with prefix: {rem}")
        except Exception as e:  # noqa: BLE001
            print(f"[iter463] cleanup warning: {e}")
        client_db.close()

    print("\n[iter463] === Summary ===")
    all_ok = True
    for label, ok in checks:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {label}")
        if not ok:
            all_ok = False
    if all_ok:
        print(f"\n[iter463] ✅ ALL {len(checks)} CONTROLLED PAYOUT CHECKS PASSED\n")
    else:
        print("\n[iter463] ❌ FAILURES ABOVE\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
