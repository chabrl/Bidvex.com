"""iter391 — Nightly base64-in-Mongo dry-run sweep + admin alert.

Registered from `server.py` on the app-startup scheduler at 04:00 UTC.
NEVER migrates automatically — only runs the existing scanner in
dry-run mode and, if ANY base64 image entry is still hiding in
`listings`, `multi_item_listings`, `vehicle_listings`, or
`storage_auctions`, sends a per-collection alert email to
`ADMIN_ALERT_EMAIL` (falls back to `charbel911@gmail.com`).

Contract:
    async def run_nightly_base64_sweep_alert(db) -> dict

Returns the same shape as `scan_collections()` plus:
    {"email_sent": bool, "alert_triggered": bool, "recipient": str}
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict

from scripts.migrate_base64_images_to_s3 import scan_collections
from services.email_service import send_html_email

logger = logging.getLogger(__name__)


# ── Config ────────────────────────────────────────────────────────────
def _admin_recipient() -> str:
    """Pick the alert recipient with sane fallbacks."""
    return (
        os.environ.get("BASE64_SWEEP_ALERT_EMAIL")
        or os.environ.get("ADMIN_ALERT_EMAIL")
        or os.environ.get("ADMIN_EMAIL")
        or "charbel911@gmail.com"
    )


def _env_label() -> str:
    """Best-effort env identifier so the subject line tells prod vs preview."""
    fu = os.environ.get("FRONTEND_URL", "")
    if not fu:
        return "unknown"
    if "prod-verify" in fu or "preview" in fu:
        return "preview"
    if "launchapp-4-r" in fu or "bidvex.com" in fu:
        return "production"
    return fu.replace("https://", "").split("/")[0]


# ── HTML report body ─────────────────────────────────────────────────
def _build_alert_html(report: Dict[str, Any], run_ts_utc: str) -> str:
    """Render a per-collection HTML table + a one-line CTA the on-call
    engineer can copy-paste to run the actual migration."""
    per_coll = report.get("per_collection") or {}
    totals   = report.get("totals") or {}

    # Build one row per collection. Highlight anything with found > 0 in red.
    rows_html_parts = []
    for coll_name, s in per_coll.items():
        found = int(s.get("found") or 0)
        row_bg = "#fef2f2" if found > 0 else "#f8fafc"
        row_border = "#ef4444" if found > 0 else "#e2e8f0"
        rows_html_parts.append(
            f'<tr style="background:{row_bg};border-left:4px solid {row_border};">'
            f'  <td style="padding:10px 14px;font-weight:600;">{coll_name}</td>'
            f'  <td style="padding:10px 14px;text-align:right;">{s.get("docs",0):,}</td>'
            f'  <td style="padding:10px 14px;text-align:right;">{s.get("docs_with_base64",0):,}</td>'
            f'  <td style="padding:10px 14px;text-align:right;font-weight:700;color:{"#dc2626" if found>0 else "#0f172a"};">{found:,}</td>'
            f'  <td style="padding:10px 14px;text-align:right;color:#475569;">{s.get("skipped",0):,}</td>'
            f'</tr>'
        )
    rows_html = "\n".join(rows_html_parts)

    grand_found = int(totals.get("found") or 0)
    grand_docs  = int(totals.get("docs")  or 0)

    return f"""
<!doctype html>
<html><head><meta charset="utf-8"></head>
<body style="margin:0;padding:24px;background:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;color:#0f172a;">
  <div style="max-width:640px;margin:0 auto;background:#ffffff;border-radius:12px;padding:28px;box-shadow:0 2px 8px rgba(0,0,0,0.06);">
    <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
      <span style="background:#dc2626;color:#fff;font-size:11px;font-weight:700;padding:3px 10px;border-radius:999px;letter-spacing:0.6px;text-transform:uppercase;">Alert</span>
      <span style="color:#64748b;font-size:12px;">BidVex · {_env_label()} · {run_ts_utc}</span>
    </div>
    <h1 style="margin:0 0 6px 0;font-size:20px;line-height:1.3;">Base64 image entries detected — <strong style="color:#dc2626;">{grand_found:,}</strong> found</h1>
    <p style="margin:0 0 20px 0;color:#475569;font-size:14px;line-height:1.55;">
      The nightly dry-run sweep across {grand_docs:,} listing docs found <strong>{grand_found:,}</strong>
      image entries still stored as base64 in MongoDB instead of S3 URLs. No migration was performed —
      this is an alert only. Review the per-collection counts below and run the migration script
      manually when you're ready.
    </p>

    <table style="width:100%;border-collapse:collapse;font-size:13px;margin-bottom:20px;background:#ffffff;border:1px solid #e2e8f0;border-radius:8px;overflow:hidden;">
      <thead>
        <tr style="background:#0f172a;color:#ffffff;">
          <th style="padding:10px 14px;text-align:left;font-weight:600;">Collection</th>
          <th style="padding:10px 14px;text-align:right;font-weight:600;">Docs scanned</th>
          <th style="padding:10px 14px;text-align:right;font-weight:600;">Docs w/ base64</th>
          <th style="padding:10px 14px;text-align:right;font-weight:600;">Base64 entries</th>
          <th style="padding:10px 14px;text-align:right;font-weight:600;">Already URL</th>
        </tr>
      </thead>
      <tbody>
        {rows_html}
      </tbody>
    </table>

    <div style="background:#0f172a;color:#e2e8f0;padding:14px 16px;border-radius:8px;font-family:'SF Mono',Menlo,Consolas,monospace;font-size:12.5px;line-height:1.6;">
      <div style="color:#94a3b8;margin-bottom:6px;font-size:11px;text-transform:uppercase;letter-spacing:0.6px;">Manual migration command</div>
      cd /app/backend<br>
      python -m scripts.migrate_base64_images_to_s3 --dry-run<br>
      python -m scripts.migrate_base64_images_to_s3
    </div>

    <p style="margin:22px 0 0 0;color:#94a3b8;font-size:11.5px;line-height:1.55;">
      Sent by the iter391 nightly base64 sweep job (04:00 UTC). Alerts fire only when
      the total <em>base64 entries found</em> is greater than zero — a silent night means everything is on S3.
    </p>
  </div>
</body></html>
"""


# ── Entry point wired into APScheduler ───────────────────────────────
async def run_nightly_base64_sweep_alert(db) -> Dict[str, Any]:
    """Run the dry-run scan, alert if any base64 remains. Never migrates."""
    run_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    recipient = _admin_recipient()

    logger.info("[base64_sweep_alert] starting nightly dry-run scan (recipient=%s)", recipient)

    # Always dry-run — the whole point of the job is a non-mutating alert.
    report = await scan_collections(db, dry_run=True)

    total_found = int((report.get("totals") or {}).get("found") or 0)
    per_coll_summary = {
        name: int((s or {}).get("found") or 0)
        for name, s in (report.get("per_collection") or {}).items()
    }

    logger.info(
        "[base64_sweep_alert] scan complete: total_found=%d per_collection=%s",
        total_found, per_coll_summary,
    )

    email_sent = False
    alert_triggered = total_found > 0
    if alert_triggered:
        try:
            html = _build_alert_html(report, run_ts)
            subject = f"[BidVex · {_env_label()}] Base64 images still in MongoDB — {total_found:,} entries"
            email_sent = await send_html_email(
                to_email=recipient,
                to_name="BidVex Admin",
                subject=subject,
                html_content=html,
                is_marketing=False,
            )
            logger.info(
                "[base64_sweep_alert] admin email dispatched (sent=%s recipient=%s total=%d)",
                email_sent, recipient, total_found,
            )
        except Exception as e:  # noqa: BLE001
            logger.exception("[base64_sweep_alert] email send failed: %s", e)
            email_sent = False
    else:
        logger.info("[base64_sweep_alert] no base64 entries found — no alert sent")

    return {
        **report,
        "run_ts_utc":       run_ts,
        "recipient":        recipient,
        "alert_triggered":  alert_triggered,
        "email_sent":       email_sent,
    }
