"""
BidVex — Dynamic SEO endpoints
==============================
Generates /sitemap.xml (with active listings) and /robots.txt at request time.
Mounted at app-level (not /api) so search engines can reach them directly.
"""
import os
from datetime import datetime
from typing import List, Dict, Any

from fastapi import APIRouter, Request
from fastapi.responses import Response

from deps import get_db


sitemap_router = APIRouter()

PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "https://bidvex.com").rstrip("/")

STATIC_PAGES = [
    ("/", "weekly", 1.0),
    ("/marketplace", "hourly", 0.95),
    ("/lots-auction", "hourly", 0.9),
    ("/lots", "hourly", 0.9),
    ("/vehicle-auctions", "weekly", 0.7),
    ("/storage-auctions", "hourly", 0.9),
    # iter259 — Partner program is now admin-managed; no public landing
    # page. Removed `/promotions/partners` from the sitemap.
    ("/become-a-broker", "weekly", 0.7),
    ("/broker-directory", "weekly", 0.7),
    ("/contact", "monthly", 0.5),
    ("/about", "monthly", 0.5),
    ("/about-us", "monthly", 0.5),
    ("/how-it-works", "monthly", 0.5),
    ("/storage-auctions/how-it-works", "monthly", 0.5),
    ("/storage-auctions/terms", "monthly", 0.4),
    ("/storage-auctions/for-facilities", "monthly", 0.5),
    ("/privacy-policy", "yearly", 0.3),
    ("/terms-of-service", "yearly", 0.3),
]


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


def _xml_url(loc: str, lastmod: str = "", changefreq: str = "weekly", priority: float = 0.5) -> str:
    parts = [f"  <url>", f"    <loc>{loc}</loc>"]
    if lastmod:
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
    parts.append(f"    <changefreq>{changefreq}</changefreq>")
    parts.append(f"    <priority>{priority:.2f}</priority>")
    parts.append("  </url>")
    return "\n".join(parts)


@sitemap_router.get("/sitemap.xml", include_in_schema=False)
async def sitemap(request: Request):
    """Dynamic sitemap including the most recent active listings."""
    db = get_db()
    base = PUBLIC_HOST or f"{request.url.scheme}://{request.url.netloc}"

    urls: List[str] = []
    for path, changefreq, priority in STATIC_PAGES:
        urls.append(_xml_url(f"{base}{path}", changefreq=changefreq, priority=priority))

    if db is not None:
        try:
            listings = await db.listings.find(
                {"status": "active"},
                {"_id": 0, "id": 1, "updated_at": 1},
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
                ))
        except Exception:
            pass

        try:
            storage = await db.storage_auctions.find(
                {"status": "active"},
                {"_id": 0, "id": 1, "updated_at": 1},
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
                ))
        except Exception:
            pass

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )
    return Response(content=body, media_type="application/xml")


@sitemap_router.get("/robots.txt", include_in_schema=False)
async def robots(request: Request):
    base = PUBLIC_HOST or f"{request.url.scheme}://{request.url.netloc}"
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /dashboard\n"
        "Disallow: /auth\n"
        "Disallow: /api/\n\n"
        f"Sitemap: {base}/sitemap.xml\n"
        f"Sitemap: {base}/api/feeds/google\n"
    )
    return Response(content=body, media_type="text/plain")
