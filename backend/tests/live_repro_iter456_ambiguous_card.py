"""
iter456 — Reproduce the ambiguous multi-item Sold card.

Seeds a multi-item auction with 3 lots covering mixed outcomes:
  Lot 1 — SOLD via auction close, payment_collected
  Lot 2 — SOLD via Buy-Now (partial: 2 of 5 sold), no payment_collected yet
  Lot 3 — UNSOLD (no bids)

Also seeds one orphan seller_statement receipt.

Fetches /api/dashboard/seller and prints what shows up under each Ended
split for this parent. The bug: today the WHOLE parent listing appears
under both "Sold" and "No Sale" as a single card that says "3 lots" —
sellers cannot see which specific lot sold and which didn't.
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

    aid = f"iter456-repro-{uuid.uuid4().hex[:8]}"
    receipt_id = f"iter456-r-{uuid.uuid4().hex[:6]}"
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
        "status": "ended",
        "lots": [
            {"lot_number": 1, "title": "Craftsman Wrench Set",
             "description": "17-piece SAE + metric",
             "quantity": 1, "sold_quantity": 0,
             "starting_price": 5.0, "current_price": 45.0,
             "final_price": 45.0,
             "winner_user_id": "iter456-buyer",
             "winning_quantity": 1, "winning_unit_price": 45.0,
             "payment_status": "payment_collected",
             "lot_status": "sold", "status": "sold"},
            {"lot_number": 2, "title": "Vintage Screwdrivers",
             "description": "Set of 12, mid-century",
             "quantity": 5, "sold_quantity": 2, "available_quantity": 3,
             "starting_price": 5.0, "current_price": 8.0,
             "buy_now_price": 8.0, "buy_now_enabled": True,
             "lot_status": "partially_sold", "status": "ended"},
            {"lot_number": 3, "title": "Antique Level",
             "description": "Wood + brass 24-inch level",
             "quantity": 1, "sold_quantity": 0,
             "starting_price": 20.0, "current_price": 20.0,
             "lot_status": "ended", "status": "ended"},
        ],
    }
    await db.multi_item_listings.insert_one(doc)
    # Historical settlement orphan
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

    try:
        async with httpx.AsyncClient(timeout=60.0, verify=True) as h:
            r = await h.post(f"{BASE_URL}/api/auth/login",
                             json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
            tok = r.json().get("access_token") or r.json().get("token")
            r = await h.get(f"{BASE_URL}/api/dashboard/seller",
                            headers={"Authorization": f"Bearer {tok}"})
            data = r.json()

            # Simulate frontend Sold filter
            def _isSold(l):
                if l.get("status") == "sold": return True
                if l.get("status") in ("ended","expired","completed"):
                    if l.get("winner_user_id") or l.get("winner_id"): return True
                    for lot in (l.get("lots") or []):
                        if lot.get("winner_user_id") or lot.get("winner_id") \
                           or (int(lot.get("sold_quantity") or 0) > 0):
                            return True
                return False
            all_l = data.get("all_listings", [])
            sold_cards = [l for l in all_l if _isSold(l)]
            our = next((l for l in sold_cards if l.get("id") == aid), None)

            print("=== iter456 — CURRENT BEHAVIOR (repro) ===\n")
            print(f"Sold-tab cards involving seed auction ({aid}):")
            if our:
                print(f"  • ONE card renders '{our.get('title')}' "
                      f"({len(our.get('lots') or [])} lots).")
                print(f"    Sub-info says '{len(our.get('lots') or [])} lots' — "
                      f"seller cannot see which lot(s) actually sold.")
                print(f"    Lot 1 sold + Lot 2 partially sold + Lot 3 unsold "
                      f"all collapsed into ONE ambiguous card.")
            else:
                print("  • Not found (unexpected).")
            # Orphan seller statement
            orphan = next((l for l in sold_cards if
                           l.get("_synthetic_from_receipt")
                           and l.get("receipt_id") == receipt_id), None)
            print()
            print(f"Historical (orphan) seller_statement card:")
            if orphan:
                print(f"  • Rendered as '{orphan.get('title')}' — no clear label "
                      f"telling seller this is a historical statement.")
            else:
                print("  • Not found (unexpected).")
            print()
            print("Same parent card ALSO appears in No Sale (Lot 3) → double-count?")
            def _isNoSale(l):
                if l.get("status") in ("ended_no_sale","unsold"): return True
                if l.get("status") in ("ended","expired"):
                    if l.get("winner_user_id"): return False
                    if any(lot.get("winner_user_id") or
                           (int(lot.get("sold_quantity") or 0) > 0)
                           for lot in (l.get("lots") or [])):
                        return False
                    return True
                return False
            ns_cards = [l for l in all_l if _isNoSale(l)]
            ns_ours = next((l for l in ns_cards if l.get("id") == aid), None)
            print(f"  No-Sale-tab has our parent card: {ns_ours is not None}")
            print(f"  (Lot 3 alone is unsold; today the seller sees "
                  f"'nothing' in the No Sale tab for this auction because the "
                  f"parent has other lots that sold.)")
    finally:
        await db.multi_item_listings.delete_one({"id": aid})
        await db.receipts.delete_one({"id": receipt_id})
        c.close()


if __name__ == "__main__":
    asyncio.run(main())
