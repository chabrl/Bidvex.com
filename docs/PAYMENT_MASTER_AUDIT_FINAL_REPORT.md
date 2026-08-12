# BidVex Payment Master Audit — Final Report (P1 Read-Only)

**Iteration:** iter482 + P1
**Date (UTC):** 2026-02-12
**Phase:** P1 — READ-ONLY MASTER AUDIT (no code changes, no production writes, no refunds, no live credentials)
**Companion artifact:** `/app/docs/AUDIT_FLOW_MATRIX.json` (machine-readable version of everything below)
**Prior artifact:** `/app/docs/GATE2_STRIPE_A1_PROOF.md` (empirical Stripe TEST-mode proof)

---

## Executive Summary

The BidVex codebase contains **25 distinct payment flows** implemented across 50+ Python files, using **at least 7 different buyer-premium calculators, 12+ platform-fee sources, 13 hardcoded copies of the Stripe `2.9%+$0.30` formula, 8 duplicate GST/QST tables, and 6 separate refund paths**. None of these are converged behind a single canonical engine, in direct violation of what Section 3 of the master brief requires ("The system must have one canonical payment-cost calculation/recovery mechanism").

The empirical Gate 2 Stripe TEST proof (see iter482 Gate 2) demonstrated that on a canonical $100 hammer × 10 % Partner BP Partner scenario, BidVex **loses $0.92 per transaction** because the code's stated design principle ("Partner bears Stripe rail via `on_behalf_of`") is factually incorrect. Destination charges on Stripe do not shift processing-fee incidence.

The most severe P0 findings, each capable of individually blocking `SAFE TO DEPLOY`, are:

1. **Stripe rail incidence is silently absorbed by BidVex on Partner destination charges** (Section 3 violation; empirically proven Gate 2). Net effect: platform-side loss on small-hammer sales; refutes the docstring claim.
2. **Non-QC Partners are silently taxed at QC rates** in `stripe_connect_service.py:475–484`. The code contains an `else:` branch that applies GST + QST to non-QC provinces. This is exactly the "silently invent a tax rule" pattern Section 5 prohibits.
3. **Invoice PDFs are dynamically recomputed from live fee tables at read time** (`routes/invoices.py:302–341`). If any fee rate changes, historical invoices change. Section 19 explicitly forbids this.
4. **Partner post-auction BidVex-fee billing does not exist** as an automated flow. Sections 2, 8, and 9 mandate an auto-generated Partner invoice with cash / cheque / e-transfer / Stripe options after auction close. No such flow is present in the code.
5. **Hardcoded `2.9%+$0.30` is used in at least 13 code paths** (backend + frontend), directly violating Section 3.
6. **Six separate Stripe.Refund.create call-sites** exist outside the new `refund_engine.py`, so partial/duplicate/webhook refund idempotency is not universally guaranteed.

**Deployment verdict for the current codebase: DO NOT DEPLOY.**
The Gate 2 rail finding must be resolved by an architectural / business decision (per your Q1=B answer, the fix is to build the missing Partner-invoice Stripe path so the *Partner* bears the rail when the Partner chooses Stripe). All other P0/P1 findings below must be remediated with tests before any deployment gate can flip to green.

No code has been modified in P1. Every finding below is read-only.

---

## 1. Complete payment-flow matrix

25 flows enumerated. Full machine-readable form in `AUDIT_FLOW_MATRIX.json` (`payment_flow_matrix[]`). Highlights:

| # | Flow | Route / Service | Payer | BidVex fee source | Refund path |
|---|---|---|---|---|---|
| F1 | Partner auction — buyer checkout | `routes/payments.py:63,841` → `calculate_partner_listing_checkout` | Buyer | 3 % × hammer as `application_fee` | `refund_engine.refund_partner_charge` (canonical) |
| F2 | Non-Partner auction winner checkout | `routes/payments.py:1887` | Buyer | 5 %/3.5 %/3 % BP + 4 %/2.5 %/2 % SC | shared refund_engine |
| F3 | Buy It Now | `routes/payments.py:1577` | Buyer | same as F2 | refund_engine |
| F4 | Vehicle checkout | `routes/payments.py:2280` + `services/vehicle_payment.py` | Buyer | 2.5 % platform fee | separate vehicle flow — NOT in refund_engine |
| F5 | Storage auction — buyer | `routes/storage_auctions.py`; `services/storage_pricing.py` | Buyer | 5 % BP (BidVex) + hardcoded 2.9 %+$0.30 recovery ADDED to buyer | own path |
| F6 | Broker (multi-lot) | `services/broker_fee_engine.py` | Broker's client | 2.5 % platform fee | own path |
| F7 | **Partner post-auction BidVex invoice** | **NOT IMPLEMENTED** | Partner (to BidVex) | 3 % × hammer + tax | N/A |
| F8 | Subscriptions | `routes/subscriptions.py`; `services/subscription_service.py` | User | tier price | Stripe.Subscription.cancel |
| F9 | Partner annual $100 access fee | `routes/subscriptions.py`; `shared.py:185` | User | $100 (hardcoded) | manual |
| F10 | Dealer subscription | `routes/dealer_subscription_routes.py`; `services/dealer_subscription_service.py` | Dealer | tier price | Stripe.Subscription |
| F11 | Broker subscription | `routes/broker_subscription_routes.py` | Broker | tier price | Stripe.Subscription |
| F12 | Marketing / promoted listings / ad campaigns / email marketing | `routes/marketing.py`, `routes/ad_campaigns.py`, `routes/payments_promotions.py` | Business | ad price | Stripe.Refund direct |
| F13 | Bidder deposits | `routes/bidder_deposits.py`; `services/bid_authorization_service.py` | Bidder | held only | `services/deposit_refund_queue.py:154` direct `Stripe.Refund.create` |
| F14 | Broker deposits | `services/broker_deposit_service.py` | Broker | held only | `services/broker_deposit_service.py:116` direct `Stripe.Refund.create` |
| F15 | Storage deposits | `services/storage_deposit_service.py` | Buyer | held only | own |
| F16 | Escrow | `services/escrow_service.py` | Buyer→escrow→Seller | destination transfer | `services/pickup_confirmation.py:174` direct `Stripe.Refund.create` |
| F17 | Disputes / cancellation refunds | `routes/disputes.py:327` | — | — | direct `Stripe.Refund.create` (P1) |
| F18 | Cancellation / no-show / failed-pickup penalties | `services/overdue_autocapture.py` | Buyer/Bidder | `hammer × 0.025` hardcoded | mixed |
| F19 | Seller payouts (manual) | `services/seller_payouts.py`; `services/manual_settlement_service.py` | — | — | Stripe.Transfer |
| F20 | Contractor commission payouts | `services/contractor_commission.py` | — | — | Stripe.Transfer (idempotency-keyed) |
| F21 | Vehicle-dealer extras | `routes/vehicle_dealer_extras.py:327` | Dealer | hardcoded `STRIPE_FIXED_FEE=0.30`, `PLATFORM_FEE_PERCENT=2.5` | Stripe.PaymentIntent |
| F22 | Down-payment (vehicle) | `services/down_payment_service.py` | Buyer | — | Stripe.Checkout |
| F23 | Public guest checkout | `routes/public_payments.py:111` | Guest | — | Stripe.Checkout |
| F24 | Admin oversight one-off transfers | `routes/admin_oversight.py:836, 1009` | — | — | Stripe.Transfer (needs audit trail) |
| F25 | Webhooks (all Stripe events) | `routes/webhooks.py:89` | — | — | outer idempotency via `stripe_events` unique-id (CORRECT) |

---

## 2. Duplicate calculators & duplicated fee formulas

### 2.1 Buyer premium — 6 independent copies

`BUYER_PREMIUM_RATES` is redefined in:
- `services/pricing_config.py:20`
- `services/tax_engine.py:65`
- `services/fee_calculation_engine.py:45`
- `services/fee_calculator.py:1123`
- `services/subscription_service.py:64`
- `services/vehicle_pricing.py:57`

**Impact:** any change to a tier rate must be made in six places or the calculators disagree. Severity: **P1**.

### 2.2 Platform fee — 12+ independent copies (including hardcoded floats)

Notable:
- `services/tax_engine.py:81,82` (Decimal, canonical): `VEHICLE_PLATFORM_FEE_RATE=0.025`, `PARTNER_PLATFORM_FEE_RATE=0.03`
- `services/pricing_config.py:11,12` (duplicate Decimal)
- `services/fee_calculation_engine.py:63` (duplicate)
- `services/fee_calculator.py:1119` (duplicate)
- `services/vehicle_fee_service.py:18` — **float `0.025`** (loses Decimal precision)
- `services/vehicle_pricing.py:63` (Decimal)
- `services/broker_fee_engine.py:36` — **float `0.025`**
- `routes/settlement.py:29` — **float `0.025`**
- `routes/vehicle_dealer_extras.py:256` — **float `2.5` (percent, not rate)**
- `routes/auctions_bids.py:1791` — ad-hoc `round(subtotal * rate, 2)`
- `routes/payments_fees.py:158` — dict `{free:0.04, premium:0.025, vip:0.02}`
- `services/overdue_autocapture.py:48` — hardcoded `0.025`

Severity: **P1**.

### 2.3 Stripe rail formula — **13+ copies of `2.9 % + $0.30`**

**This is the exact anti-pattern Section 3 forbids.** Locations:
- `services/stripe_connect_service.py:32` (Decimal 0.029)
- `services/pricing_config.py:15` (Decimal 0.029)
- `services/storage_pricing.py:36` (Decimal 0.029)
- `services/vehicle_fee_service.py:19` (float 0.029)
- `services/broker_fee_engine.py:39` (float 0.029)
- `services/fee_calculator.py:83, 1117, 1136` (Decimal 0.029 three times in one file)
- `services/fee_calculator.py:151` (dict `{"domestic":0.029}` — the only place that acknowledges non-domestic exists)
- `routes/vehicle_dealer_extras.py:262` (0.029)
- `routes/auctions_bids.py:1796` — `round(platform_fee * 0.029 + 0.30, 2)` (adhoc)
- `routes/payments_fees.py:158-207`
- `routes/subscriptions.py:44` — `_stripe_gross(round(amount * STRIPE_PERCENTAGE_FEE + 0.30, 2))`
- `frontend/src/pages/HowBrokersWorkPage.jsx:42-43` — JS 0.029/0.30 (independent from backend)

Severity: **P0** (Section 3 explicit violation).

### 2.4 Tax rates — 8 duplicate GST/QST tables

Full list in `AUDIT_FLOW_MATRIX.json → tax_engine_findings.duplicate_tax_formulas`. Notable: `routes/tax_dashboard.py:27-29` even redefines an HST_RATES dict.

Severity: **P1**.

### 2.5 Storage 4 % legacy references

Per iter482, storage seller commission was fixed to 0 % in `services/storage_pricing.py`. However `services/pricing_config.py:32-36` still lists `SELLER_COMMISSION_RATES` at 0.04 for the "free" / "basic" / "standard" / "partner" tiers, and this dict is referenced from callers that may serve storage sellers.

Severity: **P1** — needs to be reconciled with the "Storage seller = 0 %" rule.

---

## 3. Every Stripe API path (map)

`grep` returns **90 create/retrieve/list/modify/cancel/refund/reverse call sites** in production code (excluding tests) across 50 files. Full list in `AUDIT_FLOW_MATRIX.json → payment_flow_matrix[].route` + `refund_paths_multiplicity`. Categories:

| Stripe API | Count | Files |
|---|---:|---|
| `PaymentIntent.create/cancel/retrieve` | 20 | payments.py, storage_auctions.py, bidder_deposits.py, partner_card.py, vehicle_dealer_extras.py, deposits.py, escrow_service.py, storage_deposit_service.py, broker_deposit_service.py, vehicle_fee_service.py, vehicle_payment.py, bid_authorization_service.py, subscription_service.py, connect_payment_engine.py, auction_settlement.py, stripe_customer_service.py, stripe_circuit_breaker.py |
| `checkout.Session.create/retrieve` | 12 | payments.py, subscriptions.py, admin.py, partners.py, broker_subscription_routes.py, dealer_subscription_routes.py, public_payments.py, payments_promotions.py, vehicle_payment.py, subscription_service.py, connect_payment_engine.py, stripe_connect_service.py |
| `Transfer.create` | 8 | webhooks.py, admin_oversight.py, escrow_service.py, seller_payouts.py, contractor_commission.py, connect_payment_engine.py |
| `Refund.create` | **6** | disputes.py, broker_deposit_service.py, deposit_refund_queue.py, pickup_confirmation.py, payment_idempotency.py (×2), **refund_engine.py (canonical)** |
| `Subscription.create/modify/retrieve/cancel` | 12 | subscriptions.py, admin.py, partners.py, dealer_subscription_service.py, trial_conversion_reminder.py, webhooks.py |
| `Invoice.list/retrieve` | 3 | manual_settlement_service.py |
| `Webhook.construct_event` | 1 | webhooks.py (correct outer boundary) |

---

## 4. Tax engine audit

**Canonical engine:** `services/tax_engine.py` + `services/tax_rate_config.py` (province matrix).

**Silent defaults / fail-open patterns:**
- `services/stripe_connect_service.py:471` — `partner_prov = (partner_province or "QC").strip().upper()`. Falls back to QC if the caller doesn't pass one.
- `services/stripe_connect_service.py:475-484` — non-QC branch still applies GST + QST. **This is a silent tax invention.** Section 5 prohibits it. **Severity: P0.**
- `routes/payments.py:912, 1053` — `partner_province = seller.get("province") or seller.get("business_province") or "QC"` — silent QC fallback in the caller.
- `routes/payments.py:1541, 1638, 2243, 2314` — `buyer_province = (user_doc.get("province", "QC") or "QC")` — silent QC fallback for buyer province in checkout flows.

**8 duplicate copies of GST/QST/HST rates.** See §2.4.

**Missing HST-province coverage in `stripe_connect_service`:** The Partner calculator has no branch for ON/AB/BC/NS/NB/PE/NL — non-QC Partners silently receive QC tax. **P0**.

---

## 5. Seller-type fallback (`="individual"`) hits

7 non-test locations. Highest-severity:
- `routes/invoices.py:215, 308, 399` — `seller_account_type='individual'` + `buyer_account_type='individual'` fallbacks in the invoice reconstruction called at read time from `calculate_fee(...)`. **P0** — invoice PDFs can mis-tag a seller as individual and simultaneously recompute the fee.
- `services/auction_settlement.py:284, 646` — hardcoded buyer_account_type at settlement time. **P1**.
- `routes/fees.py:25, 69, 97, 357, 368` — route defaults + internal fallbacks. **P1**.
- `routes/auctions_bids.py:1756` — `resolve_seller_account_type(...) or "individual"` — fallback preserved. **P1**.

---

## 6. Storage 4 % legacy references

- `services/storage_pricing.py` — seller commission is 0 %. **FIXED in iter482.**
- `services/pricing_config.py:32-36` — `SELLER_COMMISSION_RATES` still lists 0.04 for `free`/`basic`/`standard`/`partner`; not all callers are storage-aware. **P1**.
- `routes/storage_auctions.py:946` — comment says "always 5 % commission" (misleading — should read "5 % buyer premium, 0 % seller commission"). **P2**.

---

## 7. Quantity propagation

**Coverage after iter482 is now good** for payment-critical paths. `resolve_hammer_total()` is called in:
- `services/payment_collection.py:384`
- `services/auction_settlement.py:852`
- `services/overdue_autocapture.py:47, 324`
- `routes/invoices.py:193, 262`
- `routes/payments.py:120, 894`

**Residual risk:** `routes/settlement.py:72` uses `float(doc.get("final_price") or doc.get("current_price"))` — needs to be confirmed whether this is a math path (P1) or a display path (info).

---

## 8. Buyer-facing fee explanations & lot-auction disclosures

- **Frontend hardcodes 2.9 %/$0.30**: `frontend/src/pages/HowBrokersWorkPage.jsx:40-55` — an independent JS calculator that drifts from backend. **P1**.
- **Admin dashboards display fixed 2.9 % + $0.30**: `pages/admin/PricingManager.js:226,237,247`, `pages/admin/FinanceDashboard.js:191`. **P2**.
- **Storage policy copy states 5 % + Stripe processing + tax on premium**: `pages/storage/StoragePolicies.js:64,120,164`. Copy is accurate for current storage_pricing.py but must be re-verified when the canonical engine lands. **P3**.
- **CheckoutPage.js:507** displays `breakdown.stripe_processing_fee || breakdown.processing_fee` — consumes backend value (**OK**).
- **CheckoutPage.js:432-433** derives `taxable_amount || (hammer + buyer_premium)` — this is a fallback path, minor. **P2**.

---

## 9. Partner post-auction BidVex-fee billing & email automation

**Auto-invoice generation:** NOT PRESENT for the Partner-owed-BidVex leg. The invoice module (`services/invoice_service.py`, `routes/invoices.py`) generates buyer-side invoices only.
**Auto-email:** NOT PRESENT. Partner emails found:
- `services/partner_outreach.py` — outreach / follow-up (marketing)
- `services/partner_pro_emails.py` — trial expiry / reminders
- `services/verification_service.py` — application approved / rejected
- `services/emails/*.py` — nothing for auction-completion Partner invoice.
**PAY NOW endpoint for Partner-owed-BidVex:** NOT PRESENT. There is no route that lets a Partner pay their post-auction 3 % + tax through Stripe / cash / cheque / e-transfer.
**Immutable Partner invoice record:** NOT PRESENT.
**Severity:** **P0 — full feature missing per Sections 2, 8, 9**.

---

## 10. Database immutability

- `routes/invoices.py:302-341` — dynamically calls `calculate_fee(...)` at invoice read time. If any fee schedule changes, historical invoices change. **P0 — Section 19 violation.**
- `services/receipts.py` reads persisted receipt/transaction (OK).
- `services/pdf_generators/common.py` — some PDF fields fall back to live listing data if persisted value is missing. **P1 — audit each field.**

---

## 11. Refund paths (multiplicity)

Six separate `stripe.Refund.create` call-sites exist. Only one is canonical:

| Location | Canonical? | Idempotency | Severity |
|---|:-:|---|---|
| `services/refund_engine.py:refund_partner_charge` | ✅ | `payment_charges.status == "refunded"` + Stripe `duplicate_blocked` | canonical |
| `routes/disputes.py:327` | ❌ | none observable | **P1** |
| `services/broker_deposit_service.py:116` | ❌ | none observable | **P1** |
| `services/deposit_refund_queue.py:154` | ❌ | queue-based but no Stripe-side dedupe | **P1** |
| `services/pickup_confirmation.py:174` | ❌ | none observable | **P1** |
| `services/payment_idempotency.py:282, 284` | ❌ | is an idempotency helper that creates auto-refunds (`reason="duplicate"`) | **P1** |

---

## 12. Webhook idempotency

- **Outer boundary:** ✅ `routes/webhooks.py:113-138` — `stripe_events` unique index on `id` returns 200 on duplicate. Correct pattern.
- **Handler side-effects:** partially audited. `charge.refunded` / `refund.*` handlers at `routes/webhooks.py:515+` need targeted verification in Phase 5 (Gate 3 refund proof). Preliminary assessment: OK because they update by object ID.
- **Multi-secret verification:** `routes/webhooks.py:54-83` tries multiple `STRIPE_*_WEBHOOK_SECRET` values in sequence. OK.

---

## 13. Every-place-where-Stripe-fees-are-absorbed-vs-passed

| Flow | Buyer pays Stripe rail? | Seller/Partner pays Stripe rail? | BidVex absorbs Stripe rail? |
|---|:-:|:-:|:-:|
| Partner auction (F1) | No | **No — despite docstring claim** | **Yes** (Gate 2 proven) |
| Non-Partner auction (F2) | No | No | Yes |
| Buy It Now (F3) | No | No | Yes |
| Vehicle (F4) | No | No | Yes |
| Storage buyer (F5) | **Yes** — explicit 2.9 %+$0.30 hardcoded added to buyer | No | No |
| Broker (F6) | No — grossed up | No | Yes (via broker margin) |
| Partner-owed BidVex invoice (F7) | — | — | flow does not exist |
| Subscriptions (F8) | Sometimes — `_stripe_gross` in routes/subscriptions.py:44 | — | Otherwise absorbed |
| Bidder deposits (F13) | No | No | absorbed on capture |
| Marketing (F12) | No | No | Yes |
| Escrow release (F16) | No | Sometimes — transfer amount is net of app fee | Yes for Stripe rail |

**No unified policy** — every flow chooses independently. Section 3 mandates a single canonical engine.

---

## 14. Every-place-where-payment-processing-cost-is-calc'd-dynamically-vs-hardcoded

**Hardcoded (13 backend + 1 frontend, listed in §2.3).**
**Dynamic (0):** no code currently reads the actual Stripe `balance_transaction.fee` and locks it as the authoritative processing cost. This is exactly the gap Section 3 flags: the system cannot distinguish "estimated" from "actual" Stripe cost.

---

## 15. Consolidated findings table

| # | Severity | Title | File(s) / Function | Current behavior | Intended behavior (per master brief) | Proposed fix | Dependencies | Tax/legal review needed? |
|---|:-:|---|---|---|---|---|---|:-:|
| P0-1 | P0 | Partner Stripe rail is absorbed by BidVex (Gate 2 refutes docstring) | `services/stripe_connect_service.py:391-392, 502-504, 570` | Destination charge with `on_behalf_of` does NOT shift rail; platform balance is debited $4.37 on canonical scenario | Partner (chooser of Stripe on the Partner-invoice path) bears Stripe cost; buyer NEVER bears BidVex's cost | Build Partner-invoice Stripe endpoint (Q1=B); leave buyer-side Partner checkout untouched pending legal review; correct the docstring | F7 flow build-out; canonical payment_cost_engine (P2) | Y — QC surcharge legal on B2B Partner invoice |
| P0-2 | P0 | Non-QC Partners silently taxed at QC combined rate | `services/stripe_connect_service.py:471-484` | Silent fallback: QC rate applied regardless of Partner province | FAIL CLOSED for non-QC Partners until per-province rules are ratified | Route non-QC Partners through canonical `tax_engine.calculate_taxes_for_recipient` OR raise 400 | tax_engine unification (P6) | Y — non-QC B2B place-of-supply |
| P0-3 | P0 | Invoice PDFs dynamically recompute fees at read time | `routes/invoices.py:302-341` (`calculate_fee(...)`) | Live-recalculates buyer_premium, platform_fee, tax on every render | Read persisted immutable financial facts only | Persist fee schedule version + full breakdown into `invoices` at creation; read-only rendering path | invoice_service refactor | N |
| P0-4 | P0 | Partner post-auction BidVex-fee invoice + email + PAY NOW does not exist | (missing feature) | Manual / no automation | Auto-generate immutable Partner invoice on auction close; email with lot list + PAY NOW; cash / cheque / e-transfer / Stripe | Build new `services/partner_invoice.py` + Partner invoice route + email template + Stripe processing recovery ADDED only when Partner selects Stripe | canonical payment_cost_engine (P2); tax_engine for B2B tax on 3 % fee (P6) | Y — QC B2B tax rules & Partner invoice ITC treatment |
| P0-5 | P0 | 13+ hardcoded copies of `2.9 % + $0.30` | see §2.3 | Various inline formulas | One canonical `payment_cost_engine.estimate(payment_method, currency, amount_cents)` returning `{estimated_cost, actual_cost_locked, is_estimate, legal_gate_status}` | Introduce `services/payment_cost_engine.py`; migrate all 13 call-sites | Section 3 canonical engine | Y — buyer-facing surcharge legality |
| P0-6 | P0 | Six `stripe.Refund.create` sites outside `refund_engine.py` | see §11 | Duplicate refund possible on dispute, deposits, pickup confirmation | Every refund path routes through `refund_engine.refund_partner_charge` (or a broader `refund_engine.refund_charge`) with idempotency guard | Refactor 5 non-canonical sites | tests in P5 (Gate 3) | N |
| P1-1 | P1 | Six `BUYER_PREMIUM_RATES` copies | see §2.1 | Divergence risk on tier changes | Single source in `tax_engine` (or `pricing_constants`) — every module imports | delete duplicates | schedule change to `fee_schedules` DB | N |
| P1-2 | P1 | 12+ platform-fee copies (many as floats) | see §2.2 | Loss of Decimal precision, drift risk | Decimal-only, single source | consolidate to `tax_engine.PARTNER_PLATFORM_FEE_RATE` + `VEHICLE_PLATFORM_FEE_RATE` | none | N |
| P1-3 | P1 | 8 GST/QST/HST duplicate tables | see §2.4 | Rate drift | Single `services/tax_rate_config.py` | consolidate | none | N |
| P1-4 | P1 | Frontend `HowBrokersWorkPage.jsx` re-computes fees | `frontend/src/pages/HowBrokersWorkPage.jsx:40-55` | JS-side Stripe formula (0.029/0.30) drifts from backend | Frontend fetches breakdown from `GET /api/fees/v2/preview` | rewire the page's calculator to backend endpoint | canonical engine (P2) | N |
| P1-5 | P1 | Silent QC default for `buyer_province` / `partner_province` | `routes/payments.py:912, 1053, 1541, 1638, 2243, 2314` | `.get("province") or "QC"` | FAIL CLOSED — require province from user record OR route level 400 | route-level validation | N |
| P1-6 | P1 | `services/overdue_autocapture.py:48` hardcoded 2.5 % penalty | `services/overdue_autocapture.py:48` | `round(hammer * 0.025, 2)` inline | Use canonical `tax_engine.PARTNER_PLATFORM_FEE_RATE` (2.5 % vehicle) or the schedule | move to fee_schedule reader | Section 8 penalty schedule | N |
| P1-7 | P1 | `routes/vehicle_dealer_extras.py:256-262` hardcoded PLATFORM_FEE_PERCENT=2.5 + STRIPE 0.30 | same file | inline % and $ constants | delegate to `payment_cost_engine` + `vehicle_fee_service` | P2 | N |
| P1-8 | P1 | Direct `stripe.Refund.create` in disputes / deposits / pickups (see §11) | 5 files | No idempotency guard vs `refund_engine` | route through canonical engine | P5 | N |
| P1-9 | P1 | `services/pricing_config.py:32-36` — Storage tiers still list 0.04 | one file | Storage buyer commission 4 % ghost | force to 0 for storage tier; canonicalize elsewhere | none | N |
| P1-10 | P1 | Multiple hardcoded `="individual"` fallbacks | 7 files (see §5) | Silent seller-type default may under-invoice | Fail closed via `seller_type_resolver` | P4 & P6 | N |
| P2-1 | P2 | `pages/admin/PricingManager.js` shows hardcoded `2.9 % + $0.30` | admin UI copy | Slightly outdated | Fetch from `/api/fees/v2/preview` metadata | P2 | N |
| P2-2 | P2 | Storage policy copy in `pages/storage/StoragePolicies.js` | 3 blocks | Descriptive copy — accurate for current storage_pricing.py | Re-verify wording after canonical engine lands | after P2 | Y — accuracy of buyer-facing disclosure |
| P2-3 | P2 | Subscription `_stripe_gross` gross-up in routes/subscriptions.py:44 | one function | Adds fixed 2.9 %+$0.30 gross-up | route through canonical engine | P2 | Y — subscription surcharge legality |
| P2-4 | P2 | `payment_idempotency.py:282-284` uses `stripe.Refund.create(reason="duplicate")` as an auto-recovery | one file | Auto-refunds duplicate charge attempts | route through canonical `refund_engine` | P5 | N |
| P2-5 | P2 | `routes/storage_auctions.py:946` misleading comment "always 5 % commission" | one line | comment | Correct to "5 % buyer premium, 0 % seller commission" | none | N |
| P3-1 | P3 | Trailing slash redirect `/marketplace/` → `/marketplace` still open | CDN | Non-financial | Middleware / CDN rule | none | N |
| P3-2 | P3 | CreateListingPage React duplicate-key warnings (pre-existing) | `frontend/src/pages/CreateListingPage.js` | Console warnings | Fix map keys | none | N |

---

## 16. Legal / tax items requiring human review

These are the **exclusive** items where P1 refuses to guess. All flagged for accountant / legal counsel before implementation of the affected fixes.

| Ref | Question | Why |
|---|---|---|
| L-1 | Is a buyer-facing Stripe surcharge lawful in Quebec (and other CA provinces) under the current CPA rules? | Section 4 requires legal review before adding buyer surcharge |
| L-2 | Is a **B2B** Partner-invoice Stripe surcharge (Partner is business paying BidVex's 3 % + tax + Stripe recovery) lawful? Section 3 explicitly permits "party choosing Stripe bears it, subject to law" — this needs confirmation for Canadian B2B | Q1=B answer relies on this being lawful |
| L-3 | For a non-QC Partner (e.g. ON, AB, BC): what is the correct place-of-supply for BidVex's 3 % B2B service, and does GST-only apply (rather than QC combined 14.975 %)? | E-3 recipient rule |
| L-4 | For a QC Partner selling to a non-QC buyer, what tax applies to the Partner BP (place-of-supply for the auctioneer service — is it buyer or seller residence)? | Section 5 — currently the code applies QC rate to `hammer + BP` when Partner is tax-registered regardless of buyer province |
| L-5 | Is Stripe processing recovery itself taxable? If yes, in which order — before or after tax on the underlying supply? | Section 4 |
| L-6 | Storage buyer's-premium copy already discloses "5 % + processing + tax" — is that disclosure sufficient under QC CPA? | Section 4 |
| L-7 | Subscription grossing-up (`_stripe_gross` in `routes/subscriptions.py:44`) — is this legal to display as a Stripe recovery to consumers vs businesses? | L-1 / L-2 |
| L-8 | Escrow release path: on cancellation refund, do we net-refund the buyer's original Stripe surcharge (if any) or is that non-refundable per QC CPA? | Refund tax law |
| L-9 | Bilingual disclosure requirement: any Stripe surcharge line must appear identically in EN and FR — verify all planned copy paths | QC Bill 96 |

---

## 17. Production historical exposure

Preview DB was queried in iter482 Phase 0: **$0 exposure found in preview**. Production DB was inaccessible from the preview pod. This status is **PRODUCTION EXPOSURE NOT VERIFIED**. Per your instruction "Do NOT run production DB queries" during P1, this remains unverified. Resolution deferred to the deployment gate; will require a read-only production-side script executed by you.

---

## 18. Recommended implementation order (priorities, no code executed)

Strictly ordered so each phase is committable on its own without regressing prior invariants.

1. **P2 — Canonical `payment_cost_engine`** — a pure module returning `{estimated_cost, actual_cost, is_estimate, legal_gate_status}`. Add TEST-mode unit tests. Zero call-sites modified in this phase; the engine is built and proven independently.
2. **P3 — Partner auction buyer checkout wiring** — thread `payment_cost_engine` into `stripe_connect_service.calculate_partner_listing_checkout`. Buyer still pays exactly $110.00 on the canonical scenario (fail-closed until L-1 lawful for buyer surcharge). Golden matrix expanded.
3. **P4 — Partner post-auction billing** — build the missing F7 flow: immutable invoice record, email template with SOLD LOTS + payment options, Stripe payment route that ADDS `payment_cost_engine.estimate(stripe, cad, invoice_amount).estimated_cost_cents` when the Partner selects Stripe, and settles to `actual_cost_cents` after webhook. Cash / cheque / e-transfer paths do NOT add the recovery.
4. **P5 — Refund engine consolidation & Gate 3** — refactor 5 non-canonical refund sites through `refund_engine`; live Stripe TEST-mode proof of full → partial → idempotency → webhook replay against a canonical destination-charge.
5. **P6 — Tax engine consolidation & jurisdictional coverage** — single-source for GST/QST/HST/PST/RST tables; jurisdiction-aware calculators; fail-closed for missing province/registration.
6. **P7 — Complete test matrix (Sections 20, 21)** — ≥ 200 exact-cent cases including all Partner / individual / enterprise / storage / vehicle / broker × QC/ON/AB/BC × registered/unregistered × qty 1/2/10 × Standard/Premium/VIP × Stripe/cash/e-transfer/cheque.
7. **P8 — Peripheral flows (Sections 15–18)** — escrow, deposits, penalties, marketing, subscriptions, annual fees.
8. **P9 — Static financial audit repo-wide + deployment gate** — sweep for any residual `="individual"` / `0.04` / dup calculators; every finding resolved or `REQUIRES_REVIEW`. Final gate: SAFE TO DEPLOY / DO NOT DEPLOY.

---

## 19. Explicit gate status right now

| Gate | Status |
|---|---|
| 1. Stripe TEST authentication (iter482) | ✅ PASS |
| 2. Model A₁ Sandbox Proof (iter482) | ✅ PASS WITH P0 CRITICAL FINDING (rail incidence) |
| P1 READ-ONLY MASTER AUDIT (this phase) | ✅ COMPLETE — no code changed, no production writes |
| Canonical payment_cost_engine (P2) | ⏸ PENDING your P2 approval |
| Partner buyer-checkout wiring (P3) | ⏸ PENDING |
| Partner invoice + PAY NOW (P4) | ⏸ PENDING + L-2, L-3 legal review |
| Refund engine consolidation + Gate 3 (P5) | ⏸ PENDING |
| Tax engine consolidation (P6) | ⏸ PENDING + L-3/L-4 accountant review |
| Complete test matrix (P7) | ⏸ PENDING |
| Peripheral flows (P8) | ⏸ PENDING |
| Static financial audit + deployment gate (P9) | ⏸ PENDING |
| Production historical exposure | 🚫 NOT VERIFIED (no prod DB access) |
| **Final deployment gate** | 🚫 **DO NOT DEPLOY** |

---

## 20. What P1 did NOT do

- Zero production code changes.
- Zero production DB queries.
- Zero Stripe test/live refunds.
- Zero live-mode Stripe credentials used.
- Zero writes to Partner emails, Stripe TEST accounts (other than the reused Gate 2 partner account from iter482, which was created in Gate 2, not P1).
- Zero tax-law inventions.
- Zero business-rule assumptions.

**Awaiting your P2 approval** before any code lands. The audit findings above are self-contained and can be shared with accountants / counsel for the L-1 … L-9 questions in parallel.

---

*End of P1 Master Audit report.*
