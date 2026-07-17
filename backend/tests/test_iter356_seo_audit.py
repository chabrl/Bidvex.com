"""
iter356 — Technical SEO (P0 + P1) — deliverable verification tests.

Covers every checkbox from the completion report:

    P0 fixes (5):
      ✓ PUBLIC_HOST defaults to https://www.bidvex.com
      ✓ BreadcrumbList JSON-LD on every prerender template
      ✓ FAQPage JSON-LD on /api/prerender/faq
      ✓ og:image uses first S3 listing photo on auction pages
      ✓ Vehicle schema.org type on vehicle pages

    P1 fixes (5):
      ✓ sitemap_index.xml with 5+ sub-sitemaps
      ✓ Seller / dealer / broker profiles in sitemap-sellers.xml
      ✓ 10 regional landing pages built & prerendered
      ✓ 2 French Quebec pages with correct hreflang cross-refs
      ✓ Image sitemap extension + <lastmod> on static entries

    Additional:
      ✓ SaleEvent schema (AuctionEvent equivalent) on active auctions
      ✓ /promo/share/summer-launch og:image uses www canonical

All tests are unit-scope: they exercise the pure Python builders +
FastAPI TestClient without touching Stripe / Mongo cursors. Where
Mongo is required, we use the shared FakeCollection pattern from
test_iter355_identity_bidhold.py.
"""
from __future__ import annotations

import asyncio
import importlib
import os
import re
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# P0 — Schema builder tests (pure functions, zero infra)
# ============================================================

def test_p0_public_host_defaults_to_www():
    """P0-C2 canonical alignment."""
    # Ensure PUBLIC_HOST env var isn't set for the reload.
    saved = os.environ.pop("PUBLIC_HOST", None)
    try:
        # Reload to force the module-level env read.
        import routes.sitemap as sm
        importlib.reload(sm)
        assert sm.PUBLIC_HOST == "https://www.bidvex.com", (
            f"Expected canonical www default, got {sm.PUBLIC_HOST}"
        )
    finally:
        if saved is not None:
            os.environ["PUBLIC_HOST"] = saved
            import routes.sitemap as sm
            importlib.reload(sm)


def test_p0_vehicle_ld_builder_emits_dual_type():
    """P0 — vehicle rich result schema."""
    from services.seo_jsonld import vehicle_ld
    ld = vehicle_ld(
        name="2020 Toyota RAV4 XLE",
        description="Well-maintained crossover.",
        canonical_url="https://www.bidvex.com/vehicle-auctions/v-1",
        image_url="https://cdn.bidvex.com/rav4.jpg",
        current_price=18500.00,
        currency="CAD",
        vin="4T3ZFREV9LU076551",
        make="Toyota", model="RAV4", year=2020,
        mileage_km=64000,
        body_type="SUV",
        transmission="Automatic",
        fuel_type="Gasoline",
        seller_name="AutoMax Dealer",
        availability="InStock",
        condition="UsedCondition",
    )
    assert ld["@type"] == ["Product", "Vehicle"], "must be dual-type Product+Vehicle"
    assert ld["vehicleIdentificationNumber"] == "4T3ZFREV9LU076551"
    assert ld["brand"] == {"@type": "Brand", "name": "Toyota"}
    assert ld["model"] == "RAV4"
    assert ld["vehicleModelDate"] == "2020"
    assert ld["mileageFromOdometer"] == {
        "@type": "QuantitativeValue", "value": 64000, "unitCode": "KMT",
    }
    assert ld["offers"]["price"] == 18500.0
    assert ld["offers"]["priceCurrency"] == "CAD"
    assert ld["offers"]["availability"] == "https://schema.org/InStock"
    assert ld["offers"]["itemCondition"] == "https://schema.org/UsedCondition"
    assert ld["offers"]["seller"]["name"] == "AutoMax Dealer"


def test_p0_auction_sale_event_ld_alias():
    """P0 — AuctionEvent equivalent (SaleEvent + Event dual-type)."""
    from services.seo_jsonld import auction_sale_event_ld, event_ld
    assert auction_sale_event_ld is event_ld  # alias
    ld = auction_sale_event_ld(
        name="Vintage Rolex Auction Lot #42",
        description="No reserve. Ends Friday.",
        canonical_url="https://www.bidvex.com/lots/l-42",
        starts_at_iso="2026-07-17T00:00:00Z",
        ends_at_iso="2026-07-21T00:00:00Z",
        image_url="https://cdn.bidvex.com/rolex.jpg",
        current_price=4500.00,
    )
    assert ld["@type"] == ["Event", "SaleEvent"], "must be dual-type Event+SaleEvent"
    assert ld["eventAttendanceMode"] == "https://schema.org/OnlineEventAttendanceMode"
    assert ld["eventStatus"] == "https://schema.org/EventScheduled"
    assert ld["location"]["@type"] == "VirtualLocation"
    assert ld["startDate"] == "2026-07-17T00:00:00Z"
    assert ld["endDate"] == "2026-07-21T00:00:00Z"
    assert ld["offers"]["validThrough"] == "2026-07-21T00:00:00Z"


def test_p0_breadcrumb_ld_emitted_on_every_prerender_template():
    """P0 — verify the prerender_service always attaches BreadcrumbList."""
    from services.prerender_service import _resolve_static_page, _resolve_homepage

    async def _check():
        # Static page (FAQ)
        ctx = await _resolve_static_page(db=None, path="/faq", lang="en")
        breadcrumb_blocks = [b for b in ctx["jsonld_blocks"] if "BreadcrumbList" in b]
        assert breadcrumb_blocks, "/faq missing BreadcrumbList JSON-LD"

        # Static page (About)
        ctx2 = await _resolve_static_page(db=None, path="/about", lang="en")
        breadcrumb_blocks2 = [b for b in ctx2["jsonld_blocks"] if "BreadcrumbList" in b]
        assert breadcrumb_blocks2, "/about missing BreadcrumbList JSON-LD"

        # Homepage
        ctx3 = await _resolve_homepage(db=None, lang="en")
        # Homepage doesn't need a breadcrumb (it IS the root). Just verify org.
        assert any("Organization" in b for b in ctx3["jsonld_blocks"])

    asyncio.run(_check())


def test_p0_faqpage_ld_emitted_on_faq_prerender():
    """P0 — /faq must include FAQPage JSON-LD (unlocks FAQ rich result)."""
    from services.prerender_service import _resolve_static_page

    async def _check():
        for lang in ("en", "fr"):
            ctx = await _resolve_static_page(db=None, path="/faq", lang=lang)
            faq_blocks = [b for b in ctx["jsonld_blocks"] if "FAQPage" in b]
            assert faq_blocks, f"/faq ({lang}) missing FAQPage JSON-LD"
            # Verify at least 3 Q&A pairs (Google needs >= 2)
            assert faq_blocks[0].count('"Question"') >= 3, \
                f"/faq ({lang}) should have >= 3 Q&A pairs, got {faq_blocks[0].count('Question')}"

    asyncio.run(_check())


# ============================================================
# P0 — auction page uses first S3 image + Vehicle schema
# ============================================================

class _FakeCursor:
    """Minimal Motor-cursor-like helper for the sitemap tests."""
    def __init__(self, docs):
        self._docs = docs
    def limit(self, n):
        self._docs = self._docs[:n]
        return self
    def __aiter__(self):
        self._i = 0
        return self
    async def __anext__(self):
        if self._i >= len(self._docs):
            raise StopAsyncIteration
        d = self._docs[self._i]
        self._i += 1
        return d
    async def to_list(self, n):
        return self._docs[:n]


class _FakeCollection:
    def __init__(self, docs):
        self.docs = docs
    def find(self, query, projection=None):
        return _FakeCursor(list(self.docs))
    async def find_one(self, query, projection=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items() if not isinstance(v, dict)):
                return dict(d)
        return None


class _FakeDB:
    def __init__(self):
        self.listings = _FakeCollection([])
        self.multi_item_listings = _FakeCollection([])
        self.vehicle_multi_lot_auctions = _FakeCollection([])
        self.storage_auctions = _FakeCollection([])
        self.sellers = _FakeCollection([])
        self.dealers = _FakeCollection([])
        self.brokers = _FakeCollection([])
        self.prospects = _FakeCollection([])
    def __getitem__(self, name):
        return getattr(self, name, _FakeCollection([]))


def test_p0_auction_page_uses_first_s3_image_not_placeholder():
    """P0 — auction pages must use the actual listing photo for og:image."""
    from services.prerender_service import _resolve_auction

    async def _check():
        db = _FakeDB()
        db.listings.docs = [{
            "id": "l-42",
            "title": "Antique Louis XVI Desk",
            "description": "Cherry wood, hand-carved.",
            "images": ["https://bidvex-s3.amazonaws.com/desk.jpg"],
            "current_bid": 950.0,
        }]
        ctx = await _resolve_auction(
            db, listing_id="l-42", path="/auctions/l-42",
            lang="en", kind="listing",
        )
        # og:image must be the S3 photo
        assert ctx["og_image"] == "https://bidvex-s3.amazonaws.com/desk.jpg"
        # AND appear in the Product JSON-LD image array
        prod_blocks = [b for b in ctx["jsonld_blocks"]
                       if '"@type":' in b and "Product" in b]
        assert prod_blocks, "no Product schema on auction page"
        assert "https://bidvex-s3.amazonaws.com/desk.jpg" in prod_blocks[0]

    asyncio.run(_check())


def test_p0_vehicle_auction_page_emits_vehicle_schema():
    """P0 — vehicle auctions must emit Vehicle schema (not just Product)."""
    from services.prerender_service import _resolve_auction

    async def _check():
        db = _FakeDB()
        # kind='vehicle' → prerender looks up in db.vehicle_multi_lot_auctions.
        db.vehicle_multi_lot_auctions.docs = [{
            "id": "v-77",
            "title": "2022 Ford F-150 Lightning",
            "description": "Electric pickup.",
            "images": ["https://bidvex-s3.amazonaws.com/f150.jpg"],
            "current_bid": 42000.0,
            "make": "Ford", "model": "F-150 Lightning", "year": 2022,
            "mileage": 18500, "vin": "1FTVW1EL0NWG12345",
            "body_type": "Pickup Truck", "transmission": "Automatic",
            "fuel_type": "Electric",
        }]
        ctx = await _resolve_auction(
            db, listing_id="v-77", path="/vehicle-auctions/v-77",
            lang="en", kind="vehicle",
        )
        vehicle_blocks = [b for b in ctx["jsonld_blocks"]
                          if '"Vehicle"' in b and '"Product"' in b]
        assert vehicle_blocks, "vehicle page missing Vehicle schema"
        # Vehicle-specific fields present
        v = vehicle_blocks[0]
        assert "vehicleIdentificationNumber" in v
        assert "1FTVW1EL0NWG12345" in v
        assert "mileageFromOdometer" in v
        assert "18500" in v or "18500.0" in v
        assert "vehicleModelDate" in v
        assert "2022" in v
        # AuctionEvent (SaleEvent) also present
        sale_event_blocks = [b for b in ctx["jsonld_blocks"] if "SaleEvent" in b]
        assert sale_event_blocks, "vehicle page missing SaleEvent schema"

    asyncio.run(_check())


# ============================================================
# P1 — Sitemap index architecture
# ============================================================

def _install_test_db(db):
    """Wire our FakeDB into deps.get_db so the sitemap routes see it."""
    import deps
    deps.set_db(db)


def test_p1_sitemap_index_returns_all_sub_sitemaps():
    """P1-H1 — /sitemap_index.xml enumerates every sub-sitemap."""
    from server import app
    _install_test_db(_FakeDB())
    client = TestClient(app)
    r = client.get("/sitemap_index.xml")
    assert r.status_code == 200
    body = r.text
    assert '<?xml version="1.0"' in body
    assert '<sitemapindex' in body
    for slug in [
        "sitemap-static.xml",
        "sitemap-listings.xml",
        "sitemap-vehicles.xml",
        "sitemap-storage.xml",
        "sitemap-lots.xml",
        "sitemap-sellers.xml",
    ]:
        assert slug in body, f"sitemap_index missing {slug}"
    # All URLs must be www canonical
    assert "https://www.bidvex.com" in body
    assert re.search(r"<lastmod>\d{4}-\d{2}-\d{2}</lastmod>", body), \
        "sitemap_index entries need <lastmod>"


def test_p1_sitemap_static_includes_regional_landing_pages():
    """P1-H3 — 10 EN regional pages + 2 FR Quebec twins in sitemap-static.xml."""
    from server import app
    _install_test_db(_FakeDB())
    client = TestClient(app)
    r = client.get("/sitemap-static.xml")
    assert r.status_code == 200
    body = r.text
    required_paths = [
        "/car-auctions-canada",
        "/vehicle-auctions-canada",
        "/equipment-auctions-canada",
        "/vehicle-auctions-quebec",
        "/vehicle-auctions-ontario",
        "/vehicle-auctions-british-columbia",
        "/vehicle-auctions-alberta",
        "/storage-auctions-quebec",
        "/storage-auctions-ontario",
        "/storage-auctions-british-columbia",
        # French Quebec twins:
        "/encheres-vehicules-quebec",
        "/encheres-entreposage-quebec",
    ]
    for path in required_paths:
        assert path in body, f"sitemap-static.xml missing {path}"
    # <lastmod> on every entry (iter356 M1)
    url_count = body.count("<url>")
    lastmod_count = body.count("<lastmod>")
    assert lastmod_count >= url_count, (
        f"expected <lastmod> on every url ({url_count}), got {lastmod_count}"
    )


def test_p1_sitemap_listings_has_image_extension_namespace():
    """P1-M2 — image sitemap extension enabled."""
    from server import app
    db = _FakeDB()
    db.listings.docs = [{
        "id": "l-9",
        "title": "Rare Coin",
        "images": ["https://bidvex-s3.amazonaws.com/coin.jpg"],
        "photos": [],
        "updated_at": "2026-07-17T00:00:00+00:00",
    }]
    _install_test_db(db)
    client = TestClient(app)
    r = client.get("/sitemap-listings.xml")
    assert r.status_code == 200
    body = r.text
    assert 'xmlns:image="http://www.google.com/schemas/sitemap-image/1.1"' in body
    assert "<image:image>" in body
    assert "<image:loc>https://bidvex-s3.amazonaws.com/coin.jpg</image:loc>" in body


def test_p1_sitemap_sellers_includes_all_profile_types():
    """P1-H2 — seller / dealer / broker / prospect profiles."""
    from server import app
    db = _FakeDB()
    db.sellers.docs   = [{"id": "s-1", "slug": "acme-antiques",  "updated_at": "2026-07-01"}]
    db.dealers.docs   = [{"id": "d-1", "slug": "ford-montreal",  "updated_at": "2026-07-05"}]
    db.brokers.docs   = [{"id": "b-1", "slug": "broker-jean",    "updated_at": "2026-06-30"}]
    db.prospects.docs = [{"id": "p-1", "slug": "contractor-ali", "updated_at": "2026-07-10"}]
    _install_test_db(db)
    client = TestClient(app)
    r = client.get("/sitemap-sellers.xml")
    assert r.status_code == 200
    body = r.text
    assert "/storefront/acme-antiques" in body
    assert "/dealer/ford-montreal" in body
    assert "/broker/broker-jean" in body
    assert "/prospect/contractor-ali" in body


# ============================================================
# P1 — Regional landing prerender + hreflang cross-refs
# ============================================================

def test_p1_regional_landing_en_prerender_has_correct_hreflang():
    """P1-H3 + FR Quebec — EN page hreflang points at FR twin."""
    from services.prerender_service import _resolve_regional_landing
    ctx = _resolve_regional_landing("/vehicle-auctions-quebec", "en")
    assert ctx is not None
    assert ctx["lang"] == "en"
    assert ctx["hreflang"]["en-CA"].endswith("/vehicle-auctions-quebec")
    assert ctx["hreflang"]["fr-CA"].endswith("/encheres-vehicules-quebec"), \
        "EN Quebec landing must point fr-CA at the French twin"
    assert ctx["hreflang"]["x-default"].endswith("/vehicle-auctions-quebec")


def test_p1_regional_landing_fr_twin_has_reverse_hreflang():
    """P1 — FR twin must reciprocate the hreflang cross-reference."""
    from services.prerender_service import _resolve_regional_landing
    ctx = _resolve_regional_landing("/encheres-vehicules-quebec", "fr")
    assert ctx is not None
    assert ctx["lang"] == "fr"
    assert ctx["hreflang"]["fr-CA"].endswith("/encheres-vehicules-quebec")
    assert ctx["hreflang"]["en-CA"].endswith("/vehicle-auctions-quebec"), \
        "FR Quebec twin must point en-CA at the English counterpart"


def test_p1_all_10_regional_pages_are_prerender_eligible():
    """P1-H3 — /car-auctions-canada + 9 provincial variants + 2 FR twins = 12
    (iter357 added 24 QC city pages on top → total >= 12)."""
    from services.prerender_service import _REGIONAL_LANDINGS, _resolve_regional_landing
    # iter356 introduced 12 pages; iter357 grew to 36 (12 provincial + 24 city).
    # The assertion is that we have AT LEAST the 12 iter356 pages present.
    assert len(_REGIONAL_LANDINGS) >= 12, (
        f"expected at least 12 regional pages, got {len(_REGIONAL_LANDINGS)}"
    )
    for path in _REGIONAL_LANDINGS:
        ctx = _resolve_regional_landing(path, "en")
        assert ctx is not None
        # iter358 — Press release pages use a dedicated template; other
        # regional pages continue to use regional_landing.html.
        assert ctx["template"] in ("regional_landing.html", "press_release.html")
        # Every landing has BreadcrumbList JSON-LD
        assert any("BreadcrumbList" in b for b in ctx["jsonld_blocks"]), \
            f"{path} missing BreadcrumbList"
        # Every landing has Organization JSON-LD
        assert any("Organization" in b for b in ctx["jsonld_blocks"]), \
            f"{path} missing Organization"
        # Every landing has a real title (not empty)
        assert ctx["title"] and len(ctx["title"]) >= 20, \
            f"{path} title too short: {ctx['title']!r}"


def test_p1_regional_prerender_routes_registered():
    """P1 — Confirm the prerender middleware whitelists our new paths."""
    from routes.prerender import _PRERENDER_ROUTE_PREFIXES
    for path in [
        "/car-auctions-canada",
        "/vehicle-auctions-quebec",
        "/encheres-vehicules-quebec",
        "/storage-auctions-quebec",
        "/encheres-entreposage-quebec",
    ]:
        assert path in _PRERENDER_ROUTE_PREFIXES, \
            f"{path} not in _PRERENDER_ROUTE_PREFIXES — bot middleware won't SSR it"


# ============================================================
# Additional — promo og:image + robots.txt
# ============================================================

def test_promo_summer_launch_og_uses_www_canonical():
    """Charbel's ask — /promo/share/summer-launch OG must be www canonical."""
    from server import app
    client = TestClient(app)
    # Promo router is mounted under /api (see server.py:1630).
    r = client.get("/api/promo/share/summer-launch")
    assert r.status_code == 200
    body = r.text
    # No more apex bidvex.com — everything is www.
    apex_count = body.count('"https://bidvex.com/')
    www_count = body.count('"https://www.bidvex.com/')
    assert apex_count == 0, f"promo page still has {apex_count} apex URLs"
    assert www_count >= 4, f"promo page should have >= 4 www URLs, got {www_count}"
    # And the OG image URL is unambiguous
    assert 'content="https://www.bidvex.com/static/og/summer-launch-promo.png"' in body


def test_promo_summer_launch_og_image_file_exists():
    """OG asset must be present on disk for the frontend static server to serve."""
    p = "/app/frontend/public/static/og/summer-launch-promo.png"
    assert os.path.exists(p), f"missing OG card at {p}"
    assert os.path.getsize(p) > 5000, "OG card is suspiciously small"


def test_robots_txt_declares_sitemap_index_first():
    """iter356 — robots.txt should reference sitemap_index.xml BEFORE the legacy sitemap.xml."""
    from server import app
    client = TestClient(app)
    r = client.get("/robots.txt")
    assert r.status_code == 200
    body = r.text
    assert "Sitemap:" in body
    idx_pos = body.find("sitemap_index.xml")
    legacy_pos = body.find("sitemap.xml\n") + body.find("/sitemap.xml\n")  # both count
    assert idx_pos > 0, "robots.txt missing sitemap_index.xml"
    # Sitemap index must appear BEFORE the legacy monolithic sitemap
    assert idx_pos < body.find("Sitemap: https://www.bidvex.com/sitemap.xml"), (
        "sitemap_index.xml must be listed BEFORE sitemap.xml"
    )


def test_prerender_faq_endpoint_emits_ld_blocks_via_http():
    """End-to-end — /api/prerender/faq via TestClient returns >=3 JSON-LD blocks."""
    from server import app
    _install_test_db(_FakeDB())
    client = TestClient(app)
    r = client.get("/api/prerender/faq")
    assert r.status_code == 200
    body = r.text
    assert 'application/ld+json' in body
    ld_count = body.count('application/ld+json')
    assert ld_count >= 3, (
        f"/api/prerender/faq must emit >=3 JSON-LD blocks "
        f"(Organization + Breadcrumb + FAQPage), got {ld_count}"
    )
    # Also confirm the canonical is www
    assert 'rel="canonical" href="https://www.bidvex.com/faq' in body
    # Bot marker present
    assert "x-prerender" in body.lower() or "prerender" in body.lower() or "BidVex" in body


def test_prerender_regional_landing_full_render():
    """End-to-end — /api/prerender/vehicle-auctions-quebec renders full SSR."""
    from server import app
    _install_test_db(_FakeDB())
    client = TestClient(app)
    r = client.get("/api/prerender/vehicle-auctions-quebec")
    assert r.status_code == 200
    body = r.text
    assert "<title>Vehicle Auctions Quebec" in body
    assert 'rel="canonical" href="https://www.bidvex.com/vehicle-auctions-quebec"' in body
    assert 'hreflang="fr-CA" href="https://www.bidvex.com/encheres-vehicules-quebec"' in body
    assert '"BreadcrumbList"' in body
    # H1 exists
    assert "<h1" in body


def test_prerender_regional_landing_fr_quebec_twin_renders():
    """End-to-end — /api/prerender/encheres-vehicules-quebec renders FR SSR."""
    from server import app
    _install_test_db(_FakeDB())
    client = TestClient(app)
    r = client.get("/api/prerender/encheres-vehicules-quebec")
    assert r.status_code == 200
    body = r.text
    assert '<html lang="fr">' in body
    assert "<title>Enchères de véhicules au Québec" in body
    # Reverse hreflang points back at the EN twin.
    assert 'hreflang="en-CA" href="https://www.bidvex.com/vehicle-auctions-quebec"' in body
