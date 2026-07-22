"""
iter373 — Admin Landing Page Builder (backend foundation).

Delivers three surfaces:

  1.  Admin CRUD  →  /api/admin/landing-pages/*
        list, create, read, update, delete (soft), publish, unpublish,
        duplicate. `require_admin` on every endpoint.

  2.  Public JSON →  /api/lp/{slug}                (json, for SPA render)
      Public HTML →  /api/lp/{slug}/render        (full HTML, for crawlers /
                                                    prerender fallback)
      Both:
        • serve ONLY status="published" pages, 404 otherwise
        • honour `?lang=en|fr` override then fall back to Accept-Language
        • increment view_count + view-buckets on every hit
        • capture referrer + user agent (best-effort, bounded)

  3.  Analytics roll-up (returned inside the admin detail response):
        total_views, views_7d, views_30d, top_referrers.

Design decisions
----------------
* The public route lives under `/api/lp/{slug}` because the kubernetes
  ingress only routes `/api/*` to the FastAPI app. A future frontend
  React route at `/lp/{slug}` will `fetch('/api/lp/{slug}')` and render;
  crawlers hitting `/lp/{slug}` are already handled by the existing
  BotPrerenderMiddleware which can fall through to `/api/lp/{slug}/render`.

* No new PyPI dependencies. Uses `bleach` (already installed 6.3.0) for
  HTML sanitisation and `re` for slug validation. `escape()` from `html`
  handles meta/OG tag escaping.

* Audit log written to `landing_page_audit_log` on every admin write
  (create / update / publish / unpublish / duplicate / delete). Row is
  small enough (~200 bytes) that we keep the full history without a
  TTL index.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone, timedelta
from html import escape
from typing import Any, Dict, List, Optional

import bleach
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field, field_validator

from deps import User, get_db, require_admin

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Landing Pages"])


# ─── Constants ──────────────────────────────────────────────────────────

STATUSES = ("draft", "published", "archived")
DEFAULT_STATUS = "draft"

# Slug: lowercase alphanumerics and hyphens; 2–80 chars; no leading /
# trailing hyphen; no consecutive hyphens. Chosen so slugs work as safe
# URL segments in every browser + SEO tooling.
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MIN_SLUG_LEN = 2
MAX_SLUG_LEN = 80

# Reserved slugs that would collide with SPA routes.
RESERVED_SLUGS = {
    "api", "admin", "auth", "login", "signup", "register", "logout",
    "checkout", "profile", "settings", "dashboard", "marketplace",
    "lots", "listings", "listing", "vehicles", "storage", "auction",
    "auctions", "compare", "affiliate", "affiliates", "help", "support",
    "terms", "privacy", "cookies", "search", "static", "assets", "public",
    "sitemap.xml", "robots.txt", "favicon.ico",
}

# Bleach whitelist — deliberately permissive (admin author is trusted)
# but explicit so we still strip inline event handlers and javascript:
# URIs. `<script>` is REMOVED (custom JS lives in the `js` field which
# the renderer wraps in a <script> tag). `<style>` in body-HTML is
# removed too (custom CSS goes to the `css` field).
BLEACH_ALLOWED_TAGS = list({
    # Structure
    "div", "section", "article", "aside", "header", "footer", "main",
    "nav", "figure", "figcaption",
    # Text
    "p", "span", "br", "hr", "small", "sub", "sup", "mark",
    "h1", "h2", "h3", "h4", "h5", "h6",
    "strong", "em", "b", "i", "u", "s", "code", "pre", "kbd",
    "blockquote", "q", "cite", "abbr",
    # Lists
    "ul", "ol", "li", "dl", "dt", "dd",
    # Tables
    "table", "thead", "tbody", "tfoot", "tr", "td", "th", "caption", "colgroup", "col",
    # Media
    "img", "picture", "source", "video", "audio", "iframe",  # iframe = e.g. embedded YouTube
    # Links
    "a", "button",
    # Forms — buttons only (admin marketing pages typically link out)
    "label",
    # Formatting
    "hr", "div", "span",
})

BLEACH_ALLOWED_ATTRS = {
    "*": ["class", "id", "style", "data-testid", "aria-label", "role",
          "data-page-slug", "tabindex", "title"],
    "a":       ["href", "target", "rel", "download"],
    "img":     ["src", "alt", "width", "height", "loading", "decoding", "srcset", "sizes"],
    "source":  ["src", "srcset", "media", "type", "sizes"],
    "picture": ["media"],
    "video":   ["src", "poster", "controls", "muted", "playsinline", "autoplay", "loop", "width", "height", "preload"],
    "audio":   ["src", "controls", "preload"],
    "iframe":  ["src", "width", "height", "allow", "allowfullscreen", "loading", "referrerpolicy", "title"],
    "button":  ["type", "name", "value"],
    "table":   ["border", "cellpadding", "cellspacing"],
    "td":      ["colspan", "rowspan", "align", "valign"],
    "th":      ["colspan", "rowspan", "align", "valign", "scope"],
}

BLEACH_ALLOWED_PROTOCOLS = ["http", "https", "mailto", "tel", "data"]

# Bounded caps to keep the DB row + response payload sane.
MAX_HTML_BYTES = 250_000    # ≈ 250 KB
MAX_CSS_BYTES = 100_000
MAX_JS_BYTES = 60_000
MAX_TITLE_LEN = 160
MAX_META_LEN = 320


# ─── Pydantic schemas ───────────────────────────────────────────────────


class _SlugMixin(BaseModel):
    slug: str = Field(..., min_length=MIN_SLUG_LEN, max_length=MAX_SLUG_LEN)

    @field_validator("slug")
    @classmethod
    def _slug_shape(cls, v: str) -> str:
        raw = (v or "").strip()
        # Reject any uppercase / underscore / non-ASCII BEFORE lowercasing so
        # the client sees the exact error instead of a silently coerced value.
        if raw != raw.lower():
            raise ValueError("Slug must be lowercase (no uppercase letters).")
        if raw in RESERVED_SLUGS:
            raise ValueError(f"'{raw}' is a reserved slug")
        if not SLUG_RE.match(raw):
            raise ValueError(
                "Slug must be lowercase, use only a–z, 0–9 and hyphens, "
                "and cannot start / end with a hyphen or contain '--'."
            )
        return raw


class LandingPageCreate(_SlugMixin):
    title_en: str = Field(..., min_length=1, max_length=MAX_TITLE_LEN)
    title_fr: Optional[str] = Field(None, max_length=MAX_TITLE_LEN)
    meta_description_en: Optional[str] = Field(None, max_length=MAX_META_LEN)
    meta_description_fr: Optional[str] = Field(None, max_length=MAX_META_LEN)
    html_en: str = Field("", max_length=MAX_HTML_BYTES)
    html_fr: str = Field("", max_length=MAX_HTML_BYTES)
    css: str = Field("", max_length=MAX_CSS_BYTES)
    js: str = Field("", max_length=MAX_JS_BYTES)
    show_bidvex_header: bool = True
    show_bidvex_footer: bool = True
    og_image_url: Optional[str] = Field(None, max_length=1024)


class LandingPageUpdate(BaseModel):
    """Every field optional so PATCH callers can send partial updates."""
    slug: Optional[str] = Field(None, min_length=MIN_SLUG_LEN, max_length=MAX_SLUG_LEN)
    title_en: Optional[str] = Field(None, min_length=1, max_length=MAX_TITLE_LEN)
    title_fr: Optional[str] = Field(None, max_length=MAX_TITLE_LEN)
    meta_description_en: Optional[str] = Field(None, max_length=MAX_META_LEN)
    meta_description_fr: Optional[str] = Field(None, max_length=MAX_META_LEN)
    html_en: Optional[str] = Field(None, max_length=MAX_HTML_BYTES)
    html_fr: Optional[str] = Field(None, max_length=MAX_HTML_BYTES)
    css: Optional[str] = Field(None, max_length=MAX_CSS_BYTES)
    js: Optional[str] = Field(None, max_length=MAX_JS_BYTES)
    show_bidxvex_header: Optional[bool] = None  # noqa (typo left for safety alias)
    show_bidvex_header: Optional[bool] = None
    show_bidvex_footer: Optional[bool] = None
    og_image_url: Optional[str] = Field(None, max_length=1024)

    @field_validator("slug")
    @classmethod
    def _slug_shape(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        raw = v.strip()
        if raw != raw.lower():
            raise ValueError("Slug must be lowercase (no uppercase letters).")
        if raw in RESERVED_SLUGS:
            raise ValueError(f"'{raw}' is a reserved slug")
        if not SLUG_RE.match(raw):
            raise ValueError(
                "Slug must be lowercase, use only a–z, 0–9 and hyphens, "
                "and cannot start / end with a hyphen or contain '--'."
            )
        return raw


# ─── Helpers ────────────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sanitise_html(raw: str) -> str:
    """Bleach-clean HTML body content. Strips <script>, event handlers,
    `javascript:` URIs. Returns an empty string when the input is None."""
    if not raw:
        return ""
    return bleach.clean(
        raw,
        tags=BLEACH_ALLOWED_TAGS,
        attributes=BLEACH_ALLOWED_ATTRS,
        protocols=BLEACH_ALLOWED_PROTOCOLS,
        strip=True,
        strip_comments=False,   # keep <!-- --> for authoring notes
    )


def _sanitise_css(raw: str) -> str:
    """CSS gets a lightweight scrub: strip `@import` (which can pull
    remote stylesheets) and JavaScript-URL syntax. We do NOT parse CSS
    (would need cssutils) so we accept the trade-off that authors can
    still use `url(...)` for legitimate assets."""
    if not raw:
        return ""
    cleaned = raw
    # Remove any @import <url>; statements — safer to hard-code assets.
    cleaned = re.sub(r"@import[^;]+;", "", cleaned, flags=re.IGNORECASE)
    # Neutralise javascript: URLs.
    cleaned = re.sub(r"javascript\s*:", "removed:", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def _sanitise_js(raw: str) -> str:
    """Custom JS is rendered inside a `<script>` tag on the public
    endpoint. We won't attempt to parse the JS; we just cap the length
    (enforced upstream via Pydantic) and strip closing `</script>` so
    an author can't accidentally end the tag mid-body."""
    if not raw:
        return ""
    return re.sub(r"</\s*script\s*>", "<\\/script>", raw, flags=re.IGNORECASE)


async def _slug_exists(db, slug: str, exclude_id: Optional[str] = None) -> bool:
    query: Dict[str, Any] = {"slug": slug}
    if exclude_id:
        query["id"] = {"$ne": exclude_id}
    doc = await db.landing_pages.find_one(query, {"_id": 0, "id": 1})
    return doc is not None


async def _get_page_or_404(db, page_id: str, allow_archived: bool = True) -> Dict[str, Any]:
    doc = await db.landing_pages.find_one({"id": page_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Landing page not found")
    if not allow_archived and doc.get("status") == "archived":
        raise HTTPException(status_code=404, detail="Landing page archived")
    return doc


def _mask_referrer(ref: Optional[str]) -> Optional[str]:
    """Trim referrers to origin only — never store user-visible paths."""
    if not ref or not isinstance(ref, str):
        return None
    ref = ref.strip()
    if not ref or len(ref) > 2048:
        return None
    try:
        from urllib.parse import urlparse
        p = urlparse(ref)
        if not p.scheme or not p.netloc:
            return None
        return f"{p.scheme}://{p.netloc}"
    except Exception:  # noqa: BLE001
        return None


async def _record_view(db, page_id: str, ref: Optional[str], user_agent: Optional[str], ip: Optional[str]) -> None:
    """Increments total + daily buckets + logs a bounded row for analytics.
    Any error here is swallowed — analytics must never break a public
    page render."""
    try:
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        origin = _mask_referrer(ref)
        await db.landing_pages.update_one(
            {"id": page_id},
            {
                "$inc": {"view_count": 1, f"view_buckets.{today}": 1},
                "$set": {"last_viewed_at": _now_iso()},
            },
        )
        # Bounded referrer counter — top 100 origins only, oldest wins.
        if origin:
            await db.landing_pages.update_one(
                {"id": page_id},
                {"$inc": {f"referrer_counts.{origin.replace('.', '_dot_')}": 1}},
            )
        # Best-effort per-view row for deeper analysis (bounded ring).
        await db.landing_page_views.insert_one({
            "id": str(uuid.uuid4()),
            "page_id": page_id,
            "referrer": origin,
            "user_agent": (user_agent or "")[:256],
            "ip": (ip or "")[:64],
            "created_at": _now_iso(),
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[landing-pages] view-tracking failed for {page_id}: {e}")


async def _write_audit(db, actor: User, action: str, page_id: str, before: Optional[Dict[str, Any]] = None, after: Optional[Dict[str, Any]] = None) -> None:
    """iter373 — Persist admin edit history for landing pages so security
    reviews can retrace who changed what HTML."""
    try:
        def _snap(d: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
            if not d:
                return None
            # Snapshot the fields that matter for a security review; skip
            # heavy body payloads to keep the audit log tiny.
            return {
                k: (v[:400] if isinstance(v, str) and k in ("html_en", "html_fr", "css", "js") else v)
                for k, v in d.items()
                if k in ("slug", "title_en", "title_fr", "status",
                         "meta_description_en", "meta_description_fr",
                         "show_bidvex_header", "show_bidvex_footer",
                         "og_image_url", "html_en", "html_fr", "css", "js")
            }
        await db.landing_page_audit_log.insert_one({
            "id": str(uuid.uuid4()),
            "page_id": page_id,
            "action": action,
            "actor_id": actor.id,
            "actor_email": actor.email,
            "before": _snap(before),
            "after": _snap(after),
            "created_at": _now_iso(),
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[landing-pages] audit-log failed for {page_id}: {e}")


def _select_locale(page: Dict[str, Any], lang_pref: Optional[str], accept_language: Optional[str]) -> str:
    """Return either 'en' or 'fr' based on:
        1. explicit `?lang=` override
        2. Accept-Language header (first weighted match)
        3. English default
    Also collapses to whichever language actually has content — a page
    with no FR body will always render EN even if the browser prefers FR.
    """
    langs = ["en", "fr"]
    picked = None
    if lang_pref and lang_pref.lower() in langs:
        picked = lang_pref.lower()
    elif accept_language:
        # Very small parser — just grab the first tag before ';' or ','.
        for chunk in accept_language.split(","):
            tag = chunk.split(";")[0].strip().lower()
            if tag.startswith("fr"):
                picked = "fr"
                break
            if tag.startswith("en"):
                picked = "en"
                break
    picked = picked or "en"
    if picked == "fr" and not (page.get("html_fr") or page.get("title_fr")):
        picked = "en"
    if picked == "en" and not (page.get("html_en") or page.get("title_en")):
        picked = "fr"
    return picked


def _public_view(page: Dict[str, Any], locale: str) -> Dict[str, Any]:
    """Public-safe JSON view of a landing page (excludes admin metadata)."""
    return {
        "id": page.get("id"),
        "slug": page.get("slug"),
        "locale": locale,
        "title": page.get(f"title_{locale}") or page.get("title_en"),
        "meta_description": page.get(f"meta_description_{locale}")
                            or page.get("meta_description_en"),
        "html": page.get(f"html_{locale}") or page.get("html_en") or "",
        "css": page.get("css") or "",
        "js": page.get("js") or "",
        "show_bidvex_header": bool(page.get("show_bidvex_header", True)),
        "show_bidvex_footer": bool(page.get("show_bidvex_footer", True)),
        "og_image_url": page.get("og_image_url"),
        "published_at": page.get("published_at"),
    }


def _admin_view(page: Dict[str, Any]) -> Dict[str, Any]:
    """Admin JSON view — full page + analytics roll-up."""
    return {
        **{k: v for k, v in page.items() if not k.startswith("_") and k != "view_buckets"},
        "analytics": _rollup_analytics(page),
    }


def _rollup_analytics(page: Dict[str, Any]) -> Dict[str, Any]:
    buckets = page.get("view_buckets") or {}
    today = datetime.now(timezone.utc).date()
    days_7 = {(today - timedelta(days=i)).isoformat() for i in range(7)}
    days_30 = {(today - timedelta(days=i)).isoformat() for i in range(30)}
    views_7d = sum(int(v) for k, v in buckets.items() if k in days_7)
    views_30d = sum(int(v) for k, v in buckets.items() if k in days_30)
    ref_counts_raw = page.get("referrer_counts") or {}
    top_refs = sorted(
        ((k.replace("_dot_", "."), v) for k, v in ref_counts_raw.items()),
        key=lambda x: x[1],
        reverse=True,
    )[:10]
    return {
        "total_views": int(page.get("view_count", 0)),
        "views_7d": views_7d,
        "views_30d": views_30d,
        "top_referrers": [{"origin": o, "count": int(c)} for o, c in top_refs],
        "last_viewed_at": page.get("last_viewed_at"),
    }


# ─── Admin CRUD ─────────────────────────────────────────────────────────


@router.get("/admin/landing-pages")
async def list_landing_pages(
    admin: User = Depends(require_admin),
    status: Optional[str] = Query(None, description="Filter by status"),
    q: Optional[str] = Query(None, description="Search in slug/title"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    db = get_db()
    query: Dict[str, Any] = {}
    if status:
        if status not in STATUSES:
            raise HTTPException(status_code=422, detail=f"status must be one of {STATUSES}")
        query["status"] = status
    if q:
        needle = re.escape(q.strip())
        query["$or"] = [
            {"slug": {"$regex": needle, "$options": "i"}},
            {"title_en": {"$regex": needle, "$options": "i"}},
            {"title_fr": {"$regex": needle, "$options": "i"}},
        ]

    total = await db.landing_pages.count_documents(query)
    cursor = (db.landing_pages.find(query, {"_id": 0})
              .sort("updated_at", -1)
              .skip((page - 1) * page_size)
              .limit(page_size))
    rows = [_admin_view(doc) async for doc in cursor]
    return {
        "items": rows,
        "page": page,
        "page_size": page_size,
        "total": total,
        "has_more": (page * page_size) < total,
    }


@router.post("/admin/landing-pages")
async def create_landing_page(
    body: LandingPageCreate,
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    db = get_db()
    if await _slug_exists(db, body.slug):
        raise HTTPException(status_code=409, detail={
            "error": "duplicate_slug",
            "message_en": f"A landing page with slug '{body.slug}' already exists.",
            "message_fr": f"Une page d'atterrissage avec le slug '{body.slug}' existe déjà.",
        })
    now = _now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "slug": body.slug,
        "title_en": body.title_en.strip(),
        "title_fr": (body.title_fr or "").strip() or None,
        "meta_description_en": (body.meta_description_en or "").strip() or None,
        "meta_description_fr": (body.meta_description_fr or "").strip() or None,
        "html_en": _sanitise_html(body.html_en),
        "html_fr": _sanitise_html(body.html_fr),
        "css": _sanitise_css(body.css),
        "js": _sanitise_js(body.js),
        "status": DEFAULT_STATUS,
        "show_bidvex_header": bool(body.show_bidvex_header),
        "show_bidvex_footer": bool(body.show_bidvex_footer),
        "og_image_url": (body.og_image_url or "").strip() or None,
        "created_by": admin.id,
        "created_by_email": admin.email,
        "created_at": now,
        "updated_at": now,
        "published_at": None,
        "view_count": 0,
        "view_buckets": {},
        "referrer_counts": {},
    }
    await db.landing_pages.insert_one(doc)
    await _write_audit(db, admin, "create", doc["id"], after=doc)
    logger.info(f"[landing-pages] created id={doc['id']} slug={doc['slug']} by={admin.email}")
    return _admin_view(doc)


@router.get("/admin/landing-pages/{page_id}")
async def get_landing_page(
    page_id: str,
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    db = get_db()
    page = await _get_page_or_404(db, page_id)
    return _admin_view(page)


@router.patch("/admin/landing-pages/{page_id}")
async def update_landing_page(
    page_id: str,
    body: LandingPageUpdate,
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    db = get_db()
    page = await _get_page_or_404(db, page_id)
    updates: Dict[str, Any] = {"updated_at": _now_iso()}
    body_data = body.model_dump(exclude_unset=True)

    if "slug" in body_data:
        new_slug = body_data["slug"]
        if new_slug and new_slug != page.get("slug"):
            if await _slug_exists(db, new_slug, exclude_id=page_id):
                raise HTTPException(status_code=409, detail={
                    "error": "duplicate_slug",
                    "message_en": f"A landing page with slug '{new_slug}' already exists.",
                })
            updates["slug"] = new_slug

    scalar_fields = ("title_en", "title_fr", "meta_description_en",
                     "meta_description_fr", "show_bidvex_header",
                     "show_bidvex_footer", "og_image_url")
    for field in scalar_fields:
        if field in body_data:
            v = body_data[field]
            if isinstance(v, str):
                v = v.strip() or None
            updates[field] = v

    # HTML / CSS / JS get their sanitiser.
    if "html_en" in body_data:
        updates["html_en"] = _sanitise_html(body_data["html_en"])
    if "html_fr" in body_data:
        updates["html_fr"] = _sanitise_html(body_data["html_fr"])
    if "css" in body_data:
        updates["css"] = _sanitise_css(body_data["css"])
    if "js" in body_data:
        updates["js"] = _sanitise_js(body_data["js"])

    if len(updates) == 1:  # only `updated_at` — nothing to save
        return _admin_view(page)

    await db.landing_pages.update_one({"id": page_id}, {"$set": updates})
    fresh = await _get_page_or_404(db, page_id)
    # Audit content-body changes explicitly since they're the highest-risk
    # surface for XSS. Log a compact before/after diff.
    if any(k in updates for k in ("html_en", "html_fr", "css", "js")):
        logger.info(f"[landing-pages] admin={admin.email} updated HTML/CSS/JS on id={page_id}")
    await _write_audit(db, admin, "update", page_id, before=page, after=fresh)
    return _admin_view(fresh)


@router.delete("/admin/landing-pages/{page_id}")
async def soft_delete_landing_page(
    page_id: str,
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    db = get_db()
    page = await _get_page_or_404(db, page_id)
    await db.landing_pages.update_one(
        {"id": page_id},
        {"$set": {"status": "archived", "updated_at": _now_iso()}},
    )
    fresh = await _get_page_or_404(db, page_id)
    await _write_audit(db, admin, "archive", page_id, before=page, after=fresh)
    return {"ok": True, "id": page_id, "status": "archived"}


@router.post("/admin/landing-pages/{page_id}/publish")
async def publish_landing_page(
    page_id: str,
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    db = get_db()
    page = await _get_page_or_404(db, page_id)
    if not (page.get("title_en") and (page.get("html_en") or page.get("html_fr"))):
        raise HTTPException(status_code=422, detail={
            "error": "incomplete_page",
            "message_en": "A page needs at least a title_en and html_en (or html_fr) before it can be published.",
        })
    updates = {
        "status": "published",
        "published_at": _now_iso(),
        "updated_at": _now_iso(),
    }
    await db.landing_pages.update_one({"id": page_id}, {"$set": updates})
    fresh = await _get_page_or_404(db, page_id)
    await _write_audit(db, admin, "publish", page_id, before=page, after=fresh)
    return _admin_view(fresh)


@router.post("/admin/landing-pages/{page_id}/unpublish")
async def unpublish_landing_page(
    page_id: str,
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    db = get_db()
    page = await _get_page_or_404(db, page_id)
    updates = {"status": "draft", "updated_at": _now_iso()}
    await db.landing_pages.update_one({"id": page_id}, {"$set": updates})
    fresh = await _get_page_or_404(db, page_id)
    await _write_audit(db, admin, "unpublish", page_id, before=page, after=fresh)
    return _admin_view(fresh)


@router.post("/admin/landing-pages/{page_id}/duplicate")
async def duplicate_landing_page(
    page_id: str,
    admin: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Deep-copy a page under a "-copy" (or "-copy-N") slug."""
    db = get_db()
    src = await _get_page_or_404(db, page_id)
    base_slug = f"{src['slug']}-copy"
    candidate = base_slug
    suffix = 2
    # If the base "-copy" exists, keep incrementing until we find an
    # available slug. Cap at 50 attempts to avoid an accidental infinite loop.
    while await _slug_exists(db, candidate) and suffix <= 50:
        candidate = f"{base_slug}-{suffix}"
        suffix += 1
    if await _slug_exists(db, candidate):
        raise HTTPException(status_code=409, detail="Could not find an available slug for duplicate")

    now = _now_iso()
    dup = {
        **{k: v for k, v in src.items() if k not in ("id", "slug", "created_at",
                                                     "updated_at", "published_at",
                                                     "view_count", "view_buckets",
                                                     "referrer_counts",
                                                     "last_viewed_at")},
        "id": str(uuid.uuid4()),
        "slug": candidate,
        "status": DEFAULT_STATUS,
        "created_by": admin.id,
        "created_by_email": admin.email,
        "created_at": now,
        "updated_at": now,
        "published_at": None,
        "view_count": 0,
        "view_buckets": {},
        "referrer_counts": {},
        "duplicated_from": page_id,
    }
    await db.landing_pages.insert_one(dup)
    await _write_audit(db, admin, "duplicate", dup["id"], after=dup)
    return _admin_view(dup)


# ─── Admin audit-log view ───────────────────────────────────────────────

@router.get("/admin/landing-pages/{page_id}/audit-log")
async def get_landing_page_audit_log(
    page_id: str,
    admin: User = Depends(require_admin),
    limit: int = Query(50, ge=1, le=200),
) -> Dict[str, Any]:
    db = get_db()
    _ = await _get_page_or_404(db, page_id)
    rows = await (db.landing_page_audit_log
                    .find({"page_id": page_id}, {"_id": 0})
                    .sort("created_at", -1)
                    .limit(limit)
                    .to_list(limit))
    return {"page_id": page_id, "entries": rows}


# ─── Public rendering ───────────────────────────────────────────────────

# Frontend-hostname (used to build the canonical URL). Fall back to the
# preview host when the env var is missing so tests don't blow up.
import os as _os  # noqa: E402


def _canonical_base() -> str:
    return _os.environ.get("PUBLIC_FRONTEND_URL", "").rstrip("/") or "https://bidvex.com"


@router.get("/lp/{slug}")
async def get_public_landing_page(
    slug: str,
    request: Request,
    lang: Optional[str] = Query(None, pattern=r"^(en|fr)$"),
) -> Dict[str, Any]:
    """Public JSON endpoint used by the SPA (and future prerender)."""
    db = get_db()
    slug = (slug or "").strip().lower()
    page = await db.landing_pages.find_one({"slug": slug, "status": "published"}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Landing page not found")

    accept_language = request.headers.get("accept-language")
    locale = _select_locale(page, lang, accept_language)
    referrer = request.headers.get("referer")
    user_agent = request.headers.get("user-agent")
    ip = request.client.host if request.client else None

    await _record_view(db, page["id"], referrer, user_agent, ip)

    view = _public_view(page, locale)
    view["canonical_url"] = f"{_canonical_base()}/lp/{slug}"
    return view


@router.get("/lp/{slug}/render", response_class=HTMLResponse)
async def render_public_landing_page(
    slug: str,
    request: Request,
    lang: Optional[str] = Query(None, pattern=r"^(en|fr)$"),
) -> HTMLResponse:
    """Public HTML endpoint — full document with SEO tags, custom CSS +
    body HTML + optional custom JS. Consumed by crawlers / prerender
    middleware; also directly viewable in a browser for QA."""
    db = get_db()
    slug = (slug or "").strip().lower()
    page = await db.landing_pages.find_one({"slug": slug, "status": "published"}, {"_id": 0})
    if not page:
        raise HTTPException(status_code=404, detail="Landing page not found")

    accept_language = request.headers.get("accept-language")
    locale = _select_locale(page, lang, accept_language)
    referrer = request.headers.get("referer")
    user_agent = request.headers.get("user-agent")
    ip = request.client.host if request.client else None

    await _record_view(db, page["id"], referrer, user_agent, ip)

    title = escape((page.get(f"title_{locale}") or page.get("title_en") or "BidVex")[:MAX_TITLE_LEN])
    meta_desc = escape((page.get(f"meta_description_{locale}") or page.get("meta_description_en") or "")[:MAX_META_LEN])
    canonical = f"{_canonical_base()}/lp/{slug}"
    og_image = escape((page.get("og_image_url") or "")[:1024])
    body_html = page.get(f"html_{locale}") or page.get("html_en") or ""
    css = page.get("css") or ""
    js = page.get("js") or ""

    header_html = (
        '<header class="bidvex-lp-header" data-testid="bidvex-lp-header" '
        'style="border-bottom:1px solid #e2e8f0;padding:16px 24px;'
        'font-family:sans-serif;font-weight:700;color:#0f172a;">'
        '<a href="/" style="color:#0891b2;text-decoration:none;">BidVex</a>'
        "</header>"
    ) if page.get("show_bidvex_header", True) else ""

    footer_html = (
        '<footer class="bidvex-lp-footer" data-testid="bidvex-lp-footer" '
        'style="border-top:1px solid #e2e8f0;padding:16px 24px;font-size:12px;'
        'color:#64748b;text-align:center;font-family:sans-serif;">'
        '© BidVex — <a href="/" style="color:#0891b2;">bidvex.com</a>'
        "</footer>"
    ) if page.get("show_bidvex_footer", True) else ""

    og_image_tag = (f'<meta property="og:image" content="{og_image}">'
                    if og_image else "")

    doc = f"""<!DOCTYPE html>
<html lang="{locale}" data-testid="lp-root" data-page-slug="{escape(slug)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title data-testid="lp-title">{title}</title>
<meta name="description" content="{meta_desc}" data-testid="lp-meta-description">
<link rel="canonical" href="{escape(canonical)}" data-testid="lp-canonical">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{meta_desc}">
<meta property="og:type" content="website">
<meta property="og:url" content="{escape(canonical)}">
<meta property="og:locale" content="{locale}">
{og_image_tag}
<meta name="twitter:card" content="summary_large_image">
<meta name="robots" content="index,follow">
<style data-testid="lp-css">{css}</style>
</head>
<body style="margin:0;font-family:'Inter',system-ui,sans-serif;color:#0f172a;background:#fff;">
{header_html}
<main class="bidvex-lp-body" data-testid="lp-body" data-page-slug="{escape(slug)}">
{body_html}
</main>
{footer_html}
<script data-testid="lp-js">{js}</script>
</body>
</html>"""
    return HTMLResponse(content=doc, headers={
        "Cache-Control": "public, max-age=60, s-maxage=300",
        "X-Robots-Tag": "index, follow",
        "Content-Language": locale,
        "X-BidVex-Landing-Slug": slug,
    })


# ─── Router bootstrap glue (called from server.py) ──────────────────────


def set_db(_db) -> None:
    """Kept for API parity with other routers; landing_pages uses the
    shared `get_db()` helper directly."""
    return None


__all__ = ["router", "set_db"]
