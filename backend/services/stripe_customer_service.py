"""
BidVex — Stripe Customer Service
Sticky Card Enforcement: get_or_create_stripe_customer, attach/detach payment methods,
card deletion guard, listing creation guard, cancellation penalty.
"""
import stripe
import os
import logging
from datetime import datetime, timezone
from fastapi import HTTPException

logger = logging.getLogger(__name__)

stripe.api_key = os.environ.get("STRIPE_API_KEY")

PENALTY_AMOUNT_CENTS = 5000  # $50.00 CAD


async def get_or_create_stripe_customer(db, user) -> str:
    """Idempotent — creates Stripe Customer once, reuses forever."""
    user_doc = await db.users.find_one({"id": user.id}, {"_id": 0, "stripe_customer_id": 1, "email": 1, "name": 1})
    existing = (user_doc or {}).get("stripe_customer_id")
    if existing:
        return existing

    customer = stripe.Customer.create(
        email=getattr(user, "email", ""),
        name=getattr(user, "name", ""),
        metadata={
            "user_id": str(user.id),
            "platform": "bidvex",
        },
    )
    await db.users.update_one(
        {"id": user.id},
        {"$set": {"stripe_customer_id": customer.id, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    return customer.id


async def validate_payment_method_for_listing(db, user):
    """
    Called at listing creation. Raises HTTP 402 if no valid payment method on file.
    """
    user_doc = await db.users.find_one(
        {"id": user.id},
        {"_id": 0, "has_payment_method": 1, "default_payment_method_id": 1, "stripe_customer_id": 1},
    )
    if not user_doc or not user_doc.get("has_payment_method"):
        raise HTTPException(
            status_code=402,
            detail={
                "error": "payment_method_required",
                "message_en": "A valid payment method is required to create a listing. Please add a card to your account before listing an item.",
                "message_fr": "Un moyen de paiement valide est requis pour créer une annonce. Veuillez ajouter une carte à votre compte avant de lister un article.",
            },
        )

    pm_id = user_doc.get("default_payment_method_id")
    if pm_id:
        try:
            pm = stripe.PaymentMethod.retrieve(pm_id)
            now = datetime.now(timezone.utc)
            if pm.card and (
                pm.card.exp_year < now.year
                or (pm.card.exp_year == now.year and pm.card.exp_month < now.month)
            ):
                raise HTTPException(
                    status_code=402,
                    detail={
                        "error": "payment_method_expired",
                        "message_en": "Your card on file has expired. Please update your payment method.",
                        "message_fr": "Votre carte enregistrée a expiré. Veuillez mettre à jour votre moyen de paiement.",
                    },
                )
        except stripe.StripeError:
            raise HTTPException(
                status_code=402,
                detail={"error": "payment_method_invalid",
                        "message_en": "Your payment method could not be verified. Please update it.",
                        "message_fr": "Votre moyen de paiement n'a pas pu être vérifié. Veuillez le mettre à jour."},
            )


async def check_card_deletion_allowed(db, user_id: str) -> int:
    """
    Returns the count of active listings. If > 0, card deletion is blocked.
    """
    count = await db.listings.count_documents({
        "seller_id": user_id,
        "status": {"$in": ["active", "live", "ending_soon"]},
    })
    multi_count = await db.multi_item_listings.count_documents({
        "seller_id": user_id,
        "status": {"$in": ["active", "live", "ending_soon"]},
    })
    return count + multi_count


async def charge_cancellation_penalty(db, seller_id: str, listing_id: str, reason: str) -> dict:
    """
    Charges $50 CAD cancellation penalty to seller's card on file.
    If card fails, flags account for suspension.
    """
    user_doc = await db.users.find_one(
        {"id": seller_id},
        {"_id": 0, "stripe_customer_id": 1, "default_payment_method_id": 1, "email": 1, "name": 1},
    )
    if not user_doc or not user_doc.get("stripe_customer_id"):
        await db.admin_flags.insert_one({
            "type": "no_stripe_customer_on_penalty",
            "user_id": seller_id,
            "listing_id": listing_id,
            "flagged_at": datetime.now(timezone.utc).isoformat(),
        })
        raise HTTPException(status_code=422, detail="No Stripe customer on record")

    try:
        from services.stripe_circuit_breaker import safe_stripe_call_blocking
        pi = await safe_stripe_call_blocking(
            lambda: stripe.PaymentIntent.create(
                amount=PENALTY_AMOUNT_CENTS,
                currency="cad",
                customer=user_doc["stripe_customer_id"],
                payment_method=user_doc.get("default_payment_method_id"),
                confirm=True,
                automatic_payment_methods={"enabled": True, "allow_redirects": "never"},
                description="BidVex Cancellation Penalty — Non-delivery after auction close",
                metadata={
                    "type": "cancellation_penalty",
                    "seller_id": seller_id,
                    "listing_id": listing_id,
                    "reason": reason,
                },
            ),
            operation_name="cancellation_penalty_payment_intent_create",
        )

        await db.penalty_log.insert_one({
            "seller_id": seller_id,
            "listing_id": listing_id,
            "amount_cents": PENALTY_AMOUNT_CENTS,
            "stripe_payment_intent": pi.id,
            "status": pi.status,
            "reason": reason,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })

        return {"status": "penalty_charged", "payment_intent": pi.id, "amount": "$50.00 CAD"}

    except stripe.CardError as e:
        await db.admin_flags.insert_one({
            "type": "penalty_card_declined",
            "user_id": seller_id,
            "listing_id": listing_id,
            "error_code": e.code,
            "flagged_at": datetime.now(timezone.utc).isoformat(),
        })
        raise HTTPException(status_code=402, detail={"error": "penalty_charge_failed", "code": e.code})


async def audit_stripe_customers(db):
    """
    Background job: finds users missing stripe_customer_id or with expired cards.
    Flags them in admin_flags collection.
    """
    now = datetime.now(timezone.utc)
    flagged = 0

    # Users with active listings but no stripe_customer_id
    seller_ids = await db.listings.distinct("seller_id", {"status": {"$in": ["active", "live"]}})
    for sid in seller_ids:
        user = await db.users.find_one({"id": sid}, {"_id": 0, "stripe_customer_id": 1, "has_payment_method": 1})
        if not user or not user.get("stripe_customer_id") or not user.get("has_payment_method"):
            await db.admin_flags.update_one(
                {"type": "missing_payment_method", "user_id": sid},
                {"$set": {
                    "type": "missing_payment_method",
                    "user_id": sid,
                    "flagged_at": now.isoformat(),
                }},
                upsert=True,
            )
            flagged += 1

    # Users with expired cards
    users_with_pm = db.payment_methods.find({}, {"_id": 0, "user_id": 1, "exp_month": 1, "exp_year": 1})
    async for pm in users_with_pm:
        if pm.get("exp_year", 9999) < now.year or (
            pm.get("exp_year") == now.year and pm.get("exp_month", 13) < now.month
        ):
            await db.admin_flags.update_one(
                {"type": "expired_payment_method", "user_id": pm["user_id"]},
                {"$set": {
                    "type": "expired_payment_method",
                    "user_id": pm["user_id"],
                    "flagged_at": now.isoformat(),
                }},
                upsert=True,
            )
            flagged += 1

    logger.info(f"[STRIPE_AUDIT] Flagged {flagged} accounts for review")
    return flagged
