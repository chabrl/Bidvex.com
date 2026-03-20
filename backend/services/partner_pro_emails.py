"""
BidVex Partner Pro Email Templates
HTML templates for trial lifecycle and subscription emails.
"""

BRAND_COLOR = "#06b6d4"
BRAND_NAME = "BidVex"
PROFILE_URL = "https://bidvex.com/settings/profile"


def _base_wrap(body: str) -> str:
    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#f8fafc;">
<table width="100%" cellpadding="0" cellspacing="0" style="background:#f8fafc;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
<tr><td style="background:linear-gradient(135deg,#0f172a,#164e63);padding:32px 40px;">
  <h1 style="margin:0;color:#fff;font-size:24px;">{BRAND_NAME}</h1>
</td></tr>
<tr><td style="padding:32px 40px;">{body}</td></tr>
<tr><td style="background:#f1f5f9;padding:20px 40px;text-align:center;">
  <p style="margin:0;font-size:12px;color:#94a3b8;">&copy; {BRAND_NAME}. All rights reserved.</p>
</td></tr>
</table>
</td></tr></table>
</body></html>"""


def trial_started(user_name: str, trial_end_date: str) -> dict:
    """Email sent when a user starts their 14-day Partner Pro trial."""
    body = f"""
    <h2 style="color:#0f172a;margin:0 0 16px;">Welcome to Partner Pro!</h2>
    <p style="color:#475569;line-height:1.6;">Hi {user_name},</p>
    <p style="color:#475569;line-height:1.6;">Your <strong>14-day free trial</strong> of Partner Pro is now active. All features are unlocked:</p>
    <ul style="color:#475569;line-height:1.8;padding-left:20px;">
      <li>Branded Storefront page</li>
      <li>CSV Bulk Listing Import</li>
      <li>2-hour Early Auction Access</li>
      <li>10 Featured Listings per month</li>
      <li>Full Analytics Dashboard + Export</li>
      <li>Priority Chat &amp; Email Support</li>
    </ul>
    <p style="color:#475569;line-height:1.6;">Your trial ends on <strong>{trial_end_date}</strong>.</p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{PROFILE_URL}" style="background:{BRAND_COLOR};color:#fff;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block;">
        Explore Partner Pro
      </a>
    </div>
    """
    return {
        "subject": f"Your {BRAND_NAME} Partner Pro trial is live!",
        "html": _base_wrap(body),
    }


def trial_reminder(user_name: str, days_left: int = 3) -> dict:
    """Email sent 3 days before trial expiry (day 10)."""
    body = f"""
    <h2 style="color:#0f172a;margin:0 0 16px;">Your trial ends in {days_left} days</h2>
    <p style="color:#475569;line-height:1.6;">Hi {user_name},</p>
    <p style="color:#475569;line-height:1.6;">Your Partner Pro trial is ending soon. After it expires, your account will revert to the Free tier.</p>
    <p style="color:#475569;line-height:1.6;">To keep your <strong>branded storefront</strong>, <strong>bulk import tools</strong>, <strong>early auction access</strong>, and <strong>analytics export</strong>, subscribe for just <strong>$240/year</strong> (50% launch discount).</p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{PROFILE_URL}" style="background:{BRAND_COLOR};color:#fff;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block;">
        Subscribe Now — $240/year
      </a>
    </div>
    <p style="color:#94a3b8;font-size:13px;">If you choose not to subscribe, your storefront and imported listings will remain but Partner Pro features will be locked.</p>
    """
    return {
        "subject": f"Your {BRAND_NAME} Partner Pro trial ends in {days_left} days",
        "html": _base_wrap(body),
    }


def trial_expired(user_name: str) -> dict:
    """Email sent when trial expires and user reverts to Free."""
    body = f"""
    <h2 style="color:#0f172a;margin:0 0 16px;">Your Partner Pro trial has ended</h2>
    <p style="color:#475569;line-height:1.6;">Hi {user_name},</p>
    <p style="color:#475569;line-height:1.6;">Your 14-day Partner Pro trial has expired and your account has been reverted to the <strong>Free</strong> tier.</p>
    <p style="color:#475569;line-height:1.6;">You can re-activate Partner Pro anytime for <strong>$240/year</strong> and get all your pro tools back instantly.</p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{PROFILE_URL}" style="background:{BRAND_COLOR};color:#fff;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block;">
        Reactivate Partner Pro
      </a>
    </div>
    """
    return {
        "subject": f"Your {BRAND_NAME} Partner Pro trial has ended",
        "html": _base_wrap(body),
    }


def subscription_confirmed(user_name: str, plan_name: str, amount: str, next_billing: str) -> dict:
    """Email sent when Partner Pro subscription is confirmed via Stripe."""
    body = f"""
    <h2 style="color:#0f172a;margin:0 0 16px;">Subscription Confirmed!</h2>
    <p style="color:#475569;line-height:1.6;">Hi {user_name},</p>
    <p style="color:#475569;line-height:1.6;">Thank you for subscribing to <strong>{plan_name}</strong>! Your account has been upgraded.</p>
    <table style="width:100%;border-collapse:collapse;margin:20px 0;">
      <tr><td style="padding:10px 0;border-bottom:1px solid #e2e8f0;color:#64748b;">Plan</td>
          <td style="padding:10px 0;border-bottom:1px solid #e2e8f0;font-weight:600;text-align:right;color:#0f172a;">{plan_name}</td></tr>
      <tr><td style="padding:10px 0;border-bottom:1px solid #e2e8f0;color:#64748b;">Amount</td>
          <td style="padding:10px 0;border-bottom:1px solid #e2e8f0;font-weight:600;text-align:right;color:#0f172a;">{amount}</td></tr>
      <tr><td style="padding:10px 0;color:#64748b;">Next Billing</td>
          <td style="padding:10px 0;font-weight:600;text-align:right;color:#0f172a;">{next_billing}</td></tr>
    </table>
    <div style="text-align:center;margin:28px 0;">
      <a href="{PROFILE_URL}" style="background:{BRAND_COLOR};color:#fff;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block;">
        Go to Dashboard
      </a>
    </div>
    """
    return {
        "subject": f"{BRAND_NAME} — {plan_name} subscription confirmed",
        "html": _base_wrap(body),
    }


def invoice_ready(user_name: str, invoice_number: str, download_url: str, amount: str) -> dict:
    """Email sent when a new invoice/PDF is ready to download."""
    body = f"""
    <h2 style="color:#0f172a;margin:0 0 16px;">Your Invoice is Ready</h2>
    <p style="color:#475569;line-height:1.6;">Hi {user_name},</p>
    <p style="color:#475569;line-height:1.6;">Invoice <strong>#{invoice_number}</strong> for <strong>{amount}</strong> is ready for download.</p>
    <div style="text-align:center;margin:28px 0;">
      <a href="{download_url}" style="background:{BRAND_COLOR};color:#fff;padding:12px 32px;border-radius:8px;text-decoration:none;font-weight:600;display:inline-block;">
        Download Invoice (PDF)
      </a>
    </div>
    <p style="color:#94a3b8;font-size:13px;">This download link expires in 1 hour. You can always generate a new link from your dashboard.</p>
    """
    return {
        "subject": f"{BRAND_NAME} Invoice #{invoice_number}",
        "html": _base_wrap(body),
    }
