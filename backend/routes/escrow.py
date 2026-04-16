"""
BidVex — Escrow Routes
Pickup code confirmation, escrow status, dispute initiation.
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any
from deps import get_current_user, User, get_db
from services.escrow_service import confirm_pickup, get_buyer_escrow_status, get_seller_escrow_status, initiate_dispute
from services.stripe_customer_service import charge_cancellation_penalty

escrow_router = APIRouter(prefix="/escrow", tags=["Escrow"])


@escrow_router.post("/seller/confirm-pickup")
async def seller_confirm_pickup(
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """Seller enters the 6-character pickup code to release funds."""
    db = get_db()
    auction_id = data.get("auction_id", "").strip()
    code = data.get("code", "").strip()
    if not auction_id or not code:
        raise HTTPException(status_code=400, detail="auction_id and code are required")
    return await confirm_pickup(db, current_user.id, auction_id, code)


@escrow_router.get("/buyer/status")
async def buyer_escrow_status(current_user: User = Depends(get_current_user)):
    """Get all escrow transactions for the current buyer."""
    db = get_db()
    return await get_buyer_escrow_status(db, current_user.id)


@escrow_router.get("/seller/status")
async def seller_escrow_status(current_user: User = Depends(get_current_user)):
    """Get all escrow transactions for the current seller."""
    db = get_db()
    return await get_seller_escrow_status(db, current_user.id)


@escrow_router.post("/dispute")
async def open_dispute(
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """Open a dispute on a held escrow transaction."""
    db = get_db()
    auction_id = data.get("auction_id", "").strip()
    reason = data.get("reason", "").strip()
    if not auction_id or not reason:
        raise HTTPException(status_code=400, detail="auction_id and reason are required")
    return await initiate_dispute(db, auction_id, current_user.id, reason)


@escrow_router.post("/admin/charge-penalty")
async def admin_charge_penalty(
    data: Dict[str, Any],
    current_user: User = Depends(get_current_user),
):
    """Admin-only: charge $50 cancellation penalty to a seller."""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    seller_id = data.get("seller_id", "").strip()
    listing_id = data.get("listing_id", "").strip()
    reason = data.get("reason", "Non-delivery after auction close")
    if not seller_id or not listing_id:
        raise HTTPException(status_code=400, detail="seller_id and listing_id are required")
    return await charge_cancellation_penalty(db, seller_id, listing_id, reason)



@escrow_router.get("/admin/escrow/transactions")
async def admin_list_escrows(current_user: User = Depends(get_current_user)):
    """Admin: list all escrow transactions."""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    escrows = await db.escrow_transactions.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return escrows


@escrow_router.get("/admin/escrow/penalties")
async def admin_list_penalties(current_user: User = Depends(get_current_user)):
    """Admin: list all penalty charges."""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    penalties = await db.penalty_log.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return penalties


@escrow_router.get("/admin/escrow/disputes")
async def admin_list_disputes(current_user: User = Depends(get_current_user)):
    """Admin: list all escrow disputes."""
    if current_user.role not in ["admin", "superadmin"]:
        raise HTTPException(status_code=403, detail="Admin access required")
    db = get_db()
    disputes = await db.escrow_disputes.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return disputes
