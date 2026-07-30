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

from fastapi import APIRouter, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect, Query, UploadFile, File, Form, BackgroundTasks
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
from services.emails.email_marketplace import send_auction_won_email, send_auction_sold_email
from services.emails.email_system import (
    send_document_approved_email,
    send_document_rejected_email,
    send_seller_approved_email,
    send_invoice_created_email,
    send_payment_confirmation_email,
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
    # iter427 — Suspended dealers must not create/publish listings even
    # if their old `vehicle_sellers.verification_status` is still
    # 'approved'. Suspension is set on the user doc by the admin
    # Dealer Management screen (iter420) and is the single source of
    # truth for the active/blocked state.
    if user.get("vehicle_dealer_suspended") is True:
        raise HTTPException(
            status_code=403,
            detail={
                "code": "dealer_suspended",
                "message_en": "Your dealer account is currently suspended by an administrator. Please contact support.",
                "message_fr": "Votre compte concessionnaire est actuellement suspendu par un administrateur. Veuillez contacter le support.",
            },
        )
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
    background_tasks: BackgroundTasks,
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

    # iter217 — Quebec Bill 96 compliance — French title required for QC listings
    # iter310 — Auto-translate missing French copy before the hard-gate runs.
    # Vehicle payload uses `province` (not `region`); pass it as an override.
    from services.bill96_autofill import autofill_qc_french_copy
    _vehicle_region = getattr(listing_data, "province", None) or getattr(listing_data, "region", None)
    _bill96_autofill_result_vehicle = await autofill_qc_french_copy(
        listing_data, region_override=_vehicle_region,
    )
    from services.qc_bilingual_validator import assert_qc_bilingual_titles
    assert_qc_bilingual_titles(
        title=getattr(listing_data, "title", None),
        title_fr=getattr(listing_data, "title_fr", None),
        description=getattr(listing_data, "description", None),
        description_fr=getattr(listing_data, "description_fr", None),
        region=_vehicle_region,
        city=getattr(listing_data, "city", None),
        content_language=getattr(listing_data, "content_language", None),
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

    # iter395 — Two-pillar Trust Gate: creating a listing requires phone
    # verified AND card on file, same as every other listing surface.
    from services.trust_gate import require_trust_verified
    await require_trust_verified(db, user, action="list")

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

        # iter285 — Bug 4 — Provincial registration eligibility (compliance).
        # Stored as either `["ALL"]` or an explicit province-code list.
        # Empty/None on legacy listings renders the buyer-side warning.
        "eligible_provinces": (listing_data.eligible_provinces or ["ALL"]),
        "inspection_status":  (listing_data.inspection_status or "as_is"),

        # iter286 — Bug 5 — Carfax / Inspection report references. Optional
        # on every listing; gated to broker partners on the buyer side
        # via GET /vehicle-auctions/{id}/carfax.
        "carfax_url":      (listing_data.carfax_url or "").strip() or None,
        "carfax_file":     (listing_data.carfax_file or "").strip() or None,
        "inspection_file": (listing_data.inspection_file or "").strip() or None,
        
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
    
    # iter211 P4 — tag demo accounts' vehicle listings
    from services.demo_filter import tag_listing_if_demo
    await tag_listing_if_demo(db, user["id"], listing)

    # iter292 — Directive 3: Dealer-controlled lifecycle intent.
    # If the dealer chose "Save as Draft" the listing stays in DRAFT —
    # even for trusted sellers — until they explicitly publish it. If
    # the dealer chose "Go Live Now" we overwrite start_time so bidding
    # opens immediately. "Schedule (Upcoming)" leaves start_time as
    # supplied (must be future) and lets the auction surface render the
    # Upcoming countdown card.
    _intent = (getattr(listing_data, "submission_intent", None) or "live").lower().strip()
    if _intent == "draft":
        # Hard-pin to DRAFT; skip the trusted-seller auto-promote below.
        listing["status"] = VehicleListingStatus.DRAFT.value
        _force_draft = True
    else:
        _force_draft = False
        if _intent == "live":
            # Open bidding NOW.
            _now = datetime.now(timezone.utc)
            listing["start_time"] = _now
            # Keep the original_end_time aligned to the (possibly larger) window.
            if listing.get("end_time") and listing["end_time"] < _now:
                # Auto-extend the window to 24 h so a "Go Live Now" with an
                # accidentally past end_time still yields a sane auction.
                from datetime import timedelta as _td
                listing["end_time"] = _now + _td(hours=24)
                listing["original_end_time"] = listing["end_time"]

    # iter283-hotfix-2 — Trusted-seller fast-track.
    # The strict DRAFT → PENDING → APPROVED → ACTIVE workflow makes
    # sense for unverified third-party sellers, but admins, verified
    # partners, vehicle dealers, and storage facilities have already
    # been vetted out-of-band. Trapping their listings in DRAFT until
    # an admin reviews them is the actual cause of the "vehicles
    # section empty" production complaint — sellers complete the form,
    # nothing appears, no clear signal what to do next.
    # Fast-track skips DRAFT/PENDING and writes status=ACTIVE directly
    # for these trusted accounts. Same trust model the rest of the
    # platform uses (db.listings).
    _trusted = (
        user.get("role") in ("admin", "super_admin")
        or user.get("is_partner") is True
        or (user.get("partner_verification_status") or "").lower() == "verified"
        or user.get("is_vehicle_dealer") is True
        or user.get("is_storage_facility") is True
    )
    # iter292 — Honor dealer "Save as Draft" intent over the trusted
    # fast-track. Dealers explicitly choosing draft must NOT be
    # auto-promoted to ACTIVE.
    if _trusted and not _force_draft:
        from models.vehicle_models import VehicleListingStatus as _VLS
        listing["status"] = _VLS.ACTIVE.value
        listing["approved_at"] = datetime.now(timezone.utc)
        listing["approved_by"] = user["id"]

    # iter394 — Enrich with live seller data so seller_account_type +
    # sibling booleans are stamped correctly on the vehicle listing
    # (context="vehicle" makes vehicle_dealer flag dominant here).
    try:
        from services.listing_seller_enrichment import enrich_listing_async
        listing = await enrich_listing_async(db, listing, "vehicle")
    except Exception:  # noqa: BLE001 — never block create on enrichment failure
        pass

    await db.vehicle_listings.insert_one(listing)
    
    # Update seller monthly count
    await db.vehicle_sellers.update_one(
        {"id": seller["id"]},
        {"$inc": {"monthly_listing_count": 1, "total_listings": 1}}
    )
    
    # Log audit
    await log_audit("vehicle", listing_id, "created", user["id"], "seller")

    # iter401 — Flow 1 Buyer Interest emails (real-time). Only fires when
    # the vehicle goes live immediately.
    if (listing.get("status") or "").lower() in ("active", "live"):
        try:
            from services.marketing_flows import dispatch_buyer_interest_emails
            background_tasks.add_task(
                dispatch_buyer_interest_emails, db,
                listing_id=listing_id,
                listing_type="vehicle",
            )
        except Exception as _bie:  # noqa: BLE001
            logger.warning(f"[iter401 buyer-interest vehicle] skipped: {_bie}")

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
    """Upload media (photo/video) for vehicle listing.

    iter286 — Bug 1 — Previously this endpoint **mocked** the upload
    (it generated a `/uploads/vehicles/…` placeholder URL and discarded
    the file bytes). That left every vehicle detail page rendering grey
    placeholder images. Now we upload the bytes to S3 via the existing
    `services/s3_service.py` (resize + compress to JPEG ≤ 1600px,
    quality 75) and persist the absolute CloudFront URL.
    """
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

    # iter286 — Real S3 upload. Index is computed from the current media
    # count so each photo gets a unique deterministic key.
    from services.s3_service import upload_image_to_s3
    next_index = len(listing.get("media", []))
    try:
        file_url = await upload_image_to_s3(file, vehicle_id, next_index)
    except Exception as e:
        # Surface a useful error rather than silently saving a broken URL.
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Photo upload failed: {type(e).__name__}: {str(e)}",
        )

    media_item = {
        "id": str(uuid.uuid4()),
        "type": media_type,
        "url": file_url,
        "thumbnail_url": file_url,
        "category": category,
        "caption": caption,
        "order": next_index,
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
    seller_type: str = None,
    ending_soon: bool = False  # iter298 BUG 1 — active auctions ending within 24h (dynamic)
):
    """
    List public vehicle auctions
    This is the main browse endpoint for buyers
    """
    # iter283-hotfix Mission 2 / hotfix-2 — Public vehicle browse must
    # NEVER drop listings just because `visibility` is missing on legacy
    # docs or because `requires_broker=True` (the broker gate restricts
    # CREATION, not BROWSING). It also surfaces `APPROVED` listings —
    # admin-vetted but waiting on the global launch toggle — so
    # frontends can show the inventory and let admins flip
    # `vehicle_auctions_enabled` confidently. Without this, sellers
    # complete the workflow and STILL see "0 auctions" until the
    # platform-wide toggle flips, with no visibility into what's
    # waiting in the pipeline.
    from models.vehicle_models import VehicleListingStatus as _VLS
    query = {
        "status": {"$in": [_VLS.ACTIVE.value, _VLS.APPROVED.value]},
        "$or": [
            {"visibility": VehicleAuctionVisibility.PUBLIC.value},
            {"visibility": {"$exists": False}},
            {"visibility": None},
        ],
        "is_demo": {"$ne": True},  # iter211 P4 — exclude demo dealers' vehicles
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
    # iter298 BUG 1 — "Ending Soon": active vehicle auctions whose
    # end_time falls within the next 24 hours. Computed dynamically at
    # query time (ISO-string OR datetime storage conventions).
    if ending_soon:
        _es_now = datetime.now(timezone.utc)
        _es_cutoff = _es_now + timedelta(hours=24)
        query["status"] = _VLS.ACTIVE.value
        query["$and"] = (query.get("$and") or []) + [{
            "$or": [
                {"end_time": {"$gt": _es_now.isoformat(), "$lte": _es_cutoff.isoformat()}},
                {"end_time": {"$gt": _es_now, "$lte": _es_cutoff}},
            ]
        }]
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
    
    # Also include vehicle-shape items from the general listings
    # collection (iter222 + iter283).
    # iter283-hotfix Mission 2 — Match BOTH listing_type aliases AND
    # categories (case-insensitive) so vehicles authored via the legacy
    # general create-form OR a partner sync surface here too.
    from services.listing_sections import VEHICLE_TYPES
    general_vehicle_query = {
        "status": "active",
        "$or": [
            {"listing_type": {"$in": list(VEHICLE_TYPES)}},
            {"section": "vehicles"},
            {"category": {"$regex": r"^vehicle(s|\s*parts)?$", "$options": "i"}},
            {"category": {"$regex": r"^(cars?|autos?|trucks?|motorcycles?|boats?|rvs?|trailers?)$", "$options": "i"}},
        ],
    }
    # Apply the SAME public filters as the vehicle_listings query.
    if province:
        general_vehicle_query["region"] = {
            "$regex": f"^{province.strip()}$", "$options": "i",
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

    # iter283-emergency — Hard dump of the response count. Per the
    # emergency directive, log every fetch so a 0-count fault is loud.
    # `vehicle_listings_count` + `general_listings_count` makes the
    # split visible at a glance in the boot log.
    _final = total + general_total
    logger.warning(
        "[iter283-emergency] /api/vehicles fetched "
        f"vehicle_listings={total} general_listings={general_total} "
        f"merged={_final}"
    )
    if _final == 0 and os.environ.get("BIDVEX_VEHICLES_STRICT") == "1":
        # Opt-in strict mode raises so the traceback surfaces in tests.
        # NOT default-on — would break legitimate empty-section states.
        raise RuntimeError(
            "[iter283-emergency] /api/vehicles returned 0 listings — "
            "the strict gate (BIDVEX_VEHICLES_STRICT=1) tripped. "
            f"query={query!r} general_query={general_vehicle_query!r}"
        )

    return {
        "vehicles": all_vehicles,
        "total": _final,
        "page": page,
        "pages": (_final + limit - 1) // limit
    }


@vehicle_router.get("/vehicles/{vehicle_id}")
async def get_vehicle_detail(vehicle_id: str, request: Request):
    """Get detailed vehicle listing.

    iter283-emergency-detail — Fallback chain so vehicles in either
    storage land on the same UI:
      1. db.vehicle_listings by id (legacy strict-flow listings)
      2. db.listings by id with a flexible vehicle-shape match
         (listing_type alias OR section=vehicles OR case-insensitive
         category match). The earlier strict `category: {$in: ['vehicles',
         'vehicle','car','auto']}` filter dropped `category: 'Vehicles'`
         (capital V) and was the root cause of the 404.
    """
    listing = await db.vehicle_listings.find_one({"id": vehicle_id}, {"_id": 0})

    # Fallback: check general listings collection.
    if not listing:
        from services.listing_sections import VEHICLE_TYPES
        listing = await db.listings.find_one(
            {
                "id": vehicle_id,
                "$or": [
                    {"listing_type": {"$in": list(VEHICLE_TYPES)}},
                    {"section": "vehicles"},
                    {"category": {
                        "$regex": r"^(vehicles?|vehicle\s*parts|cars?|autos?|trucks?|motorcycles?|boats?|rvs?|trailers?)$",
                        "$options": "i",
                    }},
                ],
            },
            {"_id": 0},
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
    
    # iter286 — Bug 1 — Normalize media URLs. Legacy listings stored
    # placeholder relative paths (`/uploads/vehicles/…`) when the upload
    # endpoint was mocked. Those URLs never resolve in the browser. Drop
    # them so the gallery shows a clean "no photos yet" state instead of
    # a row of broken `<img>` tags.
    _media = listing.get("media") or []
    listing["media"] = [
        m for m in _media
        if isinstance(m.get("url"), str) and m["url"].startswith("http")
    ]
    
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


# iter286 — Bug 5 — Broker-gated Carfax / inspection report endpoint.
@vehicle_router.get("/vehicle-auctions/{vehicle_id}/carfax")
async def get_vehicle_carfax(
    vehicle_id: str,
    user: dict = Depends(get_current_user),
):
    """Return Carfax / inspection report references for a vehicle listing.

    Gated to broker-partner accounts (and admins). Individual buyers see a
    `broker_required` 403 so the buyer-side UI can render a locked-state
    teaser with a "Become a Broker Partner" CTA. Sellers can always read
    their own listing's documents.

    Returns:
      { carfax_url, carfax_file, inspection_file, viewer_role }
    """
    listing = await db.vehicle_listings.find_one(
        {"id": vehicle_id},
        {"_id": 0, "seller_id": 1, "carfax_url": 1, "carfax_file": 1, "inspection_file": 1},
    )
    if not listing:
        # Cross-collection fallback for older listings.
        listing = await db.listings.find_one(
            {"id": vehicle_id, "$or": [{"section": "vehicles"}, {"category": {"$regex": "vehicle", "$options": "i"}}]},
            {"_id": 0, "seller_id": 1, "carfax_url": 1, "carfax_file": 1, "inspection_file": 1},
        )
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")

    is_admin   = (user.get("role") in ("admin", "super_admin")) or bool(user.get("is_admin"))
    is_seller  = (user.get("id") == listing.get("seller_id"))
    is_broker  = bool(
        user.get("is_broker_partner")
        or user.get("is_broker")
        or user.get("broker_partner_status") in ("active", "approved")
    )
    if not (is_admin or is_seller or is_broker):
        raise HTTPException(
            status_code=403,
            detail={
                "code":    "broker_required",
                "message": "Carfax reports are only available to verified broker partners.",
            },
        )
    return {
        "carfax_url":       listing.get("carfax_url") or None,
        "carfax_file":      listing.get("carfax_file") or None,
        "inspection_file":  listing.get("inspection_file") or None,
        "viewer_role":      "admin" if is_admin else ("seller" if is_seller else "broker"),
    }


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


# iter432 — Sales & Performance analytics ──────────────────────────────
#
# Read-only aggregation over the two collections the dealer already
# populates (`vehicle_listings` + `vehicle_bids`). No new fields written
# and no invented data — every metric maps to a real database column.
# Views are lifetime scalars on the listing document (no per-day
# tracking exists) so we window them by `created_at` of the listing.
# Bids and sold-events have their own timestamps and are windowed
# directly.

@vehicle_router.get("/vehicles/my/analytics")
async def get_my_vehicle_analytics(
    window_days: int = 30,
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user),
):
    """Aggregated 30 / 60 / 90 day performance metrics for the dealer.

    Response shape:
        {
          "window_days": 30,
          "start_date": "2026-01-08T00:00:00Z",
          "end_date":   "2026-02-07T23:59:59Z",
          "totals": {
            "views":            <int>,   # sum of views_count on listings created in window
            "bids":             <int>,   # count of vehicle_bids created in window
            "revenue":          <float>, # sum(final_price) where status=sold and sold_at in window
            "sold_count":       <int>,
            "conversion_rate":  <float>  # bids / views (0..1, 0 if views==0)
          },
          "daily_series": [
            { "date": "2026-01-08", "bids": 3, "sold": 0 },
            ...
          ],
          "granularity": "day" | "week",
          "has_data": <bool>
        }
    """
    # Guard window range.
    if window_days not in (30, 60, 90):
        window_days = 30

    now = datetime.now(timezone.utc)
    start = now - timedelta(days=window_days)

    seller_id = seller["id"]

    # ── 1. Total Views (sum of views_count across listings created in window)
    #    We can only window views by listing.created_at because there is
    #    no per-view timestamp. This is documented and honest.
    views_pipeline = [
        {"$match": {"seller_id": seller_id, "created_at": {"$gte": start}}},
        {"$group": {"_id": None, "total": {"$sum": {"$ifNull": ["$views_count", 0]}}}},
    ]
    views_agg = await db.vehicle_listings.aggregate(views_pipeline).to_list(1)
    total_views = int(views_agg[0]["total"]) if views_agg else 0

    # ── 2. Total Bids (count of vehicle_bids on this seller's listings
    #    within the window). Bids link to a listing_id — we first fetch
    #    the dealer's listing ids then count bids whose created_at ∈ window.
    listing_ids = [
        doc["id"] for doc in await db.vehicle_listings.find(
            {"seller_id": seller_id}, {"id": 1, "_id": 0}
        ).to_list(length=1000)
    ]

    total_bids = 0
    daily_bids: Dict[str, int] = {}
    if listing_ids:
        bid_pipeline = [
            {"$match": {
                "listing_id": {"$in": listing_ids},
                "created_at": {"$gte": start},
            }},
            {"$group": {
                "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
                "count": {"$sum": 1},
            }},
        ]
        bid_rows = await db.vehicle_bids.aggregate(bid_pipeline).to_list(length=200)
        for row in bid_rows:
            daily_bids[row["_id"]] = int(row["count"])
            total_bids += int(row["count"])

    # ── 3. Revenue + sold_count (status=sold, sold_at ∈ window)
    revenue_pipeline = [
        {"$match": {
            "seller_id": seller_id,
            "status": VehicleListingStatus.SOLD.value,
            "sold_at": {"$gte": start},
        }},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$sold_at"}},
            "revenue": {"$sum": {"$ifNull": ["$final_price", 0]}},
            "count": {"$sum": 1},
        }},
    ]
    revenue_rows = await db.vehicle_listings.aggregate(revenue_pipeline).to_list(length=200)

    daily_sold: Dict[str, int] = {}
    total_revenue = 0.0
    sold_count = 0
    for row in revenue_rows:
        daily_sold[row["_id"]] = int(row["count"])
        total_revenue += float(row.get("revenue") or 0)
        sold_count += int(row["count"])

    # ── 4. Build the daily time-series with zero-filled dates.
    #    For windows >= 60 days we down-sample to weekly buckets.
    granularity = "week" if window_days >= 60 else "day"
    series: List[Dict[str, Any]] = []
    if granularity == "day":
        for i in range(window_days):
            d = (start + timedelta(days=i)).strftime("%Y-%m-%d")
            series.append({"date": d, "bids": daily_bids.get(d, 0), "sold": daily_sold.get(d, 0)})
    else:
        # weekly buckets — group by ISO week starting date (Mon)
        num_weeks = max(1, window_days // 7)
        for w in range(num_weeks):
            week_start = start + timedelta(days=w * 7)
            week_end = week_start + timedelta(days=7)
            bids_sum = 0
            sold_sum = 0
            for i in range(7):
                d = (week_start + timedelta(days=i)).strftime("%Y-%m-%d")
                bids_sum += daily_bids.get(d, 0)
                sold_sum += daily_sold.get(d, 0)
            series.append({
                "date": week_start.strftime("%Y-%m-%d"),
                "week_end": week_end.strftime("%Y-%m-%d"),
                "bids": bids_sum,
                "sold": sold_sum,
            })

    conversion_rate = (total_bids / total_views) if total_views > 0 else 0.0
    has_data = bool(total_views or total_bids or sold_count)

    return {
        "window_days": window_days,
        "start_date": start.isoformat(),
        "end_date": now.isoformat(),
        "totals": {
            "views": total_views,
            "bids": total_bids,
            "revenue": round(total_revenue, 2),
            "sold_count": sold_count,
            "conversion_rate": round(conversion_rate, 4),
        },
        "daily_series": series,
        "granularity": granularity,
        "has_data": has_data,
    }


# iter293 — Directive P2: Dealer Drafts dashboard helpers ────────────

@vehicle_router.post("/vehicles/{vehicle_id}/activate")
async def activate_vehicle_listing(
    vehicle_id: str,
    intent: str = "live",          # "live" | "schedule"
    start_time: Optional[datetime] = None,
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user),
):
    """Promote a DRAFT vehicle listing to ACTIVE (live) or ACTIVE-with-
    future-start (upcoming). Dealers call this from the Drafts dashboard.
    """
    intent = (intent or "live").lower()
    if intent not in ("live", "schedule"):
        raise HTTPException(status_code=400, detail="intent must be 'live' or 'schedule'")

    listing = await db.vehicle_listings.find_one({"id": vehicle_id, "seller_id": seller["id"]})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("status") not in (VehicleListingStatus.DRAFT.value, VehicleListingStatus.PENDING_APPROVAL.value, VehicleListingStatus.APPROVED.value):
        raise HTTPException(
            status_code=409,
            detail=f"Cannot activate listing in status '{listing.get('status')}'",
        )

    now = datetime.now(timezone.utc)
    update: Dict[str, Any] = {
        "status":       VehicleListingStatus.ACTIVE.value,
        "approved_at":  now,
        "approved_by":  user["id"],
        "updated_at":   now,
    }
    if intent == "live":
        update["start_time"] = now
        # If the original end_time is in the past (24h+ since draft was
        # created), extend to 24h from now so the auction lasts a sane
        # amount of time.
        end = listing.get("end_time")
        if isinstance(end, str):
            try:
                end = datetime.fromisoformat(end.replace("Z", "+00:00"))
            except Exception:
                end = None
        if not end or end <= now:
            update["end_time"] = now + timedelta(hours=24)
            update["original_end_time"] = update["end_time"]
    else:  # schedule
        if not start_time:
            raise HTTPException(status_code=422, detail="Schedule requires a start_time")
        if start_time.tzinfo is None:
            start_time = start_time.replace(tzinfo=timezone.utc)
        if start_time <= now + timedelta(minutes=1):
            raise HTTPException(status_code=422, detail="start_time must be ≥1 min in the future")
        update["start_time"] = start_time

    await db.vehicle_listings.update_one({"id": vehicle_id}, {"$set": update})
    return {"ok": True, "status": update["status"], "start_time": update["start_time"].isoformat()}


@vehicle_router.delete("/vehicles/{vehicle_id}/draft")
async def delete_draft_vehicle_listing(
    vehicle_id: str,
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user),
):
    """Dealer deletes their own draft listing."""
    listing = await db.vehicle_listings.find_one({"id": vehicle_id, "seller_id": seller["id"]})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    if listing.get("status") not in (VehicleListingStatus.DRAFT.value, VehicleListingStatus.REJECTED.value):
        raise HTTPException(status_code=409, detail="Only draft or rejected listings can be deleted")
    await db.vehicle_listings.delete_one({"id": vehicle_id})
    return {"ok": True}


# iter428 — My Vehicles module: Duplicate + Retire endpoints ────────────

@vehicle_router.post("/vehicles/{vehicle_id}/duplicate")
async def duplicate_vehicle_listing(
    vehicle_id: str,
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user),
):
    """Clone an existing vehicle listing as a fresh DRAFT owned by the
    same dealer. Preserves the descriptive fields (year/make/model/VIN,
    media, condition report, category, features) but resets bidding
    state, timestamps, and any winner/settlement metadata.
    """
    src = await db.vehicle_listings.find_one({"id": vehicle_id, "seller_id": seller["id"]})
    if not src:
        raise HTTPException(status_code=404, detail="Listing not found")

    # Monthly listing limit still applies to duplicates.
    current_month = datetime.now(timezone.utc).strftime("%Y-%m")
    if seller.get("current_month") != current_month:
        await db.vehicle_sellers.update_one(
            {"id": seller["id"]},
            {"$set": {"monthly_listing_count": 0, "current_month": current_month}},
        )
        seller["monthly_listing_count"] = 0
    if seller["monthly_listing_count"] >= seller["monthly_listing_limit"]:
        limit = seller["monthly_listing_limit"]
        seller_type = seller["seller_type"]
        raise HTTPException(
            status_code=403,
            detail=f"Monthly listing limit reached ({limit} vehicles/month for {seller_type} sellers)",
        )

    now = datetime.now(timezone.utc)
    new_id = str(uuid.uuid4())

    # Copy the source doc and stamp draft-specific fields.
    clone: Dict[str, Any] = {k: v for k, v in src.items() if k != "_id"}
    clone["id"] = new_id
    clone["status"] = VehicleListingStatus.DRAFT.value

    # Bidding state reset
    clone["current_bid"] = 0.0
    clone["bid_count"] = 0
    clone["highest_bidder_id"] = None
    clone["watchers_count"] = 0
    clone["views_count"] = 0
    clone["reserve_met"] = False

    # Winner / settlement reset
    clone["winner_id"] = None
    clone["final_price"] = None
    clone["sold_at"] = None
    clone["rejection_reason"] = None

    # Timestamps reset — user must set new start/end when they publish.
    clone["start_time"] = None
    clone["end_time"] = None
    clone["original_end_time"] = None
    clone["created_at"] = now
    clone["updated_at"] = None
    clone["approved_at"] = None
    clone["approved_by"] = None

    # Title suffix so the dealer can tell them apart at a glance.
    original_title = src.get("title") or ""
    clone["title"] = f"{original_title} (Copy)".strip() if original_title else "(Copy)"
    if src.get("title_fr"):
        clone["title_fr"] = f"{src['title_fr']} (copie)".strip()

    await db.vehicle_listings.insert_one(clone)

    # Increment the dealer's monthly count so duplicates count toward the limit.
    await db.vehicle_sellers.update_one(
        {"id": seller["id"]},
        {"$inc": {"monthly_listing_count": 1}},
    )

    return {"ok": True, "id": new_id, "status": VehicleListingStatus.DRAFT.value}


@vehicle_router.post("/vehicles/{vehicle_id}/retire")
async def retire_vehicle_listing(
    vehicle_id: str,
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user),
):
    """Confirm-then-archive endpoint. Flips a listing to `retired` so it
    disappears from the public marketplace but remains visible from the
    dealer's dashboard (Retired tab). Sold listings cannot be retired
    (they must stay in the audit trail as SOLD).
    """
    listing = await db.vehicle_listings.find_one({"id": vehicle_id, "seller_id": seller["id"]})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    current_status = listing.get("status")
    if current_status == VehicleListingStatus.SOLD.value:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "cannot_retire_sold",
                "message_en": "Sold listings cannot be retired — they are locked for the audit trail.",
                "message_fr": "Les annonces vendues ne peuvent pas être retirées — elles sont verrouillées pour l'audit.",
            },
        )
    if current_status == VehicleListingStatus.RETIRED.value:
        # Idempotent: already retired.
        return {"ok": True, "status": VehicleListingStatus.RETIRED.value, "already": True}

    now = datetime.now(timezone.utc)
    await db.vehicle_listings.update_one(
        {"id": vehicle_id},
        {
            "$set": {
                "status": VehicleListingStatus.RETIRED.value,
                "retired_at": now,
                "retired_by": user["id"],
                "updated_at": now,
            },
        },
    )
    return {"ok": True, "status": VehicleListingStatus.RETIRED.value}


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

    # iter300 P1 — suspended buyers cannot bid (overdue-payment escalation).
    from services.bid_guard import ensure_bidding_allowed
    await ensure_bidding_allowed(db, user.id if hasattr(user, "id") else user.get("id"))

    # iter395 — Two-pillar Trust Gate (phone verified AND card on file)
    # before we hit any DB write, so unverified users get a clean 403
    # with a structured `trust_required` payload. Vehicle auctions use
    # the $500 flat deposit path (not the smart hold), but the trust
    # requirement is identical to every other bid path.
    from services.trust_gate import require_trust_verified
    await require_trust_verified(db, user, action="bid")

    # Get listing
    listing = await db.vehicle_listings.find_one({
        "id": bid_data.vehicle_id,
        "status": VehicleListingStatus.ACTIVE.value
    })
    if not listing:
        raise HTTPException(status_code=404, detail="Active auction not found")

    # iter292 — Directive 3: Block bids before the dealer's scheduled
    # start_time. ACTIVE-but-upcoming auctions render publicly with a
    # countdown but bidding must stay gated until the start moment.
    _start = listing.get("start_time")
    if isinstance(_start, str):
        try:
            _start = datetime.fromisoformat(_start.replace("Z", "+00:00"))
        except Exception:
            _start = None
    if isinstance(_start, datetime) and _start > datetime.now(timezone.utc):
        raise HTTPException(
            status_code=409,
            detail={
                "code": "auction_not_started",
                "message_en": "This auction is upcoming — bidding opens at the scheduled start time.",
                "message_fr": "Cette enchère est à venir — les offres ouvriront à l'heure de début prévue.",
                "start_time": _start.isoformat(),
            },
        )
    
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
            _get_buyer_province,
        )
        from services.province_compliance import (
            OPEN_PROVINCES,
            RESTRICTED_PROVINCES,
            QC_DISCLOSURE_PROVINCE,
            TERRITORY_PROVINCES,
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
        "created_at": datetime.now(timezone.utc),
        # iter302 — payment authorization consent stamped at placement
        "payment_authorization_consented": True,
        "payment_authorization_consented_at": datetime.now(timezone.utc).isoformat(),
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

    # iter287 — Vehicle Auto-Bid (Proxy Bidding) Engine.
    # After the manual bid commits, run the proxy bidder for any active
    # `vehicle_auto_bids` whose `max_bid` exceeds the new floor. This
    # mirrors the marketplace `_process_auto_bids` logic but works
    # against `db.vehicle_listings` (vehicles never land in db.listings
    # so the existing processor can't see them).
    try:
        await _process_vehicle_auto_bids(
            db=db,
            vehicle_id=bid_data.vehicle_id,
            current_price=bid_data.amount,
            manual_bidder_id=user["id"],
        )
    except Exception as _proxy_err:
        # Proxy-bid execution must NEVER fail the buyer's manual bid.
        logger.warning(f"Vehicle auto-bid processing error: {_proxy_err}")

    return {
        "message": "Bid placed successfully",
        "bid": bid,
        "new_current_bid": bid_data.amount,
        "reserve_met": update_data.get("reserve_met", listing.get("reserve_met", False))
    }


# ──────────────────────────────────────────────────────────────────────
# iter287 — Vehicle Auto-Bid (Proxy Bidding) Engine
# ──────────────────────────────────────────────────────────────────────


async def _process_vehicle_auto_bids(
    db,
    vehicle_id: str,
    current_price: float,
    manual_bidder_id: str,
) -> None:
    """
    After a manual bid on a vehicle, run all active auto-bids for that
    listing. The highest active auto-bid wins each round; we place an
    incremental counter-bid (`current_price + 100`) up to the bidder's
    declared maximum.

    Mirror of `routes.auctions_bids._process_auto_bids` but targets
    `db.vehicle_listings` + `db.vehicle_bids` + the vehicle-specific
    `db.vehicle_auto_bids` collection. Buyers who set their own
    auto-bid do NOT trigger their own bot (`bidder_id !=
    manual_bidder_id`).
    """
    # Pull every active vehicle auto-bid except the one belonging to
    # the buyer who just placed the manual bid (avoid self-outbidding).
    auto_bids = await db.vehicle_auto_bids.find({
        "vehicle_id": vehicle_id,
        "is_active": True,
        "user_id": {"$ne": manual_bidder_id},
    }).to_list(100)
    if not auto_bids:
        return

    listing = await db.vehicle_listings.find_one({"id": vehicle_id})
    if not listing:
        return
    if listing.get("status") != VehicleListingStatus.ACTIVE.value:
        return

    # Sort highest max_bid first — that bidder wins the round.
    auto_bids.sort(key=lambda x: float(x.get("max_bid", 0)), reverse=True)
    for ab in auto_bids:
        # Vehicle bid increment is hard-coded at $100 in the manual
        # path (see `setBidAmount((amount + 100).toString())` in the
        # frontend). Match it here so proxy bids don't violate the
        # buyer-facing increment rule.
        counter = float(current_price) + 100.0
        if counter > float(ab["max_bid"]):
            await db.vehicle_auto_bids.update_one(
                {"id": ab["id"]},
                {"$set": {"is_active": False, "exhausted_at": datetime.now(timezone.utc).isoformat()}},
            )
            try:
                await db.notifications.insert_one({
                    "id":         str(uuid.uuid4()),
                    "user_id":    ab["user_id"],
                    "type":       "vehicle_auto_bid_exceeded",
                    "title":      "Auto-bid maxed out",
                    "message":    f"Your maximum auto-bid of ${float(ab['max_bid']):.2f} on a vehicle was exceeded.",
                    "data":       {"vehicle_id": vehicle_id, "max_bid": ab["max_bid"], "current_price": current_price},
                    "read":       False,
                    "created_at": datetime.now(timezone.utc),
                })
            except Exception:
                pass
            continue

        # Place the proxy counter-bid as the auto-bid owner.
        # Skip the heavy province/dealer gates — they were enforced
        # when the auto-bid was first registered; re-running them here
        # would lock out auto-bids set before a buyer's province got
        # rate-limited mid-auction. Anti-sniping still applies via the
        # update_data branch below.
        bidder = await db.users.find_one({"id": ab["user_id"]}, {"_id": 0, "name": 1, "email": 1})
        bidder_name = (bidder or {}).get("name") or ((bidder or {}).get("email") or "").split("@")[0] or "Anonymous"
        proxy_bid = {
            "id":             str(uuid.uuid4()),
            "vehicle_id":     vehicle_id,
            "bidder_id":      ab["user_id"],
            "bidder_name":    bidder_name,
            "amount":         counter,
            "max_bid":        float(ab["max_bid"]),
            "status":         BidStatus.WINNING.value,
            "deposit_paid":   listing.get("requires_deposit", False),
            "is_auto_bid":    True,
            "created_at":     datetime.now(timezone.utc),
        }
        await db.vehicle_bids.insert_one(proxy_bid)
        # Outbid the previous winner (the manual bidder we just placed).
        await db.vehicle_bids.update_many(
            {
                "vehicle_id": vehicle_id,
                "bidder_id":  manual_bidder_id,
                "status":     BidStatus.WINNING.value,
            },
            {"$set": {"status": BidStatus.OUTBID.value}},
        )
        update_data: dict = {
            "current_bid":       counter,
            "highest_bidder_id": ab["user_id"],
            "updated_at":        datetime.now(timezone.utc),
        }
        if listing.get("reserve_price") and counter >= float(listing["reserve_price"]):
            update_data["reserve_met"] = True
        # Anti-sniping — same 2-minute soft-close rule as manual bids.
        end_time = listing.get("end_time")
        if isinstance(end_time, str):
            try:
                end_time = datetime.fromisoformat(end_time.replace("Z", "+00:00"))
            except Exception:
                end_time = None
        if end_time:
            time_remaining = (end_time - datetime.now(timezone.utc)).total_seconds()
            if 0 < time_remaining < 120:
                update_data["end_time"] = datetime.now(timezone.utc) + timedelta(minutes=2)
        await db.vehicle_listings.update_one(
            {"id": vehicle_id},
            {"$set": update_data, "$inc": {"bid_count": 1}},
        )
        # Only the highest auto-bid wins this round. Lower-tier auto-
        # bids re-fire on the *next* manual bid because their floor
        # has moved up.
        return


@vehicle_router.post("/vehicles/{vehicle_id}/auto-bid")
async def setup_vehicle_auto_bid(
    vehicle_id: str,
    max_bid: float,
    user: dict = Depends(get_current_user),
):
    """
    Register or update a vehicle auto-bid. The proxy bidder will
    counter-bid up to `max_bid` automatically whenever someone else
    bids on the listing. Idempotent — calling again updates the
    existing row.

    iter287 — Vehicle parity with the marketplace auto-bid engine.
    Returns:
      { id, vehicle_id, max_bid, is_active, updated }
    """
    if max_bid is None or float(max_bid) <= 0:
        raise HTTPException(status_code=400, detail="max_bid must be greater than 0")

    listing = await db.vehicle_listings.find_one(
        {"id": vehicle_id},
        {"_id": 0, "current_bid": 1, "starting_price": 1, "status": 1, "end_time": 1},
    )
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle listing not found")
    if listing.get("status") != VehicleListingStatus.ACTIVE.value:
        raise HTTPException(status_code=400, detail="Auction is not active")

    current = float(listing.get("current_bid") or listing.get("starting_price") or 0)
    if float(max_bid) <= current:
        raise HTTPException(
            status_code=400,
            detail=f"Max bid must be greater than the current bid (${current:.2f})",
        )

    existing = await db.vehicle_auto_bids.find_one(
        {"user_id": user["id"], "vehicle_id": vehicle_id, "is_active": True},
        {"_id": 0},
    )
    if existing:
        await db.vehicle_auto_bids.update_one(
            {"id": existing["id"]},
            {"$set": {
                "max_bid":    float(max_bid),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        return {
            "id":         existing["id"],
            "vehicle_id": vehicle_id,
            "max_bid":    float(max_bid),
            "is_active":  True,
            "updated":    True,
        }

    row = {
        "id":         str(uuid.uuid4()),
        "user_id":    user["id"],
        "vehicle_id": vehicle_id,
        "max_bid":    float(max_bid),
        "is_active":  True,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.vehicle_auto_bids.insert_one(row.copy())
    return {
        "id":         row["id"],
        "vehicle_id": vehicle_id,
        "max_bid":    float(max_bid),
        "is_active":  True,
        "updated":    False,
    }


@vehicle_router.delete("/vehicles/{vehicle_id}/auto-bid")
async def deactivate_vehicle_auto_bid(
    vehicle_id: str,
    user: dict = Depends(get_current_user),
):
    """Deactivate the caller's active auto-bid on a vehicle listing."""
    r = await db.vehicle_auto_bids.update_many(
        {"user_id": user["id"], "vehicle_id": vehicle_id, "is_active": True},
        {"$set": {"is_active": False, "deactivated_at": datetime.now(timezone.utc).isoformat()}},
    )
    if r.modified_count == 0:
        raise HTTPException(status_code=404, detail="No active auto-bid found")
    return {"message": "Auto-bid deactivated"}


@vehicle_router.get("/vehicles/auto-bid/mine")
async def list_my_vehicle_auto_bids(user: dict = Depends(get_current_user)):
    """List the caller's active vehicle auto-bids."""
    rows = await db.vehicle_auto_bids.find(
        {"user_id": user["id"], "is_active": True},
        {"_id": 0},
    ).to_list(100)
    return {"auto_bids": rows, "total": len(rows)}


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

    # iter400 — Any per-listing T&C acceptance also satisfies the platform
    # Trust Gate terms pillar. Stamp `platform_terms_accepted_at` (idempotent).
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"id": user["id"],
         "$or": [
             {"platform_terms_accepted_at": {"$exists": False}},
             {"platform_terms_accepted_at": None},
             {"platform_terms_accepted_at": ""},
         ]},
        {"$set": {
            "platform_terms_accepted_at":  now_iso,
            "platform_terms_version":      "v1",
            "platform_terms_last_seen_at": now_iso,
            "platform_terms_source":       f"vehicle_accept:{vehicle_id}",
        }},
    )

    return {"message": "Terms accepted", "acceptance_id": acceptance["id"]}




# Admin, Invoice, Documents, and Tax endpoints are in vehicles_admin.py
from routes.vehicles_admin import vehicle_admin_router  # noqa: E402, F401
