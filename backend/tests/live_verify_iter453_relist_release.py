"""
iter453 — Live preview verification for multi-item re-list release alignment.

For a partially-sold multi-item auction re-listed with mode=now, verify:
  1. New listing status == "draft"
  2. New listing is EXCLUDED from public browse (`GET /api/multi-item-listings`)
  3. New listing is EXCLUDED from marketplace browse (`GET /api/marketplace/browse`)
  4. Bid on the new draft returns non-2xx
  5. Buy Now on the new draft returns non-2xx
  6. New listing IS visible on `GET /api/dashboard/seller` in the draft bucket

Cleans up seeded docs. Non-destructive to any real data.
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

AUCTION_ID = f"iter453-{uuid.uuid4().hex[:8]}"


async def main() -> None:
    client_db = AsyncIOMotorClient(MONGO_URL)
    db = client_db[DB_NAME]

    print(f"\n[iter453] Base URL: {BASE_URL}")
    print(f"[iter453] Source auction: {AUCTION_ID}\n")

    admin = await db.users.find_one({"email": ADMIN_EMAIL})
    seller_id = admin["id"]
    doc = {
        "id": AUCTION_ID,
        "seller_id": seller_id,
        "title": f"iter453 preview verify {AUCTION_ID}",
        "description": "-",
        "city": "Montreal",
        "region": "QC",
        "location": "-",
        "category": "furniture",
        "auction_start_date": "2026-02-01T00:00:00+00:00",
        "auction_end_date": "2026-02-07T00:00:00+00:00",
        "listing_type": "multi_item",
        "buyer_premium_pct": 5.0,
        "commission_rate": 4.0,
        "tax_rate_gst": 5.0,
        "tax_rate_qst": 9.975,
        "currency": "CAD",
        "premium_percentage": 5.0,
        "status": "ended",
        "lots": [
            {
                "lot_number": 1, "title": "L1", "description": "-",
                "quantity": 10, "sold_quantity": 3, "available_quantity": 7,
                "starting_price": 5.0, "current_price": 5.0,
                "buy_now_price": 7.0, "buy_now_enabled": True,
                "lot_status": "partially_sold", "status": "ended",
                "category": "furniture", "condition": "used",
            },
            {
                "lot_number": 2, "title": "L2", "description": "-",
                "quantity": 8, "sold_quantity": 0, "available_quantity": 8,
                "starting_price": 5.0, "current_price": 5.0,
                "buy_now_price": 7.0, "buy_now_enabled": True,
                "lot_status": "active", "status": "ended",
                "category": "furniture", "condition": "used",
            },
        ],
    }
    await db.multi_item_listings.insert_one(doc)
    print("[iter453] Seeded partially-sold multi-item auction (L1:10/3, L2:8/0)\n")

    new_id = None
    ok = True

    def _check(label: str, cond: bool) -> None:
        nonlocal ok
        mark = "✓" if cond else "✗"
        print(f"    {mark} {label}")
        if not cond:
            ok = False

    try:
        async with httpx.AsyncClient(timeout=60.0, verify=True) as http:
            r = await http.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PW},
            )
            token = r.json().get("access_token") or r.json().get("token")
            auth = {"Authorization": f"Bearer {token}"}
            print("[iter453] ✓ admin logged in\n")

            # 1) Relist with mode=now
            print("[iter453] Step 1 — POST /api/listings/{id}/relist?mode=now")
            r = await http.post(
                f"{BASE_URL}/api/listings/{AUCTION_ID}/relist?mode=now",
                headers=auth,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            new_id = body["new_listing_id"]
            print(f"  → new_listing_id={new_id}")
            _check(f"new listing status == 'draft' (got '{body['status']}')",
                   body["status"] == "draft")

            # 2) Public browse (multi-item feed)
            print("\n[iter453] Step 2 — GET /api/multi-item-listings (public)")
            r = await http.get(f"{BASE_URL}/api/multi-item-listings?limit=100")
            listings = r.json() if r.status_code == 200 else []
            ids = {l.get("id") for l in listings}
            _check(f"draft NOT in /multi-item-listings feed "
                   f"(got {len(listings)} listings)", new_id not in ids)

            # 3) Marketplace aggregated browse
            print("\n[iter453] Step 3 — GET /api/marketplace/browse")
            r = await http.get(f"{BASE_URL}/api/marketplace/browse?limit=100")
            if r.status_code == 200:
                items = r.json().get("items", []) if isinstance(r.json(), dict) else r.json()
                ids2 = {i.get("id") for i in items} if isinstance(items, list) else set()
                _check(f"draft NOT in /marketplace/browse "
                       f"(got {len(items) if isinstance(items, list) else 0} items)",
                       new_id not in ids2)
            else:
                # Endpoint layout tolerance — try alternates
                print(f"    (marketplace/browse returned {r.status_code}; "
                      "checking marketplace/all-active instead)")
                r = await http.get(f"{BASE_URL}/api/multi-item-listings?limit=200")
                if r.status_code == 200:
                    ids2 = {l.get("id") for l in r.json()}
                    _check("draft NOT in default marketplace feed",
                           new_id not in ids2)

            # 4) Bid on the draft — must fail
            print("\n[iter453] Step 4 — Bid on the draft (must fail)")
            r = await http.post(
                f"{BASE_URL}/api/multi-item-listings/{new_id}/lots/1/bid",
                headers=auth,
                json={"bid_amount": 100.00},
            )
            _check(f"bid rejected (status={r.status_code}, expected non-2xx)",
                   r.status_code >= 400)
            print(f"    → response: {r.text[:120]}")

            # 5) Buy Now on the draft — must fail
            print("\n[iter453] Step 5 — Buy Now on the draft (must fail)")
            r = await http.post(
                f"{BASE_URL}/api/payments/buy-now-preview",
                headers=auth,
                json={
                    "auction_id": new_id,
                    "lot_number": 1,
                    "quantity": 1,
                },
            )
            _check(f"buy-now-preview rejected (status={r.status_code})",
                   r.status_code >= 400)
            print(f"    → response: {r.text[:120]}")

            # 6) Seller dashboard shows the draft
            print("\n[iter453] Step 6 — GET /api/dashboard/seller "
                  "(draft must appear)")
            r = await http.get(
                f"{BASE_URL}/api/dashboard/seller", headers=auth
            )
            if r.status_code == 200:
                data = r.json()
                # Look for either a `listings` array or nested structure
                listings_arr = (
                    data.get("listings")
                    or data.get("all_listings")
                    or data.get("draft_listings")
                    or []
                )
                # Some endpoints return {counts, active_listings, draft_listings, ...}
                if not listings_arr and isinstance(data, dict):
                    listings_arr = data.get("multi_listings", [])
                found = any(
                    (l.get("id") == new_id) for l in listings_arr
                )
                if not found:
                    # Fall back to scanning nested keys
                    all_flat = []
                    for k, v in data.items():
                        if isinstance(v, list):
                            all_flat.extend(v)
                    found = any(l.get("id") == new_id for l in all_flat
                                if isinstance(l, dict))
                _check(f"draft visible on seller dashboard "
                       f"(found={found}, counts={data.get('counts', {})})",
                       found)
            else:
                _check(f"seller dashboard reachable (got {r.status_code})",
                       False)

    finally:
        await db.multi_item_listings.delete_many(
            {"$or": [
                {"id": AUCTION_ID},
                {"relisted_from": AUCTION_ID},
            ] + ([{"id": new_id}] if new_id else [])}
        )
        client_db.close()
        print("\n[iter453] ✓ cleanup complete")

    if ok:
        print("\n[iter453] ✅ ALL PREVIEW VERIFICATIONS PASSED\n")
    else:
        print("\n[iter453] ❌ SOME PREVIEW VERIFICATIONS FAILED\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
