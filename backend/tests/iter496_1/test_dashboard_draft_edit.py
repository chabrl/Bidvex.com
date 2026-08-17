"""
iter496.1 — Draft listings are editable through the Seller Dashboard UI.

Locks the backend contract the Seller Dashboard Edit button now
depends on: the same `/api/listings/{id}` + `PUT /api/listings/{id}`
endpoints that were already used for pending-review drafts now also
have to work for regular `status="draft"` listings created via MCP.

Coverage
========
  * MCP-created draft can be hydrated by `GET /api/listings/{id}` and
    subsequently updated by `PUT /api/listings/{id}` (the exact call
    the Seller Dashboard editor's Save button issues).
  * Round-trip: dashboard PUT → MCP `get_listing_details` sees the
    fresh values (both surfaces read from the same underlying doc).
  * Round-trip in reverse: MCP `update_auction_draft` → dashboard
    `GET /api/listings/{id}` sees the fresh values.
  * Ownership check on the dashboard PUT stays intact for MCP drafts
    (a different user cannot PUT another user's draft).
  * Multi-item lots (`multi_item_listings`) are intentionally OUT of
    scope — the dashboard UI hides the Edit button when
    `isMultiItem` is true (they use the /lots editor instead).
  * iter495 scope enforcement still holds: read-only MCP token still
    cannot call `update_auction_draft`.

**NOTE ON IMAGE URLS**: the URLs used below (cdn.example.com/…) are
deterministic test placeholders — they are not real BidVex production
assets. This module never uploads or serves any image; it only tests
that the URL field round-trips through the create/update/dashboard
pipeline.
"""
from __future__ import annotations

import os
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

# iter496.1 — test-only placeholder URLs. NOT real production assets.
TEST_IMG_1 = "https://cdn.example.com/iter496_1-test-1.jpg"
TEST_IMG_2 = "https://cdn.example.com/iter496_1-test-2.jpg"


def _mint_jwt(uid: str, email: str) -> str:
    return jwt.encode({"sub": uid, "email": email, "role": "user",
                       "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
                      JWT_SECRET, algorithm=JWT_ALG)


async def _seed(db, uid: str):
    now = datetime.now(timezone.utc).isoformat()
    await db.users.replace_one({"id": uid}, {
        "id": uid, "email": f"{uid}@bidvex-iter4961.test", "name": uid,
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
        "stripe_payment_method_id": f"pm_iter4961_{uid}",
        "created_at": now,
    })


async def _mint_mcp_token(client: httpx.AsyncClient, user_jwt: str,
                          scopes: list[str]) -> str:
    r = await client.post(f"{BACKEND_URL}/api/mcp/token",
        headers={"Authorization": f"Bearer {user_jwt}",
                 "Content-Type": "application/json"},
        json={"label": "iter496_1", "scopes": scopes, "expires_in_days": 1})
    return r.json()["token"]


@pytest_asyncio.fixture(scope="module")
async def ctx():
    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]
    uid_a = f"iter4961_A_{uuid.uuid4().hex[:8]}"
    uid_b = f"iter4961_B_{uuid.uuid4().hex[:8]}"
    for u in (uid_a, uid_b):
        await _seed(db, u)
    async with httpx.AsyncClient(timeout=15.0) as c:
        jwt_a = _mint_jwt(uid_a, f"{uid_a}@bidvex-iter4961.test")
        jwt_b = _mint_jwt(uid_b, f"{uid_b}@bidvex-iter4961.test")
        tok_write_a = await _mint_mcp_token(c, jwt_a, ["read", "list"])
        tok_read_a  = await _mint_mcp_token(c, jwt_a, ["read"])
    yield {"uid_a": uid_a, "uid_b": uid_b,
           "jwt_a": jwt_a, "jwt_b": jwt_b,
           "tok_write_a": tok_write_a, "tok_read_a": tok_read_a}
    for u in (uid_a, uid_b):
        await db.users.delete_one({"id": u})
        await db.mcp_tokens.delete_many({"user_id": u})
        await db.payment_methods.delete_many({"user_id": u})
        await db.listings.delete_many({"seller_id": u})
    mc.close()


async def _mcp_call(c: httpx.AsyncClient, tok: str, name: str, arguments: dict):
    return await c.post(f"{BACKEND_URL}/api/mcp/tools/call",
        headers={"Authorization": f"Bearer {tok}", "Content-Type": "application/json"},
        json={"name": name, "arguments": arguments})


# ═══════════════════════════════════════════════════════════════════
# The dashboard Edit button's backend contract on an MCP draft
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dashboard_get_and_put_work_on_mcp_created_draft(ctx):
    """The Edit button navigates to /edit-listing/:id which:
       1. GETs /api/listings/{id} to hydrate the form.
       2. On Save, PUTs /api/listings/{id} with the edited fields.
       Both must succeed for an MCP-created draft."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        # Create via MCP (iter496 vertical-scoped path)
        r = await _mcp_call(c, ctx["tok_write_a"], "create_auction_draft", {
            "vertical": "marketplace",
            "raw_input": {"title": "iter496.1 baby bed", "category": "furniture",
                          "condition": "new", "price": 300,
                          "location": "Montreal, QC",
                          "description": "Original description"},
        })
        lid = r.json()["result"]["draft_id"]

        # GET — this is exactly what the Edit page's hydration call is
        r = await c.get(f"{BACKEND_URL}/api/listings/{lid}")
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "draft"

        # PUT via the same endpoint the dashboard editor's Save button uses
        r = await c.put(f"{BACKEND_URL}/api/listings/{lid}",
            headers={"Authorization": f"Bearer {ctx['jwt_a']}",
                     "Content-Type": "application/json"},
            json={"title": "iter496.1 baby bed (edited via dashboard)",
                  "description": "Edited through the Seller Dashboard.",
                  "category": "Baby & Kids",
                  "images": [TEST_IMG_1]})
        assert r.status_code == 200, r.text

        # Re-hydrate — Seller Dashboard shows the new values immediately
        r = await c.get(f"{BACKEND_URL}/api/listings/{lid}")
        body = r.json()
        assert body["title"] == "iter496.1 baby bed (edited via dashboard)"
        assert body["description"] == "Edited through the Seller Dashboard."
        assert body["category"] == "Baby & Kids"
        assert body["images"] == [TEST_IMG_1]


@pytest.mark.asyncio
async def test_dashboard_edit_visible_to_mcp_get_listing_details(ctx):
    """A change made through the dashboard PUT is visible through MCP
    `get_listing_details` — proves both surfaces read the same doc."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _mcp_call(c, ctx["tok_write_a"], "create_auction_draft", {
            "vertical": "marketplace",
            "raw_input": {"title": "Draft to be dashboard-edited",
                          "category": "misc", "condition": "used",
                          "price": 40, "location": "Laval, QC"},
        })
        lid = r.json()["result"]["draft_id"]

        # Dashboard-side edit via PUT
        r = await c.put(f"{BACKEND_URL}/api/listings/{lid}",
            headers={"Authorization": f"Bearer {ctx['jwt_a']}",
                     "Content-Type": "application/json"},
            json={"title": "Dashboard-edited title",
                  "images": [TEST_IMG_1, TEST_IMG_2]})
        assert r.status_code == 200

        # MCP surface should see it
        r = await _mcp_call(c, ctx["tok_write_a"], "get_listing_details",
                            {"listing_id": lid})
    result = r.json()["result"]
    listing = result.get("listing") or result
    assert listing["title"] == "Dashboard-edited title"
    assert listing["images"] == [TEST_IMG_1, TEST_IMG_2]


@pytest.mark.asyncio
async def test_mcp_update_visible_to_dashboard_get(ctx):
    """A change made through MCP `update_auction_draft` is visible
    through the Seller Dashboard GET — proves the reverse direction
    (iter496 flow) still works after the UI change."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _mcp_call(c, ctx["tok_write_a"], "create_auction_draft", {
            "vertical": "marketplace",
            "raw_input": {"title": "Draft to be MCP-updated",
                          "category": "misc", "condition": "used",
                          "price": 55, "location": "Ottawa, ON"},
        })
        lid = r.json()["result"]["draft_id"]

        r = await _mcp_call(c, ctx["tok_write_a"], "update_auction_draft", {
            "listing_id": lid,
            "updates": {"price": 45, "images": [TEST_IMG_1]},
        })
        assert r.status_code == 200

        r = await c.get(f"{BACKEND_URL}/api/listings/{lid}")
        body = r.json()
    assert body["starting_price"] == 45.0
    assert body["images"] == [TEST_IMG_1]


# ═══════════════════════════════════════════════════════════════════
# Ownership — dashboard PUT
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_dashboard_put_rejects_cross_user_edit_on_mcp_draft(ctx):
    """Seller B cannot dashboard-PUT seller A's draft."""
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _mcp_call(c, ctx["tok_write_a"], "create_auction_draft", {
            "vertical": "marketplace",
            "raw_input": {"title": "A's draft", "category": "misc",
                          "condition": "used", "price": 10,
                          "location": "Quebec, QC"},
        })
        lid_a = r.json()["result"]["draft_id"]

        r = await c.put(f"{BACKEND_URL}/api/listings/{lid_a}",
            headers={"Authorization": f"Bearer {ctx['jwt_b']}",
                     "Content-Type": "application/json"},
            json={"title": "hostile edit"})
    assert r.status_code == 403, r.text


# ═══════════════════════════════════════════════════════════════════
# iter495 regression via iter496.1 — scope enforcement
# ═══════════════════════════════════════════════════════════════════
@pytest.mark.asyncio
async def test_read_only_token_cannot_update_via_mcp_after_dashboard_edit(ctx):
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await _mcp_call(c, ctx["tok_write_a"], "create_auction_draft", {
            "vertical": "marketplace",
            "raw_input": {"title": "Scope check", "category": "misc",
                          "condition": "used", "price": 5,
                          "location": "Sept-Îles, QC"},
        })
        lid = r.json()["result"]["draft_id"]
        r = await _mcp_call(c, ctx["tok_read_a"], "update_auction_draft", {
            "listing_id": lid, "updates": {"price": 999}})
    assert r.status_code == 403, r.text
    assert r.json()["detail"]["error"] == "INSUFFICIENT_SCOPE"
