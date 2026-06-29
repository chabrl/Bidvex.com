"""iter321 — Real-time SSE pub/sub broker + Live Support alerts tests."""
from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

import pytest

from routes import support_escalations as se
from services.genai_direct_client import WATCHDOG_SYSTEM_INSTRUCTION


# ─── Pub/Sub broker tests ────────────────────────────────────────────────


class TestBroker:
    @pytest.mark.asyncio
    async def test_subscribe_and_publish_delivers(self):
        b = se._EscalationBroker()
        q = await b.subscribe()
        await b.publish("new_ticket", {"id": "abc"})
        msg = await asyncio.wait_for(q.get(), timeout=1.0)
        assert msg["event"] == "new_ticket"
        assert msg["data"]["id"] == "abc"
        await b.unsubscribe(q)
        assert b.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_publish_fan_out_to_multiple_subscribers(self):
        b = se._EscalationBroker()
        q1 = await b.subscribe()
        q2 = await b.subscribe()
        q3 = await b.subscribe()
        assert b.subscriber_count == 3
        await b.publish("new_ticket", {"id": "fan-out"})
        for q in (q1, q2, q3):
            m = await asyncio.wait_for(q.get(), timeout=1.0)
            assert m["data"]["id"] == "fan-out"
        for q in (q1, q2, q3):
            await b.unsubscribe(q)
        assert b.subscriber_count == 0

    @pytest.mark.asyncio
    async def test_publish_after_unsubscribe_does_not_deliver(self):
        b = se._EscalationBroker()
        q = await b.subscribe()
        await b.unsubscribe(q)
        await b.publish("new_ticket", {"id": "x"})
        # The unsubscribed queue should NOT receive the event.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(q.get(), timeout=0.2)

    @pytest.mark.asyncio
    async def test_publish_drops_slow_consumer_silently(self):
        b = se._EscalationBroker()
        # Saturate one queue, then publish — should NOT raise.
        q = asyncio.Queue(maxsize=1)
        b._subscribers.append(q)  # type: ignore[attr-defined]
        q.put_nowait({"event": "x", "data": {}})
        # Now broker.publish should silently skip this slow consumer.
        await b.publish("new_ticket", {"id": "drop"})
        # No exception means pass.
        assert True


# ─── System prompt audit (iter321 strict marker contract) ────────────────


class TestPromptStrictMarkerContract:
    def test_prompt_has_incorrect_example_anti_pattern(self):
        """iter321 — the prompt MUST teach the model what NOT to do."""
        assert "**INCORRECT (NO ticket gets created" in WATCHDOG_SYSTEM_INSTRUCTION
        assert "No marker = no ticket" in WATCHDOG_SYSTEM_INSTRUCTION

    def test_prompt_orders_marker_before_confirmation(self):
        """The marker must be emitted FIRST (PART 1), confirmation SECOND."""
        body = WATCHDOG_SYSTEM_INSTRUCTION
        marker_part_idx = body.find("**PART 1 — Start your reply with the literal marker")
        confirm_part_idx = body.find("**PART 2 — On the next line, append")
        assert marker_part_idx > 0
        assert confirm_part_idx > marker_part_idx, (
            "PART 1 (marker emission) must be ordered BEFORE PART 2 (confirmation)."
        )

    def test_prompt_explicitly_forbids_code_fence_wrap(self):
        assert "wrapped in code fences" in WATCHDOG_SYSTEM_INSTRUCTION
        # Hard rule: NEVER wrap the marker in ``` fences
        assert "NOT wrapped in any markdown fences" in WATCHDOG_SYSTEM_INSTRUCTION

    def test_prompt_post_emit_mode_uses_distinct_wording(self):
        """The old 'Your ticket is open. An agent will contact you shortly.'
        post-emit boilerplate was being confused with the pre-emit prose. The
        iter321 prompt uses a DISTINCT phrase 'Ticket already created' so
        the model never conflates the two."""
        body = WATCHDOG_SYSTEM_INSTRUCTION
        assert "✅ Ticket already created" in body
        assert "✅ Demande déjà créée" in body


# ─── Stream auth (manual JWT resolver) ───────────────────────────────────


class TestStreamAuth:
    @pytest.mark.asyncio
    async def test_stream_resolver_rejects_missing_token(self):
        from fastapi import HTTPException
        from unittest.mock import MagicMock

        class _FakeReq:
            cookies: dict = {}
            headers: dict = {}

        req = _FakeReq()
        with pytest.raises(HTTPException) as exc:
            await se._resolve_admin_from_query_or_header(req, None)
        assert exc.value.status_code == 401


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
