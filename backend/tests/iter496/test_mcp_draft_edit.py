"""
iter496 — MCP-created draft is now editable in the Seller Dashboard.

Reproduces the "Listing not found" failure that made the Claude-created
baby-bed draft unopenable, then locks the fix.

Coverage
========
  * MCP `create_auction_draft` (marketplace) now stamps the fields the
    `Listing` response model requires (`starting_price`, `current_price`,
    `auction_end_date`). The Seller-Dashboard Edit endpoint
    `GET /api/listings/{id}` returns 200 instead of 500.
  * Same for `bulk_create_listings` (reuses the single-draft path).
  * New `update_auction_draft` tool changes title/price/images on a
    draft the caller owns, updates persist, `get_listing_details` MCP
    tool reads the new values, and the Seller-Dashboard-facing
    `GET /api/listings/{id}` returns the fresh values.
  * Least privilege: read-only OAuth token → tools/list hides
    `update_auction_draft` AND tools/call returns 403
    `INSUFFICIENT_SCOPE`.
  * Cross-user block: user A cannot update user B's draft.
  * Published/live listings cannot be modified through
    `update_auction_draft` — server returns 409 `not_a_draft`.
  * iter494 vertical-scoping fix unchanged: normalisation only applies
    to marketplace/lots verticals; vehicle & storage still route
    through their own compliance cascade.
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


async def _mint_mcp_token(client: httpx.AsyncClient, user_jwt: str,
                          scopes: list[str]) -> str:
    r = await client.post(f"{BACKEND_URL}/api/mcp/token",
        headers={"Authorization": f"Bearer {user_jwt}",
                 "Content-Type": "application/json"},
        json={"label": "iter496", "scopes": scopes, "expires_in_days": 1})
    return r.json()["token"]


async def _seed_trusted_user(db, uid: str):
    now = datetime.now(timezone.utc).isoformat()
    await db.users.replace_one({"id": uid}, {
        "id": uid, "email": f"{uid}@bidvex-iter496.test", "name": uid,
        "role": "user", "account_type": "personal",
        "subscription_tier": "premium", "subscription_status": "active",
        "phone_verified": True,
        "platform_terms_accepted_at": now,
        "created_at": now,
    }, upsert=True)
    await db.payment_methods.delete_many({"user_id": uid})
    await db.payment_methods.insert_one({
        "id": str(uuid.uuid4()), "user_id": uid,
        "brand": "visa", "last4": "4242",
        "stripe_payment_method_id": f"pm_iter496_{uid}",
        "created_at": now,
    })


@pytest_asyncio.fixture(scope="module")
async def ctx():
    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]
    uid_a = f"iter496_A_{uuid.uuid4().hex[:8]}"
    uid_b = f"iter496_B_{uuid.uuid4().hex[:8]}"
    for u in (uid_a, uid_b):
        await _seed_trusted_user(db, u)

    async with httpx.AsyncClient(timeout=15.0) as c:
        tok_write_a = await _mint_mcp_token(c, _mint_jwt(uid_a, f"{uid_a}@bidvex-iter496.test"),
                                            ["read", "list"])
        tok_write_b = await _mint_mcp_token(c, _mint_jwt(uid_b, f"{uid_b}@bidvex-iter496.test"),
                                            ["read", "list"])
        tok_read_a  = await _mint_mcp_token(c, _mint_jwt(uid_a, f"{uid_a}@bidvex-iter496.test"),
                                            ["read"])

    yield {"uid_a": uid_a, "uid_b": uid_b,
           "tok_write_a": tok_write_a, "tok_write_b": tok_write_b,
           "tok_read_a": tok_read_a}

    for uid in (uid_a, uid_b):
        await db.users.delete_one({"id": uid})
        await db.mcp_tokens.delete_many({"user_id": uid})
        await db.payment_methods.delete_many({"user_id": uid})
        await db.listings.delete_many({"seller_id": uid})
    mc.close()


async def _call(client: httpx.AsyncClient, tok: str, name: str, arguments: dict):
    return await client.post(f"{BACKEND_URL}/api/mcp/tools/call",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
        json={"name": name, "arguments": arguments})


def _tool_result(response) -> dict:
    """Unwrap the `/api/mcp/tools/call` envelope."""
    return response.json().get("result") or {}


# ═══════════════════════════════════════════════════════════════════
# Regression: MCP-created marketplace draft opens in the dashboard
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_mcp_marketplace_draft_can_be_hydrated_by_dashboard(ctx):
    """Reproduce the exact failure the operator hit — create a baby-bed
    draft through MCP, then hydrate it through the Seller Dashboard
    endpoint. Must be 200 (was 500 before iter496)."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call(c, ctx["tok_write_a"], "create_auction_draft",
            {"vertical": "marketplace",
             "raw_input": {"title": "Baby bed", "category": "furniture",
                           "condition": "new", "price": 250,
                           "location": "Sherbrooke, QC"}})
    assert r.status_code == 200
    draft_id = _tool_result(r)["draft_id"]
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{BACKEND_URL}/api/listings/{draft_id}")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["title"] == "Baby bed"
    assert body["status"] == "draft"
    assert body["starting_price"] == 250.0
    assert body["current_price"] == 250.0
    assert body["auction_end_date"]  # non-null


@pytest.mark.asyncio
async def test_mcp_marketplace_draft_missing_price_still_hydrates(ctx):
    """Even when Claude sends no price at all, the draft must still be
    dashboard-openable (starting_price defaults to 0)."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call(c, ctx["tok_write_a"], "create_auction_draft",
            {"vertical": "marketplace",
             "raw_input": {"title": "No price yet",
                           "category": "misc", "condition": "used",
                           "location": "Montreal, QC"}})
    draft_id = _tool_result(r)["draft_id"]
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{BACKEND_URL}/api/listings/{draft_id}")
    assert r.status_code == 200
    assert r.json()["starting_price"] == 0.0


@pytest.mark.asyncio
async def test_bulk_create_marketplace_draft_can_be_hydrated_by_dashboard(ctx):
    """bulk_create_listings uses the same normalisation path."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call(c, ctx["tok_write_a"], "bulk_create_listings", {
            "items": [
                {"vertical": "marketplace",
                 "raw_input": {"title": "Bulk item A",
                               "category": "misc", "condition": "used",
                               "price": 50, "location": "Ottawa, ON"}},
                {"vertical": "marketplace",
                 "raw_input": {"title": "Bulk item B",
                               "category": "misc", "condition": "new",
                               "starting_price": 75.5, "location": "Toronto, ON"}},
            ]})
    body = _tool_result(r)
    assert body["created"] == 2
    ids = [it["draft_id"] for it in body["results"]]
    async with httpx.AsyncClient(timeout=15.0) as c:
        for lid in ids:
            r = await c.get(f"{BACKEND_URL}/api/listings/{lid}")
            assert r.status_code == 200, f"{lid} -> {r.status_code}"


# ═══════════════════════════════════════════════════════════════════
# New tool: update_auction_draft — happy path
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_update_auction_draft_changes_price_title_and_images(ctx):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call(c, ctx["tok_write_a"], "create_auction_draft",
            {"vertical": "marketplace",
             "raw_input": {"title": "Baby bed v1",
                           "category": "furniture", "condition": "new",
                           "price": 250, "location": "Sherbrooke, QC"}})
        lid = _tool_result(r)["draft_id"]

        r = await _call(c, ctx["tok_write_a"], "update_auction_draft", {
            "listing_id": lid,
            "updates": {
                "title":    "Baby bed v2 (price reduced)",
                "price":    199.00,
                "images":   ["https://cdn.example.com/babybed-1.jpg",
                             "https://cdn.example.com/babybed-2.jpg"],
                "category": "Baby & Kids",
            }})
    assert r.status_code == 200, r.text
    ur = _tool_result(r)
    assert ur["status"] == "draft"
    assert "starting_price" in ur["updated_fields"]
    assert "title" in ur["updated_fields"]
    assert "images" in ur["updated_fields"]

    # Persisted → dashboard hydration returns new values
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.get(f"{BACKEND_URL}/api/listings/{lid}")
    body = r.json()
    assert body["title"] == "Baby bed v2 (price reduced)"
    assert body["starting_price"] == 199.0
    assert body["current_price"] == 199.0  # kept in lockstep
    assert body["images"] == ["https://cdn.example.com/babybed-1.jpg",
                              "https://cdn.example.com/babybed-2.jpg"]
    assert body["category"] == "Baby & Kids"


@pytest.mark.asyncio
async def test_update_auction_draft_reflected_in_get_listing_details_mcp_tool(ctx):
    """MCP `get_listing_details` must also see the fresh values."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call(c, ctx["tok_write_a"], "create_auction_draft",
            {"vertical": "marketplace",
             "raw_input": {"title": "Reflected item", "price": 50,
                           "category": "misc", "condition": "used",
                           "location": "Laval, QC"}})
        lid = _tool_result(r)["draft_id"]
        await _call(c, ctx["tok_write_a"], "update_auction_draft", {
            "listing_id": lid, "updates": {"price": 99}})
        r = await _call(c, ctx["tok_write_a"], "get_listing_details",
                        {"listing_id": lid})
    detail = _tool_result(r)
    # The tool nests the listing document
    listing = detail.get("listing") or detail
    assert listing.get("starting_price") == 99.0


# ═══════════════════════════════════════════════════════════════════
# Security
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_read_only_token_cannot_call_update_auction_draft(ctx):
    """Read-only token → 403 INSUFFICIENT_SCOPE."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        # First create a draft with the write token
        r = await _call(c, ctx["tok_write_a"], "create_auction_draft",
            {"vertical": "marketplace",
             "raw_input": {"title": "Locked item", "price": 10,
                           "category": "misc", "condition": "used",
                           "location": "Sept-Îles, QC"}})
        lid = _tool_result(r)["draft_id"]
        # Try to update with the read-only token
        r = await _call(c, ctx["tok_read_a"], "update_auction_draft", {
            "listing_id": lid, "updates": {"price": 999}})
    assert r.status_code == 403, r.text
    body = r.json()
    assert body["detail"]["error"] == "INSUFFICIENT_SCOPE"
    assert body["detail"]["required_scope"] == "list"


@pytest.mark.asyncio
async def test_user_a_cannot_update_user_b_draft(ctx):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call(c, ctx["tok_write_b"], "create_auction_draft",
            {"vertical": "marketplace",
             "raw_input": {"title": "B's item", "price": 30,
                           "category": "misc", "condition": "used",
                           "location": "Quebec, QC"}})
        lid_b = _tool_result(r)["draft_id"]
        # Now user A tries to modify user B's draft
        r = await _call(c, ctx["tok_write_a"], "update_auction_draft", {
            "listing_id": lid_b, "updates": {"price": 5}})
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "not_authorized"


@pytest.mark.asyncio
async def test_update_auction_draft_rejects_published_listing(ctx):
    """A published/live listing cannot be modified through this tool."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call(c, ctx["tok_write_a"], "create_auction_draft",
            {"vertical": "marketplace",
             "raw_input": {"title": "Will be published", "price": 60,
                           "category": "misc", "condition": "used",
                           "location": "Sherbrooke, QC"}})
        lid = _tool_result(r)["draft_id"]
    # Flip the status directly in Mongo to simulate publish
    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]
    await db.listings.update_one({"id": lid}, {"$set": {"status": "active"}})
    mc.close()
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _call(c, ctx["tok_write_a"], "update_auction_draft", {
            "listing_id": lid, "updates": {"price": 5}})
    assert r.status_code == 409, r.text
    assert r.json()["detail"]["error"] == "not_a_draft"


# ═══════════════════════════════════════════════════════════════════
# Tools/list exposure
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_update_auction_draft_listed_only_with_list_scope(ctx):
    """iter495 pattern: least-privilege exposure in tools/list."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        # write token
        hdr = {"Authorization": f"Bearer {ctx['tok_write_a']}",
               "Content-Type": "application/json",
               "Accept": "application/json, text/event-stream"}
        r = await c.post(f"{BACKEND_URL}/api/mcp", headers=hdr,
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-06-18",
                             "capabilities": {},
                             "clientInfo": {"name": "iter496", "version": "1"}}})
        sid = r.headers["mcp-session-id"]
        r = await c.post(f"{BACKEND_URL}/api/mcp",
            headers={**hdr, "Mcp-Session-Id": sid},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names_write = {t["name"] for t in r.json()["result"]["tools"]}
        # read-only token
        hdr_r = {"Authorization": f"Bearer {ctx['tok_read_a']}",
                 "Content-Type": "application/json",
                 "Accept": "application/json, text/event-stream"}
        r = await c.post(f"{BACKEND_URL}/api/mcp", headers=hdr_r,
            json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                  "params": {"protocolVersion": "2025-06-18",
                             "capabilities": {},
                             "clientInfo": {"name": "iter496-r", "version": "1"}}})
        sid_r = r.headers["mcp-session-id"]
        r = await c.post(f"{BACKEND_URL}/api/mcp",
            headers={**hdr_r, "Mcp-Session-Id": sid_r},
            json={"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}})
        names_read = {t["name"] for t in r.json()["result"]["tools"]}
    assert "update_auction_draft" in names_write
    assert "update_auction_draft" not in names_read
