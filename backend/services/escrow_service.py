"""
BidVex — Escrow + Pickup Code Service
Non-vehicle items only. Holds funds until pickup code confirmation.
"""
import secrets
import stripe
import os
import logging
from datetime import datetime, timezone, timedelta
from fastapi import HTTPException

logger = logging.getLogger(__name__)

stripe.api_key = os.environ.get("STRIPE_API_KEY")

# Safe alphabet: excludes 0, O, I, 1, L to avoid confusion
PICKUP_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"


async def generate_pickup_code(db) -> str:
    """Generates a collision-safe 6-character alphanumeric code."""
    for _ in range(100):
        code = "".join(secrets.choice(PICKUP_ALPHABET) for _ in range(6))
        existing = await db.escrow_transactions.find_one({"pickup_code": code, "escrow_status": "held"})
        if not existing:
            return code
    raise RuntimeError("Failed to generate unique pickup code after 100 attempts")


async def create_escrow_hold(
    db,
    auction_id: str,
    listing_id: str,
    buyer_id: str,
    seller_id: str,
    hammer_price_cents: int,
    total_charged_cents: int,
    application_fee_cents: int,
    stripe_payment_intent_id: str,
    province: str,
) -> dict:
    """
    Called after payment_intent.succeeded for non-vehicle items.
    Funds held on BidVex platform — NO transfer to seller yet.
    """
    pickup_code = await generate_pickup_code(db)
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=48)

    escrow = {
        "auction_id": auction_id,
        "listing_id": listing_id,
        "buyer_id": buyer_id,
        "seller_id": seller_id,
        "hammer_price_cents": hammer_price_cents,
        "total_charged_cents": total_charged_cents,
        "application_fee_cents": application_fee_cents,
        "stripe_payment_intent_id": stripe_payment_intent_id,
        "stripe_transfer_id": None,
        "escrow_status": "held",
        "pickup_code": pickup_code,
        "pickup_code_expires_at": expires_at.isoformat(),
        "pickup_code_entered_at": None,
        "pickup_confirmed_at": None,
        "funds_released_at": None,
        "auto_release_scheduled_at": expires_at.isoformat(),
        "created_at": now.isoformat(),
        "updated_at": now.isoformat(),
        "item_type": "non_vehicle",
        "province": province,
    }

    await db.escrow_transactions.insert_one(escrow)
    escrow.pop("_id", None)

    # Send pickup code email to buyer
    try:
        buyer = await db.users.find_one({"id": buyer_id}, {"_id": 0, "email": 1, "name": 1, "preferred_language": 1, "language_preference": 1})
        seller_doc = await db.users.find_one({"id": seller_id}, {"_id": 0, "name": 1})
        if buyer and buyer.get("email"):
            from services.email_service import send_pickup_code_email
            await send_pickup_code_email(
                buyer=buyer,
                seller=seller_doc or {"name": "Seller"},
                pickup_code=pickup_code,
                auction_id=auction_id,
                expires_at=expires_at.strftime("%B %d, %Y at %I:%M %p UTC"),
            )
            logger.info(f"[ESCROW] Pickup code email sent to {buyer['email']}")
    except Exception as e:
        logger.error(f"[ESCROW] Failed to send pickup code email: {e}")

    logger.info(f"[ESCROW] Created hold for auction {auction_id}, code={pickup_code}, expires={expires_at}")
    return escrow


async def confirm_pickup(db, seller_id: str, auction_id: str, code: str) -> dict:
    """
    Seller enters the pickup code. Validates and releases funds.
    """
    code = code.upper().strip()

    escrow = await db.escrow_transactions.find_one(
        {"auction_id": auction_id, "escrow_status": "held"},
        {"_id": 0},
    )
    if not escrow:
        raise HTTPException(status_code=404, detail={
            "error": "escrow_not_found",
            "message_en": "No active escrow found for this auction.",
            "message_fr": "Aucun dépôt actif trouvé pour cette enchère.",
        })

    if escrow["seller_id"] != seller_id:
        raise HTTPException(status_code=403, detail={
            "error": "not_your_listing",
            "message_en": "You are not the seller for this auction.",
            "message_fr": "Vous n'êtes pas le vendeur de cette enchère.",
        })

    if escrow["pickup_code"] != code:
        await _log_failed_attempt(db, escrow["auction_id"], seller_id, code)
        raise HTTPException(status_code=400, detail={
            "error": "invalid_code",
            "message_en": "Invalid pickup code. Please ask the buyer to check their email.",
            "message_fr": "Code de retrait invalide. Veuillez demander à l'acheteur de vérifier son courriel.",
        })

    expires_at = escrow.get("pickup_code_expires_at", "")
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    if datetime.now(timezone.utc) > expires_at:
        raise HTTPException(status_code=410, detail={
            "error": "code_expired",
            "message_en": "This pickup code has expired. Funds have been auto-released.",
            "message_fr": "Ce code de retrait a expiré. Les fonds ont été libérés automatiquement.",
        })

    # Execute Stripe transfer to seller
    seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "stripe_connect_account_id": 1})
    connect_id = (seller or {}).get("stripe_connect_account_id")
    seller_payout_cents = escrow["total_charged_cents"] - escrow["application_fee_cents"]

    transfer_id = None
    if connect_id and seller_payout_cents > 0:
        try:
            transfer = stripe.Transfer.create(
                amount=seller_payout_cents,
                currency="cad",
                destination=connect_id,
                metadata={
                    "type": "escrow_release",
                    "auction_id": auction_id,
                    "pickup_code": code,
                    "released_by": "seller_code_entry",
                },
            )
            transfer_id = transfer.id
        except Exception as e:
            logger.error(f"[ESCROW] Transfer failed for {auction_id}: {e}")
            raise HTTPException(status_code=500, detail="Transfer failed. Please contact support.")

    now = datetime.now(timezone.utc).isoformat()
    await db.escrow_transactions.update_one(
        {"auction_id": auction_id, "escrow_status": "held"},
        {"$set": {
            "escrow_status": "released",
            "stripe_transfer_id": transfer_id,
            "pickup_code_entered_at": now,
            "pickup_confirmed_at": now,
            "funds_released_at": now,
            "updated_at": now,
        }},
    )

    logger.info(f"[ESCROW] Released funds for {auction_id}, transfer={transfer_id}")
    return {
        "status": "released",
        "transfer_id": transfer_id,
        "amount_released": f"${seller_payout_cents / 100:.2f} CAD",
        "message_en": "Pickup confirmed. Funds have been released to your account.",
        "message_fr": "Retrait confirmé. Les fonds ont été libérés sur votre compte.",
    }


async def _log_failed_attempt(db, auction_id: str, seller_id: str, attempted_code: str):
    """Log failed pickup code attempt and escalate after 5 failures."""
    await db.pickup_attempt_log.insert_one({
        "auction_id": auction_id,
        "seller_id": seller_id,
        "attempted_code": attempted_code,
        "attempted_at": datetime.now(timezone.utc).isoformat(),
    })
    failure_count = await db.pickup_attempt_log.count_documents({"auction_id": auction_id})
    if failure_count >= 5:
        await db.admin_flags.insert_one({
            "type": "pickup_code_brute_force",
            "auction_id": auction_id,
            "seller_id": seller_id,
            "failure_count": failure_count,
            "flagged_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.warning(f"[ESCROW] Brute force detected for auction {auction_id} by seller {seller_id}")


async def auto_release_expired_escrows(db):
    """
    Runs every 15 minutes. Finds escrows past 48h with status "held".
    Auto-releases funds to seller without requiring code.
    """
    now = datetime.now(timezone.utc)
    expired = await db.escrow_transactions.find({
        "escrow_status": "held",
        "auto_release_scheduled_at": {"$lte": now.isoformat()},
    }).to_list(100)

    released = 0
    for escrow in expired:
        try:
            seller = await db.users.find_one(
                {"id": escrow["seller_id"]}, {"_id": 0, "stripe_connect_account_id": 1}
            )
            connect_id = (seller or {}).get("stripe_connect_account_id")
            seller_payout_cents = escrow["total_charged_cents"] - escrow["application_fee_cents"]

            transfer_id = None
            if connect_id and seller_payout_cents > 0:
                transfer = stripe.Transfer.create(
                    amount=seller_payout_cents,
                    currency="cad",
                    destination=connect_id,
                    metadata={
                        "type": "escrow_auto_release",
                        "auction_id": escrow["auction_id"],
                        "released_by": "48h_auto_release",
                    },
                )
                transfer_id = transfer.id

            await db.escrow_transactions.update_one(
                {"auction_id": escrow["auction_id"], "escrow_status": "held"},
                {"$set": {
                    "escrow_status": "auto_released",
                    "stripe_transfer_id": transfer_id,
                    "funds_released_at": now.isoformat(),
                    "updated_at": now.isoformat(),
                }},
            )
            released += 1
        except Exception as e:
            logger.error(f"[ESCROW_AUTO] Failed for {escrow.get('auction_id')}: {e}")
            await db.escrow_error_log.insert_one({
                "auction_id": escrow.get("auction_id"),
                "error": str(e),
                "occurred_at": now.isoformat(),
            })

    if released > 0:
        logger.info(f"[ESCROW_AUTO] Auto-released {released} escrows")
    return released


async def get_buyer_escrow_status(db, buyer_id: str) -> list:
    """Get all escrow transactions for a buyer."""
    escrows = await db.escrow_transactions.find(
        {"buyer_id": buyer_id},
        {"_id": 0, "pickup_code": 0},
    ).sort("created_at", -1).to_list(50)
    return escrows


async def get_seller_escrow_status(db, seller_id: str) -> list:
    """Get all escrow transactions for a seller (code hidden until held)."""
    escrows = await db.escrow_transactions.find(
        {"seller_id": seller_id},
        {"_id": 0, "pickup_code": 0},
    ).sort("created_at", -1).to_list(50)
    return escrows


async def initiate_dispute(db, escrow_auction_id: str, user_id: str, reason: str) -> dict:
    """
    Stub: marks an escrow as disputed. Future: full dispute resolution flow.
    """
    escrow = await db.escrow_transactions.find_one(
        {"auction_id": escrow_auction_id, "escrow_status": "held"},
    )
    if not escrow:
        raise HTTPException(status_code=404, detail="No active escrow found")

    if user_id not in [escrow["buyer_id"], escrow["seller_id"]]:
        raise HTTPException(status_code=403, detail="Not a party to this transaction")

    now = datetime.now(timezone.utc).isoformat()
    await db.escrow_transactions.update_one(
        {"auction_id": escrow_auction_id, "escrow_status": "held"},
        {"$set": {"escrow_status": "disputed", "updated_at": now}},
    )
    await db.escrow_disputes.insert_one({
        "auction_id": escrow_auction_id,
        "initiated_by": user_id,
        "reason": reason,
        "status": "open",
        "created_at": now,
    })
    logger.info(f"[ESCROW] Dispute opened for {escrow_auction_id} by {user_id}")
    return {"status": "disputed", "message": "Dispute has been opened. Our team will review."}
