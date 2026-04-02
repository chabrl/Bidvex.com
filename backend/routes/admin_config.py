"""
BidVex - Admin Configuration (Settings, Templates, Banners, Logs)
Auto-extracted from server.py during P2 refactoring.
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File, Form, WebSocket, WebSocketDisconnect
from deps import get_db, get_current_user, get_current_user_optional, require_admin, User
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
    BannerCreate,
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



admin_config_router = APIRouter(tags=["Admin Config"])


@admin_config_router.get("/marketplace/feature-flags")
async def get_public_feature_flags():
    """
    Public endpoint to get marketplace feature flags.
    Used by frontend to conditionally show/hide features like Buy Now and Multi-Lot access.
    Only exposes safe, non-sensitive settings.
    """
    db = get_db()
    settings = await get_marketplace_settings(db)
    return {
        "enable_buy_now": settings.get("enable_buy_now", True),
        "enable_anti_sniping": settings.get("enable_anti_sniping", True),
        "anti_sniping_window_minutes": settings.get("anti_sniping_window_minutes", 2),
        "minimum_bid_increment": settings.get("minimum_bid_increment", 1.0),
        "allow_all_users_multi_lot": settings.get("allow_all_users_multi_lot", True),
    }



@admin_config_router.get("/admin/marketplace-settings")
async def get_admin_marketplace_settings(current_user: User = Depends(require_admin)):
    """Get current marketplace settings (admin only)."""
    db = get_db()
    settings = await get_marketplace_settings(db)
    return settings



@admin_config_router.put("/admin/marketplace-settings")
async def update_marketplace_settings(
    settings_data: Dict,
    current_user: User = Depends(require_admin)
):
    """Update marketplace settings (admin only). Changes take effect immediately."""
    db = get_db()
    # Get current settings for comparison
    current_settings = await get_marketplace_settings(db)
    
    # Validate settings with type and range checks
    allowed_fields = {
        "allow_all_users_multi_lot": {"type": bool},
        "require_approval_new_sellers": {"type": bool}, 
        "max_active_auctions_per_user": {"type": int, "min": 1, "max": 100},
        "max_lots_per_auction": {"type": int, "min": 1, "max": 500},
        "minimum_bid_increment": {"type": float, "min": 1.0},
        "enable_anti_sniping": {"type": bool},
        "anti_sniping_window_minutes": {"type": int, "min": 1, "max": 60},
        "enable_buy_now": {"type": bool}
    }
    
    # Filter and validate fields
    update_data = {}
    changes = []
    
    for key, value in settings_data.items():
        if key not in allowed_fields:
            continue
            
        field_rules = allowed_fields[key]
        expected_type = field_rules["type"]
        
        # Type validation
        if expected_type == bool and not isinstance(value, bool):
            raise HTTPException(status_code=400, detail=f"{key} must be a boolean")
        elif expected_type == int:
            if not isinstance(value, int) or isinstance(value, bool):
                raise HTTPException(status_code=400, detail=f"{key} must be an integer")
            if "min" in field_rules and value < field_rules["min"]:
                raise HTTPException(status_code=400, detail=f"{key} must be at least {field_rules['min']}")
            if "max" in field_rules and value > field_rules["max"]:
                raise HTTPException(status_code=400, detail=f"{key} must be at most {field_rules['max']}")
        elif expected_type == float:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise HTTPException(status_code=400, detail=f"{key} must be a number")
            if "min" in field_rules and value < field_rules["min"]:
                raise HTTPException(status_code=400, detail=f"{key} must be at least {field_rules['min']}")
        
        # Track changes for audit
        old_value = current_settings.get(key)
        if old_value != value:
            changes.append({
                "field": key,
                "old_value": old_value,
                "new_value": value
            })
        
        update_data[key] = value
    
    if not update_data:
        return current_settings  # No changes to make
    
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = current_user.email
    
    # Upsert settings
    await db.settings.update_one(
        {"id": "marketplace_settings"},
        {"$set": update_data},
        upsert=True
    )
    
    # Log each change with detailed audit trail
    for change in changes:
        log_entry = {
            "id": str(uuid.uuid4()),
            "action": "MARKETPLACE_SETTINGS_UPDATE",
            "admin_id": current_user.id,
            "admin_email": current_user.email,
            "target_type": "settings",
            "target_id": "marketplace_settings",
            "field_changed": change["field"],
            "old_value": str(change["old_value"]),
            "new_value": str(change["new_value"]),
            "details": f"Changed {change['field']}: {change['old_value']} → {change['new_value']}",
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.admin_logs.insert_one(log_entry)
    
    logger.info(f"📋 Marketplace settings updated by {current_user.email}: {[c['field'] for c in changes]}")
    
    # Return updated settings
    return await get_marketplace_settings(db)




@admin_config_router.post("/admin/marketplace-settings/restore-defaults")
async def restore_marketplace_defaults(current_user: User = Depends(require_admin)):
    """Restore marketplace settings to factory defaults (admin only)."""
    db = get_db()
    # Get current settings before reset for audit
    current_settings = await get_marketplace_settings(db)
    
    # Define hard-coded system defaults
    system_defaults = {
        "id": "marketplace_settings",
        "allow_all_users_multi_lot": True,
        "require_approval_new_sellers": False,
        "max_active_auctions_per_user": 20,
        "max_lots_per_auction": 50,
        "minimum_bid_increment": 1.0,
        "enable_anti_sniping": True,
        "anti_sniping_window_minutes": 2,
        "enable_buy_now": True,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": current_user.email
    }
    
    # Replace all settings with defaults
    await db.settings.replace_one(
        {"id": "marketplace_settings"},
        system_defaults,
        upsert=True
    )
    
    # Log the reset action with detailed before/after
    log_entry = {
        "id": str(uuid.uuid4()),
        "action": "MARKETPLACE_SETTINGS_RESET",
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "target_type": "settings",
        "target_id": "marketplace_settings",
        "details": "Restored all marketplace settings to factory defaults",
        "previous_settings": {k: v for k, v in current_settings.items() if k != "_id"},
        "new_settings": {k: v for k, v in system_defaults.items() if k != "_id"},
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_logs.insert_one(log_entry)
    
    logger.info(f"⚠️ Marketplace settings RESET to defaults by {current_user.email}")
    
    return system_defaults



@admin_config_router.get("/admin/email-templates")
async def get_admin_email_templates(current_user: User = Depends(require_admin)):
    """Get all email templates with categories (admin only)."""
    db = get_db()
    templates = await get_email_templates(db)
    
    # Count templates per category and build response
    template_dict = templates.get("templates", {})
    total_count = len(template_dict)
    
    # Group templates by category
    categorized = {}
    for cat_key, cat_info in EMAIL_TEMPLATE_CATEGORIES.items():
        cat_templates = []
        for base_key in cat_info["keys"]:
            en_key = f"{base_key}_en"
            fr_key = f"{base_key}_fr"
            if en_key in template_dict or fr_key in template_dict:
                cat_templates.append({
                    "key": base_key,
                    "name": base_key.replace("_", " ").title(),
                    "en_id": template_dict.get(en_key, ""),
                    "fr_id": template_dict.get(fr_key, ""),
                })
        
        categorized[cat_key] = {
            **cat_info,
            "templates": cat_templates,
            "count": len(cat_templates)
        }
    
    return {
        "id": templates.get("id"),
        "categories": categorized,
        "total_templates": total_count,
        "updated_at": templates.get("updated_at"),
        "updated_by": templates.get("updated_by")
    }



@admin_config_router.put("/admin/email-templates")
async def update_email_templates(
    updates: Dict[str, Any],
    current_user: User = Depends(require_admin)
):
    """Update email template IDs (admin only)."""
    db = get_db()
    templates = await get_email_templates(db)
    current_templates = templates.get("templates", {})
    
    # Validate and update templates
    updated_keys = []
    for key, new_id in updates.get("templates", {}).items():
        # Validate SendGrid template ID format (d- followed by 32 hex chars = 34 total)
        import re
        if new_id and not re.match(r'^d-[a-f0-9]{32}$', new_id):
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid template ID format for '{key}'. Must be 'd-' followed by 32 hexadecimal characters."
            )
        
        old_id = current_templates.get(key, "")
        if old_id != new_id:
            current_templates[key] = new_id
            updated_keys.append(key)
            
            # Log the change to admin action logs
            await db.admin_action_logs.insert_one({
                "id": str(uuid.uuid4()),
                "admin_id": current_user.id,
                "admin_email": current_user.email,
                "action": "email_template_update",
                "target_type": "email_template",
                "target_id": key,
                "old_value": old_id,
                "new_value": new_id,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
    
    # Update database
    await db.email_settings.update_one(
        {"id": "email_templates"},
        {
            "$set": {
                "templates": current_templates,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "updated_by": current_user.email
            }
        },
        upsert=True
    )
    
    return {
        "message": f"Updated {len(updated_keys)} template(s)",
        "updated_keys": updated_keys,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "updated_by": current_user.email
    }



@admin_config_router.get("/admin/email-templates/search")
async def search_email_templates(
    q: str = "",
    current_user: User = Depends(require_admin)
):
    """Search email templates by name or ID (admin only)."""
    db = get_db()
    templates = await get_email_templates(db)
    template_dict = templates.get("templates", {})
    
    query = q.lower()
    results = []
    
    for key, template_id in template_dict.items():
        if query in key.lower() or query in template_id.lower():
            # Find category for this template
            category = "unknown"
            base_key = "_".join(key.split("_")[:-1])  # Remove language suffix
            for cat_key, cat_info in EMAIL_TEMPLATE_CATEGORIES.items():
                if base_key in cat_info["keys"]:
                    category = cat_key
                    break
            
            results.append({
                "key": key,
                "template_id": template_id,
                "category": category,
                "name": key.replace("_", " ").title()
            })
    
    return {
        "query": q,
        "count": len(results),
        "results": results
    }



@admin_config_router.get("/admin/email-templates/audit-log")
async def get_email_template_audit_log(
    limit: int = 50,
    current_user: User = Depends(require_admin)
):
    """Get audit log of email template changes (admin only)."""
    db = get_db()
    logs = await db.admin_action_logs.find(
        {"action": "email_template_update"},
        {"_id": 0}
    ).sort("created_at", -1).limit(limit).to_list(limit)
    
    return logs



@admin_config_router.post("/admin/logs")
async def admin_create_log(data: Dict[str, Any], current_user: User = Depends(require_admin)):
    db = get_db()
    log = {
        "id": str(uuid.uuid4()),
        "admin_id": current_user.id,
        "admin_email": current_user.email,
        "action": data.get("action"),
        "target_type": data.get("target_type"),
        "target_id": data.get("target_id"),
        "details": data.get("details", ""),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admin_logs.insert_one(log)
    return log



@admin_config_router.get("/admin/logs")
async def admin_get_logs(action_type: str = None, limit: int = 100, current_user: User = Depends(require_admin)):
    db = get_db()
    query = {}
    if action_type:
        query["action"] = action_type
    
    logs = await db.admin_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit).to_list(limit)
    return logs

# PLATFORM ANNOUNCEMENTS


@admin_config_router.get("/admin/announcements")
async def admin_get_announcements(current_user: User = Depends(require_admin)):
    db = get_db()
    announcements = await db.announcements.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return announcements



@admin_config_router.post("/admin/announcements")
async def admin_create_announcement(data: Dict[str, Any], current_user: User = Depends(require_admin)):
    db = get_db()
    announcement = {
        "id": str(uuid.uuid4()),
        "title": data.get("title"),
        "message": data.get("message"),
        "target_audience": data.get("target_audience", "all"),
        "status": "active",
        "scheduled_for": data.get("scheduled_for"),
        "created_by": current_user.id,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.announcements.insert_one(announcement)
    return announcement





@admin_config_router.get("/announcements/active")
async def get_active_announcements():
    """Public endpoint: Get all active announcements for display"""
    db = get_db()
    current_time = datetime.now(timezone.utc)
    
    # Query supports both 'status': 'active' and 'is_active': True formats
    announcements = await db.announcements.find({
        "$or": [
            {"status": "active"},
            {"is_active": True}
        ]
    }, {"_id": 0}).sort("created_at", -1).to_list(10)
    
    return announcements




@admin_config_router.delete("/admin/announcements/{announcement_id}")
async def admin_delete_announcement(announcement_id: str, current_user: User = Depends(require_admin)):
    db = get_db()
    await db.announcements.delete_one({"id": announcement_id})
    return {"message": "Announcement deleted"}



@admin_config_router.get("/admin/banners")
async def get_admin_banners(current_user: User = Depends(require_admin)):
    """Get all banners (admin only)"""
    db = get_db()
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    banners = await db.banners.find({}, {"_id": 0}).sort("priority", -1).to_list(100)
    return {"banners": banners}



@admin_config_router.post("/admin/banners")
async def create_admin_banner(banner_data: BannerCreate, current_user: User = Depends(require_admin)):
    """Create a new banner (admin only)"""
    db = get_db()
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    banner = {
        "id": str(uuid.uuid4()),
        "title": banner_data.title,
        "image_url": banner_data.image_url,
        "cta_text": banner_data.cta_text,
        "cta_url": banner_data.cta_url,
        "is_active": banner_data.is_active,
        "start_date": banner_data.start_date,
        "end_date": banner_data.end_date,
        "priority": banner_data.priority,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.banners.insert_one(banner)
    banner.pop("_id", None)
    return {"message": "Banner created successfully", "banner": banner}



@admin_config_router.put("/admin/banners/{banner_id}")
async def update_admin_banner(banner_id: str, banner_data: dict, current_user: User = Depends(require_admin)):
    """Update a banner (admin only)"""
    db = get_db()
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    existing = await db.banners.find_one({"id": banner_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Banner not found")
    
    # Remove fields that shouldn't be updated
    banner_data.pop("id", None)
    banner_data.pop("_id", None)
    banner_data.pop("created_at", None)
    banner_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    
    await db.banners.update_one({"id": banner_id}, {"$set": banner_data})
    return {"message": "Banner updated successfully"}



@admin_config_router.delete("/admin/banners/{banner_id}")
async def delete_admin_banner(banner_id: str, current_user: User = Depends(require_admin)):
    """Delete a banner (admin only)"""
    db = get_db()
    if current_user.role != 'admin':
        raise HTTPException(status_code=403, detail="Admin access required")
    
    result = await db.banners.delete_one({"id": banner_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Banner not found")
    
    return {"message": "Banner deleted successfully"}



@admin_config_router.get("/banners/active")
async def get_active_banners():
    """Get active banners for homepage display (supports both carousel and hero banners)"""
    db = get_db()
    now = datetime.now(timezone.utc).isoformat()
    
    # Query for active banners from banners collection
    query = {
        "is_active": True,
        "$or": [
            {"start_date": None, "end_date": None},
            {"start_date": None, "end_date": {"$gte": now}},
            {"start_date": {"$lte": now}, "end_date": None},
            {"start_date": {"$lte": now}, "end_date": {"$gte": now}}
        ]
    }
    
    banners = await db.banners.find(query, {"_id": 0}).sort("priority", -1).to_list(10)
    
    # Also query hero_banners collection for active banners
    hero_query = {
        "active": True,
        "$or": [
            {"start_date": None, "end_date": None},
            {"start_date": None, "end_date": {"$gte": now}},
            {"start_date": {"$lte": now}, "end_date": None},
            {"start_date": {"$lte": now}, "end_date": {"$gte": now}}
        ]
    }
    
    hero_banners = await db.hero_banners.find(hero_query, {"_id": 0}).sort("order", 1).to_list(10)
    
    # Transform hero_banners to consistent format with styling
    for banner in hero_banners:
        # Map fields for consistency
        banner["is_active"] = banner.get("active", True)
        banner["image_url"] = banner.get("image_desktop") or banner.get("image_mobile")
        banner["priority"] = banner.get("order", 0)
        # Ensure styling fields have defaults
        banner["title_color"] = banner.get("title_color", "#FFFFFF")
        banner["subtitle_color"] = banner.get("subtitle_color", "#FFFFFF")
        banner["button_color"] = banner.get("button_color", "#FFFFFF")
        banner["button_text_color"] = banner.get("button_text_color", "#000000")
        banner["text_color"] = banner.get("text_color", "#FFFFFF")
        banner["font_family"] = banner.get("font_family", "Inter")
        banner["title_font_size"] = banner.get("title_font_size", "48px")
        banner["subtitle_font_size"] = banner.get("subtitle_font_size", "18px")
        banner["overlay_color"] = banner.get("overlay_color", "#000000")
        banner["overlay_opacity"] = banner.get("overlay_opacity", 0.4)
    
    # Combine both sources, prioritizing hero_banners
    all_banners = hero_banners + banners
    
    return {"banners": all_banners, "hero_banners": hero_banners}



