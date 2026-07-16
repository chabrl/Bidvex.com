"""
iter307 — Nightly Sitemap & Robots Regenerator
================================================

Writes `/app/frontend/public/sitemap.xml` + `/app/frontend/public/robots.txt`
with the FULL dynamic content (all static pages + every active listing).

Why a file (instead of a dynamic backend route at /sitemap.xml)?
  • Kubernetes ingress routes non-/api paths to the frontend SPA, so
    bidvex.com/sitemap.xml is served from the frontend container.
  • A nightly file regen guarantees the static file IS the dynamic feed.
  • Search engines (Google/Bing) re-crawl daily, so a fresh file at 2am
    ET is effectively a live sitemap from their perspective.

Scheduler hook: `scheduler.add_job` in server.py runs this every day at 02:00 ET.

This module is also safe to call directly from a Python REPL for ops debugging.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import List

logger = logging.getLogger(__name__)

PUBLIC_HOST = os.environ.get("PUBLIC_HOST", "https://www.bidvex.com").rstrip("/")

SITEMAP_PATH = "/app/frontend/public/sitemap.xml"
ROBOTS_PATH = "/app/frontend/public/robots.txt"

STATIC_PAGES = [
    ("/", "weekly", 1.0),
    ("/marketplace", "hourly", 0.95),
    ("/items", "hourly", 0.95),
    ("/lots", "hourly", 0.9),
    ("/lots-auction", "hourly", 0.9),
    ("/vehicle-auctions", "weekly", 0.7),
    ("/storage-auctions", "hourly", 0.9),
    ("/storage-auctions/how-it-works", "monthly", 0.5),
    ("/storage-auctions/terms", "monthly", 0.4),
    ("/storage-auctions/for-facilities", "monthly", 0.5),
    ("/become-a-broker", "weekly", 0.7),
    ("/broker-directory", "weekly", 0.7),
    ("/contact", "monthly", 0.5),
    ("/about", "monthly", 0.5),
    ("/about-us", "monthly", 0.5),
    ("/how-it-works", "monthly", 0.5),
    ("/privacy-policy", "yearly", 0.3),
    ("/terms-of-service", "yearly", 0.3),
    ("/legal/terms", "yearly", 0.3),
    ("/legal/privacy", "yearly", 0.3),
    ("/legal/refunds", "yearly", 0.3),
    ("/legal/prohibited", "yearly", 0.3),
]


def _xml_url(loc: str, lastmod: str = "", changefreq: str = "weekly", priority: float = 0.5) -> str:
    parts = ["  <url>", f"    <loc>{loc}</loc>"]
    if lastmod:
        parts.append(f"    <lastmod>{lastmod}</lastmod>")
    parts.append(f"    <changefreq>{changefreq}</changefreq>")
    parts.append(f"    <priority>{priority:.2f}</priority>")
    parts.append("  </url>")
    return "\n".join(parts)


def _format_lastmod(value) -> str:
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


async def regenerate_sitemap_and_robots(db) -> dict:
    """Build a fresh sitemap from the live DB and write to the frontend
    static directory. Returns counts {static, listings, vehicles, lots,
    storage, total} for logging.
    """
    urls: List[str] = []
    for path, freq, prio in STATIC_PAGES:
        urls.append(_xml_url(f"{PUBLIC_HOST}{path}", changefreq=freq, priority=prio))

    counts = {"static": len(STATIC_PAGES), "listings": 0,
              "vehicles": 0, "lots": 0, "storage": 0}

    # Marketplace listings
    try:
        async for l in db.listings.find(
            {"status": "active"},
            {"_id": 0, "id": 1, "updated_at": 1, "listing_type": 1},
        ).limit(2000):
            lid = l.get("id")
            if not lid:
                continue
            ltype = (l.get("listing_type") or "").lower()
            path = f"/vehicle-auctions/{lid}" if ltype in ("vehicle", "vehicle_auction") else f"/listing/{lid}"
            urls.append(_xml_url(
                f"{PUBLIC_HOST}{path}",
                lastmod=_format_lastmod(l.get("updated_at")),
                changefreq="hourly", priority=0.9,
            ))
            if ltype in ("vehicle", "vehicle_auction"):
                counts["vehicles"] += 1
            else:
                counts["listings"] += 1
    except Exception as e:
        logger.warning(f"[iter307 sitemap] listings query failed: {e}")

    # Multi-item lots
    try:
        async for l in db.multi_item_listings.find(
            {"status": "active"},
            {"_id": 0, "id": 1, "updated_at": 1},
        ).limit(1000):
            lid = l.get("id")
            if not lid:
                continue
            urls.append(_xml_url(
                f"{PUBLIC_HOST}/lots/{lid}",
                lastmod=_format_lastmod(l.get("updated_at")),
                changefreq="hourly", priority=0.85,
            ))
            counts["lots"] += 1
    except Exception as e:
        logger.warning(f"[iter307 sitemap] lots query failed: {e}")

    # Storage auctions
    try:
        async for s in db.storage_auctions.find(
            {"status": "active"},
            {"_id": 0, "id": 1, "updated_at": 1},
        ).limit(1000):
            sid = s.get("id")
            if not sid:
                continue
            urls.append(_xml_url(
                f"{PUBLIC_HOST}/storage-auctions/{sid}",
                lastmod=_format_lastmod(s.get("updated_at")),
                changefreq="hourly", priority=0.85,
            ))
            counts["storage"] += 1
    except Exception as e:
        logger.warning(f"[iter307 sitemap] storage query failed: {e}")

    # Dedicated vehicle_listings collection (legacy / future-proof)
    try:
        async for v in db.vehicle_listings.find(
            {"status": "active"},
            {"_id": 0, "id": 1, "updated_at": 1},
        ).limit(1000):
            vid = v.get("id")
            if not vid:
                continue
            urls.append(_xml_url(
                f"{PUBLIC_HOST}/vehicle-auctions/{vid}",
                lastmod=_format_lastmod(v.get("updated_at")),
                changefreq="hourly", priority=0.85,
            ))
            counts["vehicles"] += 1
    except Exception as e:
        logger.warning(f"[iter307 sitemap] vehicle_listings query failed: {e}")

    counts["total"] = counts["static"] + counts["listings"] + counts["vehicles"] + counts["lots"] + counts["storage"]

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        + "\n".join(urls)
        + "\n</urlset>\n"
    )

    # Ensure target dir exists, then atomically write.
    try:
        os.makedirs(os.path.dirname(SITEMAP_PATH), exist_ok=True)
        tmp = SITEMAP_PATH + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(body)
        os.replace(tmp, SITEMAP_PATH)
    except Exception as e:
        logger.error(f"[iter307 sitemap] write failed: {e}")
        raise

    # Also regenerate robots.txt so the Sitemap directive uses PUBLIC_HOST.
    robots_body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /dashboard\n"
        "Disallow: /api/\n"
        "Allow: /api/feeds/\n\n"
        f"Sitemap: {PUBLIC_HOST}/sitemap.xml\n"
    )
    try:
        with open(ROBOTS_PATH, "w", encoding="utf-8") as f:
            f.write(robots_body)
    except Exception as e:
        logger.error(f"[iter307 sitemap] robots write failed: {e}")

    logger.info(f"[iter307 sitemap] Regenerated {SITEMAP_PATH}: {counts}")
    return counts
