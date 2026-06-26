"""
iter316 Phase B — backend tests for Mission B3 (AI Pipeline Failure
Notification) + Mission B5 (admin contractors list endpoint).
"""
from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock

import pytest

# Ensure backend dir is on sys.path so test imports work the same way
# as the existing iter316 suite.
import sys
sys.path.insert(0, "/app/backend")


# ─── In-memory mock for db.call_logs + db.notifications + db.users ─

class _MockCollection:
    def __init__(self):
        self.docs = []

    async def insert_one(self, doc):
        self.docs.append(doc)
        return type("R", (), {"inserted_id": doc.get("id") or doc.get("_id")})()

    async def find_one(self, q, proj=None):
        for d in self.docs:
            ok = True
            for k, v in q.items():
                if d.get(k) != v:
                    ok = False
                    break
            if ok:
                return d
        return None

    async def update_one(self, q, upd):
        for d in self.docs:
            ok = all(d.get(k) == v for k, v in q.items())
            if ok:
                for k, v in (upd.get("$set") or {}).items():
                    d[k] = v
                return type("R", (), {"modified_count": 1})()
        return type("R", (), {"modified_count": 0})()


class _MockDB:
    def __init__(self):
        self.call_logs = _MockCollection()
        self.notifications = _MockCollection()
        self.users = _MockCollection()


# ─── Mission B3 — AI Pipeline Failure Notification ────────────────────

@pytest.mark.asyncio
async def test_voice_ai_failure_inserts_bilingual_notification():
    """When the AI pipeline exhausts retries and lands on `failed`, a
    bilingual notification row must be inserted for the call's agent."""
    from services.voice_ai_pipeline import _process_one

    db = _MockDB()
    call_id = "test-call-b3-1"
    await db.call_logs.insert_one({
        "_id": call_id,
        "agent_user_id": "agent-42",
        "client_name": "Alex Lapointe",
        "client_phone": "+14155550199",
        "ai_processing_status": "pending",
    })

    # Force the gemini call to ALWAYS fail.
    async def _fail(_path):
        raise RuntimeError("gemini boom")

    with patch("services.voice_ai_pipeline._call_gemini_on_audio", new=_fail):
        await _process_one(call_id, "/tmp/does-not-matter.mp3", db, attempt=1)

    # call_log marked failed.
    log = await db.call_logs.find_one({"_id": call_id})
    assert log["ai_processing_status"] == "failed"
    assert "gemini boom" in (log.get("ai_processing_error") or "")

    # Notification inserted exactly once with bilingual fields.
    notifs = [n for n in db.notifications.docs if n["user_id"] == "agent-42"]
    assert len(notifs) == 1, f"expected 1 failure notif, got {len(notifs)}"
    n = notifs[0]
    assert n["type"] == "voice_ai_failed"
    # Bilingual companions present.
    assert "AI Call Analysis Failed" in n["title_en"]
    assert "Analyse IA" in n["title_fr"] or "analyse IA" in n["title_fr"]
    assert "Alex Lapointe" in n["message_en"]
    assert "Alex Lapointe" in n["message_fr"]
    # Action url deep-links into the dialer for the call.
    assert n["data"]["call_log_id"] == call_id
    assert "/admin/dialer" in n["data"]["action_url"]


@pytest.mark.asyncio
async def test_voice_ai_success_does_not_notify_failure():
    """Happy path: a successful AI run inserts NO failure notification."""
    from services.voice_ai_pipeline import _process_one

    db = _MockDB()
    call_id = "test-call-b3-2"
    await db.call_logs.insert_one({
        "_id": call_id,
        "agent_user_id": "agent-42",
        "client_name": "Happy Path",
        "client_phone": "+14155550133",
        "ai_processing_status": "pending",
    })

    async def _ok(_path):
        return {
            "transcript_speakers": [{"speaker": "Agent", "start_ms": 0, "end_ms": 1000, "text": "hi"}],
            "transcript_en": "Hi",
            "transcript_fr": "Salut",
            "sentiment_score": 0.6,
            "sentiment_label": "positive",
            "call_summary": "Quick check-in.",
            "action_items": ["follow up next week"],
        }

    with patch("services.voice_ai_pipeline._call_gemini_on_audio", new=_ok):
        await _process_one(call_id, "/tmp/x.mp3", db, attempt=1)

    log = await db.call_logs.find_one({"_id": call_id})
    assert log["ai_processing_status"] == "completed"
    # No failure-kind notification produced.
    failures = [n for n in db.notifications.docs if n["type"] == "voice_ai_failed"]
    assert failures == []


@pytest.mark.asyncio
async def test_voice_ai_failure_handles_missing_agent_gracefully():
    """If the call_log no longer has agent_user_id when failure fires,
    the notification step must NOT crash the pipeline."""
    from services.voice_ai_pipeline import _process_one

    db = _MockDB()
    call_id = "test-call-b3-3"
    await db.call_logs.insert_one({
        "_id": call_id,
        # no agent_user_id field
        "client_phone": "+14155550100",
        "ai_processing_status": "pending",
    })

    async def _fail(_):
        raise RuntimeError("nope")

    with patch("services.voice_ai_pipeline._call_gemini_on_audio", new=_fail):
        await _process_one(call_id, "/tmp/x.mp3", db, attempt=1)

    log = await db.call_logs.find_one({"_id": call_id})
    assert log["ai_processing_status"] == "failed"
    # No crash, no orphan notification with empty user_id.
    assert all(n.get("user_id") for n in db.notifications.docs)


# ─── Mission B5 — voice_ai_failed template bilingual sanity ────────

def test_voice_ai_failed_template_registered():
    from services.notifications_i18n import build_notification

    n = build_notification(
        user_id="u1",
        kind="voice_ai_failed",
        params={"client_name": "Marie"},
    )
    assert "Marie" in n["message_en"]
    assert "Marie" in n["message_fr"]
    assert n["title_en"].startswith("AI")
    assert "IA" in n["title_fr"]


# ─── Mission B5 — admin/contractors list endpoint structure ────────

def test_admin_list_contractors_endpoint_exists():
    """Smoke check that the new endpoint is registered on the router."""
    from routes.twilio import router as tw_router
    paths = {r.path for r in tw_router.routes}
    assert "/twilio/admin/contractors" in paths, (
        f"new endpoint not registered: {paths}"
    )
