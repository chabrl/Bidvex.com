"""iter396 — Three-pillar Trust Gate for bidding + listing creation.

Central helper used by every write path that requires the caller to have
completed ALL THREE pillars of the Trust Status verification:

    1. Phone verified            (user.phone_verified == True)
    2. Payment method on file    (db.payment_methods row for user_id)
    3. Platform T&C accepted     (user.platform_terms_accepted_at set)

Any user missing any pillar is refused with a structured 403 that the
frontend uses to render the "Complete your Trust Status" prompt with
deep links into the profile settings flow.

Contract:
    async def require_trust_verified(db, user, *, action: str = "bid") -> None:
        raises HTTPException(status_code=403, detail={...}) if the user
        isn't fully verified. `action` is a short slug ('bid', 'list')
        that shapes the human-readable message but does not affect the
        gate logic (all three pillars are always required).

    async def user_can_bid_or_list(db, user) -> Tuple[bool, dict]:
        Read-only variant returning (allowed, reasons_dict) instead of
        raising. Used by /trust-status to compute `can_bid` deterministically.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Tuple

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


async def _has_accepted_terms(db, user) -> bool:
    """True iff the user has accepted the platform T&C at least once.

    Reads `platform_terms_accepted_at` off the user record. Falls back to
    a live DB lookup when the field isn't present on the in-memory model
    (some legacy code paths hand us a User without the fresh field).

    iter400 — Also recognizes a per-listing T&C acceptance as satisfying
    the pillar (any non-empty `auction_agreements` entry counts). This
    handles legacy users who accepted a listing's T&C before the
    platform-level stamp was introduced.
    """
    if _get(user, "platform_terms_accepted_at"):
        return True
    # iter400 — accept a per-listing agreement as proof the user has
    # already legally opted in.
    agreements = _get(user, "auction_agreements") or {}
    if isinstance(agreements, dict) and any(agreements.values()):
        return True
    user_id = _get(user, "id")
    if not user_id:
        return False
    try:
        row = await db.users.find_one(
            {"id": user_id},
            {"_id": 0, "platform_terms_accepted_at": 1, "auction_agreements": 1},
        )
        if not row:
            return False
        if row.get("platform_terms_accepted_at"):
            return True
        # DB fallback for the per-listing acceptance signal.
        db_agreements = row.get("auction_agreements") or {}
        if isinstance(db_agreements, dict) and any(db_agreements.values()):
            return True
    except Exception:  # noqa: BLE001
        return False
    return False


async def user_can_bid_or_list(db, user) -> Tuple[bool, Dict[str, Any]]:
    """Read-only three-pillar check. Never raises.

    Returns `(allowed, reasons)` where `reasons` shape is:
        {
          "phone_verified":     bool,
          "has_payment_method": bool,
          "terms_accepted":     bool,
          "missing":            ["phone" | "payment_method" | "terms" | ...],
        }
    """
    user_id = _get(user, "id")
    phone_verified = bool(_get(user, "phone_verified", False))
    has_pm = await _has_payment_method(db, user_id)
    terms_ok = await _has_accepted_terms(db, user)

    missing = []
    if not phone_verified:
        missing.append("phone")
    if not has_pm:
        missing.append("payment_method")
    if not terms_ok:
        missing.append("terms")

    return (len(missing) == 0), {
        "phone_verified":     phone_verified,
        "has_payment_method": has_pm,
        "terms_accepted":     terms_ok,
        "missing":            missing,
    }


async def require_trust_verified(db, user, *, action: str = "bid") -> None:
    """Raise 403 with a structured `trust_required` payload if the caller
    hasn't completed ALL THREE pillars: phone verified, card on file, and
    platform T&C accepted.

    `action` is either `"bid"` or `"list"` and only shapes the message —
    the three-pillar requirement is identical for both actions.
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
    if "terms" in reasons["missing"]:
        parts_en.append("accept the auction Terms & Conditions")
        parts_fr.append("accepter les conditions générales des enchères")
    what_en = " and ".join(parts_en) if parts_en else "complete your Trust Status"
    what_fr = " et ".join(parts_fr) if parts_fr else "compléter votre statut de confiance"

    # Deep-link the CTA to the most-actionable pillar. When only terms are
    # missing we jump straight to the terms modal anchor so the user can
    # accept in one click.
    if reasons["missing"] == ["terms"]:
        cta_path = "/profile/settings#terms"
    else:
        cta_path = "/profile/settings#trust"

    raise HTTPException(
        status_code=403,
        detail={
            "error":              "trust_required",
            "action":             action,
            "missing":            reasons["missing"],
            "phone_verified":     reasons["phone_verified"],
            "has_payment_method": reasons["has_payment_method"],
            "terms_accepted":     reasons["terms_accepted"],
            "message_en":         (
                f"Complete your Trust Status before you can {verb_en}. "
                f"Please {what_en}."
            ),
            "message_fr":         (
                f"Complétez votre statut de confiance avant de {verb_fr}. "
                f"Veuillez {what_fr}."
            ),
            "cta_path":           cta_path,
        },
    )
