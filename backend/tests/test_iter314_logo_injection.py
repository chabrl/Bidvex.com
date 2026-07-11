"""
iter314 — Mandatory BidVex Logo on Every Email — regression tests.

Verifies that the canonical BidVex logo block is present on every
outbound email regardless of which code path produced the HTML.

Coverage:
  • Canonical logo URL constant + idempotency token
  • `inject_bidvex_logo_header()` — empty / no-table / has-table inputs
  • Idempotency: a second pass over already-logo'd HTML is a no-op
  • `BIDVEX_EMAIL_TEMPLATE` (transactional unified path) contains the canonical URL
  • `_base_template()` (section-branded path) contains the canonical URL
  • `wrap_external_campaign_body()` (external campaigns) prepends logo + appends CASL footer
  • External campaign wrap is idempotent against legacy or canonical pre-existing logos
  • `services.email_service.LOGO_URL` points to the canonical URL
  • `send_email()` injects the logo into raw HTML pre-dispatch (mocked SG)
"""
from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

import pytest  # noqa: E402

# ─── Canonical URL fixture ──────────────────────────────────────────────

CANONICAL_URL = (
    "http://cdn.mcauto-images-production.sendgrid.net/"
    "4fbf02710175d39f/91d027c2-73da-4510-9bce-ee1ce34f16a7/4500x1080.png"
)
CANONICAL_ID_TOKEN = "/91d027c2-73da-4510-9bce-ee1ce34f16a7/"


def test_constants_match_directive():
    """The canonical URL constant matches the iter314 directive verbatim."""
    from services.emails._email_core import (
        BIDVEX_LOGO_URL, BIDVEX_LOGO_ID_TOKEN, BIDVEX_LOGO_BLOCK,
    )
    assert BIDVEX_LOGO_URL == CANONICAL_URL
    assert BIDVEX_LOGO_ID_TOKEN == CANONICAL_ID_TOKEN
    # Logo block must include the canonical URL, a bidvex.com link,
    # and the dark `#0b1a30` background per the directive.
    assert CANONICAL_URL in BIDVEX_LOGO_BLOCK
    assert "https://bidvex.com" in BIDVEX_LOGO_BLOCK
    assert "#0b1a30" in BIDVEX_LOGO_BLOCK
    assert 'alt="BidVex"' in BIDVEX_LOGO_BLOCK


def test_inject_logo_into_table_html():
    """When the HTML has a <table>, the logo row is inserted as the first child."""
    from services.emails._email_core import inject_bidvex_logo_header
    html = (
        "<html><body>"
        '<table width="100%"><tr><td>Hello world</td></tr></table>'
        "</body></html>"
    )
    out = inject_bidvex_logo_header(html)
    assert CANONICAL_URL in out
    # Logo row comes BEFORE the existing <tr><td>Hello world.
    logo_pos = out.index(CANONICAL_URL)
    hello_pos = out.index("Hello world")
    assert logo_pos < hello_pos


def test_inject_logo_into_plain_string():
    """No <table> in HTML → fallback wrapper inserts the logo + a wrapping table."""
    from services.emails._email_core import inject_bidvex_logo_header
    out = inject_bidvex_logo_header("<p>Hi from BidVex</p>")
    assert CANONICAL_URL in out
    assert "<table" in out
    assert "Hi from BidVex" in out


def test_inject_logo_is_idempotent():
    """A second pass over already-logo'd HTML produces no duplicate."""
    from services.emails._email_core import inject_bidvex_logo_header
    once = inject_bidvex_logo_header("<table><tr><td>x</td></tr></table>")
    twice = inject_bidvex_logo_header(once)
    assert once == twice  # no change on re-injection
    # Exactly one logo URL occurrence.
    assert twice.count(CANONICAL_URL) == 1


def test_inject_skips_when_legacy_logo_already_present():
    """If the HTML already contains the legacy logo URL (older template
    snapshot), we skip re-injection to avoid double-logo'd emails."""
    from services.emails._email_core import inject_bidvex_logo_header
    legacy_html = (
        '<html><body><img src="...31636d5f-c160-446b-b715-bcf542e9607e/x.png">'
        "<table><tr><td>body</td></tr></table></body></html>"
    )
    out = inject_bidvex_logo_header(legacy_html)
    # Canonical URL is NOT injected because legacy id-token is present.
    assert CANONICAL_URL not in out


def test_inject_handles_none_and_empty():
    """None / empty HTML returned untouched (defensive)."""
    from services.emails._email_core import inject_bidvex_logo_header
    assert inject_bidvex_logo_header("") == ""
    assert inject_bidvex_logo_header(None) is None  # noqa: PLR2004


def test_bidvex_email_template_uses_canonical_url():
    """The transactional unified-email template carries the canonical logo URL."""
    from services.email_templates import BIDVEX_EMAIL_TEMPLATE
    assert CANONICAL_URL in BIDVEX_EMAIL_TEMPLATE
    # And NOT the legacy URL that used to be hardcoded here.
    assert "31636d5f-c160-446b-b715-bcf542e9607e" not in BIDVEX_EMAIL_TEMPLATE


def test_base_template_contains_canonical_logo():
    """_base_template (section-branded fallback) carries the canonical logo."""
    from services.emails._email_core import _base_template
    html = _base_template("<p>hello</p>", title="t", auction_type="vehicle")
    assert CANONICAL_URL in html


def test_p0_wrap_uses_canonical_url():
    """email_service._p0_wrap inherits the canonical LOGO_URL constant."""
    from services.email_service import LOGO_URL, _p0_wrap
    assert LOGO_URL == CANONICAL_URL
    html = _p0_wrap("#0B2545", "👋", "Welcome", "<p>hi</p>", "en")
    assert CANONICAL_URL in html


# ─── External campaign wrap ─────────────────────────────────────────────


def test_wrap_external_campaign_body_adds_logo_and_footer():
    """Admin-authored HTML gets wrapped with BidVex header + CASL footer."""
    from services.external_email import wrap_external_campaign_body
    body = "<p>Special offer from us!</p>"
    out = wrap_external_campaign_body(body, "https://bidvex.com/unsub?token=x")
    assert CANONICAL_URL in out
    assert "Special offer from us!" in out
    assert "unsubscribe" in out.lower()
    assert "https://bidvex.com/unsub?token=x" in out


def test_wrap_external_campaign_body_idempotent_canonical_logo():
    """If admin already pasted the canonical logo, the wrap step is a no-op
    on the header (but still ensures CASL footer)."""
    from services.external_email import wrap_external_campaign_body
    body = (
        '<table><tr><td>'
        f'<img src="{CANONICAL_URL}">'
        "</td></tr></table>"
        "<p>Body</p>"
    )
    out = wrap_external_campaign_body(body, "https://bidvex.com/unsub?token=x")
    # Logo URL appears exactly once (no duplicate header wrap).
    assert out.count(CANONICAL_URL) == 1
    # Footer was appended because the admin didn't include {unsubscribe_url}.
    assert "unsubscribe" in out.lower()


def test_wrap_external_campaign_body_idempotent_legacy_logo():
    """If admin pasted the LEGACY logo URL, we don't add the canonical
    one (preserves what's there) — but the CASL footer is still appended."""
    from services.external_email import wrap_external_campaign_body
    body = '<img src="...31636d5f-c160-446b-b715-bcf542e9607e/x.png"><p>Body</p>'
    out = wrap_external_campaign_body(body, "https://bidvex.com/unsub?token=x")
    assert CANONICAL_URL not in out  # didn't add canonical
    assert "31636d5f-c160-446b-b715-bcf542e9607e" in out  # kept legacy
    assert "unsubscribe" in out.lower()  # footer added


def test_wrap_external_campaign_preserves_admin_unsubscribe_placeholder():
    """If admin included {unsubscribe_url} via the placeholder, the
    wrapper should not duplicate the footer (admin's footer wins)."""
    from services.external_email import wrap_external_campaign_body
    body = (
        "<p>Promo</p>"
        '<a href="MY_UNSUB">Unsubscribe</a>'
    )
    out = wrap_external_campaign_body(body, "https://bidvex.com/unsub?token=x")
    # We injected the header (logo present)…
    assert CANONICAL_URL in out
    # …and DID NOT add a second CASL footer (admin's "Unsubscribe" anchor satisfies it).
    # The CASL footer's signature text "BidVex Inc." should NOT appear.
    assert out.count("BidVex Inc.") == 0


# ─── send_email() raw-HTML path (mocked SG) ─────────────────────────────


def test_send_email_injects_logo_into_raw_html(monkeypatch):
    """A call site that passes raw HTML (e.g. compliance_notifier) gets
    the canonical logo injected automatically by `send_email()`."""
    from services.emails import _email_core as core

    captured = {}

    class _FakeMail:
        def __init__(self, **kwargs):
            captured["from_email"] = kwargs.get("from_email")
            captured["subject"] = kwargs.get("subject")
            self._html = kwargs.get("html_content")
            captured["html_content"] = self._html

        def add_header(self, *_a, **_k): pass
        def add_category(self, *_a, **_k): pass
        def add_attachment(self, *_a, **_k): pass
        def add_custom_arg(self, *_a, **_k): pass

        @property
        def reply_to(self): return None

        @reply_to.setter
        def reply_to(self, _): pass

        @property
        def tracking_settings(self): return None

        @tracking_settings.setter
        def tracking_settings(self, _): pass

    class _FakeResp:
        status_code = 202
        headers = {"X-Message-Id": "test"}

    class _FakeSG:
        def send(self, message):
            # captured["html_content"] is the Content object — pull its .content
            return _FakeResp()

    monkeypatch.setattr(core, "Mail", _FakeMail)
    monkeypatch.setattr(core, "sg", _FakeSG())
    monkeypatch.setattr(core, "SENDGRID_AVAILABLE", True)

    # Run the async send.
    result = asyncio.run(core.send_email(
        to_email="test@example.com",
        subject="iter314 logo injection test",
        html_content="<table><tr><td>Plain body</td></tr></table>",
    ))

    # The send went through (mocked SG returned 202).
    assert result["status"] == "sent"
    # The Content object inside the SG Mail must include the canonical logo.
    html_arg = captured["html_content"]
    # html_content is a Content("text/html", "...") — extract the raw HTML.
    raw_html = getattr(html_arg, "content", None) or str(html_arg)
    assert CANONICAL_URL in raw_html


def test_send_email_is_idempotent_for_already_wrapped_html(monkeypatch):
    """When the caller already produced HTML through BIDVEX_EMAIL_TEMPLATE
    (which contains the canonical logo), `send_email()` doesn't duplicate."""
    from services.emails import _email_core as core
    from services.email_templates import BIDVEX_EMAIL_TEMPLATE

    captured = {}

    class _FakeMail:
        def __init__(self, **kwargs):
            self._html = kwargs.get("html_content")
            captured["html_content"] = self._html

        def add_header(self, *_a, **_k): pass
        def add_category(self, *_a, **_k): pass
        def add_attachment(self, *_a, **_k): pass
        def add_custom_arg(self, *_a, **_k): pass

        @property
        def reply_to(self): return None

        @reply_to.setter
        def reply_to(self, _): pass

        @property
        def tracking_settings(self): return None

        @tracking_settings.setter
        def tracking_settings(self, _): pass

    class _FakeResp:
        status_code = 202
        headers = {"X-Message-Id": "x"}

    class _FakeSG:
        def send(self, _m): return _FakeResp()

    monkeypatch.setattr(core, "Mail", _FakeMail)
    monkeypatch.setattr(core, "sg", _FakeSG())
    monkeypatch.setattr(core, "SENDGRID_AVAILABLE", True)

    rendered = BIDVEX_EMAIL_TEMPLATE.format(
        lang="en", email_subject="x", email_headline="h", email_subheadline="s",
        greeting="Hi", first_name="X",
        body_html="<p>body</p>", cta_block="", secondary_block="",
        team_signature="BidVex Team", support_email="service@bidvex.com",
        current_year=2026, corp_address="x", unsubscribe_url="https://bidvex.com/unsub",
    )

    asyncio.run(core.send_email(
        to_email="test@example.com",
        subject="iter314 idempotency",
        html_content=rendered,
    ))

    html_arg = captured["html_content"]
    raw_html = getattr(html_arg, "content", None) or str(html_arg)
    # Exactly one occurrence of the canonical URL — no duplicate header.
    assert raw_html.count(CANONICAL_URL) == 1
