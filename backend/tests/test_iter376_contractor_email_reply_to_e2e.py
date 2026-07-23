"""
iter376 REGRESSION TEST — Contractor Email Hub Reply-To routing (end-to-end).

Unlike iter372's unit tests (which pass synthetic dicts to the resolver),
this test exercises the *actual HTTP route*:
    POST /api/twilio/contractor/emails/send

so it catches the class of bug where the route's Mongo projection omits
`personal_email` (as it did before iter376). The test seeds two
contractors — one with a valid `personal_email`, one without — and
asserts the persisted `contractor_emails` row uses the correct Reply-To
and `is_fallback` flag on each.

SendGrid dispatch is stubbed out (no API key + DRY-RUN path in
_sendgrid_dispatch), so the test never sends a real email.
"""

import os
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from motor.motor_asyncio import AsyncIOMotorClient
from passlib.hash import bcrypt


BASE_URL = os.environ.get(
    "TEST_BASE_URL",
    "https://prod-verify-2.preview.emergentagent.com",
).rstrip("/")


def _load_backend_env():
    env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    if not os.path.exists(env_path):
        return
    with open(env_path) as fh:
        for line in fh:
            if "=" not in line or line.startswith("#"):
                continue
            k, _, v = line.strip().partition("=")
            if k and v and k not in os.environ:
                os.environ[k] = v


async def _db():
    _load_backend_env()
    client = AsyncIOMotorClient(os.environ["MONGO_URL"])
    return client[os.environ["DB_NAME"]], client


async def _seed_contractor(db, email: str, personal_email):
    """Insert a fresh contractor directly into Mongo (already-verified,
    already-signed) so we can log in via /api/auth/login."""
    now = datetime.now(timezone.utc).isoformat()
    pwd = "ContractorTest!2026"
    doc = {
        "id": f"iter376-c-{uuid.uuid4().hex[:12]}",
        "email": email,
        "password_hash": bcrypt.hash(pwd),
        "name": "Iter376 Contractor",
        "first_name": "Iter376",
        "last_name": "Contractor",
        "role": "dialer_contractor",
        "is_active": True,
        "email_verified": True,
        "preferred_language": "en",
        "created_at": now,
        "updated_at": now,
        "extension_number": 999,
        "contractor_agreement_signed_at": now,
        "contractor_agreement_version": "v2",
    }
    if personal_email is not None:
        doc["personal_email"] = personal_email
    await db.users.insert_one(doc)
    # Seed the contractor_agreements row so the Email Hub gate passes.
    await db.contractor_agreements.insert_one({
        "id": f"iter376-agr-{uuid.uuid4().hex[:10]}",
        "contractor_id": doc["id"],
        "agreement_version": "v2.0",
        "signed_at": now,
        "ip_address": "127.0.0.1",
        "user_agent": "pytest-iter376",
    })
    return doc["id"], pwd


async def _login(client, email, pwd):
    r = await client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": email, "password": pwd},
        timeout=15,
    )
    assert r.status_code == 200, f"login failed {r.status_code}: {r.text}"
    return r.json()["access_token"]


async def _cleanup(db, ids, emails):
    if ids:
        await db.contractor_emails.delete_many({"contractor_id": {"$in": ids}})
        await db.contractor_agreements.delete_many({"contractor_id": {"$in": ids}})
    if emails:
        await db.users.delete_many({"email": {"$in": emails}})


# ─── Tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_send_uses_contractor_personal_email_as_reply_to():
    """A contractor whose `personal_email` is set MUST see it stamped as
    the outbound Reply-To in the persisted contractor_emails row."""
    db, mongo = await _db()
    email = f"iter376-c-with-{uuid.uuid4().hex[:6]}@bidvex-qa.com"
    personal = "jane.doe.iter376@example.com"
    try:
        cid, pwd = await _seed_contractor(db, email, personal)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            tok = await _login(client, email, pwd)
            r = await client.post(
                f"{BASE_URL}/api/twilio/contractor/emails/send",
                headers={"Authorization": f"Bearer {tok}"},
                json={
                    "to_email": "recipient.iter376@example.com",
                    "subject": "iter376 e2e — personal_email routing",
                    "body_html": "<p>Testing Reply-To routing.</p>",
                    "locale": "en",
                },
                timeout=20,
            )
            assert r.status_code == 200, f"send failed {r.status_code}: {r.text}"
            body = r.json()

        # The response returns the persisted row.
        assert body.get("from_email") == "contractor@bidvex.com", body
        assert body.get("from_name") == "BidVex Contractor", body
        assert body.get("reply_to") == personal, (
            f"Expected reply_to == contractor's personal_email ({personal}), "
            f"got {body.get('reply_to')}. This is the exact iter372→iter376 "
            f"regression: /api/twilio/contractor/emails/send projection was "
            f"missing `personal_email`, so the resolver silently used the "
            f"support@bidvex.com fallback."
        )
        assert body.get("reply_to_is_fallback") is False, body

        # Cross-check the DB row (belt & suspenders — the response is
        # dict(row) so it should already match).
        row = await db.contractor_emails.find_one({"id": body["id"]}, {"_id": 0})
        assert row["reply_to"] == personal
        assert row["reply_to_is_fallback"] is False
    finally:
        await _cleanup(db, [cid], [email])
        mongo.close()


@pytest.mark.asyncio
async def test_send_falls_back_when_personal_email_missing():
    """A contractor with NO personal_email must fall back to
    support@bidvex.com AND the row must flag `reply_to_is_fallback=True`."""
    db, mongo = await _db()
    email = f"iter376-c-none-{uuid.uuid4().hex[:6]}@bidvex-qa.com"
    try:
        cid, pwd = await _seed_contractor(db, email, None)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            tok = await _login(client, email, pwd)
            r = await client.post(
                f"{BASE_URL}/api/twilio/contractor/emails/send",
                headers={"Authorization": f"Bearer {tok}"},
                json={
                    "to_email": "recipient.iter376@example.com",
                    "subject": "iter376 e2e — fallback routing",
                    "body_html": "<p>Should hit fallback.</p>",
                    "locale": "en",
                },
                timeout=20,
            )
            assert r.status_code == 200, f"send failed {r.status_code}: {r.text}"
            body = r.json()

        assert body.get("reply_to") == "support@bidvex.com", body
        assert body.get("reply_to_name") == "BidVex Support", body
        assert body.get("reply_to_is_fallback") is True, body
    finally:
        await _cleanup(db, [cid], [email])
        mongo.close()


@pytest.mark.asyncio
async def test_send_falls_back_when_personal_email_is_invalid_string():
    """A contractor with a corrupted personal_email (not a valid email
    format) must still fall back safely — never dispatch to garbage."""
    db, mongo = await _db()
    email = f"iter376-c-bad-{uuid.uuid4().hex[:6]}@bidvex-qa.com"
    try:
        cid, pwd = await _seed_contractor(db, email, "not-a-real-address")
        async with httpx.AsyncClient(follow_redirects=True) as client:
            tok = await _login(client, email, pwd)
            r = await client.post(
                f"{BASE_URL}/api/twilio/contractor/emails/send",
                headers={"Authorization": f"Bearer {tok}"},
                json={
                    "to_email": "recipient.iter376@example.com",
                    "subject": "iter376 e2e — invalid personal_email",
                    "body_html": "<p>Corrupt personal email.</p>",
                    "locale": "en",
                },
                timeout=20,
            )
            assert r.status_code == 200, f"send failed {r.status_code}: {r.text}"
            body = r.json()

        assert body.get("reply_to") == "support@bidvex.com"
        assert body.get("reply_to_is_fallback") is True
    finally:
        await _cleanup(db, [cid], [email])
        mongo.close()


@pytest.mark.asyncio
async def test_patch_profile_persists_personal_email_and_next_send_uses_it():
    """
    Full round-trip: contractor edits personal_email through the profile
    PATCH endpoint (the same one the frontend uses) → the next outbound
    email must reflect the newly saved value. Confirms both the projection
    fix AND the profile endpoint wiring work together.
    """
    db, mongo = await _db()
    email = f"iter376-c-patch-{uuid.uuid4().hex[:6]}@bidvex-qa.com"
    new_personal = "post-patch.iter376@example.com"
    try:
        cid, pwd = await _seed_contractor(db, email, None)
        async with httpx.AsyncClient(follow_redirects=True) as client:
            tok = await _login(client, email, pwd)

            # 1. First send — no personal_email → fallback expected.
            r = await client.post(
                f"{BASE_URL}/api/twilio/contractor/emails/send",
                headers={"Authorization": f"Bearer {tok}"},
                json={
                    "to_email": "recipient.iter376@example.com",
                    "subject": "iter376 e2e — before PATCH",
                    "body_html": "<p>Before patch.</p>",
                    "locale": "en",
                },
                timeout=20,
            )
            assert r.status_code == 200
            before = r.json()
            assert before["reply_to_is_fallback"] is True

            # 2. Save personal_email through the SAME endpoint the frontend uses.
            r = await client.patch(
                f"{BASE_URL}/api/twilio/contractor/profile/me",
                headers={"Authorization": f"Bearer {tok}"},
                json={"personal_email": new_personal},
                timeout=15,
            )
            assert r.status_code == 200, r.text
            assert r.json().get("personal_email") == new_personal

            # 3. Second send — must now use the freshly saved personal_email.
            r = await client.post(
                f"{BASE_URL}/api/twilio/contractor/emails/send",
                headers={"Authorization": f"Bearer {tok}"},
                json={
                    "to_email": "recipient.iter376@example.com",
                    "subject": "iter376 e2e — after PATCH",
                    "body_html": "<p>After patch.</p>",
                    "locale": "en",
                },
                timeout=20,
            )
            assert r.status_code == 200
            after = r.json()
            assert after["reply_to"] == new_personal, (
                f"Expected reply_to = {new_personal} after profile patch, "
                f"got {after.get('reply_to')}. Projection bug likely reintroduced."
            )
            assert after["reply_to_is_fallback"] is False
    finally:
        await _cleanup(db, [cid], [email])
        mongo.close()
