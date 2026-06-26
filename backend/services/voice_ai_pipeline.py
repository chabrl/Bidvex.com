"""
iter316 Mission 2 — AI Voice Intelligence pipeline.

Async post-call processing of dialer recordings. Runs as a FastAPI
BackgroundTask launched from /api/twilio/recording-callback once the
MP3 is confirmed locally saved. Never blocks the call flow — if AI
processing fails completely the recording, call_log, and dialer remain
fully functional.

Pipeline steps (in order):
  1. Mark call_log.ai_processing_status = "processing"
  2. Upload the local MP3 to Gemini, request:
       • Diarized transcript (Agent vs Client labels) in original language
       • English transcript (translate if original was FR)
       • French transcript (translate if original was EN)
       • Sentiment score (-1.0 to 1.0) + label
       • 2-4 sentence call summary
       • Bulleted action items list
  3. On success: persist all fields, mark "completed"
  4. On failure: mark "failed", log error, attempt ONE retry, then stop

Reuses:
  • services.genai_direct_client.get_genai_client (iter234 confirmed working)
  • GEMINI_MODEL_ID = "gemini-2.5-flash" (locked, do not change)
"""
from __future__ import annotations

import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from google.genai import types as genai_types

from services.genai_direct_client import get_genai_client, GEMINI_MODEL_ID

logger = logging.getLogger(__name__)

# Lightweight per-process concurrency cap — Gemini rate-limits hard at
# the free tier (~15 rpm). We process one recording at a time per worker.
import asyncio
_AI_PIPELINE_LOCK = asyncio.Lock()

VOICE_AI_PROMPT = """\
You are a bilingual EN/FR call-analysis engine for BidVex (a Canadian
auction marketplace). The user is uploading an audio recording of a
business call between a BidVex Agent (or Contractor) and a Client.

Return EXACTLY one JSON object with this schema, NO markdown fences,
NO commentary:

{
  "original_language": "en" | "fr" | "mixed",
  "transcript_speakers": [
    {"speaker": "Agent" | "Client", "start_ms": int, "end_ms": int, "text": "..."},
    ...
  ],
  "transcript_en": "Full English transcript, single string with line breaks per speaker turn",
  "transcript_fr": "Full French transcript, same format",
  "sentiment_score": float in [-1.0, 1.0],     // -1 = very negative client, +1 = very positive
  "sentiment_label": "positive" | "neutral" | "negative",
  "call_summary": "2-4 sentence neutral summary of what was discussed.",
  "action_items": ["First concrete next step", "Second item", ...]
}

Strictly observe:
  • Speaker diarization: label one party "Agent" (BidVex side) and the
    other "Client". If unclear, the louder/longer-talking party that
    sounds more sales-driven is the Agent.
  • If the original language is EN, translate to FR for `transcript_fr`
    (and vice versa). If the call is mixed, keep each utterance in its
    original language in `transcript_speakers` but produce clean fully-EN
    and fully-FR versions in the transcript fields.
  • Sentiment is the CLIENT's overall sentiment toward BidVex.
  • Action items are concrete, second-person ("Send the pricing sheet",
    "Follow up next Tuesday"). 0-8 items.
  • If audio is silence or undecipherable, still return the JSON but
    with empty transcripts, sentiment_score=0, sentiment_label="neutral",
    call_summary="Audio could not be analyzed (silence or unintelligible).",
    action_items=[].
"""


# ─── Public entry-point ─────────────────────────────────────────────────

async def process_call_recording_async(call_log_id: str,
                                       audio_path: str,
                                       db) -> None:
    """Top-level pipeline. Wraps the Gemini call + retry logic + DB writes
    in a single asyncio task. Callers should fire-and-forget this via
    BackgroundTasks; do not await it from inside the recording callback."""
    async with _AI_PIPELINE_LOCK:  # per-worker serialisation
        await _process_one(call_log_id, audio_path, db, attempt=1)


async def _process_one(call_log_id: str, audio_path: str, db, attempt: int) -> None:
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.call_logs.update_one(
        {"_id": call_log_id},
        {"$set": {"ai_processing_status": "processing",
                  "ai_processing_attempt": attempt,
                  "updated_at": now_iso}},
    )
    try:
        result = await _call_gemini_on_audio(audio_path)
        validated = _validate_result(result)
        patch = {
            "ai_processing_status":    "completed",
            "ai_processed_at":         datetime.now(timezone.utc).isoformat(),
            "transcript_speakers":     validated.get("transcript_speakers"),
            "transcript_en":           validated.get("transcript_en"),
            "transcript_fr":           validated.get("transcript_fr"),
            "sentiment_score":         validated.get("sentiment_score"),
            "sentiment_label":         validated.get("sentiment_label"),
            "call_summary":            validated.get("call_summary"),
            "action_items":            validated.get("action_items"),
            "updated_at":              datetime.now(timezone.utc).isoformat(),
        }
        await db.call_logs.update_one({"_id": call_log_id}, {"$set": patch})
        logger.info(f"[voice_ai] call={call_log_id} status=completed "
                    f"sentiment={validated.get('sentiment_label')} "
                    f"actions={len(validated.get('action_items') or [])}")
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[voice_ai] call={call_log_id} attempt={attempt} failed: {e}")
        if attempt < 2:
            # One retry, no infinite loop.
            await _process_one(call_log_id, audio_path, db, attempt=attempt + 1)
            return
        await db.call_logs.update_one(
            {"_id": call_log_id},
            {"$set": {
                "ai_processing_status":  "failed",
                "ai_processing_error":   str(e)[:500],
                "ai_processed_at":       datetime.now(timezone.utc).isoformat(),
                "updated_at":            datetime.now(timezone.utc).isoformat(),
            }},
        )


# ─── Gemini call ────────────────────────────────────────────────────────

async def _call_gemini_on_audio(audio_path: str) -> Dict[str, Any]:
    """Sends the MP3 to Gemini-2.5-Flash inline (file < 20MB) or uploaded
    via the Files API (>= 20MB). Returns the parsed JSON object."""
    p = Path(audio_path)
    if not p.exists():
        raise FileNotFoundError(f"recording missing: {audio_path}")
    client = get_genai_client()
    size = p.stat().st_size
    # Use Files API for anything > 18MB (well under Gemini's 20MB inline cap).
    if size > 18 * 1024 * 1024:
        f = await asyncio.to_thread(client.files.upload, file=str(p))
        audio_part = f
    else:
        data = p.read_bytes()
        audio_part = genai_types.Part.from_bytes(data=data, mime_type="audio/mpeg")

    cfg = genai_types.GenerateContentConfig(
        response_modalities=["TEXT"],
        # We want strict JSON — keep the response stable.
        temperature=0.2,
    )
    response = await asyncio.to_thread(
        client.models.generate_content,
        model=GEMINI_MODEL_ID,
        contents=[VOICE_AI_PROMPT, audio_part],
        config=cfg,
    )
    text = (response.text or "").strip()
    # Strip any accidental ```json``` fencing.
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.IGNORECASE | re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        # Last-ditch: extract the largest {...} block.
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            return json.loads(m.group(0))
        raise ValueError(f"Gemini returned unparseable JSON: {text[:240]}") from e


# ─── Validation ─────────────────────────────────────────────────────────

def _validate_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce/clamp the Gemini output into the schema expected by call_logs."""
    if not isinstance(result, dict):
        raise ValueError("Gemini result not a dict")

    speakers = result.get("transcript_speakers") or []
    if not isinstance(speakers, list):
        speakers = []
    # Trim to dicts with the right keys.
    speakers = [
        {
            "speaker":  str(s.get("speaker") or "Unknown")[:32],
            "start_ms": int(s.get("start_ms") or 0),
            "end_ms":   int(s.get("end_ms") or 0),
            "text":     str(s.get("text") or "")[:4000],
        }
        for s in speakers if isinstance(s, dict)
    ]

    score = float(result.get("sentiment_score") or 0.0)
    score = max(-1.0, min(1.0, score))
    label = result.get("sentiment_label") or "neutral"
    if label not in {"positive", "neutral", "negative"}:
        label = "neutral"

    actions = result.get("action_items") or []
    if not isinstance(actions, list):
        actions = []
    actions = [str(a)[:200] for a in actions if a][:8]

    return {
        "transcript_speakers": speakers,
        "transcript_en":       str(result.get("transcript_en") or "")[:50000] or None,
        "transcript_fr":       str(result.get("transcript_fr") or "")[:50000] or None,
        "sentiment_score":     round(score, 3),
        "sentiment_label":     label,
        "call_summary":        str(result.get("call_summary") or "")[:2000] or None,
        "action_items":        actions,
    }


__all__ = ["process_call_recording_async"]
