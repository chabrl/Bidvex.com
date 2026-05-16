"""
Phase 5 — In-memory TTL cache for the Meta product catalog feed.

The feed is read by Meta's server-side crawler with a tight 30 s timeout.
We cache the full eligible-item list (and per-filter slices) for 15 minutes
so cold MongoDB queries never block Meta. APScheduler warms the cache
every 10 minutes; listing status changes trigger an explicit invalidation.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any, Callable, Dict, Optional, Tuple

logger = logging.getLogger(__name__)

FEED_CACHE_TTL_SECONDS = int(os.environ.get("FEED_CACHE_TTL_SECONDS", "900"))

# Bucket: key -> {"data": Any, "ts": float, "exclusions": dict}
_cache: Dict[str, Dict[str, Any]] = {}
_cache_lock = asyncio.Lock()


def make_cache_key(
    province: Optional[str],
    category: Optional[str],
    type_filter: Optional[str],
    limit: int,
    offset: int,
) -> str:
    p = (province or "").lower()
    c = (category or "").lower()
    t = (type_filter or "").lower()
    return f"fb_feed:{p}:{c}:{t}:{limit}:{offset}"


def cache_get(key: str) -> Optional[Tuple[Any, float, Dict[str, int]]]:
    entry = _cache.get(key)
    if not entry:
        return None
    age = time.time() - entry["ts"]
    if age >= FEED_CACHE_TTL_SECONDS:
        return None
    return entry["data"], entry["ts"], entry["exclusions"]


def cache_set(key: str, data: Any, exclusions: Dict[str, int]) -> None:
    _cache[key] = {
        "data": data,
        "ts": time.time(),
        "exclusions": dict(exclusions),
    }


def invalidate_feed_cache() -> int:
    """Clear all fb_feed:* keys. Returns the count of dropped entries.

    Called from listing status-change handlers so new/sold listings
    appear in Meta's catalog within minutes (next request rebuilds).
    """
    keys = [k for k in _cache if k.startswith("fb_feed:")]
    for k in keys:
        _cache.pop(k, None)
    if keys:
        logger.info("Phase5 feed cache invalidated: %d keys cleared", len(keys))
    return len(keys)


def get_cache_size() -> int:
    return len([k for k in _cache if k.startswith("fb_feed:")])


def get_last_warmed_at() -> Optional[float]:
    timestamps = [v["ts"] for k, v in _cache.items() if k.startswith("fb_feed:")]
    return max(timestamps) if timestamps else None


async def get_or_build(
    key: str,
    builder: Callable[[], Any],
) -> Tuple[Any, bool, Dict[str, int]]:
    """Cache-aside read. Returns (data, was_cache_hit, exclusions)."""
    hit = cache_get(key)
    if hit:
        data, ts, exclusions = hit
        logger.debug("Phase5 feed cache HIT: %s (age %.1fs)", key, time.time() - ts)
        return data, True, exclusions
    async with _cache_lock:
        # Double-check after acquiring the lock
        hit = cache_get(key)
        if hit:
            return hit[0], True, hit[2]
        logger.info("Phase5 feed cache MISS: %s — rebuilding", key)
        data, exclusions = await builder()
        cache_set(key, data, exclusions)
        return data, False, exclusions
