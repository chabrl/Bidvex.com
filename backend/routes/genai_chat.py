"""
iter234 — /api/chat/stream FastAPI route exposing the google-genai direct
streaming chat (Gemini 2.5 Flash).

Why a NEW router (alongside the existing /api/ai-chat router that uses the
litellm proxy + EMERGENT_LLM_KEY): the user requested a DIRECT google-genai
SDK path. The two paths run in parallel and never interfere.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

from services.genai_direct_client import GEMINI_MODEL_ID
from services.genai_streaming_chat import stream_chat_chunks
from services.genai_watchdog import run_daily_watchdog_cycle
from routes.chat_history import persist_chat_turn

logger = logging.getLogger(__name__)

genai_chat_router = APIRouter(tags=["GenAI Direct Chat"])
_admin_security = HTTPBearer(auto_error=False)
_stream_security = HTTPBearer(auto_error=False)

# Database handle is injected from server.py during lifespan startup.
_db = None


def set_genai_chat_db(database) -> None:
    global _db
    _db = database


# ----------------------------------------------------------------------------
# Request models
# ----------------------------------------------------------------------------
class StreamChatBody(BaseModel):
    message: str = Field(..., min_length=1, max_length=8000)
    extra_context: Optional[str] = Field(None, max_length=4000)
    google_search: bool = True
    # iter236 Mission 3 — Listing-aware context. When the frontend is on a
    # listing detail page, it passes the listing UUID so the backend can
    # build platform-context (current_viewed_listing + market_comparables)
    # and inject it as a JSON block into the system instruction.
    listing_id: Optional[str] = Field(None, max_length=120)
    # iter239 Mission 4 — Session continuity for persisted history. When set,
    # the (user_id, session_id) pair is up-serted with the new turn; when
    # absent and the request is authenticated, a fresh UUID is allocated.
    session_id: Optional[str] = Field(None, max_length=64)


async def _resolve_user_id(creds: Optional[HTTPAuthorizationCredentials]) -> Optional[str]:
    """Best-effort JWT → user_id resolver. Anonymous requests return None."""
    if not creds or not creds.credentials:
        return None
    try:
        from routes.auth import _decode_jwt  # type: ignore
        payload = _decode_jwt(creds.credentials)
        return payload.get("sub") or payload.get("user_id")
    except Exception:
        return None


# ----------------------------------------------------------------------------
# Streaming endpoint — POST /api/chat/stream
# ----------------------------------------------------------------------------
@genai_chat_router.post("/chat/stream")
async def post_chat_stream(
    body: StreamChatBody,
    creds: HTTPAuthorizationCredentials = Depends(_stream_security),
) -> StreamingResponse:
    """Stream a Gemini 2.5 Flash response chunk-by-chunk to the client.

    Body:
      message:       user's prompt (required)
      extra_context: optional runtime context appended to system instruction
      google_search: optional toggle (default true) — keeps the GoogleSearch tool on
      listing_id:    optional UUID to inject current_viewed_listing + market_comparables
      session_id:    optional chat session UUID; if absent a new session is created

    Response: text/plain stream, one UTF-8 fragment per chunk.
    """
    body = await _enrich_with_listing_context(body)
    user_id = await _resolve_user_id(creds)
    return _stream(body, user_id=user_id)


@genai_chat_router.get("/chat/stream")
async def get_chat_stream(
    message: str = Query(..., min_length=1, max_length=8000),
    extra_context: Optional[str] = Query(None, max_length=4000),
    google_search: bool = Query(True),
    listing_id: Optional[str] = Query(None, max_length=120),
    session_id: Optional[str] = Query(None, max_length=64),
    creds: HTTPAuthorizationCredentials = Depends(_stream_security),
) -> StreamingResponse:
    """Same as POST but exposed via GET so it can be consumed by EventSource
    or plain `fetch()`-with-streaming clients that don't support body-on-GET."""
    body = StreamChatBody(
        message=message,
        extra_context=extra_context,
        google_search=google_search,
        listing_id=listing_id,
        session_id=session_id,
    )
    body = await _enrich_with_listing_context(body)
    user_id = await _resolve_user_id(creds)
    return _stream(body, user_id=user_id)


async def _enrich_with_listing_context(body: StreamChatBody) -> StreamChatBody:
    """iter236 Mission 3 — Fetch listing + comparables and merge into extra_context."""
    if not body.listing_id or _db is None:
        return body
    try:
        from services.chat_listing_context import build_chat_listing_context
        ctx = await build_chat_listing_context(_db, body.listing_id)
        if not ctx.get("current_viewed_listing") and not ctx.get("market_comparables"):
            return body
        import json as _json
        block = (
            "### PLATFORM CONTEXT (do not share raw JSON with user) ###\n"
            f"{_json.dumps(ctx, default=str, indent=2)}"
        )
        merged = (body.extra_context.strip() + "\n\n" + block) if body.extra_context else block
        body = body.model_copy(update={"extra_context": merged})
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[iter236-context] enrichment failed for listing {body.listing_id!r}: {e}")
    return body


def _stream(body: StreamChatBody, *, user_id: Optional[str] = None) -> StreamingResponse:
    async def aiter() -> AsyncIterator[bytes]:
        # Bridge the sync google-genai stream → async generator via a queue.
        # This pattern keeps FastAPI's event loop free while the blocking
        # SDK iterator runs on a worker thread.
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        sentinel = object()
        # iter239 Mission 4 — Accumulate streamed bytes so we can persist
        # the full assistant turn after the iterator drains.
        accumulator: list[bytes] = []

        def _producer() -> None:
            try:
                for chunk in stream_chat_chunks(
                    body.message,
                    extra_system_instruction=body.extra_context,
                    enable_google_search=body.google_search,
                ):
                    asyncio.run_coroutine_threadsafe(queue.put(chunk), loop)
            except Exception as e:  # noqa: BLE001
                logger.error(f"[GenAI Direct][/chat/stream] producer error: {e}", exc_info=True)
                err_blob = f"\n\n[stream-error] {type(e).__name__}: {e}".encode("utf-8")
                asyncio.run_coroutine_threadsafe(queue.put(err_blob), loop)
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(sentinel), loop)

        # Kick off the producer in a worker thread.
        loop.run_in_executor(None, _producer)

        while True:
            item = await queue.get()
            if item is sentinel:
                break
            accumulator.append(item)
            yield item

        # iter239 Mission 4 — Persist the turn for authenticated users.
        if user_id:
            try:
                assistant_text = b"".join(accumulator).decode("utf-8", errors="ignore").strip()
                # Skip the iter236 silent priming probe ("The user is currently viewing listing ID …").
                is_priming = body.message.startswith("The user is currently viewing listing ID")
                if assistant_text and not is_priming:
                    await persist_chat_turn(
                        user_id=user_id,
                        session_id=body.session_id,
                        listing_id=body.listing_id,
                        user_message=body.message,
                        assistant_message=assistant_text,
                    )
            except Exception as e:  # noqa: BLE001
                logger.warning(f"[iter239-mission4] persist_chat_turn failed: {e}")

    return StreamingResponse(
        aiter(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-store, no-transform",
            "X-Accel-Buffering": "no",  # disable proxy buffering for true streaming
            "X-GenAI-Model": GEMINI_MODEL_ID,
            # iter239 — Surface the session_id (if explicitly set) so the FE
            # can persist it client-side without an extra round-trip.
            **({"X-Chat-Session-Id": body.session_id} if body.session_id else {}),
        },
    )


# ----------------------------------------------------------------------------
# Diagnostics endpoint — quick health check for the GEMINI_API_KEY wiring.
# ----------------------------------------------------------------------------
@genai_chat_router.get("/chat/diagnostics")
async def chat_diagnostics() -> Dict[str, Any]:
    import os as _os
    key = _os.environ.get("GEMINI_API_KEY", "")
    return {
        "model": GEMINI_MODEL_ID,
        "gemini_api_key_present": bool(key),
        "gemini_api_key_preview": (f"***{key[-6:]}" if key else None),
        "google_search_tool_enabled": True,
        "thinking_budget": -1,
    }


# ----------------------------------------------------------------------------
# On-demand admin trigger of the daily watchdog (mainly for the testing agent).
# ----------------------------------------------------------------------------
@genai_chat_router.post("/chat/watchdog/run-now")
async def run_watchdog_now(
    credentials: HTTPAuthorizationCredentials = Depends(_admin_security),
) -> Dict[str, Any]:
    # iter234 — admin-only trigger (was unauthenticated; flagged by testing agent
    # as a cost/spam vector since each call hits Gemini + sends an email).
    from routes.admin import require_admin
    await require_admin(credentials)

    if _db is None:
        raise HTTPException(status_code=503, detail="genai-chat db handle not initialised")
    started = datetime.now(timezone.utc)
    result = await run_daily_watchdog_cycle(_db)
    return {
        "triggered_at": started.isoformat(),
        "result": result,
    }


__all__ = ["genai_chat_router", "set_genai_chat_db"]
