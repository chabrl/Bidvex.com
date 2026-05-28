"""
iter236 — Mission 3 — Listing context builder for the AI chat.

When the frontend sends `listing_id` on /api/chat/stream, this module:
  1. Fetches the listing doc from bazario_db.listings by `id`.
  2. Fetches up to 5 market comparables for the same category, with closed
     items in the last 60 days ranked first by hammer_price DESC.
  3. Returns a JSON-serialisable dict suitable for embedding into the
     system instruction extra context block.

All Mongo `_id` fields are stripped. Datetime values are stringified.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


def _sanitize(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Drop `_id`, stringify datetimes, return a clean dict."""
    out: Dict[str, Any] = {}
    for k, v in doc.items():
        if k == "_id":
            continue
        if isinstance(v, datetime):
            out[k] = v.isoformat()
        else:
            out[k] = v
    return out


async def fetch_listing_context(db, listing_id: str) -> Optional[Dict[str, Any]]:
    """Return the slimmed listing context per the iter236 Mission 3 spec.

    Fields returned: title, category, condition, current_bid, buy_now_price,
    quantity, location.city, auction_end_time, seller_id,
    price_multiplied_by_quantity.
    """
    if not listing_id:
        return None
    try:
        doc = await db.listings.find_one({"id": listing_id})
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[iter236-context] listing fetch failed for {listing_id!r}: {e}")
        return None
    if not doc:
        # Try multi_item_listings as a fallback (lots auctions share the same UI).
        try:
            doc = await db.multi_item_listings.find_one({"id": listing_id})
        except Exception:  # noqa: BLE001
            doc = None
        if not doc:
            return None
    city = (
        doc.get("city")
        or (doc.get("location") or {}).get("city")
        or doc.get("seller_city")
    )
    return _sanitize({
        "id": doc.get("id"),
        "title": doc.get("title"),
        "category": doc.get("category"),
        "condition": doc.get("condition"),
        "current_bid": doc.get("current_bid") or doc.get("current_price"),
        "buy_now_price": doc.get("buy_now_price"),
        "quantity": doc.get("quantity") or 1,
        "location": {"city": city, "region": doc.get("region") or doc.get("province")},
        "auction_end_time": doc.get("auction_end_date") or doc.get("auction_end_time"),
        "seller_id": doc.get("seller_id"),
        "price_multiplied_by_quantity": bool(doc.get("price_multiplied_by_quantity")),
    })


async def fetch_market_comparables(
    db,
    listing_ctx: Dict[str, Any],
    *,
    limit: int = 5,
    window_days: int = 60,
) -> List[Dict[str, Any]]:
    """Return up to N comparable listings for the same category.

    Selection rules (spec):
      - Same category
      - Status: active OR closed within the last `window_days`
      - Exclude the current listing
      - Limit: 5 records
      - Sort: closed hammer_price DESC (closed first, then active)
    """
    if not listing_ctx or not listing_ctx.get("category"):
        return []
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    closed_match = {
        "category": listing_ctx["category"],
        "id": {"$ne": listing_ctx.get("id")},
        "status": {"$in": ["ended", "sold", "closed", "completed"]},
        "$or": [
            {"auction_end_date": {"$gte": since}},
            {"closed_at": {"$gte": since}},
        ],
        "hammer_price": {"$gt": 0},
    }
    active_match = {
        "category": listing_ctx["category"],
        "id": {"$ne": listing_ctx.get("id")},
        "status": {"$in": ["active", "upcoming"]},
    }
    projection = {
        "_id": 0,
        "id": 1, "title": 1, "current_bid": 1, "current_price": 1,
        "hammer_price": 1, "status": 1, "auction_end_date": 1,
        "city": 1, "region": 1, "quantity": 1, "location": 1,
    }
    out: List[Dict[str, Any]] = []
    try:
        closed_docs = await (
            db.listings.find(closed_match, projection)
            .sort("hammer_price", -1)
            .limit(limit)
            .to_list(length=limit)
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[iter236-context] closed-comparables query failed: {e}")
        closed_docs = []

    seen_ids = {d.get("id") for d in closed_docs}
    out.extend(closed_docs)

    remaining = max(0, limit - len(out))
    if remaining > 0:
        try:
            active_docs = await (
                db.listings.find(active_match, projection)
                .sort("current_bid", -1)
                .limit(remaining + 5)
                .to_list(length=remaining + 5)
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[iter236-context] active-comparables query failed: {e}")
            active_docs = []
        for d in active_docs:
            if d.get("id") in seen_ids:
                continue
            out.append(d)
            seen_ids.add(d.get("id"))
            if len(out) >= limit:
                break

    # Reshape per spec — strip _id, normalise city + dates.
    cleaned: List[Dict[str, Any]] = []
    for d in out[:limit]:
        cleaned.append(_sanitize({
            "id": d.get("id"),
            "title": d.get("title"),
            "current_bid": d.get("current_bid") or d.get("current_price"),
            "hammer_price": d.get("hammer_price"),
            "status": d.get("status"),
            "auction_end_time": d.get("auction_end_date"),
            "location": {"city": d.get("city") or (d.get("location") or {}).get("city")},
            "quantity": d.get("quantity") or 1,
        }))
    return cleaned


async def build_chat_listing_context(
    db,
    listing_id: Optional[str],
) -> Dict[str, Any]:
    """Top-level entry — returns the iter236 spec context dict."""
    current = await fetch_listing_context(db, listing_id) if listing_id else None
    comparables = await fetch_market_comparables(db, current) if current else []
    return {
        "current_viewed_listing": current,
        "market_comparables": comparables,
    }


__all__ = [
    "build_chat_listing_context",
    "fetch_listing_context",
    "fetch_market_comparables",
]
