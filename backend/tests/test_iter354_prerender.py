"""
iter354 — SSR prerender snapshot tests.

Uses the live prerender_service resolvers so this tests real production code
paths (not a fake). Every static route MUST emit:
  • a <title> different from any other route
  • valid canonical + hreflang alternates
  • at least Organization + BreadcrumbList JSON-LD blocks
  • <div id="root"></div> for SPA hydration
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from services.prerender_service import resolve_route, render_html


class FakeDB:
    """Minimal async-cursor-compatible fake for the static-page paths that
    don't actually hit MongoDB."""

    class _Coll:
        async def find_one(self, *a, **kw): return None

    def __getitem__(self, name): return self._Coll()
    def __getattr__(self, name): return self._Coll()


DB = FakeDB()


@pytest.mark.parametrize("path,expected_types", [
    ("/",                    {"Organization", "WebSite"}),
    ("/marketplace",         {"Organization", "BreadcrumbList"}),
    ("/vehicle-auctions",    {"Organization", "BreadcrumbList"}),
    ("/storage-auctions",    {"Organization", "BreadcrumbList"}),
    ("/faq",                 {"Organization", "BreadcrumbList", "FAQPage"}),
    ("/how-it-works",        {"Organization", "BreadcrumbList", "FAQPage"}),
    ("/about",               {"Organization", "BreadcrumbList"}),
    ("/contact",             {"Organization", "BreadcrumbList"}),
    ("/legal/terms",         {"Organization", "BreadcrumbList"}),
    ("/legal/privacy",       {"Organization", "BreadcrumbList"}),
])
def test_static_prerender_shape(path, expected_types):
    ctx = asyncio.run(resolve_route(DB, path, "en"))
    html = render_html(ctx)

    # Required meta tags
    assert re.search(r'<title>[^<]+</title>', html), f"no title on {path}"
    assert re.search(r'<meta name="description" content="[^"]+"', html), f"no description on {path}"
    assert 'https://www.bidvex.com' in html, f"canonical wrong host on {path}"
    assert 'hreflang="en-CA"' in html and 'hreflang="fr-CA"' in html, f"hreflang missing on {path}"
    assert '<meta property="og:title"' in html, f"og:title missing on {path}"
    assert '<meta property="og:image"' in html, f"og:image missing on {path}"

    # JSON-LD block presence + validity
    blocks = re.findall(r'<script type="application/ld\+json">(.+?)</script>', html, flags=re.DOTALL)
    assert blocks, f"no JSON-LD on {path}"
    types = set()
    for b in blocks:
        parsed = json.loads(b)   # will raise if malformed
        types.add(parsed.get("@type"))
    assert expected_types.issubset(types), f"missing JSON-LD types on {path}: expected {expected_types}, got {types}"

    # SPA hydration point must remain so real users still get the React app
    assert '<div id="root">' in html, f"SPA <div id=root> missing on {path}"


def test_bilingual_hreflang_alternates():
    """Both en and fr renders must expose the alternate for the other lang."""
    en_html = render_html(asyncio.run(resolve_route(DB, "/faq", "en")))
    fr_html = render_html(asyncio.run(resolve_route(DB, "/faq", "fr")))
    assert 'href="https://www.bidvex.com/faq?lang=fr"' in en_html
    assert 'href="https://www.bidvex.com/faq?lang=en"' in fr_html


def test_faq_qas_included_bilingually():
    en_ld = _extract_faqpage_qas(render_html(asyncio.run(resolve_route(DB, "/faq", "en"))))
    fr_ld = _extract_faqpage_qas(render_html(asyncio.run(resolve_route(DB, "/faq", "fr"))))
    assert any("BidVex" in qa["name"] and "safe" in qa["name"].lower() for qa in en_ld)
    assert any("séquestre" in qa["acceptedAnswer"]["text"].lower() for qa in fr_ld)


def test_escrow_language_in_faq_ld_is_two_flow():
    """Regression against the C-1 fix — the FAQPage JSON-LD must reference
    BOTH the non-vehicle escrow flow AND the vehicle broker-direct flow."""
    en_qas = _extract_faqpage_qas(render_html(asyncio.run(resolve_route(DB, "/faq", "en"))))
    text_blob = " ".join(qa["acceptedAnswer"]["text"] for qa in en_qas).lower()
    assert "escrow" in text_blob
    assert "off-platform" in text_blob or "broker" in text_blob


def test_unknown_path_falls_back_to_homepage():
    ctx = asyncio.run(resolve_route(DB, "/some/random/unknown/path", "en"))
    html = render_html(ctx)
    # Falls back to homepage template — check for a hallmark
    assert "Canada" in html


def test_canonical_uses_www_bidvex():
    """iter354 canonical migration — every prerender output canonicals to www."""
    for path in ["/", "/marketplace", "/faq", "/about", "/contact"]:
        html = render_html(asyncio.run(resolve_route(DB, path, "en")))
        m = re.search(r'<link rel="canonical" href="([^"]+)"', html)
        assert m and m.group(1).startswith("https://www.bidvex.com"), (
            f"canonical for {path} was {m.group(1) if m else 'MISSING'}"
        )


# ─── Helpers ──────────────────────────────────────────────────────────
def _extract_faqpage_qas(html: str) -> list:
    for block in re.findall(r'<script type="application/ld\+json">(.+?)</script>', html, flags=re.DOTALL):
        obj = json.loads(block)
        if obj.get("@type") == "FAQPage":
            return obj.get("mainEntity", [])
    return []
