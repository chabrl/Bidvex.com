"""
iter283-vehicle-responsive — Mobile/responsive audit pins for vehicle pages.

Pins responsive Tailwind classes added across the two vehicle surfaces:

  /vehicles  (VehicleAuctionsPage.js)        — listing grid + toolbar
  /vehicles/[id]  (VehicleDetailPage.js)     — bid panel + tabs + specs

These tests do NOT touch the math contracts (still pinned by
test_iter283_vehicle_bp_zero / test_iter283_vehicle_fee_cleanup).
They guard against future regressions of the mobile layout fixes:

  • Page wrappers have `overflow-x-hidden` so 375px viewports never
    side-scroll the whole document.
  • Tab bar scrolls horizontally instead of wrapping.
  • Vehicle Specifications grid is `grid-cols-2 sm:grid-cols-3
    lg:grid-cols-4` (was `2 md:3` — no xl breakpoint).
  • Countdown timer uses `grid grid-cols-4` (equal-width cells).
  • Bid quick-increment chips use `flex-wrap` + `justify-center`.
  • Bid panel column has `min-w-0` + sticky-only at lg+.
  • Listing grid scales 1/2/3/4 columns at sm/lg/xl.
"""
from __future__ import annotations

import os


def _read_fe(rel: str) -> str:
    base = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "frontend", "src")
    )
    with open(os.path.join(base, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ── /vehicles/[id] — detail page ─────────────────────────────────────


def test_detail_page_wrapper_no_horizontal_scroll():
    """The detail page outermost `min-h-screen` wrapper has
    `overflow-x-hidden` so a mis-sized child can never produce
    horizontal scroll at 375px."""
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    assert (
        'min-h-screen bg-slate-50 dark:bg-slate-950 overflow-x-hidden" '
        'data-testid="vehicle-detail-page"'
    ) in src


def test_detail_page_header_overflow_hidden():
    """Header strip (breadcrumb + title) also clamped."""
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    assert "border-b overflow-x-hidden" in src


def test_detail_page_tabs_scroll_horizontally():
    """`<TabsList>` no longer wraps to two rows. The container
    uses `flex flex-nowrap overflow-x-auto whitespace-nowrap`."""
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    idx = src.find('<TabsList')
    assert idx > 0
    block = src[idx:idx + 600]
    assert "flex-nowrap" in block
    assert "overflow-x-auto" in block
    assert "whitespace-nowrap" in block
    # Triggers ship flex-shrink-0 so they never compress to ellipsis.
    assert "flex-shrink-0" in block


def test_detail_page_vehicle_specs_grid_2_3_4():
    """The Vehicle Specifications grid scales 2/3/4 columns
    (sm/lg/xl viewports) per spec — was only 2/3 before."""
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    assert "grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4" in src


def test_detail_page_countdown_grid_4_equal_cells():
    """Countdown timer renders as a 4-column equal-width grid
    (Days/Hours/Min/Sec) — fits in one row at 375px."""
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    assert "grid grid-cols-4 gap-1 sm:gap-2" in src
    # Each cell uses min-w-0 + truncate so a `9999d` value doesn't
    # blow out the column width.
    assert "text-center min-w-0" in src


def test_detail_page_quick_bid_chips_flex_wrap():
    """+$100 / +$500 / +$1,000 chips flex-wrap + justify-center
    so they never overflow narrow viewports."""
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    assert "flex flex-wrap gap-2 justify-center" in src
    # Each chip has a minimum width so two-up layouts feel intentional.
    assert "min-w-[90px]" in src


def test_detail_page_bid_column_sticky_only_at_lg():
    """The bid-panel column is full-width on mobile (stacks below the
    main content) and becomes a sticky right-rail at lg+. Spec:
    "On mobile, the bid panel must stack BELOW the main content
    as a full-width block. On lg: and above, it should sit as a
    sticky right-column sidebar."

    iter286 — Bug 3 — Updated: the previous test pinned an inner-
    scroll constraint (`lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto`)
    that was the *cause* of the production "bid panel has its own
    scrollbar" bug. The fix removes those classes so the panel sticks
    to the viewport top but scrolls naturally with the page when its
    content exceeds the screen height. This test guards the corrected
    className and explicitly fails if the inner-scroll regression
    sneaks back in.
    """
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    # The bid-column wrapper sits IMMEDIATELY above the testid in
    # the JSX tree — match the className -> data-testid pair.
    needle = (
        'lg:col-span-2 space-y-4 min-w-0 lg:sticky lg:top-20 '
        'lg:self-start"\n            data-testid="vehicle-detail-bid-column"'
    )
    assert needle in src, (
        "bid-panel wrapper className regressed — expected:\n"
        f"  {needle!r}\n"
        "but it was not found in VehicleDetailPage.js"
    )
    # Guard against the inner-scroll regression.
    assert "lg:max-h-[calc(100vh-6rem)] lg:overflow-y-auto" not in src, (
        "Inner-scroll classes reintroduced — re-creates the production "
        "bug where the right-side bid panel scrolled independently."
    )


def test_detail_page_broker_gate_cta_stacks_on_mobile():
    """Broker gate "Become a Broker Partner" + "Learn More" CTAs
    stack vertically (full-width) on mobile, side-by-side at sm+."""
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    assert "flex flex-col sm:flex-row sm:flex-wrap gap-2" in src
    # Each CTA goes full-width on mobile.
    assert 'className="font-bold w-full sm:w-auto"' in src


def test_detail_page_main_container_responsive_padding():
    """Page padding shrinks on narrow viewports so the inner grid
    has more room to render."""
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    assert "max-w-7xl mx-auto px-3 sm:px-4 py-6 sm:py-8" in src


def test_detail_page_documentation_grid_responsive_padding():
    """Documentation section (Title/Ownership/Lien) uses tighter
    gap at mobile so the 3 cells fit at 375px."""
    src = _read_fe("pages/vehicles/VehicleDetailPage.js")
    assert "grid grid-cols-3 gap-2 sm:gap-4 text-sm" in src
    # Each cell has min-w-0 + truncate label so values stay inside.
    assert 'className="text-center p-3 sm:p-4 bg-slate-50 dark:bg-slate-800 rounded-lg min-w-0"' in src


# ── /vehicles — listing grid page ────────────────────────────────────


def test_listing_page_no_horizontal_scroll():
    """The listing page outer wrapper clamped horizontally."""
    src = _read_fe("pages/vehicles/VehicleAuctionsPage.js")
    assert (
        'min-h-screen bg-slate-50 dark:bg-slate-950 overflow-x-hidden" '
        'data-testid="vehicle-auctions-page"'
    ) in src


def test_listing_page_grid_scales_1_2_3_4():
    """The auction-card grid scales 1/2/3/4 columns at sm/lg/xl
    so even 4K monitors don't waste space."""
    src = _read_fe("pages/vehicles/VehicleAuctionsPage.js")
    assert (
        "grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4"
    ) in src
    # And the loading skeleton + actual grid both ship the same
    # responsive contract.
    assert src.count("grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4") >= 2
