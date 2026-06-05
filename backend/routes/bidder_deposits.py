"""
Strict Bidder Deposit Endpoints (Spec Feature 1)
=================================================
Distinct from the legacy "high-value $1k hold" flow in routes/deposits.py.
This endpoint handles partner-defined deposits (fixed CAD/USD or % of starting bid)
and uses Stripe SetupIntent + manual-capture PaymentIntent to charge the
buyer's saved card immediately upon their first bid.

Endpoints
---------
GET  /api/bidder-deposits/check/{auction_id}
       → returns { required, paid, amount, currency, deposit_id }

POST /api/bidder-deposits/charge
       → payload { auction_id }
         charges the buyer's default card for the configured deposit;
         idempotent on (auction_id, user_id, charge_type=deposit).
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel

from routes.payments_shared import get_current_user_wrapper, get_db
from services.payment_idempotency import (
    DuplicateChargeBlocked,
    mark_charge_failed,
    mark_charge_succeeded,
    reserve_charge_row,
)

logger = logging.getLogger(__name__)
security = HTTPBearer(auto_error=False)

bidder_deposits_router = APIRouter(prefix="/bidder-deposits", tags=["BidderDeposits"])


async def _auth(credentials):
    fn = get_current_user_wrapper()
    if not credentials or fn is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return await fn(credentials)


def _section_deposit_default(listing: dict) -> tuple[float, str, str]:
    """iter283 Mission 5 — Return section-default deposit (amount, type, label).
    Used when the listing has `requires_deposit=True` but no explicit
    `deposit_amount` set. Returns (0, "fixed", "") for sections without
    a default rule (marketplace / generic).

    Section rules per spec:
      • Storage          → $50 flat (refundable)
      • Vehicles         → $200 floor OR 10% of starting_price (whichever higher)
      • Lots (>$500)     → $50 floor OR 10% of starting_price
      • Marketplace      → no default (returns 0)
    """
    from services.listing_sections import infer_section
    section = infer_section(listing)
    starting = float(listing.get("starting_price") or 0)
    if section == "storage":
        return (50.0, "fixed", "$50 Refundable Storage Deposit")
    if section == "vehicles":
        amt = max(200.0, round(starting * 0.10, 2))
        return (amt, "fixed", "Vehicle Bidding Deposit (Refundable)")
    if section == "lots" and starting > 500.0:
        amt = max(50.0, round(starting * 0.10, 2))
        return (amt, "fixed", "10% Refundable Deposit")
    return (0.0, "fixed", "")


def _calc_deposit_amount(listing: dict) -> float:
    if not listing.get("requires_deposit"):
        # iter283 Mission 5 — Storage and vehicle listings have an
        # implicit deposit requirement even when the legacy field
        # `requires_deposit` is unset. Section-default kicks in.
        try:
            from services.listing_sections import infer_section
            _sec = infer_section(listing)
            if _sec in ("storage", "vehicles"):
                amt, _t, _l = _section_deposit_default(listing)
                if amt > 0:
                    return amt
        except Exception:  # noqa: BLE001
            pass
        return 0.0
    amount = float(listing.get("deposit_amount") or 0)
    if amount <= 0:
        # Explicit opt-in but no amount specified → use section default.
        amt, _t, _l = _section_deposit_default(listing)
        return amt
    if (listing.get("deposit_type") or "fixed").lower() == "percentage":
        starting = float(listing.get("starting_price") or 0)
        return round(starting * (amount / 100.0), 2)
    return round(amount, 2)


async def _find_listing(db, auction_id: str) -> Optional[dict]:
    listing = await db.listings.find_one({"id": auction_id}, {"_id": 0})
    if listing:
        listing["__source__"] = "listings"
        return listing
    listing = await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0})
    if listing:
        listing["__source__"] = "multi_item_listings"
        return listing
    listing = await db.storage_auctions.find_one({"id": auction_id}, {"_id": 0})
    if listing:
        listing["__source__"] = "storage_auctions"
        return listing
    return None


@bidder_deposits_router.get("/check/{auction_id}")
async def check_deposit(
    auction_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    user = await _auth(credentials)
    db = get_db()
    listing = await _find_listing(db, auction_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Auction not found")
    required = bool(listing.get("requires_deposit"))
    amount = _calc_deposit_amount(listing)
    currency = (listing.get("currency") or "CAD").upper()
    # iter283 Mission 5 — Section-default may auto-require deposit on
    # storage / vehicle listings even when the legacy `requires_deposit`
    # flag is unset. Reflect that in the response.
    if not required and amount > 0:
        required = True
    _amt_default, _type_default, _label_default = _section_deposit_default(listing)
    deposit_label = listing.get("deposit_label") or _label_default or None

    existing = await db.bidding_deposits.find_one(
        {"auction_id": auction_id, "user_id": user.id,
         "status": {"$in": ["held", "authorized", "succeeded", "applied"]}},
        {"_id": 0},
    )
    return {
        "required": required,
        "paid": bool(existing),
        "amount": amount,
        "currency": currency,
        "deposit_type": listing.get("deposit_type") or _type_default,
        "deposit_label": deposit_label,
        "deposit": existing,
    }


class ChargeRequest(BaseModel):
    auction_id: str


@bidder_deposits_router.post("/charge")
async def charge_deposit(
    data: ChargeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Public endpoint — see _charge_deposit_for_user for the logic."""
    user = await _auth(credentials)
    db = get_db()
    return await _charge_deposit_for_user(db, user, data.auction_id)


async def _charge_deposit_for_user(db, user, auction_id: str) -> dict:
    """
    Charge the buyer's default card for the auction's configured deposit.
    Spec-compliant:
      • Idempotent (DUPLICATE_CHARGE_BLOCKED if already succeeded)
      • Atomic DB write with Stripe rollback on failure
      • Idempotency key formatted per spec
    """
    stripe.api_key = os.environ.get("STRIPE_API_KEY", "")

    listing = await _find_listing(db, auction_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Auction not found")
    if not listing.get("requires_deposit"):
        raise HTTPException(status_code=400, detail="This auction does not require a deposit")

    amount = _calc_deposit_amount(listing)
    if amount <= 0:
        raise HTTPException(status_code=400, detail="Deposit amount is invalid")
    currency = (listing.get("currency") or "CAD").upper()

    end_dt = listing.get("auction_end_date") or listing.get("end_time")
    if isinstance(end_dt, str):
        try:
            end_dt = datetime.fromisoformat(end_dt.replace("Z", "+00:00"))
        except Exception:
            end_dt = datetime.now(timezone.utc)
    if not end_dt:
        end_dt = datetime.now(timezone.utc)
    auction_end_ts = int(end_dt.timestamp())

    user_doc = await db.users.find_one({"id": user.id}, {"_id": 0})
    customer_id = (user_doc or {}).get("stripe_customer_id")
    pm_doc = await db.payment_methods.find_one(
        {"user_id": user.id, "is_default": True}, {"_id": 0}
    )
    if not pm_doc:
        pm_doc = await db.payment_methods.find_one({"user_id": user.id}, {"_id": 0})
    if not customer_id or not pm_doc:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "no_payment_method",
                "message_en": "Add a payment method before placing your first bid on this auction.",
                "message_fr": "Ajoutez un moyen de paiement avant votre première mise.",
            },
        )

    try:
        charge_row = await reserve_charge_row(
            db,
            auction_id=auction_id,
            user_id=user.id,
            charge_type="deposit",
            currency=currency,
            amount=amount,
            auction_end_ts=auction_end_ts,
            metadata={
                "listing_title": listing.get("title", ""),
                "deposit_type": listing.get("deposit_type"),
            },
        )
    except DuplicateChargeBlocked as exc:
        return {
            "status": "already_charged",
            "message_en": "A deposit for this auction has already been charged.",
            "message_fr": "Un dépôt a déjà été débité pour cette enchère.",
            "existing_charge_id": exc.existing_id,
        }

    try:
        pi = stripe.PaymentIntent.create(
            amount=int(round(amount * 100)),
            currency=currency.lower(),
            customer=customer_id,
            payment_method=pm_doc["stripe_payment_method_id"],
            confirm=True,
            off_session=True,
            capture_method="manual",
            description=f"BidVex Bid Deposit – {listing.get('title','')[:60]} – {currency}",
            statement_descriptor_suffix="BIDVEX-DEP",
            metadata={
                "type": "bid_deposit",
                "auction_id": auction_id,
                "user_id": user.id,
                "deposit_type": listing.get("deposit_type") or "fixed",
                "scenario": "bidder_deposit",
            },
            idempotency_key=charge_row["idempotency_key"],
        )
    except stripe.error.CardError as exc:
        await mark_charge_failed(db, charge_row["id"], error=str(exc))
        raise HTTPException(status_code=402, detail={
            "error": "card_declined",
            "message_en": str(exc),
            "message_fr": "Carte refusée: " + str(exc),
        })
    except Exception as exc:
        await mark_charge_failed(db, charge_row["id"], error=str(exc))
        raise HTTPException(status_code=500, detail=str(exc))

    deposit_id = charge_row["id"] + "-d"
    deposit_doc = {
        "id": deposit_id,
        "auction_id": auction_id,
        "user_id": user.id,
        "stripe_payment_intent_id": pi.id,
        "amount": amount,
        "currency": currency,
        "status": "held",
        "deposit_type": listing.get("deposit_type"),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        await db.bidding_deposits.insert_one(deposit_doc)
        await mark_charge_succeeded(
            db, charge_row["id"], stripe_object_id=pi.id, stripe_object_type="payment_intent"
        )
    except Exception as exc:
        try:
            stripe.PaymentIntent.cancel(pi.id)
        except Exception:
            pass
        await mark_charge_failed(db, charge_row["id"], error=f"db_write_failed: {exc}")
        await db.payment_events.insert_one({
            "event": "ROLLBACK_REFUND",
            "auction_id": auction_id,
            "user_id": user.id,
            "stripe_payment_intent_id": pi.id,
            "error": str(exc)[:500],
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        raise HTTPException(status_code=500, detail="Failed to record deposit; refund initiated.")

    return {
        "status": "held",
        "deposit_id": deposit_id,
        "amount": amount,
        "currency": currency,
        "stripe_payment_intent_id": pi.id,
    }
