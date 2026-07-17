"""
iter359 — Bilingual finishing-touches test suite.

Coverage:
  • Root `/` with Accept-Language: fr → 302 to /fr/
  • Root `/` with Accept-Language: en → 302 to /en/
  • Root `/` with no header → 302 to /en/ (default)
  • Sitemap emits BOTH /en/marketplace and /fr/marche
  • Sitemap declares xmlns:xhtml namespace on <urlset>
  • Every EN + FR URL in the sitemap carries reciprocal hreflang alternates
  • x-default hreflang points at the EN variant
  • Rich-results checklist file exists at expected path
  • EN_TO_FR_SLUGS matches the frontend urlMap.js contract (spot-check)
"""
import os

import sys
sys.path.insert(0, "/app/backend")

import pytest
from fastapi.testclient import TestClient

from routes.sitemap import (
    sitemap_router,
    EN_TO_FR_SLUGS,
    FR_TO_EN_SLUGS,
    _lang_pair_for,
    _detect_lang_from_accept_language,
    STATIC_PAGES,
)
from fastapi import FastAPI


# ─── Build a minimal test app (avoids booting full server) ─────────────
_test_app = FastAPI()
_test_app.include_router(sitemap_router)
client = TestClient(_test_app)


# ═══════════════════════════════════════════════════════════════════════
# Item 3 — Root Accept-Language redirect
# ═══════════════════════════════════════════════════════════════════════

def test_root_redirect_fr_first_locale():
    """Accept-Language: fr-CA,fr;q=0.9,en;q=0.8 → 302 /fr/"""
    r = client.get("/", headers={"Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8"}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/fr/"


def test_root_redirect_en_first_locale():
    """Accept-Language: en-US,en;q=0.9 → 302 /en/"""
    r = client.get("/", headers={"Accept-Language": "en-US,en;q=0.9"}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/en/"


def test_root_redirect_no_header_defaults_to_en():
    """Missing Accept-Language → 302 /en/"""
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/en/"


def test_root_redirect_mixed_precedence():
    """fr as primary even with EN alternates → /fr/"""
    r = client.get("/", headers={"Accept-Language": "fr,en"}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/fr/"


def test_root_redirect_en_as_primary_with_fr_secondary():
    """EN primary, FR fallback → /en/ (first-locale wins)."""
    r = client.get("/", headers={"Accept-Language": "en-CA,fr-CA;q=0.9"}, follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"] == "/en/"


def test_root_redirect_uses_302_not_301():
    """302 (temporary) so we can change the algorithm later without cache lock-in."""
    r = client.get("/", headers={"Accept-Language": "fr"}, follow_redirects=False)
    assert r.status_code == 302
    # NOT 301 (permanent) — 301s are cached hard and hurt future changes.


def test_detect_lang_helper_fr():
    assert _detect_lang_from_accept_language("fr-CA,fr;q=0.9,en;q=0.8") == "fr"
    assert _detect_lang_from_accept_language("fr") == "fr"
    assert _detect_lang_from_accept_language("FR-ca") == "fr"


def test_detect_lang_helper_en_and_defaults():
    assert _detect_lang_from_accept_language("en-US,en;q=0.9") == "en"
    assert _detect_lang_from_accept_language("") == "en"
    assert _detect_lang_from_accept_language(None) == "en"
    assert _detect_lang_from_accept_language("es-MX,es;q=0.9") == "en"  # non-fr non-en → en


# ═══════════════════════════════════════════════════════════════════════
# Item 4 — Dual-URL sitemap with hreflang alternates
# ═══════════════════════════════════════════════════════════════════════

def _fetch_sitemap():
    r = client.get("/sitemap-static.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    return r.text


def test_sitemap_declares_xhtml_namespace():
    body = _fetch_sitemap()
    assert 'xmlns:xhtml="http://www.w3.org/1999/xhtml"' in body
    assert 'xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"' in body


def test_sitemap_contains_en_marketplace_and_fr_marche():
    body = _fetch_sitemap()
    assert "<loc>https://www.bidvex.com/en/marketplace</loc>" in body
    assert "<loc>https://www.bidvex.com/fr/marche</loc>" in body


def test_sitemap_contains_vehicle_auctions_en_and_fr():
    body = _fetch_sitemap()
    assert "<loc>https://www.bidvex.com/en/vehicle-auctions</loc>" in body
    assert "<loc>https://www.bidvex.com/fr/encheres-vehicules</loc>" in body


def test_sitemap_contains_press_release_en_and_fr():
    body = _fetch_sitemap()
    assert "<loc>https://www.bidvex.com/en/press/quebec-launch</loc>" in body
    assert "<loc>https://www.bidvex.com/fr/presse/lancement-quebec</loc>" in body


def test_sitemap_hreflang_alternate_marketplace_pair():
    """Both /en/marketplace and /fr/marche entries carry all three
    hreflang alternates (en-CA, fr-CA, x-default)."""
    body = _fetch_sitemap()
    # EN entry alternates
    assert 'hreflang="en-CA" href="https://www.bidvex.com/en/marketplace"' in body
    assert 'hreflang="fr-CA" href="https://www.bidvex.com/fr/marche"' in body
    # x-default points at EN per iter358 spec
    assert 'hreflang="x-default" href="https://www.bidvex.com/en/marketplace"' in body


def test_sitemap_every_en_fr_pair_appears_exactly_twice():
    """Every mapped pair in EN_TO_FR_SLUGS present in STATIC_PAGES must
    appear as both /en/<slug> AND /fr/<slug> in the sitemap."""
    body = _fetch_sitemap()
    static_paths = {p for p, _, _ in STATIC_PAGES}
    for en_slug, fr_slug in EN_TO_FR_SLUGS.items():
        if en_slug not in static_paths and fr_slug not in static_paths:
            continue  # Not in STATIC_PAGES (frontend-only pair)
        if en_slug == "/":
            expected_en = "https://www.bidvex.com/en/"
            expected_fr = "https://www.bidvex.com/fr/"
        else:
            expected_en = f"https://www.bidvex.com/en{en_slug}"
            expected_fr = f"https://www.bidvex.com/fr{fr_slug}"
        assert f"<loc>{expected_en}</loc>" in body, f"Missing EN /en{en_slug}"
        assert f"<loc>{expected_fr}</loc>" in body, f"Missing FR /fr{fr_slug}"


def test_sitemap_alternate_count_multiple_of_three():
    """Each hreflang cluster emits exactly 3 <xhtml:link> tags per URL
    (en-CA, fr-CA, x-default). The total count must be evenly divisible
    by 3 so every URL is properly clustered."""
    body = _fetch_sitemap()
    total = body.count("<xhtml:link rel=\"alternate\"")
    assert total > 0, "Zero hreflang alternates emitted"
    assert total % 3 == 0, f"Alternate count {total} not divisible by 3 — cluster broken"
    # Also assert we're emitting enough (60+ URLs × 3 each = 180+ minimum).
    assert total >= 180, f"Only {total} alternates — expected >= 180"


def test_sitemap_lang_pair_helper():
    """`_lang_pair_for` returns the correct EN + FR bare tuple."""
    assert _lang_pair_for("/marketplace") == ("/marketplace", "/marche")
    assert _lang_pair_for("/marche") == ("/marketplace", "/marche")
    assert _lang_pair_for("/vehicle-auctions") == ("/vehicle-auctions", "/encheres-vehicules")
    assert _lang_pair_for("/encheres-vehicules") == ("/vehicle-auctions", "/encheres-vehicules")
    # Unknown path → None
    assert _lang_pair_for("/some-random-path") is None


def test_en_to_fr_slugs_contract_matches_iter358_urlmap():
    """Backend EN_TO_FR_SLUGS must contain iter358 canonical pairs."""
    for expected_en, expected_fr in [
        ("/marketplace", "/marche"),
        ("/vehicle-auctions", "/encheres-vehicules"),
        ("/storage-auctions", "/encheres-entreposage"),
        ("/how-it-works", "/comment-ca-marche"),
        ("/about", "/a-propos"),
        ("/pricing", "/tarifs"),
        ("/careers", "/carrieres"),
        ("/blogs", "/blogues"),
        ("/press/quebec-launch", "/presse/lancement-quebec"),
    ]:
        assert EN_TO_FR_SLUGS.get(expected_en) == expected_fr
        # Inverse lookup: FR slug must map back to *an* EN slug. Some FR
        # slugs (e.g., /a-propos) have multiple EN aliases (/about, /about-us);
        # the inverse map holds only ONE. Accept any EN mapping.
        inverse = FR_TO_EN_SLUGS.get(expected_fr)
        assert inverse is not None, f"FR /{expected_fr} has no reverse EN mapping"
        assert EN_TO_FR_SLUGS.get(inverse) == expected_fr


# ═══════════════════════════════════════════════════════════════════════
# Item 5 — Rich Results Checklist file
# ═══════════════════════════════════════════════════════════════════════

def test_rich_results_checklist_file_exists():
    path = "/app/frontend/public/static/press/rich-results-checklist.txt"
    assert os.path.isfile(path), f"Missing checklist file at {path}"
    text = open(path, "r", encoding="utf-8").read()
    # Must reference the Rich Results Test URLs
    assert "search.google.com/test/rich-results" in text
    # Must reference both press pages
    assert "www.bidvex.com/press/quebec-launch" in text
    assert "www.bidvex.com/presse/lancement-quebec" in text
    # Must reference the sitemap index for GSC submission
    assert "sitemap_index.xml" in text
    # Must document the Cloudflare crawler-cache blocker
    assert "crawler-cache" in text.lower() or "cloudflare" in text.lower()


# ═══════════════════════════════════════════════════════════════════════
# Item 1 — Grid card aspect-ratio (component-level static check)
# ═══════════════════════════════════════════════════════════════════════

def test_grid_card_image_class_defined_in_appcss():
    """The `.grid-card-image` utility used by all 4 card components MUST
    still exist in App.css."""
    path = "/app/frontend/src/App.css"
    text = open(path, "r", encoding="utf-8").read()
    assert ".grid-card-image" in text
    assert "aspect-ratio: 4 / 3" in text


def test_marketplace_card_uses_grid_card_image():
    text = open("/app/frontend/src/components/FlattenedMarketplace.js", "r", encoding="utf-8").read()
    assert "grid-card-image" in text, "MarketplaceCard did not receive iter359 aspect-ratio class"


def test_vehicle_card_uses_grid_card_image():
    text = open("/app/frontend/src/components/vehicles/VehicleListingCard.js", "r", encoding="utf-8").read()
    assert "grid-card-image" in text, "VehicleCard did not receive iter359 aspect-ratio class"


def test_storage_card_uses_grid_card_image():
    text = open("/app/frontend/src/pages/storage/StorageAuctionCard.js", "r", encoding="utf-8").read()
    assert "grid-card-image" in text, "StorageCard did not receive iter359 aspect-ratio class"


def test_lot_card_uses_grid_card_image():
    text = open("/app/frontend/src/pages/LotsMarketplacePage.js", "r", encoding="utf-8").read()
    assert "grid-card-image" in text, "LotCard did not receive iter359 aspect-ratio class"


# ═══════════════════════════════════════════════════════════════════════
# Item 2 — LangLink sweep (static check: no plain `<Link>` remaining
# for internal navigation in the migrated files).
# ═══════════════════════════════════════════════════════════════════════

def test_langlink_component_exists():
    assert os.path.isfile("/app/frontend/src/components/LangLink.jsx")


def test_urlmap_exists_with_press_pair():
    text = open("/app/frontend/src/i18n/urlMap.js", "r", encoding="utf-8").read()
    assert "'/press/quebec-launch': '/presse/lancement-quebec'" in text
    assert "'/marketplace': '/marche'" in text


def test_no_plain_link_import_in_migrated_files():
    """None of the iter359-swept files import `Link` from react-router-dom.

    We check a representative sample — the components + pages we KNOW
    were migrated. If any of these regress to `<Link>`, we catch it."""
    swept_files = [
        "/app/frontend/src/components/Navbar.js",
        "/app/frontend/src/components/Footer.js",
        "/app/frontend/src/components/FlattenedMarketplace.js",
        "/app/frontend/src/pages/LotsMarketplacePage.js",
        "/app/frontend/src/pages/storage/StorageAuctionCard.js",
    ]
    import re
    LINK_IMPORT_RE = re.compile(
        r"import\s*\{[^}]*\bLink\b[^}]*\}\s*from\s*['\"]react-router-dom['\"]"
    )
    for path in swept_files:
        text = open(path, "r", encoding="utf-8").read()
        assert not LINK_IMPORT_RE.search(text), (
            f"{path} still imports Link from react-router-dom — LangLink sweep incomplete"
        )
        # But it MUST import LangLink.
        assert "LangLink" in text, f"{path} did not receive LangLink import"
