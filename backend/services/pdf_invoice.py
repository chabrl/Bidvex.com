"""
BidVex PDF Invoice Generator
Generates professional PDF invoices for vehicle auctions
"""

import os
import io
import uuid
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Dict, Any, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT

logger = logging.getLogger(__name__)

# Platform info
PLATFORM_NAME = os.environ.get("PLATFORM_LEGAL_NAME", "BidVex Inc.")
PLATFORM_ADDRESS = "103-761 Chalifoux Street, Sherbrooke, QC, J1G 0A8"
PLATFORM_GST = os.environ.get("PLATFORM_GST_NUMBER", "706766367RT0001")
PLATFORM_QST = os.environ.get("PLATFORM_QST_NUMBER", "1233530880TQ0001")
PLATFORM_PHONE = "1-800-BIDVEX"
PLATFORM_EMAIL = "billing@bidvex.com"
PLATFORM_WEBSITE = "www.bidvex.com"

# Colors
PRIMARY_COLOR = colors.HexColor("#2563eb")  # Blue
SECONDARY_COLOR = colors.HexColor("#1e293b")  # Slate
ACCENT_COLOR = colors.HexColor("#10b981")  # Emerald
LIGHT_GRAY = colors.HexColor("#f1f5f9")
BORDER_COLOR = colors.HexColor("#e2e8f0")


def _format_currency(amount) -> str:
    """Format amount as currency"""
    return f"${Decimal(str(amount)):,.2f}"


def _format_date(dt) -> str:
    """Format datetime for display"""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
    return dt.strftime("%B %d, %Y")


async def generate_invoice_pdf(db, invoice_id: str, lang: str = "en") -> Optional[bytes]:
    """
    Generate a professional PDF invoice
    
    Returns PDF as bytes for download/email

    Args:
        lang: "en" (default) or "fr" — localizes key labels for Quebec-FR buyers.
    """
    # Localization dictionary (compact — only the labels rendered on the invoice)
    LABELS = {
        "en": {
            "invoice": "INVOICE",
            "bill_to": "BILL TO",
            "vehicle": "VEHICLE",
            "invoice_details": "INVOICE DETAILS",
            "seller_settlement": "SELLER SETTLEMENT STATEMENT",
            "footer_contact": "Questions? Contact service@bidvex.com",
        },
        "fr": {
            "invoice": "FACTURE",
            "bill_to": "FACTURER À",
            "vehicle": "VÉHICULE",
            "invoice_details": "DÉTAILS DE LA FACTURE",
            "seller_settlement": "RELEVÉ DE RÈGLEMENT DU VENDEUR",
            "footer_contact": "Des questions ? Contactez service@bidvex.com",
        },
    }
    L = LABELS.get(lang, LABELS["en"])
    
    # Fetch invoice
    invoice = await db.vehicle_invoices.find_one({"id": invoice_id})
    if not invoice:
        logger.error(f"Invoice {invoice_id} not found")
        return None
    
    # Create PDF buffer
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    # Styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='InvoiceTitle',
        fontSize=24,
        textColor=PRIMARY_COLOR,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    ))
    styles.add(ParagraphStyle(
        name='InvoiceNumber',
        fontSize=12,
        textColor=SECONDARY_COLOR,
        spaceAfter=20
    ))
    styles.add(ParagraphStyle(
        name='SectionTitle',
        fontSize=11,
        textColor=SECONDARY_COLOR,
        fontName='Helvetica-Bold',
        spaceBefore=15,
        spaceAfter=8
    ))
    styles.add(ParagraphStyle(
        name='DetailText',
        fontSize=10,
        textColor=SECONDARY_COLOR,
        leading=14
    ))
    styles.add(ParagraphStyle(
        name='SmallText',
        fontSize=8,
        textColor=colors.gray,
        leading=10
    ))
    
    elements = []
    
    # ===== HEADER =====
    header_data = [
        [
            Paragraph(f"<b>{PLATFORM_NAME}</b>", styles['DetailText']),
            Paragraph(f"<b>{L['invoice']}</b>", styles['InvoiceTitle'])
        ],
        [
            Paragraph(f"{PLATFORM_ADDRESS}<br/>{PLATFORM_PHONE}<br/>{PLATFORM_EMAIL}", styles['SmallText']),
            ""
        ]
    ]
    header_table = Table(header_data, colWidths=[4*inch, 3*inch])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # Invoice meta info
    status_color = ACCENT_COLOR if invoice.get("payment_status") == "paid" else colors.HexColor("#f59e0b")
    status_text = invoice.get("payment_status", "pending").upper()
    
    meta_data = [
        ["Invoice Number:", invoice.get("invoice_number", "N/A"), "Status:", status_text],
        ["Invoice Date:", _format_date(invoice.get("created_at", datetime.now())), "Due Date:", _format_date(invoice.get("due_at", invoice.get("payment_deadline")))],
    ]
    meta_table = Table(meta_data, colWidths=[1.2*inch, 2.3*inch, 0.8*inch, 2*inch])
    meta_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), SECONDARY_COLOR),
        ('TEXTCOLOR', (3, 0), (3, 0), status_color),
        ('FONTNAME', (3, 0), (3, 0), 'Helvetica-Bold'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # ===== BILL TO / VEHICLE INFO =====
    bill_to = f"""
    <b>{invoice.get('buyer_name', 'N/A')}</b><br/>
    {invoice.get('buyer_email', '')}<br/>
    Province: {invoice.get('buyer_province', 'N/A')}
    """
    
    vehicle_info = f"""
    <b>{invoice.get('vehicle_title', 'Vehicle')}</b><br/>
    VIN: {invoice.get('vehicle_vin', 'N/A')}<br/>
    Auction ID: {invoice.get('auction_id', 'N/A')[:8]}...
    """
    
    address_data = [
        [Paragraph(f"<b>{L['bill_to']}</b>", styles['SectionTitle']), Paragraph(f"<b>{L['vehicle']}</b>", styles['SectionTitle'])],
        [Paragraph(bill_to, styles['DetailText']), Paragraph(vehicle_info, styles['DetailText'])]
    ]
    address_table = Table(address_data, colWidths=[3.5*inch, 3.5*inch])
    address_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 1), (-1, 1), LIGHT_GRAY),
        ('BOX', (0, 1), (-1, 1), 1, BORDER_COLOR),
        ('TOPPADDING', (0, 1), (-1, 1), 10),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 10),
        ('LEFTPADDING', (0, 1), (-1, 1), 10),
        ('RIGHTPADDING', (0, 1), (-1, 1), 10),
    ]))
    elements.append(address_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # ===== LINE ITEMS =====
    elements.append(Paragraph(f"<b>{L['invoice_details']}</b>", styles['SectionTitle']))
    
    # Table header
    line_items_data = [
        ["Description", "Rate", "Amount"]
    ]
    
    # Add line items
    for item in invoice.get("line_items", []):
        rate = f"{item.get('rate', 0) * 100:.1f}%" if item.get('rate') else ""
        amount = item.get('amount', 0)
        amount_str = _format_currency(abs(amount))
        if amount < 0:
            amount_str = f"-{amount_str}"
        
        line_items_data.append([
            item.get('description', ''),
            rate,
            amount_str
        ])
    
    line_table = Table(line_items_data, colWidths=[4.5*inch, 1*inch, 1.5*inch])
    line_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
        ('TOPPADDING', (0, 0), (-1, 0), 10),
        
        # Data rows
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TEXTCOLOR', (0, 1), (-1, -1), SECONDARY_COLOR),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        
        # Alternating row colors
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, LIGHT_GRAY]),
        
        # Grid
        ('LINEBELOW', (0, 0), (-1, -1), 0.5, BORDER_COLOR),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
    ]))
    elements.append(line_table)
    elements.append(Spacer(1, 0.2*inch))
    
    # ===== TOTALS =====
    totals_data = [
        ["Subtotal:", _format_currency(invoice.get("subtotal_before_tax", 0))],
        [f"Tax ({invoice.get('tax_type', 'GST')}):", _format_currency(invoice.get("tax_total", 0))],
    ]
    
    if invoice.get("deposit_credited", 0) > 0:
        totals_data.append(["Deposit Credit:", f"-{_format_currency(invoice.get('deposit_credited', 0))}"])
    
    if invoice.get("penalty_amount", 0) > 0:
        totals_data.append(["Late Penalty:", _format_currency(invoice.get("penalty_amount", 0))])
    
    totals_data.append(["TOTAL DUE:", _format_currency(invoice.get("total_amount", 0))])
    
    totals_table = Table(totals_data, colWidths=[5*inch, 2*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('TEXTCOLOR', (0, 0), (-1, -1), SECONDARY_COLOR),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        # Total row styling
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TEXTCOLOR', (1, -1), (1, -1), PRIMARY_COLOR),
        ('LINEABOVE', (0, -1), (-1, -1), 2, PRIMARY_COLOR),
        ('TOPPADDING', (0, -1), (-1, -1), 10),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 0.4*inch))
    
    # ===== SUBSCRIPTION SAVINGS =====
    if invoice.get("subscription_discount", 0) > 0:
        savings_text = f"✨ {invoice.get('subscription_tier', 'Premium').replace('_', ' ').title()} Member Savings: {_format_currency(invoice.get('subscription_discount', 0))}"
        elements.append(Paragraph(savings_text, ParagraphStyle(
            name='Savings',
            fontSize=10,
            textColor=ACCENT_COLOR,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER
        )))
        elements.append(Spacer(1, 0.3*inch))
    
    # ===== PAYMENT INFO =====
    if invoice.get("payment_status") == "paid":
        paid_text = f"✓ PAID on {_format_date(invoice.get('paid_at', datetime.now()))} via {invoice.get('payment_method', 'Card').upper()}"
        elements.append(Paragraph(paid_text, ParagraphStyle(
            name='Paid',
            fontSize=11,
            textColor=ACCENT_COLOR,
            fontName='Helvetica-Bold',
            alignment=TA_CENTER,
            backColor=colors.HexColor("#d1fae5"),
            borderPadding=10
        )))
    else:
        payment_text = f"""
        <b>Payment Due:</b> {_format_date(invoice.get('due_at', invoice.get('payment_deadline')))}<br/><br/>
        <b>Payment Methods:</b> Credit Card, Debit Card, Bank Transfer<br/>
        <b>Pay Online:</b> {PLATFORM_WEBSITE}/vehicle-auctions/invoices/{invoice_id}
        """
        elements.append(Paragraph(payment_text, styles['DetailText']))
    
    elements.append(Spacer(1, 0.4*inch))
    
    # ===== FOOTER =====
    footer_text = f"""
    <b>Tax Registration Numbers</b><br/>
    GST/HST: {PLATFORM_GST} | QST: {PLATFORM_QST}<br/><br/>
    <i>This is a computer-generated invoice. For questions, contact {PLATFORM_EMAIL}</i><br/>
    <i>Thank you for your business!</i>
    """
    elements.append(Paragraph(footer_text, ParagraphStyle(
        name='Footer',
        fontSize=8,
        textColor=colors.gray,
        alignment=TA_CENTER,
        leading=12
    )))
    
    # Build PDF
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    logger.info(f"Generated PDF invoice for {invoice_id}: {len(pdf_bytes)} bytes")
    
    return pdf_bytes


async def generate_settlement_pdf(db, settlement_id: str) -> Optional[bytes]:
    """
    Generate PDF for seller settlement statement
    """
    settlement = await db.vehicle_invoices.find_one({
        "id": settlement_id,
        "invoice_type": "seller_settlement"
    })
    
    if not settlement:
        return None
    
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.5*inch,
        bottomMargin=0.5*inch
    )
    
    styles = getSampleStyleSheet()
    elements = []
    
    # Title
    elements.append(Paragraph(f"<b>{PLATFORM_NAME}</b>", ParagraphStyle(
        name='Title', fontSize=14, textColor=SECONDARY_COLOR
    )))
    elements.append(Paragraph("SELLER SETTLEMENT STATEMENT", ParagraphStyle(
        name='SubTitle', fontSize=20, textColor=PRIMARY_COLOR, fontName='Helvetica-Bold', spaceAfter=20
    )))
    
    # Settlement details
    details = [
        ["Settlement #:", settlement.get("invoice_number", "N/A")],
        ["Seller:", settlement.get("seller_name", "N/A")],
        ["Vehicle:", settlement.get("vehicle_title", "N/A")],
        ["VIN:", settlement.get("vehicle_vin", "N/A")],
        ["Sale Date:", _format_date(settlement.get("created_at", datetime.now()))],
    ]
    
    details_table = Table(details, colWidths=[1.5*inch, 5.5*inch])
    details_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 0.3*inch))
    
    # Financial breakdown
    financial_data = [
        ["Description", "Amount"],
        ["Hammer Price (Sale Amount)", _format_currency(settlement.get("hammer_price", 0))],
        [f"BidVex Commission ({settlement.get('seller_commission_rate', 0) * 100:.1f}%)", f"-{_format_currency(settlement.get('seller_commission', 0))}"],
        ["NET PAYOUT", _format_currency(settlement.get("net_payout", 0))],
    ]
    
    fin_table = Table(financial_data, colWidths=[5*inch, 2*inch])
    fin_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), PRIMARY_COLOR),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, -1), (-1, -1), 12),
        ('TEXTCOLOR', (1, -1), (1, -1), ACCENT_COLOR),
        ('LINEABOVE', (0, -1), (-1, -1), 2, PRIMARY_COLOR),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOX', (0, 0), (-1, -1), 1, BORDER_COLOR),
    ]))
    elements.append(financial_data)
    elements.append(fin_table)
    
    # Build PDF
    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    
    return pdf_bytes
