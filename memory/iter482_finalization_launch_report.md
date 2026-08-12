# iter482 Finalization — Launch-Readiness Report (Feb 12, 2026)

**STATUS: LAUNCH-READY (TEST MODE)** · **DO NOT DEPLOY**

Audit scope: Stripe fee correctness · actual fee reconciliation · billing documents · payment consistency · PDF verification.

---

## 1 · Payment

| Check                                                | Result | Evidence                                                                                        |
| ---------------------------------------------------- | ------ | ----------------------------------------------------------------------------------------------- |
| Canonical engine used everywhere                     | ✅     | `services/payment_cost_engine.py` — only calculator; no duplicates found in grep audit          |
| Canadian card 2.9% + $0.30 (gross-up)                | ✅     | `$100 hammer` → estimate 333c, recovery 344c (verified via `/auction-winner-preview`)           |
| International card 3.9% + $0.30                      | ✅     | Rate matrix keyed `(STRIPE_CARD, CAD, international)`; SHORTFALL row proves 3.9% engagement     |
| Offline methods (Cash, E-Transfer, Cheque) → $0      | ✅     | Frontend + backend force 0 with reason `offline_method` (verified UI screenshot + API)          |
| Payer-bears-fee (no silent BidVex absorption)        | ✅     | L-1 CLEARED across 13 provinces; anti-regression test `test_anti_regression_stripe_never_silent_zero` |
| Actual Stripe fee reconciliation                     | ✅     | `services/stripe_reconciliation_service.py` reads BalanceTransaction.fee_details on `payment_intent.succeeded` |
| Estimated / Recovery / Actual stored separately      | ✅     | Fields: `estimated_cents`, `recovery_cents`, `actual_cents`, `variance_cents` (never overwrite) |
| Card country persisted                               | ✅     | `card_country` + `resolved_jurisdiction` in `payment_processing_reconciliation` collection      |
| Webhook idempotency                                  | ✅     | `$setOnInsert` on `payment_intent_id`; proven — 2 seed runs → 2 rows (not 4)                    |

---

## 2 · Billing Documents (PDF Visual QA)

Ran the ACTUAL PDF generators end-to-end for the canonical `$100 Individual seller · CA card` scenario. Files saved to `/tmp/iter482_final_*.pdf` and inspected via `analyze_file_tool`:

| Document                                     | Total     | Amounts Verified                                            | Result |
| -------------------------------------------- | --------- | ----------------------------------------------------------- | ------ |
| Buyer Universal Receipt (EN)                 | $107.98   | Hammer $100 · BP $3.50 · BP GST $0.35 · BP QST $0.69 · Stripe $3.44 | ✅     |
| Buyer Universal Receipt (FR — bilingual)     | 107,98 $  | Same amounts w/ French labels (REÇU / Marteau / Prime / TPS / TVQ / Frais Stripe / TOTAL PAYÉ) | ✅     |
| Marketplace Seller Statement                 | $95.40 net| Hammer $100 · Comm $4.00 · Comm GST $0.20 · Comm QST $0.40 · Net $95.40 | ✅     |
| Marketplace Seller Receipt                   | $95.40    | Same seller totals via seller_statement source              | ✅     |
| Marketplace Seller Commission Invoice        | $4.60 due | Hammer $100 · Comm $4.00 · Comm GST $0.20 · Comm QST $0.40  | ✅     |

**Every document displays:** BidVex letterhead · Buyer + Seller identification blocks · itemized settlement breakdown · legal footer (`GST 706766367RT0001 · QST 1233530880TQ0001`) · bilingual EN/FR when requested.

**Stripe processing fee** is present ($3.44) on buyer docs when paid via card, and correctly `—` on offline paths / seller docs (charged-to = buyer).

---

## 3 · Reconciliation

Persisted 2 canonical test rows and verified admin API:

```
GET /api/admin/stripe-reconciliation/summary
{
  "total_rows": 2,
  "covered": 1, "shortfall": 1, "unknown": 0, "error": 0,
  "variance_cents_covered": 11,     ← domestic CA card: recovery > actual by 11¢
  "variance_cents_shortfall": -94,  ← international US card: actual > recovery by 94¢
}
```

Both rows show `estimated_cents`, `recovery_cents`, `actual_cents`, `variance_cents`, `card_country`, `resolved_jurisdiction` — separately, never overwritten.

---

## 4 · Chain Reconciliation ($100 scenario)

```
Checkout displayed total  = 107,98 $   (screenshot /tmp/iter482_final_checkout_stripe_fixed.png)
Backend calc buyer_total  = 107.98     (winner-preview API)
Stripe PaymentIntent amt  = 10798      (metadata / persisted)
Persisted receipt total   = 107.98     (db.receipts.total_charged)
PDF total (buyer receipt) = $107.98    (Gemini analyzer confirmed)
PDF total (seller stmt)   = $95.40 net (Gemini analyzer confirmed)
Invoice line total (comm) = $4.60      (Gemini analyzer confirmed)
```

All amounts agree to the cent.

---

## 5 · Tests

| Suite                                                | Result   |
| ---------------------------------------------------- | -------- |
| `test_iter482_p0_repairs.py`                         | 10/10    |
| `test_iter482_p2_payment_cost_engine.py`             | 40/40    |
| `test_iter482_p3_fee_calculator_canonical.py`        | 16/16    |
| `test_iter482_p31_reconciliation.py`                 | 38/38    |
| `test_iter482_p4a_foundation.py`                     | 51/51    |
| `test_iter482_p4_end_to_end.py` (isolated re-run)    | 14/14    |
| `test_iter482_p5_payer_bears_fee.py`                 | 31/31    |
| `test_iter482_p51_reconciliation.py`                 | 10/10    |
| `test_iter482_golden_matrix.py`                      | 40/40    |
| **Total**                                            | **250/250** |
| Focused PDF/scenario tests (finalization script)     | 5 PDFs  |
| Stripe TEST reconciliation                           | PASS     |
| Frontend E2E smoke (Stripe ↔ Offline switch)         | PASS     |

Note: `test_iter482_p4_end_to_end.py` triggers a per-IP `/api/auth/register` rate-limit (1 req/min) when run in the full-suite pass. Isolated re-run passes 14/14 immediately. Non-blocking flake (same as iteration_463).

---

## 6 · Bugs Fixed During Audit

### 🔴 LAUNCH-BLOCKER — Fixed
**Checkout sidebar "Frais + Taxes" line was under-counting.**
- **Root cause**: `CheckoutPage.js` summed `breakdown.fees_tax_total + hammer_tax_total`. Neither field exists on the backend response — the canonical fields are `total_tax`, `gst`, `qst`, `hst`. Sidebar was displaying `$3.50` when correct value is `$4.54` (BP $3.50 + tax $1.04). Total row was correct at $107.98, so the *only* misleading value was the sidebar mid-line.
- **Fix**: `CheckoutPage.js` sidebar row now sums `buyer_premium + platform_fee + total_tax + hammer_tax_total` (canonical keys). Added `data-testid="checkout-summary-fees-taxes"`.
- **Verification**: Screenshot `/tmp/iter482_final_checkout_stripe_fixed.png` shows Stripe path with sidebar 100 + 4,54 + 3,44 = 107,98 (matches Total) and cash path with sidebar 100 + 4,54 + 0,00 = 104,54 (matches Total).

---

## 7 · Remaining Issues

### 🔴 LAUNCH BLOCKERS
**None.**

### 🟡 POST-LAUNCH (cosmetic / non-financial)
- **FR receipt labels "TPS sur prime" / "TVQ sur prime"** slightly misleading — the taxable base is `BP + processing_recovery`, not just BP. The value ($0.35 / $0.69) and Total ($107.98) are correct; only the label is imprecise. Recommend future rename to "Taxes acheteur" / "Buyer taxes".
- **Line-item `Comm. tax` column** in the seller commission invoice PDF is not obvious from the header alone. Total column already sums correctly. Recommend header tooltip / clarifying description.
- **Auth per-IP rate limit (1 req/min)** on `/api/auth/register` causes flakes when running full backend test suites. Non-blocking; a session-scoped fixture reusing existing users would eliminate this. Filed as DX improvement.
- **International-card variance email automation** — deferred from P5.1. Ledger has `SHORTFALL` rows; a follow-up job could email the delta. Not launch-blocking; admin can already review via `/api/admin/stripe-reconciliation`.

---

## 8 · Guardrails Honoured

✅ Stripe TEST mode only  ·  ✅ No production data mutated  ·  ✅ No historical financial records modified  ·  ✅ No real refunds  ·  ✅ Reused existing P4/P5/P5.1 architecture (no new calculators, no new dashboards, no redesign)  ·  ✅ Fixed exactly one financial-consistency bug and re-verified  ·  ✅ 250/250 iter482 regression suite green  ·  ✅ 5/5 critical PDFs verified visually

## 9 · Do NOT Deploy
Preview environment only. Live keys not touched. No refunds executed. Stripe production reconciliation (P9 audit) still deferred per plan.
