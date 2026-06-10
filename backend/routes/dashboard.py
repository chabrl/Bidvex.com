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
    # iter298 BUG 2/5 — `ended_no_sale` (zero-bid) + storage `unsold`
    # join the Ended bucket.
    _ENDED_STATUSES = ("sold", "ended", "expired", "completed", "ended_no_sale", "unsold")

    # iter296 P0 BUG 5 — Same union as routes/listings.py + routes/users.py:
    # a listing is "sold" if EITHER `status: "sold"` (vehicle/storage
    # convention) OR (`status: "ended"` + `winner_user_id` is set —
    # marketplace + lots convention). The old code only checked the
    # first half so the user-visible Articles Vendus / Sold Items card
    # was stuck at 0 for marketplace listings.
    def _is_sold(l: dict) -> bool:
        if l.get("status") == "sold":
            return True
        if l.get("status") == "ended" and l.get("winner_user_id"):
            return True
        return False

    # iter298 BUG 3/5 — payment lifecycle splits within the Ended bucket.
    def _is_payment_collected(l: dict) -> bool:
        return l.get("payment_status") == "payment_collected"

    def _is_payment_failed(l: dict) -> bool:
        return l.get("payment_status") == "payment_failed"

    def _is_no_sale(l: dict) -> bool:
        return (
            l.get("status") in ("ended_no_sale", "unsold")
            or (l.get("status") in ("ended", "expired") and not l.get("winner_user_id"))
        )

    active_listings = [l for l in all_listings if l.get("status") == "active"]
    sold_listings = [l for l in all_listings if _is_sold(l)]
    draft_listings = [l for l in all_listings if l.get("status") == "draft"]
    pending_review_listings = [l for l in all_listings if l.get("status") in _PENDING_STATUSES]
    ended_listings = [l for l in all_listings if l.get("status") in _ENDED_STATUSES]
    no_sale_listings = [l for l in ended_listings if _is_no_sale(l)]
    payment_collected_listings = [l for l in ended_listings if _is_payment_collected(l)]
    payment_failed_listings = [l for l in ended_listings if _is_payment_failed(l)]
    completed_listings = [l for l in all_listings if l.get("status") == "completed"]

    counts = {
        "total":             len(all_listings),
        "active":            len(active_listings),
        "pending_review":    len(pending_review_listings),
        "draft":             len(draft_listings),
        "ended":             len(ended_listings),
        "sold":              len(sold_listings),
        # iter298 BUG 5 — Ended split.
        "ended_no_sale":     len(no_sale_listings),
        "payment_collected": len(payment_collected_listings),
        "payment_failed":    len(payment_failed_listings),
        "completed":         len(completed_listings),
    }

    # Post-sale Contact Info — enrich every sold/ended listing with the
    # buyer's contact details so the seller can complete the transaction.
    # Only sold (transaction confirmed) — no info leaked for active listings.
    buyer_ids = {
        l.get("winner_user_id") or l.get("highest_bidder_id") or l.get("winner_id")
        for l in sold_listings
        if l.get("winner_user_id") or l.get("highest_bidder_id") or l.get("winner_id")
    }
    buyer_lookup = {}
    if buyer_ids:
        buyer_docs = await rdb.users.find(
            {"id": {"$in": list(buyer_ids)}},
            {"_id": 0, "id": 1, "name": 1, "email": 1, "phone": 1},
        ).to_list(len(buyer_ids))
        buyer_lookup = {u["id"]: u for u in buyer_docs}
    for l in sold_listings:
        bid = l.get("winner_user_id") or l.get("highest_bidder_id") or l.get("winner_id")
        b = buyer_lookup.get(bid) if bid else None
        if b:
            l["buyer_contact"] = {
                "name":  b.get("name", ""),
                "email": b.get("email", ""),
                "phone": b.get("phone", ""),
            }

    # iter296 — prefer `final_price` (snapshot at end time) over the
    # live `current_price` so the total doesn't drift if `current_price`
    # is later mutated by an admin tool.
    total_sales = sum(
        float(l.get("final_price") or l.get("current_price") or 0)
        for l in sold_listings
    )

    # iter298 BUG 5 — payment-collected revenue metrics. `total_sales`
    # above remains the legacy all-sold metric; these two only count
    # listings whose payment has actually been collected.
    collected_sales = sum(
        float(l.get("final_price") or l.get("current_price") or 0)
        for l in payment_collected_listings
    )
    net_payout_total = sum(
        float(l.get("net_payout_amount")
              or round(float(l.get("final_price") or l.get("current_price") or 0) * 0.975, 2))
        for l in payment_collected_listings
    )

    return {
        "active_listings": len(active_listings),
        "sold_listings": len(sold_listings),
        "draft_listings": len(draft_listings),
        "total_sales": total_sales,
        # iter298 BUG 5 — payment-collected metrics + statement links.
        "collected_sales": collected_sales,
        "net_payout_total": round(net_payout_total, 2),
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

    # Post-sale Contact Info — for each WON listing (user is the winner
    # AND auction has ended), surface the seller's contact details so the
    # buyer can complete the transaction. Pulled from existing user profile;
    # no info leaked for active listings.
    # iter298 BUG 5 — winner detection covers all conventions:
    # `winner_user_id` (canonical since iter296), legacy `winner_id`,
    # and `highest_bidder_id` on ended/sold docs.
    def _is_won_by_me(l: dict) -> bool:
        if l.get("status") not in ("sold", "ended", "completed"):
            return False
        me = current_user.id
        return (
            l.get("winner_user_id") == me
            or l.get("winner_id") == me
            or l.get("highest_bidder_id") == me
        )

    won_listings = [l for l in listings if _is_won_by_me(l)]
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

    # iter298 BUG 5 — attach receipt link + payment/pickup status to won rows.
    won_ids = [l["id"] for l in won_listings]
    receipt_rows = []
    if won_ids:
        receipt_rows = await rdb.receipts.find(
            {"user_id": current_user.id, "type": "buyer_receipt",
             "listing_id": {"$in": won_ids}},
            {"_id": 0, "id": 1, "listing_id": 1},
        ).to_list(200)
    receipt_by_listing = {r["listing_id"]: r["id"] for r in receipt_rows}
    won_items_detail = []
    for l in won_listings:
        won_items_detail.append({
            "listing_id": l["id"],
            "title": l.get("title", "Item"),
            "final_price": l.get("final_price") or l.get("current_price") or 0,
            "payment_status": l.get("payment_status") or ("pending_payment" if not l.get("payment_collected_at") else "payment_collected"),
            "payment_link_url": l.get("payment_link_url"),
            "pickup_confirmed": bool(l.get("pickup_confirmed")),
            "pickup_confirmed_at": l.get("pickup_confirmed_at"),
            "receipt_id": receipt_by_listing.get(l["id"]),
            "sold_at": l.get("sold_at") or l.get("ended_at"),
        })

    # iter298 BUG 5 — winning (live high-bidder), lost, and deposits.
    listings_by_id = {l["id"]: l for l in listings}
    my_max_bid: dict = {}
    for b in bids:
        lid = b.get("listing_id")
        if lid:
            my_max_bid[lid] = max(my_max_bid.get(lid, 0), float(b.get("amount") or 0))

    winning_bid_ids = []
    lost_bid_ids = []
    for lid, my_max in my_max_bid.items():
        l = listings_by_id.get(lid)
        if not l:
            continue
        if l.get("status") == "active":
            is_leader = (
                l.get("highest_bidder_id") == current_user.id
                or float(l.get("current_price") or 0) == my_max
            )
            if is_leader:
                winning_bid_ids.append(lid)
        elif l.get("status") in ("sold", "ended", "completed", "ended_no_sale"):
            if not _is_won_by_me(l):
                lost_bid_ids.append(lid)

    deposits = await rdb.bidding_deposits.find(
        {"user_id": current_user.id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    storage_deps = await rdb.storage_deposits.find(
        {"user_id": current_user.id}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)
    for d in storage_deps:
        d["deposit_type"] = "storage"
    for d in deposits:
        d.setdefault("deposit_type", "bidding")

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
        # iter298 BUG 5 — corrected won counter + new winning/lost/deposits.
        "won_items": len(won_listings),
        "won_items_detail": won_items_detail,
        "winning_bids": len(winning_bid_ids),
        "winning_listing_ids": winning_bid_ids,
        "lost_bids": len(lost_bid_ids),
        "lost_listing_ids": lost_bid_ids,
        "deposits": deposits + storage_deps,
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
