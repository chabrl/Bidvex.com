"""
BidVex — Bilingual PDF Invoice Generator (FR/EN)
Generates professional auction invoices using ReportLab,
uploads to Cloudflare R2 at /invoices/{transaction_id}.pdf.

Includes a Multi-Province Tax Engine supporting:
  - HST provinces (ON, NB, NS, NL, PE)
  - Dual-tax provinces (QC, BC, MB, SK)
  - GST-only territories (AB, YT, NT, NU)
"""

import os
import io
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_LEFT, TA_RIGHT, TA_CENTER

logger = logging.getLogger(__name__)

# ─── Platform Identity ───────────────────────────────────────────────
PLATFORM_NAME = "BidVex Inc."
GST_NUMBER = os.environ.get("PLATFORM_GST_NUMBER", "")
QST_NUMBER = os.environ.get("PLATFORM_QST_NUMBER", "")
BUSINESS_NUMBER = os.environ.get("PLATFORM_BUSINESS_NUMBER", "")


# =====================================================================
# MULTI-PROVINCE TAX ENGINE
# =====================================================================

def _round_currency(amount: Decimal) -> Decimal:
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# Province/Territory codes → tax configuration
# HST provinces use a single combined rate
# Dual-tax provinces show GST + PST/QST separately
# GST-only jurisdictions show GST alone
PROVINCE_TAX_CONFIG: Dict[str, Dict[str, Any]] = {
    # ── HST Provinces ──
    "ON": {"type": "hst", "hst_rate": Decimal("0.13"),   "label_en": "HST",  "label_fr": "TVH"},
    "NB": {"type": "hst", "hst_rate": Decimal("0.15"),   "label_en": "HST",  "label_fr": "TVH"},
    "NS": {"type": "hst", "hst_rate": Decimal("0.15"),   "label_en": "HST",  "label_fr": "TVH"},
    "NL": {"type": "hst", "hst_rate": Decimal("0.15"),   "label_en": "HST",  "label_fr": "TVH"},
    "PE": {"type": "hst", "hst_rate": Decimal("0.15"),   "label_en": "HST",  "label_fr": "TVH"},
    # ── Dual-Tax Provinces ──
    "QC": {
        "type": "dual",
        "gst_rate": Decimal("0.05"),
        "pst_rate": Decimal("0.09975"),
        "pst_label_en": "QST",
        "pst_label_fr": "TVQ",
        "pst_on_gst": False,  # QST is on subtotal only, NOT on GST-inclusive amount
    },
    "BC": {
        "type": "dual",
        "gst_rate": Decimal("0.05"),
        "pst_rate": Decimal("0.07"),
        "pst_label_en": "PST",
        "pst_label_fr": "TVP",
        "pst_on_gst": False,
    },
    "MB": {
        "type": "dual",
        "gst_rate": Decimal("0.05"),
        "pst_rate": Decimal("0.07"),
        "pst_label_en": "RST",
        "pst_label_fr": "TVD",
        "pst_on_gst": False,
    },
    "SK": {
        "type": "dual",
        "gst_rate": Decimal("0.05"),
        "pst_rate": Decimal("0.06"),
        "pst_label_en": "PST",
        "pst_label_fr": "TVP",
        "pst_on_gst": False,
    },
    # ── GST-Only Jurisdictions ──
    "AB": {"type": "gst_only", "gst_rate": Decimal("0.05")},
    "YT": {"type": "gst_only", "gst_rate": Decimal("0.05")},
    "NT": {"type": "gst_only", "gst_rate": Decimal("0.05")},
    "NU": {"type": "gst_only", "gst_rate": Decimal("0.05")},
}

# Default province when none is provided
DEFAULT_PROVINCE = "QC"


@dataclass
class ProvinceTaxResult:
    """Result of a multi-province tax calculation."""
    province: str
    tax_type: str          # "hst" | "dual" | "gst_only"
    subtotal: float
    tax_gst: float         # Federal GST amount (0 for HST provinces)
    tax_pst_qst: float     # Provincial PST/QST/RST amount (0 for HST/GST-only)
    tax_hst: float          # HST amount (0 for non-HST provinces)
    total_tax: float
    total_with_tax: float
    line_items: List[Dict[str, Any]]   # [{label, rate_display, amount}]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def calculate_province_tax(
    subtotal: float,
    buyer_province: str = DEFAULT_PROVINCE,
    lang: str = "en",
) -> ProvinceTaxResult:
    """
    Calculate tax for a given subtotal based on buyer's province/territory.

    Returns a ProvinceTaxResult with separate gst, pst_qst, hst amounts
    and pre-built line_items for invoice rendering.
    """
    province = buyer_province.upper().strip()
    config = PROVINCE_TAX_CONFIG.get(province)
    if not config:
        logger.warning(f"Unknown province '{province}', defaulting to {DEFAULT_PROVINCE}")
        province = DEFAULT_PROVINCE
        config = PROVINCE_TAX_CONFIG[province]

    amt = Decimal(str(subtotal))
    tax_type = config["type"]
    tax_gst = Decimal("0")
    tax_pst_qst = Decimal("0")
    tax_hst = Decimal("0")
    line_items: List[Dict[str, Any]] = []

    if tax_type == "hst":
        hst_rate = config["hst_rate"]
        tax_hst = _round_currency(amt * hst_rate)
        label = config["label_en"] if lang == "en" else config["label_fr"]
        rate_pct = f"{float(hst_rate * 100):.0f}%"
        line_items.append({
            "label": f"{label} ({rate_pct})",
            "rate_display": rate_pct,
            "amount": float(tax_hst),
        })

    elif tax_type == "dual":
        gst_rate = config["gst_rate"]
        pst_rate = config["pst_rate"]
        tax_gst = _round_currency(amt * gst_rate)
        # Important for QC: QST is on subtotal, NOT on subtotal+GST
        tax_pst_qst = _round_currency(amt * pst_rate)

        gst_pct = f"{float(gst_rate * 100):.0f}%"
        pst_label = config["pst_label_en"] if lang == "en" else config["pst_label_fr"]
        pst_pct = f"{float(pst_rate * 100):.3f}%" if province == "QC" else f"{float(pst_rate * 100):.0f}%"

        line_items.append({
            "label": f"GST ({gst_pct})" if lang == "en" else f"TPS ({gst_pct})",
            "rate_display": gst_pct,
            "amount": float(tax_gst),
        })
        line_items.append({
            "label": f"{pst_label} ({pst_pct})",
            "rate_display": pst_pct,
            "amount": float(tax_pst_qst),
        })

    else:  # gst_only
        gst_rate = config["gst_rate"]
        tax_gst = _round_currency(amt * gst_rate)
        gst_pct = f"{float(gst_rate * 100):.0f}%"
        line_items.append({
            "label": f"GST ({gst_pct})" if lang == "en" else f"TPS ({gst_pct})",
            "rate_display": gst_pct,
            "amount": float(tax_gst),
        })

    total_tax = tax_gst + tax_pst_qst + tax_hst
    total_with_tax = _round_currency(amt + total_tax)

    return ProvinceTaxResult(
        province=province,
        tax_type=tax_type,
        subtotal=float(_round_currency(amt)),
        tax_gst=float(tax_gst),
        tax_pst_qst=float(tax_pst_qst),
        tax_hst=float(tax_hst),
        total_tax=float(total_tax),
        total_with_tax=float(total_with_tax),
        line_items=line_items,
    )


# =====================================================================
# BILINGUAL LABELS
# =====================================================================

LABELS = {
    "en": {
        "invoice": "INVOICE",
        "invoice_number": "Invoice #",
        "date": "Date",
        "transaction_id": "Transaction ID",
        "bill_to": "Bill To",
        "sold_by": "Sold By",
        "item": "Item",
        "description": "Description",
        "qty": "Qty",
        "unit_price": "Unit Price",
        "amount": "Amount",
        "subtotal": "Subtotal",
        "buyer_premium": "Buyer's Premium",
        "total": "Total Due",
        "currency": "Currency",
        "province": "Province",
        "gst_number": "GST/TPS #",
        "qst_number": "QST/TVQ #",
        "business_number": "Business #",
        "thank_you": "Thank you for your purchase on BidVex.",
        "legal_notice": "This document serves as an official tax invoice.",
        "payment_terms": "Payment Terms: Due upon receipt",
    },
    "fr": {
        "invoice": "FACTURE",
        "invoice_number": "Facture #",
        "date": "Date",
        "transaction_id": "ID Transaction",
        "bill_to": "Facturer a",
        "sold_by": "Vendu par",
        "item": "Article",
        "description": "Description",
        "qty": "Qte",
        "unit_price": "Prix unitaire",
        "amount": "Montant",
        "subtotal": "Sous-total",
        "buyer_premium": "Prime acheteur",
        "total": "Total a payer",
        "currency": "Devise",
        "province": "Province",
        "gst_number": "# TPS",
        "qst_number": "# TVQ",
        "business_number": "# Entreprise",
        "thank_you": "Merci pour votre achat sur BidVex.",
        "legal_notice": "Ce document constitue une facture fiscale officielle.",
        "payment_terms": "Conditions de paiement : Payable a reception",
    },
}


def _fmt_currency(amount: float, currency: str = "CAD") -> str:
    symbol = "$" if currency in ("CAD", "USD") else currency
    return f"{symbol}{amount:,.2f}"


# =====================================================================
# PDF GENERATION
# =====================================================================

def generate_invoice_pdf(
    invoice_data: Dict[str, Any],
    buyer: Dict[str, Any],
    seller: Dict[str, Any],
    lang: str = "en",
    buyer_province: str = DEFAULT_PROVINCE,
) -> bytes:
    """
    Generate a bilingual PDF invoice with province-aware tax lines.
    Returns raw PDF bytes ready for R2 upload.
    """
    L = LABELS.get(lang, LABELS["en"])
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=letter,
        topMargin=0.6 * inch, bottomMargin=0.8 * inch,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle("InvTitle", parent=styles["Title"], fontSize=22, textColor=colors.HexColor("#1e293b"), spaceAfter=4))
    styles.add(ParagraphStyle("InvLabel", parent=styles["Normal"], fontSize=8, textColor=colors.HexColor("#64748b")))
    styles.add(ParagraphStyle("InvValue", parent=styles["Normal"], fontSize=10, textColor=colors.HexColor("#1e293b"), fontName="Helvetica-Bold"))
    styles.add(ParagraphStyle("InvSmall", parent=styles["Normal"], fontSize=7.5, textColor=colors.HexColor("#94a3b8")))
    styles.add(ParagraphStyle("InvRight", parent=styles["Normal"], fontSize=10, alignment=TA_RIGHT))
    styles.add(ParagraphStyle("InvCenter", parent=styles["Normal"], fontSize=8, alignment=TA_CENTER, textColor=colors.HexColor("#64748b")))

    elements = []
    currency = invoice_data.get("currency", "CAD")
    inv_number = invoice_data.get("invoice_number", invoice_data.get("id", "N/A"))
    inv_date = invoice_data.get("created_at", datetime.now(timezone.utc).isoformat())
    if isinstance(inv_date, str):
        try:
            inv_date = datetime.fromisoformat(inv_date).strftime("%Y-%m-%d")
        except Exception:
            inv_date = str(inv_date)[:10]

    # ── Header ──
    header_data = [
        [Paragraph(PLATFORM_NAME, styles["InvTitle"]), ""],
        [
            Paragraph(f"{L['gst_number']}: {GST_NUMBER}", styles["InvSmall"]),
            Paragraph(
                L["invoice"],
                ParagraphStyle("BigInv", fontSize=28, textColor=colors.HexColor("#dc2626"), alignment=TA_RIGHT, fontName="Helvetica-Bold"),
            ),
        ],
        [Paragraph(f"{L['qst_number']}: {QST_NUMBER}", styles["InvSmall"]), ""],
    ]
    header_table = Table(header_data, colWidths=[3.5 * inch, 3.5 * inch])
    header_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("SPAN", (1, 1), (1, 2)),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 12))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#e2e8f0")))
    elements.append(Spacer(1, 12))

    # ── Invoice Meta ──
    meta_data = [
        [
            Paragraph(L["invoice_number"], styles["InvLabel"]),
            Paragraph(str(inv_number), styles["InvValue"]),
            Paragraph(L["date"], styles["InvLabel"]),
            Paragraph(str(inv_date), styles["InvValue"]),
        ],
        [
            Paragraph(L["transaction_id"], styles["InvLabel"]),
            Paragraph(str(invoice_data.get("transaction_id", invoice_data.get("auction_id", ""))), styles["InvValue"]),
            Paragraph(L["province"], styles["InvLabel"]),
            Paragraph(buyer_province.upper(), styles["InvValue"]),
        ],
    ]
    meta_table = Table(meta_data, colWidths=[1.2 * inch, 2.3 * inch, 1.2 * inch, 2.3 * inch])
    meta_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 16))

    # ── Bill To / Sold By ──
    buyer_name = buyer.get("name", buyer.get("email", "Buyer"))
    buyer_email = buyer.get("email", "")
    seller_name = seller.get("partner_company_name") or seller.get("name", seller.get("email", "Seller"))

    party_data = [
        [Paragraph(L["bill_to"], styles["InvLabel"]), Paragraph(L["sold_by"], styles["InvLabel"])],
        [Paragraph(buyer_name, styles["InvValue"]), Paragraph(seller_name, styles["InvValue"])],
        [Paragraph(buyer_email, styles["InvSmall"]), Paragraph(seller.get("email", ""), styles["InvSmall"])],
    ]
    party_table = Table(party_data, colWidths=[3.5 * inch, 3.5 * inch])
    party_table.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
        ("TOPPADDING", (0, 0), (-1, 0), 6),
    ]))
    elements.append(party_table)
    elements.append(Spacer(1, 20))

    # ── Line Items ──
    items = invoice_data.get("items", [])
    table_header = [L["item"], L["description"], L["qty"], L["unit_price"], L["amount"]]
    table_data = [table_header]
    for item in items:
        table_data.append([
            Paragraph(str(item.get("title", item.get("name", "Auction Item"))), styles["Normal"]),
            Paragraph(str(item.get("description", ""))[:80], styles["InvSmall"]),
            str(item.get("quantity", 1)),
            _fmt_currency(item.get("unit_price", item.get("hammer_price", 0)), currency),
            _fmt_currency(item.get("amount", item.get("hammer_price", 0)), currency),
        ])

    if not items:
        table_data.append([
            Paragraph(invoice_data.get("item_title", "Auction Item"), styles["Normal"]),
            "", "1",
            _fmt_currency(invoice_data.get("subtotal", 0), currency),
            _fmt_currency(invoice_data.get("subtotal", 0), currency),
        ])

    items_table = Table(table_data, colWidths=[1.8 * inch, 2.2 * inch, 0.5 * inch, 1.2 * inch, 1.3 * inch])
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 12))

    # ── Totals (with province-aware tax lines) ──
    subtotal = invoice_data.get("subtotal", 0)
    buyer_premium = invoice_data.get("buyer_premium", 0)

    # Calculate province-specific tax
    taxable_amount = subtotal + buyer_premium
    tax_result = calculate_province_tax(taxable_amount, buyer_province, lang)

    totals_data = [
        ["", L["subtotal"], _fmt_currency(subtotal, currency)],
    ]
    if buyer_premium > 0:
        totals_data.append(["", L["buyer_premium"], _fmt_currency(buyer_premium, currency)])

    # Add province-specific tax line items
    for tax_line in tax_result.line_items:
        totals_data.append(["", tax_line["label"], _fmt_currency(tax_line["amount"], currency)])

    total = taxable_amount + tax_result.total_tax
    totals_data.append(["", L["total"], _fmt_currency(total, currency)])

    totals_table = Table(totals_data, colWidths=[3.8 * inch, 1.7 * inch, 1.5 * inch])
    totals_table.setStyle(TableStyle([
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (1, -1), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (1, -1), (-1, -1), 11),
        ("TEXTCOLOR", (2, -1), (2, -1), colors.HexColor("#dc2626")),
        ("LINEABOVE", (1, -1), (-1, -1), 1.5, colors.HexColor("#1e293b")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 30))

    # ── Footer ──
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#e2e8f0")))
    elements.append(Spacer(1, 8))
    elements.append(Paragraph(L["thank_you"], styles["InvCenter"]))
    elements.append(Paragraph(L["legal_notice"], styles["InvCenter"]))
    elements.append(Paragraph(L["payment_terms"], styles["InvCenter"]))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(
        f"{PLATFORM_NAME} | {L['business_number']}: {BUSINESS_NUMBER}",
        styles["InvCenter"],
    ))

    doc.build(elements)
    return buf.getvalue()


# =====================================================================
# GENERATE + STORE (R2) + UPDATE DB
# =====================================================================

async def generate_and_store_invoice(
    db,
    transaction_id: str,
    invoice_data: Dict[str, Any],
    buyer: Dict[str, Any],
    seller: Dict[str, Any],
    lang: str = "en",
    buyer_province: str = DEFAULT_PROVINCE,
) -> Optional[str]:
    """
    Generate a PDF invoice, upload to R2, and update the transaction record
    with invoice_url and per-tax-type amounts (tax_gst, tax_pst_qst, tax_hst).
    Returns the R2 storage path or None on failure.
    """
    try:
        pdf_bytes = generate_invoice_pdf(invoice_data, buyer, seller, lang, buyer_province)

        from services.cloud_storage import store_invoice_pdf
        storage_path = await store_invoice_pdf(transaction_id, pdf_bytes, subfolder="transactions")

        # Province tax for the DB record
        subtotal = invoice_data.get("subtotal", 0)
        buyer_premium = invoice_data.get("buyer_premium", 0)
        tax_result = calculate_province_tax(subtotal + buyer_premium, buyer_province, lang)

        await db.payment_transactions.update_one(
            {"id": transaction_id},
            {"$set": {
                "invoice_url": storage_path,
                "tax_gst": tax_result.tax_gst,
                "tax_pst_qst": tax_result.tax_pst_qst,
                "tax_hst": tax_result.tax_hst,
                "buyer_province": buyer_province.upper(),
            }},
        )

        if invoice_data.get("id"):
            await db.invoices.update_one(
                {"id": invoice_data["id"]},
                {"$set": {"pdf_url": storage_path}},
            )

        logger.info(f"Invoice generated and stored for transaction {transaction_id}: {storage_path}")
        return storage_path

    except Exception as e:
        logger.error(f"Invoice generation failed for {transaction_id}: {e}")
        return None
