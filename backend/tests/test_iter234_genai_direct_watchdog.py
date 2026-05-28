"""
iter234 — Unit tests for the direct google-genai (Gemini 2.5 Flash) integration.

These tests cover wiring + happy-path logic with a fully-mocked Gemini client
so they pass without burning real API credits OR depending on a valid key.
The live key was revoked by Google on Feb 26, 2026 (reported as leaked);
the production behaviour was verified manually before that.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# 1. Client / config wiring
# ---------------------------------------------------------------------------
def test_system_instruction_matches_user_spec():
    from services.genai_direct_client import WATCHDOG_SYSTEM_INSTRUCTION
    # Spot-check the canonical paragraph headers from the user's iter234 spec.
    assert "advanced AI core for BidVex" in WATCHDOG_SYSTEM_INSTRUCTION
    assert "Marketplace Watchdog/Fraud Detector" in WATCHDOG_SYSTEM_INSTRUCTION
    assert "Customer Support Specialist" in WATCHDOG_SYSTEM_INSTRUCTION
    assert "Bilingual Excellence" in WATCHDOG_SYSTEM_INSTRUCTION
    assert "Daily Traffic Overview" in WATCHDOG_SYSTEM_INSTRUCTION
    assert "Flagged Suspicious Activity" in WATCHDOG_SYSTEM_INSTRUCTION
    assert "Watchdog Action Items" in WATCHDOG_SYSTEM_INSTRUCTION


def test_build_generation_config_locks_invariants():
    from services.genai_direct_client import build_generation_config
    cfg = build_generation_config()
    # Thinking budget = -1 (dynamic)
    assert cfg.thinking_config.thinking_budget == -1
    # Google Search tool wired
    assert cfg.tools is not None and len(cfg.tools) == 1
    tool = cfg.tools[0]
    assert tool.google_search is not None
    # System instruction starts with the locked watchdog persona
    sys_text = cfg.system_instruction
    if hasattr(sys_text, "parts"):
        sys_text = "".join(getattr(p, "text", "") for p in sys_text.parts)
    assert "advanced AI core for BidVex" in str(sys_text)


def test_build_generation_config_appends_extra_context():
    from services.genai_direct_client import build_generation_config
    cfg = build_generation_config(extra_system_instruction="RUNTIME: testing mode")
    txt = cfg.system_instruction
    if hasattr(txt, "parts"):
        txt = "".join(getattr(p, "text", "") for p in txt.parts)
    assert "RUNTIME: testing mode" in str(txt)
    assert "Additional Runtime Context" in str(txt)


def test_build_generation_config_can_disable_search():
    from services.genai_direct_client import build_generation_config
    cfg = build_generation_config(enable_google_search=False)
    assert not cfg.tools


def test_get_genai_client_requires_key(monkeypatch):
    import services.genai_direct_client as mod
    # Force-reset the singleton + clear env var
    mod._client_singleton = None
    mod._client_key_fingerprint = None
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="GEMINI_API_KEY"):
        mod.get_genai_client()


# ---------------------------------------------------------------------------
# 2. Streaming chat — mocked iterator
# ---------------------------------------------------------------------------
def test_stream_chat_chunks_emits_bytes_in_order():
    from services import genai_streaming_chat as svc

    fake_chunks = [MagicMock(text="Hello"), MagicMock(text=", "), MagicMock(text="world!")]
    fake_client = MagicMock()
    fake_client.models.generate_content_stream.return_value = iter(fake_chunks)

    with patch.object(svc, "get_genai_client", return_value=fake_client):
        out = b"".join(svc.stream_chat_chunks("ping"))
    assert out == b"Hello, world!"


def test_stream_chat_chunks_empty_prompt_short_circuits():
    from services.genai_streaming_chat import stream_chat_chunks
    out = b"".join(stream_chat_chunks("   "))
    assert b"(empty prompt)" in out


def test_stream_chat_chunks_surfaces_errors_gracefully():
    from services import genai_streaming_chat as svc

    fake_client = MagicMock()
    fake_client.models.generate_content_stream.side_effect = RuntimeError("boom")

    with patch.object(svc, "get_genai_client", return_value=fake_client):
        out = b"".join(svc.stream_chat_chunks("anything"))
    assert b"[stream-error] RuntimeError: boom" in out


# ---------------------------------------------------------------------------
# 3. Watchdog — payload aggregation + analysis call
# ---------------------------------------------------------------------------
class _FakeAsyncCursor:
    def __init__(self, docs):
        self._docs = docs

    def sort(self, *a, **kw):
        return self

    def limit(self, *a, **kw):
        return self

    async def to_list(self, length=None):
        return self._docs[: (length or len(self._docs))]


class _FakeCollection:
    def __init__(self, docs):
        self._docs = docs

    def find(self, *a, **kw):
        return _FakeAsyncCursor(self._docs)


class _FakeDB:
    def __init__(self, collections):
        self._collections = collections

    def __getitem__(self, name):
        return self._collections.get(name, _FakeCollection([]))


def test_fetch_activity_payload_concatenates_collections():
    from services.genai_watchdog import fetch_activity_payload

    now = datetime.now(timezone.utc)
    db = _FakeDB({
        "user_sessions": _FakeCollection([
            {"user_id": "u1", "email": "a@b.com", "created_at": now, "ip_address": "1.1.1.1", "action": "login"},
            {"user_id": "u2", "email": "c@d.com", "created_at": now, "ip_address": "2.2.2.2", "action": "login"},
        ]),
        "bids": _FakeCollection([
            {"bidder_id": "u1", "bidder_email": "a@b.com", "listing_id": "lst-1",
             "amount": 100, "currency": "CAD", "created_at": now, "bidder_type": "buyer", "ip_address": "1.1.1.1"},
        ]),
    })
    bundle = asyncio.run(fetch_activity_payload(db, window_hours=24))
    assert bundle["stats"]["user_sessions"] == 2
    assert bundle["stats"]["bids"] == 1
    assert "USER_SESSIONS" in bundle["payload_text"]
    assert "BIDS" in bundle["payload_text"]
    assert "a@b.com" in bundle["payload_text"]
    assert "lst-1" in bundle["payload_text"]


def test_run_watchdog_analysis_uses_gemini_client():
    from services import genai_watchdog as svc

    fake_response = MagicMock()
    fake_response.text = "## Daily Traffic Overview\n2 users active.\n\n## Flagged Suspicious Activity\nNone.\n\n## Watchdog Action Items\nNo action."
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    with patch.object(svc, "get_genai_client", return_value=fake_client):
        out = svc.run_watchdog_analysis(
            "[session log line]",
            window_start_iso="2026-02-25T00:00:00+00:00",
            window_end_iso="2026-02-26T00:00:00+00:00",
        )
    assert "Daily Traffic Overview" in out
    call_args = fake_client.models.generate_content.call_args
    assert call_args.kwargs["model"] == "gemini-2.5-flash"
    # The payload is wrapped between the canonical fences.
    assert "=== ACTIVITY LOGS START ===" in call_args.kwargs["contents"]
    # System instruction + dynamic thinking + google search are all on the config
    cfg = call_args.kwargs["config"]
    assert cfg.thinking_config.thinking_budget == -1
    assert cfg.tools and cfg.tools[0].google_search is not None


def test_watchdog_recipient_locked_to_charbel():
    from services.genai_watchdog import WATCHDOG_RECIPIENT_EMAIL
    assert WATCHDOG_RECIPIENT_EMAIL == "charbel911@gmail.com"


# ---------------------------------------------------------------------------
# 4. Full daily cycle (mocked Gemini + mocked SendGrid)
# ---------------------------------------------------------------------------
def test_run_daily_watchdog_cycle_emits_email():
    from services import genai_watchdog as svc

    fake_response = MagicMock()
    fake_response.text = "## Daily Traffic Overview\nAll quiet."
    fake_client = MagicMock()
    fake_client.models.generate_content.return_value = fake_response

    async def fake_send_email(**kwargs):
        return {"status": "sent", "to": kwargs["to_email"], "subject": kwargs["subject"]}

    db = _FakeDB({"user_sessions": _FakeCollection([])})
    # Patch genai client + send_email
    with patch.object(svc, "get_genai_client", return_value=fake_client):
        with patch("services.email_notifications.send_email", side_effect=fake_send_email):
            result = asyncio.run(svc.run_daily_watchdog_cycle(db))

    assert result["status"] == "ok"
    assert result["delivery"]["status"] == "sent"
    assert result["delivery"]["to"] == "charbel911@gmail.com"
    assert "Watchdog" in result["delivery"]["subject"]
    assert fake_client.models.generate_content.called


# ---------------------------------------------------------------------------
# 5. Route shape — /api/chat/diagnostics
# ---------------------------------------------------------------------------
def test_diagnostics_route_exposes_locked_invariants():
    from routes.genai_chat import chat_diagnostics

    result = asyncio.run(chat_diagnostics())
    assert result["model"] == "gemini-2.5-flash"
    assert result["google_search_tool_enabled"] is True
    assert result["thinking_budget"] == -1
