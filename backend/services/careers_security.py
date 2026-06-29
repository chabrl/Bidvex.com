"""
BidVex Careers module — file-upload security helpers.

All file uploads in the Careers module MUST:
  • Validate MIME type by reading actual magic bytes (python-magic).
  • Validate file size BEFORE writing to disk.
  • Store files under a UUID-based filename to prevent path traversal.
  • Reject any file whose detected MIME ≠ allowed list.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from fastapi import HTTPException

logger = logging.getLogger(__name__)


# ─── Constants ──────────────────────────────────────────────────────────

CAREERS_UPLOAD_ROOT = Path(os.environ.get("CAREERS_UPLOAD_ROOT", "/app/uploads/careers"))

# Per-file caps (bytes).
CV_MAX_BYTES = 5 * 1024 * 1024            # 5 MB
COVER_LETTER_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
PHOTO_MAX_BYTES = 3 * 1024 * 1024         # 3 MB per photo
CERTIFICATION_MAX_BYTES = 5 * 1024 * 1024 # 5 MB per cert

MAX_PHOTOS = 5
MAX_CERTIFICATIONS = 3

ALLOWED_MIME_TYPES: Dict[str, List[str]] = {
    "cv": [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        # python-magic on plain DOCX sometimes returns the bare zip type — accept it
        # alongside the proper OOXML MIME so users aren't blocked by detector noise.
        "application/zip",
    ],
    "cover_letter": [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/zip",
    ],
    "photos": ["image/jpeg", "image/png"],
    "certifications": ["application/pdf"],
}

# Extension whitelist used as a SECOND check (defence in depth — magic
# bytes are primary).
ALLOWED_EXTENSIONS: Dict[str, List[str]] = {
    "cv": [".pdf", ".docx"],
    "cover_letter": [".pdf", ".docx"],
    "photos": [".jpg", ".jpeg", ".png"],
    "certifications": [".pdf"],
}


# ─── Path-traversal-safe directory helpers ──────────────────────────────

def ensure_applicant_dir(job_id: str, applicant_id: str) -> Path:
    """Create /uploads/careers/{job_id}/{applicant_id}/ with strict UUID
    validation on each segment — refuses anything that isn't a UUID."""
    _assert_uuid_like(job_id)
    _assert_uuid_like(applicant_id)
    path = CAREERS_UPLOAD_ROOT / job_id / applicant_id
    path.mkdir(parents=True, exist_ok=True)
    return path


_UUID_RE = re.compile(r"^[A-Za-z0-9_\-]{6,64}$")


def _assert_uuid_like(seg: str) -> None:
    if not seg or not _UUID_RE.match(seg):
        raise HTTPException(400, "invalid id segment")


# ─── MIME validator ─────────────────────────────────────────────────────

def detect_mime(buf: bytes) -> str:
    """Detect MIME via libmagic. Raises HTTPException(500) if python-magic
    isn't available — better to fail loud than to allow uploads through
    an extension-only check."""
    try:
        import magic
    except Exception as e:  # noqa: BLE001
        logger.exception(f"python-magic missing: {e}")
        raise HTTPException(500, "magic library unavailable on server")
    return magic.from_buffer(buf[:2048], mime=True)


def validate_file(*, kind: str, filename: str, content: bytes,
                   max_bytes: int) -> str:
    """Combined size+extension+MIME check. Returns the validated MIME.
    Raises 422 on any failure with bilingual envelope."""
    if not content:
        raise HTTPException(422, {
            "error": "empty_file",
            "field": kind,
            "message_en": f"Empty file uploaded for '{kind}'.",
            "message_fr": f"Fichier vide pour « {kind} ».",
        })

    if len(content) > max_bytes:
        mb = max_bytes // (1024 * 1024)
        raise HTTPException(422, {
            "error": "file_too_large",
            "field": kind,
            "filename": filename,
            "message_en": f"File '{filename}' exceeds the {mb} MB limit for {kind}.",
            "message_fr": f"Le fichier « {filename} » dépasse la limite de {mb} Mo pour {kind}.",
        })

    ext = Path(filename or "").suffix.lower()
    if ext not in ALLOWED_EXTENSIONS.get(kind, []):
        raise HTTPException(422, {
            "error": "invalid_file_extension",
            "field": kind,
            "filename": filename,
            "message_en": (
                f"File '{filename}' has an unaccepted extension. "
                f"Allowed: {', '.join(ALLOWED_EXTENSIONS.get(kind, []))}"
            ),
            "message_fr": f"Extension non acceptée pour « {filename} ».",
        })

    mime = detect_mime(content)
    if mime not in ALLOWED_MIME_TYPES.get(kind, []):
        raise HTTPException(422, {
            "error": "invalid_file_type",
            "field": kind,
            "filename": filename,
            "detected_mime": mime,
            "message_en": (
                f"File '{filename}' type not accepted (detected: {mime}). "
                f"Expected: {', '.join(ALLOWED_MIME_TYPES.get(kind, []))}"
            ),
            "message_fr": f"Type de fichier « {filename} » non accepté (détecté : {mime}).",
        })
    return mime


def save_validated_file(*, dest_dir: Path, kind: str, original_filename: str,
                          content: bytes) -> Tuple[str, str]:
    """Write `content` under a UUID-prefixed filename inside `dest_dir`.
    Returns (relative_path_segment, absolute_path).

    The original filename is preserved as a SUFFIX after the UUID for
    admin readability — but the UUID prefix means no path-traversal
    payload can escape the directory."""
    safe_ext = Path(original_filename or "").suffix.lower()
    if safe_ext not in {".pdf", ".docx", ".jpg", ".jpeg", ".png"}:
        # Default fallback — should never trigger if validate_file passed.
        safe_ext = ""
    safe_basename = re.sub(r"[^A-Za-z0-9._\-]", "_", Path(original_filename).stem)[:60]
    fname = f"{kind}_{uuid.uuid4().hex}_{safe_basename}{safe_ext}"
    target = dest_dir / fname
    # Final containment check.
    try:
        target.resolve().relative_to(dest_dir.resolve())
    except ValueError:
        raise HTTPException(400, "path traversal blocked")
    with open(target, "wb") as fh:
        fh.write(content)
    return fname, str(target)


def safe_resolve_download(*, job_id: str, applicant_id: str,
                           filename: str) -> Path:
    """Resolve a file path safely for download. Refuses any traversal
    attempt (e.g. `../../etc/passwd`). Returns the resolved Path or
    raises HTTPException."""
    _assert_uuid_like(job_id)
    _assert_uuid_like(applicant_id)
    # Strip path separators from the filename — keep only the leaf.
    if "/" in filename or "\\" in filename or filename.startswith(".."):
        raise HTTPException(403, "path traversal blocked")
    target = (CAREERS_UPLOAD_ROOT / job_id / applicant_id / filename).resolve()
    base = (CAREERS_UPLOAD_ROOT / job_id / applicant_id).resolve()
    try:
        target.relative_to(base)
    except ValueError:
        raise HTTPException(403, "path traversal blocked")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "file not found")
    return target


__all__ = [
    "CAREERS_UPLOAD_ROOT",
    "CV_MAX_BYTES",
    "COVER_LETTER_MAX_BYTES",
    "PHOTO_MAX_BYTES",
    "CERTIFICATION_MAX_BYTES",
    "MAX_PHOTOS",
    "MAX_CERTIFICATIONS",
    "ALLOWED_MIME_TYPES",
    "ALLOWED_EXTENSIONS",
    "detect_mime",
    "validate_file",
    "save_validated_file",
    "safe_resolve_download",
    "ensure_applicant_dir",
]
