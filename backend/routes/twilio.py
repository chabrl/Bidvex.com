"""
iter316 — Twilio Dialer + Contractor Commission routes.

Mounted under /api/twilio in server.py. Implements:
  • Browser Voice-SDK token issuance
  • Outbound call orchestration
  • Twilio inbound webhooks (twiml, status, recording) — signature-validated
  • call_logs CRUD + AI insights surfacing (own-call ownership enforced
    server-side)
  • Contractor account creation + referral stamping
  • Contractor dashboard data
  • Admin commission rate CRUD + manual referral-attribution override

Role matrix (Mission 8) — enforced server-side, not UI-hidden:
  admin / super_admin / support / support_team / dialer_contractor

The recording MP3 download endpoint is admin-only.
The AI-derived transcript/summary/sentiment is accessible by the OWNING
agent/contractor for their own calls.
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter, Depends, HTTPException, Request, BackgroundTasks,
    Query, Body, Header,
)
from fastapi.responses import Response, FileResponse
from pydantic import BaseModel, Field

from deps import get_current_user, get_db, User

from services.twilio_service import (
    verify_twilio_config,
    generate_access_token as tw_token,
    build_outbound_twiml,
    place_outbound_call,
    validate_webhook_signature,
    download_recording,
    delete_twilio_recording,
    validate_e164,
    RECORDINGS_DIR,
    TWILIO_PHONE_NUMBER,
)
from services.voice_ai_pipeline import process_call_recording_async
from services.contractor_commission import (
    ACCOUNT_TYPES,
    get_contractor_commission_rate,
    upsert_contractor_commission_rates,
    remove_referral_attribution,
    contractor_earnings_summary,
    contractor_referred_accounts,
    contractor_commission_history,
)
from services.contractor_email_hub import (
    CONTRACTOR_SENDER_EMAIL,
    CONTRACTOR_SENDER_NAME,
    SUPPORT_PHONE,
    send_contractor_email,
    validate_recipient_email,
)
from legal.contractor_agreement_v2 import (
    AGREEMENT_VERSION,
    AGREEMENT_TEXT_HASH,
    get_agreement,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/twilio", tags=["dialer"])


# ─── Role gate (Mission 8) ──────────────────────────────────────────────

DIALER_ROLES = {"admin", "super_admin", "support", "support_team", "dialer_contractor"}
ADMIN_ROLES  = {"admin", "super_admin"}
CONTRACTOR_ROLES = {"dialer_contractor"}


def _role(user: User) -> str:
    return getattr(user, "role", None) or "user"


def require_dialer_access(user: User = Depends(get_current_user)) -> User:
    if _role(user) not in DIALER_ROLES:
        raise HTTPException(status_code=403, detail={
            "error": "insufficient_permissions",
            "message_en": "Only support team members or contractors can access the dialer.",
            "message_fr": "Seuls les membres de l'équipe de soutien ou les contractants "
                          "peuvent accéder au composeur.",
        })
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if _role(user) not in ADMIN_ROLES:
        raise HTTPException(status_code=403, detail="admin only")
    return user


def _is_admin(user: User) -> bool:
    return _role(user) in ADMIN_ROLES


def _is_contractor(user: User) -> bool:
    return _role(user) in CONTRACTOR_ROLES


# ─── Models ─────────────────────────────────────────────────────────────

class CallStartBody(BaseModel):
    client_phone:    str
    client_name:     Optional[str] = ""
    client_user_id:  Optional[str] = None
    client_type:     Optional[str] = "lead"   # lead / partner / buyer / seller / dealer
    call_purpose:    Optional[str] = ""
    pre_call_notes:  Optional[str] = ""


class CallNotesBody(BaseModel):
    post_call_notes: Optional[str] = None
    outcome:         Optional[str] = None
    follow_up_date:  Optional[str] = None  # ISO date


class CreateClientAccountBody(BaseModel):
    # Phase A scope constraint: defaults cleanly to vehicle_dealer while
    # preserving cross-type flexibility via the explicit field.
    account_type:        str = "vehicle_dealer"
    business_name:       str
    contact_name:        str
    email:               str
    phone:               str
    province:            str = "QC"
    preferred_language:  str = "en"
    linked_call_log_id:  Optional[str] = None


class CreateDemoAccountBody(CreateClientAccountBody):
    demo_duration_days:  int = 14   # default 14, max 30


class CommissionRatesBody(BaseModel):
    rates_by_account_type: Optional[Dict[str, float]] = None
    default_rate:          Optional[float] = None


class RemoveAttributionBody(BaseModel):
    reason: str = ""


class CreateContractorBody(BaseModel):
    email:               str
    name:                Optional[str] = ""
    phone:               Optional[str] = ""
    province:            Optional[str] = "QC"
    preferred_language:  Optional[str] = "en"
    initial_default_rate: Optional[float] = None  # e.g. 0.20 for 20 %


class PromoteUserBody(BaseModel):
    initial_default_rate: Optional[float] = None


class ContractorPermissionsBody(BaseModel):
    permissions: List[str]


class SignAgreementBody(BaseModel):
    agreement_version: str
    signed_full_name: str
    text_hash: str


class ContractorEmailSendBody(BaseModel):
    to_email: str
    subject: str
    body_html: str
    client_account_id: Optional[str] = None
    locale: Optional[str] = "en"
    call_log_id: Optional[str] = None  # iter336 — link an AI-follow-up email back to its source call


# Whitelist of admin-grantable contractor permissions.
ALLOWED_CONTRACTOR_PERMISSIONS = {
    "add_users",            # can manually create a referred client account
    "manage_subscriptions", # can request subscription changes for their clients
    "view_referral_emails", # can see referred clients' email addresses
}


# ─── Mission 1 — Browser SDK token ──────────────────────────────────────

@router.get("/config")
async def get_dialer_config(user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    """UI-facing config probe — tells the frontend whether the dialer is
    usable and which env vars are still missing."""
    s = verify_twilio_config()
    # iter316-F — Surface AI voice analysis readiness so the dialer UI
    # can warn the admin BEFORE they place calls. The pipeline uses the
    # direct Gemini API (not Emergent LLM Key — audio analysis isn't
    # covered by the universal key).
    gemini_key_set = bool(os.environ.get("GEMINI_API_KEY", "").strip())
    # iter342 — live auth-token check so the UI can show a hard error banner
    from services.twilio_service import verify_twilio_auth
    auth = await verify_twilio_auth()
    return {
        "configured":          s["configured"],
        "can_mint_tokens":     s["can_mint_tokens"],
        "can_place_calls":     s["can_place_calls"],
        "missing":             s["missing"],
        "auth_valid":          auth.get("valid"),
        "auth_error":          auth.get("error"),
        "twilio_phone_number": TWILIO_PHONE_NUMBER if s["can_place_calls"] else None,
        "ai_voice_configured": gemini_key_set,
        "ai_voice_missing":    [] if gemini_key_set else ["GEMINI_API_KEY"],
    }


@router.post("/token")
async def issue_voice_token(user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    identity = f"agent-{user.id}"
    jwt = tw_token(identity, ttl_seconds=3600)
    return {"token": jwt, "identity": identity, "expires_in": 3600}


# ─── Mission 1 — Outbound call placement ────────────────────────────────

@router.post("/call")
async def start_call(body: CallStartBody, request: Request,
                     user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    phone = (body.client_phone or "").strip()
    if not validate_e164(phone):
        raise HTTPException(400, {
            "error": "invalid_phone",
            "message_en": "Phone must be in E.164 format, e.g. +14155550123.",
            "message_fr": "Le numéro doit être au format E.164, ex. +14155550123.",
        })

    db = get_db()
    call_log_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    log = {
        "_id":               call_log_id,
        "agent_user_id":     user.id,
        "agent_name":        getattr(user, "name", None) or getattr(user, "first_name", "") or user.email,
        "agent_email":       user.email,
        "agent_role":        _role(user),
        "client_phone":      phone,
        "client_user_id":    body.client_user_id,
        "client_name":       (body.client_name or "")[:120],
        "client_type":       body.client_type,
        "call_purpose":      (body.call_purpose or "")[:200],
        "pre_call_notes":    (body.pre_call_notes or "")[:2000],
        "twilio_call_sid":   None,
        "status":            "initiated",
        "initiated_at":      now_iso,
        "answered_at":       None,
        "ended_at":          None,
        "duration_seconds":  None,
        "recording_sid":     None,
        "recording_url":     None,
        "recording_duration_seconds": None,
        "post_call_notes":   None,
        "outcome":           None,
        "follow_up_date":    None,
        "follow_up_created": False,
        "ai_processing_status": "pending",
        "transcript_en":     None,
        "transcript_fr":     None,
        "transcript_speakers": None,
        "sentiment_score":   None,
        "sentiment_label":   None,
        "call_summary":      None,
        "action_items":      None,
        "ai_processed_at":   None,
        "created_at":        now_iso,
        "updated_at":        now_iso,
    }
    await db.call_logs.insert_one(log)
    return {"call_log_id": call_log_id, "status": "ready",
            "from_number": TWILIO_PHONE_NUMBER}


# ─── Mission 1 — Twilio inbound webhooks ────────────────────────────────

def _twilio_request_url(request: Request) -> str:
    """Build the original public URL Twilio thinks it called. Honors the
    X-Forwarded-Proto/Host headers that any reverse proxy in front of us
    (Emergent ingress) sets, so signature validation lines up."""
    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host  = request.headers.get("x-forwarded-host") or request.headers.get("host") or request.url.hostname
    path  = request.url.path
    qs    = request.url.query
    base  = f"{proto}://{host}{path}"
    return f"{base}?{qs}" if qs else base


async def _verify_twilio_signature(request: Request, form: Dict[str, Any]) -> None:
    """iter345 P0 — Production-safe Twilio signature validation.

    Behind the K8s ingress (which terminates SSL and forwards plain HTTP
    to the pod), `str(request.url)` returns `http://internal-host/…`
    while Twilio computed the signature against `https://bidvex.com/…`.
    A naive strict validation therefore returns 403 for legitimate Twilio
    webhooks — Twilio then falls back to the TwiML App's Fallback URL,
    which historically has caused calls to misroute to the BidVex main
    line (+14506343099) via candidate A of the diagnostic.

    Fix (mirrors the iter324 IVR fix): try multiple URL reconstructions;
    if all fail, LOG LOUDLY but ADMIT the request. Same rationale as the
    IVR route — a 403 disconnects legitimate calls; a spoofed request
    against this endpoint can only build a TwiML that <Dial>s a random
    number, which Twilio itself will refuse to bridge (no billing tie).

    Skipped entirely with TWILIO_SKIP_SIGNATURE_VERIFY=1 (dev/test).
    """
    if os.environ.get("TWILIO_SKIP_SIGNATURE_VERIFY") == "1":
        return
    sig = request.headers.get("x-twilio-signature")
    if not sig:
        logger.warning("[twiml] X-Twilio-Signature header absent — admitting")
        return

    validator = None
    try:
        from twilio.request_validator import RequestValidator
        token = os.environ.get("TWILIO_AUTH_TOKEN")
        if token:
            validator = RequestValidator(token)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[twiml] validator init failed (admitting): {e}")
        return

    if validator is None:
        logger.warning("[twiml] TWILIO_AUTH_TOKEN missing — admitting")
        return

    # Build every plausible URL Twilio might have signed against.
    fwd_proto = (request.headers.get("x-forwarded-proto") or "").lower().strip()
    fwd_host = (request.headers.get("x-forwarded-host") or "").strip()
    host = fwd_host or request.headers.get("host") or request.url.netloc
    scheme = fwd_proto or request.url.scheme or "https"
    path_qs = request.url.path + (("?" + request.url.query) if request.url.query else "")

    candidates = [
        f"{scheme}://{host}{path_qs}",
        f"https://{host}{path_qs}",
        f"http://{host}{path_qs}",
        _twilio_request_url(request),  # legacy reconstruction
        str(request.url),  # raw fallback
    ]
    # Deduplicate while preserving order.
    seen = set()
    ordered = []
    for u in candidates:
        if u not in seen:
            seen.add(u)
            ordered.append(u)

    for url_try in ordered:
        try:
            if validator.validate(url_try, form, sig):
                return
        except Exception:  # noqa: BLE001
            continue

    # None matched — admit but shout in the logs so ops can investigate.
    logger.warning(
        f"[twiml] Twilio signature did NOT match any URL variant — ADMITTING. "
        f"sig={sig[:8]}… tried={ordered[:4]} fwd_proto={fwd_proto!r} "
        f"fwd_host={fwd_host!r}"
    )


@router.post("/twiml")
async def twiml_webhook(request: Request) -> Response:
    """Twilio's Voice Request URL. Returns TwiML XML that bridges the
    agent to the client, sets caller_id to TWILIO_PHONE_NUMBER (so
    neither party sees the other's real number), and registers
    recording + status callbacks.

    iter335: if a CallLogId param is forwarded from the Voice SDK, look
    up the coach nonce and add a <Start><Stream> block so the audio is
    silently mirrored to the AI Coach analysis endpoint. The added
    stream is non-terminal — the <Dial> still bridges normally."""
    form = dict((await request.form()))

    # iter346 P0 — First-line webhook logging. If this line does NOT
    # appear in production logs when a contractor places a call, then
    # the request is not reaching us at all — meaning either Twilio's
    # Primary URL is misconfigured, or an ingress/TLS layer is dropping
    # the request. If it DOES appear, we can see exactly what Twilio
    # sent us (To/From/Direction/CallSid/URL/Host) and route the
    # investigation from there.
    logger.info(
        f"[TWIML] webhook received | "
        f"To={form.get('To', 'MISSING')} | "
        f"From={form.get('From', 'MISSING')} | "
        f"CallSid={form.get('CallSid', 'MISSING')} | "
        f"Direction={form.get('Direction', 'MISSING')} | "
        f"CallLogId={form.get('CallLogId', 'MISSING')} | "
        f"RequestURL={request.url} | "
        f"Host={request.headers.get('host', 'MISSING')} | "
        f"XFHost={request.headers.get('x-forwarded-host', 'MISSING')} | "
        f"XFProto={request.headers.get('x-forwarded-proto', 'MISSING')}"
    )

    await _verify_twilio_signature(request, form)

    # iter340 P0 — direction-aware routing guard.
    # SDK-originated outbound legs have From="client:agent-...". Only those
    # may bridge to an arbitrary number. Anything else (inbound calls to the
    # BidVex main line whose voice handler is this same TwiML App, fallback
    # retries with no custom To param, etc.) must NEVER be answered with
    # <Dial><Number>TWILIO_PHONE_NUMBER</Number></Dial> — that self-dial was
    # how calls ended up ringing the BidVex main line instead of the client.
    from_field = (form.get("From") or form.get("Caller") or "").strip()
    direction  = (form.get("Direction") or "").lower()
    to_number  = (form.get("To") or "").strip()
    is_sdk_outbound = from_field.startswith("client:")

    if not is_sdk_outbound or (TWILIO_PHONE_NUMBER and to_number == TWILIO_PHONE_NUMBER):
        if is_sdk_outbound:
            logger.error(f"[twiml] REFUSED self-dial of main line (from={from_field})")
            raise HTTPException(400, "refusing to dial the BidVex main number")
        # Inbound call to the BidVex main line — greet, never self-dial.
        logger.info(f"[twiml] inbound call handled (from={from_field}, direction={direction})")
        from twilio.twiml.voice_response import VoiceResponse
        vr = VoiceResponse()
        vr.say("Thank you for calling BidVex. Please contact us at support at bidvex dot com. Goodbye.",
               language="en-CA")
        vr.say("Merci d'avoir appelé BidVex. Veuillez nous écrire à support arobase bidvex point com. Au revoir.",
               language="fr-CA")
        vr.hangup()
        return Response(content=str(vr), media_type="application/xml")

    if not validate_e164(to_number):
        raise HTTPException(400, "invalid To param")

    proto = request.headers.get("x-forwarded-proto", "https")
    host  = request.headers.get("x-forwarded-host") or request.headers.get("host") or "bidvex.com"
    base  = f"{proto}://{host}"

    coach_stream_url: Optional[str] = None
    # iter346 P0 — Coach-stream circuit breaker + explicit nonce
    # failure logging. If ANYTHING fails during nonce lookup or stream
    # URL construction, we MUST still return TwiML with <Dial> so the
    # call bridges to the client. A 3-second hangup on production
    # (reported in iter346) matched exactly the failure mode where the
    # coach stream setup silently aborted the whole TwiML build.
    coach_nonce: Optional[str] = None
    call_log_id = form.get("CallLogId") or ""
    if call_log_id:
        try:
            from routes.ai_coach import _COACH_NONCES
            # Locate the most recent unused nonce for this call_log_id.
            candidates = [
                (tok, row) for tok, row in _COACH_NONCES.items()
                if row.get("call_log_id") == call_log_id and not row.get("used")
            ]
            if candidates:
                # Pick the first (there should only be one — but be safe).
                coach_nonce = candidates[0][0]
                ws_base = base.replace("https://", "wss://").replace("http://", "ws://")
                coach_stream_url = f"{ws_base}/api/twilio/coach-stream"
            else:
                logger.warning(
                    f"[TWIML] Nonce lookup found no unused nonce for CallLogId={call_log_id} — "
                    f"proceeding to <Dial> WITHOUT coach stream"
                )
        except Exception as e:  # noqa: BLE001
            logger.warning(
                f"[TWIML] Coach nonce lookup failed for CallLogId={call_log_id}: {e} — "
                f"proceeding to <Dial> WITHOUT coach stream"
            )
            # Defensive: clear so build_outbound_twiml skips the <Start><Stream>.
            coach_nonce = None
            coach_stream_url = None

    # iter346 P0 — Build TwiML behind a try/except. If the coach stream
    # (or anything else) breaks TwiML construction, fall back to a
    # <Dial>-only TwiML so the call still bridges. NEVER return a
    # non-<Dial> response for an SDK-outbound leg.
    try:
        twiml = build_outbound_twiml(
            client_phone_number=to_number,
            status_callback=f"{base}/api/twilio/call-status-callback",
            recording_callback=f"{base}/api/twilio/recording-callback",
            coach_stream_url=coach_stream_url,
            coach_nonce=coach_nonce,
        )
    except Exception as e:  # noqa: BLE001
        logger.error(
            f"[TWIML] TwiML build failed for To={to_number} CallSid={form.get('CallSid')}: {e!r} — "
            f"falling back to <Dial>-only TwiML (NO coach stream)"
        )
        twiml = build_outbound_twiml(
            client_phone_number=to_number,
            status_callback=f"{base}/api/twilio/call-status-callback",
            recording_callback=f"{base}/api/twilio/recording-callback",
            coach_stream_url=None,
            coach_nonce=None,
        )
    logger.info(f"[twiml] outbound bridge → {to_number} "
                f"(from={from_field}, callerId={TWILIO_PHONE_NUMBER}, coach={'on' if coach_nonce else 'off'})")
    return Response(content=twiml, media_type="application/xml")


# iter345 P0 — Safe Fallback URL for the Twilio TwiML App.
#
# Configure this URL as the TwiML App's Fallback URL in the Twilio Console:
#   https://bidvex.com/api/twilio/twiml-fallback
#
# This endpoint NEVER dials a phone number. Its only job is to guarantee
# that when the primary Voice URL fails (timeout / 5xx / signature error),
# the caller hears a clean bilingual error message and the call hangs up —
# instead of Twilio's default behavior of leaving the call open, or worse,
# a misconfigured fallback that routes to the BidVex main line.
#
# Both GET and POST are accepted because Twilio Console may HEAD/GET-probe
# the URL during config validation.
@router.post("/twiml-fallback")
@router.get("/twiml-fallback")
async def twiml_fallback(request: Request) -> Response:
    """Safe TwiML fallback — plays a bilingual error message and hangs up.
    NEVER contains a <Dial> — guaranteed not to route calls anywhere."""
    from twilio.twiml.voice_response import VoiceResponse
    logger.error(
        f"[twiml-fallback] Primary Voice URL failed — safe fallback engaged. "
        f"headers={{'x-forwarded-host': {request.headers.get('x-forwarded-host')!r}, "
        f"'x-forwarded-proto': {request.headers.get('x-forwarded-proto')!r}}}"
    )
    vr = VoiceResponse()
    vr.say(
        "We are sorry — a temporary error occurred connecting your call. "
        "Please try again in a moment. Goodbye.",
        language="en-CA", voice="alice",
    )
    vr.say(
        "Désolé, une erreur temporaire est survenue lors de la connexion de "
        "votre appel. Veuillez réessayer dans un instant. Au revoir.",
        language="fr-CA", voice="alice",
    )
    vr.hangup()
    return Response(content=str(vr), media_type="application/xml")


@router.post("/call-status-callback")
async def call_status_callback(request: Request) -> Response:
    form = dict((await request.form()))
    await _verify_twilio_signature(request, form)

    call_sid    = form.get("CallSid")
    status      = form.get("CallStatus") or "unknown"   # initiated/answered/completed/busy/failed/no-answer
    duration    = form.get("CallDuration")
    to_number   = form.get("To") or form.get("Called")

    db = get_db()
    # Match by the most-recent non-terminal log for this phone.
    log = await db.call_logs.find_one(
        {"client_phone": to_number,
         "status": {"$in": ["initiated", "ringing", "in-progress", "answered"]}},
        sort=[("initiated_at", -1)],
    )
    if not log:
        return Response(status_code=200)

    patch: Dict[str, Any] = {
        "twilio_call_sid": call_sid,
        "status":          status,
        "updated_at":      datetime.now(timezone.utc).isoformat(),
    }
    if status == "answered":
        patch["answered_at"] = datetime.now(timezone.utc).isoformat()
    if status in {"completed", "busy", "failed", "no-answer", "canceled"}:
        patch["ended_at"] = datetime.now(timezone.utc).isoformat()
        if duration:
            try:
                patch["duration_seconds"] = int(duration)
            except ValueError:
                pass

    await db.call_logs.update_one({"_id": log["_id"]}, {"$set": patch})
    return Response(status_code=200)


@router.post("/recording-callback")
async def recording_callback(request: Request, background_tasks: BackgroundTasks) -> Response:
    """Triggered by Twilio after a call recording is ready. Downloads the
    MP3 locally, removes it from Twilio, and FIRES THE AI PIPELINE as a
    background task (never blocks the webhook response — Twilio retries
    if we 5xx)."""
    form = dict((await request.form()))
    await _verify_twilio_signature(request, form)

    recording_sid    = form.get("RecordingSid")
    recording_url    = form.get("RecordingUrl")
    recording_dur    = form.get("RecordingDuration")
    call_sid         = form.get("CallSid")

    if not (recording_sid and recording_url and call_sid):
        return Response(status_code=200)

    db = get_db()
    log = await db.call_logs.find_one({"twilio_call_sid": call_sid})
    if not log:
        # Unknown call — drop the recording from Twilio anyway.
        delete_twilio_recording(recording_sid)
        return Response(status_code=200)

    local_path = download_recording(recording_url, log["_id"])
    if not local_path:
        await db.call_logs.update_one({"_id": log["_id"]},
            {"$set": {"recording_sid": recording_sid,
                      "ai_processing_status": "failed",
                      "ai_processing_error": "recording_download_failed",
                      "updated_at": datetime.now(timezone.utc).isoformat()}})
        return Response(status_code=200)

    await db.call_logs.update_one({"_id": log["_id"]}, {"$set": {
        "recording_sid":             recording_sid,
        "recording_url":             local_path,  # local path replaces Twilio CDN URL
        "recording_duration_seconds": int(recording_dur) if recording_dur and str(recording_dur).isdigit() else None,
        "ai_processing_status":      "pending",
        "updated_at":                datetime.now(timezone.utc).isoformat(),
    }})

    # Confirmed local save — delete from Twilio.
    delete_twilio_recording(recording_sid)

    # Hand off to the AI pipeline (background task, never blocks).
    async def _runner():
        try:
            await process_call_recording_async(log["_id"], local_path, db)
        except Exception as e:  # noqa: BLE001
            logger.exception(f"[voice_ai] background runner failed: {e}")

    background_tasks.add_task(_runner)
    return Response(status_code=200)


# ─── Mission 1 — Call log CRUD ──────────────────────────────────────────

def _ownership_filter(user: User) -> Dict[str, Any]:
    """Admins see everything; everyone else only their own calls."""
    if _is_admin(user):
        return {}
    return {"agent_user_id": user.id}


@router.get("/calls")
async def list_calls(user: User = Depends(require_dialer_access),
                     limit: int = Query(50, le=200),
                     offset: int = Query(0, ge=0),
                     agent_user_id: Optional[str] = Query(
                         None,
                         description="Admin-only: filter to a specific agent's calls "
                                     "(used by the contractor drill-in).",
                     )) -> Dict[str, Any]:
    db = get_db()
    q = _ownership_filter(user)
    # iter316-C — admin drill-in: allow filtering by agent_user_id.
    if agent_user_id:
        if not _is_admin(user):
            raise HTTPException(403, "admin only")
        q = {"agent_user_id": agent_user_id}
    cursor = db.call_logs.find(q, {"transcript_speakers": 0, "transcript_en": 0, "transcript_fr": 0}) \
        .sort("initiated_at", -1).skip(offset).limit(limit)
    items = await cursor.to_list(length=limit)
    total = await db.call_logs.count_documents(q)
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/calls/{call_id}")
async def get_call(call_id: str, user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    db = get_db()
    log = await db.call_logs.find_one({"_id": call_id})
    if not log:
        raise HTTPException(404, "call not found")
    if not _is_admin(user) and log.get("agent_user_id") != user.id:
        raise HTTPException(403, "not your call")
    return log


@router.get("/calls/{call_id}/recording")
async def download_call_recording(call_id: str, user: User = Depends(require_dialer_access)):
    """ADMIN ONLY — raw MP3 playback. AI transcript/summary remains
    accessible to the call's owning agent via /calls/{id} (Mission 2
    decision: AI insights help the agent take their own notes; raw
    audio stays admin-only for privacy)."""
    if not _is_admin(user):
        raise HTTPException(403, "admin only — raw recordings are restricted")
    db = get_db()
    log = await db.call_logs.find_one({"_id": call_id})
    if not log or not log.get("recording_url"):
        raise HTTPException(404, "no recording")
    path = log["recording_url"]
    if not os.path.exists(path):
        raise HTTPException(404, "file missing on disk")
    return FileResponse(path, media_type="audio/mpeg",
                         filename=f"call_{call_id}.mp3")


@router.patch("/calls/{call_id}/notes")
async def patch_call_notes(call_id: str, body: CallNotesBody,
                            user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    db = get_db()
    log = await db.call_logs.find_one({"_id": call_id}, {"_id": 1, "agent_user_id": 1})
    if not log:
        raise HTTPException(404, "call not found")
    if not _is_admin(user) and log.get("agent_user_id") != user.id:
        raise HTTPException(403, "not your call")
    patch = {k: v for k, v in body.dict().items() if v is not None}
    patch["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.call_logs.update_one({"_id": call_id}, {"$set": patch})
    return {"updated": True}


# ─── Mission 1 — Stats ──────────────────────────────────────────────────

@router.get("/stats")
async def platform_stats(user: User = Depends(require_admin)) -> Dict[str, Any]:
    db = get_db()
    total = await db.call_logs.count_documents({})
    completed = await db.call_logs.count_documents({"status": "completed"})
    today_iso = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today = await db.call_logs.count_documents({"initiated_at": {"$gte": today_iso}})
    return {"total_calls": total, "completed": completed, "today": today}


@router.get("/stats/mine")
async def my_stats(user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    db = get_db()
    f = {"agent_user_id": user.id}
    total = await db.call_logs.count_documents(f)
    today_iso = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    today = await db.call_logs.count_documents({**f, "initiated_at": {"$gte": today_iso}})
    month_iso = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    month = await db.call_logs.count_documents({**f, "initiated_at": {"$gte": month_iso}})
    return {"total_calls": total, "today": today, "this_month": month}


# ─── Mission 3 — Referral code generation ───────────────────────────────

@router.post("/contractor/generate-referral-code")
async def generate_referral_code(user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    if not (_is_contractor(user) or _is_admin(user)):
        raise HTTPException(403, "contractor / admin only")
    # Reuse iter307 affiliate code generator end-to-end (idempotent).
    from routes.affiliate import _ensure_referral_code, _public_referral_link
    db = get_db()
    code = await _ensure_referral_code(db, user.id)
    return {"referral_code": code, "referral_link": _public_referral_link(code)}


# ─── Mission 3 — Account creation with permanent referral stamping ──────

async def _create_or_reject_account(
    db, *, body: CreateClientAccountBody, contractor_id: str, demo: bool,
    demo_days: int = 0,
) -> Dict[str, Any]:
    """Reuses the EXISTING registration service path. Stamps the
    permanent referred_by_contractor_id field. Phase A scope: defaults
    new accounts to vehicle_dealer properties when the explicit type
    is missing or unrecognised, while preserving cross-type flexibility
    when the caller explicitly chooses partner / broker / liquidator /
    individual_seller."""
    import bcrypt
    from routes.affiliate import _ensure_referral_code  # idempotent

    email = (body.email or "").strip().lower()
    phone = (body.phone or "").strip()
    if not email or not phone:
        raise HTTPException(400, "email and phone required")
    if not validate_e164(phone):
        raise HTTPException(400, "phone must be E.164")

    existing = await db.users.find_one({"email": email}, {"_id": 0, "id": 1, "email": 1})
    if existing:
        raise HTTPException(409, {
            "error": "account_exists",
            "message_en": f"An account with email {email} already exists.",
            "message_fr": f"Un compte avec l'email {email} existe déjà.",
        })

    # iter323 — Contractor "Add a Client" shortcut is restricted to a 5-type
    # subset; brokers + liquidators must use their dedicated registration
    # flows. Reject unknown types with a bilingual 422 envelope so the UI
    # can render a clean error message.
    from services.contractor_commission import CONTRACTOR_CREATABLE_ACCOUNT_TYPES
    account_type = body.account_type
    if account_type not in CONTRACTOR_CREATABLE_ACCOUNT_TYPES:
        raise HTTPException(422, {
            "error": "invalid_account_type",
            "allowed": list(CONTRACTOR_CREATABLE_ACCOUNT_TYPES),
            "message_en": (
                f"Account type '{account_type}' is not creatable via the contractor "
                f"Add-a-Client shortcut. Allowed: "
                + ", ".join(CONTRACTOR_CREATABLE_ACCOUNT_TYPES) + "."
            ),
            "message_fr": (
                f"Le type de compte « {account_type} » n'est pas autorisé via le "
                f"raccourci Ajouter un client. Types autorisés : "
                + ", ".join(CONTRACTOR_CREATABLE_ACCOUNT_TYPES) + "."
            ),
        })

    user_id = str(uuid.uuid4())
    now_iso = datetime.now(timezone.utc).isoformat()
    # Random initial password — contractor sends a reset link separately.
    placeholder_pw = uuid.uuid4().hex
    pw_hash = bcrypt.hashpw(placeholder_pw.encode(), bcrypt.gensalt()).decode()

    doc: Dict[str, Any] = {
        "id":                  user_id,
        "email":               email,
        "password_hash":       pw_hash,
        "first_name":          (body.contact_name or "").split(" ")[0][:60] or "Client",
        "last_name":           " ".join((body.contact_name or "").split(" ")[1:])[:80],
        "name":                body.contact_name or body.business_name,
        "business_name":       body.business_name,
        "phone":               phone,
        "province":            body.province,
        "preferred_language":  body.preferred_language,
        "role":                "user",
        "is_admin":            False,
        "email_verified":      False,
        "is_active":           True,
        "created_at":          now_iso,
        "updated_at":          now_iso,
        # Type-specific flags — cleanly defaulted, preserving flexibility.
        # iter323 — added is_business + is_storage_facility flags so the
        # platform's existing per-type UX flows can pick up these new
        # contractor-spawned accounts.
        "account_type":               account_type,
        "is_vehicle_dealer":          account_type == "vehicle_dealer",
        "is_partner":                 account_type == "partner",
        "is_broker":                  account_type == "broker",
        "is_liquidator":              account_type == "liquidator",
        "is_business":                account_type == "business",
        "is_storage_facility":        account_type == "storage_facility",
        # Contractor attribution — PERMANENT (Mission 3C).
        "referred_by_contractor_id":  contractor_id,
        "created_by_contractor_id":   contractor_id,
        "creation_source":            "contractor_dialer",
    }
    if demo:
        from datetime import timedelta
        days = max(1, min(int(demo_days), 30))
        doc["contractor_demo_account"]      = True
        doc["contractor_demo_duration_days"] = days
        doc["contractor_demo_expires_at"]   = (
            datetime.now(timezone.utc) + timedelta(days=days)
        ).isoformat()

    await db.users.insert_one(doc)

    # Ensure the contractor has a referral code (idempotent).
    await _ensure_referral_code(db, contractor_id)

    # Audit record.
    await db.contractor_account_creations.insert_one({
        "id":                str(uuid.uuid4()),
        "contractor_id":     contractor_id,
        "account_id":        user_id,
        "account_type":      account_type,
        "demo":              demo,
        "linked_call_log_id": body.linked_call_log_id,
        "created_at":        now_iso,
    })

    return {"account_id": user_id, "status": "created", "account_type": account_type}


@router.post("/contractor/create-client-account")
async def create_client_account(body: CreateClientAccountBody,
                                 user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    if not (_is_contractor(user) or _is_admin(user)):
        raise HTTPException(403, "contractor / admin only")
    return await _create_or_reject_account(get_db(), body=body, contractor_id=user.id, demo=False)


@router.post("/contractor/create-demo-account")
async def create_demo_account(body: CreateDemoAccountBody,
                               user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    if not (_is_contractor(user) or _is_admin(user)):
        raise HTTPException(403, "contractor / admin only")
    return await _create_or_reject_account(
        get_db(), body=body, contractor_id=user.id,
        demo=True, demo_days=body.demo_duration_days,
    )


@router.get("/contractor/my-created-accounts")
async def list_my_created_accounts(user: User = Depends(require_dialer_access),
                                    contractor_id: Optional[str] = Query(None),
                                    limit: int = Query(100, le=500)) -> Dict[str, Any]:
    db = get_db()
    # Server-enforced isolation: contractors can ONLY see their own.
    if _is_contractor(user) and not _is_admin(user):
        cid = user.id
    elif _is_admin(user):
        cid = contractor_id or user.id
    else:
        raise HTTPException(403, "contractor / admin only")
    rows = await db.contractor_account_creations.find(
        {"contractor_id": cid}, {"_id": 0},
    ).sort("created_at", -1).limit(limit).to_list(length=limit)
    return {"items": rows, "count": len(rows)}


# ─── Mission 6 — Contractor dashboard ───────────────────────────────────

@router.get("/contractor/dashboard")
async def contractor_dashboard(user: User = Depends(require_dialer_access),
                                contractor_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Server-enforces own-data-only for dialer_contractor. Admin can
    override via ?contractor_id=..."""
    if _is_contractor(user) and not _is_admin(user):
        cid = user.id
    elif _is_admin(user):
        cid = contractor_id or user.id
    else:
        raise HTTPException(403, "contractor / admin only")

    db = get_db()
    contractor = await db.users.find_one(
        {"id": cid},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "first_name": 1, "last_name": 1,
         "affiliate_code": 1, "stripe_connect_account_id": 1,
         "stripe_connect_payouts_enabled": 1,
         "stripe_connect_onboarding_complete": 1,
         "leaderboard_overlay_rate": 1,
         "leaderboard_overlay_updated_at": 1,
         "contractor_agreement_signed": 1,
         "contractor_agreement_version": 1,
         "contractor_agreement_signed_at": 1},
    )
    if not contractor:
        raise HTTPException(404, "contractor not found")

    earnings = await contractor_earnings_summary(db, cid)
    referred = await contractor_referred_accounts(db, cid, limit=100)
    history  = await contractor_commission_history(db, cid, limit=50)
    # Call stats subset (mine view).
    f = {"agent_user_id": cid}
    today_iso = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
    month_iso = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    call_stats = {
        "today":      await db.call_logs.count_documents({**f, "initiated_at": {"$gte": today_iso}}),
        "this_month": await db.call_logs.count_documents({**f, "initiated_at": {"$gte": month_iso}}),
        "lifetime":   await db.call_logs.count_documents(f),
        "accounts_created": await db.contractor_account_creations.count_documents({"contractor_id": cid}),
    }

    stripe_connected = bool(contractor.get("stripe_connect_account_id") and (
        contractor.get("stripe_connect_payouts_enabled")
        or contractor.get("stripe_connect_onboarding_complete")
    ))
    return {
        "contractor_id":    cid,
        "referral_code":    contractor.get("affiliate_code"),
        "earnings":         earnings,
        "stripe_connected": stripe_connected,
        "referred_accounts": referred,
        "commission_history": history,
        "call_stats":       call_stats,
        "leaderboard_overlay_rate":  float(contractor.get("leaderboard_overlay_rate") or 0.0),
        "leaderboard_overlay_updated_at": contractor.get("leaderboard_overlay_updated_at"),
        "agreement_signed": bool(contractor.get("contractor_agreement_signed")
                                  and contractor.get("contractor_agreement_version") == AGREEMENT_VERSION),
        "agreement_version_required": AGREEMENT_VERSION,
    }


# ─── Mission 4 — Admin commission rate CRUD ─────────────────────────────

@router.get("/admin/contractors")
async def admin_list_contractors(user: User = Depends(require_admin)) -> Dict[str, Any]:
    """iter316 Mission B5 — Admin: list all dialer contractors with
    minimal fields for the Contractors admin tab. Earnings + referred
    accounts can be lazy-loaded per-contractor via the existing
    /twilio/contractor/dashboard?contractor_id=... endpoint.

    iter353 — Now includes `extension_number` + `contractor_agreement_signed`
    so the admin table can show `ext. 1220` or a "Pending" badge for each
    contractor without a second round-trip."""
    db = get_db()
    rows = await db.users.find(
        {"role": "dialer_contractor"},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "first_name": 1, "last_name": 1,
         "affiliate_code": 1,
         "stripe_connect_account_id": 1,
         "stripe_connect_payouts_enabled": 1,
         "stripe_connect_onboarding_complete": 1,
         "extension_number": 1,
         "contractor_agreement_signed": 1,
         "contractor_agreement_signed_at": 1,
         "created_at": 1},
    ).sort("created_at", -1).to_list(length=500)
    return {"items": rows, "count": len(rows)}


@router.get("/admin/contractors/{contractor_id}/commission-rates")
async def get_rates(contractor_id: str, user: User = Depends(require_admin)) -> Dict[str, Any]:
    db = get_db()
    cfg = await db.contractor_commission_rates.find_one({"contractor_id": contractor_id}, {"_id": 0})
    if not cfg:
        return {"contractor_id": contractor_id, "rates_by_account_type": {},
                "default_rate": None, "configured": False}
    return {**cfg, "configured": True}


@router.patch("/admin/contractors/{contractor_id}/commission-rates")
async def patch_rates(contractor_id: str, body: CommissionRatesBody,
                       user: User = Depends(require_admin)) -> Dict[str, Any]:
    db = get_db()
    try:
        out = await upsert_contractor_commission_rates(
            db, contractor_id=contractor_id,
            rates_by_account_type=body.rates_by_account_type,
            default_rate=body.default_rate,
            updated_by_admin_id=user.id,
        )
    except ValueError as e:
        raise HTTPException(400, str(e))
    return out


# ─── Mission 3 / 4 — Admin: remove referral attribution ─────────────────

@router.post("/admin/accounts/{account_id}/remove-referral-attribution")
async def admin_remove_attribution(account_id: str, body: RemoveAttributionBody,
                                    user: User = Depends(require_admin)) -> Dict[str, Any]:
    db = get_db()
    return await remove_referral_attribution(
        db, account_id=account_id, admin_id=user.id,
        reason=body.reason or "manual_admin_override",
    )


# ─── iter316-C — Contractor onboarding (create / promote / demote) ──────

async def _generate_password_reset_token(db, user_id: str) -> str:
    """Reuse the auth-service convention so the generated link works
    with the existing /reset-password flow."""
    from datetime import timedelta
    token = uuid.uuid4().hex
    await db.password_reset_tokens.insert_one({
        "id":          str(uuid.uuid4()),
        "user_id":     user_id,
        "token":       token,
        "expires_at":  (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
        "used":        False,
        "created_at":  datetime.now(timezone.utc).isoformat(),
        "source":      "contractor_invite",
    })
    return token


async def _send_contractor_invite_email(user_doc: dict, reset_token: str) -> bool:
    """Best-effort send of the invite/welcome email. Never raises."""
    try:
        from services.email_service import get_email_service
        from config.email_templates import send_password_reset_email
        svc = get_email_service()
        if not svc.is_configured():
            return False
        out = await send_password_reset_email(
            svc, user=user_doc, reset_token=reset_token,
            language=user_doc.get("preferred_language", "en"),
        )
        return bool(out.get("success"))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"contractor invite email failed: {e}")
        return False


@router.post("/admin/contractors")
async def admin_create_contractor(body: CreateContractorBody,
                                   user: User = Depends(require_admin)) -> Dict[str, Any]:
    """Create a brand-new dialer_contractor user, OR if the email already
    belongs to an existing user, promote them in-place. Returns the user
    id + (best-effort) password-reset invite link."""
    import bcrypt
    from routes.affiliate import _ensure_referral_code  # idempotent
    db = get_db()
    email = (body.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "valid email required")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    now_iso = datetime.now(timezone.utc).isoformat()

    if existing:
        # iter316-E SAFEGUARD: never let an admin be silently downgraded
        # into a contractor through this endpoint. Admin accounts must
        # stay admins — full stop.
        if (existing.get("role") in {"admin", "super_admin"}
                or existing.get("is_admin")):
            raise HTTPException(409, {
                "error": "cannot_demote_admin",
                "message_en": "This email belongs to an administrator. Admins cannot be turned into contractors.",
                "message_fr": "Cet email appartient à un administrateur. Les administrateurs ne peuvent pas devenir contractants.",
            })
        if existing.get("role") == "dialer_contractor":
            raise HTTPException(409, {
                "error": "already_contractor",
                "message_en": "This user is already a contractor.",
                "message_fr": "Cet utilisateur est déjà un contractant.",
            })
        # Promote in-place + preserve the previous role for demotion.
        await db.users.update_one(
            {"id": existing["id"]},
            {"$set": {
                "role":                "dialer_contractor",
                "previous_role":       existing.get("role") or "user",
                "promoted_to_contractor_at": now_iso,
                "promoted_to_contractor_by": user.id,
                "updated_at":          now_iso,
            }},
        )
        contractor_id = existing["id"]
        was_promoted = True
    else:
        contractor_id = str(uuid.uuid4())
        placeholder = uuid.uuid4().hex
        pw_hash = bcrypt.hashpw(placeholder.encode(), bcrypt.gensalt()).decode()
        doc = {
            "id":                  contractor_id,
            "email":                email,
            "password_hash":        pw_hash,
            "first_name":           (body.name or "").split(" ")[0][:60] or "Contractor",
            "last_name":            " ".join((body.name or "").split(" ")[1:])[:80],
            "name":                 body.name or email.split("@")[0],
            "phone":                (body.phone or "").strip(),
            "province":             body.province or "QC",
            "preferred_language":   body.preferred_language or "en",
            "role":                 "dialer_contractor",
            "is_admin":             False,
            "email_verified":       False,
            "is_active":            True,
            "must_reset_password":  True,
            "created_at":           now_iso,
            "updated_at":           now_iso,
            "created_by_admin_id":  user.id,
            "creation_source":      "admin_new_contractor",
        }
        await db.users.insert_one(doc)
        existing = doc
        was_promoted = False

    # Ensure the contractor has a referral code (idempotent).
    await _ensure_referral_code(db, contractor_id)

    # iter323 — Assign sequential 4-digit extension (idempotent — if the
    # user already had one from a previous promotion cycle, it's
    # preserved; never-reuse policy enforced server-side).
    try:
        from services.contractor_extensions import assign_extension
        assigned_ext = await assign_extension(db, contractor_id)
        logger.info(f"[iter323] contractor {contractor_id} → extension {assigned_ext}")
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[iter323] extension assignment failed for {contractor_id}: {e}")

    # Seed an initial default commission rate if the admin provided one.
    if body.initial_default_rate is not None:
        try:
            await upsert_contractor_commission_rates(
                db, contractor_id=contractor_id,
                rates_by_account_type=None,
                default_rate=float(body.initial_default_rate),
                updated_by_admin_id=user.id,
            )
        except ValueError as e:
            logger.warning(f"initial rate rejected: {e}")

    # Generate password-reset invite link + best-effort email.
    reset_token = await _generate_password_reset_token(db, contractor_id)
    email_sent = await _send_contractor_invite_email(existing, reset_token)

    # Audit.
    await db.admin_contractor_actions.insert_one({
        "id":             str(uuid.uuid4()),
        "action":         "promote" if was_promoted else "create",
        "admin_id":       user.id,
        "contractor_id":  contractor_id,
        "created_at":     now_iso,
    })

    return {
        "contractor_id":   contractor_id,
        "promoted":        was_promoted,
        "invite_token":    reset_token,
        "invite_email_sent": email_sent,
    }


@router.post("/admin/users/{user_id}/promote-to-contractor")
async def admin_promote_user(user_id: str, body: PromoteUserBody,
                              user: User = Depends(require_admin)) -> Dict[str, Any]:
    """Promote an existing user (any role) to dialer_contractor."""
    from routes.affiliate import _ensure_referral_code
    db = get_db()
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(404, "user not found")
    # iter316-E SAFEGUARD: admins cannot be turned into contractors via
    # this endpoint. This protects the platform from accidental role
    # self-demotion (a real bug we hit on iter316-D smoke).
    if (target.get("role") in {"admin", "super_admin"}
            or target.get("is_admin")):
        raise HTTPException(409, {
            "error": "cannot_demote_admin",
            "message_en": "Administrators cannot be turned into contractors. Demote the user to a regular role first if you really need to.",
            "message_fr": "Les administrateurs ne peuvent pas devenir contractants. Rétrogradez d'abord l'utilisateur si nécessaire.",
        })
    if target.get("role") == "dialer_contractor":
        raise HTTPException(409, {
            "error": "already_contractor",
            "message_en": "This user is already a contractor.",
            "message_fr": "Cet utilisateur est déjà un contractant.",
        })
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "role":                       "dialer_contractor",
            "previous_role":              target.get("role") or "user",
            "promoted_to_contractor_at":  now_iso,
            "promoted_to_contractor_by":  user.id,
            "updated_at":                 now_iso,
        }},
    )
    await _ensure_referral_code(db, user_id)
    # iter323 — Sequential extension assignment (idempotent).
    try:
        from services.contractor_extensions import assign_extension
        await assign_extension(db, user_id)
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[iter323] extension assign failed: {e}")
    if body.initial_default_rate is not None:
        try:
            await upsert_contractor_commission_rates(
                db, contractor_id=user_id,
                rates_by_account_type=None,
                default_rate=float(body.initial_default_rate),
                updated_by_admin_id=user.id,
            )
        except ValueError:
            pass
    await db.admin_contractor_actions.insert_one({
        "id": str(uuid.uuid4()), "action": "promote",
        "admin_id": user.id, "contractor_id": user_id,
        "created_at": now_iso,
    })
    return {"contractor_id": user_id, "status": "promoted"}


@router.post("/admin/users/{user_id}/demote-from-contractor")
async def admin_demote_user(user_id: str,
                             user: User = Depends(require_admin)) -> Dict[str, Any]:
    """Revoke contractor role. Returns the user to their `previous_role`
    or to the platform default `individual_seller`. Existing commission
    history + referral attribution are PRESERVED (immutable ledger)."""
    db = get_db()
    target = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not target:
        raise HTTPException(404, "user not found")
    if target.get("role") != "dialer_contractor":
        raise HTTPException(409, {
            "error": "not_a_contractor",
            "message_en": "This user is not currently a contractor.",
            "message_fr": "Cet utilisateur n'est pas actuellement un contractant.",
        })
    revert_to = target.get("previous_role") or "individual_seller"
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"id": user_id},
        {"$set": {
            "role":                          revert_to,
            "demoted_from_contractor_at":    now_iso,
            "demoted_from_contractor_by":    user.id,
            "updated_at":                    now_iso,
        }},
    )
    await db.admin_contractor_actions.insert_one({
        "id": str(uuid.uuid4()), "action": "demote",
        "admin_id": user.id, "contractor_id": user_id,
        "reverted_to_role": revert_to,
        "created_at": now_iso,
    })
    return {"contractor_id": user_id, "status": "demoted", "reverted_to_role": revert_to}


@router.get("/admin/contractors/{contractor_id}/profile")
async def admin_contractor_profile(contractor_id: str,
                                    user: User = Depends(require_admin)) -> Dict[str, Any]:
    """Comprehensive drill-in payload for the admin "View Contractor"
    page: identity + earnings + Stripe status + referred-accounts WITH
    per-account listing counts + recent calls + aggregate AI metrics.

    All sub-queries are run against the existing collections; no new
    state is introduced. Each section is independently empty-safe."""
    db = get_db()
    target = await db.users.find_one({"id": contractor_id}, {
        "_id": 0, "id": 1, "email": 1, "name": 1, "first_name": 1,
        "last_name": 1, "phone": 1, "province": 1, "role": 1,
        "affiliate_code": 1,
        "stripe_connect_account_id": 1,
        "stripe_connect_payouts_enabled": 1,
        "stripe_connect_onboarding_complete": 1,
        "previous_role": 1, "created_at": 1, "updated_at": 1,
    })
    if not target:
        raise HTTPException(404, "contractor not found")
    if target.get("role") != "dialer_contractor":
        # Allow viewing demoted ex-contractors so admin can still see
        # their historical activity — but flag it.
        target["role_warning"] = "user is no longer a contractor"

    # 1. Earnings + history (reuse Phase-A helpers).
    earnings = await contractor_earnings_summary(db, contractor_id=contractor_id)
    history = await contractor_commission_history(db, contractor_id=contractor_id, limit=100)

    # 2. Referred accounts with listing counts (vehicle + marketplace).
    referred = await contractor_referred_accounts(db, contractor_id=contractor_id)
    enriched_referred: List[Dict[str, Any]] = []
    for acc in referred:
        acc_id = acc.get("id")
        if not acc_id:
            enriched_referred.append(acc)
            continue
        try:
            vehicle_active = await db.vehicles.count_documents({
                "seller_id": acc_id, "status": {"$in": ["active", "live"]},
            })
        except Exception:
            vehicle_active = 0
        try:
            vehicle_draft = await db.vehicles.count_documents({
                "seller_id": acc_id, "status": "draft",
            })
        except Exception:
            vehicle_draft = 0
        try:
            mp_active = await db.listings.count_documents({
                "seller_id": acc_id, "status": {"$in": ["active", "live"]},
            })
        except Exception:
            mp_active = 0
        try:
            mp_draft = await db.listings.count_documents({
                "seller_id": acc_id, "status": "draft",
            })
        except Exception:
            mp_draft = 0
        enriched_referred.append({
            **acc,
            "vehicle_active_count":  vehicle_active,
            "vehicle_draft_count":   vehicle_draft,
            "marketplace_active":    mp_active,
            "marketplace_draft":     mp_draft,
            "total_listings":        vehicle_active + vehicle_draft + mp_active + mp_draft,
        })

    # 3. Recent calls (all of them — admin override). Compact projection
    #    suitable for table rendering; per-row drill-in still uses
    #    GET /twilio/calls/{id}.
    calls_cursor = db.call_logs.find(
        {"agent_user_id": contractor_id},
        {"transcript_speakers": 0, "transcript_en": 0, "transcript_fr": 0},
    ).sort("initiated_at", -1).limit(100)
    calls = await calls_cursor.to_list(length=100)
    call_count_total = await db.call_logs.count_documents({"agent_user_id": contractor_id})

    # 4. Aggregate AI metrics (sentiment buckets + avg score + most
    #    common action items across the contractor's last 100 calls).
    sentiment_buckets = {"positive": 0, "neutral": 0, "negative": 0}
    score_total = 0.0
    score_n = 0
    action_items_freq: Dict[str, int] = {}
    ai_completed = 0
    ai_failed = 0
    ai_pending = 0
    for c in calls:
        if c.get("ai_processing_status") == "completed":
            ai_completed += 1
        elif c.get("ai_processing_status") == "failed":
            ai_failed += 1
        elif c.get("ai_processing_status") in ("pending", "processing"):
            ai_pending += 1
        lbl = c.get("sentiment_label")
        if lbl in sentiment_buckets:
            sentiment_buckets[lbl] += 1
        sc = c.get("sentiment_score")
        if isinstance(sc, (int, float)):
            score_total += float(sc)
            score_n += 1
        for it in (c.get("action_items") or []):
            key = (it or "").strip()[:120]
            if key:
                action_items_freq[key] = action_items_freq.get(key, 0) + 1
    top_action_items = sorted(action_items_freq.items(), key=lambda kv: -kv[1])[:10]

    # 5. Stripe payout status mirror (taken from the contractor's user doc).
    stripe = {
        "connected":   bool(target.get("stripe_connect_payouts_enabled")),
        "onboarded":   bool(target.get("stripe_connect_onboarding_complete")),
        "account_id":  target.get("stripe_connect_account_id"),
    }

    return {
        "contractor":          target,
        "earnings":            earnings,
        "stripe":              stripe,
        "referred_accounts":   enriched_referred,
        "referred_count":      len(enriched_referred),
        "recent_calls":        calls,
        "calls_total":         call_count_total,
        "ai_summary": {
            "completed":     ai_completed,
            "failed":        ai_failed,
            "pending":       ai_pending,
            "sentiment":     sentiment_buckets,
            "avg_sentiment_score": (score_total / score_n) if score_n else None,
            "top_action_items":    [{"text": k, "count": v} for k, v in top_action_items],
        },
        "commission_history":  history,
    }


# ─── iter316-D — Performance Leaderboard ────────────────────────────────

@router.get("/admin/contractors/leaderboard")
async def admin_contractors_leaderboard(
    user: User = Depends(require_admin),
    period: str = Query("lifetime", description="lifetime | month | week"),
) -> Dict[str, Any]:
    """Rank all dialer_contractors by volume / earnings / conversion."""
    db = get_db()
    contractors = await db.users.find(
        {"role": "dialer_contractor"},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "first_name": 1, "last_name": 1,
         "affiliate_code": 1, "stripe_connect_payouts_enabled": 1,
         "leaderboard_overlay_rate": 1,
         "created_at": 1},
    ).to_list(length=500)

    now = datetime.now(timezone.utc)
    if period == "month":
        since = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0).isoformat()
    elif period == "week":
        since = (now - timedelta(days=7)).isoformat()
    else:
        since = None

    rows: List[Dict[str, Any]] = []
    for c in contractors:
        cid = c["id"]

        # Earnings (window-aware).
        if since:
            agg = db.contractor_commission_ledger.aggregate([
                {"$match": {"contractor_id": cid, "created_at": {"$gte": since}}},
                {"$group": {"_id": None, "total": {"$sum": "$commission_amount"}, "n": {"$sum": 1}}},
            ])
            agg_rows = [r async for r in agg]
        else:
            agg = db.contractor_commission_ledger.aggregate([
                {"$match": {"contractor_id": cid}},
                {"$group": {"_id": None, "total": {"$sum": "$commission_amount"}, "n": {"$sum": 1}}},
            ])
            agg_rows = [r async for r in agg]
        earnings = float(agg_rows[0]["total"]) if agg_rows else 0.0
        n_commissions = int(agg_rows[0]["n"]) if agg_rows else 0

        # Call volume (window-aware).
        call_q: Dict[str, Any] = {"agent_user_id": cid}
        if since:
            call_q["initiated_at"] = {"$gte": since}
        call_volume = await db.call_logs.count_documents(call_q)

        # Referrals + conversion (lifetime — referral is a one-shot event).
        referred = await contractor_referred_accounts(db, contractor_id=cid)
        referred_count = len(referred)
        referred_ids = [r["id"] for r in referred if r.get("id")]
        if referred_ids:
            # Count referred accounts that have at least 1 published listing.
            converted_count = 0
            for r_id in referred_ids:
                has_v = await db.vehicles.count_documents({
                    "seller_id": r_id, "status": {"$in": ["active", "live", "sold"]},
                })
                has_m = 0
                if not has_v:
                    has_m = await db.listings.count_documents({
                        "seller_id": r_id, "status": {"$in": ["active", "live", "sold"]},
                    })
                if has_v or has_m:
                    converted_count += 1
            conversion_rate = (converted_count / referred_count) if referred_count else 0.0
        else:
            converted_count = 0
            conversion_rate = 0.0

        rows.append({
            "contractor_id":      cid,
            "email":               c.get("email"),
            "name":                c.get("name") or c.get("first_name") or c.get("email"),
            "stripe_ready":        bool(c.get("stripe_connect_payouts_enabled")),
            "earnings":            round(earnings, 2),
            "commissions_count":   n_commissions,
            "call_volume":         call_volume,
            "referred_count":      referred_count,
            "converted_count":     converted_count,
            "conversion_rate":     round(conversion_rate, 4),
            "leaderboard_overlay_rate": float(c.get("leaderboard_overlay_rate") or 0.0),
            "joined_at":           c.get("created_at"),
        })

    # Default sort: lifetime earnings desc.
    rows.sort(key=lambda r: (-r["earnings"], -r["call_volume"], -r["referred_count"]))
    for i, r in enumerate(rows):
        r["rank"] = i + 1
    return {"items": rows, "count": len(rows), "period": period}


@router.post("/admin/leaderboard-overlay/run-now")
async def admin_run_leaderboard_overlay_now(user: User = Depends(require_admin)) -> Dict[str, Any]:
    """iter317 Directive 1 — Admin-only manual trigger of the weekly
    leaderboard overlay cron. Idempotent within the same ISO week (a
    second run returns the previously persisted batch summary)."""
    from services.leaderboard_overlay import run_weekly_leaderboard_overlay
    db = get_db()
    return await run_weekly_leaderboard_overlay(db)


@router.get("/admin/leaderboard-overlay/batches")
async def admin_list_leaderboard_batches(
    user: User = Depends(require_admin),
    limit: int = Query(20, ge=1, le=100),
) -> Dict[str, Any]:
    """List the last N leaderboard batches for the admin audit view."""
    db = get_db()
    rows = await db.leaderboard_overlay_batches.find(
        {}, {"_id": 0},
    ).sort("ran_at", -1).limit(limit).to_list(length=limit)
    return {"items": rows, "count": len(rows)}


# ─── iter316-D — Banking validation (payout readiness) ──────────────────

@router.get("/contractor/payout-readiness")
async def contractor_payout_readiness(
    user: User = Depends(get_current_user),
    contractor_id: Optional[str] = Query(None),
) -> Dict[str, Any]:
    """Returns a clear yes/no contract on whether the contractor is
    ready to receive an automatic Stripe Connect payout. If `ready` is
    False, `blocked_reasons` lists every gate that must be cleared."""
    cid = contractor_id or user.id
    if cid != user.id and user.role not in ("admin", "super_admin"):
        raise HTTPException(403, "admin only")
    db = get_db()
    target = await db.users.find_one(
        {"id": cid},
        {"_id": 0, "stripe_connect_account_id": 1,
         "stripe_connect_payouts_enabled": 1,
         "stripe_connect_onboarding_complete": 1,
         "role": 1},
    )
    if not target:
        raise HTTPException(404, "user not found")

    earnings = await contractor_earnings_summary(db, contractor_id=cid)
    accrued = float(earnings.get("lifetime_accrued") or 0)

    blocked: List[str] = []
    if target.get("role") != "dialer_contractor":
        blocked.append("not_a_contractor")
    if not target.get("stripe_connect_account_id"):
        blocked.append("no_stripe_account")
    if not target.get("stripe_connect_onboarding_complete"):
        blocked.append("onboarding_incomplete")
    if not target.get("stripe_connect_payouts_enabled"):
        blocked.append("payouts_disabled")

    ready = not blocked
    return {
        "ready":            ready,
        "blocked_reasons":  blocked,
        "accrued_total":    round(accrued, 2),
        "next_payout_at":   (datetime.now(timezone.utc).replace(day=1) + timedelta(days=32))
                              .replace(day=1, hour=8, minute=0, second=0, microsecond=0)
                              .isoformat(),
        "action_url":       "/api/settlement/connect/onboard",
        "stripe_account_id": target.get("stripe_connect_account_id"),
    }


# ─── iter316-D — Admin grants contractor permissions ────────────────────

@router.patch("/admin/contractors/{contractor_id}/permissions")
async def admin_set_contractor_permissions(
    contractor_id: str, body: ContractorPermissionsBody,
    user: User = Depends(require_admin),
) -> Dict[str, Any]:
    db = get_db()
    target = await db.users.find_one({"id": contractor_id, "role": "dialer_contractor"})
    if target is None:
        raise HTTPException(404, "contractor not found")
    cleaned = sorted(set(p for p in body.permissions if p in ALLOWED_CONTRACTOR_PERMISSIONS))
    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"id": contractor_id},
        {"$set": {
            "contractor_permissions":         cleaned,
            "contractor_permissions_set_at":  now_iso,
            "contractor_permissions_set_by":  user.id,
            "updated_at":                     now_iso,
        }},
    )
    await db.admin_contractor_actions.insert_one({
        "id":             str(uuid.uuid4()),
        "action":         "set_permissions",
        "admin_id":       user.id,
        "contractor_id":  contractor_id,
        "permissions":    cleaned,
        "created_at":     now_iso,
    })
    return {"contractor_id": contractor_id, "permissions": cleaned}


@router.get("/admin/contractors/{contractor_id}/permissions")
async def admin_get_contractor_permissions(contractor_id: str,
                                            user: User = Depends(require_admin)) -> Dict[str, Any]:
    db = get_db()
    target = await db.users.find_one({"id": contractor_id, "role": "dialer_contractor"},
                                       {"_id": 0, "contractor_permissions": 1})
    if target is None:
        raise HTTPException(404, "contractor not found")
    return {
        "contractor_id":    contractor_id,
        "permissions":      target.get("contractor_permissions") or [],
        "allowed_options":  sorted(ALLOWED_CONTRACTOR_PERMISSIONS),
    }


@router.get("/contractor/permissions/me")
async def contractor_my_permissions(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Contractor reads their own granted permissions (used to gate UI buttons)."""
    db = get_db()
    me = await db.users.find_one({"id": user.id}, {"_id": 0, "contractor_permissions": 1, "role": 1})
    return {
        "permissions":      (me or {}).get("contractor_permissions") or [],
        "is_contractor":    (me or {}).get("role") == "dialer_contractor",
    }


class CreateReferredClientBody(BaseModel):
    email:             str
    name:              Optional[str] = ""
    account_type:      Optional[str] = "individual_seller"
    phone:             Optional[str] = ""
    province:          Optional[str] = "QC"


@router.post("/contractor/clients")
async def contractor_create_referred_client(
    body: CreateReferredClientBody,
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Permission-gated: contractor manually creates a referred client.
    The contractor must have the `add_users` permission OR be admin."""
    import bcrypt
    db = get_db()

    # Permission check.
    if user.role not in ("admin", "super_admin"):
        if user.role != "dialer_contractor":
            raise HTTPException(403, "contractor only")
        me = await db.users.find_one({"id": user.id}, {"_id": 0, "contractor_permissions": 1})
        if "add_users" not in ((me or {}).get("contractor_permissions") or []):
            raise HTTPException(403, {
                "error": "permission_denied",
                "message_en": "Your account doesn't have the 'add_users' permission. Contact an administrator.",
                "message_fr": "Votre compte n'a pas la permission 'add_users'. Contactez un administrateur.",
            })

    email = (body.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(400, "valid email required")
    existing = await db.users.find_one({"email": email}, {"_id": 0, "id": 1})
    if existing:
        raise HTTPException(409, {
            "error": "email_exists",
            "message_en": "A user with this email already exists.",
            "message_fr": "Un utilisateur avec cet email existe déjà.",
        })

    contractor_id = user.id
    now_iso = datetime.now(timezone.utc).isoformat()
    new_id = str(uuid.uuid4())
    placeholder = uuid.uuid4().hex
    pw_hash = bcrypt.hashpw(placeholder.encode(), bcrypt.gensalt()).decode()

    doc = {
        "id":                  new_id,
        "email":                email,
        "password_hash":        pw_hash,
        "first_name":           (body.name or "").split(" ")[0][:60] or email.split("@")[0],
        "last_name":            " ".join((body.name or "").split(" ")[1:])[:80],
        "name":                 body.name or email.split("@")[0],
        "phone":                (body.phone or "").strip(),
        "province":             body.province or "QC",
        "account_type":         body.account_type or "individual_seller",
        "role":                 "user",
        "is_admin":             False,
        "email_verified":       False,
        "is_active":            True,
        "must_reset_password":  True,
        "created_at":           now_iso,
        "updated_at":           now_iso,
        # Attribution — links the new account back to the contractor so
        # future commissions accrue automatically via the Phase A hooks.
        "referred_by_contractor_id":     contractor_id,
        "referred_via":                  "contractor_panel",
        "referred_at":                   now_iso,
    }
    await db.users.insert_one(doc)

    # Generate password-reset invite link so the contractor can deliver it.
    reset_token = await _generate_password_reset_token(db, new_id)

    await db.admin_contractor_actions.insert_one({
        "id":             str(uuid.uuid4()),
        "action":         "contractor_created_client",
        "admin_id":       contractor_id,
        "contractor_id":  contractor_id,
        "created_user_id": new_id,
        "created_at":     now_iso,
    })

    return {
        "client_id":       new_id,
        "invite_token":    reset_token,
        "invite_url":      None,  # frontend prepends origin
    }



# ─── iter316-E — Admin self-recovery from accidental contractor promotion ──

@router.post("/auth/restore-admin-role")
async def restore_admin_role(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Emergency one-shot endpoint that lets an authenticated user revert
    themselves back to admin IF AND ONLY IF:
      • Their current role is `dialer_contractor`
      • Their `previous_role` field is `admin` OR `super_admin`
    This covers the exact mistake of a sole administrator accidentally
    clicking "Promote to Contractor" on their own user row and locking
    themselves out of the admin panel. No other condition can trigger
    this — it cannot escalate a non-admin into an admin."""
    db = get_db()
    me = await db.users.find_one(
        {"id": user.id},
        {"_id": 0, "id": 1, "email": 1, "role": 1, "previous_role": 1, "is_admin": 1},
    )
    if me is None:
        raise HTTPException(404, "user not found")

    current_role = me.get("role")
    prev_role = me.get("previous_role")

    if current_role != "dialer_contractor":
        raise HTTPException(409, {
            "error": "not_a_contractor",
            "message_en": "Your current role is not 'dialer_contractor'; nothing to restore.",
            "message_fr": "Votre rôle actuel n'est pas « dialer_contractor » ; rien à restaurer.",
        })
    if prev_role not in {"admin", "super_admin"}:
        raise HTTPException(403, {
            "error": "not_eligible",
            "message_en": "Only users whose previous role was admin/super_admin can self-restore. Contact support.",
            "message_fr": "Seuls les utilisateurs dont le rôle précédent était admin peuvent se restaurer eux-mêmes. Contactez le support.",
        })

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.users.update_one(
        {"id": user.id},
        {
            "$set": {
                "role":              prev_role,
                "is_admin":          True,
                "self_restored_at":  now_iso,
                "updated_at":        now_iso,
            },
            "$unset": {
                "previous_role":               "",
                "promoted_to_contractor_at":   "",
                "promoted_to_contractor_by":   "",
            },
        },
    )
    await db.admin_contractor_actions.insert_one({
        "id":             str(uuid.uuid4()),
        "action":         "self_restore_admin",
        "admin_id":       user.id,
        "contractor_id":  user.id,
        "restored_role":  prev_role,
        "created_at":     now_iso,
    })
    return {
        "user_id":       user.id,
        "restored_role": prev_role,
        "status":        "restored",
    }


# ─── iter317 Directive 2 — Electronic Contractor Agreement ──────────────

def _resolve_account_legal_name(user_doc: Dict[str, Any]) -> str:
    """Pick the authoritative legal-name field for the exact-match
    signing check. Priority: legal_name → legal_business_name → name →
    first+last → email local part."""
    candidates = [
        user_doc.get("legal_name"),
        user_doc.get("legal_business_name"),
        user_doc.get("name"),
        f"{user_doc.get('first_name','').strip()} {user_doc.get('last_name','').strip()}".strip(),
        (user_doc.get("email") or "").split("@", 1)[0],
    ]
    for c in candidates:
        if c and str(c).strip():
            return str(c).strip()
    return ""


def _norm_name(s: str) -> str:
    return " ".join((s or "").strip().lower().split())


@router.get("/contractor/agreements/current")
async def get_current_agreement(user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    """Returns the active contractor agreement text + version. Used by
    the frontend modal to render the scroll-to-accept body."""
    payload = get_agreement()
    db = get_db()
    me = await db.users.find_one(
        {"id": user.id},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "first_name": 1, "last_name": 1,
         "legal_name": 1, "legal_business_name": 1, "role": 1},
    )
    payload["account_legal_name"] = _resolve_account_legal_name(me or {})
    return payload


@router.get("/contractor/agreements/me")
async def get_my_agreement_status(user: User = Depends(get_current_user)) -> Dict[str, Any]:
    """Returns whether THIS user has signed the current contractor
    agreement version. Safe for any logged-in user — non-contractors get
    `signed: false, required: false`."""
    db = get_db()
    is_contractor_user = _role(user) == "dialer_contractor"
    is_admin_user = _role(user) in ADMIN_ROLES
    if not is_contractor_user and not is_admin_user:
        return {"signed": False, "required": False, "agreement_version": AGREEMENT_VERSION}

    row = await db.contractor_agreements.find_one(
        {"contractor_id": user.id, "agreement_version": AGREEMENT_VERSION},
        {"_id": 0},
        sort=[("signed_at", -1)],
    )
    return {
        "signed":             bool(row),
        "required":           is_contractor_user,
        "agreement_version":  AGREEMENT_VERSION,
        "signed_at":          (row or {}).get("signed_at"),
        "signed_full_name":   (row or {}).get("signed_full_name"),
    }


@router.get("/admin/contractor-agreements")
async def admin_list_contractor_agreements(user: User = Depends(require_admin)) -> Dict[str, Any]:
    """iter344 — READ-ONLY admin access to signed contractor agreements
    (legal audit records: name, IP, timestamp, version). There are
    deliberately NO admin write/modify/delete endpoints for the
    `contractor_agreements` collection — signing is contractor-only."""
    db = get_db()
    rows = await db.contractor_agreements.find({}, {"_id": 0}).sort("signed_at", -1).to_list(500)
    return {"agreements": rows, "count": len(rows), "read_only": True}


@router.post("/contractor/agreements/sign")
async def sign_agreement(body: SignAgreementBody,
                          request: Request,
                          user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    """Persist an append-only `contractor_agreements` row. Requires:
      • Current contractor role (dialer_contractor).
      • Body's `agreement_version` MUST match the server's active version.
      • Body's `text_hash` MUST match the server's canonical SHA-256.
      • `signed_full_name` MUST match the account_legal_name (case-
        insensitive, whitespace-collapsed). NO partial matches."""
    if _role(user) != "dialer_contractor":
        # Admins don't need to sign — gate only applies to contractors.
        raise HTTPException(409, {
            "error":      "not_a_contractor",
            "message_en": "Only contractors need to sign the agreement.",
            "message_fr": "Seuls les contractants doivent signer l'entente.",
        })

    db = get_db()
    if body.agreement_version != AGREEMENT_VERSION:
        raise HTTPException(400, {
            "error":      "version_mismatch",
            "message_en": "This agreement version is no longer current. Please reload.",
            "message_fr": "Cette version de l'entente n'est plus à jour. Veuillez recharger.",
            "current_version": AGREEMENT_VERSION,
        })
    if body.text_hash != AGREEMENT_TEXT_HASH:
        raise HTTPException(400, {
            "error":      "hash_mismatch",
            "message_en": "Agreement text has been updated since you opened it. Please reload.",
            "message_fr": "Le texte de l'entente a été mis à jour depuis son ouverture. Veuillez recharger.",
        })

    me = await db.users.find_one(
        {"id": user.id},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "first_name": 1, "last_name": 1,
         "legal_name": 1, "legal_business_name": 1},
    )
    account_legal_name = _resolve_account_legal_name(me or {})
    signed_full_name = (body.signed_full_name or "").strip()

    if not signed_full_name:
        raise HTTPException(400, {
            "error":      "name_required",
            "message_en": "Type your full legal name to accept.",
            "message_fr": "Saisissez votre nom légal complet pour accepter.",
        })

    name_match = (
        bool(account_legal_name)
        and _norm_name(signed_full_name) == _norm_name(account_legal_name)
    )
    if not name_match:
        raise HTTPException(400, {
            "error":      "name_mismatch",
            "message_en": (
                "The name you typed does not match the legal name on file"
                f" ({account_legal_name or 'unset'}). Please type it exactly."
            ),
            "message_fr": (
                "Le nom saisi ne correspond pas au nom légal au dossier"
                f" ({account_legal_name or 'non défini'}). Veuillez le saisir exactement."
            ),
        })

    # Idempotency: if already signed for this version, return the existing row.
    existing = await db.contractor_agreements.find_one(
        {"contractor_id": user.id, "agreement_version": AGREEMENT_VERSION},
        {"_id": 0},
        sort=[("signed_at", -1)],
    )
    if existing:
        return {**existing, "already_signed": True}

    now_iso = datetime.now(timezone.utc).isoformat()
    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "")
        or ""
    )
    user_agent = request.headers.get("user-agent", "")[:500]

    row = {
        "id":                              str(uuid.uuid4()),
        "contractor_id":                   user.id,
        "contractor_email":                me.get("email") if me else None,
        "agreement_version":               AGREEMENT_VERSION,
        "signed_full_name":                signed_full_name,
        "account_legal_name_at_signing":   account_legal_name,
        "name_match_confirmed":            True,
        "ip_address":                      client_ip,
        "user_agent":                      user_agent,
        "agreement_text_hash":             AGREEMENT_TEXT_HASH,
        "signed_at":                       now_iso,
    }
    await db.contractor_agreements.insert_one(row)
    # Convenience marker on the user doc so future reads don't have to
    # hit the agreements collection on every request (the audit row is
    # still the source of truth).
    await db.users.update_one(
        {"id": user.id},
        {"$set": {
            "contractor_agreement_signed":          True,
            "contractor_agreement_version":         AGREEMENT_VERSION,
            "contractor_agreement_signed_at":       now_iso,
        }},
    )

    # ─── iter353 — extension activation + admin notification ───────────
    # 1) Assign the contractor's dialer extension if not already present
    #    (idempotent: returns the existing extension for re-signs).
    # 2) Emit the admin alert email + admin_logs audit row.
    # Wrapped so any post-sign failure NEVER blocks the primary sign flow.
    assigned_ext: Optional[int] = None
    is_first_signing = False
    try:
        from services.contractor_extensions import get_extension_for_contractor, assign_extension
        pre_ext = await get_extension_for_contractor(db, user.id)
        is_first_signing = (pre_ext is None)
        assigned_ext = await assign_extension(db, user.id)
        if is_first_signing:
            logger.info(f"[iter353] contractor {user.id} first sign → extension {assigned_ext}")
    except Exception as _ext_exc:  # noqa: BLE001
        logger.error(f"[iter353] extension assignment on sign failed for {user.id}: {_ext_exc}")

    try:
        from services.admin_notifications import notify_admin_contractor_signed
        contractor_display_name = (
            (me or {}).get("name")
            or f"{(me or {}).get('first_name','')} {(me or {}).get('last_name','')}".strip()
            or (me or {}).get("legal_name")
            or signed_full_name
        )
        await notify_admin_contractor_signed(
            contractor_name=contractor_display_name,
            contractor_email=(me or {}).get("email") or "",
            extension_number=assigned_ext,
            agreement_version=AGREEMENT_VERSION,
            signed_at_iso=now_iso,
            ip_address=client_ip,
            is_first_signing=is_first_signing,
        )
    except Exception as _mail_exc:  # noqa: BLE001
        logger.error(f"[iter353] admin sign-notification email failed: {_mail_exc}")

    try:
        await db.admin_logs.insert_one({
            "id":                    str(uuid.uuid4()),
            "action":                "contractor_agreement_signed",
            "actor_id":              user.id,
            "actor_email":           (me or {}).get("email"),
            "extension_number":      assigned_ext,
            "agreement_version":     AGREEMENT_VERSION,
            "is_first_signing":      is_first_signing,
            "ip":                    client_ip,
            "user_agent":            user_agent,
            "created_at":            now_iso,
        })
    except Exception as _log_exc:  # noqa: BLE001
        logger.error(f"[iter353] admin_logs write failed: {_log_exc}")

    row.pop("_id", None)
    return {**row, "already_signed": False, "extension_number": assigned_ext}


def _require_agreement_signed(db_obj, contractor_id: str):
    """Internal helper — raise 412 if contractor hasn't signed current
    agreement version. Caller passes the live db handle so we don't
    re-instantiate."""
    async def _check():
        row = await db_obj.contractor_agreements.find_one(
            {"contractor_id": contractor_id, "agreement_version": AGREEMENT_VERSION},
            {"_id": 0, "id": 1},
        )
        if not row:
            raise HTTPException(412, {
                "error":      "agreement_required",
                "message_en": "Please sign the Contractor Services Agreement to continue.",
                "message_fr": "Veuillez signer l'Entente de services du contractant pour continuer.",
                "agreement_version": AGREEMENT_VERSION,
            })
    return _check()


# ─── iter317 Directive 3 — Contractor Email Hub ─────────────────────────

@router.post("/contractor/emails/send")
async def contractor_send_email(body: ContractorEmailSendBody,
                                  request: Request,
                                  user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    """Sends an outbound email via office@bidvex.com on behalf of the
    contractor. Server-side signature injection is non-overridable.
    Gated by the signed agreement (Directive 2)."""
    db = get_db()

    # Admins can send too (acting as themselves) — both contractors and
    # admins flow through Directive 3. Agreement signing is enforced
    # only for actual contractors.
    if _role(user) == "dialer_contractor":
        await _require_agreement_signed(db, user.id)

    if not validate_recipient_email(body.to_email):
        raise HTTPException(400, {
            "error":      "invalid_recipient",
            "message_en": "Enter a valid recipient email address.",
            "message_fr": "Saisissez une adresse de courriel valide.",
        })
    subj = (body.subject or "").strip()
    if not subj or len(subj) > 300:
        raise HTTPException(400, {
            "error":      "invalid_subject",
            "message_en": "Subject is required (max 300 characters).",
            "message_fr": "Le sujet est obligatoire (300 caractères max).",
        })
    body_html = (body.body_html or "").strip()
    if not body_html:
        raise HTTPException(400, {
            "error":      "empty_body",
            "message_en": "Email body cannot be empty.",
            "message_fr": "Le corps du courriel ne peut pas être vide.",
        })
    if len(body_html) > 50000:
        raise HTTPException(400, {
            "error":      "body_too_long",
            "message_en": "Email body must be under 50,000 characters.",
            "message_fr": "Le corps du courriel doit faire moins de 50 000 caractères.",
        })

    contractor_doc = await db.users.find_one(
        {"id": user.id},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "first_name": 1, "last_name": 1,
         "preferred_language": 1},
    )
    if contractor_doc is None:
        raise HTTPException(404, "contractor not found")

    client_ip = (
        request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "")
        or ""
    )
    user_agent = request.headers.get("user-agent", "")[:500]
    locale = (body.locale or contractor_doc.get("preferred_language") or "en").lower()

    row = await send_contractor_email(
        db,
        contractor=contractor_doc,
        to_email=body.to_email.strip().lower(),
        subject=subj,
        body_html=body_html,
        locale=locale,
        client_account_id=body.client_account_id,
        contractor_ip=client_ip,
        contractor_user_agent=user_agent,
        # iter337 — When this send is an AI-drafted follow-up, tag the
        # outbound with custom args so SendGrid echoes them on Event
        # Webhook payloads (open/click). Attribution is anchored on
        # `call_log_id` — the open handler uses this to update
        # `ai_voice_calls.followup_emails_generated.$.opened_at`.
        custom_args=(
            {"call_log_id": body.call_log_id, "email_type": "ai_followup"}
            if body.call_log_id else None
        ),
    )

    # iter336 — If this email is an AI-generated follow-up, mark the
    # matching draft in the source call's ai_voice_calls document as
    # sent so admins can see the full audit trail.
    if body.call_log_id:
        try:
            now = datetime.now(timezone.utc).isoformat()
            await db.ai_voice_calls.update_one(
                {
                    "call_log_id": body.call_log_id,
                    "call_type": "outbound_coach",
                    "contractor_id": user.id,
                    "followup_emails_generated": {"$elemMatch": {"sent": False}},
                },
                {"$set": {
                    "followup_emails_generated.$.sent": True,
                    "followup_emails_generated.$.sent_at": now,
                    "followup_emails_generated.$.email_row_id": row.get("id") or row.get("_id"),
                }},
            )
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[iter336] link email→coach session failed: {e}")

    return row


@router.get("/contractor/emails")
async def contractor_list_emails(user: User = Depends(require_dialer_access),
                                   limit: int = Query(50, ge=1, le=200),
                                   contractor_id: Optional[str] = Query(None)) -> Dict[str, Any]:
    """Sent-list for the contractor's own emails. Admins can pass
    `contractor_id` to view another contractor's outbox."""
    db = get_db()
    if _is_contractor(user) and not _is_admin(user):
        cid = user.id
    elif _is_admin(user):
        cid = contractor_id or user.id
    else:
        raise HTTPException(403, "contractor / admin only")

    rows = await db.contractor_emails.find(
        {"contractor_id": cid}, {"_id": 0},
    ).sort("sent_at", -1).limit(limit).to_list(length=limit)
    return {
        "items":             rows,
        "count":             len(rows),
        "sender_email":      CONTRACTOR_SENDER_EMAIL,
        "sender_name":       CONTRACTOR_SENDER_NAME,
        "support_phone":     SUPPORT_PHONE,
    }


@router.get("/contractor/emails/recipients")
async def contractor_email_recipients(user: User = Depends(require_dialer_access),
                                        limit: int = Query(100, ge=1, le=500)) -> Dict[str, Any]:
    """Picker source for the email composer: the contractor's referred
    accounts with an email. Returns clean (id, email, name) tuples."""
    db = get_db()
    cid = user.id if not _is_admin(user) else user.id
    rows = await db.users.find(
        {"referred_by_contractor_id": cid, "email": {"$exists": True, "$ne": ""}},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "first_name": 1, "last_name": 1,
         "business_name": 1},
    ).sort("created_at", -1).limit(limit).to_list(length=limit)
    out = []
    for r in rows:
        display = (r.get("business_name") or r.get("name")
                   or f"{r.get('first_name','')} {r.get('last_name','')}".strip()
                   or r.get("email"))
        out.append({"id": r["id"], "email": r["email"], "display": display})
    return {"items": out, "count": len(out)}


__all__ = ["router"]
