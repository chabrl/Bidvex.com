"""
iter452 — Reproduction script: shows the current re-list flow does NOT
reconcile sold_quantity for partially-sold multi-item auctions.

Seeds a multi-item listing with:
  Lot 1: quantity=10, sold_quantity=3     (partial Buy-Now sale)
  Lot 2: quantity=5,  sold_quantity=5     (fully sold via Buy-Now)
  Lot 3: quantity=8,  sold_quantity=0     (untouched)
Then simulates the ended-no-sale parent (no winner_user_id at the top)
and calls POST /api/listings/{id}/relist?mode=now.

CURRENT BUG: The relisted lots keep the original `quantity`,
`sold_quantity`, and `available_quantity` — so Lot 1 relists 10 units
(should be 7), Lot 2 relists 5 units (should be blocked), and the
listing publishes as `active` (should always be a reviewable draft).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
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

AUCTION_ID = f"iter452-repro-{uuid.uuid4().hex[:8]}"


async def main() -> None:
    client_db = AsyncIOMotorClient(MONGO_URL)
    db = client_db[DB_NAME]

    print(f"\n[iter452-repro] Base URL: {BASE_URL}")
    print(f"[iter452-repro] Auction:  {AUCTION_ID}\n")

    admin = await db.users.find_one({"email": ADMIN_EMAIL})
    seller_id = admin["id"]

    # Seed the ended, partially-sold multi-item auction.
    doc = {
        "id": AUCTION_ID,
        "seller_id": seller_id,
        "title": "iter452 repro auction",
        "description": "partial-sale relist repro",
        "city": "Montreal",
        "region": "QC",
        "location": "warehouse",
        "auction_start_date": "2026-02-01T00:00:00+00:00",
        "auction_end_date": "2026-02-07T00:00:00+00:00",
        "listing_type": "multi_item",
        "buyer_premium_pct": 5.0,
        "commission_rate": 4.0,
        "tax_rate_gst": 5.0,
        "tax_rate_qst": 9.975,
        "currency": "CAD",
        "premium_percentage": 5.0,
        "status": "ended",  # parent has ended
        "lots": [
            {
                "lot_number": 1,
                "title": "Lot 1 — partially sold via Buy-Now",
                "description": "-",
                "quantity": 10,
                "sold_quantity": 3,
                "available_quantity": 7,
                "starting_price": 5.00,
                "current_price": 5.00,
                "buy_now_price": 7.00,
                "buy_now_enabled": True,
                "lot_status": "partially_sold",
                "status": "ended",
            },
            {
                "lot_number": 2,
                "title": "Lot 2 — fully sold via Buy-Now",
                "description": "-",
                "quantity": 5,
                "sold_quantity": 5,
                "available_quantity": 0,
                "starting_price": 5.00,
                "current_price": 5.00,
                "buy_now_price": 7.00,
                "buy_now_enabled": True,
                "lot_status": "sold_out",
                "status": "sold",
            },
            {
                "lot_number": 3,
                "title": "Lot 3 — completely unsold",
                "description": "-",
                "quantity": 8,
                "sold_quantity": 0,
                "available_quantity": 8,
                "starting_price": 5.00,
                "current_price": 5.00,
                "lot_status": "active",
                "status": "ended",
            },
        ],
    }
    await db.multi_item_listings.update_one(
        {"id": AUCTION_ID}, {"$set": doc}, upsert=True
    )
    print("[iter452-repro] Seeded auction with 3 lots (10/3, 5/5, 8/0)\n")

    try:
        async with httpx.AsyncClient(timeout=60.0, verify=True) as http:
            r = await http.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PW},
            )
            token = r.json().get("access_token") or r.json().get("token")
            auth = {"Authorization": f"Bearer {token}"}
            print("[iter452-repro] ✓ admin logged in\n")

            # Call the relist endpoint.
            r = await http.post(
                f"{BASE_URL}/api/listings/{AUCTION_ID}/relist?mode=now",
                headers=auth,
            )
            print(f"[iter452-repro] POST /listings/{{id}}/relist?mode=now → {r.status_code}")
            if r.status_code != 200:
                print(f"  body: {r.text[:400]}")
                return
            body = r.json()
            new_id = body.get("new_listing_id")
            print(f"  → new_listing_id={new_id}")
            print(f"  → status={body.get('status')} (expected 'draft' per user directive)")

            # Inspect the relisted doc
            relisted = await db.multi_item_listings.find_one(
                {"id": new_id}, {"_id": 0}
            )
            print("\n[iter452-repro] === RELISTED LOTS ===")
            for lot in relisted.get("lots") or []:
                print(
                    f"  Lot #{lot.get('lot_number')}: "
                    f"quantity={lot.get('quantity')}, "
                    f"sold_quantity={lot.get('sold_quantity')}, "
                    f"available_quantity={lot.get('available_quantity')}, "
                    f"lot_status={lot.get('lot_status')}"
                )

            # Verify source doc unmodified
            source = await db.multi_item_listings.find_one(
                {"id": AUCTION_ID}, {"_id": 0}
            )
            print("\n[iter452-repro] === SOURCE (must be untouched) ===")
            for lot in source.get("lots") or []:
                print(
                    f"  Lot #{lot.get('lot_number')}: "
                    f"quantity={lot.get('quantity')}, "
                    f"sold_quantity={lot.get('sold_quantity')}, "
                    f"available_quantity={lot.get('available_quantity')}"
                )
            print(f"  Source status={source.get('status')}, relisted_to={source.get('relisted_to')}")

            # Print bug summary
            print("\n[iter452-repro] === BUG SUMMARY ===")
            expected = {1: 7, 2: "BLOCK/OMIT", 3: 8}
            actual = {
                lot.get("lot_number"): lot.get("quantity")
                for lot in relisted.get("lots") or []
            }
            for ln in (1, 2, 3):
                exp = expected[ln]
                act = actual.get(ln, "OMITTED")
                mark = "✅" if act == exp else "❌"
                print(f"  Lot #{ln}: expected quantity={exp}, actual quantity={act} {mark}")
            print(
                f"  Publish semantics: expected='draft', actual='{body.get('status')}' "
                f"{'✅' if body.get('status') == 'draft' else '❌'}"
            )

    finally:
        # Cleanup
        await db.multi_item_listings.delete_many(
            {"$or": [{"id": AUCTION_ID}, {"relisted_from": AUCTION_ID}]}
        )
        client_db.close()
        print("\n[iter452-repro] ✓ cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
