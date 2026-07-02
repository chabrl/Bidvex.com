"""
iter336 — End-to-end API integration test that mirrors the frontend flow.

1. Login as admin.
2. Insert a completed outbound_coach session directly into MongoDB
   (owned by the admin) so the ownership filter passes.
3. POST /api/ai-coach/sessions/{call_log_id}/generate-followup-email
   → assert 200 + expected shape.
4. POST /api/twilio/contractor/emails/send with the returned subject/body
   AND the linking `call_log_id` → assert 200.
5. Query MongoDB directly to confirm:
     • ai_voice_calls.followup_emails_generated[0].sent === True
     • ai_voice_calls.followup_emails_generated[0].sent_at is set
     • contractor_emails collection has a row with linked_call_log_id
       matching the seeded session.
6. Cleanup: delete seeded ai_voice_calls row + created contractor_emails row.
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timezone

import httpx
import pytest

try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
    load_dotenv("/app/backend/.env")
except Exception:
    pass

BASE = os.environ.get("PREVIEW_API_URL") or "https://prod-verify-2.preview.emergentagent.com"
ADMIN_EMAIL    = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"

sys.path.insert(0, "/app/backend")
from motor.motor_asyncio import AsyncIOMotorClient  # noqa: E402


def _login() -> str:
    r = httpx.post(f"{BASE}/api/auth/login",
                   json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
                   timeout=15)
    r.raise_for_status()
    return r.json().get("token") or r.json().get("access_token")


def _admin_id(tok: str) -> str:
    r = httpx.get(f"{BASE}/api/auth/me",
                  headers={"Authorization": f"Bearer {tok}"}, timeout=15)
    r.raise_for_status()
    return r.json()["id"]


def _seed_session(contractor_id: str) -> str:
    call_log_id = f"iter336-e2e-{uuid.uuid4().hex[:12]}"
    doc = {
        "_id": str(uuid.uuid4()),
        "call_type": "outbound_coach",
        "call_log_id": call_log_id,
        "contractor_id": contractor_id,
        "client_phone": "+18195559999",
        "call_started_at": datetime.now(timezone.utc).isoformat(),
        "call_ended_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": 300,
        "language_detected": "en",
        "ai_session_status": "completed",
        "transcript": [
            {"speaker": "contractor", "text": "Hi thanks for calling BidVex.", "timestamp_seconds": 3.0},
            {"speaker": "client",     "text": "I have a 2019 F-150 to sell.",   "timestamp_seconds": 11.0},
        ],
        "coaching_hints_log": [],
        "compliance_flags_triggered": [],
        "avg_client_sentiment": 0.55,
        "sentiment_trend": "improving",
        "ai_summary": "Client wants to sell a 2019 F-150.",
        "action_items": ["Send tiers info."],
        "followup_email_generated_count": 0,
        "followup_emails_generated": [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    async def _do():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        await db.ai_voice_calls.insert_one(doc)
        client.close()
    asyncio.get_event_loop().run_until_complete(_do())
    return call_log_id


def _cleanup(call_log_id: str, to_email: str):
    async def _do():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        await db.ai_voice_calls.delete_many({"call_log_id": call_log_id})
        await db.contractor_emails.delete_many({"to_email": to_email})
        client.close()
    try:
        asyncio.get_event_loop().run_until_complete(_do())
    except Exception:
        pass


def test_full_ai_followup_email_flow_with_mongo_verification():
    tok = _login()
    admin_id = _admin_id(tok)
    call_log_id = _seed_session(admin_id)
    to_email = f"iter336-linkage-{uuid.uuid4().hex[:6]}@example.com"

    try:
        # Step 1 — Generate follow-up draft
        gen = httpx.post(
            f"{BASE}/api/ai-coach/sessions/{call_log_id}/generate-followup-email",
            headers={"Authorization": f"Bearer {tok}"}, timeout=60,
        )
        assert gen.status_code == 200, gen.text
        d = gen.json()
        assert d["count"] == 1
        assert d["max_regenerations"] == 3
        assert d["call_log_id"] == call_log_id
        subject = d["subject"]
        body = d["body"]
        assert len(subject) > 3
        assert len(body) > 20

        # Step 2 — Send via contractor email hub WITH call_log_id link
        send = httpx.post(
            f"{BASE}/api/twilio/contractor/emails/send",
            headers={"Authorization": f"Bearer {tok}"},
            json={
                "to_email": to_email,
                "subject": subject,
                "body_html": f"<p>{body}</p>",
                "locale": "en",
                "call_log_id": call_log_id,
            },
            timeout=45,
        )
        assert send.status_code == 200, send.text

        # Step 3 — Verify Mongo state
        async def _verify():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = client[os.environ["DB_NAME"]]
            row = await db.ai_voice_calls.find_one({"call_log_id": call_log_id})
            emails = await db.contractor_emails.find({"to_email": to_email}).to_list(length=10)
            client.close()
            return row, emails

        row, emails = asyncio.get_event_loop().run_until_complete(_verify())

        assert row is not None
        entries = row.get("followup_emails_generated") or []
        assert len(entries) >= 1, f"Expected followup_emails_generated to have entries: {entries}"
        # At least one entry should have sent=True
        sent_entries = [e for e in entries if e.get("sent") is True]
        assert len(sent_entries) >= 1, f"No entry has sent=True: {entries}"
        assert sent_entries[0].get("sent_at"), "sent_at not set on the sent entry"

        # And a contractor_emails row was created for the recipient.
        assert len(emails) >= 1, "No contractor_emails row was created"
        email_row = emails[0]
        # Design: reverse link is stored on the ai_voice_calls doc as
        # followup_emails_generated.$.email_row_id, pointing to the newly
        # created contractor_emails row. Verify that back-reference matches.
        email_row_id = email_row.get("id") or str(email_row.get("_id"))
        linked_ids = [e.get("email_row_id") for e in entries if e.get("sent")]
        assert email_row_id in linked_ids, (
            f"contractor_emails row id {email_row_id!r} not linked back into "
            f"ai_voice_calls.followup_emails_generated[$].email_row_id "
            f"(found: {linked_ids})"
        )

    finally:
        _cleanup(call_log_id, to_email)


def test_rate_limit_returns_429_via_ui_flow():
    """Simulate the UI path when the contractor exceeds 3 generations."""
    tok = _login()
    admin_id = _admin_id(tok)

    # Seed session already at cap
    call_log_id = f"iter336-e2e-{uuid.uuid4().hex[:12]}"
    doc = {
        "_id": str(uuid.uuid4()),
        "call_type": "outbound_coach",
        "call_log_id": call_log_id,
        "contractor_id": admin_id,
        "client_phone": "+18195559999",
        "call_started_at": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": 300,
        "language_detected": "en",
        "ai_session_status": "completed",
        "transcript": [{"speaker": "contractor", "text": "hi", "timestamp_seconds": 1.0}],
        "followup_email_generated_count": 3,
        "followup_emails_generated": [
            {"generated_at": datetime.now(timezone.utc).isoformat(), "language": "en", "sent": False}
        ] * 3,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    async def _do():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        await db.ai_voice_calls.insert_one(doc)
        client.close()
    asyncio.get_event_loop().run_until_complete(_do())

    try:
        r = httpx.post(
            f"{BASE}/api/ai-coach/sessions/{call_log_id}/generate-followup-email",
            headers={"Authorization": f"Bearer {tok}"}, timeout=30,
        )
        assert r.status_code == 429, r.text
        detail = r.json().get("detail") or r.json()
        assert detail.get("error") == "rate_limited"
        assert "message_en" in detail
        assert "message_fr" in detail
    finally:
        async def _clean():
            client = AsyncIOMotorClient(os.environ["MONGO_URL"])
            db = client[os.environ["DB_NAME"]]
            await db.ai_voice_calls.delete_many({"call_log_id": call_log_id})
            client.close()
        asyncio.get_event_loop().run_until_complete(_clean())
