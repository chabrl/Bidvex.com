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
# TEMPLATE ID REGISTRY — 65 Templates (45 existing + 20 new)
# ═══════════════════════════════════════════════════════════════

TEMPLATE_IDS = {
    # ── AUTHENTICATION ──
    "password_reset":          {"en": "d-dbfba723dd5e4895a579b462b19c56fb", "fr": "d-9084b4478e024056a9fa5207fdfc91e6"},
    "password_changed":        {"en": "d-1e018cb66df54ee58616f9abd0720b0f", "fr": "d-16ad9371e1c54f2996f4ff453dfc2b82"},
    "email_verification":      {"en": "d-79352dd5a50849c7bb4cbe93e726051f", "fr": "d-48d6d49961ab439f89d55b890bc84b8a"},
    "two_factor_code":         {"en": "d-7fe6f17a934f491ca91aa36534be85e2", "fr": "d-ec1e531f92bc4d01bf24dc47620cabed"},
    "new_login_alert":         {"en": "d-2cbb18036b9e44e4ba67ac3ee614e339", "fr": "d-2e3509d0a8c3480e83cd0d6b6ffc8c25"},

    # ── ADMIN ──
    "account_suspended":       {"en": "d-cf2d8fb5bad74d4ab00b85236a93755d", "fr": "d-89596fbe221f4740aa29cff3d09d6754"},
    "report_received":         {"en": "d-539a4d89254f42baa38de4f139e7a36b", "fr": "d-1e6b72f9301c49949b9a5cb21f0a39d5"},

    # ── COMMUNICATION ──
    "announcement":            {"en": "d-877f77c6623b4ed3879e4a7fcab2f8a5", "fr": "d-b1fd6b2e096d47bb95c96fc9ca93af68"},
    "support_acknowledgment":  {"en": "d-5a4bdee8c66041ba8d44ba0d7fc0244a", "fr": "d-7ecc0e3ab5c24c8283416a0e1ef4c9eb"},
    "platform_update":         {"en": "d-268de17d00514f3bb674e688d414b157", "fr": "d-3dc15879450146dd9e1d48e59dc8cccc"},

    # ── FINANCIAL ──
    "payment_receipt":         {"en": "d-5f88411aa2584e63afccbbe6603b3b3a", "fr": "d-110c93dfaea74c439488cdbe89985bf3"},
    "payout_sent":             {"en": "d-36b5f93ff1064b8c815253aa60c02829", "fr": "d-73eae4ffc4e9404f9aa931493a4f2724"},
    "invoice_created":         {"en": "d-d25445886edb4cc08cc8107b07cb343f", "fr": "d-780daa32909e438aad5ee459cb21703a"},
    "invoice_overdue":         {"en": "d-4636a9fb390d4bb995c339f257ad2f0e", "fr": "d-bab623f50c80456ba5b456b3b5392718"},

    # ── SELLER ──
    "new_bid_notification":    {"en": "d-da5049e2aac143aa937c4dd113d9fb96", "fr": "d-5e45290634c648d5aa818a733a94f13d"},
    "listing_approved":        {"en": "d-e65e2943cc6d4b0b968fb0f877357fc0", "fr": "d-2d34d8977ef84acaad852ddf73cf8fb7"},
    "listing_rejected":        {"en": "d-57976d80ab25467cad32db22cd11d06b", "fr": "d-168a20ae972845658e166bc442904136"},

    # ── AUCTION ──
    "auction_announcement":    {"en": "d-e525a2ab091a42049f75fb9d102b9cde", "fr": "d-7a20775199774c5b84e0c3c12c1721a6"},
    "auction_reminder":        {"en": "d-7ae5b7a394494823b16e71a1029e1e6e", "fr": "d-8c5efdf9cd2449a7b288bc8d3be54885"},
    "auction_results":         {"en": "d-4c519ffa806f41729c07b5c9feca09ab", "fr": "d-284252b173364ddab13854da54c70a87"},

    # ── BIDDING ──
    "outbid_notification":     {"en": "d-89c95108533249aaa1659e258f11dd90", "fr": "d-94110d612e1243a58fc28c99872cfce6"},
    "bid_confirmed":           {"en": "d-fde06627d9dc4b79a250123604efb39c", "fr": "d-e1fec1eab388405cb172f71c7b6e7879"},
    "winning_bid":             {"en": "d-27a3e1edafe24fa09437ab929eeab070", "fr": "d-a790684646d0430b91686923b46bf697"},

    # ── AFFILIATE ──
    "affiliate_summary":       {"en": "d-ea4ab5b49ce9448fa552303fa5e9e2cd", "fr": "d-b7e970f39ce748c0bc3773a5a5606a91"},
    "new_referral":            {"en": "d-da95ceff24c54d39b15a29e56d804ee9", "fr": "d-32a08f1a11a7441186944747602cfd53"},
    "commission_earned":       {"en": "d-60618f4cb6d54a579fe4cc82052ea41d", "fr": "d-df3d97fe87b34060b5b6dee14977efcd"},
    "monthly_earnings":        {"en": "d-bacce34b0273477f8e7e4df61b737512", "fr": "d-7e4e67d882ad490fac384ab166e7f89b"},

    # ── LIFECYCLE (NEW — 20 templates) ──
    "welcome":                 {"en": "d-db7d296ad54247138f3f210a1fb52e0a", "fr": "d-256f3801670441808730c4cfb259d9a2"},
    "onboarding_day3":         {"en": "d-884f427a37684e0d937cadf73faffd44", "fr": "d-6c5be61e422543c8859a1e20264b052f"},
    "onboarding_week1":        {"en": "d-f23e557e8af440cda87298f0beee80d0", "fr": "d-32635bb2f72d4b3dab65bbb41af0f732"},
    "subscription_pitch":      {"en": "d-afed7ddf42524c409c2f58b85a545253", "fr": "d-a3bbbd85e5f94ca7b5d11595f9dcdfd4"},
    "reengagement":            {"en": "d-09455f0d3ef94a92a37aa564a189c825", "fr": "d-6afc5c3ab46f461c8a03a7f7f9e81a42"},
    "reengagement_final":      {"en": "d-6764b5d0529948f9ad6d09f451f11b95", "fr": "d-bec5a63988134cbeaa3caf50307049bb"},
    "subscription_final_reminder": {"en": "d-be41f17f144e46828fd5a2d1b9dab866", "fr": "d-3f3a98cb1cb3439a9fac5d0978c34620"},
    "reactivation_offer":      {"en": "d-359b30aa432a4f92835f03ecde03e251", "fr": "d-93065251739f41379a78752b6f4ca6dc"},

    # ── GEO (NEW) ──
    "new_auction_near_you":    {"en": "d-e725583ae735418782928b68851f7aec", "fr": "d-4b94f354e8644a38ae7b467afe265c6f"},
    "ending_soon_near_you":    {"en": "d-759c6bd49cb7496ca51ea85ac9052174", "fr": "d-0ce023fd52b544edbe3261dafe5fd7e0"},
}


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
