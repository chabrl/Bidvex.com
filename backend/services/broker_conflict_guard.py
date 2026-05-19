"""
iter217 Phase 5 Hotfix v5b — Broker conflict guard.

Detects when two buyers under the SAME broker try to bid against each
other on the SAME vehicle. The platform must legally block the second
bid: a broker cannot bid against itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ConflictResult:
    conflict: bool
    message_en: Optional[str] = None
    message_fr: Optional[str] = None
    blocking_buyer_id: Optional[str] = None


async def check_intra_broker_conflict(
    db,
    *,
    vehicle_listing_id: str,
    broker_id:          str,
    new_buyer_id:       str,
) -> ConflictResult:
    """Returns conflict=True if another buyer under the SAME broker is
    currently the highest bidder on this listing.

    The check is intentionally cheap — a single index lookup for the
    most recent broker_bid for this vehicle, filtered to `status` in
    ('placed', 'winning'). We deliberately do NOT walk the regular
    vehicle_listings.bids array because brokers-bound buyers always
    bid through the broker flow, and that flow always writes to
    broker_bids first.
    """
    # The most recent non-outbid, non-cancelled bid wins.
    winning = await db.broker_bids.find_one(
        {
            "vehicle_listing_id": vehicle_listing_id,
            "status": {"$in": ["placed", "winning"]},
        },
        {"_id": 0, "broker_id": 1, "buyer_user_id": 1, "bid_amount_cad": 1},
        sort=[("placed_at", -1)],
    )

    if not winning:
        return ConflictResult(conflict=False)

    if winning["broker_id"] == broker_id and winning["buyer_user_id"] != new_buyer_id:
        return ConflictResult(
            conflict=True,
            blocking_buyer_id=winning["buyer_user_id"],
            message_en=(
                "Your broker's client is currently the highest bidder on this "
                "vehicle. You cannot bid against another buyer from the same "
                "brokerage."
            ),
            message_fr=(
                "Le client de votre courtier est actuellement le plus offrant "
                "sur ce véhicule. Vous ne pouvez pas surenchérir sur un autre "
                "acheteur du même courtier."
            ),
        )

    return ConflictResult(conflict=False)
