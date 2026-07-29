"""
iter362 — Prerender bulletproofing + Contact + Admin overflow test suite.
"""
import os
import re

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, "/app/backend")

from routes.prerender import (
    _CRAWLER_UA_RE,
    _CRAWLER_UA_PATTERNS,
    is_crawler_ua,
    is_prerender_eligible,
    BotPrerenderMiddleware,
)


# ═══════════════════════════════════════════════════════════════════════
# P1 — BotPrerenderMiddleware bulletproofing
# ═══════════════════════════════════════════════════════════════════════

REQUIRED_BOT_UA_PATTERNS = [
    # Google — must include EVERY Google testing tool UA
    "googlebot", "google-inspectiontool", "google-structured-data-testing-tool",
    "adsbot-google", "mediapartners-google", "apis-google",
    "developers.google.com",
    # Microsoft / Bing / Yahoo
    "bingbot", "msnbot", "bingpreview", "slurp",
    # Search engines
    "duckduckbot", "baiduspider", "yandex",
    # Social + link scanners
    "facebookexternalhit", "twitterbot", "linkedinbot",
]


@pytest.mark.parametrize("required_pattern", REQUIRED_BOT_UA_PATTERNS)
def test_prerender_recognizes_required_bot_pattern(required_pattern):
    """Every UA pattern from the iter362 spec MUST be in the regex list."""
    assert required_pattern in _CRAWLER_UA_PATTERNS, (
        f"Missing required bot pattern: {required_pattern}"
    )


@pytest.mark.parametrize("ua", [
    "Googlebot/2.1 (+http://www.google.com/bot.html)",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    # GSC Live Test — CRITICAL: this UA verifies the middleware fires for
    # Google's "Test Live URL" tool in Search Console.
    "Mozilla/5.0 (compatible; Google-InspectionTool/1.0)",
    "Mozilla/5.0 (compatible; Google-InspectionTool/2.0)",
    # Rich Results Test
    "Mozilla/5.0 (compatible; developers.google.com/+/web/snippet)",
    # Structured Data Testing Tool (legacy but still used)
    "Google-Structured-Data-Testing-Tool",
    "Mozilla/5.0 (compatible; AdsBot-Google-Mobile; +http://www.google.com/mobile/adsbot.html)",
    "Mozilla/5.0 (compatible; AdsBot-Google)",
    "Mediapartners-Google",
    "APIs-Google (+https://developers.google.com/webmasters/APIs-Google.html)",
    "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
    "facebookexternalhit/1.1",
    "Twitterbot/1.0",
    "LinkedInBot/1.0 (compatible; Mozilla/5.0; Jakarta Commons-HttpClient/3.1 +http://www.linkedin.com)",
    "Mozilla/5.0 (compatible; DuckDuckBot-Https/1.1; https://duckduckgo.com/duckduckbot)",
    "Mozilla/5.0 (Linux; Android 6.0.1) HeadlessChrome/74.0.3729.169",
])
def test_prerender_regex_matches_real_bot_ua_strings(ua):
    """Real crawler UA strings (as seen in prod logs) must match."""
    assert _CRAWLER_UA_RE.search(ua), f"Failed to match bot UA: {ua}"
    assert is_crawler_ua(ua), f"is_crawler_ua returned False for: {ua}"


@pytest.mark.parametrize("ua", [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15",
    "Mozilla/5.0 (Linux; Android 10; SM-G975F)",
    "",
])
def test_prerender_regex_does_not_match_human_ua(ua):
    """Human browser UAs must NOT trigger the prerender path."""
    if ua:
        assert not _CRAWLER_UA_RE.search(ua), f"False-positive bot match: {ua}"
    assert not is_crawler_ua(ua), f"is_crawler_ua false-positive: {ua!r}"


def test_prerender_eligibility_covers_key_public_paths():
    for p in [
        "/", "/marketplace", "/vehicle-auctions", "/storage-auctions",
        "/lots", "/faq", "/how-it-works", "/press/quebec-launch",
        "/presse/lancement-quebec", "/en/marketplace", "/fr/marche",
    ]:
        assert is_prerender_eligible(p), f"Path {p} should be prerender-eligible"


def test_prerender_eligibility_excludes_api_and_static():
    for p in ["/api/vehicles", "/static/hero.png", "/manifest.json",
              "/robots.txt", "/sitemap.xml", "/build/asset.js"]:
        assert not is_prerender_eligible(p), f"Path {p} must not prerender"


# ═══════════════════════════════════════════════════════════════════════
# P2 — Contact Us page rebuild
# ═══════════════════════════════════════════════════════════════════════

CONTACT_PATH = "/app/frontend/src/pages/ContactUsPage.jsx"


def test_contact_page_has_all_10_email_addresses():
    text = open(CONTACT_PATH, "r", encoding="utf-8").read()
    for expected in [
        "office@bidvex.com", "service@bidvex.com", "vehicles@bidvex.com",
        "broker@bidvex.com", "dispute@bidvex.com", "payment@bidvex.com",
        "privacy@bidvex.com", "marketing@bidvex.com", "careers@bidvex.com",
        "contractor@bidvex.com",  # iter362 — 10th email destination
    ]:
        assert expected in text, f"Contact page missing email: {expected}"


def test_contact_page_has_correct_corp_num():
    text = open(CONTACT_PATH, "r", encoding="utf-8").read()
    # Strip block comments so we don't false-match the header docstring
    # that references the OLD number as historical context.
    stripped = re.sub(r'/\*.*?\*/', '', text, flags=re.DOTALL)
    # iter362 — corrected from previous 1175252874 → 1175252826
    assert "1175252826" in stripped, "Correct corp number missing in code"
    assert "1175252874" not in stripped, "Old wrong corp number leaked outside comments"


def test_contact_page_has_correct_address():
    text = open(CONTACT_PATH, "r", encoding="utf-8").read()
    # iter410 — canonical HQ street number is 761 Rue Chalifoux (was 701 pre-iter410).
    assert "761 Rue Chalifoux" in text
    assert "701 Rue Chalifoux" not in text  # old value must be gone


def test_contact_page_has_local_business_jsonld():
    text = open(CONTACT_PATH, "r", encoding="utf-8").read()
    assert "LocalBusiness" in text
    assert "LOCAL_BUSINESS_LD" in text
    # ContactPoint entries for at least 5 team inboxes.
    assert text.count("ContactPoint") >= 5


def test_contact_page_has_subject_routed_form():
    text = open(CONTACT_PATH, "r", encoding="utf-8").read()
    assert "ContactForm" in text
    # Form generates a mailto: link based on the selected subject.
    assert "mailto:" in text
    assert "handleSubmit" in text
    # Bilingual copy must exist for form labels.
    assert "formSubject" in text
    assert "formName" in text


def test_contact_page_bilingual_copy_present():
    text = open(CONTACT_PATH, "r", encoding="utf-8").read()
    # Both language keys in COPY table
    assert "en: {" in text
    assert "fr: {" in text
    # French title
    assert "Communiquer avec BidVex" in text


def test_contact_page_meta_title_spec():
    """iter362 spec: title must be
       'Contact BidVex | Canada's Bilingual Auction Marketplace' (EN)."""
    text = open(CONTACT_PATH, "r", encoding="utf-8").read()
    assert "Contact BidVex | Canada's Bilingual Auction Marketplace" in text


def test_contact_page_data_testids_for_e2e():
    text = open(CONTACT_PATH, "r", encoding="utf-8").read()
    for tid in [
        "contact-us-page", "contact-us-title", "legal-entity-block",
        "hq-block", "contact-teams-grid", "contact-form-card",
        "contact-form-submit", "contact-form-subject-select",
    ]:
        assert f'data-testid="{tid}"' in text, f"Missing data-testid: {tid}"


# ═══════════════════════════════════════════════════════════════════════
# P3 — Homepage phone mockup per-language
# ═══════════════════════════════════════════════════════════════════════

HEROPHONE_PATH = "/app/frontend/src/components/HeroPhone.js"


def test_hero_phone_serves_language_variant():
    text = open(HEROPHONE_PATH, "r", encoding="utf-8").read()
    # iter362 — must reference the FR-specific asset path
    assert "hero-phone-mockup-fr.png" in text
    # Fallback to base PNG on error
    assert "hero-phone-mockup.png" in text


def test_hero_phone_has_explicit_dimensions():
    """CLS prevention — width + height attributes required on hero LCP."""
    text = open(HEROPHONE_PATH, "r", encoding="utf-8").read()
    assert re.search(r'width="\d+"', text), "Missing explicit width on hero img"
    assert re.search(r'height="\d+"', text), "Missing explicit height on hero img"


def test_hero_phone_has_onerror_fallback():
    text = open(HEROPHONE_PATH, "r", encoding="utf-8").read()
    assert "onError" in text
    assert "fellBack" in text  # infinite-loop guard


# ═══════════════════════════════════════════════════════════════════════
# P4 — Admin overflow fix (flex-wrap instead of overflow-x-auto)
# ═══════════════════════════════════════════════════════════════════════

ADMIN_DASH_PATH = "/app/frontend/src/pages/AdminDashboard.js"


def test_admin_primary_nav_uses_flex_wrap():
    text = open(ADMIN_DASH_PATH, "r", encoding="utf-8").read()
    # iter362 — primary + secondary nav rows MUST wrap so 30+ tabs are
    # visible at once, not cropped by horizontal overflow scroll.
    assert 'flex flex-wrap items-center gap-2 py-2' in text, (
        "Admin primary nav still uses non-wrapping flex layout"
    )
    # The old broken pattern must be gone.
    assert 'overflow-x-auto' not in re.sub(
        r'/\*.*?\*/', '', text, flags=re.DOTALL,
    ), "overflow-x-auto still present on admin nav rows"


def test_admin_primary_nav_data_testids():
    text = open(ADMIN_DASH_PATH, "r", encoding="utf-8").read()
    for tid in ["admin-primary-nav", "admin-crosscutting-nav"]:
        assert f'data-testid="{tid}"' in text, f"Missing testid: {tid}"


def test_admin_buttons_have_44px_tap_target():
    """iter362 — every admin nav button uses min-h-[44px] for touch."""
    text = open(ADMIN_DASH_PATH, "r", encoding="utf-8").read()
    # At least 3 of the primary/secondary/marketing tabs carry the min-h.
    assert text.count("min-h-[44px]") >= 3


# ═══════════════════════════════════════════════════════════════════════
# P5 — Vehicles section — verify code paths (content is a DB-seed job)
# ═══════════════════════════════════════════════════════════════════════

def test_vehicle_auctions_route_registered_in_app():
    text = open("/app/frontend/src/App.js", "r", encoding="utf-8").read()
    # iter358 lang-prefixed variants MUST be there (both EN + FR).
    assert '/en/vehicle-auctions' in text
    assert '/fr/encheres-vehicules' in text


# ═══════════════════════════════════════════════════════════════════════
# Regression tripwires — iter361 middleware still installed
# ═══════════════════════════════════════════════════════════════════════

def test_bot_prerender_middleware_class_has_logging():
    text = open("/app/backend/routes/prerender.py", "r", encoding="utf-8").read()
    # iter362 spec: production diagnostic log line MUST fire on every hit.
    assert "[PRERENDER] Bot detected:" in text
    # X-Prerender-Version bumped so we can grep prod logs for iter362 hits.
    assert 'X-Prerender-Version' in text


def test_cache_headers_middleware_still_registered():
    text = open("/app/backend/server.py", "r", encoding="utf-8").read()
    assert "CacheHeadersMiddleware" in text
    assert "BotPrerenderMiddleware" in text
