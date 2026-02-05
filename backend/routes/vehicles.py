"""
Vehicle Auction Module - API Routes
Standalone, enterprise-grade vehicle auction system
Completely separate from general marketplace

Routes:
- /api/vehicles/* - Vehicle listings
- /api/vehicle-sellers/* - Seller management
- /api/vehicle-bids/* - Bidding system
- /api/vehicle-admin/* - Admin operations
"""

from fastapi import APIRouter, HTTPException, Depends, Request, WebSocket, WebSocketDisconnect, Query, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
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
    import base64
    content = await file.read()
    
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
                except:
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
