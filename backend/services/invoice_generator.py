"""
BidVex Invoice PDF Generator
Generates compliant invoices splitting Platform Service Fees and Item Sale Price
"""

from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from io import BytesIO
import base64
import logging

# Try to import reportlab, fall back to basic text if not available
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logging.warning("reportlab not installed - PDF generation will be limited")

from services.tax_engine import (
    BIDVEX_LEGAL_NAME,
    BIDVEX_ADDRESS,
    BIDVEX_GST_NUMBER,
    BIDVEX_QST_NUMBER,
    VehiclePaymentResult,
    GeneralPaymentResult,
)

logger = logging.getLogger(__name__)


def generate_invoice_number() -> str:
    """Generate unique invoice number"""
    now = datetime.now(timezone.utc)
    return f"BV-{now.strftime('%Y%m%d')}-{now.strftime('%H%M%S%f')[:10]}"


def format_currency(amount: float, currency: str = "CAD") -> str:
    """Format amount as currency string"""
    return f"${amount:,.2f} {currency}"


def generate_vehicle_invoice_pdf(
    payment_result: VehiclePaymentResult,
    buyer_info: Dict[str, Any],
    seller_info: Dict[str, Any],
    auction_info: Dict[str, Any],
    invoice_number: Optional[str] = None
) -> bytes:
    """
    Generate PDF invoice for vehicle auction
    
    Shows:
    - BidVex Platform Service Fees (with GST/QST numbers)
    - Balance due to seller via Bank Draft
    """
    if not REPORTLAB_AVAILABLE:
        return _generate_text_invoice(payment_result, buyer_info, seller_info, auction_info)
    
    invoice_num = invoice_number or generate_invoice_number()
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    styles = getSampleStyleSheet()
    elements = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#374151'),
        spaceBefore=15,
        spaceAfter=10
    )
    
    normal_style = styles['Normal']
    
    # Header
    elements.append(Paragraph("AUCTION INVOICE", title_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Invoice info table
    invoice_info = [
        ['Invoice Number:', invoice_num],
        ['Invoice Date:', datetime.now(timezone.utc).strftime('%B %d, %Y')],
        ['Auction Type:', 'Vehicle Auction'],
        ['Payment Method:', 'BidVex Fees via Stripe / Balance via Bank Draft'],
    ]
    
    info_table = Table(invoice_info, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.25*inch))
    
    # Buyer & Seller info side by side
    party_data = [
        ['BUYER', 'SELLER'],
        [buyer_info.get('name', 'N/A'), seller_info.get('name', 'N/A')],
        [buyer_info.get('email', ''), seller_info.get('email', '')],
        [buyer_info.get('address', ''), seller_info.get('address', '')],
    ]
    
    party_table = Table(party_data, colWidths=[3*inch, 3*inch])
    party_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(party_table)
    elements.append(Spacer(1, 0.25*inch))
    
    # Auction Item
    elements.append(Paragraph("AUCTION ITEM", section_style))
    item_data = [
        ['Item Description', auction_info.get('title', 'Vehicle')],
        ['Lot Number', auction_info.get('lot_number', 'N/A')],
        ['VIN', auction_info.get('vin', 'N/A')],
        ['Hammer Price', format_currency(payment_result.hammer_price)],
    ]
    
    item_table = Table(item_data, colWidths=[2*inch, 4*inch])
    item_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(item_table)
    elements.append(Spacer(1, 0.25*inch))
    
    # Platform Service Fees (BidVex)
    elements.append(Paragraph("PLATFORM SERVICE FEES", section_style))
    elements.append(Paragraph(f"<b>Provider:</b> {BIDVEX_LEGAL_NAME}", normal_style))
    elements.append(Paragraph(f"<b>GST #:</b> {BIDVEX_GST_NUMBER}", normal_style))
    elements.append(Paragraph(f"<b>QST #:</b> {BIDVEX_QST_NUMBER}", normal_style))
    elements.append(Spacer(1, 0.1*inch))
    
    fees_data = [
        ['Description', 'Rate', 'Amount'],
        ['Buyer Premium', f"{payment_result.buyer_premium_rate * 100:.1f}%", format_currency(payment_result.buyer_premium)],
        ['Platform Fee', '2.5%', format_currency(payment_result.platform_fee)],
        ['Subtotal (Fees)', '', format_currency(payment_result.bidvex_fees_subtotal)],
        ['GST (5%)', '', format_currency(payment_result.bidvex_fees_gst)],
        ['QST (9.975%)', '', format_currency(payment_result.bidvex_fees_qst)],
        ['TOTAL PLATFORM FEES (Charged Now)', '', format_currency(payment_result.stripe_charge_total)],
    ]
    
    fees_table = Table(fees_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
    fees_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#dcfce7')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(fees_table)
    elements.append(Spacer(1, 0.25*inch))
    
    # Balance Due to Seller
    elements.append(Paragraph("BALANCE DUE TO SELLER", section_style))
    
    balance_data = [
        ['Description', 'Amount'],
        ['Hammer Price (Payable via Bank Draft)', format_currency(payment_result.seller_balance_due)],
    ]
    
    balance_table = Table(balance_data, colWidths=[4*inch, 2*inch])
    balance_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#dc2626')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#fef2f2')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(balance_table)
    elements.append(Spacer(1, 0.25*inch))
    
    # Next Steps
    elements.append(Paragraph("NEXT STEPS", section_style))
    elements.append(Paragraph(payment_result.next_steps_message, normal_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Footer
    elements.append(Spacer(1, 0.5*inch))
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#6b7280'),
        alignment=TA_CENTER
    )
    elements.append(Paragraph(
        f"{BIDVEX_LEGAL_NAME} | {BIDVEX_ADDRESS}<br/>"
        f"GST/TPS #: {BIDVEX_GST_NUMBER} | QST/TVQ #: {BIDVEX_QST_NUMBER}",
        footer_style
    ))
    
    doc.build(elements)
    return buffer.getvalue()


def generate_general_invoice_pdf(
    payment_result: GeneralPaymentResult,
    buyer_info: Dict[str, Any],
    seller_info: Dict[str, Any],
    auction_info: Dict[str, Any],
    invoice_number: Optional[str] = None
) -> bytes:
    """
    Generate PDF invoice for general auction
    
    Shows:
    - Item Sale Price (with Seller's tax info if business)
    - Platform Service Fees (with BidVex GST/QST numbers)
    """
    if not REPORTLAB_AVAILABLE:
        return _generate_text_invoice_general(payment_result, buyer_info, seller_info, auction_info)
    
    invoice_num = invoice_number or generate_invoice_number()
    buffer = BytesIO()
    
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )
    
    styles = getSampleStyleSheet()
    elements = []
    
    # Custom styles
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1e40af'),
        spaceAfter=20,
        alignment=TA_CENTER
    )
    
    section_style = ParagraphStyle(
        'Section',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#374151'),
        spaceBefore=15,
        spaceAfter=10
    )
    
    normal_style = styles['Normal']
    
    # Header
    elements.append(Paragraph("AUCTION INVOICE", title_style))
    elements.append(Spacer(1, 0.25*inch))
    
    # Invoice info
    invoice_info = [
        ['Invoice Number:', invoice_num],
        ['Invoice Date:', datetime.now(timezone.utc).strftime('%B %d, %Y')],
        ['Auction Type:', 'General Auction'],
        ['Seller Type:', 'Business' if payment_result.seller_is_business else 'Private Individual'],
    ]
    
    info_table = Table(invoice_info, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 0.25*inch))
    
    # Buyer & Seller info
    party_data = [
        ['BUYER', 'SELLER'],
        [buyer_info.get('name', 'N/A'), seller_info.get('name', 'N/A')],
        [buyer_info.get('email', ''), seller_info.get('email', '')],
    ]
    
    if payment_result.seller_is_business:
        party_data.append(['', f"GST #: {seller_info.get('gst_number', 'N/A')}"])
        party_data.append(['', f"QST #: {seller_info.get('qst_number', 'N/A')}"])
    
    party_table = Table(party_data, colWidths=[3*inch, 3*inch])
    party_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f3f4f6')),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(party_table)
    elements.append(Spacer(1, 0.25*inch))
    
    # SECTION 1: Item Sale Price
    elements.append(Paragraph("ITEM SALE PRICE", section_style))
    if payment_result.seller_is_business:
        elements.append(Paragraph(f"<b>Seller (Business):</b> {seller_info.get('business_name', seller_info.get('name', 'N/A'))}", normal_style))
        elements.append(Paragraph(f"<b>GST #:</b> {seller_info.get('gst_number', 'N/A')}", normal_style))
        elements.append(Paragraph(f"<b>QST #:</b> {seller_info.get('qst_number', 'N/A')}", normal_style))
    else:
        elements.append(Paragraph(f"<b>Seller (Private):</b> {seller_info.get('name', 'N/A')}", normal_style))
        elements.append(Paragraph("<i>No tax applicable - private sale</i>", normal_style))
    elements.append(Spacer(1, 0.1*inch))
    
    item_data = [
        ['Description', 'Amount'],
        [auction_info.get('title', 'Auction Item'), format_currency(payment_result.hammer_price)],
    ]
    
    if payment_result.seller_is_business:
        item_data.extend([
            ['GST (5%)', format_currency(payment_result.hammer_gst)],
            ['QST (9.975%)', format_currency(payment_result.hammer_qst)],
            ['Item Subtotal', format_currency(payment_result.hammer_price + payment_result.hammer_tax_total)],
        ])
    else:
        item_data.append(['Item Subtotal', format_currency(payment_result.hammer_price)])
    
    item_table = Table(item_data, colWidths=[4*inch, 2*inch])
    item_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(item_table)
    elements.append(Spacer(1, 0.25*inch))
    
    # SECTION 2: Platform Service Fees
    elements.append(Paragraph("PLATFORM SERVICE FEES", section_style))
    elements.append(Paragraph(f"<b>Provider:</b> {BIDVEX_LEGAL_NAME}", normal_style))
    elements.append(Paragraph(f"<b>GST #:</b> {BIDVEX_GST_NUMBER}", normal_style))
    elements.append(Paragraph(f"<b>QST #:</b> {BIDVEX_QST_NUMBER}", normal_style))
    elements.append(Spacer(1, 0.1*inch))
    
    fees_data = [
        ['Description', 'Rate', 'Amount'],
        ['Buyer Premium', f"{payment_result.buyer_premium_rate * 100:.1f}%", format_currency(payment_result.buyer_premium)],
        ['GST on Buyer Premium (5%)', '', format_currency(payment_result.bidvex_fees_gst)],
        ['QST on Buyer Premium (9.975%)', '', format_currency(payment_result.bidvex_fees_qst)],
        ['Platform Fees Subtotal', '', format_currency(payment_result.buyer_pays_fees + payment_result.buyer_pays_fees_tax)],
    ]
    
    fees_table = Table(fees_data, colWidths=[3*inch, 1.5*inch, 1.5*inch])
    fees_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1e40af')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
    ]))
    elements.append(fees_table)
    elements.append(Spacer(1, 0.25*inch))
    
    # GRAND TOTAL
    elements.append(Paragraph("TOTAL", section_style))
    
    total_data = [
        ['GRAND TOTAL (Charged Now)', format_currency(payment_result.buyer_total)],
    ]
    
    total_table = Table(total_data, colWidths=[4*inch, 2*inch])
    total_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 14),
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#dcfce7')),
        ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('BOX', (0, 0), (-1, -1), 2, colors.HexColor('#059669')),
    ]))
    elements.append(total_table)
    elements.append(Spacer(1, 0.5*inch))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=8,
        textColor=colors.HexColor('#6b7280'),
        alignment=TA_CENTER
    )
    elements.append(Paragraph(
        f"{BIDVEX_LEGAL_NAME} | {BIDVEX_ADDRESS}<br/>"
        f"GST/TPS #: {BIDVEX_GST_NUMBER} | QST/TVQ #: {BIDVEX_QST_NUMBER}",
        footer_style
    ))
    
    doc.build(elements)
    return buffer.getvalue()


def _generate_text_invoice(payment_result, buyer_info, seller_info, auction_info) -> bytes:
    """Fallback text invoice when reportlab not available"""
    invoice_num = generate_invoice_number()
    
    text = f"""
================================================================================
                              AUCTION INVOICE
================================================================================
Invoice #: {invoice_num}
Date: {datetime.now(timezone.utc).strftime('%B %d, %Y')}
Type: Vehicle Auction

--------------------------------------------------------------------------------
BUYER: {buyer_info.get('name', 'N/A')}
       {buyer_info.get('email', '')}

SELLER: {seller_info.get('name', 'N/A')}
        {seller_info.get('email', '')}

--------------------------------------------------------------------------------
AUCTION ITEM
  Description: {auction_info.get('title', 'Vehicle')}
  VIN: {auction_info.get('vin', 'N/A')}
  Hammer Price: {format_currency(payment_result.hammer_price)}

--------------------------------------------------------------------------------
PLATFORM SERVICE FEES (BidVex Inc.)
GST #: {BIDVEX_GST_NUMBER}
QST #: {BIDVEX_QST_NUMBER}

  Buyer Premium ({payment_result.buyer_premium_rate * 100:.1f}%): {format_currency(payment_result.buyer_premium)}
  Platform Fee (2.5%): {format_currency(payment_result.platform_fee)}
  Subtotal: {format_currency(payment_result.bidvex_fees_subtotal)}
  GST (5%): {format_currency(payment_result.bidvex_fees_gst)}
  QST (9.975%): {format_currency(payment_result.bidvex_fees_qst)}
  ------------------------------------------------
  TOTAL PLATFORM FEES: {format_currency(payment_result.stripe_charge_total)}

--------------------------------------------------------------------------------
BALANCE DUE TO SELLER (via Bank Draft)
  {format_currency(payment_result.seller_balance_due)}

--------------------------------------------------------------------------------
NEXT STEPS:
{payment_result.next_steps_message}

================================================================================
{BIDVEX_LEGAL_NAME} | {BIDVEX_ADDRESS}
================================================================================
"""
    return text.encode('utf-8')


def _generate_text_invoice_general(payment_result, buyer_info, seller_info, auction_info) -> bytes:
    """Fallback text invoice for general auctions"""
    invoice_num = generate_invoice_number()
    
    seller_type = "Business" if payment_result.seller_is_business else "Private Individual"
    
    text = f"""
================================================================================
                              AUCTION INVOICE
================================================================================
Invoice #: {invoice_num}
Date: {datetime.now(timezone.utc).strftime('%B %d, %Y')}
Type: General Auction
Seller Type: {seller_type}

--------------------------------------------------------------------------------
BUYER: {buyer_info.get('name', 'N/A')}
       {buyer_info.get('email', '')}

SELLER: {seller_info.get('name', 'N/A')}
        {seller_info.get('email', '')}
"""
    
    if payment_result.seller_is_business:
        text += f"""        GST #: {seller_info.get('gst_number', 'N/A')}
        QST #: {seller_info.get('qst_number', 'N/A')}
"""
    
    text += f"""
--------------------------------------------------------------------------------
ITEM SALE PRICE
  {auction_info.get('title', 'Auction Item')}: {format_currency(payment_result.hammer_price)}
"""
    
    if payment_result.seller_is_business:
        text += f"""  GST (5%): {format_currency(payment_result.hammer_gst)}
  QST (9.975%): {format_currency(payment_result.hammer_qst)}
  Item Subtotal: {format_currency(payment_result.hammer_price + payment_result.hammer_tax_total)}
"""
    else:
        text += f"""  (No tax - private sale)
  Item Subtotal: {format_currency(payment_result.hammer_price)}
"""
    
    text += f"""
--------------------------------------------------------------------------------
PLATFORM SERVICE FEES (BidVex Inc.)
GST #: {BIDVEX_GST_NUMBER}
QST #: {BIDVEX_QST_NUMBER}

  Buyer Premium ({payment_result.buyer_premium_rate * 100:.1f}%): {format_currency(payment_result.buyer_premium)}
  GST (5%): {format_currency(payment_result.bidvex_fees_gst)}
  QST (9.975%): {format_currency(payment_result.bidvex_fees_qst)}
  Platform Fees Subtotal: {format_currency(payment_result.buyer_pays_fees + payment_result.buyer_pays_fees_tax)}

--------------------------------------------------------------------------------
GRAND TOTAL: {format_currency(payment_result.buyer_total)}

================================================================================
{BIDVEX_LEGAL_NAME} | {BIDVEX_ADDRESS}
================================================================================
"""
    return text.encode('utf-8')


# ============= EXPORTS =============

__all__ = [
    "generate_invoice_number",
    "format_currency",
    "generate_vehicle_invoice_pdf",
    "generate_general_invoice_pdf",
    "REPORTLAB_AVAILABLE",
]
