"""
iter317 Directive 3 — Contractor Email Hub (iter318 sender update).

Server-side outbound email pipeline for contractors. Enforces:
  • Sender FROM = info@bidvex.com    (hardcoded, never overridable)
  • Reply-To    = support@bidvex.com  (hardcoded, never overridable)
  • Mandatory BidVex signature block appended on every send
  • Canonical CDN logo URL (iter314 token) — NEVER the bidvex.com/assets path
  • Hardcoded support number +1 450 634 3099 — NOT a dynamic variable
  • Server appends signature even if contractor's body already contains
    one (idempotency token check).
  • Every send is logged to `contractor_emails` for the Sent list view.

Reuses suppression / activity-tracking pieces from emails._email_core.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ─── Hard-locked sender identity (Email Hub only) ───────────────────────
# iter318 — sender swapped from partners@bidvex.ca to info@bidvex.com so
# Email Hub messages benefit from the already-domain-authenticated
# bidvex.com DKIM/SPF setup. Reply-To pinned to support@bidvex.com
# per spec (NOT the contractor's email).

CONTRACTOR_SENDER_EMAIL = "info@bidvex.com"
CONTRACTOR_SENDER_NAME = "BidVex Canada"
CONTRACTOR_REPLY_TO = "support@bidvex.com"

# Aliases for new spec naming (so downstream callers can use either).
EMAIL_HUB_FROM_EMAIL = CONTRACTOR_SENDER_EMAIL
EMAIL_HUB_FROM_NAME = CONTRACTOR_SENDER_NAME
EMAIL_HUB_REPLY_TO = CONTRACTOR_REPLY_TO

# Canonical CDN logo URL from iter314 — DO NOT swap to bidvex.com/assets.
BIDVEX_CDN_LOGO_URL = (
    "http://cdn.mcauto-images-production.sendgrid.net/"
    "4fbf02710175d39f/91d027c2-73da-4510-9bce-ee1ce34f16a7/4500x1080.png"
)

# Hardcoded support number — NEVER a dynamic variable per Directive 3.
SUPPORT_PHONE = "+1 450 634 3099"
SUPPORT_PHONE_TEL = "+14506343099"

# Idempotency marker the injector looks for before appending again.
SIGNATURE_TOKEN = "bidvex-contractor-signature-v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ─── Signature builder ──────────────────────────────────────────────────

def build_contractor_signature(
    *,
    contractor_name: str,
    contractor_email: str,
    contractor_title: Optional[str] = None,
    locale: str = "en",
) -> str:
    """Returns the server-side signature HTML block.

    Locked attributes:
      • Logo = BIDVEX_CDN_LOGO_URL  (CDN, NOT bidvex.com/assets)
      • Support phone = SUPPORT_PHONE  (hardcoded, NOT a variable)
      • Sender / displayed email = info@bidvex.com (Email Hub spec)

    The block carries a hidden idempotency token so re-injection is a no-op.
    """
    fr = (locale or "en").startswith("fr")
    title_line = (contractor_title or ("Partenaire BidVex" if fr else "BidVex Partner"))
    support_label = "Soutien" if fr else "Support"
    rights = ("© BidVex Inc. Tous droits réservés."
              if fr else "© BidVex Inc. All rights reserved.")

    return f"""
<!-- {SIGNATURE_TOKEN} -->
<div style="margin-top:32px;padding-top:16px;border-top:1px solid #e2e8f0;
            font-family:Arial,sans-serif;color:#0b1a30;">
  <table cellpadding="0" cellspacing="0" border="0" role="presentation"
         style="border-collapse:collapse;">
    <tr>
      <td style="padding-right:18px;vertical-align:top;">
        <a href="https://bidvex.com" target="_blank" style="text-decoration:none;">
          <img src="{BIDVEX_CDN_LOGO_URL}"
               alt="BidVex" border="0" width="160"
               style="display:block;border:0;outline:none;text-decoration:none;
                      width:160px;height:auto;" />
        </a>
      </td>
      <td style="vertical-align:top;font-size:13px;line-height:1.5;color:#0b1a30;">
        <div style="font-weight:700;font-size:15px;">{contractor_name}</div>
        <div style="color:#475569;">{title_line}</div>
        <div style="margin-top:6px;">
          <a href="mailto:{CONTRACTOR_SENDER_EMAIL}"
             style="color:#0b1a30;text-decoration:none;">{CONTRACTOR_SENDER_EMAIL}</a>
        </div>
        <div>
          {support_label}:
          <a href="tel:{SUPPORT_PHONE_TEL}"
             style="color:#0b1a30;text-decoration:none;font-weight:600;">{SUPPORT_PHONE}</a>
        </div>
        <div style="margin-top:6px;">
          <a href="https://bidvex.com"
             style="color:#0b1a30;text-decoration:none;">bidvex.com</a>
        </div>
      </td>
    </tr>
  </table>
  <div style="margin-top:12px;font-size:11px;color:#64748b;">
    {rights}
  </div>
</div>
""".strip()


def inject_signature(html: str, signature_html: str) -> str:
    """Idempotently appends `signature_html` to `html`. If the signature
    token is already present, returns `html` unchanged."""
    if not html:
        return signature_html
    if SIGNATURE_TOKEN in html:
        return html
    # If the body ends in </body> or </html>, insert BEFORE the closing tag.
    lower = html.lower()
    for tag in ("</body>", "</html>"):
        idx = lower.rfind(tag)
        if idx != -1:
            return html[:idx] + signature_html + html[idx:]
    return html + signature_html


# ─── Public API used by the route handler ───────────────────────────────

async def send_contractor_email(
    db,
    *,
    contractor: Dict[str, Any],
    to_email: str,
    subject: str,
    body_html: str,
    locale: str = "en",
    client_account_id: Optional[str] = None,
    contractor_ip: Optional[str] = None,
    contractor_user_agent: Optional[str] = None,
) -> Dict[str, Any]:
    """Sends an outbound email on behalf of a contractor. Server-side
    signature injection + sender enforcement happens here — the route
    handler does NOT control any of these properties.

    Returns the persisted `contractor_emails` row (a dict)."""
    sig = build_contractor_signature(
        contractor_name=contractor.get("name")
            or f"{contractor.get('first_name','')} {contractor.get('last_name','')}".strip()
            or contractor.get("email", "BidVex Partner"),
        contractor_email=contractor.get("email") or CONTRACTOR_SENDER_EMAIL,
        locale=locale,
    )
    final_html = inject_signature(body_html or "", sig)

    sent_status = "sent"
    sg_message_id: Optional[str] = None
    sg_error: Optional[str] = None

    try:
        sg_message_id = await _sendgrid_dispatch(
            to_email=to_email,
            subject=subject,
            html_content=final_html,
            reply_to=CONTRACTOR_REPLY_TO,
            reply_to_name=CONTRACTOR_SENDER_NAME,
        )
    except Exception as exc:  # noqa: BLE001
        sent_status = "failed"
        sg_error = str(exc)[:300]
        logger.exception(f"[contractor-email] failed for {contractor.get('id')}: {exc}")

    row = {
        "id":                str(uuid.uuid4()),
        "contractor_id":     contractor.get("id"),
        "from_email":        CONTRACTOR_SENDER_EMAIL,
        "from_name":         CONTRACTOR_SENDER_NAME,
        "to_email":          to_email,
        "client_account_id": client_account_id,
        "subject":           subject,
        "body_html":         final_html,
        "locale":            locale,
        "status":            sent_status,
        "sendgrid_message_id": sg_message_id,
        "error":             sg_error,
        "ip_address":        contractor_ip,
        "user_agent":        contractor_user_agent,
        "sent_at":           _now_iso(),
    }
    await db.contractor_emails.insert_one(row)
    row.pop("_id", None)
    return row


# ─── SendGrid raw dispatcher (BYPASSES canonical send_email so we keep
#     the info@bidvex.com Email Hub FROM intact) ─────────────────────────

async def _sendgrid_dispatch(
    *,
    to_email: str,
    subject: str,
    html_content: str,
    reply_to: Optional[str],
    reply_to_name: Optional[str],
) -> Optional[str]:
    """Direct SendGrid call. We can't go through services.emails._email_core
    because that path forces FROM=noreply@bidvex.com. Email Hub messages
    MUST visibly originate from info@bidvex.com per Email Hub spec."""
    api_key = os.environ.get("SENDGRID_API_KEY")
    if not api_key:
        logger.info(f"[contractor-email] DRY-RUN to={to_email} subj={subject!r}")
        return None

    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content
        try:
            from sendgrid.helpers.mail import ReplyTo  # type: ignore
        except ImportError:
            ReplyTo = None  # type: ignore
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[contractor-email] sendgrid SDK unavailable: {e}")
        return None

    message = Mail(
        from_email=Email(CONTRACTOR_SENDER_EMAIL, CONTRACTOR_SENDER_NAME),
        to_emails=To(to_email),
        subject=subject,
        html_content=Content("text/html", html_content),
    )
    if reply_to:
        try:
            if ReplyTo is not None:
                message.reply_to = ReplyTo(reply_to, reply_to_name or CONTRACTOR_SENDER_NAME)
            else:
                message.reply_to = Email(reply_to, reply_to_name or CONTRACTOR_SENDER_NAME)
        except Exception:  # noqa: BLE001
            message.reply_to = Email(reply_to, reply_to_name or CONTRACTOR_SENDER_NAME)

    client = SendGridAPIClient(api_key)
    response = client.send(message)
    if 200 <= int(response.status_code) < 300:
        return (response.headers or {}).get("X-Message-Id")
    raise RuntimeError(f"sendgrid status={response.status_code} body={response.body}")


# ─── Validation helpers used by route handler ───────────────────────────

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_recipient_email(email: str) -> bool:
    if not email or len(email) > 254:
        return False
    return bool(EMAIL_RE.match(email.strip()))


__all__ = [
    "CONTRACTOR_SENDER_EMAIL",
    "CONTRACTOR_SENDER_NAME",
    "CONTRACTOR_REPLY_TO",
    "EMAIL_HUB_FROM_EMAIL",
    "EMAIL_HUB_FROM_NAME",
    "EMAIL_HUB_REPLY_TO",
    "BIDVEX_CDN_LOGO_URL",
    "SUPPORT_PHONE",
    "SIGNATURE_TOKEN",
    "build_contractor_signature",
    "inject_signature",
    "send_contractor_email",
    "validate_recipient_email",
]
