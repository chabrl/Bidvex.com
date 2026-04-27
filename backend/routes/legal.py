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
        
        pages = config.get("pages", {}) or {}
        
        # If language specified, return only that language
        if language and language in ["en", "fr"]:
            result = {}
            for page_key, page_data in pages.items():
                # Defensive: page_data may be a dict {en, fr} OR a string OR a bool
                # (legacy data). Only descend if it's a dict containing the language.
                if isinstance(page_data, dict) and language in page_data:
                    result[page_key] = page_data[language]
                elif isinstance(page_data, str):
                    # Legacy single-language entry — return as-is for any language
                    result[page_key] = page_data
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
        # Never 500 the footer — return empty pages so the UI can render gracefully
        return {
            "success": False,
            "pages": {},
            "message": "Legal pages temporarily unavailable",
        }



@legal_router.get("/admin/site-config/legal-pages")
async def get_legal_pages_admin(
    current_user: User = Depends(get_current_user)
):
    """Get legal pages for editing (Admin only)"""
    try:
        # Check admin role
        if current_user.role not in ("admin", "super_admin"):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        db = get_db()
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
        if current_user.role not in ("admin", "super_admin"):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        db = get_db()
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
        if current_user.role not in ("admin", "super_admin"):
            raise HTTPException(status_code=403, detail="Admin access required")
        
        db = get_db()
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





# ─── Cookie Consent i18n (Law 25 - Quebec Privacy) ─────────────────

COOKIE_CONSENT_STRINGS = {
    "en": {
        "banner_title": "Cookie Consent",
        "banner_text": (
            "We use cookies and similar technologies to enhance your browsing experience, "
            "analyze site traffic, and personalize content. In accordance with Quebec's "
            "Law 25 (Act to modernize legislative provisions respecting the protection of "
            "personal information), we require your explicit consent before placing non-essential "
            "cookies on your device."
        ),
        "accept_all": "Accept All Cookies",
        "refuse_all": "Refuse All",
        "customize": "Customize Preferences",
        "privacy_policy_link": "/privacy-policy",
        "privacy_policy_text": "Read our Privacy Policy",
        "categories": {
            "strictly_necessary": {
                "name": "Strictly Necessary",
                "description": (
                    "These cookies are essential for the website to function correctly. "
                    "They enable core features such as authentication, session management, "
                    "and security. They cannot be disabled."
                ),
                "required": True,
            },
            "functionality": {
                "name": "Functionality",
                "description": (
                    "These cookies enable enhanced features such as remembering your "
                    "language preferences, saved searches, and personalized settings."
                ),
                "required": False,
            },
            "analytics": {
                "name": "Analytics",
                "description": (
                    "These cookies help us understand how visitors interact with the "
                    "website by collecting anonymous usage data to improve our services."
                ),
                "required": False,
            },
            "marketing": {
                "name": "Marketing",
                "description": (
                    "These cookies are used to deliver personalized advertisements "
                    "and track campaign performance across platforms."
                ),
                "required": False,
            },
        },
        "law25_notice": (
            "Under Quebec's Law 25, you have the right to know what personal information "
            "we collect, to access and rectify it, and to withdraw your consent at any time. "
            "For questions, contact our Privacy Officer at privacy@bidvex.ca."
        ),
        "privacy_by_default": (
            "By default, only Strictly Necessary cookies are enabled. "
            "Non-essential cookies require your explicit consent."
        ),
    },
    "fr": {
        "banner_title": "Consentement aux temoins",
        "banner_text": (
            "Nous utilisons des temoins (cookies) et des technologies similaires pour ameliorer "
            "votre experience de navigation, analyser le trafic du site et personnaliser le contenu. "
            "Conformement a la Loi 25 du Quebec (Loi modernisant des dispositions legislatives en "
            "matiere de protection des renseignements personnels), nous requierons votre consentement "
            "explicite avant de placer des temoins non essentiels sur votre appareil."
        ),
        "accept_all": "Tout accepter",
        "refuse_all": "Tout refuser",
        "customize": "Personnaliser les preferences",
        "privacy_policy_link": "/privacy-policy",
        "privacy_policy_text": "Lire notre politique de confidentialite",
        "categories": {
            "strictly_necessary": {
                "name": "Strictement necessaires",
                "description": (
                    "Ces temoins sont essentiels au bon fonctionnement du site. "
                    "Ils permettent les fonctionnalites de base telles que l'authentification, "
                    "la gestion de session et la securite. Ils ne peuvent pas etre desactives."
                ),
                "required": True,
            },
            "functionality": {
                "name": "Fonctionnalite",
                "description": (
                    "Ces temoins permettent des fonctionnalites ameliorees telles que la "
                    "memorisation de vos preferences de langue, les recherches sauvegardees "
                    "et les parametres personnalises."
                ),
                "required": False,
            },
            "analytics": {
                "name": "Analytiques",
                "description": (
                    "Ces temoins nous aident a comprendre comment les visiteurs interagissent "
                    "avec le site en collectant des donnees anonymes afin d'ameliorer nos services."
                ),
                "required": False,
            },
            "marketing": {
                "name": "Publicitaires",
                "description": (
                    "Ces temoins sont utilises pour diffuser des publicites personnalisees "
                    "et mesurer la performance des campagnes sur differentes plateformes."
                ),
                "required": False,
            },
        },
        "law25_notice": (
            "En vertu de la Loi 25 du Quebec, vous avez le droit de connaitre les renseignements "
            "personnels que nous recueillons, d'y acceder, de les rectifier et de retirer votre "
            "consentement a tout moment. Pour toute question, contactez notre responsable de la "
            "protection des renseignements personnels a privacy@bidvex.ca."
        ),
        "privacy_by_default": (
            "Par defaut, seuls les temoins strictement necessaires sont actives. "
            "Les temoins non essentiels requierent votre consentement explicite."
        ),
    },
}


@legal_router.get("/legal/cookie-policy")
async def get_cookie_policy(request: Request):
    """
    Return localized cookie consent strings for the frontend banner.
    Language is determined by:
      1. ?lang=fr query param (explicit override)
      2. Accept-Language header (auto-detect)
      3. Default: English
    """
    # Explicit query param takes priority
    lang_param = request.query_params.get("lang", "").lower().strip()
    if lang_param in ("fr", "en"):
        lang = lang_param
    else:
        # Parse Accept-Language header
        accept = request.headers.get("accept-language", "")
        lang = _parse_accept_language(accept)

    strings = COOKIE_CONSENT_STRINGS.get(lang, COOKIE_CONSENT_STRINGS["en"])
    return {
        "language": lang,
        "consent": strings,
    }


def _parse_accept_language(header: str) -> str:
    """
    Simple Accept-Language parser.
    Returns 'fr' if French is preferred, else 'en'.
    """
    if not header:
        return "en"
    # Parse comma-separated values, e.g. "fr-CA,fr;q=0.9,en;q=0.8"
    parts = header.split(",")
    best_lang = "en"
    best_q = 0.0
    for part in parts:
        segments = part.strip().split(";")
        tag = segments[0].strip().lower()
        q = 1.0
        for seg in segments[1:]:
            seg = seg.strip()
            if seg.startswith("q="):
                try:
                    q = float(seg[2:])
                except ValueError:
                    q = 0.0
        if q > best_q:
            if tag.startswith("fr"):
                best_lang = "fr"
                best_q = q
            elif tag.startswith("en"):
                best_lang = "en"
                best_q = q
    return best_lang
