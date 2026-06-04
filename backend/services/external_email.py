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
  • Reply-To:    support@bidvex.com
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

EXTERNAL_FROM_EMAIL = os.environ.get(
    "EXTERNAL_FROM_EMAIL", "noreply@bidvex.ca",
)
EXTERNAL_FROM_NAME = os.environ.get("EXTERNAL_FROM_NAME", "BidVex Canada")
EXTERNAL_REPLY_TO = os.environ.get("EXTERNAL_REPLY_TO", "support@bidvex.com")
EXTERNAL_REPLY_TO_NAME = os.environ.get(
    "EXTERNAL_REPLY_TO_NAME", "BidVex Support",
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
    caller's responsibility (done once before the batch starts)."""
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import (
            Mail, Email, To, Content,
            Attachment, FileContent, FileName, FileType, Disposition,
            Header, Category, CustomArg, ReplyTo,
            TrackingSettings, ClickTracking, OpenTracking, SubscriptionTracking,
        )
    except ImportError:
        logger.error("[external-email] SendGrid SDK not installed")
        return {"status": "error", "message": "sendgrid not installed"}

    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key or api_key == "SG.your-actual-sendgrid-key-here":
        logger.warning(f"[external-email] No SendGrid key — logging only {to_email}")
        return {"status": "logged", "to": to_email}

    # Unsubscribe link with per-recipient token.
    unsub_token = make_unsubscribe_token(to_email, campaign_id, language)
    unsub_url = f"{public_base_url}/api/external/unsubscribe?token={unsub_token}"

    # Inject the per-recipient unsubscribe URL into the {unsubscribe_url}
    # placeholder. If the admin forgot the placeholder, auto-append the
    # CASL footer so we never break compliance.
    if "{unsubscribe_url}" in body_html:
        rendered = body_html.replace("{unsubscribe_url}", unsub_url)
    else:
        rendered = body_html + "\n" + casl_footer_html(unsub_url)

    rendered = inject_utm_params(rendered, {
        "utm_source":   "email",
        "utm_medium":   "marketing",
        "utm_campaign": utm_campaign or campaign_id,
    })

    message = Mail(
        from_email=Email(EXTERNAL_FROM_EMAIL, EXTERNAL_FROM_NAME),
        to_emails=To(to_email, to_name or to_email),
        subject=subject,
        html_content=Content("text/html", rendered),
    )
    try:
        message.reply_to = ReplyTo(EXTERNAL_REPLY_TO, EXTERNAL_REPLY_TO_NAME)
    except Exception:
        message.reply_to = Email(EXTERNAL_REPLY_TO, EXTERNAL_REPLY_TO_NAME)

    # ── Required headers ──
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

    # ── Attachments ──
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

    try:
        sg = SendGridAPIClient(api_key)
        response = sg.send(message)
        return {
            "status":      "sent",
            "status_code": response.status_code,
            "to":          to_email,
            "campaign_id": campaign_id,
        }
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[external-email] send failed for {to_email}: {exc}")
        return {"status": "error", "to": to_email, "message": str(exc)}


__all__ = [
    "EXTERNAL_FROM_EMAIL", "EXTERNAL_FROM_NAME",
    "EXTERNAL_REPLY_TO", "EXTERNAL_REPLY_TO_NAME",
    "inject_utm_params", "casl_footer_html", "validate_casl",
    "make_unsubscribe_token", "decode_unsubscribe_token",
    "send_external_campaign_email",
]
