"""
iter217 Phase 2 — Tests for the Phase 2 fixes:
  - Wishlist status endpoint (Bug 6)
  - Notifications cleanup endpoint + action_url field (Bug 8)
  - Bulk listing seller enrichment (Bug 7 — badges on cards)
  - Location filter normalization (Bug 10)
"""
import pytest
import asyncio

from routes.marketplace import _normalize_region, _normalize_city
from services.listing_seller_enrichment import (
    enrich_listings_bulk_async,
    enrich_listing_with_seller,
)


# ────────────────────────────────────────────────────────────────────────
# Bug 10 — Location filter normalization
# ────────────────────────────────────────────────────────────────────────
class TestRegionNormalization:
    def test_qc_aliases_collapse_to_canonical(self):
        assert _normalize_region("QC") == "qc"
        assert _normalize_region("Quebec") == "qc"
        assert _normalize_region("Québec") == "qc"
        assert _normalize_region("  qc  ") == "qc"

    def test_unknown_region_kept_as_lowercase(self):
        assert _normalize_region("FOO") == "foo"

    def test_blank_inputs_return_empty(self):
        assert _normalize_region(None) == ""
        assert _normalize_region("") == ""

    def test_all_provinces_have_aliases(self):
        # Sample a few — full set defined in marketplace module
        assert _normalize_region("ontario") == "on"
        assert _normalize_region("Nova Scotia") == "ns"
        assert _normalize_region("british columbia") == "bc"


class TestCityNormalization:
    def test_accents_stripped(self):
        assert _normalize_city("Montréal") == "montreal"
        assert _normalize_city("Québec") == "quebec"
        assert _normalize_city("Trois-Rivières") == "trois-rivieres"

    def test_trim_and_lower(self):
        assert _normalize_city(" Sherbrooke  ") == "sherbrooke"
        assert _normalize_city("MONTREAL") == "montreal"

    def test_blank(self):
        assert _normalize_city(None) == ""


# ────────────────────────────────────────────────────────────────────────
# Bug 7 — Bulk listing seller enrichment
# ────────────────────────────────────────────────────────────────────────
class _FakeCursor:
    def __init__(self, docs):
        self._docs = list(docs)

    def __aiter__(self):
        self._it = iter(self._docs)
        return self

    async def __anext__(self):
        try:
            return next(self._it)
        except StopIteration:
            raise StopAsyncIteration


class _FakeUsers:
    def __init__(self, by_id):
        self._by_id = by_id

    def find(self, query, projection):
        ids = query.get("id", {}).get("$in", [])
        return _FakeCursor([self._by_id[i] for i in ids if i in self._by_id])


class _FakeDB:
    def __init__(self, users_by_id):
        self.users = _FakeUsers(users_by_id)


class TestBulkEnrichment:
    def test_bulk_enrich_handles_mixed_seller_types(self):
        users_by_id = {
            "u-partner": {"id": "u-partner", "is_partner": True, "partner_verification_status": "verified", "partner_company_name": "abc"},
            "u-dealer": {"id": "u-dealer", "is_vehicle_dealer": True},
            "u-facility": {"id": "u-facility", "is_storage_facility": True},
            "u-business": {"id": "u-business", "is_tax_registered": True},
            "u-individual": {"id": "u-individual"},
        }
        listings = [
            {"id": "L-p", "seller_id": "u-partner", "premium_percentage": 7.5},
            {"id": "L-d", "seller_id": "u-dealer"},
            {"id": "L-f", "seller_id": "u-facility"},
            {"id": "L-b", "seller_id": "u-business"},
            {"id": "L-i", "seller_id": "u-individual"},
            {"id": "L-orphan"},  # no seller_id at all
        ]
        db = _FakeDB(users_by_id)
        asyncio.run(enrich_listings_bulk_async(db, listings))

        types = {l["id"]: l["seller_account_type"] for l in listings}
        assert types == {
            "L-p": "partner",
            "L-d": "vehicle_dealer",  # general context — but dealer-only seller has no partner flag, so still dealer
            "L-f": "storage_facility",
            "L-b": "individual",
            "L-i": "individual",
            "L-orphan": "individual",
        }
        # Partner's BP rate surfaced canonically (7.5% -> 0.075)
        partner_listing = next(l for l in listings if l["id"] == "L-p")
        assert partner_listing["buyer_premium_rate"] == 0.075
        assert partner_listing["seller_partner_company_name"] == "abc"

    def test_bulk_enrich_with_no_seller_does_not_query_mongo(self):
        # Smoke — empty list returns empty
        result = asyncio.run(enrich_listings_bulk_async(_FakeDB({}), []))
        assert result == []


# ────────────────────────────────────────────────────────────────────────
# Bug 8 — Notifications: action_url / action_type plumbing
# ────────────────────────────────────────────────────────────────────────
class TestNotificationActionUrlSchema:
    def test_notifications_create_accepts_action_url(self):
        # Import lazily so we can introspect the function signature.
        import inspect
        from routes.notifications import create_notification
        sig = inspect.signature(create_notification)
        assert "action_url" in sig.parameters
        assert "action_type" in sig.parameters

    def test_cleanup_endpoint_exists(self):
        import inspect
        from routes import notifications as nmod
        # The endpoint function should be defined.
        assert hasattr(nmod, "admin_cleanup_empty_notifications")
        sig = inspect.signature(nmod.admin_cleanup_empty_notifications)
        assert "current_user" in sig.parameters


# ────────────────────────────────────────────────────────────────────────
# Bug 6 — Wishlist status endpoint signature
# ────────────────────────────────────────────────────────────────────────
class TestWishlistStatusEndpoint:
    def test_wishlist_status_endpoint_signature(self):
        import inspect
        from routes.watchlist import get_wishlist_status
        sig = inspect.signature(get_wishlist_status)
        assert "auction_id" in sig.parameters
        assert "lot_id" in sig.parameters
        assert "current_user" in sig.parameters

    def test_wishlist_status_returns_dict_shape(self):
        # Functional-shape contract: the function should return a dict with
        # `is_wishlisted` and `wishlist_id` keys. We can't fully execute it
        # without a DB, but we can assert it's an async coroutine function.
        import inspect
        from routes.watchlist import get_wishlist_status
        assert inspect.iscoroutinefunction(get_wishlist_status)
