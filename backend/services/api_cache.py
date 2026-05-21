"""
BidVex — Redis-backed TTL Cache for public API endpoints.
Uses Upstash Redis (via REDIS_URL) with automatic in-memory fallback.
Auto-invalidation on listing create/update/status change.
"""

import os
import time
import hashlib
import json
import logging
import asyncio
from typing import Any, Optional

logger = logging.getLogger(__name__)

# ─── Cache key namespaces ────────────────────────────────────────────
LISTINGS_NS = "listings:"
MARKETPLACE_NS = "marketplace:"
CATEGORIES_NS = "categories:"
FILTER_COUNTS_NS = "filter_counts:"
MARKETPLACE_ITEMS_NS = "mp_items:"
CHAT_SESSION_NS = "chat:"

# ─── Default TTLs (seconds) ─────────────────────────────────────────
DEFAULT_TTL = 300       # 5 min for general keys
ITEMS_TTL = 30          # 30s for marketplace items
FILTER_TTL = 300        # 5 min for filter counts
CHAT_SESSION_TTL = 3600  # 1 hour for chat sessions


# ─── Redis Client Singleton ─────────────────────────────────────────
_redis_client = None
_redis_available = None  # None = not checked yet, True/False after first attempt


async def _get_redis():
    """Lazily connect to Redis. Returns client or None."""
    global _redis_client, _redis_available

    if _redis_available is False:
        return None
    if _redis_client is not None:
        return _redis_client

    redis_url = os.environ.get("REDIS_URL", "")
    if not redis_url:
        logger.critical("[REDIS] REDIS_URL not set — falling back to LOCAL MEMORY. Set REDIS_URL (rediss://...) for Upstash.")
        _redis_available = False
        return None

    if not redis_url.startswith("rediss://"):
        logger.critical(f"[REDIS] REDIS_URL must start with rediss:// (TLS) for Upstash. Got: {redis_url[:20]}... — falling back to LOCAL MEMORY.")
        _redis_available = False
        return None

    try:
        import redis.asyncio as aioredis
        _redis_client = aioredis.from_url(
            redis_url,
            decode_responses=True,
            socket_connect_timeout=5,
            socket_timeout=5,
            retry_on_timeout=True,
        )
        await _redis_client.ping()
        _redis_available = True
        logger.info("[REDIS] Connected successfully to Upstash Redis (TLS)")
        return _redis_client
    except Exception as e:
        logger.critical(f"[REDIS] Connection FAILED ({e}) — falling back to LOCAL MEMORY. Brute-force & chat cache will NOT persist across restarts.")
        _redis_available = False
        _redis_client = None
        return None


async def startup_redis_check():
    """Run on app startup. Pings Redis and logs CRITICAL if unreachable."""
    r = await _get_redis()
    if r:
        try:
            pong = await r.ping()
            logger.info(f"[REDIS] Startup ping: {'PONG' if pong else 'FAILED'} — backend=redis")
            return {"connected": True, "backend": "redis"}
        except Exception as e:
            logger.critical(f"[REDIS] Startup ping FAILED: {e} — falling back to LOCAL MEMORY")
            return {"connected": False, "backend": "memory", "error": str(e)}
    else:
        logger.critical("[REDIS] Startup check: NO Redis connection — using LOCAL MEMORY fallback. Upstash will show 0 activity.")
        return {"connected": False, "backend": "memory"}


# ─── In-Memory Fallback ─────────────────────────────────────────────
_memory_store: dict[str, tuple[Any, float]] = {}


def _mem_get(key: str) -> Optional[str]:
    entry = _memory_store.get(key)
    if entry is None:
        return None
    value, expires_at = entry
    if time.time() > expires_at:
        del _memory_store[key]
        return None
    return value


def _mem_set(key: str, value: str, ttl: int):
    _memory_store[key] = (value, time.time() + ttl)


def _mem_delete_prefix(prefix: str):
    keys = [k for k in _memory_store if k.startswith(prefix)]
    for k in keys:
        del _memory_store[k]


# ─── Unified Cache API ──────────────────────────────────────────────

async def cache_get(key: str) -> Optional[Any]:
    """Get a cached value (Redis → memory fallback). Returns deserialized Python object."""
    r = await _get_redis()
    if r:
        try:
            raw = await r.get(key)
            if raw is not None:
                return json.loads(raw)
            return None
        except Exception as e:
            logger.debug(f"[cache] Redis GET error: {e}")
    # Fallback
    raw = _mem_get(key)
    return json.loads(raw) if raw else None


async def cache_set(key: str, value: Any, ttl: int = DEFAULT_TTL):
    """Set a cached value with TTL (Redis → memory fallback)."""
    serialized = json.dumps(_prepare_for_json(value), default=str)
    r = await _get_redis()
    if r:
        try:
            await r.set(key, serialized, ex=ttl)
            return
        except Exception as e:
            logger.debug(f"[cache] Redis SET error: {e}")
    # Fallback
    _mem_set(key, serialized, ttl)


def _prepare_for_json(obj):
    """Recursively convert Pydantic models and special types to JSON-safe dicts."""
    if hasattr(obj, 'model_dump'):
        return obj.model_dump()
    if isinstance(obj, list):
        return [_prepare_for_json(item) for item in obj]
    if isinstance(obj, dict):
        return {k: _prepare_for_json(v) for k, v in obj.items()}
    return obj


async def cache_delete(key: str):
    """Delete a single cache key."""
    r = await _get_redis()
    if r:
        try:
            await r.delete(key)
        except Exception:
            pass
    _memory_store.pop(key, None)


async def invalidate_prefix(prefix: str):
    """Delete all keys matching a prefix."""
    r = await _get_redis()
    if r:
        try:
            cursor = 0
            while True:
                cursor, keys = await r.scan(cursor, match=f"{prefix}*", count=100)
                if keys:
                    await r.delete(*keys)
                if cursor == 0:
                    break
        except Exception as e:
            logger.debug(f"[cache] Redis SCAN/DEL error: {e}")
    _mem_delete_prefix(prefix)


def invalidate_listing_caches():
    """Call when any listing is created, updated, or changes status.
    Fires a background task so callers don't await."""
    asyncio.ensure_future(_invalidate_listing_caches_async())


async def _invalidate_listing_caches_async():
    await invalidate_prefix(LISTINGS_NS)
    await invalidate_prefix(MARKETPLACE_NS)
    await invalidate_prefix(CATEGORIES_NS)
    await invalidate_prefix(FILTER_COUNTS_NS)
    await invalidate_prefix(MARKETPLACE_ITEMS_NS)
    logger.info("[cache] All listing caches invalidated")


def make_cache_key(namespace: str, params: dict) -> str:
    """Generate deterministic cache key from namespace + query params.

    iter211 — Use SHA-256 (truncated) instead of MD5. The hash is only used
    to deterministically derive a short cache-key suffix; the truncation makes
    the collision space identical to the previous implementation, but the
    underlying primitive is no longer the broken MD5.
    """
    sorted_params = json.dumps(params, sort_keys=True, default=str)
    param_hash = hashlib.sha256(sorted_params.encode()).hexdigest()[:12]
    return f"{namespace}{param_hash}"


# ─── Legacy compat: TTLCache singleton for existing consumers ────────
class _LegacyCache:
    """Thin wrapper so existing code using `cache.get()` / `cache.set()` still works."""
    async def get(self, key: str) -> Optional[Any]:
        return await cache_get(key)

    async def set(self, key: str, value: Any, ttl: int = DEFAULT_TTL):
        await cache_set(key, value, ttl)

    def invalidate_prefix(self, prefix: str):
        asyncio.ensure_future(invalidate_prefix(prefix))

    def invalidate_all(self):
        asyncio.ensure_future(invalidate_prefix(""))

cache = _LegacyCache()


async def get_cache_stats() -> dict:
    """Diagnostic endpoint data."""
    r = await _get_redis()
    if r:
        try:
            info = await r.info("memory")
            dbsize = await r.dbsize()
            return {
                "backend": "redis",
                "connected": True,
                "keys": dbsize,
                "memory_used": info.get("used_memory_human", "?"),
            }
        except Exception as e:
            return {"backend": "redis", "connected": False, "error": str(e)}
    return {
        "backend": "memory",
        "connected": False,
        "keys": len(_memory_store),
    }


# ─── ChatCache: Redis-backed chat session store for Master Concierge ─
class ChatCache:
    """Stores/retrieves chat history per user session in Redis.
    Falls back to in-memory dict when Redis is unavailable."""

    _mem_sessions: dict[str, str] = {}

    @staticmethod
    def _key(user_id: str) -> str:
        return f"{CHAT_SESSION_NS}{user_id}"

    @staticmethod
    async def get_history(user_id: str, max_turns: int = 20) -> list[dict]:
        """Retrieve chat history for a user from Redis (or memory)."""
        key = ChatCache._key(user_id)
        r = await _get_redis()
        if r:
            try:
                raw = await r.get(key)
                if raw:
                    history = json.loads(raw)
                    return history[-max_turns:]
                return []
            except Exception as e:
                logger.debug(f"[ChatCache] Redis GET error: {e}")
        raw = _mem_get(key)
        if raw:
            return json.loads(raw)[-max_turns:]
        return []

    @staticmethod
    async def append_turn(user_id: str, user_msg: str, assistant_msg: str):
        """Append a user+assistant turn to session history."""
        history = await ChatCache.get_history(user_id, max_turns=50)
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": assistant_msg})
        history = history[-40:]  # keep last 20 turns (40 messages)
        serialized = json.dumps(history, default=str)
        key = ChatCache._key(user_id)
        r = await _get_redis()
        if r:
            try:
                await r.set(key, serialized, ex=CHAT_SESSION_TTL)
                return
            except Exception as e:
                logger.debug(f"[ChatCache] Redis SET error: {e}")
        _mem_set(key, serialized, CHAT_SESSION_TTL)

    @staticmethod
    async def clear(user_id: str):
        """Clear chat session for a user."""
        key = ChatCache._key(user_id)
        r = await _get_redis()
        if r:
            try:
                await r.delete(key)
            except Exception:
                pass
        _memory_store.pop(key, None)
