"""
iter304 — "Verified Auction Firm" Badge
=========================================
Admin-only endpoints to grant/revoke the verified_auction_firm boolean
on a user document. Public read-only endpoint returns the badge flag
for any user (used by frontend storefront/listing detail).

Endpoints:
  POST   /api/admin/users/{user_id}/grant-verified-firm  — admin only
  POST   /api/admin/users/{user_id}/revoke-verified-firm — admin only
  GET    /api/users/{user_id}/verified-firm              — public lookup
"""
from datetime import datetime, timezone
import logging

from fastapi import APIRouter, Depends, HTTPException

from deps import User, get_current_user, get_db

logger = logging.getLogger(__name__)

router = APIRouter(tags=["verified-firm"])


async def _require_admin(user: User = Depends(get_current_user)) -> User:
    if getattr(user, "role", None) not in {"admin", "super_admin"}:
        raise HTTPException(status_code=403, detail="Admin access required")
    return user


@router.post("/admin/users/{user_id}/grant-verified-firm")
async def grant_verified_firm(user_id: str, _admin: User = Depends(_require_admin)):
    """Grant the 'Verified Auction Firm' badge. Eligible roles: partner OR vehicle dealer."""
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    # Eligibility: partner or vehicle dealer (storefront_kind in {partner, vehicle_dealer})
    seller_type = (user_doc.get("seller_type") or "").lower()
    role = (user_doc.get("role") or "").lower()
    eligible = (
        seller_type in {"partner", "dealer", "auctioneer"}
        or role in {"partner", "admin", "super_admin"}
        or user_doc.get("is_vehicle_dealer")
        or user_doc.get("vehicle_dealer_verified")
    )
    if not eligible:
        raise HTTPException(
            status_code=400,
            detail="User is not eligible — must be Partner or Vehicle Dealer.",
        )
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "verified_auction_firm": True,
            "verified_auction_firm_granted_at": datetime.now(timezone.utc),
        }},
    )
    return {"ok": True, "user_id": user_id, "verified_auction_firm": True}


@router.post("/admin/users/{user_id}/revoke-verified-firm")
async def revoke_verified_firm(user_id: str, _admin: User = Depends(_require_admin)):
    """Revoke the 'Verified Auction Firm' badge."""
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "verified_auction_firm": False,
            "verified_auction_firm_revoked_at": datetime.now(timezone.utc),
        }},
    )
    return {"ok": True, "user_id": user_id, "verified_auction_firm": False}


@router.get("/users/{user_id}/verified-firm")
async def get_verified_firm(user_id: str):
    """Public read-only — returns whether the user has the badge."""
    db = get_db()
    user_doc = await db.users.find_one({"id": user_id}, {"_id": 0, "verified_auction_firm": 1})
    if not user_doc:
        raise HTTPException(status_code=404, detail="User not found")
    return {"user_id": user_id, "verified_auction_firm": bool(user_doc.get("verified_auction_firm"))}
