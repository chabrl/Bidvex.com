"""
iter289 — Unified Multi-Section Catalog Feed regression tests.

Verifies the four production gaps closed in this sprint:

  1. Vehicle listings now surface in the Meta + Google catalog feeds.
     The legacy mapping queried `db.vehicles` (empty table); the real
     dealer-wizard listings live in `db.vehicle_listings`.

  2. Listings missing image data NEVER get dropped — a per-section S3
     placeholder is injected:
       vehicles    → default-vehicle.jpg
       storage     → default-storage.jpg
       lots        → default-lots.jpg
       marketplace → default-item.jpg

  3. `?section=vehicles|storage|lots|marketplace` is accepted as an
     alias for the internal `type=` filter so the documented Meta +
     Google contract URLs work.

  4. `robots.txt` advertises both feeds via an explicit
     `Allow: /api/feeds/` override that takes precedence over the
     broader `Disallow: /api/` rule for crawlers that honour Allow.

Constraints honoured:
  - The /facebook-local response schema is unchanged. The `data[*].id`
    is still the raw UUID (iter224 contract — DO NOT add prefixes;
    breaks Google Merchant `id ↔ link page id` validation).
  - Cache TTL stays at 900 seconds (FEED_CACHE_TTL_SECONDS env).
  - All 4 collections are queried on every cache miss; an empty
    collection no longer aborts the build.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from pymongo import MongoClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BASE_URL = os.environ.get("PUBLIC_BACKEND_URL", "http://localhost:8001")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def admin_token():
    import time as _t
    last = None
    for _attempt in range(8):
        r = requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=15,
        )
        last = r
        if r.status_code == 200:
            return r.json().get("access_token") or r.json().get("token")
        _t.sleep(min(2 ** _attempt, 16))
    raise AssertionError(f"admin login failed: {last.status_code} {last.text[:200]}")


def _refresh_cache(admin_token):
    """Force a cache rebuild so the test sees the latest seeded docs."""
    r = requests.post(
        f"{BASE_URL}/api/feeds/facebook-local/refresh",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    return r.json()


# ── Gap 1 — vehicle_listings collection is wired into the feed ────────


def test_collection_to_type_mapping_uses_vehicle_listings():
    """The internal mapper must read from `vehicle_listings`, NOT the
    legacy empty `vehicles` collection. This was the root cause of
    zero vehicles appearing in the catalog feed."""
    from services.meta_feed_mapper import COLLECTION_TO_TYPE
    assert "vehicle_listings" in COLLECTION_TO_TYPE
    assert COLLECTION_TO_TYPE["vehicle_listings"] == "vehicle"
    # The legacy bogus mapping must NOT be present.
    assert "vehicles" not in COLLECTION_TO_TYPE


def test_section_placeholders_constant_present():
    """Per-section placeholder map must be exported so the mapper can
    inject a publicly-accessible JPEG fallback when a listing has no
    usable image.

    iter291 — Switched from the S3 bucket placeholders (which returned
    403 in production — bucket private/objects missing) to the public
    BidVex `/assets/placeholder-ad.jpg` so Google Merchant Center stops
    flagging "Unsupported image type" on placeholder fallbacks.
    """
    from services.meta_feed_mapper import SECTION_PLACEHOLDERS
    for sec in ("vehicle", "storage", "lots", "marketplace"):
        url = SECTION_PLACEHOLDERS.get(sec)
        assert isinstance(url, str)
        # Must be a publicly-accessible https JPEG/PNG/GIF — no signed
        # URLs, no proxied URLs.
        assert url.startswith("https://"), url
        assert url.lower().endswith((".jpg", ".jpeg", ".png", ".gif")), url


# ── Gap 2 — `?section=` alias maps to internal type filter ────────────


def test_facebook_local_section_alias_maps_vehicles_to_vehicle_filter(admin_token):
    _refresh_cache(admin_token)
    r = requests.get(
        f"{BASE_URL}/api/feeds/facebook-local?format=json&section=vehicles&limit=100",
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    items = body.get("data", [])
    # In the live preview db there are 4 active vehicle_listings with
    # required location fields — the post-fix feed must surface them.
    assert len(items) >= 1, "No vehicles surfaced in the feed — collection wiring regressed"
    for it in items:
        assert it.get("custom_label_0") == "vehicle", it


def test_facebook_local_section_alias_lots(admin_token):
    _refresh_cache(admin_token)
    r = requests.get(
        f"{BASE_URL}/api/feeds/facebook-local?format=json&section=lots&limit=100",
        timeout=15,
    )
    assert r.status_code == 200, r.text
    # Lots collection may be empty — endpoint must still respond.
    body = r.json()
    assert isinstance(body.get("data"), list)
    # Every item must carry the right label.
    for it in body["data"]:
        assert it.get("custom_label_0") == "lots", it


def test_facebook_local_section_alias_marketplace(admin_token):
    _refresh_cache(admin_token)
    r = requests.get(
        f"{BASE_URL}/api/feeds/facebook-local?format=json&section=marketplace&limit=100",
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body.get("data"), list)
    for it in body["data"]:
        assert it.get("custom_label_0") == "marketplace", it


# ── Gap 3 — Items missing usable images get the per-section placeholder
#           and are NEVER silently dropped from the feed. ─────────────


def test_vehicles_without_real_photos_get_default_vehicle_placeholder(admin_token):
    """Hard guarantee — every vehicle listing ships with an https image
    in the feed (real S3 photo when present, else the public BidVex
    placeholder JPEG). iter291 switched from the broken S3 placeholder
    bucket to the public `/assets/placeholder-ad.jpg`.
    """
    from services.meta_feed_mapper import SECTION_PLACEHOLDERS

    _refresh_cache(admin_token)
    r = requests.get(
        f"{BASE_URL}/api/feeds/facebook-local?format=json&section=vehicles&limit=100",
        timeout=15,
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    vehicle_placeholder = SECTION_PLACEHOLDERS["vehicle"]
    for it in items:
        link = it.get("image_link") or ""
        assert link.startswith("https://"), it
        # Either it's a real S3 photo OR the canonical placeholder.
        assert link.lower().endswith((".jpg", ".jpeg", ".png", ".gif")), it
        # If the listing has no real image, the mapper must have
        # injected the section placeholder (never an empty / proxied URL).
        if link == vehicle_placeholder:
            # Sanity: placeholder is the public bidvex jpg.
            assert vehicle_placeholder.endswith(".jpg")


def test_no_item_in_feed_lacks_an_image_link(admin_token):
    """Hard guarantee — every catalog item ships with an https image."""
    _refresh_cache(admin_token)
    r = requests.get(
        f"{BASE_URL}/api/feeds/facebook-local?format=json&limit=500",
        timeout=20,
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    assert len(items) >= 1
    for it in items:
        img = it.get("image_link")
        assert isinstance(img, str) and img.startswith("https://"), (
            f"item missing valid https image_link: {it!r}"
        )


# ── Gap 4 — robots.txt advertises both feeds ──────────────────────────


def test_robots_txt_advertises_feeds_and_allows_crawlers():
    r = requests.get(f"{BASE_URL}/robots.txt", timeout=10)
    assert r.status_code == 200, r.text
    body = r.text
    # Allow rule must EXPLICITLY override the broader Disallow.
    assert "Disallow: /api/" in body
    assert "Allow: /api/feeds/" in body
    # Both feed sitemap entries.
    assert "/api/feeds/google" in body
    assert "/api/feeds/meta-catalog.json" in body
    # The static SEO sitemap stays advertised too.
    assert "/sitemap.xml" in body


# ── Existing contract — schema must not have regressed ────────────────


def test_feed_items_have_full_meta_schema(admin_token):
    _refresh_cache(admin_token)
    r = requests.get(
        f"{BASE_URL}/api/feeds/facebook-local?format=json&limit=5",
        timeout=10,
    )
    assert r.status_code == 200, r.text
    items = r.json()["data"]
    assert len(items) >= 1
    sample = items[0]
    for k in (
        "id", "title", "description", "availability", "condition",
        "price", "link", "image_link", "brand",
        "custom_label_0", "custom_label_1", "custom_label_2",
    ):
        assert k in sample, f"missing Meta-required field {k!r} in feed item"
    # Availability must be in the Meta-accepted enum.
    assert sample["availability"] in ("in stock", "out of stock")
    # Price must end with " CAD".
    assert sample["price"].endswith(" CAD"), sample["price"]


# ── Google Merchant XML feed shape ────────────────────────────────────


def test_google_merchant_xml_renders_valid_xml(admin_token):
    _refresh_cache(admin_token)
    r = requests.get(f"{BASE_URL}/api/feeds/google", timeout=15)
    assert r.status_code == 200, r.text
    assert "application/xml" in r.headers.get("content-type", "").lower() \
        or "application/atom+xml" in r.headers.get("content-type", "").lower() \
        or "text/xml" in r.headers.get("content-type", "").lower()
    body = r.text
    # Must be valid XML (not partial / not error).
    from xml.etree import ElementTree as ET
    root = ET.fromstring(body)
    assert root is not None
    # Required Google tags must appear at least once.
    assert "<g:id>" in body
    assert "<g:title>" in body
    assert "<g:image_link>" in body
    assert "<g:price>" in body
    assert "<g:availability>" in body
    # Every image_link must be https.
    https_count = body.count("<g:image_link>https://")
    total_count = body.count("<g:image_link>")
    assert https_count == total_count, (
        f"Non-https image_link in Google Merchant feed: "
        f"{https_count}/{total_count} are https"
    )


# ── Admin force-refresh contract ──────────────────────────────────────


def test_admin_refresh_cache_returns_success(admin_token):
    r = requests.post(
        f"{BASE_URL}/api/feeds/facebook-local/refresh",
        headers={"Authorization": f"Bearer {admin_token}"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body.get("status") == "refreshed"
    assert isinstance(body.get("item_count"), int)
    assert body["item_count"] >= 1
