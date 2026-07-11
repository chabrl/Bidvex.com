"""
Phase 5 — Tests for the Meta product catalog feed.

Each test is independent. MongoDB-dependent paths are exercised via the
running app's TestClient (fastapi.testclient) so we get real integration
coverage. Pure mapper tests rely only on the in-memory data structure
defined inside the test module.
"""
import asyncio
import io
import os
import inspect
import pathlib
from datetime import datetime, timezone, timedelta
import pytest

from services.meta_feed_mapper import (
    _content_id,
    _map_condition,
    _build_link,
    _iso_region_code,
    _normalize_postal,
    _geocode,
    _price_str,
    _brand,
    _strip_html,
    _is_valid_image_url,
    _first_valid_image,
    map_listing_to_meta_item,
    _google_product_category,
    LISTING_TYPE_TO_PATH,
)


# ────────────────────────────────────────────────────────────────────────
# 4A — Schema compliance / pure mapper unit tests
# ────────────────────────────────────────────────────────────────────────
class TestContentIdFormat:
    def test_id_format_marketplace(self):
        # iter224 hotfix — content_id is now raw listing_id (no prefix).
        assert _content_id("marketplace", "abc123") == "abc123"

    def test_id_format_lots(self):
        assert _content_id("lots", "x9") == "x9"

    def test_id_format_vehicle(self):
        assert _content_id("vehicle", "uuid-1") == "uuid-1"

    def test_id_format_storage(self):
        assert _content_id("storage", "S-42") == "S-42"

    def test_id_unknown_type_defaults_to_mkt(self):
        # iter224 — unknown type still returns raw id (no prefix).
        assert _content_id("unknown", "id1") == "id1"


class TestConditionMapping:
    @pytest.mark.parametrize("input_val,expected", [
        ("new", "new"),
        ("like_new", "refurbished"),
        ("like new", "refurbished"),
        ("excellent", "refurbished"),
        ("good", "used"),
        ("fair", "used"),
        ("salvage", "used"),
        ("used", "used"),
        (None, "used"),
        ("", "used"),
        ("garbage_value", "used"),
    ])
    def test_condition(self, input_val, expected):
        assert _map_condition(input_val) == expected


class TestLinkBuilder:
    def test_link_marketplace(self):
        link = _build_link("marketplace", "abc123")
        assert link.startswith("https://")
        assert "/listings/abc123" in link

    def test_link_lots(self):
        assert "/lots/x9" in _build_link("lots", "x9")

    def test_link_vehicle(self):
        assert "/vehicle-auctions/v1" in _build_link("vehicle", "v1")

    def test_link_storage(self):
        assert "/storage-auctions/s1" in _build_link("storage", "s1")

    def test_all_types_have_path_mapping(self):
        for t in ("marketplace", "lots", "vehicle", "storage", "single", "multi_lot"):
            assert t in LISTING_TYPE_TO_PATH


class TestRegionNormalization:
    @pytest.mark.parametrize("input_val,expected", [
        ("Quebec", "QC"),
        ("Qu\u00e9bec", "QC"),
        ("QC", "QC"),
        ("qc", "QC"),
        ("Ontario", "ON"),
        ("British Columbia", "BC"),
        ("AB", "AB"),
        ("Alberta", "AB"),
        ("Nova Scotia", "NS"),
        (None, None),
        ("", None),
    ])
    def test_iso_region_code(self, input_val, expected):
        assert _iso_region_code(input_val) == expected


class TestPriceFormatter:
    def test_current_bid_takes_precedence(self):
        assert _price_str({"current_bid": 99.99, "starting_bid": 5}, None) == "99.99 CAD"

    def test_falls_back_to_starting_bid_when_no_current(self):
        assert _price_str({"current_bid": 0, "starting_bid": 25}, None) == "25.00 CAD"

    def test_minimum_fallback(self):
        assert _price_str({}, None) == "1.00 CAD"
        assert _price_str({"current_bid": None, "starting_bid": None}, None) == "1.00 CAD"

    def test_lot_aggregation_picks_max_current_price(self):
        lots = [
            {"current_price": 10, "starting_price": 5},
            {"current_price": 0, "starting_price": 7},
            {"current_price": 25, "starting_price": 5},
        ]
        # current_bid is 0 -> aggregate from lots -> max(10,0,25) -> 25
        assert _price_str({"current_bid": 0}, lots) == "25.00 CAD"


class TestPostalAndBrand:
    def test_postal_normalization(self):
        assert _normalize_postal("h2x 3l7") == "H2X3L7"
        assert _normalize_postal("J1C-0J2") == "J1C0J2"
        assert _normalize_postal(None) == ""

    def test_brand_partner(self):
        b = _brand({"seller_account_type": "partner",
                    "seller_partner_company_name": "abc auction"})
        assert b == "abc auction"

    def test_brand_partner_fallback(self):
        b = _brand({"seller_account_type": "partner"})
        assert b == "BidVex Partner"

    def test_brand_dealer(self):
        b = _brand({"seller_account_type": "vehicle_dealer"})
        assert b == "BidVex Dealer"

    def test_brand_individual(self):
        assert _brand({"seller_account_type": "individual"}) == "BidVex Marketplace"


class TestStripHtml:
    def test_strip(self):
        assert _strip_html("<p>Hello <b>World</b></p>", 100) == "Hello World"

    def test_truncates(self):
        assert _strip_html("ab" * 200, 10) == "abababab" + "ab"

    def test_handles_none(self):
        assert _strip_html(None, 100) == ""


class TestImageFilter:
    def test_valid_https_image(self):
        assert _is_valid_image_url("https://images.example.com/foo.jpg") is True

    def test_rejects_base64_data_url(self):
        assert _is_valid_image_url("data:image/jpeg;base64,/9j/4AAQ...") is False

    def test_rejects_http(self):
        assert _is_valid_image_url("http://images.example.com/foo.jpg") is False

    def test_rejects_relative_url(self):
        assert _is_valid_image_url("/static/img.jpg") is False

    def test_rejects_none(self):
        assert _is_valid_image_url(None) is False

    def test_first_valid_image_picks_https(self):
        primary, extras = _first_valid_image(
            ["data:image/jpeg;base64,xxx", "https://a.com/1.jpg", "https://a.com/2.jpg"],
            None,
        )
        assert primary == "https://a.com/1.jpg"
        assert extras == ["https://a.com/2.jpg"]

    def test_first_valid_image_walks_lots(self):
        primary, extras = _first_valid_image(
            None,
            [
                {"images": ["bad", "https://lot.com/a.jpg"]},
                {"images": ["https://lot.com/b.jpg"]},
            ],
        )
        assert primary == "https://lot.com/a.jpg"
        assert "https://lot.com/b.jpg" in extras

    def test_no_valid_image_returns_none(self):
        primary, _ = _first_valid_image(["data:image/png;base64,xxx"], None)
        assert primary is None


class TestGeocoder:
    def test_sherbrooke_qc(self):
        lat, lng = _geocode("Sherbrooke", "QC")
        assert lat is not None and lng is not None
        assert 45 < lat < 46
        assert -72 < lng < -71

    def test_montreal_qc(self):
        lat, lng = _geocode("Montr\u00e9al", "QC")
        # Accent-insensitive lookup
        assert lat is not None
        assert 45 < lat < 46

    def test_unknown_city_returns_none(self):
        assert _geocode("Atlantis", "QC") == (None, None)

    def test_calgary_ab(self):
        lat, _ = _geocode("Calgary", "AB")
        assert lat is not None and 50 < lat < 52


class TestGoogleProductCategory:
    @pytest.mark.parametrize("category,expected", [
        ("Furniture", "436"),
        ("Vehicles", "916"),
        ("Cars", "916"),
        ("Electronics", "222"),
        ("Tools", "632"),
        ("Sports", "990"),
        ("Collectibles", "216"),
        ("Mode", "166"),
        (None, "632"),
        ("UnknownCategory", "632"),
    ])
    def test_taxonomy(self, category, expected):
        assert _google_product_category(category) == expected


# ────────────────────────────────────────────────────────────────────────
# 4B — Exclusion rules at the mapper level
# ────────────────────────────────────────────────────────────────────────
def _fresh_exclusion_counter():
    return {
        "no_images": 0,
        "no_location": 0,
        "no_title": 0,
        "demo_account": 0,
        "moderation_pending": 0,
        "placeholder_used": 0,
    }


def _good_listing(**overrides):
    base = {
        "id": "L1",
        "title": "A widget",
        "description": "A nice widget",
        "status": "active",
        "images": ["https://img.example.com/foo.jpg"],
        "city": "Sherbrooke",
        "region": "QC",
        "category": "Furniture",
        "condition": "good",
        "current_bid": 99.99,
        "seller_account_type": "individual",
    }
    base.update(overrides)
    return base


class TestMapperExclusions:
    def test_active_listing_is_included(self):
        c = _fresh_exclusion_counter()
        item = map_listing_to_meta_item(_good_listing(), "marketplace", {}, c)
        assert item is not None
        # iter224 hotfix — content_id is now the raw listing id (no prefix).
        assert item["id"] == "L1"

    def test_inactive_listing_now_included_as_out_of_stock(self):
        """iter224 hotfix — ended/sold listings stay in the catalog with
        `availability: out of stock` (instead of being hard-excluded which
        broke Meta match rate)."""
        c = _fresh_exclusion_counter()
        item = map_listing_to_meta_item(_good_listing(status="ended"), "marketplace", {}, c)
        assert item is not None
        assert item["availability"] == "out of stock"

    def test_excludes_pending_review(self):
        c = _fresh_exclusion_counter()
        assert map_listing_to_meta_item(_good_listing(status="pending_review"), "marketplace", {}, c) is None
        assert c["moderation_pending"] == 1

    def test_excludes_manual_review(self):
        c = _fresh_exclusion_counter()
        assert map_listing_to_meta_item(_good_listing(status="manual_review"), "marketplace", {}, c) is None
        assert c["moderation_pending"] == 1

    def test_excludes_no_images(self):
        """iter289 — no-image listings are no longer excluded; they get a
        placeholder image so ads keep targeting them."""
        c = _fresh_exclusion_counter()
        item = map_listing_to_meta_item(_good_listing(images=[]), "marketplace", {}, c)
        assert item is not None
        assert item["image_link"]
        assert c.get("placeholder_used", 0) == 1

    def test_base64_only_images_use_branded_placeholder(self):
        """Listings with base64-only images are no longer excluded — they
        receive the BidVex branded placeholder URL so they remain ingestible
        by Meta. This is the iter217 Phase 5 bug-fix contract."""
        from services.meta_feed_mapper import BIDVEX_PLACEHOLDER_IMAGE
        c = _fresh_exclusion_counter()
        item = map_listing_to_meta_item(
            _good_listing(images=["data:image/jpeg;base64,xxx"]), "marketplace", {}, c)
        assert item is not None, "base64-only listing must surface with placeholder"
        assert item["image_link"] == BIDVEX_PLACEHOLDER_IMAGE
        assert c.get("placeholder_used", 0) == 1
        assert c["no_images"] == 0

    def test_base64_in_lots_uses_branded_placeholder(self):
        """Multi-item listings with base64 lot images also fall back to the
        branded placeholder rather than being excluded."""
        from services.meta_feed_mapper import BIDVEX_PLACEHOLDER_IMAGE
        c = _fresh_exclusion_counter()
        item = map_listing_to_meta_item(
            _good_listing(images=[], lots=[{"images": ["data:image/png;base64,xxx"]}]),
            "lots", {}, c)
        assert item is not None
        assert item["image_link"] == BIDVEX_PLACEHOLDER_IMAGE

    def test_real_https_image_preferred_over_placeholder(self):
        """When at least one valid https image exists, the placeholder must
        NOT be used — real listing photos always win."""
        from services.meta_feed_mapper import BIDVEX_PLACEHOLDER_IMAGE
        c = _fresh_exclusion_counter()
        item = map_listing_to_meta_item(
            _good_listing(images=["data:image/jpeg;base64,xxx", "https://real.example.com/a.jpg"]),
            "marketplace", {}, c)
        assert item is not None
        assert item["image_link"] == "https://real.example.com/a.jpg"
        assert item["image_link"] != BIDVEX_PLACEHOLDER_IMAGE

    def test_excludes_no_title(self):
        c = _fresh_exclusion_counter()
        assert map_listing_to_meta_item(_good_listing(title=""), "marketplace", {}, c) is None
        assert c["no_title"] == 1

    def test_excludes_no_city(self):
        c = _fresh_exclusion_counter()
        assert map_listing_to_meta_item(_good_listing(city=""), "marketplace", {}, c) is None
        assert c["no_location"] == 1

    def test_excludes_no_region(self):
        c = _fresh_exclusion_counter()
        assert map_listing_to_meta_item(_good_listing(region=None, province=None), "marketplace", {}, c) is None
        assert c["no_location"] == 1

    def test_excludes_demo_account_seller(self):
        c = _fresh_exclusion_counter()
        assert map_listing_to_meta_item(_good_listing(), "marketplace",
                                        {"is_demo_account": True}, c) is None
        assert c["demo_account"] == 1


# ────────────────────────────────────────────────────────────────────────
# 4C — Mandatory Meta fields shape
# ────────────────────────────────────────────────────────────────────────
MANDATORY_FIELDS = {
    "id", "title", "description", "availability", "condition", "price",
    "link", "image_link", "brand", "city", "region", "country",
}


class TestMandatoryMetaFields:
    def test_all_mandatory_fields_present(self):
        c = _fresh_exclusion_counter()
        item = map_listing_to_meta_item(_good_listing(), "marketplace", {}, c)
        assert item is not None
        for f in MANDATORY_FIELDS:
            assert f in item and item[f] not in ("", None), f"{f} is missing or empty"

    def test_availability_is_in_stock(self):
        item = map_listing_to_meta_item(_good_listing(), "marketplace", {}, _fresh_exclusion_counter())
        assert item["availability"] == "in stock"

    def test_country_is_CA(self):
        item = map_listing_to_meta_item(_good_listing(), "marketplace", {}, _fresh_exclusion_counter())
        assert item["country"] == "CA"

    def test_price_has_currency_suffix(self):
        item = map_listing_to_meta_item(_good_listing(), "marketplace", {}, _fresh_exclusion_counter())
        assert item["price"].endswith(" CAD")

    def test_link_is_absolute_url(self):
        item = map_listing_to_meta_item(_good_listing(), "marketplace", {}, _fresh_exclusion_counter())
        assert item["link"].startswith("https://")

    def test_image_link_is_https(self):
        item = map_listing_to_meta_item(_good_listing(), "marketplace", {}, _fresh_exclusion_counter())
        assert item["image_link"].startswith("https://")


class TestCustomLabels:
    def test_custom_label_0_is_listing_type(self):
        item = map_listing_to_meta_item(_good_listing(), "lots", {}, _fresh_exclusion_counter())
        assert item["custom_label_0"] == "lots"

    def test_custom_label_1_is_seller_account_type(self):
        item = map_listing_to_meta_item(
            _good_listing(seller_account_type="partner",
                          seller_partner_company_name="abc"),
            "lots", {}, _fresh_exclusion_counter(),
        )
        assert item["custom_label_1"] == "partner"

    def test_custom_label_2_is_normalized_region(self):
        item = map_listing_to_meta_item(_good_listing(region="quebec"), "marketplace",
                                        {}, _fresh_exclusion_counter())
        assert item["custom_label_2"] == "CA-QC"

    def test_custom_label_3_marks_ending_soon(self):
        soon = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
        item = map_listing_to_meta_item(_good_listing(auction_end_date=soon),
                                        "marketplace", {}, _fresh_exclusion_counter())
        assert item["custom_label_3"] == "auction_ending_soon"

    def test_custom_label_3_default_is_active(self):
        far = (datetime.now(timezone.utc) + timedelta(days=10)).isoformat()
        item = map_listing_to_meta_item(_good_listing(auction_end_date=far),
                                        "marketplace", {}, _fresh_exclusion_counter())
        assert item["custom_label_3"] == "auction_active"


class TestGeoCoordinates:
    def test_lat_lng_geocoded_from_city(self):
        item = map_listing_to_meta_item(_good_listing(), "marketplace", {}, _fresh_exclusion_counter())
        assert "latitude" in item and "longitude" in item
        assert 45 < item["latitude"] < 46  # Sherbrooke

    def test_explicit_lat_lng_preserved(self):
        item = map_listing_to_meta_item(
            _good_listing(latitude=44.0, longitude=-73.0),
            "marketplace", {}, _fresh_exclusion_counter(),
        )
        assert item["latitude"] == 44.0
        assert item["longitude"] == -73.0


# ────────────────────────────────────────────────────────────────────────
# 4C-2 — Seed items (Meta Commerce Manager 5-product minimum padding)
# ────────────────────────────────────────────────────────────────────────
class TestSeedItems:
    def test_build_seed_items_returns_requested_count(self):
        from services.meta_feed_mapper import build_seed_items
        seeds = build_seed_items(3)
        assert len(seeds) == 3

    def test_build_seed_items_returns_empty_when_needed_is_zero(self):
        from services.meta_feed_mapper import build_seed_items
        assert build_seed_items(0) == []
        assert build_seed_items(-1) == []

    def test_seed_items_have_all_mandatory_meta_fields(self):
        from services.meta_feed_mapper import build_seed_items
        for seed in build_seed_items(5):
            for f in MANDATORY_FIELDS:
                assert f in seed and seed[f] not in ("", None), f"seed missing {f}"

    def test_seed_items_carry_test_seed_label(self):
        """custom_label_3 must be 'test_seed' so production campaigns can
        exclude these placeholders with a single filter."""
        from services.meta_feed_mapper import build_seed_items
        for seed in build_seed_items(5):
            assert seed["custom_label_3"] == "test_seed"

    def test_seed_items_use_branded_placeholder_image(self):
        from services.meta_feed_mapper import build_seed_items, BIDVEX_PLACEHOLDER_IMAGE
        for seed in build_seed_items(5):
            assert seed["image_link"] == BIDVEX_PLACEHOLDER_IMAGE

    def test_seed_ids_have_consistent_prefix(self):
        from services.meta_feed_mapper import build_seed_items
        for seed in build_seed_items(5):
            assert seed["id"].startswith("BIDVEX-SEED-")

    def test_seed_items_cover_qc_and_on(self):
        from services.meta_feed_mapper import build_seed_items
        regions = {s["region"] for s in build_seed_items(5)}
        assert "CA-QC" in regions
        assert "CA-ON" in regions

    def test_seed_items_are_deterministic(self):
        from services.meta_feed_mapper import build_seed_items
        a = build_seed_items(5)
        b = build_seed_items(5)
        assert [s["id"] for s in a] == [s["id"] for s in b]

    def test_seed_items_capped_at_pool_size(self):
        from services.meta_feed_mapper import build_seed_items
        # Pool size is META_MIN_CATALOG_ITEMS == 5
        seeds = build_seed_items(100)
        assert len(seeds) <= 5

    def test_meta_min_catalog_items_is_five(self):
        from services.meta_feed_mapper import META_MIN_CATALOG_ITEMS
        assert META_MIN_CATALOG_ITEMS == 5



# ────────────────────────────────────────────────────────────────────────
# 4D — Live HTTP endpoint integration (real backend, no TestClient lifespan)
# ────────────────────────────────────────────────────────────────────────
import requests


@pytest.fixture(scope="module")
def api_base():
    # Read the same URL the frontend uses; falls back to local supervisor.
    url = os.environ.get("REACT_APP_BACKEND_URL")
    if not url:
        env_file = pathlib.Path("/app/frontend/.env")
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("REACT_APP_BACKEND_URL="):
                    url = line.split("=", 1)[1].strip()
                    break
    return (url or "http://localhost:8001").rstrip("/")


class TestFeedEndpoint:
    def test_feed_returns_200_unauthenticated(self, api_base):
        r = requests.get(f"{api_base}/api/feeds/facebook-local?format=json", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "data" in body
        assert isinstance(body["data"], list)

    def test_feed_response_has_correct_content_type(self, api_base):
        r = requests.get(f"{api_base}/api/feeds/facebook-local?format=json", timeout=15)
        assert r.headers["content-type"].startswith("application/json")
        # CORS for Meta's crawler
        assert r.headers.get("access-control-allow-origin") == "*"

    def test_feed_response_has_cache_control_header(self, api_base):
        # Hit localhost directly so we bypass the Cloudflare edge cache that
        # rewrites Cache-Control on the public URL. We're asserting the
        # backend's route-level header, not the CDN's.
        r = requests.get("http://localhost:8001/api/feeds/facebook-local?format=json", timeout=15)
        cc = r.headers.get("cache-control", "")
        assert "max-age=900" in cc
        assert "public" in cc

    def test_feed_meta_endpoint_returns_correct_structure(self, api_base):
        r = requests.get(f"{api_base}/api/feeds/facebook-local/meta", timeout=15)
        assert r.status_code == 200
        body = r.json()
        for key in (
            "total_active_listings", "feed_eligible_listings", "excluded_listings",
            "exclusion_reasons", "last_cached_at", "cache_ttl_seconds",
            "feed_url", "total_pages", "items_per_page",
        ):
            assert key in body, f"missing key {key}"
        for ex_key in ("no_images", "no_location", "no_title", "demo_account", "moderation_pending"):
            assert ex_key in body["exclusion_reasons"]

    def test_feed_respects_limit_parameter(self, api_base):
        r = requests.get(f"{api_base}/api/feeds/facebook-local?format=json&limit=2", timeout=15)
        assert r.status_code == 200
        assert len(r.json()["data"]) <= 2

    def test_feed_respects_province_filter(self, api_base):
        # Cross-province isolation: AB should not return QC listings.
        r = requests.get(f"{api_base}/api/feeds/facebook-local?format=json&province=AB", timeout=15)
        assert r.status_code == 200
        for it in r.json()["data"]:
            assert it["region"] != "QC"

    def test_feed_handles_empty_catalog_gracefully(self, api_base):
        # Filter by a province with no listings at all (NU)
        r = requests.get(f"{api_base}/api/feeds/facebook-local?format=json&province=NU", timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["data"] == []
        assert body["seed_padded"] is False

    def test_feed_is_unauthenticated_public(self, api_base):
        r = requests.get(f"{api_base}/api/feeds/facebook-local?format=json", timeout=15)
        assert r.status_code == 200, "Public feed must not require auth"

    def test_feed_refresh_requires_admin(self, api_base):
        r = requests.post(f"{api_base}/api/feeds/facebook-local/refresh", timeout=15)
        assert r.status_code in (401, 403)

    def test_feed_padded_to_minimum_five_items(self, api_base):
        """Meta Commerce Manager refuses catalogs with fewer than 5 products.
        The UNFILTERED feed must always include >=5 items (real + seed pad)."""
        r = requests.get(f"{api_base}/api/feeds/facebook-local?format=json", timeout=15)
        assert r.status_code == 200
        items = r.json()["data"]
        assert len(items) >= 5, f"expected >=5 items, got {len(items)}"

    def test_json_response_exposes_seed_padded_flag(self, api_base):
        """Admin tools need to know whether the feed was padded so the
        dashboard can surface a 'Add more listings' warning."""
        r = requests.get(f"{api_base}/api/feeds/facebook-local?format=json", timeout=15)
        body = r.json()
        assert "seed_padded" in body
        assert "count" in body
        assert isinstance(body["seed_padded"], bool)
        assert body["count"] == len(body["data"])

    def test_padded_seed_items_carry_test_seed_label(self, api_base):
        """Every BIDVEX-SEED-* item in the unfiltered feed must have
        custom_label_3='test_seed' so production ads can exclude them."""
        r = requests.get(f"{api_base}/api/feeds/facebook-local?format=json", timeout=15)
        assert r.status_code == 200
        for it in r.json()["data"]:
            if it["id"].startswith("BIDVEX-SEED-"):
                assert it["custom_label_3"] == "test_seed"

    def test_seed_items_use_branded_placeholder_in_live_feed(self, api_base):
        r = requests.get(f"{api_base}/api/feeds/facebook-local?format=json", timeout=15)
        for it in r.json()["data"]:
            if it["id"].startswith("BIDVEX-SEED-"):
                assert it["image_link"].endswith("/placeholder-ad.jpg")
                assert it["image_link"].startswith("https://")

    def test_seed_items_not_returned_for_filtered_queries(self, api_base):
        """Province/category-filtered queries must NOT include padded seeds —
        only the unfiltered catalog gets padded."""
        r = requests.get(f"{api_base}/api/feeds/facebook-local?format=json&province=AB", timeout=15)
        for it in r.json()["data"]:
            assert not it["id"].startswith("BIDVEX-SEED-"), \
                "filtered feeds must never include test_seed items"

    def test_meta_endpoint_reports_seed_padding(self, api_base):
        r = requests.get(f"{api_base}/api/feeds/facebook-local/meta", timeout=15)
        body = r.json()
        assert "seed_items_padded" in body
        assert "feed_total_items" in body
        assert body["feed_total_items"] >= 5

    def test_meta_excluded_listings_is_never_negative(self, api_base):
        """Old bug: seeds in feed_eligible made excluded_listings negative."""
        r = requests.get(f"{api_base}/api/feeds/facebook-local/meta", timeout=15)
        body = r.json()
        assert body["excluded_listings"] >= 0

    # ── 4D-2 — CSV format (Meta Commerce Manager default) ────────────
    def test_csv_is_default_format(self, api_base):
        """Hitting the bare URL must return CSV (Meta's preferred format)."""
        r = requests.get(f"{api_base}/api/feeds/facebook-local", timeout=15)
        assert r.status_code == 200
        ct = r.headers.get("content-type", "")
        assert ct.startswith("text/csv"), f"expected text/csv default, got {ct}"
        assert "charset=utf-8" in ct.lower()

    def test_csv_has_attachment_disposition(self, api_base):
        r = requests.get("http://localhost:8001/api/feeds/facebook-local", timeout=15)
        cd = r.headers.get("content-disposition", "")
        assert "attachment" in cd.lower()
        assert "bidvex-catalog.csv" in cd

    def test_csv_uses_crlf_line_endings(self, api_base):
        """Meta's parser requires CRLF (RFC 4180) — \\r\\n separator."""
        r = requests.get(f"{api_base}/api/feeds/facebook-local", timeout=15)
        body = r.content  # bytes
        assert b"\r\n" in body, "CSV must use CRLF line endings"

    def test_csv_has_no_bom(self, api_base):
        """UTF-8 BOM (0xEF 0xBB 0xBF) confuses Meta's parser."""
        r = requests.get(f"{api_base}/api/feeds/facebook-local", timeout=15)
        assert not r.content.startswith(b"\xef\xbb\xbf")

    def test_csv_header_columns_exact_order(self, api_base):
        """Header row must match the Meta-compliant column order exactly."""
        r = requests.get(f"{api_base}/api/feeds/facebook-local", timeout=15)
        first_line = r.text.split("\r\n", 1)[0]
        expected = (
            "id,title,description,availability,condition,"
            "price,link,image_link,brand,latitude,longitude,"
            "neighborhood,city,region,country,postal_code,"
            "additional_image_link,google_product_category,"
            "custom_label_0,custom_label_1,"
            "custom_label_2,custom_label_3,shipping"
        )
        assert first_line == expected, f"header mismatch:\n{first_line}\n--vs--\n{expected}"

    def test_csv_data_rows_are_double_quoted(self, api_base):
        """Every data cell must be wrapped in double quotes (RFC 4180 QUOTE_ALL)."""
        r = requests.get(f"{api_base}/api/feeds/facebook-local", timeout=15)
        rows = r.text.split("\r\n")
        assert len(rows) >= 2, "expected at least header + 1 data row"
        data_row = rows[1]
        # First cell must start with a quote
        assert data_row.startswith('"'), "data rows must be double-quoted"
        # Should contain "," (quote, comma, quote) between cells
        assert '","' in data_row

    def test_csv_returns_at_least_five_rows_unfiltered(self, api_base):
        """Meta Commerce Manager rejects feeds with < 5 products."""
        r = requests.get(f"{api_base}/api/feeds/facebook-local", timeout=15)
        rows = [ln for ln in r.text.split("\r\n") if ln.strip()]
        # 1 header + 5+ data rows
        assert len(rows) >= 6, f"expected >=5 data rows + header, got {len(rows)}"

    def test_csv_contains_seed_rows_in_unfiltered_feed(self, api_base):
        """Seeds pad the unfiltered feed ONLY when <5 real items exist."""
        r = requests.get(f"{api_base}/api/feeds/facebook-local", timeout=15)
        data_rows = [ln for ln in r.text.split("\r\n") if ln.strip()][1:]
        real_rows = [ln for ln in data_rows if "BIDVEX-SEED-" not in ln]
        if len(real_rows) < 5:
            assert "BIDVEX-SEED-" in r.text

    def test_csv_no_seed_rows_in_filtered_feed(self, api_base):
        r = requests.get(f"{api_base}/api/feeds/facebook-local?province=NU", timeout=15)
        # NU has 0 real listings; with filtering, no seeds either — only header.
        assert "BIDVEX-SEED-" not in r.text

    def test_csv_format_rejects_invalid_value(self, api_base):
        r = requests.get(f"{api_base}/api/feeds/facebook-local?format=xml", timeout=15)
        assert r.status_code == 400

    def test_csv_seed_link_is_bidvex_root(self, api_base):
        r = requests.get(f"{api_base}/api/feeds/facebook-local", timeout=15)
        # Seed `link` field must be plain bidvex.com per spec — seeds have
        # no real listing page.
        # Find at least one BIDVEX-SEED row and check its `link` cell.
        for line in r.text.split("\r\n"):
            if "BIDVEX-SEED-001" in line:
                assert '"https://bidvex.com"' in line, "seed link should be plain bidvex.com"
                return
        # If padding didn't kick in (>=5 real items), skip.
        pytest.skip("no seeds in feed — catalog has >=5 real items")

    def test_csv_handles_embedded_quotes_per_rfc4180(self, api_base):
        """If a listing title contains a literal quote, the CSV must escape
        it as a doubled quote ("") inside the cell — RFC 4180."""
        # We can only validate this if a real listing happens to have a quote.
        # The mapper writes via csv.writer with QUOTE_ALL — Python's stdlib
        # csv module is RFC 4180 compliant by default, so this is a smoke
        # test that the response parses cleanly back through csv.reader.
        import csv as _csv
        r = requests.get(f"{api_base}/api/feeds/facebook-local", timeout=15)
        reader = _csv.reader(io.StringIO(r.text))
        rows = list(reader)
        assert len(rows) >= 2
        # Every row must have the same column count as the header.
        header_len = len(rows[0])
        for i, row in enumerate(rows[1:], 1):
            assert len(row) == header_len, f"row {i} column count mismatch ({len(row)} vs {header_len})"


# ────────────────────────────────────────────────────────────────────────
# 4E — Frontend pixel wrapper (source-level + integration)
# ────────────────────────────────────────────────────────────────────────
class TestFrontendPixel:
    def test_metapixel_helper_exists(self):
        p = pathlib.Path("/app/frontend/src/utils/metaPixel.js")
        assert p.exists()
        src = p.read_text(encoding="utf-8")
        # Required exports
        for sym in ("initMetaPixel", "trackEvent", "trackCustomEvent",
                    "trackViewContent", "trackAddToWishlist", "trackPurchase",
                    "trackSearch", "buildContentId", "notifyConsentGranted",
                    "revokeConsent"):
            assert sym in src, f"missing {sym}"

    def test_pixel_storage_prefix_is_raw_id(self):
        """iter224 hotfix — content_ids are now raw listing.id (no prefix).
        Test renamed from `test_pixel_storage_prefix_is_sto`."""
        src = pathlib.Path("/app/frontend/src/utils/metaContentId.js").read_text(encoding="utf-8")
        # getCanonicalContentId must return the raw listing.id.
        assert "return String(listing.id)" in src
        # Verify no BIDVEX-{prefix}- template-literal pattern survives in the
        # canonical content_id helper (older iterations used this format).
        assert "`BIDVEX-${prefix}-${listing.id}`" not in src

    def test_pixel_uses_canonical_consent_key(self):
        src = pathlib.Path("/app/frontend/src/utils/metaPixel.js").read_text(encoding="utf-8")
        assert "bidvex_analytics_consent" in src

    def test_pixel_revoke_calls_fbq_consent_revoke(self):
        """CASL withdrawal MUST emit fbq('consent', 'revoke') immediately."""
        src = pathlib.Path("/app/frontend/src/utils/metaPixel.js").read_text(encoding="utf-8")
        assert "fbq('consent', 'revoke')" in src or 'fbq("consent", "revoke")' in src

    def test_pixel_id_format_matches_backend(self):
        """iter224 hotfix — FE + BE both emit RAW listing.id as content_id."""
        src = pathlib.Path("/app/frontend/src/utils/metaContentId.js").read_text(encoding="utf-8")
        # The helper must return the raw listing.id (no template-literal prefix).
        assert "return String(listing.id)" in src

    def test_pixel_consent_gated(self):
        src = pathlib.Path("/app/frontend/src/utils/metaPixel.js").read_text(encoding="utf-8")
        assert "cookieConsent" in src
        # Init defers when no consent
        assert "_hasConsent" in src

    def test_pixel_silent_when_no_env(self):
        src = pathlib.Path("/app/frontend/src/utils/metaPixel.js").read_text(encoding="utf-8")
        assert "REACT_APP_META_PIXEL_ID" in src
        # Warns but does not throw
        assert "console.warn" in src

    def test_noscript_fallback_present_in_index_html(self):
        html = pathlib.Path("/app/frontend/public/index.html").read_text(encoding="utf-8")
        # The unconditional inline fbq init is removed; only the noscript pixel remains.
        assert "<noscript>" in html
        # Inline script that called fbq() at page load is gone
        assert "fbq('init'," not in html and 'fbq("init",' not in html


# ────────────────────────────────────────────────────────────────────────
# 4E-2 — Frontend SafeImage component (Phase 5 Hotfix)
# ────────────────────────────────────────────────────────────────────────
class TestSafeImageComponent:
    def test_safe_image_component_exists(self):
        p = pathlib.Path("/app/frontend/src/components/SafeImage.jsx")
        assert p.exists()

    def test_safe_image_detects_base64_data_urls(self):
        src = pathlib.Path("/app/frontend/src/components/SafeImage.jsx").read_text(encoding="utf-8")
        assert "startsWith('data:')" in src

    def test_safe_image_uses_branded_placeholder(self):
        src = pathlib.Path("/app/frontend/src/components/SafeImage.jsx").read_text(encoding="utf-8")
        assert "bidvex.com/assets/placeholder-ad.jpg" in src

    def test_safe_image_handles_on_error(self):
        src = pathlib.Path("/app/frontend/src/components/SafeImage.jsx").read_text(encoding="utf-8")
        assert "handleError" in src or "onError" in src

    def test_listing_detail_uses_safe_image(self):
        src = pathlib.Path("/app/frontend/src/pages/ListingDetailPage.js").read_text(encoding="utf-8")
        assert "SafeImage" in src
        assert "import SafeImage" in src

    def test_multi_item_detail_uses_safe_image(self):
        src = pathlib.Path("/app/frontend/src/pages/MultiItemListingDetailPage.js").read_text(encoding="utf-8")
        assert "SafeImage" in src

    def test_marketplace_card_uses_safe_image(self):
        src = pathlib.Path("/app/frontend/src/components/FlattenedMarketplace.js").read_text(encoding="utf-8")
        assert "SafeImage" in src

    def test_lots_marketplace_uses_safe_image(self):
        src = pathlib.Path("/app/frontend/src/pages/LotsMarketplacePage.js").read_text(encoding="utf-8")
        assert "SafeImage" in src

    def test_homepage_uses_safe_image(self):
        src = pathlib.Path("/app/frontend/src/pages/HomePage.js").read_text(encoding="utf-8")
        assert "SafeImage" in src



# ────────────────────────────────────────────────────────────────────────
# 4F — Server-side wiring
# ────────────────────────────────────────────────────────────────────────
class TestServerWiring:
    def test_feeds_router_registered(self):
        from server import app
        paths = [route.path for route in app.routes]
        assert "/api/feeds/facebook-local" in paths
        assert "/api/feeds/facebook-local/meta" in paths

    def test_feeds_router_has_prefix(self):
        from routes.feeds import router
        assert router.prefix == "/feeds"


class TestCacheService:
    def test_make_key_is_deterministic(self):
        from services.feed_cache import make_cache_key
        a = make_cache_key("QC", "Furniture", "lots", 100, 0)
        b = make_cache_key("QC", "Furniture", "lots", 100, 0)
        assert a == b

    def test_invalidate_clears_all_fb_keys(self):
        from services.feed_cache import cache_set, invalidate_feed_cache, get_cache_size
        cache_set("fb_feed:test_key_1", ["x"], {})
        cache_set("fb_feed:test_key_2", ["y"], {})
        cleared = invalidate_feed_cache()
        assert cleared >= 2
        assert get_cache_size() == 0



# ────────────────────────────────────────────────────────────────────────
# 4G — Phase 5 Hotfix v4: S3 service + SafeImage threshold + endpoint wiring
# ────────────────────────────────────────────────────────────────────────
class TestS3Service:
    def test_s3_service_module_imports(self):
        from services import s3_service
        # Public API surface
        assert hasattr(s3_service, "upload_image_to_s3")
        assert hasattr(s3_service, "upload_base64_to_s3")
        assert hasattr(s3_service, "delete_s3_image")
        assert hasattr(s3_service, "is_marketplace_s3_url")
        assert hasattr(s3_service, "is_base64_image")

    def test_s3_bucket_config_is_marketplace_bucket(self):
        from services.s3_service import S3_BUCKET, S3_BASE_URL, S3_REGION
        assert S3_BUCKET == "bidvex-marketplace-images"
        assert S3_REGION == "us-east-2"
        assert "bidvex-marketplace-images.s3.us-east-2" in S3_BASE_URL
        assert S3_BASE_URL.startswith("https://")

    def test_is_marketplace_s3_url_recognizes_own_bucket(self):
        from services.s3_service import is_marketplace_s3_url
        assert is_marketplace_s3_url("https://bidvex-marketplace-images.s3.us-east-2.amazonaws.com/listings/foo/00-abc.jpg") is True
        assert is_marketplace_s3_url("https://other-bucket.s3.amazonaws.com/foo.jpg") is False
        assert is_marketplace_s3_url("data:image/jpeg;base64,xxx") is False
        assert is_marketplace_s3_url(None) is False
        assert is_marketplace_s3_url("") is False

    def test_is_base64_image_detects_data_urls(self):
        from services.s3_service import is_base64_image
        assert is_base64_image("data:image/jpeg;base64,/9j/4AAQ" + "a" * 100) is True
        assert is_base64_image("https://example.com/foo.jpg") is False
        assert is_base64_image(None) is False

    def test_build_key_strips_path_traversal(self):
        from services.s3_service import _build_key, _safe_listing_id
        # Path traversal attempts must be neutralized
        key = _build_key("../etc/passwd", 0)
        assert ".." not in key
        assert "/" in key  # the listings/{id}/{name} structure
        assert _safe_listing_id("../../etc") == "etc"

    def test_endpoint_constant_limit(self):
        from routes.listings import LISTING_IMAGES_MAX
        assert LISTING_IMAGES_MAX == 15

    def test_upload_endpoint_registered(self):
        from server import app
        paths = [route.path for route in app.routes]
        assert "/api/listings/{listing_id}/images" in paths


class TestSafeImageThreshold:
    """The new threshold-based base64 rule from Phase 5 Hotfix v4."""

    def test_safe_image_exposes_threshold_constant(self):
        src = pathlib.Path("/app/frontend/src/components/SafeImage.jsx").read_text(encoding="utf-8")
        assert "BASE64_MIN_RENDERABLE_LENGTH" in src
        assert "5000" in src

    def test_safe_image_short_base64_swapped(self):
        """Tiny base64 (< threshold) MUST still be swapped to placeholder.
        This is verified via source-level inspection — the JS implementation
        gates on `trimmed.length >= BASE64_MIN_RENDERABLE_LENGTH`."""
        src = pathlib.Path("/app/frontend/src/components/SafeImage.jsx").read_text(encoding="utf-8")
        assert "trimmed.length >= BASE64_MIN_RENDERABLE_LENGTH" in src

    def test_safe_image_placeholder_url_unchanged(self):
        src = pathlib.Path("/app/frontend/src/components/SafeImage.jsx").read_text(encoding="utf-8")
        assert "https://bidvex.com/assets/placeholder-ad.jpg" in src


class TestMigrationScript:
    def test_migration_script_exists(self):
        p = pathlib.Path("/app/backend/scripts/migrate_base64_images_to_s3.py")
        assert p.exists()

    def test_migration_supports_all_listing_collections(self):
        from scripts.migrate_base64_images_to_s3 import ADAPTERS
        assert set(ADAPTERS.keys()) >= {
            "listings", "multi_item_listings", "vehicle_listings", "storage_auctions",
        }

    def test_migration_needs_migration_skips_https(self):
        from scripts.migrate_base64_images_to_s3 import _needs_migration
        assert _needs_migration("https://bidvex.com/foo.jpg") is False
        assert _needs_migration("http://localhost/foo.jpg") is False
        assert _needs_migration("") is False
        assert _needs_migration(None) is False
        assert _needs_migration("data:image/jpeg;base64," + "A" * 1500) is True
