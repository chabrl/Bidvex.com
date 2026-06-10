"""
iter210 Step 1 — Vehicle Dealer payment-failure pipeline tests.

End-to-end coverage:
  1. handle_dealer_subscription_payment_failed sets grace fields + writes log + sends email
  2. Idempotency: same stripe_event_id processed twice → second call is a no-op
  3. enforce_dealer_grace_period suspends dealers whose grace expired > 7 days ago
  4. enforce_dealer_grace_period does NOT touch dealers whose grace is still active
  5. reactivate_dealer_after_payment clears grace + restores listings
"""
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient


@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    yield database
    client.close()


async def _seed_dealer(db, *, suspended=False, grace_days_ago=None):
    uid = f"iter210-grace-{uuid.uuid4().hex[:8]}"
    sub_id = f"sub_{uuid.uuid4().hex[:14]}"
    now = datetime.now(timezone.utc)
    doc = {
        "id": uid,
        "email": f"{uid}@example.com",
        "name": "Iter210 Dealer",
        "password": "x",
        "role": "user",
        "stripe_customer_id": f"cus_{uuid.uuid4().hex[:14]}",
        "vehicle_dealer_subscription_id": sub_id,
        "vehicle_dealer_subscription_status": "active",
        "created_at": now,
    }
    if grace_days_ago is not None:
        doc["vehicle_dealer_grace_started_at"] = now - timedelta(days=grace_days_ago)
        doc["vehicle_dealer_grace_expires_at"] = now - timedelta(days=grace_days_ago - 7)
        doc["vehicle_dealer_subscription_status"] = "past_due"
    if suspended:
        doc["vehicle_dealer_suspended"] = True
    await db.users.insert_one(doc)
    return uid, sub_id


# ─── Test 1: Day-1 trigger ────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_day1_starts_grace_writes_log_sends_email(db):
    from services import dealer_grace_period_service as svc

    uid, sub_id = await _seed_dealer(db)
    event_id = f"evt_{uuid.uuid4().hex[:14]}"
    invoice = {
        "id": f"in_{uuid.uuid4().hex[:14]}",
        "customer": "cus_test",
        "subscription": sub_id,
        "amount_due": 20000,
    }
    user = await db.users.find_one({"id": uid}, {"_id": 0})
    try:
        from services.emails import _email_core as email_notifications
        with patch.object(email_notifications, "send_email", new=AsyncMock(return_value=True)) as mock_send:
            r = await svc.handle_dealer_subscription_payment_failed(
                db, event_id=event_id, invoice=invoice, user=user,
            )
        assert "log_id" in r
        assert r["warning_email_sent"] is True
        assert mock_send.await_count == 1

        # Grace fields populated
        u2 = await db.users.find_one({"id": uid})
        assert u2["vehicle_dealer_grace_started_at"] is not None
        assert u2["vehicle_dealer_subscription_status"] == "past_due"

        # Log row created
        log = await db.dealer_compliance_log.find_one({"stripe_event_id": event_id})
        assert log is not None
        assert log["event"] == "payment_failed"
        assert log["warning_email_sent"] is True
    finally:
        await db.users.delete_one({"id": uid})
        await db.dealer_compliance_log.delete_many({"user_id": uid})


# ─── Test 2: Idempotent ───────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_same_event_id_processed_twice_is_noop(db):
    from services import dealer_grace_period_service as svc

    uid, sub_id = await _seed_dealer(db)
    event_id = f"evt_{uuid.uuid4().hex[:14]}"
    invoice = {"id": "in_x", "customer": "cus_x", "subscription": sub_id, "amount_due": 20000}
    user = await db.users.find_one({"id": uid}, {"_id": 0})
    try:
        from services.emails import _email_core as email_notifications
        with patch.object(email_notifications, "send_email", new=AsyncMock(return_value=True)) as mock_send:
            r1 = await svc.handle_dealer_subscription_payment_failed(db, event_id=event_id, invoice=invoice, user=user)
            r2 = await svc.handle_dealer_subscription_payment_failed(db, event_id=event_id, invoice=invoice, user=user)
        assert "log_id" in r1
        assert r2.get("skipped") == "already_processed"
        # Email sent exactly once across the two calls
        assert mock_send.await_count == 1
        # Exactly one log row
        rows = await db.dealer_compliance_log.count_documents({"stripe_event_id": event_id})
        assert rows == 1
    finally:
        await db.users.delete_one({"id": uid})
        await db.dealer_compliance_log.delete_many({"user_id": uid})


# ─── Test 3: Day-7 enforcement suspends ───────────────────────────────────
@pytest.mark.asyncio
async def test_grace_expired_triggers_suspension(db):
    from services.dealer_grace_period_service import enforce_dealer_grace_period

    uid, sub_id = await _seed_dealer(db, grace_days_ago=8)  # over 7 days
    # Seed a vehicle_sellers row + an active listing
    sid = str(uuid.uuid4())
    await db.vehicle_sellers.insert_one({"id": sid, "user_id": uid, "verification_status": "approved"})
    listing_id = str(uuid.uuid4())
    await db.vehicles.insert_one({"id": listing_id, "seller_id": sid, "status": "active"})

    try:
        from services.emails import _email_core as email_notifications
        with patch.object(email_notifications, "send_email", new=AsyncMock(return_value=True)):
            result = await enforce_dealer_grace_period(db)
        assert result["suspended_count"] >= 1

        u2 = await db.users.find_one({"id": uid})
        assert u2.get("vehicle_dealer_suspended") is True

        v = await db.vehicles.find_one({"id": listing_id})
        assert v["status"] == "suspended"
    finally:
        await db.users.delete_one({"id": uid})
        await db.vehicle_sellers.delete_one({"id": sid})
        await db.vehicles.delete_one({"id": listing_id})
        await db.dealer_compliance_log.delete_many({"user_id": uid})


# ─── Test 4: Day-3 (still in grace) does NOT suspend ──────────────────────
@pytest.mark.asyncio
async def test_grace_still_active_does_not_suspend(db):
    from services.dealer_grace_period_service import enforce_dealer_grace_period

    uid, sub_id = await _seed_dealer(db, grace_days_ago=3)
    try:
        from services.emails import _email_core as email_notifications
        with patch.object(email_notifications, "send_email", new=AsyncMock(return_value=True)):
            await enforce_dealer_grace_period(db)
        u2 = await db.users.find_one({"id": uid})
        assert not u2.get("vehicle_dealer_suspended")
    finally:
        await db.users.delete_one({"id": uid})
        await db.dealer_compliance_log.delete_many({"user_id": uid})


# ─── Test 5: Reactivation clears grace + restores listings ────────────────
@pytest.mark.asyncio
async def test_reactivate_clears_grace_and_restores_listings(db):
    from services.dealer_grace_period_service import reactivate_dealer_after_payment

    uid, sub_id = await _seed_dealer(db, suspended=True, grace_days_ago=10)
    sid = str(uuid.uuid4())
    await db.vehicle_sellers.insert_one({"id": sid, "user_id": uid, "verification_status": "approved"})
    listing_id = str(uuid.uuid4())
    await db.vehicles.insert_one({
        "id": listing_id, "seller_id": sid,
        "status": "suspended", "suspended_reason": "annual_fee_failed_after_grace",
    })

    try:
        await reactivate_dealer_after_payment(db, user_id=uid)

        u2 = await db.users.find_one({"id": uid})
        assert u2.get("vehicle_dealer_suspended") is False
        assert "vehicle_dealer_grace_started_at" not in u2

        v = await db.vehicles.find_one({"id": listing_id})
        assert v["status"] == "active"
        assert "suspended_reason" not in v
    finally:
        await db.users.delete_one({"id": uid})
        await db.vehicle_sellers.delete_one({"id": sid})
        await db.vehicles.delete_one({"id": listing_id})
        await db.dealer_compliance_log.delete_many({"user_id": uid})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
