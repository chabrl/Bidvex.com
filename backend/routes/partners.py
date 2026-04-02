"""
BidVex - Partner Account System
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

import stripe
from starlette.responses import FileResponse

partners_router = APIRouter(tags=["Partners"])


@partners_router.post("/partner/apply")
async def apply_for_partner(
    company_name: str = Form(...),
    neq_number: str = Form(...),
    neq_document: UploadFile = File(...),
    certification_documents: List[UploadFile] = File(...),
    current_user: User = Depends(get_current_user)
):
    """
    Submit a partner application with mandatory NEQ proof and professional certifications.
    Sets partner_verification_status to 'pending'.
    """
    # Check not already partner or pending
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if user_doc and user_doc.get("is_partner"):
        raise HTTPException(status_code=400, detail="Account is already a verified partner.")
    if user_doc and user_doc.get("partner_verification_status") == "pending":
        raise HTTPException(status_code=400, detail="You already have a pending partner application.")

    # Validate file types (PDF, JPG, PNG only)
    allowed_types = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp']
    
    if neq_document.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="NEQ document must be PDF, JPG, PNG, or WebP.")
    
    for cert_doc in certification_documents:
        if cert_doc.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Certification file '{cert_doc.filename}' must be PDF, JPG, PNG, or WebP.")

    # Store files
    upload_dir = Path("uploads/partner_docs")
    upload_dir.mkdir(parents=True, exist_ok=True)
    base_url = os.environ.get("REACT_APP_BACKEND_URL", "http://localhost:8001")

    # Save NEQ document
    neq_contents = await neq_document.read()
    if len(neq_contents) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="NEQ document must be less than 10MB.")
    neq_ext = neq_document.filename.split('.')[-1] if '.' in neq_document.filename else 'pdf'
    neq_filename = f"neq_{current_user.id}_{uuid.uuid4().hex[:8]}.{neq_ext}"
    with open(upload_dir / neq_filename, "wb") as f:
        f.write(neq_contents)
    neq_url = f"{base_url}/api/uploads/partner_docs/{neq_filename}"

    # Save certification documents
    cert_urls = []
    for cert_doc in certification_documents:
        cert_contents = await cert_doc.read()
        if len(cert_contents) > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail=f"File '{cert_doc.filename}' must be less than 10MB.")
        cert_ext = cert_doc.filename.split('.')[-1] if '.' in cert_doc.filename else 'pdf'
        cert_filename = f"cert_{current_user.id}_{uuid.uuid4().hex[:8]}.{cert_ext}"
        with open(upload_dir / cert_filename, "wb") as f:
            f.write(cert_contents)
        cert_urls.append(f"{base_url}/api/uploads/partner_docs/{cert_filename}")

    # Update user document
    now = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"id": current_user.id},
        {"$set": {
            "is_partner": False,
            "partner_verification_status": "pending",
            "partner_company_name": company_name,
            "partner_neq": neq_number,
            "partner_neq_document": neq_url,
            "partner_certifications": cert_urls,
            "partner_applied_at": now,
            "updated_at": now,
        }}
    )

    # Log the application for admin audit
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()),
        "action": "partner_application_submitted",
        "user_id": current_user.id,
        "user_email": current_user.email,
        "details": {
            "company_name": company_name,
            "neq_number": neq_number,
            "num_certifications": len(cert_urls),
        },
        "timestamp": now,
    })

    # ===== AUTOMATED EMAIL ONBOARDING (Task 5) =====
    try:
        _sg_config = None
        try:
            _sg_config = await _get_sendgrid_config()
        except Exception:
            pass
        if _sg_config:
            import sendgrid
            from sendgrid.helpers.mail import Mail, Email, To, Content
            
            sg = sendgrid.SendGridAPIClient(api_key=_sg_config["api_key"])
            from_email = Email(_sg_config["from_email"], _sg_config["from_name"])
            
            # 1) Applicant auto-reply
            applicant_html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 560px; margin: 0 auto; color: #1e293b;">
              <h2 style="color: #2563eb;">Thank You for Applying</h2>
              <p>Dear {current_user.email.split('@')[0].title()},</p>
              <p>Thank you for applying to the <strong>BidVex Partner Network</strong>. Our team is currently reviewing your NEQ and professional credentials.</p>
              <p><strong>Expected turnaround: 24-48 hours.</strong></p>
              <p>If we need additional information, we will reach out to you directly.</p>
              <hr style="border: none; border-top: 1px solid #e2e8f0; margin: 20px 0;" />
              <p style="color: #64748b; font-size: 13px;">Application Summary:</p>
              <ul style="color: #475569; font-size: 13px;">
                <li>Company: <strong>{company_name}</strong></li>
                <li>NEQ: <strong>{neq_number}</strong></li>
                <li>Documents: {len(cert_urls)} certification(s) + NEQ proof</li>
              </ul>
              <p style="color: #64748b; font-size: 12px; margin-top: 20px;">
                Questions? Contact us at <a href="mailto:partners@bidvex.ca" style="color: #2563eb;">partners@bidvex.ca</a>
              </p>
            </div>
            """
            applicant_mail = Mail(
                from_email=from_email,
                to_emails=To(current_user.email),
                subject="BidVex Partner Application — Under Review",
                html_content=Content("text/html", applicant_html)
            )
            sg.client.mail.send.post(request_body=applicant_mail.get())
            
            # 2) Internal alert to partners@bidvex.ca
            cert_links = "".join([f'<li><a href="{url}">{url.split("/")[-1]}</a></li>' for url in cert_urls])
            internal_html = f"""
            <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; color: #1e293b;">
              <h2 style="color: #dc2626;">New Partner Application</h2>
              <table style="font-size: 14px; border-collapse: collapse;">
                <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Applicant:</td><td>{current_user.email}</td></tr>
                <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Company:</td><td>{company_name}</td></tr>
                <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">NEQ:</td><td>{neq_number}</td></tr>
                <tr><td style="padding: 4px 12px 4px 0; font-weight: bold;">Applied At:</td><td>{now}</td></tr>
              </table>
              <h3 style="margin-top: 16px;">Submitted Documents:</h3>
              <ul>
                <li><a href="{neq_url}">NEQ Proof</a></li>
                {cert_links}
              </ul>
              <p style="margin-top: 16px;"><a href="{base_url}/admin" style="color: #2563eb; font-weight: bold;">Review in Admin Panel</a></p>
            </div>
            """
            internal_mail = Mail(
                from_email=from_email,
                to_emails=To("partners@bidvex.ca"),
                subject=f"[ACTION REQUIRED] New Partner Application: {company_name}",
                html_content=Content("text/html", internal_html)
            )
            sg.client.mail.send.post(request_body=internal_mail.get())
            
            logger.info(f"Partner onboarding emails sent for {current_user.email}")
        else:
            logger.info("SendGrid not configured — partner onboarding emails skipped. Configure via Admin > Email Settings.")
    except Exception as e:
        logger.warning(f"Failed to send partner onboarding emails: {e}")
        # Don't block the application submission if email fails

    return {
        "success": True,
        "message": "Partner application submitted. Our team will review your documents and reach out at partners@bidvex.ca.",
        "verification_status": "pending"
    }




@partners_router.get("/partner/status")
async def get_partner_status(current_user: User = Depends(get_current_user)):
    """Get the current user's partner account status."""
    db = get_db()
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    
    return {
        "is_partner": user_doc.get("is_partner", False),
        "verification_status": user_doc.get("partner_verification_status", "unverified"),
        "company_name": user_doc.get("partner_company_name"),
        "neq_number": user_doc.get("partner_neq"),
        "applied_at": user_doc.get("partner_applied_at"),
        "verified_at": user_doc.get("partner_verified_at"),
        "rejection_reason": user_doc.get("partner_rejection_reason"),
        "custom_premium_rate": user_doc.get("custom_premium_rate"),
    }




@partners_router.get("/uploads/partner_docs/{filename}")
async def serve_partner_document(filename: str, current_user: User = Depends(get_current_user)):
    """Serve uploaded partner documents (auth required)."""
    db = get_db()
    from fastapi.responses import FileResponse
    file_path = Path("uploads/partner_docs") / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    # Only allow the owner or admin to access
    user_doc = await db.users.find_one({"id": current_user.id})
    is_owner = filename.startswith(f"neq_{current_user.id}") or filename.startswith(f"cert_{current_user.id}")
    if not is_owner and user_doc.get("role") not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Access denied")
    return FileResponse(str(file_path))




@partners_router.get("/partner/payment-status")
async def get_partner_payment_status(current_user: User = Depends(get_current_user)):
    """Get current partner's payment status and checkout URL if needed."""
    db = get_db()
    if not current_user.is_partner and current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=400, detail="Not a partner account")
    
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    
    result = {
        "is_partner": True,
        "platform_fee_paid": user_doc.get("platform_fee_paid", False),
        "partner_verification_status": user_doc.get("partner_verification_status"),
        "partner_subscription_id": user_doc.get("partner_subscription_id"),
        "checkout_url": user_doc.get("partner_checkout_url"),
    }
    return result




@partners_router.post("/partner/create-checkout")
async def create_partner_checkout(current_user: User = Depends(get_current_user)):
    """Create a new Stripe Checkout Session for partner fee payment."""
    db = get_db()
    if not current_user.is_partner and current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=400, detail="Not a partner account")
    if current_user.platform_fee_paid:
        raise HTTPException(status_code=400, detail="Annual fee already paid")
    
    try:
        price_id = await _get_or_create_partner_fee_price()
        base_url = os.environ.get("REACT_APP_BACKEND_URL", "https://www.bidvex.com")
        
        customer_id = current_user.stripe_customer_id
        if not customer_id:
            customer = stripe.Customer.create(
                email=current_user.email,
                name=current_user.name,
                metadata={"user_id": current_user.id, "type": "partner"}
            )
            customer_id = customer.id
            await db.users.update_one({"id": current_user.id}, {"$set": {"stripe_customer_id": customer_id}})
        
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[{"price": price_id, "quantity": 1}],
            metadata={"user_id": current_user.id, "type": "partner_activation", "business_name": current_user.company_name or current_user.name},
            success_url=f"{base_url}/partner/dashboard?session_id={{CHECKOUT_SESSION_ID}}&partner_payment=success",
            cancel_url=f"{base_url}/partner/dashboard?partner_payment=cancelled",
            subscription_data={
                "metadata": {"user_id": current_user.id, "type": "partner_annual_fee"}
            },
        )
        
        await db.users.update_one({"id": current_user.id}, {"$set": {
            "partner_checkout_session_id": session.id,
            "partner_checkout_url": session.url,
        }})
        
        return {"checkout_url": session.url}
    except Exception as e:
        logger.error(f"Failed to create partner checkout: {e}")
        raise HTTPException(status_code=500, detail="Failed to create payment session")




@partners_router.post("/partner/manage-billing")
async def create_partner_billing_portal(current_user: User = Depends(get_current_user)):
    """Create a Stripe Customer Portal session for partner billing management.
    Partners can download invoices (with GST/QST), update payment methods, and manage subscriptions."""
    db = get_db()
    if not current_user.is_partner and current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=400, detail="Not a partner account")
    
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
    customer_id = user_doc.get("stripe_customer_id") if user_doc else None
    if not customer_id:
        raise HTTPException(status_code=400, detail="No billing account found. Please complete your initial payment first.")
    
    try:
        base_url = os.environ.get("REACT_APP_BACKEND_URL", "https://www.bidvex.com")
        
        # Configure portal to open on invoices/billing history page
        session = stripe.billing_portal.Session.create(
            customer=customer_id,
            return_url=f"{base_url}/partner/dashboard",
            flow_data={
                "type": "subscription_update_confirm",
            } if False else None,  # No flow_data — default portal view shows invoices
        )
        return {"url": session.url}
    except Exception as e:
        logger.error(f"Failed to create billing portal session: {e}")
        raise HTTPException(status_code=500, detail="Failed to create billing portal session")




@partners_router.get("/partner/dashboard")
async def get_partner_dashboard(current_user: User = Depends(get_current_user)):
    """Get aggregated dashboard data for partner accounts. Admins can also access."""
    db = get_db()
    if not current_user.is_partner and current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=400, detail="Not a partner account")
    
    user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0, "password": 0})
    
    # Listing stats
    active_listings = await db.listings.count_documents({"seller_id": current_user.id, "status": "active"})
    total_listings = await db.listings.count_documents({"seller_id": current_user.id})
    active_multi = await db.multi_item_listings.count_documents({"seller_id": current_user.id, "status": "active"})
    total_multi = await db.multi_item_listings.count_documents({"seller_id": current_user.id})
    
    # Bid stats
    bid_pipeline = [
        {"$match": {"seller_id": current_user.id}},
        {"$group": {"_id": None, "total_bids": {"$sum": "$bid_count"}}},
    ]
    bid_results = await db.listings.aggregate(bid_pipeline).to_list(1)
    total_bids = bid_results[0]["total_bids"] if bid_results else 0
    
    # Subscription info from Stripe if available
    subscription_info = None
    sub_id = user_doc.get("partner_subscription_id")
    if sub_id:
        try:
            sub = stripe.Subscription.retrieve(sub_id)
            subscription_info = {
                "status": sub.status,
                "current_period_start": datetime.fromtimestamp(sub.current_period_start, tz=timezone.utc).isoformat(),
                "current_period_end": datetime.fromtimestamp(sub.current_period_end, tz=timezone.utc).isoformat(),
                "cancel_at_period_end": sub.cancel_at_period_end,
                "plan_amount": sub.items.data[0].price.unit_amount / 100 if sub.items.data else 100,
                "plan_currency": sub.items.data[0].price.currency if sub.items.data else "cad",
                "plan_interval": sub.items.data[0].price.recurring.interval if sub.items.data else "year",
            }
        except Exception as e:
            logger.warning(f"Failed to retrieve partner subscription {sub_id}: {e}")
    
    # Recent activity (last 5 listing actions)
    recent_listings = await db.listings.find(
        {"seller_id": current_user.id},
        {"_id": 0, "id": 1, "title": 1, "status": 1, "created_at": 1, "bid_count": 1, "current_price": 1}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    recent_multi = await db.multi_item_listings.find(
        {"seller_id": current_user.id},
        {"_id": 0, "id": 1, "title": 1, "status": 1, "created_at": 1, "lots": 1}
    ).sort("created_at", -1).limit(5).to_list(5)
    
    for m in recent_multi:
        m["lot_count"] = len(m.pop("lots", []))
    
    return {
        "partner": {
            "company_name": user_doc.get("partner_company_name"),
            "email": user_doc.get("email"),
            "verified_at": user_doc.get("partner_verified_at"),
            "custom_premium_rate": user_doc.get("custom_premium_rate"),
            "platform_fee_paid": user_doc.get("platform_fee_paid", False),
            "partner_fee_paid_at": user_doc.get("partner_fee_paid_at"),
            "stripe_connect_status": user_doc.get("stripe_connect_status"),
        },
        "subscription": subscription_info,
        "stats": {
            "active_listings": active_listings + active_multi,
            "total_listings": total_listings + total_multi,
            "active_single": active_listings,
            "active_multi": active_multi,
            "total_bids_received": total_bids,
        },
        "recent_listings": recent_listings,
        "recent_multi_auctions": recent_multi,
    }




@partners_router.get("/partner/fee-preview")
async def partner_fee_preview(
    hammer_price: float,
    custom_buyer_premium_rate: float = 0.0,
    current_user: User = Depends(get_current_user)
):
    """
    Preview the fee breakdown for a partner listing.
    Shows: Hammer, Buyer Premium, Platform Fee (3%), Stripe Recovery, Total.
    """
    if hammer_price <= 0:
        raise HTTPException(status_code=400, detail="Hammer price must be positive.")
    
    breakdown = calculate_partner_checkout(hammer_price, custom_buyer_premium_rate)
    return breakdown





@partners_router.get("/partner/stats")
async def get_partner_stats_endpoint(current_user: User = Depends(get_current_user)):
    """
    Aggregated partner metrics. Protected — requires admin or verified partner.
    Returns total partners, verified count, pending applications,
    Pro subscribers, trialing users, and listing counts.
    """
    db = get_db()
    is_admin = current_user.role in ("admin", "superadmin")

    if not is_admin:
        user_doc = await db.users.find_one({"id": current_user.id}, {"_id": 0})
        if not user_doc or not user_doc.get("is_partner"):
            raise HTTPException(status_code=403, detail="Partner or admin access required")

    from services.partner_service import get_partner_stats
    stats = await get_partner_stats(db)
    return stats


@partners_router.get("/partner/badge/{user_id}")
async def get_partner_badge(user_id: str):
    """
    Public endpoint returning the badge type for a given user.
    Returns null badge_type if user has no badge.
    """
    db = get_db()
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    from services.partner_service import get_badge_type, is_verified_firm, get_partner_tier
    return {
        "user_id": user_id,
        "badge_type": get_badge_type(user),
        "is_verified_firm": is_verified_firm(user),
        "partner_tier": get_partner_tier(user),
    }
