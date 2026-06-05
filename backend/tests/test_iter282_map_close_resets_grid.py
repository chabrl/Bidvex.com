"""
iter282 hotfix — Map close MUST reset the items grid.

Bug report (Feb 05, 2026 — production user):
    "When the user searches by map and clicks Back, the page opens
     with empty items. The user needs to refresh the page in order
     to see the items back."

Root cause:
    The parent pages render the map via a conditional:
        {mapOpen && <MapSearchPanel onClose={() => setMapOpen(false)} ...>}
    When the user clicks Back inside MapSearchPanel, the panel calls
    `setMapOpen(false)` → the conditional removes the panel from the
    JSX tree → the panel UNMOUNTS. React does NOT re-run a useEffect
    body on unmount, only its cleanup callback. The panel's internal
    "clear geo on close" useEffect (lines 217-221 of MapSearchPanel.jsx)
    relies on the body running with `open=false`, which never happens
    in the conditional-render path → `geoFilter` stays populated →
    `geoItems` stays at the last (possibly empty) fetch result →
    grid shows "No items found" until full page refresh.

Fix:
    Both `FlattenedMarketplace.js` and `LotsMarketplacePage.js` now
    explicitly call `setGeoFilter(null)` inside the `onClose` handler
    they pass to `MapSearchPanel`. This guarantees the parent state
    is reset BEFORE the panel unmounts. The downstream effect
    (`if (!geoFilter) setGeoItems(null)`) then trips and the grid
    flips back to the cached marketplace items.
"""
from __future__ import annotations

import os
import re


FRONTEND_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")
)


def _read(rel: str) -> str:
    with open(os.path.join(FRONTEND_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _extract_jsx_block(src: str, opening_tag: str) -> str:
    """Return the substring covering the JSX element starting at
    `opening_tag` (e.g. `<MapSearchPanel`). Walks character-by-character
    so JSX braces / nested comments don't confuse boundary detection."""
    start = src.find(opening_tag)
    assert start > 0, f"{opening_tag!r} not found"
    # The element ends at the first top-level `/>` (self-closing) OR
    # the first `>` followed by `</Tag>` (paired). To stay simple we
    # walk forward, tracking nested `{ ... }` depth, and bail at `/>`
    # when depth is 0.
    depth = 0
    i = start + 1
    while i < len(src):
        ch = src[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif depth == 0 and ch == "/" and src[i + 1:i + 2] == ">":
            return src[start:i + 2]
        elif depth == 0 and ch == ">":
            return src[start:i + 1]
        i += 1
    raise AssertionError(f"could not locate end of {opening_tag!r}")


def test_iter282_hotfix_flattened_marketplace_clears_geo_on_close():
    """The FlattenedMarketplace onClose handler MUST clear geoFilter
    so the items grid recovers without a manual page refresh."""
    src = _read("components/FlattenedMarketplace.js")
    block = _extract_jsx_block(src, "<MapSearchPanel")
    # The handler explicitly calls setGeoFilter(null) BEFORE
    # setMapOpen(false) order isn't strict but both must appear.
    assert "setGeoFilter(null)" in block, (
        "regression: FlattenedMarketplace MapSearchPanel onClose "
        "no longer clears geoFilter — the bug from Feb 05, 2026 "
        "would resurface."
    )
    assert "setMapOpen(false)" in block, (
        "MapSearchPanel onClose must still close the panel"
    )


def test_iter282_hotfix_lots_marketplace_clears_geo_on_close():
    """The LotsMarketplacePage onClose handler MUST clear geoFilter."""
    src = _read("pages/LotsMarketplacePage.js")
    block = _extract_jsx_block(src, "<MapSearchPanel")
    assert "setGeoFilter(null)" in block, (
        "regression: LotsMarketplacePage MapSearchPanel onClose "
        "no longer clears geoFilter — the bug from Feb 05, 2026 "
        "would resurface."
    )
    assert "setMapOpen(false)" in block, (
        "MapSearchPanel onClose must still close the panel"
    )


def test_iter282_hotfix_documents_the_unmount_race():
    """Each call site MUST carry an inline comment explaining the
    unmount race so future agents don't naively revert the fix."""
    flat_src = _read("components/FlattenedMarketplace.js")
    lots_src = _read("pages/LotsMarketplacePage.js")
    # Both files document the race in their onClose handlers.
    for src in (flat_src, lots_src):
        # The handler mentions the conditional-unmount race.
        flat_block = _extract_jsx_block(src, "<MapSearchPanel")
        assert "iter282 hotfix" in flat_block.lower()
        assert "unmount" in flat_block.lower()


def test_iter282_hotfix_both_call_sites_use_same_pattern():
    """Both fixes apply the SAME pattern (setMapOpen(false) +
    setGeoFilter(null)) so any future MapSearchPanel mount picks
    up the same canonical handler."""
    for rel in ("components/FlattenedMarketplace.js", "pages/LotsMarketplacePage.js"):
        src = _read(rel)
        block = _extract_jsx_block(src, "<MapSearchPanel")
        # Sanity — both calls are present in the handler.
        assert re.search(r"setMapOpen\s*\(\s*false\s*\)", block), rel
        assert re.search(r"setGeoFilter\s*\(\s*null\s*\)", block), rel
