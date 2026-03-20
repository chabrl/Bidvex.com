"""
BidVex Partner Pro Features Router
Handles: CSV bulk import, analytics export, branded storefront, 
early auction access, featured listings management.
"""

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Query
from fastapi.responses import StreamingResponse
from deps import User, get_current_user
from typing import Optional
from datetime import datetime, timezone, timedelta
import logging
import uuid
import csv
import io
import json

logger = logging.getLogger(__name__)

partner_pro_router = APIRouter(tags=["Partner Pro"])

_db = None


def set_partner_pro_db(db_instance):
    global _db
    _db = db_instance


def get_db():
    if _db is None:
        raise RuntimeError("Partner Pro DB not initialised")
    return _db


PARTNER_PRO_TIERS = {"partner_pro", "vip"}


def _require_partner_pro(user: User):
    tier = getattr(user, "subscription_tier", "free")
    if tier not in PARTNER_PRO_TIERS:
        raise HTTPException(
            status_code=403,
            detail="Partner Pro or VIP subscription required",
        )


# =====================================================================
# CSV BULK LISTING IMPORT
# =====================================================================

CSV_REQUIRED_FIELDS = {"title", "starting_price", "category"}
CSV_OPTIONAL_FIELDS = {
    "description", "condition", "buy_now_price", "auction_duration_hours",
    "city", "region", "shipping_info", "listing_type",
}
CSV_ALL_FIELDS = CSV_REQUIRED_FIELDS | CSV_OPTIONAL_FIELDS


@partner_pro_router.post("/partner-pro/bulk-import")
async def bulk_import_listings(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    """
    Import listings from a CSV file.
    Required columns: title, starting_price, category
    Optional: description, condition, buy_now_price, auction_duration_hours,
              city, region, shipping_info, listing_type
    """
    _require_partner_pro(current_user)

    if not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only CSV files are accepted")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (max 5 MB)")

    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="Invalid file encoding (UTF-8 required)")

    reader = csv.DictReader(io.StringIO(text))
    headers = set(reader.fieldnames or [])

    missing = CSV_REQUIRED_FIELDS - headers
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"Missing required columns: {', '.join(sorted(missing))}",
        )

    db = get_db()
    created = []
    errors = []
    now = datetime.now(timezone.utc).isoformat()

    for row_num, row in enumerate(reader, start=2):
        title = (row.get("title") or "").strip()
        if not title:
            errors.append({"row": row_num, "error": "Empty title"})
            continue

        try:
            starting_price = float(row["starting_price"])
            if starting_price <= 0:
                raise ValueError
        except (ValueError, KeyError):
            errors.append({"row": row_num, "error": "Invalid starting_price"})
            continue

        category = (row.get("category") or "").strip()
        if not category:
            errors.append({"row": row_num, "error": "Empty category"})
            continue

        duration_hours = 72
        if row.get("auction_duration_hours"):
            try:
                duration_hours = int(row["auction_duration_hours"])
                duration_hours = max(1, min(720, duration_hours))
            except ValueError:
                pass

        buy_now = None
        if row.get("buy_now_price"):
            try:
                buy_now = float(row["buy_now_price"])
                if buy_now <= starting_price:
                    buy_now = None
            except ValueError:
                pass

        listing_id = str(uuid.uuid4())
        listing = {
            "id": listing_id,
            "seller_id": current_user.id,
            "title": title,
            "description": (row.get("description") or "").strip(),
            "starting_price": starting_price,
            "current_price": starting_price,
            "category": category,
            "condition": (row.get("condition") or "used").strip(),
            "city": (row.get("city") or "").strip(),
            "region": (row.get("region") or "").strip(),
            "shipping_info": (row.get("shipping_info") or "").strip(),
            "listing_type": (row.get("listing_type") or "private_sale").strip(),
            "buy_now_price": buy_now,
            "buy_now_enabled": buy_now is not None,
            "auction_end_date": (
                datetime.now(timezone.utc) + timedelta(hours=duration_hours)
            ).isoformat(),
            "images": [],
            "status": "active",
            "views": 0,
            "total_bids": 0,
            "bid_count": 0,
            "watchers": [],
            "created_at": now,
            "updated_at": now,
            "source": "csv_bulk_import",
        }

        await db.listings.insert_one(listing)
        created.append({"id": listing_id, "title": title})

    return {
        "success": True,
        "imported": len(created),
        "errors": len(errors),
        "created_listings": created,
        "error_details": errors[:50],
    }


@partner_pro_router.get("/partner-pro/bulk-import/template")
async def get_csv_template():
    """Download a CSV template for bulk listing import."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(sorted(CSV_ALL_FIELDS))
    writer.writerow([
        "72", "Electronics", "New",
        "Vancouver", "Sample listing description",
        "500.00", "private_sale", "QC",
        "Free shipping", "100.00", "Sample Widget",
    ])
    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bidvex_bulk_import_template.csv"},
    )


# =====================================================================
# ANALYTICS EXPORT
# =====================================================================

@partner_pro_router.get("/partner-pro/analytics/export")
async def export_analytics(
    format: str = Query("csv", regex="^(csv|json)$"),
    period_days: int = Query(30, ge=1, le=365),
    current_user: User = Depends(get_current_user),
):
    """Export seller analytics data as CSV or JSON."""
    _require_partner_pro(current_user)
    db = get_db()

    cutoff = (datetime.now(timezone.utc) - timedelta(days=period_days)).isoformat()

    listings = await db.listings.find(
        {"seller_id": current_user.id, "created_at": {"$gte": cutoff}},
        {"_id": 0, "id": 1, "title": 1, "current_price": 1, "starting_price": 1,
         "views": 1, "total_bids": 1, "bid_count": 1, "status": 1,
         "category": 1, "created_at": 1, "auction_end_date": 1},
    ).to_list(5000)

    bids = await db.bids.find(
        {"bidder_id": current_user.id, "created_at": {"$gte": cutoff}},
        {"_id": 0, "id": 1, "listing_id": 1, "amount": 1, "created_at": 1},
    ).to_list(5000)

    if format == "json":
        payload = {
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "period_days": period_days,
            "listings": listings,
            "bids": bids,
            "summary": {
                "total_listings": len(listings),
                "total_bids": len(bids),
                "active_listings": sum(1 for l in listings if l.get("status") == "active"),
                "total_views": sum(l.get("views", 0) for l in listings),
            },
        }
        return StreamingResponse(
            io.BytesIO(json.dumps(payload, indent=2, default=str).encode("utf-8")),
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=bidvex_analytics.json"},
        )

    # CSV export
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["type", "id", "title", "price", "views", "bids", "status", "category", "date"])
    for listing in listings:
        writer.writerow([
            "listing", listing.get("id"), listing.get("title"), listing.get("current_price"),
            listing.get("views", 0), listing.get("total_bids", 0) or listing.get("bid_count", 0),
            listing.get("status"), listing.get("category"), listing.get("created_at"),
        ])
    for bid in bids:
        writer.writerow([
            "bid", bid.get("id"), "", bid.get("amount"),
            "", "", "", "", bid.get("created_at"),
        ])
    buf.seek(0)
    return StreamingResponse(
        io.BytesIO(buf.getvalue().encode("utf-8")),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=bidvex_analytics.csv"},
    )


# =====================================================================
# BRANDED STOREFRONT
# =====================================================================

@partner_pro_router.get("/storefronts/{user_id}")
async def get_storefront(user_id: str):
    """Get a seller's branded storefront (public)."""
    db = get_db()
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password": 0})
    if not user:
        raise HTTPException(status_code=404, detail="Seller not found")

    tier = user.get("subscription_tier", "free")
    storefront = await db.storefronts.find_one({"user_id": user_id}, {"_id": 0})

    listings = await db.listings.find(
        {"seller_id": user_id, "status": "active"},
        {"_id": 0},
    ).sort("created_at", -1).limit(50).to_list(50)

    return {
        "seller": {
            "id": user.get("id"),
            "name": user.get("name"),
            "picture": user.get("picture"),
            "subscription_tier": tier,
            "joined": user.get("created_at"),
        },
        "storefront": storefront or {
            "banner_url": None,
            "tagline": "",
            "about": "",
            "accent_color": "#06b6d4",
        },
        "listings": listings,
        "has_storefront": tier in PARTNER_PRO_TIERS,
    }


@partner_pro_router.put("/partner-pro/storefront")
async def update_storefront(
    payload: dict,
    current_user: User = Depends(get_current_user),
):
    """Update the current user's branded storefront."""
    _require_partner_pro(current_user)
    db = get_db()

    allowed = {"tagline", "about", "accent_color", "banner_url"}
    updates = {k: v for k, v in payload.items() if k in allowed}
    updates["user_id"] = current_user.id
    updates["updated_at"] = datetime.now(timezone.utc).isoformat()

    await db.storefronts.update_one(
        {"user_id": current_user.id},
        {"$set": updates},
        upsert=True,
    )
    return {"success": True, "storefront": updates}


# =====================================================================
# FEATURED LISTINGS MANAGEMENT
# =====================================================================

@partner_pro_router.get("/partner-pro/featured-listings")
async def get_featured_listings_status(
    current_user: User = Depends(get_current_user),
):
    """Get the user's featured listing usage for the current month."""
    _require_partner_pro(current_user)
    db = get_db()

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()

    used = await db.featured_listings.count_documents({
        "user_id": current_user.id,
        "featured_at": {"$gte": month_start},
    })

    tier = getattr(current_user, "subscription_tier", "free")
    limit = 10 if tier == "partner_pro" else (-1 if tier == "vip" else 0)

    return {
        "used": used,
        "limit": limit,
        "remaining": max(0, limit - used) if limit >= 0 else -1,
        "month": now.strftime("%Y-%m"),
    }


@partner_pro_router.post("/partner-pro/featured-listings/{listing_id}")
async def feature_listing(
    listing_id: str,
    current_user: User = Depends(get_current_user),
):
    """Mark a listing as featured for the current month."""
    _require_partner_pro(current_user)
    db = get_db()

    listing = await db.listings.find_one({"id": listing_id, "seller_id": current_user.id})
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    tier = getattr(current_user, "subscription_tier", "free")
    limit = 10 if tier == "partner_pro" else -1

    if limit > 0:
        now = datetime.now(timezone.utc)
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
        used = await db.featured_listings.count_documents({
            "user_id": current_user.id,
            "featured_at": {"$gte": month_start},
        })
        if used >= limit:
            raise HTTPException(status_code=400, detail=f"Monthly featured listing limit reached ({limit})")

    await db.featured_listings.insert_one({
        "id": str(uuid.uuid4()),
        "user_id": current_user.id,
        "listing_id": listing_id,
        "featured_at": datetime.now(timezone.utc).isoformat(),
    })

    await db.listings.update_one(
        {"id": listing_id},
        {"$set": {"is_featured": True, "featured_at": datetime.now(timezone.utc).isoformat()}},
    )

    return {"success": True, "message": "Listing featured successfully"}


# =====================================================================
# EARLY AUCTION ACCESS
# =====================================================================

@partner_pro_router.get("/partner-pro/early-access")
async def get_early_access_listings(
    limit: int = Query(20, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """
    Get listings that are in the early-access window (visible only to Partner Pro / VIP).
    These are auctions that haven't started publicly yet but are within 2h of going live.
    """
    _require_partner_pro(current_user)
    db = get_db()

    now = datetime.now(timezone.utc)
    early_window = now + timedelta(hours=2)

    early_listings = await db.listings.find(
        {
            "status": "scheduled",
            "auction_start_date": {
                "$gte": now.isoformat(),
                "$lte": early_window.isoformat(),
            },
        },
        {"_id": 0},
    ).sort("auction_start_date", 1).limit(limit).to_list(limit)

    return {
        "success": True,
        "early_access_listings": early_listings,
        "count": len(early_listings),
        "window_hours": 2,
    }
