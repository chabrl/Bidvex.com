"""
iter331 — Press / Blogs CRUD routes.

Mounted at:
  Public:
    GET    /api/blogs/articles
    GET    /api/blogs/articles/{slug}
  Admin-only:
    GET    /api/admin/blogs/articles
    POST   /api/admin/blogs/articles
    PATCH  /api/admin/blogs/articles/{article_id}
    DELETE /api/admin/blogs/articles/{article_id}
    POST   /api/admin/blogs/articles/{article_id}/publish
    POST   /api/admin/blogs/articles/{article_id}/unpublish
    POST   /api/admin/blogs/articles/cover-upload   (multipart S3 upload)

Persists into the `press_articles` Mongo collection. The frontend BlogsPage
fetches published articles from the public list; the AdminBlogsConsole
performs full CRUD.

Cover images are uploaded via the existing marketplace S3 pipeline so we
stay consistent with the rest of the platform (no new bucket / credential).
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field

from deps import get_current_user, get_db, require_admin, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["blogs"])

ALLOWED_TAGS = {
    "platform", "compliance", "storage", "vehicles", "partners", "security",
    "marketing", "company", "product",
}
SLUG_RE = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,80}[a-z0-9])?$")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", (text or "").strip().lower())
    s = re.sub(r"[\s_]+", "-", s).strip("-")
    return s[:80] or uuid.uuid4().hex[:10]


def _strip_mongo(doc: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if doc is None:
        return None
    d = {k: v for k, v in doc.items() if k != "_id"}
    return d


def _public_projection() -> Dict[str, int]:
    return {
        "_id": 0, "id": 1, "slug": 1, "tag": 1, "icon": 1,
        "title_en": 1, "title_fr": 1, "excerpt_en": 1, "excerpt_fr": 1,
        "body_en": 1, "body_fr": 1, "cover_url": 1, "read_min": 1,
        "published": 1, "published_at": 1, "created_at": 1, "updated_at": 1,
    }


# ─── Pydantic request models ──────────────────────────────────────────

class ArticleCreate(BaseModel):
    title_en: str = Field(..., min_length=3, max_length=240)
    title_fr: str = Field(..., min_length=3, max_length=240)
    excerpt_en: str = Field(..., min_length=10, max_length=600)
    excerpt_fr: str = Field(..., min_length=10, max_length=600)
    body_en: str = Field(..., min_length=10, max_length=40000)
    body_fr: str = Field(..., min_length=10, max_length=40000)
    tag: str = Field("platform", max_length=40)
    slug: Optional[str] = Field(None, max_length=80)
    icon: Optional[str] = Field("BookOpen", max_length=40)
    cover_url: Optional[str] = Field(None, max_length=2000)
    read_min: int = Field(5, ge=1, le=60)
    published: bool = False


class ArticleUpdate(BaseModel):
    title_en: Optional[str] = Field(None, min_length=3, max_length=240)
    title_fr: Optional[str] = Field(None, min_length=3, max_length=240)
    excerpt_en: Optional[str] = Field(None, min_length=10, max_length=600)
    excerpt_fr: Optional[str] = Field(None, min_length=10, max_length=600)
    body_en: Optional[str] = Field(None, min_length=10, max_length=40000)
    body_fr: Optional[str] = Field(None, min_length=10, max_length=40000)
    tag: Optional[str] = Field(None, max_length=40)
    slug: Optional[str] = Field(None, max_length=80)
    icon: Optional[str] = Field(None, max_length=40)
    cover_url: Optional[str] = Field(None, max_length=2000)
    read_min: Optional[int] = Field(None, ge=1, le=60)
    published: Optional[bool] = None


# ─── Public endpoints ─────────────────────────────────────────────────

@router.get("/blogs/articles")
async def list_published_articles(
    tag: Optional[str] = Query(None, max_length=40),
    limit: int = Query(60, ge=1, le=200),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Public — only published articles, newest first."""
    q: Dict[str, Any] = {"published": True}
    if tag and tag in ALLOWED_TAGS:
        q["tag"] = tag
    docs = await db.press_articles.find(q, _public_projection()) \
        .sort("published_at", -1).to_list(limit)
    return {"articles": docs, "total": len(docs)}


@router.get("/blogs/articles/{slug}")
async def get_article_by_slug(slug: str, db=Depends(get_db)) -> Dict[str, Any]:
    """Public — fetch a single published article by slug."""
    doc = await db.press_articles.find_one(
        {"slug": slug, "published": True}, _public_projection(),
    )
    if not doc:
        raise HTTPException(404, "article not found")
    return doc


# ─── Admin endpoints ──────────────────────────────────────────────────

@router.get("/admin/blogs/articles")
async def admin_list_articles(
    include_drafts: bool = Query(True),
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    q: Dict[str, Any] = {}
    if not include_drafts:
        q["published"] = True
    docs = await db.press_articles.find(q, _public_projection()) \
        .sort("created_at", -1).to_list(500)
    return {"articles": docs, "total": len(docs)}


@router.post("/admin/blogs/articles")
async def admin_create_article(
    payload: ArticleCreate,
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    tag = payload.tag if payload.tag in ALLOWED_TAGS else "platform"
    slug = payload.slug or _slugify(payload.title_en)
    if not SLUG_RE.match(slug):
        raise HTTPException(422, "slug must be lowercase alphanumeric with dashes")

    # Ensure slug uniqueness.
    if await db.press_articles.find_one({"slug": slug}, {"_id": 1}):
        raise HTTPException(409, f"slug already exists: {slug}")

    now = _now_iso()
    doc = {
        "id": str(uuid.uuid4()),
        "slug": slug,
        "tag": tag,
        "icon": payload.icon or "BookOpen",
        "title_en": payload.title_en,
        "title_fr": payload.title_fr,
        "excerpt_en": payload.excerpt_en,
        "excerpt_fr": payload.excerpt_fr,
        "body_en": payload.body_en,
        "body_fr": payload.body_fr,
        "cover_url": payload.cover_url or None,
        "read_min": int(payload.read_min),
        "published": bool(payload.published),
        "published_at": now if payload.published else None,
        "created_at": now,
        "updated_at": now,
        "created_by": user.id,
    }
    await db.press_articles.insert_one(doc)
    return _strip_mongo(doc)


@router.patch("/admin/blogs/articles/{article_id}")
async def admin_update_article(
    article_id: str,
    payload: ArticleUpdate,
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    existing = await db.press_articles.find_one({"id": article_id})
    if existing is None:
        raise HTTPException(404, "article not found")

    updates: Dict[str, Any] = {}
    for k, v in payload.model_dump(exclude_none=True).items():
        if k == "tag" and v not in ALLOWED_TAGS:
            continue
        if k == "slug":
            if not SLUG_RE.match(v):
                raise HTTPException(422, "slug must be lowercase alphanumeric with dashes")
            # Slug uniqueness (ignore self)
            clash = await db.press_articles.find_one(
                {"slug": v, "id": {"$ne": article_id}}, {"_id": 1},
            )
            if clash:
                raise HTTPException(409, f"slug already exists: {v}")
        updates[k] = v

    if not updates:
        return _strip_mongo(existing)

    updates["updated_at"] = _now_iso()
    # If we're flipping to published for the first time, stamp published_at.
    if updates.get("published") is True and not existing.get("published_at"):
        updates["published_at"] = updates["updated_at"]
    if updates.get("published") is False:
        # Keep historical published_at for re-publish, no change needed.
        pass

    await db.press_articles.update_one({"id": article_id}, {"$set": updates})
    refreshed = await db.press_articles.find_one({"id": article_id}, _public_projection())
    return refreshed


@router.delete("/admin/blogs/articles/{article_id}")
async def admin_delete_article(
    article_id: str,
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    result = await db.press_articles.delete_one({"id": article_id})
    if result.deleted_count == 0:
        raise HTTPException(404, "article not found")
    return {"deleted": True, "id": article_id}


@router.post("/admin/blogs/articles/{article_id}/publish")
async def admin_publish_article(
    article_id: str,
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    existing = await db.press_articles.find_one({"id": article_id})
    if existing is None:
        raise HTTPException(404, "article not found")
    now = _now_iso()
    await db.press_articles.update_one(
        {"id": article_id},
        {"$set": {"published": True, "published_at": existing.get("published_at") or now, "updated_at": now}},
    )
    return {"published": True, "id": article_id}


@router.post("/admin/blogs/articles/{article_id}/unpublish")
async def admin_unpublish_article(
    article_id: str,
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    existing = await db.press_articles.find_one({"id": article_id})
    if existing is None:
        raise HTTPException(404, "article not found")
    await db.press_articles.update_one(
        {"id": article_id},
        {"$set": {"published": False, "updated_at": _now_iso()}},
    )
    return {"published": False, "id": article_id}


@router.post("/admin/blogs/articles/cover-upload")
async def admin_upload_cover(
    file: UploadFile = File(...),
    user: User = Depends(require_admin),
) -> Dict[str, Any]:
    """Multipart S3 upload — returns the public URL for use in cover_url."""
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(415, "must upload an image file")

    try:
        from services.s3_service import upload_image_to_s3
        url = await upload_image_to_s3(file, listing_id=f"blog-{uuid.uuid4().hex[:10]}", index=0)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[blogs] cover upload failed: {e}")
        raise HTTPException(500, f"upload failed: {e}")

    return {"cover_url": url}
