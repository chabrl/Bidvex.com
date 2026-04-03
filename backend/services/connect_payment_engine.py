"""
BidVex Stripe Connect Payment Engine
Handles multi-party payments, platform commissions, deposits, and payouts.

Payment Flow:
1. Buyer pays total (hammer + buyer premium + taxes + Stripe processing fee)
2. Stripe deducts processing fee (~2.9% + $0.30)
3. application_fee_amount routes platform commission to BidVex Treasury
4. Remainder is transferred to Seller's Connect account

For Vehicles:
- Hammer price is settled outside Stripe (bank draft)
- Only BidVex fees (buyer premium + platform fee + taxes) go through Stripe
"""

import os
import logging
import stripe
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional, Dict, Any

from services.pricing_config import (
    get_platform_fee_rate,
    get_buyer_premium_rate,
    get_seller_commission_rate,
    STRIPE_PROCESSING_RATE,
    STRIPE_PROCESSING_FIXED,
    GST_RATE,
    QST_RATE,
    DEPOSIT_THRESHOLD_CAD,
    DEPOSIT_AMOUNT_CENTS,
    PROMOTION_TIERS,
    calculate_email_credit_cost,
)

logger = logging.getLogger(__name__)

stripe.api_key = os.environ.get("STRIPE_API_KEY", "")


def _to_cents(amount: Decimal) -> int:
    """Convert a Decimal dollar amount to integer cents."""
    return int((amount * 100).to_integral_value(rounding=ROUND_HALF_UP))


def calculate_connect_checkout(
    hammer_price: float,
    category: str = "general",
    buyer_tier: str = "free",
    seller_tier: str = "free",
    currency: str = "CAD",
    province: str = "QC",
    include_stripe_fee: bool = True,
) -> Dict[str, Any]:
    """
    Calculate the full payment breakdown for a Stripe Connect checkout.

    Returns dict with all amounts in both dollars and cents.
    """
    hp = Decimal(str(hammer_price))
    cur = currency.upper()

    # Rates
    platform_rate = get_platform_fee_rate(category)
    buyer_premium_rate = get_buyer_premium_rate(buyer_tier)
    seller_commission_rate = get_seller_commission_rate(seller_tier)

    # Buyer premium (on top of hammer price)
    buyer_premium = (hp * buyer_premium_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Platform commission (from the hammer price)
    platform_fee = (hp * platform_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Seller commission (deducted from seller payout)
    seller_commission = (hp * seller_commission_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Subtotal before tax (what the buyer sees: hammer + buyer premium)
    subtotal = hp + buyer_premium

    # Taxes (Quebec: GST + QST on the buyer premium + platform fee)
    taxable = buyer_premium + platform_fee
    gst = (taxable * GST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    qst = (taxable * QST_RATE).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    total_tax = gst + qst

    # Grand total before Stripe processing fee
    pre_stripe_total = subtotal + total_tax

    # Stripe processing fee (passed to buyer)
    if include_stripe_fee:
        stripe_fee = ((pre_stripe_total * STRIPE_PROCESSING_RATE) + STRIPE_PROCESSING_FIXED).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    else:
        stripe_fee = Decimal("0")

    # Final buyer total
    buyer_total = pre_stripe_total + stripe_fee

    # Application fee = platform commission + buyer premium + seller commission + taxes
    # This is what BidVex keeps after Stripe deducts processing
    application_fee = platform_fee + buyer_premium + seller_commission + total_tax

    # Seller payout = hammer - seller commission
    seller_payout = hp - seller_commission

    return {
        "hammer_price": float(hp),
        "currency": cur,
        "category": category,
        "buyer_tier": buyer_tier,
        "seller_tier": seller_tier,
        # Rates
        "platform_fee_rate": float(platform_rate),
        "buyer_premium_rate": float(buyer_premium_rate),
        "seller_commission_rate": float(seller_commission_rate),
        # Amounts
        "buyer_premium": float(buyer_premium),
        "platform_fee": float(platform_fee),
        "seller_commission": float(seller_commission),
        # Tax
        "gst": float(gst),
        "qst": float(qst),
        "total_tax": float(total_tax),
        # Stripe
        "stripe_processing_fee": float(stripe_fee),
        # Totals
        "buyer_total": float(buyer_total),
        "seller_payout": float(seller_payout),
        "application_fee": float(application_fee),
        # Cents (for Stripe API)
        "buyer_total_cents": _to_cents(buyer_total),
        "application_fee_cents": _to_cents(application_fee),
        "seller_payout_cents": _to_cents(seller_payout),
    }


async def create_connect_checkout_session(
    db,
    buyer_id: str,
    listing: Dict[str, Any],
    breakdown: Dict[str, Any],
    success_url: str,
    cancel_url: str,
    payment_type: str = "auction_purchase",
    metadata_extra: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """
    Create a Stripe Checkout Session with Connect (application_fee + transfer_data).
    """
    buyer = await db.users.find_one({"id": buyer_id})
    if not buyer:
        raise ValueError("Buyer not found")

    seller_id = listing.get("seller_id")
    seller = await db.users.find_one({"id": seller_id})
    connect_account_id = seller.get("stripe_connect_account_id") if seller else None

    # Ensure buyer has a Stripe customer
    customer_id = buyer.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(
            email=buyer.get("email", ""),
            metadata={"user_id": buyer_id, "platform": "bidvex"},
        )
        customer_id = customer.id
        await db.users.update_one(
            {"id": buyer_id},
            {"$set": {"stripe_customer_id": customer_id}},
        )

    currency = breakdown.get("currency", "CAD").lower()
    line_item_name = listing.get("title", "Auction Purchase")

    # Build metadata
    meta = {
        "user_id": buyer_id,
        "listing_id": listing.get("id", ""),
        "seller_id": seller_id or "",
        "transaction_type": payment_type,
        "type": payment_type,
        "hammer_price": str(breakdown["hammer_price"]),
        "platform_fee": str(breakdown["platform_fee"]),
        "buyer_premium": str(breakdown["buyer_premium"]),
        "gst": str(breakdown["gst"]),
        "qst": str(breakdown["qst"]),
    }
    if metadata_extra:
        meta.update(metadata_extra)

    # Build session params
    session_params = {
        "customer": customer_id,
        "payment_method_types": ["card"],
        "mode": "payment",
        "line_items": [
            {
                "price_data": {
                    "currency": currency,
                    "unit_amount": breakdown["buyer_total_cents"],
                    "product_data": {
                        "name": line_item_name,
                        "description": (
                            f"Hammer: ${breakdown['hammer_price']:,.2f} | "
                            f"Premium: ${breakdown['buyer_premium']:,.2f} | "
                            f"Tax: ${breakdown['total_tax']:,.2f}"
                        ),
                    },
                },
                "quantity": 1,
            }
        ],
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": meta,
    }

    # If seller has Connect account, split the payment
    if connect_account_id:
        session_params["payment_intent_data"] = {
            "application_fee_amount": breakdown["application_fee_cents"],
            "transfer_data": {"destination": connect_account_id},
            "metadata": meta,
        }
    else:
        # No Connect account — BidVex collects everything
        session_params["payment_intent_data"] = {"metadata": meta}

    # Enable Stripe Radar for high-value transactions
    if breakdown["hammer_price"] >= 5000:
        session_params["payment_intent_data"]["statement_descriptor_suffix"] = "BIDVEX"

    session = stripe.checkout.Session.create(**session_params)
    return {
        "session_id": session.id,
        "checkout_url": session.url,
        "breakdown": breakdown,
    }


async def create_deposit_hold(
    db,
    user_id: str,
    listing_id: str,
    amount_cents: int = DEPOSIT_AMOUNT_CENTS,
    currency: str = "cad",
) -> Dict[str, Any]:
    """
    Create a $1,000 pre-authorization hold for high-value auctions (>$10k).
    Uses SetupIntent + PaymentIntent with capture_method=manual.
    """
    user = await db.users.find_one({"id": user_id})
    if not user:
        raise ValueError("User not found")

    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        customer = stripe.Customer.create(
            email=user.get("email", ""),
            metadata={"user_id": user_id, "platform": "bidvex"},
        )
        customer_id = customer.id
        await db.users.update_one(
            {"id": user_id},
            {"$set": {"stripe_customer_id": customer_id}},
        )

    # Create a PaymentIntent with manual capture (hold, don't charge)
    intent = stripe.PaymentIntent.create(
        amount=amount_cents,
        currency=currency,
        customer=customer_id,
        capture_method="manual",  # Pre-auth: hold only
        metadata={
            "user_id": user_id,
            "listing_id": listing_id,
            "transaction_type": "bidding_deposit",
            "platform": "bidvex",
        },
        description=f"BidVex Bidding Deposit — Listing {listing_id}",
        statement_descriptor_suffix="DEPOSIT",
    )

    # Store the hold in DB
    from datetime import datetime, timezone
    import uuid

    deposit_record = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "listing_id": listing_id,
        "payment_intent_id": intent.id,
        "client_secret": intent.client_secret,
        "amount_cents": amount_cents,
        "currency": currency,
        "status": "requires_confirmation",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.bidding_deposits.insert_one(deposit_record)

    return {
        "deposit_id": deposit_record["id"],
        "client_secret": intent.client_secret,
        "payment_intent_id": intent.id,
        "amount": amount_cents / 100,
        "currency": currency.upper(),
        "status": "requires_confirmation",
    }


async def release_deposit(db, user_id: str, listing_id: str) -> bool:
    """Release (cancel) a bidding deposit hold when the user loses the auction."""
    deposit = await db.bidding_deposits.find_one({
        "user_id": user_id,
        "listing_id": listing_id,
        "status": {"$in": ["requires_capture", "requires_confirmation", "succeeded"]},
    })
    if not deposit:
        return False

    try:
        stripe.PaymentIntent.cancel(deposit["payment_intent_id"])
        await db.bidding_deposits.update_one(
            {"id": deposit["id"]},
            {"$set": {"status": "released", "released_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}},
        )
        logger.info(f"Released deposit {deposit['id']} for user {user_id}")
        return True
    except stripe.StripeError as e:
        logger.error(f"Failed to release deposit: {e}")
        return False


async def capture_deposit(db, user_id: str, listing_id: str) -> bool:
    """Capture a bidding deposit when the winner fails to pay the final invoice."""
    deposit = await db.bidding_deposits.find_one({
        "user_id": user_id,
        "listing_id": listing_id,
        "status": "requires_capture",
    })
    if not deposit:
        return False

    try:
        stripe.PaymentIntent.capture(deposit["payment_intent_id"])
        await db.bidding_deposits.update_one(
            {"id": deposit["id"]},
            {"$set": {"status": "captured", "captured_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat()}},
        )
        logger.info(f"Captured deposit {deposit['id']} for user {user_id}")
        return True
    except stripe.StripeError as e:
        logger.error(f"Failed to capture deposit: {e}")
        return False


def create_promotion_checkout(
    customer_id: str,
    listing_id: str,
    user_id: str,
    tier: str,
    success_url: str,
    cancel_url: str,
) -> Dict[str, Any]:
    """Create a Stripe Checkout for listing promotion purchase."""
    promo = PROMOTION_TIERS.get(tier)
    if not promo:
        raise ValueError(f"Invalid promotion tier: {tier}")

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "cad",
                "unit_amount": promo["price_cents"],
                "product_data": {
                    "name": f"BidVex {promo['label']}",
                    "description": f"{promo['duration_days']}-day listing boost: {', '.join(promo['features'])}",
                },
            },
            "quantity": 1,
        }],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "type": "listing_promotion",
            "user_id": user_id,
            "listing_id": listing_id,
            "promotion_tier": tier,
            "duration_days": str(promo["duration_days"]),
            "transaction_type": "promotion",
        },
    )
    return {"session_id": session.id, "checkout_url": session.url, "tier": tier, "price": promo["price_cents"] / 100}


def create_email_credits_checkout(
    customer_id: str,
    user_id: str,
    quantity: int,
    success_url: str,
    cancel_url: str,
) -> Dict[str, Any]:
    """Create a Stripe Checkout for email marketing credits."""
    total_cents = calculate_email_credit_cost(quantity)
    per_email = total_cents / quantity if quantity > 0 else 0

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "cad",
                "unit_amount": total_cents,
                "product_data": {
                    "name": f"BidVex Email Credits ({quantity:,})",
                    "description": f"{quantity:,} email credits at ~${per_email/100:.3f}/email",
                },
            },
            "quantity": 1,
        }],
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "type": "email_credits",
            "user_id": user_id,
            "credit_quantity": str(quantity),
            "transaction_type": "email_credits",
        },
    )
    return {"session_id": session.id, "checkout_url": session.url, "quantity": quantity, "total_cents": total_cents}
