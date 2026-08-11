# iter468 – iter473 · Release-Readiness Audit (Read-Only)

**Prepared**: Feb, 2026
**Scope**: iter468, iter469, iter470, iter470-UI, iter471, iter472, iter473
**Mode**: READ-ONLY. No code, secrets, data, emails, payouts, or production configuration were touched. **No deploy performed.**
**Preview backend URL** (frontend REACT_APP_BACKEND_URL host): `prod-verify-2.preview.emergentagent.com`

Every "PASS" cited below is grounded in either (a) a static code path inspection, (b) an existing test report in `/app/test_reports/`, or (c) a pytest that runs entirely in-process with a Mongo fake and performs no writes/emails/transfers. No live-write verification scripts were re-executed.

---

## 1) Financial-Document Email Links — Absolute HTTPS Guarantee

### 1.1 Resolver source (`backend/services/cloud_storage.py`)

```
generate_signed_url(invoice_id, expiry_seconds=3600, base_url="")
    effective_base = (base_url or _resolve_public_base_url() or "").rstrip("/")
    return f"{effective_base}/api/invoices/download/{invoice_id}?expires=…&sig=…"

_resolve_public_base_url():
    precedence → PUBLIC_BASE_URL → APP_URL → FRONTEND_URL → REACT_APP_BACKEND_URL
    reject: blank | non-http(s) scheme | contains 'localhost' | contains '127.0.0.1' | contains '0.0.0.0'
```

### 1.2 Callers (14 total) — all rely on the resolver (no `base_url` override)

| Location | Line | Caller |
|---|---|---|
| `services/final_document_delivery.py` | 89 | buyer final invoice link |
| `services/final_document_delivery.py` | 149 | seller settlement link |
| `routes/invoices.py` | 784, 1041, 1196, 1243, 1345, 1456, 1569, 1933 | invoice / seller receipt / commission / payment-letter / transaction download |
| `tests/live_qa_iter472_document_delivery.py` | 138 | QA harness (previously verified) |
| `tests/live_verify_iter473_absolute_url.py` | 126, 260 | QA harness (previously verified) |

**Finding**: every production caller relies on the resolver — no hardcoded / relative / mocked base is ever passed.

### 1.3 Static & previously-verified evidence

Source of truth: `/app/test_reports/iter473_absolute_url_qa.json` (previously verified).

| Category | Result |
|---|---|
| T1a PUBLIC_BASE_URL wins over APP_URL | ✅ PASS |
| T1b falls back to APP_URL | ✅ PASS |
| T1c skips `localhost` → next var | ✅ PASS |
| T1d skips `127.0.0.1` | ✅ PASS |
| T1e skips non-http(s) scheme | ✅ PASS |
| T1f returns empty when no host configured | ✅ PASS |
| T2a–T2e generated URL is absolute HTTPS, no `http:///`, no `localhost`, has `/api/invoices/download/{id}`, has `expires` + `sig` | ✅ PASS (5/5) |
| T3a–T3f emailed hrefs across every {section × lang × role}: present, absolute HTTPS, no `http:///`, no `localhost/127.0.0.1`, has `/api/invoices/download/`, has `expires` + `sig` | ✅ PASS (16 × 6 = 96/96) |
| T4 emailed href click-through → `200 application/pdf` | ✅ PASS (16/16) |
| T5 expired signature returns 401/403/410 (403 observed) | ✅ PASS |
| T6 cross-user forged signature (A's sig on B's id) rejected 403 | ✅ PASS |

**Verdict — Absolute HTTPS Guarantee**: ✅ **PASS**. Emailed financial document links never emit `http:///`, `localhost`, `127.0.0.1`, `0.0.0.0`, blank hosts, non-http(s) schemes, or relative paths. When *no* host is configured the resolver returns empty and logs a warning — no silently-wrong absolute URL is ever emitted.

---

## 2) Preview vs Production URL Resolution

### 2.1 Design (per user correction)

| Environment | Active resolver source | Value |
|---|---|---|
| Preview | `APP_URL` | current preview public host |
| Production | `FRONTEND_URL` | `https://bidvex.com` |
| Optional override | `PUBLIC_BASE_URL` | not required, currently unset |

`REACT_APP_BACKEND_URL` is a **frontend-only** variable and is *not* the backend resolver's active source in either environment. The resolver still lists it as the last fallback for defence in depth.

### 2.2 Current preview `.env` observed variables (values redacted)

`/app/backend/.env` — variable names present:
- `FRONTEND_URL` = *[preview host, scheme=https, valid]*
- `PUBLIC_BASE_URL` — **not defined**
- `APP_URL` — **not defined in .env** (may be injected by the runtime platform)
- `REACT_APP_BACKEND_URL` — **not defined in backend .env** (frontend-only)

**Observation**: with `APP_URL` currently absent from `/app/backend/.env`, the resolver falls through to `FRONTEND_URL`, which today holds the preview public host — so preview links resolve correctly. If Re-publish substitutes `FRONTEND_URL` with `https://bidvex.com` while `APP_URL` remains unset, production links will resolve through `FRONTEND_URL` (production host). Both outcomes are covered by the same resolver, and both currently produce valid absolute HTTPS URLs.

**Verdict — URL Environment Resolution**: ✅ **PASS**. Preview links resolve through a valid preview HTTPS host today. Production links will resolve through `FRONTEND_URL=https://bidvex.com` when Re-publish substitutes the value. `PUBLIC_BASE_URL` remains optional and can be left unset.

---

## 3) Signed-Document Link, EN/FR, Access Rejection Tests

### 3.1 Signed-link resolution / access — previously verified

| Test | Cases | Result | Source |
|---|---|---|---|
| Secure signed link resolves 200 `application/pdf` | 16 | ✅ PASS | `iter472_document_delivery_qa.json` |
| Absolute-HTTPS href click-through | 16 | ✅ PASS | `iter473_absolute_url_qa.json` |
| Expired-signature rejection (403) | 1 | ✅ PASS | `iter473_absolute_url_qa.json` |
| Cross-user forged-signature rejection (403) | 1 | ✅ PASS | `iter473_absolute_url_qa.json` |

### 3.2 EN + FR document rendering — previously verified

| Language | Section | Buyer | Seller |
|---|---|---|---|
| EN | lots | ✅ | ✅ |
| EN | marketplace | ✅ | ✅ |
| EN | vehicles | ✅ | ✅ |
| EN | storage | ✅ | ✅ |
| FR | lots | ✅ | ✅ |
| FR | marketplace | ✅ | ✅ |
| FR | vehicles | ✅ | ✅ |
| FR | storage | ✅ | ✅ |

Sources: `iter472_document_delivery_qa_report.md` §3, `iter473_absolute_url_qa.json` (T3 blocks). All 16 signed hrefs verified absolute HTTPS. Accented FR characters (é, è, ê), CAD comma decimals, and the BidVex Canada wrapper all render as designed.

### 3.3 Dedup — previously verified

`settlement_email_dispatches` ledger — 16/16 dedup scenarios pass; retry never re-emits.

**Verdict — Signed-Link / EN-FR / Access Rejection**: ✅ **PASS** (previously verified; no re-run performed).

---

## 4) Buyer "My Purchases" Completeness

### 4.1 Backend resolver (`routes/dashboard.py` lines 490–730)

```
Authoritative source: db.receipts where type=buyer_receipt AND user_id=me
Dedupe identity:      (section, listing_id, lot_number)
Sections covered:     marketplace | lots | vehicles | storage
Parent-title resolution per section:
  marketplace → listings.title
  lots        → multi_item_listings.lots[k].title / .quantity ; parent=multi_item_listings.title
  vehicles    → vehicle_listings.lots[k].title / .description ; parent=vehicle_listings.title
  storage     → storage_auctions.title
```

Non-paid `listings.winner_user_id` wins are merged after receipt-driven paid rows, guarded by the same dedupe key (`_seen_keys`), so they cannot duplicate a paid receipt row.

### 4.2 Frontend (`frontend/src/pages/BuyerDashboard.js` line 128 → `PurchasesAndReceiptsCard`)

Renders `dashboard.won_items_detail` (paid receipts + unpaid winner rows) and separately fetches `/api/receipts/mine?role=buyer` for the "Receipts" collapsible drawer. Both queries scope to the authenticated buyer.

### 4.3 Coverage matrix

| Purchase type | Receipt row source | Deduped by | Renders |
|---|---|---|---|
| Single-item marketplace | `receipts{type:buyer_receipt, section:marketplace}` | `(marketplace, listing_id, None)` | ✅ |
| Multi-lot (multi_item_listings) | `receipts{type:buyer_receipt, section:lots, lot_number}` | `(lots, listing_id, lot_number)` | ✅ (one row per lot, section-native title + quantity) |
| Vehicle multi-lot | `receipts{type:buyer_receipt, section:vehicles, lot_number}` | `(vehicles, listing_id, lot_number)` | ✅ (one row per lot) |
| Storage | `receipts{type:buyer_receipt, section:storage}` | `(storage, listing_id, None)` | ✅ |
| Unpaid single-item win (pending payment) | `listings.winner_user_id=me` merge | `(section, listing_id, None)` | ✅ (no dup with a paid row) |

Cross-buyer isolation: every read filters by `user_id=current_user.id`. No aggregation runs across buyers.

**Verdict — Buyer My Purchases**: ✅ **PASS** (paid single-item, multi-lot marketplace, vehicle multi-lot, storage all covered; no cross-buyer data; no duplicate rows).

---

## 5) Escrow Pickup Payout-State Safety

### 5.1 Backend (`services/escrow_service.py`)

The confirm-pickup path (both Path A `escrow_transactions` and Path B `transactions`-only fallback) computes:

```
funds_shipped = bool(transfer_id) or payout_state == "sent"
target_status = "released" if funds_shipped else "pickup_confirmed_payout_pending"
```

`_payout_state_response(payout_state, amount_cad, transfer_id)` returns exactly ONE of:

| payout_state | status | transfer_id | UI copy |
|---|---|---|---|
| `sent` (real Stripe transfer id present) | `released` | real id | "Pickup confirmed. Funds have been released." |
| `pending` | `pickup_confirmed_payout_pending` | `None` | "Pickup confirmed. Payout is pending." |
| `failed` | `pickup_confirmed_payout_review` | `None` | "Pickup confirmed. Payout requires review." |
| `unknown` | `pickup_confirmed_payout_review` | `None` | "Pickup confirmed. Payout requires review." |

Path B (transactions-only fallback) is explicit: *"never assume released — consult the payout state and return an accurate message. This path records the pickup confirmation and enforces one-time-use; it does NOT trigger a Stripe transfer and does NOT cancel any pending payout obligation."*

### 5.2 Frontend (`frontend/src/components/EscrowPickupPanel.js`)

Badge configuration (lines 19–95): `payout_state === 'sent'` is the sole predicate for the "Funds Released / Fonds libérés" badge. `pending` → "Payout Pending", `failed` → "Payout Requires Review", `unknown` → "Payout Requires Review". The comment at line 23 is explicit: *"Never show 'Funds Released' unless the backend reports payout_state === 'sent'."*

Toast dispatch (line 181 onward) mirrors: `sent` → success toast; `pending` → info; `failed`/`unknown` → warning. UI can never claim "Funds Released" from a client-side inference.

### 5.3 Unit-test evidence (safe to run — in-process fake Mongo, no writes)

`/app/backend/tests/test_iter469_escrow_pickup_resolver.py` — **13/13 PASS** (re-run in this audit; no live DB, no emails, no Stripe API).

### 5.4 Stripe-transfer proof status

The escrow-release code path is inspected but **not** proven end-to-end against Stripe in this release. The controlled payout verification (`live_verify_iter465_running_escrow_payout.py`) remains **BLOCKED** on Stripe sandbox available balance (see §7). This release is **NOT** to be described as proof that Stripe transfers are verified. What *is* proven: the release will never falsely claim funds are released in the absence of a real `stripe_transfer_id`.

**Verdict — Escrow Payout-State Safety**: ✅ **PASS** on code path + UI presentation. ⚠ **NOT a Stripe-transfer verification** — that remains blocked.

---

## 6) Stripe Key Value Scan — Preview Files & Release Inputs

Scanned patterns: `sk_test_`, `sk_live_`, `rk_test_`, `rk_live_`, `pk_live_`, `pk_test_*`, `whsec_*`.

### 6.1 Source files (would be packaged in a Re-publish)

| File | Type | Classification |
|---|---|---|
| `backend/services/stripe_identity.py` (line 34) | quoted literal | **SENTINEL** — compares to placeholder string `sk_test_emergent` (8-char suffix, used only to detect the pod-env stub) |
| `backend/services/smoke_test_runner.py` (line 163) | quoted literal | **SENTINEL** — same `sk_test_emergent` gate |
| `backend/services/bid_authorization_service.py` (line 57) | quoted literal | **SENTINEL** — same gate |
| `backend/tests/test_iter269_launch_prep.py` (line 70) | quoted literal | **SENTINEL** — same gate |
| `backend/tests/test_stripe_e2e.py` (line 4) | comment/docstring | prefix mention only |
| `backend/tests/e2e_qa_test.py` (line 677, 689) | code comment | prefix mention only |
| `backend/server.py` (lines 35, 37) | code guard | prefix comparison `startswith('sk_live_','sk_test_','rk_')` — no literal value |
| `backend/scripts/verify_stripe_sync.py` (line 15) | docstring example | `sk_live_…` placeholder ellipsis |
| `backend/.env.example` | placeholder | `sk_live_...`, `whsec_...`, `pk_live_...` — documentation placeholders, not values |
| `backend/scripts/iter283_seed_test_listings.py` | **false positive** — token `mark_test` in parameter name matched the substring `sk_test_` |
| `backend/tests/live_verify_iter463_escrow_payout.py` (line 7) | code comment | mentions the sentinel `sk_test_emergent` |

**No real Stripe key value is embedded in any preview source file.** Only the sentinel placeholder `sk_test_emergent` (documented gate) and prefix-mention comments/placeholders were found.

### 6.2 `.env` files (variable names only)

**`/app/backend/.env`** — Stripe/webhook variable names present:
- `STRIPE_WEBHOOK_SECRET`
- `STRIPE_WEBHOOK_SECRET_2`
- `STRIPE_CONNECT_WEBHOOK_SECRET`
- `STRIPE_PUBLISHABLE_KEY`
- `STRIPE_TEST_SECRET_KEY`
- `STRIPE_TEST_PUBLISHABLE_KEY`
- `STRIPE_TEST_WEBHOOK_SECRET`
- `SENDGRID_WEBHOOK_PUBLIC_KEY`

**`/app/frontend/.env`** — Stripe variable name present:
- `REACT_APP_STRIPE_PUBLISHABLE_KEY`

Values were not read, not extracted, and are not reproduced in this report. If the `.env` files are included in the Re-publish package, whatever preview values they currently hold **would be packaged**. The Emergent deploy pipeline typically injects production secrets from a secure secret store at deploy time — but this must be **explicitly verified before Re-publish** (see §8).

### 6.3 Verdict — Secret Scan

- ✅ No real Stripe key literal is embedded in preview source (only the well-known `sk_test_emergent` sentinel, prefix comparisons, and documentation placeholders).
- ⚠ **`.env` files are not release-ready** if the deploy pipeline copies them literally: preview STRIPE_TEST_* and other webhook/publishable-key values would be packaged. Production must inject live values through the platform secret store rather than the preview `.env` file. Values were not inspected or exposed by this audit.

---

## 7) Preview Changes a Normal Re-publish Would Include (iter468 → iter473)

Sourced from `git log` (base = commit immediately before iter468 → HEAD `d23cb04d`).

### 7.1 Backend production code

- `backend/services/cloud_storage.py` *(iter473 — absolute-URL resolver, generate_signed_url)*
- `backend/services/escrow_service.py` *(iter469 canonical resolver + iter470 payout-state safety)*
- `backend/services/payment_collection.py` *(iter468 doc dispatch + iter469 escrow state fallback)*
- `backend/services/final_document_delivery.py` *(iter468 buyer/seller final-document delivery)*
- `backend/services/emails/email_system.py` *(iter468 new emails: buyer final-invoice link, seller settlement link)*
- `backend/services/settlement_email_dedup.py` *(iter468 dedup kinds added)*
- `backend/routes/dashboard.py` *(iter471 unified buyer receipts + dedupe)*
- `backend/routes/webhooks.py` *(iter468 dispatch on confirmed Stripe payment)*
- `backend/routes/invoices.py` *(iter473 download endpoint verification)*

### 7.2 Frontend production code

- `frontend/src/pages/BuyerDashboard.js` *(iter471 PurchasesAndReceiptsCard + won_items_detail merge)*
- `frontend/src/components/EscrowPickupPanel.js` *(iter470-UI payout-state badges, toasts, notices)*

### 7.3 Configuration / metadata / non-code

- `.emergent/emergent.yml` (touched during iter471 / iter472)
- `memory/PRD.md` (every iteration updates this)

### 7.4 Test scripts & reports (bundled in the repo)

- `backend/tests/test_iter469_escrow_pickup_resolver.py` (pytest, in-process fake — safe)
- `backend/tests/live_verify_iter469_escrow_pickup_fix.py` (live, writes — skipped in this audit)
- `backend/tests/live_repro_iter469_escrow_pickup_mismatch.py` (live, writes — skipped)
- `backend/tests/live_verify_iter470_payout_state_safety.py` (live, writes — skipped)
- `backend/tests/seed_iter470_ui_states.py`
- `backend/tests/live_verify_iter471_my_purchases_completeness.py` (live, writes — skipped)
- `backend/tests/seed_iter471_ui_purchases.py`
- `backend/tests/live_qa_iter472_document_delivery.py` (live — previously verified)
- `backend/tests/live_verify_iter473_absolute_url.py` (live — previously verified)
- `test_reports/iter472_document_delivery_qa.json` + `.md`
- `test_reports/iter473_absolute_url_qa.json`
- `test_reports/iter468_473_release_readiness_audit.md` *(this file)*

### 7.5 Unresolved / unverified items carried into the Re-publish

- ⚠ **Controlled Escrow Payout Verification (iter463 / iter465 / iter467)** — BLOCKED on Stripe sandbox available balance. The escrow-release code path is inspected and unit-tested (in-process), but no live Stripe Transfer has been proven end-to-end. This audit does **not** and cannot certify Stripe-transfer parity.
- ⚠ **iter468 secure-link email suppression for marketplace / vehicles / storage** — documented gap G4/G5 in `iter472_document_delivery_qa_report.md`: `_fetch_or_generate_buyer_invoice` currently calls `generate_lots_won_invoice` (multi-item-only) and suppresses with `no_invoice_available` for non-lots sections unless an `invoices` row is pre-seeded. Inline HTML receipts still dispatch correctly for those sections. Deferred per user directive.
- ⚠ **G1–G3 on-demand-only documents** (payment letter, seller receipt, commission invoice) — no auto-email delivery. Deferred per user directive.
- ⚠ **Storage seller commission invoice** — inline HTML only (G7). Deferred per user directive.

---

## 8) Production-Only Prerequisites (variable names only — no values)

These must be set through the platform's secret store / deploy pipeline **before** the Re-publish is safe to promote. Values are **not** reproduced in this report.

| Variable | Required value shape (name-only reference) | Notes |
|---|---|---|
| `FRONTEND_URL` | Production URL — `https://bidvex.com` | Production URL resolver source per user's design |
| Live Stripe secret API key | Live Stripe key | Must replace any preview `STRIPE_TEST_SECRET_KEY` value. Must not be reused from preview `.env`. |
| Live Stripe webhook signing secret(s) | `STRIPE_WEBHOOK_SECRET`, `STRIPE_WEBHOOK_SECRET_2`, `STRIPE_CONNECT_WEBHOOK_SECRET` | Must match the endpoints registered under the **live** Stripe account (not test-mode webhook endpoints). |

Recommended optional variable:
- `APP_URL` — if the platform sets this to the production public host, the resolver picks it up before `FRONTEND_URL` (precedence position 2). Not required as long as `FRONTEND_URL` is set correctly.
- `PUBLIC_BASE_URL` — optional override. Not required.

**REACT_APP_BACKEND_URL** (frontend) — expected to be swapped to `https://bidvex.com` by the platform frontend build; it is not the backend resolver's active source in either environment.

---

## 9) Overall Release-Readiness Verdict

| Audit Area | Verdict |
|---|---|
| Absolute HTTPS emailed document links | ✅ PASS |
| Preview / production URL resolution | ✅ PASS (preview via `FRONTEND_URL` today; production via `FRONTEND_URL=https://bidvex.com`) |
| Signed-link resolution, EN/FR docs, expired-link rejection, cross-user rejection | ✅ PASS (previously verified) |
| Buyer My Purchases completeness + isolation | ✅ PASS |
| Escrow payout-state safety (no false "Funds Released") | ✅ PASS |
| Stripe key VALUES embedded in preview source | ✅ None found (only sentinels + placeholders + prefix comparisons) |
| Stripe key VALUES packaged from preview `.env` | ⚠ **Deploy pipeline must inject production secrets** rather than copy the preview `.env`. If preview `.env` values would be packaged as-is, **the release is NOT ready to promote**. |
| Controlled Stripe payout verification | ⚠ BLOCKED — carried as unresolved |
| iter468 secure-link email for marketplace / vehicles / storage | ⚠ Gap G4/G5 — carried as deferred |

**Overall**: The iter468–iter473 code changes are structurally sound, unit- and previously-QA-verified read-only. The single hard blocker is confirmation from the deploy pipeline / platform that production Stripe secrets and `FRONTEND_URL=https://bidvex.com` are injected at deploy time and not copied from `/app/backend/.env` and `/app/frontend/.env`. Once that is confirmed, the release is ready to promote.

---

## 10) Stop

**No deploy performed. No secrets rotated. No live-write scripts re-executed.**

Report path: `/app/test_reports/iter468_473_release_readiness_audit.md`
