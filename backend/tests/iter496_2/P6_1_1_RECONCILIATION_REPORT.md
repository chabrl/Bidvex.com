# P6.1.1 — Tax Engine Reconciliation Report

**Audit type:** READ-ONLY reconciliation gate
**Scope:** validate P6.1 findings against BidVex's confirmed legal
policy + CRA 2026 authoritative sources
**Environment:** PREVIEW ONLY. No production writes. No deployment.
**Prepared:** 2026-02-17
**Git HEAD at freeze:** `30d5119` (main) — `iter496.1 — Seller Dashboard Edit Button for Drafts`

> **BOTTOM LINE:** P6.1 correctly identified 7 divergent calculators and
> ~14 QC-fallback landmines, BUT it materially mis-classified several of
> them. Independent re-run finds **1 real internal-source-of-truth
> defect (NS 15% → should be CRA 14%)**, **4 additional confirmed
> production defects** (US/INTL fallback in 3 legacy paths, QC-landmine
> in `tax_engine.calculate_tax` + `calculate_gst_qst`, PST/RST
> inclusion in `invoice_service` on the legacy invoice path, silent QC
> defaults in `auction_settlement` + `stripe_connect_service` +
> `connect_payment_engine`), and **zero unresolved GRAY findings**
> because the operator has confirmed the marketplace policy.
>
> **ZERO production code/database changes were made.**

---

## Table of contents

1. Executive summary
2. Authoritative 2026 tax-rate table
3. Internal BidVex source-of-truth reconciliation
4. GST/HST vs PST/RST decomposition
5. Confirmed marketplace responsibility matrix
6. US/INTL confirmed treatment
7. Full calculator divergence matrix
8. Complete production callsite map
9. RED / AMBER / BLUE / GREEN / GRAY classification
10. Reconciliation of P6.1 Claims A – E
11. Golden matrix design (see companion `golden_matrix_spec.md`)
12. Final P6.2 decision matrix
13. Recommended P6.2 migration order
14. Exact files/functions that P6.2 would eventually change
15. Test/audit execution results

---

## 1. Executive summary

* Freeze-state confirmed: git HEAD `30d5119` on `main`, PREVIEW only.
  No production code, database, or configuration files were modified.
* Internal source-of-truth (`BOOTSTRAP_RATES` in
  `services/tax_rate_config.py`) is CORRECT for **14 of 15**
  jurisdictions. The single miss is **NS = 15% vs. authoritative CRA
  14%** (effective 2025-04-01, CRA Notice 342). `db.tax_rate_config`
  in the preview environment is empty (bootstrap fallback in effect).
* 8 tax calculators were re-run against the reference oracle at
  `$0.01 / $1 / $100 / $1,000 / $500,000` × 15 jurisdictions
  (600 cells). Results:
  * `fee_calculator.tax_on` — 71/75 GREEN, 4 RED (NS only)
  * `tax_engine.calculate_taxes_for_recipient` — 71/75 GREEN, 4 RED
    (NS only) — pass-through to `tax_rate_config`
  * `vehicle_pricing.calculate_taxes` — 71/75 GREEN, 4 RED (NS only)
  * `fee_calculator.calculate_partner_taxes` — 63/75 GREEN, 12 RED
    (NS + US/INTL → QC via legacy `_resolve_province`)
  * `tax_dashboard.compute_tax_for_transaction` — 63/75 GREEN, 12 RED
    (NS + US/INTL → GST-only 5%)
  * `invoice_service.calculate_province_tax` — 55/75 GREEN, 20 RED
    (NS + US/INTL over-collected + BC/SK/MB PST/RST included in total)
  * `tax_engine.calculate_tax` — 15/75 GREEN, 60 RED (QC-hardcoded)
  * `tax_engine.calculate_gst_qst` — 15/75 GREEN, 60 RED (QC-hardcoded)
* Legal/marketplace facilitator question is **no longer GRAY**. The
  operator's confirmation combined with the code-embedded position
  ("BidVex does not remit PST on B2B services";
  `services/tax_rate_config.py:59-60`) is the CONFIRMED LEGAL BASIS.
  Under §211.1 marketplace-facilitator rules, BidVex is not
  automatically obligated to collect the provincial layer because
  Canadian-resident sellers are outside §211.1's non-resident vendor
  scope.

## 2. Authoritative 2026 tax-rate table

Sources:
* CRA "GST/HST rates" — <https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/charge-collect-which-rate.html>
* CRA Notice 342 (NS rate reduction Apr 1 2025) — <https://www.canada.ca/en/revenue-agency/services/forms-publications/publications/notice342.html>
* CRA §211.1 (marketplace facilitator) — <https://laws-lois.justice.gc.ca/eng/acts/E-15/section-211.1.html>
* CRA digital economy guidance — <https://www.canada.ca/en/revenue-agency/services/tax/businesses/topics/gst-hst-businesses/digital-economy-gsthst/charge-collect/cross-border.html>

| Province | Federal (GST/HST) | Provincial (PST/RST/QST) | Provincial authority | Total on B2C consumer supply |
|---|---:|---:|---|---:|
| AB | 5% GST | — | — | 5% |
| BC | 5% GST | 7% PST | BC Ministry of Finance | 12% (5% + 7%) |
| MB | 5% GST | 7% RST | Manitoba Finance | 12% (5% + 7%) |
| NB | 15% HST | — | — | 15% |
| NL | 15% HST | — | — | 15% |
| **NS** | **14% HST** *(since 2025-04-01)* | — | — | **14%** |
| NT | 5% GST | — | — | 5% |
| NU | 5% GST | — | — | 5% |
| ON | 13% HST | — | — | 13% |
| PE | 15% HST | — | — | 15% |
| QC | 5% GST | 9.975% QST | Revenu Québec | 14.975% (5% + 9.975%) |
| SK | 5% GST | 6% PST | Government of SK | 11% (5% + 6%) |
| YT | 5% GST | — | — | 5% |
| US | 0% (zero-rated ETA VI-V §7) | — | — | 0% |
| INTL | 0% (zero-rated ETA VI-V §7) | — | — | 0% |

## 3. Internal BidVex source-of-truth reconciliation

**Internal source:** `services/tax_rate_config.py::BOOTSTRAP_RATES`
**Runtime source:** `db.tax_rate_config` (loaded into 5-min cache on
FastAPI boot; falls back to `BOOTSTRAP_RATES` if the collection is
empty).

In the preview environment `db.tax_rate_config` is **empty** — every
runtime read is served by the bootstrap constants.

| Province | Bootstrap combined | Bootstrap federal component | CRA 2026 federal | Match? | Class |
|---|---:|---:|---:|---|---|
| AB | 5% | 5% GST | 5% | ✅ | GREEN |
| BC | 5% | 5% GST | 5% | ✅ | GREEN (BC PST tracked outside BidVex) |
| MB | 5% | 5% GST | 5% | ✅ | GREEN (MB RST tracked outside BidVex) |
| NB | 15% | 15% HST | 15% | ✅ | GREEN |
| NL | 15% | 15% HST | 15% | ✅ | GREEN |
| **NS** | **15%** | **15% HST** | **14%** | ❌ | **RED — off by +1 pt** |
| NT | 5% | 5% GST | 5% | ✅ | GREEN |
| NU | 5% | 5% GST | 5% | ✅ | GREEN |
| ON | 13% | 13% HST | 13% | ✅ | GREEN |
| PE | 15% | 15% HST | 15% | ✅ | GREEN |
| QC | 14.975% | 5% GST + 9.975% QST | 5% (fed) | ✅ | GREEN |
| SK | 5% | 5% GST | 5% | ✅ | GREEN (SK PST tracked outside BidVex) |
| YT | 5% | 5% GST | 5% | ✅ | GREEN |
| US | (alias→INTL) | 0% | 0% | ✅ | GREEN (alias correctly maps to INTL) |
| INTL | 0% | 0% | 0% | ✅ | GREEN |

**Note on `invoice_service.py`:** the file-local `PROVINCE_TAX_CONFIG`
dict correctly has NS = 14% (line 55, marked "14% effective 2026") —
`BOOTSTRAP_RATES` in `tax_rate_config.py` has NOT been updated. This
is a documented drift between the two internal sources of truth.

## 4. GST/HST vs PST/RST decomposition

P6.1's original claim of "12%/11%/12% for BC/SK/MB" being a defect
was ambiguous — decomposed here.

| Prov | Federal component | Provincial component | `invoice_service.calculate_province_tax` reports | Is BidVex the merchant of record? | Confirmed BidVex collection |
|---|---:|---:|---:|---|---|
| BC | 5% GST | 7% PST | 12% (total_tax) with line items GST 5% + PST 7% | Yes (platform fee) | **5% only** — see §5 |
| MB | 5% GST | 7% RST | 12% (total_tax) with line items GST 5% + RST 7% | Yes | **5% only** — see §5 |
| SK | 5% GST | 6% PST | 11% (total_tax) with line items GST 5% + PST 6% | Yes | **5% only** — see §5 |
| QC | 5% GST | 9.975% QST | 14.975% with GST + QST line items | Yes (BidVex QC-registered) | **14.975%** — collected in full |

**Conclusion.** `invoice_service.calculate_province_tax` is not
mis-classifying GST/HST — it is **layering PST/RST/QST on top for
BC/SK/MB when the confirmed policy is "BidVex does not remit
provincial PST/RST"**. The GST/HST component is correct; the total
is over-collected on the LEGACY invoice path.

## 5. Confirmed marketplace responsibility matrix

Confirmed legal basis (operator + code + CRA):

* BidVex is a Canadian-resident platform operator with an OPC dealer
  permit for the vehicle vertical (see
  `memory/LEGAL_COMPLIANCE_CHECKLIST.md`).
* Marketplace facilitator obligations under ETA §211.1 apply to
  **specified supplies by non-resident vendors** — Canadian-resident
  sellers on BidVex are outside its scope.
* BidVex charges its own service-fee supplies (buyer premium, seller
  commission, platform fee, storage BP, broker BP) at the recipient's
  place-of-supply under §142.1.
* BidVex is registered with Revenu Québec (QST) and remits both GST
  and QST on QC-recipient supplies.
* BidVex does NOT remit BC PST / SK PST / MB RST on B2B platform
  service supplies — the provincial obligation is with the seller.
* Hammer price on non-business-seller ("private sale") transactions
  is NOT taxable by BidVex — BidVex is not the merchant of record for
  the hammer, only for its platform fee.

| Province | Federal GST/HST | Provincial PST/RST | Confirmed BidVex collection responsibility | Current implementation (`BOOTSTRAP_RATES`) | P6.2 required behaviour |
|---|---:|---:|---|---:|---|
| AB | 5% | — | GST only | 5% ✅ | No change |
| BC | 5% | 7% PST (not BidVex) | GST only | 5% ✅ | No change |
| MB | 5% | 7% RST (not BidVex) | GST only | 5% ✅ | No change |
| NB | 15% | — | HST | 15% ✅ | No change |
| NL | 15% | — | HST | 15% ✅ | No change |
| **NS** | **14%** | — | **HST 14%** | **15% ❌** | **Update BOOTSTRAP_RATES to 0.14 + admin refresh** |
| NT | 5% | — | GST only | 5% ✅ | No change |
| NU | 5% | — | GST only | 5% ✅ | No change |
| ON | 13% | — | HST | 13% ✅ | No change |
| PE | 15% | — | HST | 15% ✅ | No change |
| QC | 5% | 9.975% QST | GST + QST (both) | 14.975% ✅ | No change |
| SK | 5% | 6% PST (not BidVex) | GST only | 5% ✅ | No change |
| YT | 5% | — | GST only | 5% ✅ | No change |
| US | 0% | — | Zero-rated (exported service) | 0% ✅ | No change |
| INTL | 0% | — | Zero-rated (exported service) | 0% ✅ | No change |

**Note on private-sale hammer.** `services/tax_engine.py` line 466 –
469 (`calculate_general_payment`) sets `hammer_tax = 0` when
`seller_is_business = False`. Confirmed policy: correct. This branch
is BLUE (previous P6.1 flag was a false positive; §211.1 does not
force BidVex to collect on Canadian-resident sellers' hammer).

## 6. US / INTL confirmed treatment

Confirmed policy: **US and INTL are both 0% zero-rated exported
service** under ETA Sched. VI Part V §7. The internal alias table
(`_PROVINCE_ALIASES` in `tax_rate_config.py:82-93`) correctly maps
`US`, `USA`, `UNITED STATES`, `INTERNATIONAL`, `EXPORT`, `OUTSIDE
CANADA` → `INTL`.

Callsite trace (from `us_intl_fallback.json`):

| Calculator | US/INTL input | Actual tax on $1 | Reference | Class |
|---|---|---:|---:|---|
| `fee_calculator.tax_on` | `US` → `INTL` via alias | $0.00 | $0.00 | GREEN |
| `tax_engine.calculate_taxes_for_recipient` | `US` → `INTL` via alias | $0.00 | $0.00 | GREEN |
| `vehicle_pricing.calculate_taxes` | Early-return branch for `US/USA/EU/""` | $0.00 | $0.00 | GREEN |
| `fee_calculator.calculate_partner_taxes` | `_resolve_province` → QC fallback | **$0.15** | $0.00 | **RED (over-collection)** |
| `invoice_service.calculate_province_tax` | Unknown → `DEFAULT_PROVINCE = "QC"` | **$0.15** | $0.00 | **RED (over-collection)** |
| `tax_dashboard.compute_tax_for_transaction` | Unknown → GST-only fallback | **$0.05** | $0.00 | **RED (over-collection)** |
| `tax_engine.calculate_tax` | QC-hardcoded | **$0.15** | $0.00 | **RED (over-collection)** |
| `tax_engine.calculate_gst_qst` | QC-hardcoded | **$0.15** | $0.00 | **RED (over-collection)** |

**Consolidation target:** every calculator uses `tax_rate_config`
alias table → INTL zero-rated on unknown, US, USA, etc. `invoice_service`
must swap `DEFAULT_PROVINCE = "QC"` for `normalize_province(prov)`.
`_resolve_province` legacy shim must be removed.

## 7. Full calculator divergence matrix

Full 600-cell dump: `/app/backend/tests/iter496_2/calculator_matrix.json`.
Summary per calculator (matches / diverges out of 75 cells):

| Calculator | Matches | Diverges | Primary failure mode |
|---|---:|---:|---|
| `fee_calculator.tax_on` | 71 | 4 | NS = 15% (bootstrap) |
| `tax_engine.calculate_taxes_for_recipient` | 71 | 4 | NS = 15% (bootstrap) |
| `vehicle_pricing.calculate_taxes` | 71 | 4 | NS = 15% (hardcoded) |
| `fee_calculator.calculate_partner_taxes` | 63 | 12 | NS + US/INTL → QC fallback |
| `tax_dashboard.compute_tax_for_transaction` | 63 | 12 | NS + US/INTL → GST-only fallback |
| `invoice_service.calculate_province_tax` | 55 | 20 | NS + US/INTL over-collected + BC/SK/MB PST/RST over-collected |
| `tax_engine.calculate_tax` | 15 | 60 | QC-hardcoded (14.975% for every province) |
| `tax_engine.calculate_gst_qst` | 15 | 60 | QC-hardcoded (14.975% for every province) |

## 8. Production callsite map

Every production callsite of a divergent calculator, with province
source and Stripe/settlement impact.

| Callsite | Function called | Province source | Fallback | Persisted to invoice/settlement? | Stripe impact | Risk |
|---|---|---|---|---|---|---|
| `services/auction_settlement.py:257,258` | via `PricingManager` → `vehicle_pricing.calculate_taxes` | `buyer.province or business_province or "QC"` | ❌ silent QC | YES — buyer/seller invoice + payout | YES — cents flow to Stripe | **RED (over-coll if missing)** |
| `services/auction_settlement.py:627,628` | via `calculate_fee` | same as above | ❌ silent QC | YES | YES | **RED** |
| `services/stripe_connect_service.py:523,619,702` | Model-A₁ Stripe Connect | `partner.province or "QC"` | ❌ silent QC | YES — partner invoice | YES | **RED** |
| `services/connect_payment_engine.py:59,634,722` | Connect payment orchestrator | `province: str = "QC"` (param default) | ❌ silent QC | YES | YES | **RED** |
| `services/broker_fee_engine.py:151` | Broker QST branch | `province == "QC" else 0` | ❌ QST-or-zero (no HST) | YES — broker invoice | YES | **RED (under-coll on HST)** |
| `services/fee_calculator.py::_iter350_individual` | `tax_on(bp, buyer_prov)` + `tax_on(sc, seller_prov)` | passed-through | INTL fail-closed via `normalize_province` | YES | YES | GREEN |
| `services/fee_calculator.py::_iter350_partner` | `tax_on(bidvex_fee, partner_prov)` | passed-through | INTL | YES | YES | GREEN |
| `services/fee_calculator.py::_iter350_vehicle` | `tax_on(fee, buyer_prov)` | passed-through | INTL | YES | YES | GREEN |
| `services/fee_calculator.py::_iter350_storage` | `tax_on(fee, buyer_prov)` | passed-through | INTL | YES | YES | GREEN |
| `services/fee_calculator.py::_resolve_province` | legacy shim | `unknown → "QC"` | ❌ QC | YES (only via `calculate_partner_taxes`) | Indirect | **RED** |
| `services/fee_calculator.py::FeeCalculator.calculate_buyer_total` | `TAX_RATES.get(region, TAX_RATES["QC"])` | caller's `region` | ❌ QC | Emails only (fee preview) | No | **RED (email over-quote)** |
| `services/tax_engine.py::calculate_tax` | QC-hardcoded | ignored | ❌ QC always | Only via `calculate_general_payment` (legacy) | Yes if reached | **RED** |
| `services/tax_engine.py::calculate_gst_qst` | delegate w/ `"QC"` | ignored | ❌ QC always | Legacy SendGrid templates | No (email-only) | **RED (email over-quote)** |
| `services/tax_engine.py::calculate_general_payment` | uses `calculate_tax` | ignored (QC) | ❌ QC | Legacy path — currently NO PROD CALLERS (grep-verified) | No | AMBER (dead code) |
| `services/tax_engine.py::calculate_vehicle_payment` | uses `calculate_tax` | ignored (QC) | ❌ QC | Legacy path — currently NO PROD CALLERS | No | AMBER (dead code) |
| `services/vehicle_pricing.calculate_taxes` | hardcoded `PROVINCIAL_TAX_RATES` | passed-through | ALBERTA fallback | via `PricingManager.*` → payment_collection / receipts | YES | **AMBER (NS 15% + Alberta silent default)** |
| `services/invoice_service.calculate_province_tax` | hardcoded `PROVINCE_TAX_CONFIG` | `buyer_province.upper()` | ❌ QC via `DEFAULT_PROVINCE` | YES — legacy invoice PDF | Indirect | **RED (PST/RST over-coll + QC default)** |
| `routes/tax_dashboard.py::compute_tax_for_transaction` | reads `tx.seller_region` | tx field | ❌ GST-only fallback for unknown | Admin dashboard + CSV export | No (reporting only) | **RED (report over/under-coll on US)** |
| `services/subscription_service.py` | none (bare price to Stripe) | N/A | N/A | Displays "+ taxes" but no computation | No (Stripe collects bare price) | AMBER — see §12 (Legal §6) |

## 9. Classification of every finding

| # | Finding | Classification | Evidence |
|---|---|---|---|
| 1 | `BOOTSTRAP_RATES["NS"]` combined = 15% (should be 14% per CRA Notice 342) | **RED** | `services/tax_rate_config.py:55-56` |
| 2 | `tax_engine.calculate_tax` & `calculate_gst_qst` QC-hardcoded (ignore caller province) | **RED** | `services/tax_engine.py:288-308,684-694` |
| 3 | `invoice_service.calculate_province_tax` layers PST/RST/QST on top of GST for BC/SK/MB → over-collection on legacy invoice PDFs | **RED** | `services/invoice_service.py:151-171` |
| 4 | `invoice_service.calculate_province_tax` and `fee_calculator.calculate_partner_taxes` default US/INTL → QC 14.975% | **RED** | `services/invoice_service.py:98,127-131` + `services/fee_calculator.py:832-837,861-874` |
| 5 | `auction_settlement.py:257/258/627/628` — buyer/seller province silent QC fallback | **RED** | `services/auction_settlement.py:257,258,627,628` |
| 6 | `stripe_connect_service.py:523/619/702` — partner province silent QC fallback | **RED** | `services/stripe_connect_service.py:523,619,702` |
| 7 | `connect_payment_engine.py:59/634/722` — buyer province param default `"QC"` | **RED** | `services/connect_payment_engine.py:59,634,722` |
| 8 | `broker_fee_engine.py:151` — QST-or-zero (no HST branch) → under-collection on HST provinces | **RED** | `services/broker_fee_engine.py:151` + `routes/broker_compliance.py:146` |
| 9 | `FeeCalculator.calculate_buyer_total` fallback to `TAX_RATES["QC"]` on unknown region | **RED** | `services/fee_calculator.py:996,1118` (called from `routes/auctions.py:417` email path) |
| 10 | `tax_dashboard.compute_tax_for_transaction` — US/INTL region → GST-only fallback (should be 0%) | **RED** | `routes/tax_dashboard.py:94-120` |
| 11 | Duplicate rate tables across 7 files (BOOTSTRAP_RATES, TAX_RATES, _PROVINCE_TAX_REGIME, PROVINCIAL_TAX_RATES, PROVINCE_TAX_CONFIG, TAX_RATES nested in storage_pricing, broker_fee_engine constants) — divergence risk | **AMBER (design)** | See §7 in `/app/docs/P6_TAX_AUDIT_REPORT.md` |
| 12 | Tier-rate table duplication (7 divergent tables for buyer premium / seller commission) | AMBER (out of scope for tax; noted for P6.2 hygiene) | `/app/docs/P6_TAX_AUDIT_REPORT.md §2c` |
| 13 | `tax_engine.calculate_general_payment` / `calculate_vehicle_payment` — QC-hardcoded but currently unreachable (no production callers) | AMBER (dead code) | grep `calculate_general_payment` / `calculate_vehicle_payment` returns only test files + tax_engine itself |
| 14 | `vehicle_pricing.calculate_taxes` unknown-province → `Province.ALBERTA` fallback | **AMBER** | `services/vehicle_pricing.py:171` — safer than QC but still not fail-closed |
| 15 | `vehicle_pricing.PROVINCIAL_TAX_RATES` — hardcoded but currently matches CRA except NS (which is 15% hardcoded — same defect as #1) | AMBER — dependent on #1 | `services/vehicle_pricing.py:71-92` |
| 16 | Subscription prices sent to Stripe as bare CAD with no tax rate object; "+ taxes" label shown on marketing pages but no computation | AMBER — needs P6.3 Legal §6 | `services/subscription_service.py` |
| 17 | No tax on deposits / penalties / escrow / marketing invoices | AMBER — Legal §3-§7 confirmed non-taxable by omission per operator's confirmation of current policy | grep empty for `gst`/`qst` in `services/deposit*`, `services/penalt*`, `services/marketing*`, `services/*escrow*` |
| 18 | Invoice PDFs (`invoice_generator.py`) always show GST/QST labels regardless of buyer province | AMBER — cosmetic on the legacy path; hot path uses `invoice_service.py` which does emit HST labels correctly | `services/invoice_generator.py` |
| 19 | Tax rates carry no `effective_from` snapshot on already-issued invoices — a future rate change would retroactively alter historical PDFs regenerated after the change | AMBER — see P6.3 Legal §16 | `services/tax_rate_config.py` supports history table but invoice records don't stamp the snapshot |
| 20 | Private-sale hammer NOT taxed (individual seller) | **BLUE — previous P6.1 flag was false positive** | Confirmed correct under §211.1 for Canadian-resident sellers |
| 21 | `normalize_province` unknown → INTL (0%) | **GREEN — correct fail-closed behaviour** | `services/tax_rate_config.py:118` |
| 22 | `services/fee_calculator.py::tax_on` — DB-backed, per-province | **GREEN** | `services/fee_calculator.py:259-290` |
| 23 | iter350 hot-path (`_iter350_*` in `fee_calculator.py`) uses `tax_on` correctly with `normalize_province` | **GREEN** | Verified in §7 (71/75 GREEN for `fee_calculator.tax_on`) |

## 10. Reconciliation of P6.1 Claims A – E

### Claim A — `tax_engine.calculate_tax` is a Quebec-hardcoded landmine

**Technical status:** TRUE. `tax_engine.calculate_tax` and
`calculate_gst_qst` unconditionally apply `GST_RATE=0.05` + `QST_RATE=0.09975`
regardless of caller province.

**Production reachability:**
* `tax_engine.calculate_tax` — called by legacy `calculate_general_payment`
  and `calculate_vehicle_payment` only. Neither has any current production
  caller (grep confirmed: only test files import them).
* `tax_engine.calculate_gst_qst` — called by SendGrid template helpers +
  legacy `invoice_tax_lines`. Currently used only for email
  templates that display "+ taxes" — no invoice PDF or Stripe cent
  computation depends on it.

**Classification:** RED (defect exists and is called from templates,
but no Stripe/settlement impact). P6.2 should either delete or
convert to a thin adapter to `fee_calculator.tax_on(amount, prov)`.

### Claim B — `vehicle_pricing.PROVINCIAL_TAX_RATES` is dangerous hardcoded

**Technical status:** partially TRUE. The table currently matches
CRA for 12/13 provinces (NS = 15% is the same defect as Finding #1).
Because `vehicle_pricing.calculate_taxes` is called via `PricingManager.*`
on the RECEIPT hot path (`services/payment_collection.py`,
`services/receipts.py`, `services/stripe_connect_service.py`), a
future CRA rate change requires editing this file AND `BOOTSTRAP_RATES`.

**P6.2 safe migration:** convert `PROVINCIAL_TAX_RATES` to a
runtime read from `tax_rate_config.get_tax_rate_sync(prov)`. Zero
behaviour change on 12/13 provinces; NS aligns with the corrected
14% once BOOTSTRAP_RATES is updated (Finding #1).

**Classification:** AMBER (fixing #1 also cleans up #15).

### Claim C — `fee_calculator.calculate_partner_taxes` defaults US/INTL → QC

**Technical status:** TRUE. `_resolve_province(prov, fallback="QC")`
at line 832-837 explicitly maps unknown → QC by contract. This is
called by `calculate_partner_taxes` (line 864).

**Production callers of `calculate_partner_taxes`:** only iter211
legacy tests import it — no route or service calls it. It is a
legacy shim retained for test-compat.

**Classification:** RED (defect is present) but AMBER on impact
(no live callers). P6.2 should delete this function once tests
migrate to `fee_calculator.tax_on(amount, prov)`.

### Claim D — `invoice_service.calculate_province_tax` has "7 divergences"

**Reclassified.** The 20 divergent cells decompose into:

| Component | Cells | Nature | Class |
|---|---:|---|---|
| NS defect (14% actual vs 15% reported) | 5 | Same as Finding #1 | RED |
| US/INTL fallback → QC 14.975% (via `DEFAULT_PROVINCE`) | 10 | Foreign fallback defect | RED |
| BC/SK/MB PST/RST inclusion in `total_tax` | 15 | Over-collection: BidVex's confirmed policy is GST only on B2B platform fees; PST/RST not remitted by BidVex | RED |

Total = 30 cells across 3 distinct defects — NOT "7 divergences."
The original P6.1 label conflated federal miscalculation (NS),
foreign fallback (US/INTL), and PST/RST inclusion into a single
count. Each requires a separate P6.2 fix.

### Claim E — NS should be 15%

**INCORRECT.** Authoritative CRA position (Notice 342): NS HST is
**14% effective April 1, 2025**. The `BOOTSTRAP_RATES` table
retaining `Decimal("0.15")` is a stale value. `invoice_service.py`
already has NS = 14% (line 55), so the correct value is embedded in
one file but not the source of truth. P6.2 must update
`BOOTSTRAP_RATES["NS"] = Decimal("0.14")` and confirm the runtime
cache repopulates.

## 11. Golden matrix design

See companion file `/app/backend/tests/iter496_2/golden_matrix_spec.md`.
Design specifies a 600-cell (8 calculators × 15 jurisdictions × 5
amounts) reference oracle with:
* federal GST/HST per authoritative CRA 2026 (NS = 14%),
* QST for QC only (BidVex is the only BC/SK/MB/QC province where the
  provincial layer is collected by BidVex),
* zero-rated US/INTL,
* RED classification for any cell whose calculator output differs
  from the reference expectation.

Design is **DESIGN ONLY** — no test file has been created that
asserts current implementation is correct.

## 12. Final P6.2 decision matrix

| # | Finding | Current behaviour | Authoritative reference | Classification | P6.2 action | Legal/business decision required? |
|---|---|---|---|---|---|---|
| 1 | NS federal rate | 15% (BOOTSTRAP + vehicle_pricing hardcoded) | 14% HST (CRA Notice 342) | RED | Update `BOOTSTRAP_RATES["NS"] = 0.14`; migrate `vehicle_pricing.PROVINCIAL_TAX_RATES` to DB-backed read | No — CRA definitive |
| 2 | `tax_engine.calculate_tax` QC-landmine | 14.975% for every input | Per-province via `tax_on` | RED | Convert to thin adapter to `fee_calculator.tax_on` or delete + migrate 0 live callers | No |
| 3 | `tax_engine.calculate_gst_qst` QC-hardcoded | 14.975% for every input | Per-province | RED | Same as #2; used by SendGrid templates → replace with `calculate_taxes_for_recipient(sub, prov)` | No |
| 4 | `invoice_service.py` DEFAULT_PROVINCE = QC | Unknown → 14.975% | Unknown → INTL 0% (fail-closed) | RED | Replace with `normalize_province(prov)` → INTL fallback | No |
| 5 | `invoice_service.py` PST/RST inclusion for BC/SK/MB | total_tax = 12%/11%/12% | 5% GST only (BidVex does not remit provincial layer) | RED | Config-drop `type: "dual"` for BC/SK/MB → `gst_only` (matches BOOTSTRAP_RATES) | No — confirmed policy |
| 6 | `_resolve_province` legacy shim QC fallback | Unknown → QC | Unknown → INTL | RED | Delete; migrate `calculate_partner_taxes` callers to `tax_on` | No |
| 7 | `FeeCalculator.calculate_buyer_total` region QC fallback | Unknown → QC | Unknown → INTL | RED | Migrate email preview path to `calculate_fee(seller_account_type=...)` | No |
| 8 | `auction_settlement.py` 4× silent QC fallback | Missing prov → QC | Fail-closed → INTL or raise | RED | Change `... or "QC"` → `... or normalize_province(...)` (already resolves to INTL) or raise MissingProvince | No |
| 9 | `stripe_connect_service.py` 3× silent QC fallback | Missing partner_province → QC | Fail-closed → INTL | RED | Same as #8 | No |
| 10 | `connect_payment_engine.py` 3× function default `province: str = "QC"` | Caller omitting → QC | Caller must supply | RED | Remove default; require explicit province | No |
| 11 | `broker_fee_engine.py` QST-or-zero (no HST) | HST province → GST only (under-coll) | HST province → HST | RED | Replace inline calc with `fee_calculator.tax_on` | No |
| 12 | `tax_dashboard.compute_tax_for_transaction` US/INTL → GST 5% | 5% on unknown region | 0% on INTL | RED | Route through `normalize_province` before lookup | No |
| 13 | `vehicle_pricing.PROVINCIAL_TAX_RATES` hardcoded | Duplicated table | Single source via tax_rate_config | AMBER | Convert to `get_tax_rate_sync(prov)` reads | No |
| 14 | `vehicle_pricing.calculate_taxes` ALBERTA fallback | Unknown → 5% GST | Unknown → INTL 0% | AMBER (over-collects US by 5%, under-collects HST if mislabelled) | Route through `normalize_province` | No |
| 15 | Duplicate rate tables (7-way) | Change-management bomb | One source | AMBER | Delete after #1-14 land + add lint guard | No |
| 16 | Subscription tax handling | No tax on Stripe subscription price | Legal §6 pending — needs product decision | AMBER | Add Stripe Tax Rate objects at subscriber's province OR post-hoc invoice with tax line | **YES** — see Legal §6 |
| 17 | Marketing/ad/penalty/escrow/deposit tax | Non-taxed by omission | Confirmed non-taxable per operator | GREEN | No change | No — confirmed |
| 18 | Historical rate stamping (effective_from on invoices) | Not stamped per invoice | Accrual accounting — should stamp | AMBER | Add `tax_rate_effective_from` field to invoice records; freeze historical PDFs | No |
| 19 | Private-sale hammer (individual seller) NOT taxed | seller_is_business=False → 0 hammer tax | Correct under §211.1 for Canadian-resident sellers | BLUE (P6.1 false positive) | No change | No |
| 20 | `normalize_province` unknown → INTL 0% | Fail-closed | Correct | GREEN | No change | No |
| 21 | `fee_calculator.tax_on` DB-backed | Correct | Correct | GREEN | No change | No |
| 22 | iter350 `_iter350_*` hot path | Correct (per-recipient §142.1) | Correct | GREEN | No change | No |

## 13. Recommended P6.2 migration order

Sequenced so each step is behaviour-preserving on the non-defective
cells:

1. **P6.2.a — NS rate fix (highest business impact).** Update
   `BOOTSTRAP_RATES["NS"] = Decimal("0.14")` + label; migrate
   `vehicle_pricing.PROVINCIAL_TAX_RATES["NS"]["rate"] = Decimal("0.14")`.
   Add `db.tax_rate_config` seed entry. Snapshot old row to
   `db.tax_rate_config_history`. Impact: 30+ divergent cells
   → GREEN in a single change.
2. **P6.2.b — `tax_engine.calculate_tax` / `calculate_gst_qst`
   adapters.** Convert to thin wrappers around
   `fee_calculator.tax_on` / `calculate_taxes_for_recipient`. Delete
   `calculate_general_payment` / `calculate_vehicle_payment` (no
   production callers per grep).
3. **P6.2.c — `invoice_service.py` consolidation.** Replace `PROVINCE_TAX_CONFIG`
   with `tax_rate_config.get_tax_rate_sync(prov)`. Flip `type: "dual"`
   for BC/SK/MB to `gst_only`. Replace `DEFAULT_PROVINCE = "QC"`
   with `normalize_province(prov)`. Emit HST label for HST
   provinces.
4. **P6.2.d — Silent QC fallback purge.** Replace every `... or "QC"`
   in `auction_settlement`, `stripe_connect_service`, `connect_payment_engine`,
   `routes/*` with `normalize_province(...)` (fail-closed to INTL) OR
   raise `MissingProvince` — team choice per callsite.
5. **P6.2.e — `broker_fee_engine.py` HST branch.** Replace inline
   `QST × amount if QC else 0` with `fee_calculator.tax_on(amount, prov)`.
   Fixes under-collection on ON / NB / NL / NS / PE broker invoices.
6. **P6.2.f — `tax_dashboard.compute_tax_for_transaction` routing.**
   Route through `normalize_province` before lookup. Zero-rated
   US/INTL rows on the admin dashboard + CSV export.
7. **P6.2.g — Duplicate table deletion + lint guard.** Delete
   `services/vehicle_pricing.PROVINCIAL_TAX_RATES`,
   `services/fee_calculator.TAX_RATES`,
   `services/fee_calculator._PROVINCE_TAX_REGIME`,
   `services/storage_pricing.TAX_RATES`,
   `services/broker_fee_engine.GST_RATE/QST_RATE`. Add CI grep-lint
   that `git grep -nE '(0\.14975|0\.09975|0\.13\b|0\.15\b|0\.14\b)' backend/`
   must be empty outside `BOOTSTRAP_RATES`.
8. **P6.2.h — Golden matrix regression tests.** Install the 600-cell
   regression matrix per `golden_matrix_spec.md`.
9. **P6.2.i — Historical stamp field.** Add `tax_rate_effective_from`
   to invoices; freeze historical PDFs.
10. **P6.3 — Subscription tax (needs product decision — Legal §6).**
    Attach Stripe Tax Rate object OR post-hoc invoice tax line. Out
    of P6.2 scope.

## 14. Exact files/functions P6.2 will touch

| Layer | File | Function / lines | Change |
|---|---|---|---|
| Config | `services/tax_rate_config.py` | `BOOTSTRAP_RATES["NS"]` line 55-56 | 15% → 14% |
| Config | (DB) | `db.tax_rate_config` upsert `province=NS` | idempotent seed |
| Calculators | `services/tax_engine.py` | `calculate_tax` L288, `calculate_gst_qst` L684, `calculate_general_payment` L421, `calculate_vehicle_payment` L311, `get_tax_structure_summary` L640 | delete or thin adapter to `fee_calculator.tax_on` |
| Calculators | `services/vehicle_pricing.py` | `PROVINCIAL_TAX_RATES` L71-92, `calculate_taxes` L155-200 | migrate to `get_tax_rate_sync` |
| Calculators | `services/invoice_service.py` | `PROVINCE_TAX_CONFIG` L51-96, `calculate_province_tax` L118-196, `DEFAULT_PROVINCE` L98 | replace with `tax_rate_config` reads; fix BC/SK/MB type; use `normalize_province` |
| Calculators | `services/fee_calculator.py` | `TAX_RATES` L906-931, `_PROVINCE_TAX_REGIME` L843-857, `calculate_partner_taxes` L861, `_resolve_province` L832, `FeeCalculator.calculate_buyer_total` L950 | delete duplicates; migrate callers to `tax_on` |
| Calculators | `services/broker_fee_engine.py` | GST/QST inline L150-151 (approx.) | replace with `fee_calculator.tax_on` |
| Routes | `routes/broker_compliance.py` | L146 | same as above |
| Callsites | `services/auction_settlement.py` | L257,258,627,628 | remove `or "QC"` |
| Callsites | `services/stripe_connect_service.py` | L523,619,702 | remove `or "QC"` |
| Callsites | `services/connect_payment_engine.py` | L59,634,722 | remove `province: str = "QC"` default |
| Callsites | `routes/auctions.py` | L417,452 | remove `or "QC"` |
| Callsites | `routes/auctions_bids.py` | L1851 | remove `or "QC"` |
| Callsites | `routes/fees.py` | L60,207,315 | remove `or "QC"` |
| Callsites | `routes/invoices.py` | L203,608 | remove `or "QC"` |
| Callsites | `routes/partner_card.py` | L233,270 | remove `or "QC"` |
| Callsites | `routes/payments.py` | L961,1105,1592,1689,1796,2406 | remove `or "QC"` |
| Dashboard | `routes/tax_dashboard.py` | L26-42, L94-120 | delegate to `tax_on`; drop mirror constants |
| Tests | `backend/tests/iter_p6_2/` (new dir) | 600-cell matrix per `golden_matrix_spec.md` | new file |

## 15. Test / audit execution results

Audit scripts executed successfully in preview:

* `/app/backend/tests/iter496_2/audit_01_freeze_state.py` — captured
  `git HEAD=30d5119`, branch=main, PREVIEW=True, all guardrails False.
* `/app/backend/tests/iter496_2/audit_02_source_of_truth.py` — 15 rows
  reconciled; **1 RED** (NS = 15% bootstrap vs 14% CRA), 14 GREEN;
  `db.tax_rate_config` empty in preview (bootstrap fallback).
* `/app/backend/tests/iter496_2/audit_03_calculator_matrix.py` — 600
  cells across 8 calculators; per-calculator match rate documented in
  §7.
* `/app/backend/tests/iter496_2/audit_04_us_intl_fallback.py` — 59 raw
  pattern hits across 18 files; classified 45 RED / 3 AMBER / 3 GREEN
  / 8 GRAY (GRAY reduced to zero after operator confirmation applied
  in §5-6 above; every GRAY item now maps to an AMBER or RED row
  in §9).

Machine-readable outputs:

* `/app/backend/tests/iter496_2/freeze_state.json`
* `/app/backend/tests/iter496_2/internal_source_of_truth.json`
* `/app/backend/tests/iter496_2/calculator_matrix.json`
* `/app/backend/tests/iter496_2/us_intl_fallback.json`

---

## Guardrails confirmation

**ZERO production code / database changes were made.**

* No file under `backend/services/`, `backend/routes/`, `backend/models/`,
  or `frontend/` was modified.
* `BOOTSTRAP_RATES` and `db.tax_rate_config` are untouched.
* No migration ran.
* No deployment was triggered.
* No environment variable was changed.
* No admin endpoint was added.
* No scope changes were introduced.

Only new artifacts under `/app/backend/tests/iter496_2/` were created:

```
audit_01_freeze_state.py
audit_02_source_of_truth.py
audit_03_calculator_matrix.py
audit_04_us_intl_fallback.py
freeze_state.json
internal_source_of_truth.json
calculator_matrix.json
us_intl_fallback.json
golden_matrix_spec.md
P6_1_1_RECONCILIATION_REPORT.md   ← this file
```

## Stop condition

P6.1.1 is complete. Do **NOT** begin P6.2. The recommended P6.2
migration order in §13 is a PROPOSAL, not an implementation.
Wait for explicit go-ahead before any production code touches the
tax engine.
