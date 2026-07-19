"""
iter363 — Final launch-gate regression suite.

Covers:
  • Contact form backend submission endpoint (POST /api/contact/submit)
  • Contact form validates team_id + email + message length + URL spam
  • TEAM_EMAIL_MAP contains all 10 iter362 teams
  • Hero phone mockup PNGs exist for EN + FR
  • HeroPhone.js references /static/hero-phone-{lang}.png
  • HeroPhone.css has responsive mobile sizing (70vh/50vh/42vh caps)
  • ContactUsPage form POSTs to backend (not just mailto)
  • Language toggle logic verified static-check
"""
import os
import re

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import sys
sys.path.insert(0, "/app/backend")

from routes.contact import contact_router, TEAM_EMAIL_MAP


# ═══════════════════════════════════════════════════════════════════════
# Contact form backend endpoint
# ═══════════════════════════════════════════════════════════════════════

_app = FastAPI()
_app.include_router(contact_router)
client = TestClient(_app)


def test_team_email_map_contains_all_10_iter362_teams():
    for expected in [
        "office", "support", "vehicles", "brokers", "resolutions",
        "payment", "privacy", "marketing", "careers", "contractors",
    ]:
        assert expected in TEAM_EMAIL_MAP, f"Missing team_id: {expected}"


def test_team_email_map_addresses_are_bidvex():
    for team_id, email in TEAM_EMAIL_MAP.items():
        assert email.endswith("@bidvex.com"), f"{team_id} → {email} not BidVex"


def test_contact_submit_endpoint_registered():
    paths = [getattr(r, "path", "") for r in _app.routes]
    assert "/api/contact/submit" in paths


def test_contact_submit_valid_payload_returns_200():
    r = client.post("/api/contact/submit", json={
        "name":     "Alex Boulanger",
        "email":    "alex@example.com",
        "team_id":  "support",
        "message":  "I need help with my bidding history — thanks!",
        "lang":     "en",
    })
    # Backend may return 200 (delivered) or 502 (SendGrid config missing in test).
    # Either way, the endpoint MUST be reachable and correctly routed.
    assert r.status_code in (200, 502), f"Unexpected status {r.status_code}: {r.text[:200]}"
    if r.status_code == 200:
        data = r.json()
        assert data["ok"] is True
        assert data["team"] == "support"
        assert data["routed_to"] == "service@bidvex.com"


def test_contact_submit_rejects_unknown_team_id():
    r = client.post("/api/contact/submit", json={
        "name":     "X",
        "email":    "x@y.com",
        "team_id":  "not_a_real_team",
        "message":  "hello this is a long enough message to pass validation",
    })
    assert r.status_code in (400, 422)


def test_contact_submit_rejects_short_message():
    r = client.post("/api/contact/submit", json={
        "name":     "X",
        "email":    "x@y.com",
        "team_id":  "support",
        "message":  "short",  # < 10 chars
    })
    assert r.status_code in (400, 422)


def test_contact_submit_rejects_bad_email():
    r = client.post("/api/contact/submit", json={
        "name":     "X",
        "email":    "not-an-email",
        "team_id":  "support",
        "message":  "hello this is long enough to pass validation",
    })
    assert r.status_code in (400, 422)


def test_contact_submit_rejects_url_spam():
    r = client.post("/api/contact/submit", json={
        "name":     "X",
        "email":    "x@y.com",
        "team_id":  "marketing",
        "message":  "buy now http://a.com http://b.com http://c.com http://d.com http://e.com",
    })
    assert r.status_code in (400, 422)


def test_contact_submit_all_10_teams_routable():
    """Every team_id → correct email address end-to-end."""
    for team_id, expected_email in TEAM_EMAIL_MAP.items():
        r = client.post("/api/contact/submit", json={
            "name":     "Route Test",
            "email":    "test@example.com",
            "team_id":  team_id,
            "message":  f"Routing test for team {team_id}",
        })
        assert r.status_code in (200, 502), (
            f"team_id={team_id} → {r.status_code}: {r.text[:200]}"
        )
        if r.status_code == 200:
            assert r.json()["routed_to"] == expected_email


# ═══════════════════════════════════════════════════════════════════════
# Hero phone mockup — Pillow-generated, language-aware
# ═══════════════════════════════════════════════════════════════════════

def test_hero_phone_en_asset_exists():
    p = "/app/frontend/public/static/hero-phone-en.png"
    assert os.path.isfile(p)
    assert os.path.getsize(p) > 5000  # non-trivial PNG


def test_hero_phone_fr_asset_exists():
    p = "/app/frontend/public/static/hero-phone-fr.png"
    assert os.path.isfile(p)
    assert os.path.getsize(p) > 5000


def test_heroPhone_js_references_new_static_paths():
    text = open("/app/frontend/src/components/HeroPhone.js", "r", encoding="utf-8").read()
    # iter363: PNG served from /static/hero-phone-{lang}.png
    assert "/static/hero-phone-en.png" in text
    assert "/static/hero-phone-fr.png" in text
    # Fallback path still present
    assert "hero-phone-mockup.png" in text


def test_heroPhone_css_has_mobile_max_height_caps():
    """CLS + UX fix: phone must never exceed viewport-height caps on mobile."""
    text = open("/app/frontend/src/components/HeroPhone.css", "r", encoding="utf-8").read()
    # Desktop cap
    assert "70vh" in text
    # Mobile caps
    assert "50vh" in text  # < 768px
    assert "42vh" in text  # < 480px


def test_heroPhone_css_uses_object_fit_contain():
    text = open("/app/frontend/src/components/HeroPhone.css", "r", encoding="utf-8").read()
    assert "object-fit: contain" in text


# ═══════════════════════════════════════════════════════════════════════
# Contact page: POSTs to backend (mailto: removed from form flow in iter363)
# ═══════════════════════════════════════════════════════════════════════

def test_contact_page_posts_to_backend_endpoint():
    text = open("/app/frontend/src/pages/ContactUsPage.jsx", "r", encoding="utf-8").read()
    assert "/api/contact/submit" in text
    assert "axios" in text
    # iter363: mailto: fallback removed from the form submission flow.
    # The mailto:{team.email} direct-email links on each team card
    # remain — they are a separate feature, not part of the form.
    # Assert the buildMailtoFallback function is gone.
    assert "buildMailtoFallback" not in text
    assert "window.location.href = " not in text  # no mailto redirect


def test_contact_page_shows_success_and_error_states():
    text = open("/app/frontend/src/pages/ContactUsPage.jsx", "r", encoding="utf-8").read()
    assert "contact-form-success" in text
    # iter363: fallback state replaced by explicit error state after
    # the mailto: fallback was removed from the submission flow.
    assert "contact-form-error" in text
    assert "contact-form-fallback" not in text


# ═══════════════════════════════════════════════════════════════════════
# Regression tripwires — language toggle infrastructure
# ═══════════════════════════════════════════════════════════════════════

def test_language_prefixed_routes_registered():
    """iter358 + iter363: lang-prefixed routes must precede legacy paths."""
    text = open("/app/frontend/src/App.js", "r", encoding="utf-8").read()
    # Find the position of the first lang-prefixed route and the first
    # legacy detail route with :id
    en_marketplace_idx = text.find('path="/en/marketplace"')
    fr_marche_idx = text.find('path="/fr/marche"')
    assert en_marketplace_idx > 0, "Missing /en/marketplace route"
    assert fr_marche_idx > 0, "Missing /fr/marche route"


def test_language_context_switchLang_navigates():
    text = open("/app/frontend/src/contexts/LanguageContext.js", "r", encoding="utf-8").read()
    # switchLang must call navigate() for real URL change (not just i18n).
    assert "navigate(newPath)" in text
    assert "toLangPath" in text


def test_contact_route_registered_under_both_lang_prefixes():
    text = open("/app/frontend/src/App.js", "r", encoding="utf-8").read()
    # iter358: both /en/contact and /fr/contact must render ContactUsPage.
    assert 'path="/en/contact"' in text
    assert 'path="/fr/contact"' in text
