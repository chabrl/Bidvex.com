"""
iter490 — Streamable HTTP transport regression tests.

Coverage:
  * Discovery reachable via /api/.well-known/* (ingress-safe path).
  * Issuer identifier uses path-inclusive form (RFC 8414 §3).
  * 401 responses carry WWW-Authenticate with resource_metadata URL.
  * initialize returns Mcp-Session-Id header.
  * Subsequent requests require Mcp-Session-Id → 400 if missing.
  * Unknown/expired session → 404 (client re-initializes).
  * DELETE terminates session; next call → 404.
  * Session cross-user check → 403.
  * GET returns 405 (spec-compliant — we don't do server-initiated SSE).
  * Protocol version negotiation.
  * The old /api/mcp/rpc endpoint continues to work unchanged.
  * Audit sanitizer still redacts secrets.
"""
from __future__ import annotations

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


def _mint_jwt(uid: str, email: str, role: str = "user") -> str:
    return jwt.encode({"sub": uid, "email": email, "role": role,
                       "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
                      JWT_SECRET, algorithm=JWT_ALG)


@pytest_asyncio.fixture(scope="module")
async def stream_ctx():
    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()
    uid = f"iter490_prem_{uuid.uuid4().hex[:8]}"
    other = f"iter490_other_{uuid.uuid4().hex[:8]}"
    for u, tier in [(uid, "premium"), (other, "vip")]:
        await db.users.replace_one({"id": u}, {
            "id": u, "email": f"{u}@bidvex-mcp.test",
            "name": u, "role": "user", "account_type": "personal",
            "subscription_tier": tier, "subscription_status": "active",
            "phone_verified": True, "platform_terms_accepted_at": now,
            "created_at": now,
        }, upsert=True)
    # Mint iter488 tokens (matchmaker scope for the extra tools)
    async with httpx.AsyncClient(timeout=15.0) as c:
        prem_jwt = _mint_jwt(uid, f"{uid}@bidvex-mcp.test")
        other_jwt = _mint_jwt(other, f"{other}@bidvex-mcp.test")
        prem_tok = (await c.post(f"{BACKEND_URL}/api/mcp/token",
                                  headers={"Authorization": f"Bearer {prem_jwt}",
                                           "Content-Type": "application/json"},
                                  json={"label": "iter490-prem",
                                        "scopes": ["read", "matchmaker"],
                                        "expires_in_days": 1})).json()["token"]
        other_tok = (await c.post(f"{BACKEND_URL}/api/mcp/token",
                                   headers={"Authorization": f"Bearer {other_jwt}",
                                            "Content-Type": "application/json"},
                                   json={"label": "iter490-other",
                                         "scopes": ["read"],
                                         "expires_in_days": 1})).json()["token"]
    yield {"prem_id": uid, "prem_jwt": prem_jwt, "prem_tok": prem_tok,
           "other_id": other, "other_jwt": other_jwt, "other_tok": other_tok}
    for u in (uid, other):
        await db.users.delete_one({"id": u})
        await db.mcp_tokens.delete_many({"user_id": u})
    await db.mcp_streamable_sessions.delete_many({"user_id": {"$in": [uid, other]}})
    mc.close()


async def _init(client, tok):
    r = await client.post(
        f"{BACKEND_URL}/api/mcp",
        headers={"Authorization": f"Bearer {tok}",
                 "Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-06-18",
                         "capabilities": {},
                         "clientInfo": {"name": "iter490-test", "version": "1"}}},
    )
    return r, r.headers.get("mcp-session-id")


# ═══════════════════════════════════════════════════════════════════
# Discovery
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_api_well_known_auth_server_reachable():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{BACKEND_URL}/api/.well-known/oauth-authorization-server")
    assert r.status_code == 200
    body = r.json()
    # RFC 8414 §3 — path-inclusive issuer so discovery URL resolves
    # through an ingress that only routes /api/*
    assert body["issuer"].endswith("/api")


@pytest.mark.asyncio
async def test_api_well_known_protected_resource_reachable():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{BACKEND_URL}/api/.well-known/oauth-protected-resource")
    assert r.status_code == 200
    body = r.json()
    assert body["resource"].endswith("/api/mcp")
    assert body["authorization_servers"]
    assert body["authorization_servers"][0].endswith("/api")


# ═══════════════════════════════════════════════════════════════════
# 401 → WWW-Authenticate
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_streamable_401_includes_www_authenticate():
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{BACKEND_URL}/api/mcp",
                         headers={"Content-Type": "application/json",
                                  "Accept": "application/json, text/event-stream"},
                         json={"jsonrpc": "2.0", "id": 1,
                               "method": "initialize"})
    assert r.status_code == 401
    wa = r.headers.get("www-authenticate") or ""
    assert "Bearer" in wa
    assert "resource_metadata=" in wa
    assert "/api/.well-known/oauth-protected-resource" in wa


# ═══════════════════════════════════════════════════════════════════
# Session lifecycle
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_initialize_issues_session_id(stream_ctx):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r, sid = await _init(c, stream_ctx["prem_tok"])
    assert r.status_code == 200
    assert sid and sid.startswith("mcp_sess_")
    body = r.json()
    assert body["result"]["protocolVersion"] == "2025-06-18"
    assert body["result"]["serverInfo"]["name"] == "bidvex-mcp"


@pytest.mark.asyncio
async def test_subsequent_request_without_session_400(stream_ctx):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r, _ = await _init(c, stream_ctx["prem_tok"])
        r2 = await c.post(
            f"{BACKEND_URL}/api/mcp",
            headers={"Authorization": f"Bearer {stream_ctx['prem_tok']}",
                     "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream"},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
    assert r2.status_code == 400
    assert r2.json()["detail"]["error"] == "missing_session"


@pytest.mark.asyncio
async def test_subsequent_request_with_session_success(stream_ctx):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r, sid = await _init(c, stream_ctx["prem_tok"])
        r2 = await c.post(
            f"{BACKEND_URL}/api/mcp",
            headers={"Authorization": f"Bearer {stream_ctx['prem_tok']}",
                     "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "Mcp-Session-Id": sid},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
    assert r2.status_code == 200
    tools = r2.json()["result"]["tools"]
    assert any(t["name"] == "search_auctions" for t in tools)


@pytest.mark.asyncio
async def test_unknown_session_returns_404(stream_ctx):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(
            f"{BACKEND_URL}/api/mcp",
            headers={"Authorization": f"Bearer {stream_ctx['prem_tok']}",
                     "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "Mcp-Session-Id": "mcp_sess_definitely_unknown_12345"},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "session_not_found"


@pytest.mark.asyncio
async def test_session_cross_user_rejected(stream_ctx):
    async with httpx.AsyncClient(timeout=15.0) as c:
        # user A creates session
        r, sid = await _init(c, stream_ctx["prem_tok"])
        # user B tries to use it
        r2 = await c.post(
            f"{BACKEND_URL}/api/mcp",
            headers={"Authorization": f"Bearer {stream_ctx['other_tok']}",
                     "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "Mcp-Session-Id": sid},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
    assert r2.status_code == 403
    assert r2.json()["detail"]["error"] == "session_mismatch"


@pytest.mark.asyncio
async def test_delete_terminates_session(stream_ctx):
    async with httpx.AsyncClient(timeout=15.0) as c:
        _, sid = await _init(c, stream_ctx["prem_tok"])
        r_del = await c.delete(
            f"{BACKEND_URL}/api/mcp",
            headers={"Authorization": f"Bearer {stream_ctx['prem_tok']}",
                     "Mcp-Session-Id": sid},
        )
        assert r_del.status_code == 204
        # Next call must 404
        r2 = await c.post(
            f"{BACKEND_URL}/api/mcp",
            headers={"Authorization": f"Bearer {stream_ctx['prem_tok']}",
                     "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "Mcp-Session-Id": sid},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
    assert r2.status_code == 404


@pytest.mark.asyncio
async def test_get_returns_405_with_allow_header(stream_ctx):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{BACKEND_URL}/api/mcp",
                        headers={"Authorization": f"Bearer {stream_ctx['prem_tok']}"})
    assert r.status_code == 405
    assert "POST" in (r.headers.get("allow") or "")


@pytest.mark.asyncio
async def test_scope_filter_end_to_end(stream_ctx):
    """read+matchmaker token: only those tools visible, place_bid
    blocked via streamable transport."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r, sid = await _init(c, stream_ctx["prem_tok"])
        r2 = await c.post(
            f"{BACKEND_URL}/api/mcp",
            headers={"Authorization": f"Bearer {stream_ctx['prem_tok']}",
                     "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "Mcp-Session-Id": sid},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        )
        names = {t["name"] for t in r2.json()["result"]["tools"]}
        assert names == {"search_auctions", "get_listing_details",
                         "check_bid_status", "get_bidding_advice",
                         "B2B_syndication_matchmaker"}
        # place_bid via streamable → INSUFFICIENT_SCOPE
        r3 = await c.post(
            f"{BACKEND_URL}/api/mcp",
            headers={"Authorization": f"Bearer {stream_ctx['prem_tok']}",
                     "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "Mcp-Session-Id": sid},
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                  "params": {"name": "place_bid",
                             "arguments": {"listing_id": "x", "bid_amount": 1}}},
        )
    import json as _j
    result = r3.json()["result"]
    assert result["isError"] is True
    err = _j.loads(result["content"][0]["text"])
    assert err["error"] == "INSUFFICIENT_SCOPE"


@pytest.mark.asyncio
async def test_session_persisted_across_pod_restart_semantic(stream_ctx):
    """Sessions live in MongoDB so preview pod restarts don't lose
    them. Simulates: create session, wipe in-memory (we can't actually
    restart backend during a test), verify the session still resolves
    from DB."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        _, sid = await _init(c, stream_ctx["prem_tok"])
    mc = AsyncIOMotorClient(MONGO_URL)
    doc = await mc[DB_NAME].mcp_streamable_sessions.find_one({"session_id": sid})
    mc.close()
    assert doc is not None
    assert doc["user_id"] == stream_ctx["prem_id"]
    assert doc.get("scopes") == ["read", "matchmaker"]


# ═══════════════════════════════════════════════════════════════════
# Backward compatibility
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_old_rpc_endpoint_still_works(stream_ctx):
    """iter485 /api/mcp/rpc must remain byte-for-byte identical for
    the Claude Desktop stdio bridge and iter489 harness."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(
            f"{BACKEND_URL}/api/mcp/rpc",
            headers={"Authorization": f"Bearer {stream_ctx['prem_tok']}",
                     "Content-Type": "application/json"},
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2024-11-05",
                             "capabilities": {}, "clientInfo": {"name": "test", "version": "1"}}},
        )
    assert r.status_code == 200
    body = r.json()
    # rpc endpoint is unchanged — no session id in headers, still returns
    # the caller-provided protocolVersion (or default)
    assert body["result"]["protocolVersion"] == "2024-11-05"
    # No Mcp-Session-Id on the old endpoint — that's intentional
    assert not r.headers.get("mcp-session-id")


@pytest.mark.asyncio
async def test_session_and_tool_call_audit_no_raw_token(stream_ctx):
    async with httpx.AsyncClient(timeout=15.0) as c:
        _, sid = await _init(c, stream_ctx["prem_tok"])
        await c.post(
            f"{BACKEND_URL}/api/mcp",
            headers={"Authorization": f"Bearer {stream_ctx['prem_tok']}",
                     "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "Mcp-Session-Id": sid},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                  "params": {"name": "search_auctions",
                             "arguments": {"query": "x", "limit": 1}}},
        )
    remainder = stream_ctx["prem_tok"][len("bvx_mcp_"):]
    _, secret = remainder.split("_", 1)
    mc = AsyncIOMotorClient(MONGO_URL)
    audit = await mc[DB_NAME].mcp_audit_logs.find({"user_id": stream_ctx["prem_id"]},
                                                    {"_id": 0}).to_list(2000)
    mc.close()
    blob = str(audit)
    assert stream_ctx["prem_tok"] not in blob
    assert secret not in blob
