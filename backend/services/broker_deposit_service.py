"""
iter217 Phase 5 Hotfix v5b — Broker deposit (Stripe pre-authorization).

Creates / releases / captures the refundable security deposit a buyer
must authorize before a broker partnership becomes active. All Stripe
calls use `capture_method="manual"` so the card is only ever HELD
(pre-authorized), never charged, until the broker explicitly captures.

Deposit lifecycle:
    "pending"  → buyer triggered the binding flow but no PI exists
    "held"     → PI created with capture_method=manual, status=requires_capture
    "released" → PI cancelled (no charge ever hit the card)
    "captured" → broker captured the deposit on buyer default
    "refunded" → captured then refunded
    "failed"   → PI failed authorization
"""
from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

import stripe

logger = logging.getLogger("broker_deposit")
stripe.api_key = os.environ.get("STRIPE_API_KEY")

DEFAULT_DEPOSIT_CAD = 500.0


def _to_minor(amount_cad: float) -> int:
    return int(round(float(amount_cad) * 100))


def authorize_deposit(
    *,
    amount_cad:          float,
    customer_email:      Optional[str],
    payment_method_id:   Optional[str],
    relationship_id:     str,
    broker_id:           str,
    buyer_user_id:       str,
) -> Dict[str, Any]:
    """Creates a manual-capture PaymentIntent that HOLDS the deposit.

    Returns a dict with `payment_intent_id`, `client_secret`, `status`.
    If `payment_method_id` is provided the PI is confirmed immediately
    (no further client interaction needed). If not, the client must
    confirm with `stripe.confirmCardPayment(client_secret)`.
    """
    kwargs: Dict[str, Any] = {
        "amount":          _to_minor(amount_cad),
        "currency":        "cad",
        "capture_method":  "manual",
        "automatic_payment_methods": {"enabled": True, "allow_redirects": "never"},
        "description":     f"BidVex broker deposit (hold) — relationship {relationship_id}",
        "metadata": {
            "kind":            "broker_deposit",
            "relationship_id": relationship_id,
            "broker_id":       broker_id,
            "buyer_user_id":   buyer_user_id,
        },
        "receipt_email":   customer_email,
    }
    if payment_method_id:
        kwargs["payment_method"] = payment_method_id
        kwargs["confirm"]        = True

    pi = stripe.PaymentIntent.create(**kwargs)
    logger.info("broker_deposit authorized PI=%s status=%s rel=%s", pi.id, pi.status, relationship_id)
    return {
        "payment_intent_id": pi.id,
        "client_secret":     pi.client_secret,
        "status":            pi.status,
    }


def release_deposit(payment_intent_id: str) -> Dict[str, Any]:
    """Cancels the held PaymentIntent — releases the hold without ever charging."""
    pi = stripe.PaymentIntent.cancel(payment_intent_id)
    logger.info("broker_deposit released PI=%s status=%s", pi.id, pi.status)
    return {"payment_intent_id": pi.id, "status": pi.status}


def capture_deposit(payment_intent_id: str, amount_cad: Optional[float] = None) -> Dict[str, Any]:
    """Captures (charges) the held PaymentIntent. Optionally captures a
    PARTIAL amount."""
    kwargs: Dict[str, Any] = {}
    if amount_cad is not None:
        kwargs["amount_to_capture"] = _to_minor(amount_cad)
    pi = stripe.PaymentIntent.capture(payment_intent_id, **kwargs)
    logger.info("broker_deposit captured PI=%s status=%s amount=%s", pi.id, pi.status, amount_cad)
    return {"payment_intent_id": pi.id, "status": pi.status, "amount_captured": pi.amount_received}
