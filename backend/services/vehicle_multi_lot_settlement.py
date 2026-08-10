"""
services/vehicle_multi_lot_settlement.py — iter295 P1

Per-lot post-auction settlement for multi-lot vehicle events.

When a lot closes (winner or no-bids), this module:

  1. Generates a Vehicle invoice (BP 0%, Platform 2.5%, taxes per
     `services.fee_calculator.PricingManager.vehicle_auction`).
  2. Auto-refunds deposits for losing bidders + unsold lots.
  3. Sends winner + seller email notifications.

Invariants (iter283 zero-regression):

  - Vehicle BP is 0%. Platform fee is 2.5% of hammer.
  - Deposit refund is best-effort; failures log but never block the
    rest of settlement.
  - Idempotent: settling the same lot twice is a no-op (we mark the
    lot doc with `settled_at` and skip on subsequent runs).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict
import logging
import uuid

logger = logging.getLogger("vehicle_multi_lot_settlement")


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _refund_lot_deposits(db, *, event_id: str, lot_id: str, winner_user_id: str | None) -> int:
    """Refund every active deposit on this lot EXCEPT the winner's.
    For unsold lots (no winner) refund every deposit.
    Returns the number of deposits flipped to `refunded`.
    """
    q: Dict[str, Any] = {
        "event_id": event_id,
        "lot_id": lot_id,
        "status": {"$in": ["paid", "pending", "authorized", "held", "succeeded"]},
    }
    if winner_user_id:
        q["bidder_id"] = {"$ne": winner_user_id}

    now = _now()
    refunded = 0
    async for dep in db.vehicle_bid_deposits.find(q):
        try:
            await db.vehicle_bid_deposits.update_one(
                {"id": dep["id"]},
                {
                    "$set": {
                        "status":      "refunded",
                        "refunded_at": now,
                        "refund_reason": "lot_settled" if winner_user_id else "lot_unsold",
                    }
                },
            )
            refunded += 1
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[multi_lot_settle] deposit refund failed for {dep.get('id')}: {e}")

    return refunded


async def _build_lot_invoice(
    db,
    *,
    event: Dict[str, Any],
    lot: Dict[str, Any],
    winner_user: Dict[str, Any],
    seller_user: Dict[str, Any],
) -> Dict[str, Any] | None:
    """Generate the buyer + seller invoice pair for a sold lot. Returns
    the buyer-invoice dict (or None on failure)."""
    try:
        from services.fee_calculator import PricingManager
    except Exception as e:  # noqa: BLE001
        logger.error(f"[multi_lot_settle] PricingManager import failed: {e}")
        return None

    hammer = float(lot.get("current_bid") or 0)
    if hammer <= 0:
        return None

    buyer_province = (
        winner_user.get("province")
        or lot.get("location_province")
        or event.get("location_province")
        or "ON"
    )
    buyer_tier = winner_user.get("subscription_tier", "free")

    pricing = PricingManager.vehicle_auction(
        hammer_price=hammer,
        buyer_province=buyer_province,
        buyer_tier=buyer_tier,
    )
    bi = pricing.buyer_invoice
    now = _now()
    invoice_number = f"VML-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}"

    vehicle_title = (
        f"{lot.get('year', '')} {lot.get('make', '')} {lot.get('model', '')}".strip()
        or lot.get("title")
        or "Multi-Lot Vehicle"
    )

    buyer_invoice = {
        "id":                  str(uuid.uuid4()),
        "invoice_number":      invoice_number,
        "invoice_type":        "buyer_vehicle_fee",
        # Multi-lot anchors
        "event_id":            event["id"],
        "event_title":         event.get("title"),
        "lot_id":              lot["id"],
        "lot_number":          lot.get("lot_number"),
        # Vehicle identity
        "vehicle_id":          lot["id"],   # reuse lot id so existing invoice page works
        "vehicle_vin":         lot.get("vin", ""),
        "vehicle_title":       vehicle_title,
        "auction_id":          event["id"],
        # Parties
        "buyer_id":            winner_user["id"],
        "buyer_email":         winner_user.get("email"),
        "buyer_name":          winner_user.get("full_name", winner_user.get("name", winner_user.get("email"))),
        "buyer_province":      buyer_province,
        "seller_id":           event.get("seller_id"),
        "seller_email":        event.get("seller_email") or seller_user.get("email"),
        # Money
        "hammer_price":        hammer,
        "platform_fee":        bi.fees_subtotal,
        "stripe_recovery":     bi.stripe_recovery,
        "tax_type":            bi.tax_type,
        "tax_label":           bi.tax_label,
        "tax_rate":            bi.tax_rate,
        "tax_total":           bi.tax_amount,
        "subtotal_before_tax": bi.fees_subtotal + bi.stripe_recovery,
        "total_amount":        bi.total,
        "subscription_tier":   buyer_tier,
        "line_items": [
            {"description": ln.description, "type": ln.line_type,
             "amount": ln.amount, "rate": ln.rate}
            for ln in bi.lines
        ],
        # Lifecycle
        "payment_status":      "pending",
        "payment_deadline":    None,   # set by invoice_overdue cron based on tier
        "paid_at":             None,
        "paid_amount":         0.0,
        "deposit_credited":    0.0,
        "penalty_amount":      0.0,
        "created_at":          now,
        "updated_at":          None,
        "due_at":              None,
        "note_en": "BidVex charges a 2.5% platform fee only. The vehicle hammer price is settled directly between buyer and seller.",
        "note_fr": "BidVex facture uniquement des frais de plateforme de 2,5 %. Le prix d'adjudication du véhicule est réglé directement entre l'acheteur et le vendeur.",
    }

    seller_invoice = {
        "id":                  str(uuid.uuid4()),
        "invoice_number":      f"SML-{now.strftime('%Y%m%d')}-{str(uuid.uuid4())[:8].upper()}",
        "invoice_type":        "seller_vehicle_settlement",
        "event_id":            event["id"],
        "event_title":         event.get("title"),
        "lot_id":              lot["id"],
        "lot_number":          lot.get("lot_number"),
        "vehicle_id":          lot["id"],
        "vehicle_vin":         lot.get("vin", ""),
        "vehicle_title":       vehicle_title,
        "auction_id":          event["id"],
        "buyer_invoice_id":    buyer_invoice["id"],
        "seller_id":           event.get("seller_id"),
        "seller_email":        event.get("seller_email") or seller_user.get("email"),
        "buyer_id":            winner_user["id"],
        "hammer_price":        hammer,
        "seller_commission":   0.0,
        "seller_commission_rate": 0.0,
        "net_payout":          hammer,
        "line_items": [
            {"description": "Vehicle hammer price — settled directly with buyer", "type": "info", "amount": hammer},
            {"description": "BidVex commission on vehicles", "type": "deduction", "amount": 0.0},
        ],
        "settlement_status":   "pending_buyer_payment",
        "settled_at":          None,
        "created_at":          now,
        "note_en": "Vehicle sales: seller receives full hammer price directly from buyer. BidVex does not collect or hold vehicle sale funds.",
        "note_fr": "Ventes de véhicules : le vendeur reçoit le prix d'adjudication complet directement de l'acheteur. BidVex ne collecte ni ne détient les fonds de vente de véhicules.",
    }

    try:
        await db.vehicle_invoices.insert_one(buyer_invoice)
        await db.vehicle_invoices.insert_one(seller_invoice)
    except Exception as e:  # noqa: BLE001
        logger.error(f"[multi_lot_settle] invoice insert failed: {e}")
        return None

    return buyer_invoice


async def settle_lot(db, *, event: Dict[str, Any], lot: Dict[str, Any]) -> Dict[str, Any]:
    """Settle ONE lot. Safe to call multiple times — second call is a
    no-op via the `settled_at` flag.

    Returns a small summary `{settled, refunded_count, invoice_number?}`
    for observability + tests.
    """
    if lot.get("settled_at"):
        return {"settled": False, "reason": "already_settled"}

    event_id = event["id"]
    lot_id = lot["id"]
    winner_id = lot.get("winner_user_id")

    summary: Dict[str, Any] = {"settled": True, "lot_id": lot_id, "event_id": event_id}

    # 1) Refund losing-bidder deposits + unsold-lot deposits.
    summary["refunded_count"] = await _refund_lot_deposits(
        db, event_id=event_id, lot_id=lot_id, winner_user_id=winner_id,
    )

    invoice: Dict[str, Any] | None = None
    # 2) Generate invoice + send emails ONLY when there is a winner.
    if winner_id:
        winner = await db.users.find_one({"id": winner_id}, {"_id": 0})
        seller = await db.users.find_one({"id": event.get("seller_id")}, {"_id": 0}) or {}
        if winner:
            invoice = await _build_lot_invoice(
                db, event=event, lot=lot, winner_user=winner, seller_user=seller,
            )
            if invoice:
                summary["invoice_id"]     = invoice["id"]
                summary["invoice_number"] = invoice["invoice_number"]

                # Fire emails (best-effort; never block settlement).
                # iter460 — dedup gate: one buyer + one seller email per
                # (event_id, user_id). Vehicle multi-lot events close per
                # lot; the first sold lot fires the buyer's / seller's
                # notification; subsequent lots on the same event are
                # suppressed so the buyer never receives N duplicates.
                try:
                    from services.emails.email_marketplace import (
                        send_auction_won_email,
                        send_auction_sold_email,
                    )
                    from services.emails.email_system import send_invoice_created_email
                    from services.settlement_email_dedup import claim_settlement_email as _sed_claim
                    # Invoice-created email is an INVOICE trigger (out of
                    # scope per user directive) — do NOT gate it here.
                    await send_invoice_created_email(invoice)

                    _buyer_claim = await _sed_claim(
                        db, kind="auction_won",
                        auction_id=event_id, user_id=winner.get("id"),
                    )
                    if _buyer_claim:
                        await send_auction_won_email(
                            to_email=winner.get("email"),
                            to_name=winner.get("full_name") or winner.get("name") or winner.get("email") or "",
                            auction_id=invoice["id"],
                            item_name=invoice["vehicle_title"],
                            hammer_price=invoice["hammer_price"],
                            platform_fee=invoice["platform_fee"],
                            seller_name=(seller.get("full_name") or seller.get("business_name")
                                         or seller.get("email") or "Seller"),
                            seller_contact=(seller.get("phone") or seller.get("email")
                                            or "Available in your BidVex dashboard"),
                            is_vehicle=True,
                            buyer_province=invoice["buyer_province"],
                            payment_deadline=None,
                        )
                    if seller.get("email"):
                        _seller_claim = await _sed_claim(
                            db, kind="seller_sold",
                            auction_id=event_id, user_id=event.get("seller_id"),
                        )
                        if _seller_claim:
                            await send_auction_sold_email(
                                seller_email=seller.get("email"),
                                seller_name=(seller.get("full_name") or seller.get("business_name")
                                             or seller.get("email") or "Seller"),
                                vehicle_title=invoice["vehicle_title"],
                                final_price=invoice["hammer_price"],
                                commission=0.0,
                                net_payout=invoice["hammer_price"],
                            )
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"[multi_lot_settle] email dispatch failed: {e}")

                # iter298 BUG 3/4 — Per-lot automatic platform-fee charge
                # (2.5% + Stripe recovery, BP=0%) fired at LOT close, not
                # event end. Stamps the payment lifecycle on the lot and
                # issues buyer receipt + seller statement.
                try:
                    from services.vehicle_fee_service import (
                        calculate_vehicle_fee, create_vehicle_fee_charge,
                    )
                    hammer = float(invoice["hammer_price"])
                    fee_result = await create_vehicle_fee_charge(
                        db,
                        auction_id=f"{event_id}:lot:{lot_id}",
                        buyer_id=winner_id,
                        hammer_price=hammer,
                    )
                    _fees = calculate_vehicle_fee(hammer)
                    lot_stamp: Dict[str, Any] = {}
                    if fee_result.get("success"):
                        lot_stamp = {
                            "lots.$.payment_status": "payment_collected",
                            "lots.$.payment_collected_at": _now(),
                            "lots.$.payment_transaction_id": fee_result.get("payment_intent_id"),
                            "lots.$.net_payout_amount": hammer,
                        }
                        from services.receipts import issue_transaction_records
                        await issue_transaction_records(
                            db, section="vehicles",
                            listing_id=event_id,
                            listing_title=invoice["vehicle_title"],
                            buyer_id=winner_id,
                            seller_id=event.get("seller_id"),
                            hammer_price=hammer,
                            platform_fee=float(_fees["net_commission"]),
                            taxes=float(invoice.get("tax_total") or 0),
                            processing_fee=float(_fees["stripe_processing_fee"]),
                            total_charged=float(_fees["total_charge"]),
                            transaction_id=fee_result.get("payment_intent_id"),
                            net_payout=hammer,
                            lot_number=lot.get("lot_number"),
                        )
                    else:
                        lot_stamp = {
                            "lots.$.payment_status": "payment_failed",
                            "lots.$.payment_failed_at": _now(),
                            "lots.$.payment_failure_reason": str(fee_result.get("error"))[:300],
                        }
                        from services.notifications_i18n import create_notification
                        await create_notification(
                            db, user_id=winner_id, kind="payment_failed",
                            params={"title": invoice["vehicle_title"],
                                    "amount": float(_fees["total_charge"])},
                            data={"event_id": event_id, "lot_id": lot_id,
                                  "action_url": "/settings?tab=payments"},
                        )
                    if lot_stamp:
                        await db.vehicle_multi_lot_auctions.update_one(
                            {"id": event_id, "lots.id": lot_id},
                            {"$set": lot_stamp},
                        )
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"[multi_lot_settle] per-lot fee charge failed: {e}")

    # 3) Stamp the lot as settled (idempotent guard for next ticks).
    now = _now()
    try:
        await db.vehicle_multi_lot_auctions.update_one(
            {"id": event_id, "lots.id": lot_id},
            {
                "$set": {
                    "lots.$.settled_at":  now,
                    "lots.$.invoice_id":  invoice["id"] if invoice else None,
                    "updated_at":         now,
                }
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.error(f"[multi_lot_settle] stamp settled_at failed: {e}")

    logger.info(
        f"[multi_lot_settle] lot {lot_id} settled — winner={winner_id} "
        f"refunds={summary['refunded_count']} invoice={summary.get('invoice_number','—')}"
    )
    return summary
