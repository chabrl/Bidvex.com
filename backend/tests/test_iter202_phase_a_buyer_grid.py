"""
iter202 Phase A — Vehicle Auctions Buyer Experience
====================================================
Backend tests for the new public endpoints / query params consumed by the
new VehicleHero, VehicleCategoryPills, and VehicleListingsGrid:

  • GET /api/vehicles/stats        — public counters
  • GET /api/vehicles               — taxonomy filter + promoted_first sort

These tests do NOT require auth; they exercise the public buyer-grid surface.
"""
import os
import sys
import asyncio
from datetime import datetime, timezone, timedelta

import pytest
import httpx

BACKEND_URL = "http://localhost:8001/api"


# ---------------------------------------------------------------------------
# /vehicles/stats — public counters
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vehicle_stats_public_shape():
    """Stats endpoint must be public, return 200, and expose 5 counters + as_of timestamp."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BACKEND_URL}/vehicles/stats")
    assert r.status_code == 200, r.text
    body = r.json()
    for key in ("active_listings", "ending_soon", "verified_dealers", "provinces_covered", "total_bids_24h"):
        assert key in body, f"missing key {key} in stats response"
        assert isinstance(body[key], int), f"{key} must be int, got {type(body[key])}"
        assert body[key] >= 0
    assert "as_of" in body
    # ISO-8601 with timezone
    ts = datetime.fromisoformat(body["as_of"])
    assert ts.tzinfo is not None


# ---------------------------------------------------------------------------
# /vehicles — taxonomy filter + promoted_first sort
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_vehicles_endpoint_accepts_promoted_first_param():
    """Sprint constraint: grid must support promoted_first sort param without 422."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BACKEND_URL}/vehicles", params={"promoted_first": "true", "limit": 6})
    assert r.status_code == 200, r.text
    body = r.json()
    assert "vehicles" in body and "total" in body and "page" in body
    assert isinstance(body["vehicles"], list)


@pytest.mark.asyncio
async def test_vehicles_endpoint_accepts_category_filter_param():
    """category_id filter must round-trip safely without 4xx/5xx, even if no listings match."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{BACKEND_URL}/vehicles",
            params={"category_id": "parts_accessories", "limit": 5},
        )
    assert r.status_code == 200, r.text
    body = r.json()
    # Empty listings is a valid response state
    assert body["total"] >= 0
    assert isinstance(body["vehicles"], list)


@pytest.mark.asyncio
async def test_vehicles_endpoint_accepts_subcategory_filter():
    """subcategory_id filter must round-trip cleanly."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(
            f"{BACKEND_URL}/vehicles",
            params={
                "category_id": "passenger_cars",
                "subcategory_id": "sedan",
                "limit": 5,
            },
        )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_vehicles_endpoint_default_response_shape():
    """No-param GET must return the expected response keys."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BACKEND_URL}/vehicles")
    assert r.status_code == 200
    body = r.json()
    for key in ("vehicles", "total", "page", "pages"):
        assert key in body


@pytest.mark.asyncio
async def test_vehicle_categories_still_returns_15():
    """Phase 2 categories endpoint must still expose all 15 vehicle categories (regression)."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BACKEND_URL}/vehicles/categories")
    assert r.status_code == 200
    body = r.json()
    assert body.get("total") == 15
    items = body.get("items") or []
    ids = {c["id"] for c in items}
    assert "parts_accessories" in ids
    parts = next(c for c in items if c["id"] == "parts_accessories")
    assert parts["requires_dealer_license"] is False, "parts_accessories must remain open to non-dealers"


@pytest.mark.asyncio
async def test_vehicle_province_regulations_unchanged():
    """Phase 1 province regulations must still expose all 13 jurisdictions (regression)."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BACKEND_URL}/vehicles/province-regulations")
    assert r.status_code == 200
    body = r.json()
    assert body.get("total") == 13


@pytest.mark.asyncio
async def test_vehicle_system_status_still_works():
    """Existing /vehicles/system/status endpoint must remain compatible (used by old code paths)."""
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{BACKEND_URL}/vehicles/system/status")
    assert r.status_code == 200
    body = r.json()
    assert "vehicle_auctions_enabled" in body
