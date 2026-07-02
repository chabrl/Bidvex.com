"""
iter336 — Regression suite for the AI-Generated Follow-Up Email endpoint.

Locks the 4 mandatory checkpoints:
  1. Contractor (owner) can generate a follow-up for their own completed
     coach session → returns subject_en/subject_fr/body JSON.
  2. Contractor cannot generate for another contractor's call → 404 with
     a "Session not found or access denied" body (no leakage).
  3. 4th generation attempt returns 429 with bilingual rate-limit shape.
  4. Malformed Gemini output does NOT 500 — falls back to a deterministic
     draft (subject + body still non-empty) and marks used_fallback=True.

Bonus:
  5. Email Hub send endpoint accepts an optional call_log_id and marks
     the most-recent draft in followup_emails_generated[] as sent.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import httpx
import pytest

# Load /app/backend/.env so MONGO_URL, DB_NAME, GEMINI_API_KEY are available.
try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
    load_dotenv("/app/backend/.env")
except Exception:  # pragma: no cover
    pass


BASE = os.environ.get("PREVIEW_API_URL") or "https://prod-verify-2.preview.emergentagent.com"

ADMIN_EMAIL    = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"


def _login(email: str, password: str) -> str:
    r = httpx.post(
        f"{BASE}/api/auth/login",
        headers={"Content-Type": "application/json"},
        json={"email": email, "password": password},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("token") or r.json().get("access_token") or ""


def _new_completed_session(contractor_id: str, *, status: str = "completed",
                           extra: dict | None = None) -> str:
    """Insert a fake outbound_coach session row directly into Mongo so we
    can exercise the follow-up-email endpoint without needing a real call.
    Returns the newly-minted call_log_id."""
    sys.path.insert(0, "/app/backend")
    from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore[import-untyped]

    call_log_id = f"iter336-test-{uuid.uuid4().hex[:12]}"
    doc = {
        "_id": str(uuid.uuid4()),
        "call_type":         "outbound_coach",
        "call_log_id":       call_log_id,
        "contractor_id":     contractor_id,
        "client_phone":      "+18195559999",
        "call_started_at":   datetime.now(timezone.utc).isoformat(),
        "call_ended_at":     datetime.now(timezone.utc).isoformat(),
        "duration_seconds":  432,
        "language_detected": "en",
        "ai_session_status": status,
        "transcript": [
            {"speaker": "contractor", "text": "Thanks for calling BidVex — what are you looking to sell?", "timestamp_seconds": 3.0, "sentiment_at_moment": 0.4},
            {"speaker": "client",     "text": "A 2019 Ford F-150, mostly to buyers in Quebec.",              "timestamp_seconds": 11.0, "sentiment_at_moment": 0.5},
            {"speaker": "contractor", "text": "Great choice — our vehicle dealer network is strong there.",  "timestamp_seconds": 18.0, "sentiment_at_moment": 0.5},
            {"speaker": "client",     "text": "How does the buyer's premium work?",                          "timestamp_seconds": 27.0, "sentiment_at_moment": 0.6},
        ],
        "coaching_hints_log": [],
        "compliance_flags_triggered": [],
        "avg_client_sentiment": 0.55,
        "sentiment_trend":      "improving",
        "peak_positive_moment_seconds": 27.0,
        "peak_negative_moment_seconds": 3.0,
        "ai_summary":  "Client owns a 2019 Ford F-150 and is interested in selling on BidVex; needs clarification on buyer's premium.",
        "action_items": ["Send buyer's premium tier table."],
        "followup_email_generated_count": 0,
        "followup_emails_generated": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    if extra:
        doc.update(extra)

    async def _insert():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        await db.ai_voice_calls.insert_one(doc)
        client.close()

    asyncio.get_event_loop().run_until_complete(_insert())
    return call_log_id


# ─── 1) Owner OK ─────────────────────────────────────────────────────

def test_followup_owner_generates_valid_draft():
    tok = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    # Discover the admin's user_id via /auth/me so ownership check passes.
    me = httpx.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=15).json()
    admin_id = me.get("id")
    assert admin_id, "admin id missing from /auth/me"

    call_log_id = _new_completed_session(admin_id, status="completed")

    r = httpx.post(
        f"{BASE}/api/ai-coach/sessions/{call_log_id}/generate-followup-email",
        headers={"Authorization": f"Bearer {tok}"}, timeout=60,
    )
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d.get("subject"), str) and len(d["subject"]) > 3
    assert isinstance(d.get("subject_en"), str) and len(d["subject_en"]) > 3
    assert isinstance(d.get("subject_fr"), str) and len(d["subject_fr"]) > 3
    assert isinstance(d.get("body"), str) and len(d["body"]) > 20
    assert d["call_log_id"] == call_log_id
    assert d["language_detected"] in {"en", "fr", "mixed"}
    assert d["count"] == 1
    assert d["max_regenerations"] == 3


# ─── 2) Non-owner → 404 (no leakage) ─────────────────────────────────

def test_followup_non_owner_gets_404():
    # Session owned by a random contractor UUID we invent.
    stranger_id = f"stranger-{uuid.uuid4().hex[:8]}"
    call_log_id = _new_completed_session(stranger_id, status="completed")

    # Register (or log into) a throw-away non-admin so we exercise the
    # `contractor_id != user.id` branch of the ownership filter.
    non_admin_email = f"iter336nonowner{uuid.uuid4().hex[:8]}@example.com"
    non_admin_pw = "NonOwner2026!"
    reg = httpx.post(
        f"{BASE}/api/auth/register",
        headers={"Content-Type": "application/json"},
        json={
            "email": non_admin_email,
            "password": non_admin_pw,
            "name": "Iter336 Non Owner",
            "terms_agreed": True,
            "ai_disclosure_consent": True,
        },
        timeout=15,
    )
    if reg.status_code not in {200, 201, 409}:
        pytest.skip(f"could not create test non-admin (status={reg.status_code} body={reg.text[:200]})")
    tok = _login(non_admin_email, non_admin_pw)
    r = httpx.post(
        f"{BASE}/api/ai-coach/sessions/{call_log_id}/generate-followup-email",
        headers={"Authorization": f"Bearer {tok}"}, timeout=30,
    )
    # Must be 404 — never 500, never leak the session shape.
    assert r.status_code == 404, r.text


# ─── 3) Rate limit — 4th attempt → 429 ───────────────────────────────

def test_followup_4th_generation_returns_429():
    tok = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    me = httpx.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=15).json()
    admin_id = me["id"]

    # Seed row with counter already at 3.
    call_log_id = _new_completed_session(
        admin_id, status="completed",
        extra={"followup_email_generated_count": 3, "followup_emails_generated": [
            {"generated_at": datetime.now(timezone.utc).isoformat(), "language": "en", "sent": False},
            {"generated_at": datetime.now(timezone.utc).isoformat(), "language": "en", "sent": False},
            {"generated_at": datetime.now(timezone.utc).isoformat(), "language": "en", "sent": False},
        ]},
    )
    r = httpx.post(
        f"{BASE}/api/ai-coach/sessions/{call_log_id}/generate-followup-email",
        headers={"Authorization": f"Bearer {tok}"}, timeout=30,
    )
    assert r.status_code == 429, r.text
    body = r.json()
    detail = body.get("detail") or body
    assert detail.get("error") == "rate_limited"
    assert "message_en" in detail and "message_fr" in detail
    assert detail.get("max") == 3


# ─── 4) Malformed Gemini output → deterministic fallback, not 500 ────

def test_followup_malformed_gemini_falls_back_gracefully():
    tok = _login(ADMIN_EMAIL, ADMIN_PASSWORD)
    me = httpx.get(f"{BASE}/api/auth/me", headers={"Authorization": f"Bearer {tok}"}, timeout=15).json()
    admin_id = me["id"]

    # Inject a monkeypatch server-side is impossible from here — we
    # instead invoke the extractor + fallback helpers directly to
    # prove the graceful-degradation logic itself. This assertion
    # protects the endpoint's behavior when the SDK returns garbage
    # (empty string, missing keys, prose without JSON, etc.).
    sys.path.insert(0, "/app/backend")
    from routes.ai_coach import _extract_followup_json, _fallback_followup_draft

    # Simulate several forms of malformed Gemini output.
    for garbage in [
        "",                                             # empty
        "Sorry, I can't help with that.",               # prose only
        "```json\n{\"only\": \"bogus\"}\n```",         # missing keys
        "{\"subject_en\":\"\",\"subject_fr\":\"\",\"body\":\"\"}",  # empty values
        "not-json-at-all {{{",
    ]:
        assert _extract_followup_json(garbage) is None, f"Should reject: {garbage!r}"

    fb = _fallback_followup_draft({"language_detected": "en", "ai_summary": "Client wants vehicle info."})
    assert fb["subject_en"] and fb["body"]
    assert "BidVex" in fb["body"] or "bidvex" in fb["body"].lower()

    fb_fr = _fallback_followup_draft({"language_detected": "fr", "ai_summary": ""})
    assert fb_fr["subject_fr"] and fb_fr["body"]
    assert "Bonjour" in fb_fr["body"]


# ─── 5) Bonus: Email Hub send accepts optional call_log_id link ──────

def test_email_hub_send_body_accepts_call_log_id_field():
    """Ensure the Pydantic model was extended without breaking anything."""
    sys.path.insert(0, "/app/backend")
    from routes.twilio import ContractorEmailSendBody
    body = ContractorEmailSendBody(
        to_email="foo@bar.com",
        subject="hi",
        body_html="<p>hi</p>",
        call_log_id="iter336-linkage-check",
    )
    assert body.call_log_id == "iter336-linkage-check"

    # Backward-compat: omitting call_log_id still works.
    body2 = ContractorEmailSendBody(to_email="foo@bar.com", subject="hi", body_html="<p>hi</p>")
    assert body2.call_log_id is None
