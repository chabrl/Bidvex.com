"""
iter489 — OAuth 2.1 authorization-server regression tests.

Coverage per iter489 spec §14.A + §14.B + §14.E:
  * Dynamic Client Registration (RFC 7591)
  * Authorization redirect (RFC 6749 §4.1)
  * PKCE S256 (RFC 7636)
  * Consent decision (approve / deny)
  * Token exchange
  * Code single-use enforcement
  * Code reuse invalidates the issued token (RFC 6749 §4.1.2)
  * Redirect-URI binding
  * PKCE verifier mismatch rejection
  * Expired code rejection
  * Invalid client rejection
  * Confidential client (client_secret) flow
  * Wrong client_secret rejection
  * Access token minted IS an iter488 scoped MCP token
  * Access token respects requested scopes
  * User cannot grant admin scope via OAuth (allowlist enforcement)
  * Subscription gate enforced at consent time
  * Revocation via /oauth/revoke
  * OAuth secrets absent from audit logs
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
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

REDIRECT = "https://claude.ai/api/mcp/auth_callback"


def _b64url_sha256(s: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(s.encode()).digest()).rstrip(b"=").decode()


def _mint_jwt(user_id: str, email: str, role: str = "user") -> str:
    return jwt.encode(
        {"sub": user_id, "email": email, "role": role,
         "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
        JWT_SECRET, algorithm=JWT_ALG,
    )


@pytest_asyncio.fixture(scope="module")
async def seeded():
    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()
    prem_id = f"iter489oauth_prem_{uuid.uuid4().hex[:8]}"
    free_id = f"iter489oauth_free_{uuid.uuid4().hex[:8]}"
    for uid, tier, status in [
        (prem_id, "premium", "active"),
        (free_id, "free", "inactive"),
    ]:
        await db.users.replace_one({"id": uid}, {
            "id": uid, "email": f"{uid}@bidvex-mcp.test",
            "name": uid, "role": "user", "account_type": "personal",
            "subscription_tier": tier, "subscription_status": status,
            "phone_verified": True, "platform_terms_accepted_at": now,
            "created_at": now,
        }, upsert=True)
    yield {
        "prem": {"id": prem_id, "jwt": _mint_jwt(prem_id, f"{prem_id}@bidvex-mcp.test")},
        "free": {"id": free_id, "jwt": _mint_jwt(free_id, f"{free_id}@bidvex-mcp.test")},
    }
    for uid in (prem_id, free_id):
        await db.users.delete_one({"id": uid})
        await db.mcp_tokens.delete_many({"user_id": uid})
    await db.mcp_oauth_clients.delete_many({"client_name": {"$regex": "^iter489"}})
    await db.mcp_oauth_codes.delete_many({"user_id": {"$in": [prem_id, free_id]}})
    mc.close()


# ────────── helpers ─────────────────────────────────────────────────
async def _register_public_client(client: httpx.AsyncClient, name: str = "iter489-t") -> str:
    r = await client.post(f"{BACKEND_URL}/api/mcp/oauth/register", json={
        "client_name": name,
        "redirect_uris": [REDIRECT],
        "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
    })
    assert r.status_code == 200, r.text
    body = r.json()
    assert "client_secret" not in body  # public client → no secret
    return body["client_id"]


async def _register_confidential(client: httpx.AsyncClient, name: str = "iter489-conf") -> tuple[str, str]:
    r = await client.post(f"{BACKEND_URL}/api/mcp/oauth/register", json={
        "client_name": name,
        "redirect_uris": [REDIRECT],
        "token_endpoint_auth_method": "client_secret_post",
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
    })
    assert r.status_code == 200
    body = r.json()
    return body["client_id"], body["client_secret"]


async def _flow_to_code(client: httpx.AsyncClient, jwt_token: str,
                       client_id: str, *, scope: str = "read matchmaker",
                       challenge: str, state: str = "st") -> str:
    r = await client.post(
        f"{BACKEND_URL}/api/mcp/oauth/authorize/decision",
        headers={"Authorization": f"Bearer {jwt_token}"},
        json={"approved": True, "client_id": client_id, "redirect_uri": REDIRECT,
              "code_challenge": challenge, "code_challenge_method": "S256",
              "scope": scope, "state": state},
    )
    assert r.status_code == 200, r.text
    from urllib.parse import urlparse, parse_qs
    q = parse_qs(urlparse(r.json()["redirect_to"]).query)
    return q["code"][0]


# ═══════════════════════════════════════════════════════════════════
# 1. Discovery
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_authorization_server_metadata_shape():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{BACKEND_URL}/.well-known/oauth-authorization-server")
    assert r.status_code == 200
    body = r.json()
    for key in ("issuer", "authorization_endpoint", "token_endpoint",
                "registration_endpoint", "revocation_endpoint",
                "response_types_supported", "grant_types_supported",
                "code_challenge_methods_supported", "scopes_supported"):
        assert key in body, f"missing {key}"
    assert "S256" in body["code_challenge_methods_supported"]
    assert "authorization_code" in body["grant_types_supported"]
    assert "code" in body["response_types_supported"]
    assert set(body["scopes_supported"]) >= {"read", "bid", "list", "promote", "analytics", "matchmaker"}


@pytest.mark.asyncio
async def test_protected_resource_metadata_shape():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{BACKEND_URL}/.well-known/oauth-protected-resource")
    assert r.status_code == 200
    body = r.json()
    assert body["resource"].endswith("/api/mcp")
    assert body["authorization_servers"]
    assert "read" in body["scopes_supported"]


# ═══════════════════════════════════════════════════════════════════
# 2. Client Registration
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_public_client_registration_no_secret(seeded):
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid = await _register_public_client(c)
        assert cid.startswith("mcp_")


@pytest.mark.asyncio
async def test_confidential_client_registration_returns_secret_once(seeded):
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid, cs = await _register_confidential(c)
        assert cs and len(cs) >= 40
        # The public metadata endpoint must never return the secret
        r = await c.get(f"{BACKEND_URL}/api/mcp/oauth/clients/{cid}")
        body = r.json()
        assert "client_secret" not in body
        assert "client_secret_hash" not in body


@pytest.mark.asyncio
async def test_client_registration_rejects_non_https_redirect(seeded):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{BACKEND_URL}/api/mcp/oauth/register", json={
            "client_name": "iter489-bad",
            "redirect_uris": ["http://evil.example/callback"],
            "token_endpoint_auth_method": "none",
        })
    assert r.status_code in (400, 422)


@pytest.mark.asyncio
async def test_client_registration_rejects_fragment_in_redirect(seeded):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{BACKEND_URL}/api/mcp/oauth/register", json={
            "client_name": "iter489-frag",
            "redirect_uris": ["https://claude.ai/cb#frag"],
            "token_endpoint_auth_method": "none",
        })
    assert r.status_code in (400, 422)


# ═══════════════════════════════════════════════════════════════════
# 3. Authorize + PKCE
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_authorize_redirects_to_consent_page(seeded):
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as c:
        cid = await _register_public_client(c)
        r = await c.get(f"{BACKEND_URL}/api/mcp/oauth/authorize", params={
            "response_type": "code", "client_id": cid, "redirect_uri": REDIRECT,
            "code_challenge": challenge, "code_challenge_method": "S256",
            "scope": "read", "state": "abc",
        })
    assert r.status_code == 302
    loc = r.headers["location"]
    assert loc.startswith("/mcp-consent")
    assert f"client_id={cid}" in loc


@pytest.mark.asyncio
async def test_authorize_rejects_unknown_client(seeded):
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as c:
        r = await c.get(f"{BACKEND_URL}/api/mcp/oauth/authorize", params={
            "response_type": "code", "client_id": "mcp_notreal",
            "redirect_uri": REDIRECT, "code_challenge": "x" * 43,
            "code_challenge_method": "S256", "scope": "read", "state": "s",
        })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_authorize_rejects_unregistered_redirect(seeded):
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as c:
        cid = await _register_public_client(c)
        r = await c.get(f"{BACKEND_URL}/api/mcp/oauth/authorize", params={
            "response_type": "code", "client_id": cid,
            "redirect_uri": "https://evil.example/hack",
            "code_challenge": "x" * 43, "code_challenge_method": "S256",
            "scope": "read", "state": "s",
        })
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_authorize_rejects_plain_code_challenge_method(seeded):
    async with httpx.AsyncClient(timeout=15.0, follow_redirects=False) as c:
        cid = await _register_public_client(c)
        r = await c.get(f"{BACKEND_URL}/api/mcp/oauth/authorize", params={
            "response_type": "code", "client_id": cid, "redirect_uri": REDIRECT,
            "code_challenge": "x" * 43, "code_challenge_method": "plain",
            "scope": "read", "state": "s",
        })
    # Should redirect to redirect_uri with error=invalid_request
    assert r.status_code == 302
    assert "error=invalid_request" in r.headers["location"]


# ═══════════════════════════════════════════════════════════════════
# 4. Consent decision + token exchange
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_consent_denied_returns_access_denied(seeded):
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid = await _register_public_client(c)
        r = await c.post(f"{BACKEND_URL}/api/mcp/oauth/authorize/decision",
                         headers={"Authorization": f"Bearer {seeded['prem']['jwt']}"},
                         json={"approved": False, "client_id": cid,
                               "redirect_uri": REDIRECT,
                               "code_challenge": challenge,
                               "code_challenge_method": "S256",
                               "scope": "read", "state": "s"})
    assert r.status_code == 200
    assert "error=access_denied" in r.json()["redirect_to"]


@pytest.mark.asyncio
async def test_consent_requires_jwt(seeded):
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid = await _register_public_client(c)
        r = await c.post(f"{BACKEND_URL}/api/mcp/oauth/authorize/decision",
                         json={"approved": True, "client_id": cid,
                               "redirect_uri": REDIRECT,
                               "code_challenge": challenge,
                               "code_challenge_method": "S256",
                               "scope": "read", "state": "s"})
    assert r.status_code in (401, 403)


@pytest.mark.asyncio
async def test_consent_enforces_subscription_gate(seeded):
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid = await _register_public_client(c)
        r = await c.post(f"{BACKEND_URL}/api/mcp/oauth/authorize/decision",
                         headers={"Authorization": f"Bearer {seeded['free']['jwt']}"},
                         json={"approved": True, "client_id": cid,
                               "redirect_uri": REDIRECT,
                               "code_challenge": challenge,
                               "code_challenge_method": "S256",
                               "scope": "read", "state": "s"})
    assert r.status_code == 402


@pytest.mark.asyncio
async def test_token_exchange_success_and_scope_binding(seeded):
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid = await _register_public_client(c)
        code = await _flow_to_code(c, seeded["prem"]["jwt"], cid,
                                    scope="read matchmaker", challenge=challenge)
        r = await c.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT, "client_id": cid,
            "code_verifier": verifier,
        })
    assert r.status_code == 200
    body = r.json()
    assert body["access_token"].startswith("bvx_mcp_")
    assert body["token_type"] == "Bearer"
    assert body["scope"] == "read matchmaker"


@pytest.mark.asyncio
async def test_token_is_iter488_scoped_token(seeded):
    """The OAuth access_token IS an iter488 scoped token — it must work
    end-to-end against the existing MCP endpoints."""
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid = await _register_public_client(c)
        code = await _flow_to_code(c, seeded["prem"]["jwt"], cid,
                                    scope="read matchmaker", challenge=challenge)
        tok = (await c.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT, "client_id": cid,
            "code_verifier": verifier,
        })).json()["access_token"]
        # Use it — every existing tool filter must apply
        r = await c.post(f"{BACKEND_URL}/api/mcp/tools/list",
                         headers={"Authorization": f"Bearer {tok}"})
    assert r.status_code == 200
    names = {t["name"] for t in r.json()["tools"]}
    assert "search_auctions" in names
    assert "B2B_syndication_matchmaker" in names
    assert "place_bid" not in names          # scope filter honoured
    assert "create_auction_draft" not in names


@pytest.mark.asyncio
async def test_code_is_single_use_and_revokes_token(seeded):
    """RFC 6749 §4.1.2 — code reuse MUST fail, and per best practice
    (RFC 6819 §5.2.1.1) SHOULD invalidate any tokens minted from that
    code."""
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid = await _register_public_client(c)
        code = await _flow_to_code(c, seeded["prem"]["jwt"], cid,
                                    challenge=challenge)
        tok = (await c.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT, "client_id": cid,
            "code_verifier": verifier,
        })).json()["access_token"]
        # Reuse the code
        r2 = await c.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT, "client_id": cid,
            "code_verifier": verifier,
        })
        # The previously issued token is now revoked
        r3 = await c.post(f"{BACKEND_URL}/api/mcp/tools/list",
                          headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 400
    assert r2.json()["detail"]["error"] == "invalid_grant"
    assert r3.status_code == 401


@pytest.mark.asyncio
async def test_pkce_verifier_mismatch_rejected(seeded):
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid = await _register_public_client(c)
        code = await _flow_to_code(c, seeded["prem"]["jwt"], cid,
                                    challenge=challenge)
        # Wrong verifier
        r = await c.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT, "client_id": cid,
            "code_verifier": "wrong-verifier-" + secrets.token_urlsafe(20),
        })
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_grant"


@pytest.mark.asyncio
async def test_expired_code_rejected(seeded):
    """Directly stamp a code with expires_at in the past and try to
    exchange it."""
    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid = await _register_public_client(c, name="iter489-expired")
        verifier = secrets.token_urlsafe(48)
        challenge = _b64url_sha256(verifier)
        code = "mcpcode_" + secrets.token_urlsafe(20)
        past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        await db.mcp_oauth_codes.insert_one({
            "id": str(uuid.uuid4()), "code": code, "client_id": cid,
            "user_id": seeded["prem"]["id"], "redirect_uri": REDIRECT,
            "code_challenge": challenge, "code_challenge_method": "S256",
            "scopes": ["read"], "created_at": past, "expires_at": past,
            "used": False,
        })
        r = await c.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT, "client_id": cid,
            "code_verifier": verifier,
        })
    mc.close()
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_grant"


@pytest.mark.asyncio
async def test_redirect_uri_binding(seeded):
    """redirect_uri at the token step MUST match the one presented at
    /authorize (RFC 6749 §4.1.3)."""
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid = await _register_public_client(c)
        code = await _flow_to_code(c, seeded["prem"]["jwt"], cid,
                                    challenge=challenge)
        r = await c.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": "https://claude.ai/other/callback",  # different
            "client_id": cid, "code_verifier": verifier,
        })
    assert r.status_code == 400
    assert r.json()["detail"]["error"] == "invalid_grant"


@pytest.mark.asyncio
async def test_confidential_client_secret_verified(seeded):
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid, cs = await _register_confidential(c)
        code = await _flow_to_code(c, seeded["prem"]["jwt"], cid,
                                    challenge=challenge)
        # Wrong secret
        r_bad = await c.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT, "client_id": cid,
            "client_secret": "wrong-secret", "code_verifier": verifier,
        })
        assert r_bad.status_code == 401
        # Right secret
        code2 = await _flow_to_code(c, seeded["prem"]["jwt"], cid,
                                     challenge=challenge, state="s2")
        r_ok = await c.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
            "grant_type": "authorization_code", "code": code2,
            "redirect_uri": REDIRECT, "client_id": cid,
            "client_secret": cs, "code_verifier": verifier,
        })
    assert r_ok.status_code == 200


@pytest.mark.asyncio
async def test_scope_allowlist_strips_unknown_and_admin(seeded):
    """Even if a client requests `admin`, the allowlist strips it. Even
    with `admin` in the token's scopes list (impossible after
    stripping), admin-only tools still return ADMIN_ONLY because the
    user's actual role is `user`."""
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid = await _register_public_client(c)
        code = await _flow_to_code(c, seeded["prem"]["jwt"], cid,
                                    scope="admin superadmin analytics",
                                    challenge=challenge)
        tok = (await c.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT, "client_id": cid,
            "code_verifier": verifier,
        })).json()
    assert tok["scope"] == "analytics"
    # And admin-only remains admin-only for the non-admin user
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{BACKEND_URL}/api/mcp/tools/call",
                         headers={"Authorization": f"Bearer {tok['access_token']}",
                                  "Content-Type": "application/json"},
                         json={"name": "identify_top_sellers", "arguments": {"limit": 3}})
    assert r.status_code == 403
    assert r.json()["detail"]["error"] == "ADMIN_ONLY"


# ═══════════════════════════════════════════════════════════════════
# 5. Revocation (RFC 7009)
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_oauth_revoke_endpoint_revokes_token(seeded):
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid = await _register_public_client(c)
        code = await _flow_to_code(c, seeded["prem"]["jwt"], cid,
                                    challenge=challenge)
        tok = (await c.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT, "client_id": cid,
            "code_verifier": verifier,
        })).json()["access_token"]
        r = await c.post(f"{BACKEND_URL}/api/mcp/oauth/revoke", data={"token": tok})
        assert r.status_code == 200
        # Now the token must be rejected
        r2 = await c.post(f"{BACKEND_URL}/api/mcp/tools/list",
                          headers={"Authorization": f"Bearer {tok}"})
    assert r2.status_code == 401


@pytest.mark.asyncio
async def test_oauth_revoke_unknown_token_returns_200(seeded):
    """RFC 7009 §2.2: the server SHOULD respond 200 even for unknown
    tokens to avoid revealing token existence."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{BACKEND_URL}/api/mcp/oauth/revoke",
                         data={"token": "bvx_mcp_" + "0" * 16 + "_unknown"})
    assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# 6. Credential leakage audit
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_no_oauth_secrets_in_audit_log(seeded):
    """After a full flow, the audit log must NOT contain:
      * client_secret
      * authorization code
      * PKCE verifier
      * access_token secret"""
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    async with httpx.AsyncClient(timeout=15.0) as c:
        cid, cs = await _register_confidential(c, name="iter489-audit")
        code = await _flow_to_code(c, seeded["prem"]["jwt"], cid,
                                    challenge=challenge)
        tok = (await c.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": REDIRECT, "client_id": cid,
            "client_secret": cs, "code_verifier": verifier,
        })).json()["access_token"]
        # Fire an audited MCP call
        await c.post(f"{BACKEND_URL}/api/mcp/tools/list",
                     headers={"Authorization": f"Bearer {tok}"})
    mc = AsyncIOMotorClient(MONGO_URL)
    audit = await mc[DB_NAME].mcp_audit_logs.find({}, {"_id": 0}).to_list(5000)
    mc.close()
    blob = str(audit)
    remainder = tok[len("bvx_mcp_"):]
    _, secret_part = remainder.split("_", 1)
    assert tok not in blob
    assert secret_part not in blob
    assert cs not in blob
    assert code not in blob
    assert verifier not in blob
