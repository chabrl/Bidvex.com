"""
iter239 — Tests for the frontend wiring + email refactor follow-up bundle.

Coverage:
  - `notifications/unread-count` lightweight polling endpoint (auth gate + shape).
  - `genai_chat._resolve_user_id` JWT helper handles malformed creds.
  - `email_notifications.send_unified_email` delegates to build_email_payload.
  - `email_notifications.send_bid_placed_email` round-trips through the
     unified template (signature backward-compat preserved).
  - `email_notifications.send_outbid_email` likewise.
  - `email_notifications.send_storage_bid_placed_email` returns bool.
"""
from __future__ import annotations

import asyncio
from unittest.mock import patch, AsyncMock

import pytest


# ---------------------------------------------------------------------------
# notifications/unread-count
# ---------------------------------------------------------------------------
def test_unread_count_endpoint_anon_returns_401():
    import os
    import requests
    base = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not base:
        pytest.skip("REACT_APP_BACKEND_URL not configured")
    r = requests.get(f"{base}/api/notifications/unread-count", timeout=10)
    assert r.status_code in (401, 403)


# ---------------------------------------------------------------------------
# genai_chat._resolve_user_id
# ---------------------------------------------------------------------------
def test_genai_chat_resolve_user_id_anonymous():
    from routes.genai_chat import _resolve_user_id
    out = asyncio.get_event_loop().run_until_complete(_resolve_user_id(None))
    assert out is None


def test_genai_chat_resolve_user_id_malformed_token():
    from routes.genai_chat import _resolve_user_id
    from fastapi.security import HTTPAuthorizationCredentials
    bad = HTTPAuthorizationCredentials(scheme="Bearer", credentials="not-a-jwt")
    out = asyncio.get_event_loop().run_until_complete(_resolve_user_id(bad))
    assert out is None


# ---------------------------------------------------------------------------
# Unified email dispatch
# ---------------------------------------------------------------------------
def test_send_unified_email_routes_through_build_email_payload():
    from services.email_notifications import send_unified_email
    with patch("services.email_notifications.send_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"status": "sent", "to": "x@y.z"}
        asyncio.get_event_loop().run_until_complete(
            send_unified_email(
                "welcome",
                user={"email": "alice@example.com", "first_name": "Alice"},
            )
        )
        assert mock_send.await_count == 1
        kwargs = mock_send.await_args.kwargs
        assert kwargs["to_email"] == "alice@example.com"
        assert "Welcome to BidVex" in kwargs["subject"]
        assert "Alice" in kwargs["html_content"]
        assert "Explore Marketplace" in kwargs["html_content"]


def test_legacy_send_bid_placed_email_uses_unified_template():
    from services.email_notifications import send_bid_placed_email
    with patch("services.email_notifications.send_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"status": "sent"}
        asyncio.get_event_loop().run_until_complete(send_bid_placed_email(
            bidder_email="bob@example.com",
            bidder_name="Bob",
            listing_title="Vintage Coin",
            bid_amount=123.45,
            listing_id="abc",
            auction_end_date="2099-01-01T00:00:00",
            is_leading=True,
        ))
        kwargs = mock_send.await_args.kwargs
        assert kwargs["to_email"] == "bob@example.com"
        # The unified template subject derives from the headline.
        assert "Bid is Live" in kwargs["subject"]
        # Body should contain bid amount + listing title.
        assert "123.45" in kwargs["html_content"]
        assert "Vintage Coin" in kwargs["html_content"]
        # Lead vs outbid messaging surfaces via secondary block.
        assert "highest bidder" in kwargs["html_content"]


def test_legacy_send_outbid_email_uses_unified_template():
    from services.email_notifications import send_outbid_email
    with patch("services.email_notifications.send_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"status": "sent"}
        asyncio.get_event_loop().run_until_complete(send_outbid_email(
            user_email="carol@example.com",
            user_name="Carol",
            listing_title="Rare Watch",
            their_bid=100.0,
            new_high_bid=110.0,
            listing_id="xyz",
            auction_end_date="2099-01-01T00:00:00",
        ))
        kwargs = mock_send.await_args.kwargs
        assert kwargs["to_email"] == "carol@example.com"
        assert "Outbid" in kwargs["subject"]
        assert "Rare Watch" in kwargs["html_content"]
        # New high bid surfaces in the body.
        assert "110.00" in kwargs["html_content"]


def test_legacy_send_storage_bid_placed_returns_bool():
    from services.email_notifications import send_storage_bid_placed_email
    with patch("services.email_notifications.send_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = {"status": "sent"}
        out = asyncio.get_event_loop().run_until_complete(send_storage_bid_placed_email(
            buyer={"email": "dave@example.com", "name": "Dave"},
            auction={"id": "auction-uuid-here"},
            bid_state={"current_bid": 250.0, "you_are_winning": True},
        ))
        assert out is True
        kwargs = mock_send.await_args.kwargs
        assert "auction-uu" in kwargs["html_content"] or "Storage Unit" in kwargs["html_content"]


def test_legacy_send_storage_outbid_returns_bool_false_when_no_email():
    from services.email_notifications import send_storage_outbid_email
    out = asyncio.get_event_loop().run_until_complete(send_storage_outbid_email(
        buyer={},
        auction={"id": "a"},
        new_current=99.0,
    ))
    assert out is False


# ---------------------------------------------------------------------------
# chat_history persistence guard
# ---------------------------------------------------------------------------
def test_persist_chat_turn_skips_anonymous():
    from routes.chat_history import persist_chat_turn
    out = asyncio.get_event_loop().run_until_complete(persist_chat_turn(
        user_id=None,
        session_id=None,
        listing_id=None,
        user_message="hi",
        assistant_message="hello",
    ))
    assert out is None


# ---------------------------------------------------------------------------
# Promotions endpoint shape
# ---------------------------------------------------------------------------
def test_promoted_listings_endpoint_smoke():
    import os
    import requests
    base = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not base:
        pytest.skip("REACT_APP_BACKEND_URL not configured")
    r = requests.get(f"{base}/api/promoted-listings?section=marketplace&limit=4", timeout=10)
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    assert isinstance(data["items"], list)
    assert data.get("section") == "marketplace"
