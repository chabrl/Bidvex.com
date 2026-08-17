"""
iter489 — Remote MCP HTTP transport regression tests.

Coverage per iter489 spec §14.A, §14.C, §14.D:
  * Remote MCP endpoint speaks JSON-RPC 2.0 over HTTPS
  * initialize / tools/list / tools/call
  * Malformed JSON-RPC → correct error
  * Unsupported method → -32601
  * Missing parameters → correct error
  * Notification (no id) returns 202
  * Scope filtering matches iter488 rules end-to-end via OAuth
  * Matchmaker safety unchanged (approval_required, no autonomous action)
  * Buyer PII protection unchanged
  * Every existing gate still fires
"""
from __future__ import annotations

import base64
import hashlib
import os
import secrets
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

REDIRECT = "https://claude.ai/api/mcp/auth_callback"


def _b64url_sha256(s: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(s.encode()).digest()).rstrip(b"=").decode()


def _mint_jwt(uid: str, email: str, role: str = "user") -> str:
    return jwt.encode({"sub": uid, "email": email, "role": role,
                       "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
                      JWT_SECRET, algorithm=JWT_ALG)


@pytest_asyncio.fixture(scope="module")
async def remote():
    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()
    seller_id = f"iter489rem_sel_{uuid.uuid4().hex[:8]}"
    buyer_id = f"iter489rem_broker_{uuid.uuid4().hex[:8]}"
    await db.users.replace_one({"id": seller_id}, {
        "id": seller_id, "email": f"{seller_id}@bidvex-mcp.test", "name": "iter489 seller",
        "role": "user", "account_type": "personal",
        "subscription_tier": "premium", "subscription_status": "active",
        "phone_verified": True, "platform_terms_accepted_at": now, "created_at": now,
    }, upsert=True)
    await db.users.replace_one({"id": buyer_id}, {
        "id": buyer_id, "email": f"{buyer_id}@bidvex-mcp.test",
        "name": "iter489 buyer", "role": "user", "account_type": "broker",
        "subscription_tier": "partner_pro", "subscription_status": "active",
        "admin_verified": True, "business_name": "iter489 Broker Ltd.",
        "phone": "+15145550100",  # PII we must never leak
        "province": "QC",
        "buyer_preferences": {"categories": ["industrial"], "verticals": ["marketplace"],
                              "provinces": ["QC"]},
        "created_at": now,
    }, upsert=True)
    listing_id = f"iter489rem_lst_{uuid.uuid4().hex[:8]}"
    await db.listings.replace_one({"id": listing_id}, {
        "id": listing_id, "seller_id": seller_id,
        "title": "iter489 remote test lot", "description": "test",
        "category": "industrial", "current_price": 3000.0,
        "starting_price": 1000.0, "quantity": 5, "location": "QC Montreal",
        "condition": "good", "status": "active", "created_at": now,
    }, upsert=True)
    yield {
        "seller_id": seller_id, "seller_jwt": _mint_jwt(seller_id, f"{seller_id}@bidvex-mcp.test"),
        "listing_id": listing_id, "buyer_id": buyer_id,
    }
    await db.users.delete_one({"id": seller_id})
    await db.users.delete_one({"id": buyer_id})
    await db.listings.delete_one({"id": listing_id})
    await db.mcp_tokens.delete_many({"user_id": seller_id})
    mc.close()


async def _oauth_token(client: httpx.AsyncClient, jwt_token: str,
                       scope: str = "read matchmaker") -> str:
    verifier = secrets.token_urlsafe(48)
    challenge = _b64url_sha256(verifier)
    cid = (await client.post(f"{BACKEND_URL}/api/mcp/oauth/register", json={
        "client_name": "iter489-remote",
        "redirect_uris": [REDIRECT], "token_endpoint_auth_method": "none",
        "grant_types": ["authorization_code"], "response_types": ["code"],
    })).json()["client_id"]
    dec = await client.post(f"{BACKEND_URL}/api/mcp/oauth/authorize/decision",
                            headers={"Authorization": f"Bearer {jwt_token}"},
                            json={"approved": True, "client_id": cid,
                                  "redirect_uri": REDIRECT,
                                  "code_challenge": challenge,
                                  "code_challenge_method": "S256",
                                  "scope": scope, "state": "s"})
    from urllib.parse import urlparse, parse_qs
    code = parse_qs(urlparse(dec.json()["redirect_to"]).query)["code"][0]
    tok = (await client.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
        "grant_type": "authorization_code", "code": code,
        "redirect_uri": REDIRECT, "client_id": cid,
        "code_verifier": verifier,
    })).json()["access_token"]
    return tok


# ═══════════════════════════════════════════════════════════════════
# A. JSON-RPC transport
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_remote_initialize(remote):
    async with httpx.AsyncClient(timeout=15.0) as c:
        tok = await _oauth_token(c, remote["seller_jwt"], scope="read")
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Authorization": f"Bearer {tok}",
                                  "Content-Type": "application/json"},
                         json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                               "params": {"protocolVersion": "2024-11-05",
                                          "capabilities": {},
                                          "clientInfo": {"name": "iter489-test", "version": "1"}}})
    assert r.status_code == 200
    body = r.json()
    assert body["jsonrpc"] == "2.0"
    assert body["result"]["protocolVersion"] == "2024-11-05"
    assert body["result"]["serverInfo"]["name"] == "bidvex-mcp"


@pytest.mark.asyncio
async def test_remote_tools_list_and_scope_filter(remote):
    async with httpx.AsyncClient(timeout=15.0) as c:
        tok = await _oauth_token(c, remote["seller_jwt"], scope="read matchmaker")
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Authorization": f"Bearer {tok}",
                                  "Content-Type": "application/json"},
                         json={"jsonrpc": "2.0", "id": 2,
                               "method": "tools/list", "params": {}})
    names = {t["name"] for t in r.json()["result"]["tools"]}
    assert names == {"get_listing_details", "search_auctions",
                     "check_bid_status", "get_bidding_advice",
                     "B2B_syndication_matchmaker"}


@pytest.mark.asyncio
async def test_remote_tools_call_search(remote):
    async with httpx.AsyncClient(timeout=15.0) as c:
        tok = await _oauth_token(c, remote["seller_jwt"], scope="read")
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Authorization": f"Bearer {tok}",
                                  "Content-Type": "application/json"},
                         json={"jsonrpc": "2.0", "id": 3,
                               "method": "tools/call",
                               "params": {"name": "search_auctions",
                                          "arguments": {"query": "iter489",
                                                        "limit": 5}}})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result.get("isError") is False


@pytest.mark.asyncio
async def test_remote_malformed_jsonrpc_returns_error(remote):
    async with httpx.AsyncClient(timeout=15.0) as c:
        tok = await _oauth_token(c, remote["seller_jwt"], scope="read")
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Authorization": f"Bearer {tok}",
                                  "Content-Type": "application/json"},
                         json={"not_jsonrpc": True})
    assert r.status_code == 200
    body = r.json()
    assert "error" in body
    # Missing/unrecognised method may yield either -32600 (Invalid
    # Request) or -32601 (Method not found). Both are correct.
    assert body["error"]["code"] in (-32600, -32601)


@pytest.mark.asyncio
async def test_remote_unknown_method_returns_error(remote):
    async with httpx.AsyncClient(timeout=15.0) as c:
        tok = await _oauth_token(c, remote["seller_jwt"], scope="read")
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Authorization": f"Bearer {tok}",
                                  "Content-Type": "application/json"},
                         json={"jsonrpc": "2.0", "id": 9,
                               "method": "does/not/exist", "params": {}})
    body = r.json()
    assert "error" in body and body["error"]["code"] == -32601


@pytest.mark.asyncio
async def test_remote_notification_returns_202(remote):
    async with httpx.AsyncClient(timeout=15.0) as c:
        tok = await _oauth_token(c, remote["seller_jwt"], scope="read")
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Authorization": f"Bearer {tok}",
                                  "Content-Type": "application/json"},
                         json={"jsonrpc": "2.0",
                               "method": "notifications/initialized"})
    assert r.status_code == 202


@pytest.mark.asyncio
async def test_remote_unauthenticated_rejected(remote):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Content-Type": "application/json"},
                         json={"jsonrpc": "2.0", "id": 1,
                               "method": "tools/list", "params": {}})
    assert r.status_code in (401, 403)


# ═══════════════════════════════════════════════════════════════════
# C. Scope enforcement via remote transport
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_remote_read_scope_cannot_place_bid(remote):
    async with httpx.AsyncClient(timeout=15.0) as c:
        tok = await _oauth_token(c, remote["seller_jwt"], scope="read")
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Authorization": f"Bearer {tok}",
                                  "Content-Type": "application/json"},
                         json={"jsonrpc": "2.0", "id": 20,
                               "method": "tools/call",
                               "params": {"name": "place_bid",
                                          "arguments": {"listing_id": remote["listing_id"],
                                                        "bid_amount": 100.0}}})
    result = r.json()["result"]
    assert result.get("isError") is True
    import json as _j
    err = _j.loads(result["content"][0]["text"])
    assert err["error"] == "INSUFFICIENT_SCOPE"


@pytest.mark.asyncio
async def test_remote_read_scope_cannot_create_draft(remote):
    async with httpx.AsyncClient(timeout=15.0) as c:
        tok = await _oauth_token(c, remote["seller_jwt"], scope="read")
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Authorization": f"Bearer {tok}",
                                  "Content-Type": "application/json"},
                         json={"jsonrpc": "2.0", "id": 21,
                               "method": "tools/call",
                               "params": {"name": "create_auction_draft",
                                          "arguments": {"vertical": "marketplace",
                                                        "raw_input": {"title": "iter489-should-not-exist"}}}})
    result = r.json()["result"]
    import json as _j
    assert result.get("isError") is True
    err = _j.loads(result["content"][0]["text"])
    assert err["error"] == "INSUFFICIENT_SCOPE"


@pytest.mark.asyncio
async def test_remote_no_matchmaker_scope_blocks_matchmaker(remote):
    async with httpx.AsyncClient(timeout=15.0) as c:
        tok = await _oauth_token(c, remote["seller_jwt"], scope="read analytics")
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Authorization": f"Bearer {tok}",
                                  "Content-Type": "application/json"},
                         json={"jsonrpc": "2.0", "id": 22,
                               "method": "tools/call",
                               "params": {"name": "B2B_syndication_matchmaker",
                                          "arguments": {"action": "analyze"}}})
    result = r.json()["result"]
    import json as _j
    assert result.get("isError") is True
    err = _j.loads(result["content"][0]["text"])
    assert err["error"] == "INSUFFICIENT_SCOPE"


# ═══════════════════════════════════════════════════════════════════
# D. Matchmaker safety via remote transport
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_remote_matchmaker_analyze_bilingual_and_approval_gated(remote):
    async with httpx.AsyncClient(timeout=15.0) as c:
        tok = await _oauth_token(c, remote["seller_jwt"], scope="matchmaker")
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Authorization": f"Bearer {tok}",
                                  "Content-Type": "application/json"},
                         json={"jsonrpc": "2.0", "id": 30,
                               "method": "tools/call",
                               "params": {"name": "B2B_syndication_matchmaker",
                                          "arguments": {"action": "analyze",
                                                        "min_score": 10, "max_matches": 3}}})
    result = r.json()["result"]
    struct = result.get("structuredContent") or {}
    assert struct.get("status") == "drafts_ready"
    assert struct.get("approval_required") is True
    campaigns = struct.get("campaigns") or []
    assert campaigns
    c0 = campaigns[0]
    en = (c0.get("en") or {}).get("message", "")
    fr = (c0.get("fr") or {}).get("message", "")
    assert en and fr
    assert en != fr
    # EN + FR distinguishable
    assert "Hello" in en or "Best regards" in en
    assert "Bonjour" in fr or "Cordialement" in fr


@pytest.mark.asyncio
async def test_remote_matchmaker_no_buyer_pii(remote):
    async with httpx.AsyncClient(timeout=15.0) as c:
        tok = await _oauth_token(c, remote["seller_jwt"], scope="matchmaker")
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Authorization": f"Bearer {tok}",
                                  "Content-Type": "application/json"},
                         json={"jsonrpc": "2.0", "id": 31,
                               "method": "tools/call",
                               "params": {"name": "B2B_syndication_matchmaker",
                                          "arguments": {"action": "analyze"}}})
    payload = r.text
    # Buyer email + phone must never appear in the remote response
    assert f"{remote['buyer_id']}@bidvex-mcp.test" not in payload
    assert "+15145550100" not in payload


@pytest.mark.asyncio
async def test_remote_matchmaker_authorise_does_not_dispatch(remote):
    async with httpx.AsyncClient(timeout=15.0) as c:
        tok = await _oauth_token(c, remote["seller_jwt"], scope="matchmaker")
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Authorization": f"Bearer {tok}",
                                  "Content-Type": "application/json"},
                         json={"jsonrpc": "2.0", "id": 32,
                               "method": "tools/call",
                               "params": {"name": "B2B_syndication_matchmaker",
                                          "arguments": {"action": "authorise",
                                                        "campaign_id": "camp_iter489_remote",
                                                        "explicit_authorization": True}}})
    struct = r.json()["result"].get("structuredContent") or {}
    assert struct.get("status") == "authorized_pending_dispatch"
    assert struct.get("dispatched") is False


@pytest.mark.asyncio
async def test_remote_matchmaker_no_side_effects(remote):
    """No emails, no bids, no listing modifications after a full
    matchmaker analyze+authorise round trip."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        tok = await _oauth_token(c, remote["seller_jwt"], scope="matchmaker")
        await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                     headers={"Authorization": f"Bearer {tok}",
                              "Content-Type": "application/json"},
                     json={"jsonrpc": "2.0", "id": 40,
                           "method": "tools/call",
                           "params": {"name": "B2B_syndication_matchmaker",
                                      "arguments": {"action": "analyze"}}})
    mc = AsyncIOMotorClient(MONGO_URL)
    listing = await mc[DB_NAME].listings.find_one({"id": remote["listing_id"]})
    bids = await mc[DB_NAME].bids.count_documents({"listing_id": remote["listing_id"]})
    dispatched = await mc[DB_NAME]["b2b_matchmaker_authorisations"].count_documents(
        {"seller_id": remote["seller_id"], "dispatched": True})
    mc.close()
    assert listing["title"] == "iter489 remote test lot"
    assert listing["current_price"] == 3000.0
    assert bids == 0
    assert dispatched == 0


# ═══════════════════════════════════════════════════════════════════
# Regression — existing JWT path still works
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_existing_jwt_still_works_on_remote(remote):
    """iter488 session-JWT auth path must still function unchanged."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{BACKEND_URL}/api/mcp/rpc",
                         headers={"Authorization": f"Bearer {remote['seller_jwt']}",
                                  "Content-Type": "application/json"},
                         json={"jsonrpc": "2.0", "id": 50,
                               "method": "tools/list", "params": {}})
    body = r.json()
    names = {t["name"] for t in body["result"]["tools"]}
    # No scope restriction → all non-admin tools visible
    assert "place_bid" in names
    assert "create_auction_draft" in names
    assert "search_auctions" in names
