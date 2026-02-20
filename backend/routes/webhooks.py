"""
BidVex Webhooks Router
Handles external webhooks from third-party services:
- SendGrid (email events)
- Stripe (payment events)
"""

from fastapi import APIRouter, HTTPException, Request
from typing import Dict, Any, List
from datetime import datetime, timezone
import logging
import json

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
        return {"status": "ok", "processed": processed}
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON in SendGrid webhook")
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing SendGrid webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal error")


# ========== STRIPE WEBHOOKS ==========

@webhooks_router.post("/stripe")
async def handle_stripe_webhook(request: Request):
    """
    Handle Stripe webhook events for payment/subscription tracking.
    """
    import stripe
    import os
    
    try:
        payload = await request.body()
        sig_header = request.headers.get("stripe-signature")
        endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
        
        # Verify webhook signature if secret is configured
        if endpoint_secret and sig_header:
            try:
                event = stripe.Webhook.construct_event(
                    payload, sig_header, endpoint_secret
                )
            except stripe.error.SignatureVerificationError:
                logger.error("Stripe webhook signature verification failed")
                raise HTTPException(status_code=400, detail="Invalid signature")
        else:
            event = json.loads(payload)
        
        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})
        
        db = get_db()
        
        # Log the event
        await db.stripe_events.insert_one({
            "id": event.get("id"),
            "type": event_type,
            "data": data,
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        
        # Process subscription events
        if event_type == "customer.subscription.created":
            await _handle_subscription_created(db, data)
            
        elif event_type == "customer.subscription.updated":
            await _handle_subscription_updated(db, data)
            
        elif event_type == "customer.subscription.deleted":
            await _handle_subscription_deleted(db, data)
            
        elif event_type == "invoice.payment_succeeded":
            await _handle_payment_succeeded(db, data)
            
        elif event_type == "invoice.payment_failed":
            await _handle_payment_failed(db, data)
        
        return {"status": "ok", "event_type": event_type}
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {e}")
        raise HTTPException(status_code=500, detail="Internal error")


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
    """Handle subscription cancellation"""
    customer_id = subscription.get("customer")
    
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
    """Handle successful payment"""
    customer_id = invoice.get("customer")
    
    user = await db.users.find_one({"stripe_customer_id": customer_id})
    if not user:
        return
    
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
    """Handle failed payment"""
    customer_id = invoice.get("customer")
    
    user = await db.users.find_one({"stripe_customer_id": customer_id})
    if not user:
        return
    
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
    
    # Could send notification to user about failed payment


def _map_price_to_tier(price_id: str) -> str:
    """Map Stripe price ID to subscription tier"""
    import os
    
    premium_price = os.environ.get("STRIPE_PREMIUM_PRICE_ID", "")
    vip_price = os.environ.get("STRIPE_VIP_PRICE_ID", "")
    
    if price_id == vip_price:
        return "vip"
    elif price_id == premium_price:
        return "premium"
    else:
        return "free"
