"""
BidVex Webhooks Router
Handles external webhooks from third-party services:
- SendGrid (email events)
- Stripe (payment events, subscription events)
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List
from datetime import datetime, timezone, timedelta
import logging
import json

from services.subscription_service import handle_subscription_event, get_tier_from_price_id

logger = logging.getLogger(__name__)

webhooks_router = APIRouter(prefix="/webhooks", tags=["Webhooks"])

# Database and service instances
_db = None
_get_marketing_service = None


def set_webhooks_db(db_instance):
    """Set database instance"""
    global _db
    _db = db_instance


def set_webhooks_marketing_service(marketing_service_func):
    """Set marketing service for SendGrid webhook processing"""
    global _get_marketing_service
    _get_marketing_service = marketing_service_func


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


# ========== SENDGRID WEBHOOKS ==========
# NOTE: The active SendGrid Event Webhook handler lives in
# routes/sendgrid_webhook.py (with HMAC verification, background processing,
# admin spam-alert emails, and the email_deliverable/marketing_unsubscribed
# user-flag updates). This legacy handler was removed in Feb 2026 to avoid a
# route collision at POST /api/webhooks/sendgrid.


# ========== STRIPE WEBHOOKS ==========

def _verify_stripe_event(payload: bytes, sig_header: str):
    """Verify Stripe webhook signature using all configured secrets."""
    import stripe
    import os

    secrets = [
        s for s in [
            os.environ.get("STRIPE_CONNECT_WEBHOOK_SECRET"),
            os.environ.get("STRIPE_WEBHOOK_SECRET"),
            os.environ.get("STRIPE_WEBHOOK_SECRET_2"),
            os.environ.get("STRIPE_TEST_WEBHOOK_SECRET"),
        ] if s
    ]

    if not secrets:
        logger.error("No Stripe webhook secrets configured — rejecting webhook")
        raise HTTPException(status_code=400, detail="Webhook verification not configured")

    if not sig_header:
        logger.warning("Missing stripe-signature header — rejecting webhook")
        raise HTTPException(status_code=400, detail="Missing stripe-signature header")

    last_error = None
    for secret in secrets:
        try:
            return stripe.Webhook.construct_event(payload, sig_header, secret)
        except stripe.SignatureVerificationError as e:
            last_error = str(e)
            continue

    logger.error(f"Stripe signature verification failed with {len(secrets)} secrets. Last: {last_error}")
    raise HTTPException(status_code=400, detail="Invalid signature")


@webhooks_router.post("/stripe")
async def handle_stripe_webhook(request: Request):
    """
    Unified Stripe webhook handler.
    Handles subscription lifecycle, checkout completion, trust verification.
    Uses multi-secret verification (Connect + standard secrets).
    """
    import stripe

    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")

        event = _verify_stripe_event(payload, sig_header)

        event_type = event.get("type") if isinstance(event, dict) else event["type"]
        data = (event.get("data", {}) if isinstance(event, dict) else event["data"]).get("object", {})

        db = get_db()

        # Log the event
        logger.info(f"[Webhook] DB name: {db.name}, client address: {db.client.address}, inserting event {event.get('id')}")
        try:
            insert_result = await db.stripe_events.insert_one({
                "id": event.get("id"),
                "type": event_type,
                "data": data,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
            logger.info(f"[Webhook] Event inserted: {insert_result.inserted_id}")
        except Exception as insert_err:
            logger.error(f"[Webhook] stripe_events insert FAILED: {insert_err}")

        logger.info(f"Processing Stripe webhook: {event_type}")

        # --- Subscription lifecycle ---
        if event_type == "customer.subscription.created":
            await _handle_subscription_created(db, data)
        elif event_type == "customer.subscription.updated":
            await _handle_subscription_updated(db, data)
        elif event_type == "customer.subscription.deleted":
            await _handle_subscription_deleted(db, data)

        # --- Invoice events ---
        elif event_type == "invoice.payment_succeeded":
            await _handle_payment_succeeded(db, data)
        elif event_type == "invoice.payment_failed":
            await _handle_payment_failed(db, data)
        elif event_type == "invoice.paid":
            # For subscription-related invoices, delegate to subscription handler
            if data.get("subscription"):
                subscription_id = data["subscription"]
                subscription_data = stripe.Subscription.retrieve(subscription_id)
                await handle_subscription_event(db, event_type, subscription_data)

        # --- Checkout completion ---
        elif event_type == "checkout.session.completed":
            _meta_all = data.get("metadata", {}) or {}
            session_type = _meta_all.get("type", "") or _meta_all.get("transaction_type", "")
            if session_type == "subscription_upgrade":
                pass  # handled by subscription events above
            elif session_type == "listing_promotion":
                await _handle_listing_promotion_paid(db, data)
            else:
                await _handle_checkout_completed(db, data)

        # --- Trust verification ---
        elif event_type == "setup_intent.succeeded":
            await _handle_setup_intent_succeeded(db, data)
        elif event_type == "payment_method.attached":
            await _handle_payment_method_attached(db, data)

        # --- Deposit holds (pre-auth) ---
        elif event_type == "payment_intent.amount_capturable_updated":
            # Deposit hold successfully authorized
            pi_id = data.get("id")
            pi_meta = data.get("metadata", {})
            if pi_meta.get("transaction_type") == "bidding_deposit":
                await db.bidding_deposits.update_one(
                    {"payment_intent_id": pi_id},
                    {"$set": {"status": "requires_capture", "authorized_at": datetime.now(timezone.utc).isoformat()}},
                )
                logger.info(f"Bidding deposit authorized: {pi_id}")

        elif event_type == "payment_intent.succeeded":
            pi_id = data.get("id")
            pi_meta = data.get("metadata", {})
            tx_type = pi_meta.get("transaction_type", "")

            # ─── Card-country detection (Missing 2) ───
            # Read payment_method.card.country from the PaymentIntent payload.
            # If the card was international, recalculate the actual Stripe fee
            # at the 3.9% rate and log the delta to stripe_fee_adjustments for
            # manual reconciliation. We do NOT re-charge the buyer.
            _card_country = None
            try:
                charges = (data.get("charges") or {}).get("data") or []
                if charges:
                    pm_details = (charges[0].get("payment_method_details") or {}).get("card") or {}
                    _card_country = pm_details.get("country")
                if not _card_country:
                    # Fallback — modern Stripe sometimes exposes on data.payment_method_options
                    pm = data.get("payment_method") or {}
                    card = pm.get("card") if isinstance(pm, dict) else None
                    if card:
                        _card_country = card.get("country")
            except Exception:
                _card_country = None

            try:
                if _card_country and _card_country.upper() != "CA":
                    from services.pricing_manager import gross_up_stripe_fee
                    from decimal import Decimal as _D
                    estimated_fee = float(pi_meta.get("stripe_fee_estimate", 0) or 0)
                    subtotal = float(pi_meta.get("subtotal", 0) or 0)
                    if subtotal > 0:
                        actual_fee = float(gross_up_stripe_fee(_D(str(subtotal)), card_type="international"))
                        delta = round(actual_fee - estimated_fee, 2)
                        await db.stripe_fee_adjustments.insert_one({
                            "payment_intent_id": pi_id,
                            "item_id": pi_meta.get("item_id") or pi_meta.get("listing_id"),
                            "estimated_fee": estimated_fee,
                            "actual_fee": actual_fee,
                            "delta": delta,
                            "card_country": _card_country,
                            "subtotal": subtotal,
                            "created_at": datetime.now(timezone.utc).isoformat(),
                        })
                        logger.warning(
                            f"[stripe-webhook] International card ({_card_country}) — "
                            f"fee shortfall of ${delta:.2f} logged for PI {pi_id}"
                        )
                # Always update the transaction record with card_country + actual fee
                _update = {"card_country": _card_country or "unknown"}
                if _card_country and _card_country.upper() != "CA" and "actual_fee" in locals():
                    _update["actual_stripe_fee"] = actual_fee
                await db.payment_transactions.update_one(
                    {"session_id": pi_meta.get("session_id") or pi_id},
                    {"$set": _update},
                )
                # Vehicle BuyNow transactions live in a separate collection
                await db.vehicle_buy_now_transactions.update_one(
                    {"payment_intent_id": pi_id},
                    {"$set": _update},
                )
            except Exception as _cc_err:
                logger.warning(f"[stripe-webhook] card-country reconciliation failed: {_cc_err}")

            if tx_type == "vehicle_platform_fee":
                from services.vehicle_fee_service import handle_vehicle_fee_succeeded
                await handle_vehicle_fee_succeeded(db, pi_id)
                logger.info(f"Vehicle platform fee paid: {pi_id}")

            elif tx_type in ("auction_purchase", "listing_purchase"):
                # Non-vehicle Stripe sale succeeded — record payout
                await _handle_auction_payment_succeeded(db, data, pi_meta)

        elif event_type == "payment_intent.payment_failed":
            pi_id = data.get("id")
            pi_meta = data.get("metadata", {})
            if pi_meta.get("transaction_type") == "vehicle_platform_fee":
                from services.vehicle_fee_service import handle_vehicle_fee_failed
                await handle_vehicle_fee_failed(db, pi_id)
                logger.warning(f"Vehicle platform fee failed: {pi_id}")

        elif event_type == "payment_intent.canceled":
            pi_id = data.get("id")
            pi_meta = data.get("metadata", {})
            if pi_meta.get("transaction_type") == "bidding_deposit":
                await db.bidding_deposits.update_one(
                    {"payment_intent_id": pi_id},
                    {"$set": {"status": "released", "released_at": datetime.now(timezone.utc).isoformat()}},
                )
                logger.info(f"Bidding deposit released: {pi_id}")

        else:
            logger.info(f"Unhandled Stripe event: {event_type}")

        # Track successful webhook processing
        from routes.monitoring import log_webhook_event
        import asyncio
        asyncio.ensure_future(log_webhook_event("stripe", event_type, "success"))

        return {"status": "ok", "event_type": event_type}

    except HTTPException:
        # Track webhook verification failures
        from routes.monitoring import log_webhook_event, log_error_event
        import asyncio
        asyncio.ensure_future(log_webhook_event("stripe", "verification_failed", "failed", {"error": "signature_or_http_error"}))
        asyncio.ensure_future(log_error_event("stripe_webhook_failure", "Stripe webhook verification failed", severity="error"))
        raise
    except json.JSONDecodeError:
        from routes.monitoring import log_webhook_event
        import asyncio
        asyncio.ensure_future(log_webhook_event("stripe", "invalid_json", "failed", {"error": "JSONDecodeError"}))
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        from routes.monitoring import log_webhook_event, log_error_event
        import asyncio
        asyncio.ensure_future(log_webhook_event("stripe", event_type if 'event_type' in dir() else "unknown", "failed", {"error": str(e)[:300]}))
        asyncio.ensure_future(log_error_event("stripe_webhook_failure", f"Stripe webhook processing error: {str(e)[:200]}", severity="error"))
        return {"status": "error", "message": str(e)}


async def _handle_subscription_created(db, subscription):
    """Handle new subscription creation"""
    customer_id = subscription.get("customer")
    
    # Find user by Stripe customer ID
    user = await db.users.find_one({"stripe_customer_id": customer_id})
    if not user:
        logger.warning(f"User not found for Stripe customer {customer_id}")
        return
    
    # Map Stripe price to tier
    price_id = subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
    tier = _map_price_to_tier(price_id)
    
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "subscription_tier": tier,
            "subscription_source": "stripe",
            "subscription_status": "active",
            "stripe_subscription_id": subscription.get("id"),
            "subscription_start_date": datetime.now(timezone.utc).isoformat(),
            "subscription_end_date": datetime.fromtimestamp(
                subscription.get("current_period_end", 0),
                tz=timezone.utc
            ).isoformat()
        }}
    )
    
    logger.info(f"Subscription created for user {user['id']}: {tier}")


async def _handle_subscription_updated(db, subscription):
    """Handle subscription updates"""
    customer_id = subscription.get("customer")
    
    user = await db.users.find_one({"stripe_customer_id": customer_id})
    if not user:
        return
    
    status = subscription.get("status")
    
    update = {
        "subscription_status": status,
        "stripe_subscription_id": subscription.get("id")
    }
    
    if status == "active":
        price_id = subscription.get("items", {}).get("data", [{}])[0].get("price", {}).get("id")
        update["subscription_tier"] = _map_price_to_tier(price_id)
        update["subscription_end_date"] = datetime.fromtimestamp(
            subscription.get("current_period_end", 0),
            tz=timezone.utc
        ).isoformat()
    
    await db.users.update_one({"id": user["id"]}, {"$set": update})
    logger.info(f"Subscription updated for user {user['id']}: {status}")


async def _handle_subscription_deleted(db, subscription):
    """Handle subscription cancellation — includes partner soft lock"""
    customer_id = subscription.get("customer")
    subscription_id = subscription.get("id")
    subscription_metadata = subscription.get("metadata", {})
    
    # Check if this is a partner annual fee subscription
    if subscription_metadata.get("type") == "partner_annual_fee":
        user_id = subscription_metadata.get("user_id")
        if user_id:
            await db.users.update_one(
                {"id": user_id},
                {"$set": {
                    "platform_fee_paid": False,
                    "partner_subscription_id": None,
                    "partner_fee_expired_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
            # Create notification about expired fee
            await db.notifications.insert_one({
                "id": f"notif_{user_id}_{datetime.now(timezone.utc).isoformat()}",
                "user_id": user_id,
                "type": "partner_fee_expired",
                "title": "Partner Fee Expired",
                "message": "Your annual partner fee has expired. Please update your payment method to resume listing.",
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(f"Partner soft-locked due to subscription cancellation: user={user_id}")
            return
    
    # Also check by partner_subscription_id in case metadata is missing
    partner_user = await db.users.find_one({"partner_subscription_id": subscription_id})
    if partner_user:
        await db.users.update_one(
            {"id": partner_user["id"]},
            {"$set": {
                "platform_fee_paid": False,
                "partner_subscription_id": None,
                "partner_fee_expired_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        await db.notifications.insert_one({
            "id": f"notif_{partner_user['id']}_{datetime.now(timezone.utc).isoformat()}",
            "user_id": partner_user["id"],
            "type": "partner_fee_expired",
            "title": "Partner Fee Expired",
            "message": "Your annual partner fee has expired. Please update your payment method to resume listing.",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Partner soft-locked (by subscription match): user={partner_user['id']}")
        return
    
    # Standard subscription cancellation
    user = await db.users.find_one({"stripe_customer_id": customer_id})
    if not user:
        return
    
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {
            "subscription_tier": "free",
            "subscription_source": "stripe",
            "subscription_status": "cancelled",
            "subscription_end_date": datetime.now(timezone.utc).isoformat()
        }}
    )
    
    logger.info(f"Subscription cancelled for user {user['id']}")


async def _handle_payment_succeeded(db, invoice):
    """Handle successful payment — includes partner re-activation on renewal"""
    customer_id = invoice.get("customer")
    subscription_id = invoice.get("subscription")
    
    user = await db.users.find_one({"stripe_customer_id": customer_id})
    if not user:
        return
    
    # Check if this is a partner subscription renewal payment
    if subscription_id and user.get("partner_subscription_id") == subscription_id:
        if not user.get("platform_fee_paid"):
            await db.users.update_one(
                {"id": user["id"]},
                {"$set": {
                    "platform_fee_paid": True,
                    "partner_fee_paid_at": datetime.now(timezone.utc).isoformat(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }}
            )
            await db.notifications.insert_one({
                "id": f"notif_{user['id']}_{datetime.now(timezone.utc).isoformat()}",
                "user_id": user["id"],
                "type": "partner_reactivated",
                "title": "Partner Account Re-Activated",
                "message": "Your annual partner fee payment was successful. Your partner features are restored!",
                "read": False,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(f"Partner re-activated via subscription renewal: user={user['id']}")
    
    # Log payment
    await db.payments.insert_one({
        "id": invoice.get("id"),
        "user_id": user["id"],
        "amount": invoice.get("amount_paid", 0) / 100,
        "currency": invoice.get("currency", "usd"),
        "status": "succeeded",
        "created_at": datetime.now(timezone.utc).isoformat()
    })


async def _handle_payment_failed(db, invoice):
    """Handle failed payment — includes partner soft lock on recurring failure"""
    customer_id = invoice.get("customer")
    subscription_id = invoice.get("subscription")
    
    user = await db.users.find_one({"stripe_customer_id": customer_id})
    if not user:
        return
    
    # Check if this is a partner subscription payment failure
    if subscription_id and user.get("partner_subscription_id") == subscription_id:
        await db.users.update_one(
            {"id": user["id"]},
            {"$set": {
                "platform_fee_paid": False,
                "partner_fee_payment_failed_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        await db.notifications.insert_one({
            "id": f"notif_{user['id']}_{datetime.now(timezone.utc).isoformat()}",
            "user_id": user["id"],
            "type": "partner_fee_payment_failed",
            "title": "Partner Fee Payment Failed",
            "message": "Your annual partner fee payment failed. Please update your payment method to continue listing.",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        logger.info(f"Partner soft-locked due to payment failure: user={user['id']}")
    
    # Log failed payment
    await db.payments.insert_one({
        "id": invoice.get("id"),
        "user_id": user["id"],
        "amount": invoice.get("amount_due", 0) / 100,
        "currency": invoice.get("currency", "usd"),
        "status": "failed",
        "failure_reason": invoice.get("last_finalization_error", {}).get("message"),
        "created_at": datetime.now(timezone.utc).isoformat()
    })


def _map_price_to_tier(price_id: str) -> str:
    """Map Stripe price ID to subscription tier using centralized mapping"""
    return get_tier_from_price_id(price_id)



async def _handle_auction_payment_succeeded(db, pi_data: dict, meta: dict):
    """
    Handle a successful non-vehicle auction/listing payment.
    
    Two paths:
    1. If transfer_data.destination was set in the PaymentIntent (standard Connect flow),
       Stripe auto-transfers to the seller. We just record the payout.
    2. If no transfer_data (seller without Connect), create a manual Transfer using
       PricingManager to calculate the exact seller payout.
    """
    import stripe
    import os
    import uuid as _uuid
    import traceback

    stripe.api_key = os.environ.get("STRIPE_API_KEY")
    pi_id = pi_data.get("id")
    amount = pi_data.get("amount", 0)
    transfer_data = pi_data.get("transfer_data") or {}
    transfer_group = meta.get("transfer_group", "")
    seller_id = meta.get("seller_id", "")
    listing_id = meta.get("listing_id", "")
    flow_type = meta.get("flow_type", "STANDARD_FLOW")

    now = datetime.now(timezone.utc).isoformat()
    logger.info(f"[AuctionPayout] PI {pi_id} succeeded — amount={amount}, seller={seller_id}, flow={flow_type}")

    # Calculate seller payout using PricingManager
    try:
        from services.pricing_manager import PricingManager

        hammer_price = float(meta.get("hammer_price", 0)) / 100 if meta.get("hammer_price") else amount / 100
        province = meta.get("province", "ON")
        seller_tier = meta.get("seller_tier", "free")
        buyer_tier = meta.get("buyer_tier", "free")

        # Use PricingManager for exact payout calculation
        if flow_type == "PARTNER_FLOW":
            result = PricingManager.partner_auction(hammer_price, province)
        else:
            result = PricingManager.non_vehicle_stripe(hammer_price, province, buyer_tier, seller_tier)

        si = result.seller_invoice
        seller_payout_amount = si.total if si else hammer_price
        seller_payout_cents = int(round(seller_payout_amount * 100))
        logger.info(f"[AuctionPayout] PricingManager calculated: payout=${seller_payout_amount}")
    except Exception as e:
        logger.error(f"[AuctionPayout] PricingManager FAILED: {e}\n{traceback.format_exc()}")
        return

    # Check if auto-transfer happened (transfer_data.destination was set)
    auto_transferred = bool(transfer_data.get("destination"))
    transfer_id = None

    # ── ESCROW SYSTEM: For non-vehicle items, hold funds instead of transferring ──
    is_vehicle_flow = flow_type in ("VEHICLE_FLOW", "VEHICLE_PLATFORM_FEE")
    escrow_created = False

    if not is_vehicle_flow and not auto_transferred and seller_id:
        # Create escrow hold — funds stay on platform until pickup code confirmed
        try:
            from services.escrow_service import create_escrow_hold
            buyer_id = meta.get("user_id", "")
            province = meta.get("province", "ON")
            application_fee_cents = amount - seller_payout_cents

            await create_escrow_hold(
                db=db,
                auction_id=listing_id,
                listing_id=listing_id,
                buyer_id=buyer_id,
                seller_id=seller_id,
                hammer_price_cents=int(round(hammer_price * 100)),
                total_charged_cents=amount,
                application_fee_cents=application_fee_cents,
                stripe_payment_intent_id=pi_id,
                province=province,
            )
            escrow_created = True
            logger.info(f"[AuctionPayout] Escrow hold created for PI {pi_id} — transfer deferred until pickup code")
        except Exception as e:
            logger.error(f"[AuctionPayout] Escrow creation failed, falling back to direct transfer: {e}")
            # Fallback: do direct transfer if escrow fails
            escrow_created = False

    if not escrow_created and not auto_transferred and seller_id:
        # Direct transfer (fallback or vehicle items)
        seller = await db.users.find_one({"id": seller_id}, {"_id": 0, "stripe_connect_account_id": 1})
        connect_id = (seller or {}).get("stripe_connect_account_id")

        if connect_id:
            try:
                transfer = stripe.Transfer.create(
                    amount=seller_payout_cents,
                    currency="cad",
                    destination=connect_id,
                    transfer_group=transfer_group,
                    metadata={
                        "payment_intent": pi_id,
                        "listing_id": listing_id,
                        "seller_id": seller_id,
                        "payout_type": "manual_post_payment",
                    },
                )
                transfer_id = transfer.id
                logger.info(f"[AuctionPayout] Manual transfer created: {transfer_id} → {connect_id} for ${seller_payout_cents / 100:.2f}")
            except Exception as e:
                logger.error(f"[AuctionPayout] Transfer failed for PI {pi_id}: {e}")
        else:
            logger.warning(f"[AuctionPayout] Seller {seller_id} has no Connect account — payout pending")
    elif auto_transferred:
        logger.info(f"[AuctionPayout] Auto-transfer via Connect for PI {pi_id}")

    # Record the payout in MongoDB
    payout_record = {
        "id": str(_uuid.uuid4()),
        "payment_intent_id": pi_id,
        "listing_id": listing_id,
        "seller_id": seller_id,
        "buyer_id": meta.get("user_id", ""),
        "transfer_group": transfer_group,
        "flow_type": flow_type,

        "amount_charged_cents": amount,
        "seller_payout_cents": seller_payout_cents,
        "application_fee_cents": amount - seller_payout_cents,
        "seller_payout_amount": seller_payout_amount,

        "pricing_breakdown": {
            "hammer_price": hammer_price,
            "buyer_premium": result.buyer_invoice.fees_subtotal,
            "seller_commission": si.fees_subtotal if si else 0,
            "seller_stripe_fee": si.stripe_recovery if si else 0,
            "seller_tax": si.tax_amount if si else 0,
            "seller_tax_type": si.tax_type if si else "",
            "seller_tax_label": si.tax_label if si else "",
        },

        "auto_transferred": auto_transferred,
        "manual_transfer_id": transfer_id,
        "escrow_held": escrow_created,
        "status": "escrow_held" if escrow_created else ("transferred" if (auto_transferred or transfer_id) else "pending_connect"),
        "created_at": now,
    }

    try:
        result = await db.seller_payouts.insert_one(payout_record)
        logger.info(f"[AuctionPayout] Payout record saved: seller=${seller_payout_cents / 100:.2f}, status={payout_record['status']}, inserted_id={result.inserted_id}")
    except Exception as e:
        logger.error(f"[AuctionPayout] DB insert FAILED: {e}\n{traceback.format_exc()}")


    # ── Affiliate Commission Payout ──
    try:
        buyer_id = meta.get("user_id", "")
        if buyer_id:
            buyer_doc = await db.users.find_one({"id": buyer_id}, {"_id": 0, "referred_by": 1})
            affiliate_id = (buyer_doc or {}).get("referred_by")

            if affiliate_id:
                from services.pricing_manager import PricingManager
                aff_commission = PricingManager.affiliate_commission(result.bidvex_revenue)
                aff_commission_cents = int(round(aff_commission * 100))

                if aff_commission_cents > 0:
                    # Record affiliate earning
                    earning_id = str(_uuid.uuid4())
                    await db.affiliate_earnings.insert_one({
                        "id": earning_id,
                        "affiliate_id": affiliate_id,
                        "referred_user_id": buyer_id,
                        "payment_intent_id": pi_id,
                        "listing_id": listing_id,
                        "bidvex_revenue": result.bidvex_revenue,
                        "commission_rate": 0.10,
                        "commission_amount": aff_commission,
                        "commission_cents": aff_commission_cents,
                        "status": "pending",
                        "payout_after": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
                        "stripe_transfer_id": None,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    })

                    # Mark referral as converted if first purchase
                    await db.affiliate_referrals.update_one(
                        {"affiliate_id": affiliate_id, "referred_user_id": buyer_id, "converted": False},
                        {"$set": {"converted": True, "status": "converted", "first_purchase_at": datetime.now(timezone.utc).isoformat()}}
                    )

                    # Try immediate Stripe Transfer to affiliate's Connect account
                    affiliate_doc = await db.users.find_one({"id": affiliate_id}, {"_id": 0, "stripe_connect_account_id": 1})
                    aff_connect_id = (affiliate_doc or {}).get("stripe_connect_account_id")

                    if aff_connect_id:
                        try:
                            aff_transfer = stripe.Transfer.create(
                                amount=aff_commission_cents,
                                currency="cad",
                                destination=aff_connect_id,
                                metadata={
                                    "type": "affiliate_commission",
                                    "affiliate_id": affiliate_id,
                                    "payment_intent": pi_id,
                                    "listing_id": listing_id,
                                    "description": f"Affiliate Commission for Order #{listing_id[:8]}",
                                },
                            )
                            await db.affiliate_earnings.update_one(
                                {"id": earning_id},
                                {"$set": {"status": "transferred", "stripe_transfer_id": aff_transfer.id}}
                            )
                            logger.info(f"[AffiliatePayout] Transfer {aff_transfer.id} → {aff_connect_id} for ${aff_commission:.2f}")
                        except Exception as te:
                            logger.error(f"[AffiliatePayout] Transfer failed: {te}")
                    else:
                        logger.info(f"[AffiliatePayout] Affiliate {affiliate_id} has no Connect account — commission ${aff_commission:.2f} held as pending")

    except Exception as aff_err:
        logger.error(f"[AffiliatePayout] Error: {aff_err}")


# Feature packs for promoted listings (mirrors /payments/promote-listing)
PROMOTION_FEATURE_PACK = {
    "marketplace": {
        "basic":    ["Homepage highlight", "Search priority"],
        "standard": ["Homepage highlight", "Search priority", "Category banner"],
        "premium":  ["Homepage highlight", "Search priority", "Category banner", "Email blast", "Social share"],
    },
    "lots": {
        "basic":    ["Search priority", "Homepage placement"],
        "standard": ["Search priority", "Homepage placement", "Category banner", "Featured badge"],
        "premium":  ["Search priority", "Homepage placement", "Category banner", "Featured badge",
                     "Email blast", "Social share", "Featured Partner badge"],
    },
    "storage": {
        "basic":    ["Homepage highlight", "Search priority"],
        "standard": ["Homepage highlight", "Search priority", "Category banner on Storage page"],
        "premium":  ["Homepage highlight", "Search priority", "Category banner on Storage page",
                     "Email blast to storage waitlist", "Social share"],
    },
    "partner": {
        "basic":    ["Search priority", "Homepage placement"],
        "standard": ["Search priority", "Homepage placement", "Category banner", "Featured badge"],
        "premium":  ["Search priority", "Homepage placement", "Category banner", "Featured badge",
                     "Email blast", "Social share", "Featured Partner badge"],
    },
}


async def _handle_listing_promotion_paid(db, session):
    """Activate a listing promotion after Stripe checkout.session.completed."""
    metadata = session.get("metadata", {}) or {}
    listing_id = metadata.get("listing_id")
    listing_type = (metadata.get("listing_type") or "marketplace").lower()
    tier = (metadata.get("boost_tier") or "basic").lower()
    seller_id = metadata.get("seller_id")
    boost_days = int(metadata.get("boost_days") or 7)
    session_id = session.get("id")

    if not listing_id:
        logger.warning("[promotion-paid] missing listing_id in metadata")
        return

    now = datetime.now(timezone.utc)
    promotion_end = now + timedelta(days=boost_days)
    tier_weight = {"premium": 3, "standard": 2, "basic": 1}.get(tier, 0)

    listings_coll = db.storage_auctions if listing_type == "storage" else db.listings

    features = PROMOTION_FEATURE_PACK.get(listing_type, PROMOTION_FEATURE_PACK["marketplace"]).get(tier, [])
    update_doc = {
        "is_promoted": True,
        "is_featured": True,
        "promotion_tier": tier,
        "promotion_tier_weight": tier_weight,
        "promotion_start": now.isoformat(),
        "promotion_end": promotion_end.isoformat(),
        "promoted_until": promotion_end.isoformat(),
        "promotion_features": features,
        "promotion_activated_at": now.isoformat(),
    }
    await listings_coll.update_one({"id": listing_id}, {"$set": update_doc})

    try:
        await db.promotions.update_one(
            {"session_id": session_id},
            {"$set": {
                "status": "active",
                "payment_status": "paid",
                "start_date": now.isoformat(),
                "end_date": promotion_end.isoformat(),
                "activated_at": now.isoformat(),
            }},
        )
    except Exception as e:
        logger.warning(f"[promotion-paid] could not update promotions doc: {e}")

    if tier == "premium":
        try:
            import uuid as _uuid
            await db.social_share_queue.insert_one({
                "id": _uuid.uuid4().hex,
                "listing_id": listing_id,
                "listing_type": listing_type,
                "seller_id": seller_id,
                "tier": tier,
                "requested_at": now.isoformat(),
                "status": "pending",
            })
        except Exception as e:
            logger.warning(f"[promotion-paid] social share queue insert failed: {e}")

    try:
        listing_doc = await listings_coll.find_one({"id": listing_id}, {"_id": 0})
        seller_doc = await db.users.find_one({"id": seller_id}, {"_id": 0, "name": 1, "email": 1})
        if seller_doc and seller_doc.get("email"):
            from services.email_notifications import send_promotion_confirmation_email
            await send_promotion_confirmation_email(
                seller_email=seller_doc["email"],
                seller_name=seller_doc.get("name", "Seller"),
                listing_title=(listing_doc or {}).get("title") or "Your listing",
                listing_id=listing_id,
                listing_type=listing_type,
                tier=tier,
                boost_days=boost_days,
                start_date=now,
                end_date=promotion_end,
                base_price=float(metadata.get("base_price", 0) or 0),
                gst=float(metadata.get("gst", 0) or 0),
                qst=float(metadata.get("qst", 0) or 0),
                stripe_fee=float(metadata.get("stripe_fee", 0) or 0),
                grand_total=float(metadata.get("grand_total", 0) or 0),
                features=features,
            )
    except Exception as e:
        logger.warning(f"[promotion-paid] confirmation email failed: {e}")

    logger.info(
        f"[promotion-paid] listing {listing_id} ({listing_type}) → {tier} until {promotion_end.isoformat()}"
    )




async def _handle_checkout_completed(db, session):
    """
    Handle checkout.session.completed webhook for auction purchases
    AND partner activation payments.
    """
    session_id = session.get("id")
    metadata = session.get("metadata", {})
    
    payment_type = metadata.get("type")
    
    logger.info(f"Processing checkout completed: {session_id}, type: {payment_type}")
    
    # ── Partner Activation Checkout ──
    if payment_type == "partner_activation":
        user_id = metadata.get("user_id")
        if not user_id:
            logger.warning("Partner activation checkout missing user_id in metadata")
            return
        
        subscription_id = session.get("subscription")
        
        await db.users.update_one(
            {"id": user_id},
            {"$set": {
                "platform_fee_paid": True,
                "partner_subscription_id": subscription_id,
                "partner_fee_paid_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }}
        )
        
        logger.info(f"Partner activated via checkout: user={user_id}, subscription={subscription_id}")
        
        # Create a notification for the user
        await db.notifications.insert_one({
            "id": f"notif_{user_id}_{datetime.now(timezone.utc).isoformat()}",
            "user_id": user_id,
            "type": "partner_activated",
            "title": "Partner Account Activated",
            "message": "Your annual partner fee payment was successful. Your partner features are now fully unlocked!",
            "read": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        return
    
    # ── Standard Auction Purchase Checkout ──
    invoice_id = metadata.get("invoice_id")
    
    logger.info(f"Processing checkout completed: {session_id}, type: {payment_type}")
    
    # Get pending payment record
    pending = await db.pending_payments.find_one({"session_id": session_id})
    
    if not pending:
        logger.warning(f"No pending payment found for session {session_id}")
        return
    
    breakdown = pending.get("breakdown", {})
    
    # Update pending payment status
    await db.pending_payments.update_one(
        {"session_id": session_id},
        {"$set": {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "stripe_payment_intent": session.get("payment_intent")
        }}
    )
    
    if payment_type == "auction_purchase":
        # General auction - update listing
        listing_id = metadata.get("listing_id")
        buyer_id = metadata.get("buyer_id")
        
        # Get listing and update status
        listing = await db.listings.find_one({"id": listing_id})
        if listing:
            await db.listings.update_one(
                {"id": listing_id},
                {"$set": {
                    "status": "sold",
                    "payment_status": "paid",
                    "paid_at": datetime.now(timezone.utc).isoformat(),
                    "stripe_session_id": session_id,
                    "invoice_id": invoice_id
                }}
            )
            
            # Send confirmation emails
            await _send_purchase_confirmation_emails(db, listing, buyer_id, breakdown, invoice_id)
            
            # Generate and store PDF invoice
            await _generate_and_store_invoice(db, listing, buyer_id, breakdown, invoice_id)

            # ── Affiliate Cash-Back Payout ──
            try:
                from services.connect_payment_engine import process_affiliate_payout
                await process_affiliate_payout(
                    db=db,
                    session_metadata=metadata,
                    payment_intent_id=session.get("payment_intent", ""),
                )
            except Exception as e:
                logger.warning(f"Affiliate payout processing error: {e}")
            
    elif payment_type == "vehicle_fees":
        # Vehicle auction - BidVex fees paid, hammer still due
        auction_id = metadata.get("auction_id")
        buyer_id = metadata.get("buyer_id")
        
        # Update vehicle auction status
        auction = await db.vehicle_auctions.find_one({"id": auction_id})
        if auction:
            await db.vehicle_auctions.update_one(
                {"id": auction_id},
                {"$set": {
                    "bidvex_fees_paid": True,
                    "bidvex_fees_paid_at": datetime.now(timezone.utc).isoformat(),
                    "stripe_session_id": session_id,
                    "invoice_id": invoice_id,
                    "hammer_price_status": "pending_bank_draft"
                }}
            )
            
            # Send vehicle-specific confirmation with Bank Draft instructions
            await _send_vehicle_fees_confirmation(db, auction, buyer_id, breakdown, invoice_id)
            
            # Generate invoice for fees
            await _generate_vehicle_fees_invoice(db, auction, buyer_id, breakdown, invoice_id)

    elif payment_type == "vehicle_buy_now":
        # Vehicle Buy Now — only platform fee (2.5%) settled via Stripe.
        # Hammer price is paid buyer ↔ seller directly outside BidVex.
        transaction_id = metadata.get("transaction_id")
        listing_id = metadata.get("listing_id")
        buyer_id = metadata.get("buyer_id")
        now = datetime.now(timezone.utc)

        if transaction_id:
            await db.vehicle_buy_now_transactions.update_one(
                {"id": transaction_id},
                {"$set": {
                    "payment_status": "paid",
                    "paid_at": now.isoformat(),
                    "stripe_session_id": session_id,
                    "card_charged": float(metadata.get("amount_total_cents", 0)) / 100 if metadata.get("amount_total_cents") else None,
                }},
            )

        if listing_id:
            await db.vehicle_listings.update_one(
                {"id": listing_id},
                {"$set": {
                    "status": "sold",
                    "sold_via_buy_now": True,
                    "winner_id": buyer_id,
                    "sold_at": now.isoformat(),
                }},
            )

        # Winner email (is_vehicle=True)
        try:
            buyer = await db.users.find_one({"id": buyer_id}, {"_id": 0})
            listing = await db.vehicle_listings.find_one({"id": listing_id}, {"_id": 0})
            seller_doc = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0}) if listing else None
            if buyer and buyer.get("email"):
                from services.email_notifications import send_auction_won_email
                await send_auction_won_email(
                    to_email=buyer["email"],
                    to_name=buyer.get("name", "Buyer"),
                    auction_id=listing_id,
                    item_name=(listing.get("title") if listing else "Vehicle"),
                    hammer_price=float(listing.get("buy_now_price", 0.0)) if listing else 0.0,
                    platform_fee=float(metadata.get("platform_fee", 0) or 0),
                    seller_name=(seller_doc.get("name") if seller_doc else ""),
                    seller_contact=(seller_doc.get("email") if seller_doc else ""),
                    is_vehicle=True,
                    buyer_province=(buyer.get("province", "QC") or "QC"),
                )
        except Exception as e:
            logger.warning(f"Vehicle Buy Now winner email failed: {e}")

    elif payment_type == "buy_now":        # Buy Now purchase — mark transaction paid
        transaction_id = metadata.get("transaction_id")
        auction_id = metadata.get("auction_id")
        buyer_id = metadata.get("buyer_id")

        if transaction_id:
            await db.buy_now_transactions.update_one(
                {"id": transaction_id},
                {"$set": {
                    "payment_status": "paid",
                    "paid_at": datetime.now(timezone.utc).isoformat(),
                    "stripe_session_id": session_id,
                }}
            )
            logger.info(f"Buy Now transaction {transaction_id} marked as paid")

        # Generate invoice for buy-now
        if auction_id and buyer_id:
            auction = await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0})
            if auction:
                buy_now_invoice_id = invoice_id or f"bn_{transaction_id[:8]}"
                await db.invoices.insert_one({
                    "id": buy_now_invoice_id,
                    "transaction_id": transaction_id,
                    "auction_id": auction_id,
                    "buyer_id": buyer_id,
                    "seller_id": auction.get("seller_id"),
                    "breakdown": breakdown,
                    "type": "buy_now",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                })

                # Send winner email — same template as auction winners (is_vehicle=False)
                try:
                    buyer = await db.users.find_one({"id": buyer_id}, {"_id": 0})
                    seller_doc = await db.users.find_one({"id": auction.get("seller_id")}, {"_id": 0})
                    if buyer and buyer.get("email"):
                        from services.email_notifications import send_auction_won_email
                        lot_number = metadata.get("lot_number", "")
                        lot_title = f"{auction.get('title', 'Auction')} — Lot #{lot_number}" if lot_number else auction.get("title", "Auction")
                        # Derive figures from the breakdown
                        hammer_price = float(breakdown.get("hammer_price") or 0.0) if isinstance(breakdown, dict) else 0.0
                        platform_fee = 0.0
                        if isinstance(breakdown, dict):
                            bi = breakdown.get("buyer_invoice") or {}
                            platform_fee = float(bi.get("fees_subtotal") or 0.0)
                        await send_auction_won_email(
                            to_email=buyer["email"],
                            to_name=buyer.get("name", "Buyer"),
                            auction_id=auction_id,
                            item_name=lot_title,
                            hammer_price=hammer_price,
                            platform_fee=platform_fee,
                            seller_name=(seller_doc.get("name") if seller_doc else ""),
                            seller_contact=(seller_doc.get("email") if seller_doc else ""),
                            is_vehicle=False,
                            buyer_province=(buyer.get("province", "QC") or "QC"),
                        )
                except Exception as e:
                    logger.warning(f"Failed to send buy-now winner email: {e}")

        # Schedule review request email (24h later)
        try:
            auction_obj = await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0})
            seller_doc = await db.users.find_one({"id": auction_obj["seller_id"]}, {"_id": 0}) if auction_obj else None
            await db.review_requests.update_one(
                {"transaction_id": transaction_id},
                {"$set": {
                    "transaction_id": transaction_id,
                    "buyer_id": buyer_id,
                    "item_title": auction_obj.get("title", "Item") if auction_obj else "Item",
                    "seller_name": seller_doc.get("name", "Seller") if seller_doc else "Seller",
                    "send_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                    "sent": False,
                }},
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"Failed to schedule review request: {e}")

    elif payment_type == "auction_winner":
        # Auction winner payment — mark listing fully paid
        listing_id = metadata.get("listing_id")
        buyer_id = metadata.get("buyer_id")
        late_penalty = float(metadata.get("late_penalty", "0"))

        if listing_id:
            listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
            if listing:
                await db.listings.update_one(
                    {"id": listing_id},
                    {"$set": {
                        "status": "sold",
                        "payment_status": "paid",
                        "paid_at": datetime.now(timezone.utc).isoformat(),
                        "stripe_session_id": session_id,
                        "late_penalty_charged": late_penalty,
                    }}
                )
                logger.info(f"Auction winner payment completed for listing {listing_id}")

                # Generate and store invoice
                winner_invoice_id = invoice_id or f"aw_{listing_id[:8]}"
                await _generate_and_store_invoice(db, listing, buyer_id, breakdown, winner_invoice_id)

                # Send confirmation emails
                await _send_purchase_confirmation_emails(db, listing, buyer_id, breakdown, winner_invoice_id)

                # Update pending payment
                await db.pending_payments.update_one(
                    {"listing_id": listing_id, "buyer_id": buyer_id, "type": "auction_winner"},
                    {"$set": {"status": "completed", "completed_at": datetime.now(timezone.utc).isoformat()}}
                )

                # Schedule review request email (24h later)
                try:
                    seller_doc = await db.users.find_one({"id": listing["seller_id"]}, {"_id": 0})
                    await db.review_requests.update_one(
                        {"transaction_id": listing_id},
                        {"$set": {
                            "transaction_id": listing_id,
                            "buyer_id": buyer_id,
                            "item_title": listing.get("title", "Item"),
                            "seller_name": seller_doc.get("name", "Seller") if seller_doc else "Seller",
                            "send_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
                            "sent": False,
                        }},
                        upsert=True,
                    )
                except Exception as e:
                    logger.warning(f"Failed to schedule review request: {e}")

                # ── Affiliate Cash-Back Payout ──
                try:
                    from services.connect_payment_engine import process_affiliate_payout
                    await process_affiliate_payout(
                        db=db,
                        session_metadata=metadata,
                        payment_intent_id=session.get("payment_intent", ""),
                    )
                except Exception as e:
                    logger.warning(f"Affiliate payout processing error: {e}")
    
    logger.info(f"Checkout completed processing finished: {session_id}")

    # ── Listing Promotion Checkout ──
    if payment_type == "promotion" or payment_type == "listing_promotion":
        listing_id = metadata.get("listing_id")
        user_id = metadata.get("user_id")
        tier = metadata.get("promotion_tier", "basic")
        duration_days = int(metadata.get("duration_days", "7"))

        now = datetime.now(timezone.utc)

        # Activate promotion
        await db.promotions.update_one(
            {"listing_id": listing_id, "user_id": user_id, "status": "pending_payment"},
            {"$set": {
                "status": "active",
                "start_date": now.isoformat(),
                "end_date": (now + timedelta(days=duration_days)).isoformat(),
                "paid_at": now.isoformat(),
                "stripe_session_id": session_id,
            }},
        )

        # Mark listing as promoted
        await db.listings.update_one(
            {"id": listing_id},
            {"$set": {
                "is_promoted": True,
                "promotion_tier": tier,
                "promotion_end": (now + timedelta(days=duration_days)).isoformat(),
            }},
        )
        logger.info(f"Promotion activated: listing={listing_id}, tier={tier}, days={duration_days}")

    # ── Email Marketing Credits Checkout ──
    elif payment_type == "email_credits":
        user_id = metadata.get("user_id")
        quantity = int(metadata.get("credit_quantity", "0"))

        if user_id and quantity > 0:
            await db.users.update_one(
                {"id": user_id},
                {"$inc": {"email_credits": quantity}},
            )
            # Log the purchase
            await db.email_credit_purchases.insert_one({
                "user_id": user_id,
                "quantity": quantity,
                "stripe_session_id": session_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            })
            logger.info(f"Email credits added: user={user_id}, quantity={quantity}")

    # ── Update payment_transactions is_paid for all types ──
    await db.payment_transactions.update_one(
        {"session_id": session_id},
        {"$set": {
            "payment_status": "paid",
            "is_paid": True,
            "paid_at": datetime.now(timezone.utc).isoformat(),
            "stripe_payment_intent": session.get("payment_intent"),
        }},
    )


async def _send_purchase_confirmation_emails(db, listing, buyer_id, breakdown, invoice_id):
    """Send confirmation emails to buyer and seller after successful purchase"""
    try:
        # Get buyer and seller info
        buyer = await db.users.find_one({"id": buyer_id})
        seller = await db.users.find_one({"id": listing["seller_id"]})
        
        if not buyer or not seller:
            logger.warning("Could not find buyer or seller for email notification")
            return
        
        # Import email service (SendGrid)
        from services.email_service import send_email
        
        # Send buyer confirmation
        await send_email(
            to_email=buyer.get("email"),
            subject=f"Payment Confirmed - {listing.get('title', 'Auction Item')}",
            template="purchase_confirmation",
            data={
                "buyer_name": buyer.get("name", "Buyer"),
                "item_title": listing.get("title"),
                "hammer_price": breakdown.get("hammer_price"),
                "buyer_total": breakdown.get("buyer_total"),
                "invoice_id": invoice_id,
                "seller_name": seller.get("name")
            }
        )
        
        # Send seller notification
        await send_email(
            to_email=seller.get("email"),
            subject=f"Sale Complete - {listing.get('title', 'Auction Item')}",
            template="sale_notification",
            data={
                "seller_name": seller.get("name", "Seller"),
                "item_title": listing.get("title"),
                "hammer_price": breakdown.get("hammer_price"),
                "seller_payout": breakdown.get("seller_payout"),
                "buyer_name": buyer.get("name")
            }
        )
        
        logger.info(f"Sent purchase confirmation emails for listing {listing['id']}")
        
    except Exception as e:
        logger.error(f"Failed to send purchase confirmation emails: {e}")


async def _send_vehicle_fees_confirmation(db, auction, buyer_id, breakdown, invoice_id):
    """Send confirmation email with Bank Draft instructions for vehicle purchase"""
    try:
        buyer = await db.users.find_one({"id": buyer_id})
        seller = await db.users.find_one({"id": auction.get("seller_id")})
        
        if not buyer or not seller:
            return
        
        from services.email_service import send_email
        
        await send_email(
            to_email=buyer.get("email"),
            subject="BidVex Fees Paid - Bank Draft Required",
            template="vehicle_fees_confirmation",
            data={
                "buyer_name": buyer.get("name"),
                "vehicle_title": auction.get("title", "Vehicle"),
                "fees_paid": breakdown.get("buyer_total"),
                "hammer_price_due": breakdown.get("hammer_price"),
                "seller_name": seller.get("name"),
                "seller_address": seller.get("address", "Contact seller for address"),
                "deadline_days": 14,
                "invoice_id": invoice_id
            }
        )
        
        logger.info(f"Sent vehicle fees confirmation for auction {auction['id']}")
        
    except Exception as e:
        logger.error(f"Failed to send vehicle fees confirmation: {e}")


async def _generate_and_store_invoice(db, listing, buyer_id, breakdown, invoice_id):
    """Generate PDF invoice and store URL in database"""
    try:
        from services.invoice_generator import generate_marketplace_invoice
        
        # Get buyer and seller info
        buyer = await db.users.find_one({"id": buyer_id})
        seller = await db.users.find_one({"id": listing["seller_id"]})
        
        # Generate PDF and upload to cloud storage
        invoice_url = await generate_marketplace_invoice(
            db=db,
            invoice_id=invoice_id,
            listing=listing,
            buyer=buyer,
            seller=seller,
            breakdown=breakdown,
            language=buyer.get("preferred_language", "en")
        )
        
        # Store invoice record
        await db.invoices.insert_one({
            "id": invoice_id,
            "listing_id": listing["id"],
            "buyer_id": buyer_id,
            "seller_id": listing["seller_id"],
            "breakdown": breakdown,
            "pdf_url": invoice_url,
            "type": "marketplace_purchase",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Update listing with invoice URL
        await db.listings.update_one(
            {"id": listing["id"]},
            {"$set": {"invoice_url": invoice_url}}
        )
        
        logger.info(f"Generated and stored invoice {invoice_id}")
        
    except Exception as e:
        logger.error(f"Failed to generate invoice: {e}")


async def _generate_vehicle_fees_invoice(db, auction, buyer_id, breakdown, invoice_id):
    """Generate PDF invoice for vehicle BidVex fees"""
    try:
        from services.invoice_generator import generate_vehicle_fees_invoice
        
        buyer = await db.users.find_one({"id": buyer_id})
        seller = await db.users.find_one({"id": auction.get("seller_id")})
        
        invoice_url = await generate_vehicle_fees_invoice(
            db=db,
            invoice_id=invoice_id,
            auction=auction,
            buyer=buyer,
            seller=seller,
            breakdown=breakdown,
            language=buyer.get("preferred_language", "en")
        )
        
        await db.invoices.insert_one({
            "id": invoice_id,
            "auction_id": auction["id"],
            "buyer_id": buyer_id,
            "seller_id": auction.get("seller_id"),
            "breakdown": breakdown,
            "pdf_url": invoice_url,
            "type": "vehicle_fees",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        await db.vehicle_auctions.update_one(
            {"id": auction["id"]},
            {"$set": {"invoice_url": invoice_url}}
        )
        
        logger.info(f"Generated vehicle fees invoice {invoice_id}")
        
    except Exception as e:
        logger.error(f"Failed to generate vehicle fees invoice: {e}")




# ========== TRUST VERIFICATION HANDLERS ==========

async def _handle_setup_intent_succeeded(db, setup_intent_data):
    """
    Handle setup_intent.succeeded webhook event.

    When a SetupIntent succeeds:
    1. Save the payment_method_id to the user's Stripe Customer
    2. Update MongoDB user: trust_status = "verified"
    3. Store payment method details
    """
    import stripe

    customer_id = setup_intent_data.get("customer")
    payment_method_id = setup_intent_data.get("payment_method")
    metadata = setup_intent_data.get("metadata", {})
    user_id = metadata.get("user_id")

    logger.info(f"Processing SetupIntent succeeded: customer={customer_id}, user_id={user_id}")

    if not customer_id or not payment_method_id:
        logger.warning("SetupIntent missing customer or payment_method")
        return

    user = None
    if user_id:
        user = await db.users.find_one({"id": user_id})
    if not user:
        user = await db.users.find_one({"stripe_customer_id": customer_id})

    if not user:
        logger.warning(f"No user found for customer {customer_id}")
        return

    user_id = user.get("id")

    try:
        stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": payment_method_id},
        )

        pm = stripe.PaymentMethod.retrieve(payment_method_id)

        await db.users.update_one(
            {"id": user_id},
            {"$set": {
                "trust_status": "verified",
                "trust_verified_at": datetime.now(timezone.utc).isoformat(),
                "default_payment_method_id": payment_method_id,
                "has_payment_method": True,
                "stripe_customer_id": customer_id,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

        await db.payment_methods.update_one(
            {"user_id": user_id, "stripe_payment_method_id": payment_method_id},
            {"$set": {
                "user_id": user_id,
                "stripe_payment_method_id": payment_method_id,
                "brand": pm.card.brand if pm.card else "unknown",
                "last4": pm.card.last4 if pm.card else "****",
                "exp_month": pm.card.exp_month if pm.card else 0,
                "exp_year": pm.card.exp_year if pm.card else 0,
                "is_default": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

        logger.info(f"Trust status verified for user {user_id}")

    except stripe.StripeError as e:
        logger.error(f"Stripe error in SetupIntent handler: {e}")
    except Exception as e:
        logger.error(f"Error processing SetupIntent: {e}")


async def _handle_payment_method_attached(db, pm_data):
    """
    Backup handler for payment_method.attached webhook event.

    If setup_intent.succeeded was missed, this catches the payment method
    being attached to a customer and verifies trust status.
    """
    import stripe

    customer_id = pm_data.get("customer")
    payment_method_id = pm_data.get("id")

    if not customer_id or not payment_method_id:
        return

    user = await db.users.find_one({"stripe_customer_id": customer_id})
    if not user:
        logger.info(f"payment_method.attached: No user for customer {customer_id}")
        return

    if user.get("trust_status") == "verified":
        logger.info(f"payment_method.attached: User {user['id']} already verified, skipping")
        return

    user_id = user.get("id")

    try:
        pm = stripe.PaymentMethod.retrieve(payment_method_id)

        stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": payment_method_id},
        )

        await db.users.update_one(
            {"id": user_id},
            {"$set": {
                "trust_status": "verified",
                "trust_verified_at": datetime.now(timezone.utc).isoformat(),
                "default_payment_method_id": payment_method_id,
                "has_payment_method": True,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

        await db.payment_methods.update_one(
            {"user_id": user_id, "stripe_payment_method_id": payment_method_id},
            {"$set": {
                "user_id": user_id,
                "stripe_payment_method_id": payment_method_id,
                "brand": pm.card.brand if pm.card else "unknown",
                "last4": pm.card.last4 if pm.card else "****",
                "exp_month": pm.card.exp_month if pm.card else 0,
                "exp_year": pm.card.exp_year if pm.card else 0,
                "is_default": True,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

        logger.info(f"Trust status verified via payment_method.attached for user {user_id}")

    except Exception as e:
        logger.error(f"Error in payment_method.attached handler: {e}")
