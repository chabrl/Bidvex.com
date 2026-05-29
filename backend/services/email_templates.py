"""
iter238 Mission 6 — Unified BidVex master email template.

This module is the single source of truth for ALL transactional emails.
New code paths MUST use `build_email_payload(email_type, user, data)`
+ `services.email_notifications.send_email(...)` with the returned payload.

Legacy call sites in `services/email_notifications.py` are routed through
this helper progressively as they get touched (a one-shot mass refactor was
deferred to keep the iter238 bundle shippable).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

# Locked corporate identity for the footer (matches iter232/iter237).
_CORP_ADDRESS = "761 Rue Chalifoux, Sherbrooke (Québec) J1G 0A8"
_SUPPORT_EMAIL = "support@bidvex.com"
_PUBLIC_URL = "https://bidvex.com"

BIDVEX_EMAIL_TEMPLATE = """<!DOCTYPE html>
<html lang="{lang}">
<head>
<meta charset="UTF-8">
<title>{email_subject} - BidVex</title>
<meta name="viewport" content="width=device-width, initial-scale=1.0">
</head>
<body style="font-family:Arial,sans-serif;margin:0;padding:0;background:#f4f6fb;">
<table width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:32px auto;background:#fff;border:1px solid #e0e0e0;border-radius:12px;overflow:hidden;box-shadow:0 2px 16px rgba(0,0,0,0.07);">
  <tr>
    <td style="padding:28px 24px;text-align:center;background:linear-gradient(135deg,#00CFFF,#0077FF);">
      <img src="http://cdn.mcauto-images-production.sendgrid.net/4fbf02710175d39f/31636d5f-c160-446b-b715-bcf542e9607e/4500x1080.png" alt="BidVex" width="130" style="margin:0 auto 14px;display:block;">
      <h2 style="color:#fff;margin:0;font-size:20px;font-weight:700;">{email_headline}</h2>
      <p style="color:rgba(255,255,255,0.85);margin:6px 0 0;font-size:13px;">{email_subheadline}</p>
    </td>
  </tr>
  <tr>
    <td style="padding:28px 24px;color:#333;">
      <p style="font-size:16px;margin:0 0 16px;">{greeting} {first_name},</p>
      <div style="font-size:15px;line-height:1.7;color:#444;">
        {body_html}
      </div>
      {cta_block}
      {secondary_block}
      <p style="margin-top:28px;font-size:14px;color:#555;">
        — {team_signature}<br>
        <span style="color:#999;font-size:12px;">{support_email}</span>
      </p>
    </td>
  </tr>
  <tr>
    <td style="padding:18px 24px;font-size:11px;color:#aaa;text-align:center;border-top:1px solid #f0f0f0;">
      © {current_year} BidVex Inc. — Federally incorporated in Canada<br>
      {corp_address}<br>
      <a href="{unsubscribe_url}" style="color:#aaa;text-decoration:underline;">Unsubscribe</a>
    </td>
  </tr>
</table>
</body>
</html>"""


def _t(lang: str, en: str, fr: str) -> str:
    return fr if (lang or "en").lower().startswith("fr") else en


# Locked dynamic-data table per spec.
_EMAIL_TYPES: Dict[str, Dict[str, Any]] = {
    "welcome": {
        "headline": "Welcome to BidVex! 🎉",
        "subheadline": "Your auction journey starts here.",
        "body_html": "Your account is ready. Explore thousands of listings across Canada.",
        "cta_label": "Explore Marketplace",
        "cta_url": f"{_PUBLIC_URL}/marketplace",
    },
    "bid_placed": {
        "headline": "Your Bid is Live! ⚡",
        "subheadline": "You're in the running.",
        "body_html": "You placed a bid of <strong>${bid_amount} CAD</strong> on <strong>{listing_title}</strong>. We'll notify you if you're outbid.",
        "cta_label": "View Listing",
        "cta_url": f"{_PUBLIC_URL}/listing/{{listing_id}}",
    },
    "outbid": {
        "headline": "You've Been Outbid 😮",
        "subheadline": "Don't give up — place a new bid!",
        "body_html": "Someone outbid you on <strong>{listing_title}</strong>. Current bid is now <strong>${current_bid} CAD</strong>.",
        "cta_label": "Bid Again",
        "cta_url": f"{_PUBLIC_URL}/listing/{{listing_id}}",
    },
    "auction_won": {
        "headline": "🏆 Congratulations — You Won!",
        "subheadline": "Your winning bid has been accepted.",
        "body_html": "You won <strong>{listing_title}</strong> with a final bid of <strong>${hammer_price} CAD</strong>. Please complete payment within 48 hours.",
        "cta_label": "Complete Payment",
        "cta_url": f"{_PUBLIC_URL}/checkout/{{order_id}}",
    },
    "auction_ending_soon": {
        "headline": "⏰ Auction Ending Soon!",
        "subheadline": "Less than 1 hour remaining.",
        "body_html": "<strong>{listing_title}</strong> closes in <strong>{time_remaining}</strong>. Current bid: ${current_bid} CAD.",
        "cta_label": "Bid Now",
        "cta_url": f"{_PUBLIC_URL}/listing/{{listing_id}}",
    },
    "voicemail": {
        "headline": "📞 New Voicemail Received",
        "subheadline": "Someone left you a message.",
        "body_html": "Caller: {caller_number}<br>Department: {department}<br>Language: {language}",
        "cta_label": "▶ Play Recording",
        "cta_url": "{recording_url}",
    },
    "ai_suggestion": {
        "headline": "💡 BidVex AI Has a Suggestion",
        "subheadline": "Based on your activity.",
        "body_html": "{ai_message}",
        "cta_label": "View Suggestion",
        "cta_url": "{listing_url}",
    },
    "new_feature": {
        "headline": "🚀 New Feature Available!",
        "subheadline": "{feature_name} is now live.",
        "body_html": "{feature_description}",
        "cta_label": "Explore Now",
        "cta_url": "{feature_url}",
    },
    "password_reset": {
        "headline": "Reset Your Password 🔐",
        "subheadline": "We received a reset request.",
        "body_html": "Click below to reset your password. This link expires in 1 hour.",
        "cta_label": "Reset Password",
        "cta_url": "{reset_url}",
    },
    "onboarding_reminder": {
        "headline": "Complete Your BidVex Profile 📍",
        "subheadline": "You're almost there!",
        "body_html": "Add your location to discover nearby auctions and get personalized recommendations.",
        "cta_label": "Complete Profile",
        "cta_url": f"{_PUBLIC_URL}/onboarding",
    },
}


def build_email_payload(
    email_type: str,
    user: Optional[Dict[str, Any]] = None,
    data: Optional[Dict[str, Any]] = None,
    *,
    lang: str = "en",
) -> Dict[str, Any]:
    """Return {'to_email', 'subject', 'html_content'} dict ready for
    `services.email_notifications.send_email(**payload)`.
    """
    user = user or {}
    data = data or {}
    spec = _EMAIL_TYPES.get(email_type)
    if not spec:
        raise ValueError(f"Unknown email_type {email_type!r}")

    # Personalisation
    first_name = (user.get("first_name") or user.get("name") or "there").strip()
    to_email = user.get("email") or data.get("to_email") or _SUPPORT_EMAIL

    # Format dynamic placeholders inside body / CTA URL.
    fmt = {**user, **data}
    try:
        body_html = spec["body_html"].format(**fmt)
    except (KeyError, IndexError):
        body_html = spec["body_html"]  # leave unformatted on missing keys
    try:
        cta_url = spec.get("cta_url", "").format(**fmt)
    except (KeyError, IndexError):
        cta_url = spec.get("cta_url", "")
    try:
        headline = spec["headline"].format(**fmt)
        subheadline = spec["subheadline"].format(**fmt)
    except (KeyError, IndexError):
        headline = spec["headline"]
        subheadline = spec["subheadline"]

    cta_block = (
        f'<p style="margin:28px 0 0;text-align:center;"><a href="{cta_url}" '
        f'style="display:inline-block;background:#0077FF;color:#fff;text-decoration:none;'
        f'padding:13px 28px;border-radius:7px;font-weight:700;font-size:15px;letter-spacing:0.3px;">'
        f'{spec["cta_label"]}</a></p>'
    ) if cta_url else ""

    secondary = data.get("secondary_info") or ""
    secondary_block = (
        f'<div style="margin-top:24px;padding:16px;background:#f4f6fb;border-radius:8px;'
        f'border-left:4px solid #0077FF;font-size:13px;color:#555;">{secondary}</div>'
    ) if secondary else ""

    html_content = BIDVEX_EMAIL_TEMPLATE.format(
        lang=lang,
        email_subject=headline,
        email_headline=headline,
        email_subheadline=subheadline,
        greeting=_t(lang, "Hello", "Bonjour"),
        first_name=first_name,
        body_html=body_html,
        cta_block=cta_block,
        secondary_block=secondary_block,
        team_signature=_t(lang, "The BidVex Team", "L'équipe BidVex"),
        support_email=_SUPPORT_EMAIL,
        current_year=datetime.now(timezone.utc).year,
        corp_address=_CORP_ADDRESS,
        unsubscribe_url=f"{_PUBLIC_URL}/account/email-preferences",
    )

    return {
        "to_email": to_email,
        "subject": headline.split(" - ")[0],
        "html_content": html_content,
    }


__all__ = ["BIDVEX_EMAIL_TEMPLATE", "build_email_payload"]
