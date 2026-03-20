"""
In-memory TTL cache for public API endpoints.
Auto-invalidation on listing create/update/status change.
"""
import time
import hashlib
import json
from typing import Any, Optional
from functools import wraps

class TTLCache:
    def __init__(self):
        self._store: dict[str, tuple[Any, float]] = {}
    
    def get(self, key: str) -> Optional[Any]:
        entry = self._store.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if time.time() > expires_at:
            del self._store[key]
            return None
        return value
    
    def set(self, key: str, value: Any, ttl: int):
        self._store[key] = (value, time.time() + ttl)
    
    def invalidate_prefix(self, prefix: str):
        keys_to_delete = [k for k in self._store if k.startswith(prefix)]
        for k in keys_to_delete:
            del self._store[k]
    
    def invalidate_all(self):
        self._store.clear()
    
    @property
    def size(self) -> int:
        return len(self._store)

# Singleton cache instance
cache = TTLCache()

# Cache key namespaces
LISTINGS_NS = "listings:"
MARKETPLACE_NS = "marketplace:"
CATEGORIES_NS = "categories:"

def make_cache_key(namespace: str, params: dict) -> str:
    """Generate deterministic cache key from namespace + query params."""
    sorted_params = json.dumps(params, sort_keys=True, default=str)
    param_hash = hashlib.md5(sorted_params.encode()).hexdigest()[:12]
    return f"{namespace}{param_hash}"

def invalidate_listing_caches():
    """Call this when any listing is created, updated, or changes status."""
    cache.invalidate_prefix(LISTINGS_NS)
    cache.invalidate_prefix(MARKETPLACE_NS)
    cache.invalidate_prefix(CATEGORIES_NS)
