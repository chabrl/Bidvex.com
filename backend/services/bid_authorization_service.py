"""
iter355 — Smart Pre-Authorization Holds for high-value bids.

Applies ONLY to non-vehicle auctions where the incoming bid amount
exceeds $500 CAD. Vehicle listings continue using the pre-existing
$500 flat deposit path (services/vehicle_payment.py) — completely
untouched by this module.

Hold rule (per H-1 spec):
    hold = min( max(0.10 * bid_amount, 50), 500 )    # CAD

Flow:
    1. Bidder places a bid > $500 on a non-vehicle listing.
    2. Route checks `should_require_hold(...)` → True.
    3. Route calls `create_bid_hold(...)`:
         a. Ensure user has a saved default payment method
            (400 PAYMENT_METHOD_REQUIRED if missing).
         b. Create a Stripe PaymentIntent, capture_method="manual",
            confirm=True, off_session=True.
         c. Persist to `db.bid_authorizations` with a
            (listing_id, bidder_id, active) uniqueness invariant.
    4. When the same bidder is outbid, route calls
       `release_bid_hold(...)`:
         a. Look up the active hold row for that (listing, bidder).
         b. Stripe `PaymentIntent.cancel(pi_id)` → funds released.
         c. Row transitioned to `status="released"`.
    5. When the auction ends and the bidder WINS, the hold is left
       in `requires_capture` state — settlement captures or cancels
       it during checkout. This module never captures — it only
       creates/releases.

    Failure of a hold creation → 402 PAYMENT_HOLD_FAILED (bilingual).
    Failure of a hold cancel → logged only (best-effort; the release
    is best-effort because outbid is not user-facing).
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import stripe

logger = logging.getLogger(__name__)


HOLD_THRESHOLD_CAD = 500.0
HOLD_PERCENT = 0.10
HOLD_MIN_CAD = 50.0
HOLD_MAX_CAD = 500.0


def _stripe_ready() -> bool:
    key = os.environ.get("STRIPE_API_KEY", "").strip()
    if not key or key == "sk_test_emergent":
        return False
    stripe.api_key = key
    return True


def _to_cents(amount: float) -> int:
    return int(round(float(amount) * 100))


def compute_hold_amount(bid_amount: float) -> float:
    """Return the hold size in CAD dollars.

        bid < $500          →  $0 (skip)
        $500  ≤ bid ≤ $500  →  $50    (min floor)  [bid=$500 case]
        bid = $1,000        →  $100
        bid = $5,000        →  $500   (max ceiling)
        bid = $10,000       →  $500   (max ceiling)
    """
    if float(bid_amount) <= HOLD_THRESHOLD_CAD:
        return 0.0
    raw = float(bid_amount) * HOLD_PERCENT
    return max(HOLD_MIN_CAD, min(HOLD_MAX_CAD, raw))


def should_require_hold(*, bid_amount: float, auction_type: str) -> bool:
    """Return True iff this bid triggers the pre-auth hold path.

    - Vehicle auctions are EXCLUDED (existing $500 flat deposit stands).
    - Bid must strictly EXCEED $500 to require a hold.
    """
    if (auction_type or "").lower() == "vehicle":
        return False
    return float(bid_amount) > HOLD_THRESHOLD_CAD


async def _get_default_payment_method(db, user_id: str) -> Optional[Dict[str, Any]]:
    """Return the user's default `payment_methods` row or None."""
    pm = await db.payment_methods.find_one(
        {"user_id": user_id, "is_default": True},
        {"_id": 0},
    )
    if pm:
        return pm
    return await db.payment_methods.find_one(
        {"user_id": user_id},
        {"_id": 0},
        sort=[("created_at", -1)],
    )


async def create_bid_hold(
    db,
    *,
    user: Dict[str, Any],
    listing_id: str,
    bid_amount: float,
    auction_type: str,
    listing_title: Optional[str] = None,
    lot_number: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a Stripe manual-capture PaymentIntent for the hold.

    Returns the persisted `bid_authorizations` row (including
    `stripe_payment_intent_id`) on success.

    Raises `HTTPException(400, PAYMENT_METHOD_REQUIRED)` if the user has
    no saved card, or `HTTPException(402, PAYMENT_HOLD_FAILED)` if
    Stripe declines.
    """
    from fastapi import HTTPException

    if not _stripe_ready():
        raise HTTPException(status_code=503, detail={
            "error": "STRIPE_UNAVAILABLE",
            "message_en": "Payment provider is temporarily unavailable. Please try again shortly.",
            "message_fr": "Le fournisseur de paiement est temporairement indisponible. Veuillez réessayer sous peu.",
        })

    hold_cad = compute_hold_amount(bid_amount)
    if hold_cad <= 0:
        # Caller shouldn't reach here — belt-and-suspenders.
        return {"skipped": True, "reason": "below_threshold"}

    user_id = user["id"]

    # -- 1) Ensure user has a saved default payment method + stripe customer.
    pm = await _get_default_payment_method(db, user_id)
    stripe_customer_id = (user.get("stripe_customer_id") or "").strip()

    if not pm or not pm.get("stripe_payment_method_id") or not stripe_customer_id:
        raise HTTPException(status_code=400, detail={
            "error": "PAYMENT_METHOD_REQUIRED",
            "message_en": (
                "A saved payment method is required for bids above $500. "
                "Please add a card in your profile before continuing."
            ),
            "message_fr": (
                "Un moyen de paiement enregistré est requis pour les enchères "
                "dépassant 500 $. Veuillez ajouter une carte dans votre profil "
                "avant de continuer."
            ),
        })

    # -- 2) De-dup — if bidder already has an active hold on this listing/lot,
    #        the caller is likely raising their own bid. Cancel the old hold
    #        first (release), then create a new one at the higher amount.
    query_active: Dict[str, Any] = {
        "listing_id": listing_id,
        "bidder_id": user_id,
        "status": {"$in": ["held", "requires_capture", "authorized"]},
    }
    if lot_number is not None:
        query_active["lot_number"] = lot_number

    old_hold = await db.bid_authorizations.find_one(query_active, {"_id": 0})
    if old_hold:
        try:
            await release_bid_hold(
                db,
                listing_id=listing_id,
                bidder_id=user_id,
                lot_number=lot_number,
                reason="raised_bid",
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning(
                f"[bid-hold] self-raise release failed for user={user_id} "
                f"listing={listing_id}: {exc}"
            )

    # -- 3) Create PI.
    metadata = {
        "bidvex_flow": "bid_pre_authorization_hold",
        "bidvex_user_id": user_id,
        "bidvex_listing_id": listing_id,
        "bidvex_auction_type": auction_type,
        "bidvex_bid_amount_cad": f"{bid_amount:.2f}",
        "bidvex_hold_amount_cad": f"{hold_cad:.2f}",
    }
    if lot_number is not None:
        metadata["bidvex_lot_number"] = str(lot_number)
    if listing_title:
        metadata["bidvex_listing_title"] = str(listing_title)[:120]

    idempotency_suffix = uuid.uuid4().hex[:8]
    idempotency_key = (
        f"bid-hold-{listing_id}-{user_id}-{int(bid_amount)}-{idempotency_suffix}"
    )

    try:
        pi = stripe.PaymentIntent.create(
            amount=_to_cents(hold_cad),
            currency="cad",
            customer=stripe_customer_id,
            payment_method=pm["stripe_payment_method_id"],
            capture_method="manual",
            confirm=True,
            off_session=True,
            description=(
                f"BidVex bid hold — {listing_title or listing_id}"
                + (f" (Lot #{lot_number})" if lot_number else "")
            ),
            metadata=metadata,
            idempotency_key=idempotency_key,
        )
    except stripe.CardError as card_err:  # type: ignore[attr-defined]
        code = getattr(card_err, "code", "card_declined")
        logger.warning(
            f"[bid-hold] CARD DECLINED user={user_id} listing={listing_id} "
            f"amount={hold_cad} code={code}: {card_err}"
        )
        raise HTTPException(status_code=402, detail={
            "error": "PAYMENT_HOLD_FAILED",
            "reason": "card_declined",
            "stripe_code": code,
            "hold_amount_cad": hold_cad,
            "message_en": (
                f"We could not authorize a refundable ${hold_cad:.0f} CAD hold "
                "on your card. Please try a different card and place your bid again."
            ),
            "message_fr": (
                f"Nous n'avons pas pu autoriser un dépôt de garantie "
                f"remboursable de {hold_cad:.0f} $ CAD sur votre carte. "
                "Veuillez essayer une autre carte et enchérir à nouveau."
            ),
        })
    except stripe.StripeError as exc:  # type: ignore[attr-defined]
        # Stripe outage / auth issues — fall through gracefully so a
        # verified bidder isn't locked out by an unrelated Stripe blip.
        logger.error(
            f"[bid-hold] Stripe error user={user_id} listing={listing_id}: {exc}"
        )
        raise HTTPException(status_code=502, detail={
            "error": "PAYMENT_HOLD_FAILED",
            "reason": "stripe_unavailable",
            "hold_amount_cad": hold_cad,
            "message_en": (
                "The payment network is temporarily unavailable. "
                "Please try again in a moment."
            ),
            "message_fr": (
                "Le réseau de paiement est temporairement indisponible. "
                "Veuillez réessayer dans un instant."
            ),
        })

    # -- 4) Persist.
    row = {
        "id": str(uuid.uuid4()),
        "listing_id": listing_id,
        "lot_number": lot_number,
        "bidder_id": user_id,
        "bid_amount_cad": float(bid_amount),
        "hold_amount_cad": float(hold_cad),
        "auction_type": auction_type,
        "currency": "CAD",
        "stripe_payment_intent_id": pi.id,
        "stripe_customer_id": stripe_customer_id,
        "stripe_payment_method_id": pm.get("stripe_payment_method_id"),
        "payment_method_last4": pm.get("last4") or pm.get("card_last4"),
        "status": _map_pi_status(getattr(pi, "status", None)),
        "stripe_status_raw": getattr(pi, "status", None),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "released_at": None,
        "captured_at": None,
        "release_reason": None,
    }
    await db.bid_authorizations.insert_one(row)

    logger.info(
        f"[bid-hold] CREATED user={user_id} listing={listing_id} "
        f"amount=${hold_cad:.2f} pi={pi.id} status={row['status']}"
    )
    # Strip Mongo _id for the caller (insert_one adds it to the dict).
    row.pop("_id", None)
    return row


def _map_pi_status(pi_status: Optional[str]) -> str:
    if pi_status in ("requires_capture", "requires_action"):
        return "held"
    if pi_status == "succeeded":
        return "held"  # succeeded on manual-capture = held; capture is later.
    if pi_status == "canceled":
        return "released"
    return pi_status or "unknown"


async def release_bid_hold(
    db,
    *,
    listing_id: str,
    bidder_id: str,
    lot_number: Optional[int] = None,
    reason: str = "outbid",
) -> Dict[str, Any]:
    """Cancel the bidder's active hold PaymentIntent (best-effort).

    Called from the outbid path in `routes/auctions_bids.py`. Errors are
    caught and returned as { released: False, reason: "..." } — the
    caller should log but not fail the bid placement.
    """
    query: Dict[str, Any] = {
        "listing_id": listing_id,
        "bidder_id": bidder_id,
        "status": {"$in": ["held", "requires_capture", "authorized"]},
    }
    if lot_number is not None:
        query["lot_number"] = lot_number

    hold = await db.bid_authorizations.find_one(query, {"_id": 0})
    if not hold:
        return {"released": False, "reason": "no_active_hold"}

    pi_id = hold.get("stripe_payment_intent_id")
    if not pi_id:
        return {"released": False, "reason": "no_pi_id"}

    if not _stripe_ready():
        logger.warning(f"[bid-hold] release skipped — stripe not ready pi={pi_id}")
        return {"released": False, "reason": "stripe_not_ready"}

    try:
        stripe.PaymentIntent.cancel(pi_id)
    except stripe.InvalidRequestError as exc:  # type: ignore[attr-defined]
        # PI might already be in a terminal state — record + move on.
        logger.info(f"[bid-hold] cancel {pi_id} returned InvalidRequest: {exc}")
    except stripe.StripeError as exc:  # type: ignore[attr-defined]
        logger.warning(f"[bid-hold] cancel {pi_id} failed: {exc}")
        return {"released": False, "reason": "stripe_error", "error": str(exc)[:200]}

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.bid_authorizations.update_one(
        {"id": hold["id"]},
        {"$set": {
            "status": "released",
            "released_at": now_iso,
            "release_reason": reason,
        }},
    )
    logger.info(
        f"[bid-hold] RELEASED pi={pi_id} user={bidder_id} listing={listing_id} "
        f"reason={reason}"
    )
    return {"released": True, "hold_id": hold["id"], "pi_id": pi_id, "reason": reason}


async def get_active_hold(
    db,
    *,
    listing_id: str,
    bidder_id: str,
    lot_number: Optional[int] = None,
) -> Optional[Dict[str, Any]]:
    """Return the active hold row for a (listing, bidder[, lot]) triple."""
    query: Dict[str, Any] = {
        "listing_id": listing_id,
        "bidder_id": bidder_id,
        "status": {"$in": ["held", "requires_capture", "authorized"]},
    }
    if lot_number is not None:
        query["lot_number"] = lot_number
    return await db.bid_authorizations.find_one(query, {"_id": 0})
