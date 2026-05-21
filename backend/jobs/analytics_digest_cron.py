"""
BidVex — Phase 5.4 / Task 1
Weekly Conversion-Funnel Digest Cron.

Fires every Monday at 09:00 EST (14:00 UTC) via APScheduler. Computes the
4-stage marketplace funnel for:
  - Last week (today - 7d → today)
  - Two weeks ago (today - 14d → today - 7d)

Queues a single bilingual HTML email into `email_outbox` so the existing
SendGrid drainer ships it to the admin alerts inbox.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


_ADMIN_RECIPIENT_DEFAULT = "charbel911@gmail.com"


def _safe_pct(numer: float, denom: float) -> float:
    """Percent helper that never crashes on zero division."""
    if not denom:
        return 0.0
    return round(100.0 * float(numer) / float(denom), 2)


def _delta_pct(this_week: int, prior_week: int) -> Optional[float]:
    """Growth percentage from prior → this week.

    Returns None when prior_week == 0 *and* this_week == 0 (no traffic at all),
    otherwise:
      - returns +inf-equivalent (rendered as 'New' by the HTML layer) when
        prior_week == 0 but this_week > 0 — we return float('inf') so the
        worker can detect it.
      - returns ((this - prior) / prior) * 100 rounded to 2dp otherwise.
    """
    if prior_week == 0 and this_week == 0:
        return 0.0
    if prior_week == 0:
        return float("inf")
    return round(100.0 * (this_week - prior_week) / float(prior_week), 2)


async def _funnel_for_window(db, since: datetime, until: datetime) -> Dict[str, int]:
    """Aggregate the 4-stage funnel between `since` and `until`. Both UTC-aware."""
    iso_since = since.isoformat()
    iso_until = until.isoformat()

    def _date_match(field: str = "created_at") -> Dict[str, Any]:
        return {"$or": [
            {field: {"$gte": since, "$lt": until}},
            {field: {"$gte": iso_since, "$lt": iso_until}},
        ]}

    async def _sum_views(collection: str) -> int:
        pipeline = [
            {"$match": {**_date_match(), "views": {"$exists": True}}},
            {"$group": {"_id": None, "total": {"$sum": "$views"}}},
        ]
        try:
            cur = db[collection].aggregate(pipeline)
            async for doc in cur:
                return int(doc.get("total") or 0)
        except Exception as exc:
            logger.warning(f"[digest] views sum failed for {collection}: {exc}")
        return 0

    async def _count(collection: str, query: Dict[str, Any]) -> int:
        q = {**(query or {}), **_date_match()}
        try:
            return await db[collection].count_documents(q)
        except Exception as exc:
            logger.warning(f"[digest] count failed for {collection}: {exc}")
            return 0

    views = (await _sum_views("listings")) + (await _sum_views("multi_item_listings"))
    bids_proxies = (
        await _count("bids", {}) +
        await _count("broker_proxy_authorizations", {})
    )
    binding_matches = await _count(
        "broker_binding_requests",
        {"status": {"$in": ["matched", "approved", "active", "completed", "finalised"]}},
    )
    settled = await _count(
        "broker_invoices",
        {"status": {"$in": ["paid", "settled", "released", "completed"]}},
    )
    return {
        "views":           views,
        "bids_proxies":    bids_proxies,
        "binding_matches": binding_matches,
        "settled":         settled,
    }


def _render_digest_rows(this_week: Dict[str, int], prior_week: Dict[str, int]) -> list[dict]:
    """Build the 4 comparison rows used by the HTML template."""
    keys = [
        ("views",           "Auction Views",            "Vues d'enchères"),
        ("bids_proxies",    "Bids / Proxy Auth.",       "Mises / Autor. mandataire"),
        ("binding_matches", "Broker Bindings Matched",  "Jumelages courtier"),
        ("settled",         "Settled Transactions",     "Transactions réglées"),
    ]
    rows = []
    for k, label_en, label_fr in keys:
        a = this_week.get(k, 0)
        b = prior_week.get(k, 0)
        d = _delta_pct(a, b)
        rows.append({
            "key":       k,
            "label_en":  label_en,
            "label_fr":  label_fr,
            "this_week": a,
            "prior_week": b,
            "delta_pct": d,    # None / float / float('inf')
        })
    return rows


def _format_delta_html(delta: Optional[float]) -> str:
    """Render the delta column safely as HTML."""
    if delta is None:
        return '<span style="color:#94A3B8;">&mdash;</span>'
    if delta == float("inf"):
        return '<span style="color:#10B981;font-weight:700;">&uarr; New</span>'
    if delta > 0:
        return f'<span style="color:#10B981;font-weight:700;">&uarr; +{delta:.1f}%</span>'
    if delta < 0:
        return f'<span style="color:#E11D48;font-weight:700;">&darr; {delta:.1f}%</span>'
    return '<span style="color:#64748B;">&plusmn; 0%</span>'


def _render_digest_html(*, this_week: Dict[str, int], prior_week: Dict[str, int],
                          rows: list[dict],
                          since_this: datetime, until_this: datetime,
                          since_prior: datetime, until_prior: datetime) -> str:
    """Build the HTML body for the weekly digest email using the same
    branded layout as the rest of the v9 / Phase 5.3 fallback templates."""
    BRAND_NAVY     = "#0B2545"
    BRAND_CYAN     = "#3FB4CB"
    BRAND_BUTTON   = "#2186C6"
    BRAND_BG       = "#F0F4F8"
    BRAND_TEXT     = "#1E293B"
    BRAND_MUTED    = "#64748B"
    LOGO_TOP       = ("http://cdn.mcauto-images-production.sendgrid.net/"
                       "4fbf02710175d39f/9dc6a7c3-8237-4a66-b82b-0d9abc165b44/4500x1080.png")
    LOGO_FOOTER    = ("http://cdn.mcauto-images-production.sendgrid.net/"
                       "4fbf02710175d39f/31636d5f-c160-446b-b715-bcf542e9607e/4500x1080.png")
    FONT_STACK     = "'Helvetica Neue', Helvetica, Arial, sans-serif"
    current_year   = datetime.now().year
    fmt_date = lambda d: d.strftime("%b %d, %Y")
    overall_pct = _safe_pct(this_week.get("settled", 0), this_week.get("views", 0))
    overall_pct_prior = _safe_pct(prior_week.get("settled", 0), prior_week.get("views", 0))

    table_rows = ""
    for r in rows:
        table_rows += f"""
              <tr>
                <td style="padding:10px 12px;border-bottom:1px solid #E2E8F0;font-family:{FONT_STACK};font-size:13px;color:{BRAND_TEXT};">
                  <strong>{r['label_en']}</strong><br/>
                  <span style="color:{BRAND_MUTED};font-size:11px;">{r['label_fr']}</span>
                </td>
                <td style="padding:10px 12px;border-bottom:1px solid #E2E8F0;font-family:{FONT_STACK};font-size:14px;color:{BRAND_TEXT};text-align:right;font-weight:700;">{r['this_week']:,}</td>
                <td style="padding:10px 12px;border-bottom:1px solid #E2E8F0;font-family:{FONT_STACK};font-size:14px;color:{BRAND_MUTED};text-align:right;">{r['prior_week']:,}</td>
                <td style="padding:10px 12px;border-bottom:1px solid #E2E8F0;font-family:{FONT_STACK};font-size:13px;text-align:right;">{_format_delta_html(r['delta_pct'])}</td>
              </tr>"""

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>@media (max-width:600px){{.outer-table{{width:100%!important}}.body-cell{{padding:24px 16px!important}}h1{{font-size:20px!important}}}}</style>
</head><body style="margin:0;padding:0;background-color:{BRAND_BG};font-family:{FONT_STACK};">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:{BRAND_BG};padding:24px 12px;">
<tr><td align="center">
<table class="outer-table" width="640" cellpadding="0" cellspacing="0" style="background-color:#FFFFFF;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,0.06);">
  <tr>
    <td style="background-color:{BRAND_NAVY};padding:24px 0;text-align:center;border-bottom:3px solid {BRAND_CYAN};">
      <img src="{LOGO_TOP}" alt="BidVex" width="150" style="display:inline-block;width:150px;height:auto;" />
    </td>
  </tr>
  <tr>
    <td style="background-color:{BRAND_NAVY};padding:28px 30px;text-align:center;">
      <p style="margin:0 0 4px;font-size:36px;line-height:1;">&#128202;</p>
      <h1 style="margin:0;font-family:{FONT_STACK};font-size:22px;font-weight:bold;color:#FFFFFF;">Weekly Conversion Funnel Digest</h1>
      <p style="margin:6px 0 0;font-family:{FONT_STACK};font-size:14px;color:rgba(255,255,255,0.7);">Bilan hebdomadaire de l'entonnoir de conversion</p>
      <p style="margin:6px 0 0;font-family:{FONT_STACK};font-size:13px;color:rgba(255,255,255,0.85);">
        {fmt_date(since_this)} &mdash; {fmt_date(until_this)} <span style="color:rgba(255,255,255,0.5);">vs</span> {fmt_date(since_prior)} &mdash; {fmt_date(until_prior)}
      </p>
    </td>
  </tr>
  <tr>
    <td class="body-cell" style="padding:28px 30px;">
      <p style="margin:0 0 8px;font-size:11px;text-transform:uppercase;letter-spacing:1.5px;color:{BRAND_BUTTON};font-weight:700;font-family:{FONT_STACK};">FUNNEL COMPARISON / COMPARAISON DE L'ENTONNOIR</p>
      <table width="100%" cellpadding="0" cellspacing="0" style="margin-bottom:24px;border:1px solid #E2E8F0;border-radius:8px;overflow:hidden;">
        <tr style="background:#F8FAFC;">
          <th style="padding:10px 12px;text-align:left;font-family:{FONT_STACK};font-size:11px;text-transform:uppercase;letter-spacing:1px;color:{BRAND_MUTED};">Stage</th>
          <th style="padding:10px 12px;text-align:right;font-family:{FONT_STACK};font-size:11px;text-transform:uppercase;letter-spacing:1px;color:{BRAND_MUTED};">This week</th>
          <th style="padding:10px 12px;text-align:right;font-family:{FONT_STACK};font-size:11px;text-transform:uppercase;letter-spacing:1px;color:{BRAND_MUTED};">Prior week</th>
          <th style="padding:10px 12px;text-align:right;font-family:{FONT_STACK};font-size:11px;text-transform:uppercase;letter-spacing:1px;color:{BRAND_MUTED};">&Delta;</th>
        </tr>{table_rows}
      </table>

      <table width="100%" cellpadding="0" cellspacing="0" style="background:#F0F8FF;border-left:4px solid {BRAND_BUTTON};border-radius:6px;margin-bottom:18px;">
        <tr>
          <td style="padding:14px 16px;font-family:{FONT_STACK};font-size:13px;color:{BRAND_NAVY};line-height:1.5;">
            <strong>Overall view &rarr; settled conversion:</strong>
            <span style="font-weight:700;color:{BRAND_BUTTON};">{overall_pct:.2f}%</span>
            <span style="color:{BRAND_MUTED};font-size:11px;">&nbsp;(prior week: {overall_pct_prior:.2f}%)</span>
          </td>
        </tr>
      </table>

      <p style="margin:0 0 8px;font-family:{FONT_STACK};font-size:13px;color:{BRAND_TEXT};line-height:1.5;">
        Open the dashboard for the live cohort &amp; per-stage charts.
      </p>

      <table cellpadding="0" cellspacing="0" align="left" style="margin-top:8px;">
        <tr>
          <td style="background-color:{BRAND_BUTTON};border-radius:8px;padding:12px 24px;">
            <a href="https://bidvex.com/admin?tab=conversion-funnel" style="color:#FFFFFF;font-family:{FONT_STACK};font-size:13px;font-weight:bold;text-decoration:none;display:inline-block;" target="_blank">Open Live Dashboard &rarr;</a>
          </td>
        </tr>
      </table>

      <p style="margin:24px 0 0;font-family:{FONT_STACK};font-size:11px;color:{BRAND_MUTED};line-height:1.5;">
        Generated automatically every Monday at 09:00 EST. To stop these digests, unsubscribe in Admin &rarr; Settings.
        <br/>Généré automatiquement chaque lundi à 09 h 00 EST. Pour ne plus recevoir, désabonnez-vous dans Admin &rarr; Paramètres.
      </p>
    </td>
  </tr>
  <tr>
    <td style="background-color:{BRAND_NAVY};padding:24px 30px;text-align:center;">
      <img src="{LOGO_FOOTER}" alt="BidVex" width="80" style="display:inline-block;width:80px;height:auto;opacity:0.7;margin-bottom:10px;" /><br/>
      <p style="margin:0 0 4px;font-family:{FONT_STACK};font-size:11px;color:rgba(255,255,255,0.6);">BidVex Canada | Sherbrooke, QC</p>
      <p style="margin:0;font-family:{FONT_STACK};font-size:10px;color:rgba(255,255,255,0.3);">&copy; {current_year} BidVex Inc.</p>
    </td>
  </tr>
</table>
</td></tr></table></body></html>"""


async def queue_weekly_funnel_digest(db) -> Dict[str, Any]:
    """Compute the 7-day vs 7-day-prior funnel and queue ONE digest email
    into `email_outbox` for the admin alerts mailbox.

    Idempotent within the day: if a row for today has already been queued
    we skip (so multiple invocations don't spam admins).

    Returns a dict {queued: bool, reason, this_week, prior_week, rows}.
    """
    now = datetime.now(timezone.utc)
    today = now.date()
    # Skip if a digest already queued today
    try:
        existing = await db.email_outbox.find_one(
            {"kind": "weekly_funnel_digest", "context.run_date": today.isoformat()},
            {"_id": 0, "id": 1},
        )
        if existing:
            return {"queued": False, "reason": "already_queued_today", "row_id": existing.get("id")}
    except Exception:
        pass

    since_this = datetime.combine(today - timedelta(days=7), datetime.min.time(), tzinfo=timezone.utc)
    until_this = datetime.combine(today,                       datetime.min.time(), tzinfo=timezone.utc)
    since_prior = datetime.combine(today - timedelta(days=14), datetime.min.time(), tzinfo=timezone.utc)
    until_prior = since_this

    this_week  = await _funnel_for_window(db, since_this,  until_this)
    prior_week = await _funnel_for_window(db, since_prior, until_prior)

    rows = _render_digest_rows(this_week, prior_week)
    html = _render_digest_html(
        this_week=this_week, prior_week=prior_week, rows=rows,
        since_this=since_this, until_this=until_this,
        since_prior=since_prior, until_prior=until_prior,
    )

    recipient = os.environ.get("ADMIN_DIGEST_RECIPIENT", _ADMIN_RECIPIENT_DEFAULT)
    subject = f"[BidVex] Weekly Funnel Digest — {since_this.strftime('%b %d')} → {until_this.strftime('%b %d, %Y')}"

    row = {
        "id":         str(uuid.uuid4()),
        "kind":       "weekly_funnel_digest",
        "to_email":   recipient,
        "subject":    subject,
        "html":       html,
        "context": {
            "run_date":   today.isoformat(),
            "this_week":  this_week,
            "prior_week": prior_week,
            "rows":       [{**r, "delta_pct_is_infinite": (r["delta_pct"] == float("inf"))} for r in rows],
            "since_this": since_this.isoformat(),
            "until_this": until_this.isoformat(),
            "since_prior": since_prior.isoformat(),
            "until_prior": until_prior.isoformat(),
        },
        "queued_at":  now,
    }
    # JSON-safe: drop float('inf') from delta_pct fields (Mongo BSON can't store inf)
    for r in row["context"]["rows"]:
        if r.get("delta_pct") == float("inf"):
            r["delta_pct"] = None
    try:
        await db.email_outbox.insert_one(row)
    except Exception as exc:
        logger.error(f"[digest] email_outbox.insert_one failed: {exc}", exc_info=True)
        return {"queued": False, "reason": f"insert_failed:{exc}"}

    logger.info(
        f"[digest] queued weekly funnel digest run_date={today.isoformat()} "
        f"this={this_week} prior={prior_week} recipient={recipient}"
    )
    return {
        "queued":     True,
        "row_id":     row["id"],
        "recipient":  recipient,
        "this_week":  this_week,
        "prior_week": prior_week,
        "rows":       rows,
    }
