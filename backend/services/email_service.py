"""
BidVex — SendGrid Dynamic Template Email Service
Production architecture: All emails route through send_template_email().
Language routing: user.language_preference ("en" or "fr") determines template ID.
"""

import os
import logging
import asyncio
from typing import Dict, Optional, Any
from datetime import datetime
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To
from python_http_client.exceptions import HTTPError

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# TEMPLATE ID REGISTRY — Loaded from environment variables
# Format: SENDGRID_TEMPLATE_{NAME}_{EN|FR}=d-xxxxx
# ═══════════════════════════════════════════════════════════════

_TEMPLATE_KEYS = [
    "password_reset", "password_changed", "email_verification",
    "two_factor_code", "new_login_alert",
    "account_suspended", "report_received",
    "announcement", "support_acknowledgment", "platform_update",
    "payment_receipt", "payout_sent", "invoice_created", "invoice_overdue",
    "new_bid_notification", "listing_approved", "listing_rejected",
    "auction_announcement", "auction_reminder", "auction_results",
    "outbid_notification", "bid_confirmed", "winning_bid",
    "affiliate_summary", "new_referral", "commission_earned", "monthly_earnings",
    "welcome", "onboarding_day3", "onboarding_week1", "subscription_pitch",
    "reengagement", "reengagement_final", "subscription_final_reminder",
    "reactivation_offer",
    "new_auction_near_you", "ending_soon_near_you",
    "auction_ending_soon", "cross_border_purchase_notice",
    "pickup_code", "escrow_released", "cancellation_penalty", "auto_release",
    "sticky_card_locked",
]

TEMPLATE_IDS = {}
_missing_ids = []
for _k in _TEMPLATE_KEYS:
    en_val = os.environ.get(f"SENDGRID_TEMPLATE_{_k.upper()}_EN", "")
    fr_val = os.environ.get(f"SENDGRID_TEMPLATE_{_k.upper()}_FR", "")
    TEMPLATE_IDS[_k] = {"en": en_val, "fr": fr_val}
    if not en_val:
        _missing_ids.append(f"SENDGRID_TEMPLATE_{_k.upper()}_EN")
    if not fr_val:
        _missing_ids.append(f"SENDGRID_TEMPLATE_{_k.upper()}_FR")

if _missing_ids:
    logger.warning(f"[EMAIL] Missing {len(_missing_ids)} SendGrid template env vars: {', '.join(_missing_ids[:10])}{'...' if len(_missing_ids) > 10 else ''}")


# ═══════════════════════════════════════════════════════════════
# CORE SEND FUNCTION
# ═══════════════════════════════════════════════════════════════

_sg_client = None


def _get_sg():
    global _sg_client
    if _sg_client is None:
        api_key = os.environ.get("SENDGRID_API_KEY")
        if not api_key:
            logger.error("[EMAIL] SENDGRID_API_KEY not set")
            return None
        _sg_client = SendGridAPIClient(api_key)
    return _sg_client


async def send_template_email(
    to_email: str,
    to_name: str,
    template_id: str,
    dynamic_data: dict,
    max_retries: int = 3,
) -> bool:
    """
    Send email via SendGrid Dynamic Template.
    Retry logic: 3 attempts, exponential backoff.
    Logs template_id, recipient, success/failure.
    """
    sg = _get_sg()
    if not sg:
        logger.warning(f"[EMAIL] SendGrid not configured — skipping email to {to_email}")
        return False

    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "noreply@bidvex.com")
    from_name = os.environ.get("SENDGRID_FROM_NAME", "BidVex Canada")

    # Ensure current_year is always present
    dynamic_data.setdefault("current_year", datetime.now().year)

    message = Mail(
        from_email=Email(from_email, from_name),
        to_emails=To(to_email, to_name),
    )
    message.reply_to = Email("support@bidvex.com", "BidVex Support")
    message.template_id = template_id
    message.dynamic_template_data = dynamic_data

    for attempt in range(max_retries):
        try:
            response = sg.send(message)
            logger.info(
                f"[EMAIL] Sent: to={to_email} template={template_id} "
                f"status={response.status_code} msgid={response.headers.get('X-Message-Id', '?')}"
            )
            return True
        except HTTPError as e:
            error_body = e.body if hasattr(e, "body") else str(e)
            logger.error(f"[EMAIL] HTTPError (attempt {attempt+1}/{max_retries}): to={to_email} err={error_body}")
            if attempt == max_retries - 1:
                return False
            await asyncio.sleep(2 ** attempt)
        except Exception as e:
            logger.exception(f"[EMAIL] Unexpected error: to={to_email} err={e}")
            return False

    return False


def resolve_template(name: str, lang: str) -> str:
    """Look up template ID by name and language. Falls back to EN."""
    entry = TEMPLATE_IDS.get(name)
    if not entry:
        logger.error(f"[EMAIL] Unknown template name: {name}")
        return ""
    lang_key = "fr" if lang and lang.startswith("fr") else "en"
    return entry.get(lang_key, entry.get("en", ""))


# ═══════════════════════════════════════════════════════════════
# TYPED EMAIL FUNCTIONS — Each matches a trigger in the platform
# ═══════════════════════════════════════════════════════════════

async def send_welcome_email(user: dict) -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("welcome", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={"first_name": user.get("name", "").split()[0] if user.get("name") else ""},
    )


async def send_password_reset_email(user: dict, reset_url: str) -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("password_reset", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={"first_name": user.get("name", "").split()[0] if user.get("name") else "", "reset_url": reset_url},
    )


async def send_password_changed_email(user: dict) -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("password_changed", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={"first_name": user.get("name", "").split()[0] if user.get("name") else ""},
    )


async def send_email_verification_email(user: dict, verification_url: str) -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("email_verification", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={"first_name": user.get("name", "").split()[0] if user.get("name") else "", "verification_url": verification_url},
    )


async def send_bid_confirmed_email(user: dict, auction_id: str, auction_title: str, bid_amount: float) -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("bid_confirmed", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "auction_id": auction_id,
            "auction_title": auction_title,
            "bid_amount": f"${bid_amount:,.2f}",
            "auction_url": f"https://bidvex.com/listing/{auction_id}",
        },
    )


async def send_outbid_notification_email(user: dict, auction_id: str, auction_title: str, current_highest_bid: float) -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("outbid_notification", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "auction_id": auction_id,
            "auction_title": auction_title,
            "current_highest_bid": f"${current_highest_bid:,.2f}",
            "auction_url": f"https://bidvex.com/listing/{auction_id}",
        },
    )


async def send_winning_bid_email(user: dict, auction_id: str, auction_title: str, bid_amount: float) -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("winning_bid", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "auction_id": auction_id,
            "auction_title": auction_title,
            "bid_amount": f"${bid_amount:,.2f}",
            "auction_url": f"https://bidvex.com/listing/{auction_id}",
        },
    )


async def send_new_bid_notification_email(user: dict, auction_id: str, auction_title: str, bid_amount: float, bidder_name: str) -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("new_bid_notification", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "auction_id": auction_id,
            "auction_title": auction_title,
            "bid_amount": f"${bid_amount:,.2f}",
            "bidder_name": bidder_name,
            "auction_url": f"https://bidvex.com/listing/{auction_id}",
        },
    )


async def send_payment_receipt_email(user: dict, amount: float, transaction_id: str, invoice_id: str = "") -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("payment_receipt", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "amount": f"${amount:,.2f}",
            "transaction_id": transaction_id,
            "invoice_id": invoice_id,
        },
    )


async def send_listing_approved_email(user: dict, auction_id: str, auction_title: str) -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("listing_approved", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "auction_id": auction_id,
            "auction_title": auction_title,
            "auction_url": f"https://bidvex.com/listing/{auction_id}",
        },
    )


async def send_listing_rejected_email(user: dict, auction_id: str, auction_title: str, reason: str = "") -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("listing_rejected", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "auction_id": auction_id,
            "auction_title": auction_title,
            "reason": reason,
        },
    )


async def send_subscription_reminder_email(user: dict, plan_name: str, expiry_date: str, renewal_price: str) -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("subscription_final_reminder", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "plan_name": plan_name,
            "expiry_date": expiry_date,
            "renewal_price": renewal_price,
        },
    )


async def send_affiliate_summary_email(user: dict, total_earnings: str, payout_date: str) -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("affiliate_summary", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "total_earnings": total_earnings,
            "payout_date": payout_date,
        },
    )


async def send_new_referral_email(user: dict, referral_name: str, commission_amount: str) -> bool:
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("new_referral", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "referral_name": referral_name,
            "commission_amount": commission_amount,
        },
    )


async def send_geo_auction_alert(user: dict, auction: dict, distance_km: float, alert_type: str = "new") -> bool:
    """Send geo-targeted auction alert. alert_type: 'new' or 'ending_soon'."""
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    template_name = "new_auction_near_you" if alert_type == "new" else "ending_soon_near_you"
    tid = resolve_template(template_name, lang)
    data = {
        "first_name": user.get("name", "").split()[0] if user.get("name") else "",
        "auction_title": auction.get("title", ""),
        "auction_id": auction.get("id", ""),
        "city": auction.get("city", auction.get("location", "")),
        "distance_km": str(round(distance_km)),
    }
    if alert_type == "new":
        data["start_price"] = f"${auction.get('starting_price', 0):,.2f}"
        data["auction_end_time"] = auction.get("end_time", "")
    else:
        data["current_highest_bid"] = f"${auction.get('current_price', 0):,.2f}"
        data["hours_remaining"] = str(auction.get("hours_remaining", "?"))
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data=data,
    )


async def send_auction_ending_soon_email(user: dict, auction_id: str, item_name: str,
                                         current_highest_bid: float, user_last_bid: float,
                                         time_remaining: str) -> bool:
    """
    Trigger: 1 hour before auction end.
    Sent to all users who placed a bid OR watched/saved the auction.
    """
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("auction_ending_soon", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "user_name": user.get("name", ""),
            "auction_id": auction_id,
            "item_name": item_name,
            "current_highest_bid": f"${current_highest_bid:,.2f}",
            "user_last_bid": f"${user_last_bid:,.2f}",
            "time_remaining": time_remaining,
            "auction_url": f"https://bidvex.com/listing/{auction_id}",
        },
    )


async def send_cross_border_purchase_notice_email(user: dict, auction_id: str, item_name: str,
                                                    hammer_price: float) -> bool:
    """
    Trigger: Fires immediately when a winning bid is confirmed AND listing.is_cross_border == true.
    Contains full CBSA/RIV/CFIA/CBP/SAAQ/RDPRM compliance checklist.
    """
    lang = user.get("preferred_language", user.get("language_preference", "en"))
    tid = resolve_template("cross_border_purchase_notice", lang)
    return await send_template_email(
        to_email=user["email"],
        to_name=user.get("name", ""),
        template_id=tid,
        dynamic_data={
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "user_name": user.get("name", ""),
            "auction_id": auction_id,
            "item_name": item_name,
            "hammer_price": f"${hammer_price:,.2f}",
            "auction_url": f"https://bidvex.com/listing/{auction_id}",
        },
    )


# ═══════════════════════════════════════════════════════════════
# P0 TRANSACTIONAL EMAILS — Inline HTML with SendGrid fallback
# Uses SendGrid dynamic templates when configured, else inline HTML
# ═══════════════════════════════════════════════════════════════

LOGO_URL = "http://cdn.mcauto-images-production.sendgrid.net/4fbf02710175d39f/9dc6a7c3-8237-4a66-b82b-0d9abc165b44/4500x1080.png"
DASHBOARD_URL = "https://bidvex.com/buyer/dashboard"
SUPPORT_URL = "https://bidvex.com/policies"


def _p0_wrap(hero_color: str, emoji: str, headline: str, body_html: str, lang: str = "en") -> str:
    """BidVex design-system email wrapper: header, hero, body card, footer."""
    yr = datetime.now().year
    footer_line = "Tous droits réservés" if lang == "fr" else "All rights reserved"
    return f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
<meta name="color-scheme" content="light dark">
<meta name="supported-color-schemes" content="light dark">
<style>
@media (prefers-color-scheme:dark){{
  .email-body{{background-color:#1E293B!important}}
  .email-card{{background-color:#0F172A!important}}
  .email-text{{color:#E2E8F0!important}}
  .email-subtext{{color:#94A3B8!important}}
  .data-card{{background-color:#1E3A5F!important;border-color:#3FB4CB!important}}
}}
@media (max-width:600px){{
  .email-wrapper{{width:100%!important}}
  .email-card{{padding:20px 16px!important}}
  .pickup-code{{font-size:36px!important;letter-spacing:4px!important}}
  h1{{font-size:20px!important}}
  .cta-button{{padding:12px 24px!important;font-size:14px!important}}
}}
</style>
</head>
<body class="email-body" style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Arial,sans-serif;background-color:#f1f5f9;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#f1f5f9;padding:32px 16px;">
<tr><td align="center">
<table class="email-wrapper" width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;">
<!-- Header -->
<tr><td style="background-color:#0B2545;text-align:center;padding:24px 40px 20px 40px;">
<img src="{LOGO_URL}" width="150" alt="BidVex" style="display:block;margin:0 auto;">
</td></tr>
<tr><td style="background-color:#3FB4CB;height:3px;font-size:0;line-height:0;">&nbsp;</td></tr>
<!-- Hero -->
<tr><td style="background-color:{hero_color};text-align:center;padding:32px 40px;">
<div style="font-size:48px;margin-bottom:12px;">{emoji}</div>
<h1 style="font-size:24px;font-weight:700;color:#FFFFFF;margin:0;">{headline}</h1>
</td></tr>
<!-- Body -->
<tr><td class="email-card" style="background-color:#FFFFFF;border-radius:0 0 10px 10px;box-shadow:0 4px 20px rgba(0,0,0,0.08);padding:32px 40px;">
{body_html}
</td></tr>
<!-- Footer -->
<tr><td style="background-color:#0B2545;text-align:center;padding:24px 40px;border-radius:0 0 10px 10px;margin-top:8px;">
<img src="{LOGO_URL}" width="80" style="opacity:0.7;margin-bottom:12px;">
<p style="color:#94A3B8;font-size:12px;margin:4px 0;">BidVex Canada | Sherbrooke, QC</p>
<p style="color:#94A3B8;font-size:12px;margin:4px 0;">support@bidvex.com | bidvex.com</p>
<p style="color:#94A3B8;font-size:11px;margin:12px 0 0 0;">&copy; {yr} BidVex Canada. {footer_line}.</p>
</td></tr>
</table>
</td></tr></table>
</body></html>"""


async def _send_p0_email(to_email: str, to_name: str, template_name: str,
                         lang: str, subject: str, html_fallback: str,
                         dynamic_data: dict) -> bool:
    """Try SendGrid dynamic template first; fall back to inline HTML."""
    tid = resolve_template(template_name, lang)
    if tid:
        return await send_template_email(to_email, to_name, tid, dynamic_data)
    # Fallback: send inline HTML via raw SendGrid
    sg = _get_sg()
    if not sg:
        logger.warning(f"[EMAIL] No SendGrid — skipping {template_name} to {to_email}")
        return False
    try:
        from sendgrid.helpers.mail import Mail as SgMail, Email as SgEmail, To as SgTo, Content as SgContent
        msg = SgMail(
            from_email=SgEmail(os.environ.get("SENDGRID_FROM_EMAIL", "info@bidvex.com"), "BidVex"),
            to_emails=SgTo(to_email, to_name),
            subject=subject,
            html_content=SgContent("text/html", html_fallback),
        )
        response = sg.send(msg)
        logger.info(f"[EMAIL] Inline {template_name} sent to {to_email} status={response.status_code}")
        return response.status_code in (200, 201, 202)
    except Exception as e:
        logger.error(f"[EMAIL] Failed inline {template_name} to {to_email}: {e}")
        return False


# ── 1. PICKUP CODE EMAIL (Buyer) ──────────────────────────────

async def send_pickup_code_email(buyer: dict, seller: dict, pickup_code: str,
                                 auction_id: str, expires_at: str) -> bool:
    lang = buyer.get("language_preference", buyer.get("preferred_language", "en"))
    lang = "fr" if lang and lang.startswith("fr") else "en"
    first = (buyer.get("first_name") or buyer.get("full_name", buyer.get("name", ""))).split()[0] if buyer.get("first_name") or buyer.get("full_name") or buyer.get("name") else "Buyer"
    seller_name = seller.get("full_name", seller.get("name", "Seller"))

    if lang == "fr":
        subject = f"Votre code de retrait : {pickup_code}"
        headline = "Votre code de retrait"
        intro = f"<p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Bonjour {first},</p><p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Vos fonds sont en séquestre. Présentez ce code au vendeur <strong>{seller_name}</strong> lors du retrait de votre article.</p>"
        code_caption = "Présentez ce code au vendeur lors du retrait. Valide 48 heures."
        cta_text = "Voir mon tableau de bord"
    else:
        subject = f"Your Pickup Code: {pickup_code}"
        headline = "Your Pickup Code"
        intro = f"<p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Hi {first},</p><p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Your funds are held in escrow. Present this code to the seller <strong>{seller_name}</strong> when you pick up your item.</p>"
        code_caption = "Present this code to the seller at pickup. Valid for 48 hours."
        cta_text = "View My Dashboard"

    body = f"""{intro}
<table width="100%" cellpadding="0" cellspacing="0"><tr><td style="text-align:center;padding:24px 0;">
<div style="display:inline-block;background-color:#F0F8FF;border:2px solid #3FB4CB;border-radius:8px;padding:24px 40px;">
<p class="pickup-code" style="font-family:'Courier New',Courier,monospace;font-size:48px;font-weight:700;color:#0B2545;letter-spacing:8px;margin:0;line-height:1.2;">{pickup_code}</p>
<p class="email-subtext" style="font-size:12px;color:#64748B;margin:8px 0 0 0;">{code_caption}</p>
</div></td></tr></table>
<table class="data-card" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F0F8FF;border:1px solid #3FB4CB;border-radius:8px;padding:16px;margin:16px 0;">
<tr><td><p class="email-subtext" style="margin:4px 0;color:#64748B;font-size:13px;">Auction: <strong style="color:#0B2545;">{auction_id}</strong></p>
<p class="email-subtext" style="margin:4px 0;color:#64748B;font-size:13px;">Seller: <strong style="color:#0B2545;">{seller_name}</strong></p>
<p class="email-subtext" style="margin:4px 0;color:#64748B;font-size:13px;">Expires: <strong style="color:#0B2545;">{expires_at}</strong></p></td></tr></table>
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 0;">
<a class="cta-button" href="{DASHBOARD_URL}" style="display:inline-block;background-color:#2186C6;color:#FFFFFF;font-weight:700;font-size:15px;text-decoration:none;padding:14px 32px;border-radius:8px;">{cta_text}</a>
</td></tr></table>"""

    html = _p0_wrap("#1C6EC1", "&#128274;", headline, body, lang)
    return await _send_p0_email(
        buyer.get("email", ""), first, "pickup_code", lang, subject, html,
        {"first_name": first, "pickup_code": pickup_code, "auction_id": auction_id,
         "seller_name": seller_name, "expires_at": expires_at,
         "dashboard_url": DASHBOARD_URL, "subject": subject},
    )


# ── 2. ESCROW FUNDS RELEASED EMAIL (Seller) ──────────────────

async def send_escrow_released_email(seller: dict, buyer: dict, escrow: dict) -> bool:
    lang = seller.get("language_preference", seller.get("preferred_language", "en"))
    lang = "fr" if lang and lang.startswith("fr") else "en"
    first = (seller.get("first_name") or seller.get("full_name", seller.get("name", ""))).split()[0] if seller.get("first_name") or seller.get("full_name") or seller.get("name") else "Seller"
    auction_id = escrow.get("auction_id", "N/A")
    total_cents = escrow.get("total_charged_cents", 0)
    fee_cents = escrow.get("application_fee_cents", 0)
    payout = f"${(total_cents - fee_cents) / 100:.2f} CAD"
    transfer_id = escrow.get("stripe_transfer_id", "N/A")

    if lang == "fr":
        subject = f"Fonds libérés — Enchère {auction_id}"
        headline = "Fonds libérés avec succès"
        intro = f"<p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Bonjour {first},</p><p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>L'acheteur a confirmé le retrait. Vos fonds ont été transférés à votre compte Stripe Connect.</p>"
        cta_text = "Voir mon tableau de bord"
    else:
        subject = f"Funds Released — Auction {auction_id}"
        headline = "Funds Successfully Released"
        intro = f"<p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Hi {first},</p><p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>The buyer has confirmed pickup. Your funds have been transferred to your Stripe Connect account.</p>"
        cta_text = "View My Dashboard"

    body = f"""{intro}
<table class="data-card" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F0F8FF;border:1px solid #3FB4CB;border-radius:8px;padding:16px;margin:16px 0;">
<tr><td>
<p class="email-subtext" style="margin:4px 0;color:#64748B;font-size:13px;">Auction: <strong style="color:#0B2545;">{auction_id}</strong></p>
<p style="margin:8px 0;color:#0B2545;font-size:22px;font-weight:700;">{payout}</p>
<p class="email-subtext" style="margin:4px 0;color:#64748B;font-size:13px;">Transfer: <strong style="color:#0B2545;">{transfer_id}</strong></p>
</td></tr></table>
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 0;">
<a class="cta-button" href="{DASHBOARD_URL}" style="display:inline-block;background-color:#2186C6;color:#FFFFFF;font-weight:700;font-size:15px;text-decoration:none;padding:14px 32px;border-radius:8px;">{cta_text}</a>
</td></tr></table>"""

    html = _p0_wrap("#10b981", "&#9989;", headline, body, lang)
    return await _send_p0_email(
        seller.get("email", ""), first, "escrow_released", lang, subject, html,
        {"first_name": first, "auction_id": auction_id, "amount_released": payout,
         "transfer_id": transfer_id, "dashboard_url": DASHBOARD_URL},
    )


# ── 3. CANCELLATION PENALTY EMAIL (Seller) ───────────────────

async def send_cancellation_penalty_email(seller: dict, listing_id: str,
                                          penalty_amount: str, reason: str) -> bool:
    lang = seller.get("language_preference", seller.get("preferred_language", "en"))
    lang = "fr" if lang and lang.startswith("fr") else "en"
    first = (seller.get("first_name") or seller.get("full_name", seller.get("name", ""))).split()[0] if seller.get("first_name") or seller.get("full_name") or seller.get("name") else "Seller"

    if lang == "fr":
        subject = f"Pénalité d'annulation — {penalty_amount}"
        headline = "Pénalité d'annulation appliquée"
        intro = f"<p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Bonjour {first},</p><p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Une pénalité d'annulation a été débitée de votre mode de paiement enregistré.</p>"
        cta_text = "Contacter le support"
    else:
        subject = f"Cancellation Penalty — {penalty_amount}"
        headline = "Cancellation Penalty Applied"
        intro = f"<p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Hi {first},</p><p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>A cancellation penalty has been charged to your payment method on file.</p>"
        cta_text = "Contact Support"

    body = f"""{intro}
<table class="data-card" width="100%" cellpadding="0" cellspacing="0" style="background-color:#FEF2F2;border:1px solid #FCA5A5;border-radius:8px;padding:16px;margin:16px 0;">
<tr><td>
<p style="margin:8px 0;color:#DC2626;font-size:22px;font-weight:700;">{penalty_amount}</p>
<p class="email-subtext" style="margin:4px 0;color:#64748B;font-size:13px;">Listing: <strong style="color:#0B2545;">{listing_id}</strong></p>
<p class="email-subtext" style="margin:4px 0;color:#64748B;font-size:13px;">Reason: <strong style="color:#0B2545;">{reason}</strong></p>
</td></tr></table>
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 0;">
<a class="cta-button" href="{SUPPORT_URL}" style="display:inline-block;background-color:#2186C6;color:#FFFFFF;font-weight:700;font-size:15px;text-decoration:none;padding:14px 32px;border-radius:8px;">{cta_text}</a>
</td></tr></table>"""

    html = _p0_wrap("#DC2626", "&#9888;&#65039;", headline, body, lang)
    return await _send_p0_email(
        seller.get("email", ""), first, "cancellation_penalty", lang, subject, html,
        {"first_name": first, "penalty_amount": penalty_amount, "listing_id": listing_id,
         "reason": reason, "support_url": SUPPORT_URL},
    )


# ── 4. AUTO-RELEASE NOTICE EMAIL (Buyer) ─────────────────────

async def send_auto_release_email(buyer: dict, seller: dict, escrow: dict) -> bool:
    lang = buyer.get("language_preference", buyer.get("preferred_language", "en"))
    lang = "fr" if lang and lang.startswith("fr") else "en"
    first = (buyer.get("first_name") or buyer.get("full_name", buyer.get("name", ""))).split()[0] if buyer.get("first_name") or buyer.get("full_name") or buyer.get("name") else "Buyer"
    auction_id = escrow.get("auction_id", "N/A")
    total_cents = escrow.get("total_charged_cents", 0)
    fee_cents = escrow.get("application_fee_cents", 0)
    payout = f"${(total_cents - fee_cents) / 100:.2f} CAD"

    if lang == "fr":
        subject = f"Fonds libérés automatiquement — Enchère {auction_id}"
        headline = "Libération automatique des fonds"
        intro = f"<p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Bonjour {first},</p><p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Le délai de 48 heures pour la confirmation du retrait est expiré. Les fonds ont été automatiquement libérés au vendeur.</p>"
        reason = "Délai de 48h expiré — libération automatique"
        cta_text = "Voir mon tableau de bord"
    else:
        subject = f"Funds Auto-Released — Auction {auction_id}"
        headline = "Funds Auto-Released"
        intro = f"<p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Hi {first},</p><p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>The 48-hour pickup confirmation window has expired. Funds have been automatically released to the seller.</p>"
        reason = "48-hour window expired — auto-released"
        cta_text = "View My Dashboard"

    body = f"""{intro}
<table class="data-card" width="100%" cellpadding="0" cellspacing="0" style="background-color:#F0F8FF;border:1px solid #3FB4CB;border-radius:8px;padding:16px;margin:16px 0;">
<tr><td>
<p class="email-subtext" style="margin:4px 0;color:#64748B;font-size:13px;">Auction: <strong style="color:#0B2545;">{auction_id}</strong></p>
<p style="margin:8px 0;color:#0B2545;font-size:22px;font-weight:700;">{payout}</p>
<p class="email-subtext" style="margin:4px 0;color:#64748B;font-size:13px;">{reason}</p>
</td></tr></table>
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 0;">
<a class="cta-button" href="{DASHBOARD_URL}" style="display:inline-block;background-color:#2186C6;color:#FFFFFF;font-weight:700;font-size:15px;text-decoration:none;padding:14px 32px;border-radius:8px;">{cta_text}</a>
</td></tr></table>"""

    html = _p0_wrap("#F59E0B", "&#9200;", headline, body, lang)
    return await _send_p0_email(
        buyer.get("email", ""), first, "auto_release", lang, subject, html,
        {"first_name": first, "auction_id": auction_id, "amount_released": payout,
         "auto_release_reason": reason, "dashboard_url": DASHBOARD_URL},
    )


# ── 5. STICKY CARD LOCKED EMAIL (Seller) ─────────────────────

async def send_sticky_card_locked_email(seller: dict, active_listing_count: int) -> bool:
    lang = seller.get("language_preference", seller.get("preferred_language", "en"))
    lang = "fr" if lang and lang.startswith("fr") else "en"
    first = (seller.get("first_name") or seller.get("full_name", seller.get("name", ""))).split()[0] if seller.get("first_name") or seller.get("full_name") or seller.get("name") else "Seller"

    if lang == "fr":
        subject = "Mode de paiement verrouillé — Annonces actives"
        headline = "Votre mode de paiement est verrouillé"
        intro = f"<p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Bonjour {first},</p><p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Vous avez <strong>{active_listing_count}</strong> annonce(s) active(s). Votre mode de paiement ne peut pas être retiré tant que toutes les annonces sont terminées ou annulées.</p>"
        cta_text = "Gérer mes annonces"
    else:
        subject = "Payment Method Locked — Active Listings"
        headline = "Your Payment Method is Locked"
        intro = f"<p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>Hi {first},</p><p class='email-text' style='color:#334155;font-size:15px;line-height:1.6;'>You have <strong>{active_listing_count}</strong> active listing(s). Your payment method cannot be removed until all listings are ended or cancelled.</p>"
        cta_text = "Manage My Listings"

    body = f"""{intro}
<table class="data-card" width="100%" cellpadding="0" cellspacing="0" style="background-color:#FEF3C7;border:1px solid #FCD34D;border-radius:8px;padding:16px;margin:16px 0;">
<tr><td>
<p style="margin:0;color:#92400E;font-size:15px;font-weight:600;">&#128274; {active_listing_count} active listing(s)</p>
</td></tr></table>
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:24px 0;">
<a class="cta-button" href="{DASHBOARD_URL}" style="display:inline-block;background-color:#2186C6;color:#FFFFFF;font-weight:700;font-size:15px;text-decoration:none;padding:14px 32px;border-radius:8px;">{cta_text}</a>
</td></tr></table>"""

    html = _p0_wrap("#F59E0B", "&#128179;", headline, body, lang)
    return await _send_p0_email(
        seller.get("email", ""), first, "sticky_card_locked", lang, subject, html,
        {"first_name": first, "active_listing_count": str(active_listing_count),
         "dashboard_url": DASHBOARD_URL},
    )



# ═══════════════════════════════════════════════════════════════
# BACKWARD COMPATIBILITY — EmailService class + get_email_service()
# Used by: server.py, admin_ops.py, auth.py, invoices.py, etc.
# ═══════════════════════════════════════════════════════════════

class EmailService:
    """Backward-compatible wrapper around the new template-based system."""

    def __init__(self):
        self.client = _get_sg()
        self.from_email = os.environ.get("SENDGRID_FROM_EMAIL", "info@bidvex.com")
        self.from_name = os.environ.get("SENDGRID_FROM_NAME", "BidVex")

    def is_configured(self) -> bool:
        return self.client is not None

    async def send_email(
        self,
        to: str,
        template_id: str,
        dynamic_data: Dict[str, Any],
        language: str = "en",
        **kwargs,
    ) -> Dict[str, Any]:
        """Send via dynamic template (old interface)."""
        dynamic_data.setdefault("current_year", datetime.now().year)
        dynamic_data["language"] = language

        success = await send_template_email(
            to_email=to,
            to_name=dynamic_data.get("first_name", ""),
            template_id=template_id,
            dynamic_data=dynamic_data,
        )
        return {"success": success, "message_id": None}

    async def send_with_retry(self, *args, **kwargs):
        return await self.send_email(*args, **kwargs)


_email_service_instance = None


def get_email_service() -> EmailService:
    """Singleton factory — backward compatible."""
    global _email_service_instance
    if _email_service_instance is None:
        _email_service_instance = EmailService()
    return _email_service_instance
