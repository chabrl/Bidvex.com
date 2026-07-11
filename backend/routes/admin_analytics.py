"""
routes/admin_analytics.py — iter299 P2

Advanced Analytics for the Admin panel. Single payload, computed
on-demand from the existing MongoDB collections (no new data
structures, no caches to maintain).

GET /api/admin/analytics   (admin-only)
"""
from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)
analytics_router = APIRouter(prefix="/admin/analytics", tags=["admin-analytics"])

_SOLD_UNION = ["sold", "ended", "completed"]
_ENDED_UNION = ["sold", "ended", "expired", "completed", "ended_no_sale", "unsold", "no_sale"]


@analytics_router.post("/top-sellers/recalculate")
async def trigger_top_seller_recalc(admin: User = Depends(require_admin)):
    """iter300 — manually trigger the nightly Top Seller badge job."""
    db = get_db()
    from services.top_sellers import recalculate_top_sellers
    return await recalculate_top_sellers(db)


def _parse_dt(v) -> Optional[datetime]:
    if not v:
        return None
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    try:
        dt = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:  # noqa: BLE001
        return None


def _is_sold(doc: Dict[str, Any]) -> bool:
    if doc.get("status") == "sold":
        return True
    return doc.get("status") in ("ended", "completed") and bool(
        doc.get("winner_user_id") or doc.get("winner_id") or doc.get("winning_bidder_id")
    )


def _hammer(doc: Dict[str, Any]) -> float:
    return float(doc.get("final_price") or doc.get("current_price")
                 or doc.get("current_bid") or 0)


def _day(dt: Optional[datetime]) -> Optional[str]:
    return dt.strftime("%Y-%m-%d") if dt else None


@analytics_router.get("/overview")
async def get_admin_analytics(
    admin: User = Depends(require_admin),
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
):
    db = get_db()
    now = datetime.now(timezone.utc)

    # ── iter301 P2 — 60-second response cache (range-keyed).
    from services.api_cache import cache_get, cache_set
    _cache_key = f"admin_analytics:overview:{from_date or 'default'}:{to_date or 'default'}"
    _cached = await cache_get(_cache_key)
    if _cached:
        return _cached

    # ── iter300 P2 — optional custom date range (?from=YYYY-MM-DD&to=YYYY-MM-DD).
    # Defaults to the last 30 days. Range-scoped metrics: GMV(range),
    # revenue(range + per-day series), signups series, top sellers, avg
    # hammer, conversion. All-time KPIs are always included alongside.
    range_to = _parse_dt(to_date) or now
    if to_date:  # include the full "to" day
        range_to = range_to.replace(hour=23, minute=59, second=59)
    range_from = _parse_dt(from_date) or (range_to - timedelta(days=29))
    if range_from > range_to:
        range_from, range_to = range_to, range_from
    span_days = min(366, max(1, (range_to.date() - range_from.date()).days + 1))

    sections = {
        "marketplace": ("listings", "auction_end_date"),
        "lots": ("multi_item_listings", "auction_end_date"),
        "vehicles": ("vehicle_listings", "end_time"),
        "storage": ("storage_auctions", "end_time"),
    }

    gmv_all = 0.0
    gmv_range = 0.0
    auctions_by_section: Dict[str, Dict[str, int]] = {}
    hammer_sums: Dict[str, List[float]] = defaultdict(list)
    seller_gmv: Dict[str, float] = defaultdict(float)
    conversion = {"ended_total": 0, "ended_with_bids": 0}

    for section, (coll_name, _end_field) in sections.items():
        docs = await db[coll_name].find(
            {}, {"_id": 0, "status": 1, "final_price": 1, "current_price": 1,
                 "current_bid": 1, "winner_user_id": 1, "winner_id": 1,
                 "winning_bidder_id": 1, "seller_id": 1, "facility_owner_id": 1,
                 "bid_count": 1, "bids": 1, "sold_at": 1, "ended_at": 1,
                 "is_demo": 1},
        ).to_list(50000)
        docs = [d for d in docs if not d.get("is_demo")]

        by_status: Dict[str, int] = defaultdict(int)
        for d in docs:
            by_status[d.get("status") or "unknown"] += 1
            end_dt = _parse_dt(d.get("sold_at") or d.get("ended_at"))
            end_in_range = (end_dt is None) or (range_from <= end_dt <= range_to)
            if d.get("status") in _ENDED_UNION and end_in_range:
                conversion["ended_total"] += 1
                bid_count = d.get("bid_count")
                if bid_count is None:
                    bid_count = len(d.get("bids") or [])
                if (bid_count or 0) > 0 or _is_sold(d):
                    conversion["ended_with_bids"] += 1
            if _is_sold(d):
                amount = _hammer(d)
                gmv_all += amount
                sold_dt = _parse_dt(d.get("sold_at") or d.get("ended_at"))
                if sold_dt and range_from <= sold_dt <= range_to:
                    gmv_range += amount
                    hammer_sums[section].append(amount)
                    seller = d.get("seller_id") or d.get("facility_owner_id")
                    if seller:
                        seller_gmv[seller] += amount
        auctions_by_section[section] = dict(by_status)

    # ── Platform revenue: actual collected fees from receipts; fall back
    # to the 2.5% estimate over GMV when receipts predate the system. ──
    receipts = await db.receipts.find(
        {"type": "buyer_receipt"},
        {"_id": 0, "platform_fee": 1, "created_at": 1},
    ).to_list(50000)
    fees_collected_all = round(sum(float(r.get("platform_fee") or 0) for r in receipts), 2)
    fees_collected_range = round(sum(
        float(r.get("platform_fee") or 0) for r in receipts
        if range_from <= (_parse_dt(r.get("created_at")) or now) <= range_to
    ), 2)

    # ── Users by role ──
    users = await db.users.find(
        {}, {"_id": 0, "role": 1, "is_vehicle_dealer": 1, "is_storage_facility": 1,
             "is_partner": 1, "is_demo": 1, "created_at": 1},
    ).to_list(100000)
    users = [u for u in users if not u.get("is_demo")]
    users_by_role: Dict[str, int] = defaultdict(int)
    for u in users:
        if u.get("role") in ("admin", "super_admin"):
            users_by_role["admin"] += 1
        elif u.get("is_vehicle_dealer"):
            users_by_role["vehicle_dealer"] += 1
        elif u.get("is_storage_facility"):
            users_by_role["storage_facility"] += 1
        elif u.get("is_partner"):
            users_by_role["partner_broker"] += 1
        else:
            users_by_role["individual"] += 1

    # ── Top 5 sellers by GMV (within the selected range) ──
    top_seller_rows = sorted(seller_gmv.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_seller_docs = {}
    if top_seller_rows:
        ids = [sid for sid, _ in top_seller_rows]
        docs = await db.users.find({"id": {"$in": ids}},
                                   {"_id": 0, "id": 1, "name": 1, "email": 1}).to_list(5)
        top_seller_docs = {u["id"]: u for u in docs}
    top_sellers = [{
        "seller_id": sid,
        "name": (top_seller_docs.get(sid) or {}).get("name") or "—",
        "gmv": round(amount, 2),
    } for sid, amount in top_seller_rows]

    # ── Top 5 most-bid listings (bids collection covers marketplace+lots;
    # vehicle_bids covers vehicles) ──
    bid_counts: Dict[str, int] = defaultdict(int)
    pipeline = [{"$group": {"_id": "$listing_id", "n": {"$sum": 1}}},
                {"$sort": {"n": -1}}, {"$limit": 10}]
    for coll in ("bids", "vehicle_bids"):
        async for row in db[coll].aggregate(pipeline):
            if row.get("_id"):
                bid_counts[row["_id"]] += int(row["n"])
    top_bid_rows = sorted(bid_counts.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_listings = []
    for lid, n in top_bid_rows:
        title = None
        for coll_name in ("listings", "multi_item_listings", "vehicle_listings", "storage_auctions"):
            doc = await db[coll_name].find_one({"id": lid}, {"_id": 0, "title": 1})
            if doc:
                title = doc.get("title")
                break
        top_listings.append({"listing_id": lid, "title": title or lid[:8], "bids": n})

    # ── Daily series (selected range, capped at 366 buckets) ──
    day_keys = [(range_to - timedelta(days=i)).strftime("%Y-%m-%d")
                for i in range(span_days - 1, -1, -1)]
    signups_by_day = {k: 0 for k in day_keys}
    for u in users:
        d = _day(_parse_dt(u.get("created_at")))
        if d in signups_by_day:
            signups_by_day[d] += 1
    revenue_by_day = {k: 0.0 for k in day_keys}
    for r in receipts:
        d = _day(_parse_dt(r.get("created_at")))
        if d in revenue_by_day:
            revenue_by_day[d] += float(r.get("platform_fee") or 0)

    avg_hammer = {
        section: round(sum(vals) / len(vals), 2) if vals else 0.0
        for section, vals in ((s, hammer_sums.get(s, [])) for s in sections)
    }
    conv_rate = (round(100.0 * conversion["ended_with_bids"] / conversion["ended_total"], 1)
                 if conversion["ended_total"] else 0.0)

    result = {
        "generated_at": now.isoformat(),
        "range": {"from": range_from.strftime("%Y-%m-%d"),
                  "to": range_to.strftime("%Y-%m-%d"), "days": span_days},
        "gmv": {"all_time": round(gmv_all, 2), "range": round(gmv_range, 2),
                "last_30d": round(gmv_range, 2)},
        "platform_revenue": {
            "all_time": fees_collected_all,
            "range": fees_collected_range,
            "last_30d": fees_collected_range,
            "estimated_all_time": round(gmv_all * 0.025, 2),
        },
        "auctions_by_section": auctions_by_section,
        "users_by_role": dict(users_by_role),
        "total_users": len(users),
        "top_sellers": top_sellers,
        "top_listings": top_listings,
        "conversion_rate_pct": conv_rate,
        "conversion_detail": conversion,
        "avg_hammer_by_section": avg_hammer,
        "signups_per_day": [{"date": k, "count": signups_by_day[k]} for k in day_keys],
        "revenue_per_day": [{"date": k, "amount": round(revenue_by_day[k], 2)} for k in day_keys],
    }
    await cache_set(_cache_key, result, ttl=60)
    return result
