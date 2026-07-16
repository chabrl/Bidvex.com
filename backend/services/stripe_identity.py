"""
iter355 — Stripe Identity (KYC) service.

Wraps Stripe VerificationSession creation + retrieval and persists the
verification lifecycle on `db.users`.

Design rules (per H-1 spec):
    • type="document" — passport, driver's license, gov'd photo ID.
    • Verification is a *soft-gate at Checkout/Win* — bidders can bid
      freely; only the winning buyer is forced through KYC before
      /api/settlement/settle can finalize the charge.
    • Existing users are NOT retroactively forced (forward-only). The gate
      only fires when they try to settle a win.
    • Stripe VerificationSession returns a `client_secret` the frontend
      hands to Stripe.js `stripe.verifyIdentity(clientSecret)`. Once the
      user completes the flow, Stripe fires the webhook
      `identity.verification_session.verified` which sets
      `is_identity_verified=True` on the user doc.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe

logger = logging.getLogger(__name__)


def _stripe_ready() -> bool:
    key = os.environ.get("STRIPE_API_KEY", "").strip()
    if not key or key == "sk_test_emergent":
        return False
    stripe.api_key = key
    return True


async def create_or_get_session(
    db,
    user: Dict[str, Any],
    return_url: Optional[str] = None,
) -> Dict[str, Any]:
    """Create (or reuse) a Stripe Identity VerificationSession for `user`.

    Returns a dict with { id, client_secret, status, url } — the frontend
    uses `client_secret` in `stripe.verifyIdentity()` OR redirects to
    `url` for hosted flows.

    Idempotent: if the user already has a `stripe_verification_session_id`
    still in a non-terminal state (`requires_input`, `processing`), we
    retrieve and re-return that session's client_secret instead of
    creating a new one — prevents duplicate Stripe entries on retries.
    """
    if not _stripe_ready():
        raise RuntimeError("Stripe API key not configured")

    user_id = user.get("id") or user.get("_id")
    if not user_id:
        raise ValueError("user must have an 'id' field")

    # Reuse in-flight session if present + still salvageable.
    existing_id = user.get("stripe_verification_session_id")
    if existing_id:
        try:
            existing = stripe.identity.VerificationSession.retrieve(existing_id)
            existing_status = getattr(existing, "status", None)
            # Reusable states: requires_input (user hasn't uploaded yet)
            # + processing (uploaded, awaiting Stripe review).
            if existing_status in ("requires_input", "processing"):
                logger.info(
                    f"[stripe-identity] reusing session {existing_id} "
                    f"for user={user_id} status={existing_status}"
                )
                return {
                    "id": existing.id,
                    "client_secret": existing.client_secret,
                    "status": existing_status,
                    "url": getattr(existing, "url", None),
                    "reused": True,
                }
            # verified / canceled / requires_action(retry) → make a new one.
        except stripe.StripeError as exc:  # type: ignore[attr-defined]
            logger.warning(
                f"[stripe-identity] retrieve stale session {existing_id} "
                f"failed for user={user_id}: {exc} — creating fresh"
            )

    metadata = {
        "bidvex_user_id": str(user_id),
        "bidvex_flow": "bidder_kyc_win_gate",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if user.get("email"):
        metadata["bidvex_user_email"] = str(user["email"])[:120]

    try:
        session = stripe.identity.VerificationSession.create(
            type="document",
            metadata=metadata,
            options={
                "document": {
                    "require_matching_selfie": True,
                    "require_live_capture": True,
                    "allowed_types": [
                        "driving_license",
                        "id_card",
                        "passport",
                    ],
                }
            },
            return_url=return_url or None,
        )
    except stripe.StripeError as exc:  # type: ignore[attr-defined]
        logger.error(
            f"[stripe-identity] create session failed for user={user_id}: {exc}"
        )
        raise

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"id": user_id},
        {
            "$set": {
                "stripe_verification_session_id": session.id,
                "stripe_identity_status": session.status,
                "stripe_identity_started_at": now_iso,
                # Do NOT flip is_identity_verified here — only the webhook
                # sets that (single source of truth).
            }
        },
    )

    logger.info(
        f"[stripe-identity] created session {session.id} for user={user_id} "
        f"status={session.status}"
    )
    return {
        "id": session.id,
        "client_secret": session.client_secret,
        "status": session.status,
        "url": getattr(session, "url", None),
        "reused": False,
    }


async def refresh_status_from_stripe(db, user: Dict[str, Any]) -> Dict[str, Any]:
    """Poll Stripe for the latest session state.

    Called by `GET /api/identity/status` so the frontend can display a
    live status even before the webhook lands. Never mutates
    `is_identity_verified` — only the webhook flips that bit
    (webhook is the single source of truth for eventual consistency).
    """
    session_id = user.get("stripe_verification_session_id")
    if not session_id or not _stripe_ready():
        return {
            "is_identity_verified": bool(user.get("is_identity_verified")),
            "stripe_identity_status": user.get("stripe_identity_status"),
            "stripe_verification_session_id": session_id,
        }
    try:
        session = stripe.identity.VerificationSession.retrieve(session_id)
    except stripe.StripeError as exc:  # type: ignore[attr-defined]
        logger.warning(
            f"[stripe-identity] status refresh failed for session={session_id}: {exc}"
        )
        return {
            "is_identity_verified": bool(user.get("is_identity_verified")),
            "stripe_identity_status": user.get("stripe_identity_status"),
            "stripe_verification_session_id": session_id,
        }

    live_status = getattr(session, "status", None)
    if live_status and live_status != user.get("stripe_identity_status"):
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "stripe_identity_status": live_status,
                "stripe_identity_status_refreshed_at":
                    datetime.now(timezone.utc).isoformat(),
            }},
        )

    return {
        "is_identity_verified": bool(user.get("is_identity_verified"))
                                or live_status == "verified",
        "stripe_identity_status": live_status,
        "stripe_verification_session_id": session_id,
    }


async def apply_webhook_event(
    db,
    event_type: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    """Apply an `identity.verification_session.*` webhook to the user doc.

    Called from `routes/webhooks.py::handle_stripe_webhook`.

    Returns a small dict of what got mutated (for logging).
    """
    session_id = data.get("id") if isinstance(data, dict) else getattr(data, "id", None)
    metadata = (
        data.get("metadata") if isinstance(data, dict) else getattr(data, "metadata", {})
    ) or {}
    user_id = metadata.get("bidvex_user_id") if isinstance(metadata, dict) else None

    # Fallback: session_id lookup if metadata is missing.
    query: Dict[str, Any] = {}
    if user_id:
        query["id"] = user_id
    elif session_id:
        query["stripe_verification_session_id"] = session_id
    else:
        logger.warning(
            f"[stripe-identity] webhook {event_type} missing user_id + session_id"
        )
        return {"skipped": True, "reason": "no_identifier"}

    user_doc = await db.users.find_one(query, {"_id": 0, "id": 1, "email": 1})
    if not user_doc:
        logger.warning(
            f"[stripe-identity] webhook {event_type} — no user found for {query}"
        )
        return {"skipped": True, "reason": "user_not_found", "query": query}

    now_iso = datetime.now(timezone.utc).isoformat()
    update: Dict[str, Any] = {
        "stripe_identity_status_refreshed_at": now_iso,
    }

    if event_type == "identity.verification_session.verified":
        # Extract legal info from `verified_outputs` (SAFE — this is the
        # only PII Stripe returns, and only after verification succeeds).
        verified_outputs = (
            data.get("verified_outputs") if isinstance(data, dict)
            else getattr(data, "verified_outputs", None)
        ) or {}
        legal_name = None
        if isinstance(verified_outputs, dict):
            first = (verified_outputs.get("first_name") or "").strip()
            last = (verified_outputs.get("last_name") or "").strip()
            if first or last:
                legal_name = f"{first} {last}".strip()
        dob_raw = (
            verified_outputs.get("dob") if isinstance(verified_outputs, dict) else None
        ) or {}
        dob_iso = None
        if isinstance(dob_raw, dict) and dob_raw.get("year"):
            try:
                dob_iso = (
                    f"{int(dob_raw['year']):04d}-"
                    f"{int(dob_raw.get('month') or 1):02d}-"
                    f"{int(dob_raw.get('day') or 1):02d}"
                )
            except (TypeError, ValueError):
                dob_iso = None

        update.update({
            "is_identity_verified": True,
            "stripe_identity_status": "verified",
            "stripe_identity_verified_at": now_iso,
            "stripe_verification_session_id": session_id,
        })
        if legal_name:
            update["identity_legal_name"] = legal_name
        if dob_iso:
            update["identity_dob"] = dob_iso

    elif event_type == "identity.verification_session.requires_input":
        # User uploaded something Stripe rejected — surface the reason
        # so the frontend can render a helpful message.
        last_error = (
            data.get("last_error") if isinstance(data, dict)
            else getattr(data, "last_error", None)
        ) or {}
        err_code = last_error.get("code") if isinstance(last_error, dict) else None
        err_reason = last_error.get("reason") if isinstance(last_error, dict) else None
        update.update({
            "stripe_identity_status": "requires_input",
            "stripe_identity_last_error_code": err_code,
            "stripe_identity_last_error_reason": err_reason,
        })

    elif event_type == "identity.verification_session.processing":
        update["stripe_identity_status"] = "processing"

    elif event_type == "identity.verification_session.canceled":
        update["stripe_identity_status"] = "canceled"

    else:
        # Unknown identity event — record status if we have it, no side-effects.
        status = (
            data.get("status") if isinstance(data, dict)
            else getattr(data, "status", None)
        )
        if status:
            update["stripe_identity_status"] = status

    await db.users.update_one({"id": user_doc["id"]}, {"$set": update})
    logger.info(
        f"[stripe-identity] webhook {event_type} applied to user={user_doc['id']} "
        f"→ status={update.get('stripe_identity_status')} "
        f"verified={update.get('is_identity_verified', False)}"
    )
    return {
        "user_id": user_doc["id"],
        "event_type": event_type,
        "status": update.get("stripe_identity_status"),
        "verified": bool(update.get("is_identity_verified")),
    }
