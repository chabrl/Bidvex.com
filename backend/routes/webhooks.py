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

@webhooks_router.post("/sendgrid")
async def handle_sendgrid_webhook(request: Request):
    """
    Handle SendGrid webhook events for email tracking.
    Events include: delivered, opened, clicked, bounced, unsubscribed, spam_report
    """
    try:
        body = await request.body()
        events = json.loads(body)
        
        if not isinstance(events, list):
            events = [events]
        
        db = get_db()
        processed = 0
        
        for event in events:
            event_type = event.get("event")
            email = event.get("email", "").lower()
            campaign_id = event.get("campaign_id")
            timestamp = event.get("timestamp")
            
            if not event_type or not email:
                continue
            
            # Store event
            event_record = {
                "id": f"{email}_{event_type}_{timestamp}",
                "event_type": event_type,
                "email": email,
                "campaign_id": campaign_id,
                "timestamp": timestamp,
                "sg_message_id": event.get("sg_message_id"),
                "sg_event_id": event.get("sg_event_id"),
                "ip": event.get("ip"),
                "url": event.get("url"),
                "useragent": event.get("useragent"),
                "reason": event.get("reason"),
                "status": event.get("status"),
                "created_at": datetime.now(timezone.utc).isoformat()
            }
            
            await db.email_events.update_one(
                {"id": event_record["id"]},
                {"$set": event_record},
                upsert=True
            )
            
            # Process specific events
            if event_type == "bounce":
                # Mark email as bounced
                await db.email_suppressions.update_one(
                    {"email": email},
                    {"$set": {
                        "email": email,
                        "reason": "bounce",
                        "bounce_reason": event.get("reason"),
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }},
                    upsert=True
                )
                
            elif event_type == "unsubscribe":
                # Add to global suppression list
                await db.email_suppressions.update_one(
                    {"email": email},
                    {"$set": {
                        "email": email,
                        "reason": "unsubscribe",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }},
                    upsert=True
                )
                
            elif event_type == "spamreport":
                # Add to suppression and flag for review
                await db.email_suppressions.update_one(
                    {"email": email},
                    {"$set": {
                        "email": email,
                        "reason": "spam_report",
                        "created_at": datetime.now(timezone.utc).isoformat()
                    }},
                    upsert=True
                )
            
            # Update campaign stats if campaign_id present
            if campaign_id:
                stat_field = f"stats.{event_type}"
                
                # Try admin campaigns first
                await db.email_campaigns.update_one(
                    {"id": campaign_id},
                    {"$inc": {stat_field: 1}}
                )
                
                # Also try user campaigns
                await db.user_marketing_campaigns.update_one(
                    {"id": campaign_id},
                    {"$inc": {stat_field: 1}}
                )
            
            processed += 1
        
        logger.info(f"Processed {processed} SendGrid webhook events")
        from routes.monitoring import log_webhook_event
        import asyncio
        asyncio.ensure_future(log_webhook_event("sendgrid", f"batch_{processed}", "success", {"count": processed}))
        return {"status": "ok", "processed": processed}
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in SendGrid webhook")
        from routes.monitoring import log_webhook_event
        import asyncio
        asyncio.ensure_future(log_webhook_event("sendgrid", "invalid_json", "failed"))
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing SendGrid webhook: {e}")
        from routes.monitoring import log_webhook_event, log_error_event
        import asyncio
        asyncio.ensure_future(log_webhook_event("sendgrid", "processing_error", "failed", {"error": str(e)[:300]}))
        asyncio.ensure_future(log_error_event("sendgrid_webhook_failure", f"SendGrid webhook error: {str(e)[:200]}", severity="error"))
        raise HTTPException(status_code=500, detail="Internal error")


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
        await db.stripe_events.insert_one({
            "id": event.get("id"),
            "type": event_type,
            "data": data,
            "created_at": datetime.now(timezone.utc).isoformat()
        })

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
            session_type = data.get("metadata", {}).get("type", "")
            if session_type == "subscription_upgrade":
                pass  # handled by subscription events above
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
            if pi_meta.get("transaction_type") == "vehicle_platform_fee":
                from services.vehicle_fee_service import handle_vehicle_fee_succeeded
                await handle_vehicle_fee_succeeded(db, pi_id)
                logger.info(f"Vehicle platform fee paid: {pi_id}")

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

    elif payment_type == "buy_now":
        # Buy Now purchase — mark transaction paid
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

                # Send confirmation email
                try:
                    buyer = await db.users.find_one({"id": buyer_id}, {"_id": 0})
                    if buyer and buyer.get("email"):
                        from services.email_notifications import send_email
                        lot_number = metadata.get("lot_number", "")
                        lot_title = f"Lot #{lot_number}" if lot_number else "Item"
                        await send_email(
                            to_email=buyer["email"],
                            subject=f"Payment Confirmed - {auction.get('title', 'Buy Now Purchase')}",
                            html_content=f"<p>Hi {buyer.get('name', 'Buyer')},</p>"
                                         f"<p>Your Buy Now payment for <strong>{lot_title}</strong> "
                                         f"from <strong>{auction.get('title', 'Auction')}</strong> has been confirmed.</p>"
                                         f"<p>Transaction ID: {transaction_id}</p>"
                                         f"<p>Thank you for your purchase!</p>",
                        )
                except Exception as e:
                    logger.warning(f"Failed to send buy-now confirmation email: {e}")

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
