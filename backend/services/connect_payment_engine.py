"""
BidVex Stripe Connect Payment Engine
Handles multi-party payments with two-tier marketplace economy:

PARTNER FLOW (is_partner=True, $100/yr Annual Fee):
  - BidVex keeps ONLY Seller Commission (2.5% vehicle / 3.0% general)
  - 100% of Buyer Premium goes to Partner's Connect account
  - Stripe fees deducted from Partner's final payout (NOT passed to buyer)
  - Taxes on (Hammer + Premium)

STANDARD FLOW (is_partner=False):
  - BidVex keeps BOTH Buyer Premium AND Seller Commission
  - Seller receives only Hammer - Seller Commission
  - Stripe processing fee passed to buyer
  - Taxes on (Hammer + Premium)

For Vehicles (both flows):
  - Hammer price settled outside Stripe (bank draft)
  - Only fees go through Stripe
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
    AFFILIATE_COMMISSION_RATE,
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
    seller_is_partner: bool = False,
) -> Dict[str, Any]:
    """
    Calculate payment breakdown using PricingManager (Master Pricing Structure).

    Routes to the correct PricingManager method based on category and seller type.
    Returns a backward-compatible dict consumed by create_connect_checkout_session
    and build_itemized_line_items.
    """
    from services.pricing_manager import PricingManager, stripe_recovery as _sr
    from decimal import Decimal

    hp = Decimal(str(hammer_price))
    cur = currency.upper()
    cat = category.lower() if category else "general"
    is_vehicle = any(kw in cat for kw in ("vehicle", "car", "auto", "truck", "motorcycle"))

    # ── Route to correct PricingManager method ──
    if seller_is_partner:
        result = PricingManager.partner_auction(hammer_price, province)
    elif is_vehicle:
        result = PricingManager.vehicle_auction(hammer_price, province, buyer_tier)
    else:
        result = PricingManager.non_vehicle_stripe(hammer_price, province, buyer_tier, seller_tier)

    bi = result.buyer_invoice
    si = result.seller_invoice

    # ── Build backward-compatible return dict ──
    flow_type = "PARTNER_FLOW" if seller_is_partner else "STANDARD_FLOW"

    # Extract individual tax components for Stripe line items
    gst = 0.0
    qst = 0.0
    hst = 0.0
    for ln in bi.lines:
        if ln.line_type == "tax":
            if "GST + QST" in ln.description or "GST" in ln.description:
                # For QC, split into GST and QST from the tax breakdown
                if bi.tax_type == "GST+QST":
                    # Recalculate from the taxable amount
                    taxable_d = Decimal(str(bi.fees_subtotal + bi.stripe_recovery))
                    gst = float((taxable_d * Decimal("0.05")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                    qst = float((taxable_d * Decimal("0.09975")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
                elif bi.tax_type == "HST":
                    hst = ln.amount
                else:
                    gst = ln.amount

    total_tax = bi.tax_amount

    # For vehicles: hammer is NOT in the Stripe charge (settled offline)
    # For non-vehicles: hammer IS in the Stripe charge
    if is_vehicle:
        stripe_charge = Decimal(str(bi.total))  # Only fees + stripe + tax
        buyer_total_full = hp + stripe_charge  # Full buyer cost incl offline hammer
    else:
        stripe_charge = Decimal(str(bi.total))  # hammer + BP + stripe + tax
        buyer_total_full = stripe_charge

    # Seller payout and commission
    seller_commission = 0.0
    seller_commission_rate = 0.0
    seller_payout = float(hp)  # default: seller keeps hammer
    buyer_premium = bi.fees_subtotal if not is_vehicle else 0.0
    platform_fee = bi.fees_subtotal if is_vehicle else 0.0
    partner_premium_retained = 0.0

    if si:
        seller_commission = si.fees_subtotal
        # Find commission rate from line items
        for ln in si.lines:
            if ln.rate and ln.line_type in ("fee", "deduction"):
                seller_commission_rate = ln.rate
                break
        seller_payout = si.total  # For non_vehicle_stripe, this is net payout
        if not is_vehicle and not seller_is_partner:
            # Standard non-vehicle: seller payout = hammer - SC - stripe - tax
            pass  # si.total already correct

    if seller_is_partner:
        seller_commission_rate = 0.03
        platform_fee = seller_commission  # For partners, platform fee = commission

    # Application fee (what BidVex keeps via Stripe)
    if seller_is_partner:
        application_fee = Decimal(str(seller_commission)) if not is_vehicle else stripe_charge
    elif is_vehicle:
        application_fee = stripe_charge
    else:
        application_fee = Decimal(str(buyer_premium + seller_commission + total_tax))

    return {
        "hammer_price": float(hp),
        "currency": cur,
        "category": category,
        "is_vehicle": is_vehicle,
        "flow_type": flow_type,
        "seller_is_partner": seller_is_partner,
        "buyer_tier": buyer_tier,
        "seller_tier": seller_tier,
        "province": province,
        # Rates
        "platform_fee_rate": 0.025 if is_vehicle else 0.0,
        "buyer_premium_rate": 0.0 if (is_vehicle or seller_is_partner) else (bi.fees_subtotal / hammer_price if hammer_price else 0),
        "seller_commission_rate": float(seller_commission_rate),
        # Amounts
        "buyer_premium": buyer_premium,
        "platform_fee": platform_fee,
        "seller_commission": seller_commission,
        "partner_premium_retained": partner_premium_retained,
        # Tax (on fees only — Rule 5)
        "tax_type": bi.tax_type,
        "tax_label": bi.tax_label,
        "taxable_amount": bi.fees_subtotal + bi.stripe_recovery,
        "gst": gst,
        "qst": qst,
        "hst": hst,
        "total_tax": total_tax,
        # Stripe
        "stripe_processing_fee": bi.stripe_recovery,
        # Totals
        "buyer_total": float(buyer_total_full),
        "stripe_charge": float(stripe_charge),
        "seller_payout": float(seller_payout),
        "application_fee": float(application_fee),
        # Cents (for Stripe API)
        "buyer_total_cents": _to_cents(stripe_charge),
        "application_fee_cents": _to_cents(application_fee),
        "seller_payout_cents": _to_cents(Decimal(str(seller_payout))),
    }


def build_itemized_line_items(
    breakdown: Dict[str, Any],
    listing_title: str = "Auction Purchase",
    late_penalty: float = 0.0,
    is_vehicle: bool = False,
) -> list:
    """
    Build separate Stripe line_items for Quebec tax compliance.
    GST and QST appear as distinct rows on the Stripe checkout page.

    General: Hammer + Buyer Premium + GST + QST + Stripe Fee (Standard only)
    Vehicle: Buyer Premium + Platform Fee + GST + QST + Stripe Fee (Standard only)
    Partner flow: No Processing Fee line (deducted from Partner payout by Stripe)
    """
    currency = breakdown.get("currency", "CAD").lower()
    is_partner = breakdown.get("seller_is_partner", False)
    items = []

    # 1. Hammer Price (general only — vehicles pay hammer offline via bank draft)
    if not is_vehicle:
        hammer_cents = _to_cents(Decimal(str(breakdown["hammer_price"])))
        items.append({
            "price_data": {
                "currency": currency,
                "unit_amount": hammer_cents,
                "product_data": {
                    "name": listing_title,
                    "description": "Winning bid amount",
                },
            },
            "quantity": 1,
        })

    # 2. Buyer Premium
    premium_cents = _to_cents(Decimal(str(breakdown["buyer_premium"])))
    if premium_cents > 0:
        rate_pct = round(breakdown["buyer_premium_rate"] * 100, 1)
        desc = "100% transferred to Partner seller" if is_partner else "BidVex service fee based on subscription tier"
        items.append({
            "price_data": {
                "currency": currency,
                "unit_amount": premium_cents,
                "product_data": {
                    "name": f"Buyer Premium ({rate_pct}%)",
                    "description": desc,
                },
            },
            "quantity": 1,
        })

    # 3. Platform Fee (vehicles only — explicitly charged to buyer; for general it's internal)
    if is_vehicle:
        platform_fee_cents = _to_cents(Decimal(str(breakdown["platform_fee"])))
        if platform_fee_cents > 0:
            pf_rate = round(breakdown.get("platform_fee_rate", 0.025) * 100, 1)
            items.append({
                "price_data": {
                    "currency": currency,
                    "unit_amount": platform_fee_cents,
                    "product_data": {
                        "name": f"Platform Fee ({pf_rate}%)",
                        "description": "BidVex vehicle transaction fee",
                    },
                },
                "quantity": 1,
            })

    # 4. GST (5% Federal) — on (Hammer + Premium)
    gst_cents = _to_cents(Decimal(str(breakdown["gst"])))
    if gst_cents > 0:
        items.append({
            "price_data": {
                "currency": currency,
                "unit_amount": gst_cents,
                "product_data": {
                    "name": "GST (TPS 5%)",
                    "description": f"Federal Goods & Services Tax — GST# {os.environ.get('PLATFORM_GST_NUMBER', '')}",
                },
            },
            "quantity": 1,
        })

    # 5. QST (9.975% Quebec) — on (Hammer + Premium)
    qst_cents = _to_cents(Decimal(str(breakdown["qst"])))
    if qst_cents > 0:
        items.append({
            "price_data": {
                "currency": currency,
                "unit_amount": qst_cents,
                "product_data": {
                    "name": "QST (TVQ 9.975%)",
                    "description": f"Quebec Sales Tax — QST# {os.environ.get('PLATFORM_QST_NUMBER', '')}",
                },
            },
            "quantity": 1,
        })

    # 6. Stripe Processing Fee (STANDARD flow only — Partners absorb this)
    if not is_partner:
        stripe_fee_cents = _to_cents(Decimal(str(breakdown["stripe_processing_fee"])))
        if stripe_fee_cents > 0:
            items.append({
                "price_data": {
                    "currency": currency,
                    "unit_amount": stripe_fee_cents,
                    "product_data": {
                        "name": "Payment Processing Fee",
                        "description": "Credit card processing (2.9% + $0.30)",
                    },
                },
                "quantity": 1,
            })

    # 7. Late Penalty (if applicable)
    if late_penalty > 0:
        penalty_cents = _to_cents(Decimal(str(late_penalty)))
        items.append({
            "price_data": {
                "currency": currency,
                "unit_amount": penalty_cents,
                "product_data": {
                    "name": "Late Payment Penalty",
                    "description": "2% per month overdue",
                },
            },
            "quantity": 1,
        })

    return items


async def create_connect_checkout_session(
    db,
    buyer_id: str,
    listing: Dict[str, Any],
    breakdown: Dict[str, Any],
    success_url: str,
    cancel_url: str,
    payment_type: str = "auction_purchase",
    metadata_extra: Optional[Dict[str, str]] = None,
    late_penalty: float = 0.0,
    idempotency_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Create a Stripe Checkout Session with Connect (application_fee + transfer_data).
    Uses itemized line items so GST/QST appear as separate rows (Quebec compliance).
    Includes transfer_group for affiliate payouts.
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

    listing_title = listing.get("title", "Auction Purchase")
    category = listing.get("category", "general").lower()
    is_vehicle = any(kw in category for kw in ("vehicle", "car", "auto", "truck", "motorcycle"))

    # Build itemized line items (GST/QST as separate rows)
    line_items = build_itemized_line_items(
        breakdown=breakdown,
        listing_title=listing_title,
        late_penalty=late_penalty,
        is_vehicle=is_vehicle,
    )

    # Check if the seller was referred (affiliate tracking)
    affiliate_id = seller.get("referred_by") if seller else None

    # Build metadata
    flow_type = breakdown.get("flow_type", "STANDARD_FLOW")

    import uuid as _uuid
    transfer_group = f"tg_{listing.get('id', '')}_{str(_uuid.uuid4())[:8]}"

    meta = {
        "user_id": buyer_id,
        "listing_id": listing.get("id", ""),
        "item_id": listing.get("id", ""),
        "seller_id": seller_id or "",
        "transaction_type": payment_type,
        "type": payment_type,
        "flow_type": flow_type,
        "transfer_group": transfer_group,
        "hammer_price": str(breakdown["hammer_price"]),
        "platform_fee": str(breakdown["platform_fee"]),
        "buyer_premium": str(breakdown["buyer_premium"]),
        "seller_commission": str(breakdown["seller_commission"]),
        "gst": str(breakdown["gst"]),
        "qst": str(breakdown["qst"]),
        "stripe_fee_estimate": str(breakdown.get("stripe_processing_fee", 0)),
        "subtotal": str(round(
            float(breakdown["hammer_price"])
            + float(breakdown["buyer_premium"])
            + float(breakdown["gst"])
            + float(breakdown["qst"]),
            2,
        )),
        "late_penalty": str(late_penalty),
    }
    if affiliate_id:
        meta["affiliate_id"] = affiliate_id
    if metadata_extra:
        meta.update(metadata_extra)

    # Application fee includes late penalty (BidVex keeps it)
    app_fee_cents = breakdown["application_fee_cents"]
    if late_penalty > 0:
        app_fee_cents += _to_cents(Decimal(str(late_penalty)))

    # Build session params
    session_params = {
        "customer": customer_id,
        "payment_method_types": ["card"],
        "mode": "payment",
        "line_items": line_items,
        "success_url": success_url,
        "cancel_url": cancel_url,
        "metadata": meta,
    }

    # If seller has Connect account, split the payment
    if connect_account_id and not is_vehicle:
        session_params["payment_intent_data"] = {
            "application_fee_amount": app_fee_cents,
            "transfer_data": {"destination": connect_account_id},
            "transfer_group": transfer_group,
            "metadata": meta,
        }
    else:
        # No Connect account or vehicle — BidVex collects everything
        session_params["payment_intent_data"] = {
            "transfer_group": transfer_group,
            "metadata": meta,
        }

    # Enable Stripe Radar for high-value transactions
    if breakdown["hammer_price"] >= 5000:
        session_params["payment_intent_data"]["statement_descriptor_suffix"] = "BIDVEX"

    create_kwargs = {}
    if idempotency_key:
        create_kwargs["idempotency_key"] = idempotency_key

    session = stripe.checkout.Session.create(**session_params, **create_kwargs)

    total_cents = breakdown["buyer_total_cents"]
    if late_penalty > 0:
        total_cents += _to_cents(Decimal(str(late_penalty)))

    return {
        "session_id": session.id,
        "checkout_url": session.url,
        "breakdown": breakdown,
        "total_cents": total_cents,
        "late_penalty": late_penalty,
        "transfer_group": transfer_group,
        "affiliate_id": affiliate_id,
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
    from services.stripe_circuit_breaker import safe_stripe_call_blocking
    intent = await safe_stripe_call_blocking(
        lambda: stripe.PaymentIntent.create(
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
        ),
        operation_name="bidding_deposit_payment_intent_create",
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
    buyer_province: str = "QC",
) -> Dict[str, Any]:
    """Create a Stripe Checkout for listing promotion purchase with jurisdiction-aware tax."""
    from services.pricing_manager import PricingManager

    promo = PROMOTION_TIERS.get(tier)
    if not promo:
        raise ValueError(f"Invalid promotion tier: {tier}")

    base_cents = promo["price_cents"]
    base_dollars = Decimal(str(base_cents)) / 100

    pricing = PricingManager.flat_purchase(float(base_dollars), buyer_province, f"BidVex {promo['label']}")
    pi = pricing.buyer_invoice

    stripe_cents = _to_cents(Decimal(str(pi.stripe_recovery)))
    tax_cents = _to_cents(Decimal(str(pi.tax_amount)))

    line_items = [
        {
            "price_data": {
                "currency": "cad",
                "unit_amount": base_cents,
                "product_data": {
                    "name": f"BidVex {promo['label']}",
                    "description": f"{promo['duration_days']}-day listing boost: {', '.join(promo['features'])}",
                },
            },
            "quantity": 1,
        },
    ]
    if stripe_cents > 0:
        line_items.append({
            "price_data": {
                "currency": "cad",
                "unit_amount": stripe_cents,
                "product_data": {"name": "Stripe Processing Fee", "description": "Payment processing fee recovery"},
            },
            "quantity": 1,
        })
    if tax_cents > 0:
        line_items.append({
            "price_data": {
                "currency": "cad",
                "unit_amount": tax_cents,
                "product_data": {"name": f"Tax — {pi.tax_label}", "description": f"{pi.tax_type} — GST# {os.environ.get('PLATFORM_GST_NUMBER', '')}"},
            },
            "quantity": 1,
        })

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="payment",
        line_items=line_items,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "type": "listing_promotion",
            "user_id": user_id,
            "listing_id": listing_id,
            "promotion_tier": tier,
            "duration_days": str(promo["duration_days"]),
            "transaction_type": "promotion",
            "tax_type": pi.tax_type,
            "tax_label": pi.tax_label,
            "buyer_province": buyer_province,
        },
    )
    return {
        "session_id": session.id,
        "checkout_url": session.url,
        "tier": tier,
        "price": base_cents / 100,
        "stripe_recovery": float(pi.stripe_recovery),
        "tax": float(pi.tax_amount),
        "tax_type": pi.tax_type,
        "tax_label": pi.tax_label,
        "total": float(pi.total),
    }


def create_email_credits_checkout(
    customer_id: str,
    user_id: str,
    quantity: int,
    success_url: str,
    cancel_url: str,
    buyer_province: str = "QC",
) -> Dict[str, Any]:
    """Create a Stripe Checkout for email marketing credits with jurisdiction-aware tax."""
    from services.pricing_manager import PricingManager

    total_cents = calculate_email_credit_cost(quantity)
    per_email = total_cents / quantity if quantity > 0 else 0
    base_dollars = Decimal(str(total_cents)) / 100

    pricing = PricingManager.flat_purchase(float(base_dollars), buyer_province, f"BidVex Email Credits ({quantity:,})")
    pi = pricing.buyer_invoice

    stripe_cents = _to_cents(Decimal(str(pi.stripe_recovery)))
    tax_cents = _to_cents(Decimal(str(pi.tax_amount)))

    line_items = [
        {
            "price_data": {
                "currency": "cad",
                "unit_amount": total_cents,
                "product_data": {
                    "name": f"BidVex Email Credits ({quantity:,})",
                    "description": f"{quantity:,} email credits at ~${per_email/100:.3f}/email",
                },
            },
            "quantity": 1,
        },
    ]
    if stripe_cents > 0:
        line_items.append({
            "price_data": {
                "currency": "cad",
                "unit_amount": stripe_cents,
                "product_data": {"name": "Stripe Processing Fee", "description": "Payment processing fee recovery"},
            },
            "quantity": 1,
        })
    if tax_cents > 0:
        line_items.append({
            "price_data": {
                "currency": "cad",
                "unit_amount": tax_cents,
                "product_data": {"name": f"Tax — {pi.tax_label}", "description": f"{pi.tax_type} — GST# {os.environ.get('PLATFORM_GST_NUMBER', '')}"},
            },
            "quantity": 1,
        })

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        mode="payment",
        line_items=line_items,
        success_url=success_url,
        cancel_url=cancel_url,
        metadata={
            "type": "email_credits",
            "user_id": user_id,
            "credit_quantity": str(quantity),
            "transaction_type": "email_credits",
            "tax_type": pi.tax_type,
            "tax_label": pi.tax_label,
            "buyer_province": buyer_province,
        },
    )
    grand_total_cents = total_cents + stripe_cents + tax_cents
    return {
        "session_id": session.id,
        "checkout_url": session.url,
        "quantity": quantity,
        "total_cents": grand_total_cents,
        "subtotal_cents": total_cents,
        "stripe_recovery": float(pi.stripe_recovery),
        "tax": float(pi.tax_amount),
        "tax_type": pi.tax_type,
        "tax_label": pi.tax_label,
    }


async def process_affiliate_payout(
    db,
    session_metadata: Dict[str, str],
    payment_intent_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Process affiliate cash-back payout using Stripe Transfer.
    Called from webhook after a successful checkout on a referred seller's listing.

    Calculates 15% of BidVex's commission and transfers it to the affiliate's
    Connect account within the same transfer_group.
    """
    affiliate_id = session_metadata.get("affiliate_id")
    if not affiliate_id:
        return None

    transfer_group = session_metadata.get("transfer_group")
    flow_type = session_metadata.get("flow_type", "STANDARD_FLOW")

    # Look up the affiliate user
    affiliate = await db.users.find_one({"id": affiliate_id})
    if not affiliate:
        logger.warning(f"Affiliate user not found: {affiliate_id}")
        return None

    affiliate_connect_id = affiliate.get("stripe_connect_account_id")

    # Calculate BidVex's commission (what we can share from)
    seller_commission = float(session_metadata.get("seller_commission", "0"))
    buyer_premium = float(session_metadata.get("buyer_premium", "0"))

    if flow_type == "PARTNER_FLOW":
        # Partner flow: BidVex only keeps seller commission
        bidvex_revenue = seller_commission
    else:
        # Standard flow: BidVex keeps both
        bidvex_revenue = buyer_premium + seller_commission

    # Affiliate gets 15% of BidVex's revenue
    affiliate_payout = round(bidvex_revenue * float(AFFILIATE_COMMISSION_RATE), 2)
    affiliate_payout_cents = int(round(affiliate_payout * 100))

    if affiliate_payout_cents <= 0:
        return None

    # Record the affiliate payout
    from datetime import datetime, timezone
    import uuid

    payout_record = {
        "id": str(uuid.uuid4()),
        "affiliate_id": affiliate_id,
        "seller_id": session_metadata.get("seller_id", ""),
        "listing_id": session_metadata.get("listing_id", ""),
        "payment_intent_id": payment_intent_id,
        "transfer_group": transfer_group,
        "flow_type": flow_type,
        "bidvex_revenue": bidvex_revenue,
        "affiliate_rate": float(AFFILIATE_COMMISSION_RATE),
        "affiliate_payout": affiliate_payout,
        "affiliate_payout_cents": affiliate_payout_cents,
        "status": "pending",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if affiliate_connect_id:
        # Execute the Stripe Transfer immediately
        try:
            transfer = stripe.Transfer.create(
                amount=affiliate_payout_cents,
                currency=session_metadata.get("currency", "cad").lower(),
                destination=affiliate_connect_id,
                transfer_group=transfer_group,
                metadata={
                    "affiliate_id": affiliate_id,
                    "seller_id": session_metadata.get("seller_id", ""),
                    "listing_id": session_metadata.get("listing_id", ""),
                    "type": "affiliate_cashback",
                },
                description=f"BidVex Affiliate Cash-Back — Listing {session_metadata.get('listing_id', '')}",
            )
            payout_record["stripe_transfer_id"] = transfer.id
            payout_record["status"] = "transferred"
            logger.info(f"Affiliate payout: ${affiliate_payout:.2f} to {affiliate_id} via transfer {transfer.id}")
        except stripe.StripeError as e:
            payout_record["status"] = "failed"
            payout_record["error"] = str(e)
            logger.error(f"Affiliate payout failed: {e}")
    else:
        # Credit to internal balance (no Connect account)
        await db.users.update_one(
            {"id": affiliate_id},
            {"$inc": {"affiliate_balance": affiliate_payout}},
        )
        payout_record["status"] = "credited_internally"
        logger.info(f"Affiliate payout: ${affiliate_payout:.2f} credited to {affiliate_id} internal balance")

    await db.affiliate_payouts.insert_one(payout_record)
    return payout_record
