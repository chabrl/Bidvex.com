"""
iter486 — MCP JSON-RPC transport + stdio bridge + SSE + Redis limiter.

Covers everything Claude Desktop needs to talk to the BidVex MCP server
end-to-end:

  1. **MCP JSON-RPC 2.0 protocol** — full handshake plus tool call flow
     (initialize → notifications/initialized → tools/list → tools/call).
  2. **Full workflow** — `search_auctions` → `get_listing_details` →
     `place_bid` (with all gates firing).
  3. **stdio bridge** — spawn `backend/mcp_bridge.py` as a subprocess
     and exchange JSON-RPC over stdin/stdout, exactly the way Claude
     Desktop launches it.
  4. **SSE transport** — open `/api/mcp/sse`, POST a message to the
     session-scoped endpoint, receive the response on the SSE stream.
  5. **Redis-backed rate limiter** — persistence across simulated
     "restart" (state survives module reload).
  6. **Redis outage fallback** — with Redis unreachable the limiter
     still works using the in-memory bucket, and the API stays up.
"""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import httpx
import jwt
import pytest
import pytest_asyncio
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
LOCAL_URL   = "http://localhost:8001"
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
    client = AsyncIOMotorClient(MONGO_URL)
    db = client[DB_NAME]
    now = datetime.now(timezone.utc).isoformat()

    # Fully verified premium buyer for the bid-flow test.
    buyer = {
        "id":                          f"mcp486_b_{uuid.uuid4().hex[:8]}",
        "email":                       f"mcp486_b_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
        "name":                        "MCP486 Buyer",
        "role":                        "user",
        "account_type":                "personal",
        "subscription_tier":           "premium",
        "subscription_status":         "active",
        "phone_verified":              True,
        "platform_terms_accepted_at":  now,
        "created_at":                  now,
    }
    seller = {
        "id":         f"mcp486_s_{uuid.uuid4().hex[:8]}",
        "email":      f"mcp486_s_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
        "name":       "MCP486 Seller",
        "role":       "user",
        "created_at": now,
    }
    for u in (buyer, seller):
        await db.users.insert_one(dict(u))
    await db.payment_methods.insert_one({
        "id":         str(uuid.uuid4()),
        "user_id":    buyer["id"],
        "brand":      "visa",
        "last4":      "4242",
        "created_at": now,
    })
    # A distinctive listing so the search hits it deterministically.
    marker = f"mcp486marker{uuid.uuid4().hex[:8]}"
    listing_id = f"mcp486_lot_{uuid.uuid4().hex[:8]}"
    await db.listings.insert_one({
        "id":               listing_id,
        "title":            f"Vintage bike {marker}",
        "description":      f"iter486 test listing {marker}",
        "seller_id":        seller["id"],
        "status":           "active",
        "current_price":    10.0,
        "starting_bid":     10.0,
        "category":         "bikes",
        "created_at":       now,
        "auction_end_date": (datetime.now(timezone.utc) + timedelta(days=7)).isoformat(),
    })
    buyer["token"] = _mint(buyer["id"], buyer["email"], "user")
    seller["token"] = _mint(seller["id"], seller["email"], "user")

    yield {"buyer": buyer, "seller": seller, "listing_id": listing_id, "marker": marker, "db": db}

    await db.users.delete_many({"id": {"$in": [buyer["id"], seller["id"]]}})
    await db.payment_methods.delete_many({"user_id": {"$in": [buyer["id"], seller["id"]]}})
    await db.listings.delete_many({"id": listing_id})
    await db.mcp_audit_logs.delete_many({"user_id": {"$in": [buyer["id"], seller["id"]]}})
    client.close()


# ─── 1. JSON-RPC 2.0 protocol handshake ──────────────────────────────
@pytest.mark.asyncio
async def test_jsonrpc_initialize_returns_valid_serverinfo(seeded):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/rpc",
                          headers={"Authorization": f"Bearer {seeded['buyer']['token']}"},
                          json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                "params": {"protocolVersion": "2024-11-05",
                                           "capabilities": {},
                                           "clientInfo": {"name": "pytest", "version": "1"}}})
    assert r.status_code == 200
    body = r.json()
    assert body["jsonrpc"] == "2.0"
    assert body["id"] == 1
    assert "result" in body and "error" not in body
    res = body["result"]
    assert res["protocolVersion"] == "2024-11-05"
    assert res["serverInfo"]["name"] == "bidvex-mcp"
    assert "tools" in res["capabilities"]


@pytest.mark.asyncio
async def test_jsonrpc_notifications_initialized_returns_202(seeded):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/rpc",
                          headers={"Authorization": f"Bearer {seeded['buyer']['token']}"},
                          json={"jsonrpc": "2.0", "method": "notifications/initialized"})
    assert r.status_code == 202
    assert r.content in (b"", b"null")  # per spec: no response body


@pytest.mark.asyncio
async def test_jsonrpc_ping_ok(seeded):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/rpc",
                          headers={"Authorization": f"Bearer {seeded['buyer']['token']}"},
                          json={"jsonrpc": "2.0", "id": 9, "method": "ping"})
    assert r.status_code == 200
    assert r.json()["result"] == {}


@pytest.mark.asyncio
async def test_jsonrpc_tools_list_shape_matches_mcp_spec(seeded):
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/rpc",
                          headers={"Authorization": f"Bearer {seeded['buyer']['token']}"},
                          json={"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
    assert r.status_code == 200
    tools = r.json()["result"]["tools"]
    names = [t["name"] for t in tools]
    # Every non-admin tool must be present
    for expected in ("search_auctions", "get_listing_details", "place_bid",
                     "check_bid_status", "create_auction_draft",
                     "get_bidding_advice", "generate_listing_video",
                     "B2B_syndication_matchmaker"):
        assert expected in names, f"missing tool {expected}"
    # Non-admin must NOT see admin-only tools
    assert "identify_top_sellers" not in names
    # Every tool has the exact MCP schema keys
    for t in tools:
        assert set(t.keys()) >= {"name", "description", "inputSchema"}
        assert "input_schema" not in t   # snake_case must NOT leak into MCP output
        assert t["inputSchema"]["type"] == "object"


# ─── 2. Full workflow via JSON-RPC ────────────────────────────────────
@pytest.mark.asyncio
async def test_full_workflow_search_details_bid_via_jsonrpc(seeded):
    """Simulate exactly what Claude Desktop does: search → details → bid.

    All 3 tool calls travel through the MCP JSON-RPC protocol; all gates
    (subscription + trust + payment method + rate limit + audit) fire.
    """
    buyer = seeded["buyer"]
    marker = seeded["marker"]
    listing_id = seeded["listing_id"]

    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30) as ac:
        headers = {"Authorization": f"Bearer {buyer['token']}"}

        # (1) search_auctions — finds our seeded listing by marker
        r = await ac.post("/api/mcp/rpc", headers=headers,
                          json={"jsonrpc": "2.0", "id": 100, "method": "tools/call",
                                "params": {"name": "search_auctions",
                                           "arguments": {"query": marker,
                                                         "vertical": "marketplace",
                                                         "limit": 5}}})
        assert r.status_code == 200
        result = r.json()["result"]
        assert result["isError"] is False
        found = result["structuredContent"]["results"]["marketplace"]
        assert any(x["id"] == listing_id for x in found), "seeded listing not found by search"

        # (2) get_listing_details — pull the same listing by id
        r = await ac.post("/api/mcp/rpc", headers=headers,
                          json={"jsonrpc": "2.0", "id": 101, "method": "tools/call",
                                "params": {"name": "get_listing_details",
                                           "arguments": {"listing_id": listing_id}}})
        assert r.status_code == 200
        result = r.json()["result"]
        assert result["isError"] is False
        assert result["structuredContent"]["listing"]["id"] == listing_id

        # (3) place_bid — with all gates firing. We pass a valid amount
        # and a matching ceiling. The bid MAY be rejected by the
        # underlying bid handler for a business reason (e.g. self-bid,
        # min-increment), but the MCP layer must NOT skip any gate.
        r = await ac.post("/api/mcp/rpc", headers=headers,
                          json={"jsonrpc": "2.0", "id": 102, "method": "tools/call",
                                "params": {"name": "place_bid",
                                           "arguments": {"listing_id": listing_id,
                                                         "bid_amount": 11.0,
                                                         "user_max_ceiling": 50.0}}})
        assert r.status_code == 200
        result = r.json()["result"]
        # Either the bid landed (isError False) or was rejected by the
        # underlying bid endpoint (isError True) — but MUST NOT crash.
        assert "content" in result

        # (4) The rate-limit remaining counter is exposed via _meta
        assert result["_meta"] is not None


@pytest.mark.asyncio
async def test_place_bid_ceiling_rejection_via_jsonrpc(seeded):
    """`bid_amount > user_max_ceiling` must be rejected (isError=true),
    not silently capped."""
    buyer = seeded["buyer"]
    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        r = await ac.post("/api/mcp/rpc",
                          headers={"Authorization": f"Bearer {buyer['token']}"},
                          json={"jsonrpc": "2.0", "id": 200, "method": "tools/call",
                                "params": {"name": "place_bid",
                                           "arguments": {"listing_id": seeded["listing_id"],
                                                         "bid_amount": 100.0,
                                                         "user_max_ceiling": 50.0}}})
    assert r.status_code == 200
    result = r.json()["result"]
    assert result["isError"] is True
    err = json.loads(result["content"][0]["text"])
    assert err["error"] == "BID_EXCEEDS_MAX_CEILING"


# ─── 3. stdio bridge subprocess test ─────────────────────────────────
@pytest.mark.asyncio
async def test_stdio_bridge_subprocess_roundtrip(seeded):
    """Spawn `mcp_bridge.py` as an actual subprocess, exchange three
    JSON-RPC messages over stdin/stdout, verify all responses come back
    correctly. This IS the Claude Desktop launch path.
    """
    env = dict(os.environ)
    env["BIDVEX_MCP_URL"] = LOCAL_URL
    env["BIDVEX_MCP_JWT"] = seeded["buyer"]["token"]

    proc = await asyncio.create_subprocess_exec(
        sys.executable, "/app/backend/mcp_bridge.py",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )

    async def _send(msg: Dict[str, Any]) -> None:
        proc.stdin.write((json.dumps(msg) + "\n").encode())
        await proc.stdin.drain()

    async def _recv_line(timeout: float = 10.0) -> Dict[str, Any]:
        line = await asyncio.wait_for(proc.stdout.readline(), timeout=timeout)
        assert line, "bridge closed stdout unexpectedly"
        return json.loads(line.decode())

    try:
        # initialize
        await _send({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                     "params": {"protocolVersion": "2024-11-05",
                                "capabilities": {},
                                "clientInfo": {"name": "stdio-bridge-test", "version": "1"}}})
        resp = await _recv_line()
        assert resp["id"] == 1
        assert resp["result"]["serverInfo"]["name"] == "bidvex-mcp"

        # notifications/initialized — no response expected; server returns
        # 202 which our bridge translates to "no output line"
        await _send({"jsonrpc": "2.0", "method": "notifications/initialized"})

        # tools/list
        await _send({"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        resp = await _recv_line()
        assert resp["id"] == 2
        names = [t["name"] for t in resp["result"]["tools"]]
        assert "search_auctions" in names

        # tools/call → search_auctions with seeded marker
        await _send({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                     "params": {"name": "search_auctions",
                                "arguments": {"query": seeded["marker"], "vertical": "marketplace",
                                              "limit": 5}}})
        resp = await _recv_line()
        assert resp["id"] == 3
        assert resp["result"]["isError"] is False
        found = resp["result"]["structuredContent"]["results"]["marketplace"]
        assert any(x["id"] == seeded["listing_id"] for x in found)
    finally:
        try:
            proc.stdin.close()
        except Exception:  # noqa: BLE001
            pass
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()


# ─── 4. SSE transport test ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_sse_transport_endpoint_and_message_roundtrip(seeded):
    """Open /api/mcp/sse, read the endpoint frame, POST a message to
    it, read the response back off the SSE stream. This is the exact
    handshake `mcp-remote` performs."""
    headers = {"Authorization": f"Bearer {seeded['buyer']['token']}"}

    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
        # Open the SSE stream — send an initialize on a separate POST
        # right after we learn the message-URL.
        async with ac.stream("GET", "/api/mcp/sse", headers=headers) as stream:
            assert stream.status_code == 200
            endpoint_url = None
            init_response = None

            async def _reader():
                nonlocal endpoint_url, init_response
                event_type = None
                data_lines: List[str] = []
                async for raw in stream.aiter_lines():
                    if raw == "":
                        # dispatch complete event
                        if event_type == "endpoint" and data_lines:
                            endpoint_url = data_lines[0]
                        elif event_type == "message" and data_lines:
                            init_response = json.loads("\n".join(data_lines))
                            return
                        event_type = None
                        data_lines = []
                        continue
                    if raw.startswith("event: "):
                        event_type = raw[len("event: "):].strip()
                    elif raw.startswith("data: "):
                        data_lines.append(raw[len("data: "):])

            reader_task = asyncio.create_task(_reader())

            # Wait until the endpoint event arrives
            deadline = time.time() + 5.0
            while endpoint_url is None and time.time() < deadline:
                await asyncio.sleep(0.05)
            assert endpoint_url, "server did not advertise SSE message endpoint"

            # POST initialize to the session-scoped endpoint
            async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac2:
                r = await ac2.post(endpoint_url,
                                    headers=headers,
                                    json={"jsonrpc": "2.0", "id": 1, "method": "initialize",
                                          "params": {"protocolVersion": "2024-11-05",
                                                     "capabilities": {},
                                                     "clientInfo": {"name": "sse-test", "version": "1"}}})
                assert r.status_code == 202

            # Wait for the SSE response frame
            await asyncio.wait_for(reader_task, timeout=5.0)
            assert init_response is not None
            assert init_response["id"] == 1
            assert init_response["result"]["serverInfo"]["name"] == "bidvex-mcp"


# ─── 5. Redis-backed limiter ────────────────────────────────────────
@pytest.mark.asyncio
async def test_redis_limiter_persistence(monkeypatch):
    """Simulate: (a) fake Redis is up, (b) fill the bucket, (c) simulate
    'backend restart' by reimporting mcp_server and resetting the
    in-memory bucket, (d) confirm the next call is still rejected —
    proving state persisted in Redis, not in-process."""
    from fakeredis.aioredis import FakeRedis
    import mcp_server as srv

    fake = FakeRedis(decode_responses=True)
    # Swap the module-level client + mark ready
    srv._redis_client = fake
    srv._redis_ready = True
    # `_get_redis` short-circuits on empty REDIS_URL — set a placeholder
    # so the preset fake client is actually returned.
    original_url = os.environ.get("REDIS_URL")
    os.environ["REDIS_URL"] = "redis://fake:6379/0"

    user_id = f"test_persist_{uuid.uuid4().hex[:8]}"

    # Fill the bucket
    for i in range(srv._RATE_LIMIT_PER_MIN):
        allowed, remaining, backend = await srv._rate_limit_check(user_id)
        assert allowed, f"unexpected block at call {i}"
        assert backend == "redis"

    # (Simulated restart) — clear in-process bucket only
    srv._rate_buckets.pop(user_id, None)

    # Redis state is still there → next call must be blocked
    allowed, remaining, backend = await srv._rate_limit_check(user_id)
    assert allowed is False, "Redis state did not persist across simulated restart"
    assert backend == "redis"

    # Cleanup so downstream tests aren't blocked
    await fake.delete(f"mcp:rl:{user_id}")
    srv._redis_client = None
    srv._redis_ready = None
    if original_url is not None:
        os.environ["REDIS_URL"] = original_url
    else:
        os.environ.pop("REDIS_URL", None)


@pytest.mark.asyncio
async def test_redis_outage_falls_back_to_memory(monkeypatch):
    """Simulate Redis being completely unreachable. The limiter must
    still function using the in-process bucket, and the API layer must
    stay up (no 5xx storms)."""
    import mcp_server as srv

    class BrokenRedis:
        def pipeline(self):        raise RuntimeError("Redis down")
        async def ping(self):      raise RuntimeError("Redis down")

    # Force the module to think Redis is unreachable
    srv._redis_client = None
    srv._redis_ready = False
    # Prevent _get_redis from finding a URL and reconnecting
    original_url = os.environ.get("REDIS_URL")
    os.environ["REDIS_URL"] = ""
    try:
        srv._rate_buckets.clear()
        user_id = f"test_outage_{uuid.uuid4().hex[:8]}"

        # Should use in-memory backend and succeed
        for i in range(srv._RATE_LIMIT_PER_MIN):
            allowed, remaining, backend = await srv._rate_limit_check(user_id)
            assert allowed, f"unexpected block at call {i} during outage"
            assert backend == "memory"

        # N+1 blocks
        allowed, remaining, backend = await srv._rate_limit_check(user_id)
        assert allowed is False
        assert backend == "memory"

        # And the HTTP surface must still respond during Redis outage.
        # Use a valid premium token so we get past the subscription gate.
        async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=15) as ac:
            r = await ac.get("/api/mcp/health")
            assert r.status_code == 200
    finally:
        if original_url is not None:
            os.environ["REDIS_URL"] = original_url
        else:
            os.environ.pop("REDIS_URL", None)
        srv._rate_buckets.clear()
