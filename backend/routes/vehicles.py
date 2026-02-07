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
    # Models
    VehicleSellerCreate, VehicleSeller, VehicleSellerDocument,
    VehicleListingCreate, VehicleListing, VehicleMedia, VehicleConditionReport,
    VehicleBidCreate, VehicleBid, VehicleBidDeposit,
    VehicleInvoice, VehicleInvoiceLineItem,
    LegalAcceptance, VehicleAuditLog,
    validate_vin
)
from services.vin_decoder import decode_vin as vin_decode_service
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
    jwt_secret = os.environ.get('JWT_SECRET', 'dev-secret-key')
    
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
    return seller


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
    """
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
    limit: int = 20
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
    
    # Sort
    sort_dir = 1 if sort_order == "asc" else -1
    sort_field = sort_by if sort_by in ["end_time", "current_bid", "created_at", "year", "mileage"] else "end_time"
    
    skip = (page - 1) * limit
    
    cursor = db.vehicle_listings.find(query, {"_id": 0}).sort(sort_field, sort_dir).skip(skip).limit(limit)
    vehicles = await cursor.to_list(length=limit)
    
    total = await db.vehicle_listings.count_documents(query)
    
    return {
        "vehicles": vehicles,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit
    }


@vehicle_router.get("/vehicles/{vehicle_id}")
async def get_vehicle_detail(vehicle_id: str, request: Request):
    """Get detailed vehicle listing"""
    listing = await db.vehicle_listings.find_one({"id": vehicle_id}, {"_id": 0})
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
        {"_id": 0, "id": 1, "seller_type": 1, "business_name": 1, 
         "average_rating": 1, "total_sold": 1}
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
async def place_vehicle_bid(
    bid_data: VehicleBidCreate,
    user: dict = Depends(get_current_user)
):
    """
    Place a bid on a vehicle
    Enforces deposit requirement and bid increment rules
    """
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
            "status": "paid"
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


# ============= ADMIN ENDPOINTS =============

@vehicle_router.get("/vehicle-admin/pending-sellers")
async def get_pending_sellers(admin: dict = Depends(get_admin_user)):
    """Get sellers pending verification"""
    cursor = db.vehicle_sellers.find(
        {"verification_status": {"$in": [
            SellerVerificationStatus.PENDING.value,
            SellerVerificationStatus.UNDER_REVIEW.value
        ]}},
        {"_id": 0}
    ).sort("created_at", 1)
    sellers = await cursor.to_list(length=100)
    
    # Enrich with user info
    for seller in sellers:
        user = await db.users.find_one(
            {"id": seller["user_id"]},
            {"_id": 0, "email": 1, "full_name": 1}
        )
        seller["user"] = user
    
    return {"sellers": sellers}


@vehicle_router.post("/vehicle-admin/sellers/{seller_id}/approve")
async def approve_seller(
    seller_id: str,
    admin: dict = Depends(get_admin_user)
):
    """Approve vehicle seller"""
    seller = await db.vehicle_sellers.find_one({"id": seller_id})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    old_status = seller["verification_status"]
    
    await db.vehicle_sellers.update_one(
        {"id": seller_id},
        {
            "$set": {
                "verification_status": SellerVerificationStatus.APPROVED.value,
                "approved_at": datetime.now(timezone.utc),
                "approved_by": admin["id"],
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    await log_audit(
        "seller", seller_id, "approved", 
        admin["id"], "admin",
        old_value={"status": old_status},
        new_value={"status": SellerVerificationStatus.APPROVED.value}
    )
    
    return {"message": "Seller approved successfully"}


@vehicle_router.post("/vehicle-admin/sellers/{seller_id}/reject")
async def reject_seller(
    seller_id: str,
    reason: str,
    admin: dict = Depends(get_admin_user)
):
    """Reject vehicle seller application"""
    seller = await db.vehicle_sellers.find_one({"id": seller_id})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    old_status = seller["verification_status"]
    
    await db.vehicle_sellers.update_one(
        {"id": seller_id},
        {
            "$set": {
                "verification_status": SellerVerificationStatus.REJECTED.value,
                "rejection_reason": reason,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    await log_audit(
        "seller", seller_id, "rejected",
        admin["id"], "admin",
        old_value={"status": old_status},
        new_value={"status": SellerVerificationStatus.REJECTED.value},
        reason=reason
    )
    
    return {"message": "Seller rejected"}


@vehicle_router.get("/vehicle-admin/pending-vehicles")
async def get_pending_vehicles(admin: dict = Depends(get_admin_user)):
    """Get vehicles pending approval"""
    cursor = db.vehicle_listings.find(
        {"status": VehicleListingStatus.PENDING_APPROVAL.value},
        {"_id": 0}
    ).sort("created_at", 1)
    vehicles = await cursor.to_list(length=100)
    
    # Enrich with seller info
    for vehicle in vehicles:
        seller = await db.vehicle_sellers.find_one(
            {"id": vehicle["seller_id"]},
            {"_id": 0, "seller_type": 1, "business_name": 1}
        )
        vehicle["seller"] = seller
    
    return {"vehicles": vehicles}


@vehicle_router.post("/vehicle-admin/vehicles/{vehicle_id}/approve")
async def approve_vehicle(
    vehicle_id: str,
    admin: dict = Depends(get_admin_user)
):
    """Approve vehicle listing"""
    listing = await db.vehicle_listings.find_one({"id": vehicle_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    if listing["status"] != VehicleListingStatus.PENDING_APPROVAL.value:
        raise HTTPException(status_code=400, detail="Vehicle not pending approval")
    
    old_status = listing["status"]
    
    # Set to active if start time has passed, otherwise approved
    now = datetime.now(timezone.utc)
    start_time = listing["start_time"]
    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    
    new_status = VehicleListingStatus.ACTIVE.value if now >= start_time else VehicleListingStatus.APPROVED.value
    
    await db.vehicle_listings.update_one(
        {"id": vehicle_id},
        {
            "$set": {
                "status": new_status,
                "approved_at": datetime.now(timezone.utc),
                "approved_by": admin["id"],
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    await log_audit(
        "vehicle", vehicle_id, "approved",
        admin["id"], "admin",
        old_value={"status": old_status},
        new_value={"status": new_status}
    )
    
    return {"message": "Vehicle approved", "new_status": new_status}


@vehicle_router.post("/vehicle-admin/vehicles/{vehicle_id}/reject")
async def reject_vehicle(
    vehicle_id: str,
    reason: str,
    admin: dict = Depends(get_admin_user)
):
    """Reject vehicle listing"""
    listing = await db.vehicle_listings.find_one({"id": vehicle_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    old_status = listing["status"]
    
    await db.vehicle_listings.update_one(
        {"id": vehicle_id},
        {
            "$set": {
                "status": VehicleListingStatus.REJECTED.value,
                "rejection_reason": reason,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    await log_audit(
        "vehicle", vehicle_id, "rejected",
        admin["id"], "admin",
        old_value={"status": old_status},
        new_value={"status": VehicleListingStatus.REJECTED.value},
        reason=reason
    )
    
    return {"message": "Vehicle listing rejected"}


@vehicle_router.post("/vehicle-admin/vehicles/{vehicle_id}/cancel")
async def cancel_vehicle_auction(
    vehicle_id: str,
    reason: str,
    admin: dict = Depends(get_admin_user)
):
    """Cancel/freeze an active auction"""
    listing = await db.vehicle_listings.find_one({"id": vehicle_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    old_status = listing["status"]
    
    await db.vehicle_listings.update_one(
        {"id": vehicle_id},
        {
            "$set": {
                "status": VehicleListingStatus.CANCELLED.value,
                "rejection_reason": reason,
                "updated_at": datetime.now(timezone.utc)
            }
        }
    )
    
    # Cancel all active bids
    await db.vehicle_bids.update_many(
        {"vehicle_id": vehicle_id, "status": {"$in": [BidStatus.ACTIVE.value, BidStatus.WINNING.value]}},
        {"$set": {"status": BidStatus.CANCELLED.value}}
    )
    
    await log_audit(
        "vehicle", vehicle_id, "cancelled",
        admin["id"], "admin",
        old_value={"status": old_status},
        new_value={"status": VehicleListingStatus.CANCELLED.value},
        reason=reason
    )
    
    return {"message": "Auction cancelled"}


@vehicle_router.post("/vehicle-admin/bids/{bid_id}/remove")
async def remove_bid(
    bid_id: str,
    reason: str,
    admin: dict = Depends(get_admin_user)
):
    """Remove a bid (admin action with audit)"""
    bid = await db.vehicle_bids.find_one({"id": bid_id})
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    
    old_status = bid["status"]
    
    await db.vehicle_bids.update_one(
        {"id": bid_id},
        {
            "$set": {
                "status": BidStatus.RETRACTED.value,
                "retracted_at": datetime.now(timezone.utc),
                "retraction_reason": reason
            }
        }
    )
    
    # Recalculate current bid for the vehicle
    vehicle_id = bid["vehicle_id"]
    highest_bid = await db.vehicle_bids.find_one(
        {"vehicle_id": vehicle_id, "status": {"$in": [BidStatus.ACTIVE.value, BidStatus.WINNING.value]}},
        sort=[("amount", -1)]
    )
    
    if highest_bid:
        await db.vehicle_listings.update_one(
            {"id": vehicle_id},
            {
                "$set": {
                    "current_bid": highest_bid["amount"],
                    "highest_bidder_id": highest_bid["bidder_id"]
                }
            }
        )
        await db.vehicle_bids.update_one(
            {"id": highest_bid["id"]},
            {"$set": {"status": BidStatus.WINNING.value}}
        )
    else:
        await db.vehicle_listings.update_one(
            {"id": vehicle_id},
            {
                "$set": {
                    "current_bid": 0.0,
                    "highest_bidder_id": None
                }
            }
        )
    
    await log_audit(
        "bid", bid_id, "removed",
        admin["id"], "admin",
        old_value={"status": old_status, "amount": bid["amount"]},
        new_value={"status": BidStatus.RETRACTED.value},
        reason=reason
    )
    
    return {"message": "Bid removed"}


@vehicle_router.get("/vehicle-admin/audit-logs")
async def get_audit_logs(
    entity_type: str = None,
    entity_id: str = None,
    limit: int = 100,
    admin: dict = Depends(get_admin_user)
):
    """Get audit logs"""
    query = {}
    if entity_type:
        query["entity_type"] = entity_type
    if entity_id:
        query["entity_id"] = entity_id
    
    cursor = db.vehicle_audit_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    logs = await cursor.to_list(length=limit)
    
    return {"logs": logs}


# ============= WEBSOCKET FOR LIVE BIDDING =============

class VehicleConnectionManager:
    """Manage WebSocket connections for live vehicle auctions"""
    
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, vehicle_id: str):
        await websocket.accept()
        if vehicle_id not in self.active_connections:
            self.active_connections[vehicle_id] = []
        self.active_connections[vehicle_id].append(websocket)
    
    def disconnect(self, websocket: WebSocket, vehicle_id: str):
        if vehicle_id in self.active_connections:
            if websocket in self.active_connections[vehicle_id]:
                self.active_connections[vehicle_id].remove(websocket)
    
    async def broadcast_to_vehicle(self, vehicle_id: str, message: dict):
        if vehicle_id in self.active_connections:
            for connection in self.active_connections[vehicle_id]:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass


vehicle_manager = VehicleConnectionManager()


@vehicle_router.websocket("/ws/vehicle/{vehicle_id}")
async def vehicle_auction_websocket(websocket: WebSocket, vehicle_id: str):
    """WebSocket endpoint for live vehicle auction updates"""
    await vehicle_manager.connect(websocket, vehicle_id)
    
    try:
        # Send initial state
        listing = await db.vehicle_listings.find_one({"id": vehicle_id}, {"_id": 0})
        if listing:
            await websocket.send_json({
                "type": "initial_state",
                "current_bid": listing["current_bid"],
                "bid_count": listing["bid_count"],
                "end_time": listing["end_time"].isoformat() if isinstance(listing["end_time"], datetime) else listing["end_time"],
                "reserve_met": listing.get("reserve_met", False)
            })
        
        while True:
            # Keep connection alive and handle incoming messages
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            
    except WebSocketDisconnect:
        vehicle_manager.disconnect(websocket, vehicle_id)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        vehicle_manager.disconnect(websocket, vehicle_id)


# Function to broadcast bid updates (call this after placing bid)
async def broadcast_bid_update(vehicle_id: str, bid_amount: float, bid_count: int, 
                               end_time: datetime, reserve_met: bool):
    """Broadcast bid update to all connected clients"""
    await vehicle_manager.broadcast_to_vehicle(vehicle_id, {
        "type": "bid_update",
        "current_bid": bid_amount,
        "bid_count": bid_count,
        "end_time": end_time.isoformat() if isinstance(end_time, datetime) else end_time,
        "reserve_met": reserve_met,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


# ============= PRICING & FINANCIAL ENDPOINTS =============

@vehicle_router.get("/vehicles/{vehicle_id}/pricing-estimate")
async def get_vehicle_pricing_estimate(
    vehicle_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get pricing estimate for a vehicle auction
    Shows fees, taxes, and total for both buyer and seller
    """
    listing = await db.vehicle_listings.find_one({"id": vehicle_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Get user subscription tier if logged in
    buyer_tier = "basic"
    seller_tier = "basic"
    
    if credentials:
        try:
            user = await get_current_user(credentials)
            buyer_tier = user.get("subscription_tier", "basic")
        except Exception:
            pass
    
    # Get seller subscription tier
    seller = await db.vehicle_sellers.find_one({"id": listing["seller_id"]})
    if seller:
        seller_user = await db.users.find_one({"id": listing["seller_user_id"]})
        if seller_user:
            seller_tier = seller_user.get("subscription_tier", "basic")
    
    # Use current bid or starting price
    estimate_price = listing.get("current_bid") or listing.get("starting_price", 0)
    
    return get_pricing_estimate(
        estimate_price,
        listing.get("location_province", "ON"),
        buyer_tier,
        seller_tier
    )


@vehicle_router.post("/vehicles/{vehicle_id}/pricing-breakdown")
async def calculate_pricing_breakdown(
    vehicle_id: str,
    bid_amount: float,
    user: dict = Depends(get_current_user)
):
    """
    Calculate detailed pricing breakdown for a specific bid amount
    Used before placing a bid to show exact costs
    """
    listing = await db.vehicle_listings.find_one({"id": vehicle_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    # Get buyer's province from profile or use listing location
    buyer_province = user.get("province") or listing.get("location_province", "ON")
    
    # Get buyer subscription tier
    buyer_tier = get_subscription_tier(user)
    
    # Calculate full breakdown
    breakdown = calculate_buyer_pricing(bid_amount, buyer_province, buyer_tier)
    
    return {
        "bid_amount": bid_amount,
        "vehicle_id": vehicle_id,
        "breakdown": {
            "hammer_price": float(breakdown.hammer_price),
            "buyer_premium": {
                "rate": f"{float(breakdown.buyer_premium_rate) * 100:.1f}%",
                "amount": float(breakdown.buyer_premium)
            },
            "platform_fee": {
                "rate": "2.5%",
                "amount": float(breakdown.platform_fee)
            },
            "subtotal_before_tax": float(breakdown.subtotal_before_tax),
            "taxes": {
                "type": breakdown.tax_breakdown.tax_type,
                "province": breakdown.tax_breakdown.province,
                "gst": float(breakdown.tax_breakdown.gst_amount),
                "pst": float(breakdown.tax_breakdown.pst_amount),
                "qst": float(breakdown.tax_breakdown.qst_amount),
                "hst": float(breakdown.tax_breakdown.hst_amount),
                "total": float(breakdown.tax_breakdown.total_tax),
                "rate": f"{float(breakdown.tax_breakdown.total_rate) * 100:.2f}%"
            },
            "total_payable": float(breakdown.total_payable),
            "subscription_tier": breakdown.subscription_tier,
            "subscription_discount": float(breakdown.discount_applied)
        }
    }


# ============= INVOICE ENDPOINTS =============

@vehicle_router.get("/vehicle-invoices/my")
async def get_my_invoices(
    invoice_type: str = None,
    status: str = None,
    user: dict = Depends(get_current_user)
):
    """Get all invoices for current user (as buyer or seller)"""
    invoices = await get_invoices_for_user(db, user["id"], invoice_type, status)
    return {"invoices": invoices}


@vehicle_router.get("/vehicle-invoices/{invoice_id}")
async def get_invoice(
    invoice_id: str,
    user: dict = Depends(get_current_user)
):
    """Get detailed invoice by ID"""
    invoice = await get_invoice_summary(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Verify user has access
    if invoice.get("buyer_id") != user["id"] and invoice.get("seller_id") != user["id"]:
        # Check if admin
        if user.get("role") not in ["admin", "super_admin"]:
            raise HTTPException(status_code=403, detail="Access denied")
    
    return invoice


@vehicle_router.post("/vehicle-invoices/{invoice_id}/pay")
async def pay_invoice(
    invoice_id: str,
    payment_method: str,
    user: dict = Depends(get_current_user)
):
    """
    Process payment for an invoice
    In production, this would integrate with Stripe/payment processor
    """
    invoice = await get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Verify buyer owns the invoice
    if invoice.get("buyer_id") != user["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to pay this invoice")
    
    if invoice.get("payment_status") == InvoiceStatus.PAID:
        raise HTTPException(status_code=400, detail="Invoice already paid")
    
    # Calculate amount due
    amount_due = invoice["total_amount"] + invoice.get("penalty_amount", 0) - invoice.get("paid_amount", 0)
    
    # In production: Create Stripe payment intent, process payment, etc.
    # For now, simulate successful payment
    result = await process_invoice_payment(
        db,
        invoice_id,
        amount_due,
        payment_method,
        f"demo_txn_{uuid.uuid4()}"
    )
    
    return result


@vehicle_router.get("/vehicle-invoices/vehicle/{vehicle_id}")
async def get_vehicle_invoices(
    vehicle_id: str,
    user: dict = Depends(get_current_user)
):
    """Get all invoices related to a vehicle auction"""
    invoices = await db.vehicle_invoices.find(
        {"vehicle_id": vehicle_id},
        {"_id": 0}
    ).to_list(length=10)
    
    # Filter based on user access
    accessible = []
    for inv in invoices:
        if inv.get("buyer_id") == user["id"] or inv.get("seller_id") == user["id"]:
            accessible.append(inv)
        elif user.get("role") in ["admin", "super_admin"]:
            accessible.append(inv)
    
    return {"invoices": accessible}


# ============= SELLER FINANCIAL ENDPOINTS =============

@vehicle_router.get("/vehicle-sellers/me/financials")
async def get_seller_financials(
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user)
):
    """Get seller's financial overview including commission rates and payouts"""
    # Get subscription tier
    tier = get_subscription_tier(user)
    
    # Get pending settlements
    pending_settlements = await db.vehicle_invoices.find({
        "seller_id": user["id"],
        "invoice_type": "seller_settlement",
        "settlement_status": {"$in": ["pending_buyer_payment", "ready"]}
    }, {"_id": 0}).to_list(length=100)
    
    # Get completed settlements
    completed_settlements = await db.vehicle_invoices.find({
        "seller_id": user["id"],
        "invoice_type": "seller_settlement",
        "settlement_status": "completed"
    }, {"_id": 0}).sort("settled_at", -1).limit(20).to_list(length=20)
    
    # Calculate totals
    pending_payout = sum(s.get("net_payout", 0) for s in pending_settlements)
    total_earned = sum(s.get("net_payout", 0) for s in completed_settlements)
    total_commission_paid = sum(s.get("seller_commission", 0) for s in completed_settlements)
    
    # Get commission rate info
    from services.vehicle_pricing import SELLER_COMMISSION_RATES
    commission_rate = float(SELLER_COMMISSION_RATES[tier]) * 100
    basic_rate = float(SELLER_COMMISSION_RATES[SubscriptionTier.BASIC]) * 100
    
    return {
        "subscription_tier": tier.value,
        "commission_rate": f"{commission_rate:.1f}%",
        "commission_savings": f"{basic_rate - commission_rate:.1f}%" if tier != SubscriptionTier.BASIC else "0%",
        "financials": {
            "pending_payout": pending_payout,
            "total_earned": total_earned,
            "total_commission_paid": total_commission_paid,
            "pending_settlements_count": len(pending_settlements)
        },
        "pending_settlements": pending_settlements,
        "recent_settlements": completed_settlements[:5]
    }


# ============= ADMIN FINANCIAL ENDPOINTS =============

@vehicle_router.get("/vehicle-admin/invoices")
async def admin_list_invoices(
    status: str = None,
    invoice_type: str = None,
    limit: int = 50,
    admin: dict = Depends(get_admin_user)
):
    """Admin: List all invoices with filters"""
    query = {}
    if status:
        query["payment_status"] = status
    if invoice_type:
        query["invoice_type"] = invoice_type
    
    cursor = db.vehicle_invoices.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    invoices = await cursor.to_list(length=limit)
    
    # Get summary stats
    total_pending = await db.vehicle_invoices.count_documents({"payment_status": "pending"})
    total_overdue = await db.vehicle_invoices.count_documents({"payment_status": "overdue"})
    total_paid = await db.vehicle_invoices.count_documents({"payment_status": "paid"})
    
    return {
        "invoices": invoices,
        "stats": {
            "pending": total_pending,
            "overdue": total_overdue,
            "paid": total_paid
        }
    }


@vehicle_router.post("/vehicle-admin/run-scheduler")
async def admin_run_scheduler(admin: dict = Depends(get_admin_user)):
    """
    Admin: Manually trigger the auction scheduler
    Processes ended auctions, activates scheduled ones, applies penalties
    """
    result = await run_auction_scheduler(db)
    
    await log_audit(
        "system", "scheduler", "manual_run",
        admin["id"], "admin",
        new_value=result
    )
    
    return {
        "message": "Scheduler executed successfully",
        "results": result
    }


@vehicle_router.post("/vehicle-admin/process-auction/{vehicle_id}")
async def admin_process_auction(
    vehicle_id: str,
    admin: dict = Depends(get_admin_user)
):
    """Admin: Manually process a single ended auction"""
    listing = await db.vehicle_listings.find_one({"id": vehicle_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    if listing["status"] != "active":
        raise HTTPException(status_code=400, detail=f"Vehicle status is '{listing['status']}', not active")
    
    result = await process_ended_auction(db, listing)
    
    return {
        "vehicle_id": result.vehicle_id,
        "status": result.status,
        "winner_id": result.winner_id,
        "final_price": result.final_price,
        "buyer_invoice_id": result.buyer_invoice_id,
        "seller_invoice_id": result.seller_invoice_id,
        "error": result.error
    }


@vehicle_router.get("/vehicle-admin/financial-summary")
async def admin_financial_summary(admin: dict = Depends(get_admin_user)):
    """Admin: Get overall financial summary"""
    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # This month's buyer invoices
    monthly_buyer_invoices = await db.vehicle_invoices.find({
        "invoice_type": "buyer",
        "created_at": {"$gte": start_of_month}
    }).to_list(length=1000)
    
    monthly_revenue = sum(inv.get("platform_fee", 0) + inv.get("buyer_premium", 0) for inv in monthly_buyer_invoices)
    monthly_tax_collected = sum(inv.get("tax_total", 0) for inv in monthly_buyer_invoices)
    monthly_volume = sum(inv.get("hammer_price", 0) for inv in monthly_buyer_invoices)
    
    # All time stats
    all_buyer_invoices = await db.vehicle_invoices.find({
        "invoice_type": "buyer"
    }).to_list(length=10000)
    
    total_revenue = sum(inv.get("platform_fee", 0) + inv.get("buyer_premium", 0) for inv in all_buyer_invoices)
    total_volume = sum(inv.get("hammer_price", 0) for inv in all_buyer_invoices)
    
    # Outstanding amounts
    pending_invoices = await db.vehicle_invoices.find({
        "invoice_type": "buyer",
        "payment_status": {"$in": ["pending", "overdue"]}
    }).to_list(length=1000)
    
    outstanding_amount = sum(inv.get("total_amount", 0) + inv.get("penalty_amount", 0) - inv.get("paid_amount", 0) 
                            for inv in pending_invoices)
    
    return {
        "this_month": {
            "revenue": monthly_revenue,
            "tax_collected": monthly_tax_collected,
            "volume": monthly_volume,
            "transactions": len(monthly_buyer_invoices)
        },
        "all_time": {
            "revenue": total_revenue,
            "volume": total_volume,
            "transactions": len(all_buyer_invoices)
        },
        "outstanding": {
            "amount": outstanding_amount,
            "invoices_count": len(pending_invoices)
        }
    }


# ============= STRIPE PAYMENT ENDPOINTS =============

@vehicle_router.post("/vehicle-payments/invoice/{invoice_id}/checkout")
async def create_invoice_checkout(
    invoice_id: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    Create Stripe checkout session for invoice payment
    Amount is determined server-side from invoice (not user-controllable)
    """
    payment_service = get_payment_service()
    
    # Get base URL from request
    base_url = str(request.base_url)
    
    # Get origin URL from header (frontend sends this)
    origin_url = request.headers.get("Origin") or request.headers.get("Referer", "").rstrip("/")
    if not origin_url:
        origin_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    
    try:
        result = await payment_service.create_invoice_checkout(
            db,
            invoice_id,
            user["id"],
            base_url,
            origin_url
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@vehicle_router.post("/vehicle-payments/deposit/{vehicle_id}/checkout")
async def create_deposit_checkout(
    vehicle_id: str,
    request: Request,
    user: dict = Depends(get_current_user)
):
    """
    Create Stripe checkout session for bid deposit
    Deposit amount is fixed per vehicle (server-side)
    """
    payment_service = get_payment_service()
    
    base_url = str(request.base_url)
    origin_url = request.headers.get("Origin") or request.headers.get("Referer", "").rstrip("/")
    if not origin_url:
        origin_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
    
    # Get deposit amount from listing (server-side)
    listing = await db.vehicle_listings.find_one({"id": vehicle_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    deposit_amount = listing.get("deposit_amount", 500)
    
    try:
        result = await payment_service.create_deposit_checkout(
            db,
            vehicle_id,
            user["id"],
            deposit_amount,
            base_url,
            origin_url
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@vehicle_router.get("/vehicle-payments/status/{session_id}")
async def check_payment_status(
    session_id: str,
    request: Request
):
    """
    Check Stripe checkout session status
    Called by frontend after returning from Stripe
    """
    payment_service = get_payment_service()
    base_url = str(request.base_url)
    
    try:
        result = await payment_service.check_payment_status(db, session_id, base_url)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@vehicle_router.post("/webhook/stripe")
async def stripe_webhook(request: Request):
    """
    Stripe webhook endpoint
    Handles payment confirmations, refunds, etc.
    """
    try:
        body = await request.body()
        signature = request.headers.get("Stripe-Signature")
        
        payment_service = get_payment_service()
        webhook_url = f"{request.base_url}api/webhook/stripe"
        checkout = payment_service._get_checkout(webhook_url)
        
        # Handle webhook
        event = await checkout.handle_webhook(body, signature)
        
        logger.info(f"Stripe webhook received: {event.event_type} - {event.session_id}")
        
        # Process based on event type
        if event.event_type == "checkout.session.completed":
            # Update payment status
            await payment_service.check_payment_status(db, event.session_id, str(request.base_url))
        
        return {"received": True, "event_type": event.event_type}
    except Exception as e:
        logger.exception(f"Stripe webhook error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


# ============= DOCUMENT UPLOAD ENDPOINTS =============

@vehicle_router.post("/vehicle-documents/upload")
async def upload_verification_document(
    document_type: str = Form(...),
    description: str = Form(None),
    file: UploadFile = File(...),
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user)
):
    """
    Upload a seller verification document
    Supports PDF, JPG, PNG, WEBP (max 10MB)
    """
    # Validate document type
    try:
        DocumentType(document_type)  # Validate the type
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid document type. Valid types: {[d.value for d in DocumentType]}"
        )
    
    # Read file content
    content = await file.read()
    
    try:
        document = await create_seller_document(
            db,
            seller["id"],
            user["id"],
            document_type,
            content,
            file.filename,
            description
        )
        return {
            "message": "Document uploaded successfully",
            "document": document
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@vehicle_router.get("/vehicle-documents/my")
async def get_my_documents(
    document_type: str = None,
    status: str = None,
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user)
):
    """Get all documents for current seller"""
    documents = await get_seller_documents(db, seller["id"], document_type, status)
    
    # Get verification status
    verification = await check_seller_verification_status(db, seller["id"])
    
    return {
        "documents": documents,
        "verification_status": verification
    }


@vehicle_router.get("/vehicle-documents/required")
async def get_required_documents(
    seller: dict = Depends(get_vehicle_seller)
):
    """Get list of required documents based on seller type"""
    seller_type = seller.get("seller_type", "private")
    required = get_document_types_for_seller_type(seller_type)
    
    # Get already uploaded documents
    existing = await get_seller_documents(db, seller["id"])
    existing_types = {doc["document_type"] for doc in existing}
    
    # Mark which are already uploaded
    for doc in required:
        doc["uploaded"] = doc["type"] in existing_types
    
    return {
        "seller_type": seller_type,
        "required_documents": required
    }


@vehicle_router.get("/vehicle-documents/{document_id}")
async def get_document(
    document_id: str,
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user)
):
    """Get document details by ID"""
    document = await get_document_by_id(db, document_id)
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Verify ownership
    if document["seller_id"] != seller["id"]:
        raise HTTPException(status_code=403, detail="Access denied")
    
    return document


# ============= ADMIN DOCUMENT ENDPOINTS =============

@vehicle_router.get("/vehicle-admin/documents/pending")
async def admin_get_pending_documents(
    limit: int = 50,
    admin: dict = Depends(get_admin_user)
):
    """Admin: Get all pending documents for review"""
    documents = await get_pending_documents_for_admin(db, limit)
    return {
        "pending_count": len(documents),
        "documents": documents
    }


@vehicle_router.post("/vehicle-admin/documents/{document_id}/approve")
async def admin_approve_document(
    document_id: str,
    notes: str = None,
    admin: dict = Depends(get_admin_user)
):
    """Admin: Approve a seller document"""
    try:
        document = await approve_document(db, document_id, admin["id"], notes)
        return {
            "message": "Document approved",
            "document": document
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@vehicle_router.post("/vehicle-admin/documents/{document_id}/reject")
async def admin_reject_document(
    document_id: str,
    reason: str,
    admin: dict = Depends(get_admin_user)
):
    """Admin: Reject a seller document"""
    if not reason:
        raise HTTPException(status_code=400, detail="Rejection reason is required")
    
    try:
        document = await reject_document(db, document_id, admin["id"], reason)
        return {
            "message": "Document rejected",
            "document": document
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@vehicle_router.get("/vehicle-admin/documents/seller/{seller_id}")
async def admin_get_seller_documents(
    seller_id: str,
    admin: dict = Depends(get_admin_user)
):
    """Admin: Get all documents for a specific seller"""
    documents = await get_seller_documents(db, seller_id, include_archived=True)
    verification = await check_seller_verification_status(db, seller_id)
    
    return {
        "seller_id": seller_id,
        "documents": documents,
        "verification_status": verification
    }


# ============= SCHEDULER ADMIN ENDPOINTS =============

@vehicle_router.get("/vehicle-admin/scheduler/status")
async def admin_get_scheduler_status(admin: dict = Depends(get_admin_user)):
    """Admin: Get scheduler status and job list"""
    status = get_scheduler_status()
    return status


@vehicle_router.post("/vehicle-admin/scheduler/run/{job_id}")
async def admin_run_scheduler_job(
    job_id: str,
    admin: dict = Depends(get_admin_user)
):
    """Admin: Manually trigger a specific scheduler job"""
    result = await run_job_manually(job_id)
    
    await log_audit(
        "scheduler", job_id, "manual_execution",
        admin["id"], "admin",
        new_value=result
    )
    
    return result


# ============= CRA TAX REPORTING ENDPOINTS =============

@vehicle_router.get("/vehicle-admin/tax-reports")
async def admin_get_tax_reports(
    report_type: str = None,
    year: int = None,
    limit: int = 20,
    admin: dict = Depends(get_admin_user)
):
    """
    Admin: Get list of generated tax reports
    
    Optional filters:
    - report_type: gst_hst_summary, provincial_tax, annual_summary, seller_payments
    - year: Tax year
    """
    reports = await get_tax_reports(db, report_type, year, limit)
    return {
        "count": len(reports),
        "reports": reports
    }


@vehicle_router.get("/vehicle-admin/tax-reports/{report_id}")
async def admin_get_tax_report(
    report_id: str,
    admin: dict = Depends(get_admin_user)
):
    """Admin: Get specific tax report with full details"""
    report = await get_tax_report_by_id(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Tax report not found")
    return report


@vehicle_router.get("/vehicle-admin/tax-reports/{report_id}/download")
async def admin_download_tax_report(
    report_id: str,
    admin: dict = Depends(get_admin_user)
):
    """Admin: Download tax report XML file"""
    xml_content = await download_tax_report_xml(db, report_id)
    if not xml_content:
        raise HTTPException(status_code=404, detail="Tax report not found")
    
    from fastapi.responses import Response
    
    # Get report to build filename
    report = await get_tax_report_by_id(db, report_id)
    report_type = report.get("report_type", "tax")
    year = report.get("year", datetime.now().year)
    filename = f"bidvex_{report_type}_{year}_{report_id[:8]}.xml"
    
    await log_audit(
        "tax_report", report_id, "downloaded",
        admin["id"], "admin"
    )
    
    return Response(
        content=xml_content,
        media_type="application/xml",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@vehicle_router.post("/vehicle-admin/tax-reports/generate/gst-hst")
async def admin_generate_gst_hst_report(
    start_date: str,
    end_date: str,
    reporting_period: str = "quarterly",
    admin: dict = Depends(get_admin_user)
):
    """
    Admin: Generate GST/HST Summary Report for CRA filing
    
    This generates a GST34-compatible report with:
    - Total taxable sales by province
    - GST collected (5% federal)
    - HST collected (ON 13%, Atlantic 15%)
    - Provincial breakdown for audit
    
    Parameters:
    - start_date: YYYY-MM-DD format
    - end_date: YYYY-MM-DD format  
    - reporting_period: monthly, quarterly, annual
    """
    try:
        start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    report = await generate_gst_hst_report(db, start, end, reporting_period)
    
    await log_audit(
        "tax_report", report["report_id"], "generated",
        admin["id"], "admin",
        new_value={"type": "gst_hst_summary", "period": f"{start_date} to {end_date}"}
    )
    
    return report


@vehicle_router.post("/vehicle-admin/tax-reports/generate/qst")
async def admin_generate_qst_report(
    start_date: str,
    end_date: str,
    admin: dict = Depends(get_admin_user)
):
    """
    Admin: Generate Quebec QST Report
    
    For Revenu Québec filing with:
    - GST collected on QC transactions
    - QST collected (9.975%)
    - Transaction breakdown
    """
    try:
        start = datetime.fromisoformat(start_date).replace(tzinfo=timezone.utc)
        end = datetime.fromisoformat(end_date).replace(hour=23, minute=59, second=59, tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    
    report = await generate_qst_report(db, start, end)
    
    await log_audit(
        "tax_report", report["report_id"], "generated",
        admin["id"], "admin",
        new_value={"type": "qst", "period": f"{start_date} to {end_date}"}
    )
    
    return report


@vehicle_router.post("/vehicle-admin/tax-reports/generate/seller-payments")
async def admin_generate_seller_payments_report(
    year: int,
    admin: dict = Depends(get_admin_user)
):
    """
    Admin: Generate Annual Seller Payments Report (T5018-style)
    
    For CRA reporting of payments to sellers:
    - Only includes sellers with payments >= $500
    - Includes gross payments, commissions, net payouts
    - Used for T5018 filing requirements
    """
    if year < 2020 or year > datetime.now().year:
        raise HTTPException(status_code=400, detail="Invalid year")
    
    report = await generate_seller_payments_report(db, year)
    
    await log_audit(
        "tax_report", report["report_id"], "generated",
        admin["id"], "admin",
        new_value={"type": "seller_payments", "year": year}
    )
    
    return report


@vehicle_router.post("/vehicle-admin/tax-reports/generate/annual-summary")
async def admin_generate_annual_summary(
    year: int,
    admin: dict = Depends(get_admin_user)
):
    """
    Admin: Generate Comprehensive Annual Tax Summary
    
    Complete year-end report with:
    - All tax types (GST, HST, PST, QST)
    - Monthly breakdown
    - Total revenue and fees
    - Platform performance metrics
    """
    if year < 2020 or year > datetime.now().year:
        raise HTTPException(status_code=400, detail="Invalid year")
    
    report = await generate_annual_summary(db, year)
    
    await log_audit(
        "tax_report", report["report_id"], "generated",
        admin["id"], "admin",
        new_value={"type": "annual_summary", "year": year}
    )
    
    return report


# ============= PDF INVOICE DOWNLOAD ENDPOINTS =============

@vehicle_router.get("/vehicle-invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Download invoice as PDF
    
    Generates a professional PDF invoice with:
    - Full BidVex branding
    - Business Number (BN) and GST/HST registration numbers
    - Complete line items with tax breakdown
    - Payment status and deadline
    - Subscription savings if applicable
    """
    # Verify user has access to this invoice
    invoice = await get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Check access - buyer, seller, or admin
    is_buyer = invoice.get("buyer_id") == user["id"]
    is_seller = invoice.get("seller_id") == user["id"]
    is_admin = user.get("role") in ["admin", "super_admin"]
    
    if not (is_buyer or is_seller or is_admin):
        raise HTTPException(status_code=403, detail="Access denied to this invoice")
    
    # Generate PDF
    pdf_bytes = await generate_invoice_pdf(db, invoice_id)
    if not pdf_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate PDF")
    
    from fastapi.responses import Response
    
    filename = f"BidVex_Invoice_{invoice.get('invoice_number', invoice_id[:8])}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@vehicle_router.get("/vehicle-invoices/{invoice_id}/settlement-pdf")
async def download_settlement_pdf(
    invoice_id: str,
    user: dict = Depends(get_current_user)
):
    """
    Download seller settlement statement as PDF
    
    For sellers to have a record of their payout breakdown
    """
    # Verify this is a seller settlement and user has access
    invoice = await get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Settlement not found")
    
    if invoice.get("invoice_type") != "seller_settlement":
        raise HTTPException(status_code=400, detail="This is not a settlement document")
    
    # Check access - seller or admin
    is_seller = invoice.get("seller_id") == user["id"]
    is_admin = user.get("role") in ["admin", "super_admin"]
    
    if not (is_seller or is_admin):
        raise HTTPException(status_code=403, detail="Access denied to this settlement")
    
    # Generate PDF
    pdf_bytes = await generate_settlement_pdf(db, invoice_id)
    if not pdf_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate PDF")
    
    from fastapi.responses import Response
    
    filename = f"BidVex_Settlement_{invoice.get('invoice_number', invoice_id[:8])}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )