"""
BidVex Storage Auction Service — proxy bidding + soft-close.

Proxy logic (eBay style):
  • Every user submits a MAX bid (their secret ceiling).
  • Visible `current_bid` advances by `bid_increment` only as needed to
    place the leader $1 above the second-highest max (capped by leader's max).
  • If a new bidder's max ≤ current leader's max, leader stays winning
    at min(leader_max, new_max + 1).
  • If a new bidder's max > current leader's max, the new bidder takes
    the lead at min(new_max, leader_max + 1).

Soft close:
  • If a bid lands within the final `soft_close_extension_minutes`,
    the auction's end_time is extended by that many minutes.

CRITICAL CORRECTNESS RULES (iter172):
  • `bid_record.bidder_id` ALWAYS matches the user who submitted (never attributed
    to a different user even when the leader's proxy auto-pushes).
  • `bid_record.amount` ALWAYS equals the submitter's own max_bid (their intent).
    Auto-advances of `current_bid` are a SEPARATE concept stored at the auction
    level — never in a bid_record — to avoid the "system outbid me" illusion.
  • A submitting user who is already the leader cannot push their amount HIGHER
    than they intended. Their max_bid simply replaces their prior ceiling.
  • Idempotency: identical (bidder_id, max_bid) submissions within 2 seconds are
    silently collapsed into a single record — prevents double-click duplicates.
  • NEVER modify current_bid downward (monotonic); guards prevent regressions.
"""
from datetime import datetime, timezone, timedelta
from typing import Dict, Optional
from fastapi import HTTPException

DEDUPE_WINDOW_SECONDS = 2.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_dt(v) -> datetime:
    if isinstance(v, datetime):
        return v if v.tzinfo else v.replace(tzinfo=timezone.utc)
    return datetime.fromisoformat(str(v).replace("Z", "+00:00"))


def _highest_max_bidder(bids: list, exclude_bidder: Optional[str] = None):
    """
    Return the (bidder_id, max_bid) pair with the highest OUTSTANDING max_bid.
    Since we now store ONE record per bidder representing their LATEST ceiling,
    we compute the leader from the most-recent max per bidder.
    """
    if not bids:
        return None, 0.0
    # Most-recent max per bidder
    per_bidder = {}
    for b in bids:
        bid_id = b.get("bidder_id")
        if not bid_id:
            continue
        # Later entries overwrite earlier ones (bids are in chronological order)
        per_bidder[bid_id] = float(b.get("max_bid", 0))

    eligible = {k: v for k, v in per_bidder.items() if k != exclude_bidder} if exclude_bidder else per_bidder
    if not eligible:
        return None, 0.0
    top_bidder = max(eligible, key=lambda k: eligible[k])
    return top_bidder, eligible[top_bidder]


async def place_bid(db, auction_id: str, bidder_id: str, max_bid: float) -> Dict:
    """
    Run a proxy bid and persist atomically. Returns the new state:
      { current_bid, bid_count, end_time, leader_id, soft_close_extended,
        your_max_bid, you_are_winning, outbid_user_id, is_duplicate }
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
    bids = auction.get("bids", [])

    # ── Min-bid rule ──
    # First bid must be ≥ starting_price. Subsequent bids must be ≥ current_bid + increment.
    min_required = (current_bid + increment) if bids else max(starting_price, current_bid)

    if max_bid < min_required:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "bid_too_low",
                "message_en": f"Minimum bid is ${min_required:.2f}",
                "message_fr": f"Offre minimale est de {min_required:.2f} $",
            },
        )

    # ── Idempotency: identical submission within 2s? ──
    # Prevents duplicate bids when the user double-clicks the bid button.
    now_dt = _now()
    for b in reversed(bids):
        if b.get("bidder_id") == bidder_id and float(b.get("max_bid", 0)) == float(max_bid):
            try:
                placed_at = _parse_dt(b.get("placed_at"))
                if (now_dt - placed_at).total_seconds() < DEDUPE_WINDOW_SECONDS:
                    # Silent dedup — return current state
                    leader_id, _ = _highest_max_bidder(bids)
                    return {
                        "current_bid": current_bid,
                        "bid_count": len(bids),
                        "end_time": end_time.isoformat(),
                        "leader_id": leader_id,
                        "soft_close_extended": False,
                        "your_max_bid": float(max_bid),
                        "you_are_winning": leader_id == bidder_id,
                        "outbid_user_id": None,
                        "is_duplicate": True,
                    }
            except Exception:
                pass
        break  # Only check most-recent bid

    # ── Proxy bidding resolution ──
    # leader_id/leader_max = the CURRENT STANDING leader (excluding the submitter,
    # so we can detect whether the submitter is competing against someone else).
    other_leader_id, other_leader_max = _highest_max_bidder(bids, exclude_bidder=bidder_id)
    # self_max: the submitter's own prior ceiling (if any).
    _, self_prior_max = _highest_max_bidder([b for b in bids if b.get("bidder_id") == bidder_id])

    new_current = current_bid
    winning_bidder: str

    if other_leader_id is None:
        # No other competitors — submitter becomes (or remains) the only bidder.
        # First-bid floor: current_bid stays at starting_price. Otherwise unchanged.
        winning_bidder = bidder_id
        if not bids:
            new_current = starting_price
        # else: current_bid stays; the submitter just raised their ceiling.

    elif max_bid > other_leader_max:
        # Submitter's max beats every other bidder. They take the lead.
        new_current = min(float(max_bid), other_leader_max + increment)
        winning_bidder = bidder_id

    else:
        # An OTHER user still holds the highest max. Their proxy holds the lead,
        # advancing current_bid to (submitter_max + increment) capped by their own max.
        # NOTE: This auto-advance is NEVER attributed to the submitter in bid_record.
        new_current = min(other_leader_max, float(max_bid) + increment)
        winning_bidder = other_leader_id

    # Current bid is monotonically non-decreasing.
    new_current = round(max(new_current, current_bid), 2)

    # ── Soft close ──
    soft_extended = False
    soft_minutes = int(auction.get("soft_close_extension_minutes", 10) or 10)
    if auction.get("soft_close_enabled", True):
        time_remaining = (end_time - now_dt).total_seconds()
        if 0 < time_remaining < soft_minutes * 60:
            end_time = end_time + timedelta(minutes=soft_minutes)
            soft_extended = True

    # ── Snapshot outbid info BEFORE persisting the new bid.
    # We compute who was the standing leader over the pre-existing bids. If the
    # submitter just took the lead from a DIFFERENT user, that user was outbid.
    prev_leader_id, _ = _highest_max_bidder(bids)
    outbid_user_id = prev_leader_id if (winning_bidder == bidder_id
                                        and prev_leader_id
                                        and prev_leader_id != bidder_id) else None
    original_bid_count = len(bids)

    # ── Persist the bid_record.
    # bid_record faithfully represents the submitter's OWN ceiling, never an
    # auto-advance that belongs to the leader. This prevents the UX illusion of
    # "the system auto-outbid me" on my own bid submission.
    bid_record = {
        "bidder_id": bidder_id,
        "amount": float(max_bid),       # The submitter's intent — their ceiling.
        "max_bid": float(max_bid),
        "placed_at": now_dt.isoformat(),
        "is_proxy": False,
    }

    await db.storage_auctions.update_one(
        {"id": auction_id},
        {
            "$set": {
                "current_bid": new_current,
                "winning_bidder_id": winning_bidder,
                "end_time": end_time.isoformat(),
                "updated_at": now_dt.isoformat(),
            },
            "$push": {"bids": bid_record},
            "$inc": {"bid_count": 1},
        },
    )

    return {
        "current_bid": new_current,
        "bid_count": original_bid_count + 1,
        "end_time": end_time.isoformat(),
        "leader_id": winning_bidder,
        "soft_close_extended": soft_extended,
        "your_max_bid": float(max_bid),
        "you_are_winning": winning_bidder == bidder_id,
        "outbid_user_id": outbid_user_id,
        "is_duplicate": False,
    }
