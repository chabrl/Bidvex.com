"""
BidVex Analytics Router
Handles seller analytics and promotion tracking including:
- Impressions tracking (homepage, marketplace views)
- Click tracking (detail page visits)
- Bid velocity metrics
- Real-time analytics updates
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import logging

logger = logging.getLogger(__name__)

analytics_router = APIRouter(prefix="/analytics", tags=["Analytics"])

# Database will be injected from main app
_db = None

def set_db(db_instance):
    """Set database instance from main app"""
    global _db
    _db = db_instance

def get_db():
    """Get database instance"""
    if _db is None:
        raise HTTPException(status_code=500, detail="Database not initialized")
    return _db


# ========== TRACK IMPRESSION ==========
@analytics_router.post("/impression")
async def track_impression(data: Dict[str, Any]):
    """
    Track an impression (view) of a listing
    Called when a listing appears on homepage, marketplace, or search results
    """
    db = get_db()
    
    listing_id = data.get("listing_id")
    source = data.get("source", "unknown")  # homepage, marketplace, search, hot_items
    user_id = data.get("user_id")  # Optional, can be anonymous
    
    if not listing_id:
        raise HTTPException(status_code=400, detail="listing_id is required")
    
    # Create impression record
    impression = {
        "id": str(uuid4()),
        "listing_id": listing_id,
        "source": source,
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")
    }
    
    await db.analytics_impressions.insert_one(impression)
    
    # Update listing's view count
    await db.listings.update_one(
        {"id": listing_id},
        {"$inc": {"views": 1, "impressions": 1}}
    )
    
    # Also check multi_item_listings
    await db.multi_item_listings.update_one(
        {"id": listing_id},
        {"$inc": {"views": 1, "impressions": 1}}
    )
    
    return {"status": "tracked"}


# ========== TRACK CLICK ==========
@analytics_router.post("/click")
async def track_click(data: Dict[str, Any]):
    """
    Track a click (detail page visit) for a listing
    Called when a user visits the listing detail page
    """
    db = get_db()
    
    listing_id = data.get("listing_id")
    source = data.get("source", "direct")  # homepage, marketplace, search, notification
    user_id = data.get("user_id")
    referrer = data.get("referrer")
    
    if not listing_id:
        raise HTTPException(status_code=400, detail="listing_id is required")
    
    # Create click record
    click = {
        "id": str(uuid4()),
        "listing_id": listing_id,
        "source": source,
        "user_id": user_id,
        "referrer": referrer,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d")
    }
    
    await db.analytics_clicks.insert_one(click)
    
    # Update listing's click count
    await db.listings.update_one(
        {"id": listing_id},
        {"$inc": {"clicks": 1}}
    )
    
    await db.multi_item_listings.update_one(
        {"id": listing_id},
        {"$inc": {"clicks": 1}}
    )
    
    return {"status": "tracked"}


# ========== GET SELLER ANALYTICS ==========
@analytics_router.get("/seller/{seller_id}")
async def get_seller_analytics(
    seller_id: str,
    period: str = Query("7d", description="Time period: 7d, 30d, 90d, all")
):
    """
    Get comprehensive analytics for a seller's listings
    Returns impressions, clicks, bids, and performance metrics
    """
    db = get_db()
    
    # Calculate date range
    now = datetime.now(timezone.utc)
    if period == "7d":
        start_date = now - timedelta(days=7)
    elif period == "30d":
        start_date = now - timedelta(days=30)
    elif period == "90d":
        start_date = now - timedelta(days=90)
    else:
        start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    
    start_date_str = start_date.isoformat()
    
    # Get seller's listings
    listings = await db.listings.find(
        {"seller_id": seller_id},
        {"_id": 0, "id": 1, "title": 1, "views": 1, "clicks": 1, "impressions": 1, "status": 1}
    ).to_list(1000)
    
    multi_listings = await db.multi_item_listings.find(
        {"seller_id": seller_id},
        {"_id": 0, "id": 1, "title": 1, "views": 1, "clicks": 1, "impressions": 1, "status": 1}
    ).to_list(1000)
    
    all_listings = listings + multi_listings
    listing_ids = [l["id"] for l in all_listings]
    
    # Get impressions by day
    impressions_pipeline = [
        {"$match": {
            "listing_id": {"$in": listing_ids},
            "timestamp": {"$gte": start_date_str}
        }},
        {"$group": {
            "_id": "$date",
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    impressions_by_day = await db.analytics_impressions.aggregate(impressions_pipeline).to_list(100)
    
    # Get clicks by day
    clicks_pipeline = [
        {"$match": {
            "listing_id": {"$in": listing_ids},
            "timestamp": {"$gte": start_date_str}
        }},
        {"$group": {
            "_id": "$date",
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    clicks_by_day = await db.analytics_clicks.aggregate(clicks_pipeline).to_list(100)
    
    # Get bids by day
    bids_pipeline = [
        {"$match": {
            "listing_id": {"$in": listing_ids},
            "created_at": {"$gte": start_date_str}
        }},
        {"$addFields": {
            "date": {"$substr": ["$created_at", 0, 10]}
        }},
        {"$group": {
            "_id": "$date",
            "count": {"$sum": 1},
            "total_amount": {"$sum": "$amount"}
        }},
        {"$sort": {"_id": 1}}
    ]
    bids_by_day = await db.bids.aggregate(bids_pipeline).to_list(100)
    
    # Also check lot_bids
    lot_bids_pipeline = [
        {"$match": {
            "listing_id": {"$in": listing_ids},
            "created_at": {"$gte": start_date_str}
        }},
        {"$addFields": {
            "date": {"$substr": ["$created_at", 0, 10]}
        }},
        {"$group": {
            "_id": "$date",
            "count": {"$sum": 1},
            "total_amount": {"$sum": "$amount"}
        }},
        {"$sort": {"_id": 1}}
    ]
    lot_bids_by_day = await db.lot_bids.aggregate(lot_bids_pipeline).to_list(100)
    
    # Combine bids
    combined_bids = {}
    for b in bids_by_day + lot_bids_by_day:
        date = b["_id"]
        if date not in combined_bids:
            combined_bids[date] = {"count": 0, "total_amount": 0}
        combined_bids[date]["count"] += b["count"]
        combined_bids[date]["total_amount"] += b.get("total_amount", 0)
    
    bids_chart_data = [
        {"date": k, "count": v["count"], "total_amount": v["total_amount"]}
        for k, v in sorted(combined_bids.items())
    ]
    
    # Calculate totals
    total_impressions = sum(i.get("impressions", 0) or i.get("views", 0) for i in all_listings)
    total_clicks = sum(i.get("clicks", 0) for i in all_listings)
    total_bids = sum(b["count"] for b in bids_chart_data)
    
    # Get impression sources
    sources_pipeline = [
        {"$match": {"listing_id": {"$in": listing_ids}}},
        {"$group": {
            "_id": "$source",
            "count": {"$sum": 1}
        }}
    ]
    impression_sources = await db.analytics_impressions.aggregate(sources_pipeline).to_list(20)
    
    # Calculate click-through rate
    ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    
    # Get top performing listings
    top_listings = sorted(all_listings, key=lambda x: x.get("clicks", 0) or 0, reverse=True)[:5]
    
    return {
        "summary": {
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_bids": total_bids,
            "click_through_rate": round(ctr, 2),
            "total_listings": len(all_listings),
            "active_listings": len([l for l in all_listings if l.get("status") == "active"])
        },
        "charts": {
            "impressions": [{"date": i["_id"], "count": i["count"]} for i in impressions_by_day],
            "clicks": [{"date": c["_id"], "count": c["count"]} for c in clicks_by_day],
            "bids": bids_chart_data
        },
        "sources": {s["_id"]: s["count"] for s in impression_sources},
        "top_listings": top_listings,
        "period": period
    }


# ========== GET LISTING ANALYTICS ==========
@analytics_router.get("/listing/{listing_id}")
async def get_listing_analytics(
    listing_id: str,
    period: str = Query("7d", description="Time period: 7d, 30d, all")
):
    """
    Get detailed analytics for a specific listing
    """
    db = get_db()
    
    # Calculate date range
    now = datetime.now(timezone.utc)
    if period == "7d":
        start_date = now - timedelta(days=7)
    elif period == "30d":
        start_date = now - timedelta(days=30)
    else:
        start_date = datetime(2020, 1, 1, tzinfo=timezone.utc)
    
    start_date_str = start_date.isoformat()
    
    # Get listing
    listing = await db.listings.find_one({"id": listing_id}, {"_id": 0})
    if not listing:
        listing = await db.multi_item_listings.find_one({"id": listing_id}, {"_id": 0})
    
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")
    
    # Get impressions timeline
    impressions_pipeline = [
        {"$match": {
            "listing_id": listing_id,
            "timestamp": {"$gte": start_date_str}
        }},
        {"$group": {
            "_id": {"date": "$date", "source": "$source"},
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id.date": 1}}
    ]
    impressions_data = await db.analytics_impressions.aggregate(impressions_pipeline).to_list(500)
    
    # Get clicks timeline
    clicks_pipeline = [
        {"$match": {
            "listing_id": listing_id,
            "timestamp": {"$gte": start_date_str}
        }},
        {"$group": {
            "_id": "$date",
            "count": {"$sum": 1}
        }},
        {"$sort": {"_id": 1}}
    ]
    clicks_data = await db.analytics_clicks.aggregate(clicks_pipeline).to_list(100)
    
    # Get bid velocity (bids over time)
    bids = await db.bids.find(
        {"listing_id": listing_id, "created_at": {"$gte": start_date_str}},
        {"_id": 0, "amount": 1, "created_at": 1}
    ).to_list(1000)
    
    lot_bids = await db.lot_bids.find(
        {"listing_id": listing_id, "created_at": {"$gte": start_date_str}},
        {"_id": 0, "amount": 1, "created_at": 1}
    ).to_list(1000)
    
    all_bids = bids + lot_bids
    
    # Group bids by hour for bid velocity
    bid_velocity = {}
    for bid in all_bids:
        hour = bid["created_at"][:13]  # YYYY-MM-DDTHH
        if hour not in bid_velocity:
            bid_velocity[hour] = {"count": 0, "total": 0}
        bid_velocity[hour]["count"] += 1
        bid_velocity[hour]["total"] += bid.get("amount", 0)
    
    return {
        "listing": {
            "id": listing_id,
            "title": listing.get("title"),
            "total_views": listing.get("views", 0),
            "total_clicks": listing.get("clicks", 0),
            "total_impressions": listing.get("impressions", 0),
            "total_bids": len(all_bids),
            "status": listing.get("status")
        },
        "impressions_by_source": impressions_data,
        "clicks_timeline": [{"date": c["_id"], "count": c["count"]} for c in clicks_data],
        "bid_velocity": [
            {"hour": k, "count": v["count"], "total": v["total"]}
            for k, v in sorted(bid_velocity.items())
        ],
        "period": period
    }


# ========== REAL-TIME VIEW UPDATE ==========
@analytics_router.post("/realtime-view")
async def track_realtime_view(data: Dict[str, Any]):
    """
    Track a real-time view for live dashboard updates
    Used for the seller's live analytics dashboard
    """
    db = get_db()
    
    listing_id = data.get("listing_id")
    seller_id = data.get("seller_id")
    
    if not listing_id:
        raise HTTPException(status_code=400, detail="listing_id is required")
    
    # Increment view counter
    result = await db.listings.find_one_and_update(
        {"id": listing_id},
        {"$inc": {"views": 1}},
        return_document=True
    )
    
    if not result:
        result = await db.multi_item_listings.find_one_and_update(
            {"id": listing_id},
            {"$inc": {"views": 1}},
            return_document=True
        )
    
    if result:
        return {
            "status": "tracked",
            "new_view_count": result.get("views", 0)
        }
    
    return {"status": "listing_not_found"}
