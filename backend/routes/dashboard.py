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
_db_read = None
_get_current_user = None


def set_dashboard_db(db_instance):
    global _db
    _db = db_instance


def set_dashboard_read_db(db_instance):
    global _db_read
    _db_read = db_instance


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

    rdb = _db_read if _db_read is not None else _db
    # Fetch single listings
    listings = await rdb.listings.find(
        {"seller_id": current_user.id}, {"_id": 0}
    ).to_list(1000)

    # Fetch multi-item listings
    multi_listings = await rdb.multi_item_listings.find(
        {"seller_id": current_user.id}, {"_id": 0}
    ).to_list(1000)

    all_listings = listings + multi_listings

    # HOTFIX v9.1 / Fix 3 — Seller dashboard filter-tab counts.
    # A listing is "pending_review" when it sits in any of the three
    # review-pending statuses surfaced by the AI Watchdog or Manual Review
    # flow: pending_ai_review, pending_admin_review, pending_review.
    _PENDING_STATUSES = ("pending_ai_review", "pending_admin_review", "pending_review")
    _ENDED_STATUSES = ("sold", "ended", "expired", "completed")

    active_listings = [l for l in all_listings if l.get("status") == "active"]
    sold_listings = [l for l in all_listings if l.get("status") == "sold"]
    draft_listings = [l for l in all_listings if l.get("status") == "draft"]
    pending_review_listings = [l for l in all_listings if l.get("status") in _PENDING_STATUSES]
    ended_listings = [l for l in all_listings if l.get("status") in _ENDED_STATUSES]

    counts = {
        "total":          len(all_listings),
        "active":         len(active_listings),
        "pending_review": len(pending_review_listings),
        "draft":          len(draft_listings),
        "ended":          len(ended_listings),
        "sold":           len(sold_listings),
    }

    # Post-sale Contact Info — enrich every sold/ended listing with the
    # buyer's contact details so the seller can complete the transaction.
    # Only sold (transaction confirmed) — no info leaked for active listings.
    buyer_ids = {l.get("highest_bidder_id") or l.get("winner_id") for l in sold_listings if l.get("highest_bidder_id") or l.get("winner_id")}
    buyer_lookup = {}
    if buyer_ids:
        buyer_docs = await rdb.users.find(
            {"id": {"$in": list(buyer_ids)}},
            {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1},
        ).to_list(len(buyer_ids))
        buyer_lookup = {u["id"]: u for u in buyer_docs}
    for l in sold_listings:
        bid = l.get("highest_bidder_id") or l.get("winner_id")
        b = buyer_lookup.get(bid) if bid else None
        if b:
            l["buyer_contact"] = {
                "name":  b.get("name", ""),
                "email": b.get("email", ""),
                "phone": b.get("phone", ""),
            }

    total_sales = sum(l.get("current_price", 0) for l in sold_listings)

    return {
        "active_listings": len(active_listings),
        "sold_listings": len(sold_listings),
        "draft_listings": len(draft_listings),
        "total_sales": total_sales,
        "listings": listings,
        "multi_item_listings": multi_listings,
        "all_listings": all_listings,
        # HOTFIX v9.1 / Fix 3 — Filter-tab counts for the seller dashboard.
        "counts": counts,
    }


@dashboard_router.get("/buyer")
async def get_buyer_dashboard(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user(credentials)

    rdb = _db_read if _db_read is not None else _db
    bids = await rdb.bids.find(
        {"bidder_id": current_user.id}, {"_id": 0}
    ).to_list(1000)

    listing_ids = list(set(bid["listing_id"] for bid in bids))
    listings = await rdb.listings.find(
        {"id": {"$in": listing_ids}}, {"_id": 0}
    ).to_list(1000)

    # Fetch watchlist items
    watchlist_items = await rdb.watchlist.find(
        {"user_id": current_user.id}, {"_id": 0}
    ).to_list(100)
    watchlist_listing_ids = [item["listing_id"] for item in watchlist_items if "listing_id" in item]
    watchlist_listings = await rdb.listings.find(
        {"id": {"$in": watchlist_listing_ids}, "status": {"$ne": "deleted"}},
        {"_id": 0},
    ).to_list(100)

    # Post-sale Contact Info — for each WON listing (user is the highest bidder
    # AND status is sold/ended), surface the seller's contact details so the
    # buyer can complete the transaction. Pulled from existing user profile;
    # no info leaked for active listings.
    won_listings = [
        l for l in listings
        if l.get("status") == "sold"
        and (l.get("highest_bidder_id") == current_user.id or l.get("winner_id") == current_user.id)
    ]
    seller_ids = {l.get("seller_id") for l in won_listings if l.get("seller_id")}
    seller_lookup = {}
    if seller_ids:
        seller_docs = await rdb.users.find(
            {"id": {"$in": list(seller_ids)}},
            {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1},
        ).to_list(len(seller_ids))
        seller_lookup = {u["id"]: u for u in seller_docs}
    for l in won_listings:
        s = seller_lookup.get(l.get("seller_id"))
        if s:
            l["seller_contact"] = {
                "name":  s.get("name", ""),
                "email": s.get("email", ""),
                "phone": s.get("phone", ""),
            }

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


# iter206 — Seller-facing compliance notifications (pause / approval / rejection)
@dashboard_router.get("/seller/notifications")
async def get_seller_notifications(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")

    current_user = await _get_current_user(credentials)
    rdb = _db_read if _db_read is not None else _db
    notifications = await rdb.seller_notifications.find(
        {"seller_id": current_user.id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(50)
    unread = sum(1 for n in notifications if not n.get("read"))
    return {"notifications": notifications, "unread": unread}


@dashboard_router.post("/seller/notifications/{notification_kind}/mark-read")
async def mark_seller_notification_read(
    notification_kind: str,  # "all" or a specific kind
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")
    current_user = await _get_current_user(credentials)
    query = {"seller_id": current_user.id}
    if notification_kind != "all":
        query["kind"] = notification_kind
    res = await _db.seller_notifications.update_many(query, {"$set": {"read": True}})
    return {"ok": True, "marked": res.modified_count}



# iter211 — Pickup-coordination notifications (post-payment winner ↔ seller)
@dashboard_router.get("/pickup-notifications")
async def get_pickup_notifications(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Return pickup-coordination rows for the current user (winner or seller side)."""
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")
    current_user = await _get_current_user(credentials)
    rdb = _db_read if _db_read is not None else _db
    notifications = await rdb.pickup_notifications.find(
        {"user_id": current_user.id},
        {"_id": 0},
    ).sort("created_at", -1).to_list(50)
    unread = sum(1 for n in notifications if not n.get("read"))
    return {"notifications": notifications, "unread": unread}


@dashboard_router.post("/pickup-notifications/{notification_id}/mark-read")
async def mark_pickup_notification_read(
    notification_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    if not credentials:
        from fastapi import HTTPException
        raise HTTPException(status_code=401, detail="Authentication required")
    current_user = await _get_current_user(credentials)
    query = {"user_id": current_user.id}
    if notification_id != "all":
        query["id"] = notification_id
    res = await _db.pickup_notifications.update_many(query, {"$set": {"read": True}})
    return {"ok": True, "marked": res.modified_count}
