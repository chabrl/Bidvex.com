"""iter322 — HTTP-level integration tests (real preview URL).

Validates the THREE bug fixes + the interactive chat feature end-to-end:
  - Bug A: admin-issued password reset token validates with 60-min expiry
  - Bug C: admin-verify endpoint accepts admin_verified key (and legacy verified)
  - Feature: admin reply + user reply + user-side SSE (server reachable)
  - Regression: iter320/321 endpoints still respond.
"""
from __future__ import annotations

import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://prod-verify-2.preview.emergentagent.com").rstrip("/")

ADMIN_EMAIL = "charbel911@gmail.com"
ADMIN_PASSWORD = "Anderosli123!@#"
BUYER_EMAIL = "testbuyer@bidvex.com"
BUYER_PASSWORD = "TestBuyer2026!"


# ─── Fixtures ────────────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def session():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _login(session, email, password):
    r = session.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": password}, timeout=20)
    if r.status_code != 200:
        pytest.skip(f"Login failed for {email}: {r.status_code} {r.text[:200]}")
    data = r.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip(f"No token in login response for {email}: {data}")
    return token, data.get("user") or data.get("user_data") or {}


@pytest.fixture(scope="module")
def admin_auth(session):
    token, user = _login(session, ADMIN_EMAIL, ADMIN_PASSWORD)
    return {"token": token, "user": user, "headers": {"Authorization": f"Bearer {token}"}}


@pytest.fixture(scope="module")
def buyer_auth(session):
    token, user = _login(session, BUYER_EMAIL, BUYER_PASSWORD)
    return {"token": token, "user": user, "headers": {"Authorization": f"Bearer {token}"}}


# ─── Bug A — Admin password reset token has 60-min expiry & validates ────


class TestBugA_AdminPasswordReset:
    def test_admin_issued_token_validates(self, session, admin_auth, buyer_auth):
        """Bug A — admin reset endpoint stores token in DB with 1-hour TTL.
        We verify by reading the latest token row from MongoDB and confirming
        (a) expires_at is ~60min in the future, (b) used=False, (c) the
        public verify-reset-token endpoint reports valid=True.
        """
        import asyncio
        import sys
        from datetime import datetime, timezone
        from pathlib import Path
        BACKEND_ROOT = Path("/app/backend")
        if str(BACKEND_ROOT) not in sys.path:
            sys.path.insert(0, str(BACKEND_ROOT))

        # Resolve buyer_id via admin user listing
        r = session.get(f"{BASE_URL}/api/admin/users?search=testbuyer", headers=admin_auth["headers"], timeout=20)
        assert r.status_code == 200, f"List users failed: {r.status_code} {r.text[:200]}"
        body = r.json()
        users = body if isinstance(body, list) else body.get("users", [])
        buyer = next((u for u in users if u.get("email") == BUYER_EMAIL), None)
        assert buyer, "Test buyer not found"
        buyer_id = buyer.get("id") or buyer.get("_id")

        before = datetime.now(timezone.utc)

        # Trigger admin-issued password reset
        r = session.post(
            f"{BASE_URL}/api/admin/users/{buyer_id}/reset-password",
            headers=admin_auth["headers"],
            timeout=30,
        )
        assert r.status_code in (200, 201), f"Admin reset failed: {r.status_code} {r.text[:300]}"

        # Read latest token from MongoDB
        from motor.motor_asyncio import AsyncIOMotorClient
        # Load backend .env to get the actual MONGO_URL/DB_NAME
        env_path = Path("/app/backend/.env")
        env = {}
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    env[k.strip()] = v.strip()
        mongo_url = env.get("MONGO_URL") or os.environ.get("MONGO_URL")
        db_name = env.get("DB_NAME") or os.environ.get("DB_NAME")
        assert mongo_url and db_name, "MONGO_URL/DB_NAME not resolvable"

        async def fetch_token():
            client = AsyncIOMotorClient(mongo_url)
            try:
                coll = client[db_name]["password_reset_tokens"]
                doc = await coll.find_one(
                    {"user_id": buyer_id},
                    sort=[("created_at", -1)],
                )
                if not doc:
                    # Try by email
                    doc = await coll.find_one(
                        {"email": BUYER_EMAIL},
                        sort=[("created_at", -1)],
                    )
                return doc
            finally:
                client.close()

        doc = asyncio.run(fetch_token())
        assert doc, "No password_reset_tokens row found in DB after admin reset"

        # Verify expires_at ~ now + 60min
        exp = doc.get("expires_at")
        assert exp, f"No expires_at on token row: {doc}"
        if isinstance(exp, str):
            exp = datetime.fromisoformat(exp.replace("Z", "+00:00"))
        if exp.tzinfo is None:
            exp = exp.replace(tzinfo=timezone.utc)
        delta_min = (exp - before).total_seconds() / 60
        assert 55 <= delta_min <= 65, f"expires_at delta={delta_min:.1f}min, expected ~60 (Bug A regression)"
        assert doc.get("used") is False, f"Token 'used' field should be False, got {doc.get('used')}"

        # Verify the public endpoint reports valid=True
        token = doc.get("token") or doc.get("_id")
        r2 = session.get(f"{BASE_URL}/api/auth/verify-reset-token/{token}", timeout=20)
        assert r2.status_code == 200, f"verify-reset-token: {r2.status_code} {r2.text[:300]}"
        v = r2.json()
        assert v.get("valid") is True, f"Token marked INVALID (Bug A regression): {v}"
        # Also verify expires_in_minutes ~ 60 if present
        exp_min = v.get("expires_in_minutes")
        if exp_min is not None:
            assert 50 <= exp_min <= 65, f"verify endpoint expires_in_minutes={exp_min} (expected ~60)"


# ─── Bug C — Admin verify accepts admin_verified key (and legacy `verified`) ─


class TestBugC_AdminVerify:
    def _get_buyer_id(self, session, admin_auth):
        r = session.get(f"{BASE_URL}/api/admin/users?search=testbuyer", headers=admin_auth["headers"], timeout=20)
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        body = r.json()
        users = body if isinstance(body, list) else body.get("users", [])
        buyer = next((u for u in users if u.get("email") == BUYER_EMAIL), None)
        assert buyer, "buyer not found"
        return buyer.get("id") or buyer.get("_id"), buyer

    def test_admin_verified_key_toggles_user(self, session, admin_auth):
        buyer_id, _ = self._get_buyer_id(session, admin_auth)

        # Set admin_verified = True
        r = session.put(
            f"{BASE_URL}/api/admin/users/{buyer_id}/admin-verify",
            headers=admin_auth["headers"],
            json={"admin_verified": True},
            timeout=20,
        )
        assert r.status_code in (200, 204), f"admin-verify failed: {r.status_code} {r.text[:300]}"

        # GET — confirm flip
        _, buyer = self._get_buyer_id(session, admin_auth)
        assert buyer.get("admin_verified") is True, f"admin_verified not set: {buyer.get('admin_verified')}"
        assert buyer.get("admin_verified_by"), "admin_verified_by not set"
        assert buyer.get("admin_verified_at"), "admin_verified_at not set"

        # Now reverse it
        r2 = session.put(
            f"{BASE_URL}/api/admin/users/{buyer_id}/admin-verify",
            headers=admin_auth["headers"],
            json={"admin_verified": False},
            timeout=20,
        )
        assert r2.status_code in (200, 204), f"admin-verify revoke failed: {r2.status_code} {r2.text[:200]}"
        _, buyer2 = self._get_buyer_id(session, admin_auth)
        assert buyer2.get("admin_verified") is False

    def test_legacy_verified_key_still_works(self, session, admin_auth):
        buyer_id, _ = self._get_buyer_id(session, admin_auth)
        r = session.put(
            f"{BASE_URL}/api/admin/users/{buyer_id}/admin-verify",
            headers=admin_auth["headers"],
            json={"verified": True},
            timeout=20,
        )
        assert r.status_code in (200, 204), f"legacy key failed: {r.status_code} {r.text[:200]}"
        _, buyer = self._get_buyer_id(session, admin_auth)
        assert buyer.get("admin_verified") is True, "Legacy verified key did not toggle admin_verified"
        # Reset for cleanliness
        session.put(
            f"{BASE_URL}/api/admin/users/{buyer_id}/admin-verify",
            headers=admin_auth["headers"],
            json={"admin_verified": False},
            timeout=20,
        )


# ─── Interactive chat — full reply flow ──────────────────────────────────


@pytest.fixture(scope="module")
def created_ticket(session, buyer_auth):
    """Create a fresh escalation owned by testbuyer."""
    payload = {
        "problem": f"TEST_iter322_integration_{uuid.uuid4().hex[:8]}",
        "category": "general",
    }
    r = session.post(
        f"{BASE_URL}/api/support/escalate",
        headers=buyer_auth["headers"],
        json=payload,
        timeout=20,
    )
    assert r.status_code in (200, 201), f"escalate failed: {r.status_code} {r.text[:300]}"
    body = r.json()
    tid = body.get("ticket_id") or body.get("id") or (body.get("ticket") or {}).get("id")
    assert tid, f"No ticket id: {body}"
    return tid


class TestInteractiveChat:
    def test_admin_reply_appends_message(self, session, admin_auth, created_ticket):
        msg = f"Hello from admin TEST_{uuid.uuid4().hex[:6]}"
        r = session.post(
            f"{BASE_URL}/api/admin/support/escalations/{created_ticket}/reply",
            headers=admin_auth["headers"],
            json={"message": msg},
            timeout=20,
        )
        assert r.status_code == 200, f"admin reply failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("ok") is True
        ticket = body.get("ticket") or {}
        transcript = ticket.get("transcript") or []
        assert any(m.get("role") == "admin" and msg in (m.get("content") or "") for m in transcript), \
            f"Admin message missing from transcript: {transcript}"
        # status should auto-promote to acknowledged
        assert ticket.get("status") in ("acknowledged", "open"), f"Unexpected status: {ticket.get('status')}"
        assert ticket.get("has_unread_admin_reply") is True
        assert ticket.get("last_admin_reply_at")

    def test_admin_reply_validates_empty_message(self, session, admin_auth, created_ticket):
        r = session.post(
            f"{BASE_URL}/api/admin/support/escalations/{created_ticket}/reply",
            headers=admin_auth["headers"],
            json={"message": ""},
            timeout=20,
        )
        assert r.status_code in (400, 422), f"Expected 400/422 for empty msg, got {r.status_code}"

    def test_admin_reply_validates_too_long(self, session, admin_auth, created_ticket):
        r = session.post(
            f"{BASE_URL}/api/admin/support/escalations/{created_ticket}/reply",
            headers=admin_auth["headers"],
            json={"message": "x" * 2501},
            timeout=20,
        )
        assert r.status_code in (400, 422), f"Expected 400/422 for too-long msg, got {r.status_code}"

    def test_admin_reply_unknown_ticket_returns_404(self, session, admin_auth):
        r = session.post(
            f"{BASE_URL}/api/admin/support/escalations/nonexistent-{uuid.uuid4().hex}/reply",
            headers=admin_auth["headers"],
            json={"message": "hi"},
            timeout=20,
        )
        assert r.status_code == 404, f"Expected 404, got {r.status_code} {r.text[:200]}"

    def test_user_reply_appends_message(self, session, buyer_auth, created_ticket):
        msg = f"User reply TEST_{uuid.uuid4().hex[:6]}"
        r = session.post(
            f"{BASE_URL}/api/support/escalations/{created_ticket}/reply",
            headers=buyer_auth["headers"],
            json={"message": msg},
            timeout=20,
        )
        assert r.status_code == 200, f"user reply failed: {r.status_code} {r.text[:300]}"
        body = r.json()
        assert body.get("ok") is True
        transcript = (body.get("ticket") or {}).get("transcript") or []
        assert any(m.get("role") == "user" and msg in (m.get("content") or "") for m in transcript)

    def test_user_reply_forbidden_for_non_owner(self, session, admin_auth, created_ticket):
        # Admin token trying to use the USER reply endpoint on a non-owned ticket → 403
        r = session.post(
            f"{BASE_URL}/api/support/escalations/{created_ticket}/reply",
            headers=admin_auth["headers"],
            json={"message": "hi"},
            timeout=20,
        )
        assert r.status_code == 403, f"Expected 403, got {r.status_code} {r.text[:200]}"


# ─── SSE stream endpoints reachable ──────────────────────────────────────


class TestSSEStreams:
    def test_user_stream_requires_auth(self, session):
        r = session.get(f"{BASE_URL}/api/support/escalations/user/stream", timeout=10, stream=True)
        assert r.status_code in (401, 403), f"Unauth stream should be 401/403, got {r.status_code}"

    def test_user_stream_with_token_query_param_opens(self, session, buyer_auth):
        # Open SSE with token in query param; consume first event then close.
        url = f"{BASE_URL}/api/support/escalations/user/stream?token={buyer_auth['token']}"
        with session.get(url, timeout=10, stream=True) as r:
            assert r.status_code == 200, f"User stream returned {r.status_code}"
            # Read up to a few KB to capture the `event: ready` packet
            chunks = b""
            start = time.time()
            for chunk in r.iter_content(chunk_size=128):
                chunks += chunk
                if b"event: ready" in chunks or time.time() - start > 5:
                    break
            assert b"event: ready" in chunks, f"No ready event in: {chunks[:400]!r}"

    def test_admin_stream_with_token_opens(self, session, admin_auth):
        url = f"{BASE_URL}/api/admin/support/escalations/realtime/stream?token={admin_auth['token']}"
        with session.get(url, timeout=10, stream=True) as r:
            assert r.status_code == 200, f"Admin stream returned {r.status_code}"
            chunks = b""
            start = time.time()
            for chunk in r.iter_content(chunk_size=128):
                chunks += chunk
                if b"event: ready" in chunks or time.time() - start > 5:
                    break
            assert b"event: ready" in chunks, f"No ready event: {chunks[:400]!r}"


# ─── Regression — iter320/321 endpoints still work ───────────────────────


class TestRegression:
    def test_post_escalate_still_works(self, session, buyer_auth):
        r = session.post(
            f"{BASE_URL}/api/support/escalate",
            headers=buyer_auth["headers"],
            json={"problem": "TEST_regression_iter320", "category": "general"},
            timeout=20,
        )
        assert r.status_code in (200, 201), f"{r.status_code} {r.text[:200]}"

    def test_admin_list_escalations(self, session, admin_auth):
        r = session.get(
            f"{BASE_URL}/api/admin/support/escalations",
            headers=admin_auth["headers"],
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"

    def test_admin_pending_count(self, session, admin_auth):
        r = session.get(
            f"{BASE_URL}/api/admin/support/escalations/pending/count",
            headers=admin_auth["headers"],
            timeout=20,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text[:200]}"
        body = r.json()
        assert any(k in body for k in ("count", "pending", "open_count")), f"No count key in: {body}"


if __name__ == "__main__":
    import sys
    sys.exit(pytest.main([__file__, "-v", "--tb=short"]))
