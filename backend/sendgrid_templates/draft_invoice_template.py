"""
BidVex — Draft Invoice bilingual HTML builder.
Accepts a PricingResult and renders a complete email-ready invoice.
"""

LOGO_URL = "https://cdn.mcauto-images-production.sendgrid.net/4fbf02710175d39f/9dc6a7c3-8237-4a66-b82b-0d9abc165b44/4500x1080.png"
CTA_BASE = "https://bidvex.com"
C = {
    "navy": "#0B2545", "blue": "#2186C6", "sky": "#3FB4CB", "white": "#FFFFFF",
    "light_bg": "#F0F8FF", "text_dark": "#1E293B", "text_med": "#64748B",
    "green": "#059669", "amber": "#F59E0B", "red": "#DC2626", "border": "#E2E8F0",
}
FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"


def _row(label, value, bold=False, color=None):
    vc = f"color:{color};" if color else ""
    fw = "font-weight:bold;" if bold else ""
    return (
        f'<tr>'
        f'<td style="padding:6px 0;font-family:{FONT};font-size:13px;color:{C["text_dark"]};">{label}</td>'
        f'<td style="padding:6px 0;font-family:{FONT};font-size:13px;text-align:right;{fw}{vc}">{value}</td>'
        f'</tr>'
    )


def _sep():
    return f'<tr><td colspan="2" style="border-top:1px solid {C["border"]};height:1px;padding:0;">&nbsp;</td></tr>'


def _section_header(en, fr, color):
    return (
        f'<tr><td colspan="2" style="padding:12px 0 6px;font-family:{FONT};font-size:14px;font-weight:bold;color:{color};">'
        f'{en} <span style="color:{C["text_med"]};font-weight:normal;font-size:12px;">/ {fr}</span></td></tr>'
    )


def _build_side(side, is_buyer=True):
    """Build HTML table from a SideInvoice."""
    rows = ""
    for ln in side.lines:
        if ln.line_type == "hammer":
            rows += _row(ln.description, f"${ln.amount:,.2f}")
        elif ln.line_type == "deduction":
            rows += _row(ln.description, f"-${abs(ln.amount):,.2f}", color=C["red"])
        elif ln.line_type == "fee":
            rows += _row(ln.description, f"${ln.amount:,.2f}")
        elif ln.line_type == "stripe":
            rows += _row(ln.description, f"${ln.amount:,.2f}" if is_buyer else f"-${abs(ln.amount):,.2f}",
                         color=None if is_buyer else C["red"])
        elif ln.line_type == "tax":
            rows += _row(ln.description, f"${ln.amount:,.2f}" if is_buyer else f"-${abs(ln.amount):,.2f}",
                         color=C["amber"])
    rows += _sep()
    if is_buyer:
        rows += _row("TOTAL BUYER CHARGE / TOTAL ACHETEUR", f"${side.total:,.2f}", bold=True, color=C["navy"])
    else:
        rows += _row("NET SELLER PAYOUT / VERSEMENT NET VENDEUR", f"${side.total:,.2f}", bold=True, color=C["green"])

    return f'<table width="100%" cellpadding="0" cellspacing="0">{rows}</table>'


def build_draft_invoice_html(result) -> str:
    """Build complete bilingual draft invoice HTML from a PricingResult."""

    tx_type_en = {
        "vehicle": "Vehicle Auction",
        "non_vehicle_stripe": "Non-Vehicle Auction (Stripe)",
        "non_vehicle_cash": "Non-Vehicle Auction (Cash/E-Transfer)",
        "flat_purchase": "Subscription / Promotion",
    }.get(result.transaction_type, result.transaction_type)

    bi = result.buyer_invoice

    # Buyer card
    buyer_html = _build_side(bi, is_buyer=True)
    buyer_card = (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;">'
        f'<tr><td style="background-color:{C["light_bg"]};border:1px solid {C["sky"]};border-radius:8px;padding:16px;">'
        + _section_header("BUYER CHARGES", "FRAIS ACHETEUR", C["blue"])[0:-1]
        + buyer_html
        + f'</td></tr></table>'
    )

    # Seller card (optional)
    seller_card = ""
    if result.seller_invoice:
        si = result.seller_invoice
        seller_html = _build_side(si, is_buyer=False)
        seller_card = (
            f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;">'
            f'<tr><td style="background-color:#FFF7ED;border:1px solid {C["amber"]};border-radius:8px;padding:16px;">'
            + _section_header("SELLER DEDUCTIONS", "D&Eacute;DUCTIONS VENDEUR", C["red"])[0:-1]
            + seller_html
            + f'</td></tr></table>'
        )
    elif result.transaction_type == "vehicle":
        seller_card = (
            f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;">'
            f'<tr><td style="background-color:#F0FDF4;border:1px solid {C["green"]};border-radius:8px;padding:16px;">'
            f'<p style="font-family:{FONT};font-size:14px;font-weight:bold;color:{C["green"]};margin:0 0 8px;">SELLER / VENDEUR</p>'
            f'<p style="font-family:{FONT};font-size:13px;color:{C["text_dark"]};margin:0;">Seller receives full hammer price (${result.hammer_price:,.2f}) directly from buyer. BidVex charges $0 to the seller for vehicle sales.</p>'
            f'<p style="font-family:{FONT};font-size:13px;color:{C["text_med"]};margin:8px 0 0;">Le vendeur re&ccedil;oit le prix d\'adjudication complet directement de l\'acheteur. BidVex ne facture rien au vendeur pour les ventes de v&eacute;hicules.</p>'
            f'</td></tr></table>'
        )

    # BidVex revenue
    rev_card = (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;">'
        f'<tr><td style="background-color:#F0FDF4;border:1px solid {C["green"]};border-radius:8px;padding:16px;">'
        f'<table width="100%" cellpadding="0" cellspacing="0">'
        + _row("BidVex Gross Revenue / Revenu brut BidVex", f"${result.bidvex_revenue:,.2f}", bold=True, color=C["green"])
        + f'</table></td></tr></table>'
    )

    hp_display = f"${result.hammer_price:,.2f} CAD" if result.hammer_price else "N/A"

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>@media (max-width:600px){{.outer-table{{width:100%!important}}.body-cell{{padding:24px 16px!important}}h1{{font-size:20px!important}}}}</style>
</head><body style="margin:0;padding:0;background-color:#F0F4F8;font-family:{FONT};">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F0F4F8;padding:24px 12px;">
<tr><td align="center">
<table class="outer-table" width="600" cellpadding="0" cellspacing="0" style="background-color:{C['white']};border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);">

<tr><td style="background-color:{C['navy']};padding:24px 0;text-align:center;border-bottom:3px solid {C['sky']};">
<img src="{LOGO_URL}" alt="BidVex" width="150" style="display:inline-block;width:150px;height:auto;" />
</td></tr>

<tr><td style="background-color:{C['navy']};padding:32px 30px;text-align:center;">
<p style="margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:2px;color:{C['sky']};font-family:{FONT};">DRAFT INVOICE / FACTURE PROVISOIRE</p>
<h1 style="margin:0;font-family:{FONT};font-size:24px;font-weight:bold;color:{C['white']};">{tx_type_en} — {hp_display}</h1>
<p style="margin:12px 0 0;font-family:{FONT};font-size:12px;color:rgba(255,255,255,0.5);">Province: {result.province} | Buyer Tier: {result.buyer_tier} | Seller Tier: {result.seller_tier} | Tax: {bi.tax_label}</p>
</td></tr>

<tr><td class="body-cell" style="padding:32px 30px;">

<p style="margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:{C['blue']};font-weight:700;font-family:{FONT};">ENGLISH</p>
<p style="margin:0 0 14px;font-family:{FONT};font-size:15px;line-height:1.6;color:{C['text_dark']};">This is a <strong>draft invoice preview</strong> generated by the BidVex Admin Panel using the Master Pricing Structure. Tax is applied only on BidVex fees, never on the hammer price.</p>

{buyer_card}
{seller_card}
{rev_card}

<table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;"><tr><td style="border-top:2px solid {C['border']};height:1px;font-size:0;line-height:0;">&nbsp;</td></tr></table>

<p style="margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:{C['blue']};font-weight:700;font-family:{FONT};">FRAN&Ccedil;AIS</p>
<p style="margin:0 0 14px;font-family:{FONT};font-size:15px;line-height:1.6;color:{C['text_dark']};">Ceci est un <strong>aper&ccedil;u de facture provisoire</strong> g&eacute;n&eacute;r&eacute; par le panneau d'administration BidVex. La taxe est appliqu&eacute;e uniquement sur les frais BidVex, jamais sur le prix d'adjudication.</p>

<p style="margin:12px 0 0;font-family:{FONT};font-size:12px;color:{C['text_med']};">BidVex Inc. | GST: 706766367RT0001 | QST: 1233530880TQ0001</p>

</td></tr>

<tr><td style="background-color:{C['navy']};padding:28px 30px;text-align:center;">
<img src="{LOGO_URL}" alt="BidVex" width="80" style="display:inline-block;width:80px;height:auto;opacity:0.7;margin-bottom:12px;" /><br/>
<p style="margin:0 0 6px;font-family:{FONT};font-size:12px;color:rgba(255,255,255,0.6);">BidVex Canada | Sherbrooke, QC</p>
<p style="margin:0 0 6px;font-family:{FONT};font-size:12px;color:rgba(255,255,255,0.5);"><a href="mailto:support@bidvex.com" style="color:{C['sky']};text-decoration:none;">support@bidvex.com</a></p>
<p style="margin:0;font-family:{FONT};font-size:11px;color:rgba(255,255,255,0.35);"><a href="{CTA_BASE}/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;">Privacy</a> &nbsp;|&nbsp; <a href="{CTA_BASE}/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;">Terms</a></p>
<p style="margin:8px 0 0;font-family:{FONT};font-size:11px;color:rgba(255,255,255,0.3);">&copy; 2026 BidVex Inc.</p>
</td></tr>

</table></td></tr></table></body></html>"""

    return html
