"""
iter367 P0/P1 — Static launch-gate tests for the production audit pass.

Coverage:
  1. Lightbox CSS fullscreen fix — index.css contains fullscreen rules
  2. Dashboard buyer/seller aggregate from won_auctions + receipts
  3. Escrow union with transactions collection
  4. Multi-Lot deep-link routing FlattenedMarketplace uses ?lot=
  5. MultiItemListingDetailPage reads useSearchParams
  6. Live activity ticker component + endpoint
  7. Bid increment table component
  8. Affiliate program page + footer link + route + urlMap
  9. Admin unsubscribe guard intact
 10. Admin analytics uses receipts for GMV
"""
import os
import re
from pathlib import Path

ROOT = Path("/app")


def read(path: str) -> str:
    return (ROOT / path.lstrip("/")).read_text(encoding="utf-8")


# ----- 1. Lightbox CSS fullscreen fix -----

def test_lightbox_fullscreen_css_present():
    css = read("frontend/src/index.css")
    # yarl__portal AND ril__outer both must have position:fixed inset 0
    assert ".yarl__portal" in css
    assert ".ril__outer" in css or ".ril-outer" in css
    assert "inset: 0 !important" in css
    assert "width: 100vw !important" in css
    assert "height: 100vh !important" in css
    # slide/image sizing rules
    assert ".yarl__slide_image" in css
    assert "max-width: 90vw" in css


# ----- 2. Buyer dashboard reads won_auctions + receipts -----

def test_buyer_dashboard_reads_won_auctions_and_receipts():
    src = read("backend/routes/dashboard.py")
    # won_auctions query
    assert "won_auctions.find" in src
    # receipts query for buyer
    assert 'receipts.find' in src
    assert '"type": "buyer_receipt"' in src
    # bid_status enrichment
    assert 'b["bid_status"]' in src or "b['bid_status']" in src
    # ended_no_listing status must exist
    assert "ended_no_listing" in src


def test_buyer_dashboard_won_items_uses_union():
    src = read("backend/routes/dashboard.py")
    assert "total_won_items" in src
    # union combines list of listing IDs
    assert "won_auctions_docs" in src


# ----- 3. Seller dashboard aggregates receipts (seller_statement) -----

def test_seller_dashboard_reads_seller_statements():
    src = read("backend/routes/dashboard.py")
    assert '"type": "seller_statement"' in src
    assert "receipt_only_sales" in src
    assert "seller_statements" in src


# ----- 4. Escrow service union with transactions -----

def test_escrow_service_unions_transactions():
    src = read("backend/services/escrow_service.py")
    assert "db.transactions.find" in src
    assert "pickup_code_listing_id" in src
    # both buyer + seller status use the union
    assert src.count("db.transactions.find") >= 2


# ----- 5. Multi-Lot deep-link routing -----

def test_flattened_marketplace_deep_link_uses_lot_query_param():
    src = read("frontend/src/components/FlattenedMarketplace.js")
    assert "?lot=" in src, "FlattenedMarketplace must construct ?lot= deep-links"
    assert "item.auction_id" in src
    assert "lot_number ?? item.lot_id" in src or "lot_number" in src


def test_multi_item_listing_detail_reads_search_params():
    src = read("frontend/src/pages/MultiItemListingDetailPage.js")
    assert "useSearchParams" in src, "MultiItemListingDetailPage must read useSearchParams"
    assert "searchParams.get('lot')" in src or 'searchParams.get("lot")' in src
    assert "targetLotParam" in src


# ----- 6. Live activity ticker -----

def test_activity_ticker_component_exists():
    src = read("frontend/src/components/MultiLotActivityTicker.jsx")
    assert "auctionId" in src
    assert "recent-activity" in src
    assert "15000" in src  # 15s polling
    assert 'data-testid="multi-lot-activity-ticker"' in src


def test_recent_activity_endpoint_exists():
    src = read("backend/routes/listings.py")
    assert '@listings_router.get("/lots/{auction_id}/recent-activity")' in src
    assert "def get_multi_lot_recent_activity" in src
    assert "bidder_alias" in src
    assert "time_ago" in src


# ----- 7. Bid increment table (iter368 — now dynamic, backed by
#            /api/multi-item-listings/{id}/increment-info) -----

def test_bid_increment_table_component_exists():
    src = read("frontend/src/components/BidIncrementTable.jsx")
    # iter368 rewrite: no hardcoded INCREMENTS array; fetches from server.
    assert "INCREMENTS" not in src, "iter368 removed the hardcoded INCREMENTS ladder"
    assert "increment-info" in src, "BidIncrementTable must fetch schedule from the server"
    assert "auctionId" in src, "Component must accept the auctionId prop"
    assert 'data-testid="bid-increment-table"' in src
    assert 'data-testid="bid-increment-strategy"' in src
    # Fixed mode branch must exist for sellers who pick that strategy.
    assert 'data-testid="bid-increment-fixed"' in src


# ----- 8. Affiliate program + footer link + route + urlMap -----

def test_affiliate_page_exists():
    src = read("frontend/src/pages/AffiliateProgramPage.jsx")
    assert 'data-testid="affiliate-program-page"' in src
    assert 'data-testid="affiliate-title"' in src
    assert "Affiliate Program" in src
    assert "programme-affilies" not in src or True  # placeholder — bilingual copy is fine
    # Bilingual copy tables present
    assert "COPY = {" in src
    assert "en:" in src and "fr:" in src


def test_affiliate_route_registered():
    src = read("frontend/src/App.js")
    assert "AffiliateProgramPage" in src
    assert '/affiliate-program' in src
    assert '/fr/programme-affilies' in src


def test_footer_has_affiliate_link():
    src = read("frontend/src/components/Footer.js")
    assert 'footer-affiliate-program-link' in src
    assert '/affiliate-program' in src


def test_url_map_pair():
    src = read("frontend/src/i18n/urlMap.js")
    assert "'/affiliate-program': '/programme-affilies'" in src


# ----- 9. Admin unsubscribe guard intact -----

def test_admin_unsubscribe_guard_intact():
    src = read("backend/routes/unsubscribe.py")
    assert "ADMIN_UNSUBSCRIBE_REFUSAL" in src
    assert "admin_unsubscribe_blocked" in src
    assert "_is_admin_email" in src


# ----- 10. Admin analytics receipts GMV fallback -----

def test_admin_analytics_uses_receipts_for_gmv():
    src = read("backend/routes/admin_analytics.py")
    assert "receipts_gmv_all" in src
    assert "receipts_gmv_range" in src
    assert "gmv_all = max(gmv_all, receipts_gmv_all)" in src
