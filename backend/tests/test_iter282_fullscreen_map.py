"""
iter282 — Full-Screen Map Search verification.

Scope (per the user's IMG_4369 directive):
  Change 1 — Fullscreen overlay (position:fixed; 100vw/100vh;
             z-index:1000) with floating radius slider (z:1001) +
             Back button top-left (z:1002, pill, BidVex blue).
             Restores scroll position via sessionStorage on close.
  Change 2 — Item markers rendered as 40×40 image-circle divIcons
             with white border + soft shadow. BidVex fallback when
             no image. Clustering preserved via react-leaflet-cluster
             (already in package.json).
  Change 3 — Marker click → branded popup with 120px image, title
             clamped to 2 lines, CAD-formatted bid, "View Listing"
             BidVex-blue full-width button. Popup className
             `bv-map-popup` + CSS to hide the default tip arrow.

This iteration is a self-contained refactor of
`components/MapSearchPanel.jsx`. No backend changes, no parent-page
edits — the parents still pass `open` / `onClose` / `onGeoChange` and
the fullscreen UX is fully encapsulated.
"""
from __future__ import annotations

import os


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, "..", "frontend", "src"))


def _read_fe(rel: str) -> str:
    with open(os.path.join(FRONTEND_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ── Change 1 — Fullscreen overlay + Back button + scroll restore ──────


def test_iter282_overlay_is_position_fixed_full_viewport():
    src = _read_fe("components/MapSearchPanel.jsx")
    # The overlay must be position:fixed with 100vw/100vh per the spec.
    assert "position: 'fixed'" in src
    assert "width: '100vw'" in src
    assert "height: '100vh'" in src
    # Spec-pinned z-indexes — overlay at 1000.
    assert "zIndex: 1000" in src


def test_iter282_radius_slider_panel_zindex_1001():
    """The floating radius card sits ABOVE the map (1001) but BELOW
    the Back button (1002)."""
    src = _read_fe("components/MapSearchPanel.jsx")
    # Find the radius card block and confirm its zIndex.
    card_idx = src.find('data-testid="map-search-radius-card"')
    assert card_idx > 0, "radius card testid missing"
    block = src[card_idx:card_idx + 1200]
    assert "zIndex: 1001" in block


def test_iter282_back_button_zindex_1002_blue_pill():
    src = _read_fe("components/MapSearchPanel.jsx")
    btn_idx = src.find('data-testid="map-search-back-btn"')
    assert btn_idx > 0, "back button testid missing"
    block = src[btn_idx:btn_idx + 900]
    # Z-index hierarchy as specified.
    assert "zIndex: 1002" in block
    # BidVex blue brand color.
    assert "#2d6be4" in block
    # Pill shape — borderRadius 9999 = fully rounded.
    assert "borderRadius: 9999" in block


def test_iter282_close_handler_wired_to_back_button():
    src = _read_fe("components/MapSearchPanel.jsx")
    btn_idx = src.find('data-testid="map-search-back-btn"')
    block = src[btn_idx:btn_idx + 600]
    # Back button MUST call the parent-supplied onClose (CSS/state
    # toggle, not a route change).
    assert "onClick={onClose}" in block


def test_iter282_scroll_restore_uses_sessionStorage_key():
    """When the overlay opens we save scrollY to sessionStorage; on
    close we restore it. Body overflow is locked while open so the
    map doesn't double-scroll."""
    src = _read_fe("components/MapSearchPanel.jsx")
    assert "SCROLL_RESTORE_KEY" in src
    assert "sessionStorage.setItem(SCROLL_RESTORE_KEY" in src
    assert "sessionStorage.getItem(SCROLL_RESTORE_KEY)" in src
    assert "sessionStorage.removeItem(SCROLL_RESTORE_KEY)" in src
    # Body scroll lock + restore.
    assert "document.body.style.overflow = 'hidden'" in src
    assert "window.scrollTo(0, y)" in src


def test_iter282_scroll_lock_helper_is_a_hook():
    """`useScrollLockAndRestore(open)` MUST be a hook that runs on
    every `open` flip so toggling the overlay in/out is a clean
    state-only change with no route navigation."""
    src = _read_fe("components/MapSearchPanel.jsx")
    assert "function useScrollLockAndRestore(open)" in src
    assert "useScrollLockAndRestore(open)" in src
    # The cleanup function restores the previous overflow + scroll.
    assert "previousOverflow" in src
    assert "previousY" in src


# ── Change 2 — Image-circle markers (40×40) ───────────────────────────


def test_iter282_builds_divicon_marker_with_image_background():
    """Markers MUST be L.divIcon-based 40×40 image circles per the
    spec — no default Leaflet pin."""
    src = _read_fe("components/MapSearchPanel.jsx")
    assert "buildImageMarkerIcon" in src
    assert "L.divIcon" in src
    # Spec-pinned icon size.
    assert "iconSize:   [40, 40]" in src or "iconSize: [40, 40]" in src
    # Anchor centered on the circle (20, 20).
    assert "iconAnchor: [20, 20]" in src
    # className intentionally separates wrapper styling so we can
    # transparent-out the Leaflet default + own the CSS.
    assert "bvx-map-marker-wrap" in src


def test_iter282_marker_css_has_circle_shape_white_border_shadow():
    """The .bvx-map-marker class must be a 40×40 white-bordered
    circle with a soft drop shadow — per the spec."""
    src = _read_fe("components/MapSearchPanel.jsx")
    # CSS rules — width/height/border-radius/border/shadow all defined
    # inline inside the component's <style> block.
    assert "width: 40px" in src
    assert "height: 40px" in src
    assert "border-radius: 50%" in src
    assert "border: 2px solid #ffffff" in src
    assert "box-shadow:" in src
    # Background image uses cover sizing so any aspect ratio works.
    assert "background-size: cover" in src
    assert "background-position: center" in src


def test_iter282_image_fallback_uses_bidvex_logo():
    """Listings with no image MUST get the BidVex logo on a #1A1A2E
    background — never a blank circle."""
    src = _read_fe("components/MapSearchPanel.jsx")
    assert "BVX_FALLBACK_LOGO" in src
    # The data-URI SVG carries the brand background.
    assert "%231A1A2E" in src  # url-encoded #1A1A2E
    # And the safe-URL builder prefers the listing image; falls back
    # to the logo only when none is present.
    assert "(imageUrl || BVX_FALLBACK_LOGO)" in src


def test_iter282_primary_image_helper_walks_listing_shape():
    """`primaryImage(m)` MUST handle every shape the backend can ship
    (array of strings, array of objects with .url, .image flat field)."""
    src = _read_fe("components/MapSearchPanel.jsx")
    assert "const primaryImage" in src
    assert "Array.isArray(m.images)" in src
    assert "m.images[0]" in src
    assert "first.url" in src
    assert "m.image" in src


# ── Change 3 — Click popup with image + title + bid + button ──────────


def test_iter282_popup_has_branded_classname_no_tip_arrow():
    src = _read_fe("components/MapSearchPanel.jsx")
    # Spec-mandated className on the popup AND CSS rule that hides
    # the default Leaflet popup tip.
    assert 'className="bv-map-popup"' in src
    assert ".leaflet-popup.bv-map-popup .leaflet-popup-tip" in src
    assert "display: none" in src
    # White background + 8px border-radius + 12px padding.
    assert "border-radius: 8px" in src
    assert "padding: 12px" in src
    assert "background: #ffffff" in src


def test_iter282_popup_renders_image_title_bid_view_button():
    src = _read_fe("components/MapSearchPanel.jsx")
    # Image 120px wide, rounded.
    assert "width: 120" in src
    assert "borderRadius: 8" in src
    # Title clamped to 2 lines.
    assert "WebkitLineClamp: 2" in src
    assert "WebkitBoxOrient: 'vertical'" in src
    # Current bid in green.
    assert "#0D9F4F" in src
    # "View Listing" button — BidVex blue + full width.
    assert "View Listing" in src or "Voir l'annonce" in src
    # Button anchor uses the BidVex blue.
    assert "background: '#2d6be4'" in src
    # Wire-format navigation matches the existing /listing/{id} route.
    assert "/listing/${m.id}" in src


def test_iter282_popup_amount_formatted_as_cad():
    """Spec calls for current bid in CAD format. We route everything
    through Intl.NumberFormat('en-CA', { style: 'currency' })."""
    src = _read_fe("components/MapSearchPanel.jsx")
    assert "Intl.NumberFormat" in src
    assert "en-CA" in src
    assert "style: 'currency'" in src
    # currency defaults to 'CAD' when the listing doesn't carry one.
    assert "currency = 'CAD'" in src or "'CAD'" in src


def test_iter282_popup_has_per_listing_testid():
    """Per-listing testid template literal so spec tests can target
    any specific popup."""
    src = _read_fe("components/MapSearchPanel.jsx")
    assert "data-testid={`bvx-map-popup-${m.id}`}" in src
    assert "data-testid={`bvx-map-view-listing-${m.id}`}" in src


# ── Clustering preservation ────────────────────────────────────────────


def test_iter282_marker_clustering_preserved_when_over_threshold():
    """Spec said "use Leaflet.markercluster if already in deps".
    `react-leaflet-cluster` is in package.json — we must keep using it."""
    src = _read_fe("components/MapSearchPanel.jsx")
    assert "import MarkerClusterGroup from 'react-leaflet-cluster'" in src
    assert "<MarkerClusterGroup" in src
    # Existing threshold preserved.
    assert "validMarkers.length > 10" in src


def test_iter282_no_new_npm_dependencies_added():
    """Spec explicitly forbade adding new dependencies. The
    refactored file MUST import ONLY from packages already in
    package.json."""
    src = _read_fe("components/MapSearchPanel.jsx")
    allowed_imports = (
        "from 'react'",
        "from 'react-leaflet'",
        "from 'react-leaflet-cluster'",
        "from 'leaflet'",
        "from 'leaflet/dist/leaflet.css'",
        "from 'lucide-react'",
    )
    import_lines = [ln for ln in src.splitlines() if ln.startswith("import ")]
    assert import_lines, "no import lines found"
    for ln in import_lines:
        # Each import must reference one of the allowed sources.
        assert any(allowed in ln for allowed in allowed_imports), (
            f"unexpected import (new dependency?): {ln!r}"
        )


# ── Sanity: parent pages still see the same exported component ────────


def test_iter282_parent_pages_still_lazy_load_unchanged():
    """The fullscreen upgrade is a self-contained refactor — parents
    must not need any change. Confirm both existing mount sites still
    import MapSearchPanel with the same lazy-import pattern."""
    lots = _read_fe("pages/LotsMarketplacePage.js")
    assert "import('../components/MapSearchPanel')" in lots
    flat = _read_fe("components/FlattenedMarketplace.js")
    assert "import('./MapSearchPanel')" in flat


def test_iter282_geocoding_relies_on_existing_backend_geo_field():
    """The spec mentions seller-postal-code geocoding. We do NOT
    geocode client-side — the backend `/marketplace/items/geo`
    endpoint already returns each item's geo.coordinates via the
    2dsphere index. Client-side geocoding would be redundant + risk
    rate-limiting from a free public API. This test makes the design
    decision explicit so it doesn't get reverted."""
    src = _read_fe("components/MapSearchPanel.jsx")
    # We READ from the backend geo field.
    assert "m.geo.coordinates" in src
    # We do NOT call any client-side geocoding API.
    forbidden = (
        "nominatim",
        "nominatim.openstreetmap.org",
        "geocode.maps.co",
        "mapbox.com/geocoding",
        "googleapis.com/geocode",
    )
    for needle in forbidden:
        assert needle not in src.lower(), (
            f"client-side geocoding ({needle}) is forbidden — the "
            f"backend `/marketplace/items/geo` endpoint already returns "
            f"each listing's geo.coordinates via 2dsphere."
        )


# ── Smoke check on the existing /marketplace/items/geo endpoint ───────


def test_iter282_backend_geo_endpoint_still_returns_canonical_shape():
    """End-to-end sanity that the backend route the component reads
    from is still healthy and shaped the way the marker builder
    expects (id, title, images, current_price, geo.coordinates)."""
    import httpx
    BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8001")
    try:
        r = httpx.get(
            f"{BASE}/api/marketplace/items/geo",
            params={"lat": 45.5017, "lng": -73.5673, "radius_km": 100, "limit": 5},
            timeout=8.0,
        )
    except Exception:
        import pytest
        pytest.skip("backend unreachable")
    assert r.status_code == 200, r.text
    body = r.json()
    assert "items" in body
    # If any items exist they must carry the canonical shape.
    for it in body.get("items", []):
        assert "id" in it
        # `geo.coordinates` may be absent on legacy docs — but when
        # present must be a 2-tuple of [lng, lat].
        geo = it.get("geo") or {}
        if "coordinates" in geo:
            coords = geo["coordinates"]
            assert isinstance(coords, list) and len(coords) == 2
