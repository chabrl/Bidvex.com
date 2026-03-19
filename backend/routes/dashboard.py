"""
BidVex Dashboard Router
User-facing dashboard endpoints for buyers and sellers.
"""

from fastapi import APIRouter, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import logging

logger = logging.getLogger(__name__)

dashboard_router = APIRouter(prefix="/dashboard", tags=["Dashboard"])
security = HTTPBearer(auto_error=False)

_db = None
_get_current_user = None


def set_dashboard_db(db_instance):
    global _db
    _db = db_instance


def set_dashboard_auth(get_current_user_func):
    global _get_current_user

    async def wrapper(credentials):
        class MockRequest:
            cookies = {}
        return await get_current_user_func(MockRequest(), credentials)

    _get_current_user = wrapper


@dashboard_router.get("/seller")
async def get_seller_dashboard(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user(credentials)

    # Fetch single listings
    listings = await _db.listings.find(
        {"seller_id": current_user.id}, {"_id": 0}
    ).to_list(1000)

    # Fetch multi-item listings
    multi_listings = await _db.multi_item_listings.find(
        {"seller_id": current_user.id}, {"_id": 0}
    ).to_list(1000)

    all_listings = listings + multi_listings

    active_listings = [l for l in all_listings if l["status"] == "active"]
    sold_listings = [l for l in all_listings if l["status"] == "sold"]
    draft_listings = [l for l in all_listings if l["status"] == "draft"]

    total_sales = sum(l.get("current_price", 0) for l in sold_listings)

    return {
        "active_listings": len(active_listings),
        "sold_listings": len(sold_listings),
        "draft_listings": len(draft_listings),
        "total_sales": total_sales,
        "listings": listings,
        "multi_item_listings": multi_listings,
        "all_listings": all_listings,
    }


@dashboard_router.get("/buyer")
async def get_buyer_dashboard(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user(credentials)

    bids = await _db.bids.find(
        {"bidder_id": current_user.id}, {"_id": 0}
    ).to_list(1000)

    listing_ids = list(set(bid["listing_id"] for bid in bids))
    listings = await _db.listings.find(
        {"id": {"$in": listing_ids}}, {"_id": 0}
    ).to_list(1000)

    # Fetch watchlist items
    watchlist_items = await _db.watchlist.find(
        {"user_id": current_user.id}, {"_id": 0}
    ).to_list(100)
    watchlist_listing_ids = [item["listing_id"] for item in watchlist_items if "listing_id" in item]
    watchlist_listings = await _db.listings.find(
        {"id": {"$in": watchlist_listing_ids}, "status": {"$ne": "deleted"}},
        {"_id": 0},
    ).to_list(100)

    return {
        "total_bids": len(bids),
        "active_bids": len(
            [
                b
                for b in bids
                if any(
                    l["status"] == "active"
                    for l in listings
                    if l["id"] == b["listing_id"]
                )
            ]
        ),
        "won_items": len([l for l in listings if l["status"] == "sold"]),
        "bids": bids,
        "listings": listings,
        "watchlist": watchlist_listings,
    }
