"""
iter482 P5.1 — Stripe Actual-Fee Reconciliation Service
=======================================================

For every successful Stripe payment we already know:
  * estimated_cents  — additive Stripe fee estimate (base × rate + fixed)
  * recovery_cents   — gross-up amount the payer was charged

After the payment succeeds we retrieve the authoritative fee from
Stripe's ``BalanceTransaction`` and compute variance:

  * actual_cents        — Stripe BalanceTransaction.fee_details[type=stripe_fee]
  * variance_cents      — recovery_cents - actual_cents  (positive = COVERED)
  * reconciliation_status
        - COVERED   (recovery >= actual)
        - SHORTFALL (recovery <  actual — BidVex is out of pocket)

All four values are persisted in ``db.payment_processing_reconciliation``
keyed by ``payment_intent_id`` — idempotent (updates existing row on
webhook replay, never duplicates).

The service also resolves the authoritative card-country jurisdiction
from ``payment_method_details.card.country`` and stores it so admins
can audit CA-vs-INT charging accuracy.

iter482 P6 completion — On a genuine SHORTFALL the service dispatches
one idempotent variance email to the admin billing recipients (uses
the canonical SendGrid dispatcher and ``variance_notification_status``
flag on the reconciliation doc so webhook retries never re-send).
"""

from __future__ import annotations
import os
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


# Public API-visible status vocabulary (iter482 P6 completion). The
# internal storage keeps the legacy values (COVERED / SHORTFALL /
# UNKNOWN / ERROR) for backwards compatibility with existing rows and
# the summary aggregation; this map is used when a caller (typically
# the admin dashboard route) wants the P6-canonical vocabulary.
STATUS_ALIASES: Dict[str, str] = {
    "COVERED":   "RECONCILED",
    "SHORTFALL": "SHORTFALL",
    "UNKNOWN":   "PENDING",
    "ERROR":     "ERROR",
}


def public_status(internal_status: Optional[str]) -> str:
    """Translate an internal reconciliation_status to the
    P6-canonical vocabulary that the admin dashboard consumes.

    Rules:
      • COVERED   → RECONCILED (recovery covered the actual fee)
      • SHORTFALL → SHORTFALL  (BidVex is out of pocket)
      • UNKNOWN   → PENDING    (no BalanceTransaction yet)
      • ERROR     → ERROR      (Stripe retrieve failed)
    """
    return STATUS_ALIASES.get((internal_status or "").upper(), "PENDING")


def _get_stripe():
    import stripe
    stripe.api_key = os.environ.get("STRIPE_TEST_SECRET_KEY") or os.environ.get("STRIPE_API_KEY")
    return stripe


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _reconciliation_status(recovery_cents: int, actual_cents: int) -> str:
    if actual_cents == 0:
        # No actual fee retrieved yet (e.g. non-Stripe path) — treat as UNKNOWN
        return "UNKNOWN"
    return "COVERED" if recovery_cents >= actual_cents else "SHORTFALL"


async def reconcile_payment_intent(db, payment_intent_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve the authoritative Stripe fee for ``payment_intent_id`` and
    persist the reconciliation record.  Idempotent — a webhook replay
    updates the existing row in-place instead of duplicating it.

    Returns the persisted reconciliation document, or ``None`` if the
    PaymentIntent could not be resolved (in which case an ``error``
    record is still written for admin visibility).
    """
    stripe = _get_stripe()
    try:
        pi = stripe.PaymentIntent.retrieve(
            payment_intent_id,
            expand=["latest_charge.balance_transaction", "payment_method"],
        )
    except Exception as exc:  # pragma: no cover — network/Stripe error
        logger.warning(f"[reconcile] PaymentIntent.retrieve({payment_intent_id}) failed: {exc}")
        await db.payment_processing_reconciliation.update_one(
            {"payment_intent_id": payment_intent_id},
            {"$set": {
                "payment_intent_id": payment_intent_id,
                "reconciliation_status": "ERROR",
                "error": str(exc),
                "updated_at": _iso_now(),
            },
             "$setOnInsert": {"created_at": _iso_now()}},
            upsert=True,
        )
        return None

    # ── Read estimate / recovery from PaymentIntent metadata ─────────
    meta = pi.get("metadata") or {}
    estimated_cents = int(meta.get("payment_processing_estimated_cents", 0) or 0)
    recovery_cents = int(meta.get("payment_processing_recovery_cents", 0) or 0)
    payer_role = meta.get("payment_processing_payer_role") or "buyer"
    rate = meta.get("payment_processing_rate")
    prior_jurisdiction = meta.get("payment_processing_jurisdiction")

    # ── Read actual fee from BalanceTransaction ──────────────────────
    # iter482 P6.1 — Stripe's deep-nested `expand=['latest_charge.balance_transaction']`
    # can return `balance_transaction=None` in the current API version
    # (the nested expansion is not populated immediately after confirm —
    # Stripe's ledger writes the BalanceTransaction asynchronously,
    # typically within a few seconds). Fall back to retrieving the
    # charge directly with a single-level expand, and if the BT is
    # still absent, poll up to 3× at 1s intervals. In production the
    # `payment_intent.succeeded` webhook usually arrives after the BT
    # is posted, but this retry hardens the direct-call path used by
    # tests and admin re-reconciliation.
    import time as _time
    actual_cents = 0
    stripe_currency = "cad"
    charge_id = None
    balance_txn_id = None
    fee_details = []
    latest_charge = pi.get("latest_charge") or {}
    if isinstance(latest_charge, dict):
        charge_id = latest_charge.get("id")
        bt = latest_charge.get("balance_transaction")
        if not isinstance(bt, dict) and charge_id:
            for _attempt in range(3):
                try:
                    fresh = stripe.Charge.retrieve(charge_id, expand=["balance_transaction"])
                    bt = fresh.get("balance_transaction")
                    if isinstance(bt, dict):
                        break
                except Exception as _bt_exc:
                    logger.warning(f"[reconcile] charge refetch for BT failed: {_bt_exc}")
                    bt = None
                _time.sleep(1)
        if isinstance(bt, dict):
            balance_txn_id = bt.get("id")
            actual_cents = int(bt.get("fee") or 0)
            stripe_currency = (bt.get("currency") or "cad").lower()
            # Convert Stripe FeeDetail objects to plain dicts so Motor
            # can persist them cleanly.
            raw_details = bt.get("fee_details") or []
            fee_details = [dict(x) if isinstance(x, dict) else x for x in raw_details]

    # ── Resolve authoritative card country ───────────────────────────
    card_country = None
    if isinstance(latest_charge, dict):
        pmd = (latest_charge.get("payment_method_details") or {}).get("card") or {}
        card_country = pmd.get("country") or pmd.get("issuer_country")
    if not card_country:
        pm = pi.get("payment_method") or {}
        if isinstance(pm, dict):
            card_country = (pm.get("card") or {}).get("country")
    resolved_jurisdiction = "domestic" if (card_country or "").upper() == "CA" else "international"

    variance_cents = recovery_cents - actual_cents
    status = _reconciliation_status(recovery_cents, actual_cents)

    doc = {
        "payment_intent_id": payment_intent_id,
        "charge_id": charge_id,
        "balance_transaction_id": balance_txn_id,
        "currency": stripe_currency.upper(),
        "estimated_cents": estimated_cents,
        "recovery_cents": recovery_cents,
        "actual_cents": actual_cents,
        "variance_cents": variance_cents,
        "reconciliation_status": status,
        "payer_role": payer_role,
        "rate_snapshot": rate,
        "prior_jurisdiction": prior_jurisdiction,
        "card_country": card_country,
        "resolved_jurisdiction": resolved_jurisdiction,
        "fee_details": fee_details,
        "engine_version": "iter482-P5.1-v1",
        "updated_at": _iso_now(),
    }

    await db.payment_processing_reconciliation.update_one(
        {"payment_intent_id": payment_intent_id},
        {"$set": doc, "$setOnInsert": {"created_at": _iso_now()}},
        upsert=True,
    )

    logger.info(
        f"[reconcile] PI={payment_intent_id} status={status} recovery={recovery_cents}c "
        f"actual={actual_cents}c variance={variance_cents}c country={card_country}"
    )

    # iter482 P6 — idempotent variance notification. Only fires when the
    # reconciliation ends in SHORTFALL AND the notification has not
    # already been dispatched for this PI. Webhook replays / repeat
    # calls into this function are no-ops for the email once the flag
    # is set.
    try:
        if status == "SHORTFALL":
            row = await db.payment_processing_reconciliation.find_one(
                {"payment_intent_id": payment_intent_id},
                {"_id": 0, "variance_notification_status": 1},
            )
            if not row or row.get("variance_notification_status") != "SENT":
                from services.variance_notification_service import (
                    dispatch_variance_notification,
                )
                await dispatch_variance_notification(db, doc)
    except Exception as _notif_err:  # pragma: no cover — best-effort
        logger.warning(
            f"[reconcile] variance notification dispatch failed for "
            f"PI={payment_intent_id}: {_notif_err}"
        )

    return doc


def build_reconciliation_from_event(data: Dict[str, Any]) -> Dict[str, Any]:
    """Build a reconciliation snapshot directly from a webhook event
    payload (no additional Stripe API call).  Used when the event
    payload already contains an expanded ``latest_charge`` +
    ``balance_transaction``.  Non-async so callers can invoke it from
    plain code paths.  Returns the reconciliation doc (unpersisted).
    """
    pi_id = data.get("id")
    meta = data.get("metadata") or {}
    estimated_cents = int(meta.get("payment_processing_estimated_cents", 0) or 0)
    recovery_cents = int(meta.get("payment_processing_recovery_cents", 0) or 0)

    actual_cents = 0
    charge_id = None
    balance_txn_id = None
    fee_details = []
    charges = (data.get("charges") or {}).get("data") or []
    if charges:
        c = charges[0]
        charge_id = c.get("id")
        bt = c.get("balance_transaction")
        if isinstance(bt, dict):
            balance_txn_id = bt.get("id")
            actual_cents = int(bt.get("fee") or 0)
            fee_details = bt.get("fee_details") or []
    return {
        "payment_intent_id": pi_id,
        "charge_id": charge_id,
        "balance_transaction_id": balance_txn_id,
        "estimated_cents": estimated_cents,
        "recovery_cents": recovery_cents,
        "actual_cents": actual_cents,
        "variance_cents": recovery_cents - actual_cents,
        "reconciliation_status": _reconciliation_status(recovery_cents, actual_cents),
        "fee_details": fee_details,
    }
