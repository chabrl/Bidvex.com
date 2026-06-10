"""
BidVex — Vehicle Platform Fee Service
Implements the "Fee-to-Unlock" intermediary model:
  - BidVex charges buyer 2.5% platform fee + Stripe processing recovery
  - Seller contact revealed only AFTER successful payment
  - Vehicle hammer price settled directly between buyer and seller
"""

import os
import logging
import stripe
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)

STRIPE_API_KEY = os.environ.get("STRIPE_API_KEY", "")
PLATFORM_FEE_RATE = 0.025  # 2.5%
STRIPE_PERCENT_FEE = 0.029  # 2.9%
STRIPE_FIXED_FEE = 0.30     # $0.30 CAD


def calculate_vehicle_fee(hammer_price: float) -> dict:
    """
    Calculate the total charge so BidVex receives exactly 2.5% net of Stripe fees.

    Formula:
      net_commission = hammer_price * 0.025
      total_charge   = (net_commission + 0.30) / (1 - 0.029)

    Returns dict with all amounts in CAD, rounded to 2 decimals.
    """
    net_commission = round(hammer_price * PLATFORM_FEE_RATE, 2)
    total_charge = round((net_commission + STRIPE_FIXED_FEE) / (1 - STRIPE_PERCENT_FEE), 2)
    stripe_processing = round(total_charge - net_commission, 2)

    return {
        "hammer_price": hammer_price,
        "net_commission": net_commission,
        "stripe_processing_fee": stripe_processing,
        "total_charge": total_charge,
        "fee_rate": PLATFORM_FEE_RATE,
        "currency": "cad",
    }


async def create_vehicle_fee_charge(
    db,
    auction_id: str,
    buyer_id: str,
    hammer_price: float,
    buyer_stripe_customer_id: Optional[str] = None,
    buyer_default_payment_method: Optional[str] = None,
) -> dict:
    """
    Create a Stripe PaymentIntent to charge the buyer the platform fee.
    Called automatically when the auction closes and a winner is determined.

    Returns: { success, payment_intent_id, total_charge, ... }
    """
    stripe.api_key = STRIPE_API_KEY
    fees = calculate_vehicle_fee(hammer_price)

    if not buyer_stripe_customer_id:
        buyer_doc = await db.users.find_one({"id": buyer_id}, {"_id": 0, "stripe_customer_id": 1, "default_payment_method_id": 1})
        if not buyer_doc or not buyer_doc.get("stripe_customer_id"):
            logger.error(f"[VehicleFee] Buyer {buyer_id} has no Stripe customer ID")
            return {"success": False, "error": "Buyer has no Stripe customer on file"}
        buyer_stripe_customer_id = buyer_doc["stripe_customer_id"]
        buyer_default_payment_method = buyer_doc.get("default_payment_method_id")

    amount_cents = int(round(fees["total_charge"] * 100))

    try:
        pi_params = {
            "amount": amount_cents,
            "currency": "cad",
            "customer": buyer_stripe_customer_id,
            "description": f"BidVex Platform Fee — Auction #{auction_id[:8]}",
            "metadata": {
                "bidvex_role": "platform_intermediary",
                "vehicle_title_holder": "seller",
                "transaction_type": "vehicle_platform_fee",
                "auction_id": auction_id,
                "buyer_id": buyer_id,
                "hammer_price": str(hammer_price),
                "net_commission": str(fees["net_commission"]),
                "stripe_processing_fee": str(fees["stripe_processing_fee"]),
                "vehicle_price_collected_by_bidvex": "false",
                "description_en": f"BidVex Platform Fee — Auction #{auction_id[:8]}",
                "description_fr": f"Frais de plateforme BidVex — Enchère #{auction_id[:8]}",
            },
            "confirm": True,
            "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"},
        }

        if buyer_default_payment_method:
            pi_params["payment_method"] = buyer_default_payment_method

        from services.stripe_circuit_breaker import safe_stripe_call_blocking
        pi = await safe_stripe_call_blocking(
            lambda: stripe.PaymentIntent.create(**pi_params),
            operation_name="vehicle_fee_payment_intent_create",
        )

        # Store settlement record
        now = datetime.now(timezone.utc).isoformat()
        settlement_doc = {
            "auction_id": auction_id,
            "buyer_id": buyer_id,
            "hammer_price": hammer_price,
            "net_commission_amount": fees["net_commission"],
            "stripe_processing_fee": fees["stripe_processing_fee"],
            "total_processed_amount": fees["total_charge"],
            "fee_percentage": PLATFORM_FEE_RATE,
            "stripe_payment_intent_id": pi.id,
            "settlement_status": "FEE_PROCESSING" if pi.status != "succeeded" else "FEE_PAID",
            "contact_revealed": pi.status == "succeeded",
            "vehicle_price_collected_by_bidvex": False,
            "created_at": now,
            "updated_at": now,
        }
        await db.vehicle_settlements.insert_one(settlement_doc)

        logger.info(f"[VehicleFee] Created PI {pi.id} for auction {auction_id} — ${fees['total_charge']} CAD (status={pi.status})")

        return {
            "success": True,
            "payment_intent_id": pi.id,
            "payment_intent_status": pi.status,
            **fees,
        }

    except stripe.StripeError as e:
        logger.error(f"[VehicleFee] Stripe error for auction {auction_id}: {e}")
        now = datetime.now(timezone.utc).isoformat()
        await db.vehicle_settlements.insert_one({
            "auction_id": auction_id,
            "buyer_id": buyer_id,
            "hammer_price": hammer_price,
            "net_commission_amount": fees["net_commission"],
            "total_processed_amount": fees["total_charge"],
            "fee_percentage": PLATFORM_FEE_RATE,
            "settlement_status": "FEE_FAILED",
            "contact_revealed": False,
            "error": str(e),
            "created_at": now,
            "updated_at": now,
        })
        return {"success": False, "error": str(e)}


async def handle_vehicle_fee_succeeded(db, payment_intent_id: str):
    """
    Called by Stripe webhook on payment_intent.succeeded for vehicle_platform_fee.
    Reveals seller contact to buyer.
    """
    settlement = await db.vehicle_settlements.find_one(
        {"stripe_payment_intent_id": payment_intent_id},
        {"_id": 0}
    )
    if not settlement:
        logger.warning(f"[VehicleFee] No settlement found for PI {payment_intent_id}")
        return False

    now = datetime.now(timezone.utc).isoformat()
    # After the fee is paid, we enter the dealer-confirmation phase.
    # settlement_status transitions: FEE_PROCESSING → FEE_PAID → AWAITING_DEALER_CONFIRMATION
    # (once dealer marks settled) → DEALER_CONFIRMED → (optional buyer ack) → FULLY_SETTLED
    # (or → DISPUTED if the buyer escalates → ADMIN_RESOLVED).

    # Capture seller_id on the settlement so the dealer dashboard can query it.
    listing = await db.vehicle_listings.find_one(
        {"id": settlement["auction_id"]}, {"_id": 0, "seller_id": 1, "seller_user_id": 1}
    ) or await db.listings.find_one(
        {"id": settlement["auction_id"]}, {"_id": 0, "seller_id": 1}
    ) or {}
    seller_id = listing.get("seller_user_id") or listing.get("seller_id")

    await db.vehicle_settlements.update_one(
        {"stripe_payment_intent_id": payment_intent_id},
        {"$set": {
            "settlement_status": "AWAITING_DEALER_CONFIRMATION",
            "contact_revealed": True,
            "fee_paid_at": now,
            "updated_at": now,
            **({"seller_id": seller_id} if seller_id else {}),
        }}
    )

    logger.info(f"[VehicleFee] Fee paid — contact revealed for auction {settlement['auction_id']}")

    # Send bilingual success email to buyer
    try:
        buyer = await db.users.find_one({"id": settlement["buyer_id"]}, {"_id": 0, "email": 1, "name": 1})
        auction_id = settlement["auction_id"]

        # Try vehicle_listings first, then listings
        listing = await db.vehicle_listings.find_one({"id": auction_id}, {"_id": 0})
        if not listing:
            listing = await db.listings.find_one({"id": auction_id}, {"_id": 0})

        seller_id = (listing or {}).get("seller_user_id") or (listing or {}).get("seller_id")
        seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "name": 1, "email": 1, "phone": 1, "company_name": 1}) if seller_id else None

        if buyer and buyer.get("email") and seller:
            from services.emails._email_core import send_email
            hammer = settlement["hammer_price"]
            fee_amount = settlement["net_commission_amount"]
            seller_name = seller.get("company_name") or seller.get("name", "Seller")
            seller_contact = seller.get("email", "")
            seller_phone = seller.get("phone", "")

            html = f"""
            <div style="font-family:Arial,sans-serif;max-width:600px;margin:0 auto;">
              <h2>Congratulations — You Won! / Félicitations — Vous avez gagné!</h2>
              <hr/>
              <p><strong>EN:</strong></p>
              <p>Congratulations — you are the winning bidder for Auction #{auction_id[:8]}.</p>
              <p><strong>Hammer Price:</strong> ${hammer:,.2f} CAD</p>
              <p><strong>Seller:</strong> {seller_name} | {seller_contact} | {seller_phone}</p>
              <p>Payment for the vehicle is arranged directly between you and the seller. BidVex does not process or hold vehicle sale funds.</p>
              <p>BidVex Platform Fee of 2.5% (${fee_amount:,.2f}) has been charged separately to your card on file.</p>
              <hr/>
              <p><strong>FR:</strong></p>
              <p>Félicitations — vous êtes l'enchérisseur gagnant de l'enchère #{auction_id[:8]}.</p>
              <p><strong>Prix d'adjudication :</strong> {hammer:,.2f} $ CAD</p>
              <p><strong>Vendeur :</strong> {seller_name} | {seller_contact} | {seller_phone}</p>
              <p>Le paiement du véhicule est organisé directement entre vous et le vendeur. BidVex ne traite pas et ne détient pas les fonds de vente de véhicules.</p>
              <p>Les frais de plateforme BidVex de 2,5 % ({fee_amount:,.2f} $) ont été débités séparément de votre carte enregistrée.</p>
              <hr/>
              <p style="font-size:11px;color:#666;"><em>BidVex only collects facilitation and processing fees. The purchase price of the asset is settled privately between buyer and seller. / BidVex ne perçoit que les frais de facilitation et de traitement. Le prix d'achat de l'actif est réglé en privé entre l'acheteur et le vendeur.</em></p>
            </div>
            """
            await send_email(
                to_email=buyer["email"],
                subject=f"You Won Auction #{auction_id[:8]}! / Vous avez gagné l'enchère #{auction_id[:8]}!",
                html_content=html,
            )
            logger.info(f"[VehicleFee] Success email sent to {buyer['email']}")
    except Exception as e:
        logger.error(f"[VehicleFee] Email send error: {e}")

    return True


async def handle_vehicle_fee_failed(db, payment_intent_id: str):
    """Called by Stripe webhook on payment_intent.payment_failed for vehicle_platform_fee."""
    now = datetime.now(timezone.utc).isoformat()
    await db.vehicle_settlements.update_one(
        {"stripe_payment_intent_id": payment_intent_id},
        {"$set": {"settlement_status": "FEE_FAILED", "updated_at": now}}
    )
    logger.warning(f"[VehicleFee] Fee payment failed for PI {payment_intent_id}")
