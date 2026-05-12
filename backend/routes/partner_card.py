"""
iter209 Step 3 — Partner saved-card flow (Stripe SetupIntent + off-session PaymentIntent).

Endpoints exposed by `partner_card_router`:
  GET  /api/partner/saved-card                — fetch saved card metadata (brand/last4/exp)
  POST /api/partner/setup-card                — create SetupIntent → returns client_secret + setup_intent_id
  POST /api/partner/saved-card/confirm        — receive PaymentMethod.id from client, attach + set default, persist
  DELETE /api/partner/saved-card              — detach PM + clear from DB
  POST /api/partner/cash-commission-charge    — internal: off-session PaymentIntent for cash/e-transfer auctions

Single source of truth for all 3% / hammer-based commission math: `services.fee_calculator.calculate_fee`.

Auth: requires partner-role user; non-partner gets a 403.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

import stripe
from fastapi import APIRouter, Depends, HTTPException, Body

from deps import get_current_user, get_db, User

logger = logging.getLogger(__name__)

stripe.api_key = os.environ.get("STRIPE_API_KEY")

partner_card_router = APIRouter(tags=["Partner Cards"])


# ─── Helpers ───────────────────────────────────────────────────────────────
async def _ensure_stripe_customer(db, user: User) -> str:
    """Return the Stripe customer id for this user, creating one if needed."""
    user_doc = await db.users.find_one({"id": user.id}, {"_id": 0, "stripe_customer_id": 1, "email": 1, "name": 1})
    customer_id = (user_doc or {}).get("stripe_customer_id")
    if customer_id:
        return customer_id

    customer = stripe.Customer.create(
        email=user_doc.get("email") if user_doc else user.email,
        name=user_doc.get("name") if user_doc else user.email,
        metadata={"bidvex_user_id": user.id, "role": "partner"},
    )
    await db.users.update_one({"id": user.id}, {"$set": {"stripe_customer_id": customer.id}})
    return customer.id


def _require_partner(user: User, user_doc: dict) -> None:
    """Throw 403 if user is not a verified partner (or admin override)."""
    if user_doc.get("role") in ("admin", "super_admin"):
        return
    if user_doc.get("partner_verification_status") != "verified" and not user_doc.get("is_partner"):
        raise HTTPException(status_code=403, detail={
            "error": "not_a_verified_partner",
            "message_en": "Saved cards are reserved for verified partners.",
            "message_fr": "Les cartes enregistrées sont réservées aux partenaires vérifiés.",
        })


# ─── GET /api/partner/saved-card ──────────────────────────────────────────
@partner_card_router.get("/partner/saved-card")
async def get_saved_card(current_user: User = Depends(get_current_user)):
    db = get_db()
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="user_not_found")
    _require_partner(current_user, user_doc)

    pm_id = user_doc.get("partner_stripe_payment_method_id")
    if not pm_id:
        return {"has_card": False}

    return {
        "has_card": True,
        "brand": user_doc.get("partner_card_brand"),
        "last4": user_doc.get("partner_card_last4"),
        "exp_month": user_doc.get("partner_card_exp_month"),
        "exp_year": user_doc.get("partner_card_exp_year"),
        "payment_method_id": pm_id,
    }


# ─── POST /api/partner/setup-card ─────────────────────────────────────────
@partner_card_router.post("/partner/setup-card")
async def create_setup_intent(current_user: User = Depends(get_current_user)):
    """Create a SetupIntent in off-session mode for the partner.

    Returns:
        { client_secret, setup_intent_id, stripe_publishable_key (optional) }
    """
    db = get_db()
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="user_not_found")
    _require_partner(current_user, user_doc)

    customer_id = await _ensure_stripe_customer(db, current_user)
    try:
        intent = stripe.SetupIntent.create(
            customer=customer_id,
            usage="off_session",                       # required so we can later charge cash commissions
            payment_method_types=["card"],
            metadata={"bidvex_user_id": current_user.id, "purpose": "partner_saved_card"},
        )
    except stripe.StripeError as e:
        logger.warning(f"[iter209] SetupIntent create failed for {current_user.id}: {e}")
        raise HTTPException(status_code=502, detail={"error": "stripe_unavailable", "message": str(e)})

    return {
        "client_secret": intent.client_secret,
        "setup_intent_id": intent.id,
        "publishable_key": os.environ.get("STRIPE_PUBLISHABLE_KEY"),
    }


# ─── POST /api/partner/saved-card/confirm ─────────────────────────────────
@partner_card_router.post("/partner/saved-card/confirm")
async def confirm_saved_card(
    payment_method_id: str = Body(..., embed=True),
    current_user: User = Depends(get_current_user),
):
    """After the client confirms the SetupIntent, persist the PaymentMethod.id on the user.

    Body: { "payment_method_id": "pm_xxx" }
    """
    db = get_db()
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="user_not_found")
    _require_partner(current_user, user_doc)

    customer_id = await _ensure_stripe_customer(db, current_user)
    try:
        # Attach (idempotent — Stripe silently no-ops if already attached)
        pm = stripe.PaymentMethod.retrieve(payment_method_id)
        if pm.customer != customer_id:
            stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)
            pm = stripe.PaymentMethod.retrieve(payment_method_id)
        # Set as default
        stripe.Customer.modify(customer_id, invoice_settings={"default_payment_method": payment_method_id})
    except stripe.StripeError as e:
        logger.warning(f"[iter209] attach PM failed for {current_user.id}: {e}")
        raise HTTPException(status_code=502, detail={"error": "stripe_unavailable", "message": str(e)})

    card = pm.card or {}
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {
            "partner_stripe_payment_method_id": payment_method_id,
            "partner_card_brand": card.get("brand"),
            "partner_card_last4": card.get("last4"),
            "partner_card_exp_month": card.get("exp_month"),
            "partner_card_exp_year": card.get("exp_year"),
            "partner_card_added_at": datetime.now(timezone.utc),
        }},
    )

    return {
        "success": True,
        "brand": card.get("brand"),
        "last4": card.get("last4"),
        "exp_month": card.get("exp_month"),
        "exp_year": card.get("exp_year"),
    }


# ─── DELETE /api/partner/saved-card ───────────────────────────────────────
@partner_card_router.delete("/partner/saved-card")
async def delete_saved_card(current_user: User = Depends(get_current_user)):
    db = get_db()
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="user_not_found")
    _require_partner(current_user, user_doc)

    pm_id = user_doc.get("partner_stripe_payment_method_id")
    if pm_id:
        try:
            stripe.PaymentMethod.detach(pm_id)
        except stripe.StripeError as e:
            logger.warning(f"[iter209] detach PM failed for {current_user.id}: {e}")

    await db.users.update_one(
        {"id": current_user.id},
        {"$unset": {
            "partner_stripe_payment_method_id": "",
            "partner_card_brand": "",
            "partner_card_last4": "",
            "partner_card_exp_month": "",
            "partner_card_exp_year": "",
        }},
    )
    return {"success": True}


# ─── POST /api/partner/cash-commission-charge (internal) ──────────────────
async def charge_partner_cash_commission(
    db,
    *,
    partner_user_id: str,
    listing_id: str,
    listing_title: str,
    hammer_price: float,
    partner_bp_rate: float,
    card_type: str = "domestic",
) -> dict:
    """Auto-charge the 3% commission + GST + QST + Stripe gross-up to the partner's
    saved PaymentMethod off-session. Called automatically when an auction with
    payment_method=cash|e_transfer closes.

    Returns:
        { "success": bool, "payment_intent_id": str, "amount_charged": float, "requires_action": bool, ... }
    """
    from services.fee_calculator import calculate_fee

    user = await db.users.find_one({"id": partner_user_id}, {"_id": 0})
    if not user:
        return {"success": False, "error": "user_not_found"}

    pm_id = user.get("partner_stripe_payment_method_id")
    customer_id = user.get("stripe_customer_id")
    if not pm_id or not customer_id:
        return {"success": False, "error": "no_saved_card"}

    fee = calculate_fee(
        hammer_price=hammer_price,
        auction_type="lots",
        seller_account_type="partner",
        partner_bp_rate=partner_bp_rate,
        payment_method="cash",
        card_type=card_type,
    )

    # Gross-up total in cents (commission + taxes + Stripe gross-up)
    total_charge = fee["seller_commission_total"] + fee["seller_stripe_fee"]
    amount_cents = int(round(total_charge * 100))
    if amount_cents <= 0:
        return {"success": False, "error": "non_positive_amount"}

    try:
        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency="cad",
            customer=customer_id,
            payment_method=pm_id,
            off_session=True,
            confirm=True,
            description=f"BidVex platform commission — {listing_title[:90]}",
            metadata={
                "bidvex_user_id": partner_user_id,
                "listing_id": listing_id,
                "hammer_price": str(hammer_price),
                "partner_bp_rate": str(partner_bp_rate),
                "kind": "partner_cash_commission",
            },
        )
    except stripe.CardError as e:
        # 3DS / SCA required → save for follow-up
        err = e.error
        payment_intent_id = getattr(err, "payment_intent", {}) or {}
        return {
            "success": False,
            "error": "requires_action",
            "code": err.code if hasattr(err, "code") else None,
            "message": err.message if hasattr(err, "message") else str(e),
            "payment_intent_id": payment_intent_id.get("id") if isinstance(payment_intent_id, dict) else None,
        }
    except stripe.StripeError as e:
        logger.warning(f"[iter209] off-session PaymentIntent failed for {partner_user_id}: {e}")
        return {"success": False, "error": "stripe_unavailable", "message": str(e)}

    # Persist the charge on the listing
    try:
        await db.listings.update_one(
            {"id": listing_id},
            {"$set": {
                "partner_cash_commission_payment_intent_id": intent.id,
                "partner_cash_commission_amount": total_charge,
                "partner_cash_commission_charged_at": datetime.now(timezone.utc),
                "partner_cash_commission_status": intent.status,
            }},
        )
    except Exception as exc:
        logger.warning(f"[iter209] listing update after cash commission failed: {exc}")

    return {
        "success": intent.status in ("succeeded", "processing"),
        "payment_intent_id": intent.id,
        "amount_charged": total_charge,
        "status": intent.status,
        "requires_action": intent.status == "requires_action",
        "fee_breakdown": fee,
    }


# Optional: thin HTTP wrapper around the internal function (admin-only — manual retry)
@partner_card_router.post("/partner/cash-commission-charge")
async def http_charge_partner_cash_commission(
    partner_user_id: str = Body(...),
    listing_id: str = Body(...),
    listing_title: str = Body(...),
    hammer_price: float = Body(...),
    partner_bp_rate: float = Body(...),
    current_user: User = Depends(get_current_user),
):
    """Admin manual trigger — useful when an auto-charge originally hit `requires_action`."""
    db = get_db()
    admin_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0, "role": 1})
    if not admin_doc or admin_doc.get("role") not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="admin_required")
    result = await charge_partner_cash_commission(
        db,
        partner_user_id=partner_user_id,
        listing_id=listing_id,
        listing_title=listing_title,
        hammer_price=hammer_price,
        partner_bp_rate=partner_bp_rate,
    )
    return result
