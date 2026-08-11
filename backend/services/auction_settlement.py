"""
Auction Settlement — single entry point on auction close
=========================================================
Forks payment flow based on `listing.payment_method`:

  • "cash" / "etransfer"  → Scenario A
        Charge BUYER commission only (deposit credited if covers it)
        Charge SELLER commission separately
        Buyer pays full hammer to seller offline.

  • "stripe"              → Scenario B
        Charge BUYER full (hammer + commission - deposit_already_paid)
        Transfer payout to SELLER via Stripe Connect.
        Validate winner_user_id matches charge.user_id (WINNER_MISMATCH_BLOCKED).

Used by:
  • services.scheduled_jobs.process_ended_auctions  (marketplace)
  • services.scheduled_jobs.process_ended_storage_auctions  (storage)
  • services.vehicle_auction_handler  (vehicle)
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Optional

import stripe

from services.payment_idempotency import (
    DuplicateChargeBlocked,
    mark_charge_failed,
    mark_charge_succeeded,
    reserve_charge_row,
    rollback_stripe_charge,
)
from services.fee_calculator import calculate_fee, promo_first_listing_waiver_applies

logger = logging.getLogger(__name__)


def _to_cents(amount: float) -> int:
    return int(round(float(amount) * 100))



# iter244 Mission 1 — Settlement-time promotion override.
async def _apply_settlement_promotions(
    *,
    db,
    winner_user_id: str,
    seller_id: str,
    buyer_premium_amount: float,
    seller_commission_amount: float,
    auction_id: str,
    listing_type: str = "lots",
) -> Dict[str, Any]:
    """Apply active admin promotions to buyer_premium AND seller_commission
    at the moment of bid settlement. Discount amounts are recorded
    atomically via `record_promotion_usage()` so promotion counters reflect
    real revenue impact.

    Returns:
        {
          buyer_discount_amount: float,
          seller_discount_amount: float,
          buyer_promotion_id: str | None,
          seller_promotion_id: str | None,
          buyer_coupon_code: str | None,
          seller_coupon_code: str | None,
        }

    Failures (e.g. transient DB error in the promotion lookup) are
    swallowed and logged — settlement must NEVER block on a promotion
    bookkeeping issue.
    """
    out: Dict[str, Any] = {
        "buyer_discount_amount": 0.0,
        "seller_discount_amount": 0.0,
        "buyer_promotion_id": None,
        "seller_promotion_id": None,
        "buyer_coupon_code": None,
        "seller_coupon_code": None,
    }
    try:
        from services.promotion_runtime import apply_and_record_discount
        # Buyer side.
        bd = await apply_and_record_discount(
            db=db,
            user_id=winner_user_id,
            transaction_type="buyer_premium",
            base_amount_cad=float(buyer_premium_amount),
            listing_type=listing_type,
            transaction_id=auction_id,
            record_usage=True,
        )
        if bd.applies:
            out["buyer_discount_amount"] = float(bd.discount_amount)
            out["buyer_promotion_id"] = bd.promotion_id
            out["buyer_coupon_code"] = bd.coupon_code
        # Seller side.
        sd = await apply_and_record_discount(
            db=db,
            user_id=seller_id,
            transaction_type="seller_commission",
            base_amount_cad=float(seller_commission_amount),
            listing_type=listing_type,
            transaction_id=auction_id,
            record_usage=True,
        )
        if sd.applies:
            out["seller_discount_amount"] = float(sd.discount_amount)
            out["seller_promotion_id"] = sd.promotion_id
            out["seller_coupon_code"] = sd.coupon_code
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[settlement-promo] failed: {type(e).__name__}: {e}")
    return out



async def _get_default_pm(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Find the user's default Stripe payment method on file."""
    pm = await db.payment_methods.find_one(
        {"user_id": user_id, "is_default": True}, {"_id": 0}
    )
    if not pm:
        pm = await db.payment_methods.find_one({"user_id": user_id}, {"_id": 0})
    return pm


async def _log_payment_event(db, *, event: str, **payload):
    payload.update({
        "id": str(uuid.uuid4()),
        "event": event,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    await db.payment_events.insert_one(payload)


async def _record_charge_with_atomic_rollback(
    db,
    *,
    charge_row: Dict[str, Any],
    pi: Any,
    db_writes: Optional[list] = None,
) -> bool:
    """
    Mark charge succeeded + run any extra DB writes inside a try-block.
    On any DB exception → trigger Stripe rollback (refund/cancel) immediately.
    """
    try:
        await mark_charge_succeeded(
            db,
            charge_row["id"],
            stripe_object_id=pi.id,
            stripe_object_type="payment_intent",
        )
        if db_writes:
            for op in db_writes:
                await op
        return True
    except Exception as exc:
        logger.exception(f"DB write after Stripe success failed — rolling back: {exc}")
        charge_row["stripe_object_id"] = pi.id
        charge_row["stripe_object_type"] = "payment_intent"
        await rollback_stripe_charge(charge_row, reason="db_write_failed")
        await db.payment_charges.update_one(
            {"id": charge_row["id"]},
            {"$set": {
                "status": "rolled_back",
                "error": f"db_write_failed: {str(exc)[:300]}",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        await _log_payment_event(
            db,
            event="ROLLBACK_REFUND",
            charge_id=charge_row["id"],
            stripe_payment_intent_id=pi.id,
            error=str(exc)[:500],
        )
        return False


async def _charge_card(
    db,
    *,
    customer_id: str,
    payment_method_id: str,
    amount_cents: int,
    currency: str,
    description: str,
    statement_descriptor: Optional[str],
    metadata: Dict[str, Any],
    idempotency_key: str,
    transfer_destination: Optional[str] = None,
    application_fee_amount_cents: Optional[int] = None,
) -> Any:
    """Create + confirm a PaymentIntent in one shot using a saved card."""
    stripe.api_key = os.environ.get("STRIPE_API_KEY", "")
    kwargs: Dict[str, Any] = dict(
        amount=amount_cents,
        currency=currency.lower(),
        customer=customer_id,
        payment_method=payment_method_id,
        confirm=True,
        off_session=True,
        description=description[:1000],
        metadata=metadata,
    )
    if statement_descriptor:
        # Stripe limits to 22 chars
        kwargs["statement_descriptor_suffix"] = statement_descriptor[:22]
    if transfer_destination:
        kwargs["transfer_data"] = {"destination": transfer_destination}
        if application_fee_amount_cents is not None:
            kwargs["application_fee_amount"] = application_fee_amount_cents
    return stripe.PaymentIntent.create(idempotency_key=idempotency_key, **kwargs)


# ============================================================
# Scenario A — Cash / E-Transfer (commission only)
# ============================================================

async def settle_cash_or_etransfer(
    db,
    *,
    auction_id: str,
    listing: Dict[str, Any],
    winner_user_id: str,
    seller_id: str,
    hammer_price: float,
    currency: str,
    auction_end_ts: int,
) -> Dict[str, Any]:
    """
    Cash/E-Transfer settlement:
      • Buyer charged COMMISSION ONLY (deposit credited).
      • Seller charged COMMISSION ONLY.
      • Buyer pays seller full hammer offline.
    """
    currency = (currency or "CAD").upper()
    result = {"buyer_charge": None, "seller_charge": None, "warnings": []}

    # ---- BUYER COMMISSION ----
    buyer = await db.users.find_one({"id": winner_user_id})
    buyer_tier = (buyer or {}).get("subscription_tier", "free")
    seller = await db.users.find_one({"id": seller_id})
    seller_tier = (seller or {}).get("subscription_tier", "free")
    buyer_prov = (buyer or {}).get("province") or (buyer or {}).get("business_province") or "QC"
    seller_prov = (seller or {}).get("province") or (seller or {}).get("business_province") or "QC"

    # iter350 — Single source of truth: calculate_fee() with per-user Place-of-Supply
    fee = calculate_fee(
        hammer_price=float(hammer_price),
        auction_type="lots",
        seller_account_type="individual",
        seller_tier=seller_tier,
        buyer_account_type="individual",
        buyer_tier=buyer_tier,
        payment_method="stripe",
        card_type="domestic",
        buyer_province=buyer_prov,
        seller_province=seller_prov,
    )
    buyer_commission = float(fee["buyer_premium"]) + float(fee["buyer_taxes"]) + float(fee["buyer_stripe_recovery"])
    seller_commission = float(fee["seller_commission_total"])

    # iter298 BUG 3/4 — expose the fee breakdown for receipts/statements.
    result["fee_breakdown"] = {
        "fee_model_version": fee.get("fee_model_version", "iter350"),
        "hammer_price": float(hammer_price),
        "buyer_premium": float(fee["buyer_premium"]),
        "buyer_stripe_recovery": float(fee.get("buyer_stripe_recovery", fee.get("buyer_stripe_fee", 0))),
        "buyer_taxes": float(fee["buyer_taxes"]),
        "buyer_tax_label": fee.get("buyer_tax_label", ""),
        "buyer_tax_province": fee.get("buyer_tax_province", buyer_prov),
        "buyer_total_charged": buyer_commission,
        "seller_commission": float(fee["seller_commission"]),
        "seller_stripe_recovery": float(fee.get("seller_stripe_recovery", 0)),
        "seller_taxes": float(fee.get("seller_taxes", 0)),
        "seller_tax_label": fee.get("seller_tax_label", ""),
        "seller_tax_province": fee.get("seller_tax_province", seller_prov),
        "seller_payout": float(fee["seller_payout"]),
        # ── iter476 itemized snapshot (populated from the same authoritative FeeResult) ──
        # BUYER SIDE — hammer tax is NOT collected here (individual/enterprise
        # sellers don't have BidVex collect hammer GST/QST; that only applies
        # to certain business paths and is handled by other verticals).
        "hammer_gst": 0.0,
        "hammer_qst": 0.0,
        "buyer_premium_gst": float(fee.get("buyer_gst", 0)),
        "buyer_premium_qst": float(fee.get("buyer_qst", 0)),
        # Service fee (BidVex platform service) is bundled inside
        # buyer_premium for the individual/enterprise route — expose it
        # as 0/none to avoid double-counting.
        "service_fee": 0.0,
        "service_fee_gst": 0.0,
        "service_fee_qst": 0.0,
        "stripe_fee": float(fee.get("buyer_stripe_recovery", 0)),
        "stripe_fee_charged_to": "buyer",   # buyer bears the gross-up
        # SELLER SIDE
        "seller_commission_gst": float(fee.get("seller_gst", 0)),
        "seller_commission_qst": float(fee.get("seller_qst", 0)),
        "other_deductions": float(fee.get("seller_stripe_recovery", 0)),
        # Meta
        "buyer_premium_rate": float(fee.get("buyer_premium_rate", 0)),
        "seller_commission_rate": float(fee.get("seller_commission_rate", 0)),
        "seller_is_tax_registered": False,
    }
    # Snapshot the itemized block once (before promo discounts) so the
    # persisted receipt reflects the authoritative pre-discount split.
    result["itemized"] = {
        k: result["fee_breakdown"][k]
        for k in (
            "hammer_gst", "hammer_qst",
            "buyer_premium", "buyer_premium_gst", "buyer_premium_qst",
            "service_fee", "service_fee_gst", "service_fee_qst",
            "stripe_fee", "stripe_fee_charged_to",
            "seller_commission", "seller_commission_gst", "seller_commission_qst",
            "other_deductions",
            "buyer_premium_rate", "seller_commission_rate",
            "seller_is_tax_registered",
        )
    }

    # iter244 Mission 1 — Apply active promotion overrides at settlement.
    # Discounts are computed BEFORE deposit credits so the savings are
    # always visible in the audit ledger. Promotion_id + discount metadata
    # are appended to the charge-row metadata block below.
    promo_meta = await _apply_settlement_promotions(
        db=db,
        winner_user_id=winner_user_id,
        seller_id=seller_id,
        buyer_premium_amount=float(fee["buyer_premium"]),
        seller_commission_amount=seller_commission,
        auction_id=auction_id,
        listing_type=listing.get("listing_type") or "lots",
    )
    # Apply discounts.
    buyer_commission = max(0.0, round(buyer_commission - promo_meta["buyer_discount_amount"], 2))
    seller_commission = max(0.0, round(seller_commission - promo_meta["seller_discount_amount"], 2))

    # iter340 — Canada-Day promo: the account's FIRST listing settles with
    # zero seller commission. Consumption is atomic/idempotent.
    if seller_commission > 0 and promo_first_listing_waiver_applies(seller):
        from services.trial_promo import try_consume_first_listing_free
        if await try_consume_first_listing_free(db, seller_id):
            result["fee_breakdown"]["promo_first_listing_waiver"] = seller_commission
            seller_commission = 0.0

    # --- Deposit credit lookup (winner's deposit, if any) ---
    deposit_doc = await db.bidding_deposits.find_one(
        {"auction_id": auction_id, "user_id": winner_user_id, "status": {"$in": ["held", "authorized", "succeeded"]}},
        {"_id": 0},
    )
    if not deposit_doc:
        deposit_doc = await db.storage_deposits.find_one(
            {"auction_id": auction_id, "user_id": winner_user_id, "status": {"$in": ["held", "authorized", "succeeded"]}},
            {"_id": 0},
        )

    deposit_amount = float(deposit_doc.get("amount", 0)) if deposit_doc else 0.0
    remaining_buyer = max(0.0, round(buyer_commission - deposit_amount, 2))

    if deposit_amount >= buyer_commission and deposit_amount > 0 and deposit_doc:
        # Full deposit covers commission → capture deposit, no extra charge
        try:
            stripe.api_key = os.environ.get("STRIPE_API_KEY", "")
            stripe.PaymentIntent.capture(
                deposit_doc["stripe_payment_intent_id"],
                amount_to_capture=_to_cents(buyer_commission),
                idempotency_key=f"deposit_capture_{auction_id}_{winner_user_id}_{auction_end_ts}",
            )
            await db.bidding_deposits.update_one(
                {"id": deposit_doc["id"]},
                {"$set": {
                    "status": "applied",
                    "applied_amount": buyer_commission,
                    "applied_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            result["buyer_charge"] = {"applied_from_deposit": buyer_commission, "extra_charge": 0}
            await _log_payment_event(
                db,
                event="BUYER_COMMISSION_FROM_DEPOSIT",
                auction_id=auction_id, user_id=winner_user_id,
                amount=buyer_commission, currency=currency,
            )
        except Exception as exc:
            logger.error(f"deposit capture failed: {exc}")
            result["warnings"].append(f"deposit_capture_failed: {exc}")
    elif remaining_buyer > 0:
        # Reserve charge row + execute Stripe call for remainder
        try:
            charge_row = await reserve_charge_row(
                db,
                auction_id=auction_id,
                user_id=winner_user_id,
                charge_type="buyer_commission",
                currency=currency,
                amount=remaining_buyer,
                auction_end_ts=auction_end_ts,
                metadata={
                    "listing_title": listing.get("title", ""),
                    "hammer_price": hammer_price,
                    "deposit_credit": deposit_amount,
                    "scenario": "cash_or_etransfer",
                    # iter244 Mission 1 — Promotion metadata for ledger audit.
                    "buyer_promotion_id": promo_meta.get("buyer_promotion_id"),
                    "buyer_coupon_code": promo_meta.get("buyer_coupon_code"),
                    "buyer_discount_amount": promo_meta.get("buyer_discount_amount", 0.0),
                    "seller_promotion_id": promo_meta.get("seller_promotion_id"),
                    "seller_coupon_code": promo_meta.get("seller_coupon_code"),
                    "seller_discount_amount": promo_meta.get("seller_discount_amount", 0.0),
                },
            )
        except DuplicateChargeBlocked as exc:
            await _log_payment_event(
                db, event="DUPLICATE_CHARGE_BLOCKED",
                auction_id=auction_id, user_id=winner_user_id,
                charge_type="buyer_commission",
            )
            result["warnings"].append(str(exc))
        else:
            pm = await _get_default_pm(db, winner_user_id)
            if not pm:
                await mark_charge_failed(db, charge_row["id"], error="no_payment_method_on_file")
                result["warnings"].append("buyer_no_pm")
            else:
                try:
                    pi = await _charge_card(
                        db,
                        customer_id=buyer.get("stripe_customer_id"),
                        payment_method_id=pm["stripe_payment_method_id"],
                        amount_cents=_to_cents(remaining_buyer),
                        currency=currency,
                        description=f"BidVex Buyer Commission – {listing.get('title','')[:60]} – {currency}",
                        statement_descriptor="BIDVEX-COMM",
                        metadata={
                            "type": "buyer_commission",
                            "auction_id": auction_id,
                            "winner_user_id": winner_user_id,
                            "scenario": "cash_or_etransfer",
                        },
                        idempotency_key=charge_row["idempotency_key"],
                    )
                    db_writes = []
                    if deposit_doc and deposit_amount > 0:
                        # Capture the deposit + remaining charged separately
                        try:
                            stripe.PaymentIntent.capture(
                                deposit_doc["stripe_payment_intent_id"],
                                amount_to_capture=_to_cents(deposit_amount),
                                idempotency_key=f"deposit_capture_{auction_id}_{winner_user_id}_{auction_end_ts}",
                            )
                            db_writes.append(db.bidding_deposits.update_one(
                                {"id": deposit_doc["id"]},
                                {"$set": {"status": "applied", "applied_amount": deposit_amount,
                                          "applied_at": datetime.now(timezone.utc).isoformat()}},
                            ))
                        except Exception as exc:
                            logger.warning(f"deposit capture warn: {exc}")
                    await _record_charge_with_atomic_rollback(
                        db, charge_row=charge_row, pi=pi, db_writes=db_writes,
                    )
                    result["buyer_charge"] = {
                        "applied_from_deposit": deposit_amount,
                        "extra_charge": remaining_buyer,
                        "stripe_pi": pi.id,
                    }
                    try:
                        from services.emails.email_system import send_charge_confirmation_email
                        await send_charge_confirmation_email(
                            db, user_id=winner_user_id, auction_id=auction_id,
                            amount=remaining_buyer, currency=currency,
                            charge_type="buyer_commission",
                        )
                    except Exception:
                        pass
                except stripe.StripeError as exc:
                    await mark_charge_failed(db, charge_row["id"], error=str(exc))
                    result["warnings"].append(f"buyer_charge_failed: {exc}")

    # ---- SELLER COMMISSION ----
    if seller_commission > 0:
        try:
            seller_charge_row = await reserve_charge_row(
                db,
                auction_id=auction_id,
                user_id=seller_id,
                charge_type="seller_commission",
                currency=currency,
                amount=seller_commission,
                auction_end_ts=auction_end_ts,
                metadata={
                    "listing_title": listing.get("title", ""),
                    "hammer_price": hammer_price,
                    "scenario": "cash_or_etransfer",
                },
            )
        except DuplicateChargeBlocked:
            seller_charge_row = None
        if seller_charge_row:
            seller_pm = await _get_default_pm(db, seller_id)
            if not seller_pm:
                await mark_charge_failed(db, seller_charge_row["id"], error="no_payment_method_on_file")
                result["warnings"].append("seller_no_pm")
            else:
                try:
                    pi = await _charge_card(
                        db,
                        customer_id=seller.get("stripe_customer_id"),
                        payment_method_id=seller_pm["stripe_payment_method_id"],
                        amount_cents=_to_cents(seller_commission),
                        currency=currency,
                        description=f"BidVex Seller Commission – {listing.get('title','')[:60]} – {currency}",
                        statement_descriptor="BIDVEX-SELL",
                        metadata={
                            "type": "seller_commission",
                            "auction_id": auction_id,
                            "seller_id": seller_id,
                            "scenario": "cash_or_etransfer",
                        },
                        idempotency_key=seller_charge_row["idempotency_key"],
                    )
                    await _record_charge_with_atomic_rollback(
                        db, charge_row=seller_charge_row, pi=pi,
                    )
                    result["seller_charge"] = {"amount": seller_commission, "stripe_pi": pi.id}
                    try:
                        from services.emails.email_system import send_charge_confirmation_email
                        await send_charge_confirmation_email(
                            db, user_id=seller_id, auction_id=auction_id,
                            amount=seller_commission, currency=currency,
                            charge_type="seller_commission",
                        )
                    except Exception:
                        pass
                except stripe.StripeError as exc:
                    await mark_charge_failed(db, seller_charge_row["id"], error=str(exc))
                    result["warnings"].append(f"seller_charge_failed: {exc}")

    return result


# ============================================================
# Scenario B — Stripe (full payment + Connect payout)
# ============================================================

async def settle_stripe_full(
    db,
    *,
    auction_id: str,
    listing: Dict[str, Any],
    winner_user_id: str,
    seller_id: str,
    hammer_price: float,
    currency: str,
    auction_end_ts: int,
) -> Dict[str, Any]:
    """
    Stripe scenario:
      • Validate winner_user_id matches DB winner (else WINNER_MISMATCH_BLOCKED).
      • Charge buyer (hammer + commission - deposit_already_paid).
      • Transfer seller payout via Connect (winning_bid - seller_commission).
    """
    currency = (currency or "CAD").upper()
    result = {"buyer_charge": None, "seller_payout": None, "warnings": []}

    # WINNER VALIDATION
    db_winner = listing.get("winner_id") or listing.get("winning_bidder_id") or listing.get("highest_bidder_id")
    if db_winner and db_winner != winner_user_id:
        await _log_payment_event(
            db, event="WINNER_MISMATCH_BLOCKED",
            auction_id=auction_id,
            requested_winner=winner_user_id, db_winner=db_winner,
        )
        return {"error": "WINNER_MISMATCH_BLOCKED", "warnings": ["winner_id_mismatch"]}

    buyer = await db.users.find_one({"id": winner_user_id})
    seller = await db.users.find_one({"id": seller_id})
    buyer_tier = (buyer or {}).get("subscription_tier", "free")
    seller_tier = (seller or {}).get("subscription_tier", "free")
    buyer_prov = (buyer or {}).get("province") or (buyer or {}).get("business_province") or "QC"
    seller_prov = (seller or {}).get("province") or (seller or {}).get("business_province") or "QC"

    # iter350 — Single source of truth: calculate_fee() with per-user Place-of-Supply
    fee = calculate_fee(
        hammer_price=float(hammer_price),
        auction_type="lots",
        seller_account_type="individual",
        seller_tier=seller_tier,
        buyer_account_type="individual",
        buyer_tier=buyer_tier,
        payment_method="stripe",
        card_type="domestic",
        buyer_province=buyer_prov,
        seller_province=seller_prov,
    )
    buyer_total = float(fee["buyer_total_charged"])
    seller_payout = float(fee["seller_payout"])

    # iter244 Mission 1 — Apply active promotion overrides at settlement.
    promo_meta = await _apply_settlement_promotions(
        db=db,
        winner_user_id=winner_user_id,
        seller_id=seller_id,
        buyer_premium_amount=float(fee["buyer_premium"]),
        seller_commission_amount=float(fee["seller_commission"]),
        auction_id=auction_id,
        listing_type=listing.get("listing_type") or "lots",
    )
    buyer_total = max(0.0, round(buyer_total - promo_meta["buyer_discount_amount"], 2))
    seller_payout = round(seller_payout + promo_meta["seller_discount_amount"], 2)

    # iter340 — Canada-Day promo: waive the remaining seller commission on
    # the account's first listing by returning it to the payout.
    _remaining_commission = max(0.0, round(float(fee["seller_commission"]) - promo_meta["seller_discount_amount"], 2))
    if _remaining_commission > 0 and promo_first_listing_waiver_applies(seller):
        from services.trial_promo import try_consume_first_listing_free
        if await try_consume_first_listing_free(db, seller_id):
            seller_payout = round(seller_payout + _remaining_commission, 2)
            promo_meta["first_listing_waiver"] = _remaining_commission

    # iter298 BUG 3/4 — expose the full fee breakdown so the
    # payment-collection layer can stamp `net_payout_amount` and issue
    # itemized receipts without re-running the fee engine.
    result["fee_breakdown"] = {
        "fee_model_version": fee.get("fee_model_version", "iter350"),
        "hammer_price": float(hammer_price),
        "buyer_premium": float(fee["buyer_premium"]),
        "buyer_stripe_recovery": float(fee.get("buyer_stripe_recovery", fee.get("buyer_stripe_fee", 0))),
        "buyer_taxes": float(fee["buyer_taxes"]),
        "buyer_tax_label": fee.get("buyer_tax_label", ""),
        "buyer_tax_province": fee.get("buyer_tax_province", buyer_prov),
        "buyer_total_charged": buyer_total,
        "seller_commission": float(fee["seller_commission"]),
        "seller_stripe_recovery": float(fee.get("seller_stripe_recovery", 0)),
        "seller_taxes": float(fee.get("seller_taxes", 0)),
        "seller_tax_label": fee.get("seller_tax_label", ""),
        "seller_tax_province": fee.get("seller_tax_province", seller_prov),
        "seller_payout": seller_payout,
        "promo_first_listing_waiver": promo_meta.get("first_listing_waiver", 0.0),
    }

    # Deposit credit — bidding deposits (marketplace/lots) OR storage deposits.
    deposit_doc = await db.bidding_deposits.find_one(
        {"auction_id": auction_id, "user_id": winner_user_id, "status": {"$in": ["held", "authorized"]}},
        {"_id": 0},
    )
    if not deposit_doc:
        deposit_doc = await db.storage_deposits.find_one(
            {"auction_id": auction_id, "user_id": winner_user_id, "status": {"$in": ["held", "authorized"]}},
            {"_id": 0},
        )
    deposit_amount = float(deposit_doc.get("amount", 0)) if deposit_doc else 0.0
    final_charge = max(0.0, round(buyer_total - deposit_amount, 2))

    # Reserve charge row
    try:
        charge_row = await reserve_charge_row(
            db,
            auction_id=auction_id,
            user_id=winner_user_id,
            charge_type="buyer_full_payment",
            currency=currency,
            amount=final_charge,
            auction_end_ts=auction_end_ts,
            metadata={
                "hammer_price": hammer_price,
                "buyer_total_before_deposit": buyer_total,
                "deposit_credit": deposit_amount,
                "scenario": "stripe_full",
                # iter244 Mission 1 — Promotion metadata for ledger audit.
                "buyer_promotion_id": promo_meta.get("buyer_promotion_id"),
                "buyer_coupon_code": promo_meta.get("buyer_coupon_code"),
                "buyer_discount_amount": promo_meta.get("buyer_discount_amount", 0.0),
                "seller_promotion_id": promo_meta.get("seller_promotion_id"),
                "seller_coupon_code": promo_meta.get("seller_coupon_code"),
                "seller_discount_amount": promo_meta.get("seller_discount_amount", 0.0),
            },
        )
    except DuplicateChargeBlocked as exc:
        result["warnings"].append(str(exc))
        return result

    seller_connect_id = (seller or {}).get("stripe_connect_account_id")
    pm = await _get_default_pm(db, winner_user_id)

    if not pm:
        await mark_charge_failed(db, charge_row["id"], error="no_payment_method_on_file")
        result["warnings"].append("buyer_no_pm")
        return result

    try:
        # iter298 BUG 3 — NON-CUSTODIAL GUARD: never route funds to the
        # seller automatically. The full buyer charge lands on the BidVex
        # platform account; the seller's net payout is flagged
        # `payout_pending` for admin review + manual payout (see
        # services.payment_collection). Stripe Connect destination
        # charges are disabled until Connect is fully configured.
        _ = seller_connect_id  # retained for observability/logging only

        if final_charge > 0:
            pi = await _charge_card(
                db,
                customer_id=buyer.get("stripe_customer_id"),
                payment_method_id=pm["stripe_payment_method_id"],
                amount_cents=_to_cents(final_charge),
                currency=currency,
                description=f"BidVex Purchase – {listing.get('title','')[:60]} – {currency}",
                statement_descriptor="BIDVEX-WIN",
                metadata={
                    "type": "buyer_full_payment",
                    "auction_id": auction_id,
                    "winner_user_id": winner_user_id,
                    "hammer_price": str(hammer_price),
                    "deposit_credit": str(deposit_amount),
                    "scenario": "stripe_full",
                },
                idempotency_key=charge_row["idempotency_key"],
            )
            db_writes = []
            if deposit_doc:
                try:
                    stripe.PaymentIntent.capture(
                        deposit_doc["stripe_payment_intent_id"],
                        amount_to_capture=_to_cents(deposit_amount),
                        idempotency_key=f"deposit_capture_{auction_id}_{winner_user_id}_{auction_end_ts}",
                    )
                    db_writes.append(db.bidding_deposits.update_one(
                        {"id": deposit_doc["id"]},
                        {"$set": {"status": "applied", "applied_amount": deposit_amount,
                                  "applied_at": datetime.now(timezone.utc).isoformat()}},
                    ))
                except Exception as exc:
                    logger.warning(f"deposit capture warn: {exc}")
            ok = await _record_charge_with_atomic_rollback(
                db, charge_row=charge_row, pi=pi, db_writes=db_writes,
            )
            if ok:
                result["buyer_charge"] = {
                    "amount": final_charge, "stripe_pi": pi.id,
                    "deposit_credit": deposit_amount,
                }
                try:
                    from services.emails.email_system import send_charge_confirmation_email
                    await send_charge_confirmation_email(
                        db, user_id=winner_user_id, auction_id=auction_id,
                        amount=final_charge, currency=currency,
                        charge_type="buyer_full_payment",
                    )
                except Exception:
                    pass

        # iter298 BUG 3 — payout is ALWAYS pending admin review now
        # (non-custodial). Record the obligation; payment_collection
        # owns the `pending_payouts` admin-review queue.
        result["seller_payout"] = {
            "amount": seller_payout,
            "method": "payout_pending_admin_review",
            "status": "payout_pending",
        }
    except stripe.StripeError as exc:
        await mark_charge_failed(db, charge_row["id"], error=str(exc))
        result["warnings"].append(f"buyer_charge_failed: {exc}")

    return result


# ============================================================
# Public entry point
# ============================================================

async def settle_auction(
    db,
    *,
    auction_id: str,
    listing: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Single entry point — choose flow based on listing.payment_method.
    Spec: payment_method ∈ {"stripe", "cash", "etransfer", "e-transfer"}
    """
    payment_method = (listing.get("payment_method") or "stripe").lower().replace("-", "")
    winner_user_id = (
        listing.get("winner_id")
        or listing.get("winning_bidder_id")
        or listing.get("highest_bidder_id")
    )
    seller_id = listing.get("seller_id")
    # iter451 — Single source of truth for the merchandise total. Uses
    # `resolve_hammer_total` so a per-unit multi-item lot (unit=$7, qty=2,
    # multiply_hammer_by_quantity=True) correctly resolves to $14 instead
    # of leaking through as $7. Preserves existing behaviour for
    # total-lot pricing, quantity=1, pre-multiplied prices, and Buy Now
    # (which never enters this settlement path).
    from services.hammer_total import resolve_hammer_total
    _mt = resolve_hammer_total(listing)
    hammer_price = float(_mt["hammer_total"])
    winning_unit_price = float(_mt["unit_price"])
    winning_quantity = int(_mt["quantity"])
    currency = (listing.get("currency") or "CAD").upper()
    end_dt = listing.get("auction_end_date") or listing.get("end_time") or datetime.now(timezone.utc)
    if isinstance(end_dt, str):
        try:
            end_dt = datetime.fromisoformat(end_dt.replace("Z", "+00:00"))
        except Exception:
            end_dt = datetime.now(timezone.utc)
    auction_end_ts = int(end_dt.timestamp())

    if not winner_user_id:
        return {"settled": False, "reason": "no_winner"}
    if not seller_id:
        return {"settled": False, "reason": "no_seller"}
    if hammer_price <= 0:
        return {"settled": False, "reason": "invalid_hammer_price"}

    if payment_method in ("cash", "etransfer", "etransfere"):
        out = await settle_cash_or_etransfer(
            db,
            auction_id=auction_id,
            listing=listing,
            winner_user_id=winner_user_id,
            seller_id=seller_id,
            hammer_price=hammer_price,
            currency=currency,
            auction_end_ts=auction_end_ts,
        )
        out["scenario"] = "cash_or_etransfer"
    else:
        out = await settle_stripe_full(
            db,
            auction_id=auction_id,
            listing=listing,
            winner_user_id=winner_user_id,
            seller_id=seller_id,
            hammer_price=hammer_price,
            currency=currency,
            auction_end_ts=auction_end_ts,
        )
        out["scenario"] = "stripe_full"

    out["settled"] = True
    out["currency"] = currency
    out["auction_id"] = auction_id
    # iter451 — Expose the merchandise-total breakdown so downstream
    # callers (invoices, buyer confirmation, seller settlement) can show
    # `unit × quantity = line total` without re-doing the math.
    out["merchandise_total"] = {
        "unit_price": winning_unit_price,
        "quantity": winning_quantity,
        "hammer_total": hammer_price,
        "is_multiplied": bool(_mt["is_multiplied"]),
    }
    return out


__all__ = ["settle_auction", "settle_cash_or_etransfer", "settle_stripe_full"]
