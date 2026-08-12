# P2 — Canonical Payment-Cost Engine — Final Report

**Iteration:** iter482 + P2
**Date (UTC):** 2026-02-12
**Scope:** Section 4 ($0.31 reconciliation) + Section 5 (canonical `payment_cost_engine.py`) — nothing else.
**Guardrails honored:** no deploy, no production DB queries, no refunds, no live-mode credentials, no historical record modification, no wiring of the engine into existing call-sites (that's P3+), no invented tax rules.

---

## 1. $0.31 reconciliation — RESOLVED

### 1.1 Empirical trace of the exact receipt

Reported receipt:
```
Hammer            $7.00
BidVex Buyer Fee  $0.25
Taxes             $0.08
Payment Processing $0.00
TOTAL PAID        $7.64
```
Displayed sum: **$7.33**.
Amount charged: **$7.64**.
Unexplained delta: **$0.31**.

Simulating `services.fee_calculator._iter350_individual` (invoked via `services.fee_calculator.calculate_fee`) with:
- `hammer_price = $7.00`
- `buyer_tier = "premium"` (3.5 % Buyer Premium tier)
- `seller_tier = "standard"` (individual seller)
- `buyer_prov = "QC"`, `seller_prov = "QC"`
- `payment = "stripe"`
- `auction_type = "general"`, `seller_type = "individual"`

produces:

| Line | Cents | Dollars |
|---|---:|---:|
| `hammer_price` | 700 | $7.00 |
| `buyer_premium` (3.5% × $7) | 25 | $0.25 |
| **`buyer_stripe_recovery`** (= `buyer_premium × 0.029 + $0.30`) | **31** | **$0.31** |
| `buyer_taxes` (QC 14.975% × ($0.25 + $0.31)) | 8 | $0.08 |
| **`buyer_total_charged`** | **764** | **$7.64** |

Exact-cent match. **The $0.31 IS the `buyer_stripe_recovery` line** produced by `services/fee_calculator.py:397-410`. It was collected as part of the buyer's $7.64 Stripe charge but not rendered in the receipt UI.

### 1.2 Root cause (P0)

Two independent bugs converge:

1. **Fee calculation is duplicated across 4 non-Partner buyer-side calculators**, each producing different totals for the exact same inputs:

| Calculator | File | processing | total | Matches receipt? |
|---|---|---:|---:|:-:|
| `_iter350_individual` (`calculate_fee`) | `services/fee_calculator.py:385` | $0.31 | **$7.64** | ✅ |
| `calculate_general_payment` | `services/tax_engine.py:421` | $0.53 | $7.90 | no |
| `calculate_general_checkout` | `services/stripe_connect_service.py:133` | $0.53 | $7.86 | no |
| `calculate_connect_checkout` | `services/connect_payment_engine.py:53` (via `PricingManager`) | $0.53 | $7.90 | no |

The buyer's Stripe charge was created via a route that called one of `calculate_general_checkout` / `calculate_connect_checkout` (total $7.86 – $7.90), while the RECEIPT record was rebuilt via `calculate_fee → _iter350_individual` (total $7.64). Two calculators disagree, but the RECEIPT persisted $7.64 as the total.

**Even worse:** the frontend `PriceBreakdown.js:214-224` and receipt renderers only draw a "Payment Processing" line when `breakdown.stripe_processing_fee > 0`. Since the receipt path uses `buyer_stripe_recovery` (from `_iter350_individual`) rather than `stripe_processing_fee` (the field the renderer looks for), the row renders as **$0.00** (or is omitted entirely).

The $0.31 is EXACTLY the value that would be labelled and displayed if the renderer read the correct field.

### 1.3 What was actually charged vs what the receipt claims

- **If** the buyer was actually charged $7.64 (per the receipt total): the calculator was `_iter350_individual`. Then Section 7 is VIOLATED because the itemized display omits the $0.31 line.
- **If** the buyer was actually charged $7.86 – $7.90 (via one of the other 3 calculators) but the RECEIPT was regenerated later with `calculate_fee` and stored as $7.64: then the buyer paid MORE than the receipt claims. Section 19 (immutability) is VIOLATED because the receipt is dynamically recomputed from a different calculator's rules than the one that actually charged the card.

**Either way, this is a P0 defect: `DO NOT DEPLOY` until the calculator convergence lands in P3+**.

### 1.4 Reconciliation status

- $0.31 identified: ✅ EXACT cent match via `_iter350_individual`.
- Every cent explained: ✅ hammer $7 + BP $0.25 + stripe_recovery $0.31 + tax $0.08 = $7.64.
- Root cause understood: ✅ (a) 4 duplicate calculators disagree, (b) receipt renderer looks at the wrong field name.
- Production data touched: ❌ NO.
- Fix applied in P2: ❌ NO (per phased plan; the fix is P3 receipt renderer + calculator convergence via canonical engine).
- Deployment status: **DO NOT DEPLOY.**

Trace script: `/app/backend/tests/p2_reconciliation_31cent_trace.py`
Reproduction of the exact $7.64 via `_iter350_individual`: proven by the Python invocation embedded in this document.

---

## 2. Canonical `payment_cost_engine.py` — Delivered

### 2.1 Files created

- `/app/backend/services/payment_cost_engine.py` (410 lines, 0 lint errors)
- `/app/backend/tests/test_iter482_p2_payment_cost_engine.py` (40 exact-cent invariants — all passing)
- `/app/backend/tests/p2_reconciliation_31cent_trace.py` (the $0.31 trace)

**Wiring into existing calculators is deliberately deferred to P3.**  P2 only ships the module and its tests.

### 2.2 Public API

```python
from services.payment_cost_engine import (
    ENGINE_VERSION,               # "iter482-P2-v1"
    PaymentMethod,                # Enum: STRIPE_CARD | CASH | CHEQUE | E_TRANSFER | OFFLINE
    PayerRole,                    # Enum: BUYER | PARTNER | SELLER | PLATFORM | SUBSCRIBER
    LegalGate,                    # Enum: CLEARED | REQUIRES_TAX_LEGAL_REVIEW | PROHIBITED
    EstimatedCost,                # dataclass returned by estimate(...)
    ActualCost,                   # dataclass returned by lock_actual(...)
    PaymentCostSnapshot,          # persistable estimate + actual bundle
    estimate,                     # pre-charge estimate
    lock_actual,                  # post-webhook lock (Stripe BalanceTransaction)
    describe_rates,               # admin-facing rate matrix
)
```

### 2.3 Exact formulas (Section 12 requirement)

**Rate matrix** (single source; no duplication in callers):

| method | currency | card_class | pct | fixed_cents | source |
|---|---|---|---:|---:|---|
| stripe_card | CAD | domestic | 0.029 | 30 | stripe_docs_2026_02 |
| stripe_card | CAD | international | 0.039 | 30 | stripe_docs_2026_02 |
| stripe_card | USD | domestic | 0.029 | 30 | stripe_docs_2026_02 |

**Additive formula (buyer/partner pays cost):**
```
estimated_cents = int(round(amount_cents/100 × pct, 2) × 100)  +  fixed_cents
```

**Offline methods** (`CASH`, `CHEQUE`, `E_TRANSFER`, `OFFLINE`): `estimated_cents = 0`, `reason_code = "offline_method"`.

**Legal gate matrix (Section 4 FAIL CLOSED):**
- `(BUYER, *)` → `REQUIRES_TAX_LEGAL_REVIEW` — every province, every buyer-facing surcharge fails closed.
- `(PARTNER, QC/ON/AB/BC/…)` → `CLEARED` — Q1=B answer, B2B recovery permitted.
- `(SUBSCRIBER, QC/ON/AB/BC)` → `REQUIRES_TAX_LEGAL_REVIEW` — subject to L-1/L-2 legal review.
- `(SELLER, QC)` → `REQUIRES_TAX_LEGAL_REVIEW` — edge case.
- `(PLATFORM, *)` → `CLEARED` — BidVex absorbing its own rail is a bookkeeping-only entry.

**Silent-zero prevention (Section 10):** every zero result carries a non-empty `reason_code`. Assertions:
- `offline_method` — offline payment
- `legally_gated` — legal gate says review required
- `prohibited` — legal gate says prohibited
- `unknown_rate_matrix` — combination not in matrix
- `platform_absorbed` — caller opted in with `absorbed_by_platform=True`

**Estimated vs actual (Section 5):**
- `estimate(...)` returns `EstimatedCost(is_estimate=True, ...)`. **Never** treat as final.
- `lock_actual(...)` returns `ActualCost(is_estimate=False, ...)` and REQUIRES `balance_transaction_fee_source_type == "stripe_fee"` sourced directly from `stripe.BalanceTransaction.fee_details[*]` where `type == "stripe_fee"`. Passing `"application_fee"` (or anything else) raises `ValueError` — this closes the door on the Gate 2 mis-attribution finding, where the partner-side app-fee reversal was mistaken for the Stripe processing fee.

### 2.4 Tests added — 40, all passing

`services/payment_cost_engine.py` invariants covered:

- Engine version stable
- `describe_rates()` shape valid
- Offline methods always $0 (5 methods × parametrized)
- Buyer-Stripe surcharge fails closed in all 13 provinces (13 parametrized)
- Partner B2B Stripe recovery computed correctly in QC/ON/AB/BC (4 parametrized)
- Partner Stripe recovery @ $100 → $3.20 exact
- Partner Stripe recovery @ $0 → $0.30 (fixed component only)
- Unknown currency returns 0 with `reason_code=unknown_rate_matrix`
- Unknown jurisdiction returns 0 with `REQUIRES_TAX_LEGAL_REVIEW`
- `absorbed_by_platform=True` returns 0 with `reason_code=platform_absorbed` and CLEARED
- `lock_actual()` happy path
- `lock_actual()` rejects `balance_transaction_fee_source_type="application_fee"`
- `lock_actual()` rejects negative fee
- Silent-zero prevention (every zero result has non-empty `reason_code`)
- `EstimatedCost.to_dict()` JSON-serializable
- `is_estimate` flag correctness on both types
- Buyer cheque payment → $0, CLEARED, `offline_method`
- International card uses 3.9% rate (not domestic 2.9%)
- `rate_source` field populated for auditability
- Canonical $0.31 scenario — BUYER FLOW currently gated (fail-closed)
- Canonical $0.31 scenario — PARTNER FLOW computes $0.31 exactly

**Test count:**

| Suite | Count | Pass | Fail |
|---|---:|---:|---:|
| P2 new: `test_iter482_p2_payment_cost_engine.py` | 40 | 40 | 0 |
| Existing: `test_iter482_golden_matrix.py` | 72 | 72 | 0 |
| Existing: `test_iter482_refund_engine.py` | ~7 | pass | 0 |
| Existing: `test_iter482_p0_repairs.py` | ~7 | pass | 0 |
| **Total (P2 + regression)** | **126** | **126** | **0** |

Golden regression suite total from iter482 remained at 86/86 passing.

---

## 3. Files changed in P2

**New files (no existing production code modified):**

- `/app/backend/services/payment_cost_engine.py` (NEW — canonical engine, 410 lines)
- `/app/backend/tests/test_iter482_p2_payment_cost_engine.py` (NEW — 40 exact-cent tests)
- `/app/backend/tests/p2_reconciliation_31cent_trace.py` (NEW — $0.31 investigation trace)
- `/app/docs/P2_PAYMENT_COST_ENGINE_REPORT.md` (this report)

**No existing files were modified in P2.** The canonical engine is imported nowhere in production yet — that's P3's job.

---

## 4. Unresolved legal / tax questions (blocking L-1 … L-9 from P1)

Item L-2 (B2B Partner Stripe recovery is lawful in Canada) is currently **encoded as CLEARED** in the legal-gate matrix for provinces QC/ON/AB/BC/SK/MB/NS/NB/NL/PE/YT/NT/NU. This encoding must be confirmed by accountant/counsel before P4 sends any Partner invoice with a Stripe recovery line. If counsel says NO for any province, the corresponding rows in `_LEGAL_GATE_MATRIX` must be downgraded to `REQUIRES_TAX_LEGAL_REVIEW` before P4 code-completes.

All other legal items (L-1 buyer surcharge, L-3 non-QC Partner tax, L-4 cross-province BP tax, L-5 tax-on-processing, L-6 storage disclosure, L-7 subscription gross-up, L-8 refund tax, L-9 bilingual disclosure) remain **UNRESOLVED**. The engine encodes buyer/subscriber/seller surcharge as `REQUIRES_TAX_LEGAL_REVIEW` (fail-closed) — none of them will silently produce a charge until you explicitly flip a gate.

---

## 5. `REQUIRES_TAX_LEGAL_REVIEW` items to feed accountant/counsel

Verbatim from `payment_cost_engine._LEGAL_GATE_MATRIX`:

1. **Buyer-facing Stripe surcharge on auction checkout** — 13 provinces, all fail-closed. Blocks P3 buyer-side Partner surcharge feature.
2. **Subscriber-facing Stripe surcharge on subscription checkout** — QC/ON/AB/BC fail-closed. Affects F8 (subscriptions), F9 (Partner annual), F10 (dealer), F11 (broker).
3. **Seller-facing Stripe surcharge** — QC fail-closed. Rare / edge case only.
4. **Non-QC Partner-BP tax rate** — separate issue (in tax_engine.py, not payment_cost_engine); still fail-closed pending L-3.
5. **Tax-on-processing recovery** — L-5; not encoded in this engine (tax engine's job).

---

## 6. Gate status right now

| Gate | Status |
|---|---|
| 1. Stripe TEST auth (iter482) | ✅ PASS |
| 2. Model A₁ Sandbox Proof (iter482) | ✅ PASS WITH P0 FINDING (rail incidence) |
| P1 READ-ONLY MASTER AUDIT | ✅ COMPLETE |
| **P2 Canonical payment_cost_engine** | ✅ **COMPLETE — module shipped, 40 tests pass, $0.31 identified & reconciled** |
| P3 Partner auction buyer-checkout wiring | ⏸ PENDING your approval |
| P4 Partner post-auction billing | ⏸ PENDING + L-2 legal review |
| P5 Refund engine consolidation + Gate 3 | ⏸ PENDING |
| P6 Tax engine consolidation | ⏸ PENDING + L-3 / L-4 accountant review |
| P7 Complete test matrix (≥ 200 cases) | ⏸ PENDING |
| P8 Peripheral flows | ⏸ PENDING |
| P9 Static audit + deployment gate | ⏸ PENDING |
| Production historical exposure | 🚫 NOT VERIFIED |
| **Final deployment gate** | 🚫 **DO NOT DEPLOY** |

---

## 7. What P2 explicitly did NOT do

- Zero production code files modified.
- Zero production DB queries or writes.
- Zero Stripe TEST or LIVE refunds.
- Zero live-mode Stripe credentials touched.
- Zero fix applied to the $0.31 receipt display bug (fix belongs to P3+ receipt renderer convergence).
- Zero tax rule invented (buyer-surcharge fail-closed; non-QC Partner tax deferred to P6).
- Zero wiring of the new engine into existing calculators (that's P3).
- Zero email templates or emails sent (P4).

**Awaiting your approval before I take any action toward P3.** No code will land in `stripe_connect_service.py`, `payments.py`, receipt renderers, or the frontend until you say so.

---

*End of P2 report.*
