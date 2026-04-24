"""
BidVex - Subscription Plans, Coupons & Checkout
Auto-extracted from server.py during P2 refactoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from deps import get_db, get_current_user, get_current_user_optional, User
from shared import (
    DEFAULT_EMAIL_TEMPLATES, EMAIL_TEMPLATE_CATEGORIES,
    DEFAULT_MARKETPLACE_SETTINGS, AFFILIATE_COMMISSION_RATE,
    generate_affiliate_code, get_email_templates, get_email_template_id,
    get_marketplace_settings, get_epoch_timestamp, get_server_timestamp,
    calculate_buyer_fees, calculate_seller_fees, calculate_stripe_fee_recovery,
    calculate_partner_checkout, calculate_standard_checkout,
    FeeCalculation, UserCreate, Category, Invoice, PaddleNumber,
    PaymentTransaction, SessionCreate, get_minimum_increment,
    STANDARD_BUYER_PREMIUM_RATE, STANDARD_SELLER_COMMISSION_RATE,
    PARTNER_PLATFORM_FEE_RATE, PARTNER_ANNUAL_ACCESS_FEE,
    STRIPE_PERCENTAGE_FEE, STRIPE_FIXED_FEE,
)
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from pydantic import BaseModel, Field
from pathlib import Path
import logging
import uuid
import os as _os
import json as _json

logger = logging.getLogger(__name__)

from services.subscription_pricing import get_pricing_service, CouponCode

try:
    from services.tax_engine import calculate_gst_qst
except ImportError:
    def calculate_gst_qst(subtotal, currency="CAD"):
        gst = round(subtotal * 0.05, 2)
        qst = round(subtotal * 0.09975, 2)
        return {"gst_amount": gst, "qst_amount": qst, "total_with_tax": round(subtotal + gst + qst, 2)}


def _calculate_stripe_fee(amount):
    return round(amount * STRIPE_PERCENTAGE_FEE + STRIPE_FIXED_FEE, 2) if amount > 0 else 0


async def _generate_subscription_invoice(db, user, plan_id, amount, subscription_id, fee):
    invoice = {
        "id": str(uuid.uuid4()),
        "user_id": user.id,
        "plan_id": plan_id,
        "amount": amount,
        "fee": fee,
        "subscription_id": str(subscription_id) if subscription_id else None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "paid",
    }
    await db.subscription_invoices.insert_one(invoice)

import stripe

subscriptions_router = APIRouter(tags=["Subscriptions"])


@subscriptions_router.get("/admin/subscription-plans")
async def get_subscription_plans(current_user: User = Depends(get_current_user)):
    """Get all subscription plans with pricing"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pricing_service = get_pricing_service(get_db())
    plans = await pricing_service.get_all_plans()
    return {"success": True, "plans": plans}



@subscriptions_router.get("/subscription-plans")
async def get_public_subscription_plans():
    """Get public subscription plans (no auth required)"""
    pricing_service = get_pricing_service(get_db())
    plans = await pricing_service.get_all_plans()
    # Remove sensitive fields for public view (keep original_price for promotional display)
    public_plans = []
    for plan in plans:
        public_plan = {
            "plan_id": plan.get("plan_id"),
            "name": plan.get("name"),
            "price_monthly": plan.get("price_monthly", 0),
            "price_yearly": plan.get("price_yearly", 0),
            "original_price_monthly": plan.get("original_price_monthly", 0),
            "original_price_yearly": plan.get("original_price_yearly", 0),
            "features": plan.get("features", []),
            "buyer_premium_discount": plan.get("buyer_premium_discount", 0),
            "seller_commission_discount": plan.get("seller_commission_discount", 0),
            "monthly_listing_limit": plan.get("monthly_listing_limit", 0),
            "is_active": plan.get("is_active", True),
            "stripe_price_id_monthly": plan.get("stripe_price_id_monthly"),
            "stripe_price_id_yearly": plan.get("stripe_price_id_yearly")
        }
        public_plans.append(public_plan)
    return {"success": True, "plans": public_plans}



@subscriptions_router.put("/admin/subscription-plans/{plan_id}")
async def update_subscription_plan(
    plan_id: str,
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Update subscription plan pricing and settings"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pricing_service = get_pricing_service(get_db())
    reason = data.pop("reason", None)
    
    try:
        updated_plan = await pricing_service.update_plan_pricing(
            plan_id=plan_id,
            updates=data,
            admin_id=current_user.id,
            reason=reason
        )
        return {"success": True, "plan": updated_plan}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



@subscriptions_router.get("/admin/subscription-plans/changelog")
async def get_pricing_changelog(
    plan_id: Optional[str] = None,
    limit: int = 50,
    current_user: User = Depends(get_current_user)
):
    """Get pricing change history"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pricing_service = get_pricing_service(get_db())
    logs = await pricing_service.get_pricing_changelog(plan_id=plan_id, limit=limit)
    return {"success": True, "changelog": logs}



@subscriptions_router.post("/admin/coupons")
async def create_coupon(
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Create a new coupon code"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pricing_service = get_pricing_service(get_db())
    
    try:
        coupon_data = CouponCode(**data)
        coupon = await pricing_service.create_coupon(coupon_data, admin_id=current_user.id)
        return {"success": True, "coupon": coupon}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



@subscriptions_router.get("/admin/coupons")
async def get_coupons(
    include_inactive: bool = False,
    current_user: User = Depends(get_current_user)
):
    """Get all coupon codes"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pricing_service = get_pricing_service(get_db())
    coupons = await pricing_service.get_all_coupons(include_inactive=include_inactive)
    return {"success": True, "coupons": coupons}



@subscriptions_router.get("/admin/coupons/{coupon_id}")
async def get_coupon(
    coupon_id: str,
    current_user: User = Depends(get_current_user)
):
    """Get a specific coupon by ID"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pricing_service = get_pricing_service(get_db())
    coupon = await pricing_service.get_coupon(coupon_id)
    if not coupon:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return {"success": True, "coupon": coupon}



@subscriptions_router.put("/admin/coupons/{coupon_id}")
async def update_coupon(
    coupon_id: str,
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Update a coupon code"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pricing_service = get_pricing_service(get_db())
    
    try:
        updated_coupon = await pricing_service.update_coupon(
            coupon_id=coupon_id,
            updates=data,
            admin_id=current_user.id
        )
        return {"success": True, "coupon": updated_coupon}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))



@subscriptions_router.delete("/admin/coupons/{coupon_id}")
async def delete_coupon(
    coupon_id: str,
    current_user: User = Depends(get_current_user)
):
    """Delete (deactivate) a coupon code"""
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    pricing_service = get_pricing_service(get_db())
    success = await pricing_service.delete_coupon(coupon_id)
    if not success:
        raise HTTPException(status_code=404, detail="Coupon not found")
    return {"success": True, "message": "Coupon deactivated"}



@subscriptions_router.post("/validate-coupon")
async def validate_coupon_code(data: Dict[str, Any]):
    """
    Validate a coupon code and calculate discount.
    Public endpoint - no auth required.
    """
    code = data.get("code", "").strip()
    plan_id = data.get("plan_id", "premium")
    billing_period = data.get("billing_period", "yearly")
    
    if not code:
        raise HTTPException(status_code=400, detail="Coupon code is required")
    
    pricing_service = get_pricing_service(get_db())
    result = await pricing_service.validate_coupon(
        code=code,
        plan_id=plan_id,
        billing_period=billing_period
    )
    
    return result.dict()




@subscriptions_router.get("/subscriptions/price-breakdown")
async def get_price_breakdown(plan_id: str):
    """Get full price breakdown including taxes and processing fee for a plan."""
    pricing_service = get_pricing_service(get_db())
    plan = await pricing_service.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")

    subtotal = plan.get("price_yearly", 0)
    tax = calculate_gst_qst(subtotal)
    amount_after_tax = tax["total_with_tax"]
    processing_fee = _calculate_stripe_fee(amount_after_tax) if subtotal > 0 else 0
    total = round(amount_after_tax + processing_fee, 2)

    return {
        "plan_id": plan_id,
        "plan_name": plan.get("name", plan_id.title()),
        "subtotal": subtotal,
        "gst": tax["gst_amount"],
        "qst": tax["qst_amount"],
        "processing_fee": processing_fee,
        "total": total,
        "currency": "CAD"
    }




@subscriptions_router.post("/subscriptions/create")
async def create_subscription(
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """
    Create a Stripe subscription using the user's saved default payment method.
    No redirect — charges the card on file directly.
    """
    plan_id = data.get("plan_id")  # "premium", "partner_pro", or "vip"
    if plan_id not in ("premium", "partner_pro", "vip"):
        raise HTTPException(status_code=400, detail="Invalid plan. Choose 'premium', 'partner_pro', or 'vip'.")

    user = await get_db().users.find_one({"id": current_user.id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    customer_id = user.get("stripe_customer_id")
    if not customer_id:
        raise HTTPException(status_code=400, detail="No Stripe customer on file. Please add a payment method first.")

    default_pm = user.get("default_payment_method_id")
    if not default_pm:
        raise HTTPException(status_code=400, detail="No payment method on file. Please add a card first.")

    # Look up the Stripe Price ID from the DB
    pricing_service = get_pricing_service(get_db())
    plan = await pricing_service.get_plan(plan_id)
    if not plan:
        raise HTTPException(status_code=400, detail="Plan not found")

    stripe_price_id = plan.get("stripe_price_id_yearly")
    if not stripe_price_id:
        raise HTTPException(status_code=400, detail="Stripe price not configured for this plan")

    # Handle existing subscription — upgrade with proration instead of cancel
    existing_sub_id = user.get("stripe_subscription_id")
    if existing_sub_id:
        try:
            existing_sub = stripe.Subscription.retrieve(existing_sub_id)
            existing_status = dict(existing_sub).get("status")
            
            if existing_status in ("active", "trialing"):
                # Upgrade: swap the price item, Stripe handles proration automatically
                items_data = dict(existing_sub).get("items", {})
                items_list = items_data.get("data", []) if isinstance(items_data, dict) else []
                
                if items_list:
                    old_item_id = items_list[0].get("id") if isinstance(items_list[0], dict) else items_list[0].id
                    updated_sub = stripe.Subscription.modify(
                        existing_sub_id,
                        items=[{
                            "id": old_item_id,
                            "price": stripe_price_id
                        }],
                        proration_behavior="create_prorations",
                        metadata={
                            "user_id": current_user.id,
                            "plan_id": plan_id,
                            "billing_period": "yearly"
                        }
                    )
                    
                    up_data = dict(updated_sub)
                    start_ts = up_data.get("start_date") or up_data.get("billing_cycle_anchor") or up_data.get("created")
                    start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc) if start_ts else datetime.now(timezone.utc)
                    end_dt = start_dt.replace(year=start_dt.year + 1)
                    
                    await get_db().users.update_one(
                        {"id": current_user.id},
                        {"$set": {
                            "subscription_tier": plan_id,
                            "subscription_status": "active",
                            "stripe_subscription_id": updated_sub.id,
                            "subscription_source": "stripe",
                            "subscription_start_date": start_dt.isoformat(),
                            "subscription_end_date": end_dt.isoformat(),
                            "cancel_at_period_end": False,
                            "updated_at": datetime.now(timezone.utc).isoformat()
                        }}
                    )
                    
                    logger.info(f"Subscription upgraded: {updated_sub.id} for user {current_user.id}, new tier={plan_id}")

                    # Generate invoice for the upgrade
                    price_amount = plan.get("price_yearly", 0)
                    fee = _calculate_stripe_fee(calculate_gst_qst(price_amount)["total_with_tax"]) if price_amount > 0 else 0
                    try:
                        await _generate_subscription_invoice(get_db(), user, plan_id, price_amount, updated_sub.id, fee)
                    except Exception as inv_err:
                        logger.error(f"Invoice generation failed for upgrade: {inv_err}")

                    return {
                        "success": True,
                        "subscription_id": updated_sub.id,
                        "status": "active",
                        "tier": plan_id,
                        "current_period_end": end_dt.isoformat(),
                        "action": "upgraded"
                    }
            else:
                # Old sub is canceled/past_due — cancel it fully and create new
                try:
                    stripe.Subscription.cancel(existing_sub_id)
                except Exception:
                    pass
        except stripe.StripeError as e:
            logger.warning(f"Could not modify old subscription {existing_sub_id}: {e}")
            try:
                stripe.Subscription.cancel(existing_sub_id)
            except Exception:
                pass

    try:
        subscription = stripe.Subscription.create(
            customer=customer_id,
            items=[{"price": stripe_price_id}],
            default_payment_method=default_pm,
            metadata={
                "user_id": current_user.id,
                "plan_id": plan_id,
                "billing_period": "yearly"
            }
        )

        sub_data = dict(subscription)
        # For yearly plans, period end = billing_cycle_anchor + 1 year
        start_ts = sub_data.get("start_date") or sub_data.get("billing_cycle_anchor") or sub_data.get("created")
        if start_ts:
            start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
            end_dt = start_dt.replace(year=start_dt.year + 1)
            end_date = end_dt.isoformat()
            start_date = start_dt.isoformat()
        else:
            start_date = datetime.now(timezone.utc).isoformat()
            end_date = datetime.now(timezone.utc).replace(year=datetime.now(timezone.utc).year + 1).isoformat()

        # Update user record in MongoDB
        await get_db().users.update_one(
            {"id": current_user.id},
            {"$set": {
                "subscription_tier": plan_id,
                "subscription_status": "active",
                "stripe_subscription_id": subscription.id,
                "subscription_source": "stripe",
                "subscription_start_date": start_date,
                "subscription_end_date": end_date,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )

        logger.info(f"Subscription created: {subscription.id} for user {current_user.id}, tier={plan_id}")

        # Generate invoice
        price_amount = plan.get("price_yearly", 0)
        fee = _calculate_stripe_fee(calculate_gst_qst(price_amount)["total_with_tax"]) if price_amount > 0 else 0
        try:
            await _generate_subscription_invoice(get_db(), user, plan_id, price_amount, subscription.id, fee)
        except Exception as inv_err:
            logger.error(f"Invoice generation failed: {inv_err}")

        return {
            "success": True,
            "subscription_id": subscription.id,
            "status": subscription.status,
            "tier": plan_id,
            "current_period_end": end_date
        }

    except stripe.StripeError as e:
        logger.error(f"Stripe subscription creation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))





@subscriptions_router.post("/subscriptions/cancel")
async def cancel_subscription(current_user: User = Depends(get_current_user)):
    """
    Cancel subscription at period end. No refund — user keeps access until billing cycle ends.
    """
    user = await get_db().users.find_one({"id": current_user.id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sub_id = user.get("stripe_subscription_id")
    if not sub_id:
        raise HTTPException(status_code=400, detail="No active subscription to cancel")

    try:
        updated_sub = stripe.Subscription.modify(
            sub_id,
            cancel_at_period_end=True
        )

        sub_data = dict(updated_sub)
        start_ts = sub_data.get("start_date") or sub_data.get("billing_cycle_anchor") or sub_data.get("created")
        end_dt = None
        if start_ts:
            start_dt = datetime.fromtimestamp(start_ts, tz=timezone.utc)
            end_dt = start_dt.replace(year=start_dt.year + 1)

        await get_db().users.update_one(
            {"id": current_user.id},
            {"$set": {
                "subscription_status": "active",
                "cancel_at_period_end": True,
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )

        logger.info(f"Subscription {sub_id} set to cancel at period end for user {current_user.id}")

        return {
            "success": True,
            "message": "Your subscription has been set to cancel at the end of the current billing period.",
            "access_until": end_dt.isoformat() if end_dt else user.get("subscription_end_date"),
            "tier": user.get("subscription_tier")
        }

    except stripe.StripeError as e:
        logger.error(f"Stripe subscription cancellation failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))




@subscriptions_router.post("/subscriptions/reactivate")
async def reactivate_subscription(current_user: User = Depends(get_current_user)):
    """Reactivate a subscription that was set to cancel at period end."""
    user = await get_db().users.find_one({"id": current_user.id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sub_id = user.get("stripe_subscription_id")
    if not sub_id:
        raise HTTPException(status_code=400, detail="No subscription to reactivate")

    try:
        stripe.Subscription.modify(sub_id, cancel_at_period_end=False)
        await get_db().users.update_one(
            {"id": current_user.id},
            {"$set": {
                "cancel_at_period_end": False,
                "subscription_status": "active",
                "updated_at": datetime.now(timezone.utc).isoformat()
            }}
        )
        logger.info(f"Subscription {sub_id} reactivated for user {current_user.id}")
        return {"success": True, "message": "Your subscription has been reactivated. You will continue to be charged at your next renewal date."}
    except stripe.StripeError as e:
        raise HTTPException(status_code=400, detail=str(e))





@subscriptions_router.get("/subscriptions/status")
async def get_subscription_status(current_user: User = Depends(get_current_user)):
    """
    Get detailed subscription status for the management panel.
    """
    user = await get_db().users.find_one({"id": current_user.id})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    result = {
        "tier": user.get("subscription_tier", "free"),
        "status": user.get("subscription_status", "inactive"),
        "cancel_at_period_end": user.get("cancel_at_period_end", False),
        "start_date": user.get("subscription_start_date"),
        "end_date": user.get("subscription_end_date"),
        "stripe_subscription_id": user.get("stripe_subscription_id"),
        "has_payment_method": user.get("has_payment_method", False),
        "default_payment_method_id": user.get("default_payment_method_id"),
    }

    # Get live status from Stripe if subscription exists
    sub_id = user.get("stripe_subscription_id")
    if sub_id:
        try:
            sub = stripe.Subscription.retrieve(sub_id)
            sub_data = dict(sub)
            result["stripe_status"] = sub_data.get("status", "unknown")
            result["cancel_at_period_end"] = sub_data.get("cancel_at_period_end", False)
        except stripe.StripeError:
            result["stripe_status"] = "error"

    return result





@subscriptions_router.post("/subscription/checkout")
async def create_subscription_checkout(
    data: Dict[str, Any],
    request: Request,
    current_user: User = Depends(get_current_user)
):
    """
    Create a Stripe checkout session for subscription with optional coupon.
    """
    plan_id = data.get("plan_id", "premium")
    billing_period = data.get("billing_period", "yearly")  # monthly or yearly
    coupon_code = data.get("coupon_code")
    origin_url = data.get("origin_url", str(request.base_url).rstrip("/"))
    
    pricing_service = get_pricing_service(get_db())
    
    # Get plan details
    plan = await pricing_service.get_plan(plan_id)
    if not plan or plan_id == "free":
        raise HTTPException(status_code=400, detail="Invalid plan selected")
    
    # Get price
    if billing_period == "monthly":
        price = plan.get("price_monthly", 0)
        stripe_price_id = plan.get("stripe_price_id_monthly")
    else:
        price = plan.get("price_yearly", 0)
        stripe_price_id = plan.get("stripe_price_id_yearly")
    
    if price <= 0:
        raise HTTPException(status_code=400, detail="Plan pricing not configured")
    
    # Validate coupon if provided
    stripe_coupon_id = None
    discount_amount = 0
    final_price = price
    
    if coupon_code:
        validation = await pricing_service.validate_coupon(
            code=coupon_code,
            plan_id=plan_id,
            billing_period=billing_period
        )
        
        if not validation.valid:
            raise HTTPException(status_code=400, detail=validation.message)
        
        stripe_coupon_id = validation.stripe_coupon_id
        discount_amount = validation.discount_amount or 0
        final_price = validation.new_total or price
    
    # Build checkout session URLs
    success_url = f"{origin_url}/subscription/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{origin_url}/pricing"
    
    try:
        # Create Stripe checkout session
        checkout_params = {
            "mode": "subscription" if stripe_price_id else "payment",
            "success_url": success_url,
            "cancel_url": cancel_url,
            "customer_email": current_user.email,
            "metadata": {
                "user_id": current_user.id,
                "plan_id": plan_id,
                "billing_period": billing_period,
                "coupon_code": coupon_code or "",
                "original_price": str(price),
                "discount_amount": str(discount_amount),
                "final_price": str(final_price)
            }
        }
        
        if stripe_price_id:
            checkout_params["line_items"] = [{
                "price": stripe_price_id,
                "quantity": 1
            }]
        else:
            # One-time payment with jurisdiction-aware tax (Rule 5 + Rule 6)
            import os
            from decimal import Decimal, ROUND_HALF_UP
            from services.pricing_manager import PricingManager

            # Get buyer's province from profile
            db = get_db()
            buyer_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0, "province": 1})
            buyer_province = (buyer_doc or {}).get("province", "QC")

            pricing_result = PricingManager.flat_purchase(final_price, buyer_province, f"BidVex {plan.get('name')} Subscription")
            pi = pricing_result.buyer_invoice

            base_cents = int(final_price * 100)
            stripe_cents = int(Decimal(str(pi.stripe_recovery)) * 100)
            tax_cents = int(Decimal(str(pi.tax_amount)) * 100)

            checkout_params["line_items"] = [
                {
                    "price_data": {
                        "currency": "cad",
                        "product_data": {
                            "name": f"BidVex {plan.get('name')} - {billing_period.capitalize()}",
                            "description": f"BidVex {plan.get('name')} subscription"
                        },
                        "unit_amount": base_cents,
                    },
                    "quantity": 1
                },
                {
                    "price_data": {
                        "currency": "cad",
                        "product_data": {
                            "name": "Stripe Processing Fee",
                            "description": "Payment processing fee recovery",
                        },
                        "unit_amount": stripe_cents,
                    },
                    "quantity": 1
                },
                {
                    "price_data": {
                        "currency": "cad",
                        "product_data": {
                            "name": f"Tax — {pi.tax_label}",
                            "description": f"{pi.tax_type} — GST# {os.environ.get('PLATFORM_GST_NUMBER', '')}",
                        },
                        "unit_amount": tax_cents,
                    },
                    "quantity": 1
                },
            ]
            checkout_params["mode"] = "payment"
            checkout_params["metadata"]["tax_type"] = pi.tax_type
            checkout_params["metadata"]["tax_label"] = pi.tax_label
            checkout_params["metadata"]["buyer_province"] = buyer_province
        
        # Apply coupon if we have a Stripe coupon ID
        if stripe_coupon_id:
            checkout_params["discounts"] = [{"coupon": stripe_coupon_id}]
        
        session = stripe.checkout.Session.create(**checkout_params)
        
        # Create payment transaction record
        transaction = {
            "id": f"txn-{datetime.now().timestamp()}",
            "session_id": session.id,
            "user_id": current_user.id,
            "user_email": current_user.email,
            "plan_id": plan_id,
            "billing_period": billing_period,
            "original_amount": price,
            "discount_amount": discount_amount,
            "final_amount": final_price,
            "coupon_code": coupon_code,
            "currency": "cad",
            "payment_status": "initiated",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await get_db().payment_transactions.insert_one(transaction)
        
        # Increment coupon usage if applied
        if coupon_code:
            await pricing_service.increment_coupon_usage(coupon_code)
        
        return {
            "success": True,
            "checkout_url": session.url,
            "session_id": session.id,
            "original_price": price,
            "discount_amount": discount_amount,
            "final_price": final_price
        }
        
    except stripe.StripeError as e:
        logger.error(f"Stripe checkout error: {e}")
        raise HTTPException(status_code=500, detail=f"Payment processing error: {str(e)}")



@subscriptions_router.get("/admin/subscription-analytics")
async def get_subscription_analytics(current_user: User = Depends(get_current_user)):
    """
    Get comprehensive subscription analytics for admin dashboard.
    Includes revenue metrics, subscriber counts, plan distribution, coupon usage.
    """
    if getattr(current_user, "role", None) not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        now = datetime.now(timezone.utc)
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        start_of_last_month = (start_of_month - timedelta(days=1)).replace(day=1)
        
        # Get all users with subscriptions
        users = await get_db().users.find({}, {"_id": 0, "subscription_tier": 1, "subscription_start_date": 1, "subscription_end_date": 1, "subscription_source": 1}).to_list(10000)
        
        # Calculate subscriber counts by plan
        plan_counts = {"free": 0, "premium": 0, "vip": 0}
        active_subscribers = 0
        manual_count = 0
        stripe_count = 0
        
        for user in users:
            tier = user.get("subscription_tier", "free").lower()
            if tier in plan_counts:
                plan_counts[tier] += 1
            else:
                plan_counts["free"] += 1
            
            if tier != "free":
                active_subscribers += 1
                source = user.get("subscription_source", "").lower()
                if source == "manual":
                    manual_count += 1
                else:
                    stripe_count += 1
        
        # Get payment transactions for revenue
        transactions = await get_db().payment_transactions.find({
            "status": "completed",
            "type": {"$in": ["subscription_checkout", "subscription"]}
        }, {"_id": 0}).to_list(1000)
        
        total_revenue = 0
        monthly_revenue = 0
        yearly_revenue = 0
        this_month_revenue = 0
        last_month_revenue = 0
        
        monthly_data = {}  # For chart data
        
        for txn in transactions:
            amount = float(txn.get("final_price", txn.get("amount", 0)))
            total_revenue += amount
            
            billing = txn.get("billing_period", "yearly")
            if billing == "monthly":
                monthly_revenue += amount
            else:
                yearly_revenue += amount
            
            created_at = txn.get("created_at")
            if created_at:
                try:
                    if isinstance(created_at, str):
                        txn_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                    else:
                        txn_date = created_at
                    
                    # Monthly breakdown for chart
                    month_key = txn_date.strftime("%Y-%m")
                    if month_key not in monthly_data:
                        monthly_data[month_key] = {"revenue": 0, "count": 0}
                    monthly_data[month_key]["revenue"] += amount
                    monthly_data[month_key]["count"] += 1
                    
                    # This month vs last month
                    if txn_date >= start_of_month:
                        this_month_revenue += amount
                    elif txn_date >= start_of_last_month and txn_date < start_of_month:
                        last_month_revenue += amount
                except Exception:
                    pass
        
        # Get coupon statistics
        coupons = await get_db().coupon_codes.find({}, {"_id": 0}).to_list(100)
        total_coupons = len(coupons)
        active_coupons = sum(1 for c in coupons if c.get("is_active", True))
        total_coupon_uses = sum(c.get("usage_count", 0) for c in coupons)
        
        # Top coupons by usage
        top_coupons = sorted(coupons, key=lambda x: x.get("usage_count", 0), reverse=True)[:5]
        top_coupons_data = [
            {
                "code": c.get("code"),
                "uses": c.get("usage_count", 0),
                "discount_type": c.get("discount_type"),
                "value": c.get("value")
            }
            for c in top_coupons
        ]
        
        # Calculate discount savings from coupons
        total_discount_given = 0
        for txn in transactions:
            discount = float(txn.get("discount_amount", 0))
            total_discount_given += discount
        
        # Get pricing changelog for recent changes
        recent_changes = await get_db().pricing_changelog.find({}, {"_id": 0}).sort("changed_at", -1).limit(10).to_list(10)
        
        # Calculate MRR (Monthly Recurring Revenue) estimate
        mrr_estimate = (plan_counts.get("premium", 0) * 30 + plan_counts.get("vip", 0) * 60)  # Using current prices
        
        # Growth calculation
        growth_percentage = 0
        if last_month_revenue > 0:
            growth_percentage = round(((this_month_revenue - last_month_revenue) / last_month_revenue) * 100, 1)
        
        # Prepare monthly chart data (last 6 months)
        chart_data = []
        for i in range(5, -1, -1):
            month_date = now - timedelta(days=30 * i)
            month_key = month_date.strftime("%Y-%m")
            month_label = month_date.strftime("%b %Y")
            data = monthly_data.get(month_key, {"revenue": 0, "count": 0})
            chart_data.append({
                "month": month_label,
                "revenue": round(data["revenue"], 2),
                "subscriptions": data["count"]
            })
        
        return {
            "success": True,
            "overview": {
                "total_revenue": round(total_revenue, 2),
                "this_month_revenue": round(this_month_revenue, 2),
                "last_month_revenue": round(last_month_revenue, 2),
                "growth_percentage": growth_percentage,
                "mrr_estimate": round(mrr_estimate, 2),
                "monthly_revenue_split": round(monthly_revenue, 2),
                "yearly_revenue_split": round(yearly_revenue, 2)
            },
            "subscribers": {
                "total_users": len(users),
                "active_subscribers": active_subscribers,
                "free_users": plan_counts.get("free", 0),
                "premium_users": plan_counts.get("premium", 0),
                "vip_users": plan_counts.get("vip", 0),
                "manual_subscriptions": manual_count,
                "stripe_subscriptions": stripe_count
            },
            "coupons": {
                "total_coupons": total_coupons,
                "active_coupons": active_coupons,
                "total_uses": total_coupon_uses,
                "total_discount_given": round(total_discount_given, 2),
                "top_coupons": top_coupons_data
            },
            "chart_data": chart_data,
            "recent_changes": recent_changes
        }
    except Exception as e:
        logger.error(f"Error fetching subscription analytics: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@subscriptions_router.get("/subscription/status")
async def get_subscription_status_simple(current_user: User = Depends(get_current_user)):
    """Get user's subscription status and features - Yearly billing, no Power Bids"""
    tier = current_user.subscription_tier
    
    features = {
        "free": {
            "tier": "Free",
            "buyer_premium": "5%",
            "seller_commission": "4%",
            "auto_bid_bot": False,
            "priority_notifications": False,
            "early_access": False,
            "promotion_days": 0
        },
        "premium": {
            "tier": "Premium",
            "buyer_premium": "3.5%",
            "seller_commission": "2.5%",
            "auto_bid_bot": True,
            "priority_notifications": True,
            "early_access": False,
            "promotion_days": 3,
            "price": "$99.99/year"
        },
        "vip": {
            "tier": "VIP",
            "buyer_premium": "3%",
            "seller_commission": "2%",
            "auto_bid_bot": True,
            "priority_notifications": True,
            "early_access": True,
            "promotion_days": 7,
            "price": "$299.99/year"
        }
    }
    
    return {
        "subscription_tier": tier,
        "subscription_status": current_user.subscription_status,
        "features": features.get(tier, features["free"]),
        "subscription_start_date": current_user.subscription_start_date,
        "subscription_end_date": current_user.subscription_end_date
    }



