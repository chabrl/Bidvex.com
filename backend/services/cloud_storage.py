"""
BidVex Secure Invoice Storage Service
Stores PDF invoices on persistent local storage outside /app.
Generates HMAC-signed time-limited download URLs.

Architecture designed for easy swap to S3/GCS — only this file changes.
"""

import hashlib
import hmac
import os
import time
import logging
from pathlib import Path
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

# Storage root OUTSIDE /app to survive redeploys
STORAGE_ROOT = Path(os.environ.get("INVOICE_STORAGE_ROOT", "/data/invoices"))
SIGNING_SECRET = os.environ.get("INVOICE_SIGNING_SECRET", os.environ.get("JWT_SECRET", "fallback-secret"))
DEFAULT_EXPIRY_SECONDS = 3600  # 1 hour


def _ensure_storage():
    """Create storage directory if it doesn't exist."""
    STORAGE_ROOT.mkdir(parents=True, exist_ok=True)


def _sign(payload: str) -> str:
    """HMAC-SHA256 signature for a payload string."""
    return hmac.new(
        SIGNING_SECRET.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()


def generate_signed_url(invoice_id: str, expiry_seconds: int = DEFAULT_EXPIRY_SECONDS, base_url: str = "") -> str:
    """
    Create a time-limited signed download URL for an invoice.
    Returns path like /api/invoices/download/<invoice_id>?expires=...&sig=...
    """
    expires = int(time.time()) + expiry_seconds
    payload = f"{invoice_id}:{expires}"
    sig = _sign(payload)
    return f"{base_url}/api/invoices/download/{invoice_id}?expires={expires}&sig={sig}"


def verify_signature(invoice_id: str, expires: int, sig: str) -> bool:
    """Verify an HMAC-signed download URL. Returns False if expired or tampered."""
    if int(time.time()) > expires:
        return False
    payload = f"{invoice_id}:{expires}"
    expected = _sign(payload)
    return hmac.compare_digest(sig, expected)


async def store_invoice_pdf(invoice_id: str, pdf_data: bytes, subfolder: str = "general") -> str:
    """
    Store a PDF on disk and return its internal storage path.
    subfolder examples: 'subscription', 'lots_won', 'payment_letter', 'seller_statement'
    """
    _ensure_storage()
    target_dir = STORAGE_ROOT / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{invoice_id}.pdf"
    file_path = target_dir / filename
    file_path.write_bytes(pdf_data)
    logger.info(f"Invoice stored: {file_path} ({len(pdf_data)} bytes)")
    return str(file_path)


async def retrieve_invoice_pdf(storage_path: str) -> bytes | None:
    """Read a stored PDF from its storage path. Returns None if missing."""
    p = Path(storage_path)
    if p.exists():
        return p.read_bytes()
    logger.warning(f"Invoice file not found at {storage_path}")
    return None


async def delete_invoice_pdf(storage_path: str) -> bool:
    """Delete a stored PDF."""
    p = Path(storage_path)
    if p.exists():
        p.unlink()
        return True
    return False
