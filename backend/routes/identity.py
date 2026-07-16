"""
iter355 — Identity verification routes (Stripe Identity, KYC soft-gate).

Endpoints:
    POST /api/identity/verify         → create/reuse VerificationSession
    GET  /api/identity/status         → live status (webhook + poll refresh)

Winning-bid soft-gate lives in routes/settlement.py + vehicle_settlement.py.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from deps import User, get_current_user
from services.stripe_identity import (
    create_or_get_session,
    refresh_status_from_stripe,
)

logger = logging.getLogger(__name__)

identity_router = APIRouter(prefix="/identity", tags=["Identity"])

_db = None


def set_identity_db(db_instance):
    global _db
    _db = db_instance


def _get_db():
    if _db is None:
        raise RuntimeError("Identity router: database not initialized")
    return _db


class VerifyRequest(BaseModel):
    return_url: Optional[str] = None


@identity_router.post("/verify")
async def start_verification(
    body: VerifyRequest,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Create (or reuse) a Stripe Identity VerificationSession.

    Returns:
        {
          verification_session_id: "vs_...",
          client_secret:           "vs_client_secret_...",
          status:                  "requires_input"|"processing"|...,
          url:                     "https://verify.stripe.com/..."  (hosted flow),
          reused:                  bool,
        }

    Frontend uses `client_secret` with `@stripe/stripe-js`
    `stripe.verifyIdentity(client_secret)` for the embedded modal flow,
    OR redirects the user to `url` for the hosted flow (mobile fallback).
    """
    db = _get_db()

    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    if user_doc.get("is_identity_verified"):
        return {
            "already_verified": True,
            "is_identity_verified": True,
            "stripe_identity_status": "verified",
        }

    try:
        session = await create_or_get_session(
            db,
            user=user_doc,
            return_url=body.return_url,
        )
    except RuntimeError as exc:
        # Stripe key not configured — 503, not 500.
        raise HTTPException(status_code=503, detail={
            "error": "STRIPE_IDENTITY_UNAVAILABLE",
            "message_en": "Identity verification is temporarily unavailable. Please try again shortly.",
            "message_fr": "La vérification d'identité est temporairement indisponible. Veuillez réessayer sous peu.",
            "detail": str(exc),
        })
    except Exception as exc:  # noqa: BLE001
        logger.exception(
            f"[identity] verify start failed for user={current_user.id}: {exc}"
        )
        raise HTTPException(status_code=502, detail={
            "error": "STRIPE_IDENTITY_ERROR",
            "message_en": "Could not start identity verification. Please try again.",
            "message_fr": "Impossible de démarrer la vérification d'identité. Veuillez réessayer.",
        })

    return {
        "verification_session_id": session["id"],
        "client_secret": session["client_secret"],
        "status": session["status"],
        "url": session.get("url"),
        "reused": session.get("reused", False),
        "is_identity_verified": False,
    }


@identity_router.get("/status")
async def verification_status(
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Return the current KYC state for `current_user`.

    Poll-friendly — the frontend can hit this every few seconds after the
    user closes the Stripe modal to detect the `verified` transition even
    before the webhook fires.
    """
    db = _get_db()
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")

    live = await refresh_status_from_stripe(db, user_doc)
    return {
        "is_identity_verified": bool(live.get("is_identity_verified")),
        "stripe_identity_status": live.get("stripe_identity_status"),
        "stripe_verification_session_id": live.get("stripe_verification_session_id"),
        "identity_legal_name": user_doc.get("identity_legal_name"),
        "last_error_reason": user_doc.get("stripe_identity_last_error_reason"),
    }
