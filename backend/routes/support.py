"""
iter276 — Support chat endpoint.
iter278 — Streaming variant via SSE.

Exposes:
    GET  /api/support/health   (anonymous)
    POST /api/support/chat     (JWT — single JSON reply)
    POST /api/support/chat/stream  (JWT — Server-Sent Events stream)

Auth model:
    The chat surfaces require a valid JWT (`current_user` dependency).
    Anonymous access would invite token-burn from bots and leak the
    platform-internal P0 rules baked into the system_instruction.

Session handling:
    The caller may supply an optional `session_id`. When omitted we
    derive one from `current_user.id`.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from deps import get_current_user, User
from services.ai_service import (
    AI_MODEL, AI_PROVIDER, AI_TEST_MODE,
    chat_with_assistant, chat_stream_with_assistant,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/support", tags=["Support — AI Core Assistant"])


class SupportChatBody(BaseModel):
    message:    str            = Field(..., min_length=1, max_length=4000)
    session_id: Optional[str]  = Field(default=None, max_length=200)


class SupportChatResponse(BaseModel):
    response:   str
    session_id: str
    model:      str
    test_mode:  bool


@router.get("/health")
async def support_health() -> dict:
    """Lightweight liveness probe for the AI Core Assistant. Returns
    the active model + test-mode flag so ops can confirm config at a
    glance. Anonymous because health checks must not require auth."""
    return {
        "ok":        True,
        "provider":  AI_PROVIDER,
        "model":     AI_MODEL,
        "test_mode": AI_TEST_MODE,
    }


@router.post("/chat", response_model=SupportChatResponse)
async def support_chat(
    body: SupportChatBody,
    current_user: User = Depends(get_current_user),
) -> SupportChatResponse:
    """Send a user message to the BidVex AI Core Platform Assistant
    and return its markdown response. Multi-turn context is preserved
    per-session — by default keyed to the authenticated user's id so
    every follow-up question lands in the same context window."""
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message must be a non-empty string")

    session_id = (body.session_id or "").strip() or f"user:{current_user.id}"

    try:
        reply = await chat_with_assistant(session_id, message)
    except RuntimeError as exc:
        # Service-level failure (LLM down, key missing). Caller gets a
        # clean 502 rather than a 500 so they know to retry vs. report.
        logger.error(f"[support_chat] AI service failure for user={current_user.id}: {exc}")
        raise HTTPException(status_code=502, detail="AI assistant temporarily unavailable")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return SupportChatResponse(
        response=reply,
        session_id=session_id,
        model=AI_MODEL,
        test_mode=AI_TEST_MODE,
    )


__all__ = ["router"]


# ── iter278 — Streaming variant ───────────────────────────────────────


@router.post("/chat/stream")
async def support_chat_stream(
    body: SupportChatBody,
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    """Stream the assistant's reply as Server-Sent Events.

    Wire format (one event per chunk):

        event: chunk
        data: <chunk text JSON-encoded>

        event: done
        data: {"session_id": "...", "model": "...", "test_mode": true|false}

    On any mid-stream failure the service yields a final
    `event: error` frame so the client always sees a terminal event.

    Auth: same JWT requirement as the non-streaming `/chat` route.
    """
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(status_code=400, detail="message must be a non-empty string")

    session_id = (body.session_id or "").strip() or f"user:{current_user.id}"

    async def event_iter():
        # Initial `start` frame so the client can render the typing
        # indicator + clear any prior buffer before the first chunk.
        yield (
            f"event: start\n"
            f"data: {json.dumps({'session_id': session_id, 'model': AI_MODEL})}\n\n"
        )

        had_error = False
        chunk_count = 0
        try:
            async for chunk in chat_stream_with_assistant(session_id, message):
                if chunk.startswith("[STREAM_ERROR]"):
                    had_error = True
                    yield (
                        f"event: error\n"
                        f"data: {json.dumps({'reason': chunk[len('[STREAM_ERROR]'):].strip()})}\n\n"
                    )
                    continue
                chunk_count += 1
                yield (
                    f"event: chunk\n"
                    f"data: {json.dumps({'text': chunk})}\n\n"
                )
        except Exception as exc:  # noqa: BLE001
            # Defensive — the underlying generator promises never to
            # raise but we still wrap so a regression upstream can't
            # crash the response.
            logger.error(f"[support_chat_stream] iterator raised: {exc}")
            had_error = True
            yield (
                f"event: error\n"
                f"data: {json.dumps({'reason': type(exc).__name__})}\n\n"
            )

        # Terminal frame — always emitted, even on partial failure, so
        # the client knows the stream is closed.
        yield (
            f"event: done\n"
            f"data: {json.dumps({'session_id': session_id, 'model': AI_MODEL, 'test_mode': AI_TEST_MODE, 'had_error': had_error, 'chunks': chunk_count})}\n\n"
        )

    return StreamingResponse(
        event_iter(),
        media_type="text/event-stream",
        headers={
            # SSE-specific headers — disable buffering at every layer
            # so chunks reach the browser as soon as they're yielded.
            "Cache-Control":     "no-cache, no-transform",
            "X-Accel-Buffering": "no",       # nginx / k8s ingress
            "Connection":        "keep-alive",
        },
    )
