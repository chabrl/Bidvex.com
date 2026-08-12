"""
BidVex — Canonical Payment-Method Registry
==========================================

iter482 P4A — Seller-Controlled Payment Methods

Single source of truth for the accepted-payment-method list used across
every listing / auction / transaction model.  Consumers MUST import
from this module rather than re-declaring constants.

Rules (per Master Payment Remediation §1, §14):
  * A seller declares one or more accepted methods at auction creation.
  * The declaration is SNAPSHOTTED (immutable) at first bid.
  * Only the buyer's selection from the accepted list can drive
    checkout.  Selecting an unaccepted method → 400
    ``PAYMENT_METHOD_NOT_ACCEPTED``.

Guardrails honoured:
  * DO NOT hardcode a fifth method here — the four constants are the
    exhaustive list.
  * DO NOT silently default missing configuration to any value.
  * DO NOT touch historical data — see the backfill script for the
    one-time additive migration.

Canonical method slugs (lower-case, no punctuation aside from
``etransfer`` which is a single token):

    stripe    — Stripe card / debit / Apple Pay / Google Pay / wallets
    etransfer — Interac e-Transfer (Canada) or wire transfer
    cash      — Physical currency, paid on pickup
    cheque    — Bank cheque, mailed / hand-delivered

Aliases (accepted at API boundary, normalised to canonical on write):
    e_transfer, e-transfer  → etransfer
    card, stripe_card       → stripe
    check                   → cheque
"""

from __future__ import annotations
from typing import Iterable, List, Set

# ── Canonical, exhaustive method list ────────────────────────────────
STRIPE:    str = "stripe"
ETRANSFER: str = "etransfer"
CASH:      str = "cash"
CHEQUE:    str = "cheque"

ALL_METHODS: List[str] = [STRIPE, ETRANSFER, CASH, CHEQUE]
ALL_METHODS_SET: Set[str] = set(ALL_METHODS)

# Methods that generate a Stripe rail cost and therefore MAY be subject
# to buyer-facing processing recovery (only when L-1 legal gate opens).
STRIPE_RAIL_METHODS: Set[str] = {STRIPE}

# Offline methods — no Stripe rail cost, no processing recovery ever.
OFFLINE_METHODS: Set[str] = {ETRANSFER, CASH, CHEQUE}

# Alias resolution (input → canonical).  Any string not in this map is
# rejected by ``normalise`` with ``ValueError``.
_ALIASES = {
    "stripe":       STRIPE,
    "stripe_card":  STRIPE,
    "card":         STRIPE,
    "etransfer":    ETRANSFER,
    "e_transfer":   ETRANSFER,
    "e-transfer":   ETRANSFER,
    "cash":         CASH,
    "cheque":       CHEQUE,
    "check":        CHEQUE,
}


class InvalidPaymentMethodError(ValueError):
    """Raised for unrecognised or empty payment-method slugs."""


def normalise(method: str) -> str:
    """Canonicalise a single method slug.  Case-insensitive.

    >>> normalise("Stripe")     == "stripe"
    >>> normalise("E-Transfer") == "etransfer"
    >>> normalise("check")      == "cheque"

    Raises:
        InvalidPaymentMethodError: on empty or unrecognised input.
    """
    if not method or not isinstance(method, str):
        raise InvalidPaymentMethodError("payment method must be a non-empty string")
    key = method.strip().lower().replace(" ", "_")
    if key in ALL_METHODS_SET:
        return key
    canon = _ALIASES.get(key)
    if canon is None:
        raise InvalidPaymentMethodError(
            f"Unknown payment method '{method}'. "
            f"Allowed: {ALL_METHODS}"
        )
    return canon


def normalise_list(methods: Iterable[str]) -> List[str]:
    """Canonicalise + dedupe an iterable of method slugs.  Preserves
    the order of first occurrence.

    Raises:
        InvalidPaymentMethodError: if any member is invalid.
        ValueError: if the resulting list is empty (at least one
                    method is required).
    """
    seen: Set[str] = set()
    out: List[str] = []
    for m in methods or []:
        canon = normalise(m)
        if canon not in seen:
            seen.add(canon)
            out.append(canon)
    if not out:
        raise ValueError(
            "accepted_payment_methods must contain at least one method"
        )
    return out


def is_offline(method: str) -> bool:
    """True if the payer bears no Stripe processing charge on this
    method (cash / cheque / e-transfer).  Card = False."""
    return normalise(method) in OFFLINE_METHODS


def carries_stripe_rail(method: str) -> bool:
    """True iff choosing this method actually incurs a Stripe rail cost
    on the platform / partner Connect account."""
    return normalise(method) in STRIPE_RAIL_METHODS


__all__ = [
    "STRIPE", "ETRANSFER", "CASH", "CHEQUE",
    "ALL_METHODS", "ALL_METHODS_SET",
    "STRIPE_RAIL_METHODS", "OFFLINE_METHODS",
    "InvalidPaymentMethodError",
    "normalise", "normalise_list",
    "is_offline", "carries_stripe_rail",
]
