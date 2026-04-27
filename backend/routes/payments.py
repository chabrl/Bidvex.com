"""
BidVex Payments Router
Core payment operations: Checkout, Payment Methods, Subscriptions, Advanced Checkout.
Fee calculations → payments_fees.py | Promotions & Credits → payments_promotions.py
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone
import logging
import uuid
import os
import stripe

from routes.payments_shared import (
    set_payments_db, set_payments_auth, get_db,
    get_current_user_wrapper, security,
)
from routes.payments_fees import fees_sub_router
from routes.payments_promotions import promotions_sub_router

# Configure Stripe API key
stripe.api_key = os.environ.get('STRIPE_API_KEY', '')

logger = logging.getLogger(__name__)

payments_router = APIRouter(prefix="/payments", tags=["Payments"])

# Include sub-routers
payments_router.include_router(fees_sub_router)
payments_router.include_router(promotions_sub_router)

# Re-export DI setters so server.py doesn't need to change its imports
__all__ = ["payments_router", "set_payments_db", "set_payments_auth"]


async def _auth(credentials):
    """Authenticate user from Bearer credentials."""
    fn = get_current_user_wrapper()
    if fn is None:
        raise RuntimeError("Auth not initialized")
    return await fn(credentials)


# ========== CHECKOUT ENDPOINTS ==========

class CheckoutRequest(BaseModel):
    # Subscription checkout fields
    price_id: Optional[str] = None
    success_url: Optional[str] = None
    cancel_url: Optional[str] = None
    # Legacy listing checkout fields
    listing_id: Optional[str] = None
    origin_url: Optional[str] = None


@payments_router.post("/checkout")
async def create_checkout_session(
    data: CheckoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Unified checkout endpoint.
    - With price_id → subscription checkout
    - With listing_id → listing purchase checkout
    """
    import stripe

    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _auth(credentials)
    db = get_db()

    user = await db.users.find_one({"id": current_user.id})
    customer_id = user.get("stripe_customer_id") if user else None

    if not customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=getattr(current_user, "name", current_user.email),
            metadata={"user_id": current_user.id},
        )
        customer_id = customer.id
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"stripe_customer_id": customer_id}},
        )

    # ── Listing purchase checkout (Stripe Connect) ──
    if data.listing_id:
        listing = await db.listings.find_one({"id": data.listing_id}, {"_id": 0})
        if not listing:
            raise HTTPException(status_code=404, detail="Listing not found")

        from services.connect_payment_engine import calculate_connect_checkout, create_connect_checkout_session

        # Get buyer and seller tiers
        buyer_tier = user.get("subscription_tier", "free")
        seller = await db.users.find_one({"id": listing.get("seller_id")})
        seller_tier = seller.get("subscription_tier", "free") if seller else "free"
        seller_is_partner = bool(seller.get("is_partner") and seller.get("platform_fee_paid")) if seller else False

        breakdown = calculate_connect_checkout(
            hammer_price=listing["current_price"],
            category=listing.get("category", "general"),
            buyer_tier=buyer_tier,
            seller_tier=seller_tier,
            currency=listing.get("currency", "CAD"),
            province=listing.get("region", "QC"),
            seller_is_partner=seller_is_partner,
        )

        origin = data.origin_url or "https://bidvex.com"
        result = await create_connect_checkout_session(
            db=db,
            buyer_id=current_user.id,
            listing=listing,
            breakdown=breakdown,
            success_url=f"{origin}/payment/success?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=f"{origin}/listing/{data.listing_id}",
            payment_type="listing_purchase",
        )

        # Record transaction with full breakdown
        txn = {
            "id": str(uuid.uuid4()),
            "session_id": result["session_id"],
            "user_id": current_user.id,
            "listing_id": data.listing_id,
            "seller_id": listing.get("seller_id", ""),
            "flow_type": breakdown["flow_type"],
            "amount": breakdown["buyer_total"],
            "hammer_price": breakdown["hammer_price"],
            "buyer_premium": breakdown["buyer_premium"],
            "platform_fee": breakdown["platform_fee"],
            "seller_commission": breakdown["seller_commission"],
            "partner_premium_retained": breakdown.get("partner_premium_retained", 0),
            "tax_gst": breakdown["gst"],
            "tax_qst": breakdown["qst"],
            "stripe_processing_fee": breakdown["stripe_processing_fee"],
            "currency": breakdown["currency"].lower(),
            "payment_status": "pending",
            "payment_type": "listing_purchase",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.payment_transactions.insert_one(txn)

        return {"url": result["checkout_url"], "session_id": result["session_id"], "breakdown": breakdown}

    # ── Subscription checkout ──
    if not data.price_id or not data.success_url:
        raise HTTPException(status_code=400, detail="price_id and success_url are required for subscription checkout")

    session = stripe.checkout.Session.create(
        customer=customer_id,
        payment_method_types=["card"],
        line_items=[{"price": data.price_id, "quantity": 1}],
        mode="subscription",
        success_url=data.success_url,
        cancel_url=data.cancel_url or data.success_url,
        metadata={"user_id": current_user.id},
    )

    return {"session_id": session.id, "url": session.url}


@payments_router.get("/status/{session_id}")
async def get_checkout_status(session_id: str):
    """Get checkout session status"""
    import stripe
    
    try:
        session = stripe.checkout.Session.retrieve(session_id)
        return {
            "status": session.status,
            "payment_status": session.payment_status,
            "customer": session.customer,
            "subscription": session.subscription
        }
    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))


# ========== SUBSCRIPTION STATUS ==========

@payments_router.get("/subscription/status")
async def get_subscription_status(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get current user's subscription status"""
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _auth(credentials)
    db = get_db()
    
    user = await db.users.find_one({"id": current_user.id})
    
    result = {
        "tier": user.get("subscription_tier", "free"),
        "source": user.get("subscription_source", "manual"),
        "status": user.get("subscription_status", "inactive"),
        "start_date": user.get("subscription_start_date"),
        "end_date": user.get("subscription_end_date")
    }
    
    # If Stripe subscription, get live status
    if user.get("stripe_subscription_id"):
        try:
            sub = stripe.Subscription.retrieve(user["stripe_subscription_id"])
            sub_data = dict(sub)
            result["stripe_status"] = sub_data.get("status", "unknown")
            start_ts = sub_data.get("start_date") or sub_data.get("billing_cycle_anchor")
            if start_ts:
                end_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc).replace(
                    year=datetime.fromtimestamp(start_ts, tz=timezone.utc).year + 1
                )
                result["stripe_current_period_end"] = end_dt.isoformat()
        except stripe.StripeError:
            result["stripe_status"] = "error"
    
    return result


# ========== PAYMENT METHODS ==========

@payments_router.post("/setup-intent")
async def create_setup_intent(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create a Stripe SetupIntent for collecting payment method
    
    This is used for Trust Status verification - a valid payment method
    automatically verifies the user and allows them to place bids.
    
    Returns:
        client_secret: For use with Stripe Elements/Checkout
    """
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _auth(credentials)
    db = get_db()
    
    user = await db.users.find_one({"id": current_user.id})
    customer_id = user.get("stripe_customer_id")
    
    # Create customer if doesn't exist
    if not customer_id:
        customer = stripe.Customer.create(
            email=current_user.email,
            name=getattr(current_user, 'name', current_user.email),
            metadata={"user_id": current_user.id, "platform": "bidvex"}
        )
        customer_id = customer.id
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"stripe_customer_id": customer_id}}
        )
    
    # Create SetupIntent
    setup_intent = stripe.SetupIntent.create(
        customer=customer_id,
        payment_method_types=["card"],
        metadata={
            "user_id": current_user.id,
            "purpose": "trust_verification"
        }
    )
    
    return {
        "client_secret": setup_intent.client_secret,
        "setup_intent_id": setup_intent.id,
        "customer_id": customer_id
    }


@payments_router.post("/setup-intent/confirm")
async def confirm_setup_intent(
    data: Dict[str, str],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Confirm that a SetupIntent was successful and update trust status
    
    Called by frontend after Stripe Elements confirms the payment method.
    This is a backup in case the webhook doesn't fire immediately.
    """
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    setup_intent_id = data.get("setup_intent_id")
    if not setup_intent_id:
        raise HTTPException(status_code=400, detail="SetupIntent ID required")
    
    current_user = await _auth(credentials)
    db = get_db()
    
    # Retrieve and verify the SetupIntent
    try:
        setup_intent = stripe.SetupIntent.retrieve(setup_intent_id)
        
        if setup_intent.status != "succeeded":
            raise HTTPException(
                status_code=400, 
                detail="SetupIntent not successful"
            )
        
        # Verify this belongs to the current user
        if setup_intent.metadata.get("user_id") != current_user.id:
            raise HTTPException(status_code=403, detail="SetupIntent does not belong to this user")
        
        payment_method_id = setup_intent.payment_method
        
        # Set as default payment method
        stripe.Customer.modify(
            setup_intent.customer,
            invoice_settings={"default_payment_method": payment_method_id}
        )
        
        # Update user trust status
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {
                "trust_status": "verified",
                "trust_verified_at": datetime.now(timezone.utc).isoformat(),
                "default_payment_method_id": payment_method_id,
                "has_payment_method": True,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        
        # Store payment method record
        pm = stripe.PaymentMethod.retrieve(payment_method_id)
        await db.payment_methods.update_one(
            {"user_id": current_user.id, "stripe_payment_method_id": payment_method_id},
            {"$set": {
                "user_id": current_user.id,
                "stripe_payment_method_id": payment_method_id,
                "brand": pm.card.brand,
                "last4": pm.card.last4,
                "exp_month": pm.card.exp_month,
                "exp_year": pm.card.exp_year,
                "is_default": True,
                "created_at": datetime.now(timezone.utc).isoformat()
            }},
            upsert=True
        )
        
        return {
            "status": "success",
            "trust_status": "verified",
            "payment_method": {
                "id": payment_method_id,
                "brand": pm.card.brand,
                "last4": pm.card.last4
            }
        }
        
    except stripe.StripeError as e:
        logger.error(f"Stripe error confirming SetupIntent: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@payments_router.get("/trust-status")
async def get_trust_status(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current user's trust verification status
    
    Returns:
        trust_status: "verified", "pending", or "unverified"
        has_payment_method: Boolean
        payment_method: Default payment method details (if exists)
    """
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    current_user = await _auth(credentials)
    db = get_db()
    
    user = await db.users.find_one({"id": current_user.id})
    
    trust_status = user.get("trust_status", "unverified")
    has_payment_method = user.get("has_payment_method", False)
    phone_verified = user.get("phone_verified", False)
    
    # Get default payment method
    payment_method = None
    customer_id = user.get("stripe_customer_id")
    
    if customer_id and has_payment_method:
        try:
            methods = stripe.PaymentMethod.list(customer=customer_id, type="card", limit=1)
            if methods.data:
                pm = methods.data[0]
                payment_method = {
                    "id": pm.id,
                    "brand": pm.card.brand,
                    "last4": pm.card.last4,
                    "exp_month": pm.card.exp_month,
                    "exp_year": pm.card.exp_year
                }
        except stripe.StripeError:
            pass
    
    return {
        "trust_status": trust_status,
        "is_verified": trust_status == "verified",
        "has_payment_method": has_payment_method,
        "phone_verified": phone_verified,
        "payment_method": payment_method,
        "trust_verified_at": user.get("trust_verified_at"),
        "can_bid": trust_status == "verified"
    }


@payments_router.post("/payment-methods")
async def add_payment_method(
    data: Dict[str, str],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Add a payment method, store in DB, and update trust status."""
    import stripe

    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _auth(credentials)
    db = get_db()

    payment_method_id = data.get("payment_method_id")
    if not payment_method_id:
        raise HTTPException(status_code=400, detail="Payment method ID required")

    try:
        user = await db.users.find_one({"id": current_user.id})
        customer_id = user.get("stripe_customer_id") if user else None

        if not customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=getattr(current_user, 'name', current_user.email),
                metadata={"user_id": current_user.id, "platform": "bidvex"},
            )
            customer_id = customer.id
            await db.users.update_one(
                {"id": current_user.id},
                {"$set": {"stripe_customer_id": customer_id}},
            )

        payment_method = stripe.PaymentMethod.retrieve(payment_method_id)
        stripe.PaymentMethod.attach(payment_method_id, customer=customer_id)

        stripe.Customer.modify(
            customer_id,
            invoice_settings={"default_payment_method": payment_method_id},
        )

        pm_doc = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "stripe_payment_method_id": payment_method_id,
            "card_brand": payment_method.card.brand if payment_method.card else "unknown",
            "last4": payment_method.card.last4 if payment_method.card else "****",
            "exp_month": payment_method.card.exp_month if payment_method.card else 0,
            "exp_year": payment_method.card.exp_year if payment_method.card else 0,
            "is_verified": True,
            "is_default": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }

        await db.payment_methods.insert_one(pm_doc)

        # Update user trust status
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {
                "trust_status": "verified",
                "has_payment_method": True,
                "default_payment_method_id": payment_method_id,
                "trust_verified_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )

        del pm_doc["_id"]  # MongoDB adds _id after insert
        return pm_doc

    except stripe.StripeError as e:
        logger.error(f"Stripe error in add_payment_method: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Payment method error: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@payments_router.get("/payment-methods")
async def get_payment_methods(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get user's saved payment methods from DB."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _auth(credentials)
    db = get_db()

    methods = await db.payment_methods.find(
        {"user_id": current_user.id}, {"_id": 0}
    ).to_list(100)
    return methods


@payments_router.delete("/payment-methods/{method_id}")
async def delete_payment_method(
    method_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Delete a payment method — BLOCKED if seller has active listings."""
    import stripe
    from services.stripe_customer_service import check_card_deletion_allowed

    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _auth(credentials)
    db = get_db()

    # Sticky Card Guard: block deletion with active listings
    active_count = await check_card_deletion_allowed(db, current_user.id)
    if active_count > 0:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "payment_method_locked",
                "message_en": f"You have {active_count} active listing(s). Your payment method cannot be removed while auctions are live. Please wait for your auctions to end or cancel them first.",
                "message_fr": f"Vous avez {active_count} annonce(s) active(s). Votre moyen de paiement ne peut pas être supprimé pendant que des enchères sont en cours. Veuillez attendre la fin de vos enchères ou les annuler d'abord.",
                "active_listing_count": active_count,
            },
        )

    method = await db.payment_methods.find_one(
        {"id": method_id, "user_id": current_user.id}
    )
    if not method:
        raise HTTPException(status_code=404, detail="Payment method not found")

    try:
        stripe.PaymentMethod.detach(method["stripe_payment_method_id"])
    except Exception:
        pass

    await db.payment_methods.delete_one({"id": method_id})

    # Clear user's default payment method
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {"has_payment_method": False, "updated_at": datetime.now(timezone.utc).isoformat()},
         "$unset": {"default_payment_method_id": ""}},
    )

    return {"message": "Payment method deleted"}


# ========== CHECKOUT ENDPOINTS WITH FULL BREAKDOWN ==========

from services.stripe_connect_service import (
    calculate_general_checkout,
    calculate_vehicle_checkout,
    calculate_partner_listing_checkout,
    create_destination_charge,
    create_vehicle_payment_session,
    STRIPE_PERCENTAGE_FEE,
    STRIPE_FIXED_FEE
)


class AuctionCheckoutRequest(BaseModel):
    """Request model for auction checkout"""
    listing_id: str = Field(..., description="Listing/auction ID")
    return_url: str = Field(..., description="URL to redirect after checkout")


@payments_router.post("/checkout/auction")
async def create_auction_checkout(
    request: AuctionCheckoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create checkout session for auction purchase
    
    This handles both GENERAL and VEHICLE auctions:
    - GENERAL: Destination charge to seller's Stripe Connect account
    - VEHICLE: Direct charge for BidVex fees only (hammer paid offline)
    
    Returns checkout URL and complete breakdown for display.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _auth(credentials)
    
    # Get listing
    listing = await db.listings.find_one({"id": request.listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Verify buyer is the winner
    if listing.get("winning_bidder_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Only the winning bidder can checkout")
    
    # Check if already paid
    if listing.get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="This auction has already been paid")
    
    # Get seller info
    seller = await db.users.find_one({"id": listing["seller_id"]})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # Determine if this is a vehicle auction
    category = listing.get("category", "").lower()
    is_vehicle = any(keyword in category for keyword in ["vehicle", "car", "auto", "truck", "motorcycle"])
    is_partner = listing.get("is_partner_listing", False)
    
    hammer_price = listing.get("current_price", listing.get("starting_price", 0))
    
    if is_partner:
        # Partner listing — 3% platform fee, custom buyer premium, destination charge
        seller_connect_id = seller.get("stripe_connect_account_id")
        if not seller_connect_id:
            raise HTTPException(
                status_code=400, 
                detail="Partner has not completed Stripe Connect onboarding."
            )
        
        custom_bp_rate = listing.get("custom_buyer_premium_rate", 0.0) or 0.0
        partner_is_tax_registered = seller.get("is_tax_registered", False)
        
        breakdown = calculate_partner_listing_checkout(
            hammer_price=hammer_price,
            custom_buyer_premium_rate=custom_bp_rate,
            partner_is_tax_registered=partner_is_tax_registered,
            include_processing_fee=True
        )
        
        result = await create_destination_charge(
            db=db,
            listing_id=request.listing_id,
            buyer_id=current_user.id,
            breakdown=breakdown,
            return_url=request.return_url,
            seller_connect_account_id=seller_connect_id
        )
        
        return {
            "checkout_type": "partner",
            **result
        }
    elif is_vehicle:
        # Vehicle auction - only BidVex fees via Stripe
        breakdown = calculate_vehicle_checkout(
            hammer_price=hammer_price,
            buyer_tier=current_user.subscription_tier if hasattr(current_user, 'subscription_tier') else "basic"
        )
        
        result = await create_vehicle_payment_session(
            db=db,
            auction_id=request.listing_id,
            buyer_id=current_user.id,
            breakdown=breakdown,
            return_url=request.return_url
        )
        
        return {
            "checkout_type": "vehicle",
            **result
        }
    else:
        # General auction - destination charge to seller
        seller_connect_id = seller.get("stripe_connect_account_id")
        
        if not seller_connect_id:
            raise HTTPException(
                status_code=400, 
                detail="Seller has not completed Stripe Connect onboarding. Please contact seller."
            )
        
        breakdown = calculate_general_checkout(
            hammer_price=hammer_price,
            buyer_tier=current_user.subscription_tier if hasattr(current_user, 'subscription_tier') else "basic",
            seller_tier=seller.get("subscription_tier", "basic"),
            seller_is_tax_registered=seller.get("is_tax_registered", False),
            include_processing_fee=True
        )
        
        result = await create_destination_charge(
            db=db,
            listing_id=request.listing_id,
            buyer_id=current_user.id,
            breakdown=breakdown,
            return_url=request.return_url,
            seller_connect_account_id=seller_connect_id
        )
        
        return {
            "checkout_type": "general",
            **result
        }


@payments_router.get("/checkout/preview/{listing_id}")
async def preview_checkout_breakdown(
    listing_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get checkout breakdown preview without creating a session
    
    Use this to display the cost breakdown in the UI before checkout.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _auth(credentials)
    
    # Get listing
    listing = await db.listings.find_one({"id": listing_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Get seller info
    seller = await db.users.find_one({"id": listing["seller_id"]})
    
    category = listing.get("category", "").lower()
    is_vehicle = any(keyword in category for keyword in ["vehicle", "car", "auto", "truck", "motorcycle"])
    is_partner = listing.get("is_partner_listing", False)
    
    hammer_price = listing.get("current_price", listing.get("starting_price", 0))
    
    buyer_tier = "basic"
    if hasattr(current_user, 'subscription_tier'):
        buyer_tier = current_user.subscription_tier
    
    if is_partner:
        # Partner listing — custom buyer premium, 3% platform fee
        custom_bp_rate = listing.get("custom_buyer_premium_rate", 0.0) or 0.0
        partner_is_tax_registered = seller.get("is_tax_registered", False) if seller else False
        
        breakdown = calculate_partner_listing_checkout(
            hammer_price=hammer_price,
            custom_buyer_premium_rate=custom_bp_rate,
            partner_is_tax_registered=partner_is_tax_registered,
            include_processing_fee=True
        )
        
        return {
            "checkout_type": "partner",
            "breakdown": breakdown.to_dict(),
            "is_partner_listing": True,
            "partner_company": seller.get("partner_company_name") if seller else None,
            "seller_is_tax_registered": partner_is_tax_registered,
            "fee_model_label": "Partner Auction",
        }
    elif is_vehicle:
        breakdown = calculate_vehicle_checkout(
            hammer_price=hammer_price,
            buyer_tier=buyer_tier
        )
        
        return {
            "checkout_type": "vehicle",
            "breakdown": breakdown.to_dict(),
            "stripe_charge_description": "BidVex Fees Only",
            "hammer_price_note": "Hammer price ($" + f"{float(breakdown.hammer_price):,.2f}" + ") paid directly to seller via Bank Draft",
            "seller_is_tax_registered": False
        }
    else:
        seller_tier = seller.get("subscription_tier", "basic") if seller else "basic"
        seller_is_tax_registered = seller.get("is_tax_registered", False) if seller else False
        
        breakdown = calculate_general_checkout(
            hammer_price=hammer_price,
            buyer_tier=buyer_tier,
            seller_tier=seller_tier,
            seller_is_tax_registered=seller_is_tax_registered,
            include_processing_fee=True
        )
        
        return {
            "checkout_type": "general",
            "breakdown": breakdown.to_dict(),
            "stripe_charge_description": "Full Payment via Stripe",
            "seller_is_tax_registered": seller_is_tax_registered,
            "tax_on_item_note": "Tax on item (14.975%)" if seller_is_tax_registered else "No tax on item (private seller)"
        }


# ========== INVOICE DOWNLOAD ENDPOINT ==========

from fastapi.responses import FileResponse

@payments_router.get("/invoices/download/{invoice_id}")
async def download_invoice(invoice_id: str):
    """
    Download PDF invoice by ID
    
    Checks for invoice in /tmp/invoices directory
    """
    storage_dir = "/tmp/invoices"
    
    # Try marketplace invoice first
    filepath = os.path.join(storage_dir, f"marketplace_{invoice_id}.pdf")
    if os.path.exists(filepath):
        return FileResponse(
            filepath,
            media_type="application/pdf",
            filename=f"invoice_{invoice_id[:8]}.pdf"
        )
    
    # Try vehicle invoice
    filepath = os.path.join(storage_dir, f"vehicle_{invoice_id}.pdf")
    if os.path.exists(filepath):
        return FileResponse(
            filepath,
            media_type="application/pdf",
            filename=f"invoice_vehicle_{invoice_id[:8]}.pdf"
        )
    
    raise HTTPException(status_code=404, detail="Invoice not found")


# ========== SUBSCRIPTION ENDPOINTS ==========

from services.subscription_service import (
    get_all_tiers,
    get_tier_benefits,
    create_subscription_checkout,
    get_user_subscription_status,
    STRIPE_PRICE_IDS,
    BUYER_PREMIUM_RATES,
    SELLER_COMMISSION_RATES,
)


@payments_router.get("/subscriptions/tiers")
async def get_subscription_tiers():
    """
    Get all available subscription tiers with pricing and benefits
    
    Returns:
        List of tiers: Free, Premium ($180/mo), VIP ($300/mo)
        Fee comparison table
    """
    return get_all_tiers()


@payments_router.get("/subscriptions/my-status")
async def get_my_subscription_status(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current user's subscription status and benefits
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _auth(credentials)
    
    return await get_user_subscription_status(db, current_user.id)


class SubscriptionUpgradeRequest(BaseModel):
    tier: str = Field(..., description="Target tier: 'premium' or 'vip'")
    return_url: str = Field(..., description="URL to redirect after checkout")


@payments_router.post("/subscriptions/upgrade")
async def upgrade_subscription(
    request: SubscriptionUpgradeRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create checkout session for subscription upgrade
    
    Args:
        tier: Target subscription tier ('premium' or 'vip')
        return_url: URL to redirect after checkout
    
    Returns:
        Stripe Checkout URL for subscription payment
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    if request.tier.lower() not in ["premium", "vip"]:
        raise HTTPException(status_code=400, detail="Invalid tier. Must be 'premium' or 'vip'")
    
    db = get_db()
    current_user = await _auth(credentials)
    
    result = await create_subscription_checkout(
        db=db,
        user_id=current_user.id,
        tier=request.tier.lower(),
        return_url=request.return_url
    )
    
    return result


@payments_router.get("/subscriptions/fee-rates")
async def get_fee_rates(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get fee rates for current user's subscription tier
    
    Used by tax calculation endpoints to apply correct rates.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _auth(credentials)
    
    user = await db.users.find_one({"id": current_user.id})
    tier = user.get("subscription_tier", "free") if user else "free"
    
    return {
        "tier": tier,
        "buyer_premium_rate": BUYER_PREMIUM_RATES.get(tier, 0.05),
        "buyer_premium_display": f"{BUYER_PREMIUM_RATES.get(tier, 0.05) * 100:.1f}%",
        "seller_commission_rate": SELLER_COMMISSION_RATES.get(tier, 0.04),
        "seller_commission_display": f"{SELLER_COMMISSION_RATES.get(tier, 0.04) * 100:.1f}%",
        "all_rates": {
            "free": {"buyer": "5.0%", "seller": "4.0%"},
            "premium": {"buyer": "3.5%", "seller": "2.5%"},
            "vip": {"buyer": "3.0%", "seller": "2.0%"}
        }
    }


# ========== SELLER EARNINGS DASHBOARD ==========

@payments_router.get("/seller/earnings")
async def get_seller_earnings(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get seller earnings dashboard data
    
    Returns:
        - Total earned
        - Pending payouts
        - Available balance
        - Recent transactions
    """
    import stripe
    
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _auth(credentials)
    
    user = await db.users.find_one({"id": current_user.id})
    connect_account_id = user.get("stripe_connect_account_id") if user else None
    
    if not connect_account_id:
        return {
            "has_connect_account": False,
            "message": "Please complete seller onboarding to view earnings",
            "onboarding_required": True
        }
    
    try:
        # Get Stripe Connect account balance
        balance = stripe.Balance.retrieve(stripe_account=connect_account_id)
        
        # Get available balance
        available = sum(
            b.get("amount", 0) 
            for b in balance.get("available", []) 
            if b.get("currency") == "cad"
        )
        
        # Get pending balance
        pending = sum(
            b.get("amount", 0) 
            for b in balance.get("pending", []) 
            if b.get("currency") == "cad"
        )
        
        # Get recent payouts
        payouts = stripe.Payout.list(
            limit=10,
            stripe_account=connect_account_id
        )
        
        recent_payouts = [
            {
                "id": p.id,
                "amount": p.amount / 100,
                "currency": p.currency.upper(),
                "status": p.status,
                "arrival_date": datetime.fromtimestamp(p.arrival_date, tz=timezone.utc).isoformat() if p.arrival_date else None,
                "created": datetime.fromtimestamp(p.created, tz=timezone.utc).isoformat()
            }
            for p in payouts.data
        ]
        
        # Get total earned from database
        total_earned_cursor = db.invoices.aggregate([
            {"$match": {"seller_id": current_user.id, "type": "marketplace_purchase"}},
            {"$group": {"_id": None, "total": {"$sum": "$breakdown.seller_payout"}}}
        ])
        total_earned_result = await total_earned_cursor.to_list(length=1)
        total_earned = total_earned_result[0]["total"] if total_earned_result else 0
        
        # Get account status
        account = stripe.Account.retrieve(connect_account_id)
        
        return {
            "has_connect_account": True,
            "account_id": connect_account_id,
            "payouts_enabled": account.payouts_enabled,
            "charges_enabled": account.charges_enabled,
            "financial_metrics": {
                "total_earned": total_earned,
                "total_earned_display": f"${total_earned:,.2f}",
                "pending_payouts": pending / 100,
                "pending_payouts_display": f"${pending / 100:,.2f}",
                "available_balance": available / 100,
                "available_balance_display": f"${available / 100:,.2f}",
                "currency": "CAD"
            },
            "recent_payouts": recent_payouts,
            "requirements": {
                "currently_due": list(account.requirements.currently_due) if account.requirements else [],
                "past_due": list(account.requirements.past_due) if account.requirements else []
            }
        }
        
    except stripe.StripeError as e:
        logger.error(f"Stripe error getting seller earnings: {e}")
        return {
            "has_connect_account": True,
            "error": "Unable to retrieve earnings data",
            "message": str(e)
        }


@payments_router.get("/seller/transactions")
async def get_seller_transactions(
    limit: int = 20,
    offset: int = 0,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get seller's transaction history
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    db = get_db()
    current_user = await _auth(credentials)
    
    # Get invoices where user is seller
    invoices_cursor = db.invoices.find(
        {"seller_id": current_user.id}
    ).sort("created_at", -1).skip(offset).limit(limit)
    
    invoices = await invoices_cursor.to_list(length=limit)
    
    transactions = []
    for inv in invoices:
        breakdown = inv.get("breakdown", {})
        transactions.append({
            "id": inv.get("id"),
            "type": inv.get("type", "sale"),
            "listing_id": inv.get("listing_id"),
            "auction_id": inv.get("auction_id"),
            "hammer_price": breakdown.get("hammer_price", 0),
            "seller_commission": breakdown.get("seller_commission", 0),
            "seller_payout": breakdown.get("seller_payout", 0),
            "created_at": inv.get("created_at"),
            "pdf_url": inv.get("pdf_url")
        })
    
    # Get total count
    total_count = await db.invoices.count_documents({"seller_id": current_user.id})
    
    return {
        "transactions": transactions,
        "total_count": total_count,
        "limit": limit,
        "offset": offset
    }



# ========== BUY NOW CHECKOUT FLOW ==========

def BUYER_PREMIUM_RATES_FOR_DISPLAY(tier: str, is_partner_seller: bool = False) -> float:
    """Mirror of PricingManager.BUYER_PREMIUM_RATES exposed as float for API responses."""
    if is_partner_seller:
        return 0.05  # Standard BP still applies when seller is a partner
    return {"free": 0.05, "basic": 0.05, "standard": 0.05,
            "premium": 0.035,
            "vip": 0.03, "vip_elite": 0.03,
            "partner": 0.0}.get((tier or "free").lower(), 0.05)


class BuyNowPreviewRequest(BaseModel):
    auction_id: str
    lot_number: int
    quantity: int = 1


class BuyNowCheckoutRequest(BaseModel):
    auction_id: str
    lot_number: int
    quantity: int = 1
    return_url: str


@payments_router.post("/buy-now-preview")
async def buy_now_preview(
    data: BuyNowPreviewRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Server-side price breakdown for Buy Now purchase.
    No side effects — for display only before user confirms.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _auth(credentials)
    db = get_db()

    auction = await db.multi_item_listings.find_one({"id": data.auction_id}, {"_id": 0})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    if auction.get("status") != "active":
        raise HTTPException(status_code=400, detail="Auction is not active")

    target_lot = None
    for lot in auction.get("lots", []):
        if lot["lot_number"] == data.lot_number:
            target_lot = lot
            break

    if not target_lot:
        raise HTTPException(status_code=404, detail="Lot not found")
    if not target_lot.get("buy_now_enabled"):
        raise HTTPException(status_code=400, detail="Buy Now not available for this lot")

    buy_now_price = target_lot.get("buy_now_price")
    if not buy_now_price:
        raise HTTPException(status_code=400, detail="Buy Now price not set")

    available_qty = target_lot.get("available_quantity", target_lot.get("quantity", 1))
    if data.quantity > available_qty:
        raise HTTPException(status_code=400, detail=f"Only {available_qty} units available")

    item_total = buy_now_price * data.quantity

    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    buyer_tier = user_doc.get("subscription_tier", "free") if user_doc else "free"
    buyer_province = (user_doc.get("province", "QC") if user_doc else "QC") or "QC"

    seller = await db.users.find_one({"id": auction["seller_id"]}, {"_id": 0})
    seller_is_business = seller.get("is_tax_registered", False) if seller else False
    seller_tier = seller.get("subscription_tier", "free") if seller else "free"
    seller_is_partner = bool(seller.get("is_partner") and seller.get("platform_fee_paid")) if seller else False

    # Canonical pricing — same engine winning-bid checkout uses.
    from services.pricing_manager import PricingManager
    if seller_is_partner:
        pr = PricingManager.partner_auction(item_total, buyer_province)
    else:
        pr = PricingManager.non_vehicle_stripe(item_total, buyer_province, buyer_tier, seller_tier)

    bi = pr.buyer_invoice
    return {
        "lot_title": target_lot.get("title", "Item"),
        "price_per_unit": buy_now_price,
        "quantity": data.quantity,
        "item_total": item_total,
        "buyer_premium_rate": BUYER_PREMIUM_RATES_FOR_DISPLAY(buyer_tier, seller_is_partner),
        "buyer_premium": bi.fees_subtotal,
        "gst": bi.tax_amount if bi.tax_type == "GST" else 0.0,
        "qst": 0.0,  # Combined GST+QST shown in total_tax for QC
        "total_tax": bi.tax_amount,
        "tax_label": bi.tax_label,
        "processing_fee": bi.stripe_recovery,
        "buyer_total": bi.total,
        "seller_is_business": seller_is_business,
        "seller_is_partner": seller_is_partner,
        "available_quantity": available_qty,
        "breakdown": pr.to_dict(),
    }


@payments_router.post("/buy-now-checkout")
async def buy_now_checkout(
    data: BuyNowCheckoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Process Buy Now purchase: validate, decrement inventory, create Stripe session.
    All prices recalculated server-side from MongoDB.
    """
    import stripe as stripe_mod

    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _auth(credentials)
    db = get_db()

    # Check if buy-now is enabled
    settings_doc = await db.marketplace_settings.find_one({}, {"_id": 0})
    if settings_doc and not settings_doc.get("enable_buy_now", True):
        raise HTTPException(status_code=403, detail="Buy Now is currently disabled")

    # Fetch auction from DB (server-side truth)
    auction = await db.multi_item_listings.find_one({"id": data.auction_id}, {"_id": 0})
    if not auction:
        raise HTTPException(status_code=404, detail="Auction not found")
    if auction["status"] != "active":
        raise HTTPException(status_code=400, detail="Auction is not active")

    if auction.get("seller_id") == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot buy your own listing")

    # Find lot
    lot_index = None
    target_lot = None
    for idx, lot in enumerate(auction.get("lots", [])):
        if lot["lot_number"] == data.lot_number:
            lot_index = idx
            target_lot = lot
            break

    if target_lot is None:
        raise HTTPException(status_code=404, detail="Lot not found")
    if not target_lot.get("buy_now_enabled", False):
        raise HTTPException(status_code=400, detail="Buy Now not available for this lot")

    # Server-side price (NEVER trust frontend)
    buy_now_price = target_lot["buy_now_price"]
    if not buy_now_price:
        raise HTTPException(status_code=400, detail="Buy Now price not set")

    available_qty = target_lot.get("available_quantity", target_lot.get("quantity", 1))
    if available_qty <= 0:
        raise HTTPException(status_code=400, detail="Sold out")
    if data.quantity > available_qty:
        raise HTTPException(status_code=400, detail=f"Only {available_qty} units available")

    item_total = buy_now_price * data.quantity

    # Calculate fees server-side via canonical PricingManager
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    buyer_tier = user_doc.get("subscription_tier", "free") if user_doc else "free"
    buyer_province = (user_doc.get("province", "QC") if user_doc else "QC") or "QC"

    seller = await db.users.find_one({"id": auction["seller_id"]}, {"_id": 0})
    seller_tier = seller.get("subscription_tier", "free") if seller else "free"
    seller_is_partner = bool(seller.get("is_partner") and seller.get("platform_fee_paid")) if seller else False

    from services.pricing_manager import PricingManager
    if seller_is_partner:
        pr = PricingManager.partner_auction(item_total, buyer_province)
    else:
        pr = PricingManager.non_vehicle_stripe(item_total, buyer_province, buyer_tier, seller_tier)
    bi = pr.buyer_invoice
    buyer_total_cents = int(round(bi.total * 100))
    # Application fee = all BidVex revenue (BP + SC + taxes on fees) → BidVex account
    # Stripe recovery is a pass-through from buyer to Stripe, not BidVex revenue
    app_fee_dollars = pr.bidvex_revenue + bi.tax_amount
    stripe_application_fee_cents = int(round(app_fee_dollars * 100))

    # Decrement inventory
    new_available_qty = available_qty - data.quantity
    new_sold_qty = target_lot.get("sold_quantity", 0) + data.quantity
    if new_available_qty == 0:
        new_lot_status = "sold_out"
    elif new_sold_qty > 0:
        new_lot_status = "partially_sold"
    else:
        new_lot_status = target_lot.get("lot_status", "active")

    inv_result = await db.multi_item_listings.update_one(
        {"id": data.auction_id},
        {"$set": {
            f"lots.{lot_index}.available_quantity": new_available_qty,
            f"lots.{lot_index}.sold_quantity": new_sold_qty,
            f"lots.{lot_index}.lot_status": new_lot_status,
        }}
    )
    if inv_result.modified_count == 0:
        raise HTTPException(status_code=500, detail="Failed to update inventory")

    # Create transaction record
    transaction_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    transaction = {
        "id": transaction_id,
        "auction_id": data.auction_id,
        "lot_number": data.lot_number,
        "buyer_id": current_user.id,
        "quantity_purchased": data.quantity,
        "price_per_unit": buy_now_price,
        "total_amount": item_total,
        "buyer_total": bi.total,
        "buyer_premium": bi.fees_subtotal,
        "buyer_premium_rate": BUYER_PREMIUM_RATES_FOR_DISPLAY(buyer_tier, seller_is_partner),
        "seller_commission": pr.seller_invoice.fees_subtotal if pr.seller_invoice else 0.0,
        "total_tax": bi.tax_amount,
        "tax_label": bi.tax_label,
        "buyer_province": buyer_province,
        "payment_status": "pending",
        "transaction_date": now.isoformat(),
    }
    await db.buy_now_transactions.insert_one(transaction)

    # Create Stripe checkout session
    customer_id = user_doc.get("stripe_customer_id") if user_doc else None
    if not customer_id:
        customer = stripe_mod.Customer.create(
            email=current_user.email,
            name=getattr(current_user, "name", current_user.email),
            metadata={"user_id": current_user.id},
        )
        customer_id = customer.id
        await db.users.update_one(
            {"id": current_user.id},
            {"$set": {"stripe_customer_id": customer_id}},
        )

    lot_title = target_lot.get("title", "Item")
    bp_pct = BUYER_PREMIUM_RATES_FOR_DISPLAY(buyer_tier, seller_is_partner) * 100
    description = (
        f"{lot_title} x{data.quantity} | "
        f"Buyer Premium ({bp_pct:.1f}%): ${bi.fees_subtotal:,.2f} | "
        f"Tax: ${bi.tax_amount:,.2f}"
    )

    seller_connect_id = seller.get("stripe_connect_account_id") if seller else None

    auction_currency = auction.get("currency", "CAD").lower()

    session_params = {
        "customer": customer_id,
        "payment_method_types": ["card"],
        "mode": "payment",
        "line_items": [{
            "price_data": {
                "currency": auction_currency,
                "unit_amount": buyer_total_cents,
                "product_data": {
                    "name": f"Buy Now - {lot_title}",
                    "description": description,
                },
            },
            "quantity": 1,
        }],
        "success_url": f"{data.return_url}?status=success&session_id={{CHECKOUT_SESSION_ID}}&txn={transaction_id}",
        "cancel_url": f"{data.return_url}?status=cancelled",
        "metadata": {
            "type": "buy_now",
            "transaction_id": transaction_id,
            "auction_id": data.auction_id,
            "lot_number": str(data.lot_number),
            "buyer_id": current_user.id,
            "is_vehicle": "false",
        },
    }

    if seller_connect_id:
        session_params["payment_intent_data"] = {
            "application_fee_amount": stripe_application_fee_cents,
            "transfer_data": {"destination": seller_connect_id},
        }

    session = stripe_mod.checkout.Session.create(**session_params)

    # Link session to transaction
    await db.buy_now_transactions.update_one(
        {"id": transaction_id},
        {"$set": {"stripe_session_id": session.id}},
    )

    return {
        "success": True,
        "checkout_url": session.url,
        "session_id": session.id,
        "transaction_id": transaction_id,
        "breakdown": pr.to_dict(),
    }


# ========== AUCTION WINNER CHECKOUT FLOW ==========

@payments_router.get("/auction-winner-preview/{listing_id}")
async def auction_winner_preview(
    listing_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Preview checkout breakdown for auction winner using Connect engine.
    Shows tier-based fees + separate GST/QST amounts.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _auth(credentials)
    db = get_db()

    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.get("winner_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Only the auction winner can view this checkout")

    if listing.get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="This auction has already been paid")

    from services.connect_payment_engine import calculate_connect_checkout

    hammer_price = listing.get("final_price", listing.get("current_price", 0))

    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    buyer_tier = user_doc.get("subscription_tier", "free") if user_doc else "free"

    seller = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0})
    seller_tier = seller.get("subscription_tier", "free") if seller else "free"
    seller_is_business = seller.get("is_tax_registered", False) if seller else False
    seller_is_partner = bool(seller.get("is_partner") and seller.get("platform_fee_paid")) if seller else False

    category = listing.get("category", "general")
    currency = listing.get("currency", "CAD")

    breakdown = calculate_connect_checkout(
        hammer_price=hammer_price,
        category=category,
        buyer_tier=buyer_tier,
        seller_tier=seller_tier,
        currency=currency,
        province=listing.get("region", "QC"),
        include_stripe_fee=True,
        seller_is_partner=seller_is_partner,
    )

    # Late penalty calculation
    late_penalty = 0.0
    payment_deadline = listing.get("payment_deadline")
    if payment_deadline:
        deadline_dt = datetime.fromisoformat(payment_deadline)
        now = datetime.now(timezone.utc)
        if now > deadline_dt:
            days_late = (now - deadline_dt).days
            months_late = max(1, (days_late + 29) // 30)
            penalty_rate = 0.02 * months_late
            late_penalty = round(hammer_price * penalty_rate, 2)

    total_with_penalty = breakdown["buyer_total"] + late_penalty

    return {
        "listing_id": listing_id,
        "title": listing.get("title", ""),
        "hammer_price": hammer_price,
        "currency": currency,
        "checkout_type": "vehicle" if breakdown.get("is_vehicle") else "general",
        "flow_type": breakdown["flow_type"],
        "seller_is_partner": seller_is_partner,
        "buyer_tier": buyer_tier,
        "seller_tier": seller_tier,
        "buyer_premium_rate": breakdown["buyer_premium_rate"],
        "buyer_premium": breakdown["buyer_premium"],
        "seller_commission_rate": breakdown["seller_commission_rate"],
        "seller_commission": breakdown["seller_commission"],
        "platform_fee": breakdown["platform_fee"],
        "partner_premium_retained": breakdown.get("partner_premium_retained", 0),
        "gst": breakdown["gst"],
        "qst": breakdown["qst"],
        "total_tax": breakdown["total_tax"],
        "stripe_processing_fee": breakdown["stripe_processing_fee"],
        "buyer_total_before_penalty": breakdown["buyer_total"],
        "late_penalty": late_penalty,
        "buyer_total": total_with_penalty,
        "seller_payout": breakdown["seller_payout"],
        "payment_deadline": payment_deadline,
        "is_overdue": late_penalty > 0,
        "seller_is_business": seller_is_business,
        "is_partner_listing": seller_is_partner,
        "breakdown": breakdown,
        "images": listing.get("images", []),
        "category": listing.get("category", ""),
    }


@payments_router.post("/auction-winner-checkout/{listing_id}")
async def auction_winner_checkout(
    listing_id: str,
    data: Dict[str, str],
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Create Stripe checkout session for auction winner using Connect engine.
    - Dynamic tier-based buyer premium / seller commission
    - Stripe fee pass-through to buyer
    - GST/QST as separate Stripe line items (Quebec compliance)
    - Idempotency key prevents double charges
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _auth(credentials)
    db = get_db()

    # Server-side validation
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.get("winner_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Only the auction winner can checkout")

    if listing.get("status") not in ("ended", "won", "pending_payment"):
        raise HTTPException(status_code=400, detail="Listing is not in a valid state for checkout")

    if listing.get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="Already paid")

    # Server-side price calculation via Connect engine
    from services.connect_payment_engine import calculate_connect_checkout, create_connect_checkout_session

    hammer_price = listing.get("final_price", listing.get("current_price", 0))

    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    buyer_tier = user_doc.get("subscription_tier", "free") if user_doc else "free"

    seller = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0})
    seller_tier = seller.get("subscription_tier", "free") if seller else "free"
    seller_is_partner = bool(seller.get("is_partner") and seller.get("platform_fee_paid")) if seller else False

    category = listing.get("category", "general")
    currency = listing.get("currency", "CAD")

    breakdown = calculate_connect_checkout(
        hammer_price=hammer_price,
        category=category,
        buyer_tier=buyer_tier,
        seller_tier=seller_tier,
        currency=currency,
        province=listing.get("region", "QC"),
        include_stripe_fee=True,
        seller_is_partner=seller_is_partner,
    )

    # Late penalty
    late_penalty = 0.0
    payment_deadline = listing.get("payment_deadline")
    if payment_deadline:
        deadline_dt = datetime.fromisoformat(payment_deadline)
        now = datetime.now(timezone.utc)
        if now > deadline_dt:
            days_late = (now - deadline_dt).days
            months_late = max(1, (days_late + 29) // 30)
            penalty_rate = 0.02 * months_late
            late_penalty = round(hammer_price * penalty_rate, 2)

    return_url = data.get("return_url", f"https://bidvex.com/checkout/{listing_id}")
    idempotency_key = f"auction_{listing_id}_{current_user.id}"

    result = await create_connect_checkout_session(
        db=db,
        buyer_id=current_user.id,
        listing=listing,
        breakdown=breakdown,
        success_url=f"{return_url}?status=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{return_url}?status=cancelled",
        payment_type="auction_winner",
        metadata_extra={"listing_id": listing_id},
        late_penalty=late_penalty,
        idempotency_key=idempotency_key,
    )

    # Store pending payment with full Connect breakdown
    await db.pending_payments.update_one(
        {"listing_id": listing_id, "buyer_id": current_user.id, "type": "auction_winner"},
        {"$set": {
            "id": str(uuid.uuid4()),
            "session_id": result["session_id"],
            "listing_id": listing_id,
            "buyer_id": current_user.id,
            "seller_id": listing.get("seller_id", ""),
            "type": "auction_winner",
            "breakdown": breakdown,
            "late_penalty": late_penalty,
            "total_cents": result["total_cents"],
            "status": "pending",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }},
        upsert=True
    )

    # Update listing payment status
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {"payment_status": "checkout_initiated"}},
    )

    return {
        "checkout_url": result["checkout_url"],
        "session_id": result["session_id"],
        "total_cents": result["total_cents"],
        "late_penalty": late_penalty,
        "breakdown": breakdown,
    }



# ── Offline Checkout (Cash / E-Transfer) ─────────────────────────
class OfflineCheckoutRequest(BaseModel):
    payment_method: str  # "cash" or "etransfer"
    return_url: str = ""


@payments_router.post("/offline-checkout/{listing_id}")
async def offline_checkout(
    listing_id: str,
    data: OfflineCheckoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Process an offline (cash or e-transfer) checkout for an auction winner.
    Skips Stripe — marks items reserved, sets pending_payment status,
    and sends bilingual confirmation email with payment instructions.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _auth(credentials)
    db = get_db()

    if data.payment_method not in ("cash", "etransfer"):
        raise HTTPException(status_code=400, detail="Invalid payment method. Must be 'cash' or 'etransfer'.")

    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    if listing.get("winner_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Only the auction winner can checkout")

    if listing.get("status") not in ("ended", "won", "pending_payment"):
        raise HTTPException(status_code=400, detail="Listing is not in a valid state for checkout")

    if listing.get("payment_status") == "paid":
        raise HTTPException(status_code=400, detail="Already paid")

    # Calculate breakdown (same engine, no Stripe fee)
    from services.connect_payment_engine import calculate_connect_checkout

    hammer_price = listing.get("final_price", listing.get("current_price", 0))
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    buyer_tier = user_doc.get("subscription_tier", "free") if user_doc else "free"

    seller = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0})
    seller_tier = seller.get("subscription_tier", "free") if seller else "free"
    seller_is_partner = bool(seller.get("is_partner") and seller.get("platform_fee_paid")) if seller else False

    breakdown = calculate_connect_checkout(
        hammer_price=hammer_price,
        category=listing.get("category", "general"),
        buyer_tier=buyer_tier,
        seller_tier=seller_tier,
        currency=listing.get("currency", "CAD"),
        province=listing.get("region", "QC"),
        include_stripe_fee=False,
        seller_is_partner=seller_is_partner,
    )

    order_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()

    # Fetch interac email from site_settings for e-transfer instructions
    interac_email = ""
    if data.payment_method == "etransfer":
        site_settings = await db.site_settings.find_one({}, {"_id": 0})
        interac_email = (site_settings or {}).get("interac_email", "payments@bidvex.com")

    # Create offline order record
    order_record = {
        "id": order_id,
        "listing_id": listing_id,
        "buyer_id": current_user.id,
        "seller_id": listing.get("seller_id", ""),
        "type": "auction_winner",
        "payment_method": data.payment_method,
        "order_status": "pending_payment",
        "payment_status": "waiting_for_offline_confirmation",
        "hammer_price": hammer_price,
        "buyer_premium": breakdown.get("buyer_premium", 0),
        "platform_fee": breakdown.get("platform_fee", 0),
        "gst": breakdown.get("gst", 0),
        "qst": breakdown.get("qst", 0),
        "buyer_total": breakdown.get("buyer_total", hammer_price),
        "breakdown": breakdown,
        "interac_email": interac_email if data.payment_method == "etransfer" else None,
        "created_at": now_iso,
        "updated_at": now_iso,
    }

    await db.offline_orders.insert_one({**order_record, "_id": None})
    # Remove the _id that MongoDB adds
    await db.offline_orders.update_one({"id": order_id}, {"$unset": {"_id": ""}})

    # Mark listing as reserved to prevent double-selling
    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {
            "status": "reserved",
            "payment_status": "waiting_for_offline_confirmation",
            "payment_method": data.payment_method,
            "offline_order_id": order_id,
            "reserved_at": now_iso,
            "updated_at": now_iso,
        }}
    )

    # Send bilingual confirmation email
    try:
        from services.email_service import get_email_service
        email_svc = get_email_service()
        if email_svc.is_configured() and user_doc:
            lang = user_doc.get("preferred_language", "en")
            is_fr = lang == "fr"
            item_title = listing.get("title", "Auction Item")

            if data.payment_method == "etransfer":
                subject = f"Instructions de paiement - Virement Interac #{order_id[:8]}" if is_fr else f"Payment Instructions - Interac E-Transfer #{order_id[:8]}"
                html = f"""
                <html><body style="font-family:Arial,sans-serif;padding:20px;max-width:600px;margin:auto">
                <div style="background:#1e40af;padding:20px;border-radius:12px 12px 0 0;text-align:center">
                    <h1 style="color:white;margin:0;font-size:22px">{'Confirmation de commande' if is_fr else 'Order Confirmation'}</h1>
                </div>
                <div style="border:1px solid #e2e8f0;border-top:none;padding:24px;border-radius:0 0 12px 12px">
                    <p>{'Bonjour' if is_fr else 'Hello'} {user_doc.get('name','').split()[0]},</p>
                    <p>{'Votre commande a été confirmée. Veuillez compléter le paiement par virement Interac.' if is_fr else 'Your order has been confirmed. Please complete payment via Interac E-Transfer.'}</p>
                    <div style="background:#eff6ff;border:1px solid #bfdbfe;border-radius:8px;padding:16px;margin:16px 0">
                        <h3 style="margin:0 0 8px 0;color:#1e40af">{'Instructions de virement Interac' if is_fr else 'Interac E-Transfer Instructions'}</h3>
                        <table style="width:100%;border-collapse:collapse">
                            <tr><td style="padding:6px 0;color:#64748b">{'Envoyer à' if is_fr else 'Send to'}:</td><td style="padding:6px 0;font-weight:bold">{interac_email}</td></tr>
                            <tr><td style="padding:6px 0;color:#64748b">{'Montant' if is_fr else 'Amount'}:</td><td style="padding:6px 0;font-weight:bold">${breakdown.get('buyer_total', hammer_price):,.2f} CAD</td></tr>
                            <tr><td style="padding:6px 0;color:#64748b">{'Référence' if is_fr else 'Reference'}:</td><td style="padding:6px 0;font-weight:bold">{order_id[:8].upper()}</td></tr>
                            <tr><td style="padding:6px 0;color:#64748b">{'Article' if is_fr else 'Item'}:</td><td style="padding:6px 0">{item_title}</td></tr>
                        </table>
                    </div>
                    <p style="color:#64748b;font-size:13px">{'Veuillez inclure le numéro de référence dans le message du virement. Le paiement sera confirmé dans les 24 heures.' if is_fr else 'Please include the reference number in the transfer message. Payment will be confirmed within 24 hours.'}</p>
                    <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0">
                    <p style="color:#94a3b8;font-size:12px;text-align:center">BidVex Inc. — {'Toutes taxes incluses' if is_fr else 'All taxes included'}</p>
                </div></body></html>
                """
            else:
                subject = f"Instructions de paiement - Comptant #{order_id[:8]}" if is_fr else f"Payment Instructions - Cash #{order_id[:8]}"
                html = f"""
                <html><body style="font-family:Arial,sans-serif;padding:20px;max-width:600px;margin:auto">
                <div style="background:#1e40af;padding:20px;border-radius:12px 12px 0 0;text-align:center">
                    <h1 style="color:white;margin:0;font-size:22px">{'Confirmation de commande' if is_fr else 'Order Confirmation'}</h1>
                </div>
                <div style="border:1px solid #e2e8f0;border-top:none;padding:24px;border-radius:0 0 12px 12px">
                    <p>{'Bonjour' if is_fr else 'Hello'} {user_doc.get('name','').split()[0]},</p>
                    <p>{'Votre commande a été confirmée avec paiement en comptant.' if is_fr else 'Your order has been confirmed with cash payment.'}</p>
                    <div style="background:#f0fdf4;border:1px solid #bbf7d0;border-radius:8px;padding:16px;margin:16px 0">
                        <h3 style="margin:0 0 8px 0;color:#166534">{'Instructions de paiement comptant' if is_fr else 'Cash Payment Instructions'}</h3>
                        <table style="width:100%;border-collapse:collapse">
                            <tr><td style="padding:6px 0;color:#64748b">{'Montant dû' if is_fr else 'Amount Due'}:</td><td style="padding:6px 0;font-weight:bold">${breakdown.get('buyer_total', hammer_price):,.2f} CAD</td></tr>
                            <tr><td style="padding:6px 0;color:#64748b">{'Référence' if is_fr else 'Reference'}:</td><td style="padding:6px 0;font-weight:bold">{order_id[:8].upper()}</td></tr>
                            <tr><td style="padding:6px 0;color:#64748b">{'Article' if is_fr else 'Item'}:</td><td style="padding:6px 0">{item_title}</td></tr>
                        </table>
                        <p style="margin:12px 0 0 0;color:#166534;font-weight:500">{'Veuillez contacter le vendeur pour organiser la cueillette et le paiement.' if is_fr else 'Please contact the seller to arrange local pickup and payment.'}</p>
                    </div>
                    <hr style="border:none;border-top:1px solid #e2e8f0;margin:20px 0">
                    <p style="color:#94a3b8;font-size:12px;text-align:center">BidVex Inc. — {'Toutes taxes incluses' if is_fr else 'All taxes included'}</p>
                </div></body></html>
                """
            await email_svc.send_raw_html(user_doc["email"], subject, html)
    except Exception as e:
        logger.error(f"Failed to send offline checkout email: {e}")

    return {
        "success": True,
        "order_id": order_id,
        "payment_method": data.payment_method,
        "order_status": "pending_payment",
        "payment_status": "waiting_for_offline_confirmation",
        "interac_email": interac_email if data.payment_method == "etransfer" else None,
        "breakdown": breakdown,
        "message": "Order confirmed. Follow payment instructions sent to your email." if data.payment_method == "etransfer"
                   else "Order confirmed. Please arrange pickup and cash payment with the seller.",
    }


@payments_router.get("/offline-order/{order_id}")
async def get_offline_order(
    order_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """Get offline order details."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    current_user = await _auth(credentials)
    db = get_db()
    order = await db.offline_orders.find_one({"id": order_id}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    if order.get("buyer_id") != current_user.id and order.get("seller_id") != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized")
    return order



# ========== VEHICLE BUY NOW FLOW (Non-custodial — P0 audit) ==========

class VehicleBuyNowRequest(BaseModel):
    listing_id: str


@payments_router.post("/vehicle-buy-now-preview")
async def vehicle_buy_now_preview(
    data: VehicleBuyNowRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Preview the 2.5% platform fee breakdown for Vehicle Buy Now."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    current_user = await _auth(credentials)
    db = get_db()

    listing = await db.vehicle_listings.find_one({"id": data.listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle listing not found")
    if listing.get("status") != "active":
        raise HTTPException(status_code=400, detail="Vehicle listing is not active")
    if not listing.get("buy_now_price") or not listing.get("buy_now_enabled", True):
        raise HTTPException(status_code=400, detail="Buy Now not available on this vehicle")
    if listing.get("seller_id") == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot buy your own listing")

    buy_now_price = float(listing["buy_now_price"])

    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    buyer_province = (user_doc.get("province", "QC") if user_doc else "QC") or "QC"

    from services.pricing_manager import PricingManager
    pr = PricingManager.vehicle_auction(buy_now_price, buyer_province)
    bi = pr.buyer_invoice

    # Check existing deposit hold
    deposit = await db.vehicle_bid_deposits.find_one(
        {"buyer_id": current_user.id, "listing_id": data.listing_id,
         "status": {"$in": ["paid", "authorized"]}},
        {"_id": 0},
    )
    deposit_amount = float(deposit.get("amount", 500.0)) if deposit else 0.0
    will_capture_from_deposit = min(deposit_amount, bi.total) if deposit else 0.0
    will_charge_card = max(0.0, bi.total - deposit_amount)

    return {
        "listing_id": data.listing_id,
        "vehicle_title": listing.get("title", ""),
        "buy_now_price": buy_now_price,
        "platform_fee_rate": 0.025,
        "platform_fee": bi.fees_subtotal,
        "stripe_recovery": bi.stripe_recovery,
        "tax_amount": bi.tax_amount,
        "tax_label": bi.tax_label,
        "buyer_province": buyer_province,
        "total_platform_fee": bi.total,
        "has_deposit": bool(deposit),
        "deposit_amount": deposit_amount,
        "will_capture_from_deposit": will_capture_from_deposit,
        "will_charge_card_additional": will_charge_card,
        "hammer_paid_directly_to_seller": buy_now_price,
        "breakdown": pr.to_dict(),
    }


@payments_router.post("/vehicle-buy-now-checkout")
async def vehicle_buy_now_checkout(
    data: VehicleBuyNowRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Execute Vehicle Buy Now.
    BidVex NEVER collects the hammer — only the 2.5% platform fee + stripe recovery + tax.

    Deposit handling:
      • fee ≤ $500  → partial capture of deposit (exact fee amount), remainder auto-released
      • fee > $500  → capture full deposit + separate PaymentIntent for remainder
      • no deposit → full fee charged to card on file
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    current_user = await _auth(credentials)
    db = get_db()

    # Validate listing
    listing = await db.vehicle_listings.find_one({"id": data.listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle listing not found")
    if listing.get("status") != "active":
        raise HTTPException(status_code=400, detail="Vehicle listing is not active")
    if not listing.get("buy_now_price") or not listing.get("buy_now_enabled", True):
        raise HTTPException(status_code=400, detail="Buy Now not available on this vehicle")
    if listing.get("seller_id") == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot buy your own listing")

    buy_now_price = float(listing["buy_now_price"])

    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=401, detail="User not found")
    buyer_province = (user_doc.get("province", "QC") or "QC").upper()

    # Canonical pricing
    from services.pricing_manager import PricingManager
    pr = PricingManager.vehicle_auction(buy_now_price, buyer_province)
    bi = pr.buyer_invoice
    platform_fee_total = round(bi.total, 2)
    platform_fee_cents = int(round(platform_fee_total * 100))

    # Ensure Stripe customer
    customer_id = user_doc.get("stripe_customer_id")
    if not customer_id:
        cust = stripe.Customer.create(
            email=user_doc.get("email", current_user.email),
            name=user_doc.get("name", current_user.email),
            metadata={"user_id": current_user.id},
        )
        customer_id = cust.id
        await db.users.update_one({"id": current_user.id}, {"$set": {"stripe_customer_id": customer_id}})

    # Look up active deposit hold
    deposit = await db.vehicle_bid_deposits.find_one(
        {"buyer_id": current_user.id, "listing_id": data.listing_id,
         "status": {"$in": ["paid", "authorized"]}},
        {"_id": 0},
    )

    transaction_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)

    deposit_captured_amount = 0.0
    card_charged_amount = 0.0
    stripe_actions = []

    try:
        if deposit:
            deposit_amount = float(deposit.get("amount", 500.0))
            deposit_cents = int(round(deposit_amount * 100))
            pi_id = deposit.get("stripe_payment_intent_id")
            if not pi_id:
                raise HTTPException(status_code=500, detail="Deposit missing PaymentIntent")

            if platform_fee_cents <= deposit_cents:
                # Partial capture — exact fee, remainder auto-released
                stripe.PaymentIntent.capture(pi_id, amount_to_capture=platform_fee_cents)
                deposit_captured_amount = platform_fee_total
                stripe_actions.append({"action": "deposit_partial_capture", "pi": pi_id, "amount": platform_fee_total})
                await db.vehicle_bid_deposits.update_one(
                    {"id": deposit["id"]},
                    {"$set": {
                        "status": "partially_captured",
                        "captured_amount": platform_fee_total,
                        "released_amount": round(deposit_amount - platform_fee_total, 2),
                        "captured_at": now,
                        "capture_reason": "vehicle_buy_now_platform_fee",
                    }},
                )
            else:
                # Capture full deposit + charge remainder to card
                stripe.PaymentIntent.capture(pi_id)
                deposit_captured_amount = deposit_amount
                stripe_actions.append({"action": "deposit_full_capture", "pi": pi_id, "amount": deposit_amount})

                remainder_cents = platform_fee_cents - deposit_cents
                remainder_amount = round(remainder_cents / 100.0, 2)
                pi = stripe.PaymentIntent.create(
                    amount=remainder_cents,
                    currency="cad",
                    customer=customer_id,
                    payment_method=user_doc.get("stripe_default_payment_method"),
                    off_session=True if user_doc.get("stripe_default_payment_method") else False,
                    confirm=True if user_doc.get("stripe_default_payment_method") else False,
                    description=f"BidVex Vehicle Platform Fee Remainder — Listing {data.listing_id}",
                    metadata={
                        "type": "vehicle_buy_now_remainder",
                        "listing_id": data.listing_id,
                        "buyer_id": current_user.id,
                        "transaction_id": transaction_id,
                        "bidvex_role": "platform_intermediary",
                        "vehicle_price_collected_by_bidvex": "false",
                        "fee_type": "vehicle_platform_fee_remainder",
                    },
                )
                card_charged_amount = remainder_amount
                stripe_actions.append({"action": "card_charge_remainder", "pi": pi.id, "amount": remainder_amount})
                await db.vehicle_bid_deposits.update_one(
                    {"id": deposit["id"]},
                    {"$set": {
                        "status": "captured",
                        "captured_amount": deposit_amount,
                        "captured_at": now,
                        "capture_reason": "vehicle_buy_now_platform_fee",
                    }},
                )
        else:
            # No deposit — charge full fee to card on file
            payment_method = user_doc.get("stripe_default_payment_method")
            if not payment_method:
                # Fall back to a Stripe Checkout session — card on file required for off-session
                session = stripe.checkout.Session.create(
                    customer=customer_id,
                    payment_method_types=["card"],
                    mode="payment",
                    line_items=[{
                        "price_data": {
                            "currency": "cad",
                            "unit_amount": platform_fee_cents,
                            "product_data": {
                                "name": f"Vehicle Platform Fee — {listing.get('title', 'Vehicle')}",
                                "description": f"2.5% BidVex platform fee + stripe + {bi.tax_label}",
                            },
                        },
                        "quantity": 1,
                    }],
                    success_url=f"{os.environ.get('FRONTEND_URL', 'https://bidvex.com')}/vehicle-auctions/{data.listing_id}?buy_now=success&txn={transaction_id}",
                    cancel_url=f"{os.environ.get('FRONTEND_URL', 'https://bidvex.com')}/vehicle-auctions/{data.listing_id}?buy_now=cancelled",
                    metadata={
                        "type": "vehicle_buy_now",
                        "listing_id": data.listing_id,
                        "buyer_id": current_user.id,
                        "transaction_id": transaction_id,
                        "bidvex_role": "platform_intermediary",
                        "vehicle_price_collected_by_bidvex": "false",
                    },
                )
                # Record transaction as pending checkout
                await db.vehicle_buy_now_transactions.insert_one({
                    "id": transaction_id,
                    "listing_id": data.listing_id,
                    "buyer_id": current_user.id,
                    "seller_id": listing.get("seller_id"),
                    "buy_now_price": buy_now_price,
                    "platform_fee": bi.fees_subtotal,
                    "stripe_recovery": bi.stripe_recovery,
                    "tax_amount": bi.tax_amount,
                    "tax_label": bi.tax_label,
                    "buyer_province": buyer_province,
                    "total_platform_fee": platform_fee_total,
                    "payment_status": "pending",
                    "deposit_captured": 0.0,
                    "card_charged": 0.0,
                    "stripe_session_id": session.id,
                    "transaction_date": now.isoformat(),
                })
                return {
                    "success": True,
                    "requires_checkout": True,
                    "checkout_url": session.url,
                    "session_id": session.id,
                    "transaction_id": transaction_id,
                    "breakdown": pr.to_dict(),
                }

            pi = stripe.PaymentIntent.create(
                amount=platform_fee_cents,
                currency="cad",
                customer=customer_id,
                payment_method=payment_method,
                off_session=True,
                confirm=True,
                description=f"BidVex Vehicle Platform Fee — Listing {data.listing_id}",
                metadata={
                    "type": "vehicle_buy_now",
                    "listing_id": data.listing_id,
                    "buyer_id": current_user.id,
                    "transaction_id": transaction_id,
                    "bidvex_role": "platform_intermediary",
                    "vehicle_price_collected_by_bidvex": "false",
                },
            )
            card_charged_amount = platform_fee_total
            stripe_actions.append({"action": "card_charge_full", "pi": pi.id, "amount": platform_fee_total})
    except stripe.CardError as ce:
        raise HTTPException(status_code=402, detail=f"Card declined: {ce.user_message or str(ce)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("vehicle_buy_now stripe error")
        raise HTTPException(status_code=500, detail=f"Payment processing error: {str(e)}")

    # Mark listing as sold
    await db.vehicle_listings.update_one(
        {"id": data.listing_id},
        {"$set": {
            "status": "sold",
            "sold_via_buy_now": True,
            "winner_id": current_user.id,
            "sold_at": now.isoformat(),
            "final_price": buy_now_price,
        }},
    )

    # Create transaction record
    await db.vehicle_buy_now_transactions.insert_one({
        "id": transaction_id,
        "listing_id": data.listing_id,
        "buyer_id": current_user.id,
        "seller_id": listing.get("seller_id"),
        "buy_now_price": buy_now_price,
        "platform_fee": bi.fees_subtotal,
        "stripe_recovery": bi.stripe_recovery,
        "tax_amount": bi.tax_amount,
        "tax_label": bi.tax_label,
        "buyer_province": buyer_province,
        "total_platform_fee": platform_fee_total,
        "payment_status": "paid",
        "deposit_captured": deposit_captured_amount,
        "card_charged": card_charged_amount,
        "stripe_actions": stripe_actions,
        "transaction_date": now.isoformat(),
        "paid_at": now.isoformat(),
    })

    # Send the standard winner email (is_vehicle=True inserts the bilingual non-custodial notice)
    try:
        from services.email_notifications import send_auction_won_email
        seller = await db.users.find_one({"id": listing.get("seller_id")}, {"_id": 0})
        await send_auction_won_email(
            to_email=user_doc.get("email", current_user.email),
            to_name=user_doc.get("name", current_user.email),
            auction_id=data.listing_id,
            item_name=listing.get("title", "Vehicle"),
            hammer_price=buy_now_price,
            platform_fee=platform_fee_total,
            seller_name=(seller.get("name") if seller else ""),
            seller_contact=(seller.get("email") if seller else ""),
            is_vehicle=True,
            buyer_province=buyer_province,
        )
    except Exception as e:
        logger.warning(f"Vehicle Buy Now winner email failed: {e}")

    return {
        "success": True,
        "requires_checkout": False,
        "transaction_id": transaction_id,
        "platform_fee_charged": platform_fee_total,
        "deposit_captured": deposit_captured_amount,
        "card_charged": card_charged_amount,
        "stripe_actions": stripe_actions,
        "hammer_paid_directly_to_seller": buy_now_price,
        "breakdown": pr.to_dict(),
    }
