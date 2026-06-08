"""
iter291 — Image Lightbox z-index + Catalog Feed compliance regression.

Validates the two production bugs fixed in this sprint.

Bug 1 — Vehicle Image Lightbox close (×) button was behind the BidVex
header on mobile. The custom lightbox used `z-50` while the navbar
uses `z-[70]` and the banner uses `z-[80]`. We bump the lightbox to
`z-[100]` and the close button to `z-[9999]`. Frontend-only — covered
by an integration screenshot in CI.

Bug 2 — Google Merchant Center catalog feed errors:
    • Invalid region [region]  — 100% of products
    • Missing shipping info     — 100% of products
    • Unsupported image type    — 33.3% of products

This file asserts the three Google-spec gaps are closed at the XML
mapper layer (faster than reaching the live endpoint).
"""
import pytest


# ── Region must be ISO 3166-2 (e.g. CA-QC) ───────────────────────────


def test_google_feed_region_is_iso_3166_2():
    """`<g:region>` must include the country prefix (CA-QC, not just QC)."""
    from services.google_feed_mapper import meta_item_to_google_xml

    meta_item = {
        "id": "test-001",
        "title": "Test Vehicle",
        "description": "Test",
        "link": "https://bidvex.com/vehicle-auctions/test-001",
        "image_link": "https://example.com/image.jpg",
        "price": "5000.00 CAD",
        "availability": "in stock",
        "condition": "used",
        "brand": "BidVex Dealer",
        "city": "Montreal",
        "region": "QC",
        "country": "CA",
        "postal_code": "H2X3L7",
        "custom_label_0": "vehicle",
    }
    xml = meta_item_to_google_xml(meta_item)
    assert "<g:region>CA-QC</g:region>" in xml, (
        f"region must be ISO 3166-2 'CA-QC', not bare 'QC':\n{xml}"
    )
    # Bare 'QC' must NOT appear inside g:region (would re-trigger the
    # Google Merchant Center "Invalid region [region]" error).
    assert "<g:region>QC</g:region>" not in xml


def test_google_feed_region_passes_through_when_already_iso():
    """If the source already supplies `CA-ON`, don't double-prefix it."""
    from services.google_feed_mapper import meta_item_to_google_xml

    meta_item = {
        "id": "test-002",
        "title": "T",
        "image_link": "https://x.example.com/i.png",
        "region": "CA-ON",
        "country": "CA",
        "city": "Toronto",
        "custom_label_0": "marketplace",
    }
    xml = meta_item_to_google_xml(meta_item)
    assert "<g:region>CA-ON</g:region>" in xml
    assert "<g:region>CA-CA-ON</g:region>" not in xml


# ── Shipping block must always be present ────────────────────────────


def test_google_feed_shipping_block_always_present():
    """Every product must carry a `<g:shipping>` block so Google stops
    reporting `Missing shipping info in some countries`."""
    from services.google_feed_mapper import meta_item_to_google_xml

    # Even when city/region are missing, the country-level shipping
    # block must still emit so Google has a default shipping policy.
    minimal_item = {
        "id": "test-003",
        "title": "Minimal",
        "image_link": "https://example.com/x.jpg",
        "country": "CA",
    }
    xml = meta_item_to_google_xml(minimal_item)
    assert "<g:shipping>" in xml
    assert "<g:country>CA</g:country>" in xml
    assert "<g:service>Buyer Arranges Pickup</g:service>" in xml
    assert "<g:price>0.00 CAD</g:price>" in xml


# ── Image sanitization (no webp, no query strings) ───────────────────


def test_google_image_sanitizer_strips_query_params():
    from services.google_feed_mapper import _sanitize_google_image_url

    cleaned = _sanitize_google_image_url(
        "https://cdn.bidvex.com/image.jpg?w=800&format=webp"
    )
    assert cleaned == "https://cdn.bidvex.com/image.jpg"


def test_google_image_sanitizer_rejects_webp():
    from services.google_feed_mapper import _sanitize_google_image_url

    assert _sanitize_google_image_url("https://cdn.bidvex.com/foo.webp") == ""
    assert _sanitize_google_image_url("https://cdn.bidvex.com/foo.svg") == ""
    assert _sanitize_google_image_url("https://cdn.bidvex.com/foo.heic") == ""


def test_google_image_sanitizer_accepts_jpeg_png_gif():
    from services.google_feed_mapper import _sanitize_google_image_url

    for ext in (".jpg", ".jpeg", ".png", ".gif", ".JPG"):
        url = f"https://cdn.bidvex.com/foo{ext}"
        assert _sanitize_google_image_url(url) == url


def test_google_feed_falls_back_to_placeholder_when_image_unrecoverable():
    """If the listing's primary image is webp/svg/unsupported, the feed
    must substitute a publicly-accessible JPEG placeholder instead of
    emitting an empty `<g:image_link>` (which fails Google Merchant
    Center's mandatory-fields check)."""
    from services.google_feed_mapper import meta_item_to_google_xml

    item = {
        "id": "test-004",
        "title": "Webp Item",
        "image_link": "https://cdn.bidvex.com/foo.webp",
        "country": "CA",
        "region": "QC",
        "city": "Montreal",
        "custom_label_0": "vehicle",
    }
    xml = meta_item_to_google_xml(item)
    assert "<g:image_link>" in xml
    # No empty tag
    assert "<g:image_link></g:image_link>" not in xml
    # Placeholder must be a jpg
    assert ".jpg</g:image_link>" in xml


# ── Meta feed image filter ───────────────────────────────────────────


def test_meta_feed_image_filter_rejects_webp():
    """Meta now also rejects webp at the source so both feeds carry the
    same image URLs (Google sanitizer becomes a defence-in-depth)."""
    from services.meta_feed_mapper import _is_valid_image_url

    assert _is_valid_image_url("https://cdn.bidvex.com/img.jpg") is True
    assert _is_valid_image_url("https://cdn.bidvex.com/img.webp") is False
    assert _is_valid_image_url("https://cdn.bidvex.com/img.svg") is False
    # ?query is OK if path ends in jpg
    assert _is_valid_image_url("https://cdn.bidvex.com/img.jpg?w=800") is True


def test_meta_feed_normalize_strips_query():
    from services.meta_feed_mapper import _normalize_image_url

    assert (
        _normalize_image_url("https://cdn.bidvex.com/img.jpg?w=800&fmt=webp")
        == "https://cdn.bidvex.com/img.jpg"
    )
    assert (
        _normalize_image_url("https://cdn.bidvex.com/img.png#thumb")
        == "https://cdn.bidvex.com/img.png"
    )
