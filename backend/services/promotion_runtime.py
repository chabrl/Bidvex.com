"""
iter242 Mission 2 — Centralized promotion application for runtime fee paths.

This module is the single integration point between
`routes.admin_promotions.apply_active_promotions()` and the live
fee-calculation paths (Stripe checkout, buyer premium, seller commission,
listing fees). It returns a structured discount block that callers slot
into their pricing math.

The contract:
    >>> discount = await compute_promotion_discount(
    ...     db, user_id="u1", transaction_type="bid",
    ...     listing_type="marketplace", base_amount_cad=100.0,
    ... )
    >>> discount.applies          # True / False
    >>> discount.discount_amount  # in CAD
    >>> discount.final_amount     # base - discount, floored at 0
    >>> discount.is_full_waiver   # True if 100% off (skip Stripe entirely)
    >>> discount.promotion_id     # for record_promotion_usage()
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional

from routes.admin_promotions import apply_active_promotions


@dataclass
class PromotionDiscount:
    """Standard discount block returned by `compute_promotion_discount`."""
    applies: bool
    promotion_id: Optional[str] = None
    promotion_type: Optional[str] = None
    coupon_code: Optional[str] = None
    discount_percent: float = 0.0
    discount_amount: float = 0.0
    final_amount: float = 0.0
    is_full_waiver: bool = False
    raw_promotion: Optional[Dict[str, Any]] = None
    saved_amount_cad: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d.pop("raw_promotion", None)  # keep dict serializable
        return d


# Map each transaction_type → which promotion types waive it.
_WAIVERS_BY_TX = {
    "listing_fee":         {"free_first_listing", "free_platform_fee"},
    "listing_promotion":   {"free_promotion_boost", "free_platform_fee"},
    "buyer_premium":       {"free_platform_fee"},
    "seller_commission":   {"free_platform_fee", "reduced_commission", "free_first_listing"},
    "subscription_upgrade":{"subscription_discount", "free_platform_fee"},
}


async def compute_promotion_discount(
    db,
    user_id: str,
    transaction_type: str,
    base_amount_cad: float,
    listing_type: Optional[str] = None,
    coupon_code: Optional[str] = None,
) -> PromotionDiscount:
    """Single entry-point for every checkout/invoice path.

    Args:
        db:               Motor DB handle.
        user_id:          The acting user's UUID.
        transaction_type: One of `listing_fee | listing_promotion |
                          buyer_premium | seller_commission |
                          subscription_upgrade`.
        base_amount_cad:  The pre-discount amount in CAD (float).
        listing_type:     Optional scope hint for the promotion engine
                          (`marketplace | lots | storage | vehicles | all`).
        coupon_code:      Optional coupon code (case-insensitive) — if set,
                          the engine ONLY considers that exact promo.
    """
    matched = await apply_active_promotions(
        db=db,
        user_id=user_id,
        transaction_type=transaction_type,
        listing_type=listing_type,
        coupon_code=coupon_code,
    )
    if not matched:
        return PromotionDiscount(applies=False, final_amount=float(base_amount_cad))

    ptype = matched.get("type")
    cfg = matched.get("config", {}) or {}

    # Determine whether this transaction is even eligible for the matched
    # promotion type (e.g. a `reduced_commission` promo can't waive a
    # `listing_promotion` purchase).
    eligible = ptype in _WAIVERS_BY_TX.get(transaction_type, set())
    if not eligible:
        return PromotionDiscount(applies=False, final_amount=float(base_amount_cad))

    # Compute the discount percentage from the promotion config.
    if ptype in ("free_platform_fee", "free_first_listing", "free_promotion_boost"):
        pct = 100.0
    elif ptype in ("reduced_commission", "subscription_discount"):
        pct = float(cfg.get("discount_percent", 0))
    else:
        pct = float(cfg.get("discount_percent", 0))

    pct = max(0.0, min(100.0, pct))
    base = float(base_amount_cad or 0.0)
    discount_amount = round(base * (pct / 100.0), 2)
    final_amount = max(0.0, round(base - discount_amount, 2))
    full_waiver = pct >= 100.0 or final_amount == 0.0

    return PromotionDiscount(
        applies=True,
        promotion_id=matched.get("id"),
        promotion_type=ptype,
        coupon_code=matched.get("coupon_code"),
        discount_percent=pct,
        discount_amount=discount_amount,
        final_amount=final_amount,
        is_full_waiver=full_waiver,
        raw_promotion=matched,
        saved_amount_cad=discount_amount,
    )


async def apply_and_record_discount(
    db,
    user_id: str,
    transaction_type: str,
    base_amount_cad: float,
    *,
    listing_type: Optional[str] = None,
    coupon_code: Optional[str] = None,
    transaction_id: Optional[str] = None,
    record_usage: bool = True,
) -> PromotionDiscount:
    """iter243 Mission 3 — Compute discount AND record usage atomically.

    This is the canonical entry-point that the buyer_premium, seller_commission,
    listing_fee, and subscription_upgrade paths should call. It:
      1. Resolves the best applicable promotion (or returns no-op).
      2. If a promotion matched AND `record_usage=True`, atomically bumps
         `promotion.current_uses` and logs the redemption via
         `record_promotion_usage()`.
      3. Returns the discount block for the caller to slot into invoices /
         Stripe metadata.

    The caller is responsible for storing the returned `promotion_id` +
    `discount_amount` in their invoice/ledger record.
    """
    from routes.admin_promotions import record_promotion_usage
    discount = await compute_promotion_discount(
        db=db,
        user_id=user_id,
        transaction_type=transaction_type,
        listing_type=listing_type,
        base_amount_cad=base_amount_cad,
        coupon_code=coupon_code,
    )
    if discount.applies and record_usage and discount.promotion_id:
        try:
            await record_promotion_usage(
                db=db,
                promotion_id=discount.promotion_id,
                user_id=user_id,
                transaction_id=transaction_id,
                transaction_type=transaction_type,
                saved_amount=discount.discount_amount,
            )
        except Exception:
            # Never let a usage-log failure break the underlying transaction.
            pass
    return discount


__all__ = ["compute_promotion_discount", "apply_and_record_discount", "PromotionDiscount"]
