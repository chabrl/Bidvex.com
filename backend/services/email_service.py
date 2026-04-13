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

    from_email = os.environ.get("SENDGRID_FROM_EMAIL", "info@bidvex.com")
    from_name = os.environ.get("SENDGRID_FROM_NAME", "BidVex")

    # Ensure current_year is always present
    dynamic_data.setdefault("current_year", datetime.now().year)

    message = Mail(
        from_email=Email(from_email, from_name),
        to_emails=To(to_email, to_name),
    )
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
