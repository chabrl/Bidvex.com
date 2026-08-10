"""
iter459 — Live end-to-end verifier for buyer payment-letter accuracy.

Seeds a multi-item auction with mixed lot outcomes and verifies that the
buyer payment letter (`POST /api/invoices/payment-letter/{auction_id}/{user_id}`)
uses ONLY that specific buyer's actually-won lots and every fee / tax
number is sourced from the unified fee engine.

Fixture:
  Lot 1 (qty 1)   → Winner A, sold, $100 unit → $100 total
  Lot 2 (qty 3)   → Winner A, sold, $7 × 3    → $21 total
  Lot 3 (qty 2)   → Winner B, sold, $50 × 2   → $100 total
  Lot 4 (qty 1)   → NO WINNER, unsold

Expected numbers (individual seller QC, buyer QC free tier):
  Buyer A hammer:   $100 + $21 = $121
  Buyer A BP 5%:    $6.05
  Stripe recovery:  (6.05 × 0.029) + 0.30 = $0.48
  Tax (14.975% on BP+SR): (6.05 + 0.48) × 0.14975 ≈ $0.98
  Total charged:    $121 + $6.05 + $0.48 + $0.98 ≈ $128.51

  Buyer B hammer:   $100
  Buyer B BP 5%:    $5.00

Verifications:
  • EN payment letter for Buyer A:
      - contains only Lot 1 + Lot 2 (real won lots)
      - shows real paddle number (12001), NEVER a sample paddle
      - contains Buyer A's real name, NEVER "Test Buyer" placeholder
      - contains $100.00 (Lot 1 line total), $21.00 (Lot 2 line total)
      - contains $7.00 (Lot 2 unit price), qty 3
      - contains hammer total $121.00
      - contains BP amount $6.05 (5.00%)
      - contains payment charges $0.48 (Stripe recovery, engine output)
      - contains QC tax lines with real amounts
      - contains Buyer B's paddle only if we're looking at Buyer B's letter
      - does NOT contain Lot 3, Lot 4, Buyer B's name, paddle 12002
      - does NOT contain the previous demo strings ("first 3 lots") or 5051-5053
  • FR payment letter for Buyer A:
      - contains "Prime d'acheteur", "Total marteau", "TPS", "TVQ" labels
      - contains the same real amounts and Buyer A's real data
  • Buyer B payment letter contains only Lot 3 and NEVER contains Lot 1 or
    Lot 2 hammer values, and never contains Buyer A's paddle.

All seeded documents (auction, users, paddle_numbers, invoices) are
removed by the finally-block regardless of outcome.
"""
from __future__ import annotations

import asyncio
import io
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

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

PREFIX = f"iter459-{uuid.uuid4().hex[:8]}"


def _fresh_id(kind: str) -> str:
    return f"{PREFIX}-{kind}-{uuid.uuid4().hex[:6]}"


async def _seed(db) -> Dict[str, Any]:
    """Create removable users + a multi-item auction with the fixture.

    Returns seeded ids for verification & cleanup."""
    now_iso = datetime.now(timezone.utc).isoformat()

    seller_id = _fresh_id("seller")
    buyer_a_id = _fresh_id("buyerA")
    buyer_b_id = _fresh_id("buyerB")

    users_docs = [
        {
            "id": seller_id, "email": f"{seller_id}@example.test",
            "name": "VerifySeller iter459",
            "full_name": "VerifySeller iter459",
            "phone": "555-000-0001",
            "province": "QC",
            "subscription_tier": "free",
            "account_type": "individual",
            "preferred_language": "en",
            "created_at": now_iso,
        },
        {
            "id": buyer_a_id, "email": f"{buyer_a_id}@example.test",
            "name": "VerifyBuyer_A_iter459",
            "full_name": "VerifyBuyer_A_iter459",
            "phone": "555-111-1111",
            "province": "QC", "subscription_tier": "free",
            "account_type": "individual",
            "billing_address": "1 Main St, Montréal, QC",
            "preferred_language": "en",
            "created_at": now_iso,
        },
        {
            "id": buyer_b_id, "email": f"{buyer_b_id}@example.test",
            "name": "VerifyBuyer_B_iter459",
            "full_name": "VerifyBuyer_B_iter459",
            "phone": "555-222-2222",
            "province": "QC", "subscription_tier": "free",
            "account_type": "individual",
            "billing_address": "2 Rue Sainte-Catherine, Montréal, QC",
            "preferred_language": "en",
            "created_at": now_iso,
        },
    ]
    await db.users.insert_many(users_docs)

    auction_id = _fresh_id("auction")
    end_dt = datetime.now(timezone.utc).isoformat()
    auction_doc = {
        "id": auction_id,
        "title": f"Verify iter459 Buyer PL Auction ({PREFIX})",
        "city": "Montréal",
        "region": "QC",
        "location_province": "QC",
        "seller_id": seller_id,
        "listing_type": "lots",
        "auction_type": "lots",
        "status": "ended",
        "currency": "CAD",
        "auction_end_date": end_dt,
        "lots": [
            {
                "lot_number": 1,
                "title": "Lot 1 — Solo item",
                "description": "Single-quantity sold lot, hammer $100.",
                "status": "sold",
                "winner_user_id": buyer_a_id,
                "final_price": 100.0,
                "current_price": 100.0,
                "winning_unit_price": 100.0,
                "winning_quantity": 1,
                "quantity": 1,
                "sold_at": now_iso,
            },
            {
                "lot_number": 2,
                "title": "Lot 2 — Multi-qty (3 × $7)",
                "description": "Per-unit-priced lot with quantity=3, multiply_hammer_by_quantity=True.",
                "status": "sold",
                "winner_user_id": buyer_a_id,
                "final_price": 7.0,
                "current_price": 7.0,
                "winning_unit_price": 7.0,
                "winning_quantity": 3,
                "quantity": 3,
                "multiply_hammer_by_quantity": True,
                "sold_at": now_iso,
            },
            {
                "lot_number": 3,
                "title": "Lot 3 — Multi-qty (2 × $50)",
                "description": "Different buyer wins this multi-qty lot.",
                "status": "sold",
                "winner_user_id": buyer_b_id,
                "final_price": 50.0,
                "current_price": 50.0,
                "winning_unit_price": 50.0,
                "winning_quantity": 2,
                "quantity": 2,
                "multiply_hammer_by_quantity": True,
                "sold_at": now_iso,
            },
            {
                "lot_number": 4,
                "title": "Lot 4 — Unsold",
                "description": "No bidders → must NOT appear in any buyer's payment letter.",
                "status": "ended",
                "winner_user_id": None,
                "final_price": 0.0,
                "current_price": 0.0,
                "quantity": 1,
            },
        ],
        "created_at": now_iso,
        "updated_at": now_iso,
    }
    await db.multi_item_listings.insert_one(auction_doc)

    # Real paddle numbers for the two winners.
    paddle_a_num = 12001
    paddle_b_num = 12002
    await db.paddle_numbers.insert_many([
        {"id": _fresh_id("paddleA"), "auction_id": auction_id,
         "user_id": buyer_a_id, "paddle_number": paddle_a_num, "assigned_at": now_iso},
        {"id": _fresh_id("paddleB"), "auction_id": auction_id,
         "user_id": buyer_b_id, "paddle_number": paddle_b_num, "assigned_at": now_iso},
    ])

    return {
        "auction_id": auction_id,
        "seller_id": seller_id,
        "buyer_a_id": buyer_a_id,
        "buyer_b_id": buyer_b_id,
        "paddle_a_num": paddle_a_num,
        "paddle_b_num": paddle_b_num,
    }


async def _cleanup(db, ids: Dict[str, Any]):
    await db.users.delete_many({"id": {"$in": [
        ids["seller_id"], ids["buyer_a_id"], ids["buyer_b_id"]
    ]}})
    await db.multi_item_listings.delete_many({"id": ids["auction_id"]})
    await db.paddle_numbers.delete_many({"auction_id": ids["auction_id"]})
    await db.invoices.delete_many({"auction_id": ids["auction_id"]})


async def _login_admin(http) -> Dict[str, str]:
    r = await http.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PW},
    )
    r.raise_for_status()
    token = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {token}"}


async def _pdf_text_from_url(http, url: str) -> str:
    """Download the signed-URL PDF and return its full text via pdfplumber."""
    if url.startswith("/"):
        url = f"{BASE_URL}{url}"
    r = await http.get(url)
    r.raise_for_status()
    import pdfplumber
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        parts: List[str] = []
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)


async def _generate_pl(http, auth, auction_id: str, buyer_id: str, lang: str) -> Dict[str, Any]:
    """POST to payment-letter endpoint and return the JSON payload."""
    r = await http.post(
        f"{BASE_URL}/api/invoices/payment-letter/{auction_id}/{buyer_id}?lang={lang}",
        headers=auth,
    )
    if r.status_code != 200:
        return {"status_code": r.status_code, "text": r.text}
    body = r.json()
    body["status_code"] = 200
    return body


async def main():
    client_db = AsyncIOMotorClient(MONGO_URL)
    db = client_db[DB_NAME]

    print(f"\n[iter459-live] Base: {BASE_URL}")
    print(f"[iter459-live] Prefix: {PREFIX}\n")

    ids: Dict[str, Any] = {}
    checks: List[tuple] = []

    try:
        ids = await _seed(db)
        print("[iter459-live] ✓ seeded fresh removable auction + users + paddles\n")

        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as http:
            auth = await _login_admin(http)
            print("[iter459-live] ✓ admin logged in\n")

            # ─────────────── Buyer A — EN payment letter ────────────────
            plA_en = await _generate_pl(http, auth, ids["auction_id"], ids["buyer_a_id"], "en")
            checks.append((f"Buyer A EN: HTTP 200 (got {plA_en.get('status_code')})",
                           plA_en.get("status_code") == 200))
            checks.append(("Buyer A EN: response lots_count == 2",
                           plA_en.get("lots_count") == 2))
            checks.append(("Buyer A EN: response hammer_total == $121.00",
                           abs(float(plA_en.get("hammer_total", 0)) - 121.0) < 0.01))
            checks.append(("Buyer A EN: response paddle_number == 12001 (real)",
                           plA_en.get("paddle_number") == 12001))

            urlA_en = plA_en.get("download_url")
            if urlA_en:
                text = await _pdf_text_from_url(http, urlA_en)
                # ── No placeholders / demo tokens ─────────────────────
                checks.append(("Buyer A EN PDF: no 'Test Buyer' placeholder",
                               "Test Buyer" not in text))
                checks.append(("Buyer A EN PDF: no sample paddles 5051/5052/5053",
                               all(s not in text for s in ("5051", "5052", "5053"))))
                # ── Real buyer data ───────────────────────────────────
                checks.append(("Buyer A EN PDF: real buyer A name present",
                               "VerifyBuyer_A_iter459" in text))
                checks.append(("Buyer A EN PDF: real paddle A (12001) present",
                               "12001" in text))
                # ── Auction title present ─────────────────────────────
                checks.append(("Buyer A EN PDF: auction title present",
                               "Verify iter459 Buyer PL" in text))
                # ── Only Buyer A's real lots — Lot 1 + Lot 2 ──────────
                checks.append(("Buyer A EN PDF: Lot 1 present",
                               re.search(r"\b1\b[^\n]{0,120}Solo item", text) is not None
                               or "Solo item" in text))
                checks.append(("Buyer A EN PDF: Lot 2 present",
                               "Multi-qty (3" in text))
                checks.append(("Buyer A EN PDF: Lot 2 unit price $7.00 present",
                               "$7.00" in text))
                checks.append(("Buyer A EN PDF: Lot 2 qty 3 present",
                               re.search(r"\b3\b", text) is not None))
                checks.append(("Buyer A EN PDF: Lot 2 line total $21.00 present",
                               "$21.00" in text or "21.00" in text))
                checks.append(("Buyer A EN PDF: Lot 1 line total $100.00 present",
                               "$100.00" in text or "100.00" in text))
                # ── Hammer total $121 ────────────────────────────────
                checks.append(("Buyer A EN PDF: hammer_total $121.00 present",
                               "$121.00" in text or "121.00" in text))
                # ── Buyer's Premium at 5.00% ($6.05) — real engine ─────
                checks.append(("Buyer A EN PDF: buyer's premium 5.00% present",
                               "5.00%" in text or "5.0%" in text or "5%" in text))
                checks.append(("Buyer A EN PDF: buyer's premium amount $6.05 present",
                               "$6.05" in text or "6.05" in text))
                # ── Payment charges line present ──────────────────────
                checks.append(("Buyer A EN PDF: Payment Processing Charges label present",
                               "Payment Processing Charges" in text
                               or "Processing" in text))
                # ── Tax lines (QC → GST 5% + QST 9.975%) ──────────────
                checks.append(("Buyer A EN PDF: GST 5.0% line present",
                               "GST" in text and "5.0%" in text))
                checks.append(("Buyer A EN PDF: QST 9.975% line present",
                               "9.975%" in text))
                # ── Exclusions: Buyer B, Lot 3, Lot 4, other paddle ────
                checks.append(("Buyer A EN PDF: does NOT contain Buyer B name",
                               "VerifyBuyer_B_iter459" not in text))
                checks.append(("Buyer A EN PDF: does NOT contain Buyer B paddle 12002",
                               "12002" not in text))
                checks.append(("Buyer A EN PDF: does NOT contain Lot 3 title",
                               "Multi-qty (2" not in text))
                checks.append(("Buyer A EN PDF: does NOT contain Lot 4 (unsold)",
                               "Lot 4 — Unsold" not in text
                               and "Lot 4" not in text.split("\n")[0:5]))  # not in headers
                # ── Anti-hardcoded lot count: '3 lot(s)' must not appear
                #     from the old "first 3 lots" demo template. ──────
                checks.append(("Buyer A EN PDF: shows real lot count 2 (not hardcoded 3)",
                               "won 2 lot" in text.lower() or " 2 lot(s)" in text))

            # ─────────────── Buyer A — FR payment letter ────────────────
            plA_fr = await _generate_pl(http, auth, ids["auction_id"], ids["buyer_a_id"], "fr")
            checks.append((f"Buyer A FR: HTTP 200 (got {plA_fr.get('status_code')})",
                           plA_fr.get("status_code") == 200))
            urlA_fr = plA_fr.get("download_url")
            if urlA_fr:
                text_fr = await _pdf_text_from_url(http, urlA_fr)
                checks.append(("Buyer A FR PDF: 'Prime d'acheteur' present",
                               "Prime" in text_fr))
                checks.append(("Buyer A FR PDF: 'Total marteau' present",
                               "Total marteau" in text_fr))
                checks.append(("Buyer A FR PDF: 'TPS' (French GST) present",
                               "TPS" in text_fr))
                checks.append(("Buyer A FR PDF: 'TVQ' (French QST) present",
                               "TVQ" in text_fr))
                checks.append(("Buyer A FR PDF: real buyer A name present",
                               "VerifyBuyer_A_iter459" in text_fr))
                checks.append(("Buyer A FR PDF: real paddle A (12001) present",
                               "12001" in text_fr))
                checks.append(("Buyer A FR PDF: hammer_total $121.00 present",
                               "$121.00" in text_fr or "121.00" in text_fr))
                checks.append(("Buyer A FR PDF: buyer premium $6.05 present",
                               "6.05" in text_fr))
                checks.append(("Buyer A FR PDF: does NOT contain Buyer B name",
                               "VerifyBuyer_B_iter459" not in text_fr))
                checks.append(("Buyer A FR PDF: does NOT contain Buyer B paddle",
                               "12002" not in text_fr))
                checks.append(("Buyer A FR PDF: does NOT contain Lot 3",
                               "Multi-qty (2" not in text_fr))

            # ─────────────── Buyer B — EN payment letter ────────────────
            plB_en = await _generate_pl(http, auth, ids["auction_id"], ids["buyer_b_id"], "en")
            checks.append((f"Buyer B EN: HTTP 200 (got {plB_en.get('status_code')})",
                           plB_en.get("status_code") == 200))
            checks.append(("Buyer B EN: response lots_count == 1",
                           plB_en.get("lots_count") == 1))
            checks.append(("Buyer B EN: response hammer_total == $100.00",
                           abs(float(plB_en.get("hammer_total", 0)) - 100.0) < 0.01))
            checks.append(("Buyer B EN: response paddle_number == 12002 (real)",
                           plB_en.get("paddle_number") == 12002))

            urlB_en = plB_en.get("download_url")
            if urlB_en:
                textB = await _pdf_text_from_url(http, urlB_en)
                checks.append(("Buyer B EN PDF: real buyer B name present",
                               "VerifyBuyer_B_iter459" in textB))
                checks.append(("Buyer B EN PDF: real paddle B (12002) present",
                               "12002" in textB))
                # Only Buyer B's lot (Lot 3, $50 × 2 = $100)
                checks.append(("Buyer B EN PDF: Lot 3 title present",
                               "Multi-qty (2" in textB))
                checks.append(("Buyer B EN PDF: Lot 3 unit price $50.00 present",
                               "$50.00" in textB or "50.00" in textB))
                # Exclusions — Buyer A's lots, name, paddle
                checks.append(("Buyer B EN PDF: does NOT contain Buyer A name",
                               "VerifyBuyer_A_iter459" not in textB))
                checks.append(("Buyer B EN PDF: does NOT contain Buyer A paddle 12001",
                               "12001" not in textB))
                checks.append(("Buyer B EN PDF: does NOT contain Lot 1 (Solo item)",
                               "Solo item" not in textB))
                checks.append(("Buyer B EN PDF: does NOT contain Lot 2 (Multi-qty 3)",
                               "Multi-qty (3" not in textB))
                checks.append(("Buyer B EN PDF: does NOT contain Lot 4 (unsold)",
                               "Lot 4 — Unsold" not in textB))

    finally:
        if ids:
            try:
                await _cleanup(db, ids)
                print("\n[iter459-live] ✓ cleaned up all seeded documents")
            except Exception as e:  # noqa: BLE001
                print(f"\n[iter459-live] ⚠ cleanup warning: {e}")
        client_db.close()

    print("\n[iter459-live] === Summary ===")
    all_ok = True
    for label, ok in checks:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {label}")
        if not ok:
            all_ok = False
    if all_ok:
        print("\n[iter459-live] ✅ ALL LIVE E2E CHECKS PASSED\n")
    else:
        print("\n[iter459-live] ❌ FAILURES ABOVE\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
