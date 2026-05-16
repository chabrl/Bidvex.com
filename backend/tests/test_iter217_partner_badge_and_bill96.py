"""
iter217 — Tests for Phase 1: Partner Auction badge + fee logic + Bill 96 validator.

These tests lock the contract that:
  - Verified partners (status="verified") get badge_type="verified_firm" or
    "approved_partner" depending on their subscription / annual-fee state.
  - The listing-seller-enrichment helper correctly classifies sellers based
    on context (general lots vs vehicle vs storage).
  - The Quebec Bill 96 bilingual-title validator raises 422 on QC listings
    that lack a French title.
"""
from fastapi import HTTPException
import pytest

from services.partner_service import (
    is_verified_firm,
    get_badge_type,
    get_partner_tier,
)
from services.listing_seller_enrichment import (
    resolve_seller_account_type,
    enrich_listing_with_seller,
    _coerce_rate_to_fraction,
)
from services.qc_bilingual_validator import (
    assert_qc_bilingual_titles,
    _is_quebec_listing,
)


# ────────────────────────────────────────────────────────────────────────
# Bug 1 — Badge logic accepts "verified" canonical status
# ────────────────────────────────────────────────────────────────────────
class TestPartnerBadgeStatusAlias:
    def test_verified_status_unlocks_verified_firm(self):
        user = {
            "is_partner": True,
            "partner_verification_status": "verified",
            "partner_subscription_active": True,
        }
        assert is_verified_firm(user) is True
        assert get_badge_type(user) == "verified_firm"

    def test_legacy_approved_status_still_works(self):
        user = {
            "is_partner": True,
            "partner_verification_status": "approved",
            "platform_fee_paid": True,
        }
        assert is_verified_firm(user) is True
        assert get_badge_type(user) == "verified_firm"

    def test_verified_without_fee_paid_gives_approved_partner(self):
        user = {
            "is_partner": True,
            "partner_verification_status": "verified",
        }
        assert is_verified_firm(user) is False
        assert get_badge_type(user) == "approved_partner"

    def test_non_partner_gets_no_badge(self):
        assert get_badge_type({"is_partner": False}) is None
        assert get_badge_type({}) is None

    def test_vip_tier_upgrades_to_verified_vip(self):
        user = {
            "is_partner": True,
            "partner_verification_status": "verified",
            "platform_fee_paid": True,
            "subscription_tier": "vip_elite",
        }
        assert get_badge_type(user) == "verified_vip"
        assert get_partner_tier(user) == "vip"


# ────────────────────────────────────────────────────────────────────────
# Bug 1 — Seller account-type resolution scoped to listing context
# ────────────────────────────────────────────────────────────────────────
class TestSellerAccountResolution:
    def test_alex_boulanger_classifies_as_partner_on_general(self):
        # Alex is BOTH a verified partner AND a vehicle dealer. On a general
        # (lots/marketplace) listing he must surface as PARTNER, not vehicle
        # dealer, otherwise the listing is mis-badged as a vehicle auction.
        seller = {
            "is_partner": True,
            "partner_verification_status": "verified",
            "is_vehicle_dealer": True,
            "is_storage_facility": False,
        }
        assert resolve_seller_account_type(seller, "general") == "partner"

    def test_dealer_dominates_on_vehicle_surface(self):
        seller = {
            "is_partner": True,
            "partner_verification_status": "verified",
            "is_vehicle_dealer": True,
        }
        assert resolve_seller_account_type(seller, "vehicle") == "vehicle_dealer"

    def test_facility_dominates_on_storage_surface(self):
        seller = {
            "is_partner": True,
            "partner_verification_status": "verified",
            "is_storage_facility": True,
        }
        assert resolve_seller_account_type(seller, "storage") == "storage_facility"

    def test_unverified_partner_is_individual(self):
        seller = {"is_partner": True, "partner_verification_status": "pending"}
        assert resolve_seller_account_type(seller, "general") == "individual"

    def test_no_seller_yields_individual(self):
        assert resolve_seller_account_type({}, "general") == "individual"


# ────────────────────────────────────────────────────────────────────────
# Bug 1 — Listing enrichment surfaces canonical buyer_premium_rate
# ────────────────────────────────────────────────────────────────────────
class TestListingEnrichment:
    def test_partner_listing_carries_5pct_bp_as_fraction(self):
        # Alex's actual stored doc shape — premium_percentage=5.0 means 5%.
        listing = {
            "id": "L1",
            "seller_id": "alex",
            "premium_percentage": 5.0,
            "commission_rate": 4.0,
        }
        seller = {
            "is_partner": True,
            "partner_verification_status": "verified",
            "partner_company_name": "abc auction",
        }
        out = enrich_listing_with_seller(listing, seller, "general")
        assert out["seller_account_type"] == "partner"
        assert out["seller_is_partner"] is True
        assert out["seller_partner_company_name"] == "abc auction"
        assert out["buyer_premium_rate"] == 0.05
        assert out["seller_is_business"] is True

    def test_listing_with_explicit_buyer_premium_rate_wins(self):
        listing = {"id": "L1", "buyer_premium_rate": 0.15, "premium_percentage": 5.0}
        seller = {"is_partner": True, "partner_verification_status": "verified"}
        out = enrich_listing_with_seller(listing, seller, "general")
        assert out["buyer_premium_rate"] == 0.15

    def test_coerce_rate_handles_percent_and_fraction(self):
        assert _coerce_rate_to_fraction(15) == 0.15
        assert _coerce_rate_to_fraction(5.0) == 0.05
        assert _coerce_rate_to_fraction(0.15) == 0.15
        assert _coerce_rate_to_fraction(0.0) == 0.0
        assert _coerce_rate_to_fraction(None) is None
        assert _coerce_rate_to_fraction("foo") is None

    def test_individual_seller_yields_private_sale_classification(self):
        listing = {"id": "L1"}
        seller = {"is_partner": False}
        out = enrich_listing_with_seller(listing, seller, "general")
        assert out["seller_account_type"] == "individual"
        assert out["seller_is_partner"] is False
        assert out["seller_is_business"] is False


# ────────────────────────────────────────────────────────────────────────
# Bug 2 — Quebec Bill 96 bilingual-title validator
# ────────────────────────────────────────────────────────────────────────
class TestQuebecBill96Validator:
    def test_qc_region_is_detected(self):
        assert _is_quebec_listing("QC", None) is True
        assert _is_quebec_listing("quebec", None) is True
        assert _is_quebec_listing("ON", None) is False

    def test_qc_city_fallback_works_when_region_blank(self):
        assert _is_quebec_listing("", "Sherbrooke") is True
        assert _is_quebec_listing(None, "Montréal") is True
        assert _is_quebec_listing("", "Toronto") is False

    def test_qc_listing_missing_fr_title_raises_422(self):
        with pytest.raises(HTTPException) as exc:
            assert_qc_bilingual_titles(
                title="Leather couch", title_fr=None,
                description="Nice", description_fr=None,
                region="QC", city="Sherbrooke",
                content_language="en",
            )
        assert exc.value.status_code == 422
        assert exc.value.detail["error"] == "qc_french_title_required"
        assert "Loi 96" in exc.value.detail["message_fr"]

    def test_qc_listing_with_fr_title_but_missing_fr_description(self):
        with pytest.raises(HTTPException) as exc:
            assert_qc_bilingual_titles(
                title="Leather couch", title_fr="Canapé en cuir",
                description="Nice and clean", description_fr=None,
                region="QC", content_language="en",
            )
        assert exc.value.status_code == 422
        assert exc.value.detail["error"] == "qc_french_description_required"

    def test_qc_listing_fully_bilingual_passes(self):
        # Should not raise.
        assert_qc_bilingual_titles(
            title="Leather couch", title_fr="Canapé en cuir",
            description="Nice and clean", description_fr="Propre",
            region="QC", content_language="en",
        )

    def test_non_qc_listing_does_not_require_french(self):
        # Toronto seller in English — no FR required.
        assert_qc_bilingual_titles(
            title="Leather couch", title_fr=None,
            description="Nice", description_fr=None,
            region="ON", city="Toronto", content_language="en",
        )

    def test_qc_listing_typed_in_french_with_title_only_passes(self):
        # Seller typed in FR — `title` IS the French copy.
        assert_qc_bilingual_titles(
            title="Canapé en cuir", title_fr=None,
            description="Propre", description_fr=None,
            region="QC", content_language="fr",
        )
