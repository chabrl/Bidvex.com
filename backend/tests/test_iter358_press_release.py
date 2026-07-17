"""
iter358 — Press-release page test suite.

Coverage:
  • EN + FR entries registered in _REGIONAL_LANDINGS
  • Both paths prerender-eligible
  • Both paths present in sitemap-static.xml with priority 0.8
  • EN page renders with NewsArticle JSON-LD + correct datePublished (2026-07-17)
  • FR page renders with `<html lang="fr">` + French copy
  • Reciprocal hreflang cross-references between EN + FR
  • PDF is on disk + non-empty
  • Footer contains "Press / Presse" link
  • Founder attribution uses correct titles ("Founder & CEO" / "Fondateur et PDG")
  • Author role appears in JSON-LD
"""
import asyncio
import json
import os
import re

import pytest

import sys
sys.path.insert(0, "/app/backend")

from services.press_release import (
    PRESS_RELEASE_DATE_PUBLISHED,
    PRESS_RELEASE_PDF_URL,
    FOUNDER_NAME,
    FOUNDER_TITLE_EN,
    FOUNDER_TITLE_FR,
    press_release_paths,
    build_press_release_entries,
    news_article_ld_for,
)
from services.prerender_service import (
    _REGIONAL_LANDINGS,
    resolve_route,
    render_html,
)
from routes.prerender import is_prerender_eligible, _PRERENDER_ROUTE_PREFIXES
from routes.sitemap import STATIC_PAGES


# ─── Constants / fixtures ─────────────────────────────────────────────
EN_PATH = "/press/quebec-launch"
FR_PATH = "/presse/lancement-quebec"
PDF_DISK_PATH = "/app/frontend/public/static/press/bidvex-quebec-launch.pdf"


class _NullDB:
    """Stub DB — press-release pages don't touch Mongo."""
    def __getitem__(self, name):
        class _C:
            async def find_one(self, *a, **k): return None
            def find(self, *a, **k):
                class _Cur:
                    def limit(self, n): return self
                    async def to_list(self, n): return []
                    def __aiter__(self): return self
                    async def __anext__(self): raise StopAsyncIteration
                return _Cur()
        return _C()


# ─── Registration + eligibility ───────────────────────────────────────
def test_press_paths_registered():
    """Both EN + FR press paths are in _REGIONAL_LANDINGS."""
    assert EN_PATH in _REGIONAL_LANDINGS
    assert FR_PATH in _REGIONAL_LANDINGS
    assert _REGIONAL_LANDINGS[EN_PATH]["kind"] == "press_release"
    assert _REGIONAL_LANDINGS[FR_PATH]["kind"] == "press_release"


def test_press_paths_prerender_eligible():
    """Bots hitting the press URLs must route to the prerender pipeline."""
    assert is_prerender_eligible(EN_PATH)
    assert is_prerender_eligible(FR_PATH)
    # And the path prefixes list explicitly includes them
    assert EN_PATH in _PRERENDER_ROUTE_PREFIXES
    assert FR_PATH in _PRERENDER_ROUTE_PREFIXES


def test_pdf_asset_not_prerender_eligible():
    """PDF URLs must be excluded from prerender (they're binary files)."""
    assert not is_prerender_eligible("/static/press/bidvex-quebec-launch.pdf")


def test_press_paths_in_sitemap_static():
    """Sitemap-static must include both press URLs with priority 0.8."""
    paths = {p: pri for p, _cf, pri in STATIC_PAGES}
    assert EN_PATH in paths
    assert FR_PATH in paths
    assert paths[EN_PATH] == 0.8
    assert paths[FR_PATH] == 0.8


# ─── PDF asset checks ─────────────────────────────────────────────────
def test_pdf_exists_and_non_empty():
    assert os.path.isfile(PDF_DISK_PATH), f"PDF not found at {PDF_DISK_PATH}"
    size = os.path.getsize(PDF_DISK_PATH)
    assert size > 3000, f"PDF suspiciously small ({size} bytes) — regenerate"


def test_pdf_url_constant_matches_asset_location():
    """The URL string that lands in JSON-LD/HTML must match the disk path."""
    assert PRESS_RELEASE_PDF_URL == "/static/press/bidvex-quebec-launch.pdf"


# ─── NewsArticle JSON-LD builder ──────────────────────────────────────
def test_news_article_ld_en_shape():
    ld = news_article_ld_for("en")
    assert ld["@type"] == "NewsArticle"
    assert ld["datePublished"] == "2026-07-17"
    assert ld["dateModified"] == "2026-07-17"
    assert ld["inLanguage"] == "en-CA"
    assert ld["url"].endswith(EN_PATH)
    assert ld["author"]["name"] == FOUNDER_NAME
    assert ld["author"]["jobTitle"] == FOUNDER_TITLE_EN  # "Founder & CEO"
    assert ld["publisher"]["name"] == "BidVex Inc."
    assert "bidvex-icon.png" in ld["publisher"]["logo"]["url"]


def test_news_article_ld_fr_shape():
    ld = news_article_ld_for("fr")
    assert ld["datePublished"] == "2026-07-17"
    assert ld["inLanguage"] == "fr-CA"
    assert ld["url"].endswith(FR_PATH)
    assert ld["author"]["jobTitle"] == FOUNDER_TITLE_FR  # "Fondateur et PDG"


def test_founder_titles_locked():
    """Titles MUST match user's business card. Not a template."""
    assert FOUNDER_NAME == "Charbel Lichaa"
    assert FOUNDER_TITLE_EN == "Founder & CEO"
    assert FOUNDER_TITLE_FR == "Fondateur et PDG"


def test_launch_date_is_july_17_2026():
    """User directive: JSON-LD datePublished MUST be 2026-07-17."""
    assert PRESS_RELEASE_DATE_PUBLISHED == "2026-07-17"


# ─── Full page render (async) ─────────────────────────────────────────
def _render(path, lang):
    return asyncio.run(_render_async(path, lang))


async def _render_async(path, lang):
    db = _NullDB()
    ctx = await resolve_route(db, path, lang)
    html = render_html(ctx)
    return ctx, html


def test_en_page_renders_full_ssr():
    ctx, html = _render(EN_PATH, "en")
    assert ctx["template"] == "press_release.html"
    assert ctx["is_press_release"] is True
    assert '<html lang="en"' in html
    # NewsArticle JSON-LD block
    assert '"@type":"NewsArticle"' in html
    assert '"datePublished":"2026-07-17"' in html
    # Reciprocal hreflang → FR twin
    assert f'hreflang="fr-CA" href="https://www.bidvex.com{FR_PATH}"' in html
    # PDF download link
    assert PRESS_RELEASE_PDF_URL in html
    # Founder attribution in body copy
    assert "Charbel Lichaa" in html
    assert "Founder &amp; CEO" in html
    # Launch offer code
    assert "SUMMER2026" in html


def test_fr_page_renders_full_ssr_with_fr_html_lang():
    ctx, html = _render(FR_PATH, "fr")
    assert ctx["template"] == "press_release.html"
    assert ctx["is_press_release"] is True
    # French page MUST have <html lang="fr"> for hreflang integrity
    assert '<html lang="fr"' in html
    # NewsArticle JSON-LD block with FR language
    assert '"inLanguage":"fr-CA"' in html
    assert '"datePublished":"2026-07-17"' in html
    # Reciprocal hreflang → EN twin
    assert f'hreflang="en-CA" href="https://www.bidvex.com{EN_PATH}"' in html
    # French founder title
    assert "Fondateur et PDG" in html
    # Loi 96 mention (bilingual compliance)
    assert "Loi 96" in html


def test_footer_contains_press_link_on_every_page():
    """iter358 spec: link to press release in the base template footer."""
    ctx, html_en = _render("/faq", "en")
    assert "/press/quebec-launch" in html_en
    ctx, html_fr = _render("/faq", "fr")
    assert "/presse/lancement-quebec" in html_fr


def test_press_release_carries_organization_and_breadcrumb_and_newsarticle_ld():
    ctx, html = _render(EN_PATH, "en")
    # Count application/ld+json script blocks — must be >= 3
    # (organization + breadcrumb + newsarticle at minimum)
    count = html.count('<script type="application/ld+json">')
    assert count >= 3, f"Expected >= 3 JSON-LD blocks, got {count}"
    # Verify each type is present
    assert '"@type":"Organization"' in html
    assert '"@type":"BreadcrumbList"' in html
    assert '"@type":"NewsArticle"' in html


def test_press_release_has_no_local_business_ld():
    """Press releases are NOT city pages — no LocalBusiness JSON-LD."""
    ctx, html = _render(EN_PATH, "en")
    # LocalBusiness is only for city / homepage / province pages
    assert '"@type":"LocalBusiness"' not in html


def test_press_release_canonical_uses_www():
    ctx, html = _render(EN_PATH, "en")
    assert 'href="https://www.bidvex.com/press/quebec-launch"' in html
    ctx, html = _render(FR_PATH, "fr")
    assert 'href="https://www.bidvex.com/presse/lancement-quebec"' in html


# ─── Regression: iter357 outputs still work ────────────────────────────
def test_regression_qc_montreal_still_renders():
    ctx, html = _render("/encheres-vehicules-montreal", "fr")
    assert '<html lang="fr"' in html
    assert '"@type":"LocalBusiness"' in html


def test_regression_faq_still_has_faqpage_ld():
    ctx, html = _render("/faq", "en")
    assert '"@type":"FAQPage"' in html
