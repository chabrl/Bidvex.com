"""
BidVex Email Templates Configuration

Maps logical email types to verified SendGrid Dynamic Template IDs.
Each template has EN and FR variants validated against the live API.

Source of truth: /app/backend/tests/email_test_report.json (54 templates, all 202)
"""

from typing import Dict, Any
from datetime import datetime, timezone


class EmailTemplates:
    """
    Verified SendGrid Dynamic Template IDs for BidVex emails.
    Each constant maps to {en: ..., fr: ...} for bilingual support.
    """

    # --- Authentication ---
    WELCOME = {
        "en": "d-db7d296ad54247138f3f210a1fb52e0a",
        "fr": "d-256f3801670441808730c4cfb259d9a2",
    }
    EMAIL_VERIFICATION = {
        "en": "d-79352dd5a50849c7bb4cbe93e726051f",
        "fr": "d-48d6d49961ab439f89d55b890bc84b8a",
    }
    PASSWORD_RESET = {
        "en": "d-dbfba723dd5e4895a579b462b19c56fb",
        "fr": "d-9084b4478e024056a9fa5207fdfc91e6",
    }
    PASSWORD_CHANGED = {
        "en": "d-1e018cb66df54ee58616f9abd0720b0f",
        "fr": "d-16ad9371e1c54f2996f4ff453dfc2b82",
    }
    TWO_FACTOR = {
        "en": "d-7fe6f17a934f491ca91aa36534be85e2",
        "fr": "d-ec1e531f92bc4d01bf24dc47620cabed",
    }
    LOGIN_ALERT = {
        "en": "d-2cbb18036b9e44e4ba67ac3ee614e339",
        "fr": "d-2e3509d0a8c3480e83cd0d6b6ffc8c25",
    }

    # --- Bidding ---
    BID_PLACED = {
        "en": "d-fde06627d9dc4b79a250123604efb39c",
        "fr": "d-e1fec1eab388405cb172f71c7b6e7879",
    }
    BID_OUTBID = {
        "en": "d-89c95108533249aaa1659e258f11dd90",
        "fr": "d-94110d612e1243a58fc28c99872cfce6",
    }
    BID_WON = {
        "en": "d-27a3e1edafe24fa09437ab929eeab070",
        "fr": "d-a790684646d0430b91686923b46bf697",
    }

    # --- Auction ---
    AUCTION_STARTED = {
        "en": "d-e525a2ab091a42049f75fb9d102b9cde",
        "fr": "d-7a20775199774c5b84e0c3c12c1721a6",
    }
    AUCTION_ENDING_SOON = {
        "en": "d-7ae5b7a394494823b16e71a1029e1e6e",
        "fr": "d-8c5efdf9cd2449a7b288bc8d3be54885",
    }
    AUCTION_RESULTS = {
        "en": "d-4c519ffa806f41729c07b5c9feca09ab",
        "fr": "d-284252b173364ddab13854da54c70a87",
    }

    # --- Seller ---
    NEW_BID_RECEIVED = {
        "en": "d-da5049e2aac143aa937c4dd113d9fb96",
        "fr": "d-5e45290634c648d5aa818a733a94f13d",
    }
    LISTING_APPROVED = {
        "en": "d-e65e2943cc6d4b0b968fb0f877357fc0",
        "fr": "d-2d34d8977ef84acaad852ddf73cf8fb7",
    }
    LISTING_REJECTED = {
        "en": "d-57976d80ab25467cad32db22cd11d06b",
        "fr": "d-168a20ae972845658e166bc442904136",
    }

    # --- Financial ---
    INVOICE = {
        "en": "d-d25445886edb4cc08cc8107b07cb343f",
        "fr": "d-780daa32909e438aad5ee459cb21703a",
    }
    PAYMENT_RECEIVED = {
        "en": "d-5f88411aa2584e63afccbbe6603b3b3a",
        "fr": "d-110c93dfaea74c439488cdbe89985bf3",
    }
    PAYOUT_SENT = {
        "en": "d-36b5f93ff1064b8c815253aa60c02829",
        "fr": "d-73eae4ffc4e9404f9aa931493a4f2724",
    }

    # --- Communication ---
    ANNOUNCEMENT = {
        "en": "d-877f77c6623b4ed3879e4a7fcab2f8a5",
        "fr": "d-b1fd6b2e096d47bb95c96fc9ca93af68",
    }
    SUPPORT_ACK = {
        "en": "d-5a4bdee8c66041ba8d44ba0d7fc0244a",
        "fr": "d-7ecc0e3ab5c24c8283416a0e1ef4c9eb",
    }
    PLATFORM_UPDATES = {
        "en": "d-268de17d00514f3bb674e688d414b157",
        "fr": "d-3dc15879450146dd9e1d48e59dc8cccc",
    }

    # --- Admin ---
    REPORT_RECEIVED = {
        "en": "d-539a4d89254f42baa38de4f139e7a36b",
        "fr": "d-1e6b72f9301c49949b9a5cb21f0a39d5",
    }
    ACCOUNT_SUSPENDED = {
        "en": "d-cf2d8fb5bad74d4ab00b85236a93755d",
        "fr": "d-89596fbe221f4740aa29cff3d09d6754",
    }

    # --- Affiliate ---
    AFFILIATE_COMMISSION = {
        "en": "d-60618f4cb6d54a579fe4cc82052ea41d",
        "fr": "d-df3d97fe87b34060b5b6dee14977efcd",
    }
    AFFILIATE_REFERRAL = {
        "en": "d-da95ceff24c54d39b15a29e56d804ee9",
        "fr": "d-32a08f1a11a7441186944747602cfd53",
    }
    AFFILIATE_EARNINGS = {
        "en": "d-bacce34b0273477f8e7e4df61b737512",
        "fr": "d-7e4e67d882ad490fac384ab166e7f89b",
    }
    AFFILIATE_SUMMARY = {
        "en": "d-ea4ab5b49ce9448fa552303fa5e9e2cd",
        "fr": "d-b7e970f39ce748c0bc3773a5a5606a91",
    }

    @classmethod
    def get_id(cls, template: dict, language: str = "en") -> str:
        """Return the template ID for the given language, falling back to EN."""
        return template.get(language, template["en"])


class EmailDataBuilder:
    """Helper class to build dynamic data for email templates."""

    @staticmethod
    def welcome_email(user: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "full_name": user.get("name"),
            "email": user.get("email"),
            "login_url": "https://bidvex.com/auth",
            "explore_url": "https://bidvex.com/marketplace",
            "account_type": user.get("account_type", "personal").title(),
        }

    @staticmethod
    def password_reset_email(
        user: Dict[str, Any], reset_token: str, expires_in_hours: int = 1
    ) -> Dict[str, Any]:
        reset_url = f"https://bidvex.com/reset-password?token={reset_token}"
        expiry_message = (
            f"{expires_in_hours} hour"
            if expires_in_hours == 1
            else f"{expires_in_hours} hours"
        )
        return {
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "reset_url": reset_url,
            "reset_link": reset_url,
            "expires_in_hours": expires_in_hours,
            "expiry_time": expiry_message,
            "support_email": "support@bidvex.com",
        }

    @staticmethod
    def password_changed_email(user: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "email": user.get("email"),
            "change_time": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "support_email": "support@bidvex.com",
            "login_url": "https://bidvex.com/auth",
        }

    @staticmethod
    def bid_placed_email(
        user: Dict[str, Any],
        listing: Dict[str, Any],
        bid_amount: float,
        currency: str = "CAD",
    ) -> Dict[str, Any]:
        return {
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "listing_title": listing.get("title"),
            "listing_url": f'https://bidvex.com/listing/{listing.get("id")}',
            "bid_amount": f"{bid_amount:.2f}",
            "currency": currency,
            "listing_image": listing.get("images", [""])[0],
            "auction_end_date": listing.get("auction_end_date"),
            "current_high_bid": f"{listing.get('current_price', 0):.2f}",
        }

    @staticmethod
    def outbid_email(
        user: Dict[str, Any],
        listing: Dict[str, Any],
        new_bid_amount: float,
        currency: str = "CAD",
    ) -> Dict[str, Any]:
        return {
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "listing_title": listing.get("title"),
            "listing_url": f'https://bidvex.com/listing/{listing.get("id")}',
            "new_bid_amount": f"{new_bid_amount:.2f}",
            "currency": currency,
            "listing_image": listing.get("images", [""])[0],
            "bid_now_url": f'https://bidvex.com/listing/{listing.get("id")}#bid',
        }

    @staticmethod
    def auction_won_email(
        user: Dict[str, Any],
        listing: Dict[str, Any],
        winning_bid: float,
        currency: str = "CAD",
    ) -> Dict[str, Any]:
        premium_rate = listing.get("custom_buyer_premium_rate") or 0.05
        premium_amount = round(winning_bid * premium_rate, 2)
        return {
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "listing_title": listing.get("title"),
            "winning_bid": f"{winning_bid:.2f}",
            "currency": currency,
            "listing_image": listing.get("images", [""])[0],
            "seller_name": listing.get("seller_name", "Seller"),
            "payment_url": f'https://bidvex.com/payment/{listing.get("id")}',
            "invoice_url": f'https://bidvex.com/invoice/{listing.get("id")}',
            "buyers_premium_percent": f"{premium_rate * 100:.1f}",
            "buyers_premium_amount": f"{premium_amount:.2f}",
        }

    @staticmethod
    def invoice_email(
        user: Dict[str, Any], invoice: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "invoice_number": invoice.get("invoice_number"),
            "invoice_date": invoice.get("date"),
            "total_amount": f"{invoice.get('total', 0):.2f}",
            "currency": invoice.get("currency", "CAD"),
            "items": invoice.get("items", []),
            "subtotal": f"{invoice.get('subtotal', 0):.2f}",
            "tax": f"{invoice.get('tax', 0):.2f}",
            "shipping": f"{invoice.get('shipping', 0):.2f}",
            "invoice_pdf_url": invoice.get("pdf_url"),
            "buyers_premium_percent": f"{invoice.get('buyers_premium_rate', 0.05) * 100:.1f}",
            "buyers_premium_amount": f"{invoice.get('buyers_premium_amount', 0):.2f}",
            "payment_method": invoice.get("payment_method", "Credit Card"),
        }

    @staticmethod
    def new_message_email(
        user: Dict[str, Any], sender: Dict[str, Any], message_preview: str
    ) -> Dict[str, Any]:
        return {
            "first_name": user.get("name", "").split()[0] if user.get("name") else "",
            "sender_name": sender.get("name"),
            "message_preview": (
                message_preview[:100] + "..."
                if len(message_preview) > 100
                else message_preview
            ),
            "messages_url": "https://bidvex.com/messages",
            "sender_profile_url": f'https://bidvex.com/seller/{sender.get("id")}',
        }


# --------------- helper functions ---------------

async def send_welcome_email(email_service, user: Dict[str, Any], language: str = "en"):
    """Send welcome email to new user."""
    return await email_service.send_email(
        to=user["email"],
        template_id=EmailTemplates.get_id(EmailTemplates.WELCOME, language),
        dynamic_data=EmailDataBuilder.welcome_email(user),
        language=language,
    )


async def send_password_reset_email(
    email_service,
    user: Dict[str, Any],
    reset_token: str,
    language: str = "en",
):
    """Send password reset email with inline HTML button (bypasses template variable issues)."""
    data = EmailDataBuilder.password_reset_email(user, reset_token)
    data["current_year"] = datetime.now().year
    reset_url = data["reset_url"]
    first_name = data["first_name"] or "there"
    expiry_time = data["expiry_time"]

    if language == "fr":
        subject = "BidVex — Réinitialisation de votre mot de passe"
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:40px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;">
  <tr><td style="background:#1e3a8a;padding:24px 32px;text-align:center;">
    <h1 style="color:#ffffff;margin:0;font-size:24px;">BidVex</h1>
  </td></tr>
  <tr><td style="padding:32px;">
    <h2 style="color:#1e3a8a;margin:0 0 16px;">Réinitialisation du mot de passe</h2>
    <p style="color:#374151;font-size:16px;line-height:1.6;">Bonjour {first_name},</p>
    <p style="color:#374151;font-size:16px;line-height:1.6;">Nous avons reçu une demande de réinitialisation de votre mot de passe. Cliquez sur le bouton ci-dessous pour continuer :</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;"><tr><td align="center">
      <a href="{reset_url}" target="_blank" style="display:inline-block;background:#1e3a8a;color:#ffffff;text-decoration:none;padding:14px 32px;border-radius:6px;font-size:16px;font-weight:bold;">Réinitialiser le mot de passe</a>
    </td></tr></table>
    <p style="color:#6b7280;font-size:14px;line-height:1.5;">Ce lien expire dans {expiry_time}. Si vous n'avez pas fait cette demande, ignorez ce courriel.</p>
    <p style="color:#6b7280;font-size:12px;line-height:1.5;margin-top:16px;word-break:break-all;">Lien direct : <a href="{reset_url}" style="color:#1e3a8a;">{reset_url}</a></p>
  </td></tr>
  <tr><td style="background:#f9fafb;padding:16px 32px;text-align:center;">
    <p style="color:#9ca3af;font-size:12px;margin:0;">&copy; BidVex {data['current_year']} — support@bidvex.com</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""
    else:
        subject = "BidVex — Reset Your Password"
        html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:0;background:#f4f4f5;font-family:Arial,Helvetica,sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f5;padding:40px 0;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#ffffff;border-radius:8px;overflow:hidden;">
  <tr><td style="background:#1e3a8a;padding:24px 32px;text-align:center;">
    <h1 style="color:#ffffff;margin:0;font-size:24px;">BidVex</h1>
  </td></tr>
  <tr><td style="padding:32px;">
    <h2 style="color:#1e3a8a;margin:0 0 16px;">Password Reset</h2>
    <p style="color:#374151;font-size:16px;line-height:1.6;">Hi {first_name},</p>
    <p style="color:#374151;font-size:16px;line-height:1.6;">We received a request to reset your password. Click the button below to continue:</p>
    <table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;"><tr><td align="center">
      <a href="{reset_url}" target="_blank" style="display:inline-block;background:#1e3a8a;color:#ffffff;text-decoration:none;padding:14px 32px;border-radius:6px;font-size:16px;font-weight:bold;">Reset Password</a>
    </td></tr></table>
    <p style="color:#6b7280;font-size:14px;line-height:1.5;">This link expires in {expiry_time}. If you didn't request this, please ignore this email.</p>
    <p style="color:#6b7280;font-size:12px;line-height:1.5;margin-top:16px;word-break:break-all;">Direct link: <a href="{reset_url}" style="color:#1e3a8a;">{reset_url}</a></p>
  </td></tr>
  <tr><td style="background:#f9fafb;padding:16px 32px;text-align:center;">
    <p style="color:#9ca3af;font-size:12px;margin:0;">&copy; BidVex {data['current_year']} — support@bidvex.com</p>
  </td></tr>
</table>
</td></tr></table>
</body></html>"""

    return await email_service.send_raw_html(to=user["email"], subject=subject, html_content=html, disable_tracking=True)


async def send_bid_confirmation(
    email_service,
    user: Dict[str, Any],
    listing: Dict[str, Any],
    bid_amount: float,
    language: str = "en",
):
    """Send bid placement confirmation."""
    return await email_service.send_email(
        to=user["email"],
        template_id=EmailTemplates.get_id(EmailTemplates.BID_PLACED, language),
        dynamic_data=EmailDataBuilder.bid_placed_email(user, listing, bid_amount),
        language=language,
    )


async def send_outbid_notification(
    email_service,
    user: Dict[str, Any],
    listing: Dict[str, Any],
    new_bid_amount: float,
    language: str = "en",
):
    """Send outbid notification."""
    return await email_service.send_email(
        to=user["email"],
        template_id=EmailTemplates.get_id(EmailTemplates.BID_OUTBID, language),
        dynamic_data=EmailDataBuilder.outbid_email(user, listing, new_bid_amount),
        language=language,
    )
