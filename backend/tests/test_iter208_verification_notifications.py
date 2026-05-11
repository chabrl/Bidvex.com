"""
iter208 — Verification notifications end-to-end test.

Verifies that:
  1. Partner approve  → email sent + admin_notifications row + seller_notifications row
  2. Partner reject   → email sent + admin_notifications row + seller_notifications row
  3. Dealer-license approve → email sent + admin_notifications row + seller_notifications row
  4. Dealer-license reject  → email sent + admin_notifications row + seller_notifications row
  5. URL migration:
       - localhost prefix → relative
       - bidvex.com prefix → relative
       - already-relative → unchanged
       - external URL → unchanged

All email assertions monkey-patch `send_email` to avoid actually hitting SendGrid.
"""
import os
import sys
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env")

from motor.motor_asyncio import AsyncIOMotorClient

# Make sure backend code can import server config
os.environ.setdefault("MONGO_URL", os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
os.environ.setdefault("DB_NAME", os.environ.get("DB_NAME", "test"))


@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    yield database
    client.close()


# ─── URL normalization tests ──────────────────────────────────────────────

def test_normalize_url_strips_localhost():
    from scripts.migrate_doc_urls_to_relative import _normalize_url
    assert _normalize_url("http://localhost:8001/api/uploads/partner_docs/foo.pdf") == "/api/uploads/partner_docs/foo.pdf"


def test_normalize_url_strips_bidvex_com():
    from scripts.migrate_doc_urls_to_relative import _normalize_url
    assert _normalize_url("https://www.bidvex.com/api/uploads/partner_docs/foo.pdf") == "/api/uploads/partner_docs/foo.pdf"
    assert _normalize_url("https://bidvex.com/api/uploads/partner_docs/foo.pdf") == "/api/uploads/partner_docs/foo.pdf"


def test_normalize_url_strips_preview_hostname():
    from scripts.migrate_doc_urls_to_relative import _normalize_url
    assert _normalize_url("https://prod-verify-2.preview.emergentagent.com/api/uploads/foo.pdf") == "/api/uploads/foo.pdf"


def test_normalize_url_preserves_relative_path():
    from scripts.migrate_doc_urls_to_relative import _normalize_url
    assert _normalize_url("/api/uploads/partner_docs/foo.pdf") == "/api/uploads/partner_docs/foo.pdf"


def test_normalize_url_preserves_external_url():
    """External (non-BidVex) URLs are left untouched for manual audit."""
    from scripts.migrate_doc_urls_to_relative import _normalize_url
    assert _normalize_url("https://example.com/external.pdf") == "https://example.com/external.pdf"


def test_normalize_url_handles_none_and_empty():
    from scripts.migrate_doc_urls_to_relative import _normalize_url
    assert _normalize_url(None) is None
    assert _normalize_url("") == ""


# ─── Partner approve flow ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_partner_approve_dispatches_email_and_notifications(db):
    from services import verification_service as vs

    uid = f"iter208-test-{uuid.uuid4().hex[:8]}"
    user = {
        "id": uid,
        "email": f"{uid}@bidvex.test",
        "name": "Iter208 Partner",
        "partner_company_name": "Iter208 Inc.",
        "partner_neq": "1234567890",
    }
    admin_id = f"admin-{uuid.uuid4().hex[:8]}"

    with patch.object(vs, "_send_partner_approved_email", new=AsyncMock(return_value=True)) as mock_send:
        result = await vs.notify_partner_decision(
            db, user=user, decision="approve", admin_id=admin_id,
            checkout_url="https://checkout.stripe.com/example",
        )

    assert result["email_sent"] is True
    assert result["admin_notif"] is True
    assert result["seller_notif"] is True
    mock_send.assert_awaited_once()

    # admin_notifications row
    admin_row = await db.admin_notifications.find_one(
        {"kind": "partner_approved", "target_user_id": uid}, {"_id": 0}
    )
    assert admin_row is not None
    assert admin_row.get("admin_id") == admin_id

    # seller_notifications row (bilingual)
    seller_row = await db.seller_notifications.find_one(
        {"kind": "partner_approved", "user_id": uid}, {"_id": 0}
    )
    assert seller_row is not None
    assert "verified" in seller_row.get("body_en", "").lower()
    assert "vérifié" in seller_row.get("body_fr", "").lower()

    # cleanup
    await db.admin_notifications.delete_many({"target_user_id": uid})
    await db.seller_notifications.delete_many({"user_id": uid})


# ─── Partner reject flow ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_partner_reject_dispatches_email_and_notifications(db):
    from services import verification_service as vs

    uid = f"iter208-test-{uuid.uuid4().hex[:8]}"
    user = {
        "id": uid,
        "email": f"{uid}@bidvex.test",
        "name": "Iter208 Reject",
        "partner_company_name": "Iter208 Rejected Co.",
    }
    admin_id = f"admin-{uuid.uuid4().hex[:8]}"
    reason = "Missing NEQ proof — please re-upload"

    with patch.object(vs, "_send_partner_rejected_email", new=AsyncMock(return_value=True)) as mock_send:
        result = await vs.notify_partner_decision(
            db, user=user, decision="reject", admin_id=admin_id,
            rejection_reason=reason,
        )

    assert result["email_sent"] is True
    mock_send.assert_awaited_once()
    args = mock_send.await_args
    # Reason must be passed through
    assert reason in (args.args + tuple(args.kwargs.values()))

    admin_row = await db.admin_notifications.find_one(
        {"kind": "partner_rejected", "target_user_id": uid}, {"_id": 0}
    )
    assert admin_row is not None
    assert admin_row.get("extra", {}).get("reason") == reason

    seller_row = await db.seller_notifications.find_one(
        {"kind": "partner_rejected", "user_id": uid}, {"_id": 0}
    )
    assert seller_row is not None
    assert reason in seller_row.get("body_en", "")
    assert reason in seller_row.get("body_fr", "")
    # Action Required bilingual title
    assert "Action Required" in seller_row.get("title_en", "")
    assert "Action requise" in seller_row.get("title_fr", "")

    # cleanup
    await db.admin_notifications.delete_many({"target_user_id": uid})
    await db.seller_notifications.delete_many({"user_id": uid})


# ─── Dealer license approve flow ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_dealer_license_approve_dispatches_email_and_notifications(db):
    from services import verification_service as vs

    uid = f"iter208-test-{uuid.uuid4().hex[:8]}"
    lic_id = f"lic-{uuid.uuid4().hex[:8]}"
    user = {"id": uid, "email": f"{uid}@bidvex.test", "name": "Dealer Approve"}
    license_doc = {
        "id": lic_id,
        "user_id": uid,
        "license_number": "OMVIC-12345",
        "jurisdiction": "ON",
        "expiry_date": datetime.now(timezone.utc) + timedelta(days=365),
        "status": "approved",
    }
    admin_id = f"admin-{uuid.uuid4().hex[:8]}"

    with patch("services.verification_service.send_dealer_license_approved_email",
               new=AsyncMock(return_value=True)) as mock_send:
        result = await vs.notify_dealer_license_decision(
            db, user=user, license_doc=license_doc, decision="approve", admin_id=admin_id,
        )

    assert result["email_sent"] is True
    mock_send.assert_awaited_once()

    admin_row = await db.admin_notifications.find_one(
        {"kind": "dealer_license_approved", "target_user_id": uid}, {"_id": 0}
    )
    assert admin_row is not None
    assert admin_row.get("extra", {}).get("license_id") == lic_id

    seller_row = await db.seller_notifications.find_one(
        {"kind": "dealer_license_approved", "user_id": uid}, {"_id": 0}
    )
    assert seller_row is not None
    assert "verified" in seller_row.get("body_en", "").lower()
    assert "vérifié" in seller_row.get("body_fr", "").lower()

    await db.admin_notifications.delete_many({"target_user_id": uid})
    await db.seller_notifications.delete_many({"user_id": uid})


# ─── Dealer license reject flow ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_dealer_license_reject_dispatches_email_and_notifications(db):
    from services import verification_service as vs

    uid = f"iter208-test-{uuid.uuid4().hex[:8]}"
    lic_id = f"lic-{uuid.uuid4().hex[:8]}"
    user = {"id": uid, "email": f"{uid}@bidvex.test", "name": "Dealer Reject"}
    license_doc = {
        "id": lic_id,
        "user_id": uid,
        "license_number": "OMVIC-99999",
        "jurisdiction": "ON",
        "status": "rejected",
    }
    admin_id = f"admin-{uuid.uuid4().hex[:8]}"
    reason = "License expiry date is unreadable on the upload"

    with patch("services.verification_service.send_dealer_license_rejected_email",
               new=AsyncMock(return_value=True)) as mock_send:
        result = await vs.notify_dealer_license_decision(
            db, user=user, license_doc=license_doc, decision="reject",
            admin_id=admin_id, rejection_reason=reason,
        )

    assert result["email_sent"] is True
    mock_send.assert_awaited_once()

    admin_row = await db.admin_notifications.find_one(
        {"kind": "dealer_license_rejected", "target_user_id": uid}, {"_id": 0}
    )
    assert admin_row is not None
    assert admin_row.get("extra", {}).get("reason") == reason

    seller_row = await db.seller_notifications.find_one(
        {"kind": "dealer_license_rejected", "user_id": uid}, {"_id": 0}
    )
    assert seller_row is not None
    assert reason in seller_row.get("body_en", "")
    assert reason in seller_row.get("body_fr", "")
    assert "Action Required" in seller_row.get("title_en", "")
    assert "Action requise" in seller_row.get("title_fr", "")

    await db.admin_notifications.delete_many({"target_user_id": uid})
    await db.seller_notifications.delete_many({"user_id": uid})


# ─── Resilience: email failure does not raise ────────────────────────────

@pytest.mark.asyncio
async def test_email_failure_does_not_raise(db):
    """Even if SendGrid blows up, the decision endpoint never sees an exception."""
    from services import verification_service as vs

    uid = f"iter208-test-{uuid.uuid4().hex[:8]}"
    user = {"id": uid, "email": f"{uid}@bidvex.test", "name": "Robust"}

    async def boom(*a, **kw):
        raise RuntimeError("SendGrid melted")

    with patch.object(vs, "_send_partner_approved_email", side_effect=boom):
        result = await vs.notify_partner_decision(
            db, user=user, decision="approve", admin_id="admin-x",
        )

    # email_sent False but admin/seller rows still written
    assert result["email_sent"] is False
    assert result["admin_notif"] is True
    assert result["seller_notif"] is True

    await db.admin_notifications.delete_many({"target_user_id": uid})
    await db.seller_notifications.delete_many({"user_id": uid})


# ─── Invalid decision → no-op (not partial state) ────────────────────────

@pytest.mark.asyncio
async def test_invalid_decision_is_noop(db):
    from services import verification_service as vs

    uid = f"iter208-test-{uuid.uuid4().hex[:8]}"
    user = {"id": uid, "email": f"{uid}@bidvex.test"}

    result = await vs.notify_partner_decision(
        db, user=user, decision="maybe", admin_id="admin-x",
    )
    assert result == {"email_sent": False, "admin_notif": False, "seller_notif": False}

    # No rows written
    admin_row = await db.admin_notifications.find_one({"target_user_id": uid})
    seller_row = await db.seller_notifications.find_one({"user_id": uid})
    assert admin_row is None
    assert seller_row is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
