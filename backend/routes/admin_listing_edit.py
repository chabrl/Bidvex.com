"""
BidVex — Admin full-listing edit endpoint.
Separate file to avoid touching the massive admin.py.
"""
from typing import Optional
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import logging

from deps import get_db, require_admin, User

logger = logging.getLogger(__name__)
admin_listing_edit_router = APIRouter(tags=["Admin Listing Edit"])


class AdminListingUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    starting_price: Optional[float] = None
    reserve_price: Optional[float] = None
    buy_now_price: Optional[float] = None
    city: Optional[str] = None
    region: Optional[str] = None


@admin_listing_edit_router.put("/admin/listings/{listing_id}")
async def admin_edit_listing(
    listing_id: str,
    data: AdminListingUpdate,
    current_user: User = Depends(require_admin),
):
    """Admin edits a single-item auction listing (title, price, location, etc.)."""
    db = get_db()
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    update = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Sanity: prices must be non-negative
    for k in ("starting_price", "reserve_price", "buy_now_price"):
        if k in update and update[k] is not None and update[k] < 0:
            raise HTTPException(status_code=400, detail=f"{k} cannot be negative")

    now = datetime.now(timezone.utc)
    update["updated_at"] = now
    update["last_edited_by_admin"] = current_user.email

    await db.listings.update_one({"id": listing_id}, {"$set": update})
    await db.admin_logs.insert_one({
        "id": f"edit-{listing_id}-{int(now.timestamp())}",
        "action": "admin_edit_listing",
        "admin_email": current_user.email,
        "admin_id": getattr(current_user, "id", None),
        "details": {"listing_id": listing_id, "changed": list(data.model_dump(exclude_none=True).keys())},
        "timestamp": now.isoformat(),
    })
    logger.info(f"[ADMIN] {current_user.email} edited listing {listing_id}: {list(update.keys())}")
    return {"success": True, "id": listing_id, "updated_fields": list(update.keys())}


@admin_listing_edit_router.put("/admin/multi-item-listings/{listing_id}")
async def admin_edit_multi_listing(
    listing_id: str,
    data: AdminListingUpdate,
    current_user: User = Depends(require_admin),
):
    """Admin edits a multi-item auction's header (not individual lots)."""
    db = get_db()
    listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Multi-item listing not found")

    # For multi-item listings, only a subset of fields makes sense
    allowed = {"title", "description", "category", "city", "region"}
    update = {k: v for k, v in data.model_dump(exclude_none=True).items() if k in allowed}
    if not update:
        raise HTTPException(status_code=400, detail="No editable fields supplied")

    now = datetime.now(timezone.utc)
    update["updated_at"] = now
    update["last_edited_by_admin"] = current_user.email

    await db.multi_item_listings.update_one({"id": listing_id}, {"$set": update})
    await db.admin_logs.insert_one({
        "id": f"edit-multi-{listing_id}-{int(now.timestamp())}",
        "action": "admin_edit_multi_listing",
        "admin_email": current_user.email,
        "admin_id": getattr(current_user, "id", None),
        "details": {"listing_id": listing_id, "changed": list(update.keys())},
        "timestamp": now.isoformat(),
    })
    return {"success": True, "id": listing_id, "updated_fields": list(update.keys())}
