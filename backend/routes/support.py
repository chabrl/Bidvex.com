"""
iter276 — Support chat endpoint.

Exposes `POST /api/support/chat` and `GET /api/support/health`.

Auth model:
    The route requires a valid JWT (`current_user` dependency). This
    is intentional — the AI Core Assistant is a *post-login* support
    surface, not a public marketing chatbot. Anonymous access would
    invite token-burn from bots and leak the platform-internal P0
    rules baked into the system_instruction.

Session handling:
    The caller may supply an optional `session_id`. When omitted we
    derive one from `current_user.id` so a single user's repeat
    queries always land in the same multi-turn context window —
    without the frontend having to manage session ids manually.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from deps import get_current_user, User
from services.ai_service import (
    AI_MODEL, AI_PROVIDER, AI_TEST_MODE,
    chat_with_assistant,
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
