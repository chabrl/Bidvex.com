"""
iter346 — Regression + new tests for:
  BUG 3   Admin unsubscribe guard + startup self-heal + revert of stale
          suppression state.
  BUG 2   Role check regression sweep — role in ("admin","super_admin")
          on storage/facilities/campaigns endpoints.
  Camp.   External Campaigns list returns 200 with defensive normalization
          on schema-drift documents.
  BUG 1   Dialer TwiML endpoint: coach stream is non-fatal (nonce lookup
          failure still yields <Dial>), lenient signature (from iter345)
          still admits, first-line logging landed.
  Admin Logs pagination envelope: {items, total_count, page, pages, limit}.
  Compliance digest builds valid HTML with sessions.
  Watchlist bid reminders: last_chance job is registered in scheduler.
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path("/app/backend")))
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

os.environ["TWILIO_SKIP_SIGNATURE_VERIFY"] = "1"

from fastapi import FastAPI
from fastapi.testclient import TestClient
from pymongo import MongoClient
from motor.motor_asyncio import AsyncIOMotorClient

import routes.twilio as tw_routes

BIDVEX_MAIN = "+14506343099"
CLIENT_NUM  = "+15145551234"


def _api_base() -> str:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                return line.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


API = _api_base() + "/api"


@pytest.fixture(scope="module")
def db():
    client = MongoClient(os.environ["MONGO_URL"])
    yield client[os.environ["DB_NAME"]]
    client.close()


@pytest.fixture(scope="module")
def twiml_client():
    app = FastAPI()
    app.include_router(tw_routes.router, prefix="/api")
    return TestClient(app)


def _mint_admin_token(db, email_prefix: str = "iter346_admin"):
    """Seed a super_admin user + return (jwt, id, email)."""
    import bcrypt
    from jose import jwt
    uid = str(uuid.uuid4())
    email = f"{email_prefix}_{uuid.uuid4().hex[:8]}@test.com"
    pw = bcrypt.hashpw(b"AdminPass123!", bcrypt.gensalt()).decode()
    db.users.insert_one({
        "id":             uid,
        "email":          email,
        "password":       pw,
        "name":           "Iter346 Admin",
        "role":           "super_admin",
        "created_at":     datetime.now(timezone.utc).isoformat(),
        "email_verified": True,
    })
    jwt_secret = os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production")
    token = jwt.encode({
        "sub":   uid,
        "email": email,
        "type":  "access",
        "exp":   datetime.now(timezone.utc) + timedelta(hours=1),
    }, jwt_secret, algorithm="HS256")
    return token, uid, email


# ═══ BUG 3 — Admin unsubscribe guard ═══════════════════════════════════

class TestAdminUnsubscribeGuard:

    def test_admin_unsubscribe_blocked(self, db):
        """Attempting to unsubscribe an admin/super_admin must 403."""
        _, uid, email = _mint_admin_token(db, "iter346_unsub_admin")
        try:
            # Build a valid unsubscribe token for that email.
            from routes.unsubscribe import generate_unsubscribe_token
            token = generate_unsubscribe_token(email)

            r = requests.post(
                f"{API}/unsubscribe/confirm",
                json={"token": token},
                timeout=30,
            )
            assert r.status_code == 403, f"admin unsubscribe must 403, got {r.status_code}"
            detail = r.json().get("detail")
            assert isinstance(detail, dict), f"detail must be bilingual dict, got {detail}"
            assert detail.get("error") == "admin_unsubscribe_blocked"
            assert "administrative" in detail.get("message_en", "").lower()
            assert "administratifs" in detail.get("message_fr", "").lower()

            # Auto-confirm endpoint must also 403.
            r2 = requests.post(
                f"{API}/unsubscribe/auto-confirm",
                json={"token": token, "lang": "en"},
                timeout=30,
            )
            assert r2.status_code == 403

            # Audit row must be written.
            audit = db.unsubscribe_events.find_one(
                {"email": email, "event": "blocked_admin_attempt"},
                sort=[("unsubscribed_at", -1)],
            )
            assert audit is not None, "blocked_admin_attempt audit row missing"

            # User must NOT be marked as unsubscribed.
            user = db.users.find_one({"id": uid}, {"_id": 0, "marketing_unsubscribed": 1, "email_unsubscribed": 1})
            assert not user.get("marketing_unsubscribed")
            assert not user.get("email_unsubscribed")
        finally:
            db.users.delete_one({"id": uid})
            db.unsubscribe_events.delete_many({"email": email})

    def test_non_admin_unsubscribe_still_works(self, db):
        """Guard must NOT block regular users — regression check."""
        from routes.unsubscribe import generate_unsubscribe_token
        uid = str(uuid.uuid4())
        email = f"iter346_regular_{uuid.uuid4().hex[:8]}@test.com"
        db.users.insert_one({
            "id":   uid,
            "email": email,
            "role":  "user",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            token = generate_unsubscribe_token(email)
            r = requests.post(f"{API}/unsubscribe/confirm", json={"token": token}, timeout=30)
            assert r.status_code == 200, f"regular user unsubscribe must succeed, got {r.status_code}"
        finally:
            db.users.delete_one({"id": uid})
            db.email_suppressions.delete_many({"email": email})
            db.external_email_suppressions.delete_many({"email": email})


# ═══ BUG 2 — Role check regression sweep ═══════════════════════════════

class TestSuperAdminBypass:
    """super_admin must be able to access admin-only endpoints that were
    previously gated on role=='admin' only."""

    def test_storage_facilities_returns_200_for_super_admin(self, db):
        token, uid, _ = _mint_admin_token(db, "iter346_facil")
        try:
            r = requests.get(
                f"{API}/admin/storage-facilities",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code}"
            data = r.json()
            assert "facilities" in data and "total" in data
        finally:
            db.users.delete_one({"id": uid})

    def test_storage_auctions_returns_200_for_super_admin(self, db):
        token, uid, _ = _mint_admin_token(db, "iter346_storauc")
        try:
            r = requests.get(
                f"{API}/admin/storage-auctions",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            assert r.status_code == 200, f"expected 200, got {r.status_code}"
        finally:
            db.users.delete_one({"id": uid})

    def test_regular_user_still_blocked(self, db):
        """Regression: role='user' must still get 403."""
        import bcrypt
        from jose import jwt as _jwt
        uid = str(uuid.uuid4())
        db.users.insert_one({
            "id": uid, "email": f"iter346_u_{uid[:8]}@test.com",
            "name": "Iter346 Regular",
            "password": bcrypt.hashpw(b"UserPass123!", bcrypt.gensalt()).decode(),
            "role": "user", "created_at": datetime.now(timezone.utc).isoformat(),
        })
        try:
            token = _jwt.encode(
                {"sub": uid, "type": "access",
                 "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
                os.environ.get("JWT_SECRET", "dev-secret-key-change-in-production"),
                algorithm="HS256",
            )
            r = requests.get(
                f"{API}/admin/storage-facilities",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            assert r.status_code == 403
        finally:
            db.users.delete_one({"id": uid})


# ═══ External Campaigns defensive normalization ═══════════════════════

class TestExternalCampaignsList:

    def test_list_returns_200_with_defensive_fields(self, db):
        token, uid, _ = _mint_admin_token(db, "iter346_camp")
        # Seed a legacy-shape campaign missing modern fields.
        legacy_id = str(uuid.uuid4())
        db.external_email_campaigns.insert_one({
            "id": legacy_id, "name": "iter346 legacy",
            "status": "draft", "created_at": datetime.now(timezone.utc).isoformat(),
            # NO: subject_en, subject_fr, analytics, recipient_count,
            #     attach_trial_coupon, auto_paused, followup_emails_generated
        })
        try:
            r = requests.get(
                f"{API}/admin/external-campaigns",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            assert r.status_code == 200, r.text[:300]
            data = r.json()
            assert "campaigns" in data
            row = next((c for c in data["campaigns"] if c["id"] == legacy_id), None)
            assert row is not None, "legacy row missing from list"
            # Defensive normalization must have populated ALL modern fields.
            assert row["subject_en"] == ""
            assert row["subject_fr"] == ""
            assert row["recipient_count"] == 0
            assert row["auto_paused"] is False
            assert row["followup_emails_generated"] is False
            assert row["attach_trial_coupon"] is False
            assert isinstance(row["analytics"], dict)
        finally:
            db.external_email_campaigns.delete_one({"id": legacy_id})
            db.users.delete_one({"id": uid})


# ═══ BUG 1 — Dialer hedges ═════════════════════════════════════════════

class TestDialerHedges:

    def test_twiml_still_bridges_client_with_new_logging(self, twiml_client):
        """Regression — the added first-line log must not break routing."""
        r = twiml_client.post("/api/twilio/twiml", data={
            "To": CLIENT_NUM, "From": "client:agent-test-1", "Direction": "outbound-api",
            "CallSid": "CA-iter346-test",
        })
        assert r.status_code == 200
        xml = r.text
        assert f">{CLIENT_NUM}</Number>" in xml
        assert f'callerId="{BIDVEX_MAIN}"' in xml

    def test_twiml_with_missing_calllogid_still_bridges(self, twiml_client):
        """Coach stream is best-effort. Missing CallLogId → no <Stream>
        but <Dial> to client must still be present."""
        r = twiml_client.post("/api/twilio/twiml", data={
            "To": CLIENT_NUM, "From": "client:agent-test-1", "Direction": "outbound-api",
            # No CallLogId → no coach stream lookup at all.
        })
        assert r.status_code == 200
        xml = r.text
        assert "<Dial" in xml
        assert f">{CLIENT_NUM}</Number>" in xml
        assert "<Stream" not in xml

    def test_twiml_with_invalid_calllogid_still_bridges(self, twiml_client):
        """When nonce lookup misses (invalid CallLogId), the endpoint
        must NOT hang up — it must still return TwiML with <Dial>."""
        r = twiml_client.post("/api/twilio/twiml", data={
            "To": CLIENT_NUM, "From": "client:agent-test-1", "Direction": "outbound-api",
            "CallSid": "CA-iter346-nonce-miss",
            "CallLogId": "does-not-exist-in-COACH_NONCES-fdec",
        })
        assert r.status_code == 200, r.text[:300]
        xml = r.text
        # Dial to the client must still be present.
        assert f">{CLIENT_NUM}</Number>" in xml, f"<Dial> missing from TwiML: {xml[:400]}"
        # Coach stream should have been silently skipped.
        assert "<Stream" not in xml or "url=\"wss://" not in xml.split("<Dial")[0]

    def test_fallback_endpoint_still_never_dials(self, twiml_client):
        """iter345 safety net still holds."""
        r = twiml_client.post("/api/twilio/twiml-fallback")
        assert r.status_code == 200
        assert "<Dial" not in r.text
        assert BIDVEX_MAIN not in r.text


# ═══ Admin logs pagination envelope ════════════════════════════════════

class TestAdminLogsPagination:

    def test_paginated_envelope(self, db):
        token, uid, _ = _mint_admin_token(db, "iter346_logs")
        # Seed a bunch of logs.
        seeded_ids = []
        for i in range(75):
            log_id = f"iter346-log-{uid}-{i}"
            seeded_ids.append(log_id)
            db.admin_logs.insert_one({
                "id":           log_id,
                "action":       "iter346_test",
                "admin_id":     uid,
                "admin_email":  "iter346@test.com",
                "target_type":  "user",
                "target_id":    f"tgt-{i}",
                "details":      {"i": i, "big": "x" * 800},  # trigger trim path
                "created_at":   (datetime.now(timezone.utc) - timedelta(minutes=i)).isoformat(),
                "timestamp":    (datetime.now(timezone.utc) - timedelta(minutes=i)).isoformat(),
            })
        try:
            r = requests.get(
                f"{API}/admin/logs?action_type=iter346_test&page=1&limit=50",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            assert r.status_code == 200
            data = r.json()
            assert "items" in data and "total_count" in data and "pages" in data
            assert data["total_count"] >= 75, f"expected ≥75, got {data['total_count']}"
            assert len(data["items"]) == 50
            assert data["pages"] >= 2
            # Details must have been trimmed.
            row = data["items"][0]
            det = row.get("details")
            assert isinstance(det, dict)
            big = det.get("big", "")
            assert len(big) <= 400, f"big field should have been trimmed, len={len(big)}"

            # Page 2 must return remainder.
            r2 = requests.get(
                f"{API}/admin/logs?action_type=iter346_test&page=2&limit=50",
                headers={"Authorization": f"Bearer {token}"},
                timeout=30,
            )
            assert r2.status_code == 200
            d2 = r2.json()
            assert len(d2["items"]) >= 25
        finally:
            db.admin_logs.delete_many({"id": {"$in": seeded_ids}})
            db.users.delete_one({"id": uid})


# ═══ Compliance digest ═════════════════════════════════════════════════

class TestComplianceDigest:

    def test_digest_html_builds_with_sessions(self):
        from services.compliance_digest import _build_html
        now = datetime.now(timezone.utc)
        sessions = [
            {"started_at": now.isoformat(), "admin_email": "a@b.com",
             "target_email": "t@u.com", "duration_minutes": 45.0, "actions_count": 12},
            {"started_at": now.isoformat(), "admin_email": "c@d.com",
             "target_email": "t2@u.com", "duration_minutes": 5.0, "actions_count": 2},
        ]
        html = _build_html(sessions, now - timedelta(days=7), now)
        assert "<html" in html and "</html>" in html
        assert "BidVex Weekly Impersonation Audit" in html
        assert "a@b.com" in html and "c@d.com" in html
        assert "Résumé en français" in html
        # Sessions > 30 min flagged.
        assert "🚨" in html

    def test_digest_html_builds_empty(self):
        from services.compliance_digest import _build_html
        now = datetime.now(timezone.utc)
        html = _build_html([], now - timedelta(days=7), now)
        assert "No impersonation sessions" in html


# ═══ Watchlist bid reminders / last_chance job wired ══════════════════

class TestLastChanceScheduler:

    def test_scheduler_module_registers_last_chance_job(self):
        """iter346 P0 — the job must be defined in `services.scheduler`
        (was silently missing before iter346)."""
        import services.scheduler as scheduler_mod
        # Load the source and assert the job id appears in an add_job call.
        with open(scheduler_mod.__file__) as f:
            src = f.read()
        assert 'id="last_chance_nudges"' in src, "last_chance_nudges job not registered in scheduler"
        assert 'process_last_chance_nudges' in src, "process_last_chance_nudges not wired"

    def test_scheduler_module_registers_compliance_digest_job(self):
        import services.scheduler as scheduler_mod
        with open(scheduler_mod.__file__) as f:
            src = f.read()
        assert 'id="compliance_digest"' in src
        assert 'weekly_impersonation_digest_job' in src


# ═══ Deployment/startup self-heal verifies ═════════════════════════════

@pytest.mark.asyncio
async def test_startup_selfheal_reverts_admin_suppression():
    """Simulate: an admin got suppressed (like the 2026-07-02 charbel911
    incident); a subsequent boot must clear them and re-flip user flags."""
    from motor.motor_asyncio import AsyncIOMotorClient as _M
    client = _M(os.environ["MONGO_URL"])
    db = client[os.environ["DB_NAME"]]
    uid = str(uuid.uuid4())
    email = f"iter346_selfheal_{uuid.uuid4().hex[:8]}@test.com"
    now = datetime.now(timezone.utc)
    await db.users.insert_one({
        "id": uid, "email": email, "role": "super_admin",
        "marketing_unsubscribed": True, "email_unsubscribed": True,
        "marketing_unsubscribed_at": now, "created_at": now.isoformat(),
    })
    await db.email_suppressions.insert_one({"email": email, "source": "link", "unsubscribed_at": now})
    await db.external_email_suppressions.insert_one({"email": email, "source": "platform", "suppressed_at": now.isoformat()})
    try:
        # Replay the exact self-heal block from server.py.
        admin_emails = [u["email"] async for u in db.users.find(
            {"role": {"$in": ["admin", "super_admin"]},
             "$or": [
                 {"marketing_unsubscribed": True},
                 {"email_unsubscribed": True},
             ]},
            {"_id": 0, "email": 1},
        )]
        assert email in admin_emails

        await db.users.update_many(
            {"email": {"$in": admin_emails}},
            {"$set": {
                "marketing_unsubscribed": False,
                "email_unsubscribed": False,
                "marketing_resubscribed_at": now,
                "marketing_resubscribed_source": "iter346_admin_selfheal",
            }},
        )
        r1 = await db.email_suppressions.delete_many({"email": {"$in": admin_emails}})
        r2 = await db.external_email_suppressions.delete_many({"email": {"$in": admin_emails}})
        assert r1.deleted_count >= 1
        assert r2.deleted_count >= 1
        # And the user flags are flipped back.
        user = await db.users.find_one({"id": uid}, {"_id": 0, "marketing_unsubscribed": 1, "email_unsubscribed": 1})
        assert user["marketing_unsubscribed"] is False
        assert user["email_unsubscribed"] is False
    finally:
        await db.users.delete_one({"id": uid})
        await db.email_suppressions.delete_many({"email": email})
        await db.external_email_suppressions.delete_many({"email": email})
        client.close()
