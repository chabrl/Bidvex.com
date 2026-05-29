"""
iter238 Mission 5 — Promoted / Featured listings API.

Endpoints:
  GET  /api/listings/promoted?section={marketplace|lots|storage|vehicles|homepage}&limit=8
  POST /api/listings/{listing_id}/promote
       Body: { sections: ["marketplace","homepage",...], duration_days: 7 }
  POST /api/admin/backfill-coordinates  (mission 2.2)

Promotion data lives on the listing doc itself:
  is_promoted, promotion_tier, promotion_sections, promotion_expires_at, promoted_at
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

promotions_router = APIRouter(tags=["Listing Promotions"])
_security = HTTPBearer(auto_error=False)
_db = None


def set_promotions_db(database) -> None:
    global _db
    _db = database


_PROMOTION_SECTIONS = {"marketplace", "lots", "storage", "vehicles", "homepage"}


class PromoteBody(BaseModel):
    sections: List[str] = Field(default_factory=lambda: ["marketplace"])
    duration_days: int = Field(7, ge=1, le=90)
    tier: str = Field("featured")


def _project_promo(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": doc.get("id"),
        "title": doc.get("title"),
        "category": doc.get("category"),
        "images": doc.get("images") or [],
        "current_price": doc.get("current_price") or doc.get("current_bid"),
        "starting_price": doc.get("starting_price"),
        "buy_now_enabled": bool(doc.get("buy_now_enabled")),
        "buy_now_price": doc.get("buy_now_price"),
        "currency": doc.get("currency") or "CAD",
        "city": doc.get("city"),
        "region": doc.get("region"),
        "seller_id": doc.get("seller_id"),
        "status": doc.get("status"),
        "auction_end_date": doc.get("auction_end_date"),
        "quantity": doc.get("quantity") or 1,
        "multiply_hammer_by_quantity": bool(doc.get("multiply_hammer_by_quantity")),
        "price_multiplied_by_quantity": bool(doc.get("price_multiplied_by_quantity")),
        "listing_type": doc.get("listing_type"),
        "is_promoted": True,
        "promotion_tier": doc.get("promotion_tier"),
        "promoted_at": doc.get("promoted_at"),
        "promotion_expires_at": doc.get("promotion_expires_at"),
    }


@promotions_router.get("/promoted-listings")
async def get_promoted(
    section: str = Query("marketplace", max_length=20),
    limit: int = Query(8, ge=1, le=24),
) -> Dict[str, Any]:
    if _db is None:
        raise HTTPException(status_code=503, detail="db not initialised")
    if section not in _PROMOTION_SECTIONS:
        raise HTTPException(status_code=400, detail=f"section must be one of {sorted(_PROMOTION_SECTIONS)}")
    now = datetime.now(timezone.utc)
    query = {
        "is_promoted": True,
        "promotion_sections": section,
        "$or": [
            {"promotion_expires_at": None},
            {"promotion_expires_at": {"$gt": now}},
        ],
        "status": {"$in": ["active", "upcoming"]},
    }
    cursor = _db.listings.find(query, {"_id": 0}).sort("promoted_at", -1).limit(limit)
    docs = await cursor.to_list(length=limit)
    return {"items": [_project_promo(d) for d in docs], "total": len(docs), "section": section}


@promotions_router.post("/listings/{listing_id}/promote")
async def promote_listing(
    listing_id: str,
    body: PromoteBody,
    creds: HTTPAuthorizationCredentials = Depends(_security),
) -> Dict[str, Any]:
    if _db is None:
        raise HTTPException(status_code=503, detail="db not initialised")
    if not creds or not creds.credentials:
        raise HTTPException(status_code=401, detail="auth required")

    # Permission gate — seller must own the listing OR be admin.
    from routes.auth import _decode_jwt  # type: ignore
    try:
        payload = _decode_jwt(creds.credentials)
        user_id = payload.get("sub") or payload.get("user_id")
        # iter239 — Accept both `is_admin` boolean claim AND `role: "admin"`
        # so admins minted under either token scheme can promote listings.
        is_admin = bool(payload.get("is_admin")) or payload.get("role") == "admin"
    except Exception:
        raise HTTPException(status_code=401, detail="invalid token")

    listing = await _db.listings.find_one({"id": listing_id}, {"_id": 0, "seller_id": 1, "listing_type": 1})
    if not listing:
        raise HTTPException(status_code=404, detail="listing not found")
    if not is_admin and listing.get("seller_id") != user_id:
        raise HTTPException(status_code=403, detail="not your listing")

    # Validate sections.
    invalid = [s for s in body.sections if s not in _PROMOTION_SECTIONS]
    if invalid:
        raise HTTPException(status_code=400, detail=f"invalid sections: {invalid}")

    now = datetime.now(timezone.utc)
    expires = now + timedelta(days=body.duration_days)
    await _db.listings.update_one(
        {"id": listing_id},
        {
            "$set": {
                "is_promoted": True,
                "promotion_tier": body.tier,
                "promotion_sections": body.sections,
                "promoted_at": now,
                "promotion_expires_at": expires,
            },
        },
    )
    return {
        "status": "promoted",
        "sections": body.sections,
        "promotion_tier": body.tier,
        "promotion_expires_at": expires.isoformat(),
    }


@promotions_router.post("/admin/backfill-coordinates")
async def backfill_coordinates(
    creds: HTTPAuthorizationCredentials = Depends(_security),
    max_listings: int = Query(200, ge=1, le=1000),
) -> Dict[str, Any]:
    """iter238 Mission 2.2 — admin backfill for missing geo coords."""
    if not creds:
        raise HTTPException(status_code=401, detail="auth required")
    from routes.admin import require_admin
    await require_admin(creds)
    if _db is None:
        raise HTTPException(status_code=503, detail="db not initialised")
    from services.geo_resolver import backfill_all
    return await backfill_all(_db, max_listings=max_listings)


__all__ = ["promotions_router", "set_promotions_db"]
