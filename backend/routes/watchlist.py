"""
Watchlist & Wishlist routes
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from deps import get_current_user, get_db, User
import uuid
import logging

logger = logging.getLogger(__name__)

watchlist_router = APIRouter(tags=["Watchlist & Wishlist"])


class Wishlist(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    auction_id: str
    lot_id: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Watchlist (listings, auctions, lots) ───

@watchlist_router.post("/watchlist/add")
async def add_to_watchlist(
    item_id: str,
    item_type: str = "listing",
    current_user: User = Depends(get_current_user)
):
    """Add an item to user's watchlist"""
    db = get_db()
    try:
        if item_type not in ['listing', 'auction', 'lot']:
            raise HTTPException(status_code=400, detail="Invalid item_type. Must be 'listing', 'auction', or 'lot'")

        if item_type == 'listing':
            item = await db.listings.find_one({"id": item_id}, {"_id": 0})
            if not item:
                raise HTTPException(status_code=404, detail="Listing not found")
        elif item_type == 'auction':
            item = await db.multi_item_listings.find_one({"id": item_id}, {"_id": 0})
            if not item:
                raise HTTPException(status_code=404, detail="Auction not found")
        elif item_type == 'lot':
            item = await db.multi_item_listings.find_one(
                {"lots.lot_number": {"$exists": True}}, {"_id": 0}
            )
            if not item:
                raise HTTPException(status_code=404, detail="Lot not found")

        existing = await db.watchlist.find_one({
            "user_id": current_user.id, "item_id": item_id, "item_type": item_type
        })
        if existing:
            return {"message": "Already in watchlist", "already_added": True}

        watchlist_item = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "item_id": item_id,
            "item_type": item_type,
            "added_at": datetime.now(timezone.utc).isoformat()
        }
        await db.watchlist.insert_one(watchlist_item)
        return {"message": "Added to watchlist", "success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error adding to watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to add to watchlist")


@watchlist_router.post("/watchlist/remove")
async def remove_from_watchlist(
    item_id: str,
    item_type: str = "listing",
    current_user: User = Depends(get_current_user)
):
    """Remove an item from user's watchlist"""
    db = get_db()
    try:
        result = await db.watchlist.delete_one({
            "user_id": current_user.id, "item_id": item_id, "item_type": item_type
        })
        if result.deleted_count == 0:
            return {"message": "Item not in watchlist", "success": False}
        return {"message": "Removed from watchlist", "success": True}
    except Exception as e:
        logger.error(f"Error removing from watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to remove from watchlist")


@watchlist_router.get("/watchlist")
async def get_watchlist(current_user: User = Depends(get_current_user)):
    """Get user's watchlist with item details"""
    db = get_db()
    try:
        watchlist_items = await db.watchlist.find(
            {"user_id": current_user.id}, {"_id": 0}
        ).sort("added_at", -1).to_list(200)

        if not watchlist_items:
            return {"listings": [], "auctions": [], "lots": [], "total": 0}

        listing_items = [i for i in watchlist_items if i.get("item_type", "listing") == "listing"]
        auction_items = [i for i in watchlist_items if i.get("item_type") == "auction"]
        lot_items = [i for i in watchlist_items if i.get("item_type") == "lot"]

        result = {"listings": [], "auctions": [], "lots": [], "total": len(watchlist_items)}

        if listing_items:
            listing_ids = [i.get("item_id") or i.get("listing_id") for i in listing_items]
            listings = await db.listings.find(
                {"id": {"$in": listing_ids}, "status": {"$ne": "deleted"}}, {"_id": 0}
            ).to_list(100)
            listings_map = {l["id"]: l for l in listings}
            for item in listing_items:
                item_id = item.get("item_id") or item.get("listing_id")
                listing = listings_map.get(item_id)
                if listing:
                    result["listings"].append({**listing, "watchlist_added_at": item["added_at"], "watchlist_type": "listing"})

        if auction_items:
            auction_ids = [i["item_id"] for i in auction_items]
            auctions = await db.multi_item_listings.find(
                {"id": {"$in": auction_ids}, "status": {"$ne": "deleted"}}, {"_id": 0}
            ).to_list(100)
            auctions_map = {a["id"]: a for a in auctions}
            for item in auction_items:
                auction = auctions_map.get(item["item_id"])
                if auction:
                    result["auctions"].append({**auction, "watchlist_added_at": item["added_at"], "watchlist_type": "auction"})

        if lot_items:
            for item in lot_items:
                item_id = item["item_id"]
                if ":" in item_id:
                    auction_id, lot_number = item_id.split(":")
                    lot_number = int(lot_number)
                    auction = await db.multi_item_listings.find_one({"id": auction_id}, {"_id": 0})
                    if auction:
                        lot = next((l for l in auction.get("lots", []) if l.get("lot_number") == lot_number), None)
                        if lot:
                            result["lots"].append({
                                "auction_id": auction_id,
                                "auction_title": auction.get("title"),
                                "lot": lot,
                                "watchlist_added_at": item["added_at"],
                                "watchlist_type": "lot"
                            })

        return result
    except Exception as e:
        logger.error(f"Error fetching watchlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch watchlist")


@watchlist_router.get("/watchlist/check/{listing_id}")
async def check_watchlist_status(listing_id: str, current_user: User = Depends(get_current_user)):
    """Check if a listing is in user's watchlist"""
    db = get_db()
    try:
        exists = await db.watchlist.find_one({
            "user_id": current_user.id, "listing_id": listing_id
        })
        return {"in_watchlist": exists is not None}
    except Exception as e:
        logger.error(f"Error checking watchlist status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check watchlist status")


# ─── Lot Watching ───

@watchlist_router.post("/lots/watch")
async def watch_lot(data: Dict[str, Any], current_user: User = Depends(get_current_user)):
    """Add a specific lot to user's watched lots"""
    db = get_db()
    try:
        listing_id = data.get("listing_id")
        lot_number = data.get("lot_number")
        if not listing_id or lot_number is None:
            raise HTTPException(status_code=400, detail="listing_id and lot_number are required")

        existing = await db.lot_watches.find_one({
            "user_id": current_user.id, "listing_id": listing_id, "lot_number": lot_number
        })
        if existing:
            return {"message": "Already watching this lot", "already_watching": True}

        watch = {
            "id": str(uuid.uuid4()),
            "user_id": current_user.id,
            "listing_id": listing_id,
            "lot_number": lot_number,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.lot_watches.insert_one(watch)
        return {"message": "Now watching lot", "success": True}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error watching lot: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to watch lot")


@watchlist_router.delete("/lots/watch")
async def unwatch_lot(listing_id: str, lot_number: int, current_user: User = Depends(get_current_user)):
    """Remove a lot from user's watched lots"""
    db = get_db()
    try:
        result = await db.lot_watches.delete_one({
            "user_id": current_user.id, "listing_id": listing_id, "lot_number": lot_number
        })
        if result.deleted_count == 0:
            return {"message": "Not watching this lot", "success": False}
        return {"message": "Stopped watching lot", "success": True}
    except Exception as e:
        logger.error(f"Error unwatching lot: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to unwatch lot")


@watchlist_router.get("/lots/{listing_id}/watched")
async def get_watched_lots(listing_id: str, current_user: User = Depends(get_current_user)):
    """Get user's watched lots for a specific listing"""
    db = get_db()
    try:
        watches = await db.lot_watches.find(
            {"user_id": current_user.id, "listing_id": listing_id}, {"_id": 0}
        ).to_list(100)
        return {"watched_lots": [w["lot_number"] for w in watches]}
    except Exception as e:
        logger.error(f"Error getting watched lots: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get watched lots")


@watchlist_router.get("/lots/{listing_id}/watch-count/{lot_number}")
async def get_lot_watch_count(listing_id: str, lot_number: int):
    """Get total watch count for a specific lot"""
    db = get_db()
    try:
        count = await db.lot_watches.count_documents({"listing_id": listing_id, "lot_number": lot_number})
        return {"count": count}
    except Exception as e:
        logger.error(f"Error getting lot watch count: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get watch count")


# ─── Wishlist (multi-item auctions) ───

@watchlist_router.post("/wishlist")
async def add_to_wishlist(auction_id: str, lot_id: Optional[str] = None, current_user: User = Depends(get_current_user)):
    """Add auction or specific lot to user's wishlist"""
    db = get_db()
    try:
        existing = await db.wishlist.find_one({
            "user_id": current_user.id, "auction_id": auction_id, "lot_id": lot_id
        })
        if existing:
            return {"message": "Already in wishlist", "wishlist_id": existing["id"]}

        wishlist_item = Wishlist(user_id=current_user.id, auction_id=auction_id, lot_id=lot_id)
        await db.wishlist.insert_one(wishlist_item.model_dump())

        await db.multi_item_listings.update_one(
            {"id": auction_id}, {"$inc": {"wishlist_count": 1}}
        )
        return {"message": "Added to wishlist", "wishlist_id": wishlist_item.id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@watchlist_router.delete("/wishlist/{auction_id}")
async def remove_from_wishlist(auction_id: str, current_user: User = Depends(get_current_user)):
    """Remove auction from user's wishlist"""
    db = get_db()
    try:
        result = await db.wishlist.delete_one({
            "user_id": current_user.id, "auction_id": auction_id
        })
        if result.deleted_count > 0:
            await db.multi_item_listings.update_one(
                {"id": auction_id}, {"$inc": {"wishlist_count": -1}}
            )
            return {"message": "Removed from wishlist"}
        else:
            raise HTTPException(status_code=404, detail="Item not in wishlist")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@watchlist_router.get("/wishlist")
async def get_user_wishlist(current_user: User = Depends(get_current_user)):
    """Get user's wishlist with auction details"""
    db = get_db()
    try:
        wishlist_items = await db.wishlist.find({"user_id": current_user.id}).to_list(100)
        auction_ids = list(set([i["auction_id"] for i in wishlist_items]))
        auctions = await db.multi_item_listings.find({"id": {"$in": auction_ids}}).to_list(100)
        auctions_map = {a["id"]: a for a in auctions}

        result = []
        for item in wishlist_items:
            auction = auctions_map.get(item["auction_id"])
            if auction:
                auction.pop("_id", None)
                result.append({
                    "wishlist_id": item["id"],
                    "auction": auction,
                    "lot_id": item.get("lot_id"),
                    "added_at": item["created_at"].isoformat() if isinstance(item["created_at"], datetime) else item["created_at"]
                })
        return {"wishlist": result, "total": len(result)}
    except Exception as e:
        logger.error(f"Error fetching wishlist: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch wishlist")
