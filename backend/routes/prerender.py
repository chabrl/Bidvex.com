"""
iter354 — Prerender route for search crawlers.

Two entry points:
  1. `GET /api/prerender/{path:path}?lang=en|fr` — explicit prerender. Called by
     the Cloudflare Worker in production, and by our preview ingress middleware.
  2. `BotPrerenderMiddleware` (registered in server.py) — inspects User-Agent on
     non-`/api/*` requests; when a known crawler UA is detected, transparently
     serves the prerender output instead of the SPA.

Every failure path returns 200 with a minimal HTML shell so a slow DB fetch
never produces a Cloudflare "invalid or incomplete response" popup.
"""
from __future__ import annotations

import asyncio
import logging
import re
from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from deps import get_db
from services.prerender_service import resolve_route, render_html

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prerender", tags=["seo-prerender"])

# ─── Known-crawler UA regex ────────────────────────────────────────────
# We match by substring against the lower-cased User-Agent. Sourced from
# https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers
# and https://developers.facebook.com/docs/sharing/webmasters/crawler
_CRAWLER_UA_PATTERNS = [
    "googlebot", "bingbot", "slurp",  # google/bing/yahoo
    "duckduckbot", "baiduspider", "yandexbot",
    "sogou", "exabot", "facebot", "facebookexternalhit",
    "linkedinbot", "twitterbot", "slackbot", "discordbot",
    "whatsapp", "telegrambot", "vkshare", "w3c_validator",
    "redditbot", "applebot", "mj12bot", "semrushbot", "ahrefsbot",
    "yeti", "petalbot", "bytespider",
]
_CRAWLER_UA_RE = re.compile("|".join(re.escape(p) for p in _CRAWLER_UA_PATTERNS), re.IGNORECASE)


def is_crawler_ua(user_agent: Optional[str]) -> bool:
    if not user_agent:
        return False
    return bool(_CRAWLER_UA_RE.search(user_agent))


# ─── Public routes eligible for SSR prerender ──────────────────────────
_PRERENDER_ROUTE_PREFIXES = (
    "/",
    "/marketplace",
    "/lots-marketplace",
    "/vehicle-auctions",
    "/storage-auctions",
    "/broker-directory",
    "/auctions/",
    "/multi-item-auctions/",
    "/vehicles/",
    "/storage/",
    "/faq",
    "/how-it-works",
    "/about",
    "/about-us",
    "/contact",
    "/terms",
    "/legal/",
    "/privacy-policy",
    # iter356 — Regional SEO landing pages
    "/car-auctions-canada",
    "/vehicle-auctions-canada",
    "/vehicle-auctions-quebec",
    "/vehicle-auctions-ontario",
    "/vehicle-auctions-british-columbia",
    "/vehicle-auctions-alberta",
    "/storage-auctions-quebec",
    "/storage-auctions-ontario",
    "/storage-auctions-british-columbia",
    "/equipment-auctions-canada",
    # French Quebec twins
    "/encheres-vehicules-quebec",
    "/encheres-entreposage-quebec",
)


def is_prerender_eligible(path: str) -> bool:
    """True if the given path should be prerendered for crawlers."""
    if path.startswith("/api/") or path.startswith("/static/") or path.startswith("/build/"):
        return False
    if any(path.endswith(ext) for ext in (".js", ".css", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".map", ".txt", ".xml", ".json")):
        return False
    if path in ("/", ""):
        return True
    return any(path == p.rstrip("/") or path.startswith(p) for p in _PRERENDER_ROUTE_PREFIXES if p != "/")


# ─── The explicit endpoint ─────────────────────────────────────────────
@router.get("/{path:path}", response_class=HTMLResponse)
async def prerender_endpoint(
    path: str,
    request: Request,
    lang: str = Query("en", regex="^(en|fr)$"),
    db=Depends(get_db),
):
    """GET /api/prerender/{path}?lang=en|fr — returns fully rendered HTML."""
    normalized = "/" + path.lstrip("/")

    async def _run():
        ctx = await resolve_route(db, normalized, lang)
        return render_html(ctx)

    try:
        html = await asyncio.wait_for(_run(), timeout=8.0)
        return HTMLResponse(
            content=html,
            headers={
                "Cache-Control": "public, max-age=60, s-maxage=300",
                "X-Prerender-Version": "iter354",
            },
        )
    except asyncio.TimeoutError:
        logger.error(f"[prerender] budget exceeded 8s path={normalized!r}")
    except Exception as exc:  # noqa: BLE001
        logger.exception(f"[prerender] failed path={normalized!r}: {exc}")

    # Graceful fallback — minimal HTML that still validates for Cloudflare.
    fallback = f"""<!DOCTYPE html><html lang="{lang}"><head>
<meta charset="UTF-8"><title>BidVex — Auction Marketplace</title>
<meta name="description" content="BidVex — Canada's bilingual auction marketplace.">
<link rel="canonical" href="https://www.bidvex.com{normalized}">
</head><body><h1>BidVex</h1><p>Please try again in a moment.</p><div id="root"></div></body></html>"""
    return HTMLResponse(content=fallback, status_code=200,
                        headers={"X-Prerender-Version": "iter354-fallback"})


# ─── Ingress middleware (preview environment) ──────────────────────────
class BotPrerenderMiddleware(BaseHTTPMiddleware):
    """Preview-side ingress override.

    When a request:
      • is a GET,
      • has a crawler User-Agent (or `?_ssr=1` debug flag),
      • targets a prerender-eligible path,
    we short-circuit the SPA response with prerendered HTML.

    Real users continue to hit the SPA build served by the frontend container.
    In production, this middleware is redundant — the Cloudflare Worker does
    the same routing at the edge — but keeping it here lets us validate the
    prerender output end-to-end on preview.bidvex.com before touching CF.
    """

    def __init__(self, app: ASGIApp, enabled: bool = True) -> None:
        super().__init__(app)
        self.enabled = enabled

    async def dispatch(self, request: Request, call_next):
        if not self.enabled:
            return await call_next(request)
        if request.method != "GET":
            return await call_next(request)
        path = request.url.path or "/"
        if not is_prerender_eligible(path):
            return await call_next(request)

        ua = request.headers.get("user-agent") or ""
        force_ssr = request.query_params.get("_ssr") == "1"
        if not (force_ssr or is_crawler_ua(ua)):
            return await call_next(request)

        # Determine language — query param wins, then Accept-Language
        lang = request.query_params.get("lang", "en")
        if lang not in ("en", "fr"):
            accept = (request.headers.get("accept-language") or "").lower()
            lang = "fr" if accept.startswith("fr") else "en"

        try:
            # Grab a db handle via the app state — fall back to deps.get_db
            from deps import get_db
            db = get_db()
            async def _run():
                ctx = await resolve_route(db, path, lang)
                return render_html(ctx)
            html = await asyncio.wait_for(_run(), timeout=8.0)
            return HTMLResponse(
                content=html,
                headers={
                    "Cache-Control": "public, max-age=60, s-maxage=300",
                    "X-Prerender-Version": "iter354",
                    "X-Prerender-UA-Match": "1",
                },
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[prerender-middleware] failed for path={path!r}: {exc} — falling back to SPA")
            return await call_next(request)
