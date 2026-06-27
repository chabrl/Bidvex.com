"""
iter316-E — Admin self-protection + self-recovery from accidental
contractor promotion.

Tests:
  • POST /api/twilio/admin/contractors with an existing-ADMIN email
    must 409 with cannot_demote_admin (NEVER silently downgrade).
  • POST /api/twilio/admin/users/{admin_id}/promote-to-contractor
    must 409 with cannot_demote_admin.
  • POST /api/twilio/auth/restore-admin-role
       - Current admin (role=admin) → 409 not_a_contractor.
       - Non-contractor non-admin (e.g. buyer) → 409 not_a_contractor.
       - Demoted-admin (role=dialer_contractor, previous_role=admin) →
         restores in one shot.
"""
from __future__ import annotations

import os
import sys
import httpx
import pytest
import asyncio

sys.path.insert(0, "/app/backend")

API_BASE = (os.environ.get("REACT_APP_BACKEND_URL")
            or "https://prod-verify-2.preview.emergentagent.com")
ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PASSWORD = "TestBuyer2026!"


def _h(tok): return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def admin_token() -> str:
    r = httpx.post(f"{API_BASE}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }, timeout=30.0)
    assert r.status_code == 200
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def admin_id() -> str:
    r = httpx.post(f"{API_BASE}/api/auth/login", json={
        "email": ADMIN_EMAIL, "password": ADMIN_PASSWORD,
    }, timeout=30.0)
    assert r.status_code == 200
    me = httpx.get(f"{API_BASE}/api/auth/me",
                    headers=_h(r.json()["access_token"]),
                    timeout=15.0).json()
    return me["id"]


@pytest.fixture(scope="module")
def buyer_token() -> str:
    r = httpx.post(f"{API_BASE}/api/auth/login", json={
        "email": BUYER_EMAIL, "password": BUYER_PASSWORD,
    }, timeout=30.0)
    if r.status_code != 200:
        pytest.skip(f"buyer login failed: {r.status_code}")
    return r.json()["access_token"]


# ─── Safeguard 1: cannot create-or-promote ADMIN to contractor via /admin/contractors

def test_admin_create_contractor_blocks_when_email_is_admin(admin_token):
    r = httpx.post(f"{API_BASE}/api/twilio/admin/contractors",
                   headers=_h(admin_token),
                   json={"email": ADMIN_EMAIL, "name": "should fail"},
                   timeout=30.0)
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert isinstance(d, dict)
    assert d["error"] == "cannot_demote_admin"
    assert "administrator" in d["message_en"].lower()
    assert "administrateur" in d["message_fr"].lower()


# ─── Safeguard 2: cannot promote ADMIN via /admin/users/{id}/promote-to-contractor

def test_admin_promote_user_blocks_admin_target(admin_token, admin_id):
    r = httpx.post(
        f"{API_BASE}/api/twilio/admin/users/{admin_id}/promote-to-contractor",
        headers=_h(admin_token), json={}, timeout=30.0,
    )
    assert r.status_code == 409, r.text
    d = r.json()["detail"]
    assert isinstance(d, dict)
    assert d["error"] == "cannot_demote_admin"


# ─── Self-restore endpoint — happy + sad paths ────────────────────────

def test_restore_admin_role_409_when_already_admin(admin_token):
    r = httpx.post(f"{API_BASE}/api/twilio/auth/restore-admin-role",
                   headers=_h(admin_token), timeout=30.0)
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "not_a_contractor"


def test_restore_admin_role_409_for_buyer_who_was_never_admin(buyer_token):
    r = httpx.post(f"{API_BASE}/api/twilio/auth/restore-admin-role",
                   headers=_h(buyer_token), timeout=30.0)
    # Buyer is not a contractor → 409 not_a_contractor.
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "not_a_contractor"


def test_restore_admin_role_requires_authentication():
    r = httpx.post(f"{API_BASE}/api/twilio/auth/restore-admin-role", timeout=30.0)
    assert r.status_code in (401, 403)


def test_restore_admin_role_round_trip_via_direct_db_setup():
    """End-to-end happy path: simulate the exact mistake by directly
    setting a test user's role to dialer_contractor + previous_role=admin
    in the DB (the API now refuses to do this via the front door), then
    call the recovery endpoint and assert the role is restored."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    from datetime import datetime, timezone
    import uuid as _uuid
    load_dotenv("/app/backend/.env")

    async def _setup_and_test():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        # 1. Create a fresh test-admin user directly in DB.
        email = f"iter316e-recover-{_uuid.uuid4().hex[:8]}@example.com"
        uid = str(_uuid.uuid4())
        import bcrypt
        pw = "RecoverMe2026!"
        await db.users.insert_one({
            "id":             uid,
            "email":          email,
            "password_hash":  bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
            "role":           "dialer_contractor",
            "previous_role":  "admin",
            "is_admin":       False,
            "is_active":      True,
            "email_verified": True,
            "first_name":     "Recover",
            "last_name":      "Test",
            "name":           "Recover Test",
            "created_at":     datetime.now(timezone.utc).isoformat(),
        })
        try:
            # 2. Log in as that user.
            login = httpx.post(f"{API_BASE}/api/auth/login", json={
                "email": email, "password": pw,
            }, timeout=30.0)
            assert login.status_code == 200, login.text
            tok = login.json()["access_token"]

            # 3. Call the recovery endpoint.
            r = httpx.post(
                f"{API_BASE}/api/twilio/auth/restore-admin-role",
                headers={"Authorization": f"Bearer {tok}"},
                timeout=30.0,
            )
            assert r.status_code == 200, r.text
            body = r.json()
            assert body["status"] == "restored"
            assert body["restored_role"] == "admin"

            # 4. Verify in DB the fields are properly cleaned up.
            doc = await db.users.find_one(
                {"id": uid},
                {"_id": 0, "role": 1, "is_admin": 1, "previous_role": 1,
                 "self_restored_at": 1, "promoted_to_contractor_at": 1},
            )
            assert doc["role"] == "admin"
            assert doc["is_admin"] is True
            assert "previous_role" not in doc
            assert "promoted_to_contractor_at" not in doc
            assert doc.get("self_restored_at")

            # 5. Calling again is now a no-op → 409 not_a_contractor.
            r2 = httpx.post(
                f"{API_BASE}/api/twilio/auth/restore-admin-role",
                headers={"Authorization": f"Bearer {tok}"},
                timeout=30.0,
            )
            assert r2.status_code == 409
            assert r2.json()["detail"]["error"] == "not_a_contractor"
        finally:
            # cleanup
            await db.users.delete_one({"id": uid})

    asyncio.run(_setup_and_test())


def test_restore_admin_role_eligibility_check_when_prev_role_not_admin():
    """If a user was a regular `user`/`buyer` who got promoted to
    contractor, the self-restore must REFUSE (it can't escalate)."""
    from motor.motor_asyncio import AsyncIOMotorClient
    from dotenv import load_dotenv
    from datetime import datetime, timezone
    import uuid as _uuid
    load_dotenv("/app/backend/.env")

    async def _setup_and_test():
        client = AsyncIOMotorClient(os.environ["MONGO_URL"])
        db = client[os.environ["DB_NAME"]]
        email = f"iter316e-noesc-{_uuid.uuid4().hex[:8]}@example.com"
        uid = str(_uuid.uuid4())
        import bcrypt
        pw = "NoEscalation2026!"
        await db.users.insert_one({
            "id":            uid,
            "email":         email,
            "password_hash": bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode(),
            "role":          "dialer_contractor",
            "previous_role": "user",   # NOT admin
            "is_admin":      False,
            "is_active":     True,
            "email_verified": True,
            "first_name":    "NoEsc",
            "last_name":     "Test",
            "name":          "NoEsc Test",
            "created_at":    datetime.now(timezone.utc).isoformat(),
        })
        try:
            login = httpx.post(f"{API_BASE}/api/auth/login", json={
                "email": email, "password": pw,
            }, timeout=30.0)
            assert login.status_code == 200, login.text
            tok = login.json()["access_token"]

            r = httpx.post(
                f"{API_BASE}/api/twilio/auth/restore-admin-role",
                headers={"Authorization": f"Bearer {tok}"},
                timeout=30.0,
            )
            # Must NOT escalate. Must respond 403 not_eligible.
            assert r.status_code == 403
            assert r.json()["detail"]["error"] == "not_eligible"

            doc = await db.users.find_one({"id": uid}, {"_id": 0, "role": 1, "is_admin": 1})
            assert doc["role"] == "dialer_contractor"
            assert doc["is_admin"] is False
        finally:
            await db.users.delete_one({"id": uid})

    asyncio.run(_setup_and_test())
