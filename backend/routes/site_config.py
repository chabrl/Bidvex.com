"""
BidVex Site Configuration Router
Site mode, branding, homepage layout, hero banners.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, Dict
from datetime import datetime, timezone
from jose import jwt, JWTError
from deps import User
import logging
import uuid
import os

logger = logging.getLogger(__name__)

site_config_router = APIRouter(tags=["Site Configuration"])
security = HTTPBearer(auto_error=False)

_db = None

# Default site configuration
DEFAULT_SITE_CONFIG = {
    "id": "site_config",
    "branding": {
        "logo_url": None,
        "logo_type": "default",
        "primary_color": "#3B82F6",
        "secondary_color": "#10B981",
        "accent_color": "#8B5CF6",
        "surface_color": "#F8FAFC",
        "font_family": "Inter",
    },
    "homepage_layout": {
        "sections": [
            {"id": "hero_banner", "name": "Hero Banner", "visible": True, "order": 0},
            {"id": "homepage_banner", "name": "Banner Carousel", "visible": True, "order": 1},
            {"id": "ending_soon", "name": "Ending Soon", "visible": True, "order": 2},
            {"id": "featured", "name": "Featured Auctions", "visible": True, "order": 3},
            {"id": "browse_items", "name": "Browse Individual Items", "visible": True, "order": 4},
            {"id": "new_listings", "name": "New Listings", "visible": True, "order": 5},
            {"id": "recently_sold", "name": "Recently Sold", "visible": True, "order": 6},
            {"id": "recently_viewed", "name": "Recently Viewed", "visible": True, "order": 7},
            {"id": "hot_items", "name": "Hot Items", "visible": True, "order": 8},
            {"id": "top_sellers", "name": "Top Sellers", "visible": True, "order": 9},
            {"id": "how_it_works", "name": "How It Works", "visible": True, "order": 10},
            {"id": "trust_features", "name": "Trust Features", "visible": True, "order": 11},
        ]
    },
    "hero_banners": [],
    "updated_at": None,
    "updated_by": None,
}


def set_site_config_db(db_instance):
    global _db
    _db = db_instance


def get_db():
    if _db is None:
        raise RuntimeError("Site config database not initialized")
    return _db


async def _require_admin(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify user has admin role."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    db = get_db()
    jwt_secret = os.environ.get("JWT_SECRET")
    try:
        payload = jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
        if not user_doc:
            raise HTTPException(status_code=401, detail="User not found")
        current_user = User(**user_doc)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    if not current_user.email.endswith("@bidvex.com") and current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


async def _get_site_config():
    db = get_db()
    config = await db.site_config.find_one({"id": "site_config"}, {"_id": 0})
    if not config:
        config = {**DEFAULT_SITE_CONFIG, "updated_at": datetime.now(timezone.utc).isoformat()}
        await db.site_config.insert_one(config)
    return config



# ========== PUBLIC SITE CONFIG ==========

@site_config_router.get("/site-config")
async def get_public_site_config():
    try:
        db = get_db()
        config = await _get_site_config()
        active_banners = await db.hero_banners.find({"active": True}, {"_id": 0}).sort("order", 1).to_list(20)
        return {
            "branding": config.get("branding", DEFAULT_SITE_CONFIG["branding"]),
            "homepage_layout": config.get("homepage_layout", DEFAULT_SITE_CONFIG["homepage_layout"]),
            "hero_banners": active_banners,
        }
    except Exception as e:
        logger.error(f"site-config DB error, returning defaults: {e}")
        return {
            "branding": DEFAULT_SITE_CONFIG["branding"],
            "homepage_layout": DEFAULT_SITE_CONFIG["homepage_layout"],
            "hero_banners": [],
        }


@site_config_router.get("/admin/site-config")
async def get_admin_site_config(current_user: User = Depends(_require_admin)):
    db = get_db()
    config = await _get_site_config()
    banners = await db.hero_banners.find({}, {"_id": 0}).sort("order", 1).to_list(100)
    return {**config, "hero_banners": banners}


@site_config_router.put("/admin/site-config/branding")
async def update_site_branding(branding_data: Dict, current_user: User = Depends(_require_admin)):
    db = get_db()
    current_config = await _get_site_config()
    old_branding = current_config.get("branding", {}).copy()
    allowed_fields = ["logo_url", "logo_type", "primary_color", "secondary_color", "accent_color", "surface_color", "font_family"]
    color_fields = ["primary_color", "secondary_color", "accent_color", "surface_color"]
    for field in color_fields:
        if field in branding_data:
            color = branding_data[field]
            if color and not (color.startswith("#") and len(color) in [4, 7]):
                raise HTTPException(status_code=400, detail=f"Invalid color format for {field}")
    valid_fonts = ["Inter", "Montserrat", "Poppins", "Roboto", "Open Sans", "Lato", "Nunito"]
    if "font_family" in branding_data and branding_data["font_family"] not in valid_fonts:
        raise HTTPException(status_code=400, detail=f"Invalid font. Choose from: {', '.join(valid_fonts)}")
    new_branding = {**old_branding}
    for field in allowed_fields:
        if field in branding_data:
            new_branding[field] = branding_data[field]
    await db.site_config.update_one(
        {"id": "site_config"},
        {"$set": {"branding": new_branding, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": current_user.email}},
        upsert=True,
    )
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "BRANDING_UPDATE", "admin_id": current_user.id,
        "admin_email": current_user.email, "target_type": "site_config", "target_id": "branding",
        "details": f"Updated branding: {list(branding_data.keys())}",
        "old_value": old_branding, "new_value": new_branding,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return await _get_site_config()


@site_config_router.put("/admin/site-config/homepage-layout")
async def update_homepage_layout(layout_data: Dict, current_user: User = Depends(_require_admin)):
    db = get_db()
    current_config = await _get_site_config()
    old_layout = current_config.get("homepage_layout", {}).copy()
    if "sections" not in layout_data:
        raise HTTPException(status_code=400, detail="sections field is required")
    sections = layout_data["sections"]
    if not isinstance(sections, list):
        raise HTTPException(status_code=400, detail="sections must be a list")
    valid_section_ids = [s["id"] for s in DEFAULT_SITE_CONFIG["homepage_layout"]["sections"]]
    for section in sections:
        if not isinstance(section, dict):
            raise HTTPException(status_code=400, detail="Each section must be an object")
        if "id" not in section or "visible" not in section:
            raise HTTPException(status_code=400, detail="Each section must have 'id' and 'visible' fields")
        if section["id"] not in valid_section_ids:
            raise HTTPException(status_code=400, detail=f"Invalid section id: {section['id']}")
    new_layout = {"sections": sections}
    await db.site_config.update_one(
        {"id": "site_config"},
        {"$set": {"homepage_layout": new_layout, "updated_at": datetime.now(timezone.utc).isoformat(), "updated_by": current_user.email}},
        upsert=True,
    )
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "HOMEPAGE_LAYOUT_UPDATE", "admin_id": current_user.id,
        "admin_email": current_user.email, "target_type": "site_config", "target_id": "homepage_layout",
        "details": "Updated homepage section visibility/order",
        "old_value": old_layout, "new_value": new_layout,
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return await _get_site_config()


# ========== HERO BANNER CRUD ==========

@site_config_router.get("/admin/hero-banners")
async def get_hero_banners(current_user: User = Depends(_require_admin)):
    db = get_db()
    return await db.hero_banners.find({}, {"_id": 0}).sort("order", 1).to_list(100)


@site_config_router.post("/admin/hero-banners")
async def create_hero_banner(banner_data: Dict, current_user: User = Depends(_require_admin)):
    db = get_db()
    last_banner = await db.hero_banners.find_one(sort=[("order", -1)])
    next_order = (last_banner.get("order", 0) + 1) if last_banner else 0
    banner = {
        "id": str(uuid.uuid4()),
        "title_en": banner_data.get("title_en", banner_data.get("title", "")),
        "title_fr": banner_data.get("title_fr", ""),
        "subtitle_en": banner_data.get("subtitle_en", banner_data.get("subtitle", "")),
        "subtitle_fr": banner_data.get("subtitle_fr", ""),
        "cta_text_en": banner_data.get("cta_text_en", banner_data.get("cta_text", "Learn More")),
        "cta_text_fr": banner_data.get("cta_text_fr", "En savoir plus"),
        "title": banner_data.get("title", banner_data.get("title_en", "")),
        "subtitle": banner_data.get("subtitle", banner_data.get("subtitle_en", "")),
        "cta_text": banner_data.get("cta_text", banner_data.get("cta_text_en", "Learn More")),
        "image_desktop": banner_data.get("image_desktop"),
        "image_mobile": banner_data.get("image_mobile"),
        "cta_link": banner_data.get("cta_link", "/marketplace"),
        "title_color": banner_data.get("title_color", "#FFFFFF"),
        "subtitle_color": banner_data.get("subtitle_color", "#FFFFFF"),
        "button_color": banner_data.get("button_color", "#FFFFFF"),
        "button_text_color": banner_data.get("button_text_color", "#000000"),
        "text_color": banner_data.get("text_color", "#FFFFFF"),
        "font_family": banner_data.get("font_family", "Inter"),
        "title_font_size": banner_data.get("title_font_size", "48px"),
        "subtitle_font_size": banner_data.get("subtitle_font_size", "18px"),
        "overlay_color": banner_data.get("overlay_color", "#000000"),
        "overlay_opacity": banner_data.get("overlay_opacity", 0.4),
        "active": banner_data.get("active", True),
        "start_date": banner_data.get("start_date"),
        "end_date": banner_data.get("end_date"),
        "order": next_order,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user.email,
    }
    await db.hero_banners.insert_one(banner)
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "HERO_BANNER_CREATE", "admin_id": current_user.id,
        "admin_email": current_user.email, "target_type": "hero_banner", "target_id": banner["id"],
        "details": f"Created hero banner: {banner['title']}",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    banner.pop("_id", None)
    return banner


@site_config_router.put("/admin/hero-banners/{banner_id}")
async def update_hero_banner(banner_id: str, banner_data: Dict, current_user: User = Depends(_require_admin)):
    db = get_db()
    existing = await db.hero_banners.find_one({"id": banner_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Banner not found")
    allowed_fields = [
        "title_en", "title_fr", "subtitle_en", "subtitle_fr", "cta_text_en", "cta_text_fr",
        "title", "subtitle", "cta_text", "image_desktop", "image_mobile", "cta_link",
        "title_color", "subtitle_color", "button_color", "button_text_color", "text_color",
        "font_family", "title_font_size", "subtitle_font_size", "overlay_color", "overlay_opacity",
        "active", "start_date", "end_date", "order",
    ]
    update_data = {k: v for k, v in banner_data.items() if k in allowed_fields}
    update_data["updated_at"] = datetime.now(timezone.utc).isoformat()
    update_data["updated_by"] = current_user.email
    await db.hero_banners.update_one({"id": banner_id}, {"$set": update_data})
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "HERO_BANNER_UPDATE", "admin_id": current_user.id,
        "admin_email": current_user.email, "target_type": "hero_banner", "target_id": banner_id,
        "details": f"Updated hero banner: {list(update_data.keys())}",
        "old_value": {k: existing.get(k) for k in update_data if k in existing},
        "new_value": update_data, "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return await db.hero_banners.find_one({"id": banner_id}, {"_id": 0})


@site_config_router.delete("/admin/hero-banners/{banner_id}")
async def delete_hero_banner(banner_id: str, current_user: User = Depends(_require_admin)):
    db = get_db()
    existing = await db.hero_banners.find_one({"id": banner_id})
    if not existing:
        raise HTTPException(status_code=404, detail="Banner not found")
    await db.hero_banners.delete_one({"id": banner_id})
    await db.admin_logs.insert_one({
        "id": str(uuid.uuid4()), "action": "HERO_BANNER_DELETE", "admin_id": current_user.id,
        "admin_email": current_user.email, "target_type": "hero_banner", "target_id": banner_id,
        "details": f"Deleted hero banner: {existing.get('title')}",
        "deleted_banner": {k: v for k, v in existing.items() if k != "_id"},
        "created_at": datetime.now(timezone.utc).isoformat(),
    })
    return {"message": "Banner deleted successfully"}
