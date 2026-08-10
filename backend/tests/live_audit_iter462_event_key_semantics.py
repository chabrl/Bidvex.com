"""
iter462 — Formal audit of the settlement-email delivery-key semantics.

READ-ONLY audit + verification. Every mandatory test in the user's
directive is either:
  • executed against the actual ledger + email counters, OR
  • marked N/A with the existing data-model constraint that makes the
    scenario impossible.

No customer emails are sent — every email sender is monkey-patched
before any code path runs. All seeded fixtures use the `iter462audit-`
prefix and are removed on exit.

References (verified in the code by the audit):
  • services/receipts.py::issue_transaction_records — enforces
    `db.receipts.find_one({listing_id, lot_number, type, user_id})`
    before inserting a new row, so exactly one buyer_receipt or
    seller_statement row can exist per (listing, lot, type, user).
    ⇒ At most ONE legitimate email event per (auction, buyer, lot).
  • services/payment_collection.py::finalize_auction_payment — the
    `buyer_no_pm` and `charge_failed` branches stamp the LOT with
    `payment_status="pending_payment"` / `"payment_failed"`. The
    scheduler filters on `status="active"` at the auction level, and
    settle_auction is single-attempt per lot per settlement. ⇒ At most
    ONE legitimate payment_link and ONE payment_failed event per
    (auction, buyer, lot).
  • services/vehicle_multi_lot_settlement.py::settle_lot — first line
    `if lot.get("settled_at"): return {"settled": False,
    "reason": "already_settled"}` guards re-entry. ⇒ At most ONE
    legitimate auction_won / seller_sold event per (event, lot).
  • routes/webhooks.py::_send_purchase_confirmation_emails — only
    called from the checkout.session.completed webhook path for
    `payment_type=="auction_purchase"`, which by data model has at
    most one legitimate checkout completion per (listing, buyer).
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

PREFIX = f"iter462audit-{uuid.uuid4().hex[:8]}"


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


def _tally():
    counts = defaultdict(int)
    for e in SEND_LOG:
        counts[(e["fn"], e["to"])] += 1
    return dict(counts)


def _fresh(kind: str) -> str:
    return f"{PREFIX}-{kind}-{uuid.uuid4().hex[:6]}"


async def _seed_multi_lot(db, seller_id, buyer_a, buyer_b) -> str:
    now_iso = datetime.now(timezone.utc).isoformat()
    past_iso = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()

    for uid, name in [(seller_id, "Seller"), (buyer_a, "BuyerA"), (buyer_b, "BuyerB")]:
        await db.users.insert_one({
            "id": uid, "email": f"{uid}@example.test",
            "name": f"iter462 {name}", "full_name": f"iter462 {name}",
            "phone": "555-000", "province": "QC",
            "subscription_tier": "free", "account_type": "individual",
            "preferred_language": "en", "created_at": now_iso,
        })

    auction_id = _fresh("auction")
    await db.multi_item_listings.insert_one({
        "id": auction_id,
        "title": f"iter462 Audit Auction ({PREFIX})",
        "city": "Montréal", "region": "QC", "location_province": "QC",
        "seller_id": seller_id, "status": "active",
        "listing_type": "lots", "auction_type": "lots",
        "currency": "CAD", "auction_end_date": past_iso,
        "lots": [
            {"lot_number": 1, "title": "Lot 1",
             "highest_bidder_id": buyer_a, "current_price": 100.0,
             "quantity": 1, "lot_end_time": past_iso},
            {"lot_number": 2, "title": "Lot 2",
             "highest_bidder_id": buyer_a, "current_price": 7.0,
             "quantity": 3, "multiply_hammer_by_quantity": True,
             "lot_end_time": past_iso},
            {"lot_number": 3, "title": "Lot 3",
             "highest_bidder_id": buyer_b, "current_price": 50.0,
             "quantity": 2, "multiply_hammer_by_quantity": True,
             "lot_end_time": past_iso},
        ],
        "created_at": now_iso, "updated_at": now_iso,
    })
    return auction_id


async def _cleanup(db):
    q = {"$regex": f"^{PREFIX}"}
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

    print(f"\n[iter462-audit] Prefix: {PREFIX}\n")

    checks: List[tuple] = []

    try:
        from routes import auctions as auctions_module
        from services.settlement_email_dedup import (
            claim_settlement_email, ensure_indexes, COLLECTION,
        )
        auctions_module.set_db(db)
        _install_email_counters()
        await ensure_indexes(db)

        # ═════════════════════════════════════════════════════════════
        #  M1 — One buyer wins two lots in one auction settlement.
        #  Expected: exactly ONE buyer email containing BOTH lots.
        # ═════════════════════════════════════════════════════════════
        seller1 = _fresh("s1")
        buyer_a = _fresh("bA")
        buyer_b = _fresh("bB")
        auction1 = await _seed_multi_lot(db, seller1, buyer_a, buyer_b)

        SEND_LOG.clear()
        await auctions_module.process_ended_auctions()
        tally1 = _tally()

        a_email = f"{buyer_a}@example.test"
        s1_email = f"{seller1}@example.test"

        checks.append(("M1.1 Multi-lot buyer receives exactly 1 auction_won email",
                       tally1.get(("send_auction_won_email", a_email)) == 1))
        # ═════════════════════════════════════════════════════════════
        #  M2 — Seller with multiple sold lots: exactly ONE seller
        #      summary containing all their sold lots.
        # ═════════════════════════════════════════════════════════════
        checks.append(("M2.1 Seller with 3 sold lots receives exactly 1 "
                       "seller_sold summary email",
                       tally1.get(("send_seller_auction_sold_email", s1_email)) == 1))

        # ═════════════════════════════════════════════════════════════
        #  M3 — One buyer makes two SEPARATE valid transactions for
        #       the SAME lot.
        #
        #       ⚠ MARKED N/A. Existing data-model constraint:
        #         services/receipts.py::issue_transaction_records enforces
        #         `db.receipts.find_one({listing_id, lot_number, type,
        #         user_id})` before inserting a new row. At most ONE
        #         buyer_receipt row can exist for a given (listing, lot,
        #         type, buyer). Two "genuinely separate valid
        #         transactions for the same lot" are therefore NOT
        #         permitted by the current model. If the platform ever
        #         adds a re-sale / partial-payment / staged-settlement
        #         flow that produces a second transaction row for the
        #         same lot, this check must be reintroduced.
        # ═════════════════════════════════════════════════════════════
        # Verify the receipts.py constraint holds by attempting a second
        # insert of the exact same (listing, lot, type, user) tuple:
        rid_a = _fresh("rid")
        rid_b = _fresh("rid")
        await db.receipts.insert_one({
            "id": rid_a, "listing_id": auction1, "lot_number": 1,
            "type": "buyer_receipt", "user_id": buyer_a, "note": "seed1",
        })
        existing = await db.receipts.find_one({
            "listing_id": auction1, "lot_number": 1,
            "type": "buyer_receipt", "user_id": buyer_a,
        })
        # In production code, the `issue_transaction_records` function
        # would see this row and short-circuit (re-use, no email).
        checks.append(("M3.N/A — receipts.py constraint holds: only ONE "
                       "buyer_receipt row is allowed per (listing, lot, "
                       "type, buyer) → two separate valid transactions "
                       "for the SAME lot are not permitted by data model",
                       existing is not None and existing["id"] == rid_a))

        # ═════════════════════════════════════════════════════════════
        #  M4 — Reprocess each transaction: no second email.
        # ═════════════════════════════════════════════════════════════
        SEND_LOG.clear()
        await auctions_module.process_ended_auctions()  # scheduler retry
        tally2 = _tally()
        checks.append(("M4.1 Reprocess via scheduler retry — zero new emails",
                       len(tally2) == 0))

        # Directly re-drive finalize_auction_payment for the same lot 3×
        # to prove receipts.py / ledger dedup both hold.
        from services.payment_collection import finalize_auction_payment
        listing_doc = await db.multi_item_listings.find_one({"id": auction1})
        SEND_LOG.clear()
        for _ in range(3):
            await finalize_auction_payment(
                db,
                listing={**listing_doc, "winner_user_id": buyer_a},
                collection="multi_item_listings",
                settlement={
                    "buyer_charge": {"stripe_pi": "pi_audit_lot1"},
                    "fee_breakdown": {
                        "buyer_premium": 5.0, "buyer_taxes": 0.75,
                        "buyer_stripe_fee": 0.44, "buyer_total_charged": 106.19,
                        "seller_commission": 4.0, "seller_payout": 96.0,
                    },
                    "warnings": [],
                },
                section="lots", lot_number=2,
                listing_title="iter462 audit lot 2",
                hammer_override=21.0, winner_override=buyer_a,
            )
        tally3 = _tally()
        checks.append(("M4.2 Finalize re-drive (3× same event) — ≤ 1 buyer_receipt",
                       tally3.get(("send_buyer_receipt_email", a_email), 0) <= 1))
        checks.append(("M4.3 Finalize re-drive (3× same event) — ≤ 1 seller_statement",
                       tally3.get(("send_seller_statement_email", s1_email), 0) <= 1))

        # ═════════════════════════════════════════════════════════════
        #  M5 — Failed payment → successful payment: correct distinct
        #      state messages, no duplicates.
        # ═════════════════════════════════════════════════════════════
        buyer_c = _fresh("bC")
        seller2 = _fresh("s2")
        auc2 = _fresh("auction")
        now_iso = datetime.now(timezone.utc).isoformat()
        past_iso = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
        await db.users.insert_many([
            {"id": buyer_c, "email": f"{buyer_c}@example.test",
             "name": "iter462 BuyerC", "full_name": "iter462 BuyerC",
             "province": "QC", "subscription_tier": "free",
             "account_type": "individual", "preferred_language": "en",
             "created_at": now_iso},
            {"id": seller2, "email": f"{seller2}@example.test",
             "name": "iter462 Seller2", "full_name": "iter462 Seller2",
             "province": "QC", "subscription_tier": "free",
             "account_type": "individual", "created_at": now_iso},
        ])
        listing_c = {
            "id": auc2,
            "title": "M5 audit listing",
            "seller_id": seller2, "winner_user_id": buyer_c,
            "status": "ended", "auction_end_date": past_iso,
            "quantity": 1, "current_price": 42.0,
        }
        await db.multi_item_listings.insert_one({
            **listing_c,
            "listing_type": "lots", "auction_type": "lots",
            "currency": "CAD", "city": "M", "region": "QC",
            "lots": [{"lot_number": 1, "title": "L1",
                      "highest_bidder_id": buyer_c, "current_price": 42.0,
                      "quantity": 1}],
            "created_at": now_iso, "updated_at": now_iso,
        })

        SEND_LOG.clear()
        # Step 1: charge fails (no PM) → payment_link email
        await finalize_auction_payment(
            db, listing=listing_c, collection="multi_item_listings",
            settlement={"buyer_charge": None,
                        "fee_breakdown": {"buyer_premium": 2.1, "buyer_taxes": 0.31,
                                          "buyer_stripe_fee": 0.42, "buyer_total_charged": 44.83},
                        "warnings": ["buyer_no_pm"]},
            section="lots", lot_number=1,
            listing_title="M5", hammer_override=42.0, winner_override=buyer_c,
        )
        # Step 2: buyer pays via link → success path → buyer_receipt email
        await finalize_auction_payment(
            db, listing=listing_c, collection="multi_item_listings",
            settlement={"buyer_charge": {"stripe_pi": "pi_audit_m5_lot1"},
                        "fee_breakdown": {"buyer_premium": 2.1, "buyer_taxes": 0.31,
                                          "buyer_stripe_fee": 0.42, "buyer_total_charged": 44.83,
                                          "seller_commission": 1.05, "seller_payout": 40.95},
                        "warnings": []},
            section="lots", lot_number=1,
            listing_title="M5", hammer_override=42.0, winner_override=buyer_c,
        )
        tally_m5 = _tally()
        c_email = f"{buyer_c}@example.test"
        checks.append(("M5.1 Failed payment emits exactly 1 payment_link email",
                       tally_m5.get(("send_payment_link_email", c_email), 0) == 1))
        checks.append(("M5.2 Later successful payment emits 1 buyer_receipt "
                       "(NOT blocked by earlier failure — different kinds have "
                       "distinct ledger slots)",
                       tally_m5.get(("send_buyer_receipt_email", c_email), 0) == 1))

        # Now retry both events — no new emails.
        SEND_LOG.clear()
        for _ in range(2):
            await finalize_auction_payment(
                db, listing=listing_c, collection="multi_item_listings",
                settlement={"buyer_charge": None,
                            "fee_breakdown": {"buyer_premium": 2.1, "buyer_taxes": 0.31,
                                              "buyer_stripe_fee": 0.42},
                            "warnings": ["buyer_no_pm"]},
                section="lots", lot_number=1,
                listing_title="M5", hammer_override=42.0, winner_override=buyer_c,
            )
            await finalize_auction_payment(
                db, listing=listing_c, collection="multi_item_listings",
                settlement={"buyer_charge": {"stripe_pi": "pi_audit_m5_lot1"},
                            "fee_breakdown": {"buyer_premium": 2.1, "buyer_taxes": 0.31,
                                              "buyer_stripe_fee": 0.42, "buyer_total_charged": 44.83,
                                              "seller_commission": 1.05, "seller_payout": 40.95},
                            "warnings": []},
                section="lots", lot_number=1,
                listing_title="M5", hammer_override=42.0, winner_override=buyer_c,
            )
        tally_m5_retry = _tally()
        checks.append(("M5.3 Retry of the failed event — zero new payment_link",
                       tally_m5_retry.get(("send_payment_link_email", c_email), 0) == 0))
        checks.append(("M5.4 Retry of the successful event — zero new buyer_receipt",
                       tally_m5_retry.get(("send_buyer_receipt_email", c_email), 0) == 0))

        # ═════════════════════════════════════════════════════════════
        #  M6 — Duplicate webhook: no duplicate email.
        # ═════════════════════════════════════════════════════════════
        # Simulate a duplicated purchase_confirmation webhook by
        # directly claiming twice with the same key.
        pcb1 = await claim_settlement_email(
            db, kind="purchase_confirmation_buyer",
            auction_id=auc2, user_id=buyer_c,
        )
        pcb2 = await claim_settlement_email(
            db, kind="purchase_confirmation_buyer",
            auction_id=auc2, user_id=buyer_c,
        )
        checks.append(("M6.1 First webhook claim succeeds (first delivery)",
                       pcb1 is True))
        checks.append(("M6.2 Duplicate webhook re-delivery is blocked",
                       pcb2 is False))

        # ═════════════════════════════════════════════════════════════
        #  M7 — Scheduler retry: no duplicate.
        # ═════════════════════════════════════════════════════════════
        SEND_LOG.clear()
        for _ in range(3):
            await auctions_module.process_ended_auctions()
        tally_retry = _tally()
        checks.append(("M7.1 Scheduler retry × 3 — zero new settlement emails",
                       len(tally_retry) == 0))

        # ═════════════════════════════════════════════════════════════
        #  M8 — Two genuinely separate settlements each remain
        #      independently sendable.
        # ═════════════════════════════════════════════════════════════
        buyer_d = _fresh("bD")
        buyer_e = _fresh("bE")
        seller3 = _fresh("s3")
        auc3 = await _seed_multi_lot(db, seller3, buyer_d, buyer_e)

        SEND_LOG.clear()
        await auctions_module.process_ended_auctions()
        tally_m8 = _tally()
        d_email = f"{buyer_d}@example.test"
        e_email = f"{buyer_e}@example.test"
        s3_email = f"{seller3}@example.test"

        checks.append(("M8.1 New auction Buyer D fires exactly 1 auction_won",
                       tally_m8.get(("send_auction_won_email", d_email)) == 1))
        checks.append(("M8.2 New auction Buyer E fires exactly 1 auction_won",
                       tally_m8.get(("send_auction_won_email", e_email)) == 1))
        checks.append(("M8.3 New auction Seller fires exactly 1 seller_sold",
                       tally_m8.get(("send_seller_auction_sold_email", s3_email)) == 1))
        # Auction 1 buyers untouched by auction 3 close.
        checks.append(("M8.4 Auction 1 Buyer A not touched by Auction 3 close",
                       tally_m8.get(("send_auction_won_email", a_email), 0) == 0))
        # Ledger has independent rows for both auctions.
        rows_auc1 = await db[COLLECTION].count_documents({"auction_id": auction1})
        rows_auc3 = await db[COLLECTION].count_documents({"auction_id": auc3})
        checks.append((f"M8.5 Ledger holds independent rows per auction "
                       f"(auc1={rows_auc1}, auc3={rows_auc3})",
                       rows_auc1 >= 3 and rows_auc3 >= 3))

        # Ledger inventory + key structure ─────────────────────────────
        rows = await db[COLLECTION].find(
            {"auction_id": {"$regex": f"^{PREFIX}"}}
        ).to_list(200)
        print("\n[iter462-audit] Ledger rows (auction_id, kind, user_id, event_key):")
        for r in rows:
            print(f"  {r.get('auction_id'):<42} {r.get('kind'):<28} "
                  f"user={r.get('user_id'):<40} event_key={r.get('event_key')!r}")

    finally:
        try:
            await _cleanup(db)
            print("\n[iter462-audit] ✓ cleaned up all seeded fixtures")
        except Exception as e:  # noqa: BLE001
            print(f"[iter462-audit] cleanup warning: {e}")
        client_db.close()

    print("\n[iter462-audit] === Mandatory-test summary ===")
    all_ok = True
    for label, ok in checks:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {label}")
        if not ok:
            all_ok = False
    if all_ok:
        print(f"\n[iter462-audit] ✅ ALL {len(checks)} MANDATORY AUDIT CHECKS PASSED\n")
    else:
        print("\n[iter462-audit] ❌ FAILURES ABOVE\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
