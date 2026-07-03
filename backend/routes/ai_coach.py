"""
iter335 — Outbound Contractor AI Coach (silent Gemini eavesdrop).

Completely separate from iter334 (inbound press-9 AI assistant). Runs only
on OUTBOUND contractor→client calls placed via the Admin Dialer.

Pipeline (verified live against Google):
    Twilio outbound call
        ↓ <Start><Stream> (non-terminal — call proceeds to <Dial>)
    WS /api/twilio/coach-stream?token=<nonce>
        ↓ audioop µ-law/8k → PCM16/16k
    Gemini Live (native-audio-latest) session
        with input_audio_transcription + output_audio_transcription
        → returns text transcripts of the caller's audio.
        ↓ every ~7 seconds, accumulated transcript fed into
    Regular Gemini 2.5 Flash (generate_content) with
        response_mime_type="application/json" + JSON schema
        → returns strict coaching hint object.
        ↓ pushed via
    WS /api/ws/contractor-coaching/{call_log_id}
        → contractor's browser dashboard.

Gemini's audio output is DISCARDED. The client and contractor never hear
the AI. Only the JSON coaching hints reach the contractor's dashboard.

Storage in Mongo `ai_voice_calls` collection (shared with iter334, keyed
on `call_type` discriminator):
  call_type = "outbound_coach"     — rows created here.
  call_type = "inbound_press9"     — rows created by iter334 (untouched).
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from fastapi import (
    APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect,
)
from pydantic import BaseModel

from deps import get_current_user, get_db, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Coach — iter335"])

# ─── Configuration ────────────────────────────────────────────────────

# Live API model — must support input_audio_transcription (native audio).
STT_MODEL_DEFAULT = "gemini-2.5-flash-native-audio-latest"

# Analysis model — regular chat with strict JSON schema.
ANALYSIS_MODEL_DEFAULT = "gemini-2.5-flash"

NONCE_TTL_SECONDS = 120           # 2 min from call-init to WS open.
ANALYSIS_INTERVAL_SECONDS = 7.0   # push a hint every ~7 s.
MIN_TRANSCRIPT_CHARS = 12         # skip if transcript too short.
HARD_CALL_LIMIT_SECONDS = 10 * 60
CALL_WARNING_AT_SECONDS = 9 * 60


SYSTEM_PROMPT_COACH = """You are a silent real-time call coach for a BidVex contractor. You are analyzing the last few seconds of a live sales call between the BidVex contractor and a potential client. Neither party hears you — you produce JSON coaching hints for the contractor's dashboard ONLY.

Output ONLY a single valid JSON object matching this exact structure:
{
  "sentiment": "positive" | "neutral" | "negative" | "resistant" | "interested",
  "client_sentiment_score": <number between -1.0 and 1.0>,
  "tone_alert": null | "getting_impatient" | "confused" | "warming_up" | "about_to_disengage",
  "coaching_hint": "<short actionable tip for the contractor, 1 sentence>",
  "compliance_flag": null | "bill_96_required" | "broker_rule_applicable" | "prohibited_claim_detected",
  "suggested_next_line": "<optional suggested thing contractor could say next>" | null,
  "language_detected": "en" | "fr" | "mixed"
}

Rules:
- If the client expresses interest in registering or pricing: tone_alert="warming_up" and provide a registration-focused coaching_hint.
- If the client is about to hang up or disengage: tone_alert="about_to_disengage" and provide a retention-focused coaching_hint.
- If you detect a compliance risk (broker vehicle rules in restricted provinces, Bill 96 French language requirements, prohibited claims): set compliance_flag immediately.
- Answer in the dominant conversation language.
- Do NOT wrap the JSON in markdown fences. Do NOT include prose. Only the JSON object."""


# ─── Nonce store (in-memory) ──────────────────────────────────────────

_COACH_NONCES: Dict[str, Dict[str, Any]] = {}


def _issue_coach_nonce(call_log_id: str, contractor_id: str, client_phone: str) -> str:
    tok = secrets.token_urlsafe(32)
    _COACH_NONCES[tok] = {
        "call_log_id": call_log_id,
        "contractor_id": contractor_id,
        "client_phone": client_phone,
        "expires_at": time.time() + NONCE_TTL_SECONDS,
        "used": False,
    }
    _gc_coach_nonces()
    return tok


def _consume_coach_nonce(tok: str) -> Optional[Dict[str, Any]]:
    row = _COACH_NONCES.get(tok)
    if not row:
        return None
    if row["used"] or row["expires_at"] < time.time():
        return None
    row["used"] = True
    return row


def _peek_coach_nonce(tok: str) -> Optional[Dict[str, Any]]:
    """Non-consuming lookup — for testing and status introspection."""
    row = _COACH_NONCES.get(tok)
    if not row:
        return None
    if row["expires_at"] < time.time():
        return None
    return row


def _gc_coach_nonces() -> None:
    now = time.time()
    for k in [k for k, v in _COACH_NONCES.items() if v["expires_at"] < now]:
        _COACH_NONCES.pop(k, None)


# ─── Coaching subscribers (dashboard WS) ──────────────────────────────
# Keyed by call_log_id → set of WebSocket objects (allow multi-tab).

_COACH_SUBSCRIBERS: Dict[str, Set[WebSocket]] = {}


async def _broadcast_to_dashboard(call_log_id: str, payload: Dict[str, Any]) -> None:
    subs = list(_COACH_SUBSCRIBERS.get(call_log_id, set()))
    dead: List[WebSocket] = []
    for ws in subs:
        try:
            await ws.send_json(payload)
        except Exception:  # noqa: BLE001
            dead.append(ws)
    if dead:
        for w in dead:
            _COACH_SUBSCRIBERS.get(call_log_id, set()).discard(w)


# ─── Helpers ──────────────────────────────────────────────────────────

def _get_db():
    from server import db
    return db


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


HINT_SCHEMA_KEYS = {
    "sentiment", "client_sentiment_score", "tone_alert",
    "coaching_hint", "compliance_flag", "suggested_next_line", "language_detected",
}
ALLOWED_SENTIMENT = {"positive", "neutral", "negative", "resistant", "interested"}
ALLOWED_TONE = {None, "getting_impatient", "confused", "warming_up", "about_to_disengage"}
ALLOWED_COMPLIANCE = {None, "bill_96_required", "broker_rule_applicable", "prohibited_claim_detected"}
ALLOWED_LANG = {"en", "fr", "mixed"}


def extract_and_validate_hint(raw_text: str) -> Optional[Dict[str, Any]]:
    """Robustly extract JSON from Gemini's output (playbook warned about
    markdown fences and prose leakage) and validate the schema. Returns
    None if the JSON is malformed OR fails schema constraints."""
    if not raw_text:
        return None
    txt = re.sub(r"```(?:json)?", "", raw_text).strip("` \n\t")
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group())
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(obj, dict):
        return None
    # Fill any missing key with None so downstream can rely on shape.
    for k in HINT_SCHEMA_KEYS:
        obj.setdefault(k, None)
    if obj.get("sentiment") not in ALLOWED_SENTIMENT:
        return None
    if obj.get("tone_alert") not in ALLOWED_TONE:
        obj["tone_alert"] = None
    if obj.get("compliance_flag") not in ALLOWED_COMPLIANCE:
        obj["compliance_flag"] = None
    if obj.get("language_detected") not in ALLOWED_LANG:
        obj["language_detected"] = "en"
    # Clamp score.
    try:
        s = float(obj.get("client_sentiment_score") or 0)
    except Exception:  # noqa: BLE001
        s = 0.0
    obj["client_sentiment_score"] = max(-1.0, min(1.0, s))
    return obj


def mask_phone(phone: str) -> str:
    """+15149490038 → +1 514 ***-**38 (per spec)."""
    if not phone or not phone.startswith("+"):
        return phone or ""
    digits = re.sub(r"\D", "", phone)
    if len(digits) < 4:
        return phone
    cc = digits[:1]
    area = digits[1:4]
    tail = digits[-2:]
    return f"+{cc} {area} ***-**{tail}"


# ─── HTTP: mint nonce for a call_log ──────────────────────────────────

class CoachSessionInitBody(BaseModel):
    call_log_id: str


@router.post("/coach/session-init")
async def coach_session_init(
    body: CoachSessionInitBody,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Called by the AdminDialer right after POST /twilio/call. Mints a
    one-shot nonce bound to (call_log_id, contractor_id) so the WSS
    Media Stream that Twilio will open can authenticate itself."""
    log = await db.call_logs.find_one({"_id": body.call_log_id}, {"_id": 1, "agent_user_id": 1, "client_phone": 1})
    if not log:
        raise HTTPException(404, "call_log not found")
    # Only the owning agent can init coaching for their own call.
    if log.get("agent_user_id") != user.id:
        role = (getattr(user, "role", None) or "").lower()
        if role not in {"admin", "super_admin"}:
            raise HTTPException(403, "not your call")

    token = _issue_coach_nonce(
        call_log_id=body.call_log_id,
        contractor_id=user.id,
        client_phone=log.get("client_phone") or "",
    )
    return {
        "nonce": token,
        "call_log_id": body.call_log_id,
        "coach_ws_path": f"/api/ws/contractor-coaching/{body.call_log_id}",
        "ttl_seconds": NONCE_TTL_SECONDS,
    }


# ─── WebSocket: coaching push channel (dashboard side) ────────────────

@router.websocket("/ws/contractor-coaching/{call_log_id}")
async def contractor_coaching_ws(websocket: WebSocket, call_log_id: str) -> None:
    """Contractor's dashboard subscribes here to receive JSON hints as
    they are produced. JWT auth via query parameter `token=…` (the
    browser sub-protocol) — validated against the standard access token
    lifecycle."""
    tok = websocket.query_params.get("token") or ""
    # Verify JWT
    try:
        from deps import jwt_secret
        from jose import jwt as _jwt  # type: ignore[import-not-found]
        payload = _jwt.decode(tok, jwt_secret, algorithms=["HS256"])
        sub = payload.get("sub")
    except Exception:  # noqa: BLE001
        await websocket.close(code=1008, reason="invalid token")
        return
    if not sub:
        await websocket.close(code=1008, reason="no sub")
        return

    db = _get_db()
    log = await db.call_logs.find_one({"_id": call_log_id}, {"_id": 1, "agent_user_id": 1})
    if not log:
        await websocket.close(code=1008, reason="call not found")
        return
    # Ownership: dashboard client must be the agent who owns the call
    # OR an admin (support supervisors can shadow).
    if log.get("agent_user_id") != sub:
        u = await db.users.find_one({"id": sub}, {"role": 1})
        role = (u or {}).get("role", "").lower()
        if role not in {"admin", "super_admin"}:
            await websocket.close(code=1008, reason="not your call")
            return

    await websocket.accept()
    _COACH_SUBSCRIBERS.setdefault(call_log_id, set()).add(websocket)
    logger.info(f"[ai-coach] dashboard subscribed call_log_id={call_log_id} user={sub}")
    await websocket.send_json({"type": "call_status", "data": {"status": "subscribed"}, "timestamp": _now_iso()})
    try:
        while True:
            # Keep-alive; we don't expect the dashboard to send anything.
            msg = await websocket.receive_text()
            if msg == "ping":
                await websocket.send_json({"type": "pong", "timestamp": _now_iso()})
    except WebSocketDisconnect:
        pass
    finally:
        _COACH_SUBSCRIBERS.get(call_log_id, set()).discard(websocket)


# ─── WebSocket: Twilio Media Stream side (eavesdrop) ──────────────────

@router.websocket("/twilio/coach-stream")
async def twilio_coach_stream(websocket: WebSocket) -> None:
    """Twilio Media Stream (from <Start><Stream>) → silent Gemini analyzer.

    Twilio delivers the nonce in the FIRST 'start' frame under
    `start.customParameters.nonce`. We validate then open Gemini Live.
    """
    await websocket.accept()
    logger.info("[ai-coach] Twilio Media Stream WS connected — waiting for start frame")

    # Wait for the first `start` frame to validate the nonce.
    call_log_id: Optional[str] = None
    contractor_id: Optional[str] = None
    client_phone: Optional[str] = None

    try:
        first_raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
    except asyncio.TimeoutError:
        await websocket.close(code=1008, reason="no start frame")
        return
    try:
        first = json.loads(first_raw)
    except Exception:  # noqa: BLE001
        await websocket.close(code=1008, reason="bad start frame")
        return
    if first.get("event") not in {"connected", "start"}:
        await websocket.close(code=1008, reason="expected start")
        return

    if first.get("event") == "connected":
        # Twilio sends {event:'connected',protocol:'Call',version:'1.0.0'} first,
        # then follows immediately with 'start'. Read the next frame.
        try:
            second_raw = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        except asyncio.TimeoutError:
            await websocket.close(code=1008, reason="no start after connected")
            return
        try:
            first = json.loads(second_raw)
        except Exception:  # noqa: BLE001
            await websocket.close(code=1008, reason="bad start frame")
            return

    if first.get("event") != "start":
        await websocket.close(code=1008, reason="expected start")
        return

    start = first.get("start") or {}
    _stream_sid = start.get("streamSid")  # noqa: F841 — persisted for debug only
    custom_params = start.get("customParameters") or {}
    nonce_tok = custom_params.get("nonce") or ""
    row = _consume_coach_nonce(nonce_tok)
    if not row:
        logger.warning(f"[ai-coach] rejecting WS — invalid or expired nonce (len={len(nonce_tok)})")
        await websocket.close(code=1008, reason="invalid or expired nonce")
        return
    call_log_id = row["call_log_id"]
    contractor_id = row["contractor_id"]
    client_phone = row["client_phone"]
    logger.info(f"[ai-coach] Media Stream authenticated for call_log_id={call_log_id}")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("[ai-coach] GEMINI_API_KEY missing — closing coach WS")
        await websocket.close(code=1011, reason="ai unavailable")
        await _broadcast_to_dashboard(call_log_id, {
            "type": "ai_status", "data": {"status": "failed"}, "timestamp": _now_iso(),
        })
        return

    # ── Persist initial ai_voice_calls row for this outbound coach session ──
    db = _get_db()
    try:
        await db.ai_voice_calls.insert_one({
            "_id": str(uuid.uuid4()),
            "call_type":       "outbound_coach",
            "call_log_id":     call_log_id,
            "contractor_id":   contractor_id,
            "client_phone":    client_phone,
            "call_started_at": _now_iso(),
            "call_ended_at":   None,
            "duration_seconds": None,
            "language_detected": None,
            "ai_session_status": "in_progress",
            "transcript":       [],
            "coaching_hints_log": [],
            "compliance_flags_triggered": [],
            "avg_client_sentiment": None,
            "sentiment_trend": None,
            "peak_positive_moment_seconds": None,
            "peak_negative_moment_seconds": None,
            "ai_summary": None,
            "action_items": None,
            "created_at": _now_iso(),
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ai-coach] insert row failed: {e}")

    # ── Import Gemini SDK ──
    try:
        from google import genai
        from google.genai import types as gtypes
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[ai-coach] google-genai import failed: {e}")
        await websocket.close(code=1011, reason="ai sdk missing")
        return
    client = genai.Client(api_key=api_key)

    from services.ai_voice_audio import twilio_mulaw_to_gemini_pcm16

    state: Dict[str, Any] = {
        "started_at":         time.time(),
        "closed":             False,
        "transcript_buffer":  "",     # accumulated STT since last analysis
        "full_transcript":    [],     # list of {speaker,text,timestamp_seconds,sentiment_at_moment}
        "hints_log":          [],     # all validated hints
        "sentiment_series":   [],     # (t, score)
        "compliance_flags":   set(),
        "language_final":     None,
    }

    stt_cfg = gtypes.LiveConnectConfig(
        response_modalities=["AUDIO"],   # native-audio-only supports AUDIO output
        input_audio_transcription=gtypes.AudioTranscriptionConfig(),
        system_instruction=gtypes.Content(parts=[
            gtypes.Part.from_text(text="You are a passive transcription engine. Do not speak. Do not reply. Only transcribe what you hear.")
        ]),
    )

    async def _analyze_and_push(snippet: str) -> None:
        """Feed accumulated transcript to regular Gemini for JSON hints."""
        if len(snippet.strip()) < MIN_TRANSCRIPT_CHARS:
            return
        analysis_prompt = (
            f"Last ~7 seconds of a BidVex sales call (transcript):\n"
            f"---\n{snippet.strip()[:2000]}\n---\n"
            "Analyze and output the JSON coaching hint per your instructions."
        )
        try:
            resp = await client.aio.models.generate_content(
                model=os.environ.get("GEMINI_COACH_ANALYSIS_MODEL", "").strip() or ANALYSIS_MODEL_DEFAULT,
                contents=analysis_prompt,
                config=gtypes.GenerateContentConfig(
                    response_mime_type="application/json",
                    system_instruction=SYSTEM_PROMPT_COACH,
                    temperature=0.4,
                ),
            )
            raw = getattr(resp, "text", None) or ""
            hint = extract_and_validate_hint(raw)
            if hint is None:
                logger.warning(f"[ai-coach] hint failed schema: raw={raw[:200]!r}")
                return
            elapsed = round(time.time() - state["started_at"], 2)
            state["hints_log"].append({"t": elapsed, **hint})
            state["sentiment_series"].append((elapsed, hint["client_sentiment_score"]))
            if hint.get("compliance_flag"):
                state["compliance_flags"].add(hint["compliance_flag"])
            if hint.get("language_detected"):
                state["language_final"] = hint["language_detected"]
            state["full_transcript"].append({
                "speaker": "client",  # We can't reliably diarise on 1-track — attribute best-effort.
                "text": snippet.strip(),
                "timestamp_seconds": elapsed,
                "sentiment_at_moment": hint["client_sentiment_score"],
            })
            await _broadcast_to_dashboard(call_log_id, {
                "type": "coaching_hint",
                "data": hint,
                "timestamp": _now_iso(),
                "elapsed_seconds": elapsed,
            })
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ai-coach] analysis push failed: {e}")
            await _broadcast_to_dashboard(call_log_id, {
                "type": "ai_status", "data": {"status": "degraded", "reason": str(e)[:120]},
                "timestamp": _now_iso(),
            })

    async def _persist_final(reason: str) -> None:
        if state["closed"]:
            return
        state["closed"] = True
        duration = int(time.time() - state["started_at"])
        # Aggregates
        avg_s = None
        trend = None
        peak_pos = None
        peak_neg = None
        if state["sentiment_series"]:
            scores = [s for _t, s in state["sentiment_series"]]
            avg_s = round(sum(scores) / len(scores), 3)
            # Simple trend: compare first-third vs last-third average.
            if len(scores) >= 3:
                third = len(scores) // 3
                first_avg = sum(scores[:third]) / max(third, 1)
                last_avg = sum(scores[-third:]) / max(third, 1)
                delta = last_avg - first_avg
                trend = "improving" if delta > 0.15 else "declining" if delta < -0.15 else "stable"
            top = max(state["sentiment_series"], key=lambda p: p[1])
            bot = min(state["sentiment_series"], key=lambda p: p[1])
            peak_pos = round(top[0], 2)
            peak_neg = round(bot[0], 2)
        # Ai summary — best-effort 1 shot.
        summary_text = None
        try:
            joined = " ".join(h.get("coaching_hint", "") for h in state["hints_log"][-20:])
            if joined.strip():
                s_resp = await client.aio.models.generate_content(
                    model=ANALYSIS_MODEL_DEFAULT,
                    contents=f"Write a concise 2-4 sentence internal summary of a sales call given these coaching hints: {joined[:1200]}",
                )
                summary_text = (getattr(s_resp, "text", None) or "").strip()[:800]
        except Exception:  # noqa: BLE001
            pass

        try:
            await db.ai_voice_calls.update_one(
                {"call_log_id": call_log_id, "call_type": "outbound_coach"},
                {"$set": {
                    "call_ended_at":     _now_iso(),
                    "duration_seconds":  duration,
                    "ai_session_status": reason,
                    "transcript":        state["full_transcript"],
                    "coaching_hints_log": state["hints_log"],
                    "compliance_flags_triggered": sorted(state["compliance_flags"]),
                    "avg_client_sentiment": avg_s,
                    "sentiment_trend":    trend,
                    "peak_positive_moment_seconds": peak_pos,
                    "peak_negative_moment_seconds": peak_neg,
                    "language_detected":  state["language_final"],
                    "ai_summary":         summary_text,
                }},
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ai-coach] persist final failed: {e}")

        await _broadcast_to_dashboard(call_log_id, {
            "type": "ai_status", "data": {"status": "session_ended", "reason": reason},
            "timestamp": _now_iso(),
        })

    try:
        async with client.aio.live.connect(model=STT_MODEL_DEFAULT, config=stt_cfg) as session:
            async def upstream_audio() -> None:
                try:
                    async for message in websocket.iter_text():
                        try:
                            data = json.loads(message)
                        except Exception:
                            continue
                        ev = data.get("event")
                        if ev == "media":
                            payload = (data.get("media") or {}).get("payload") or ""
                            if not payload:
                                continue
                            try:
                                mulaw = base64.b64decode(payload)
                            except Exception:
                                continue
                            pcm16k = twilio_mulaw_to_gemini_pcm16(mulaw)
                            try:
                                await session.send_realtime_input(
                                    audio=gtypes.Blob(mime_type="audio/pcm;rate=16000", data=pcm16k),
                                )
                            except Exception as e:  # noqa: BLE001
                                logger.warning(f"[ai-coach] send audio failed: {e}")
                        elif ev == "stop":
                            logger.info(f"[ai-coach] Twilio 'stop' event for call_log_id={call_log_id}")
                            return
                except WebSocketDisconnect:
                    return

            async def downstream_stt() -> None:
                try:
                    async for msg in session.receive():
                        sc = getattr(msg, "server_content", None)
                        if not sc:
                            continue
                        it = getattr(sc, "input_transcription", None)
                        if it and getattr(it, "text", None):
                            state["transcript_buffer"] += it.text
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"[ai-coach] STT downstream error: {e}")

            async def analyzer_ticker() -> None:
                """Slice the accumulated transcript every ~7 s and analyse."""
                warned_time = False
                while not state["closed"]:
                    await asyncio.sleep(ANALYSIS_INTERVAL_SECONDS)
                    elapsed = time.time() - state["started_at"]
                    if elapsed > HARD_CALL_LIMIT_SECONDS:
                        # Hard cutoff — end analysis, but the actual Twilio
                        # call continues (Twilio ignores the WS close).
                        try:
                            await websocket.close(code=1000, reason="ai time limit")
                        except Exception:
                            pass
                        return
                    if elapsed > CALL_WARNING_AT_SECONDS and not warned_time:
                        warned_time = True
                        await _broadcast_to_dashboard(call_log_id, {
                            "type": "coaching_hint",
                            "data": {
                                "sentiment": "neutral", "client_sentiment_score": 0.0,
                                "tone_alert": None,
                                "coaching_hint": "Call approaching 10-minute AI session limit. Wrap up or the AI analysis will stop.",
                                "compliance_flag": None, "suggested_next_line": None,
                                "language_detected": state.get("language_final") or "en",
                            },
                            "timestamp": _now_iso(),
                        })
                    snippet = state["transcript_buffer"]
                    state["transcript_buffer"] = ""
                    if snippet.strip():
                        await _analyze_and_push(snippet)

            await _broadcast_to_dashboard(call_log_id, {
                "type": "ai_status", "data": {"status": "active"}, "timestamp": _now_iso(),
            })

            tasks = [
                asyncio.create_task(upstream_audio()),
                asyncio.create_task(downstream_stt()),
                asyncio.create_task(analyzer_ticker()),
            ]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for t in tasks:
                    t.cancel()

    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[ai-coach] session error: {e}")
        await _broadcast_to_dashboard(call_log_id, {
            "type": "ai_status", "data": {"status": "failed", "reason": str(e)[:120]},
            "timestamp": _now_iso(),
        })
        try:
            await websocket.close(code=1011, reason="gemini error")
        except Exception:
            pass
    finally:
        await _persist_final(state.get("closed") and "timeout" or "completed")


# ─── Diagnostics ──────────────────────────────────────────────────────

@router.get("/coach/config")
async def coach_config() -> Dict[str, Any]:
    return {
        "stt_model":                 os.environ.get("GEMINI_COACH_STT_MODEL", "").strip() or STT_MODEL_DEFAULT,
        "analysis_model":            os.environ.get("GEMINI_COACH_ANALYSIS_MODEL", "").strip() or ANALYSIS_MODEL_DEFAULT,
        "api_key_configured":        bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "analysis_interval_seconds": ANALYSIS_INTERVAL_SECONDS,
        "hard_limit_seconds":        HARD_CALL_LIMIT_SECONDS,
        "nonce_ttl_seconds":         NONCE_TTL_SECONDS,
    }


# ─── Admin endpoints — outbound-coach transcripts ────────────────────

from deps import require_admin  # noqa: E402


@router.get("/admin/ai-coach/sessions")
async def admin_list_coach_sessions(
    limit: int = Query(60, ge=1, le=200),
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """List outbound coach sessions. Phone numbers returned MASKED per
    the spec (+1 XXX ***-**NN)."""
    docs = await db.ai_voice_calls.find(
        {"call_type": "outbound_coach"},
        # iter337 — include followup_emails_generated so we can derive a
        # compact `followup_status` column for the list view. We keep it
        # off the wire by rewriting to a compact string after read.
        {"_id": 0, "transcript": 0, "coaching_hints_log": 0},
    ).sort("call_started_at", -1).to_list(limit)
    for d in docs:
        d["client_phone_masked"] = mask_phone(d.get("client_phone") or "")
        # Never expose raw phone in the admin list.
        d.pop("client_phone", None)
        # iter337 — derive compact per-row followup status.
        drafts = d.get("followup_emails_generated") or []
        sent = next((x for x in reversed(drafts) if x.get("sent")), None)
        if not sent:
            d["followup_status"] = "not_sent"
        elif sent.get("opened_at"):
            d["followup_status"] = "opened"
        else:
            d["followup_status"] = "sent_not_opened"
        d["followup_last_opened_at"] = (sent or {}).get("opened_at")
        d["followup_last_sent_at"]   = (sent or {}).get("sent_at")
        # Strip the potentially large array from the list payload; the
        # detail endpoint still returns it in full.
        d.pop("followup_emails_generated", None)
    return {"sessions": docs, "total": len(docs), "call_type": "outbound_coach"}


@router.get("/admin/ai-coach/sessions/{call_log_id}")
async def admin_get_coach_session(
    call_log_id: str,
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Full transcript + coaching hints log for a single outbound coach
    session. Phone masked."""
    doc = await db.ai_voice_calls.find_one(
        {"call_type": "outbound_coach", "call_log_id": call_log_id},
        {"_id": 0},
    )
    if doc is None:
        raise HTTPException(404, "coach session not found")
    doc["client_phone_masked"] = mask_phone(doc.get("client_phone") or "")
    doc.pop("client_phone", None)
    return doc


# ─── iter336: AI-generated post-call follow-up email ─────────────────

FOLLOWUP_MAX_GENERATIONS = 3


def _format_transcript_excerpt(transcript: List[Dict[str, Any]], last_n: int = 10) -> str:
    """Format the last N transcript entries as readable dialogue."""
    recent = transcript[-last_n:] if len(transcript) > last_n else transcript
    lines = []
    for entry in recent:
        speaker = "Contractor" if (entry.get("speaker") == "contractor") else "Client"
        text = (entry.get("text") or "").strip()
        if text:
            lines.append(f"{speaker}: {text[:400]}")
    return "\n".join(lines) if lines else "Transcript not available"


def _build_followup_prompt(session: Dict[str, Any]) -> str:
    """Build the Gemini prompt with all 8 context fields per the spec."""
    language = (session.get("language_detected") or "en").lower()
    lang_instruction = (
        "Respond entirely in French." if language == "fr"
        else "Respond entirely in English."
    )
    duration_min = (session.get("duration_seconds") or 0) // 60
    trend = session.get("sentiment_trend") or "unknown"
    avg_s = session.get("avg_client_sentiment")
    avg_s_str = f"{avg_s:.2f}" if isinstance(avg_s, (int, float)) else "n/a"
    flags = ", ".join(session.get("compliance_flags_triggered", []) or []) or "none"
    summary = session.get("ai_summary") or "Not available"
    action_items = "; ".join(session.get("action_items") or []) or "none"
    transcript_excerpt = _format_transcript_excerpt(session.get("transcript") or [], last_n=10)

    return f"""You are a professional sales follow-up email writer for BidVex, Canada's online auction marketplace.

A BidVex contractor just completed a sales call with a potential client. Using the call data below, write a warm, professional, and persuasive follow-up email that:
- Thanks the client for their time
- Summarizes the key points discussed
- Addresses any concerns or questions raised during the call
- Highlights the specific BidVex benefits most relevant to this client based on the conversation
- Ends with a clear, single call-to-action (register on bidvex.com, schedule a demo, or reply to this email)
- Sounds natural and human — never like a template or a bot wrote it

{lang_instruction}
Keep the email concise (under 250 words). Do not include a subject line in the body. Do not include a signature — it will be added automatically.

CALL DATA:
- Call duration: {duration_min} minutes
- Client sentiment trend: {trend}
- Average client sentiment score: {avg_s_str} (-1.0 = very negative, 1.0 = very positive)
- Compliance flags triggered: {flags}
- AI call summary: {summary}
- Action items identified: {action_items}
- Detected language: {language}
- Transcript excerpt (last 10 exchanges for context):
{transcript_excerpt}

OUTPUT FORMAT — return a JSON object with exactly these fields:
{{
  "subject_en": "email subject line in English",
  "subject_fr": "email subject line in French",
  "body": "the full email body text — plain text, no HTML, no signature"
}}
Output ONLY valid JSON. No prose, no markdown, no explanation outside the JSON."""


def _extract_followup_json(raw_text: str) -> Optional[Dict[str, str]]:
    """Extract subject_en/subject_fr/body from Gemini's output, defensively."""
    if not raw_text:
        return None
    txt = re.sub(r"```(?:json)?", "", raw_text).strip("` \n\t")
    m = re.search(r"\{.*\}", txt, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group())
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(obj, dict):
        return None
    subject_en = (obj.get("subject_en") or "").strip()
    subject_fr = (obj.get("subject_fr") or "").strip()
    body = (obj.get("body") or "").strip()
    if not (subject_en or subject_fr) or not body:
        return None
    return {
        "subject_en": subject_en[:300] or subject_fr[:300],
        "subject_fr": subject_fr[:300] or subject_en[:300],
        "body": body[:8000],
    }


def _fallback_followup_draft(session: Dict[str, Any]) -> Dict[str, str]:
    """Deterministic fallback when Gemini returns malformed JSON. Uses the
    AI summary if available, otherwise a neutral thank-you."""
    lang = (session.get("language_detected") or "en").lower()
    summary = (session.get("ai_summary") or "").strip()
    if lang == "fr":
        subject = "Suivi de notre conversation — BidVex"
        body = (
            "Bonjour,\n\n"
            "Merci d'avoir pris le temps de discuter avec nous aujourd'hui à propos de BidVex.\n\n"
            + (f"Résumé de notre échange : {summary}\n\n" if summary else "")
            + "N'hésitez pas à répondre à ce courriel si vous avez des questions, ou visitez bidvex.com "
              "pour créer votre compte et explorer nos enchères en direct.\n\n"
              "Au plaisir de vous accompagner."
        )
    else:
        subject = "Following up on our call — BidVex"
        body = (
            "Hi,\n\n"
            "Thanks for taking the time to speak with us today about BidVex.\n\n"
            + (f"Quick recap of what we discussed: {summary}\n\n" if summary else "")
            + "Please reply to this email with any follow-up questions, or head over to bidvex.com "
              "to create your account and start bidding right away.\n\n"
              "Talk soon."
        )
    return {"subject_en": subject if lang != "fr" else "Following up on our call — BidVex",
            "subject_fr": subject if lang == "fr" else "Suivi de notre conversation — BidVex",
            "body": body}


@router.post("/ai-coach/sessions/{call_log_id}/generate-followup-email")
async def generate_followup_email(
    call_log_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """One-click Gemini follow-up email drafter for a completed AI coach
    session. Owner-only + admin. Rate-limited to 3 generations per call."""
    role = (getattr(user, "role", None) or "").lower()
    is_admin = role in {"admin", "super_admin"}

    query: Dict[str, Any] = {"call_log_id": call_log_id, "call_type": "outbound_coach"}
    if not is_admin:
        query["contractor_id"] = user.id

    session = await db.ai_voice_calls.find_one(query, {"_id": 0})
    if session is None:
        # Ownership failures deliberately return the same 404 shape as
        # "not found" to avoid leaking presence to other contractors.
        raise HTTPException(404, "Session not found or access denied")

    status = (session.get("ai_session_status") or "").lower()
    if status not in {"completed", "degraded"}:
        raise HTTPException(400, "Call session must be completed before generating a follow-up")

    already = int(session.get("followup_email_generated_count", 0) or 0)
    if already >= FOLLOWUP_MAX_GENERATIONS:
        raise HTTPException(
            429,
            {
                "error": "rate_limited",
                "message_en": f"Maximum regenerations reached for this call ({FOLLOWUP_MAX_GENERATIONS}).",
                "message_fr": f"Nombre maximum de régénérations atteint pour cet appel ({FOLLOWUP_MAX_GENERATIONS}).",
                "count": already,
                "max": FOLLOWUP_MAX_GENERATIONS,
            },
        )

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(503, "AI unavailable (missing GEMINI_API_KEY)")

    prompt = _build_followup_prompt(session)
    used_fallback = False
    draft: Optional[Dict[str, str]] = None

    try:
        from google import genai
        from google.genai import types as gtypes
        client = genai.Client(api_key=api_key)
        resp = await client.aio.models.generate_content(
            model=os.environ.get("GEMINI_COACH_ANALYSIS_MODEL", "").strip() or ANALYSIS_MODEL_DEFAULT,
            contents=prompt,
            config=gtypes.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.5,
            ),
        )
        raw = getattr(resp, "text", None) or ""
        draft = _extract_followup_json(raw)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[followup-email] Gemini call failed: {e}")

    if draft is None:
        # Never 500 — deterministic fallback per spec.
        draft = _fallback_followup_draft(session)
        used_fallback = True

    language = (session.get("language_detected") or "en").lower()
    subject = draft["subject_fr"] if language == "fr" else draft["subject_en"]
    now = _now_iso()
    entry = {
        "generated_at": now,
        "language": language,
        "sent": False,
        "used_fallback": used_fallback,
    }
    try:
        await db.ai_voice_calls.update_one(
            {"call_log_id": call_log_id, "call_type": "outbound_coach"},
            {
                "$inc": {"followup_email_generated_count": 1},
                "$push": {"followup_emails_generated": entry},
            },
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[followup-email] counter update failed: {e}")

    return {
        "subject": subject,
        "subject_en": draft["subject_en"],
        "subject_fr": draft["subject_fr"],
        "body": draft["body"],
        "language_detected": language,
        "call_log_id": call_log_id,
        "count": already + 1,
        "max_regenerations": FOLLOWUP_MAX_GENERATIONS,
        "used_fallback": used_fallback,
    }



# ─── iter337 — Follow-up open status + open rate + nudges + targets ────

@router.get("/ai-coach/sessions/{call_log_id}/followup-status")
async def get_followup_status(
    call_log_id: str,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Lightweight polling endpoint for FollowUpEmailPanel to check the
    latest sent+opened state (populated by the SendGrid open webhook).
    Owner-only + admin. Cheap: projects only the 3 arrays we need."""
    role = (getattr(user, "role", None) or "").lower()
    is_admin = role in {"admin", "super_admin"}
    q: Dict[str, Any] = {"call_log_id": call_log_id, "call_type": "outbound_coach"}
    if not is_admin:
        q["contractor_id"] = user.id
    doc = await db.ai_voice_calls.find_one(
        q,
        {
            "_id": 0,
            "followup_emails_generated": 1,
            "followup_email_generated_count": 1,
        },
    )
    if doc is None:
        raise HTTPException(404, "Session not found or access denied")
    drafts = doc.get("followup_emails_generated") or []
    sent = next((d for d in reversed(drafts) if d.get("sent")), None)
    return {
        "call_log_id":  call_log_id,
        "generated_count": int(doc.get("followup_email_generated_count") or 0),
        "max_regenerations": FOLLOWUP_MAX_GENERATIONS,
        "sent":         bool(sent),
        "sent_at":      (sent or {}).get("sent_at"),
        "opened":       bool((sent or {}).get("opened_at")),
        "opened_at":    (sent or {}).get("opened_at"),
    }


@router.get("/admin/ai-coach/followup-open-rate")
async def admin_followup_open_rate(
    days: int = Query(30, ge=1, le=365),
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Aggregate open-rate across all AI follow-up emails sent in the
    last N days. Returns count + rate for the admin Coach Sessions
    header ('X% of AI follow-up emails opened, last 30 days')."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    pipeline = [
        {"$match": {"call_type": "outbound_coach"}},
        {"$project": {
            "_id": 0,
            "drafts": {
                "$filter": {
                    "input": {"$ifNull": ["$followup_emails_generated", []]},
                    "as": "d",
                    "cond": {"$and": [
                        {"$eq": ["$$d.sent", True]},
                        {"$gte": ["$$d.sent_at", cutoff]},
                    ]},
                },
            },
        }},
        {"$unwind": "$drafts"},
        {"$group": {
            "_id": None,
            "sent_count":   {"$sum": 1},
            "opened_count": {"$sum": {"$cond": [{"$ne": ["$drafts.opened_at", None]}, 1, 0]}},
        }},
    ]
    docs = await db.ai_voice_calls.aggregate(pipeline).to_list(1)
    if not docs:
        return {"sent_count": 0, "opened_count": 0, "open_rate_pct": 0.0, "window_days": days}
    row = docs[0]
    sent = int(row.get("sent_count") or 0)
    opened = int(row.get("opened_count") or 0)
    rate = round((opened / sent) * 100.0, 1) if sent > 0 else 0.0
    return {
        "sent_count":    sent,
        "opened_count":  opened,
        "open_rate_pct": rate,
        "window_days":   days,
    }


# ─── Nudges ─────────────────────────────────────────────────────────────

@router.get("/ai-coach/nudges")
async def list_nudges(
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """List active (undismissed, unread-or-recent) post-call nudges for
    the current contractor."""
    cursor = db.notifications.find(
        {
            "user_id": user.id,
            "type": {"$in": ["contractor_post_call_nudge", "ai_followup_opened"]},
            "dismissed": {"$ne": True},
        },
        {"_id": 0},
    ).sort("created_at", -1).limit(limit)
    items = [n async for n in cursor]
    return {"nudges": items, "total": len(items)}


class DismissBody(BaseModel):
    id: str


@router.post("/ai-coach/nudges/dismiss")
async def dismiss_nudge(
    body: DismissBody,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Mark a single nudge as dismissed. Idempotent — dismissing twice
    returns the same shape."""
    r = await db.notifications.update_one(
        {"id": body.id, "user_id": user.id},
        {"$set": {
            "dismissed": True,
            "dismissed_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "nudge not found")
    return {"id": body.id, "dismissed": True}


# ─── Today's Follow-Up Targets ──────────────────────────────────────────

@router.get("/ai-coach/followup-targets")
async def list_followup_targets(
    user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Return the pre-built list of at most 5 prioritised follow-up
    targets for the current contractor. Snapshot is refreshed daily by
    the scheduler; the endpoint just serves the persisted document."""
    from services.nudge_engine import FOLLOWUP_TARGET_COLLECTION
    doc = await db[FOLLOWUP_TARGET_COLLECTION].find_one(
        {"contractor_id": user.id}, {"_id": 0},
    )
    if not doc:
        return {"items": [], "generated_at": None, "contractor_id": user.id}
    # Filter out dismissed items — the dashboard doesn't want to see them.
    visible = [i for i in (doc.get("items") or []) if not i.get("dismissed")]
    return {
        "items":          visible,
        "generated_at":   doc.get("generated_at"),
        "generated_date": doc.get("generated_date"),
        "contractor_id":  user.id,
    }


class TargetDismissBody(BaseModel):
    id: str


@router.post("/ai-coach/followup-targets/dismiss")
async def dismiss_followup_target(
    body: TargetDismissBody,
    user: User = Depends(get_current_user),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """Mark a single follow-up target item as dismissed for this
    contractor. Idempotent — subsequent dismisses return the same shape.
    The scheduler preserves dismissed=true across daily refreshes so
    the item stays hidden."""
    from services.nudge_engine import FOLLOWUP_TARGET_COLLECTION
    r = await db[FOLLOWUP_TARGET_COLLECTION].update_one(
        {"contractor_id": user.id, "items.id": body.id},
        {"$set": {
            "items.$.dismissed":    True,
            "items.$.dismissed_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    if r.matched_count == 0:
        raise HTTPException(404, "target not found")
    return {"id": body.id, "dismissed": True}
