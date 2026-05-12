"""
Vehicle Auction Module - API Routes
Standalone, enterprise-grade vehicle auction system
Completely separate from general marketplace

Routes:
- /api/vehicles/* - Vehicle listings
- /api/vehicle-sellers/* - Seller management
- /api/vehicle-bids/* - Bidding system
- /api/vehicle-admin/* - Admin operations
- /api/vehicle-invoices/* - Invoice management
- /api/vehicle-payments/* - Payment processing
- /api/vehicle-documents/* - Document uploads
"""

from fastapi import APIRouter, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect, Query, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.responses import FileResponse
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from bson.objectid import ObjectId
import os
import uuid
import json
import asyncio
import logging

from models.vehicle_models import (
    # Enums
    SellerType, SellerVerificationStatus, VehicleListingStatus,
    VehicleAuctionType, VehicleAuctionVisibility, BidStatus,
    VehicleBodyType, TransmissionType, FuelType, DrivetrainType,
    TitleStatus, OwnershipStatus, LienStatus,
    # iter194 — dealer access + run status + license verification
    AuctionAccessType, VehicleRunStatus, DealerLicenseVerificationStatus,
    # Models
    VehicleSellerCreate, VehicleSeller, VehicleSellerDocument,
    VehicleListingCreate, VehicleListing, VehicleMedia, VehicleConditionReport,
    VehicleBidCreate, VehicleBid, VehicleBidDeposit,
    VehicleInvoice, VehicleInvoiceLineItem,
    LegalAcceptance, VehicleAuditLog,
    DealerLicenseSubmit, DealerLicense, DealerLicenseAdminAction,
    UnlockFeeQuote, UnlockFeeIntent, DealerContactReveal,
    validate_vin
)
from services.vin_decoder import decode_vin as vin_decode_service
from rate_limit import limiter as _limiter
from services.vehicle_pricing import (
    calculate_buyer_pricing,
    calculate_seller_pricing,
    get_pricing_estimate,
    get_subscription_tier,
    SubscriptionTier,
    PAYMENT_DEADLINE_DAYS
)
from services.vehicle_invoice import (
    generate_vehicle_invoice,
    get_invoice_by_id,
    get_invoices_for_user,
    get_invoice_summary,
    process_invoice_payment,
    InvoiceStatus
)
from services.vehicle_auction_handler import (
    process_ended_auction,
    process_all_ended_auctions,
    run_auction_scheduler
)
from services.vehicle_payment import get_payment_service
from services.seller_documents import (
    create_seller_document,
    get_seller_documents,
    get_document_by_id,
    approve_document,
    reject_document,
    check_seller_verification_status,
    get_pending_documents_for_admin,
    get_document_types_for_seller_type,
    DocumentType,
    DocumentStatus
)
from services.scheduler import (
    get_scheduler_status,
    run_job_manually
)
from services.cra_tax_reporting import (
    generate_gst_hst_report,
    generate_qst_report,
    generate_seller_payments_report,
    generate_annual_summary,
    get_tax_reports,
    get_tax_report_by_id,
    download_tax_report_xml,
    TaxReportType
)
from services.pdf_invoice import (
    generate_invoice_pdf,
    generate_settlement_pdf
)
from services.email_notifications import (
    send_document_approved_email,
    send_document_rejected_email,
    send_seller_approved_email,
    send_invoice_created_email,
    send_payment_confirmation_email,
    send_auction_won_email,
    send_auction_sold_email
)

logger = logging.getLogger(__name__)

# Router setup
vehicle_router = APIRouter(prefix="/api", tags=["Vehicle Auctions"])
security = HTTPBearer(auto_error=False)

# Database connection (will be set from main app)
db = None

def set_vehicle_db(database):
    """Set database instance from main app"""
    global db
    db = database


# ============= AUTHENTICATION HELPERS =============

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Extract current user from JWT token"""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    from jose import jwt, JWTError
    jwt_secret = os.environ.get('JWT_SECRET', 'dev-secret-key-change-in-production')
    
    try:
        payload = jwt.decode(credentials.credentials, jwt_secret, algorithms=["HS256"])
        # JWT uses 'sub' field for user_id
        user_id = payload.get("sub") or payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
        
        user = await db.users.find_one({"id": user_id})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return user
    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


async def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify admin access"""
    user = await get_current_user(credentials)
    if user.get("role") not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


async def get_vehicle_seller(user: dict = Depends(get_current_user)):
    """Get verified vehicle seller profile for current user"""
    seller = await db.vehicle_sellers.find_one({
        "user_id": user["id"],
        "verification_status": SellerVerificationStatus.APPROVED.value
    })
    if not seller:
        raise HTTPException(status_code=403, detail="Verified vehicle seller account required")
    return seller


# ============= AUDIT LOGGING =============

async def log_audit(entity_type: str, entity_id: str, action: str, 
                   performed_by: str, role: str, old_value: dict = None, 
                   new_value: dict = None, reason: str = None):
    """Log an audit entry"""
    audit = {
        "id": str(uuid.uuid4()),
        "entity_type": entity_type,
        "entity_id": entity_id,
        "action": action,
        "performed_by": performed_by,
        "performed_by_role": role,
        "old_value": old_value,
        "new_value": new_value,
        "reason": reason,
        "created_at": datetime.now(timezone.utc)
    }
    await db.vehicle_audit_logs.insert_one(audit)


# ============= SYSTEM STATUS & ADMIN CONTROLS =============

# Default system settings - Vehicle auctions are DISABLED until permits obtained
DEFAULT_SYSTEM_SETTINGS = {
    "vehicle_auctions_enabled": False,  # MUST be False by default - Admin only activation
    "vehicle_listing_enabled": False,   # Permanently disabled for all users
    "vehicle_bidding_enabled": False,   # Disabled until auctions enabled
    "updated_at": None,
    "updated_by": None
}

async def get_system_settings():
    """Get current system settings for vehicle auctions"""
    settings = await db.vehicle_system_settings.find_one({"_id": "vehicle_settings"})
    if not settings:
        # Initialize with defaults (all disabled)
        await db.vehicle_system_settings.insert_one({
            "_id": "vehicle_settings",
            **DEFAULT_SYSTEM_SETTINGS,
            "created_at": datetime.now(timezone.utc)
        })
        return DEFAULT_SYSTEM_SETTINGS
    
    # Remove _id from response
    settings.pop("_id", None)
    return settings


# iter202 Phase A — Public stats strip for the new buyer-experience hero.
@vehicle_router.get("/vehicles/stats")
async def get_vehicle_stats():
    """Public — high-level counters surfaced on the Vehicle Auctions hero banner.

    Returns:
      • `active_listings`      — count of currently-active public auctions
      • `ending_soon`          — auctions ending within the next 24 hours
      • `verified_dealers`     — dealers with a verified dealer licence
      • `provinces_covered`    — distinct provinces with at least one active listing
      • `total_bids_24h`       — bids placed across all vehicle listings in the last 24h
    """
    now = datetime.now(timezone.utc)
    soon = now + timedelta(hours=24)
    twenty_four_h_ago = now - timedelta(hours=24)
    active_query = {
        "status": VehicleListingStatus.ACTIVE.value,
        "visibility": VehicleAuctionVisibility.PUBLIC.value,
    }
    # Count active listings
    active_count = await db.vehicle_listings.count_documents(active_query)
    # Ending soon (next 24h) — accept both ISO strings and datetime values
    ending_query = {**active_query, "end_time": {"$gte": now.isoformat(), "$lte": soon.isoformat()}}
    ending_count = await db.vehicle_listings.count_documents(ending_query)
    # Distinct provinces represented in active listings
    provinces = await db.vehicle_listings.distinct("location_province", active_query)
    provinces_covered = len([p for p in (provinces or []) if p])
    # Verified dealers
    verified_dealers = await db.users.count_documents({"dealer_license_verified": True})
    # 24h bid volume — accept ISO string or datetime; tolerate either
    bids_24h = await db.vehicle_bids.count_documents({
        "$or": [
            {"created_at": {"$gte": twenty_four_h_ago.isoformat()}},
            {"created_at": {"$gte": twenty_four_h_ago}},
        ]
    })
    return {
        "active_listings": active_count,
        "ending_soon": ending_count,
        "verified_dealers": verified_dealers,
        "provinces_covered": provinces_covered,
        "total_bids_24h": bids_24h,
        "as_of": now.isoformat(),
    }


@vehicle_router.get("/vehicles/system/status")
async def get_vehicle_system_status():
    """
    Get current vehicle auction system status
    
    Public endpoint - no auth required
    Returns whether vehicle auctions are enabled
    """
    settings = await get_system_settings()
    return {
        "vehicle_auctions_enabled": settings.get("vehicle_auctions_enabled", False),
        "vehicle_listing_enabled": settings.get("vehicle_listing_enabled", False),
        "vehicle_bidding_enabled": settings.get("vehicle_bidding_enabled", False),
        "discovery_mode": not settings.get("vehicle_auctions_enabled", False),
        "message": "Vehicle auctions are currently in discovery mode" if not settings.get("vehicle_auctions_enabled", False) else "Vehicle auctions are active"
    }


# iter201 — Phase 2 — Vehicle category taxonomy (15 categories per CEO spec).
@vehicle_router.get("/vehicles/categories")
async def list_vehicle_categories():
    """Public — returns the 15 BidVex vehicle categories with bilingual labels + subcategories.

    CEO constraint #3: `parts_accessories` does NOT require dealer licence.
    """
    from services.vehicle_categories import VEHICLE_CATEGORIES
    return {"total": len(VEHICLE_CATEGORIES), "items": VEHICLE_CATEGORIES}


# iter201 — Phase 1 — Province regulations registry (public read-only).
# Used by the province-aware seller onboarding wizard and buyer gate.
@vehicle_router.get("/vehicles/province-regulations")
async def list_province_regulations():
    """List all 13 jurisdictions seeded in `province_regulations`.

    Public — no auth required. Frontend caches this for the seller and buyer flows.
    """
    docs = await db.province_regulations.find({}, {"_id": 0}).sort("province_code", 1).to_list(50)
    return {"total": len(docs), "items": docs}


@vehicle_router.get("/vehicles/province-regulations/{province_code}")
async def get_province_regulation(province_code: str):
    """Fetch one province/territory by 2-letter code (BC/AB/SK/MB/ON/QC/NB/NS/PE/NL/YT/NT/NU)."""
    code = (province_code or "").strip().upper()
    doc = await db.province_regulations.find_one({"province_code": code}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Unknown province code: {code}")
    return doc


@vehicle_router.post("/vehicle-admin/system/toggle-auctions")
async def admin_toggle_vehicle_auctions(
    enabled: bool,
    admin: dict = Depends(get_admin_user)
):
    """
    Admin only: Enable or disable vehicle auctions system-wide
    
    When disabled:
    - No vehicle auctions can go live
    - No bids can be placed
    - No vehicle listings can be activated
    - Discovery/browse mode only
    
    IMPORTANT: This is the ONLY way to enable vehicle auctions
    """
    now = datetime.now(timezone.utc)
    
    # Get current settings for audit log
    current_settings = await get_system_settings()
    
    # Update settings
    await db.vehicle_system_settings.update_one(
        {"_id": "vehicle_settings"},
        {
            "$set": {
                "vehicle_auctions_enabled": enabled,
                "vehicle_bidding_enabled": enabled,  # Bidding follows auction status
                # Note: vehicle_listing_enabled stays False - separate control
                "updated_at": now,
                "updated_by": admin["id"]
            }
        },
        upsert=True
    )
    
    # Log audit
    await log_audit(
        "system_settings", "vehicle_settings", 
        "auctions_enabled" if enabled else "auctions_disabled",
        admin["id"], "admin",
        old_value={"vehicle_auctions_enabled": current_settings.get("vehicle_auctions_enabled", False)},
        new_value={"vehicle_auctions_enabled": enabled}
    )
    
    logger.info(f"Admin {admin['id']} {'enabled' if enabled else 'disabled'} vehicle auctions")
    
    return {
        "success": True,
        "vehicle_auctions_enabled": enabled,
        "vehicle_bidding_enabled": enabled,
        "vehicle_listing_enabled": False,  # Always report this as disabled
        "message": f"Vehicle auctions have been {'enabled' if enabled else 'disabled'}",
        "updated_at": now.isoformat()
    }


@vehicle_router.post("/vehicle-admin/system/toggle-listing")
async def admin_toggle_vehicle_listing(
    enabled: bool,
    admin: dict = Depends(get_admin_user)
):
    """
    Admin only: Enable or disable vehicle listing capability
    
    When disabled (default):
    - No users can create vehicle listings
    - No vehicle auctions can be submitted
    - This is a separate control from auction viewing
    
    IMPORTANT: This should remain OFF until all permits are approved
    """
    now = datetime.now(timezone.utc)
    
    # Get current settings for audit log
    current_settings = await get_system_settings()
    
    # Update settings
    await db.vehicle_system_settings.update_one(
        {"_id": "vehicle_settings"},
        {
            "$set": {
                "vehicle_listing_enabled": enabled,
                "updated_at": now,
                "updated_by": admin["id"]
            }
        },
        upsert=True
    )
    
    # Log audit
    await log_audit(
        "system_settings", "vehicle_settings", 
        "listing_enabled" if enabled else "listing_disabled",
        admin["id"], "admin",
        old_value={"vehicle_listing_enabled": current_settings.get("vehicle_listing_enabled", False)},
        new_value={"vehicle_listing_enabled": enabled}
    )
    
    logger.info(f"Admin {admin['id']} {'enabled' if enabled else 'disabled'} vehicle listing")
    
    return {
        "success": True,
        "vehicle_listing_enabled": enabled,
        "message": f"Vehicle listing has been {'enabled' if enabled else 'disabled'}",
        "updated_at": now.isoformat()
    }


@vehicle_router.get("/vehicle-admin/system/settings")
async def admin_get_system_settings(admin: dict = Depends(get_admin_user)):
    """Admin only: Get all system settings"""
    settings = await get_system_settings()
    return settings


# ============= VIN DECODER ENDPOINT =============

@vehicle_router.get("/vehicles/decode-vin/{vin}")
async def decode_vin_endpoint(vin: str, user: dict = Depends(get_current_user)):
    """
    Decode a VIN using NHTSA API
    Returns vehicle information from VIN
    """
    if not validate_vin(vin):
        raise HTTPException(status_code=400, detail="Invalid VIN format")
    
    result = await vin_decode_service(vin)
    
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "VIN decode failed"))
    
    return result["data"]


# ============= VEHICLE SELLER ENDPOINTS =============

@vehicle_router.post("/vehicle-sellers/register")
async def register_vehicle_seller(
    seller_data: VehicleSellerCreate,
    user: dict = Depends(get_current_user)
):
    """
    Register as a vehicle seller
    Requires admin approval before listing vehicles
    
    NOTE: Registration is allowed even when listing is disabled,
    but actual listing will be blocked until permits are obtained.
    """
    # Check if already registered
    existing = await db.vehicle_sellers.find_one({"user_id": user["id"]})
    if existing:
        raise HTTPException(status_code=400, detail="Already registered as vehicle seller")
    
    # Determine monthly limit based on seller type
    if seller_data.seller_type == SellerType.PRIVATE:
        monthly_limit = 1
    else:
        monthly_limit = 500
    
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    
    seller = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "seller_type": seller_data.seller_type.value,
        "verification_status": SellerVerificationStatus.PENDING.value,
        
        # Business info
        "business_name": seller_data.business_name,
        "business_address": seller_data.business_address,
        "business_phone": seller_data.business_phone,
        
        # Licensing
        "license_number": seller_data.license_number,
        "license_province": seller_data.license_province,
        "license_expiry": seller_data.license_expiry,
        "tax_id": seller_data.tax_id,
        
        # Profile
        "website": seller_data.website,
        "description": seller_data.description,
        "logo_url": None,
        
        # Documents
        "documents": [],
        
        # Stats
        "total_listings": 0,
        "total_sold": 0,
        "total_revenue": 0.0,
        "average_rating": 0.0,
        "review_count": 0,
        
        # Limits
        "monthly_listing_count": 0,
        "monthly_listing_limit": monthly_limit,
        "current_month": current_month,
        
        # Timestamps
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
        "approved_at": None,
        "approved_by": None,
        "rejection_reason": None
    }
    
    await db.vehicle_sellers.insert_one(seller)
    
    # Log audit
    await log_audit("seller", seller["id"], "registered", user["id"], "seller", new_value={"seller_type": seller_data.seller_type.value})
    
    # Remove MongoDB _id
    seller.pop("_id", None)
    return seller


@vehicle_router.get("/vehicle-sellers/me")
async def get_my_seller_profile(user: dict = Depends(get_current_user)):
    """Get current user's vehicle seller profile"""
    seller = await db.vehicle_sellers.find_one({"user_id": user["id"]}, {"_id": 0})
    if not seller:
        raise HTTPException(status_code=404, detail="Not registered as vehicle seller")
    # iter209 — surface resubmission counters to the frontend
    seller.setdefault("resubmission_count", 0)
    seller.setdefault("max_resubmissions", 3)
    seller.setdefault("rejection_history", [])
    return seller


@vehicle_router.post("/vehicles/dealer/resubmit")
async def resubmit_vehicle_dealer_application(
    payload: VehicleSellerCreate,
    user: dict = Depends(get_current_user),
):
    """iter209 Step 2 — Vehicle dealer application resubmission.

    Rules:
      - Current vehicle_sellers.verification_status must be 'rejected'
      - Max 3 attempts (HTTP 403 with bilingual message on 4th)
      - Text fields pre-fillable; uploads cleared (re-supplied via separate endpoint)
    """
    from services.resubmission_service import resubmit_application

    body = {
        "seller_type": payload.seller_type.value if payload.seller_type else None,
        "business_name": payload.business_name,
        "business_address": payload.business_address,
        "business_phone": payload.business_phone,
        "license_number": payload.license_number,
        "license_province": payload.license_province,
        "tax_id": payload.tax_id,
        "website": payload.website,
        "description": payload.description,
    }
    result = await resubmit_application(
        db,
        flavor="dealer",
        user_id=user["id"],
        user_email=user.get("email"),
        payload=body,
    )
    return result


@vehicle_router.post("/vehicle-sellers/documents")
async def upload_seller_document(
    document_type: str,
    file: UploadFile = File(...),
    user: dict = Depends(get_current_user)
):
    """Upload verification document for seller"""
    seller = await db.vehicle_sellers.find_one({"user_id": user["id"]})
    if not seller:
        raise HTTPException(status_code=404, detail="Not registered as vehicle seller")
    
    valid_types = ["drivers_license", "business_license", "dealer_license", 
                   "auctioneer_license", "proof_of_address", "tax_certificate", "other"]
    if document_type not in valid_types:
        raise HTTPException(status_code=400, detail=f"Invalid document type. Must be one of: {valid_types}")
    
    # In production, upload to cloud storage
    # For now, store as base64 or URL placeholder
    await file.read()  # Read to validate file, content stored in cloud in production
    
    # For demo, we'll create a placeholder URL
    # In production, upload to S3/GCS and get real URL
    file_url = f"/uploads/seller-docs/{seller['id']}/{document_type}_{uuid.uuid4()}"
    
    document = {
        "document_type": document_type,
        "file_url": file_url,
        "file_name": file.filename,
        "uploaded_at": datetime.now(timezone.utc),
        "verified": False,
        "verified_by": None,
        "verified_at": None,
        "notes": None
    }
    
    await db.vehicle_sellers.update_one(
        {"id": seller["id"]},
        {
            "$push": {"documents": document},
            "$set": {
                "updated_at": datetime.now(timezone.utc),
                "verification_status": SellerVerificationStatus.UNDER_REVIEW.value
            }
        }
    )
    
    return {"message": "Document uploaded successfully", "document": document}


@vehicle_router.get("/vehicle-sellers/{seller_id}/public")
async def get_seller_public_profile(seller_id: str):
    """Get public seller profile (for vehicle listing pages)"""
    seller = await db.vehicle_sellers.find_one(
        {"id": seller_id, "verification_status": SellerVerificationStatus.APPROVED.value},
        {
            "_id": 0,
            "id": 1,
            "seller_type": 1,
            "business_name": 1,
            "description": 1,
            "logo_url": 1,
            "total_listings": 1,
            "total_sold": 1,
            "average_rating": 1,
            "review_count": 1,
            "created_at": 1
        }
    )
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    # Add badge info
    seller["badges"] = []
    if seller["seller_type"] == "dealer":
        seller["badges"].append({"type": "licensed_dealer", "label": "Licensed Dealer"})
    elif seller["seller_type"] == "auctioneer":
        seller["badges"].append({"type": "verified_auctioneer", "label": "Verified Auctioneer"})
    else:
        seller["badges"].append({"type": "private_seller", "label": "Private Seller"})
    
    return seller


# ============= VEHICLE LISTING ENDPOINTS =============

@vehicle_router.post("/vehicles")
async def create_vehicle_listing(
    listing_data: VehicleListingCreate,
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user)
):
    """
    Create a new vehicle listing
    Enforces seller limits and requires minimum media
    
    BLOCKED when vehicle_listing_enabled is False (default)
    """
    # CRITICAL: Check if vehicle listing is enabled system-wide
    settings = await get_system_settings()
    if not settings.get("vehicle_listing_enabled", False):
        raise HTTPException(
            status_code=403,
            detail="Vehicle listing is currently disabled. Vehicle auctions are pending permit approval. Please check back later."
        )
    
    # Check seller limits
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    
    # Reset monthly count if new month
    if seller.get("current_month") != current_month:
        await db.vehicle_sellers.update_one(
            {"id": seller["id"]},
            {"$set": {"monthly_listing_count": 0, "current_month": current_month}}
        )
        seller["monthly_listing_count"] = 0
    
    # Check monthly limit
    if seller["monthly_listing_count"] >= seller["monthly_listing_limit"]:
        limit = seller["monthly_listing_limit"]
        seller_type = seller["seller_type"]
        raise HTTPException(
            status_code=403, 
            detail=f"Monthly listing limit reached ({limit} vehicles/month for {seller_type} sellers)"
        )
    
    # Private sellers cannot create dealer-only auctions
    if seller["seller_type"] == "private" and listing_data.visibility != VehicleAuctionVisibility.PUBLIC:
        raise HTTPException(
            status_code=403,
            detail="Private sellers can only create public auctions"
        )

    # iter194: Only licensed dealers can restrict bidder access to licensed-only
    if (
        listing_data.auction_access == AuctionAccessType.LICENSED_ONLY
        and seller["seller_type"] != "dealer"
    ):
        raise HTTPException(
            status_code=403,
            detail="Only licensed dealers can create licensed-only auctions"
        )

    # iter201 — Phase 2 — Vehicle category validation (CEO 15-category spec)
    from services.vehicle_categories import (
        get_category as _get_cat,
        get_subcategory as _get_subcat,
        category_requires_dealer_license as _cat_needs_lic,
    )
    if not listing_data.category_id:
        raise HTTPException(status_code=400, detail={
            "code": "category_required",
            "message_en": "A vehicle category is required.",
            "message_fr": "Une catégorie de véhicule est requise.",
        })
    cat_doc = _get_cat(listing_data.category_id)
    if not cat_doc:
        raise HTTPException(status_code=400, detail={
            "code": "category_invalid",
            "message_en": f"Unknown vehicle category '{listing_data.category_id}'.",
            "message_fr": f"Catégorie de véhicule inconnue : « {listing_data.category_id} ».",
        })
    if listing_data.subcategory_id and not _get_subcat(listing_data.category_id, listing_data.subcategory_id):
        raise HTTPException(status_code=400, detail={
            "code": "subcategory_invalid",
            "message_en": f"Unknown subcategory '{listing_data.subcategory_id}' for category '{listing_data.category_id}'.",
            "message_fr": "Sous-catégorie inconnue.",
        })
    # CEO constraint #3 — only `parts_accessories` is open to non-dealers.
    if _cat_needs_lic(listing_data.category_id) and seller["seller_type"] != "dealer":
        raise HTTPException(status_code=403, detail={
            "code": "category_requires_dealer_license",
            "message_en": "This vehicle category requires a verified provincial dealer licence. Only Vehicle Parts & Accessories is open to individual sellers.",
            "message_fr": "Cette catégorie de véhicule nécessite une licence de concessionnaire provinciale vérifiée. Seules les pièces et accessoires sont ouverts aux vendeurs individuels.",
        })

    # iter201 — Phase 2 — Quebec French-language enforcement (CEO constraint #2)
    if (listing_data.location_province or "").upper() == "QC":
        title_fr = (listing_data.title_fr or "").strip()
        description_fr = (listing_data.description_fr or "").strip()
        # If the seller didn't provide a French field, use the main title/description as French only
        # when its language is plausibly French (very lightweight heuristic — accent presence).
        if not title_fr and not any(c in (listing_data.title or "") for c in "àâçéèêëîïôûùüÿ"):
            raise HTTPException(status_code=400, detail={
                "code": "qc_french_title_required",
                "message_en": "Quebec listings must include a French title (Charter of the French Language).",
                "message_fr": "Les annonces québécoises doivent inclure un titre en français (Charte de la langue française).",
            })
        if not description_fr and not any(c in (listing_data.description or "") for c in "àâçéèêëîïôûùüÿ"):
            raise HTTPException(status_code=400, detail={
                "code": "qc_french_description_required",
                "message_en": "Quebec listings must include a French description.",
                "message_fr": "Les annonces québécoises doivent inclure une description en français.",
            })

    # Decode VIN
    vin_result = await vin_decode_service(listing_data.vin)
    vin_decoded = vin_result.get("success", False)
    vin_data = vin_result.get("data") if vin_decoded else None
    
    # Create listing
    listing_id = str(uuid.uuid4())
    
    listing = {
        "id": listing_id,
        "seller_id": seller["id"],
        "seller_user_id": user["id"],
        
        # VIN
        "vin": listing_data.vin,
        "vin_decoded": vin_decoded,
        "vin_data": vin_data,
        
        # Basic Info
        "year": listing_data.year,
        "make": listing_data.make,
        "model": listing_data.model,
        "trim": listing_data.trim,
        "body_type": listing_data.body_type.value,
        
        # Specs
        "mileage": listing_data.mileage,
        "transmission": listing_data.transmission.value,
        "fuel_type": listing_data.fuel_type.value,
        "drivetrain": listing_data.drivetrain.value,
        "engine_size": listing_data.engine_size,
        "cylinders": listing_data.cylinders,
        "horsepower": listing_data.horsepower,
        
        # Colors
        "exterior_color": listing_data.exterior_color,
        "interior_color": listing_data.interior_color,
        
        # Documentation
        "ownership_status": listing_data.ownership_status.value,
        "title_status": listing_data.title_status.value,
        "lien_status": listing_data.lien_status.value,
        "inspection_report_url": None,
        "title_document_url": None,
        
        # Condition
        "condition_report": listing_data.condition_report.model_dump(),
        
        # Location
        "location_city": listing_data.location_city,
        "location_province": listing_data.location_province,
        "location_postal_code": listing_data.location_postal_code,
        
        # Auction Settings
        "auction_type": listing_data.auction_type.value,
        "visibility": listing_data.visibility.value,
        "auction_access": listing_data.auction_access.value,    # iter194
        "run_status": listing_data.run_status.value,            # iter194
        "start_time": listing_data.start_time,
        "end_time": listing_data.end_time,
        "original_end_time": listing_data.end_time,
        "starting_price": listing_data.starting_price,
        "reserve_price": listing_data.reserve_price,
        "reserve_met": False,
        "buy_now_price": listing_data.buy_now_price,
        "bid_increment": listing_data.bid_increment,
        
        # Deposit
        "requires_deposit": listing_data.requires_deposit,
        "deposit_amount": listing_data.deposit_amount,
        
        # Description
        "title": listing_data.title,
        "description": listing_data.description,
        "features": listing_data.features,

        # iter198 — Pilot attribution
        "utm_source": (listing_data.utm_source or "").strip()[:100] or None,

        # iter201 — Phase 2 — Vehicle category + Quebec bilingual fields
        "category_id": listing_data.category_id,
        "subcategory_id": listing_data.subcategory_id or None,
        "title_fr": (listing_data.title_fr or "").strip() or None,
        "description_fr": (listing_data.description_fr or "").strip() or None,
        
        # Media (to be added separately)
        "media": [],
        
        # Status
        "status": VehicleListingStatus.DRAFT.value,
        "rejection_reason": None,
        
        # Bidding Stats
        "current_bid": 0.0,
        "bid_count": 0,
        "highest_bidder_id": None,
        "watchers_count": 0,
        "views_count": 0,
        
        # Winner
        "winner_id": None,
        "final_price": None,
        "sold_at": None,
        
        # Fees
        "buyer_premium_percent": 5.0,
        "platform_fee_percent": 2.5,
        
        # Timestamps
        "created_at": datetime.now(timezone.utc),
        "updated_at": None,
        "approved_at": None,
        "approved_by": None
    }
    
    await db.vehicle_listings.insert_one(listing)
    
    # Update seller monthly count
    await db.vehicle_sellers.update_one(
        {"id": seller["id"]},
        {"$inc": {"monthly_listing_count": 1, "total_listings": 1}}
    )
    
    # Log audit
    await log_audit("vehicle", listing_id, "created", user["id"], "seller")
    
    listing.pop("_id", None)
    return listing


@vehicle_router.post("/vehicles/{vehicle_id}/media")
async def upload_vehicle_media(
    vehicle_id: str,
    category: str,
    file: UploadFile = File(...),
    caption: str = None,
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user)
):
    """Upload media (photo/video) for vehicle listing"""
    listing = await db.vehicle_listings.find_one({
        "id": vehicle_id,
        "seller_id": seller["id"]
    })
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle listing not found")
    
    valid_categories = ["front", "rear", "driver_side", "passenger_side", 
                       "interior_front", "interior_rear", "dashboard", 
                       "engine", "trunk", "vin_plate", "damage", "document", "other"]
    if category not in valid_categories:
        raise HTTPException(status_code=400, detail=f"Invalid category. Must be one of: {valid_categories}")
    
    # Determine media type
    content_type = file.content_type or ""
    media_type = "video" if "video" in content_type else "photo"
    
    # Generate placeholder URL (in production, upload to cloud storage)
    file_url = f"/uploads/vehicles/{vehicle_id}/{category}_{uuid.uuid4()}"
    
    media_item = {
        "id": str(uuid.uuid4()),
        "type": media_type,
        "url": file_url,
        "thumbnail_url": file_url,  # In production, generate thumbnail
        "category": category,
        "caption": caption,
        "order": len(listing.get("media", [])),
        "uploaded_at": datetime.now(timezone.utc)
    }
    
    await db.vehicle_listings.update_one(
        {"id": vehicle_id},
        {
            "$push": {"media": media_item},
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }
    )
    
    return {"message": "Media uploaded successfully", "media": media_item}


@vehicle_router.post("/vehicles/{vehicle_id}/submit")
async def submit_vehicle_for_approval(
    vehicle_id: str,
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user)
):
    """Submit vehicle listing for admin approval"""
    listing = await db.vehicle_listings.find_one({
        "id": vehicle_id,
        "seller_id": seller["id"],
        "status": VehicleListingStatus.DRAFT.value
    })
    if not listing:
        raise HTTPException(status_code=404, detail="Draft listing not found")
    
    # Validate minimum 10 photos
    media = listing.get("media", [])
    photo_count = len([m for m in media if m.get("type") == "photo"])
    if photo_count < 10:
        raise HTTPException(
            status_code=400, 
            detail=f"Minimum 10 photos required. Current: {photo_count}"
        )
    
    # Check required photo categories
    required_categories = ["front", "rear", "vin_plate"]
    uploaded_categories = [m.get("category") for m in media]
    missing = [c for c in required_categories if c not in uploaded_categories]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required photo categories: {missing}"
        )
    
    await db.vehicle_listings.update_one(
        {"id": vehicle_id},
        {
            "$set": {
                "status": VehicleListingStatus.PENDING_APPROVAL.value,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    await log_audit("vehicle", vehicle_id, "submitted_for_approval", user["id"], "seller")
    
    return {"message": "Listing submitted for approval"}


@vehicle_router.get("/vehicles")
async def list_vehicles(
    status: str = None,
    auction_type: str = None,
    make: str = None,
    year_min: int = None,
    year_max: int = None,
    price_min: float = None,
    price_max: float = None,
    body_type: str = None,
    province: str = None,
    sort_by: str = "end_time",
    sort_order: str = "asc",
    page: int = 1,
    limit: int = 20,
    # iter202 Phase A — taxonomy-aware filter + promoted-first ordering
    category_id: str = None,
    subcategory_id: str = None,
    promoted_first: bool = False,
    # iter202 Phase B — related-vehicles support (exclude current listing on detail page)
    exclude_id: str = None,
    # iter202 Phase B — sidebar filter additions
    auction_status: str = None,
    condition: str = None,
    max_mileage: int = None,
    transmission: str = None,
    fuel_type: str = None,
    drivetrain: str = None,
    title_status: str = None,
    seller_type: str = None
):
    """
    List public vehicle auctions
    This is the main browse endpoint for buyers
    """
    query = {
        "status": VehicleListingStatus.ACTIVE.value,
        "visibility": VehicleAuctionVisibility.PUBLIC.value
    }
    
    if make:
        query["make"] = {"$regex": make, "$options": "i"}
    if year_min:
        query["year"] = {"$gte": year_min}
    if year_max:
        query.setdefault("year", {})["$lte"] = year_max
    if price_min:
        query["starting_price"] = {"$gte": price_min}
    if price_max:
        query.setdefault("starting_price", {})["$lte"] = price_max
    if body_type:
        query["body_type"] = body_type
    if province:
        query["location_province"] = province
    if auction_type:
        query["auction_type"] = auction_type
    # iter202 Phase A — category taxonomy filter
    if category_id:
        query["category_id"] = category_id
    if subcategory_id:
        query["subcategory_id"] = subcategory_id
    # iter202 Phase B — exclude a specific listing (for related-vehicles)
    if exclude_id:
        query["id"] = {"$ne": exclude_id}
    # iter202 Phase B — sidebar filters
    if auction_status:
        query["auction_type"] = auction_status if auction_status != "scheduled" else "scheduled"
    if condition:
        query["condition_status"] = condition
    if max_mileage is not None:
        query["mileage"] = {"$lte": int(max_mileage)}
    if transmission:
        query["transmission"] = transmission
    if fuel_type:
        query["fuel_type"] = fuel_type
    if drivetrain:
        query["drivetrain"] = drivetrain
    if title_status:
        query["title_status"] = title_status
    if seller_type:
        query["seller.seller_type"] = seller_type
    
    # Sort
    sort_dir = 1 if sort_order == "asc" else -1
    sort_field = sort_by if sort_by in ["end_time", "current_bid", "created_at", "year", "mileage"] else "end_time"
    # iter202 Phase A — bubble promoted listings to the top when requested
    sort_spec = [("is_promoted", -1), (sort_field, sort_dir)] if promoted_first else [(sort_field, sort_dir)]
    
    skip = (page - 1) * limit
    
    cursor = db.vehicle_listings.find(query, {"_id": 0}).sort(sort_spec).skip(skip).limit(limit)
    vehicles = await cursor.to_list(length=limit)
    
    total = await db.vehicle_listings.count_documents(query)
    
    # Also include vehicle-category items from the general listings collection
    general_vehicle_query = {
        "status": "active",
        "category": {"$in": ["vehicles", "vehicle", "car", "auto"]}
    }
    general_vehicles = await db.listings.find(
        general_vehicle_query, {"_id": 0}
    ).sort("auction_end_date", 1).to_list(500)
    
    # Normalize general listings to match vehicle_listings shape
    for gv in general_vehicles:
        # Parse title to extract year/make/model
        title = gv.get("title_en") or gv.get("title", "")
        parts = title.split(" ", 2)
        parsed_year = 0
        parsed_make = ""
        parsed_model = title
        if len(parts) >= 3 and parts[0].isdigit() and len(parts[0]) == 4:
            parsed_year = int(parts[0])
            parsed_make = parts[1]
            parsed_model = parts[2].split(" — ")[0]
        elif len(parts) >= 2:
            parsed_make = parts[0]
            parsed_model = " ".join(parts[1:])
        
        gv.setdefault("end_time", gv.get("auction_end_date"))
        gv.setdefault("current_bid", gv.get("current_price", gv.get("starting_price", 0)))
        gv.setdefault("make", parsed_make)
        gv.setdefault("model", parsed_model)
        gv.setdefault("year", parsed_year)
        gv.setdefault("mileage", 0)
        gv.setdefault("body_type", "sedan")
        gv.setdefault("transmission", "")
        gv.setdefault("fuel_type", "")
        gv.setdefault("exterior_color", "")
        gv.setdefault("drivetrain", "")
        gv.setdefault("engine", "")
        gv.setdefault("location_province", gv.get("region", "QC"))
        gv.setdefault("condition_status", gv.get("condition", "like_new"))
        gv.setdefault("views_count", gv.get("views", 0))
        gv.setdefault("source", "listings")
    
    # Merge and re-sort
    all_vehicles = vehicles + general_vehicles
    general_total = await db.listings.count_documents(general_vehicle_query)
    
    return {
        "vehicles": all_vehicles,
        "total": total + general_total,
        "page": page,
        "pages": ((total + general_total) + limit - 1) // limit
    }


@vehicle_router.get("/vehicles/{vehicle_id}")
async def get_vehicle_detail(vehicle_id: str, request: Request):
    """Get detailed vehicle listing"""
    listing = await db.vehicle_listings.find_one({"id": vehicle_id}, {"_id": 0})
    
    # Fallback: check general listings collection for vehicle-category items
    if not listing:
        listing = await db.listings.find_one(
            {"id": vehicle_id, "category": {"$in": ["vehicles", "vehicle", "car", "auto"]}},
            {"_id": 0}
        )
        if listing:
            # Parse title to extract year/make/model (e.g. "2024 BMW M3 Competition xDrive")
            title = listing.get("title_en") or listing.get("title", "")
            parts = title.split(" ", 2)
            parsed_year = 0
            parsed_make = ""
            parsed_model = title
            if len(parts) >= 3 and parts[0].isdigit() and len(parts[0]) == 4:
                parsed_year = int(parts[0])
                parsed_make = parts[1]
                parsed_model = parts[2].split(" — ")[0]  # Remove subtitle after dash
            elif len(parts) >= 2:
                parsed_make = parts[0]
                parsed_model = " ".join(parts[1:])
            
            # Normalize to vehicle detail shape
            listing.setdefault("end_time", listing.get("auction_end_date"))
            listing.setdefault("current_bid", listing.get("current_price", listing.get("starting_price", 0)))
            listing.setdefault("make", parsed_make)
            listing.setdefault("model", parsed_model)
            listing.setdefault("year", parsed_year)
            listing.setdefault("mileage", 0)
            listing.setdefault("vin", "")
            listing.setdefault("body_type", "")
            listing.setdefault("transmission", "")
            listing.setdefault("fuel_type", "")
            listing.setdefault("exterior_color", "")
            listing.setdefault("interior_color", "")
            listing.setdefault("drivetrain", "")
            listing.setdefault("engine", "")
            listing.setdefault("source", "listings")
            listing.setdefault("views_count", listing.get("views", 0))
            listing.setdefault("condition_report", {})
            listing.setdefault("media", [])
            listing.setdefault("recent_bids", [])
            # Fetch bid history from bids collection
            bids = await db.bids.find(
                {"listing_id": vehicle_id},
                {"_id": 0, "id": 1, "bidder_id": 1, "amount": 1, "created_at": 1, "bid_type": 1}
            ).sort("created_at", -1).limit(20).to_list(20)
            listing["recent_bids"] = bids
            # Get seller info from users
            seller = await db.users.find_one(
                {"id": listing.get("seller_id")},
                {"_id": 0, "id": 1, "name": 1, "account_type": 1}
            )
            listing["seller"] = seller
            # Increment view count in listings collection
            await db.listings.update_one({"id": vehicle_id}, {"$inc": {"views": 1}})
            return listing
    
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Increment view count
    await db.vehicle_listings.update_one(
        {"id": vehicle_id},
        {"$inc": {"views_count": 1}}
    )
    
    # Get seller info
    seller = await db.vehicle_sellers.find_one(
        {"id": listing["seller_id"]},
        {"_id": 0, "id": 1, "user_id": 1, "seller_type": 1, "business_name": 1,
         "average_rating": 1, "total_sold": 1,
         # iter201 — Phase 2 — Province-licensed dealer badge fields
         "license_number": 1, "license_province": 1,
         "dealer_license_number": 1, "dealer_license_province": 1, "dealer_license_type": 1}
    )
    listing["seller"] = seller
    
    # Get bid history (anonymized)
    bids = await db.vehicle_bids.find(
        {"vehicle_id": vehicle_id},
        {"_id": 0, "id": 1, "bidder_name": 1, "amount": 1, "created_at": 1}
    ).sort("created_at", -1).limit(20).to_list(length=20)
    listing["recent_bids"] = bids
    
    return listing


@vehicle_router.get("/vehicles/my/listings")
async def get_my_vehicle_listings(
    status: str = None,
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user)
):
    """Get seller's own vehicle listings"""
    query = {"seller_id": seller["id"]}
    if status:
        query["status"] = status
    
    cursor = db.vehicle_listings.find(query, {"_id": 0}).sort("created_at", -1)
    listings = await cursor.to_list(length=100)
    
    return {"listings": listings}


# ============= BIDDING ENDPOINTS =============

@vehicle_router.post("/vehicle-bids")
@_limiter.limit("10/minute")
async def place_vehicle_bid(
    request: Request,
    bid_data: VehicleBidCreate,
    user: dict = Depends(get_current_user)
):
    """
    Place a bid on a vehicle
    Enforces deposit requirement and bid increment rules
    
    BLOCKED when vehicle_bidding_enabled is False (default)
    """
    # CRITICAL: Check if vehicle bidding is enabled system-wide
    settings = await get_system_settings()
    if not settings.get("vehicle_bidding_enabled", False):
        raise HTTPException(
            status_code=403,
            detail="Vehicle bidding is currently disabled. Vehicle auctions are pending permit approval."
        )
    
    # Get listing
    listing = await db.vehicle_listings.find_one({
        "id": bid_data.vehicle_id,
        "status": VehicleListingStatus.ACTIVE.value
    })
    if not listing:
        raise HTTPException(status_code=404, detail="Active auction not found")
    
    # Check auction visibility
    if listing["visibility"] == VehicleAuctionVisibility.DEALER_ONLY.value:
        seller = await db.vehicle_sellers.find_one({"user_id": user["id"]})
        if not seller or seller["seller_type"] != "dealer":
            raise HTTPException(status_code=403, detail="This auction is for licensed dealers only")

    # iter194: Licensed-only auction gate — buyer must have approved dealer license verification
    if listing.get("auction_access") == AuctionAccessType.LICENSED_ONLY.value:
        license_doc = await db.dealer_licenses.find_one(
            {"user_id": user["id"]},
            {"_id": 0, "status": 1, "expiry_date": 1}
        )
        is_approved = license_doc and license_doc.get("status") == DealerLicenseVerificationStatus.APPROVED.value
        if not is_approved:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "dealer_license_required",
                    "message_en": "This auction is restricted to licensed dealers. Please complete dealer-license verification.",
                    "message_fr": "Cette enchère est réservée aux concessionnaires agréés. Veuillez compléter la vérification de votre permis.",
                }
            )
        # Check expiry
        expiry = license_doc.get("expiry_date") if license_doc else None
        if expiry:
            if isinstance(expiry, str):
                try:
                    expiry = datetime.fromisoformat(expiry.replace('Z', '+00:00'))
                except Exception:
                    expiry = None
            if expiry and expiry < datetime.now(timezone.utc):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "code": "dealer_license_expired",
                        "message_en": "Your dealer license has expired. Please re-verify before bidding.",
                        "message_fr": "Votre permis de concessionnaire a expiré. Veuillez le renouveler avant d'enchérir.",
                    }
                )

    # iter201 — Phase 3 / 3A — Province-aware buyer gate.
    # Skip for parts_accessories (CEO constraint #3 — parts are open to everyone).
    listing_category = (listing.get("category_id") or "").lower()
    if listing_category != "parts_accessories":
        from routes.vehicle_buyer_verification import (
            OPEN_PROVINCES,
            RESTRICTED_PROVINCES,
            QC_DISCLOSURE_PROVINCE,
            TERRITORY_PROVINCES,
            _get_buyer_province,
        )
        buyer_doc = await db.users.find_one(
            {"id": user["id"]},
            {"_id": 0, "province": 1, "vehicle_buyer_verification": 1},
        )
        province = _get_buyer_province(buyer_doc or {})
        if not province:
            raise HTTPException(status_code=403, detail={
                "code": "province_required",
                "message_en": "Please set your province in Profile Settings to confirm your eligibility to bid on vehicles.",
                "message_fr": "Veuillez définir votre province dans les paramètres de profil pour confirmer votre admissibilité aux enchères de véhicules.",
            })

        bv = (buyer_doc or {}).get("vehicle_buyer_verification") or {}

        if province in RESTRICTED_PROVINCES:
            # iter201 — Honour verification only if it was issued for the current province.
            bv_province = (bv.get("province") or "").upper()
            if not (bv.get("verified") and bv_province == province):
                state = bv.get("status") or "not_submitted"
                raise HTTPException(status_code=403, detail={
                    "code": "buyer_verification_required",
                    "state": state,
                    "province": province,
                    "message_en": "This province restricts vehicle auction purchases to licensed dealers. Please complete buyer verification before bidding.",
                    "message_fr": "Cette province limite l'achat de véhicules aux enchères aux concessionnaires licenciés. Veuillez compléter la vérification d'acheteur avant d'enchérir.",
                })

        if province == QC_DISCLOSURE_PROVINCE:
            qc_acks = bv.get("qc_lpc_ack") or {}
            if not qc_acks.get(listing.get("id")):
                raise HTTPException(status_code=403, detail={
                    "code": "qc_lpc_ack_required",
                    "listing_id": listing.get("id"),
                    "province": "QC",
                    "message_en": "Please acknowledge the Quebec Consumer Protection (LPC) disclosure for this listing before bidding.",
                    "message_fr": "Veuillez reconnaître la divulgation LPC du Québec pour cette annonce avant d'enchérir.",
                })

        if province in TERRITORY_PROVINCES:
            await db.audit_logs.insert_one({
                "action": "territory_vehicle_bid",
                "user_id": user["id"],
                "province": province,
                "vehicle_id": bid_data.vehicle_id,
                "amount": bid_data.amount,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    # Check auction timing
    now = datetime.now(timezone.utc)
    start_time = listing["start_time"]
    end_time = listing["end_time"]
    
    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    if isinstance(end_time, str):
        end_time = datetime.fromisoformat(end_time.replace('Z', '+00:00'))
    
    if now < start_time:
        raise HTTPException(status_code=400, detail="Auction has not started yet")
    if now > end_time:
        raise HTTPException(status_code=400, detail="Auction has ended")
    
    # Check deposit requirement
    if listing["requires_deposit"]:
        deposit = await db.vehicle_bid_deposits.find_one({
            "vehicle_id": bid_data.vehicle_id,
            "bidder_id": user["id"],
            "status": {"$in": ["paid", "authorized"]}
        })
        if not deposit:
            raise HTTPException(
                status_code=402, 
                detail=f"Deposit of ${listing['deposit_amount']} required before bidding"
            )
    
    # Validate bid amount
    current_bid = listing["current_bid"]
    starting_price = listing["starting_price"]
    bid_increment = listing["bid_increment"]
    
    min_bid = max(starting_price, current_bid + bid_increment) if current_bid > 0 else starting_price
    
    if bid_data.amount < min_bid:
        raise HTTPException(
            status_code=400, 
            detail=f"Minimum bid is ${min_bid:.2f} (current: ${current_bid:.2f} + increment: ${bid_increment:.2f})"
        )
    
    # Cannot bid on own listing
    if listing["seller_user_id"] == user["id"]:
        raise HTTPException(status_code=400, detail="Cannot bid on your own vehicle")
    
    # Create anonymized bidder name
    bidder_name = f"Bidder ***{user['id'][-4:]}"
    
    # Create bid
    bid_id = str(uuid.uuid4())
    bid = {
        "id": bid_id,
        "vehicle_id": bid_data.vehicle_id,
        "bidder_id": user["id"],
        "bidder_name": bidder_name,
        "amount": bid_data.amount,
        "max_bid": bid_data.max_bid,
        "status": BidStatus.WINNING.value,
        "deposit_paid": listing["requires_deposit"],
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.vehicle_bids.insert_one(bid)
    
    # Update previous highest bid status
    if listing["highest_bidder_id"]:
        await db.vehicle_bids.update_many(
            {
                "vehicle_id": bid_data.vehicle_id,
                "bidder_id": listing["highest_bidder_id"],
                "status": BidStatus.WINNING.value
            },
            {"$set": {"status": BidStatus.OUTBID.value}}
        )
    
    # Update listing
    update_data = {
        "current_bid": bid_data.amount,
        "highest_bidder_id": user["id"],
        "updated_at": datetime.now(timezone.utc)
    }
    
    # Check if reserve met
    if listing["reserve_price"] and bid_data.amount >= listing["reserve_price"]:
        update_data["reserve_met"] = True
    
    # Anti-sniping: extend auction if bid in last 2 minutes
    time_remaining = (end_time - now).total_seconds()
    if time_remaining < 120:  # 2 minutes
        new_end_time = now + timedelta(minutes=2)
        update_data["end_time"] = new_end_time
        logger.info(f"Anti-sniping: Extended auction {bid_data.vehicle_id} to {new_end_time}")
    
    await db.vehicle_listings.update_one(
        {"id": bid_data.vehicle_id},
        {
            "$set": update_data,
            "$inc": {"bid_count": 1}
        }
    )
    
    bid.pop("_id", None)
    return {
        "message": "Bid placed successfully",
        "bid": bid,
        "new_current_bid": bid_data.amount,
        "reserve_met": update_data.get("reserve_met", listing.get("reserve_met", False))
    }


@vehicle_router.post("/vehicle-bids/deposit")
async def pay_bid_deposit(
    vehicle_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Pay refundable bid deposit
    Required before bidding on vehicles that require deposit
    """
    listing = await db.vehicle_listings.find_one({"id": vehicle_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    if not listing["requires_deposit"]:
        return {"message": "No deposit required for this auction"}
    
    # Check existing deposit
    existing = await db.vehicle_bid_deposits.find_one({
        "vehicle_id": vehicle_id,
        "bidder_id": user["id"],
        "status": "paid"
    })
    if existing:
        return {"message": "Deposit already paid", "deposit": existing}
    
    # In production, integrate with Stripe to create payment intent
    # For now, create deposit record
    deposit = {
        "id": str(uuid.uuid4()),
        "vehicle_id": vehicle_id,
        "bidder_id": user["id"],
        "amount": listing["deposit_amount"],
        "status": "paid",  # In production, start as "pending"
        "payment_intent_id": f"demo_pi_{uuid.uuid4()}",
        "created_at": datetime.now(timezone.utc),
        "paid_at": datetime.now(timezone.utc)
    }
    
    await db.vehicle_bid_deposits.insert_one(deposit)
    
    deposit.pop("_id", None)
    return {"message": "Deposit paid successfully", "deposit": deposit}


@vehicle_router.get("/vehicle-bids/my")
async def get_my_bids(
    user: dict = Depends(get_current_user)
):
    """Get user's bid history"""
    cursor = db.vehicle_bids.find(
        {"bidder_id": user["id"]},
        {"_id": 0}
    ).sort("created_at", -1)
    bids = await cursor.to_list(length=100)
    
    # Enrich with vehicle info
    for bid in bids:
        vehicle = await db.vehicle_listings.find_one(
            {"id": bid["vehicle_id"]},
            {"_id": 0, "title": 1, "year": 1, "make": 1, "model": 1, 
             "current_bid": 1, "status": 1, "end_time": 1}
        )
        bid["vehicle"] = vehicle
    
    return {"bids": bids}


# ============= LEGAL ACCEPTANCE =============

@vehicle_router.post("/vehicles/{vehicle_id}/accept-terms")
async def accept_bidding_terms(
    vehicle_id: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """Accept As-Is Where-Is and bidding terms before bidding"""
    listing = await db.vehicle_listings.find_one({"id": vehicle_id})
    if not listing:
        listing = await db.listings.find_one({"id": vehicle_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Record acceptance
    acceptance = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "vehicle_id": vehicle_id,
        "acceptance_type": "bid_terms",
        "accepted": True,
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
        "created_at": datetime.now(timezone.utc)
    }
    
    await db.vehicle_legal_acceptances.insert_one(acceptance)
    
    return {"message": "Terms accepted", "acceptance_id": acceptance["id"]}




# Admin, Invoice, Documents, and Tax endpoints are in vehicles_admin.py
from routes.vehicles_admin import vehicle_admin_router  # noqa: E402, F401
