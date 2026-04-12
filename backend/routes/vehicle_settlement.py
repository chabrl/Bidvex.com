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
