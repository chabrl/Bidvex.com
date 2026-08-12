# BidVex — Auction Marketplace PRD

## iter482 — Phase P4 Seller-Controlled Payment Methods (Feb 12, 2026) ✅ COMPLETE — PREVIEW ONLY · DO NOT DEPLOY

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


## iter482 — Phase P4A Foundation: Seller-Controlled Payment Methods (Feb 12, 2026) ✅ COMPLETE — PREVIEW ONLY · DO NOT DEPLOY

**Scope**: Foundation layer — canonical registry, immutable snapshot service, model field addition, idempotent backfill script, 51 unit tests. No checkout, no Stripe wiring, no frontend.

### Files created
- `backend/services/payment_methods_registry.py` — canonical `{stripe, etransfer, cash, cheque}` + aliases + offline/rail helpers
- `backend/services/seller_payment_methods_service.py` — `effective_methods()`, `guard_edit()`, `snapshot_at_first_bid()`, `assert_selection_allowed()`
- `backend/scripts/iter482_p4a_backfill_accepted_payment_methods.py` — idempotent, 36 preview rows backfilled
- `backend/tests/test_iter482_p4a_foundation.py` — 51 tests

### Files modified (schema-only, additive)
- `models/auction_models.py` — `ListingCreate`, `Listing`, `MultiItemListingCreate` gain `accepted_payment_methods`; `Listing` gains `accepted_payment_methods_snapshot` + `accepted_payment_methods_locked_at`
- `models/storage_auction.py` — `StorageAuctionCreate` gains field + validator
- `models/vehicle_models.py` — `VehicleListingCreate` gains field + validator

### Business rules enforced
- ≥ 1 method required; canonical slugs only; aliases normalised on write
- Immutable snapshot at first bid; post-bid edits blocked (`PaymentMethodsLockedError`)
- Buyer selection gated by SNAPSHOT (never live list) if locked
- No silent defaults for new listings; `PaymentMethodsMissingError` on orphan rows
- Legacy singleton `payment_method` retained for backward compatibility

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
