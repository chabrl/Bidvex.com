"""
iter292 — Vehicle-dealer cross-section bleed regression.

Bug: A licensed vehicle dealer (or storage facility) listing a non-vehicle /
non-storage item (Marketplace, Lots) was getting the "Vehicle Dealer Auction
— Full taxes on hammer price" badge AND the vehicle-specific fee block on
the listing detail page. The condition incorrectly keyed on the SELLER's
role rather than the LISTING's collection.

Fix: `resolve_seller_account_type` now only stamps `vehicle_dealer` /
`storage_facility` when the listing's CONTEXT is the corresponding section.
Marketplace / Lots context falls through partner > individual; the
listing's `seller_is_business` flag carries the dealer's tax-registered
status so the standard (non-private-sale) tax UI still applies.

Constraints honoured:
- Vehicle context still resolves to `vehicle_dealer` when the seller IS a dealer.
- Storage context still resolves to `storage_facility` when the seller IS a facility.
- Partner verification still dominates in all contexts.
- No fee math touched — only display-layer classification.
"""
import pytest

from services.listing_seller_enrichment import (
    resolve_seller_account_type,
    enrich_listing_with_seller,
)


VEHICLE_DEALER_SELLER = {
    "id": "seller-dealer-1",
    "is_vehicle_dealer": True,
    "is_tax_registered": True,
    "is_partner": False,
}

STORAGE_FACILITY_SELLER = {
    "id": "seller-facility-1",
    "is_storage_facility": True,
    "account_type": "storage_facility",
    "is_tax_registered": True,
    "is_partner": False,
}

PARTNER_SELLER = {
    "id": "seller-partner-1",
    "is_partner": True,
    "partner_verification_status": "verified",
    "partner_company_name": "Acme Auction House",
    "is_tax_registered": True,
}

INDIVIDUAL_SELLER = {
    "id": "seller-individual-1",
    "is_partner": False,
    "is_vehicle_dealer": False,
    "is_storage_facility": False,
    "is_tax_registered": False,
}


# ── Cross-section bleed gone ─────────────────────────────────────────


def test_vehicle_dealer_listing_marketplace_item_is_not_vehicle_dealer():
    """The original bug: a dealer listing a table on Marketplace was
    getting the Vehicle Dealer Auction badge. Must now resolve to
    individual (the dealer is a regular seller in this context)."""
    assert resolve_seller_account_type(VEHICLE_DEALER_SELLER, "general") == "individual"
    assert resolve_seller_account_type(VEHICLE_DEALER_SELLER, "marketplace") == "individual"
    assert resolve_seller_account_type(VEHICLE_DEALER_SELLER, "lots") == "individual"


def test_storage_facility_listing_lots_item_is_not_storage_facility():
    """A storage facility running a Lots auction shouldn't be flagged
    as a Storage Facility Auction — it's just a Lots auction."""
    assert resolve_seller_account_type(STORAGE_FACILITY_SELLER, "general") == "individual"
    assert resolve_seller_account_type(STORAGE_FACILITY_SELLER, "lots") == "individual"
    assert resolve_seller_account_type(STORAGE_FACILITY_SELLER, "marketplace") == "individual"


# ── In-section behaviour unchanged ───────────────────────────────────


def test_vehicle_context_still_resolves_dealer_to_vehicle_dealer():
    """Within the vehicle listings surface, a dealer IS a Vehicle Dealer Auction."""
    assert resolve_seller_account_type(VEHICLE_DEALER_SELLER, "vehicle") == "vehicle_dealer"


def test_storage_context_still_resolves_facility_to_storage_facility():
    """Within the storage auctions surface, a facility IS a Storage Auction."""
    assert resolve_seller_account_type(STORAGE_FACILITY_SELLER, "storage") == "storage_facility"


def test_partner_dominates_in_every_context():
    """A verified partner is always a Partner Auction regardless of section."""
    for ctx in ("general", "marketplace", "lots", "vehicle", "storage"):
        assert resolve_seller_account_type(PARTNER_SELLER, ctx) == "partner"


def test_individual_seller_resolves_to_individual_in_all_contexts():
    for ctx in ("general", "marketplace", "lots", "vehicle", "storage"):
        assert resolve_seller_account_type(INDIVIDUAL_SELLER, ctx) == "individual"


# ── enrich_listing_with_seller field shape ───────────────────────────


def test_enrichment_clears_vehicle_dealer_flag_for_marketplace_listing():
    """The frontend reads `seller_is_vehicle_dealer` to render the vehicle
    badge. After the fix this MUST be False on a dealer's Marketplace
    listing."""
    listing = {"id": "l-1", "title": "Used table", "seller_id": "seller-dealer-1"}
    enriched = enrich_listing_with_seller(listing, VEHICLE_DEALER_SELLER, "general")
    assert enriched["seller_account_type"] == "individual"
    assert enriched["seller_is_vehicle_dealer"] is False
    assert enriched["seller_is_storage_facility"] is False
    assert enriched["seller_is_partner"] is False
    # Tax-registered dealer is still a business seller (no Private Sale
    # tax savings) — only the vehicle-specific badge + fee block goes
    # away. iter292: directive 1.
    assert enriched["seller_is_business"] is True


def test_enrichment_keeps_vehicle_dealer_flag_inside_vehicle_context():
    """Inside the Vehicle Auctions surface, the flag stays on."""
    listing = {"id": "v-1", "title": "2020 Ford F-350", "seller_id": "seller-dealer-1"}
    enriched = enrich_listing_with_seller(listing, VEHICLE_DEALER_SELLER, "vehicle")
    assert enriched["seller_account_type"] == "vehicle_dealer"
    assert enriched["seller_is_vehicle_dealer"] is True


def test_enrichment_clears_storage_facility_flag_for_lots_listing():
    listing = {"id": "lot-1", "title": "Misc lot", "seller_id": "seller-facility-1"}
    enriched = enrich_listing_with_seller(listing, STORAGE_FACILITY_SELLER, "lots")
    assert enriched["seller_account_type"] == "individual"
    assert enriched["seller_is_storage_facility"] is False
    assert enriched["seller_is_business"] is True
