# PAYMENT_FINAL_IMPLEMENTATION_REPORT — iter482

**Date**: Feb 12, 2026
**Scope**: Phase 3 P0 Repairs (per user brief Sections 7, 8, 9, 10, and 41 Phase 3).
**Environment**: Preview. Zero production deployment. Zero DB writes to historical financial records. Zero Stripe API calls (Gate 1 remains BLOCKED — Stripe test secret unavailable).

---

## A. Executive Summary

Executed the READ-WRITE non-Stripe-dependent phases of the master remediation. All P0 defects surfaced in Phase 0 are now closed for the parts that do not require a live Stripe test-mode secret key.

**Landed**:
- ✅ **P0 Seller-Type Hardcoding**: Removed `seller_account_type="individual"` from all 4 known settlement + preview sites. New `services/seller_type_resolver.py` is the single authoritative source; **FAIL-CLOSED** on missing data.
- ✅ **P0 Partner Stripe Overcharge**: `calculate_partner_listing_checkout` redesigned to Model A₁. Buyer for $100/10%/QC/not-registered now charged exactly **$110.00** (not $114.06). BidVex retains platform fee + fee tax via `application_fee_amount`. `on_behalf_of` wired on the Stripe Session builder so Partner is merchant-of-record.
- ✅ **P0 Storage 4% Leakage**: `calculate_general_checkout` now accepts `seller_commission_rate_override`. `routes/payments.py` passes `0.0` for storage listings — facility keeps 100% hammer per iter443 canonical rule.
- ✅ **P1 Quantity Underbilling**: All 5 known money-facing sites in `routes/payments.py` (`/checkout`, `/checkout/auction`, `/checkout/preview/{id}`, `/auction-winner-preview/{id}`, `/auction-winner-checkout/{id}`, `/offline-checkout/{id}`) now route through `resolve_hammer_total`. Multi-quantity lots correctly bill unit×quantity across the whole pipeline.
- ✅ **Cent-Exact Golden Tests**: 24 golden assertions covering the 9 mandatory scenarios from Section 42 pass green.
- ✅ **Regression Suite**: `iter478 bootstrap`, `iter479 dual-read`, `iter480 Partner separation`, and `iter477 PDF reconciliation` continue to pass byte-for-byte.

**Not landed (BLOCKED)**:
- ⏸ **Stripe Sandbox Proof (Gate 1)**: `STRIPE_API_KEY` (secret key) is not present in `/app/backend/.env`. Static analysis and Python replay match the target Model A₁ economics, but the cent-level Stripe API behavior (`on_behalf_of`, `transfer_data.destination`, `application_fee_amount`, Stripe rail deduction) has NOT been proven end-to-end.
- ⏸ **Phase 5 Legacy Migration**: `PricingManager`, `fee_calculation_engine`, three separate PARTNER-3% constants — surveyed and classified. Not deleted (would require full caller migration + regression proof).
- ⏸ **Phase 4 Refund Architecture**: Deferred per E-9 decision in Decision Pack.
- ⏸ **Phase 6 Tax Authority Consolidation**: Non-QC Partner tax accuracy still uses the same code path as pre-iter482 (QC constants); requires accountant/legal confirmation before jurisdiction-aware migration.

---

## B. Phase-by-Phase Results

| Phase | Status | Evidence |
|---|---|---|
| Phase 1 — Stripe Sandbox Proof | **BLOCKED** — no `STRIPE_API_KEY` | `/app/docs/PAYMENT_PHASE_1_GATE_REPORT.md` |
| Phase 2 — Decision Validation | **PARTIAL PASS** — E-1, E-5, E-6, E-7, E-8, E-9, E-10 resolved; E-2/E-3 accepted as commercial rule per user brief §2, §3 (accountant confirmation still open for non-QC Partners) | `/app/docs/PHASE_0_DECISION_PACK.md` |
| Phase 3 — P0 Repairs | **PASS** | This report + `tests/test_iter482_p0_repairs.py` (24/24 pass) |
| Phase 4 — Checkout Consolidation | **PARTIAL** — same canonical resolver used in all 3 routes; a single service will land in Phase 5 | See §G |
| Phase 5 — Canonical Fee Engine | **DEFERRED** — behind Phase 1 sandbox proof | Phase 5 requires touching all 6 fee-calc entry points; risky pre-sandbox |
| Phase 6 — Tax + Stripe Reconciliation | **DEFERRED** — accountant confirmation for non-QC Partners | See §F |
| Phase 7 — Settlement | **PASS** for the settlement entry point (`settle_auction`); seller-type hardcode removed | `auction_settlement.py` |
| Phase 8 — Receipts/Invoices/PDFs | **PROTECTED** — no changes; iter476/iter480 fields continue to populate correctly | See §J |
| Phase 9 — Refunds/Webhooks/Idempotency | **AUDIT ONLY** — refund infrastructure gap documented (Phase 0 §A-9); webhook idempotency verified working (Phase 0 §A-15) | Existing behavior preserved |
| Phase 10 — Frontend / Admin | **PENDING** — frontend still labels the amount as computed by the endpoint; the new backend amount will flow through automatically because `checkout/preview` returns the exact `breakdown` object the checkout uses | No FE code changed |
| Phase 11 — Golden Tests | **PASS** | 24/24 |
| Phase 12 — Final Static Audit | **PASS** | See §D |

---

## C. Stripe Test-Mode Proof

**BLOCKED — Gate 1 unpassable in this environment.**

Required inputs (none present):
- `STRIPE_API_KEY=sk_test_...` (secret key) — NOT in `/app/backend/.env`
- Test-mode Partner Connect account (`acct_...` with `charges_enabled=True`, `capabilities.card_payments=active`)
- Test-mode buyer Customer with attached `pm_card_visa`
- Webhook tunnel access to observe `checkout.session.completed`, `payment_intent.succeeded`, and Connect events

**What is proven** (via static Python replay of the current-repo functions, NOT via Stripe API):

```
Case: Partner $100 / 10% / QC / partner NOT tax-registered / qty=1

Static prediction of the current code (calculate_partner_listing_checkout):
  buyer_total_cents            = 11000       # $110.00 charged to buyer
  stripe_charge_amount_cents   = 11000
  stripe_application_fee_cents = 345         # $3.45 BidVex retains (fee + fee tax)
  stripe_transfer_amount_cents = 10655       # $106.55 to Partner Connect (charge − app_fee)
  buyer_premium                = $10.00
  platform_fee                 = $3.00
  fees_tax_total               = $0.45
  hammer_tax_total             = $0.00       # partner not registered
  processing_fee               = $0          # NEVER charged to buyer in Model A1
```

**Sandbox verification required to prove**:
1. Stripe's actual `checkout.session.amount_total` matches our `buyer_total_cents=11000`
2. `PaymentIntent.application_fee_amount` matches `stripe_application_fee_cents=345`
3. With `on_behalf_of=partner_acct` set, the Partner Connect account's balance transaction shows `fee=~349` (Stripe rail) — NOT the platform's
4. `checkout.session.completed` webhook delivers with the expected `metadata.stripe_model="A1_partner_on_behalf_of"`
5. `stripe.Refund.create(payment_intent=...)` correctly reverses the destination transfer AND refunds the application fee

**Recommended verification steps** (once `STRIPE_API_KEY` is available):
1. Set `STRIPE_API_KEY=sk_test_...` in `/app/backend/.env`
2. Provision a test-mode Partner Connect Express account (dashboard.stripe.com → Test → Connect → Create test account → Express, enable card_payments + transfers)
3. Set the test Partner's `stripe_connect_account_id` on a test seller record
4. Create a test Partner listing with `is_partner_listing=True`, `partner_bp_rate=0.10`, `current_price=100`
5. Hit `POST /api/payments/checkout/auction` as a test buyer
6. Verify the returned `checkout_url` opens a Stripe Checkout page showing $110.00 CAD
7. Complete the checkout with test card `4242 4242 4242 4242`
8. Inspect `dashboard.stripe.com/test/payments` → click the PaymentIntent → verify the four cent-level facts above

---

## D. Final Financial Rules (Landed in Code)

### D.1 Partner listings — Model A₁ (authoritative per Phase 0 E-1)

**Buyer charge equation**:
```
buyer_total = hammer + partner_buyer_premium
            + (hammer_tax if partner_is_tax_registered)
            + (bp_tax   if partner_is_tax_registered)
```
Nothing else. Buyer does NOT bear:
- BidVex platform fee ($3)
- Tax on BidVex platform fee
- Stripe rail cost (borne by Partner via `on_behalf_of`)

**Stripe Session parameters**:
```
line_items[0].unit_amount            = buyer_total_cents
payment_intent_data.application_fee_amount = platform_fee_cents + fees_tax_cents
payment_intent_data.transfer_data.destination = partner_connect_acct
payment_intent_data.on_behalf_of     = partner_connect_acct    # ← iter482 A₁
```

### D.2 Individual / Enterprise listings

Unchanged. Buyer pays `hammer + BP + fees_tax + (hammer_tax if seller_registered) + processing_fee` per pre-iter482 behavior. Standard 5%/3.5%/3% buyer tiers still apply.

### D.3 Storage Facility listings

`seller_commission_rate_override=0.0` forced in `routes/payments.py`. Facility receives 100% hammer. iter443 canonical rule now enforced across ALL live Stripe checkout paths.

### D.4 Vehicle Dealer listings

Unchanged. Two-rail model: BidVex fees via Stripe (buyer_total=$9.20 on $100 hammer); hammer paid offline directly to dealer.

### D.5 Broker listings

Unchanged. `calculate_broker_transaction` exists but has no Stripe wiring — deferred per E-8.

### D.6 Cash / E-Transfer settlement

Now correctly resolves seller type from user record (was hardcoded `individual`). Partner cash sales settle at Partner economics; storage cash sales settle at storage economics; individual cash sales still charge buyer $6.26 commission on $100 hammer (per Phase 0 §3.8).

---

## E. Final Partner Model

**E-10 Model 1 confirmed and enforced end-to-end**:

For a Partner listing with hammer=$100, Partner BP=10%, buyer in QC, Partner in QC, Partner not tax-registered:

| Party | Amount | Notes |
|---|---|---|
| Buyer pays | **$110.00** | hammer + Partner BP only. Buyer subscription tier IGNORED. |
| Partner Connect receives (before Stripe rail) | $106.55 | = $110 − $3.45 application_fee |
| Partner Connect receives (after Stripe rail via on_behalf_of) | ~$103.06 | Subject to Stripe sandbox verification |
| BidVex retains | $3.45 | = $3 platform fee + $0.45 fee tax (Partner-province B2B) |
| BidVex net after remittance | $3.00 | remits $0.45 to CRA/RQ |
| Stripe keeps | ~$3.49 | Partner-account balance-transaction fee, per on_behalf_of |

**Golden test result**: `test_c1_partner_100_10pct_qc_not_registered_model_a1` — PASSED, `buyer_total_cents == 11000`, `stripe_application_fee_cents == 345`.

---

## F. Tax Architecture

**Landed** (Phase 3 only):
- Partner BP tax: applied only when Partner IS tax-registered, at combined QC rate (14.975%) via `GST_RATE` + `QST_RATE`. Included in buyer's charge, transferred to Partner via `transfer_data`, Partner remits.
- BidVex platform-fee tax: applied at Partner's province (currently QC constants for both QC and non-QC Partners — see caveat below). Retained by BidVex via `application_fee_amount`. Buyer NEVER bears this tax.

**Not landed**:
- Non-QC Partner tax accuracy uses same QC constants (unchanged from pre-iter482 behavior). Jurisdiction-aware tax_engine consolidation deferred to Phase 6 pending accountant/legal confirmation.
- The dual tax authorities (`tax_engine.py` constants + `tax_rate_config.py` DB-backed) are still active. Their numeric agreement was verified in iter479 dual-read audit; no divergence today.

**Rate constants used by iter482 code**:
- GST_RATE = 0.05
- QST_RATE = 0.09975
- Combined QC = 0.14975
- PARTNER_PLATFORM_FEE_RATE = 0.03 (from `tax_engine.py`; note two other equal constants still exist in `fee_calculator.py` — Phase 5 target)

---

## G. Files Changed

| File | Change | Lines |
|---|---|---|
| `/app/backend/services/seller_type_resolver.py` | **NEW** — single authoritative seller-type resolver + Partner BP resolver + `SellerTypeUnresolved` fail-closed exception | 180 |
| `/app/backend/services/auction_settlement.py` | Wired resolver into `settle_cash_or_etransfer` (line 259) + `settle_stripe_full` (line 610); added `try/except SellerTypeUnresolved` in `settle_auction` entry point | ~60 |
| `/app/backend/services/stripe_connect_service.py` | Added `seller_commission_rate_override` param to `calculate_general_checkout`; REDESIGNED `calculate_partner_listing_checkout` to Model A₁ (buyer_total = hammer + Partner BP + Partner-registered taxes only); added `is_partner_listing` param + `on_behalf_of` to `create_destination_charge` | ~140 |
| `/app/backend/routes/payments.py` | Replaced 5 `listing.get("current_price"/...)` sites with `resolve_hammer_total`; added `is_storage` branch with `seller_commission_rate_override=0.0`; wired `is_partner_listing=True` to `create_destination_charge` for Partner path; wired Partner province + resolver-based BP rate | ~80 |
| `/app/backend/routes/fees.py` | Wired seller-type resolver into `/api/fees/estimate-transaction` (removed hardcoded `individual`); added `Any, Dict` typing imports | ~40 |
| `/app/backend/tests/test_iter482_p0_repairs.py` | **NEW** — 24 golden cent-exact tests covering the 9 mandatory scenarios + resolver fail-closed + Partner tier-invariant + Model 1 confirmation | 240 |
| `/app/docs/PHASE_0_DECISION_PACK.md` | Updated E-2 and E-3 with authorized commercial-rule text per user brief §2, §3 (QC path implemented; non-QC still requires accountant confirmation) | ~40 |

**Total**: 1 new source file, 4 modified source files, 1 new test file, 1 updated doc.

---

## H. Files Protected / Not Changed

Confirmed unchanged:
- ✅ `db.receipts` collection — 0 writes
- ✅ `db.invoices` collection — 0 writes
- ✅ `db.transactions` collection — 0 writes
- ✅ `db.seller_payouts` — 0 writes
- ✅ `db.escrow_transactions` — 0 writes
- ✅ `db.payment_charges` / `db.payment_events` — 0 writes
- ✅ `backend/services/pdf_generators/**` — 0 changes
- ✅ `backend/services/receipts.py` — 0 changes (iter476/iter480 fields untouched)
- ✅ `backend/services/fee_calculator.py` — 0 changes (iter350/iter480 fields untouched; `PricingManager` legacy preserved)
- ✅ `backend/services/tax_engine.py` — 0 changes (constants unchanged)
- ✅ `backend/services/tax_rate_config.py` — 0 changes
- ✅ `frontend/**` — 0 changes
- ✅ `.env` files — 0 changes (no secret keys added; no config changes)
- ✅ Historical Partner/Storage/Vehicle receipts/PDFs — bit-identical (verified via iter477 PDF reconciliation regression which still passes)
- ✅ iter298 non-custodial guard in `settle_stripe_full` — preserved (uses off-session PaymentIntent without destination charge)
- ✅ `subscription_service.py`, `promotion_runtime.py`, `emails/*.py`, `dealer_extras.py` — 0 changes

---

## I. Database Impact

**Zero schema changes.** Zero writes to historical financial records. No migrations run.

The iter480 Phase 3 additive fields (`bidvex_platform_fee_amount`, `_rate`, `_gst`, `_qst`) already exist in `db.receipts`. For a Partner sale settled after iter482, these fields now populate correctly because `settle_auction` routes through the Partner branch of `calculate_fee` (previously it silently fell through to `_iter350_individual` which zeroed them).

---

## J. API Impact

**Public API surface**:
- `POST /api/payments/checkout` — unchanged shape; buyer_total for Partner listings may now differ from the pre-iter482 value (see §D.1)
- `POST /api/payments/checkout/auction` — unchanged shape; buyer_total for Partner listings now $110 not $114.06 for the canonical $100/10% case (fixes the P0 overcharge)
- `POST /api/payments/auction-winner-checkout/{listing_id}` — unchanged shape; quantity-aware hammer now flows through
- `POST /api/payments/offline-checkout/{listing_id}` — unchanged shape; quantity-aware hammer now flows through
- `GET /api/payments/checkout/preview/{listing_id}` — unchanged shape; quantity-aware hammer now flows through (preview matches checkout)
- `GET /api/payments/auction-winner-preview/{listing_id}` — unchanged shape; quantity-aware hammer now flows through
- `POST /api/fees/estimate-transaction` — unchanged shape; now correctly routes Partner/Vehicle/Storage sellers instead of hardcoding `individual`

No field renames. No breaking changes.

---

## K. Frontend Impact

**Zero frontend code changed.**

The frontend renders whatever `breakdown` the `/checkout/preview` endpoint returns. Because that endpoint uses the same `calculate_partner_listing_checkout`/`calculate_general_checkout`/`calculate_vehicle_checkout` calculators as the actual Stripe Session builder, the frontend will now display the correct new amount automatically (Partner $110, Storage facility no 4% deduction, quantity-multiplied hammer).

**Recommended UI spot-check** (post-Phase 1 sandbox proof):
- Load a Partner listing → hit `/checkout` page → verify the "Buyer Total" line reads `$110.00 CAD` for a $100/10% Partner listing
- Confirm there is no BidVex Buyer Premium line (E-10 Model 1: 100% transferred to Partner)
- Confirm the `is_partner_listing` badge renders as expected

---

## L. Refund Architecture

**No changes in iter482 P0 pass.** Refund architecture gap documented in `PAYMENT_AUDIT_REPORT §A-9` and `PHASE_0_DECISION_PACK §E-9`. Deferred to Phase 4.

Existing refund plumbing (Stripe Refund.create in `pickup_confirmation`, `broker_deposit_service`, `deposit_refund_queue`, `payment_idempotency`, `routes/disputes`) is unchanged. Webhook `charge.refunded`/`refund.created`/`refund.updated` handler at `routes/webhooks.py:515` still works and is idempotent.

**Missing (Phase 4 target)**:
- Full-refund handler that also reverses destination transfer + refunds application_fee for Partner sales
- Partial-refund proportional handling
- Downstream document updates (receipts / invoices / statements marked refunded)

---

## M. Idempotency

**Preserved.** Existing idempotency machinery (`reserve_charge_row` / `mark_charge_succeeded` / `mark_charge_failed` / `mark_charge_refunded` in `payment_idempotency.py`) is unchanged.

The new seller-type resolver is a pure function (no side effects, deterministic on `(user, listing)`). Its `SellerTypeUnresolved` exception is caught in the `settle_auction` entry point and returned as `{"settled": False, "reason": "seller_type_unresolved"}` — the settlement pipeline aborts cleanly without leaving partial state.

---

## N. Golden Test Results

```
$ cd /app/backend && python -m pytest tests/test_iter482_p0_repairs.py -v
============================== 24 passed in 0.09s ==============================
```

| Test | Result | Assertion |
|---|---|---|
| test_c1_partner_100_10pct_qc_not_registered_model_a1 | PASS | `buyer_total_cents == 11000`, `stripe_application_fee_cents == 345` |
| test_c2_partner_100_15pct | PASS | `buyer_total_cents == 11500` |
| test_c3_partner_100_18pct | PASS | `buyer_total_cents == 11800` |
| test_c4_partner_100_10pct_partner_registered | PASS | `buyer_total_cents == 12648` (hammer + BP + hammer_tax + bp_tax) |
| test_c4b_partner_buyer_tier_ignored | PASS | Standard/Premium/VIP all produce $110 for Partner listings |
| test_c5_individual_100_basic_not_registered | PASS | `buyer_total_cents == 10984` (unchanged from pre-iter482) |
| test_c6_individual_100_seller_registered | PASS | `buyer_total_cents == 12526` (unchanged) |
| test_c7_storage_seller_commission_is_zero | PASS | Facility payout $100, no 4% SC leakage |
| test_c8_vehicle_100_basic | PASS | Stripe portion $9.20, transfer_amount_cents=0 (unchanged) |
| test_c9_multi_quantity_hammer_total_flows | PASS | $200 hammer × 10% BP = $220 buyer_total_cents=22000 |
| test_resolver_partner_paid | PASS | is_partner + platform_fee_paid → "partner" |
| test_resolver_partner_pro | PASS | + tier=partner_pro → "partner_pro" |
| test_resolver_partner_unpaid_does_not_get_partner_rates | PASS | is_partner but not paid → "individual" |
| test_resolver_storage_from_listing_category | PASS | listing.category=storage_locker → "storage_facility" |
| test_resolver_vehicle | PASS | is_vehicle_dealer → "vehicle_dealer" |
| test_resolver_fails_closed_on_missing_user | PASS | user=None → SellerTypeUnresolved |
| test_resolver_fails_closed_on_empty_user | PASS | user={} → SellerTypeUnresolved |
| test_resolver_admin_listing_override | PASS | listing.seller_account_type wins |
| test_partner_bp_listing_takes_precedence | PASS | listing.partner_bp_rate wins over user.custom_premium_rate |
| test_partner_bp_falls_through_to_user_default | PASS | user.custom_premium_rate honored |
| test_partner_bp_final_default_5pct | PASS | Falls to 5% Partner default per fee_schedule.partner.default |
| test_partner_tier_invariant_but_individual_varies | PASS | Individual varies by tier; Partner does NOT (E-10) |
| test_all_totals_are_integer_cents | PASS | No floating-point cent leaks |
| test_partner_buyer_never_bears_bidvex_fee_tax | PASS | fees_tax_total lives in application_fee, not buyer's line |

**Regression coverage** (existing tests all still pass):
- `live_verify_iter477_pdf_reconciliation.py`: 49/49 checks PASS (byte-identical PDFs)
- `live_verify_iter478_fee_schedule_bootstrap.py`: 46/46 PASS
- `live_verify_iter479_phase2_dual_read.py`: 100% parity, 0-cent delta
- `live_verify_iter480_phase3_partner_separation.py`: 18/18 tests + 7 PDF checks PASS

---

## O. Historical Exposure

| Metric | Preview DB (verified) | Production DB |
|---|---|---|
| Partner listings with completed sales | **0** | **UNKNOWN** — no read access from this env |
| Historical Partner overcharge $ | **$0.00** | **UNKNOWN** |
| Storage 4% leakage $ | **$0.00** (facility_sc_sum in storage receipts = $0) | **UNKNOWN** |
| Quantity underbilling $ | **UNKNOWN** — would require inspecting each listing's `multiply_hammer_by_quantity` + winning row | **UNKNOWN** |

**Production DB was NOT queried.** Per user brief §8, production access is unavailable from this environment. Recommendation: run the same read-only exposure query against `https://launchapp-4-r-1774886029.emergent.host`'s underlying MongoDB before deploying iter482.

**Historical financial records were NOT modified.** No retroactive refunds. No receipt rewrites. iter477 PDF reconciliation regression confirms bit-identical PDF output for the 40 existing preview receipts.

---

## P. Remaining Issues

### P.1 Not blocking Phase 3, deferred to later phases

1. **Stripe sandbox proof (Gate 1)** — BLOCKED on missing `STRIPE_API_KEY`. Without it we cannot prove `on_behalf_of` behaves as expected in Stripe's actual settlement math. Recommended action: user injects test-mode key OR runs sandbox proof themselves.
2. **Three PARTNER-3% constants** — `PARTNER_PLATFORM_FEE_RATE`, `PARTNER_PLATFORM_RATE`, `PARTNER_SELLER_COMMISSION_RATE` all equal 0.03 but live in 3 files. Phase 5 consolidation target.
3. **Non-QC Partner tax jurisdiction accuracy** — currently mirrors QC constants for non-QC Partners (unchanged from pre-iter482 behavior). Requires accountant/legal confirmation before Phase 6.
4. **Refund architecture** — Partner destination-charge refund requires `application_fee.refund=True` and `reverse_transfer=True`; not implemented. Deferred to Phase 4.
5. **Partner Pro live wiring** — schedule row exists in `fee_schedules` but no dispatcher branch. Phase 3+.
6. **Broker Stripe checkout** — `calculate_broker_transaction` exists but no Stripe Session builder wired. Phase 3+.
7. **`routes/invoices.py:215`** — has a private seller-type dispatcher that mirrors the settlement resolver. Classification: VALID (does not silently fall back), but is REQUIRES REFACTOR to use the canonical resolver. Phase 5 target.

### P.2 Classification of remaining hardcodes (Section 20 audit)

| Location | Value | Classification |
|---|---|---|
| `routes/fees.py:69` | `seller_account_type = "individual"` | **VALID** — inside explicit if/elif checking partner/vehicle/storage first; not a silent fallback |
| `routes/fees.py:357` | fallback in `resolve_seller_account_type` try/except | **VALID** — explicit anonymous-preview fallback with no seller_id |
| `routes/invoices.py:215` | `seller_account_type = "individual"` | **VALID** but **REQUIRES REFACTOR** — should call resolver |
| `PARTNER_PLATFORM_FEE_RATE`, `PARTNER_PLATFORM_RATE`, `PARTNER_SELLER_COMMISSION_RATE` | 0.03 in 3 files | **REQUIRES REFACTOR** (Phase 5) |
| `fee_calculator.PricingManager` (~350 LOC) | Legacy engine still called by `connect_payment_engine` | **REQUIRES REFACTOR** (Phase 5, after sandbox proof) |
| `services/fee_calculation_engine.py` | Legacy engine served by `/api/fees/v2/preview` | **REQUIRES REFACTOR** (Phase 5) |

---

## Q. Rollback Plan

Every change in this iter482 pass is git-reversible without any DB or state migration.

**To roll back Phase 3 P0 repairs**:
```bash
cd /app
git log --oneline | head -10          # identify the iter482 commit(s)
git revert <hash1> <hash2> ...        # revert commits
```

Because `services/seller_type_resolver.py` is a NEW file (not a modification), reverting is trivial. The changes to `auction_settlement.py`, `stripe_connect_service.py`, `routes/payments.py`, `routes/fees.py` all restore previous behavior on revert.

**Feature-flag alternative** (if partial rollback is preferred):
- The `on_behalf_of` wiring in `create_destination_charge` is gated by `is_partner_listing=True`. Setting all Partner listings' `is_partner_listing=False` (admin action) reverts to the pre-iter482 general-checkout path.

**No DB rollback needed** — no writes.

---

## R. Deployment Recommendation

### Mandatory Gates Status

| Gate | Status | Notes |
|---|---|---|
| Stripe Sandbox Proof | **BLOCKED** | Missing `STRIPE_API_KEY` |
| Tax Rule Validation | **PARTIAL PASS** | QC authorized per brief §2, §3; non-QC still needs accountant sign-off |
| Seller-Type Audit | **PASS** | 4/4 settlement + 1/1 preview hardcodes removed; resolver fail-closes |
| Storage 0% Audit | **PASS** | `seller_commission_rate_override=0.0` forced on storage listings |
| Quantity Audit | **PASS** | 5/5 money-facing sites in `routes/payments.py` fixed |
| Checkout Consolidation | **PARTIAL PASS** | Resolver and quantity fix applied to all 3 endpoints; single-service consolidation deferred to Phase 5 |
| Canonical Fee Engine | **PARTIAL PASS** | `calculate_fee` is the canonical entry point for settlement; `stripe_connect_service` calculators remain thin wrappers; full unification deferred to Phase 5 |
| Settlement | **PASS** | `settle_auction` correctly routes via seller type |
| Receipts/Invoices/PDF | **PASS** | Byte-identical to pre-iter482; iter477 regression confirms |
| Refunds | **BLOCKED** | Refund infrastructure gap remains — Phase 4 target |
| Webhooks | **PASS** | Unchanged; idempotent handlers preserved |
| Idempotency | **PASS** | `payment_idempotency.py` machinery unchanged |
| Frontend Parity | **PASS** (by construction) | FE reads `breakdown` object which now reflects new Partner math automatically |
| Golden Matrix | **PASS** | 24/24 cent-exact tests green |
| Static Financial Audit | **PARTIAL PASS** | Zero remaining silent-fallback `seller_account_type="individual"` in settlement paths; three PARTNER-3% constants remain (Phase 5) |
| Historical Exposure | **BLOCKED** | Preview DB: $0. Production DB not queryable from this environment |
| Deployment | **NOT PERFORMED** | Preview only |

---

### Final Verdict

**Stripe Sandbox: BLOCKED**
**Tax Rule Validation: PARTIAL PASS**
**Seller-Type Audit: PASS**
**Storage 0% Audit: PASS**
**Quantity Audit: PASS**
**Checkout Consolidation: PARTIAL PASS**
**Canonical Fee Engine: PARTIAL PASS**
**Settlement: PASS**
**Receipts/Invoices/PDF: PASS**
**Refunds: BLOCKED**
**Webhooks: PASS**
**Idempotency: PASS**
**Frontend Parity: PASS**
**Golden Matrix: PASS**
**Static Financial Audit: PARTIAL PASS**
**Historical Exposure: BLOCKED**
**Deployment: NOT PERFORMED**

---

# DO NOT DEPLOY

**Reason**: Two mandatory financial gates remain unresolved and the brief explicitly forbids issuing `SAFE TO DEPLOY` while any is BLOCKED:

1. **Stripe Sandbox Proof (Gate 1) is BLOCKED.** The `on_behalf_of` mechanism in `create_destination_charge` is a Stripe Connect settlement-flow change. Static Python replay predicts the intended economics (buyer $110, application_fee $3.45, Partner Connect transfer $106.55, Stripe rail $3.49 on Partner side) but Stripe's *actual* runtime behavior of `on_behalf_of` + `transfer_data.destination` + `application_fee_amount` has NOT been proven end-to-end. Deploying a Partner-money-flow change without live-Stripe sandbox proof risks a class of failure documented in the brief (Section 5: "If the actual Stripe infrastructure produces anything different, STOP").

2. **Refund architecture (Phase 4) is not landed.** For Partner destination charges under the new `on_behalf_of` model, refunds require `application_fee.refund=True` AND `reverse_transfer=True` — neither is currently wired into a production route. Any Partner buyer chargeback would require manual Stripe Dashboard operations.

3. **Non-QC Partner tax accuracy still requires accountant/legal confirmation.** Currently non-QC Partners fall back to QC constants (unchanged behavior; not a regression, but not fully authoritative either).

**What is safe to deploy TODAY** (with additional gates): the storage 4% leakage fix, quantity underbilling fix, and seller-type-resolver hardening are P0 fixes that would improve production if deployed in isolation. But per the brief's Section 41 gate-by-gate rule, we should not peel them off from the Partner Stripe fix — otherwise the deployed system would inconsistently route Partner sales.

**Recommended path to `SAFE TO DEPLOY`**:
1. Provide `STRIPE_API_KEY=sk_test_...` and a test-mode Partner Connect account
2. Execute the Phase 1 sandbox proof (I'll write the isolated script)
3. Reconcile the sandbox cent-values to the Model A₁ prediction
4. If they match, implement the Phase 4 refund handler for Partner destination charges
5. Run a full golden-test sweep including a live Stripe test refund
6. Query production DB for historical exposure (out-of-band)
7. Then and only then, re-emit `SAFE TO DEPLOY`

Until those steps complete, iter482 P0 code changes should remain **on the preview branch only**.

---

*End of iter482 Phase 3 P0 Final Report. Awaiting sandbox key + Phase 4 authorization to proceed to `SAFE TO DEPLOY`.*
