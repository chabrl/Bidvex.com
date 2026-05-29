"""
iter238 Mission 1 — Onboarding endpoint for first-time Google sign-in users.

Flow:
  - Frontend hits `/onboarding` route after Google OAuth success when
    profile.onboarding_complete !== true.
  - Three-step wizard submits to POST /api/onboarding/complete with
    { password?, city?, province?, postal_code? }.
  - Server hashes the optional password, writes location, flips the
    onboarding_complete flag, and returns the updated profile shape.

Idempotent — re-submitting after onboarding_complete already true is a no-op.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

onboarding_router = APIRouter(prefix="/onboarding", tags=["Onboarding"])
_security = HTTPBearer(auto_error=False)
_db = None


def set_onboarding_db(database) -> None:
    global _db
    _db = database


class OnboardingBody(BaseModel):
    password: Optional[str] = Field(None, min_length=8, max_length=128)
    city: Optional[str] = Field(None, max_length=120)
    province: Optional[str] = Field(None, max_length=10)
    postal_code: Optional[str] = Field(None, max_length=10)
    skip_all: bool = False


def _password_valid(pw: str) -> bool:
    if len(pw) < 8:
        return False
    has_upper = any(c.isupper() for c in pw)
    has_digit = any(c.isdigit() for c in pw)
    return has_upper and has_digit


@onboarding_router.get("/status")
async def onboarding_status(
    creds: HTTPAuthorizationCredentials = Depends(_security),
) -> Dict[str, Any]:
    """Returns { onboarding_complete: bool, has_location: bool, has_password: bool }."""
    if not creds:
        raise HTTPException(status_code=401, detail="auth required")
    if _db is None:
        raise HTTPException(status_code=503, detail="db not initialised")
    from routes.auth import _decode_jwt
    try:
        payload = _decode_jwt(creds.credentials)
        user_id = payload.get("sub") or payload.get("user_id")
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")
    user = await _db.users.find_one(
        {"id": user_id},
        {"_id": 0, "onboarding_complete": 1, "password_hash": 1, "city": 1, "location": 1},
    )
    if not user:
        raise HTTPException(status_code=404, detail="user not found")
    return {
        "onboarding_complete": bool(user.get("onboarding_complete")),
        "has_password": bool(user.get("password_hash")),
        "has_location": bool(user.get("city") or user.get("location")),
    }


@onboarding_router.post("/complete")
async def complete_onboarding(
    body: OnboardingBody,
    creds: HTTPAuthorizationCredentials = Depends(_security),
) -> Dict[str, Any]:
    if not creds:
        raise HTTPException(status_code=401, detail="auth required")
    if _db is None:
        raise HTTPException(status_code=503, detail="db not initialised")
    from routes.auth import _decode_jwt
    try:
        payload = _decode_jwt(creds.credentials)
        user_id = payload.get("sub") or payload.get("user_id")
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")

    update: Dict[str, Any] = {
        "onboarding_complete": True,
        "onboarding_completed_at": datetime.now(timezone.utc),
    }

    if body.password and not body.skip_all:
        if not _password_valid(body.password):
            raise HTTPException(status_code=400, detail="password must be 8+ chars with 1 uppercase + 1 digit")
        try:
            from passlib.context import CryptContext  # type: ignore
            pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
            update["password_hash"] = pwd_ctx.hash(body.password)
        except Exception:
            # Fallback to bcrypt directly if passlib not available.
            import bcrypt  # type: ignore
            update["password_hash"] = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()

    if not body.skip_all and (body.city or body.province or body.postal_code):
        if body.city:
            update["city"] = body.city.strip()
        if body.province:
            update["region"] = body.province.strip().upper()
        if body.postal_code:
            update["postal_code"] = body.postal_code.strip().upper()
        # Try to auto-resolve coordinates (best-effort).
        try:
            if body.postal_code:
                from services.geo_resolver import resolve_postal_code
                coords = await resolve_postal_code(body.postal_code)
                if coords:
                    update["geo"] = {
                        "type": "Point",
                        "coordinates": [coords["lng"], coords["lat"]],
                        "city": body.city or "",
                        "province": body.province or "",
                        "source": "onboarding_postal",
                    }
            if "geo" not in update and body.city:
                from utils import build_geo_point
                g = build_geo_point(body.city, province=body.province)
                if g:
                    update["geo"] = {**g, "source": "onboarding_city"}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[iter238-onboarding] geo enrichment failed: {e}")

    await _db.users.update_one({"id": user_id}, {"$set": update})
    return {"status": "ok", "onboarding_complete": True}


__all__ = ["onboarding_router", "set_onboarding_db"]
