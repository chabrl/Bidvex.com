"""
iter323 — Contractor profile + IVR + leaderboard + SendGrid inbound parse.

Endpoints
─────────
GET    /api/twilio/contractor/profile/me
    Returns the calling contractor's profile (extension, personal phone,
    profile photo URL, name, email). Used by the dashboard header.

PATCH  /api/twilio/contractor/profile/me
    Updates `personal_phone_number` (E.164) on the contractor's own
    record. Cannot update extension_number (server-assigned, immutable).

POST   /api/twilio/contractor/profile/photo
    Multipart upload of a single profile image. Reuses s3_service's
    image upload pipeline. Returns the new `profile_photo_url`.

GET    /api/twilio/contractor/leaderboard
    INTENTIONAL DATA-ISOLATION EXCEPTION (iter323 directive 4).
    Returns the FULL ranked list of every active contractor:
    rank, name, profile photo URL, this week's volume score (rounded),
    leaderboard_overlay_rate, trend ▲/▼/—. Dollar earnings stay private
    per-contractor. The caller's own row is marked `is_self: true`.

GET    /api/twilio/contractor/extension/me
    Convenience read-only endpoint: returns the caller's extension number
    for display in the dashboard.

GET    /api/twilio/contractor/inbound-calls
    Returns the caller's own log of inbound extension calls
    (date/time, duration, outcome). Per-contractor data-isolation.

# IVR routes
POST   /api/twilio/ivr/incoming
    TwiML webhook for the main +1 450 634 3099 line. Plays a
    bilingual prompt, then <Gather>s the extension digits.
POST   /api/twilio/ivr/route
    Receives Gather'd digits → looks up contractor → <Dial>s their
    personal phone with the BidVex caller-ID + a whisper announcement.
POST   /api/twilio/ivr/whisper
    TwiML sub-endpoint that the contractor's leg hits when the call
    bridges — plays "Incoming BidVex call from <client>" before the
    legs are joined.
POST   /api/twilio/ivr/status
    Status callback for inbound-extension calls. Updates the log row
    with duration, outcome (answered/missed/busy).

# SendGrid inbound parse webhook
POST   /api/sendgrid/inbound-parse
    Multipart POST from SendGrid when a client replies to a
    partners+c{contractor_id}@reply.bidvex.ca address. Parses the
    contractor tag, attaches the reply to the original thread, and
    fires an in-app notification.
"""
from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Request, UploadFile,
)
from pydantic import BaseModel, Field

from deps import get_current_user, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Contractor — iter323"])


# ─── Shared helpers ──────────────────────────────────────────────────────


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


def _validate_e164(phone: str) -> bool:
    return bool(E164_RE.match(phone or ""))


# Avoid circular imports: pull these lazily inside handlers.
def _get_db():
    from deps import get_db
    return get_db()


def _require_contractor(user: User = Depends(get_current_user)) -> User:
    """FastAPI dependency. Allows dialer_contractor + admin/super_admin
    (admins are permitted so they can debug + view leaderboard)."""
    if not user:
        raise HTTPException(401, "auth required")
    role = getattr(user, "role", None)
    if role != "dialer_contractor" and role not in {"admin", "super_admin"}:
        raise HTTPException(403, "contractor only")
    return user


# ─── Pydantic models ────────────────────────────────────────────────────


class UpdateProfileBody(BaseModel):
    personal_phone_number: Optional[str] = Field(None, max_length=20)


# ─── Profile endpoints (Directive 3A + 5) ───────────────────────────────


@router.get("/twilio/contractor/profile/me")
async def get_my_contractor_profile(user: User = Depends(_require_contractor)) -> Dict[str, Any]:
    db = _get_db()
    doc = await db.users.find_one(
        {"id": user.id},
        {
            "_id": 0, "password": 0, "password_hash": 0,
        },
    )
    if not doc:
        raise HTTPException(404, "profile not found")
    # iter323 — ensure the extension exists (lazy-assign on first read for
    # legacy contractors who predate iter323).
    if not doc.get("extension_number") and doc.get("role") == "dialer_contractor":
        try:
            from services.contractor_extensions import assign_extension
            ext = await assign_extension(db, user.id)
            doc["extension_number"] = ext
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[iter323] lazy ext-assign failed for {user.id}: {e}")

    return {
        "id":                   doc.get("id"),
        "email":                doc.get("email"),
        "name":                 doc.get("name") or
                                  f"{doc.get('first_name','')} {doc.get('last_name','')}".strip(),
        "first_name":           doc.get("first_name"),
        "last_name":            doc.get("last_name"),
        "phone":                doc.get("phone"),
        "personal_phone_number": doc.get("personal_phone_number"),
        "extension_number":     doc.get("extension_number"),
        "profile_photo_url":    doc.get("profile_photo_url"),
        "preferred_language":   doc.get("preferred_language") or "en",
        "role":                 doc.get("role"),
    }


@router.patch("/twilio/contractor/profile/me")
async def update_my_contractor_profile(
    body: UpdateProfileBody,
    user: User = Depends(_require_contractor),
) -> Dict[str, Any]:
    db = _get_db()
    updates: Dict[str, Any] = {"updated_at": _now_iso()}
    if body.personal_phone_number is not None:
        phone = body.personal_phone_number.strip()
        if not _validate_e164(phone):
            raise HTTPException(422, {
                "error": "invalid_phone",
                "message_en": "Personal phone must be in E.164 format (e.g. +14501234567).",
                "message_fr": "Le téléphone personnel doit être au format E.164 (ex. +14501234567).",
            })
        updates["personal_phone_number"] = phone
    if len(updates) == 1:  # only updated_at set
        return await get_my_contractor_profile(user=user)
    await db.users.update_one({"id": user.id}, {"$set": updates})
    return await get_my_contractor_profile(user=user)


# ─── Profile photo upload (Directive 5) ─────────────────────────────────


# Reuse the platform's existing image pipeline so the upload limits +
# resize + S3 routing match what's already used for listing photos.
PROFILE_PHOTO_MAX_BYTES = 5 * 1024 * 1024  # 5MB — same ballpark as listing photos
PROFILE_PHOTO_ALLOWED = {"image/jpeg", "image/png", "image/webp"}


@router.post("/twilio/contractor/profile/photo")
async def upload_my_profile_photo(
    file: UploadFile = File(...),
    user: User = Depends(_require_contractor),
) -> Dict[str, Any]:
    db = _get_db()
    # Light client-side validation; the s3_service does deeper checks.
    if file.content_type not in PROFILE_PHOTO_ALLOWED:
        raise HTTPException(422, {
            "error": "invalid_image_type",
            "message_en": "Profile photo must be JPEG, PNG, or WEBP.",
            "message_fr": "La photo de profil doit être en JPEG, PNG ou WEBP.",
        })
    raw = await file.read()
    if not raw:
        raise HTTPException(400, "empty upload")
    if len(raw) > PROFILE_PHOTO_MAX_BYTES:
        raise HTTPException(413, {
            "error": "image_too_large",
            "message_en": f"Profile photo must be ≤ {PROFILE_PHOTO_MAX_BYTES//(1024*1024)}MB.",
            "message_fr": f"La photo de profil doit faire ≤ {PROFILE_PHOTO_MAX_BYTES//(1024*1024)}Mo.",
        })

    # Reuse the existing s3 image pipeline. We piggy-back on the listing-photo
    # upload signature by giving the file a `contractor_{user_id}` pseudo-listing
    # key — the bucket prefix differentiation is handled inside s3_service.
    try:
        from services.s3_service import _upload_bytes_sync
        # Run blocking upload in a worker thread so the ASGI loop stays free.
        import asyncio
        url = await asyncio.to_thread(
            _upload_bytes_sync, raw, f"contractor-{user.id[:12]}", 0,
        )
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[iter323] profile photo upload failed: {e}")
        raise HTTPException(503, {
            "error": "upload_failed",
            "message_en": "Could not upload your profile photo. Please retry.",
            "message_fr": "Téléversement de la photo échoué. Veuillez réessayer.",
        })

    await db.users.update_one(
        {"id": user.id},
        {"$set": {
            "profile_photo_url":         url,
            "profile_photo_uploaded_at": _now_iso(),
            "updated_at":                _now_iso(),
        }},
    )
    return {"ok": True, "profile_photo_url": url}


# ─── Extension read endpoint (Directive 3B) ─────────────────────────────


@router.get("/twilio/contractor/extension/me")
async def get_my_extension(user: User = Depends(_require_contractor)) -> Dict[str, Any]:
    db = _get_db()
    from services.contractor_extensions import (
        get_extension_for_contractor, assign_extension,
    )
    ext = await get_extension_for_contractor(db, user.id)
    if not ext and getattr(user, "role", "") == "dialer_contractor":
        ext = await assign_extension(db, user.id)
    return {
        "extension_number": ext,
        "support_phone":    "+1 450 634 3099",
        "share_text_en": (
            f"You can reach me directly on +1 (450) 634-3099 ext. {ext}." if ext else
            "Your extension is being provisioned — please refresh in a moment."
        ),
        "share_text_fr": (
            f"Vous pouvez me joindre directement au +1 (450) 634-3099 poste {ext}." if ext else
            "Votre poste est en cours d'attribution — actualisez dans un instant."
        ),
    }


# ─── Inbound call log endpoint (Directive 3E) ───────────────────────────


@router.get("/twilio/contractor/inbound-calls")
async def list_my_inbound_calls(
    user: User = Depends(_require_contractor),
    limit: int = 50,
    skip: int = 0,
) -> Dict[str, Any]:
    db = _get_db()
    limit = max(1, min(int(limit or 50), 200))
    skip = max(0, int(skip or 0))
    cursor = db.inbound_extension_calls.find(
        {"contractor_id": user.id}, {"_id": 0},
    ).sort("started_at", -1).skip(skip).limit(limit)
    items = [doc async for doc in cursor]
    total = await db.inbound_extension_calls.count_documents({"contractor_id": user.id})
    return {"items": items, "total": total, "limit": limit, "skip": skip}


# ─── Leaderboard (Directive 4) ──────────────────────────────────────────


def _trend_marker(now_rank: Optional[int], last_rank: Optional[int]) -> str:
    """Tiny pure helper — returns '▲' / '▼' / '—' for the trend column.
    Lower rank number = better position (rank 1 is #1)."""
    if now_rank is None or last_rank is None:
        return "—"
    if now_rank < last_rank:
        return "▲"
    if now_rank > last_rank:
        return "▼"
    return "—"


@router.get("/twilio/contractor/leaderboard")
async def get_contractor_leaderboard(caller: User = Depends(_require_contractor)) -> Dict[str, Any]:
    """
    INTENTIONAL DATA-ISOLATION EXCEPTION (iter323 directive 4).
    ──────────────────────────────────────────────────────────
    Every contractor in the platform sees every other contractor's
    rank, display name, profile photo, volume score, and overlay rate %.
    This is by design — the contract's "Dynamic Leaderboard & Game-Based
    Commission Scheme" framing makes competitive visibility the explicit
    point. Dollar earnings stay private and are NEVER included here.

    DO NOT lock this endpoint to "own data only" in any future security
    audit — that would break the game mechanic. The exception is enforced
    consciously and documented in iter323 PRD notes.
    """
    db = _get_db()

    # Pull every active contractor + their overlay rate.
    contractors = []
    cursor = db.users.find(
        {"role": "dialer_contractor", "is_active": {"$ne": False}},
        {"_id": 0, "id": 1, "name": 1, "first_name": 1, "last_name": 1, "email": 1,
         "profile_photo_url": 1, "extension_number": 1,
         "leaderboard_overlay_rate": 1, "leaderboard_history": 1,
         "weekly_volume_score": 1},
    )
    async for c in cursor:
        contractors.append(c)

    # Sort by weekly_volume_score desc, then by most recent overlay change.
    def _score(c: Dict[str, Any]) -> float:
        v = c.get("weekly_volume_score")
        try:
            return float(v) if v is not None else 0.0
        except (TypeError, ValueError):
            return 0.0

    contractors.sort(key=_score, reverse=True)

    rows: List[Dict[str, Any]] = []
    for idx, c in enumerate(contractors):
        history = c.get("leaderboard_history") or []
        # `leaderboard_history` is the leaderboard_overlay service's audit
        # trail; entries have `rank` + `week_starting`. Pull the most
        # recent and the one before that to compute the trend.
        prev_rank = None
        if isinstance(history, list) and len(history) >= 2:
            try:
                # `history[-1]` is THIS week, `history[-2]` is last week.
                prev_rank = int(history[-2].get("rank")) if history[-2].get("rank") is not None else None
            except (TypeError, ValueError):
                prev_rank = None

        now_rank = idx + 1
        display_name = (c.get("name") or
                        f"{c.get('first_name','')} {c.get('last_name','')}".strip() or
                        c.get("email") or
                        "BidVex Partner")

        rows.append({
            "rank":                    now_rank,
            "display_name":            display_name,
            "profile_photo_url":       c.get("profile_photo_url"),
            "extension_number":        c.get("extension_number"),
            "weekly_volume_score":     round(_score(c), 2),
            "leaderboard_overlay_rate": float(c.get("leaderboard_overlay_rate") or 0.0),
            "trend":                   _trend_marker(now_rank, prev_rank),
            "is_self":                 (c.get("id") == caller.id),
        })

    return {
        "rows":         rows,
        "total":        len(rows),
        "caller_id":    caller.id,
        # The week stamp matches the leaderboard_overlay cron's window.
        "generated_at": _now_iso(),
        "data_isolation_exception": (
            "iter323-directive-4 — contractor leaderboard intentionally "
            "shares names + photos + overlay% + ranks across all contractors. "
            "Dollar earnings remain private per contractor."
        ),
    }


__all__ = ["router"]
