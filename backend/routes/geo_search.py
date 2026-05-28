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
    """Create the 2dsphere index on the GeoJSON `geo` field (iter237).

    iter237 — DEVIATION FROM SPEC LETTER: the existing `location` field is a
    string (human-readable address) consumed by 5+ UI components. To avoid
    breaking those displays we store the GeoJSON Point under a separate
    top-level `geo` field. The 2dsphere index and `$geoWithin` queries
    target `geo`. Pydantic models keep `location: str` intact.

    Idempotent — MongoDB silently no-ops if an identical index already
    exists. The previous iter236 `location.coordinates` 2dsphere index
    is left in place harmlessly (no documents populate that path).
    """
    if _db is None:
        return {"status": "skipped", "reason": "db handle not initialised"}
    try:
        await _db.listings.create_index(
            [("geo", "2dsphere")],
            name="geo_2dsphere",
            sparse=True,
            background=True,
        )
        await _db.multi_item_listings.create_index(
            [("geo", "2dsphere")],
            name="geo_2dsphere",
            sparse=True,
            background=True,
        )
        logger.info("[iter237-geo] 2dsphere indexes ensured on listings.geo + multi_item_listings.geo")
        return {"status": "ok"}
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[iter237-geo] index ensure failed: {e}")
        return {"status": "error", "error": str(e)}


def _project(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Return only the safe public fields per the marketplace card spec.

    iter237 — Also surfaces `geo` (GeoJSON Point) so the frontend
    MapSearchPanel can plot markers without re-fetching.
    """
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
        "city": doc.get("city"),
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
        # GeoJSON Point ([lng, lat]) — frontend Leaflet must reverse to [lat, lng].
        "geo": doc.get("geo"),
        # Keep the legacy `location` field as a string for display continuity.
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
    """iter237 — Geo-aware listings search using $geoWithin + $centerSphere.

    Behaviour:
      • lat + lng + radius_km → $geoWithin/$centerSphere on `geo`. Other
        filters (category, province) are MERGED into the same query dict
        instead of replacing them (RC-4 fix).
      • Only city → case-insensitive regex on listing.city.
      • Otherwise → standard active-listing list (capped by `limit`).
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="geo-search db handle not initialised")

    # ------------------------------------------------------------------
    # Base filter — start empty and merge every active constraint into it.
    # ------------------------------------------------------------------
    query: Dict[str, Any] = {
        "status": {"$in": ["active", "upcoming"]},
        "is_demo": {"$ne": True},
        "is_demo_sandbox": {"$ne": True},
    }
    if category:
        query["category"] = category
    if province:
        query["$or"] = [
            {"region": {"$regex": f"^{re.escape(province)}$", "$options": "i"}},
            {"province": {"$regex": f"^{re.escape(province)}$", "$options": "i"}},
        ]

    geo_active = lat is not None and lng is not None
    effective_radius_km = radius_km if radius_km is not None else 50.0

    if geo_active:
        # Earth radius ≈ 6371 km → radius in radians for $centerSphere.
        radius_radians = float(effective_radius_km) / 6371.0
        query["geo"] = {
            "$geoWithin": {
                "$centerSphere": [[float(lng), float(lat)], radius_radians],
            },
        }
        # Hard guard against docs that somehow ended up with NULL coordinates.
        query["geo.coordinates"] = {"$exists": True, "$ne": None}
        # When geo is active we IGNORE the free-text city — the radius search
        # is more precise and avoids the spec's "geo and text both empty" trap.
    elif city:
        query["city"] = {"$regex": re.escape(city), "$options": "i"}

    projection = {
        "_id": 0,
        "id": 1, "title": 1, "description": 1, "category": 1, "images": 1,
        "current_price": 1, "current_bid": 1, "starting_price": 1,
        "buy_now_enabled": 1, "buy_now_price": 1, "hammer_price": 1, "currency": 1,
        "status": 1, "city": 1, "region": 1, "province": 1,
        "seller_id": 1, "seller_is_business": 1, "seller_account_type": 1,
        "auction_end_date": 1, "quantity": 1,
        "multiply_hammer_by_quantity": 1, "price_multiplied_by_quantity": 1,
        "listing_type": 1, "location": 1, "geo": 1,
    }

    try:
        cursor = _db.listings.find(query, projection).limit(limit)
        docs = await cursor.to_list(length=limit)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[iter237-geo] $geoWithin query failed (returning empty): {e}")
        docs = []

    # When geo is active, compute distance_km client-side from the GeoJSON.
    if geo_active:
        from math import radians, sin, cos, atan2, sqrt
        for d in docs:
            try:
                lng2, lat2 = d["geo"]["coordinates"]
                phi1, phi2 = radians(float(lat)), radians(float(lat2))
                dphi = radians(float(lat2) - float(lat))
                dlmb = radians(float(lng2) - float(lng))
                a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlmb / 2) ** 2
                d["distance_km"] = round(6371.0 * 2 * atan2(sqrt(a), sqrt(1 - a)), 2)
            except Exception:  # noqa: BLE001
                d["distance_km"] = None
        docs.sort(key=lambda x: (x.get("distance_km") is None, x.get("distance_km") or 0))

    items = [_project(d) for d in docs]
    return {
        "items": items,
        "total": len(items),
        "filter": {
            "lat": lat,
            "lng": lng,
            "radius_km": effective_radius_km if geo_active else None,
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
