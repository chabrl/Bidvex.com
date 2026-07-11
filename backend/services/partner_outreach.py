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

from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional

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
service@bidvex.com
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
      <a href="mailto:service@bidvex.com" style="color:#2563eb;text-decoration:none;">service@bidvex.com</a>
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
        "<b>service@bidvex.com</b> or visit "
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
    "PARTNER_OUTREACH_EMAIL_SUBJECT_FR",
    "PARTNER_FOLLOWUP_EMAIL_SUBJECT",
    "PARTNER_FOLLOWUP_EMAIL_SUBJECT_FR",
    "partner_outreach_email_html",
    "partner_outreach_email_html_fr",
    "partner_followup_email_html",
    "partner_followup_email_html_fr",
    "build_partner_outreach_pdf",
    "build_partner_outreach_pdf_fr",
]


# ═════════════════════════════════════════════════════════════════════
# iter248 Mission 1 — Quebec French localization (email + PDF)
# ═════════════════════════════════════════════════════════════════════

PARTNER_OUTREACH_EMAIL_SUBJECT_FR = "Offre exclusive : Essayez BidVex gratuitement !"


def partner_outreach_email_html_fr(coupon_code: Optional[str] = None) -> str:
    """Render the French (Quebec) partner outreach email body as branded HTML.

    Mirrors the structure of `partner_outreach_email_html` byte-for-byte
    with formal corporate French translation.
    """
    coupon_block = ""
    if coupon_code:
        coupon_block = f"""
<div style="margin:24px 0;padding:16px 18px;border:1.5px dashed #f59e0b;
            background:#fffbeb;border-radius:10px;text-align:center;">
  <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;
            letter-spacing:1.5px;color:#92400e;font-weight:700;">
    Votre code promo partenaire exclusif
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
<html lang="fr-CA">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{PARTNER_OUTREACH_EMAIL_SUBJECT_FR}</title></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background:#f0f4f8;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f8;padding:32px 16px;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.08);">
  <tr><td style="background:linear-gradient(135deg,#1e40af 0%,#2563eb 100%);padding:28px 32px;text-align:center;">
    <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:800;letter-spacing:-0.5px;">BidVex</h1>
    <p style="margin:6px 0 0;color:#93c5fd;font-size:12px;text-transform:uppercase;letter-spacing:2px;font-weight:600;">
      Programme Partenaires
    </p>
  </td></tr>
  <tr><td style="padding:36px 32px 8px;">
    <h2 style="margin:0 0 18px;color:#0f172a;font-size:22px;font-weight:700;">
      Bonjour, partenaires BidVex !
    </h2>
    <p style="color:#475569;font-size:15px;line-height:1.7;margin:0 0 14px;">
      Nous sommes ravis de vous inviter à essayer notre plateforme d'enchères avancée,
      <a href="https://bidvex.com" style="color:#2563eb;text-decoration:none;font-weight:600;">bidvex.com</a>.
    </p>
    <p style="color:#475569;font-size:15px;line-height:1.7;margin:0 0 14px;">
      À titre d'offre spéciale, nous avons le plaisir de vous offrir
      <strong style="color:#0f172a;">votre première annonce entièrement gratuite</strong>,
      sans frais d'abonnement ni frais d'inscription. Nous tenons à vous donner cette
      occasion exclusive d'essayer notre toute dernière plateforme technologique sans risque.
    </p>
    <p style="color:#475569;font-size:15px;line-height:1.7;margin:0 0 14px;">
      Découvrez à quel point il est facile de joindre notre vaste réseau d'acheteurs
      inscrits et de profiter de notre infrastructure d'enchères en temps réel.
    </p>
    {coupon_block}
    <p style="color:#475569;font-size:15px;line-height:1.7;margin:18px 0 0;">
      Veuillez consulter la pièce jointe pour tous les détails sur l'inscription
      et le lancement de votre première annonce gratuite.
    </p>
    <p style="margin:28px 0 0;text-align:center;">
      <a href="https://bidvex.com/become-a-partner"
         style="display:inline-block;background:linear-gradient(135deg,#1e40af,#2563eb);
                color:#fff;text-decoration:none;padding:14px 32px;border-radius:8px;
                font-weight:700;font-size:15px;letter-spacing:0.3px;">
        S'inscrire comme partenaire
      </a>
    </p>
    <p style="margin:36px 0 0;color:#475569;font-size:14px;line-height:1.6;">
      Cordialement,<br>
      <strong style="color:#0f172a;">L'équipe BidVex</strong><br>
      <a href="mailto:service@bidvex.com" style="color:#2563eb;text-decoration:none;">service@bidvex.com</a>
    </p>
  </td></tr>
  <tr><td style="background:#f8fafc;padding:18px 32px;border-top:1px solid #e2e8f0;border-radius:0 0 16px 16px;text-align:center;">
    <p style="margin:0;color:#94a3b8;font-size:11px;line-height:1.6;">
      &copy; 2026 BidVex Inc. — 761, rue Chalifoux, Sherbrooke (Québec) J1G 0A8<br>
      <a href="https://bidvex.com/legal" style="color:#2563eb;text-decoration:none;">Confidentialité</a> &middot;
      <a href="https://bidvex.com/legal" style="color:#2563eb;text-decoration:none;">Conditions</a>
    </p>
  </td></tr>
</table>
</td></tr>
</table>
</body></html>"""


def build_partner_outreach_pdf_fr(coupon_code: Optional[str] = None) -> bytes:
    """Render the French Guide d'évaluation du programme partenaires PDF."""
    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=LETTER,
        leftMargin=0.7 * inch,
        rightMargin=0.7 * inch,
        topMargin=0.7 * inch,
        bottomMargin=0.7 * inch,
        title="Guide d'évaluation du programme partenaires BidVex",
        author="BidVex Inc.",
    )

    base = getSampleStyleSheet()
    NAVY = colors.HexColor("#1e3a8a")
    BLUE = colors.HexColor("#2563eb")
    GREEN = colors.HexColor("#059669")
    SLATE_500 = colors.HexColor("#64748b")
    SLATE_900 = colors.HexColor("#0f172a")
    AMBER = colors.HexColor("#f59e0b")

    h_title = ParagraphStyle("TitleH", parent=base["Title"],
        fontName="Helvetica-Bold", fontSize=18, leading=22,
        textColor=NAVY, alignment=0, spaceAfter=4,
    )
    h_sub = ParagraphStyle("Sub", parent=base["BodyText"],
        fontName="Helvetica", fontSize=10, leading=13,
        textColor=SLATE_500, spaceAfter=16,
    )
    h_section = ParagraphStyle("Section", parent=base["Heading2"],
        fontName="Helvetica-Bold", fontSize=13, leading=16,
        textColor=BLUE, spaceBefore=14, spaceAfter=6,
    )
    body = ParagraphStyle("Body", parent=base["BodyText"],
        fontName="Helvetica", fontSize=10.5, leading=15,
        textColor=SLATE_900, spaceAfter=4,
    )
    bullet = ParagraphStyle("Bullet", parent=body, leftIndent=12, bulletIndent=0, spaceAfter=3)
    step = ParagraphStyle("Step", parent=body, leftIndent=18, bulletIndent=0, spaceAfter=4)

    story = []

    # ── Header ──
    story.append(Paragraph("BidVex | Marketplace d'enchères en ligne", h_title))
    story.append(Paragraph(
        "Guide d'évaluation du programme partenaires",
        ParagraphStyle("Tagline", parent=h_title, fontSize=13, leading=16,
                       textColor=BLUE, spaceAfter=2),
    ))
    story.append(Paragraph(
        "Offre de lancement exclusive pour encanteurs et liquidateurs",
        h_sub,
    ))
    story.append(HRFlowable(width="100%", thickness=1.2, color=BLUE, spaceAfter=14))

    # ── Value proposition ──
    story.append(Paragraph("Votre première annonce — 100 % GRATUITE", h_section))
    story.append(Paragraph(
        "Essayez notre toute dernière plateforme technologique sans aucun engagement "
        "financier. Votre première annonce d'enchères multiples sur BidVex ne comporte "
        "aucuns frais :",
        body,
    ))
    value_rows = [
        ["•", Paragraph("<b>0 $ de frais d'installation</b> &mdash; créez votre compte partenaire gratuitement.", body)],
        ["•", Paragraph("<b>0 $ de frais d'abonnement</b> &mdash; aucun frais mensuel pendant votre période d'essai.", body)],
        ["•", Paragraph("<b>0 $ de frais de création d'annonce</b> &mdash; publiez votre première enchère sans frais.", body)],
        ["•", Paragraph("<b>0 % de frais de plateforme</b> &mdash; nous renonçons à la commission vendeur et à la prime acheteur sur votre première vente.", body)],
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

    # ── Exclusive Partner Benefits ──
    story.append(Paragraph("Avantages exclusifs des partenaires", h_section))
    benefits = [
        ("Téléversement d'actifs en lot",
         "Déposez un fichier CSV ou un lot de photos pour lancer des centaines d'articles en une seule opération."),
        ("Badge de statut courtier dédié",
         "Badge Partenaire Vérifié sur chaque annonce &mdash; instaurez la confiance acheteur dès le premier coup d'œil."),
        ("Analyses en temps réel",
         "Activité des enchérisseurs, nombre d'observateurs et métriques de conversion en direct sur chaque enchère."),
        ("Acheminement financier sécurisé via Stripe Connect",
         "Versements directs avec règlement conforme PCI et journaux d'audit complets pour chaque transaction."),
    ]
    for title, desc in benefits:
        story.append(Paragraph(
            f"<b style='color:#1e3a8a'>&#8226; {title}.</b> {desc}",
            bullet,
        ))
    story.append(Spacer(1, 8))

    # ── Coupon highlight ──
    if coupon_code:
        coupon_tbl = Table(
            [[Paragraph(
                f"<b>Votre code promo exclusif :</b> "
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

    # ── Registration Protocol ──
    story.append(Paragraph("Protocole d'inscription", h_section))
    steps_fr = [
        "Visitez <b>bidvex.com</b> et sélectionnez <b>« Inscription Partenaire »</b>.",
        "Complétez la vérification en plusieurs étapes (configuration de l'entreprise et de la région).",
        "Saisissez votre <b>code promo partenaire</b> exclusif dans votre nouveau tableau de bord "
        "pour appliquer automatiquement le crédit d'essai gratuit.",
        "Téléversez vos actifs et lancez votre enchère en direct, <b>sans aucuns frais initiaux</b>.",
    ]
    for idx, txt in enumerate(steps_fr, start=1):
        story.append(Paragraph(
            f"<font color='#2563eb'><b>{idx}.</b></font> &nbsp;{txt}",
            step,
        ))
    story.append(Spacer(1, 14))

    # ── Footer ──
    story.append(HRFlowable(width="100%", thickness=0.5, color=SLATE_500, spaceBefore=14, spaceAfter=8))
    story.append(Paragraph(
        "Des questions ? Communiquez avec notre équipe partenaires à "
        "<b>service@bidvex.com</b> ou visitez "
        "<a href='https://bidvex.com/become-a-partner' color='#2563eb'>bidvex.com/become-a-partner</a>.",
        ParagraphStyle("Foot", parent=body, fontSize=9.5, textColor=SLATE_500),
    ))
    story.append(Paragraph(
        "&copy; 2026 BidVex Inc. &mdash; 761, rue Chalifoux, Sherbrooke (Québec) J1G 0A8",
        ParagraphStyle("Foot2", parent=body, fontSize=8.5, textColor=SLATE_500),
    ))

    doc.build(story)
    pdf_bytes = buf.getvalue()
    buf.close()
    return pdf_bytes


# ═════════════════════════════════════════════════════════════════════
# iter248 Mission 3 — 14-day follow-up reminder
# ═════════════════════════════════════════════════════════════════════

PARTNER_FOLLOWUP_EMAIL_SUBJECT = "Your exclusive partner trial credit is waiting"
PARTNER_FOLLOWUP_EMAIL_SUBJECT_FR = "Votre crédit d'essai partenaire exclusif vous attend"


def partner_followup_email_html(coupon_code: Optional[str] = None) -> str:
    """14-day follow-up email body (English) for partners who haven't
    redeemed their trial coupon yet."""
    coupon_html = (
        f"<code style='background:#fffbeb;padding:6px 14px;border:1px dashed #f59e0b;"
        f"border-radius:6px;font-weight:700;color:#0f172a;'>{coupon_code}</code>"
        if coupon_code else ""
    )
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"></head>
<body style="margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f0f4f8;padding:32px 16px;">
<table width="640" cellpadding="0" cellspacing="0" align="center"
       style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#1e40af,#2563eb);padding:28px 32px;text-align:center;">
  <h1 style="margin:0;color:#fff;font-size:24px;font-weight:800;">A quick reminder</h1>
  <p style="margin:6px 0 0;color:#93c5fd;font-size:12px;text-transform:uppercase;letter-spacing:1.8px;">
    BidVex Partner Program
  </p>
</td></tr>
<tr><td style="padding:32px 32px 8px;">
  <p style="color:#0f172a;font-size:16px;line-height:1.6;margin:0 0 14px;">Hi there,</p>
  <p style="color:#475569;font-size:15px;line-height:1.7;margin:0 0 14px;">
    Your <strong>exclusive partner trial credit</strong> is still waiting on bidvex.com.
    Two weeks ago we offered you your <strong>first listing completely free</strong> &mdash; that offer is still open, but only for a limited time.
  </p>
  <p style="color:#475569;font-size:15px;line-height:1.7;margin:0 0 14px;">
    Enter the code below in your partner dashboard to apply your $0 first-listing
    waiver and launch your auction live:
  </p>
  <p style="text-align:center;margin:24px 0;">{coupon_html}</p>
  <p style="color:#475569;font-size:15px;line-height:1.7;margin:18px 0 0;">
    Need help getting set up? Reach us anytime at
    <a href="mailto:service@bidvex.com" style="color:#2563eb;">service@bidvex.com</a>.
  </p>
  <p style="margin:32px 0 0;color:#475569;font-size:14px;">
    Best regards,<br><strong style="color:#0f172a;">The BidVex Team</strong>
  </p>
</td></tr>
<tr><td style="background:#f8fafc;padding:16px 32px;border-top:1px solid #e2e8f0;text-align:center;">
  <p style="margin:0;color:#94a3b8;font-size:11px;">&copy; 2026 BidVex Inc. &middot; service@bidvex.com</p>
</td></tr>
</table></body></html>"""


def partner_followup_email_html_fr(coupon_code: Optional[str] = None) -> str:
    """14-day follow-up email body (French) for QC partners."""
    coupon_html = (
        f"<code style='background:#fffbeb;padding:6px 14px;border:1px dashed #f59e0b;"
        f"border-radius:6px;font-weight:700;color:#0f172a;'>{coupon_code}</code>"
        if coupon_code else ""
    )
    return f"""<!DOCTYPE html>
<html lang="fr-CA"><head><meta charset="UTF-8"></head>
<body style="margin:0;font-family:-apple-system,Segoe UI,Roboto,sans-serif;background:#f0f4f8;padding:32px 16px;">
<table width="640" cellpadding="0" cellspacing="0" align="center"
       style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.08);">
<tr><td style="background:linear-gradient(135deg,#1e40af,#2563eb);padding:28px 32px;text-align:center;">
  <h1 style="margin:0;color:#fff;font-size:24px;font-weight:800;">Un petit rappel</h1>
  <p style="margin:6px 0 0;color:#93c5fd;font-size:12px;text-transform:uppercase;letter-spacing:1.8px;">
    Programme partenaires BidVex
  </p>
</td></tr>
<tr><td style="padding:32px 32px 8px;">
  <p style="color:#0f172a;font-size:16px;line-height:1.6;margin:0 0 14px;">Bonjour,</p>
  <p style="color:#475569;font-size:15px;line-height:1.7;margin:0 0 14px;">
    Votre <strong>crédit d'essai partenaire exclusif</strong> vous attend toujours sur bidvex.com.
    Il y a deux semaines, nous vous avons offert votre <strong>première annonce entièrement gratuite</strong>
    &mdash; cette offre demeure valide, mais pour une durée limitée.
  </p>
  <p style="color:#475569;font-size:15px;line-height:1.7;margin:0 0 14px;">
    Saisissez le code ci-dessous dans votre tableau de bord partenaire pour appliquer
    votre dispense de première annonce à 0 $ et lancer votre enchère :
  </p>
  <p style="text-align:center;margin:24px 0;">{coupon_html}</p>
  <p style="color:#475569;font-size:15px;line-height:1.7;margin:18px 0 0;">
    Besoin d'aide ? Communiquez avec nous à
    <a href="mailto:service@bidvex.com" style="color:#2563eb;">service@bidvex.com</a>.
  </p>
  <p style="margin:32px 0 0;color:#475569;font-size:14px;">
    Cordialement,<br><strong style="color:#0f172a;">L'équipe BidVex</strong>
  </p>
</td></tr>
<tr><td style="background:#f8fafc;padding:16px 32px;border-top:1px solid #e2e8f0;text-align:center;">
  <p style="margin:0;color:#94a3b8;font-size:11px;">&copy; 2026 BidVex Inc. &middot; service@bidvex.com</p>
</td></tr>
</table></body></html>"""


# ─── Language detection helper ────────────────────────────────────────

def detect_partner_language(user: Optional[Dict[str, Any]]) -> str:
    """Resolve the email language for a partner.

    Priority order:
      1. Explicit `preferred_language` field on the user record
         (`"fr"` or `"fr-CA"` → French; any other non-empty value pins
         English so an explicit user preference wins over province).
      2. Recorded province `"QC"` → French.
      3. Default → English.
    """
    if not user:
        return "en"
    pref = (user.get("preferred_language") or user.get("language") or "").lower().strip()
    if pref:
        # An explicit user preference always wins over province.
        return "fr" if pref.startswith("fr") else "en"
    province = (user.get("province") or "").upper().strip()
    if province == "QC":
        return "fr"
    return "en"


async def cron_partner_outreach_followup(
    db,
    *,
    coupon_code: str = "BIDVEX-PARTNERS",
    promotion_start: str = "2026-03-03",
    days_after_signup: int = 14,
    now_dt: Optional[datetime] = None,
    send_callable=None,
) -> Dict[str, Any]:
    """iter248 Mission 3 — Daily worker that fires a 14-day follow-up
    reminder to every partner who:
      • registered AFTER `promotion_start` (2026-03-03 by default)
      • has zero `promotion_usage` rows for `BIDVEX-PARTNERS`
      • whose `created_at` is exactly `today - days_after_signup`

    Language is decided per-recipient via `detect_partner_language()`.
    The `send_callable` lets callers (tests) inject a stub instead of
    the real `send_unified_email` dispatcher.
    """
    from datetime import datetime as _dt, timedelta as _tdelta, timezone as _tz

    today_dt = (now_dt or _dt.now(_tz.utc)).date()
    target_signup_day = today_dt - _tdelta(days=days_after_signup)

    # Range filter (start-of-day → end-of-day) since `created_at` is an ISO
    # timestamp string; a string-prefix range hits the index.
    range_lo = f"{target_signup_day.isoformat()}T00:00:00"
    range_hi = f"{target_signup_day.isoformat()}T23:59:59.999999+00:00"
    promo_start_iso = f"{promotion_start}T00:00:00"

    if send_callable is None:
        from services.emails._email_core import send_unified_email as _sender
        send_callable = _sender

    partners_cur = db.users.find({
        "$or": [{"is_partner": True}, {"account_type": "partner"}],
        "created_at": {
            "$gte": max(promo_start_iso, range_lo),
            "$lt": range_hi,
        },
    }, {
        "_id": 0, "id": 1, "email": 1, "first_name": 1, "name": 1,
        "company_name": 1, "province": 1, "preferred_language": 1,
        "language": 1, "created_at": 1,
    })
    partners = await partners_cur.to_list(length=5000)

    sent = 0
    skipped = 0
    results: List[Dict[str, Any]] = []
    for u in partners:
        # Skip if this partner has already redeemed the coupon.
        already_used = await db.promotion_usage.count_documents({
            "user_id": u.get("id"),
            "coupon_code": coupon_code,
        })
        if already_used:
            skipped += 1
            results.append({"email": u.get("email"), "status": "skipped_redeemed"})
            continue

        lang = detect_partner_language(u)
        if lang == "fr":
            subject = PARTNER_FOLLOWUP_EMAIL_SUBJECT_FR
            html = partner_followup_email_html_fr(coupon_code=coupon_code)
        else:
            subject = PARTNER_FOLLOWUP_EMAIL_SUBJECT
            html = partner_followup_email_html(coupon_code=coupon_code)

        try:
            res = await send_callable(
                "new_feature",
                user={
                    "email": u.get("email"),
                    "first_name": u.get("first_name") or u.get("company_name") or u.get("name") or "Partner",
                },
                data={
                    "html_full_override": html,
                    "subject_override": subject,
                },
            )
            if res and res.get("status") in ("sent", "logged"):
                sent += 1
                results.append({"email": u.get("email"), "lang": lang, "status": res.get("status")})
            else:
                results.append({"email": u.get("email"), "lang": lang, "status": "error", "detail": str(res)[:200]})
        except Exception as exc:  # noqa: BLE001
            results.append({"email": u.get("email"), "lang": lang, "status": "error", "detail": str(exc)[:200]})

    # Audit row.
    audit = {
        "id": str(__import__("uuid").uuid4()),
        "ran_at": (now_dt or _dt.now(_tz.utc)).isoformat(),
        "target_signup_day": target_signup_day.isoformat(),
        "matched": len(partners),
        "sent": sent,
        "skipped": skipped,
        "results": results,
    }
    try:
        await db.partner_followup_runs.insert_one(audit)
    except Exception:
        pass
    audit.pop("_id", None)
    return audit
