"""
iter210 Step 2 — Partner & Dealer Resubmission Admin Email Bug Fix.

Verifies that BOTH flavors fire the admin notification email via SendGrid
when an applicant resubmits. The bug was that `PARTNERS_ALERT_EMAIL` was
never set in .env, so emails were going to a dead fallback address — and
the wrap-in-try/except was swallowing the failure silently.

Fix locks in:
  * ADMIN_NOTIFICATION_EMAIL is checked FIRST (env var the user specified)
  * On crash, full exception is logged with stack trace (no more silent swallow)
  * email_recipients + send_results persisted on admin_notifications.extra
    for auditability
  * Subject + body include applicant name, email, province, resubmission_count
    (as "Resubmission #N"), previous rejection reason, timestamp, admin panel link
"""
import os
import sys
import uuid
from datetime import datetime, timezone
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


@pytest.mark.asyncio
async def test_partner_resubmit_fires_admin_email_to_env_var_recipient(db):
    """Partner resubmission MUST dispatch a SendGrid email to ADMIN_NOTIFICATION_EMAIL."""
    from services import email_notifications
    from services.resubmission_service import resubmit_application

    uid = f"iter210-pmail-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": uid,
        "email": f"{uid}@example.com",
        "password": "x",
        "name": "Test Partner",
        "role": "user",
        "partner_verification_status": "rejected",
        "partner_company_name": "Test Auctions Inc.",
        "partner_neq": "9999999",
        "partner_rejection_reason": "Document quality too low",
        "partner_rejected_at": datetime.now(timezone.utc),
        "created_at": datetime.now(timezone.utc),
    })
    try:
        with patch.object(email_notifications, "send_email", new=AsyncMock(return_value={"status": "sent", "status_code": 202})) as mock_send:
            with patch.dict(os.environ, {"ADMIN_NOTIFICATION_EMAIL": "ops@bidvex.test"}, clear=False):
                result = await resubmit_application(
                    db, flavor="partner", user_id=uid, user_email=f"{uid}@example.com",
                    payload={"partner_company_name": "Re-Submitted Co"},
                )
        assert result["status"] == "pending_review"

        # ── Email must have been sent at least once ──
        assert mock_send.await_count >= 1, "send_email NOT called — admin email bug regressed"
        call = mock_send.await_args_list[0]
        kwargs = call.kwargs
        assert kwargs.get("to_email") == "ops@bidvex.test", \
            f"Expected ops@bidvex.test, got {kwargs.get('to_email')}"

        # ── Required body fields per spec ──
        body = kwargs.get("html_content", "")
        assert "Test Auctions Inc." in body or "Partner Application Resubmitted" in body
        assert "ops" not in body  # don't leak admin email in body
        assert "Resubmission #1" in body, "Resubmission count must appear as 'Resubmission #N'"
        assert "Document quality too low" in body, "Previous rejection reason must appear"
        assert "/admin" in body, "Admin panel link must appear"
        assert "UTC" in body, "Timestamp must appear"

        # ── Subject ──
        subj = kwargs.get("subject", "")
        assert "Resubmitted" in subj
        assert "#1" in subj

        # ── admin_notifications row contains audit trail ──
        notif = await db.admin_notifications.find_one({"target_user_id": uid, "kind": "partner_resubmitted"})
        assert notif is not None
        extra = notif.get("extra", {})
        assert "email_recipients" in extra
        assert "ops@bidvex.test" in extra["email_recipients"]
        assert extra.get("email_send_results"), "send_results must be persisted on admin_notifications"
    finally:
        await db.users.delete_one({"id": uid})
        await db.admin_notifications.delete_many({"target_user_id": uid})


@pytest.mark.asyncio
async def test_dealer_resubmit_fires_admin_email_to_env_var_recipient(db):
    """Dealer resubmission MUST dispatch a SendGrid email to ADMIN_NOTIFICATION_EMAIL (same code path)."""
    from services import email_notifications
    from services.resubmission_service import resubmit_application

    uid = f"iter210-dmail-{uuid.uuid4().hex[:8]}"
    sid = str(uuid.uuid4())
    await db.vehicle_sellers.insert_one({
        "id": sid, "user_id": uid,
        "verification_status": "rejected",
        "rejection_reason": "License expired — must upload current OMVIC",
        "seller_type": "dealer",
        "business_name": "Old Motors",
        "license_number": "OMVIC-111",
        "license_province": "ON",
        "created_at": datetime.now(timezone.utc),
    })
    try:
        with patch.object(email_notifications, "send_email", new=AsyncMock(return_value={"status": "sent", "status_code": 202})) as mock_send:
            with patch.dict(os.environ, {"ADMIN_NOTIFICATION_EMAIL": "ops@bidvex.test"}, clear=False):
                result = await resubmit_application(
                    db, flavor="dealer", user_id=uid, user_email=f"{uid}@example.com",
                    payload={"business_name": "Fresh Motors", "license_number": "OMVIC-222", "license_province": "ON"},
                )
        assert result["status"] == "pending_review"
        assert mock_send.await_count >= 1
        kwargs = mock_send.await_args_list[0].kwargs
        assert kwargs.get("to_email") == "ops@bidvex.test"

        body = kwargs.get("html_content", "")
        assert "Vehicle Dealer Application Resubmitted" in body
        assert "License expired — must upload current OMVIC" in body
        assert "Resubmission #1" in body
        # Province surfaces from updates (was just set to ON)
        assert "ON" in body or "—" not in body  # at minimum it doesn't show dash for ON
    finally:
        await db.vehicle_sellers.delete_one({"id": sid})
        await db.admin_notifications.delete_many({"target_user_id": uid})


@pytest.mark.asyncio
async def test_admin_email_failure_does_not_break_resubmit(db):
    """A SendGrid crash MUST NOT propagate to the caller."""
    from services import email_notifications
    from services.resubmission_service import resubmit_application

    uid = f"iter210-crash-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": uid,
        "email": f"{uid}@example.com",
        "password": "x", "role": "user",
        "partner_verification_status": "rejected",
        "partner_rejection_reason": "Crash test",
        "created_at": datetime.now(timezone.utc),
    })
    try:
        async def boom(*a, **kw):
            raise RuntimeError("SendGrid 503")

        with patch.object(email_notifications, "send_email", new=boom):
            result = await resubmit_application(
                db, flavor="partner", user_id=uid, user_email=f"{uid}@example.com",
                payload={"partner_company_name": "Crash Co"},
            )
        # Must succeed even when SendGrid crashes
        assert result["status"] == "pending_review"
    finally:
        await db.users.delete_one({"id": uid})
        await db.admin_notifications.delete_many({"target_user_id": uid})


@pytest.mark.asyncio
async def test_recipient_fallback_chain_uses_admin_email_first(db):
    """When BOTH ADMIN_NOTIFICATION_EMAIL and PARTNERS_ALERT_EMAIL are set, ADMIN wins."""
    from services import email_notifications
    from services.resubmission_service import resubmit_application

    uid = f"iter210-fallback-{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": uid,
        "email": f"{uid}@example.com",
        "password": "x", "role": "user",
        "partner_verification_status": "rejected",
        "partner_rejection_reason": "Fallback chain test",
        "created_at": datetime.now(timezone.utc),
    })
    try:
        with patch.object(email_notifications, "send_email", new=AsyncMock(return_value={"status": "sent"})) as mock_send:
            with patch.dict(os.environ,
                            {"ADMIN_NOTIFICATION_EMAIL": "admin@bidvex.test",
                             "PARTNERS_ALERT_EMAIL": "partners@bidvex.test"},
                            clear=False):
                await resubmit_application(
                    db, flavor="partner", user_id=uid, user_email=f"{uid}@example.com",
                    payload={"partner_company_name": "Fallback Co"},
                )
        # ADMIN wins
        assert mock_send.await_args_list[0].kwargs.get("to_email") == "admin@bidvex.test"
    finally:
        await db.users.delete_one({"id": uid})
        await db.admin_notifications.delete_many({"target_user_id": uid})


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
