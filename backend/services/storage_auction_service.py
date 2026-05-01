"""
BidVex Storage Auction Service — proxy bidding + soft-close.

Proxy logic (matches BID13 / eBay style):
  • Every user submits a MAX bid (their secret ceiling).
  • Visible `current_bid` advances by `bid_increment` only as needed to
    place the leader $1 above the second-highest max.
  • If a new bidder's max ≤ current leader's max, leader stays winning
    at min(leader_max, new_max + 1).
  • If a new bidder's max > current leader's max, the new bidder takes
    the lead at min(new_max, leader_max + 1).

Soft close:
  • If a bid lands within the final `soft_close_extension_minutes`,
    the auction's end_time is extended by that many minutes.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from fastapi import HTTPException


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(v) -> datetime:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _highest_max_bidder(bids: list, exclude_bidder: Optional[str] = None):
    """Return the (bidder_id, max_bid) pair with the highest max_bid."""
    if not bids:
        return None, 0.0
    eligible = [b for b in bids if b.get("bidder_id") != exclude_bidder] if exclude_bidder else bids
    if not eligible:
        return None, 0.0
    leader = max(eligible, key=lambda b: float(b.get("max_bid", 0)))
    return leader.get("bidder_id"), float(leader.get("max_bid", 0))


async def place_bid(db, auction_id: str, bidder_id: str, max_bid: float) -> Dict:
    """
    Run a proxy bid and persist atomically. Returns the new state:
      { current_bid, bid_count, end_time, leader_id, soft_close_extended }
    """
    auction = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")

    if auction.get("status") != "active":
        raise HTTPException(
            status_code=400,
            detail={
                "error": "auction_not_active",
                "message_en": f"Auction is not active (status: {auction.get('status')}).",
                "message_fr": f"L'enchère n'est pas active (statut: {auction.get('status')}).",
            },
        )

    end_time = _parse_dt(auction.get("end_time"))
    if _now() >= end_time:
        raise HTTPException(status_code=400, detail="Auction has ended")

    increment = float(auction.get("bid_increment", 10.0))
    current_bid = float(auction.get("current_bid", auction.get("starting_price", 0)))
    starting_price = float(auction.get("starting_price", 0))

    # Min required: must be at least starting_price (first bid) or current+increment (subsequent).
    bids = auction.get("bids", [])
    min_required = current_bid + increment if bids else max(starting_price, current_bid)

    if max_bid < min_required:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bid_too_low",
                "message_en": f"Minimum bid is ${min_required:.2f}",
                "message_fr": f"Offre minimale est de {min_required:.2f} $",
            },
        )

    # ── Proxy bidding logic ──
    leader_id, leader_max = _highest_max_bidder(bids)
    new_current = current_bid

    if leader_id is None or leader_id == bidder_id:
        # First bid by anyone (or same bidder raising their own ceiling).
        # Visible current_bid stays at starting_price for the very first bid;
        # otherwise stays at current. The bidder's max is recorded silently.
        new_current = starting_price if not bids else current_bid
        winning_bidder = bidder_id
    elif max_bid > leader_max:
        # New bidder beats the standing leader → takes the lead at $1 above leader's max
        # (capped by their own max).
        new_current = min(float(max_bid), leader_max + 1.0)
        winning_bidder = bidder_id
    else:
        # Existing leader holds. Their visible bid advances to $1 above the new max,
        # capped at their own ceiling.
        new_current = min(leader_max, float(max_bid) + 1.0)
        winning_bidder = leader_id

    new_current = round(max(new_current, current_bid), 2)

    # ── Soft close ──
    soft_extended = False
    soft_minutes = int(auction.get("soft_close_extension_minutes", 10) or 10)
    if auction.get("soft_close_enabled", True):
        time_remaining = (end_time - _now()).total_seconds()
        if time_remaining < soft_minutes * 60:
            end_time = end_time + timedelta(minutes=soft_minutes)
            soft_extended = True

    bid_record = {
        "bidder_id": bidder_id,
        "amount": new_current,
        "max_bid": float(max_bid),
        "placed_at": _now().isoformat(),
        "is_proxy": False,
    }

    await db.storage_auctions.update_one(
        {"id": auction_id},
        {
            "$set": {
                "current_bid": new_current,
                "winning_bidder_id": winning_bidder,
                "end_time": end_time.isoformat(),
                "updated_at": _now().isoformat(),
            },
            "$push": {"bids": bid_record},
            "$inc": {"bid_count": 1},
        },
    )

    return {
        "current_bid": new_current,
        "bid_count": len(bids) + 1,
        "end_time": end_time.isoformat(),
        "leader_id": winning_bidder,
        "soft_close_extended": soft_extended,
        "your_max_bid": float(max_bid),
        "you_are_winning": winning_bidder == bidder_id,
        "outbid_user_id": leader_id if (winning_bidder != leader_id and leader_id) else None,
    }
