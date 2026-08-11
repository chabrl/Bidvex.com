"""iter475 — Shared PDF renderer used by every new BidVex document
generator (universal receipt, storage buyer/seller docs, marketplace
seller docs, vehicle seller docs).

Guiding rules
=============
1. **No math.**  Every dollar figure passed to `render_document` must have
   already been computed by the settlement pipeline (`db.receipts`,
   `db.transactions`, `db.invoices`).  This module NEVER multiplies,
   divides, adds tax, computes commission, or otherwise transforms
   monetary values.  It formats and lays them out.
2. **Bilingual EN/FR.**  Every rendered string is derived from the
   `DocumentSpec` structure so callers control the exact language mix.
3. **BidVex only.**  Letterhead is always the BidVex Inc. block from
   `services.pdf_invoice` — no partner co-branding, no dynamic issuer.
4. **Reuse existing style tokens** from `pdf_invoice.py` so the visual
   language is consistent across every document surface.
"""
from __future__ import annotations

import io
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, List, Optional, Sequence, Tuple

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Paragraph, Spacer, SimpleDocTemplate, Table, TableStyle,
)

from services.pdf_invoice import (
    PLATFORM_NAME, PLATFORM_ADDRESS, PLATFORM_GST, PLATFORM_QST,
    PLATFORM_PHONE, PLATFORM_EMAIL, PLATFORM_WEBSITE,
    PRIMARY_COLOR, SECONDARY_COLOR, ACCENT_COLOR, LIGHT_GRAY, BORDER_COLOR,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════

def money(amount, *, currency: str = "CAD") -> str:
    """Format a monetary amount. `amount` may be None/int/float/str/Decimal."""
    if amount is None or amount == "":
        return "—"
    try:
        d = Decimal(str(amount))
    except Exception:  # noqa: BLE001
        return "—"
    prefix = "$" if currency == "USD" else "CA$"
    return f"{prefix}{d:,.2f}"


def dt_str(dt) -> str:
    if not dt:
        return "—"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return dt
    return dt.strftime("%b %d, %Y")


def L(spec: "DocumentSpec", en: str, fr: str) -> str:
    return fr if spec.lang == "fr" else en


# ═══════════════════════════════════════════════════════════════════
#  DocumentSpec — every generator hands one of these to the renderer.
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DocumentSpec:
    """A pure data description of one BidVex document.

    Every field is either a plain string, an already-formatted amount, or
    a dict — the renderer never performs arithmetic on numeric fields.
    """
    # Header
    title_en:       str
    title_fr:       str
    document_id:    str                     # invoice_number or receipt_ref
    document_date:  Any                     # datetime or ISO str
    lang:           str = "en"              # "en" | "fr"

    # Party block (rendered top-right under BidVex letterhead)
    party_label_en: str = "PARTY"
    party_label_fr: str = "PARTIE"
    party_name:     str = ""
    party_email:    str = ""
    party_phone:    str = ""
    party_address:  str = ""

    # Settlement / listing meta (rendered as a two-column detail table)
    meta_rows:      List[Tuple[str, str, str]] = field(default_factory=list)
    # (label_en, label_fr, value_str)  — value already formatted by caller

    # Line-item table (settled figures — pre-formatted)
    line_headers_en: Sequence[str] = ()
    line_headers_fr: Sequence[str] = ()
    line_rows:       List[Sequence[str]] = field(default_factory=list)

    # Totals table (pre-formatted key/value pairs)
    totals:          List[Tuple[str, str, str]] = field(default_factory=list)
    # (label_en, label_fr, value_str)

    # Footer note (short, bilingual)
    footer_en:      str = "Questions? Contact service@bidvex.com"
    footer_fr:      str = "Des questions ? Contactez service@bidvex.com"

    # Optional watermark-style disclaimer at bottom (e.g. "This document is
    # not a receipt for payment")
    disclaimer_en:  str = ""
    disclaimer_fr:  str = ""


# ═══════════════════════════════════════════════════════════════════
#  Renderer
# ═══════════════════════════════════════════════════════════════════

def _make_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="DocTitle", fontSize=22, textColor=PRIMARY_COLOR,
        fontName="Helvetica-Bold", spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="DocSubtitle", fontSize=11, textColor=SECONDARY_COLOR,
        spaceAfter=14,
    ))
    styles.add(ParagraphStyle(
        name="SectionTitle", fontSize=11, textColor=SECONDARY_COLOR,
        fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        name="Detail", fontSize=10, textColor=SECONDARY_COLOR, leading=14,
    ))
    styles.add(ParagraphStyle(
        name="Tiny", fontSize=8, textColor=colors.gray, leading=10,
    ))
    styles.add(ParagraphStyle(
        name="Disclaimer", fontSize=8, textColor=colors.gray, leading=10,
        alignment=TA_CENTER,
    ))
    return styles


def render_document(spec: DocumentSpec) -> bytes:
    """Render a DocumentSpec to PDF bytes.  Deterministic — same spec in,
    same layout out.  No side effects, no DB reads."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.75 * inch, rightMargin=0.75 * inch,
        topMargin=0.5 * inch, bottomMargin=0.5 * inch,
    )
    styles = _make_styles()
    elems: List[Any] = []

    # ── Header: BidVex block + document title
    title = spec.title_fr if spec.lang == "fr" else spec.title_en
    header_data = [[
        Paragraph(f"<b>{PLATFORM_NAME}</b>", styles["Detail"]),
        Paragraph(f"<b>{title}</b>", styles["DocTitle"]),
    ], [
        Paragraph(
            f"{PLATFORM_ADDRESS}<br/>{PLATFORM_PHONE}<br/>"
            f"{PLATFORM_EMAIL}<br/>{PLATFORM_WEBSITE}",
            styles["Tiny"],
        ),
        Paragraph(
            f"{L(spec, 'No.', 'N°')} {spec.document_id}<br/>"
            f"{L(spec, 'Issued', 'Émis')}: {dt_str(spec.document_date)}",
            styles["Detail"],
        ),
    ]]
    header = Table(header_data, colWidths=[4 * inch, 3 * inch])
    header.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 4),
    ]))
    elems.append(header)
    elems.append(Spacer(1, 0.15 * inch))

    # ── Party block
    party_lbl = L(spec, spec.party_label_en, spec.party_label_fr)
    party_body: List[str] = []
    if spec.party_name:
        party_body.append(f"<b>{spec.party_name}</b>")
    if spec.party_email:
        party_body.append(spec.party_email)
    if spec.party_phone:
        party_body.append(spec.party_phone)
    if spec.party_address:
        party_body.append(spec.party_address)
    if party_body:
        elems.append(Paragraph(party_lbl, styles["SectionTitle"]))
        elems.append(Paragraph("<br/>".join(party_body), styles["Detail"]))

    # ── Meta rows
    if spec.meta_rows:
        elems.append(Paragraph(
            L(spec, "DETAILS", "DÉTAILS"), styles["SectionTitle"]))
        meta_data = [
            [
                Paragraph(L(spec, en, fr), styles["Detail"]),
                Paragraph(val or "—", styles["Detail"]),
            ]
            for (en, fr, val) in spec.meta_rows
        ]
        meta_tbl = Table(meta_data, colWidths=[2.2 * inch, 4.8 * inch])
        meta_tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("TEXTCOLOR", (0, 0), (0, -1), colors.gray),
        ]))
        elems.append(meta_tbl)

    # ── Line items table (only if headers provided)
    if spec.line_headers_en:
        headers = list(
            spec.line_headers_fr if spec.lang == "fr" else spec.line_headers_en
        )
        rows = [headers] + [list(r) for r in spec.line_rows]
        cw = _column_widths_for(len(headers))
        line_tbl = Table(rows, colWidths=cw, repeatRows=1)
        line_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_COLOR),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, BORDER_COLOR),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        elems.append(Spacer(1, 0.12 * inch))
        elems.append(line_tbl)

    # ── Totals table
    if spec.totals:
        totals_data = [
            [
                Paragraph(L(spec, en, fr), styles["Detail"]),
                Paragraph(f"<b>{val}</b>", styles["Detail"]),
            ]
            for (en, fr, val) in spec.totals
        ]
        totals_tbl = Table(totals_data, colWidths=[5 * inch, 2 * inch])
        totals_tbl.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEABOVE", (0, -1), (-1, -1), 1, PRIMARY_COLOR),
            ("BACKGROUND", (0, -1), (-1, -1), LIGHT_GRAY),
            ("FONTSIZE", (0, -1), (-1, -1), 12),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        elems.append(Spacer(1, 0.12 * inch))
        elems.append(totals_tbl)

    # ── Legal footer (always includes GST/QST + issuer)
    elems.append(Spacer(1, 0.2 * inch))
    legal = Paragraph(
        f"{PLATFORM_NAME} — GST {PLATFORM_GST} · QST {PLATFORM_QST}",
        styles["Tiny"],
    )
    elems.append(legal)
    if spec.disclaimer_en or spec.disclaimer_fr:
        elems.append(Spacer(1, 0.05 * inch))
        elems.append(Paragraph(
            L(spec, spec.disclaimer_en, spec.disclaimer_fr),
            styles["Disclaimer"],
        ))
    elems.append(Spacer(1, 0.05 * inch))
    elems.append(Paragraph(
        L(spec, spec.footer_en, spec.footer_fr), styles["Tiny"],
    ))

    doc.build(elems)
    return buf.getvalue()


def _column_widths_for(n: int) -> List[float]:
    """Sensible column widths for a full-width (7in) line-item table."""
    if n == 2:
        return [4.5 * inch, 2.5 * inch]
    if n == 3:
        return [3.4 * inch, 2 * inch, 1.6 * inch]
    if n == 4:
        return [2.8 * inch, 1.6 * inch, 1.1 * inch, 1.5 * inch]
    if n == 5:
        return [2.2 * inch, 1.4 * inch, 0.9 * inch, 1.1 * inch, 1.4 * inch]
    # 6+
    return [7 * inch / n] * n


# ═══════════════════════════════════════════════════════════════════
#  Settlement reader — reads a `db.receipts` row and returns the
#  pre-computed dollar amounts. NO math is performed here.
# ═══════════════════════════════════════════════════════════════════

async def load_receipt(db, *, section: str, listing_id: str,
                       user_id: str, receipt_type: str,
                       lot_number: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """Return the settlement receipt row that governs a document.

    receipt_type ∈ {"buyer_receipt", "seller_statement"}
    """
    q: Dict[str, Any] = {
        "type": receipt_type,
        "section": section,
        "listing_id": listing_id,
        "user_id": user_id,
    }
    if lot_number is not None:
        q["lot_number"] = lot_number
    return await db.receipts.find_one(q, {"_id": 0})


async def load_receipts_for_seller(db, *, section: str, listing_id: str,
                                   seller_id: str) -> List[Dict[str, Any]]:
    """Return every seller_statement receipt belonging to `seller_id` for
    a given listing.  Used by the seller statement / commission-invoice
    generators to aggregate line items."""
    cur = db.receipts.find(
        {"type": "seller_statement", "section": section,
         "listing_id": listing_id, "user_id": seller_id},
        {"_id": 0},
    )
    return [r async for r in cur]


async def load_receipts_for_buyer(db, *, section: str, listing_id: str,
                                  user_id: str) -> List[Dict[str, Any]]:
    """Return every buyer_receipt for a (section, listing, buyer) — used
    by the multi-lot storage/vehicle buyer invoice generators to combine
    multiple lot rows into one order-level document."""
    cur = db.receipts.find(
        {"type": "buyer_receipt", "section": section,
         "listing_id": listing_id, "user_id": user_id},
        {"_id": 0},
    )
    return [r async for r in cur]


def sum_field(rows: List[Dict[str, Any]], field: str) -> str:
    """Sum a numeric field verbatim across rows.  This is the ONLY
    aggregation this module performs — and it's a pure sum, not a
    recomputation of fees / taxes / commissions.  Result is returned
    formatted (never as a Decimal to be re-transformed downstream)."""
    total = Decimal("0")
    for r in rows:
        v = r.get(field)
        if v is None or v == "":
            continue
        try:
            total += Decimal(str(v))
        except Exception:  # noqa: BLE001
            continue
    return money(total)


def latest_currency(rows: List[Dict[str, Any]]) -> str:
    for r in reversed(rows):
        c = r.get("currency")
        if c:
            return c
    return "CAD"
