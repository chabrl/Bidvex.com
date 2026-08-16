# BidVex MCP Server — Integration Guide (iter485 + iter486)

**Status:** Preview/Staging only. Registered under `MCP_ENABLED=true`.
**Version:** iter486 (Claude Desktop end-to-end integration, 2026-02-17)
**Files:** `backend/mcp_server.py`, `backend/mcp_bridge.py`
**Mount paths (when enabled):**
- `POST /api/mcp/rpc`                      — JSON-RPC 2.0 (used by stdio bridge, internal callers)
- `GET  /api/mcp/sse` + `POST /api/mcp/sse/messages?sid=<id>` — MCP HTTP-SSE transport
- `POST /api/mcp/tools/list`               — Legacy REST (iter485 backwards-compat)
- `POST /api/mcp/tools/call`               — Legacy REST (iter485 backwards-compat)
- `GET  /api/mcp/health`                   — Public liveness probe

The MCP server is an **additive** layer that exposes a fixed set of
BidVex marketplace operations as Claude-callable tools. It does **not**
duplicate any business logic — every tool wraps existing internal
services (bid handler, trust gate, fee calculator, market comparables,
top-sellers analytics, Meta Ads publisher). Deleting the two MCP files
leaves the rest of the platform behavior unchanged.

---

## 1. Transports

| Transport            | Endpoint / Path                                      | Used by                             |
|----------------------|------------------------------------------------------|-------------------------------------|
| **stdio**            | `backend/mcp_bridge.py` subprocess                   | Claude Desktop (native)             |
| **HTTP JSON-RPC**    | `POST /api/mcp/rpc`                                  | The bridge; other backend services  |
| **HTTP-SSE**         | `GET /api/mcp/sse` + `POST /api/mcp/sse/messages`    | `mcp-remote`, Claude Web, external clients |
| **Legacy REST**      | `POST /api/mcp/tools/{list,call}`                    | iter485 tests + internal callers (kept for backwards-compat) |

All four surfaces share the same tool implementations, gates, and
audit-log path. The MCP-compliance surface lives entirely in
`_dispatch_jsonrpc()`; transports differ only in how they wrap
requests/responses.

---

## 2. Claude Desktop configuration (drop-in)

Save this as your `claude_desktop_config.json`
(`~/Library/Application Support/Claude/claude_desktop_config.json` on
macOS, `%APPDATA%\Claude\claude_desktop_config.json` on Windows):

```json
{
  "mcpServers": {
    "bidvex": {
      "command": "python",
      "args": [
        "/absolute/path/to/backend/mcp_bridge.py"
      ],
      "env": {
        "BIDVEX_MCP_URL": "https://your-bidvex-host.example.com",
        "BIDVEX_MCP_JWT": "eyJhbGciOiJIUzI1NiJ9..."
      }
    }
  }
}
```

- **`BIDVEX_MCP_URL`** — base URL of your BidVex backend (no trailing
  slash; the bridge appends `/api/mcp/rpc`).
- **`BIDVEX_MCP_JWT`** — a BidVex JWT for the caller. Obtain from
  `POST /api/auth/login` and paste here. The bridge does not implement
  a login flow — Claude Desktop clients are authenticated as the user
  whose JWT is configured.

To rotate the token: replace the string, restart Claude Desktop. The
bridge is stateless.

### Alternative: connect a remote MCP client via SSE

If you want to connect **without installing the bridge locally** (e.g.
Claude Web or `mcp-remote`), use the SSE transport:

```json
{
  "mcpServers": {
    "bidvex": {
      "command": "npx",
      "args": [
        "mcp-remote",
        "https://your-bidvex-host.example.com/api/mcp/sse",
        "--header", "Authorization: Bearer eyJhbGciOi..."
      ]
    }
  }
}
```

The server advertises the message-post endpoint on first connect;
`mcp-remote` handles the rest.

---

## 3. Authentication flow

1. The caller obtains a BidVex JWT via `/api/auth/login` /
   `/api/auth/register`. The MCP server does **not** issue tokens.
2. The bridge (or SSE client) attaches `Authorization: Bearer <jwt>`
   to every request to the backend.
3. The JWT is validated by the same `deps.get_current_user` FastAPI
   dependency the rest of the backend uses (HS256 against
   `JWT_SECRET`, checks user still exists, checks not expired).
4. On failure the response is `401 Unauthorized`; nothing is written
   to the audit log because we don't yet know the user id.

---

## 4. Subscription access gate

The MCP server is available **only** to accounts on an active annual
paid subscription. The gate is enforced on **every** JSON-RPC and REST
call.

| Condition                   | Field(s) checked                                                                                                    |
|-----------------------------|--------------------------------------------------------------------------------------------------------------------|
| Premium / VIP / Partner Pro | `subscription_tier ∈ {"premium","vip","partner_pro"}` AND `subscription_status == "active"`                        |
| Vehicle Dealer              | `is_vehicle_dealer == true` AND `dealer_subscription_status == "active"` AND `dealer_subscription_active == true`  |
| Broker                      | `account_type == "broker"` AND `subscription_status == "active"`                                                   |
| Storage Facility            | `account_type == "storage_facility"` AND `facility_verified == true` AND `subscription_status == "active"`         |
| Admin / super_admin (ops)   | `role ∈ {"admin","super_admin"}`                                                                                   |

Failure response (**HTTP 402**, JSON-RPC error `-32001`):
```json
{
  "jsonrpc": "2.0", "id": <n>,
  "error": {
    "code":    -32001,
    "message": "SUBSCRIPTION_REQUIRED",
    "data":    { "error": "SUBSCRIPTION_REQUIRED", "message_en": "…", "message_fr": "…", "upgrade_url": "/pricing" }
  }
}
```

Field names were verified against the live `users` collection before
this gate was written; nothing is hardcoded from documentation-only.

---

## 5. Verification gate (per-tool)

Bid + listing-creation tools apply a second gate after the subscription
check.

### Base gate
Reuses `services.trust_gate.require_trust_verified` — same rules that
gate the REST bid endpoint:
- `phone_verified == true`
- Caller has ≥ 1 row in the `payment_methods` collection (Stripe card
  on file)
- `platform_terms_accepted_at` is set on the user record

Failure: HTTP 403 with `{"error": "trust_required", "missing": [...] }`.

### Corporate/seller tax verification (create-listing tools only)
On top of the base gate, `create_auction_draft` and
`bulk_create_listings` additionally require **verified Seller Tax ID**
per vertical:

| Account shape                          | Required in addition to `tax_id != ""` |
|----------------------------------------|----------------------------------------|
| `is_vehicle_dealer == true`            | `dealer_license_verified == true`     |
| `account_type == "storage_facility"`   | `facility_verified == true`           |
| `account_type ∈ {"broker","business"}` | `admin_verified == true`              |
| `account_type == "personal"`           | Any non-empty `tax_id` string         |

---

## 6. Rate limiting — Redis-backed with in-memory fallback

- **Scope**: per-JWT-subject (`sub` claim = user id).
- **Window**: sliding 60 seconds.
- **Limit**: `MCP_RATE_LIMIT_PER_MIN` env var (default **30 / minute**).
- **Backend selection** (in order):
  1. **Redis** — configured via `REDIS_URL`, keyed as `mcp:rl:<user_id>`,
     stored as a ZSET with the timestamp as the score. State survives
     backend restart.
  2. **In-process bucket** — automatic fallback when Redis is unreachable
     or `REDIS_URL` is unset. State is per-process and lost on restart.
- **Fail-open safety**: any exception in either backend falls open — a
  limiter bug can never wedge a legitimate caller. On a Redis error the
  cached client is dropped so the next call re-probes.

Successful responses include `_meta.rate_limit_remaining` in the tool
call payload:
```json
"_meta": { "rate_limit_remaining": 27 }
```

Exceeded (**HTTP 429 or JSON-RPC isError=true**):
```json
{
  "error":            "RATE_LIMIT_EXCEEDED",
  "limit_per_minute": 30,
  "retry_after_s":    60,
  "backend":          "redis"    // or "memory"
}
```

---

## 7. Audit logging

Every tool invocation — success, failure, or rejected — writes exactly
one row to the **`mcp_audit_logs`** collection. Audit-write failures
never impact the user's flow (logged at WARNING and swallowed).

### Schema
```jsonc
{
  "id":            "<uuid>",
  "source":        "mcp_claude",           // fixed constant
  "user_id":       "<caller's id>",
  "tool_name":     "<tool>",               // e.g. "place_bid"
  "input_params":  { … sanitized args … }, // see §8
  "timestamp":     "<ISO-8601 UTC>",
  "result_status": "success" | "failure" | "rejected",
  "error_code":    "<short error code>",   // null on success
  "latency_ms":    45
}
```

`result_status` semantics:
- `success`   — handler returned a value; audit written before response.
- `rejected`  — 4xx (user-facing validation, gate, or rate limit).
- `failure`   — 5xx (internal / infra error).

---

## 8. Secret sanitization

`_sanitize()` recursively rewrites any dict key matching this pattern
before the row hits `mcp_audit_logs`:

```
/(password|secret|token|api[_-]?key|access[_-]?key|refresh|
  card_?number|cvv|cvc|pan|iban|routing|authorization|cookie|jwt)/i
```

…and any **value** matching a known secret shape (Stripe live/test
keys, webhook secrets, restricted keys, AWS keys, `Bearer …`):

```
/^(sk_(live|test)_|rk_(live|test)_|whsec_|pk_live_|pk_test_|
   AKIA[0-9A-Z]{16}|Bearer\s+[A-Za-z0-9._\-]+)/
```

Keys are redacted as `<redacted:key>`, matching values as
`<redacted:value>`. Deep nesting is capped at 6 levels. Strings > 1000
chars are truncated to 1000 + `"…<truncated>"`. Lists cap at 50 items.

Failure responses never include `str(exc)` in the client body — only a
short error code (`INTERNAL_ERROR`). This is guarded by
`test_source_does_not_import_or_touch_stripe_secrets` at import time.

---

## 9. Tool catalogue (13 tools)

Full input schemas are also served by `tools/list` (self-describing).

### Bidding & Marketplace

- **`search_auctions`** *(new, iter486)* — Search across all four verticals
  (`marketplace | lots | vehicle | storage`). Filters: `query`, `vertical`,
  `category`, `min_price`, `max_price`, `status`, `limit`. Query text is
  regex-escaped server-side via `services.sanitizer.safe_regex`. Returns
  per-vertical result groups so callers can render them separately.
- **`get_listing_details(listing_id)`** — Full public listing document
  across all four verticals; strips obviously private fields (`internal_notes`,
  `admin_notes`, seller stripe id). This is the **broader BidVex** tool and
  is intentionally NOT renamed to `get_lot_details`.
- **`place_bid(listing_id, bid_amount, user_max_ceiling?)`** — Bids via HTTP
  loopback to the existing `POST /api/bids` handler; snipe protection,
  minimum increment, deposit, watchdog moderation, and notifications all
  fire unchanged. **Rejects (400 `BID_EXCEEDS_MAX_CEILING`)** when
  `bid_amount > user_max_ceiling` — never silently capped.
- **`create_auction_draft(vertical, raw_input)`** — Persists a
  `status="draft"` document; publishing remains an explicit separate
  action. Additional gate: corporate tax verification.
- **`bulk_create_listings(items[])`** — Iterates `create_auction_draft`;
  cap 500 items. Verifies tax up front to avoid partial writes.
- **`check_bid_status(listing_id, user_id?, lot_number?)`** — Caller's
  bid standing on a listing (winning/outbid/won/ended/no_bids + position).

### Marketing & Creative

- **`publish_meta_ad_promotion(listing_id, budget_cap_cents, duration_days)`**
  — Wraps `services.ads_publisher.publish_to_meta_sync`. Hard rails:
  budget cap ≤ $100k lifetime, duration 1–30 days, caller must own
  listing. Returns `NOT_IMPLEMENTED` when Meta env is not provisioned.
- **`generate_listing_video(listing_id)`** — **STUB** — Higgsfield not
  provisioned → `NOT_IMPLEMENTED / higgsfield_not_provisioned`.

### Analytics & Advice

- **`get_bidding_advice(listing_id)`** — Market comparables via
  `services.chat_listing_context.fetch_market_comparables`. Data only.
- **`analyze_seller_inventory(seller_id?)`** — Read-only aggregation
  across all four verticals. Non-admin scoped to own inventory.
- **`detect_performance_bottlenecks(seller_id?, listing_id?)`** —
  Flags actives with < 25% of same-category median views.
- **`identify_top_sellers(limit=5)`** — Admin only.
  Wraps `services.top_sellers.compute_top_sellers`.
- **`B2B_syndication_matchmaker(seller_id, manifest_raw_data)`** —
  **STUB** — `NOT_IMPLEMENTED / b2b_matchmaker_phase_2` + TARGET INTENT
  comment block preserved in handler source.

---

## 10. What this MCP server does **NOT** touch

The scope of iter485 + iter486 is deliberately narrow:

- ❌ No changes to any existing REST route or route file (except the
  ~14-line opt-in mount block in `server.py` behind `MCP_ENABLED`).
- ❌ No changes to `services/fee_calculator.py`, `services/tax_engine.py`,
  or any commission/tax calculator.
- ❌ No changes to Stripe integration code (no new Stripe API calls
  are made by the MCP layer — bids reuse the existing bid handler
  which owns Stripe interactions).
- ❌ No changes to the Gemini watchdog / moderation pipeline.
- ❌ No changes to escrow, deposits, auction lifecycle, or payout
  logic.
- ❌ No modifications to `trust_gate`, subscription gates, tax-ID
  gates, audit log format, or any authorization primitive.
- ❌ No Higgsfield or B2B matchmaker business logic invented — both
  are declared stubs that return `NOT_IMPLEMENTED`.
- ❌ **NO PRODUCTION DEPLOYMENT.** Preview only per user command.

---

## 11. Enabling in preview / disabling

**Preview** (`/app/backend/.env`):
```
MCP_ENABLED=true

# Optional — omit to use in-process rate limiter only
REDIS_URL=rediss://user:pass@host:6379/0

# Optional — override default 30/min
# MCP_RATE_LIMIT_PER_MIN=60
```

Then `sudo supervisorctl restart backend`. Health check:
```
curl http://localhost:8001/api/mcp/health
# {"status":"ok","protocol":"mcp-http","tool_count":13}
```

**Disable**: remove or set `MCP_ENABLED=false`. The router is imported
conditionally in `server.py` — flipping the flag off unmounts the
router at next backend restart.

---

## 12. Testing

Two test files cover the complete surface:

### `backend/tests/iter482/test_mcp_server.py` — 18 tests (iter485)

Access gates + audit + sanitizer + legacy REST endpoints.

### `backend/tests/iter482/test_mcp_jsonrpc_transport.py` — 10 tests (iter486)

| Test                                                                    | Verifies                                                             |
|-------------------------------------------------------------------------|----------------------------------------------------------------------|
| `test_jsonrpc_initialize_returns_valid_serverinfo`                      | `initialize` returns `protocolVersion`, `serverInfo`, `capabilities` |
| `test_jsonrpc_notifications_initialized_returns_202`                    | Notifications receive no response body (per MCP spec)                |
| `test_jsonrpc_ping_ok`                                                  | `ping` returns empty result                                          |
| `test_jsonrpc_tools_list_shape_matches_mcp_spec`                        | `inputSchema` camelCase, no `input_schema` leakage, all 13 tools present |
| `test_full_workflow_search_details_bid_via_jsonrpc`                     | `search_auctions` → `get_listing_details` → `place_bid` end-to-end   |
| `test_place_bid_ceiling_rejection_via_jsonrpc`                          | `bid_amount > ceiling` → `isError=true` with `BID_EXCEEDS_MAX_CEILING` |
| `test_stdio_bridge_subprocess_roundtrip`                                | Spawns `mcp_bridge.py`, exchanges 3 JSON-RPC msgs over stdin/stdout  |
| `test_sse_transport_endpoint_and_message_roundtrip`                     | Full SSE handshake: open GET → endpoint event → POST → SSE response  |
| `test_redis_limiter_persistence`                                        | Fake Redis state SURVIVES simulated backend restart                  |
| `test_redis_outage_falls_back_to_memory`                                | Redis unreachable → limiter transparently uses in-memory bucket      |

Run:
```
cd /app/backend && python -m pytest tests/iter482/test_mcp_server.py tests/iter482/test_mcp_jsonrpc_transport.py -v
# 28 passed
```

---

## 13. Files created / modified

**Created:**
- `backend/mcp_server.py`                                    — MCP server + tool handlers + JSON-RPC + SSE
- `backend/mcp_bridge.py`                                    — stdio bridge (Claude Desktop launcher)
- `backend/tests/iter482/test_mcp_server.py`                 — iter485 gate & audit tests (18)
- `backend/tests/iter482/test_mcp_jsonrpc_transport.py`      — iter486 protocol & transport tests (10)
- `docs/MCP_INTEGRATION.md`                                  — this document

**Modified (opt-in only):**
- `backend/server.py`                                        — ~14 lines behind `MCP_ENABLED` flag
- `backend/.env`                                             — added `MCP_ENABLED=true` (preview only)
- `backend/requirements.txt`                                 — added `fakeredis==2.37.0` + `sortedcontainers==2.4.0` (test dependency only)

**Not modified:**
- Any existing REST route, tool business logic, gate primitive
  (`trust_gate`, subscription, tax-id checks), audit-log format,
  Stripe integration, fee/tax calculator, watchdog, escrow, or
  auction lifecycle code.
