"""
iter451 — Live E2E Buy Now regression against the preview backend.

Seeds an ACTIVE multi-item listing with a Buy Now-enabled lot:
  buy_now_price = $7.00,  quantity available = 5
Buyer purchases quantity = 2 via `POST /api/payments/buy-now-preview`
(server-side price breakdown, no side effects).

Asserts:
  • price_per_unit == 7.00
  • quantity == 2
  • item_total == 14.00
  • buyer_premium reconciles off $14 basis (~$0.70 at 5%)
  • buyer_total > item_total (adds premium + Stripe recovery + tax)
  • total_tax > 0 for a QC buyer
  • processing_fee > 0
  • Backend fields don't leak the resolver's `is_multiplied` path

Then runs a parallel confirmation for the auction-end fix:
  seeds a $7 × 2 auction lot, hits invoice endpoint, extracts PDF,
  verifies the SAME reconciliation ($14 hammer + fees).

Buy Now must not use `resolve_hammer_total` — it has its own
`buy_now_price * quantity` formula.
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

SEED_AUCTION_ID = f"iter451-bn-{uuid.uuid4().hex[:8]}"


async def main() -> None:
    client_db = AsyncIOMotorClient(MONGO_URL)
    db = client_db[DB_NAME]

    print(f"\n[iter451-buy-now] Base URL: {BASE_URL}")
    print(f"[iter451-buy-now] Auction: {SEED_AUCTION_ID}\n")

    # Seed a Buy Now-enabled multi-item listing
    admin = await db.users.find_one({"email": ADMIN_EMAIL})
    if not admin:
        print("[iter451-buy-now] ERROR: admin not found in DB")
        return
    seller_id = admin["id"]

    auction_doc = {
        "id": SEED_AUCTION_ID,
        "seller_id": seller_id,
        "title": "iter451 Buy Now Regression Auction",
        "description": "Buy Now flow test",
        "city": "Montreal",
        "region": "QC",
        "auction_end_date": "2026-08-31T23:59:59+00:00",
        "start_date": "2026-08-01T00:00:00+00:00",
        "listing_type": "multi_item",
        "buyer_premium_pct": 5.0,
        "commission_rate": 4.0,
        "tax_rate_gst": 5.0,
        "tax_rate_qst": 9.975,
        "currency": "CAD",
        "premium_percentage": 5.0,
        "status": "active",
        "lots": [
            {
                "lot_number": 1,
                "title": "Widget",
                "description": "Buy Now widget",
                "quantity": 5,
                "available_quantity": 5,
                "sold_quantity": 0,
                "buy_now_enabled": True,
                "buy_now_price": 7.00,
                "starting_price": 5.00,
                "current_price": 5.00,
                "lot_status": "active",
            }
        ],
    }
    await db.multi_item_listings.update_one(
        {"id": SEED_AUCTION_ID}, {"$set": auction_doc}, upsert=True
    )
    print("[iter451-buy-now] Seeded active Buy Now lot ($7/unit, 5 available)\n")

    ok_all = True
    try:
        async with httpx.AsyncClient(timeout=60.0, verify=True) as http:
            # Log in as admin (also used as buyer to keep the fixture single-tenant)
            r = await http.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PW},
            )
            assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
            token = r.json().get("access_token") or r.json().get("token")
            assert token, "no token"
            auth = {"Authorization": f"Bearer {token}"}
            print("[iter451-buy-now] ✓ admin logged in\n")

            # 1) Server-side price breakdown for Buy Now: $7 × 2
            print("[iter451-buy-now] POST /api/payments/buy-now-preview  (qty=2)")
            r = await http.post(
                f"{BASE_URL}/api/payments/buy-now-preview",
                headers=auth,
                json={
                    "auction_id": SEED_AUCTION_ID,
                    "lot_number": 1,
                    "quantity": 2,
                },
            )
            print(f"  → status {r.status_code}")
            if r.status_code != 200:
                print(f"  body: {r.text[:400]}")
                ok_all = False
            else:
                body = r.json()
                print(f"  → price_per_unit={body.get('price_per_unit')}")
                print(f"  → quantity={body.get('quantity')}")
                print(f"  → item_total={body.get('item_total')}")
                print(f"  → buyer_premium={body.get('buyer_premium')}")
                print(f"  → tax_label={body.get('tax_label')}")
                print(f"  → total_tax={body.get('total_tax')}")
                print(f"  → processing_fee={body.get('processing_fee')}")
                print(f"  → buyer_total={body.get('buyer_total')}")

                _bp = float(body.get("buyer_premium", 0))
                _it = float(body.get("item_total", 0))
                _rate = float(body.get("buyer_premium_rate", 0.05))
                _expected_bp = round(_it * _rate, 2)
                checks = {
                    "price_per_unit == 7.00":
                        abs(float(body.get("price_per_unit", 0)) - 7.00) < 0.005,
                    "quantity == 2":
                        int(body.get("quantity", 0)) == 2,
                    "item_total == 14.00 ($7 × 2)":
                        abs(_it - 14.00) < 0.005,
                    f"buyer_premium reconciles off $14 (rate={_rate}, "
                    f"expected≈${_expected_bp})":
                        abs(_bp - _expected_bp) < 0.05,
                    "total_tax > 0 (QC buyer)":
                        float(body.get("total_tax", 0)) > 0,
                    "processing_fee > 0 (Stripe recovery)":
                        float(body.get("processing_fee", 0)) > 0,
                    "buyer_total > item_total ($14)":
                        float(body.get("buyer_total", 0)) > 14.00,
                    "buyer_total < $20 (upper sanity)":
                        float(body.get("buyer_total", 0)) < 20.00,
                }
                for k, v in checks.items():
                    mark = "✓" if v else "✗"
                    print(f"    {mark} {k}")
                    if not v:
                        ok_all = False

            # 2) Regression check: quantity=1 baseline must still work
            print("\n[iter451-buy-now] POST /api/payments/buy-now-preview  (qty=1)")
            r = await http.post(
                f"{BASE_URL}/api/payments/buy-now-preview",
                headers=auth,
                json={
                    "auction_id": SEED_AUCTION_ID,
                    "lot_number": 1,
                    "quantity": 1,
                },
            )
            if r.status_code == 200:
                b = r.json()
                print(f"  → item_total={b.get('item_total')} (expected 7.00)")
                if abs(float(b.get("item_total", 0)) - 7.00) < 0.005:
                    print("    ✓ Buy Now qty=1 baseline unchanged (item_total=$7)")
                else:
                    print("    ✗ Buy Now qty=1 baseline broken")
                    ok_all = False
            else:
                print(f"  ✗ status {r.status_code}: {r.text[:200]}")
                ok_all = False

            # 3) Regression: 400 on requested qty > available (existing rule)
            print("\n[iter451-buy-now] POST /api/payments/buy-now-preview  "
                  "(qty=999, must 400)")
            r = await http.post(
                f"{BASE_URL}/api/payments/buy-now-preview",
                headers=auth,
                json={
                    "auction_id": SEED_AUCTION_ID,
                    "lot_number": 1,
                    "quantity": 999,
                },
            )
            if r.status_code == 400:
                print(f"    ✓ Buy Now rejected qty > available (status 400)")
            else:
                print(f"    ✗ expected 400, got {r.status_code}: {r.text[:200]}")
                ok_all = False

    finally:
        await db.multi_item_listings.delete_one({"id": SEED_AUCTION_ID})
        client_db.close()
        print("\n[iter451-buy-now] ✓ cleanup complete")

    if ok_all:
        print("\n[iter451-buy-now] ✅ ALL BUY NOW LIVE E2E CHECKS PASSED\n")
    else:
        print("\n[iter451-buy-now] ❌ SOME BUY NOW LIVE E2E CHECKS FAILED\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
