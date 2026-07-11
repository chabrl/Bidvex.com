"""
BidVex SendGrid Dynamic Template Generator — BILINGUAL (Bill 96 Compliant)
Each template contains BOTH EN and FR in the same email body.
EN block first, divider, FR block second.
Run: python generate_bilingual_templates.py
Output: 10 bilingual .html files (not 20 separate EN/FR files)
"""

LOGO_URL = "http://cdn.mcauto-images-production.sendgrid.net/4fbf02710175d39f/9dc6a7c3-8237-4a66-b82b-0d9abc165b44/4500x1080.png"
CTA_BASE = "https://bidvex.com"

C = {
    "navy": "#0B2545", "blue": "#2186C6", "sky": "#3FB4CB", "white": "#FFFFFF",
    "light_bg": "#F0F8FF", "text_dark": "#1E293B", "text_med": "#64748B",
    "green": "#059669", "amber": "#F59E0B", "red": "#DC2626", "border": "#E2E8F0",
}
FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif"


def zone1():
    return f'<tr><td style="background-color:{C["navy"]};padding:24px 0;text-align:center;border-bottom:3px solid {C["sky"]};"><img src="{LOGO_URL}" alt="BidVex" width="150" style="display:inline-block;width:150px;height:auto;" /></td></tr>'

def hero(color, icon, en_headline, fr_headline):
    return (
        f'<tr><td style="background-color:{color};padding:32px 30px;text-align:center;">'
        f'<p style="margin:0 0 8px;font-size:48px;line-height:1;">{icon}</p>'
        f'<h1 style="margin:0;font-family:{FONT};font-size:24px;font-weight:bold;color:{C["white"]};">{en_headline}</h1>'
        f'<p style="margin:8px 0 0;font-family:{FONT};font-size:16px;color:rgba(255,255,255,0.7);">{fr_headline}</p>'
        f'</td></tr>'
    )

def divider():
    return f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;"><tr><td style="border-top:2px solid {C["border"]};height:1px;font-size:0;line-height:0;">&nbsp;</td></tr></table>'

def lang_label(lang):
    return f'<p style="margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:{C["blue"]};font-weight:700;font-family:{FONT};">{lang}</p>'

def p(text):
    return f'<p style="margin:0 0 14px;font-family:{FONT};font-size:15px;line-height:1.6;color:{C["text_dark"]};">{text}</p>'

def card(html):
    return f'<table width="100%" cellpadding="0" cellspacing="0" style="margin:16px 0;"><tr><td style="background-color:{C["light_bg"]};border:1px solid {C["sky"]};border-radius:8px;padding:16px;">{html}</td></tr></table>'

def badge(text, bg):
    return f'<span style="display:inline-block;background-color:{bg};color:{C["white"]};font-family:{FONT};font-size:11px;font-weight:bold;padding:4px 10px;border-radius:4px;text-transform:uppercase;letter-spacing:1px;">{text}</span>'

def cta(en_label, fr_label, url):
    return (
        f'<tr><td style="padding:8px 30px 32px;text-align:center;">'
        f'<table cellpadding="0" cellspacing="0" align="center"><tr>'
        f'<td style="background-color:{C["blue"]};border-radius:8px;padding:14px 32px;">'
        f'<a href="{url}" style="color:{C["white"]};font-family:{FONT};font-size:15px;font-weight:bold;text-decoration:none;display:inline-block;" target="_blank" clicktracking=off>{en_label} / {fr_label}</a>'
        f'</td></tr></table></td></tr>'
    )

def footer():
    return (
        f'<tr><td style="background-color:{C["navy"]};padding:28px 30px;text-align:center;">'
        f'<img src="{LOGO_URL}" alt="BidVex" width="80" style="display:inline-block;width:80px;height:auto;opacity:0.7;margin-bottom:12px;" /><br/>'
        f'<p style="margin:0 0 6px;font-family:{FONT};font-size:12px;color:rgba(255,255,255,0.6);">BidVex Canada | Sherbrooke, QC</p>'
        f'<p style="margin:0 0 6px;font-family:{FONT};font-size:12px;color:rgba(255,255,255,0.5);"><a href="mailto:service@bidvex.com" style="color:{C["sky"]};text-decoration:none;" clicktracking=off>service@bidvex.com</a></p>'
        f'<p style="margin:0;font-family:{FONT};font-size:11px;color:rgba(255,255,255,0.35);"><a href="{CTA_BASE}/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;" clicktracking=off>Privacy</a> &nbsp;|&nbsp; <a href="{CTA_BASE}/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;" clicktracking=off>Terms</a></p>'
        f'<p style="margin:8px 0 0;font-family:{FONT};font-size:11px;color:rgba(255,255,255,0.3);">&copy; {{{{current_year}}}} BidVex Inc.</p>'
        f'</td></tr>'
    )

def body(html):
    return f'<tr><td class="body-cell" style="padding:32px 30px;">{html}</td></tr>'

def icon_card(icon, en_title, en_desc, fr_title, fr_desc):
    return (
        f'<table cellpadding="0" cellspacing="0" style="background-color:{C["light_bg"]};border:1px solid {C["sky"]};border-radius:8px;padding:16px;width:100%;margin-bottom:12px;">'
        f'<tr><td style="font-size:28px;padding-bottom:8px;">{icon}</td></tr>'
        f'<tr><td style="font-family:{FONT};font-size:13px;font-weight:bold;color:{C["navy"]};padding-bottom:2px;">{en_title}</td></tr>'
        f'<tr><td style="font-family:{FONT};font-size:12px;color:{C["text_med"]};line-height:1.5;padding-bottom:8px;">{en_desc}</td></tr>'
        f'<tr><td style="border-top:1px solid {C["border"]};padding-top:8px;font-family:{FONT};font-size:13px;font-weight:bold;color:{C["navy"]};padding-bottom:2px;">{fr_title}</td></tr>'
        f'<tr><td style="font-family:{FONT};font-size:12px;color:{C["text_med"]};line-height:1.5;">{fr_desc}</td></tr>'
        f'</table>'
    )

def wrap(rows):
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>@media (max-width:600px){{.outer-table{{width:100%!important}}.body-cell{{padding:24px 16px!important}}h1{{font-size:20px!important}}}}</style>
</head><body style="margin:0;padding:0;background-color:#F0F4F8;font-family:{FONT};">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#F0F4F8;padding:24px 12px;">
<tr><td align="center">
<table class="outer-table" width="600" cellpadding="0" cellspacing="0" style="background-color:{C['white']};border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);">
{rows}
</table></td></tr></table></body></html>"""


TEMPLATES = []

# 1. Welcome
TEMPLATES.append(("welcome_bilingual", wrap(
    zone1() + hero(C["navy"], "&#127881;", "Welcome to BidVex, {{first_name}}!", "Bienvenue chez BidVex, {{first_name}} !") +
    body(
        lang_label("ENGLISH") +
        p("You've just joined North America's most advanced all-in-one auction marketplace. Whether you're looking for a fleet of trucks, a single rare collectible, or liquidating an entire warehouse of industrial equipment — BidVex is built to handle it all.") +
        icon_card("&#128722;", "All-In-One Marketplace", "From vehicles and heavy machinery to multi-item lots.",
                  "Marché tout-en-un", "Des véhicules et de la machinerie lourde aux lots d'articles multiples.") +
        icon_card("&#129302;", "AI-Powered Tools", "Our intelligent concierge is ready to help you 24/7.",
                  "Outils propulsés par l'IA", "Notre concierge intelligent est prêt à vous aider 24/7.") +
        icon_card("&#127760;", "Bilingual &amp; Cross-Border", "Seamlessly buy or sell across Canada and the US.",
                  "Bilingue et transfrontalier", "Achetez ou vendez partout au Canada et aux États-Unis.") +
        f'<p style="margin:12px 0 0;font-family:{FONT};font-size:12px;color:{C["text_med"]};">BidVex uses AI for support, categorization, and fraud detection. You may request human review of any AI decision at <a href="mailto:privacy@bidvex.com" style="color:{C["blue"]};" clicktracking=off>privacy@bidvex.com</a> (Law 25).</p>' +
        divider() +
        lang_label("FRANÇAIS") +
        p("Vous venez de rejoindre la plateforme « tout-en-un » la plus avancée en Amérique du Nord. Que vous cherchiez une flotte de camions, une pièce de collection unique ou que vous souhaitiez liquider un entrepôt complet d'équipement industriel — BidVex est conçu pour tout gérer.") +
        f'<p style="margin:12px 0 0;font-family:{FONT};font-size:12px;color:{C["text_med"]};">BidVex utilise l\'IA pour le support, la catégorisation et la détection de fraude. Vous pouvez demander une révision humaine à <a href="mailto:privacy@bidvex.com" style="color:{C["blue"]};" clicktracking=off>privacy@bidvex.com</a> (Loi 25).</p>'
    ) +
    cta("Explore the Marketplace", "Explorer le marché", f"{CTA_BASE}/marketplace") + footer()
)))

# 2. Onboarding Day 3
TEMPLATES.append(("onboarding_day3_bilingual", wrap(
    zone1() + hero(C["blue"], "&#128296;", "Have You Placed Your First Bid?", "Avez-vous placé votre première enchère ?") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, it's been 3 days since you joined BidVex. There are live auctions happening right now near you — don't miss out!") +
        p("Bidding is simple: find an item, set your maximum, and our system bids for you. If you win, you'll be notified instantly.") +
        divider() +
        lang_label("FRANÇAIS") +
        p("Bonjour {{first_name}}, cela fait 3 jours que vous avez rejoint BidVex. Des enchères en direct se déroulent en ce moment près de chez vous — ne les manquez pas !") +
        p("Enchérir est simple : trouvez un article, définissez votre maximum, et notre système enchérit pour vous. Si vous gagnez, vous serez notifié instantanément.")
    ) +
    cta("Browse Live Auctions", "Parcourir les enchères", f"{CTA_BASE}/marketplace") + footer()
)))

# 3. Onboarding Week 1
TEMPLATES.append(("onboarding_week1_bilingual", wrap(
    zone1() + hero(C["blue"], "&#128218;", "Your BidVex Quick-Start Guide", "Votre guide de démarrage BidVex") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, here's everything you need to know to get the most out of BidVex in your first week.") +
        icon_card("&#128269;", "Find &amp; Bid", "Browse categories, set price alerts, and bid on items you love.",
                  "Trouver et enchérir", "Parcourez les catégories, définissez des alertes de prix et enchérissez.") +
        icon_card("&#128176;", "Sell &amp; Earn", "List your items for auction — from a single tool to an entire warehouse.",
                  "Vendre et gagner", "Listez vos articles aux enchères — d'un seul outil à un entrepôt entier.") +
        divider() +
        lang_label("FRANÇAIS") +
        p("Bonjour {{first_name}}, voici tout ce que vous devez savoir pour tirer le meilleur parti de BidVex dès votre première semaine.")
    ) +
    cta("Explore Plans", "Explorer les plans", f"{CTA_BASE}/pricing") + footer()
)))

# 4. Subscription Pitch
TEMPLATES.append(("subscription_pitch_bilingual", wrap(
    zone1() + hero(C["navy"], "&#128640;", "Unlock the Full BidVex Experience", "Débloquez l'expérience BidVex complète") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, you've been on BidVex for 2 weeks. Ready to take it to the next level? Upgrade today and get <strong>20% off your first year</strong>.") +
        card(f'<p style="font-family:{FONT};font-size:12px;color:{C["text_med"]};margin:0 0 4px;text-transform:uppercase;letter-spacing:1px;">Your Exclusive Code / Votre code exclusif</p><p style="font-family:{FONT};font-size:28px;font-weight:bold;color:{C["blue"]};margin:0;letter-spacing:2px;">{{{{coupon_code}}}}</p><p style="font-family:{FONT};font-size:12px;color:{C["red"]};margin:6px 0 0;font-weight:bold;">Offer expires in 48h / L\'offre expire dans 48 heures</p>') +
        divider() +
        lang_label("FRANÇAIS") +
        p("Bonjour {{first_name}}, vous êtes sur BidVex depuis 2 semaines. Prêt à passer au niveau supérieur ? Améliorez votre plan aujourd'hui et obtenez <strong>20 % de réduction sur votre première année</strong>.")
    ) +
    cta("Upgrade Now — 20% Off", "Améliorer — 20 % de rabais", f"{CTA_BASE}/pricing") + footer()
)))

# 5. Re-engagement
TEMPLATES.append(("reengagement_bilingual", wrap(
    zone1() + hero(C["sky"], "&#128075;", "We Miss You, {{first_name}}!", "Vous nous manquez, {{first_name}} !") +
    body(
        lang_label("ENGLISH") +
        p("It's been a while since you last visited BidVex. A lot has happened — new listings, new sellers, and auctions ending soon near you.") +
        p("Your account is still fully active and ready to go. Jump back in today.") +
        divider() +
        lang_label("FRANÇAIS") +
        p("Cela fait un moment que vous n'avez pas visité BidVex. Beaucoup de choses se sont passées — nouvelles annonces, nouveaux vendeurs et des enchères se terminant bientôt près de chez vous.") +
        p("Votre compte est toujours actif et prêt. Revenez dès aujourd'hui.")
    ) +
    cta("Browse What's New", "Découvrir les nouveautés", f"{CTA_BASE}/marketplace") + footer()
)))

# 6. Re-engagement Final
TEMPLATES.append(("reengagement_final_bilingual", wrap(
    zone1() + hero(C["amber"], "&#9200;", "Last Chance — Come Back & Save", "Dernière chance — Revenez et économisez") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, we haven't seen you in 45 days. Here's an exclusive <strong>15% discount</strong> on any BidVex subscription.") +
        card(f'<p style="font-family:{FONT};font-size:12px;color:{C["text_med"]};margin:0 0 4px;text-transform:uppercase;letter-spacing:1px;">Come-Back Code / Code de retour</p><p style="font-family:{FONT};font-size:28px;font-weight:bold;color:{C["amber"]};margin:0;letter-spacing:2px;">{{{{coupon_code}}}}</p><p style="font-family:{FONT};font-size:12px;color:{C["red"]};margin:6px 0 0;font-weight:bold;">This is your final reminder / Ceci est votre dernier rappel</p>') +
        divider() +
        lang_label("FRANÇAIS") +
        p("Bonjour {{first_name}}, nous ne vous avons pas vu depuis 45 jours. Voici une <strong>réduction exclusive de 15 %</strong> sur tout abonnement BidVex.")
    ) +
    cta("Reactivate & Save 15%", "Réactiver et économiser 15 %", f"{CTA_BASE}/pricing") + footer()
)))

# 7. Subscription Final Reminder
TEMPLATES.append(("subscription_final_reminder_bilingual", wrap(
    zone1() + hero(C["red"], "&#128274;", "Your Subscription Expires Tomorrow", "Votre abonnement expire demain") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, your <strong>{{plan_name}}</strong> subscription expires <strong>tomorrow</strong>. After that, you'll lose access to premium features.") +
        card(f'<table width="100%" cellpadding="0" cellspacing="0" style="font-family:{FONT};font-size:14px;color:{C["text_dark"]};"><tr><td style="padding:4px 0;color:{C["text_med"]};">Plan</td><td style="padding:4px 0;font-weight:bold;text-align:right;">{{{{plan_name}}}}</td></tr><tr><td style="padding:4px 0;color:{C["text_med"]};">Expires / Expire le</td><td style="padding:4px 0;font-weight:bold;text-align:right;color:{C["red"]};">{{{{expiry_date}}}}</td></tr><tr><td style="padding:4px 0;color:{C["text_med"]};">Price / Prix</td><td style="padding:4px 0;font-weight:bold;text-align:right;">{{{{renewal_price}}}}</td></tr></table>') +
        divider() +
        lang_label("FRANÇAIS") +
        p("Bonjour {{first_name}}, votre abonnement <strong>{{plan_name}}</strong> expire <strong>demain</strong>. Après cela, vous perdrez l'accès aux fonctionnalités premium.") +
        p("Renouvelez maintenant pour conserver vos avantages sans interruption.")
    ) +
    cta("Renew My Plan", "Renouveler mon plan", f"{CTA_BASE}/pricing") + footer()
)))

# 8. Reactivation Offer
TEMPLATES.append(("reactivation_offer_bilingual", wrap(
    zone1() + hero(C["green"], "&#128275;", "Welcome Back — Here's a Gift", "Bon retour — Voici un cadeau") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, your subscription has ended, but we'd love to have you back. Here's a special discount to reactivate today.") +
        card(f'<p style="font-family:{FONT};font-size:12px;color:{C["text_med"]};margin:0 0 4px;text-transform:uppercase;letter-spacing:1px;">Reactivation Code / Code de réactivation</p><p style="font-family:{FONT};font-size:28px;font-weight:bold;color:{C["green"]};margin:0;letter-spacing:2px;">{{{{coupon_code}}}}</p>') +
        p("All your listings, bid history, and watchlists are still here — waiting for you.") +
        divider() +
        lang_label("FRANÇAIS") +
        p("Bonjour {{first_name}}, votre abonnement a pris fin, mais nous serions ravis de vous revoir. Voici une réduction spéciale pour réactiver aujourd'hui.") +
        p("Toutes vos annonces, votre historique d'enchères et vos listes de surveillance sont encore ici — en attente.")
    ) +
    cta("Reactivate My Account", "Réactiver mon compte", f"{CTA_BASE}/pricing") + footer()
)))

# 9. New Auction Near You
TEMPLATES.append(("new_auction_near_you_bilingual", wrap(
    zone1() + hero(C["sky"], "&#128205;", "New Auction Near You — {{city}}", "Nouvelle enchère près de chez vous — {{city}}") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, a new auction just went live near your location. Don't miss this opportunity!") +
        f'{badge("{{{{distance_km}}}} KM", C["sky"])}' +
        card(f'<p style="font-family:{FONT};font-size:16px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">{{{{auction_title}}}}</p><table width="100%" cellpadding="0" cellspacing="0" style="font-family:{FONT};font-size:13px;color:{C["text_dark"]};"><tr><td style="padding:3px 0;color:{C["text_med"]};">Starting Price / Prix de départ</td><td style="padding:3px 0;font-weight:bold;text-align:right;">{{{{start_price}}}}</td></tr><tr><td style="padding:3px 0;color:{C["text_med"]};">Location / Lieu</td><td style="padding:3px 0;text-align:right;">{{{{city}}}}</td></tr></table>') +
        divider() +
        lang_label("FRANÇAIS") +
        p("Bonjour {{first_name}}, une nouvelle enchère vient de commencer près de chez vous. Ne manquez pas cette opportunité !")
    ) +
    cta("View Auction", "Voir l'enchère", CTA_BASE + "/listing/{{auction_id}}") + footer()
)))

# 10. Ending Soon Near You
TEMPLATES.append(("ending_soon_near_you_bilingual", wrap(
    zone1() + hero(C["red"], "&#9203;", "Ending in {{hours_remaining}}h — Auction Near You", "Se termine dans {{hours_remaining}}h — Enchère près de vous") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, an auction near you is about to close. If you're interested, now is the time to act!") +
        f'{badge("ENDING SOON / SE TERMINE BIENTÔT", C["red"])}' +
        card(f'<p style="font-family:{FONT};font-size:16px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">{{{{auction_title}}}}</p><table width="100%" cellpadding="0" cellspacing="0" style="font-family:{FONT};font-size:13px;color:{C["text_dark"]};"><tr><td style="padding:3px 0;color:{C["text_med"]};">Highest Bid / Enchère la plus haute</td><td style="padding:3px 0;font-weight:bold;text-align:right;color:{C["green"]};">{{{{current_highest_bid}}}}</td></tr><tr><td style="padding:3px 0;color:{C["text_med"]};">Time Left / Temps restant</td><td style="padding:3px 0;font-weight:bold;text-align:right;color:{C["red"]};">{{{{hours_remaining}}}} hours / heures</td></tr><tr><td style="padding:3px 0;color:{C["text_med"]};">Distance</td><td style="padding:3px 0;text-align:right;">{{{{distance_km}}}} km</td></tr></table>') +
        divider() +
        lang_label("FRANÇAIS") +
        p("Bonjour {{first_name}}, une enchère près de chez vous est sur le point de se terminer. Si vous êtes intéressé, c'est le moment d'agir !") +
        p("Ne laissez pas celle-ci vous échapper. Placez votre enchère avant la fin du temps imparti.")
    ) +
    cta("Bid Now", "Enchérir maintenant", CTA_BASE + "/listing/{{auction_id}}") + footer()
)))


if __name__ == "__main__":
    import os
    out_dir = os.path.dirname(os.path.abspath(__file__))
    for name, html in TEMPLATES:
        html = html.replace("{{{{", "{{").replace("}}}}", "}}")
        path = os.path.join(out_dir, f"{name}.html")
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"  Generated: {name}.html")
    print(f"\n  Total: {len(TEMPLATES)} bilingual templates generated")
