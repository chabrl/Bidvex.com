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
    # iter220 Task 4 — Admin can append/remove images directly. Full array
    # replacement (frontend sends the FINAL desired list each time).
    images: Optional[list[str]] = None


@admin_listing_edit_router.put("/admin/listings/{listing_id}")
async def admin_edit_listing(
    listing_id: str,
    data: AdminListingUpdate,
    current_user: User = Depends(require_admin),
):
    """Admin edits a single-item auction listing (title, price, location,
    images, etc.). Image updates accept full-array replacement so the FE
    can append new uploads or delete bad ones atomically.
    """
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
    # iter220 Task 4 — image array hygiene
    if "images" in update:
        if not isinstance(update["images"], list):
            raise HTTPException(status_code=400, detail="images must be a list")
        # Deduplicate while preserving order; cap at 30 (Stripe + Meta limit).
        seen = set()
        clean_imgs: list[str] = []
        for url in update["images"]:
            if not isinstance(url, str) or not url.strip():
                continue
            u = url.strip()
            if u in seen:
                continue
            seen.add(u)
            clean_imgs.append(u)
        update["images"] = clean_imgs[:30]

    now = datetime.now(timezone.utc)
    update["updated_at"] = now
    update["last_edited_by_admin"] = current_user.email

    await db.listings.update_one({"id": listing_id}, {"$set": update})

    # iter220 Task 4 — Invalidate the in-process GET-listing cache so the
    # admin sees the updated images immediately (the cache otherwise serves
    # stale data for up to 60s).
    try:
        from routes.listings import _listing_cache
        _listing_cache.pop(listing_id, None)
    except Exception:  # noqa: BLE001 — cache invalidation is best-effort
        pass

    await db.admin_logs.insert_one({
        "id": f"edit-{listing_id}-{int(now.timestamp())}",
        "action": "admin_edit_listing",
        "admin_email": current_user.email,
        "admin_id": getattr(current_user, "id", None),
        "details": {
            "listing_id": listing_id,
            "changed": list(data.model_dump(exclude_none=True).keys()),
            "image_count_after": len(update["images"]) if "images" in update else None,
        },
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

    # iter220 Task 4 — Multi-item auction headers can be edited for title,
    # description, category, location, AND cover-image array. Individual lot
    # imagery stays per-lot (separate endpoint).
    allowed = {"title", "description", "category", "city", "region", "images"}
    update = {k: v for k, v in data.model_dump(exclude_none=True).items() if k in allowed}
    if not update:
        raise HTTPException(status_code=400, detail="No editable fields supplied")
    if "images" in update:
        if not isinstance(update["images"], list):
            raise HTTPException(status_code=400, detail="images must be a list")
        seen = set()
        clean_imgs: list[str] = []
        for url in update["images"]:
            if not isinstance(url, str) or not url.strip():
                continue
            u = url.strip()
            if u in seen:
                continue
            seen.add(u)
            clean_imgs.append(u)
        update["images"] = clean_imgs[:30]

    now = datetime.now(timezone.utc)
    update["updated_at"] = now
    update["last_edited_by_admin"] = current_user.email

    await db.multi_item_listings.update_one({"id": listing_id}, {"$set": update})
    await db.admin_logs.insert_one({
        "id": f"edit-multi-{listing_id}-{int(now.timestamp())}",
        "action": "admin_edit_multi_listing",
        "admin_email": current_user.email,
        "admin_id": getattr(current_user, "id", None),
        "details": {
            "listing_id": listing_id,
            "changed": list(update.keys()),
            "image_count_after": len(update["images"]) if "images" in update else None,
        },
        "timestamp": now.isoformat(),
    })
    return {"success": True, "id": listing_id, "updated_fields": list(update.keys())}


# ═══ iter343 BUG-4 — Admin edits INDIVIDUAL LOTS inside multi-lot auctions ═══

class AdminLotUpdate(BaseModel):
    """Every editable lot field — general lots AND vehicle multi-lot."""
    title: Optional[str] = None
    title_fr: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    quantity: Optional[int] = None
    starting_price: Optional[float] = None
    reserve_price: Optional[float] = None
    bid_increment: Optional[float] = None
    condition: Optional[str] = None
    location: Optional[str] = None
    images: Optional[list[str]] = None
    # Vehicle-lot specific
    vin: Optional[str] = None
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    mileage: Optional[int] = None
    location_city: Optional[str] = None
    location_province: Optional[str] = None


def _diff_lot(old_lot: dict, changes: dict) -> tuple[dict, dict]:
    prev, new = {}, {}
    for k, v in changes.items():
        if old_lot.get(k) != v:
            prev[k] = old_lot.get(k)
            new[k] = v
    return prev, new


async def _apply_lot_edit(
    db, *, collection: str, parent_id: str, lot: dict, lot_match: dict,
    changes: dict, admin: User, action: str, lot_ref,
):
    prev_values, new_values = _diff_lot(lot, changes)
    if not new_values:
        return {"success": True, "id": parent_id, "updated_fields": [],
                "message": "No values changed"}

    # Keep current_bid in sync when starting_price changes on a bid-less lot
    if "starting_price" in new_values and not (lot.get("bid_count") or 0):
        if "current_bid" in lot:
            new_values["current_bid"] = new_values["starting_price"]

    now = datetime.now(timezone.utc)
    set_ops = {f"lots.$.{k}": v for k, v in new_values.items()}
    set_ops["updated_at"] = now
    set_ops["last_edited_by_admin"] = admin.email
    res = await db[collection].update_one(
        {"id": parent_id, **lot_match}, {"$set": set_ops},
    )
    if res.matched_count == 0:
        raise HTTPException(status_code=404, detail="Lot not found in auction")

    # Field-level audit trail (spec: admin_id, event_id, lot_id,
    # fields_changed, previous_values, new_values, timestamp)
    await db.admin_logs.insert_one({
        "id": f"edit-lot-{parent_id}-{lot_ref}-{int(now.timestamp())}",
        "action": action,
        "admin_email": admin.email,
        "admin_id": getattr(admin, "id", None),
        "details": {
            "event_id": parent_id,
            "lot_id": lot_ref,
            "fields_changed": sorted(new_values.keys()),
            "previous_values": prev_values,
            "new_values": new_values,
        },
        "timestamp": now.isoformat(),
    })
    logger.info(f"[ADMIN] {admin.email} edited lot {lot_ref} of {parent_id}: {sorted(new_values.keys())}")
    return {"success": True, "id": parent_id, "lot": lot_ref,
            "updated_fields": sorted(new_values.keys())}


@admin_listing_edit_router.put("/admin/multi-item-listings/{listing_id}/lots/{lot_number}")
async def admin_edit_multi_lot(
    listing_id: str,
    lot_number: int,
    data: AdminLotUpdate,
    current_user: User = Depends(require_admin),
):
    """Admin edits ONE lot inside a general multi-item (lots) auction."""
    db = get_db()
    listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        raise HTTPException(status_code=404, detail="Multi-item listing not found")
    lot = next((l for l in listing.get("lots", []) if l.get("lot_number") == lot_number), None)
    if not lot:
        raise HTTPException(status_code=404, detail=f"Lot #{lot_number} not found")

    changes = data.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")
    if changes.get("quantity") is not None and changes["quantity"] < 1:
        raise HTTPException(status_code=400, detail="quantity must be >= 1")
    for k in ("starting_price", "reserve_price", "bid_increment"):
        if changes.get(k) is not None and changes[k] < 0:
            raise HTTPException(status_code=400, detail=f"{k} cannot be negative")

    return await _apply_lot_edit(
        db, collection="multi_item_listings", parent_id=listing_id, lot=lot,
        lot_match={"lots.lot_number": lot_number}, changes=changes,
        admin=current_user, action="admin_edit_multi_lot", lot_ref=lot_number,
    )


@admin_listing_edit_router.put("/admin/vehicle-multi-lot-auctions/{event_id}/lots/{lot_id}")
async def admin_edit_vehicle_multi_lot(
    event_id: str,
    lot_id: str,
    data: AdminLotUpdate,
    current_user: User = Depends(require_admin),
):
    """Admin edits ONE lot inside a vehicle multi-lot auction event."""
    db = get_db()
    event = await db.vehicle_multi_lot_auctions.find_one({"id": event_id}, {"_id": 0})
    if not event:
        raise HTTPException(status_code=404, detail="Vehicle multi-lot event not found")
    lot = next((l for l in event.get("lots", []) if l.get("id") == lot_id), None)
    if not lot:
        raise HTTPException(status_code=404, detail="Lot not found in event")

    changes = data.model_dump(exclude_none=True)
    if not changes:
        raise HTTPException(status_code=400, detail="No fields to update")
    for k in ("starting_price", "reserve_price", "bid_increment"):
        if changes.get(k) is not None and changes[k] < 0:
            raise HTTPException(status_code=400, detail=f"{k} cannot be negative")

    return await _apply_lot_edit(
        db, collection="vehicle_multi_lot_auctions", parent_id=event_id, lot=lot,
        lot_match={"lots.id": lot_id}, changes=changes,
        admin=current_user, action="admin_edit_vehicle_multi_lot", lot_ref=lot_id,
    )
