"""iter476 — Shared PDF branding module.

Central source for the BidVex letterhead + optional seller/partner
logo. Reused by every generator in ``services/pdf_generators/`` so the
logo-loading code is never duplicated.
"""
from __future__ import annotations

import io
import logging
from pathlib import Path
from typing import Any, Optional

from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, Spacer, Table, TableStyle

from services.pdf_invoice import (
    PLATFORM_NAME, PLATFORM_ADDRESS,
    PLATFORM_GST, PLATFORM_QST,
    PLATFORM_PHONE, PLATFORM_EMAIL, PLATFORM_WEBSITE,
    PRIMARY_COLOR, SECONDARY_COLOR, BORDER_COLOR,
)

logger = logging.getLogger(__name__)

_BIDVEX_LOGO_PATH = Path(__file__).parent / "assets" / "bidvex_logo.png"
_BIDVEX_LOGO_MAX_WIDTH  = 1.6 * inch
_BIDVEX_LOGO_MAX_HEIGHT = 0.55 * inch

_SELLER_LOGO_MAX_WIDTH  = 1.4 * inch
_SELLER_LOGO_MAX_HEIGHT = 0.5 * inch


def _sized_image(source, max_w: float, max_h: float) -> Optional[Image]:
    """Return a ReportLab Image constrained to a bounding box while
    preserving aspect ratio. `source` can be a file path or bytes."""
    try:
        if isinstance(source, (bytes, bytearray)):
            source = io.BytesIO(source)
        img = Image(source)
        # scale
        orig_w, orig_h = img.imageWidth, img.imageHeight
        if not orig_w or not orig_h:
            return None
        ratio = min(max_w / orig_w, max_h / orig_h, 1.0)
        img.drawWidth  = orig_w * ratio
        img.drawHeight = orig_h * ratio
        return img
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[branding] failed to load image: {e}")
        return None


def bidvex_logo_flowable() -> Any:
    """Return a ReportLab flowable for the BidVex logo, or a text
    fallback if the logo file is unavailable."""
    if _BIDVEX_LOGO_PATH.is_file():
        img = _sized_image(str(_BIDVEX_LOGO_PATH), _BIDVEX_LOGO_MAX_WIDTH, _BIDVEX_LOGO_MAX_HEIGHT)
        if img is not None:
            return img
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    return Paragraph(
        f"<b><font size='14' color='#{PRIMARY_COLOR.hexval()[2:]}'>{PLATFORM_NAME}</font></b>",
        ParagraphStyle("BidVexFallback", alignment=TA_LEFT),
    )


def seller_logo_flowable(logo_bytes: Optional[bytes]) -> Optional[Any]:
    """Return a ReportLab flowable for a seller/partner/dealer logo
    when bytes are provided; otherwise ``None`` (caller should skip)."""
    if not logo_bytes:
        return None
    return _sized_image(logo_bytes, _SELLER_LOGO_MAX_WIDTH, _SELLER_LOGO_MAX_HEIGHT)


async def resolve_seller_logo_bytes(db, seller_id: str) -> Optional[bytes]:
    """Fetch the seller's stored logo bytes from S3 for embedding. Falls
    back gracefully to ``None`` if the seller has no logo or the fetch
    fails."""
    if not seller_id:
        return None
    try:
        user = await db.users.find_one(
            {"id": seller_id},
            {"_id": 0, "logo_storage_path": 1, "logo_url": 1},
        )
        if not user:
            return None
        path = user.get("logo_storage_path")
        if not path:
            return None
        from services.cloud_storage import retrieve_business_logo
        return await retrieve_business_logo(path)
    except Exception as e:  # noqa: BLE001
        logger.debug(f"[branding] seller logo fetch failed: {e}")
        return None


def bidvex_letterhead_table(styles) -> Table:
    """Return a table holding the BidVex letterhead:
        [ LOGO ] [ Address / phone / email / website / GST / QST ]
    Used at the top of every iter476-standard document."""
    logo = bidvex_logo_flowable()
    info = Paragraph(
        f"<b>{PLATFORM_NAME}</b><br/>"
        f"{PLATFORM_ADDRESS}<br/>"
        f"{PLATFORM_PHONE} · {PLATFORM_EMAIL}<br/>"
        f"{PLATFORM_WEBSITE}<br/>"
        f"<font size='8' color='gray'>GST {PLATFORM_GST} · QST {PLATFORM_QST}</font>",
        styles["Tiny"],
    )
    tbl = Table([[logo, info]], colWidths=[2.0 * inch, 5.0 * inch])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (0, 0), (0, 0), "LEFT"),
        ("ALIGN", (1, 0), (1, 0), "LEFT"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl


def party_block(
    styles, *,
    title_en: str, title_fr: str, lang: str,
    name: str, address: str = "", phone: str = "", email: str = "",
    gst: str = "", qst: str = "", tax_number: str = "",
    logo_bytes: Optional[bytes] = None,
) -> Table:
    """Return a small stacked block: title + logo (optional) + name +
    address + phone/email + tax numbers.  Both buyer and seller blocks
    on every iter476 PDF use this helper — identical layout guaranteed."""
    heading = title_fr if lang == "fr" else title_en

    body_lines = []
    if name:
        body_lines.append(f"<b>{name}</b>")
    if address:
        body_lines.append(address.replace("\n", "<br/>"))
    contact_parts = [p for p in (phone, email) if p]
    if contact_parts:
        body_lines.append(" · ".join(contact_parts))
    tax_parts = []
    if gst: tax_parts.append(f"GST {gst}")
    if qst: tax_parts.append(f"QST {qst}")
    if not tax_parts and tax_number:
        tax_parts.append(("N° fiscal " if lang == "fr" else "Tax # ") + tax_number)
    if tax_parts:
        body_lines.append(f"<font size='8' color='gray'>{' · '.join(tax_parts)}</font>")

    para = Paragraph("<br/>".join(body_lines) or "—", styles["Detail"])

    # If a logo was provided (seller/partner block on buyer docs), stack
    # logo above the party info.
    if logo_bytes:
        logo = seller_logo_flowable(logo_bytes)
        if logo is not None:
            inner = Table([[logo], [para]], colWidths=[3.2 * inch])
            inner.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (0, 0), 4),
            ]))
            para = inner  # type: ignore[assignment]

    header = Paragraph(
        f"<b><font size='9' color='gray'>{heading}</font></b>",
        styles["Detail"],
    )
    block = Table([[header], [para]], colWidths=[3.4 * inch])
    block.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, 1), (-1, 1), 0.5, BORDER_COLOR),
        ("TOPPADDING", (0, 1), (-1, 1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    return block


def two_party_row(buyer_block: Table, seller_block: Table) -> Table:
    """Side-by-side BUYER | SELLER block, standardised across every PDF."""
    tbl = Table([[buyer_block, seller_block]], colWidths=[3.4 * inch, 3.4 * inch])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ]))
    return tbl
