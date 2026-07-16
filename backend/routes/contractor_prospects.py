"""
iter341 P1 — Contractor Prospect Finder routes.

GET /api/contractor/prospect-finder?city=Montreal&type=vehicle_dealer&radius_km=25
Auth: dialer_contractor, admin. Feature-flagged on GOOGLE_MAPS_API_KEY.
Results cached 24h per {city+type+radius} in Mongo for billing control;
`already_in_bidvex` is recomputed on every request (accounts change daily).
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException, Query

from deps import get_db, User
from routes.twilio import require_dialer_access
from services.prospect_finder import (
    BILLING_NOTE, TYPE_QUERIES, flag_already_in_bidvex, maps_flag, search_places,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contractor", tags=["prospect-finder"])

CACHE_TTL_SECONDS = 24 * 3600
MAX_RESULTS = 20
# iter353 — Cloudflare origin timeout on bidvex.com is ~30s. Cap the outer
# request budget well below that so we always return a JSON body — never
# an "invalid or incomplete response" Cloudflare error.
REQUEST_BUDGET_SECONDS = 22.0


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("/prospect-finder/config")
async def prospect_finder_config(user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    return {**maps_flag(), "types": list(TYPE_QUERIES.keys()), "billing_note": BILLING_NOTE}


@router.get("/prospect-finder")
async def prospect_finder(
    city: str = Query(..., min_length=2, max_length=80),
    biz_type: str = Query(..., alias="type"),
    radius_km: int = Query(25, ge=1, le=100),
    user: User = Depends(require_dialer_access),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """iter353 hardened — every failure path returns 200 with an `error`
    field so Cloudflare never sees a malformed origin response. Total
    request budget is bounded by `asyncio.wait_for(..., 22s)` below
    Cloudflare's 30s origin ceiling."""
    flag = maps_flag()
    if not flag["enabled"]:
        raise HTTPException(503, flag["prerequisite"])
    if biz_type not in TYPE_QUERIES:
        raise HTTPException(400, f"invalid type — one of: {', '.join(TYPE_QUERIES)}")

    async def _run() -> Dict[str, Any]:
        started = time.monotonic()
        cache_key = f"{city.strip().lower()}|{biz_type}|{radius_km}"
        cached = await db.prospect_finder_cache.find_one({"key": cache_key}, {"_id": 0})
        cache_hit = False
        results = []
        if cached:
            age = (_now() - datetime.fromisoformat(cached["fetched_at"])).total_seconds()
            if age < CACHE_TTL_SECONDS:
                results = cached["results"]
                cache_hit = True
        if not cache_hit:
            try:
                results = await search_places(city.strip(), biz_type, MAX_RESULTS)
            except Exception as e:  # noqa: BLE001
                logger.error(f"[prospect-finder] Places API error for city={city!r} type={biz_type!r}: {e}")
                # Graceful 200 — Cloudflare stays happy, frontend renders empty state
                return {
                    "items": [], "total": 0, "cached": False,
                    "fetched_at": _now().isoformat(),
                    "error": "prospect_finder_upstream_unavailable",
                    "error_message_en": (
                        "Google Places is temporarily slow or unavailable. "
                        "Please try again in a moment or use a more specific city name."
                    ),
                    "error_message_fr": (
                        "Google Places est temporairement lent ou indisponible. "
                        "Veuillez réessayer dans un instant ou saisir un nom de ville plus précis."
                    ),
                    "billing_note": BILLING_NOTE,
                    "duration_ms": int((time.monotonic() - started) * 1000),
                }
            try:
                await db.prospect_finder_cache.update_one(
                    {"key": cache_key},
                    {"$set": {"key": cache_key, "results": results,
                              "fetched_at": _now().isoformat(), "requested_by": user.id}},
                    upsert=True,
                )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[prospect-finder] cache write failed (non-fatal): {e}")

        items = [dict(r) for r in results]
        await flag_already_in_bidvex(db, items)
        return {
            "items": items,
            "total": len(items),
            "cached": cache_hit,
            "fetched_at": (cached or {}).get("fetched_at") if cache_hit else _now().isoformat(),
            "billing_note": BILLING_NOTE,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    try:
        return await asyncio.wait_for(_run(), timeout=REQUEST_BUDGET_SECONDS)
    except asyncio.TimeoutError:
        logger.error(
            f"[prospect-finder] outer budget exceeded {REQUEST_BUDGET_SECONDS}s "
            f"city={city!r} type={biz_type!r} radius={radius_km}"
        )
        return {
            "items": [], "total": 0, "cached": False,
            "fetched_at": _now().isoformat(),
            "error": "prospect_finder_timeout",
            "error_message_en": (
                "Search took too long. Try a smaller/more specific city name "
                "(e.g. \"Montreal\" instead of \"Quebec\")."
            ),
            "error_message_fr": (
                "La recherche a été trop longue. Essayez un nom de ville plus précis "
                "(p. ex. « Montréal » au lieu de « Québec »)."
            ),
            "billing_note": BILLING_NOTE,
        }
    except Exception as e:  # noqa: BLE001
        # Absolute belt-and-suspenders — anything unexpected still returns 200
        logger.exception(f"[prospect-finder] unexpected failure: {e}")
        return {
            "items": [], "total": 0, "cached": False,
            "fetched_at": _now().isoformat(),
            "error": "prospect_finder_internal_error",
            "error_message_en": "An unexpected error occurred. Our team has been notified.",
            "error_message_fr": "Une erreur inattendue s'est produite. Notre équipe a été notifiée.",
            "billing_note": BILLING_NOTE,
        }
