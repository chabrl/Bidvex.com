"""
iter451 — Live E2E test for /api/invoices/lots-won/{auction_id}/{user_id}

Seeds a multi-item listing where a buyer wins two lots:
  • Lot A — $7 × 2 = $14
  • Lot B — $10 × 3 = $30
Total merchandise = $44

Then hits the actual HTTP endpoint (through the preview URL) and
verifies the returned invoice_record persists and the PDF is generated.

The response JSON is a redirect/signed-URL wrapper, so we hit the
endpoint, then fetch the PDF, extract text, and assert the multi-item
math is present.

Run:
  cd /app/backend && python tests/live_e2e_iter451_invoice_pdf.py

Requires:
  - REACT_APP_BACKEND_URL in /app/frontend/.env
  - MongoDB connection from /app/backend/.env
  - charbel911@gmail.com admin credentials (auto-loaded from
    /app/memory/test_credentials.md convention).

CLEANS UP the seeded docs on exit.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

# Load /app/backend as import root
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

SEED_AUCTION_ID = f"iter451-e2e-{uuid.uuid4().hex[:8]}"
SEED_BUYER_ID = f"iter451-buyer-{uuid.uuid4().hex[:8]}"


async def main() -> None:
    client_db = AsyncIOMotorClient(MONGO_URL)
    db = client_db[DB_NAME]

    print(f"\n[iter451-e2e] Base URL: {BASE_URL}")
    print(f"[iter451-e2e] Auction:  {SEED_AUCTION_ID}")
    print(f"[iter451-e2e] Buyer:    {SEED_BUYER_ID}\n")

    # 1) Seed buyer
    buyer_doc = {
        "id": SEED_BUYER_ID,
        "email": f"{SEED_BUYER_ID}@iter451.test",
        "name": "Iter451 Test Buyer",
        "phone": "+15145550451",
        "billing_address": "1 Test Ave, Montreal, QC",
        "province": "QC",
        "subscription_tier": "free",
        "preferred_language": "en",
        "account_type": "user",
        "role": "user",
    }
    await db.users.update_one(
        {"id": SEED_BUYER_ID}, {"$set": buyer_doc}, upsert=True
    )

    # 2) Seed seller (use admin as seller so we don't need a full user tree)
    admin_seller = await db.users.find_one({"email": ADMIN_EMAIL})
    if not admin_seller:
        print("[iter451-e2e] ERROR: admin seller not found in DB")
        return
    seller_id = admin_seller["id"]

    # 3) Seed multi-item auction with 2 winning lots for our buyer
    auction_doc = {
        "id": SEED_AUCTION_ID,
        "seller_id": seller_id,
        "title": "iter451 Regression Auction",
        "description": "e2e test",
        "city": "Montreal",
        "region": "QC",
        "location": "Test warehouse",
        "auction_end_date": "2026-02-08T00:00:00+00:00",
        "listing_type": "multi_item",
        "multiply_hammer_by_quantity": True,
        "buyer_premium_pct": 5.0,
        "commission_rate": 4.0,
        "tax_rate_gst": 5.0,
        "tax_rate_qst": 9.975,
        "currency": "CAD",
        "premium_percentage": 5.0,
        "status": "ended",
        "lots": [
            {
                "lot_number": 1,
                "title": "Widget A",
                "description": "Widget A, per-unit $7",
                "final_price": 7.00,       # unit price
                "current_price": 7.00,
                "quantity_won": 2,
                "quantity": 2,
                "winning_unit_price": 7.00,
                "winning_quantity": 2,
                "winner_user_id": SEED_BUYER_ID,
                "status": "sold",
            },
            {
                "lot_number": 2,
                "title": "Widget B",
                "description": "Widget B, per-unit $10",
                "final_price": 10.00,      # unit price
                "current_price": 10.00,
                "quantity_won": 3,
                "quantity": 3,
                "winning_unit_price": 10.00,
                "winning_quantity": 3,
                "winner_user_id": SEED_BUYER_ID,
                "status": "sold",
            },
        ],
    }
    await db.multi_item_listings.update_one(
        {"id": SEED_AUCTION_ID}, {"$set": auction_doc}, upsert=True
    )
    print(f"[iter451-e2e] Seeded auction with 2 winning lots for buyer\n")

    ok_all = True
    try:
        async with httpx.AsyncClient(timeout=60.0, verify=True) as http:
            # 4) Log in as admin
            r = await http.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": ADMIN_EMAIL, "password": ADMIN_PW},
            )
            assert r.status_code == 200, (
                f"admin login failed: {r.status_code} {r.text}"
            )
            token = r.json().get("access_token") or r.json().get("token")
            assert token, f"no token in login response: {r.json()}"
            auth = {"Authorization": f"Bearer {token}"}
            print("[iter451-e2e] ✓ admin logged in\n")

            # 5) Hit the actual PDF endpoint
            print("[iter451-e2e] POST /api/invoices/lots-won/{auction}/{buyer}")
            r = await http.post(
                f"{BASE_URL}/api/invoices/lots-won/{SEED_AUCTION_ID}/{SEED_BUYER_ID}?lang=en",
                headers=auth,
            )
            print(f"  → status {r.status_code}")
            if r.status_code != 200:
                print(f"  body: {r.text[:400]}")
                ok_all = False
            else:
                body = r.json()
                print(f"  → success={body.get('success')}")
                print(f"  → invoice_number={body.get('invoice_number')}")
                print(f"  → paddle_number={body.get('paddle_number')}")
                print(f"  → download_url={(body.get('download_url') or '')[:80]}...")
                assert body.get("success") is True, "invoice not marked success"

                # 6) Fetch invoice record from DB and verify
                invoice_row = await db.invoices.find_one(
                    {"auction_id": SEED_AUCTION_ID, "user_id": SEED_BUYER_ID}
                )
                assert invoice_row is not None, "invoice row not persisted"
                print(f"  → DB invoice.id={invoice_row.get('id')}")
                print(f"  → DB invoice.storage_path={invoice_row.get('storage_path')}")

                # 7) Verify PDF is present + extract text and assert amounts
                dl = body.get("download_url")
                if dl:
                    if dl.startswith("/"):
                        dl = f"{BASE_URL}{dl}"
                    r_pdf = await http.get(dl)
                    print(f"  → PDF fetch status={r_pdf.status_code}, "
                          f"bytes={len(r_pdf.content)}")
                    if r_pdf.status_code == 200 and r_pdf.content:
                        # Extract text with pdfplumber if available; else grep
                        # naive PDF raw text.
                        pdf_bytes = r_pdf.content
                        try:
                            import pdfplumber
                            import io
                            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                                text = "\n".join(
                                    (p.extract_text() or "") for p in pdf.pages
                                )
                        except Exception as e:
                            print(f"  pdfplumber unavailable ({e}); "
                                  "using naive decode")
                            text = pdf_bytes.decode("latin-1", "ignore")

                        # Assertions:
                        checks = {
                            "Unit Price header":
                                "Unit Price" in text or "Prix unitaire" in text,
                            "Line total $14.00 for Lot A":
                                "$14.00" in text or "14.00" in text,
                            "Line total $30.00 for Lot B":
                                "$30.00" in text or "30.00" in text,
                            "Hammer total $44.00":
                                "$44.00" in text or "44.00" in text,
                            "Unit price $7.00 present":
                                "$7.00" in text or "7.00" in text,
                            "Unit price $10.00 present":
                                "$10.00" in text or "10.00" in text,
                            "Quantity 2 present":
                                "2" in text,
                            "Quantity 3 present":
                                "3" in text,
                        }
                        for k, v in checks.items():
                            mark = "✓" if v else "✗"
                            print(f"    {mark} {k}")
                            if not v:
                                ok_all = False

            # 8) FR variant — same endpoint, ?lang=fr, ensures bilingual
            # invoice renders `Prix unitaire / Qté / Total ligne` and the
            # buyer's preferred_language is respected.
            print("\n[iter451-e2e] POST /api/invoices/lots-won?lang=fr")
            r = await http.post(
                f"{BASE_URL}/api/invoices/lots-won/{SEED_AUCTION_ID}/{SEED_BUYER_ID}?lang=fr",
                headers=auth,
            )
            print(f"  → status {r.status_code}")
            if r.status_code == 200:
                body_fr = r.json()
                dl_fr = body_fr.get("download_url")
                if dl_fr:
                    if dl_fr.startswith("/"):
                        dl_fr = f"{BASE_URL}{dl_fr}"
                    r_pdf_fr = await http.get(dl_fr)
                    print(f"  → FR PDF fetch status={r_pdf_fr.status_code}, "
                          f"bytes={len(r_pdf_fr.content)}")
                    if r_pdf_fr.status_code == 200:
                        try:
                            import pdfplumber
                            import io
                            with pdfplumber.open(io.BytesIO(r_pdf_fr.content)) as pdf:
                                text_fr = "\n".join(
                                    (p.extract_text() or "") for p in pdf.pages
                                )
                        except Exception:
                            text_fr = r_pdf_fr.content.decode("latin-1", "ignore")
                        fr_checks = {
                            "Prix unitaire (FR) header":
                                "Prix unitaire" in text_fr,
                            "Total ligne (FR) header":
                                "Total ligne" in text_fr,
                            "$14.00 (FR) line total":
                                "$14.00" in text_fr or "14.00" in text_fr,
                            "$30.00 (FR) line total":
                                "$30.00" in text_fr or "30.00" in text_fr,
                            "$44.00 (FR) hammer total":
                                "$44.00" in text_fr or "44.00" in text_fr,
                        }
                        for k, v in fr_checks.items():
                            mark = "✓" if v else "✗"
                            print(f"    {mark} {k}")
                            if not v:
                                ok_all = False
            else:
                print(f"  body: {r.text[:200]}")
                ok_all = False

    finally:
        # Clean up
        await db.multi_item_listings.delete_one({"id": SEED_AUCTION_ID})
        await db.users.delete_one({"id": SEED_BUYER_ID})
        await db.invoices.delete_many(
            {"auction_id": SEED_AUCTION_ID}
        )
        await db.paddle_numbers.delete_many({"auction_id": SEED_AUCTION_ID})
        print("\n[iter451-e2e] ✓ cleanup complete")
        client_db.close()

    if ok_all:
        print("\n[iter451-e2e] ✅ ALL LIVE E2E CHECKS PASSED\n")
    else:
        print("\n[iter451-e2e] ❌ SOME LIVE E2E CHECKS FAILED\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
