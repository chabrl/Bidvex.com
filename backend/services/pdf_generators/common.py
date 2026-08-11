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

    # iter476 — Complete BUYER + SELLER identification (both parties on
    # every document, side-by-side). All fields are read verbatim from
    # `db.users`. Omit any field to render blank rather than fabricate.
    buyer_name:     str = ""
    buyer_email:    str = ""
    buyer_phone:    str = ""
    buyer_address:  str = ""
    buyer_gst:      str = ""
    buyer_qst:      str = ""
    buyer_tax_number: str = ""

    seller_name:    str = ""
    seller_email:   str = ""
    seller_phone:   str = ""
    seller_address: str = ""
    seller_gst:     str = ""
    seller_qst:     str = ""
    seller_tax_number: str = ""
    # bytes of the seller's logo (from S3) — rendered ONLY on
    # buyer-facing documents
    seller_logo_bytes: Optional[bytes] = None
    show_seller_logo: bool = False

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

    # iter476 — itemized breakdown rows sourced verbatim from the
    # settlement record.  Structure: list of (label_en, label_fr,
    # amount_str_or_blank, is_bold).  Blank amounts render as "—" so
    # historical (pre-iter476) receipts render truthfully.
    itemized_rows: List[Tuple[str, str, str, bool]] = field(default_factory=list)

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
        name="DocTitle", fontSize=20, leading=24, textColor=PRIMARY_COLOR,
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
    from services.pdf_generators.branding import (
        bidvex_letterhead_table, party_block, two_party_row,
    )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.45 * inch, bottomMargin=0.45 * inch,
    )
    styles = _make_styles()
    elems: List[Any] = []

    # ── iter476: BidVex letterhead + document title row ──
    elems.append(bidvex_letterhead_table(styles))
    title = spec.title_fr if spec.lang == "fr" else spec.title_en
    title_row = Table([[
        Paragraph(f"<b>{title}</b>", styles["DocTitle"]),
        Paragraph(
            f"<font size='9' color='gray'>{L(spec, 'No.', 'N°')}</font> "
            f"<b>{spec.document_id}</b><br/>"
            f"<font size='9' color='gray'>{L(spec, 'Issued', 'Émis')}: "
            f"{dt_str(spec.document_date)}</font>",
            styles["Detail"],
        ),
    ]], colWidths=[4.2 * inch, 2.8 * inch])
    title_row.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("LINEBELOW", (0, 0), (-1, -1), 1.2, PRIMARY_COLOR),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
    ]))
    elems.append(title_row)
    elems.append(Spacer(1, 0.12 * inch))

    # ── iter476: BUYER + SELLER side-by-side (both parties on ALL docs) ──
    buyer_blk = party_block(
        styles,
        title_en="BUYER", title_fr="ACHETEUR", lang=spec.lang,
        name=spec.buyer_name, address=spec.buyer_address,
        phone=spec.buyer_phone, email=spec.buyer_email,
        gst=spec.buyer_gst, qst=spec.buyer_qst,
        tax_number=spec.buyer_tax_number,
    )
    seller_blk = party_block(
        styles,
        title_en="SELLER / DEALER", title_fr="VENDEUR / CONCESSIONNAIRE",
        lang=spec.lang,
        name=spec.seller_name, address=spec.seller_address,
        phone=spec.seller_phone, email=spec.seller_email,
        gst=spec.seller_gst, qst=spec.seller_qst,
        tax_number=spec.seller_tax_number,
        logo_bytes=spec.seller_logo_bytes if spec.show_seller_logo else None,
    )
    elems.append(two_party_row(buyer_blk, seller_blk))
    elems.append(Spacer(1, 0.12 * inch))

    # ── Meta rows
    if spec.meta_rows:
        elems.append(Paragraph(
            L(spec, "DOCUMENT DETAILS", "DÉTAILS DU DOCUMENT"),
            styles["SectionTitle"]))
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
        # iter477 QA fix — wrap DATA cells in Paragraphs so long lot titles
        # word-wrap inside their column instead of overflowing into the
        # adjacent Hammer / Total column. Headers stay as plain strings so
        # the bold/white styling still applies via TableStyle.
        cell_style = ParagraphStyle(
            name="LineCell", fontSize=9, leading=11,
            textColor=SECONDARY_COLOR,
        )
        cell_style_right = ParagraphStyle(
            name="LineCellRight", fontSize=9, leading=11,
            textColor=SECONDARY_COLOR, alignment=TA_RIGHT,
        )
        wrapped_rows = []
        for row in spec.line_rows:
            r = list(row)
            for i, val in enumerate(r):
                if isinstance(val, str):
                    # Right-align the last column (typically "Total" or
                    # "Net payout") to match the header alignment.
                    style = cell_style_right if i == len(r) - 1 else cell_style
                    r[i] = Paragraph(val.replace("&", "&amp;"), style)
            wrapped_rows.append(r)
        rows = [headers] + wrapped_rows
        cw = _column_widths_for(len(headers))
        line_tbl = Table(rows, colWidths=cw, repeatRows=1)
        line_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PRIMARY_COLOR),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("ALIGN", (-1, 0), (-1, 0), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("GRID", (0, 0), (-1, -1), 0.4, BORDER_COLOR),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
        ]))
        elems.append(Spacer(1, 0.12 * inch))
        elems.append(line_tbl)

    # ── iter476: itemized financial breakdown (transparent auction
    # settlement layout).  Every row is populated ONLY from the persisted
    # settlement record — blank fields render as "—" (never fabricated).
    if spec.itemized_rows:
        elems.append(Spacer(1, 0.15 * inch))
        elems.append(Paragraph(
            L(spec, "ITEMIZED SETTLEMENT BREAKDOWN",
              "DÉTAIL DU RÈGLEMENT"),
            styles["SectionTitle"]))
        it_data = []
        for (en, fr, val, is_bold) in spec.itemized_rows:
            label = L(spec, en, fr)
            v = val or "—"
            if is_bold:
                it_data.append([
                    Paragraph(f"<b>{label}</b>", styles["Detail"]),
                    Paragraph(f"<b>{v}</b>", styles["Detail"]),
                ])
            else:
                it_data.append([
                    Paragraph(label, styles["Detail"]),
                    Paragraph(v, styles["Detail"]),
                ])
        it_tbl = Table(it_data, colWidths=[4.6 * inch, 2.4 * inch])
        # Style: subtle GRID, TOTAL rows highlighted
        s = [
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#e5e7eb")),
            ("TOPPADDING", (0, 0), (-1, -1), 3),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]
        for i, (_, _, _, is_bold) in enumerate(spec.itemized_rows):
            if is_bold:
                s.append(("BACKGROUND", (0, i), (-1, i), LIGHT_GRAY))
                s.append(("LINEABOVE", (0, i), (-1, i), 1, PRIMARY_COLOR))
        it_tbl.setStyle(TableStyle(s))
        elems.append(it_tbl)

    # ── Totals table (only rendered when no itemized breakdown is used;
    # kept for backward compatibility with the seller-receipt generator).
    if spec.totals and not spec.itemized_rows:
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
    elems.append(Spacer(1, 0.18 * inch))
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


# ═══════════════════════════════════════════════════════════════════
#  iter476 — Party details + itemized-breakdown helpers.
# ═══════════════════════════════════════════════════════════════════

def party_from_user(user: Dict[str, Any]) -> Dict[str, str]:
    """Extract the canonical BUYER/SELLER identification block from a
    `db.users` row.  Handles both legacy and iter476-extended profiles."""
    if not user:
        return {"name": "", "email": "", "phone": "", "address": "",
                "gst": "", "qst": "", "tax_number": ""}
    name = (
        user.get("company_name") or user.get("business_name")
        or user.get("name") or user.get("full_name") or user.get("email") or ""
    )
    return {
        "name":       name,
        "email":      user.get("email") or "",
        "phone":      user.get("phone") or "",
        "address":    user.get("business_address")
                      or user.get("address") or "",
        "gst":        user.get("gst_number") or "",
        "qst":        user.get("qst_number") or "",
        "tax_number": user.get("tax_number") or "",
    }


def build_itemized_rows_for_buyer(
    rows: List[Dict[str, Any]], *, currency: str, lang: str = "en",
) -> List[Tuple[str, str, str, bool]]:
    """Assemble the itemized-breakdown rows for a BUYER document.

    Sums are pure — each column is summed verbatim across `rows`. When a
    column is entirely missing on the source receipts (historical
    pre-iter476 rows), the value is rendered as "—" so the reader can
    see the field wasn't captured.  We NEVER split an aggregate to
    invent an itemized value.
    """
    def _sum_or_blank(field: str) -> str:
        total = Decimal("0")
        any_populated = False
        for r in rows:
            v = r.get(field)
            if v is None or v == "":
                continue
            try:
                total += Decimal(str(v))
                any_populated = True
            except Exception:  # noqa: BLE001
                continue
        if not any_populated:
            return "—"
        return money(total, currency=currency)

    # buyer stripe fee only shows if any row marks it as buyer-charged
    stripe_field_populated = any(
        r.get("stripe_fee") is not None and
        str(r.get("stripe_fee_charged_to") or "").lower() == "buyer"
        for r in rows
    )

    def _stripe_sum() -> str:
        if not stripe_field_populated:
            return "—"
        total = Decimal("0")
        for r in rows:
            if str(r.get("stripe_fee_charged_to") or "").lower() == "buyer":
                v = r.get("stripe_fee")
                if v is not None:
                    total += Decimal(str(v))
        return money(total, currency=currency)

    out: List[Tuple[str, str, str, bool]] = [
        ("Hammer Price Subtotal", "Sous-total marteau",
         sum_field(rows, "hammer_price"), False),
        ("Hammer GST (5%)", "TPS marteau (5 %)",     _sum_or_blank("hammer_gst"), False),
        ("Hammer QST (9.975%)", "TVQ marteau (9,975 %)", _sum_or_blank("hammer_qst"), False),
        ("Buyer's Premium", "Prime d'acheteur",       _sum_or_blank("buyer_premium"), False),
        ("Buyer's Premium GST (5%)", "TPS sur prime (5 %)",     _sum_or_blank("buyer_premium_gst"), False),
        ("Buyer's Premium QST (9.975%)", "TVQ sur prime (9,975 %)", _sum_or_blank("buyer_premium_qst"), False),
        ("BidVex Service Fee", "Frais de service BidVex", _sum_or_blank("service_fee"), False),
        ("Service Fee GST (5%)", "TPS sur frais (5 %)",     _sum_or_blank("service_fee_gst"), False),
        ("Service Fee QST (9.975%)", "TVQ sur frais (9,975 %)", _sum_or_blank("service_fee_qst"), False),
        ("Stripe Card Processing Fee", "Frais de traitement Stripe", _stripe_sum(), False),
        ("GRAND TOTAL PAID", "TOTAL PAYÉ",
         sum_field(rows, "total_charged"), True),
    ]
    return out


def build_itemized_rows_for_seller(
    rows: List[Dict[str, Any]], *, currency: str, lang: str = "en",
) -> List[Tuple[str, str, str, bool]]:
    """Assemble the itemized-breakdown rows for a SELLER document
    (statement / commission invoice)."""
    def _sum_or_blank(field: str) -> str:
        total = Decimal("0")
        any_populated = False
        for r in rows:
            v = r.get(field)
            if v is None or v == "":
                continue
            try:
                total += Decimal(str(v))
                any_populated = True
            except Exception:  # noqa: BLE001
                continue
        if not any_populated:
            return "—"
        return money(total, currency=currency)

    stripe_seller_populated = any(
        r.get("stripe_fee") is not None and
        str(r.get("stripe_fee_charged_to") or "").lower() == "seller"
        for r in rows
    )

    def _stripe_seller_sum() -> str:
        if not stripe_seller_populated:
            return "—"
        total = Decimal("0")
        for r in rows:
            if str(r.get("stripe_fee_charged_to") or "").lower() == "seller":
                v = r.get("stripe_fee")
                if v is not None:
                    total += Decimal(str(v))
        return money(total, currency=currency)

    # ── iter480 Phase 3 canonical BidVex Platform Fee split ──
    # If any receipt in the group has a non-zero bidvex_platform_fee_amount
    # (currently only Partner sales), render "BidVex Platform Fee" rows
    # in place of the ambiguously-named "Seller Commission" rows so the
    # persisted economic concept is displayed correctly.  Historical
    # receipts predate this field — they fall back to the legacy
    # "Seller Commission" label without any numeric change.
    bidvex_platform_fee_present = any(
        (r.get("bidvex_platform_fee_amount") or 0) not in (0, 0.0, None, "")
        for r in rows
    )

    if bidvex_platform_fee_present:
        commission_rows = [
            ("BidVex Platform Fee",   "Frais de plateforme BidVex",
             _sum_or_blank("bidvex_platform_fee_amount"), False),
            ("Platform Fee GST (5%)", "TPS sur frais BidVex (5 %)",
             _sum_or_blank("bidvex_platform_fee_gst"),    False),
            ("Platform Fee QST (9.975%)", "TVQ sur frais BidVex (9,975 %)",
             _sum_or_blank("bidvex_platform_fee_qst"),    False),
        ]
    else:
        commission_rows = [
            ("Seller Commission",   "Commission vendeur",
             _sum_or_blank("seller_commission"), False),
            ("Commission GST (5%)", "TPS sur commission (5 %)",
             _sum_or_blank("seller_commission_gst"), False),
            ("Commission QST (9.975%)", "TVQ sur commission (9,975 %)",
             _sum_or_blank("seller_commission_qst"), False),
        ]

    return [
        ("Hammer Total (Gross)", "Marteau brut",
         sum_field(rows, "hammer_price"), False),
        ("Hammer GST Collected", "TPS marteau collectée", _sum_or_blank("hammer_gst"), False),
        ("Hammer QST Collected", "TVQ marteau collectée", _sum_or_blank("hammer_qst"), False),
        *commission_rows,
        ("Other Deductions",    "Autres retenues",        _sum_or_blank("other_deductions"), False),
        ("Stripe Card Processing Fee", "Frais de traitement Stripe", _stripe_seller_sum(), False),
        ("NET PAYOUT",          "PAIEMENT NET",
         sum_field(rows, "net_payout"), True),
    ]
