"""iter348 — Feed image URL crawler-health check.

Google Merchant Center and Meta Commerce Manager BOTH remove products
whose `image_link` returns:
  - HTTP 4xx (403 = bucket policy blocks anon; 404 = object deleted;
    401 = presigned URL expired)
  - HTTP 5xx
  - A non-image Content-Type (XML permission errors show as
    application/xml; HTML error pages show as text/html)

We can't ask AWS S3 or Cloudinary to "please respond nicely" — but we
CAN verify each URL FROM OUR FEED PIPELINE the same way Googlebot does
(HEAD request, Googlebot User-Agent) and skip any URL that fails.

Failing URLs cause the feed mapper to fall through to the per-listing
pre-baked JPEG placeholder we already generate on our own domain — that
placeholder is guaranteed crawlable, so the product remains in the
catalog with a branded card instead of being silently removed.

In-process TTL cache keeps HEAD traffic to O(1) per unique URL per hour.
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)


# 60 min cache — long enough to keep a single feed rebuild's HEAD traffic
# to O(unique URLs), short enough that a fresh S3 bucket policy fix flows
# through automatically without a redeploy.
_TTL_SECONDS = 60 * 60

# result[url] = (verified_at_epoch, ok, content_type, http_status)
_CACHE: Dict[str, Tuple[float, bool, str, int]] = {}
_CACHE_LOCK = asyncio.Lock()

# Bail-out cap to avoid pathological cases where an entire batch of
# thousands of listings triggers HEAD checks in one build. We defer
# uncached URLs to a background job when the total exceeds this.
_MAX_HEAD_PER_BUILD = 400

# Googlebot-Image UA — the exact string Google publishes.
_GOOGLEBOT_UA = (
    "Mozilla/5.0 (compatible; Googlebot-Image/1.0; "
    "+http://www.google.com/bot.html)"
)


def clear_cache() -> int:
    """Test hook."""
    n = len(_CACHE)
    _CACHE.clear()
    return n


def cache_stats() -> Dict[str, Any]:
    now = time.time()
    fresh = sum(1 for (t, *_ ) in _CACHE.values() if now - t < _TTL_SECONDS)
    return {
        "total_cached": len(_CACHE),
        "fresh":        fresh,
        "ttl_seconds":  _TTL_SECONDS,
    }


async def _head_probe(client: httpx.AsyncClient, url: str) -> Tuple[bool, str, int]:
    """Return (crawler_would_accept, content_type, http_status)."""
    try:
        r = await client.head(
            url,
            headers={"User-Agent": _GOOGLEBOT_UA, "Accept": "image/*"},
            timeout=5.0,
        )
    except httpx.HTTPError as e:
        logger.warning(f"[img-health] HEAD failed for {url[:120]}: {type(e).__name__}: {e}")
        return False, "", 0

    ct = (r.headers.get("content-type") or "").split(";", 1)[0].strip().lower()
    status = r.status_code
    ok_status = 200 <= status < 300
    ok_ct = ct.startswith("image/") and "svg" not in ct and "webp" not in ct
    accepted = ok_status and ok_ct
    if not accepted:
        logger.info(
            f"[img-health] would-reject: status={status} ct={ct!r} url={url[:140]}"
        )
    return accepted, ct, status


async def is_url_crawlable(url: str) -> Tuple[bool, str, int]:
    """Idempotent, TTL-cached check. Returns (ok, content_type, status)."""
    if not url or not url.startswith("https://"):
        return False, "", 0

    now = time.time()
    hit = _CACHE.get(url)
    if hit and now - hit[0] < _TTL_SECONDS:
        _, ok, ct, st = hit
        return ok, ct, st

    async with httpx.AsyncClient(follow_redirects=True) as http:
        ok, ct, status = await _head_probe(http, url)

    async with _CACHE_LOCK:
        _CACHE[url] = (now, ok, ct, status)
    return ok, ct, status


async def filter_crawlable(urls: list[str], max_check: int = _MAX_HEAD_PER_BUILD) -> Dict[str, Tuple[bool, str, int]]:
    """Verify a batch of URLs in parallel. Returns {url: (ok, ct, status)}.

    Deduplicates on entry, uses cached values, respects `max_check` to
    cap the number of new HEAD requests. URLs beyond the cap are treated
    as UNKNOWN (ok=True, ct="", status=0) — feed emits them as-is; a
    subsequent build with a warmer cache will re-verify them.
    """
    out: Dict[str, Tuple[bool, str, int]] = {}
    uncached: list[str] = []
    now = time.time()

    for u in dict.fromkeys(urls):
        if not isinstance(u, str) or not u.startswith("https://"):
            out[u] = (False, "", 0)
            continue
        hit = _CACHE.get(u)
        if hit and now - hit[0] < _TTL_SECONDS:
            _, ok, ct, st = hit
            out[u] = (ok, ct, st)
        else:
            uncached.append(u)

    if not uncached:
        return out

    to_check = uncached[:max_check]
    deferred = uncached[max_check:]

    async with httpx.AsyncClient(follow_redirects=True) as http:
        results = await asyncio.gather(
            *[_head_probe(http, u) for u in to_check],
            return_exceptions=False,
        )
    async with _CACHE_LOCK:
        for u, (ok, ct, st) in zip(to_check, results):
            _CACHE[u] = (now, ok, ct, st)
            out[u] = (ok, ct, st)

    # Deferred URLs — pass through as unknown.
    for u in deferred:
        out[u] = (True, "", 0)

    return out


async def diagnose_sample(urls: list[str], limit: int = 20) -> Dict[str, Any]:
    """Admin diagnostic: HEAD-test up to `limit` URLs, classify failures,
    return a compact JSON report that Charbel can eyeball to see if the
    S3 bucket policy needs opening up or which URLs need image
    regeneration.
    """
    sample = list(dict.fromkeys(urls))[:limit]
    if not sample:
        return {"tested": 0, "results": []}

    results = []
    async with httpx.AsyncClient(follow_redirects=True) as http:
        head_results = await asyncio.gather(
            *[_head_probe(http, u) for u in sample],
            return_exceptions=False,
        )

    for url, (ok, ct, status) in zip(sample, head_results):
        cause = None
        if not ok:
            if status == 403:
                cause = "s3_bucket_policy_blocks_anonymous_get (fix: enable public-read GetObject in AWS Console)"
            elif status == 401:
                cause = "presigned_url_expired_or_signed_v4_mismatch (fix: emit raw public URL, not presigned)"
            elif status == 404:
                cause = "object_not_found (fix: re-upload; DB has orphan reference)"
            elif status == 0:
                cause = "network_timeout_or_dns_failure (fix: verify hostname reachable from public internet)"
            elif ct and not ct.startswith("image/"):
                cause = f"wrong_content_type ({ct}) — object exists but S3 metadata says non-image; re-upload with ContentType=image/jpeg"
            else:
                cause = f"unknown ({status} {ct})"
        results.append({
            "url":               url,
            "http_status":       status,
            "content_type":      ct,
            "would_be_accepted": ok,
            "probable_cause":    cause,
        })

    ok_count = sum(1 for r in results if r["would_be_accepted"])
    return {
        "tested":                  len(results),
        "would_be_accepted_count": ok_count,
        "would_be_rejected_count": len(results) - ok_count,
        "results":                 results,
        "cache_stats":             cache_stats(),
    }
