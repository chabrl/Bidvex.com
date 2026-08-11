"""iter475/476 — Section-specific document PDFs.

Every generator returns PDF bytes. Every dollar figure is read verbatim
from `db.receipts` (never recomputed). iter476: both parties + itemized
breakdown + BidVex letterhead + optional seller logo on buyer docs.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.pdf_generators.common import (
    DocumentSpec, render_document, money, sum_field, latest_currency,
    load_receipts_for_seller, load_receipts_for_buyer,
    party_from_user, build_itemized_rows_for_buyer,
    build_itemized_rows_for_seller,
)
from services.pdf_generators.branding import resolve_seller_logo_bytes


# ═══════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════

def _stable_doc_id(prefix: str, listing_id: str, user_id: str) -> str:
    return f"{prefix}-{listing_id[-6:].upper()}-{user_id[-4:].upper()}"


async def _fetch_user(db, user_id: str) -> Dict[str, Any]:
    return (await db.users.find_one({"id": user_id}, {"_id": 0}) or {})


async def _resolve_counterparty(
    db, *, section: str, listing_id: str, my_id: str, my_role: str,
    receipts: List[Dict[str, Any]],
) -> Optional[str]:
    """Given the current caller (buyer or seller) find the counterparty
    id from either the receipts themselves or the listing document."""
    # Try the receipts first (some receipts stamp buyer_id / seller_id
    # explicitly).
    for r in receipts:
        cp = r.get("seller_id" if my_role == "buyer" else "buyer_id")
        if cp and cp != my_id:
            return cp
    listing_col = {
        "marketplace": "listings",
        "lots": "multi_item_listings",
        "vehicles": "vehicle_listings",
        "storage": "storage_auctions",
    }.get(section, "listings")
    doc = await db[listing_col].find_one(
        {"id": listing_id},
        {"_id": 0, "seller_id": 1, "facility_owner_id": 1,
         "winner_user_id": 1, "winning_bidder_id": 1,
         "highest_bidder_id": 1},
    ) or {}
    if my_role == "buyer":
        return doc.get("seller_id") or doc.get("facility_owner_id")
    return (doc.get("winner_user_id") or doc.get("winning_bidder_id")
            or doc.get("highest_bidder_id"))


async def _build_two_party_kwargs(
    db, *, section: str, listing_id: str,
    buyer_id: Optional[str], seller_id: Optional[str],
    show_seller_logo: bool,
) -> Dict[str, Any]:
    """Return the buyer/seller identification block kwargs used by every
    iter476-standard DocumentSpec."""
    buyer = await _fetch_user(db, buyer_id) if buyer_id else {}
    seller = await _fetch_user(db, seller_id) if seller_id else {}
    bp = party_from_user(buyer)
    sp = party_from_user(seller)
    kwargs = {
        "buyer_name":       bp["name"],
        "buyer_email":      bp["email"],
        "buyer_phone":      bp["phone"],
        "buyer_address":    bp["address"],
        "buyer_gst":        bp["gst"],
        "buyer_qst":        bp["qst"],
        "buyer_tax_number": bp["tax_number"],
        "seller_name":      sp["name"],
        "seller_email":     sp["email"],
        "seller_phone":     sp["phone"],
        "seller_address":   sp["address"],
        "seller_gst":       sp["gst"],
        "seller_qst":       sp["qst"],
        "seller_tax_number": sp["tax_number"],
        "seller_logo_bytes": None,
        "show_seller_logo": show_seller_logo,
    }
    if show_seller_logo and seller_id:
        kwargs["seller_logo_bytes"] = await resolve_seller_logo_bytes(db, seller_id)
    return kwargs


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

    listing = await db.storage_auctions.find_one(
        {"id": listing_id}, {"_id": 0, "title": 1, "facility_id": 1,
                             "facility_name": 1, "location": 1,
                             "seller_id": 1, "facility_owner_id": 1}
    ) or {}
    currency = latest_currency(rows)
    first = rows[0]

    seller_id = listing.get("seller_id") or listing.get("facility_owner_id")
    party_kw = await _build_two_party_kwargs(
        db, section="storage", listing_id=listing_id,
        buyer_id=user_id, seller_id=seller_id, show_seller_logo=True,
    )

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

    itemized = build_itemized_rows_for_buyer(rows, currency=currency, lang=lang)

    spec = DocumentSpec(
        title_en="STORAGE INVOICE",
        title_fr="FACTURE DE CASIER",
        document_id=_stable_doc_id("BV-STO-INV", listing_id, user_id),
        document_date=first.get("created_at") or datetime.now(timezone.utc),
        lang=lang,
        **party_kw,
        meta_rows=meta_rows,
        line_headers_en=line_headers_en,
        line_headers_fr=line_headers_fr,
        line_rows=line_rows,
        itemized_rows=itemized,
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
    listing = await db[listing_collection].find_one(
        {"id": listing_id}, {"_id": 0, "title": 1}
    ) or {}
    currency = latest_currency(rows)
    first = rows[0]

    buyer_id = await _resolve_counterparty(
        db, section=section, listing_id=listing_id, my_id=seller_id,
        my_role="seller", receipts=rows,
    )
    party_kw = await _build_two_party_kwargs(
        db, section=section, listing_id=listing_id,
        buyer_id=buyer_id, seller_id=seller_id,
        show_seller_logo=False,   # seller-facing doc → no seller logo overlay
    )

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

    itemized = build_itemized_rows_for_seller(rows, currency=currency, lang=lang)

    spec = DocumentSpec(
        title_en=title_en,
        title_fr=title_fr,
        document_id=_stable_doc_id("BV-STMT", listing_id, seller_id),
        document_date=first.get("created_at") or datetime.now(timezone.utc),
        lang=lang,
        **party_kw,
        meta_rows=meta_rows,
        line_headers_en=line_headers_en,
        line_headers_fr=line_headers_fr,
        line_rows=line_rows,
        itemized_rows=itemized,
        disclaimer_en=(
            "Payout is issued through your registered payout method. "
            "See the seller receipt for a payment confirmation. Amounts "
            "shown as '—' were not persisted at the time of settlement."
        ),
        disclaimer_fr=(
            "Le paiement est effectué via votre méthode de versement "
            "enregistrée. Les montants affichés « — » n'ont pas été "
            "enregistrés au moment du règlement."
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

    buyer_id = await _resolve_counterparty(
        db, section=section, listing_id=listing_id, my_id=seller_id,
        my_role="seller", receipts=rows,
    )
    party_kw = await _build_two_party_kwargs(
        db, section=section, listing_id=listing_id,
        buyer_id=buyer_id, seller_id=seller_id,
        show_seller_logo=False,
    )

    meta_rows = [
        ("Auction",  "Enchère",  listing.get("title") or listing_id),
        ("Payout method", "Méthode de versement", seller.get("payout_method") or "Stripe Connect"),
        ("Reference", "Référence", first.get("payout_reference") or first.get("order_number") or "—"),
    ]

    itemized = build_itemized_rows_for_seller(rows, currency=currency, lang=lang)

    spec = DocumentSpec(
        title_en=title_en,
        title_fr=title_fr,
        document_id=_stable_doc_id("BV-SRCPT", listing_id, seller_id),
        document_date=first.get("created_at") or datetime.now(timezone.utc),
        lang=lang,
        **party_kw,
        meta_rows=meta_rows,
        itemized_rows=itemized,
    )
    return render_document(spec)


# ═══════════════════════════════════════════════════════════════════
#  Seller Commission Invoice
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
    listing = await db[listing_collection].find_one(
        {"id": listing_id}, {"_id": 0, "title": 1}
    ) or {}
    currency = latest_currency(rows)
    first = rows[0]

    buyer_id = await _resolve_counterparty(
        db, section=section, listing_id=listing_id, my_id=seller_id,
        my_role="seller", receipts=rows,
    )
    party_kw = await _build_two_party_kwargs(
        db, section=section, listing_id=listing_id,
        buyer_id=buyer_id, seller_id=seller_id,
        show_seller_logo=False,
    )

    meta_rows = [
        ("Auction",  "Enchère",  listing.get("title") or listing_id),
        ("Listing ID","ID annonce", listing_id),
        ("Line items","Lignes",   str(len(rows))),
    ]

    line_headers_en = ["Lot", "Hammer", "Commission", "Comm. tax", "Total"]
    line_headers_fr = ["Lot", "Marteau", "Commission", "Taxe comm.", "Total"]
    line_rows = []
    for r in rows:
        comm = r.get("seller_commission")
        comm_gst = r.get("seller_commission_gst")
        comm_qst = r.get("seller_commission_qst")
        line_rows.append([
            "—" if r.get("lot_number") is None else str(r["lot_number"]),
            money(r.get("hammer_price"), currency=currency),
            money(comm, currency=currency) if comm is not None else "—",
            money((float(comm_gst or 0) + float(comm_qst or 0)), currency=currency) if (comm_gst or comm_qst) is not None else "—",
            money((float(comm or 0) + float(comm_gst or 0) + float(comm_qst or 0)), currency=currency) if comm is not None else "—",
        ])

    # Reuse the seller itemized helper (shows commission, taxes, net)
    itemized = build_itemized_rows_for_seller(rows, currency=currency, lang=lang)

    spec = DocumentSpec(
        title_en=title_en,
        title_fr=title_fr,
        document_id=_stable_doc_id("BV-COMM", listing_id, seller_id),
        document_date=first.get("created_at") or datetime.now(timezone.utc),
        lang=lang,
        **party_kw,
        meta_rows=meta_rows,
        line_headers_en=line_headers_en,
        line_headers_fr=line_headers_fr,
        line_rows=line_rows,
        itemized_rows=itemized,
        disclaimer_en=(
            "This commission was withheld from your gross hammer proceeds. "
            "See the seller statement for the net payout."
        ),
        disclaimer_fr=(
            "Cette commission a été retenue sur votre marteau brut. "
            "Consultez le relevé du vendeur pour le montant net."
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
