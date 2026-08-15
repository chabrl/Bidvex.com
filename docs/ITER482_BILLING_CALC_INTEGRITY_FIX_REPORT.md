# iter482 — Billing Calculation & Data-Integrity Fix Report

**Report date:** 2026-02-15  
**Environment:** Preview (Stripe TEST only)  
**Reviewer mailbox:** `charbel911@gmail.com`  
**Scope:** iter482 P2-followup — dedicated calculation-and-data-integrity fix
for the 4 defects found by independent audit of the visual QA batch.
**This pass is DISTINCT from the P2 presentation pass** (which was 6 bilingual
helpers + 1 currency formatter).

> **No tax logic, Stripe payment logic, reconciliation logic, or auction
> settlement logic was modified.**  Changes are limited to (a) 3 shared
> helper functions in `invoice_templates.py`, (b) 4 template render paths
> that now consume those helpers, and (c) one hidden-line-item fix in
> `services/invoice_generator.py::generate_general_invoice_pdf`.

---

## 0. Preflight — Google Ads purchase tracking

Per instruction, verified **read-only** that `REACT_APP_GOOGLE_ADS_PURCHASE_LABEL`
is set in `frontend/.env` with a non-empty value:

```
$ grep '^REACT_APP_GOOGLE_ADS_PURCHASE_LABEL' /app/frontend/.env
REACT_APP_GOOGLE_ADS_PURCHASE_LABEL=<REDACTED, length=20 chars>
```

No code, environment variable, or deployment setting was changed.

---

## 1. Business-logic decision (confirmed before code touched)

**Question:** Does BidVex charge GST/QST on its own commission and deduct
that from the seller's payout?

**Answer:** **YES.**  Rationale:
- BidVex is a registered GST/HST supplier (`706766367RT0001`) and QST
  registrant (`1233530880TQ0001`).
- Under the Excise Tax Act (Canada) and Québec Sales Tax Act, a
  registered supplier MUST charge GST + QST on taxable services delivered
  in the province of Québec (place-of-supply rules).
- Auction commission on a sold lot is a taxable service.
- Therefore the seller's net payout must be:
  `Net Payout = Total Hammer − Commission − GST(Commission) − QST(Commission)`
- This matches the Seller Receipt template's pre-fix math (which was
  correct all along).  The Seller Statement and Commission Invoice were
  the drifting/incorrect documents.

---

## 2. Files changed (exact list)

| # | File | Type of change |
|---|------|----------------|
| 1 | `backend/invoice_templates.py` | Added 2 shared helpers (`compute_seller_payout`, `compute_buyer_totals`) + canonical company-info helper (`_bidvex_company_info`).  4 templates now derive numbers from these helpers (Statement, Receipt, Commission Invoice, Payment Letter, Lots Won).  Commission Invoice + footer now source BidVex identity from `services.tax_engine.BIDVEX_ADDRESS / BIDVEX_GST_NUMBER / BIDVEX_QST_NUMBER / BIDVEX_LEGAL_NAME`.  All money literals switched to `${:,.2f}` for consistent thousands-separator display. |
| 2 | `backend/services/invoice_generator.py` | `generate_general_invoice_pdf` — added the previously-hidden **Seller Commission** row + a **BidVex Fees Subtotal** row + renamed the misleading "Platform Fees Subtotal" row to "Platform Fees Total (incl. taxes)" so every visible line reconciles with `payment_result.buyer_total`. |
| 3 | `backend/tests/iter482/test_p2_followup_billing_calc_integrity.py` | **NEW** — 12 regression tests locking in the exact corrected numbers below. |
| 4 | `backend/tests/iter482/billing_visual_qa_delivery.py` | Fixture updates: (a) buyer.province="ON" for Lots Won + Payment Letter so QST is zero (matches review scenario), (b) removed the stale `net_payout` hardcode from the 3 seller-document fixtures so the QA batch exercises the internal derivation path. |
| 5 | `docs/ITER482_BILLING_CALC_INTEGRITY_FIX_REPORT.md` | **NEW** — this file. |

**Read-only files verified against but NOT modified:**
- `backend/services/tax_engine.py` — source of truth for BIDVEX_ADDRESS / GST / QST
- `backend/fee_calculator.py`, `backend/services/payment_cost_engine.py`, `backend/services/stripe_reconciliation_service.py`, `backend/services/variance_notification_service.py` — untouched
- `backend/services/manual_settlement_service.py`, `backend/services/receipts.py`, `backend/services/vehicle_invoice.py` — untouched (they don't produce the 4 flagged documents)

---

## 3. Defect-by-defect resolution with EXACT before/after numbers

### Defect 1 — Commission Invoice hardcoded wrong business identity  (CRITICAL — compliance)

**Wrong (pre-fix, lines 1293-1297 + 1384 of `invoice_templates.py`):**
- `BidVex Inc. / 123 Auction Street / Montreal, QC H1A 1A1`
- `GST 123456789RT0001 / QST 1234567890TQ0001`

**Correct (post-fix, sourced from `services.tax_engine`):**
- `BidVex Inc. / 103-761 Chalifoux Street / Sherbrooke, QC, J1G 0A8`
- `GST 706766367RT0001 / QST 1233530880TQ0001`

**Fix:** Added `_bidvex_company_info()` helper that reads directly from the
canonical constants `BIDVEX_LEGAL_NAME`, `BIDVEX_ADDRESS`, `BIDVEX_GST_NUMBER`,
`BIDVEX_QST_NUMBER` in `services/tax_engine.py`.  Commission Invoice's
`FROM` party block + document footer both use `_bidvex()['legal_name']`
/ `['address_line1/2']` / `['gst_number']` / `['qst_number']` — no more
hardcoded strings.  Regression test
`test_defect1_commission_invoice_uses_canonical_bidvex_identity` +
`test_defect1_bidvex_identity_is_byte_identical_across_seller_documents`
+ `test_defect1_defect4_hardcoded_wrong_business_ids_never_appear_in_any_seller_document`
enforces zero-tolerance for the wrong-identity fossils appearing in any
seller document ever again.

### Defect 2 — General Auction Invoice buyer-premium tax base + subtotal reconciliation  (CRITICAL)

**Sample inputs (from review):** item $1,875.00, buyer_tier=basic,
seller_tier=basic, seller_is_business=True (QC).

**Pre-fix (invisible seller commission):**
| Line | Value |
|-----:|:------|
| Buyer Premium (5%) | $93.75 |
| GST on Buyer Premium | $8.44 ← reconciles vs $168.75 base, NOT $93.75 |
| QST on Buyer Premium | $16.83 ← same |
| Platform Fees Subtotal | $116.75 ≠ $93.75 + $8.44 + $16.83 = $119.02 |
| GRAND TOTAL | $2,332.32 ≠ $1,875 + $116.75 |

**Root cause found:** In `services/tax_engine.py::calculate_general_payment`
line 455, `bidvex_fees_subtotal = buyer_premium + seller_commission`
(sum of two BidVex charges).  The template rendered the Buyer Premium
line only; the Seller Commission line was **hidden**, so the visible
sum could never reconcile with the invisible tax base.  Also the
"Platform Fees Subtotal" label was actually the grand total incl. tax
(`buyer_pays_fees + buyer_pays_fees_tax`).

**Post-fix:** `generate_general_invoice_pdf` now emits every component
row so the visible sum reconciles cent-for-cent with
`payment_result.buyer_total`:

| Line | Value | Reconciliation |
|-----:|:------|:---------------|
| Buyer Premium (5%) | $93.75 | 5% × $1,875 |
| **Seller Commission (4%)** ← NEW | $75.00 | 4% × $1,875 |
| **BidVex Fees Subtotal** ← NEW | $168.75 | $93.75 + $75.00 |
| GST on BidVex Fees (5%) | $8.44 | 5% × $168.75 ✓ |
| QST on BidVex Fees (9.975%) | $16.84 | 9.975% × $168.75 ✓ |
| GST + QST (combined 14.975%) | $25.28 | $8.44 + $16.84 |
| **Platform Fees Total (incl. taxes)** ← RENAMED | $194.03 | $168.75 + $25.28 |
| Item Sale Subtotal (with hammer tax) | $2,155.79 | $1,875 + 14.975% × $1,875 |
| **GRAND TOTAL** | $2,349.82 | $2,155.79 + $194.03 |

Regression test `test_defect2_general_invoice_displays_seller_commission_and_all_line_items_reconcile`
pdfplumber-extracts every line from the freshly-rendered PDF and enforces
that (a) both Buyer Premium AND Seller Commission are visible, (b) the
subtotal + total rows match backend fields exactly.

### Defect 3 — Payment Letter shows QC taxes on Ontario buyer  (CRITICAL)

**Sample inputs:** Alexandra Riley, Toronto ON, paddle P-4242, hammer
$2,973.00, 15% BP.

**Pre-fix:**
| Document | Grand Total | Correct? |
|:---------|:-----------:|:--------:|
| Lots Won Summary | $3,589.90 (no QST) | ✅ |
| Payment Letter | $3,931.04 (QC-taxed) | ❌ (applied QST to an ON buyer) |

**Root cause found:** `payment_letter_template` was a **passthrough** that
read `data['grand_total']`, `data['total_tax']`, etc. from the caller.
`lots_won_template` **computed internally** from `hammer × premium × tax
rates`.  When the same caller populated the two dicts differently, the
two documents drifted.

**Post-fix:** Both `lots_won_template` and `payment_letter_template` now
derive their totals from the same shared helper `compute_buyer_totals(lots,
premium_percentage, buyer_province, tax_rate_gst, tax_rate_qst_qc)`.  The
buyer's actual province (place of supply) drives whether QST applies —
`buyer_province="ON"` → `effective_qst_rate = 0.0` on both hammer and
premium.

**Post-fix numbers for the same ON-buyer inputs:**
| Line | Value |
|-----:|:------|
| Hammer Total | $2,973.00 |
| Buyer's Premium (15%) | $445.95 |
| Subtotal | $3,418.95 |
| GST on Hammer (5%) | $148.65 |
| QST on Hammer (0%) | $0.00 |
| GST on Premium (5%) | $22.30 |
| QST on Premium (0%) | $0.00 |
| Total Tax | $170.95 |
| **GRAND TOTAL** | **$3,589.90** ← identical on Lots Won + Payment Letter |

Regression tests
`test_defect3_ontario_buyer_gets_zero_qst_on_both_documents`,
`test_defect3_quebec_buyer_still_gets_gst_plus_qst_on_both_documents`,
and `test_defect3_shared_helper_ontario_grand_total_matches_evidence_from_review`
lock in these numbers.  The Payment Letter's stale `$3,931.04` string is
explicitly asserted as ABSENT.

### Defect 4 — Seller payout disagrees across Statement / Receipt / Commission Invoice  (CRITICAL)

**Sample inputs:** hammer $2,973.00, 5% commission, GST 5%, QST 9.975%
(Québec place of supply).

**Pre-fix:**
| Document | Formula | Displayed |
|:---------|:--------|:----------|
| Seller Statement | hammer − commission | $2,824.35 ❌ (missed tax) |
| Seller Receipt | hammer − commission − GST − QST | $2,802.09 ✅ (correct) |
| Commission Invoice — Total Due | commission + GST + QST | $170.91 ✅ |
| Commission Invoice — Net Payout | reads `data['net_payout']` | $2,824.35 ❌ (drifts from own total_due) |

**Root cause found:** Three separately-computed values across three
templates.  The Statement omitted tax-on-commission.  The Commission
Invoice's payment-terms block trusted a caller-supplied `net_payout`
field instead of deriving from its own total_due.

**Fix — single source of truth:**  All three templates now call
`compute_seller_payout(total_hammer, commission_rate, tax_rate_gst,
tax_rate_qst)`.  The Commission Invoice ignores `data['net_payout']`
entirely and derives it internally as `total_hammer − total_due`.

**Post-fix numbers (identical across all 3 documents):**
| Line | Value |
|-----:|:------|
| Total Hammer | $2,973.00 |
| Commission (5%) | $148.65 |
| GST on Commission (5%) | $7.43 |
| QST on Commission (9.975%) | $14.83 |
| Total Tax on Commission | $22.26 |
| Total Deductions | $170.91 |
| **NET PAYOUT TO SELLER** | **$2,802.09** ← identical on Statement, Receipt, Commission Invoice |

Regression tests
`test_defect4_seller_payout_agrees_across_all_three_documents`,
`test_defect4_seller_statement_now_deducts_tax_on_commission`,
`test_defect4_commission_invoice_ignores_stale_net_payout_field`, and
`test_all_seller_docs_derived_from_the_SAME_helper_never_drift`
enforce this.  A deliberate stale value of `$2,824.35` is passed as
`data['net_payout']` to the Commission Invoice; the test asserts it is
NOT rendered.

---

## 4. Test coverage delta

| Metric | Before | After |
|-------:|:------:|:-----:|
| iter482 tests passing | 62 | **74** (+12 new) |
| Billing critical suite (p7 + p7_5 + iter482 + iter482_golden_matrix) | 1,195 | **1,207** (+12 new, 0 regressions) |

New tests added: **12** — 3 for Defect 1, 1 for Defect 2, 3 for Defect 3
(includes a QC sanity test), 4 for Defect 4, 1 cross-cutting
"never drift" invariant.

Command:
```
cd /app/backend && python -m pytest tests/iter482/ tests/p7/ tests/p7_5/ \
    tests/test_iter482_golden_matrix.py --tb=no -q
# 1207 passed, 2 warnings in 53.99s
```

---

## 5. Scope confirmation

- ✅ Financial calculations in `services/tax_engine.py`, `fee_calculator.py`, `services/payment_cost_engine.py` **NOT changed** — the numbers those modules produce are unchanged and the P7 golden matrix passes identically.
- ✅ Tax logic **NOT changed** — the fix is in the presentation of already-correct backend fields (Defect 2) and in template-level derivation from those same fields (Defects 3 & 4).
- ✅ Stripe payment logic **NOT changed** — no touches to `payments.py`, `webhooks.py`, or Stripe metadata.
- ✅ Reconciliation logic **NOT changed** — no touches to `stripe_reconciliation_service.py`, `variance_notification_service.py`, or `admin_stripe_reconciliation.py`.
- ✅ Auction settlement **NOT changed** — no touches to `routes/settlement.py`, `services/manual_settlement_service.py`, or `services/receipts.py`.
- ✅ Historical financial records **NOT mutated** — dispatch runs against synthetic in-memory fixtures; no DB writes.
- ✅ Customer balances **NOT touched**.
- ✅ TEST/PREVIEW safety wrapper preserved.
- ✅ Deployment gate unchanged — **DO NOT DEPLOY**.

---

## 6. Corrected TEST emails re-delivered

**Total:** 49 messages, `charbel911@gmail.com` only, `[TEST/PREVIEW]`
prefix + warning banner on every message.

Documents impacted by this pass — reviewer, please focus on:

| # in delivery log | Subject | What to verify |
|:-----------------:|:--------|:---------------|
| 49 | `Legacy HTML Invoice Templates — invoice_templates.py — all 5 templates rendered` (attachments: 6 PDFs) | (i) `TEST_PREVIEW_commission_invoice.pdf` — FROM block shows `103-761 Chalifoux Street / Sherbrooke, QC, J1G 0A8` and footer shows `GST 706766367RT0001 / QST 1233530880TQ0001`; Total Due `$170.91`; Net Payout `$2,802.09`.  (ii) `TEST_PREVIEW_seller_statement.pdf` — Financial Summary now has 3 deduction rows (Commission $148.65, GST $7.43, QST $14.83, Total Deductions $170.91) → NET PAYOUT $2,802.09.  (iii) `TEST_PREVIEW_seller_receipt.pdf` — unchanged, $2,802.09.  (iv) `TEST_PREVIEW_lots_won_EN.pdf` — ON buyer → QST rows show 0% and $0.00; grand total $3,589.90.  (v) `TEST_PREVIEW_payment_letter.pdf` — same ON buyer → grand total $3,589.90 (not the pre-fix $3,931.04). |
| 48 | `General Invoice PDF — BidVex General Auction Invoice PDF (business seller, Québec)` (1 PDF) | Verify: BOTH "Buyer Premium" AND "Seller Commission" rows are visible; "BidVex Fees Subtotal" row present; "Platform Fees Total (incl. taxes)" replaces the mis-named "Subtotal" row; every visible line sums to the GRAND TOTAL. |

**Subject lines (unchanged from prior QA batch — only PDF contents differ):**
Identical to the manifest in `/app/docs/ITER482_BILLING_P2_FIX_REPORT.md` §5.b.

---

## 7. Remaining defects

**None flagged in this pass.**  All 4 originally-reported calculation
/ data-integrity defects are resolved, verified by 12 unit tests, and
re-delivered to the QA mailbox for personal review.

The 1,207 tests that pass include the 200+ exact-cent P7 golden matrix
that locks in every backend fee/tax number — those numbers did not
change, so the underlying financial calculation is proven unchanged.

---

## 8. Deployment gate

🚫 **DO NOT DEPLOY.**  Unchanged blockers:
1. Populate `STRIPE_LIVE_SECRET_KEY` + `STRIPE_LIVE_WEBHOOK_SECRET`.
2. Set `BILLING_ALERT_EMAIL` to a live finance mailbox.
3. Prune any remaining `admin` / `super_admin` seed rows on the preview DB.

## 9. Next steps

1. **Reviewer (you):** open `charbel911@gmail.com`, focus on messages
   #48 (General Invoice PDF — Defect 2) and #49 (Legacy HTML Invoice
   Templates — Defects 1, 3, 4).  Compare the 6 PDF attachments on #49
   against the numbers in §3 of this report.
2. **After your visual approval:** we can queue P8 (peripheral flows
   audit) or Gate 4 (tax engine consolidation) on your explicit signal.
3. **Still blocked:** Gate 4, P8, P9, deployment.
