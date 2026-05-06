"""
Deposit Refund Queue — 60-second SLA worker
============================================
Replaces 5-minute cron polling with a 10-second tick + atomic claim queue.

Flow:
  1. When auction ends (via `enqueue_non_winner_refunds`), we insert one
     `deposit_refund_queue` row per non-winning deposit holder.
  2. The `process_deposit_refund_queue` worker (registered in scheduler.py
     with IntervalTrigger(seconds=10)) atomically claims pending rows,
     issues Stripe refunds, marks them succeeded.
  3. On failure: increment `attempts`, schedule retry with exponential
     backoff (10s, 30s, 90s). After 3 attempts → mark `failed`, alert admin.

Schema (`deposit_refund_queue`):
{
  "id": uuid,
  "auction_id": str,
  "user_id": str,
  "deposit_id": str,                # source deposit doc id
  "deposit_collection": str,        # bidding_deposits|storage_deposits
  "stripe_payment_intent_id": str,
  "amount": float,
  "currency": str,
  "status": "pending"|"processing"|"succeeded"|"failed",
  "attempts": int,
  "next_attempt_at": iso str,
  "last_error": str|None,
  "created_at": iso str,
  "updated_at": iso str,
  "completed_at": iso str|None,
}
"""
from __future__ import annotations

import asyncio
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

import stripe

logger = logging.getLogger(__name__)

REFUND_BACKOFF_SECONDS = [10, 30, 90]
MAX_REFUND_ATTEMPTS = 3
REFUND_BATCH_SIZE = 25


async def ensure_refund_queue_indexes(db) -> None:
    try:
        await db.deposit_refund_queue.create_index(
            [("status", 1), ("next_attempt_at", 1)], name="ix_status_next"
        )
        await db.deposit_refund_queue.create_index(
            [("auction_id", 1), ("user_id", 1), ("deposit_id", 1)],
            unique=True,
            name="ux_auction_user_deposit",
        )
        logger.info("deposit_refund_queue indexes ensured")
    except Exception as exc:
        logger.warning(f"deposit_refund_queue index creation failed: {exc}")


async def enqueue_non_winner_refunds(
    db,
    *,
    auction_id: str,
    winner_user_id: Optional[str],
    deposits: Iterable[Dict[str, Any]],
    deposit_collection: str = "bidding_deposits",
) -> int:
    """
    Enqueue refund jobs for every deposit that does NOT belong to the winner.
    Returns the count of jobs enqueued.

    `deposits` should be the cursor of held/authorized deposit docs for the
    auction; each must contain `id`, `user_id`, `stripe_payment_intent_id`,
    `amount`, optional `currency`.
    """
    enqueued = 0
    now = datetime.now(timezone.utc)
    for d in deposits:
        if not d.get("stripe_payment_intent_id"):
            continue
        if winner_user_id and d.get("user_id") == winner_user_id:
            continue  # winner deposit is credited, not refunded
        row = {
            "id": str(uuid.uuid4()),
            "auction_id": auction_id,
            "user_id": d["user_id"],
            "deposit_id": d["id"],
            "deposit_collection": deposit_collection,
            "stripe_payment_intent_id": d["stripe_payment_intent_id"],
            "amount": float(d.get("amount", 0)),
            "currency": (d.get("currency") or "CAD").upper(),
            "status": "pending",
            "attempts": 0,
            "next_attempt_at": now.isoformat(),
            "last_error": None,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "completed_at": None,
        }
        try:
            await db.deposit_refund_queue.insert_one(row)
            enqueued += 1
        except Exception:
            # duplicate (auction_id, user_id, deposit_id) — already enqueued
            pass
    if enqueued:
        logger.info(
            f"deposit_refund_queue: enqueued {enqueued} refund jobs for auction={auction_id}"
        )
    return enqueued


async def _claim_pending_jobs(db, *, batch_size: int = REFUND_BATCH_SIZE) -> List[Dict[str, Any]]:
    """Atomically transition `pending` → `processing`, return claimed rows."""
    now = datetime.now(timezone.utc)
    claimed: List[Dict[str, Any]] = []
    for _ in range(batch_size):
        doc = await db.deposit_refund_queue.find_one_and_update(
            {
                "status": "pending",
                "next_attempt_at": {"$lte": now.isoformat()},
            },
            {"$set": {"status": "processing", "updated_at": now.isoformat()}},
        )
        if not doc:
            break
        claimed.append(doc)
    return claimed


async def _process_single_refund(db, job: Dict[str, Any]) -> None:
    """Issue Stripe refund/cancel and update DB row + source deposit row."""
    stripe.api_key = os.environ.get("STRIPE_API_KEY", "")
    pi_id = job["stripe_payment_intent_id"]
    job_id = job["id"]
    attempts = int(job.get("attempts", 0)) + 1
    now = datetime.now(timezone.utc)

    try:
        # Try cancel first (uncaptured manual hold) → fall back to refund
        try:
            stripe.PaymentIntent.cancel(pi_id)
            stripe_op = "canceled"
        except stripe.error.InvalidRequestError as exc:
            # Already captured → refund the captured amount
            if "cannot be canceled" in str(exc).lower() or "already" in str(exc).lower():
                stripe.Refund.create(payment_intent=pi_id, reason="requested_by_customer")
                stripe_op = "refunded"
            else:
                raise

        await db.deposit_refund_queue.update_one(
            {"id": job_id},
            {"$set": {
                "status": "succeeded",
                "completed_at": now.isoformat(),
                "updated_at": now.isoformat(),
                "attempts": attempts,
                "stripe_op": stripe_op,
            }},
        )
        # Update source deposit row
        coll = db[job.get("deposit_collection", "bidding_deposits")]
        await coll.update_one(
            {"id": job["deposit_id"]},
            {"$set": {
                "status": "refunded",
                "refunded_at": now.isoformat(),
                "stripe_refund_op": stripe_op,
            }},
        )
        # Send email (best effort)
        try:
            from services.email_notifications import send_deposit_refunded_email
            await send_deposit_refunded_email(
                db=db,
                user_id=job["user_id"],
                auction_id=job["auction_id"],
                amount=job["amount"],
                currency=job["currency"],
            )
        except Exception as e:
            logger.warning(f"deposit_refund email failed for job={job_id}: {e}")
    except Exception as exc:
        err_msg = str(exc)[:500]
        if attempts >= MAX_REFUND_ATTEMPTS:
            await db.deposit_refund_queue.update_one(
                {"id": job_id},
                {"$set": {
                    "status": "failed",
                    "attempts": attempts,
                    "last_error": err_msg,
                    "updated_at": now.isoformat(),
                }},
            )
            logger.error(
                f"deposit_refund_queue: PERMANENT_FAILURE job={job_id} pi={pi_id} err={err_msg}"
            )
            # Alert admin via payment_events
            await db.payment_events.insert_one({
                "id": str(uuid.uuid4()),
                "event": "DEPOSIT_REFUND_PERMANENT_FAILURE",
                "auction_id": job["auction_id"],
                "user_id": job["user_id"],
                "amount": job["amount"],
                "currency": job["currency"],
                "stripe_payment_intent_id": pi_id,
                "error": err_msg,
                "created_at": now.isoformat(),
            })
        else:
            backoff = REFUND_BACKOFF_SECONDS[min(attempts - 1, len(REFUND_BACKOFF_SECONDS) - 1)]
            next_attempt = now + timedelta(seconds=backoff)
            await db.deposit_refund_queue.update_one(
                {"id": job_id},
                {"$set": {
                    "status": "pending",  # back to pending for retry
                    "attempts": attempts,
                    "last_error": err_msg,
                    "next_attempt_at": next_attempt.isoformat(),
                    "updated_at": now.isoformat(),
                }},
            )
            logger.warning(
                f"deposit_refund_queue: retry attempt={attempts} job={job_id} in {backoff}s err={err_msg}"
            )


async def process_deposit_refund_queue(db) -> Dict[str, int]:
    """
    Worker tick: claim a batch and process in parallel.
    Registered with IntervalTrigger(seconds=10) → meets <60s SLA per spec
    (auction end → enqueue → next tick within 10s → asyncio.gather refunds).
    """
    claimed = await _claim_pending_jobs(db, batch_size=REFUND_BATCH_SIZE)
    if not claimed:
        return {"processed": 0}
    await asyncio.gather(*[_process_single_refund(db, j) for j in claimed])
    succeeded = await db.deposit_refund_queue.count_documents(
        {"id": {"$in": [j["id"] for j in claimed]}, "status": "succeeded"}
    )
    return {"processed": len(claimed), "succeeded": succeeded}
