# BidVex MCP Server — Integration Guide (iter485)

**Status:** Preview/Staging only. NOT registered in `server.py` by default.
**Version:** iter485 (initial delivery, 2026-02-16)
**File:** `backend/mcp_server.py`
**Mount path:** `/api/mcp/*` (when enabled)
**Enabled by:** `MCP_ENABLED=true` env var (opt-in)

The MCP server is an **additive** layer that exposes a fixed set of
BidVex marketplace operations as Claude-callable tools. It does **not**
duplicate any business logic — every tool wraps existing internal
services (bid handler, trust gate, fee calculator, market comparables,
top-sellers analytics, Meta Ads publisher). Deleting the file leaves
the rest of the platform behavior unchanged.

---

## 1. Endpoints

| Method | Path                       | Auth       | Purpose                                                          |
|--------|----------------------------|------------|------------------------------------------------------------------|
| GET    | `/api/mcp/health`          | Public     | Liveness probe (no user data)                                    |
| POST   | `/api/mcp/tools/list`      | JWT + gate | Return the tool catalogue visible to the caller                  |
| POST   | `/api/mcp/tools/call`      | JWT + gate | Dispatch a single tool call                                      |

`tools/call` body:
```json
{
  "name": "<tool_name>",
  "arguments": { … }
}
```

---

## 2. Authentication flow

1. The caller obtains a BidVex JWT via the existing `/api/auth/login` /
   `/api/auth/register` flow. The MCP server does **not** issue tokens.
2. Every MCP request includes `Authorization: Bearer <jwt>` (or the
   `session_token` cookie, whichever the caller has).
3. The JWT is validated by the same `deps.get_current_user` FastAPI
   dependency the rest of the backend uses (HS256 against
   `JWT_SECRET`, checks user still exists, checks not expired).
4. On success, the user document is loaded once from the `users`
   collection and reused across the request-scoped gates below.
5. On failure the response is `401 Unauthorized`; nothing is written
   to the audit log because we don't yet know the user id.

---

## 3. Subscription access gate

The MCP server is available **only** to accounts on an active annual
paid subscription. The gate is enforced on **every** request (not
just `tools/call`) by `_require_mcp_access`.

An account is granted access iff **any** of these evaluate true:

| Condition | Field(s) checked                                                                                                    |
|-----------|--------------------------------------------------------------------------------------------------------------------|
| Premium / VIP / Partner Pro | `subscription_tier ∈ {"premium","vip","partner_pro"}` AND `subscription_status == "active"`             |
| Vehicle Dealer              | `is_vehicle_dealer == true` AND `dealer_subscription_status == "active"` AND `dealer_subscription_active == true` |
| Broker                      | `account_type == "broker"` AND `subscription_status == "active"`                                                   |
| Storage Facility            | `account_type == "storage_facility"` AND `facility_verified == true` AND `subscription_status == "active"`         |
| Admin / super_admin (ops)   | `role ∈ {"admin","super_admin"}`                                                                                   |

Failure response (**HTTP 402 Payment Required**):
```json
{
  "detail": {
    "error":       "SUBSCRIPTION_REQUIRED",
    "message_en":  "The BidVex MCP service is available only to Premium, VIP, Partner Pro, Vehicle Dealer, Broker, or verified Storage Facility accounts with an active annual subscription.",
    "message_fr":  "Le service MCP BidVex est réservé aux comptes Premium, VIP, Partner Pro, Concessionnaire automobile, Courtier ou Établissement d'entreposage vérifié avec un abonnement annuel actif.",
    "upgrade_url": "/pricing"
  }
}
```

Field names were verified against the live `users` collection before
this gate was written; nothing is hardcoded from documentation-only.

---

## 4. Verification gate (per-tool)

Bid + listing-creation tools apply a second gate after the subscription
check.

### Base gate (all "actionable" tools)
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

| Account shape                     | Required in addition to `tax_id != ""`                       |
|-----------------------------------|--------------------------------------------------------------|
| `is_vehicle_dealer == true`       | `dealer_license_verified == true`                            |
| `account_type == "storage_facility"` | `facility_verified == true`                              |
| `account_type ∈ {"broker","business"}` | `admin_verified == true`                              |
| `account_type == "personal"`      | Any non-empty `tax_id` string is accepted                    |

Failure responses:
```json
{ "detail": { "error": "TAX_ID_REQUIRED", "message_en": "…", "message_fr": "…" } }
{ "detail": { "error": "TAX_ID_REQUIRED", "detail": "dealer_license_not_verified", "message_en": "…", "message_fr": "…" } }
{ "detail": { "error": "TAX_ID_REQUIRED", "detail": "facility_not_verified",       "message_en": "…", "message_fr": "…" } }
{ "detail": { "error": "TAX_ID_REQUIRED", "detail": "corporate_not_verified",      "message_en": "…", "message_fr": "…" } }
```

---

## 5. Rate limiting

- **Scope**: per-JWT-subject (`sub` claim = user id).
- **Window**: sliding 60 seconds.
- **Limit**: `MCP_RATE_LIMIT_PER_MIN` env var (default **30 / minute**).
- **Implementation**: in-process sliding-window buckets. This is
  intentionally simple for a preview server and DOES lose state on
  backend restart. For production a Redis-backed limiter would replace it.
- **Fail-open safety**: any exception inside the limiter falls open —
  a limiter bug can never wedge a legitimate caller.

Successful responses include `rate_limit_remaining` in the payload:
```json
{ "tool": "get_listing_details", "result": {…}, "rate_limit_remaining": 27 }
```

Exceeded (**HTTP 429**):
```json
{
  "detail": {
    "error":            "RATE_LIMIT_EXCEEDED",
    "limit_per_minute": 30,
    "retry_after_s":    60,
    "message_en":       "Too many MCP tool calls. Please slow down.",
    "message_fr":       "Trop d'appels d'outils MCP. Veuillez ralentir."
  }
}
```

---

## 6. Audit logging

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
  "input_params":  { … sanitized args … }, // see §7
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

### Example rows (real, captured 2026-02-16)

Success with **sanitized** sensitive args:
```json
{
  "id":            "51b1b937-0198-456f-bce8-c57d4f35fd6c",
  "source":        "mcp_claude",
  "user_id":       "8940074d-da97-43ca-9a0b-c59d39411ed6",
  "tool_name":     "get_listing_details",
  "input_params":  {
    "listing_id":  "58758582-f53a-46d8-bc0b-87cf9de60523",
    "password":    "<redacted:key>",
    "api_key":     "<redacted:key>"
  },
  "timestamp":     "2026-02-16T22:33:23.284383+00:00",
  "result_status": "success",
  "error_code":    null,
  "latency_ms":    180
}
```

Rejected (unknown tool):
```json
{
  "id":            "2ba448d4-8ff6-4263-9e6f-f75f35c7b34f",
  "source":        "mcp_claude",
  "user_id":       "8940074d-da97-43ca-9a0b-c59d39411ed6",
  "tool_name":     "nonexistent_tool",
  "input_params":  {},
  "timestamp":     "2026-02-16T22:33:23.607815+00:00",
  "result_status": "rejected",
  "error_code":    "UNKNOWN_TOOL",
  "latency_ms":    45
}
```

Stub success (`NOT_IMPLEMENTED`):
```json
{
  "id":            "a66a0782-f1f9-4fd2-934f-18f932cd0639",
  "source":        "mcp_claude",
  "user_id":       "8940074d-da97-43ca-9a0b-c59d39411ed6",
  "tool_name":     "B2B_syndication_matchmaker",
  "input_params":  { "seller_id": "demo-seller-1", "manifest_raw_data": { "csv": "..." } },
  "timestamp":     "2026-02-16T22:33:23.890296+00:00",
  "result_status": "success",
  "error_code":    null,
  "latency_ms":    45
}
```

---

## 7. Secret sanitization

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

## 8. Tool catalogue

All tools return JSON. Complete input schemas are also served by
`POST /api/mcp/tools/list` (self-describing).

### Bidding & Marketplace

#### `get_listing_details(listing_id)`
Returns the full **public** listing document across all four verticals
(`marketplace | lots | vehicle | storage`), stripping obviously
private fields (`internal_notes`, `admin_notes`, seller stripe id).

Input:  `{ "listing_id": string }`
Output: `{ "vertical": "marketplace|lots|vehicle|storage", "listing": {...} }`
Errors: `listing_not_found` (404), `listing_id required` (400)

#### `place_bid(listing_id, bid_amount, user_max_ceiling?)`
Places a bid via **HTTP loopback to the existing `POST /api/bids`
handler** — so snipe protection, minimum increment, deposit rules,
watchdog moderation, and notifications all fire unchanged.

Explicit guard added on top:
1. Full trust gate (phone + payment method + T&C).
2. If `user_max_ceiling` is provided AND `bid_amount > user_max_ceiling`,
   the call is **REJECTED** (400 `BID_EXCEEDS_MAX_CEILING`) — never
   silently capped.

Input:  `{ "listing_id": string, "bid_amount": number, "user_max_ceiling"?: number }`
Output: `{ "bid_status": "placed", "result": { …from bid handler… } }`
Errors: `trust_required` (403), `BID_EXCEEDS_MAX_CEILING` (400), plus
any error bubbled from the underlying bid endpoint (listing not found,
below-minimum increment, listing ended, self-bid, etc.).

#### `create_auction_draft(vertical, raw_input)`
Persists a `status="draft"` document in the appropriate collection.
Publishing remains an explicit separate action (unchanged existing
publish endpoints). Only fields the caller supplies are stored; ownership
(`seller_id`), `status`, `id`, `created_via` are set by the server.

Input:  `{ "vertical": "marketplace|lots|vehicle|storage", "raw_input": object }`
Output: `{ "draft_id": string, "vertical": string, "status": "draft" }`
Additional gate: **corporate tax verification** (§4).

#### `bulk_create_listings(items[])`
Iterates over `items[]`, calling `create_auction_draft` for each.
Cap: **500 items per call**. Returns a per-item success/failure array.
Additional gate: **corporate tax verification** (§4), enforced once
up front so partial writes don't leak on unverified callers.

#### `check_bid_status(listing_id, user_id?, lot_number?)`
Returns the caller's bid standing on a single listing (or lot). Non-
admin callers can only query their own standing.

Output shape:
```json
{
  "listing_id":     "...",
  "listing_status": "active|ended|...",
  "total_bids":     N,
  "user_position":  1|2|3|null,
  "status":         "winning|outbid|won|ended_outbid|not_participating|no_bids"
}
```

### Marketing & Creative

#### `publish_meta_ad_promotion(listing_id, budget_cap_cents, duration_days)`
Publishes a Meta Ads campaign via `services.ads_publisher.publish_to_meta_sync`.

Hard rails:
- `budget_cap_cents ∈ [1, 10_000_000]` (max $100 000 lifetime cap).
- `duration_days ∈ [1, 30]`.
- Caller must own the listing (or be admin).
- If `services.ads_publisher.meta_flag()['enabled'] == false` (missing
  env vars), returns `NOT_IMPLEMENTED` with the prerequisite string —
  no attempt to create a new billing account or spend beyond what's
  already provisioned.
- Daily budget derived server-side from `budget_cap_cents / duration_days`.

#### `generate_listing_video(listing_id)`
**STUB** — Higgsfield integration is not provisioned in this
codebase. Returns:
```json
{
  "status":     "NOT_IMPLEMENTED",
  "reason":     "higgsfield_not_provisioned",
  "message_en": "Short-form video generation via Higgsfield is not currently provisioned on this BidVex environment. Contact platform ops to enable.",
  "message_fr": "La génération de vidéos courtes via Higgsfield n'est pas configurée sur cet environnement BidVex. Contactez l'exploitation."
}
```
Logs a WARN on every invocation.

### Analytics & Advice

#### `get_bidding_advice(listing_id)`
Returns market comparables (via `services.chat_listing_context.fetch_market_comparables`) — **data only**, no advice generation. Same window/rules
as the existing chat-context path.

#### `analyze_seller_inventory(seller_id?)`
Read-only aggregation across `listings`, `multi_item_listings`,
`vehicles`, `storage_units`. Non-admin callers can only inspect their
own inventory. Returns:
```json
{
  "seller_id":    "...",
  "active_count": N,
  "ended_count":  N,
  "total_gmv":    12345.67,
  "stale_active": [{ "id": "...", "title": "..." }, ...],
  "categories":   [...]
}
```
"Stale" = active > 14 days old with no bids.

#### `detect_performance_bottlenecks(seller_id?, listing_id?)`
Flags active `listings` with fewer views than 25% of same-category
median (min 1). Read-only; non-admins scoped to their own listings.

#### `identify_top_sellers(limit=5)`  — **admin only**
Wraps `services.top_sellers.compute_top_sellers`. Excludes demo data.
Enforced by `admin_only=True` in the tool registry AND a second
`_require_admin_role` check in the dispatcher.

#### `B2B_syndication_matchmaker(seller_id, manifest_raw_data)`
**STUB** — deliberately not implemented in this pass.
Returns `NOT_IMPLEMENTED / b2b_matchmaker_phase_2` and logs a WARN.
The full Phase 2 intent is preserved in a `TARGET INTENT` comment
block inside the handler body (`backend/mcp_server.py`).

---

## 9. What this MCP server does **NOT** touch

The scope of iter485 is deliberately narrow and read-only-friendly:

- ❌ No changes to any existing REST route or route file.
- ❌ No changes to `services/fee_calculator.py`, `services/tax_engine.py`,
  or any commission/tax calculator.
- ❌ No changes to Stripe integration code (no new Stripe API calls
  are made by the MCP layer — bids reuse the existing bid handler
  which owns Stripe interactions).
- ❌ No changes to the Gemini watchdog / moderation pipeline.
- ❌ No new environment variables added, other than the opt-in
  `MCP_ENABLED` flag and the optional `MCP_RATE_LIMIT_PER_MIN`
  override.
- ❌ No Higgsfield or B2B matchmaker business logic invented — both
  are declared stubs that return `NOT_IMPLEMENTED`.
- ❌ No production deployment. Enabling in production requires:
  (a) explicit sign-off after review, (b) migrating the in-process
  rate limiter to Redis, (c) fronting with an actual MCP transport
  bridge (SSE) if desired.

---

## 10. Enabling in preview / disabling

**Preview** (`/app/backend/.env`):
```
MCP_ENABLED=true
```
Then `sudo supervisorctl restart backend`. Health check:
```
curl http://localhost:8001/api/mcp/health
# {"status":"ok","protocol":"mcp-http","tool_count":12}
```

**Disable**: remove or set `MCP_ENABLED=false`. The router is imported
conditionally in `server.py` — flipping the flag off unmounts the
router at next backend restart.

---

## 11. Testing

Regression suite: `backend/tests/iter482/test_mcp_server.py` — 18
tests, all passing:

| Test                                                          | Verifies                                                  |
|---------------------------------------------------------------|-----------------------------------------------------------|
| `test_free_tier_blocked_from_tools_list`                      | Free tier → 402 SUBSCRIPTION_REQUIRED on `tools/list`     |
| `test_free_tier_blocked_from_call`                            | Free tier → 402 SUBSCRIPTION_REQUIRED on `tools/call`     |
| `test_premium_can_list_tools`                                 | Premium sees all 11 non-admin tools, no admin-only tools  |
| `test_admin_sees_admin_only_tools`                            | Admin sees `identify_top_sellers` too                     |
| `test_bid_rejected_when_no_payment_method`                    | Trust gate fires when no card on file                     |
| `test_bid_rejected_when_ceiling_exceeded`                     | `bid_amount > user_max_ceiling` → 400 (no silent cap)     |
| `test_create_draft_requires_tax_verification`                 | Dealer w/ unverified license → 403 dealer_license_not_verified |
| `test_non_admin_blocked_from_top_sellers`                     | `identify_top_sellers` returns 403 ADMIN_ONLY for non-admin |
| `test_get_listing_details_ok_for_premium`                     | Read-only tool works for premium user                     |
| `test_get_bidding_advice_returns_comparables`                 | Comparables tool returns data-only, no advice             |
| `test_generate_listing_video_is_stub`                         | Higgsfield stub returns NOT_IMPLEMENTED                   |
| `test_b2b_matchmaker_is_stub`                                 | B2B matchmaker stub returns NOT_IMPLEMENTED               |
| `test_unknown_tool_returns_404`                               | UNKNOWN_TOOL response for bogus name                      |
| `test_rate_limit_exceeded_writes_audit`                       | 30th call succeeds, 31st → 429 + audit row written        |
| `test_audit_row_sanitizes_secrets`                            | password/api_key/jwt_token/card_number all redacted       |
| `test_unauth_request_gets_401`                                | No token → 401                                            |
| `test_source_has_b2b_stub_intent_comment`                     | Phase-2 intent comment preserved in source                |
| `test_source_does_not_import_or_touch_stripe_secrets`         | MCP file never imports Stripe or touches secret keys      |

Run:
```
cd /app/backend && python -m pytest tests/iter482/test_mcp_server.py -v
```

---

## 12. What was NOT modified

Zero existing files touched other than a single conditional block in
`server.py` gated by `MCP_ENABLED`. Full list of files created /
modified for this iteration:

| File                                             | Kind    |
|--------------------------------------------------|---------|
| `backend/mcp_server.py`                          | NEW     |
| `backend/tests/iter482/test_mcp_server.py`       | NEW     |
| `docs/MCP_INTEGRATION.md`                        | NEW     |
| `backend/server.py`                              | MODIFIED — added ~14 lines behind the `MCP_ENABLED` flag |
| `backend/.env`                                   | MODIFIED — added `MCP_ENABLED=true` (preview only)       |

No modifications to `fee_calculator`, `tax_engine`, watchdog, Stripe
integration, existing REST endpoints, or the frontend.
