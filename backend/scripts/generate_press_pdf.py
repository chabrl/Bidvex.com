"""
iter358 — Generate the BidVex Quebec Launch bilingual product PDF.

Produces `/app/frontend/public/static/press/bidvex-quebec-launch.pdf`,
a clean 2-page fiche (Page 1 EN, Page 2 FR) styled in the BidVex palette:
  • Header: dark navy #0B2545 with white BidVex wordmark
  • Body:   clean white background, dark text
  • Accents: BidVex blue #2B8FD0 for bullets + links

Run: `python /app/backend/scripts/generate_press_pdf.py`
This script is idempotent — safe to re-run.
"""
from __future__ import annotations

import os
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak,
    HRFlowable, KeepTogether,
)


# ─── Palette ──────────────────────────────────────────────────────────
NAVY  = colors.HexColor("#0B2545")
BLUE  = colors.HexColor("#2B8FD0")
GREY_DARK  = colors.HexColor("#1E293B")
GREY_MED   = colors.HexColor("#475569")
GREY_LIGHT = colors.HexColor("#E2E8F0")
BG_ACCENT  = colors.HexColor("#F0F9FF")


OUTPUT_PATH = Path("/app/frontend/public/static/press/bidvex-quebec-launch.pdf")
LOGO_PATH   = Path("/app/frontend/public/bidvex-logo-opt.png")


def _make_styles():
    ss = getSampleStyleSheet()
    return {
        "wordmark": ParagraphStyle(
            "wordmark", parent=ss["Normal"],
            fontName="Helvetica-Bold", fontSize=26,
            textColor=colors.white, leading=32,
        ),
        "tagline": ParagraphStyle(
            "tagline", parent=ss["Normal"],
            fontName="Helvetica", fontSize=10,
            textColor=colors.HexColor("#94A3B8"),
            leading=14, spaceBefore=2,
        ),
        "h1": ParagraphStyle(
            "h1", parent=ss["Heading1"],
            fontName="Helvetica-Bold", fontSize=20,
            textColor=NAVY, leading=26,
            spaceBefore=8, spaceAfter=12,
        ),
        "h2": ParagraphStyle(
            "h2", parent=ss["Heading2"],
            fontName="Helvetica-Bold", fontSize=13,
            textColor=BLUE, leading=18,
            spaceBefore=14, spaceAfter=4,
        ),
        "body": ParagraphStyle(
            "body", parent=ss["Normal"],
            fontName="Helvetica", fontSize=10.5,
            textColor=GREY_DARK, leading=15,
            spaceBefore=2, spaceAfter=2,
        ),
        "bullet": ParagraphStyle(
            "bullet", parent=ss["Normal"],
            fontName="Helvetica", fontSize=10.5,
            textColor=GREY_DARK, leading=15,
            leftIndent=14, bulletIndent=2,
            spaceBefore=2, spaceAfter=2,
        ),
        "footer_label": ParagraphStyle(
            "footer_label", parent=ss["Normal"],
            fontName="Helvetica-Bold", fontSize=9,
            textColor=NAVY, leading=12,
        ),
        "footer_body": ParagraphStyle(
            "footer_body", parent=ss["Normal"],
            fontName="Helvetica", fontSize=9,
            textColor=GREY_MED, leading=12,
        ),
        "eyebrow": ParagraphStyle(
            "eyebrow", parent=ss["Normal"],
            fontName="Helvetica-Bold", fontSize=9,
            textColor=BLUE, leading=12,
        ),
    }


def _draw_header(canvas, doc, wordmark_text: str, subtitle_text: str):
    """Dark navy banner across the top of every page."""
    canvas.saveState()
    canvas.setFillColor(NAVY)
    canvas.rect(0, doc.pagesize[1] - 78, doc.pagesize[0], 78, stroke=0, fill=1)
    # Left: BidVex wordmark
    canvas.setFillColor(colors.white)
    canvas.setFont("Helvetica-Bold", 22)
    canvas.drawString(0.55 * inch, doc.pagesize[1] - 40, "BidVex")
    canvas.setFont("Helvetica", 9)
    canvas.setFillColor(colors.HexColor("#94A3B8"))
    canvas.drawString(0.55 * inch, doc.pagesize[1] - 55, subtitle_text)
    # Right: tag/lang label
    canvas.setFont("Helvetica-Bold", 9)
    canvas.setFillColor(BLUE)
    canvas.drawRightString(doc.pagesize[0] - 0.55 * inch, doc.pagesize[1] - 40, wordmark_text)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.HexColor("#CBD5E1"))
    canvas.drawRightString(doc.pagesize[0] - 0.55 * inch, doc.pagesize[1] - 55, "www.bidvex.com")
    canvas.restoreState()


def _draw_footer(canvas, doc):
    canvas.saveState()
    canvas.setStrokeColor(GREY_LIGHT)
    canvas.setLineWidth(0.75)
    canvas.line(0.55 * inch, 0.6 * inch, doc.pagesize[0] - 0.55 * inch, 0.6 * inch)
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY_MED)
    canvas.drawString(0.55 * inch, 0.42 * inch,
                      "BidVex Inc. · 761 Rue Chalifoux, Sherbrooke (Québec) J1G 0A8 · Corp. no 1175252826")
    canvas.setFont("Helvetica-Bold", 8)
    canvas.setFillColor(BLUE)
    canvas.drawRightString(doc.pagesize[0] - 0.55 * inch, 0.42 * inch,
                           "marketing@bidvex.com · +1 (450) 634-3099")
    canvas.restoreState()


def _en_page(styles):
    """Build EN page flowables."""
    flow = []
    flow.append(Spacer(1, 0.35 * inch))  # push below header banner
    flow.append(Paragraph("PRODUCT OVERVIEW · JULY 2026", styles["eyebrow"]))
    flow.append(Spacer(1, 4))
    flow.append(Paragraph("BidVex Inc. — Product Overview", styles["h1"]))
    flow.append(Paragraph(
        "<b>Canada's Bilingual Online Auction Marketplace</b>", styles["body"]))
    flow.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceBefore=8, spaceAfter=10))

    flow.append(Paragraph("Four Verticals — One Account", styles["h2"]))
    flow.append(Paragraph(
        "General Marketplace &nbsp;·&nbsp; Lots &amp; Liquidation &nbsp;·&nbsp; "
        "Vehicle Auctions &nbsp;·&nbsp; Storage Auctions",
        styles["body"]))

    flow.append(Paragraph("Platform Fee", styles["h2"]))
    flow.append(Paragraph(
        "<b>2.5% only</b> — versus 10–15% at traditional auction houses. "
        "Transparent, disclosed at listing time, and permanent (not a launch promotion).",
        styles["body"]))

    flow.append(Paragraph("Technology", styles["h2"]))
    for line in [
        "• AI-powered fraud detection on every listing",
        "• Soft-close anti-snipe protection (60-second bid extensions)",
        "• Stripe escrow for non-vehicle items",
        "• Real-time WebSocket bidding (sub-100ms latency)",
        "• Stripe Identity KYC verification for winners",
    ]:
        flow.append(Paragraph(line, styles["bullet"]))

    flow.append(Paragraph("Compliance", styles["h2"]))
    for line in [
        "• Fully bilingual EN/FR — compliant with Bill 96 (Loi 96)",
        "• SAAQ / OMVIC / AMVIC / VSA verified vehicle dealers",
        "• PIPEDA and Quebec Law 25 data governance",
        "• Canadian corporation (Corp. no 1175252826)",
    ]:
        flow.append(Paragraph(line, styles["bullet"]))

    flow.append(Paragraph("Coverage", styles["h2"]))
    flow.append(Paragraph(
        "All 10 Canadian provinces. Deep local coverage in Quebec: Montréal, Québec City, "
        "Sherbrooke, Laval, Gatineau, Saguenay, Trois-Rivières, Longueuil.",
        styles["body"]))

    flow.append(Spacer(1, 10))
    launch_box = Table(
        [[Paragraph(
            "<b>Launch Offer — SUMMER2026</b><br/>"
            "First month of Premium listing features free of charge. "
            "Valid through August 31, 2026.",
            ParagraphStyle("launch", fontName="Helvetica", fontSize=10.5,
                           textColor=colors.HexColor("#0C4A6E"), leading=14),
        )]],
        colWidths=[6.7 * inch],
    )
    launch_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG_ACCENT),
        ("BOX",        (0, 0), (-1, -1), 1, BLUE),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING",   (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
    ]))
    flow.append(launch_box)

    flow.append(Spacer(1, 14))
    flow.append(Paragraph("Contact", styles["h2"]))
    flow.append(Paragraph(
        "<b>marketing@bidvex.com</b> &nbsp;·&nbsp; +1 (450) 634-3099 &nbsp;·&nbsp; "
        "www.bidvex.com<br/>"
        "BidVex Inc. — 761 Rue Chalifoux, Sherbrooke (Québec) J1G 0A8 — Corp. no 1175252826",
        styles["body"]))

    return flow


def _fr_page(styles):
    """Build FR page flowables."""
    flow = []
    flow.append(Spacer(1, 0.35 * inch))
    flow.append(Paragraph("APERÇU DE LA PLATEFORME · JUILLET 2026", styles["eyebrow"]))
    flow.append(Spacer(1, 4))
    flow.append(Paragraph("BidVex Inc. — Aperçu de la plateforme", styles["h1"]))
    flow.append(Paragraph(
        "<b>La plateforme d'enchères en ligne bilingue du Canada</b>", styles["body"]))
    flow.append(HRFlowable(width="100%", thickness=1, color=BLUE, spaceBefore=8, spaceAfter=10))

    flow.append(Paragraph("Quatre verticales — un seul compte", styles["h2"]))
    flow.append(Paragraph(
        "Marketplace générale &nbsp;·&nbsp; Lots et liquidation &nbsp;·&nbsp; "
        "Enchères de véhicules &nbsp;·&nbsp; Enchères d'entreposage",
        styles["body"]))

    flow.append(Paragraph("Frais de plateforme", styles["h2"]))
    flow.append(Paragraph(
        "<b>2,5 % seulement</b> — contre 10 à 15 % chez les maisons d'enchères "
        "traditionnelles. Transparents, divulgués dès la mise en ligne et permanents "
        "(non pas une promotion de lancement).",
        styles["body"]))

    flow.append(Paragraph("Technologie", styles["h2"]))
    for line in [
        "• Détection de fraude par IA sur chaque annonce",
        "• Fermeture progressive anti-snipe (prolongations de 60 secondes)",
        "• Séquestre Stripe pour les articles non-véhicules",
        "• Enchères en temps réel par WebSocket (latence &lt; 100 ms)",
        "• Vérification d'identité Stripe Identity KYC pour les gagnants",
    ]:
        flow.append(Paragraph(line, styles["bullet"]))

    flow.append(Paragraph("Conformité", styles["h2"]))
    for line in [
        "• Entièrement bilingue FR/EN — conforme à la Loi 96",
        "• Concessionnaires vérifiés SAAQ / OMVIC / AMVIC / VSA",
        "• Gouvernance des données selon la LPRPDE et la Loi 25 du Québec",
        "• Société canadienne (numéro de corporation 1175252826)",
    ]:
        flow.append(Paragraph(line, styles["bullet"]))

    flow.append(Paragraph("Couverture", styles["h2"]))
    flow.append(Paragraph(
        "Les 10 provinces canadiennes. Couverture locale approfondie au Québec : "
        "Montréal, Québec, Sherbrooke, Laval, Gatineau, Saguenay, Trois-Rivières, Longueuil.",
        styles["body"]))

    flow.append(Spacer(1, 10))
    launch_box = Table(
        [[Paragraph(
            "<b>Offre de lancement — SUMMER2026</b><br/>"
            "Premier mois d'inscription Premium gratuit. "
            "Valable jusqu'au 31 août 2026.",
            ParagraphStyle("launch_fr", fontName="Helvetica", fontSize=10.5,
                           textColor=colors.HexColor("#0C4A6E"), leading=14),
        )]],
        colWidths=[6.7 * inch],
    )
    launch_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BG_ACCENT),
        ("BOX",        (0, 0), (-1, -1), 1, BLUE),
        ("LEFTPADDING",  (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING",   (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 10),
    ]))
    flow.append(launch_box)

    flow.append(Spacer(1, 14))
    flow.append(Paragraph("Contact", styles["h2"]))
    flow.append(Paragraph(
        "<b>marketing@bidvex.com</b> &nbsp;·&nbsp; +1 (450) 634-3099 &nbsp;·&nbsp; "
        "www.bidvex.com<br/>"
        "BidVex Inc. — 761 Rue Chalifoux, Sherbrooke (Québec) J1G 0A8 — Numéro de corporation 1175252826",
        styles["body"]))

    return flow


def build_pdf():
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    styles = _make_styles()

    doc = SimpleDocTemplate(
        str(OUTPUT_PATH),
        pagesize=LETTER,
        leftMargin=0.55 * inch, rightMargin=0.55 * inch,
        topMargin=1.15 * inch, bottomMargin=0.8 * inch,
        title="BidVex Inc. — Product Overview",
        author="BidVex Inc.",
        subject="Canada's Bilingual Online Auction Marketplace — Product Overview",
        creator="BidVex press pipeline (iter358)",
    )

    # Page-tracking flag: page 1 = EN, page 2 = FR
    state = {"lang": "EN"}

    def _on_first_page(canvas, doc):
        _draw_header(canvas, doc,
                     wordmark_text="ENGLISH · EN",
                     subtitle_text="Canada's Bilingual Online Auction Marketplace")
        _draw_footer(canvas, doc)

    def _on_later_pages(canvas, doc):
        _draw_header(canvas, doc,
                     wordmark_text="FRANÇAIS · FR",
                     subtitle_text="La marketplace d'enchères en ligne bilingue du Canada")
        _draw_footer(canvas, doc)

    story = _en_page(styles) + [PageBreak()] + _fr_page(styles)
    doc.build(story, onFirstPage=_on_first_page, onLaterPages=_on_later_pages)

    size = OUTPUT_PATH.stat().st_size
    print(f"[iter358] PDF generated: {OUTPUT_PATH} ({size:,} bytes)")
    return OUTPUT_PATH


if __name__ == "__main__":
    build_pdf()
