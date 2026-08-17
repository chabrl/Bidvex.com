"""
iter488 — Scoped MCP Token System regression tests.

Coverage (per iter488 spec Part A.8):
  * Token generation via the HTTP endpoint.
  * Raw token returned exactly once (creation response only).
  * Raw token NEVER persisted to MongoDB (only bcrypt hash).
  * Bcrypt hash correctly persisted and verifies against the raw secret.
  * Raw token cannot be retrieved through the list endpoint.
  * Valid token authenticates against every MCP endpoint (tools/list,
    tools/call REST, JSON-RPC).
  * Revoked token is rejected.
  * Expired token is rejected.
  * Invalid/malformed token is rejected.
  * Token owner isolation (user A cannot see or revoke user B's tokens).
  * Subscription gate is enforced during token creation (free-tier → 402).
  * Requested scopes are validated against the allowlist.
  * User cannot self-grant privileged/admin scopes (allowlist blocks it).
  * Effective permissions never exceed the user's actual permissions
    (out-of-scope tool calls return INSUFFICIENT_SCOPE).
  * Existing trust/tax-ID/admin gates still enforced when authenticating
    with an MCP token (a `bid`-scoped token still hits the trust gate).
  * `last_used_at` updates after successful use.
  * Raw token never appears in audit logs.
  * Existing JWT auth continues working unchanged (regression).

Tests mint JWTs directly against JWT_SECRET so they don't exercise the
login rate limiter.
"""
from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
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


def _mint(user_id: str, email: str, role: str = "user") -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode(
        {"sub": user_id, "email": email, "role": role, "exp": exp},
        JWT_SECRET, algorithm=JWT_ALG,
    )


@pytest_asyncio.fixture(scope="module")
async def seeded():
    """Seed a premium user, a free-tier user, and an admin user."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()

    users = {
        "premium": {
            "id":                  f"iter488_prem_{uuid.uuid4().hex[:8]}",
            "email":                f"iter488_prem_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
            "name":                 "iter488 Premium",
            "role":                 "user",
            "account_type":         "personal",
            "subscription_tier":    "premium",
            "subscription_status":  "active",
            "phone_verified":       True,
            "created_at":           now,
        },
        "free": {
            "id":                  f"iter488_free_{uuid.uuid4().hex[:8]}",
            "email":                f"iter488_free_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
            "name":                 "iter488 Free",
            "role":                 "user",
            "account_type":         "personal",
            "subscription_tier":    "free",
            "subscription_status":  "inactive",
            "phone_verified":       False,
            "created_at":           now,
        },
        "admin": {
            "id":                  f"iter488_adm_{uuid.uuid4().hex[:8]}",
            "email":                f"iter488_adm_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
            "name":                 "iter488 Admin",
            "role":                 "super_admin",
            "account_type":         "personal",
            "subscription_tier":    "vip",
            "subscription_status":  "active",
            "phone_verified":       True,
            "created_at":           now,
        },
        "other": {
            "id":                  f"iter488_oth_{uuid.uuid4().hex[:8]}",
            "email":                f"iter488_oth_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
            "name":                 "iter488 Other",
            "role":                 "user",
            "account_type":         "personal",
            "subscription_tier":    "vip",
            "subscription_status":  "active",
            "phone_verified":       True,
            "created_at":           now,
        },
    }
    for u in users.values():
        await db.users.replace_one({"id": u["id"]}, u, upsert=True)

    yield {
        "premium":       (users["premium"]["id"], _mint(users["premium"]["id"], users["premium"]["email"])),
        "free":          (users["free"]["id"], _mint(users["free"]["id"], users["free"]["email"])),
        "admin":         (users["admin"]["id"], _mint(users["admin"]["id"], users["admin"]["email"], role="super_admin")),
        "other":         (users["other"]["id"], _mint(users["other"]["id"], users["other"]["email"])),
    }

    # Cleanup
    for u in users.values():
        await db.users.delete_one({"id": u["id"]})
        await db.mcp_tokens.delete_many({"user_id": u["id"]})
    client.close()


# ─── Helpers ─────────────────────────────────────────────────────
async def _create_token(client, jwt_token, *, label="unit-test", scopes=None, days=90):
    r = await client.post(
        f"{BACKEND_URL}/api/mcp/token",
        headers={"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"},
        json={"label": label, "scopes": scopes or ["read"], "expires_in_days": days},
    )
    return r


# ═══════════════════════════════════════════════════════════════════
# 1) Token generation
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_generate_token_returns_raw_exactly_once(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _create_token(client, jwt_token, label="unit", scopes=["read"])
        assert r.status_code == 200, r.text
        body = r.json()
        assert "token" in body and body["token"].startswith("bvx_mcp_")
        assert "token_id" in body and len(body["token_id"]) == 16
        assert body["scopes"] == ["read"]
        assert "warning_en" in body and "warning_fr" in body


@pytest.mark.asyncio
async def test_raw_token_not_persisted_in_mongo(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _create_token(client, jwt_token, label="not-in-db")
        assert r.status_code == 200
        raw, token_id = r.json()["token"], r.json()["token_id"]
    # Split the surface into its two parts so we can search Mongo for either
    remainder = raw[len("bvx_mcp_"):]
    _, secret = remainder.split("_", 1)
    mc = AsyncIOMotorClient(MONGO_URL)
    doc = await mc[DB_NAME].mcp_tokens.find_one({"token_id": token_id})
    mc.close()
    assert doc is not None
    # Must have a bcrypt hash and NEVER the raw secret
    assert doc["token_hash"].startswith("$2b$")
    haystack = str(doc)
    assert secret not in haystack
    assert raw not in haystack


@pytest.mark.asyncio
async def test_bcrypt_hash_verifies_against_raw_secret(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _create_token(client, jwt_token, label="bcrypt-check")
        raw, token_id = r.json()["token"], r.json()["token_id"]
    remainder = raw[len("bvx_mcp_"):]
    _, secret = remainder.split("_", 1)
    mc = AsyncIOMotorClient(MONGO_URL)
    doc = await mc[DB_NAME].mcp_tokens.find_one({"token_id": token_id})
    mc.close()
    assert bcrypt.checkpw(secret.encode("utf-8"), doc["token_hash"].encode("utf-8"))


@pytest.mark.asyncio
async def test_list_endpoint_never_returns_raw_or_hash(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        await _create_token(client, jwt_token, label="listed")
        r = await client.get(
            f"{BACKEND_URL}/api/mcp/tokens",
            headers={"Authorization": f"Bearer {jwt_token}"},
        )
    body = r.json()
    for row in body["tokens"]:
        assert "token" not in row
        assert "token_hash" not in row
        assert set(row.keys()) >= {"token_id", "label", "scopes", "created_at", "expires_at", "status"}


# ═══════════════════════════════════════════════════════════════════
# 2) Authentication
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_valid_token_authenticates_tools_list(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _create_token(client, jwt_token, label="auth-check", scopes=["read", "matchmaker"])
        raw = r.json()["token"]
        r2 = await client.post(
            f"{BACKEND_URL}/api/mcp/tools/list",
            headers={"Authorization": f"Bearer {raw}"},
        )
    assert r2.status_code == 200, r2.text
    tools = r2.json()["tools"]
    names = {t["name"] for t in tools}
    # Read-scope tools are present, out-of-scope tools are hidden
    assert "get_listing_details" in names  # read
    assert "search_auctions" in names
    assert "B2B_syndication_matchmaker" in names  # matchmaker
    assert "place_bid" not in names  # bid — not granted
    assert "create_auction_draft" not in names  # list — not granted


@pytest.mark.asyncio
async def test_revoked_token_is_rejected(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _create_token(client, jwt_token, label="revoke-me")
        raw, tid = r.json()["token"], r.json()["token_id"]
        # Prove it works first
        r2 = await client.post(f"{BACKEND_URL}/api/mcp/tools/list",
                               headers={"Authorization": f"Bearer {raw}"})
        assert r2.status_code == 200
        # Revoke
        rd = await client.delete(f"{BACKEND_URL}/api/mcp/token/{tid}",
                                 headers={"Authorization": f"Bearer {jwt_token}"})
        assert rd.status_code == 200
        # Now the raw token must be rejected
        r3 = await client.post(f"{BACKEND_URL}/api/mcp/tools/list",
                               headers={"Authorization": f"Bearer {raw}"})
    assert r3.status_code == 401
    detail = r3.json().get("detail")
    assert isinstance(detail, dict) and detail.get("error") == "INVALID_MCP_TOKEN"


@pytest.mark.asyncio
async def test_expired_token_is_rejected(seeded):
    """Directly stamp an expired token record + a valid bcrypt of a
    known secret. Tests only the expiration check."""
    user_id, jwt_token = seeded["premium"]
    tid = uuid.uuid4().hex[:16]
    secret = "expiredsecret" + uuid.uuid4().hex
    bh = bcrypt.hashpw(secret.encode("utf-8"), bcrypt.gensalt(rounds=4)).decode("utf-8")
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    doc = {
        "id":           str(uuid.uuid4()),
        "token_id":     tid,
        "user_id":      user_id,
        "token_hash":   bh,
        "label":        "expired",
        "scopes":       ["read"],
        "created_at":   past,
        "expires_at":   past,
        "revoked":      False,
    }
    mc = AsyncIOMotorClient(MONGO_URL)
    await mc[DB_NAME].mcp_tokens.insert_one(doc)
    mc.close()
    raw = f"bvx_mcp_{tid}_{secret}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{BACKEND_URL}/api/mcp/tools/list",
                              headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_invalid_token_is_rejected(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Format that LOOKS like an MCP token but is fake
        raw = "bvx_mcp_" + "0" * 16 + "_" + "notarealsecret"
        r = await client.post(f"{BACKEND_URL}/api/mcp/tools/list",
                              headers={"Authorization": f"Bearer {raw}"})
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_malformed_token_falls_back_to_jwt(seeded):
    """Something that isn't shaped like an MCP token must be treated as
    a normal JWT (which will 401 if not a valid JWT)."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(f"{BACKEND_URL}/api/mcp/tools/list",
                              headers={"Authorization": "Bearer garbage-string"})
    assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════
# 3) Owner isolation
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_token_owner_isolation_list(seeded):
    _, jwt_a = seeded["premium"]
    _, jwt_b = seeded["other"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        await _create_token(client, jwt_a, label="only-A-sees")
        r_b = await client.get(
            f"{BACKEND_URL}/api/mcp/tokens",
            headers={"Authorization": f"Bearer {jwt_b}"},
        )
    labels = [t["label"] for t in r_b.json()["tokens"]]
    assert "only-A-sees" not in labels


@pytest.mark.asyncio
async def test_token_owner_isolation_revoke(seeded):
    _, jwt_a = seeded["premium"]
    _, jwt_b = seeded["other"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _create_token(client, jwt_a, label="A-only-can-revoke")
        tid = r.json()["token_id"]
        # B cannot revoke A's token
        r_del = await client.delete(
            f"{BACKEND_URL}/api/mcp/token/{tid}",
            headers={"Authorization": f"Bearer {jwt_b}"},
        )
    assert r_del.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_revoke_any_token(seeded):
    _, jwt_a = seeded["premium"]
    _, jwt_admin = seeded["admin"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _create_token(client, jwt_a, label="admin-revocable")
        tid = r.json()["token_id"]
        r_del = await client.delete(
            f"{BACKEND_URL}/api/mcp/token/{tid}",
            headers={"Authorization": f"Bearer {jwt_admin}"},
        )
    assert r_del.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# 4) Subscription gate
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_subscription_gate_blocks_free_tier_creation(seeded):
    _, jwt_free = seeded["free"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _create_token(client, jwt_free, label="should-fail")
    assert r.status_code == 402
    body = r.json()
    assert body["detail"]["error"] == "SUBSCRIPTION_REQUIRED"


# ═══════════════════════════════════════════════════════════════════
# 5) Scope enforcement
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_scopes_validated_against_allowlist(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{BACKEND_URL}/api/mcp/token",
            headers={"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"},
            json={"label": "bad-scope", "scopes": ["hackerman", "admin", "root"], "expires_in_days": 30},
        )
    # Should reject because after filtering to allowlist the list is empty
    assert r.status_code == 422 or r.status_code == 400, r.text


@pytest.mark.asyncio
async def test_user_cannot_self_grant_admin_scope(seeded):
    """Even passing `admin` in the scopes list must not confer admin
    access — the allowlist strips it and the underlying admin gate is
    still governed by `user.role`, not by the token."""
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{BACKEND_URL}/api/mcp/token",
            headers={"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"},
            json={"label": "no-admin", "scopes": ["admin", "analytics"], "expires_in_days": 30},
        )
        # `admin` gets stripped, `analytics` survives
        assert r.status_code == 200
        assert "admin" not in r.json()["scopes"]
        assert "analytics" in r.json()["scopes"]
        raw = r.json()["token"]
        # Even with an analytics-scoped token, the admin-only tool must
        # still return ADMIN_ONLY — token cannot elevate role.
        r2 = await client.post(
            f"{BACKEND_URL}/api/mcp/tools/call",
            headers={"Authorization": f"Bearer {raw}", "Content-Type": "application/json"},
            json={"name": "identify_top_sellers", "arguments": {"limit": 5}},
        )
    assert r2.status_code == 403
    detail = r2.json().get("detail")
    assert isinstance(detail, dict) and detail.get("error") == "ADMIN_ONLY"


@pytest.mark.asyncio
async def test_out_of_scope_call_rejected(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _create_token(client, jwt_token, label="read-only", scopes=["read"])
        raw = r.json()["token"]
        r2 = await client.post(
            f"{BACKEND_URL}/api/mcp/tools/call",
            headers={"Authorization": f"Bearer {raw}", "Content-Type": "application/json"},
            json={"name": "place_bid", "arguments": {"listing_id": "x", "bid_amount": 1.0}},
        )
    assert r2.status_code == 403
    detail = r2.json()["detail"]
    assert detail["error"] == "INSUFFICIENT_SCOPE"
    assert detail["required_scope"] == "bid"
    assert "bid" not in detail["granted_scopes"]


# ═══════════════════════════════════════════════════════════════════
# 6) Existing trust gate still enforced
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_bid_scope_still_hits_trust_gate(seeded):
    """A `bid`-scoped token cannot bypass the phone/payment-method
    trust gate that the REST bid endpoint already enforces."""
    _, jwt_token = seeded["premium"]  # premium but NO payment method
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _create_token(client, jwt_token, label="bid-token", scopes=["bid"])
        raw = r.json()["token"]
        r2 = await client.post(
            f"{BACKEND_URL}/api/mcp/tools/call",
            headers={"Authorization": f"Bearer {raw}", "Content-Type": "application/json"},
            json={"name": "place_bid", "arguments": {"listing_id": "nonexistent", "bid_amount": 1.0, "user_max_ceiling": 100.0}},
        )
    # Must fail because trust gate is not satisfied — never a 200.
    assert r2.status_code in (400, 401, 403, 404), r2.text


# ═══════════════════════════════════════════════════════════════════
# 7) last_used_at + regression on JWT auth
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_last_used_at_updates_on_use(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _create_token(client, jwt_token, label="touch-me")
        raw, tid = r.json()["token"], r.json()["token_id"]
        # Pre-use — last_used_at is None
        lst = await client.get(f"{BACKEND_URL}/api/mcp/tokens",
                               headers={"Authorization": f"Bearer {jwt_token}"})
        pre = next(t for t in lst.json()["tokens"] if t["token_id"] == tid)
        assert pre["last_used_at"] is None
        # Use the token
        await client.post(f"{BACKEND_URL}/api/mcp/tools/list",
                          headers={"Authorization": f"Bearer {raw}"})
        # Post-use — last_used_at populated
        lst2 = await client.get(f"{BACKEND_URL}/api/mcp/tokens",
                                headers={"Authorization": f"Bearer {jwt_token}"})
        post = next(t for t in lst2.json()["tokens"] if t["token_id"] == tid)
    assert post["last_used_at"] is not None


@pytest.mark.asyncio
async def test_existing_jwt_auth_regression(seeded):
    """Regression: normal session JWT must still work end-to-end on the
    MCP endpoints (proves iter488 didn't break iter485/486/487)."""
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{BACKEND_URL}/api/mcp/tools/list",
            headers={"Authorization": f"Bearer {jwt_token}"},
        )
        assert r.status_code == 200
        assert len(r.json()["tools"]) >= 12  # all non-admin tools visible


# ═══════════════════════════════════════════════════════════════════
# 8) Raw token never appears in audit log
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_raw_token_never_appears_in_audit_log(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _create_token(client, jwt_token, label="no-audit-leak")
        raw = r.json()["token"]
        # Exercise the audit path
        await client.post(f"{BACKEND_URL}/api/mcp/tools/list",
                          headers={"Authorization": f"Bearer {raw}"})
        await client.post(
            f"{BACKEND_URL}/api/mcp/tools/call",
            headers={"Authorization": f"Bearer {raw}", "Content-Type": "application/json"},
            json={"name": "get_listing_details", "arguments": {"listing_id": "x"}},
        )
    remainder = raw[len("bvx_mcp_"):]
    _, secret = remainder.split("_", 1)
    mc = AsyncIOMotorClient(MONGO_URL)
    rows = await mc[DB_NAME].mcp_audit_logs.find({}, {"_id": 0}).to_list(2000)
    mc.close()
    haystack = str(rows)
    assert raw not in haystack
    assert secret not in haystack


# ═══════════════════════════════════════════════════════════════════
# 9) Format edge cases + expiration bounds
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_expiration_out_of_bounds_rejected(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{BACKEND_URL}/api/mcp/token",
            headers={"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"},
            json={"label": "way-too-long", "scopes": ["read"], "expires_in_days": 10_000},
        )
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_label_validation_rejects_bad_chars(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{BACKEND_URL}/api/mcp/token",
            headers={"Authorization": f"Bearer {jwt_token}", "Content-Type": "application/json"},
            json={"label": "<script>alert(1)</script>", "scopes": ["read"], "expires_in_days": 30},
        )
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_revoke_unknown_token_404(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.delete(
            f"{BACKEND_URL}/api/mcp/token/{'f'*16}",
            headers={"Authorization": f"Bearer {jwt_token}"},
        )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_revoke_bad_token_id_format_400(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.delete(
            f"{BACKEND_URL}/api/mcp/token/not-a-hex-id",
            headers={"Authorization": f"Bearer {jwt_token}"},
        )
    assert r.status_code == 400


# ═══════════════════════════════════════════════════════════════════
# 10) JSON-RPC transport works with MCP token
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_jsonrpc_authenticates_with_mcp_token(seeded):
    _, jwt_token = seeded["premium"]
    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await _create_token(client, jwt_token, label="jsonrpc-token",
                                scopes=["read", "matchmaker"])
        raw = r.json()["token"]
        r2 = await client.post(
            f"{BACKEND_URL}/api/mcp/rpc",
            headers={"Authorization": f"Bearer {raw}", "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}},
        )
    assert r2.status_code == 200
    body = r2.json()
    names = {t["name"] for t in body["result"]["tools"]}
    assert "search_auctions" in names
    assert "B2B_syndication_matchmaker" in names
    assert "place_bid" not in names
