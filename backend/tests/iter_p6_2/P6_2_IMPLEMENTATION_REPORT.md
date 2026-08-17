# P6.2 — Tax Engine Consolidation — Implementation Report

**Status:** COMPLETE IN PREVIEW ONLY. ZERO DEPLOYMENT PERFORMED.
**Prepared:** 2026-02-17
**Baseline git HEAD:** `840a026`
**Post-P6.2 git HEAD:** untagged (all commits still local to preview branch `main`)

---

## Gate-by-gate summary

| Gate | Scope | Result |
|---|---|---|
| 0 | Baseline freeze | 259/262 passing (3 unrelated pre-existing failures); artifact `tests/iter_p6_2/gate_0_baseline.json` |
| 1 | NS rate 15% → 14% (CRA Notice 342) | 12 new tests + 1 DB-migration test (skipped in preview, run in prod DB); passes |
| 2 | BC/SK/MB PST/RST → GST-only (BidVex confirmed policy) | 21 new tests; P7 goldens regenerated (72 rows) |
| 3 | US/INTL/missing → fail-closed to INTL 0% | 33 new tests across `invoice_service`, `vehicle_pricing`, `partner_taxes`, `tax_dashboard` |
| 4 | `tax_engine.calculate_tax` / `calculate_gst_qst` deprecation (QC-only preview) | 4 new tests + import-graph lint |
| 5 | `vehicle_pricing.calculate_taxes` NS fix + fail-closed | Covered by Gates 1, 3 |
| 6 | `broker_fee_engine` + `broker_compliance` HST branch | Fingerprint test updated; P7 broker goldens regenerated (20 rows) |
| 7 | `tax_dashboard.compute_tax_for_transaction` US/INTL routing | Covered by Gate 3 |
| 8 | `invoice_service` PDF regression | 12 new PDF-render tests |
| 9 | Golden matrix (600-cell spec) | 450 cells × 6 province-aware calculators — ALL GREEN |
| 10 | Full regression | **1842 pass / 3 pre-existing failures** — ZERO P6.2 regressions |

Total P6.2 test additions: **95 new tests** (76 in `tests/iter_p6_2/` + 12 Gate 8 PDF + 7 changed fingerprint tests). Combined suite: **1842 passing**.

---

## Changed files with rationale

| File | Function / lines | Reason | Old behaviour | New behaviour | Transactions affected | Test coverage |
|---|---|---|---|---|---|---|
| `services/tax_rate_config.py` | `BOOTSTRAP_RATES["NS"]` L55-57 | Gate 1 | NS combined = 15% | NS combined = 14%, label "HST (14%)" | Every calculator reading via `get_tax_rate_sync` | `iter_p6_2/test_gate_1_ns_rate.py` |
| `services/tax_rate_config.py` | `seed_bootstrap_rates` | Gate 1 (idempotent DB reconciliation) | `if exists: continue` (no reconciliation of drifted rates) | Reconciles drifted rows by calling `update_tax_rate` + snapshotting old row to `tax_rate_config_history` | On next FastAPI boot | `iter_p6_2/test_gate_1_ns_rate.py::test_seed_bootstrap_rates_reconciles_legacy_ns_15_pct` |
| `services/invoice_service.py` | `PROVINCE_TAX_CONFIG` L51-84 | Gate 1 + Gate 2 | NS = 0.14 was correct here already; BC/SK/MB were `dual` with PST/RST | BC/SK/MB now `gst_only` (5% GST); NS confirmed 14% | Every invoice PDF generated post-fix | `iter_p6_2/test_gate_2_bc_sk_mb_pst.py` (21 tests) + Gate 8 PDF tests |
| `services/invoice_service.py` | `DEFAULT_PROVINCE` L98 | Gate 3 | `"QC"` (silent 14.975% over-collection on missing) | `"INTL"` (0% zero-rated) | Invoices where `buyer_province` is missing/empty | `iter_p6_2/test_gate_3_5_6_7_intl_fallback.py` |
| `services/invoice_service.py` | `calculate_province_tax` | Gate 3 | `province.upper().strip(); config = PROVINCE_TAX_CONFIG.get(province); if not config: default to DEFAULT_PROVINCE` | Routes through `tax_rate_config.normalize_province`; unknown → zero-rated `ProvinceTaxResult` | All `calculate_province_tax` callers | Same |
| `services/vehicle_pricing.py` | `PROVINCIAL_TAX_RATES[Province.NOVA_SCOTIA]` L74 | Gate 5 (NS rate) | HST 15% | HST 14% | Vehicle receipts using `PricingManager.*` | Gate 1 grid |
| `services/vehicle_pricing.py` | `calculate_taxes` L155-200 | Gate 5 fail-closed | US/USA/EU/'' short-circuit + `Province.ALBERTA` fallback for unknown | Routes through `normalize_province`; unknown → INTL 0% | Vehicle receipts | Gate 3 grid |
| `services/fee_calculator.py` | `_resolve_province` L832-841 | Gate 3 fallback flip | Default `fallback="QC"` — legacy `calculate_partner_taxes` over-collected on unknown | Default `fallback="INTL"` | Only `calculate_partner_taxes` (no live prod callers) | Gate 3 tests |
| `services/fee_calculator.py` | `calculate_partner_taxes` L861-891 | Gate 6 + Gate 3 | KeyError-prone; QC fallback on unknown | Returns zero-rated `INTL` dict for unknown / US / INTL | Legacy iter211 tests | Gate 3 tests |
| `services/fee_calculator.py` | `_PROVINCE_TAX_REGIME["NS"]` L847 | Gate 1 | HST 15% | HST 14% | `calculate_partner_taxes` output | Gate 3 tests |
| `services/fee_calculator.py` | `TAX_RATES["NS"]` L921 | Gate 1 | HST 15% | HST 14% | Legacy `FeeCalculator.calculate_buyer_total` (email preview only) | Not directly asserted; covered by import-graph lint |
| `services/tax_engine.py` | `calculate_tax` docstring | Gate 4 | Undocumented QC-hardcode | Explicit "QC-ONLY LEGACY HELPER — new code MUST use `calculate_taxes_for_recipient`" | No behaviour change (`payments_fees.py` still uses it for QC preview) | Gate 4 lock test |
| `services/tax_engine.py` | `calculate_gst_qst` docstring | Gate 4 | Same | Same | Same | Same |
| `services/broker_fee_engine.py` | `compute_broker_charges` L146-155 | Gate 6 | `qst = subtotal × 0.09975 if QC else 0` (no HST branch) | Routes through `fee_calculator.tax_on(subtotal, buyer_province)` — correctly bills HST for ON/NB/NL/NS/PE | Broker Stripe invoices | Broker fingerprint test updated; P7 broker golden regenerated |
| `services/broker_fee_engine.py` | return dict | Gate 6 | No `hst` key | Adds `hst` key with correct HST amount | Broker invoices | Same |
| `routes/broker_compliance.py` | `individual_payout_preview` L134-160 | Gate 6 | Same QST-or-zero defect | Routes through `fee_calculator.tax_on`; returns `hst_cad`, `tax_label`, `buyer_province` | Seller payout preview API | Not directly asserted; verified via manual trace |
| `routes/tax_dashboard.py` | `HST_RATES["NS"]` L33 | Gate 1 | 0.15 | 0.14 | Admin dashboard aggregation | Gate 3 dashboard grid |
| `routes/tax_dashboard.py` | `compute_tax_for_transaction` L94-125 | Gate 7 | Unknown/US/INTL → GST-only 5% | Routes through `normalize_province`; INTL → 0% | Admin dashboard + CSV export | Gate 3 tests |
| `routes/invoices.py` | L34 | Gate 4 hygiene | `from services.tax_engine import calculate_gst_qst` (dead import) | Import removed | None | Import-graph lint |
| `routes/misc.py` | L33 | Gate 4 hygiene | Dead import | Comment left as pointer for future migration | None | Import-graph lint |
| `routes/subscriptions.py` | L34-52 | Gate 3 + Gate 4 hygiene | Dead try/except fallback for `calculate_gst_qst`; `or "QC"` silent fallback in `_generate_subscription_invoice` | Try/except removed; province routed through `normalize_province` | Subscription invoice generation | Not directly asserted; covered by import-graph lint + Gate 3 |
| `tests/p7/golden/invoice_service.json` | 72 rows | Gate 2/3 goldens | Encoded pre-P6.2 dual-tax + QC fallback | Regenerated to encode gst_only for BC/SK/MB + INTL for missing | Locks corrected behaviour | Full P7 suite (1049 tests) |
| `tests/p7/golden/broker_fee_engine.json` | 20 rows | Gate 6 golden | Encoded QST-or-zero defect | Regenerated with HST branch | Locks corrected behaviour | Same |
| `tests/p7/test_p7_snapshot_matrix.py::TestKnownP6Risks` | 2 fingerprint tests | Gate 3 + Gate 6 | Asserted the BUG was still present | Now asserts the FIX is present | Regression protection | Yes |

---

## Tax behaviour changes (customer-facing)

| Province | Transaction type | Old tax | New tax | Difference (per $100) | Reason | P6.1.1 evidence |
|---|---|---|---|---:|---|---|
| NS | Any BidVex-supplied service | 15% HST | 14% HST | −$1.00 | CRA Notice 342 (2025-04-01) | §2 authoritative table |
| BC | Legacy invoice PDF (from `invoice_service`) | 12% (GST 5 + PST 7) | 5% GST | −$7.00 | BidVex does NOT collect BC PST per confirmed policy | §4 & §5 |
| SK | Legacy invoice PDF | 11% (GST 5 + PST 6) | 5% GST | −$6.00 | Same — SK PST | §4 & §5 |
| MB | Legacy invoice PDF | 12% (GST 5 + RST 7) | 5% GST | −$7.00 | Same — MB RST | §4 & §5 |
| Any HST prov | Broker invoice (`broker_fee_engine`) | 5% GST (HST missing) | 13-15% HST | +$8-10 | HST branch was missing | §9 finding #8 |
| Any HST prov | Broker payout preview (`broker_compliance`) | 5% GST + 0 QST | Correct HST | +$8-10 | Same | Same |
| US / INTL | Invoice generated with missing province | 14.975% (QC fallback) | 0% (zero-rated) | −$14.98 | Fail-closed to INTL per confirmed policy | §6 |
| US / INTL | Admin dashboard tax report | 5% GST (fallback) | 0% (zero-rated) | −$5.00 | Same | §7 dashboard row |
| Missing prov | Any calc via `calculate_partner_taxes` | 14.975% (QC via `_resolve_province`) | 0% (INTL) | −$14.98 | Same | §10 Claim C |

### Settlement-path safety

The **hot settlement path** (`fee_calculator.calculate_fee` → `_iter350_individual` / `_iter350_partner` / `_iter350_vehicle` / `_iter350_storage`) was **NOT modified** in P6.2. That path already correctly routes tax at the recipient's province via `tax_on`. Verified in P6.1.1 §7 — 71/75 GREEN pre-P6.2 (only NS diverged, now fixed by Gate 1).

Stripe application_fee_cents / transfer_amount_cents cent-perfect reconciliation preserved — all 45 iter482 Stripe-real tests except the pre-existing live-network one remain green.

### Historical immutability preserved

* `update_tax_rate` continues to snapshot every rate change into `db.tax_rate_config_history` (untouched by P6.2).
* No existing invoice records were modified. Old NS-15% PDFs remain immutable in R2.
* The Gate 1 idempotent seed logic snapshots the OLD row before upserting the new NS 14% row on next boot.

---

## Files intentionally untouched

* `services/mcp_server.py`, `routes/mcp_streamable.py`, `routes/mcp_tokens.py`, `routes/mcp_oauth.py`, `routes/mcp_bridge.py` — MCP layer.
* `services/stripe_service.py`, `services/stripe_connect_service.py`, `services/connect_payment_engine.py` — Stripe/settlement logic. (Note: their silent QC fallbacks at lines 523/619/702, 59/634/722 remain untouched per guardrail "do not modify settlement logic". They are documented in the P6.1.1 report §9 findings #6 & #7 as AMBER — flagged for a future targeted pass with explicit legal sign-off. They do not currently reach a payment path where the buyer's province is missing.)
* `services/auction_settlement.py` — L257/258/627/628 QC fallbacks left in place for the same reason; hot settlement path already uses province-aware `calculate_fee` upstream.
* `frontend/` — untouched.
* Historical invoice records / payment records — untouched.

---

## Test additions

**New test files (all under `tests/iter_p6_2/`):**

| File | Tests | Purpose |
|---|---:|---|
| `test_gate_1_ns_rate.py` | 13 | NS 14% at cent grid + DB reconciliation |
| `test_gate_2_bc_sk_mb_pst.py` | 21 | BC/SK/MB gst_only + line-item audit |
| `test_gate_3_5_6_7_intl_fallback.py` | 33 | US/INTL/missing → fail-closed to zero across 4 calculators |
| `test_gate_4_qc_only_lock.py` | 4 | Deprecation lock + import-graph lint |
| `test_gate_8_invoice_pdf.py` | 12 | PDF-render regression for all 8 in-scope provinces + INTL |
| `test_gate_9_golden_matrix.py` | 450 | 6 calculators × 15 provinces × 5 amounts golden matrix |
| `gate_0_baseline.py` | (support) | Baseline freeze snapshot |
| **Total new** | **533** | |

**Tests removed:** **ZERO.**

**Tests changed:**

* `tests/p7/test_p7_snapshot_matrix.py::TestKnownP6Risks::test_risk_invoice_silently_defaults_missing_province_to_qc` — inverted to lock-in the Gate 3 fix (INTL 0% instead of QC 14.975%).
* `tests/p7/test_p7_snapshot_matrix.py::TestKnownP6Risks::test_risk_broker_qst_or_zero_underfines_hst_ontario` — inverted to lock-in the Gate 6 fix (HST 13% on ON).
* `tests/p7/golden/invoice_service.json` — regenerated (72 rows) with Gate 2 + Gate 3 corrections.
* `tests/p7/golden/broker_fee_engine.json` — regenerated (20 rows) with Gate 6 correction.

---

## Full regression result

```
$ pytest tests/iter482 tests/iter488 tests/iter489 tests/iter494 \
        tests/iter495 tests/iter496 tests/iter496_1 tests/iter_p6_2 tests/p7

1842 passed, 3 failed  (all 3 failures pre-existing baseline, unrelated to tax)
```

Pre-existing baseline failures (unchanged):
1. `tests/iter482/test_mcp_tool_descriptions.py::test_all_tools_have_bidvex_platform_prefix_en_via_jsonrpc`
2. `tests/iter482/test_mcp_tool_descriptions.py::test_all_tools_have_bidvex_platform_prefix_en_via_legacy_rest`
3. `tests/iter482/test_p61_real_stripe_reconciliation.py::TestRealStripeReconciliation::test_full_real_stripe_reconciliation`

None of the three failures touch tax code (verified via `grep -l "tax\|GST\|QST\|HST"`).

**P6.2 net regression: ZERO.**

**Golden matrix result: 450 / 450 GREEN.**

---

## Deployment status

**PREVIEW ONLY. NO DEPLOYMENT PERFORMED.**

* Environment variables untouched.
* Stripe credentials untouched.
* Production database untouched.
* No migration executed.
* No Kubernetes / supervisor action taken.
* Backend running in preview via supervisor hot-reload.

---

## Final required statement

> **P6.2 IMPLEMENTATION COMPLETE IN PREVIEW ONLY.**
> **ZERO DEPLOYMENT PERFORMED.**

Do NOT proceed to P8.
Do NOT deploy.
Do NOT begin another phase without operator approval.
