"""
Phase 5 Hotfix v4 — Marketplace S3 image service.

A dedicated S3 client for marketplace listing photos. Intentionally separate
from `services/cloud_storage.py` (which targets a Cloudflare R2 bucket for
compliance documents) so the two image domains don't collide on bucket
names or credentials.

Public API:
    upload_image_to_s3(file, listing_id, index)       async UploadFile -> URL
    upload_base64_to_s3(base64_str, listing_id, idx)  async str        -> URL
    delete_s3_image(url)                              sync  URL        -> bool

Image processing (applied to BOTH upload paths):
    * 10 MB hard maximum on raw input.
    * Auto-rotate via EXIF orientation.
    * Resize to fit within 2000×2000 px (preserves aspect ratio).
    * Re-encode to JPEG, quality 85, progressive, no metadata.
    * Object ACL set to `public-read` so Meta's crawler and public web
      buyers can fetch the photo without an auth handshake.

Storage layout:
    s3://{bucket}/listings/{listing_id}/{index:02d}-{ulid8}.jpg

`{ulid8}` is an 8-char random suffix so re-uploading at the same index
never overwrites a previous photo (S3 keys are immutable from the
listing's POV — old URLs stop working only when explicitly deleted).
"""
from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import re
import secrets
from typing import Optional, Tuple
from urllib.parse import urlparse

import boto3
from botocore.exceptions import BotoCoreError, ClientError
from fastapi import UploadFile
from PIL import Image, ImageOps

logger = logging.getLogger("s3_service")

# ── Config (intentionally namespaced — separate from the R2 doc bucket) ──
_AWS_ACCESS_KEY = os.environ.get("MARKETPLACE_AWS_ACCESS_KEY_ID")
_AWS_SECRET_KEY = os.environ.get("MARKETPLACE_AWS_SECRET_ACCESS_KEY")
_AWS_REGION     = os.environ.get("MARKETPLACE_AWS_REGION", "us-east-2")
_S3_BUCKET      = os.environ.get("MARKETPLACE_S3_BUCKET_NAME", "bidvex-marketplace-images")
_S3_BASE_URL    = (
    os.environ.get("MARKETPLACE_S3_BASE_URL")
    or f"https://{_S3_BUCKET}.s3.{_AWS_REGION}.amazonaws.com"
).rstrip("/")

# Limits & quality tuning
MAX_RAW_BYTES        = 10 * 1024 * 1024   # 10 MB
MAX_PIXEL_DIMENSION  = 2000               # px on the longest edge
JPEG_QUALITY         = 85
ACCEPTED_MIME_PREFIX = ("image/jpeg", "image/png", "image/webp", "image/heic", "image/heif")


# ── Lazy-init S3 client ────────────────────────────────────────────────
_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    if not (_AWS_ACCESS_KEY and _AWS_SECRET_KEY):
        raise RuntimeError(
            "MARKETPLACE_AWS_ACCESS_KEY_ID / SECRET not configured. "
            "Add them to backend/.env before uploading marketplace images."
        )
    _client = boto3.client(
        "s3",
        aws_access_key_id=_AWS_ACCESS_KEY,
        aws_secret_access_key=_AWS_SECRET_KEY,
        region_name=_AWS_REGION,
    )
    return _client


# ── Image processing ──────────────────────────────────────────────────
def _process_image_bytes(raw: bytes) -> bytes:
    """Compress + resize image bytes. Returns JPEG-encoded bytes.

    * Auto-rotates per EXIF.
    * Downsizes to fit within MAX_PIXEL_DIMENSION on the longest edge.
    * Strips metadata.
    * Re-encodes as JPEG, quality 85, progressive.
    """
    if len(raw) > MAX_RAW_BYTES:
        raise ValueError(f"image exceeds {MAX_RAW_BYTES // (1024*1024)}MB limit")

    with Image.open(io.BytesIO(raw)) as im:
        # Strip EXIF rotation and flatten to RGB (handles RGBA, palette images)
        im = ImageOps.exif_transpose(im)
        if im.mode in ("RGBA", "P", "LA"):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1] if im.mode in ("RGBA", "LA") else None)
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")

        # Cap longest edge at MAX_PIXEL_DIMENSION (no upscaling)
        if max(im.size) > MAX_PIXEL_DIMENSION:
            im.thumbnail((MAX_PIXEL_DIMENSION, MAX_PIXEL_DIMENSION), Image.LANCZOS)

        out = io.BytesIO()
        im.save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True, progressive=True)
        return out.getvalue()


# ── Key construction ──────────────────────────────────────────────────
def _safe_listing_id(listing_id: str) -> str:
    """Strip any path-traversal characters from listing_id."""
    return re.sub(r"[^a-zA-Z0-9_-]", "", str(listing_id or "unknown"))[:64] or "unknown"


def _build_key(listing_id: str, index: int) -> str:
    safe_id = _safe_listing_id(listing_id)
    suffix  = secrets.token_hex(4)  # 8-char random
    return f"listings/{safe_id}/{int(index):02d}-{suffix}.jpg"


def _key_to_url(key: str) -> str:
    return f"{_S3_BASE_URL}/{key}"


# ── Public API ────────────────────────────────────────────────────────
async def upload_image_to_s3(file: UploadFile, listing_id: str, index: int) -> str:
    """Compress + upload a FastAPI `UploadFile` to S3. Returns the public URL."""
    raw = await file.read()
    if not raw:
        raise ValueError("uploaded file is empty")

    return await asyncio.to_thread(_upload_bytes_sync, raw, listing_id, index)


async def upload_base64_to_s3(base64_str: str, listing_id: str, index: int) -> str:
    """Decode + compress + upload a base64 data URL (or plain base64) to S3.

    Accepts both `data:image/jpeg;base64,...` and bare `iVBORw0...` strings.
    """
    if not base64_str or not isinstance(base64_str, str):
        raise ValueError("base64_str must be a non-empty string")

    if "," in base64_str and base64_str.startswith("data:"):
        _, payload = base64_str.split(",", 1)
    else:
        payload = base64_str

    try:
        raw = base64.b64decode(payload, validate=False)
    except Exception as e:
        raise ValueError(f"invalid base64: {e}") from e

    if not raw:
        raise ValueError("base64 decoded to empty bytes")

    return await asyncio.to_thread(_upload_bytes_sync, raw, listing_id, index)


def _upload_bytes_sync(raw: bytes, listing_id: str, index: int) -> str:
    processed = _process_image_bytes(raw)
    key       = _build_key(listing_id, index)
    client    = _get_client()
    try:
        client.put_object(
            Bucket=_S3_BUCKET,
            Key=key,
            Body=processed,
            ContentType="image/jpeg",
            ACL="public-read",
            CacheControl="public, max-age=31536000, immutable",
        )
    except (BotoCoreError, ClientError) as e:
        logger.error("S3 put_object failed for key=%s: %s", key, e)
        raise

    url = _key_to_url(key)
    logger.info("uploaded marketplace image: %s (%d -> %d bytes)", url, len(raw), len(processed))
    return url


def delete_s3_image(url: str) -> bool:
    """Best-effort deletion of an S3 object given its public URL.

    Returns True on success, False if the URL doesn't belong to this bucket
    or the delete failed. Never raises — callers can fire-and-forget.
    """
    if not url or not isinstance(url, str):
        return False
    parsed = urlparse(url)
    if _S3_BUCKET not in parsed.netloc:
        return False
    key = parsed.path.lstrip("/")
    if not key:
        return False
    try:
        client = _get_client()
        client.delete_object(Bucket=_S3_BUCKET, Key=key)
        return True
    except (BotoCoreError, ClientError, RuntimeError) as e:
        logger.warning("S3 delete failed for %s: %s", url, e)
        return False


# ── Helpers ───────────────────────────────────────────────────────────
def is_marketplace_s3_url(url: str) -> bool:
    """Returns True if the URL points at our marketplace S3 bucket."""
    if not url or not isinstance(url, str):
        return False
    return _S3_BUCKET in url and url.startswith("https://")


def is_base64_image(value: str) -> bool:
    """Best-effort detection of base64 data URLs that need migration."""
    if not value or not isinstance(value, str):
        return False
    return value.startswith("data:image/") or (
        len(value) > 1000 and re.fullmatch(r"[A-Za-z0-9+/=\s]+", value[:200]) is not None
    )


# Expose config for unit tests / migration scripts
S3_BUCKET   = _S3_BUCKET
S3_BASE_URL = _S3_BASE_URL
S3_REGION   = _AWS_REGION


# ── Broker document upload (PDF / image, no resizing) ─────────────────
# Used by `POST /api/brokers/upload-documents`. Unlike listing photos,
# broker licenses and corporate-registration certificates are often PDFs
# and MUST NOT be compressed. We stream them straight through.
BROKER_DOC_MAX_BYTES   = 10 * 1024 * 1024
BROKER_DOC_MIME_ALLOW  = (
    "application/pdf",
    "image/jpeg", "image/jpg", "image/png", "image/webp",
)


def _safe_label(label: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_-]", "", str(label or "doc"))[:32] or "doc"


async def upload_broker_document(file: UploadFile, user_id: str, label: str = "doc") -> str:
    """Upload a broker registration document (PDF / image) to S3.

    Returns the public HTTPS URL. PDFs are uploaded as-is (no resize).
    Images > 2000px are re-encoded as JPEG via `_process_image_bytes`
    to keep file sizes small.
    """
    if file.content_type and file.content_type not in BROKER_DOC_MIME_ALLOW:
        raise ValueError(f"unsupported_mime:{file.content_type}")
    raw = await file.read()
    if not raw:
        raise ValueError("uploaded file is empty")
    if len(raw) > BROKER_DOC_MAX_BYTES:
        raise ValueError(f"file_too_large:max_{BROKER_DOC_MAX_BYTES // (1024*1024)}MB")

    safe_uid    = _safe_listing_id(user_id)
    safe_label_ = _safe_label(label)
    suffix      = secrets.token_hex(4)

    if (file.content_type or "").startswith("image/"):
        body         = _process_image_bytes(raw)
        key          = f"broker-docs/{safe_uid}/{safe_label_}-{suffix}.jpg"
        content_type = "image/jpeg"
    else:
        body         = raw
        ext          = "pdf" if "pdf" in (file.content_type or "") else "bin"
        key          = f"broker-docs/{safe_uid}/{safe_label_}-{suffix}.{ext}"
        content_type = file.content_type or "application/pdf"

    def _upload():
        client = _get_client()
        client.put_object(
            Bucket=_S3_BUCKET,
            Key=key,
            Body=body,
            ContentType=content_type,
            ACL="public-read",
            CacheControl="public, max-age=86400",
        )

    await asyncio.to_thread(_upload)
    url = _key_to_url(key)
    logger.info("broker doc uploaded: %s (label=%s, %d bytes)", url, label, len(body))
    return url
