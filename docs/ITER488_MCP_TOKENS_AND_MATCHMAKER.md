# iter488 — Scoped MCP Tokens + B2B Matchmaker Phase 2 (Feb 2026)

**PREVIEW ONLY · DO NOT DEPLOY**

This document supplements `MCP_INTEGRATION.md` for iter488 additions.
No existing MCP behavior was changed — every new surface is additive.

---

## 1. Scoped MCP Token System

### Overview
Users can now generate **scoped MCP tokens** to connect Claude Desktop
(or any MCP client) to their BidVex account without exposing their
session JWT.

- Tokens live in the new `mcp_tokens` collection.
- Raw token is returned **exactly once** at creation and never persisted.
- Only the bcrypt hash of the token's secret is stored.
- Token permissions can never exceed the user's actual permissions.
- Every existing MCP gate (subscription / trust / tax-ID / admin /
  rate limit / audit log) continues to apply unchanged.

### API endpoints
All endpoints require a valid session JWT.

| Method | Path                          | Purpose                                              |
| :----- | :---------------------------- | :--------------------------------------------------- |
| POST   | `/api/mcp/token`              | Create a new scoped token (returns raw token once).  |
| GET    | `/api/mcp/tokens`             | List the caller's tokens (metadata only).            |
| DELETE | `/api/mcp/token/{token_id}`   | Revoke a token immediately (owner or admin only).    |

### Token format
```
bvx_mcp_<token_id (16 hex chars)>_<secret (secrets.token_urlsafe(32))>
```
Only the `token_id` is used to locate the record in MongoDB (bcrypt
hashes are salted so we can't query by hash). Bcrypt verification is
performed against the stored `token_hash`.

### Allowed scopes
The scope allowlist is **coarse and deliberate**:

| Scope        | Tools it unlocks                                                        |
| :----------- | :---------------------------------------------------------------------- |
| `read`       | `get_listing_details`, `search_auctions`, `check_bid_status`, `get_bidding_advice` |
| `bid`        | `place_bid` (still enforces trust gate)                                 |
| `list`       | `create_auction_draft`, `bulk_create_listings` (still enforces tax-ID gate) |
| `promote`    | `publish_meta_ad_promotion`, `generate_listing_video`                   |
| `analytics`  | `analyze_seller_inventory`, `detect_performance_bottlenecks`, `identify_top_sellers` (admin-only remains admin-only) |
| `matchmaker` | `B2B_syndication_matchmaker`                                            |

Admin capability is deliberately **not** grantable by tokens; it flows
only from `user.role`. Even a token that requests `admin` in its scopes
list will have that entry silently stripped by the allowlist.

### Claude Desktop configuration
After the raw token is generated, the settings page displays a
ready-to-copy JSON snippet:
```json
{
  "mcpServers": {
    "bidvex": {
      "command": "python",
      "args": ["/absolute/path/to/backend/mcp_bridge.py"],
      "env": {
        "BIDVEX_MCP_URL": "https://your-bidvex.example.com",
        "BIDVEX_MCP_JWT": "<newly generated MCP token>"
      }
    }
  }
}
```
The existing `mcp_bridge.py` script accepts either a session JWT or an
MCP token in `BIDVEX_MCP_JWT`. No bridge changes were required.

### End-to-end acceptance test (proven Feb 2026)
1. Generate token via `POST /api/mcp/token` → raw returned once.
2. Set `BIDVEX_MCP_URL` + `BIDVEX_MCP_JWT`, launch stdio bridge.
3. `initialize` handshake → protocol 2024-11-05.
4. `tools/list` → returns only the tools inside the token's scopes.
5. `tools/call` → succeeds for in-scope tools, returns
   `INSUFFICIENT_SCOPE` for out-of-scope tools.
6. `DELETE /api/mcp/token/{id}` → immediate revocation.
7. Any subsequent bridge call → `INVALID_MCP_TOKEN` (401).

---

## 2. B2B Matchmaker Phase 2

Replaces the Phase-1 `NOT_IMPLEMENTED` stub while preserving the tool
name `B2B_syndication_matchmaker` for backward compatibility.

### Pipeline
```
seller inventory → manifest parser → buyer clustering → match scoring
                → explainable reasons → bilingual EN/FR campaign drafts
                → REQUIRES EXPLICIT APPROVAL → audit
```

### Guarantees (never violated)
- **No autonomous emails.** The service does not send anything.
- **No advertising spend.** The service does not create paid campaigns.
- **No listing modifications, bids, or financial commitments.**
- **No PII leakage.** Buyer output is limited to `user_id`, optional
  `business_name`, coarse `segment`, and non-PII signals.
- **Approval is a hard gate.** The `authorise` action records the
  intent in `b2b_matchmaker_authorisations` and returns
  `authorized_pending_dispatch` — actual dispatch is deferred to Ops
  and is never triggered automatically.

### MCP tool interface
```jsonc
{
  "name": "B2B_syndication_matchmaker",
  "arguments": {
    "action": "analyze",          // or "authorise"
    "seller_id": "<optional>",    // defaults to caller (admin may override)
    "min_score": 30,              // 0..100
    "max_matches": 20,            // 1..100
    "campaign_id": "<required for authorise>",
    "explicit_authorization": true  // must be true to authorise
  }
}
```

### Buyer segments
A "qualified" B2B buyer is any user matching at least one of:
- `is_vehicle_dealer=True` AND `vehicle_dealer_verified=True`
- `account_type in {"broker","storage_facility","business"}` AND
  (`subscription_status="active"` OR `admin_verified=True` OR
  `facility_verified=True`)

### Match scoring (explainable, 0–100)
| Component                       | Points |
| :------------------------------ | :----: |
| Vertical / asset-type match     |   25   |
| Category match                  |   20   |
| Geography (province)            |   15   |
| Price-range fit                 |   15   |
| Quantity-range fit              |   10   |
| Historical bidding signal       |   10   |
| Condition preference            |    5   |

Every point contribution is emitted as an explicit `reasons` array
so the campaign draft can render the rationale to a human.

### Campaign drafts
Bilingual EN + FR drafts are generated **independently**:
- English uses natural greetings ("Hello", "Best regards, the BidVex team").
- French uses natural greetings ("Bonjour", "Cordialement, l'équipe BidVex").
- Neither is mechanical concatenation nor a translation of the other.

---

## 3. Regression coverage

| Suite                                                     | Tests |
| :-------------------------------------------------------- | :---: |
| `tests/iter488/test_mcp_tokens.py`                        |  22   |
| `tests/iter488/test_b2b_matchmaker.py`                    |  22   |
| `tests/iter482/test_mcp_server.py`                        |  18   |
| `tests/iter482/test_mcp_jsonrpc_transport.py`             |  10   |
| `tests/iter482/test_mcp_tool_descriptions.py`             |   5   |
| **Total**                                                 |  77   |

Existing iter482 P6.2 + security-hardening suites (`27 tests`) remain
untouched and continue passing.

---

## 4. Guardrails held

- **No existing JWT behavior changed.**
- **No existing MCP tool handler business logic changed.**
- **No auction / bidding / payment / Stripe / tax / settlement /
  escrow / fee logic changed.**
- **All existing trust/subscription/tax-ID/admin gates continue to
  fire even when authenticating with an MCP token.**
- **Raw MCP tokens are never persisted or logged.**
- **B2B Matchmaker does not autonomously contact buyers, spend money,
  place bids, or modify listings.**
- **Preview only — no deploy.**
