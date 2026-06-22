"""
iter310 — Public "Recently Sold" Ticker

GET /api/public/recently-sold?limit=10
  → Returns the last N completed sales across all 4 sections:
    marketplace listings, vehicles, multi-item, storage.
    Anonymized (no buyer/seller names). Used by the homepage
    rolling-ticker social-proof component.
    Cached for 60s in memory.
"""
from __future__ import annotations

import time
from typing import Any, List

from fastapi import APIRouter, Query

from deps import get_db


public_recently_sold_router = APIRouter(tags=["Public Recently Sold"])

_SOLD_STATUSES = ("sold", "completed", "won", "closed")
_CACHE: dict = {"at": 0, "data": None, "limit": 0}
_TTL = 60  # seconds


async def _fetch_recent(db, collection: str, limit: int, title_keys: list) -> List[dict]:
    """Fetch most-recent sold rows from a single collection."""
    proj: dict = {"_id": 0, "id": 1, "current_price": 1, "hammer_price": 1,
                  "ended_at": 1, "updated_at": 1, "currency": 1}
    for k in title_keys:
        proj[k] = 1
    cursor = (
        db[collection]
        .find(
            {"status": {"$in": list(_SOLD_STATUSES)}},
            proj,
        )
        .sort([("ended_at", -1), ("updated_at", -1)])
        .limit(limit)
    )
    rows = await cursor.to_list(limit)
    out = []
    for r in rows:
        title = next((r.get(k) for k in title_keys if r.get(k)), None)
        if not title:
            continue
        price = (
            r.get("hammer_price")
            or r.get("current_price")
            or 0
        )
        try:
            price = round(float(price), 2)
        except Exception:
            continue
        if price <= 0:
            continue
        out.append({
            "id":        r.get("id"),
            "title":     str(title)[:80],
            "price":     price,
            "currency":  r.get("currency") or "CAD",
            "section":   collection,
            "ended_at":  r.get("ended_at") or r.get("updated_at"),
        })
    return out


@public_recently_sold_router.get("/public/recently-sold")
async def public_recently_sold(limit: int = Query(10, ge=1, le=25)):
    """Anonymized recent sales across all 4 sections (60s cache)."""
    now = time.time()
    if (
        _CACHE["data"] is not None
        and _CACHE["limit"] == limit
        and (now - _CACHE["at"]) < _TTL
    ):
        return _CACHE["data"]

    db = get_db()
    if db is None:
        return {"items": []}

    per_collection = max(limit, 5)
    combined: List[dict] = []
    # 4 sections — pull a bit extra from each, then sort + slice.
    combined += await _fetch_recent(db, "listings",                  per_collection, ["title", "name"])
    combined += await _fetch_recent(db, "vehicle_listings",          per_collection, ["title"])
    combined += await _fetch_recent(db, "multi_item_listings",       per_collection, ["title"])
    combined += await _fetch_recent(db, "storage_auctions",          per_collection, ["title", "facility_name", "unit_number"])

    def _sort_key(r: dict) -> Any:
        return r.get("ended_at") or 0

    combined.sort(key=_sort_key, reverse=True)
    sliced = combined[:limit]

    # Strip any volatile sort key from the response.
    payload = {
        "items": [
            {
                "id":       r["id"],
                "title":    r["title"],
                "price":    r["price"],
                "currency": r["currency"],
                "section":  r["section"],
            }
            for r in sliced
        ],
    }
    _CACHE.update(at=now, data=payload, limit=limit)
    return payload


__all__ = ["public_recently_sold_router"]
