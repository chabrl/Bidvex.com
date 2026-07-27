"""
iter397 — Broker annual-fee self-checkout.

Endpoints:
  POST /api/broker-subscription/create-checkout-session
      Broker-facing: create a hosted Stripe Checkout Session that lets
      the caller pay their annual membership. The Stripe Product,
      Price, and LAUNCH50_BRK coupon are sourced from
      `services.pricing_engine_service` (key = "broker_annual_fee") so
      admin edits at `/api/admin/pricing-engine/broker_annual_fee`
      flow through automatically. The launch-window coupon is applied
      when `is_within_launch_window` is True.

  GET  /api/broker-subscription/status
      Broker-facing: subscription state (active / expires_at / etc.).
      Mirrors `/api/brokers/me/subscription` but tightens the "is
      already paid" idempotency signal used by the checkout endpoint.

Design notes:
  * Idempotency — if the broker's `subscription_status == "active"` and
    `subscription_expires_at` is in the future, we return
    `{"already_active": True, ...}` instead of creating a new session.
  * Demo accounts are refused (matches dealer-subscription behavior).
  * Success/cancel URLs deep-link back to /broker/dashboard with a
    `broker_fee=success|cancelled` query flag the dashboard reacts to.
  * Webhook activation is implemented in `routes/webhooks.py`
    (session_type == "broker_annual_fee") and stamps:
        subscription_status: "active"
        subscription_started_at, subscription_expires_at (+365d)
        subscription_stripe_session_id
        subscription_stripe_subscription_id
        subscription_stripe_customer_id
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import stripe
from fastapi import APIRouter, Depends, HTTPException

from deps import get_current_user, get_db, User

logger = logging.getLogger(__name__)
broker_subscription_router = APIRouter(tags=["Broker Subscription"])


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def _get_broker_or_404(db, user_id: str) -> dict:
    broker = await db.brokers.find_one({"user_id": user_id}, {"_id": 0})
    if not broker:
        raise HTTPException(status_code=403, detail={"error": "not_a_broker"})
    return broker


def _is_active(broker: dict) -> bool:
    if (broker.get("subscription_status") or "unpaid") != "active":
        return False
    exp = broker.get("subscription_expires_at")
    if isinstance(exp, str):
        try:
            exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        except Exception:  # noqa: BLE001
            return False
    if isinstance(exp, datetime):
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        return exp > _utcnow()
    # No expiry stored yet — treat as inactive so the broker can pay.
    return False


@broker_subscription_router.post("/broker-subscription/create-checkout-session")
async def create_broker_checkout_session(current_user: User = Depends(get_current_user)):
    """Create a hosted Stripe Checkout Session for the broker's annual
    membership. Uses `pricing_engine_service` for Product/Price/Coupon.

    Returns:
      * `{ "already_active": true, "expires_at": ISO }` — subscription is
        still valid; no new session created.
      * `{ "checkout_url": str, "session_id": str, "final_cad": float,
           "base_cad": float, "discount_applied": bool }` on success.
    """
    db = get_db()
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0}) or {}

    # Demo-account isolation (matches dealer flow).
    if user_doc.get("is_demo_account") is True:
        raise HTTPException(status_code=403, detail="demo_mode_payments_disabled")

    broker = await _get_broker_or_404(db, current_user.id)

    if _is_active(broker):
        return {
            "already_active": True,
            "expires_at": (
                broker.get("subscription_expires_at").isoformat()
                if hasattr(broker.get("subscription_expires_at"), "isoformat")
                else broker.get("subscription_expires_at")
            ),
        }

    # ── Resolve Stripe Price + LAUNCH50_BRK coupon from pricing_engine ──
    from services.pricing_engine_service import (
        update_pricing as _pe_update,
        is_within_launch_window as _pe_in_window,
        effective_price as _pe_effective,
    )
    settings = await _pe_update(db, "broker_annual_fee")
    price_id = settings["stripe_price_id"]
    coupon_id = settings.get("stripe_coupon_id")
    in_window = _pe_in_window(settings)

    # ── Ensure a Stripe Customer exists ──
    stripe.api_key = os.environ.get("STRIPE_API_KEY")
    customer_id = user_doc.get("stripe_customer_id")
    if not customer_id:
        cust = stripe.Customer.create(
            email=current_user.email,
            name=current_user.name,
            metadata={"user_id": current_user.id, "type": "broker"},
        )
        customer_id = cust.id
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"stripe_customer_id": customer_id}},
        )

    frontend_url = os.environ.get("REACT_APP_BACKEND_URL", "https://www.bidvex.com")
    session_kwargs = dict(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        # Stripe rejects `allow_promotion_codes` + `discounts` simultaneously.
        # We attach the launch coupon programmatically when eligible.
        success_url=f"{frontend_url}/broker/dashboard?broker_fee=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{frontend_url}/broker/dashboard?broker_fee=cancelled",
        metadata={
            "type":       "broker_annual_fee",
            "user_id":    current_user.id,
            "broker_id":  broker["id"],
        },
        subscription_data={
            "metadata": {
                "type":      "broker_annual_fee",
                "user_id":   current_user.id,
                "broker_id": broker["id"],
            },
        },
    )
    discount_applied = False
    if in_window and coupon_id:
        session_kwargs["discounts"] = [{"coupon": coupon_id}]
        discount_applied = True

    try:
        session = stripe.checkout.Session.create(**session_kwargs)
    except stripe.StripeError as e:  # noqa: BLE001
        logger.error(f"[broker-checkout] Stripe error for user={current_user.id}: {e}")
        raise HTTPException(status_code=502, detail={"error": "stripe_checkout_failed", "message": str(e)})

    # Record the pending checkout on the broker doc so admins can see
    # who is mid-flight.
    await db.brokers.update_one(
        {"id": broker["id"]},
        {"$set": {
            "subscription_stripe_session_id": session.id,
            "subscription_checkout_created_at": _utcnow(),
            "subscription_stripe_customer_id": customer_id,
        }},
    )

    base_cad = float(settings.get("base_price_cad") or 0)
    final_cad = _pe_effective(settings) if discount_applied else base_cad

    return {
        "checkout_url":     session.url,
        "session_id":       session.id,
        "base_cad":         round(base_cad, 2),
        "final_cad":        round(final_cad, 2),
        "discount_applied": discount_applied,
        "coupon_id":        coupon_id if discount_applied else None,
    }


@broker_subscription_router.get("/broker-subscription/status")
async def my_broker_subscription_status(current_user: User = Depends(get_current_user)):
    """Broker-facing subscription status. Used by BrokerDashboardPage
    to decide whether to show the Pay Now CTA."""
    db = get_db()
    broker = await _get_broker_or_404(db, current_user.id)
    active = _is_active(broker)
    return {
        "broker_id":                broker["id"],
        "subscription_status":      broker.get("subscription_status") or "unpaid",
        "active":                   active,
        "expires_at":               (
            broker.get("subscription_expires_at").isoformat()
            if hasattr(broker.get("subscription_expires_at"), "isoformat")
            else broker.get("subscription_expires_at")
        ),
        "started_at":               (
            broker.get("subscription_started_at").isoformat()
            if hasattr(broker.get("subscription_started_at"), "isoformat")
            else broker.get("subscription_started_at")
        ),
        "stripe_subscription_id":   broker.get("subscription_stripe_subscription_id"),
    }
