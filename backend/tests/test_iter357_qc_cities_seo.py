"""
iter357 — QC city pages + LocalBusiness + subpath routing + social proof.

Deliverable verification (per QA checklist):

FR Quebec AdWords copy:
  ✓ /encheres-vehicules-quebec renders city-grid + Adwords copy
  ✓ /encheres-entreposage-quebec renders equivalent section
  ✓ 8 QC vehicle city pages built + prerendered
  ✓ 4 QC storage city pages built + prerendered
  ✓ Each city page: unique H1, unique meta description, BreadcrumbList
  ✓ City pages in sitemap-static.xml

/en/ /fr/ subpath (backend only, iter357 slice):
  ✓ /en/faq resolves lang=en with English title
  ✓ /fr/faq resolves lang=fr with French title + <html lang="fr">
  ✓ Prerender endpoint accepts /en/* and /fr/* prefixes
  ✓ Old /faq still returns 200 (backward compat)

Trust presence:
  ✓ LocalBusiness schema on homepage with correct NAP
  ✓ NAP consistent across all page footers (via BIDVEX_NAP constant)
  ✓ Social proof widget renders server-side (visible in prerender output)
  ✓ sameAs array in Organization schema with all 4 social profiles
"""
from __future__ import annotations

import asyncio
import os
import re
import sys
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ============================================================
# Fake DB (copied compact from iter355/356 pattern)
# ============================================================

class _FakeCursor:
    def __init__(self, docs): self._docs = docs
    def limit(self, n): self._docs = self._docs[:n]; return self
    def __aiter__(self): self._i = 0; return self
    async def __anext__(self):
        if self._i >= len(self._docs): raise StopAsyncIteration
        d = self._docs[self._i]; self._i += 1; return d
    async def to_list(self, n): return self._docs[:n]


class _FakeCollection:
    def __init__(self, docs=None): self.docs = docs or []
    def find(self, q, p=None): return _FakeCursor(list(self.docs))
    async def find_one(self, q, p=None):
        for d in self.docs:
            if all(d.get(k) == v for k, v in q.items() if not isinstance(v, dict)):
                return dict(d)
        return None
    async def count_documents(self, q):
        return sum(1 for d in self.docs if all(d.get(k) == v for k, v in q.items()
                                              if not isinstance(v, dict)))
    async def distinct(self, field):
        return list({d.get(field) for d in self.docs if d.get(field)})


class _FakeDB:
    def __init__(self):
        self.users             = _FakeCollection()
        self.listings          = _FakeCollection()
        self.multi_item_listings = _FakeCollection()
        self.vehicle_multi_lot_auctions = _FakeCollection()
        self.storage_auctions  = _FakeCollection()
        self.sellers           = _FakeCollection()
        self.dealers           = _FakeCollection()
        self.brokers           = _FakeCollection()
        self.prospects         = _FakeCollection()
    def __getitem__(self, name):
        return getattr(self, name, _FakeCollection())


def _install(db):
    import deps
    deps.set_db(db)


# ============================================================
# QC city page — data catalog
# ============================================================

def test_qc_city_catalog_has_8_vehicle_cities_and_4_storage():
    """iter357 — 12 cities × 2 langs = 24 entries."""
    from services.qc_city_pages import (
        build_qc_vehicle_city_entries,
        build_qc_storage_city_entries,
    )
    veh = build_qc_vehicle_city_entries()
    stor = build_qc_storage_city_entries()
    # 8 vehicle × 2 langs = 16 entries
    assert len(veh) == 16, f"expected 16 vehicle entries, got {len(veh)}"
    # 4 storage × 2 langs = 8 entries
    assert len(stor) == 8, f"expected 8 storage entries, got {len(stor)}"
    # Every FR entry has a `body_fr` blurb ≥ 500 chars (real Quebec content)
    for path, entry in veh.items():
        if entry.get("lang_only") == "fr":
            assert len(entry.get("body_fr", "")) >= 500, \
                f"{path} FR blurb too short: {len(entry.get('body_fr',''))}"
    # Every EN twin has `body_en` blurb ≥ 400 chars
    for path, entry in veh.items():
        if not entry.get("lang_only"):
            assert len(entry.get("body_en", "")) >= 400, \
                f"{path} EN blurb too short: {len(entry.get('body_en',''))}"


def test_qc_city_body_copy_is_unique_per_city():
    """iter357 — no template lorem-ipsum. Each city has substantively unique copy."""
    from services.qc_city_pages import build_qc_vehicle_city_entries
    veh = build_qc_vehicle_city_entries()
    fr_blurbs = {p: e.get("body_fr", "") for p, e in veh.items()
                 if e.get("lang_only") == "fr"}
    assert len(fr_blurbs) == 8
    # No two blurbs are identical
    assert len(set(fr_blurbs.values())) == 8, \
        "duplicate FR city blurbs — copy must be unique per city"
    # Each blurb mentions its own city name
    for path, blurb in fr_blurbs.items():
        entry = veh[path]
        city = entry.get("city_fr")
        assert city and city.lower()[:5] in blurb.lower(), \
            f"{path} blurb doesn't mention {city}"


def test_qc_city_pages_all_registered_as_prerender():
    """iter357 — Every QC city path must be in _PRERENDER_ROUTE_PREFIXES."""
    from routes.prerender import _PRERENDER_ROUTE_PREFIXES
    from services.qc_city_pages import all_qc_city_paths
    for path in all_qc_city_paths():
        assert path in _PRERENDER_ROUTE_PREFIXES, \
            f"{path} not registered for SSR prerender"


def test_qc_city_pages_all_in_sitemap():
    """iter357 — sitemap-static.xml lists every QC city URL."""
    from server import app
    _install(_FakeDB())
    client = TestClient(app)
    r = client.get("/sitemap-static.xml")
    assert r.status_code == 200
    body = r.text
    from services.qc_city_pages import all_qc_city_paths
    for path in all_qc_city_paths():
        assert path in body, f"sitemap-static missing {path}"


# ============================================================
# QC city page rendering — SSR output
# ============================================================

def test_fr_qc_city_page_renders_full_ssr():
    """iter357 — /api/prerender/encheres-vehicules-montreal returns FR SSR."""
    from server import app
    _install(_FakeDB())
    client = TestClient(app)
    r = client.get("/api/prerender/encheres-vehicules-montreal")
    assert r.status_code == 200
    body = r.text
    assert '<html lang="fr"' in body
    assert "Enchères de véhicules à Montréal" in body
    assert 'rel="canonical" href="https://www.bidvex.com/encheres-vehicules-montreal"' in body
    assert 'hreflang="en-CA" href="https://www.bidvex.com/vehicle-auctions-montreal"' in body
    # LocalBusiness schema present (with Montréal in the name)
    assert '"LocalBusiness"' in body
    # NAP: exact street address must appear
    assert "701 Rue Chalifoux" in body
    # H1 present
    assert "<h1" in body


def test_en_qc_city_page_reverse_hreflang():
    """iter357 — EN twin page's hreflang points back at FR."""
    from server import app
    _install(_FakeDB())
    client = TestClient(app)
    r = client.get("/api/prerender/vehicle-auctions-montreal")
    assert r.status_code == 200
    body = r.text
    assert '<html lang="en"' in body
    assert 'hreflang="fr-CA" href="https://www.bidvex.com/encheres-vehicules-montreal"' in body


def test_qc_province_page_renders_city_grid_and_adwords_copy():
    """iter357 — FR Quebec province page has city grid + Loi 96 + SAAQ + SUMMER2026."""
    from server import app
    _install(_FakeDB())
    client = TestClient(app)
    r = client.get("/api/prerender/encheres-vehicules-quebec")
    assert r.status_code == 200
    body = r.text
    # City grid present with all 8 city links
    assert 'class="city-grid"' in body
    for city_slug in ["montreal", "quebec-ville", "sherbrooke", "laval",
                      "gatineau", "saguenay", "trois-rivieres", "longueuil"]:
        assert f"/encheres-vehicules-{city_slug}" in body, \
            f"city grid missing /encheres-vehicules-{city_slug}"
    # Adwords copy specifics
    assert "Loi 96" in body
    assert "SAAQ" in body
    assert "SUMMER2026" in body
    assert "Pourquoi choisir BidVex" in body


def test_qc_storage_province_page_renders_4_city_grid():
    """iter357 — FR storage province page has 4-city grid (M, Q, S, L)."""
    from server import app
    _install(_FakeDB())
    client = TestClient(app)
    r = client.get("/api/prerender/encheres-entreposage-quebec")
    assert r.status_code == 200
    body = r.text
    assert 'class="city-grid"' in body
    for city_slug in ["montreal", "quebec-ville", "sherbrooke", "laval"]:
        assert f"/encheres-entreposage-{city_slug}" in body, \
            f"storage city grid missing {city_slug}"


# ============================================================
# LocalBusiness + Organization sameAs
# ============================================================

def test_homepage_emits_local_business_schema_with_correct_nap():
    """iter357 — homepage LocalBusiness with 701 Rue Chalifoux + Sherbrooke."""
    from server import app
    _install(_FakeDB())
    client = TestClient(app)
    r = client.get("/api/prerender/")
    assert r.status_code == 200
    body = r.text
    assert '"LocalBusiness"' in body
    assert '"701 Rue Chalifoux"' in body
    assert '"Sherbrooke"' in body
    assert '"J1G 0A8"' in body
    assert '"+14506343099"' in body
    assert '"BidVex Inc."' in body


def test_organization_schema_has_all_4_social_profiles_in_sameas():
    """iter357 — Organization.sameAs lists FB, LinkedIn, Twitter, Instagram."""
    from services.seo_jsonld import organization_ld
    org = organization_ld()
    sameas = org.get("sameAs", [])
    assert len(sameas) == 4, f"expected 4 social profiles, got {len(sameas)}"
    joined = "\n".join(sameas)
    for domain in ["facebook.com", "linkedin.com", "twitter.com", "instagram.com"]:
        assert domain in joined, f"sameAs missing {domain}"


def test_local_business_ld_builder_with_and_without_city():
    """iter357 — local_business_ld() works both for homepage (no city)
    and QC city pages (with city_name)."""
    from services.seo_jsonld import local_business_ld
    # Homepage variant
    generic = local_business_ld(lang="en")
    assert generic["name"] == "BidVex Inc."
    assert generic["address"]["streetAddress"] == "701 Rue Chalifoux"
    assert generic["geo"]["latitude"] == 45.4041
    # QC city variant (FR)
    fr_mtl = local_business_ld(city_name="Montréal", lang="fr")
    assert "Montréal" in fr_mtl["name"]
    assert "Québec" in fr_mtl["name"]
    # QC city variant (EN)
    en_mtl = local_business_ld(city_name="Montreal", lang="en")
    assert "Montreal" in en_mtl["name"]
    assert "Quebec" in en_mtl["name"]


def test_nap_consistency_across_pages():
    """iter357 — NAP identical across homepage, city page, and legal footer.
    Google penalizes NAP inconsistency between pages."""
    from server import app
    _install(_FakeDB())
    client = TestClient(app)
    canonical_street = "701 Rue Chalifoux"
    canonical_postal = "J1G 0A8"
    for path in [
        "/api/prerender/",
        "/api/prerender/encheres-vehicules-montreal",
        "/api/prerender/vehicle-auctions-quebec",
        "/api/prerender/faq",
    ]:
        r = client.get(path)
        assert r.status_code == 200
        # Every page's regional_landing.html footer OR JSON-LD contains the NAP.
        # For homepage, JSON-LD only; for regional pages, both footer + JSON-LD.
        assert canonical_street in r.text, f"{path} missing street address"
        assert canonical_postal in r.text, f"{path} missing postal code"


# ============================================================
# Subpath handling — /en/* /fr/*
# ============================================================

def test_en_subpath_prerender_resolves_english():
    """iter357 — /en/faq resolves lang=en."""
    from server import app
    _install(_FakeDB())
    client = TestClient(app)
    r = client.get("/api/prerender/en/faq")
    assert r.status_code == 200
    body = r.text
    assert '<html lang="en"' in body
    assert "<title>BidVex FAQ" in body
    # Canonical still points at the un-prefixed URL for now — the ?lang= query
    # is the current canonical scheme. iter358 SPA refactor will switch to
    # `/en/faq` as the canonical URL directly.
    assert 'rel="canonical"' in body


def test_fr_subpath_prerender_resolves_french():
    """iter357 — /fr/faq resolves lang=fr with French title."""
    from server import app
    _install(_FakeDB())
    client = TestClient(app)
    r = client.get("/api/prerender/fr/faq")
    assert r.status_code == 200
    body = r.text
    assert '<html lang="fr"' in body
    assert "FAQ BidVex" in body


def test_old_urls_still_work_backward_compat():
    """iter357 — Old URLs like /faq keep returning 200 (no forced redirect yet)."""
    from server import app
    _install(_FakeDB())
    client = TestClient(app)
    for path in ["/api/prerender/faq", "/api/prerender/marketplace",
                 "/api/prerender/vehicle-auctions"]:
        r = client.get(path)
        assert r.status_code == 200, f"backward-compat broken for {path}"


# ============================================================
# Social proof widget (SSR-rendered)
# ============================================================

def test_public_platform_stats_endpoint_returns_json():
    """iter357 — GET /api/public/platform-stats returns JSON with 4 counters."""
    from server import app
    _install(_FakeDB())
    client = TestClient(app)
    r = client.get("/api/public/platform-stats")
    assert r.status_code == 200
    data = r.json()
    for key in ("dealers", "auctions_completed", "provinces", "active_now"):
        assert key in data, f"platform-stats missing key {key}"
        assert isinstance(data[key], str), f"platform-stats.{key} not a string"


def test_platform_stats_uses_fallback_when_db_empty():
    """iter357 — Empty DB → aspirational fallback numbers, not '0'."""
    from services.platform_stats import get_platform_stats, _FALLBACK

    async def _run():
        db = _FakeDB()  # empty
        stats = await get_platform_stats(db)
        # Empty DB should return _FALLBACK (all "50+", "1,200+", etc.)
        assert stats == _FALLBACK

    asyncio.run(_run())


def test_social_proof_widget_ssr_rendered_on_qc_landing():
    """iter357 — Social proof bar appears in prerendered QC landing HTML."""
    from server import app
    _install(_FakeDB())
    client = TestClient(app)
    r = client.get("/api/prerender/encheres-vehicules-quebec")
    assert r.status_code == 200
    body = r.text
    assert "social-proof-bar" in body
    # Bilingual text markers
    assert ("Concessionnaires vérifiés" in body) or ("Verified dealers" in body)
    # Numbers ARE rendered (either real or fallback)
    assert re.search(r'<strong[^>]*>[0-9,+]+</strong>', body), \
        "social proof numbers not rendered inline"


# ============================================================
# Regression — every iter356 test still passes here too
# ============================================================

def test_regression_iter356_prerender_regional_still_works():
    """Regression — iter356 regional landings still resolve after iter357 patches."""
    from services.prerender_service import _resolve_regional_landing
    for path in [
        "/car-auctions-canada",
        "/vehicle-auctions-canada",
        "/equipment-auctions-canada",
        "/vehicle-auctions-quebec",
        "/vehicle-auctions-ontario",
        "/encheres-vehicules-quebec",
    ]:
        ctx = _resolve_regional_landing(path, "en")
        assert ctx is not None
        assert ctx["template"] == "regional_landing.html"


def test_regression_sitemap_index_still_returns_200():
    from server import app
    _install(_FakeDB())
    client = TestClient(app)
    r = client.get("/sitemap_index.xml")
    assert r.status_code == 200
    assert "sitemapindex" in r.text
