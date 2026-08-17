# iter489 — BidVex Remote MCP Connector for Claude.ai

**PREVIEW ONLY — NO DEPLOYMENT PERFORMED · Feb 18, 2026**

Adds a standards-compliant OAuth 2.1 authorization server that lets
Claude.ai (and any other MCP client speaking the "custom remote
connector" protocol) authenticate against BidVex without exposing the
user's session JWT — while reusing the entire iter488 scoped-token
security stack unchanged.

---

## Architecture

```
Claude.ai (web)
     ↓ 1. discover /.well-known/oauth-authorization-server
     ↓ 2. dynamic client registration (RFC 7591)
     ↓ 3. browser redirect → /api/mcp/oauth/authorize (PKCE S256)
     ↓ 4. user approves scopes on /mcp-consent React page
     ↓ 5. 302 back to Claude.ai with ?code=…
     ↓ 6. Claude.ai backend exchanges code + PKCE at /api/mcp/oauth/token
     ↓ 7. server mints iter488 scoped MCP token — RETURNS IT AS access_token
     ↓ 8. Claude.ai → POST /api/mcp/rpc with Bearer <bvx_mcp_...>
             ↓ (unchanged) _resolve_user_or_mcp_token → existing gates → tools

Claude Desktop (iter488 path — untouched):
   stdio → mcp_bridge.py → POST /api/mcp/rpc (Bearer <bvx_mcp_...>)
```

Key property: **the OAuth access token IS an iter488 scoped MCP token.**
There is no second token store. Every existing property (bcrypt hashing,
scope filtering, revocation, expiration, audit sanitisation,
subscription gate, trust gate, admin gate) applies without modification.

---

## Endpoints

### Discovery (public, unauthenticated)
| Path                                            | Purpose                                 |
| :---------------------------------------------- | :-------------------------------------- |
| `GET /.well-known/oauth-authorization-server`   | RFC 8414 authorization-server metadata  |
| `GET /.well-known/oauth-protected-resource`     | RFC 9728 protected-resource metadata    |

### OAuth 2.1 flow
| Path                                       | Auth               | Purpose                       |
| :----------------------------------------- | :----------------- | :---------------------------- |
| `POST /api/mcp/oauth/register`             | public             | RFC 7591 dynamic registration |
| `GET  /api/mcp/oauth/authorize`            | none (browser)     | RFC 6749 §4.1 start           |
| `POST /api/mcp/oauth/authorize/decision`   | session JWT        | consent approve/deny          |
| `POST /api/mcp/oauth/token`                | client (+ PKCE)    | code → access token           |
| `POST /api/mcp/oauth/revoke`               | none (token=auth)  | RFC 7009 revocation           |
| `GET  /api/mcp/oauth/clients/{client_id}`  | public             | read-only client metadata     |

### MCP transports (reused from iter488 — unchanged)
| Path                            | Notes                              |
| :------------------------------ | :--------------------------------- |
| `POST /api/mcp/rpc`             | JSON-RPC 2.0 (used by Claude.ai)   |
| `GET  /api/mcp/sse`             | HTTP-SSE transport (iter486)       |
| `POST /api/mcp/sse/messages`    | SSE messaging endpoint             |

---

## Security invariants (all held)

- **PKCE S256 mandatory.** No `plain` challenge, no missing verifier.
- **Authorization codes single-use.** Code reuse returns
  `invalid_grant` AND **revokes the previously issued token** per
  RFC 6819 §5.2.1.1.
- **Redirect URI binding.** The URI at `/token` MUST match the one
  presented at `/authorize`.
- **Client-secret bcrypt-hashed.** No plain-text secrets.
- **Scope allowlist.** OAuth requests are filtered against iter488's
  `{read, bid, list, promote, analytics, matchmaker}`. `admin` cannot
  be self-granted; the admin gate remains role-based.
- **Subscription gate at consent time.** Free-tier users cannot mint
  OAuth-issued tokens.
- **Zero token duplication.** OAuth `access_token` is an iter488
  scoped MCP token (`bvx_mcp_…`). Revoking either surface revokes the
  same underlying record.
- **Audit sanitisation.** `access_token`, `client_secret`, PKCE
  verifier, and authorization codes are never persisted to the audit
  log (verified by automated tests).

---

## Test coverage — iter489 delta

| Suite                                                                | Tests |
| :------------------------------------------------------------------- | :---: |
| `tests/iter489/test_mcp_oauth.py` — OAuth flow + PKCE + revocation   |  22   |
| `tests/iter489/test_mcp_remote_transport.py` — MCP over HTTP + scope |  17   |
| `tests/iter489/iter489_claude_ai_e2e_acceptance.py` — E2E harness    |  45   |
| **iter489 subtotal**                                                 | **84**|

### Regression (iter488 baseline preserved)
| Suite                                             | Tests | Status |
| :------------------------------------------------ | :---: | :----: |
| `tests/iter488/test_mcp_tokens.py`                |  25   |   ✓    |
| `tests/iter488/test_b2b_matchmaker.py`            |  19   |   ✓    |
| `tests/iter482/test_mcp_server.py`                |  18   |   ✓    |
| `tests/iter482/test_mcp_jsonrpc_transport.py`     |  10   |   ✓    |
| `tests/iter482/test_mcp_tool_descriptions.py`     |   5   |   ✓    |
| iter488 stdio bridge acceptance harness           |  34   |   ✓    |
| **iter488 baseline maintained**                   | **111**| ✓     |

**Total across iter488 + iter489: 195 checks green, 0 regressions.**

---

## Claude.ai operator instructions

1. Open **claude.ai**.
2. Go to **Settings → Connectors**.
3. Click **Add custom connector**.
4. Fill in:
    - **Name:** `BidVex`
    - **Remote MCP server URL:** `<your bidvex origin>/api/mcp/rpc`
      (available on Settings → Connect Claude → "Connect Claude.ai
      (Web)" card in BidVex)
5. Click **Connect**. Claude.ai will:
    - Discover `/.well-known/oauth-authorization-server`.
    - Dynamically register itself (no manual client-id needed).
    - Redirect your browser to `/mcp-consent?...` (BidVex).
6. **Approve** the requested scopes on the BidVex consent page.
7. You are returned to Claude.ai — connector shows as **Connected**.
8. In a new Claude conversation, enable the BidVex connector.
9. Try a harmless read-only query, e.g. *"List BidVex tools"* or
   *"Search BidVex for active listings."*

### First test (recommended)
- Do **not** ask Claude to place a bid or authorise a matchmaker
  campaign during the first acceptance test.
- Read-only queries prove protocol correctness without touching real
  data.

---

## Environment variables

**No new required env vars.** iter489 is fully additive.

Optional overrides:
| Variable                    | Effect                                                              |
| :-------------------------- | :------------------------------------------------------------------ |
| `REMOTE_MCP_PUBLIC_URL`     | Override the origin advertised in discovery metadata (e.g. behind a proxy). Defaults to `FRONTEND_URL` if set, else the request's own base URL. |

---

## Claude.ai GUI status

**Not proven from these tests.** The server-side wire-protocol acceptance
harness (`iter489_claude_ai_e2e_acceptance.py`) uses the exact HTTP
message sequence Anthropic's Claude.ai connector backend sends, but a
real Claude.ai *client* connection requires:

1. The operator opening Claude.ai in a real browser.
2. Adding the connector via **Settings → Connectors → Add custom connector**.
3. Completing the OAuth flow in that browser.

That final step is an operator action.

---

## Files changed (additive)

**New backend:**
- `backend/routes/mcp_oauth.py`
- `backend/tests/iter489/__init__.py`
- `backend/tests/iter489/test_mcp_oauth.py`
- `backend/tests/iter489/test_mcp_remote_transport.py`
- `backend/tests/iter489/iter489_claude_ai_e2e_acceptance.py`

**New frontend:**
- `frontend/src/pages/McpConsentPage.jsx`

**Additive edits (no removals, no behavioural changes):**
- `backend/server.py` — mount OAuth router + `.well-known` metadata (+~55 lines).
- `frontend/src/App.js` — register `/mcp-consent` route + lazy import (+3 lines).
- `frontend/src/components/ConnectClaudeSection.jsx` — add "Connect
  Claude.ai (Web)" card + Globe icon import (+~85 lines).

**Untouched (per spec):**
- `backend/mcp_server.py` — MCP JSON-RPC dispatch, tool registry, gates,
  Redis limiter, audit format.
- `backend/mcp_bridge.py` — Claude Desktop stdio bridge.
- `backend/routes/mcp_tokens.py` — iter488 scoped-token endpoints.
- `backend/services/b2b_matchmaker.py` — matchmaker business logic.
- All auction / bidding / payment / Stripe / tax / settlement / escrow /
  fee logic.
