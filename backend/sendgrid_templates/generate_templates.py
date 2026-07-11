"""
BidVex SendGrid Dynamic Template Generator
Generates all 20 HTML templates following the Part 2 Design System.
Run: python generate_templates.py
Output: One .html file per template in this directory.
"""

LOGO_URL = "http://cdn.mcauto-images-production.sendgrid.net/4fbf02710175d39f/9dc6a7c3-8237-4a66-b82b-0d9abc165b44/4500x1080.png"
LOGO_FOOTER_URL = LOGO_URL
CTA_BASE = "https://bidvex.com"

# Brand colors
C = {
    "navy": "#0B2545",
    "blue": "#2186C6",
    "sky": "#3FB4CB",
    "white": "#FFFFFF",
    "light_bg": "#F0F8FF",
    "text_dark": "#1E293B",
    "text_med": "#64748B",
    "green": "#059669",
    "amber": "#F59E0B",
    "red": "#DC2626",
    "border": "#E2E8F0",
}

FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"


def zone1_header():
    return f"""
    <!-- ZONE 1 — Header -->
    <tr>
      <td style="background-color:{C['navy']};padding:24px 0;text-align:center;border-bottom:3px solid {C['sky']};">
        <img src="{LOGO_URL}" alt="BidVex" width="150" style="display:inline-block;width:150px;height:auto;" />
      </td>
    </tr>"""


def zone2_hero(color, icon, headline):
    return f"""
    <!-- ZONE 2 — Hero -->
    <tr>
      <td style="background-color:{color};padding:32px 30px;text-align:center;">
        <p style="margin:0 0 8px;font-size:48px;line-height:1;">{icon}</p>
        <h1 style="margin:0;font-family:{FONT};font-size:24px;font-weight:bold;color:{C['white']};">{headline}</h1>
      </td>
    </tr>"""


def zone4_cta(label, url):
    return f"""
    <!-- ZONE 4 — CTA -->
    <tr>
      <td style="padding:8px 30px 32px;text-align:center;">
        <table cellpadding="0" cellspacing="0" align="center"><tr>
          <td style="background-color:{C['blue']};border-radius:8px;padding:14px 32px;">
            <a href="{url}" style="color:{C['white']};font-family:{FONT};font-size:15px;font-weight:bold;text-decoration:none;display:inline-block;" target="_blank" clicktracking=off>{label}</a>
          </td>
        </tr></table>
      </td>
    </tr>"""


def zone5_footer():
    return f"""
    <!-- ZONE 5 — Footer -->
    <tr>
      <td style="background-color:{C['navy']};padding:28px 30px;text-align:center;">
        <img src="{LOGO_FOOTER_URL}" alt="BidVex" width="80" style="display:inline-block;width:80px;height:auto;opacity:0.7;margin-bottom:12px;" /><br/>
        <p style="margin:0 0 6px;font-family:{FONT};font-size:12px;color:rgba(255,255,255,0.6);">BidVex Canada | Sherbrooke, QC</p>
        <p style="margin:0 0 6px;font-family:{FONT};font-size:12px;color:rgba(255,255,255,0.5);">
          <a href="mailto:service@bidvex.com" style="color:{C['sky']};text-decoration:none;" clicktracking=off>service@bidvex.com</a>
        </p>
        <p style="margin:0;font-family:{FONT};font-size:11px;color:rgba(255,255,255,0.35);">
          <a href="{CTA_BASE}/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;" clicktracking=off>Privacy</a> &nbsp;|&nbsp;
          <a href="{CTA_BASE}/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;" clicktracking=off>Terms</a> &nbsp;|&nbsp;
          <a href="{{{{unsubscribe_url}}}}" style="color:rgba(255,255,255,0.45);text-decoration:underline;" clicktracking=off>Unsubscribe</a>
        </p>
        <p style="margin:8px 0 0;font-family:{FONT};font-size:11px;color:rgba(255,255,255,0.3);">&copy; {{{{current_year}}}} BidVex Inc.</p>
      </td>
    </tr>"""


def data_card(content_html):
    return f"""
        <table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;"><tr>
          <td style="background-color:{C['light_bg']};border:1px solid {C['sky']};border-radius:8px;padding:16px;">
            {content_html}
          </td>
        </tr></table>"""


def badge(text, bg_color):
    return f'<span style="display:inline-block;background-color:{bg_color};color:{C["white"]};font-family:{FONT};font-size:11px;font-weight:bold;padding:4px 10px;border-radius:4px;text-transform:uppercase;letter-spacing:1px;">{text}</span>'


def wrap(body_rows):
    return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    @media (max-width: 600px) {{
      .outer-table {{ width: 100% !important; }}
      .body-cell {{ padding: 24px 16px !important; }}
      .two-col td {{ display: block !important; width: 100% !important; padding: 8px 0 !important; }}
      h1 {{ font-size: 20px !important; }}
      .cta-btn {{ padding: 16px 24px !important; font-size: 16px !important; }}
    }}
  </style>
</head>
<body style="margin:0;padding:0;background-color:#F0F4F8;font-family:{FONT};">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F0F4F8;padding:24px 12px;">
<tr><td align="center">
<table class="outer-table" width="600" cellpadding="0" cellspacing="0" style="background-color:{C['white']};border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);">
{body_rows}
</table>
</td></tr>
</table>
</body>
</html>"""


def body_zone(html):
    return f"""
    <!-- ZONE 3 — Body -->
    <tr>
      <td class="body-cell" style="padding:32px 30px;">
        {html}
      </td>
    </tr>"""


def icon_row(items):
    """items = [(icon, title, desc), ...]"""
    cols = ""
    for icon, title, desc in items:
        cols += f"""
          <td valign="top" style="padding:8px;">
            <table cellpadding="0" cellspacing="0" style="background-color:{C['light_bg']};border:1px solid {C['sky']};border-radius:8px;padding:16px;width:100%;">
              <tr><td style="font-size:28px;padding-bottom:8px;">{icon}</td></tr>
              <tr><td style="font-family:{FONT};font-size:13px;font-weight:bold;color:{C['navy']};padding-bottom:4px;">{title}</td></tr>
              <tr><td style="font-family:{FONT};font-size:12px;color:{C['text_med']};line-height:1.5;">{desc}</td></tr>
            </table>
          </td>"""
    return f'<table class="two-col" width="100%" cellpadding="0" cellspacing="0"><tr>{cols}</tr></table>'


def p(text, bold=False):
    w = "font-weight:bold;" if bold else ""
    return f'<p style="margin:0 0 14px;font-family:{FONT};font-size:15px;line-height:1.6;color:{C["text_dark"]};{w}">{text}</p>'


# ════════════════════════════════════════════════════════════
# TEMPLATE DEFINITIONS
# ════════════════════════════════════════════════════════════

TEMPLATES = []

# 1. Welcome
TEMPLATES.append(("01_welcome_en", wrap(
    zone1_header() +
    zone2_hero(C["navy"], "&#127881;", "Welcome to BidVex, {{first_name}}!") +
    body_zone(
        p("You've just joined North America's most advanced all-in-one auction marketplace. Whether you're looking for a fleet of trucks, a single rare collectible, or liquidating an entire warehouse of industrial equipment — BidVex is built to handle it all.") +
        icon_row([
            ("&#128722;", "All-In-One Marketplace", "From vehicles and heavy machinery to multi-item lots."),
            ("&#129302;", "AI-Powered Tools", "Our intelligent concierge is ready to help you 24/7."),
        ]) +
        '<div style="height:8px;"></div>' +
        icon_row([
            ("&#127760;", "Bilingual &amp; Cross-Border", "Seamlessly buy or sell across Canada and the US."),
            ("&#128274;", "Secure &amp; Compliant", "Province-verified dealer sellers, Law 25 compliant, Stripe payments."),
        ]) +
        '<div style="height:8px;"></div>' +
        p("Your account is ready. Start exploring the marketplace today.") +
        '<p style="margin:12px 0 0;font-family:' + FONT + ';font-size:12px;color:' + C["text_med"] + ';">BidVex uses AI for support, categorization, and fraud detection. You may request human review of any AI decision at <a href="mailto:privacy@bidvex.com" style="color:' + C["blue"] + ';" clicktracking=off>privacy@bidvex.com</a> (Law 25).</p>'
    ) +
    zone4_cta("Explore the Marketplace", f"{CTA_BASE}/marketplace") +
    zone5_footer()
)))

TEMPLATES.append(("01_welcome_fr", wrap(
    zone1_header() +
    zone2_hero(C["navy"], "&#127881;", "Bienvenue chez BidVex, {{first_name}} !") +
    body_zone(
        p("Vous venez de rejoindre la plateforme « tout-en-un » la plus avancée en Amérique du Nord. Que vous cherchiez une flotte de camions, une pièce de collection unique ou que vous souhaitiez liquider un entrepôt complet d'équipement industriel — BidVex est conçu pour tout gérer.") +
        icon_row([
            ("&#128722;", "Marché tout-en-un", "Des véhicules et de la machinerie lourde aux lots d'articles multiples."),
            ("&#129302;", "Outils propulsés par l'IA", "Notre concierge intelligent est prêt à vous aider 24/7."),
        ]) +
        '<div style="height:8px;"></div>' +
        icon_row([
            ("&#127760;", "Bilingue et transfrontalier", "Achetez ou vendez partout au Canada et aux États-Unis."),
            ("&#128274;", "Sécurisé et conforme", "Vendeurs concessionnaires vérifiés par province, conforme Loi 25, paiements Stripe."),
        ]) +
        '<div style="height:8px;"></div>' +
        p("Votre compte est prêt. Commencez à explorer le marché dès aujourd'hui.") +
        '<p style="margin:12px 0 0;font-family:' + FONT + ';font-size:12px;color:' + C["text_med"] + ';">BidVex utilise l\'IA pour le support, la catégorisation et la détection de fraude. Vous pouvez demander une révision humaine à <a href="mailto:privacy@bidvex.com" style="color:' + C["blue"] + ';" clicktracking=off>privacy@bidvex.com</a> (Loi 25).</p>'
    ) +
    zone4_cta("Explorer le marché", f"{CTA_BASE}/marketplace") +
    zone5_footer()
)))

# 2. Onboarding Day 3
TEMPLATES.append(("02_onboarding_day3_en", wrap(
    zone1_header() +
    zone2_hero(C["blue"], "&#128296;", "Have You Placed Your First Bid?") +
    body_zone(
        p(f"Hi {{{{first_name}}}},") +
        p("It's been 3 days since you joined BidVex. There are live auctions happening right now near you — don't miss out!") +
        f'{badge("LIVE AUCTIONS", C["green"])}' +
        data_card(
            f'<p style="font-family:{FONT};font-size:14px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">Auctions Near You</p>' +
            f'<p style="font-family:{FONT};font-size:13px;color:{C["text_dark"]};margin:0;line-height:1.6;">We found active auctions within 50 km of your location. Browse them now and place your first bid.</p>'
        ) +
        p("Bidding on BidVex is simple: find an item, set your maximum, and our system bids for you up to that amount. If you win, you'll be notified instantly.")
    ) +
    zone4_cta("Browse Live Auctions", f"{CTA_BASE}/marketplace") +
    zone5_footer()
)))

TEMPLATES.append(("02_onboarding_day3_fr", wrap(
    zone1_header() +
    zone2_hero(C["blue"], "&#128296;", "Avez-vous placé votre première enchère ?") +
    body_zone(
        p(f"Bonjour {{{{first_name}}}},") +
        p("Cela fait 3 jours que vous avez rejoint BidVex. Des enchères en direct se déroulent en ce moment près de chez vous — ne les manquez pas !") +
        f'{badge("ENCHÈRES EN DIRECT", C["green"])}' +
        data_card(
            f'<p style="font-family:{FONT};font-size:14px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">Enchères près de chez vous</p>' +
            f'<p style="font-family:{FONT};font-size:13px;color:{C["text_dark"]};margin:0;line-height:1.6;">Nous avons trouvé des enchères actives à moins de 50 km. Parcourez-les et placez votre première enchère.</p>'
        ) +
        p("Enchérir sur BidVex est simple : trouvez un article, définissez votre maximum, et notre système enchérit pour vous jusqu'à ce montant. Si vous gagnez, vous serez notifié instantanément.")
    ) +
    zone4_cta("Parcourir les enchères", f"{CTA_BASE}/marketplace") +
    zone5_footer()
)))

# 3. Onboarding Week 1
TEMPLATES.append(("03_onboarding_week1_en", wrap(
    zone1_header() +
    zone2_hero(C["blue"], "&#128218;", "Your BidVex Quick-Start Guide") +
    body_zone(
        p(f"Hi {{{{first_name}}}},") +
        p("Here's everything you need to know to get the most out of BidVex in your first week.") +
        icon_row([
            ("&#128269;", "Find &amp; Bid", "Browse categories, set price alerts, and bid on items you love."),
            ("&#128176;", "Sell &amp; Earn", "List your items for auction — from a single tool to an entire warehouse."),
        ]) +
        '<div style="height:8px;"></div>' +
        icon_row([
            ("&#128202;", "Seller Dashboard", "Track your listings, invoices, and payouts in real time."),
            ("&#11088;", "Go Pro", "Upgrade your plan for premium features, lower fees, and priority support."),
        ]) +
        '<div style="height:12px;"></div>' +
        data_card(
            f'<p style="font-family:{FONT};font-size:14px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">Subscription Plans</p>' +
            f'<table width="100%" cellpadding="0" cellspacing="0" style="font-family:{FONT};font-size:12px;color:{C["text_dark"]};">' +
            f'<tr><td style="padding:4px 0;font-weight:bold;">Free</td><td style="padding:4px 0;">Browse &amp; bid, basic alerts</td></tr>' +
            f'<tr><td style="padding:4px 0;font-weight:bold;">Pro</td><td style="padding:4px 0;">Lower fees, advanced analytics, priority support</td></tr>' +
            f'<tr><td style="padding:4px 0;font-weight:bold;">Business</td><td style="padding:4px 0;">Unlimited listings, bulk tools, API access</td></tr>' +
            f'</table>'
        )
    ) +
    zone4_cta("Explore Plans", f"{CTA_BASE}/pricing") +
    zone5_footer()
)))

TEMPLATES.append(("03_onboarding_week1_fr", wrap(
    zone1_header() +
    zone2_hero(C["blue"], "&#128218;", "Votre guide de démarrage BidVex") +
    body_zone(
        p(f"Bonjour {{{{first_name}}}},") +
        p("Voici tout ce que vous devez savoir pour tirer le meilleur parti de BidVex dès votre première semaine.") +
        icon_row([
            ("&#128269;", "Trouver et enchérir", "Parcourez les catégories, définissez des alertes de prix et enchérissez."),
            ("&#128176;", "Vendre et gagner", "Listez vos articles aux enchères — d'un seul outil à un entrepôt entier."),
        ]) +
        '<div style="height:8px;"></div>' +
        icon_row([
            ("&#128202;", "Tableau de bord vendeur", "Suivez vos annonces, factures et paiements en temps réel."),
            ("&#11088;", "Passez Pro", "Améliorez votre plan pour des fonctionnalités premium et des frais réduits."),
        ]) +
        '<div style="height:12px;"></div>' +
        data_card(
            f'<p style="font-family:{FONT};font-size:14px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">Plans d\'abonnement</p>' +
            f'<table width="100%" cellpadding="0" cellspacing="0" style="font-family:{FONT};font-size:12px;color:{C["text_dark"]};">' +
            f'<tr><td style="padding:4px 0;font-weight:bold;">Gratuit</td><td style="padding:4px 0;">Parcourir et enchérir, alertes de base</td></tr>' +
            f'<tr><td style="padding:4px 0;font-weight:bold;">Pro</td><td style="padding:4px 0;">Frais réduits, analyses avancées, support prioritaire</td></tr>' +
            f'<tr><td style="padding:4px 0;font-weight:bold;">Business</td><td style="padding:4px 0;">Annonces illimitées, outils en lot, accès API</td></tr>' +
            f'</table>'
        )
    ) +
    zone4_cta("Explorer les plans", f"{CTA_BASE}/pricing") +
    zone5_footer()
)))

# 4. Subscription Pitch (Day 14)
TEMPLATES.append(("04_subscription_pitch_en", wrap(
    zone1_header() +
    zone2_hero(C["navy"], "&#128640;", "Unlock the Full BidVex Experience") +
    body_zone(
        p(f"Hi {{{{first_name}}}},") +
        p("You've been on BidVex for 2 weeks now. Ready to take it to the next level? Upgrade today and get <strong>20% off your first year</strong> with your exclusive welcome code.") +
        data_card(
            f'<p style="font-family:{FONT};font-size:12px;color:{C["text_med"]};margin:0 0 4px;text-transform:uppercase;letter-spacing:1px;">Your Exclusive Code</p>' +
            f'<p style="font-family:{FONT};font-size:28px;font-weight:bold;color:{C["blue"]};margin:0;letter-spacing:2px;">{{{{coupon_code}}}}</p>' +
            f'<p style="font-family:{FONT};font-size:12px;color:{C["red"]};margin:6px 0 0;font-weight:bold;">Offer expires in 48 hours</p>'
        ) +
        icon_row([
            ("&#9989;", "Lower Fees", "Save on every transaction with reduced platform fees."),
            ("&#128200;", "Advanced Analytics", "Real-time dashboards, bid history, and market insights."),
        ]) +
        '<div style="height:8px;"></div>' +
        icon_row([
            ("&#128172;", "Priority Support", "Dedicated support queue — responses within 2 hours."),
            ("&#9889;", "Bulk Tools", "Multi-item listing, CSV import, and inventory management."),
        ])
    ) +
    zone4_cta("Upgrade Now — 20% Off", f"{CTA_BASE}/pricing") +
    zone5_footer()
)))

TEMPLATES.append(("04_subscription_pitch_fr", wrap(
    zone1_header() +
    zone2_hero(C["navy"], "&#128640;", "Débloquez l'expérience BidVex complète") +
    body_zone(
        p(f"Bonjour {{{{first_name}}}},") +
        p("Vous êtes sur BidVex depuis 2 semaines. Prêt à passer au niveau supérieur ? Améliorez votre plan aujourd'hui et obtenez <strong>20 % de réduction sur votre première année</strong> avec votre code exclusif.") +
        data_card(
            f'<p style="font-family:{FONT};font-size:12px;color:{C["text_med"]};margin:0 0 4px;text-transform:uppercase;letter-spacing:1px;">Votre code exclusif</p>' +
            f'<p style="font-family:{FONT};font-size:28px;font-weight:bold;color:{C["blue"]};margin:0;letter-spacing:2px;">{{{{coupon_code}}}}</p>' +
            f'<p style="font-family:{FONT};font-size:12px;color:{C["red"]};margin:6px 0 0;font-weight:bold;">L\'offre expire dans 48 heures</p>'
        ) +
        icon_row([
            ("&#9989;", "Frais réduits", "Économisez sur chaque transaction avec des frais réduits."),
            ("&#128200;", "Analyses avancées", "Tableaux de bord en temps réel, historique d'enchères et insights."),
        ]) +
        '<div style="height:8px;"></div>' +
        icon_row([
            ("&#128172;", "Support prioritaire", "File d'attente dédiée — réponses en moins de 2 heures."),
            ("&#9889;", "Outils en lot", "Annonces multiples, import CSV et gestion d'inventaire."),
        ])
    ) +
    zone4_cta("Améliorer — 20 % de rabais", f"{CTA_BASE}/pricing") +
    zone5_footer()
)))

# 5. Re-engagement (Day 30)
TEMPLATES.append(("05_reengagement_en", wrap(
    zone1_header() +
    zone2_hero(C["sky"], "&#128075;", "We Miss You, {{first_name}}!") +
    body_zone(
        p("It's been a while since you last visited BidVex. A lot has happened — new listings, new sellers, and auctions ending soon near you.") +
        f'{badge("NEW THIS WEEK", C["blue"])}' +
        data_card(
            f'<p style="font-family:{FONT};font-size:14px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">Featured Auctions Near You</p>' +
            f'<p style="font-family:{FONT};font-size:13px;color:{C["text_dark"]};margin:0;line-height:1.6;">We\'ve curated active auctions within your area. Don\'t let them close without you.</p>'
        ) +
        p("Your account is still fully active and ready to go. Jump back in today.")
    ) +
    zone4_cta("Browse What's New", f"{CTA_BASE}/marketplace") +
    zone5_footer()
)))

TEMPLATES.append(("05_reengagement_fr", wrap(
    zone1_header() +
    zone2_hero(C["sky"], "&#128075;", "Vous nous manquez, {{first_name}} !") +
    body_zone(
        p("Cela fait un moment que vous n'avez pas visité BidVex. Beaucoup de choses se sont passées — nouvelles annonces, nouveaux vendeurs et des enchères se terminant bientôt près de chez vous.") +
        f'{badge("NOUVEAU CETTE SEMAINE", C["blue"])}' +
        data_card(
            f'<p style="font-family:{FONT};font-size:14px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">Enchères vedettes près de chez vous</p>' +
            f'<p style="font-family:{FONT};font-size:13px;color:{C["text_dark"]};margin:0;line-height:1.6;">Nous avons sélectionné des enchères actives dans votre région. Ne les laissez pas se terminer sans vous.</p>'
        ) +
        p("Votre compte est toujours actif et prêt. Revenez dès aujourd'hui.")
    ) +
    zone4_cta("Découvrir les nouveautés", f"{CTA_BASE}/marketplace") +
    zone5_footer()
)))

# 6. Re-engagement Final (Day 45)
TEMPLATES.append(("06_reengagement_final_en", wrap(
    zone1_header() +
    zone2_hero(C["amber"], "&#9200;", "Last Chance — Come Back &amp; Save") +
    body_zone(
        p(f"Hi {{{{first_name}}}},") +
        p("We haven't seen you in 45 days. As a welcome-back gesture, here's an exclusive <strong>15% discount</strong> on any BidVex subscription.") +
        data_card(
            f'<p style="font-family:{FONT};font-size:12px;color:{C["text_med"]};margin:0 0 4px;text-transform:uppercase;letter-spacing:1px;">Your Come-Back Code</p>' +
            f'<p style="font-family:{FONT};font-size:28px;font-weight:bold;color:{C["amber"]};margin:0;letter-spacing:2px;">{{{{coupon_code}}}}</p>' +
            f'<p style="font-family:{FONT};font-size:12px;color:{C["red"]};margin:6px 0 0;font-weight:bold;">This is your final reminder</p>'
        ) +
        p("Auctions are closing daily. Sellers are listing equipment, vehicles, and rare items every hour. Don't miss out.")
    ) +
    zone4_cta("Reactivate &amp; Save 15%", f"{CTA_BASE}/pricing") +
    zone5_footer()
)))

TEMPLATES.append(("06_reengagement_final_fr", wrap(
    zone1_header() +
    zone2_hero(C["amber"], "&#9200;", "Dernière chance — Revenez et économisez") +
    body_zone(
        p(f"Bonjour {{{{first_name}}}},") +
        p("Nous ne vous avons pas vu depuis 45 jours. En guise de bienvenue, voici une <strong>réduction exclusive de 15 %</strong> sur tout abonnement BidVex.") +
        data_card(
            f'<p style="font-family:{FONT};font-size:12px;color:{C["text_med"]};margin:0 0 4px;text-transform:uppercase;letter-spacing:1px;">Votre code de retour</p>' +
            f'<p style="font-family:{FONT};font-size:28px;font-weight:bold;color:{C["amber"]};margin:0;letter-spacing:2px;">{{{{coupon_code}}}}</p>' +
            f'<p style="font-family:{FONT};font-size:12px;color:{C["red"]};margin:6px 0 0;font-weight:bold;">Ceci est votre dernier rappel</p>'
        ) +
        p("Des enchères se terminent chaque jour. Des vendeurs listent des équipements, véhicules et articles rares à chaque heure. Ne manquez rien.")
    ) +
    zone4_cta("Réactiver et économiser 15 %", f"{CTA_BASE}/pricing") +
    zone5_footer()
)))

# 7. Subscription Final Reminder
TEMPLATES.append(("07_subscription_final_reminder_en", wrap(
    zone1_header() +
    zone2_hero(C["red"], "&#128274;", "Your Subscription Expires Tomorrow") +
    body_zone(
        p(f"Hi {{{{first_name}}}},") +
        p("Your <strong>{{{{plan_name}}}}</strong> subscription expires <strong>tomorrow</strong>. After that, you'll lose access to premium features including lower fees, analytics, and priority support.") +
        data_card(
            f'<table width="100%" cellpadding="0" cellspacing="0" style="font-family:{FONT};font-size:14px;color:{C["text_dark"]};">' +
            f'<tr><td style="padding:4px 0;color:{C["text_med"]};">Current Plan</td><td style="padding:4px 0;font-weight:bold;text-align:right;">{{{{plan_name}}}}</td></tr>' +
            f'<tr><td style="padding:4px 0;color:{C["text_med"]};">Expires</td><td style="padding:4px 0;font-weight:bold;text-align:right;color:{C["red"]};">{{{{expiry_date}}}}</td></tr>' +
            f'<tr><td style="padding:4px 0;color:{C["text_med"]};">Renewal Price</td><td style="padding:4px 0;font-weight:bold;text-align:right;">{{{{renewal_price}}}}</td></tr>' +
            f'</table>'
        ) +
        p("Renew now to keep your benefits without interruption.")
    ) +
    zone4_cta("Renew My Plan", f"{CTA_BASE}/pricing") +
    zone5_footer()
)))

TEMPLATES.append(("07_subscription_final_reminder_fr", wrap(
    zone1_header() +
    zone2_hero(C["red"], "&#128274;", "Votre abonnement expire demain") +
    body_zone(
        p(f"Bonjour {{{{first_name}}}},") +
        p("Votre abonnement <strong>{{{{plan_name}}}}</strong> expire <strong>demain</strong>. Après cela, vous perdrez l'accès aux fonctionnalités premium incluant les frais réduits, les analyses et le support prioritaire.") +
        data_card(
            f'<table width="100%" cellpadding="0" cellspacing="0" style="font-family:{FONT};font-size:14px;color:{C["text_dark"]};">' +
            f'<tr><td style="padding:4px 0;color:{C["text_med"]};">Plan actuel</td><td style="padding:4px 0;font-weight:bold;text-align:right;">{{{{plan_name}}}}</td></tr>' +
            f'<tr><td style="padding:4px 0;color:{C["text_med"]};">Expire le</td><td style="padding:4px 0;font-weight:bold;text-align:right;color:{C["red"]};">{{{{expiry_date}}}}</td></tr>' +
            f'<tr><td style="padding:4px 0;color:{C["text_med"]};">Prix de renouvellement</td><td style="padding:4px 0;font-weight:bold;text-align:right;">{{{{renewal_price}}}}</td></tr>' +
            f'</table>'
        ) +
        p("Renouvelez maintenant pour conserver vos avantages sans interruption.")
    ) +
    zone4_cta("Renouveler mon plan", f"{CTA_BASE}/pricing") +
    zone5_footer()
)))

# 8. Reactivation Offer
TEMPLATES.append(("08_reactivation_offer_en", wrap(
    zone1_header() +
    zone2_hero(C["green"], "&#128275;", "Welcome Back — Here's a Gift") +
    body_zone(
        p(f"Hi {{{{first_name}}}},") +
        p("Your subscription has ended, but we'd love to have you back. As a special offer, here's a <strong>discount to reactivate</strong> your plan today.") +
        data_card(
            f'<p style="font-family:{FONT};font-size:12px;color:{C["text_med"]};margin:0 0 4px;text-transform:uppercase;letter-spacing:1px;">Reactivation Code</p>' +
            f'<p style="font-family:{FONT};font-size:28px;font-weight:bold;color:{C["green"]};margin:0;letter-spacing:2px;">{{{{coupon_code}}}}</p>'
        ) +
        p("All your listings, bid history, and watchlists are still here — waiting for you. Reactivate and pick up right where you left off.")
    ) +
    zone4_cta("Reactivate My Account", f"{CTA_BASE}/pricing") +
    zone5_footer()
)))

TEMPLATES.append(("08_reactivation_offer_fr", wrap(
    zone1_header() +
    zone2_hero(C["green"], "&#128275;", "Bon retour — Voici un cadeau") +
    body_zone(
        p(f"Bonjour {{{{first_name}}}},") +
        p("Votre abonnement a pris fin, mais nous serions ravis de vous revoir. En offre spéciale, voici une <strong>réduction pour réactiver</strong> votre plan aujourd'hui.") +
        data_card(
            f'<p style="font-family:{FONT};font-size:12px;color:{C["text_med"]};margin:0 0 4px;text-transform:uppercase;letter-spacing:1px;">Code de réactivation</p>' +
            f'<p style="font-family:{FONT};font-size:28px;font-weight:bold;color:{C["green"]};margin:0;letter-spacing:2px;">{{{{coupon_code}}}}</p>'
        ) +
        p("Toutes vos annonces, votre historique d'enchères et vos listes de surveillance sont encore ici — en attente. Réactivez et reprenez exactement où vous en étiez.")
    ) +
    zone4_cta("Réactiver mon compte", f"{CTA_BASE}/pricing") +
    zone5_footer()
)))

# 9. New Auction Near You (Geo)
TEMPLATES.append(("09_new_auction_near_you_en", wrap(
    zone1_header() +
    zone2_hero(C["sky"], "&#128205;", "New Auction Near You — {{city}}") +
    body_zone(
        p(f"Hi {{{{first_name}}}},") +
        p("A new auction just went live near your location. Don't miss this opportunity!") +
        f'{badge("{{{{distance_km}}}} KM FROM YOU", C["sky"])}' +
        data_card(
            f'<p style="font-family:{FONT};font-size:16px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">{{{{auction_title}}}}</p>' +
            f'<table width="100%" cellpadding="0" cellspacing="0" style="font-family:{FONT};font-size:13px;color:{C["text_dark"]};">' +
            f'<tr><td style="padding:3px 0;color:{C["text_med"]};">Starting Price</td><td style="padding:3px 0;font-weight:bold;text-align:right;">{{{{start_price}}}}</td></tr>' +
            f'<tr><td style="padding:3px 0;color:{C["text_med"]};">Location</td><td style="padding:3px 0;text-align:right;">{{{{city}}}}</td></tr>' +
            f'<tr><td style="padding:3px 0;color:{C["text_med"]};">Starts</td><td style="padding:3px 0;text-align:right;">{{{{auction_end_time}}}}</td></tr>' +
            f'</table>'
        )
    ) +
    zone4_cta("View Auction", f"{CTA_BASE}/listing/{{{{auction_id}}}}") +
    zone5_footer()
)))

TEMPLATES.append(("09_new_auction_near_you_fr", wrap(
    zone1_header() +
    zone2_hero(C["sky"], "&#128205;", "Nouvelle enchère près de chez vous — {{city}}") +
    body_zone(
        p(f"Bonjour {{{{first_name}}}},") +
        p("Une nouvelle enchère vient de commencer près de chez vous. Ne manquez pas cette opportunité !") +
        f'{badge("{{{{distance_km}}}} KM DE VOUS", C["sky"])}' +
        data_card(
            f'<p style="font-family:{FONT};font-size:16px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">{{{{auction_title}}}}</p>' +
            f'<table width="100%" cellpadding="0" cellspacing="0" style="font-family:{FONT};font-size:13px;color:{C["text_dark"]};">' +
            f'<tr><td style="padding:3px 0;color:{C["text_med"]};">Prix de départ</td><td style="padding:3px 0;font-weight:bold;text-align:right;">{{{{start_price}}}}</td></tr>' +
            f'<tr><td style="padding:3px 0;color:{C["text_med"]};">Lieu</td><td style="padding:3px 0;text-align:right;">{{{{city}}}}</td></tr>' +
            f'<tr><td style="padding:3px 0;color:{C["text_med"]};">Début</td><td style="padding:3px 0;text-align:right;">{{{{auction_end_time}}}}</td></tr>' +
            f'</table>'
        )
    ) +
    zone4_cta("Voir l'enchère", f"{CTA_BASE}/listing/{{{{auction_id}}}}") +
    zone5_footer()
)))

# 10. Ending Soon Near You (Geo)
TEMPLATES.append(("10_ending_soon_near_you_en", wrap(
    zone1_header() +
    zone2_hero(C["red"], "&#9203;", "Ending in {{hours_remaining}}h — Auction Near You") +
    body_zone(
        p(f"Hi {{{{first_name}}}},") +
        p("An auction near you is about to close. If you're interested, now is the time to act!") +
        f'{badge("ENDING SOON", C["red"])}' +
        data_card(
            f'<p style="font-family:{FONT};font-size:16px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">{{{{auction_title}}}}</p>' +
            f'<table width="100%" cellpadding="0" cellspacing="0" style="font-family:{FONT};font-size:13px;color:{C["text_dark"]};">' +
            f'<tr><td style="padding:3px 0;color:{C["text_med"]};">Current Highest Bid</td><td style="padding:3px 0;font-weight:bold;text-align:right;color:{C["green"]};">{{{{current_highest_bid}}}}</td></tr>' +
            f'<tr><td style="padding:3px 0;color:{C["text_med"]};">Time Remaining</td><td style="padding:3px 0;font-weight:bold;text-align:right;color:{C["red"]};">{{{{hours_remaining}}}} hours</td></tr>' +
            f'<tr><td style="padding:3px 0;color:{C["text_med"]};">Distance</td><td style="padding:3px 0;text-align:right;">{{{{distance_km}}}} km</td></tr>' +
            f'</table>'
        ) +
        p("Don't let this one slip away. Place your bid before time runs out.")
    ) +
    zone4_cta("Bid Now", f"{CTA_BASE}/listing/{{{{auction_id}}}}") +
    zone5_footer()
)))

TEMPLATES.append(("10_ending_soon_near_you_fr", wrap(
    zone1_header() +
    zone2_hero(C["red"], "&#9203;", "Se termine dans {{hours_remaining}}h — Enchère près de vous") +
    body_zone(
        p(f"Bonjour {{{{first_name}}}},") +
        p("Une enchère près de chez vous est sur le point de se terminer. Si vous êtes intéressé, c'est le moment d'agir !") +
        f'{badge("SE TERMINE BIENTÔT", C["red"])}' +
        data_card(
            f'<p style="font-family:{FONT};font-size:16px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">{{{{auction_title}}}}</p>' +
            f'<table width="100%" cellpadding="0" cellspacing="0" style="font-family:{FONT};font-size:13px;color:{C["text_dark"]};">' +
            f'<tr><td style="padding:3px 0;color:{C["text_med"]};">Enchère la plus haute</td><td style="padding:3px 0;font-weight:bold;text-align:right;color:{C["green"]};">{{{{current_highest_bid}}}}</td></tr>' +
            f'<tr><td style="padding:3px 0;color:{C["text_med"]};">Temps restant</td><td style="padding:3px 0;font-weight:bold;text-align:right;color:{C["red"]};">{{{{hours_remaining}}}} heures</td></tr>' +
            f'<tr><td style="padding:3px 0;color:{C["text_med"]};">Distance</td><td style="padding:3px 0;text-align:right;">{{{{distance_km}}}} km</td></tr>' +
            f'</table>'
        ) +
        p("Ne laissez pas celle-ci vous échapper. Placez votre enchère avant la fin du temps imparti.")
    ) +
    zone4_cta("Enchérir maintenant", f"{CTA_BASE}/listing/{{{{auction_id}}}}") +
    zone5_footer()
)))


# ════════════════════════════════════════════════════════════
# GENERATE FILES
# ════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import os
    out_dir = os.path.dirname(os.path.abspath(__file__))
    for name, html in TEMPLATES:
        # Fix double-escaped handlebars (Python f-string needs {{{{ for literal {{)
        html = html.replace("{{{{", "{{").replace("}}}}", "}}")
        path = os.path.join(out_dir, f"{name}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  Generated: {name}.html")
    print(f"\n  Total: {len(TEMPLATES)} templates generated in {out_dir}/")
