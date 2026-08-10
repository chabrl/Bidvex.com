"""
iter460 — Full acceptance test suite for duplicate settlement-email fix.

Covers every scenario mandated by the user:
  1. A duplicated settlement trigger (same scheduler run twice back-to-back)
  2. A retry (scheduler tick #2 finds the auction already ended)
  3. Multiple lots for one buyer in the same auction (aggregation)
  4. Two different buyers on the same auction (each gets exactly ONE email)
  5. Two separate settlements (each fires its own emails independently)
  6. Retried webhook re-drive of finalize_auction_payment for a settled lot

Uses in-process monkey-patched email senders + direct call to
`process_ended_auctions` after `set_db()`. Cleans up all seeded docs.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from collections import defaultdict
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

PREFIX = f"iter460acc-{uuid.uuid4().hex[:8]}"


SEND_LOG: List[Dict[str, Any]] = []


def _install_email_counters():
    import services.emails.email_marketplace as em
    import services.emails.email_system as es
    import services.emails.email_vehicles as ev

    async def _rec(fn, **kw):
        to = (kw.get("to_email") or kw.get("seller_email") or kw.get("buyer_email")
              or (kw.get("buyer") or {}).get("email") or (kw.get("seller") or {}).get("email")
              or "unknown")
        SEND_LOG.append({"fn": fn, "to": to})
        return {"mocked": True}

    em.send_auction_won_email = lambda **kw: _rec("send_auction_won_email", **kw)
    em.send_auction_sold_email = lambda **kw: _rec("send_auction_sold_email", **kw)
    ev.send_seller_auction_sold_email = lambda **kw: _rec("send_seller_auction_sold_email", **kw)
    ev.send_seller_auction_no_bids_email = lambda **kw: _rec("send_seller_auction_no_bids_email", **kw)
    es.send_buyer_receipt_email = lambda **kw: _rec("send_buyer_receipt_email", **kw)
    es.send_seller_statement_email = lambda **kw: _rec("send_seller_statement_email", **kw)
    es.send_payment_link_email = lambda **kw: _rec("send_payment_link_email", **kw)
    es.send_payment_failed_email = lambda **kw: _rec("send_payment_failed_email", **kw)
    es.send_invoice_created_email = lambda **kw: _rec("send_invoice_created_email", **kw)


def _tally(log):
    counts = defaultdict(int)
    for e in log:
        counts[(e["fn"], e["to"])] += 1
    return dict(counts)


def _fresh(kind: str) -> str:
    return f"{PREFIX}-{kind}-{uuid.uuid4().hex[:6]}"


async def _seed_multi_lot_auction(db, seller_id, buyer_a_id, buyer_b_id) -> str:
    now_iso = datetime.now(timezone.utc).isoformat()
    past_iso = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()

    for uid, name in [(seller_id, "Seller"), (buyer_a_id, "BuyerA"), (buyer_b_id, "BuyerB")]:
        await db.users.insert_one({
            "id": uid, "email": f"{uid}@example.test",
            "name": f"iter460 {name}", "full_name": f"iter460 {name}",
            "phone": "555-000", "province": "QC",
            "subscription_tier": "free", "account_type": "individual",
            "preferred_language": "en", "created_at": now_iso,
        })

    auction_id = _fresh("auction")
    await db.multi_item_listings.insert_one({
        "id": auction_id,
        "title": f"iter460 Acceptance Auction ({PREFIX})",
        "city": "Montréal", "region": "QC", "location_province": "QC",
        "seller_id": seller_id, "status": "active",
        "listing_type": "lots", "auction_type": "lots",
        "currency": "CAD", "auction_end_date": past_iso,
        "lots": [
            {"lot_number": 1, "title": "Lot 1",
             "highest_bidder_id": buyer_a_id, "current_price": 100.0,
             "quantity": 1, "lot_end_time": past_iso},
            {"lot_number": 2, "title": "Lot 2",
             "highest_bidder_id": buyer_a_id, "current_price": 7.0,
             "quantity": 3, "multiply_hammer_by_quantity": True,
             "lot_end_time": past_iso},
            {"lot_number": 3, "title": "Lot 3",
             "highest_bidder_id": buyer_b_id, "current_price": 50.0,
             "quantity": 2, "multiply_hammer_by_quantity": True,
             "lot_end_time": past_iso},
            {"lot_number": 4, "title": "Lot 4 unsold",
             "highest_bidder_id": None, "current_price": 0.0,
             "quantity": 1, "lot_end_time": past_iso},
        ],
        "created_at": now_iso, "updated_at": now_iso,
    })
    return auction_id


async def _cleanup(db, prefix: str):
    q = {"$regex": f"^{prefix}"}
    await db.users.delete_many({"id": q})
    await db.multi_item_listings.delete_many({"id": q})
    await db.paddle_numbers.delete_many({"auction_id": q})
    await db.invoices.delete_many({"auction_id": q})
    await db.receipts.delete_many({"listing_id": q})
    await db.transactions.delete_many({"listing_id": q})
    await db.notifications.delete_many({"data.listing_id": q})
    await db.pending_payouts.delete_many({"listing_id": q})
    await db.settlement_email_dispatches.delete_many({"auction_id": q})


async def main():
    client_db = AsyncIOMotorClient(MONGO_URL)
    db = client_db[DB_NAME]

    print(f"\n[iter460-acc] Prefix: {PREFIX}\n")

    checks: List[tuple] = []

    try:
        from routes import auctions as auctions_module
        auctions_module.set_db(db)
        _install_email_counters()

        # ── Scenario A: multi-lot buyer + two different buyers on same auction ──
        seller1 = _fresh("seller1")
        buyer_a = _fresh("buyerA")
        buyer_b = _fresh("buyerB")
        auction1 = await _seed_multi_lot_auction(db, seller1, buyer_a, buyer_b)

        SEND_LOG.clear()
        await auctions_module.process_ended_auctions()
        tally_a = _tally(SEND_LOG)

        b_a_email = f"{buyer_a}@example.test"
        b_b_email = f"{buyer_b}@example.test"
        s1_email  = f"{seller1}@example.test"

        # (3) Multi-lot buyer: Buyer A won 2 lots → gets EXACTLY 1 auction_won
        checks.append(("Scenario 3 — Buyer A (multi-lot): exactly 1 auction_won email",
                       tally_a.get(("send_auction_won_email", b_a_email)) == 1))
        # (4) Two different buyers: Buyer B (1 lot) also gets EXACTLY 1
        checks.append(("Scenario 4 — Buyer B (single-lot): exactly 1 auction_won email",
                       tally_a.get(("send_auction_won_email", b_b_email)) == 1))
        # Seller receives EXACTLY 1 seller_sold email covering 3 sold lots
        checks.append(("Scenario 3/4 — Seller: exactly 1 seller_sold summary email",
                       tally_a.get(("send_seller_auction_sold_email", s1_email)) == 1))
        # Buyer A wins 2 lots → payment_link is per-lot but must be gated to 1
        checks.append(("Scenario 3 — Buyer A: exactly 1 payment_link email",
                       tally_a.get(("send_payment_link_email", b_a_email)) == 1))
        # Buyer B: 1 payment_link
        checks.append(("Scenario 4 — Buyer B: exactly 1 payment_link email",
                       tally_a.get(("send_payment_link_email", b_b_email)) == 1))
        # Unsold lot 4 must NOT fire an auction_won email to anyone
        checks.append(("Unsold lot 4: no auction_won emails fired for missing bidder",
                       sum(1 for k in tally_a if k[0] == "send_auction_won_email") == 2))

        # ── Scenario 1 + 2: Duplicated trigger + scheduler retry (same auction) ──
        SEND_LOG.clear()
        await auctions_module.process_ended_auctions()  # tick 2 — retry
        tally_retry = _tally(SEND_LOG)
        # (1) Duplicated trigger — ledger blocks all sends
        checks.append(("Scenario 1 — Duplicated trigger: zero re-sends",
                       len(tally_retry) == 0))
        # (2) Retry: same as above (status flip guard also helps)
        checks.append(("Scenario 2 — Scheduler retry: zero re-sends",
                       len(tally_retry) == 0))

        # Third trigger for extra safety
        SEND_LOG.clear()
        await auctions_module.process_ended_auctions()
        tally_third = _tally(SEND_LOG)
        checks.append(("Third trigger: still zero re-sends",
                       len(tally_third) == 0))

        # ── Scenario 6: finalize_auction_payment webhook re-drive ──
        from services.payment_collection import finalize_auction_payment
        listing_doc = await db.multi_item_listings.find_one({"id": auction1})
        SEND_LOG.clear()
        synthetic_settlement = {
            "buyer_charge": {"stripe_pi": "pi_repro_acc_lot1"},
            "fee_breakdown": {
                "buyer_premium": 5.0, "buyer_taxes": 0.75,
                "buyer_stripe_fee": 0.44, "buyer_total_charged": 106.19,
                "seller_commission": 4.0, "seller_payout": 96.0,
            },
            "warnings": [],
        }
        for _ in range(3):  # 3× the SAME event
            await finalize_auction_payment(
                db,
                listing={**listing_doc, "winner_user_id": buyer_a},
                collection="multi_item_listings",
                settlement=synthetic_settlement,
                section="lots",
                lot_number=1,
                listing_title="iter460 Acceptance — Lot 1",
                hammer_override=100.0,
                winner_override=buyer_a,
            )
        tally_finalize = _tally(SEND_LOG)
        # For lot 1: previous receipt was created earlier (if payment succeeded)
        # OR none if payment_link path fired. In either case, 3 calls must not
        # produce > 1 buyer_receipt + 1 seller_statement emails.
        checks.append(("Scenario 6 — Finalize re-drive: ≤ 1 buyer_receipt email",
                       tally_finalize.get(("send_buyer_receipt_email", b_a_email), 0) <= 1))
        checks.append(("Scenario 6 — Finalize re-drive: ≤ 1 seller_statement email",
                       tally_finalize.get(("send_seller_statement_email", s1_email), 0) <= 1))

        # ── Scenario 5: two SEPARATE settlements (independent) ──
        seller2 = _fresh("seller2")
        buyer_c = _fresh("buyerC")
        buyer_d = _fresh("buyerD")
        auction2 = await _seed_multi_lot_auction(db, seller2, buyer_c, buyer_d)

        SEND_LOG.clear()
        await auctions_module.process_ended_auctions()
        tally_b = _tally(SEND_LOG)

        c_email = f"{buyer_c}@example.test"
        d_email = f"{buyer_d}@example.test"
        s2_email = f"{seller2}@example.test"

        # (5) Each new settlement fires its own emails — independence.
        checks.append(("Scenario 5 — Auction 2 Buyer C: exactly 1 auction_won email",
                       tally_b.get(("send_auction_won_email", c_email)) == 1))
        checks.append(("Scenario 5 — Auction 2 Buyer D: exactly 1 auction_won email",
                       tally_b.get(("send_auction_won_email", d_email)) == 1))
        checks.append(("Scenario 5 — Auction 2 Seller: exactly 1 seller_sold email",
                       tally_b.get(("send_seller_auction_sold_email", s2_email)) == 1))
        # Auction 1's buyers must NOT get emails from auction 2's settlement.
        checks.append(("Scenario 5 — Auction 1 buyers untouched by Auction 2 close",
                       tally_b.get(("send_auction_won_email", b_a_email), 0) == 0
                       and tally_b.get(("send_auction_won_email", b_b_email), 0) == 0))

        # ── Ledger contains correct rows ──
        # Two auctions × (2 buyers "auction_won" + 1 seller "seller_sold") = 6 dispatches minimum
        dispatch_count = await db.settlement_email_dispatches.count_documents(
            {"auction_id": {"$in": [auction1, auction2]}}
        )
        checks.append((
            f"Ledger recorded ≥ 6 dispatch rows across the 2 auctions (got {dispatch_count})",
            dispatch_count >= 6,
        ))

    finally:
        try:
            await _cleanup(db, PREFIX)
            print("\n[iter460-acc] ✓ cleaned up all seeded fixtures")
        except Exception as e:
            print(f"[iter460-acc] cleanup warning: {e}")
        client_db.close()

    print("\n[iter460-acc] === Summary ===")
    all_ok = True
    for label, ok in checks:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {label}")
        if not ok:
            all_ok = False
    if all_ok:
        print(f"\n[iter460-acc] ✅ ALL {len(checks)} ACCEPTANCE CHECKS PASSED\n")
    else:
        print("\n[iter460-acc] ❌ FAILURES ABOVE\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
