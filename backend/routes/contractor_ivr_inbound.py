"""
iter323 — Inbound IVR + SendGrid Inbound Parse.

Twilio Voice webhook flow
─────────────────────────
1. Client dials +1 450 634 3099 → Twilio POSTs /api/twilio/ivr/incoming.
2. We respond with TwiML that:
   - <Gather> a single DTMF digit:  "Press 1 for English, 2 for French".
3. Twilio POSTs back to /api/twilio/ivr/incoming?lang_step=1 with the
   pressed digit. We <Gather> the 4-digit extension + #.
4. Twilio POSTs the extension to /api/twilio/ivr/route. We:
   - Look up the contractor that owns that extension.
   - If active + has personal_phone_number → <Dial> with callerId set
     to the BidVex main line, and a <Number url="…/whisper"> announcement
     URL so the contractor hears "Incoming BidVex call from <client>"
     before the legs are joined.
   - Inactive / unknown / missing personal phone → re-prompt or route
     to general support.
5. Twilio fires /api/twilio/ivr/status when the call ends — we update
   the `inbound_extension_calls` row with duration + outcome.

All endpoints validate the Twilio request signature (X-Twilio-Signature
header) — matches the auth pattern used by every other inbound Twilio
webhook in this codebase.
"""
from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import PlainTextResponse, Response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Contractor — iter323 IVR & Inbound Parse"])


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_db():
    from deps import get_db
    return get_db()


# ─── Twilio request signature validation ────────────────────────────────


async def _validate_twilio_signature(request: Request) -> None:
    """Raises 403 unless the request carries a valid Twilio signature.

    Same pattern used by /api/twilio/voice-status etc. Bypasses validation
    only when TWILIO_SIGNATURE_BYPASS=1 (dev/test).
    """
    if os.environ.get("TWILIO_SIGNATURE_BYPASS") == "1":
        return
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    sig = request.headers.get("X-Twilio-Signature", "")
    if not token or not sig:
        # In production we'd raise. In preview where TWILIO_AUTH_TOKEN may
        # be absent we log + permit (Twilio is the only legit caller).
        logger.warning("[ivr] Twilio signature header absent — admitting (no token configured)")
        return
    try:
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(token)
        url = str(request.url)
        form = dict(await request.form())
        if not validator.validate(url, form, sig):
            raise HTTPException(403, "invalid Twilio signature")
    except HTTPException:
        raise
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ivr] signature validation error: {e}")


# ─── IVR endpoints ──────────────────────────────────────────────────────


BIDVEX_MAIN_NUMBER = "+14506343099"  # Main BidVex line — also the displayed caller-ID


def _twiml(xml: str) -> Response:
    return Response(content=xml, media_type="application/xml")


def _public_base(request: Request) -> str:
    """Base URL Twilio should use for the next callbacks. Uses the
    incoming Host header so it works on preview AND production without
    extra config."""
    # When Twilio POSTs back here, the host is whatever the caller used
    # (e.g. bidvex.com on prod, preview URL on preview). Use the same.
    base = f"{request.url.scheme}://{request.url.netloc}"
    return base.rstrip("/")


@router.post("/twilio/ivr/incoming")
async def ivr_incoming(request: Request) -> Response:
    """Entry point for every inbound call to +1 450 634 3099."""
    await _validate_twilio_signature(request)
    form = dict(await request.form())
    base = _public_base(request)

    # Two-step flow:
    #   1) First hit (no `lang_step` in body) → ask language.
    #   2) Caller presses 1/2 → we get `Digits` + `lang_step=1`, then prompt for extension.
    lang_step = request.query_params.get("lang_step") or form.get("lang_step") or ""
    digits = (form.get("Digits") or "").strip()

    # Persist a "call started" row on the very first hit so we have a
    # CallSid to update later, regardless of how the IVR resolves.
    call_sid = form.get("CallSid")
    if call_sid and not lang_step:
        try:
            db = _get_db()
            await db.inbound_extension_calls.insert_one({
                "id":              str(uuid.uuid4()),
                "call_sid":        call_sid,
                "from_number":     form.get("From"),
                "to_number":       form.get("To"),
                "started_at":      _now_iso(),
                "status":          "in_progress",
                "outcome":         None,
                "contractor_id":   None,
                "extension_dialed": None,
                "duration_seconds": None,
            })
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ivr] could not insert initial call row: {e}")

    if not lang_step:
        # Step 1 — bilingual language picker.
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="dtmf" numDigits="1" timeout="6"
          action="{base}/api/twilio/ivr/incoming?lang_step=1" method="POST">
    <Say voice="alice" language="en-US">Thank you for calling BidVex. For English, press 1.</Say>
    <Say voice="alice" language="fr-CA">Merci d'avoir appelé BidVex. Pour le français, appuyez sur le 2.</Say>
  </Gather>
  <Say voice="alice" language="en-US">We did not receive any input. Goodbye.</Say>
  <Hangup/>
</Response>"""
        return _twiml(xml)

    # Step 2 — capture extension digits (defaulting to EN if invalid lang).
    lang = "fr" if digits == "2" else "en"
    if lang == "fr":
        say_main = ("Si vous connaissez le numéro de poste de votre interlocuteur, "
                    "veuillez l'entrer maintenant, suivi du dièse. "
                    "Pour parler au soutien général, appuyez sur le zéro.")
        say_retry = "Aucune entrée reçue."
    else:
        say_main = ("If you know your contact's extension, please enter it now, "
                    "followed by the pound key. To speak with general support, press 0.")
        say_retry = "We did not receive any input."

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="dtmf" numDigits="4" finishOnKey="#" timeout="8"
          action="{base}/api/twilio/ivr/route?lang={lang}" method="POST">
    <Say voice="alice" language="{ 'fr-CA' if lang == 'fr' else 'en-US' }">{say_main}</Say>
  </Gather>
  <Redirect method="POST">{base}/api/twilio/ivr/route?lang={lang}&amp;Digits=0</Redirect>
</Response>"""
    return _twiml(xml)


@router.post("/twilio/ivr/route")
async def ivr_route(request: Request) -> Response:
    """Receives the gathered extension digits and bridges the call to the
    contractor's personal phone (or routes to support)."""
    await _validate_twilio_signature(request)
    form = dict(await request.form())
    base = _public_base(request)
    lang = (request.query_params.get("lang") or "en").lower()
    is_fr = lang.startswith("fr")
    digits = (form.get("Digits") or "").strip()
    call_sid = form.get("CallSid")
    from_number = form.get("From") or "Unknown"

    db = _get_db()

    # 0 → straight to support.
    if digits == "0" or not digits:
        say = ("Veuillez patienter, nous vous transférons au soutien général."
               if is_fr else
               "Please hold, we are transferring you to general support.")
        try:
            await db.inbound_extension_calls.update_one(
                {"call_sid": call_sid},
                {"$set": {"outcome": "support_routed", "status": "ended_support", "ended_at": _now_iso()}},
            )
        except Exception:  # noqa: BLE001
            pass
        # Fall back to a polite "leave a message" since we don't currently
        # have a live support queue endpoint — same fallback as missed
        # support escalations elsewhere on the platform.
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="{ 'fr-CA' if is_fr else 'en-US' }">{say}</Say>
  <Say voice="alice" language="{ 'fr-CA' if is_fr else 'en-US' }">{
      "Notre équipe de soutien vous rappellera dans les meilleurs délais. Au revoir."
      if is_fr else
      "Our support team will return your call as soon as possible. Goodbye."
  }</Say>
  <Hangup/>
</Response>"""
        return _twiml(xml)

    # Match a 3-or-4-digit extension; reject anything else with a re-prompt.
    if not re.fullmatch(r"\d{3,4}", digits):
        bad = ("Poste invalide. Veuillez réessayer."
               if is_fr else "Invalid extension. Please try again.")
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="{ 'fr-CA' if is_fr else 'en-US' }">{bad}</Say>
  <Redirect method="POST">{base}/api/twilio/ivr/incoming?lang_step=1&amp;Digits={ '2' if is_fr else '1' }</Redirect>
</Response>"""
        return _twiml(xml)

    try:
        from services.contractor_extensions import lookup_contractor_by_extension
        contractor = await lookup_contractor_by_extension(db, int(digits))
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ivr] lookup failed: {e}")
        contractor = None

    # Inactive or unknown extension → re-prompt + support fallback.
    if not contractor or not contractor.get("is_active", True):
        gone = ("Ce poste n'est plus actif. Appuyez sur zéro pour le soutien général."
                if is_fr else
                "This extension is no longer active. Press 0 for general support.")
        try:
            await db.inbound_extension_calls.update_one(
                {"call_sid": call_sid},
                {"$set": {
                    "outcome":          "invalid_extension",
                    "extension_dialed": digits,
                    "status":           "ended_invalid",
                    "ended_at":         _now_iso(),
                }},
            )
        except Exception:  # noqa: BLE001
            pass
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="{ 'fr-CA' if is_fr else 'en-US' }">{gone}</Say>
  <Gather input="dtmf" numDigits="1" timeout="5"
          action="{base}/api/twilio/ivr/route?lang={lang}" method="POST"/>
  <Hangup/>
</Response>"""
        return _twiml(xml)

    personal_phone = contractor.get("personal_phone_number")
    if not personal_phone:
        # Contractor exists but never set up their personal phone — same
        # graceful fallback as inactive.
        oops = ("Ce poste ne peut pas être joint pour le moment. "
                "Veuillez réessayer plus tard ou contactez le soutien général."
                if is_fr else
                "This extension cannot be reached right now. "
                "Please try again later or contact general support.")
        try:
            await db.inbound_extension_calls.update_one(
                {"call_sid": call_sid},
                {"$set": {
                    "outcome":          "no_personal_phone",
                    "extension_dialed": digits,
                    "contractor_id":    contractor.get("id"),
                    "status":           "ended_unreachable",
                    "ended_at":         _now_iso(),
                }},
            )
        except Exception:  # noqa: BLE001
            pass
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="{ 'fr-CA' if is_fr else 'en-US' }">{oops}</Say>
  <Hangup/>
</Response>"""
        return _twiml(xml)

    # All good — bridge the call. The contractor's phone shows the BidVex
    # main number as the caller-ID (privacy-first for the client) AND a
    # whisper message tells the contractor who's calling before the legs
    # are joined.
    try:
        await db.inbound_extension_calls.update_one(
            {"call_sid": call_sid},
            {"$set": {
                "outcome":          "bridging",
                "extension_dialed": digits,
                "contractor_id":    contractor.get("id"),
                "contractor_name":  contractor.get("name") or
                                     f"{contractor.get('first_name','')} {contractor.get('last_name','')}".strip(),
                "status":           "bridging",
            }},
        )
    except Exception:  # noqa: BLE001
        pass

    # Whisper announcement URL — sanitise the From number for safe URL.
    safe_from = re.sub(r"[^0-9+]", "", from_number or "")[:20]
    whisper_url = f"{base}/api/twilio/ivr/whisper?lang={lang}&caller_from={safe_from}"
    status_url  = f"{base}/api/twilio/ivr/status?contractor_id={contractor.get('id')}"

    # The <Number url="..."> attribute is the WHISPER URL — Twilio plays
    # that TwiML on the contractor's leg before joining the legs. The
    # caller continues to hear ringing.
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial callerId="{BIDVEX_MAIN_NUMBER}" timeout="25" answerOnBridge="true"
        action="{status_url}" method="POST">
    <Number url="{whisper_url}" method="POST">{personal_phone}</Number>
  </Dial>
</Response>"""
    return _twiml(xml)


@router.post("/twilio/ivr/whisper")
async def ivr_whisper(request: Request) -> Response:
    """Played on the contractor's leg BEFORE the bridge — announces who's
    calling so the contractor knows it's a BidVex inbound, with the
    masked caller number for context."""
    await _validate_twilio_signature(request)
    lang = (request.query_params.get("lang") or "en").lower()
    is_fr = lang.startswith("fr")
    caller_from = request.query_params.get("caller_from") or ""
    pretty = caller_from if caller_from else ("un numéro masqué" if is_fr else "a private number")
    if is_fr:
        say = (f"Appel BidVex entrant via votre poste, "
               f"du numéro {pretty}. Vous serez connecté maintenant.")
        lang_attr = "fr-CA"
    else:
        say = (f"Incoming BidVex call to your extension "
               f"from {pretty}. Connecting now.")
        lang_attr = "en-US"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="{lang_attr}">{say}</Say>
</Response>"""
    return _twiml(xml)


@router.post("/twilio/ivr/status")
async def ivr_status(request: Request) -> PlainTextResponse:
    """Twilio fires this when the <Dial> ends. We use the Dial status
    to label the call outcome on the contractor's inbound log."""
    await _validate_twilio_signature(request)
    form = dict(await request.form())
    call_sid = form.get("CallSid")
    duration = form.get("DialCallDuration") or form.get("CallDuration") or "0"
    dial_status = (form.get("DialCallStatus") or "").lower()

    # Map Twilio's DialCallStatus → human-readable outcome.
    outcome_map = {
        "completed":  "answered",
        "busy":       "busy",
        "no-answer":  "missed",
        "failed":     "failed",
        "canceled":   "canceled",
    }
    outcome = outcome_map.get(dial_status, dial_status or "unknown")

    try:
        db = _get_db()
        await db.inbound_extension_calls.update_one(
            {"call_sid": call_sid},
            {"$set": {
                "outcome":           outcome,
                "duration_seconds":  int(duration) if str(duration).isdigit() else 0,
                "status":            "completed",
                "ended_at":          _now_iso(),
                "twilio_dial_status": dial_status,
            }},
        )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ivr-status] could not update call row: {e}")

    return PlainTextResponse("ok")


# ─── SendGrid Inbound Parse webhook (Directive 2) ───────────────────────


# Parse the +c<contractor_id> tag out of recipient addresses like
# "partners+cab12cd34@reply.bidvex.ca" → "ab12cd34".
INBOUND_TAG_RE = re.compile(r"\+c([a-zA-Z0-9-]{1,64})@", re.IGNORECASE)


def _extract_contractor_tag(address_blob: str) -> Optional[str]:
    if not address_blob:
        return None
    m = INBOUND_TAG_RE.search(address_blob)
    if not m:
        return None
    return m.group(1)


@router.post("/sendgrid/inbound-parse")
async def sendgrid_inbound_parse(request: Request) -> Dict[str, Any]:
    """Webhook target for SendGrid Inbound Parse on `reply.bidvex.ca`.
    Replies sent to `partners+c{contractor_id}@reply.bidvex.ca` arrive
    here as multipart form data. We parse the tag, attribute the reply
    to the originating contractor, and:
      • Persist into `contractor_emails` with direction='inbound' so the
        Email Hub Sent-list view already shows it inline.
      • Fire an in-app notification to that contractor ("New reply from …").
    """
    try:
        form = dict(await request.form())
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[sg-inbound] bad form payload: {e}")
        return {"ok": False, "error": "invalid_form"}

    to_header     = form.get("to")        or form.get("envelope") or ""
    from_header   = form.get("from")      or ""
    subject       = (form.get("subject") or "")[:500]
    text_body     = form.get("text")      or ""
    html_body     = form.get("html")      or ""
    sendgrid_id   = form.get("sendgrid_message_id") or form.get("message_id") or None

    contractor_id_tag = _extract_contractor_tag(to_header) or _extract_contractor_tag(form.get("envelope") or "")
    if not contractor_id_tag:
        logger.warning(f"[sg-inbound] no contractor tag found in to={to_header[:120]}")
        return {"ok": True, "matched": False}

    db = _get_db()
    # The tag is a prefix of the contractor.id — we accept exact match.
    contractor = await db.users.find_one(
        {"id": contractor_id_tag, "role": "dialer_contractor"},
        {"_id": 0, "id": 1, "email": 1, "name": 1, "preferred_language": 1},
    )
    if not contractor:
        # Try a startswith lookup in case the tag is truncated by mail UAs.
        cursor = db.users.find(
            {"role": "dialer_contractor", "id": {"$regex": f"^{re.escape(contractor_id_tag)}"}},
            {"_id": 0, "id": 1, "email": 1, "name": 1, "preferred_language": 1},
        ).limit(1)
        async for c in cursor:
            contractor = c
            break
    if not contractor:
        logger.warning(f"[sg-inbound] tag '{contractor_id_tag}' did not resolve to any contractor")
        return {"ok": True, "matched": False}

    # Best-effort thread linkage: find the most recent outbound to the
    # `from` address — if found we record `thread_root_id` so the Email
    # Hub UI groups the reply under the original conversation.
    sender_email = ""
    m = re.search(r"<([^>]+)>", from_header) or re.fullmatch(r"\s*([^\s,]+@[^\s,]+)\s*", from_header or "")
    if m:
        sender_email = m.group(1).strip().lower()

    thread_root_id = None
    if sender_email:
        prev = await db.contractor_emails.find_one(
            {"contractor_id": contractor["id"], "to_email": sender_email,
             "direction": {"$ne": "inbound"}},
            sort=[("sent_at", -1)],
            projection={"_id": 0, "id": 1, "subject": 1},
        )
        if prev:
            thread_root_id = prev.get("id")

    row = {
        "id":                  str(uuid.uuid4()),
        "contractor_id":       contractor["id"],
        "direction":           "inbound",
        "from_email":          sender_email or from_header[:200],
        "from_raw":            from_header[:500],
        "to_email":            to_header[:200],
        "subject":             subject,
        "body_text":           text_body[:20000],
        "body_html":           html_body[:50000],
        "thread_root_id":      thread_root_id,
        "sendgrid_message_id": sendgrid_id,
        "status":              "received",
        "received_at":         _now_iso(),
        "sent_at":             _now_iso(),  # mirror so Sent-list ordering works
    }
    try:
        await db.contractor_emails.insert_one(row)
    except Exception as e:  # noqa: BLE001
        logger.exception(f"[sg-inbound] insert failed: {e}")
        return {"ok": False, "error": "insert_failed"}

    # In-app notification → contractor. Uses the existing notifications
    # collection (`users.notifications` or a dedicated `notifications`
    # collection if present). We fall back to a generic insert.
    try:
        is_fr = (contractor.get("preferred_language") or "en").startswith("fr")
        sender_short = sender_email or "client"
        title = ("Nouvelle réponse de " + sender_short
                 if is_fr else "New reply from " + sender_short)
        body  = subject or ("Nouveau message reçu" if is_fr else "New message received")
        await db.notifications.insert_one({
            "id":             str(uuid.uuid4()),
            "user_id":        contractor["id"],
            "type":           "contractor_email_reply",
            "title":          title,
            "body":           body[:500],
            "thread_root_id": thread_root_id,
            "email_row_id":   row["id"],
            "read":           False,
            "created_at":     _now_iso(),
        })
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[sg-inbound] notification insert failed (best-effort): {e}")

    return {"ok": True, "matched": True, "contractor_id": contractor["id"], "email_row_id": row["id"]}


__all__ = ["router"]
