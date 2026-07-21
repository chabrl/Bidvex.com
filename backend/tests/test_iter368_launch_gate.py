"""
iter368 — Static launch-gate tests for multi-lot UX refinement + affiliate corrections.

Coverage:
  1. Dynamic Bid Increment Table (component fetches from server; no hardcoded ladder)
  2. Dynamic increment-info + next-bid endpoints derive from utils.py
  3. Compact lot card (image 180 px, arrows, single image, no "Starting Bid",
     Fees popover, Buy Now, Auto-Bid Bot button, state variants)
  4. LotDetailPage exists + registered on route
  5. Prev / Next lot navigation (buttons + keyboard + swipe hooks)
  6. Scroll-restoration snapshot on grid return
  7. Affiliate page copy uses 3% net platform profit / for life (no 10%)
  8. Affiliate dashboard has This Month / Last Month / Lifetime / Projected
  9. Referral table renders pending/approved/rejected badges
"""
from pathlib import Path

ROOT = Path("/app")


def read(path: str) -> str:
    return (ROOT / path.lstrip("/")).read_text(encoding="utf-8")


# ----- 1. Dynamic Bid Increment Table -----

def test_bid_increment_table_is_dynamic():
    src = read("frontend/src/components/BidIncrementTable.jsx")
    # No hardcoded ladder / no INCREMENTS constant array.
    assert "INCREMENTS" not in src
    # Component must fetch from the server endpoint.
    assert "increment-info" in src
    assert "auctionId" in src
    # Both tiered/simplified and fixed rendering branches present.
    assert 'data-testid="bid-increment-fixed"' in src
    assert 'data-testid="bid-increment-rows"' in src
    assert 'data-testid="bid-increment-strategy"' in src


def test_multi_lot_page_passes_auction_id_to_table():
    src = read("frontend/src/pages/MultiItemListingDetailPage.js")
    assert "<BidIncrementTable auctionId={id}" in src


# ----- 2. Dynamic increment-info + next-bid endpoints derive from utils.py -----

def test_increment_info_endpoint_is_dynamic():
    src = read("backend/routes/misc.py")
    # iter368 replaced the hardcoded schedule blocks with utils-derived data.
    assert "get_minimum_increment_tiered" in src
    assert "get_minimum_increment_simplified" in src
    # Response shape must expose min/max/step per row + labels.
    assert '"min": float(lo)' in src
    assert '"step": float(step)' in src
    assert '"range_label":' in src
    assert '"increment_label":' in src
    # Fixed mode support.
    assert '"increment_option": "fixed"' in src


def test_next_bid_endpoint_exists():
    src = read("backend/routes/misc.py")
    assert '@misc_router.get("/multi-item-listings/{listing_id}/next-bid")' in src
    assert 'async def get_multi_lot_next_bid' in src
    assert '"suggestions":' in src


def test_frontend_min_increment_walks_server_schedule():
    src = read("frontend/src/pages/MultiItemListingDetailPage.js")
    # iter368 refactor: uses the schedule array from server, no hardcoded numbers.
    assert "incrementInfo.schedule" in src
    # Old inline ladder must be gone.
    assert "if (currentBid < 100) return 5" not in src


# ----- 3. Compact lot card -----

def test_compact_lot_card_exists_and_shape():
    src = read("frontend/src/components/CompactLotCard.jsx")
    # iter369 — Fixed 200 px image height (was 180).
    assert "height: 200" in src
    # Prev/next image arrows for multi-image lots (interpolated data-testids).
    assert "prev-image" in src
    assert "next-image" in src
    # No hardcoded "Starting Bid" / "Opening Bid" in the card.
    assert "Starting Bid" not in src
    assert "Opening Bid" not in src
    # iter369 — Buy Now removed from grid cards. Auto-Bid + Fees stay.
    assert "auto-bid" in src
    assert "fees-btn" in src
    assert "fees-popover" in src
    # State variants covered (default / leading / outbid / ended).
    assert "stateStyles" in src
    for k in ["default", "leading", "outbid", "ended"]:
        assert f"{k}:" in src or f"'{k}'" in src or f'"{k}"' in src


def test_multi_lot_page_uses_compact_card():
    src = read("frontend/src/pages/MultiItemListingDetailPage.js")
    assert "import CompactLotCard" in src
    assert "<CompactLotCard" in src
    # The heavy 500-line inline card must no longer be present.
    assert "View Fee Breakdown" not in src


# ----- 4. LotDetailPage + route registered -----

def test_lot_detail_page_exists():
    src = read("frontend/src/pages/LotDetailPage.jsx")
    for tid in [
        "lot-detail-page", "lot-detail-title", "lot-detail-current-bid",
        "lot-detail-next-bid", "lot-detail-quick-bid",
        "lot-detail-prev", "lot-detail-next",
        "lot-detail-back-to-grid", "lot-detail-bid-history",
        "lot-detail-actions", "lot-detail-seller",
    ]:
        assert tid in src, f"missing testid {tid} in LotDetailPage"


def test_lot_detail_route_registered():
    src = read("frontend/src/App.js")
    assert "/lots/:auctionId/lot/:lotNumber" in src
    assert "LotDetailPage" in src


# ----- 5. Prev / Next lot navigation -----

def test_lot_detail_prev_next_and_keyboard_and_swipe():
    src = read("frontend/src/pages/LotDetailPage.jsx")
    # Prev / Next callbacks.
    assert "goToLot" in src
    # Keyboard: ArrowRight / ArrowLeft.
    assert "ArrowRight" in src and "ArrowLeft" in src
    # Swipe: onTouchStart / onTouchEnd.
    assert "onTouchStart" in src and "onTouchEnd" in src


# ----- 6. Scroll-restoration snapshot -----

def test_scroll_snapshot_written_and_consumed():
    card_src = read("frontend/src/components/CompactLotCard.jsx")
    parent_src = read("frontend/src/pages/MultiItemListingDetailPage.js")
    # Card writes a scrollY snapshot to sessionStorage before navigating.
    assert "sessionStorage.setItem" in card_src or "sessionStorage.setItem" in parent_src
    # Parent restores from the snapshot on mount and consumes it.
    assert "bidvex_grid_state" in parent_src
    assert "window.scrollTo" in parent_src
    assert "sessionStorage.removeItem" in parent_src


# ----- 7. Affiliate page correct 3 % / net platform profit / for life -----

def test_affiliate_page_wording_correct():
    src = read("frontend/src/pages/AffiliateProgramPage.jsx")
    # No "10%" mention anywhere.
    assert "10%" not in src
    # 3% mention + "net platform profit" wording.
    assert "3%" in src
    assert "net platform profit" in src
    # Lifetime attribution (no 12-month cutoff).
    assert "for life" in src.lower() or "à vie" in src
    assert "12 months" not in src  # old wording removed
    # Attribution cookie 30 days.
    assert "30 days" in src or "30 jours" in src


def test_affiliate_dashboard_has_period_metrics():
    src = read("frontend/src/pages/AffiliateDashboard.js")
    # iter368 — new mini-row above the existing 4 KPIs.
    assert 'data-testid="affiliate-period-metrics"' in src
    # keys are interpolated into `period-metric-${row.key}` in JSX, so we
    # verify the row keys themselves appear in the render array.
    for key in ["this-month", "last-month", "lifetime", "projected"]:
        assert f"key: '{key}'" in src, f"missing row key {key} in period metrics"


# ----- 8. Referrals table pending / approved / rejected -----

def test_referral_table_shows_three_statuses():
    src = read("frontend/src/pages/AffiliateDashboard.js")
    # Statuses covered in the render.
    assert "'approved'" in src
    assert "'rejected'" in src
    assert "'pending'" in src
    # Legacy "converted" alias still mapped so old data keeps rendering.
    assert "converted" in src
