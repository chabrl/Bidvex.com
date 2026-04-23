"""
BidVex — SendGrid Event Webhook Receiver
Headquarters: Sherbrooke, QC, Canada.

Endpoint: POST /api/webhooks/sendgrid

Processes SendGrid Event Webhook payloads (array of events) to maintain
deliverability, honor unsubscribes, log engagement, and alert admins on
spam reports (sender-reputation protection — currently 97%).

Reference: https://docs.sendgrid.com/for-developers/tracking-events/event
"""

from __future__ import annotations

import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Depends, Query
from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)

sendgrid_webhook_router = APIRouter(tags=["SendGrid Webhook"])

# ─── Config ─────────────────────────────────────────────────────────────────

SENDGRID_WEBHOOK_PUBLIC_KEY = os.environ.get("SENDGRID_WEBHOOK_PUBLIC_KEY", "").strip()
ADMIN_ALERT_EMAIL = os.environ.get("ADMIN_ALERT_EMAIL", "info@bidvex.com")
HQ_LABEL = "BidVex Canada — Sherbrooke, QC"

# Event → category (used for concise routing)
DELIVERABILITY_KILL_EVENTS = {"bounce", "dropped", "spamreport"}
UNSUBSCRIBE_EVENTS = {"unsubscribe", "group_unsubscribe"}
RESUBSCRIBE_EVENTS = {"group_resubscribe"}
DELIVERY_STATUS_EVENTS = {"processed", "delivered", "deferred"}
ENGAGEMENT_EVENTS = {"open", "click"}


# ─── HMAC Signature Verification ────────────────────────────────────────────

async def _verify_signature(request: Request, raw_body: bytes) -> bool:
    """
    Verify SendGrid Event Webhook ECDSA signature when a public key is
    configured. Returns True if valid OR if verification is disabled.
    """
    if not SENDGRID_WEBHOOK_PUBLIC_KEY:
        return True  # verification disabled; accept all
    try:
        from sendgrid.helpers.eventwebhook import EventWebhook  # type: ignore

        signature = request.headers.get("X-Twilio-Email-Event-Webhook-Signature")
        timestamp = request.headers.get("X-Twilio-Email-Event-Webhook-Timestamp")
        if not signature or not timestamp:
            logger.warning("[SG_WEBHOOK] Missing signature/timestamp headers")
            return False

        ew = EventWebhook()
        pub_key = ew.convert_public_key_to_ecdsa(SENDGRID_WEBHOOK_PUBLIC_KEY)
        payload = raw_body.decode("utf-8") if isinstance(raw_body, (bytes, bytearray)) else str(raw_body)
        ok = ew.verify_signature(pub_key, payload, signature, timestamp)
        if not ok:
            logger.warning("[SG_WEBHOOK] Signature verification FAILED")
        return bool(ok)
    except ImportError:
        logger.error("[SG_WEBHOOK] sendgrid EventWebhook helper unavailable — skipping verification")
        return True
    except Exception as e:
        logger.error(f"[SG_WEBHOOK] Verification error: {e}")
        return False


# ─── Event Handlers ─────────────────────────────────────────────────────────

async def _handle_deliverability_kill(db, event: Dict[str, Any]) -> None:
    """bounce / dropped / spamreport → mark user undeliverable + suppression list."""
    email = (event.get("email") or "").lower().strip()
    if not email:
        return

    event_type = event.get("event")
    reason = event.get("reason") or event.get("type") or ""
    sg_event_id = event.get("sg_event_id")

    # 1. Flag user — non-fatal if no user doc exists (webhook is source of truth)
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "email_deliverable": False,
                "email_deliverability_reason": reason,
                "email_deliverability_event": event_type,
                "email_deliverability_updated_at": datetime.now(timezone.utc),
            }
        },
    )

    # 2. Add to suppression list (idempotent on sg_event_id)
    if sg_event_id:
        await db.email_suppression.update_one(
            {"sg_event_id": sg_event_id},
            {
                "$setOnInsert": {
                    "email": email,
                    "event": event_type,
                    "reason": reason,
                    "bounce_type": event.get("type"),  # "hard" / "soft" / "blocked"
                    "status": event.get("status"),
                    "sg_message_id": event.get("sg_message_id"),
                    "created_at": datetime.now(timezone.utc),
                }
            },
            upsert=True,
        )
    else:
        await db.email_suppression.insert_one(
            {
                "email": email,
                "event": event_type,
                "reason": reason,
                "bounce_type": event.get("type"),
                "status": event.get("status"),
                "sg_message_id": event.get("sg_message_id"),
                "created_at": datetime.now(timezone.utc),
            }
        )


async def _handle_unsubscribe(db, event: Dict[str, Any]) -> None:
    """unsubscribe / group_unsubscribe → set marketing_unsubscribed."""
    email = (event.get("email") or "").lower().strip()
    if not email:
        return
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "marketing_unsubscribed": True,
                "marketing_unsubscribed_at": datetime.now(timezone.utc),
                "marketing_unsubscribed_source": event.get("event"),
                "marketing_unsubscribed_group_id": event.get("asm_group_id"),
            }
        },
    )


async def _handle_resubscribe(db, event: Dict[str, Any]) -> None:
    """group_resubscribe → clear marketing_unsubscribed."""
    email = (event.get("email") or "").lower().strip()
    if not email:
        return
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "marketing_unsubscribed": False,
                "marketing_resubscribed_at": datetime.now(timezone.utc),
            }
        },
    )


async def _handle_delivery_status(db, event: Dict[str, Any]) -> None:
    """processed / delivered / deferred → update email_sends row (best-effort)."""
    sg_message_id = event.get("sg_message_id")
    if not sg_message_id:
        return
    await db.email_sends.update_one(
        {"sg_message_id": sg_message_id},
        {
            "$set": {
                "delivery_status": event.get("event"),
                "delivery_updated_at": datetime.now(timezone.utc),
            }
        },
    )


async def _handle_engagement(db, event: Dict[str, Any]) -> None:
    """open / click → log to email_events (Reach & Velocity analytics)."""
    await db.email_events.insert_one(
        {
            "sg_event_id": event.get("sg_event_id"),
            "sg_message_id": event.get("sg_message_id"),
            "email": (event.get("email") or "").lower().strip(),
            "event": event.get("event"),
            "url": event.get("url"),  # click events only
            "user_agent": event.get("useragent"),
            "ip": event.get("ip"),
            "timestamp": datetime.fromtimestamp(
                event.get("timestamp", 0), tz=timezone.utc
            ) if event.get("timestamp") else datetime.now(timezone.utc),
            "category": event.get("category"),
            "campaign_id": event.get("campaign_id"),
            "received_at": datetime.now(timezone.utc),
        }
    )


# ─── Admin Spam Alert ───────────────────────────────────────────────────────

async def _send_spam_alert(event: Dict[str, Any]) -> None:
    """
    Sends an urgent admin alert when a recipient marks a BidVex email as spam.
    Sender reputation is currently ~97% — every spam complaint is material.
    Runs in a BackgroundTask so the webhook returns fast.
    """
    try:
        from services.admin_notifications import _send_admin_raw, _admin_card
    except Exception as e:
        logger.error(f"[SG_WEBHOOK] admin_notifications import failed: {e}")
        return

    email = event.get("email", "unknown")
    ts = event.get("timestamp")
    when = (
        datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if ts else datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    )
    rows = [
        ("Recipient", email),
        ("Event", "spamreport"),
        ("SendGrid Message ID", event.get("sg_message_id") or "n/a"),
        ("Subject", event.get("subject") or "n/a"),
        ("Category", ", ".join(event.get("category") or []) if isinstance(event.get("category"), list) else (event.get("category") or "n/a")),
        ("When", when),
        ("Impact", "Sender reputation at risk — investigate immediately"),
        ("Location", HQ_LABEL),
    ]
    html = _admin_card(
        "🚨 SPAM REPORT — Sender Reputation Alert",
        rows,
        cta_url="https://www.bidvex.com/admin/email-deliverability",
        cta_label="Review Email Deliverability",
    )
    subject = f"🚨 SPAM REPORT: {email} — BidVex sender-reputation alert"
    await _send_admin_raw(subject, html)
    logger.warning(
        f"[SG_WEBHOOK] SPAM REPORT processed for {email} — admin alerted "
        f"({HQ_LABEL})"
    )


# ─── Main Event Processor (runs in BackgroundTasks) ─────────────────────────

async def _process_events(events: List[Dict[str, Any]]) -> Dict[str, int]:
    """Dispatch each event to its handler. Never raises."""
    db = get_db()
    counters: Dict[str, int] = {}
    for ev in events:
        etype = (ev.get("event") or "").lower()
        counters[etype] = counters.get(etype, 0) + 1
        try:
            if etype in DELIVERABILITY_KILL_EVENTS:
                await _handle_deliverability_kill(db, ev)
                if etype == "spamreport":
                    await _send_spam_alert(ev)
            elif etype in UNSUBSCRIBE_EVENTS:
                await _handle_unsubscribe(db, ev)
            elif etype in RESUBSCRIBE_EVENTS:
                await _handle_resubscribe(db, ev)
            elif etype in DELIVERY_STATUS_EVENTS:
                await _handle_delivery_status(db, ev)
            elif etype in ENGAGEMENT_EVENTS:
                await _handle_engagement(db, ev)
            else:
                logger.info(f"[SG_WEBHOOK] Unhandled event type: {etype}")
        except Exception as e:
            logger.error(
                f"[SG_WEBHOOK] Handler error (event={etype}, email={ev.get('email')}): {e}"
            )
    logger.info(f"[SG_WEBHOOK] Processed {sum(counters.values())} events: {counters}")
    return counters


# ─── Routes ─────────────────────────────────────────────────────────────────

@sendgrid_webhook_router.post("/webhooks/sendgrid")
async def receive_sendgrid_events(
    request: Request,
    background_tasks: BackgroundTasks,
):
    """
    Receive SendGrid Event Webhook POST.

    SendGrid expects a fast 200 OK. We:
      1. Verify signature (if public key configured).
      2. Schedule event processing as a BackgroundTask.
      3. Return 200 immediately.
    """
    raw_body = await request.body()

    # Signature verification (if enabled)
    if not await _verify_signature(request, raw_body):
        logger.warning("[SG_WEBHOOK] Rejected request with invalid signature")
        # Returning 403 so SendGrid stops retrying a tampered payload
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse JSON — SendGrid sends an array of events
    try:
        import json as _json
        events = _json.loads(raw_body.decode("utf-8")) if raw_body else []
        if isinstance(events, dict):
            events = [events]  # tolerate single-object bodies
        if not isinstance(events, list):
            raise ValueError("Expected JSON array of events")
    except Exception as e:
        logger.error(f"[SG_WEBHOOK] Body parse error: {e}")
        # Return 200 anyway — SendGrid is not at fault for our parse errors
        # and we don't want infinite retries of unparseable payloads.
        return {"status": "received", "processed": 0, "error": "parse_failed"}

    # Process asynchronously so we can ACK fast
    background_tasks.add_task(_process_events, events)

    return {
        "status": "received",
        "count": len(events),
        "signature_verified": bool(SENDGRID_WEBHOOK_PUBLIC_KEY),
        "hq": HQ_LABEL,
    }


# ─── Admin Visibility ───────────────────────────────────────────────────────

@sendgrid_webhook_router.get("/admin/email-events")
async def admin_list_email_events(
    email: Optional[str] = Query(None, description="Filter by recipient email"),
    event: Optional[str] = Query(None, description="Filter by event type"),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(require_admin),
):
    """Return recent email engagement events for admin investigation."""
    db = get_db()
    q: Dict[str, Any] = {}
    if email:
        q["email"] = email.lower().strip()
    if event:
        q["event"] = event
    events = (
        await db.email_events.find(q, {"_id": 0})
        .sort("received_at", -1)
        .to_list(limit)
    )
    return {"count": len(events), "events": events}


@sendgrid_webhook_router.get("/admin/email-suppression")
async def admin_list_suppression(
    email: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(require_admin),
):
    """Return recent bounce/drop/spam entries (deliverability kill list)."""
    db = get_db()
    q: Dict[str, Any] = {}
    if email:
        q["email"] = email.lower().strip()
    items = (
        await db.email_suppression.find(q, {"_id": 0})
        .sort("created_at", -1)
        .to_list(limit)
    )
    return {"count": len(items), "items": items}
