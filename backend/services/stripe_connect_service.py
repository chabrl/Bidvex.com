"""
BidVex Stripe Connect Payment Service
Handles destination charges with tax calculations and gross-up formula

GROSS-UP FORMULA:
To ensure BidVex receives the full intended amount after Stripe fees (2.9% + $0.30):
gross_amount = (net_amount + 0.30) / (1 - 0.029)

PAYMENT FLOW:
1. General Items/Lots - Destination Charges via Stripe Connect
   - BidVex Service Fees (Buyer Premium + Seller Commission) taxed at 14.975%
   - Hammer Price: 0% tax if private seller, +14.975% if business seller
   - Application Fee goes to BidVex
   - Remainder transferred to seller's Connect account

2. Vehicles - Hybrid Payment (BidVex fees only via Stripe)
   - Only BidVex fees charged via Stripe
   - Hammer price paid directly by buyer to seller (Bank Draft)
"""

import os
import logging
from typing import Dict, Any, Optional, Tuple
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timezone
from dataclasses import dataclass, asdict
import uuid

logger = logging.getLogger(__name__)

# Stripe processing fee rates
STRIPE_PERCENTAGE_FEE = Decimal("0.029")  # 2.9%
STRIPE_FIXED_FEE = Decimal("0.30")        # $0.30 CAD

# Import tax constants from tax_engine
from services.tax_engine import (
    GST_RATE,
    QST_RATE,
    COMBINED_TAX_RATE,
    BIDVEX_GST_NUMBER,
    BIDVEX_QST_NUMBER,
    BIDVEX_LEGAL_NAME,
    BUYER_PREMIUM_RATES,
    SELLER_COMMISSION_RATES,
    VEHICLE_PLATFORM_FEE_RATE,
    PARTNER_PLATFORM_FEE_RATE,
    _round_currency,
    _to_cents,
    _normalize_tier
)


def _gross_up(net_amount: Decimal) -> Decimal:
    """
    Calculate gross amount to charge so BidVex receives net_amount after Stripe fees.
    
    Formula: gross = (net + 0.30) / (1 - 0.029)
    
    Example: To receive $100 net:
    gross = (100 + 0.30) / (1 - 0.029) = 100.30 / 0.971 = $103.30
    Stripe takes: 103.30 * 0.029 + 0.30 = $3.30
    BidVex receives: 103.30 - 3.30 = $100.00 ✓
    """
    return _round_currency((net_amount + STRIPE_FIXED_FEE) / (1 - STRIPE_PERCENTAGE_FEE))


def calculate_processing_fee(amount: Decimal) -> Decimal:
    """Calculate Stripe processing fee on a given amount"""
    return _round_currency(amount * STRIPE_PERCENTAGE_FEE + STRIPE_FIXED_FEE)


@dataclass
class CheckoutBreakdown:
    """Complete breakdown for checkout display and Stripe charge creation"""
    
    # Input
    hammer_price: Decimal
    buyer_tier: str
    seller_tier: str
    seller_is_tax_registered: bool
    is_vehicle: bool
    
    # Fees
    buyer_premium_rate: Decimal
    buyer_premium: Decimal
    seller_commission_rate: Decimal
    seller_commission: Decimal
    platform_fee: Decimal  # Vehicles only (2.5%)
    
    # BidVex fees subtotal (before tax)
    bidvex_fees_subtotal: Decimal
    
    # Taxes
    gst_on_hammer: Decimal      # 0 if private seller, 5% if business
    qst_on_hammer: Decimal      # 0 if private seller, 9.975% if business
    hammer_tax_total: Decimal
    
    gst_on_fees: Decimal        # 5% on all BidVex fees
    qst_on_fees: Decimal        # 9.975% on all BidVex fees
    fees_tax_total: Decimal
    
    total_tax: Decimal
    
    # Processing fee (Stripe 2.9% + $0.30)
    processing_fee: Decimal
    processing_fee_display: Decimal  # Visible to buyer
    
    # Totals
    subtotal_before_tax: Decimal
    buyer_total: Decimal           # Total buyer pays (hammer + premium + taxes + processing)
    buyer_total_cents: int
    
    # Stripe parameters (for destination charge)
    stripe_charge_amount_cents: int
    stripe_application_fee_cents: int  # What BidVex keeps
    stripe_transfer_amount_cents: int  # What seller receives
    
    # Seller info
    seller_payout: Decimal        # Hammer - commission (+ hammer tax if collected)
    seller_receives_tax: Decimal  # Tax collected on seller's behalf (business only)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with serializable types"""
        result = {}
        for key, value in asdict(self).items():
            if isinstance(value, Decimal):
                result[key] = float(value)
            else:
                result[key] = value
        return result


def calculate_general_checkout(
    hammer_price: float,
    buyer_tier: str = "basic",
    seller_tier: str = "basic",
    seller_is_tax_registered: bool = False,
    include_processing_fee: bool = True
) -> CheckoutBreakdown:
    """
    Calculate complete checkout breakdown for GENERAL items/lots
    
    This uses Stripe Connect destination charges:
    - Total charge goes to seller's Connect account
    - Application fee (BidVex's share) is deducted automatically
    - Seller receives remainder
    
    Args:
        hammer_price: Winning bid amount
        buyer_tier: Buyer's subscription tier
        seller_tier: Seller's subscription tier
        seller_is_tax_registered: Whether seller has GST/QST registration
        include_processing_fee: Whether to add processing fee to buyer total
    
    Returns:
        CheckoutBreakdown with all amounts calculated
    """
    hammer = Decimal(str(hammer_price))
    b_tier = _normalize_tier(buyer_tier)
    s_tier = _normalize_tier(seller_tier)
    
    # Get rates
    buyer_premium_rate = BUYER_PREMIUM_RATES.get(b_tier, Decimal("0.05"))
    seller_commission_rate = SELLER_COMMISSION_RATES.get(s_tier, Decimal("0.04"))
    
    # Calculate fees
    buyer_premium = _round_currency(hammer * buyer_premium_rate)
    seller_commission = _round_currency(hammer * seller_commission_rate)
    platform_fee = Decimal("0")  # No platform fee for general items
    
    bidvex_fees_subtotal = buyer_premium + seller_commission
    
    # Calculate taxes
    # Hammer price tax (only if seller is tax registered)
    if seller_is_tax_registered:
        gst_on_hammer = _round_currency(hammer * GST_RATE)
        qst_on_hammer = _round_currency(hammer * QST_RATE)
    else:
        gst_on_hammer = Decimal("0")
        qst_on_hammer = Decimal("0")
    hammer_tax_total = gst_on_hammer + qst_on_hammer
    
    # BidVex fees tax (always applies)
    gst_on_fees = _round_currency(bidvex_fees_subtotal * GST_RATE)
    qst_on_fees = _round_currency(bidvex_fees_subtotal * QST_RATE)
    fees_tax_total = gst_on_fees + qst_on_fees
    
    total_tax = hammer_tax_total + fees_tax_total
    
    # Subtotal before processing fee
    subtotal_before_processing = hammer + buyer_premium + total_tax
    
    # Calculate processing fee using gross-up
    if include_processing_fee:
        gross_amount = _gross_up(subtotal_before_processing)
        processing_fee = gross_amount - subtotal_before_processing
    else:
        processing_fee = Decimal("0")
        gross_amount = subtotal_before_processing
    
    buyer_total = gross_amount
    
    # Stripe parameters
    # Application fee = BidVex fees (premium + commission) + tax on fees
    application_fee = buyer_premium + seller_commission + fees_tax_total
    
    # What seller receives = Hammer - commission + hammer tax (if business)
    seller_payout = hammer - seller_commission
    seller_receives_tax = hammer_tax_total  # Tax collected on seller's behalf
    
    # Transfer to seller = hammer - commission + hammer_tax (if business seller)
    # The hammer tax goes to seller who must remit it to government
    transfer_amount = seller_payout + seller_receives_tax
    
    return CheckoutBreakdown(
        hammer_price=hammer,
        buyer_tier=buyer_tier,
        seller_tier=seller_tier,
        seller_is_tax_registered=seller_is_tax_registered,
        is_vehicle=False,
        
        buyer_premium_rate=buyer_premium_rate,
        buyer_premium=buyer_premium,
        seller_commission_rate=seller_commission_rate,
        seller_commission=seller_commission,
        platform_fee=platform_fee,
        
        bidvex_fees_subtotal=bidvex_fees_subtotal,
        
        gst_on_hammer=gst_on_hammer,
        qst_on_hammer=qst_on_hammer,
        hammer_tax_total=hammer_tax_total,
        
        gst_on_fees=gst_on_fees,
        qst_on_fees=qst_on_fees,
        fees_tax_total=fees_tax_total,
        
        total_tax=total_tax,
        
        processing_fee=processing_fee,
        processing_fee_display=processing_fee,
        
        subtotal_before_tax=hammer + buyer_premium,
        buyer_total=buyer_total,
        buyer_total_cents=_to_cents(buyer_total),
        
        stripe_charge_amount_cents=_to_cents(buyer_total),
        stripe_application_fee_cents=_to_cents(application_fee),
        stripe_transfer_amount_cents=_to_cents(transfer_amount),
        
        seller_payout=seller_payout,
        seller_receives_tax=seller_receives_tax
    )


def calculate_vehicle_checkout(
    hammer_price: float,
    buyer_tier: str = "basic"
) -> CheckoutBreakdown:
    """
    Calculate checkout breakdown for VEHICLE auctions
    
    Vehicle auctions use HYBRID payment:
    - Only BidVex fees are charged via Stripe (with tax + processing)
    - Hammer price is paid directly to seller via Bank Draft
    
    Args:
        hammer_price: Winning bid amount (for fee calculation)
        buyer_tier: Buyer's subscription tier
    
    Returns:
        CheckoutBreakdown with BidVex fees only in Stripe charge
    """
    hammer = Decimal(str(hammer_price))
    b_tier = _normalize_tier(buyer_tier)
    
    # Get buyer premium rate
    buyer_premium_rate = BUYER_PREMIUM_RATES.get(b_tier, Decimal("0.05"))
    
    # Calculate fees
    buyer_premium = _round_currency(hammer * buyer_premium_rate)
    platform_fee = _round_currency(hammer * VEHICLE_PLATFORM_FEE_RATE)
    
    bidvex_fees_subtotal = buyer_premium + platform_fee
    
    # Tax only on BidVex fees (not hammer - hammer paid offline)
    gst_on_fees = _round_currency(bidvex_fees_subtotal * GST_RATE)
    qst_on_fees = _round_currency(bidvex_fees_subtotal * QST_RATE)
    fees_tax_total = gst_on_fees + qst_on_fees
    
    # No hammer tax via Stripe (paid offline)
    gst_on_hammer = Decimal("0")
    qst_on_hammer = Decimal("0")
    hammer_tax_total = Decimal("0")
    
    # Subtotal for Stripe charge (fees + tax only)
    subtotal_before_processing = bidvex_fees_subtotal + fees_tax_total
    
    # Gross up for processing fee
    gross_amount = _gross_up(subtotal_before_processing)
    processing_fee = gross_amount - subtotal_before_processing
    
    buyer_total_stripe = gross_amount  # What buyer pays via Stripe
    
    return CheckoutBreakdown(
        hammer_price=hammer,
        buyer_tier=buyer_tier,
        seller_tier="basic",  # Not relevant for vehicles
        seller_is_tax_registered=False,  # Not relevant - hammer paid offline
        is_vehicle=True,
        
        buyer_premium_rate=buyer_premium_rate,
        buyer_premium=buyer_premium,
        seller_commission_rate=Decimal("0"),  # No commission for vehicles
        seller_commission=Decimal("0"),
        platform_fee=platform_fee,
        
        bidvex_fees_subtotal=bidvex_fees_subtotal,
        
        gst_on_hammer=gst_on_hammer,
        qst_on_hammer=qst_on_hammer,
        hammer_tax_total=hammer_tax_total,
        
        gst_on_fees=gst_on_fees,
        qst_on_fees=qst_on_fees,
        fees_tax_total=fees_tax_total,
        
        total_tax=fees_tax_total,  # Only fees tax for vehicles
        
        processing_fee=processing_fee,
        processing_fee_display=processing_fee,
        
        subtotal_before_tax=bidvex_fees_subtotal,
        buyer_total=buyer_total_stripe,
        buyer_total_cents=_to_cents(buyer_total_stripe),
        
        # For vehicles, full charge goes to BidVex (no destination charge)
        stripe_charge_amount_cents=_to_cents(buyer_total_stripe),
        stripe_application_fee_cents=_to_cents(buyer_total_stripe),  # All to BidVex
        stripe_transfer_amount_cents=0,  # No transfer - hammer paid offline
        
        seller_payout=hammer,  # Seller receives full hammer via Bank Draft
        seller_receives_tax=Decimal("0")  # Tax handled separately if business
    )


def calculate_partner_listing_checkout(
    hammer_price: float,
    custom_buyer_premium_rate: float = 0.0,
    partner_is_tax_registered: bool = False,
    include_processing_fee: bool = True
) -> CheckoutBreakdown:
    """
    Calculate checkout breakdown for PARTNER listings.
    
    Partner fee model (overrides ALL subscription discounts):
    - Platform Fee: Fixed 3% of Hammer Price (collected by BidVex)
    - Buyer Premium: Custom rate set by partner (e.g., 18%)
    - Stripe fee: Recovered from buyer via Net-Zero gross-up
    - Transfer to partner: Hammer + Buyer Premium
    - Application fee: Platform Fee (3%) + tax on fees + Stripe recovery
    
    Args:
        hammer_price: Winning bid amount
        custom_buyer_premium_rate: Partner's custom buyer premium (e.g., 0.18 for 18%)
        partner_is_tax_registered: Whether partner has GST/QST registration
        include_processing_fee: Whether to add processing fee to buyer total
    """
    hammer = Decimal(str(hammer_price))
    bp_rate = Decimal(str(custom_buyer_premium_rate))
    
    # Partner-specific rates (override subscription discounts)
    buyer_premium = _round_currency(hammer * bp_rate)
    platform_fee = _round_currency(hammer * PARTNER_PLATFORM_FEE_RATE)
    
    # BidVex fees = platform fee only (buyer premium goes to partner)
    bidvex_fees_subtotal = platform_fee
    
    # Taxes on hammer (only if partner is tax registered)
    if partner_is_tax_registered:
        gst_on_hammer = _round_currency(hammer * GST_RATE)
        qst_on_hammer = _round_currency(hammer * QST_RATE)
    else:
        gst_on_hammer = Decimal("0")
        qst_on_hammer = Decimal("0")
    hammer_tax_total = gst_on_hammer + qst_on_hammer
    
    # Tax on BidVex fees (platform fee) — always applies
    gst_on_fees = _round_currency(bidvex_fees_subtotal * GST_RATE)
    qst_on_fees = _round_currency(bidvex_fees_subtotal * QST_RATE)
    fees_tax_total = gst_on_fees + qst_on_fees
    
    # Tax on buyer premium (if partner is registered, tax on BP goes to partner)
    gst_on_bp = _round_currency(buyer_premium * GST_RATE) if partner_is_tax_registered else Decimal("0")
    qst_on_bp = _round_currency(buyer_premium * QST_RATE) if partner_is_tax_registered else Decimal("0")
    bp_tax_total = gst_on_bp + qst_on_bp
    
    total_tax = hammer_tax_total + fees_tax_total + bp_tax_total
    
    # Subtotal before processing
    subtotal_before_processing = hammer + buyer_premium + total_tax
    
    # Gross-up for Stripe processing fee
    if include_processing_fee:
        gross_amount = _gross_up(subtotal_before_processing)
        processing_fee = gross_amount - subtotal_before_processing
    else:
        processing_fee = Decimal("0")
        gross_amount = subtotal_before_processing
    
    buyer_total = gross_amount
    
    # Stripe parameters:
    # Transfer to partner = Hammer + BP + hammer_tax + bp_tax (partner remits tax)
    transfer_to_partner = hammer + buyer_premium + hammer_tax_total + bp_tax_total
    
    # Application fee (BidVex keeps) = Platform fee + fee taxes + processing fee
    application_fee = platform_fee + fees_tax_total + processing_fee
    
    return CheckoutBreakdown(
        hammer_price=hammer,
        buyer_tier="partner",
        seller_tier="partner",
        seller_is_tax_registered=partner_is_tax_registered,
        is_vehicle=False,
        
        buyer_premium_rate=bp_rate,
        buyer_premium=buyer_premium,
        seller_commission_rate=Decimal("0"),  # No seller commission for partners
        seller_commission=Decimal("0"),
        platform_fee=platform_fee,
        
        bidvex_fees_subtotal=bidvex_fees_subtotal,
        
        gst_on_hammer=gst_on_hammer,
        qst_on_hammer=qst_on_hammer,
        hammer_tax_total=hammer_tax_total,
        
        gst_on_fees=gst_on_fees,
        qst_on_fees=qst_on_fees,
        fees_tax_total=fees_tax_total,
        
        total_tax=total_tax,
        
        processing_fee=processing_fee,
        processing_fee_display=processing_fee,
        
        subtotal_before_tax=hammer + buyer_premium,
        buyer_total=buyer_total,
        buyer_total_cents=_to_cents(buyer_total),
        
        stripe_charge_amount_cents=_to_cents(buyer_total),
        stripe_application_fee_cents=_to_cents(application_fee),
        stripe_transfer_amount_cents=_to_cents(transfer_to_partner),
        
        seller_payout=transfer_to_partner,
        seller_receives_tax=hammer_tax_total + bp_tax_total
    )


async def create_destination_charge(
    db,
    listing_id: str,
    buyer_id: str,
    breakdown: CheckoutBreakdown,
    return_url: str,
    seller_connect_account_id: str
) -> Dict[str, Any]:
    """
    Create Stripe Checkout Session with destination charge
    
    For general items/lots, uses destination charges to split payment:
    - Total charge on buyer
    - Application fee to BidVex
    - Remainder to seller's Connect account
    """
    import stripe
    
    # Get buyer info
    buyer = await db.users.find_one({"id": buyer_id})
    if not buyer:
        raise ValueError("Buyer not found")
    
    customer_id = buyer.get("stripe_customer_id")
    
    # Create customer if needed
    if not customer_id:
        customer = stripe.Customer.create(
            email=buyer.get("email"),
            name=buyer.get("name"),
            metadata={"user_id": buyer_id, "platform": "bidvex"}
        )
        customer_id = customer.id
        await db.users.update_one(
            {"id": buyer_id},
            {"$set": {"stripe_customer_id": customer_id}}
        )
    
    # Generate invoice ID
    invoice_id = str(uuid.uuid4())
    
    # Build line items for display
    line_items_display = [
        f"Hammer Price: ${float(breakdown.hammer_price):,.2f}",
        f"Buyer's Premium ({float(breakdown.buyer_premium_rate)*100:.1f}%): ${float(breakdown.buyer_premium):,.2f}",
    ]
    
    if breakdown.seller_is_tax_registered:
        line_items_display.append(f"GST/QST on Item (14.975%): ${float(breakdown.hammer_tax_total):,.2f}")
    
    line_items_display.append(f"GST/QST on Fees: ${float(breakdown.fees_tax_total):,.2f}")
    
    if breakdown.processing_fee > 0:
        line_items_display.append(f"Processing Fee: ${float(breakdown.processing_fee):,.2f}")
    
    description = " | ".join(line_items_display)
    
    # Create checkout session with destination charge
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "cad",
                "unit_amount": breakdown.buyer_total_cents,
                "product_data": {
                    "name": f"BidVex Auction - {listing_id[:8]}",
                    "description": description
                }
            },
            "quantity": 1
        }],
        payment_intent_data={
            "application_fee_amount": breakdown.stripe_application_fee_cents,
            "transfer_data": {
                "destination": seller_connect_account_id
            },
            "metadata": {
                "listing_id": listing_id,
                "buyer_id": buyer_id,
                "invoice_id": invoice_id,
                "type": "auction_purchase"
            }
        },
        success_url=f"{return_url}?session_id={{CHECKOUT_SESSION_ID}}&status=success",
        cancel_url=f"{return_url}?status=cancelled",
        metadata={
            "listing_id": listing_id,
            "buyer_id": buyer_id,
            "invoice_id": invoice_id,
            "type": "auction_purchase",
            "hammer_price": str(float(breakdown.hammer_price)),
            "seller_is_business": str(breakdown.seller_is_tax_registered)
        }
    )
    
    # Store pending payment record
    await db.pending_payments.insert_one({
        "id": invoice_id,
        "session_id": session.id,
        "listing_id": listing_id,
        "buyer_id": buyer_id,
        "breakdown": breakdown.to_dict(),
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {
        "session_id": session.id,
        "checkout_url": session.url,
        "invoice_id": invoice_id,
        "breakdown": breakdown.to_dict()
    }


async def create_vehicle_payment_session(
    db,
    auction_id: str,
    buyer_id: str,
    breakdown: CheckoutBreakdown,
    return_url: str
) -> Dict[str, Any]:
    """
    Create Stripe Checkout Session for vehicle BidVex fees only
    
    Vehicles use a hybrid payment model:
    - BidVex fees charged via Stripe (this session)
    - Hammer price paid directly to seller via Bank Draft
    """
    import stripe
    
    # Get buyer info
    buyer = await db.users.find_one({"id": buyer_id})
    if not buyer:
        raise ValueError("Buyer not found")
    
    customer_id = buyer.get("stripe_customer_id")
    
    if not customer_id:
        customer = stripe.Customer.create(
            email=buyer.get("email"),
            name=buyer.get("name"),
            metadata={"user_id": buyer_id, "platform": "bidvex"}
        )
        customer_id = customer.id
        await db.users.update_one(
            {"id": buyer_id},
            {"$set": {"stripe_customer_id": customer_id}}
        )
    
    invoice_id = str(uuid.uuid4())
    
    # Build description
    description = (
        f"BidVex Vehicle Auction Fees | "
        f"Buyer Premium: ${float(breakdown.buyer_premium):,.2f} | "
        f"Platform Fee: ${float(breakdown.platform_fee):,.2f} | "
        f"Tax: ${float(breakdown.fees_tax_total):,.2f} | "
        f"Processing: ${float(breakdown.processing_fee):,.2f}"
    )
    
    # Create session (no destination charge - all to BidVex)
    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="payment",
        line_items=[{
            "price_data": {
                "currency": "cad",
                "unit_amount": breakdown.buyer_total_cents,
                "product_data": {
                    "name": f"BidVex Vehicle Fees - {auction_id[:8]}",
                    "description": description
                }
            },
            "quantity": 1
        }],
        payment_intent_data={
            "metadata": {
                "auction_id": auction_id,
                "buyer_id": buyer_id,
                "invoice_id": invoice_id,
                "type": "vehicle_fees",
                "hammer_price": str(float(breakdown.hammer_price))
            }
        },
        success_url=f"{return_url}?session_id={{CHECKOUT_SESSION_ID}}&status=success",
        cancel_url=f"{return_url}?status=cancelled",
        metadata={
            "auction_id": auction_id,
            "buyer_id": buyer_id,
            "invoice_id": invoice_id,
            "type": "vehicle_fees",
            "hammer_price": str(float(breakdown.hammer_price))
        }
    )
    
    # Store pending payment
    await db.pending_payments.insert_one({
        "id": invoice_id,
        "session_id": session.id,
        "auction_id": auction_id,
        "buyer_id": buyer_id,
        "breakdown": breakdown.to_dict(),
        "status": "pending",
        "is_vehicle": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    
    return {
        "session_id": session.id,
        "checkout_url": session.url,
        "invoice_id": invoice_id,
        "breakdown": breakdown.to_dict(),
        "hammer_price_due_to_seller": float(breakdown.hammer_price),
        "payment_instructions": "After paying BidVex fees, you must send a Bank Draft for the hammer price directly to the seller within 14 days."
    }


# Export public functions
__all__ = [
    "calculate_general_checkout",
    "calculate_vehicle_checkout",
    "create_destination_charge",
    "create_vehicle_payment_session",
    "CheckoutBreakdown",
    "calculate_processing_fee",
    "STRIPE_PERCENTAGE_FEE",
    "STRIPE_FIXED_FEE"
]
