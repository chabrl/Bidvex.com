"""
iter332 — Regression test for Twilio Error 12100 (XML Document Parse Failure).

The /api/twilio/ivr/route endpoint used to emit a TwiML `<Number url="…">`
attribute whose URL contained a raw `&` between the two query parameters
(`?lang=en&caller_from=+…`). Twilio's TwiML parser rejects unescaped
ampersands in XML attribute values, causing every inbound bridge attempt
to fail with error 12100 ("Document parse failure").

This suite locks the fix: the emitted TwiML MUST
  1. contain `&amp;` (not a bare `&`) between `lang=` and `caller_from=`,
  2. parse cleanly through a strict XML parser,
  3. still produce the intended URL when the parser decodes the entity.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import httpx
import pytest


BASE = os.environ.get("PREVIEW_API_URL") or "https://prod-verify-2.preview.emergentagent.com"
IVR_ROUTE = f"{BASE}/api/twilio/ivr/route"
KNOWN_EXTENSION = "1220"  # Seeded contractor extension per test_credentials.md


def _hit(lang: str = "en"):
    """POST the IVR route endpoint with proxy headers so the whisper URL
    is stamped as https:// (iter324 fix)."""
    return httpx.post(
        f"{IVR_ROUTE}?lang={lang}",
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "bidvex.com",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "Digits": KNOWN_EXTENSION,
            "From": "+18195803757",
            "CallSid": "CAtest_iter332_regression",
        },
        timeout=15,
    )


@pytest.mark.parametrize("lang", ["en", "fr"])
def test_whisper_url_ampersand_is_escaped(lang):
    """The <Number url="…"> attribute must use &amp; not raw &."""
    r = _hit(lang=lang)
    assert r.status_code == 200, r.text
    body = r.text

    # Positive: escaped entity is present.
    assert "&amp;caller_from=" in body, (
        f"Missing &amp; entity in whisper URL for lang={lang}. Body:\n{body}"
    )

    # Negative: NO raw & should appear in a <Number url="…"> attribute.
    # We check by extracting the url attribute substring and asserting
    # no bare & remains inside it.
    start = body.find('<Number url="')
    assert start != -1, f"Missing <Number> element:\n{body}"
    end = body.find('"', start + len('<Number url="'))
    url_attr = body[start + len('<Number url="'):end]
    assert "&" not in url_attr or "&amp;" in url_attr, (
        f"Raw & leaked into url attr: {url_attr!r}"
    )


def test_response_is_strict_xml_parseable():
    """Twilio uses a strict XML parser — the response MUST parse."""
    r = _hit(lang="en")
    assert r.status_code == 200

    # If the ampersand were unescaped, ET.fromstring would raise
    # xml.etree.ElementTree.ParseError.
    root = ET.fromstring(r.text)
    number = root.find(".//Number")
    assert number is not None

    url_attr = number.get("url") or ""
    # After parsing, the URL should decode to a raw & (entity resolved).
    assert "lang=en" in url_attr
    assert "&caller_from=+18195803757" in url_attr, (
        f"Parsed URL missing expected query params: {url_attr!r}"
    )


def test_number_method_and_action_still_correct():
    """Regression guard for the surrounding TwiML structure."""
    r = _hit(lang="en")
    root = ET.fromstring(r.text)
    dial = root.find(".//Dial")
    assert dial is not None
    assert dial.get("method") == "POST"
    assert dial.get("timeout") == "25"
    assert dial.get("answerOnBridge") == "true"
    assert (dial.get("action") or "").startswith("https://")

    number = root.find(".//Number")
    assert number.get("method") == "POST"
    assert (number.get("url") or "").startswith("https://")
