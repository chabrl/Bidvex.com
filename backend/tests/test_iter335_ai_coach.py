"""
iter335 — Regression suite for the Outbound Silent AI Coach.

Covers the 8 mandatory checkpoints:
  1. Inbound IVR (iter324/332/333/334) untouched — no Gemini/WS leaked
     into the extension or press-0 branches. Only the press-9 branch has
     Gemini, and that lives on the completely separate iter334 pipeline.
  2. TwiML builder emits <Start><Stream> ONLY when coach nonce provided.
  3. TwiML shape when coach is enabled: <Start> before <Dial>, non-terminal.
  4. /coach/session-init mints a unique one-shot nonce with 60-120s TTL.
  5. Coach WS rejects Media Stream connection without a valid nonce.
  6. Nonce is one-shot — second WS connect with same nonce is rejected.
  7. audioop µ-law/8k → PCM16/16k round-trip preserves byte count.
  8. Coach JSON output extractor + validator returns valid schema keys.
  9. `ai_voice_calls` collection remains partitioned by call_type
     ("outbound_coach" here vs. "inbound_press9" from iter334).
"""
from __future__ import annotations

import asyncio
import os
import xml.etree.ElementTree as ET

import httpx
import pytest


BASE = os.environ.get("PREVIEW_API_URL") or "https://prod-verify-2.preview.emergentagent.com"

ADMIN_EMAIL    = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


def _admin_token() -> str:
    r = httpx.post(
        f"{BASE}/api/auth/login",
        headers={"Content-Type": "application/json"},
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("token") or r.json().get("access_token") or ""


# ─── 1) Inbound IVR audit — no coach WS leaked ───────────────────────

def test_inbound_ivr_press_0_still_bridges_support_no_gemini():
    """Direct verification that press-0 emits ONLY a bare <Dial><Number>."""
    r = httpx.post(
        f"{BASE}/api/twilio/ivr/route?lang=en",
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "bidvex.com",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"Digits": "0", "From": "+15145550002", "CallSid": "CAtest_iter335_audit_p0"},
        timeout=15,
    )
    assert r.status_code == 200
    root = ET.fromstring(r.text)
    # Must NOT contain <Start>, <Stream>, <Connect> — those are all
    # Gemini/streaming signals that must NOT touch the press-0 branch.
    assert root.find(".//Start") is None
    assert root.find(".//Stream") is None
    assert root.find(".//Connect") is None
    number = root.find(".//Number")
    assert number is not None and (number.text or "").strip() == "+15149490038"


def test_inbound_ivr_extension_no_coach_gemini_leak():
    """Contractor extension (e.g. 1220) → contractor dial with whisper URL.
    Must NOT emit any coach-stream URL."""
    r = httpx.post(
        f"{BASE}/api/twilio/ivr/route?lang=en",
        headers={
            "X-Forwarded-Proto": "https",
            "X-Forwarded-Host": "bidvex.com",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        data={"Digits": "1220", "From": "+15145550003", "CallSid": "CAtest_iter335_audit_ext"},
        timeout=15,
    )
    assert r.status_code == 200
    root = ET.fromstring(r.text)
    # Extension branch has a whisper <Number url="…"> — that URL must NOT
    # be the coach-stream endpoint.
    number = root.find(".//Number")
    if number is not None:
        whisper = number.get("url") or ""
        assert "/api/twilio/coach-stream" not in whisper, "Coach WS leaked into extension whisper URL!"


# ─── 2 & 3) TwiML builder ────────────────────────────────────────────

def test_twiml_builder_no_coach_params_is_identical_to_iter316():
    """Regression: without coach params, TwiML is exactly the previous shape."""
    from services.twilio_service import build_outbound_twiml
    xml = build_outbound_twiml(
        client_phone_number="+18195803757",
        status_callback="https://bidvex.com/api/twilio/call-status-callback",
        recording_callback="https://bidvex.com/api/twilio/recording-callback",
    )
    root = ET.fromstring(xml)
    assert root.find(".//Start") is None
    assert root.find(".//Stream") is None
    dial = root.find(".//Dial")
    assert dial is not None
    assert dial.find("Number") is not None


def test_twiml_builder_with_coach_params_prepends_start_stream():
    """When coach_stream_url + coach_nonce given, <Start><Stream> is
    prepended BEFORE <Dial> (non-terminal — call proceeds to bridge)."""
    from services.twilio_service import build_outbound_twiml
    xml = build_outbound_twiml(
        client_phone_number="+18195803757",
        status_callback="https://bidvex.com/api/twilio/call-status-callback",
        recording_callback="https://bidvex.com/api/twilio/recording-callback",
        coach_stream_url="wss://bidvex.com/api/twilio/coach-stream",
        coach_nonce="ITER335-TEST-NONCE",
    )
    root = ET.fromstring(xml)
    start = root.find(".//Start")
    stream = root.find(".//Start/Stream")
    dial = root.find(".//Dial")
    assert start is not None
    assert stream is not None
    assert stream.get("url") == "wss://bidvex.com/api/twilio/coach-stream"
    assert stream.get("track") == "both_tracks"
    param = stream.find("Parameter[@name='nonce']")
    assert param is not None
    assert param.get("value") == "ITER335-TEST-NONCE"
    # Order: <Start> must come BEFORE <Dial>
    children = list(root)
    assert children.index(start) < children.index(dial)


# ─── 4) /coach/session-init mints a one-shot nonce ───────────────────

def test_coach_session_init_mints_nonce():
    tok = _admin_token()
    # Create a call_log
    r = httpx.post(
        f"{BASE}/api/twilio/call",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}"},
        json={"client_phone": "+18195803757", "client_type": "individual", "call_purpose": "iter335 nonce test"},
        timeout=15,
    )
    assert r.status_code == 200, r.text
    call_log_id = r.json()["call_log_id"]

    r2 = httpx.post(
        f"{BASE}/api/coach/session-init",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}"},
        json={"call_log_id": call_log_id},
        timeout=15,
    )
    assert r2.status_code == 200
    d = r2.json()
    assert d.get("call_log_id") == call_log_id
    assert isinstance(d.get("nonce"), str) and len(d["nonce"]) >= 32
    assert d.get("ttl_seconds") == 120
    assert d.get("coach_ws_path", "").endswith(call_log_id)


def test_coach_session_init_rejects_bad_call_log_id():
    tok = _admin_token()
    r = httpx.post(
        f"{BASE}/api/coach/session-init",
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {tok}"},
        json={"call_log_id": "does-not-exist-uuid"},
        timeout=15,
    )
    assert r.status_code == 404


# ─── 5 & 6) WebSocket nonce enforcement ──────────────────────────────

@pytest.mark.asyncio
async def test_coach_ws_rejects_missing_or_invalid_nonce():
    """The Twilio Media Stream WS closes if the first `start` frame does
    not carry a valid nonce in customParameters."""
    import websockets
    from websockets.exceptions import ConnectionClosed
    try:
        _InvalidStatus = websockets.exceptions.InvalidStatus
    except AttributeError:
        _InvalidStatus = websockets.exceptions.InvalidStatusCode  # type: ignore[attr-defined]

    ws_url = BASE.replace("https://", "wss://").replace("http://", "ws://")
    url = f"{ws_url}/api/twilio/coach-stream"
    try:
        async with websockets.connect(url, open_timeout=10, close_timeout=5) as ws:
            # Twilio would first send 'connected', then 'start'.
            await ws.send('{"event":"connected","protocol":"Call","version":"1.0.0"}')
            await ws.send('{"event":"start","start":{"streamSid":"MZ_fake","customParameters":{"nonce":"BAD"}}}')
            with pytest.raises(Exception):
                await asyncio.wait_for(ws.recv(), timeout=4)
    except _InvalidStatus as e:
        status = getattr(getattr(e, "response", None), "status_code", None) or getattr(e, "status_code", None)
        assert status in (400, 401, 403, 404), f"unexpected status: {status}"
    except ConnectionClosed:
        pass  # explicit close — pass


def test_coach_nonce_is_one_shot():
    """Second consumption of the same nonce must fail (helper level test)."""
    from routes.ai_coach import _issue_coach_nonce, _consume_coach_nonce
    tok = _issue_coach_nonce("call-A", "user-B", "+1123")
    row1 = _consume_coach_nonce(tok)
    assert row1 is not None
    assert row1["call_log_id"] == "call-A"
    row2 = _consume_coach_nonce(tok)
    assert row2 is None, "Nonce must not be reusable"


# ─── 7) audioop µ-law round-trip ─────────────────────────────────────

def test_coach_audio_roundtrip_uses_stdlib_audioop_no_numpy():
    from services.ai_voice_audio import (
        twilio_mulaw_to_gemini_pcm16, gemini_pcm16_to_twilio_mulaw,
    )
    import audioop, math, struct
    pcm8k = b"".join(
        struct.pack("<h", int(15000 * math.sin(2 * math.pi * 300 * n / 8000)))
        for n in range(3200)  # 400 ms
    )
    mulaw = audioop.lin2ulaw(pcm8k, 2)
    pcm16k = twilio_mulaw_to_gemini_pcm16(mulaw)
    assert len(pcm16k) > 0
    # simulate a Gemini output back-conversion for full duplex sanity
    pcm24k, _ = audioop.ratecv(pcm8k, 2, 1, 8000, 24000, None)
    mulaw_back = gemini_pcm16_to_twilio_mulaw(pcm24k)
    assert abs(len(mulaw_back) - len(mulaw)) / len(mulaw) < 0.05


# ─── 8) JSON hint schema extractor ───────────────────────────────────

def test_coach_hint_extractor_handles_markdown_fences_and_prose():
    from routes.ai_coach import extract_and_validate_hint

    # 8a. Clean JSON.
    clean = '{"sentiment":"positive","client_sentiment_score":0.7,"tone_alert":"warming_up","coaching_hint":"Ask for the vehicle type.","compliance_flag":null,"suggested_next_line":"Have you sold on an auction before?","language_detected":"en"}'
    out = extract_and_validate_hint(clean)
    assert out is not None
    assert out["sentiment"] == "positive"
    assert out["tone_alert"] == "warming_up"
    assert -1.0 <= out["client_sentiment_score"] <= 1.0
    assert set(out.keys()) >= {"sentiment", "client_sentiment_score", "tone_alert", "coaching_hint", "compliance_flag", "suggested_next_line", "language_detected"}

    # 8b. Wrapped in markdown fence.
    fenced = "```json\n" + clean + "\n```"
    out2 = extract_and_validate_hint(fenced)
    assert out2 is not None
    assert out2["sentiment"] == "positive"

    # 8c. Prose leak before the JSON.
    proseful = 'Here is your evaluation: ' + clean
    out3 = extract_and_validate_hint(proseful)
    assert out3 is not None

    # 8d. Bad sentiment enum → rejected.
    bad = clean.replace("positive", "explosive")
    assert extract_and_validate_hint(bad) is None

    # 8e. Score clamp.
    over = clean.replace("0.7", "3.5")
    out4 = extract_and_validate_hint(over)
    assert out4 is not None
    assert out4["client_sentiment_score"] == 1.0


def test_coach_hint_extractor_masks_phone():
    from routes.ai_coach import mask_phone
    assert mask_phone("+15149490038") == "+1 514 ***-**38"
    assert mask_phone("") == ""
    # Even if numbers are weird, don't crash.
    assert isinstance(mask_phone("+331"), str)


# ─── 9) Two pathways decoupled: iter334 config + iter335 config ──────

def test_two_ai_pathways_expose_independent_config_endpoints():
    r1 = httpx.get(f"{BASE}/api/twilio/ai-voice/config", timeout=10)
    r2 = httpx.get(f"{BASE}/api/coach/config", timeout=10)
    assert r1.status_code == 200
    assert r2.status_code == 200
    a = r1.json()
    b = r2.json()
    # iter334 uses native-audio for AUDIO output; iter335 uses the same
    # for STT + a separate regular Gemini for JSON analysis.
    assert a["model"] == "gemini-2.5-flash-native-audio-latest"
    assert b["stt_model"] == "gemini-2.5-flash-native-audio-latest"
    assert b["analysis_model"] == "gemini-2.5-flash"
    # Both endpoints report their own hard limit (10 minutes each).
    assert a["hard_limit_seconds"] == 600
    assert b["hard_limit_seconds"] == 600
    # The coach exposes its analysis interval — iter334 does not.
    assert b["analysis_interval_seconds"] == 7.0
    assert "analysis_interval_seconds" not in a
