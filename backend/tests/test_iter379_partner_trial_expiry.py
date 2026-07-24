"""
iter379 — Partner-trial expiry regression test.

The audit surfaced that admin-granted partner trials (broker/dealer/
storage) never expire because the pre-existing scheduler
`expire_partner_pro_trials` only touches subscription-trial fields.

This test:

  1. Seeds a user + partner_trials row whose `trial_expires_at` is in
     the past.
  2. Runs the new expiry sweep.
  3. Asserts the trial row flipped to `status='expired'`.
  4. Asserts all four user flags cleared:
       partner_trial_active, is_broker_partner, partner_type,
       partner_trial_expires_at.
  5. Asserts exactly one audit row landed in
     `partner_trial_expiry_log`.
  6. Runs the sweep a second time and asserts nothing else changes
     (idempotency guard).
"""

from __future__ import annotations

import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, "/app/backend")


def _load_env():
    p = Path("/app/backend/.env")
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            os.environ.setdefault(k.strip(), v.strip())


async def _mongo():
    _load_env()
    from motor.motor_asyncio import AsyncIOMotorClient
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]], client


@pytest.mark.asyncio
async def test_expired_broker_trial_is_flipped_and_flags_cleared(monkeypatch):
    """Full happy-path — user's trial expired yesterday → sweep flips
    row + clears flags + drops audit row."""
    db, client = await _mongo()

    uid = f"iter379u-{uuid.uuid4().hex[:10]}"
    tid = f"iter379t-{uuid.uuid4().hex[:10]}"
    email = f"iter379-{uuid.uuid4().hex[:6]}@bidvex-qa.com"
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    try:
        await db.users.insert_one({
            "id": uid, "email": email, "name": "Iter379 Broker",
            "role": "buyer", "is_active": True,
            "preferred_language": "en",
            # The four flags the trial writer had stamped:
            "partner_trial_active": True,
            "partner_trial_expires_at": yesterday,
            "is_broker_partner": True,
            "partner_type": "broker",
            "created_at": yesterday,
        })
        await db.partner_trials.insert_one({
            "id": tid, "user_id": uid,
            "partner_type": "broker",
            "company_name": "Iter379 Realty",
            "licence_number": "L-379",
            "province": "QC",
            "phone": "5145550000",
            "status": "active",
            "trial_expires_at": yesterday,
            "featured_listings_remaining": 20,
            "created_at": yesterday,
        })

        # Stub the email send so the test doesn't hit SendGrid.
        from services import partner_trial_expiry as pte
        async def _fake_send(_db, _uid, _pt):
            return True
        monkeypatch.setattr(pte, "_send_trial_ended_email", _fake_send)

        stats = await pte.run_partner_trial_expiry(db)

        # (a) Sweep saw + expired exactly this row
        assert stats["scanned"] == 1, stats
        assert stats["expired"] == 1, stats
        assert stats["user_flags_cleared"] == 1, stats
        assert stats["emails_sent"] == 1, stats
        assert stats["errors"] == 0, stats

        # (b) partner_trials row flipped to expired
        after_row = await db.partner_trials.find_one({"id": tid}, {"_id": 0})
        assert after_row["status"] == "expired", after_row
        assert after_row.get("expired_at"), "expired_at must be stamped"

        # (c) User flags cleared
        after_user = await db.users.find_one({"id": uid}, {"_id": 0})
        assert after_user["partner_trial_active"] is False, after_user
        assert after_user["partner_trial_expires_at"] is None, after_user
        assert after_user["is_broker_partner"] is False, after_user
        assert after_user["partner_type"] is None, after_user

        # (d) Audit row present exactly once
        audit_rows = await db.partner_trial_expiry_log.find(
            {"trial_id": tid}, {"_id": 0},
        ).to_list(10)
        assert len(audit_rows) == 1
        assert audit_rows[0]["sent_email"] is True

        # (e) IDEMPOTENCY — second run is a no-op
        stats2 = await pte.run_partner_trial_expiry(db)
        assert stats2["scanned"] == 0, stats2  # no active-expired rows left
        assert stats2["expired"] == 0
        assert stats2["emails_sent"] == 0

        # Audit log stays at exactly 1 row
        audit_after = await db.partner_trial_expiry_log.count_documents({"trial_id": tid})
        assert audit_after == 1

    finally:
        await db.users.delete_one({"id": uid})
        await db.partner_trials.delete_one({"id": tid})
        await db.partner_trial_expiry_log.delete_many({"trial_id": tid})
        client.close()


@pytest.mark.asyncio
async def test_active_trial_that_has_not_expired_is_untouched(monkeypatch):
    """A partner trial with `trial_expires_at` still in the future must
    NOT be flipped or have its flags cleared."""
    db, client = await _mongo()

    uid = f"iter379u-safe-{uuid.uuid4().hex[:10]}"
    tid = f"iter379t-safe-{uuid.uuid4().hex[:10]}"
    email = f"iter379-safe-{uuid.uuid4().hex[:6]}@bidvex-qa.com"
    future = (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()

    try:
        await db.users.insert_one({
            "id": uid, "email": email, "name": "Iter379 Live",
            "role": "buyer", "is_active": True,
            "partner_trial_active": True,
            "partner_trial_expires_at": future,
            "is_broker_partner": True,
            "partner_type": "broker",
            "created_at": future,
        })
        await db.partner_trials.insert_one({
            "id": tid, "user_id": uid,
            "partner_type": "broker",
            "status": "active",
            "trial_expires_at": future,
            "created_at": future,
        })

        from services import partner_trial_expiry as pte
        async def _fake_send(_db, _uid, _pt): return True
        monkeypatch.setattr(pte, "_send_trial_ended_email", _fake_send)

        stats = await pte.run_partner_trial_expiry(db)
        assert stats["scanned"] == 0, "future-dated trial must not be scanned"
        assert stats["expired"] == 0

        after_user = await db.users.find_one({"id": uid}, {"_id": 0})
        assert after_user["partner_trial_active"] is True
        assert after_user["is_broker_partner"] is True
        assert after_user["partner_type"] == "broker"

        after_row = await db.partner_trials.find_one({"id": tid}, {"_id": 0})
        assert after_row["status"] == "active"
        assert "expired_at" not in after_row

    finally:
        await db.users.delete_one({"id": uid})
        await db.partner_trials.delete_one({"id": tid})
        client.close()


# ─── Scheduler wiring ────────────────────────────────────────────────

def test_scheduler_registers_async_wrapper():
    src = Path("/app/backend/server.py").read_text()
    assert "async def _partner_trial_expiry_tick" in src, (
        "iter379 scheduler wrapper missing"
    )
    assert "id='partner_trial_expiry'" in src or 'id="partner_trial_expiry"' in src
    # Must NOT be the broken sync-lambda pattern
    assert 'lambda: safe_run("partner_trial_expiry"' not in src
    assert "lambda: safe_run('partner_trial_expiry'" not in src
