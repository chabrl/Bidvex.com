"""
iter283 — Final pre-launch fix suite.

Pins six missions:
  M1: Storage listing visibility (UNIT 205 bug)
  M2: Correct seller badge on storage listings (no "Vehicle Dealer" for
      multi-flagged sellers)
  M3: Vehicle listing form does not crash on submit errors
  M4: Universal dual-visibility (marketplace + section page)
  M5: Section-default deposit rules
  M6: Test-listing seed integrity
"""
from __future__ import annotations

import os
import re
import pytest


# ── M1 / M4 — Storage section query + universal marketplace ──


def test_iter283_storage_query_accepts_all_aliases():
    """`/api/storage-auctions` MUST match every storage alias so a
    listing created under any of the aliases shows up in the storage
    section. UNIT 205 bug."""
    from services.listing_sections import section_query_filter, STORAGE_TYPES
    q = section_query_filter("storage")
    aliases = q["listing_type"]["$in"]
    for required in ("storage_auction", "storage", "storage_locker",
                     "unit", "unit_auction"):
        assert required in aliases, f"missing storage alias {required!r}"
    assert set(aliases) == set(STORAGE_TYPES)


def test_iter283_marketplace_query_is_universal():
    """Per Mission 4: marketplace returns ALL active listings. No
    listing_type filter (the spec literally says: "Marketplace shows
    everything")."""
    from services.listing_sections import section_query_filter
    assert section_query_filter("marketplace") == {}


def test_iter283_section_inference_storage_by_category():
    """Storage category WITHOUT listing_type → infers section=storage.
    Closes the UNIT 205 bug at creation time."""
    from services.listing_sections import infer_section, infer_seller_context
    assert infer_section({"category": "Storage"}) == "storage"
    assert infer_section({"category": "storage"}) == "storage"
    assert infer_seller_context({"category": "Storage"}) == "storage"


def test_iter283_section_inference_vehicle_by_category():
    from services.listing_sections import infer_section, infer_seller_context
    assert infer_section({"category": "Vehicles"}) == "vehicles"
    assert infer_seller_context({"category": "Vehicles"}) == "vehicle"


def test_iter283_section_inference_listing_type_wins_over_category():
    """If a listing has an explicit listing_type, that wins over
    category guesswork."""
    from services.listing_sections import infer_section
    assert infer_section({
        "listing_type": "storage_locker",
        "category": "Vehicles",
    }) == "storage"


def test_iter283_quantity_heuristic_falls_back_to_lots():
    """Multi-quantity listings with no listing_type → lots."""
    from services.listing_sections import infer_section
    assert infer_section({"quantity": 10, "category": "Tools"}) == "lots"
    assert infer_section({"quantity": 1, "category": "Tools"}) == "marketplace"


# ── M2 — Seller badge context inferred per LISTING (not per SELLER) ──


def test_iter283_context_storage_listing_uses_storage_context():
    """A storage listing from a multi-flagged seller (admin who is
    is_vehicle_dealer AND is_storage_facility) MUST use storage
    context so the right badge renders."""
    from services.listing_sections import infer_seller_context
    storage_listing = {
        "listing_type": "storage_locker",
        "category": "Storage",
    }
    assert infer_seller_context(storage_listing) == "storage"


def test_iter283_listing_detail_uses_inferred_context():
    """The single-listing GET endpoint MUST infer the seller context
    per-listing (iter283 fix) rather than passing the static "general"
    context that caused the Vehicle Dealer badge bug."""
    src = open("/app/backend/routes/listings.py").read()
    # The static "general" call was removed.
    assert "enrich_listing_with_seller(listing_doc, seller, \"general\")" not in src
    # Replaced by per-listing inference.
    assert "infer_seller_context(listing_doc)" in src


# ── M3 — Vehicle listing crash-proof submit ──


def test_iter283_vehicle_form_has_error_boundary():
    """`/vehicle-auctions/create` MUST be wrapped in an ErrorBoundary
    so a render-time crash doesn't show a blank white page."""
    app_src = open("/app/frontend/src/App.js").read()
    # Locate the route element and assert the ErrorBoundary wrap.
    idx = app_src.find('/vehicle-auctions/create')
    assert idx > 0
    block = app_src[idx:idx + 600]
    assert 'ErrorBoundary' in block
    assert 'scope="vehicle-listing-create"' in block


def test_iter283_vehicle_submit_coerces_dict_detail_to_string():
    """`toast.error()` MUST receive a string. The submit handler now
    coerces dict-shaped backend errors (e.g. { detail: { error,
    message_en, message_fr } }) before passing them to toast."""
    src = open("/app/frontend/src/pages/vehicles/CreateVehicleListingPage.js").read()
    # Defensive coercion present in BOTH catch blocks.
    assert src.count("typeof _detail === 'string'") >= 2
    assert src.count("_detail.message_en") >= 2
    # 403 broker-required friendly message.
    assert 'broker partnership' in src.lower()


def test_iter283_vehicle_submit_wraps_photo_uploads():
    """One failing photo MUST NOT abort the whole submit. Each upload
    is wrapped in try/catch and the loop continues."""
    src = open("/app/frontend/src/pages/vehicles/CreateVehicleListingPage.js").read()
    assert "_photo_fail" in src
    assert "photo upload failed" in src.lower()


# ── M5 — Section-default deposit rules ──


def test_iter283_deposit_marketplace_is_zero():
    from routes.bidder_deposits import _calc_deposit_amount
    listing = {"listing_type": "marketplace", "starting_price": 150}
    assert _calc_deposit_amount(listing) == 0.0


def test_iter283_deposit_storage_is_50_flat():
    """Storage listings ALWAYS require a $50 flat deposit per spec."""
    from routes.bidder_deposits import _calc_deposit_amount
    listing = {"listing_type": "storage_locker", "starting_price": 1.0}
    assert _calc_deposit_amount(listing) == 50.0


def test_iter283_deposit_vehicle_floor_200():
    """Vehicle deposit = max($200, 10% of starting_price)."""
    from routes.bidder_deposits import _calc_deposit_amount
    low = {"listing_type": "vehicle_auction", "starting_price": 1000.0}
    assert _calc_deposit_amount(low) == 200.0
    high = {"listing_type": "vehicle_auction", "starting_price": 5000.0}
    assert _calc_deposit_amount(high) == 500.0


def test_iter283_deposit_lots_threshold_500():
    """Lot deposit fires ONLY when starting_price > $500 AND
    requires_deposit=True; 10% with $50 floor."""
    from routes.bidder_deposits import _calc_deposit_amount
    below = {"listing_type": "lot_auction", "starting_price": 50.0,
             "requires_deposit": True}
    assert _calc_deposit_amount(below) == 0.0
    above = {"listing_type": "lot_auction", "starting_price": 1000.0,
             "requires_deposit": True}
    assert _calc_deposit_amount(above) == 100.0  # 10% of 1000


# ── M6 — Seed integrity ──


def test_iter283_seed_script_has_all_four_sections():
    src = open("/app/backend/scripts/iter283_seed_test_listings.py").read()
    for ident in ("iter283-test-marketplace", "iter283-test-lot",
                  "iter283-test-storage", "iter283-test-vehicle"):
        assert ident in src, f"missing seed id {ident}"
    # All seeds include the required `current_price` field
    # (regression: missing it caused /api/listings to 500).
    assert src.count('"current_price"') >= 4


# ── Frontend cross-link banners (M4.5) ──


def test_iter283_storage_page_links_to_marketplace():
    src = open("/app/frontend/src/pages/storage/StorageAuctionsBrowse.js").read()
    assert 'data-testid="storage-marketplace-crosslink"' in src
    assert 'to="/marketplace"' in src


def test_iter283_lots_page_links_to_marketplace():
    src = open("/app/frontend/src/pages/LotsMarketplacePage.js").read()
    assert 'data-testid="lots-marketplace-crosslink"' in src
    assert 'to="/marketplace"' in src


# ── Section badge on marketplace cards (M4.4) ──


def test_iter283_marketplace_card_has_section_badges():
    src = open("/app/frontend/src/components/FlattenedMarketplace.js").read()
    assert 'data-testid="section-badge-storage"' in src
    assert 'data-testid="section-badge-vehicles"' in src
    assert 'data-testid="section-badge-lots"' in src
    # Warehouse + Car icons imported for the new badges.
    assert "Warehouse," in src and "Car" in src


# ── Listing detail seller-info card surfaces website + company (M2) ──


def test_iter283_listing_detail_shows_seller_company_and_website():
    src = open("/app/frontend/src/pages/ListingDetailPage.js").read()
    assert 'seller_company_name' in src
    assert 'seller_website' in src
    assert 'data-testid="seller-public-info"' in src
    assert 'rel="noopener noreferrer"' in src


def test_iter283_profile_route_accepts_website_field():
    """Profile PUT MUST allow the seller to set their website. iter283
    added `website` to allowed_fields and sanitized the URL."""
    src = open("/app/backend/routes/profiles.py").read()
    # Allowed-fields whitelist contains website.
    assert '"website",' in src
    # XSS guard rejects dangerous schemes.
    assert 'javascript:' in src and 'vbscript:' in src
