#!/usr/bin/env python3
"""
iter488 — REAL Claude Desktop E2E ACCEPTANCE HARNESS.

This script simulates Claude Desktop exactly the way Claude Desktop
does it: by spawning `backend/mcp_bridge.py` as a subprocess and
exchanging newline-delimited JSON-RPC 2.0 messages over stdin/stdout.

**Important honesty:** the Claude Desktop GUI application cannot be run
inside the Kubernetes preview container (no display, no Claude Desktop
binary). From the BidVex MCP server's perspective, however, the wire
protocol is byte-for-byte identical: `initialize`, `notifications/
initialized`, `tools/list`, `tools/call`, framed as JSON-RPC over
stdio, forwarded by `mcp_bridge.py` to `POST /api/mcp/rpc`. If this
harness passes, a real Claude Desktop client on the operator's own
machine will experience the same behaviour (subject only to correctness
of the local `claude_desktop_config.json`, which is user-supplied).

The harness enforces every acceptance criterion the user asked for.
Any single failure is a defect.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import bcrypt
import httpx
import jwt
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient

load_dotenv("/app/backend/.env")

BACKEND_URL = os.environ.get("REACT_APP_BACKEND_URL") or "http://localhost:8001"
MONGO_URL   = os.environ["MONGO_URL"]
DB_NAME     = os.environ["DB_NAME"]
JWT_SECRET  = os.environ["JWT_SECRET"]
JWT_ALG     = os.environ.get("JWT_ALGORITHM", "HS256")

BRIDGE_PATH = "/app/backend/mcp_bridge.py"

REPORT: Dict[str, Any] = {
    "started_at":     datetime.now(timezone.utc).isoformat(),
    "backend_url":    BACKEND_URL,
    "checks":         [],
    "defects":        [],
}


def _record(name: str, passed: bool, detail: Any = None) -> None:
    REPORT["checks"].append({"name": name, "passed": passed, "detail": detail})
    if not passed:
        REPORT["defects"].append({"name": name, "detail": detail})
    print(f"  {'✓' if passed else '✗'} {name}"
          + (f" :: {detail}" if detail and not passed else ""))


def _mint_jwt(user_id: str, email: str, role: str = "user") -> str:
    return jwt.encode(
        {"sub": user_id, "email": email, "role": role,
         "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
        JWT_SECRET, algorithm=JWT_ALG,
    )


# ═══════════════════════════════════════════════════════════════════
# Bridge subprocess helper — spawns mcp_bridge.py exactly as Claude
# Desktop would, sends framed JSON-RPC lines, collects responses.
# ═══════════════════════════════════════════════════════════════════
async def bridge_exchange(mcp_token: str, messages: List[Dict[str, Any]],
                          timeout_s: float = 30.0) -> List[Dict[str, Any]]:
    """Spawn mcp_bridge.py, send each message as a line, close stdin,
    collect all response lines (JSON objects), return them in order."""
    env = os.environ.copy()
    env["BIDVEX_MCP_URL"] = BACKEND_URL
    env["BIDVEX_MCP_JWT"] = mcp_token
    proc = await asyncio.create_subprocess_exec(
        sys.executable, BRIDGE_PATH,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env,
    )
    payload = b""
    for msg in messages:
        payload += (json.dumps(msg) + "\n").encode()
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(input=payload), timeout=timeout_s,
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
        raise
    lines: List[Dict[str, Any]] = []
    for line in stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            lines.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return lines


# ═══════════════════════════════════════════════════════════════════
# Seeding — build the users we need for every scenario. Uses idempotent
# upserts so the harness can re-run.
# ═══════════════════════════════════════════════════════════════════
async def seed(db) -> Dict[str, Dict[str, str]]:
    now = datetime.now(timezone.utc).isoformat()
    users: Dict[str, Dict[str, Any]] = {}

    # (1) Premium/full — passes every gate (subscription + trust +
    # payment method). Used for the happy path.
    users["premium_full"] = {
        "id":                 f"iter488e2e_pf_{uuid.uuid4().hex[:8]}",
        "email":               f"iter488e2e_pf_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
        "name":                "iter488 E2E Premium",
        "role":                "user",
        "account_type":        "personal",
        "subscription_tier":   "premium",
        "subscription_status": "active",
        "phone_verified":      True,
        "platform_terms_accepted_at": now,
        "created_at":          now,
    }
    # (2) Premium/no payment method — used to prove trust gate still
    # fires when authenticating via MCP token with `bid` scope.
    users["premium_no_pm"] = {
        "id":                 f"iter488e2e_np_{uuid.uuid4().hex[:8]}",
        "email":               f"iter488e2e_np_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
        "name":                "iter488 E2E No PM",
        "role":                "user",
        "account_type":        "personal",
        "subscription_tier":   "premium",
        "subscription_status": "active",
        "phone_verified":      True,
        "platform_terms_accepted_at": now,
        "created_at":          now,
    }
    # (3) Free-tier — used to prove subscription gate still fires.
    users["free"] = {
        "id":                 f"iter488e2e_free_{uuid.uuid4().hex[:8]}",
        "email":               f"iter488e2e_free_{uuid.uuid4().hex[:6]}@bidvex-mcp.test",
        "name":                "iter488 E2E Free",
        "role":                "user",
        "account_type":        "personal",
        "subscription_tier":   "free",
        "subscription_status": "inactive",
        "created_at":          now,
    }

    for u in users.values():
        await db.users.replace_one({"id": u["id"]}, u, upsert=True)

    # Give premium_full a payment method so trust gate would pass
    await db.payment_methods.delete_many({"user_id": users["premium_full"]["id"]})
    await db.payment_methods.insert_one({
        "id":         str(uuid.uuid4()),
        "user_id":    users["premium_full"]["id"],
        "type":       "card",
        "last4":      "4242",
        "created_at": now,
    })

    # Seed a listing owned by premium_full so search_auctions +
    # get_listing_details + matchmaker have real inventory.
    listing_id = f"iter488e2e_lst_{uuid.uuid4().hex[:8]}"
    await db.listings.replace_one({"id": listing_id}, {
        "id":            listing_id,
        "seller_id":     users["premium_full"]["id"],
        "title":         "Iter488 E2E Test Beams 10T",
        "description":   "Steel beams, ready for pickup in Montreal.",
        "category":      "industrial",
        "current_price": 4500.0,
        "starting_price": 2500.0,
        "quantity":      10,
        "location":      "QC Montreal",
        "condition":     "good",
        "status":        "active",
        "created_at":    now,
    }, upsert=True)

    # Seed a qualified broker buyer so the matchmaker actually finds
    # a match and generates campaign drafts we can inspect.
    buyer_id = f"iter488e2e_broker_{uuid.uuid4().hex[:8]}"
    await db.users.replace_one({"id": buyer_id}, {
        "id":                 buyer_id,
        "email":               f"{buyer_id}@bidvex-mcp.test",
        "name":                "Iter488 E2E Broker",
        "role":                "user",
        "account_type":        "broker",
        "subscription_tier":   "partner_pro",
        "subscription_status": "active",
        "admin_verified":      True,
        "business_name":       "Iter488 E2E Broker Co.",
        "phone":               "+15145550199",  # PII we must NEVER leak
        "province":            "QC",
        "buyer_preferences": {
            "categories": ["industrial"],
            "verticals":  ["marketplace"],
            "provinces":  ["QC"],
            "min_price":  100,
            "max_price":  50000,
        },
        "created_at":          now,
    }, upsert=True)

    return {
        "premium_full":  {"id": users["premium_full"]["id"],  "jwt": _mint_jwt(users["premium_full"]["id"],  users["premium_full"]["email"])},
        "premium_no_pm": {"id": users["premium_no_pm"]["id"], "jwt": _mint_jwt(users["premium_no_pm"]["id"], users["premium_no_pm"]["email"])},
        "free":          {"id": users["free"]["id"],          "jwt": _mint_jwt(users["free"]["id"],          users["free"]["email"])},
        "seed_listing_id": listing_id,
        "buyer_id":     buyer_id,
    }


async def cleanup(db, ctx: Dict[str, Any]) -> None:
    for k in ("premium_full", "premium_no_pm", "free"):
        uid = ctx[k]["id"]
        await db.users.delete_one({"id": uid})
        await db.mcp_tokens.delete_many({"user_id": uid})
        await db.payment_methods.delete_many({"user_id": uid})
    await db.users.delete_one({"id": ctx["buyer_id"]})
    await db.listings.delete_one({"id": ctx["seed_listing_id"]})
    await db["b2b_matchmaker_authorisations"].delete_many({"campaign_id": {"$regex": "^camp_"}})


# ═══════════════════════════════════════════════════════════════════
# Token helpers
# ═══════════════════════════════════════════════════════════════════
async def create_scoped_token(jwt_token: str, scopes: List[str], label: str,
                              *, days: int = 30) -> Tuple[str, str]:
    async with httpx.AsyncClient(timeout=15.0) as c:
        r = await c.post(f"{BACKEND_URL}/api/mcp/token",
                         headers={"Authorization": f"Bearer {jwt_token}",
                                  "Content-Type": "application/json"},
                         json={"label": label, "scopes": scopes, "expires_in_days": days})
    body = r.json()
    return body["token"], body["token_id"]


# ═══════════════════════════════════════════════════════════════════
# ACCEPTANCE TEST
# ═══════════════════════════════════════════════════════════════════
async def run() -> int:
    print(f"\n=== iter488 REAL CLAUDE DESKTOP E2E ACCEPTANCE ===")
    print(f"Backend URL: {BACKEND_URL}")
    print(f"Bridge path: {BRIDGE_PATH}\n")

    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]

    print("Seeding fixtures…")
    ctx = await seed(db)
    print(f"  premium_full={ctx['premium_full']['id']}")
    print(f"  premium_no_pm={ctx['premium_no_pm']['id']}")
    print(f"  free={ctx['free']['id']}")
    print(f"  seed_listing={ctx['seed_listing_id']}")
    print(f"  buyer={ctx['buyer_id']}")

    try:
        # ─────────────────────────────────────────────────────────
        # A) Generate a token with (read + matchmaker) scope for the
        # premium_full user.
        # ─────────────────────────────────────────────────────────
        print("\n[A] Generate scoped MCP token (read + matchmaker)…")
        raw, tid = await create_scoped_token(
            ctx["premium_full"]["jwt"],
            scopes=["read", "matchmaker"],
            label="e2e-happy-path",
        )
        _record("A.1 raw token returned exactly once",
                bool(raw and raw.startswith("bvx_mcp_")),
                {"prefix_ok": raw.startswith("bvx_mcp_")})
        # Confirm raw NOT in DB
        doc = await db.mcp_tokens.find_one({"token_id": tid})
        remainder = raw[len("bvx_mcp_"):]
        _, secret = remainder.split("_", 1)
        haystack = str(doc)
        _record("A.2 raw secret NOT persisted in mongo",
                secret not in haystack and raw not in haystack)
        _record("A.3 bcrypt hash persisted",
                doc["token_hash"].startswith("$2b$") and
                bcrypt.checkpw(secret.encode("utf-8"),
                               doc["token_hash"].encode("utf-8")))

        # ─────────────────────────────────────────────────────────
        # B) Bridge-driven MCP handshake + full happy path
        # ─────────────────────────────────────────────────────────
        print("\n[B] stdio bridge handshake + happy path…")
        msgs = [
            {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "claude-desktop", "version": "sim-1.0"},
            }},
            {"jsonrpc": "2.0", "method": "notifications/initialized"},
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
            {"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {
                "name": "search_auctions",
                "arguments": {"query": "beams", "vertical": "marketplace", "limit": 5},
            }},
            {"jsonrpc": "2.0", "id": 4, "method": "tools/call", "params": {
                "name": "get_listing_details",
                "arguments": {"listing_id": ctx["seed_listing_id"]},
            }},
            {"jsonrpc": "2.0", "id": 5, "method": "tools/call", "params": {
                "name": "B2B_syndication_matchmaker",
                "arguments": {"action": "analyze", "min_score": 10, "max_matches": 5},
            }},
        ]
        resp = await bridge_exchange(raw, msgs)
        by_id = {r.get("id"): r for r in resp if isinstance(r, dict)}

        # initialize
        init = by_id.get(1) or {}
        _record("B.1 initialize handshake — protocol 2024-11-05",
                init.get("result", {}).get("protocolVersion") == "2024-11-05",
                init.get("result", {}))
        _record("B.2 initialize handshake — serverInfo=bidvex-mcp",
                init.get("result", {}).get("serverInfo", {}).get("name") == "bidvex-mcp")

        # tools/list
        tl = by_id.get(2) or {}
        tools = tl.get("result", {}).get("tools", [])
        tool_names = {t["name"] for t in tools}
        _record("B.3 tools/list — only read + matchmaker tools visible",
                tool_names == {"get_listing_details", "search_auctions",
                               "check_bid_status", "get_bidding_advice",
                               "B2B_syndication_matchmaker"},
                sorted(tool_names))

        # search_auctions
        sa = by_id.get(3) or {}
        sa_ok = sa.get("result", {}).get("isError") is False
        sa_struct = sa.get("result", {}).get("structuredContent", {})
        _record("B.4 search_auctions — succeeds", sa_ok)
        # get_listing_details
        gl = by_id.get(4) or {}
        gl_ok = gl.get("result", {}).get("isError") is False
        gl_struct = gl.get("result", {}).get("structuredContent", {})
        _record("B.5 get_listing_details — returns seed listing",
                gl_ok and gl_struct.get("listing", {}).get("id") == ctx["seed_listing_id"])

        # Matchmaker analyze
        mm = by_id.get(5) or {}
        mm_ok = mm.get("result", {}).get("isError") is False
        mm_struct = mm.get("result", {}).get("structuredContent", {})
        _record("B.6 matchmaker — analyze returns drafts_ready",
                mm_struct.get("status") == "drafts_ready",
                mm_struct.get("status"))
        _record("B.7 matchmaker — approval_required=True",
                mm_struct.get("approval_required") is True)

        campaigns = mm_struct.get("campaigns") or []
        en_msg = fr_msg = ""
        if campaigns:
            c0 = campaigns[0]
            en_msg = (c0.get("en") or {}).get("message", "")
            fr_msg = (c0.get("fr") or {}).get("message", "")
        _record("B.8 EN campaign generated (non-empty, English-flavoured)",
                bool(en_msg) and ("Hello" in en_msg or "Best regards" in en_msg),
                {"en_message_preview": en_msg[:120]})
        _record("B.9 FR campaign generated (non-empty, French-flavoured)",
                bool(fr_msg) and ("Bonjour" in fr_msg or "Cordialement" in fr_msg),
                {"fr_message_preview": fr_msg[:120]})
        _record("B.10 EN and FR campaigns are not identical",
                en_msg and fr_msg and en_msg != fr_msg)

        # ─────────────────────────────────────────────────────────
        # C) Approval gate — authorise must NOT dispatch
        # ─────────────────────────────────────────────────────────
        if campaigns:
            camp_id = campaigns[0]["campaign_id"]
            print("\n[C] Matchmaker approval gate…")
            resp_c = await bridge_exchange(raw, [
                {"jsonrpc": "2.0", "id": 6, "method": "tools/call", "params": {
                    "name": "B2B_syndication_matchmaker",
                    "arguments": {"action": "authorise", "campaign_id": camp_id,
                                  "explicit_authorization": True},
                }},
                {"jsonrpc": "2.0", "id": 7, "method": "tools/call", "params": {
                    "name": "B2B_syndication_matchmaker",
                    "arguments": {"action": "authorise", "campaign_id": camp_id,
                                  "explicit_authorization": False},
                }},
            ])
            by_id_c = {r.get("id"): r for r in resp_c if isinstance(r, dict)}
            auth = (by_id_c.get(6) or {}).get("result", {}).get("structuredContent", {})
            unauth = (by_id_c.get(7) or {}).get("result", {}).get("structuredContent", {})
            _record("C.1 authorise (explicit=True) → authorized_pending_dispatch",
                    auth.get("status") == "authorized_pending_dispatch" and
                    auth.get("dispatched") is False,
                    auth)
            _record("C.2 authorise (explicit=False) → approval_required",
                    unauth.get("status") == "approval_required", unauth)

        # ─────────────────────────────────────────────────────────
        # D) Buyer PII protection — matchmaker payload must NOT contain
        # phone/email of the buyer we seeded.
        # ─────────────────────────────────────────────────────────
        print("\n[D] Buyer PII protection…")
        full_payload = json.dumps(mm_struct)
        _record("D.1 buyer email absent from matchmaker payload",
                f"{ctx['buyer_id']}@bidvex-mcp.test" not in full_payload)
        _record("D.2 buyer phone absent from matchmaker payload",
                "+15145550199" not in full_payload)
        # But business_name IS allowed (public commercial identity)
        _record("D.3 buyer business_name is emitted (allowed)",
                "Iter488 E2E Broker Co." in full_payload)

        # ─────────────────────────────────────────────────────────
        # E) Negative authorisation cases — new tokens with narrower
        # scopes, confirm scope enforcement across REST + JSON-RPC.
        # ─────────────────────────────────────────────────────────
        print("\n[E] Negative authorisation cases…")

        # E.1 read-only token cannot invoke place_bid
        raw_read, _ = await create_scoped_token(
            ctx["premium_full"]["jwt"], scopes=["read"], label="e2e-read-only")
        resp_e1 = await bridge_exchange(raw_read, [
            {"jsonrpc": "2.0", "id": 20, "method": "tools/call", "params": {
                "name": "place_bid",
                "arguments": {"listing_id": ctx["seed_listing_id"],
                              "bid_amount": 100.0, "user_max_ceiling": 500.0},
            }},
        ])
        r20 = (resp_e1[0] if resp_e1 else {}).get("result", {})
        is_err = r20.get("isError")
        err_body = json.loads(r20.get("content", [{}])[0].get("text", "{}")) if is_err else {}
        _record("E.1 read scope cannot invoke place_bid — INSUFFICIENT_SCOPE",
                bool(is_err) and err_body.get("error") == "INSUFFICIENT_SCOPE",
                err_body)

        # E.2 read-only token cannot invoke create_auction_draft
        resp_e2 = await bridge_exchange(raw_read, [
            {"jsonrpc": "2.0", "id": 21, "method": "tools/call", "params": {
                "name": "create_auction_draft",
                "arguments": {"vertical": "marketplace",
                              "raw_input": {"title": "should not be created"}},
            }},
        ])
        r21 = (resp_e2[0] if resp_e2 else {}).get("result", {})
        is_err2 = r21.get("isError")
        err_body2 = json.loads(r21.get("content", [{}])[0].get("text", "{}")) if is_err2 else {}
        _record("E.2 read scope cannot invoke listing creation — INSUFFICIENT_SCOPE",
                bool(is_err2) and err_body2.get("error") == "INSUFFICIENT_SCOPE",
                err_body2)
        # And verify no draft was persisted
        drafts = await db.listings.count_documents(
            {"seller_id": ctx["premium_full"]["id"],
             "title": "should not be created"})
        _record("E.2b confirmed NO draft persisted", drafts == 0)

        # E.3 token without matchmaker scope cannot invoke matchmaker
        raw_no_mm, _ = await create_scoped_token(
            ctx["premium_full"]["jwt"], scopes=["read", "analytics"],
            label="e2e-no-mm")
        resp_e3 = await bridge_exchange(raw_no_mm, [
            {"jsonrpc": "2.0", "id": 22, "method": "tools/call", "params": {
                "name": "B2B_syndication_matchmaker",
                "arguments": {"action": "analyze"},
            }},
        ])
        r22 = (resp_e3[0] if resp_e3 else {}).get("result", {})
        is_err3 = r22.get("isError")
        err_body3 = json.loads(r22.get("content", [{}])[0].get("text", "{}")) if is_err3 else {}
        _record("E.3 token w/o matchmaker scope cannot invoke matchmaker",
                bool(is_err3) and err_body3.get("error") == "INSUFFICIENT_SCOPE",
                err_body3)

        # E.4 Revoked token is rejected immediately
        raw_rev, tid_rev = await create_scoped_token(
            ctx["premium_full"]["jwt"], scopes=["read"], label="e2e-revoke-me")
        # Prove it works first
        pre = await bridge_exchange(raw_rev, [
            {"jsonrpc": "2.0", "id": 30, "method": "tools/list", "params": {}},
        ])
        pre_ok = "result" in (pre[0] if pre else {})
        # Revoke
        async with httpx.AsyncClient(timeout=15.0) as c:
            await c.delete(f"{BACKEND_URL}/api/mcp/token/{tid_rev}",
                           headers={"Authorization": f"Bearer {ctx['premium_full']['jwt']}"})
        # Now the raw must be rejected
        post = await bridge_exchange(raw_rev, [
            {"jsonrpc": "2.0", "id": 31, "method": "tools/list", "params": {}},
        ])
        # After revocation the bridge writes back the raw HTTP error
        # payload (`{"detail": {"error": "INVALID_MCP_TOKEN", ...}}`)
        # because the JSON-RPC endpoint fails at the dependency layer
        # with a 401.
        rev_detail = ((post[0] if post else {}) or {}).get("detail") or {}
        _record("E.4 revoked token is rejected immediately",
                pre_ok and rev_detail.get("error") == "INVALID_MCP_TOKEN",
                rev_detail)

        # E.5 Expired token is rejected. Direct DB insert of an
        # already-expired token with a known bcrypt-verifiable secret.
        exp_tid = uuid.uuid4().hex[:16]
        exp_secret = "expiredsec_" + uuid.uuid4().hex
        exp_bh = bcrypt.hashpw(exp_secret.encode("utf-8"),
                               bcrypt.gensalt(rounds=4)).decode("utf-8")
        exp_raw = f"bvx_mcp_{exp_tid}_{exp_secret}"
        past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        await db.mcp_tokens.insert_one({
            "id":         str(uuid.uuid4()),
            "token_id":   exp_tid,
            "user_id":    ctx["premium_full"]["id"],
            "token_hash": exp_bh,
            "label":      "e2e-expired",
            "scopes":     ["read"],
            "created_at": past,
            "expires_at": past,
            "revoked":    False,
        })
        exp_resp = await bridge_exchange(exp_raw, [
            {"jsonrpc": "2.0", "id": 40, "method": "tools/list", "params": {}},
        ])
        exp_detail = ((exp_resp[0] if exp_resp else {}) or {}).get("detail") or {}
        _record("E.5 expired token is rejected",
                exp_detail.get("error") == "INVALID_MCP_TOKEN", exp_detail)

        # ─────────────────────────────────────────────────────────
        # F) Existing gates still fire when authenticating via MCP token
        # ─────────────────────────────────────────────────────────
        print("\n[F] Existing gates still enforce…")

        # F.1 Subscription gate — free-tier user cannot even mint a
        # token, so we hit the gate directly at creation time.
        async with httpx.AsyncClient(timeout=15.0) as c:
            r_free = await c.post(f"{BACKEND_URL}/api/mcp/token",
                                  headers={"Authorization": f"Bearer {ctx['free']['jwt']}",
                                           "Content-Type": "application/json"},
                                  json={"label": "free-should-fail",
                                        "scopes": ["read"],
                                        "expires_in_days": 30})
        _record("F.1 subscription gate still rejects free tier at creation",
                r_free.status_code == 402 and
                r_free.json().get("detail", {}).get("error") == "SUBSCRIPTION_REQUIRED",
                {"status": r_free.status_code})

        # F.2 Trust gate — premium user WITHOUT payment method must
        # still be rejected when a `bid`-scoped token calls place_bid.
        raw_bid_no_pm, _ = await create_scoped_token(
            ctx["premium_no_pm"]["jwt"], scopes=["bid"], label="e2e-nopm-bid")
        resp_f2 = await bridge_exchange(raw_bid_no_pm, [
            {"jsonrpc": "2.0", "id": 50, "method": "tools/call", "params": {
                "name": "place_bid",
                "arguments": {"listing_id": ctx["seed_listing_id"],
                              "bid_amount": 100.0, "user_max_ceiling": 500.0},
            }},
        ])
        r50 = (resp_f2[0] if resp_f2 else {}).get("result", {})
        _record("F.2 trust gate still rejects bid without payment method",
                r50.get("isError") is True,
                (r50.get("content") or [{}])[0].get("text", "")[:120])

        # F.3 Admin-only tool remains admin-only even with matching scope
        raw_analytics, _ = await create_scoped_token(
            ctx["premium_full"]["jwt"], scopes=["analytics"], label="e2e-analytics-only")
        resp_f3 = await bridge_exchange(raw_analytics, [
            {"jsonrpc": "2.0", "id": 60, "method": "tools/call", "params": {
                "name": "identify_top_sellers", "arguments": {"limit": 3},
            }},
        ])
        r60 = (resp_f3[0] if resp_f3 else {}).get("result", {})
        r60_body = json.loads((r60.get("content") or [{}])[0].get("text", "{}")) if r60.get("isError") else {}
        _record("F.3 admin-only remains admin-only for non-admin token",
                r60.get("isError") is True and r60_body.get("error") == "ADMIN_ONLY",
                r60_body)

        # ─────────────────────────────────────────────────────────
        # G) Matchmaker did not send anything / spend / bid / modify.
        # Verify counts against DB state we control.
        # ─────────────────────────────────────────────────────────
        print("\n[G] Matchmaker side-effect guardrails…")
        listing_before = await db.listings.find_one({"id": ctx["seed_listing_id"]})
        # emails_outbox is a canonical email queue used elsewhere in the
        # platform. The matchmaker MUST NOT have enqueued anything.
        outbox_rows = await db.get_collection("email_outbox").count_documents(
            {"to": {"$regex": ctx["buyer_id"]}}) if "email_outbox" in await db.list_collection_names() else 0
        bids_written = await db.bids.count_documents({"listing_id": ctx["seed_listing_id"]})
        auth_rows = await db["b2b_matchmaker_authorisations"].count_documents(
            {"seller_id": ctx["premium_full"]["id"]})

        _record("G.1 no email to buyer emitted by matchmaker",
                outbox_rows == 0)
        _record("G.2 no bid was placed by matchmaker",
                bids_written == 0)
        _record("G.3 listing was NOT modified by matchmaker",
                listing_before is not None and
                listing_before.get("title") == "Iter488 E2E Test Beams 10T" and
                listing_before.get("current_price") == 4500.0)
        # Authorisation rows may exist but must be `dispatched=False`.
        dispatched_any = await db["b2b_matchmaker_authorisations"].count_documents(
            {"seller_id": ctx["premium_full"]["id"], "dispatched": True})
        _record("G.4 no matchmaker authorisation is dispatched",
                dispatched_any == 0 and auth_rows >= 1)

        # ─────────────────────────────────────────────────────────
        # H) Raw token never appears in audit logs
        # ─────────────────────────────────────────────────────────
        print("\n[H] Raw token isolation in audit logs…")
        audit_rows = await db.mcp_audit_logs.find(
            {"user_id": ctx["premium_full"]["id"]}, {"_id": 0}).to_list(500)
        blob = json.dumps(audit_rows, default=str)
        _record("H.1 raw MCP token absent from audit log",
                raw not in blob and secret not in blob)
        # And confirm audit rows DO exist for the calls we made
        matchmaker_audit = [r for r in audit_rows if r.get("tool_name") == "B2B_syndication_matchmaker"]
        _record("H.2 audit rows written for matchmaker calls",
                len(matchmaker_audit) >= 1,
                {"count": len(matchmaker_audit)})

        # ─────────────────────────────────────────────────────────
        # I) `tokens/list` still never returns raw or hash
        # ─────────────────────────────────────────────────────────
        async with httpx.AsyncClient(timeout=15.0) as c:
            r_list = await c.get(f"{BACKEND_URL}/api/mcp/tokens",
                                 headers={"Authorization": f"Bearer {ctx['premium_full']['jwt']}"})
        rows = r_list.json()["tokens"]
        ok = all(("token" not in row) and ("token_hash" not in row) for row in rows)
        _record("I.1 GET /api/mcp/tokens never returns raw or hash", ok,
                {"row_keys_sample": list(rows[0].keys()) if rows else []})

    finally:
        await cleanup(db, ctx)
        mc.close()

    # ═══════════════════════════════════════════════════════════════
    # Report
    # ═══════════════════════════════════════════════════════════════
    REPORT["ended_at"] = datetime.now(timezone.utc).isoformat()
    REPORT["total_checks"] = len(REPORT["checks"])
    REPORT["passed"] = sum(1 for c in REPORT["checks"] if c["passed"])
    REPORT["failed"] = REPORT["total_checks"] - REPORT["passed"]
    out_path = Path("/app/test_reports/iter488_real_claude_e2e.json")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(REPORT, indent=2, default=str))
    print(f"\n=== SUMMARY ===")
    print(f"  Checks: {REPORT['passed']}/{REPORT['total_checks']} passed")
    print(f"  Report: {out_path}")
    if REPORT["defects"]:
        print("  DEFECTS:")
        for d in REPORT["defects"]:
            print(f"    ✗ {d['name']} :: {d['detail']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
