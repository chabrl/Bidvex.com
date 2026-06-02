"""
BidVex Email Notification Service
Sends transactional emails for vehicle auctions
"""

import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Email configuration
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "support@bidvex.com")
FROM_NAME = os.environ.get("SENDGRID_FROM_NAME", "BidVex")

# iter254 Mission 4 — Canonical outbound branding constants.
# Use these to override the From/Reply-To headers for branded paths
# without polluting the global SENDGRID_FROM_EMAIL env default.
B2B_PARTNER_FROM_EMAIL = "partners@bidvex.ca"
B2B_PARTNER_FROM_NAME = "BidVex Partner Program"
TRANSACTIONAL_FROM_EMAIL = "support@bidvex.com"
TRANSACTIONAL_FROM_NAME = "BidVex"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://www.bidvex.com")

# Check if SendGrid is available
SENDGRID_AVAILABLE = False
sg = None

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail, Email, To, Content, Attachment, FileContent, FileName, FileType, Disposition
    if SENDGRID_API_KEY and SENDGRID_API_KEY != "SG.your-actual-sendgrid-key-here":
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        SENDGRID_AVAILABLE = True
        logger.info("SendGrid email service initialized")
    else:
        logger.warning("SendGrid API key not configured - emails will be logged only")
except ImportError:
    logger.warning("SendGrid not installed - emails will be logged only")


def _format_currency(amount) -> str:
    """Format amount as currency"""
    return f"${float(amount):,.2f}"


def _format_date(dt) -> str:
    """Format datetime for display"""
    if isinstance(dt, str):
        dt = datetime.fromisoformat(dt.replace('Z', '+00:00'))
    return dt.strftime("%B %d, %Y at %I:%M %p")


def _detect_language(*sources) -> str:
    """iter249 Mission 3 — Resolve the recipient language from any of
    the supplied source dicts/strings. Priority:
      1. `preferred_language` / `language` field (any source).
      2. `province` field (any source) — `"QC"` → French.
      3. Default → English.

    Each source can be a dict (user, invoice, etc.) or a raw province
    string. The first non-empty signal wins.
    """
    for src in sources:
        if not src:
            continue
        if isinstance(src, str):
            if src.upper().strip() == "QC":
                return "fr"
            continue
        pref = (src.get("preferred_language") or src.get("language")
                or src.get("buyer_preferred_language")
                or src.get("buyer_language") or "").lower().strip()
        if pref:
            return "fr" if pref.startswith("fr") else "en"
        prov = (src.get("province") or src.get("buyer_province") or "").upper().strip()
        if prov == "QC":
            return "fr"
    return "en"


def _format_currency_fr(amount) -> str:
    """Format amount as French-Canadian currency (`10 000,00 $`)."""
    s = f"{float(amount):,.2f}"
    return s.replace(",", " ").replace(".", ",") + " $"




async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    attachments: List[Dict] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    reply_to: Optional[str] = None,
    is_marketing: bool = False,
) -> Dict[str, Any]:
    """iter244 Mission 2 — Canonical low-level SendGrid dispatcher.
    iter254 Mission 4 — Now accepts optional `from_email`/`from_name`/
    `reply_to` overrides so individual outbound paths can stamp branded
    headers (`partners@bidvex.ca` for B2B blasts, `support@bidvex.com`
    for transactional). Defaults preserve the existing global FROM.

    iter266 Mission 2 — Universal suppression gate. Skips every send
    (including raw-HTML and html_full_override paths) when the
    recipient is in `email_suppressions` OR (for marketing emails) has
    `marketing_unsubscribed=True` on their user record. Returns a
    `{"status": "skipped", "reason": ...}` envelope without any
    SendGrid round-trip.
    """
    # iter266 Mission 2 — suppression gate covering ALL outbound paths.
    try:
        from routes.unsubscribe import is_marketing_suppressed as _suppress_check
        from deps import get_db as _get_db
        if to_email:
            _norm = to_email.strip().lower()
            _db = _get_db()
            _hit = await _db.email_suppressions.find_one(
                {"email": _norm}, {"_id": 0, "email": 1}
            )
            if _hit:
                logger.info(f"[email-suppressed] {to_email} — global unsubscribe — skipping send")
                return {
                    "status": "skipped",
                    "reason": "unsubscribed",
                    "to": to_email,
                    "subject": subject,
                }
            if is_marketing and await _suppress_check(_norm):
                logger.info(f"[email-suppressed] {to_email} — marketing opt-out — skipping send")
                return {
                    "status": "skipped",
                    "reason": "marketing_suppressed",
                    "to": to_email,
                    "subject": subject,
                }
    except Exception as _exc:  # noqa: BLE001
        # Defensive: never let the suppression check break a transactional send.
        logger.debug(f"[email-suppression-check] skipped: {_exc}")

    if not SENDGRID_AVAILABLE:
        logger.info(f"[EMAIL LOG] To: {to_email}, Subject: {subject}")
        logger.debug(f"[EMAIL CONTENT] {html_content[:500]}...")
        return {
            "status": "logged",
            "message": "SendGrid not configured - email logged",
            "from_email": from_email or FROM_EMAIL,
            "from_name": from_name or FROM_NAME,
            "reply_to": reply_to,
        }
    
    try:
        _from = from_email or FROM_EMAIL
        _from_name = from_name or FROM_NAME
        message = Mail(
            from_email=Email(_from, _from_name),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", html_content)
        )
        if reply_to:
            try:
                from sendgrid.helpers.mail import ReplyTo as _ReplyTo
                message.reply_to = _ReplyTo(reply_to)
            except Exception:
                # ReplyTo class import may differ between SendGrid SDK
                # versions; fall back to setting the attribute directly.
                message.reply_to = Email(reply_to)
        
        # Add attachments if any
        if attachments:
            for att in attachments:
                attachment = Attachment(
                    FileContent(att["content"]),
                    FileName(att["filename"]),
                    FileType(att["type"]),
                    Disposition("attachment")
                )
                message.add_attachment(attachment)
        
        logger.info(f"[EMAIL_DEBUG] Sending email to: {to_email} | Subject: {subject} | From: {FROM_EMAIL}")
        response = sg.send(message)
        
        logger.info(f"[EMAIL_DEBUG] SendGrid response for {to_email}: status_code={response.status_code}")
        
        return {
            "status": "sent",
            "status_code": response.status_code,
            "to": to_email,
            "subject": subject
        }
    except Exception as e:
        logger.error(f"[EMAIL_DEBUG] FAILED to send email to {to_email}: {e}")
        return {"status": "error", "message": str(e)}


async def send_unified_email(
    email_type: str,
    user: Dict[str, Any],
    data: Optional[Dict[str, Any]] = None,
    *,
    lang: str = "en",
    attachments: Optional[List[Dict]] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    reply_to: Optional[str] = None,
    is_marketing: bool = False,
) -> Dict[str, Any]:
    """iter239 Mission 6 — Canonical email dispatch using the unified
    `build_email_payload()` mapping engine.

    This is the new entry-point for ALL transactional emails. Pass the
    `email_type` (e.g. `welcome`, `bid_placed`, `outbid`, `auction_won`,
    `auction_ending_soon`, `voicemail`, `ai_suggestion`, `new_feature`,
    `password_reset`, `onboarding_reminder`) plus the user + data context.

    iter244 Mission 2 — Three optional override paths in `data` preserve
    legacy compliance HTML byte-for-byte:
      - `html_full_override`: send the HTML verbatim (no wrapping)
      - `body_html_override`: wrap inside BIDVEX header/footer chrome
      - `subject_override`:   override the registry's auto-derived subject

    iter254 Mission 4 — Optional from_email/from_name/reply_to overrides
    let callers stamp branded outbound headers (e.g. `partners@bidvex.ca`
    for B2B blasts, `support@bidvex.com` for transactional).

    iter266 Mission 2 — `is_marketing=True` activates the marketing
    suppression gate so opt-out users never receive promo blasts even
    when callers route through this unified path.
    """
    from services.email_templates import build_email_payload
    payload = build_email_payload(email_type, user=user, data=data or {}, lang=lang)
    return await send_email(
        to_email=payload["to_email"],
        subject=payload["subject"],
        html_content=payload["html_content"],
        attachments=attachments,
        from_email=from_email,
        from_name=from_name,
        reply_to=reply_to,
        is_marketing=is_marketing,
    )


async def _send_via_unified(
    *,
    to_email: str,
    subject: str,
    html_content: str,
    first_name: str = "",
    attachments: Optional[List[Dict]] = None,
) -> Dict[str, Any]:
    """iter244 Mission 2 — Internal shim that routes a legacy "I already
    have rich HTML" callsite through `send_unified_email()` with the
    `html_full_override` passthrough. Every migrated legacy helper now
    calls this instead of the raw `send_email()` so that we get a single
    consolidated outbound path.
    """
    return await send_unified_email(
        "new_feature",  # placeholder type — overridden by html_full_override
        user={"email": to_email, "first_name": first_name},
        data={
            "html_full_override": html_content,
            "subject_override": subject,
        },
        attachments=attachments,
    )


# ===== EMAIL TEMPLATES =====

def _section_label(auction_type: Optional[str] = None) -> Dict[str, str]:
    """Map an auction's source section to its branded header / icon / color.

    Used by the email base template and every transactional email so the
    "🚗 BidVex Vehicle Auctions" style header never shows for a Marketplace
    item (or vice versa).

    Returns dict with keys: name_en, name_fr, icon, color.
    """
    at = (auction_type or "").strip().lower()
    if at in ("marketplace", "general", "single", "listing"):
        return {"name_en": "BidVex Marketplace", "name_fr": "BidVex Marketplace",
                "icon": "🏷️", "color": "#0ea5e9"}  # sky blue
    if at in ("lots", "lot", "multi_item", "multi-item", "multi_item_listing"):
        return {"name_en": "BidVex Lots Auction", "name_fr": "BidVex Enchères par lots",
                "icon": "📦", "color": "#8b5cf6"}  # violet
    if at in ("storage", "storage_auction", "storage_auctions"):
        return {"name_en": "BidVex Storage Auctions", "name_fr": "BidVex Enchères d'entreposage",
                "icon": "🔐", "color": "#f59e0b"}  # amber
    if at in ("vehicle", "vehicles", "vehicle_auction", "vehicle_auctions", "car", "auto"):
        return {"name_en": "BidVex Vehicle Auctions", "name_fr": "BidVex Enchères de véhicules",
                "icon": "🚗", "color": "#2563eb"}  # blue
    # Fallback
    return {"name_en": "BidVex Auctions", "name_fr": "BidVex Enchères",
            "icon": "🔨", "color": "#0f172a"}


def _base_template(content: str, title: str = "BidVex Notification",
                   auction_type: Optional[str] = None) -> str:
    """Base HTML email template with dynamic section branding.

    Pass `auction_type` so the header reflects the item's source section
    (marketplace / lots / storage / vehicle) instead of a hardcoded value.
    """
    label = _section_label(auction_type)
    header_bg = label["color"]
    header_text = f'{label["icon"]} {label["name_en"]}'
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>{title}</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; background-color: #f1f5f9;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f1f5f9; padding: 40px 20px;">
            <tr>
                <td align="center">
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 12px; box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);">
                        <!-- Header -->
                        <tr>
                            <td style="background-color: {header_bg}; padding: 30px; border-radius: 12px 12px 0 0;">
                                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: bold;">
                                    {header_text}
                                </h1>
                            </td>
                        </tr>
                        <!-- Content -->
                        <tr>
                            <td style="padding: 40px 30px;">
                                {content}
                            </td>
                        </tr>
                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #f8fafc; padding: 20px 30px; border-radius: 0 0 12px 12px; border-top: 1px solid #e2e8f0;">
                                <p style="margin: 0; font-size: 12px; color: #64748b; text-align: center;">
                                    © 2026 BidVex Inc. All rights reserved.<br>
                                    <a href="{FRONTEND_URL}/privacy-policy" style="color: #2563eb;">Privacy Policy</a> | 
                                    <a href="{FRONTEND_URL}/terms-of-service" style="color: #2563eb;">Terms of Service</a>
                                </p>
                            </td>
                        </tr>
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """


# ===== INVOICE EMAILS =====


async def send_welcome_email(user_email: str, user_name: str) -> Dict[str, Any]:
    """
    Send premium bilingual welcome email — BidVex Ecosystem.
    French (top) → English (bottom), separated by grey divider.
    High-end branded HTML with hero image, two-column advantage grid, CTA.
    """
    logger.info(f"[EMAIL_DEBUG] Triggering Welcome Email for: {user_email} | User: {user_name}")

    HERO_IMG = "https://images.unsplash.com/photo-1774867559682-e856ab83a7db?w=1200&q=80&auto=format"
    MARKETPLACE_URL = "https://bidvex.com/marketplace"
    PRIVACY_URL = "https://bidvex.com/legal"
    TERMS_URL = "https://bidvex.com/legal"

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Bienvenue chez BidVex / Welcome to BidVex</title>
</head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;background-color:#f0f4f8;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f0f4f8;padding:32px 16px;">
<tr><td align="center">
<table width="640" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 8px 30px rgba(0,0,0,0.08);">

  <!-- Logo Header -->
  <tr>
    <td style="background:linear-gradient(135deg,#1e40af 0%,#2563eb 100%);padding:28px 32px;text-align:center;">
      <h1 style="margin:0;color:#ffffff;font-size:28px;font-weight:800;letter-spacing:-0.5px;">
        BidVex
      </h1>
      <p style="margin:6px 0 0;color:#93c5fd;font-size:12px;text-transform:uppercase;letter-spacing:2px;font-weight:600;">
        Auction Ecosystem / Écosystème d'enchères
      </p>
    </td>
  </tr>

  <!-- Hero Image -->
  <tr>
    <td>
      <img src="{HERO_IMG}" alt="BidVex All-in-One Marketplace — Heavy equipment, vehicles, and industrial assets / Marché tout-en-un BidVex — Équipement lourd, véhicules et actifs industriels" width="640" style="display:block;width:100%;height:auto;max-height:260px;object-fit:cover;" />
    </td>
  </tr>

  <!-- ═══════ FRENCH SECTION ═══════ -->
  <tr>
    <td style="padding:36px 32px 24px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="border-left:4px solid #2563eb;padding-left:16px;">
            <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:#2563eb;font-weight:700;">Français</p>
            <h2 style="margin:0;color:#0f172a;font-size:24px;font-weight:700;">Bienvenue chez BidVex, {user_name} !</h2>
          </td>
        </tr>
      </table>
      <p style="color:#475569;font-size:15px;line-height:1.7;margin:18px 0;">
        Vous venez de rejoindre la plateforme &laquo; tout-en-un &raquo; la plus avancée en Amérique du Nord. Que vous cherchiez une flotte de camions, une pièce de collection unique ou que vous souhaitiez liquider un entrepôt complet d'équipement industriel, BidVex est conçu pour tout gérer.
      </p>

      <!-- Advantage Grid FR -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 0;">
        <tr>
          <td width="50%" valign="top" style="padding:8px 12px 8px 0;">
            <table cellpadding="0" cellspacing="0" style="background:#eff6ff;border-radius:10px;padding:16px;width:100%;">
              <tr>
                <td style="padding:0 0 8px;font-size:22px;">&#128722;</td>
              </tr>
              <tr>
                <td style="font-size:13px;font-weight:700;color:#1e3a5f;">Marché tout-en-un</td>
              </tr>
              <tr>
                <td style="font-size:12px;color:#475569;line-height:1.5;padding-top:4px;">Des véhicules et de la machinerie lourde aux lots d'articles multiples.</td>
              </tr>
            </table>
          </td>
          <td width="50%" valign="top" style="padding:8px 0 8px 12px;">
            <table cellpadding="0" cellspacing="0" style="background:#eff6ff;border-radius:10px;padding:16px;width:100%;">
              <tr>
                <td style="padding:0 0 8px;font-size:22px;">&#129302;</td>
              </tr>
              <tr>
                <td style="font-size:13px;font-weight:700;color:#1e3a5f;">Outils propulsés par l'IA</td>
              </tr>
              <tr>
                <td style="font-size:12px;color:#475569;line-height:1.5;padding-top:4px;">Notre concierge intelligent est prêt à vous aider 24/7.</td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td colspan="2" valign="top" style="padding:8px 0 0;">
            <table cellpadding="0" cellspacing="0" style="background:#eff6ff;border-radius:10px;padding:16px;width:100%;">
              <tr>
                <td style="padding:0 0 8px;font-size:22px;">&#127760;</td>
              </tr>
              <tr>
                <td style="font-size:13px;font-weight:700;color:#1e3a5f;">Bilingue et transfrontalier</td>
              </tr>
              <tr>
                <td style="font-size:12px;color:#475569;line-height:1.5;padding-top:4px;">Achetez ou vendez partout au Canada et aux États-Unis.</td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ═══════ DIVIDER ═══════ -->
  <tr>
    <td style="padding:0 32px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="border-top:2px solid #e2e8f0;height:1px;font-size:0;line-height:0;">&nbsp;</td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ═══════ ENGLISH SECTION ═══════ -->
  <tr>
    <td style="padding:24px 32px 36px;">
      <table width="100%" cellpadding="0" cellspacing="0">
        <tr>
          <td style="border-left:4px solid #2563eb;padding-left:16px;">
            <p style="margin:0 0 4px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:#2563eb;font-weight:700;">English</p>
            <h2 style="margin:0;color:#0f172a;font-size:24px;font-weight:700;">Welcome to BidVex, {user_name}!</h2>
          </td>
        </tr>
      </table>
      <p style="color:#475569;font-size:15px;line-height:1.7;margin:18px 0;">
        You've just joined North America's most advanced all-in-one marketplace. Whether you are looking for a fleet of trucks, a single rare collectible, or liquidating an entire warehouse of industrial equipment, BidVex is built to handle it all.
      </p>

      <!-- Advantage Grid EN -->
      <table width="100%" cellpadding="0" cellspacing="0" style="margin:8px 0 0;">
        <tr>
          <td width="50%" valign="top" style="padding:8px 12px 8px 0;">
            <table cellpadding="0" cellspacing="0" style="background:#eff6ff;border-radius:10px;padding:16px;width:100%;">
              <tr>
                <td style="padding:0 0 8px;font-size:22px;">&#128722;</td>
              </tr>
              <tr>
                <td style="font-size:13px;font-weight:700;color:#1e3a5f;">All-In-One Marketplace</td>
              </tr>
              <tr>
                <td style="font-size:12px;color:#475569;line-height:1.5;padding-top:4px;">From vehicles and heavy machinery to multi-item lots.</td>
              </tr>
            </table>
          </td>
          <td width="50%" valign="top" style="padding:8px 0 8px 12px;">
            <table cellpadding="0" cellspacing="0" style="background:#eff6ff;border-radius:10px;padding:16px;width:100%;">
              <tr>
                <td style="padding:0 0 8px;font-size:22px;">&#129302;</td>
              </tr>
              <tr>
                <td style="font-size:13px;font-weight:700;color:#1e3a5f;">AI-Powered Tools</td>
              </tr>
              <tr>
                <td style="font-size:12px;color:#475569;line-height:1.5;padding-top:4px;">Our intelligent concierge is ready to help you 24/7.</td>
              </tr>
            </table>
          </td>
        </tr>
        <tr>
          <td colspan="2" valign="top" style="padding:8px 0 0;">
            <table cellpadding="0" cellspacing="0" style="background:#eff6ff;border-radius:10px;padding:16px;width:100%;">
              <tr>
                <td style="padding:0 0 8px;font-size:22px;">&#127760;</td>
              </tr>
              <tr>
                <td style="font-size:13px;font-weight:700;color:#1e3a5f;">Bilingual &amp; Cross-Border</td>
              </tr>
              <tr>
                <td style="font-size:12px;color:#475569;line-height:1.5;padding-top:4px;">Seamlessly buy or sell across Canada and the US.</td>
              </tr>
            </table>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ═══════ CTA BUTTON ═══════ -->
  <tr>
    <td style="padding:0 32px 40px;text-align:center;">
      <table cellpadding="0" cellspacing="0" align="center">
        <tr>
          <td style="background:linear-gradient(135deg,#1e40af 0%,#2563eb 100%);border-radius:12px;padding:18px 48px;">
            <a href="{MARKETPLACE_URL}" style="color:#ffffff;text-decoration:none;font-size:16px;font-weight:700;display:inline-block;letter-spacing:0.3px;">
              Explorer le marché / Explore the Marketplace
            </a>
          </td>
        </tr>
      </table>
    </td>
  </tr>

  <!-- ═══════ FOOTER ═══════ -->
  <tr>
    <td style="background-color:#f8fafc;padding:24px 32px;border-top:1px solid #e2e8f0;border-radius:0 0 16px 16px;">
      <p style="margin:0;font-size:12px;color:#94a3b8;text-align:center;line-height:1.6;">
        &copy; 2026 BidVex Inc. Based in Sherbrooke, QC.<br/>
        <a href="{PRIVACY_URL}" style="color:#2563eb;text-decoration:none;">Privacy Policy</a> &nbsp;|&nbsp;
        <a href="{TERMS_URL}" style="color:#2563eb;text-decoration:none;">Terms of Service</a>
      </p>
    </td>
  </tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    result = await _send_via_unified(
        to_email=user_email,
        subject="Welcome to the BidVex Ecosystem! / Bienvenue dans l'écosystème BidVex !",
        html_content=html
    )

    logger.info(f"[EMAIL_DEBUG] Welcome Email result for {user_email}: {result}")
    return result

async def send_invoice_created_email(invoice: Dict[str, Any]) -> Dict[str, Any]:
    """Send email when a new invoice is generated. iter249 — language-aware."""
    lang = _detect_language(invoice)
    is_fr = lang == "fr"
    title = "Facture générée" if is_fr else "Invoice Generated"
    intro = (
        "Félicitations ! Votre enchère gagnante a été traitée. Voici les détails de votre facture :"
        if is_fr else
        "Congratulations! Your winning bid has been processed. Here are your invoice details:"
    )
    lbl_inv = "Facture nº :" if is_fr else "Invoice #:"
    lbl_veh = "Véhicule :" if is_fr else "Vehicle:"
    lbl_hammer = "Prix marteau :" if is_fr else "Hammer Price:"
    lbl_total = "Total à payer :" if is_fr else "Total Due:"
    lbl_due = "Échéance :" if is_fr else "Due Date:"
    cta = "Voir et payer la facture" if is_fr else "View & Pay Invoice"
    fine_print = (
        "Le paiement est dû dans les 14 jours. Tout retard peut entraîner une pénalité mensuelle de 2 %."
        if is_fr else
        "Payment is due within 14 days. Late payments may incur a 2% monthly penalty."
    )
    fmt_money = _format_currency_fr if is_fr else _format_currency

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #1e293b;">{title}</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        {intro}
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #f8fafc; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_inv}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('invoice_number', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_veh}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('vehicle_title', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_hammer}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{fmt_money(invoice.get('hammer_price', 0))}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_total}</strong></td>
                <td style="padding: 8px 0; text-align: right; font-size: 18px; color: #2563eb; font-weight: bold;">
                    {fmt_money(invoice.get('total_amount', 0))}
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_due}</strong></td>
                <td style="padding: 8px 0; text-align: right; color: #f59e0b;">
                    {_format_date(invoice.get('due_at', invoice.get('payment_deadline')))}
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #2563eb; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/invoices/{invoice.get('id')}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">{cta}</a>
            </td>
        </tr>
    </table>
    
    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        {fine_print}
    </p>
    """
    subject = (
        f"Facture nº{invoice.get('invoice_number')} — {invoice.get('vehicle_title')}"
        if is_fr else
        f"Invoice #{invoice.get('invoice_number')} - {invoice.get('vehicle_title')}"
    )
    return await _send_via_unified(
        to_email=invoice.get('buyer_email'),
        subject=subject,
        html_content=_base_template(content, title)
    )


async def send_payment_confirmation_email(invoice: Dict[str, Any]) -> Dict[str, Any]:
    """Send email when payment is received. iter249 — language-aware."""
    lang = _detect_language(invoice)
    is_fr = lang == "fr"
    title = "✓ Paiement reçu" if is_fr else "✓ Payment Received"
    intro = (
        "Merci ! Votre paiement a été traité avec succès."
        if is_fr else
        "Thank you! Your payment has been successfully processed."
    )
    confirmed_lbl = "Paiement confirmé" if is_fr else "Payment Confirmed"
    lbl_inv = "Facture nº :" if is_fr else "Invoice #:"
    lbl_veh = "Véhicule :" if is_fr else "Vehicle:"
    lbl_date = "Date de paiement :" if is_fr else "Payment Date:"
    seller_note = (
        "Le vendeur a été notifié et coordonnera la prise en charge ou la livraison du véhicule avec vous."
        if is_fr else
        "The seller has been notified and will coordinate vehicle pickup/delivery with you."
    )
    cta = "Voir le reçu" if is_fr else "View Receipt"
    fmt_money = _format_currency_fr if is_fr else _format_currency

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">{title}</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        {intro}
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #d1fae5; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #065f46; font-size: 14px;">{confirmed_lbl}</p>
        <p style="margin: 10px 0 0 0; color: #065f46; font-size: 28px; font-weight: bold;">
            {fmt_money(invoice.get('paid_amount', invoice.get('total_amount', 0)))}
        </p></td></tr></table>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #f8fafc; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_inv}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('invoice_number', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_veh}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('vehicle_title', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>{lbl_date}</strong></td>
                <td style="padding: 8px 0; text-align: right;">{_format_date(invoice.get('paid_at', datetime.now(timezone.utc)))}</td>
            </tr>
        </table>
    </td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        {seller_note}
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #f1f5f9; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/invoices/{invoice.get('id')}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">{cta}</a>
            </td>
        </tr>
    </table>
    """
    subject = (
        f"Paiement confirmé — Facture nº{invoice.get('invoice_number')}"
        if is_fr else
        f"Payment Confirmed - Invoice #{invoice.get('invoice_number')}"
    )
    return await _send_via_unified(
        to_email=invoice.get('buyer_email'),
        subject=subject,
        html_content=_base_template(content, title)
    )


async def send_invoice_overdue_email(invoice: Dict[str, Any], days_overdue: int) -> Dict[str, Any]:
    """Send reminder for overdue invoice"""
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #dc2626;">⚠️ Payment Overdue</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Your invoice payment is now <strong>{days_overdue} days overdue</strong>. 
        Please make payment immediately to avoid additional penalties.
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #fef2f2; border: 1px solid #fecaca; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>Invoice #:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{invoice.get('invoice_number', 'N/A')}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Original Amount:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{_format_currency(invoice.get('total_amount', 0))}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Late Penalty:</strong></td>
                <td style="padding: 8px 0; text-align: right; color: #dc2626;">
                    +{_format_currency(invoice.get('penalty_amount', 0))}
                </td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Total Due Now:</strong></td>
                <td style="padding: 8px 0; text-align: right; font-size: 18px; color: #dc2626; font-weight: bold;">
                    {_format_currency(invoice.get('total_amount', 0) + invoice.get('penalty_amount', 0))}
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <p style="color: #991b1b; font-size: 13px; line-height: 1.6; background-color: #fef2f2; padding: 15px; border-radius: 8px;">
        <strong>Warning:</strong> Continued non-payment may result in account suspension and 
        additional collection actions.
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #dc2626; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/invoices/{invoice.get('id')}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Pay Now</a>
            </td>
        </tr>
    </table>
    """
    
    return await _send_via_unified(
        to_email=invoice.get('buyer_email'),
        subject=f"⚠️ OVERDUE: Invoice #{invoice.get('invoice_number')} - Action Required",
        html_content=_base_template(content, "Payment Overdue")
    )


# ===== DOCUMENT EMAILS =====

async def send_document_approved_email(
    user_email: str,
    user_name: str,
    document_type: str
) -> Dict[str, Any]:
    """Send email when a document is approved"""
    doc_name = document_type.replace('_', ' ').title()
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">✓ Document Approved</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {user_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Great news! Your <strong>{doc_name}</strong> document has been reviewed and approved.
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #d1fae5; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #065f46; font-size: 18px; font-weight: bold;">
            ✓ {doc_name} Verified
        </p></td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        You can now continue with your seller verification process. Once all required documents 
        are approved, you'll be able to list vehicles for auction.
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/seller/register" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">View Verification Status</a>
            </td>
        </tr>
    </table>
    """
    
    return await _send_via_unified(
        to_email=user_email,
        subject=f"✓ Document Approved: {doc_name}",
        html_content=_base_template(content, "Document Approved")
    )


async def send_document_rejected_email(
    user_email: str,
    user_name: str,
    document_type: str,
    rejection_reason: str
) -> Dict[str, Any]:
    """Send email when a document is rejected"""
    doc_name = document_type.replace('_', ' ').title()
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #f59e0b;">Document Needs Attention</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {user_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Unfortunately, your <strong>{doc_name}</strong> document could not be approved.
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 20px; margin: 20px 0;">        <p style="margin: 0 0 10px 0; color: #92400e; font-weight: bold;">Reason:</p>
        <p style="margin: 0; color: #92400e;">{rejection_reason}</p></td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        Please upload a new document that addresses the issue above. Make sure your document:
    </p>
    
    <ul style="color: #475569; line-height: 1.8;">
        <li>Is clearly legible and not blurry</li>
        <li>Shows all required information</li>
        <li>Is current and not expired</li>
        <li>Is in PDF, JPG, or PNG format</li>
    </ul>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #f59e0b; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/seller/register" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Re-upload Document</a>
            </td>
        </tr>
    </table>
    """
    
    return await _send_via_unified(
        to_email=user_email,
        subject=f"Action Required: {doc_name} - Re-upload Needed",
        html_content=_base_template(content, "Document Needs Attention")
    )


async def send_seller_approved_email(
    user_email: str,
    user_name: str,
    seller_type: str
) -> Dict[str, Any]:
    """Send email when seller account is fully approved"""
    seller_type_name = seller_type.replace('_', ' ').title()
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">🎉 Congratulations!</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {user_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Your <strong>{seller_type_name}</strong> seller account has been fully verified and approved!
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #d1fae5; border-radius: 8px; padding: 30px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #065f46; font-size: 14px;">Account Status</p>
        <p style="margin: 10px 0 0 0; color: #065f46; font-size: 24px; font-weight: bold;">
            ✓ APPROVED
        </p></td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        You can now:
    </p>
    
    <ul style="color: #475569; line-height: 1.8;">
        <li>List vehicles for auction</li>
        <li>Set your own starting prices and reserves</li>
        <li>Track bids in real-time</li>
        <li>Receive payments directly to your account</li>
    </ul>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/create" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">List Your First Vehicle</a>
            </td>
        </tr>
    </table>
    """
    
    return await _send_via_unified(
        to_email=user_email,
        subject="🎉 Your Seller Account is Approved!",
        html_content=_base_template(content, "Seller Account Approved")
    )


# ===== AUCTION EMAILS =====
# Note: send_auction_won_email is defined further below (unified signature
# supporting both vehicle and non-vehicle auctions with EN/FR legal text).


async def send_auction_sold_email(
    seller_email: str,
    seller_name: str,
    vehicle_title: str,
    final_price: float,
    commission: float,
    net_payout: float
) -> Dict[str, Any]:
    """Send email to seller when vehicle is sold"""
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">🎉 Your Vehicle Sold!</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Congratulations {seller_name}!
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Your vehicle has been successfully sold at auction:
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #d1fae5; border-radius: 8px; padding: 25px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #065f46; font-size: 18px; font-weight: bold;">
            {vehicle_title}
        </p></td></tr></table>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #f8fafc; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>Sale Price:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{_format_currency(final_price)}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>BidVex Commission:</strong></td>
                <td style="padding: 8px 0; text-align: right; color: #dc2626;">-{_format_currency(commission)}</td>
            </tr>
            <tr style="border-top: 2px solid #2563eb;">
                <td style="padding: 12px 0;"><strong>Your Payout:</strong></td>
                <td style="padding: 12px 0; text-align: right; font-size: 20px; color: #10b981; font-weight: bold;">
                    {_format_currency(net_payout)}
                </td>
            </tr>
        </table>
    </td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        Your payout will be processed once the buyer completes payment (typically within 14 days).
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/vehicle-auctions/seller/financials" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">View Financials</a>
            </td>
        </tr>
    </table>
    """
    
    return await _send_via_unified(
        to_email=seller_email,
        subject=f"🎉 Sold! {vehicle_title} - {_format_currency(final_price)}",
        html_content=_base_template(content, "Vehicle Sold")
    )


# ===== BID NOTIFICATION EMAILS =====

async def send_bid_placed_email(
    bidder_email: str,
    bidder_name: str,
    listing_title: str,
    bid_amount: float,
    listing_id: str,
    auction_end_date: str,
    is_leading: bool = True,
    auction_type: Optional[str] = None,
) -> Dict[str, Any]:
    """iter239 Mission 6 — Refactored to route through `send_unified_email`.

    Original signature preserved for backward-compat. `auction_type` is still
    accepted but the unified BidVex template uses a single master layout.
    The bidding context (lead/outbid messaging) is surfaced via
    `secondary_info` rather than per-section custom HTML.
    """
    _ = auction_type  # legacy arg, retained for callers
    secondary = (
        "✓ You are currently the highest bidder. We'll notify you if someone outbids you."
        if is_leading else
        "Your bid has been recorded, but you're not currently leading the auction."
    )
    deadline_str = _format_date(auction_end_date) if auction_end_date else ""
    return await send_unified_email(
        "bid_placed",
        user={"email": bidder_email, "first_name": bidder_name},
        data={
            "bid_amount": f"{float(bid_amount):,.2f}",
            "listing_title": listing_title,
            "listing_id": listing_id,
            "secondary_info": f"{secondary}<br><strong>Auction ends:</strong> {deadline_str}" if deadline_str else secondary,
        },
    )


# ===== SELLER: NEW BID ON YOUR LISTING =====

async def send_seller_bid_received_email(
    seller_email: str,
    seller_name: str,
    listing_title: str,
    listing_id: str,
    bid_amount: float,
    bidder_alias: str,
    auction_end_date: str,
    auction_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Notify the seller that a new bid was placed on their listing.

    Uses a privacy-preserving alias for the bidder (not full name/email).
    """
    label = _section_label(auction_type)
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #0ea5e9;">🔔 New Bid on Your Listing / Nouvelle enchère sur votre annonce</h2>

    <p style="color: #475569; line-height: 1.6;">Hi {seller_name},</p>

    <p style="color: #475569; line-height: 1.6;">
        A new bid has just been placed on your {label['name_en']} listing.
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      <tr><td style="background-color: #f0f9ff; border: 2px solid #0ea5e9; border-radius: 8px; padding: 25px;">
        <p style="margin: 0 0 12px 0; color: #0c4a6e; font-size: 18px; font-weight: bold;">{listing_title}</p>
        <table width="100%" style="font-size: 14px; color: #1e293b;">
          <tr><td style="padding: 6px 0;"><strong>New Bid:</strong></td>
              <td style="padding: 6px 0; text-align: right; font-size: 20px; color: #0ea5e9; font-weight: bold;">{_format_currency(bid_amount)}</td></tr>
          <tr><td style="padding: 6px 0;"><strong>Bidder:</strong></td>
              <td style="padding: 6px 0; text-align: right; color: #475569;">{bidder_alias}</td></tr>
          <tr><td style="padding: 6px 0;"><strong>Auction Ends:</strong></td>
              <td style="padding: 6px 0; text-align: right; color: #dc2626;">{_format_date(auction_end_date)}</td></tr>
        </table>
      </td></tr>
    </table>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
      <tr><td align="center" style="background-color: #0ea5e9; padding: 14px 30px; border-radius: 8px;">
        <a href="{FRONTEND_URL}/listing/{listing_id}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px;">View Your Listing</a>
      </td></tr>
    </table>

    <hr style="border:0; border-top:1px solid #e2e8f0; margin: 24px 0;" />

    <p style="color: #475569; line-height: 1.6;">Bonjour {seller_name},</p>
    <p style="color: #475569; line-height: 1.6;">
        Une nouvelle enchère vient d'être placée sur votre annonce {label['name_fr']}.
        L'identifiant de l'enchérisseur est affiché sous forme d'alias pour protéger sa vie privée.
    </p>

    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        <strong>Tip:</strong> Log in to your seller dashboard to follow live bid activity.
    </p>
    """
    return await _send_via_unified(
        to_email=seller_email,
        subject=f"🔔 New bid on your listing — {listing_title} | {label['name_en']}",
        html_content=_base_template(content, "New Bid Received", auction_type=auction_type),
    )


async def send_outbid_email(
    user_email: str,
    user_name: str,
    listing_title: str,
    their_bid: float,
    new_high_bid: float,
    listing_id: str,
    auction_end_date: str,
    auction_type: Optional[str] = None,
) -> Dict[str, Any]:
    """iter239 Mission 6 — Refactored to route through `send_unified_email`.

    Signature preserved for backward compatibility. `auction_type` retained
    but the unified template uses a single master layout.
    """
    _ = auction_type  # legacy arg, retained
    suggested = new_high_bid + 1
    deadline_str = _format_date(auction_end_date) if auction_end_date else ""
    secondary = (
        f"Your bid: <strike>{_format_currency(their_bid)}</strike>"
        f"<br>Suggested next bid: <strong>{_format_currency(suggested)}</strong> or higher."
    )
    if deadline_str:
        secondary += f"<br><strong>Auction ends:</strong> {deadline_str}"
    return await send_unified_email(
        "outbid",
        user={"email": user_email, "first_name": user_name},
        data={
            "current_bid": f"{float(new_high_bid):,.2f}",
            "listing_title": listing_title,
            "listing_id": listing_id,
            "secondary_info": secondary,
        },
    )


# ===== SUBSCRIPTION EMAILS =====

async def send_subscription_reminder_email(
    user_email: str,
    user_name: str,
    plan: str,
    days_remaining: int,
    end_date: str
) -> Dict[str, Any]:
    """Send reminder email 3 days before subscription expires"""
    plan_name = plan.title()
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #f59e0b;">⏰ Subscription Expiring Soon</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {user_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Your <strong>{plan_name}</strong> subscription will expire in <strong>{days_remaining} days</strong>.
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;"><tr><td style="background-color: #fef3c7; border: 1px solid #fcd34d; border-radius: 8px; padding: 20px;">
        <table width="100%" style="font-size: 14px; color: #1e293b;">
            <tr>
                <td style="padding: 8px 0;"><strong>Current Plan:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{plan_name}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Expires On:</strong></td>
                <td style="padding: 8px 0; text-align: right;">{end_date}</td>
            </tr>
            <tr>
                <td style="padding: 8px 0;"><strong>Days Remaining:</strong></td>
                <td style="padding: 8px 0; text-align: right; color: #d97706; font-weight: bold;">{days_remaining}</td>
            </tr>
        </table>
    </td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        To continue enjoying {plan_name} benefits (reduced fees, priority support, and more), 
        please contact support to renew your subscription.
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #f59e0b; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/settings/subscription" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">View Subscription</a>
            </td>
        </tr>
    </table>
    
    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        If your subscription expires, your account will be downgraded to the Free plan automatically.
    </p>
    """
    
    return await _send_via_unified(
        to_email=user_email,
        subject=f"⏰ Your {plan_name} Subscription Expires in {days_remaining} Days",
        html_content=_base_template(content, "Subscription Reminder")
    )


async def send_subscription_expired_email(
    user_email: str,
    user_name: str,
    previous_plan: str
) -> Dict[str, Any]:
    """Send confirmation email when subscription expires"""
    plan_name = previous_plan.title()
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #64748b;">Subscription Expired</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {user_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Your <strong>{plan_name}</strong> subscription has expired. Your account has been 
        downgraded to the <strong>Free</strong> plan.
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #f1f5f9; border-radius: 8px; padding: 20px; margin: 20px 0;">        <h4 style="margin: 0 0 15px 0; color: #334155;">What's Changed:</h4>
        <ul style="margin: 0; padding: 0 0 0 20px; color: #475569; line-height: 1.8;">
            <li>Monthly listing limit reduced</li>
            <li>Buyer premium discounts removed</li>
            <li>Seller commission discounts removed</li>
            <li>Priority support no longer available</li>
        </ul></td></tr></table>
    
    <p style="color: #475569; line-height: 1.6;">
        Don't worry! Your existing listings will remain active. To regain your {plan_name} benefits, 
        please contact support to renew your subscription.
    </p>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #1e3a5f; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/settings/subscription" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Renew Subscription</a>
            </td>
        </tr>
    </table>
    
    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        Thank you for being a {plan_name} member. We hope to see you back soon!
    </p>
    """
    
    return await _send_via_unified(
        to_email=user_email,
        subject=f"Your {plan_name} Subscription Has Expired",
        html_content=_base_template(content, "Subscription Expired")
    )


async def send_subscription_upgraded_email(
    user_email: str,
    user_name: str,
    new_plan: str,
    end_date: str
) -> Dict[str, Any]:
    """Send confirmation when subscription is upgraded/changed by admin"""
    plan_name = new_plan.title()
    
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">🎉 Subscription Updated</h2>
    
    <p style="color: #475569; line-height: 1.6;">
        Hi {user_name},
    </p>
    
    <p style="color: #475569; line-height: 1.6;">
        Great news! Your subscription has been updated to <strong>{plan_name}</strong>.
    </p>
    
    <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td style="background-color: #d1fae5; border-radius: 8px; padding: 20px; margin: 20px 0; text-align: center;">        <p style="margin: 0; color: #065f46; font-size: 24px; font-weight: bold;">
            {plan_name}
        </p>
        <p style="margin: 10px 0 0 0; color: #10b981; font-size: 14px;">
            Active until {end_date}
        </p></td></tr></table>
    
    <h4 style="margin: 25px 0 15px 0; color: #334155;">Your {plan_name} Benefits:</h4>
    <ul style="margin: 0; padding: 0 0 0 20px; color: #475569; line-height: 1.8;">
        {"<li>Reduced buyer premium fees</li>" if new_plan in ['premium', 'vip'] else ""}
        {"<li>Lower seller commission rates</li>" if new_plan in ['premium', 'vip'] else ""}
        {"<li>Priority customer support</li>" if new_plan in ['premium', 'vip'] else ""}
        {"<li>Advanced analytics dashboard</li>" if new_plan == 'vip' else ""}
        {"<li>Dedicated account manager</li>" if new_plan == 'vip' else ""}
    </ul>
    
    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
                <a href="{FRONTEND_URL}/marketplace" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Start Exploring</a>
            </td>
        </tr>
    </table>
    """
    
    return await _send_via_unified(
        to_email=user_email,
        subject=f"🎉 Welcome to {plan_name}!",
        html_content=_base_template(content, "Subscription Updated")
    )



# ========== AUCTION WINNER EMAILS ==========

async def send_auction_won_email(
    to_email: str = "",
    to_name: str = "",
    auction_id: str = "",
    item_name: str = "",
    hammer_price: float = 0.0,
    platform_fee: float = 0.0,
    seller_name: str = "",
    seller_contact: str = "",
    is_vehicle: bool = False,
    is_cross_border: bool = False,
    buyer_province: str = "QC",
    payment_deadline: Optional[str] = None,
    # --- Back-compat aliases (older callers) ---
    winner_email: Optional[str] = None,
    winner_name: Optional[str] = None,
    item_title: Optional[str] = None,
    final_price: Optional[float] = None,
    listing_id: Optional[str] = None,
    buyer_email: Optional[str] = None,
    buyer_name: Optional[str] = None,
    vehicle_title: Optional[str] = None,
    invoice_id: Optional[str] = None,
    buyers_premium_rate: Optional[float] = None,  # noqa: ARG001 — legacy, ignored
) -> Dict[str, Any]:
    """
    Send 'You Won!' email to auction winner.

    Legal-compliant behavior:
      - For vehicles (is_vehicle=True), injects a bilingual EN/FR notice that
        the hammer price is settled DIRECTLY between buyer and seller and that
        BidVex only charges the 2.5% platform fee + taxes.
      - For non-vehicles, shows the standard checkout CTA (BidVex collects full
        hammer via Stripe Connect).
      - For cross-border (is_cross_border=True), appends the cross-border
        compliance notice in both languages.
    """
    # Back-compat normalization
    to_email = to_email or winner_email or buyer_email or ""
    to_name = to_name or winner_name or buyer_name or ""
    item_name = item_name or item_title or vehicle_title or "Item"
    auction_id = auction_id or listing_id or invoice_id or ""
    if hammer_price in (None, 0.0) and final_price is not None:
        hammer_price = final_price

    checkout_url = f"{FRONTEND_URL}/checkout/{auction_id}"
    invoice_url = f"{FRONTEND_URL}/vehicle-auctions/invoices/{auction_id}"
    hammer_display = _format_currency(hammer_price)
    fee_display = _format_currency(platform_fee)
    # French Canadian currency: "10 000,00 $" — suffix style
    def _fr_currency(amount):
        s = f"{float(amount):,.2f}"  # 10,000.00
        return s.replace(",", " ").replace(".", ",") + " $"
    hammer_display_fr = _fr_currency(hammer_price)
    fee_display_fr = _fr_currency(platform_fee)
    deadline_display = _format_date(payment_deadline) if payment_deadline else "14 days"

    # ── Vehicle-specific payment notice (EN + FR) ──
    vehicle_notice = ""
    if is_vehicle:
        seller_contact_line = seller_contact or "Available in your BidVex dashboard"
        seller_display = seller_name or "Seller"
        vehicle_notice = f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      <tr><td style="background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 8px; padding: 20px;">
        <p style="margin: 0 0 10px 0; color: #92400e; font-weight: bold; font-size: 15px;">
          ⚠️ VEHICLE PAYMENT NOTICE
        </p>
        <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          Payment for the vehicle (<strong>{hammer_display}</strong>) is arranged directly
          between you and the seller. BidVex does not process or hold vehicle purchase funds.
        </p>
        <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          <strong>Seller Contact:</strong> {seller_display} | {seller_contact_line}
        </p>
        <p style="margin: 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          BidVex Platform Fee of 2.5% (<strong>{fee_display}</strong>) has been charged
          separately to your card on file. This is the only amount BidVex collects.
        </p>
      </td></tr>
    </table>

    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      <tr><td style="background-color: #fef3c7; border-left: 4px solid #f59e0b; border-radius: 8px; padding: 20px;">
        <p style="margin: 0 0 10px 0; color: #92400e; font-weight: bold; font-size: 15px;">
          ⚠️ AVIS DE PAIEMENT DU VÉHICULE
        </p>
        <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          Le paiement du véhicule (<strong>{hammer_display_fr}</strong>) est organisé
          directement entre vous et le vendeur. BidVex ne traite pas et ne détient pas
          les fonds d'achat de véhicules.
        </p>
        <p style="margin: 0 0 10px 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          <strong>Contact du vendeur :</strong> {seller_display} | {seller_contact_line}
        </p>
        <p style="margin: 0; color: #78350f; font-size: 14px; line-height: 1.6;">
          Les frais de plateforme BidVex de 2,5 % (<strong>{fee_display_fr}</strong>) ont été
          débités séparément de votre carte enregistrée. C'est le seul montant que BidVex perçoit.
        </p>
      </td></tr>
    </table>
    """

    # ── Cross-border compliance notice (EN + FR) ──
    cross_border_notice = ""
    if is_cross_border:
        cross_border_notice = f"""
    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      <tr><td style="background-color: #eff6ff; border-left: 4px solid #2563eb; border-radius: 8px; padding: 20px;">
        <p style="margin: 0 0 8px 0; color: #1e40af; font-weight: bold; font-size: 14px;">
          🌐 Cross-Border Purchase Notice
        </p>
        <p style="margin: 0 0 8px 0; color: #1e293b; font-size: 13px; line-height: 1.6;">
          This purchase crosses provincial or international borders. You may be responsible
          for additional import duties, brokerage, GST/HST/QST on import, and compliance
          with your province's ({buyer_province}) vehicle registration rules.
        </p>
        <p style="margin: 0; color: #1e293b; font-size: 13px; line-height: 1.6;">
          Cet achat franchit des frontières provinciales ou internationales. Vous pourriez
          être responsable des droits d'importation, du courtage, de la TPS/TVH/TVQ à
          l'importation, et de la conformité aux règles d'immatriculation de votre
          province ({buyer_province}).
        </p>
      </td></tr>
    </table>
    """

    # ── CTA button ──
    cta_url = invoice_url if is_vehicle else checkout_url
    cta_label = "View Fee Invoice" if is_vehicle else "Complete Payment"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">Congratulations! You Won!</h2>

    <p style="color: #475569; line-height: 1.6;">
        Hi {to_name},
    </p>

    <p style="color: #475569; line-height: 1.6;">
        You've won the auction for <strong>{item_name}</strong>!
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <td style="background-color: #ecfdf5; border-radius: 8px; padding: 20px; margin: 20px 0;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td style="color: #065f46; font-size: 14px; padding: 4px 0;">Item:</td>
                        <td style="color: #065f46; font-size: 14px; font-weight: bold; text-align: right;">{item_name}</td>
                    </tr>
                    <tr>
                        <td style="color: #065f46; font-size: 14px; padding: 4px 0;">Winning Bid:</td>
                        <td style="color: #065f46; font-size: 24px; font-weight: bold; text-align: right;">{hammer_display}</td>
                    </tr>
                    <tr>
                        <td style="color: #065f46; font-size: 14px; padding: 4px 0;">Payment Due By:</td>
                        <td style="color: #dc2626; font-size: 14px; font-weight: bold; text-align: right;">{deadline_display}</td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
    {vehicle_notice}
    {cross_border_notice}

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
                <a href="{cta_url}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;" data-testid="auction-won-cta">{cta_label}</a>
            </td>
        </tr>
    </table>

    <p style="color: #94a3b8; font-size: 12px; text-align: center;">
        If the button doesn't work, copy this link: {cta_url}
    </p>
    """

    # iter249 Mission 3 — Language-aware subject (auction_won already
    # renders bilingual EN+FR bodies for vehicles; the subject now
    # follows the recipient's language preference too).
    _aw_lang = _detect_language(buyer_province)
    if _aw_lang == "fr":
        subject = (
            f"Vous avez gagné ! Véhicule {item_name} — Facture des frais prête"
            if is_vehicle
            else f"Vous avez gagné ! Effectuez le paiement pour {item_name}"
        )
    else:
        subject = (
            f"You Won! Vehicle {item_name} — Fee Invoice Ready"
            if is_vehicle
            else f"You Won! Complete Payment for {item_name}"
        )

    return await _send_via_unified(
        to_email=to_email,
        subject=subject,
        html_content=_base_template(content, "Auction Won")
    )


async def send_payment_reminder_email(
    winner_email: str,
    winner_name: str,
    item_title: str,
    final_price: float,
    listing_id: str,
    days_remaining: int,
    payment_deadline: str,
) -> Dict[str, Any]:
    """Send payment reminder email (day 10)"""
    checkout_url = f"{FRONTEND_URL}/checkout/{listing_id}"
    price_display = _format_currency(final_price)
    deadline_display = _format_date(payment_deadline) if payment_deadline else "soon"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #f59e0b;">Payment Reminder</h2>

    <p style="color: #475569; line-height: 1.6;">
        Hi {winner_name},
    </p>

    <p style="color: #475569; line-height: 1.6;">
        This is a reminder that your payment for <strong>{item_title}</strong> is due in <strong>{days_remaining} days</strong>.
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <td style="background-color: #fffbeb; border: 1px solid #fbbf24; border-radius: 8px; padding: 20px;">
                <p style="margin: 0 0 8px 0; color: #92400e; font-weight: bold;">Payment Details</p>
                <p style="margin: 0; color: #92400e;">Amount: <strong>{price_display}</strong> (+ applicable fees &amp; taxes)</p>
                <p style="margin: 8px 0 0 0; color: #dc2626; font-weight: bold;">Deadline: {deadline_display}</p>
            </td>
        </tr>
    </table>

    <p style="color: #475569; line-height: 1.6; margin-top: 20px;">
        After the deadline, a <strong>2% monthly late penalty</strong> will be applied to your balance.
    </p>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #f59e0b; padding: 14px 30px; border-radius: 8px;">
                <a href="{checkout_url}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Pay Now</a>
            </td>
        </tr>
    </table>
    """

    return await _send_via_unified(
        to_email=winner_email,
        subject=f"Payment Reminder: {item_title} - {days_remaining} Days Left",
        html_content=_base_template(content, "Payment Reminder")
    )


async def send_payment_overdue_email(
    winner_email: str,
    winner_name: str,
    item_title: str,
    final_price: float,
    listing_id: str,
    penalty_amount: float,
    total_with_penalty: float,
) -> Dict[str, Any]:
    """Send payment overdue notice with penalty (day 14+)"""
    checkout_url = f"{FRONTEND_URL}/checkout/{listing_id}"
    price_display = _format_currency(final_price)
    penalty_display = _format_currency(penalty_amount)
    total_display = _format_currency(total_with_penalty)

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #dc2626;">Payment Overdue</h2>

    <p style="color: #475569; line-height: 1.6;">
        Hi {winner_name},
    </p>

    <p style="color: #475569; line-height: 1.6;">
        Your payment for <strong>{item_title}</strong> is now <strong>overdue</strong>. A late penalty has been applied.
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0">
        <tr>
            <td style="background-color: #fef2f2; border: 1px solid #fca5a5; border-radius: 8px; padding: 20px;">
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td style="color: #991b1b; font-size: 14px; padding: 4px 0;">Original Amount:</td>
                        <td style="color: #991b1b; font-size: 14px; text-align: right;">{price_display}</td>
                    </tr>
                    <tr>
                        <td style="color: #dc2626; font-size: 14px; padding: 4px 0;">Late Penalty (2%/month):</td>
                        <td style="color: #dc2626; font-size: 14px; font-weight: bold; text-align: right;">+{penalty_display}</td>
                    </tr>
                    <tr>
                        <td colspan="2" style="border-top: 1px solid #fca5a5; padding-top: 8px; margin-top: 8px;"></td>
                    </tr>
                    <tr>
                        <td style="color: #991b1b; font-size: 16px; font-weight: bold; padding: 4px 0;">New Total Due:</td>
                        <td style="color: #dc2626; font-size: 20px; font-weight: bold; text-align: right;">{total_display}</td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>

    <p style="color: #475569; line-height: 1.6; margin-top: 20px;">
        Please complete your payment immediately to avoid further penalties. The late penalty increases by 2% for each additional month.
    </p>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td align="center" style="background-color: #dc2626; padding: 14px 30px; border-radius: 8px;">
                <a href="{checkout_url}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Pay Now</a>
            </td>
        </tr>
    </table>
    """

    return await _send_via_unified(
        to_email=winner_email,
        subject=f"OVERDUE: Payment Required for {item_title}",
        html_content=_base_template(content, "Payment Overdue")
    )


# ========== REVIEW REQUEST EMAIL ==========

async def send_review_request_email(
    buyer_email: str,
    buyer_name: str,
    item_title: str,
    transaction_id: str,
    seller_name: str,
) -> Dict[str, Any]:
    """Send 'How was your purchase?' email 24h after payment confirmation."""
    review_url = f"{FRONTEND_URL}/review/{transaction_id}"

    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #1e3a8a;">How was your purchase?</h2>

    <p style="color: #475569; line-height: 1.6;">
        Hi {buyer_name},
    </p>

    <p style="color: #475569; line-height: 1.6;">
        You recently purchased <strong>{item_title}</strong> from <strong>{seller_name}</strong>.
        We'd love to hear about your experience!
    </p>

    <p style="color: #475569; line-height: 1.6;">
        Your review helps other buyers make informed decisions and helps sellers improve.
    </p>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
        <tr>
            <td style="padding: 4px;">
                <span style="font-size: 36px; color: #f59e0b;">&#9733;&#9733;&#9733;&#9733;&#9733;</span>
            </td>
        </tr>
    </table>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 20px auto;">
        <tr>
            <td align="center" style="background-color: #1e3a8a; padding: 14px 30px; border-radius: 8px;">
                <a href="{review_url}" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px; display: inline-block;">Leave a Review</a>
            </td>
        </tr>
    </table>

    <p style="color: #94a3b8; font-size: 12px; text-align: center;">
        If the button doesn't work, copy this link: {review_url}
    </p>
    """

    return await _send_via_unified(
        to_email=buyer_email,
        subject=f"How was your purchase of {item_title}?",
        html_content=_base_template(content, "Leave a Review")
    )


# ============================================================================
# STORAGE UNIT AUCTIONS — bilingual EN+FR (iteration 169)
# ============================================================================
import os as _os
from datetime import datetime as _dt


def _storage_panel(title_en: str, title_fr: str, body_en: str, body_fr: str, cta_url: str = "", cta_en: str = "", cta_fr: str = "") -> str:
    cta_block = ""
    if cta_url and cta_en:
        cta_block = f"""
        <div style="text-align:center;margin:20px 0;">
          <a href="{cta_url}" style="background:#0F3060;color:#fff;text-decoration:none;font-weight:700;padding:12px 26px;border-radius:24px;display:inline-block;">
            {cta_en} / {cta_fr}
          </a>
        </div>
        """
    return f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:24px;background:#fff;">
      <div style="background:linear-gradient(135deg,#0B2545,#0F3060);color:#fff;padding:24px;border-radius:12px;margin-bottom:16px;">
        <p style="margin:0;font-size:11px;letter-spacing:2px;opacity:0.7;">🔒 BIDVEX STORAGE AUCTIONS</p>
        <h2 style="margin:6px 0 0 0;font-size:22px;">{title_en}</h2>
        <p style="margin:4px 0 0 0;font-size:14px;color:#3FB4CB;">{title_fr}</p>
      </div>
      <div style="color:#1e293b;font-size:14px;line-height:1.55;">
        <p><strong>EN:</strong> {body_en}</p>
        <hr style="border:none;border-top:1px solid #e5e7eb;margin:12px 0;"/>
        <p><strong>FR:</strong> {body_fr}</p>
      </div>
      {cta_block}
      <p style="font-size:11px;color:#94a3b8;text-align:center;margin-top:24px;">BidVex Canada — bilingual auction marketplace</p>
    </div>
    """


async def send_storage_bid_placed_email(buyer: dict, auction: dict, bid_state: dict) -> bool:
    """iter239 Mission 6 — Routes through `send_unified_email("bid_placed")`."""
    if not buyer or not buyer.get("email"):
        return False
    a_id = (auction or {}).get("id", "")
    cur = bid_state.get("current_bid", 0)
    winning = bid_state.get("you_are_winning")
    secondary = (
        "You are currently winning the auction."
        if winning else
        "You are NOT currently winning — your maximum was outbid."
    )
    result = await send_unified_email(
        "bid_placed",
        user={"email": buyer["email"], "first_name": buyer.get("name") or buyer.get("full_name") or ""},
        data={
            "bid_amount": f"{float(cur):,.2f}",
            "listing_title": f"Storage Unit Auction #{a_id[:8]}",
            "listing_id": a_id,
            "secondary_info": secondary,
        },
    )
    return result.get("status") in ("sent", "logged")


async def send_storage_outbid_email(buyer: dict, auction: dict, new_current: float) -> bool:
    """iter239 Mission 6 — Routes through `send_unified_email("outbid")`."""
    if not buyer or not buyer.get("email"):
        return False
    a_id = (auction or {}).get("id", "")
    result = await send_unified_email(
        "outbid",
        user={"email": buyer["email"], "first_name": buyer.get("name") or buyer.get("full_name") or ""},
        data={
            "current_bid": f"{float(new_current):,.2f}",
            "listing_title": f"Storage Unit Auction #{a_id[:8]}",
            "listing_id": a_id,
            "secondary_info": "Place a higher max bid to retake the lead.",
        },
    )
    return result.get("status") in ("sent", "logged")


async def send_storage_auction_won_email(buyer: dict, auction: dict, facility: dict, pricing: dict = None) -> bool:
    """
    Bilingual winner email. Branches on auction.payment_method:
      • stripe   → BidVex charged buyer card (5% + stripe + tax); buyer pays hammer via Stripe to facility
      • cash     → buyer pays hammer CASH directly to facility
      • etransfer→ buyer sends Interac e-Transfer to facility's registered email

    Always includes a cleanup-deadline warning with forfeit clause.
    """
    if not buyer or not buyer.get("email"):
        return False

    unit = auction.get("unit_number", "—")
    bid = float(auction.get("winning_bid") or auction.get("current_bid") or 0)
    pm = (auction.get("payment_method") or "stripe").lower()
    fac_name = facility.get("company_name", "—")
    fac_contact = facility.get("contact_name", "—")
    fac_phone = facility.get("phone", "—")
    fac_email = facility.get("email", "—")
    pay_deadline = auction.get("payment_deadline") or auction.get("cleanup_deadline", "—")
    cleanup_deadline = auction.get("cleanup_deadline", "—")
    cleanup_deposit = float(auction.get("cleanup_deposit", 0) or 0)
    buyer_name = buyer.get("name") or buyer.get("full_name") or "—"

    # Optional BidVex charge (for Stripe path only)
    buyer_stripe_charge = 0.0
    if pricing and pricing.get("buyer_invoice"):
        # stripe path: platform_fee + stripe_recovery + tax (BidVex-collected portion)
        bi = pricing["buyer_invoice"]
        buyer_stripe_charge = float(bi.get("platform_fee", 0)) + float(bi.get("stripe_recovery", 0)) + float(bi.get("tax", 0))

    # ── Per-method body ──
    if pm == "stripe":
        body_en = (
            f"Congratulations! You won Unit <strong>#{unit}</strong> at <strong>{fac_name}</strong>.<br/>"
            f"Your winning bid: <strong>${bid:,.2f}</strong><br/><br/>"
            f"BidVex has charged your card <strong>${buyer_stripe_charge:,.2f}</strong> (platform fee + Stripe + taxes).<br/>"
            f"You must pay <strong>${bid:,.2f}</strong> to the facility via Stripe before <strong>{pay_deadline}</strong>.<br/><br/>"
            f"<strong>Facility contact:</strong> {fac_contact} | {fac_phone} | {fac_email}<br/>"
        )
        body_fr = (
            f"Félicitations! Vous avez remporté l'unité <strong>#{unit}</strong> à <strong>{fac_name}</strong>.<br/>"
            f"Votre offre gagnante : <strong>{bid:,.2f} $</strong><br/><br/>"
            f"BidVex a débité <strong>{buyer_stripe_charge:,.2f} $</strong> sur votre carte (frais de plateforme + Stripe + taxes).<br/>"
            f"Vous devez payer <strong>{bid:,.2f} $</strong> à la facilité via Stripe avant le <strong>{pay_deadline}</strong>.<br/><br/>"
            f"<strong>Contact facilité :</strong> {fac_contact} | {fac_phone} | {fac_email}<br/>"
        )
    elif pm == "cash":
        body_en = (
            f"Congratulations! You won Unit <strong>#{unit}</strong> at <strong>{fac_name}</strong> for "
            f"<strong>${bid:,.2f}</strong>.<br/><br/>"
            f"You must pay <strong>${bid:,.2f} CASH</strong> directly to the facility.<br/>"
            f"Contact the facility to arrange payment and pickup:<br/>"
            f"<strong>{fac_contact}</strong> | {fac_phone} | {fac_email}<br/>"
            f"<strong>Payment deadline:</strong> {pay_deadline}<br/>"
            f"<strong>Cleanup deadline:</strong> {cleanup_deadline}<br/>"
        )
        body_fr = (
            f"Félicitations! Vous avez remporté l'unité <strong>#{unit}</strong> à <strong>{fac_name}</strong> pour "
            f"<strong>{bid:,.2f} $</strong>.<br/><br/>"
            f"Vous devez payer <strong>{bid:,.2f} $ COMPTANT</strong> directement à la facilité.<br/>"
            f"Contactez la facilité pour organiser le paiement et le ramassage :<br/>"
            f"<strong>{fac_contact}</strong> | {fac_phone} | {fac_email}<br/>"
            f"<strong>Date limite de paiement :</strong> {pay_deadline}<br/>"
            f"<strong>Date limite de nettoyage :</strong> {cleanup_deadline}<br/>"
        )
    else:  # etransfer
        body_en = (
            f"Congratulations! You won Unit <strong>#{unit}</strong> at <strong>{fac_name}</strong> for "
            f"<strong>${bid:,.2f}</strong>.<br/><br/>"
            f"Send <strong>${bid:,.2f}</strong> via <strong>Interac e-Transfer</strong> to: <strong>{fac_email}</strong><br/>"
            f"<strong>Reference:</strong> BidVex Unit #{unit} — {buyer_name}<br/>"
            f"Contact the facility to confirm receipt:<br/>"
            f"<strong>{fac_contact}</strong> | {fac_phone}<br/>"
            f"<strong>Payment deadline:</strong> {pay_deadline}<br/>"
            f"<strong>Cleanup deadline:</strong> {cleanup_deadline}<br/>"
        )
        body_fr = (
            f"Félicitations! Vous avez remporté l'unité <strong>#{unit}</strong> à <strong>{fac_name}</strong> pour "
            f"<strong>{bid:,.2f} $</strong>.<br/><br/>"
            f"Envoyez <strong>{bid:,.2f} $</strong> par <strong>virement Interac</strong> à : <strong>{fac_email}</strong><br/>"
            f"<strong>Référence :</strong> BidVex Unité #{unit} — {buyer_name}<br/>"
            f"Contactez la facilité pour confirmer la réception :<br/>"
            f"<strong>{fac_contact}</strong> | {fac_phone}<br/>"
            f"<strong>Date limite de paiement :</strong> {pay_deadline}<br/>"
            f"<strong>Date limite de nettoyage :</strong> {cleanup_deadline}<br/>"
        )

    # ── Cleanup / forfeit notice (always appended, bilingual) ──
    pickup_code = auction.get("pickup_code")
    pickup_en = ""
    pickup_fr = ""
    if pickup_code:
        # Generate inline base64 QR image so it renders in every email client
        qr_img_tag = ""
        try:
            import base64 as _b64
            from routes.storage_auctions import _generate_pickup_qr_png_bytes
            qr_bytes = _generate_pickup_qr_png_bytes(pickup_code)
            qr_b64 = _b64.b64encode(qr_bytes).decode("ascii")
            qr_img_tag = (
                f"<div style='margin:12px auto;display:inline-block;background:#FFFFFF;"
                f"padding:12px;border-radius:8px;border:2px solid #fde68a'>"
                f"<img src='data:image/png;base64,{qr_b64}' alt='Scan for pickup verification / Scanner pour vérification de ramassage' "
                f"width='180' height='180' "
                f"style='display:block;width:180px;height:180px;image-rendering:pixelated;background:#FFFFFF'/>"
                f"</div>"
            )
        except Exception as e:
            logger.error(f"[STORAGE_EMAIL] QR embed failed: {e}")

        pickup_en = (
            f"<hr style='margin:16px 0;border:none;border-top:1px solid #e2e8f0'/>"
            f"<div style='background:#fef3c7;border:2px dashed #d97706;border-radius:10px;padding:16px;text-align:center;margin:12px 0'>"
            f"<div style='font-size:11px;letter-spacing:2px;color:#92400e;font-weight:700'>YOUR PICKUP CODE</div>"
            f"<div style='font-size:28px;font-weight:900;color:#78350f;letter-spacing:3px;font-family:monospace;margin-top:6px'>{pickup_code}</div>"
            f"{qr_img_tag}"
            f"<div style='font-size:11px;color:#92400e;margin-top:4px'>Scan at pickup · Show code to staff</div>"
            f"</div>"
            f"Present this code (or the QR) to facility staff when you arrive for pickup. "
            f"The facility will mark this code as used upon verification. "
            f"<strong>Do not share this code</strong> — it authorizes access to the unit."
        )
        pickup_fr = (
            f"<hr style='margin:16px 0;border:none;border-top:1px solid #e2e8f0'/>"
            f"<div style='background:#fef3c7;border:2px dashed #d97706;border-radius:10px;padding:16px;text-align:center;margin:12px 0'>"
            f"<div style='font-size:11px;letter-spacing:2px;color:#92400e;font-weight:700'>VOTRE CODE DE RÉCUPÉRATION</div>"
            f"<div style='font-size:28px;font-weight:900;color:#78350f;letter-spacing:3px;font-family:monospace;margin-top:6px'>{pickup_code}</div>"
            f"{qr_img_tag}"
            f"<div style='font-size:11px;color:#92400e;margin-top:4px'>Scanner à la récupération · Présentez le code</div>"
            f"</div>"
            f"Présentez ce code (ou le QR) au personnel de la facilité lors de votre arrivée. "
            f"La facilité marquera ce code comme utilisé après vérification. "
            f"<strong>Ne partagez pas ce code</strong> — il autorise l'accès à l'unité."
        )

    cleanup_en = (
        f"<hr style='margin:16px 0;border:none;border-top:1px solid #e2e8f0'/>"
        f"⚠️ <strong>IMPORTANT:</strong> You must completely empty the unit by "
        f"<strong>{cleanup_deadline}</strong>. Failure to empty the unit forfeits your "
        f"cleaning deposit of <strong>${cleanup_deposit:.2f}</strong> and will result in "
        f"account suspension.<br/>"
        f"Cleaning deposit: <strong>${cleanup_deposit:.2f}</strong> (refunded after the unit is confirmed empty)."
    )
    cleanup_fr = (
        f"<hr style='margin:16px 0;border:none;border-top:1px solid #e2e8f0'/>"
        f"⚠️ <strong>IMPORTANT :</strong> Vous devez vider complètement l'unité avant "
        f"<strong>{cleanup_deadline}</strong>. Le non-respect de cette date limite entraîne la "
        f"perte de votre dépôt de nettoyage de <strong>{cleanup_deposit:.2f} $</strong> et la "
        f"suspension de votre compte.<br/>"
        f"Dépôt de nettoyage : <strong>{cleanup_deposit:.2f} $</strong> (remboursé après confirmation que l'unité est vide)."
    )

    return bool(await _send_via_unified(
        to_email=buyer["email"],
        subject=f"🎉 You won — Storage Auction Unit #{unit}",
        html_content=_storage_panel(
            "You won the auction",
            "Vous avez gagné l'enchère",
            body_en + pickup_en + cleanup_en,
            body_fr + pickup_fr + cleanup_fr,
            cta_url=f"https://www.bidvex.com/storage-auctions/{auction.get('id','')}",
            cta_en="View auction",
            cta_fr="Voir l'enchère",
        ),
    ))


async def send_storage_auction_sold_email(facility: dict, auction: dict, buyer: dict) -> bool:
    """Bilingual notification to the facility when their unit sells."""
    if not facility or not facility.get("email"):
        return False
    a_id = auction.get("id", "")[:8]
    unit = auction.get("unit_number", "—")
    bid = float(auction.get("winning_bid") or auction.get("current_bid") or 0)
    pm = (auction.get("payment_method") or "stripe").lower()
    pm_label_en = {"stripe": "Stripe (online)", "cash": "Cash", "etransfer": "Interac e-Transfer"}.get(pm, pm)
    pm_label_fr = {"stripe": "Stripe (en ligne)", "cash": "Comptant", "etransfer": "Virement Interac"}.get(pm, pm)

    buyer_name = buyer.get("name") or buyer.get("full_name") or "—"
    buyer_email = buyer.get("email", "—")
    buyer_phone = buyer.get("phone", "—")

    body_en = (
        f"Storage auction for Unit <strong>#{unit}</strong> (#{a_id}) sold for "
        f"<strong>${bid:,.2f}</strong>.<br/><br/>"
        f"<strong>Payment method:</strong> {pm_label_en}<br/>"
        f"<strong>Winning bidder:</strong> {buyer_name} &lt;{buyer_email}&gt;<br/>"
        f"<strong>Phone:</strong> {buyer_phone}<br/><br/>"
        f"Contact the winner to coordinate payment and pickup. "
        f"Your BidVex commission invoice (5% + Stripe + applicable tax) will arrive separately."
    )
    body_fr = (
        f"L'enchère pour l'unité <strong>#{unit}</strong> (#{a_id}) a été vendue pour "
        f"<strong>{bid:,.2f} $</strong>.<br/><br/>"
        f"<strong>Mode de paiement :</strong> {pm_label_fr}<br/>"
        f"<strong>Enchérisseur gagnant :</strong> {buyer_name} &lt;{buyer_email}&gt;<br/>"
        f"<strong>Téléphone :</strong> {buyer_phone}<br/><br/>"
        f"Contactez le gagnant pour organiser le paiement et le ramassage. "
        f"Votre facture de commission BidVex (5 % + Stripe + taxes applicables) suivra séparément."
    )
    return bool(await _send_via_unified(
        to_email=facility["email"],
        subject=f"✅ Sold — Storage Auction Unit #{unit}",
        html_content=_storage_panel("Auction sold", "Enchère vendue", body_en, body_fr),
    ))


async def send_storage_ending_soon_email(buyer: dict, auction: dict) -> bool:
    """iter239 Mission 6 — Routes through `send_unified_email("auction_ending_soon")`."""
    if not buyer or not buyer.get("email"):
        return False
    a_id = auction.get("id", "")
    result = await send_unified_email(
        "auction_ending_soon",
        user={"email": buyer["email"], "first_name": buyer.get("name") or buyer.get("full_name") or ""},
        data={
            "listing_title": f"Storage Unit Auction #{a_id[:8]}",
            "listing_id": a_id,
            "time_remaining": "under 1 hour",
            "current_bid": f"{float(auction.get('current_bid', 0)):,.2f}",
            "secondary_info": "Place your final max bid now to stay in the lead.",
        },
    )
    return result.get("status") in ("sent", "logged")


async def send_storage_facility_approved_email(facility: dict) -> bool:
    if not facility or not facility.get("email"):
        return False
    body_en = (
        f"Welcome to BidVex Storage Auctions, <strong>{facility.get('company_name','')}</strong>! "
        f"Your facility has been verified. You can now log in and create your first storage unit auction. "
        f"BidVex charges a flat 5% commission on each successful sale — buyers pay no platform fee."
    )
    body_fr = (
        f"Bienvenue chez BidVex Enchères d'entreposage, <strong>{facility.get('company_name','')}</strong>! "
        f"Votre facilité a été vérifiée. Vous pouvez maintenant vous connecter et créer votre première enchère. "
        f"BidVex facture une commission fixe de 5% sur chaque vente réussie — les acheteurs ne paient aucun frais de plateforme."
    )
    return await _send_via_unified(
        to_email=facility["email"],
        subject="✅ Your BidVex Storage Facility account is approved",
        html_content=_storage_panel("Facility approved", "Facilité approuvée", body_en, body_fr,
                                    cta_url="https://www.bidvex.com/storage-dashboard",
                                    cta_en="Open dashboard", cta_fr="Ouvrir le tableau de bord"),
    )


async def send_storage_seller_commission_invoice(facility: dict, auction: dict, pricing: dict) -> bool:
    if not facility or not facility.get("email"):
        return False
    s = pricing["seller_invoice"]
    a_id = auction.get("id", "")[:8]
    body_en = (
        f"BidVex commission invoice for storage auction <strong>#{a_id}</strong>:<br/>"
        f"• Commission (5%): <strong>${s['commission']:.2f}</strong><br/>"
        f"• Stripe processing: ${s['stripe_recovery']:.2f}<br/>"
        f"• Tax — {s['tax_label']}: ${s['tax']:.2f}<br/>"
        f"<strong>Total due to BidVex: ${s['total']:.2f}</strong>"
    )
    body_fr = (
        f"Facture de commission BidVex pour l'enchère <strong>#{a_id}</strong> :<br/>"
        f"• Commission (5 %) : <strong>{s['commission']:.2f} $</strong><br/>"
        f"• Frais Stripe : {s['stripe_recovery']:.2f} $<br/>"
        f"• Taxe — {s['tax_label']} : {s['tax']:.2f} $<br/>"
        f"<strong>Total dû à BidVex : {s['total']:.2f} $</strong>"
    )
    return await _send_via_unified(
        to_email=facility["email"],
        subject=f"BidVex Commission Invoice — Storage Auction #{a_id}",
        html_content=_storage_panel("Commission invoice", "Facture de commission", body_en, body_fr),
    )


# Internal admin alert helpers (not in the 7 user-facing list, but referenced by routes)

async def send_storage_facility_registration_admin_alert(facility: dict) -> bool:
    admin_email = (
        _os.environ.get("ADMIN_NOTIFICATION_EMAIL")
        or _os.environ.get("ADMIN_EMAIL")
        or "charbel911@gmail.com"
    )
    body_en = (
        f"New storage facility registration awaiting verification:<br/>"
        f"<strong>{facility.get('company_name','—')}</strong><br/>"
        f"Contact: {facility.get('contact_name','—')} &lt;{facility.get('email','—')}&gt;<br/>"
        f"Phone: {facility.get('phone','—')}<br/>"
        f"Location: {facility.get('city','—')}, {facility.get('province','')}<br/>"
        f"Units available: {facility.get('units_available',0)}"
    )
    body_fr = "Nouvelle facilité d'entreposage en attente de vérification."
    return await _send_via_unified(
        to_email=admin_email,
        subject=f"[Storage Facility] New registration — {facility.get('company_name','')}",
        html_content=_storage_panel("New facility registration", "Nouvelle facilité", body_en, body_fr,
                                    cta_url="https://www.bidvex.com/admin", cta_en="Review", cta_fr="Examiner"),
    )


async def send_storage_facility_pending_user_email(facility: dict) -> bool:
    if not facility or not facility.get("email"):
        return False
    body_en = (
        "Thanks for registering your storage facility with BidVex! Your application "
        "is under review by our team. You'll receive a confirmation email within "
        "1–2 business days once your account is verified."
    )
    body_fr = (
        "Merci d'avoir inscrit votre facilité d'entreposage chez BidVex! Votre demande "
        "est en cours d'examen par notre équipe. Vous recevrez un courriel de confirmation "
        "dans 1 à 2 jours ouvrables une fois votre compte vérifié."
    )
    return await _send_via_unified(
        to_email=facility["email"],
        subject="Application received — BidVex Storage Auctions",
        html_content=_storage_panel("Application received", "Demande reçue", body_en, body_fr),
    )


# iter214 P1 — Dedicated pickup-code email for individual-seller cash/etransfer
# transactions. Bilingual EN+FR. Contains the BVX-XXXXXXXX code in a prominent
# box plus the seller's contact info so the buyer knows where to pay.

async def send_buyer_pickup_code_email(
    *, buyer: dict, seller: dict, listing_title: str, hammer_price: float,
    pickup_code: str, payment_method: str, transaction_id: str,
) -> bool:
    if not buyer or not buyer.get("email") or not pickup_code:
        return False
    method_label_en = "Interac e-Transfer" if payment_method == "etransfer" else "Cash"
    method_label_fr = "Virement Interac" if payment_method == "etransfer" else "Comptant"
    seller_name = (seller or {}).get("name") or "the seller"
    seller_contact = (seller or {}).get("email") or (seller or {}).get("phone") or "—"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:20px;background:#f8fafc;">
      <div style="background:white;padding:24px;border-radius:12px;border:1px solid #e2e8f0;">
        <h2 style="color:#1e40af;margin:0 0 8px;">🎉 Congratulations — you won an auction!</h2>
        <p style="color:#475569;margin:0 0 12px;">Item: <strong>{listing_title}</strong> · Final bid: <strong>CA${hammer_price:,.2f}</strong></p>
        <p style="color:#475569;margin:0 0 16px;">Payment method: <strong>{method_label_en}</strong> — pay <strong>{seller_name}</strong> directly ({seller_contact}).</p>

        <div style="background:#fffbeb;border:2px solid #f59e0b;border-radius:12px;padding:18px;text-align:center;margin:16px 0;">
          <p style="margin:0;color:#92400e;text-transform:uppercase;font-size:11px;letter-spacing:0.05em;font-weight:bold;">🔑 Pickup Code / Code de collecte</p>
          <p style="margin:8px 0 4px;font-size:28px;font-weight:bold;color:#1e3a8a;letter-spacing:0.15em;font-family:'Courier New',monospace;">{pickup_code}</p>
          <p style="margin:0;color:#92400e;font-size:11px;">Transaction #{transaction_id[:8]}</p>
        </div>

        <p style="color:#334155;line-height:1.6;font-size:13px;">
          <strong>EN:</strong> Share this code with the seller <strong>ONLY after</strong> you have completed your payment.
          The seller must enter this code on BidVex to confirm receipt of payment and release your funds.
          Do <strong>NOT</strong> share before payment.
        </p>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:14px 0;">
        <p style="color:#334155;line-height:1.6;font-size:13px;">
          <strong>FR :</strong> Partagez ce code avec le vendeur <strong>UNIQUEMENT après</strong> avoir effectué votre paiement.
          Le vendeur doit saisir ce code sur BidVex pour confirmer la réception du paiement et libérer les fonds.
          <strong>NE PARTAGEZ PAS</strong> ce code avant le paiement.
        </p>

        <p style="color:#94a3b8;font-size:11px;text-align:center;margin-top:24px;">
          BidVex Inc. · GST# 706766367RT0001 · QST# 1233530880TQ0001 · All amounts in CAD<br>
          ({method_label_fr} — Montants en CAD)
        </p>
      </div>
    </div>
    """
    return await _send_via_unified(
        to_email=buyer["email"],
        subject=f"🔑 Your pickup code · Votre code de collecte — {pickup_code}",
        html_content=html,
    )


async def send_seller_pickup_instructions_email(
    *, seller: dict, listing_title: str, hammer_price: float,
    payment_method: str, transaction_id: str,
) -> bool:
    if not seller or not seller.get("email"):
        return False
    method_label_en = "Interac e-Transfer" if payment_method == "etransfer" else "Cash"
    method_label_fr = "Virement Interac" if payment_method == "etransfer" else "Comptant"
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:640px;margin:0 auto;padding:20px;background:#f8fafc;">
      <div style="background:white;padding:24px;border-radius:12px;border:1px solid #e2e8f0;">
        <h2 style="color:#16a34a;margin:0 0 8px;">✅ Your item has sold!</h2>
        <p style="color:#475569;margin:0 0 12px;">Item: <strong>{listing_title}</strong> · Sold for: <strong>CA${hammer_price:,.2f}</strong></p>
        <p style="color:#475569;margin:0 0 16px;">Payment method chosen by the buyer: <strong>{method_label_en}</strong>.</p>

        <div style="background:#ecfdf5;border:2px solid #16a34a;border-radius:12px;padding:18px;margin:16px 0;">
          <p style="margin:0 0 8px;color:#166534;text-transform:uppercase;font-size:11px;letter-spacing:0.05em;font-weight:bold;">🔑 How to release your funds / Libération des fonds</p>
          <p style="color:#334155;line-height:1.6;font-size:13px;margin:0 0 10px;">
            <strong>EN:</strong> Once you have received payment from the buyer, ask them for their <strong>Pickup Code</strong>
            (format <code>BVX-XXXXXXXX</code>) and enter it at
            <a href="https://www.bidvex.com/confirm-payment">bidvex.com/confirm-payment</a>.
            This confirms payment received and completes the transaction on BidVex.
            Your funds will be marked as settled.
          </p>
          <p style="color:#334155;line-height:1.6;font-size:13px;margin:0;">
            <strong>FR :</strong> Une fois le paiement reçu, demandez le <strong>Code de collecte</strong> à l'acheteur
            et saisissez-le sur
            <a href="https://www.bidvex.com/confirmer-paiement">bidvex.com/confirmer-paiement</a>.
            Cela confirme la réception et complète la transaction.
          </p>
        </div>

        <p style="color:#92400e;font-size:12px;background:#fef3c7;padding:12px;border-radius:6px;">
          ⚠️ The BidVex commission will be charged to your card on file within 24 hours of pickup-code confirmation.<br>
          La commission BidVex sera prélevée sur votre carte enregistrée dans les 24 heures.
        </p>

        <p style="color:#94a3b8;font-size:11px;text-align:center;margin-top:24px;">
          BidVex Inc. · GST# 706766367RT0001 · QST# 1233530880TQ0001 · Tx #{transaction_id[:8]}<br>
          ({method_label_fr})
        </p>
      </div>
    </div>
    """
    return await _send_via_unified(
        to_email=seller["email"],
        subject="✅ Item sold — pickup-code instructions · Article vendu — Instructions",
        html_content=html,
    )



# Fires for both the auction winner and the seller when an auction ends and
# a conversation is opened in `routes.messages.create_auction_won_conversation`.

# iter216 — Bilingual EN+FR "subscription active" email sent the moment an
# admin manual-settles an annual fee (partner / vehicle dealer / storage).

async def send_manual_subscription_active_email(
    *, user: dict, account_kind: str, amount_cad: float,
    method: str, renewal_until: str, reference: str = "",
) -> bool:
    if not user or not user.get("email"):
        return False
    name = user.get("name") or user.get("email")
    kind_label_en = {
        "partner": "Partner",
        "vehicle_dealer": "Vehicle Dealer",
        "storage_facility": "Storage Facility",
    }.get(account_kind, "Annual Subscription")
    kind_label_fr = {
        "partner": "Partenaire",
        "vehicle_dealer": "Concessionnaire de véhicules",
        "storage_facility": "Facilité d'entreposage",
    }.get(account_kind, "Abonnement annuel")
    method_label_en = {
        "e_transfer": "Interac e-Transfer",
        "cash": "Cash",
        "cheque": "Cheque",
        "wire": "Wire / Bank Transfer",
    }.get(method, method.replace("_", " ").title())
    method_label_fr = {
        "e_transfer": "Virement Interac",
        "cash": "Comptant",
        "cheque": "Chèque",
        "wire": "Virement bancaire",
    }.get(method, method.replace("_", " ").title())
    renewal_short = (renewal_until or "")[:10]
    ref_html = f"<p style='margin:6px 0;font-size:12px;color:#64748b;'>Reference / Référence: <code>{reference}</code></p>" if reference else ""
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f8fafc;">
      <div style="padding:24px;background:white;border-radius:12px;border:1px solid #e2e8f0;">
        <h2 style="color:#16a34a;margin:0 0 10px;">✅ Your annual subscription is active</h2>
        <p style="color:#334155;line-height:1.6;">Hi <strong>{name}</strong>,</p>
        <p style="color:#334155;line-height:1.6;">Your <strong>BidVex {kind_label_en}</strong> annual subscription payment has been confirmed by our team.</p>
        <div style="background:#ecfdf5;border:1px solid #16a34a;border-radius:8px;padding:14px;margin:12px 0;">
          <p style="margin:4px 0;"><strong>Amount paid:</strong> CA${amount_cad:,.2f}</p>
          <p style="margin:4px 0;"><strong>Method:</strong> {method_label_en}</p>
          <p style="margin:4px 0;"><strong>Active until:</strong> {renewal_short}</p>
          {ref_html}
        </div>
        <p style="color:#334155;line-height:1.6;">All features are now unlocked on your dashboard.</p>

        <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">

        <h2 style="color:#16a34a;margin:0 0 10px;">✅ Votre abonnement annuel est actif</h2>
        <p style="color:#334155;line-height:1.6;">Bonjour <strong>{name}</strong>,</p>
        <p style="color:#334155;line-height:1.6;">Votre paiement d'abonnement annuel BidVex <strong>{kind_label_fr}</strong> a été confirmé par notre équipe.</p>
        <div style="background:#ecfdf5;border:1px solid #16a34a;border-radius:8px;padding:14px;margin:12px 0;">
          <p style="margin:4px 0;"><strong>Montant payé :</strong> {amount_cad:,.2f} $ CAD</p>
          <p style="margin:4px 0;"><strong>Méthode :</strong> {method_label_fr}</p>
          <p style="margin:4px 0;"><strong>Actif jusqu'au :</strong> {renewal_short}</p>
        </div>
        <p style="color:#334155;line-height:1.6;">Toutes les fonctionnalités sont maintenant débloquées sur votre tableau de bord.</p>

        <p style="color:#94a3b8;font-size:11px;text-align:center;margin-top:24px;">
          BidVex Inc. · GST# 706766367RT0001 · QST# 1233530880TQ0001 · All amounts in CAD
        </p>
      </div>
    </div>
    """
    return await _send_via_unified(
        to_email=user["email"],
        subject="✅ Your annual subscription is active · Votre abonnement annuel est actif — BidVex",
        html_content=html,
    )


async def send_auction_thread_opened_email(
    *,
    recipient: dict,
    role: str,                # 'winner' | 'seller'
    counterparty: dict,
    listing_title: str,
    listing_id: str,
    conversation_id: str,
    winning_amount: float,
) -> bool:
    """Notify a winner or seller that a new message thread has been opened."""
    if not recipient or not recipient.get("email"):
        return False
    name = recipient.get("name") or recipient.get("first_name") or recipient.get("email")
    cp_name = (counterparty or {}).get("name") or "Your counterparty"
    amount_str = f"CA${float(winning_amount or 0):,.2f}"
    msg_link = f"https://www.bidvex.com/messages?conversation={conversation_id}"

    if role == "winner":
        subject = f"🎉 You won — message thread opened for {listing_title}"
        body_en = (
            f"Hi <strong>{name}</strong>,<br/><br/>"
            f"Congratulations — you won the auction for <strong>{listing_title}</strong> "
            f"with a final bid of <strong>{amount_str}</strong>.<br/><br/>"
            f"A direct message thread has been opened between you and the seller "
            f"(<strong>{cp_name}</strong>) to coordinate payment and pickup."
        )
        body_fr = (
            f"Bonjour <strong>{name}</strong>,<br/><br/>"
            f"Félicitations — vous avez remporté l'enchère pour <strong>{listing_title}</strong> "
            f"avec une mise finale de <strong>{amount_str}</strong>.<br/><br/>"
            f"Un fil de messages direct a été ouvert entre vous et le vendeur "
            f"(<strong>{cp_name}</strong>) pour coordonner le paiement et la cueillette."
        )
    else:  # seller
        subject = f"✅ Sold — message thread opened with the winning bidder ({listing_title})"
        body_en = (
            f"Hi <strong>{name}</strong>,<br/><br/>"
            f"Great news — your listing <strong>{listing_title}</strong> has sold for "
            f"<strong>{amount_str}</strong>.<br/><br/>"
            f"A direct message thread has been opened between you and the winning bidder "
            f"(<strong>{cp_name}</strong>) so you can coordinate payment and pickup."
        )
        body_fr = (
            f"Bonjour <strong>{name}</strong>,<br/><br/>"
            f"Bonne nouvelle — votre annonce <strong>{listing_title}</strong> a été vendue pour "
            f"<strong>{amount_str}</strong>.<br/><br/>"
            f"Un fil de messages direct a été ouvert entre vous et l'enchérisseur gagnant "
            f"(<strong>{cp_name}</strong>) pour coordonner le paiement et la cueillette."
        )

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;padding:20px;background:#f8fafc;border-radius:12px;">
      <div style="padding:20px;background:white;border-radius:8px;">
        <h2 style="color:#1e40af;margin:0 0 12px;">{subject}</h2>
        <p style="color:#334155;line-height:1.6;">{body_en}</p>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:16px 0;">
        <p style="color:#334155;line-height:1.6;">{body_fr}</p>
        <div style="text-align:center;margin-top:20px;">
          <a href="{msg_link}" style="display:inline-block;padding:12px 28px;background:#2563eb;color:white;text-decoration:none;border-radius:8px;font-weight:600;">
            Open message thread · Ouvrir le fil
          </a>
        </div>
        <p style="color:#64748b;font-size:11px;text-align:center;margin-top:24px;">
          BidVex — Listing #{listing_id[:8]}
        </p>
      </div>
    </div>
    """
    return await _send_via_unified(to_email=recipient["email"], subject=subject, html_content=html)



async def send_storage_facility_registration_verified_email(facility: dict) -> bool:
    if not facility or not facility.get("email"):
        return False
    body_en = (
        f"Good news, <strong>{facility.get('company_name','')}</strong>! "
        f"Your business-registration document has been verified by BidVex. "
        f"As soon as your overall facility status is approved, you'll be able to list storage units."
    )
    body_fr = (
        f"Bonne nouvelle, <strong>{facility.get('company_name','')}</strong>! "
        f"Votre document d'enregistrement d'entreprise a été vérifié par BidVex. "
        f"Dès que le statut global de votre facilité sera approuvé, vous pourrez lister des unités."
    )
    return await _send_via_unified(
        to_email=facility["email"],
        subject="✅ Business registration verified — BidVex Storage Auctions",
        html_content=_storage_panel(
            "Registration verified", "Enregistrement vérifié",
            body_en, body_fr,
            cta_url="https://www.bidvex.com/storage-dashboard",
            cta_en="Open dashboard", cta_fr="Ouvrir le tableau de bord",
        ),
    )


async def send_storage_facility_registration_rejected_email(facility: dict, reason: str) -> bool:
    if not facility or not facility.get("email"):
        return False
    safe_reason = (reason or "").strip() or "Document did not meet our verification requirements."
    body_en = (
        f"Hi <strong>{facility.get('company_name','')}</strong>,<br/><br/>"
        f"Your business-registration document was <strong>not accepted</strong> by our verification team.<br/><br/>"
        f"<strong>Reason from BidVex:</strong> {safe_reason}<br/><br/>"
        f"Please return to your registration page, upload a corrected document, "
        f"and resubmit. We'll review the new document within 1–2 business days."
    )
    body_fr = (
        f"Bonjour <strong>{facility.get('company_name','')}</strong>,<br/><br/>"
        f"Votre document d'enregistrement d'entreprise <strong>n'a pas été accepté</strong> par notre équipe de vérification.<br/><br/>"
        f"<strong>Motif de BidVex :</strong> {safe_reason}<br/><br/>"
        f"Veuillez retourner à votre page d'inscription, téléverser un document corrigé "
        f"et le soumettre à nouveau. Nous examinerons le nouveau document sous 1 à 2 jours ouvrables."
    )
    return await _send_via_unified(
        to_email=facility["email"],
        subject="⚠️ Action required — Business registration not accepted",
        html_content=_storage_panel(
            "Registration not accepted", "Enregistrement non accepté",
            body_en, body_fr,
            cta_url="https://www.bidvex.com/storage-auctions/register-facility?resubmit=1",
            cta_en="Resubmit document", cta_fr="Soumettre à nouveau",
        ),
    )


# ─────────────────────────────────────────────────────────────
# iter175 — Vehicle deposit auto-captured (bilingual EN+FR per Bill 96)
# ─────────────────────────────────────────────────────────────
async def send_vehicle_deposit_captured_email(
    buyer: dict,
    invoice: dict,
    deposit: dict,
    captured_amount: float,
) -> bool:
    """
    Sent automatically when the auto-capture cron job captures a $500 vehicle
    bidding deposit because the winner's 2.5% platform-fee invoice remained
    unpaid past `payment_deadline + 48h`. EN+FR per Bill 96.
    """
    if not buyer or not buyer.get("email"):
        return False

    inv_no = invoice.get("invoice_number", "—")
    veh_title = invoice.get("vehicle_title", "your vehicle")
    fee_total = invoice.get("total_amount") or invoice.get("platform_fee") or 0
    amt = captured_amount or deposit.get("amount") or 500.0

    body_en = (
        f"Your $500 bidding deposit for <strong>{veh_title}</strong> has been "
        f"captured because invoice <strong>{inv_no}</strong> "
        f"(${fee_total:.2f} CAD platform fee) was not paid within 48 hours of "
        f"the deadline. Amount captured: <strong>${amt:.2f} CAD</strong>. "
        f"This brings your account into good standing — no further action is required. "
        f"If you believe this was in error, contact support@bidvex.com within 14 days."
    )
    body_fr = (
        f"Votre dépôt d'enchère de 500 $ pour <strong>{veh_title}</strong> a été "
        f"saisi parce que la facture <strong>{inv_no}</strong> "
        f"({fee_total:.2f} $ CAD de frais de plateforme) n'a pas été payée dans les "
        f"48 heures suivant l'échéance. Montant saisi : <strong>{amt:.2f} $ CAD</strong>. "
        f"Votre compte est maintenant en règle — aucune autre action requise. "
        f"Si vous croyez qu'il s'agit d'une erreur, contactez support@bidvex.com dans les 14 jours."
    )

    html = _storage_panel(
        "Bidding deposit captured",
        "Dépôt d'enchère saisi",
        body_en,
        body_fr,
        cta_url="https://www.bidvex.com/profile/settings?tab=billing",
        cta_en="View invoices",
        cta_fr="Voir les factures",
    )
    return await _send_via_unified(
        to_email=buyer["email"],
        subject=f"[BidVex] Bidding deposit captured · Dépôt saisi — Invoice {inv_no}",
        html_content=html,
    )



# ===== BUG 5: POST-AUCTION EMAILS (Seller) =====

async def send_seller_auction_sold_email(
    seller_email: str,
    seller_name: str,
    listing_title: str,
    listing_id: str,
    hammer_price: float,
    platform_fee: float,
    net_payout: float,
    winning_bidder_alias: str,
    auction_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Sent to the seller when their auction ends with at least one bid."""
    label = _section_label(auction_type)
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #10b981;">🏁 Your auction ended — item sold / Votre enchère est terminée</h2>

    <p style="color: #475569; line-height: 1.6;">Hi {seller_name},</p>

    <p style="color: #475569; line-height: 1.6;">
        Great news — your {label['name_en']} auction ended and the item has sold.
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" border="0" style="margin: 20px 0;">
      <tr><td style="background-color: #ecfdf5; border: 2px solid #10b981; border-radius: 8px; padding: 25px;">
        <p style="margin: 0 0 12px 0; color: #065f46; font-size: 18px; font-weight: bold;">{listing_title}</p>
        <table width="100%" style="font-size: 14px; color: #1e293b;">
          <tr><td style="padding: 6px 0;">Hammer Price:</td>
              <td style="padding: 6px 0; text-align: right; font-weight: bold;">{_format_currency(hammer_price)}</td></tr>
          <tr><td style="padding: 6px 0;">Platform Fee:</td>
              <td style="padding: 6px 0; text-align: right; color: #dc2626;">−{_format_currency(platform_fee)}</td></tr>
          <tr><td style="padding: 6px 0; border-top: 1px solid #d1fae5;"><strong>Your Payout (est.):</strong></td>
              <td style="padding: 6px 0; text-align: right; border-top: 1px solid #d1fae5; font-size: 18px; color: #065f46; font-weight: bold;">{_format_currency(net_payout)}</td></tr>
          <tr><td style="padding: 6px 0;">Winning Bidder:</td>
              <td style="padding: 6px 0; text-align: right; color: #475569;">{winning_bidder_alias}</td></tr>
        </table>
      </td></tr>
    </table>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
      <tr><td align="center" style="background-color: #10b981; padding: 14px 30px; border-radius: 8px;">
        <a href="{FRONTEND_URL}/dashboard/sales" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px;">Open Seller Dashboard</a>
      </td></tr>
    </table>

    <p style="color: #64748b; font-size: 13px; line-height: 1.6;">
        Your payout will be transferred to your connected Stripe account once the buyer completes payment (typically within 2–5 business days).
    </p>

    <hr style="border:0;border-top:1px solid #e2e8f0;margin:24px 0;" />
    <p style="color:#475569;line-height:1.6;">
        Bonjour {seller_name}, votre enchère {label['name_fr']} s'est terminée et l'article a été vendu pour {_format_currency(hammer_price)}.
        Votre paiement sera transféré sur votre compte Stripe connecté une fois que l'acheteur aura payé.
    </p>
    """
    return await _send_via_unified(
        to_email=seller_email,
        subject=f"Your auction ended — {listing_title} sold for {_format_currency(hammer_price)} | {label['name_en']}",
        html_content=_base_template(content, "Auction Ended — Item Sold", auction_type=auction_type),
    )


async def send_seller_auction_no_bids_email(
    seller_email: str,
    seller_name: str,
    listing_title: str,
    listing_id: str,
    auction_type: Optional[str] = None,
) -> Dict[str, Any]:
    """Sent to the seller when their auction ends with zero bids."""
    label = _section_label(auction_type)
    content = f"""
    <h2 style="margin: 0 0 20px 0; color: #f59e0b;">Your auction ended — no bids / Votre enchère s'est terminée sans enchères</h2>

    <p style="color: #475569; line-height: 1.6;">Hi {seller_name},</p>
    <p style="color: #475569; line-height: 1.6;">
        Your {label['name_en']} auction for <strong>{listing_title}</strong> ended without any bids.
        You can relist it — sometimes a fresh title, better photos, or a lower starting price makes the difference.
    </p>

    <table cellpadding="0" cellspacing="0" border="0" align="center" style="margin: 30px auto;">
      <tr><td align="center" style="background-color: #0ea5e9; padding: 14px 30px; border-radius: 8px;">
        <a href="{FRONTEND_URL}/listing/{listing_id}/edit" style="color: #ffffff; text-decoration: none; font-weight: bold; font-size: 16px;">Edit & Relist</a>
      </td></tr>
    </table>

    <hr style="border:0;border-top:1px solid #e2e8f0;margin:24px 0;" />
    <p style="color:#475569;line-height:1.6;">
        Bonjour {seller_name}, votre enchère {label['name_fr']} pour <strong>{listing_title}</strong> s'est terminée sans enchères.
        Vous pouvez la republier depuis votre tableau de bord vendeur.
    </p>
    """
    return await _send_via_unified(
        to_email=seller_email,
        subject=f"Your auction ended with no bids — {listing_title}",
        html_content=_base_template(content, "Auction Ended — No Bids", auction_type=auction_type),
    )


# ===== PROMOTION CONFIRMATION EMAIL =====

async def send_promotion_confirmation_email(
    seller_email: str,
    seller_name: str,
    listing_title: str,
    listing_id: str,
    listing_type: str,
    tier: str,
    boost_days: int,
    start_date,
    end_date,
    base_price: float,
    gst: float,
    qst: float,
    stripe_fee: float,
    grand_total: float,
    features,
) -> Dict[str, Any]:
    """Sent after Stripe confirms payment for a listing promotion."""
    _lt = (listing_type or "marketplace").lower()
    _brand_type = "lots" if _lt in ("lots", "partner") else ("storage" if _lt == "storage" else "marketplace")
    label = _section_label(_brand_type)

    feats = "".join([f"<li style='color:#1e293b;padding:2px 0;'>{f}</li>" for f in (features or [])])

    def _fmt(d):
        try:
            return d.strftime("%Y-%m-%d")
        except Exception:
            return str(d)

    tier_label = {"basic": "Basic Boost", "standard": "Standard Boost", "premium": "Premium Boost"}.get(tier, tier.title())

    content = f"""
    <h2 style="margin:0 0 20px 0;color:#10b981;">✅ Your listing is now boosted / Votre annonce est propulsée</h2>

    <p style="color:#475569;line-height:1.6;">Hi {seller_name},</p>
    <p style="color:#475569;line-height:1.6;">
        Your {label['name_en']} listing has been successfully promoted.
    </p>

    <table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;">
      <tr><td style="background:#ecfdf5;border:2px solid #10b981;border-radius:8px;padding:25px;">
        <p style="margin:0 0 12px 0;color:#065f46;font-size:18px;font-weight:bold;">{listing_title}</p>
        <table width="100%" style="font-size:14px;color:#1e293b;">
          <tr><td>Tier:</td><td style="text-align:right;"><strong>{tier_label} ({boost_days} days)</strong></td></tr>
          <tr><td>Start:</td><td style="text-align:right;">{_fmt(start_date)}</td></tr>
          <tr><td>End:</td><td style="text-align:right;">{_fmt(end_date)}</td></tr>
        </table>
        <p style="margin:16px 0 6px;color:#065f46;font-weight:bold;">Features activated:</p>
        <ul style="margin:0 0 0 20px;padding:0;">{feats}</ul>
      </td></tr>
    </table>

    <h3 style="margin:20px 0 10px;color:#0f172a;">Payment receipt</h3>
    <table width="100%" cellpadding="0" cellspacing="0" style="font-size:14px;color:#1e293b;">
      <tr><td>Base price:</td><td style="text-align:right;">{_format_currency(base_price)}</td></tr>
      <tr><td>GST (5%):</td><td style="text-align:right;">{_format_currency(gst)}</td></tr>
      <tr><td>QST (9.975%):</td><td style="text-align:right;">{_format_currency(qst)}</td></tr>
      <tr><td>Payment Processing:</td><td style="text-align:right;">{_format_currency(stripe_fee)}</td></tr>
      <tr><td style="border-top:1px solid #e2e8f0;padding-top:6px;"><strong>Total Charged:</strong></td>
          <td style="border-top:1px solid #e2e8f0;padding-top:6px;text-align:right;font-weight:bold;">{_format_currency(grand_total)} CAD</td></tr>
    </table>

    <table cellpadding="0" cellspacing="0" align="center" style="margin:30px auto;">
      <tr><td align="center" style="background:#10b981;padding:14px 30px;border-radius:8px;">
        <a href="{FRONTEND_URL}/listing/{listing_id}" style="color:#fff;text-decoration:none;font-weight:bold;">View Your Listing</a>
      </td></tr>
    </table>

    <p style="color:#64748b;font-size:13px;">Questions? <a href="mailto:support@bidvex.ca">support@bidvex.ca</a></p>

    <hr style="border:0;border-top:1px solid #e2e8f0;margin:24px 0;" />
    <p style="color:#475569;line-height:1.6;">
        Bonjour {seller_name}, votre annonce {label['name_fr']} a été promue avec succès ({tier_label}, {boost_days} jours).
    </p>
    """
    return await _send_via_unified(
        to_email=seller_email,
        subject=f"✅ Your listing is now boosted — {listing_title} | {label['name_en']}",
        html_content=_base_template(content, "Listing Promoted", auction_type=_brand_type),
    )



# ============================================================
# Deposit refund / charge / payout notifications (Spec Feature 2 + 3)
# ============================================================

async def send_deposit_refunded_email(
    db, *, user_id: str, auction_id: str, amount: float, currency: str = "CAD"
) -> bool:
    """Send refund-confirmation email after non-winner deposit is refunded."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "name": 1})
    if not user or not user.get("email"):
        return False
    listing = (
        await db.listings.find_one({"id": auction_id}, {"_id": 0, "title": 1})
        or await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0, "title": 1})
        or await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0, "unit_number": 1})
        or {}
    )
    title = listing.get("title") or listing.get("unit_number") or auction_id
    cur = (currency or "CAD").upper()
    name = user.get("name") or user.get("email").split("@")[0]
    content = f"""
    <h2 style="color:#1e40af">Your deposit has been refunded · Votre dépôt a été remboursé</h2>
    <p>Hi {name},</p>
    <p><strong>EN:</strong> Your deposit of <strong>${amount:,.2f} {cur}</strong> for auction
    <em>“{title}”</em> has been refunded. It will appear on your statement within 5–7 business days.</p>
    <p><strong>FR:</strong> Votre dépôt de <strong>{amount:,.2f} $ {cur}</strong> pour
    l’enchère <em>« {title} »</em> a été remboursé. Il apparaîtra sur votre relevé d’ici 5 à 7 jours ouvrables.</p>
    <p>— The BidVex Team / L’équipe BidVex</p>
    """
    return await _send_via_unified(
        to_email=user["email"],
        subject=f"Deposit refunded · Dépôt remboursé — ${amount:,.2f} {cur}",
        html_content=_base_template(content, "Deposit Refunded"),
    )


async def send_charge_confirmation_email(
    db, *, user_id: str, auction_id: str, amount: float, currency: str = "CAD",
    charge_type: str = "buyer_commission",
) -> bool:
    """Notify user of a successful charge (winner full / commission / seller)."""
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "email": 1, "name": 1})
    if not user or not user.get("email"):
        return False
    listing = (
        await db.listings.find_one({"id": auction_id}, {"_id": 0, "title": 1})
        or await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0, "title": 1})
        or {}
    )
    title = listing.get("title") or auction_id
    cur = (currency or "CAD").upper()
    label_en = {
        "buyer_commission": "BidVex Buyer Commission",
        "buyer_full_payment": "BidVex Purchase",
        "buy_now_payment": "Buy Now Purchase",
        "seller_commission": "BidVex Seller Commission",
        "seller_payout": "BidVex Sale Payout",
    }.get(charge_type, "BidVex Charge")
    label_fr = {
        "buyer_commission": "Commission acheteur BidVex",
        "buyer_full_payment": "Achat BidVex",
        "buy_now_payment": "Achat immédiat",
        "seller_commission": "Commission vendeur BidVex",
        "seller_payout": "Paiement vendeur BidVex",
    }.get(charge_type, "Charge BidVex")
    name = user.get("name") or user.get("email").split("@")[0]
    content = f"""
    <h2 style="color:#1e40af">{label_en} · {label_fr}</h2>
    <p>Hi {name},</p>
    <p><strong>EN:</strong> Your card has been charged <strong>${amount:,.2f} {cur}</strong>
    ({label_en}) for auction <em>“{title}”</em>.</p>
    <p><strong>FR:</strong> Votre carte a été débitée de <strong>{amount:,.2f} $ {cur}</strong>
    ({label_fr}) pour l’enchère <em>« {title} »</em>.</p>
    <p>— The BidVex Team / L’équipe BidVex</p>
    """
    return await _send_via_unified(
        to_email=user["email"],
        subject=f"{label_en} · {label_fr} — ${amount:,.2f} {cur}",
        html_content=_base_template(content, label_en),
    )


async def send_payout_confirmation_email(
    db, *, seller_id: str, auction_id: str, amount: float, currency: str = "CAD",
) -> bool:
    """Notify seller their Connect payout was initiated."""
    seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "email": 1, "name": 1})
    if not seller or not seller.get("email"):
        return False
    listing = (
        await db.listings.find_one({"id": auction_id}, {"_id": 0, "title": 1})
        or await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0, "title": 1})
        or {}
    )
    title = listing.get("title") or auction_id
    cur = (currency or "CAD").upper()
    name = seller.get("name") or seller.get("email").split("@")[0]
    content = f"""
    <h2 style="color:#1e40af">Sale payout initiated · Paiement de vente initié</h2>
    <p>Hi {name},</p>
    <p><strong>EN:</strong> Your sale payout of <strong>${amount:,.2f} {cur}</strong> for
    auction <em>“{title}”</em> has been initiated through Stripe Connect.</p>
    <p><strong>FR:</strong> Le paiement de votre vente de <strong>{amount:,.2f} $ {cur}</strong>
    pour l’enchère <em>« {title} »</em> a été initié via Stripe Connect.</p>
    <p>— The BidVex Team / L’équipe BidVex</p>
    """
    return await _send_via_unified(
        to_email=seller["email"],
        subject=f"Sale payout · Paiement de vente — ${amount:,.2f} {cur}",
        html_content=_base_template(content, "Payout Initiated"),
    )


# ============================================================
# iter189 — Promotion expiry + email blast notifications
# ============================================================

async def send_promotion_expired_email(
    *, seller_email: str, seller_name: str, listing_title: str,
    listing_id: str, listing_type: str, tier: str = "basic",
) -> bool:
    """Notify seller their boost expired and prompt them to renew."""
    renew_path = {
        "marketplace": f"/listing/{listing_id}",
        "lots": f"/lots-auction/{listing_id}",
        "vehicle": f"/vehicle-auctions/{listing_id}",
        "storage": f"/storage-auctions/{listing_id}",
    }.get(listing_type, f"/listing/{listing_id}")
    tier_label = {"basic": "Basic", "standard": "Standard", "premium": "Premium"}.get(tier, tier.title())
    content = f"""
    <h2 style="color:#1e40af">Your boost has ended · Votre promotion est terminée</h2>
    <p>Hi {seller_name or 'Seller'},</p>
    <p><strong>EN:</strong> Your <strong>{tier_label}</strong> boost for
    <em>"{listing_title}"</em> has ended. Your listing is no longer featured —
    <a href="https://bidvex.com{renew_path}" style="color:#2563eb">renew to stay featured</a>.</p>
    <p><strong>FR:</strong> Votre promotion <strong>{tier_label}</strong> pour
    <em>« {listing_title} »</em> est terminée. Votre annonce n'est plus en vedette —
    <a href="https://bidvex.com{renew_path}" style="color:#2563eb">renouvelez pour rester en vedette</a>.</p>
    <p>— The BidVex Team / L'équipe BidVex</p>
    """
    return await _send_via_unified(
        to_email=seller_email,
        subject=f"Your boost ended · Votre promotion est terminée — {listing_title}",
        html_content=_base_template(content, "Boost Ended"),
    )


async def send_promotion_email_blast(
    *, to_email: str, listing_title: str, listing_id: str,
    listing_type: str, category: str = "",
) -> bool:
    """T+24h email blast to category subscribers for premium-boosted listings."""
    path = {
        "marketplace": f"/listing/{listing_id}",
        "lots": f"/lots-auction/{listing_id}",
        "vehicle": f"/vehicle-auctions/{listing_id}",
        "storage": f"/storage-auctions/{listing_id}",
    }.get(listing_type, f"/listing/{listing_id}")
    content = f"""
    <h2 style="color:#1e40af">Featured · En vedette : {listing_title}</h2>
    <p><strong>EN:</strong> Don't miss this featured auction —
    <a href="https://bidvex.com{path}" style="color:#2563eb">view auction</a>.</p>
    <p><strong>FR:</strong> Ne manquez pas cette enchère en vedette —
    <a href="https://bidvex.com{path}" style="color:#2563eb">voir l'enchère</a>.</p>
    <p>— The BidVex Team / L'équipe BidVex</p>
    """
    return await _send_via_unified(
        to_email=to_email,
        subject=f"Featured: {listing_title} — Don't Miss This Auction · En vedette : Ne manquez pas",
        html_content=_base_template(content, "Featured Auction"),
    )


# ============= DEALER LICENSE VERIFICATION EMAILS (iter195) =============

async def send_dealer_license_approved_email(user: dict, license_doc: dict) -> bool:
    """Notify a buyer their dealer-license verification is approved."""
    if not user or not user.get("email"):
        return False
    license_no = license_doc.get("license_number", "")[:32]
    jurisdiction = license_doc.get("jurisdiction", "")
    body_en = (
        f"Your dealer license has been verified. You can now bid on licensed-only vehicle "
        f"auctions on BidVex.<br/><br/>"
        f"License #: <strong>{license_no}</strong> ({jurisdiction})<br/>"
        f"Status: <strong style='color:#059669;'>Approved</strong>"
    )
    body_fr = (
        f"Votre permis de concessionnaire a été vérifié. Vous pouvez maintenant enchérir "
        f"sur les enchères de véhicules réservées aux concessionnaires sur BidVex.<br/><br/>"
        f"N° de permis : <strong>{license_no}</strong> ({jurisdiction})<br/>"
        f"Statut : <strong style='color:#059669;'>Approuvé</strong>"
    )
    # iter249 Mission 3 — Language-aware subject (body already bilingual).
    _dl_lang = _detect_language(user)
    subject_dl = (
        "✅ Permis de concessionnaire vérifié"
        if _dl_lang == "fr"
        else "✅ Dealer License Verified · Permis de concessionnaire vérifié"
    )
    return await _send_via_unified(
        to_email=user["email"],
        subject=subject_dl,
        html_content=_storage_panel(
            "Dealer License Approved", "Permis de concessionnaire approuvé",
            body_en, body_fr,
            cta_url="https://bidvex.com/vehicle-auctions",
            cta_en="Browse Vehicle Auctions",
            cta_fr="Parcourir les enchères de véhicules",
        ),
    )


async def send_dealer_license_rejected_email(user: dict, license_doc: dict, reason: str = "") -> bool:
    """Notify a buyer their dealer-license verification was rejected."""
    if not user or not user.get("email"):
        return False
    license_no = license_doc.get("license_number", "")[:32]
    reason_en = reason or "Please contact support for more information."
    reason_fr = reason or "Veuillez contacter le support pour plus d'informations."
    body_en = (
        f"Your dealer license submission was reviewed and unfortunately could not be approved.<br/><br/>"
        f"License #: <strong>{license_no}</strong><br/>"
        f"Reason: <em>{reason_en}</em><br/><br/>"
        f"You may resubmit a corrected license at any time."
    )
    body_fr = (
        f"Votre soumission de permis de concessionnaire a été examinée et n'a malheureusement pas pu être approuvée.<br/><br/>"
        f"N° de permis : <strong>{license_no}</strong><br/>"
        f"Raison : <em>{reason_fr}</em><br/><br/>"
        f"Vous pouvez soumettre à nouveau un permis corrigé à tout moment."
    )
    return await _send_via_unified(
        to_email=user["email"],
        subject="Dealer License Verification — Action Required · Action requise",
        html_content=_storage_panel(
            "License Verification Rejected", "Vérification du permis rejetée",
            body_en, body_fr,
            cta_url="https://bidvex.com/vehicle-auctions/dealer-license",
            cta_en="Resubmit Dealer License",
            cta_fr="Resoumettre le permis",
        ),
    )


async def send_dealer_license_expired_email(user: dict, license_doc: dict) -> bool:
    """Notify a buyer their dealer-license verification has expired."""
    if not user or not user.get("email"):
        return False
    license_no = license_doc.get("license_number", "")[:32]
    expiry = license_doc.get("expiry_date", "")
    if hasattr(expiry, "strftime"):
        expiry = expiry.strftime("%Y-%m-%d")
    body_en = (
        f"Your dealer license on file has expired. To continue bidding on licensed-only "
        f"vehicle auctions, please submit your renewed license.<br/><br/>"
        f"License #: <strong>{license_no}</strong><br/>"
        f"Expired on: <strong>{expiry}</strong>"
    )
    body_fr = (
        f"Votre permis de concessionnaire enregistré a expiré. Pour continuer à enchérir "
        f"sur les enchères réservées aux concessionnaires, veuillez soumettre votre permis renouvelé.<br/><br/>"
        f"N° de permis : <strong>{license_no}</strong><br/>"
        f"Expiré le : <strong>{expiry}</strong>"
    )
    return await _send_via_unified(
        to_email=user["email"],
        subject="⚠️ Dealer License Expired · Permis de concessionnaire expiré",
        html_content=_storage_panel(
            "Dealer License Expired", "Permis expiré",
            body_en, body_fr,
            cta_url="https://bidvex.com/vehicle-auctions/dealer-license",
            cta_en="Renew License",
            cta_fr="Renouveler le permis",
        ),
    )



# ============= NEW MESSAGE EMAIL (iter196) =============

async def send_new_message_email(
    recipient: dict,
    sender_name: str,
    preview: str,
    listing_id: str = None,
    conversation_id: str = None,
) -> bool:
    """
    Send a bilingual notification when an offline user receives a new in-app message.
    """
    if not recipient or not recipient.get("email"):
        return False

    safe_preview = (preview or "").strip().replace("<", "&lt;").replace(">", "&gt;")
    if len(safe_preview) > 200:
        safe_preview = safe_preview[:200] + "…"

    cta_url = "https://bidvex.com/messages"
    if conversation_id:
        cta_url += f"?conversation={conversation_id}"

    body_en = (
        f"<strong>{sender_name}</strong> sent you a message on BidVex:<br/><br/>"
        f"<em style='border-left:3px solid #2563eb;padding-left:10px;display:block;margin:10px 0;color:#475569;'>"
        f"{safe_preview}</em>"
        f"<br/>Reply directly inside BidVex to keep your conversation secure."
    )
    body_fr = (
        f"<strong>{sender_name}</strong> vous a envoyé un message sur BidVex :<br/><br/>"
        f"<em style='border-left:3px solid #2563eb;padding-left:10px;display:block;margin:10px 0;color:#475569;'>"
        f"{safe_preview}</em>"
        f"<br/>Répondez directement dans BidVex pour garder votre conversation sécurisée."
    )

    return await _send_via_unified(
        to_email=recipient["email"],
        subject=f"💬 New message from {sender_name} · Nouveau message",
        html_content=_storage_panel(
            "You have a new message", "Vous avez un nouveau message",
            body_en, body_fr,
            cta_url=cta_url,
            cta_en="Open Conversation",
            cta_fr="Ouvrir la conversation",
        ),
    )


async def send_listing_requires_action_email(
    recipient: dict,
    listing_title: str,
    listing_id: str,
    reason_code: str = "iter201_phase2_compliance_fields_required",
) -> bool:
    """
    iter201 — Phase 2 — Notify a seller that one of their pre-existing vehicle
    listings has been flagged `requires_seller_action` because new mandatory
    compliance fields (category, condition matrix, accident/lien/use, payment
    methods) need to be filled in before the listing can return to the
    public marketplace.
    """
    if not recipient or not recipient.get("email"):
        return False

    safe_title = (listing_title or "Untitled vehicle").strip().replace("<", "&lt;").replace(">", "&gt;")
    cta_url = f"https://bidvex.com/vehicle-auctions/edit/{listing_id}"

    body_en = (
        f"BidVex has updated its vehicle listing requirements to comply with provincial dealer regulations across Canada. "
        f"Your existing listing <strong>{safe_title}</strong> needs a few additional fields filled in before it can return to the public marketplace.<br/><br/>"
        f"<strong>What's needed (≈2 minutes):</strong>"
        f"<ul style='margin:8px 0 8px 20px;padding:0;'>"
        f"<li>Vehicle category (cars, SUVs, trucks, etc.)</li>"
        f"<li>Condition (Excellent / Good / Fair / Salvage / Parts)</li>"
        f"<li>Accident history, lien status, previous use</li>"
        f"<li>Payment methods accepted, deposit requirement</li>"
        f"</ul>"
        f"Until then, your listing has been hidden from public view but is preserved as a draft."
    )
    body_fr = (
        f"BidVex a mis à jour ses exigences de listing de véhicules pour se conformer aux règlements provinciaux des concessionnaires partout au Canada. "
        f"Votre annonce existante <strong>{safe_title}</strong> nécessite quelques champs supplémentaires avant de pouvoir réapparaître publiquement.<br/><br/>"
        f"<strong>Ce qu'il faut faire (≈2 minutes) :</strong>"
        f"<ul style='margin:8px 0 8px 20px;padding:0;'>"
        f"<li>Catégorie du véhicule (voitures, VUS, camionnettes, etc.)</li>"
        f"<li>État (Excellent / Bon / Moyen / Récupération / Pièces)</li>"
        f"<li>Historique d'accidents, privilèges, usage antérieur</li>"
        f"<li>Modes de paiement acceptés, exigence de dépôt</li>"
        f"</ul>"
        f"En attendant, votre annonce est masquée du public mais conservée en tant que brouillon."
    )

    return await _send_via_unified(
        to_email=recipient["email"],
        subject="🛠️ Action required: update your BidVex vehicle listing · Mise à jour requise",
        html_content=_storage_panel(
            "Action required on your vehicle listing",
            "Action requise sur votre annonce de véhicule",
            body_en, body_fr,
            cta_url=cta_url,
            cta_en="Update Listing",
            cta_fr="Mettre à jour l'annonce",
        ),
    )


async def send_buyer_verification_decision_email(
    recipient: dict,
    decision: str,            # "approve" | "reject"
    province: Optional[str] = None,
    rejection_reason: Optional[str] = None,
    verification_type: Optional[str] = None,  # "dealer" | "dealer_representative"
) -> bool:
    """iter201 — Phase 3 / 3B — Bilingual buyer-verification decision email.

    Mirrors the polish of `send_dealer_license_approved_email` /
    `send_dealer_license_rejected_email`: structured body, regulator-aware
    province name, action-oriented CTA, masked status callouts.
    """
    if not recipient or not recipient.get("email"):
        return False
    province_code = (province or "your province").upper()
    province_label_en = {
        "ON": "Ontario", "NB": "New Brunswick", "NS": "Nova Scotia",
        "PE": "Prince Edward Island", "NL": "Newfoundland and Labrador",
        "BC": "British Columbia", "AB": "Alberta", "SK": "Saskatchewan",
        "MB": "Manitoba", "QC": "Quebec",
        "YT": "Yukon", "NT": "Northwest Territories", "NU": "Nunavut",
    }.get(province_code, province_code)
    province_label_fr = {
        "ON": "Ontario", "NB": "Nouveau-Brunswick", "NS": "Nouvelle-Écosse",
        "PE": "Île-du-Prince-Édouard", "NL": "Terre-Neuve-et-Labrador",
        "BC": "Colombie-Britannique", "AB": "Alberta", "SK": "Saskatchewan",
        "MB": "Manitoba", "QC": "Québec",
        "YT": "Yukon", "NT": "Territoires du Nord-Ouest", "NU": "Nunavut",
    }.get(province_code, province_code)
    type_label_en = "Dealer Representative" if verification_type == "dealer_representative" else "Licensed Dealer"
    type_label_fr = "Représentant de concessionnaire" if verification_type == "dealer_representative" else "Concessionnaire licencié"

    if decision == "approve":
        subject = "✅ Buyer Verification Approved · Vérification d'acheteur approuvée"
        body_en = (
            f"Your buyer verification for <strong>{province_label_en}</strong> has been approved. "
            f"You can now bid on dealer vehicle auctions in {province_label_en}.<br/><br/>"
            f"Verification type: <strong>{type_label_en}</strong><br/>"
            f"Status: <strong style='color:#059669;'>Approved</strong>"
        )
        body_fr = (
            f"Votre vérification d'acheteur pour <strong>{province_label_fr}</strong> a été approuvée. "
            f"Vous pouvez maintenant enchérir sur les enchères de véhicules de concessionnaires en {province_label_fr}.<br/><br/>"
            f"Type de vérification : <strong>{type_label_fr}</strong><br/>"
            f"Statut : <strong style='color:#059669;'>Approuvé</strong>"
        )
        cta_en, cta_fr = "Browse Vehicle Auctions", "Parcourir les enchères de véhicules"
        cta_url = "https://bidvex.com/vehicle-auctions"
        title_en, title_fr = "Buyer Verification Approved", "Vérification d'acheteur approuvée"
    else:
        reason = (rejection_reason or "").strip() or (
            "Documents could not be verified."
        )
        reason_fr = (rejection_reason or "").strip() or (
            "Les documents n'ont pas pu être vérifiés."
        )
        subject = "❌ Buyer Verification Update · Mise à jour de la vérification"
        body_en = (
            f"Your buyer-verification submission for <strong>{province_label_en}</strong> was reviewed "
            f"and unfortunately could not be approved at this time.<br/><br/>"
            f"Reason: <em>{reason}</em><br/><br/>"
            f"You may resubmit with updated documents at any time."
        )
        body_fr = (
            f"Votre demande de vérification d'acheteur pour <strong>{province_label_fr}</strong> a été examinée "
            f"et n'a malheureusement pas pu être approuvée pour le moment.<br/><br/>"
            f"Raison : <em>{reason_fr}</em><br/><br/>"
            f"Vous pouvez resoumettre avec des documents mis à jour à tout moment."
        )
        cta_en, cta_fr = "Resubmit Verification", "Resoumettre la vérification"
        cta_url = "https://bidvex.com/profile/verification"
        title_en, title_fr = "Buyer Verification Update", "Mise à jour de la vérification d'acheteur"

    return await _send_via_unified(
        to_email=recipient["email"],
        subject=subject,
        html_content=_storage_panel(
            title_en, title_fr,
            body_en, body_fr,
            cta_url=cta_url,
            cta_en=cta_en,
            cta_fr=cta_fr,
        ),
    )


async def send_dealer_license_expiring_email(recipient: dict, days_until_expiry: int) -> bool:
    """iter201 — Phase 3 / 3C — 30-day warning before dealer licence expires."""
    if not recipient or not recipient.get("email"):
        return False
    return await _send_via_unified(
        to_email=recipient["email"],
        subject=f"⚠️ Your dealer licence expires in {days_until_expiry} days — BidVex · Licence expire bientôt",
        html_content=_storage_panel(
            "Your dealer licence expires soon",
            "Votre licence de concessionnaire expire bientôt",
            f"Your provincial dealer licence will expire in <strong>{days_until_expiry} days</strong>. "
            f"To keep your vehicle listings active, please upload your renewed licence document before the expiry date.",
            f"Votre licence provinciale de concessionnaire expirera dans <strong>{days_until_expiry} jours</strong>. "
            f"Pour garder vos annonces actives, veuillez téléverser votre licence renouvelée avant la date d'expiration.",
            cta_url="https://bidvex.com/seller/dealer-license",
            cta_en="Upload Renewed Licence",
            cta_fr="Téléverser la licence renouvelée",
        ),
    )


async def send_seller_license_expired_email(recipient: dict, suspended_count: int = 0) -> bool:
    """iter201 — Phase 3 / 3C — Hard expiry: SELLER licence expired, listings suspended.

    Distinct from `send_dealer_license_expired_email` which targets buyers
    whose iter195 dealer-license-verification record expired.
    """
    if not recipient or not recipient.get("email"):
        return False
    return await _send_via_unified(
        to_email=recipient["email"],
        subject="🚫 Your dealer licence has expired — listings suspended · Licence expirée",
        html_content=_storage_panel(
            "Your dealer licence has expired",
            "Votre licence de concessionnaire a expiré",
            f"Your provincial dealer licence has expired. To comply with provincial regulations, "
            f"BidVex has suspended <strong>{suspended_count}</strong> of your active vehicle listings. "
            f"Upload your renewed licence to reactivate them.",
            f"Votre licence provinciale de concessionnaire a expiré. Conformément aux règlements provinciaux, "
            f"BidVex a suspendu <strong>{suspended_count}</strong> de vos annonces actives. "
            f"Téléversez votre licence renouvelée pour les réactiver.",
            cta_url="https://bidvex.com/seller/dealer-license",
            cta_en="Upload Renewed Licence",
            cta_fr="Téléverser la licence renouvelée",
        ),
    )


