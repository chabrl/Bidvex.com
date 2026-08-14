"""
iter484 — Reserve Price Settlement Gate
=======================================

Single-source-of-truth helper for the "reserve not met" auction-close
decision.  Consumed by:

  * ``services.auction_settlement.settle_auction`` — halts the
    payment pipeline BEFORE any Stripe charge is created.
  * ``routes.auctions`` (single-listing + multi-lot flows) — flips the
    listing/lot status to ``reserve_not_met`` and creates the
    system-generated Auction Request row for admin review.

Design
------
* Reserve is stored in CAD dollars.  ``None`` OR ``0`` OR a negative
  value means "no reserve set — proceed normally".
* For multi-lot auctions the lot-level ``reserve_price`` OVERRIDES the
  auction-level one when both are present.
* This module is purely functional — no DB writes, no side effects.
"""
from __future__ import annotations

from typing import Any, Optional


def _coerce_price(value: Any) -> Optional[float]:
    """Return a positive float or None."""
    if value in (None, "", False):
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    if v <= 0:
        return None
    return round(v, 2)


def resolve_reserve_price(
    listing: dict,
    lot: Optional[dict] = None,
) -> Optional[float]:
    """Return the effective reserve price for this settlement.

    Precedence:
        1. lot.reserve_price  (lot-level wins)
        2. listing.reserve_price
        3. None
    """
    if lot is not None:
        lot_reserve = _coerce_price(lot.get("reserve_price"))
        if lot_reserve is not None:
            return lot_reserve
    return _coerce_price((listing or {}).get("reserve_price"))


def is_reserve_met(
    hammer_price: float,
    reserve_price: Optional[float],
) -> bool:
    """True when settlement may proceed.  A missing / 0 / negative
    reserve is treated as "no reserve" → always met."""
    if reserve_price is None:
        return True
    try:
        h = float(hammer_price)
    except (TypeError, ValueError):
        return True
    return h >= float(reserve_price)


__all__ = ["resolve_reserve_price", "is_reserve_met"]
