"""
services/overdue_autocapture.py — iter300 P1

Hourly auto-capture of overdue auction payments.

Pipeline (marketplace `listings`):
  pending_payment ──(48h link expiry, existing cron)──▶ payment_status="overdue"
  overdue + 48h  ──(THIS job)──▶ re-attempt Stripe charge on saved PM
      • success → payment_collected + normal settlement bookkeeping
                  (receipts, payout queue, notifications) via
                  services.payment_collection.finalize_auction_payment
      • failure / no PM → payment_status="payment_failed_final",
                  buyer final-warning email+notification, admin alert.
                  Retried hourly up to 3 total attempts.
      • 3 failed attempts → buyer `bidding_suspended=True`, admin notified.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict

logger = logging.getLogger(__name__)

MAX_ATTEMPTS = 3
ADMIN_EMAIL = "charbel911@gmail.com"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _parse(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:  # noqa: BLE001
        return None


def _buyer_total(listing: Dict[str, Any]) -> float:
    hammer = float(listing.get("final_price") or listing.get("current_price") or 0)
    platform_fee = round(hammer * 0.025, 2)
    penalty = float(listing.get("late_penalty_amount") or 0)
    return round(hammer + platform_fee + penalty, 2)


async def _notify_admin(db, *, listing: Dict[str, Any], reason: str, suspended: bool = False):
    try:
        await db.admin_alerts.insert_one({
            "id": str(uuid.uuid4()),
            "type": "overdue_autocapture_failed" if not suspended else "buyer_bidding_suspended",
            "listing_id": listing.get("id"),
            "buyer_id": listing.get("winner_id") or listing.get("winner_user_id"),
            "amount": _buyer_total(listing),
            "reason": reason[:300],
            "created_at": _now().isoformat(),
            "resolved": False,
        })
    except Exception:  # noqa: BLE001
        pass
    try:
        admin = await db.users.find_one({"email": ADMIN_EMAIL}, {"_id": 0, "id": 1})
        if admin:
            from services.notifications_i18n import create_notification
            kind = "bidding_suspended_admin" if suspended else "overdue_capture_failed_admin"
            await create_notification(
                db, user_id=admin["id"], kind=kind,
                params={"title": listing.get("title", "Item"), "amount": _buyer_total(listing)},
                data={"listing_id": listing.get("id"), "action_url": "/admin?tab=users"})
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[overdue-capture] admin notif failed: {e}")


async def _suspend_buyer(db, buyer_id: str, listing: Dict[str, Any]):
    await db.users.update_one(
        {"id": buyer_id},
        {"$set": {"bidding_suspended": True,
                  "bidding_suspended_at": _now().isoformat(),
                  "bidding_suspended_reason": f"3 failed payment attempts — listing {listing.get('id')}"}})
    try:
        from services.notifications_i18n import create_notification
        await create_notification(
            db, user_id=buyer_id, kind="bidding_suspended",
            params={"title": listing.get("title", "Item")},
            data={"listing_id": listing.get("id")})
    except Exception:  # noqa: BLE001
        pass
    buyer = await db.users.find_one({"id": buyer_id}, {"_id": 0, "email": 1, "name": 1})
    if buyer and buyer.get("email"):
        try:
            from services.emails.email_engagement import send_bidding_suspended_email
            await send_bidding_suspended_email(
                to_email=buyer["email"], to_name=buyer.get("name") or "Bidder",
                listing_title=listing.get("title", "Item"))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[overdue-capture] suspension email failed: {e}")
    await _notify_admin(db, listing=listing, reason="bidding suspended after 3 failed attempts",
                        suspended=True)
    logger.info(f"[overdue-capture] buyer {buyer_id} bidding SUSPENDED")


async def _record_failure(db, listing: Dict[str, Any], buyer_id: str, attempts: int, reason: str):
    await db.listings.update_one(
        {"id": listing["id"]},
        {"$set": {"payment_status": "payment_failed_final",
                  "payment_retry_attempts": attempts,
                  "payment_last_attempt_at": _now().isoformat(),
                  "overdue_since": listing.get("overdue_since") or listing.get("overdue_at")
                  or _now().isoformat(),
                  "payment_failure_reason": reason[:300]}})
    # Buyer final warning (every failed attempt — max 3)
    try:
        from services.notifications_i18n import create_notification
        await create_notification(
            db, user_id=buyer_id, kind="payment_final_warning",
            params={"title": listing.get("title", "Item"), "amount": _buyer_total(listing)},
            data={"listing_id": listing["id"], "action_url": "/dashboard/buyer"})
    except Exception:  # noqa: BLE001
        pass
    buyer = await db.users.find_one({"id": buyer_id}, {"_id": 0, "email": 1, "name": 1})
    if buyer and buyer.get("email"):
        try:
            from services.emails.email_engagement import send_payment_final_warning_email
            await send_payment_final_warning_email(
                to_email=buyer["email"], to_name=buyer.get("name") or "Bidder",
                listing_title=listing.get("title", "Item"),
                amount=_buyer_total(listing), attempt=attempts, max_attempts=MAX_ATTEMPTS)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[overdue-capture] warning email failed: {e}")
    await _notify_admin(db, listing=listing, reason=reason)
    if attempts >= MAX_ATTEMPTS:
        await _suspend_buyer(db, buyer_id, listing)


async def process_overdue_autocapture(db) -> Dict[str, Any]:
    """Hourly tick. Never raises."""
    out = {"scanned": 0, "captured": 0, "failed": 0, "suspended_skipped": 0}
    try:
        now = _now()
        cutoff_48h = (now - timedelta(hours=48)).isoformat()
        retry_gate = (now - timedelta(minutes=55)).isoformat()

        candidates = await db.listings.find({
            "payment_status": {"$in": ["overdue", "payment_overdue", "payment_failed_final"]},
            "$and": [
                {"$or": [
                    {"overdue_since": {"$lte": cutoff_48h}},
                    {"overdue_at": {"$lte": cutoff_48h}},
                ]},
                {"$or": [
                    {"payment_last_attempt_at": {"$exists": False}},
                    {"payment_last_attempt_at": {"$lte": retry_gate}},
                ]},
            ],
        }, {"_id": 0}).to_list(50)

        for listing in candidates:
            out["scanned"] += 1
            attempts = int(listing.get("payment_retry_attempts") or 0)
            if attempts >= MAX_ATTEMPTS:
                out["suspended_skipped"] += 1
                continue
            buyer_id = (listing.get("winner_id") or listing.get("winner_user_id")
                        or listing.get("winning_bidder_id"))
            if not buyer_id:
                continue
            attempts += 1
            amount = _buyer_total(listing)

            # ── Saved payment method? ──
            from services.auction_settlement import _charge_card, _get_default_pm, _to_cents
            buyer = await db.users.find_one(
                {"id": buyer_id}, {"_id": 0, "stripe_customer_id": 1})
            pm = await _get_default_pm(db, buyer_id)
            if not pm or not (buyer or {}).get("stripe_customer_id"):
                out["failed"] += 1
                await _record_failure(db, listing, buyer_id, attempts,
                                      "no_payment_method_on_file")
                continue

            try:
                pi = await _charge_card(
                    db,
                    customer_id=buyer["stripe_customer_id"],
                    payment_method_id=pm["stripe_payment_method_id"],
                    amount_cents=_to_cents(amount),
                    currency="CAD",
                    description=f"BidVex Overdue Payment Recovery – {(listing.get('title') or '')[:60]}",
                    statement_descriptor="BIDVEX",
                    metadata={
                        "type": "overdue_autocapture",
                        "listing_id": listing["id"],
                        "buyer_id": buyer_id,
                        "attempt": str(attempts),
                    },
                    idempotency_key=f"overdue-{listing['id']}-attempt{attempts}",
                )
            except Exception as exc:  # noqa: BLE001 — stripe + transport errors
                out["failed"] += 1
                await _record_failure(db, listing, buyer_id, attempts,
                                      f"charge_failed: {exc}")
                continue

            # ── SUCCESS — clear overdue, run normal settlement bookkeeping ──
            out["captured"] += 1
            await db.listings.update_one(
                {"id": listing["id"]},
                {"$set": {"payment_retry_attempts": attempts,
                          "payment_last_attempt_at": now.isoformat(),
                          "payment_recovered_at": now.isoformat()},
                 "$unset": {"late_penalty_rate": "", "overdue_notified": ""}})
            hammer = float(listing.get("final_price") or listing.get("current_price") or 0)
            from services.payment_collection import finalize_auction_payment
            await finalize_auction_payment(
                db, listing=listing, collection="listings",
                settlement={
                    "buyer_charge": {"amount": amount, "stripe_pi": pi.id},
                    "warnings": [],
                    "fee_breakdown": {
                        "hammer_price": hammer,
                        "buyer_premium": round(hammer * 0.025, 2),
                        "buyer_taxes": 0,
                        "buyer_stripe_fee": 0,
                        "buyer_total_charged": amount,
                        "seller_commission": round(hammer * 0.025, 2),
                        "seller_payout": round(hammer * 0.975, 2),
                    },
                },
                section="marketplace",
            )
            logger.info(f"[overdue-capture] RECOVERED ${amount:.2f} for listing {listing['id']} (pi={pi.id})")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[overdue-capture] tick failed: {e}")
    return out
