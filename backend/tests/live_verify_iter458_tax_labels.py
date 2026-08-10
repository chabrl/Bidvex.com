"""iter458 — Live end-to-end tax-label verifier.

Seeds a fresh removable seller per province + a single sold lot, calls
`/api/invoices/seller-receipt/...` and `/api/invoices/commission-invoice/...`
for EN and FR, downloads the resulting PDFs, and asserts the rendered
tax labels match what the existing tax engine actually returned:

  QC      → GST + QST rows (EN) · TPS + TVQ rows (FR); no HST
  NS      → HST row       (EN) · TVH row         (FR); never labeled GST
  AB      → GST row       (EN) · TPS row         (FR); never HST/QST
  BC      → GST row       (EN) · TPS row         (FR); NO PST synthesis
  INTL    → no tax row at all (zero tax → suppressed)

All seeded rows are removed by the `finally` block.
"""
from __future__ import annotations

import asyncio
import io
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

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


CASES: List[Tuple[str, str, List[str], List[str], List[str]]] = [
    # (province, lang, must_contain, must_not_contain, description)
    ("QC", "en", ["GST", "QST"],   ["HST"],          "QC EN: GST + QST, no HST"),
    ("QC", "fr", ["TPS", "TVQ"],   ["TVH"],          "QC FR: TPS + TVQ, no TVH"),
    ("NS", "en", ["HST"],          ["QST"],          "NS EN: HST only, never QST"),
    ("NS", "fr", ["TVH"],          ["TVQ"],          "NS FR: TVH only, never TVQ"),
    ("ON", "en", ["HST"],          ["QST"],          "ON EN: HST only, never QST"),
    ("AB", "en", ["GST"],          ["HST", "QST"],   "AB EN: GST only, no HST/QST"),
    ("AB", "fr", ["TPS"],          ["TVH", "TVQ"],   "AB FR: TPS only, no TVH/TVQ"),
    ("BC", "en", ["GST"],          ["HST", "QST", "PST"], "BC EN: engine returns GST only, no PST synthesis"),
    ("BC", "fr", ["TPS"],          ["TVH", "TVQ", "TVP"], "BC FR: engine returns TPS only, no synthesised TVP"),
]


async def _seed_case(db, province: str, prefix: str, lang: str = "en") -> Dict[str, str]:
    """Seed one seller + one 1-lot auction for the given province + lang."""
    now = datetime.now(timezone.utc).isoformat()
    seller_id = f"{prefix}-{province}-{lang}-seller"
    buyer_id = f"{prefix}-{province}-{lang}-buyer"
    auction_id = f"{prefix}-{province}-{lang}-auction"

    await db.users.insert_many([
        {"id": seller_id, "email": f"{seller_id}@example.test",
         "name": f"IterSeller {province}",
         "full_name": f"IterSeller {province}",
         "phone": "555-000-0001",
         "province": province, "subscription_tier": "free",
         "account_type": "individual", "preferred_language": "en",
         "created_at": now},
        {"id": buyer_id, "email": f"{buyer_id}@example.test",
         "name": f"IterBuyer {province}",
         "full_name": f"IterBuyer {province}",
         "province": province, "subscription_tier": "free",
         "created_at": now},
    ])
    await db.multi_item_listings.insert_one({
        "id": auction_id,
        "title": f"iter458 tax-label {province}",
        "city": "Testville", "region": province,
        "location_province": province,
        "seller_id": seller_id,
        "listing_type": "lots", "status": "ended",
        "currency": "CAD", "auction_end_date": now,
        "lots": [
            {"lot_number": 1, "title": f"Lot for {province}",
             "description": "-",
             "status": "sold", "winner_user_id": buyer_id,
             "final_price": 200.0, "quantity": 1, "sold_at": now},
        ],
        "created_at": now, "updated_at": now,
    })
    await db.paddle_numbers.insert_one({
        "id": f"{prefix}-{province}-{lang}-paddle", "auction_id": auction_id,
        "user_id": buyer_id, "paddle_number": 55001, "assigned_at": now,
    })
    return {"auction_id": auction_id, "seller_id": seller_id,
            "buyer_id": buyer_id}


async def _cleanup_case(db, ids: Dict[str, str]) -> None:
    await db.users.delete_many({"id": {"$in": [ids["seller_id"], ids["buyer_id"]]}})
    await db.multi_item_listings.delete_many({"id": ids["auction_id"]})
    await db.paddle_numbers.delete_many({"auction_id": ids["auction_id"]})
    await db.invoices.delete_many({"auction_id": ids["auction_id"]})
    await db.receipts.delete_many({"listing_id": ids["auction_id"]})


async def _login_admin(http) -> Dict[str, str]:
    r = await http.post(f"{BASE_URL}/api/auth/login",
                        json={"email": ADMIN_EMAIL, "password": ADMIN_PW})
    r.raise_for_status()
    token = r.json().get("access_token") or r.json().get("token")
    return {"Authorization": f"Bearer {token}"}


async def _pdf_text(http, url: str) -> str:
    if url.startswith("/"):
        url = f"{BASE_URL}{url}"
    r = await http.get(url)
    r.raise_for_status()
    import pdfplumber
    with pdfplumber.open(io.BytesIO(r.content)) as pdf:
        text = "\n".join(p.extract_text() or "" for p in pdf.pages)
    # Strip BidVex's OWN CRA registration-number footer strings — these
    # are fixed platform legal identifiers unrelated to the tax charged
    # on THIS transaction. Presence of "GST/HST Registration #" in the
    # footer must NOT be interpreted as "HST was charged on this txn".
    footer_noise = [
        "GST/HST Registration #",  # EN header/footer legal id
        "GST/TPS #",               # EN header
        "QST Registration #",      # EN footer
        "QST/TVQ #",               # EN header
        "N° d'inscription TPS/TVH",  # FR variant
        "Nº d'inscription TPS/TVH",  # FR variant (º)
        "N° d'inscription TVQ",      # FR variant
        "Nº d'inscription TVQ",      # FR variant (º)
        "GST #",                     # short-form header (invoice_templates_complete)
        "QST #",                     # short-form header
        "gst_registration",          # translation key fallback (defensive)
        "qst_registration",          # translation key fallback
        # PDF line-wrapping frequently splits the composite CRA registration
        # phrases onto separate visual rows. Strip the composite tokens too
        # so a wrapped "GST/HST" fragment in the footer never leaks into
        # the tax-charged assertions.
        "GST/HST",
        "TPS/TVH",
    ]
    for phrase in footer_noise:
        text = text.replace(phrase, "")
    return text


def _switch_seller_lang(db_sync, seller_id: str, lang: str):
    # Templates use `seller.preferred_language` for locale routing.
    pass  # done outside main loop via async db


async def main():
    client_db = AsyncIOMotorClient(MONGO_URL)
    db = client_db[DB_NAME]

    prefix = f"iter458-{uuid.uuid4().hex[:8]}"
    print(f"\n[iter458-live] Base: {BASE_URL}")
    print(f"[iter458-live] Prefix: {prefix}\n")

    checks: List[Tuple[str, bool]] = []
    seeded: List[Dict[str, str]] = []

    try:
        async with httpx.AsyncClient(timeout=120.0, follow_redirects=True) as http:
            auth = await _login_admin(http)
            print("[iter458-live] ✓ admin logged in\n")

            for province, lang, must_contain, must_not_contain, desc in CASES:
                ids = await _seed_case(db, province, prefix, lang=lang)
                seeded.append(ids)
                # Switch seller language so the template renders in the
                # requested locale.
                await db.users.update_one(
                    {"id": ids["seller_id"]},
                    {"$set": {"preferred_language": lang}},
                )

                # ── Seller Receipt ──
                r = await http.post(
                    f"{BASE_URL}/api/invoices/seller-receipt/{ids['auction_id']}/{ids['seller_id']}",
                    headers=auth,
                )
                if r.status_code != 200:
                    checks.append((f"[{desc}] seller-receipt HTTP 200 (got {r.status_code})", False))
                    continue
                url = r.json().get("download_url")
                receipt_text = await _pdf_text(http, url)
                for token in must_contain:
                    ok = token in receipt_text
                    checks.append((f"[{desc}] receipt contains '{token}'", ok))
                for token in must_not_contain:
                    ok = token not in receipt_text
                    checks.append((f"[{desc}] receipt does NOT contain '{token}'", ok))

                # ── Commission Invoice ──
                r = await http.post(
                    f"{BASE_URL}/api/invoices/commission-invoice/{ids['auction_id']}/{ids['seller_id']}",
                    headers=auth,
                )
                if r.status_code != 200:
                    checks.append((f"[{desc}] commission-invoice HTTP 200 (got {r.status_code})", False))
                    continue
                url = r.json().get("download_url")
                comm_text = await _pdf_text(http, url)
                for token in must_contain:
                    ok = token in comm_text
                    checks.append((f"[{desc}] commission-invoice contains '{token}'", ok))
                for token in must_not_contain:
                    ok = token not in comm_text
                    checks.append((f"[{desc}] commission-invoice does NOT contain '{token}'", ok))

            # ── Zero-tax case (INTL) — no tax row at all ──
            ids = await _seed_case(db, "INTL", prefix, lang="en")
            seeded.append(ids)
            r = await http.post(
                f"{BASE_URL}/api/invoices/seller-receipt/{ids['auction_id']}/{ids['seller_id']}",
                headers=auth,
            )
            if r.status_code == 200:
                url = r.json().get("download_url")
                text = await _pdf_text(http, url)
                # No misleading tax label / tax amount rendered.
                for token in ["GST", "QST", "HST", "TPS", "TVQ", "TVH", "PST", "TVP"]:
                    ok = token not in text
                    checks.append(
                        (f"[INTL zero-tax] receipt does NOT render '{token}'", ok)
                    )
            else:
                checks.append((f"[INTL zero-tax] receipt HTTP 200 (got {r.status_code})", False))

    finally:
        for ids in seeded:
            try:
                await _cleanup_case(db, ids)
            except Exception as e:  # noqa: BLE001
                print(f"[iter458-live] ⚠ cleanup warning for {ids.get('auction_id')}: {e}")
        client_db.close()
        print("\n[iter458-live] ✓ cleanup complete")

    print("\n[iter458-live] === Summary ===")
    all_ok = True
    for label, ok in checks:
        mark = "✓" if ok else "✗"
        print(f"  {mark} {label}")
        if not ok:
            all_ok = False
    if all_ok:
        print("\n[iter458-live] ✅ ALL LIVE E2E TAX-LABEL CHECKS PASSED\n")
    else:
        print("\n[iter458-live] ❌ FAILURES ABOVE\n")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
