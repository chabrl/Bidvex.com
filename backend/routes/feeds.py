"""
Phase 5 — Public Meta product catalog feed.

  GET /api/feeds/facebook-local        — CSV feed (default) for Meta ingestion
  GET /api/feeds/facebook-local?format=json  — JSON feed for admin + tests
  GET /api/feeds/facebook-local/meta   — health/monitoring snapshot

The CSV path is what Meta Business Manager points at. Meta's parser is RFC
4180 strict (CRLF line endings, double-quoted strings, escaped embedded
quotes, UTF-8 with no BOM).

The JSON path is what the Admin Feeds dashboard + the pytest regression
suite consume — it returns the SAME catalog data shaped as
`{"data": [...], "seed_padded": bool, "count": int}`.

Both endpoints are PUBLIC (no auth) so Meta's server-side fetcher can read
them. The CSV path also serves `Access-Control-Allow-Origin: *` so the same
catalog can power third-party retargeting if needed.
"""
from __future__ import annotations

import csv
import io
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from fastapi import APIRouter, Query, Request, Response, HTTPException, Depends
from fastapi.responses import PlainTextResponse

from deps import get_db, require_admin
from services import feed_cache
from services.feed_cache import (
    cache_set,
    get_cache_size,
    get_last_warmed_at,
    invalidate_feed_cache,
    make_cache_key,
)
from services.listing_seller_enrichment import enrich_listings_bulk_async
from services.meta_feed_mapper import (
    COLLECTION_TO_TYPE,
    FEED_REQUIRE_GEO,
    META_MIN_CATALOG_ITEMS,
    build_seed_items,
    map_listing_to_meta_item,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/feeds", tags=["feeds"])

# ── Config ────────────────────────────────────────────────────────────
FEED_MAX_ITEMS_PER_REQUEST = int(os.environ.get("FEED_MAX_ITEMS_PER_REQUEST", "2000"))
FEED_DEFAULT_LIMIT = 500
FEED_RATE_LIMIT_PER_MINUTE = int(os.environ.get("FEED_RATE_LIMIT_PER_MINUTE", "10"))
BIDVEX_BASE_URL = os.environ.get("BIDVEX_BASE_URL", "https://bidvex.com").rstrip("/")

# Lightweight per-IP throttle (no external dep)
_RL_WINDOW_SEC = 60
_RL_BUCKETS: Dict[str, List[float]] = {}


def _check_rate_limit(ip: str) -> None:
    import time
    now = time.time()
    bucket = _RL_BUCKETS.setdefault(ip, [])
    cutoff = now - _RL_WINDOW_SEC
    while bucket and bucket[0] < cutoff:
        bucket.pop(0)
    if len(bucket) >= FEED_RATE_LIMIT_PER_MINUTE:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    bucket.append(now)


# ── Collection iterator ──────────────────────────────────────────────
async def _walk_active_listings(
    db,
    *,
    province: Optional[str] = None,
    category: Optional[str] = None,
    type_filter: Optional[str] = None,
) -> List[Tuple[str, Dict[str, Any]]]:
    """Yields tuples (collection_listing_type, listing_doc) for every active listing
    across the marketplace, lots, vehicle and storage collections.

    `province`/`category`/`type_filter` are server-side narrowing filters
    so we don't pay to enrich + map items we'll drop anyway.
    """
    collections = list(COLLECTION_TO_TYPE.items())
    if type_filter:
        collections = [c for c in collections if c[1] == type_filter]

    query: Dict[str, Any] = {"status": "active"}
    if category:
        query["category"] = category
    if province:
        # Match both the iter217 normalizer aliases and stored case variants.
        from routes.marketplace import _normalize_region, _PROVINCE_ALIASES
        norm = _normalize_region(province)
        synonyms = sorted({k for k, v in _PROVINCE_ALIASES.items() if v == norm} | {norm}) if norm else [province]
        all_variants = synonyms + [s.upper() for s in synonyms]
        query["$or"] = [
            {"region":   {"$in": all_variants}},
            {"province": {"$in": all_variants}},
        ]

    out: List[Tuple[str, Dict[str, Any]]] = []
    for collection_name, listing_type in collections:
        coll = db[collection_name]
        async for doc in coll.find(query, {"_id": 0}):
            out.append((listing_type, doc))
    return out


# ── Builder used by cache-aside ──────────────────────────────────────
async def _build_feed_items(
    province: Optional[str],
    category: Optional[str],
    type_filter: Optional[str],
    limit: int,
    offset: int,
) -> Tuple[List[Dict[str, Any]], Dict[str, int]]:
    db = get_db()
    docs = await _walk_active_listings(
        db,
        province=province,
        category=category,
        type_filter=type_filter,
    )

    # Enrich every doc with seller_account_type / company name (iter217 helper).
    grouped: Dict[str, List[Dict[str, Any]]] = {}
    for ltype, doc in docs:
        grouped.setdefault(ltype, []).append(doc)
    for listings in grouped.values():
        await enrich_listings_bulk_async(db, listings)

    # Pre-load distinct seller docs for demo-account checks.
    seller_ids = list({d.get("seller_id") for _, d in docs if d.get("seller_id")})
    sellers_by_id: Dict[str, Dict[str, Any]] = {}
    if seller_ids:
        async for u in db.users.find(
            {"id": {"$in": seller_ids}},
            {"_id": 0, "id": 1, "is_demo_account": 1, "is_demo": 1, "demo": 1},
        ):
            sellers_by_id[u["id"]] = u

    exclusions = {
        "no_images": 0,
        "no_location": 0,
        "no_title": 0,
        "demo_account": 0,
        "moderation_pending": 0,
        "placeholder_used": 0,
        "seed_items_padded": 0,
    }

    items: List[Dict[str, Any]] = []
    for ltype, doc in docs:
        seller = sellers_by_id.get(doc.get("seller_id"), {})
        item = map_listing_to_meta_item(doc, ltype, seller, exclusions)
        if item is not None:
            items.append(item)

    # Meta Commerce Manager 5-product minimum: pad the UNFILTERED feed with
    # branded seed items when the live catalog has fewer than 5 eligible
    # listings. Province/category/type-filtered queries are NEVER padded so
    # the empty-NU integration test (and any future segment query) still
    # returns the true slice.
    is_unfiltered = (province is None and category is None and type_filter is None)
    if is_unfiltered and len(items) < META_MIN_CATALOG_ITEMS:
        seeds_needed = META_MIN_CATALOG_ITEMS - len(items)
        seeds = build_seed_items(seeds_needed)
        items.extend(seeds)
        exclusions["seed_items_padded"] = len(seeds)

    total_eligible = len(items)
    items = items[offset:offset + limit]

    logger.info(
        "FB feed built: %d included, %d excluded from %d total listings "
        "(exclusions=%s)",
        total_eligible,
        sum(exclusions.values()),
        len(docs),
        exclusions,
    )

    return items, exclusions


# ── Meta-compliant CSV column order ──────────────────────────────────
# Exact order locked by user spec. Header row is unquoted column names;
# every data cell is double-quoted (RFC 4180). CRLF line endings, UTF-8
# without BOM.
_CSV_COLUMNS: List[str] = [
    "id", "title", "description", "availability", "condition",
    "price", "link", "image_link", "brand", "latitude", "longitude",
    "neighborhood", "city", "region", "country", "postal_code",
    "additional_image_link", "google_product_category",
    "sale_price", "custom_label_0", "custom_label_1",
    "custom_label_2", "custom_label_3",
]


def _items_to_csv(items: List[Dict[str, Any]]) -> str:
    """Serialize feed items to a Meta-compliant CSV string.

    * Header row: unquoted column names in `_CSV_COLUMNS` order.
    * All data cells: double-quoted (`csv.QUOTE_ALL`).
    * Embedded quotes / commas escaped per RFC 4180.
    * Line endings: CRLF (`\\r\\n`).
    * Encoding: UTF-8 without BOM (handled by FastAPI's text Response).
    * Missing optional fields: rendered as empty string "" (not null).
    """
    buf = io.StringIO()
    # Header row — explicitly unquoted, written manually so the
    # column-name row stays plain `id,title,...` (Meta convention).
    buf.write(",".join(_CSV_COLUMNS))
    buf.write("\r\n")

    writer = csv.writer(
        buf,
        delimiter=",",
        quotechar='"',
        quoting=csv.QUOTE_ALL,
        lineterminator="\r\n",
    )
    for item in items:
        row = []
        for col in _CSV_COLUMNS:
            v = item.get(col, "")
            if v is None:
                v = ""
            row.append(str(v))
        writer.writerow(row)
    return buf.getvalue()


# ── Public feed endpoint ─────────────────────────────────────────────
@router.get("/facebook-local")
async def get_facebook_local_feed(
    request: Request,
    response: Response,
    limit: int = Query(FEED_DEFAULT_LIMIT, ge=1, le=FEED_MAX_ITEMS_PER_REQUEST),
    offset: int = Query(0, ge=0),
    province: Optional[str] = None,
    category: Optional[str] = None,
    type: Optional[str] = Query(None, description="marketplace|lots|vehicle|storage"),
    format: str = Query("csv", description="csv (default, Meta-compliant) | json"),
):
    """Public catalog feed for Meta Dynamic & Local Inventory Ads.

    Default response: **CSV** (Meta's preferred ingestion format — RFC 4180
    quoted, CRLF line endings, UTF-8 without BOM, `text/csv; charset=utf-8`).

    `?format=json` returns the legacy JSON shape used by the Admin Feeds
    dashboard and the pytest regression suite — shape:
    `{"data": [...], "seed_padded": bool, "count": int}`.

    No authentication required — Meta's crawler cannot authenticate.
    """
    _check_rate_limit(request.client.host if request.client else "anon")

    fmt = (format or "csv").lower().strip()
    if fmt not in ("csv", "json"):
        raise HTTPException(status_code=400, detail="format must be 'csv' or 'json'")

    key = make_cache_key(province, category, type, limit, offset)

    async def _builder():
        return await _build_feed_items(province, category, type, limit, offset)

    data, was_hit, exclusions = await feed_cache.get_or_build(key, _builder)
    seed_padded = bool(exclusions.get("seed_items_padded", 0))

    # Shared headers (Meta crawler + CORS + cache)
    response.headers["Cache-Control"] = "public, max-age=900"
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["X-Feed-Cache"] = "HIT" if was_hit else "MISS"

    if fmt == "json":
        return {
            "data":        data,
            "count":       len(data),
            "seed_padded": seed_padded,
        }

    # CSV path — Meta-compliant text/csv response.
    csv_body = _items_to_csv(data)
    return PlainTextResponse(
        content=csv_body,
        media_type="text/csv; charset=utf-8",
        headers={
            "Cache-Control":               "public, max-age=900",
            "Access-Control-Allow-Origin": "*",
            "X-Feed-Cache":                "HIT" if was_hit else "MISS",
            "X-Seed-Padded":               "true" if seed_padded else "false",
            "Content-Disposition":         'attachment; filename="bidvex-catalog.csv"',
        },
    )


# ── Feed metadata / health endpoint ──────────────────────────────────
@router.get("/facebook-local/meta")
async def get_facebook_local_feed_meta() -> Dict[str, Any]:
    """Returns feed health information for monitoring + admin dashboards.
    PUBLIC — no auth required so the same endpoint can power Meta's
    catalog-health webhooks and our internal admin UI."""
    db = get_db()

    # Count totals across all four collections in parallel.
    total_active = 0
    for coll_name in COLLECTION_TO_TYPE:
        total_active += await db[coll_name].count_documents({"status": "active"})

    # Build a non-paginated eligibility snapshot (cached for performance).
    key = make_cache_key(None, None, None, FEED_MAX_ITEMS_PER_REQUEST, 0)
    async def _builder():
        return await _build_feed_items(None, None, None, FEED_MAX_ITEMS_PER_REQUEST, 0)
    eligible_items, was_hit, exclusions = await feed_cache.get_or_build(key, _builder)

    last_warmed_ts = get_last_warmed_at()
    last_warmed_iso = (
        datetime.fromtimestamp(last_warmed_ts, tz=timezone.utc).isoformat()
        if last_warmed_ts else None
    )

    items_per_page = FEED_DEFAULT_LIMIT
    feed_total = len(eligible_items)
    seeds_padded = int(exclusions.get("seed_items_padded", 0))
    feed_real = feed_total - seeds_padded  # actual live listings in the feed
    total_pages = (feed_total + items_per_page - 1) // items_per_page if items_per_page else 1

    return {
        "total_active_listings":   total_active,
        "feed_eligible_listings":  feed_real,
        "feed_total_items":        feed_total,
        "seed_items_padded":       seeds_padded,
        "excluded_listings":       max(0, total_active - feed_real),
        "exclusion_reasons":       exclusions,
        "last_cached_at":          last_warmed_iso,
        "cache_ttl_seconds":       int(os.environ.get("FEED_CACHE_TTL_SECONDS", "900")),
        "feed_url":                f"{BIDVEX_BASE_URL}/api/feeds/facebook-local",
        "total_pages":             total_pages,
        "items_per_page":          items_per_page,
        "require_geo_for_inclusion": FEED_REQUIRE_GEO,
        "cache_was_hit":           was_hit,
    }


# ── Admin: force a cache refresh ─────────────────────────────────────
@router.post("/facebook-local/refresh", dependencies=[Depends(require_admin)])
async def refresh_facebook_local_feed() -> Dict[str, Any]:
    """Admin-only — invalidate the cache so the next public request rebuilds."""
    cleared = invalidate_feed_cache()
    # Pre-warm immediately so the admin sees the new count.
    items, exclusions = await _build_feed_items(None, None, None, FEED_MAX_ITEMS_PER_REQUEST, 0)
    cache_set(make_cache_key(None, None, None, FEED_MAX_ITEMS_PER_REQUEST, 0), items, exclusions)
    return {
        "status":     "refreshed",
        "item_count": len(items),
        "cleared":    cleared,
        "exclusions": exclusions,
    }
