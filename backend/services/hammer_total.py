"""
iter451 — Merchandise-Total Resolver
====================================

Single source of truth for computing the merchandise (hammer) total at
auction-end for a listing OR a lot inside a multi-item event.

Rule (per user directive):
  • If the winning row uses per-unit pricing AND `multiply_hammer_by_quantity`
    is set AND `quantity_won` / `quantity` > 1, hammer_total = unit_price × quantity.
    Example: unit=$7, qty=2 → hammer_total=$14.
  • If `price_multiplied_by_quantity=True` on the row, the stored price is
    ALREADY the total and MUST NOT be re-multiplied (Buy Now / Storage /
    total-lot pricing modes).
  • Quantity of 1 → hammer_total = unit_price.
  • Multiply flag False → hammer_total = unit_price (total-lot pricing).
  • Never falls back to top-level listing defaults when a lot dict
    carries the price + quantity fields.

`quantity_won` is preferred over `quantity` so partial-quantity wins
report the buyer-owed total correctly.

Returns a plain dict so callers can pattern-match:
  {
    "unit_price": float,       # per-unit price used
    "quantity":   int,         # winning quantity (≥ 1)
    "hammer_total": float,     # unit_price × quantity when multiplied
    "is_multiplied": bool,     # True when the multiplier fired
    "multiply_flag": bool,     # the source flag value
    "already_multiplied": bool # True when the stored price was pre-multiplied
  }

DO NOT modify historical records — this helper is prospective only,
consumed by NEW auction-end / settlement / invoice flows.
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def _num(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ""):
            return float(default)
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _int(value: Any, default: int = 1) -> int:
    try:
        if value in (None, ""):
            return int(default)
        return int(float(value))
    except (TypeError, ValueError):
        return int(default)


def resolve_hammer_total(
    listing: Optional[Dict[str, Any]] = None,
    *,
    lot: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Resolve the merchandise total for one auction-end row.

    Parameters
    ----------
    listing : dict, optional
        The parent listing document. Used as fallback for the multiply
        flag when a lot doesn't carry its own copy.
    lot : dict, optional
        A lot dict inside `listing.lots[]`. When present, the lot's
        `current_price` / `final_price` / `quantity` / `quantity_won`
        take precedence over the listing's top-level fields.

    Notes
    -----
    Preserves existing behaviour for:
      • total-lot pricing (multiply flag False) — no multiplication
      • quantity of 1 — no multiplication
      • Buy Now — Buy Now uses `buy_now_price` on a different flow; the
        checkout path never calls this helper. Safe.
      • pre-multiplied prices (`price_multiplied_by_quantity=True`) —
        the stored price is returned as-is.
    """
    row = lot if lot is not None else (listing or {})
    parent = listing or {}

    # Unit / per-item price stored on the row. Fallback chain matches the
    # existing settle_auction resolver so nothing else breaks.
    unit_price = _num(
        row.get("final_price")
        or row.get("current_price")
        or row.get("current_bid")
        or row.get("winning_bid")
        or row.get("starting_price"),
        0.0,
    )

    # Winning quantity — quantity_won wins over quantity. Clamp to ≥ 1
    # so zero/null never silently zero-outs the transaction.
    quantity_raw = row.get("quantity_won") or row.get("quantity") or 1
    quantity = max(1, _int(quantity_raw, 1))

    # Multiply flag: lot overrides listing.
    multiply_flag = bool(
        row.get("multiply_hammer_by_quantity")
        if "multiply_hammer_by_quantity" in row
        else parent.get("multiply_hammer_by_quantity")
    )
    # If the stored price was ALREADY multiplied by the seller, do NOT
    # re-multiply — the price on the row is the total.
    already_multiplied = bool(
        row.get("price_multiplied_by_quantity")
        if "price_multiplied_by_quantity" in row
        else parent.get("price_multiplied_by_quantity")
    )

    if already_multiplied:
        # Stored price IS the total. Recover per-unit for display.
        return {
            "unit_price": round(unit_price / quantity, 2) if quantity else unit_price,
            "quantity": quantity,
            "hammer_total": round(unit_price, 2),
            "is_multiplied": False,
            "multiply_flag": multiply_flag,
            "already_multiplied": True,
        }

    if multiply_flag and quantity > 1:
        return {
            "unit_price": round(unit_price, 2),
            "quantity": quantity,
            "hammer_total": round(unit_price * quantity, 2),
            "is_multiplied": True,
            "multiply_flag": True,
            "already_multiplied": False,
        }

    # Fall-through: total-lot pricing OR quantity=1.
    return {
        "unit_price": round(unit_price, 2),
        "quantity": quantity,
        "hammer_total": round(unit_price, 2),
        "is_multiplied": False,
        "multiply_flag": multiply_flag,
        "already_multiplied": False,
    }


__all__ = ["resolve_hammer_total"]
