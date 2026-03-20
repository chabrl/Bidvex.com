"""
BidVex Cloud Invoice Storage Service
Stores PDF invoices in Emergent Object Storage.
Generates HMAC-signed time-limited download URLs via backend proxy.
"""

import hashlib
import hmac
import os
import time
import logging
import requests
import uuid

logger = logging.getLogger(__name__)

# ── Emergent Object Storage config ──────────────────────────────────
STORAGE_URL = "https://integrations.emergentagent.com/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "bidvex"

# ── Signed-URL config (backend auth, unchanged) ────────────────────
SIGNING_SECRET = os.environ.get("INVOICE_SIGNING_SECRET", os.environ.get("JWT_SECRET", "fallback-secret"))
DEFAULT_EXPIRY_SECONDS = 3600  # 1 hour

# Module-level storage key (session-scoped, initialized once)
_storage_key = None


def _init_storage():
    """Initialize Emergent Object Storage once. Returns the reusable storage_key."""
    global _storage_key
    if _storage_key:
        return _storage_key
    resp = requests.post(
        f"{STORAGE_URL}/init",
        json={"emergent_key": EMERGENT_KEY},
        timeout=30,
    )
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    logger.info("Emergent Object Storage initialized successfully")
    return _storage_key


def _put_object(path: str, data: bytes, content_type: str) -> dict:
    """Upload file to Emergent Object Storage."""
    key = _init_storage()
    resp = requests.put(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key, "Content-Type": content_type},
        data=data,
        timeout=120,
    )
    resp.raise_for_status()
    return resp.json()


def _get_object(path: str) -> bytes | None:
    """Download file from Emergent Object Storage. Returns bytes or None."""
    key = _init_storage()
    resp = requests.get(
        f"{STORAGE_URL}/objects/{path}",
        headers={"X-Storage-Key": key},
        timeout=60,
    )
    if resp.status_code == 404:
        return None
    resp.raise_for_status()
    return resp.content


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
    return f"{base_url}/api/invoices/download/{invoice_id}?expires={expires}&sig={sig}"


def verify_signature(invoice_id: str, expires: int, sig: str) -> bool:
    if int(time.time()) > expires:
        return False
    payload = f"{invoice_id}:{expires}"
    expected = _sign(payload)
    return hmac.compare_digest(sig, expected)


# ── Public API (same interface as before) ───────────────────────────

async def store_invoice_pdf(invoice_id: str, pdf_data: bytes, subfolder: str = "general") -> str:
    """
    Upload a PDF to Emergent Object Storage.
    Returns the canonical storage path.
    """
    storage_path = f"{APP_NAME}/invoices/{subfolder}/{invoice_id}.pdf"
    try:
        result = _put_object(storage_path, pdf_data, "application/pdf")
        canonical = result.get("path", storage_path)
        logger.info(f"Invoice uploaded to cloud: {canonical} ({len(pdf_data)} bytes)")
        return canonical
    except Exception as e:
        logger.error(f"Cloud upload failed for {invoice_id}: {e}")
        raise


async def retrieve_invoice_pdf(storage_path: str) -> bytes | None:
    """Download a stored PDF from Emergent Object Storage."""
    try:
        data = _get_object(storage_path)
        if data is None:
            logger.warning(f"Invoice not found in cloud: {storage_path}")
        return data
    except Exception as e:
        logger.error(f"Cloud download failed for {storage_path}: {e}")
        return None


async def delete_invoice_pdf(storage_path: str) -> bool:
    """Soft-delete only (Emergent storage has no delete API). Returns True always."""
    logger.info(f"Soft-delete requested for {storage_path} (no-op in cloud)")
    return True
