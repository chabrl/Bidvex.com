"""
BidVex — Phase 5.3 / Task 3
Admin Conversion-Rate Funnel Dashboard backend.

GET /api/admin/analytics/conversion-funnel

Computes the 4-stage marketplace funnel:
  1. Total Auction Views           (sum of listings.views + multi_item_listings.views)
  2. Total Bid / Proxy Submissions (bids + broker_proxy_authorizations)
  3. Total Partner Binding Matches (broker_binding_requests.status='matched|approved')
  4. Total Settled Transactions    (broker_invoices.status in {paid, settled})

For each step we report:
  - count
  - step_drop_off_pct: % users lost from the PREVIOUS step (1 - n_i/n_{i-1})
  - cumulative_conversion_pct: n_i / n_1 (relative to total views)

Optional query params:
  - days  (int, default 30) — window in days (UTC). Pass 0 for all-time.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Query

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)

conversion_funnel_router = APIRouter(tags=["Admin Analytics"])


def _safe_pct(numer: float, denom: float) -> float:
    if not denom:
        return 0.0
    return round(100.0 * float(numer) / float(denom), 2)


async def _sum_field(db, collection: str, field: str, *, since: Optional[datetime]) -> int:
    """Sum a numeric field across a collection, optionally filtered by created_at >= since."""
    match: dict = {field: {"$exists": True}}
    if since is not None:
        # Some collections store created_at as datetime, some as ISO string.
        match["$or"] = [
            {"created_at": {"$gte": since}},
            {"created_at": {"$gte": since.isoformat()}},
        ]
    pipeline = [
        {"$match": match},
        {"$group": {"_id": None, "total": {"$sum": f"${field}"}}},
    ]
    try:
        cur = db[collection].aggregate(pipeline)
        async for doc in cur:
            return int(doc.get("total") or 0)
    except Exception as exc:
        logger.warning(f"[funnel] _sum_field({collection}.{field}) failed: {exc}")
    return 0


async def _count(db, collection: str, query: dict, *, since: Optional[datetime] = None,
                 date_field: str = "created_at") -> int:
    q = dict(query or {})
    if since is not None:
        q[date_field] = {"$gte": since}
    try:
        return await db[collection].count_documents(q)
    except Exception as exc:
        logger.warning(f"[funnel] count({collection}) failed: {exc}")
        return 0


@conversion_funnel_router.get("/admin/analytics/conversion-funnel")
async def get_conversion_funnel(
    days: int = Query(30, ge=0, le=365, description="Window in days. 0 = all-time"),
    current_user: User = Depends(require_admin),
):
    """Returns the 4-stage funnel + drop-off math, scoped to the window."""
    db = get_db()
    since: Optional[datetime] = None
    if days and days > 0:
        since = datetime.now(timezone.utc) - timedelta(days=days)

    # ── Stage 1: Total auction views (unique impressions) ──────────────
    # `views` is a counter on each listing doc, incremented per public detail-page hit.
    views_single = await _sum_field(db, "listings", "views", since=since)
    views_multi  = await _sum_field(db, "multi_item_listings", "views", since=since)
    total_views = views_single + views_multi

    # ── Stage 2: Total bid + broker proxy authorizations ───────────────
    bids = await _count(db, "bids", {}, since=since)
    proxies = await _count(db, "broker_proxy_authorizations", {}, since=since)
    total_bids_proxies = bids + proxies

    # ── Stage 3: Total partner-binding matches completed ───────────────
    matched_states = ["matched", "approved", "active", "completed", "finalised"]
    binding_matches = await _count(
        db,
        "broker_binding_requests",
        {"status": {"$in": matched_states}},
        since=since,
    )

    # ── Stage 4: Total settled transactions ────────────────────────────
    settled_states = ["paid", "settled", "released", "completed"]
    settled = await _count(
        db,
        "broker_invoices",
        {"status": {"$in": settled_states}},
        since=since,
    )

    # Drop-off math
    steps = [
        {
            "key":      "views",
            "label_en": "Auction Views",
            "label_fr": "Vues d'enchères",
            "count":    total_views,
        },
        {
            "key":      "bids_proxies",
            "label_en": "Bids / Proxy Auth.",
            "label_fr": "Mises / Autor. mandataire",
            "count":    total_bids_proxies,
        },
        {
            "key":      "binding_matches",
            "label_en": "Broker Bindings Matched",
            "label_fr": "Jumelages courtier",
            "count":    binding_matches,
        },
        {
            "key":      "settled",
            "label_en": "Settled Transactions",
            "label_fr": "Transactions réglées",
            "count":    settled,
        },
    ]

    enriched = []
    prev_count: Optional[int] = None
    base_count = steps[0]["count"]
    for s in steps:
        c = s["count"]
        step_drop_off_pct = None if prev_count is None else _safe_pct(prev_count - c, prev_count)
        cumulative_pct = _safe_pct(c, base_count)
        enriched.append({
            **s,
            "step_drop_off_pct":      step_drop_off_pct,
            "cumulative_conversion_pct": cumulative_pct,
        })
        prev_count = c

    return {
        "window_days":      days if days > 0 else None,
        "since":            since.isoformat() if since else None,
        "generated_at":     datetime.now(timezone.utc).isoformat(),
        "steps":            enriched,
        "totals": {
            "views":            total_views,
            "bids_proxies":     total_bids_proxies,
            "binding_matches":  binding_matches,
            "settled":          settled,
            # Overall view → settled conversion
            "overall_conversion_pct": _safe_pct(settled, base_count),
        },
    }
