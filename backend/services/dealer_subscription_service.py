"""
iter209 Step 6 — Vehicle Dealer Annual $100 CAD Stripe Subscription

Idempotent bootstrap of:
  * Stripe Product:  "BidVex Vehicle Dealer Platform Access"
  * Stripe Price:    $200/year CAD recurring
  * Stripe Coupon:   LAUNCH50 (50% off, duration=forever)
  * stripe_settings MongoDB collection caches Product.id / Price.id / Coupon.id
    so subsequent restarts re-use them instead of creating new ones.

Functions:
  * bootstrap_dealer_subscription_objects(db)        → returns dict of cached IDs
  * create_dealer_subscription(db, user, payment_method_id) → Subscription.create with LAUNCH50 applied
  * get_dealer_subscription_status(db, user_id)       → dict for admin UI
  * suspend_dealer_for_failed_payment(db, user_id)    → hides listings + emails dealer

All public callers must obtain `STRIPE_API_KEY` from environment; no fallback.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

import stripe

logger = logging.getLogger(__name__)
stripe.api_key = os.environ.get("STRIPE_API_KEY")

PRODUCT_NAME = "BidVex Vehicle Dealer Platform Access"
PRICE_UNIT_AMOUNT_CENTS = 20_000      # $200.00 CAD/year (50% LAUNCH coupon → $100 effective)
PRICE_CURRENCY = "cad"
PRICE_INTERVAL = "year"
COUPON_ID = "LAUNCH50"                # idempotency key in our own collection
COUPON_PERCENT_OFF = 50.0

GRACE_PERIOD_DAYS = 7


async def _get_or_create_settings(db) -> dict:
    """Return the cached dealer-subscription Stripe IDs, creating them if missing."""
    doc = await db.stripe_settings.find_one({"id": "vehicle_dealer_subscription"}, {"_id": 0}) or {}
    product_id = doc.get("product_id")
    price_id = doc.get("price_id")
    coupon_id = doc.get("coupon_id")

    # 1) Product ─ idempotent by metadata lookup
    if not product_id:
        existing = stripe.Product.list(limit=100)
        for p in existing.data:
            if p.metadata.get("bidvex_role") == "vehicle_dealer_subscription":
                product_id = p.id
                break
        if not product_id:
            p = stripe.Product.create(
                name=PRODUCT_NAME,
                metadata={"bidvex_role": "vehicle_dealer_subscription"},
            )
            product_id = p.id

    # 2) Price ─ recurring yearly
    if not price_id:
        prices = stripe.Price.list(product=product_id, limit=100)
        for pr in prices.data:
            r = pr.recurring or {}
            if (pr.unit_amount == PRICE_UNIT_AMOUNT_CENTS and pr.currency == PRICE_CURRENCY
                    and r.get("interval") == PRICE_INTERVAL and pr.active):
                price_id = pr.id
                break
        if not price_id:
            pr = stripe.Price.create(
                product=product_id,
                unit_amount=PRICE_UNIT_AMOUNT_CENTS,
                currency=PRICE_CURRENCY,
                recurring={"interval": PRICE_INTERVAL},
                metadata={"bidvex_role": "vehicle_dealer_subscription"},
            )
            price_id = pr.id

    # 3) Coupon LAUNCH50 ─ 50% off forever
    if not coupon_id:
        try:
            existing_coupon = stripe.Coupon.retrieve(COUPON_ID)
            coupon_id = existing_coupon.id
        except stripe.InvalidRequestError:
            c = stripe.Coupon.create(
                id=COUPON_ID,
                percent_off=COUPON_PERCENT_OFF,
                duration="forever",
                name="BidVex Launch 50% Discount",
                metadata={"bidvex_role": "vehicle_dealer_subscription"},
            )
            coupon_id = c.id

    # Persist
    await db.stripe_settings.update_one(
        {"id": "vehicle_dealer_subscription"},
        {"$set": {
            "id": "vehicle_dealer_subscription",
            "product_id": product_id,
            "price_id": price_id,
            "coupon_id": coupon_id,
            "updated_at": datetime.now(timezone.utc),
        }},
        upsert=True,
    )
    return {"product_id": product_id, "price_id": price_id, "coupon_id": coupon_id}


async def bootstrap_dealer_subscription_objects(db) -> dict:
    """Idempotent bootstrap — safe to call on every startup."""
    return await _get_or_create_settings(db)


async def _ensure_customer(db, user_id: str, user_email: Optional[str], user_name: Optional[str]) -> str:
    doc = await db.users.find_one({"id": user_id}, {"_id": 0, "stripe_customer_id": 1, "email": 1, "name": 1})
    if not doc:
        raise ValueError("user_not_found")
    cust = doc.get("stripe_customer_id")
    if cust:
        return cust
    c = stripe.Customer.create(
        email=user_email or doc.get("email"),
        name=user_name or doc.get("name"),
        metadata={"bidvex_user_id": user_id, "role": "vehicle_dealer"},
    )
    await db.users.update_one({"id": user_id}, {"$set": {"stripe_customer_id": c.id}})
    return c.id


async def create_dealer_subscription(
    db,
    *,
    user_id: str,
    user_email: Optional[str] = None,
    user_name: Optional[str] = None,
    payment_method_id: Optional[str] = None,
    apply_launch_discount: Optional[bool] = None,
) -> dict:
    """Create a recurring annual subscription for a vehicle dealer.

    iter210 Step 3: consults `pricing_engine_service` for the live price/coupon
    and applies the launch coupon iff `is_within_launch_window` is True.
    Callers can override `apply_launch_discount` explicitly (used by tests).
    """
    # Read live pricing — auto-creates Stripe Product/Price/Coupon on first call
    from services.pricing_engine_service import update_pricing, is_within_launch_window
    settings = await update_pricing(db, "vehicle_dealer_annual_fee")
    customer_id = await _ensure_customer(db, user_id, user_email, user_name)

    if payment_method_id:
        try:
            stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)
        except stripe.StripeError as e:
            logger.warning(f"[iter209] PM attach (sub) no-op: {e}")
        stripe.Customer.modify(customer_id, invoice_settings={"default_payment_method": payment_method_id})

    sub_kwargs = {
        "customer": customer_id,
        "items": [{"price": settings["stripe_price_id"]}],
        "expand": ["latest_invoice.payment_intent"],
        "metadata": {"bidvex_user_id": user_id, "kind": "vehicle_dealer_annual"},
    }
    # Should the launch coupon apply? Admin can override per-call (apply_launch_discount=True)
    if apply_launch_discount is None:
        apply_launch_discount = is_within_launch_window(settings)
    if apply_launch_discount and settings.get("stripe_coupon_id"):
        sub_kwargs["discounts"] = [{"coupon": settings["stripe_coupon_id"]}]

    sub = stripe.Subscription.create(**sub_kwargs)

    # Persist subscription metadata on the user
    update = {
        "vehicle_dealer_subscription_id": sub.id,
        "vehicle_dealer_subscription_status": sub.status,
        "vehicle_dealer_subscription_current_period_end": (
            datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc)
            if hasattr(sub, "current_period_end") and sub.current_period_end else None
        ),
        "vehicle_dealer_subscription_started_at": datetime.now(timezone.utc),
        "vehicle_dealer_subscription_price_id": settings["stripe_price_id"],
    }
    await db.users.update_one({"id": user_id}, {"$set": update})

    return {
        "subscription_id": sub.id,
        "status": sub.status,
        "current_period_end": update["vehicle_dealer_subscription_current_period_end"],
        "latest_invoice_id": sub.latest_invoice.id if sub.latest_invoice else None,
        "client_secret": (
            sub.latest_invoice.payment_intent.client_secret
            if sub.latest_invoice and getattr(sub.latest_invoice, "payment_intent", None)
            else None
        ),
    }


async def get_dealer_subscription_status(db, user_id: str) -> dict:
    """Surface subscription info for the Admin panel."""
    doc = await db.users.find_one(
        {"id": user_id},
        {"_id": 0,
         "vehicle_dealer_subscription_id": 1,
         "vehicle_dealer_subscription_status": 1,
         "vehicle_dealer_subscription_current_period_end": 1,
         "vehicle_dealer_subscription_started_at": 1},
    ) or {}
    sub_id = doc.get("vehicle_dealer_subscription_id")
    if not sub_id:
        return {"has_subscription": False}

    # Fetch live from Stripe for source-of-truth status + period end
    try:
        sub = stripe.Subscription.retrieve(sub_id)
        return {
            "has_subscription": True,
            "subscription_id": sub.id,
            "status": sub.status,
            "current_period_end": (
                datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc).isoformat()
                if hasattr(sub, "current_period_end") and sub.current_period_end else None
            ),
            "cancel_at_period_end": sub.cancel_at_period_end,
            "discount_active": bool(sub.discount),
            "started_at": (doc.get("vehicle_dealer_subscription_started_at").isoformat()
                           if doc.get("vehicle_dealer_subscription_started_at") else None),
        }
    except stripe.StripeError as e:
        logger.warning(f"[iter209] Subscription.retrieve failed for {sub_id}: {e}")
        return {"has_subscription": True, "subscription_id": sub_id, "status": doc.get("vehicle_dealer_subscription_status"), "error": str(e)}


async def suspend_dealer_for_failed_payment(db, user_id: str, *, reason: str = "annual_fee_failed") -> dict:
    """Hide all the dealer's active listings + flag the user.

    Called by the Stripe `invoice.payment_failed` webhook after 7-day grace.
    """
    now = datetime.now(timezone.utc)
    # Flag user
    await db.users.update_one({"id": user_id}, {"$set": {
        "vehicle_dealer_suspended": True,
        "vehicle_dealer_suspended_reason": reason,
        "vehicle_dealer_suspended_at": now,
    }})
    # Hide listings
    seller = await db.vehicle_sellers.find_one({"user_id": user_id}, {"_id": 0, "id": 1})
    if seller:
        await db.vehicles.update_many(
            {"seller_id": seller["id"], "status": {"$in": ["active", "live"]}},
            {"$set": {"status": "suspended", "suspended_reason": reason, "suspended_at": now}},
        )
    return {"success": True, "suspended_at": now.isoformat()}
