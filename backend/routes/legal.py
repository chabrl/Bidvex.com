"""
BidVex - Legal Pages CMS
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



legal_router = APIRouter(tags=["Legal"])


@legal_router.get("/site-config/legal-pages")
async def get_legal_pages_public(language: str = "en"):
    """Get legal pages content (public endpoint) - supports both EN and FR"""
    db = get_db()
    try:
        # Get site config from database
        config = await db.site_config.find_one({"type": "legal_pages"})
        
        if not config:
            # Return default empty structure
            return {
                "success": False,
                "message": "Legal pages not configured yet"
            }
        
        pages = config.get("pages", {})
        
        # If language specified, return only that language
        if language and language in ["en", "fr"]:
            result = {}
            for page_key, page_data in pages.items():
                if language in page_data:
                    result[page_key] = page_data[language]
            return {
                "success": True,
                "pages": result,
                "language": language
            }
        
        # Return all languages
        return {
            "success": True,
            "pages": pages
        }
    
    except Exception as e:
        logger.error(f"Error fetching legal pages: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch legal pages")



@legal_router.get("/admin/site-config/legal-pages")
async def get_legal_pages_admin(
    current_user: User = Depends(get_current_user)
):
    """Get legal pages for editing (Admin only)"""
    try:
        # Check admin role
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get site config
        config = await db.site_config.find_one({"type": "legal_pages"})
        
        if not config:
            # Return default structure
            return {
                "success": True,
                "pages": {
                    "how_it_works": {
                        "en": {"title": "How It Works", "content": "", "link_type": "page", "link_value": "/how-it-works"},
                        "fr": {"title": "Comment ça marche", "content": "", "link_type": "page", "link_value": "/how-it-works"}
                    },
                    "privacy_policy": {
                        "en": {"title": "Privacy Policy", "content": "", "link_type": "page", "link_value": "/privacy-policy"},
                        "fr": {"title": "Confidentialité", "content": "", "link_type": "page", "link_value": "/privacy-policy"}
                    },
                    "terms_of_service": {
                        "en": {"title": "Terms & Conditions", "content": "", "link_type": "page", "link_value": "/terms-of-service"},
                        "fr": {"title": "Conditions d'utilisation", "content": "", "link_type": "page", "link_value": "/terms-of-service"}
                    },
                    "support": {
                        "en": {"title": "Contact Support", "content": "", "link_type": "mailto", "link_value": "support@bidvex.com"},
                        "fr": {"title": "Contacter le support", "content": "", "link_type": "mailto", "link_value": "support@bidvex.com"}
                    }
                },
                "updated_at": None,
                "updated_by": None
            }
        
        return {
            "success": True,
            "pages": config.get("pages", {}),
            "updated_at": config.get("updated_at"),
            "updated_by": config.get("updated_by")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching legal pages for admin: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch legal pages")



@legal_router.put("/admin/site-config/legal-pages")
async def update_legal_pages(
    pages: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Update legal pages content (Admin only)"""
    try:
        # Check admin role
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Get existing config for audit log
        existing_config = await db.site_config.find_one({"type": "legal_pages"})
        
        # Update or insert site config
        updated_config = {
            "type": "legal_pages",
            "pages": pages,
            "updated_at": datetime.utcnow(),
            "updated_by": current_user.id,
            "updated_by_email": current_user.email
        }
        
        await db.site_config.update_one(
            {"type": "legal_pages"},
            {"$set": updated_config},
            upsert=True
        )
        
        # Log to admin logs
        await db.admin_logs.insert_one({
            "action": "legal_pages_updated",
            "admin_id": current_user.id,
            "admin_email": current_user.email,
            "details": {
                "pages_updated": list(pages.keys())
            },
            "created_at": datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": "Legal pages updated successfully",
            "updated_at": updated_config["updated_at"].isoformat()
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating legal pages: {e}")
        raise HTTPException(status_code=500, detail="Failed to update legal pages")



@legal_router.post("/admin/site-config/seed-legal-pages")
async def seed_legal_pages(
    current_user: User = Depends(get_current_user)
):
    """Seed legal pages with default content from existing pages (Admin only)"""
    try:
        # Check admin role
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Admin access required")
        
        # Check if already seeded
        existing = await db.site_config.find_one({"type": "legal_pages"})
        if existing and existing.get("pages"):
            return {
                "success": False,
                "message": "Legal pages already seeded. Use PUT endpoint to update."
            }
        
        # Default seed content (will be populated from existing pages)
        seed_content = {
            "type": "legal_pages",
            "pages": {
                "how_it_works": {
                    "en": {
                        "title": "How It Works",
                        "content": "<h1>How BidVex Works</h1><p>BidVex is your premier online auction marketplace...</p>",
                        "link_type": "page",
                        "link_value": "/how-it-works"
                    },
                    "fr": {
                        "title": "Comment ça marche",
                        "content": "<h1>Comment fonctionne BidVex</h1><p>BidVex est votre plateforme d'enchères en ligne...</p>",
                        "link_type": "page",
                        "link_value": "/how-it-works"
                    }
                },
                "privacy_policy": {
                    "en": {
                        "title": "Privacy Policy",
                        "content": "<h1>Privacy Policy</h1><p>Your privacy is important to us...</p>",
                        "link_type": "page",
                        "link_value": "/privacy-policy"
                    },
                    "fr": {
                        "title": "Politique de confidentialité",
                        "content": "<h1>Politique de confidentialité</h1><p>Votre vie privée est importante pour nous...</p>",
                        "link_type": "page",
                        "link_value": "/privacy-policy"
                    }
                },
                "terms_of_service": {
                    "en": {
                        "title": "Terms & Conditions",
                        "content": "<h1>Terms of Service</h1><p>Welcome to BidVex. By using our platform...</p>",
                        "link_type": "page",
                        "link_value": "/terms-of-service"
                    },
                    "fr": {
                        "title": "Conditions d'utilisation",
                        "content": "<h1>Conditions d'utilisation</h1><p>Bienvenue sur BidVex. En utilisant notre plateforme...</p>",
                        "link_type": "page",
                        "link_value": "/terms-of-service"
                    }
                },
                "support": {
                    "en": {
                        "title": "Contact Support",
                        "content": "<h1>Contact Support</h1><p>Need help? Our support team is here for you.</p><p>Email: support@bidvex.com</p>",
                        "link_type": "mailto",
                        "link_value": "support@bidvex.com"
                    },
                    "fr": {
                        "title": "Contacter le support",
                        "content": "<h1>Contacter le support</h1><p>Besoin d'aide? Notre équipe de support est là pour vous.</p><p>Email: support@bidvex.com</p>",
                        "link_type": "mailto",
                        "link_value": "support@bidvex.com"
                    }
                }
            },
            "updated_at": datetime.utcnow(),
            "updated_by": current_user.id,
            "updated_by_email": current_user.email,
            "seeded": True
        }
        
        await db.site_config.insert_one(seed_content)
        
        # Log action
        await db.admin_logs.insert_one({
            "action": "legal_pages_seeded",
            "admin_id": current_user.id,
            "admin_email": current_user.email,
            "created_at": datetime.utcnow()
        })
        
        return {
            "success": True,
            "message": "Legal pages seeded successfully with default content"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error seeding legal pages: {e}")
        raise HTTPException(status_code=500, detail="Failed to seed legal pages")



