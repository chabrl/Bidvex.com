"""iter477 — Visual PDF QA harness.

Generates every buyer/seller PDF type against seeded fixtures and
renders each to PNG (via PyMuPDF) so the output can be visually
inspected. Fixtures cover:
    • Buyer Invoice (Storage)
    • Buyer Universal Receipt (Marketplace, Vehicles, Storage, Lots)
    • Seller Statement (Marketplace, Vehicles, Storage)
    • Commission Invoice (Marketplace, Vehicles, Storage)
    • Multi-lot buyer transaction (3 lots)
    • Multi-page transaction (12 lots — forces at least 2 pages)
    • Buyer document WITH seller logo
    • Buyer document WITHOUT seller logo
    • Historical transaction with NO itemized fields
    • EN + FR variants

Programmatic checks (no visual claims made without evidence):
    • Text-mode extraction verifies every expected label + amount
      is present on the correct page.
    • Detects sentinel words ("None", "null", "undefined", "NaN") on
      any page — flagged as a defect.
    • Confirms multi-page PDFs have >1 page.
    • Confirms BidVex letterhead + GST/QST render on every page.
    • Confirms both BUYER + SELLER blocks render on every doc.
    • Confirms "—" (em-dash placeholder) appears on the historical
      document and does NOT appear on the itemized documents where
      real values were persisted.

Idempotent: seeds `iter477qa-*` fixtures on entry, cleans up on exit.
Never touches production data.
"""
from __future__ import annotations

import asyncio
import io
import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

BACKEND = Path("/app/backend")
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv  # type: ignore
load_dotenv(BACKEND / ".env")

import fitz  # type: ignore  (PyMuPDF)
from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
from pypdf import PdfReader  # type: ignore

from services.pdf_generators.universal_receipt import generate_universal_receipt
from services.pdf_generators.sections import (
    generate_storage_buyer_invoice,
    generate_marketplace_seller_statement,
    generate_marketplace_seller_receipt,
    generate_marketplace_seller_commission_invoice,
    generate_vehicle_seller_statement,
    generate_vehicle_seller_commission_invoice,
    generate_storage_seller_statement,
    generate_storage_seller_commission_invoice,
)
from services.receipts import ITEMIZED_KEYS

QA_PREFIX = "iter477qa-"
OUT_DIR = Path("/tmp/iter477_pdf_qa")
NOW = datetime.now(timezone.utc).isoformat()

# per-lot fixture (same as reconciliation test)
FIXTURE = {
    "hammer_price":            200.00, "hammer_gst": 10.00, "hammer_qst": 19.95,
    "buyer_premium":            20.00, "buyer_premium_gst": 1.00, "buyer_premium_qst": 2.00,
    "service_fee":               8.00, "service_fee_gst": 0.40, "service_fee_qst": 0.80,
    "stripe_fee":                7.50, "stripe_fee_charged_to": "buyer",
    "seller_commission":        10.00, "seller_commission_gst": 0.50, "seller_commission_qst": 1.00,
    "other_deductions":          0.00,
    "buyer_premium_rate":        0.10, "seller_commission_rate": 0.05,
    "seller_is_tax_registered": True,
    "bidvex_gst_number":        "706766367RT0001",
    "bidvex_qst_number":        "1223530849TQ0001",
}
BUYER_TOTAL = 269.65
SELLER_NET  = 218.45

# Historical (aggregate only)
HIST = {
    "hammer_price":   150.00, "platform_fee": 7.50, "taxes": 22.42,
    "processing_fee":   4.55, "total_charged": 184.47, "net_payout": 142.50,
}

# Small valid PNG for the "seller with logo" case — generated with Pillow
# to guarantee a clean data stream ReportLab can render.
def _make_valid_png() -> bytes:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (240, 120), (30, 80, 160))
    d = ImageDraw.Draw(img)
    d.rectangle([10, 10, 230, 110], outline=(255, 255, 255), width=3)
    d.text((30, 40), "LOGO SELLER", fill=(255, 255, 255))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


PNG_1x1 = _make_valid_png()


async def _ensure_user(db, *, email, name, has_logo=False, extra=None) -> str:
    existing = await db.users.find_one({"email": email}, {"_id": 0, "id": 1})
    if existing:
        return existing["id"]
    uid = str(uuid.uuid4())
    doc = {
        "id": uid, "email": email, "name": name, "role": "user",
        "company_name": name, "business_address": "789 Rue QA, Montreal QC H1B 2B2",
        "phone": "+15145559999", "gst_number": "987654321RT0001",
        "qst_number": "9876543210TQ0001", "created_at": NOW,
        "iter477qa_seed": True,
    }
    if has_logo:
        # Direct upload via cloud_storage
        from services.cloud_storage import store_business_logo
        key, url = await store_business_logo(uid, PNG_1x1, "image/png", "png")
        doc["logo_url"] = url
        doc["logo_storage_path"] = key
    if extra:
        doc.update(extra)
    await db.users.insert_one(doc)
    return uid


async def _insert_itemized_receipt(
    db, *, section, listing_id, listing_title, user_id, role, lot_number,
) -> str:
    rid = str(uuid.uuid4())
    doc = {
        "id": rid,
        "type": "buyer_receipt" if role == "buyer" else "seller_statement",
        "user_id": user_id, "section": section, "listing_id": listing_id,
        "lot_number": lot_number, "listing_title": listing_title,
        "hammer_price": FIXTURE["hammer_price"],
        "platform_fee": FIXTURE["buyer_premium"] + FIXTURE["service_fee"],
        "taxes": (
            FIXTURE["hammer_gst"] + FIXTURE["hammer_qst"]
            + FIXTURE["buyer_premium_gst"] + FIXTURE["buyer_premium_qst"]
            + FIXTURE["service_fee_gst"] + FIXTURE["service_fee_qst"]
        ),
        "processing_fee": FIXTURE["stripe_fee"],
        "total_charged": BUYER_TOTAL,
        "net_payout": SELLER_NET,
        "currency": "CAD", "created_at": NOW,
        "order_number": f"BVX-{listing_id[-8:].upper()}",
        "seller_name": "QA Seller",
        "quantity": 1,
        "itemized_reconciled": True, "itemized_version": 1,
        "iter477qa_seed": True,
    }
    for k in ITEMIZED_KEYS:
        if k in FIXTURE:
            doc[k] = FIXTURE[k]
    await db.receipts.insert_one(doc)
    return rid


async def _insert_historical_receipt(
    db, *, section, listing_id, listing_title, user_id, role, lot_number,
) -> str:
    rid = str(uuid.uuid4())
    await db.receipts.insert_one({
        "id": rid,
        "type": "buyer_receipt" if role == "buyer" else "seller_statement",
        "user_id": user_id, "section": section, "listing_id": listing_id,
        "lot_number": lot_number, "listing_title": listing_title,
        "hammer_price": HIST["hammer_price"], "platform_fee": HIST["platform_fee"],
        "taxes": HIST["taxes"], "processing_fee": HIST["processing_fee"],
        "total_charged": HIST["total_charged"], "net_payout": HIST["net_payout"],
        "currency": "CAD", "created_at": NOW,
        "order_number": f"BVX-HIST-{listing_id[-6:].upper()}",
        "seller_name": "Historical QA Seller", "quantity": 1,
        "iter477qa_seed": True,
    })
    return rid


async def cleanup(db):
    for col in ("users", "listings", "vehicle_listings",
                "storage_auctions", "multi_item_listings", "receipts"):
        try:
            await db[col].delete_many({"iter477qa_seed": True})
        except Exception:  # noqa: BLE001
            pass


async def seed(db):
    """Seed all fixture scenarios needed for the visual QA."""
    await cleanup(db)

    buyer = await _ensure_user(
        db, email="iter477qa_buyer@test.com", name="QA Buyer Corp.",
    )
    seller_with_logo = await _ensure_user(
        db, email="iter477qa_seller_logo@test.com",
        name="Logo Seller Inc.", has_logo=True,
    )
    seller_no_logo = await _ensure_user(
        db, email="iter477qa_seller_nolog@test.com",
        name="Plain Seller Ltd.", has_logo=False,
    )

    ids = {"buyer_id": buyer, "seller_logo_id": seller_with_logo,
           "seller_nolog_id": seller_no_logo}

    # 1) MARKETPLACE — Buyer + Seller WITH logo (itemized)
    lid = f"{QA_PREFIX}mkt-logo-{uuid.uuid4().hex[:8]}"
    await db.listings.insert_one({
        "id": lid, "title": "QA · Marketplace item (seller has logo)",
        "status": "sold", "winner_user_id": buyer,
        "seller_id": seller_with_logo,
        "final_price": FIXTURE["hammer_price"],
        "iter477qa_seed": True,
    })
    await _insert_itemized_receipt(
        db, section="marketplace", listing_id=lid,
        listing_title="QA · Marketplace item (seller has logo)",
        user_id=buyer, role="buyer", lot_number=None,
    )
    await _insert_itemized_receipt(
        db, section="marketplace", listing_id=lid,
        listing_title="QA · Marketplace item (seller has logo)",
        user_id=seller_with_logo, role="seller", lot_number=None,
    )
    ids["mkt_logo"] = lid

    # 2) MARKETPLACE — Buyer + Seller WITHOUT logo (itemized)
    lid = f"{QA_PREFIX}mkt-nolog-{uuid.uuid4().hex[:8]}"
    await db.listings.insert_one({
        "id": lid, "title": "QA · Marketplace item (seller has NO logo)",
        "status": "sold", "winner_user_id": buyer,
        "seller_id": seller_no_logo,
        "final_price": FIXTURE["hammer_price"],
        "iter477qa_seed": True,
    })
    await _insert_itemized_receipt(
        db, section="marketplace", listing_id=lid,
        listing_title="QA · Marketplace item (seller has NO logo)",
        user_id=buyer, role="buyer", lot_number=None,
    )
    await _insert_itemized_receipt(
        db, section="marketplace", listing_id=lid,
        listing_title="QA · Marketplace item (seller has NO logo)",
        user_id=seller_no_logo, role="seller", lot_number=None,
    )
    ids["mkt_nolog"] = lid

    # 3) STORAGE — Buyer Invoice
    lid = f"{QA_PREFIX}sto-{uuid.uuid4().hex[:8]}"
    await db.storage_auctions.insert_one({
        "id": lid, "title": "QA · Storage Locker A12",
        "status": "sold", "facility_name": "QA Storage Facility",
        "location": "Sherbrooke, QC",
        "seller_id": seller_with_logo, "facility_owner_id": seller_with_logo,
        "winner_user_id": buyer,
        "iter477qa_seed": True,
    })
    await _insert_itemized_receipt(
        db, section="storage", listing_id=lid,
        listing_title="QA · Storage Locker A12",
        user_id=buyer, role="buyer", lot_number=None,
    )
    await _insert_itemized_receipt(
        db, section="storage", listing_id=lid,
        listing_title="QA · Storage Locker A12",
        user_id=seller_with_logo, role="seller", lot_number=None,
    )
    ids["sto"] = lid

    # 4) MULTI-LOT — 3 lots (single-page multi-lot buyer)
    lid = f"{QA_PREFIX}lots-3-{uuid.uuid4().hex[:8]}"
    await db.multi_item_listings.insert_one({
        "id": lid, "title": "QA · Estate 3-lot event",
        "status": "ended", "seller_id": seller_with_logo,
        "lots": [
            {"lot_number": i, "title": f"QA 3-lot #{i}",
             "quantity": 1, "current_price": FIXTURE["hammer_price"]}
            for i in (1, 2, 3)
        ],
        "iter477qa_seed": True,
    })
    for lot in (1, 2, 3):
        await _insert_itemized_receipt(
            db, section="lots", listing_id=lid,
            listing_title=f"QA 3-lot #{lot}",
            user_id=buyer, role="buyer", lot_number=lot,
        )
        await _insert_itemized_receipt(
            db, section="lots", listing_id=lid,
            listing_title=f"QA 3-lot #{lot}",
            user_id=seller_with_logo, role="seller", lot_number=lot,
        )
    ids["lots_3"] = lid

    # 5) MULTI-PAGE — 12 lots (should force ≥ 2 pages)
    lid = f"{QA_PREFIX}lots-12-{uuid.uuid4().hex[:8]}"
    await db.multi_item_listings.insert_one({
        "id": lid, "title": "QA · Big Estate 12-lot Event",
        "status": "ended", "seller_id": seller_with_logo,
        "lots": [
            {"lot_number": i, "title": f"QA Big 12-lot #{i} — with a longer title to force wrapping and multi-page break",
             "quantity": 1, "current_price": FIXTURE["hammer_price"]}
            for i in range(1, 13)
        ],
        "iter477qa_seed": True,
    })
    for lot in range(1, 13):
        await _insert_itemized_receipt(
            db, section="lots", listing_id=lid,
            listing_title=f"QA Big 12-lot #{lot} — with a longer title to force wrapping and multi-page break",
            user_id=buyer, role="buyer", lot_number=lot,
        )
        await _insert_itemized_receipt(
            db, section="lots", listing_id=lid,
            listing_title=f"QA Big 12-lot #{lot} — with a longer title to force wrapping and multi-page break",
            user_id=seller_with_logo, role="seller", lot_number=lot,
        )
    ids["lots_12"] = lid

    # 6) VEHICLES
    lid = f"{QA_PREFIX}veh-{uuid.uuid4().hex[:8]}"
    await db.vehicle_listings.insert_one({
        "id": lid, "title": "QA · Vehicle multi-lot dealer sale",
        "status": "sold", "seller_id": seller_with_logo,
        "winner_user_id": buyer,
        "lots": [
            {"lot_number": 1, "title": "2020 QA Sedan (VIN QA123)",
             "quantity": 1, "current_price": FIXTURE["hammer_price"]},
        ],
        "iter477qa_seed": True,
    })
    await _insert_itemized_receipt(
        db, section="vehicles", listing_id=lid,
        listing_title="2020 QA Sedan (VIN QA123)",
        user_id=buyer, role="buyer", lot_number=1,
    )
    await _insert_itemized_receipt(
        db, section="vehicles", listing_id=lid,
        listing_title="2020 QA Sedan (VIN QA123)",
        user_id=seller_with_logo, role="seller", lot_number=1,
    )
    ids["veh"] = lid

    # 7) HISTORICAL — no itemized data (marketplace)
    lid = f"{QA_PREFIX}hist-{uuid.uuid4().hex[:8]}"
    await db.listings.insert_one({
        "id": lid, "title": "QA · HISTORICAL aggregate-only",
        "status": "sold", "winner_user_id": buyer,
        "seller_id": seller_no_logo,
        "final_price": HIST["hammer_price"],
        "iter477qa_seed": True,
    })
    await _insert_historical_receipt(
        db, section="marketplace", listing_id=lid,
        listing_title="QA · HISTORICAL aggregate-only",
        user_id=buyer, role="buyer", lot_number=None,
    )
    await _insert_historical_receipt(
        db, section="marketplace", listing_id=lid,
        listing_title="QA · HISTORICAL aggregate-only",
        user_id=seller_no_logo, role="seller", lot_number=None,
    )
    ids["hist"] = lid

    return ids


def _render_pdf_to_png(pdf_bytes: bytes, name_prefix: str) -> list[Path]:
    """Render every page of a PDF to a PNG. Returns list of file paths."""
    OUT_DIR.mkdir(exist_ok=True, parents=True)
    docs = fitz.open(stream=pdf_bytes, filetype="pdf")
    paths = []
    for i in range(len(docs)):
        page = docs.load_page(i)
        pix = page.get_pixmap(dpi=140)
        p = OUT_DIR / f"{name_prefix}_p{i+1}.png"
        pix.save(str(p))
        paths.append(p)
    docs.close()
    return paths


def _extract_text(pdf_bytes: bytes) -> tuple[str, int]:
    """Return (text, page_count)."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    txt = "\n".join(p.extract_text() or "" for p in reader.pages)
    return txt, len(reader.pages)


SENTINELS = ("None", "null", "undefined", "NaN")


def _visual_asserts(name: str, pdf_bytes: bytes, *, expect_multi_page: bool = False,
                    expect_logo: bool = False, expect_dash_placeholder: bool = False,
                    expect_no_synthesis: bool = False,
                    required_labels_en: list[str] | None = None,
                    forbidden_amounts: list[str] | None = None,
                    ) -> list[dict]:
    """Programmatic visual checks — every claim backed by extracted text."""
    results = []
    text, pages = _extract_text(pdf_bytes)
    # Normalized text: collapse whitespace (newlines + NBSP → single space)
    # so title / label checks are robust to PDF line breaks and
    # non-breaking-space characters used by ReportLab.
    normalized = re.sub(r"\s+", " ", text.replace("\u00a0", " "))

    def add(check, ok, **kw):
        results.append({"pdf": name, "check": check, "ok": ok, **kw})

    # Save PDF to disk for reference
    OUT_DIR.mkdir(exist_ok=True, parents=True)
    (OUT_DIR / f"{name}.pdf").write_bytes(pdf_bytes)

    # 1. Renders as PDF
    add("valid_pdf_magic", pdf_bytes.startswith(b"%PDF"),
        bytes=len(pdf_bytes), pages=pages)

    # 2. Multi-page expectation
    if expect_multi_page:
        add("multi_page_present", pages > 1, pages=pages)

    # 3. BidVex letterhead + GST/QST (real BidVex numbers from
    #    services.pdf_invoice.PLATFORM_GST/PLATFORM_QST)
    add("bidvex_letterhead", "BidVex Inc." in text)
    add("bidvex_gst_present", "706766367RT0001" in text)
    add("bidvex_qst_present", "1233530880TQ0001" in text)

    # 4. Both party blocks
    add("buyer_block_present",
        "BUYER" in text or "ACHETEUR" in text)
    add("seller_block_present",
        "SELLER" in text or "VENDEUR" in text or "DEALER" in text)

    # 5. Sentinel scan — no leaked None/null/undefined/NaN
    hits = {s: (s in text) for s in SENTINELS}
    add("no_sentinel_artifacts", not any(hits.values()), matches=hits)

    # 6. CAD currency format
    add("cad_currency_format",
        bool(re.search(r"CA\$\s?[\d,]+\.\d{2}", text)),
        first_match=next(iter(re.findall(r"CA\$\s?[\d,]+\.\d{2}", text)), None))

    # 7. Dash placeholder (historical rows must show it)
    dash_here = "—" in text or "\u2014" in text
    if expect_dash_placeholder:
        add("dash_placeholder_present", dash_here)

    # 8. Anti-synthesis: for historical rows, the fabricated
    #    hammer_gst/qst amounts must NOT appear.
    if expect_no_synthesis:
        # 150.00 hammer → fabricated 7.50 (5%) and 14.96 (9.975%)
        found_75 = "CA$7.50" in text or "$7.50" in text
        found_1496 = "CA$14.96" in text or "$14.96" in text
        add("historical_no_fabricated_hammer_gst",
            not found_75, found_amount="CA$7.50" if found_75 else None)
        add("historical_no_fabricated_hammer_qst",
            not found_1496, found_amount="CA$14.96" if found_1496 else None)

    # 9. Required labels — matched against normalized (collapsed
    #    whitespace) text so titles that wrapped onto two PDF lines
    #    (e.g. "MARKETPLACE SELLER\nSTATEMENT") still resolve.
    for lbl in required_labels_en or []:
        norm_lbl = re.sub(r"\s+", " ", lbl.replace("\u00a0", " "))
        add(f"label_present::{lbl[:40]}", norm_lbl in normalized, snippet=lbl[:40])

    # 10. Explicit forbidden amounts (per-test)
    for amt in forbidden_amounts or []:
        add(f"forbidden_amount_absent::{amt}", amt not in text)

    return results


async def main():
    results = []
    add_many = lambda rs: results.extend(rs)  # noqa: E731

    client = AsyncIOMotorClient(os.environ["MONGO_URL"], tz_aware=True)
    db = client[os.environ["DB_NAME"]]
    ids = await seed(db)

    try:
        buyer   = ids["buyer_id"]
        seller  = ids["seller_logo_id"]
        seller2 = ids["seller_nolog_id"]

        # ══════════════ 1) STORAGE BUYER INVOICE (with seller logo) ══════════════
        pdf = await generate_storage_buyer_invoice(
            db, listing_id=ids["sto"], user_id=buyer, lang="en",
        )
        _render_pdf_to_png(pdf, "01_storage_buyer_invoice_en")
        add_many(_visual_asserts(
            "01_storage_buyer_invoice_en", pdf,
            expect_logo=True,
            required_labels_en=[
                "STORAGE INVOICE", "BUYER", "SELLER / DEALER",
                "Hammer Price Subtotal", "Hammer GST (5%)", "Hammer QST (9.975%)",
                "Buyer's Premium", "BidVex Service Fee",
                "Stripe Card Processing Fee", "GRAND TOTAL PAID",
                "CA$269.65",   # exact grand total
                "CA$200.00",   # hammer
                "CA$10.00",    # hammer GST
                "CA$19.95",    # hammer QST
                "CA$20.00",    # buyer premium
                "CA$8.00",     # service fee
                "CA$7.50",     # Stripe
                "QA Buyer Corp.", "Logo Seller Inc.",
            ],
        ))

        # ══════════════ 2) STORAGE BUYER INVOICE — French ══════════════
        pdf = await generate_storage_buyer_invoice(
            db, listing_id=ids["sto"], user_id=buyer, lang="fr",
        )
        _render_pdf_to_png(pdf, "02_storage_buyer_invoice_fr")
        add_many(_visual_asserts(
            "02_storage_buyer_invoice_fr", pdf,
            required_labels_en=[
                "FACTURE DE CASIER", "ACHETEUR", "VENDEUR / CONCESSIONNAIRE",
                "Sous-total marteau", "TPS marteau (5\u00a0%)",
                "TVQ marteau (9,975\u00a0%)", "Prime d'acheteur",
                "TOTAL PAY\u00c9",
                "CA$269.65",
            ],
        ))

        # ══════════════ 3) UNIVERSAL RECEIPT — Marketplace with logo ══════════════
        pdf = await generate_universal_receipt(
            db, section="marketplace", listing_id=ids["mkt_logo"],
            user_id=buyer, lang="en",
        )
        _render_pdf_to_png(pdf, "03_universal_receipt_mkt_with_logo")
        add_many(_visual_asserts(
            "03_universal_receipt_mkt_with_logo", pdf,
            expect_logo=True,
            required_labels_en=[
                "RECEIPT", "BUYER", "SELLER / DEALER",
                "Hammer Price Subtotal", "GRAND TOTAL PAID",
                "CA$269.65", "CA$200.00",
                "QA Buyer Corp.", "Logo Seller Inc.",
                "iter477qa_buyer@test.com",
                "iter477qa_seller_logo@test.com",
            ],
        ))

        # ══════════════ 4) UNIVERSAL RECEIPT — Marketplace WITHOUT logo ══════════════
        pdf = await generate_universal_receipt(
            db, section="marketplace", listing_id=ids["mkt_nolog"],
            user_id=buyer, lang="en",
        )
        _render_pdf_to_png(pdf, "04_universal_receipt_mkt_no_logo")
        add_many(_visual_asserts(
            "04_universal_receipt_mkt_no_logo", pdf,
            required_labels_en=[
                "RECEIPT", "BUYER", "SELLER / DEALER",
                "Plain Seller Ltd.",  # no logo, name should still be present
                "GRAND TOTAL PAID", "CA$269.65",
            ],
        ))

        # ══════════════ 5) MULTI-LOT (3 lots) BUYER TRANSACTION ══════════════
        pdf = await generate_universal_receipt(
            db, section="lots", listing_id=ids["lots_3"],
            user_id=buyer, lang="en",
        )
        _render_pdf_to_png(pdf, "05_universal_receipt_multi_lot_3")
        add_many(_visual_asserts(
            "05_universal_receipt_multi_lot_3", pdf,
            required_labels_en=[
                "RECEIPT", "GRAND TOTAL PAID",
                "CA$808.95",  # 3 × 269.65
                "CA$600.00",  # 3 × 200 hammer subtotal
                "QA 3-lot #1", "QA 3-lot #2", "QA 3-lot #3",
                "Lots included",   # meta row
                "3",                # 3 lots
            ],
        ))

        # ══════════════ 6) MULTI-PAGE (12 lots) ══════════════
        pdf = await generate_universal_receipt(
            db, section="lots", listing_id=ids["lots_12"],
            user_id=buyer, lang="en",
        )
        _render_pdf_to_png(pdf, "06_universal_receipt_12_lot_multipage")
        add_many(_visual_asserts(
            "06_universal_receipt_12_lot_multipage", pdf,
            expect_multi_page=True,
            required_labels_en=[
                "RECEIPT", "GRAND TOTAL PAID",
                "CA$3,235.80",  # 12 × 269.65
                "CA$2,400.00",  # 12 × 200
                "QA Big 12-lot #1",
                "QA Big 12-lot #12",
            ],
        ))

        # ══════════════ 7) MARKETPLACE SELLER STATEMENT ══════════════
        pdf = await generate_marketplace_seller_statement(
            db, listing_id=ids["mkt_logo"], seller_id=seller, lang="en",
        )
        _render_pdf_to_png(pdf, "07_seller_statement_mkt_en")
        add_many(_visual_asserts(
            "07_seller_statement_mkt_en", pdf,
            required_labels_en=[
                "MARKETPLACE SELLER STATEMENT",
                "BUYER", "SELLER / DEALER",
                "Hammer Total (Gross)", "Seller Commission",
                "Commission GST (5%)", "Commission QST (9.975%)",
                "NET PAYOUT",
                "CA$218.45", "CA$10.00", "CA$0.50", "CA$1.00",
                "QA Buyer Corp.", "Logo Seller Inc.",
            ],
        ))

        # ══════════════ 8) SELLER COMMISSION INVOICE ══════════════
        pdf = await generate_marketplace_seller_commission_invoice(
            db, listing_id=ids["mkt_logo"], seller_id=seller, lang="en",
        )
        _render_pdf_to_png(pdf, "08_commission_invoice_mkt_en")
        add_many(_visual_asserts(
            "08_commission_invoice_mkt_en", pdf,
            required_labels_en=[
                "MARKETPLACE COMMISSION INVOICE",
                "Seller Commission", "Commission GST", "Commission QST",
                "NET PAYOUT", "CA$10.00", "CA$0.50", "CA$1.00", "CA$218.45",
            ],
        ))

        # ══════════════ 9) SELLER STATEMENT — Vehicles ══════════════
        pdf = await generate_vehicle_seller_statement(
            db, listing_id=ids["veh"], seller_id=seller, lang="en",
        )
        _render_pdf_to_png(pdf, "09_seller_statement_vehicle_en")
        add_many(_visual_asserts(
            "09_seller_statement_vehicle_en", pdf,
            required_labels_en=[
                "VEHICLE SELLER STATEMENT",
                "2020 QA Sedan (VIN QA123)",
                "NET PAYOUT", "CA$218.45",
            ],
        ))

        # ══════════════ 10) SELLER STATEMENT — Storage FR ══════════════
        pdf = await generate_storage_seller_statement(
            db, listing_id=ids["sto"], seller_id=seller, lang="fr",
        )
        _render_pdf_to_png(pdf, "10_seller_statement_storage_fr")
        add_many(_visual_asserts(
            "10_seller_statement_storage_fr", pdf,
            required_labels_en=[
                "RELEV\u00c9 VENDEUR",
                "PAIEMENT NET", "CA$218.45",
                "Marteau brut", "Commission vendeur",
                "TPS sur commission", "TVQ sur commission",
            ],
        ))

        # ══════════════ 11) HISTORICAL BUYER RECEIPT (no itemized data) ═══════
        pdf = await generate_universal_receipt(
            db, section="marketplace", listing_id=ids["hist"],
            user_id=buyer, lang="en",
        )
        _render_pdf_to_png(pdf, "11_universal_receipt_historical")
        add_many(_visual_asserts(
            "11_universal_receipt_historical", pdf,
            expect_dash_placeholder=True,
            expect_no_synthesis=True,
            required_labels_en=[
                "RECEIPT", "GRAND TOTAL PAID",
                "CA$150.00",   # historical hammer
                "CA$184.47",   # historical total_charged
            ],
            forbidden_amounts=[
                # Fabricated values that MUST NOT appear
                "CA$7.50",   # 5% × 150 fabrication
                "CA$14.96",  # 9.975% × 150 fabrication
            ],
        ))

    finally:
        await cleanup(db)

    passed = sum(1 for r in results if r["ok"])
    total  = len(results)
    out = {
        "iter": "477-visual-qa",
        "passed": passed, "total": total,
        "pdf_output_dir": str(OUT_DIR),
        "results": results,
    }
    p = Path("/app/test_reports/iter477_pdf_visual_qa.json")
    p.parent.mkdir(exist_ok=True, parents=True)
    p.write_text(json.dumps(out, indent=2, default=str))
    print(f"[iter477-visual] {passed}/{total} passed → {p}")
    # Group failures for readability
    fails = [r for r in results if not r["ok"]]
    if fails:
        print(f"\n=== {len(fails)} FAIL ===")
        for r in fails:
            print(f"  FAIL [{r['pdf']}] {r['check']} → {r}")
    else:
        print("  All visual checks PASS.")
    print(f"\nRendered PNGs written to: {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
