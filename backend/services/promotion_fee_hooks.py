"""
iter243 Mission 3 — Public helper hooks for the remaining 4 fee paths.

This module exposes plug-in points that the listing-creation and
subscription-upgrade routes can call with minimal disruption.

Pattern:
    >>> hook = await listing_fee_hook(db, user_id, base_amount_cad=4.99,
    ...                              listing_type="marketplace")
    >>> if hook["is_full_waiver"]:
    ...     # Skip Stripe, mark listing live for $0.00
    ... else:
    ...     stripe_amount_cents = int(hook["final_amount"] * 100)
"""
from __future__ import annotations

from typing import Any, Dict, Optional

from services.promotion_runtime import apply_and_record_discount


async def listing_fee_hook(
    db,
    user_id: str,
    base_amount_cad: float,
    *,
    listing_type: str = "marketplace",
    coupon_code: Optional[str] = None,
    record_usage: bool = False,
) -> Dict[str, Any]:
    """Apply active promotions to a listing-creation/upfront fee."""
    discount = await apply_and_record_discount(
        db=db,
        user_id=user_id,
        transaction_type="listing_fee",
        base_amount_cad=base_amount_cad,
        listing_type=listing_type,
        coupon_code=coupon_code,
        record_usage=record_usage,
    )
    return {
        "base_amount": float(base_amount_cad),
        "final_amount": float(discount.final_amount),
        "discount_amount": float(discount.discount_amount),
        "is_full_waiver": bool(discount.is_full_waiver),
        "promotion_id": discount.promotion_id,
        "coupon_code": discount.coupon_code,
        "applies": bool(discount.applies),
    }


async def subscription_upgrade_hook(
    db,
    user_id: str,
    base_amount_cad: float,
    *,
    target_tier: Optional[str] = None,
    coupon_code: Optional[str] = None,
    record_usage: bool = False,
) -> Dict[str, Any]:
    """Apply active promotions to a subscription-tier upgrade checkout.

    `target_tier` is forwarded as `listing_type` so promotions can be
    scoped via the standard scope mechanism (e.g. only premium upgrades).
    """
    discount = await apply_and_record_discount(
        db=db,
        user_id=user_id,
        transaction_type="subscription_upgrade",
        base_amount_cad=base_amount_cad,
        listing_type=target_tier or "all",
        coupon_code=coupon_code,
        record_usage=record_usage,
    )
    return {
        "base_amount": float(base_amount_cad),
        "final_amount": float(discount.final_amount),
        "discount_amount": float(discount.discount_amount),
        "discount_percent": float(discount.discount_percent),
        "is_full_waiver": bool(discount.is_full_waiver),
        "promotion_id": discount.promotion_id,
        "coupon_code": discount.coupon_code,
        "applies": bool(discount.applies),
    }


__all__ = ["listing_fee_hook", "subscription_upgrade_hook"]
