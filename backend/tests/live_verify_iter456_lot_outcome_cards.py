"""
iter456 — Live preview verification for lot-level outcome cards.

Seeds a multi-item auction with mixed outcomes + one orphan seller
statement, then asserts that:

  1. The Sold tab renders ONE card per SOLD lot (not one parent card).
  2. The No Sale tab renders ONE card per UNSOLD lot (partial-sale
     parent no longer hides its unsold lot).
  3. Lot cards have lot_number, meaningful lot_title, parent auction
     name as secondary, quantity_sold/remaining, hammer_total.
  4. Historical orphan receipts render as a "Historical settlement"
     card with a receipt_id reference.
  5. Badge counts equal the number of matching outcome cards.
  6. Payment Collected is a strict subset of Sold.

The verifier does NOT deploy, does NOT touch code, does NOT charge
real funds; every seeded doc is cleaned up.
"""
from __future__ import annotations
import asyncio, os, sys, uuid
from datetime import datetime, timezone
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


async def main():
    c = AsyncIOMotorClient(MONGO_URL)
    db = c[DB_NAME]
    admin = await db.users.find_one({"email": ADMIN_EMAIL})
    seller_id = admin["id"]

    aid = f"iter456-live-{uuid.uuid4().hex[:8]}"
    receipt_id = f"iter456-hist-{uuid.uuid4().hex[:6]}"

    doc = {
        "id": aid,
        "seller_id": seller_id,
        "title": "Vintage Toolbox Estate",
        "description": "-",
        "city": "Montreal", "region": "QC", "location": "-",
        "auction_start_date": "2026-02-01T00:00:00+00:00",
        "auction_end_date":   "2026-02-07T00:00:00+00:00",
        "listing_type": "multi_item",
        "buyer_premium_pct": 5.0, "commission_rate": 4.0,
        "tax_rate_gst": 5.0, "tax_rate_qst": 9.975,
        "currency": "CAD", "premium_percentage": 5.0,
        "multiply_hammer_by_quantity": True,
        "status": "ended",
        "lots": [
            {"lot_number": 1, "title": "Craftsman Wrench Set",
             "description": "17-piece SAE + metric",
             "quantity": 1, "sold_quantity": 0,
             "starting_price": 5.0, "current_price": 45.0,
             "final_price": 45.0, "winning_unit_price": 45.0,
             "winner_user_id": "iter456-buyer",
             "winning_quantity": 1,
             "payment_status": "payment_collected",
             "lot_status": "sold", "status": "sold"},
            {"lot_number": 2, "title": "Vintage Screwdrivers",
             "description": "12-piece mid-century set",
             "quantity": 5, "sold_quantity": 2, "available_quantity": 3,
             "starting_price": 5.0, "current_price": 8.0,
             "buy_now_price": 8.0, "buy_now_enabled": True,
             "lot_status": "partially_sold", "status": "ended"},
            {"lot_number": 3, "title": "Antique Level",
             "description": "24-inch wood + brass level",
             "quantity": 1, "sold_quantity": 0,
             "starting_price": 20.0, "current_price": 20.0,
             "lot_status": "ended", "status": "ended"},
        ],
    }
    await db.multi_item_listings.insert_one(doc)
    await db.receipts.insert_one({
        "id": receipt_id,
        "type": "seller_statement",
        "user_id": seller_id,
        "listing_id": f"iter456-purged-{uuid.uuid4().hex[:6]}",
        "listing_title": "iter456 purged historical",
        "buyer_id": "hist-buyer",
        "hammer_price": 250.00,
        "total_charged": 262.50,
        "net_payout": 240.00,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    ok = True
    def _check(label, cond):
        nonlocal ok
        mark = "✓" if cond else "✗"
        print(f"    {mark} {label}")
        if not cond:
            ok = False

    try:
        async with httpx.AsyncClient(timeout=60.0, verify=True) as h:
            r = await h.post(f"{BASE_URL}/api/auth/login",
                             json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
            tok = r.json().get("access_token") or r.json().get("token")
            auth = {"Authorization": f"Bearer {tok}"}

            for lang in ("en", "fr"):
                print(f"\n[iter456] Language={lang.upper()}")
                r = await h.get(f"{BASE_URL}/api/dashboard/seller?lang={lang}",
                                headers=auth)
                data = r.json()
                assert r.status_code == 200
                outcomes = data.get("lot_outcomes") or []
                iter456_outcomes = [
                    o for o in outcomes
                    if o.get("listing_id") == aid or o.get("receipt_id") == receipt_id
                ]
                # 1) Lot 1 → sold + payment_collected
                l1 = next((o for o in iter456_outcomes
                           if o.get("lot_number") == 1), None)
                _check("Lot 1 outcome exists", l1 is not None)
                if l1:
                    _check(f"Lot 1 title = 'Craftsman Wrench Set' "
                           f"(got '{l1.get('lot_title')}')",
                           l1.get("lot_title") == "Craftsman Wrench Set")
                    _check(f"Lot 1 parent context = 'Vintage Toolbox Estate' "
                           f"(got '{l1.get('parent_title')}')",
                           l1.get("parent_title") == "Vintage Toolbox Estate")
                    _check(f"Lot 1 outcome_status = 'sold' "
                           f"(got '{l1.get('outcome_status')}')",
                           l1.get("outcome_status") in ("sold", "completed"))
                    _check(f"Lot 1 payment_status = 'payment_collected'",
                           l1.get("payment_status") == "payment_collected")
                    _check(f"Lot 1 hammer_total = 45.00 "
                           f"(got {l1.get('hammer_total')})",
                           abs(l1.get("hammer_total", 0) - 45.00) < 0.01)
                    _check(f"Lot 1 quantity_sold = 1 "
                           f"(got {l1.get('quantity_sold')})",
                           l1.get("quantity_sold") == 1)

                # 2) Lot 2 → sold (partial via Buy-Now)
                l2 = next((o for o in iter456_outcomes
                           if o.get("lot_number") == 2), None)
                _check("Lot 2 outcome exists", l2 is not None)
                if l2:
                    _check(f"Lot 2 outcome_status = 'sold' "
                           f"(got '{l2.get('outcome_status')}')",
                           l2.get("outcome_status") == "sold")
                    _check(f"Lot 2 quantity_sold = 2 "
                           f"(got {l2.get('quantity_sold')})",
                           l2.get("quantity_sold") == 2)
                    _check(f"Lot 2 quantity_remaining = 3 "
                           f"(got {l2.get('quantity_remaining')})",
                           l2.get("quantity_remaining") == 3)
                    _check(f"Lot 2 hammer_total = 16.00 ($8×2) "
                           f"(got {l2.get('hammer_total')})",
                           abs(l2.get("hammer_total", 0) - 16.00) < 0.01)

                # 3) Lot 3 → no_sale
                l3 = next((o for o in iter456_outcomes
                           if o.get("lot_number") == 3), None)
                _check("Lot 3 outcome exists", l3 is not None)
                if l3:
                    _check(f"Lot 3 outcome_status = 'no_sale' "
                           f"(got '{l3.get('outcome_status')}')",
                           l3.get("outcome_status") == "no_sale")
                    _check(f"Lot 3 hammer_total = 0 (no sale) "
                           f"(got {l3.get('hammer_total')})",
                           l3.get("hammer_total") == 0.0)

                # 4) Historical settlement present with receipt_id reference
                hist = next((o for o in iter456_outcomes
                             if o.get("receipt_id") == receipt_id), None)
                _check("Historical outcome exists", hist is not None)
                if hist:
                    _check("Historical is_historical = True",
                           hist.get("is_historical") is True)
                    _check("Historical outcome_status = 'sold'",
                           hist.get("outcome_status") == "sold")
                    _check("Historical listing_type = 'historical'",
                           hist.get("listing_type") == "historical")
                    _check(f"Historical receipt_id set (got {hist.get('receipt_id')})",
                           hist.get("receipt_id") == receipt_id)

                # 5) Ended-split counts match visible outcome cards
                counts = data.get("counts", {})
                def _matches(o, split):
                    if split == "sold":
                        return o["outcome_status"] in ("sold", "completed")
                    if split == "no_sale":
                        return o["outcome_status"] == "no_sale"
                    if split == "payment_collected":
                        return o["outcome_status"] in ("sold", "completed") \
                            and o.get("payment_status") == "payment_collected"
                    if split == "payment_failed":
                        return o["outcome_status"] in ("sold", "completed") \
                            and o.get("payment_status") in ("payment_failed",
                                                            "payment_failed_final")
                    if split == "completed":
                        return o["outcome_status"] == "completed" or (
                            o.get("pickup_confirmed")
                            and o.get("payment_status") == "payment_collected"
                        )
                    return True

                for split, count_key in [
                    ("sold", "sold"),
                    ("no_sale", "ended_no_sale"),
                    ("payment_collected", "payment_collected"),
                    ("payment_failed", "payment_failed"),
                    ("completed", "completed"),
                ]:
                    visible = sum(1 for o in outcomes if _matches(o, split))
                    _check(f"{split} count ({counts.get(count_key)}) == visible cards ({visible})",
                           counts.get(count_key, 0) == visible)

                # 6) Payment Collected is a subset of Sold
                pc = {o["outcome_id"] for o in outcomes
                      if _matches(o, "payment_collected")}
                sold = {o["outcome_id"] for o in outcomes
                        if _matches(o, "sold")}
                _check("Payment Collected ⊆ Sold", pc.issubset(sold))
    finally:
        await db.multi_item_listings.delete_one({"id": aid})
        await db.receipts.delete_one({"id": receipt_id})
        c.close()

    if ok:
        print("\n[iter456] ✅ ALL LIVE OUTCOME-CARD CHECKS PASSED\n")
    else:
        print("\n[iter456] ❌ FAILURES ABOVE\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
