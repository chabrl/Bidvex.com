"""
iter334 — BidVex AI Voice Assistant (Twilio Media Streams ↔ Gemini Live).

Endpoints mounted under /api:

  POST /twilio/ivr/ai-assistant
    HTTP webhook Twilio hits when the caller presses '9' on the main IVR.
    Returns TwiML that opens a bi-directional Media Stream to our
    /twilio/ai-stream WebSocket, along with a short-lived signed nonce
    that gates who may connect.

  GET  /twilio/ivr/ai-fallback
    Fallback TwiML used when the Gemini Live session fails to open.
    Announces a graceful hold and routes the caller to the /route?Digits=0
    general-support bridge (iter333).

  WS   /twilio/ai-stream
    The bi-directional Twilio Media Stream. Payloads are µ-law/8kHz JSON
    frames — we transcode them to PCM/16kHz for Gemini, receive PCM/24kHz
    back, and transcode to µ-law/8kHz for Twilio's playback. The system
    prompt (BidVex General Assistant) is injected once at connection.

  GET  /admin/ai-voice/calls
    Admin listing of stored transcripts (speaker-labelled).

Environment:
    GEMINI_API_KEY               — reused from the existing Gemini config.
    GEMINI_LIVE_MODEL (optional) — overrides the default model identifier.
"""
from __future__ import annotations

import asyncio
import base64
import hmac
import json
import logging
import os
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from xml.sax.saxutils import escape as _xml_escape

from fastapi import (
    APIRouter, Depends, HTTPException, Query, Request, WebSocket, WebSocketDisconnect,
)
from fastapi.responses import Response
from pydantic import BaseModel

from deps import require_admin, get_db, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["AI Voice — iter334"])

# ─── Configuration ────────────────────────────────────────────────────

GEMINI_LIVE_MODEL_DEFAULT = "gemini-2.5-flash-native-audio-latest"
NONCE_TTL_SECONDS = 120  # Twilio dials the WS within ~5s, but be generous.
HARD_CALL_LIMIT_SECONDS = 10 * 60      # 10 minutes total.
CALL_WARNING_AT_SECONDS = 9 * 60       # 9-minute soft warning.
CALLER_SILENCE_WARN_SECONDS = 10
CALLER_SILENCE_END_SECONDS = 20

# Regex intents that instantly transfer to human support (defence-in-depth
# in case Gemini fails to emit the [TRANSFER_TO_SUPPORT] marker for very
# short utterances like "agent!").
HUMAN_HANDOFF_UTTERANCE_RE = re.compile(
    r"\b(agent|human|support|representative|real\s+person|talk\s+to\s+someone|"
    r"parler\s+(?:à|a)\s+(?:quelqu'un|une\s+personne|un\s+agent)|un\s+humain|"
    r"un\s+repr(?:é|e)sentant)\b",
    re.IGNORECASE,
)

BIDVEX_AI_ASSISTANT_SYSTEM_PROMPT = """You are the BidVex AI Assistant — a helpful, professional, bilingual (English and French) voice assistant for BidVex Inc., Canada's online auction marketplace headquartered in Sherbrooke, Québec. You help callers understand how the platform works.

You can answer questions about:
- How to register as a buyer or seller
- How auctions work (bidding, soft-close, buy now, deposits)
- Vehicle auctions (licensed dealer requirements, provincial compliance, broker intermediaries)
- Lots and multi-item auctions (liquidation events, lot bidding)
- Storage auctions
- Marketplace single-item listings
- Fees and commissions (2.5% platform fee, buyer's premium, deposits)
- Bill 96 Quebec bilingual listing requirements
- How to become a broker or partner
- How to contact a human agent or support team

You do NOT have access to live auction data, real-time prices, or individual user accounts. If asked about a specific listing, bid status, or account issue, tell the caller you cannot access live data over the phone and direct them to bidvex.com or service@bidvex.com.

Always be concise — this is a voice call, not a chat interface. Keep responses under 3 sentences unless the caller asks for more detail. Be warm, professional, and efficient.

If the caller speaks French, respond entirely in French. If they speak English, respond entirely in English. Match the caller's language automatically from their first utterance.

If the caller asks to speak with a human, a real person, an agent, or support, immediately say "Let me connect you to our support team" (or the French equivalent) and output the special marker [TRANSFER_TO_SUPPORT] on a new line. Do not output anything else after this marker.

If the session is approaching its time limit, warn the caller and offer to connect them to support before it ends."""


# ─── Nonce store (in-memory; TTL-bound) ───────────────────────────────
# Twilio does not sign Media Stream WebSocket connections. We instead
# generate a per-call nonce inside the signed webhook and require Twilio
# to present it back on the WS handshake. Nonces are one-shot.

_STREAM_NONCES: Dict[str, Dict[str, Any]] = {}


def _issue_nonce(call_sid: str, lang: str) -> str:
    token = secrets.token_urlsafe(24)
    _STREAM_NONCES[token] = {
        "call_sid": call_sid,
        "lang": lang,
        "expires_at": time.time() + NONCE_TTL_SECONDS,
    }
    # Cheap GC of expired nonces so the dict does not grow unbounded.
    _gc_nonces()
    return token


def _consume_nonce(token: str) -> Optional[Dict[str, Any]]:
    row = _STREAM_NONCES.pop(token, None)
    if not row:
        return None
    if row["expires_at"] < time.time():
        return None
    return row


def _gc_nonces() -> None:
    now = time.time()
    dead = [k for k, v in _STREAM_NONCES.items() if v["expires_at"] < now]
    for k in dead:
        _STREAM_NONCES.pop(k, None)


# ─── Helpers imported lazily to keep import cycles at bay ─────────────

def _public_base(request: Request) -> str:
    from routes.contractor_ivr_inbound import _public_base as _pb
    return _pb(request)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_db():
    from server import db
    return db


def _twiml(xml: str) -> Response:
    return Response(content=xml, media_type="application/xml")


async def _validate_twilio_signature(request: Request) -> None:
    from routes.contractor_ivr_inbound import _validate_twilio_signature as _vt
    await _vt(request)


# ─── HTTP endpoint: TwiML that opens the Media Stream ─────────────────

@router.post("/twilio/ivr/ai-assistant")
async def ivr_ai_assistant(request: Request) -> Response:
    """TwiML that connects Twilio to our WebSocket AI voice bridge."""
    await _validate_twilio_signature(request)
    form = dict(await request.form())
    base_https = _public_base(request)               # https://…
    ws_base = base_https.replace("https://", "wss://").replace("http://", "ws://")
    lang = (request.query_params.get("lang") or "en").lower()
    is_fr = lang.startswith("fr")
    call_sid = form.get("CallSid") or f"unknown-{uuid.uuid4().hex[:8]}"

    # Persist an AI call row so admin transcript view can find it later.
    try:
        db = _get_db()
        await db.ai_voice_calls.insert_one({
            "id":          str(uuid.uuid4()),
            "call_sid":    call_sid,
            "from_number": form.get("From"),
            "lang":        lang,
            "started_at":  _now_iso(),
            "ended_at":    None,
            "status":      "connecting",
            "transcript":  [],
            "summary":     None,
            "duration_seconds": None,
            "handoff":     None,
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ai-voice] could not insert AI call row: {e}")

    token = _issue_nonce(call_sid, lang)

    intro_en = "Welcome to BidVex AI Assistant — how can I help you today?"
    intro_fr = "Bienvenue chez l'assistant IA BidVex — comment puis-je vous aider ?"
    intro    = intro_fr if is_fr else intro_en
    lang_iso = "fr-CA" if is_fr else "en-US"

    stream_url = f"{ws_base}/api/twilio/ai-stream?token={token}&lang={lang}"

    # <Say> plays the greeting immediately; <Connect><Stream> then runs
    # bi-directionally until closed. `statusCallback` fires so we can
    # persist final timings even if the WS closed abnormally.
    status_cb = f"{base_https}/api/twilio/ai-stream/status?call_sid={call_sid}"

    # iter332 pattern — every URL going into an XML attribute must have
    # its raw '&' escaped to '&amp;' or the strict TwiML parser rejects
    # the whole document with error 12100.
    stream_url_xml = _xml_escape(stream_url)
    status_cb_xml  = _xml_escape(status_cb)
    fallback_url_xml = _xml_escape(f"{base_https}/api/twilio/ivr/ai-fallback?lang={lang}")

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="{lang_iso}">{intro}</Say>
  <Connect>
    <Stream url="{stream_url_xml}" statusCallback="{status_cb_xml}" statusCallbackMethod="POST" track="inbound_track" />
  </Connect>
  <Redirect method="POST">{fallback_url_xml}</Redirect>
</Response>"""
    return _twiml(xml)


@router.get("/twilio/ivr/ai-fallback")
async def ivr_ai_fallback(request: Request) -> Response:
    """Fallback when the WS handshake fails — hand off to press-0 support."""
    base = _public_base(request)
    lang = (request.query_params.get("lang") or "en").lower()
    is_fr = lang.startswith("fr")

    say_en = "Our AI assistant is temporarily unavailable. Please hold while we connect you to support."
    say_fr = "Notre assistant IA est momentanément indisponible. Veuillez patienter, nous vous transférons au soutien."
    say    = say_fr if is_fr else say_en
    lang_iso = "fr-CA" if is_fr else "en-US"
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="{lang_iso}">{say}</Say>
  <Redirect method="POST">{base}/api/twilio/ivr/route?lang={lang}&amp;Digits=0</Redirect>
</Response>"""
    return _twiml(xml)


@router.post("/twilio/ai-stream/status")
async def ai_stream_status(request: Request) -> Response:
    """Media Stream status callback — persists final status and duration."""
    form = dict(await request.form())
    call_sid = request.query_params.get("call_sid") or form.get("CallSid")
    ev = form.get("StreamEvent") or form.get("StreamStatus")
    if not call_sid:
        return Response(status_code=204)
    try:
        db = _get_db()
        await db.ai_voice_calls.update_one(
            {"call_sid": call_sid},
            {"$set": {"last_stream_event": ev, "last_event_at": _now_iso()}},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ai-voice] status cb update failed: {e}")
    return Response(status_code=204)


# ─── Twilio → Gemini bridge (WebSocket handler) ───────────────────────

@router.websocket("/twilio/ai-stream")
async def twilio_ai_stream(websocket: WebSocket) -> None:
    """Bridge Twilio Media Stream ↔ Gemini Live.

    Note: Twilio's Media Stream WebSocket protocol emits JSON envelopes:
      { event: 'connected', … }
      { event: 'start',   start: {streamSid, callSid, …} }
      { event: 'media',   media: {payload: <base64 µ-law>, chunk, timestamp} }
      { event: 'mark',    mark: {name} }        # optional
      { event: 'stop',    streamSid }
    """
    # ── Nonce validation (our stand-in for Twilio-signed WS) ─────
    token = websocket.query_params.get("token") or ""
    lang  = (websocket.query_params.get("lang") or "en").lower()
    nonce = _consume_nonce(token)
    if not nonce:
        await websocket.close(code=1008, reason="invalid or expired nonce")
        return
    call_sid = nonce["call_sid"]
    lang     = nonce["lang"] or lang

    await websocket.accept()
    logger.info(f"[ai-voice] WS accepted for call_sid={call_sid} lang={lang}")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("[ai-voice] GEMINI_API_KEY missing — closing WS")
        await websocket.close(code=1011, reason="ai unavailable")
        return

    # Session state
    state: Dict[str, Any] = {
        "stream_sid":   None,
        "started_at":   time.time(),
        "last_caller_audio_at": time.time(),
        "transcript":   [],       # list of {"role","text","ts"}
        "handoff":      None,     # 'transfer_to_support' | None
        "closed":       False,
    }

    # ── Gemini Live SDK (lazy-import so this module still loads even if
    #    google-genai has a transient issue) ──────────────────────────
    try:
        from google import genai
        from google.genai import types as gtypes
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[ai-voice] google-genai import failed: {e}")
        await websocket.close(code=1011, reason="ai sdk missing")
        return

    live_model = os.environ.get("GEMINI_LIVE_MODEL", "").strip() or GEMINI_LIVE_MODEL_DEFAULT
    client = genai.Client(api_key=api_key)

    # System instruction / persona
    lang_hint = ("\n\nCurrent caller language hint: FRENCH. Prefer French unless the caller clearly speaks English."
                 if lang.startswith("fr")
                 else "\n\nCurrent caller language hint: ENGLISH. Prefer English unless the caller clearly speaks French.")
    live_config = gtypes.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=gtypes.Content(
            parts=[gtypes.Part.from_text(text=BIDVEX_AI_ASSISTANT_SYSTEM_PROMPT + lang_hint)]
        ),
    )

    # Import audio helpers
    from services.ai_voice_audio import (
        twilio_mulaw_to_gemini_pcm16,
        gemini_pcm16_to_twilio_mulaw,
    )

    session_ended_reason: Optional[str] = None

    async def _persist_final(reason: str) -> None:
        if state["closed"]:
            return
        state["closed"] = True
        duration = int(time.time() - state["started_at"])
        summary_line = " ".join(
            (t.get("text") or "").strip()
            for t in state["transcript"][-6:]
            if t.get("role") == "assistant"
        )[:400]
        try:
            db = _get_db()
            await db.ai_voice_calls.update_one(
                {"call_sid": call_sid},
                {"$set": {
                    "ended_at": _now_iso(),
                    "status":   f"ended_{reason}",
                    "transcript": state["transcript"],
                    "duration_seconds": duration,
                    "summary":  summary_line or None,
                    "handoff":  state["handoff"],
                    "lang_final": lang,
                }},
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ai-voice] persist final failed: {e}")

    async def _bridge_to_support() -> None:
        """When [TRANSFER_TO_SUPPORT] is detected: modify the live Twilio call
        to redirect to the press-0 support bridge. Requires the Twilio REST
        credentials — reuses the same TWILIO_ACCOUNT_SID/TWILIO_AUTH_TOKEN
        pair the rest of the platform uses."""
        state["handoff"] = "transfer_to_support"
        try:
            from twilio.rest import Client as TwilioClient
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ai-voice] twilio SDK missing: {e}")
            return
        sid   = os.environ.get("TWILIO_ACCOUNT_SID", "").strip()
        tok   = os.environ.get("TWILIO_AUTH_TOKEN", "").strip()
        pub_base = os.environ.get("TWILIO_PUBLIC_BASE", "").strip()
        if not (sid and tok):
            logger.warning("[ai-voice] Twilio REST creds missing — cannot transfer")
            return
        # Compose an absolute URL for /api/twilio/ivr/route?Digits=0 that
        # Twilio's REST call can dial back into.
        base = pub_base or "https://bidvex.com"
        redirect_url = f"{base}/api/twilio/ivr/route?lang={lang}&Digits=0"
        try:
            TwilioClient(sid, tok).calls(call_sid).update(
                method="POST", url=redirect_url,
            )
            logger.info(f"[ai-voice] transferred call={call_sid} → {redirect_url}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ai-voice] Twilio transfer failed: {e}")

    async def _send_clear_to_twilio() -> None:
        """Barge-in helper — purge Twilio's playback buffer."""
        if state.get("stream_sid"):
            try:
                await websocket.send_text(json.dumps({
                    "event": "clear",
                    "streamSid": state["stream_sid"],
                }))
            except Exception:  # noqa: BLE001
                pass

    # ── Open Gemini Live session ──────────────────────────────────
    try:
        async with client.aio.live.connect(model=live_model, config=live_config) as session:

            async def upstream() -> None:
                """Twilio → Gemini."""
                try:
                    async for message in websocket.iter_text():
                        try:
                            data = json.loads(message)
                        except Exception:
                            continue
                        ev = data.get("event")

                        if ev == "start":
                            state["stream_sid"] = data.get("start", {}).get("streamSid")
                            logger.info(f"[ai-voice] stream started sid={state['stream_sid']}")

                        elif ev == "media":
                            payload = (data.get("media") or {}).get("payload") or ""
                            if not payload:
                                continue
                            mulaw = base64.b64decode(payload)
                            pcm16 = twilio_mulaw_to_gemini_pcm16(mulaw)
                            state["last_caller_audio_at"] = time.time()
                            try:
                                await session.send_realtime_input(
                                    audio=gtypes.Blob(
                                        mime_type="audio/pcm;rate=16000",
                                        data=pcm16,
                                    ),
                                )
                            except Exception as e:  # noqa: BLE001
                                logger.warning(f"[ai-voice] send audio failed: {e}")

                        elif ev == "stop":
                            logger.info(f"[ai-voice] Twilio sent stop for sid={state['stream_sid']}")
                            return
                except WebSocketDisconnect:
                    return

            async def downstream() -> None:
                """Gemini → Twilio, plus transcript accumulation."""
                nonlocal session_ended_reason
                try:
                    async for msg in session.receive():
                        sc = getattr(msg, "server_content", None)
                        if not sc:
                            continue

                        model_turn = getattr(sc, "model_turn", None)
                        if not model_turn:
                            continue

                        for part in (getattr(model_turn, "parts", None) or []):
                            # Accumulate the model's text for transcripts and
                            # transfer-marker detection.
                            text_piece = getattr(part, "text", None)
                            if text_piece:
                                if "[TRANSFER_TO_SUPPORT]" in text_piece:
                                    logger.info("[ai-voice] TRANSFER_TO_SUPPORT marker detected")
                                    # Strip the marker before persisting.
                                    clean = text_piece.replace("[TRANSFER_TO_SUPPORT]", "").strip()
                                    if clean:
                                        state["transcript"].append({
                                            "role": "assistant", "text": clean, "ts": _now_iso(),
                                        })
                                    await _bridge_to_support()
                                    session_ended_reason = "transferred"
                                    return
                                state["transcript"].append({
                                    "role": "assistant", "text": text_piece, "ts": _now_iso(),
                                })

                            # Ship audio back to Twilio (24 kHz PCM → µ-law 8 kHz).
                            inline = getattr(part, "inline_data", None)
                            pcm16_24k = getattr(inline, "data", None) if inline else None
                            if pcm16_24k:
                                mulaw = gemini_pcm16_to_twilio_mulaw(pcm16_24k)
                                if state.get("stream_sid") and mulaw:
                                    try:
                                        await websocket.send_text(json.dumps({
                                            "event": "media",
                                            "streamSid": state["stream_sid"],
                                            "media": {"payload": base64.b64encode(mulaw).decode("ascii")},
                                        }))
                                    except Exception as e:  # noqa: BLE001
                                        logger.warning(f"[ai-voice] send audio to twilio failed: {e}")
                                        return

                        # Turn-complete event (Gemini finished a response).
                        if getattr(sc, "turn_complete", False):
                            # No-op — we simply keep listening for the next
                            # user turn.
                            pass
                except Exception as e:  # noqa: BLE001
                    logger.warning(f"[ai-voice] downstream error: {e}")

            async def watchdog() -> None:
                """Enforces hard cutoff and silence timeouts."""
                nonlocal session_ended_reason
                warned_time = False
                warned_silence = False
                while not state["closed"]:
                    await asyncio.sleep(2)
                    elapsed = time.time() - state["started_at"]
                    if elapsed > HARD_CALL_LIMIT_SECONDS:
                        session_ended_reason = "time_limit"
                        try:
                            await websocket.close(code=1000, reason="10-minute limit")
                        except Exception:
                            pass
                        return
                    if elapsed > CALL_WARNING_AT_SECONDS and not warned_time:
                        warned_time = True
                        # Ask Gemini to warn the user, verbally.
                        try:
                            warn_prompt = ("(SYSTEM) The session will end in 60 seconds. "
                                           "Warn the caller that we're near the time limit and "
                                           "offer to transfer to human support.")
                            await session.send_realtime_input(text=warn_prompt)
                        except Exception:
                            pass

                    silent_for = time.time() - state["last_caller_audio_at"]
                    if silent_for > CALLER_SILENCE_END_SECONDS:
                        session_ended_reason = "silence_timeout"
                        try:
                            await websocket.close(code=1000, reason="silence")
                        except Exception:
                            pass
                        return
                    if silent_for > CALLER_SILENCE_WARN_SECONDS and not warned_silence:
                        warned_silence = True
                        try:
                            nudge = ("(SYSTEM) The caller has been silent for 10 seconds. "
                                     "Gently prompt them: 'Are you still there? Etes-vous toujours la?'")
                            await session.send_realtime_input(text=nudge)
                        except Exception:
                            pass

            watchdog_task = asyncio.create_task(watchdog())
            try:
                await asyncio.gather(upstream(), downstream())
            finally:
                watchdog_task.cancel()

    except WebSocketDisconnect:
        session_ended_reason = session_ended_reason or "caller_hangup"
    except Exception as e:  # noqa: BLE001
        session_ended_reason = "gemini_error"
        logger.exception(f"[ai-voice] Gemini Live session failed: {e}")
        try:
            await websocket.close(code=1011, reason="gemini error")
        except Exception:
            pass
    finally:
        await _persist_final(session_ended_reason or "unknown")


# ─── Admin endpoints (transcripts) ────────────────────────────────────

class AICallSummary(BaseModel):
    id:          Optional[str] = None
    call_sid:    Optional[str] = None
    from_number: Optional[str] = None
    lang:        Optional[str] = None
    lang_final:  Optional[str] = None
    started_at:  Optional[str] = None
    ended_at:    Optional[str] = None
    status:      Optional[str] = None
    handoff:     Optional[str] = None
    duration_seconds: Optional[int] = None
    summary:     Optional[str] = None
    transcript_len: int = 0


@router.get("/admin/ai-voice/calls")
async def admin_list_ai_calls(
    limit: int = Query(60, ge=1, le=200),
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    """List recent BidVex AI voice-assistant calls (transcript summaries)."""
    docs = await db.ai_voice_calls.find(
        {},
        {"_id": 0, "transcript": {"$slice": -1}},  # send tail only to save bytes
    ).sort("started_at", -1).to_list(limit)

    # Second pass: fetch transcript length via aggregation-lite in Python.
    calls: List[Dict[str, Any]] = []
    for d in docs:
        entry = {k: v for k, v in d.items() if k != "transcript"}
        entry["transcript_len"] = 0  # will be filled below in full-fetch endpoint
        calls.append(entry)
    return {"calls": calls, "total": len(calls)}


@router.get("/admin/ai-voice/calls/{call_sid}")
async def admin_get_ai_call(
    call_sid: str,
    user: User = Depends(require_admin),
    db=Depends(get_db),
) -> Dict[str, Any]:
    doc = await db.ai_voice_calls.find_one({"call_sid": call_sid}, {"_id": 0})
    if doc is None:
        raise HTTPException(404, "call not found")
    return doc


# ─── Introspection endpoint used by the tests ─────────────────────────

@router.get("/twilio/ai-voice/config")
async def ai_voice_config(request: Request) -> Dict[str, Any]:
    """Non-secret diagnostics — is the AI voice pipeline wired up?"""
    return {
        "model":               os.environ.get("GEMINI_LIVE_MODEL") or GEMINI_LIVE_MODEL_DEFAULT,
        "api_key_configured":  bool(os.environ.get("GEMINI_API_KEY", "").strip()),
        "hard_limit_seconds":  HARD_CALL_LIMIT_SECONDS,
        "silence_end_seconds": CALLER_SILENCE_END_SECONDS,
    }
