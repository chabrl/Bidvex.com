"""iter475 — Section-specific document PDFs.

Each generator returns PDF bytes.  Every dollar figure is read verbatim
from `db.receipts` (never recomputed).

Generators:
  * `generate_storage_buyer_invoice`  — storage section buyer invoice
  * `generate_marketplace_seller_statement` — marketplace seller
    statement (aggregates one seller's marketplace `seller_statement`
    receipts on a single-item listing)
  * `generate_marketplace_seller_receipt`   — marketplace seller receipt
  * `generate_vehicle_seller_statement`     — vehicle-auction seller
    statement (per vehicle multi-lot event, aggregates all lots owned by
    the seller)
  * `generate_vehicle_seller_receipt`       — vehicle-auction seller
    receipt
  * `generate_vehicle_seller_commission_invoice` — vehicle-auction seller
    commission invoice
  * `generate_storage_seller_statement` / _receipt / _commission_invoice
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.pdf_generators.common import (
    DocumentSpec, render_document, money, sum_field, latest_currency,
    load_receipts_for_seller, load_receipts_for_buyer,
)


# ═══════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════

def _stable_doc_id(prefix: str, listing_id: str, user_id: str) -> str:
    """Deterministic invoice number so re-generation returns the same
    identifier and `db.invoices` unique-index (section, listing, user,
    invoice_type) can dedupe safely."""
    return f"{prefix}-{listing_id[-6:].upper()}-{user_id[-4:].upper()}"


async def _fetch_user(db, user_id: str) -> Dict[str, Any]:
    return (await db.users.find_one({"id": user_id}, {"_id": 0}) or {})


def _party(user: Dict[str, Any]) -> Dict[str, str]:
    return {
        "party_name":    user.get("name") or user.get("email") or "",
        "party_email":   user.get("email") or "",
        "party_phone":   user.get("phone") or "",
        "party_address": user.get("address") or "",
    }


# ═══════════════════════════════════════════════════════════════════
#  STORAGE — BUYER INVOICE
# ═══════════════════════════════════════════════════════════════════

async def generate_storage_buyer_invoice(
    db, *, listing_id: str, user_id: str, lang: str = "en",
) -> Optional[bytes]:
    rows = await load_receipts_for_buyer(
        db, section="storage", listing_id=listing_id, user_id=user_id,
    )
    if not rows:
        return None

    buyer = await _fetch_user(db, user_id)
    listing = await db.storage_auctions.find_one(
        {"id": listing_id}, {"_id": 0, "title": 1, "facility_id": 1,
                             "facility_name": 1, "location": 1}
    ) or {}
    currency = latest_currency(rows)
    first = rows[0]

    meta_rows = [
        ("Auction",     "Enchère",     listing.get("title") or listing_id),
        ("Facility",    "Installation", listing.get("facility_name") or "—"),
        ("Location",    "Emplacement", listing.get("location") or "—"),
        ("Order",       "Commande",    first.get("order_number") or "—"),
    ]

    line_headers_en = ["Item", "Qty", "Hammer", "Total"]
    line_headers_fr = ["Article", "Qté", "Marteau", "Total"]
    line_rows = [[
        (r.get("listing_title") or listing.get("title") or "")[:60],
        str(r.get("quantity") or 1),
        money(r.get("hammer_price"), currency=currency),
        money(r.get("total_charged"), currency=currency),
    ] for r in rows]

    totals = [
        ("Hammer subtotal", "Sous-total marteau", sum_field(rows, "hammer_price")),
        ("Platform fee",    "Frais de plateforme", sum_field(rows, "platform_fee")),
        ("Taxes",           "Taxes",               sum_field(rows, "taxes")),
        ("Processing fee",  "Frais de traitement", sum_field(rows, "processing_fee")),
        ("TOTAL DUE / PAID","TOTAL DÛ / PAYÉ",     sum_field(rows, "total_charged")),
    ]

    spec = DocumentSpec(
        title_en="STORAGE INVOICE",
        title_fr="FACTURE DE CASIER",
        document_id=_stable_doc_id("BV-STO-INV", listing_id, user_id),
        document_date=first.get("created_at") or datetime.now(timezone.utc),
        lang=lang,
        party_label_en="BILL TO",
        party_label_fr="FACTURER À",
        **_party(buyer),
        meta_rows=meta_rows,
        line_headers_en=line_headers_en,
        line_headers_fr=line_headers_fr,
        line_rows=line_rows,
        totals=totals,
    )
    return render_document(spec)


# ═══════════════════════════════════════════════════════════════════
#  Seller Statement (marketplace / vehicles / storage)
# ═══════════════════════════════════════════════════════════════════

async def _generate_generic_seller_statement(
    db, *, section: str, listing_id: str, seller_id: str, lang: str,
    listing_collection: str,
    title_en: str, title_fr: str,
    section_label_en: str, section_label_fr: str,
) -> Optional[bytes]:
    rows = await load_receipts_for_seller(
        db, section=section, listing_id=listing_id, seller_id=seller_id,
    )
    if not rows:
        return None
    seller = await _fetch_user(db, seller_id)
    listing = await db[listing_collection].find_one(
        {"id": listing_id}, {"_id": 0, "title": 1}
    ) or {}
    currency = latest_currency(rows)
    first = rows[0]

    meta_rows = [
        ("Section", "Section", f"{section_label_en} · {section_label_fr}"
         if lang == "en" else f"{section_label_fr} · {section_label_en}"),
        ("Auction",  "Enchère",  listing.get("title") or listing_id),
        ("Listing ID","ID annonce", listing_id),
        ("Line items","Lignes",   str(len(rows))),
    ]

    line_headers_en = ["Lot", "Item", "Qty", "Hammer", "Net payout"]
    line_headers_fr = ["Lot", "Article", "Qté", "Marteau", "Paiement net"]
    line_rows = [[
        "—" if r.get("lot_number") is None else str(r["lot_number"]),
        (r.get("listing_title") or "")[:60],
        str(r.get("quantity") or 1),
        money(r.get("hammer_price"), currency=currency),
        money(r.get("net_payout"), currency=currency),
    ] for r in rows]

    totals = [
        ("Hammer subtotal", "Sous-total marteau", sum_field(rows, "hammer_price")),
        ("Platform commission", "Commission de plateforme", sum_field(rows, "platform_fee")),
        ("Taxes on commission", "Taxes sur commission", sum_field(rows, "taxes")),
        ("Processing fee",  "Frais de traitement", sum_field(rows, "processing_fee")),
        ("NET PAYOUT",      "PAIEMENT NET",       sum_field(rows, "net_payout")),
    ]

    spec = DocumentSpec(
        title_en=title_en,
        title_fr=title_fr,
        document_id=_stable_doc_id("BV-STMT", listing_id, seller_id),
        document_date=first.get("created_at") or datetime.now(timezone.utc),
        lang=lang,
        party_label_en="PAYEE",
        party_label_fr="BÉNÉFICIAIRE",
        **_party(seller),
        meta_rows=meta_rows,
        line_headers_en=line_headers_en,
        line_headers_fr=line_headers_fr,
        line_rows=line_rows,
        totals=totals,
        disclaimer_en=(
            "Payout is issued through your registered payout method. "
            "See the seller receipt for a payment confirmation."
        ),
        disclaimer_fr=(
            "Le paiement est effectué via votre méthode de versement "
            "enregistrée. Consultez le reçu du vendeur pour la "
            "confirmation de paiement."
        ),
    )
    return render_document(spec)


# ═══════════════════════════════════════════════════════════════════
#  Seller Receipt (marketplace / vehicles / storage)
# ═══════════════════════════════════════════════════════════════════

async def _generate_generic_seller_receipt(
    db, *, section: str, listing_id: str, seller_id: str, lang: str,
    listing_collection: str,
    title_en: str, title_fr: str,
) -> Optional[bytes]:
    rows = await load_receipts_for_seller(
        db, section=section, listing_id=listing_id, seller_id=seller_id,
    )
    if not rows:
        return None
    seller = await _fetch_user(db, seller_id)
    listing = await db[listing_collection].find_one(
        {"id": listing_id}, {"_id": 0, "title": 1}
    ) or {}
    currency = latest_currency(rows)
    first = rows[0]

    meta_rows = [
        ("Auction",  "Enchère",  listing.get("title") or listing_id),
        ("Payout method", "Méthode de versement", seller.get("payout_method") or "Stripe Connect"),
        ("Reference", "Référence", first.get("payout_reference") or first.get("order_number") or "—"),
    ]

    totals = [
        ("Hammer settled", "Marteau réglé",  sum_field(rows, "hammer_price")),
        ("Commission withheld", "Commission retenue", sum_field(rows, "platform_fee")),
        ("Taxes on commission", "Taxes sur commission", sum_field(rows, "taxes")),
        ("Processing withheld", "Traitement retenu", sum_field(rows, "processing_fee")),
        ("NET PAID TO SELLER", "PAYÉ AU VENDEUR", sum_field(rows, "net_payout")),
    ]

    spec = DocumentSpec(
        title_en=title_en,
        title_fr=title_fr,
        document_id=_stable_doc_id("BV-SRCPT", listing_id, seller_id),
        document_date=first.get("created_at") or datetime.now(timezone.utc),
        lang=lang,
        party_label_en="PAID TO",
        party_label_fr="PAYÉ À",
        **_party(seller),
        meta_rows=meta_rows,
        totals=totals,
    )
    return render_document(spec)


# ═══════════════════════════════════════════════════════════════════
#  Seller Commission Invoice (marketplace / vehicles / storage)
# ═══════════════════════════════════════════════════════════════════

async def _generate_generic_commission_invoice(
    db, *, section: str, listing_id: str, seller_id: str, lang: str,
    listing_collection: str,
    title_en: str, title_fr: str,
) -> Optional[bytes]:
    rows = await load_receipts_for_seller(
        db, section=section, listing_id=listing_id, seller_id=seller_id,
    )
    if not rows:
        return None
    seller = await _fetch_user(db, seller_id)
    listing = await db[listing_collection].find_one(
        {"id": listing_id}, {"_id": 0, "title": 1}
    ) or {}
    currency = latest_currency(rows)
    first = rows[0]

    meta_rows = [
        ("Auction",  "Enchère",  listing.get("title") or listing_id),
        ("Listing ID","ID annonce", listing_id),
        ("Line items","Lignes",   str(len(rows))),
    ]

    line_headers_en = ["Lot", "Hammer", "Commission", "Tax on comm.", "Total"]
    line_headers_fr = ["Lot", "Marteau", "Commission", "Taxe sur comm.", "Total"]
    line_rows = [[
        "—" if r.get("lot_number") is None else str(r["lot_number"]),
        money(r.get("hammer_price"), currency=currency),
        money(r.get("platform_fee"), currency=currency),
        money(r.get("taxes"), currency=currency),
        money((float(r.get("platform_fee") or 0) + float(r.get("taxes") or 0)), currency=currency),
    ] for r in rows]

    totals = [
        ("Total commission",    "Commission totale",   sum_field(rows, "platform_fee")),
        ("Total tax",           "Taxes totales",       sum_field(rows, "taxes")),
        ("AMOUNT WITHHELD",     "MONTANT RETENU",      sum_field(rows, "platform_fee")),  # note
    ]

    spec = DocumentSpec(
        title_en=title_en,
        title_fr=title_fr,
        document_id=_stable_doc_id("BV-COMM", listing_id, seller_id),
        document_date=first.get("created_at") or datetime.now(timezone.utc),
        lang=lang,
        party_label_en="BILLED TO",
        party_label_fr="FACTURÉ À",
        **_party(seller),
        meta_rows=meta_rows,
        line_headers_en=line_headers_en,
        line_headers_fr=line_headers_fr,
        line_rows=line_rows,
        totals=totals,
        disclaimer_en=(
            "This commission was withheld from your gross hammer proceeds. "
            "See the seller statement for the net payout."
        ),
        disclaimer_fr=(
            "Cette commission a été retenue sur votre marteau brut. "
            "Consultez le relevé de règlement du vendeur pour le montant net."
        ),
    )
    return render_document(spec)


# ═══════════════════════════════════════════════════════════════════
#  Public API — thin wrappers per (section, kind)
# ═══════════════════════════════════════════════════════════════════

# Marketplace
async def generate_marketplace_seller_statement(db, *, listing_id, seller_id, lang="en"):
    return await _generate_generic_seller_statement(
        db, section="marketplace", listing_id=listing_id, seller_id=seller_id,
        lang=lang, listing_collection="listings",
        title_en="MARKETPLACE SELLER STATEMENT",
        title_fr="RELEVÉ VENDEUR — PLACE DE MARCHÉ",
        section_label_en="Marketplace", section_label_fr="Place de marché",
    )


async def generate_marketplace_seller_receipt(db, *, listing_id, seller_id, lang="en"):
    return await _generate_generic_seller_receipt(
        db, section="marketplace", listing_id=listing_id, seller_id=seller_id,
        lang=lang, listing_collection="listings",
        title_en="MARKETPLACE SELLER RECEIPT",
        title_fr="REÇU DU VENDEUR — PLACE DE MARCHÉ",
    )


async def generate_marketplace_seller_commission_invoice(db, *, listing_id, seller_id, lang="en"):
    return await _generate_generic_commission_invoice(
        db, section="marketplace", listing_id=listing_id, seller_id=seller_id,
        lang=lang, listing_collection="listings",
        title_en="MARKETPLACE COMMISSION INVOICE",
        title_fr="FACTURE DE COMMISSION — PLACE DE MARCHÉ",
    )


# Vehicles
async def generate_vehicle_seller_statement(db, *, listing_id, seller_id, lang="en"):
    return await _generate_generic_seller_statement(
        db, section="vehicles", listing_id=listing_id, seller_id=seller_id,
        lang=lang, listing_collection="vehicle_listings",
        title_en="VEHICLE SELLER STATEMENT",
        title_fr="RELEVÉ VENDEUR — VÉHICULES",
        section_label_en="Vehicles", section_label_fr="Véhicules",
    )


async def generate_vehicle_seller_receipt(db, *, listing_id, seller_id, lang="en"):
    return await _generate_generic_seller_receipt(
        db, section="vehicles", listing_id=listing_id, seller_id=seller_id,
        lang=lang, listing_collection="vehicle_listings",
        title_en="VEHICLE SELLER RECEIPT",
        title_fr="REÇU DU VENDEUR — VÉHICULES",
    )


async def generate_vehicle_seller_commission_invoice(db, *, listing_id, seller_id, lang="en"):
    return await _generate_generic_commission_invoice(
        db, section="vehicles", listing_id=listing_id, seller_id=seller_id,
        lang=lang, listing_collection="vehicle_listings",
        title_en="VEHICLE COMMISSION INVOICE",
        title_fr="FACTURE DE COMMISSION — VÉHICULES",
    )


# Storage sellers
async def generate_storage_seller_statement(db, *, listing_id, seller_id, lang="en"):
    return await _generate_generic_seller_statement(
        db, section="storage", listing_id=listing_id, seller_id=seller_id,
        lang=lang, listing_collection="storage_auctions",
        title_en="STORAGE SELLER STATEMENT",
        title_fr="RELEVÉ VENDEUR — CASIER",
        section_label_en="Storage", section_label_fr="Casier",
    )


async def generate_storage_seller_receipt(db, *, listing_id, seller_id, lang="en"):
    return await _generate_generic_seller_receipt(
        db, section="storage", listing_id=listing_id, seller_id=seller_id,
        lang=lang, listing_collection="storage_auctions",
        title_en="STORAGE SELLER RECEIPT",
        title_fr="REÇU DU VENDEUR — CASIER",
    )


async def generate_storage_seller_commission_invoice(db, *, listing_id, seller_id, lang="en"):
    return await _generate_generic_commission_invoice(
        db, section="storage", listing_id=listing_id, seller_id=seller_id,
        lang=lang, listing_collection="storage_auctions",
        title_en="STORAGE COMMISSION INVOICE",
        title_fr="FACTURE DE COMMISSION — CASIER",
    )
