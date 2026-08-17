# P6.1.1 — Golden Regression Matrix Specification (DESIGN ONLY)

**Status:** DESIGN specification — NOT executable, NOT installed as a truth oracle.
This document specifies the P6.2 regression matrix. It DOES NOT
implement any test that asserts current behaviour is correct.

**Purpose:** Give P6.2 an explicit `REFERENCE EXPECTATION` for every
(calculator × province × amount) cell so that any behaviour change during
consolidation is either INTENDED (matches the reference) or REGRESSION
(does not match the reference and is not on the approved delta list).

---

## 1. Confirmed reference inputs (per operator's legal/accounting confirmation)

| Input | Confirmed value | Source |
|---|---|---|
| Federal GST/HST rates (2026) | See §2 | CRA canada.ca "GST/HST rates by province" |
| Nova Scotia HST effective 2025-04-01 | **14%** (not 15%) | CRA Notice 342 |
| Quebec QST | 9.975% (federal 5% + QST 9.975% separately shown) | Revenu Québec IN-203-V |
| BidVex collection of BC PST (7%) | **NOT collected by BidVex** on platform B2B services | `services/tax_rate_config.py` inline note; confirmed by operator |
| BidVex collection of SK PST (6%) | **NOT collected by BidVex** on platform B2B services | Same |
| BidVex collection of MB RST (7%) | **NOT collected by BidVex** on platform B2B services | Same |
| US / INTL recipient | **0% (zero-rated exported service)** | ETA Sched. VI Part V §7 |
| Unknown / missing province | **INTL (0%) — fail-closed**, NOT QC | `services/tax_rate_config.py::normalize_province` — confirmed policy |
| Marketplace facilitator obligation on hammer | Applies to **non-resident vendors** only (ETA §211.1). Canadian-resident sellers → NOT auto-obligated | CRA §211.1 + digital economy guidance |

## 2. Reference federal rate table (`REFERENCE_FEDERAL`)

| Province | Federal rate | Provincial (informational only, NOT collected by BidVex) |
|---|---|---|
| AB | 5% GST | — |
| BC | 5% GST | 7% PST (BC Min. of Finance — NOT via BidVex) |
| MB | 5% GST | 7% RST (Manitoba Finance — NOT via BidVex) |
| NB | 15% HST | — |
| NL | 15% HST | — |
| **NS** | **14% HST** | — |
| NT | 5% GST | — |
| NU | 5% GST | — |
| ON | 13% HST | — |
| PE | 15% HST | — |
| QC | 5% GST **+ 9.975% QST** (both collected by BidVex; BidVex is QC-registered) | 9.975% QST (Revenu Québec — collected via BidVex) |
| SK | 5% GST | 6% PST (Sask. — NOT via BidVex) |
| YT | 5% GST | — |
| US | 0% (zero-rated exported service) | — |
| INTL | 0% (zero-rated exported service) | — |

## 3. Test grid dimensions

* **Calculators (8):** `tax_engine.calculate_tax`, `tax_engine.calculate_gst_qst`,
  `tax_engine.calculate_taxes_for_recipient`, `vehicle_pricing.calculate_taxes`,
  `fee_calculator.tax_on`, `fee_calculator.calculate_partner_taxes`,
  `invoice_service.calculate_province_tax`, `tax_dashboard.compute_tax_for_transaction`
* **Provinces (15):** all 13 CA provinces/territories + `US` alias + `INTL`
* **Amounts (5):** `$0.01`, `$1`, `$100`, `$1,000`, `$500,000`
* **Transaction types (design-time only, not exhaustive yet):**
  buyer_premium, seller_commission, partner_platform_fee,
  vehicle_2_5, storage_5, broker_2_5, subscription, marketplace_hammer

Total cells (calc × prov × amount): 8 × 15 × 5 = **600 cells**.

## 4. Cell semantics

For each cell the matrix records FOUR quantities:

1. **`reference_federal_amount`** — `amount × REFERENCE_FEDERAL[prov]`, 2dp round-half-up.
2. **`reference_qst_amount`** — `amount × 0.09975` if `prov == "QC"` else `0`.
3. **`reference_pst_rst_amount`** — informational only; ALWAYS 0 in
   what BidVex collects (per confirmed policy). Emitted in a separate
   report column so a future policy change can be evaluated without
   editing the reference oracle.
4. **`reference_total_bidvex_collected`** — sum of (1) + (2).

## 5. Classification rule for every cell

```
if actual == reference_total_bidvex_collected:
    GREEN (aligned)
elif prov == "NS" and actual == amount * 0.15:
    RED (NS defect — see Finding #1)
elif prov in {"US","INTL"} and actual > 0:
    RED (foreign fallback — see Finding #4)
elif prov in {"BC","SK","MB"} and actual > amount * 0.05:
    RED (invoice_service PST/RST inclusion — see Finding #3)
    NOTE — This is only RED IF BidVex is the merchant of record.
    Design keeps this row RED under the confirmed "BidVex does not
    collect provincial PST/RST" policy.
elif calc in {"tax_engine.calculate_tax","tax_engine.calculate_gst_qst"}:
    RED (QC-landmine — see Finding #2)
else:
    AMBER (uncategorised divergence — needs manual review)
```

## 6. Rounding rule

All amounts are `Decimal` quantized to `0.01` using `ROUND_HALF_UP`
(matches CRA rounding practice and current `_round_currency` helpers).
The oracle produces a SINGLE canonical reference — no per-calculator
rounding tolerance.

## 7. Non-goals (explicit)

* Not an assertion of "current implementation is correct." Any cell
  whose reference != actual is a divergence, not an accepted baseline.
* Not a legal opinion. Reference values come from operator-confirmed
  policy + authoritative CRA 2026 sources cited above.
* Not a P6.2 migration script. Consolidation strategy lives in the
  main P6.1.1 reconciliation report.

## 8. Approved deltas for P6.2

Any P6.2 change that alters a calculator's output for a given cell
must be listed here BEFORE the change ships, in the format:

| Calculator | Province | Amount | Before | After | Reason |
|---|---|---|---|---|---|

Initially empty. Populated during P6.2 planning, not during P6.1.1.

## 9. Recommended P6.2 pytest layout

```
backend/tests/iter_p6_2/
  test_golden_matrix.py           — asserts every 600 cells matches reference
  test_ns_rate_transition.py      — NS 15% → 14% after DB update
  test_intl_fallback_zero.py      — US/INTL never > 0 tax
  test_missing_province_fails_closed.py  — no more silent QC default
  fixtures/
    golden_matrix.json            — reference oracle, auto-generated
    approved_deltas.yaml          — human-curated list of intended changes
```

## 10. Coverage guarantees

Golden matrix is REGRESSION-safe (any drift fails CI). It is NOT
policy-safe: if the confirmed legal position changes later (e.g.
BidVex begins collecting BC PST), the reference oracle must be
updated in the same PR that flips the policy, and every affected
cell must have a corresponding row in §8.
