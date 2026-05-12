"""
iter210 Step 1 — Vehicle Dealer Annual-Fee Payment Failure Pipeline

When `invoice.payment_failed` fires for a vehicle-dealer subscription:
  Day 1: write `dealer_compliance_log` row + send warning email (EN/FR)
  Day 7: call `suspend_dealer_for_failed_payment` → hide all listings + email

The webhook itself only registers the failure and dispatches Day-1.
Day-7 enforcement runs through a daily cron (`enforce_dealer_grace_period_job`)
so we don't depend on Stripe re-firing the event.

Idempotency:
  * webhook side uses `stripe_event_id` as the unique key per row
  * daily cron only suspends users whose grace started > 7 days ago AND
    `vehicle_dealer_suspended` is not already True
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

GRACE_PERIOD_DAYS = 7


# ─── Email content (bilingual) ─────────────────────────────────────────────
def _warning_email_html(dealer_name: str, last4: str | None = None) -> str:
    last4_block = (
        f"<p style='font-size:12px;color:#64748b;'>Card ending in •••• {last4}</p>"
        if last4 else ""
    )
    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:560px;margin:0 auto;color:#1e293b;">
      <div style="background:#dc2626;padding:24px 28px;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:20px;">⚠️ Payment Failed</h1>
        <p style="color:#fecaca;margin:6px 0 0;font-size:13px;">Update your card to avoid listing suspension</p>
      </div>
      <div style="padding:24px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;font-size:14px;line-height:1.7;">
        <p>Hi {dealer_name or 'there'},</p>
        <p>Your <strong>BidVex Vehicle Dealer</strong> annual platform fee payment failed.</p>
        {last4_block}
        <p>Please update your payment method within <strong>{GRACE_PERIOD_DAYS} days</strong> to keep your listings live.
        After that, all your active vehicle listings will be suspended automatically.</p>
        <p style="margin:20px 0;text-align:center;">
          <a href="https://bidvex.com/partner/payment-settings" style="display:inline-block;background:#2563eb;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;">Update Payment Method</a>
        </p>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:18px 0;" />
        <p style="color:#475569;font-size:13px;">
          <strong>Bonjour,</strong><br/>
          Le paiement annuel de vos frais de plateforme <strong>BidVex marchand automobile</strong> a échoué.
          Veuillez mettre à jour votre moyen de paiement dans les {GRACE_PERIOD_DAYS} jours pour éviter
          la suspension automatique de vos annonces de véhicules.
        </p>
        <p style="color:#94a3b8;font-size:12px;margin-top:14px;">
          Questions? Contact us at <a href="mailto:partners@bidvex.ca" style="color:#2563eb;">partners@bidvex.ca</a>
        </p>
      </div>
    </div>
    """


def _suspension_email_html(dealer_name: str) -> str:
    return f"""
    <div style="font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;max-width:560px;margin:0 auto;color:#1e293b;">
      <div style="background:#0f172a;padding:24px 28px;border-radius:12px 12px 0 0;">
        <h1 style="color:#fff;margin:0;font-size:20px;">Listings Suspended</h1>
        <p style="color:#94a3b8;margin:6px 0 0;font-size:13px;">Annonces suspendues</p>
      </div>
      <div style="padding:24px;border:1px solid #e2e8f0;border-top:none;border-radius:0 0 12px 12px;font-size:14px;line-height:1.7;">
        <p>Hi {dealer_name or 'there'},</p>
        <p>Your {GRACE_PERIOD_DAYS}-day grace period has ended without a successful annual fee payment.
        All your active vehicle listings have been <strong>suspended</strong> and removed from public view.</p>
        <p>You can reactivate at any time by updating your payment method — your listings will be restored automatically.</p>
        <p style="margin:20px 0;text-align:center;">
          <a href="https://bidvex.com/partner/payment-settings" style="display:inline-block;background:#16a34a;color:#fff;padding:12px 28px;border-radius:8px;text-decoration:none;font-weight:600;">Reactivate Account</a>
        </p>
        <hr style="border:none;border-top:1px solid #e2e8f0;margin:18px 0;" />
        <p style="color:#475569;font-size:13px;">
          <strong>Bonjour,</strong><br/>
          Votre période de grâce de {GRACE_PERIOD_DAYS} jours est terminée sans paiement réussi.
          Toutes vos annonces de véhicules ont été <strong>suspendues</strong>.
          Vous pouvez réactiver votre compte à tout moment en mettant à jour votre moyen de paiement.
        </p>
      </div>
    </div>
    """


# ─── Webhook entry point (called from routes/webhooks.py) ──────────────────
async def handle_dealer_subscription_payment_failed(
    db,
    *,
    event_id: str,
    invoice: dict[str, Any],
    user: dict[str, Any],
) -> dict:
    """Day-1 of the grace period.

    Idempotent via `stripe_event_id` unique index on dealer_compliance_log.
    """
    subscription_id = invoice.get("subscription")
    if not subscription_id:
        return {"skipped": "no_subscription_id"}

    if user.get("vehicle_dealer_subscription_id") != subscription_id:
        return {"skipped": "not_dealer_subscription"}

    # Idempotency
    existing = await db.dealer_compliance_log.find_one({"stripe_event_id": event_id})
    if existing:
        logger.info(f"[iter210] event {event_id} already processed — skipping")
        return {"skipped": "already_processed", "log_id": existing.get("id")}

    now = datetime.now(timezone.utc)
    # Has grace already started? (from earlier retry attempt)
    user_doc = await db.users.find_one({"id": user["id"]}, {"_id": 0, "vehicle_dealer_grace_started_at": 1, "name": 1, "email": 1, "partner_card_last4": 1})
    grace_started_at = (user_doc or {}).get("vehicle_dealer_grace_started_at")
    if not grace_started_at:
        grace_started_at = now
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "vehicle_dealer_grace_started_at": now,
                "vehicle_dealer_grace_expires_at": now + timedelta(days=GRACE_PERIOD_DAYS),
                "vehicle_dealer_subscription_status": "past_due",
            }},
        )

    # Log
    import uuid as _uuid
    log_id = str(_uuid.uuid4())
    await db.dealer_compliance_log.insert_one({
        "id": log_id,
        "stripe_event_id": event_id,
        "event": "payment_failed",
        "user_id": user["id"],
        "subscription_id": subscription_id,
        "invoice_id": invoice.get("id"),
        "amount_due_cents": invoice.get("amount_due", 0),
        "grace_started_at": grace_started_at,
        "grace_expires_at": grace_started_at + timedelta(days=GRACE_PERIOD_DAYS),
        "warning_email_sent": False,
        "created_at": now,
    })

    # Send Day-1 warning email
    email_sent = False
    try:
        from services.email_notifications import send_email
        dealer_name = (user_doc or {}).get("name") or user.get("email") or "Dealer"
        await send_email(
            to_email=user.get("email") or (user_doc or {}).get("email"),
            subject="⚠️ Payment failed — update your card to avoid listing suspension · Paiement échoué",
            html_content=_warning_email_html(dealer_name, last4=(user_doc or {}).get("partner_card_last4")),
        )
        email_sent = True
    except Exception as exc:
        logger.warning(f"[iter210] dealer warning email failed: {exc}")

    await db.dealer_compliance_log.update_one(
        {"id": log_id},
        {"$set": {"warning_email_sent": email_sent}},
    )

    return {
        "log_id": log_id,
        "grace_started_at": grace_started_at.isoformat(),
        "grace_expires_at": (grace_started_at + timedelta(days=GRACE_PERIOD_DAYS)).isoformat(),
        "warning_email_sent": email_sent,
    }


# ─── Day-7 enforcement (called from scheduler) ─────────────────────────────
async def enforce_dealer_grace_period(db) -> dict:
    """Run as daily cron.

    Suspends every dealer whose grace period has expired AND who has not paid yet
    AND who is not already suspended. Idempotent.
    """
    now = datetime.now(timezone.utc)
    candidates = db.users.find(
        {
            "vehicle_dealer_grace_started_at": {"$lte": now - timedelta(days=GRACE_PERIOD_DAYS)},
            "vehicle_dealer_subscription_status": "past_due",
            "$or": [
                {"vehicle_dealer_suspended": {"$exists": False}},
                {"vehicle_dealer_suspended": False},
            ],
        },
        {"_id": 0, "id": 1, "email": 1, "name": 1},
    )
    suspended = 0
    async for u in candidates:
        try:
            from services.dealer_subscription_service import suspend_dealer_for_failed_payment
            await suspend_dealer_for_failed_payment(db, u["id"], reason="annual_fee_failed_after_grace")
            try:
                from services.email_notifications import send_email
                await send_email(
                    to_email=u.get("email"),
                    subject="BidVex Vehicle Dealer — Listings Suspended · Annonces suspendues",
                    html_content=_suspension_email_html(u.get("name") or u.get("email")),
                )
            except Exception as exc:
                logger.warning(f"[iter210] suspension email failed for {u['id']}: {exc}")

            await db.dealer_compliance_log.insert_one({
                "id": f"susp-{u['id']}-{now.isoformat()}",
                "event": "suspended_after_grace",
                "user_id": u["id"],
                "suspended_at": now,
                "created_at": now,
            })
            suspended += 1
        except Exception as exc:
            logger.warning(f"[iter210] dealer suspension failed for {u.get('id')}: {exc}")

    return {"suspended_count": suspended, "checked_at": now.isoformat()}


# ─── Reactivation when payment finally succeeds ────────────────────────────
async def reactivate_dealer_after_payment(db, *, user_id: str) -> None:
    """Clear grace flags + restore listings when a previously-failed sub pays."""
    now = datetime.now(timezone.utc)
    await db.users.update_one(
        {"id": user_id},
        {"$unset": {
            "vehicle_dealer_grace_started_at": "",
            "vehicle_dealer_grace_expires_at": "",
        },
         "$set": {
            "vehicle_dealer_subscription_status": "active",
            "vehicle_dealer_suspended": False,
            "vehicle_dealer_reactivated_at": now,
        }},
    )
    seller = await db.vehicle_sellers.find_one({"user_id": user_id}, {"_id": 0, "id": 1})
    if seller:
        await db.vehicles.update_many(
            {"seller_id": seller["id"], "status": "suspended", "suspended_reason": {"$in": ["annual_fee_failed", "annual_fee_failed_after_grace"]}},
            {"$set": {"status": "active"}, "$unset": {"suspended_reason": "", "suspended_at": ""}},
        )
    await db.dealer_compliance_log.insert_one({
        "id": f"reactivated-{user_id}-{now.isoformat()}",
        "event": "reactivated_after_payment",
        "user_id": user_id,
        "reactivated_at": now,
        "created_at": now,
    })
