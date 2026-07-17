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
from fastapi.responses import Response, RedirectResponse

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
    # iter357 — 24 QC city landing pages (12 cities × 2 languages)
    ("/vehicle-auctions-montreal", "weekly", 0.8),
    ("/vehicle-auctions-quebec-city", "weekly", 0.8),
    ("/vehicle-auctions-sherbrooke", "weekly", 0.8),
    ("/vehicle-auctions-laval", "weekly", 0.8),
    ("/vehicle-auctions-gatineau", "weekly", 0.8),
    ("/vehicle-auctions-saguenay", "weekly", 0.75),
    ("/vehicle-auctions-trois-rivieres", "weekly", 0.75),
    ("/vehicle-auctions-longueuil", "weekly", 0.8),
    ("/encheres-vehicules-montreal", "weekly", 0.8),
    ("/encheres-vehicules-quebec-ville", "weekly", 0.8),
    ("/encheres-vehicules-sherbrooke", "weekly", 0.8),
    ("/encheres-vehicules-laval", "weekly", 0.8),
    ("/encheres-vehicules-gatineau", "weekly", 0.8),
    ("/encheres-vehicules-saguenay", "weekly", 0.75),
    ("/encheres-vehicules-trois-rivieres", "weekly", 0.75),
    ("/encheres-vehicules-longueuil", "weekly", 0.8),
    ("/storage-auctions-montreal", "weekly", 0.8),
    ("/storage-auctions-quebec-city", "weekly", 0.8),
    ("/storage-auctions-sherbrooke", "weekly", 0.8),
    ("/storage-auctions-laval", "weekly", 0.8),
    ("/encheres-entreposage-montreal", "weekly", 0.8),
    ("/encheres-entreposage-quebec-ville", "weekly", 0.8),
    ("/encheres-entreposage-sherbrooke", "weekly", 0.8),
    ("/encheres-entreposage-laval", "weekly", 0.8),
    # iter358 — Quebec launch press release pages (EN + FR).
    ("/press/quebec-launch", "monthly", 0.8),
    ("/presse/lancement-quebec", "monthly", 0.8),
]


# Sitemap URL cap per Google spec.
_SUBSITEMAP_LIMIT = 5000


# iter359 — EN↔FR slug map (mirrors frontend/src/i18n/urlMap.js).
# The sitemap emits BOTH sides of every pair with reciprocal
# <xhtml:link rel="alternate"> tags — Google requires each variant to
# self-declare its alternates for canonical clustering.
EN_TO_FR_SLUGS: Dict[str, str] = {
    "/":                                    "/",
    "/marketplace":                         "/marche",
    "/lots":                                "/lots",
    "/lots-auction":                        "/lots",
    "/vehicle-auctions":                    "/encheres-vehicules",
    "/storage-auctions":                    "/encheres-entreposage",
    "/how-it-works":                        "/comment-ca-marche",
    "/how-brokers-work":                    "/comment-fonctionnent-les-courtiers",
    "/about":                               "/a-propos",
    "/about-us":                            "/a-propos",
    "/contact":                             "/contact",
    "/faq":                                 "/faq",
    "/pricing":                             "/tarifs",
    "/terms-of-service":                    "/conditions-utilisation",
    "/privacy-policy":                      "/politique-confidentialite",
    "/careers":                             "/carrieres",
    "/community":                           "/communaute",
    "/blogs":                               "/blogues",
    "/prohibited-items":                    "/articles-interdits",
    "/broker-directory":                    "/annuaire-courtiers",
    "/become-a-broker":                     "/devenir-courtier",
    "/become-a-partner":                    "/devenir-partenaire",
    "/press/quebec-launch":                 "/presse/lancement-quebec",
    # Regional cities
    "/vehicle-auctions-quebec":             "/encheres-vehicules-quebec",
    "/storage-auctions-quebec":             "/encheres-entreposage-quebec",
    "/vehicle-auctions-montreal":           "/encheres-vehicules-montreal",
    "/vehicle-auctions-quebec-city":        "/encheres-vehicules-quebec-ville",
    "/vehicle-auctions-sherbrooke":         "/encheres-vehicules-sherbrooke",
    "/vehicle-auctions-laval":              "/encheres-vehicules-laval",
    "/vehicle-auctions-gatineau":           "/encheres-vehicules-gatineau",
    "/vehicle-auctions-saguenay":           "/encheres-vehicules-saguenay",
    "/vehicle-auctions-trois-rivieres":     "/encheres-vehicules-trois-rivieres",
    "/vehicle-auctions-longueuil":          "/encheres-vehicules-longueuil",
    "/storage-auctions-montreal":           "/encheres-entreposage-montreal",
    "/storage-auctions-quebec-city":        "/encheres-entreposage-quebec-ville",
    "/storage-auctions-sherbrooke":         "/encheres-entreposage-sherbrooke",
    "/storage-auctions-laval":              "/encheres-entreposage-laval",
}
FR_TO_EN_SLUGS: Dict[str, str] = {v: k for k, v in EN_TO_FR_SLUGS.items()}


def _lang_pair_for(bare_path: str) -> Optional[tuple]:
    """
    Given a bare (no lang prefix) EN or FR path, return the tuple
    `(en_bare, fr_bare)`. Returns None if the path has no known FR twin
    (in which case we can't emit a hreflang alternate cluster).
    """
    if bare_path in EN_TO_FR_SLUGS:
        return (bare_path, EN_TO_FR_SLUGS[bare_path])
    if bare_path in FR_TO_EN_SLUGS:
        return (FR_TO_EN_SLUGS[bare_path], bare_path)
    return None


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
    hreflang_alternates: Optional[List[tuple]] = None,
) -> str:
    """Emit a single <url> block, optionally with an image:image extension.

    iter359 — `hreflang_alternates` is a list of `(hreflang_code, full_url)`
    tuples emitted as `<xhtml:link rel="alternate" hreflang="X" href="Y"/>`
    inside the `<url>` block. Every FR/EN twin gets an `x-default` entry
    pointing at the EN variant per Google's recommended pattern.
    """
    parts = ["  <url>", f"    <loc>{_xml_escape(loc)}</loc>"]
    # iter359 — hreflang cross-references FIRST (Google convention).
    if hreflang_alternates:
        for hreflang, href in hreflang_alternates:
            parts.append(
                f'    <xhtml:link rel="alternate" hreflang="{hreflang}" '
                f'href="{_xml_escape(href)}"/>'
            )
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


def _wrap_urlset(urls: List[str], with_image_ns: bool = False, with_xhtml_ns: bool = False) -> str:
    """Wrap a list of <url> blocks in a valid urlset envelope.

    iter359 — `with_xhtml_ns=True` adds the `xmlns:xhtml` namespace needed
    for `<xhtml:link rel="alternate">` hreflang blocks in sitemap-static.
    """
    xmlns_extra = ""
    if with_image_ns:
        xmlns_extra += ' xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"'
    if with_xhtml_ns:
        xmlns_extra += ' xmlns:xhtml="http://www.w3.org/1999/xhtml"'
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
    """Static pages + regional landings — iter359 emits DUAL EN + FR URLs
    with reciprocal `<xhtml:link rel="alternate">` hreflang blocks.

    Every page in `STATIC_PAGES` that has a known FR twin (per
    `EN_TO_FR_SLUGS`) gets:
      • Its EN `/en/<slug>` variant with alternates → en-CA, fr-CA, x-default
      • Its FR `/fr/<slug>` variant with alternates → en-CA, fr-CA, x-default

    Google recommends every URL in a hreflang cluster self-declare its
    alternates + include an x-default (fallback for other languages) —
    that's exactly what we emit here.

    Pages without a FR twin (e.g., `/lots-auction`) are emitted once at
    their bare path, unchanged (backward compat for legacy indexed URLs).
    """
    base = PUBLIC_HOST or f"{request.url.scheme}://{request.url.netloc}"
    today = _now_iso_date()

    urls: List[str] = []
    seen_pairs: set = set()  # Dedup: emit each EN/FR pair only once.

    for path, cf, pr in STATIC_PAGES:
        pair = _lang_pair_for(path)

        # Pages without a known FR twin — emit as-is (single URL, no alternates).
        if pair is None:
            urls.append(_xml_url(f"{base}{path}", lastmod=today, changefreq=cf, priority=pr))
            continue

        en_bare, fr_bare = pair
        if (en_bare, fr_bare) in seen_pairs:
            continue
        seen_pairs.add((en_bare, fr_bare))

        # Build the EN + FR absolute URLs, then the shared hreflang cluster.
        en_url = f"{base}/en{en_bare if en_bare != '/' else ''}"
        fr_url = f"{base}/fr{fr_bare if fr_bare != '/' else ''}"
        # Root case — /en/ and /fr/ have trailing slash for clarity.
        if en_bare == "/":
            en_url = f"{base}/en/"
            fr_url = f"{base}/fr/"

        alternates = [
            ("en-CA",      en_url),
            ("fr-CA",      fr_url),
            ("x-default",  en_url),  # EN is the default fallback per iter358 spec
        ]

        urls.append(_xml_url(en_url, lastmod=today, changefreq=cf, priority=pr,
                             hreflang_alternates=alternates))
        urls.append(_xml_url(fr_url, lastmod=today, changefreq=cf, priority=pr,
                             hreflang_alternates=alternates))

    return _sitemap_response(_wrap_urlset(urls, with_xhtml_ns=True))


# ═══════════════════════════════════════════════════════════════════════
#  iter359 — Root `/` Accept-Language 302 redirect
#  Bots + browsers landing at bare `/` get redirected to `/en/` or `/fr/`
#  based on the `Accept-Language` request header. This is what makes the
#  root URL indexable as a language-neutral entry point that fans out to
#  the correct localized canonical.
#
#  Executed at the FastAPI layer BEFORE any SPA rendering — the browser
#  receives a real HTTP 302 with a `Location:` header, not a JS redirect.
#  In production (`bidvex.com`), FastAPI serves the SPA build directly,
#  so this handler intercepts every naked root request.
# ═══════════════════════════════════════════════════════════════════════

def _detect_lang_from_accept_language(header: str) -> str:
    """
    Parse an `Accept-Language` header and return 'fr' if the first
    preferred locale is French, else 'en'. Empty/absent header → 'en'.

    Examples:
      "fr-CA,fr;q=0.9,en;q=0.8"    → 'fr'
      "en-US,en;q=0.9"             → 'en'
      "fr,en"                      → 'fr'
      "en-CA,fr-CA;q=0.9"          → 'en'
      "" or None                   → 'en'
    """
    if not header:
        return "en"
    # Take the first (highest-priority) locale token.
    first = header.split(",")[0].strip().lower()
    if first.startswith("fr"):
        return "fr"
    return "en"


@sitemap_router.get("/", include_in_schema=False)
async def root_lang_redirect(request: Request):
    """iter359 — 302 redirect from `/` to `/en/` or `/fr/` based on
    Accept-Language. This handler is registered on the main app via
    `include_router(sitemap_router)` and takes priority over the SPA
    catch-all (registered LAST in server.py)."""
    lang = _detect_lang_from_accept_language(request.headers.get("accept-language", ""))
    target = "/fr/" if lang == "fr" else "/en/"
    return RedirectResponse(url=target, status_code=302)


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
