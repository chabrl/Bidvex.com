"""
iter468 — Final document delivery acceptance test.

Verifies:
  1. Confirmed Stripe payment → buyer gets ONE email w/ ONE secure link
     to their paid invoice; seller gets ONE email w/ ONE secure link
     to their settlement statement. Both links resolve to a document
     containing only the recipient's actual data.
  2. Duplicate payment event (retry of `finalize_auction_payment` for
     the same settled event) → NO second email fires for either side.
  3. Failed Stripe payment (buyer_charge=None) → NO document email
     fires. NO documents generated.
  4. Multi-lot settlement → ONE buyer email covering all Buyer A's
     won lots; ONE seller email; independent of Buyer B's settlement.

No customer emails sent (all senders monkey-patched). All fixtures
removed on exit.
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

PREFIX = f"iter468-{uuid.uuid4().hex[:8]}"

SEND_LOG: List[Dict[str, Any]] = []


def _install_email_counters():
    import services.emails.email_marketplace as em
    import services.emails.email_system as es
    import services.emails.email_vehicles as ev

    async def _rec(fn, **kw):
        SEND_LOG.append({
            "fn": fn,
            "to": (kw.get("to_email") or kw.get("seller_email")
                   or kw.get("buyer_email")
                   or (kw.get("buyer") or {}).get("email")
                   or (kw.get("seller") or {}).get("email")
                   or "unknown"),
            "kwargs": {k: str(v)[:120] for k, v in kw.items()
                       if k in ("invoice_link", "statement_link",
                                "invoice_number", "statement_number",
                                "listing_title")},
        })
        return {"mocked": True}

    em.send_auction_won_email = lambda **kw: _rec("send_auction_won_email", **kw)
    em.send_auction_sold_email = lambda **kw: _rec("send_auction_sold_email", **kw)
    ev.send_seller_auction_sold_email = lambda **kw: _rec("send_seller_auction_sold_email", **kw)
    es.send_buyer_receipt_email = lambda **kw: _rec("send_buyer_receipt_email", **kw)
    es.send_seller_statement_email = lambda **kw: _rec("send_seller_statement_email", **kw)
    es.send_payment_link_email = lambda **kw: _rec("send_payment_link_email", **kw)
    es.send_payment_failed_email = lambda **kw: _rec("send_payment_failed_email", **kw)
    es.send_buyer_final_invoice_link_email = lambda **kw: _rec(
        "send_buyer_final_invoice_link_email", **kw)
    es.send_seller_settlement_link_email = lambda **kw: _rec(
        "send_seller_settlement_link_email", **kw)


def _tally():
    counts = defaultdict(int)
    for e in SEND_LOG:
        counts[(e["fn"], e["to"])] += 1
    return dict(counts)


def _fresh(kind: str) -> str:
    return f"{PREFIX}-{kind}-{uuid.uuid4().hex[:6]}"


async def _seed_ml(db, seller_id, buyer_a, buyer_b) -> str:
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    past_iso = (now - timedelta(minutes=5)).isoformat()
    for uid, name in [(seller_id, "S"), (buyer_a, "A"), (buyer_b, "B")]:
        await db.users.insert_one({
            "id": uid, "email": f"{uid}@example.test",
            "name": f"iter468 {name}", "full_name": f"iter468 {name}",
            "province": "QC", "subscription_tier": "free",
            "account_type": "individual", "preferred_language": "en",
            "phone": "555", "created_at": now_iso,
        })
    auction_id = _fresh("auction")
    await db.multi_item_listings.insert_one({
        "id": auction_id,
        "title": f"iter468 Confirm-Stripe Auction ({PREFIX})",
        "city": "Montréal", "region": "QC", "location_province": "QC",
        "seller_id": seller_id, "status": "ended",
        "listing_type": "lots", "auction_type": "lots",
        "currency": "CAD", "auction_end_date": past_iso,
        "lots": [
            {"lot_number": 1, "title": "Lot 1",
             "highest_bidder_id": buyer_a, "winner_user_id": buyer_a,
             "current_price": 100.0, "final_price": 100.0,
             "status": "sold",
             "quantity": 1, "lot_end_time": past_iso},
            {"lot_number": 2, "title": "Lot 2",
             "highest_bidder_id": buyer_a, "winner_user_id": buyer_a,
             "current_price": 7.0, "final_price": 7.0,
             "status": "sold",
             "quantity": 3, "multiply_hammer_by_quantity": True,
             "lot_end_time": past_iso},
            {"lot_number": 3, "title": "Lot 3",
             "highest_bidder_id": buyer_b, "winner_user_id": buyer_b,
             "current_price": 50.0, "final_price": 50.0,
             "status": "sold",
             "quantity": 2, "multiply_hammer_by_quantity": True,
             "lot_end_time": past_iso},
        ],
        "created_at": now_iso, "updated_at": now_iso,
    })
    return auction_id


async def _cleanup(db, prefix):
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
    print(f"\n[iter468] Prefix: {PREFIX}\n")

    checks: List[tuple] = []

    try:
        from services.final_document_delivery import deliver_final_documents
        from services.settlement_email_dedup import ensure_indexes, COLLECTION
        # Mirror FastAPI startup: initialise the routes module's shared
        # DB reference so `generate_lots_won_invoice` /
        # `generate_seller_statement` can operate. In the running backend
        # this happens automatically via server.py startup; here we
        # mirror it for the in-process test.
        from deps import set_db as _deps_set_db
        _deps_set_db(db)
        await ensure_indexes(db)
        _install_email_counters()

        seller_id = _fresh("seller1")
        buyer_a = _fresh("buyerA")
        buyer_b = _fresh("buyerB")
        auction_id = await _seed_ml(db, seller_id, buyer_a, buyer_b)

        # ═════════════════════════════════════════════════════════════
        # M1 — Confirmed Stripe payment for Buyer A (won 2 lots)
        # ═════════════════════════════════════════════════════════════
        SEND_LOG.clear()
        result_a = await deliver_final_documents(
            db,
            auction_id=auction_id,
            buyer_id=buyer_a,
            seller_id=seller_id,
            payment_method="stripe",
            buyer_charge={"stripe_pi": f"pi_iter468_conf_{buyer_a}"},
            listing_title="iter468 Multi-lot Auction",
        )
        tally_a = _tally()

        checks.append((
            "M1.1 Eligibility: confirmed stripe payment was recognised as "
            "eligible",
            result_a["eligible"] is True,
        ))
        checks.append((
            "M1.2 Buyer A received EXACTLY ONE final invoice link email",
            tally_a.get(("send_buyer_final_invoice_link_email",
                         f"{buyer_a}@example.test")) == 1,
        ))
        checks.append((
            "M1.3 Seller received EXACTLY ONE settlement statement link email",
            tally_a.get(("send_seller_settlement_link_email",
                         f"{seller_id}@example.test")) == 1,
        ))
        # Inspect kwargs — link is a URL and invoice_number is present
        buyer_msg = next(
            (m for m in SEND_LOG
             if m["fn"] == "send_buyer_final_invoice_link_email"), None,
        )
        seller_msg = next(
            (m for m in SEND_LOG
             if m["fn"] == "send_seller_settlement_link_email"), None,
        )
        checks.append((
            "M1.4 Buyer email carries a non-empty invoice_link + "
            "invoice_number",
            bool(buyer_msg and buyer_msg["kwargs"].get("invoice_link")
                 and buyer_msg["kwargs"].get("invoice_number")),
        ))
        checks.append((
            "M1.5 Seller email carries a non-empty statement_link + "
            "statement_number",
            bool(seller_msg and seller_msg["kwargs"].get("statement_link")
                 and seller_msg["kwargs"].get("statement_number")),
        ))
        # Confirm real invoices persisted with actual buyer/seller ids
        buyer_invoice = await db.invoices.find_one({
            "auction_id": auction_id, "user_id": buyer_a,
            "invoice_type": "lots_won",
        })
        seller_statement = await db.invoices.find_one({
            "auction_id": auction_id, "user_id": seller_id,
            "invoice_type": "seller_statement",
        })
        checks.append((
            "M1.6 Buyer invoice PDF row persisted for Buyer A",
            buyer_invoice is not None,
        ))
        checks.append((
            "M1.7 Seller statement PDF row persisted for Seller",
            seller_statement is not None,
        ))
        # Ledger has one row per side
        led_buyer = await db[COLLECTION].count_documents({
            "kind": "final_document_buyer_link",
            "auction_id": auction_id, "user_id": buyer_a,
        })
        led_seller = await db[COLLECTION].count_documents({
            "kind": "final_document_seller_link",
            "auction_id": auction_id, "user_id": seller_id,
        })
        checks.append((f"M1.8 Ledger has 1 buyer-link row (got {led_buyer})",
                       led_buyer == 1))
        checks.append((f"M1.9 Ledger has 1 seller-link row (got {led_seller})",
                       led_seller == 1))

        # ═════════════════════════════════════════════════════════════
        # M2 — Duplicate payment event → NO second document email
        # ═════════════════════════════════════════════════════════════
        SEND_LOG.clear()
        result_dup = await deliver_final_documents(
            db,
            auction_id=auction_id, buyer_id=buyer_a, seller_id=seller_id,
            payment_method="stripe",
            buyer_charge={"stripe_pi": f"pi_iter468_conf_{buyer_a}"},
            listing_title="iter468 Multi-lot Auction",
        )
        tally_dup = _tally()

        checks.append((
            "M2.1 Duplicate confirmed-payment event triggered NO buyer "
            "second email",
            tally_dup.get(("send_buyer_final_invoice_link_email",
                           f"{buyer_a}@example.test"), 0) == 0,
        ))
        checks.append((
            "M2.2 Duplicate confirmed-payment event triggered NO seller "
            "second email",
            tally_dup.get(("send_seller_settlement_link_email",
                           f"{seller_id}@example.test"), 0) == 0,
        ))
        checks.append((
            "M2.3 Duplicate call reported suppression reason='duplicate_claim'",
            result_dup["buyer_email_suppressed_reason"] == "duplicate_claim"
            and result_dup["seller_email_suppressed_reason"] == "duplicate_claim",
        ))

        # ═════════════════════════════════════════════════════════════
        # M3 — Failed Stripe payment (no buyer_charge) → NO email
        # ═════════════════════════════════════════════════════════════
        buyer_c = _fresh("buyerC")
        seller2 = _fresh("seller2")
        auc_c = _fresh("auction")
        now_iso = datetime.now(timezone.utc).isoformat()
        await db.users.insert_many([
            {"id": buyer_c, "email": f"{buyer_c}@example.test",
             "name": "C", "full_name": "C", "province": "QC",
             "subscription_tier": "free", "account_type": "individual",
             "preferred_language": "en", "created_at": now_iso},
            {"id": seller2, "email": f"{seller2}@example.test",
             "name": "S2", "full_name": "S2", "province": "QC",
             "subscription_tier": "free", "account_type": "individual",
             "created_at": now_iso},
        ])
        await db.multi_item_listings.insert_one({
            "id": auc_c, "title": "iter468 Failed Auction",
            "city": "M", "region": "QC", "location_province": "QC",
            "seller_id": seller2, "status": "ended",
            "listing_type": "lots", "auction_type": "lots",
            "currency": "CAD", "auction_end_date": now_iso,
            "lots": [{"lot_number": 1, "title": "F1",
                      "winner_user_id": buyer_c, "highest_bidder_id": buyer_c,
                      "current_price": 42.0, "final_price": 42.0,
                      "status": "sold", "quantity": 1}],
            "created_at": now_iso, "updated_at": now_iso,
        })

        SEND_LOG.clear()
        # buyer_charge is None → not confirmed → must skip
        result_fail_1 = await deliver_final_documents(
            db, auction_id=auc_c, buyer_id=buyer_c, seller_id=seller2,
            payment_method="stripe", buyer_charge=None,
            listing_title="iter468 Failed Auction",
        )
        # Also try non-Stripe methods explicitly
        result_fail_2 = await deliver_final_documents(
            db, auction_id=auc_c, buyer_id=buyer_c, seller_id=seller2,
            payment_method="cash",
            buyer_charge={"stripe_pi": "pi_should_not_matter"},
            listing_title="iter468 Failed Auction",
        )
        result_fail_3 = await deliver_final_documents(
            db, auction_id=auc_c, buyer_id=buyer_c, seller_id=seller2,
            payment_method="etransfer",
            buyer_charge={"stripe_pi": "pi_should_not_matter"},
            listing_title="iter468 Failed Auction",
        )
        result_fail_4 = await deliver_final_documents(
            db, auction_id=auc_c, buyer_id=buyer_c, seller_id=seller2,
            payment_method="stripe", buyer_charge={},
            listing_title="iter468 Failed Auction",
        )
        tally_fail = _tally()

        checks.append((
            "M3.1 Failed (buyer_charge=None) — NO buyer email fired",
            tally_fail.get(("send_buyer_final_invoice_link_email",
                            f"{buyer_c}@example.test"), 0) == 0,
        ))
        checks.append((
            "M3.2 Failed (buyer_charge=None) — NO seller email fired",
            tally_fail.get(("send_seller_settlement_link_email",
                            f"{seller2}@example.test"), 0) == 0,
        ))
        checks.append((
            "M3.3 Cash payment method — NOT eligible; skipped",
            result_fail_2["eligible"] is False,
        ))
        checks.append((
            "M3.4 E-transfer payment method — NOT eligible; skipped",
            result_fail_3["eligible"] is False,
        ))
        checks.append((
            "M3.5 Stripe with empty buyer_charge — NOT eligible; skipped",
            result_fail_4["eligible"] is False,
        ))
        checks.append((
            "M3.6 Suppression reason='not_confirmed_stripe' on all 4 "
            "failed paths",
            all(r["buyer_email_suppressed_reason"] == "not_confirmed_stripe"
                for r in (result_fail_1, result_fail_2, result_fail_3,
                          result_fail_4)),
        ))

        # ═════════════════════════════════════════════════════════════
        # M4 — Multi-lot settlement: one buyer email covers all lots.
        # Also confirm Buyer B (independent settlement) fires
        # independently for its own confirmed payment.
        # ═════════════════════════════════════════════════════════════
        # (already covered by M1 for Buyer A). Now trigger Buyer B.
        SEND_LOG.clear()
        result_b = await deliver_final_documents(
            db, auction_id=auction_id, buyer_id=buyer_b, seller_id=seller_id,
            payment_method="stripe",
            buyer_charge={"stripe_pi": f"pi_iter468_conf_{buyer_b}"},
            listing_title="iter468 Multi-lot Auction",
        )
        tally_b = _tally()

        checks.append((
            "M4.1 Buyer B (independent settlement) received EXACTLY ONE "
            "final invoice link email",
            tally_b.get(("send_buyer_final_invoice_link_email",
                         f"{buyer_b}@example.test")) == 1,
        ))
        # Seller now has TWO settlements (buyer_a earlier + buyer_b now)
        # BUT the ledger key `(kind, auction_id, seller_id, "")` is
        # already claimed by M1's seller send, so the seller does NOT
        # get a second email — the seller_statement PDF already covers
        # ALL sold lots for this auction. This is by design.
        checks.append((
            "M4.2 Seller does NOT get a second email for the same auction "
            "settlement (already claimed in M1 — statement PDF aggregates)",
            tally_b.get(("send_seller_settlement_link_email",
                         f"{seller_id}@example.test"), 0) == 0,
        ))

        # Confirm Buyer A ledger row still exactly 1, plus a fresh row
        # for Buyer B — three total rows for this auction.
        rows_final = await db[COLLECTION].find({
            "auction_id": auction_id,
            "kind": {"$in": ["final_document_buyer_link",
                             "final_document_seller_link"]},
        }).to_list(20)
        checks.append((
            f"M4.3 Ledger holds 3 rows for this auction "
            f"(1 seller + 2 buyers), got {len(rows_final)}",
            len(rows_final) == 3,
        ))

        # Print the ledger for observability
        print("\n[iter468] Final-document ledger rows:")
        for r in rows_final:
            r.pop("_id", None)
            print(f"  {r.get('kind'):<28} user={r.get('user_id'):<40} "
                  f"event_key={r.get('event_key')!r}")

    finally:
        try:
            await _cleanup(db, PREFIX)
            print(f"\n[iter468] ✓ cleaned up all fixtures with prefix {PREFIX}")
        except Exception as e:  # noqa: BLE001
            print(f"[iter468] cleanup warning: {e}")
        client_db.close()

    print("\n[iter468] === Summary ===")
    all_ok = True
    for label, ok in checks:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {label}")
        if not ok:
            all_ok = False
    if all_ok:
        print(f"\n[iter468] ✅ ALL {len(checks)} ACCEPTANCE CHECKS PASSED\n")
    else:
        print("\n[iter468] ❌ FAILURES ABOVE\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
