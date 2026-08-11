"""
BidVex Cloud Invoice Storage Service
Stores PDF invoices in S3-compatible object storage (AWS S3, Cloudflare R2, MinIO, etc.).
Generates HMAC-signed time-limited download URLs via backend proxy.
"""

import hashlib
import hmac
import os
import time
import logging
import uuid
import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# ── S3 config ───────────────────────────────────────────────────────
S3_BUCKET = os.environ.get("S3_BUCKET_NAME", "bidvex-storage")
S3_REGION = os.environ.get("S3_REGION", "us-east-1")
S3_ENDPOINT_URL = os.environ.get("S3_ENDPOINT_URL")  # For R2/MinIO; leave unset for AWS S3
APP_NAME = "bidvex"

# ── Signed-URL config (backend auth, unchanged) ────────────────────
SIGNING_SECRET = os.environ.get("INVOICE_SIGNING_SECRET", os.environ.get("JWT_SECRET", "fallback-secret"))
DEFAULT_EXPIRY_SECONDS = 3600  # 1 hour

# Module-level S3 client (initialized once)
_s3_client = None


def _get_s3():
    """Get or create the S3 client."""
    global _s3_client
    if _s3_client:
        return _s3_client

    kwargs = {
        "service_name": "s3",
        "region_name": S3_REGION,
    }
    # Support custom endpoints for Cloudflare R2, MinIO, etc.
    if S3_ENDPOINT_URL:
        kwargs["endpoint_url"] = S3_ENDPOINT_URL

    _s3_client = boto3.client(**kwargs)
    logger.info("S3 storage client initialized")
    return _s3_client


def _put_object(path: str, data: bytes, content_type: str, acl: str = "private") -> dict:
    """Upload file to S3 with explicit ACL (default: private)."""
    client = _get_s3()
    params = {
        "Bucket": S3_BUCKET,
        "Key": path,
        "Body": data,
        "ContentType": content_type,
    }
    if acl:
        params["ACL"] = acl
    client.put_object(**params)
    return {"path": path}


def _get_object(path: str) -> bytes | None:
    """Download file from S3. Returns bytes or None."""
    client = _get_s3()
    try:
        response = client.get_object(Bucket=S3_BUCKET, Key=path)
        return response["Body"].read()
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return None
        raise


def _delete_object(path: str) -> bool:
    """Delete a file from S3."""
    client = _get_s3()
    try:
        client.delete_object(Bucket=S3_BUCKET, Key=path)
        return True
    except ClientError:
        return False


# ── HMAC signed-URL helpers (unchanged) ─────────────────────────────

def _sign(payload: str) -> str:
    return hmac.new(
        SIGNING_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def generate_signed_url(invoice_id: str, expiry_seconds: int = DEFAULT_EXPIRY_SECONDS, base_url: str = "") -> str:
    expires = int(time.time()) + expiry_seconds
    payload = f"{invoice_id}:{expires}"
    sig = _sign(payload)
    # iter473 — Resolve absolute public base URL when the caller does
    # not pass one explicitly. The signed path + expiry + signature
    # are preserved exactly — only the host prefix is filled in.
    effective_base = (base_url or _resolve_public_base_url() or "").rstrip("/")
    return f"{effective_base}/api/invoices/download/{invoice_id}?expires={expires}&sig={sig}"


# iter473 — Public base URL resolver for absolute emailed document
# links. Reads from environment in this precedence:
#   1. PUBLIC_BASE_URL   (explicit override; set in .env when needed)
#   2. APP_URL           (backend-facing public host, used elsewhere)
#   3. FRONTEND_URL      (React frontend public host)
#   4. REACT_APP_BACKEND_URL (fallback — same value on this platform)
#
# Never hardcodes a preview / production domain. Rejects blank,
# `localhost`, `127.0.0.1`, and non-http(s) values so a malformed
# env variable never poisons an emailed link. When nothing resolves,
# returns "" and logs a warning — the caller receives a relative
# path (existing behaviour) instead of a silently wrong absolute URL.
_INVALID_HOST_TOKENS = ("localhost", "127.0.0.1", "0.0.0.0")


def _resolve_public_base_url() -> str:
    for var in ("PUBLIC_BASE_URL", "APP_URL", "FRONTEND_URL", "REACT_APP_BACKEND_URL"):
        v = os.environ.get(var, "").strip()
        if not v:
            continue
        v = v.rstrip("/")
        low = v.lower()
        if not (low.startswith("http://") or low.startswith("https://")):
            continue
        if any(tok in low for tok in _INVALID_HOST_TOKENS):
            # Local dev host — safe to skip; try the next var.
            continue
        return v
    logger.warning(
        "[cloud_storage] no public base URL configured "
        "(PUBLIC_BASE_URL / APP_URL / FRONTEND_URL / REACT_APP_BACKEND_URL) — "
        "signed URLs will be relative"
    )
    return ""


def verify_signature(invoice_id: str, expires: int, sig: str) -> bool:
    if int(time.time()) > expires:
        return False
    payload = f"{invoice_id}:{expires}"
    expected = _sign(payload)
    return hmac.compare_digest(sig, expected)


# ── Public API (same interface as before) ───────────────────────────

async def store_invoice_pdf(invoice_id: str, pdf_data: bytes, subfolder: str = "general") -> str:
    """
    Upload a PDF to S3.
    Returns the canonical storage path.
    """
    storage_path = f"{APP_NAME}/invoices/{subfolder}/{invoice_id}.pdf"
    try:
        result = _put_object(storage_path, pdf_data, "application/pdf")
        canonical = result.get("path", storage_path)
        logger.info(f"Invoice uploaded to S3: {canonical} ({len(pdf_data)} bytes)")
        return canonical
    except Exception as e:
        logger.error(f"S3 upload failed for {invoice_id}: {e}")
        raise


async def retrieve_invoice_pdf(storage_path: str) -> bytes | None:
    """Download a stored PDF from S3."""
    try:
        data = _get_object(storage_path)
        if data is None:
            logger.warning(f"Invoice not found in S3: {storage_path}")
        return data
    except Exception as e:
        logger.error(f"S3 download failed for {storage_path}: {e}")
        return None


async def delete_invoice_pdf(storage_path: str) -> bool:
    """Delete a stored PDF from S3."""
    try:
        return _delete_object(storage_path)
    except Exception as e:
        logger.error(f"S3 delete failed for {storage_path}: {e}")
        return False
