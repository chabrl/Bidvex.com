"""
iter236/237 — Geo-aware listings search.  iter343 — MULTI-COLLECTION.

BUG-1 iter343 ROOT CAUSE: this endpoint queried ONLY `db.listings`, so
multi-lot auctions (multi_item_listings), vehicles, vehicle multi-lot
events and storage auctions never appeared on the map. It now unions all
five active collections, each normalized to the marketplace card shape
with a `_section` tag + ready-made `detail_path` for the frontend.

Listings carry a GeoJSON Point under the top-level `geo` field:
    geo = { "type": "Point", "coordinates": [lng, lat], ... }
Documents without coordinates are skipped by $geoWithin (backfill via
scripts/backfill_geo.py).
"""
from __future__ import annotations

import logging
import re
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

geo_router = APIRouter(tags=["Marketplace Geo Search"])

_db = None  # set at startup


def set_geo_db(database) -> None:
    global _db
    _db = database


# iter343 — every publicly searchable collection.
#   (collection, section, detail_path_prefix, active statuses)
GEO_SEARCH_SOURCES = [
    ("listings",                   "marketplace",       "/listing/",           ["active", "upcoming"]),
    ("multi_item_listings",        "lots",              "/lots/",              ["active", "upcoming"]),
    ("vehicle_listings",           "vehicle",           "/vehicle-auctions/",  ["active", "upcoming"]),
    ("vehicle_multi_lot_auctions", "vehicle_multi_lot", "/vehicle-multi-lot/", ["live", "upcoming", "active"]),
    ("storage_auctions",           "storage",           "/storage-auctions/",  ["active", "upcoming"]),
]


async def ensure_2dsphere_index() -> Dict[str, Any]:
    """Create the 2dsphere index on `geo` for ALL searchable collections.

    iter343 — previously only listings + multi_item_listings were indexed;
    vehicle, vehicle multi-lot and storage collections were missing.
    Idempotent — MongoDB no-ops when an identical index exists.
    """
    if _db is None:
        return {"status": "skipped", "reason": "db handle not initialised"}
    done = []
    for coll_name, *_ in GEO_SEARCH_SOURCES:
        try:
            await _db[coll_name].create_index(
                [("geo", "2dsphere")],
                name="geo_2dsphere",
                sparse=True,
                background=True,
            )
            done.append(coll_name)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[geo] index ensure failed on {coll_name}: {e}")
    logger.info(f"[geo] 2dsphere indexes ensured on: {done}")
    return {"status": "ok", "collections": done}


def _project(doc: Dict[str, Any], section: str, path_prefix: str) -> Dict[str, Any]:
    """Normalize any collection's doc to the marketplace map-card shape."""
    doc_id = doc.get("id")

    # Title normalization per collection
    title = doc.get("title")
    if not title and section == "vehicle":
        title = " ".join(str(x) for x in (doc.get("year"), doc.get("make"), doc.get("model")) if x).strip() or "Vehicle"
    if not title and section == "storage":
        size = doc.get("unit_size") or ""
        title = (doc.get("description_en") or f"Storage unit {size}").strip()

    # Price normalization
    price = doc.get("current_price") or doc.get("current_bid")
    if price in (None, 0) and section in ("lots", "vehicle_multi_lot"):
        lots = doc.get("lots") or []
        try:
            price = sum(float(l.get("current_bid") or l.get("starting_price") or 0) for l in lots) or None
        except Exception:  # noqa: BLE001
            price = None

    images = doc.get("images") or doc.get("photos") or []
    if not images and section in ("lots", "vehicle_multi_lot"):
        for l in (doc.get("lots") or []):
            lot_imgs = l.get("images") or l.get("media") or []
            if lot_imgs:
                images = lot_imgs if isinstance(lot_imgs, list) else []
                break

    end_date = doc.get("auction_end_date") or doc.get("end_time") or doc.get("end_date")

    return {
        "id": doc_id,
        "title": title,
        "description": doc.get("description") or doc.get("description_en"),
        "category": doc.get("category"),
        "images": images if isinstance(images, list) else [],
        "current_price": price,
        "starting_price": doc.get("starting_price"),
        "buy_now_enabled": bool(doc.get("buy_now_enabled")),
        "buy_now_price": doc.get("buy_now_price"),
        "hammer_price": doc.get("hammer_price"),
        "currency": doc.get("currency") or "CAD",
        "status": doc.get("status"),
        "city": doc.get("city") or doc.get("facility_city"),
        "region": doc.get("region") or doc.get("province") or doc.get("facility_province"),
        "seller_id": doc.get("seller_id"),
        "seller_is_business": bool(doc.get("seller_is_business")),
        "seller_account_type": doc.get("seller_account_type"),
        "auction_end_date": end_date if isinstance(end_date, str) else (end_date.isoformat() if end_date else None),
        "quantity": doc.get("quantity") or 1,
        "multiply_hammer_by_quantity": bool(doc.get("multiply_hammer_by_quantity")),
        "price_multiplied_by_quantity": bool(doc.get("price_multiplied_by_quantity")),
        "listing_type": doc.get("listing_type"),
        "total_lots": len(doc.get("lots") or []) if section in ("lots", "vehicle_multi_lot") else None,
        "distance_km": doc.get("distance_km"),
        # GeoJSON Point ([lng, lat]) — frontend Leaflet must reverse to [lat, lng].
        "geo": doc.get("geo"),
        "location": doc.get("location"),
        # iter343 — section tag + ready-made frontend route
        "_section": section,
        "detail_path": f"{path_prefix}{doc_id}",
    }


_PROJECTION = {
    "_id": 0,
    "id": 1, "title": 1, "description": 1, "description_en": 1, "category": 1,
    "images": 1, "photos": 1, "media": 1,
    "current_price": 1, "current_bid": 1, "starting_price": 1,
    "buy_now_enabled": 1, "buy_now_price": 1, "hammer_price": 1, "currency": 1,
    "status": 1, "city": 1, "region": 1, "province": 1,
    "facility_city": 1, "facility_province": 1,
    "year": 1, "make": 1, "model": 1, "unit_size": 1,
    "seller_id": 1, "seller_is_business": 1, "seller_account_type": 1,
    "auction_end_date": 1, "end_time": 1, "end_date": 1, "quantity": 1,
    "multiply_hammer_by_quantity": 1, "price_multiplied_by_quantity": 1,
    "listing_type": 1, "location": 1, "geo": 1,
    "lots.current_bid": 1, "lots.starting_price": 1, "lots.images": 1, "lots.media": 1,
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
    """Geo-aware search across ALL active listing collections (iter343).

    Behaviour:
      • lat + lng + radius_km → $geoWithin/$centerSphere on `geo`
      • Only city → case-insensitive regex on city/facility_city
      • Otherwise → standard active listings (capped by `limit`)
    """
    if _db is None:
        raise HTTPException(status_code=503, detail="geo-search db handle not initialised")

    geo_active = lat is not None and lng is not None
    effective_radius_km = radius_km if radius_km is not None else 50.0

    docs: List[Dict[str, Any]] = []
    for coll_name, section, path_prefix, statuses in GEO_SEARCH_SOURCES:
        query: Dict[str, Any] = {
            "status": {"$in": statuses},
            "is_demo": {"$ne": True},
            "is_demo_sandbox": {"$ne": True},
        }
        if category and section in ("marketplace", "lots"):
            query["category"] = category
        elif category and section not in ("marketplace", "lots"):
            # vehicle/storage sections have no free category taxonomy —
            # skip them entirely when a category filter is requested.
            continue
        if province:
            query["$or"] = [
                {"region": {"$regex": f"^{re.escape(province)}$", "$options": "i"}},
                {"province": {"$regex": f"^{re.escape(province)}$", "$options": "i"}},
                {"facility_province": {"$regex": f"^{re.escape(province)}$", "$options": "i"}},
            ]
        if geo_active:
            radius_radians = float(effective_radius_km) / 6371.0
            query["geo"] = {
                "$geoWithin": {
                    "$centerSphere": [[float(lng), float(lat)], radius_radians],
                },
            }
            query["geo.coordinates"] = {"$exists": True, "$ne": None}
        elif city:
            query["$or"] = (query.get("$or") or []) + [
                {"city": {"$regex": re.escape(city), "$options": "i"}},
                {"facility_city": {"$regex": re.escape(city), "$options": "i"}},
            ]
            # Merge with the province $or if both present (must both hold)
            if province and "$or" in query and len(query["$or"]) > 3:
                prov_or = query["$or"][:3]
                city_or = query["$or"][3:]
                query.pop("$or")
                query["$and"] = [{"$or": prov_or}, {"$or": city_or}]

        try:
            cursor = _db[coll_name].find(query, _PROJECTION).limit(limit)
            rows = await cursor.to_list(length=limit)
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[geo] query failed on {coll_name} (skipping): {e}")
            rows = []
        for r in rows:
            r["_section"], r["_path_prefix"] = section, path_prefix
        docs.extend(rows)

    # When geo is active, compute distance_km from the GeoJSON point.
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

    docs = docs[:limit]
    items = [_project(d, d.pop("_section"), d.pop("_path_prefix")) for d in docs]
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


__all__ = ["geo_router", "set_geo_db", "ensure_2dsphere_index", "GEO_SEARCH_SOURCES"]
