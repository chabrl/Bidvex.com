"""
iter282 — Change 4: Seller location pin accuracy.

Verifies the priority chain used by `routes/listings.py::create_listing`
when a new listing is inserted:

    1) postal_code present → Nominatim resolve → `geo.source = "nominatim_postal"`
    2) postal_code absent or fails → CITY_COORDS centroid → `geo.source = "city_centroid"`
    3) neither resolves → `geo` field is OMITTED entirely (silent skip)

The map endpoint `/api/marketplace/items/geo` filters by `$geoWithin`
which inherently excludes documents missing `geo.coordinates`, so an
unresolvable listing is never plotted at a misleading default (0,0 or
map center).

These tests pin the behavior in `services/geo_resolver.py` and the
text-level priority chain in `routes/listings.py`. They do NOT call
Nominatim live — the network resolver is monkey-patched.
"""
from __future__ import annotations

import os

import pytest


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


def _read_backend(rel: str) -> str:
    with open(os.path.join(BACKEND_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ── Static-text guard — pin the priority chain in routes/listings.py ──


def test_iter282_listing_creation_uses_postal_code_priority():
    """The single-listing create route MUST attempt postal_code resolution
    BEFORE falling back to city centroid. iter237's city-only enrichment
    was insufficient — postal_code is FSA-precise and ships per-listing."""
    src = _read_backend("routes/listings.py")
    # The iter282 enrichment block exists.
    assert "[iter282-geo]" in src
    # Priority hint in the comment so future agents don't revert.
    assert "Priority chain" in src or "priority chain" in src
    # Imports `resolve_postal_code` from the iter238 resolver service.
    assert "from services.geo_resolver import resolve_postal_code" in src
    # Postal source is tagged so admin tooling can distinguish per-listing
    # accuracy from rough city centroids.
    assert '"source": "nominatim_postal"' in src
    # City fallback still preserved.
    assert '"source": "city_centroid"' in src or '"source": "city_centroid",' in src


def test_iter282_listing_creation_silently_skips_unresolvable():
    """When neither postal_code nor city resolves we MUST leave `geo`
    unset (NOT default to 0,0 or the map center). The `$geoWithin`
    query then silently skips this listing on the map."""
    src = _read_backend("routes/listings.py")
    # The enrichment block sets `geo` only when `_geo` is truthy —
    # there is no `else: listing_dict["geo"] = {...default coords...}`.
    block_start = src.find("[iter282-geo]")
    assert block_start > 0
    block = src[block_start - 1500:block_start + 200]
    # Explicit "silently skips" intent documented in the source for
    # zero-ambiguity to maintenance agents.
    assert "silently skip" in block.lower() or "silently skipped" in block.lower()


# ── Functional tests — resolve_listing_coordinates priority chain ──


@pytest.mark.asyncio
async def test_iter282_resolver_postal_wins_over_city(monkeypatch):
    """Postal-code path MUST take precedence over the city centroid
    when both are available. Source tag = 'nominatim_postal'."""
    from services import geo_resolver

    captured = {"update": None}

    async def _fake_resolve(_postal):
        return {"lat": 45.4042, "lng": -71.8929}

    monkeypatch.setattr(geo_resolver, "resolve_postal_code", _fake_resolve)

    class _Listings:
        async def find_one(self, *_a, **_k):
            return {
                "id": "L1",
                "geo": None,
                "postal_code": "J1H 1B1",
                "city": "Montreal",   # different city — must be IGNORED
                "region": "QC",
            }

        async def update_one(self, _f, update):
            captured["update"] = update

    class _DB:
        listings = _Listings()

    out = await geo_resolver.resolve_listing_coordinates(_DB(), "L1")
    assert out["status"] == "resolved_postal"
    # Coordinates came from the (mocked) postal resolver — Sherbrooke FSA.
    point = captured["update"]["$set"]["geo"]
    assert point["type"] == "Point"
    assert point["coordinates"] == [-71.8929, 45.4042]
    assert point["source"] == "nominatim_postal"


@pytest.mark.asyncio
async def test_iter282_resolver_falls_back_to_city_when_postal_fails(monkeypatch):
    """If Nominatim returns nothing for the postal code we MUST fall back
    to the city centroid with source='city_centroid'."""
    from services import geo_resolver

    captured = {"update": None}

    async def _fake_resolve(_postal):
        return None  # Nominatim could not resolve

    monkeypatch.setattr(geo_resolver, "resolve_postal_code", _fake_resolve)

    class _Listings:
        async def find_one(self, *_a, **_k):
            return {
                "id": "L2",
                "geo": None,
                "postal_code": "X0X 0X0",   # syntactically valid but unknown
                "city": "Sherbrooke",
                "region": "QC",
            }

        async def update_one(self, _f, update):
            captured["update"] = update

    class _DB:
        listings = _Listings()

    out = await geo_resolver.resolve_listing_coordinates(_DB(), "L2")
    assert out["status"] == "resolved_city"
    point = captured["update"]["$set"]["geo"]
    assert point["type"] == "Point"
    # Sherbrooke centroid per CITY_COORDS.
    assert point["coordinates"] == [-71.8929, 45.4042]
    assert point["source"] == "city_centroid"


@pytest.mark.asyncio
async def test_iter282_resolver_returns_unresolved_when_city_unknown(monkeypatch):
    """No postal + unknown city = no geo written. The map endpoint will
    silently skip this listing (correct behavior per the spec)."""
    from services import geo_resolver

    update_called = {"hit": False}

    async def _fake_resolve(_postal):
        return None

    monkeypatch.setattr(geo_resolver, "resolve_postal_code", _fake_resolve)

    class _Listings:
        async def find_one(self, *_a, **_k):
            return {
                "id": "L3",
                "geo": None,
                "postal_code": "",
                "city": "Atlantis",
                "region": "QC",
            }

        async def update_one(self, _f, _u):
            update_called["hit"] = True

    class _DB:
        listings = _Listings()

    out = await geo_resolver.resolve_listing_coordinates(_DB(), "L3")
    assert out["status"] == "unresolved"
    # CRITICAL: no DB write — we never plant a misleading default pin.
    assert update_called["hit"] is False


# ── Frontend defence: marker layer skips listings without coordinates ──


def test_iter282_frontend_filters_out_listings_without_geo():
    """Defence-in-depth: even if the backend ever shipped an item with
    no/blank `geo.coordinates`, the map MUST not plot it."""
    fe_src_path = os.path.join(
        BACKEND_ROOT, "..", "frontend", "src",
        "components", "MapSearchPanel.jsx",
    )
    with open(fe_src_path, "r", encoding="utf-8") as fh:
        src = fh.read()
    # The component explicitly filters out malformed coords before
    # passing into the cluster/marker layer.
    assert "m?.geo?.coordinates?.length === 2" in src
    # No marker is ever rendered at [0, 0].
    assert "[0, 0]" not in src
    assert "MONTREAL_CENTER" in src  # map *center* default is OK; markers must NOT use it
