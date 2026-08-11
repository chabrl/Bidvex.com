"""iter475 — Universal Receipt PDF.

One PDF template that renders a BidVex buyer receipt for ANY paid
purchase across marketplace / lots / vehicles / storage.  Reads the
canonical `db.receipts` row(s) — never recomputes fees, taxes, or
totals.  For multi-lot orders (multiple `buyer_receipt` rows sharing
one `listing_id`) the generator aggregates them into a single
order-level receipt with one line per lot.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.pdf_generators.common import (
    DocumentSpec, render_document, load_receipt, load_receipts_for_buyer,
    money, sum_field, latest_currency,
)

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
    """Return the universal-receipt PDF as bytes.

    If `lot_number` is `None` (single-item sections) or the buyer has
    multiple lots on the same listing, the receipt aggregates every
    matching row (order-level).  If a specific `lot_number` is supplied
    the receipt is scoped to that single lot.
    """
    # Load all buyer receipts for the (section, listing, buyer) — we
    # aggregate into ONE PDF per user directive (no duplicates).
    rows = await load_receipts_for_buyer(
        db, section=section, listing_id=listing_id, user_id=user_id,
    )
    if lot_number is not None:
        rows = [r for r in rows if r.get("lot_number") == lot_number]
    if not rows:
        return None

    # Buyer party block
    buyer = await db.users.find_one({"id": user_id}, {"_id": 0}) or {}
    party_name = buyer.get("name") or buyer.get("email") or "Buyer"
    party_email = buyer.get("email") or ""
    party_phone = buyer.get("phone") or ""

    # Meta rows: settlement identifiers pulled verbatim
    first_row = rows[0]
    order_ref = first_row.get("order_number") or first_row.get("id") or "—"
    currency = latest_currency(rows)
    section_title_en = SECTION_TITLES_EN.get(section, section)
    section_title_fr = SECTION_TITLES_FR.get(section, section)
    meta_rows = [
        ("Section",       "Section",       f"{section_title_en} · {section_title_fr}" if lang == "en" else f"{section_title_fr} · {section_title_en}"),
        ("Order",         "Commande",      order_ref),
        ("Listing ID",    "ID annonce",    listing_id),
        ("Lots included", "Lots inclus",   str(len(rows))),
    ]

    # Line-item table — one row per receipt row (lot)
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

    totals = [
        ("Hammer subtotal", "Sous-total marteau", sum_field(rows, "hammer_price")),
        ("Platform fee",    "Frais de plateforme", sum_field(rows, "platform_fee")),
        ("Taxes",           "Taxes",               sum_field(rows, "taxes")),
        ("Processing fee",  "Frais de traitement", sum_field(rows, "processing_fee")),
        ("TOTAL PAID",      "TOTAL PAYÉ",          sum_field(rows, "total_charged")),
    ]

    # Generate a stable document id (order_ref + section prefix)
    doc_id = f"BV-RCPT-{(order_ref or listing_id)[-8:].upper()}"

    spec = DocumentSpec(
        title_en="RECEIPT",
        title_fr="REÇU",
        document_id=doc_id,
        document_date=first_row.get("created_at") or datetime.now(timezone.utc),
        lang=lang,
        party_label_en="RECEIVED FROM",
        party_label_fr="REÇU DE",
        party_name=party_name,
        party_email=party_email,
        party_phone=party_phone,
        meta_rows=meta_rows,
        line_headers_en=line_headers_en,
        line_headers_fr=line_headers_fr,
        line_rows=line_rows,
        totals=totals,
        disclaimer_en=(
            "This receipt reflects amounts already settled with BidVex. "
            "It is not a new invoice."
        ),
        disclaimer_fr=(
            "Ce reçu reflète les montants déjà réglés auprès de BidVex. "
            "Il ne s'agit pas d'une nouvelle facture."
        ),
    )
    return render_document(spec)
