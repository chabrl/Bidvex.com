"""
iter210 Step 5 — Demo Account creator tests.

Covers:
  * create_demo_account for all 3 account types
  * Account flagged is_demo_account=True with bypass flags + vip_elite tier
  * Welcome email dispatched
  * Listing creation by a demo user returns 403 demo_mode_payments_disabled
  * Extend extends expiry; convert-to-real strips bypass flags
  * check_demo_account_expiry flips status + hides listings + emails
  * Invalid account_type → ValueError
"""
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
import httpx

sys.path.insert(0, "/app/backend")
from dotenv import load_dotenv
load_dotenv("/app/backend/.env", override=True)

from motor.motor_asyncio import AsyncIOMotorClient

API_URL = ""
with open("/app/frontend/.env") as f:
    for line in f:
        if line.startswith("REACT_APP_BACKEND_URL="):
            API_URL = line.split("=", 1)[1].strip().rstrip("/")
            break


@pytest_asyncio.fixture
async def db():
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    database = client[os.environ["DB_NAME"]]
    yield database
    client.close()


# ─── Unit: create_demo_account ────────────────────────────────────────────
@pytest.mark.asyncio
@pytest.mark.parametrize("account_type", ["vehicle_dealer", "partner", "storage_facility"])
async def test_create_demo_account_each_type(db, account_type):
    from services import email_notifications
    from services.demo_account_service import create_demo_account

    email = f"demo-{account_type}-{uuid.uuid4().hex[:6]}@example.com"
    try:
        with patch.object(email_notifications, "send_email", new=AsyncMock(return_value={"status": "sent"})) as mock_send:
            r = await create_demo_account(
                db,
                account_type=account_type,
                company_name=f"{account_type.title()} Demo Co",
                contact_email=email,
                province="ON",
                duration_days=14,
                notes="iter210 test",
                created_by_email="admin@bidvex.test",
            )
        assert r["email"] == email
        assert r["account_type"] == account_type
        assert r["welcome_email_sent"] is True
        assert len(r["temp_password"]) >= 10
        assert mock_send.await_count == 1

        u = await db.users.find_one({"email": email})
        assert u["is_demo_account"] is True
        assert u["subscription_tier"] == "vip_elite"
        assert u["phone_verified"] is True
        assert u["email_verified"] is True
        assert u["demo_status"] == "active"
        # Type-specific bypass
        if account_type == "vehicle_dealer":
            assert u["dealer_license_verified"] is True
            assert u["is_vehicle_dealer"] is True
        elif account_type == "partner":
            assert u["is_partner"] is True
            assert u["partner_verification_status"] == "verified"
        elif account_type == "storage_facility":
            assert u["is_storage_facility"] is True
    finally:
        await db.users.delete_many({"email": email})


@pytest.mark.asyncio
async def test_create_demo_rejects_invalid_account_type(db):
    from services.demo_account_service import create_demo_account
    with pytest.raises(ValueError):
        await create_demo_account(
            db,
            account_type="bogus",
            company_name="x", contact_email="x@y.com",
            province="ON", duration_days=14,
        )


@pytest.mark.asyncio
async def test_extend_pushes_expiry_out(db):
    from services.demo_account_service import create_demo_account, extend_demo_account
    from services import email_notifications

    email = f"demo-ext-{uuid.uuid4().hex[:6]}@example.com"
    try:
        with patch.object(email_notifications, "send_email", new=AsyncMock()):
            created = await create_demo_account(
                db, account_type="vehicle_dealer", company_name="Ext",
                contact_email=email, province="ON", duration_days=7,
            )
        r = await extend_demo_account(db, created["id"], additional_days=21)
        u = await db.users.find_one({"id": created["id"]})
        exp = u["demo_expires_at"]
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        # Should be 7 + 21 days from creation = roughly 28 days from now
        assert (exp - datetime.now(timezone.utc)).days >= 25
    finally:
        await db.users.delete_one({"email": email})


@pytest.mark.asyncio
async def test_convert_to_real_strips_bypass_flags(db):
    from services.demo_account_service import create_demo_account, convert_demo_to_real
    from services import email_notifications

    email = f"demo-conv-{uuid.uuid4().hex[:6]}@example.com"
    try:
        with patch.object(email_notifications, "send_email", new=AsyncMock()):
            created = await create_demo_account(
                db, account_type="partner", company_name="ConvCo",
                contact_email=email, province="QC", duration_days=14,
            )
            r = await convert_demo_to_real(db, created["id"])
        u = await db.users.find_one({"id": created["id"]})
        assert u["is_demo_account"] is False
        assert u["is_partner"] is False
        assert u["partner_verification_status"] == "unverified"
        assert u["demo_status"] == "converted"
    finally:
        await db.users.delete_one({"email": email})


@pytest.mark.asyncio
async def test_check_demo_expiry_flips_status(db):
    """Force expiry by backdating demo_expires_at and run the cron."""
    from services.demo_account_service import create_demo_account, check_demo_account_expiry
    from services import email_notifications

    email = f"demo-exp-{uuid.uuid4().hex[:6]}@example.com"
    try:
        with patch.object(email_notifications, "send_email", new=AsyncMock()):
            created = await create_demo_account(
                db, account_type="partner", company_name="ExpCo",
                contact_email=email, province="BC", duration_days=14,
            )
            # Backdate
            await db.users.update_one(
                {"id": created["id"]},
                {"$set": {"demo_expires_at": datetime.now(timezone.utc) - timedelta(days=1)}},
            )
            result = await check_demo_account_expiry(db)

        assert result["expired_count"] >= 1
        u = await db.users.find_one({"id": created["id"]})
        assert u["demo_status"] == "expired"
        assert "demo_expired_at" in u
    finally:
        await db.users.delete_one({"email": email})


# ─── HTTP: payment gate for demo users ────────────────────────────────────
@pytest.mark.asyncio
async def test_demo_user_cannot_create_listing(db):
    """A logged-in demo user creating a listing → 403 demo_mode_payments_disabled."""
    from services.demo_account_service import create_demo_account
    from services import email_notifications

    email = f"demo-pay-{uuid.uuid4().hex[:6]}@example.com"
    try:
        with patch.object(email_notifications, "send_email", new=AsyncMock()):
            created = await create_demo_account(
                db, account_type="vehicle_dealer", company_name="PayGate",
                contact_email=email, province="ON", duration_days=14,
            )
        # Log in via the live API
        r = httpx.post(
            f"{API_URL}/api/auth/login",
            json={"email": email, "password": created["temp_password"]},
            timeout=15,
        )
        assert r.status_code == 200, f"demo login failed: {r.text[:200]}"
        token = r.json().get("access_token") or r.json().get("token")
        listing_payload = {
            "title": "Demo listing", "description": "x" * 30,
            "category": "lots:test", "condition": "new",
            "starting_price": 100, "auction_end_date": "2027-01-01T00:00:00Z",
            "agreement_accepted": True, "payment_method": "stripe",
            "location": "Montreal", "city": "Montreal", "region": "QC", "country": "Canada",
        }
        r2 = httpx.post(
            f"{API_URL}/api/listings",
            headers={"Authorization": f"Bearer {token}"},
            json=listing_payload, timeout=20,
        )
        assert r2.status_code == 403, f"expected 403, got {r2.status_code}: {r2.text[:200]}"
        detail = r2.json().get("detail")
        assert isinstance(detail, dict)
        assert detail.get("error") == "demo_mode_payments_disabled"
        assert "message_en" in detail and "message_fr" in detail
    finally:
        await db.users.delete_one({"email": email})


# ─── HTTP: admin endpoints ────────────────────────────────────────────────
def _admin_token() -> str:
    r = httpx.post(
        f"{API_URL}/api/auth/login",
        json={"email": "charbel911@gmail.com", "password": "Anderosli123!@#"},
        timeout=15,
    )
    r.raise_for_status()
    return r.json().get("access_token") or r.json().get("token")


def test_admin_list_demo_accounts_endpoint():
    token = _admin_token()
    r = httpx.get(
        f"{API_URL}/api/admin/demo-accounts",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert isinstance(body["items"], list)


def test_admin_create_demo_via_http():
    token = _admin_token()
    email = f"demo-http-{uuid.uuid4().hex[:6]}@example.com"
    r = httpx.post(
        f"{API_URL}/api/admin/demo-accounts",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "account_type": "storage_facility",
            "company_name": "HTTP Demo",
            "contact_email": email,
            "province": "NS",
            "duration_days": 7,
            "notes": "iter210 HTTP test",
        },
        timeout=20,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["email"] == email
    assert body["account_type"] == "storage_facility"
    assert "temp_password" in body
    # Cleanup
    httpx.delete(
        f"{API_URL}/api/admin/demo-accounts/{body['id']}",
        headers={"Authorization": f"Bearer {token}"},
        timeout=15,
    )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
