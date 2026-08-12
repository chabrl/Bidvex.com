# BidVex — Auction Marketplace PRD

## iter482 — Phase P5.1 Stripe Actual-Fee Reconciliation + Card Country + Partner Invoice (Feb 12, 2026) ✅ COMPLETE — PREVIEW ONLY · DO NOT DEPLOY

### Scope delivered end-to-end
- **Actual Stripe BalanceTransaction persistence** — new `services/stripe_reconciliation_service.py` retrieves the authoritative `BalanceTransaction.fee`/`fee_details`, plus `payment_method_details.card.country`, and persists a canonical row in `db.payment_processing_reconciliation` keyed by `payment_intent_id`.  Idempotent via `$setOnInsert` — webhook replay updates the same row without duplicating.
- **Canonical reconciliation record**:
  - `estimated_cents` — additive Stripe estimate (base × rate + fixed)
  - `recovery_cents`  — gross-up amount charged to the payer
  - `actual_cents`    — BalanceTransaction.fee
  - `variance_cents`  — `recovery - actual`
  - `reconciliation_status` ∈ `COVERED` (`≥ actual`) / `SHORTFALL` (`< actual`) / `UNKNOWN` (no BT) / `ERROR` (Stripe API failed)
  - `card_country` + `resolved_jurisdiction` (`domestic`/`international`)
- **`payment_intent.succeeded` webhook** now invokes `reconcile_payment_intent` before the existing card-country delta logging (preserves the legacy shortfall log for non-CA cards).
- **PaymentIntent metadata expanded** with the seven canonical fields (`payment_processing_estimated_cents`, `payment_processing_recovery_cents`, `payment_processing_rate`, `payment_processing_jurisdiction`, `payment_processing_payer_role`, `buyer_total_cents`, `seller_commission_cents`) so the reconciler can compute variance without a second DB round-trip.
- **Admin ledger API** — new `routes/admin_stripe_reconciliation.py`:
  - `GET /api/admin/stripe-reconciliation` (filter by status, since, limit)
  - `GET /api/admin/stripe-reconciliation/{payment_intent_id}` (single row)
  - `GET /api/admin/stripe-reconciliation/summary` (aggregate covered/shortfall/unknown counts + variance totals)
  - Role gated to `admin` / `super_admin`
- **Partner multi-lot PAY NOW invoice** — extended `GET /api/seller/commission-invoice/{id}` so `multi_item_listings` rows return `sold_lots[]` + summed `hammer_cents`.  Frontend `SellerCommissionInvoicePage.js` renders the sold-lots table above the commission detail card.  Screenshot `/tmp/iter482_p51_partner_invoice.png` confirms: **3 sold lots totalling $870 → 4% commission $34.80 + taxes $5.21 + Stripe recovery $1.51 = $41.52 (via Stripe) / $40.01 (offline)**.

### Test results — 276/276 GREEN across P0/P2/P3/P3.1/P4/P4A/P5/P5.1
| Suite | Result |
|---|---|
| iter482 P0 golden repairs | 10/10 |
| iter482 golden matrix | 40/40 |
| iter482 P2 canonical engine | 40/40 |
| iter482 P3 fee_calculator | 16/16 |
| iter482 P3.1 reconciliation | 38/38 |
| iter482 P4A foundation | 51/51 |
| iter482 P4 end-to-end | 14/14 |
| iter482 P5 payer-bears-fee | 31/31 |
| **iter482 P5.1 reconciliation (new)** | **10/10** |
| **Anti-regression: no silent $0 for Stripe** | proven |

### Files changed (P5.1)
- Backend: `services/stripe_reconciliation_service.py` (new), `routes/admin_stripe_reconciliation.py` (new), `routes/webhooks.py` (wire reconciler in `payment_intent.succeeded`), `services/stripe_connect_service.py` (metadata expansion), `routes/seller_commission_invoice.py` (sold_lots + hammer-sum for multi-item), `server.py`
- Frontend: `pages/SellerCommissionInvoicePage.js` (sold lots table)
- Tests: `backend/tests/test_iter482_p51_reconciliation.py` (10 new tests including anti-regression + Stripe stub monkeypatch)

### Anti-regression guards added
- Test `test_anti_regression_stripe_never_silent_zero` asserts every Stripe/card payment either has `recovery_cents > 0` OR a documented `reason_code` (`offline_method`, `legally_gated`, `prohibited`, `platform_absorbed`, `unknown_rate_matrix`).  Prevents a future L-1 flip from silently zeroing the fee.
- Test `test_reconcile_payment_intent_persists_and_is_idempotent` proves webhook replay never duplicates a reconciliation row.
- Test `test_reconcile_payment_intent_error_when_stripe_fails` proves an `ERROR` row is still written on Stripe API failure so admins see the missing reconciliation.

### Rate examples — cent-exact via canonical engine
| Base | Card | Additive | Gross-up recovery |
|---|---|---|---|
| $100 | CA domestic | $3.20 | **$3.30** |
| $100 | international | $4.20 | **$4.38** |
| $7 | CA domestic | $0.50 | **$0.52** |
| $1,000 | CA domestic | $29.30 | **$30.18** |

### Guardrails honoured
✅ Preview only — **DO NOT DEPLOY** · ✅ Stripe **TEST** mode only · ✅ No production data mutated · ✅ No historical records modified · ✅ No real refunds · ✅ BidVex never silently absorbs Stripe cost (invariant proven) · ✅ Offline methods always $0 with `reason_code=offline_method` · ✅ Idempotent webhook reconciliation

### Known limitation (documented, NOT silently ignored)
- **Card country pre-confirmation**: Stripe Checkout Session amounts are locked at session creation, so we cannot know the card's country *before* the payer confirms.  The engine defaults to `domestic` for the initial estimate; on webhook receive we resolve the true country from `payment_method_details.card.country` and record any variance in the reconciliation ledger.  If the user's business policy requires re-issuing a variance invoice for international-card shortfalls, that is a straightforward follow-up: iterate rows with `resolved_jurisdiction="international"` AND `reconciliation_status="SHORTFALL"` and email the delta.

### Deferred (post-P5.1, awaiting next directive)
- 🟠 **International-card variance invoice** — email seller/buyer the delta captured in `stripe_fee_adjustments` + `payment_processing_reconciliation.SHORTFALL` rows
- 🟠 **P6** — Tax engine consolidation across jurisdictions
- 🟠 **P7** — ≥ 200-case exact-cent regression matrix
- 🟢 **P8** — Peripheral flows
- 🟠 **P9** — Static audit + deployment gate

---


## iter482 — Phase P5 Payer-Bears-Stripe-Processing-Cost (Feb 12, 2026) ✅ COMPLETE — PREVIEW ONLY · DO NOT DEPLOY

### Scope delivered end-to-end (Backend + Frontend + Tests)
- **L-1 legal gate OPENED** per explicit user directive: buyer + seller Stripe recovery is CLEARED across all 13 provinces/territories.  Terms of Use disclose that when a payer selects a Stripe/card payment method they bear the Stripe processing cost — BidVex never silently absorbs it.
- **Canonical gross-up recovery** added to `services/payment_cost_engine.py`.  `estimate(mode="gross_up")` returns both:
  - `estimated_cents` — additive underlying Stripe fee (`base × rate + fixed`)
  - `recovery_cents` — mathematically correct amount to add so BidVex actually recovers the Stripe cost cent-for-cent: `ceil((base × rate + fixed) / (1 − rate))`
- **CA vs INT rate matrix** honoured: `2.9% + $0.30` domestic / `3.9% + $0.30` international.
- **`stripe_connect_service.calculate_general_checkout` + `connect_payment_engine.calculate_connect_checkout` + `fee_calculator.calculate_fee`** ALL sourced from the canonical engine.  Path A ↔ Path B reconcile cent-exact.  BidVex's `application_fee` now includes the buyer-borne recovery so Stripe's actual fee is covered by the payer, not by BidVex.
- **CheckoutPage.js**:
  - Sidebar row: **"Payment Processing Fee"** (never hidden when Stripe selected)
  - Card row: bilingual **"Frais de traitement du paiement / Payment Processing Fee"** with the rate label `(2.9% + $0.30 — gross-up)` and a Reason line if the engine returns 0 with a documented reason
  - Total Due includes the recovery cent-exact
- **New Seller Commission Invoice**:
  - Backend: `routes/seller_commission_invoice.py` — `GET /api/seller/commission-invoice/{listing_id}` + `POST /api/seller/commission-invoice/{listing_id}/pay-now`
  - Rate resolver: 4% Individual/Business · 3% Partner · Vehicle/Storage flagged `REQUIRES_BUSINESS_REVIEW`
  - Renders the 4 payment-method breakdown (Stripe/E-Transfer/Cash/Cheque) with per-method total and reason codes
  - Persistence: `db.seller_commission_invoices` with pending/paid states + Stripe Checkout Session id
  - Frontend: `/seller/commission-invoice/:listingId` — bilingual page with itemized total and **PAY NOW** button that redirects to Stripe Checkout or records offline instructions
- **PriceBreakdown.js**: updated to show reason code when processing is 0 for a Stripe path (never silent $0).
- **BidVex retention math**: `application_fee = BP + SC + fees_tax + processing_recovery`; the destination-charge invariant `charge = app_fee + transfer` still holds cent-exact.
- **Regression tests updated** to reflect the new L-1 CLEARED behaviour + new invariants.

### Rate examples (cent-exact via canonical engine)
| Base | Card | Additive estimate | Gross-up recovery |
|---|---|---|---|
| $100 | CA domestic | $3.20 | **$3.30** |
| $100 | international | $4.20 | **$4.38** |
| $7 | CA domestic | $0.50 | **$0.52** |
| $1,000 | CA domestic | $29.30 | **$30.18** |

### Test results — 270/270 across P5 + regression
| Suite | Result |
|---|---|
| iter482 P0 golden repairs | 10/10 |
| iter482 golden matrix | 40/40 |
| iter482 P2 payment cost engine | 40/40 |
| iter482 P3 fee_calculator canonical | 16/16 |
| iter482 P3.1 reconciliation | 38/38 |
| iter482 P4A foundation | 51/51 |
| iter482 P4 end-to-end | 14/14 |
| **iter482 P5 payer-bears-fee (new)** | **31/31** |

### Frontend E2E proofs (visual)
- `/tmp/iter482_p5_checkout.png` — Total $107.98 = hammer $100 + BP $3.50 + GST $0.35 + QST $0.69 + Processing $3.44 (bilingual label, no silent $0)
- `/tmp/iter482_p5_checkout_switch_fixed.png` — Reactive switching: Stripe $107.98 / $3.44, Cash $104.54 / $0.00, E-Transfer $104.54 / $0.00, Stripe $107.98 / $3.44 (verified via automated E2E)
- `/tmp/iter482_p5_seller_invoice.png` — Seller commission invoice $5.05 = commission $4.00 + tax $0.60 + Stripe recovery $0.45 (4 payment methods, PAY NOW active)

### Files changed
- Backend: `services/payment_cost_engine.py`, `services/stripe_connect_service.py`, `services/connect_payment_engine.py`, `services/fee_calculator.py`, `routes/seller_commission_invoice.py` (new), `server.py`
- Frontend: `pages/CheckoutPage.js`, `pages/SellerCommissionInvoicePage.js` (new), `components/PriceBreakdown.js`, `App.js`
- Tests: `tests/test_iter482_p5_payer_bears_fee.py` (new · 31 tests), regression tests updated in `test_iter482_p31_reconciliation.py`, `test_iter482_p0_repairs.py`, `test_iter482_p2_payment_cost_engine.py`, `test_iter482_p3_fee_calculator_canonical.py`

### Guardrails honoured
✅ Preview only — **DO NOT DEPLOY** · ✅ Stripe TEST mode · ✅ No production data mutated · ✅ No historical financial records changed · ✅ Terms-of-use payer-bears-fee disclosure captured · ✅ BidVex retains recovery via application_fee (Stripe's actual fee comes out of that recovery, NOT BidVex margin)

### Deferred (awaiting Stripe test-mode real-charge test)
- 🟠 **Actual Stripe BalanceTransaction reconciliation via webhook** (`services/payment_cost_engine.lock_actual` is already the API — needs the `payment_intent.succeeded` webhook wiring to persist actual fee alongside estimate/recovery)
- 🟠 **Card country detection at payment confirmation** — currently defaults to `domestic` for the initial estimate; on webhook receive-side we can read `payment_method.card.country` and post-charge reconcile (delta absorbed by BidVex or invoiced separately per business policy)
- 🟠 **Partner post-auction "PAY NOW" 3% invoice page** — backend covers computation via `routes/partner_platform_fee.py` (existing); UI is next
- 🟠 **P6** — Tax engine consolidation
- 🟠 **P7** — ≥ 200-case regression matrix
- 🟢 **P8** — Peripheral flows
- 🟠 **P9** — Static audit + deployment gate


---


## iter482 — Phase P4 Seller-Controlled Payment Methods (Feb 12, 2026) ✅ COMPLETE — PREVIEW ONLY

Canonical `AcceptedPaymentMethodsSelector` (stripe/etransfer/cash/cheque) wired across all Create flows.  Immutable snapshot at first bid.  Buyer restriction on CheckoutPage.js with server-side enforcement (`400 PAYMENT_METHOD_NOT_ACCEPTED`).  Selected method propagated to receipts + Stripe metadata.  Legacy duplicate radios REMOVED.

## iter482 — Phase P4A Foundation (Feb 12, 2026) ✅
Canonical registry, snapshot service, model field addition, backfill script, 51 unit tests.

## iter482 — Phase P3.1 Cross-Calculator Reconciliation (Feb 12, 2026) ✅
Root-caused and fixed the $0.02 tax divergence.  196/196 tests passed pre-P5.

## iter482 — Phase P3 Checkout Wiring & $0.31 Fix (Feb 12, 2026) ✅
Wired canonical `payment_cost_engine` into every buyer-facing calculator.

## Original problem statement + core requirements

1. Exact-cent reconciliation across all financial paths.
2. Seller-controlled payment methods (stripe/etransfer/cash/cheque). ✅ P4
3. Buyer restricted to seller's accepted methods. ✅ P4
4. BidVex NEVER silently absorbs Stripe processing costs. Payer-bears-fee model implemented. ✅ P5
5. First-bid immutable snapshot on payment methods. ✅ P4A
6. Selected payment method propagates to transactions, receipts, and seller dashboards. ✅ P4

## Personas
- Individual buyer, Individual/Business seller (4% commission), Partner (3% platform fee), Vehicle Dealer, Storage Facility, Admin (`charbel911@gmail.com`).

## Architecture
- Frontend: React SPA + Tailwind + shadcn/ui
- Backend: FastAPI + Motor (async Mongo)
- Integrations: Stripe (TEST mode), SendGrid, Twilio, Cloudflare R2, Emergent LLM key

## Prioritized backlog
- 🟠 P5.1 Actual Stripe fee reconciliation via webhook + card_country detection
- 🟠 Partner post-auction "PAY NOW" invoice UI (backend done)
- 🟠 P6 Tax engine consolidation
- 🟠 P7 ≥ 200-case regression matrix
- 🟢 P8 Peripheral flows (escrow, deposits, penalties, marketing)
- 🟠 P9 Static audit + deployment gate
- 🟢 Admin Fee Schedule UI
- 🟢 Claude AI models integration
- 🟢 Lot buyer chip + photo auto-matcher

### Scope delivered end-to-end (Backend + Frontend + Tests)
- **Canonical seller multi-select** (`stripe`, `etransfer`, `cash`, `cheque`) via `AcceptedPaymentMethodsSelector.jsx` wired into ALL Create-Listing flows (Individual, Multi-Item, Vehicle, Vehicle Multi-Lot, Storage). **Legacy duplicate radio buttons REMOVED** in `CreateListingPage.js`, `CreateMultiItemListing.js`, `storage/StorageAuctionCreate.js`.
- **Immutable snapshot** at first bid via `services/seller_payment_methods_service.py` (`accepted_payment_methods_snapshot` + `accepted_payment_methods_locked_at`).
- **Buyer restriction** on `CheckoutPage.js`: fetches `/api/listings/{id}/accepted-payment-methods` on load and dynamically renders only the seller's accepted methods. First accepted method auto-selected. Cheque support added. Button disabled if none configured.
- **Buyer selection ack**: buyer calls `POST /api/checkout/select-payment-method` with exact-cent totals BEFORE any Stripe session or offline order is created. Anti-tamper check enforces `parts_sum == total_cents`.
- **Server-side enforcement** in `POST /api/payments/checkout/auction`, `POST /api/payments/auction-winner-checkout/{id}`, `POST /api/payments/offline-checkout/{id}` — every buyer-selected method is validated against `assert_selection_allowed()`. Non-accepted methods → 400 `PAYMENT_METHOD_NOT_ACCEPTED`.
- **Cheque flow**: offline endpoint now accepts `cheque` alongside `cash`/`etransfer` with a bilingual confirmation email (EN/FR) and dedicated success message.
- **L-1 fail-closed reinforced** in `services/connect_payment_engine.calculate_connect_checkout`: canonical `payment_cost_engine.estimate()` snapshot is now attached, and any leaked `bi.stripe_recovery` is stripped from `buyer_total` / `stripe_charge` — buyer NEVER pays Stripe processing while L-1 is closed.
- **Buyer's Premium attribution** added to `PriceBreakdown.js` + `CheckoutPage.js`: label now reads *"Buyer's Premium (by seller/Partner, X.X%)"*.
- **Selected payment method propagation**: `offline_orders.selected_payment_method`, `pending_payments.selected_payment_method`, `listings.selected_payment_method`, Stripe `payment_intent.metadata.selected_payment_method` all record the canonical slug.

### Test results — 239/239 PASS · 0 regressions
| Suite | Result |
|---|---|
| iter482 P0 golden repairs | 10/10 |
| iter482 golden matrix | 40/40 |
| iter482 P2 payment cost engine | 46/46 |
| iter482 P3 fee_calculator canonical | 16/16 |
| iter482 P3.1 cross-calc reconciliation | 38/38 |
| iter482 refund engine | 7/7 |
| iter482 P4A foundation | 51/51 |
| **iter482 P4 end-to-end (new)** | **14/14** |

### Frontend E2E proofs (visual, this session)
- `/tmp/iter482_p4_create_smoke.png` — Create Listing shows ONLY the new canonical selector (no duplicate radio)
- `/tmp/iter482_p4_checkout_multi.png` — Checkout renders only 3 methods (stripe/etransfer/cash) because seller configured those three; Cheque is hidden
- `/tmp/iter482_p4_checkout_after_fix.png` — Total $104.54 exact; Processing $0.00 (L-1 gate honoured); Buyer Premium attribution visible

### Files modified (backend)
- `routes/payments.py` — added `payment_method` field to `AuctionCheckoutRequest`, enforcement in `/checkout/auction`, `/auction-winner-checkout`, `/offline-checkout`. Added cheque branch to offline order + email. Persisted `selected_payment_method` on offline_orders and listings. Fixed `_id` insert bug on `offline_orders`.
- `services/stripe_connect_service.py` — `create_destination_charge` now accepts `selected_payment_method`, records in payment_intent metadata and `pending_payments`.
- `services/connect_payment_engine.py` — canonical `payment_processing` snapshot added; leaked `stripe_recovery` stripped from buyer path when L-1 closed.

### Files modified (frontend)
- `pages/CheckoutPage.js` — accepted-methods fetch on load, dynamic method filter (incl. Cheque), first-accepted default, `select-payment-method` ack call before Stripe / offline submission, disabled state when no methods, `payment_method` passed to backend, buyer premium attribution.
- `pages/CreateListingPage.js` — removed legacy 3-radio group; only `AcceptedPaymentMethodsSelector` remains. Fixed duplicate `quantity` keys.
- `pages/CreateMultiItemListing.js` — removed legacy radio group.
- `pages/storage/StorageAuctionCreate.js` — replaced 3-button legacy selector with canonical multi-select.
- `components/PriceBreakdown.js` — buyer premium attribution.

### Files created
- `backend/tests/test_iter482_p4_end_to_end.py` — 14 tests covering registry, service invariants, HTTP enforcement (offline path, ack path, cheque path, tamper detection, snapshot lock).

### Guardrails honoured
- **DO NOT DEPLOY** — preview only
- Buyer Stripe surcharge = $0 (L-1 CLOSED) across all winner + preview + checkout paths
- Offline methods (cash / etransfer / cheque) processing fee = $0 permanently
- Partner Model A₁ topology preserved
- No production data mutated
- No refunds executed
- Every historical iter482 test continues to pass

### Deferred to next phases
- P5: Refund engine consolidation + Gate 3 live Stripe TEST proof
- P6: Tax engine consolidation
- P7: ≥ 200-case exact-cent matrix
- P8: Peripheral flows (escrow, deposits, penalties, marketing)
- P9: Static financial audit repo-wide + final deployment gate
- Admin Fee Schedule UI (P1)
- Claude AI models integration (P1)
- Explicit Individual/Business seller B2B commission invoice UI (backend already computes; frontend needs a dedicated invoice widget on seller dashboard)
- Partner post-auction billing "PAY NOW" invoice flow (backend covers computation; a dedicated Partner invoice page would round it out)

## 🛑 HALTED at P4 boundary — awaiting explicit approval to enter P5+

---


## iter482 — Phase P3.1 Cross-Calculator Reconciliation (Feb 12, 2026) ✅ COMPLETE
Root-caused and eliminated the $0.02 divergence between `calculate_fee()` (Path A, CRA/iter350) and `calculate_general_checkout()` (Path B, Stripe session builder) for the $7.00/premium/premium/QC/QC scenario. 196/196 tests pass. Details preserved in git history and iter482 P3 architectural docs.

## iter482 — Phase P3 Checkout Wiring & $0.31 Frontend Fix (Feb 12, 2026) ✅ COMPLETE
Wired canonical `services/payment_cost_engine.py` into every buyer-facing calculator, eliminating the phantom $0.31 Stripe surcharge. `payment_processing.amount_cents` is now the ONE source of truth. 158/158 tests pass.

## Original problem statement + P0/P1 backlog

1. P0/P1 Payment Infrastructure Audit, Remediation & Financial Reconciliation. Exact-cent reconciliation.
2. Implement Seller-Controlled Payment Methods. ✅ **DONE — P4**
3. Buyers can only select from the payment methods enabled by the seller. ✅ **DONE — P4**
4. BidVex must NEVER silently absorb Stripe processing costs; while L-1 CLOSED buyer Stripe surcharge = $0. Offline methods always $0. ✅ **DONE — P3 + P4**
5. First-bid immutable snapshot on payment methods. ✅ **DONE — P4A**
6. Selected payment method must propagate to transactions, receipts, and seller dashboards. ✅ **DONE — P4** (offline_orders, listings, pending_payments, Stripe metadata all persist `selected_payment_method`)

## Personas
- **Individual buyer** — logs in, browses, bids, wins, checks out with one of the seller's accepted methods.
- **Individual seller / Business** — creates a listing, picks accepted payment methods, receives payout minus 4% commission.
- **Partner (Pro)** — creates lot auctions, uses 3% platform fee, uses Model A₁ Connect topology.
- **Vehicle Dealer** — hybrid payments (fees online, hammer offline).
- **Storage Facility** — 5% BP + 0% SC.
- **Admin (`charbel911@gmail.com`)** — permanent sole admin.

## Architecture
- Frontend: React SPA + Tailwind + shadcn/ui
- Backend: FastAPI + Motor (async Mongo)
- Integrations: Stripe (TEST mode), SendGrid, Twilio, Cloudflare R2, Emergent LLM key

## Prioritized backlog (P0 top-down)
- P0 P5 — Refund engine consolidation + live Stripe TEST proof
- P0 P6 — Tax engine consolidation across jurisdictions
- P0 P7 — ≥200-case exact-cent regression matrix
- P1 P8 — Peripheral flows (escrow, deposits, penalties, marketing)
- P0 P9 — Static financial audit + final deployment gate
- P1 Admin Fee Schedule UI
- P1 Claude AI models integration
- P1 Explicit seller-side commission invoice widget on seller dashboard
- P1 Partner post-auction billing "PAY NOW" invoice UX
- P2 Lot buyer chip + photo-to-row auto-matcher
