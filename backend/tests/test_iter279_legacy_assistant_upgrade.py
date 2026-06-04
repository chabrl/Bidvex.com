"""
iter279 — Upgrade the legacy public AIAssistant in-place with the
iter278 streaming UX (typewriter cursor + rose Stop button), without
touching its existing route, history, or anonymous-access behavior.

Background:
    The screenshot user uploaded showed `components/AIAssistant.js` —
    the *site-wide* "Luxury Auction Specialist" widget — not the
    iter277 dashboard widget. That legacy assistant already streamed
    via its own `/chat/stream` endpoint but lacked the user-clickable
    Stop button + visible cursor. iter279 adds both, in-place,
    without changing the legacy backend route (which is intentionally
    public so anonymous marketplace visitors keep their assistant).

Coverage:

Mission 1 — Stop button + abort wiring
  • An `activeStreamCtrlRef` holds the in-flight AbortController so
    the user can interrupt mid-stream.
  • `handleStop()` reads the ref → clears it → calls `.abort()` in
    that order (sequencing matters: catch handler uses ref==null to
    detect user-initiated abort vs. internal timeout abort).
  • Cleanup useEffect aborts any in-flight stream on unmount.

Mission 2 — Typewriter cursor + partial badge
  • The streaming bubble renders an `ai-core-stream-cursor` span when
    `msg.streaming === true`. Branding parity preserved (cyan cursor
    matches the existing `#06B6D4` brand color, not the indigo cursor
    of the dashboard widget).
  • `ai-core-msg-partial-{idx}` badge shows up when a user stops a
    stream mid-flight.

Mission 3 — Send/Stop button swap
  • While `isLoading=true` the action button surfaces the Square icon
    + rose-600 styling + the `ai-core-stop` testid. While idle, the
    legacy `ai-assistant-send-btn` testid + brand gradient styling +
    Send icon are unchanged.
  • Button is disabled only when `!isLoading && !input.trim()` —
    while streaming, the Stop button is ALWAYS enabled.

Mission 4 — User abort UX (no giant red error CTA)
  • The catch block distinguishes user-aborts from real failures by
    checking `e.name === 'AbortError' && !activeStreamCtrlRef.current`.
  • On user abort, the partial bubble is finalized with `partial:true`
    and the existing red "Service temporarily unavailable" CTA is NOT
    rendered.
  • Real failures (network down, both attempts exhausted) still
    surface the legacy CTA.

Mission 5 — Branding + scope preservation
  • Header literals "BidVex AI Core" and "Your Luxury Auction
    Specialist" remain in the file.
  • Footer literal "Powered by Gemini 2.5 Flash" remains.
  • The legacy `/chat/stream` endpoint (NOT iter278's `/support/chat/stream`)
    is still the only fetch target — anonymous public visitors keep
    their assistant.
"""
from __future__ import annotations

import os

import pytest  # noqa: F401  (kept for parity with sibling suites)


BACKEND_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_ROOT = os.path.abspath(os.path.join(BACKEND_ROOT, "..", "frontend", "src"))


def _read_fe(rel: str) -> str:
    with open(os.path.join(FRONTEND_ROOT, rel), "r", encoding="utf-8") as fh:
        return fh.read()


# ── Mission 1 — Stop button + abort wiring ────────────────────────────


def test_iter279_assistant_holds_active_stream_controller_ref():
    src = _read_fe("components/AIAssistant.js")
    assert "activeStreamCtrlRef" in src
    # Initialized as a ref (not state — refs survive re-renders without
    # triggering them).
    assert "useRef(null)" in src
    # Comment-line documenting the iter279 intent.
    assert "iter279" in src


def test_iter279_stream_helper_publishes_controller_to_ref():
    """When `streamOnce` creates its AbortController it MUST publish
    it to the ref so the user-clickable Stop button can read + abort
    the in-flight fetch."""
    src = _read_fe("components/AIAssistant.js")
    assert "activeStreamCtrlRef.current = ctrl" in src
    # And the ref MUST be released in the finally block so a follow-up
    # turn doesn't try to abort the wrong fetch.
    assert "activeStreamCtrlRef.current === ctrl" in src
    assert "activeStreamCtrlRef.current = null" in src


def test_iter279_handle_stop_function_exists():
    src = _read_fe("components/AIAssistant.js")
    assert "const handleStop" in src
    # Ordering MATTERS — clear ref BEFORE calling abort so the catch
    # handler's `!activeStreamCtrlRef.current` check identifies the
    # abort as user-initiated rather than a timeout-initiated abort.
    handle_stop_idx = src.find("const handleStop")
    body_end = src.find("};", handle_stop_idx)
    block = src[handle_stop_idx:body_end]
    null_idx = block.find("activeStreamCtrlRef.current = null")
    abort_idx = block.find("ctrl.abort()")
    assert 0 < null_idx < abort_idx, (
        "handleStop must null the ref BEFORE calling abort() so the "
        "user-abort branch in catch identifies correctly"
    )


def test_iter279_unmount_cleanup_aborts_in_flight_stream():
    """If the component unmounts (route change / hot reload) while a
    stream is in flight, the controller must be aborted so we don't
    leak the socket."""
    src = _read_fe("components/AIAssistant.js")
    # The cleanup useEffect (returns an arrow function from the
    # effect body — `useEffect(() => () => { ... }, []);`).
    cleanup_idx = src.find("useEffect(() => () => {")
    assert cleanup_idx > 0, "missing unmount cleanup useEffect"
    block = src[cleanup_idx:cleanup_idx + 500]
    assert "activeStreamCtrlRef.current" in block
    assert "ctrl.abort()" in block


# ── Mission 2 — Typewriter cursor + partial badge ─────────────────────


def test_iter279_typewriter_cursor_rendered_on_streaming_bubble():
    src = _read_fe("components/AIAssistant.js")
    assert 'data-testid="ai-core-stream-cursor"' in src
    # Cursor renders ONLY while the bubble has `msg.streaming === true`.
    assert "{msg.streaming && (" in src
    # Branding parity — cyan cursor (#06B6D4), not the indigo of the
    # dashboard widget. The legacy assistant keeps its brand palette.
    assert "bg-[#06B6D4]" in src or "bg-cyan" in src


def test_iter279_partial_badge_renders_on_interrupted_bubble():
    src = _read_fe("components/AIAssistant.js")
    # Per-bubble badge — testid is a template literal so the spec
    # can target any specific message index.
    assert "data-testid={`ai-core-msg-partial-${idx}`}" in src
    # Bilingual label visible inside the badge (the legacy assistant
    # is bilingual EN/FR site-wide).
    assert "partial" in src
    assert "partiel" in src
    # Conditional render on the `msg.partial` flag.
    assert "{msg.partial &&" in src


# ── Mission 3 — Send/Stop button swap ─────────────────────────────────


def test_iter279_action_button_swaps_send_for_stop_during_stream():
    src = _read_fe("components/AIAssistant.js")
    # Conditional testid — Send when idle, Stop when streaming.
    assert 'data-testid={isLoading ? "ai-core-stop" : "ai-assistant-send-btn"}' in src
    # Conditional aria-label too.
    assert 'aria-label={isLoading ? "Stop generating" : "Send message"}' in src
    # onClick branches between the two handlers.
    assert "onClick={isLoading ? handleStop : handleSend}" in src
    # Stop button uses the rose palette to match the dashboard widget.
    assert "bg-rose-600" in src
    # While streaming the button must NOT be disabled (the legacy code
    # disabled it whenever `isLoading` was true — that prevented the
    # user from interrupting at all).
    assert "disabled={!isLoading && !input.trim()}" in src
    # Square icon is imported from lucide so the Stop button renders.
    assert "Square" in src.split("from 'lucide-react'")[0]


# ── Mission 4 — User abort UX (no giant red error CTA) ────────────────


def test_iter279_catch_branch_distinguishes_user_abort_from_failure():
    """The legacy catch surfaced a giant red 'Service temporarily
    unavailable' CTA on every error. iter279 distinguishes the case
    where the user clicked Stop (AbortError + ref already cleared by
    handleStop) so the bubble is finalized as partial WITHOUT the CTA."""
    src = _read_fe("components/AIAssistant.js")
    assert "wasUserAbort" in src
    # The two conditions composed: AbortError AND the ref has already
    # been cleared by handleStop (the catch arrives after the abort,
    # so by then the ref is null).
    assert "e?.name === 'AbortError'" in src
    assert "!activeStreamCtrlRef.current" in src
    # User-abort branch finalizes the streaming bubble with partial:true.
    assert "partial: true" in src
    # Real-failure branch still surfaces the legacy CTA.
    assert "Service temporarily unavailable" in src


# ── Mission 5 — Branding + scope preservation ─────────────────────────


def test_iter279_assistant_retains_luxury_specialist_branding():
    src = _read_fe("components/AIAssistant.js")
    # Header branding strings remain intact — the user explicitly
    # asked us to retain these.
    assert "BidVex AI Core" in src
    assert "Luxury Auction Specialist" in src
    # Footer branding remains intact.
    assert "Powered by Gemini 2.5 Flash" in src


def test_iter279_assistant_still_uses_legacy_chat_stream_endpoint():
    """The legacy `AIAssistant` mounts on PUBLIC pages (marketplace /
    homepage) so it MUST keep using its existing `/chat/stream` route
    — which permits anonymous access. The iter278 `/support/chat/stream`
    is JWT-only and would break anonymous visitors.

    This guard prevents a future refactor from accidentally repointing
    the public assistant at the protected endpoint."""
    src = _read_fe("components/AIAssistant.js")
    # The legacy endpoint must remain.
    assert "/chat/stream" in src
    # The iter278 JWT-only endpoint MUST NOT have replaced it.
    assert "/support/chat/stream" not in src


def test_iter279_iter277_widget_route_scope_unchanged():
    """Belt-and-suspenders: confirm the iter277 widget still ONLY
    mounts on the dashboard + admin routes. We don't want iter279 to
    have promoted the iter277 widget globally as a side effect."""
    src = _read_fe("App.js")
    for needle in (
        "/seller/dashboard",
        "/buyer/dashboard",
        "/facility/dashboard",
        "path.startsWith('/admin')",
    ):
        assert needle in src, f"iter277 route gate regressed: {needle}"
    assert "AICoreSupportWidgetWrapper" in src
    # And the legacy AIAssistantWrapper is still mounted as the public
    # site-wide surface.
    assert "<AIAssistantWrapper />" in src
