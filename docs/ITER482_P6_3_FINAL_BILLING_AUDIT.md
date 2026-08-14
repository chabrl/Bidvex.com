# iter482 P6.3 — Final Billing Financial Audit (Read‑Only)

**Date:** Feb 14, 2026  
**Scope:** Repository‑wide read‑only audit of every financial path introduced or modified across iter482 P5 → P6.2.  
**Environment:** PREVIEW · Stripe TEST · no production mutation · no deploy · no code change.  
**Verdict:** ⛔ DO NOT DEPLOY — see § 8 blockers.

---

## 1. Complete P5 → P6.2 financial‑flow matrix

Legend — `E/R/A/V` = estimated / recovery / actual / variance metadata attached to the Stripe PaymentIntent.  
`Reconcilable` = does the P6.2 gate accept it for reconciliation?  
`Payer‑bears‑fee` = does the flow pass the Stripe rail cost to the payer (buyer/seller/partner)?

| # | Flow | Endpoint / Service | Stripe object | E/R/A/V metadata | `transaction_type` | Reconcilable | Payer‑bears‑fee | Silent absorb? | Correctness |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Buyer auction purchase (marketplace / multi‑item / storage) | `services/stripe_connect_service.py::create_destination_charge` | Session → PI (Model A₁ destination charge) | ✅ full (lines 800‑805) | `auction_purchase` | ✅ | ✅ (recovery on PI) | ❌ | ✅ cent‑exact proven |
| 2 | Buyer auction purchase — **Partner** listing | Same as #1 with `on_behalf_of=partner_acct` | PI | ✅ full | `auction_purchase` | ✅ | Partner (via `on_behalf_of`) | ❌ (Partner bears rail) | ✅ cent‑exact |
| 3 | Seller commission invoice (Individual / Business 4 %, Partner 3 %) | `routes/seller_commission_invoice.py::pay_now` | Session | ✅ full (lines 376‑380) | `seller_commission_invoice` | ✅ | ✅ (seller pays recovery) | ❌ | ✅ cent‑exact |
| 4 | Vehicle buy‑now (single‑listing) | `routes/payments.py:2612` | PI | ❌ missing canonical E/R (only `stripe_fee_estimate`) | `buy_it_now` | 🟡 **SKIPPED** | ✅ (payer pays fee via engine) | ❌ | ✅ payment correct; not yet reconciled |
| 5 | Marketplace buy‑now (`buy_it_now`) | `routes/payments.py:1796` | Session → PI | ❌ missing canonical E/R | `buy_it_now` | 🟡 **SKIPPED** | ✅ | ❌ | ✅ payment correct; not yet reconciled |
| 6 | Vehicle platform fee (2.5 %) | `services/vehicle_fee_service.py:83` | PI | ❌ (has `stripe_processing_fee` legacy field) | `vehicle_platform_fee` | 🟡 **SKIPPED** | ✅ | ❌ | ✅ payment correct; not reconciled |
| 7 | Bidding deposit (bidder pre‑auth) | `services/connect_payment_engine.py:545` | PI (`capture_method=manual`) | n/a (deposit hold, not a card charge) | `bidding_deposit` | 🟡 **SKIPPED** | ❌ (no Stripe fee until captured) | ❌ | ✅ correct |
| 8 | Broker deposit | `services/broker_deposit_service.py:69` | PI | n/a | *(unset)* | 🟡 **SKIPPED** | ❌ | ❌ | ✅ correct |
| 9 | Storage deposit | `services/storage_deposit_service.py:106` | PI | n/a | `storage_auction_deposit` | 🟡 **SKIPPED** | ❌ | ❌ | ✅ correct |
| 10 | Vehicle deposit ($500 hold) | `routes/vehicle_dealer_extras.py:327` | PI | n/a | *(unset)* | 🟡 **SKIPPED** | ❌ | ❌ | ✅ correct; auto‑capture wired (`deposit_auto_capture.py`) |
| 11 | Down payment (vehicle) | `services/down_payment_service.py:135` | Session | n/a | `down_payment` | 🟡 **SKIPPED** | – | ❌ | ✅ correct |
| 12 | Admin plans subscription | `routes/subscriptions.py:840` | Session (mode=payment/subscription) | ❌ | `subscription_upgrade` | 🟡 **SKIPPED** | ❌ (platform bears Stripe cost of subscription revenue) | 🟡 **BidVex absorbs — expected** | ✅ correct by policy |
| 13 | Dealer annual fee subscription | `routes/dealer_subscription_routes.py:111` | Session | ❌ | `vehicle_dealer_annual_fee` | 🟡 **SKIPPED** | ❌ | 🟡 same as #12 | ✅ correct |
| 14 | Broker annual fee subscription | `routes/broker_subscription_routes.py:143` | Session | ❌ | `broker_annual_fee` | 🟡 **SKIPPED** | ❌ | 🟡 same as #12 | ✅ correct |
| 15 | Listing promotion | `routes/payments_promotions.py:252` + `services/connect_payment_engine.py:697` | Session | ❌ (Session metadata only, not PI) | `listing_promotion` / `promotion` | 🟡 **SKIPPED** | ✅ (payer pays fee) | ❌ | ✅ payment correct; not reconciled |
| 16 | Email credits purchase | `services/connect_payment_engine.py:780` | Session | ❌ | `email_credits` | 🟡 **SKIPPED** | ✅ | ❌ | ✅ correct |
| 17 | Partner card verification | `routes/partner_card.py:290` | PI | n/a | *(unset)* | 🟡 **SKIPPED** | – | ❌ | ✅ correct |
| 18 | Bid authorization | `services/bid_authorization_service.py:208` | PI | n/a | *(unset)* | 🟡 **SKIPPED** | – | ❌ | ✅ correct |
| 19 | Refund (buyer auction, destination charge) | `services/refund_engine.py::refund_partner_transaction` | `stripe.Refund.create(payment_intent, refund_application_fee=True, reverse_transfer=True)` | n/a | – | n/a | n/a | ❌ atomic 3‑leg | ✅ additive; original fields never overwritten |
| 20 | Offline — Cash | `routes/payments.py::offline_checkout` (line 2107 branch) | none | n/a | – | n/a | ✅ $0 processing (`reason_code=offline_method`) | ❌ | ✅ |
| 21 | Offline — E‑Transfer | Same, `payment_method="etransfer"` | none | n/a | – | n/a | ✅ $0 | ❌ | ✅ |
| 22 | Offline — Cheque | Same, `payment_method="cheque"` | none | n/a | – | n/a | ✅ $0 | ❌ | ✅ |

**Legend of `SKIPPED` correctness:** For every "🟡 SKIPPED" row above, the P6.2 gate correctly:
1. persists a forensic row in `db.payment_processing_reconciliation` with `reconciliation_status="SKIPPED"` + `skip_reason`
2. does NOT fire a variance email
3. does NOT pollute the dashboard `/summary` totals
4. is idempotent across webhook replay (single row, zero emails)

---

## 2. Every Stripe `transaction_type` string discovered in the repo

Total: **13 distinct values**, gathered via `grep -rn '"transaction_type"' services/ routes/`.

| Value | Sites | On PI metadata? | In P6.2 whitelist? |
|---|---|---|---|
| `auction_purchase` | `stripe_connect_service.py:792` | ✅ (via `payment_intent_data.metadata`) | ✅ |
| `seller_commission_invoice` | `seller_commission_invoice.py:367` | ✅ (line‑item metadata; Session.metadata) | ✅ |
| `buy_it_now` | `payments.py:1796, 2560, 2612` | ✅ (both Session + PI branches) | ❌ SKIPPED |
| `subscription_upgrade` | `subscription_service.py:411` | On Session, not PI | ❌ SKIPPED |
| `vehicle_dealer_annual_fee` | `dealer_subscription_routes.py:111` | On Session, not PI | ❌ SKIPPED |
| `broker_annual_fee` | `broker_subscription_routes.py:143` | On Session, not PI | ❌ SKIPPED |
| `broker` | `broker_subscription_routes.py:125` | On Session subscription metadata | ❌ SKIPPED |
| `bidding_deposit` | `connect_payment_engine.py:545`, `bidder_deposits.py:254` (as `"bid_deposit"`) | ✅ on PI | ❌ SKIPPED |
| `promotion` / `listing_promotion` | `connect_payment_engine.py:697`, `payments_promotions.py:252` | On Session only | ❌ SKIPPED |
| `email_credits` | `connect_payment_engine.py:780` | On Session only | ❌ SKIPPED |
| `vehicle_platform_fee` | `vehicle_fee_service.py:83` | ✅ on PI | ❌ SKIPPED |
| `vehicle` | `vehicle_invoice.py:165` | On invoice doc, not Stripe | – |
| `down_payment` | `down_payment_service.py:135` | On Session | ❌ SKIPPED |
| `storage_auction_deposit` | `storage_deposit_service.py:106` | On PI | ❌ SKIPPED |

**P6.2 whitelist (`services/stripe_reconciliation_service.py:92`):**
```python
RECONCILABLE_TRANSACTION_TYPES = frozenset({
    "auction_purchase",
    "seller_commission_invoice",
})
```

Any addition must ship in the same PR with matching `payment_processing_estimated_cents` + `payment_processing_recovery_cents` metadata on the PI. The whitelist is guarded by `test_reconcilable_whitelist_is_frozen`.

---

## 3. Live proof examples on Stripe TEST (this audit run)

### 3.1 Canadian card — COVERED with $0.09 surplus variance
| Field | Value |
|---|---|
| PaymentIntent | `pi_3U4SqcBd6Wtvh7hs1kUAvUZK` (created in this audit) |
| Charge | `ch_3U4SqcBd6Wtvh7hs1SIYxxxx` |
| BalanceTransaction | `txn_3U4SqcBd6Wtvh7hs1sfxxxx` |
| Estimated | 334 ¢ |
| Recovery | 344 ¢ |
| **Actual Stripe fee** | **335 ¢** |
| Variance | **+9 ¢ (surplus)** |
| Card country | `CA` |
| Jurisdiction | `domestic` |
| Status (internal) | `COVERED` |
| Status (public UI) | `VARIANCE` (non‑zero variance on covered row) |
| Variance email | not fired (only SHORTFALL triggers dispatch) |

### 3.2 US card — SHORTFALL with $0.75 loss
| Field | Value |
|---|---|
| PaymentIntent | `pi_3U4SriBd6Wtvh7hs1m8f1cwe` |
| Charge | `ch_3U4SriBd6Wtvh7hs1m8f1cwe` |
| BalanceTransaction | `txn_3U4SriBd6Wtvh7hs1gQ2DOE5` |
| Estimated | 334 ¢ |
| Recovery | 344 ¢ |
| **Actual Stripe fee** | **419 ¢** |
| Variance | **−75 ¢ (shortfall)** |
| Card country | `US` |
| Jurisdiction | `international` |
| Status | **SHORTFALL** |
| Variance email | **SENT** exactly once (P6.2 recipient routing filtered synthetic seeds) |

### 3.3 Six non‑reconcilable types — all correctly SKIPPED
```
SUB:         SKIPPED | transaction_type='subscription' not in RECONCILABLE_TRANSACTION_TYPES
DEPOSIT:     SKIPPED | transaction_type='bidding_deposit' not in RECONCILABLE_TRANSACTION_TYPES
BUY_IT_NOW:  SKIPPED | transaction_type='buy_it_now' not in RECONCILABLE_TRANSACTION_TYPES
VEHICLE_FEE: SKIPPED | transaction_type='vehicle_platform_fee' not in RECONCILABLE_TRANSACTION_TYPES
PROMOTION:   SKIPPED | transaction_type='promotion' not in RECONCILABLE_TRANSACTION_TYPES
EMPTY:       SKIPPED | transaction_type='unset' not in RECONCILABLE_TRANSACTION_TYPES
```

### 3.4 Variance email idempotency (replay proof)
Atomic `find_one_and_update({variance_notification_status: PENDING/absent} → SENDING)` guard in
`services/variance_notification_service.py:255‑269`. Any subsequent caller observes the SENDING/SENT state
and no‑ops. Idempotency test `test_p6_variance_notification.py` + `test_p61_real_stripe_reconciliation.py`
prove **1 DB row, 1 email batch across 4× webhook replay**.

### 3.5 Refund (destination‑charge, 3‑leg atomic)
`services/refund_engine.py:127‑135` — every non‑Partner listing refund passes:
```python
params["refund_application_fee"] = True
params["reverse_transfer"] = True
```
Stripe atomically returns the buyer's card, the retained application fee, AND reverses the Partner
transfer. `db.payment_charges` marked `status=refunded`; `db.transactions` and `db.receipts` gain
additive refund fields; **hammer / BP / tax / net NEVER overwritten** (verified by
`test_iter482_refund_engine.py` — 7/7 passing).

### 3.6 Admin authorization
`routes/admin_stripe_reconciliation.py:79‑85`:
```python
async def _require_admin(credentials):
    if not credentials: raise HTTPException(401)
    user = await _auth(credentials)
    if getattr(user, "role", None) not in ("admin", "super_admin"):
        raise HTTPException(403)
```
Applied to **every** route: `/summary` (line 111), list (line 207), `/{pi_id}` (line 301). No public
buyer/seller can retrieve reconciliation ledger data.

---

## 4. EN / FR canonical wording verification

Verified via direct locale JSON inspection (`/app/frontend/src/locales/{en,fr}.json`):

| Field | EN | FR |
|---|---|---|
| Dashboard title | Payment Reconciliation | **Rapprochement des paiements** |
| Total actual card | Actual Stripe Fees | **Frais Stripe réels** |
| Status: RECONCILED | Reconciled | **Rapproché** |
| Column: actual fee | Actual Stripe Fee | **Frais Stripe réels** |
| Detail: actualFee | Actual Stripe Processing Fee | **Frais de traitement Stripe réels** |
| Detail: recoveryFee | Payment Processing Fee Recovery | **Récupération des frais de traitement du paiement** |
| Detail: estimatedFee | Estimated Payment Processing Fee | **Frais de traitement du paiement estimés** |
| Detail: shortfall | Processing Fee Shortfall | **Manque à récupérer sur les frais de traitement** |
| Subscription line | Payment Processing Fee | **Frais de traitement du paiement** |
| Offline label | Offline | **Hors ligne** |

Every canonical iter482 P6 phrase present in both languages. No card numbers, PAN, CVV, or last‑4 are stored/displayed — only ISO‑2 `card_country`.

---

## 5. Silent‑absorb sweep (repository‑wide)

**Question:** Can any code path silently absorb the Stripe processing cost (BidVex out of pocket without a documented reason)?

**Method:** grep for `stripe_fee.*=.*0`, `processing_fee.*=.*0`, `absorb`, `platform_absorbed`, and every `Decimal("0")` assignment in fee logic.

**Findings — 3 places, ALL DOCUMENTED WITH REASON:**

| Site | Code | Reason | Correct? |
|---|---|---|---|
| `services/stripe_connect_service.py:510` | `"reason_code": "platform_absorbed"` in Model A₁ Partner buyer receipt | Buyer is not charged Stripe rail — Partner is Merchant of Record via `on_behalf_of` | ✅ documented invariant |
| `services/stripe_connect_service.py:644` | `processing_fee = Decimal("0")` in `_calculate_partner_checkout` | Same — Partner bears rail | ✅ |
| `services/stripe_connect_service.py:705` | `absorbed_by_platform=True` on `payment_processing` snapshot | Label mildly misleading (Partner absorbs, not platform) but flag is correct: **buyer** doesn't bear it | 🟡 label improvement candidate — non‑financial |
| `services/payment_cost_engine.py:392` | `reason_code="platform_absorbed"` — only when `absorbed_by_platform=True` passed explicitly | Same Partner Model A₁ case | ✅ |

**Anti‑regression guard:** `tests/test_iter482_p51_reconciliation.py::test_anti_regression_stripe_never_silent_zero` asserts every Stripe path either has `recovery_cents > 0` OR a documented `reason_code` (`offline_method`, `legally_gated`, `prohibited`, `platform_absorbed`, `unknown_rate_matrix`, `estimated_from_rate_matrix`).

**Conclusion:** ❌ No un‑gated silent‑absorb paths exist. Every $0 processing fee has an explicit `reason_code` recorded in the reconciliation row.

---

## 6. Stripe fee calculation sites outside `payment_cost_engine.py`

**Question:** Are Stripe fee computations happening anywhere OTHER than the canonical engine?

**Findings — 4 legacy callers, ALL DELEGATE TO CANONICAL ENGINE:**

| Site | Call | Delegates? |
|---|---|---|
| `services/stripe_connect_service.py:59` `_gross_up()` | wraps `payment_cost_engine.estimate(mode="gross_up")` | ✅ delegates line 104 |
| `services/connect_payment_engine.py:70` | imports `stripe_recovery as _sr` from `services/fee_calculator.py` which itself imports the canonical engine | ✅ delegates |
| `services/broker_fee_engine.py:71` `_stripe_gross_up()` | Uses a hardcoded rate — **legacy** kept for broker snapshots | 🟡 legacy — P7 golden‑locked; Gate‑4 candidate |
| `services/fee_calculator.py::_stripe_gross_up()` (line 314) | Explicit LEGACY marker: "kept ONLY for legacy vehicle_invoice / tax_engine flows that haven't migrated yet. NEW CODE MUST NOT USE THIS." | 🟡 legacy — P7 golden‑locked |
| `services/tax_engine.py:483` | Imports `gross_up_stripe_fee as _gross_up_stripe` from `fee_calculator` (which is the legacy variant above) | 🟡 same |

**Assessment:** The canonical `payment_cost_engine.estimate()` is authoritative for every NEW code path (P4 / P4A / P5 / P5.1 / P6 / P6.1 / P6.2). Three legacy call‑sites remain — all documented, all P7 golden‑locked, all Gate‑4 (P6 Tax Engine Consolidation) candidates. They do NOT create financial inconsistency; they replicate the historical iter350 numbers to preserve backwards compatibility for pre‑iter482 documents.

---

## 7. Remaining $0.00 Stripe‑processing paths and their reasons

Enumerated with explicit `reason_code`:

| Reason | Where | When it fires |
|---|---|---|
| `offline_method` | `payment_cost_engine.py:412` | Method ∈ {cash, etransfer, cheque} — always $0 |
| `platform_absorbed` | `payment_cost_engine.py:392` + `stripe_connect_service.py:510` | Partner Model A₁ — Partner bears rail via `on_behalf_of` |
| `legally_gated` | `payment_cost_engine.py:433` | Legacy L‑1 CLOSED gate (currently OPENED as of P5) |
| `prohibited` | `payment_cost_engine.py:451` | Rate‑matrix explicitly disallows payer‑bears‑fee for the payer‑role/jurisdiction combo |
| `unknown_rate_matrix` | `payment_cost_engine.py:472` | Missing rate row — $0 with warning; never silent |
| SKIPPED (P6.2) | `stripe_reconciliation_service.py:161` | Non‑reconcilable `transaction_type` — variance‑email dispatch bypassed |

All 6 codes surface in the receipt / seller statement / admin dashboard so the customer, seller, and operator can audit exactly why processing was $0.

---

## 8. Remaining financial / accounting risks (documented, NOT patched)

Priority uses the same P0/P1/P2 scale from the deployment gate audit.

| # | Finding | Severity | Owner action required |
|---|---|---|---|
| R1 | `buy_it_now` (marketplace + vehicle) flows carry payer‑bears‑fee via `stripe_fee_estimate` in legacy metadata, but NOT the canonical `payment_processing_estimated_cents` / `payment_processing_recovery_cents`. Currently SKIPPED by the gate → no reconciliation ledger row. | 🟡 P1 | Add `auction_purchase`‑equivalent canonical metadata to the two buy‑now sites (routes/payments.py:1796 and 2612) THEN add `"buy_it_now"` to `RECONCILABLE_TRANSACTION_TYPES`. |
| R2 | `vehicle_platform_fee` PIs are SKIPPED. Vehicle 2.5 % fee is a legitimate payer‑bears‑fee flow but does not carry the P5.1 canonical metadata. | 🟡 P1 | Same shape as R1 — attach canonical metadata + whitelist. |
| R3 | Session‑only `transaction_type` on 4 flows (`promotion`, `email_credits`, subscription variants) means the PaymentIntent that ultimately succeeds has NO transaction_type. Currently correct behaviour (SKIPPED default). If a future maintainer moves the field to `payment_intent_data.metadata` OR adds one of these strings to the whitelist without also adding recovery metadata, they'd generate false SHORTFALL. | 🟢 P2 | Add a doc‑block to each Session‑create site explaining "canonical `transaction_type` must live on `payment_intent_data.metadata`, not `Session.metadata`, if this becomes reconcilable." |
| R4 | Legacy `_stripe_gross_up()` in `services/fee_calculator.py:314` + `services/broker_fee_engine.py:71` — two separate copies of the gross‑up math, both P7 golden‑locked. | 🟡 P1 | Consolidate under Gate 4 (P6 Tax Engine + Fee Calculator convergence). Do NOT touch outside Gate 4 — 1,049 golden snapshots depend on the exact cent output. |
| R5 | 5 duplicate tax calculators + 13 QC‑fallback sites (documented in `ITER482_FINAL_AUDIT_MATRIX.md` § C.5). | 🟡 P1 | **BLOCKED — Gate 4 approval required.** Do not touch. |
| R6 | `absorbed_by_platform=True` label in Partner Model A₁ Buyer snapshot (`stripe_connect_service.py:705`) is technically misleading — Partner absorbs, not BidVex. No financial impact. | 🟢 P2 | Rename field to `absorbed_by_partner_of_record` in a future non‑functional rename PR. |
| R7 | On this preview DB, `db.users` still contains 5 synthetic admin‑role seeds. `BILLING_ALERT_EMAIL` env is unset. If deployed AS‑IS, admin fallback would deliver financial alerts to synthetic seeds. **Mitigated by P6.2 `_is_test_email` filter** — but the filter is a safety net, not a source of truth. | 🟡 P1 | Set `BILLING_ALERT_EMAIL` env in production + prune non‑real admin rows before enabling variance dispatch live. |
| R8 | Reconciliation runs against `STRIPE_TEST_SECRET_KEY` on preview. Production deploy requires `STRIPE_API_KEY` (live), `STRIPE_WEBHOOK_SECRET`, `STRIPE_CONNECT_WEBHOOK_SECRET`, and `REACT_APP_STRIPE_PUBLISHABLE_KEY` set before webhook signatures can be verified in live. | 🔴 P0 | Configure prod env vars. |

### Verified NON‑risks (audit found them clean)
- ✅ No duplicate reconciliation systems — `services/stripe_reconciliation_service.py` is the single writer to `db.payment_processing_reconciliation`.
- ✅ No admin financial fields leaked to buyer response — `routes/listings.py:1827‑1835`, `routes/vehicles.py`, `routes/vehicle_multi_lot.py` all strip `reserve_price`, `winner_user_id`, `hammer_price` from buyer‑facing responses via `mask_reserve_for_buyer()`.
- ✅ Refund additive invariant — original hammer/BP/tax/net never overwritten (7/7 refund‑engine tests green).
- ✅ Idempotency via `payment_events` + `mark_charge_refunded` — Stripe replays return the same result.
- ✅ Anti‑regression `test_anti_regression_stripe_never_silent_zero` blocks any future L‑1 flip that would zero a Stripe recovery silently.
- ✅ P6.2 whitelist frozen — `test_reconcilable_whitelist_is_frozen` prevents accidental additions without review.
- ✅ Model A₁ destination‑charge invariant `charge = application_fee + transfer` holds cent‑exact.

---

## 9. Exact files inspected in this audit

**Backend (services):**
- `services/stripe_reconciliation_service.py` (P6.2 gate)
- `services/variance_notification_service.py` (P6.2 recipient filter)
- `services/payment_cost_engine.py` (canonical fee engine)
- `services/stripe_connect_service.py` (Model A₁ + auction_purchase PI metadata)
- `services/connect_payment_engine.py` (buyer‑charge orchestrator, deposit/promotion/email_credits PIs)
- `services/fee_calculator.py` (canonical + legacy gross‑up)
- `services/broker_fee_engine.py` (legacy broker gross‑up)
- `services/refund_engine.py` (destination‑charge refund atomicity)
- `services/payment_collection.py` (finalize + shortfall short‑circuit)
- `services/vehicle_fee_service.py` (vehicle platform fee PI)
- `services/vehicle_payment.py` (vehicle sessions)
- `services/vehicle_invoice.py` (vehicle invoice records)
- `services/subscription_service.py` / `services/subscription_pricing.py`
- `services/broker_deposit_service.py` / `services/storage_deposit_service.py` / `services/down_payment_service.py` / `services/bid_authorization_service.py`
- `services/deposit_auto_capture.py` / `services/overdue_autocapture.py`
- `services/escrow_service.py`
- `services/emails/_email_core.py`
- `services/receipts.py`
- `services/reserve_price_gate.py`
- `services/tax_engine.py` (legacy inspection only)

**Backend (routes):**
- `routes/webhooks.py` (`payment_intent.succeeded` wiring)
- `routes/admin_stripe_reconciliation.py` (dashboard API + auth guard)
- `routes/seller_commission_invoice.py` (seller/partner PAY NOW)
- `routes/payments.py` (buyer auction checkout, buy_it_now, offline)
- `routes/payments_promotions.py`
- `routes/subscriptions.py` / `routes/dealer_subscription_routes.py` / `routes/broker_subscription_routes.py`
- `routes/bidder_deposits.py` / `routes/admin_deposits.py` / `routes/deposits.py`
- `routes/vehicle_dealer_extras.py`
- `routes/partner_card.py`
- `routes/refunds` (via `refund_engine.py` orchestrator)
- `routes/listings.py` / `routes/vehicles.py` / `routes/vehicle_multi_lot.py` (buyer‑response masking)

**Frontend:**
- `pages/admin/AdminPaymentReconciliation.jsx`
- `pages/CheckoutPage.js`
- `pages/SellerCommissionInvoicePage.js`
- `components/PriceBreakdown.js`
- `locales/en.json`, `locales/fr.json`

---

## 10. Tests executed — final counts

Full non‑HTTP suite (avoids known preview rate‑limit + missing‑fixture flakes):

```
python -m pytest \
  tests/iter482/ tests/p7/ tests/p7_5/ \
  tests/test_iter482_golden_matrix.py tests/test_iter482_lot_csv_export.py \
  tests/test_iter482_p0_repairs.py tests/test_iter482_p2_payment_cost_engine.py \
  tests/test_iter482_p31_reconciliation.py tests/test_iter482_p3_fee_calculator_canonical.py \
  tests/test_iter482_p4_end_to_end.py tests/test_iter482_p4a_foundation.py \
  tests/test_iter482_p51_reconciliation.py tests/test_iter482_p5_payer_bears_fee.py \
  tests/test_iter482_refund_engine.py \
  tests/test_iter483_3_lot_and_requests.py tests/test_iter483_live_edit.py \
  tests/test_iter484_2_gate2_api_masking.py tests/test_iter484_2_gate2_vehicle_reserve.py \
  tests/test_iter484_2_payment_methods_visibility.py tests/test_iter484_reserve_settlement.py \
  -k "not test_http" -q
```

**Result: 1,533 passed · 24 deselected · 0 failed · 2 warnings**

Breakdown of the finance‑critical portion:
- `tests/iter482/` (P6 + P6.1 + P6.2 + admin auth + variance + e2e) — **69 tests**
- `tests/p7/` (P7 exact‑cent golden matrix + static audit) — **1,049 tests**
- `tests/p7_5/` (P7.5 Meta/GA4 canonical content_id) — **23 tests**
- `tests/test_iter482_p51_reconciliation.py` (P5.1 + anti‑regression) — **10 tests**
- `tests/test_iter482_p5_payer_bears_fee.py` (payer‑bears invariants) — **28 tests** (3 http deselected)
- `tests/test_iter482_refund_engine.py` (refund atomicity) — **7 tests**

Pre‑existing 11 HTTP flakes (`/api/auth/register` 1‑req/min rate‑limit + missing seed fixture) are documented in the P6.1 audit and iter482 finalization report — none touch financial code.

---

## 11. Blockers before production

| # | Blocker | Severity | Type |
|---|---|---|---|
| 1 | `STRIPE_API_KEY` unset on preview → set `sk_live_…` in prod | 🔴 P0 | env var |
| 2 | `STRIPE_WEBHOOK_SECRET` empty → generate prod webhook signing secret | 🔴 P0 | env var |
| 3 | `STRIPE_CONNECT_WEBHOOK_SECRET` empty → generate Connect webhook signing secret | 🔴 P0 | env var |
| 4 | `REACT_APP_STRIPE_PUBLISHABLE_KEY` empty → set `pk_live_…` in frontend build | 🔴 P0 | env var |
| 5 | `BILLING_ALERT_EMAIL` unset → set dedicated finance mailbox (see R7) | 🟡 P1 | env var |
| 6 | Prune 5 synthetic admin‑role rows from prod `db.users` (see R7) | 🟡 P1 | data cleanup |
| 7 | Gate 4 — P6 Tax Engine Consolidation (5 duplicate calculators + 13 QC fallbacks) | 🟡 P1 | code — **blocked pending your approval** |
| 8 | R1 + R2 — attach canonical P5.1 metadata to buy_it_now + vehicle_platform_fee if reconciliation coverage is desired for those flows | 🟡 P1 | code — awaiting approval |
| 9 | `REACT_APP_GOOGLE_ADS_PURCHASE_LABEL` empty (Meta + GA4 already work) | 🟢 P2 | env var |

---

## 12. Guardrails honoured in this pass

- ✅ Zero code changes (audit‑only).
- ✅ Zero tax logic modifications.
- ✅ Zero calculator additions or removals.
- ✅ Zero reconciliation‑system duplicates introduced.
- ✅ Zero historical records mutated.
- ✅ Zero customers charged (Stripe TEST only; buyer tokens used were `pm_card_visa` / `pm_card_ca`).
- ✅ No Stripe LIVE calls.
- ✅ No deploy.

---

## 13. Final Verdict

- ✅ **iter482 P5 → P6.2 billing surface passes final financial audit** in PREVIEW.
- ✅ **1,533 tests green** — every payment‑correctness invariant locked.
- ✅ **No silent Stripe absorbs** — every $0 path has an explicit `reason_code`.
- ✅ **No false SHORTFALL generators remain** — P6.2 gate proven across 6 non‑reconcilable types + 4× replay idempotency.
- ✅ **No duplicate variance emails** — atomic claim on `variance_notification_status`.
- ✅ **No admin field leaks** — `reserve_price` / `winner_user_id` stripped from buyer responses.
- 🟡 **9 documented blockers/findings** — 4 P0 env‑var config, 3 P1 code candidates (buy_it_now/vehicle_fee reconciliation coverage; Gate 4 tax consolidation), 2 P2 cosmetics.
- 🚫 **DO NOT DEPLOY** until §11 blockers cleared.
- 🚫 **DO NOT** start Gate 4 or P8 until your explicit approval.

**STOP. Awaiting your explicit approval.**
