"""
iter234 — Direct google-genai SDK client for Gemini 2.5 Flash.

Parallel to (and intentionally independent from) services/ai_assistant_v2.py
which uses the litellm + EMERGENT_LLM_KEY proxy path. This module talks
directly to Google's Gemini Developer API using the official `google-genai`
SDK (v2.6.0) authenticated via the user's own GEMINI_API_KEY.

Used by:
  • services.genai_streaming_chat — /api/chat/stream FastAPI route
  • services.genai_watchdog       — 24h cron log scanner

Spec lock-in (do not change without explicit user sign-off):
  • Model               : gemini-2.5-flash
  • thinking_budget     : -1   (dynamic thinking)
  • Tools               : Google Search grounding enabled
  • System instruction  : WATCHDOG_SYSTEM_INSTRUCTION below (EN/FR canonical)
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from google import genai
from google.genai import types as genai_types

logger = logging.getLogger(__name__)

GEMINI_MODEL_ID = "gemini-2.5-flash"

# ----- System instruction (canonical, resolved at runtime) -----
# iter497 — The BidVex Gemini system instruction is no longer hard-coded
# in this module. It lives in MongoDB (``db.ai_config``) so admins can
# edit it live via ``PUT /api/admin/ai-config/system-instruction``. On
# cold cache the sync accessor falls back to the on-disk seed file
# (/app/memory/BIDVEX_AI_SYSTEM_INSTRUCTION_SEED.md) — see
# ``services.ai_config_service`` for the full contract.
#
# The ``WATCHDOG_SYSTEM_INSTRUCTION`` name is preserved for backward
# compatibility with iter234+ tests that import it directly. It is
# resolved at module load time from the sync cache (or seed file), so
# process boot always has a non-empty value. Runtime callers with async
# DB access should prefer ``ai_config_service.get_system_instruction(db)``
# so live admin edits propagate within the cache TTL.
from services.ai_config_service import get_system_instruction_sync as _get_sys_instruction_sync

WATCHDOG_SYSTEM_INSTRUCTION: str = _get_sys_instruction_sync()


# Lazy singleton client (constructed on first use, re-created if key rotates)
_client_singleton: Optional[genai.Client] = None
_client_key_fingerprint: Optional[str] = None


def _resolve_api_key() -> str:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY environment variable is not set. Direct google-genai "
            "integration requires the user's own Gemini Developer API key."
        )
    return key


def get_genai_client() -> genai.Client:
    """Return a process-wide google-genai Client. Reconstructs if the key
    fingerprint changes (e.g. live env reload)."""
    global _client_singleton, _client_key_fingerprint
    key = _resolve_api_key()
    fp = key[-6:]  # last 6 chars only — never log full key
    if _client_singleton is None or _client_key_fingerprint != fp:
        _client_singleton = genai.Client(api_key=key)
        _client_key_fingerprint = fp
        logger.info(f"[GenAI Direct] Constructed Gemini client | key=***{fp} | model={GEMINI_MODEL_ID}")
    return _client_singleton


def build_generation_config(
    *,
    extra_system_instruction: Optional[str] = None,
    enable_google_search: bool = True,
) -> genai_types.GenerateContentConfig:
    """Build the canonical GenerateContentConfig used by every direct call.

    Locked invariants:
      • system_instruction = live value from ``db.ai_config`` (via the
        sync cache in ``services.ai_config_service``) with the on-disk
        seed file as fallback (+ optional extra block appended)
      • thinking_config    = ThinkingConfig(thinking_budget=-1)  (dynamic)
      • tools              = [Tool(google_search=GoogleSearch())] when enabled

    Callers that hold an async ``db`` handle SHOULD pre-warm the cache via
    ``await ai_config_service.get_system_instruction(db)`` before invoking
    this builder so live admin edits propagate immediately. Otherwise the
    cache TTL (5 min) governs propagation.
    """
    # Read from the sync cache on every call — this reflects the freshest
    # value that any async pre-warm or admin-edit has written. Never
    # captures the constant snapshotted at import time.
    system_text = _get_sys_instruction_sync()
    if extra_system_instruction:
        system_text = f"{system_text}\n\n# Additional Runtime Context\n{extra_system_instruction.strip()}"

    tools = []
    if enable_google_search:
        tools.append(genai_types.Tool(google_search=genai_types.GoogleSearch()))

    return genai_types.GenerateContentConfig(
        system_instruction=system_text,
        thinking_config=genai_types.ThinkingConfig(thinking_budget=-1),
        tools=tools or None,
        response_modalities=["TEXT"],
    )


__all__ = [
    "GEMINI_MODEL_ID",
    "WATCHDOG_SYSTEM_INSTRUCTION",
    "get_genai_client",
    "build_generation_config",
]
