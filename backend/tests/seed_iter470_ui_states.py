"""
iter470 — Seed 5 removable escrow rows for the seller dashboard so we
can screenshot every payout-state badge in one panel.

Seller: testseller@bidvex.com (id=87b286ed-b40b-4bb6-943b-b62cdc31b8fd)

Rows seeded (all removable, prefixed `iter470ui-`):
  A. HELD          — escrow_transactions row, escrow_status=held (no payout)
  B. SENT          — transactions-only paid row + seller_payouts sent
  C. PENDING       — transactions-only paid row + seller_payouts pending
  D. FAILED        — transactions-only paid row + seller_payouts failed
  E. UNKNOWN       — transactions-only paid row + NO payout record

Cleanup helper is exposed via ``python … --cleanup``.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

BACKEND = Path("/app/backend")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # type: ignore
load_dotenv(BACKEND / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore

SELLER_ID = "87b286ed-b40b-4bb6-943b-b62cdc31b8fd"  # testseller@bidvex.com
PREFIX = "iter470ui-"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def seed(db):
    buyer_id = f"{PREFIX}buyer-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": buyer_id,
        "email": f"{PREFIX}buyer@test.example",
        "name": "iter470 UI buyer",
        "role": "user",
        "created_at": now_iso(),
        "iter470ui_seed": True,
    })

    # A. HELD
    a_id = f"{PREFIX}A-{uuid.uuid4().hex[:8]}"
    exp = datetime.now(timezone.utc) + timedelta(hours=36)
    await db.escrow_transactions.insert_one({
        "auction_id": a_id, "listing_id": a_id,
        "buyer_id": buyer_id, "seller_id": SELLER_ID,
        "hammer_price_cents": 5000, "total_charged_cents": 5500,
        "application_fee_cents": 250,
        "stripe_payment_intent_id": f"pi_{a_id}",
        "escrow_status": "held",
        "pickup_code": "BVX-UIHELD01",
        "pickup_code_expires_at": exp.isoformat(),
        "auto_release_scheduled_at": exp.isoformat(),
        "created_at": now_iso(), "updated_at": now_iso(),
        "item_type": "non_vehicle", "province": "QC",
    })
    await db.listings.update_one({"id": a_id}, {"$set": {
        "id": a_id, "title": "iter470 UI · A · HELD", "iter470ui_seed": True,
    }}, upsert=True)

    # Helper to seed a paid transactions-only row (no escrow row).
    async def _seed_tx(tag, amount, transfer_id=None, payout_status=None):
        listing_id = f"{PREFIX}{tag}-{uuid.uuid4().hex[:8]}"
        await db.transactions.insert_one({
            "id": str(uuid.uuid4()),
            "listing_id": listing_id, "pickup_code_listing_id": listing_id,
            "auction_id": listing_id,
            "listing_title": f"iter470 UI · {tag} · {payout_status or 'unknown'}",
            "buyer_id": buyer_id, "seller_id": SELLER_ID,
            "pickup_code_seller_id": SELLER_ID,
            "hammer_price": amount, "amount": amount,
            "payment_method": "stripe",
            "stripe_payment_intent": f"pi_{listing_id}",
            "status": "paid", "payment_confirmed": True,
            "commission_already_collected": True,
            "pickup_code": f"BVX-UI{tag}CONFIRMED",
            # Row is already pickup-confirmed so the dashboard renders
            # the payout state (not the held state) for the screenshot.
            "pickup_code_confirmed_at": now_iso(),
            "pickup_code_confirmed_by": SELLER_ID,
            "pickup_code_issued_at": now_iso(),
            "created_at": now_iso(),
            "iter470ui_seed": True,
        })
        await db.listings.update_one({"id": listing_id}, {"$set": {
            "id": listing_id, "title": f"iter470 UI · {tag}", "iter470ui_seed": True,
        }}, upsert=True)
        if payout_status:
            await db.seller_payouts.insert_one({
                "id": str(uuid.uuid4()),
                "section": "marketplace", "listing_id": listing_id,
                "listing_title": f"iter470 UI · {tag}",
                "seller_id": SELLER_ID, "amount": amount, "currency": "CAD",
                "status": payout_status, "stripe_transfer_id": transfer_id,
                "sent_at": now_iso() if payout_status == "sent" else None,
                "created_at": now_iso(),
            })
        return listing_id

    await _seed_tx("B", 42.00, transfer_id="tr_ui_iter470_B", payout_status="sent")
    await _seed_tx("C", 25.00, transfer_id=None, payout_status="pending")
    await _seed_tx("D", 30.00, transfer_id=None, payout_status="failed")
    await _seed_tx("E", 17.00, transfer_id=None, payout_status=None)  # UNKNOWN

    print("[iter470ui] seeded 5 rows (A held, B sent, C pending, D failed, E unknown)")


async def cleanup(db):
    coll_targets = [
        ("transactions", {"iter470ui_seed": True}),
        ("escrow_transactions", {"auction_id": {"$regex": f"^{PREFIX}"}}),
        ("listings", {"iter470ui_seed": True}),
        ("users", {"iter470ui_seed": True}),
        ("seller_payouts", {"listing_id": {"$regex": f"^{PREFIX}"}}),
        ("pending_payouts", {"listing_id": {"$regex": f"^{PREFIX}"}}),
        ("pickup_attempt_log", {"auction_id": {"$regex": f"^{PREFIX}"}}),
    ]
    removed = {}
    for coll, q in coll_targets:
        r = await db[coll].delete_many(q)
        removed[coll] = r.deleted_count
    print(f"[iter470ui] cleanup: {removed}")


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cleanup", action="store_true")
    args = parser.parse_args()

    client = AsyncIOMotorClient(os.environ["MONGO_URL"], tz_aware=True)
    db = client[os.environ["DB_NAME"]]

    if args.cleanup:
        await cleanup(db)
    else:
        await cleanup(db)  # start clean
        await seed(db)


if __name__ == "__main__":
    asyncio.run(main())
