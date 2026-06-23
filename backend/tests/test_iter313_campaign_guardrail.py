"""
iter313 P2 — Per-Campaign 5% Auto-Pause Guardrail regression tests.

Validates the full guardrail loop:
  1. Below-threshold ratio → no auto-pause.
  2. Above-threshold ratio → status flips to `auto_paused` with audit row.
  3. /send-now is blocked on auto_paused.
  4. /resume-auto-paused requires {confirm: true} (400 without).
  5. /resume-auto-paused with confirm flips status back to `sent` + audit.
  6. /auto-paused list endpoint surfaces the currently-paused set.
  7. Min-sample guardrail: <20 attempts is never auto-paused (noise).
"""
from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import requests

sys.path.insert(0, "/app/backend")

from dotenv import load_dotenv  # noqa: E402
load_dotenv("/app/backend/.env")

from pymongo import MongoClient  # noqa: E402

with open("/app/frontend/.env") as f:
    BASE_URL = next(
        (line.split("=", 1)[1].strip() for line in f if line.startswith("REACT_APP_BACKEND_URL")),
        None,
    )

ADMIN = (os.environ.get("ADMIN_EMAIL", "charbel911@gmail.com"),
         os.environ.get("ADMIN_PASSWORD", "Anderosli123!@#"))

CAMPAIGNS_BASE = f"{BASE_URL}/api/admin/external-campaigns"


@pytest.fixture(scope="module")
def db():
    cli = MongoClient(os.environ["MONGO_URL"])
    yield cli[os.environ["DB_NAME"]]
    cli.close()


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN[0], "password": ADMIN[1]},
        timeout=15,
    )
    if r.status_code != 200:
        pytest.skip(f"admin login failed ({r.status_code}): {r.text}")
    return r.json()["access_token"]


def _h(tok):
    return {"Authorization": f"Bearer {tok}"}


def _make_campaign(db, status="sent", recipient_count=100, analytics=None):
    """Insert a campaign document directly (bypasses send flow)."""
    cid = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()
    a = {
        "delivered": 95, "opened": 50, "clicked": 10,
        "bounced": 0, "unsubscribed": 0, "spam_reports": 0,
        "registrations": 0, "premium_upgrades": 0,
        "last_updated_at": now,
    }
    if analytics:
        a.update(analytics)
    db.external_email_campaigns.insert_one({
        "id":              cid,
        "name":            f"iter313 Guardrail Test {cid[:8]}",
        "subject_en":      "iter313 guardrail test",
        "body_html_en":    "<p>test</p>",
        "status":          status,
        "recipient_count": recipient_count,
        "analytics":       a,
        "created_at":      now,
        "updated_at":      now,
        "sent_at":         now,
        "_iter313_test":   True,
    })
    return cid


def _cleanup(db, campaign_id):
    db.external_email_campaigns.delete_one({"id": campaign_id})
    db.campaign_guardrail_events.delete_many({"campaign_id": campaign_id})


def _trigger_event(db, campaign_id, event_type, count=1):
    """Simulate an inbound SendGrid webhook event and let the handler
    apply the guardrail. We call the internal handler directly to keep
    the test deterministic (no signature/network)."""
    import asyncio
    from routes.sendgrid_webhook import _handle_external_campaign_event
    db_async = _async_db()
    async def _run():
        for i in range(count):
            await _handle_external_campaign_event(db_async, {
                "event":       event_type,
                "email":       f"bounce-{uuid.uuid4().hex[:6]}@example.com",
                "campaign_id": campaign_id,
                "campaign_type": "external",
            })
    asyncio.run(_run())


def _async_db():
    from motor.motor_asyncio import AsyncIOMotorClient
    cli = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return cli[os.environ["DB_NAME"]]


# ─── Tests ──────────────────────────────────────────────────────────────


def test_below_threshold_does_not_auto_pause(db):
    """4% negative ratio (4 bounces on 100 delivered) → must NOT pause."""
    cid = _make_campaign(db, recipient_count=100, analytics={"delivered": 100})
    try:
        _trigger_event(db, cid, "bounce", count=4)
        doc = db.external_email_campaigns.find_one({"id": cid}, {"_id": 0})
        assert doc["status"] == "sent", f"4% should NOT trigger guardrail, got {doc['status']}"
        assert doc["analytics"]["bounced"] == 4
    finally:
        _cleanup(db, cid)


def test_above_threshold_auto_pauses(db):
    """6% bounce ratio (6 bounces on 100 delivered) → must pause."""
    cid = _make_campaign(db, recipient_count=100, analytics={"delivered": 100})
    try:
        _trigger_event(db, cid, "bounce", count=6)
        doc = db.external_email_campaigns.find_one({"id": cid}, {"_id": 0})
        assert doc["status"] == "auto_paused", f"6% MUST trigger guardrail, got {doc['status']}"
        assert doc["auto_paused_reason"] == "bounce_unsubscribe_ratio_exceeded"
        assert doc["auto_paused_ratio_pct"] > 5.0
        # Audit row written.
        audit = db.campaign_guardrail_events.find_one(
            {"campaign_id": cid, "event": "auto_pause_triggered"},
        )
        assert audit is not None
        assert audit["ratio_pct"] > 5.0
    finally:
        _cleanup(db, cid)


def test_combined_bounce_unsubscribe_pauses(db):
    """3 bounces + 3 unsubs on 100 delivered = 6% → must pause."""
    cid = _make_campaign(db, recipient_count=100, analytics={"delivered": 100})
    try:
        _trigger_event(db, cid, "bounce", count=3)
        _trigger_event(db, cid, "unsubscribe", count=3)
        doc = db.external_email_campaigns.find_one({"id": cid}, {"_id": 0})
        assert doc["status"] == "auto_paused"
        assert doc["auto_paused_negative_count"] == 6
    finally:
        _cleanup(db, cid)


def test_tiny_sample_never_pauses(db):
    """Even 100% bounce on <20 attempts must NOT pause (noise guard).
    Seed delivered=5 + 5 bounces → attempted=10 < 20 → no pause."""
    cid = _make_campaign(db, recipient_count=5, analytics={"delivered": 5})
    try:
        _trigger_event(db, cid, "bounce", count=5)
        doc = db.external_email_campaigns.find_one({"id": cid}, {"_id": 0})
        assert doc["status"] == "sent", (
            f"Tiny sample (<20) must skip guardrail, got {doc['status']}")
    finally:
        _cleanup(db, cid)


def test_send_now_blocked_when_auto_paused(db, admin_token):
    """POST /external-campaigns/{id}/send-now must 400 on auto_paused."""
    cid = _make_campaign(db, status="auto_paused", recipient_count=100,
                          analytics={"delivered": 100, "bounced": 6})
    try:
        r = requests.post(
            f"{CAMPAIGNS_BASE}/{cid}/send-now",
            headers=_h(admin_token), timeout=15,
        )
        assert r.status_code == 400, f"expected 400 got {r.status_code}: {r.text}"
        assert "auto-paused" in r.text.lower() or "auto_paused" in r.text.lower()
    finally:
        _cleanup(db, cid)


def test_resume_requires_confirm_true(db, admin_token):
    """POST /resume-auto-paused without {confirm:true} must 400."""
    cid = _make_campaign(db, status="auto_paused", recipient_count=100,
                          analytics={"delivered": 100, "bounced": 6})
    try:
        # confirm absent
        r1 = requests.post(
            f"{CAMPAIGNS_BASE}/{cid}/resume-auto-paused",
            headers=_h(admin_token), json={}, timeout=15,
        )
        assert r1.status_code == 400
        # confirm=false
        r2 = requests.post(
            f"{CAMPAIGNS_BASE}/{cid}/resume-auto-paused",
            headers=_h(admin_token), json={"confirm": False}, timeout=15,
        )
        assert r2.status_code == 400
        # Status unchanged
        doc = db.external_email_campaigns.find_one({"id": cid}, {"_id": 0})
        assert doc["status"] == "auto_paused"
    finally:
        _cleanup(db, cid)


def test_resume_with_confirm_flips_to_sent(db, admin_token):
    """POST /resume-auto-paused with confirm=true → 200, status=sent, audit row."""
    cid = _make_campaign(db, status="auto_paused", recipient_count=100,
                          analytics={"delivered": 100, "bounced": 6})
    try:
        r = requests.post(
            f"{CAMPAIGNS_BASE}/{cid}/resume-auto-paused",
            headers=_h(admin_token),
            json={"confirm": True, "acknowledge_risk": "Cleaned list"},
            timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["resumed"] is True
        assert body["status"] == "sent"
        doc = db.external_email_campaigns.find_one({"id": cid}, {"_id": 0})
        assert doc["status"] == "sent"
        assert doc.get("auto_paused_resumed_at")
        # Audit row written.
        audit = db.campaign_guardrail_events.find_one(
            {"campaign_id": cid, "event": "auto_pause_resumed"},
        )
        assert audit is not None
        assert audit["reason"] == "Cleaned list"
    finally:
        _cleanup(db, cid)


def test_auto_paused_list_endpoint(db, admin_token):
    """GET /external-campaigns/auto-paused returns paused campaigns."""
    cid = _make_campaign(db, status="auto_paused", recipient_count=100,
                          analytics={"delivered": 100, "bounced": 7})
    # Hydrate the iter313 P2 metadata fields (the webhook writes these).
    db.external_email_campaigns.update_one(
        {"id": cid},
        {"$set": {
            "auto_paused_at":              datetime.now(timezone.utc).isoformat(),
            "auto_paused_reason":          "bounce_unsubscribe_ratio_exceeded",
            "auto_paused_ratio_pct":       7.0,
            "auto_paused_negative_count":  7,
            "auto_paused_attempted_count": 100,
        }},
    )
    try:
        r = requests.get(
            f"{CAMPAIGNS_BASE}/auto-paused",
            headers=_h(admin_token), timeout=15,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        ids = [c["id"] for c in body["items"]]
        assert cid in ids, f"{cid} missing from auto-paused list {ids}"
        match = next(c for c in body["items"] if c["id"] == cid)
        assert match["auto_paused_ratio_pct"] == 7.0
    finally:
        _cleanup(db, cid)


def test_double_pause_is_idempotent(db):
    """A second pass over the guardrail must NOT overwrite the
    auto_paused_at timestamp (CAS guard)."""
    cid = _make_campaign(db, recipient_count=100, analytics={"delivered": 100})
    try:
        _trigger_event(db, cid, "bounce", count=6)
        doc1 = db.external_email_campaigns.find_one({"id": cid}, {"_id": 0})
        assert doc1["status"] == "auto_paused"
        first_ts = doc1["auto_paused_at"]
        # Second hit (additional bounces while already paused).
        _trigger_event(db, cid, "bounce", count=3)
        doc2 = db.external_email_campaigns.find_one({"id": cid}, {"_id": 0})
        assert doc2["status"] == "auto_paused"
        assert doc2["auto_paused_at"] == first_ts, (
            "auto_paused_at must NOT change on re-trigger (CAS-guarded)")
        # Bounce counter still incremented though.
        assert doc2["analytics"]["bounced"] >= doc1["analytics"]["bounced"]
    finally:
        _cleanup(db, cid)
