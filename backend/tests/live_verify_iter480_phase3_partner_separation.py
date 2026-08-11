"""iter480 — Phase 3 canonical BidVex Platform Fee separation tests.

Master directive Section 22 test matrix (P1–P8) + Section 24 zero-cent
invariant.  Verifies the canonical Partner Buyer Premium ≠ BidVex
Platform Fee separation without changing any historical financial value.

Every test is either:
  • an in-process call to services.fee_calculator.calculate_fee() and
    services.auction_settlement fee_breakdown assembly (numeric proof), or
  • a rendered PDF from an in-process seeded receipt that shows the
    correct "BidVex Platform Fee" label for new Partner receipts.

Idempotent: seeds ``iter480qa-*`` rows on entry, cleans them on exit.
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

from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
from pypdf import PdfReader  # type: ignore

from services.fee_calculator import calculate_fee, PARTNER_PLATFORM_RATE
from services.fee_schedule import (
    get_active_schedule, resolve_buyer_premium_rate,
    resolve_seller_commission_rate,
)
from services.receipts import ITEMIZED_KEYS
from services.pdf_generators.sections import (
    generate_marketplace_seller_statement,
    generate_marketplace_seller_receipt,
    generate_marketplace_seller_commission_invoice,
)
from services.pdf_generators.universal_receipt import generate_universal_receipt


PREFIX = "iter480qa-"
NOW = datetime.now(timezone.utc).isoformat()


def _c(v) -> int:
    """Convert dollars to integer cents."""
    return int(round(float(v or 0) * 100))


def _extract_text(pdf_bytes: bytes) -> str:
    r = PdfReader(io.BytesIO(pdf_bytes))
    return "\n".join(p.extract_text() or "" for p in r.pages)


async def _ensure_user(db, *, email, name) -> str:
    existing = await db.users.find_one({"email": email}, {"_id": 0, "id": 1})
    if existing:
        return existing["id"]
    uid = str(uuid.uuid4())
    await db.users.insert_one({
        "id": uid, "email": email, "name": name, "role": "user",
        "company_name": name,
        "business_address": "456 Rue P3, Montreal QC H1C 3C3",
        "phone": "+15145550480",
        "gst_number": "111222333RT0001", "qst_number": "1112223330TQ0001",
        "created_at": NOW,
        "iter480qa_seed": True,
    })
    return uid


async def _seed_partner_receipt(
    db, *, listing_id, listing_title, buyer_id, seller_id, partner_bp_rate,
) -> dict:
    """Directly seed a Partner-sale receipt WITH the new canonical
    ``bidvex_platform_fee_*`` fields, mirroring what auction_settlement
    will now write on new Partner settlements."""
    hammer = 100.00
    bp_amount   = round(hammer * partner_bp_rate, 2)
    platform_fee_rate   = float(PARTNER_PLATFORM_RATE)
    platform_fee_amount = round(hammer * platform_fee_rate, 2)   # 3.00
    # Taxes computed via tax_on in the real fee_calculator; we just carry
    # placeholder values here — the reconciliation math doesn't include
    # them for the buyer since Partner buyer_side taxes = 0.
    doc = {
        "id":              str(uuid.uuid4()),
        "type":            "buyer_receipt",
        "user_id":         buyer_id,
        "section":         "marketplace",
        "listing_id":      listing_id,
        "lot_number":      None,
        "listing_title":   listing_title,
        "hammer_price":    hammer,
        "platform_fee":    0.0,
        "taxes":           0.0,
        "processing_fee":  0.0,
        "total_charged":   hammer + bp_amount,   # buyer pays hammer + partner BP ONLY
        "net_payout":      hammer + bp_amount,   # partner receives hammer + BP
        "currency":        "CAD",
        "created_at":      NOW,
        "order_number":    f"BVX-{listing_id[-8:].upper()}",
        "seller_name":     "iter480 Partner Seller",
        "quantity":        1,
        # iter476 itemized snapshot
        "buyer_premium":   bp_amount,
        "buyer_premium_rate": partner_bp_rate,
        "buyer_premium_gst": 0.0, "buyer_premium_qst": 0.0,
        "hammer_gst": 0.0, "hammer_qst": 0.0,
        "service_fee": 0.0, "service_fee_gst": 0.0, "service_fee_qst": 0.0,
        "stripe_fee": 0.0, "stripe_fee_charged_to": "buyer",
        # ── legacy Partner-sale seller_commission field ──
        # kept 0 for the CANONICAL Phase 3 receipt (BidVex fee lives in
        # the new field below).  Old-style receipts would set this to
        # $3 — PDF renderer handles both cases.
        "seller_commission":     0.0,
        "seller_commission_rate": 0.0,
        "seller_commission_gst": 0.0,
        "seller_commission_qst": 0.0,
        "other_deductions": 0.0,
        "seller_is_tax_registered": False,
        "bidvex_gst_number": "706766367RT0001",
        "bidvex_qst_number": "1233530880TQ0001",
        # ── iter480 Phase 3 canonical fields ──
        "bidvex_platform_fee_rate":   platform_fee_rate,
        "bidvex_platform_fee_amount": platform_fee_amount,
        "bidvex_platform_fee_gst":    0.0,
        "bidvex_platform_fee_qst":    0.0,
        "fee_schedule_version":       1,
        "fee_model_version":          "iter350",
        "itemized_reconciled":        True,
        "itemized_version":           2,   # v2 = iter480 canonical
        "iter480qa_seed":             True,
    }
    # Companion seller receipt (mirrors buyer for the sample partner sale).
    # Build BEFORE the buyer insert so pymongo hasn't yet stamped _id
    # onto the buyer doc (which dict() would otherwise copy).
    seller_doc = {k: v for k, v in doc.items() if k != "_id"}
    seller_doc["id"]      = str(uuid.uuid4())
    seller_doc["type"]    = "seller_statement"
    seller_doc["user_id"] = seller_id
    await db.receipts.insert_one(doc)
    await db.receipts.insert_one(seller_doc)
    return doc


async def cleanup(db):
    for col in ("users", "listings", "receipts"):
        try:
            await db[col].delete_many({"iter480qa_seed": True})
        except Exception:  # noqa: BLE001
            pass


# ═══════════════════════════════════════════════════════════════════
async def main():
    results = []
    def add(name, ok, **kw):
        results.append({"test": name, "ok": ok, **kw})

    client = AsyncIOMotorClient(os.environ["MONGO_URL"], tz_aware=True)
    db = client[os.environ["DB_NAME"]]
    await cleanup(db)

    # ══════════════════════════════════════════════════════════
    #  Numeric proofs — no DB needed
    # ══════════════════════════════════════════════════════════
    # P1: Partner 10% on $100 hammer, QC/QC
    fee_p1 = calculate_fee(
        hammer_price=100.0, auction_type="lots",
        seller_account_type="partner", seller_tier="partner",
        buyer_account_type="individual", buyer_tier="standard",
        payment_method="stripe", card_type="domestic",
        buyer_province="QC", seller_province="QC", partner_province="QC",
        partner_bp_rate=0.10,
    )
    add("P1.partner_10pct_buyer_pays_partner_BP_only",
        ok=_c(fee_p1["buyer_premium"]) == 1000 and _c(fee_p1["buyer_total_charged"]) == 11000,
        buyer_premium=fee_p1["buyer_premium"], total=fee_p1["buyer_total_charged"])
    add("P1.partner_10pct_bidvex_platform_fee_is_3.00",
        ok=_c(fee_p1["bidvex_platform_fee_amount"]) == 300
           and _c(fee_p1["seller_commission"]) == 300,   # legacy field mirrors it
        platform=fee_p1["bidvex_platform_fee_amount"],
        legacy_seller_commission=fee_p1["seller_commission"])
    add("P1.partner_10pct_buyer_does_NOT_pay_platform_fee",
        ok=_c(fee_p1["buyer_total_charged"]) == _c(100.0 + fee_p1["buyer_premium"]),
        note="buyer_total = hammer + partner BP; the 3% platform fee is NOT included")

    # P2: Partner 15%
    fee_p2 = calculate_fee(
        hammer_price=100.0, auction_type="lots",
        seller_account_type="partner", seller_tier="partner",
        buyer_account_type="individual", buyer_tier="standard",
        payment_method="stripe", card_type="domestic",
        buyer_province="QC", seller_province="QC", partner_province="QC",
        partner_bp_rate=0.15,
    )
    add("P2.partner_15pct",
        ok=_c(fee_p2["buyer_premium"]) == 1500
           and _c(fee_p2["bidvex_platform_fee_amount"]) == 300
           and _c(fee_p2["buyer_total_charged"]) == 11500,
        buyer_premium=fee_p2["buyer_premium"],
        platform_fee=fee_p2["bidvex_platform_fee_amount"])

    # P3: Partner 18% custom
    fee_p3 = calculate_fee(
        hammer_price=100.0, auction_type="lots",
        seller_account_type="partner", seller_tier="partner",
        buyer_account_type="individual", buyer_tier="standard",
        payment_method="stripe", card_type="domestic",
        buyer_province="QC", seller_province="QC", partner_province="QC",
        partner_bp_rate=0.18,
    )
    add("P3.partner_18pct_custom",
        ok=_c(fee_p3["buyer_premium"]) == 1800
           and _c(fee_p3["bidvex_platform_fee_amount"]) == 300
           and _c(fee_p3["buyer_total_charged"]) == 11800)

    # P4: Immutable snapshot preserved (a 10% snapshot is not changed by
    # a schedule change).  The calculator takes partner_bp_rate as an
    # explicit parameter — the schedule cannot silently override it.
    schedule = await get_active_schedule(db)
    # Resolver with listing_override 0.10 returns 0.10 regardless of
    # what the schedule's `partner.default` says.
    resolved = float(resolve_buyer_premium_rate(
        schedule, seller_account_type="partner",
        listing_override=Decimal("0.10"),
    ))
    add("P4.immutable_snapshot_survives_schedule_change",
        ok=(resolved == 0.10),
        note="listing_override wins Priority 2; schedule.partner.default 5% is Priority 4",
        resolved=resolved)

    # P5: Partner Pro rates (schedule-only in Phase 3)
    ppro_bp = float(resolve_buyer_premium_rate(schedule, seller_account_type="partner_pro"))
    ppro_sc = float(resolve_seller_commission_rate(schedule, seller_account_type="partner_pro"))
    add("P5.partner_pro_rates_from_schedule",
        ok=(round(ppro_bp, 6) == 0.037500 and round(ppro_sc, 6) == 0.030000),
        bp=ppro_bp, sc=ppro_sc)

    # P6: Zero-double-charge — for a $100 hammer Partner 10% sale, buyer
    # total must equal $110, NOT $113.  Directive Section 23 CRITICAL.
    add("P6.no_double_charge_of_platform_fee",
        ok=(_c(fee_p1["buyer_total_charged"]) == 11000       # $110
            and _c(fee_p1["buyer_total_charged"]) != 11300), # not $113
        buyer_total=fee_p1["buyer_total_charged"])

    # P7: Partner net payout DOES account for the 3% BidVex platform fee.
    # For a Partner sale, seller_payout in the current FeeResult carries
    # "partner_owes" (money BidVex will withhold from the transfer to
    # partner).  It MUST be non-zero, equal to bidvex_fee + stripe + tax.
    add("P7.partner_net_accounts_for_platform_fee",
        ok=(fee_p1["seller_payout"] > 0
            and abs(fee_p1["seller_payout"]
                    - (fee_p1["bidvex_platform_fee_amount"]
                       + fee_p1["seller_stripe_recovery"]
                       + fee_p1["seller_taxes"])) < 0.005),
        seller_payout=fee_p1["seller_payout"],
        components={
            "bidvex_platform_fee": fee_p1["bidvex_platform_fee_amount"],
            "seller_stripe_recovery": fee_p1["seller_stripe_recovery"],
            "seller_taxes": fee_p1["seller_taxes"],
        })

    # P8: Fields are DISTINCT even when they numerically match.  The
    # FeeResult exposes ``buyer_premium`` (partner BP) and
    # ``bidvex_platform_fee_amount`` (BidVex 3%) as DIFFERENT keys.
    add("P8.partner_bp_vs_platform_fee_distinct_fields",
        ok=("bidvex_platform_fee_amount" in fee_p1
            and "buyer_premium" in fee_p1
            and _c(fee_p1["buyer_premium"]) != _c(fee_p1["bidvex_platform_fee_amount"])),
        bp=fee_p1["buyer_premium"], platform=fee_p1["bidvex_platform_fee_amount"])

    # ══════════════════════════════════════════════════════════
    #  PDF proofs — new canonical PDF renders "BidVex Platform Fee"
    # ══════════════════════════════════════════════════════════
    buyer_id  = await _ensure_user(db, email="iter480qa_buyer@test.com",
                                    name="iter480 QA Buyer")
    seller_id = await _ensure_user(db, email="iter480qa_partner@test.com",
                                    name="iter480 Partner Seller Inc.")

    lid = f"{PREFIX}mkt-{uuid.uuid4().hex[:8]}"
    await db.listings.insert_one({
        "id":              lid,
        "title":           "iter480 QA · Partner sale $100 · 10% BP",
        "status":          "sold",
        "winner_user_id":  buyer_id,
        "seller_id":       seller_id,
        "final_price":     100.00,
        "iter480qa_seed":  True,
    })
    await _seed_partner_receipt(
        db, listing_id=lid,
        listing_title="iter480 QA · Partner sale $100 · 10% BP",
        buyer_id=buyer_id, seller_id=seller_id, partner_bp_rate=0.10,
    )

    # T-PDF-1: BUYER PDF shows partner BP, NOT platform fee
    pdf_buyer = await generate_universal_receipt(
        db, section="marketplace", listing_id=lid, user_id=buyer_id, lang="en",
    )
    text_buyer = _extract_text(pdf_buyer)
    add("T_PDF_1.buyer_receipt_shows_buyer_premium",
        ok=("Buyer's Premium" in text_buyer and "CA$10.00" in text_buyer),
        snippet=text_buyer[:200].replace("\n", " | "))
    add("T_PDF_2.buyer_receipt_does_NOT_show_bidvex_platform_fee_as_buyer_charge",
        ok=("BidVex Platform Fee" not in text_buyer),
        note="Partner Platform Fee is a Partner cost, not a buyer charge")
    add("T_PDF_3.buyer_total_paid_is_110_not_113",
        ok=("CA$110.00" in text_buyer and "CA$113.00" not in text_buyer))

    # T-PDF-4: SELLER STATEMENT shows "BidVex Platform Fee" (not "Seller Commission")
    pdf_seller = await generate_marketplace_seller_statement(
        db, listing_id=lid, seller_id=seller_id, lang="en",
    )
    text_seller = _extract_text(pdf_seller)
    add("T_PDF_4.seller_statement_shows_BidVex_Platform_Fee_label",
        ok=("BidVex Platform Fee" in text_seller
            and "CA$3.00" in text_seller),
        snippet=text_seller.split("BidVex Platform Fee")[0][-60:]
              + "BidVex Platform Fee" +
              text_seller.split("BidVex Platform Fee")[-1][:60]
              if "BidVex Platform Fee" in text_seller else "NOT FOUND")
    add("T_PDF_5.seller_statement_does_NOT_show_ambiguous_Seller_Commission",
        ok=("Seller Commission" not in text_seller),
        note="Partner path: BidVex fee is NOT a seller commission")

    # T-PDF-6: Commission Invoice — itemized breakdown must show new labels
    pdf_comm = await generate_marketplace_seller_commission_invoice(
        db, listing_id=lid, seller_id=seller_id, lang="en",
    )
    text_comm = _extract_text(pdf_comm)
    add("T_PDF_6.commission_invoice_itemized_shows_BidVex_Platform_Fee",
        ok=("BidVex Platform Fee" in text_comm
            and "CA$3.00" in text_comm))

    # T-PDF-7: FR seller statement renders French label
    pdf_seller_fr = await generate_marketplace_seller_statement(
        db, listing_id=lid, seller_id=seller_id, lang="fr",
    )
    text_seller_fr = _extract_text(pdf_seller_fr)
    add("T_PDF_7.fr_seller_statement_uses_Frais_de_plateforme_BidVex",
        ok=("Frais de plateforme BidVex" in text_seller_fr
            and "CA$3.00" in text_seller_fr))

    # ══════════════════════════════════════════════════════════
    #  Historical fallback: seed a LEGACY partner receipt (no
    #  bidvex_platform_fee_amount field) and confirm PDF still renders
    #  "Seller Commission $3.00" (backward compatibility).
    # ══════════════════════════════════════════════════════════
    legacy_lid = f"{PREFIX}mkt-legacy-{uuid.uuid4().hex[:8]}"
    await db.listings.insert_one({
        "id":              legacy_lid,
        "title":           "iter480 QA · LEGACY Partner sale (pre-iter480)",
        "status":          "sold",
        "winner_user_id":  buyer_id,
        "seller_id":       seller_id,
        "final_price":     100.00,
        "iter480qa_seed":  True,
    })
    legacy_doc = {
        "id":              str(uuid.uuid4()),
        "type":            "buyer_receipt",
        "user_id":         buyer_id,
        "section":         "marketplace",
        "listing_id":      legacy_lid,
        "listing_title":   "iter480 QA · LEGACY Partner sale (pre-iter480)",
        "hammer_price":    100.00, "platform_fee": 0.0, "taxes": 0.0,
        "processing_fee":  0.0, "total_charged": 110.00, "net_payout": 3.00,
        "currency":        "CAD", "created_at": NOW,
        "order_number":    f"BVX-LEG-{uuid.uuid4().hex[:6].upper()}",
        "seller_name":     "Legacy Partner Seller", "quantity": 1,
        # iter476 itemized — legacy Partner-shape: BidVex fee under seller_commission
        "buyer_premium": 10.00, "buyer_premium_rate": 0.10,
        "buyer_premium_gst": 0.0, "buyer_premium_qst": 0.0,
        "hammer_gst": 0.0, "hammer_qst": 0.0,
        "service_fee": 0.0, "service_fee_gst": 0.0, "service_fee_qst": 0.0,
        "stripe_fee": 0.0, "stripe_fee_charged_to": "buyer",
        # LEGACY partner receipt — BidVex fee stuffed into seller_commission
        "seller_commission":      3.00,
        "seller_commission_rate": 0.03,
        "seller_commission_gst":  0.0,
        "seller_commission_qst":  0.0,
        "other_deductions": 0.0, "seller_is_tax_registered": False,
        "bidvex_gst_number": "706766367RT0001",
        "bidvex_qst_number": "1233530880TQ0001",
        # NO iter480 fields — this is a LEGACY receipt
        "fee_model_version": "iter350",
        "itemized_reconciled": True, "itemized_version": 1,
        "iter480qa_seed": True,
    }
    seller_legacy = {k: v for k, v in legacy_doc.items() if k != "_id"}
    seller_legacy["id"]      = str(uuid.uuid4())
    seller_legacy["type"]    = "seller_statement"
    seller_legacy["user_id"] = seller_id
    # Build the seller mirror BEFORE the first insert (else pymongo has
    # already stamped _id onto legacy_doc and dict() would copy it).
    await db.receipts.insert_one(legacy_doc)
    await db.receipts.insert_one(seller_legacy)

    pdf_legacy = await generate_marketplace_seller_statement(
        db, listing_id=legacy_lid, seller_id=seller_id, lang="en",
    )
    text_legacy = _extract_text(pdf_legacy)
    add("T_PDF_LEGACY.legacy_receipt_still_shows_Seller_Commission",
        ok=("Seller Commission" in text_legacy
            and "BidVex Platform Fee" not in text_legacy
            and "CA$3.00" in text_legacy),
        note="Historical partner receipts render unchanged — backward compat preserved")

    await cleanup(db)

    # ══════════════════════════════════════════════════════════
    passed = sum(1 for r in results if r["ok"])
    total  = len(results)
    out = {
        "iter": "480-phase3-partner-separation",
        "passed": passed, "total": total,
        "canonical_partner_100_10pct_example": {
            "hammer_price":       fee_p1["hammer_price"],
            "buyer_premium":      fee_p1["buyer_premium"],
            "buyer_total_charged": fee_p1["buyer_total_charged"],
            "bidvex_platform_fee_amount": fee_p1["bidvex_platform_fee_amount"],
            "bidvex_platform_fee_rate":   fee_p1["bidvex_platform_fee_rate"],
            "seller_payout_partner_owes": fee_p1["seller_payout"],
            "seller_stripe_recovery":     fee_p1["seller_stripe_recovery"],
            "seller_taxes":               fee_p1["seller_taxes"],
        },
        "results": results,
    }
    p = Path("/app/test_reports/iter480_phase3_partner_separation.json")
    p.parent.mkdir(exist_ok=True, parents=True)
    p.write_text(json.dumps(out, indent=2, default=str))
    print(f"[iter480] {passed}/{total} passed → {p}")
    for r in results:
        flag = "OK" if r["ok"] else "FAIL"
        extra = json.dumps({k: v for k, v in r.items() if k not in ("test", "ok")}, default=str)[:200]
        print(f"  [{flag:4}] {r['test']:60s} {extra}")


if __name__ == "__main__":
    asyncio.run(main())
