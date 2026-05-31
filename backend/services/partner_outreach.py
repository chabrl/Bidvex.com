"""
iter247 — Partner Program Outreach (PDF flyer + cold-email blast).

The exact bilingual-ready English copy and PDF layout for the high-converting
B2B "first listing free" campaign targeting professional Auctioneers &
Liquidators. Used by the one-shot blast endpoint
`POST /api/admin/promotions/partner-outreach/send`.

This module exposes:
  • PARTNER_OUTREACH_EMAIL_SUBJECT
  • PARTNER_OUTREACH_EMAIL_HTML(coupon_code)  → str
  • build_partner_outreach_pdf(coupon_code)   → bytes
"""
from __future__ import annotations

from io import BytesIO
from typing import Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
)


PARTNER_OUTREACH_EMAIL_SUBJECT = "Exclusive offer to try BidVex for free!"

# Locked English copy (user-provided verbatim).
_PARTNER_OUTREACH_EMAIL_TEXT = """Hello BidVex Partners!

We are excited to invite you to try our advanced auction platform, bidvex.com.

As a special offer, we are pleased to offer you your first listing completely free, with no subscription or listing fees. We want to give you this exclusive opportunity to try our latest technological platform risk-free.

Discover how easy it is to reach our wide network of registered buyers and experience our real-time bidding infrastructure.

Please check the attachment for full details on how to register and launch your first free listing.

Best regards,

The BidVex Team
support@bidvex.ca
"""


def partner_outreach_email_html(coupon_code: Optional[str] = None) -> str:
    """Render the partner outreach email body as branded HTML.

    The coupon code is surfaced inline near the CTA so partners can copy
    it without opening the PDF; the PDF still carries the canonical
    step-by-step registration protocol.
    """
    coupon_block = ""
    if coupon_code:
        coupon_block = f"""
<div style="margin:24px 0;padding:16px 18px;border:1.5px dashed #f59e0b;
            background:#fffbeb;border-radius:10px;text-align:center;">
  <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;
            letter-spacing:1.5px;color:#92400e;font-weight:700;">
    Your Exclusive Partner Coupon
  </p>
  <code style="display:inline-block;margin-top:6px;font-size:20px;
               font-weight:800;letter-spacing:1.2px;color:#0f172a;
               background:#ffffff;padding:8px 18px;border-radius:6px;
               border:1px solid #fde68a;">
    {coupon_code}
  </code>
</div>
"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{PARTNER_OUTREACH_EMAIL_SUBJECT}</title></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background:#f0f4f8;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:32px 16px;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.08);">
  <tr><td style="background:linear-gradient(135deg,#1e40af 0%,#2563eb 100%);padding:28px 32px;text-align:center;">
    <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:800;letter-spacing:-0.5px;">BidVex</h1>
    <p style="margin:6px 0 0;color:#93c5fd;font-size:12px;text-transform:uppercase;letter-spacing:2px;font-weight:600;">
      Partner Program
    </p>
  </td></tr>
  <tr><td style="padding:36px 32px 8px;">
    <h2 style="margin:0 0 18px;color:#0f172a;font-size:22px;font-weight:700;">
      Hello BidVex Partners!
    </h2>
    <p style="color:#475569;font-size:15px;line-height:1.7;margin:0 0 14px;">
      We are excited to invite you to try our advanced auction platform,
      <a href="https://bidvex.com" style="color:#2563eb;text-decoration:none;font-weight:600;">bidvex.com</a>.
    </p>
    <p style="color:#475569;font-size:15px;line-height:1.7;margin:0 0 14px;">
      As a special offer, we are pleased to offer you
      <strong style="color:#0f172a;">your first listing completely free</strong>,
      with no subscription or listing fees. We want to give you this exclusive
      opportunity to try our latest technological platform risk-free.
    </p>
    <p style="color:#475569;font-size:15px;line-height:1.7;margin:0 0 14px;">
      Discover how easy it is to reach our wide network of registered buyers and
      experience our real-time bidding infrastructure.
    </p>
    {coupon_block}
    <p style="color:#475569;font-size:15px;line-height:1.7;margin:18px 0 0;">
      Please check the attachment for full details on how to register and launch
      your first free listing.
    </p>
    <p style="margin:28px 0 0;text-align:center;">
      <a href="https://bidvex.com/become-a-partner"
         style="display:inline-block;background:linear-gradient(135deg,#1e40af,#2563eb);
                color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;
                font-weight:700;font-size:15px;letter-spacing:0.3px;">
        Register as Partner
      </a>
    </p>
    <p style="margin:36px 0 0;color:#475569;font-size:14px;line-height:1.6;">
      Best regards,<br>
      <strong style="color:#0f172a;">The BidVex Team</strong><br>
      <a href="mailto:support@bidvex.ca" style="color:#2563eb;text-decoration:none;">support@bidvex.ca</a>
    </p>
  </td></tr>
  <tr><td style="background:#f8fafc;padding:18px 32px;border-top:1px solid #e2e8f0;border-radius:0 0 16px 16px;text-align:center;">
    <p style="margin:0;color:#94a3b8;font-size:11px;line-height:1.6;">
      &copy; 2026 BidVex Inc. — 761 Rue Chalifoux, Sherbrooke (Québec) J1G 0A8<br>
      <a href="https://bidvex.com/legal" style="color:#2563eb;text-decoration:none;">Privacy</a> &middot;
      <a href="https://bidvex.com/legal" style="color:#2563eb;text-decoration:none;">Terms</a>
    </p>
  </td></tr>
</table>
</td></tr>
</table>
</body></html>"""


def build_partner_outreach_pdf(coupon_code: Optional[str] = None) -> bytes:
    """Render the locked Partner Program Evaluation Guide PDF.

    Layout (verbatim per spec):
      • Header: "BidVex | Online Auction Marketplace - Partner Program
                 Evaluation Guide"
      • Value proposition (4 zero-dollar bullets)
      • Exclusive Partner Benefits (4 items)
      • Registration Protocol (4-step playbook)
      • Coupon code highlight (when provided)
    """
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title="BidVex Partner Program Evaluation Guide",
        author="BidVex Inc.",
    )

    base = getSampleStyleSheet()
    NAVY = colors.HexColor("#1e3a8a")
    BLUE = colors.HexColor("#2563eb")
    GREEN = colors.HexColor("#059669")
    SLATE_500 = colors.HexColor("#64748b")
    SLATE_900 = colors.HexColor("#0f172a")
    AMBER = colors.HexColor("#f59e0b")

    h_title = ParagraphStyle(
        "TitleH", parent=base["Title"],
        fontName="Helvetica-Bold", fontSize=18, leading=22,
        textColor=NAVY, alignment=0, spaceAfter=4,
    )
    h_sub = ParagraphStyle(
        "Sub", parent=base["BodyText"],
        fontName="Helvetica", fontSize=10, leading=13,
        textColor=SLATE_500, spaceAfter=16,
    )
    h_section = ParagraphStyle(
        "Section", parent=base["Heading2"],
        fontName="Helvetica-Bold", fontSize=13, leading=16,
        textColor=BLUE, spaceBefore=14, spaceAfter=6,
    )
    body = ParagraphStyle(
        "Body", parent=base["BodyText"],
        fontName="Helvetica", fontSize=10.5, leading=15,
        textColor=SLATE_900, spaceAfter=4,
    )
    bullet = ParagraphStyle(
        "Bullet", parent=body, leftIndent=12, bulletIndent=0,
        spaceAfter=3,
    )
    step = ParagraphStyle(
        "Step", parent=body, leftIndent=18, bulletIndent=0,
        spaceAfter=4,
    )

    story = []

    # ── Header ──────────────────────────────────────────────────────
    story.append(Paragraph(
        "BidVex | Online Auction Marketplace",
        h_title,
    ))
    story.append(Paragraph(
        "Partner Program Evaluation Guide",
        ParagraphStyle(
            "Tagline", parent=h_title, fontSize=13, leading=16,
            textColor=BLUE, spaceAfter=2,
        ),
    ))
    story.append(Paragraph(
        "Exclusive launch offer for Auctioneers &amp; Liquidators",
        h_sub,
    ))
    story.append(HRFlowable(width="100%", thickness=1.2, color=BLUE, spaceAfter=14))

    # ── Value proposition ───────────────────────────────────────────
    story.append(Paragraph("Your First Listing — 100% FREE", h_section))
    story.append(Paragraph(
        "Test our latest technological platform with zero upfront commitment. "
        "Your first multi-auction listing on BidVex carries no fees of any kind:",
        body,
    ))
    value_rows = [
        ["•", Paragraph("<b>$0 Setup Fee</b> &mdash; create your partner account at no cost.", body)],
        ["•", Paragraph("<b>$0 Subscription Fees</b> &mdash; no monthly platform charge during your trial.", body)],
        ["•", Paragraph("<b>$0 Listing Creation Costs</b> &mdash; publish your first auction free of charge.", body)],
        ["•", Paragraph("<b>0% Platform Fees</b> &mdash; we waive both seller commission and buyer premium on your first sale.", body)],
    ]
    tbl = Table(value_rows, colWidths=[12, 7.0 * inch - 12])
    tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("TEXTCOLOR", (0, 0), (0, -1), GREEN),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (0, -1), 12),
    ]))
    story.append(tbl)
    story.append(Spacer(1, 8))

    # ── Exclusive Partner Benefits ──────────────────────────────────
    story.append(Paragraph("Exclusive Partner Benefits", h_section))
    benefits = [
        ("Bulk Asset Uploading",
         "Drop a CSV or photo batch to launch hundreds of lots in one go."),
        ("Dedicated Broker Status Badging",
         "Verified Partner badge on every listing &mdash; build buyer trust at first glance."),
        ("Real-Time Analytics",
         "Live bidder activity, watchlist counts, and conversion metrics on every auction."),
        ("Secure Financial Routing via Stripe Connect",
         "Direct payouts with PCI-compliant settlement and full transaction audit trails."),
    ]
    for title, desc in benefits:
        story.append(Paragraph(
            f"<b style='color:#1e3a8a'>&#8226; {title}.</b> {desc}",
            bullet,
        ))
    story.append(Spacer(1, 8))

    # ── Coupon highlight ───────────────────────────────────────────
    if coupon_code:
        coupon_tbl = Table(
            [[Paragraph(
                f"<b>Your Exclusive Coupon Code:</b> "
                f"<font name='Courier-Bold' size='13' color='#0f172a'>{coupon_code}</font>",
                ParagraphStyle("Cou", parent=body, fontSize=11, alignment=1),
            )]],
            colWidths=[7.1 * inch],
        )
        coupon_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fffbeb")),
            ("BOX", (0, 0), (-1, -1), 1.2, AMBER),
            ("TOPPADDING", (0, 0), (-1, -1), 10),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ("LEFTPADDING", (0, 0), (-1, -1), 12),
            ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ]))
        story.append(coupon_tbl)
        story.append(Spacer(1, 8))

    # ── Registration Protocol ──────────────────────────────────────
    story.append(Paragraph("Registration Protocol", h_section))
    steps = [
        "Go to <b>bidvex.com</b> and select <b>“Partner Registration”</b>.",
        "Complete the multi-step verification (Company &amp; regional setup).",
        "Enter your exclusive <b>Partner Coupon Code</b> in your new dashboard "
        "to automatically apply the free trial credit.",
        "Upload your assets and launch your auction live with <b>zero upfront fees</b>.",
    ]
    for idx, txt in enumerate(steps, start=1):
        story.append(Paragraph(
            f"<font color='#2563eb'><b>{idx}.</b></font> &nbsp;{txt}",
            step,
        ))
    story.append(Spacer(1, 14))

    # ── Footer ──────────────────────────────────────────────────────
    story.append(HRFlowable(width="100%", thickness=0.5, color=SLATE_500, spaceBefore=14, spaceAfter=8))
    story.append(Paragraph(
        "Questions? Reach our partner desk anytime at "
        "<b>support@bidvex.ca</b> or visit "
        "<a href='https://bidvex.com/become-a-partner' color='#2563eb'>bidvex.com/become-a-partner</a>.",
        ParagraphStyle("Foot", parent=body, fontSize=9.5, textColor=SLATE_500),
    ))
    story.append(Paragraph(
        "&copy; 2026 BidVex Inc. &mdash; 761 Rue Chalifoux, Sherbrooke (Québec) J1G 0A8",
        ParagraphStyle("Foot2", parent=body, fontSize=8.5, textColor=SLATE_500),
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes


__all__ = [
    "PARTNER_OUTREACH_EMAIL_SUBJECT",
    "partner_outreach_email_html",
    "build_partner_outreach_pdf",
]
