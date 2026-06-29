"""iter322 — Bug fixes (password reset + admin verify) + Interactive chat tests."""
from __future__ import annotations

import asyncio
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest

from routes import support_escalations as se


# ─── Pub/Sub broker — user-targeted events (iter322) ─────────────────────


class TestUserBroker:
    @pytest.mark.asyncio
    async def test_publish_to_user_only_delivers_to_that_user(self):
        b = se._EscalationBroker()
        alice = await b.subscribe_user("alice-id")
        bob = await b.subscribe_user("bob-id")
        # Publish to alice
        await b.publish_to_user("alice-id", "admin_reply", {"ticket_id": "t1"})
        msg = await asyncio.wait_for(alice.get(), timeout=1.0)
        assert msg["event"] == "admin_reply"
        assert msg["data"]["ticket_id"] == "t1"
        # Bob should NOT receive alice's event
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(bob.get(), timeout=0.2)
        await b.unsubscribe_user("alice-id", alice)
        await b.unsubscribe_user("bob-id", bob)
        assert b.user_subscriber_count == 0

    @pytest.mark.asyncio
    async def test_user_can_have_multiple_open_tabs(self):
        b = se._EscalationBroker()
        tab1 = await b.subscribe_user("u1")
        tab2 = await b.subscribe_user("u1")
        tab3 = await b.subscribe_user("u1")
        assert b.user_subscriber_count == 3
        await b.publish_to_user("u1", "admin_reply", {"id": "abc"})
        for q in (tab1, tab2, tab3):
            m = await asyncio.wait_for(q.get(), timeout=1.0)
            assert m["data"]["id"] == "abc"

    @pytest.mark.asyncio
    async def test_unsubscribe_user_cleans_empty_lists(self):
        b = se._EscalationBroker()
        q = await b.subscribe_user("solo")
        assert "solo" in b._user_subscribers
        await b.unsubscribe_user("solo", q)
        # Last subscriber removed → key cleaned up from dict.
        assert "solo" not in b._user_subscribers


# ─── Bug fixes audit (iter322) ────────────────────────────────────────────


class TestBugAAdminResetExpiresAt:
    """Bug A — admin_user_management.py:415 used to store expires_at=NOW,
    making the token instantly expired. Verify the source now adds 1h."""

    def test_admin_reset_password_expires_in_one_hour(self):
        src = (BACKEND_ROOT / "routes/admin_user_management.py").read_text()
        # The fix must use `+ timedelta(hours=1)` for the admin-issued token.
        assert "datetime.now(timezone.utc) + timedelta(hours=1)" in src, (
            "Bug A regression — admin-issued password reset must give the token "
            "a 1-hour lifetime, not NOW."
        )
        # The token row must also include used=False (was missing pre-iter322).
        assert '"used": False' in src

    def test_admin_reset_password_url_uses_env_var(self):
        src = (BACKEND_ROOT / "routes/admin_user_management.py").read_text()
        # The reset URL must read FRONTEND_URL, not be hardcoded to bidvex.com.
        assert 'os.environ.get("FRONTEND_URL"' in src
        assert "https://www.bidvex.com/reset-password" not in src


class TestBugBPasswordResetURLEnvVar:
    """Bug B — email_templates.py:168 was hardcoded to https://bidvex.com.
    iter322 fix: read FRONTEND_URL env var so preview works too."""

    def test_password_reset_email_template_uses_frontend_url(self):
        src = (BACKEND_ROOT / "config/email_templates.py").read_text()
        # The fix must reference FRONTEND_URL env var.
        assert 'FRONTEND_URL' in src
        # The bare hardcoded URL must be gone from the template builder.
        # (Other occurrences in `change_password_email` / `explore_url` are
        # allowed — only the reset-password builder is affected.)
        # Test the change applied to the password_reset_email function:
        builder_block = src.split("def password_reset_email")[1].split("def password_changed_email")[0]
        assert 'reset_url = f"https://bidvex.com/reset-password' not in builder_block
        assert 'f"{frontend_url}/reset-password?token=' in builder_block


class TestBugCAdminVerifyKeyMismatch:
    """Bug C — admin.py:261 read `verified` from payload but frontend sends
    `admin_verified`. iter322 fix: accept either key."""

    def test_admin_verify_endpoint_accepts_admin_verified_key(self):
        src = (BACKEND_ROOT / "routes/admin.py").read_text()
        # Must read 'admin_verified' from the request payload.
        assert 'if "admin_verified" in data' in src
        assert 'data.get("admin_verified"' in src


# ─── Interactive chat (iter322) — endpoint surface audit ──────────────────


class TestInteractiveChatEndpointsExist:
    def test_admin_reply_endpoint_registered(self):
        # Pulled into context above — the route should exist on the router.
        routes = [getattr(r, "path", "") for r in se.router.routes]
        assert "/admin/support/escalations/{ticket_id}/reply" in routes

    def test_user_reply_endpoint_registered(self):
        routes = [getattr(r, "path", "") for r in se.router.routes]
        assert "/support/escalations/{ticket_id}/reply" in routes

    def test_user_stream_endpoint_registered(self):
        routes = [getattr(r, "path", "") for r in se.router.routes]
        assert "/support/escalations/user/stream" in routes


# ─── ReplyRequest validation ──────────────────────────────────────────────


class TestReplyRequestValidation:
    def test_empty_message_is_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            se.ReplyRequest(message="")

    def test_too_long_message_is_rejected(self):
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            se.ReplyRequest(message="x" * 2501)

    def test_valid_message_accepted(self):
        r = se.ReplyRequest(message="Hello there")
        assert r.message == "Hello there"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
