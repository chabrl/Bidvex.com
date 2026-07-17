"""
BidVex — Dynamic SEO endpoints (iter356 rewrite)
==================================================
Endpoints:
    /sitemap.xml              — legacy single-file sitemap (kept for backward compat)
    /sitemap_index.xml        — NEW: sitemap-of-sitemaps for scale (P1-H1)
    /sitemap-static.xml       — NEW: static pages + regional landings
    /sitemap-listings.xml     — NEW: marketplace listings (up to 5,000)
    /sitemap-vehicles.xml     — NEW: vehicle auctions (up to 5,000)
    /sitemap-storage.xml      — NEW: storage auctions (up to 5,000)
    /sitemap-lots.xml         — NEW: multi-item lots (up to 5,000)
    /sitemap-sellers.xml      — NEW: seller/dealer/broker profiles (up to 5,000, P1-H2)
    /robots.txt               — dynamic robots (unchanged apart from sitemap_index reference)

Google spec constraints per file: 50,000 URLs, 50 MiB uncompressed.
We cap each sub-sitemap at 5,000 URLs to keep responses fast + cacheable.

Image sitemap extension (P1-M2): each auction/vehicle URL includes an
`<image:image>` block with the primary listing photo — unlocks Google Images
indexing which drives long-tail visual-search traffic.
"""
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import logging

from fastapi import APIRouter, Request
from fastapi.responses import Response

from deps import get_db


logger = logging.getLogger(__name__)

sitemap_router = APIRouter()

# iter356 — canonical alignment (P0-C2): default MUST be the canonical
# `www.bidvex.com` host, not the apex. Log a warning if PUBLIC_HOST is
# missing so we notice env drift in preview/prod.
_DEFAULT_HOST = "https://www.bidvex.com"
_PUBLIC_HOST_RAW = os.environ.get("PUBLIC_HOST")
if not _PUBLIC_HOST_RAW:
    logger.warning(
        "[iter356 sitemap] PUBLIC_HOST env var not set — defaulting to %s. "
        "Set PUBLIC_HOST in production to avoid canonical drift.",
        _DEFAULT_HOST,
    )
PUBLIC_HOST = (_PUBLIC_HOST_RAW or _DEFAULT_HOST).rstrip("/")


# ─── Static + regional landing page catalog ────────────────────────────
STATIC_PAGES: List[tuple] = [
    ("/", "weekly", 1.0),
    ("/marketplace", "hourly", 0.95),
    ("/lots-auction", "hourly", 0.9),
    ("/lots", "hourly", 0.9),
    ("/vehicle-auctions", "weekly", 0.85),
    ("/storage-auctions", "hourly", 0.9),
    ("/broker-directory", "weekly", 0.7),
    ("/become-a-broker", "weekly", 0.7),
    ("/contact", "monthly", 0.5),
    ("/about", "monthly", 0.5),
    ("/about-us", "monthly", 0.5),
    ("/how-it-works", "monthly", 0.5),
    ("/faq", "monthly", 0.7),
    ("/storage-auctions/how-it-works", "monthly", 0.5),
    ("/storage-auctions/terms", "monthly", 0.4),
    ("/storage-auctions/for-facilities", "monthly", 0.5),
    ("/privacy-policy", "yearly", 0.3),
    ("/terms-of-service", "yearly", 0.3),
    # iter356 — Regional SEO landing pages (P1-H3)
    ("/car-auctions-canada", "weekly", 0.85),
    ("/vehicle-auctions-canada", "weekly", 0.85),
    ("/equipment-auctions-canada", "weekly", 0.85),
    ("/vehicle-auctions-quebec", "weekly", 0.85),
    ("/vehicle-auctions-ontario", "weekly", 0.85),
    ("/vehicle-auctions-british-columbia", "weekly", 0.8),
    ("/vehicle-auctions-alberta", "weekly", 0.8),
    ("/storage-auctions-quebec", "weekly", 0.85),
    ("/storage-auctions-ontario", "weekly", 0.85),
    ("/storage-auctions-british-columbia", "weekly", 0.8),
    # French Quebec twins
    ("/encheres-vehicules-quebec", "weekly", 0.85),
    ("/encheres-entreposage-quebec", "weekly", 0.85),
]


# Sitemap URL cap per Google spec.
_SUBSITEMAP_LIMIT = 5000


def _now_iso_date() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _format_lastmod(value: Any) -> str:
    """Best-effort ISO 8601 date for <lastmod>. Returns '' when unparsable."""
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d")
        except Exception:
            return ""
    return ""


def _first_image(doc: Dict[str, Any]) -> Optional[str]:
    """Extract first S3/HTTPS image URL from a listing doc (or its lots)."""
    imgs = doc.get("images") or doc.get("photos") or []
    for cand in imgs:
        if isinstance(cand, str) and cand.startswith("http"):
            return cand
    for lot in (doc.get("lots") or []):
        for cand in (lot.get("images") or lot.get("photos") or []):
            if isinstance(cand, str) and cand.startswith("http"):
                return cand
    return None


def _xml_escape(text: str) -> str:
    """Minimal XML escape — sufficient for URLs + English/French text."""
    return (
        text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
    )


def _xml_url(
    loc: str,
    lastmod: str = "",
    changefreq: str = "weekly",
    priority: float = 0.5,
    image_url: Optional[str] = None,
    image_title: Optional[str] = None,
) -> str:
    """Emit a single <url> block, optionally with an image:image extension."""
    parts = ["  <url>", f"    <loc>{_xml_escape(loc)}</loc>"]
    if lastmod:
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
    parts.append(f"    <changefreq>{changefreq}</changefreq>")
    parts.append(f"    <priority>{priority:.2f}</priority>")
    if image_url:
        parts.append("    <image:image>")
        parts.append(f"      <image:loc>{_xml_escape(image_url)}</image:loc>")
        if image_title:
            parts.append(f"      <image:title>{_xml_escape(image_title[:200])}</image:title>")
        parts.append("    </image:image>")
    parts.append("  </url>")
    return "\n".join(parts)


def _wrap_urlset(urls: List[str], with_image_ns: bool = False) -> str:
    """Wrap a list of <url> blocks in a valid urlset envelope."""
    xmlns_extra = (
        ' xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"'
        if with_image_ns else ""
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"{xmlns_extra}>\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )


def _sitemap_response(body: str) -> Response:
    return Response(
        content=body,
        media_type="application/xml",
        headers={"Cache-Control": "public, max-age=300, s-maxage=1800"},
    )


# ═══════════════════════════════════════════════════════════════════════
#  SITEMAP INDEX (P1-H1) — sitemap-of-sitemaps
# ═══════════════════════════════════════════════════════════════════════

@sitemap_router.get("/sitemap_index.xml", include_in_schema=False)
async def sitemap_index(request: Request):
    """Master index pointing at all sub-sitemaps. Submit THIS to Google
    Search Console — Google will discover every sub-sitemap automatically."""
    base = PUBLIC_HOST or f"{request.url.scheme}://{request.url.netloc}"
    today = _now_iso_date()
    subs = [
        ("sitemap-static.xml",    today),
        ("sitemap-listings.xml",  today),
        ("sitemap-vehicles.xml",  today),
        ("sitemap-storage.xml",   today),
        ("sitemap-lots.xml",      today),
        ("sitemap-sellers.xml",   today),
    ]
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<sitemapindex xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for slug, mod in subs:
        parts.append("  <sitemap>")
        parts.append(f"    <loc>{base}/{slug}</loc>")
        parts.append(f"    <lastmod>{mod}</lastmod>")
        parts.append("  </sitemap>")
    parts.append("</sitemapindex>")
    return _sitemap_response("\n".join(parts) + "\n")


# ═══════════════════════════════════════════════════════════════════════
#  SUB-SITEMAPS (P1-H1)
# ═══════════════════════════════════════════════════════════════════════

@sitemap_router.get("/sitemap-static.xml", include_in_schema=False)
async def sitemap_static(request: Request):
    """Static pages + regional landings. lastmod = deploy date (best-effort)."""
    base = PUBLIC_HOST or f"{request.url.scheme}://{request.url.netloc}"
    today = _now_iso_date()  # iter356 M1 — lastmod on static entries
    urls = [
        _xml_url(f"{base}{path}", lastmod=today, changefreq=cf, priority=pr)
        for path, cf, pr in STATIC_PAGES
    ]
    return _sitemap_response(_wrap_urlset(urls))


@sitemap_router.get("/sitemap-listings.xml", include_in_schema=False)
async def sitemap_listings(request: Request):
    db = get_db()
    base = PUBLIC_HOST or f"{request.url.scheme}://{request.url.netloc}"
    urls: List[str] = []
    if db is not None:
        try:
            cursor = db.listings.find(
                {"status": "active", "listing_type": {"$ne": "vehicle"}},
                {"_id": 0, "id": 1, "updated_at": 1, "title": 1,
                 "images": 1, "photos": 1},
            ).limit(_SUBSITEMAP_LIMIT)
            async for l in cursor:
                lid = l.get("id")
                if not lid:
                    continue
                img = _first_image(l)
                urls.append(_xml_url(
                    f"{base}/listing/{lid}",
                    lastmod=_format_lastmod(l.get("updated_at")),
                    changefreq="hourly",
                    priority=0.9,
                    image_url=img,
                    image_title=l.get("title"),
                ))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[iter356 sitemap-listings] query failed: {exc}")
    return _sitemap_response(_wrap_urlset(urls, with_image_ns=True))


@sitemap_router.get("/sitemap-vehicles.xml", include_in_schema=False)
async def sitemap_vehicles(request: Request):
    db = get_db()
    base = PUBLIC_HOST or f"{request.url.scheme}://{request.url.netloc}"
    urls: List[str] = []
    if db is not None:
        try:
            # Vehicle auctions live in `listings` with listing_type in
            # {"vehicle", "vehicle_auction"} OR in dedicated vehicle_multi_lot_auctions.
            cursor = db.listings.find(
                {"status": "active",
                 "listing_type": {"$in": ["vehicle", "vehicle_auction"]}},
                {"_id": 0, "id": 1, "updated_at": 1, "title": 1,
                 "images": 1, "photos": 1},
            ).limit(_SUBSITEMAP_LIMIT)
            async for v in cursor:
                vid = v.get("id")
                if not vid:
                    continue
                img = _first_image(v)
                urls.append(_xml_url(
                    f"{base}/vehicle-auctions/{vid}",
                    lastmod=_format_lastmod(v.get("updated_at")),
                    changefreq="hourly",
                    priority=0.85,
                    image_url=img,
                    image_title=v.get("title"),
                ))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[iter356 sitemap-vehicles] query failed: {exc}")
    return _sitemap_response(_wrap_urlset(urls, with_image_ns=True))


@sitemap_router.get("/sitemap-storage.xml", include_in_schema=False)
async def sitemap_storage(request: Request):
    db = get_db()
    base = PUBLIC_HOST or f"{request.url.scheme}://{request.url.netloc}"
    urls: List[str] = []
    if db is not None:
        try:
            cursor = db.storage_auctions.find(
                {"status": "active"},
                {"_id": 0, "id": 1, "updated_at": 1, "title": 1,
                 "images": 1, "photos": 1},
            ).limit(_SUBSITEMAP_LIMIT)
            async for s in cursor:
                sid = s.get("id")
                if not sid:
                    continue
                img = _first_image(s)
                urls.append(_xml_url(
                    f"{base}/storage-auctions/{sid}",
                    lastmod=_format_lastmod(s.get("updated_at")),
                    changefreq="hourly",
                    priority=0.85,
                    image_url=img,
                    image_title=s.get("title"),
                ))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[iter356 sitemap-storage] query failed: {exc}")
    return _sitemap_response(_wrap_urlset(urls, with_image_ns=True))


@sitemap_router.get("/sitemap-lots.xml", include_in_schema=False)
async def sitemap_lots(request: Request):
    db = get_db()
    base = PUBLIC_HOST or f"{request.url.scheme}://{request.url.netloc}"
    urls: List[str] = []
    if db is not None:
        try:
            cursor = db.multi_item_listings.find(
                {"status": "active"},
                {"_id": 0, "id": 1, "updated_at": 1, "title": 1,
                 "images": 1, "lots": 1},
            ).limit(_SUBSITEMAP_LIMIT)
            async for lot in cursor:
                lid = lot.get("id")
                if not lid:
                    continue
                img = _first_image(lot)
                urls.append(_xml_url(
                    f"{base}/lots/{lid}",
                    lastmod=_format_lastmod(lot.get("updated_at")),
                    changefreq="hourly",
                    priority=0.85,
                    image_url=img,
                    image_title=lot.get("title"),
                ))
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[iter356 sitemap-lots] query failed: {exc}")
    return _sitemap_response(_wrap_urlset(urls, with_image_ns=True))


@sitemap_router.get("/sitemap-sellers.xml", include_in_schema=False)
async def sitemap_sellers(request: Request):
    """iter356 (P1-H2) — Seller, dealer, and broker profile pages.

    Includes:
      - /storefront/{slug}          — public seller storefronts
      - /dealer/{slug}              — dealer public pages
      - /broker/{slug}              — broker public pages
      - /prospect/{slug}            — prospect finder profiles
    """
    db = get_db()
    base = PUBLIC_HOST or f"{request.url.scheme}://{request.url.netloc}"
    urls: List[str] = []
    if db is None:
        return _sitemap_response(_wrap_urlset(urls))

    async def _harvest(collection_name: str, url_prefix: str, priority: float = 0.6,
                       slug_fields: tuple = ("slug", "handle", "public_slug", "id")):
        """Emit sitemap entries for any user-facing collection."""
        try:
            coll = db[collection_name]
            cursor = coll.find(
                {"is_public": {"$ne": False}},
                {"_id": 0, "slug": 1, "handle": 1, "public_slug": 1,
                 "id": 1, "updated_at": 1},
            ).limit(_SUBSITEMAP_LIMIT)
            async for doc in cursor:
                slug = next((doc.get(f) for f in slug_fields if doc.get(f)), None)
                if not slug:
                    continue
                urls.append(_xml_url(
                    f"{base}{url_prefix}{slug}",
                    lastmod=_format_lastmod(doc.get("updated_at")),
                    changefreq="weekly",
                    priority=priority,
                ))
        except Exception as exc:  # noqa: BLE001
            logger.info(f"[iter356 sellers-sitemap] {collection_name} skipped: {exc}")

    # Sellers (storefronts)
    await _harvest("sellers",   "/storefront/", priority=0.7)
    # Dealers (vehicle dealers)
    await _harvest("dealers",   "/dealer/",     priority=0.75)
    # Brokers
    await _harvest("brokers",   "/broker/",     priority=0.75)
    # Prospect Finder profiles (contractors)
    await _harvest("prospects", "/prospect/",   priority=0.5)

    return _sitemap_response(_wrap_urlset(urls))


# ═══════════════════════════════════════════════════════════════════════
#  Legacy monolithic sitemap (kept for backward compat — SC already
#  submitted this URL. It now points at STATIC_PAGES + a sample of each
#  dynamic collection).
# ═══════════════════════════════════════════════════════════════════════

@sitemap_router.get("/sitemap.xml", include_in_schema=False)
async def sitemap(request: Request):
    """Legacy single-file sitemap. Retained for the Search Console entry
    already submitted at iter268. New crawlers should follow
    /sitemap_index.xml for the full scaled index."""
    db = get_db()
    base = PUBLIC_HOST or f"{request.url.scheme}://{request.url.netloc}"
    today = _now_iso_date()

    urls: List[str] = []
    for path, changefreq, priority in STATIC_PAGES:
        urls.append(_xml_url(
            f"{base}{path}", lastmod=today,
            changefreq=changefreq, priority=priority,
        ))

    if db is not None:
        try:
            listings = await db.listings.find(
                {"status": "active"},
                {"_id": 0, "id": 1, "updated_at": 1, "title": 1,
                 "images": 1, "photos": 1},
            ).limit(1000).to_list(1000)
            for listing in listings:
                lid = listing.get("id")
                if not lid:
                    continue
                urls.append(_xml_url(
                    f"{base}/listing/{lid}",
                    lastmod=_format_lastmod(listing.get("updated_at")),
                    changefreq="hourly",
                    priority=0.9,
                    image_url=_first_image(listing),
                    image_title=listing.get("title"),
                ))
        except Exception:
            pass
        try:
            storage = await db.storage_auctions.find(
                {"status": "active"},
                {"_id": 0, "id": 1, "updated_at": 1, "title": 1,
                 "images": 1, "photos": 1},
            ).limit(500).to_list(500)
            for auc in storage:
                aid = auc.get("id")
                if not aid:
                    continue
                urls.append(_xml_url(
                    f"{base}/storage-auctions/{aid}",
                    lastmod=_format_lastmod(auc.get("updated_at")),
                    changefreq="hourly",
                    priority=0.85,
                    image_url=_first_image(auc),
                    image_title=auc.get("title"),
                ))
        except Exception:
            pass
        try:
            lots = await db.multi_item_listings.find(
                {"status": "active"},
                {"_id": 0, "id": 1, "updated_at": 1, "title": 1,
                 "images": 1, "lots": 1},
            ).limit(500).to_list(500)
            for lot in lots:
                lid = lot.get("id")
                if not lid:
                    continue
                urls.append(_xml_url(
                    f"{base}/lots/{lid}",
                    lastmod=_format_lastmod(lot.get("updated_at")),
                    changefreq="hourly",
                    priority=0.85,
                    image_url=_first_image(lot),
                    image_title=lot.get("title"),
                ))
        except Exception:
            pass

    return _sitemap_response(_wrap_urlset(urls, with_image_ns=True))


# ═══════════════════════════════════════════════════════════════════════
#  robots.txt (unchanged apart from sitemap_index)
# ═══════════════════════════════════════════════════════════════════════

@sitemap_router.get("/robots.txt", include_in_schema=False)
async def robots(request: Request):
    base = PUBLIC_HOST or f"{request.url.scheme}://{request.url.netloc}"
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /dashboard\n"
        "Disallow: /auth\n"
        "Disallow: /api/\n"
        "Allow: /api/feeds/\n\n"
        # iter356 — declare the sitemap index first so crawlers discover all
        # sub-sitemaps in one pass. Old /sitemap.xml kept for backward compat.
        f"Sitemap: {base}/sitemap_index.xml\n"
        f"Sitemap: {base}/sitemap.xml\n"
        f"Sitemap: {base}/api/feeds/google\n"
        f"Sitemap: {base}/api/feeds/meta-catalog.json\n"
    )
    return Response(content=body, media_type="text/plain")
