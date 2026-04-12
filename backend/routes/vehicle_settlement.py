"""
BidVex — Vehicle Settlement Routes
Handles fee calculation, seller-contact gating, and settlement status.
"""

from fastapi import APIRouter, HTTPException, Depends
from deps import get_db, get_current_user, User
from services.vehicle_fee_service import calculate_vehicle_fee
from datetime import datetime, timezone
import logging

logger = logging.getLogger(__name__)

vehicle_settlement_router = APIRouter(tags=["Vehicle Settlement"])


@vehicle_settlement_router.get("/vehicle-settlement/fee-preview/{hammer_price}")
async def preview_vehicle_fee(hammer_price: float):
    """
    Public endpoint: calculate the platform fee breakdown for a given hammer price.
    Used by frontend to show the bilingual fee breakdown on bidding screens.
    """
    if hammer_price <= 0:
        raise HTTPException(status_code=400, detail="Hammer price must be positive")
    fees = calculate_vehicle_fee(hammer_price)
    return {
        "hammer_price": fees["hammer_price"],
        "platform_fee": fees["net_commission"],
        "processing_fee": fees["stripe_processing_fee"],
        "total_charge_to_buyer": fees["total_charge"],
        "fee_rate_percent": fees["fee_rate"] * 100,
        "currency": "CAD",
        "breakdown_en": f"Platform Fee: ${fees['net_commission']:.2f} + Processing: ${fees['stripe_processing_fee']:.2f}",
        "breakdown_fr": f"Frais de plateforme : {fees['net_commission']:.2f} $ + Traitement : {fees['stripe_processing_fee']:.2f} $",
    }


@vehicle_settlement_router.get("/auctions/{auction_id}/seller-contact")
async def get_seller_contact(auction_id: str, current_user: User = Depends(get_current_user)):
    """
    Gated endpoint: returns seller contact info ONLY after platform fee is paid.
    Returns 402 Payment Required if contact_revealed is false.
    """
    db = get_db()

    # Check settlement record
    settlement = await db.vehicle_settlements.find_one(
        {"auction_id": auction_id, "buyer_id": current_user.id},
        {"_id": 0}
    )

    if not settlement:
        raise HTTPException(
            status_code=402,
            detail={
                "message_en": "Platform fee payment required to view seller contact information.",
                "message_fr": "Le paiement des frais de plateforme est requis pour voir les coordonnées du vendeur.",
                "settlement_status": "PENDING_CLOSE",
            }
        )

    if not settlement.get("contact_revealed", False):
        raise HTTPException(
            status_code=402,
            detail={
                "message_en": "Platform fee payment is being processed. Seller contact will be revealed once payment succeeds.",
                "message_fr": "Le paiement des frais de plateforme est en cours de traitement. Les coordonnées du vendeur seront révélées une fois le paiement réussi.",
                "settlement_status": settlement.get("settlement_status", "FEE_PROCESSING"),
            }
        )

    # Fee paid — reveal seller contact
    listing = await db.vehicle_listings.find_one({"id": auction_id}, {"_id": 0})
    if not listing:
        listing = await db.listings.find_one({"id": auction_id}, {"_id": 0})

    seller_id = (listing or {}).get("seller_user_id") or (listing or {}).get("seller_id")
    if not seller_id:
        raise HTTPException(status_code=404, detail="Seller not found for this auction")

    seller = await db.users.find_one(
        {"id": seller_id},
        {"_id": 0, "name": 1, "email": 1, "phone": 1, "company_name": 1, "address": 1}
    )
    if not seller:
        raise HTTPException(status_code=404, detail="Seller account not found")

    return {
        "contact_revealed": True,
        "settlement_status": "FEE_PAID",
        "seller": {
            "name": seller.get("company_name") or seller.get("name", ""),
            "email": seller.get("email", ""),
            "phone": seller.get("phone", ""),
            "address": seller.get("address", ""),
        },
        "auction_id": auction_id,
        "hammer_price": settlement.get("hammer_price"),
        "fee_paid": settlement.get("net_commission_amount"),
    }


@vehicle_settlement_router.get("/vehicle-settlement/{auction_id}/status")
async def get_settlement_status(auction_id: str, current_user: User = Depends(get_current_user)):
    """Check settlement status for an auction the user won."""
    db = get_db()
    settlement = await db.vehicle_settlements.find_one(
        {"auction_id": auction_id, "buyer_id": current_user.id},
        {"_id": 0, "settlement_status": 1, "contact_revealed": 1, "hammer_price": 1,
         "net_commission_amount": 1, "total_processed_amount": 1, "fee_paid_at": 1}
    )
    if not settlement:
        return {"settlement_status": "PENDING_CLOSE", "contact_revealed": False}
    return settlement



@vehicle_settlement_router.post("/vehicle-settlement/verify-card")
async def verify_card_for_bidding(current_user: User = Depends(get_current_user)):
    """
    Pre-bid safety gate: Create a Stripe SetupIntent to verify the buyer's card
    supports 3D Secure before allowing bids on vehicle auctions.
    Returns the client_secret for the frontend to confirm.
    """
    import os
    import stripe
    stripe.api_key = os.environ.get("STRIPE_API_KEY", "")
    db = get_db()

    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0, "stripe_customer_id": 1})
    if not user_doc or not user_doc.get("stripe_customer_id"):
        raise HTTPException(status_code=400, detail="No payment method on file. Please add a card first.")

    # Check if already verified recently
    existing = await db.card_verifications.find_one({
        "user_id": current_user.id,
        "status": "succeeded",
    })
    if existing:
        return {"verified": True, "message": "Card already verified."}

    try:
        si = stripe.SetupIntent.create(
            customer=user_doc["stripe_customer_id"],
            usage="off_session",
            metadata={
                "user_id": current_user.id,
                "purpose": "vehicle_bid_verification",
            },
        )

        await db.card_verifications.insert_one({
            "user_id": current_user.id,
            "setup_intent_id": si.id,
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        return {
            "verified": False,
            "client_secret": si.client_secret,
            "setup_intent_id": si.id,
            "message_en": "To ensure auction integrity, please verify your card. This is a temporary authorization only.",
            "message_fr": "Pour garantir l'intégrité de l'enchère, veuillez vérifier votre carte. Il s'agit d'une autorisation temporaire uniquement.",
        }
    except Exception as e:
        logger.error(f"SetupIntent creation failed: {e}")
        raise HTTPException(status_code=500, detail="Card verification failed. Please try again.")


@vehicle_settlement_router.post("/vehicle-settlement/confirm-card-verification")
async def confirm_card_verification(current_user: User = Depends(get_current_user)):
    """Mark card as verified after frontend confirms the SetupIntent."""
    db = get_db()
    await db.card_verifications.update_one(
        {"user_id": current_user.id, "status": "pending"},
        {"$set": {"status": "succeeded", "verified_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"verified": True, "message": "Card verified successfully."}
