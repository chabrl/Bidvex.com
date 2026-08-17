"""
iter495 — Scope enforcement + Claude write-scope diagnostic tests.

Formalises the least-privilege guarantees that Claude's connector
depends on:

  * Read-only OAuth token (scope=`read`) — the tools/list surface hides
    every write tool. `create_auction_draft` MUST NOT appear.
  * A token that includes `list` (BidVex's canonical write scope for
    listing creation) exposes `create_auction_draft` and
    `bulk_create_listings`. Confirms iter494's vertical-scoping fix is
    reachable end-to-end.
  * DCR-negotiated scopes flow through /authorize → consent → /token
    without narrowing: `scope=read list matchmaker` DCR → same scope
    on the issued token.
  * `search_auctions` is available on read-only tokens (regression
    guard for the OAuth read surface).
  * The BidVex OAuth server does NOT invent a `write` scope — the
    canonical write scopes remain `list` and `bid`.
  * All existing MCP tests (iter482, iter488, iter489, iter494) remain
    green.

Nothing in this module modifies OAuth, transport, tokens, tools, or
business logic.
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


async def _oauth_dance(client: httpx.AsyncClient, user_jwt: str, scopes: list[str]) -> tuple[str, list[str]]:
    """Full OAuth 2.1 flow: DCR → /authorize → consent → /token.
    Returns (access_token, granted_scopes_from_token_response)."""
    oidc = (await client.get(f"{BACKEND_URL}/api/.well-known/openid-configuration")).json()
    reg = await client.post(oidc["registration_endpoint"], json={
        "client_name": "iter495-flow",
        "redirect_uris": [CLAUDE_REDIRECT],
        "grant_types": ["authorization_code"],
        "response_types": ["code"],
        "token_endpoint_auth_method": "none",
        "scope": " ".join(scopes),
    })
    assert reg.status_code == 201, reg.text
    cid = reg.json()["client_id"]

    verifier, challenge = _pkce()
    state = "iter495_" + uuid.uuid4().hex[:8]
    dec = await client.post(f"{BACKEND_URL}/api/mcp/oauth/authorize/decision",
        headers={"Authorization": f"Bearer {user_jwt}",
                 "Content-Type": "application/json"},
        json={"approved": True, "client_id": cid,
              "redirect_uri": CLAUDE_REDIRECT,
              "code_challenge": challenge,
              "code_challenge_method": "S256",
              "scope": " ".join(scopes), "state": state})
    assert dec.status_code == 200, dec.text
    code = parse_qs(urlparse(dec.json()["redirect_to"]).query)["code"][0]

    tok = await client.post(oidc["token_endpoint"], data={
        "grant_type": "authorization_code",
        "code": code, "redirect_uri": CLAUDE_REDIRECT,
        "client_id": cid, "code_verifier": verifier,
    })
    assert tok.status_code == 200, tok.text
    return tok.json()["access_token"], tok.json()["scope"].split()


@pytest_asyncio.fixture(scope="module")
async def ctx():
    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]
    uid = f"iter495_{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc).isoformat()
    await db.users.replace_one({"id": uid}, {
        "id": uid, "email": f"{uid}@bidvex-iter495.test", "name": uid,
        "role": "user", "account_type": "personal",
        "subscription_tier": "premium", "subscription_status": "active",
        "phone_verified": True,
        "platform_terms_accepted_at": now,
        "created_at": now,
    }, upsert=True)
    await db.payment_methods.insert_one({
        "id": str(uuid.uuid4()), "user_id": uid,
        "brand": "visa", "last4": "4242",
        "stripe_payment_method_id": f"pm_iter495_{uid}",
        "created_at": now,
    })
    yield {"uid": uid,
           "jwt": _mint_jwt(uid, f"{uid}@bidvex-iter495.test")}
    await db.users.delete_one({"id": uid})
    await db.mcp_tokens.delete_many({"user_id": uid})
    await db.payment_methods.delete_many({"user_id": uid})
    await db.mcp_oauth_clients.delete_many({"client_name": "iter495-flow"})
    await db.listings.delete_many({"seller_id": uid})
    mc.close()


async def _open_session(client: httpx.AsyncClient, tok: str) -> str:
    r = await client.post(f"{BACKEND_URL}/api/mcp",
        headers={"Authorization": f"Bearer {tok}",
                 "Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"},
        json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
              "params": {"protocolVersion": "2025-06-18",
                         "capabilities": {},
                         "clientInfo": {"name": "iter495", "version": "1"}}})
    assert r.status_code == 200, r.text
    return r.headers["mcp-session-id"]


async def _tools_list(client: httpx.AsyncClient, tok: str, sid: str) -> list[str]:
    r = await client.post(f"{BACKEND_URL}/api/mcp",
        headers={"Authorization": f"Bearer {tok}",
                 "Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream",
                 "Mcp-Session-Id": sid},
        json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
    assert r.status_code == 200, r.text
    return [t["name"] for t in r.json()["result"]["tools"]]


# ═══════════════════════════════════════════════════════════════════
# Canonical scope catalog — BidVex uses `list`, not `write`
# ═══════════════════════════════════════════════════════════════════
def test_bidvex_scope_catalog_has_no_write_scope():
    """Regression guard: BidVex's canonical scopes are
    read/bid/list/promote/analytics/matchmaker. `write` is NOT a scope
    — the write scope for listings is `list`."""
    from routes.mcp_tokens import ALLOWED_SCOPES
    assert set(ALLOWED_SCOPES) == {"read", "bid", "list", "promote",
                                    "analytics", "matchmaker"}
    assert "write" not in ALLOWED_SCOPES


def test_create_auction_draft_requires_list_scope():
    """The tool→scope map must keep `create_auction_draft` gated by
    `list`. If this ever changes we want the test to scream."""
    from mcp_server import _TOOL_SCOPE_MAP
    assert _TOOL_SCOPE_MAP["create_auction_draft"] == "list"
    assert _TOOL_SCOPE_MAP["bulk_create_listings"] == "list"
    # Sanity: reads stay `read`, bidding stays `bid`
    assert _TOOL_SCOPE_MAP["search_auctions"] == "read"
    assert _TOOL_SCOPE_MAP["get_listing_details"] == "read"
    assert _TOOL_SCOPE_MAP["place_bid"] == "bid"


# ═══════════════════════════════════════════════════════════════════
# Scope negotiation preserves what the client requested
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dcr_preserves_all_requested_scopes(ctx):
    """Client that requests every scope (Claude's default when the
    connector is added fresh) receives ALL scopes in the token."""
    async with httpx.AsyncClient(timeout=20.0) as c:
        tok, granted = await _oauth_dance(c, ctx["jwt"],
            ["read", "bid", "list", "promote", "analytics", "matchmaker"])
    assert set(granted) == {"read", "bid", "list", "promote",
                            "analytics", "matchmaker"}


@pytest.mark.asyncio
async def test_dcr_preserves_narrower_scope(ctx):
    """Client that requests only `read matchmaker` receives exactly
    that subset — no scope expansion by the server."""
    async with httpx.AsyncClient(timeout=20.0) as c:
        tok, granted = await _oauth_dance(c, ctx["jwt"], ["read", "matchmaker"])
    assert set(granted) == {"read", "matchmaker"}


@pytest.mark.asyncio
async def test_dcr_default_falls_back_to_read(ctx):
    """RFC 6749 §3.3: an empty scope request defaults to a minimum
    (BidVex chose `read`). Explicit request wins over default."""
    async with httpx.AsyncClient(timeout=20.0) as c:
        oidc = (await c.get(f"{BACKEND_URL}/api/.well-known/openid-configuration")).json()
        reg = await c.post(oidc["registration_endpoint"], json={
            "client_name": "iter495-noscope",
            "redirect_uris": [CLAUDE_REDIRECT],
            "token_endpoint_auth_method": "none",
        })
        cid = reg.json()["client_id"]
        v, ch = _pkce()
        st = "iter495_ns_" + uuid.uuid4().hex[:8]
        # Send an empty scope at /authorize
        dec = await c.post(f"{BACKEND_URL}/api/mcp/oauth/authorize/decision",
            headers={"Authorization": f"Bearer {ctx['jwt']}",
                     "Content-Type": "application/json"},
            json={"approved": True, "client_id": cid,
                  "redirect_uri": CLAUDE_REDIRECT,
                  "code_challenge": ch, "code_challenge_method": "S256",
                  "scope": "", "state": st})
        code = parse_qs(urlparse(dec.json()["redirect_to"]).query)["code"][0]
        tok = await c.post(oidc["token_endpoint"], data={
            "grant_type": "authorization_code",
            "code": code, "redirect_uri": CLAUDE_REDIRECT,
            "client_id": cid, "code_verifier": v})
    granted = tok.json()["scope"].split()
    assert granted == ["read"], f"expected fallback to read, got {granted}"


# ═══════════════════════════════════════════════════════════════════
# Least-privilege enforcement: read-only vs write-enabled
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_read_only_token_hides_create_auction_draft(ctx):
    """Read-only OAuth token MUST NOT expose write tools in tools/list."""
    async with httpx.AsyncClient(timeout=20.0) as c:
        tok, granted = await _oauth_dance(c, ctx["jwt"], ["read"])
        assert set(granted) == {"read"}
        sid = await _open_session(c, tok)
        names = await _tools_list(c, tok, sid)
    assert "create_auction_draft" not in names
    assert "bulk_create_listings" not in names
    assert "place_bid" not in names          # `bid` scope also absent
    # But read tools ARE exposed
    assert "search_auctions" in names
    assert "get_listing_details" in names


@pytest.mark.asyncio
async def test_read_only_token_gets_403_on_create_auction_draft(ctx):
    """Read-only token that tries to call create_auction_draft anyway
    must be blocked at the scope layer with 403 INSUFFICIENT_SCOPE."""
    async with httpx.AsyncClient(timeout=20.0) as c:
        tok, _ = await _oauth_dance(c, ctx["jwt"], ["read"])
        sid = await _open_session(c, tok)
        r = await c.post(f"{BACKEND_URL}/api/mcp",
            headers={"Authorization": f"Bearer {tok}",
                     "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "Mcp-Session-Id": sid},
            json={"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                  "params": {"name": "create_auction_draft",
                             "arguments":
                                 {"vertical": "marketplace",
                                  "raw_input": {"title": "should be blocked"}}}})
    body = r.json()["result"]
    assert body.get("isError") is True
    txt = body["content"][0]["text"]
    assert "INSUFFICIENT_SCOPE" in txt
    assert '"required_scope": "list"' in txt or "'required_scope': 'list'" in txt


@pytest.mark.asyncio
async def test_write_enabled_token_exposes_create_auction_draft(ctx):
    """OAuth token that includes `list` (canonical write scope for
    listings) MUST expose create_auction_draft in tools/list — this is
    the scope Claude uses to create listings."""
    async with httpx.AsyncClient(timeout=20.0) as c:
        tok, granted = await _oauth_dance(c, ctx["jwt"], ["read", "list"])
        assert "list" in granted
        sid = await _open_session(c, tok)
        names = await _tools_list(c, tok, sid)
    assert "create_auction_draft" in names
    assert "bulk_create_listings" in names
    # place_bid still hidden — `bid` scope wasn't granted
    assert "place_bid" not in names


# ═══════════════════════════════════════════════════════════════════
# iter494 vertical-scoping regression via Claude-parity OAuth token
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_write_enabled_token_can_create_marketplace_listing(ctx):
    """Full Claude-parity path: DCR → authorize → token (with `list`)
    → tools/call create_auction_draft (marketplace, baby-bed style).
    Must succeed — proves iter494's vertical scoping is reachable
    through the actual Claude connector transport."""
    async with httpx.AsyncClient(timeout=20.0) as c:
        tok, _ = await _oauth_dance(c, ctx["jwt"], ["read", "list"])
        sid = await _open_session(c, tok)
        r = await c.post(f"{BACKEND_URL}/api/mcp",
            headers={"Authorization": f"Bearer {tok}",
                     "Content-Type": "application/json",
                     "Accept": "application/json, text/event-stream",
                     "Mcp-Session-Id": sid},
            json={"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                  "params": {"name": "create_auction_draft",
                             "arguments": {
                                 "vertical": "marketplace",
                                 "raw_input": {"title": "Brand new baby bed",
                                               "category": "furniture",
                                               "condition": "new",
                                               "price": 250.00}}}})
    body = r.json()["result"]
    assert body.get("isError") is not True, body
    # structuredContent should carry the draft envelope
    sc = body.get("structuredContent") or {}
    assert sc.get("vertical") == "marketplace"
    assert sc.get("status") == "draft"


@pytest.mark.asyncio
async def test_write_enabled_dealer_still_blocked_on_vehicle(ctx):
    """Regression: even with the write scope granted, an unverified
    vehicle dealer MUST still be blocked on the vehicle vertical
    (iter482 + iter494 compliance)."""
    # Convert the seed user into an unverified vehicle dealer for this test
    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]
    await db.users.update_one({"id": ctx["uid"]},
        {"$set": {"is_vehicle_dealer": True,
                   "dealer_license_verified": False,
                   "dealer_subscription_status": "active",
                   "dealer_subscription_active": True,
                   "tax_id": "GST123456"}})
    try:
        async with httpx.AsyncClient(timeout=20.0) as c:
            tok, _ = await _oauth_dance(c, ctx["jwt"], ["read", "list"])
            sid = await _open_session(c, tok)
            r = await c.post(f"{BACKEND_URL}/api/mcp",
                headers={"Authorization": f"Bearer {tok}",
                         "Content-Type": "application/json",
                         "Accept": "application/json, text/event-stream",
                         "Mcp-Session-Id": sid},
                json={"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                      "params": {"name": "create_auction_draft",
                                 "arguments": {
                                     "vertical": "vehicle",
                                     "raw_input": {"title": "unit-test truck",
                                                   "vin": "TESTVIN123"}}}})
        body = r.json()["result"]
        assert body.get("isError") is True
        txt = body["content"][0]["text"]
        assert "TAX_ID_REQUIRED" in txt or "dealer_license_not_verified" in txt
    finally:
        # Restore fixture state
        await db.users.update_one({"id": ctx["uid"]},
            {"$set": {"is_vehicle_dealer": False,
                       "dealer_license_verified": False,
                       "tax_id": ""}})
        mc.close()
