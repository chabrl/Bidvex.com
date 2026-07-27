"""iter395 — Trust-verified gate for bidding + listing creation.

Central helper used by every write path that requires the caller to have
completed BOTH pillars of the Trust Status verification:

    1. Phone verified (user.phone_verified == True)
    2. At least one active payment method on file (db.payment_methods
       has a row for user_id)

Any user missing either pillar is refused with a structured 403 that
the frontend uses to render the "Complete your Trust Status" prompt
with deep links into the profile settings flow.

Contract:
    async def require_trust_verified(db, user, *, action: str = "bid") -> None:
        raises HTTPException(status_code=403, detail={...}) if the user
        isn't fully verified. `action` is a short slug ('bid', 'list')
        that shapes the human-readable message but does not affect the
        gate logic (both pillars are always required).

    async def user_can_bid_or_list(db, user) -> Tuple[bool, dict]:
        Read-only variant returning (allowed, reasons_dict) instead of
        raising. Used by /trust-status to compute `can_bid` deterministically
        (bug fix — previous logic accepted email-verified-only which
        bypassed the two-pillar gate entirely).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from fastapi import HTTPException

logger = logging.getLogger(__name__)


async def _has_payment_method(db, user_id: str) -> bool:
    """True iff the user has ≥1 row in `payment_methods`."""
    if not user_id:
        return False
    try:
        n = await db.payment_methods.count_documents({"user_id": user_id})
        return int(n) > 0
    except Exception:  # noqa: BLE001
        return False


def _get(user: Any, key: str, default=None):
    """Accept either a Pydantic User model or a raw dict."""
    if user is None:
        return default
    if isinstance(user, dict):
        return user.get(key, default)
    return getattr(user, key, default)


async def user_can_bid_or_list(db, user) -> Tuple[bool, Dict[str, Any]]:
    """Read-only two-pillar check. Never raises.

    Returns `(allowed, reasons)` where `reasons` shape is:
        {
          "phone_verified":     bool,
          "has_payment_method": bool,
          "missing":            ["phone" | "payment_method" | ...],   # empty list = allowed
        }
    """
    user_id = _get(user, "id")
    phone_verified = bool(_get(user, "phone_verified", False))
    has_pm = await _has_payment_method(db, user_id)

    missing = []
    if not phone_verified:
        missing.append("phone")
    if not has_pm:
        missing.append("payment_method")

    return (len(missing) == 0), {
        "phone_verified":     phone_verified,
        "has_payment_method": has_pm,
        "missing":            missing,
    }


async def require_trust_verified(db, user, *, action: str = "bid") -> None:
    """Raise 403 with a structured `trust_required` payload if the caller
    hasn't completed BOTH phone verification AND card-on-file.

    `action` is either `"bid"` or `"list"` and only shapes the message —
    the two-pillar requirement is identical for both actions.
    """
    allowed, reasons = await user_can_bid_or_list(db, user)
    if allowed:
        return

    # iter300 P1 — Also enforce the existing suspension guard so admins
    # can freeze a bidder without leaking around the trust gate.
    try:
        from services.bid_guard import ensure_bidding_allowed
        await ensure_bidding_allowed(db, _get(user, "id"))
    except HTTPException:
        raise
    except Exception:  # noqa: BLE001 — bid_guard is optional in some paths
        pass

    # Compose bilingual message
    is_list = action == "list"
    verb_en = "list an item" if is_list else "place a bid"
    verb_fr = "publier une annonce" if is_list else "placer une enchère"
    parts_en = []
    parts_fr = []
    if "phone" in reasons["missing"]:
        parts_en.append("verify your phone number")
        parts_fr.append("vérifier votre numéro de téléphone")
    if "payment_method" in reasons["missing"]:
        parts_en.append("add a valid payment card")
        parts_fr.append("ajouter une carte de paiement valide")
    what_en = " and ".join(parts_en) if parts_en else "complete your Trust Status"
    what_fr = " et ".join(parts_fr) if parts_fr else "compléter votre statut de confiance"

    raise HTTPException(
        status_code=403,
        detail={
            "error":              "trust_required",
            "action":             action,
            "missing":            reasons["missing"],
            "phone_verified":     reasons["phone_verified"],
            "has_payment_method": reasons["has_payment_method"],
            "message_en":         (
                f"Complete your Trust Status before you can {verb_en}. "
                f"Please {what_en}."
            ),
            "message_fr":         (
                f"Complétez votre statut de confiance avant de {verb_fr}. "
                f"Veuillez {what_fr}."
            ),
            "cta_path":           "/profile/settings#trust",
        },
    )
