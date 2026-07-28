# iter295 P2 — Shared email helpers + SendGrid plumbing.
# Source of truth for branding, dispatch, suppression gates, and
# section / base / storage HTML scaffolds. The previous monolith
# `services/email_notifications.py` is now a thin re-export shim.
"""
BidVex Email Notification Service
Sends transactional emails for vehicle auctions
"""

import os
import asyncio
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Email configuration
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY")
# iter270 Deliverability fix — Canonical FROM = noreply@bidvex.com so
# DKIM/SPF/DMARC alignment is consistent across every outbound path.
# Reply-To is set per email-type (service@bidvex.com for transactional,
# contractor@bidvex.com for partner-related) so users still reach the right
# inbox when they hit Reply.
FROM_EMAIL = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@bidvex.com")
FROM_NAME = os.environ.get("SENDGRID_FROM_NAME", "BidVex Canada")

# iter254 Mission 4 / iter270 — Branded FROM addresses are now collapsed
# onto the unified noreply@bidvex.com sender (.com — not .ca) so Gmail/
# Outlook see the same authenticated domain on every message. The .ca
# address remains only as a Reply-To target for partner inboxes.
B2B_PARTNER_FROM_EMAIL = "noreply@bidvex.com"
B2B_PARTNER_FROM_NAME = "BidVex Canada"
B2B_PARTNER_REPLY_TO = "contractor@bidvex.com"
B2B_PARTNER_REPLY_TO_NAME = "BidVex Partner Team"
TRANSACTIONAL_FROM_EMAIL = "noreply@bidvex.com"
TRANSACTIONAL_FROM_NAME = "BidVex Canada"
TRANSACTIONAL_REPLY_TO = "service@bidvex.com"
TRANSACTIONAL_REPLY_TO_NAME = "BidVex Support"
MARKETING_REPLY_TO = "service@bidvex.com"
MARKETING_REPLY_TO_NAME = "BidVex Support"
FRONTEND_URL = os.environ.get("FRONTEND_URL", "https://www.bidvex.com")

# Check if SendGrid is available
SENDGRID_AVAILABLE = False
sg = None

try:
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import (
        Mail, Email, To, Content, Attachment,
        FileContent, FileName, FileType, Disposition,
    )
    # iter270 — Spam-classification helpers. Imported lazily/optionally
    # so older SDKs still work even if a helper isn't available.
    try:
        from sendgrid.helpers.mail import (
            Header as _SgHeader,
            Category as _SgCategory,
            TrackingSettings as _SgTrackingSettings,
            ClickTracking as _SgClickTracking,
            OpenTracking as _SgOpenTracking,
            SubscriptionTracking as _SgSubscriptionTracking,
            ReplyTo as _SgReplyTo,
        )
    except ImportError:
        _SgHeader = None
        _SgCategory = None
        _SgTrackingSettings = None
        _SgClickTracking = None
        _SgOpenTracking = None
        _SgSubscriptionTracking = None
        _SgReplyTo = None
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


# ─── iter314 — Mandatory BidVex Logo Injection ──────────────────────────
#
# Every outbound email (transactional, marketing, system, admin-triggered,
# external campaign, scheduled, manual) MUST display the BidVex logo
# at the top, immediately after the preheader and before any subject-
# matter content. We accomplish this with a single idempotent
# injector applied:
#
#   (a) Inside `send_email()` — the canonical dispatcher most paths use.
#   (b) Inside `send_external_campaign_email()` — for admin-authored
#       raw HTML (wraps body inside the standard BidVex header + footer).
#   (c) Inside any remaining direct `sg.send()` call sites (legacy paths
#       in `email_service.py`, `routes/admin_config.py`, `routes/auth.py`).
#
# The canonical logo URL is hosted on SendGrid's CDN and must not be
# rehosted or substituted (per iter314 directive).
BIDVEX_LOGO_URL = (
    "http://cdn.mcauto-images-production.sendgrid.net/"
    "4fbf02710175d39f/91d027c2-73da-4510-9bce-ee1ce34f16a7/4500x1080.png"
)
BIDVEX_LOGO_ID_TOKEN = "/91d027c2-73da-4510-9bce-ee1ce34f16a7/"  # idempotency marker
BIDVEX_LOGO_BLOCK = (
    '<tr>'
    '<td style="background-color: #0b1a30; padding: 25px 40px; text-align: left;">'
    '<a href="https://bidvex.com" target="_blank" style="text-decoration: none;">'
    f'<img src="{BIDVEX_LOGO_URL}" alt="BidVex" border="0" '
    'style="display: block; height: 32px; max-height: 32px; width: auto;">'
    '</a>'
    '</td>'
    '</tr>'
)


def inject_bidvex_logo_header(html: str) -> str:
    """iter314 — Idempotently prepend the canonical BidVex logo row to
    the first <table> inside an HTML email body.

    Strategy (in order):
      1. If the HTML already contains the canonical logo URL anywhere
         (matched by its unique CDN id-token), return it unchanged.
         This protects emails that already render through a wrapper
         that itself contains the logo (e.g. BIDVEX_EMAIL_TEMPLATE in
         services/email_templates.py).
      2. If the HTML contains a `<table ...>` open tag, insert
         BIDVEX_LOGO_BLOCK as the first child <tr>. This is the
         Outlook-safe path — the logo becomes the first content row of
         the email's main table.
      3. Otherwise, wrap the whole HTML in a minimal Outlook-safe
         <table> with the logo as the first row. This is a defensive
         fallback for plain-string HTML snippets.
    """
    if not html or not isinstance(html, str):
        return html
    if BIDVEX_LOGO_ID_TOKEN in html:
        return html  # logo already present — no duplicates
    # iter314 — also catch the older (pre-canonical) logo URL token
    # that may live in legacy template snapshots; we don't *replace*
    # it here (callers that own those templates have been migrated
    # to the canonical URL), but we *don't* double-inject either.
    if "31636d5f-c160-446b-b715-bcf542e9607e" in html:
        return html
    import re as _re
    m = _re.search(r"<table\b[^>]*>", html, flags=_re.IGNORECASE)
    if m:
        head = html[: m.end()]
        tail = html[m.end():]
        return head + BIDVEX_LOGO_BLOCK + tail
    # Fallback wrapper.
    return (
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="background-color:#f1f5f9;font-family:Arial,sans-serif;">'
        f'{BIDVEX_LOGO_BLOCK}'
        '<tr><td style="padding:24px;background-color:#ffffff;">'
        + html +
        '</td></tr>'
        '</table>'
    )


async def send_email(
    to_email: str,
    subject: str,
    html_content: str,
    attachments: List[Dict] = None,
    from_email: Optional[str] = None,
    from_name: Optional[str] = None,
    reply_to: Optional[str] = None,
    reply_to_name: Optional[str] = None,
    is_marketing: bool = False,
    categories: Optional[List[str]] = None,
    custom_args: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """iter244 Mission 2 — Canonical low-level SendGrid dispatcher.
    iter254 Mission 4 — Now accepts optional `from_email`/`from_name`/
    `reply_to` overrides so individual outbound paths can stamp branded
    headers (`contractor@bidvex.com` for B2B blasts, `service@bidvex.com`
    for transactional). Defaults preserve the existing global FROM.

    iter266 Mission 2 — Universal suppression gate. Skips every send
    (including raw-HTML and html_full_override paths) when the
    recipient is in `email_suppressions` OR (for marketing emails) has
    `marketing_unsubscribed=True` on their user record. Returns a
    `{"status": "skipped", "reason": ...}` envelope without any
    SendGrid round-trip.

    iter270 deliverability fix — Adds the full Gmail-Promotions /
    CAN-SPAM / CASL header set on every send:
      • List-Unsubscribe + List-Unsubscribe-Post on marketing emails
      • SendGrid Categories so Activity Feed segments correctly
      • Click-tracking OFF (kills url8676-style redirects that flag spam)
      • Open-tracking ON (pixel only, neutral)
      • X-Entity-Ref-ID (per-recipient/day) to avoid Gmail grouping
      • Precedence: bulk on marketing emails
      • X-Mailer stamp for forensic traceability
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
        # iter314 — Mandatory BidVex logo on every outbound email.
        # Idempotent: if the html already contains the canonical logo
        # URL (because it was rendered through a wrapper that already
        # includes it), this is a no-op.
        html_content = inject_bidvex_logo_header(html_content)

        # iter366 — Replace the {{UNSUBSCRIBE_URL}} placeholder in the
        # HTML footer with a signed one-click token URL. This makes the
        # visible unsubscribe link work end-to-end without asking the
        # user to type their email. Transactional emails still ship the
        # link because the endpoint gracefully handles both modes
        # (marketing-only opt-out; transactional emails remain).
        if "{{UNSUBSCRIBE_URL}}" in html_content:
            try:
                from routes.unsubscribe import build_unsubscribe_urls
                _unsub = build_unsubscribe_urls(to_email).get("en", "")
            except Exception:
                _unsub = f"{FRONTEND_URL}/unsubscribe?email={to_email}"
            if not _unsub:
                _unsub = f"{FRONTEND_URL}/unsubscribe?email={to_email}"
            html_content = html_content.replace("{{UNSUBSCRIBE_URL}}", _unsub)

        # iter270 — Always send from the unified noreply@bidvex.com so
        # the same DKIM key + SPF record + DMARC policy is used on every
        # message. Callers can pass `from_name` to keep their branded
        # display name (e.g. "BidVex Partner Team") but the address
        # is locked to the authenticated sender. Reply-To preserves
        # the intended human inbox.
        _from = FROM_EMAIL  # Force canonical sender — overrides ignored.
        _from_name = from_name or FROM_NAME
        message = Mail(
            from_email=Email(_from, _from_name),
            to_emails=To(to_email),
            subject=subject,
            html_content=Content("text/html", html_content)
        )

        # ── Reply-To ──
        # Pick the right human inbox if not explicitly provided.
        _reply_to = reply_to
        _reply_to_name = reply_to_name
        if not _reply_to:
            if is_marketing:
                _reply_to = MARKETING_REPLY_TO
                _reply_to_name = MARKETING_REPLY_TO_NAME
            else:
                _reply_to = TRANSACTIONAL_REPLY_TO
                _reply_to_name = TRANSACTIONAL_REPLY_TO_NAME
        try:
            if _SgReplyTo is not None:
                message.reply_to = _SgReplyTo(_reply_to, _reply_to_name)
            else:
                message.reply_to = Email(_reply_to, _reply_to_name)
        except Exception:
            message.reply_to = Email(_reply_to)

        # ── iter270 — Spam-busting headers & categories ──
        if _SgHeader is not None:
            try:
                # Per-recipient, per-day entity id stops Gmail from
                # collapsing many similar broadcasts into the spam folder.
                import hashlib as _hashlib
                entity_id = _hashlib.sha256(
                    f"{to_email}|{subject}|{datetime.now(timezone.utc).date().isoformat()}".encode()
                ).hexdigest()[:32]
                message.add_header(_SgHeader("X-Entity-Ref-ID", entity_id))
                message.add_header(_SgHeader("X-Mailer", "BidVex Email System v2.0"))
                if is_marketing:
                    # iter366 — Generate a SIGNED token so the frontend
                    # /unsubscribe page can auto-verify and confirm without
                    # asking the user for their email. The old `?email=`
                    # scheme produced a 400 `token_missing` and users saw
                    # a broken page.
                    try:
                        from routes.unsubscribe import build_unsubscribe_urls
                        unsub_url = build_unsubscribe_urls(to_email).get("en", "")
                    except Exception:
                        unsub_url = f"{FRONTEND_URL}/unsubscribe?email={to_email}"
                    if not unsub_url:
                        unsub_url = f"{FRONTEND_URL}/unsubscribe?email={to_email}"
                    message.add_header(_SgHeader(
                        "List-Unsubscribe",
                        f"<{unsub_url}>, <mailto:unsubscribe@bidvex.com?subject=unsubscribe>",
                    ))
                    message.add_header(_SgHeader(
                        "List-Unsubscribe-Post",
                        "List-Unsubscribe=One-Click",
                    ))
                    message.add_header(_SgHeader("Precedence", "bulk"))
            except Exception as _hexc:  # noqa: BLE001
                logger.debug(f"[email-headers] skipped: {_hexc}")

        # ── SendGrid Categories ──
        try:
            _cats = list(categories or [])
            if not _cats:
                _cats = ["marketing", "promotional"] if is_marketing else ["transactional"]
            if _SgCategory is not None:
                for cat in _cats:
                    message.add_category(_SgCategory(cat))
            else:
                for cat in _cats:
                    message.add_category(cat)
        except Exception as _cexc:  # noqa: BLE001
            logger.debug(f"[email-categories] skipped: {_cexc}")

        # ── Tracking settings: click OFF, open ON, subscription OFF ──
        try:
            if _SgTrackingSettings is not None:
                _ts = _SgTrackingSettings()
                _ts.click_tracking = _SgClickTracking(False, False)
                _ts.open_tracking = _SgOpenTracking(True)
                _ts.subscription_tracking = _SgSubscriptionTracking(False)
                message.tracking_settings = _ts
        except Exception as _texc:  # noqa: BLE001
            logger.debug(f"[email-tracking] skipped: {_texc}")

        # ── Custom args (analytics / per-tenant attribution) ──
        if custom_args:
            try:
                from sendgrid.helpers.mail import CustomArg as _SgCustomArg
                for k, v in custom_args.items():
                    message.add_custom_arg(_SgCustomArg(str(k), str(v)))
            except Exception:
                pass

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
        
        logger.info(
            f"[EMAIL_DEBUG] Sending email to: {to_email} | Subject: {subject} | From: {_from} | Reply-To: {_reply_to}"
        )
        response = await asyncio.to_thread(sg.send, message)
        
        logger.info(f"[EMAIL_DEBUG] SendGrid response for {to_email}: status_code={response.status_code}")
        
        return {
            "status": "sent",
            "status_code": response.status_code,
            "to": to_email,
            "from": _from,
            "reply_to": _reply_to,
            "subject": subject,
            "is_marketing": is_marketing,
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
    reply_to_name: Optional[str] = None,
    is_marketing: bool = False,
    categories: Optional[List[str]] = None,
    custom_args: Optional[Dict[str, str]] = None,
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
    let callers stamp branded outbound headers (e.g. `contractor@bidvex.com`
    for B2B blasts, `service@bidvex.com` for transactional).

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
        reply_to_name=reply_to_name,
        is_marketing=is_marketing,
        categories=categories,
        custom_args=custom_args,
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
                        <!-- iter314 — BidVex logo (canonical, must appear first) -->
                        {BIDVEX_LOGO_BLOCK}
                        <!-- Section header -->
                        <tr>
                            <td style="background-color: {header_bg}; padding: 30px;">
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
                                <p style="margin: 0 0 8px; font-size: 12px; color: #64748b; text-align: center;">
                                    © 2026 BidVex Inc. All rights reserved.<br>
                                    <a href="{FRONTEND_URL}/privacy-policy" style="color: #2563eb;">Privacy Policy</a> | 
                                    <a href="{FRONTEND_URL}/terms-of-service" style="color: #2563eb;">Terms of Service</a>
                                </p>
                                <!-- iter366 — Visible unsubscribe link. The
                                     {{UNSUBSCRIBE_URL}} placeholder is filled
                                     with a signed one-click token in
                                     _send_via_unified(). If unsubscribe is
                                     unavailable (transactional-only send),
                                     the placeholder is stripped by the same
                                     step and the block hides itself. -->
                                <p style="margin: 6px 0 0; font-size: 11px; color: #94a3b8; text-align: center;">
                                    Don&apos;t want marketing emails?
                                    <a href="{{{{UNSUBSCRIBE_URL}}}}" style="color: #64748b; text-decoration: underline;">Unsubscribe</a>
                                    · Transactional emails (receipts, security, order updates) are always sent.
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


def _storage_panel(title_en: str, title_fr: str, body_en: str, body_fr: str, cta_url: str = "", cta_en: str = "", cta_fr: str = "") -> str:
    # Outlook-safe: strict table layout, inline CSS, solid colors (no
    # gradients / flex / grid / structural divs).
    cta_block = ""
    if cta_url and cta_en:
        cta_block = f"""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0">
          <tr><td align="center" style="padding:20px 0;">
            <a href="{cta_url}" style="background-color:#0F3060;color:#ffffff;text-decoration:none;font-weight:700;padding:12px 26px;border-radius:24px;display:inline-block;font-family:Arial,sans-serif;">
              {cta_en} / {cta_fr}
            </a>
          </td></tr>
        </table>
        """
    return f"""
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color:#ffffff;">
      <tr><td align="center" style="padding:24px;">
        <table role="presentation" width="640" cellpadding="0" cellspacing="0" border="0" style="max-width:640px;font-family:Arial,sans-serif;">
          <tr>
            <td bgcolor="#0B2545" style="background-color:#0B2545;color:#ffffff;padding:24px;border-radius:12px;">
              <p style="margin:0;font-size:11px;letter-spacing:2px;color:#9fb3c8;">🔒 BIDVEX STORAGE AUCTIONS</p>
              <h2 style="margin:6px 0 0 0;font-size:22px;color:#ffffff;">{title_en}</h2>
              <p style="margin:4px 0 0 0;font-size:14px;color:#3FB4CB;">{title_fr}</p>
            </td>
          </tr>
          <tr><td style="height:16px;line-height:16px;font-size:1px;">&nbsp;</td></tr>
          <tr>
            <td style="color:#1e293b;font-size:14px;line-height:1.55;">
              <p style="margin:0 0 12px 0;"><strong>EN:</strong> {body_en}</p>
              <hr style="border:none;border-top:1px solid #e5e7eb;margin:12px 0;"/>
              <p style="margin:12px 0 0 0;"><strong>FR:</strong> {body_fr}</p>
            </td>
          </tr>
          <tr><td>{cta_block}</td></tr>
          <tr>
            <td align="center" style="font-size:11px;color:#94a3b8;padding-top:24px;">BidVex Canada — bilingual auction marketplace</td>
          </tr>
        </table>
      </td></tr>
    </table>
    """

