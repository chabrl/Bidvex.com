"""
iter482 Security Hardening — regression tests for SEC-001 and SEC-002.

SEC-001 · Unauthenticated notification injection to any user
  - Historical bug: `POST /api/notifications/create` had no auth dependency
    and accepted a client-supplied `user_id`, letting anyone write phishing
    notifications into any user's feed.
  - Fix: The endpoint was REMOVED entirely. Admin-driven creation now
    goes exclusively through `POST /api/notifications/admin/send`, which
    requires an authenticated admin session.

SEC-002 · Password-reset backdoor gated only by the JWT signing secret
  - Historical bug: `POST /api/auth/admin-force-sync` reset any account's
    password when the caller supplied a header equal to `JWT_SECRET` (a
    shared-secret bypass, plain `!=` compare, not real auth).
  - Fix: The endpoint was REMOVED entirely.

Both endpoints must now return 404 (route not registered). The surviving
admin-driven notification endpoint (`/notifications/admin/send`) is
covered by an admin-vs-non-admin auth matrix.

Tokens are minted directly against the backend's JWT_SECRET so the tests
do not touch the login rate limiter.
"""
from __future__ import annotations
import os
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
MONGO_URL   = os.environ["MONGO_URL"]
DB_NAME     = os.environ["DB_NAME"]
JWT_SECRET  = os.environ["JWT_SECRET"]
JWT_ALG     = os.environ.get("JWT_ALGORITHM", "HS256")


def _mint(user_id: str, email: str, role: str) -> str:
    """Mint the same JWT shape the FastAPI auth dependency accepts."""
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode(
        {"sub": user_id, "email": email, "role": role, "exp": exp},
        JWT_SECRET, algorithm=JWT_ALG,
    )


@pytest_asyncio.fixture(scope="module")
async def seeded_users():
    """Seed one admin + one buyer, cleaned up at teardown."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    ids = {}
    for role in ("admin", "buyer"):
        uid = f"sec482_{role}_{uuid.uuid4().hex[:8]}"
        email = f"{uid}@bidvex-sec482.com"
        await db.users.insert_one({
            "id": uid,
            "email": email,
            "role": role,
            "name": f"SEC482 {role}",
            "is_active": True,
            "email_verified": True,
            "is_admin": role == "admin",
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        ids[role] = {"id": uid, "email": email, "token": _mint(uid, email, role)}
    yield ids
    for r in ids.values():
        await db.users.delete_one({"id": r["id"]})
        await db.notifications.delete_many({"user_id": r["id"]})
    client.close()


# ─── SEC-001 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sec001_legacy_create_endpoint_is_removed_anonymous():
    """Anonymous POST /api/notifications/create must NOT succeed.

    We probe with the exact query-string shape the audit used to confirm
    the original vulnerability — this proves the attack surface is gone,
    not merely gated. Accepts 404 (route removed) or 405 (SPA GET
    catch-all matches the path, no POST handler); both prove the route
    is unregistered as a POST endpoint.
    """
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post(
            "/api/notifications/create",
            params={
                "user_id": "__sec482_probe__",
                "notification_type": "test",
                "title": "should never write",
                "message": "should never write",
            },
        )
    assert r.status_code in (404, 405), (
        f"Legacy /api/notifications/create route must be removed. "
        f"Got {r.status_code}. Body: {r.text[:400]}"
    )

    # Belt-and-suspenders: confirm no row was inserted by the probe.
    client = AsyncIOMotorClient(MONGO_URL)
    try:
        db = client[DB_NAME]
        stray = await db.notifications.count_documents({"user_id": "__sec482_probe__"})
        assert stray == 0, "Removed endpoint must not write to the DB"
    finally:
        client.close()


@pytest.mark.asyncio
async def test_sec001_legacy_create_endpoint_is_removed_with_admin_token(seeded_users):
    """Even a valid admin token must not resurrect the removed path.

    Accepts 404 or 405 — both prove the POST route is truly unregistered
    (not merely auth-gated).
    """
    headers = {"Authorization": f"Bearer {seeded_users['admin']['token']}"}
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post(
            "/api/notifications/create",
            params={
                "user_id": seeded_users["buyer"]["id"],
                "notification_type": "test",
                "title": "should never route",
                "message": "should never route",
            },
            headers=headers,
        )
    assert r.status_code in (404, 405), (
        f"Legacy /api/notifications/create must be gone even with an admin token. "
        f"Got {r.status_code}. Body: {r.text[:400]}"
    )


@pytest.mark.asyncio
async def test_sec001_admin_send_rejects_anonymous():
    """The surviving admin endpoint must reject unauthenticated callers."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post(
            "/api/notifications/admin/send",
            json={
                "user_id": "__sec482_probe__",
                "title": "anonymous phish attempt",
                "body":  "should be rejected",
            },
        )
    assert r.status_code in (401, 403), (
        f"admin/send must require auth. Got {r.status_code}. Body: {r.text[:400]}"
    )


@pytest.mark.asyncio
async def test_sec001_admin_send_rejects_non_admin(seeded_users):
    """A logged-in NON-admin must NOT be able to send notifications."""
    headers = {"Authorization": f"Bearer {seeded_users['buyer']['token']}"}
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post(
            "/api/notifications/admin/send",
            json={
                "user_id": seeded_users["admin"]["id"],
                "title": "buyer trying to phish admin",
                "body":  "should be forbidden",
            },
            headers=headers,
        )
    assert r.status_code == 403, (
        f"Non-admin must get 403 from admin/send. Got {r.status_code}. Body: {r.text[:400]}"
    )


@pytest.mark.asyncio
async def test_sec001_admin_send_accepts_admin(seeded_users):
    """The surviving admin endpoint still works for real admins."""
    headers = {"Authorization": f"Bearer {seeded_users['admin']['token']}"}
    recipient = seeded_users["buyer"]["id"]
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post(
            "/api/notifications/admin/send",
            json={
                "user_id": recipient,
                "title": "sec482 regression — legitimate admin send",
                "body":  "must succeed",
            },
            headers=headers,
        )
    assert r.status_code == 200, (
        f"Legit admin call must succeed. Got {r.status_code}. Body: {r.text[:400]}"
    )
    payload = r.json()
    assert payload.get("success") is True
    assert payload.get("sent_count") == 1


# ─── SEC-002 ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_sec002_admin_force_sync_route_is_removed_anonymous():
    """Anonymous POST /api/auth/admin-force-sync must NOT succeed.

    Even without the correct sync-key header, the endpoint used to return
    403 (route existed). A 404 or 405 proves the route is unregistered as
    a POST endpoint.
    """
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post(
            "/api/auth/admin-force-sync",
            json={"email": "charbel911@gmail.com", "new_password": "should-never-work"},
        )
    assert r.status_code in (404, 405), (
        f"admin-force-sync route must be removed. Got {r.status_code}. "
        f"Body: {r.text[:400]}"
    )


@pytest.mark.asyncio
async def test_sec002_admin_force_sync_route_is_removed_with_sync_key():
    """Presenting the JWT_SECRET as the sync-key header must ALSO fail.

    This is the exact attack the audit called out: leaking JWT_SECRET
    previously granted arbitrary password reset. It must be impossible
    now regardless of any credential the attacker has.
    """
    headers = {"X-Sync-Key": JWT_SECRET}
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post(
            "/api/auth/admin-force-sync",
            json={"email": "charbel911@gmail.com", "new_password": "should-never-work"},
            headers=headers,
        )
    assert r.status_code in (404, 405), (
        f"admin-force-sync must be gone even when the caller knows JWT_SECRET. "
        f"Got {r.status_code}. Body: {r.text[:400]}"
    )


# ─── Static verification of the source files themselves ──────────────────


def test_sec001_source_no_longer_defines_create_endpoint():
    """Guard against accidental reintroduction of the deleted route."""
    with open("/app/backend/routes/notifications.py", "r", encoding="utf-8") as fh:
        src = fh.read()
    assert '@notifications_router.post("/notifications/create")' not in src, (
        "The /notifications/create endpoint must remain deleted (SEC-001)."
    )
    # Sanity: the surviving admin endpoint still exists.
    assert '@notifications_router.post("/notifications/admin/send")' in src


def test_sec002_source_no_longer_defines_admin_force_sync():
    """Guard against accidental reintroduction of the deleted backdoor."""
    with open("/app/backend/routes/auth.py", "r", encoding="utf-8") as fh:
        src = fh.read()
    assert '@auth_router.post("/admin-force-sync")' not in src, (
        "The /admin-force-sync endpoint must remain deleted (SEC-002)."
    )
    assert "async def admin_force_password_sync" not in src, (
        "The admin_force_password_sync handler must remain deleted (SEC-002)."
    )
    # Sanity: no residual shared-secret comparison against JWT_SECRET.
    assert "sync_key != JWT_SECRET" not in src, (
        "Shared-secret sync-key comparison must not exist (SEC-002)."
    )
