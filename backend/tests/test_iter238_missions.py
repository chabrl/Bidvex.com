"""iter238 — Mission 1/4/5/6 unit tests."""
from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Mission 6 — Unified email template
# ---------------------------------------------------------------------------
def test_email_template_includes_corporate_footer():
    from services.email_templates import BIDVEX_EMAIL_TEMPLATE, build_email_payload
    # The constant carries a placeholder; the rendered output substitutes the locked address.
    assert "{corp_address}" in BIDVEX_EMAIL_TEMPLATE
    rendered = build_email_payload("welcome", {"first_name": "X", "email": "x@x.com"}, {})
    assert "761 Rue Chalifoux, Sherbrooke (Québec) J1G 0A8" in rendered["html_content"]
    assert "support@bidvex.com" in rendered["html_content"]


@pytest.mark.parametrize("email_type", [
    "welcome", "bid_placed", "outbid", "auction_won",
    "auction_ending_soon", "voicemail", "ai_suggestion",
    "new_feature", "password_reset", "onboarding_reminder",
])
def test_build_email_payload_supports_all_types(email_type):
    from services.email_templates import build_email_payload
    user = {"first_name": "Test", "email": "t@example.com"}
    data = {
        "bid_amount": 100,
        "listing_id": "lst-1",
        "listing_title": "Vintage Lamp",
        "current_bid": 120,
        "hammer_price": 500,
        "order_id": "ord-1",
        "time_remaining": "45m",
        "caller_number": "+15145555555",
        "department": "Support",
        "language": "EN",
        "recording_url": "https://bidvex.com/r/1",
        "ai_message": "Try this comparable.",
        "listing_url": "https://bidvex.com/listing/1",
        "feature_name": "Live Bid Streaming",
        "feature_description": "Real-time price tickers.",
        "feature_url": "https://bidvex.com/features/streaming",
        "reset_url": "https://bidvex.com/reset?t=xyz",
    }
    payload = build_email_payload(email_type, user, data)
    assert payload["to_email"] == "t@example.com"
    assert "Test" in payload["html_content"]
    # Footer must always be there.
    assert "761 Rue Chalifoux" in payload["html_content"]
    assert "support@bidvex.com" in payload["html_content"]


def test_build_email_payload_handles_french():
    from services.email_templates import build_email_payload
    payload = build_email_payload("welcome", {"first_name": "Alice", "email": "a@b.com"}, {}, lang="fr")
    assert "Bonjour" in payload["html_content"]
    assert "L'équipe BidVex" in payload["html_content"]


def test_build_email_payload_rejects_unknown_type():
    from services.email_templates import build_email_payload
    with pytest.raises(ValueError):
        build_email_payload("nonexistent_type", {}, {})


# ---------------------------------------------------------------------------
# Mission 1 — Onboarding model fields
# ---------------------------------------------------------------------------
def test_onboarding_password_validator_accepts_strong_password():
    from routes.onboarding import _password_valid
    assert _password_valid("Strong1Password") is True
    assert _password_valid("OkayPass1") is True


def test_onboarding_password_validator_rejects_weak():
    from routes.onboarding import _password_valid
    assert _password_valid("short1") is False        # too short
    assert _password_valid("longbutnoupper1") is False
    assert _password_valid("LongButNoDigit") is False


def test_onboarding_body_schema_accepts_partial_fields():
    from routes.onboarding import OnboardingBody
    o = OnboardingBody(city="Montreal", province="QC")
    assert o.city == "Montreal"
    assert o.skip_all is False
    o2 = OnboardingBody(skip_all=True)
    assert o2.password is None and o2.skip_all


# ---------------------------------------------------------------------------
# Mission 5 — Promoted listings query helper
# ---------------------------------------------------------------------------
def test_promote_body_defaults_and_validates():
    from routes.promotions import PromoteBody
    b = PromoteBody(sections=["marketplace"], duration_days=7)
    assert b.tier == "featured"
    assert b.duration_days == 7
    b2 = PromoteBody()
    assert b2.sections == ["marketplace"]


def test_promotion_sections_constant_is_locked():
    from routes import promotions as mod
    expected = {"marketplace", "lots", "storage", "vehicles", "homepage"}
    assert mod._PROMOTION_SECTIONS == expected


# ---------------------------------------------------------------------------
# Mission 2 — Postal code validator
# ---------------------------------------------------------------------------
def test_canadian_postal_validator():
    from services.geo_resolver import _is_valid_ca_postal
    assert _is_valid_ca_postal("J1G 0A8")
    assert _is_valid_ca_postal("j1g0a8")
    assert not _is_valid_ca_postal("90210")    # US ZIP
    assert not _is_valid_ca_postal("ABC123")
    assert not _is_valid_ca_postal("")


# ---------------------------------------------------------------------------
# Mission 4 — persist_chat_turn shape
# ---------------------------------------------------------------------------
def test_persist_chat_turn_skips_anonymous():
    from routes import chat_history as mod
    mod.set_chat_history_db(MagicMock())
    out = asyncio.run(mod.persist_chat_turn(
        user_id=None,
        session_id=None,
        listing_id=None,
        user_message="hi",
        assistant_message="hello",
    ))
    assert out is None
    mod.set_chat_history_db(None)


def test_send_ai_notification_skips_when_db_missing():
    from routes import chat_history as mod
    mod.set_chat_history_db(None)
    out = asyncio.run(mod.send_ai_notification(
        user_id="u1", message_content="test",
    ))
    assert out["status"] == "skipped"
