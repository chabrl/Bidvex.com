"""
BidVex Admin Notifications — recipient resolved at call-time from env vars.
Uses raw HTML via SendGrid (no template required).

Recipient resolution order (first non-empty wins):
    ADMIN_NOTIFICATION_EMAIL  →  ADMIN_EMAIL  →  "charbel911@gmail.com"

The hardcoded fallback is the authoritative BidVex ops inbox — any deployment
that loses the env-var values still routes admin alerts to a real human inbox.
"""
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _resolve_admin_email() -> str:
    """Read admin recipient at runtime — tolerates env reloads / overrides."""
    return (
        os.environ.get("ADMIN_NOTIFICATION_EMAIL")
        or os.environ.get("ADMIN_EMAIL")
        or "charbel911@gmail.com"
    )


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
    """iter244 Mission 2 — Send admin alert via the unified email pipeline.

    Routes through `send_unified_email()` with `html_full_override` so the
    rich admin HTML is preserved byte-for-byte while consolidating ALL
    outbound mails into a single canonical send path.
    """
    admin_email = _resolve_admin_email()
    try:
        from services.emails._email_core import send_unified_email
        result = await send_unified_email(
            "new_feature",
            user={"email": admin_email, "first_name": "BidVex Admin"},
            data={
                "html_full_override": html,
                "subject_override": subject,
            },
        )
        status = result.get("status") if isinstance(result, dict) else None
        logger.info(f"[ADMIN_EMAIL] Sent to {admin_email}: subject='{subject}' status={status}")
        return status in ("sent", "logged")
    except Exception as e:
        logger.error(f"[ADMIN_EMAIL] Failed to {admin_email}: {e}")
        return False


async def notify_admin_new_user(user) -> bool:
    def _g(key, default=""):
        if isinstance(user, dict):
            return user.get(key, default)
        return getattr(user, key, default)

    email = _g("email", "")
    name = _g("name") or _g("full_name") or email
    lang = (_g("preferred_language") or _g("language_preference") or "en") or "en"
    auth_provider = (_g("auth_provider") or "email") or "email"

    # Country (from signup IP geolocation)
    country_name = _g("signup_country_name") or "Unknown"
    country_code = _g("signup_country_code") or ""
    country_display = (
        f"{country_name} ({country_code})" if country_code and country_name != "Unknown" else country_name
    )

    # Referral
    ref_code = _g("referred_by_code")
    ref_email = _g("referred_by_email")
    ref_name = _g("referred_by_name")
    if ref_code:
        referred_display = (
            f"{ref_name} &lt;{ref_email}&gt; — code <strong>{ref_code}</strong>"
            if ref_email
            else f"code <strong>{ref_code}</strong>"
        )
    else:
        referred_display = "Direct (no referral)"

    return await _send_admin_raw(
        f"New Signup - {email}",
        _admin_card("New User Registration", [
            ("Name", name),
            ("Email", email),
            ("Provider", auth_provider.title()),
            ("Country", country_display),
            ("Referred by", referred_display),
            ("Language", lang.upper()),
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



async def notify_admin_base64_sweep(
    migrated_count: int,
    affected_docs: list,  # list of {"collection": str, "listing_id": str, "path": str, "url": str}
    skipped_count: int = 0,
    failed_count: int = 0,
) -> bool:
    """iter351 — Nightly base64 sweep alert.

    Fires only when migrated_count > 0 (i.e. a client bypassed the S3
    pre-signed URL flow and wrote base64 into the DB). Lists the affected
    listing IDs so ops can trace the frontend regression quickly.
    """
    # Group affected docs by collection for readable HTML
    by_coll: dict = {}
    for row in affected_docs:
        by_coll.setdefault(row["collection"], []).append(row)

    per_coll_html = ""
    for coll, rows in sorted(by_coll.items()):
        # Deduplicate listing_ids (an item with 5 base64 images shows once)
        unique_ids = []
        seen = set()
        for r in rows:
            if r["listing_id"] not in seen:
                seen.add(r["listing_id"])
                unique_ids.append(r["listing_id"])
        ids_html = "".join(
            f'<li style="font-family:monospace;font-size:12px;color:#0B2545;">{lid}</li>'
            for lid in unique_ids[:50]  # cap at 50 IDs per collection to keep email readable
        )
        overflow = ""
        if len(unique_ids) > 50:
            overflow = f'<li style="color:#94A3B8;font-size:12px;">… and {len(unique_ids) - 50} more</li>'
        per_coll_html += (
            f'<tr><td style="padding:8px 16px;font-weight:600;color:#0B2545;">'
            f'{coll} <span style="color:#64748B;font-weight:400;">({len(rows)} images, '
            f'{len(unique_ids)} listing IDs)</span></td></tr>'
            f'<tr><td style="padding:0 32px 12px;"><ul style="margin:0;padding-left:20px;">'
            f'{ids_html}{overflow}</ul></td></tr>'
        )

    subject = f"iter351 — Nightly Base64 Sweep migrated {migrated_count} image(s)"
    html = f"""<!DOCTYPE html><html><body style="margin:0;padding:0;background:#F0F4F8;font-family:sans-serif;">
<table width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" style="padding:40px 20px;">
<table width="640" style="background:#fff;border-radius:10px;box-shadow:0 4px 20px rgba(0,0,0,0.08);">
<tr><td style="background:#B45309;padding:20px 24px;border-radius:10px 10px 0 0;">
<h2 style="color:#fff;margin:0;font-size:18px;">⚠️ BidVex Admin &mdash; Base64 Sweep Alert</h2></td></tr>
<tr><td style="padding:20px 24px;">
<p style="margin:0 0 12px;color:#1E293B;font-size:14px;">
A client bypassed the S3 pre-signed URL flow and wrote base64 images directly to MongoDB.
The nightly sweep at 04:00 UTC has already migrated them to S3, but the frontend flow
that produced them should be identified and patched (see backlog: "block base64 at API boundary").
</p>
<table width="100%" style="border-top:1px solid #E2E8F0;margin-top:8px;">
<tr><td style="padding:8px 0;color:#64748B;font-size:13px;">Images migrated</td>
<td style="padding:8px 0;color:#1E293B;font-size:13px;font-weight:600;">{migrated_count}</td></tr>
<tr><td style="padding:8px 0;color:#64748B;font-size:13px;">Already-on-S3 (skipped)</td>
<td style="padding:8px 0;color:#1E293B;font-size:13px;font-weight:600;">{skipped_count}</td></tr>
<tr><td style="padding:8px 0;color:#64748B;font-size:13px;">Failed uploads</td>
<td style="padding:8px 0;color:#1E293B;font-size:13px;font-weight:600;">{failed_count}</td></tr>
<tr><td style="padding:8px 0;color:#64748B;font-size:13px;">Time (UTC)</td>
<td style="padding:8px 0;color:#1E293B;font-size:13px;font-weight:600;">{datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")}</td></tr>
</table>
</td></tr>
<tr><td style="padding:0 24px 20px;">
<h3 style="color:#0B2545;font-size:14px;margin:12px 0 8px;">Affected listing IDs</h3>
<table width="100%">{per_coll_html}</table>
</td></tr>
<tr><td style="padding:0 24px 24px;text-align:center;">
<a href="https://www.bidvex.com/admin/feeds" style="background:#0B2545;color:white;padding:12px 24px;
border-radius:8px;text-decoration:none;font-weight:bold;">Review Feed Diagnostics</a>
</td></tr>
<tr><td style="background:#F8FAFC;padding:12px 24px;border-radius:0 0 10px 10px;text-align:center;color:#94A3B8;font-size:11px;">
BidVex Canada &mdash; Admin Notification System &mdash; iter351 nightly_base64_sweep</td></tr>
</table></td></tr></table></body></html>"""
    return await _send_admin_raw(subject, html)
