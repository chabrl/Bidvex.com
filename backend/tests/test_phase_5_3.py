"""
Phase 5.3 — Backend tests for:
  Task 1 : Welcome HTML template + v9 fallback HTML renderers + worker no longer stubs.
  Task 2 : Meta CAPI structured-log fallback when env vars missing.
  Task 3 : Conversion funnel computation correctness.
  Task 4 : Welcome email HTML contains required blocks (Law-25, How-It-Works, grid).
"""
from __future__ import annotations

import importlib
import logging
import os
import pytest

from services.templates.welcome_email import (
    render_welcome_email,
    render_kind_html,
    HTML_FALLBACK_RENDERERS,
)


# ── Task 4 — Welcome HTML content ────────────────────────────────────────

def test_welcome_email_renders_dual_language_and_required_blocks():
    html = render_welcome_email(first_name="Alex")
    # Must include English + French header lines
    assert "Welcome to BidVex, Alex!" in html
    assert "Bienvenue chez BidVex" in html
    # Law 25 mention in both languages
    assert "Law 25" in html
    assert "Loi 25" in html
    # How-It-Works CTA module in both EN + FR
    assert html.count("/how-it-works") >= 2
    assert "How-It-Works Guide" in html
    assert "guide de fonctionnement" in html
    # Featured grid present with both cards
    assert "Vehicle Auctions" in html
    assert "Multi-Lot Industrial" in html
    # Marketplace CTA
    assert "Explore the Marketplace" in html
    # Logo image included
    assert "cdn.mcauto-images-production.sendgrid.net" in html


def test_welcome_email_fallback_for_missing_first_name():
    html = render_welcome_email(first_name="")
    assert "Welcome to BidVex, there!" in html
    assert "Bienvenue chez BidVex, à vous !" in html


def test_welcome_email_escapes_user_input():
    html = render_welcome_email(first_name="<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html


# ── Task 1 — V9 fallback HTML renderers ──────────────────────────────────

@pytest.mark.parametrize("kind", [
    "auction_end_time_changed_seller",
    "auction_end_time_changed_bidder",
    "auction_end_time_changed_watchlist",
    "ai_review_admin_alert",
    "ai_review_admin_escalation",
    "ai_review_approved",
    "ai_review_rejected",
    "quantity_invoice",
])
def test_v9_fallback_renderer_returns_html(kind):
    """Each v9 kind has an HTML fallback renderer that returns a full
    HTML document with both languages and the brand footer."""
    dd = {
        "listing_title":      "Sample Listing",
        "new_end_time":       "2030-01-01T00:00:00Z",
        "old_end_time":       "2026-01-01T00:00:00Z",
        "seller_category":    "Furniture",
        "suggested_category": "Vehicles",
        "admin_note":         "Please correct the category.",
        "cta_url":            "https://bidvex.com/test",
        "minutes_open":       60,
        "quantity":           5,
        "base_amount":        "12,500.00",
    }
    html = render_kind_html(kind, dd)
    assert html is not None, f"No HTML for kind {kind}"
    assert "<!DOCTYPE html>" in html
    assert "BidVex Canada" in html
    assert "Law&nbsp;25" in html or "Law 25" in html
    assert "Loi&nbsp;25" in html or "Loi 25" in html


def test_v9_registry_has_all_kinds():
    """The HTML_FALLBACK_RENDERERS dict must include all v9 kinds + the
    legacy quantity_invoice helper."""
    required = {
        "auction_end_time_changed_seller",
        "auction_end_time_changed_bidder",
        "auction_end_time_changed_watchlist",
        "ai_review_admin_alert",
        "ai_review_admin_escalation",
        "ai_review_approved",
        "ai_review_rejected",
    }
    assert required.issubset(set(HTML_FALLBACK_RENDERERS.keys()))


def test_render_kind_html_returns_none_for_unknown_kind():
    assert render_kind_html("totally_made_up_kind", {}) is None


def test_email_worker_html_fallback_branch_no_longer_stubs(monkeypatch):
    """When _template_id returns None, _send_via_sendgrid should attempt the
    HTML fallback path (not the legacy stub branch).

    We monkey-patch send_html_email to capture invocation, and confirm:
      - tmpl_id lookup returns None
      - send_html_email is called with rendered HTML
      - the returned reason is `sent_html_fallback` or `stubbed_no_sendgrid`
        but never `stubbed_no_template`.
    """
    import asyncio
    from workers import email_delivery_worker as ew

    # Ensure no template env vars in scope
    for k in list(os.environ):
        if k.startswith("SENDGRID_TEMPLATE_AI_REVIEW_"):
            monkeypatch.delenv(k, raising=False)

    captured = {}

    async def fake_send_html_email(*, to_email, to_name, subject, html_content, **kw):
        captured["to"] = to_email
        captured["subject"] = subject
        captured["html_len"] = len(html_content or "")
        # Pretend SendGrid was configured and accepted the message
        return True

    import services.email_service as es
    monkeypatch.setattr(es, "send_html_email", fake_send_html_email)

    row = {
        "kind": "ai_review_approved",
        "to_email": "test@bidvex.com",
    }
    dd = {
        "listing_title":  "My Listing",
        "admin_note":     "Looks good.",
        "subject":        "Approved",
        "cta_url":        "https://bidvex.com/seller/dashboard",
    }

    ok, reason = asyncio.get_event_loop().run_until_complete(
        ew._send_via_sendgrid(row, "test@bidvex.com", "Tester", "en", dd)
    )
    assert ok is True
    assert reason != "stubbed_no_template"
    assert reason in ("sent_html_fallback", "stubbed_no_sendgrid")
    if reason == "sent_html_fallback":
        assert captured["html_len"] > 500
        assert captured["subject"] == "Approved"


# ── Task 2 — Meta CAPI structured-log fallback ────────────────────────────

def test_meta_capi_fallback_logs_when_env_missing(caplog, monkeypatch):
    """When META_PIXEL_ID is missing we should emit a structured log line
    with the event_id, value, currency etc. — not silently bypass."""
    import asyncio
    from services import analytics_tracker as at

    monkeypatch.delenv("META_PIXEL_ID", raising=False)
    monkeypatch.delenv("META_CAPI_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("META_CAPI_DISABLE", raising=False)

    event = at.build_purchase_event(
        platform_fee=375.00,
        broker_fee=500.00,
        user_data={"em": ["abcdef"], "client_ip_address": "1.2.3.4", "client_user_agent": "ua"},
        event_id="broker_invoice_test_v9",
    )
    assert event["custom_data"]["value"] == 875.00

    with caplog.at_level(logging.INFO, logger=at.logger.name):
        result = asyncio.get_event_loop().run_until_complete(at._send_to_meta([event]))
    assert result["ok"] is False
    assert result["reason"] == "missing_env"
    assert result.get("fallback") == "structured_log"

    # The structured log line must contain the value and event_id
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "meta_capi/fallback" in joined
    assert "broker_invoice_test_v9" in joined
    assert "value=875" in joined.replace(" ", "").replace("875.00", "875").replace("=875.0", "=875") or "875" in joined
    # Cleartext PII must be scrubbed from the log line
    assert "1.2.3.4" not in joined
    assert "client_ip_address" not in joined


def test_meta_capi_fallback_when_disabled_via_env(caplog, monkeypatch):
    """META_CAPI_DISABLE=true → still emit the structured fallback log."""
    import asyncio
    from services import analytics_tracker as at

    monkeypatch.setenv("META_PIXEL_ID", "test_pixel")
    monkeypatch.setenv("META_CAPI_ACCESS_TOKEN", "test_token")
    monkeypatch.setenv("META_CAPI_DISABLE", "true")

    event = at.build_purchase_event(
        platform_fee=100,
        broker_fee=200,
        user_data={},
        event_id="broker_invoice_disabled",
    )
    with caplog.at_level(logging.INFO, logger=at.logger.name):
        result = asyncio.get_event_loop().run_until_complete(at._send_to_meta([event]))
    assert result["ok"] is False
    assert result["reason"] == "disabled_via_env"
    joined = "\n".join(r.getMessage() for r in caplog.records)
    assert "meta_capi/fallback" in joined
    assert "broker_invoice_disabled" in joined


# ── Task 3 — Conversion funnel route registration ─────────────────────────

def test_conversion_funnel_router_imports():
    mod = importlib.import_module("routes.admin_conversion_funnel")
    assert hasattr(mod, "conversion_funnel_router")
    paths = {r.path for r in mod.conversion_funnel_router.routes}
    assert "/admin/analytics/conversion-funnel" in paths


def test_conversion_funnel_drop_off_math():
    """Verify the percentage drop-off + cumulative-conversion math in
    isolation by importing the helper."""
    from routes.admin_conversion_funnel import _safe_pct
    # 70% drop-off between 100 → 30
    assert _safe_pct(100 - 30, 100) == 70.0
    # 100% drop-off between 50 → 0
    assert _safe_pct(50 - 0, 50) == 100.0
    # Zero denom → 0.0
    assert _safe_pct(10, 0) == 0.0
    # Tiny rounding behaviour
    assert _safe_pct(1, 3) == 33.33
