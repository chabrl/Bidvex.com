"""
iter271 — External email campaign sender.

A dedicated outbound path for ACQUISITION marketing emails sent to
contacts who are NOT BidVex users yet. Lives parallel to (and is
deliberately isolated from) the platform marketing engine in
`services/email_notifications.py`.

Spec-locked rules:
  • FROM:        noreply@bidvex.ca  (acquisition domain)
                 — falls back to noreply@bidvex.com when .ca DNS
                   is not yet authenticated.
  • Reply-To:    service@bidvex.com
  • List-Unsubscribe + List-Unsubscribe-Post: One-Click
  • Precedence:  bulk
  • Click tracking OFF
  • Categories:  external_marketing + acquisition
  • Custom args: campaign_id + campaign_type=external  (webhook keys)
  • UTM params:  injected into every <a href> in the body
  • CASL footer: enforced upstream (`{unsubscribe_url}` must be in body)
"""
from __future__ import annotations

import base64
import hashlib
import logging
import os
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode, urlsplit, urlunsplit, parse_qsl

logger = logging.getLogger(__name__)

# ── Canonical envelope ───────────────────────────────────────────────
#
# iter271 spec target: `noreply@bidvex.ca`.
# iter272 reality:     the `.ca` domain is NOT yet DKIM-authenticated
#                      in SendGrid, so every live send returns 403 →
#                      campaign status flips to `failed` → no emails
#                      reach inboxes. We keep the `.ca` brand as the
#                      documented default but ALSO resolve a verified
#                      operational sender (defaults to the `.com`
#                      authenticated mailbox) and auto-fall back to
#                      it when SendGrid rejects the primary FROM.

EXTERNAL_FROM_EMAIL = os.environ.get(
    "EXTERNAL_FROM_EMAIL", "noreply@bidvex.ca",
)
EXTERNAL_FROM_NAME = os.environ.get("EXTERNAL_FROM_NAME", "BidVex Canada")
EXTERNAL_REPLY_TO = os.environ.get("EXTERNAL_REPLY_TO", "service@bidvex.com")
EXTERNAL_REPLY_TO_NAME = os.environ.get(
    "EXTERNAL_REPLY_TO_NAME", "BidVex Support",
)
# Operational fallback — the verified SendGrid mailbox that will always
# pass DKIM + SPF alignment. Resolved at import-time so all sends share
# the same authoritative value.
EXTERNAL_VERIFIED_FROM_EMAIL = (
    os.environ.get("EXTERNAL_VERIFIED_FROM_EMAIL")
    or os.environ.get("SENDGRID_FROM_EMAIL")
    or "noreply@bidvex.com"
)
EXTERNAL_VERIFIED_FROM_NAME = (
    os.environ.get("EXTERNAL_VERIFIED_FROM_NAME")
    or os.environ.get("SENDGRID_FROM_NAME")
    or "BidVex Canada"
)

# A 4xx response carrying any of these substrings indicates the SendGrid
# account does not yet trust the primary FROM address — we then retry
# once with the verified fallback sender so the campaign still ships.
_SENDER_AUTH_HINTS = (
    "verified sender",
    "sender identity",
    "domain authentication",
    "from address",
    "must be verified",
    "does not match a verified",
)


# ── UTM injection ────────────────────────────────────────────────────


_HREF_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE)


def inject_utm_params(html: str, utm: Dict[str, str]) -> str:
    """Append utm_* params to every absolute href in the HTML body.
    Relative URLs and mailto: / unsubscribe URLs are left untouched."""
    if not html or not utm:
        return html

    def _rewrite(match: "re.Match[str]") -> str:
        url = match.group(1)
        # Skip mailto:, anchor-only, and unsubscribe URLs.
        if url.startswith("mailto:") or url.startswith("#"):
            return match.group(0)
        if "unsubscribe" in url.lower():
            return match.group(0)
        try:
            parts = urlsplit(url)
        except Exception:
            return match.group(0)
        if not parts.scheme:
            return match.group(0)
        q = dict(parse_qsl(parts.query, keep_blank_values=True))
        for k, v in utm.items():
            q.setdefault(k, v)  # don't clobber existing UTMs
        new_url = urlunsplit(
            (parts.scheme, parts.netloc, parts.path, urlencode(q), parts.fragment),
        )
        return f'href="{new_url}"'

    return _HREF_RE.sub(_rewrite, html)


# ── CASL compliance helpers ──────────────────────────────────────────


def casl_footer_html(unsubscribe_url: str) -> str:
    """The mandated bilingual CASL footer block — used by previewer +
    auto-injected when the campaign body forgot it."""
    return f"""
<!-- CASL compliance footer -->
<table width="100%" style="margin-top:32px;border-top:1px solid #e2e8f0;">
  <tr>
    <td style="padding:20px;text-align:center;font-size:11px;color:#94a3b8;line-height:1.8;font-family:Arial,sans-serif;">
      <strong>BidVex Inc.</strong> | Sherbrooke, QC, Canada<br>
      You are receiving this email because your address was added to a BidVex marketing list.<br>
      <strong>Vous recevez cet email car votre adresse a été ajoutée à une liste marketing BidVex.</strong><br><br>
      <a href="{unsubscribe_url}" style="color:#2f80ff;font-weight:600;">
        Unsubscribe / Se désabonner
      </a>
      &nbsp;·&nbsp;
      <a href="https://bidvex.com/privacy-policy" style="color:#94a3b8;">
        Privacy Policy / Politique de confidentialité
      </a><br><br>
      © 2026 BidVex Inc. All rights reserved. / Tous droits réservés.
    </td>
  </tr>
</table>
""".strip()


# iter314 — Mandatory BidVex header for external (admin-authored) campaigns.
# The send pipeline below wraps the admin's raw HTML body inside this
# shell server-side, so admins never need to remember to paste a logo
# block into the campaign editor. Idempotent: if the body already
# contains the canonical logo URL the wrap is skipped.
_BIDVEX_LOGO_URL = (
    "http://cdn.mcauto-images-production.sendgrid.net/"
    "4fbf02710175d39f/91d027c2-73da-4510-9bce-ee1ce34f16a7/4500x1080.png"
)
_BIDVEX_LOGO_ID_TOKEN = "/91d027c2-73da-4510-9bce-ee1ce34f16a7/"
_BIDVEX_LEGACY_LOGO_TOKEN = "31636d5f-c160-446b-b715-bcf542e9607e"


def wrap_external_campaign_body(body_html: str, unsubscribe_url: str) -> str:
    """iter314 — Wrap admin-authored campaign HTML inside the standard
    BidVex header (logo) + footer (CASL unsubscribe).

    Behaviour:
      • If `body_html` already contains the canonical BidVex logo URL
        OR the legacy logo URL, we skip the header wrap (no duplicates)
        but still ensure the CASL footer is present.
      • Otherwise we build a complete Outlook-safe email document with
        the logo row first, the admin body inside a `<td>` cell, and
        the CASL footer below.
    """
    has_logo = (
        _BIDVEX_LOGO_ID_TOKEN in (body_html or "")
        or _BIDVEX_LEGACY_LOGO_TOKEN in (body_html or "")
    )
    has_footer = (
        "{unsubscribe_url}" in (body_html or "")
        or "unsubscribe" in (body_html or "").lower()
    )

    if has_logo:
        # Admin (or a previous wrap pass) already injected the logo.
        # Just guarantee the CASL footer is present.
        if has_footer:
            return body_html or ""
        return (body_html or "") + "\n" + casl_footer_html(unsubscribe_url)

    footer_block = casl_footer_html(unsubscribe_url) if not has_footer else ""

    return (
        '<!DOCTYPE html>'
        '<html><head>'
        '<meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        '</head>'
        '<body style="margin:0;padding:0;background-color:#f1f5f9;font-family:Arial,sans-serif;">'
        '<table width="100%" cellpadding="0" cellspacing="0" border="0" '
        'style="background-color:#f1f5f9;padding:32px 16px;">'
        '<tr><td align="center">'
        '<table width="600" cellpadding="0" cellspacing="0" border="0" '
        'style="background-color:#ffffff;border-radius:12px;overflow:hidden;max-width:600px;">'
        # iter314 — Canonical BidVex logo row.
        '<tr>'
        '<td style="background-color: #0b1a30; padding: 25px 40px; text-align: left;">'
        '<a href="https://bidvex.com" target="_blank" style="text-decoration: none;">'
        f'<img src="{_BIDVEX_LOGO_URL}" alt="BidVex" border="0" '
        'style="display: block; height: 32px; max-height: 32px; width: auto;">'
        '</a>'
        '</td>'
        '</tr>'
        # Admin-authored body slotted in.
        '<tr><td style="padding:32px 40px;color:#0f172a;font-size:15px;line-height:1.6;">'
        f'{body_html or ""}'
        '</td></tr>'
        # CASL footer (only if admin omitted it).
        f'{footer_block}'
        '</table>'
        '</td></tr>'
        '</table>'
        '</body></html>'
    )


def validate_casl(subject: str, body_html: str) -> Optional[str]:
    """Return an error string if the campaign fails CASL — otherwise None."""
    if not subject or not subject.strip():
        return "Email subject must not be empty"
    if not body_html or not body_html.strip():
        return "Email body must not be empty"
    if "{unsubscribe_url}" not in body_html and "unsubscribe" not in body_html.lower():
        return "Email body must contain {unsubscribe_url} for CASL compliance"
    return None


# ── Unsubscribe token ────────────────────────────────────────────────


def make_unsubscribe_token(email: str, campaign_id: str, lang: str = "en") -> str:
    """Sign a tiny JWT bearing the email + campaign_id so the public
    /external/unsubscribe endpoint can decode it without a DB lookup."""
    import jwt
    secret = os.environ.get("JWT_SECRET", "")
    payload = {
        "email": (email or "").strip().lower(),
        "campaign_id": campaign_id,
        "lang": (lang or "en")[:2],
        "type": "external_unsub",
        "iat": int(datetime.now(timezone.utc).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_unsubscribe_token(token: str) -> Dict[str, Any]:
    import jwt
    secret = os.environ.get("JWT_SECRET", "")
    return jwt.decode(token, secret, algorithms=["HS256"])


# ── Send helper ──────────────────────────────────────────────────────


def _looks_like_sender_auth_error(message: str) -> bool:
    """Heuristic match for SendGrid responses indicating the FROM mailbox
    is not yet authenticated in this account. We use this to decide
    whether retrying with the verified fallback sender is worthwhile."""
    if not message:
        return False
    haystack = message.lower()
    return any(hint in haystack for hint in _SENDER_AUTH_HINTS)


def _build_mail_message(
    *,
    from_email: str,
    from_name: str,
    to_email: str,
    to_name: str,
    subject: str,
    rendered: str,
    unsub_url: str,
    campaign_id: str,
    attachments: Optional[List[Dict[str, Any]]],
):
    """Construct the full SendGrid Mail() with every header/category/
    tracking setting we ship across all external-campaign sends. Isolated
    so we can rebuild it cleanly when the first send is rejected and we
    need to retry with the verified fallback FROM address."""
    from sendgrid.helpers.mail import (
        Mail, Email, To, Content,
        Attachment, FileContent, FileName, FileType, Disposition,
        Header, Category, CustomArg, ReplyTo,
        TrackingSettings, ClickTracking, OpenTracking, SubscriptionTracking,
    )

    message = Mail(
        from_email=Email(from_email, from_name),
        to_emails=To(to_email, to_name or to_email),
        subject=subject,
        html_content=Content("text/html", rendered),
    )
    try:
        message.reply_to = ReplyTo(EXTERNAL_REPLY_TO, EXTERNAL_REPLY_TO_NAME)
    except Exception:
        message.reply_to = Email(EXTERNAL_REPLY_TO, EXTERNAL_REPLY_TO_NAME)

    # ── Required spam-classification headers ──
    try:
        message.add_header(Header(
            "List-Unsubscribe",
            f"<{unsub_url}>, <mailto:unsubscribe@bidvex.com?subject=unsubscribe>",
        ))
        message.add_header(Header("List-Unsubscribe-Post", "List-Unsubscribe=One-Click"))
        message.add_header(Header("Precedence", "bulk"))
        message.add_header(Header("X-Mailer", "BidVex External Marketing v1.0"))
        entity_id = hashlib.sha256(
            f"{to_email}|{subject}|{datetime.now(timezone.utc).date().isoformat()}".encode()
        ).hexdigest()[:32]
        message.add_header(Header("X-Entity-Ref-ID", entity_id))
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"[external-email] header attach skipped: {exc}")

    # ── Categories + custom args (webhook routing keys) ──
    try:
        message.add_category(Category("external_marketing"))
        message.add_category(Category("acquisition"))
        message.add_custom_arg(CustomArg("campaign_id", str(campaign_id)))
        message.add_custom_arg(CustomArg("campaign_type", "external"))
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"[external-email] category/custom-arg skipped: {exc}")

    # ── Tracking settings ──
    try:
        ts = TrackingSettings()
        ts.click_tracking = ClickTracking(False, False)
        ts.open_tracking = OpenTracking(True)
        ts.subscription_tracking = SubscriptionTracking(False)
        message.tracking_settings = ts
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"[external-email] tracking attach skipped: {exc}")

    # ── Attachments (base64-encoded, MIME validated upstream) ──
    for att in (attachments or []):
        fpath = att.get("file_path")
        if not fpath or not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, "rb") as fh:
                encoded = base64.b64encode(fh.read()).decode("utf-8")
            message.add_attachment(Attachment(
                FileContent(encoded),
                FileName(att.get("original_filename") or os.path.basename(fpath)),
                FileType(att.get("mime_type") or "application/octet-stream"),
                Disposition("attachment"),
            ))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[external-email] attachment skipped {fpath}: {exc}")

    return message


async def send_external_campaign_email(
    *,
    to_email: str,
    to_name: str,
    subject: str,
    body_html: str,
    campaign_id: str,
    utm_campaign: str,
    attachments: Optional[List[Dict[str, Any]]] = None,
    language: str = "en",
    public_base_url: str = "https://bidvex.com",
) -> Dict[str, Any]:
    """Send a single external campaign email through SendGrid.

    Returns a result dict — never raises. Suppression checks are the
    caller's responsibility (done once before the batch starts).

    iter272 — On a primary-sender auth failure (e.g. `noreply@bidvex.ca`
    not yet DKIM-authenticated), we transparently retry once with the
    verified fallback FROM address so the campaign still ships and the
    overall status no longer flips to `failed`. The result envelope
    surfaces `from_email_used` + `fallback_used=True` for analytics.
    """
    try:
        from sendgrid import SendGridAPIClient
    except ImportError:
        logger.error("[external-email] SendGrid SDK not installed")
        return {"status": "error", "message": "sendgrid not installed"}

    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key or api_key == "SG.your-actual-sendgrid-key-here":
        logger.warning(f"[external-email] No SendGrid key — logging only {to_email}")
        return {
            "status":          "logged",
            "to":              to_email,
            "from_email_used": EXTERNAL_FROM_EMAIL,
            "fallback_used":   False,
        }

    # Unsubscribe link with per-recipient token.
    # iter309 D4 — Canonical frontend URL format:
    #   https://bidvex.com/unsubscribe?token=<jwt>&lang=<en|fr>
    # The frontend /unsubscribe page calls the unified /api/unsubscribe/auto-*
    # endpoints which decode both platform itsdangerous AND external JWT tokens.
    unsub_token = make_unsubscribe_token(to_email, campaign_id, language)
    public_base = (public_base_url or "https://bidvex.com").rstrip("/")
    lang_tag = (language or "en")[:2].lower()
    if lang_tag not in ("en", "fr"):
        lang_tag = "en"
    unsub_url = f"{public_base}/unsubscribe?token={unsub_token}&lang={lang_tag}"

    # Inject the per-recipient unsubscribe URL into the {unsubscribe_url}
    # placeholder. If the admin forgot the placeholder, the wrapper
    # below will inject a CASL footer automatically.
    rendered = (body_html or "").replace("{unsubscribe_url}", unsub_url)

    # iter314 — Server-side BidVex header (logo) + CASL footer wrap.
    # This guarantees every external campaign email carries the canonical
    # BidVex logo at the top, regardless of what the admin pasted into
    # the campaign editor. Idempotent: if the admin already included
    # the canonical logo URL, the wrap step skips the header.
    rendered = wrap_external_campaign_body(rendered, unsub_url)

    rendered = inject_utm_params(rendered, {
        "utm_source":   "email",
        "utm_medium":   "marketing",
        "utm_campaign": utm_campaign or campaign_id,
    })

    # Primary attempt with the documented acquisition sender.
    sg = SendGridAPIClient(api_key)
    primary_message = _build_mail_message(
        from_email=EXTERNAL_FROM_EMAIL,
        from_name=EXTERNAL_FROM_NAME,
        to_email=to_email, to_name=to_name,
        subject=subject, rendered=rendered, unsub_url=unsub_url,
        campaign_id=campaign_id, attachments=attachments,
    )
    try:
        response = sg.send(primary_message)
        return {
            "status":          "sent",
            "status_code":     response.status_code,
            "to":              to_email,
            "campaign_id":     campaign_id,
            "from_email_used": EXTERNAL_FROM_EMAIL,
            "fallback_used":   False,
        }
    except Exception as exc:  # noqa: BLE001
        primary_err = str(exc)
        # Try to pull the SendGrid HTTPError body for a clearer signal.
        body_text = primary_err
        try:
            raw = getattr(exc, "body", None)
            if raw:
                body_text = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else str(raw)
        except Exception:
            pass

        retry_with_fallback = (
            _looks_like_sender_auth_error(body_text)
            and EXTERNAL_VERIFIED_FROM_EMAIL
            and EXTERNAL_VERIFIED_FROM_EMAIL.lower() != EXTERNAL_FROM_EMAIL.lower()
        )
        if not retry_with_fallback:
            logger.error(
                f"[external-email] send failed for {to_email} from "
                f"{EXTERNAL_FROM_EMAIL}: {primary_err} | body={body_text[:240]}"
            )
            return {
                "status":          "error",
                "to":              to_email,
                "message":         primary_err,
                "from_email_used": EXTERNAL_FROM_EMAIL,
                "fallback_used":   False,
            }

        logger.warning(
            f"[external-email] primary FROM {EXTERNAL_FROM_EMAIL} rejected "
            f"({body_text[:160]}). Retrying with verified sender "
            f"{EXTERNAL_VERIFIED_FROM_EMAIL}."
        )
        fallback_message = _build_mail_message(
            from_email=EXTERNAL_VERIFIED_FROM_EMAIL,
            from_name=EXTERNAL_VERIFIED_FROM_NAME,
            to_email=to_email, to_name=to_name,
            subject=subject, rendered=rendered, unsub_url=unsub_url,
            campaign_id=campaign_id, attachments=attachments,
        )
        try:
            response = sg.send(fallback_message)
            return {
                "status":          "sent",
                "status_code":     response.status_code,
                "to":              to_email,
                "campaign_id":     campaign_id,
                "from_email_used": EXTERNAL_VERIFIED_FROM_EMAIL,
                "fallback_used":   True,
            }
        except Exception as exc2:  # noqa: BLE001
            logger.error(
                f"[external-email] fallback send ALSO failed for {to_email} "
                f"from {EXTERNAL_VERIFIED_FROM_EMAIL}: {exc2}"
            )
            return {
                "status":          "error",
                "to":              to_email,
                "message":         f"primary: {primary_err} | fallback: {exc2}",
                "from_email_used": EXTERNAL_VERIFIED_FROM_EMAIL,
                "fallback_used":   True,
            }


__all__ = [
    "EXTERNAL_FROM_EMAIL", "EXTERNAL_FROM_NAME",
    "EXTERNAL_REPLY_TO", "EXTERNAL_REPLY_TO_NAME",
    "EXTERNAL_VERIFIED_FROM_EMAIL", "EXTERNAL_VERIFIED_FROM_NAME",
    "inject_utm_params", "casl_footer_html", "validate_casl",
    "make_unsubscribe_token", "decode_unsubscribe_token",
    "send_external_campaign_email",
    "_looks_like_sender_auth_error",
]
