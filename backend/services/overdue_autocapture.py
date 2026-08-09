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
    # iter451 — Use the shared merchandise-total resolver so multi-item
    # per-unit listings (unit=$7, qty=2) auto-capture the correct $14
    # base, not $7. Preserves total-lot pricing / qty=1 behaviour.
    from services.hammer_total import resolve_hammer_total
    hammer = float(resolve_hammer_total(listing)["hammer_total"])
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


async def _record_failure(db, listing: Dict[str, Any], buyer_id: str, attempts: int,
                          reason: str, collection: str = "listings"):
    await db[collection].update_one(
        {"id": listing["id"]},
        {"$set": {"payment_status": "payment_overdue",
                  "payment_retry_attempts": attempts,
                  "payment_last_attempt_at": _now().isoformat(),
                  "overdue_since": listing.get("overdue_since") or listing.get("overdue_at")
                  or _now().isoformat(),
                  "payment_failure_reason": reason[:300]}})
    # iter302 — flag the buyer account on payment failure
    try:
        await db.users.update_one(
            {"id": buyer_id},
            {"$set": {"account_flagged_payment_overdue": True,
                      "account_flagged_payment_overdue_at": _now().isoformat()}})
    except Exception:  # noqa: BLE001
        pass
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


_CAPTURE_COLLECTIONS = [
    ("listings", "marketplace"),
    ("multi_item_listings", "lots"),
    ("storage_auctions", "storage"),
    ("vehicle_listings", "vehicles"),
]

_BID_COLLECTIONS = {
    "listings": ["bids"],
    "multi_item_listings": ["bids", "lot_bids"],
    "vehicle_listings": ["vehicle_bids"],
}


async def _has_payment_consent(db, collection: str, listing: Dict[str, Any], buyer_id: str) -> bool:
    """iter302 — FCAC/Rule H1 gate: only auto-capture when the winning
    buyer's bid carries `payment_authorization_consented: true`."""
    lid = listing["id"]
    if collection == "storage_auctions":
        return any(
            b.get("bidder_id") == buyer_id and b.get("payment_authorization_consented")
            for b in (listing.get("bids") or [])
        )
    for bc in _BID_COLLECTIONS.get(collection, ["bids"]):
        doc = await db[bc].find_one({
            "payment_authorization_consented": True,
            "$and": [
                {"$or": [{"listing_id": lid}, {"vehicle_id": lid},
                         {"auction_id": lid}, {"event_id": lid}]},
                {"$or": [{"bidder_id": buyer_id}, {"user_id": buyer_id}]},
            ],
        }, {"_id": 0})
        if doc:
            return True
    # Embedded bids on the listing doc (multi-lot vehicle events etc.)
    return any(
        (b.get("bidder_id") == buyer_id or b.get("user_id") == buyer_id)
        and b.get("payment_authorization_consented")
        for b in (listing.get("bids") or [])
    )


async def _mark_consent_missing(db, collection: str, listing: Dict[str, Any], buyer_id: str):
    """No standing authorization → never auto-charge. Mark overdue once,
    notify admin + send the buyer a final warning, then leave the listing
    for manual/buyer-initiated settlement."""
    await db[collection].update_one(
        {"id": listing["id"]},
        {"$set": {"payment_status": "payment_overdue",
                  "autocapture_consent_missing": True,
                  "overdue_since": listing.get("overdue_since") or listing.get("overdue_at")
                  or _now().isoformat()}})
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
                amount=_buyer_total(listing), attempt=1, max_attempts=1)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[overdue-capture] consent-missing warning email failed: {e}")
    await _notify_admin(db, listing=listing, reason="no_payment_authorization_consent")


async def process_overdue_autocapture(db) -> Dict[str, Any]:
    """Hourly tick — iter302 timeline. Never raises.

    T+72h (payment_deadline reached) on ALL 4 sections:
      • consent + saved card → off-session capture fires immediately
      • consent missing      → payment_overdue once, admin + buyer notified,
                               no retries, no suspension
      • capture fails / no card → payment_overdue, buyer final warning,
        admin notified; retried hourly up to MAX_ATTEMPTS, then bidding
        privileges suspended.
    """
    out = {"scanned": 0, "captured": 0, "failed": 0, "suspended_skipped": 0,
           "consent_missing": 0}
    try:
        now = _now()
        now_iso = now.isoformat()
        retry_gate = (now - timedelta(minutes=55)).isoformat()

        for collection, section in _CAPTURE_COLLECTIONS:
            candidates = await db[collection].find({
                "autocapture_consent_missing": {"$ne": True},
                "$and": [
                    {"$or": [
                        # T+72h — deadline reached while still unpaid
                        {"payment_status": "pending_payment",
                         "payment_deadline": {"$ne": None, "$lte": now_iso}},
                        # already overdue / previous failed attempts
                        {"payment_status": {"$in": ["overdue", "payment_overdue",
                                                    "payment_failed_final"]}},
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
                            or listing.get("winning_bidder_id") or listing.get("highest_bidder_id"))
                if not buyer_id:
                    continue

                # ── iter302 — consent gate ──
                if not await _has_payment_consent(db, collection, listing, buyer_id):
                    out["consent_missing"] += 1
                    await _mark_consent_missing(db, collection, listing, buyer_id)
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
                                          "no_payment_method_on_file", collection)
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
                            "section": section,
                            "buyer_id": buyer_id,
                            "attempt": str(attempts),
                        },
                        idempotency_key=f"overdue-{listing['id']}-attempt{attempts}",
                    )
                except Exception as exc:  # noqa: BLE001 — stripe + transport errors
                    out["failed"] += 1
                    await _record_failure(db, listing, buyer_id, attempts,
                                          f"charge_failed: {exc}", collection)
                    continue

                # ── SUCCESS — clear overdue, run normal settlement bookkeeping ──
                out["captured"] += 1
                await db[collection].update_one(
                    {"id": listing["id"]},
                    {"$set": {"payment_retry_attempts": attempts,
                              "payment_last_attempt_at": now.isoformat(),
                              "payment_recovered_at": now.isoformat()},
                     "$unset": {"late_penalty_rate": "", "overdue_notified": ""}})
                from services.hammer_total import resolve_hammer_total as _rht
                hammer = float(_rht(listing)["hammer_total"])
                from services.payment_collection import finalize_auction_payment
                await finalize_auction_payment(
                    db, listing=listing, collection=collection,
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
                    section=section,
                )
                logger.info(f"[overdue-capture] RECOVERED ${amount:.2f} for {section} listing {listing['id']} (pi={pi.id})")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[overdue-capture] tick failed: {e}")
    return out
