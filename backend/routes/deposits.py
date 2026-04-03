"""
BidVex Bidding Deposits Router
Handles pre-authorization holds for high-value auctions (>$10k).
"""

from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime, timezone
import logging

from services.pricing_config import DEPOSIT_THRESHOLD_CAD, DEPOSIT_AMOUNT_CENTS, DEPOSIT_AMOUNT_DOLLARS
from services.connect_payment_engine import create_deposit_hold, release_deposit, capture_deposit

logger = logging.getLogger(__name__)

deposits_router = APIRouter(prefix="/deposits", tags=["Deposits"])
security = HTTPBearer(auto_error=False)

_db = None
_get_current_user = None


def set_deposits_db(db_instance):
    global _db
    _db = db_instance


def set_deposits_auth(auth_func):
    global _get_current_user

    async def wrapper(credentials):
        class MockRequest:
            cookies = {}
        return await auth_func(MockRequest(), credentials)

    _get_current_user = wrapper


def get_db():
    if _db is None:
        raise RuntimeError("Database not initialized")
    return _db


class DepositRequest(BaseModel):
    listing_id: str = Field(..., description="ID of the high-value listing")


@deposits_router.post("/create")
async def create_bidding_deposit(
    data: DepositRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """
    Create a $1,000 pre-authorization hold for a high-value auction.
    Required when listing starting_price > $10,000 CAD.
    """
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    db = get_db()
    current_user = await _get_current_user(credentials)

    # Verify listing exists and qualifies
    listing = await db.listings.find_one({"id": data.listing_id})
    if not listing:
        # Check multi_item_listings too
        listing = await db.multi_item_listings.find_one({"id": data.listing_id})

    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    starting_price = listing.get("starting_price", 0)
    currency = listing.get("currency", "CAD")

    if starting_price < DEPOSIT_THRESHOLD_CAD:
        raise HTTPException(
            status_code=400,
            detail=f"Deposit not required for listings under ${DEPOSIT_THRESHOLD_CAD:,} {currency}",
        )

    # Check if user already has an active deposit for this listing
    existing = await db.bidding_deposits.find_one({
        "user_id": current_user.id,
        "listing_id": data.listing_id,
        "status": {"$in": ["requires_confirmation", "requires_capture", "succeeded"]},
    })
    if existing:
        return {
            "deposit_id": existing["id"],
            "status": existing["status"],
            "message": "Active deposit already exists for this listing",
            "client_secret": existing.get("client_secret"),
        }

    result = await create_deposit_hold(
        db=db,
        user_id=current_user.id,
        listing_id=data.listing_id,
        amount_cents=DEPOSIT_AMOUNT_CENTS,
        currency=currency.lower(),
    )

    return result


@deposits_router.get("/status/{listing_id}")
async def check_deposit_status(
    listing_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Check if the current user has a valid deposit for a listing."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    db = get_db()
    current_user = await _get_current_user(credentials)

    deposit = await db.bidding_deposits.find_one(
        {"user_id": current_user.id, "listing_id": listing_id},
        {"_id": 0},
    )

    if not deposit:
        # Check if deposit is required
        listing = await db.listings.find_one({"id": listing_id})
        if not listing:
            listing = await db.multi_item_listings.find_one({"id": listing_id})

        requires_deposit = listing and listing.get("starting_price", 0) >= DEPOSIT_THRESHOLD_CAD

        return {
            "has_deposit": False,
            "requires_deposit": requires_deposit,
            "deposit_amount": DEPOSIT_AMOUNT_DOLLARS,
            "threshold": DEPOSIT_THRESHOLD_CAD,
        }

    return {
        "has_deposit": True,
        "deposit_id": deposit.get("id"),
        "status": deposit.get("status"),
        "amount": deposit.get("amount_cents", 0) / 100,
        "currency": deposit.get("currency", "CAD").upper(),
        "created_at": deposit.get("created_at"),
    }


@deposits_router.get("/my-deposits")
async def get_my_deposits(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Get all deposits for the current user."""
    if not credentials:
        raise HTTPException(status_code=401, detail="Authentication required")

    db = get_db()
    current_user = await _get_current_user(credentials)

    deposits = await db.bidding_deposits.find(
        {"user_id": current_user.id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(50)

    return {"deposits": deposits}
