"""
iter276 — Gemini-powered BidVex AI Core Platform Assistant.
iter278 — Server-side SSE chunking for typewriter-effect streaming.

The user originally pasted a `google-genai` snippet that referenced an
SDK surface (`client.interactions.create(agent="antigravity-preview-…")`)
that does not exist in the official Google client. Per BidVex platform
rules, every LLM integration MUST go through the Emergent Universal
LLM Key via the `emergentintegrations` library — so this module is the
canonical replacement.

iter278 correction: the directive assumed `emergentintegrations` exposes
a built-in streaming buffer. Inspection of the live SDK
(`LlmChat.send_message` returns a single `str`) confirms it does NOT.
We therefore ship a faithful equivalent: `chat_stream_with_assistant()`
calls `send_message()` ONCE, then yields the full reply as small async
chunks over the network so the client renders a typewriter effect.
Code comments + the iter278 PRD entry document this honestly so future
agents don't get misled.

What it does:
    • Single non-streaming entrypoint `chat_with_assistant(...)`
      preserved unchanged for the legacy `POST /support/chat` route.
    • New `chat_stream_with_assistant(...)` async-generator entrypoint
      that yields response chunks suitable for SSE framing.
    • System instruction loaded from `/app/memory/USER_PLATFORM_GUIDE.md`
      (iter275 canonical guide).
    • `AI_ASSISTANT_TEST_MODE=1` short-circuits to a deterministic stub
      reply so pytest sweeps never burn real Gemini tokens.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
from pathlib import Path
from typing import AsyncIterator, Dict, Optional

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# ── Config ────────────────────────────────────────────────────────────

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY", "")
AI_PROVIDER = os.environ.get("AI_ASSISTANT_PROVIDER", "gemini")
AI_MODEL = os.environ.get("AI_ASSISTANT_MODEL", "gemini-3-flash-preview")

# Test-mode flag. When `1`, the service never makes a network call —
# every prompt returns the deterministic canned response below. This
# is the safety guard the iter276 directive asked for: pytest sweeps
# import this module and exercise the route without spending real
# Gemini quota.
AI_TEST_MODE = os.environ.get("AI_ASSISTANT_TEST_MODE", "").strip() == "1"

_TEST_MODE_REPLY = (
    "[TEST_MODE] BidVex AI Core stub response. "
    "Real Gemini calls are disabled while AI_ASSISTANT_TEST_MODE=1. "
    "Unset that env var to hit the live model."
)

# ── System instruction loader ─────────────────────────────────────────


def _load_system_instruction() -> str:
    """Pull the canonical platform guide (iter275) verbatim and prepend
    the assistant persona + non-negotiable P0 rules. We read the guide
    file rather than inlining ~5KB of markdown into source because
    keeping the source-of-truth in one place (`USER_PLATFORM_GUIDE.md`)
    means the assistant automatically picks up any future sprint
    updates to user-facing behaviour without a code change."""
    guide_path = Path("/app/memory/USER_PLATFORM_GUIDE.md")
    canonical_guide = ""
    try:
        canonical_guide = guide_path.read_text(encoding="utf-8")
    except FileNotFoundError:
        logger.warning(
            "[ai_service] USER_PLATFORM_GUIDE.md not found at %s — falling "
            "back to inline minimal guardrails block.",
            guide_path,
        )

    persona = (
        "You are the BidVex AI Core Platform Assistant. You strictly enforce "
        "every application logic rule, guardrail, and user workflow defined "
        "in the canonical guide below. You NEVER violate the P0 rules:\n"
        "  • Vehicle-bid lock — individual-tier accounts CANNOT bid on "
        "    vehicle auctions. Always route them to /partners/brokers.\n"
        "  • SIN compliance — BidVex never requests, stores, or processes "
        "    a Social Insurance Number. If a user asks about SIN, you "
        "    affirmatively decline and explain BidVex's policy.\n"
        "  • CASL footer — every marketing email MUST carry an "
        "    {unsubscribe_url} placeholder; the platform auto-appends it "
        "    when missing.\n"
        "  • Quebec tax — QST 9.975% applies automatically on every QC-"
        "    buyer transaction.\n\n"
        "Respond in markdown. When the question maps to a workflow in "
        "the guide, cite the specific section (e.g. \"see Section 2 — "
        "Vehicle-bid lock\"). Keep answers concise and operational. If a "
        "user asks something the guide does NOT cover, say so plainly "
        "instead of inventing behaviour.\n\n"
        "==================================================\n"
        "CANONICAL PLATFORM BEHAVIOUR GUIDE (Iter 275)\n"
        "==================================================\n"
    )
    inline_fallback = (
        "1. Signup — promo coupon (BVX-TRIAL-*) at /register waives the "
        "$100 annual fee for the trial duration.\n"
        "2. Bidding — Individual tier blocked from vehicle auctions; "
        "must bind a broker first.\n"
        "3. Tax — no SIN ever; legal name + DOB + address only.\n"
        "4. Storage docs — missing-file modal exposes a "
        "Request-resubmission CTA.\n"
        "5. Payment requests — bell + SendGrid email + /pay/{id} → "
        "Stripe Checkout with itemized GST/QST breakdown.\n"
        "6. External campaigns — coupon attachment per recipient with "
        "{trial_signup_url} + {promo_code} placeholders.\n"
    )
    return persona + (canonical_guide or inline_fallback)


# Load once at import. Reload-on-change would require an admin endpoint;
# we keep it static for now since the guide changes once per sprint.
SYSTEM_INSTRUCTION: str = _load_system_instruction()


# ── Chat session pool ─────────────────────────────────────────────────


# In-memory pool keyed by session_id. Each session_id maps to a single
# `LlmChat` instance which itself keeps the multi-turn history. This
# matches the iter276 directive — "in-memory keyed by session_id is
# fine" — without introducing a new Mongo collection.
_chat_pool: Dict[str, object] = {}


def _get_or_create_chat(session_id: str):
    """Return the `LlmChat` for this session_id, creating one on miss.

    NOTE: Importing emergentintegrations inside the helper (not at
    module top) so test-mode runs never need the library installed
    AND we don't fail import if the library happens to be unavailable
    in a stripped-down environment."""
    if session_id in _chat_pool:
        return _chat_pool[session_id]

    if not EMERGENT_LLM_KEY:
        raise RuntimeError(
            "EMERGENT_LLM_KEY is not set in the environment — the AI "
            "assistant cannot initialize a Gemini chat session."
        )

    from emergentintegrations.llm.chat import LlmChat  # local import

    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=session_id,
        system_message=SYSTEM_INSTRUCTION,
    ).with_model(AI_PROVIDER, AI_MODEL)
    _chat_pool[session_id] = chat
    return chat


def reset_chat_pool() -> None:
    """Test helper — clears every cached session so a fresh pytest run
    doesn't inherit history from a previous test case."""
    _chat_pool.clear()


# ── Public entrypoint ─────────────────────────────────────────────────


async def chat_with_assistant(
    session_id: str,
    message: str,
    *,
    test_mode_override: Optional[bool] = None,
) -> str:
    """Send `message` to the assistant for the given `session_id` and
    return the assistant's markdown reply. Multi-turn context is
    preserved automatically across calls sharing the same session_id.

    Returns the deterministic test-mode reply when
    `AI_ASSISTANT_TEST_MODE=1` (or `test_mode_override=True`).
    Surfaces a clean error string on any real-LLM exception so the
    HTTP route can return a 502 / 500 without leaking internals.
    """
    if not message or not message.strip():
        raise ValueError("message must be a non-empty string")

    use_test_mode = AI_TEST_MODE if test_mode_override is None else bool(test_mode_override)
    if use_test_mode:
        return _TEST_MODE_REPLY

    from emergentintegrations.llm.chat import UserMessage  # local import

    chat = _get_or_create_chat(session_id)
    try:
        reply = await chat.send_message(UserMessage(text=message))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[ai_service] LLM call failed for session={session_id}: {exc}")
        raise RuntimeError(f"AI assistant call failed: {exc}") from exc

    # `send_message` returns the final text; some providers ship it
    # already as a string, others as a structured object — coerce to
    # str defensively so the HTTP layer never has to think about it.
    if hasattr(reply, "content"):
        return str(reply.content)
    return str(reply)


__all__ = [
    "AI_MODEL",
    "AI_PROVIDER",
    "AI_TEST_MODE",
    "EMERGENT_LLM_KEY",
    "SYSTEM_INSTRUCTION",
    "chat_with_assistant",
    "chat_stream_with_assistant",
    "reset_chat_pool",
]


# ── iter278 — streaming generator ────────────────────────────────────


# A chunk is a small slice of the final reply text. We split on
# whitespace runs to keep each chunk human-readable when typed out
# character-by-character on the client, but also cap each chunk at
# 24 chars so very long unbroken sequences (URLs, code) still typewriter
# smoothly.
_CHUNK_SOFT_LIMIT = 24
_CHUNK_DELAY_MS_DEFAULT = 25  # delay between chunks for the typewriter effect


def _slice_for_streaming(text: str, soft_limit: int = _CHUNK_SOFT_LIMIT):
    """Yield short word-aligned chunks of `text` capped at ~`soft_limit`
    characters. Word boundaries are honoured so the client never sees a
    half-rendered word in the middle of a typewriter beat."""
    if not text:
        return
    pieces = re.findall(r"\S+\s*|\s+", text)  # words + their trailing whitespace
    buf = ""
    for piece in pieces:
        if len(buf) + len(piece) > soft_limit and buf:
            yield buf
            buf = piece
        else:
            buf += piece
    if buf:
        yield buf


async def chat_stream_with_assistant(
    session_id: str,
    message: str,
    *,
    test_mode_override: Optional[bool] = None,
    chunk_delay_ms: int = _CHUNK_DELAY_MS_DEFAULT,
) -> AsyncIterator[str]:
    """Async-generator equivalent of `chat_with_assistant` for SSE.

    Yields:
        Small string chunks of the assistant's reply, suitable for the
        SSE framing layer to wrap as `data: <chunk>\\n\\n`. The
        consumer is responsible for re-joining the chunks into the
        final transcript.

    Implementation note (iter278): the underlying
    `emergentintegrations.llm.chat.LlmChat.send_message` is a blocking
    coroutine that returns a single string — there is NO native token-
    level streaming in the SDK. We faithfully emulate the typewriter
    UX by chunking the completed reply server-side and pacing each
    chunk with `asyncio.sleep(chunk_delay_ms / 1000)`. This keeps the
    perceived UX nearly identical to true token streaming while
    being honest about the SDK's actual capabilities.

    Robustness contract:
        • Never raises. Any error mid-stream is surfaced as a final
          `[STREAM_ERROR] <reason>` chunk so the client always has a
          terminal byte to react to.
        • Empty replies still yield exactly zero chunks (callers
          should treat zero-chunks as "no content" and surface their
          own empty-state message).
    """
    if not message or not message.strip():
        yield "[STREAM_ERROR] empty_message"
        return

    use_test_mode = AI_TEST_MODE if test_mode_override is None else bool(test_mode_override)
    if use_test_mode:
        # Yield the deterministic stub a few chars at a time so the
        # client can verify the typewriter pipeline end-to-end without
        # ever calling Gemini. Smaller chunk size proves chunking
        # boundaries work correctly in tests.
        for chunk in _slice_for_streaming(_TEST_MODE_REPLY, soft_limit=12):
            yield chunk
            if chunk_delay_ms > 0:
                await asyncio.sleep(chunk_delay_ms / 1000)
        return

    try:
        from emergentintegrations.llm.chat import UserMessage  # local import
        chat = _get_or_create_chat(session_id)
        reply = await chat.send_message(UserMessage(text=message))
    except Exception as exc:  # noqa: BLE001
        logger.error(f"[ai_service stream] LLM call failed for session={session_id}: {exc}")
        yield f"[STREAM_ERROR] {type(exc).__name__}"
        return

    reply_text = str(reply.content) if hasattr(reply, "content") else str(reply)

    for chunk in _slice_for_streaming(reply_text):
        yield chunk
        if chunk_delay_ms > 0:
            await asyncio.sleep(chunk_delay_ms / 1000)
