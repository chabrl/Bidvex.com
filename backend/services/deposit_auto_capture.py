"""
Vehicle Deposit Auto-Capture Job — iter175
==========================================
Scheduled task that automatically captures the $500 vehicle bidding deposit
when a winner's 2.5% platform fee invoice remains unpaid more than
DEPOSIT_AUTO_CAPTURE_GRACE_HOURS (default 48h) past its `payment_deadline`.

CASL/Bill 96 compliance: the buyer is notified IN BOTH LANGUAGES via
`send_vehicle_deposit_captured_email` immediately after capture.

Idempotency: jobs that have already captured a deposit (status='captured')
are skipped on subsequent runs. Once captured, the deposit auto-capture
event is recorded in `vehicle_audit_logs` so admins can audit.
"""
from datetime import datetime, timedelta, timezone
import logging
import os

logger = logging.getLogger(__name__)

DEPOSIT_AUTO_CAPTURE_GRACE_HOURS = int(
    os.environ.get("DEPOSIT_AUTO_CAPTURE_GRACE_HOURS", "48")
)


async def run_auto_capture_overdue_deposits(db) -> dict:
    """
    Find vehicle invoices that are:
      • payment_status in {pending, overdue}
      • now > payment_deadline + GRACE_HOURS
      • have an associated deposit in status {paid, authorized}
    Capture each deposit via PaymentService.capture_deposit() and email
    the buyer (bilingual).
    """
    if db is None:
        logger.warning("[AUTO_CAPTURE] db is None, skipping")
        return {"error": "db_not_initialized"}

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=DEPOSIT_AUTO_CAPTURE_GRACE_HOURS)

    # Find candidate buyer invoices
    candidates = await db.vehicle_invoices.find(
        {
            "invoice_type": "buyer",
            "payment_status": {"$in": ["pending", "overdue"]},
            "payment_deadline": {"$lt": cutoff},
        },
        {"_id": 0},
    ).to_list(200)

    if not candidates:
        logger.info("[AUTO_CAPTURE] no overdue invoices to process")
        return {"processed": 0, "captured": 0, "skipped": 0}

    from services.vehicle_payment import get_payment_service
    payment_service = get_payment_service()

    processed = 0
    captured_count = 0
    skipped = 0

    for inv in candidates:
        processed += 1
        buyer_id = inv.get("buyer_id")
        vehicle_id = inv.get("vehicle_id")

        # Find the deposit hold matching this winner+vehicle
        deposit = await db.vehicle_bid_deposits.find_one(
            {
                "user_id": buyer_id,
                "vehicle_id": vehicle_id,
                "status": {"$in": ["paid", "authorized"]},
            },
            {"_id": 0},
        )
        if not deposit:
            logger.info(
                f"[AUTO_CAPTURE] no capturable deposit for buyer={buyer_id} vehicle={vehicle_id}"
            )
            skipped += 1
            continue

        try:
            result = await payment_service.capture_deposit(
                db,
                deposit_id=deposit["id"],
                reason="fee_invoice_unpaid_past_deadline_auto_capture",
            )
            captured_count += 1
            captured_amount = float(result.get("amount_captured") or 0)
            logger.info(
                f"[AUTO_CAPTURE] captured deposit={deposit['id']} amount=${captured_amount}"
            )

            # iter310 — Apply captured amount against the unpaid invoice
            # balance. Flag remaining as `payment_overdue` if the deposit
            # didn't cover the full invoice (existing escalation path
            # continues to drive collections from there).
            try:
                inv_total = float(inv.get("total_amount") or 0)
                already_paid = float(inv.get("paid_amount") or 0)
                new_paid = already_paid + captured_amount
                remaining = max(0.0, inv_total - new_paid)
                inv_update = {
                    "paid_amount":             round(new_paid, 2),
                    "deposit_capture_applied": True,
                    "deposit_capture_amount":  round(captured_amount, 2),
                    "deposit_capture_at":      now,
                }
                if remaining <= 0.01:
                    inv_update["payment_status"] = "paid"
                    inv_update["paid_at"] = now
                    inv_update["payment_method"] = "deposit_capture"
                else:
                    inv_update["payment_status"]   = "payment_overdue"
                    inv_update["remaining_balance"] = round(remaining, 2)
                    inv_update["overdue_flagged_at"] = now
                await db.vehicle_invoices.update_one({"id": inv["id"]}, {"$set": inv_update})
                logger.info(
                    f"[AUTO_CAPTURE] invoice={inv.get('id')} applied ${captured_amount} "
                    f"→ paid=${new_paid:.2f}, remaining=${remaining:.2f}, "
                    f"status={inv_update['payment_status']}"
                )
            except Exception as inv_err:
                logger.error(
                    f"[AUTO_CAPTURE] invoice update failed for {inv.get('id')}: {inv_err}"
                )

            # Notify buyer in EN+FR (bilingual per Bill 96)
            try:
                from services.emails.email_vehicles import send_vehicle_deposit_captured_email
                buyer = await db.users.find_one({"id": buyer_id}, {"_id": 0})
                if buyer and buyer.get("email"):
                    await send_vehicle_deposit_captured_email(
                        buyer=buyer,
                        invoice=inv,
                        deposit=deposit,
                        captured_amount=result.get("amount_captured"),
                    )
            except Exception as e:
                logger.error(f"[AUTO_CAPTURE] email send failed: {e}")
        except Exception as e:
            logger.error(f"[AUTO_CAPTURE] capture failed for deposit={deposit.get('id')}: {e}")
            skipped += 1

    return {
        "processed": processed,
        "captured": captured_count,
        "skipped": skipped,
        "grace_hours": DEPOSIT_AUTO_CAPTURE_GRACE_HOURS,
    }
