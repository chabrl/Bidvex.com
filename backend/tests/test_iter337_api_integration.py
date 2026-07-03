"""iter337 — HTTP-level API integration tests against the live preview URL.

Covers, end-to-end via the public /api gateway:
  • Login as admin
  • Follow-up status polling endpoint + open-rate aggregate
  • Nudges list + dismiss
  • Follow-up targets list + dismiss (persistence across GETs)
  • Ad Campaigns CRUD + Gemini copy + CSV export
  • SendGrid webhook 403 on missing signature
"""
from __future__ import annotations

import csv
import io
import os
import uuid
from datetime import datetime, timezone, timedelta

import pytest
import requests
from pymongo import MongoClient
from dotenv import dotenv_values

# Read backend/.env robustly (has spaces, commas, PEMs)
_env = dotenv_values(os.path.join(os.path.dirname(__file__), "..", ".env"))

BASE_URL = (
    os.environ.get("REACT_APP_BACKEND_URL")
    or "https://prod-verify-2.preview.emergentagent.com"
).rstrip("/")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"

MONGO_URL = _env.get("MONGO_URL") or os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
DB_NAME   = _env.get("DB_NAME")   or os.environ.get("DB_NAME")   or "bazario_db"


@pytest.fixture(scope="module")
def mongo_db():
    client = MongoClient(MONGO_URL)
    yield client[DB_NAME]
    client.close()


@pytest.fixture(scope="module")
def admin_session():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}, timeout=20)
    assert r.status_code == 200, f"Admin login failed: {r.status_code} {r.text}"
    data = r.json()
    token = data.get("token") or data.get("access_token")
    assert token, f"No token in login response: {data}"
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    # attach user_id for downstream tests
    s.user_id = (data.get("user") or {}).get("id") or (data.get("user") or {}).get("user_id")
    assert s.user_id, f"No user id in login response: {data}"
    return s


# ─── D1: Follow-up status polling + open-rate ──────────────────────────

def test_followup_status_sent_not_opened_then_opened(admin_session, mongo_db):
    """Seed an outbound_coach ai_voice_calls row with a sent-but-not-opened
    followup_emails_generated entry. Verify the polling endpoint reflects
    the state, then flip opened_at and verify the change."""
    call_log_id = f"TEST_iter337_{uuid.uuid4().hex[:8]}"
    sent_at = datetime.now(timezone.utc).isoformat()
    doc = {
        "call_log_id": call_log_id,
        "call_type": "outbound_coach",
        "contractor_id": admin_session.user_id,
        "followup_email_generated_count": 1,
        "followup_emails_generated": [
            {
                "generated_at": sent_at,
                "language": "en",
                "sent": True,
                "sent_at": sent_at,
                "sendgrid_message_id": "sg-test-" + uuid.uuid4().hex[:8],
            }
        ],
        "created_at": sent_at,
    }
    mongo_db.ai_voice_calls.insert_one(doc)
    try:
        r = admin_session.get(f"{BASE_URL}/api/ai-coach/sessions/{call_log_id}/followup-status", timeout=15)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["sent"] is True
        assert body["sent_at"] == sent_at
        assert body["opened"] is False
        assert body["opened_at"] is None

        # Flip to opened
        opened_at = datetime.now(timezone.utc).isoformat()
        mongo_db.ai_voice_calls.update_one(
            {"call_log_id": call_log_id, "call_type": "outbound_coach"},
            {"$set": {"followup_emails_generated.0.opened_at": opened_at}},
        )
        r2 = admin_session.get(f"{BASE_URL}/api/ai-coach/sessions/{call_log_id}/followup-status", timeout=15)
        assert r2.status_code == 200
        b2 = r2.json()
        assert b2["opened"] is True
        assert b2["opened_at"] == opened_at
    finally:
        mongo_db.ai_voice_calls.delete_one({"call_log_id": call_log_id})


def test_admin_followup_open_rate_math(admin_session, mongo_db):
    """Seed 3 sent + 2 opened rows within the window; expect open_rate_pct
    to reflect that. Uses ISO cutoff so we set sent_at to now."""
    now = datetime.now(timezone.utc)
    marker = f"TEST_iter337_openrate_{uuid.uuid4().hex[:6]}"
    seeded_ids = []
    try:
        for i in range(3):
            entry = {
                "generated_at": now.isoformat(),
                "language": "en",
                "sent": True,
                "sent_at": now.isoformat(),
            }
            if i < 2:
                entry["opened_at"] = now.isoformat()
            _id = mongo_db.ai_voice_calls.insert_one({
                "call_log_id": f"{marker}_{i}",
                "call_type": "outbound_coach",
                "contractor_id": admin_session.user_id,
                "followup_emails_generated": [entry],
                "followup_email_generated_count": 1,
                "created_at": now.isoformat(),
            }).inserted_id
            seeded_ids.append(_id)

        r = admin_session.get(f"{BASE_URL}/api/admin/ai-coach/followup-open-rate?days=30", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        # Might have other data in DB. We only sanity check the shape + math consistency.
        assert data["sent_count"] >= 3
        assert data["opened_count"] >= 2
        # Rate math: rate == round(opened/sent*100, 1)
        expected = round((data["opened_count"] / data["sent_count"]) * 100.0, 1)
        assert abs(data["open_rate_pct"] - expected) < 0.05
        assert data["window_days"] == 30
    finally:
        mongo_db.ai_voice_calls.delete_many({"call_log_id": {"$regex": f"^{marker}"}})


# ─── D2: Nudges list + dismiss ─────────────────────────────────────────

def test_nudges_list_and_dismiss(admin_session, mongo_db):
    nudge_id = f"TEST_nudge_{uuid.uuid4().hex[:8]}"
    mongo_db.notifications.insert_one({
        "id": nudge_id,
        "user_id": admin_session.user_id,
        "type": "contractor_post_call_nudge",
        "title": "TEST — call sentiment declining",
        "body": "Test nudge body",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dismissed": False,
    })
    try:
        r = admin_session.get(f"{BASE_URL}/api/ai-coach/nudges", timeout=15)
        assert r.status_code == 200, r.text
        ids = [n.get("id") for n in r.json().get("nudges", [])]
        assert nudge_id in ids, f"Seeded nudge not returned. ids={ids}"

        dr = admin_session.post(f"{BASE_URL}/api/ai-coach/nudges/dismiss", json={"id": nudge_id}, timeout=15)
        assert dr.status_code == 200, dr.text
        assert dr.json().get("dismissed") is True

        r2 = admin_session.get(f"{BASE_URL}/api/ai-coach/nudges", timeout=15)
        ids2 = [n.get("id") for n in r2.json().get("nudges", [])]
        assert nudge_id not in ids2, "Dismissed nudge still returned"
    finally:
        mongo_db.notifications.delete_one({"id": nudge_id})


# ─── D2: Follow-Up Targets list + dismiss (with persistence) ───────────

def test_followup_targets_dismiss_persistence(admin_session, mongo_db):
    tid = f"test-target-{uuid.uuid4().hex[:6]}"
    doc = {
        "contractor_id": admin_session.user_id,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generated_date": datetime.now(timezone.utc).date().isoformat(),
        "items": [
            {
                "id": tid,
                "reason": "demo_expiring",
                "text_en": "Demo expiring soon — take action",
                "text_fr": "Démo expire bientôt",
                "dismissed": False,
            }
        ],
    }
    # Upsert-like — delete first to avoid conflict
    mongo_db.followup_targets.delete_many({"contractor_id": admin_session.user_id})
    mongo_db.followup_targets.insert_one(doc)
    try:
        r = admin_session.get(f"{BASE_URL}/api/ai-coach/followup-targets", timeout=15)
        assert r.status_code == 200, r.text
        ids = [i.get("id") for i in r.json().get("items", [])]
        assert tid in ids, f"Seeded target not returned. ids={ids}"

        dr = admin_session.post(f"{BASE_URL}/api/ai-coach/followup-targets/dismiss", json={"id": tid}, timeout=15)
        assert dr.status_code == 200, dr.text
        assert dr.json().get("dismissed") is True

        r2 = admin_session.get(f"{BASE_URL}/api/ai-coach/followup-targets", timeout=15)
        ids2 = [i.get("id") for i in r2.json().get("items", [])]
        assert tid not in ids2, "Dismissed target still returned"

        # Verify persistence — the underlying items array should still contain
        # the entry but with dismissed=True
        stored = mongo_db.followup_targets.find_one({"contractor_id": admin_session.user_id})
        matched = [i for i in (stored.get("items") or []) if i.get("id") == tid]
        assert matched and matched[0].get("dismissed") is True
    finally:
        mongo_db.followup_targets.delete_many({"contractor_id": admin_session.user_id})


# ─── D3: Ad Campaigns CRUD ─────────────────────────────────────────────

def test_ad_campaigns_bogus_listing_ids_skipped(admin_session):
    r = admin_session.post(
        f"{BASE_URL}/api/admin/ad-campaigns",
        json={"listing_ids": [f"nonexistent-{uuid.uuid4().hex[:6]}"], "platform": "both"},
        timeout=30,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total_created"] == 0
    assert data["skipped"], "expected at least one skipped entry"
    reasons = [s.get("reason") for s in data["skipped"]]
    assert "listing_not_found" in reasons


def test_ad_campaigns_full_crud_with_real_listing(admin_session, mongo_db):
    """Seed a real listing → POST create → assert copy within char limits →
    GET list contains it → PATCH ready → GET CSV export → DELETE."""
    listing_id = f"TEST_listing_{uuid.uuid4().hex[:8]}"
    mongo_db.listings.delete_many({"id": listing_id})
    mongo_db.listings.insert_one({
        "id": listing_id,
        "title": "TEST Vintage Toolbox",
        "description": "A well-maintained vintage steel toolbox, ready for its next workshop.",
        "starting_price": 42.5,
        "category": "tools",
        "status": "active",
        "images": ["https://example.com/tool.jpg"],
    })
    campaign_id = None
    try:
        # CREATE
        r = admin_session.post(
            f"{BASE_URL}/api/admin/ad-campaigns",
            json={"listing_ids": [listing_id], "platform": "both"},
            timeout=45,  # Gemini may take ~10s
        )
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["total_created"] == 1, f"expected 1 created, got {data}"
        camp = data["created"][0]
        campaign_id = camp["id"]
        # Char limits
        assert len(camp["headline_en"]) <= 40
        assert len(camp["headline_fr"]) <= 40
        assert len(camp["description_en"]) <= 90
        assert len(camp["description_fr"]) <= 90
        assert camp["status"] == "draft"
        assert camp["platform"] == "both"
        assert camp["listing_id"] == listing_id

        # LIST
        r2 = admin_session.get(f"{BASE_URL}/api/admin/ad-campaigns?limit=200", timeout=15)
        assert r2.status_code == 200
        ids = [c["id"] for c in r2.json().get("items", [])]
        assert campaign_id in ids

        # PATCH → ready
        r3 = admin_session.patch(
            f"{BASE_URL}/api/admin/ad-campaigns/{campaign_id}",
            json={"status": "ready"},
            timeout=15,
        )
        assert r3.status_code == 200, r3.text
        assert r3.json()["status"] == "ready"

        # CSV export — Google + status=ready
        r4 = admin_session.get(
            f"{BASE_URL}/api/admin/ad-campaigns/export.csv?platform=google&status=ready",
            timeout=30,
        )
        assert r4.status_code == 200
        ct = r4.headers.get("content-type", "")
        assert "text/csv" in ct.lower(), f"bad content-type: {ct}"
        text = r4.text
        # Parse CSV and assert the canonical Google Merchant Center columns are present
        reader = csv.reader(io.StringIO(text))
        header = next(reader)
        needed = {"id", "title", "description", "link", "image_link", "availability", "condition", "price", "brand"}
        assert needed.issubset(set(header)), f"missing columns; got {header}"
        # The seeded campaign should be in the CSV
        rows = list(reader)
        row_ids = [row[header.index("id")] for row in rows]
        assert campaign_id in row_ids, "campaign not in CSV"
    finally:
        if campaign_id:
            try:
                admin_session.delete(f"{BASE_URL}/api/admin/ad-campaigns/{campaign_id}", timeout=15)
            except Exception:
                pass
        mongo_db.listings.delete_many({"id": listing_id})
        mongo_db.ad_campaigns.delete_many({"listing_id": listing_id})


# ─── D1: SendGrid webhook signature enforcement ────────────────────────

def test_sendgrid_webhook_rejects_missing_signature():
    r = requests.post(
        f"{BASE_URL}/api/webhooks/sendgrid",
        json=[{"event": "open", "email": "test@example.com"}],
        timeout=15,
    )
    # If SENDGRID_WEBHOOK_PUBLIC_KEY is set (it is per .env), must be 403.
    assert r.status_code == 403, f"Expected 403 with no signature, got {r.status_code}: {r.text[:200]}"
