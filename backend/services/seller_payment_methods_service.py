"""
BidVex — Seller-Controlled Payment Methods Service
==================================================

iter482 P4A — Immutable snapshot + validation.

The seller declares which payment methods are accepted for an auction
at creation time.  When the auction receives its first bid, the current
``accepted_payment_methods`` list is FROZEN into
``accepted_payment_methods_snapshot`` and further edits require an
explicit controlled workflow (documented but not implemented in P4A —
returns 409 until an admin flag flips).

This module is deliberately thin and pure — every routine takes the
document dict and returns either the frozen list or raises a domain
exception.  Database writes happen in the caller (routes/services).

Guardrails (Master Payment Remediation §1, §5, §14):
  * NO silent default of methods — every listing MUST declare its list.
  * Snapshot is IMMUTABLE once locked (no in-place mutation).
  * Buyer selection is validated against the SNAPSHOT if locked, else
    against the live list.  Never against a hard-coded fallback.
"""

from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from services.payment_methods_registry import (
    ALL_METHODS,
    normalise,
    normalise_list,
    InvalidPaymentMethodError,
)


class PaymentMethodsError(Exception):
    """Base class for seller-payment-method domain errors."""


class PaymentMethodsLockedError(PaymentMethodsError):
    """Raised when a seller attempts to change accepted_payment_methods
    on a listing that has already received its first bid.  The route
    layer maps this to HTTP 409."""


class PaymentMethodNotAcceptedError(PaymentMethodsError):
    """Raised when a buyer selects a method that is not in the
    accepted list.  The route layer maps this to HTTP 400."""


class PaymentMethodsMissingError(PaymentMethodsError):
    """Raised when a listing has no accepted_payment_methods and no
    legacy singleton ``payment_method`` to fall back on.  The route
    layer maps this to HTTP 422 — the seller must be forced to declare."""


# ────────────────────────────────────────────────────────────────────
# Read-side — resolve the EFFECTIVE list for a listing document
# ────────────────────────────────────────────────────────────────────
def effective_methods(listing: Dict[str, Any]) -> List[str]:
    """Return the authoritative list of accepted methods for a listing.

    Precedence (highest first):
      1. ``accepted_payment_methods_snapshot`` — immutable, set at first
         bid.  If present, this is the ONLY answer.
      2. ``accepted_payment_methods`` — live seller configuration.
      3. Legacy singleton ``payment_method`` (pre-P4A rows).  Wrapped
         into a single-element list for backward compat.
      4. Raise ``PaymentMethodsMissingError``.

    The returned list is normalised (canonical slugs) and de-duped.
    """
    snap = listing.get("accepted_payment_methods_snapshot")
    if isinstance(snap, list) and snap:
        return normalise_list(snap)
    live = listing.get("accepted_payment_methods")
    if isinstance(live, list) and live:
        return normalise_list(live)
    legacy = listing.get("payment_method")
    if isinstance(legacy, str) and legacy.strip():
        try:
            return [normalise(legacy)]
        except InvalidPaymentMethodError:
            pass
    raise PaymentMethodsMissingError(
        f"Listing {listing.get('id') or listing.get('_id')} has no "
        f"accepted_payment_methods declared and no legacy fallback."
    )


def is_locked(listing: Dict[str, Any]) -> bool:
    """True iff the snapshot has been taken (first bid recorded)."""
    return bool(listing.get("accepted_payment_methods_snapshot"))


# ────────────────────────────────────────────────────────────────────
# Write-side — validate / snapshot / edit-guard
# ────────────────────────────────────────────────────────────────────
def validate_new_declaration(methods: List[str]) -> List[str]:
    """Validate a fresh seller declaration.  Called from create-listing
    routes.

    Returns the canonicalised list (safe to persist).
    Raises ``InvalidPaymentMethodError`` or ``ValueError`` (empty).
    """
    canon = normalise_list(methods)
    # At least one method (the registry already enforces this) — nothing
    # else to check in P4A.  Card-eligibility is per-seller Stripe Connect
    # status which is enforced by ``services.stripe_customer_service``
    # at buyer-selection time, not at declaration.
    return canon


def guard_edit(listing: Dict[str, Any], new_methods: List[str]) -> List[str]:
    """Called from listing-update routes when the seller edits
    accepted_payment_methods.  P4A behaviour:

        * If NOT locked → allow the edit; return canonicalised list.
        * If locked → refuse with ``PaymentMethodsLockedError``.

    The controlled workflow to allow post-bid edits is intentionally
    NOT implemented in P4A (deferred to P4B once we have the buyer-
    consent flow to notify existing bidders).
    """
    if is_locked(listing):
        raise PaymentMethodsLockedError(
            "accepted_payment_methods are locked — the auction has "
            "already received a bid.  Contact support to open the "
            "controlled edit workflow."
        )
    return validate_new_declaration(new_methods)


def snapshot_at_first_bid(
    listing: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """If the listing has not been snapshotted yet, produce the DB
    update dict that locks the current live list into
    ``accepted_payment_methods_snapshot`` (and stamps
    ``accepted_payment_methods_locked_at``).  The caller is
    responsible for applying the update to Mongo.

    Returns None if already snapshotted (idempotent).
    """
    if is_locked(listing):
        return None
    live = listing.get("accepted_payment_methods")
    if not isinstance(live, list) or not live:
        legacy = listing.get("payment_method")
        if isinstance(legacy, str) and legacy.strip():
            try:
                live = [normalise(legacy)]
            except InvalidPaymentMethodError:
                live = None
    if not live:
        raise PaymentMethodsMissingError(
            "Cannot snapshot: listing has no accepted_payment_methods "
            "and no legacy fallback."
        )
    canon = normalise_list(live)
    return {
        "accepted_payment_methods_snapshot": canon,
        "accepted_payment_methods_locked_at":
            datetime.now(timezone.utc).isoformat(),
    }


# ────────────────────────────────────────────────────────────────────
# Buyer-selection gate
# ────────────────────────────────────────────────────────────────────
def assert_selection_allowed(
    listing: Dict[str, Any],
    selected: str,
) -> str:
    """Validate that the buyer's chosen payment method is one of the
    accepted methods on this listing.  Returns the canonicalised slug
    on success.  Raises ``PaymentMethodNotAcceptedError`` on failure.

    Uses ``effective_methods`` — the SNAPSHOT wins if the listing has
    received a bid, guaranteeing every bidder sees the terms that were
    in effect when they bid.
    """
    try:
        canon = normalise(selected)
    except InvalidPaymentMethodError as exc:
        raise PaymentMethodNotAcceptedError(str(exc)) from exc
    accepted = effective_methods(listing)
    if canon not in accepted:
        raise PaymentMethodNotAcceptedError(
            f"Payment method '{canon}' is not accepted for this "
            f"auction.  Seller allows: {accepted}"
        )
    return canon


__all__ = [
    "PaymentMethodsError",
    "PaymentMethodsLockedError",
    "PaymentMethodNotAcceptedError",
    "PaymentMethodsMissingError",
    "ALL_METHODS",
    "effective_methods",
    "is_locked",
    "validate_new_declaration",
    "guard_edit",
    "snapshot_at_first_bid",
    "assert_selection_allowed",
    "http_require_methods",
]


# ────────────────────────────────────────────────────────────────────
# HTTP helper — for use in FastAPI route handlers
# ────────────────────────────────────────────────────────────────────
def http_require_methods(methods_in):
    """Validate + canonicalise a payload from a POST/PATCH listing route.

    Empty / missing / invalid → HTTP 400 with bilingual message.
    Returns the canonical list on success.
    """
    from fastapi import HTTPException
    if methods_in is None or (isinstance(methods_in, list) and not methods_in):
        raise HTTPException(status_code=400, detail={
            "error": "accepted_payment_methods_required",
            "message_en": "Please select at least one payment method.",
            "message_fr": "Veuillez sélectionner au moins un mode de paiement.",
        })
    try:
        return validate_new_declaration(list(methods_in))
    except (InvalidPaymentMethodError, ValueError) as exc:
        raise HTTPException(status_code=400, detail={
            "error": "invalid_payment_methods",
            "reason": str(exc),
            "message_en": "One of the payment methods you selected is not allowed. Choose from: card, e-transfer, cash, cheque.",
            "message_fr": "L'un des modes de paiement sélectionnés n'est pas autorisé. Choisissez parmi : carte, virement, espèces, chèque.",
        }) from exc
