"""iter475/476 — Universal Receipt PDF.

One PDF template that renders a BidVex buyer receipt for ANY paid
purchase across marketplace / lots / vehicles / storage.  Reads the
canonical `db.receipts` row(s) — never recomputes fees, taxes, or
totals.  For multi-lot orders (multiple `buyer_receipt` rows sharing
one `listing_id`) the generator aggregates them into a single
order-level receipt with one line per lot.

iter476 — renders BOTH parties (buyer + seller) side-by-side with full
identification, plus the itemized settlement breakdown (hammer /
buyer's premium / service fee / provincial taxes / Stripe fee /
grand total).  Every dollar figure is read verbatim from `db.receipts`.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.pdf_generators.common import (
    DocumentSpec, render_document, load_receipts_for_buyer,
    money, sum_field, latest_currency,
    party_from_user, build_itemized_rows_for_buyer,
)
from services.pdf_generators.branding import resolve_seller_logo_bytes

logger = logging.getLogger(__name__)


SECTION_TITLES_EN = {
    "marketplace": "Marketplace",
    "lots":        "Multi-lot Auction",
    "vehicles":    "Vehicle Auction",
    "storage":     "Storage Auction",
}
SECTION_TITLES_FR = {
    "marketplace": "Place de marché",
    "lots":        "Enchère multi-lot",
    "vehicles":    "Enchère véhicules",
    "storage":     "Enchère de casier",
}


async def generate_universal_receipt(
    db, *, section: str, listing_id: str, user_id: str, lang: str = "en",
    lot_number: Optional[int] = None,
) -> Optional[bytes]:
    """Return the universal-receipt PDF as bytes."""
    rows = await load_receipts_for_buyer(
        db, section=section, listing_id=listing_id, user_id=user_id,
    )
    if lot_number is not None:
        rows = [r for r in rows if r.get("lot_number") == lot_number]
    if not rows:
        return None

    first_row = rows[0]
    order_ref = first_row.get("order_number") or first_row.get("id") or "—"
    currency = latest_currency(rows)

    # Resolve BOTH parties from db.users
    buyer = await db.users.find_one({"id": user_id}, {"_id": 0}) or {}
    # find seller_id from the corresponding seller_statement rows if
    # present, else from the listing document
    seller_id = first_row.get("seller_id") or first_row.get("seller_user_id")
    if not seller_id:
        listing_col = {
            "marketplace": "listings",
            "lots": "multi_item_listings",
            "vehicles": "vehicle_listings",
            "storage": "storage_auctions",
        }.get(section, "listings")
        listing_doc = await db[listing_col].find_one(
            {"id": listing_id}, {"_id": 0, "seller_id": 1, "facility_owner_id": 1}
        ) or {}
        seller_id = listing_doc.get("seller_id") or listing_doc.get("facility_owner_id")
    seller = await db.users.find_one({"id": seller_id}, {"_id": 0}) if seller_id else {}
    seller = seller or {}

    buyer_p = party_from_user(buyer)
    seller_p = party_from_user(seller)

    # Seller logo — fetched from S3 for embedding on buyer-facing docs
    seller_logo = await resolve_seller_logo_bytes(db, seller_id) if seller_id else None

    section_title_en = SECTION_TITLES_EN.get(section, section)
    section_title_fr = SECTION_TITLES_FR.get(section, section)
    meta_rows = [
        ("Section", "Section",
         f"{section_title_en} · {section_title_fr}" if lang == "en"
         else f"{section_title_fr} · {section_title_en}"),
        ("Order",         "Commande",   order_ref),
        ("Listing ID",    "ID annonce", listing_id),
        ("Lots included", "Lots inclus", str(len(rows))),
        ("Fee model",     "Modèle de frais",
         first_row.get("itemized_version") and "iter476 · itemized" or "legacy · aggregate"),
    ]

    line_headers_en = ["Lot", "Item", "Qty", "Hammer", "Total"]
    line_headers_fr = ["Lot", "Article", "Qté", "Marteau", "Total"]
    line_rows: List[List[str]] = []
    for r in rows:
        lot = "—" if r.get("lot_number") is None else str(r["lot_number"])
        line_rows.append([
            lot,
            (r.get("listing_title") or "")[:60],
            str(r.get("quantity") or 1),
            money(r.get("hammer_price"), currency=currency),
            money(r.get("total_charged"), currency=currency),
        ])

    itemized = build_itemized_rows_for_buyer(rows, currency=currency, lang=lang)

    doc_id = f"BV-RCPT-{(order_ref or listing_id)[-8:].upper()}"

    spec = DocumentSpec(
        title_en="RECEIPT",
        title_fr="REÇU",
        document_id=doc_id,
        document_date=first_row.get("created_at") or datetime.now(timezone.utc),
        lang=lang,
        buyer_name=buyer_p["name"], buyer_email=buyer_p["email"],
        buyer_phone=buyer_p["phone"], buyer_address=buyer_p["address"],
        buyer_gst=buyer_p["gst"], buyer_qst=buyer_p["qst"],
        buyer_tax_number=buyer_p["tax_number"],
        seller_name=seller_p["name"], seller_email=seller_p["email"],
        seller_phone=seller_p["phone"], seller_address=seller_p["address"],
        seller_gst=seller_p["gst"], seller_qst=seller_p["qst"],
        seller_tax_number=seller_p["tax_number"],
        seller_logo_bytes=seller_logo,
        show_seller_logo=True,   # buyer-facing doc → show seller logo
        meta_rows=meta_rows,
        line_headers_en=line_headers_en,
        line_headers_fr=line_headers_fr,
        line_rows=line_rows,
        itemized_rows=itemized,
        disclaimer_en=(
            "This receipt reflects amounts already settled with BidVex. "
            "Stripe card processing fee applied to this transaction "
            "when shown. Fields marked '—' were not persisted at the "
            "time of the original settlement."
        ),
        disclaimer_fr=(
            "Ce reçu reflète les montants déjà réglés auprès de BidVex. "
            "Les frais de traitement Stripe sont indiqués le cas "
            "échéant. Les champs affichés « — » n'ont pas été "
            "enregistrés au moment du règlement original."
        ),
    )
    return render_document(spec)
