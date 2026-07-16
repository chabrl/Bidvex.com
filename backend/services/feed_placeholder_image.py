"""
services/feed_placeholder_image.py — iter297 P1

Server-side Pillow placeholder image generator for the Meta + Google
Merchant feeds. Solves the long-tail of feed-listing rejections caused
by missing photos or webp/redirect URLs by:

  1. Drawing a BidVex-branded JPEG with the listing's title +
     category on a #0B2545 background.
  2. Uploading it to S3 under `placeholders/<listing_id>.jpg`.
  3. Returning the CloudFront URL.

A nightly scheduler job (`regenerate_missing_feed_placeholders`)
scans every listing missing a valid image URL and pre-bakes the
placeholder so the feed rendering path can serve it instantly without
synchronous Pillow work.
"""
from __future__ import annotations

import io
import logging
import os
from typing import Optional

from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# Brand palette (locked in iter294 design audit).
_BG      = (0x0B, 0x25, 0x45)
_ACCENT  = (0xF8, 0xC5, 0x4E)
_FG      = (0xFF, 0xFF, 0xFF)
_MUTED   = (0xCB, 0xD5, 0xE1)

CANVAS_W = 1200
CANVAS_H = 1200

_FONT_TITLE_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]
_FONT_BODY_PATHS = [
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
]


def _font(paths, size: int) -> ImageFont.ImageFont:
    for p in paths:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def _wrap_text(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, max_width: int) -> list[str]:
    """Greedy word-wrap, returns lines that each fit within max_width."""
    words = text.split()
    lines: list[str] = []
    current = ""
    for w in words:
        cand = f"{current} {w}".strip() if current else w
        if draw.textlength(cand, font=font) <= max_width:
            current = cand
        else:
            if current:
                lines.append(current)
            current = w
    if current:
        lines.append(current)
    return lines or [""]


def build_placeholder_bytes(*, title: str, category: str = "") -> bytes:
    """Render the JPEG bytes. Pure function — no S3, no DB, fully
    unit-testable."""
    img = Image.new("RGB", (CANVAS_W, CANVAS_H), _BG)
    draw = ImageDraw.Draw(img)

    # Diagonal accent stripe top-left → corner brand mark.
    draw.polygon(
        [(0, 0), (260, 0), (0, 260)],
        fill=_ACCENT,
    )
    # "BidVex" wordmark (top-right).
    brand_font = _font(_FONT_TITLE_PATHS, 64)
    brand_text = "BidVex"
    bw = draw.textlength(brand_text, font=brand_font)
    draw.text((CANVAS_W - bw - 60, 50), brand_text, fill=_FG, font=brand_font)

    # Category pill (bottom-left).
    if category:
        cat_font = _font(_FONT_BODY_PATHS, 36)
        cat_text = category.upper()
        ctw = draw.textlength(cat_text, font=cat_font)
        # Pill background
        pill_x, pill_y = 60, CANVAS_H - 130
        pill_w, pill_h = int(ctw + 60), 60
        draw.rounded_rectangle(
            [pill_x, pill_y, pill_x + pill_w, pill_y + pill_h],
            radius=30, fill=_ACCENT,
        )
        draw.text((pill_x + 30, pill_y + 8), cat_text, fill=_BG, font=cat_font)

    # Title — wrapped, centered.
    title_text = (title or "BidVex Listing").strip()
    if len(title_text) > 100:
        title_text = title_text[:97] + "..."
    title_font = _font(_FONT_TITLE_PATHS, 78)
    max_width = CANVAS_W - 160
    lines = _wrap_text(draw, title_text, title_font, max_width)
    # If we'd render >4 lines, shrink and re-wrap once.
    if len(lines) > 4:
        title_font = _font(_FONT_TITLE_PATHS, 58)
        lines = _wrap_text(draw, title_text, title_font, max_width)[:5]
    line_h = title_font.size + 16
    total_h = len(lines) * line_h
    y = (CANVAS_H - total_h) // 2 - 40
    for ln in lines:
        lw = draw.textlength(ln, font=title_font)
        draw.text(((CANVAS_W - lw) // 2, y), ln, fill=_FG, font=title_font)
        y += line_h

    # Footer caption.
    foot_font = _font(_FONT_BODY_PATHS, 28)
    foot = "View on bidvex.com"
    fw = draw.textlength(foot, font=foot_font)
    draw.text(((CANVAS_W - fw) // 2, CANVAS_H - 80), foot, fill=_MUTED, font=foot_font)

    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=85, optimize=True)
    return buf.getvalue()


async def generate_and_upload_placeholder(*, listing_id: str, title: str, category: str = "") -> Optional[str]:
    """Render → upload → return the public S3 URL. Returns None on failure
    so callers can fall back to the static `placeholder-ad.jpg`."""
    try:
        data = build_placeholder_bytes(title=title, category=category)
    except Exception as e:
        logger.warning(f"[feed_placeholder] render failed for {listing_id}: {e}")
        return None
    key = f"placeholders/{listing_id}.jpg"
    try:
        # iter351 — fix broken imports. Use the s3_service public helpers
        # (`_get_client`, `S3_BUCKET`, `_key_to_url`) instead of the
        # non-existent `s3_client`/`get_cloudfront_url` exports.
        from services.s3_service import _get_client, S3_BUCKET, _key_to_url
        client = _get_client()
        if not client or not S3_BUCKET:
            logger.warning("[feed_placeholder] S3 not configured")
            return None
        client.put_object(
            Bucket=S3_BUCKET,
            Key=key,
            Body=data,
            ContentType="image/jpeg",
            ACL="public-read",
            CacheControl="public, max-age=86400",
        )
        return _key_to_url(key)
    except Exception as e:
        logger.warning(f"[feed_placeholder] s3 upload failed for {listing_id}: {e}")
        return None


# ── Nightly sweep ─────────────────────────────────────────────────────

_LISTING_KINDS = (
    ("listings",              "marketplace"),
    ("multi_item_listings",   "lots"),
    ("vehicle_listings",      "vehicle"),
    ("storage_auctions",      "storage"),
)


def _needs_placeholder(doc: dict) -> bool:
    """A listing needs a placeholder if it has no usable image URL.

    Checks (in order of trust):
      • `images[0]`           — marketplace / lots
      • `photos[0]` / `media[0].url` — vehicles, storage
      • `image_url`, `cover_image` — legacy fields
    """
    candidates = (
        (doc.get("images") or [None])[0],
        (doc.get("photos") or [None])[0],
        (doc.get("media")  or [{}])[0].get("url") if isinstance((doc.get("media") or [{}])[0], dict) else None,
        doc.get("image_url"),
        doc.get("cover_image"),
    )
    for c in candidates:
        if c and isinstance(c, str) and c.startswith(("http://", "https://")) \
           and not c.endswith(".webp"):
            return False
    return True


async def regenerate_missing_feed_placeholders(db) -> dict:
    """Nightly sweep: any active or upcoming listing that lacks a
    valid image URL gets a freshly-rendered placeholder uploaded to
    S3 and stored under `placeholder_image_url`.

    The feed mapper reads `placeholder_image_url` BEFORE falling back
    to the static `/assets/placeholder-ad.jpg`.
    """
    out = {"generated": 0, "errors": 0, "skipped": 0, "by_kind": {}}
    for coll_name, kind in _LISTING_KINDS:
        try:
            async for doc in db[coll_name].find({
                "status": {"$in": ["active", "upcoming"]},
            }, {"_id": 0, "id": 1, "title": 1, "category": 1, "make": 1, "model": 1, "year": 1,
                "images": 1, "photos": 1, "media": 1, "image_url": 1, "cover_image": 1,
                "placeholder_image_url": 1}):
                if doc.get("placeholder_image_url"):
                    out["skipped"] += 1
                    continue
                if not _needs_placeholder(doc):
                    out["skipped"] += 1
                    continue
                # Compose a reasonable title for vehicle docs lacking `title`.
                title = doc.get("title") or " ".join(
                    str(x) for x in (doc.get("year"), doc.get("make"), doc.get("model")) if x
                ).strip()
                category = doc.get("category") or kind
                url = await generate_and_upload_placeholder(
                    listing_id=doc["id"], title=title or "BidVex Listing", category=category,
                )
                if url:
                    await db[coll_name].update_one(
                        {"id": doc["id"]},
                        {"$set": {"placeholder_image_url": url}},
                    )
                    out["generated"] += 1
                    out["by_kind"][kind] = out["by_kind"].get(kind, 0) + 1
                else:
                    out["errors"] += 1
        except Exception as e:
            logger.warning(f"[feed_placeholder] scan {coll_name} failed: {e}")
            out["errors"] += 1
    return out


__all__ = [
    "build_placeholder_bytes",
    "generate_and_upload_placeholder",
    "regenerate_missing_feed_placeholders",
]
