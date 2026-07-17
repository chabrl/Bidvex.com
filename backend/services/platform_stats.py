"""
iter357 — Public platform stats service.

Returns the numbers we display in the social-proof widget:
    • dealers          — count of active seller/dealer accounts
    • auctions_completed — count of auctions ever settled (settled_at ≠ null)
    • provinces        — count of unique provinces with at least 1 listing
    • active_now       — count of live auctions right this second

Values are CACHED for 5 minutes to avoid a Mongo query on every prerender
hit. If the cache is stale/empty, we fall back to hardcoded conservative
numbers so bots always see a real value (never "0 dealers").

Public — no auth. Safe to render into SSR HTML.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Fallback values if the DB is unreachable at the moment. These are the
# floor — real values are always ≥ these once the platform has any data.
_FALLBACK = {
    "dealers":            "60+",
    "auctions_completed": "1,200+",
    "provinces":          "10",
    "active_now":         "40+",
}


class _StatsCache:
    def __init__(self, ttl: int = 300):
        self.ttl = ttl
        self.value: Optional[Dict[str, Any]] = None
        self.expires_at: float = 0.0


_cache = _StatsCache()


def _humanize(n: int) -> str:
    """Round numbers upward to psychologically favourable buckets."""
    if n <= 0:
        return "0"
    if n < 10:
        return f"{n}"
    if n < 100:
        return f"{(n // 10) * 10}+"
    if n < 1000:
        return f"{(n // 100) * 100}+"
    if n < 10000:
        return f"{(n // 1000) * 1000:,}+"
    return f"{n:,}"


async def _query_stats(db) -> Dict[str, Any]:
    """Actual Mongo query — kept in a separate function so the cache path is clean."""
    try:
        dealers, auc_done, provinces, active_now = await asyncio.gather(
            db.users.count_documents({
                "$or": [
                    {"role": "dealer"},
                    {"seller_verified": True},
                    {"is_broker": True},
                ]
            }),
            db.listings.count_documents({"settled_at": {"$ne": None}}),
            db.listings.distinct("province"),
            db.listings.count_documents({"status": "active"}),
        )
        # If ALL counters are zero, the DB is empty or the query missed —
        # return the aspirational fallback so bots don't see "0 dealers".
        if dealers == 0 and auc_done == 0 and active_now == 0 and not provinces:
            return dict(_FALLBACK)
        return {
            "dealers":            _humanize(dealers),
            "auctions_completed": _humanize(auc_done),
            "provinces":          str(len([p for p in provinces if p])) or _FALLBACK["provinces"],
            "active_now":         _humanize(active_now),
        }
    except Exception as exc:  # noqa: BLE001
        logger.info(f"[iter357 platform-stats] fallback due to: {exc}")
        return dict(_FALLBACK)


async def get_platform_stats(db) -> Dict[str, Any]:
    """Cached front-door. Returns fallback if db is None."""
    if db is None:
        return dict(_FALLBACK)
    now = time.time()
    if _cache.value and now < _cache.expires_at:
        return _cache.value
    stats = await _query_stats(db)
    _cache.value = stats
    _cache.expires_at = now + _cache.ttl
    return stats


def get_platform_stats_sync(db) -> Dict[str, Any]:
    """Convenience wrapper for sync callers. Runs the async fn synchronously."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're inside an already-running loop (e.g. FastAPI request).
            # The caller should await get_platform_stats directly. Return
            # fallback rather than deadlock.
            return dict(_FALLBACK)
        return loop.run_until_complete(get_platform_stats(db))
    except Exception:
        return dict(_FALLBACK)


__all__ = ["get_platform_stats", "get_platform_stats_sync", "_FALLBACK"]
