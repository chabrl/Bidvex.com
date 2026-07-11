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
        if item_type not in ['listing', 'auction', 'lot', 'vehicle', 'storage']:
            raise HTTPException(status_code=400, detail="Invalid item_type. Must be 'listing', 'auction', 'lot', 'vehicle', or 'storage'")

        if item_type == 'listing':
            item = await db.listings.find_one({"id": item_id}, {"_id": 0})
            if not item:
                raise HTTPException(status_code=404, detail="Listing not found")
        elif item_type == 'auction':
            item = await db.multi_item_listings.find_one({"id": item_id}, {"_id": 0})
            if not item:
                raise HTTPException(status_code=404, detail="Auction not found")
        elif item_type == 'vehicle':
            # iter343 BUG-5 — vehicle listings are watchable too
            item = await db.vehicle_listings.find_one({"id": item_id}, {"_id": 0, "id": 1})
            if not item:
                raise HTTPException(status_code=404, detail="Vehicle listing not found")
        elif item_type == 'storage':
            # iter343 BUG-5 — storage auctions are watchable too
            item = await db.storage_auctions.find_one({"id": item_id}, {"_id": 0, "id": 1})
            if not item:
                raise HTTPException(status_code=404, detail="Storage auction not found")
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
    """User's watchlist with item details (iter343 BUG-5 overhaul).

    ROOT CAUSES fixed:
      • Rows whose lookup failed (deleted/ended-purged docs) were silently
        DROPPED while `total` counted raw rows → count/cards mismatch and
        "missing" items. Unresolvable rows now come back as
        `unavailable: true` placeholders.
      • Lot cards read `lot.current_price`, but raw lot docs only carry
        `current_bid` (current_price is computed in the lots GET endpoint)
        → blank prices. Normalized here.
      • Vehicle & storage collections were not supported at all.
    """
    db = get_db()
    try:
        watchlist_items = await db.watchlist.find(
            {"user_id": current_user.id}, {"_id": 0}
        ).sort("added_at", -1).to_list(200)

        result = {"listings": [], "auctions": [], "lots": [],
                  "vehicles": [], "storage": [], "unavailable": [],
                  "total": len(watchlist_items)}
        if not watchlist_items:
            return result

        def _placeholder(item):
            return {
                "unavailable": True,
                "item_id": item.get("item_id") or item.get("listing_id"),
                "item_type": item.get("item_type", "listing"),
                "watchlist_added_at": item.get("added_at"),
            }

        by_type = {}
        for i in watchlist_items:
            by_type.setdefault(i.get("item_type", "listing"), []).append(i)

        # ── Simple id→doc collections ─────────────────────────────────
        simple_specs = [
            ("listing", db.listings,           "listings"),
            ("auction", db.multi_item_listings, "auctions"),
            ("vehicle", db.vehicle_listings,    "vehicles"),
            ("storage", db.storage_auctions,    "storage"),
        ]
        for type_key, coll, out_key in simple_specs:
            items = by_type.get(type_key) or []
            if not items:
                continue
            ids = [i.get("item_id") or i.get("listing_id") for i in items]
            docs = await coll.find(
                {"id": {"$in": ids}, "status": {"$ne": "deleted"}}, {"_id": 0}
            ).to_list(200)
            doc_map = {d["id"]: d for d in docs}
            for item in items:
                item_id = item.get("item_id") or item.get("listing_id")
                doc = doc_map.get(item_id)
                if not doc:
                    result["unavailable"].append(_placeholder(item))
                    continue
                # Normalize price/title/images across collections
                if doc.get("current_price") in (None, 0):
                    doc["current_price"] = doc.get("current_bid") or doc.get("starting_price")
                if not doc.get("title"):
                    if type_key == "vehicle":
                        doc["title"] = " ".join(str(x) for x in (doc.get("year"), doc.get("make"), doc.get("model")) if x).strip() or "Vehicle"
                    elif type_key == "storage":
                        doc["title"] = doc.get("description_en") or f"Storage unit {doc.get('unit_size') or ''}".strip()
                if not doc.get("images"):
                    doc["images"] = doc.get("photos") or []
                if not doc.get("city"):
                    doc["city"] = doc.get("facility_city")
                if not doc.get("region"):
                    doc["region"] = doc.get("province") or doc.get("facility_province")
                if not doc.get("auction_end_date"):
                    end = doc.get("end_time") or doc.get("end_date")
                    doc["auction_end_date"] = end if isinstance(end, str) else (end.isoformat() if end else None)
                result[out_key].append({**doc, "watchlist_added_at": item["added_at"], "watchlist_type": type_key})

        # ── Individual lots ("auction_id:lot_number") ─────────────────
        lot_items = by_type.get("lot") or []
        if lot_items:
            parent_ids = list({i["item_id"].split(":")[0] for i in lot_items if ":" in i["item_id"]})
            parents = await db.multi_item_listings.find(
                {"id": {"$in": parent_ids}}, {"_id": 0}
            ).to_list(200)
            parent_map = {p["id"]: p for p in parents}
            for item in lot_items:
                item_id = item["item_id"]
                if ":" not in item_id:
                    result["unavailable"].append(_placeholder(item))
                    continue
                auction_id, lot_number = item_id.split(":")
                auction = parent_map.get(auction_id)
                lot = None
                if auction:
                    try:
                        lot = next((l for l in auction.get("lots", []) if l.get("lot_number") == int(lot_number)), None)
                    except ValueError:
                        lot = None
                if not auction or not lot:
                    result["unavailable"].append(_placeholder(item))
                    continue
                # iter343 — raw lots carry `current_bid`; normalize price
                if lot.get("current_price") in (None, 0):
                    lot = {**lot, "current_price": lot.get("current_bid") or lot.get("starting_price")}
                result["lots"].append({
                    "auction_id": auction_id,
                    "auction_title": auction.get("title"),
                    "auction_status": auction.get("status"),
                    "lot": lot,
                    "watchlist_added_at": item["added_at"],
                    "watchlist_type": "lot",
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


@watchlist_router.get("/wishlist/status/{auction_id}")
async def get_wishlist_status(
    auction_id: str,
    lot_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
):
    """iter217 — Returns whether the current user has THIS specific
    auction (and optionally lot) saved. Lets the heart icon render the
    correct initial filled/unfilled state on every detail page."""
    db = get_db()
    query = {"user_id": current_user.id, "auction_id": auction_id}
    if lot_id:
        query["lot_id"] = lot_id
    item = await db.wishlist.find_one(query, {"_id": 0})
    return {"is_wishlisted": bool(item), "wishlist_id": item.get("id") if item else None}
