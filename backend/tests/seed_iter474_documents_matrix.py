"""iter474 — Removable preview seed for dashboard document access tests.

Seeds two buyers, two sellers, and one auction per section (marketplace,
multi-lot lots, vehicle multi-lot, storage). Every paid receipt row + the
corresponding `db.invoices` PDF record + a minimal valid PDF in S3 are
created so the dashboard document-access endpoints have real signed
downloads to resolve.

Cleanup with `--cleanup`. Nothing outside the seeded rows (identified by
`iter474ui_seed: True`) is touched.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

BACKEND = Path("/app/backend")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # type: ignore
load_dotenv(BACKEND / ".env")

from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore

from services.cloud_storage import store_invoice_pdf  # noqa: E402

PREFIX = "iter474ui-"

# Minimal valid PDF (single blank page) — 244 bytes. Enough for
# `/api/invoices/download/{id}` to return `application/pdf` with content.
_MIN_PDF = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Count 1/Kids[3 0 R]>>endobj\n"
    b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 612 792]"
    b"/Contents 4 0 R/Resources<<>>>>endobj\n"
    b"4 0 obj<</Length 44>>stream\n"
    b"BT /F1 12 Tf 50 750 Td (iter474 preview PDF) Tj ET\n"
    b"endstream endobj\n"
    b"xref\n0 5\n"
    b"0000000000 65535 f \n"
    b"0000000009 00000 n \n"
    b"0000000053 00000 n \n"
    b"0000000097 00000 n \n"
    b"0000000178 00000 n \n"
    b"trailer<</Size 5/Root 1 0 R>>\nstartxref\n265\n%%EOF\n"
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _ensure_user(db, *, email: str, name: str, role: str,
                       password: str | None = None) -> str:
    doc = await db.users.find_one({"email": email}, {"_id": 0, "id": 1})
    if doc:
        return doc["id"]
    from routes.auth import hash_password  # type: ignore

    uid = str(uuid.uuid4())
    hashed = hash_password(password or "IterTestPwd!123")
    await db.users.insert_one({
        "id": uid, "email": email, "name": name, "password": hashed,
        "role": role, "account_type": role,
        "phone_verified": True, "email_verified": True, "id_verified": True,
        "phone": "+15145550100", "preferred_language": "en",
        "created_at": _now(),
        "iter474ui_seed": True,
    })
    return uid


async def _store_pdf_invoice(
    db, *,
    invoice_id: str,
    invoice_type: str,          # e.g. "lots_won", "seller_statement"
    owner_field: str,           # "user_id" or "buyer_id"
    owner_id: str,
    auction_field: str,         # "auction_id" or "listing_id"
    auction_id: str,
    invoice_number: str,
    subfolder: str,
    type_field: str = "invoice_type",  # some rows use `type` instead
    extra: dict | None = None,
) -> None:
    """Upload a real PDF to S3 + persist the invoice row so the signed
    download URL will return `200 application/pdf`."""
    path = await store_invoice_pdf(invoice_id, _MIN_PDF, subfolder=subfolder)
    row = {
        "id":            invoice_id,
        type_field:      invoice_type,
        owner_field:     owner_id,
        auction_field:   auction_id,
        "invoice_number": invoice_number,
        "storage_path":  path,
        "generated_date": _now(),
        "status":        "generated",
        "iter474ui_seed": True,
    }
    if extra:
        row.update(extra)
    await db.invoices.insert_one(row)


async def _insert_receipt(
    db, *, section: str, user_id: str, buyer_or_seller: str,
    listing_id: str, lot_number, listing_title: str,
) -> str:
    rid = str(uuid.uuid4())
    await db.receipts.insert_one({
        "id":            rid,
        "type":          "buyer_receipt" if buyer_or_seller == "buyer" else "seller_statement",
        "user_id":       user_id,
        "section":       section,
        "listing_id":    listing_id,
        "lot_number":    lot_number,
        "listing_title": listing_title,
        "hammer_price":  100.0, "platform_fee": 5.0, "taxes": 14.975,
        "processing_fee": 0.0, "total_charged": 120.0, "net_payout": 95.0,
        "currency": "CAD", "created_at": _now(),
        "iter474ui_seed": True,
    })
    return rid


async def seed(db):
    # ── Actors ───────────────────────────────────────────────
    buyer_a = await _ensure_user(
        db, email="testbuyer@bidvex.com",
        name="Test Buyer", role="user",
    )
    buyer_b = await _ensure_user(
        db, email="iter474_buyer_b@test.com",
        name="Cross Buyer B", role="user",
    )
    seller_a = await _ensure_user(
        db, email="testseller@bidvex.com",
        name="Test Seller", role="user",
    )
    seller_b = await _ensure_user(
        db, email="iter474_seller_b@test.com",
        name="Cross Seller B", role="user",
    )

    print(f"[iter474ui] actors: buyerA={buyer_a[:8]} buyerB={buyer_b[:8]}"
          f" sellerA={seller_a[:8]} sellerB={seller_b[:8]}")

    # ═════════════════════════════════════════════════════════
    # A. MARKETPLACE (single-item) — buyer_a from seller_a
    # ═════════════════════════════════════════════════════════
    lid_mkt = f"{PREFIX}mkt-{uuid.uuid4().hex[:8]}"
    await db.listings.insert_one({
        "id":            lid_mkt,
        "title":         "iter474 · Marketplace test item",
        "final_price":   120.00, "current_price": 120.00, "status": "sold",
        "winner_user_id": buyer_a, "seller_id": seller_a,
        "sold_at":       _now(),
        "iter474ui_seed": True,
    })
    await _insert_receipt(
        db, section="marketplace", user_id=buyer_a, buyer_or_seller="buyer",
        listing_id=lid_mkt, lot_number=None,
        listing_title="iter474 · Marketplace test item",
    )
    await _insert_receipt(
        db, section="marketplace", user_id=seller_a, buyer_or_seller="seller",
        listing_id=lid_mkt, lot_number=None,
        listing_title="iter474 · Marketplace test item",
    )
    # Buyer PDF invoice — marketplace_purchase
    await _store_pdf_invoice(
        db, invoice_id=str(uuid.uuid4()),
        invoice_type="marketplace_purchase",
        owner_field="buyer_id", owner_id=buyer_a,
        auction_field="listing_id", auction_id=lid_mkt,
        invoice_number=f"BV-MKT-{lid_mkt[-6:].upper()}",
        subfolder="marketplace_purchase",
        type_field="type",
        extra={"seller_id": seller_a},
    )

    # ═════════════════════════════════════════════════════════
    # B. MULTI-LOT — buyer_a wins lots 1, 2, 3 from seller_a
    # ═════════════════════════════════════════════════════════
    lid_multi = f"{PREFIX}lot-{uuid.uuid4().hex[:8]}"
    await db.multi_item_listings.insert_one({
        "id":         lid_multi,
        "title":      "iter474 · Estate multi-lot",
        "status":     "ended",
        "seller_id":  seller_a,
        "lots": [
            {"lot_number": 1, "title": "Lot 1", "description": "l1",
             "quantity": 1, "current_price": 45.0, "starting_price": 20.0,
             "status": "sold", "winner_user_id": buyer_a,
             "payment_status": "payment_collected"},
            {"lot_number": 2, "title": "Lot 2", "description": "l2",
             "quantity": 2, "current_price": 60.0, "starting_price": 30.0,
             "status": "sold", "winner_user_id": buyer_a,
             "payment_status": "payment_collected"},
            {"lot_number": 3, "title": "Lot 3", "description": "l3",
             "quantity": 1, "current_price": 85.0, "starting_price": 40.0,
             "status": "sold", "winner_user_id": buyer_a,
             "payment_status": "payment_collected"},
        ],
        "iter474ui_seed": True,
    })
    for ln, title in [(1, "Lot 1"), (2, "Lot 2"), (3, "Lot 3")]:
        await _insert_receipt(
            db, section="lots", user_id=buyer_a, buyer_or_seller="buyer",
            listing_id=lid_multi, lot_number=ln,
            listing_title=title,
        )
        await _insert_receipt(
            db, section="lots", user_id=seller_a, buyer_or_seller="seller",
            listing_id=lid_multi, lot_number=ln,
            listing_title=title,
        )

    # SINGLE order-level PDFs (shared across all 3 lot rows).
    # Buyer: lots_won invoice + payment_letter
    lots_won_id = str(uuid.uuid4())
    await _store_pdf_invoice(
        db, invoice_id=lots_won_id,
        invoice_type="lots_won",
        owner_field="user_id", owner_id=buyer_a,
        auction_field="auction_id", auction_id=lid_multi,
        invoice_number=f"BV-INV-{lid_multi[-6:].upper()}",
        subfolder="lots_won",
    )
    await _store_pdf_invoice(
        db, invoice_id=str(uuid.uuid4()),
        invoice_type="payment_letter",
        owner_field="user_id", owner_id=buyer_a,
        auction_field="auction_id", auction_id=lid_multi,
        invoice_number=f"BV-PL-{lid_multi[-6:].upper()}",
        subfolder="payment_letter",
        extra={"language": "en"},
    )
    # Seller: statement + seller_receipt + commission_invoice
    for inv_type, subfolder, num_prefix in [
        ("seller_statement",   "seller_statement",   "BV-STMT"),
        ("seller_receipt",     "seller_receipt",     "BV-RCPT"),
        ("commission_invoice", "commission_invoice", "BV-COMM"),
    ]:
        await _store_pdf_invoice(
            db, invoice_id=str(uuid.uuid4()),
            invoice_type=inv_type,
            owner_field="user_id", owner_id=seller_a,
            auction_field="auction_id", auction_id=lid_multi,
            invoice_number=f"{num_prefix}-{lid_multi[-6:].upper()}",
            subfolder=subfolder,
        )

    # ═════════════════════════════════════════════════════════
    # C. VEHICLE MULTI-LOT — buyer_a wins lot 1 from seller_a
    # ═════════════════════════════════════════════════════════
    lid_veh = f"{PREFIX}veh-{uuid.uuid4().hex[:8]}"
    await db.vehicle_listings.insert_one({
        "id":         lid_veh,
        "title":      "iter474 · Dealer vehicle multi-lot",
        "status":     "ended",
        "seller_id":  seller_a,
        "lots": [
            {"lot_number": 1, "title": "2019 Ford F-150 XLT",
             "vin": "1FTEW1E52KFA00074", "quantity": 1,
             "status": "sold", "winner_user_id": buyer_a},
            {"lot_number": 2, "title": "2020 Chevy Silverado",
             "vin": "3GCUYDED4LG500074", "quantity": 1},
        ],
        "iter474ui_seed": True,
    })
    await _insert_receipt(
        db, section="vehicles", user_id=buyer_a, buyer_or_seller="buyer",
        listing_id=lid_veh, lot_number=1,
        listing_title="2019 Ford F-150 XLT",
    )
    await _insert_receipt(
        db, section="vehicles", user_id=seller_a, buyer_or_seller="seller",
        listing_id=lid_veh, lot_number=1,
        listing_title="2019 Ford F-150 XLT",
    )
    # Buyer vehicle fees invoice (existing generator)
    await _store_pdf_invoice(
        db, invoice_id=str(uuid.uuid4()),
        invoice_type="vehicle_fees",
        owner_field="buyer_id", owner_id=buyer_a,
        auction_field="auction_id", auction_id=lid_veh,
        invoice_number=f"BV-VEH-{lid_veh[-6:].upper()}",
        subfolder="vehicle_fees",
        extra={"seller_id": seller_a},
    )
    # No vehicle-mode seller PDFs exist per the audit — omit deliberately.

    # ═════════════════════════════════════════════════════════
    # D. STORAGE — buyer_a from seller_a (no PDF generators wired)
    # ═════════════════════════════════════════════════════════
    lid_sto = f"{PREFIX}sto-{uuid.uuid4().hex[:8]}"
    await db.storage_auctions.insert_one({
        "id":        lid_sto,
        "title":     "iter474 · Storage unit test",
        "status":    "ended",
        "seller_id": seller_a,
        "iter474ui_seed": True,
    })
    await _insert_receipt(
        db, section="storage", user_id=buyer_a, buyer_or_seller="buyer",
        listing_id=lid_sto, lot_number=None,
        listing_title="iter474 · Storage unit test",
    )
    await _insert_receipt(
        db, section="storage", user_id=seller_a, buyer_or_seller="seller",
        listing_id=lid_sto, lot_number=None,
        listing_title="iter474 · Storage unit test",
    )
    # Storage has no PDF generator per audit — do not seed invoice rows.

    print(f"[iter474ui] seeded:")
    print(f"  marketplace listing = {lid_mkt}")
    print(f"  multi-lot listing   = {lid_multi}  (3 lots, 1 order invoice)")
    print(f"  vehicle listing     = {lid_veh}")
    print(f"  storage listing     = {lid_sto}  (no PDF — expect not_supported)")
    print(f"[iter474ui] Buyer A id = {buyer_a}")
    print(f"[iter474ui] Buyer B id = {buyer_b}")
    print(f"[iter474ui] Seller A id = {seller_a}")
    print(f"[iter474ui] Seller B id = {seller_b}")


async def cleanup(db):
    removed: dict[str, int] = {}
    for coll in ("users", "listings", "multi_item_listings",
                 "vehicle_listings", "storage_auctions", "receipts",
                 "invoices"):
        r = await db[coll].delete_many({"iter474ui_seed": True})
        removed[coll] = r.deleted_count
    print(f"[iter474ui] cleanup: {removed}")


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cleanup", action="store_true")
    args = p.parse_args()
    client = AsyncIOMotorClient(os.environ["MONGO_URL"], tz_aware=True)
    db = client[os.environ["DB_NAME"]]
    if args.cleanup:
        await cleanup(db)
    else:
        await cleanup(db)
        await seed(db)


if __name__ == "__main__":
    asyncio.run(main())
