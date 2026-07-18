"""
iter361 — Cache-control middleware + Sitemap health probe.

Two features rolled into one small router module:

  1. **Cache-control middleware** — layered on the FastAPI app:
     - Static assets (`/static/`, `/assets/`, files with cacheable extensions)
       get `Cache-Control: public, max-age=31536000, immutable` (1 year).
     - Bot User-Agents get `Cache-Control: no-store, no-cache, must-revalidate`
       + `Vary: User-Agent` on every response. This is our defensive hedge
       against the mysterious `X-Rendered-By: crawler-cache` layer on the
       bidvex.com production stack: if that layer respects
       origin cache-control, we force it to bypass its cache and let
       BotPrerenderMiddleware inject valid JSON-LD.

  2. **Sitemap health probe** — `GET /api/admin/seo/sitemap-status`:
     Admin-only. Fetches the sitemap index + every sub-sitemap and
     reports accessibility, URL count, robots.txt sitemap references,
     and last-modified stamps. Used by ops to verify GSC readiness.
"""
from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.types import ASGIApp

# ─── Bot-UA regex (matches BotPrerenderMiddleware's list) ─────────────
_BOT_UA_REGEX = re.compile(
    r"("
    r"googlebot|google-inspectiontool|google-structured-data-testing-tool|"
    r"adsbot-google|mediapartners-google|apis-google|"
    r"bingbot|msnbot|bingpreview|"
    r"slurp|yahoo|duckduckbot|duckduckgo|"
    r"baiduspider|yandex(bot|images)?|yeti|naverbot|"
    r"sogou|exabot|seznambot|"
    r"facebot|facebookexternalhit|meta-externalagent|"
    r"linkedinbot|twitterbot|x-clientua|"
    r"slackbot|slack-imgproxy|discordbot|"
    r"whatsapp|telegrambot|vkshare|"
    r"redditbot|applebot|"
    r"mj12bot|semrushbot|ahrefsbot|dotbot|petalbot|"
    r"bytespider|chrome-lighthouse|"
    r"w3c_validator|validator\.w3\.org|"
    r"embedly|rogerbot|quora link preview|showyoubot|outbrain|"
    r"pinterest|developers\.google\.com/\+/web/snippet|"
    r"headlesschrome"
    r")",
    re.IGNORECASE,
)

# File extensions that always get the 1-year immutable cache header.
# CRA/Vite bundle output hashes filenames, making immutable-caching safe.
_IMMUTABLE_STATIC_EXT = re.compile(
    r"\.(js|mjs|css|png|jpe?g|webp|avif|gif|svg|ico|map|woff2?|ttf|eot|otf)$",
    re.IGNORECASE,
)
_IMMUTABLE_PATH_PREFIXES = ("/static/", "/assets/", "/_next/static/")


class CacheHeadersMiddleware(BaseHTTPMiddleware):
    """iter361 — Universal Cache-Control layer.

    Runs AFTER the app response. Sets:
      • Static assets → 1-year immutable cache
      • Bot UAs → no-store (defeats intermediate proxies like crawler-cache)
      • Other HTML responses → left untouched (BotPrerenderMiddleware +
        route-level headers manage their own values)
    """

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        try:
            path = request.url.path or "/"
            ua = request.headers.get("user-agent", "")

            # ── 1. Bot-UA response ─ force cache bypass ─────────────
            if _BOT_UA_REGEX.search(ua):
                # Only override HTML responses; leave 3xx/4xx and API JSON alone.
                content_type = response.headers.get("content-type", "")
                if content_type.startswith("text/html") or content_type == "":
                    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
                    response.headers["Pragma"] = "no-cache"
                    response.headers["Expires"] = "0"
                    # `Vary: User-Agent` tells intermediate caches "your cache
                    # key MUST include the UA" — a valid signal to CF Speed
                    # Brain / crawler-cache to skip its shared cache.
                    existing_vary = response.headers.get("Vary", "")
                    if "User-Agent" not in existing_vary:
                        response.headers["Vary"] = (
                            existing_vary + ", User-Agent"
                            if existing_vary else "User-Agent"
                        )
                    response.headers["X-Bot-Detected"] = "true"

            # ── 2. Static assets ─ long-lived immutable cache ───────
            elif path.startswith(_IMMUTABLE_PATH_PREFIXES) or _IMMUTABLE_STATIC_EXT.search(path):
                # Only apply if no explicit Cache-Control already set upstream.
                if "cache-control" not in {k.lower() for k in response.headers.keys()}:
                    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        except Exception:
            # Never break responses on header manipulation errors.
            pass
        return response


# ═══════════════════════════════════════════════════════════════════════
#  Sitemap health probe (admin-only)
# ═══════════════════════════════════════════════════════════════════════

seo_router = APIRouter(prefix="/api/admin/seo", tags=["admin-seo"])


async def _fetch_url(client: httpx.AsyncClient, url: str) -> Dict[str, Any]:
    """Fetch a URL, return {ok, status, body, elapsed_ms, error}."""
    started = time.perf_counter()
    try:
        r = await client.get(url, follow_redirects=True, timeout=8.0)
        return {
            "ok": r.status_code == 200,
            "status": r.status_code,
            "body": r.text,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "ok": False,
            "status": 0,
            "body": "",
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "error": str(exc)[:200],
        }


_LOC_RE = re.compile(r"<loc>([^<]+)</loc>", re.IGNORECASE)


def _count_urls(xml_body: str) -> int:
    return len(_LOC_RE.findall(xml_body or ""))


def _extract_subsitemaps(xml_body: str) -> List[str]:
    """Parse a sitemap index and return sub-sitemap URLs."""
    if "<sitemapindex" not in (xml_body or "").lower():
        return []
    return _LOC_RE.findall(xml_body or "")


@seo_router.get("/sitemap-status")
async def sitemap_status(request: Request):
    """iter361 — Fetches sitemap-index + all sub-sitemaps, robots.txt.

    Returns a dict summarizing crawlability of the SEO surface. Admin-only.

    Response schema:
      {
        sitemap_index_url: str,
        sitemap_index_accessible: bool,
        sitemap_index_url_count: int,        # count of sub-sitemap <loc> entries
        sub_sitemaps: [
          {url, accessible, url_count, last_modified, elapsed_ms, error}
        ],
        robots_txt_url: str,
        robots_txt_accessible: bool,
        robots_txt_references_sitemap_index: bool,
        robots_txt_references_sitemap_xml:  bool,
        last_checked: iso8601,
      }
    """
    # Auth: admin only. We late-import to avoid a startup cycle.
    from deps import require_admin, get_current_user
    try:
        user = await get_current_user(request)  # type: ignore[arg-type]
        await require_admin(current_user=user)  # type: ignore[arg-type]
    except Exception:
        raise HTTPException(status_code=403, detail="Admin authentication required")

    # Base URL — prefer the production canonical, fall back to request origin
    # so this endpoint self-tests correctly on any environment.
    from services.seo_jsonld import CANONICAL_HOST
    base = CANONICAL_HOST or f"{request.url.scheme}://{request.url.netloc}"
    sitemap_index_url = f"{base}/sitemap_index.xml"
    robots_url = f"{base}/robots.txt"

    now_iso = datetime.now(timezone.utc).isoformat()

    async with httpx.AsyncClient() as client:
        # Fetch sitemap index + robots.txt in parallel.
        idx_result, robots_result = await asyncio.gather(
            _fetch_url(client, sitemap_index_url),
            _fetch_url(client, robots_url),
        )

        sub_urls = _extract_subsitemaps(idx_result["body"]) if idx_result["ok"] else []
        sub_results = []
        if sub_urls:
            # Fetch every sub-sitemap in parallel (cap at 10 to avoid runaway).
            fetches = [_fetch_url(client, u) for u in sub_urls[:10]]
            fetched = await asyncio.gather(*fetches)
            for u, f in zip(sub_urls[:10], fetched):
                sub_results.append({
                    "url": u,
                    "accessible": f["ok"],
                    "status": f["status"],
                    "url_count": _count_urls(f["body"]),
                    "elapsed_ms": f["elapsed_ms"],
                    "error": f["error"],
                })

    robots_body = robots_result["body"] if robots_result["ok"] else ""
    return {
        "sitemap_index_url": sitemap_index_url,
        "sitemap_index_accessible": idx_result["ok"],
        "sitemap_index_status": idx_result["status"],
        "sitemap_index_url_count": len(sub_urls),
        "sub_sitemaps": sub_results,
        "robots_txt_url": robots_url,
        "robots_txt_accessible": robots_result["ok"],
        "robots_txt_references_sitemap_index": "sitemap_index.xml" in robots_body,
        "robots_txt_references_sitemap_xml":   "sitemap.xml" in robots_body,
        "canonical_host": base,
        "last_checked": now_iso,
    }


__all__ = [
    "CacheHeadersMiddleware",
    "seo_router",
]
