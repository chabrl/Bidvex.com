"""
services/payment_collection.py — iter298 BUG 3

Post-settlement payment lifecycle layer. Interprets the output of
`services.auction_settlement.settle_auction` (and the vehicle fee
charge) and:

  • SUCCESS  → stamp `payment_status="payment_collected"` on the listing,
               compute `net_payout_amount` (hammer − 2.5% platform fee),
               enqueue a `payout_pending` row for admin manual payout
               (BidVex is non-custodial — no automatic Stripe payouts),
               issue buyer receipt + seller statement (BUG 4),
               bilingual platform notifications for both parties.
  • NO PM    → create a Stripe Payment Link for the buyer total, email
               it with a 48-hour deadline (`payment_deadline`), stamp
               `payment_status="pending_payment"`. The overdue cron
               flags `payment_overdue` past the deadline.
  • FAILURE  → stamp `payment_status="payment_failed"`, email + notify
               the buyer, alert the admin.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

ADMIN_EMAIL = "charbel911@gmail.com"
PUBLIC_URL = os.environ.get("PUBLIC_BASE_URL") or os.environ.get("FRONTEND_URL") or "https://bidvex.com"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _ensure_stripe_pickup_code(
    db, *, collection: str, listing_id: str, listing_title: str,
    buyer_id: str, seller_id, hammer: float, stripe_pi, lot_number=None,
) -> str:
    """iter302 — idempotent pickup code for a Stripe-collected win.

    Creates/reuses a db.transactions row (so the iter297 seller
    confirm-pickup-code flow works) with commission_already_collected=True
    (Stripe already took the platform fee — the confirm flow must not
    enqueue a second commission charge). Also stamps the code on the
    listing doc for buyer-dashboard display."""
    from routes.transaction_pickup_code import generate_pickup_code

    existing = await db.transactions.find_one(
        {"listing_id": listing_id, "lot_number": lot_number, "pickup_code": {"$exists": True}},
        {"_id": 0, "pickup_code": 1},
    )
    if existing and existing.get("pickup_code"):
        code = existing["pickup_code"]
    else:
        code = generate_pickup_code()
        buyer = await db.users.find_one({"id": buyer_id}, {"_id": 0, "email": 1, "name": 1})
        seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "email": 1, "name": 1}) if seller_id else None
        await db.transactions.insert_one({
            "id": str(uuid.uuid4()),
            "listing_id": listing_id,
            "pickup_code_listing_id": listing_id,
            "lot_number": lot_number,
            "listing_title": listing_title,
            "buyer_id": buyer_id,
            "buyer_email": (buyer or {}).get("email"),
            "seller_id": seller_id,
            "seller_email": (seller or {}).get("email"),
            "pickup_code_seller_id": seller_id,
            "hammer_price": hammer,
            "amount": hammer,
            "payment_method": "stripe",
            "stripe_payment_intent": stripe_pi,
            "status": "paid",
            "payment_confirmed": True,
            "commission_already_collected": True,
            "pickup_code": code,
            "pickup_code_issued_at": _now_iso(),
            "created_at": _now_iso(),
        })
    await db[collection].update_one(
        {"id": listing_id}, {"$set": {"pickup_code": code}}
    )
    return code


async def _stamp(db, collection: str, listing_id: str, fields: Dict[str, Any],
                 lot_number: Optional[Any] = None):
    coll = db[collection]
    if lot_number is not None:
        prefixed = {f"lots.$.{k}": v for k, v in fields.items()}
        await coll.update_one(
            {"id": listing_id, "lots.lot_number": lot_number}, {"$set": prefixed}
        )
        # Mirror top-level payment summary stamps so dashboard queries work.
        await coll.update_one({"id": listing_id}, {"$set": {"updated_at": _now_iso()}})
    else:
        await coll.update_one({"id": listing_id}, {"$set": fields})


async def _enqueue_payout_pending(db, *, listing_id, seller_id, amount, section,
                                  listing_title, lot_number=None):
    """Non-custodial guard — flag for admin review instead of auto-payout."""
    existing = await db.pending_payouts.find_one(
        {"listing_id": listing_id, "lot_number": lot_number, "seller_id": seller_id},
        {"_id": 0, "id": 1},
    )
    if existing:
        return existing["id"]
    pid = str(uuid.uuid4())
    await db.pending_payouts.insert_one({
        "id": pid,
        "listing_id": listing_id,
        "lot_number": lot_number,
        "listing_title": listing_title,
        "seller_id": seller_id,
        "amount": round(float(amount), 2),
        "currency": "CAD",
        "section": section,
        "status": "payout_pending",
        "created_at": _now_iso(),
    })
    return pid


async def create_buyer_payment_link(
    db, *, listing_id: str, listing_title: str, buyer_id: str,
    amount_cad: float, section: str, lot_number: Optional[Any] = None,
) -> Optional[str]:
    """Create a Stripe Payment Link for the buyer's total. Returns URL or
    None on Stripe failure (never raises)."""
    try:
        import stripe
        stripe.api_key = os.environ.get("STRIPE_API_KEY", "")
        link = stripe.PaymentLink.create(
            line_items=[{
                "price_data": {
                    "currency": "cad",
                    "unit_amount": int(round(float(amount_cad) * 100)),
                    "product_data": {"name": f"BidVex — {listing_title[:100]}"},
                },
                "quantity": 1,
            }],
            metadata={
                "type": "auction_win_payment",
                "listing_id": listing_id,
                "lot_number": str(lot_number or ""),
                "buyer_id": buyer_id,
                "section": section,
            },
            after_completion={
                "type": "redirect",
                "redirect": {"url": f"{PUBLIC_URL}/payment-confirmed?ref={listing_id}"},
            },
        )
        return link.url
    except Exception as e:  # noqa: BLE001
        logger.error(f"[payment-collection] PaymentLink.create failed for {listing_id}: {e}")
        return None


async def settle_storage_stripe(db, *, auction: Dict[str, Any], pricing: Dict[str, Any]) -> Dict[str, Any]:
    """iter298 BUG 3 — Storage auctions (Stripe path): charge the winner
    (hammer + 5% platform fee + processing + tax − $50 deposit already
    collected) on their saved card at close. Returns a settlement-shaped
    dict for `finalize_auction_payment`."""
    from services.auction_settlement import _charge_card, _get_default_pm, _to_cents
    from services.payment_idempotency import (
        DuplicateChargeBlocked, mark_charge_failed, mark_charge_succeeded,
        reserve_charge_row,
    )

    result: Dict[str, Any] = {"buyer_charge": None, "warnings": [], "scenario": "storage_stripe"}
    bi = (pricing or {}).get("buyer_invoice") or {}
    hammer = float(bi.get("hammer_price") or auction.get("current_bid") or 0)
    platform_fee = float(bi.get("platform_fee") or 0)
    stripe_recovery = float(bi.get("stripe_recovery") or 0)
    tax = float(bi.get("tax") or 0)
    buyer_total = float(bi.get("total") or 0)
    remaining = float(bi.get("remaining_after_deposit") or buyer_total)
    winner_id = auction.get("winning_bidder_id") or auction.get("winner_user_id")
    facility_receives = float(((pricing or {}).get("facility_invoice") or {}).get("facility_receives") or hammer)

    result["fee_breakdown"] = {
        "hammer_price": hammer,
        "buyer_premium": platform_fee,
        "buyer_taxes": tax,
        "buyer_stripe_fee": stripe_recovery,
        "buyer_total_charged": buyer_total,
        "seller_commission": round(hammer - facility_receives, 2),
        "seller_payout": facility_receives,
    }
    if not winner_id or remaining <= 0:
        if remaining <= 0:
            result["buyer_charge"] = {"applied_from_deposit": buyer_total, "extra_charge": 0}
        return result

    try:
        end_dt = auction.get("end_time")
        try:
            end_ts = int(datetime.fromisoformat(str(end_dt).replace("Z", "+00:00")).timestamp())
        except Exception:  # noqa: BLE001
            end_ts = int(datetime.now(timezone.utc).timestamp())
        charge_row = await reserve_charge_row(
            db,
            auction_id=auction["id"],
            user_id=winner_id,
            charge_type="storage_buyer_full_payment",
            currency="CAD",
            amount=remaining,
            auction_end_ts=end_ts,
            metadata={
                "listing_title": auction.get("title") or auction.get("unit_number") or "Storage Unit",
                "hammer_price": hammer,
                "deposit_credit": float(bi.get("deposit_paid") or 0),
                "scenario": "storage_stripe",
            },
        )
    except DuplicateChargeBlocked as exc:
        result["warnings"].append(str(exc))
        return result

    buyer = await db.users.find_one({"id": winner_id}) or {}
    pm = await _get_default_pm(db, winner_id)
    if not pm or not buyer.get("stripe_customer_id"):
        await mark_charge_failed(db, charge_row["id"], error="no_payment_method_on_file")
        result["warnings"].append("buyer_no_pm")
        return result

    try:
        import stripe
        stripe.api_key = os.environ.get("STRIPE_API_KEY", "")
        pi = await _charge_card(
            db,
            customer_id=buyer.get("stripe_customer_id"),
            payment_method_id=pm["stripe_payment_method_id"],
            amount_cents=_to_cents(remaining),
            currency="CAD",
            description=f"BidVex Storage Purchase – {(auction.get('title') or auction.get('unit_number') or '')[:60]}",
            statement_descriptor="BIDVEX-STOR",
            metadata={
                "type": "storage_buyer_full_payment",
                "auction_id": auction["id"],
                "winner_user_id": winner_id,
                "hammer_price": str(hammer),
            },
            idempotency_key=charge_row["idempotency_key"],
        )
        await mark_charge_succeeded(
            db, charge_row["id"],
            stripe_object_id=pi.id, stripe_object_type="payment_intent",
        )
        result["buyer_charge"] = {"amount": remaining, "stripe_pi": pi.id}
    except Exception as exc:  # noqa: BLE001 — stripe.StripeError + transport errors
        await mark_charge_failed(db, charge_row["id"], error=str(exc))
        result["warnings"].append(f"buyer_charge_failed: {exc}")
    return result


async def finalize_auction_payment(
    db,
    *,
    listing: Dict[str, Any],
    collection: str,                # listings | multi_item_listings | storage_auctions | vehicle_listings
    settlement: Dict[str, Any],
    section: str,                   # marketplace | lots | storage | vehicles
    lot_number: Optional[Any] = None,
    listing_title: Optional[str] = None,
    hammer_override: Optional[float] = None,
    winner_override: Optional[str] = None,
) -> Dict[str, Any]:
    """Interpret a settle_auction result and drive the payment lifecycle.
    Never raises — auction close must not block on payment bookkeeping."""
    out: Dict[str, Any] = {"payment_status": None}
    try:
        listing_id = listing.get("id")
        title = listing_title or listing.get("title") or "Item"
        winner_id = winner_override or (
            listing.get("winner_user_id") or listing.get("winner_id")
            or listing.get("winning_bidder_id") or listing.get("highest_bidder_id")
        )
        seller_id = listing.get("seller_id") or listing.get("facility_owner_id")
        hammer = float(
            hammer_override
            if hammer_override is not None
            else (listing.get("final_price") or listing.get("current_price")
                  or listing.get("current_bid") or 0)
        )
        if not winner_id or hammer <= 0:
            return out

        warnings = settlement.get("warnings") or []
        fee = settlement.get("fee_breakdown") or {}
        buyer_charge = settlement.get("buyer_charge")
        platform_fee = float(fee.get("buyer_premium") or round(hammer * 0.025, 2))
        taxes = float(fee.get("buyer_taxes") or 0)
        processing = float(fee.get("buyer_stripe_fee") or 0)
        total_charged = float(fee.get("buyer_total_charged") or 0)
        net_payout = round(hammer - float(fee.get("seller_commission") or platform_fee), 2)
        from services.notifications_i18n import create_notification

        # ── SUCCESS ───────────────────────────────────────────────────
        if buyer_charge:
            stripe_pi = (buyer_charge or {}).get("stripe_pi")
            await _stamp(db, collection, listing_id, {
                "payment_status": "payment_collected",
                "payment_collected_at": _now_iso(),
                "net_payout_amount": net_payout,
                "payment_transaction_id": stripe_pi,
            }, lot_number=lot_number)
            out["payment_status"] = "payment_collected"

            # iter302 — automatic Connect payout (falls back to the
            # pending-payouts queue + admin notification internally).
            try:
                from services.seller_payouts import process_seller_payout
                payout = await process_seller_payout(
                    db, section=section, listing_id=listing_id, listing_title=title,
                    seller_id=seller_id, net_amount=net_payout, lot_number=lot_number,
                    source_transaction_id=stripe_pi,
                )
                out["payout_status"] = payout.get("status")
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[payment-collection] payout dispatch failed for {listing_id}: {e}")
                await _enqueue_payout_pending(
                    db, listing_id=listing_id, seller_id=seller_id,
                    amount=net_payout, section=section, listing_title=title,
                    lot_number=lot_number,
                )

            # iter302 — pickup code for every winning transaction (Stripe
            # path). Stored on a db.transactions row (so the existing
            # seller confirm-pickup-code flow works) + stamped on the
            # listing for dashboard display + included in receipt email.
            pickup_code = None
            try:
                pickup_code = await _ensure_stripe_pickup_code(
                    db, collection=collection, listing_id=listing_id,
                    listing_title=title, buyer_id=winner_id, seller_id=seller_id,
                    hammer=hammer, stripe_pi=stripe_pi, lot_number=lot_number,
                )
                out["pickup_code"] = pickup_code
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[payment-collection] pickup code failed for {listing_id}: {e}")

            # PM last4 (best-effort)
            last4 = None
            try:
                pm = await db.payment_methods.find_one(
                    {"user_id": winner_id}, {"_id": 0, "last4": 1, "card_last4": 1})
                last4 = (pm or {}).get("last4") or (pm or {}).get("card_last4")
            except Exception:  # noqa: BLE001
                pass

            from services.receipts import issue_transaction_records
            records = await issue_transaction_records(
                db, section=section, listing_id=listing_id, listing_title=title,
                buyer_id=winner_id, seller_id=seller_id, hammer_price=hammer,
                platform_fee=platform_fee, taxes=taxes, processing_fee=processing,
                total_charged=total_charged or None, payment_method_last4=last4,
                transaction_id=stripe_pi, net_payout=net_payout, lot_number=lot_number,
                pickup_code=pickup_code,
            )
            out.update(records)
            await _stamp(db, collection, listing_id, {
                "buyer_receipt_id": records.get("receipt_id"),
                "seller_statement_id": records.get("statement_id"),
            }, lot_number=lot_number)

            try:
                await create_notification(
                    db, user_id=winner_id, kind="payment_collected",
                    params={"title": title, "amount": total_charged or hammer},
                    data={"listing_id": listing_id, "receipt_id": records.get("receipt_id"),
                          "action_url": "/dashboard/buyer"},
                )
                if seller_id:
                    await create_notification(
                        db, user_id=seller_id, kind="payment_collected_seller",
                        params={"title": title, "amount": net_payout},
                        data={"listing_id": listing_id,
                              "statement_id": records.get("statement_id"),
                              "action_url": "/seller/dashboard"},
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[payment-collection] notif failed for {listing_id}: {e}")
            return out

        # ── NO PAYMENT METHOD → Payment link, 72h deadline (iter302) ──
        if "buyer_no_pm" in warnings:
            buyer_total = total_charged or round(hammer + platform_fee + taxes, 2)
            link_url = await create_buyer_payment_link(
                db, listing_id=listing_id, listing_title=title, buyer_id=winner_id,
                amount_cad=buyer_total, section=section, lot_number=lot_number,
            )
            deadline = (datetime.now(timezone.utc) + timedelta(hours=72)).isoformat()
            await _stamp(db, collection, listing_id, {
                "payment_status": "pending_payment",
                "payment_deadline": deadline,
                "payment_link_url": link_url,
                "winner_id": winner_id,
            }, lot_number=lot_number)
            out["payment_status"] = "pending_payment"
            out["payment_link_url"] = link_url

            buyer = await db.users.find_one({"id": winner_id}, {"_id": 0}) or {}
            if buyer.get("email"):
                try:
                    from services.emails.email_system import send_payment_link_email
                    await send_payment_link_email(
                        buyer=buyer, listing_title=title, listing_id=listing_id,
                        total_due=buyer_total, payment_link_url=link_url,
                        deadline_iso=deadline,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"[payment-collection] payment-link email failed: {e}")
            try:
                await create_notification(
                    db, user_id=winner_id, kind="payment_link_sent",
                    params={"title": title, "amount": buyer_total},
                    data={"listing_id": listing_id, "payment_link_url": link_url,
                          "deadline": deadline, "action_url": "/dashboard/buyer"},
                )
            except Exception:  # noqa: BLE001
                pass
            return out

        # ── CHARGE FAILED ─────────────────────────────────────────────
        failed = [w for w in warnings if "charge_failed" in str(w)]
        if failed:
            await _stamp(db, collection, listing_id, {
                "payment_status": "payment_failed",
                "payment_failed_at": _now_iso(),
                "payment_failure_reason": str(failed[0])[:300],
            }, lot_number=lot_number)
            out["payment_status"] = "payment_failed"

            buyer = await db.users.find_one({"id": winner_id}, {"_id": 0}) or {}
            if buyer.get("email"):
                try:
                    from services.emails.email_system import send_payment_failed_email
                    await send_payment_failed_email(
                        buyer=buyer, listing_title=title, listing_id=listing_id,
                        amount=total_charged or hammer,
                    )
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"[payment-collection] failure email failed: {e}")
            try:
                await create_notification(
                    db, user_id=winner_id, kind="payment_failed",
                    params={"title": title, "amount": total_charged or hammer},
                    data={"listing_id": listing_id, "action_url": "/settings?tab=payments"},
                )
            except Exception:  # noqa: BLE001
                pass
            # Admin alert
            try:
                await db.admin_alerts.insert_one({
                    "id": str(uuid.uuid4()),
                    "type": "payment_failed",
                    "listing_id": listing_id,
                    "lot_number": lot_number,
                    "section": section,
                    "buyer_id": winner_id,
                    "amount": total_charged or hammer,
                    "reason": str(failed[0])[:300],
                    "created_at": _now_iso(),
                    "resolved": False,
                })
            except Exception:  # noqa: BLE001
                pass
            return out

        return out
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[payment-collection] finalize failed: {e}")
        return out
