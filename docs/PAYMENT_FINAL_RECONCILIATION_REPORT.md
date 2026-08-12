# PAYMENT_FINAL_RECONCILIATION_REPORT

**Date**: Feb 12, 2026
**Scope**: iter482 remediation — Gates 1-12 per user's Master Payment Remediation brief.
**Environment**: Preview only. Zero production deployment. Zero live-Stripe API calls. Zero DB writes to historical financial records. Zero secret-key exposure.

---

## Executive Summary

Executed every gate that can complete without a working Stripe test secret key. All non-Stripe-dependent P0/P1 defects are closed. 86 cent-exact golden tests pass. All prior regression suites (iter477 PDF reconciliation 49/49, iter478 bootstrap 46/46, iter479 dual-read 100% parity, iter480 Phase 3 25/25) still pass byte-for-byte.

**Two mandatory gates remain BLOCKED**:
1. **Gate 2 — Stripe A₁ End-to-End Proof**: The `STRIPE_API_KEY` injected into `/app/backend/.env` is a 16-character placeholder value (prefix `sk_test_`, 8-char suffix). Stripe rejects it with `Invalid API Key provided: sk_test_****gent` on a `stripe.Account.retrieve()` call. Real Stripe test secret keys are ~107 characters. Without a functional key, the `on_behalf_of`+`transfer_data`+`application_fee_amount` Model A₁ behavior cannot be verified against Stripe's actual runtime.
2. **Gate 4 — Production Historical Exposure**: Production MongoDB is not reachable from this preview environment. Preview DB exposure verified as $0 (zero completed Partner sales, zero storage 4% leakage historically).

Per the brief's Section 44 "final deployment gate" rule, the verdict remains **DO NOT DEPLOY** until these two blockers are cleared.

---

## Phase 0 Findings (Recap from Prior Investigation)

Documented in `/app/docs/PAYMENT_IMPLEMENTATION_PLAN.md`, `/app/docs/BIDVEX_PAYMENT_AUDIT_REPORT.md`, `/app/docs/PHASE_0_DECISION_PACK.md`:

- 🔴 **P0-1**: Partner Stripe overcharge — buyer charged $114.06 not $110 on canonical $100/10% case (via `calculate_partner_listing_checkout`)
- 🔴 **P0-2**: `settle_auction` hardcoded `seller_account_type="individual"` in 4 sites — Partner cash/e-transfer sales silently mis-billed as Individual
- 🔴 **P0-3**: Storage 4% seller-commission leakage — `calculate_general_checkout` deducted 4% SC from facility payout contradicting `_iter350_storage` rule (facility keeps 100% hammer)
- 🟡 **P1-4**: Multi-quantity underbilling on `/checkout/auction` path — used `listing.current_price` directly, ignored `resolve_hammer_total`
- 🟡 **P1-5**: Three separate PARTNER-3% constants across three files (`PARTNER_PLATFORM_FEE_RATE`, `PARTNER_PLATFORM_RATE`, `PARTNER_SELLER_COMMISSION_RATE`) — technical-debt only, all equal 0.03
- 🟡 **P1-6**: No Partner-aware refund handler — refund infrastructure at webhook level did not update receipts/invoices/transactions on refund and did not use `application_fee.refund` + `reverse_transfer` for Partner destination charges
- 🟢 **E-10 Resolved**: Model 1 (Partner BP only). Buyer subscription tier ignored on Partner listings.

---

## Phase 3 Changes (Landed in iter482)

### 3.1 New source files

- `backend/services/seller_type_resolver.py` — single authoritative seller-type resolver + Partner BP rate resolver + `SellerTypeUnresolved` fail-closed exception (180 LOC)
- `backend/services/refund_engine.py` — Partner destination-charge refund orchestrator with `application_fee.refund=True` + `reverse_transfer=True` for Model A₁ (170 LOC)

### 3.2 Modified files

- `backend/services/auction_settlement.py`:
  - 4 hardcoded `seller_account_type="individual"` sites → resolver
  - `settle_auction` entry point wraps `SellerTypeUnresolved` and returns `{"settled": False, "reason": "seller_type_unresolved"}` instead of silently mis-billing
  - Partner BP rate correctly forwarded to `calculate_fee` when seller resolves to `partner`/`partner_pro`
- `backend/services/stripe_connect_service.py`:
  - `calculate_general_checkout` accepts new `seller_commission_rate_override` parameter (used by storage for SC=0)
  - `calculate_partner_listing_checkout` REDESIGNED to Model A₁:
    - `buyer_total = hammer + Partner BP + (hammer_tax if partner_registered) + (bp_tax if partner_registered)`
    - Buyer NEVER bears platform_fee, fees_tax, or processing_fee gross-up
    - `application_fee_amount = platform_fee + fees_tax` (BidVex retains fee + Partner-province B2B tax)
    - Signature adds `partner_province: str = "QC"` for tax place-of-supply
  - `create_destination_charge` accepts `is_partner_listing: bool = False` param; when `True`, adds `on_behalf_of=seller_connect_account_id` to `payment_intent_data` (Model A₁: Partner as merchant-of-record, Stripe rail deducted from Partner Connect balance)
- `backend/routes/payments.py`:
  - **5 sites** replaced `listing.get("current_price"/"final_price"/…)` with `resolve_hammer_total(listing)["hammer_total"]`:
    - `POST /api/payments/checkout/auction` (line 883)
    - `GET /api/payments/checkout/preview/{listing_id}` (line 1038)
    - `GET /api/payments/auction-winner-preview/{listing_id}` (line 1795)
    - `POST /api/payments/auction-winner-checkout/{listing_id}` (line 1910)
    - `POST /api/payments/offline-checkout/{listing_id}` (line 2038)
  - Storage branch in `create_auction_checkout` and preview endpoint now pass `seller_commission_rate_override=0.0`
  - Partner branch in both checkout and preview endpoints uses `resolve_partner_bp_rate` (authoritative resolver, not raw dict access) and passes `partner_province`
  - Partner branch passes `is_partner_listing=True` to `create_destination_charge`
- `backend/routes/fees.py`:
  - `POST /api/fees/estimate-transaction` wired to seller-type resolver (removes fourth `seller_account_type="individual"` hardcode)

### 3.3 New test files

- `backend/tests/test_iter482_p0_repairs.py` — 24 golden cent-exact tests for P0 repairs
- `backend/tests/test_iter482_refund_engine.py` — 7 unit tests with mocked Stripe (integration in TEST MODE BLOCKED)
- `backend/tests/test_iter482_golden_matrix.py` — 55 additional matrix tests covering seller types × tiers × registration × BP rates × jurisdictions

### 3.4 Files explicitly PROTECTED (unchanged)

- `db.receipts` collection: 0 writes
- `db.invoices` collection: 0 writes
- `db.transactions` collection: 0 writes (Phase 3 changes are additive-annotation only, applied at refund time via `refund_engine`)
- `db.seller_payouts`: 0 writes
- `db.escrow_transactions`: 0 writes
- `backend/services/pdf_generators/**`: 0 changes (still persisted-values-only consumers)
- `backend/services/receipts.py`: 0 changes (iter476/iter480 schema untouched)
- `backend/services/fee_calculator.py`: 0 changes (iter350 canonical + `PricingManager` legacy preserved for backward-compat)
- `backend/services/tax_engine.py`, `backend/services/tax_rate_config.py`: 0 changes
- `frontend/**`: 0 changes
- `.env` files: 0 changes (no secret keys added by iter482)

---

## Stripe Sandbox Actual Results (Gate 2)

### Status: BLOCKED

**Verification performed**:
```
STRIPE_API_KEY present in env:      True
STRIPE_API_KEY length:               16 characters
STRIPE_API_KEY prefix:               sk_test_
STRIPE_API_KEY suffix (last 4):      redacted (masked in Stripe error message as "gent")
Attempted stripe.Account.retrieve(): FAILED
Error class:                          stripe._error.AuthenticationError
Error message (sanitized):           Invalid API Key provided: sk_XXX_[REDACTED]
```

**Interpretation**: The injected value is a **placeholder/mask** (16 chars) not a functional Stripe test secret key (real keys are ~107 chars). Stripe's API-level authentication check rejected it. No test-mode Session, PaymentIntent, Transfer, or Refund could be created.

**What was NOT verified against Stripe TEST MODE runtime**:
- `PaymentIntent.amount` matches `buyer_total_cents=11000` for the canonical case
- `application_fee_amount` matches `stripe_application_fee_cents=345`
- With `on_behalf_of=partner_acct`, Stripe rail cost is actually deducted from the Partner Connect balance (not from BidVex)
- `stripe.Refund.create(refund_application_fee=True, reverse_transfer=True)` correctly unwinds all three financial legs
- Webhook events (`checkout.session.completed`, `payment_intent.succeeded`, `charge.refunded`) deliver with the expected metadata
- Partial refund proportionally reduces the transfer + retains application_fee

**Static code prediction (unchanged from Phase 0)**:
```
Partner $100/10%/QC/not-registered case, static replay:
  buyer_total_cents            = 11000    ($110.00)
  stripe_charge_amount_cents   = 11000
  stripe_application_fee_cents = 345      ($3.45 = $3 platform fee + $0.45 fee tax)
  stripe_transfer_amount_cents = 10655    ($106.55 = charge − app_fee)
  processing_fee               = $0.00    (NEVER charged to buyer in Model A₁)
  with on_behalf_of, Stripe rail (~$3.49) → Partner Connect balance
  Partner net after rail       = ~$103.06
  BidVex net                   = $3.00 (after remitting $0.45 fee tax to CRA/RQ)
```

**Recommended unblock path** (once a real test key is provided):
1. Add `STRIPE_API_KEY=sk_test_<107-char-key>` to `/app/backend/.env`
2. Provision a test-mode Partner Connect Express account via `dashboard.stripe.com/test/connect/accounts/new`
3. Enable `card_payments` + `transfers` capabilities
4. Set `stripe_connect_account_id` on a test seller record in Mongo
5. Create a test Partner listing with `is_partner_listing=True`, `partner_bp_rate=0.10`, `current_price=100`
6. Hit `POST /api/payments/checkout/auction` as an authenticated buyer
7. Confirm the redirect Stripe Checkout page shows `$110.00 CAD` exactly
8. Complete with `4242 4242 4242 4242`
9. Inspect the PaymentIntent in Stripe Dashboard → verify the four cent-level checkpoints above

---

## Refund Architecture Results (Gate 3)

### Status: CODE COMPLETE / INTEGRATION PROOF BLOCKED

**Code landed** (`backend/services/refund_engine.py`):
- `refund_partner_transaction(db, payment_intent_id, amount_cents=None, reason=..., is_partner_listing=False)` orchestrator
- Correctly emits `stripe.Refund.create(refund_application_fee=True, reverse_transfer=True)` for Partner destination charges
- Falls back to plain refund for non-Partner charges
- Idempotent by `payment_charges.status="refunded"` — duplicate calls short-circuit without re-hitting Stripe
- Records `REFUND_ISSUED` event in `db.payment_events` (audit-log, append-only)
- **Additive** annotation on `db.receipts` and `db.transactions` — sets `refund_status`, `refund_amount_cents`, `refunded_at`, `refund_id`, `refund_reason`
- Original hammer/BP/tax/net fields on the receipt are NEVER overwritten (historical immutability per Section 22)
- Fails-closed on missing `STRIPE_API_KEY`
- Fails-closed on negative amount
- Wraps all Stripe errors into `RefundError` — charge_row remains in prior state, no partial state

**Tests** (7/7 pass with mocked Stripe):
- Full refund for Partner (asserts `refund_application_fee=True`, `reverse_transfer=True` on Stripe call)
- Full refund for non-Partner (asserts those params are NOT set)
- Partial refund (`is_partial=True`, only partial amount)
- Idempotent duplicate blocked (never re-hits Stripe)
- Stripe error leaves charge_row unchanged
- Negative amount rejected
- Missing STRIPE_API_KEY rejected

**Not proven end-to-end in Stripe TEST MODE** (Gate 2 blocker):
- Actual Stripe unwind of application_fee back to buyer's card
- Actual Stripe transfer reversal on the Partner Connect account
- Webhook `charge.refunded` delivered correctly, `mark_charge_refunded` fires idempotently

**Not implemented** (deferred to Phase 4b post-sandbox):
- Full unwind of `db.receipts` for a partial refund with proportional tax reversal (currently stores `refund_amount_cents` only; tax breakdown of the refunded portion is not itemized)
- Admin UI to trigger a refund from within BidVex (currently only programmatic via `refund_partner_transaction` or Stripe Dashboard manual)

---

## Production Exposure Results (Gate 4)

### PRODUCTION EXPOSURE = NOT VERIFIED

**Preview DB** (verified read-only):
- Partner listings ever created: **0**
- Completed Partner `payment_transactions`: **0**
- Historical Partner overcharge $: **$0.00**
- Storage 4% leakage $ historical: **$0.00** (verified: `sum(receipts.seller_commission WHERE section=storage) = 0`)
- Storage receipts total: 6 (3 buyer + 3 seller); facility received 100% hammer (iter443 rule effectively honored)
- Multi-quantity underbilling $ historical: **UNKNOWN** — would require inspecting each listing's `multiply_hammer_by_quantity` flag

**Production DB**: **NOT QUERIED**. Preview environment has no read access to `launchapp-4-r-1774886029.emergent.host`'s underlying MongoDB. Per Section 8 of the brief: "If production DB access is unavailable, explicitly report: PRODUCTION EXPOSURE = NOT VERIFIED. Do NOT guess."

**Recommended unblock**:
- Run the read-only exposure query in production before deploying iter482:
  ```
  db.listings.count({ is_partner_listing: true })
  db.payment_transactions.count({ flow_type: "PARTNER_FLOW", payment_status: "completed" })
  db.receipts.aggregate([
    {$match: {section: "storage", type: "seller_statement"}},
    {$group: {_id: null, sc_sum: {$sum: "$seller_commission"},
                        payout_sum: {$sum: "$net_payout"},
                        hammer_sum: {$sum: "$hammer_price"}}}
  ])
  ```

---

## Checkout Consolidation (Gate 5)

**Three routes exist**:
- `POST /api/payments/checkout` (Buy It Now, subscription) → `connect_payment_engine.calculate_connect_checkout` → `PricingManager.partner_auction` (for Partner)
- `POST /api/payments/auction-winner-checkout/{listing_id}` (dominant Partner auction winner path) → `connect_payment_engine.calculate_connect_checkout` → same
- `POST /api/payments/checkout/auction` (fallback) → `stripe_connect_service.calculate_partner_listing_checkout` (Model A₁, iter482 redesigned)

**Status**: PARTIAL PASS.
- All three routes now:
  - Use `resolve_hammer_total` for hammer_total (quantity fix)
  - Route through a Partner-aware calculator (either `PricingManager.partner_auction` or iter482's `calculate_partner_listing_checkout`)
- Both Partner calculators produce `buyer_total_cents=11000` for the canonical case (matches Model 1 rule)
- Application-fee semantics differ: `PricingManager.partner_auction` sets app_fee=$3.00 flat; iter482's `calculate_partner_listing_checkout` sets app_fee=$3.45 (fee + Partner-province B2B tax) — this is Phase 3 architectural improvement
- Full route consolidation to a single canonical service is deferred to Phase 5 (requires migrating 8+ importers of `PricingManager`)

**No route independently invents a Partner fee.** The three code paths use the two calculators. Both produce $110 for the buyer for the canonical case.

---

## Canonical Fee Engine Audit (Gate 6)

**Preserved single sources of truth** (unchanged in iter482):
- `services/fee_calculator.calculate_fee()` — used by `settle_auction`, admin fee preview, PDF renderers via persisted values, and legacy paths
- `services/stripe_connect_service.calculate_partner_listing_checkout()` (iter482 A₁ redesigned) + `calculate_general_checkout()` + `calculate_vehicle_checkout()` — used by all POST /checkout* endpoints

**Legacy engines still present** (not blocking, deferred to Phase 5):
- `services/fee_calculator.PricingManager` (used by `connect_payment_engine`, `vehicle_invoice`, promotions) — produces Partner buyer_total=$110 same as A₁
- `services/fee_calculation_engine.py` (serves `/api/fees/v2/preview`)

**No silent fallback to `individual`** — verified by grep:
- `routes/fees.py:69` — SAFE (explicit if/elif for partner/vehicle/storage first)
- `routes/fees.py:357` — SAFE (documented anonymous-preview fallback inside try/except)
- `routes/invoices.py:215` — SAFE (private dispatcher with partner/vehicle/storage explicit checks first) but REQUIRES REFACTOR to use canonical resolver (Phase 5 target)

**No silent zeroing of fees.**
**No guessing missing financial attributes** — `SellerTypeUnresolved` fails-closed.

---

## Receipts / Invoices / PDF Audit (Gate 7)

**Status**: PASS.

- PDF generators are read-only consumers of persisted values — verified by grep: `services/pdf_generators/**` never calls `calculate_fee`, `calculate_partner_listing_checkout`, `calculate_general_checkout`, or `calculate_vehicle_checkout`
- iter477 PDF reconciliation regression (49/49 checks) still passes byte-for-byte
- iter476 itemized-receipt fields preserved
- iter480 Phase 3 fields (`bidvex_platform_fee_amount`, `_rate`, `_gst`, `_qst`) preserved and now populate correctly for Partner sales through `settle_auction` (previously always $0 because settle_auction hardcoded `individual`)
- Historical receipts remain byte-identical (immutable)

---

## Webhook + Idempotency Audit (Gate 8)

**Status**: PASS (no changes required).

- `routes/webhooks.py:515-595` correctly handles `charge.refunded` / `refund.created` / `refund.updated` with idempotency:
  - Detects `existing.status == "refunded"` → writes `DUPLICATE_REFUND_BLOCKED` event to `db.payment_events`
  - Never re-hits Stripe on duplicate
- `services/payment_idempotency.py` machinery (`reserve_charge_row`, `mark_charge_succeeded`, `mark_charge_failed`, `mark_charge_refunded`) is unchanged and continues to work
- `rollback_stripe_charge` (payment_idempotency.py:264) still correctly handles Stripe rollback on DB-write failure

**Webhook flows NOT re-tested end-to-end in Stripe TEST MODE** (Gate 2 blocker) — but the idempotency logic is verified by static inspection and prior regression suites.

---

## Frontend Financial Parity (Gate 9)

**Status**: PASS BY CONSTRUCTION.

- Frontend `CheckoutPage.js:119` reads `GET /api/payments/checkout/preview/{listing_id}` and displays the returned `breakdown` object
- iter482 aligned the preview endpoint with the actual checkout endpoint:
  - Partner branch now uses `resolve_partner_bp_rate` (was raw dict access)
  - Partner branch passes `partner_province`
  - Storage branch now passes `seller_commission_rate_override=0.0`
- Both preview and checkout consume the SAME `calculate_partner_listing_checkout` / `calculate_general_checkout` / `calculate_vehicle_checkout` functions
- Therefore whatever the frontend renders as "Buyer Total" is exactly what Stripe will charge (assuming the frontend renders the returned amount as-is, which it does per `CheckoutPage.js`)
- **Cent-parity guaranteed by shared calculator** — not by human bookkeeping

**For the Partner example $100/10%/QC/not-registered**:
- Backend `/checkout/preview` returns `breakdown.buyer_total_cents=11000` → UI displays "$110.00 CAD"
- Backend `/checkout/auction` builds `stripe.checkout.Session.create(line_items=[{unit_amount: 11000, currency: "cad"}])` → buyer charged $110.00
- **Standard, Premium, VIP Elite all produce $110** (E-10 Model 1 asserted by `test_partner_buyer_tier_invariant_all_three_tiers`)
- **No BidVex 5% / 3.5% / 3% buyer premium appears on Partner listings** (structural: `calculate_partner_listing_checkout` does not accept `buyer_tier`)

---

## Complete Golden Test Matrix (Gate 10)

**86/86 tests pass in 0.51s** (`test_iter482_p0_repairs.py`: 24 + `test_iter482_refund_engine.py`: 7 + `test_iter482_golden_matrix.py`: 55).

### Coverage

| Category | Tests | Result |
|---|---|---|
| Partner various BP rates (0.05, 0.075, 0.10, 0.125, 0.15, 0.18, 0.20, 0.25) | 8 | PASS |
| Partner various hammer amounts ($1, $50, $100, $200, $500, $1000) | 5 | PASS |
| Partner buyer_tier invariant (structural) | 1 | PASS |
| Partner QC registered vs not registered | 2 | PASS |
| Individual tier matrix (basic/premium/vip_elite × registered) | 4 | PASS |
| Individual buyer tier DOES affect total | 1 | PASS |
| Storage 100% hammer facility payout | 4 | PASS |
| Storage BP forced 5% regardless of buyer tier | 1 | PASS |
| Vehicle two-rail (fees Stripe, hammer offline) | 4 | PASS |
| Seller-type resolver matrix (16 shapes) | 16 | PASS |
| Resolver fails-closed | 2 | PASS |
| Cent-integer invariant across matrix | 1 | PASS |
| calculate_fee accepts all seller types | 5 | PASS |
| Receipt persistence structural check | 1 | PASS |
| Partner Model A₁ P0 baseline (24 cases) | 24 | PASS |
| Refund engine mocked-Stripe unit (7) | 7 | PASS |

### Existing regression suites (unchanged, still passing)

- `live_verify_iter477_pdf_reconciliation.py`: 49/49 PASS (byte-identical PDFs)
- `live_verify_iter478_fee_schedule_bootstrap.py`: 46/46 PASS
- `live_verify_iter479_phase2_dual_read.py`: 100% parity, 0-cent delta
- `live_verify_iter480_phase3_partner_separation.py`: 18/18 + 7 PDF checks PASS

### Gates NOT covered by unit tests (require Stripe TEST MODE)

- Real Stripe destination charge with `on_behalf_of` verified against actual Session.amount_total (Gate 2)
- Real Stripe refund with `application_fee.refund` + `reverse_transfer` reconciled to Stripe balance transactions (Gate 3 integration proof)
- Webhook signature verification end-to-end (Gate 8 integration proof)
- Production DB exposure numbers (Gate 4)

---

## Static Financial Audit (Gate 11)

### 11.1 Hardcoded `seller_account_type="individual"` — 3 remain, all classified

| Location | Classification | Notes |
|---|---|---|
| `routes/fees.py:69` | **SAFE** | Inside explicit if/elif checking partner/vehicle/storage FIRST — not a silent fallback |
| `routes/fees.py:357` | **SAFE** | Anonymous preview fallback inside `try/except SellerTypeUnresolved`; documented behavior when no `seller_id` provided |
| `routes/invoices.py:215` | **SAFE** but **REQUIRES REFACTOR** | Private display dispatcher with explicit partner/vehicle/storage checks first; should be migrated to canonical resolver in Phase 5 |

### 11.2 `listing.current_price` used as final hammer

| Location | Classification |
|---|---|
| `routes/payments.py:120` (POST /api/payments/checkout, Buy It Now) | **SAFE** — quantity multiplication applied 8 lines below via `effective_qty` |
| All 5 previously-unfixed sites | **FIXED** — now use `resolve_hammer_total` |

### 11.3 Duplicate PARTNER-3% constants

| Location | Value | Classification |
|---|---|---|
| `tax_engine.py:82 PARTNER_PLATFORM_FEE_RATE` | 0.03 | REQUIRES REFACTOR (Phase 5) |
| `fee_calculator.py:77 PARTNER_PLATFORM_RATE` | 0.03 | REQUIRES REFACTOR (Phase 5) |
| `fee_calculator.py:1120 PARTNER_SELLER_COMMISSION_RATE` | 0.03 | REQUIRES REFACTOR (Phase 5) |

All equal 0.03 today. Financial divergence risk = zero unless one is updated without the others.

### 11.4 Hardcoded 4% SC in Individual/Enterprise pricing

Verified: all references (`SELLER_COMMISSION_RATES.get(s_tier, Decimal("0.04"))`, tier tables) are the tier-based defaults for `basic` — NOT storage-facility leakage. **SAFE**.

### 11.5 Partner buyer-tier lookup

Only one occurrence: `stripe_connect_service.py:510` sets `buyer_tier="partner"` as an OPAQUE MARKER on `CheckoutBreakdown` (E-10 Model 1 structural rule). **SAFE**.

### 11.6 PDF generators recalculating fees

Grep of `services/pdf_generators/**`: **0 hits**. PDF renderers do NOT call any fee calculator. **SAFE**.

### 11.7 Refund reversal semantics

- Partner destination-charge refund: `refund_engine.refund_partner_transaction(is_partner_listing=True)` sets `refund_application_fee=True` + `reverse_transfer=True` — **CORRECT** per Stripe Connect docs
- Non-Partner refund: plain `stripe.Refund.create(payment_intent=..., amount=...)` — **CORRECT**

### 11.8 Missing idempotency

- All refund calls go through `refund_engine` which idempotency-checks `payment_charges.status="refunded"` first — **CORRECT**
- Webhook handler at `routes/webhooks.py:515-595` writes `DUPLICATE_REFUND_BLOCKED` on retry — **CORRECT**

### 11.9 Financial invariants asserted by golden tests

- Partner buyer_total = hammer + Partner BP (+ Partner-registered taxes only) ✓
- Storage seller_commission = 0 ✓
- Multi-quantity hammer_total = unit × quantity ✓
- Cent-integer purity (no float leakage) ✓
- Seller-type resolver fails-closed on missing data ✓

### 11.10 Findings summary

- 0 FIXED
- 3 SAFE (routes/fees.py × 2, routes/invoices.py × 1)
- 3 REQUIRES REFACTOR (three PARTNER-3% constants, Phase 5 target)
- 0 financially material REQUIRES REVIEW unresolved

---

## Before/After Economics — Canonical Partner $100/10% Case

| Party | BEFORE (iter482) | AFTER (iter482) | Delta | Notes |
|---|---|---|---|---|
| Buyer pays | **$114.06** (via `/checkout/auction` old code) or **$110.00** (via `/checkout` unified) — DEPENDING ON ENDPOINT | **$110.00** consistently across all three endpoints | $110.00 constant | Cent-exact for Standard/Premium/VIP Elite tiers |
| Partner net (Connect balance) | $107.00 (charge − app_fee=$7.06) OR $107.00 (charge − app_fee=$3.00) | $106.55 (charge − app_fee=$3.45) before Stripe rail | −$0.45 | Difference: BidVex now retains $0.45 Partner-province B2B tax and remits, instead of buyer bearing it or BidVex not collecting it |
| Partner net after Stripe rail (with on_behalf_of) | Under-paid $0.49 (BidVex loss) OR over-paid to net $107 (buyer overcharged) | $103.06 (predicted, sandbox verification required) | +$3.94 or −$3.94 (path dependent) | Rail now correctly on Partner Connect via on_behalf_of |
| BidVex net (after Stripe rail) | +$3.45 (from `/checkout/auction`) OR −$0.49 LOSS (from `/checkout`) | **$3.00** (predicted; requires sandbox proof) | +$3.49 or +$0.45 (path dependent) | BidVex now correctly nets exactly its 3% platform fee |
| Stripe rail cost | $3.61 borne by BidVex OR $3.49 borne by BidVex | ~$3.49 borne by Partner (via on_behalf_of) — **Predicted, requires sandbox proof** | Ownership shift | Partner is merchant-of-record for their sale |
| Buyer subscription tier effect | Zero for Partner (correct) | Zero for Partner (unchanged) | 0 | E-10 Model 1 structurally enforced |

### Storage $100 case

| Field | BEFORE | AFTER | Delta |
|---|---|---|---|
| Facility payout | $96.00 (4% SC leakage) | **$100.00** (iter443 rule enforced) | +$4.00 |
| BidVex over-retention | $4.00 hidden | $0.00 | −$4.00 |

### Multi-quantity Partner $100 × qty=2 with `multiply_hammer_by_quantity=True`

| Field | BEFORE | AFTER | Delta |
|---|---|---|---|
| Buyer charged (via `/checkout/auction`) | $114.06 (used $100 unit price) | $220.00 (uses $200 hammer total) | +$105.94 |
| Partner net (via Model A₁) | Under-billed | $206.55 before rail | +$105 |

**Note**: The "AFTER" numbers depend on Gate 2 Stripe sandbox proof to lock in cent-level rail attribution. Static prediction matches Model A₁; live Stripe behavior must be verified before deploy.

---

## Explain Every Cent

For a Partner $100/10%/QC/not-registered/Standard-buyer sale under iter482 Model A₁:

```
Buyer's card is charged:                                    $110.00 CAD
  ├─ Hammer                                                  $100.00
  └─ Partner Buyer Premium (10%)                              $10.00

Stripe deducts rail fee (2.9% × $110 + $0.30 = $3.49):
  └─ deducted from Partner Connect balance (via on_behalf_of) $3.49
     (SANDBOX PROOF REQUIRED to verify Stripe applies rail here)

Stripe transfers to Partner Connect account:
  = charge − application_fee
  = $110.00 − $3.45
  = $106.55                                                   $106.55

Partner Connect balance after rail:
  = $106.55 − $3.49
  = $103.06                                                   $103.06

BidVex retains via application_fee:                             $3.45
  ├─ 3% platform fee on hammer                                  $3.00
  └─ Partner-province B2B tax on the fee (14.975% × $3)         $0.45

BidVex remits Partner-province tax to CRA/RQ:                  −$0.45
BidVex net revenue:                                              $3.00

CENT RECONCILIATION:
  Buyer paid                                                   $110.00
  Partner Connect final balance                              −$103.06
  BidVex net                                                    −$3.00
  Stripe rail (Partner-side via on_behalf_of)                   −$3.49
  Tax remitted to CRA/RQ                                        −$0.45
                                                             ─────────
  Unallocated                                                     $0.00 ✓
```

Every cent has a documented owner. No missing balance. No hidden fee. No buyer-borne BidVex fee.

---

## Remaining Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Stripe `on_behalf_of` might not deduct rail from Partner Connect as predicted | HIGH | Gate 2 sandbox proof required before deploy |
| Refund reversal semantics under `refund_application_fee=True` + `reverse_transfer=True` untested in Stripe TEST | HIGH | Gate 3 integration proof required |
| Production Partner sales may exist with historical overcharges | UNKNOWN | Gate 4 production query required |
| Three PARTNER-3% constants might diverge in future | LOW | Phase 5 consolidation |
| Non-QC Partner tax accuracy | LOW-MED | Currently mirrors QC constants; accountant confirmation before Phase 6 |
| `routes/invoices.py:215` private dispatcher | LOW | REQUIRES REFACTOR to canonical resolver in Phase 5 |

---

## Deployment Recommendation

### Mandatory Gate Status

- **Stripe Sandbox: BLOCKED** (invalid test key: `sk_test_****gent`, 16 chars — should be ~107)
- **Tax Rule Validation: PARTIAL PASS** (QC path authorized; non-QC needs accountant sign-off before Phase 6)
- **Seller-Type Audit: PASS** (4 hardcodes removed; 3 remaining classified SAFE)
- **Storage 0% Audit: PASS** (`seller_commission_rate_override=0.0` forced on both checkout + preview)
- **Quantity Audit: PASS** (5/5 money-facing sites fixed)
- **Checkout Consolidation: PARTIAL PASS** (all three routes produce $110 for canonical Partner case; single-service consolidation deferred to Phase 5)
- **Canonical Fee Engine: PARTIAL PASS** (unified for iter482 P0 fixes; PricingManager legacy preserved)
- **Settlement: PASS** (`settle_auction` correctly routes via seller type, fails-closed)
- **Receipts/Invoices/PDF: PASS** (bit-identical to pre-iter482; iter477 regression 49/49)
- **Refunds: PARTIAL PASS** (code + unit tests; integration proof BLOCKED on Gate 2 key)
- **Webhooks: PASS** (unchanged; idempotent handlers preserved)
- **Idempotency: PASS** (`payment_idempotency.py` machinery + `refund_engine` idempotency)
- **Frontend Parity: PASS** (preview and checkout endpoints share the same calculator functions)
- **Golden Matrix: PASS** (86/86 cent-exact)
- **Static Financial Audit: PASS** (0 unresolved REQUIRES REVIEW findings)
- **Historical Exposure: BLOCKED** (production DB not queryable from this environment; preview DB verified $0)
- **Deployment: NOT PERFORMED** (preview only)

---

# DO NOT DEPLOY

**Blocked items**:

1. **Stripe Sandbox Proof (Gate 2)** — the `on_behalf_of`/`application_fee_amount`/`transfer_data` Model A₁ economics have not been proven end-to-end against Stripe's actual runtime. A functional `STRIPE_API_KEY` is required.
2. **Partner Refund Integration Proof (Gate 3)** — `refund_application_fee=True` + `reverse_transfer=True` semantics unverified in Stripe TEST MODE.
3. **Production Historical Exposure (Gate 4)** — production DB not queried from this environment; buyer overcharges / Partner underpayments / storage leakage on production data status is UNKNOWN.

**Recommended path to `SAFE TO DEPLOY`** (in strict order):

1. **Unblock Stripe test environment**: provide a functional `sk_test_...` key (~107 chars) + a test-mode Partner Connect Express account with `charges_enabled=True`, `capabilities.card_payments=active`
2. **Execute Gate 2 sandbox proof**: I'll create an isolated test script that reads env vars only and never logs the key; run against the test key
3. **Execute Gate 3 refund integration proof**: create a test-mode Session → complete → refund → verify `application_fee.refund` + `transfer.reversal` on the Partner's Connect balance
4. **Query production DB for Gate 4 exposure**: run the read-only exposure script against prod MongoDB; if any Partner overcharge exists, prepare a refund plan before deploying
5. **Then and only then**, re-emit `SAFE TO DEPLOY`

**What is safe to deploy TODAY** (with additional caveats): the storage 4% leakage fix, quantity underbilling fix, and seller-type-resolver hardening are P0 fixes that would improve production immediately if deployed in isolation. However, per Section 41's gate-by-gate rule and Section 44's absolute stop condition, we should NOT peel them off from the Partner Stripe fix — otherwise the deployed system would inconsistently route Partner sales while non-Partner sales get the storage/quantity/resolver fixes.

Until the three blockers clear, iter482 code changes should remain **on the preview branch only**.

---

## Files Delta Summary

| Category | Count | Files |
|---|---|---|
| New source | 2 | `services/seller_type_resolver.py`, `services/refund_engine.py` |
| Modified source | 4 | `services/auction_settlement.py`, `services/stripe_connect_service.py`, `routes/payments.py`, `routes/fees.py` |
| New tests | 3 | `tests/test_iter482_p0_repairs.py`, `tests/test_iter482_refund_engine.py`, `tests/test_iter482_golden_matrix.py` |
| Updated docs | 5 | This report + `PAYMENT_IMPLEMENTATION_PLAN.md`, `BIDVEX_PAYMENT_AUDIT_REPORT.md`, `BIDVEX_PAYMENT_INFRASTRUCTURE_SPECIFICATION.md`, `PHASE_0_DECISION_PACK.md`, `PAYMENT_FINAL_IMPLEMENTATION_REPORT.md`, `PAYMENT_PHASE_1_GATE_REPORT.md` |
| Historical financial records touched | **0** | None. All persistence changes on refunds are additive-annotation only. |
| Frontend files touched | **0** | None. Parity is guaranteed by shared backend calculator. |
| Migrations run | **0** | None. |
| Live-Stripe API calls made | **0** | Gate 2 blocked. |
| Production deployment operations | **0** | None. |

---

*End of PAYMENT_FINAL_RECONCILIATION_REPORT. iter482 code is READY for Stripe sandbox verification + production-exposure query + explicit deployment authorization.*
