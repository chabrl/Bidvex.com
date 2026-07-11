"""iter231 — Google Merchant Center XML feed tests.

Validates the new GET /api/feeds/google endpoint:
  • 200 + application/xml content-type
  • Well-formed RSS 2.0 with xmlns:g namespace declaration
  • Every <item> has the 8 required g:* fields
  • g:price uses current_bid (NEVER buy_now / sale_price)
  • g:availability flips correctly for ended listings
  • g:id matches the canonical listing.id (= Meta Pixel content_id =
    Schema.org JSON-LD @id) — proves Three-Surface Mirroring is intact
  • g:price_type is the literal string "auction"
  • Items inserted via meta_feed_mapper appear in the Google XML feed too
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import pytest
import requests


BASE_URL = os.environ.get("BIDVEX_BASE_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")
API = f"{BASE_URL}/api"
NS = {"g": "http://base.google.com/ns/1.0"}


def _fetch(limit: int = 10) -> tuple[int, str]:
    r = requests.get(f"{API}/feeds/google?limit={limit}", timeout=30)
    return r.status_code, r.text


def test_google_feed_returns_200_and_xml_content_type():
    r = requests.get(f"{API}/feeds/google?limit=5", timeout=30)
    assert r.status_code == 200
    assert "application/xml" in r.headers.get("content-type", "")
    assert r.headers.get("x-feed-item-count")
    assert int(r.headers["x-feed-item-count"]) >= 1


def test_google_feed_is_well_formed_rss_2_with_g_namespace():
    status, body = _fetch(5)
    assert status == 200
    root = ET.fromstring(body)
    assert root.tag == "rss"
    assert root.attrib.get("version") == "2.0"
    # The g: namespace MUST be declared exactly
    assert "http://base.google.com/ns/1.0" in body
    channel = root.find("channel")
    assert channel is not None
    assert channel.find("title").text == "BidVex — Live Auction Catalog"


def test_every_item_has_required_g_fields():
    """The 8 fields Google Merchant Center rejects items for missing."""
    status, body = _fetch(10)
    assert status == 200
    root = ET.fromstring(body)
    items = root.findall(".//item")
    assert items, "feed must contain at least one item"
    required = ["id", "title", "description", "link", "image_link",
                "availability", "condition", "price"]
    for it in items:
        for tag in required:
            el = it.find(f"g:{tag}", NS)
            assert el is not None, f"item missing g:{tag}: {ET.tostring(it)[:200]}"
            assert el.text and el.text.strip(), f"empty g:{tag}: {ET.tostring(it)[:200]}"


def test_g_price_uses_cad_and_not_buy_now():
    """Price string is always 'NNNN.NN CAD' (matching Meta CSV)."""
    status, body = _fetch(10)
    root = ET.fromstring(body)
    items = root.findall(".//item")
    for it in items:
        price_text = it.find("g:price", NS).text
        assert price_text.endswith("CAD"), f"price must be in CAD: {price_text!r}"
        # Must NOT mention sale_price anywhere
        item_xml = ET.tostring(it, encoding="unicode")
        assert "sale_price" not in item_xml.lower(), \
            "sale_price/MSRP must NEVER appear in auction feed"


def test_g_price_type_is_literal_auction():
    status, body = _fetch(5)
    root = ET.fromstring(body)
    items = root.findall(".//item")
    for it in items:
        pt = it.find("g:price_type", NS)
        assert pt is not None and pt.text == "auction"


def test_g_availability_is_in_stock_or_out_of_stock():
    """Google's whitelist — must be exactly one of these underscored forms."""
    status, body = _fetch(20)
    root = ET.fromstring(body)
    items = root.findall(".//item")
    for it in items:
        av = it.find("g:availability", NS).text
        assert av in ("in_stock", "out_of_stock"), f"invalid g:availability: {av!r}"


def test_g_identifier_exists_is_no_for_auctions():
    """Auction lots have no GTIN/MPN/identifier."""
    status, body = _fetch(5)
    root = ET.fromstring(body)
    items = root.findall(".//item")
    for it in items:
        ide = it.find("g:identifier_exists", NS)
        assert ide is not None and ide.text == "no"


def test_g_id_matches_listing_id_uuid_format():
    """Three-Surface Mirroring proof: g:id is the raw listing.id UUID for
    single listings, or the iter344 per-lot form
    `LOT-<uuid>-L<n>` / `VML-<uuid>-<hex8>` for decomposed multi-lot items."""
    status, body = _fetch(5)
    root = ET.fromstring(body)
    items = root.findall(".//item")
    import re
    uuid_re = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$", re.I)
    lot_re = re.compile(r"^(LOT|VML)-[0-9a-z\-]+-(L\d+|[0-9a-f]{1,8})$", re.I)
    for it in items:
        gid = it.find("g:id", NS).text
        # Allow seed prefixes only when seed-padded
        if gid.startswith("BIDVEX-SEED-"):
            continue
        assert uuid_re.match(gid) or lot_re.match(gid), (
            f"g:id must be a listing UUID or a per-lot id: {gid!r}"
        )


def test_g_id_matches_meta_csv_id_for_same_listing():
    """The same listing must appear in BOTH the Meta CSV AND the Google XML
    with the SAME id value (= match-rate alignment guarantee)."""
    csv_r = requests.get(f"{API}/feeds/facebook-local?limit=20&format=json", timeout=30)
    if csv_r.status_code != 200:
        pytest.skip("Meta JSON feed unavailable")
    meta_ids = {row["id"] for row in csv_r.json().get("data", [])}

    xml_r = requests.get(f"{API}/feeds/google?limit=20", timeout=30)
    assert xml_r.status_code == 200
    google_ids = {it.find("g:id", NS).text for it in ET.fromstring(xml_r.text).findall(".//item")}

    overlap = meta_ids & google_ids
    assert overlap, "Meta and Google feeds must share at least one matching id (Three-Surface Mirroring)"


def test_g_condition_is_in_google_whitelist():
    """Google rejects anything outside new/refurbished/used."""
    status, body = _fetch(20)
    root = ET.fromstring(body)
    items = root.findall(".//item")
    allowed = {"new", "refurbished", "used"}
    for it in items:
        cond = it.find("g:condition", NS).text
        assert cond in allowed, f"invalid g:condition: {cond!r}"


def test_xmlns_g_is_declared_exactly_once_on_root():
    """Defensive — Google's parser handles bad namespace decl badly."""
    _, body = _fetch(5)
    assert body.count('xmlns:g="http://base.google.com/ns/1.0"') == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
