"""
Generate Draft Invoice bilingual email template for admin test emails.
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


def build_draft_invoice_html(inv) -> str:
    """Build complete bilingual draft invoice HTML from a DraftInvoice dataclass."""
    d = inv.to_template_data()

    # Build buyer tax rows
    buyer_tax_rows = ""
    if inv.buyer_tax_type == "HST":
        buyer_tax_rows = _row(f"HST ({d['buyer_tax_rate']})", d["buyer_hst"])
    elif inv.buyer_tax_type == "GST+QST":
        buyer_tax_rows = _row("GST (5.00%)", d["buyer_gst"]) + _row("QST (9.975%)", d["buyer_qst"])
    elif inv.buyer_tax_type == "GST+PST":
        buyer_tax_rows = _row("GST (5.00%)", d["buyer_gst"]) + _row("PST", d["buyer_pst"])
    else:
        buyer_tax_rows = _row("GST (5.00%)", d["buyer_gst"])

    # Build seller tax rows
    seller_tax_rows = ""
    if inv.seller_tax_type == "HST":
        seller_tax_rows = _row(f"HST ({d['seller_tax_rate']})", d["seller_hst"])
    elif inv.seller_tax_type == "GST+QST":
        seller_tax_rows = _row("GST (5.00%)", d["seller_gst"]) + _row("QST (9.975%)", d["seller_qst"])
    elif inv.seller_tax_type == "GST+PST":
        seller_tax_rows = _row("GST (5.00%)", d["seller_gst"]) + _row("PST", d["seller_pst"])
    else:
        seller_tax_rows = _row("GST (5.00%)", d["seller_gst"])

    buyer_table = (
        f'<table width="100%" cellpadding="0" cellspacing="0">'
        + _section_header("BUYER CHARGES", "FRAIS ACHETEUR", C["blue"])
        + _row("Hammer Price / Prix d'adjudication", d["hammer_price"])
        + _row(f"Buyer Premium / Prime acheteur ({d['buyer_premium_rate']})", d["buyer_premium"])
        + _row(f"Platform Fee / Frais plateforme ({d['buyer_platform_fee']})", d["buyer_platform_fee"])
        + _row("Stripe Processing / Traitement Stripe", d["buyer_stripe_fee"])
        + _sep()
        + _row("Subtotal / Sous-total", d["buyer_subtotal"], bold=True)
        + _section_header(f"TAXES ({inv.buyer_tax_label})", f"TAXES ({inv.buyer_tax_label})", C["amber"])
        + buyer_tax_rows
        + _row("Total Tax / Total taxes", d["buyer_total_tax"], bold=True, color=C["amber"])
        + _sep()
        + _row("TOTAL BUYER PAYS / TOTAL ACHETEUR", d["buyer_total"], bold=True, color=C["navy"])
        + f'</table>'
    )

    seller_table = (
        f'<table width="100%" cellpadding="0" cellspacing="0">'
        + _section_header("SELLER DEDUCTIONS", "D&Eacute;DUCTIONS VENDEUR", C["red"])
        + _row("Hammer Price / Prix d'adjudication", d["hammer_price"])
        + _row(f"Seller Commission ({d['seller_commission_rate']})", f"-{d['seller_commission']}", color=C["red"])
        + _row("Platform Fee / Frais plateforme (2.50%)", f"-{d['seller_platform_fee']}", color=C["red"])
        + _row("Stripe Processing / Traitement Stripe", f"-{d['seller_stripe_fee']}", color=C["red"])
        + _sep()
        + _row("Total Deductions / Total d&eacute;ductions", f"-{d['seller_subtotal_deductions']}", bold=True, color=C["red"])
        + _section_header(f"TAXES ON FEES ({inv.seller_tax_label})", f"TAXES SUR FRAIS ({inv.seller_tax_label})", C["amber"])
        + seller_tax_rows
        + _row("Total Tax / Total taxes", f"-{d['seller_total_tax']}", bold=True, color=C["amber"])
        + _sep()
        + _row("NET SELLER PAYOUT / VERSEMENT NET VENDEUR", d["seller_net_payout"], bold=True, color=C["green"])
        + f'</table>'
    )

    bidvex_summary = (
        f'<table width="100%" cellpadding="0" cellspacing="0" style="margin-top:16px;">'
        + _section_header("BIDVEX REVENUE SUMMARY", "SOMMAIRE REVENUS BIDVEX", C["navy"])
        + _row("BidVex Gross Revenue / Revenu brut", d["bidvex_revenue"], bold=True, color=C["green"])
        + f'</table>'
    )

    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>@media (max-width:600px){{.outer-table{{width:100%!important}}.body-cell{{padding:24px 16px!important}}h1{{font-size:20px!important}}}}</style>
</head><body style="margin:0;padding:0;background-color:#F0F4F8;font-family:{FONT};">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F0F4F8;padding:24px 12px;">
<tr><td align="center">
<table class="outer-table" width="600" cellpadding="0" cellspacing="0" style="background-color:{C['white']};border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);">

<!-- Header -->
<tr><td style="background-color:{C['navy']};padding:24px 0;text-align:center;border-bottom:3px solid {C['sky']};">
<img src="{LOGO_URL}" alt="BidVex" width="150" style="display:inline-block;width:150px;height:auto;" />
</td></tr>

<!-- Hero -->
<tr><td style="background-color:{C['navy']};padding:32px 30px;text-align:center;">
<p style="margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:2px;color:{C['sky']};font-family:{FONT};">DRAFT INVOICE / FACTURE PROVISOIRE</p>
<h1 style="margin:0;font-family:{FONT};font-size:24px;font-weight:bold;color:{C['white']};">Vehicle Auction — ${inv.hammer_price:,.2f} CAD</h1>
<p style="margin:8px 0 0;font-family:{FONT};font-size:16px;color:rgba(255,255,255,0.7);">Ench&egrave;re v&eacute;hicule — {inv.hammer_price:,.2f} $ CAD</p>
<p style="margin:12px 0 0;font-family:{FONT};font-size:12px;color:rgba(255,255,255,0.5);">Province: {inv.buyer_province} | Buyer Tier: {inv.buyer_tier} | Seller Tier: {inv.seller_tier}</p>
</td></tr>

<!-- Body -->
<tr><td class="body-cell" style="padding:32px 30px;">

<!-- EN label -->
<p style="margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:{C['blue']};font-weight:700;font-family:{FONT};">ENGLISH</p>
<p style="margin:0 0 14px;font-family:{FONT};font-size:15px;line-height:1.6;color:{C['text_dark']};">This is a <strong>draft invoice preview</strong> generated by the BidVex Admin Panel. It reflects the current Master Pricing Structure for a Vehicle category auction.</p>

<!-- Buyer Card -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;">
<tr><td style="background-color:{C['light_bg']};border:1px solid {C['sky']};border-radius:8px;padding:16px;">
{buyer_table}
</td></tr></table>

<!-- Seller Card -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;">
<tr><td style="background-color:#FFF7ED;border:1px solid {C['amber']};border-radius:8px;padding:16px;">
{seller_table}
</td></tr></table>

<!-- BidVex Revenue -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;">
<tr><td style="background-color:#F0FDF4;border:1px solid {C['green']};border-radius:8px;padding:16px;">
{bidvex_summary}
</td></tr></table>

<!-- Divider -->
<table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;"><tr><td style="border-top:2px solid {C['border']};height:1px;font-size:0;line-height:0;">&nbsp;</td></tr></table>

<!-- FR label -->
<p style="margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:{C['blue']};font-weight:700;font-family:{FONT};">FRAN&Ccedil;AIS</p>
<p style="margin:0 0 14px;font-family:{FONT};font-size:15px;line-height:1.6;color:{C['text_dark']};">Ceci est un <strong>aper&ccedil;u de facture provisoire</strong> g&eacute;n&eacute;r&eacute; par le panneau d'administration BidVex. Il refl&egrave;te la structure tarifaire ma&icirc;tresse actuelle pour une ench&egrave;re de cat&eacute;gorie V&eacute;hicule.</p>

<p style="margin:12px 0 0;font-family:{FONT};font-size:12px;color:{C['text_med']};">BidVex Inc. | GST: 706766367RT0001 | QST: 1233530880TQ0001</p>
<p style="margin:4px 0 0;font-family:{FONT};font-size:12px;color:{C['text_med']};">BidVex uses AI for support, categorization, and fraud detection. You may request human review at <a href="mailto:privacy@bidvex.com" style="color:{C['blue']};">privacy@bidvex.com</a> (Law 25).</p>

</td></tr>

<!-- Footer -->
<tr><td style="background-color:{C['navy']};padding:28px 30px;text-align:center;">
<img src="{LOGO_URL}" alt="BidVex" width="80" style="display:inline-block;width:80px;height:auto;opacity:0.7;margin-bottom:12px;" /><br/>
<p style="margin:0 0 6px;font-family:{FONT};font-size:12px;color:rgba(255,255,255,0.6);">BidVex Canada | Sherbrooke, QC</p>
<p style="margin:0 0 6px;font-family:{FONT};font-size:12px;color:rgba(255,255,255,0.5);"><a href="mailto:support@bidvex.com" style="color:{C['sky']};text-decoration:none;">support@bidvex.com</a></p>
<p style="margin:0;font-family:{FONT};font-size:11px;color:rgba(255,255,255,0.35);"><a href="{CTA_BASE}/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;">Privacy</a> &nbsp;|&nbsp; <a href="{CTA_BASE}/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;">Terms</a></p>
<p style="margin:8px 0 0;font-family:{FONT};font-size:11px;color:rgba(255,255,255,0.3);">&copy; 2026 BidVex Inc.</p>
</td></tr>

</table></td></tr></table></body></html>"""

    return html
