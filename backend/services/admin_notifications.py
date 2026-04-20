"""
BidVex Admin Notifications — all go to info@bidvex.com
Uses raw HTML via SendGrid (no template required).
"""
import os
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

ADMIN_EMAIL = "info@bidvex.com"
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")


def _admin_card(title, rows, cta_url="", cta_label=""):
    rows_html = "".join(
        f'<tr><td style="padding:8px 16px;color:#64748B;font-size:13px;">{k}</td>'
        f'<td style="padding:8px 16px;color:#1E293B;font-size:13px;font-weight:600;">{v}</td></tr>'
        for k, v in rows
    )
    cta = (
        f'<p style="margin-top:20px;text-align:center;">'
        f'<a href="{cta_url}" style="background:#0B2545;color:white;padding:12px 24px;'
        f'border-radius:8px;text-decoration:none;font-weight:bold;">{cta_label}</a></p>'
        if cta_url else ""
    )
    return f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#F0F4F8;font-family:sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:40px 20px;">
<table width="560" style="background:#fff;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
<tr><td style="background:#0B2545;padding:20px 24px;border-radius:10px 10px 0 0;">
<h2 style="color:#fff;margin:0;font-size:18px;">BidVex Admin &mdash; {title}</h2></td></tr>
<tr><td style="padding:8px 0;"><table width="100%">{rows_html}</table></td></tr>
<tr><td style="padding:0 24px 24px;">{cta}</td></tr>
<tr><td style="background:#F8FAFC;padding:12px 24px;border-radius:0 0 10px 10px;text-align:center;color:#94A3B8;font-size:11px;">
BidVex Canada &mdash; Admin Notification System</td></tr>
</table></td></tr></table></body></html>"""


async def _send_admin_raw(subject, html):
    """Send raw HTML email to admin via SendGrid REST API."""
    if not SENDGRID_API_KEY:
        logger.warning("[ADMIN_EMAIL] No SendGrid API key")
        return False
    try:
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        msg = Mail(
            from_email=Email(os.environ.get("SENDGRID_FROM_EMAIL", "noreply@bidvex.com"), "BidVex Canada"),
            to_emails=To(ADMIN_EMAIL, "BidVex Admin"),
            subject=subject,
            html_content=Content("text/html", html),
        )
        msg.reply_to = Email("support@bidvex.com", "BidVex Support")
        response = sg.send(msg)
        logger.info(f"[ADMIN_EMAIL] Sent: subject='{subject}' status={response.status_code}")
        return response.status_code in (200, 201, 202)
    except Exception as e:
        logger.error(f"[ADMIN_EMAIL] Failed: {e}")
        return False


async def notify_admin_new_user(user) -> bool:
    email = user.get("email", "") if isinstance(user, dict) else getattr(user, "email", "")
    name = user.get("full_name", email) if isinstance(user, dict) else getattr(user, "full_name", email)
    lang = (user.get("language_preference", "en") if isinstance(user, dict) else getattr(user, "language_preference", "en")) or "en"
    return await _send_admin_raw(
        f"New Signup - {email}",
        _admin_card("New User Registration", [
            ("Name", name), ("Email", email), ("Language", lang.upper()),
            ("Time", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")),
        ], cta_url="https://www.bidvex.com/admin/users", cta_label="View User"),
    )


async def notify_admin_new_listing(listing) -> bool:
    title = listing.get("title", "Untitled")
    seller_id = str(listing.get("seller_id", ""))
    return await _send_admin_raw(
        f"New Listing - {title}",
        _admin_card("New Listing Pending Approval", [
            ("Title", title), ("Seller ID", seller_id),
            ("Time", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")),
        ], cta_url="https://www.bidvex.com/admin", cta_label="Review Listing"),
    )


async def notify_admin_penalty_charged(seller, listing_id, amount) -> bool:
    email = seller.get("email", "") if isinstance(seller, dict) else getattr(seller, "email", "")
    return await _send_admin_raw(
        f"Penalty Charged - {email}",
        _admin_card("Cancellation Penalty Applied", [
            ("Seller", email), ("Listing", listing_id), ("Amount", amount),
            ("Time", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")),
        ], cta_url="https://www.bidvex.com/admin", cta_label="View Penalties"),
    )


async def notify_admin_failed_payment(user_email, amount, reason) -> bool:
    return await _send_admin_raw(
        f"Failed Payment - {user_email}",
        _admin_card("Payment Failed", [
            ("User", user_email), ("Amount", amount), ("Reason", reason),
            ("Time", datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")),
        ], cta_url="https://www.bidvex.com/admin", cta_label="View Payments"),
    )
