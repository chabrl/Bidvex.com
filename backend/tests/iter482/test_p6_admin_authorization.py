"""
iter482 P6 — Admin Payment Reconciliation route authorization tests.

Validates the admin-only gate via real HTTP against the running backend:
  • unauthenticated  → 401
  • buyer role       → 403
  • seller role      → 403
  • admin role       → 200
  • super_admin role → 200

Tokens are minted directly with the backend's JWT_SECRET so the tests do
NOT hit the login endpoint (avoids rate limiting during a re-run) and
so the auth-token contract stays coupled to what the FastAPI dependency
actually validates.

Requires:
  - REACT_APP_BACKEND_URL (or falls back to localhost:8001)
  - JWT_SECRET / JWT_ALGORITHM read from backend/.env

Test users are inserted / removed inside a `p6auth_` id prefix so
re-runs are idempotent.
"""
from __future__ import annotations
import os
import pytest
import pytest_asyncio
import httpx
import jwt
import uuid
from datetime import datetime, timezone, timedelta
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv("/app/backend/.env")

BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
MONGO_URL   = os.environ["MONGO_URL"]
DB_NAME     = os.environ["DB_NAME"]
JWT_SECRET  = os.environ["JWT_SECRET"]
JWT_ALG     = os.environ.get("JWT_ALGORITHM", "HS256")

pytestmark = pytest.mark.asyncio


def _mint(user_id: str, email: str, role: str) -> str:
    """Mint the same JWT the FastAPI auth dependency validates."""
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode(
        {"sub": user_id, "email": email, "role": role, "exp": exp},
        JWT_SECRET, algorithm=JWT_ALG,
    )


@pytest_asyncio.fixture(scope="module")
async def seeded_users():
    """Create four users (admin / super_admin / seller / buyer) then
    remove them at teardown so re-runs are idempotent.
    """
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    ids = {}
    for role in ("admin", "super_admin", "seller", "buyer"):
        uid = f"p6auth_{role}_{uuid.uuid4().hex[:8]}"
        email = f"{uid}@bidvex-p6test.com"
        await db.users.insert_one({
            "id": uid,
            "email": email,
            "role": role,
            "name": f"P6 {role}",
            "is_active": True,
            "email_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        })
        ids[role] = {"id": uid, "email": email, "token": _mint(uid, email, role)}
    yield ids
    for r in ids.values():
        await db.users.delete_one({"id": r["id"]})
    client.close()


async def _get(path: str, token: str | None):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15.0) as c:
        headers = {"Authorization": f"Bearer {token}"} if token else {}
        return await c.get(path, headers=headers)


class TestAdminReconciliationAuthorization:
    async def test_unauthenticated_returns_401(self):
        r = await _get("/api/admin/stripe-reconciliation/summary", None)
        assert r.status_code == 401, r.text

    async def test_buyer_returns_403(self, seeded_users):
        r = await _get(
            "/api/admin/stripe-reconciliation/summary",
            seeded_users["buyer"]["token"],
        )
        assert r.status_code == 403, r.text

    async def test_seller_returns_403(self, seeded_users):
        r = await _get(
            "/api/admin/stripe-reconciliation/summary",
            seeded_users["seller"]["token"],
        )
        assert r.status_code == 403, r.text

    async def test_admin_returns_200(self, seeded_users):
        r = await _get(
            "/api/admin/stripe-reconciliation/summary",
            seeded_users["admin"]["token"],
        )
        assert r.status_code == 200, r.text
        body = r.json()
        # Response must carry the P6-canonical vocabulary.
        for key in ("reconciled", "variance", "shortfall", "pending", "error",
                    "estimated_cents_total", "recovery_cents_total",
                    "actual_cents_total"):
            assert key in body, f"missing key {key} in summary payload"

    async def test_super_admin_returns_200(self, seeded_users):
        r = await _get(
            "/api/admin/stripe-reconciliation",
            seeded_users["super_admin"]["token"],
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert "rows" in body and isinstance(body["rows"], list)

    async def test_list_supports_p6_status_filter(self, seeded_users):
        r = await _get(
            "/api/admin/stripe-reconciliation?status=SHORTFALL",
            seeded_users["admin"]["token"],
        )
        assert r.status_code == 200, r.text

    async def test_search_param_accepted(self, seeded_users):
        r = await _get(
            "/api/admin/stripe-reconciliation?search=pi_test_never_exists",
            seeded_users["admin"]["token"],
        )
        assert r.status_code == 200, r.text
        assert r.json().get("count") == 0
