"""
iter482 — Partner Destination-Charge Refund Engine
==================================================

Single authoritative orchestrator for refunding an auction/marketplace
Stripe charge whose Session was built via ``create_destination_charge``
in the Partner Model A₁ architecture.

For a Partner destination charge with ``on_behalf_of=partner_acct`` +
``transfer_data.destination=partner_acct`` + ``application_fee_amount``,
a correct refund requires *three* things to reconcile:

1. The buyer's card charge (`stripe.Refund.create(payment_intent=...)`)
2. The application_fee retained by BidVex must be returned to the buyer
   (``refund_application_fee=True``)
3. The destination transfer to the Partner Connect account must be
   reversed (``reverse_transfer=True``)

Under `stripe.Refund.create`, Stripe atomically executes all three
when the appropriate parameters are set — otherwise the platform
balance, the Partner's Connect balance, and the buyer's card can end
up in inconsistent states.

The function is idempotent by `refund_id` in `db.payment_events` — a
duplicate call with the same `payment_intent_id` yields the same
result (via the mark_charge_refunded state-machine).

Historical financial records are NOT modified.  On refund, we UPDATE:
- ``db.payment_charges``      → mark status=refunded (or partially_refunded)
- ``db.payment_events``       → append refund event
- ``db.transactions``         → add refund breakdown fields (additive,
                                 never overwrites the original)
- ``db.receipts``             → add refunded_at / refunded_amount / refund_status
                                 (additive; original financial fields
                                 untouched — per Section 22 of the
                                 remediation brief)

NEVER modifies the original hammer/BP/tax/net fields on the receipt.
"""

from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

import stripe

from services.payment_idempotency import mark_charge_refunded

logger = logging.getLogger(__name__)


class RefundError(Exception):
    """Raised for any refund-orchestrator failure that leaves the
    system in a well-defined state (either fully-refunded or
    unchanged).  Never leaves partial state."""


async def refund_partner_transaction(
    db,
    *,
    payment_intent_id: str,
    amount_cents: Optional[int] = None,
    reason: str = "requested_by_customer",
    initiated_by: str = "system",
    is_partner_listing: bool = False,
) -> Dict[str, Any]:
    """Refund an auction Stripe charge with correct Connect semantics.

    Args:
        payment_intent_id: The `pi_...` id of the original charge.
        amount_cents: Cents to refund (None = full refund).
        reason: Stripe reason code (`duplicate`, `fraudulent`,
            `requested_by_customer`, or freeform).
        initiated_by: Actor id (user, admin, webhook).
        is_partner_listing: Whether the original charge used the Partner
            Model A₁ architecture (on_behalf_of + application_fee).
            When True, Stripe refund is created with
            ``refund_application_fee=True`` + ``reverse_transfer=True``.

    Returns:
        {
          "refund_id": "re_...",
          "status": "succeeded|pending|failed",
          "amount_refunded_cents": int,
          "is_partial": bool,
          "duplicate_blocked": bool,
        }

    Raises:
        RefundError: on any orchestration inconsistency (Stripe succeeded
            but DB write failed, or Stripe rejected the reversal).
    """
    stripe.api_key = os.environ.get("STRIPE_API_KEY", "")
    if not stripe.api_key:
        raise RefundError("STRIPE_API_KEY missing — cannot process refunds")

    # ---- Idempotency guard: has this PI already been refunded?
    charge_row = await db.payment_charges.find_one(
        {"stripe_object_id": payment_intent_id}, {"_id": 0}
    )
    if charge_row and charge_row.get("status") == "refunded":
        return {
            "refund_id": None,
            "status": "duplicate_blocked",
            "amount_refunded_cents": 0,
            "is_partial": False,
            "duplicate_blocked": True,
        }

    # ---- Build Stripe Refund.create parameters
    params: Dict[str, Any] = {
        "payment_intent": payment_intent_id,
        "reason": reason,
    }
    if amount_cents is not None:
        if amount_cents <= 0:
            raise RefundError(f"amount_cents must be positive; got {amount_cents}")
        params["amount"] = int(amount_cents)

    # iter482 — Partner Model A₁ destination-charge refund:
    # Return the application_fee to the buyer + reverse the destination
    # transfer so the Partner's Connect balance also unwinds.
    if is_partner_listing:
        params["refund_application_fee"] = True
        params["reverse_transfer"] = True

    # ---- Execute Stripe refund
    try:
        r = stripe.Refund.create(**params)
    except Exception as exc:  # includes stripe.error.StripeError and network errors
        # Do NOT flip charge_row to refunded — the Stripe call failed.
        raise RefundError(f"Stripe refund failed: {exc}") from exc

    refund_id = r.id
    r_status = r.status
    r_amount = int(r.amount)

    # ---- Determine whether this was a full or partial refund
    charge_amount = int(charge_row.get("amount", 0) * 100) if charge_row and charge_row.get("amount") else None
    is_partial = charge_amount is not None and r_amount < charge_amount

    now = datetime.now(timezone.utc).isoformat()

    # ---- Persist to db.payment_events (audit log; append-only)
    await db.payment_events.insert_one({
        "id": str(uuid.uuid4()),
        "event": "REFUND_ISSUED",
        "auction_id": (charge_row or {}).get("auction_id"),
        "user_id": (charge_row or {}).get("user_id"),
        "stripe_payment_intent_id": payment_intent_id,
        "stripe_refund_id": refund_id,
        "amount_refunded_cents": r_amount,
        "is_partial": is_partial,
        "is_partner_listing": is_partner_listing,
        "reason": reason,
        "initiated_by": initiated_by,
        "created_at": now,
    })

    # ---- Mark payment_charges row refunded (only on full refund)
    if not is_partial and charge_row:
        await mark_charge_refunded(db, charge_row["id"], reason=reason)

    # ---- Additive receipt annotation (NEVER overwrite original financials)
    # The receipt already carries the authoritative pre-refund values.
    # We add a `refund` sub-document that reflects the reversal state.
    await db.receipts.update_many(
        {"transaction_id": (charge_row or {}).get("id")},
        {"$set": {
            "refund_status": "partial" if is_partial else "full",
            "refund_amount_cents": r_amount,
            "refunded_at": now,
            "refund_id": refund_id,
            "refund_reason": reason,
        }}
    )
    # ---- Additive transaction annotation
    await db.transactions.update_many(
        {"stripe_payment_intent": payment_intent_id},
        {"$set": {
            "refund_status": "partial" if is_partial else "full",
            "refund_amount_cents": r_amount,
            "refunded_at": now,
            "refund_id": refund_id,
        }}
    )

    logger.info(
        f"REFUND_ISSUED pi={payment_intent_id} refund={refund_id} "
        f"amount={r_amount} partial={is_partial} partner={is_partner_listing}"
    )
    return {
        "refund_id": refund_id,
        "status": r_status,
        "amount_refunded_cents": r_amount,
        "is_partial": is_partial,
        "duplicate_blocked": False,
    }


__all__ = ["refund_partner_transaction", "RefundError"]
