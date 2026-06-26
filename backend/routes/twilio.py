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
from datetime import datetime, timezone
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


# ─── Mission 1 — Browser SDK token ──────────────────────────────────────

@router.get("/config")
async def get_dialer_config(user: User = Depends(require_dialer_access)) -> Dict[str, Any]:
    """UI-facing config probe — tells the frontend whether the dialer is
    usable and which env vars are still missing."""
    s = verify_twilio_config()
    return {
        "configured":      s["configured"],
        "can_mint_tokens": s["can_mint_tokens"],
        "can_place_calls": s["can_place_calls"],
        "missing":         s["missing"],
        "twilio_phone_number": TWILIO_PHONE_NUMBER if s["can_place_calls"] else None,
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
    """Reject if the X-Twilio-Signature header is missing or wrong.
    Skipped only when the env var TWILIO_SKIP_SIGNATURE_VERIFY=1 is set
    (local dev / unit-test). Production must enforce."""
    if os.environ.get("TWILIO_SKIP_SIGNATURE_VERIFY") == "1":
        return
    sig = request.headers.get("x-twilio-signature")
    if not sig:
        raise HTTPException(403, "missing twilio signature")
    if not validate_webhook_signature(_twilio_request_url(request), form, sig):
        raise HTTPException(403, "invalid twilio signature")


@router.post("/twiml")
async def twiml_webhook(request: Request) -> Response:
    """Twilio's Voice Request URL. Returns TwiML XML that bridges the
    agent to the client, sets caller_id to TWILIO_PHONE_NUMBER (so
    neither party sees the other's real number), and registers
    recording + status callbacks."""
    form = dict((await request.form()))
    await _verify_twilio_signature(request, form)

    to_number = form.get("To") or form.get("Called") or ""
    if not validate_e164(to_number):
        raise HTTPException(400, "invalid To param")

    proto = request.headers.get("x-forwarded-proto", "https")
    host  = request.headers.get("x-forwarded-host") or request.headers.get("host") or "bidvex.com"
    base  = f"{proto}://{host}"
    twiml = build_outbound_twiml(
        client_phone_number=to_number,
        status_callback=f"{base}/api/twilio/call-status-callback",
        recording_callback=f"{base}/api/twilio/recording-callback",
    )
    return Response(content=twiml, media_type="application/xml")


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
                     offset: int = Query(0, ge=0)) -> Dict[str, Any]:
    db = get_db()
    q = _ownership_filter(user)
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

    # Phase A scope — default cleanly to vehicle_dealer, allow override.
    account_type = body.account_type
    if account_type not in ACCOUNT_TYPES:
        account_type = "vehicle_dealer"

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
        "account_type":               account_type,
        "is_vehicle_dealer":          account_type == "vehicle_dealer",
        "is_partner":                 account_type == "partner",
        "is_broker":                  account_type == "broker",
        "is_liquidator":              account_type == "liquidator",
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
         "stripe_connect_onboarding_complete": 1},
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
    }


# ─── Mission 4 — Admin commission rate CRUD ─────────────────────────────

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


__all__ = ["router"]
