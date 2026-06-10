"""
Vehicle Admin, Invoice, Documents, Tax Sub-Router
Extracted from vehicles.py for maintainability (~1,380 lines).
"""

from fastapi import APIRouter, HTTPException, Depends, Request, Query, UploadFile, File, Form
from fastapi.responses import FileResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.websockets import WebSocket, WebSocketDisconnect
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone, timedelta
import os
import uuid
import json
import logging

from models.vehicle_models import (
    SellerType, SellerVerificationStatus, VehicleListingStatus,
    VehicleAuctionType, VehicleAuctionVisibility, BidStatus,
    VehicleBodyType, TransmissionType, FuelType, DrivetrainType,
    TitleStatus, OwnershipStatus, LienStatus,
    VehicleSellerCreate, VehicleSeller, VehicleSellerDocument,
    VehicleListingCreate, VehicleListing, VehicleMedia, VehicleConditionReport,
    VehicleBidCreate, VehicleBid, VehicleBidDeposit,
    VehicleInvoice, VehicleInvoiceLineItem,
    LegalAcceptance, VehicleAuditLog,
    validate_vin
)
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

vehicle_admin_router = APIRouter(prefix="/api", tags=["Vehicle Admin"])

security = HTTPBearer(auto_error=False)

# DB reference — set from vehicles.py
_db = None

def _init_vehicle_admin(database):
    global _db
    _db = database


# iter211 — Module-level lazy `db` proxy. Resolves the F821 errors where
# endpoints used `db.xxx` without first calling `db = get_db()`. The proxy
# lazily delegates every attribute access to the runtime DB (either the
# initialized `_db` reference set by `_init_vehicle_admin`, or the live db
# returned by `deps.get_db()`).
from deps import get_db as _get_db_runtime

class _LazyDBProxy:
    def __getattr__(self, name):
        target = _db if _db is not None else _get_db_runtime()
        return getattr(target, name)

    def __getitem__(self, name):
        target = _db if _db is not None else _get_db_runtime()
        return target[name]

db = _LazyDBProxy()


# iter211 — Import the system-settings helper from the parent module so
# endpoints can call `await get_system_settings()` without a NameError.
async def get_system_settings():
    from routes.vehicles import get_system_settings as _gss
    return await _gss()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Reuse auth from parent — imported at runtime to avoid circular deps."""
    from routes.vehicles import get_current_user as _get_current_user
    return await _get_current_user(credentials)


async def get_admin_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Reuse admin auth from parent."""
    from routes.vehicles import get_admin_user as _get_admin_user
    return await _get_admin_user(credentials)


async def get_vehicle_seller(user: dict = Depends(get_current_user)):
    """Reuse vehicle seller auth from parent."""
    from routes.vehicles import get_vehicle_seller as _get_vehicle_seller
    return await _get_vehicle_seller(user)


async def log_audit(entity_type, entity_id, action, performed_by, role, old_value=None, new_value=None, reason=None):
    """Reuse audit logging from parent."""
    from routes.vehicles import log_audit as _log_audit
    return await _log_audit(entity_type, entity_id, action, performed_by, role, old_value, new_value, reason)


# ============= ADMIN ENDPOINTS =============

@vehicle_admin_router.get("/vehicle-admin/pending-sellers")
async def get_pending_sellers(admin: dict = Depends(get_admin_user)):
    """Get sellers pending verification"""
    cursor = _db.vehicle_sellers.find(
        {"verification_status": {"$in": [
            SellerVerificationStatus.PENDING.value,
            SellerVerificationStatus.UNDER_REVIEW.value
        ]}},
        {"_id": 0}
    ).sort("created_at", 1)
    sellers = await cursor.to_list(length=100)
    
    # Enrich with user info
    for seller in sellers:
        user = await _db.users.find_one(
            {"id": seller["user_id"]},
            {"_id": 0, "email": 1, "full_name": 1}
        )
        seller["user"] = user
    
    return {"sellers": sellers}


@vehicle_admin_router.post("/vehicle-admin/sellers/{seller_id}/approve")
async def approve_seller(
    seller_id: str,
    admin: dict = Depends(get_admin_user)
):
    """Approve vehicle seller"""
    seller = await _db.vehicle_sellers.find_one({"id": seller_id})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    old_status = seller["verification_status"]
    
    await _db.vehicle_sellers.update_one(
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

    # iter211-fix — propagate approval to the user document so the dealer
    # dashboard banner (DealerAnnualFeeBanner) and the dealer-subscription
    # endpoints can see `is_vehicle_dealer=True`. Without this flag the
    # gold "Pay Annual Fee" CTA never renders and the dealer cannot pay.
    if seller.get("user_id"):
        await _db.users.update_one(
            {"id": seller["user_id"]},
            {"$set": {
                "is_vehicle_dealer": True,
                "vehicle_dealer_approved_at": datetime.now(timezone.utc).isoformat(),
                "vehicle_dealer_approved_by": admin["id"],
            }},
        )

    await log_audit(
        "seller", seller_id, "approved", 
        admin["id"], "admin",
        old_value={"status": old_status},
        new_value={"status": SellerVerificationStatus.APPROVED.value}
    )
    
    return {"message": "Seller approved successfully"}


@vehicle_admin_router.post("/vehicle-admin/sellers/{seller_id}/reject")
async def reject_seller(
    seller_id: str,
    reason: str,
    admin: dict = Depends(get_admin_user)
):
    """Reject vehicle seller application"""
    seller = await _db.vehicle_sellers.find_one({"id": seller_id})
    if not seller:
        raise HTTPException(status_code=404, detail="Seller not found")
    
    old_status = seller["verification_status"]
    
    await _db.vehicle_sellers.update_one(
        {"id": seller_id},
        {
            "$set": {
                "verification_status": SellerVerificationStatus.REJECTED.value,
                "rejection_reason": reason,
                # iter209 — capture who/when for resubmission history audit
                "rejected_at": datetime.now(timezone.utc),
                "rejected_by": admin["id"],
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


@vehicle_admin_router.get("/vehicle-admin/pending-vehicles")
async def get_pending_vehicles(admin: dict = Depends(get_admin_user)):
    """Get vehicles pending approval"""
    cursor = _db.vehicle_listings.find(
        {"status": VehicleListingStatus.PENDING_APPROVAL.value},
        {"_id": 0}
    ).sort("created_at", 1)
    vehicles = await cursor.to_list(length=100)
    
    # Enrich with seller info
    for vehicle in vehicles:
        seller = await _db.vehicle_sellers.find_one(
            {"id": vehicle["seller_id"]},
            {"_id": 0, "seller_type": 1, "business_name": 1}
        )
        vehicle["seller"] = seller
    
    return {"vehicles": vehicles}


@vehicle_admin_router.post("/vehicle-admin/vehicles/{vehicle_id}/approve")
async def approve_vehicle(
    vehicle_id: str,
    admin: dict = Depends(get_admin_user)
):
    """
    Approve vehicle listing
    
    NOTE: Admin can still approve vehicles even when auctions are paused.
    This allows pre-approval before system goes live.
    However, the vehicle won't become ACTIVE until auctions are enabled.
    """
    # Check if auctions are enabled - warn but don't block admin
    settings = await get_system_settings()
    
    listing = await _db.vehicle_listings.find_one({"id": vehicle_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    if listing["status"] != VehicleListingStatus.PENDING_APPROVAL.value:
        raise HTTPException(status_code=400, detail="Vehicle not pending approval")
    
    old_status = listing["status"]
    
    # Set to active if start time has passed AND auctions are enabled, otherwise approved
    now = datetime.now(timezone.utc)
    start_time = listing["start_time"]
    if isinstance(start_time, str):
        start_time = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
    
    # Only set to ACTIVE if auctions are enabled AND time has passed
    auctions_enabled = settings.get("vehicle_auctions_enabled", False)
    if auctions_enabled and now >= start_time:
        new_status = VehicleListingStatus.ACTIVE.value
    else:
        new_status = VehicleListingStatus.APPROVED.value
    
    await _db.vehicle_listings.update_one(
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
    
    response = {"message": "Vehicle approved", "new_status": new_status}
    
    # Add warning if auctions are paused
    if not auctions_enabled:
        response["warning"] = "Vehicle auctions are currently paused. Listing will not go live until system is enabled by admin."
    
    return response


@vehicle_admin_router.post("/vehicle-admin/vehicles/{vehicle_id}/reject")
async def reject_vehicle(
    vehicle_id: str,
    reason: str,
    admin: dict = Depends(get_admin_user)
):
    """Reject vehicle listing"""
    listing = await _db.vehicle_listings.find_one({"id": vehicle_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    old_status = listing["status"]
    
    await _db.vehicle_listings.update_one(
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


@vehicle_admin_router.post("/vehicle-admin/vehicles/{vehicle_id}/cancel")
async def cancel_vehicle_auction(
    vehicle_id: str,
    reason: str,
    admin: dict = Depends(get_admin_user)
):
    """Cancel/freeze an active auction"""
    listing = await _db.vehicle_listings.find_one({"id": vehicle_id})
    if not listing:
        raise HTTPException(status_code=404, detail="Vehicle not found")
    
    old_status = listing["status"]
    
    await _db.vehicle_listings.update_one(
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
    await _db.vehicle_bids.update_many(
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


@vehicle_admin_router.post("/vehicle-admin/bids/{bid_id}/remove")
async def remove_bid(
    bid_id: str,
    reason: str,
    admin: dict = Depends(get_admin_user)
):
    """Remove a bid (admin action with audit)"""
    bid = await _db.vehicle_bids.find_one({"id": bid_id})
    if not bid:
        raise HTTPException(status_code=404, detail="Bid not found")
    
    old_status = bid["status"]
    
    await _db.vehicle_bids.update_one(
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
    highest_bid = await _db.vehicle_bids.find_one(
        {"vehicle_id": vehicle_id, "status": {"$in": [BidStatus.ACTIVE.value, BidStatus.WINNING.value]}},
        sort=[("amount", -1)]
    )
    
    if highest_bid:
        await _db.vehicle_listings.update_one(
            {"id": vehicle_id},
            {
                "$set": {
                    "current_bid": highest_bid["amount"],
                    "highest_bidder_id": highest_bid["bidder_id"]
                }
            }
        )
        await _db.vehicle_bids.update_one(
            {"id": highest_bid["id"]},
            {"$set": {"status": BidStatus.WINNING.value}}
        )
    else:
        await _db.vehicle_listings.update_one(
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


@vehicle_admin_router.get("/vehicle-admin/audit-logs")
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
    
    cursor = _db.vehicle_audit_logs.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
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


@vehicle_admin_router.websocket("/ws/vehicle/{vehicle_id}")
async def vehicle_auction_websocket(websocket: WebSocket, vehicle_id: str):
    """WebSocket endpoint for live vehicle auction updates"""
    await vehicle_manager.connect(websocket, vehicle_id)
    
    try:
        # Send initial state
        listing = await _db.vehicle_listings.find_one({"id": vehicle_id}, {"_id": 0})
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

@vehicle_admin_router.get("/vehicles/{vehicle_id}/pricing-estimate")
async def get_vehicle_pricing_estimate(
    vehicle_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get pricing estimate for a vehicle auction
    Shows fees, taxes, and total for both buyer and seller
    """
    listing = await _db.vehicle_listings.find_one({"id": vehicle_id}, {"_id": 0})
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
    seller = await _db.vehicle_sellers.find_one({"id": listing["seller_id"]})
    if seller:
        seller_user = await _db.users.find_one({"id": listing["seller_user_id"]})
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


@vehicle_admin_router.post("/vehicles/{vehicle_id}/pricing-breakdown")
async def calculate_pricing_breakdown(
    vehicle_id: str,
    bid_amount: float,
    user: dict = Depends(get_current_user)
):
    """
    Calculate detailed pricing breakdown for a specific bid amount
    Used before placing a bid to show exact costs
    """
    listing = await _db.vehicle_listings.find_one({"id": vehicle_id}, {"_id": 0})
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

@vehicle_admin_router.get("/vehicle-invoices/my")
async def get_my_invoices(
    invoice_type: str = None,
    status: str = None,
    user: dict = Depends(get_current_user)
):
    """Get all invoices for current user (as buyer or seller)"""
    invoices = await get_invoices_for_user(db, user["id"], invoice_type, status)
    return {"invoices": invoices}


@vehicle_admin_router.get("/vehicle-invoices/{invoice_id}")
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


@vehicle_admin_router.post("/vehicle-invoices/{invoice_id}/pay")
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


@vehicle_admin_router.get("/vehicle-invoices/vehicle/{vehicle_id}")
async def get_vehicle_invoices(
    vehicle_id: str,
    user: dict = Depends(get_current_user)
):
    """Get all invoices related to a vehicle auction"""
    invoices = await _db.vehicle_invoices.find(
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

@vehicle_admin_router.get("/vehicle-sellers/me/financials")
async def get_seller_financials(
    seller: dict = Depends(get_vehicle_seller),
    user: dict = Depends(get_current_user)
):
    """Get seller's financial overview including commission rates and payouts"""
    # Get subscription tier
    tier = get_subscription_tier(user)
    
    # Get pending settlements
    pending_settlements = await _db.vehicle_invoices.find({
        "seller_id": user["id"],
        "invoice_type": "seller_settlement",
        "settlement_status": {"$in": ["pending_buyer_payment", "ready"]}
    }, {"_id": 0}).to_list(length=100)
    
    # Get completed settlements
    completed_settlements = await _db.vehicle_invoices.find({
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

@vehicle_admin_router.get("/vehicle-admin/invoices")
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
    
    cursor = _db.vehicle_invoices.find(query, {"_id": 0}).sort("created_at", -1).limit(limit)
    invoices = await cursor.to_list(length=limit)
    
    # Get summary stats
    total_pending = await _db.vehicle_invoices.count_documents({"payment_status": "pending"})
    total_overdue = await _db.vehicle_invoices.count_documents({"payment_status": "overdue"})
    total_paid = await _db.vehicle_invoices.count_documents({"payment_status": "paid"})
    
    return {
        "invoices": invoices,
        "stats": {
            "pending": total_pending,
            "overdue": total_overdue,
            "paid": total_paid
        }
    }


@vehicle_admin_router.post("/vehicle-admin/run-scheduler")
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


@vehicle_admin_router.post("/vehicle-admin/process-auction/{vehicle_id}")
async def admin_process_auction(
    vehicle_id: str,
    admin: dict = Depends(get_admin_user)
):
    """Admin: Manually process a single ended auction"""
    listing = await _db.vehicle_listings.find_one({"id": vehicle_id})
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


@vehicle_admin_router.get("/vehicle-admin/financial-summary")
async def admin_financial_summary(admin: dict = Depends(get_admin_user)):
    """Admin: Get overall financial summary"""
    now = datetime.now(timezone.utc)
    start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    # This month's buyer invoices
    monthly_buyer_invoices = await _db.vehicle_invoices.find({
        "invoice_type": "buyer",
        "created_at": {"$gte": start_of_month}
    }).to_list(length=1000)
    
    monthly_revenue = sum(inv.get("platform_fee", 0) + inv.get("buyer_premium", 0) for inv in monthly_buyer_invoices)
    monthly_tax_collected = sum(inv.get("tax_total", 0) for inv in monthly_buyer_invoices)
    monthly_volume = sum(inv.get("hammer_price", 0) for inv in monthly_buyer_invoices)
    
    # All time stats
    all_buyer_invoices = await _db.vehicle_invoices.find({
        "invoice_type": "buyer"
    }).to_list(length=10000)
    
    total_revenue = sum(inv.get("platform_fee", 0) + inv.get("buyer_premium", 0) for inv in all_buyer_invoices)
    total_volume = sum(inv.get("hammer_price", 0) for inv in all_buyer_invoices)
    
    # Outstanding amounts
    pending_invoices = await _db.vehicle_invoices.find({
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

@vehicle_admin_router.post("/vehicle-payments/invoice/{invoice_id}/checkout")
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


@vehicle_admin_router.post("/vehicle-payments/deposit/{vehicle_id}/checkout")
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
    listing = await _db.vehicle_listings.find_one({"id": vehicle_id})
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


@vehicle_admin_router.get("/vehicle-payments/status/{session_id}")
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


@vehicle_admin_router.post("/webhook/stripe")
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

@vehicle_admin_router.post("/vehicle-documents/upload")
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


@vehicle_admin_router.get("/vehicle-documents/my")
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


@vehicle_admin_router.get("/vehicle-documents/required")
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


@vehicle_admin_router.get("/vehicle-documents/{document_id}")
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

@vehicle_admin_router.get("/vehicle-admin/documents/pending")
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


@vehicle_admin_router.post("/vehicle-admin/documents/{document_id}/approve")
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


@vehicle_admin_router.post("/vehicle-admin/documents/{document_id}/reject")
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


@vehicle_admin_router.get("/vehicle-admin/documents/seller/{seller_id}")
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

@vehicle_admin_router.get("/vehicle-admin/scheduler/status")
async def admin_get_scheduler_status(admin: dict = Depends(get_admin_user)):
    """Admin: Get scheduler status and job list"""
    status = get_scheduler_status()
    return status


@vehicle_admin_router.post("/vehicle-admin/scheduler/run/{job_id}")
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

@vehicle_admin_router.get("/vehicle-admin/tax-reports")
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


@vehicle_admin_router.get("/vehicle-admin/tax-reports/{report_id}")
async def admin_get_tax_report(
    report_id: str,
    admin: dict = Depends(get_admin_user)
):
    """Admin: Get specific tax report with full details"""
    report = await get_tax_report_by_id(db, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Tax report not found")
    return report


@vehicle_admin_router.get("/vehicle-admin/tax-reports/{report_id}/download")
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


@vehicle_admin_router.post("/vehicle-admin/tax-reports/generate/gst-hst")
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


@vehicle_admin_router.post("/vehicle-admin/tax-reports/generate/qst")
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


@vehicle_admin_router.post("/vehicle-admin/tax-reports/generate/seller-payments")
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


@vehicle_admin_router.post("/vehicle-admin/tax-reports/generate/annual-summary")
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

@vehicle_admin_router.get("/vehicle-invoices/{invoice_id}/pdf")
async def download_invoice_pdf(
    invoice_id: str,
    lang: str = "en",
    user: dict = Depends(get_current_user)
):
    """
    Download invoice as PDF.
    
    Query params:
      - lang: "en" (default) or "fr" — localizes key labels
    
    Generates a professional PDF invoice with:
    - Full BidVex branding
    - Business Number (BN) and GST/HST registration numbers
    - Complete line items with tax breakdown
    - Payment status and deadline
    - Subscription savings if applicable
    """
    # Verify user has access to this invoice
    db = _db  # module-level db handle set by server.py
    invoice = await get_invoice_by_id(db, invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    
    # Check access - buyer, seller, or admin
    is_buyer = invoice.get("buyer_id") == user["id"]
    is_seller = invoice.get("seller_id") == user["id"]
    is_admin = user.get("role") in ["admin", "super_admin"]
    
    if not (is_buyer or is_seller or is_admin):
        raise HTTPException(status_code=403, detail="Access denied to this invoice")
    
    # Validate language
    if lang not in ("en", "fr"):
        lang = "en"

    # Generate PDF
    pdf_bytes = await generate_invoice_pdf(db, invoice_id, lang=lang)
    if not pdf_bytes:
        raise HTTPException(status_code=500, detail="Failed to generate PDF")
    
    from fastapi.responses import Response
    
    filename = f"BidVex_{'Facture' if lang == 'fr' else 'Invoice'}_{invoice.get('invoice_number', invoice_id[:8])}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@vehicle_admin_router.get("/vehicle-invoices/{invoice_id}/settlement-pdf")
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