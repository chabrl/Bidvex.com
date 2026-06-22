"""
iter310 — Admin Unsubscribe Audit Trail
======================================
Surfaces the `unsubscribe_events` collection (written by every successful
unsubscribe attempt in routes/unsubscribe.py + routes/external_campaigns.py)
to admins for deliverability monitoring.

Endpoints (all `require_admin`):
  GET /api/admin/unsubscribe-audit
      → Paginated list, filterable by date range + campaign_id.
      Response:
        {
          "count":   <total>,
          "page":    <1-indexed>,
          "per_page": <int>,
          "events":  [{ id, email_masked, campaign_id, campaign_name,
                        source, unsubscribed_at, token_type, lang, event }],
          "summary": { last_7_days, last_30_days, today }
        }
  GET /api/admin/unsubscribe-audit/summary
      → Lightweight daily counts only (last 7 / 30 days), used by the
      admin dashboard pill so the spike-detection UI can render without
      pulling the full list.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query

from deps import get_db, require_admin, User


admin_unsubscribe_audit_router = APIRouter(tags=["Admin Unsubscribe Audit"])


def _mask_email(email: str) -> str:
    """Show first 3 chars + domain — e.g. 'cha***@gmail.com'."""
    if not email or "@" not in email:
        return "***"
    local, _, domain = email.partition("@")
    if len(local) <= 3:
        return f"{local}***@{domain}"
    return f"{local[:3]}***@{domain}"


def _iso(dt):
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc).isoformat()
    return dt


@admin_unsubscribe_audit_router.get("/admin/unsubscribe-audit/summary")
async def admin_unsubscribe_summary(
    current_user: User = Depends(require_admin),
):
    """Aggregated counts for the early-warning dashboard pill."""
    db = get_db()
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    last_7 = now - timedelta(days=7)
    last_30 = now - timedelta(days=30)

    # Single $facet so we hit the index once.
    pipeline = [
        {"$match": {"unsubscribed_at": {"$gte": last_30}, "event": "unsubscribed"}},
        {
            "$facet": {
                "today":   [{"$match": {"unsubscribed_at": {"$gte": today_start}}},
                            {"$count": "n"}],
                "last_7":  [{"$match": {"unsubscribed_at": {"$gte": last_7}}},
                            {"$count": "n"}],
                "last_30": [{"$count": "n"}],
                "by_day": [
                    {
                        "$group": {
                            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$unsubscribed_at"}},
                            "count": {"$sum": 1},
                        }
                    },
                    {"$sort": {"_id": 1}},
                ],
                "by_source": [
                    {"$group": {"_id": "$source", "count": {"$sum": 1}}},
                ],
            }
        },
    ]
    docs = await db.unsubscribe_events.aggregate(pipeline).to_list(1)
    facets = docs[0] if docs else {}

    def _first_count(arr):
        return arr[0]["n"] if arr else 0

    return {
        "today":     _first_count(facets.get("today", [])),
        "last_7":    _first_count(facets.get("last_7", [])),
        "last_30":   _first_count(facets.get("last_30", [])),
        "by_day":    [{"date": d["_id"], "count": d["count"]} for d in facets.get("by_day", [])],
        "by_source": [{"source": d["_id"], "count": d["count"]} for d in facets.get("by_source", [])],
        "generated_at": now.isoformat(),
    }


@admin_unsubscribe_audit_router.get("/admin/unsubscribe-audit")
async def admin_list_unsubscribe_audit(
    start_date: Optional[str] = Query(None, description="ISO-8601 lower bound (inclusive)"),
    end_date: Optional[str] = Query(None, description="ISO-8601 upper bound (exclusive)"),
    campaign_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None, description="platform | external_campaign"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    current_user: User = Depends(require_admin),
):
    """Paginated audit list, joined with campaign name when applicable."""
    db = get_db()
    q: dict = {"event": "unsubscribed"}

    if start_date:
        try:
            q.setdefault("unsubscribed_at", {})["$gte"] = datetime.fromisoformat(start_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    if end_date:
        try:
            q.setdefault("unsubscribed_at", {})["$lt"] = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        except ValueError:
            pass
    if campaign_id:
        q["campaign_id"] = campaign_id
    if source in ("platform", "external_campaign"):
        q["source"] = source

    skip = (page - 1) * per_page
    cursor = db.unsubscribe_events.find(q, {"_id": 0}).sort("unsubscribed_at", -1).skip(skip).limit(per_page)
    rows = await cursor.to_list(per_page)
    total = await db.unsubscribe_events.count_documents(q)

    # Enrich with campaign name (single batch lookup).
    campaign_ids = list({r.get("campaign_id") for r in rows if r.get("campaign_id")})
    name_map: dict = {}
    if campaign_ids:
        async for c in db.external_email_campaigns.find(
            {"id": {"$in": campaign_ids}}, {"_id": 0, "id": 1, "name": 1}
        ):
            name_map[c["id"]] = c.get("name")

    events = []
    for r in rows:
        events.append({
            "id":              r.get("id"),
            "email_masked":    _mask_email(r.get("email") or ""),
            "campaign_id":     r.get("campaign_id"),
            "campaign_name":   name_map.get(r.get("campaign_id")) if r.get("campaign_id") else None,
            "source":          r.get("source"),
            "unsubscribed_at": _iso(r.get("unsubscribed_at")),
            "token_type":      r.get("token_type"),
            "lang":            r.get("lang") or "en",
            "event":           r.get("event"),
        })

    return {
        "count":    total,
        "page":     page,
        "per_page": per_page,
        "events":   events,
    }


__all__ = ["admin_unsubscribe_audit_router"]
