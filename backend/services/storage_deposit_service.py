"""
BidVex Storage Auction — Participation Deposit Service (iter170)
=================================================================
Optional, facility-configured deposit held via Stripe PaymentIntent
with `capture_method="manual"` (true authorization HOLD — funds aren't
captured until auction close).

Lifecycle:
  • create_deposit_hold(auction_id, buyer, amount) → PI confirmed in
    capture_method=manual mode. Doc inserted into storage_deposits.
  • release_deposits_on_close(auction_id, winner_id):
      Winner → status='applied', PI canceled (deposit conceptually
        deducted from final balance — winner brings less cash to facility
        OR final Stripe charge subtracts deposit).
      Losers → status='refunded', PI canceled (auth released, no funds moved).
  • forfeit_deposit(auction_id, buyer_id, reason): winner failed to pay →
    PI captured (funds collected as penalty).

Stripe import is local (lazy) so unit-tests of pure pricing math don't
need a Stripe key in the env.
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException

logger = logging.getLogger(__name__)

DEPOSIT_COLLECTION = "storage_deposits"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _stripe():
    import stripe
    api_key = os.environ.get("STRIPE_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="Stripe not configured")
    stripe.api_key = api_key
    return stripe


async def get_existing_deposit(db, auction_id: str, buyer_id: str) -> Optional[dict]:
    return await db[DEPOSIT_COLLECTION].find_one(
        {"auction_id": auction_id, "buyer_id": buyer_id, "status": "held"},
        {"_id": 0},
    )


async def create_deposit_hold(
    db,
    auction_id: str,
    buyer_id: str,
    buyer_email: str,
    amount: float,
    payment_method_id: str,
) -> dict:
    """
    Authorize (HOLD) the deposit on the buyer's card. Funds are NOT
    captured. Returns the persisted deposit document.

    Idempotency: if a 'held' deposit already exists for this (auction, buyer),
    return it without creating a duplicate Stripe PI.
    """
    existing = await get_existing_deposit(db, auction_id, buyer_id)
    if existing:
        return existing

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Deposit amount must be positive.")

    stripe = _stripe()

    # Reuse-or-create Stripe Customer
    user = await db.users.find_one({"id": buyer_id}, {"_id": 0, "stripe_customer_id": 1, "email": 1})
    customer_id = (user or {}).get("stripe_customer_id")
    if not customer_id:
        cust = stripe.Customer.create(email=buyer_email, metadata={"buyer_id": buyer_id})
        customer_id = cust.id
        await db.users.update_one({"id": buyer_id}, {"$set": {"stripe_customer_id": customer_id}})

    # Attach PM to customer if needed
    try:
        stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)
    except Exception as e:
        # Already attached or other recoverable error
        logger.info(f"[STORAGE_DEPOSIT] PM.attach noop: {e}")

    try:
        pi = stripe.PaymentIntent.create(
            amount=int(round(float(amount) * 100)),
            currency="cad",
            customer=customer_id,
            payment_method=payment_method_id,
            confirm=True,
            capture_method="manual",
            off_session=False,
            automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
            metadata={
                "type": "storage_auction_deposit",
                "auction_id": auction_id,
                "buyer_id": buyer_id,
            },
            description=f"BidVex storage auction deposit — auction {auction_id}",
        )
    except Exception as e:
        logger.error(f"[STORAGE_DEPOSIT] PI.create failed: {e}")
        raise HTTPException(status_code=402, detail=f"Stripe authorization failed: {e}")

    if pi.status not in ("requires_capture", "succeeded"):
        raise HTTPException(
            status_code=402,
            detail={
                "error": "deposit_authorization_failed",
                "stripe_status": pi.status,
                "message_en": "Deposit authorization failed. Please try a different card.",
                "message_fr": "L'autorisation du dépôt a échoué. Veuillez essayer une autre carte.",
            },
        )

    doc = {
        "auction_id": auction_id,
        "buyer_id": buyer_id,
        "buyer_email": buyer_email,
        "amount": float(amount),
        "stripe_payment_intent_id": pi.id,
        "stripe_customer_id": customer_id,
        "status": "held",  # held | applied | refunded | forfeited
        "created_at": _now().isoformat(),
    }
    await db[DEPOSIT_COLLECTION].insert_one(doc.copy())
    doc.pop("_id", None)
    return doc


async def release_deposits_on_close(db, auction_id: str, winner_buyer_id: Optional[str]) -> dict:
    """
    Called by the auction close cron when an auction status flips to 'ended'/'sold'.
    Cancels Stripe authorizations for ALL held deposits on this auction.
    Marks winner deposit as 'applied' (deducted from final amount), losers as 'refunded'.
    """
    stripe = _stripe()
    rows = await db[DEPOSIT_COLLECTION].find(
        {"auction_id": auction_id, "status": "held"},
        {"_id": 0},
    ).to_list(1000)

    applied = 0
    refunded = 0
    errors = []

    for d in rows:
        pi_id = d["stripe_payment_intent_id"]
        is_winner = winner_buyer_id and d["buyer_id"] == winner_buyer_id
        try:
            stripe.PaymentIntent.cancel(pi_id)
        except Exception as e:
            # PI might already be canceled or in a non-cancellable state
            logger.warning(f"[STORAGE_DEPOSIT] cancel({pi_id}) failed: {e}")
            errors.append({"pi_id": pi_id, "error": str(e)})

        new_status = "applied" if is_winner else "refunded"
        timestamp_field = "applied_at" if is_winner else "refunded_at"
        await db[DEPOSIT_COLLECTION].update_one(
            {"auction_id": auction_id, "buyer_id": d["buyer_id"]},
            {"$set": {"status": new_status, timestamp_field: _now().isoformat()}},
        )
        if is_winner:
            applied += 1
        else:
            refunded += 1

    return {
        "auction_id": auction_id,
        "deposits_applied": applied,
        "deposits_refunded": refunded,
        "errors": errors,
    }


async def forfeit_deposit(db, auction_id: str, buyer_id: str, reason: str) -> dict:
    """
    Winner failed to pay within deadline → CAPTURE the held authorization.
    Funds are collected as a penalty.
    """
    deposit = await db[DEPOSIT_COLLECTION].find_one(
        {"auction_id": auction_id, "buyer_id": buyer_id, "status": "held"},
        {"_id": 0},
    )
    if not deposit:
        raise HTTPException(status_code=404, detail="No held deposit found for this auction/buyer.")

    stripe = _stripe()
    try:
        stripe.PaymentIntent.capture(deposit["stripe_payment_intent_id"])
    except Exception as e:
        logger.error(f"[STORAGE_DEPOSIT] capture failed: {e}")
        raise HTTPException(status_code=502, detail=f"Stripe capture failed: {e}")

    await db[DEPOSIT_COLLECTION].update_one(
        {"auction_id": auction_id, "buyer_id": buyer_id, "status": "held"},
        {
            "$set": {
                "status": "forfeited",
                "forfeited_at": _now().isoformat(),
                "forfeit_reason": reason or "Payment deadline missed",
            }
        },
    )
    return {"status": "forfeited", "amount": deposit["amount"]}
