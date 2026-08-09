"""
iter454 — Reproduce Seller Dashboard "Sold (1) blank tab" bug.

Simulates the exact defect condition:
  • A seller_statement receipt exists for a completed sale.
  • The corresponding listing document has been purged post-settlement.
  • Dashboard shows counts.sold = 1 but all_listings does NOT contain
    the sale, so the frontend Sold tab renders empty.

Cleans up seeded data.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
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
    client_db = AsyncIOMotorClient(MONGO_URL)
    db = client_db[DB_NAME]

    admin = await db.users.find_one({"email": ADMIN_EMAIL})
    seller_id = admin["id"]

    print(f"\n[iter454-repro] Base URL: {BASE_URL}")
    print(f"[iter454-repro] Seller: {seller_id}\n")

    receipt_id = f"iter454-r-{uuid.uuid4().hex[:8]}"
    orphan_listing_id = f"iter454-purged-{uuid.uuid4().hex[:8]}"

    receipt_doc = {
        "id": receipt_id,
        "type": "seller_statement",
        "user_id": seller_id,
        "listing_id": orphan_listing_id,   # listing was purged
        "listing_title": "Test purged listing (iter454)",
        "buyer_id": "some-buyer-id",
        "hammer_price": 100.00,
        "total_charged": 105.00,
        "net_payout": 96.00,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.receipts.insert_one(receipt_doc)
    print("[iter454-repro] Seeded seller_statement receipt (listing purged)\n")

    try:
        async with httpx.AsyncClient(timeout=60.0, verify=True) as http:
            r = await http.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PW},
            )
            token = r.json().get("access_token") or r.json().get("token")
            auth = {"Authorization": f"Bearer {token}"}
            r = await http.get(f"{BASE_URL}/api/dashboard/seller", headers=auth)
            data = r.json()
            counts = data.get("counts", {})
            all_listings = data.get("all_listings", [])

            # How many entries in all_listings match the Sold predicate?
            def _is_sold(l):
                if l.get("status") == "sold":
                    return True
                if l.get("status") == "ended" and l.get("winner_user_id"):
                    return True
                return False
            sold_visible = [l for l in all_listings if _is_sold(l)]

            # Multi-item sold check (per-lot)
            for l in all_listings:
                if l.get("lots"):
                    if any(lot.get("winner_user_id") for lot in l["lots"]):
                        if l not in sold_visible:
                            sold_visible.append(l)

            print("[iter454-repro] === DASHBOARD STATE ===")
            print(f"  counts.sold             = {counts.get('sold')}")
            print(f"  counts.payment_collected= {counts.get('payment_collected')}")
            print(f"  all_listings length     = {len(all_listings)}")
            print(f"  Sold-tab visible cards  = {len(sold_visible)}")
            print(
                f"  seller_statements       = "
                f"{len(data.get('seller_statements', []))}"
            )
            mismatch = counts.get("sold", 0) != len(sold_visible)
            print(
                f"\n[iter454-repro] BUG {'REPRODUCED ✅' if mismatch else 'not reproduced ❌'}: "
                f"counts.sold={counts.get('sold')} but Sold-tab shows "
                f"{len(sold_visible)} cards"
            )
    finally:
        await db.receipts.delete_one({"id": receipt_id})
        client_db.close()
        print("\n[iter454-repro] ✓ cleanup complete")


if __name__ == "__main__":
    asyncio.run(main())
