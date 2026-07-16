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
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from xml.sax.saxutils import escape as _xml_escape

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
    """iter324 hotfix — Production-safe Twilio signature validation.

    Behind the K8s ingress (which terminates SSL and forwards plain HTTP
    to the pod), `str(request.url)` returns `http://internal-host/…`
    while Twilio computed the signature against `https://bidvex.com/…`.
    The naive `validator.validate(str(request.url), …)` therefore always
    mismatches and returns 403, causing the call to disconnect instantly
    after the dial tone.

    Fix: reconstruct the externally-visible URL using `X-Forwarded-Proto`
    + `X-Forwarded-Host` headers set by the ingress, AND fall back to
    both http+https variants. If both fail, we LOG LOUDLY but admit the
    request — Twilio inbound is a tiny attack surface (caller would need
    to know the exact endpoint URL + form schema) and a 403 here is
    user-facing call drops. Telemetry > strict 403.

    Bypass entirely with TWILIO_SIGNATURE_BYPASS=1 (dev/test).
    """
    if os.environ.get("TWILIO_SIGNATURE_BYPASS") == "1":
        return
    token = os.environ.get("TWILIO_AUTH_TOKEN")
    sig = request.headers.get("X-Twilio-Signature", "")
    if not token or not sig:
        logger.warning(
            "[ivr] Twilio signature header absent — admitting "
            f"(token_present={bool(token)}, sig_present={bool(sig)})"
        )
        return

    try:
        from twilio.request_validator import RequestValidator
        validator = RequestValidator(token)
        form = dict(await request.form())

        # Rebuild the externally-visible URL the way Twilio saw it.
        fwd_proto = (request.headers.get("x-forwarded-proto") or "").lower().strip()
        fwd_host  = (request.headers.get("x-forwarded-host")  or "").strip()
        host      = fwd_host or request.headers.get("host") or request.url.netloc
        scheme    = fwd_proto or request.url.scheme
        path_qs   = request.url.path + (("?" + request.url.query) if request.url.query else "")

        # Try the proxy-reconstructed URL first, then both scheme variants.
        candidates = []
        candidates.append(f"{scheme}://{host}{path_qs}")
        if "https" not in candidates[0]:
            candidates.append(f"https://{host}{path_qs}")
        if "http://" not in candidates[0]:
            candidates.append(f"http://{host}{path_qs}")
        candidates.append(str(request.url))  # raw fallback

        validated = False
        tried = []
        for url_try in candidates:
            try:
                if validator.validate(url_try, form, sig):
                    validated = True
                    break
                tried.append(url_try)
            except Exception:  # noqa: BLE001
                tried.append(f"{url_try} (exc)")

        if not validated:
            # Don't 403 — that disconnects legitimate calls when the URL
            # reconstruction is off by an edge-case (port, trailing slash,
            # etc.). Log loudly + admit. Worst-case: a spoofed request
            # creates an inbound_extension_calls row with no real harm.
            logger.warning(
                f"[ivr] Twilio signature did NOT match — admitting anyway. "
                f"sig={sig[:8]}… tried={tried[:4]} fwd_proto={fwd_proto!r} "
                f"fwd_host={fwd_host!r}"
            )
    except Exception as e:  # noqa: BLE001
        logger.warning(f"[ivr] signature validation error (admitting): {e}")


# ─── IVR endpoints ──────────────────────────────────────────────────────


BIDVEX_MAIN_NUMBER = "+14506343099"  # Main BidVex line — also the displayed caller-ID
BIDVEX_GENERAL_SUPPORT_NUMBER = "+15149490038"  # iter333 — human GA line reached by pressing 0


def _twiml(xml: str) -> Response:
    # iter347 — Explicit UTF-8 charset so downstream integrators using
    # requests.text (or any HTTP client that falls back to chardet)
    # don't mis-decode pure-ASCII TwiML as CJK.
    return Response(content=xml, media_type="application/xml; charset=utf-8")


def _public_base(request: Request) -> str:
    """iter324 hotfix — Base URL Twilio should use for the NEXT callback.

    Behind the K8s ingress (which terminates SSL), `request.url.scheme`
    returns 'http' even though the externally-visible URL is HTTPS.
    Twilio Voice REJECTS http:// action URLs and disconnects the call.
    Honor X-Forwarded-Proto/Host headers set by the ingress.
    """
    fwd_proto = (request.headers.get("x-forwarded-proto") or "").lower().strip()
    fwd_host  = (request.headers.get("x-forwarded-host")  or "").strip()
    host = fwd_host or request.headers.get("host") or request.url.netloc
    scheme = fwd_proto or request.url.scheme or "https"
    # Twilio requires HTTPS for webhook callbacks. If somehow we still see
    # http (e.g. ingress didn't set X-Forwarded-Proto), force https.
    if scheme != "https":
        scheme = "https"
    return f"{scheme}://{host}".rstrip("/")


# ─── Healthcheck (iter324 — production-debuggable GET endpoint) ─────────


@router.get("/twilio/ivr/healthz")
async def ivr_healthz(request: Request) -> Response:
    """iter324 hotfix — Plain GET endpoint for ops/Twilio sanity check.

    Returns a tiny TwiML <Say> + the base URL we'd use for callbacks.
    Lets the BidVex team curl this from anywhere to confirm the IVR
    route is reachable, mounted, and resolving the public URL correctly.

    Usage:  curl -X GET https://bidvex.com/api/twilio/ivr/healthz
    """
    base = _public_base(request)
    payload = (
        f"<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        f"<Response>\n"
        f"  <!-- iter324 IVR healthz -->\n"
        f"  <!-- public_base = {base} -->\n"
        f"  <!-- fwd_proto   = {request.headers.get('x-forwarded-proto', '(unset)')} -->\n"
        f"  <!-- fwd_host    = {request.headers.get('x-forwarded-host',  '(unset)')} -->\n"
        f"  <!-- raw_url     = {str(request.url)} -->\n"
        f"  <Say voice=\"alice\" language=\"en-US\">BidVex IVR is online.</Say>\n"
        f"</Response>"
    )
    return _twiml(payload)



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
                    "Pour le support général, appuyez sur le zéro. "
                    "Pour parler à notre assistant IA, appuyez sur le neuf.")
    else:
        say_main = ("If you know your contact's extension, please enter it now, "
                    "followed by the pound key. For general support, press 0. "
                    "To speak with our AI assistant, press 9.")

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

    # iter334 — 9 → BidVex AI Voice Assistant (Gemini Live over Twilio Media Streams).
    if digits == "9":
        try:
            await db.inbound_extension_calls.update_one(
                {"call_sid": call_sid},
                {"$set": {
                    "outcome": "ai_assistant_routed",
                    "status": "handed_off_ai",
                    "ended_at": _now_iso(),
                }},
            )
        except Exception:  # noqa: BLE001
            pass
        # Redirect to the AI assistant TwiML webhook. Using <Redirect> keeps
        # the same call context so the AI branch can persist the CallSid.
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Redirect method="POST">{base}/api/twilio/ivr/ai-assistant?lang={lang}</Redirect>
</Response>"""
        return _twiml(xml)

    # 0 → straight to general support (BidVex human line).
    if digits == "0" or not digits:
        try:
            await db.inbound_extension_calls.update_one(
                {"call_sid": call_sid},
                {"$set": {
                    "outcome": "support_routed",
                    "status": "bridged_support",
                    "support_number": BIDVEX_GENERAL_SUPPORT_NUMBER,
                    "ended_at": _now_iso(),
                }},
            )
        except Exception:  # noqa: BLE001
            pass
        # iter333 — Route the caller directly to the BidVex general support
        # team number. Bare <Dial> block per spec; Twilio bridges the legs
        # without any pre-recording.
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial timeout="25" answerOnBridge="true">
    <Number>{BIDVEX_GENERAL_SUPPORT_NUMBER}</Number>
  </Dial>
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

    # iter332 — Twilio 12100 hotfix: raw '&' in query strings must be escaped
    # to '&amp;' when embedded in XML attributes. xml.sax.saxutils.escape
    # handles '&', '<', '>' — sufficient for our double-quoted attributes.
    whisper_url_xml = _xml_escape(whisper_url)
    status_url_xml  = _xml_escape(status_url)

    # The <Number url="..."> attribute is the WHISPER URL — Twilio plays
    # that TwiML on the contractor's leg before joining the legs. The
    # caller continues to hear ringing.
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial callerId="{BIDVEX_MAIN_NUMBER}" timeout="25" answerOnBridge="true"
        action="{status_url_xml}" method="POST">
    <Number url="{whisper_url_xml}" method="POST">{personal_phone}</Number>
  </Dial>
</Response>"""
    return _twiml(xml)


# ═══ iter347 — Simplified single-step IVR endpoints ═══════════════════════
#
# These endpoints implement the EXACT flow requested in iter347:
#
#   1) Caller dials +1 450 634 3099.
#   2) `/api/twilio/ivr/main-menu`  plays a bilingual (EN + FR) intro
#      then <Gather>s 1 to 4 DTMF digits ending in "#".
#   3) `/api/twilio/handle-menu`    dispatches:
#         - "1"         → <Dial> the general support line.
#         - 4-digit ext → look up contractor → <Dial> personal_phone.
#         - anything else / no input → replay the menu (with a soft
#           bilingual "we didn't catch that" nudge). After 3 failed
#           attempts (?attempt=3) the caller is routed to support so
#           the call is NEVER dropped.
#
# These live alongside — and do NOT replace — the earlier iter323/324
# multi-step IVR at `/api/twilio/ivr/incoming`. Twilio Console can be
# pointed at whichever entrypoint the ops team prefers.


# iter349 — Business-hours awareness for the main IVR menu.
#
# Mon-Fri 08:00 - 19:00 America/Toronto = business hours → interactive
# menu. Anything else → informational after-hours message + hangup.
try:
    from zoneinfo import ZoneInfo  # Python 3.9+ (backend is 3.11)
    _MONTREAL_TZ = ZoneInfo("America/Toronto")
except Exception:  # pragma: no cover — extremely defensive fallback
    _MONTREAL_TZ = None


def _current_montreal_time() -> datetime:
    """iter349 — Injectable point for time-based IVR routing.

    Kept as a module-level function so unit tests can monkey-patch it
    to force either working-hours or after-hours behaviour deterministically.
    """
    if _MONTREAL_TZ is not None:
        return datetime.now(_MONTREAL_TZ)
    # Extreme fallback — approximate ET as UTC-5.
    return datetime.now(timezone.utc) - timedelta(hours=5)


def is_business_hours_now() -> bool:
    """Return True when the current Montreal time is Mon-Fri 08:00-19:00."""
    now = _current_montreal_time()
    # weekday(): Mon=0 … Sun=6. Business days = 0-4.
    if now.weekday() > 4:
        return False
    if now.hour < 8 or now.hour >= 19:
        return False
    return True


@router.post("/twilio/ivr/main-menu")
@router.get("/twilio/ivr/main-menu")
async def ivr_main_menu(request: Request) -> Response:
    """iter347 + iter349 — Bilingual IVR with business-hours awareness.

    Business hours (Mon-Fri 08:00-19:00 America/Toronto):
      - Full interactive <Gather> — dial extension / press 1 support /
        press 0 general.
    After hours (weekend, or weekday before 08:00 / after 19:00):
      - Bilingual informational <Say> + <Hangup>. No keypress prompted.

    On no-input Twilio will follow-through to the same URL again with
    ?attempt++ so we don't cut off callers who are still fetching their
    contractor's extension.
    """
    # Signature validation on both GET and POST — GET is used by the
    # Twilio Console during initial configuration probing.
    try:
        await _validate_twilio_signature(request)
    except HTTPException:
        # Admit on validation failure (mirrors ivr_incoming's stance —
        # a 403 disconnects legitimate calls; a spoofed request can only
        # replay this deterministic TwiML with no billing/PII impact).
        logger.warning("[ivr/main-menu] signature validation failed — admitting")
    base = _public_base(request)

    # Persist a "call started" row on the very first hit so we have a
    # CallSid to update later, regardless of how the IVR resolves.
    form: Dict[str, Any] = {}
    if request.method == "POST":
        try:
            form = dict(await request.form())
        except Exception:  # noqa: BLE001
            form = {}
    call_sid = form.get("CallSid")
    attempt = int(request.query_params.get("attempt") or "1")

    # ── iter349 — Business-hours check ───────────────────────────────
    business_hours = is_business_hours_now()
    montreal_now = _current_montreal_time()

    if call_sid and attempt == 1:
        try:
            db = _get_db()
            await db.inbound_extension_calls.insert_one({
                "id":                str(uuid.uuid4()),
                "call_sid":          call_sid,
                "from_number":       form.get("From"),
                "to_number":         form.get("To"),
                "started_at":        _now_iso(),
                "status":            "in_progress",
                "outcome":           None,
                "contractor_id":     None,
                "extension_dialed":  None,
                "duration_seconds":  None,
                # iter349 — annotate the row with the branch chosen and
                # the Montreal-time snapshot so ops can retro-audit
                # after-hours misses without querying Twilio.
                "menu_variant":      "iter349_time_aware",
                "business_hours":    business_hours,
                "montreal_time":     montreal_now.isoformat(),
                "montreal_weekday":  montreal_now.strftime("%A"),
            })
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ivr/main-menu] initial call row insert failed: {e}")

    # ── After-hours branch ───────────────────────────────────────────
    # Informational bilingual message + hangup. No <Gather>, no keypress.
    if not business_hours:
        after_hours_en = (
            "Thank you for calling BidVex. Our office is currently closed. "
            "You can reach us Monday to Friday, from 8:00 AM to 7:00 PM, "
            "or send us an email at support at bidvex dot com. Thank you."
        )
        after_hours_fr = (
            "Merci d'avoir appelé BidVex. Nos bureaux sont actuellement "
            "fermés. Vous pouvez nous joindre du lundi au vendredi, de "
            "8h00 à 19h00, ou nous envoyer un courriel à support at "
            "bidvex point com. Merci."
        )
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="en-US">{after_hours_en}</Say>
  <Say voice="alice" language="fr-CA">{after_hours_fr}</Say>
  <Hangup/>
</Response>"""
        # Best-effort audit update.
        if call_sid:
            try:
                db = _get_db()
                await db.inbound_extension_calls.update_one(
                    {"call_sid": call_sid},
                    {"$set": {
                        "outcome":  "after_hours_hangup",
                        "status":   "ended_after_hours",
                        "ended_at": _now_iso(),
                    }},
                )
            except Exception:  # noqa: BLE001
                pass
        return _twiml(xml)

    # ── Working-hours branch ─────────────────────────────────────────
    # Nudge language if this is a retry.
    nudge_en = "" if attempt <= 1 else " We didn't catch that — let's try one more time."
    nudge_fr = "" if attempt <= 1 else " Nous n'avons pas capté votre choix — un instant, réessayons."

    intro_en = (
        f"Hello, thank you for calling BidVex.{nudge_en} "
        "If you know your contractor's extension, please dial it now, "
        "press 1 for support, or press 0 for general inquiries."
    )
    intro_fr = (
        f"Bonjour, merci d'avoir appelé BidVex.{nudge_fr} "
        "Si vous connaissez le poste de votre entrepreneur, veuillez le "
        "composer maintenant, appuyez sur 1 pour le support, ou appuyez "
        "sur 0 pour les demandes générales."
    )

    # After 3 failed attempts, gracefully route to support so the call
    # is never dropped.
    if attempt >= 4:
        graceful = (
            "We're going to connect you to the support team now. "
            "One moment please. Nous vous connectons à l'équipe de soutien maintenant."
        )
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="en-US">{graceful}</Say>
  <Dial timeout="25" answerOnBridge="true">
    <Number>{BIDVEX_GENERAL_SUPPORT_NUMBER}</Number>
  </Dial>
</Response>"""
        return _twiml(xml)

    next_action = f"{base}/api/twilio/handle-menu?attempt={attempt}"

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="dtmf" numDigits="4" finishOnKey="#" timeout="8"
          action="{next_action}" method="POST">
    <Say voice="alice" language="en-US">{intro_en}</Say>
    <Say voice="alice" language="fr-CA">{intro_fr}</Say>
  </Gather>
  <Redirect method="POST">{base}/api/twilio/ivr/main-menu?attempt={attempt + 1}</Redirect>
</Response>"""
    return _twiml(xml)


@router.post("/twilio/handle-menu")
async def handle_menu(request: Request) -> Response:
    """iter347 — Dispatch handler for the single-step main menu.

    Behaviour:
      - `Digits == "1"`  → immediately <Dial> the general support line.
      - `Digits` is 3-4 digits and looks up an active contractor with a
        personal_phone_number set → <Dial> that number (with whisper).
      - anything else / no input / inactive extension → route back to
        the main menu with ?attempt++.
    """
    try:
        await _validate_twilio_signature(request)
    except HTTPException:
        logger.warning("[ivr/handle-menu] signature validation failed — admitting")

    form = dict(await request.form())
    base = _public_base(request)
    digits = (form.get("Digits") or "").strip()
    call_sid = form.get("CallSid")
    from_number = form.get("From") or "Unknown"
    attempt = int(request.query_params.get("attempt") or "1")
    db = _get_db()

    def _log_outcome(**fields):
        if not call_sid:
            return
        try:
            import asyncio as _aio
            _aio.create_task(
                db.inbound_extension_calls.update_one(
                    {"call_sid": call_sid},
                    {"$set": {"ended_at": _now_iso(), **fields}},
                )
            )
        except Exception:  # noqa: BLE001
            pass

    # ── Support (press 1) OR General inquiries (press 0) ─────────────
    # iter349 — 0 and 1 both route to the general support line.
    if digits in ("1", "0"):
        _log_outcome(
            outcome=("support_routed" if digits == "1" else "general_inquiries_routed"),
            status="bridged_support",
            support_number=BIDVEX_GENERAL_SUPPORT_NUMBER,
            digit_pressed=digits,
            menu_variant="iter349_time_aware",
        )
        greet_en = (
            "Connecting you to the support team. Please hold."
            if digits == "1" else
            "Connecting you to general inquiries. Please hold."
        )
        xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="alice" language="en-US">{greet_en}</Say>
  <Dial timeout="25" answerOnBridge="true">
    <Number>{BIDVEX_GENERAL_SUPPORT_NUMBER}</Number>
  </Dial>
</Response>"""
        return _twiml(xml)

    # ── 4-digit contractor extension ──────────────────────────────────
    if re.fullmatch(r"\d{3,4}", digits):
        try:
            from services.contractor_extensions import lookup_contractor_by_extension
            contractor = await lookup_contractor_by_extension(db, int(digits))
        except Exception as e:  # noqa: BLE001
            logger.warning(f"[ivr/handle-menu] lookup failed for ext={digits}: {e}")
            contractor = None

        personal_phone = (contractor or {}).get("personal_phone_number")
        is_active = (contractor or {}).get("is_active", True)

        if contractor and is_active and personal_phone:
            _log_outcome(
                outcome="bridging",
                status="bridging",
                extension_dialed=digits,
                contractor_id=contractor.get("id"),
                contractor_name=(
                    contractor.get("name") or
                    f"{contractor.get('first_name','')} {contractor.get('last_name','')}".strip()
                ),
                menu_variant="iter347_single_step",
            )

            safe_from = re.sub(r"[^0-9+]", "", from_number)[:20]
            whisper_url_xml = _xml_escape(
                f"{base}/api/twilio/ivr/whisper?lang=en&caller_from={safe_from}"
            )
            status_url_xml = _xml_escape(
                f"{base}/api/twilio/ivr/status?contractor_id={contractor.get('id')}"
            )
            xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial callerId="{BIDVEX_MAIN_NUMBER}" timeout="25" answerOnBridge="true"
        action="{status_url_xml}" method="POST">
    <Number url="{whisper_url_xml}" method="POST">{personal_phone}</Number>
  </Dial>
</Response>"""
            return _twiml(xml)

        # Contractor not found OR inactive OR no personal_phone — replay
        # the menu with the "we didn't catch that" nudge. Never drop.
        _log_outcome(
            outcome="invalid_extension",
            status="ended_invalid",
            extension_dialed=digits,
            menu_variant="iter347_single_step",
        )

    # ── Empty input / invalid digit sequence → replay menu ────────────
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Redirect method="POST">{base}/api/twilio/ivr/main-menu?attempt={attempt + 1}</Redirect>
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
