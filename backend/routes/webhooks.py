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
        
        # Process checkout session completed (auction purchases)
        elif event_type == "checkout.session.completed":
            await _handle_checkout_completed(db, data)
        
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


async def _handle_checkout_completed(db, session):
    """
    Handle checkout.session.completed webhook for auction purchases
    
    This triggers when buyer completes payment via Stripe Checkout.
    Actions:
    1. Update listing/auction status to "Paid"
    2. Send confirmation emails to buyer and seller
    3. Generate and store PDF invoice
    """
    session_id = session.get("id")
    metadata = session.get("metadata", {})
    
    payment_type = metadata.get("type")
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
    
    logger.info(f"Checkout completed processing finished: {session_id}")


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

