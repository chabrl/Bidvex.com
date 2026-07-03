"""
iter337 — Regression suite for AI Follow-Up Open Tracking + Nudges + Ad Campaigns.

Covers the 6 mandatory checkpoints from Directives 1–3:
  1. SendGrid open event: matched to correct call session, opened_at set.
  2. SendGrid open event: second open does not re-trigger the first-open notification.
  3. Post-call nudge fires for a declining-sentiment session.
  4. Follow-Up Target scheduler: demo-expiring account surfaced correctly.
  5. Dismissed target item is not re-shown to the same contractor after next daily refresh.
  6. Ad copy generation returns valid EN + FR headline + description within character limits.

Zero-network unit style — everything runs against the local MongoDB via
motor. No real SendGrid, no real Gemini (except test 6 which uses the
fallback path when GEMINI_API_KEY missing, so still deterministic).
"""
from __future__ import annotations

import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest

try:
    from dotenv import load_dotenv  # type: ignore[import-not-found]
    load_dotenv("/app/backend/.env")
except Exception:  # pragma: no cover
    pass

sys.path.insert(0, "/app/backend")


# ─── Test fixtures ─────────────────────────────────────────────────────

@pytest.fixture
def event_loop():
    """Provide a dedicated event loop for each test — motor async ops."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)  # motor binds to the current thread loop
    yield loop
    loop.close()
    asyncio.set_event_loop(None)


def _db():
    from motor.motor_asyncio import AsyncIOMotorClient  # type: ignore
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]], client


def _now():
    return datetime.now(timezone.utc)


def _iso(dt):
    return dt.isoformat()


def _seed_session(loop, contractor_id, **overrides):
    """Insert a completed outbound_coach ai_voice_calls row and return its call_log_id."""
    db, client = _db()
    call_log_id = f"iter337-{uuid.uuid4().hex[:12]}"
    doc = {
        "_id":               str(uuid.uuid4()),
        "call_type":         "outbound_coach",
        "call_log_id":       call_log_id,
        "contractor_id":     contractor_id,
        "client_phone":      "+15145551234",
        "call_started_at":   _iso(_now() - timedelta(minutes=15)),
        "call_ended_at":     _iso(_now() - timedelta(minutes=5)),
        "duration_seconds":  600,
        "language_detected": "en",
        "ai_session_status": "completed",
        "sentiment_trend":   "improving",
        "avg_client_sentiment": 0.3,
        "compliance_flags_triggered": [],
        "action_items":      [],
        "ai_summary":        "Client interested in vehicle auctions.",
        "followup_email_generated_count": 1,
        "followup_emails_generated": [{
            "generated_at": _iso(_now() - timedelta(minutes=3)),
            "language":     "en",
            "sent":         True,
            "sent_at":      _iso(_now() - timedelta(minutes=2)),
            "email_row_id": f"row-{uuid.uuid4().hex[:8]}",
            "used_fallback": False,
        }],
        "transcript":         [],
        "coaching_hints_log": [],
        "created_at":         _iso(_now()),
    }
    doc.update(overrides)
    loop.run_until_complete(db.ai_voice_calls.insert_one(doc))
    client.close()
    return call_log_id


def _cleanup(loop, call_log_ids, contractor_ids=None):
    if not call_log_ids and not contractor_ids:
        return
    db, client = _db()
    if call_log_ids:
        loop.run_until_complete(db.ai_voice_calls.delete_many({"call_log_id": {"$in": call_log_ids}}))
    # Wipe any notifications whose id references our test call_log_ids OR
    # whose user_id is one of our synthetic contractor ids.
    q = {"$or": []}
    if call_log_ids:
        q["$or"].append({"id": {"$regex": "|".join(call_log_ids)}})
    if contractor_ids:
        q["$or"].append({"user_id": {"$in": list(contractor_ids)}})
    if q["$or"]:
        loop.run_until_complete(db.notifications.delete_many(q))
    client.close()


# ─── Checkpoint 1: open event → opened_at set ──────────────────────────

def test_ai_followup_open_event_sets_opened_at(event_loop):
    from routes.sendgrid_webhook import _handle_ai_followup_engagement

    contractor_id = "c1-iter337"
    _cleanup(event_loop, [], [contractor_id])  # scrub prior runs
    call_log_id = _seed_session(event_loop, contractor_id=contractor_id)
    ts = int(_now().timestamp())
    event = {
        "event":       "open",
        "email":       "client@example.com",
        "timestamp":   ts,
        "custom_args": {"call_log_id": call_log_id, "email_type": "ai_followup"},
    }
    db, client = _db()
    try:
        event_loop.run_until_complete(_handle_ai_followup_engagement(db, event))
        doc = event_loop.run_until_complete(
            db.ai_voice_calls.find_one({"call_log_id": call_log_id}, {"_id": 0}),
        )
        drafts = doc.get("followup_emails_generated") or []
        assert drafts, "no drafts persisted"
        assert drafts[0].get("opened_at"), "opened_at was not set after open event"
        # Notification created for the contractor.
        notif = event_loop.run_until_complete(
            db.notifications.find_one({"user_id": "c1-iter337", "type": "ai_followup_opened"}),
        )
        assert notif is not None, "first-open notification not created"
    finally:
        client.close()
        _cleanup(event_loop, [call_log_id])


# ─── Checkpoint 2: second open → no duplicate notification ──────────────

def test_ai_followup_second_open_no_duplicate_notification(event_loop):
    from routes.sendgrid_webhook import _handle_ai_followup_engagement

    contractor_id = "c2-iter337"
    _cleanup(event_loop, [], [contractor_id])
    call_log_id = _seed_session(event_loop, contractor_id=contractor_id)
    ts = int(_now().timestamp())
    event = {
        "event":       "open",
        "email":       "client@example.com",
        "timestamp":   ts,
        "sg_event_id": f"sg-{uuid.uuid4().hex[:8]}",  # unique first open
        "custom_args": {"call_log_id": call_log_id, "email_type": "ai_followup"},
    }
    db, client = _db()
    try:
        # First open — creates the notification + sets opened_at.
        event_loop.run_until_complete(_handle_ai_followup_engagement(db, event))
        first_count = event_loop.run_until_complete(
            db.notifications.count_documents({"user_id": "c2-iter337", "type": "ai_followup_opened"}),
        )
        assert first_count == 1, f"expected 1 notification after first open, got {first_count}"

        # Second open with a DIFFERENT sg_event_id — the notification's
        # idempotency key derives from (call_log_id, target_idx) so a
        # second physical open must not create a second notification.
        event2 = {**event, "sg_event_id": f"sg-{uuid.uuid4().hex[:8]}", "timestamp": ts + 10}
        event_loop.run_until_complete(_handle_ai_followup_engagement(db, event2))
        second_count = event_loop.run_until_complete(
            db.notifications.count_documents({"user_id": "c2-iter337", "type": "ai_followup_opened"}),
        )
        assert second_count == 1, (
            f"second open should NOT create a duplicate notification "
            f"(count went {first_count} -> {second_count})"
        )
    finally:
        client.close()
        _cleanup(event_loop, [call_log_id])


# ─── Checkpoint 3: declining-sentiment post-call nudge ─────────────────

def test_post_call_nudge_fires_for_declining_sentiment(event_loop):
    from services.nudge_engine import run_post_call_nudge_sweep

    contractor_id = "c3-iter337"
    _cleanup(event_loop, [], [contractor_id])
    call_log_id = _seed_session(
        event_loop,
        contractor_id=contractor_id,
        sentiment_trend="declining",
        avg_client_sentiment=-0.4,
        followup_email_generated_count=0,
        followup_emails_generated=[],
    )
    db, client = _db()
    try:
        stats = event_loop.run_until_complete(run_post_call_nudge_sweep(db))
        assert stats["scanned"] >= 1
        assert stats["declining"] >= 1, f"expected declining nudge to fire, got stats={stats}"
        n = event_loop.run_until_complete(
            db.notifications.find_one({
                "user_id": contractor_id,
                "type":    "contractor_post_call_nudge",
                "data.reason": "declining_sentiment",
            }),
        )
        assert n is not None, "declining_sentiment nudge document not found"
        assert n.get("message_en") and n.get("message_fr"), "nudge must be bilingual"

        # Idempotent — running the sweep twice does NOT create duplicates.
        stats2 = event_loop.run_until_complete(run_post_call_nudge_sweep(db))
        assert stats2["declining"] == 0, "second sweep produced a duplicate nudge"
    finally:
        client.close()
        _cleanup(event_loop, [call_log_id])


# ─── Checkpoint 4: demo-expiring surfaced by follow-up target scheduler ─

def test_followup_target_scheduler_surfaces_demo_expiring(event_loop):
    from services.nudge_engine import _build_followup_targets_for_contractor

    contractor_id = f"c4-{uuid.uuid4().hex[:6]}"
    demo_account_id = f"demo-{uuid.uuid4().hex[:8]}"
    now = _now()

    db, client = _db()
    try:
        # Seed a demo account expiring in 3 days.
        event_loop.run_until_complete(db.users.insert_one({
            "id":                demo_account_id,
            "email":             f"{demo_account_id}@example.com",
            "name":              "Demo Business",
            "business_name":     "Iter337 Demo Co.",
            "demo_expiry_date":  _iso(now + timedelta(days=3)),
            "created_at":        _iso(now),
        }))
        event_loop.run_until_complete(db.contractor_account_creations.insert_one({
            "id":            str(uuid.uuid4()),
            "contractor_id": contractor_id,
            "account_id":    demo_account_id,
            "account_type":  "vehicle_dealer",
            "demo":          True,
            "created_at":    _iso(now),
        }))

        items = event_loop.run_until_complete(
            _build_followup_targets_for_contractor(db, contractor_id),
        )
        assert items, "expected at least 1 follow-up target"
        demo_item = next((i for i in items if i["reason"] == "demo_expiring" and i["account_id"] == demo_account_id), None)
        assert demo_item is not None, f"demo-expiring account not surfaced. items={items}"
        assert demo_item["days_left"] <= 3
        assert demo_item["text_en"] and demo_item["text_fr"]
    finally:
        # Cleanup
        event_loop.run_until_complete(db.users.delete_one({"id": demo_account_id}))
        event_loop.run_until_complete(db.contractor_account_creations.delete_many({"contractor_id": contractor_id}))
        client.close()


# ─── Checkpoint 5: dismissed target stays dismissed after refresh ──────

def test_dismissed_followup_target_stays_hidden_after_refresh(event_loop):
    from services.nudge_engine import (
        run_daily_followup_targets, FOLLOWUP_TARGET_COLLECTION,
    )

    contractor_id = f"c5-{uuid.uuid4().hex[:6]}"
    demo_account_id = f"demo-{uuid.uuid4().hex[:8]}"
    now = _now()

    db, client = _db()
    try:
        # Seed users row for the contractor so the scheduler picks him up.
        event_loop.run_until_complete(db.users.insert_one({
            "id":    contractor_id,
            "email": f"{contractor_id}@example.com",
            "role":  "dialer_contractor",
        }))
        event_loop.run_until_complete(db.users.insert_one({
            "id":                demo_account_id,
            "email":             f"{demo_account_id}@example.com",
            "business_name":     "Iter337 Dismiss Co.",
            "demo_expiry_date":  _iso(now + timedelta(days=2)),
            "created_at":        _iso(now),
        }))
        event_loop.run_until_complete(db.contractor_account_creations.insert_one({
            "id":            str(uuid.uuid4()),
            "contractor_id": contractor_id,
            "account_id":    demo_account_id,
            "account_type":  "vehicle_dealer",
            "demo":          True,
            "created_at":    _iso(now),
        }))

        # Run 1 → item present + not dismissed.
        event_loop.run_until_complete(run_daily_followup_targets(db))
        doc1 = event_loop.run_until_complete(
            db[FOLLOWUP_TARGET_COLLECTION].find_one({"contractor_id": contractor_id}),
        )
        assert doc1 is not None
        item = next((i for i in doc1["items"] if i["account_id"] == demo_account_id), None)
        assert item and not item.get("dismissed")

        # Mark it dismissed manually (mimic UI action).
        event_loop.run_until_complete(db[FOLLOWUP_TARGET_COLLECTION].update_one(
            {"contractor_id": contractor_id, "items.id": item["id"]},
            {"$set": {"items.$.dismissed": True, "items.$.dismissed_at": _iso(now)}},
        ))

        # Run 2 → dismissed=True must be preserved.
        event_loop.run_until_complete(run_daily_followup_targets(db))
        doc2 = event_loop.run_until_complete(
            db[FOLLOWUP_TARGET_COLLECTION].find_one({"contractor_id": contractor_id}),
        )
        item2 = next((i for i in doc2["items"] if i["account_id"] == demo_account_id), None)
        assert item2 and item2.get("dismissed") is True, (
            "dismissed item was reset on next daily refresh"
        )
    finally:
        event_loop.run_until_complete(db.users.delete_one({"id": demo_account_id}))
        event_loop.run_until_complete(db.users.delete_one({"id": contractor_id}))
        event_loop.run_until_complete(db.contractor_account_creations.delete_many({"contractor_id": contractor_id}))
        event_loop.run_until_complete(db[FOLLOWUP_TARGET_COLLECTION].delete_one({"contractor_id": contractor_id}))
        client.close()


# ─── Checkpoint 6: ad copy generation — char limits + fallback ─────────

def test_ad_copy_generation_returns_valid_bilingual_within_char_limits(event_loop):
    from routes.ad_campaigns import (
        _generate_ad_copy, _extract_ad_json, _fallback_ad_copy,
        MAX_HEADLINE_CHARS, MAX_DESCRIPTION_CHARS,
    )

    # Fallback path always produces a valid dict (no Gemini call needed).
    fb = _fallback_ad_copy({"title": "2019 Ford F-150 SuperCrew XLT"})
    for k in ("headline_en", "headline_fr", "description_en", "description_fr"):
        assert fb[k], f"fallback field {k} is empty"
    assert len(fb["headline_en"]) <= MAX_HEADLINE_CHARS
    assert len(fb["headline_fr"]) <= MAX_HEADLINE_CHARS
    assert len(fb["description_en"]) <= MAX_DESCRIPTION_CHARS
    assert len(fb["description_fr"]) <= MAX_DESCRIPTION_CHARS

    # JSON extractor rejects malformed payloads.
    for garbage in [
        "",
        "not-json",
        '{"headline_en":"only en"}',                          # missing keys
        '{"headline_en":"","headline_fr":"","description_en":"","description_fr":""}',  # empty
    ]:
        assert _extract_ad_json(garbage) is None, f"extractor accepted garbage: {garbage!r}"

    # JSON extractor accepts valid payloads and clips to limits.
    valid = (
        '{"headline_en":"Bid now on this 2019 F-150 pickup with clean title",'
        '"headline_fr":"Enchérissez sur ce F-150 2019 en excellent état à vendre",'
        '"description_en":"Live auction ending Sunday. Register free and place your bid on BidVex today. Save on trusted Canadian dealer inventory.",'
        '"description_fr":"Enchère en direct dimanche. Inscrivez-vous gratuitement et enchérissez sur BidVex. Économies sur inventaire de concessionnaires canadiens."}'
    )
    parsed = _extract_ad_json(valid)
    assert parsed is not None
    for k in ("headline_en", "headline_fr", "description_en", "description_fr"):
        max_len = MAX_HEADLINE_CHARS if k.startswith("headline") else MAX_DESCRIPTION_CHARS
        assert len(parsed[k]) <= max_len, f"{k}={parsed[k]!r} exceeds cap {max_len}"

    # End-to-end generator returns (copy, used_fallback). Whichever path
    # runs, all char-length guarantees hold.
    copy, used_fallback = event_loop.run_until_complete(_generate_ad_copy({
        "title": "Test Auction Item",
        "description": "Sample description for iter337 unit test.",
        "listing_type": "marketplace",
    }))
    assert isinstance(copy, dict)
    for k in ("headline_en", "headline_fr", "description_en", "description_fr"):
        max_len = MAX_HEADLINE_CHARS if k.startswith("headline") else MAX_DESCRIPTION_CHARS
        assert copy[k], f"{k} is empty"
        assert len(copy[k]) <= max_len, f"{k} exceeds cap"
    assert isinstance(used_fallback, bool)


# ─── Bonus: sendgrid_webhook re-hydrates custom_args via sg_message_id ─

def test_ai_followup_open_falls_back_to_contractor_emails_lookup(event_loop):
    """When SendGrid strips custom_args, the handler must recover them
    from the contractor_emails row we stored at send time."""
    from routes.sendgrid_webhook import _handle_ai_followup_engagement

    contractor_id = "c7-iter337"
    _cleanup(event_loop, [], [contractor_id])
    sg_msg_id = f"sg-msg-{uuid.uuid4().hex[:8]}"
    call_log_id = _seed_session(event_loop, contractor_id=contractor_id)

    db, client = _db()
    email_row_id = str(uuid.uuid4())
    try:
        # Seed a contractor_emails row whose custom_args carry the linkage.
        event_loop.run_until_complete(db.contractor_emails.insert_one({
            "id":                  email_row_id,
            "contractor_id":       contractor_id,
            "sendgrid_message_id": sg_msg_id,
            "to_email":            "client@example.com",
            "subject":             "Follow up",
            "custom_args":         {"call_log_id": call_log_id, "email_type": "ai_followup"},
            "sent_at":             _iso(_now()),
        }))

        event = {
            "event":         "open",
            "email":         "client@example.com",
            "timestamp":     int(_now().timestamp()),
            "sg_message_id": sg_msg_id,
            # NO custom_args — SendGrid stripped them.
        }
        event_loop.run_until_complete(_handle_ai_followup_engagement(db, event))
        doc = event_loop.run_until_complete(
            db.ai_voice_calls.find_one({"call_log_id": call_log_id}, {"_id": 0}),
        )
        drafts = doc.get("followup_emails_generated") or []
        assert drafts and drafts[0].get("opened_at"), (
            "opened_at should be set even when SendGrid strips custom_args"
        )
    finally:
        event_loop.run_until_complete(db.contractor_emails.delete_one({"id": email_row_id}))
        client.close()
        _cleanup(event_loop, [call_log_id])
