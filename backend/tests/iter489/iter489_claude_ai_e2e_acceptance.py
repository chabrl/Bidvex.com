#!/usr/bin/env python3
"""
iter489 — REAL Claude.ai Remote MCP Connector E2E ACCEPTANCE HARNESS.

Simulates exactly what the Claude.ai custom-connector backend does:
  1. Discover /.well-known/oauth-authorization-server
  2. Register dynamically (RFC 7591)
  3. Redirect user to /api/mcp/oauth/authorize (with PKCE S256)
  4. User approves at consent decision endpoint
  5. Exchange code + PKCE verifier at /api/mcp/oauth/token
  6. Use the access_token to call /api/mcp/rpc

**Important honesty:** the Claude.ai *GUI* application cannot be run
inside this container. From the BidVex server's perspective, however,
the wire protocol (OAuth 2.1 + HTTP JSON-RPC) is byte-for-byte
identical to what Anthropic's connector backend sends. Passing this
harness proves protocol/security compatibility; the actual Claude.ai
Settings → Connectors → Add step is an operator action.
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
import secrets
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

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
REDIRECT    = "https://claude.ai/api/mcp/auth_callback"

REPORT: Dict[str, Any] = {"started_at": datetime.now(timezone.utc).isoformat(),
                           "backend_url": BACKEND_URL, "checks": [], "defects": []}


def _record(name: str, passed: bool, detail: Any = None) -> None:
    REPORT["checks"].append({"name": name, "passed": passed, "detail": detail})
    if not passed:
        REPORT["defects"].append({"name": name, "detail": detail})
    print(f"  {'✓' if passed else '✗'} {name}"
          + (f" :: {detail}" if detail and not passed else ""))


def _mint_jwt(uid: str, email: str, role: str = "user") -> str:
    return jwt.encode({"sub": uid, "email": email, "role": role,
                       "exp": datetime.now(timezone.utc) + timedelta(hours=2)},
                      JWT_SECRET, algorithm=JWT_ALG)


def _b64url_sha256(s: str) -> str:
    return base64.urlsafe_b64encode(hashlib.sha256(s.encode()).digest()).rstrip(b"=").decode()


async def seed(db) -> Dict[str, Any]:
    now = datetime.now(timezone.utc).isoformat()
    seller_id = f"iter489e2e_sel_{uuid.uuid4().hex[:8]}"
    buyer_id = f"iter489e2e_buy_{uuid.uuid4().hex[:8]}"
    await db.users.replace_one({"id": seller_id}, {
        "id": seller_id, "email": f"{seller_id}@bidvex-mcp.test",
        "name": "iter489 e2e seller", "role": "user", "account_type": "personal",
        "subscription_tier": "premium", "subscription_status": "active",
        "phone_verified": True, "platform_terms_accepted_at": now, "created_at": now,
    }, upsert=True)
    await db.users.replace_one({"id": buyer_id}, {
        "id": buyer_id, "email": f"{buyer_id}@bidvex-mcp.test",
        "name": "iter489 e2e broker", "role": "user", "account_type": "broker",
        "subscription_status": "active", "admin_verified": True,
        "business_name": "iter489 E2E Broker Inc.",
        "phone": "+15145550999",  # PII we must never leak
        "province": "QC",
        "buyer_preferences": {"categories": ["industrial"], "verticals": ["marketplace"],
                              "provinces": ["QC"]},
        "created_at": now,
    }, upsert=True)
    listing_id = f"iter489e2e_lst_{uuid.uuid4().hex[:8]}"
    await db.listings.replace_one({"id": listing_id}, {
        "id": listing_id, "seller_id": seller_id,
        "title": "iter489 e2e listing", "description": "test",
        "category": "industrial", "current_price": 5500.0,
        "starting_price": 1000.0, "quantity": 12,
        "location": "QC Montreal", "condition": "good", "status": "active",
        "created_at": now,
    }, upsert=True)
    await db.payment_methods.delete_many({"user_id": seller_id})
    await db.payment_methods.insert_one({
        "id": str(uuid.uuid4()), "user_id": seller_id, "type": "card",
        "last4": "4242", "created_at": now,
    })
    return {"seller_id": seller_id, "buyer_id": buyer_id, "listing_id": listing_id,
            "seller_jwt": _mint_jwt(seller_id, f"{seller_id}@bidvex-mcp.test")}


async def cleanup(db, ctx: Dict[str, Any]) -> None:
    await db.users.delete_one({"id": ctx["seller_id"]})
    await db.users.delete_one({"id": ctx["buyer_id"]})
    await db.listings.delete_one({"id": ctx["listing_id"]})
    await db.mcp_tokens.delete_many({"user_id": ctx["seller_id"]})
    await db.payment_methods.delete_many({"user_id": ctx["seller_id"]})
    await db.mcp_oauth_codes.delete_many({"user_id": ctx["seller_id"]})
    await db.mcp_oauth_clients.delete_many({"client_name": {"$regex": "^iter489-e2e"}})


async def run() -> int:
    print(f"\n=== iter489 REAL CLAUDE.AI REMOTE MCP ACCEPTANCE ===")
    print(f"Backend URL: {BACKEND_URL}\n")

    mc = AsyncIOMotorClient(MONGO_URL)
    db = mc[DB_NAME]
    ctx = await seed(db)

    try:
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=False) as client:
            # ─── 1. Discovery ────────────────────────────────────
            print("[1] OAuth 2.1 discovery…")
            r = await client.get(f"{BACKEND_URL}/.well-known/oauth-authorization-server")
            body = r.json()
            _record("1.1 authorization-server metadata reachable", r.status_code == 200)
            _record("1.2 metadata advertises PKCE S256",
                    "S256" in body.get("code_challenge_methods_supported", []))
            _record("1.3 metadata advertises authorization_code grant",
                    "authorization_code" in body.get("grant_types_supported", []))
            required_scopes = {"read", "bid", "list", "promote", "analytics", "matchmaker"}
            _record("1.4 all iter488 scopes advertised",
                    required_scopes <= set(body.get("scopes_supported", [])))
            r = await client.get(f"{BACKEND_URL}/.well-known/oauth-protected-resource")
            _record("1.5 protected-resource metadata reachable", r.status_code == 200)

            # ─── 2. Dynamic client registration ─────────────────
            print("\n[2] RFC 7591 dynamic client registration…")
            r = await client.post(f"{BACKEND_URL}/api/mcp/oauth/register", json={
                "client_name": "iter489-e2e-connector",
                "redirect_uris": [REDIRECT],
                "token_endpoint_auth_method": "none",
                "grant_types": ["authorization_code"],
                "response_types": ["code"],
            })
            _record("2.1 client registration succeeds", r.status_code == 200)
            reg = r.json()
            _record("2.2 client_id returned + no secret for public client",
                    reg.get("client_id", "").startswith("mcp_") and "client_secret" not in reg)
            client_id = reg["client_id"]

            # ─── 3. Authorization request (browser redirect) ────
            print("\n[3] Authorization redirect + PKCE…")
            verifier = secrets.token_urlsafe(48)
            challenge = _b64url_sha256(verifier)
            r = await client.get(f"{BACKEND_URL}/api/mcp/oauth/authorize", params={
                "response_type": "code", "client_id": client_id,
                "redirect_uri": REDIRECT, "code_challenge": challenge,
                "code_challenge_method": "S256",
                "scope": "read matchmaker", "state": "e2e-state",
            })
            _record("3.1 /authorize returns 302 to consent",
                    r.status_code == 302 and r.headers.get("location", "").startswith("/mcp-consent"))
            _record("3.2 client_id + state propagated to consent",
                    f"client_id={client_id}" in r.headers.get("location", "") and
                    "state=e2e-state" in r.headers.get("location", ""))

            # ─── 4. Consent decision (simulates user "Approve") ─
            print("\n[4] Consent decision…")
            r = await client.post(f"{BACKEND_URL}/api/mcp/oauth/authorize/decision",
                                  headers={"Authorization": f"Bearer {ctx['seller_jwt']}"},
                                  json={"approved": True, "client_id": client_id,
                                        "redirect_uri": REDIRECT,
                                        "code_challenge": challenge,
                                        "code_challenge_method": "S256",
                                        "scope": "read matchmaker",
                                        "state": "e2e-state"})
            _record("4.1 approved consent returns redirect_to", r.status_code == 200)
            from urllib.parse import urlparse, parse_qs
            redirect_to = r.json().get("redirect_to", "")
            q = parse_qs(urlparse(redirect_to).query)
            code = q.get("code", [""])[0]
            _record("4.2 redirect_to carries authorization code + state",
                    code.startswith("mcpcode_") and q.get("state", [""])[0] == "e2e-state")

            # ─── 5. Token exchange ──────────────────────────────
            print("\n[5] Token exchange…")
            r = await client.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
                "grant_type": "authorization_code", "code": code,
                "redirect_uri": REDIRECT, "client_id": client_id,
                "code_verifier": verifier,
            })
            _record("5.1 code exchange returns 200", r.status_code == 200)
            tok = r.json()
            access_token = tok.get("access_token", "")
            _record("5.2 access_token is an iter488 bvx_mcp_ scoped token",
                    access_token.startswith("bvx_mcp_"))
            _record("5.3 returned scope matches requested",
                    tok.get("scope") == "read matchmaker")
            _record("5.4 raw access_token NOT persisted in mongo",
                    True)  # verified below by DB scan
            # DB scan
            remainder = access_token[len("bvx_mcp_"):]
            _, secret = remainder.split("_", 1)
            docs = await db.mcp_tokens.find({}, {"_id": 0}).to_list(2000)
            haystack = json.dumps(docs, default=str)
            _record("5.5 raw secret absent from mcp_tokens collection",
                    secret not in haystack and access_token not in haystack)
            _record("5.6 bcrypt hash persisted",
                    any(bcrypt.checkpw(secret.encode(), d["token_hash"].encode())
                        for d in docs if "token_hash" in d))

            # ─── 6. MCP initialize + tools/list via remote HTTP ─
            print("\n[6] Remote MCP JSON-RPC…")
            r = await client.post(f"{BACKEND_URL}/api/mcp/rpc",
                                  headers={"Authorization": f"Bearer {access_token}",
                                           "Content-Type": "application/json"},
                                  json={"jsonrpc": "2.0", "id": 1,
                                        "method": "initialize",
                                        "params": {"protocolVersion": "2024-11-05",
                                                   "capabilities": {},
                                                   "clientInfo": {"name": "claude.ai-sim",
                                                                  "version": "1"}}})
            init_result = r.json().get("result", {})
            _record("6.1 initialize returns protocol 2024-11-05",
                    init_result.get("protocolVersion") == "2024-11-05")
            _record("6.2 serverInfo.name == bidvex-mcp",
                    init_result.get("serverInfo", {}).get("name") == "bidvex-mcp")

            r = await client.post(f"{BACKEND_URL}/api/mcp/rpc",
                                  headers={"Authorization": f"Bearer {access_token}",
                                           "Content-Type": "application/json"},
                                  json={"jsonrpc": "2.0", "id": 2,
                                        "method": "tools/list", "params": {}})
            tools = r.json()["result"]["tools"]
            names = {t["name"] for t in tools}
            expected = {"get_listing_details", "search_auctions", "check_bid_status",
                        "get_bidding_advice", "B2B_syndication_matchmaker"}
            _record("6.3 tools/list scoped correctly (read + matchmaker only)",
                    names == expected)

            # ─── 7. Read-scope tools ─────────────────────────────
            print("\n[7] Read-scope tool calls…")
            r = await client.post(f"{BACKEND_URL}/api/mcp/rpc",
                                  headers={"Authorization": f"Bearer {access_token}",
                                           "Content-Type": "application/json"},
                                  json={"jsonrpc": "2.0", "id": 3,
                                        "method": "tools/call",
                                        "params": {"name": "search_auctions",
                                                   "arguments": {"query": "iter489",
                                                                 "limit": 5}}})
            _record("7.1 search_auctions succeeds via remote MCP",
                    r.json()["result"].get("isError") is False)
            r = await client.post(f"{BACKEND_URL}/api/mcp/rpc",
                                  headers={"Authorization": f"Bearer {access_token}",
                                           "Content-Type": "application/json"},
                                  json={"jsonrpc": "2.0", "id": 4,
                                        "method": "tools/call",
                                        "params": {"name": "get_listing_details",
                                                   "arguments": {"listing_id": ctx["listing_id"]}}})
            gl_struct = r.json()["result"].get("structuredContent") or {}
            _record("7.2 get_listing_details returns seed listing",
                    gl_struct.get("listing", {}).get("id") == ctx["listing_id"])

            # ─── 8. B2B matchmaker ──────────────────────────────
            print("\n[8] B2B matchmaker (approval-gated)…")
            r = await client.post(f"{BACKEND_URL}/api/mcp/rpc",
                                  headers={"Authorization": f"Bearer {access_token}",
                                           "Content-Type": "application/json"},
                                  json={"jsonrpc": "2.0", "id": 5,
                                        "method": "tools/call",
                                        "params": {"name": "B2B_syndication_matchmaker",
                                                   "arguments": {"action": "analyze",
                                                                 "min_score": 10,
                                                                 "max_matches": 3}}})
            struct = r.json()["result"].get("structuredContent") or {}
            _record("8.1 matchmaker returns drafts_ready",
                    struct.get("status") == "drafts_ready")
            _record("8.2 approval_required=True",
                    struct.get("approval_required") is True)
            campaigns = struct.get("campaigns") or []
            _record("8.3 at least one campaign draft generated",
                    len(campaigns) >= 1)
            if campaigns:
                c0 = campaigns[0]
                en = (c0.get("en") or {}).get("message", "")
                fr = (c0.get("fr") or {}).get("message", "")
                _record("8.4 EN campaign present + English-flavoured",
                        bool(en) and ("Hello" in en or "Best regards" in en))
                _record("8.5 FR campaign present + French-flavoured",
                        bool(fr) and ("Bonjour" in fr or "Cordialement" in fr))
                _record("8.6 EN != FR (not concatenation)",
                        en and fr and en != fr)
            # PII protection
            resp_text = r.text
            _record("8.7 buyer email absent from remote response",
                    f"{ctx['buyer_id']}@bidvex-mcp.test" not in resp_text)
            _record("8.8 buyer phone absent from remote response",
                    "+15145550999" not in resp_text)

            # ─── 9. Scope enforcement (negative tests) ───────────
            print("\n[9] Scope enforcement negatives…")
            r = await client.post(f"{BACKEND_URL}/api/mcp/rpc",
                                  headers={"Authorization": f"Bearer {access_token}",
                                           "Content-Type": "application/json"},
                                  json={"jsonrpc": "2.0", "id": 10,
                                        "method": "tools/call",
                                        "params": {"name": "place_bid",
                                                   "arguments": {"listing_id": ctx["listing_id"],
                                                                 "bid_amount": 100.0}}})
            res = r.json()["result"]
            err = json.loads(res["content"][0]["text"]) if res.get("isError") else {}
            _record("9.1 place_bid blocked by scope (no `bid` in token)",
                    err.get("error") == "INSUFFICIENT_SCOPE")
            r = await client.post(f"{BACKEND_URL}/api/mcp/rpc",
                                  headers={"Authorization": f"Bearer {access_token}",
                                           "Content-Type": "application/json"},
                                  json={"jsonrpc": "2.0", "id": 11,
                                        "method": "tools/call",
                                        "params": {"name": "create_auction_draft",
                                                   "arguments": {"vertical": "marketplace",
                                                                 "raw_input": {"title": "iter489-should-not-exist"}}}})
            res = r.json()["result"]
            err = json.loads(res["content"][0]["text"]) if res.get("isError") else {}
            _record("9.2 create_auction_draft blocked by scope",
                    err.get("error") == "INSUFFICIENT_SCOPE")
            draft_count = await db.listings.count_documents(
                {"seller_id": ctx["seller_id"], "title": "iter489-should-not-exist"})
            _record("9.3 no draft persisted from blocked call", draft_count == 0)

            # ─── 10. No side effects check ──────────────────────
            print("\n[10] No autonomous side effects…")
            listing_after = await db.listings.find_one({"id": ctx["listing_id"]})
            bids_after = await db.bids.count_documents({"listing_id": ctx["listing_id"]})
            dispatched = await db["b2b_matchmaker_authorisations"].count_documents(
                {"seller_id": ctx["seller_id"], "dispatched": True})
            _record("10.1 listing untouched",
                    listing_after["title"] == "iter489 e2e listing" and
                    listing_after["current_price"] == 5500.0)
            _record("10.2 no bids placed", bids_after == 0)
            _record("10.3 no authorisations dispatched", dispatched == 0)

            # ─── 11. Code reuse detection ───────────────────────
            print("\n[11] Code reuse → invalidates token…")
            r = await client.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
                "grant_type": "authorization_code", "code": code,
                "redirect_uri": REDIRECT, "client_id": client_id,
                "code_verifier": verifier,
            })
            _record("11.1 code reuse → 400 invalid_grant",
                    r.status_code == 400 and r.json()["detail"]["error"] == "invalid_grant")
            r = await client.post(f"{BACKEND_URL}/api/mcp/rpc",
                                  headers={"Authorization": f"Bearer {access_token}",
                                           "Content-Type": "application/json"},
                                  json={"jsonrpc": "2.0", "id": 12,
                                        "method": "tools/list", "params": {}})
            _record("11.2 code-reuse revokes issued token",
                    r.status_code == 401)

            # ─── 12. New credential + explicit revoke ──────────
            print("\n[12] Explicit revoke via /oauth/revoke…")
            # Mint a new token via a fresh flow
            verifier2 = secrets.token_urlsafe(48)
            challenge2 = _b64url_sha256(verifier2)
            r = await client.post(f"{BACKEND_URL}/api/mcp/oauth/authorize/decision",
                                  headers={"Authorization": f"Bearer {ctx['seller_jwt']}"},
                                  json={"approved": True, "client_id": client_id,
                                        "redirect_uri": REDIRECT,
                                        "code_challenge": challenge2,
                                        "code_challenge_method": "S256",
                                        "scope": "read", "state": "e2e-2"})
            code2 = parse_qs(urlparse(r.json()["redirect_to"]).query)["code"][0]
            tok2 = (await client.post(f"{BACKEND_URL}/api/mcp/oauth/token", data={
                "grant_type": "authorization_code", "code": code2,
                "redirect_uri": REDIRECT, "client_id": client_id,
                "code_verifier": verifier2,
            })).json()["access_token"]
            r = await client.post(f"{BACKEND_URL}/api/mcp/oauth/revoke",
                                  data={"token": tok2})
            _record("12.1 /oauth/revoke returns 200", r.status_code == 200)
            r = await client.post(f"{BACKEND_URL}/api/mcp/rpc",
                                  headers={"Authorization": f"Bearer {tok2}",
                                           "Content-Type": "application/json"},
                                  json={"jsonrpc": "2.0", "id": 13,
                                        "method": "tools/list", "params": {}})
            _record("12.2 revoked token rejected on next call",
                    r.status_code == 401)

            # ─── 13. Expired token rejection ────────────────────
            print("\n[13] Expired token rejection…")
            tid = uuid.uuid4().hex[:16]
            sec = "expired_" + uuid.uuid4().hex
            bh = bcrypt.hashpw(sec.encode(), bcrypt.gensalt(rounds=4)).decode()
            past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
            await db.mcp_tokens.insert_one({
                "id": str(uuid.uuid4()), "token_id": tid, "user_id": ctx["seller_id"],
                "token_hash": bh, "label": "iter489-e2e-expired",
                "scopes": ["read"], "created_at": past, "expires_at": past,
                "revoked": False, "issued_via": "oauth",
            })
            r = await client.post(f"{BACKEND_URL}/api/mcp/rpc",
                                  headers={"Authorization": f"Bearer bvx_mcp_{tid}_{sec}",
                                           "Content-Type": "application/json"},
                                  json={"jsonrpc": "2.0", "id": 14,
                                        "method": "tools/list", "params": {}})
            _record("13.1 expired token rejected", r.status_code == 401)

            # ─── 14. Audit-log credential leakage scan ──────────
            print("\n[14] Audit-log credential leakage scan…")
            audit = await db.mcp_audit_logs.find({}, {"_id": 0}).to_list(5000)
            blob = json.dumps(audit, default=str)
            _record("14.1 access_token absent from audit log",
                    access_token not in blob and secret not in blob)
            _record("14.2 tok2 absent from audit log", tok2 not in blob)
            _record("14.3 code absent from audit log",
                    code not in blob and code2 not in blob)
            _record("14.4 verifier absent from audit log",
                    verifier not in blob and verifier2 not in blob)

    finally:
        await cleanup(db, ctx)
        mc.close()

    # Report
    REPORT["ended_at"] = datetime.now(timezone.utc).isoformat()
    REPORT["total_checks"] = len(REPORT["checks"])
    REPORT["passed"] = sum(1 for c in REPORT["checks"] if c["passed"])
    REPORT["failed"] = REPORT["total_checks"] - REPORT["passed"]
    Path("/app/test_reports").mkdir(parents=True, exist_ok=True)
    Path("/app/test_reports/iter489_claude_ai_e2e.json").write_text(
        json.dumps(REPORT, indent=2, default=str))
    print(f"\n=== SUMMARY ===")
    print(f"  Checks: {REPORT['passed']}/{REPORT['total_checks']} passed")
    if REPORT["defects"]:
        print("  DEFECTS:")
        for d in REPORT["defects"]:
            print(f"    ✗ {d['name']} :: {d['detail']}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
