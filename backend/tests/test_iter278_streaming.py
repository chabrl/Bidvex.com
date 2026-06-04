"""
iter278 — Streaming AI Core (SSE) verification.

Critical correction documented in `services/ai_service.py`: the
`emergentintegrations` library does NOT expose native token streaming
(verified via `inspect` — only `send_message()` returning a single
string exists). iter278 ships a faithful equivalent: server-side
chunking over SSE that produces the typewriter UX.

Coverage:

Mission 1 — Server-side chunker + generator
  • `_slice_for_streaming` honours word boundaries and the chunk cap.
  • `chat_stream_with_assistant` is an async-generator returning at
    least one chunk in test mode, and never raises.
  • Empty input yields exactly one `[STREAM_ERROR]` chunk.

Mission 2 — SSE endpoint shape
  • `POST /api/support/chat/stream` requires JWT (anonymous 401/403).
  • Authenticated test-mode stream emits:
        event: start
        event: chunk  (≥ 1 times)
        event: done
    with each `data:` line as valid JSON.
  • `text/event-stream` content-type + no-cache + nginx-no-buffer
    headers are set.

Mission 3 — Frontend consumer + robustness
  • Widget uses `fetch` + `ReadableStream` (NOT EventSource, which
    can't carry JWT).
  • Imports include AbortController-driven cancellation +
    `_parseSseBlock` helper.
  • Streaming bubble carries `streaming: true` flag and a cursor
    testid; finalize helper sets `partial: true` when an error
    interrupts mid-stream.
  • Stop button (`ai-core-stop`) replaces Send while streaming.

Mission 4 — Locale parity
  • `stopLabel` and `partialLabel` exist in BOTH en.json and fr.json
    under `aiCore`.

Mission 5 — Full regression sanity
  • iter276 non-streaming endpoint still works unchanged.
"""
from __future__ import annotations

import asyncio
import json
import os

import httpx
import pytest


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, "..", "frontend", "src"))
BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8001")


def _read_fe(rel: str) -> str:
    with open(os.path.join(FRONTEND_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


def _login_admin():
    try:
        r = httpx.post(
            f"{BASE}/api/auth/login",
            json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
            timeout=8.0,
        )
        if r.status_code != 200:
            return None
        return r.json().get("access_token") or r.json().get("token")
    except Exception:
        return None


# ── Mission 1 — Chunker + generator ───────────────────────────────────


def test_iter278_slice_helper_honours_word_boundaries():
    from services.ai_service import _slice_for_streaming
    text = "Hello there friend, this is a streaming test of the AI Core."
    chunks = list(_slice_for_streaming(text, soft_limit=12))
    # No chunk exceeds the cap by more than one whole word.
    for c in chunks:
        assert len(c) <= 24, f"chunk too long: {len(c)} chars"
    # Re-joining must reproduce the original text exactly.
    assert "".join(chunks) == text
    # At least one chunk should fit comfortably inside the limit.
    assert any(0 < len(c) <= 12 for c in chunks)


def test_iter278_slice_helper_handles_edge_cases():
    from services.ai_service import _slice_for_streaming
    assert list(_slice_for_streaming("")) == []
    # A single very long unbroken word is preserved as one chunk even
    # if it overflows the soft limit — chunking honours boundaries.
    long_word = "x" * 80
    chunks = list(_slice_for_streaming(long_word, soft_limit=10))
    assert "".join(chunks) == long_word


def test_iter278_chat_stream_with_assistant_yields_chunks_in_test_mode():
    """End-to-end async-generator behaviour — test mode never hits
    the network and yields more than one chunk so we know the chunker
    is actually being driven by the generator."""
    from services.ai_service import chat_stream_with_assistant

    async def collect():
        out = []
        async for piece in chat_stream_with_assistant(
            "iter278-test", "hello",
            test_mode_override=True,
            chunk_delay_ms=0,        # no sleep — tests stay fast
        ):
            out.append(piece)
        return out

    chunks = asyncio.run(collect())
    assert len(chunks) >= 2, "test-mode stream must yield multiple chunks"
    assert all(isinstance(c, str) for c in chunks)
    assert "".join(chunks).startswith("[TEST_MODE]")
    # No stream-error frame in the happy path.
    assert not any(c.startswith("[STREAM_ERROR]") for c in chunks)


def test_iter278_chat_stream_empty_message_yields_stream_error():
    from services.ai_service import chat_stream_with_assistant

    async def collect():
        out = []
        async for piece in chat_stream_with_assistant(
            "iter278-empty", "   ",
            test_mode_override=True,
            chunk_delay_ms=0,
        ):
            out.append(piece)
        return out

    chunks = asyncio.run(collect())
    assert len(chunks) == 1
    assert chunks[0].startswith("[STREAM_ERROR]")
    assert "empty_message" in chunks[0]


# ── Mission 2 — SSE endpoint shape ────────────────────────────────────


def test_iter278_stream_endpoint_rejects_anonymous():
    r = httpx.post(
        f"{BASE}/api/support/chat/stream",
        json={"message": "ping"},
        timeout=8.0,
    )
    assert r.status_code in (401, 403), r.text


def test_iter278_stream_endpoint_returns_sse_content_type():
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable (likely rate-limited)")
    # Use stream=True so we can inspect headers without buffering the body.
    with httpx.stream(
        "POST",
        f"{BASE}/api/support/chat/stream",
        json={"message": "hello"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20.0,
    ) as r:
        assert r.status_code == 200, r.text
        ctype = r.headers.get("content-type", "")
        assert "text/event-stream" in ctype, f"unexpected content-type: {ctype}"
        cc = r.headers.get("cache-control", "")
        assert "no-cache" in cc
        # nginx / k8s ingress buffer-off header
        assert r.headers.get("x-accel-buffering") == "no"


def test_iter278_stream_endpoint_emits_canonical_sse_event_sequence():
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable")
    events = []
    with httpx.stream(
        "POST",
        f"{BASE}/api/support/chat/stream",
        json={"message": "iter278 happy path"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=20.0,
    ) as r:
        assert r.status_code == 200
        buf = ""
        for raw in r.iter_text():
            buf += raw
            while "\n\n" in buf:
                block, buf = buf.split("\n\n", 1)
                event = "message"
                data = ""
                for line in block.split("\n"):
                    if line.startswith("event:"):
                        event = line[6:].strip()
                    elif line.startswith("data:"):
                        data += line[5:].strip()
                if not data:
                    continue
                try:
                    parsed = json.loads(data)
                except Exception:
                    parsed = {"raw": data}
                events.append((event, parsed))

    # Canonical sequence: start → chunk(s) → done. No errors in the
    # happy path. Allow extra `chunk` frames between start and done.
    kinds = [e[0] for e in events]
    assert kinds[0] == "start", f"first event must be `start`, got {kinds[:3]}"
    assert kinds[-1] == "done", f"last event must be `done`, got {kinds[-3:]}"
    chunk_events = [e for e in events if e[0] == "chunk"]
    assert len(chunk_events) >= 1, "stream must emit at least one chunk"
    assert not any(e[0] == "error" for e in events), "happy path must NOT emit error"

    # The `done` frame carries the metadata block.
    done = events[-1][1]
    for k in ("session_id", "model", "test_mode", "had_error", "chunks"):
        assert k in done, f"done frame missing key: {k}"
    assert done["had_error"] is False
    assert done["test_mode"] is True
    assert done["chunks"] >= 1
    # All chunks reassemble to the iter276 test-mode stub string.
    full = "".join(e[1].get("text", "") for e in chunk_events)
    assert full.startswith("[TEST_MODE]")


def test_iter278_stream_endpoint_400_on_empty_message():
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable")
    r = httpx.post(
        f"{BASE}/api/support/chat/stream",
        json={"message": "   "},
        headers={"Authorization": f"Bearer {token}"},
        timeout=10.0,
    )
    assert r.status_code in (400, 422), r.text


# ── Mission 3 — Frontend consumer + robustness ────────────────────────


def test_iter278_widget_uses_fetch_streaming_not_axios():
    src = _read_fe("components/AICoreSupportWidget.jsx")
    # POSTs the streaming endpoint via `fetch` so we can read
    # `res.body.getReader()` — axios doesn't expose streams in browsers.
    assert "/support/chat/stream" in src
    assert "res.body.getReader()" in src
    assert "TextDecoder" in src
    # The legacy non-streaming axios POST must NOT still be the live
    # path — axios is no longer imported.
    assert "import axios" not in src
    assert "axios.post(`${API_BASE}/support/chat`," not in src


def test_iter278_widget_uses_abort_controller():
    src = _read_fe("components/AICoreSupportWidget.jsx")
    assert "AbortController" in src
    # The ref MUST be aborted on unmount to avoid leaking fetches.
    assert "abortRef.current.abort()" in src
    # And the Stop button wires to the same controller.
    assert "stopStream" in src


def test_iter278_widget_parses_sse_blocks_and_handles_each_event():
    src = _read_fe("components/AICoreSupportWidget.jsx")
    assert "_parseSseBlock" in src
    # SSE keep-alive comments (lines starting with ':') must be
    # silently skipped — the protocol uses them as heartbeats.
    assert "line.startsWith(':')" in src
    # The three canonical event types are all handled.
    for evt in ('chunk', 'error', 'done'):
        assert f"parsed.event === '{evt}'" in src, f"missing handler for SSE event: {evt}"


def test_iter278_widget_renders_typewriter_cursor_on_streaming_bubble():
    src = _read_fe("components/AICoreSupportWidget.jsx")
    assert 'data-testid="ai-core-stream-cursor"' in src
    # Cursor renders ONLY while the message bubble has `streaming=true`.
    assert "{m.streaming && (" in src
    # And the streaming flag is initialized on the placeholder message
    # so the typewriter begins instantly when the first chunk lands.
    assert "streaming: true" in src


def test_iter278_widget_swaps_send_for_stop_button_during_stream():
    src = _read_fe("components/AICoreSupportWidget.jsx")
    # The action button MUST switch testid + handler while `sending`.
    assert 'data-testid={sending ? "ai-core-stop" : "ai-core-send"}' in src
    assert "onClick={sending ? stopStream : sendMessage}" in src


def test_iter278_widget_marks_partial_on_mid_stream_failure():
    """Robustness contract — when a stream is interrupted, the
    partial text remains on screen but the bubble carries a `partial`
    flag + a "(partial)" suffix on the timestamp row."""
    src = _read_fe("components/AICoreSupportWidget.jsx")
    assert "_finalizeActiveStream" in src
    # The finalizer uses the local `receivedAnyChunk` boolean to decide
    # whether the partial UX should fire (we never want a clean stream
    # to render as "(partial)").
    assert "partial: receivedAnyChunk" in src
    # Per-bubble UI cell rendered with the localized partial label.
    assert "t('aiCore.partialLabel')" in src
    assert "data-testid={`ai-core-msg-partial-${idx}`}" in src


def test_iter278_widget_aborts_in_flight_stream_on_unmount():
    src = _read_fe("components/AICoreSupportWidget.jsx")
    # The cleanup useEffect must call abort() so leaving the dashboard
    # mid-stream doesn't leak a fetch.
    cleanup_block_start = src.find("useEffect(() => () => {")
    assert cleanup_block_start > 0, "missing cleanup useEffect"
    cleanup_block = src[cleanup_block_start:cleanup_block_start + 400]
    assert "abortRef.current.abort()" in cleanup_block


# ── Mission 4 — Locale parity ─────────────────────────────────────────


def _load_locale(name: str):
    with open(os.path.join(FRONTEND_ROOT, "locales", name), "r", encoding="utf-8") as fh:
        return json.load(fh)


def test_iter278_new_aicore_locale_keys_present_in_en_and_fr():
    en = _load_locale("en.json")["aiCore"]
    fr = _load_locale("fr.json")["aiCore"]
    for k in ("stopLabel", "partialLabel"):
        assert k in en, f"en.json aiCore missing: {k}"
        assert k in fr, f"fr.json aiCore missing: {k}"
        assert en[k] and fr[k]
    # And the FR strings must actually be French, not English fallback.
    assert "Arrêter" in fr["stopLabel"]
    assert fr["partialLabel"].lower() == "partiel"


def test_iter278_en_fr_aicore_key_sets_still_match():
    """Adding stopLabel + partialLabel must keep the EN/FR contract
    in lock-step. Drift between locales is a hard fail."""
    en_keys = set(_load_locale("en.json").get("aiCore", {}).keys())
    fr_keys = set(_load_locale("fr.json").get("aiCore", {}).keys())
    assert en_keys == fr_keys, (
        f"locale drift detected. EN-only: {en_keys - fr_keys}; "
        f"FR-only: {fr_keys - en_keys}"
    )


# ── Mission 5 — Existing non-streaming endpoint still works ───────────


def test_iter278_legacy_non_streaming_endpoint_still_lives():
    token = _login_admin()
    if not token:
        pytest.skip("admin login unavailable")
    r = httpx.post(
        f"{BASE}/api/support/chat",
        json={"message": "iter278 sanity"},
        headers={"Authorization": f"Bearer {token}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    # iter276 envelope shape is preserved untouched.
    assert all(k in body for k in ("response", "session_id", "model", "test_mode"))
    assert body["test_mode"] is True
    assert body["response"].startswith("[TEST_MODE]")
