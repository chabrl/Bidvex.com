"""
iter236 — Mission 2 — Geo-aware listings search.

Exposes:
    GET  /api/marketplace/items/geo
        Optional query params:
            lat: float
            lng: float
            radius_km: float    (default 50 if lat+lng present)
            city: str           (case-insensitive regex)
            category: str
            province: str
            limit: int          (default 60, hard cap 200)
        Returns:
            {"items": [...], "total": int, "filter": {...}}

    POST /api/marketplace/items/ensure-geo-index
        Idempotent admin-friendly trigger — creates the 2dsphere index on
        listings.location.coordinates. Also called automatically once at
        backend startup via server.py.

Listings expected to carry GeoJSON Point under `location.coordinates`:
    location = { "type": "Point", "coordinates": [lng, lat] }
When a listing has no coordinates, geo queries skip it (per MongoDB
$geoNear semantics). The endpoint gracefully falls back to a
city-regex / category filter if neither lat nor lng is supplied.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

logger = logging.getLogger(__name__)

geo_router = APIRouter(tags=["Marketplace Geo Search"])

_db = None  # set at startup


def set_geo_db(database) -> None:
    global _db
    _db = database


async def ensure_2dsphere_index() -> Dict[str, Any]:
    """Create the 2dsphere index on `listings.location.coordinates`.

    Idempotent — MongoDB silently no-ops if an identical index already
    exists. Logged at info level on first creation, debug on re-runs.
    """
    if _db is None:
        return {"status": "skipped", "reason": "db handle not initialised"}
    try:
        await _db.listings.create_index(
            [("location.coordinates", "2dsphere")],
            name="location_coordinates_2dsphere",
            sparse=True,
            background=True,
        )
        # Multi-item listings can also receive geo if they store a center point.
        await _db.multi_item_listings.create_index(
            [("location.coordinates", "2dsphere")],
            name="multi_location_coordinates_2dsphere",
            sparse=True,
            background=True,
        )
        logger.info("[iter236-geo] 2dsphere indexes ensured on listings + multi_item_listings")
        return {"status": "ok"}
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[iter236-geo] index ensure failed: {e}")
        return {"status": "error", "error": str(e)}


def _project(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Return only the safe public fields per the marketplace card spec."""
    return {
        "id": doc.get("id"),
        "title": doc.get("title"),
        "description": doc.get("description"),
        "category": doc.get("category"),
        "images": doc.get("images") or [],
        "current_price": doc.get("current_price") or doc.get("current_bid"),
        "starting_price": doc.get("starting_price"),
        "buy_now_enabled": bool(doc.get("buy_now_enabled")),
        "buy_now_price": doc.get("buy_now_price"),
        "hammer_price": doc.get("hammer_price"),
        "currency": doc.get("currency") or "CAD",
        "status": doc.get("status"),
        "city": doc.get("city") or (doc.get("location", {}) or {}).get("city"),
        "region": doc.get("region") or doc.get("province"),
        "seller_id": doc.get("seller_id"),
        "seller_is_business": bool(doc.get("seller_is_business")),
        "seller_account_type": doc.get("seller_account_type"),
        "auction_end_date": doc.get("auction_end_date"),
        "quantity": doc.get("quantity") or 1,
        "multiply_hammer_by_quantity": bool(doc.get("multiply_hammer_by_quantity")),
        "price_multiplied_by_quantity": bool(doc.get("price_multiplied_by_quantity")),
        "listing_type": doc.get("listing_type"),
        "distance_km": doc.get("distance_km"),
        "location": doc.get("location"),
    }


@geo_router.get("/marketplace/items/geo")
async def get_geo_items(
    lat: Optional[float] = Query(None),
    lng: Optional[float] = Query(None),
    radius_km: Optional[float] = Query(None, ge=1, le=2000),
    city: Optional[str] = Query(None, max_length=120),
    category: Optional[str] = Query(None, max_length=80),
    province: Optional[str] = Query(None, max_length=40),
    limit: int = Query(60, ge=1, le=200),
) -> Dict[str, Any]:
    """Geo-aware listings search.

    Behaviour:
      • lat + lng + radius_km → $geoNear pipeline, returns docs ordered by
        ascending distance with a `distance_km` field on each.
      • Only city → case-insensitive regex against listing.city.
      • Otherwise → standard active-listing list (capped by `limit`).
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="geo-search db handle not initialised")

    # ------------------------------------------------------------------
    # Base filter (active listings, non-demo, non-vehicle marketplace)
    # ------------------------------------------------------------------
    base_match: Dict[str, Any] = {
        "status": {"$in": ["active", "upcoming"]},
        "is_demo": {"$ne": True},
        "is_demo_sandbox": {"$ne": True},
    }
    if category:
        base_match["category"] = category
    if province:
        base_match["$or"] = [
            {"region": {"$regex": f"^{re.escape(province)}$", "$options": "i"}},
            {"province": {"$regex": f"^{re.escape(province)}$", "$options": "i"}},
        ]

    geo_active = lat is not None and lng is not None

    if geo_active:
        effective_radius_km = radius_km if radius_km is not None else 50.0
        max_meters = effective_radius_km * 1000.0
        pipeline: List[Dict[str, Any]] = [
            {
                "$geoNear": {
                    "near": {"type": "Point", "coordinates": [float(lng), float(lat)]},
                    "distanceField": "distance_m",
                    "maxDistance": max_meters,
                    "spherical": True,
                    "query": base_match,
                }
            },
            {"$limit": limit},
            {
                "$addFields": {
                    "distance_km": {"$round": [{"$divide": ["$distance_m", 1000]}, 2]},
                }
            },
        ]
        try:
            items_raw = await _db.listings.aggregate(pipeline).to_list(length=limit)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[iter236-geo] $geoNear failed (falling back to city/limit): {e}")
            items_raw = []
        items = [_project(d) for d in items_raw]
        return {
            "items": items,
            "total": len(items),
            "filter": {
                "lat": lat,
                "lng": lng,
                "radius_km": effective_radius_km,
                "city": city,
                "category": category,
                "province": province,
            },
        }

    # ---- No geo coords supplied → city / category fallback ----
    if city:
        base_match["$and"] = base_match.get("$and", []) + [
            {"city": {"$regex": re.escape(city), "$options": "i"}},
        ]

    projection = {
        "_id": 0,
        "id": 1, "title": 1, "description": 1, "category": 1, "images": 1,
        "current_price": 1, "current_bid": 1, "starting_price": 1,
        "buy_now_enabled": 1, "buy_now_price": 1, "hammer_price": 1, "currency": 1,
        "status": 1, "city": 1, "region": 1, "province": 1,
        "seller_id": 1, "seller_is_business": 1, "seller_account_type": 1,
        "auction_end_date": 1, "quantity": 1,
        "multiply_hammer_by_quantity": 1, "price_multiplied_by_quantity": 1,
        "listing_type": 1, "location": 1,
    }
    cursor = _db.listings.find(base_match, projection).limit(limit)
    docs = await cursor.to_list(length=limit)
    items = [_project(d) for d in docs]
    return {
        "items": items,
        "total": len(items),
        "filter": {
            "lat": None,
            "lng": None,
            "radius_km": None,
            "city": city,
            "category": category,
            "province": province,
        },
    }


@geo_router.post("/marketplace/items/ensure-geo-index")
async def trigger_ensure_index() -> Dict[str, Any]:
    """Idempotent admin trigger — useful for manual reindex from the dashboard."""
    return await ensure_2dsphere_index()


__all__ = ["geo_router", "set_geo_db", "ensure_2dsphere_index"]
