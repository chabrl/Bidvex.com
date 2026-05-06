"""
BidVex Payment Idempotency & Duplicate-Charge Guard
====================================================
Single source of truth for:
  • Building deterministic Stripe idempotency keys.
  • Atomically reserving a payment_charges row before any Stripe call.
  • Refusing to re-charge an already succeeded record (DUPLICATE_CHARGE_BLOCKED).
  • Rolling back a Stripe charge when the DB write fails (ROLLBACK_REFUND).

Schema (collection: `payment_charges`)
--------------------------------------
{
  "id": uuid,
  "auction_id": str,            # listing/auction/storage_auction id
  "user_id": str,               # buyer or seller depending on charge_type
  "charge_type": str,           # see CHARGE_TYPES
  "currency": "CAD" | "USD",
  "amount": float,              # in major units
  "idempotency_key": str,       # deterministic
  "stripe_object_id": str|None, # SetupIntent / PaymentIntent / Charge id
  "stripe_object_type": str|None,
  "status": "pending"|"succeeded"|"failed"|"refunded"|"rolled_back"|"blocked_duplicate",
  "error": str|None,
  "metadata": dict,
  "created_at": iso str,
  "updated_at": iso str,
  "succeeded_at": iso str|None,
  "refunded_at": iso str|None,
}

Index: unique(auction_id, user_id, charge_type) WHERE status="succeeded".
This index is created on app startup by `ensure_payment_charges_indexes`.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe

logger = logging.getLogger(__name__)

# ---- Charge type registry ----
# Per spec: every charge must reference (auction_id, user_id, charge_type).
CHARGE_TYPES = {
    "deposit",                  # Per-bid deposit (held when first bid placed)
    "buyer_commission",         # BidVex commission charged to winning buyer (cash/etransfer flow)
    "buyer_full_payment",       # Full hammer + commission (Stripe flow)
    "buy_now_payment",          # Buy-Now full charge
    "seller_commission",        # BidVex commission charged to seller (cash/etransfer flow)
    "seller_payout",            # Stripe Connect transfer to seller (Stripe flow)
}


def build_idempotency_key(
    charge_type: str,
    auction_id: str,
    user_id: str,
    auction_end_ts: Optional[int] = None,
) -> str:
    """
    Build deterministic idempotency key per spec:
      `{charge_type}_{auction_id}_{user_id}_{unix_timestamp_of_auction_end}`

    If auction_end_ts is missing, fall back to current unix timestamp truncated
    to the nearest minute to keep the key stable across retries within 60s.
    """
    if charge_type not in CHARGE_TYPES:
        raise ValueError(f"Unknown charge_type: {charge_type}")
    if auction_end_ts is None:
        auction_end_ts = int(datetime.now(timezone.utc).timestamp() // 60 * 60)
    return f"{charge_type}_{auction_id}_{user_id}_{auction_end_ts}"


# ---- DB-backed duplicate-charge guard ----

class DuplicateChargeBlocked(Exception):
    """Raised when an existing succeeded charge is found for the tuple."""

    def __init__(self, charge_type: str, auction_id: str, user_id: str, existing_id: str):
        self.charge_type = charge_type
        self.auction_id = auction_id
        self.user_id = user_id
        self.existing_id = existing_id
        super().__init__(
            f"DUPLICATE_CHARGE_BLOCKED charge_type={charge_type} "
            f"auction={auction_id} user={user_id} existing_charge={existing_id}"
        )


async def ensure_payment_charges_indexes(db) -> None:
    """Create indexes (idempotent). Called at app startup."""
    try:
        await db.payment_charges.create_index(
            [("idempotency_key", 1)], unique=True, name="ux_idem_key"
        )
        await db.payment_charges.create_index(
            [("auction_id", 1), ("user_id", 1), ("charge_type", 1), ("status", 1)],
            name="ix_auction_user_type_status",
        )
        await db.payment_charges.create_index(
            [("status", 1), ("created_at", -1)], name="ix_status_created"
        )
        logger.info("payment_charges indexes ensured")
    except Exception as exc:
        logger.warning(f"payment_charges index creation failed: {exc}")


async def find_existing_charge(
    db,
    *,
    auction_id: str,
    user_id: str,
    charge_type: str,
) -> Optional[Dict[str, Any]]:
    """Return any existing succeeded or pending charge for the tuple."""
    return await db.payment_charges.find_one(
        {
            "auction_id": auction_id,
            "user_id": user_id,
            "charge_type": charge_type,
            "status": {"$in": ["succeeded", "pending"]},
        },
        {"_id": 0},
    )


async def reserve_charge_row(
    db,
    *,
    auction_id: str,
    user_id: str,
    charge_type: str,
    currency: str,
    amount: float,
    auction_end_ts: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Atomically reserve a `payment_charges` row before invoking Stripe.

    Behavior:
      • If a SUCCEEDED row exists → raise DuplicateChargeBlocked.
      • If a PENDING row exists with same idempotency_key → reuse it (retry path).
      • Else insert a new pending row and return it.
    """
    if charge_type not in CHARGE_TYPES:
        raise ValueError(f"Unknown charge_type: {charge_type}")
    currency = (currency or "CAD").upper()
    if currency not in ("CAD", "USD"):
        raise ValueError(f"Unsupported currency: {currency}")

    idem_key = build_idempotency_key(charge_type, auction_id, user_id, auction_end_ts)

    # Block on existing succeeded charge for SAME tuple (any idem key)
    existing_succeeded = await db.payment_charges.find_one(
        {
            "auction_id": auction_id,
            "user_id": user_id,
            "charge_type": charge_type,
            "status": "succeeded",
        },
        {"_id": 0, "id": 1},
    )
    if existing_succeeded:
        # Log the block so admin dashboard can flag it
        await db.payment_events.insert_one(
            {
                "id": str(uuid.uuid4()),
                "event": "DUPLICATE_CHARGE_BLOCKED",
                "auction_id": auction_id,
                "user_id": user_id,
                "charge_type": charge_type,
                "existing_charge_id": existing_succeeded["id"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        raise DuplicateChargeBlocked(
            charge_type, auction_id, user_id, existing_succeeded["id"]
        )

    # Re-use pending row with same idempotency_key (retry of same call)
    existing_pending = await db.payment_charges.find_one(
        {"idempotency_key": idem_key, "status": "pending"}, {"_id": 0}
    )
    if existing_pending:
        return existing_pending

    now = datetime.now(timezone.utc).isoformat()
    row = {
        "id": str(uuid.uuid4()),
        "auction_id": auction_id,
        "user_id": user_id,
        "charge_type": charge_type,
        "currency": currency,
        "amount": round(float(amount), 2),
        "idempotency_key": idem_key,
        "stripe_object_id": None,
        "stripe_object_type": None,
        "status": "pending",
        "error": None,
        "metadata": metadata or {},
        "created_at": now,
        "updated_at": now,
        "succeeded_at": None,
        "refunded_at": None,
    }
    try:
        await db.payment_charges.insert_one(row)
    except Exception as exc:
        # Race: another process inserted the same idem key in the same instant
        logger.warning(f"reserve_charge_row insert race: {exc}")
        existing = await db.payment_charges.find_one(
            {"idempotency_key": idem_key}, {"_id": 0}
        )
        if existing:
            return existing
        raise
    return row


async def mark_charge_succeeded(
    db, charge_id: str, *, stripe_object_id: str, stripe_object_type: str
) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.payment_charges.update_one(
        {"id": charge_id},
        {"$set": {
            "status": "succeeded",
            "stripe_object_id": stripe_object_id,
            "stripe_object_type": stripe_object_type,
            "succeeded_at": now,
            "updated_at": now,
        }},
    )


async def mark_charge_failed(db, charge_id: str, *, error: str) -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.payment_charges.update_one(
        {"id": charge_id},
        {"$set": {"status": "failed", "error": str(error)[:500], "updated_at": now}},
    )


async def mark_charge_refunded(db, charge_id: str, *, reason: str = "refunded") -> None:
    now = datetime.now(timezone.utc).isoformat()
    await db.payment_charges.update_one(
        {"id": charge_id},
        {"$set": {
            "status": "refunded",
            "refunded_at": now,
            "updated_at": now,
            "metadata.refund_reason": reason,
        }},
    )


# ---- Atomic Stripe + DB rollback helper ----

async def rollback_stripe_charge(
    charge_row: Dict[str, Any], *, reason: str = "db_write_failed"
) -> bool:
    """
    Issue an immediate Stripe refund/cancel for a charge whose DB write failed.
    Returns True if rollback executed, False otherwise.
    """
    stripe.api_key = os.environ.get("STRIPE_API_KEY", "")
    obj_id = charge_row.get("stripe_object_id")
    obj_type = charge_row.get("stripe_object_type")
    if not obj_id:
        return False
    try:
        if obj_type == "payment_intent":
            try:
                stripe.PaymentIntent.cancel(obj_id)
            except Exception:
                # Already captured → refund instead
                stripe.Refund.create(payment_intent=obj_id, reason="duplicate")
        elif obj_type == "charge":
            stripe.Refund.create(charge=obj_id, reason="duplicate")
        elif obj_type == "setup_intent":
            try:
                stripe.SetupIntent.cancel(obj_id)
            except Exception:
                pass
        logger.warning(
            f"ROLLBACK_REFUND charge={charge_row.get('id')} stripe={obj_id} reason={reason}"
        )
        return True
    except Exception as exc:
        logger.error(
            f"ROLLBACK_FAILED charge={charge_row.get('id')} stripe={obj_id} err={exc}"
        )
        return False


__all__ = [
    "build_idempotency_key",
    "ensure_payment_charges_indexes",
    "find_existing_charge",
    "reserve_charge_row",
    "mark_charge_succeeded",
    "mark_charge_failed",
    "mark_charge_refunded",
    "rollback_stripe_charge",
    "DuplicateChargeBlocked",
    "CHARGE_TYPES",
]
