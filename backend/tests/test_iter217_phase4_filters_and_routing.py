"""
iter217 Phase 4 — Tests for the 4 critical production regressions:
  Bug 1  Filters broken on /marketplace + /lots + /storage + /vehicle pages
  Bug 2  Marketplace cards rendered partner listings as "Vente privée"
  Bug 3  Homepage Pro Auctions section emoji + card layout
  Bug 4  Notifications routing fallbacks
"""
import inspect
import pathlib
import pytest

from routes.marketplace import (
    get_marketplace_items,
    _normalize_region,
    _normalize_city,
)


# ────────────────────────────────────────────────────────────────────────
# Bug 1 — Marketplace filters wired into the API
# ────────────────────────────────────────────────────────────────────────
class TestMarketplaceFilterParams:
    def test_endpoint_accepts_phase4_pill_filters(self):
        sig = inspect.signature(get_marketplace_items)
        params = sig.parameters
        # Phase 4 new filters
        assert "private_sales_only" in params
        assert "partner_only" in params
        assert "lots_auction_only" in params
        # Phase 2 normalizer-backed filters (still present)
        assert "province" in params
        assert "region" in params
        assert "city" in params
        assert "tax_status" in params

    def test_no_taxes_filter_uses_account_type(self):
        # Source must filter on the enriched `seller_account_type` field
        # rather than the legacy `seller_is_business`. This is the bug fix.
        src = inspect.getsource(get_marketplace_items)
        assert "no_taxes" in src
        # The replacement uses `seller_account_type == "individual"`
        assert 'seller_account_type") == "individual"' in src

    def test_tax_status_partner_filter_uses_account_type(self):
        src = inspect.getsource(get_marketplace_items)
        assert 'tax_status == "partner"' in src
        # No more legacy `seller_type == "partner"` or `is_partner_listing` filter logic
        legacy_bad = 'i.get("seller_type") == "partner"'
        assert legacy_bad not in src


class TestProvinceNormalizerStillWorks:
    def test_quebec_full_name_collapses_to_qc(self):
        assert _normalize_region("Quebec") == "qc"
        assert _normalize_region("Québec") == "qc"
        assert _normalize_region("QC") == "qc"
        assert _normalize_region("qc") == "qc"

    def test_alberta(self):
        assert _normalize_region("AB") == "ab"
        assert _normalize_region("Alberta") == "ab"

    def test_city_accents(self):
        assert _normalize_city("Montréal") == "montreal"
        assert _normalize_city("Trois-Rivières") == "trois-rivieres"


# ────────────────────────────────────────────────────────────────────────
# Bug 2 — Marketplace cards: enrichment on cached items
# ────────────────────────────────────────────────────────────────────────
class TestMarketplaceCacheEnrichment:
    def test_build_marketplace_items_uses_enrichment_helpers(self):
        # The cache builder must use the iter217 enrichment helpers so
        # every cached item carries seller_account_type + buyer_premium_rate.
        from routes.marketplace import _build_marketplace_items
        src = inspect.getsource(_build_marketplace_items)
        assert "resolve_seller_account_type" in src
        assert "_coerce_rate_to_fraction" in src
        assert '"seller_account_type"' in src
        assert '"seller_is_partner"' in src
        assert '"seller_partner_company_name"' in src
        assert '"buyer_premium_rate"' in src

    def test_full_seller_doc_fetched_not_just_tax_flag(self):
        # The previous code only fetched is_tax_registered. The new code
        # MUST fetch is_partner, partner_verification_status, etc.
        from routes.marketplace import _build_marketplace_items
        src = inspect.getsource(_build_marketplace_items)
        assert '"is_partner": 1' in src
        assert '"partner_verification_status": 1' in src
        assert '"is_vehicle_dealer": 1' in src
        assert '"is_storage_facility": 1' in src


# ────────────────────────────────────────────────────────────────────────
# Bug 3 — Homepage Pro Auctions: emoji + ghost cards + capitalized name
# ────────────────────────────────────────────────────────────────────────
class TestProAuctionsHomepage:
    def test_pro_auctions_uses_svg_not_emoji(self):
        comp = pathlib.Path("/app/frontend/src/components/ProfessionalAuctionsPromo.jsx").read_text(encoding="utf-8")
        # The 🔨 emoji must NOT appear in the heading area
        # (only allowed inside translation values that the i18n layer renders).
        # Check the heading area specifically — the SVG must be present.
        assert "<svg" in comp
        assert 'pro-auctions-gavel-icon' in comp
        # And the inline `🔨 {t(...)}` pattern is gone
        assert "🔨 {t(" not in comp

    def test_pro_auctions_ghost_card_renders(self):
        comp = pathlib.Path("/app/frontend/src/components/ProfessionalAuctionsPromo.jsx").read_text(encoding="utf-8")
        assert "pro-auction-ghost-card" in comp
        assert "moreSoon" in comp
        assert "beFirst" in comp

    def test_pro_auctions_browse_lots_is_solid_blue_btn(self):
        comp = pathlib.Path("/app/frontend/src/components/ProfessionalAuctionsPromo.jsx").read_text(encoding="utf-8")
        assert "pro-auction-browse-lots-btn" in comp
        # Solid blue background (#2563eb) on the CTA
        assert "#2563eb" in comp

    def test_pro_auctions_company_capitalize_css(self):
        comp = pathlib.Path("/app/frontend/src/components/ProfessionalAuctionsPromo.jsx").read_text(encoding="utf-8")
        # The company-name <p> must have textTransform: 'capitalize' so
        # 'abc auction' renders as 'Abc Auction'.
        assert "textTransform: 'capitalize'" in comp


# ────────────────────────────────────────────────────────────────────────
# Bug 4 — Notifications: guaranteed navigation + /notifications page
# ────────────────────────────────────────────────────────────────────────
class TestNotificationsRouting:
    def test_notification_center_default_falls_back_to_notifications_page(self):
        comp = pathlib.Path("/app/frontend/src/components/NotificationCenter.js").read_text(encoding="utf-8")
        # The default branch must end with a navigate('/notifications') call.
        assert "navigate('/notifications')" in comp

    def test_notifications_page_exists_and_routes(self):
        page = pathlib.Path("/app/frontend/src/pages/NotificationsPage.jsx")
        assert page.exists()
        body = page.read_text(encoding="utf-8")
        assert "mark-all-read" in body
        assert "notification-row" in body
        assert "mark-all-read-btn" in body

    def test_app_js_wires_notifications_route(self):
        app_js = pathlib.Path("/app/frontend/src/App.js").read_text(encoding="utf-8")
        assert 'NotificationsPage' in app_js
        assert '"/notifications"' in app_js


# ────────────────────────────────────────────────────────────────────────
# Marketplace sidebar: "No locations yet" empty state removed
# ────────────────────────────────────────────────────────────────────────
class TestMarketplaceSidebarLocation:
    def test_no_locations_yet_text_gated_behind_data(self):
        sidebar = pathlib.Path("/app/frontend/src/components/MarketplaceSidebar.js").read_text(encoding="utf-8")
        # The entire location block must be conditional on locations.length > 0
        # so the "No locations yet" placeholder never appears.
        assert "filterData.locations.length > 0" in sidebar
        assert "noLocations" not in sidebar  # placeholder removed


# ────────────────────────────────────────────────────────────────────────
# FlattenedMarketplace card uses SellerAccountBadge
# ────────────────────────────────────────────────────────────────────────
class TestMarketplaceCardBadge:
    def test_flattened_marketplace_uses_seller_account_badge(self):
        comp = pathlib.Path("/app/frontend/src/components/FlattenedMarketplace.js").read_text(encoding="utf-8")
        assert "SellerAccountBadge" in comp
        # The legacy `isPrivateSale = !item.seller_is_business` is replaced
        # with the account-type based derivation.
        assert "seller_account_type" in comp

    def test_flattened_marketplace_hides_save_15_for_partners(self):
        comp = pathlib.Path("/app/frontend/src/components/FlattenedMarketplace.js").read_text(encoding="utf-8")
        # The "Save 15%" banner must be gated on isPrivateSale (which is
        # only true for account_type === 'individual').
        # Source check — the partner BP hint block must exist too.
        assert "partnerBpHint" in comp
        assert "isPartner" in comp
