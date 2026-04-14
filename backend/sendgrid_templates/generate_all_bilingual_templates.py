"""
BidVex — Complete Bilingual Email Template Generator
Generates ALL 29 remaining bilingual templates (EN + FR in one HTML).
Uses the same design system as the existing 10 lifecycle/geo templates.
Run: python generate_all_bilingual_templates.py
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


def kv_row(label, value, value_color=None):
    vc = f'color:{value_color};' if value_color else ''
    return (
        f'<tr><td style="padding:4px 0;color:{C["text_med"]};font-family:{FONT};font-size:13px;">{label}</td>'
        f'<td style="padding:4px 0;font-weight:bold;text-align:right;font-family:{FONT};font-size:13px;{vc}">{value}</td></tr>'
    )


def detail_table(rows_html):
    return (
        f'<table width="100%" cellpadding="0" cellspacing="0" '
        f'style="font-family:{FONT};font-size:14px;color:{C["text_dark"]};">'
        f'{rows_html}</table>'
    )


def cta(en_label, fr_label, url):
    return (
        f'<tr><td style="padding:8px 30px 32px;text-align:center;">'
        f'<table cellpadding="0" cellspacing="0" align="center"><tr>'
        f'<td style="background-color:{C["blue"]};border-radius:8px;padding:14px 32px;">'
        f'<a href="{url}" style="color:{C["white"]};font-family:{FONT};font-size:15px;font-weight:bold;text-decoration:none;display:inline-block;" target="_blank">{en_label} / {fr_label}</a>'
        f'</td></tr></table></td></tr>'
    )


def footer():
    return (
        f'<tr><td style="background-color:{C["navy"]};padding:28px 30px;text-align:center;">'
        f'<img src="{LOGO_URL}" alt="BidVex" width="80" style="display:inline-block;width:80px;height:auto;opacity:0.7;margin-bottom:12px;" /><br/>'
        f'<p style="margin:0 0 6px;font-family:{FONT};font-size:12px;color:rgba(255,255,255,0.6);">BidVex Canada | Sherbrooke, QC</p>'
        f'<p style="margin:0 0 6px;font-family:{FONT};font-size:12px;color:rgba(255,255,255,0.5);"><a href="mailto:support@bidvex.com" style="color:{C["sky"]};text-decoration:none;">support@bidvex.com</a></p>'
        f'<p style="margin:0;font-family:{FONT};font-size:11px;color:rgba(255,255,255,0.35);"><a href="{CTA_BASE}/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;">Privacy</a> &nbsp;|&nbsp; <a href="{CTA_BASE}/legal" style="color:rgba(255,255,255,0.45);text-decoration:underline;">Terms</a></p>'
        f'<p style="margin:8px 0 0;font-family:{FONT};font-size:11px;color:rgba(255,255,255,0.3);">&copy; {{{{current_year}}}} BidVex Inc.</p>'
        f'</td></tr>'
    )


def body(html):
    return f'<tr><td class="body-cell" style="padding:32px 30px;">{html}</td></tr>'


def law25_note():
    return (
        f'<p style="margin:12px 0 0;font-family:{FONT};font-size:12px;color:{C["text_med"]};">'
        f'BidVex uses AI for support, categorization, and fraud detection. You may request human review of any AI decision at '
        f'<a href="mailto:privacy@bidvex.com" style="color:{C["blue"]};">privacy@bidvex.com</a> (Law 25).</p>'
    )


def law25_note_fr():
    return (
        f'<p style="margin:12px 0 0;font-family:{FONT};font-size:12px;color:{C["text_med"]};">'
        f'BidVex utilise l\'IA pour le support, la cat&eacute;gorisation et la d&eacute;tection de fraude. '
        f'Vous pouvez demander une r&eacute;vision humaine &agrave; '
        f'<a href="mailto:privacy@bidvex.com" style="color:{C["blue"]};">privacy@bidvex.com</a> (Loi 25).</p>'
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

# ═══════════════════════════════════════════════════════════════
# AUTH TEMPLATES (5)
# ═══════════════════════════════════════════════════════════════

# 1. Password Reset
TEMPLATES.append(("auth_password_reset_bilingual", wrap(
    zone1() + hero(C["red"], "&#128274;", "Reset Your Password", "R&eacute;initialisez votre mot de passe") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, we received a request to reset your password. Click the button below to create a new one. This link expires in 1 hour.") +
        p("If you did not request a password reset, please ignore this email or contact our support team immediately.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, nous avons re&ccedil;u une demande de r&eacute;initialisation de votre mot de passe. Cliquez sur le bouton ci-dessous pour en cr&eacute;er un nouveau. Ce lien expire dans 1 heure.") +
        p("Si vous n'avez pas demand&eacute; cette r&eacute;initialisation, veuillez ignorer cet e-mail ou contacter notre &eacute;quipe de support imm&eacute;diatement.")
    ) +
    cta("Reset Password", "R&eacute;initialiser le mot de passe", "{{reset_url}}") + footer()
)))

# 2. Password Changed
TEMPLATES.append(("auth_password_changed_bilingual", wrap(
    zone1() + hero(C["green"], "&#9989;", "Password Changed Successfully", "Mot de passe modifi&eacute; avec succ&egrave;s") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, your BidVex password was successfully changed. If you made this change, no further action is needed.") +
        p("If you did NOT change your password, please reset it immediately and contact <a href=\"mailto:support@bidvex.com\" style=\"color:#2186C6;\">support@bidvex.com</a>.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, votre mot de passe BidVex a &eacute;t&eacute; modifi&eacute; avec succ&egrave;s. Si vous avez effectu&eacute; ce changement, aucune action suppl&eacute;mentaire n'est requise.") +
        p("Si vous n'avez PAS modifi&eacute; votre mot de passe, veuillez le r&eacute;initialiser imm&eacute;diatement et contacter <a href=\"mailto:support@bidvex.com\" style=\"color:#2186C6;\">support@bidvex.com</a>.")
    ) +
    cta("Go to BidVex", "Aller sur BidVex", CTA_BASE) + footer()
)))

# 3. Email Verification
TEMPLATES.append(("auth_email_verification_bilingual", wrap(
    zone1() + hero(C["blue"], "&#128231;", "Verify Your Email Address", "V&eacute;rifiez votre adresse courriel") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, thank you for registering on BidVex! Please verify your email address by clicking the button below.") +
        p("This verification link expires in 24 hours.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, merci de vous &ecirc;tre inscrit sur BidVex ! Veuillez v&eacute;rifier votre adresse courriel en cliquant sur le bouton ci-dessous.") +
        p("Ce lien de v&eacute;rification expire dans 24 heures.")
    ) +
    cta("Verify Email", "V&eacute;rifier le courriel", "{{verification_url}}") + footer()
)))

# 4. Two-Factor Code
TEMPLATES.append(("auth_two_factor_bilingual", wrap(
    zone1() + hero(C["navy"], "&#128272;", "Your Verification Code", "Votre code de v&eacute;rification") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, here is your two-factor authentication code:") +
        card(
            f'<p style="font-family:{FONT};font-size:12px;color:{C["text_med"]};margin:0 0 4px;text-transform:uppercase;letter-spacing:1px;">Verification Code / Code de v&eacute;rification</p>'
            f'<p style="font-family:{FONT};font-size:36px;font-weight:bold;color:{C["blue"]};margin:0;letter-spacing:6px;">{{{{verification_code}}}}</p>'
            f'<p style="font-family:{FONT};font-size:12px;color:{C["red"]};margin:6px 0 0;font-weight:bold;">Expires in 10 minutes / Expire dans 10 minutes</p>'
        ) +
        p("If you did not request this code, please secure your account immediately.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, voici votre code d'authentification &agrave; deux facteurs :") +
        p("Si vous n'avez pas demand&eacute; ce code, veuillez s&eacute;curiser votre compte imm&eacute;diatement.")
    ) + footer()
)))

# 5. Login Alert
TEMPLATES.append(("auth_login_alert_bilingual", wrap(
    zone1() + hero(C["amber"], "&#128680;", "New Login Detected", "Nouvelle connexion d&eacute;tect&eacute;e") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, a new login to your BidVex account was detected.") +
        card(detail_table(
            kv_row("Date / Heure", "{{login_time}}") +
            kv_row("IP Address / Adresse IP", "{{login_ip}}") +
            kv_row("Device / Appareil", "{{login_device}}")
        )) +
        p("If this was you, no action is needed. If you don't recognize this login, please <a href=\"" + CTA_BASE + "/settings\" style=\"color:#2186C6;\">change your password</a> immediately.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, une nouvelle connexion &agrave; votre compte BidVex a &eacute;t&eacute; d&eacute;tect&eacute;e.") +
        p("Si c'&eacute;tait vous, aucune action n'est requise. Sinon, veuillez <a href=\"" + CTA_BASE + "/settings\" style=\"color:#2186C6;\">changer votre mot de passe</a> imm&eacute;diatement.")
    ) +
    cta("Review Account Security", "V&eacute;rifier la s&eacute;curit&eacute; du compte", CTA_BASE + "/settings") + footer()
)))

# ═══════════════════════════════════════════════════════════════
# ADMIN TEMPLATES (2)
# ═══════════════════════════════════════════════════════════════

# 6. Account Suspended
TEMPLATES.append(("admin_account_suspended_bilingual", wrap(
    zone1() + hero(C["red"], "&#128683;", "Account Suspended", "Compte suspendu") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, your BidVex account has been suspended for the following reason:") +
        card(f'<p style="font-family:{FONT};font-size:15px;font-weight:bold;color:{C["red"]};margin:0;">{{{{reason}}}}</p>') +
        p("If you believe this is an error, please contact our support team at <a href=\"mailto:support@bidvex.com\" style=\"color:#2186C6;\">support@bidvex.com</a> with your account details.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, votre compte BidVex a &eacute;t&eacute; suspendu pour la raison suivante :") +
        p("Si vous croyez qu'il s'agit d'une erreur, veuillez contacter notre &eacute;quipe de support &agrave; <a href=\"mailto:support@bidvex.com\" style=\"color:#2186C6;\">support@bidvex.com</a>.")
    ) + footer()
)))

# 7. Report Received
TEMPLATES.append(("admin_report_received_bilingual", wrap(
    zone1() + hero(C["blue"], "&#128196;", "Your Report Has Been Received", "Votre signalement a &eacute;t&eacute; re&ccedil;u") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, thank you for submitting a report. Our team is reviewing it and will take action as needed.") +
        card(detail_table(
            kv_row("Report ID / No de signalement", "{{report_id}}") +
            kv_row("Type", "{{report_type}}")
        )) +
        p("You will receive a follow-up notification once the review is complete.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, merci d'avoir soumis un signalement. Notre &eacute;quipe l'examine et prendra les mesures n&eacute;cessaires.") +
        p("Vous recevrez une notification de suivi une fois l'examen termin&eacute;.")
    ) +
    cta("View Your Reports", "Voir vos signalements", CTA_BASE + "/dashboard") + footer()
)))

# ═══════════════════════════════════════════════════════════════
# COMMUNICATION TEMPLATES (3)
# ═══════════════════════════════════════════════════════════════

# 8. Announcement
TEMPLATES.append(("comm_announcement_bilingual", wrap(
    zone1() + hero(C["navy"], "&#128227;", "{{announcement_title}}", "{{announcement_title}}") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, we have an important announcement from BidVex:") +
        card(f'<p style="font-family:{FONT};font-size:15px;color:{C["text_dark"]};margin:0;line-height:1.6;">{{{{announcement_body_en}}}}</p>') +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, voici une annonce importante de BidVex :") +
        card(f'<p style="font-family:{FONT};font-size:15px;color:{C["text_dark"]};margin:0;line-height:1.6;">{{{{announcement_body_fr}}}}</p>')
    ) +
    cta("Learn More", "En savoir plus", "{{cta_url}}") + footer()
)))

# 9. Support Acknowledgment
TEMPLATES.append(("comm_support_ack_bilingual", wrap(
    zone1() + hero(C["green"], "&#128172;", "We Received Your Message", "Nous avons re&ccedil;u votre message") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, thank you for contacting BidVex support. We've received your request and will respond within 24&ndash;48 business hours.") +
        card(detail_table(
            kv_row("Ticket ID / No de billet", "{{ticket_id}}") +
            kv_row("Subject / Sujet", "{{subject}}")
        )) +
        p("In the meantime, you may find answers in our <a href=\"" + CTA_BASE + "/help\" style=\"color:#2186C6;\">Help Center</a>.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, merci d'avoir contact&eacute; le support BidVex. Nous avons re&ccedil;u votre demande et r&eacute;pondrons dans un d&eacute;lai de 24 &agrave; 48 heures ouvrables.") +
        p("Entre-temps, vous pouvez consulter notre <a href=\"" + CTA_BASE + "/help\" style=\"color:#2186C6;\">Centre d'aide</a>.")
    ) + footer()
)))

# 10. Platform Updates
TEMPLATES.append(("comm_platform_updates_bilingual", wrap(
    zone1() + hero(C["sky"], "&#128640;", "What's New on BidVex", "Quoi de neuf sur BidVex") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, here's what's new on BidVex this month:") +
        card(
            f'<p style="font-family:{FONT};font-size:16px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">{{{{update_title}}}}</p>'
            f'<p style="font-family:{FONT};font-size:14px;color:{C["text_dark"]};margin:0;line-height:1.6;">{{{{update_description}}}}</p>'
        ) +
        p("We're constantly improving BidVex to give you the best auction experience in Canada.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, voici les nouveaut&eacute;s sur BidVex ce mois-ci :") +
        p("Nous am&eacute;liorons constamment BidVex pour vous offrir la meilleure exp&eacute;rience d'ench&egrave;res au Canada.")
    ) +
    cta("See What's New", "D&eacute;couvrir les nouveaut&eacute;s", CTA_BASE + "/marketplace") + footer()
)))

# ═══════════════════════════════════════════════════════════════
# FINANCIAL TEMPLATES (4)
# ═══════════════════════════════════════════════════════════════

# 11. Invoice Issued
TEMPLATES.append(("fin_invoice_issued_bilingual", wrap(
    zone1() + hero(C["navy"], "&#128196;", "Invoice #{{invoice_number}}", "Facture #{{invoice_number}}") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, a new invoice has been issued for your account.") +
        card(detail_table(
            kv_row("Invoice / Facture", "#{{invoice_number}}") +
            kv_row("Amount / Montant", "{{amount}}", C["navy"]) +
            kv_row("Due Date / &Eacute;ch&eacute;ance", "{{due_date}}", C["red"]) +
            kv_row("Currency / Devise", "CAD")
        )) +
        p("Please ensure payment is made before the due date to avoid service interruptions.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, une nouvelle facture a &eacute;t&eacute; &eacute;mise pour votre compte.") +
        p("Veuillez vous assurer que le paiement est effectu&eacute; avant la date d'&eacute;ch&eacute;ance pour &eacute;viter toute interruption de service.")
    ) +
    cta("View Invoice", "Voir la facture", CTA_BASE + "/dashboard/invoices") + footer()
)))

# 12. Payment Receipt
TEMPLATES.append(("fin_payment_receipt_bilingual", wrap(
    zone1() + hero(C["green"], "&#9989;", "Payment Confirmed", "Paiement confirm&eacute;") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, your payment has been received and processed successfully.") +
        card(detail_table(
            kv_row("Transaction ID", "{{transaction_id}}") +
            kv_row("Amount Paid / Montant pay&eacute;", "{{amount}}", C["green"]) +
            kv_row("Invoice / Facture", "{{invoice_id}}")
        )) +
        p("A receipt has been saved to your account for your records.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, votre paiement a &eacute;t&eacute; re&ccedil;u et trait&eacute; avec succ&egrave;s.") +
        p("Un re&ccedil;u a &eacute;t&eacute; enregistr&eacute; dans votre compte pour vos dossiers.")
    ) +
    cta("View Receipt", "Voir le re&ccedil;u", CTA_BASE + "/dashboard/invoices") + footer()
)))

# 13. Payout Sent
TEMPLATES.append(("fin_payout_sent_bilingual", wrap(
    zone1() + hero(C["green"], "&#128184;", "Payout Sent!", "Versement envoy&eacute; !") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, great news! Your payout has been processed and sent to your bank account.") +
        card(detail_table(
            kv_row("Payout ID", "{{payout_id}}") +
            kv_row("Amount / Montant", "{{amount}}", C["green"]) +
            kv_row("Status", badge("SENT / ENVOY&Eacute;", C["green"]))
        )) +
        p("Please allow 2&ndash;5 business days for the funds to appear in your account.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, bonne nouvelle ! Votre versement a &eacute;t&eacute; trait&eacute; et envoy&eacute; &agrave; votre compte bancaire.") +
        p("Veuillez pr&eacute;voir 2 &agrave; 5 jours ouvrables pour que les fonds apparaissent dans votre compte.")
    ) +
    cta("View Payout History", "Voir l'historique des versements", CTA_BASE + "/dashboard") + footer()
)))

# 14. Invoice Overdue
TEMPLATES.append(("fin_invoice_overdue_bilingual", wrap(
    zone1() + hero(C["red"], "&#9888;", "Invoice Overdue — Action Required", "Facture en retard &mdash; Action requise") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, your invoice is now past due. Please make payment as soon as possible to avoid account restrictions.") +
        card(detail_table(
            kv_row("Invoice / Facture", "#{{invoice_number}}") +
            kv_row("Amount Due / Montant d&ucirc;", "{{amount}}", C["red"]) +
            kv_row("Original Due Date / &Eacute;ch&eacute;ance initiale", "{{due_date}}", C["red"]) +
            kv_row("Status", badge("OVERDUE / EN RETARD", C["red"]))
        )) +
        p("If you have already made payment, please disregard this notice.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, votre facture est maintenant en retard. Veuillez effectuer le paiement d&egrave;s que possible pour &eacute;viter des restrictions sur votre compte.") +
        p("Si vous avez d&eacute;j&agrave; effectu&eacute; le paiement, veuillez ignorer cet avis.")
    ) +
    cta("Pay Now", "Payer maintenant", CTA_BASE + "/dashboard/invoices") + footer()
)))

# ═══════════════════════════════════════════════════════════════
# SELLER TEMPLATES (3)
# ═══════════════════════════════════════════════════════════════

# 15. New Bid on Your Listing
TEMPLATES.append(("seller_new_bid_bilingual", wrap(
    zone1() + hero(C["green"], "&#128176;", "New Bid on Your Listing!", "Nouvelle ench&egrave;re sur votre annonce !") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, someone just placed a bid on your listing!") +
        card(detail_table(
            kv_row("Listing / Annonce", "{{auction_title}}") +
            kv_row("Bid Amount / Montant", "{{bid_amount}}", C["green"]) +
            kv_row("Bidder / Ench&eacute;risseur", "{{bidder_name}}")
        )) +
        p("Log in to track your listing's activity and manage bids.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, quelqu'un vient de placer une ench&egrave;re sur votre annonce !") +
        p("Connectez-vous pour suivre l'activit&eacute; de votre annonce et g&eacute;rer les ench&egrave;res.")
    ) +
    cta("View Listing", "Voir l'annonce", CTA_BASE + "/listing/{{auction_id}}") + footer()
)))

# 16. Listing Approved
TEMPLATES.append(("seller_listing_approved_bilingual", wrap(
    zone1() + hero(C["green"], "&#9989;", "Listing Approved!", "Annonce approuv&eacute;e !") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, your listing has been approved and is now live on BidVex!") +
        card(f'<p style="font-family:{FONT};font-size:16px;font-weight:bold;color:{C["navy"]};margin:0;">{{{{auction_title}}}}</p>') +
        p("Buyers can now view and bid on your item. Share the link to attract more bidders!") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, votre annonce a &eacute;t&eacute; approuv&eacute;e et est maintenant en ligne sur BidVex !") +
        p("Les acheteurs peuvent maintenant voir et ench&eacute;rir sur votre article. Partagez le lien pour attirer plus d'ench&eacute;risseurs !")
    ) +
    cta("View Your Listing", "Voir votre annonce", "{{auction_url}}") + footer()
)))

# 17. Listing Rejected
TEMPLATES.append(("seller_listing_rejected_bilingual", wrap(
    zone1() + hero(C["red"], "&#10060;", "Listing Rejected", "Annonce refus&eacute;e") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, unfortunately your listing has been rejected by our review team.") +
        card(
            f'<p style="font-family:{FONT};font-size:15px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">{{{{auction_title}}}}</p>'
            f'<p style="font-family:{FONT};font-size:13px;color:{C["text_med"]};margin:0 0 4px;">Reason / Raison :</p>'
            f'<p style="font-family:{FONT};font-size:14px;color:{C["red"]};margin:0;font-weight:bold;">{{{{reason}}}}</p>'
        ) +
        p("You may edit and resubmit your listing. If you have questions, please contact <a href=\"mailto:support@bidvex.com\" style=\"color:#2186C6;\">support@bidvex.com</a>.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, malheureusement, votre annonce a &eacute;t&eacute; refus&eacute;e par notre &eacute;quipe de r&eacute;vision.") +
        p("Vous pouvez modifier et resoumettre votre annonce. Pour toute question, contactez <a href=\"mailto:support@bidvex.com\" style=\"color:#2186C6;\">support@bidvex.com</a>.")
    ) +
    cta("Edit Listing", "Modifier l'annonce", CTA_BASE + "/dashboard/listings") + footer()
)))

# ═══════════════════════════════════════════════════════════════
# AUCTION TEMPLATES (3)
# ═══════════════════════════════════════════════════════════════

# 18. Auction Announcement
TEMPLATES.append(("auction_announcement_bilingual", wrap(
    zone1() + hero(C["navy"], "&#128227;", "New Auction: {{auction_title}}", "Nouvelle ench&egrave;re : {{auction_title}}") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, a new auction matching your interests is now live on BidVex!") +
        card(detail_table(
            kv_row("Auction / Ench&egrave;re", "{{auction_title}}") +
            kv_row("Starts / D&eacute;but", "{{start_date}}") +
            kv_row("Starting Price / Prix de d&eacute;part", "{{start_price}}")
        )) +
        p("Be the first to bid and get the best deal!") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, une nouvelle ench&egrave;re correspondant &agrave; vos int&eacute;r&ecirc;ts est maintenant en ligne sur BidVex !") +
        p("Soyez le premier &agrave; ench&eacute;rir et obtenez la meilleure offre !")
    ) +
    cta("View Auction", "Voir l'ench&egrave;re", CTA_BASE + "/listing/{{auction_id}}") + footer()
)))

# 19. Auction Reminder
TEMPLATES.append(("auction_reminder_bilingual", wrap(
    zone1() + hero(C["amber"], "&#9200;", "Auction Reminder: Ending Soon", "Rappel : Ench&egrave;re se terminant bient&ocirc;t") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, an auction you're watching is ending soon! Don't miss your chance to bid.") +
        card(detail_table(
            kv_row("Auction / Ench&egrave;re", "{{auction_title}}") +
            kv_row("Ends / Fin", "{{end_date}}", C["red"]) +
            kv_row("Current Bid / Ench&egrave;re actuelle", "{{current_bid}}", C["green"])
        )) +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, une ench&egrave;re que vous surveillez se termine bient&ocirc;t ! Ne manquez pas votre chance d'ench&eacute;rir.") +
        p("Agissez maintenant avant qu'il ne soit trop tard.")
    ) +
    cta("Place Your Bid", "Placer votre ench&egrave;re", CTA_BASE + "/listing/{{auction_id}}") + footer()
)))

# 20. Auction Results
TEMPLATES.append(("auction_results_bilingual", wrap(
    zone1() + hero(C["navy"], "&#127942;", "Auction Results", "R&eacute;sultats de l'ench&egrave;re") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, the auction has ended. Here are the results:") +
        card(detail_table(
            kv_row("Auction / Ench&egrave;re", "{{auction_title}}") +
            kv_row("Winning Bid / Ench&egrave;re gagnante", "{{winning_bid}}", C["green"]) +
            kv_row("Total Bids / Ench&egrave;res totales", "{{total_bids}}")
        )) +
        p("Thank you for participating. Stay tuned for upcoming auctions!") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, l'ench&egrave;re est termin&eacute;e. Voici les r&eacute;sultats :") +
        p("Merci de votre participation. Restez &agrave; l'aff&ucirc;t des prochaines ench&egrave;res !")
    ) +
    cta("Browse More Auctions", "Parcourir d'autres ench&egrave;res", CTA_BASE + "/marketplace") + footer()
)))

# ═══════════════════════════════════════════════════════════════
# BID TEMPLATES (3)
# ═══════════════════════════════════════════════════════════════

# 21. Outbid Notification
TEMPLATES.append(("bid_outbid_bilingual", wrap(
    zone1() + hero(C["amber"], "&#128680;", "You've Been Outbid!", "Vous avez &eacute;t&eacute; surench&eacute;ri !") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, another bidder has placed a higher bid on an item you're watching.") +
        card(detail_table(
            kv_row("Auction / Ench&egrave;re", "{{auction_title}}") +
            kv_row("New Highest Bid / Nouvelle ench&egrave;re", "{{current_highest_bid}}", C["red"])
        )) +
        p("Act now to reclaim the lead!") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, un autre ench&eacute;risseur a plac&eacute; une ench&egrave;re plus &eacute;lev&eacute;e sur un article que vous surveillez.") +
        p("Agissez maintenant pour reprendre la t&ecirc;te !")
    ) +
    cta("Bid Again", "Ench&eacute;rir &agrave; nouveau", CTA_BASE + "/listing/{{auction_id}}") + footer()
)))

# 22. Bid Confirmed
TEMPLATES.append(("bid_confirmed_bilingual", wrap(
    zone1() + hero(C["green"], "&#9989;", "Bid Confirmed!", "Ench&egrave;re confirm&eacute;e !") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, your bid has been successfully placed.") +
        card(detail_table(
            kv_row("Auction / Ench&egrave;re", "{{auction_title}}") +
            kv_row("Your Bid / Votre ench&egrave;re", "{{bid_amount}}", C["green"])
        )) +
        p("We'll notify you if someone outbids you. Good luck!") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, votre ench&egrave;re a &eacute;t&eacute; plac&eacute;e avec succ&egrave;s.") +
        p("Nous vous notifierons si quelqu'un surench&eacute;rit. Bonne chance !")
    ) +
    cta("Track Auction", "Suivre l'ench&egrave;re", CTA_BASE + "/listing/{{auction_id}}") + footer()
)))

# 23. Winning Bid
TEMPLATES.append(("bid_winning_bilingual", wrap(
    zone1() + hero(C["green"], "&#127881;", "Congratulations — You Won!", "F&eacute;licitations &mdash; Vous avez gagn&eacute; !") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, congratulations! You have the winning bid on the following auction:") +
        card(detail_table(
            kv_row("Auction / Ench&egrave;re", "{{auction_title}}") +
            kv_row("Winning Bid / Ench&egrave;re gagnante", "{{bid_amount}}", C["green"])
        )) +
        p("Please complete the payment process to finalize your purchase. The seller will be notified once your payment is confirmed.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, f&eacute;licitations ! Vous avez l'ench&egrave;re gagnante sur l'ench&egrave;re suivante :") +
        p("Veuillez compl&eacute;ter le processus de paiement pour finaliser votre achat. Le vendeur sera notifi&eacute; une fois votre paiement confirm&eacute;.")
    ) +
    cta("Complete Payment", "Compl&eacute;ter le paiement", CTA_BASE + "/listing/{{auction_id}}") + footer()
)))

# ═══════════════════════════════════════════════════════════════
# AFFILIATE TEMPLATES (4)
# ═══════════════════════════════════════════════════════════════

# 24. Monthly Earnings
TEMPLATES.append(("affiliate_monthly_earnings_bilingual", wrap(
    zone1() + hero(C["green"], "&#128176;", "Your Monthly Earnings Report", "Votre rapport de revenus mensuel") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, here's your affiliate earnings summary for {{period}}:") +
        card(detail_table(
            kv_row("Period / P&eacute;riode", "{{period}}") +
            kv_row("Total Earnings / Revenus totaux", "{{total_earnings}}", C["green"]) +
            kv_row("New Referrals / Nouvelles r&eacute;f&eacute;rences", "{{new_referrals}}") +
            kv_row("Payout Date / Date de versement", "{{payout_date}}")
        )) +
        p("Thank you for being a valued BidVex affiliate partner!") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, voici votre sommaire de revenus d'affiliation pour {{period}} :") +
        p("Merci d'&ecirc;tre un partenaire affili&eacute; pr&eacute;cieux de BidVex !")
    ) +
    cta("View Dashboard", "Voir le tableau de bord", CTA_BASE + "/dashboard/affiliate") + footer()
)))

# 25. Commission Earned
TEMPLATES.append(("affiliate_commission_earned_bilingual", wrap(
    zone1() + hero(C["green"], "&#128181;", "Commission Earned!", "Commission gagn&eacute;e !") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, you just earned a commission from a referral's activity on BidVex!") +
        card(detail_table(
            kv_row("Commission / Commission", "{{commission_amount}}", C["green"]) +
            kv_row("From Referral / De la r&eacute;f&eacute;rence", "{{referral_name}}")
        )) +
        p("Keep sharing your referral link to earn more!") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, vous venez de gagner une commission gr&acirc;ce &agrave; l'activit&eacute; d'une r&eacute;f&eacute;rence sur BidVex !") +
        p("Continuez &agrave; partager votre lien de r&eacute;f&eacute;rence pour gagner davantage !")
    ) +
    cta("View Earnings", "Voir les revenus", CTA_BASE + "/dashboard/affiliate") + footer()
)))

# 26. Referral Notification
TEMPLATES.append(("affiliate_referral_notification_bilingual", wrap(
    zone1() + hero(C["blue"], "&#128101;", "New Referral Signup!", "Nouvelle inscription par r&eacute;f&eacute;rence !") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, someone just signed up on BidVex using your referral link!") +
        card(detail_table(
            kv_row("New Member / Nouveau membre", "{{referral_name}}")
        )) +
        p("You'll earn commissions on their activity. Share your link with more people to maximize your earnings.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, quelqu'un vient de s'inscrire sur BidVex en utilisant votre lien de r&eacute;f&eacute;rence !") +
        p("Vous gagnerez des commissions sur leur activit&eacute;. Partagez votre lien avec d'autres personnes pour maximiser vos revenus.")
    ) +
    cta("View Referrals", "Voir les r&eacute;f&eacute;rences", CTA_BASE + "/dashboard/affiliate") + footer()
)))

# 27. Program Summary
TEMPLATES.append(("affiliate_program_summary_bilingual", wrap(
    zone1() + hero(C["navy"], "&#128202;", "Affiliate Program Summary", "Sommaire du programme d'affiliation") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, here's an overview of your BidVex affiliate program performance:") +
        card(detail_table(
            kv_row("Total Referrals / R&eacute;f&eacute;rences totales", "{{total_referrals}}") +
            kv_row("Total Earnings / Revenus totaux", "{{total_earnings}}", C["green"]) +
            kv_row("Active Referrals / R&eacute;f&eacute;rences actives", "{{active_referrals}}") +
            kv_row("Conversion Rate / Taux de conversion", "{{conversion_rate}}")
        )) +
        p("Keep up the great work! Share your referral link to grow your network.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, voici un aper&ccedil;u de la performance de votre programme d'affiliation BidVex :") +
        p("Continuez votre excellent travail ! Partagez votre lien pour agrandir votre r&eacute;seau.")
    ) +
    cta("View Full Report", "Voir le rapport complet", CTA_BASE + "/dashboard/affiliate") + footer()
)))

# ═══════════════════════════════════════════════════════════════
# TRIGGER TEMPLATES (2)
# ═══════════════════════════════════════════════════════════════

# 28. Auction Ending Soon (Trigger — for bidders/watchers)
TEMPLATES.append(("trigger_auction_ending_soon_bilingual", wrap(
    zone1() + hero(C["red"], "&#9203;", "Auction Ending Soon!", "Ench&egrave;re se terminant bient&ocirc;t !") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, an auction you've bid on or watched is about to close!") +
        card(detail_table(
            kv_row("Auction / Ench&egrave;re", "{{item_name}}") +
            kv_row("Current Highest Bid", "{{current_highest_bid}}", C["green"]) +
            kv_row("Your Last Bid / Votre ench&egrave;re", "{{user_last_bid}}") +
            kv_row("Time Left / Temps restant", "{{time_remaining}}", C["red"])
        )) +
        p("Don't let this one slip away. Place your final bid now!") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, une ench&egrave;re sur laquelle vous avez ench&eacute;ri ou que vous surveillez est sur le point de se terminer !") +
        p("Ne laissez pas celle-ci vous &eacute;chapper. Placez votre ench&egrave;re finale maintenant !")
    ) +
    cta("Bid Now", "Ench&eacute;rir maintenant", CTA_BASE + "/listing/{{auction_id}}") + footer()
)))

# 29. Cross-Border Purchase Notice
TEMPLATES.append(("trigger_cross_border_notice_bilingual", wrap(
    zone1() + hero(C["amber"], "&#127760;", "Cross-Border Purchase Notice", "Avis d'achat transfrontalier") +
    body(
        lang_label("ENGLISH") +
        p("Hi {{first_name}}, congratulations on winning a cross-border auction! Please review the following compliance requirements before finalizing your purchase:") +
        card(
            f'<p style="font-family:{FONT};font-size:14px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">{{{{item_name}}}}</p>'
            + detail_table(
                kv_row("Hammer Price / Prix marteau", "{{hammer_price}}", C["green"])
            )
        ) +
        card(
            f'<p style="font-family:{FONT};font-size:13px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">Compliance Checklist / Liste de conformit&eacute;</p>'
            f'<ul style="font-family:{FONT};font-size:13px;color:{C["text_dark"]};line-height:1.8;margin:0;padding-left:18px;">'
            f'<li>CBSA Import Declaration</li>'
            f'<li>RIV Inspection (vehicles)</li>'
            f'<li>CFIA Soil Declaration (heavy equipment)</li>'
            f'<li>CBP Export Clearance (if applicable)</li>'
            f'<li>SAAQ Registration (QC vehicles)</li>'
            f'<li>RDPRM Lien Verification</li>'
            f'</ul>'
        ) +
        p("For more information, visit our <a href=\"" + CTA_BASE + "/legal\" style=\"color:#2186C6;\">Cross-Border Guide</a>.") +
        divider() +
        lang_label("FRAN&Ccedil;AIS") +
        p("Bonjour {{first_name}}, f&eacute;licitations pour avoir remport&eacute; une ench&egrave;re transfrontali&egrave;re ! Veuillez consulter les exigences de conformit&eacute; suivantes avant de finaliser votre achat :") +
        card(
            f'<p style="font-family:{FONT};font-size:13px;font-weight:bold;color:{C["navy"]};margin:0 0 8px;">Liste de conformit&eacute;</p>'
            f'<ul style="font-family:{FONT};font-size:13px;color:{C["text_dark"]};line-height:1.8;margin:0;padding-left:18px;">'
            f'<li>D&eacute;claration d\'importation ASFC</li>'
            f'<li>Inspection RIV (v&eacute;hicules)</li>'
            f'<li>D&eacute;claration de sol ACIA (&eacute;quipement lourd)</li>'
            f'<li>D&eacute;douanement CBP (si applicable)</li>'
            f'<li>Immatriculation SAAQ (v&eacute;hicules QC)</li>'
            f'<li>V&eacute;rification de privilège RDPRM</li>'
            f'</ul>'
        ) +
        p("Pour plus d'information, consultez notre <a href=\"" + CTA_BASE + "/legal\" style=\"color:#2186C6;\">Guide transfrontalier</a>.")
    ) +
    cta("View Purchase Details", "Voir les d&eacute;tails de l'achat", CTA_BASE + "/listing/{{auction_id}}") + footer()
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
