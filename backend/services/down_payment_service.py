"""
BidVex — Post-Auction Down Payment Service
============================================
After an auction ends, the winning bidder must pay a down payment within
24 h or forfeit their bidding deposit. The auction is then offered to the
runner-up.

Configuration:
    STORAGE: flat $50 CAD per win
    VEHICLE: 10% of winning bid CAD

State machine on `down_payments` collection:
    pending  → buyer hasn't paid yet (created at auction end)
    paid     → Stripe payment_intent succeeded
    expired  → 24 h passed without payment, deposit forfeited
    cancelled→ admin manually cancelled

Public API surface (all live in routes/down_payments.py):
    GET  /api/down-payments/{auction_id}        — buyer/seller status
    POST /api/down-payments/{auction_id}/pay    — start Stripe checkout
    GET  /api/down-payments/me                  — buyer's open down payments
"""
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import logging
import os
import uuid
from typing import Optional, Dict, Any

import stripe

logger = logging.getLogger(__name__)

stripe.api_key = os.environ.get("STRIPE_API_KEY")

DOWN_PAYMENT_DEADLINE_HOURS = 24

STORAGE_FLAT_DOWN_PAYMENT_CAD = Decimal("50.00")
VEHICLE_DOWN_PAYMENT_PCT = Decimal("0.10")  # 10 %


def _calculate_down_payment(auction_type: str, winning_bid: float) -> float:
    """Return the post-auction down payment due in CAD dollars (always a float)."""
    if auction_type == "storage":
        return float(STORAGE_FLAT_DOWN_PAYMENT_CAD)
    if auction_type == "vehicle":
        return float((Decimal(str(winning_bid)) * VEHICLE_DOWN_PAYMENT_PCT).quantize(Decimal("0.01")))
    raise ValueError(f"Down payments not supported for auction_type={auction_type}")


async def create_down_payment(
    db,
    *,
    auction_id: str,
    auction_type: str,           # "storage" | "vehicle"
    buyer_id: str,
    seller_id: Optional[str],
    winning_bid: float,
    listing_title: str = "",
) -> Dict[str, Any]:
    """Idempotent — returns the existing down-payment record if one exists."""
    existing = await db.down_payments.find_one(
        {"auction_id": auction_id, "buyer_id": buyer_id, "status": {"$in": ["pending", "paid"]}},
        {"_id": 0},
    )
    if existing:
        return existing

    amount = _calculate_down_payment(auction_type, winning_bid)
    now = datetime.now(timezone.utc)
    deadline = now + timedelta(hours=DOWN_PAYMENT_DEADLINE_HOURS)

    record = {
        "id": str(uuid.uuid4()),
        "auction_id": auction_id,
        "auction_type": auction_type,
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "winning_bid": float(winning_bid),
        "amount": float(amount),
        "currency": "CAD",
        "status": "pending",
        "listing_title": listing_title,
        "deadline_at": deadline.isoformat(),
        "created_at": now.isoformat(),
        "stripe_session_id": None,
        "stripe_payment_intent_id": None,
        "paid_at": None,
        "expired_at": None,
    }
    await db.down_payments.insert_one(record)
    record.pop("_id", None)
    logger.info(
        f"[down-payment] created {record['id']} for auction={auction_id} "
        f"type={auction_type} amount=${amount} deadline={deadline.isoformat()}"
    )
    return record


async def create_stripe_checkout_for_down_payment(
    db, *, down_payment_id: str, return_url: str
) -> Dict[str, Any]:
    """Build a Stripe Checkout session that will mark the down payment paid
    when its `payment_intent.succeeded` webhook arrives.
    """
    dp = await db.down_payments.find_one({"id": down_payment_id}, {"_id": 0})
    if not dp:
        raise ValueError("Down payment not found")
    if dp["status"] != "pending":
        raise ValueError(f"Down payment already {dp['status']}")

    amount_cents = int(round(dp["amount"] * 100))
    title_short = (dp.get("listing_title") or "Auction win")[:80]

    session = stripe.checkout.Session.create(
        mode="payment",
        payment_method_types=["card"],
        line_items=[{
            "price_data": {
                "currency": "cad",
                "product_data": {
                    "name": f"BidVex Down Payment — {title_short}",
                    "description": (
                        "Storage auction down payment ($50 flat)" if dp["auction_type"] == "storage"
                        else "Vehicle auction down payment (10% of winning bid)"
                    ),
                },
                "unit_amount": amount_cents,
            },
            "quantity": 1,
        }],
        success_url=f"{return_url}?dp_status=success&dp_id={down_payment_id}",
        cancel_url=f"{return_url}?dp_status=cancelled&dp_id={down_payment_id}",
        metadata={
            "transaction_type": "down_payment",
            "down_payment_id": down_payment_id,
            "auction_id": dp["auction_id"],
            "auction_type": dp["auction_type"],
            "buyer_id": dp["buyer_id"],
            "seller_id": dp.get("seller_id") or "",
            "winning_bid": str(dp["winning_bid"]),
        },
    )

    await db.down_payments.update_one(
        {"id": down_payment_id},
        {"$set": {"stripe_session_id": session.id}},
    )
    return {"checkout_url": session.url, "session_id": session.id}


async def mark_down_payment_paid(db, *, session_id: str, payment_intent_id: Optional[str] = None):
    """Webhook handler — flip the down_payment to `paid` and update the auction."""
    dp = await db.down_payments.find_one({"stripe_session_id": session_id}, {"_id": 0})
    if not dp:
        logger.warning(f"[down-payment] session {session_id} not found")
        return None
    if dp["status"] == "paid":
        return dp
    now = datetime.now(timezone.utc)
    await db.down_payments.update_one(
        {"id": dp["id"]},
        {"$set": {
            "status": "paid",
            "paid_at": now.isoformat(),
            "stripe_payment_intent_id": payment_intent_id,
        }},
    )
    # Unlock the auction → "down_payment_received" → seller releases item
    auction_coll = (
        db.storage_auctions if dp["auction_type"] == "storage" else db.vehicle_listings
    )
    await auction_coll.update_one(
        {"id": dp["auction_id"]},
        {"$set": {
            "down_payment_status": "paid",
            "down_payment_paid_at": now.isoformat(),
        }},
    )
    logger.info(f"[down-payment] {dp['id']} marked paid for auction {dp['auction_id']}")
    return dp


async def expire_overdue_and_promote_runner_up(db) -> Dict[str, int]:
    """Cron — runs hourly. For every pending down_payment past its deadline:
        1. Mark down_payment status=expired.
        2. Forfeit any bidding deposit on file for that buyer.
        3. Find the next-highest bidder; if they exist, transfer the win
           and create a fresh 24 h down payment for them.
    """
    now = datetime.now(timezone.utc)
    cursor = db.down_payments.find(
        {"status": "pending", "deadline_at": {"$lt": now.isoformat()}},
        {"_id": 0},
    )
    overdue = await cursor.to_list(500)
    expired_count = 0
    promoted_count = 0

    for dp in overdue:
        try:
            await db.down_payments.update_one(
                {"id": dp["id"]},
                {"$set": {"status": "expired", "expired_at": now.isoformat()}},
            )
            expired_count += 1

            # ─── Forfeit bidding deposit (if any) ───
            await db.bidding_deposits.update_many(
                {"auction_id": dp["auction_id"], "user_id": dp["buyer_id"], "status": {"$in": ["held", "authorized"]}},
                {"$set": {"status": "forfeited", "forfeited_at": now.isoformat(),
                          "forfeit_reason": "down_payment_expired_24h"}},
            )

            # ─── Promote runner-up ───
            promoted = await _promote_runner_up(db, dp)
            if promoted:
                promoted_count += 1
        except Exception as e:
            logger.error(f"[down-payment] expire failed for {dp.get('id')}: {e}")

    if expired_count or promoted_count:
        logger.info(f"[down-payment] cron: expired={expired_count} promoted_runner_up={promoted_count}")
    return {"expired": expired_count, "promoted_runner_up": promoted_count}


async def _promote_runner_up(db, expired_dp) -> bool:
    """Find the runner-up on the auction and create a new pending
    down_payment for them. Updates the auction row's winner pointer.
    """
    auction_id = expired_dp["auction_id"]
    auction_type = expired_dp["auction_type"]
    excluded_user_id = expired_dp["buyer_id"]

    if auction_type == "storage":
        coll = db.storage_auctions
    else:
        coll = db.vehicle_listings

    auction = await coll.find_one({"id": auction_id}, {"_id": 0})
    if not auction:
        return False

    # Bid list lives inline on the auction document; strip the original winner
    # then pick the next-highest by amount.
    bids = sorted(
        [b for b in (auction.get("bids") or []) if b.get("bidder_id") != excluded_user_id],
        key=lambda b: float(b.get("amount", 0)),
        reverse=True,
    )
    if not bids:
        # No runner-up — auction is just dead
        await coll.update_one(
            {"id": auction_id},
            {"$set": {"status": "no_winner", "down_payment_status": "expired"}},
        )
        return False

    winner_bid = bids[0]
    new_buyer = await db.users.find_one({"id": winner_bid["bidder_id"]}, {"_id": 0, "id": 1, "email": 1, "name": 1})
    if not new_buyer:
        return False

    await coll.update_one(
        {"id": auction_id},
        {"$set": {
            "highest_bidder_id": new_buyer["id"],
            "winner_id": new_buyer["id"],
            "current_bid": float(winner_bid["amount"]),
            "current_price": float(winner_bid["amount"]),
            "status": "ended",
            "promoted_from_expired_dp": expired_dp["id"],
        }},
    )

    new_dp = await create_down_payment(
        db,
        auction_id=auction_id,
        auction_type=auction_type,
        buyer_id=new_buyer["id"],
        seller_id=auction.get("facility_owner_id") or auction.get("seller_id"),
        winning_bid=float(winner_bid["amount"]),
        listing_title=auction.get("title") or auction.get("unit_number") or "Your auction win",
    )

    # Email the new winner
    try:
        from services.emails.email_marketplace import send_auction_won_email
        await send_auction_won_email(
            to_email=new_buyer["email"],
            to_name=new_buyer.get("name", "Winner"),
            item_name=new_dp["listing_title"],
            auction_id=auction_id,
            hammer_price=float(winner_bid["amount"]),
            platform_fee=float(new_dp["amount"]),
            is_vehicle=(auction_type == "vehicle"),
        )
    except Exception as e:
        logger.warning(f"[down-payment] runner-up email failed: {e}")

    logger.info(
        f"[down-payment] promoted runner-up {new_buyer['id']} on auction {auction_id} "
        f"(new dp={new_dp['id']})"
    )
    return True
