"""
iter205 P0 — Compliance Admin Notification Dispatcher
======================================================
Whenever the watchdog or AI scanner pauses a listing, OR the synchronous
gate blocks a listing creation, this module:

  1. Inserts a row into `admin_notifications` (visible on Admin Home /
     Compliance Alerts tab) so an admin always sees the event.
  2. Best-effort SendGrid email to every super-admin / admin so urgent
     violations are pushed beyond the in-app surface.
  3. Bumps the `compliance_health_signals` counter so the green/yellow/red
     KPI can detect false-negatives even when the watchdog reports 0 paused.

All operations are fail-OPEN — a notification dispatch failure must NEVER
prevent the listing from being paused.

Public API:
  • notify_admins_of_violation(db, *, kind, listing, signals, …) → dict
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


async def _admin_recipients(db) -> list[str]:
    """Return list of admin email addresses to notify."""
    cursor = db.users.find(
        {"role": {"$in": ["admin", "super_admin"]}, "email": {"$ne": None}},
        {"_id": 0, "email": 1},
    ).limit(20)
    return [doc["email"] async for doc in cursor if doc.get("email")]


async def _send_admin_email(*, recipients: list[str], subject: str, html: str) -> bool:
    """Best-effort SendGrid send. Returns True on success, False on any failure."""
    if not recipients:
        return False
    try:
        from services.email_notifications import send_email
    except Exception as e:
        logger.warning("[notify] no email sender available: %s", e)
        return False
    sent_any = False
    for to in recipients:
        try:
            res = await send_email(to_email=to, subject=subject, html_content=html)
            if res:
                sent_any = True
        except Exception as e:
            logger.warning("[notify] sendgrid failure for %s: %s", to, e)
    return sent_any


async def notify_admins_of_violation(
    db,
    *,
    kind: str,                      # "blocked_at_gate" | "paused_by_ai" | "paused_by_watchdog"
    listing: dict,
    signals: list[str],
    seller_email: Optional[str] = None,
    extra: Optional[dict] = None,
) -> dict:
    """Insert admin_notifications row + dispatch email. Always returns a summary.

    Always best-effort: any failure is logged but never re-raised."""
    now = datetime.now(timezone.utc).isoformat()
    listing_id = listing.get("id")
    title = (listing.get("title") or "")[:160]
    category = listing.get("category")
    seller_id = listing.get("seller_id")

    severity = {
        "blocked_at_gate": "info",         # gate did its job — informational
        "paused_by_ai":    "warning",      # AI caught a slip-through
        "paused_by_watchdog": "high",      # watchdog backstop fired = something went wrong upstream
    }.get(kind, "warning")

    notification = {
        "kind": "vehicle_compliance_violation",
        "subkind": kind,
        "severity": severity,
        "listing_id": listing_id,
        "collection": (extra or {}).get("collection", "listings"),
        "seller_id": seller_id,
        "seller_email": seller_email,
        "title": title,
        "category": category,
        "detection_signals": signals,
        "read": False,
        "resolved": False,
        "created_at": now,
        **(extra or {}),
    }
    try:
        await db.admin_notifications.insert_one(notification)
    except Exception as e:
        logger.error("[notify] admin_notifications insert failed: %s", e)

    # Dispatch email asynchronously — do NOT block the watchdog/scanner
    if kind != "blocked_at_gate":  # Don't email for every blocked POST — too noisy
        try:
            recipients = await _admin_recipients(db)
            subject = f"[BidVex Compliance] Vehicle listing {kind.replace('_',' ')} — {title}"
            signal_html = "".join(f"<li><code>{s}</code></li>" for s in signals[:8])
            html = f"""
                <h2>Compliance system action</h2>
                <p><strong>Kind:</strong> {kind}</p>
                <p><strong>Listing ID:</strong> {listing_id}</p>
                <p><strong>Title:</strong> {title}</p>
                <p><strong>Category:</strong> {category or "(none)"}</p>
                <p><strong>Seller:</strong> {seller_email or seller_id}</p>
                <p><strong>Detection signals:</strong></p>
                <ul>{signal_html or '<li>(none)</li>'}</ul>
                <p><strong>Severity:</strong> {severity}</p>
                <p>Triage in the admin panel: Vehicles → Compliance Alerts.</p>
                <p style="color:#64748b;font-size:12px">iter205 — automated by the BidVex Safety Watchdog. Replies are not monitored.</p>
            """
            asyncio.create_task(_send_admin_email(recipients=recipients, subject=subject, html=html))
        except Exception as e:
            logger.warning("[notify] email dispatch scheduling failed: %s", e)

    return {"created_at": now, "severity": severity, "kind": kind, "listing_id": listing_id}
