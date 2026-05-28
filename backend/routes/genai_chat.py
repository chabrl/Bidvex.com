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

logger = logging.getLogger(__name__)

genai_chat_router = APIRouter(tags=["GenAI Direct Chat"])
_admin_security = HTTPBearer(auto_error=False)

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


# ----------------------------------------------------------------------------
# Streaming endpoint — POST /api/chat/stream
# ----------------------------------------------------------------------------
@genai_chat_router.post("/chat/stream")
async def post_chat_stream(body: StreamChatBody) -> StreamingResponse:
    """Stream a Gemini 2.5 Flash response chunk-by-chunk to the client.

    Body:
      message:       user's prompt (required)
      extra_context: optional runtime context appended to system instruction
      google_search: optional toggle (default true) — keeps the GoogleSearch tool on

    Response: text/plain stream, one UTF-8 fragment per chunk.
    """
    return _stream(body)


@genai_chat_router.get("/chat/stream")
async def get_chat_stream(
    message: str = Query(..., min_length=1, max_length=8000),
    extra_context: Optional[str] = Query(None, max_length=4000),
    google_search: bool = Query(True),
) -> StreamingResponse:
    """Same as POST but exposed via GET so it can be consumed by EventSource
    or plain `fetch()`-with-streaming clients that don't support body-on-GET."""
    body = StreamChatBody(
        message=message,
        extra_context=extra_context,
        google_search=google_search,
    )
    return _stream(body)


def _stream(body: StreamChatBody) -> StreamingResponse:
    async def aiter() -> AsyncIterator[bytes]:
        # Bridge the sync google-genai stream → async generator via a queue.
        # This pattern keeps FastAPI's event loop free while the blocking
        # SDK iterator runs on a worker thread.
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_running_loop()
        sentinel = object()

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
            yield item

    return StreamingResponse(
        aiter(),
        media_type="text/plain; charset=utf-8",
        headers={
            "Cache-Control": "no-store, no-transform",
            "X-Accel-Buffering": "no",  # disable proxy buffering for true streaming
            "X-GenAI-Model": GEMINI_MODEL_ID,
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
