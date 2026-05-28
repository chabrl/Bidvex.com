"""
iter234 — 24h Watchdog cron — pulls the last 24h of activity from MongoDB,
hands a clean text payload to Gemini 2.5 Flash via the direct google-genai
SDK (`generate_content`), and emails the markdown report to the platform
owner via the existing SendGrid helper.

Triggered daily at 00:00 UTC by services/scheduler.py (APScheduler CronTrigger).
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from services.genai_direct_client import (
    GEMINI_MODEL_ID,
    build_generation_config,
    get_genai_client,
)

logger = logging.getLogger(__name__)

# Recipient locked by the iter234 spec.
WATCHDOG_RECIPIENT_EMAIL = os.environ.get(
    "WATCHDOG_RECIPIENT_EMAIL",
    "charbel911@gmail.com",
).strip()

# Per-collection caps so a single noisy collection cannot blow the prompt budget.
DEFAULT_PER_COLLECTION_LIMIT = 500
DEFAULT_PAYLOAD_CHAR_BUDGET = 180_000  # ≈ 45k tokens, well within Gemini 2.5 Flash window


# ----------------------------------------------------------------------------
# 1. MongoDB activity-log aggregator
# ----------------------------------------------------------------------------
async def fetch_activity_payload(
    db,
    *,
    window_hours: int = 24,
    per_collection_limit: int = DEFAULT_PER_COLLECTION_LIMIT,
) -> Dict[str, Any]:
    """Pulls every relevant activity stream and flattens to a text payload.

    Returns a dict:
      {
        "window_start": iso,
        "window_end":   iso,
        "stats":        {<collection>: <count>},
        "payload_text": "<concatenated lines>",
      }
    """
    now = datetime.now(timezone.utc)
    since = now - timedelta(hours=window_hours)

    sections: List[str] = []
    stats: Dict[str, int] = {}

    collections_to_scan: List[Dict[str, Any]] = [
        {
            "name": "user_sessions",
            "ts_field": "created_at",
            "projection": {"_id": 0, "user_id": 1, "email": 1, "created_at": 1, "ip_address": 1, "user_agent": 1, "action": 1},
            "format": lambda d: (
                f"[{d.get('created_at')}] user_session "
                f"user={d.get('user_id', '?')} email={d.get('email', '?')} "
                f"ip={d.get('ip_address', '?')} action={d.get('action', 'login')}"
            ),
        },
        {
            "name": "audit_logs",
            "ts_field": "timestamp",
            "projection": {"_id": 0, "actor_id": 1, "actor_email": 1, "action": 1, "target_type": 1, "target_id": 1, "ip_address": 1, "timestamp": 1, "metadata": 1},
            "format": lambda d: (
                f"[{d.get('timestamp')}] audit "
                f"actor={d.get('actor_id', '?')} email={d.get('actor_email', '?')} "
                f"action={d.get('action', '?')} target={d.get('target_type', '?')}:{d.get('target_id', '?')} "
                f"ip={d.get('ip_address', '?')}"
            ),
        },
        {
            "name": "admin_logs",
            "ts_field": "timestamp",
            "projection": {"_id": 0, "admin_id": 1, "admin_email": 1, "action": 1, "timestamp": 1, "details": 1, "ip_address": 1},
            "format": lambda d: (
                f"[{d.get('timestamp')}] admin_action "
                f"admin={d.get('admin_id', '?')} email={d.get('admin_email', '?')} "
                f"action={d.get('action', '?')} ip={d.get('ip_address', '?')}"
            ),
        },
        {
            "name": "bids",
            "ts_field": "created_at",
            "projection": {"_id": 0, "bidder_id": 1, "bidder_email": 1, "listing_id": 1, "amount": 1, "currency": 1, "created_at": 1, "bidder_type": 1, "ip_address": 1},
            "format": lambda d: (
                f"[{d.get('created_at')}] bid "
                f"bidder={d.get('bidder_id', '?')} email={d.get('bidder_email', '?')} "
                f"listing={d.get('listing_id', '?')} amount={d.get('amount', '?')} {d.get('currency', 'CAD')} "
                f"type={d.get('bidder_type', 'buyer')} ip={d.get('ip_address', '?')}"
            ),
        },
        {
            "name": "payment_transactions",
            "ts_field": "created_at",
            "projection": {"_id": 0, "user_id": 1, "user_email": 1, "payment_status": 1, "amount": 1, "currency": 1, "created_at": 1, "stripe_session_id": 1, "ip_address": 1, "failure_reason": 1},
            "format": lambda d: (
                f"[{d.get('created_at')}] payment "
                f"user={d.get('user_id', '?')} email={d.get('user_email', '?')} "
                f"status={d.get('payment_status', '?')} amount={d.get('amount', '?')} {d.get('currency', 'CAD')} "
                f"failure={d.get('failure_reason', '-')} ip={d.get('ip_address', '?')}"
            ),
        },
        {
            "name": "stripe_events",
            "ts_field": "received_at",
            "projection": {"_id": 0, "event_id": 1, "event_type": 1, "received_at": 1, "user_id": 1, "outcome": 1},
            "format": lambda d: (
                f"[{d.get('received_at')}] stripe_event "
                f"type={d.get('event_type', '?')} event_id={d.get('event_id', '?')} "
                f"user={d.get('user_id', '?')} outcome={d.get('outcome', '-')}"
            ),
        },
    ]

    for spec in collections_to_scan:
        name = spec["name"]
        ts_field = spec["ts_field"]
        try:
            coll = db[name]
        except Exception:  # noqa: BLE001
            continue
        try:
            query = {ts_field: {"$gte": since, "$lte": now}}
            cursor = coll.find(
                query,
                spec["projection"],
            ).sort(ts_field, 1).limit(per_collection_limit)
            docs = await cursor.to_list(length=per_collection_limit)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[Watchdog] collection={name} query failed: {e}")
            continue

        stats[name] = len(docs)
        if not docs:
            continue
        lines = [spec["format"](d) for d in docs]
        sections.append(
            f"=== {name.upper()} ({len(docs)} records) ===\n" + "\n".join(lines)
        )

    payload_text = "\n\n".join(sections)
    # Hard char budget so a runaway day cannot crash the model
    if len(payload_text) > DEFAULT_PAYLOAD_CHAR_BUDGET:
        payload_text = payload_text[:DEFAULT_PAYLOAD_CHAR_BUDGET] + "\n\n[[truncated]]"

    return {
        "window_start": since.isoformat(),
        "window_end":   now.isoformat(),
        "stats":        stats,
        "payload_text": payload_text or "(no activity recorded in the past 24 hours)",
    }


# ----------------------------------------------------------------------------
# 2. Gemini analysis call (non-streaming)
# ----------------------------------------------------------------------------
def run_watchdog_analysis(payload_text: str, *, window_start_iso: str, window_end_iso: str) -> str:
    """Hand the raw activity payload to Gemini 2.5 Flash and return the
    markdown security report."""
    client = get_genai_client()
    config = build_generation_config(
        extra_system_instruction=(
            "You will now produce the Daily Security & Activity Summary as defined in Section 2 of your system instructions. "
            f"The activity window is from {window_start_iso} to {window_end_iso}. "
            "Output must be clean Markdown, three sections in order: "
            "**Daily Traffic Overview**, **Flagged Suspicious Activity**, **Watchdog Action Items**. "
            "Be concise, decisive, and include specific user IDs/emails when present."
        ),
        enable_google_search=True,
    )
    prompt = (
        "Below are the raw user activity logs, database dumps, and backend transaction "
        "histories captured over the past 24 hours of BidVex marketplace activity. "
        "Process them objectively per your watchdog protocol and emit the security report.\n\n"
        "=== ACTIVITY LOGS START ===\n"
        f"{payload_text}\n"
        "=== ACTIVITY LOGS END ==="
    )
    response = client.models.generate_content(
        model=GEMINI_MODEL_ID,
        contents=prompt,
        config=config,
    )
    return (getattr(response, "text", None) or "").strip() or (
        "_(Gemini returned an empty response — no analysis available.)_"
    )


# ----------------------------------------------------------------------------
# 3. SendGrid dispatch using the existing helper
# ----------------------------------------------------------------------------
async def send_watchdog_email(
    *,
    report_markdown: str,
    stats: Dict[str, int],
    window_start_iso: str,
    window_end_iso: str,
    recipient: Optional[str] = None,
) -> Dict[str, Any]:
    """Email the report via SendGrid (uses services.email_notifications.send_email)."""
    from services.email_notifications import send_email  # local import to avoid circular load

    recipient = (recipient or WATCHDOG_RECIPIENT_EMAIL).strip()
    subject = f"[BidVex Watchdog] Daily Security Report — {window_end_iso[:10]}"

    # Minimal HTML wrapper around the markdown body (preserves <br/> + monospace fenced blocks).
    stats_rows = "".join(
        f"<tr><td style='padding:4px 12px;border:1px solid #e5e7eb;'>{name}</td>"
        f"<td style='padding:4px 12px;border:1px solid #e5e7eb;text-align:right;'>{count}</td></tr>"
        for name, count in sorted(stats.items())
    ) or "<tr><td colspan='2' style='padding:8px;'>(no records pulled)</td></tr>"

    html_body = f"""
    <div style="font-family:-apple-system,Segoe UI,Roboto,sans-serif;max-width:760px;margin:0 auto;padding:24px;background:#f8fafc;">
      <h2 style="color:#0f172a;margin:0 0 8px 0;">BidVex Watchdog — Daily Security Report</h2>
      <p style="color:#475569;margin:0 0 16px 0;">
        Window: <strong>{window_start_iso}</strong> → <strong>{window_end_iso}</strong><br/>
        Model: <code>gemini-2.5-flash</code> · Thinking: dynamic · Google Search grounding: enabled
      </p>
      <table style="border-collapse:collapse;margin-bottom:24px;font-size:13px;">
        <thead>
          <tr style="background:#0f172a;color:#f8fafc;">
            <th style="padding:6px 12px;text-align:left;">Collection</th>
            <th style="padding:6px 12px;text-align:right;">Records pulled</th>
          </tr>
        </thead>
        <tbody>{stats_rows}</tbody>
      </table>
      <div style="background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;padding:20px;color:#0f172a;line-height:1.55;white-space:pre-wrap;font-size:14px;">{_html_escape(report_markdown)}</div>
      <p style="color:#94a3b8;font-size:11px;margin-top:24px;text-align:center;">
        BidVex Watchdog · automated daily scan · cron 00:00 UTC
      </p>
    </div>
    """.strip()

    return await send_email(
        to_email=recipient,
        subject=subject,
        html_content=html_body,
    )


def _html_escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
         .replace("<", "&lt;")
         .replace(">", "&gt;")
    )


# ----------------------------------------------------------------------------
# 4. Top-level cron entry point
# ----------------------------------------------------------------------------
async def run_daily_watchdog_cycle(db) -> Dict[str, Any]:
    """One-shot: pull 24h logs → Gemini analysis → SendGrid email.

    Returns a small status dict for the scheduler observability layer.
    """
    started_at = datetime.now(timezone.utc)
    logger.info("[Watchdog] daily cycle started at %s", started_at.isoformat())

    try:
        bundle = await fetch_activity_payload(db)

        # Gemini call is blocking — push to a worker thread so we don't pin the loop.
        report = await asyncio.to_thread(
            run_watchdog_analysis,
            bundle["payload_text"],
            window_start_iso=bundle["window_start"],
            window_end_iso=bundle["window_end"],
        )

        delivery = await send_watchdog_email(
            report_markdown=report,
            stats=bundle["stats"],
            window_start_iso=bundle["window_start"],
            window_end_iso=bundle["window_end"],
        )

        elapsed_ms = int((datetime.now(timezone.utc) - started_at).total_seconds() * 1000)
        logger.info(
            "[Watchdog] daily cycle complete | elapsed_ms=%d | stats=%s | delivery=%s",
            elapsed_ms, bundle["stats"], delivery.get("status"),
        )

        return {
            "status": "ok",
            "elapsed_ms": elapsed_ms,
            "stats": bundle["stats"],
            "delivery": delivery,
            "window_start": bundle["window_start"],
            "window_end": bundle["window_end"],
        }
    except Exception as e:  # noqa: BLE001
        logger.error(f"[Watchdog] daily cycle FAILED: {e}", exc_info=True)
        return {"status": "error", "error": str(e)}


__all__ = [
    "WATCHDOG_RECIPIENT_EMAIL",
    "fetch_activity_payload",
    "run_watchdog_analysis",
    "send_watchdog_email",
    "run_daily_watchdog_cycle",
]
