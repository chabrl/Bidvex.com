"""
iter234 — Streaming chat service backed by google-genai (Gemini 2.5 Flash).

Exposes a synchronous generator `stream_chat_chunks()` that wraps
`client.models.generate_content_stream()` for use with FastAPI's
`StreamingResponse`. Per the integration playbook (iter234), synchronous
streaming endpoints are the simplest + safest path; FastAPI runs them in a
thread-pool so the event loop is never blocked.
"""
from __future__ import annotations

import logging
from typing import Iterator, Optional

from services.genai_direct_client import (
    GEMINI_MODEL_ID,
    build_generation_config,
    get_genai_client,
)

logger = logging.getLogger(__name__)


def stream_chat_chunks(
    prompt: str,
    *,
    extra_system_instruction: Optional[str] = None,
    enable_google_search: bool = True,
) -> Iterator[bytes]:
    """Stream the model's response chunk-by-chunk as UTF-8 bytes.

    Each yielded chunk is the raw text fragment from the latest stream
    event. Caller is expected to wrap this generator in a `StreamingResponse`
    or directly forward to a websocket / SSE channel.
    """
    if not prompt or not prompt.strip():
        yield b"(empty prompt)"
        return

    client = get_genai_client()
    config = build_generation_config(
        extra_system_instruction=extra_system_instruction,
        enable_google_search=enable_google_search,
    )

    try:
        stream = client.models.generate_content_stream(
            model=GEMINI_MODEL_ID,
            contents=prompt,
            config=config,
        )
        emitted_any = False
        for chunk in stream:
            text = getattr(chunk, "text", None) or ""
            if text:
                emitted_any = True
                yield text.encode("utf-8")
        if not emitted_any:
            logger.warning("[GenAI Direct][Stream] No text chunks emitted for prompt of length %d", len(prompt))
            yield b""
    except Exception as e:  # noqa: BLE001
        logger.error(f"[GenAI Direct][Stream] error during streaming: {e}", exc_info=True)
        # Surface a controlled, human-readable trailer instead of leaking a 500.
        yield f"\n\n[stream-error] {type(e).__name__}: {e}".encode("utf-8")


__all__ = ["stream_chat_chunks"]
