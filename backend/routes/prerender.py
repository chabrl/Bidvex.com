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
# Match by substring against the lower-cased User-Agent. Sourced from:
#   https://developers.google.com/search/docs/crawling-indexing/overview-google-crawlers
#   https://developers.facebook.com/docs/sharing/webmasters/crawler
#   https://www.bing.com/webmasters/help/which-crawlers-does-bing-use-8c184ec0
# iter362 — expanded to cover ALL Google testing tools (GSC Live Test uses
# `google-inspectiontool`, Rich Results Test uses `developers.google.com`)
# plus every AI/social crawler that consumes structured data.
_CRAWLER_UA_PATTERNS = [
    # ── Google (including SEO testing tools — CRITICAL for GSC verification) ──
    "googlebot", "google-inspectiontool", "google-structured-data-testing-tool",
    "adsbot-google", "mediapartners-google", "apis-google",
    "developers.google.com",  # Rich Results Test / URL Inspection Live UA
    # ── Microsoft / Bing / Yahoo ──
    "bingbot", "msnbot", "bingpreview", "slurp", "yahoo",
    # ── Other search engines ──
    "duckduckbot", "duckduckgo",
    "baiduspider", "yandex", "yeti", "naverbot",
    "sogou", "exabot", "seznambot",
    # ── Social unfurlers ──
    "facebot", "facebookexternalhit", "meta-externalagent",
    "linkedinbot", "twitterbot", "x-clientua",
    "slackbot", "slack-imgproxy", "discordbot",
    "whatsapp", "telegrambot", "vkshare",
    "redditbot", "applebot",
    # ── SEO / audit crawlers ──
    "mj12bot", "semrushbot", "ahrefsbot", "dotbot", "petalbot",
    "bytespider", "chrome-lighthouse",
    "w3c_validator", "validator.w3.org",
    # ── Preview cards + link scanners ──
    "embedly", "quora link preview", "showyoubot", "outbrain",
    "pinterest", "rogerbot",
    # ── Generic bot markers (last-line-of-defense) ──
    "headlesschrome",
]
_CRAWLER_UA_RE = re.compile("|".join(re.escape(p) for p in _CRAWLER_UA_PATTERNS), re.IGNORECASE)


def is_crawler_ua(user_agent: Optional[str]) -> bool:
    if not user_agent:
        return False
    return bool(_CRAWLER_UA_RE.search(user_agent))


# ─── Public routes eligible for SSR prerender ──────────────────────────
_PRERENDER_ROUTE_PREFIXES = (
    "/",
    "/en/", "/fr/",         # iter357 — bilingual subpaths (backend only for now)
    "/marketplace",
    "/marche",
    "/lots",
    "/lots-auction",
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
    "/encheres-vehicules-quebec",
    "/encheres-entreposage-quebec",
    # iter357 — 24 QC city landing pages (12 cities × 2 languages)
    "/vehicle-auctions-montreal",
    "/vehicle-auctions-quebec-city",
    "/vehicle-auctions-sherbrooke",
    "/vehicle-auctions-laval",
    "/vehicle-auctions-gatineau",
    "/vehicle-auctions-saguenay",
    "/vehicle-auctions-trois-rivieres",
    "/vehicle-auctions-longueuil",
    "/encheres-vehicules-montreal",
    "/encheres-vehicules-quebec-ville",
    "/encheres-vehicules-sherbrooke",
    "/encheres-vehicules-laval",
    "/encheres-vehicules-gatineau",
    "/encheres-vehicules-saguenay",
    "/encheres-vehicules-trois-rivieres",
    "/encheres-vehicules-longueuil",
    "/storage-auctions-montreal",
    "/storage-auctions-quebec-city",
    "/storage-auctions-sherbrooke",
    "/storage-auctions-laval",
    "/encheres-entreposage-montreal",
    "/encheres-entreposage-quebec-ville",
    "/encheres-entreposage-sherbrooke",
    "/encheres-entreposage-laval",
    # iter358 — Quebec launch press release pages (EN + FR).
    "/press/quebec-launch",
    "/presse/lancement-quebec",
)


def is_prerender_eligible(path: str) -> bool:
    """True if the given path should be prerendered for crawlers."""
    if path.startswith("/api/") or path.startswith("/static/") or path.startswith("/build/"):
        return False
    if any(path.endswith(ext) for ext in (".js", ".css", ".png", ".jpg", ".jpeg", ".webp", ".svg", ".ico", ".map", ".txt", ".xml", ".json", ".pdf", ".woff", ".woff2", ".ttf")):
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


# ─── Ingress middleware ────────────────────────────────────────────────
class BotPrerenderMiddleware(BaseHTTPMiddleware):
    """iter362 — SOLE bot-prerender path (FastAPI-only architecture).

    When a request:
      • is a GET,
      • has a crawler User-Agent (or `?_ssr=1` debug flag),
      • targets a prerender-eligible path,
    we short-circuit the SPA response with prerendered HTML inline —
    NO redirect to `/api/prerender/*` (bots must receive the HTML at the
    ORIGINAL URL so canonical URLs match what Google indexes).

    Real users continue to hit the SPA build served by the frontend
    container. Every response includes `X-Prerender-Version` +
    `X-Prerender-UA-Match` headers for production diagnosis, plus a
    structured `[PRERENDER]` log line at INFO level.
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

        # iter362 — Production diagnostic log. This line is what Charbel
        # greps for in Emergent logs to confirm middleware fires on prod.
        logger.info(
            f"[PRERENDER] Bot detected: ua='{ua[:80]}' path='{path}' lang='{lang}' "
            f"force_ssr={force_ssr} → serving SSR inline"
        )

        try:
            from deps import get_db
            db = get_db()
            async def _run():
                ctx = await resolve_route(db, path, lang)
                return render_html(ctx)
            html = await asyncio.wait_for(_run(), timeout=8.0)
            return HTMLResponse(
                content=html,
                status_code=200,
                headers={
                    # Explicit media type + charset (belt & suspenders for
                    # crawlers that check Content-Type before parsing HTML).
                    "Content-Type": "text/html; charset=utf-8",
                    "Cache-Control": "public, max-age=60, s-maxage=300",
                    "X-Prerender-Version": "iter362",
                    "X-Prerender-UA-Match": "1",
                    # Vary tells intermediate caches the response depends
                    # on the request UA — protects human SPA cache from
                    # being served bot HTML (and vice versa).
                    "Vary": "User-Agent, Accept-Language",
                },
            )
        except asyncio.TimeoutError:
            logger.error(f"[PRERENDER] budget exceeded 8s path={path!r} ua={ua[:80]!r}")
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"[PRERENDER] failed for path={path!r} ua={ua[:80]!r}: {exc} — "
                f"falling back to SPA"
            )
            return await call_next(request)
