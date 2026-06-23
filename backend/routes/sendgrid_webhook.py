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
ADMIN_ALERT_EMAIL = os.environ.get("ADMIN_ALERT_EMAIL", "charbel911@gmail.com")
HQ_LABEL = "BidVex Canada — Sherbrooke, QC"

# Event → category (used for concise routing)
DELIVERABILITY_KILL_EVENTS = {"bounce", "dropped"}
UNSUBSCRIBE_EVENTS = {"unsubscribe", "group_unsubscribe", "spamreport"}
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
        # SDK signature: verify_signature(payload, signature, timestamp, public_key=None)
        ok = ew.verify_signature(payload, signature, timestamp, pub_key)
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
        await db.email_suppressions.update_one(
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
        await db.email_suppressions.insert_one(
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
    """unsubscribe / group_unsubscribe / spamreport → set marketing_unsubscribed."""
    email = (event.get("email") or "").lower().strip()
    if not email:
        return
    now = datetime.now(timezone.utc)
    etype = event.get("event")
    # Upsert users — webhook is source of truth even for contact-only imports.
    import uuid as _uuid
    await db.users.update_one(
        {"email": email},
        {
            "$set": {
                "marketing_unsubscribed": True,
                "marketing_unsubscribed_at": now,
                "marketing_unsubscribed_source": etype,
                "marketing_unsubscribed_group_id": event.get("asm_group_id"),
            },
            "$setOnInsert": {
                "id": str(_uuid.uuid4()),
                "email": email,
                "created_at": now,
                "is_contact_only": True,
            },
        },
        upsert=True,
    )
    # Fast-lookup suppression table (used by send-time guard)
    await db.email_suppressions.update_one(
        {"email": email},
        {
            "$set": {
                "email": email,
                "unsubscribed_at": now,
                "source": etype or "sendgrid_webhook",
            }
        },
        upsert=True,
    )
    # Preserve admin spam alert behaviour (was previously triggered by the
    # deliverability_kill branch — preserved here now that spamreport is
    # routed to UNSUBSCRIBE_EVENTS).
    if etype == "spamreport":
        try:
            await _send_spam_alert(event)
        except Exception as e:
            logger.warning(f"[SG_WEBHOOK] spam alert failed: {e}")


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
            # iter271 — External campaign analytics counters.
            # The `custom_args` keys ride alongside top-level fields
            # in SendGrid's webhook payload, so check both.
            campaign_type = (
                ev.get("campaign_type")
                or (ev.get("custom_args") or {}).get("campaign_type")
                or ""
            )
            if campaign_type == "external":
                await _handle_external_campaign_event(db, ev)

            if etype in DELIVERABILITY_KILL_EVENTS:
                await _handle_deliverability_kill(db, ev)
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


# ─── iter271 — External campaign event handler ──────────────────────────────


_EXTERNAL_FIELD_MAP: Dict[str, str] = {
    "delivered":   "analytics.delivered",
    "open":        "analytics.opened",
    "click":       "analytics.clicked",
    "bounce":      "analytics.bounced",
    "dropped":     "analytics.bounced",
    "deferred":    "analytics.bounced",
    "blocked":     "analytics.bounced",
    "unsubscribe": "analytics.unsubscribed",
    "group_unsubscribe": "analytics.unsubscribed",
    "spamreport":  "analytics.spam_reports",
}

_EXTERNAL_AUTO_SUPPRESS: Dict[str, str] = {
    "bounce":            "bounce",
    "dropped":           "bounce",
    "blocked":           "bounce",
    "unsubscribe":       "unsubscribe",
    "group_unsubscribe": "unsubscribe",
    "spamreport":        "spam_report",
}


async def _handle_external_campaign_event(db, event: Dict[str, Any]) -> None:
    """Update `external_email_campaigns.analytics` + auto-suppress on
    bounce/unsubscribe/spamreport for external campaigns only."""
    etype = (event.get("event") or "").lower()
    custom = event.get("custom_args") or {}
    campaign_id = event.get("campaign_id") or custom.get("campaign_id")
    email = (event.get("email") or "").strip().lower()
    if not campaign_id:
        logger.info(f"[external-campaign-event] {etype} missing campaign_id — skipped")
        return

    field = _EXTERNAL_FIELD_MAP.get(etype)
    if field:
        await db.external_email_campaigns.update_one(
            {"id": campaign_id},
            {"$inc": {field: 1},
             "$set": {"analytics.last_updated_at": datetime.now(timezone.utc).isoformat()}},
        )

    suppress_reason = _EXTERNAL_AUTO_SUPPRESS.get(etype)
    if suppress_reason and email:
        await db.external_email_suppressions.update_one(
            {"email": email},
            {"$setOnInsert": {
                "email":         email,
                "reason":        suppress_reason,
                "campaign_id":   campaign_id,
                "suppressed_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

    # iter313 P2 — Per-Campaign 5% Bounce+Unsubscribe Guardrail.
    # When (bounces + unsubscribes + spam_reports) / recipient_count
    # exceeds 5%, auto-pause the campaign, halt any future sends,
    # notify admin, and surface an admin banner until manually
    # resumed (confirmation-gated). This protects SendGrid sender
    # reputation per-campaign (in addition to the global 1% global
    # guardrail that already exists).
    if etype in {"bounce", "dropped", "blocked", "unsubscribe",
                 "group_unsubscribe", "spamreport"}:
        await _maybe_auto_pause_campaign(db, campaign_id)


# iter313 P2 — Per-Campaign Auto-Pause Guardrail.
_GUARDRAIL_THRESHOLD_PCT  = 5.0    # bounce+unsub+spam ratio (percent)
_GUARDRAIL_MIN_SAMPLE     = 20     # ignore tiny-sample noise

async def _maybe_auto_pause_campaign(db, campaign_id: str) -> None:
    """Auto-pause a campaign if its negative-engagement ratio exceeds
    the 5% threshold. Guard against:
      • Already-auto-paused campaigns (re-trigger is harmless but noisy).
      • Drafts & scheduled campaigns (no sends yet).
      • Tiny samples (need >=20 attempted before pause triggers)."""
    doc = await db.external_email_campaigns.find_one(
        {"id": campaign_id},
        {"_id": 0, "id": 1, "status": 1, "analytics": 1, "recipient_count": 1,
         "name": 1, "subject_en": 1},
    )
    if not doc:
        return
    status = doc.get("status")
    # Only consider campaigns that are actively sending or already sent.
    if status not in {"sending", "sent"}:
        return
    a = doc.get("analytics") or {}
    bounced  = int(a.get("bounced") or 0)
    unsub    = int(a.get("unsubscribed") or 0)
    spam     = int(a.get("spam_reports") or 0)
    delivered = int(a.get("delivered") or 0)
    recipient_count = int(doc.get("recipient_count") or 0)
    # Denominator = total attempted (delivered + bounced + unsub).
    # We use this rather than recipient_count alone because some
    # recipients are suppressed pre-send (never attempted).
    attempted = max(delivered + bounced + unsub, recipient_count)
    if attempted < _GUARDRAIL_MIN_SAMPLE:
        return
    negative = bounced + unsub + spam
    ratio_pct = round((negative / attempted) * 100, 2)
    if ratio_pct <= _GUARDRAIL_THRESHOLD_PCT:
        return

    now_iso = datetime.now(timezone.utc).isoformat()
    # CAS update: only flip status → auto_paused if not already paused.
    res = await db.external_email_campaigns.update_one(
        {"id": campaign_id, "status": {"$nin": ["auto_paused", "paused"]}},
        {"$set": {
            "status":                       "auto_paused",
            "auto_paused_at":               now_iso,
            "auto_paused_reason":           "bounce_unsubscribe_ratio_exceeded",
            "auto_paused_ratio_pct":        ratio_pct,
            "auto_paused_negative_count":   negative,
            "auto_paused_attempted_count":  attempted,
            "updated_at":                   now_iso,
        }},
    )
    if res.modified_count == 0:
        return  # Already auto-paused; nothing to log/notify.

    # Audit trail (always written, even if notification mail fails).
    try:
        import uuid
        await db.campaign_guardrail_events.insert_one({
            "id":                str(uuid.uuid4()),
            "campaign_id":       campaign_id,
            "campaign_name":     doc.get("name") or doc.get("subject_en") or campaign_id,
            "event":             "auto_pause_triggered",
            "ratio_pct":         ratio_pct,
            "threshold_pct":     _GUARDRAIL_THRESHOLD_PCT,
            "negative_count":    negative,
            "attempted_count":   attempted,
            "bounced":           bounced,
            "unsubscribed":      unsub,
            "spam_reports":      spam,
            "triggered_at":      now_iso,
        })
    except Exception as audit_err:
        logger.warning(f"[guardrail audit] insert failed: {audit_err}")

    # In-app admin notification (bell badge).
    try:
        import uuid
        admin_users = await db.users.find(
            {"role": {"$in": ["admin", "super_admin"]}}, {"_id": 0, "id": 1, "email": 1},
        ).to_list(length=20)
        for au in admin_users:
            await db.notifications.insert_one({
                "id":         str(uuid.uuid4()),
                "user_id":    au["id"],
                "type":       "campaign_auto_paused",
                "title":      "Campaign auto-paused (5% guardrail)",
                "message":    (f"Campaign '{doc.get('name') or campaign_id}' "
                               f"auto-paused — bounce+unsubscribe ratio {ratio_pct}% "
                               f"exceeds 5% threshold ({negative}/{attempted})."),
                "url":        f"/admin/campaigns?focus={campaign_id}",
                "read":       False,
                "created_at": now_iso,
            })
    except Exception as notif_err:
        logger.warning(f"[guardrail notify] insert failed: {notif_err}")

    # Best-effort admin email alert. Never blocks the webhook.
    try:
        from services.email_service import send_html_email
        await send_html_email(
            to_email=ADMIN_ALERT_EMAIL,
            subject=f"[BidVex] Campaign auto-paused — {ratio_pct}% bounce/unsub ratio",
            html=(
                f"<h2>Campaign auto-paused</h2>"
                f"<p>The campaign <b>{doc.get('name') or campaign_id}</b> "
                f"(id <code>{campaign_id}</code>) was automatically paused "
                f"because its bounce+unsubscribe+spam ratio exceeded "
                f"the 5% guardrail.</p>"
                f"<ul>"
                f"<li>Ratio: <b>{ratio_pct}%</b> (threshold {_GUARDRAIL_THRESHOLD_PCT}%)</li>"
                f"<li>Negative events: {negative} ({bounced} bounced, "
                f"{unsub} unsubscribed, {spam} spam reports)</li>"
                f"<li>Attempted: {attempted}</li>"
                f"</ul>"
                f"<p>The campaign cannot resume sending until an admin "
                f"explicitly confirms resumption from the Admin Campaigns "
                f"dashboard.</p>"
                f"<p style='color:#64748b;font-size:12px'>{HQ_LABEL}</p>"
            ),
        )
    except Exception as mail_err:
        logger.warning(f"[guardrail mail] {mail_err}")


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
        await db.email_suppressions.find(q, {"_id": 0})
        .sort("created_at", -1)
        .to_list(limit)
    )
    return {"count": len(items), "items": items}
