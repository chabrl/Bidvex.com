"""
iter238 Mission 2 — Postal-code → coordinates resolver via Nominatim.

Uses OpenStreetMap's Nominatim service (free, no API key) to resolve a
Canadian postal code to {lat, lng}. Required User-Agent header is set
per Nominatim's usage policy. Hard rate-limit: 1 RPS shared across all
resolves so we never get banned.

Used by:
  • routes/listings.py — auto-populate `geo` when a postal_code is supplied
  • POST /api/admin/backfill-coordinates — admin one-shot backfill endpoint
"""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

NOMINATIM_BASE = "https://nominatim.openstreetmap.org/search"
USER_AGENT = "BidVex/1.0 (service@bidvex.com)"

_last_call_ts: float = 0.0
_lock = asyncio.Lock()


_POSTAL_RE = re.compile(r"^[A-Z]\d[A-Z]\s?\d[A-Z]\d$", re.IGNORECASE)


def _is_valid_ca_postal(code: str) -> bool:
    return bool(_POSTAL_RE.match((code or "").strip()))


async def resolve_postal_code(postal_code: str) -> Optional[Dict[str, float]]:
    """Return {'lat': float, 'lng': float} or None. Honours 1 RPS Nominatim policy."""
    if not _is_valid_ca_postal(postal_code):
        return None
    async with _lock:
        global _last_call_ts
        wait_for = 1.05 - (asyncio.get_event_loop().time() - _last_call_ts)
        if wait_for > 0:
            await asyncio.sleep(wait_for)
        _last_call_ts = asyncio.get_event_loop().time()
        try:
            async with httpx.AsyncClient(timeout=10.0, headers={"User-Agent": USER_AGENT}) as client:
                r = await client.get(
                    NOMINATIM_BASE,
                    params={
                        "postalcode": postal_code.strip(),
                        "country": "CA",
                        "format": "json",
                        "limit": 1,
                    },
                )
            if r.status_code != 200:
                return None
            data = r.json()
            if not data:
                return None
            return {"lat": float(data[0]["lat"]), "lng": float(data[0]["lon"])}
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[iter238-nominatim] resolve_postal_code({postal_code!r}) failed: {e}")
            return None


async def resolve_listing_coordinates(db, listing_id: str) -> Dict[str, Any]:
    """Resolve coords for a single listing using the priority chain:
        1) existing geo.coordinates → no-op
        2) postal_code → Nominatim → write back to db.listings
        3) city → CITY_COORDS fallback (handled at create time already)
    """
    doc = await db.listings.find_one({"id": listing_id}, {"_id": 0, "geo": 1, "postal_code": 1, "city": 1, "region": 1})
    if not doc:
        return {"status": "not_found"}
    if (doc.get("geo") or {}).get("coordinates"):
        return {"status": "already_set"}
    postal = (doc.get("postal_code") or "").strip()
    if postal:
        resolved = await resolve_postal_code(postal)
        if resolved:
            geo_point = {
                "type": "Point",
                "coordinates": [resolved["lng"], resolved["lat"]],
                "city": doc.get("city") or "",
                "province": doc.get("region") or "",
                "source": "nominatim_postal",
            }
            await db.listings.update_one(
                {"id": listing_id},
                {"$set": {"geo": geo_point, "geo_resolved_at": datetime.now(timezone.utc)}},
            )
            return {"status": "resolved_postal", "geo": geo_point}
    # Fall back to city-level resolution.
    try:
        from utils import build_geo_point
        city_geo = build_geo_point(doc.get("city"), province=doc.get("region"))
        if city_geo:
            await db.listings.update_one(
                {"id": listing_id},
                {"$set": {"geo": {**city_geo, "source": "city_centroid"},
                          "geo_resolved_at": datetime.now(timezone.utc)}},
            )
            return {"status": "resolved_city", "geo": city_geo}
    except Exception:  # noqa: BLE001
        pass
    return {"status": "unresolved"}


async def backfill_all(db, *, max_listings: int = 200) -> Dict[str, Any]:
    """Back-fill geo for every listing missing coords. Capped to protect Nominatim."""
    cursor = db.listings.find(
        {"$or": [{"geo": {"$exists": False}}, {"geo.coordinates": None}]},
        {"_id": 0, "id": 1},
    ).limit(max_listings)
    docs = await cursor.to_list(length=max_listings)
    counts = {"resolved_postal": 0, "resolved_city": 0, "unresolved": 0, "already_set": 0}
    for d in docs:
        out = await resolve_listing_coordinates(db, d["id"])
        counts[out["status"]] = counts.get(out["status"], 0) + 1
    return {"checked": len(docs), "counts": counts}


__all__ = ["resolve_postal_code", "resolve_listing_coordinates", "backfill_all"]
