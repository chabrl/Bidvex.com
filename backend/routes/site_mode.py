"""
BidVex - Site Mode & Maintenance
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
    SiteModeUpdate, EmailSubscription,
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

from pydantic import EmailStr

site_mode_router = APIRouter(tags=["Site Mode"])


@site_mode_router.get("/site-mode")
async def get_site_mode():
    """
    Get current site mode (public endpoint).
    Returns: live, maintenance, or coming_soon
    """
    db = get_db()
    try:
        settings = await db.site_settings.find_one({"setting_id": "site_mode"})
        if not settings:
            # Default to live mode
            return {
                "mode": "live",
                "message": None,
                "expected_back": None,
                "social_links": None,
                "updated_at": None
            }
        return {
            "mode": settings.get("mode", "live"),
            "message": settings.get("message"),
            "expected_back": settings.get("expected_back"),
            "social_links": settings.get("social_links"),
            "updated_at": settings.get("updated_at")
        }
    except Exception as e:
        logger.error(f"Error fetching site mode: {e}")
        return {"mode": "live", "message": None, "expected_back": None, "social_links": None}



@site_mode_router.put("/admin/site-mode")
async def update_site_mode(data: SiteModeUpdate, current_user: User = Depends(get_current_user)):
    """
    Update site mode (admin only).
    Valid modes: live, maintenance, coming_soon
    """
    db = get_db()
    # FIX: role-based admin check (was brittle @bidvex.com email check which
    # locked out primary admin charbel911@gmail.com).
    if getattr(current_user, "role", None) not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    if data.mode not in ["live", "maintenance", "coming_soon"]:
        raise HTTPException(status_code=400, detail="Invalid mode. Use: live, maintenance, coming_soon")
    
    try:
        update_data = {
            "setting_id": "site_mode",
            "mode": data.mode,
            "message": data.message,
            "message_fr": data.message_fr,
            "expected_back": data.expected_back,
            "scheduled_start": data.scheduled_start,
            "scheduled_end": data.scheduled_end,
            "social_links": data.social_links,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": current_user.email
        }
        
        await db.site_settings.update_one(
            {"setting_id": "site_mode"},
            {"$set": update_data},
            upsert=True
        )
        
        # Log the action
        await db.admin_logs.insert_one({
            "log_id": f"log-{uuid.uuid4()}",
            "action": "site_mode_changed",
            "admin_email": current_user.email,
            "details": f"Changed site mode to: {data.mode}",
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return {"success": True, "mode": data.mode, "message": "Site mode updated successfully"}
    except Exception as e:
        logger.error(f"Error updating site mode: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@site_mode_router.post("/subscribe")
async def subscribe_email(data: EmailSubscription, request: Request):
    """
    Subscribe an email to launch notifications (public endpoint).
    Used on maintenance/coming soon page.
    """
    db = get_db()
    try:
        # Check if already subscribed
        existing = await db.launch_subscribers.find_one({"email": data.email.lower()})
        if existing:
            return {"success": True, "message": "You're already subscribed! We'll notify you when we launch."}
        
        # Get client IP
        client_ip = request.client.host if request.client else None
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        
        # Save subscriber
        subscriber = {
            "subscriber_id": f"sub-{uuid.uuid4()}",
            "email": data.email.lower(),
            "subscribed_at": datetime.now(timezone.utc).isoformat(),
            "ip_address": client_ip,
            "source": "coming_soon_page",
            "notified": False
        }
        
        await db.launch_subscribers.insert_one(subscriber)
        
        return {
            "success": True,
            "message": "Thank you! We will notify you when BidVex is live."
        }
    except Exception as e:
        logger.error(f"Error subscribing email: {e}")
        raise HTTPException(status_code=500, detail="Failed to subscribe. Please try again.")



@site_mode_router.get("/admin/subscribers")
async def get_subscribers(
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=100),
    search: str = Query(None)
):
    """
    Get all launch subscribers (admin only).
    """
    db = get_db()
    if getattr(current_user, "role", None) not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        query = {}
        if search:
            query["email"] = {"$regex": search, "$options": "i"}
        
        total = await db.launch_subscribers.count_documents(query)
        skip = (page - 1) * limit
        
        subscribers = await db.launch_subscribers.find(
            query,
            {"_id": 0}
        ).sort("subscribed_at", -1).skip(skip).limit(limit).to_list(limit)
        
        return {
            "success": True,
            "subscribers": subscribers,
            "total": total,
            "page": page,
            "pages": (total + limit - 1) // limit
        }
    except Exception as e:
        logger.error(f"Error fetching subscribers: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@site_mode_router.get("/admin/subscribers/export")
async def export_subscribers(current_user: User = Depends(get_current_user)):
    """
    Export all subscribers as CSV (admin only).
    """
    db = get_db()
    if getattr(current_user, "role", None) not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        subscribers = await db.launch_subscribers.find({}, {"_id": 0}).to_list(10000)
        
        # Build CSV content
        csv_lines = ["email,subscribed_at,ip_address,source,notified"]
        for sub in subscribers:
            csv_lines.append(
                f"{sub.get('email', '')},{sub.get('subscribed_at', '')},{sub.get('ip_address', '')},{sub.get('source', '')},{sub.get('notified', False)}"
            )
        
        return {
            "success": True,
            "csv": "\n".join(csv_lines),
            "total": len(subscribers),
            "filename": f"bidvex_subscribers_{datetime.now().strftime('%Y%m%d')}.csv"
        }
    except Exception as e:
        logger.error(f"Error exporting subscribers: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@site_mode_router.delete("/admin/subscribers/{subscriber_id}")
async def delete_subscriber(subscriber_id: str, current_user: User = Depends(get_current_user)):
    """
    Delete a subscriber (admin only).
    """
    db = get_db()
    if getattr(current_user, "role", None) not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        result = await db.launch_subscribers.delete_one({"subscriber_id": subscriber_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Subscriber not found")
        
        return {"success": True, "message": "Subscriber deleted"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting subscriber: {e}")
        raise HTTPException(status_code=500, detail=str(e))



@site_mode_router.get("/admin/subscribers/stats")
async def get_subscriber_stats(current_user: User = Depends(get_current_user)):
    """
    Get subscriber statistics (admin only).
    """
    db = get_db()
    if getattr(current_user, "role", None) not in ("admin", "superadmin"):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    try:
        total = await db.launch_subscribers.count_documents({})
        
        # Get subscribers by day (last 7 days)
        now = datetime.now(timezone.utc)
        daily_counts = []
        for i in range(6, -1, -1):
            day = now - timedelta(days=i)
            day_start = day.replace(hour=0, minute=0, second=0, microsecond=0)
            day_end = day_start + timedelta(days=1)
            
            count = await db.launch_subscribers.count_documents({
                "subscribed_at": {
                    "$gte": day_start.isoformat(),
                    "$lt": day_end.isoformat()
                }
            })
            daily_counts.append({
                "date": day_start.strftime("%b %d"),
                "count": count
            })
        
        # Today's count
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = await db.launch_subscribers.count_documents({
            "subscribed_at": {"$gte": today_start.isoformat()}
        })
        
        return {
            "success": True,
            "total": total,
            "today": today_count,
            "daily_trend": daily_counts
        }
    except Exception as e:
        logger.error(f"Error fetching subscriber stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Use environment variable for API key (already defined at line 9308)


