"""
iter316 — Twilio Voice SDK service layer.

Centralises every Twilio Voice integration point used by the click-to-call
dialer:
  • Access-Token generation (browser Voice SDK auth)
  • TwiML XML generation for outbound calls (caller-id masking + recording)
  • Outbound-call REST helper
  • Inbound webhook signature validation
  • Recording download / local storage / Twilio-side deletion
  • Startup configuration verification (degrades gracefully when unset)

The dialer is OPTIONAL infrastructure. If any of the 6 env vars are missing
the service refuses to mint tokens / place calls, but the rest of the
platform stays fully functional (this is checked at runtime — never raises
on import).

Reused upstream:
  • emails.send_email — for any notification mails (not used directly here)
  • cloud_storage — NOT used; recordings stored locally under /uploads.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Lazy / defensive imports — twilio is installed but if the package
# tree ever changes we don't want to nuke the whole backend.
try:
    from twilio.rest import Client
    from twilio.jwt.access_token import AccessToken
    from twilio.jwt.access_token.grants import VoiceGrant
    from twilio.twiml.voice_response import VoiceResponse, Dial
    from twilio.request_validator import RequestValidator
    TWILIO_SDK_AVAILABLE = True
except Exception as e:  # noqa: BLE001
    logger.warning(f"[twilio] SDK import failed: {e}")
    TWILIO_SDK_AVAILABLE = False

# ─── Config ─────────────────────────────────────────────────────────────

TWILIO_ACCOUNT_SID   = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN    = os.environ.get("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER  = os.environ.get("TWILIO_PHONE_NUMBER")
TWILIO_TWIML_APP_SID = os.environ.get("TWILIO_TWIML_APP_SID")
TWILIO_API_KEY       = os.environ.get("TWILIO_API_KEY")
TWILIO_API_SECRET    = os.environ.get("TWILIO_API_SECRET")

# Local recording storage — never goes to a CDN / Twilio retains nothing.
RECORDINGS_DIR = Path(os.environ.get("CALL_RECORDINGS_DIR",
                                      "/app/backend/uploads/call_recordings"))


# ─── Configuration verification ─────────────────────────────────────────

def verify_twilio_config() -> dict:
    """Startup-time + endpoint-time configuration check. Returns a dict
    describing which env vars are set and whether the dialer can be used
    end-to-end. Never raises — the dialer degrades gracefully."""
    checks = {
        "TWILIO_ACCOUNT_SID":   bool(TWILIO_ACCOUNT_SID),
        "TWILIO_AUTH_TOKEN":    bool(TWILIO_AUTH_TOKEN),
        "TWILIO_PHONE_NUMBER":  bool(TWILIO_PHONE_NUMBER),
        "TWILIO_API_KEY":       bool(TWILIO_API_KEY),
        "TWILIO_API_SECRET":    bool(TWILIO_API_SECRET),
        "TWILIO_TWIML_APP_SID": bool(TWILIO_TWIML_APP_SID),
        "TWILIO_SDK_INSTALLED": TWILIO_SDK_AVAILABLE,
    }
    missing = [k for k, ok in checks.items() if not ok and k != "TWILIO_SDK_INSTALLED"]
    can_mint_tokens = all([TWILIO_API_KEY, TWILIO_API_SECRET,
                            TWILIO_TWIML_APP_SID, TWILIO_ACCOUNT_SID,
                            TWILIO_SDK_AVAILABLE])
    can_place_calls = all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
                            TWILIO_PHONE_NUMBER, TWILIO_SDK_AVAILABLE])
    fully_configured = can_mint_tokens and can_place_calls
    if not fully_configured:
        logger.warning(f"[twilio] Dialer not fully configured. Missing: {missing}. "
                       f"can_mint_tokens={can_mint_tokens}, can_place_calls={can_place_calls}")
    return {
        "configured":      fully_configured,
        "can_mint_tokens": can_mint_tokens,
        "can_place_calls": can_place_calls,
        "missing":         missing,
        "checks":          checks,
    }


def _require_can_mint() -> None:
    s = verify_twilio_config()
    if not s["can_mint_tokens"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={
            "error": "twilio_not_configured",
            "missing": s["missing"],
            "message_en": "Twilio dialer is not configured. Set TWILIO_API_KEY, "
                          "TWILIO_API_SECRET, and TWILIO_TWIML_APP_SID after creating "
                          "the TwiML App in the Twilio Console.",
            "message_fr": "Le composeur Twilio n'est pas configuré.",
        })


def _require_can_place_calls() -> None:
    s = verify_twilio_config()
    if not s["can_place_calls"]:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail={
            "error": "twilio_not_configured",
            "missing": s["missing"],
            "message_en": "Twilio outbound calling not configured.",
            "message_fr": "Les appels sortants Twilio ne sont pas configurés.",
        })


# ─── Clients ────────────────────────────────────────────────────────────

def get_twilio_client():
    _require_can_place_calls()
    return Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)


def get_request_validator() -> Optional["RequestValidator"]:
    if not (TWILIO_AUTH_TOKEN and TWILIO_SDK_AVAILABLE):
        return None
    return RequestValidator(TWILIO_AUTH_TOKEN)


# ─── Token minting (browser Voice SDK) ──────────────────────────────────

def generate_access_token(agent_identity: str, ttl_seconds: int = 3600) -> str:
    """Mint a Twilio Access Token scoped to outgoing voice only.
    Used by the browser SDK to register a Device and place calls."""
    _require_can_mint()
    token = AccessToken(
        TWILIO_ACCOUNT_SID, TWILIO_API_KEY, TWILIO_API_SECRET,
        identity=agent_identity, ttl=ttl_seconds,
    )
    token.add_grant(VoiceGrant(
        outgoing_application_sid=TWILIO_TWIML_APP_SID,
        incoming_allow=False,
    ))
    return token.to_jwt()


# ─── TwiML ──────────────────────────────────────────────────────────────

def build_outbound_twiml(client_phone_number: str,
                         status_callback: str,
                         recording_callback: str,
                         coach_stream_url: Optional[str] = None,
                         coach_nonce: Optional[str] = None) -> str:
    """Build the TwiML XML returned to Twilio's Voice Request webhook.
    Bridges agent → client, masks both numbers via caller_id, enables
    recording, registers status + recording callbacks.

    iter335 addition: if `coach_stream_url` + `coach_nonce` are provided,
    prepend a NON-TERMINAL <Start><Stream> block so the outbound audio is
    also copied to the BidVex AI Coach WebSocket for silent analysis.
    The <Dial> then proceeds normally — the caller and contractor never
    hear anything from Gemini.
    """
    if not TWILIO_SDK_AVAILABLE:
        raise RuntimeError("Twilio SDK not installed")
    # iter340 P0 — defense-in-depth: the dialed destination must never be
    # the BidVex main line itself (callerId and destination are separate).
    if TWILIO_PHONE_NUMBER and client_phone_number == TWILIO_PHONE_NUMBER:
        raise ValueError("Refusing to build TwiML that dials TWILIO_PHONE_NUMBER (self-dial guard)")
    response = VoiceResponse()

    if coach_stream_url and coach_nonce:
        start = response.start()
        stream = start.stream(url=coach_stream_url, track="both_tracks")
        stream.parameter(name="nonce", value=coach_nonce)

    dial = Dial(
        caller_id=TWILIO_PHONE_NUMBER,
        record="record-from-answer",
        recording_status_callback=recording_callback,
        recording_status_callback_method="POST",
        recording_status_callback_event="completed",
    )
    dial.number(
        client_phone_number,
        status_callback=status_callback,
        status_callback_method="POST",
        status_callback_event="initiated answered completed",
    )
    response.append(dial)
    return str(response)


# ─── Outbound call placement (REST API) ─────────────────────────────────

def place_outbound_call(client_phone_number: str,
                        agent_identity: str,
                        status_callback_url: str) -> dict:
    """Initiate the outbound leg via Twilio REST. The client receives the
    call from TWILIO_PHONE_NUMBER. Returns the Twilio call SID + status."""
    cli = get_twilio_client()
    call = cli.calls.create(
        to=client_phone_number,
        from_=TWILIO_PHONE_NUMBER,
        url=f"https://{os.environ.get('TWILIO_PUBLIC_HOST', 'bidvex.com')}/api/twilio/twiml",
        method="POST",
        status_callback=status_callback_url,
        status_callback_method="POST",
        status_callback_event=["initiated", "answered", "completed"],
        record=True,
    )
    return {"sid": call.sid, "status": call.status}


# ─── Signature validation (inbound webhooks) ────────────────────────────

def validate_webhook_signature(url: str, params: dict, signature: str) -> bool:
    """Per Twilio docs, all webhooks include X-Twilio-Signature header.
    We require this for /twiml, /call-status-callback, /recording-callback
    so SendGrid- / Twilio-impersonation is rejected at the edge."""
    validator = get_request_validator()
    if validator is None:
        # Auth token absent — fail closed.
        return False
    try:
        return validator.validate(url, params, signature)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[twilio] signature validation error: {e}")
        return False


# ─── Recording download + local storage ─────────────────────────────────

def download_recording(recording_url: str, call_log_id: str) -> Optional[str]:
    """Download the MP3 from Twilio's CDN to the local uploads dir.
    Returns the absolute path on success, None on failure."""
    if not (TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN):
        logger.warning("[twilio] Cannot download recording — auth missing")
        return None
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    target = RECORDINGS_DIR / f"{call_log_id}.mp3"
    # Twilio recording URLs return WAV by default; the .mp3 suffix forces MP3.
    if not recording_url.endswith(".mp3"):
        recording_url = recording_url + ".mp3"
    try:
        r = requests.get(recording_url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN),
                          timeout=60, stream=True)
        if r.status_code != 200:
            logger.warning(f"[twilio] download failed {r.status_code}: {recording_url}")
            return None
        with open(target, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        return str(target)
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[twilio] download_recording: {e}")
        return None


def delete_twilio_recording(recording_sid: str) -> bool:
    """Once we've persisted the MP3 locally, drop it from Twilio's storage
    so we're not billed for it and the data residency stays in our control."""
    try:
        cli = get_twilio_client()
        cli.recordings(recording_sid).delete()
        return True
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[twilio] delete_twilio_recording {recording_sid}: {e}")
        return False


# ─── Phone number validation ────────────────────────────────────────────

import re
_E164 = re.compile(r"^\+[1-9]\d{6,14}$")


def validate_e164(phone: str) -> bool:
    """Strict E.164 check: leading '+', country code 1-9, 7-15 total digits."""
    return bool(phone and _E164.match(phone.strip()))


__all__ = [
    "verify_twilio_config",
    "get_twilio_client",
    "generate_access_token",
    "build_outbound_twiml",
    "place_outbound_call",
    "validate_webhook_signature",
    "download_recording",
    "delete_twilio_recording",
    "validate_e164",
    "RECORDINGS_DIR",
    "TWILIO_PHONE_NUMBER",
]
