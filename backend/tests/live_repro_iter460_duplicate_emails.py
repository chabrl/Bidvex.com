"""
iter460 STEP 1 — Reproduction of duplicate transactional settlement emails.

MANDATORY: reproduce the bug before changing any code.

Fixture (removable — `iter460-<uuid>` prefix on every doc):
  Multi-item lots auction with:
    Lot 1 (qty 1)  → Buyer A wins, hammer $100
    Lot 2 (qty 3)  → Buyer A wins, unit $7 × qty 3 = $21
    Lot 3 (qty 2)  → Buyer B wins, unit $50 × qty 2 = $100
    Lot 4          → NO WINNER (unsold)

Expected (BEFORE FIX):
  • Buyer A receives 2× `send_auction_won_email` (one per won lot) — DUP
  • Buyer A receives 2× `send_buyer_receipt_email` — one per lot receipt — DUP
  • Seller receives 3× `send_seller_auction_sold_email` (Lot 1 / 2 / 3) — DUP
  • Seller receives 3× `send_seller_statement_email` — DUP
  • Running `process_ended_auctions` a SECOND time inside 60s could re-send

We monkey-patch every email sender in the module registry to count calls
per (fn_name, to_email). No SendGrid calls are made.

After collecting the counts, we run `process_ended_auctions` a SECOND
time to confirm retry behavior.

Prints a JSON summary and exits 0 if the bug is reproduced (dup counts
> 1 for the relevant per-event emails), exit 1 if we cannot reproduce.
"""
from __future__ import annotations

import asyncio
import json
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

PREFIX = f"iter460-{uuid.uuid4().hex[:8]}"


def _fresh(kind: str) -> str:
    return f"{PREFIX}-{kind}-{uuid.uuid4().hex[:6]}"


# ─── Monkey-patch all senders to count calls without hitting SendGrid ─────
SEND_LOG: List[Dict[str, Any]] = []


def _install_email_counters():
    """Replace every settlement-related email sender with a counter."""
    import services.emails.email_marketplace as em
    import services.emails.email_system as es
    import services.emails.email_vehicles as ev

    async def _rec(fn_name, **kwargs):
        # Extract to_email robustly
        to_email = (
            kwargs.get("to_email")
            or kwargs.get("seller_email")
            or kwargs.get("buyer_email")
            or (kwargs.get("buyer") or {}).get("email")
            or (kwargs.get("seller") or {}).get("email")
            or "unknown"
        )
        SEND_LOG.append({"fn": fn_name, "to": to_email,
                         "kwargs_keys": list(kwargs.keys())})
        return {"success": True, "mocked": True}

    em.send_auction_won_email = lambda **kw: _rec("send_auction_won_email", **kw)
    em.send_auction_sold_email = lambda **kw: _rec("send_auction_sold_email", **kw)
    ev.send_seller_auction_sold_email = lambda **kw: _rec("send_seller_auction_sold_email", **kw)
    ev.send_seller_auction_no_bids_email = lambda **kw: _rec("send_seller_auction_no_bids_email", **kw)
    es.send_buyer_receipt_email = lambda **kw: _rec("send_buyer_receipt_email", **kw)
    es.send_seller_statement_email = lambda **kw: _rec("send_seller_statement_email", **kw)
    es.send_payment_link_email = lambda **kw: _rec("send_payment_link_email", **kw)
    es.send_payment_failed_email = lambda **kw: _rec("send_payment_failed_email", **kw)
    es.send_invoice_created_email = lambda **kw: _rec("send_invoice_created_email", **kw)


async def _seed(db, seller_id, buyer_a_id, buyer_b_id) -> str:
    """Seed a multi-item auction where the ends have already passed."""
    now_iso = datetime.now(timezone.utc).isoformat()
    past_iso = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()

    await db.users.insert_many([
        {"id": seller_id, "email": f"{seller_id}@example.test",
         "name": "Iter460 Seller", "full_name": "Iter460 Seller",
         "phone": "555-000-1", "province": "QC",
         "subscription_tier": "free", "account_type": "individual",
         "preferred_language": "en", "created_at": now_iso},
        {"id": buyer_a_id, "email": f"{buyer_a_id}@example.test",
         "name": "Iter460 BuyerA", "full_name": "Iter460 BuyerA",
         "phone": "555-000-2", "province": "QC",
         "subscription_tier": "free", "account_type": "individual",
         "preferred_language": "en", "created_at": now_iso},
        {"id": buyer_b_id, "email": f"{buyer_b_id}@example.test",
         "name": "Iter460 BuyerB", "full_name": "Iter460 BuyerB",
         "phone": "555-000-3", "province": "QC",
         "subscription_tier": "free", "account_type": "individual",
         "preferred_language": "en", "created_at": now_iso},
    ])

    auction_id = _fresh("auction")
    doc = {
        "id": auction_id,
        "title": f"Iter460 Repro Auction ({PREFIX})",
        "city": "Montréal", "region": "QC", "location_province": "QC",
        "seller_id": seller_id,
        "status": "active",     # scheduler filters on this
        "listing_type": "lots",
        "auction_type": "lots",
        "currency": "CAD",
        "auction_end_date": past_iso,
        "lots": [
            {"lot_number": 1, "title": "Lot 1 solo",
             "highest_bidder_id": buyer_a_id, "current_price": 100.0,
             "quantity": 1, "lot_end_time": past_iso},
            {"lot_number": 2, "title": "Lot 2 multi-qty",
             "highest_bidder_id": buyer_a_id, "current_price": 7.0,
             "quantity": 3, "multiply_hammer_by_quantity": True,
             "lot_end_time": past_iso},
            {"lot_number": 3, "title": "Lot 3 buyerB",
             "highest_bidder_id": buyer_b_id, "current_price": 50.0,
             "quantity": 2, "multiply_hammer_by_quantity": True,
             "lot_end_time": past_iso},
            {"lot_number": 4, "title": "Lot 4 unsold",
             "highest_bidder_id": None, "current_price": 0.0,
             "quantity": 1, "lot_end_time": past_iso},
        ],
        "created_at": now_iso, "updated_at": now_iso,
    }
    await db.multi_item_listings.insert_one(doc)
    return auction_id


async def _cleanup(db, auction_id, user_ids):
    await db.users.delete_many({"id": {"$in": user_ids}})
    await db.multi_item_listings.delete_many({"id": auction_id})
    await db.paddle_numbers.delete_many({"auction_id": auction_id})
    await db.invoices.delete_many({"auction_id": auction_id})
    await db.receipts.delete_many({"listing_id": auction_id})
    await db.transactions.delete_many({"listing_id": auction_id})
    await db.notifications.delete_many({"data.listing_id": auction_id})
    await db.pending_payouts.delete_many({"listing_id": auction_id})
    # iter460 dedup ledger (may not exist yet in repro run)
    try:
        await db.settlement_email_dispatches.delete_many({"auction_id": auction_id})
    except Exception:
        pass


async def main():
    client_db = AsyncIOMotorClient(MONGO_URL)
    db = client_db[DB_NAME]

    seller_id = _fresh("seller")
    buyer_a_id = _fresh("buyerA")
    buyer_b_id = _fresh("buyerB")
    all_users = [seller_id, buyer_a_id, buyer_b_id]

    print(f"\n[iter460-repro] Prefix: {PREFIX}\n")

    try:
        auction_id = await _seed(db, seller_id, buyer_a_id, buyer_b_id)
        print(f"[iter460-repro] ✓ seeded auction {auction_id} with 4 lots\n")

        _install_email_counters()

        # First scheduler tick — inject DB into route module and run.
        from routes import auctions as auctions_module
        auctions_module.set_db(db)
        # Also inject into routes.messages so create_auction_won_conversation works
        try:
            from routes import messages as messages_module
            if hasattr(messages_module, "set_db"):
                messages_module.set_db(db)
        except Exception:
            pass

        await auctions_module.process_ended_auctions()
        print(f"[iter460-repro] ✓ First scheduler tick complete — "
              f"{len(SEND_LOG)} email calls recorded\n")

        # Snapshot after tick 1.
        tick1_log = list(SEND_LOG)

        # Second tick — simulate scheduler retry (60s later). The auction
        # status is now 'ended' so the query {"status": "active"} SHOULD
        # skip it — but let's confirm and also check what happens if the
        # doc is somehow reset (or if per-lot emails leak elsewhere).
        # We also directly simulate a "duplicated settlement trigger" by
        # calling finalize_auction_payment on the same lot twice.
        SEND_LOG.clear()
        await auctions_module.process_ended_auctions()
        tick2_log = list(SEND_LOG)
        print(f"[iter460-repro] ✓ Second scheduler tick complete — "
              f"{len(SEND_LOG)} email calls recorded (should be 0 if idempotent)\n")

        # Duplicated finalize call (webhook-retry simulation) — force a
        # re-entry by resetting the top-level status back to 'ended' and
        # calling finalize_auction_payment for lot 1 a second time.
        SEND_LOG.clear()
        try:
            from services.payment_collection import finalize_auction_payment
            listing_doc = await db.multi_item_listings.find_one({"id": auction_id})
            lot1 = next(l for l in listing_doc["lots"] if l["lot_number"] == 1)
            synthetic_settlement = {
                "buyer_charge": {"stripe_pi": "pi_repro_lot1"},
                "fee_breakdown": {
                    "buyer_premium": 5.0, "buyer_taxes": 0.75,
                    "buyer_stripe_fee": 0.44, "buyer_total_charged": 106.19,
                    "seller_commission": 4.0, "seller_payout": 96.0,
                },
                "warnings": [],
            }
            for _ in range(2):
                await finalize_auction_payment(
                    db,
                    listing={**listing_doc, "winner_user_id": buyer_a_id},
                    collection="multi_item_listings",
                    settlement=synthetic_settlement,
                    section="lots",
                    lot_number=1,
                    listing_title="Iter460 Repro Auction — Lot 1",
                    hammer_override=100.0,
                    winner_override=buyer_a_id,
                )
        except Exception as e:
            print(f"[iter460-repro] finalize retry probe error: {e}")

        finalize_retry_log = list(SEND_LOG)

        # Aggregate counts by (fn, to_email)
        def _tally(log):
            counts = defaultdict(int)
            for e in log:
                counts[(e["fn"], e["to"])] += 1
            return dict(counts)

        tally1 = _tally(tick1_log)
        tally2 = _tally(tick2_log)
        tally_retry = _tally(finalize_retry_log)

        print("[iter460-repro] === TICK 1 (multi-lot fan-out) ===")
        for k, v in sorted(tally1.items()):
            marker = " ⚠ DUP" if v > 1 else ""
            print(f"  {v:>2}x  {k[0]:<40} → {k[1]}{marker}")

        print("\n[iter460-repro] === TICK 2 (scheduler retry — expect 0) ===")
        for k, v in sorted(tally2.items()):
            print(f"  {v:>2}x  {k[0]:<40} → {k[1]}")

        print("\n[iter460-repro] === FINALIZE RETRY (webhook re-drive) ===")
        for k, v in sorted(tally_retry.items()):
            marker = " ⚠ DUP" if v > 1 else ""
            print(f"  {v:>2}x  {k[0]:<40} → {k[1]}{marker}")

        # Verdict: bug reproduced if buyer A got > 1 auction_won emails OR
        # > 1 buyer_receipt emails on tick 1.
        buyer_a_email = f"{buyer_a_id}@example.test"
        seller_email  = f"{seller_id}@example.test"
        dup_hits = []
        if tally1.get(("send_auction_won_email", buyer_a_email), 0) > 1:
            dup_hits.append("Buyer A got multiple auction_won emails")
        if tally1.get(("send_buyer_receipt_email", buyer_a_email), 0) > 1:
            dup_hits.append("Buyer A got multiple buyer_receipt emails")
        if tally1.get(("send_seller_auction_sold_email", seller_email), 0) > 1:
            dup_hits.append("Seller got multiple seller_auction_sold emails")
        if tally1.get(("send_seller_statement_email", seller_email), 0) > 1:
            dup_hits.append("Seller got multiple seller_statement emails")
        retry_dup = any(v > 1 for v in tally_retry.values())
        if retry_dup:
            dup_hits.append("Finalize retry sent duplicate emails")

        print("\n[iter460-repro] === VERDICT ===")
        if dup_hits:
            print("  ✓ BUG REPRODUCED. Duplicate emails:")
            for h in dup_hits:
                print(f"    - {h}")
        else:
            print("  ✗ Could not reproduce — no duplicates detected.")

        # Machine-readable summary
        summary = {
            "prefix": PREFIX,
            "auction_id": auction_id,
            "tick1": tally1,
            "tick2": tally2,
            "finalize_retry": tally_retry,
            "reproduced": bool(dup_hits),
            "duplicate_hits": dup_hits,
        }
        print("\n[iter460-repro] JSON:")
        print(json.dumps({str(k): v for k, v in summary.items() if k not in ("tick1", "tick2", "finalize_retry")}, indent=2, default=str))
        print("Tick1 tally:", {f"{k[0]}:{k[1]}": v for k, v in tally1.items()})
        print("Tick2 tally:", {f"{k[0]}:{k[1]}": v for k, v in tally2.items()})
        print("Retry tally:", {f"{k[0]}:{k[1]}": v for k, v in tally_retry.items()})

    finally:
        try:
            await _cleanup(db, auction_id if 'auction_id' in locals() else None, all_users)
            print("\n[iter460-repro] ✓ cleaned up seeded fixture")
        except Exception as e:
            print(f"[iter460-repro] cleanup warning: {e}")
        client_db.close()


if __name__ == "__main__":
    asyncio.run(main())
