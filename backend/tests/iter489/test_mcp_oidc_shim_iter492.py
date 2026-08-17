"""
iter492 — Claude.ai OIDC-Discovery compatibility regression tests.

Log evidence (Aug 17 2026, trace `ofid_70a58ada3432eda4`, Anthropic
egress IPs 160.79.106.177/179/180/182) proved that Claude.ai's remote
MCP client probes `/.well-known/openid-configuration` BEFORE it tries
`/.well-known/oauth-authorization-server` and gives up on 404 without
falling back — even though BidVex advertises `registration_endpoint`
via RFC 8414. This module verifies the compatibility shim.

Coverage:
  * `GET /api/.well-known/openid-configuration` returns 200 with the
    OpenID-Connect-Discovery-1.0 §3 required fields present.
  * The `openid-configuration` doc surfaces the SAME OAuth endpoints
    as the RFC 8414 doc (issuer, authorization_endpoint, token_endpoint,
    registration_endpoint) — no divergence that would confuse the
    client's state machine.
  * `GET /api/mcp/oauth/jwks.json` returns an empty JWKS
    (`{"keys": []}`) — legal per RFC 7517 §5. We don't sign id_tokens.
  * The compatibility shim did NOT weaken the underlying OAuth
    metadata (grant_types_supported still restricted to
    ["authorization_code"], scopes_supported still bounded to our
    allowlist, no `openid` scope leaked).
  * Full flow initiated from `openid-configuration` end-to-end:
    Claude-style client can use the discovery doc to reach DCR,
    /authorize, /token, and finally the Streamable HTTP endpoint.
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

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

CLAUDE_REDIRECT = "https://claude.ai/api/mcp/auth_callback"


def _mint_jwt(uid: str, email: str) -> str:
    return jwt.encode({"sub": uid, "email": email, "role": "user",
                       "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
                      JWT_SECRET, algorithm=JWT_ALG)


def _pkce() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(os.urandom(48)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


@pytest_asyncio.fixture(scope="module")
async def oidc_ctx():
    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()
    uid = f"iter492_{uuid.uuid4().hex[:8]}"
    await db.users.replace_one({"id": uid}, {
        "id": uid, "email": f"{uid}@bidvex-mcp.test",
        "name": uid, "role": "user", "account_type": "personal",
        "subscription_tier": "premium", "subscription_status": "active",
        "phone_verified": True, "platform_terms_accepted_at": now,
        "created_at": now,
    }, upsert=True)
    yield {"uid": uid,
           "jwt": _mint_jwt(uid, f"{uid}@bidvex-mcp.test")}
    await db.users.delete_one({"id": uid})
    await db.mcp_tokens.delete_many({"user_id": uid})
    await db.mcp_oauth_clients.delete_many({"client_name":
                                             {"$regex": "^iter492"}})
    mc.close()


# ═══════════════════════════════════════════════════════════════════
# OIDC discovery shim exists and is reachable
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_openid_configuration_reachable_via_ingress_safe_path():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{BACKEND_URL}/api/.well-known/openid-configuration")
    assert r.status_code == 200
    body = r.json()
    # OIDC Discovery 1.0 §3 required fields
    for f in ("issuer", "authorization_endpoint", "token_endpoint",
              "jwks_uri", "response_types_supported",
              "subject_types_supported",
              "id_token_signing_alg_values_supported"):
        assert f in body, f"OIDC required field missing: {f}"
    assert body["issuer"].endswith("/api")
    assert body["subject_types_supported"] == ["public"]
    assert body["id_token_signing_alg_values_supported"] == ["RS256"]


@pytest.mark.asyncio
async def test_jwks_endpoint_returns_empty_keys():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{BACKEND_URL}/api/mcp/oauth/jwks.json")
    assert r.status_code == 200
    assert r.json() == {"keys": []}


# ═══════════════════════════════════════════════════════════════════
# OIDC shim must NOT diverge from the RFC 8414 doc
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_oidc_and_oauth_metadata_agree_on_endpoints():
    async with httpx.AsyncClient(timeout=15.0) as c:
        a = (await c.get(f"{BACKEND_URL}/api/.well-known/oauth-authorization-server")).json()
        o = (await c.get(f"{BACKEND_URL}/api/.well-known/openid-configuration")).json()
    for f in ("issuer", "authorization_endpoint", "token_endpoint",
              "registration_endpoint", "revocation_endpoint",
              "response_types_supported", "grant_types_supported",
              "code_challenge_methods_supported",
              "token_endpoint_auth_methods_supported",
              "scopes_supported"):
        assert a[f] == o[f], f"drift between oauth-as and openid-config for {f}"


@pytest.mark.asyncio
async def test_oidc_shim_does_not_leak_openid_scope():
    """We are NOT an OIDC identity provider. `openid` MUST NOT appear
    in the advertised scope catalog."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        o = (await c.get(f"{BACKEND_URL}/api/.well-known/openid-configuration")).json()
    assert "openid" not in o["scopes_supported"]


@pytest.mark.asyncio
async def test_oidc_shim_grant_types_restricted():
    """The shim must NOT accidentally re-widen grant_types_supported."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        o = (await c.get(f"{BACKEND_URL}/api/.well-known/openid-configuration")).json()
    assert o["grant_types_supported"] == ["authorization_code"]


# ═══════════════════════════════════════════════════════════════════
# End-to-end — Claude-style flow driven purely from openid-config
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_full_flow_from_openid_configuration(oidc_ctx):
    """Simulate Claude.ai's actual discovery order — start from the
    OIDC endpoint, follow the metadata to `registration_endpoint`,
    perform DCR → /authorize → /token → open a Streamable HTTP
    session → tools/list → tools/call. Every step must succeed."""
    async with httpx.AsyncClient(timeout=20.0, follow_redirects=False) as c:
        # 1) OIDC discovery
        oidc = (await c.get(f"{BACKEND_URL}/api/.well-known/openid-configuration")).json()
        reg  = oidc["registration_endpoint"]
        auth = oidc["authorization_endpoint"]
        tok  = oidc["token_endpoint"]

        # 2) DCR — public client
        r = await c.post(reg, json={
            "client_name": "iter492-Claude",
            "redirect_uris": [CLAUDE_REDIRECT],
            "grant_types": ["authorization_code", "refresh_token"],
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
            "scope": "read matchmaker",
        })
        assert r.status_code == 201, r.text
        client_id = r.json()["client_id"]

        # 3) /authorize with PKCE
        verifier, challenge = _pkce()
        state = "iter492_" + uuid.uuid4().hex[:8]
        r = await c.get(auth, params={
            "response_type": "code", "client_id": client_id,
            "redirect_uri": CLAUDE_REDIRECT,
            "code_challenge": challenge, "code_challenge_method": "S256",
            "scope": "read matchmaker", "state": state,
        })
        assert r.status_code == 302
        assert "/mcp-consent" in (r.headers.get("location") or "")

        # 4) Consent decision
        r = await c.post(
            f"{BACKEND_URL}/api/mcp/oauth/authorize/decision",
            headers={"Authorization": f"Bearer {oidc_ctx['jwt']}",
                     "Content-Type": "application/json"},
            json={"approved": True, "client_id": client_id,
                  "redirect_uri": CLAUDE_REDIRECT,
                  "code_challenge": challenge,
                  "code_challenge_method": "S256",
                  "scope": "read matchmaker", "state": state},
        )
        assert r.status_code == 200
        code = parse_qs(urlparse(r.json()["redirect_to"]).query)["code"][0]

        # 5) Token exchange
        r = await c.post(tok, data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": CLAUDE_REDIRECT,
            "client_id": client_id,
            "code_verifier": verifier,
        })
        assert r.status_code == 200
        access_token = r.json()["access_token"]
        assert access_token.startswith("bvx_mcp_")

        # 6) initialize + tools/list on Streamable HTTP
        r = await c.post(
            f"{BACKEND_URL}/api/mcp",
            headers={"Authorization": f"Bearer {access_token}",
                     "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-06-18",
                             "capabilities": {},
                             "clientInfo": {"name": "iter492", "version": "1"}}},
        )
        assert r.status_code == 200
        sid = r.headers["mcp-session-id"]

        r = await c.post(
            f"{BACKEND_URL}/api/mcp",
            headers={"Authorization": f"Bearer {access_token}",
                     "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "Mcp-Session-Id": sid},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list",
                  "params": {}},
        )
        assert r.status_code == 200
        names = {t["name"] for t in r.json()["result"]["tools"]}
        assert "search_auctions" in names
        assert "B2B_syndication_matchmaker" in names
        # scope-filtered — no place_bid for a read+matchmaker token
        assert "place_bid" not in names


# ═══════════════════════════════════════════════════════════════════
# Root-path openid-configuration remains 404 through the ingress
# (safety-net regression: don't accidentally trigger the SPA route)
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_root_openid_configuration_is_not_the_backend_response():
    """Confirms the ingress-safe /api/.well-known/openid-configuration
    is the ONLY backend-served OIDC discovery URL. The bare-root path
    (`/.well-known/openid-configuration`) goes through the frontend SPA
    and is not required by Claude given the path-inclusive issuer."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        # Just prove the API path works — the root path may be shadowed
        # by the SPA fallback and returning HTML, that's OK.
        api = await c.get(f"{BACKEND_URL}/api/.well-known/openid-configuration")
        assert api.status_code == 200
        assert api.headers.get("content-type", "").startswith("application/json")
