"""iter237 — GeoJSON migration + $geoWithin query tests."""
from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# 1. CITY_COORDS lookup table
# ---------------------------------------------------------------------------
def test_city_coords_includes_all_required_canadian_cities():
    from utils import CITY_COORDS
    required = [
        "sherbrooke", "montreal", "quebec city", "laval", "gatineau",
        "longueuil", "saguenay", "levis", "trois-rivieres", "drummondville",
        "saint-jerome", "granby", "sorel-tracy",
        "toronto", "ottawa", "vancouver", "calgary", "edmonton",
    ]
    for city in required:
        assert city in CITY_COORDS, f"missing {city!r}"
        entry = CITY_COORDS[city]
        assert "lat" in entry and "lng" in entry
        # Canada lat range 41-83, lng range -141 to -52.
        assert 41 <= entry["lat"] <= 83
        assert -141 <= entry["lng"] <= -52


def test_sherbrooke_locked_to_expected_coords():
    from utils import CITY_COORDS
    e = CITY_COORDS["sherbrooke"]
    assert round(e["lat"], 4) == 45.4042
    assert round(e["lng"], 4) == -71.8929


# ---------------------------------------------------------------------------
# 2. resolve_city_coords + build_geo_point
# ---------------------------------------------------------------------------
def test_resolve_city_handles_case_and_whitespace():
    from utils import resolve_city_coords
    assert resolve_city_coords("Sherbrooke")["lat"] == 45.4042
    assert resolve_city_coords("  SHERBROOKE  ")["lat"] == 45.4042
    assert resolve_city_coords("sherbrooke")["lng"] == -71.8929


def test_resolve_city_handles_french_accents():
    from utils import resolve_city_coords
    # "Trois-Rivières" with accents must still resolve via _normalise.
    assert resolve_city_coords("Trois-Rivières")["lat"] == 46.3432
    # "Lévis" with acute
    assert resolve_city_coords("Lévis")["lat"] == 46.8032


def test_resolve_unknown_city_returns_none():
    from utils import resolve_city_coords
    assert resolve_city_coords("Atlantis") is None
    assert resolve_city_coords("") is None
    assert resolve_city_coords(None) is None


def test_build_geo_point_shapes_to_geojson():
    from utils import build_geo_point
    g = build_geo_point("Sherbrooke", province="QC")
    assert g["type"] == "Point"
    # GeoJSON spec — coordinates MUST be [longitude, latitude] not [lat, lng].
    assert g["coordinates"] == [-71.8929, 45.4042]
    assert g["city"] == "Sherbrooke"
    assert g["province"] == "QC"


def test_build_geo_point_returns_none_for_unknown_city():
    from utils import build_geo_point
    assert build_geo_point("Atlantis") is None
    assert build_geo_point(None) is None


# ---------------------------------------------------------------------------
# 3. geo_search route — $geoWithin / $centerSphere query construction
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_geo_search_uses_centersphere_with_correct_radius_radians(monkeypatch):
    import routes.geo_search as mod

    captured = {}

    class _Cursor:
        def __init__(self, docs): self._docs = docs
        def limit(self, *_a, **_k): return self
        async def to_list(self, length=None): return self._docs

    class _FakeColl:
        def find(self, query, *_a, **_k):
            captured["query"] = query
            return _Cursor([])
        async def create_index(self, *_a, **_k): return "ok"

    class _FakeDB:
        def __getitem__(self, _n): return _FakeColl()
        listings = _FakeColl()
        multi_item_listings = _FakeColl()

    mod.set_geo_db(_FakeDB())
    try:
        out = await mod.get_geo_items(
            lat=45.5017, lng=-73.5673, radius_km=100,
            city=None, category=None, province=None, limit=5,
        )
        # Confirm the captured query has the right shape.
        q = captured["query"]
        assert "geo" in q
        assert "$geoWithin" in q["geo"]
        assert "$centerSphere" in q["geo"]["$geoWithin"]
        center, radius_rad = q["geo"]["$geoWithin"]["$centerSphere"]
        # Longitude FIRST (per GeoJSON).
        assert center == [-73.5673, 45.5017]
        # 100 km / 6371 km earth-radius ≈ 0.01570
        assert abs(radius_rad - (100.0 / 6371.0)) < 1e-9
        # The geo.coordinates existence guard MUST be merged (RC-4 fix).
        assert "geo.coordinates" in q
        # Result envelope is consistent.
        assert out["filter"]["radius_km"] == 100.0
        assert out["filter"]["lat"] == 45.5017
    finally:
        mod.set_geo_db(None)


@pytest.mark.asyncio
async def test_geo_search_combines_with_category_filter():
    import routes.geo_search as mod

    captured = {}

    class _Cursor:
        def limit(self, *_a, **_k): return self
        async def to_list(self, length=None): return []

    class _FakeColl:
        def find(self, query, *_a, **_k):
            captured["query"] = query
            return _Cursor()

    class _FakeDB:
        def __getitem__(self, _n): return _FakeColl()
        listings = _FakeColl()

    mod.set_geo_db(_FakeDB())
    try:
        await mod.get_geo_items(
            lat=45.5017, lng=-73.5673, radius_km=50,
            city=None, category="electronics", province="QC", limit=10,
        )
        q = captured["query"]
        # Category MUST coexist with the geo filter (RC-4 fix).
        assert q.get("category") == "electronics"
        assert "geo" in q
        assert q["status"]["$in"] == ["active", "upcoming"]
    finally:
        mod.set_geo_db(None)
