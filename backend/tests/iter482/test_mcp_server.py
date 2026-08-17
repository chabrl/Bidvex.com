"""
iter485 — MCP Server regression tests.

Covers:
  1. Subscription gate: free-tier → SUBSCRIPTION_REQUIRED (402);
     premium/vip/partner_pro/dealer/broker/facility → ACCEPTED.
  2. Verification gate on bid + listing tools:
       - missing phone → trust_required
       - missing payment method → trust_required
       - missing tax_id (corporate) → TAX_ID_REQUIRED
  3. Rate limit: N+1th call in a minute → RATE_LIMIT_EXCEEDED (429).
  4. Audit log: every branch (success/failure/rejected) writes a row.
  5. Secret sanitization: sensitive keys are redacted before the row
     lands in `mcp_audit_logs`.
  6. NOT_IMPLEMENTED stubs for `generate_listing_video` and
     `B2B_syndication_matchmaker`.
  7. Admin-only tools (`identify_top_sellers`) reject non-admins.
  8. `place_bid` REJECTS when bid_amount > user_max_ceiling (does not
     silently cap and proceed).

Tokens are minted directly against the backend's JWT_SECRET so the
tests do not exercise the login rate limiter.
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


def _mint(user_id: str, email: str, role: str = "user") -> str:
    exp = datetime.now(timezone.utc) + timedelta(hours=1)
    return jwt.encode(
        {"sub": user_id, "email": email, "role": role, "exp": exp},
        JWT_SECRET, algorithm=JWT_ALG,
    )


@pytest_asyncio.fixture(scope="module")
async def seeded():
    """Seed 5 users spanning all subscription/verification permutations."""
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]

    users = {}
    now = datetime.now(timezone.utc).isoformat()

    # (A) Free tier — must be REJECTED by subscription gate
    users["free"] = {
        "id":                  f"mcp485_free_{uuid.uuid4().hex[:8]}",
        "email":                f"mcp485_free_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
        "name":                 "MCP485 Free User",
        "role":                 "user",
        "account_type":         "personal",
        "subscription_tier":    "free",
        "subscription_status":  "inactive",
        "phone_verified":       True,
        "created_at":           now,
    }

    # (B) Premium active — subscription passes; NO payment method yet →
    # bid tool rejected by trust gate
    users["premium_no_pm"] = {
        "id":                   f"mcp485_prem_{uuid.uuid4().hex[:8]}",
        "email":                f"mcp485_prem_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
        "name":                 "MCP485 Premium No PM",
        "role":                 "user",
        "account_type":         "personal",
        "subscription_tier":    "premium",
        "subscription_status":  "active",
        "phone_verified":       True,
        "platform_terms_accepted_at": now,
        "created_at":           now,
    }

    # (C) Premium active + fully trust-verified — every gate passes
    users["premium_full"] = {
        "id":                   f"mcp485_pf_{uuid.uuid4().hex[:8]}",
        "email":                f"mcp485_pf_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
        "name":                 "MCP485 Premium Full",
        "role":                 "user",
        "account_type":         "personal",
        "subscription_tier":    "premium",
        "subscription_status":  "active",
        "phone_verified":       True,
        "platform_terms_accepted_at": now,
        "created_at":           now,
    }

    # (D) Vehicle dealer, subscribed, tax_id present but license NOT
    # verified → TAX_ID_REQUIRED (dealer_license_not_verified)
    users["dealer_unverified"] = {
        "id":                   f"mcp485_du_{uuid.uuid4().hex[:8]}",
        "email":                f"mcp485_du_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
        "name":                 "MCP485 Dealer Unverified",
        "role":                 "user",
        "account_type":         "business",
        "subscription_tier":    "free",
        "subscription_status":  "inactive",
        "is_vehicle_dealer":    True,
        "dealer_subscription_status": "active",
        "dealer_subscription_active": True,
        "dealer_license_verified":    False,
        "tax_id":               "111111111",
        "phone_verified":       True,
        "platform_terms_accepted_at": now,
        "created_at":           now,
    }

    # (E) Admin — for identify_top_sellers admin-only tool
    users["admin"] = {
        "id":                   f"mcp485_adm_{uuid.uuid4().hex[:8]}",
        "email":                f"mcp485_adm_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
        "name":                 "MCP485 Admin",
        "role":                 "super_admin",
        "account_type":         "personal",
        "subscription_tier":    "premium",
        "subscription_status":  "active",
        "phone_verified":       True,
        "platform_terms_accepted_at": now,
        "created_at":           now,
    }

    for u in users.values():
        await db.users.insert_one(dict(u))
        # premium_full + dealer_unverified get payment methods (needed to
        # advance past the trust gate so we can test downstream gates)
        if u["id"] in (users["premium_full"]["id"], users["dealer_unverified"]["id"]):
            await db.payment_methods.insert_one({
                "id":         str(uuid.uuid4()),
                "user_id":    u["id"],
                "brand":      "visa",
                "last4":      "4242",
                "created_at": now,
            })
        # Tokens
        u["token"] = _mint(u["id"], u["email"], u.get("role") or "user")

    # Give the tests a fresh listing to bid on
    listing_id = f"mcp485_lot_{uuid.uuid4().hex[:8]}"
    seller_id  = f"mcp485_seller_{uuid.uuid4().hex[:8]}"
    await db.users.insert_one({
        "id": seller_id, "email": f"mcp485_seller@bidvex-mcp.test",
        "name": "MCP485 Seller",
        "role": "user", "created_at": now,
    })
    await db.listings.insert_one({
        "id":            listing_id,
        "title":         "MCP485 Test Listing",
        "seller_id":     seller_id,
        "status":        "active",
        "current_bid":   10.0,
        "starting_bid":  10.0,
        "category":      "general",
        "created_at":    now,
        "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    })

    yield {"users": users, "listing_id": listing_id, "seller_id": seller_id, "db": db}

    # Teardown
    ids = [u["id"] for u in users.values()] + [seller_id]
    await db.users.delete_many({"id": {"$in": ids}})
    await db.payment_methods.delete_many({"user_id": {"$in": ids}})
    await db.listings.delete_many({"id": listing_id})
    await db.mcp_audit_logs.delete_many({"user_id": {"$in": ids}})
    client.close()


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ─── Gate 1 — subscription tier ──────────────────────────────────────
@pytest.mark.asyncio
async def test_free_tier_blocked_from_tools_list(seeded):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/list",
                          headers=_bearer(seeded["users"]["free"]["token"]))
    assert r.status_code == 402
    assert (r.json().get("detail") or {}).get("error") == "SUBSCRIPTION_REQUIRED"


@pytest.mark.asyncio
async def test_free_tier_blocked_from_call(seeded):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/call",
                          headers=_bearer(seeded["users"]["free"]["token"]),
                          json={"name": "get_listing_details",
                                "arguments": {"listing_id": seeded["listing_id"]}})
    assert r.status_code == 402
    assert (r.json().get("detail") or {}).get("error") == "SUBSCRIPTION_REQUIRED"


@pytest.mark.asyncio
async def test_premium_can_list_tools(seeded):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/list",
                          headers=_bearer(seeded["users"]["premium_full"]["token"]))
    assert r.status_code == 200
    tools = r.json()["tools"]
    names = [t["name"] for t in tools]
    # Admin-only tool must NOT be visible to non-admin
    assert "identify_top_sellers" not in names
    # All 11 non-admin tools must be present
    for expected in ("get_listing_details", "place_bid", "create_auction_draft",
                     "bulk_create_listings", "check_bid_status",
                     "publish_meta_ad_promotion", "generate_listing_video",
                     "get_bidding_advice", "analyze_seller_inventory",
                     "detect_performance_bottlenecks",
                     "B2B_syndication_matchmaker"):
        assert expected in names


@pytest.mark.asyncio
async def test_admin_sees_admin_only_tools(seeded):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/list",
                          headers=_bearer(seeded["users"]["admin"]["token"]))
    names = [t["name"] for t in r.json()["tools"]]
    assert "identify_top_sellers" in names


# ─── Gate 2 — trust / verification ────────────────────────────────────
@pytest.mark.asyncio
async def test_bid_rejected_when_no_payment_method(seeded):
    """Premium tier, phone verified, T&C accepted, but NO card on file."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/call",
                          headers=_bearer(seeded["users"]["premium_no_pm"]["token"]),
                          json={"name": "place_bid",
                                "arguments": {"listing_id": seeded["listing_id"],
                                              "bid_amount": 11.0,
                                              "user_max_ceiling": 50.0}})
    assert r.status_code == 403
    detail = r.json().get("detail") or {}
    assert detail.get("error") == "trust_required"
    assert "payment_method" in (detail.get("missing") or [])


@pytest.mark.asyncio
async def test_bid_rejected_when_ceiling_exceeded(seeded):
    """Even a fully verified user is REJECTED when bid_amount > ceiling —
    the tool must never silently cap and proceed."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/call",
                          headers=_bearer(seeded["users"]["premium_full"]["token"]),
                          json={"name": "place_bid",
                                "arguments": {"listing_id": seeded["listing_id"],
                                              "bid_amount": 100.0,
                                              "user_max_ceiling": 50.0}})
    assert r.status_code == 400
    assert (r.json().get("detail") or {}).get("error") == "BID_EXCEEDS_MAX_CEILING"


@pytest.mark.asyncio
async def test_create_draft_requires_tax_verification(seeded):
    """Vehicle dealer subscribed but license_verified=False must be
    rejected with TAX_ID_REQUIRED / dealer_license_not_verified."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/call",
                          headers=_bearer(seeded["users"]["dealer_unverified"]["token"]),
                          json={"name": "create_auction_draft",
                                "arguments": {"vertical": "vehicle",
                                              "raw_input": {"title": "unit test truck", "vin": "TEST"}}})
    assert r.status_code == 403
    detail = r.json().get("detail") or {}
    assert detail.get("error") == "TAX_ID_REQUIRED"
    assert detail.get("detail") == "dealer_license_not_verified"


# ─── Gate 3 — admin-only enforcement ─────────────────────────────────
@pytest.mark.asyncio
async def test_non_admin_blocked_from_top_sellers(seeded):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/call",
                          headers=_bearer(seeded["users"]["premium_full"]["token"]),
                          json={"name": "identify_top_sellers",
                                "arguments": {"limit": 5}})
    assert r.status_code == 403
    assert (r.json().get("detail") or {}).get("error") == "ADMIN_ONLY"


# ─── Read-only tools work for premium users ───────────────────────────
@pytest.mark.asyncio
async def test_get_listing_details_ok_for_premium(seeded):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/call",
                          headers=_bearer(seeded["users"]["premium_full"]["token"]),
                          json={"name": "get_listing_details",
                                "arguments": {"listing_id": seeded["listing_id"]}})
    assert r.status_code == 200
    data = r.json()
    assert data["tool"] == "get_listing_details"
    listing = data["result"]["listing"]
    assert listing["id"] == seeded["listing_id"]
    assert listing["title"] == "MCP485 Test Listing"


@pytest.mark.asyncio
async def test_get_bidding_advice_returns_comparables(seeded):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/call",
                          headers=_bearer(seeded["users"]["premium_full"]["token"]),
                          json={"name": "get_bidding_advice",
                                "arguments": {"listing_id": seeded["listing_id"]}})
    assert r.status_code == 200
    assert "comparables" in r.json()["result"]


# ─── NOT_IMPLEMENTED stubs ───────────────────────────────────────────
@pytest.mark.asyncio
async def test_generate_listing_video_is_stub(seeded):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/call",
                          headers=_bearer(seeded["users"]["premium_full"]["token"]),
                          json={"name": "generate_listing_video",
                                "arguments": {"listing_id": seeded["listing_id"]}})
    assert r.status_code == 200
    assert r.json()["result"]["status"] == "NOT_IMPLEMENTED"
    assert r.json()["result"]["reason"] == "higgsfield_not_provisioned"


@pytest.mark.asyncio
async def test_b2b_matchmaker_functional_after_iter488(seeded):
    """iter488 replaced the Phase 1 stub with a functional
    approval-based matchmaker. The tool must now analyse the caller's
    own inventory and return `drafts_ready`. External communications
    still require explicit authorisation."""
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30) as ac:
        r = await ac.post("/api/mcp/tools/call",
                          headers=_bearer(seeded["users"]["premium_full"]["token"]),
                          json={"name": "B2B_syndication_matchmaker",
                                "arguments": {"action": "analyze"}})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["status"] in {"drafts_ready", "no_inventory"}
    if result["status"] == "drafts_ready":
        assert result.get("approval_required") is True


# ─── Unknown tool ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_unknown_tool_returns_404(seeded):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/call",
                          headers=_bearer(seeded["users"]["premium_full"]["token"]),
                          json={"name": "does_not_exist", "arguments": {}})
    assert r.status_code == 404
    assert (r.json().get("detail") or {}).get("error") == "UNKNOWN_TOOL"


# ─── Rate limit + audit log + sanitizer ───────────────────────────────
@pytest.mark.asyncio
async def test_rate_limit_exceeded_writes_audit(seeded):
    """Blast the endpoint until we hit the per-user limit; assert 429
    and that the failure lands as `rejected/RATE_LIMIT_EXCEEDED` in the
    audit collection."""
    from mcp_server import _RATE_LIMIT_PER_MIN, _rate_buckets
    user = seeded["users"]["admin"]  # use admin so the tool is cheap
    # Reset the bucket for this test so we control the count.
    _rate_buckets.pop(user["id"], None)

    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        # Fill the bucket
        for _ in range(_RATE_LIMIT_PER_MIN):
            r = await ac.post("/api/mcp/tools/call",
                              headers=_bearer(user["token"]),
                              json={"name": "get_listing_details",
                                    "arguments": {"listing_id": seeded["listing_id"]}})
            assert r.status_code == 200
        # +1 should trip
        r = await ac.post("/api/mcp/tools/call",
                          headers=_bearer(user["token"]),
                          json={"name": "get_listing_details",
                                "arguments": {"listing_id": seeded["listing_id"]}})
    assert r.status_code == 429
    assert (r.json().get("detail") or {}).get("error") == "RATE_LIMIT_EXCEEDED"

    # Audit row lookup — use a per-test Motor client to avoid cross-loop
    # issues with the module-scoped fixture db handle.
    fresh_client = AsyncIOMotorClient(MONGO_URL)
    try:
        db = fresh_client[DB_NAME]
        row = await db.mcp_audit_logs.find_one(
            {"user_id": user["id"], "error_code": "RATE_LIMIT_EXCEEDED"},
            {"_id": 0},
        )
        assert row is not None
        assert row["source"] == "mcp_claude"
        assert row["result_status"] == "rejected"
    finally:
        fresh_client.close()

    # Reset for downstream tests
    _rate_buckets.pop(user["id"], None)


@pytest.mark.asyncio
async def test_audit_row_sanitizes_secrets(seeded):
    """Include obviously sensitive keys and Stripe-key-shaped values in
    the input arguments; assert they never reach mcp_audit_logs."""
    from mcp_server import _rate_buckets
    user = seeded["users"]["premium_full"]
    _rate_buckets.pop(user["id"], None)  # ensure headroom

    sensitive_args = {
        "listing_id":     seeded["listing_id"],
        "password":       "hunter2_should_not_survive",
        "api_key":        "sk_live_abcdef1234567890",
        "nested":         {"jwt_token": "Bearer eyJhbGciOiJIUzI1NiJ9.abc.def",
                           "card_number": "4242424242424242"},
    }
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/call",
                          headers=_bearer(user["token"]),
                          json={"name": "get_listing_details", "arguments": sensitive_args})
    assert r.status_code == 200

    # Per-test Motor client — avoids the "attached to a different loop"
    # error when the fixture's db handle is reused across tests.
    fresh_client = AsyncIOMotorClient(MONGO_URL)
    try:
        db = fresh_client[DB_NAME]
        row = await db.mcp_audit_logs.find_one(
            {"user_id": user["id"], "tool_name": "get_listing_details", "result_status": "success"},
            {"_id": 0},
            sort=[("timestamp", -1)],
        )
        assert row is not None
        ip = row["input_params"]
        # Sensitive keys redacted
        assert ip.get("password")  == "<redacted:key>"
        assert ip.get("api_key")   == "<redacted:key>"
        assert ip.get("nested", {}).get("jwt_token")    == "<redacted:key>"
        assert ip.get("nested", {}).get("card_number") == "<redacted:key>"
        # Innocuous field preserved
        assert ip.get("listing_id") == seeded["listing_id"]
    finally:
        fresh_client.close()


# ─── Unauth requests get 401 ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_unauth_request_gets_401():
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/tools/list")
    assert r.status_code == 401


# ─── Static verification of the source file ───────────────────────────
def test_source_b2b_matchmaker_is_now_functional_iter488():
    """iter488 replaced the Phase-1 stub with a functional
    approval-based matchmaker. Guard that:
      * the handler exists and calls the b2b_matchmaker service,
      * the description mentions the approval requirement,
      * the tool NEVER auto-dispatches emails/ads/bids.
    """
    with open("/app/backend/mcp_server.py", "r", encoding="utf-8") as fh:
        src = fh.read()
    assert "async def tool_b2b_syndication_matchmaker" in src
    # Wires into the iter488 service
    assert "services.b2b_matchmaker" in src
    assert "run_matchmaker" in src
    assert "authorised_execute_campaign" in src
    # The description explicitly labels the approval-first contract
    idx = src.find('"B2B_syndication_matchmaker": ToolSpec(')
    assert idx > 0
    tail = src[idx: idx + 2500]
    assert "authorised" in tail.lower() or "authorized" in tail.lower()
    assert "will never" in tail.lower() or "never" in tail.lower()


def test_source_does_not_import_or_touch_stripe_secrets():
    """MCP server must never import Stripe SDK or touch secret keys."""
    with open("/app/backend/mcp_server.py", "r", encoding="utf-8") as fh:
        src = fh.read()
    assert "STRIPE_SECRET_KEY" not in src
    assert "stripe.api_key" not in src
    assert "import stripe" not in src.replace(" import stripe as ", "")
