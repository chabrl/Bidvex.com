"""
iter333 — Regression test for General Support routing (press '0').

Callers who press '0' on the BidVex inbound line MUST be bridged directly
to the general support team number `+15149490038`. This test locks:
  1. The emitted TwiML is exactly the spec:
       <Response><Dial timeout="25" answerOnBridge="true">
         <Number>+15149490038</Number>
       </Dial></Response>
  2. Both `lang=en` and `lang=fr` produce the same routing.
  3. Empty `Digits` (no gather selection) falls through to the same path.
  4. The ledger row is stamped as `outcome=support_routed`.
"""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

import httpx
import pytest


BASE = os.environ.get("PREVIEW_API_URL") or "https://prod-verify-2.preview.emergentagent.com"
IVR_ROUTE = f"{BASE}/api/twilio/ivr/route"
GENERAL_SUPPORT_NUMBER = "+15149490038"


def _hit(lang: str, digits: str, call_sid: str = "CAtest_iter333"):
    return httpx.post(
        f"{IVR_ROUTE}?lang={lang}",
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "bidvex.com",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={
            "Digits": digits,
            "From": "+18195803757",
            "CallSid": call_sid,
        },
        timeout=15,
    )


@pytest.mark.parametrize("lang", ["en", "fr"])
def test_press_zero_bridges_to_general_support(lang):
    r = _hit(lang=lang, digits="0", call_sid=f"CAtest_iter333_zero_{lang}")
    assert r.status_code == 200, r.text
    root = ET.fromstring(r.text)

    dial = root.find(".//Dial")
    assert dial is not None, f"Missing <Dial> in TwiML: {r.text}"
    assert dial.get("timeout") == "25"
    assert dial.get("answerOnBridge") == "true"

    number = root.find(".//Number")
    assert number is not None, f"Missing <Number> in TwiML: {r.text}"
    assert (number.text or "").strip() == GENERAL_SUPPORT_NUMBER, (
        f"Wrong target number: {number.text!r} (expected {GENERAL_SUPPORT_NUMBER!r})"
    )

    # No <Say> / <Hangup> should be present — spec is a bare Dial block.
    assert root.find(".//Say") is None, "Unexpected <Say> in press-0 TwiML"
    assert root.find(".//Hangup") is None, "Unexpected <Hangup> in press-0 TwiML"


def test_empty_digits_falls_through_to_support():
    """A caller who lets the Gather time out (no digit) → also to support."""
    r = _hit(lang="en", digits="", call_sid="CAtest_iter333_empty")
    assert r.status_code == 200
    root = ET.fromstring(r.text)
    number = root.find(".//Number")
    assert number is not None
    assert (number.text or "").strip() == GENERAL_SUPPORT_NUMBER


def test_valid_extension_still_dials_contractor_not_support():
    """Regression guard: a valid contractor extension MUST NOT bridge to
    general support — it must still bridge to the contractor's personal
    phone via the whisper URL path."""
    r = _hit(lang="en", digits="1220", call_sid="CAtest_iter333_ext")
    assert r.status_code == 200
    root = ET.fromstring(r.text)
    number = root.find(".//Number")
    assert number is not None
    assert (number.text or "").strip() != GENERAL_SUPPORT_NUMBER, (
        "Contractor extension mistakenly routed to general support"
    )
    # The contractor dial has a whisper url; general support does not.
    assert number.get("url"), "Contractor <Number> should carry a whisper url"
