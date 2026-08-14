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


# ─────────────────────────────────────────────────────────────────
# iter484.2 Gate 2 — Buyer-facing reserve state masking
# ─────────────────────────────────────────────────────────────────
def _derive_reserve_state(
    reserve_price: Optional[float],
    current_bid: Optional[float],
    stored_reserve_met: Any = None,
) -> str:
    """Return the buyer-facing reserve state string.

    Values:
      * ``"none"``     — no reserve set
      * ``"met"``      — reserve set AND (stored flag = True OR current_bid ≥ reserve)
      * ``"not_met"``  — reserve set AND buyer bid is below it

    The stored ``reserve_met`` boolean (set by the bid handler at first
    reserve-crossing bid) takes precedence over the derived comparison
    so the state stays consistent with the authoritative bid path.
    """
    rp = _coerce_price(reserve_price)
    if rp is None:
        return "none"
    if stored_reserve_met is True:
        return "met"
    try:
        cb = float(current_bid) if current_bid is not None else 0.0
    except (TypeError, ValueError):
        cb = 0.0
    return "met" if cb >= rp else "not_met"


def mask_reserve_for_buyer(doc: Any) -> Any:
    """Strip ``reserve_price`` from a vehicle listing / lot dict and
    replace it with buyer-safe indicators.

    Buyer sees ONLY:
      * ``has_reserve``    (bool)  — reserve is configured
      * ``reserve_state``  (str)   — one of ``"none" | "met" | "not_met"``
      * ``reserve_met``    (bool)  — kept for backwards compatibility
                                     (matches ``reserve_state == "met"``)

    Never emits the raw amount. Non-destructive on the input dict
    (returns a shallow copy).  Passes non-dict input through unchanged
    so this can be applied unconditionally.
    """
    if not isinstance(doc, dict):
        return doc
    out = dict(doc)  # shallow copy
    raw_reserve = out.pop("reserve_price", None)
    current_bid = out.get("current_bid") or out.get("current_price") or out.get("starting_price")
    stored_met = out.get("reserve_met")
    state = _derive_reserve_state(raw_reserve, current_bid, stored_met)
    out["has_reserve"] = state != "none"
    out["reserve_state"] = state
    # keep reserve_met consistent
    if state == "none":
        out["reserve_met"] = False
    elif state == "met":
        out["reserve_met"] = True
    else:  # not_met
        # only overwrite if the stored value would leak "met" incorrectly
        if stored_met is None:
            out["reserve_met"] = False
    return out


def mask_reserve_for_buyer_with_lots(doc: Any) -> Any:
    """Same as :func:`mask_reserve_for_buyer` but also recurses into a
    ``lots`` array (vehicle multi-lot events).  Each lot has its own
    reserve; the buyer-facing state is per-lot."""
    if not isinstance(doc, dict):
        return doc
    out = mask_reserve_for_buyer(doc)
    lots = out.get("lots")
    if isinstance(lots, list):
        out["lots"] = [mask_reserve_for_buyer(l) for l in lots]
    return out


__all__ = [
    "resolve_reserve_price",
    "is_reserve_met",
    "mask_reserve_for_buyer",
    "mask_reserve_for_buyer_with_lots",
]
