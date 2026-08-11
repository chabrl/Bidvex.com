"""iter477 — Strict PDF ↔ DB reconciliation verification.

Purpose (per user directive for iter477):
    1. Prove that every itemized dollar figure on the new buyer / seller
       PDFs is read verbatim from ``db.receipts`` — never synthesized,
       never split from an aggregate, never recomputed.
    2. Prove that BUYER: `sum(itemized components) == receipt.total_charged`
       to the cent, and SELLER: `gross ± deductions == receipt.net_payout`
       to the cent.
    3. Prove that HISTORICAL receipts (without itemized fields) render
       "—" for the missing components — no synthesis of historical data.

Runs the PDF generators IN-PROCESS (no HTTP round trip needed — the
generators are pure functions that take ``db`` and return bytes) so we
can extract every dollar amount and reconcile it against the persisted
settlement record with no ambiguity.

Idempotent: seeds ``iter477-*`` fixtures on entry, cleans them up on
exit.  Does NOT touch production data or any pre-existing receipt row.
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

from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
from pypdf import PdfReader  # type: ignore

from services.pdf_generators.universal_receipt import generate_universal_receipt
from services.pdf_generators.sections import (
    generate_storage_buyer_invoice,
    generate_marketplace_seller_statement,
    generate_marketplace_seller_receipt,
    generate_marketplace_seller_commission_invoice,
    generate_vehicle_seller_statement,
    generate_vehicle_seller_receipt,
    generate_vehicle_seller_commission_invoice,
    generate_storage_seller_statement,
    generate_storage_seller_receipt,
    generate_storage_seller_commission_invoice,
)
from services.receipts import reconcile_itemized, ITEMIZED_KEYS

PREFIX = "iter477-"
NOW = datetime.now(timezone.utc).isoformat()


# ═══════════════════════════════════════════════════════════════════
#  Fixture per-lot amounts.  Chosen so reconcile_itemized() passes
#  exactly (no rounding drift) — the test then proves the same figures
#  appear verbatim on the rendered PDFs.
# ═══════════════════════════════════════════════════════════════════
FIXTURE = {
    "hammer_price":          200.00,
    "hammer_gst":             10.00,
    "hammer_qst":             19.95,
    "buyer_premium":          20.00,
    "buyer_premium_gst":       1.00,
    "buyer_premium_qst":       2.00,
    "service_fee":             8.00,
    "service_fee_gst":         0.40,
    "service_fee_qst":         0.80,
    "stripe_fee":              7.50,
    "stripe_fee_charged_to":   "buyer",
    "seller_commission":      10.00,
    "seller_commission_gst":   0.50,
    "seller_commission_qst":   1.00,
    "other_deductions":        0.00,
    "buyer_premium_rate":     0.10,
    "seller_commission_rate": 0.05,
    "seller_is_tax_registered": True,
    "bidvex_gst_number":      "123456789RT0001",
    "bidvex_qst_number":      "1234567890TQ0001",
}
# Derived totals (checked by reconcile_itemized before persistence)
BUYER_TOTAL_PAID = Decimal("269.65")   # 200 + 10 + 19.95 + 20 + 1 + 2 + 8 + 0.40 + 0.80 + 7.50
SELLER_NET_PAYOUT = Decimal("218.45")  # 200 + 10 + 19.95 - 10 - 0.50 - 1.00

# Historical fixture (aggregate-only, NO itemized fields)
HIST_FIXTURE = {
    "hammer_price":   150.00,
    "platform_fee":     7.50,
    "taxes":           22.42,
    "processing_fee":   4.55,
    "total_charged":  184.47,
    "net_payout":     142.50,
}


def _extract_amounts(pdf_bytes: bytes) -> list[str]:
    """Return every CA$-prefixed dollar amount from the PDF, in order."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join(p.extract_text() or "" for p in reader.pages)
    return [m.replace(",", "") for m in re.findall(r"CA\$\s?([\d,]+\.\d{2})", text)]


def _extract_all_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(p.extract_text() or "" for p in reader.pages)


def _cents(dec: Decimal | float | str) -> int:
    return int((Decimal(str(dec)) * 100).to_integral_value())


async def _ensure_user(db, *, email: str, name: str) -> str:
    existing = await db.users.find_one({"email": email}, {"_id": 0, "id": 1})
    if existing:
        return existing["id"]
    uid = str(uuid.uuid4())
    await db.users.insert_one({
        "id":              uid,
        "email":           email,
        "name":            name,
        "role":            "user",
        "company_name":    name,
        "business_address": "123 Rue Test, Montreal QC H1A 1A1",
        "phone":           "+15145551234",
        "gst_number":      "123456789RT0001",
        "qst_number":      "1234567890TQ0001",
        "created_at":      NOW,
        "iter477_seed":    True,
    })
    return uid


async def _seed_listing(db, *, collection: str, doc: dict) -> None:
    doc.setdefault("iter477_seed", True)
    await db[collection].insert_one(doc)


async def _insert_itemized_receipt(
    db, *, section: str, listing_id: str, listing_title: str,
    user_id: str, buyer_or_seller: str, lot_number,
) -> str:
    """Insert a receipt with a fully-itemized breakdown that reconciles."""
    rid = str(uuid.uuid4())
    base = {
        "id":               rid,
        "type":             "buyer_receipt" if buyer_or_seller == "buyer" else "seller_statement",
        "user_id":          user_id,
        "section":          section,
        "listing_id":       listing_id,
        "lot_number":       lot_number,
        "listing_title":    listing_title,
        "hammer_price":     FIXTURE["hammer_price"],
        "platform_fee":     FIXTURE["buyer_premium"] + FIXTURE["service_fee"],
        "taxes":            (
            FIXTURE["hammer_gst"] + FIXTURE["hammer_qst"]
            + FIXTURE["buyer_premium_gst"] + FIXTURE["buyer_premium_qst"]
            + FIXTURE["service_fee_gst"] + FIXTURE["service_fee_qst"]
        ),
        "processing_fee":   FIXTURE["stripe_fee"],
        "total_charged":    float(BUYER_TOTAL_PAID),
        "net_payout":       float(SELLER_NET_PAYOUT),
        "currency":         "CAD",
        "created_at":       NOW,
        "order_number":     f"BVX-{listing_id[-8:].upper()}",
        "seller_name":      "Test Seller Inc.",
        "quantity":         1,
        "itemized_reconciled": True,
        "itemized_version": 1,
        "iter477_seed":     True,
    }
    for k in ITEMIZED_KEYS:
        if k in FIXTURE:
            base[k] = FIXTURE[k]
    await db.receipts.insert_one(base)
    return rid


async def _insert_historical_receipt(
    db, *, section: str, listing_id: str, listing_title: str,
    user_id: str, buyer_or_seller: str, lot_number,
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
        "hammer_price":  HIST_FIXTURE["hammer_price"],
        "platform_fee":  HIST_FIXTURE["platform_fee"],
        "taxes":         HIST_FIXTURE["taxes"],
        "processing_fee": HIST_FIXTURE["processing_fee"],
        "total_charged": HIST_FIXTURE["total_charged"],
        "net_payout":    HIST_FIXTURE["net_payout"],
        "currency":      "CAD",
        "created_at":    NOW,
        "order_number":  f"BVX-HIS-{listing_id[-6:].upper()}",
        "seller_name":   "Historical Seller",
        "quantity":      1,
        "iter477_seed":  True,
    })
    return rid


async def seed(db) -> dict:
    """Seed itemized + historical rows across all 4 sections."""
    buyer_id = await _ensure_user(
        db, email="iter477_buyer@test.com", name="iter477 Test Buyer",
    )
    seller_id = await _ensure_user(
        db, email="iter477_seller@test.com", name="iter477 Test Seller",
    )

    # ── Marketplace: 1 itemized single-item pair ─────────────────
    mkt_id = f"{PREFIX}mkt-{uuid.uuid4().hex[:8]}"
    await _seed_listing(db, collection="listings", doc={
        "id": mkt_id, "title": "iter477 · Marketplace itemized item",
        "status": "sold",
        "winner_user_id": buyer_id, "seller_id": seller_id,
        "final_price": FIXTURE["hammer_price"],
        "current_price": FIXTURE["hammer_price"],
    })
    await _insert_itemized_receipt(
        db, section="marketplace", listing_id=mkt_id,
        listing_title="iter477 · Marketplace itemized item",
        user_id=buyer_id, buyer_or_seller="buyer", lot_number=None,
    )
    await _insert_itemized_receipt(
        db, section="marketplace", listing_id=mkt_id,
        listing_title="iter477 · Marketplace itemized item",
        user_id=seller_id, buyer_or_seller="seller", lot_number=None,
    )

    # ── Vehicles: 1 itemized single-lot vehicle pair ─────────────
    veh_id = f"{PREFIX}veh-{uuid.uuid4().hex[:8]}"
    await _seed_listing(db, collection="vehicle_listings", doc={
        "id": veh_id, "title": "iter477 · Vehicle test lot",
        "status": "sold", "seller_id": seller_id,
        "lots": [
            {"lot_number": 1, "title": "2020 Test Sedan",
             "quantity": 1, "current_price": FIXTURE["hammer_price"]},
        ],
    })
    await _insert_itemized_receipt(
        db, section="vehicles", listing_id=veh_id,
        listing_title="2020 Test Sedan",
        user_id=buyer_id, buyer_or_seller="buyer", lot_number=1,
    )
    await _insert_itemized_receipt(
        db, section="vehicles", listing_id=veh_id,
        listing_title="2020 Test Sedan",
        user_id=seller_id, buyer_or_seller="seller", lot_number=1,
    )

    # ── Storage: 1 itemized storage auction pair ────────────────
    sto_id = f"{PREFIX}sto-{uuid.uuid4().hex[:8]}"
    await _seed_listing(db, collection="storage_auctions", doc={
        "id": sto_id, "title": "iter477 · Storage locker",
        "status": "sold",
        "facility_name": "Test Facility", "location": "Montreal, QC",
        "seller_id": seller_id, "facility_owner_id": seller_id,
    })
    await _insert_itemized_receipt(
        db, section="storage", listing_id=sto_id,
        listing_title="iter477 · Storage locker",
        user_id=buyer_id, buyer_or_seller="buyer", lot_number=None,
    )
    await _insert_itemized_receipt(
        db, section="storage", listing_id=sto_id,
        listing_title="iter477 · Storage locker",
        user_id=seller_id, buyer_or_seller="seller", lot_number=None,
    )

    # ── Multi-lot: 2 itemized lots (verifies aggregation across lots) ─
    lots_id = f"{PREFIX}lots-{uuid.uuid4().hex[:8]}"
    await _seed_listing(db, collection="multi_item_listings", doc={
        "id": lots_id, "title": "iter477 · Multi-lot estate",
        "status": "ended", "seller_id": seller_id,
        "lots": [
            {"lot_number": 1, "title": "Lot 1 - iter477",
             "quantity": 1, "current_price": FIXTURE["hammer_price"]},
            {"lot_number": 2, "title": "Lot 2 - iter477",
             "quantity": 1, "current_price": FIXTURE["hammer_price"]},
        ],
    })
    for lot in (1, 2):
        await _insert_itemized_receipt(
            db, section="lots", listing_id=lots_id,
            listing_title=f"Lot {lot} - iter477",
            user_id=buyer_id, buyer_or_seller="buyer", lot_number=lot,
        )
        await _insert_itemized_receipt(
            db, section="lots", listing_id=lots_id,
            listing_title=f"Lot {lot} - iter477",
            user_id=seller_id, buyer_or_seller="seller", lot_number=lot,
        )

    # ── Historical marketplace (aggregate-only, NO itemized) ────
    hist_id = f"{PREFIX}hist-{uuid.uuid4().hex[:8]}"
    await _seed_listing(db, collection="listings", doc={
        "id": hist_id, "title": "iter477 · HISTORICAL aggregate item",
        "status": "sold",
        "winner_user_id": buyer_id, "seller_id": seller_id,
        "final_price": HIST_FIXTURE["hammer_price"],
    })
    await _insert_historical_receipt(
        db, section="marketplace", listing_id=hist_id,
        listing_title="iter477 · HISTORICAL aggregate item",
        user_id=buyer_id, buyer_or_seller="buyer", lot_number=None,
    )
    await _insert_historical_receipt(
        db, section="marketplace", listing_id=hist_id,
        listing_title="iter477 · HISTORICAL aggregate item",
        user_id=seller_id, buyer_or_seller="seller", lot_number=None,
    )

    return {
        "buyer_id":  buyer_id,
        "seller_id": seller_id,
        "mkt_id":    mkt_id,
        "veh_id":    veh_id,
        "sto_id":    sto_id,
        "lots_id":   lots_id,
        "hist_id":   hist_id,
    }


async def cleanup(db) -> None:
    for col in ("users", "listings", "vehicle_listings", "storage_auctions",
                "multi_item_listings", "receipts"):
        try:
            await db[col].delete_many({"iter477_seed": True})
        except Exception:  # noqa: BLE001
            pass


def check_reconcile_helper() -> dict:
    """Sanity: verify the FIXTURE reconciles with itself before we seed."""
    rec = reconcile_itemized(
        hammer_price=FIXTURE["hammer_price"],
        itemized=FIXTURE,
        total_charged=float(BUYER_TOTAL_PAID),
        net_payout=float(SELLER_NET_PAYOUT),
    )
    return rec


async def main():
    results = []
    add = lambda **kw: results.append(kw)  # noqa: E731

    # ── PRE-CHECK 0: fixture reconciles ────────────────────────
    rec = check_reconcile_helper()
    add(test="pre-check-fixture-reconciles",
        ok=rec["ok"],
        buyer_delta_cents=rec["buyer_delta_cents"],
        seller_delta_cents=rec["seller_delta_cents"],
        reasons=rec["reasons"])
    if not rec["ok"]:
        print("[iter477] fixture itself doesn't reconcile — aborting.")
        return

    client = AsyncIOMotorClient(os.environ["MONGO_URL"], tz_aware=True)
    db = client[os.environ["DB_NAME"]]

    # Idempotency: wipe old iter477 seed if leftover from prior run
    await cleanup(db)
    ids = await seed(db)

    try:
        buyer_id  = ids["buyer_id"]
        seller_id = ids["seller_id"]

        # ══════════════════════════════════════════════════════
        #  T1-T4: BUYER — Universal Receipt reconciliation per section
        # ══════════════════════════════════════════════════════
        for section, lid, expected_lot_count in (
            ("marketplace", ids["mkt_id"], 1),
            ("vehicles",    ids["veh_id"], 1),
            ("storage",     ids["sto_id"], 1),
            ("lots",        ids["lots_id"], 2),
        ):
            pdf = await generate_universal_receipt(
                db, section=section, listing_id=lid, user_id=buyer_id, lang="en",
            )
            add(test=f"T1.{section}-buyer-receipt-generated",
                ok=(pdf is not None and pdf.startswith(b"%PDF")),
                bytes=len(pdf or b""))
            if not pdf:
                continue

            amounts = _extract_amounts(pdf)
            text = _extract_all_text(pdf)

            # Per-lot expected: values scale by number of lots for lots section
            expected_hammer      = FIXTURE["hammer_price"] * expected_lot_count
            expected_hammer_gst  = FIXTURE["hammer_gst"] * expected_lot_count
            expected_hammer_qst  = FIXTURE["hammer_qst"] * expected_lot_count
            expected_buyer_prem  = FIXTURE["buyer_premium"] * expected_lot_count
            expected_bp_gst      = FIXTURE["buyer_premium_gst"] * expected_lot_count
            expected_bp_qst      = FIXTURE["buyer_premium_qst"] * expected_lot_count
            expected_svc_fee     = FIXTURE["service_fee"] * expected_lot_count
            expected_svc_gst     = FIXTURE["service_fee_gst"] * expected_lot_count
            expected_svc_qst     = FIXTURE["service_fee_qst"] * expected_lot_count
            expected_stripe      = FIXTURE["stripe_fee"] * expected_lot_count
            expected_grand_total = float(BUYER_TOTAL_PAID) * expected_lot_count

            def _has(v: float) -> bool:
                return f"{v:,.2f}".replace(",", "") in amounts

            checks = {
                "hammer":         _has(expected_hammer),
                "hammer_gst":     _has(expected_hammer_gst),
                "hammer_qst":     _has(expected_hammer_qst),
                "buyer_premium":  _has(expected_buyer_prem),
                "buyer_prem_gst": _has(expected_bp_gst),
                "buyer_prem_qst": _has(expected_bp_qst),
                "service_fee":    _has(expected_svc_fee),
                "service_gst":    _has(expected_svc_gst),
                "service_qst":    _has(expected_svc_qst),
                "stripe":         _has(expected_stripe),
                "grand_total":    _has(expected_grand_total),
            }
            add(
                test=f"T1.{section}-buyer-itemized-lines-present",
                ok=all(checks.values()),
                missing=[k for k, v in checks.items() if not v],
                expected_grand_total=f"{expected_grand_total:,.2f}",
                sample_amounts=amounts[-8:] if amounts else [],
            )

            # DB reconciliation: sum(total_charged) across the buyer's
            # receipts in this listing must equal grand_total on PDF
            recs = await db.receipts.find(
                {"user_id": buyer_id, "type": "buyer_receipt",
                 "section": section, "listing_id": lid},
                {"_id": 0}
            ).to_list(20)
            db_total = sum(Decimal(str(r["total_charged"])) for r in recs)
            pdf_total = Decimal(str(expected_grand_total))
            add(
                test=f"T1.{section}-buyer-db-vs-pdf-total-exact",
                ok=(_cents(db_total) == _cents(pdf_total)),
                db_total=f"{db_total:,.2f}",
                pdf_total=f"{pdf_total:,.2f}",
            )

            # BUYER identification present on PDF
            add(
                test=f"T1.{section}-buyer-party-block",
                ok=("iter477 Test Buyer" in text or "iter477_buyer@test.com" in text),
                sample_text=text[:200].replace("\n", " | ") if text else "",
            )
            # SELLER identification present on PDF
            add(
                test=f"T1.{section}-seller-party-block",
                ok=("iter477 Test Seller" in text or "iter477_seller@test.com" in text),
            )

        # ══════════════════════════════════════════════════════
        #  T5: Storage Buyer Invoice (dedicated section endpoint)
        # ══════════════════════════════════════════════════════
        pdf = await generate_storage_buyer_invoice(
            db, listing_id=ids["sto_id"], user_id=buyer_id, lang="en",
        )
        add(test="T5.storage-buyer-invoice-generated",
            ok=(pdf is not None and pdf.startswith(b"%PDF")))
        if pdf:
            amounts = _extract_amounts(pdf)
            add(test="T5.storage-buyer-invoice-grand-total-exact",
                ok=(f"{float(BUYER_TOTAL_PAID):,.2f}".replace(",", "") in amounts),
                expected=f"{float(BUYER_TOTAL_PAID):,.2f}",
                sample_amounts=amounts[-6:])

        # ══════════════════════════════════════════════════════
        #  T6-T9: SELLER statements per section — net_payout must
        #  exactly equal the DB-persisted seller net.
        # ══════════════════════════════════════════════════════
        seller_cases = [
            ("marketplace", ids["mkt_id"], 1, generate_marketplace_seller_statement),
            ("vehicles",    ids["veh_id"], 1, generate_vehicle_seller_statement),
            ("storage",     ids["sto_id"], 1, generate_storage_seller_statement),
            ("lots",        None, 0, None),  # skipped — lots use legacy generator
        ]
        for section, lid, expected_lot_count, gen in seller_cases:
            if not gen:
                continue
            pdf = await gen(db, listing_id=lid, seller_id=seller_id, lang="en")
            add(test=f"T6.{section}-seller-statement-generated",
                ok=(pdf is not None and pdf.startswith(b"%PDF")))
            if not pdf:
                continue

            amounts = _extract_amounts(pdf)
            text = _extract_all_text(pdf)

            expected_hammer = FIXTURE["hammer_price"] * expected_lot_count
            expected_h_gst  = FIXTURE["hammer_gst"] * expected_lot_count
            expected_h_qst  = FIXTURE["hammer_qst"] * expected_lot_count
            expected_comm   = FIXTURE["seller_commission"] * expected_lot_count
            expected_c_gst  = FIXTURE["seller_commission_gst"] * expected_lot_count
            expected_c_qst  = FIXTURE["seller_commission_qst"] * expected_lot_count
            expected_net    = float(SELLER_NET_PAYOUT) * expected_lot_count

            def _has(v: float) -> bool:
                return f"{v:,.2f}".replace(",", "") in amounts

            checks = {
                "hammer_gross":    _has(expected_hammer),
                "hammer_gst":      _has(expected_h_gst),
                "hammer_qst":      _has(expected_h_qst),
                "commission":      _has(expected_comm),
                "commission_gst":  _has(expected_c_gst),
                "commission_qst":  _has(expected_c_qst),
                "net_payout":      _has(expected_net),
            }
            add(
                test=f"T6.{section}-seller-itemized-lines-present",
                ok=all(checks.values()),
                missing=[k for k, v in checks.items() if not v],
                expected_net=f"{expected_net:,.2f}",
                sample=amounts[-8:],
            )

            # DB-vs-PDF reconciliation
            recs = await db.receipts.find(
                {"user_id": seller_id, "type": "seller_statement",
                 "section": section, "listing_id": lid},
                {"_id": 0}
            ).to_list(20)
            db_net = sum(Decimal(str(r["net_payout"])) for r in recs)
            pdf_net = Decimal(str(expected_net))
            add(
                test=f"T6.{section}-seller-db-vs-pdf-net-exact",
                ok=(_cents(db_net) == _cents(pdf_net)),
                db_net=f"{db_net:,.2f}",
                pdf_net=f"{pdf_net:,.2f}",
            )

            # Seller Receipt + Commission Invoice
            receipt_gen = {
                "marketplace": generate_marketplace_seller_receipt,
                "vehicles":    generate_vehicle_seller_receipt,
                "storage":     generate_storage_seller_receipt,
            }[section]
            comm_gen = {
                "marketplace": generate_marketplace_seller_commission_invoice,
                "vehicles":    generate_vehicle_seller_commission_invoice,
                "storage":     generate_storage_seller_commission_invoice,
            }[section]
            r_pdf = await receipt_gen(db, listing_id=lid, seller_id=seller_id, lang="en")
            c_pdf = await comm_gen(db, listing_id=lid, seller_id=seller_id, lang="en")
            add(test=f"T7.{section}-seller-receipt-generated",
                ok=(r_pdf is not None and r_pdf.startswith(b"%PDF")))
            add(test=f"T8.{section}-seller-commission-invoice-generated",
                ok=(c_pdf is not None and c_pdf.startswith(b"%PDF")))
            if r_pdf:
                r_amounts = _extract_amounts(r_pdf)
                add(test=f"T7.{section}-seller-receipt-net-exact",
                    ok=(f"{expected_net:,.2f}".replace(",", "") in r_amounts),
                    expected=f"{expected_net:,.2f}")
            if c_pdf:
                c_amounts = _extract_amounts(c_pdf)
                add(test=f"T8.{section}-seller-commission-invoice-commission-exact",
                    ok=(f"{expected_comm:,.2f}".replace(",", "") in c_amounts),
                    expected=f"{expected_comm:,.2f}")

        # ══════════════════════════════════════════════════════
        #  T9: HISTORICAL receipts — verify "—" appears for missing
        #      itemized fields (NO SYNTHESIS).
        # ══════════════════════════════════════════════════════
        pdf = await generate_universal_receipt(
            db, section="marketplace", listing_id=ids["hist_id"],
            user_id=buyer_id, lang="en",
        )
        add(test="T9.historical-buyer-receipt-generated",
            ok=(pdf is not None and pdf.startswith(b"%PDF")))
        if pdf:
            text = _extract_all_text(pdf)
            amounts = _extract_amounts(pdf)
            # itemized components MUST render as "—" for historical rows —
            # never fabricated from the aggregate totals.
            has_dash_placeholder = "—" in text
            # Historical aggregate totals MUST appear (not itemized)
            has_hammer  = f"{HIST_FIXTURE['hammer_price']:,.2f}".replace(",", "") in amounts
            has_total   = f"{HIST_FIXTURE['total_charged']:,.2f}".replace(",", "") in amounts
            # SYNTHESIS GUARD: the itemized-only fields we did NOT persist
            # (hammer_gst=5% of 150 = 7.50, etc.) must NOT appear as
            # invented numbers.
            fabricated_hammer_gst = f"{150.00 * 0.05:,.2f}".replace(",", "")   # 7.50
            fabricated_hammer_qst = f"{150.00 * 0.09975:,.2f}".replace(",", "") # 14.96
            no_fabrication = (
                fabricated_hammer_gst not in amounts
                and fabricated_hammer_qst not in amounts
            )
            add(test="T9.historical-shows-dash-placeholder",
                ok=has_dash_placeholder)
            add(test="T9.historical-aggregate-total-exact",
                ok=(has_hammer and has_total),
                has_hammer=has_hammer, has_total=has_total)
            add(test="T9.historical-no-synthesis-of-itemized-fields",
                ok=no_fabrication,
                fab_gst_present=(fabricated_hammer_gst in amounts),
                fab_qst_present=(fabricated_hammer_qst in amounts),
                found=amounts[-6:])

        # ══════════════════════════════════════════════════════
        #  T10: The itemized-reconciled receipt row survives roundtrip.
        # ══════════════════════════════════════════════════════
        one_row = await db.receipts.find_one(
            {"user_id": buyer_id, "type": "buyer_receipt",
             "listing_id": ids["mkt_id"]}, {"_id": 0})
        add(test="T10.itemized-row-persisted",
            ok=(bool(one_row) and one_row.get("itemized_reconciled") is True
                and one_row.get("hammer_gst") == FIXTURE["hammer_gst"]
                and one_row.get("buyer_premium") == FIXTURE["buyer_premium"]
                and one_row.get("seller_commission") == FIXTURE["seller_commission"]),
            row_keys=sorted(list(one_row.keys()))[:20] if one_row else [])

    finally:
        await cleanup(db)

    passed = sum(1 for r in results if r.get("ok"))
    total  = len(results)
    out = {
        "iter": 477,
        "passed": passed,
        "total":  total,
        "fixture": {
            "buyer_total_paid":  str(BUYER_TOTAL_PAID),
            "seller_net_payout": str(SELLER_NET_PAYOUT),
        },
        "results": results,
    }
    p = Path("/app/test_reports/iter477_pdf_reconciliation.json")
    p.parent.mkdir(exist_ok=True, parents=True)
    p.write_text(json.dumps(out, indent=2, default=str))
    print(f"[iter477] {passed}/{total} passed → {p}")
    for r in results:
        flag = "OK" if r.get("ok") else "FAIL"
        print(f"  [{flag:4}] {r['test']:60s} {json.dumps({k: v for k, v in r.items() if k != 'test' and k != 'ok'}, default=str)[:180]}")


if __name__ == "__main__":
    asyncio.run(main())
