"""
iter283-hotfix — Production hotfix following iter283 final pre-launch.

Pins four missions:
  M1 — Storage section province filter (case-insensitive + listings
        collection aggregation).
  M2 — Vehicles section public visibility (visibility flag flex +
        listing_type alias matching + case-insensitive category).
  M3 — Map cluster CSS hi-vis pill (white circle + BidVex Blue ring).
  M4 — Section-filter chip row above marketplace grid.
"""
from __future__ import annotations

import os
import pytest


def _read(rel: str) -> str:
    base = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    with open(os.path.join(base, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _read_fe(rel: str) -> str:
    base = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")
    )
    with open(os.path.join(base, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ── M1 — Storage province filter ─────────────────────────────────────


def test_hotfix_storage_provinces_aggregates_listings_collection():
    """The /provinces endpoint MUST union both source collections so
    storage units authored via the general listings flow contribute
    to the dropdown counts."""
    src = _read("routes/storage_auctions.py")
    # The endpoint is now multi-source.
    idx = src.find('@storage_router.get("/storage-auctions/provinces")')
    assert idx > 0
    block = src[idx:idx + 2500]
    # Aggregates both collections.
    assert "db.storage_auctions.aggregate" in block
    assert "db.listings.aggregate" in block
    # Uses iter283's STORAGE_TYPES (so it picks up every alias).
    assert "STORAGE_TYPES" in block


def test_hotfix_storage_province_filter_case_insensitive():
    """Selecting "QC" must match listings stored as "qc" or "Qc" too."""
    src = _read("routes/storage_auctions.py")
    # Both province filter callsites use regex with the case-insensitive
    # option flag — never `.upper()` (which broke if the data was
    # already lowercase).
    assert "facility_province" in src
    facility_idx = src.find('query["facility_province"]')
    assert facility_idx > 0
    block = src[facility_idx:facility_idx + 400]
    assert '"$options": "i"' in block
    # Same defence on the listings collection side.
    region_idx = src.find('listings_query["region"]')
    assert region_idx > 0
    block = src[region_idx:region_idx + 400]
    assert '"$options": "i"' in block


# ── M2 — Vehicles section ─────────────────────────────────────────────


def test_hotfix_vehicles_endpoint_flex_visibility():
    """The public /vehicles browse must NOT drop legacy docs that
    have no `visibility` field. Active + non-demo is enough."""
    src = _read("routes/vehicles.py")
    # The strict `"visibility": PUBLIC` was replaced by an OR that
    # accepts missing/null visibility too.
    idx = src.find("# iter283-hotfix Mission 2")
    assert idx > 0, "hotfix note missing — fix may have been reverted"
    block = src[idx:idx + 800]
    assert '"$exists": False' in block or '"$exists": false' in block.lower()


def test_hotfix_vehicles_endpoint_uses_listing_type_aliases():
    """The fallback general-listings query MUST union
    listing_type aliases + section + category fallback."""
    src = _read("routes/vehicles.py")
    assert "from services.listing_sections import VEHICLE_TYPES" in src
    assert "list(VEHICLE_TYPES)" in src
    # The OR query is multi-shape (listing_type + section + category).
    idx = src.find("general_vehicle_query")
    assert idx > 0
    block = src[idx:idx + 1500]
    assert '"listing_type"' in block
    assert '"section"' in block
    assert '"category"' in block


def test_hotfix_vehicles_endpoint_does_not_filter_by_requires_broker():
    """The public browse must NEVER filter listings out based on
    `requires_broker` — the broker gate applies to CREATION, not
    VIEWING. Buyers and guests should see every active vehicle."""
    src = _read("routes/vehicles.py")
    # Locate the public list_vehicles function.
    idx = src.find('@vehicle_router.get("/vehicles")')
    assert idx > 0
    end = src.find('@vehicle_router.get', idx + 50)
    if end < 0:
        end = len(src)
    block = src[idx:end]
    # Strip out comment lines (anything starting with `#`) — we only
    # care about actual MongoDB filters/conditionals using the field.
    code_only = "\n".join(
        line for line in block.splitlines()
        if not line.strip().startswith("#")
    )
    # No `query["requires_broker"]` or `requires_broker: ...` filter.
    assert "requires_broker" not in code_only, (
        "regression: /vehicles browse now filters by requires_broker — "
        "guests/buyers will lose visibility into broker-gated auctions."
    )


# ── M3 — Map cluster CSS ─────────────────────────────────────────────


def test_hotfix_map_cluster_high_vis_pill():
    """Cluster icons MUST use white circle + BidVex Blue (#0055FF)
    ring + bold navy digits per the design spec."""
    src = _read_fe("components/MapSearchPanel.jsx")
    # Cluster overrides are present.
    assert ".marker-cluster div" in src
    # White circle background.
    assert "background-color: #ffffff !important" in src
    # BidVex Blue 3px ring.
    assert "border: 3px solid #0055FF !important" in src
    # Deep navy text.
    assert "color: #0a1628 !important" in src
    # Bold font weight 800.
    assert "font-weight: 800 !important" in src
    # Soft drop shadow per spec.
    assert "box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15) !important" in src
    # Perfect circle.
    assert "border-radius: 50% !important" in src


# ── M4 — Section-filter chip row ─────────────────────────────────────


def test_hotfix_chip_row_renders_above_grid():
    """The chip row sits at the top of the marketplace grid component."""
    src = _read_fe("components/FlattenedMarketplace.js")
    chip_idx = src.find('data-testid="section-filter-chip-row"')
    feat_idx = src.find('section="marketplace" limit={8}')
    assert chip_idx > 0 and feat_idx > 0
    # Chip row appears AFTER the featured banner (visually below it,
    # right above the grid).
    assert chip_idx > feat_idx


def test_hotfix_chip_row_has_all_five_chips():
    src = _read_fe("components/FlattenedMarketplace.js")
    # Template-literal testid (`section-chip-${chip.id}`) carries the
    # ID list inline — assert the IDs are all listed in the chip array.
    for chip_id in ("'all'", "'marketplace'", "'lots'",
                    "'vehicles'", "'storage'"):
        assert f"id: {chip_id}" in src, (
            f"chip {chip_id} missing — Mission 4 incomplete"
        )
    # Template-literal testid is present (renders to
    # data-testid="section-chip-{id}" at runtime).
    assert 'data-testid={`section-chip-${chip.id}`}' in src


def test_hotfix_chip_row_active_style():
    """Active chip uses BidVex Blue (#0055FF) bg + white text + 700 weight."""
    src = _read_fe("components/FlattenedMarketplace.js")
    chip_block_idx = src.find('data-testid="section-filter-chip-row"')
    block = src[chip_block_idx:chip_block_idx + 3500]
    # Active state colors.
    assert "#0055FF" in block
    assert "#ffffff" in block
    # Inactive bg per spec.
    assert "#f0f4f8" in block
    # Inactive text + border per spec.
    assert "#4a5568" in block
    assert "#e2e8f0" in block


def test_hotfix_chip_row_horizontal_scroll_on_mobile():
    """Mobile: chip row scrolls horizontally."""
    src = _read_fe("components/FlattenedMarketplace.js")
    chip_block_idx = src.find('data-testid="section-filter-chip-row"')
    block = src[chip_block_idx:chip_block_idx + 3500]
    assert "overflowX: 'auto'" in block
    assert "whiteSpace: 'nowrap'" in block


def test_hotfix_chip_filter_state_default_all():
    src = _read_fe("components/FlattenedMarketplace.js")
    # Default chip state is 'all' so the universal feed is the
    # landing experience.
    assert "section_filter: 'all'" in src


# ── Backend behavioral smoke (synchronous import-only checks) ──


def test_hotfix_storage_query_filter_unchanged_by_hotfix():
    """The shared section_query_filter() still returns the canonical
    storage aliases (iter283 contract preserved)."""
    from services.listing_sections import section_query_filter, STORAGE_TYPES
    q = section_query_filter("storage")
    assert set(q["listing_type"]["$in"]) == set(STORAGE_TYPES)


def test_hotfix_deposit_rules_unchanged_by_hotfix():
    """Mission 5 contract (storage = $50 flat, vehicles = max($200, 10%))
    MUST survive every hotfix — the deposit engine wasn't touched."""
    from routes.bidder_deposits import _calc_deposit_amount
    assert _calc_deposit_amount({"listing_type": "storage_locker",
                                  "starting_price": 1.0}) == 50.0
    assert _calc_deposit_amount({"listing_type": "vehicle_auction",
                                  "starting_price": 5000.0}) == 500.0
