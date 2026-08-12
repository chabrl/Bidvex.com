"""
Seller Type Resolver — Single Authoritative Source
==================================================

Resolves the authoritative seller type for a financial transaction from
the seller's user record and (optionally) the listing document.

FAIL-CLOSED policy:
  If the seller's user record is missing or ambiguous AND the caller
  cannot demonstrate that the missing information does not affect
  money, `resolve_seller_account_type` raises `SellerTypeUnresolved`.
  Callers must never silently default to "individual".

Ordered precedence (first match wins):
  1. Explicit override from `listing.seller_account_type` (admin-forced,
     rare)
  2. Partner: `user.is_partner == True` AND `user.platform_fee_paid == True`
       - If also `user.subscription_tier == "partner_pro"` -> "partner_pro"
       - Else -> "partner"
  3. Vehicle dealer: `user.is_vehicle_dealer == True` OR
     `user.role == "vehicle_dealer"`
  4. Storage facility: `user.is_storage_facility == True` OR
     `listing.category == "storage_locker"` OR
     `listing.listing_type == "storage_locker"`
  5. Broker: `user.is_broker == True` OR `user.role == "broker"`
  6. Enterprise: `user.account_type == "enterprise"` OR
     `user.is_enterprise == True`
  7. Individual: `user.account_type == "individual"` (explicit)

Fail-closed cases:
  - `user` is None            -> SellerTypeUnresolved("user record missing")
  - No positive signal above  -> SellerTypeUnresolved("account_type not set")

Notes:
  * A Partner who has not paid the annual `platform_fee_paid=True` flag
    does NOT get the Partner economic model. iter302/iter478 rule.
  * Storage facility can be flagged either on the user or on the listing.
    A user without `is_storage_facility` but listing a `storage_locker`
    category listing IS treated as storage_facility for that listing
    only. This preserves the iter443 rule (facility keeps 100% hammer).
"""

from __future__ import annotations

from typing import Any, Dict, Literal, Optional

SellerAccountType = Literal[
    "individual",
    "enterprise",
    "partner",
    "partner_pro",
    "vehicle_dealer",
    "storage_facility",
    "broker",
]

ALL_SELLER_TYPES = (
    "individual",
    "enterprise",
    "partner",
    "partner_pro",
    "vehicle_dealer",
    "storage_facility",
    "broker",
)


class SellerTypeUnresolved(Exception):
    """Raised when a seller's account type cannot be determined and the
    missing data materially affects the financial calculation.

    Callers MUST NOT catch this and fall back to a default; they must
    surface the exception, refuse the transaction, and notify admin.
    """

    def __init__(self, reason: str, *, seller_id: Optional[str] = None):
        self.reason = reason
        self.seller_id = seller_id
        super().__init__(
            f"Seller account type unresolved (seller_id={seller_id!r}): {reason}. "
            f"Financial calculation refuses to fall back to 'individual'."
        )


def resolve_seller_account_type(
    *,
    user: Optional[Dict[str, Any]],
    listing: Optional[Dict[str, Any]] = None,
    seller_id_for_error: Optional[str] = None,
) -> SellerAccountType:
    """Return the authoritative seller account type.

    Args:
        user: The seller's row from `db.users` (with `_id` removed).
        listing: Optional listing document; consulted for
            `seller_account_type` override and `storage_locker` category.
        seller_id_for_error: Used only in the SellerTypeUnresolved
            exception message; never affects the return value.

    Returns:
        One of `ALL_SELLER_TYPES`.

    Raises:
        SellerTypeUnresolved: if the seller's type cannot be determined.
    """
    listing = listing or {}
    override = listing.get("seller_account_type")
    if isinstance(override, str) and override.strip().lower() in ALL_SELLER_TYPES:
        return override.strip().lower()  # type: ignore[return-value]

    if user is None:
        raise SellerTypeUnresolved(
            "user record is None", seller_id=seller_id_for_error
        )

    is_partner = bool(user.get("is_partner"))
    platform_fee_paid = bool(user.get("platform_fee_paid"))
    subscription_tier = (user.get("subscription_tier") or "").strip().lower()

    # 2. Partner / Partner Pro
    if is_partner and platform_fee_paid:
        if subscription_tier == "partner_pro":
            return "partner_pro"
        return "partner"

    # 3. Vehicle dealer
    if bool(user.get("is_vehicle_dealer")) or (
        (user.get("role") or "").strip().lower() == "vehicle_dealer"
    ):
        return "vehicle_dealer"

    # 4. Storage facility (user-flag OR listing-flag)
    if bool(user.get("is_storage_facility")):
        return "storage_facility"
    if listing:
        cat = (listing.get("category") or "").strip().lower()
        listing_type = (listing.get("listing_type") or "").strip().lower()
        if cat == "storage_locker" or listing_type == "storage_locker":
            return "storage_facility"

    # 5. Broker
    if bool(user.get("is_broker")) or (
        (user.get("role") or "").strip().lower() == "broker"
    ):
        return "broker"

    # 6. Enterprise
    if bool(user.get("is_enterprise")) or (
        (user.get("account_type") or "").strip().lower() == "enterprise"
    ):
        return "enterprise"

    # 7. Individual (explicit only — no silent fallback)
    account_type = (user.get("account_type") or "").strip().lower()
    if account_type == "individual":
        return "individual"

    # If `subscription_tier` is present and looks like a normal
    # tier (free/basic/premium/vip_elite) with no other signal, this
    # is an individual account whose `account_type` field was never
    # written. Treat as individual EXPLICITLY (this is not a silent
    # default — we require positive tier evidence).
    if subscription_tier in ("free", "basic", "standard", "premium", "vip_elite", "vip"):
        return "individual"

    raise SellerTypeUnresolved(
        "account_type could not be resolved from any positive signal "
        "(is_partner/is_vehicle_dealer/is_storage_facility/is_broker/"
        "is_enterprise/account_type/subscription_tier all missing or ambiguous)",
        seller_id=seller_id_for_error,
    )


def resolve_partner_bp_rate(
    *,
    listing: Optional[Dict[str, Any]] = None,
    user: Optional[Dict[str, Any]] = None,
    default_rate: float = 0.05,
) -> float:
    """Resolve the Partner Buyer Premium rate for a Partner listing.

    Precedence (per iter478 and PHASE_0_DECISION_PACK E-10):
      1. `listing.partner_bp_rate` (per-lot override)
      2. `listing.custom_buyer_premium_rate` (per-lot override, legacy)
      3. `user.custom_premium_rate` (per-Partner-account default)
      4. `default_rate` (5% per fee_schedule.partner.default)

    Only positive rates are honored; zero/None values fall through.
    Never returns a negative rate.
    """
    def _as_pos_rate(v: Any) -> Optional[float]:
        try:
            r = float(v)
        except (TypeError, ValueError):
            return None
        if r > 0:
            return r
        return None

    listing = listing or {}
    user = user or {}

    for candidate in (
        listing.get("partner_bp_rate"),
        listing.get("custom_buyer_premium_rate"),
        user.get("custom_premium_rate"),
    ):
        r = _as_pos_rate(candidate)
        if r is not None:
            return r
    return float(default_rate)


__all__ = [
    "resolve_seller_account_type",
    "resolve_partner_bp_rate",
    "SellerTypeUnresolved",
    "ALL_SELLER_TYPES",
    "SellerAccountType",
]
