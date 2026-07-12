"""iter346 P0 — Weekly Impersonation Compliance Digest.

Runs every Monday at 09:00 America/Toronto (13:00 UTC in winter, 13:00 in
summer via TZ-aware CronTrigger) and emails the compliance officer a
summary of every admin impersonation session from the previous 7 days.

Recipient: env `COMPLIANCE_OFFICER_EMAIL` — falls back to
`charbel911@gmail.com` (the platform super_admin) so the digest is never
silently dropped after an env misconfig.

Bilingual: primary English body + a French summary section at the bottom
for Quebec compliance requirements.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


DIGEST_SUBJECT = "BidVex Weekly Impersonation Audit — Week of {week_label}"


def _fmt_dt(iso: str | None) -> str:
    if not iso:
        return "—"
    try:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        return dt.strftime("%Y-%m-%d %H:%M UTC")
    except Exception:  # noqa: BLE001
        return str(iso)[:19]


def _build_html(sessions: List[Dict[str, Any]], week_start: datetime, week_end: datetime) -> str:
    total = len(sessions)
    long_sessions = [s for s in sessions if (s.get("duration_minutes") or 0) > 30]

    rows_html = ""
    for s in sessions:
        dur = s.get("duration_minutes")
        flag = " 🚨" if (dur or 0) > 30 else ""
        rows_html += (
            f"<tr>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{_fmt_dt(s.get('started_at'))}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{s.get('admin_email') or s.get('admin_id') or '—'}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee'>{s.get('target_email') or s.get('target_user_id') or '—'}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;text-align:right'>{dur if dur is not None else '—'}{flag}</td>"
            f"<td style='padding:6px 10px;border-bottom:1px solid #eee;text-align:right'>{s.get('actions_count', 0)}</td>"
            f"</tr>"
        )

    if not rows_html:
        rows_html = (
            "<tr><td colspan='5' style='padding:24px;text-align:center;color:#888;font-style:italic'>"
            "No impersonation sessions in this reporting window."
            "</td></tr>"
        )

    return f"""
<!doctype html>
<html><body style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;color:#111">
  <div style="max-width:720px;margin:24px auto;padding:24px;background:#fff">
    <h1 style="color:#0B2545;margin:0 0 4px 0;font-size:22px">BidVex Weekly Impersonation Audit</h1>
    <p style="margin:0 0 24px 0;color:#666;font-size:14px">
      Reporting window: {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')} (UTC)
    </p>

    <div style="display:flex;gap:12px;margin:20px 0">
      <div style="flex:1;padding:14px;background:#F5F8FB;border-radius:8px">
        <div style="font-size:12px;color:#666">Total sessions</div>
        <div style="font-size:26px;font-weight:600;color:#0B2545">{total}</div>
      </div>
      <div style="flex:1;padding:14px;background:{'#FFF3E0' if long_sessions else '#F5F8FB'};border-radius:8px">
        <div style="font-size:12px;color:#666">Sessions &gt; 30 min</div>
        <div style="font-size:26px;font-weight:600;color:{'#B45309' if long_sessions else '#0B2545'}">{len(long_sessions)}</div>
      </div>
    </div>

    <table style="width:100%;border-collapse:collapse;font-size:13px;margin-top:16px">
      <thead>
        <tr style="background:#0B2545;color:#fff">
          <th style="padding:8px 10px;text-align:left">Started (UTC)</th>
          <th style="padding:8px 10px;text-align:left">Admin</th>
          <th style="padding:8px 10px;text-align:left">Target</th>
          <th style="padding:8px 10px;text-align:right">Duration (min)</th>
          <th style="padding:8px 10px;text-align:right">Actions</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>

    <hr style="border:none;border-top:1px solid #eee;margin:32px 0"/>

    <h2 style="color:#0B2545;font-size:16px;margin:0 0 8px 0">Résumé en français</h2>
    <p style="margin:0;color:#333;font-size:13px;line-height:1.5">
      Période du {week_start.strftime('%Y-%m-%d')} au {week_end.strftime('%Y-%m-%d')} (UTC).
      Nombre total de sessions d'impersonation par les administrateurs&nbsp;: <b>{total}</b>.
      Sessions dépassant 30&nbsp;minutes&nbsp;: <b>{len(long_sessions)}</b>.
      Le tableau ci-dessus présente la liste complète des sessions —
      chaque ligne indique la date de début, l'administrateur ayant
      impersonifié, l'utilisateur ciblé, la durée en minutes et le nombre
      d'actions journalisées durant la session. Les sessions dépassant
      30&nbsp;minutes sont marquées d'une alerte (🚨) pour révision.
    </p>

    <p style="margin:24px 0 0 0;color:#999;font-size:11px">
      Auto-generated by BidVex compliance scheduler. To change the
      recipient, set the <code>COMPLIANCE_OFFICER_EMAIL</code> environment
      variable. Digests are dispatched every Monday at 09:00
      America/Toronto.
    </p>
  </div>
</body></html>
"""


async def weekly_impersonation_digest_job() -> Dict[str, Any]:
    """APScheduler entry-point — runs every Monday at 09:00 America/Toronto.

    Idempotent: if the job runs twice within the same 7-day window, both
    runs will send. We accept this trade-off (rather than persisting a
    "last-sent-at" gate) because the digest is small (~5-10 rows/week)
    and duplicate delivery in the compliance mailbox is preferable to
    missed delivery when the scheduler restarts on a fresh pod.
    """
    from services.emails._email_core import send_email

    try:
        from server import get_database as _get_db
        db = _get_db()
    except Exception:  # noqa: BLE001
        # Fallback: try the shared module accessor.
        from deps import get_db as _get_db2
        db = _get_db2()

    now = datetime.now(timezone.utc)
    week_start = now - timedelta(days=7)
    query = {
        "action": "impersonation_started",
        "timestamp": {"$gte": week_start.isoformat(), "$lte": now.isoformat()},
    }
    starts = await db.admin_logs.find(query, {"_id": 0}).sort("timestamp", -1).to_list(500)

    # Materialize per-session summaries (same shape as the /admin/impersonation-history endpoint).
    sessions: List[Dict[str, Any]] = []
    for row in starts:
        started_at = row.get("timestamp")
        details = row.get("details") or {}
        expires_at = details.get("expires_at")
        try:
            start_dt = datetime.fromisoformat(started_at.replace("Z", "+00:00")) if started_at else None
            expires_dt = datetime.fromisoformat(expires_at.replace("Z", "+00:00")) if expires_at else None
        except Exception:  # noqa: BLE001
            start_dt = expires_dt = None
        ended_at_dt = min(expires_dt, now) if expires_dt else None
        duration_minutes = None
        if start_dt and ended_at_dt:
            duration_minutes = round((ended_at_dt - start_dt).total_seconds() / 60.0, 2)

        # Count actions within the session window.
        actions_count = 0
        if started_at and expires_at:
            actions_count = await db.admin_logs.count_documents({
                "action":         {"$ne": "impersonation_started"},
                "admin_id":       row.get("admin_id"),
                "target_user_id": row.get("target_user_id"),
                "timestamp":      {"$gt": started_at, "$lte": expires_at},
            })

        sessions.append({
            "admin_id":         row.get("admin_id"),
            "admin_email":      row.get("admin_email"),
            "target_user_id":   row.get("target_user_id"),
            "target_email":     row.get("target_email"),
            "started_at":       started_at,
            "expires_at":       expires_at,
            "duration_minutes": duration_minutes,
            "actions_count":    actions_count,
        })

    recipient = (
        os.environ.get("COMPLIANCE_OFFICER_EMAIL")
        or os.environ.get("ADMIN_EMAIL")
        or "charbel911@gmail.com"
    )
    subject = DIGEST_SUBJECT.format(week_label=week_start.strftime("%Y-%m-%d"))
    html = _build_html(sessions, week_start, now)

    try:
        await send_email(recipient, subject, html)
        logger.info(
            f"[compliance-digest] SENT to {recipient} — {len(sessions)} sessions, "
            f"window={week_start.date()}→{now.date()}"
        )
        return {"status": "sent", "recipient": recipient, "sessions": len(sessions)}
    except Exception as e:  # noqa: BLE001
        logger.error(f"[compliance-digest] send failed: {e}")
        return {"status": "failed", "error": str(e)}
