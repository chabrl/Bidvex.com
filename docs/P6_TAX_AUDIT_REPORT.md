# P6 — Tax Engine Consolidation Audit Report
**Status:** AUDIT ONLY — no code changes, no deploy.
**Scope:** all Canadian tax logic (GST, QST, HST) across the BidVex codebase.
**Baseline:** 88 backend tests passing (iter483 + iter484). Preserved throughout audit.
**Prepared for:** future consolidation into a single authoritative `tax_engine.py`.

---

## Executive Summary
Tax logic is scattered across **at least 9 different files** with **7 duplicate rate
tables** and **~14 silent-default fallbacks to Quebec (14.975%)**. There is a
canonical DB-backed source of truth (`services/tax_rate_config.py` +
`services/fee_calculator.py::calculate_fee()`) which is correctly used on the hot
auction settlement path, BUT the legacy calculators, admin dashboards, invoice
generators and vehicle path continue to use hardcoded rate tables and QC
fallbacks. Six locations FAIL OPEN by defaulting an unknown province to
QC 14.975% (over-collection risk).

**Top risks (highest → lowest):**

1. **P0 — Over-collection risk** in `fee_calculator._resolve_province` and
   `FeeCalculator.calculate_buyer_total` — unknown province silently becomes
   QC (14.975%). Buyer/seller in AB (5%) or ON (13%) could be over-taxed if
   the calling path uses the legacy shim.
2. **P0 — Under-collection risk** in `broker_fee_engine.py` — QST is
   hardcoded to 0 for any non-QC province. Buyer in a non-QC HST province is
   under-taxed (should collect HST).
3. **P0 — Duplicate rate tables (7 copies)** create a change-management
   bomb: when CRA changes a rate, at least 7 files must be edited in
   lockstep or the totals will silently drift.
4. **P1 — No tax handling** for deposits, penalties, subscriptions,
   marketing invoices, or escrow releases. Legal review required to
   confirm each is either non-taxable or that the omission is a defect.
5. **P1 — Invoice PDFs** hardcode GST/QST labels even when the recipient
   is outside QC (see `invoice_generator.py`).

---

## 1. Tax Calculation Inventory

Each entry is: **file** · **function** · **lines** · **formula** · **rate** ·
**conditions**.

### Canonical (DB-backed, iter350) — the future single source of truth
| File | Function | Lines | Formula | Rate | Conditions |
|---|---|---|---|---|---|
| `services/tax_rate_config.py` | `BOOTSTRAP_RATES` | 44–78 | dict lookup | QC 14.975%, ON 13%, NB/NL/NS/PE 15%, AB/BC/MB/SK/YT/NT/NU 5%, INTL 0% | Per-province table; DB row wins if present. |
| `services/tax_rate_config.py` | `normalize_province` | 102–119 | alias map | — | Unknown → INTL (0%) fail-closed. **CORRECT.** |
| `services/tax_rate_config.py` | `get_tax_rate_sync` | 122–134 | cache read | — | Bootstrap fallback if cache empty. |
| `services/fee_calculator.py` | `tax_on` | 259–290 | `amt × row["combined"]` (per-line `gst`/`qst`/`hst`) | Per-province from DB | Delegates to `tax_rate_config`. **CORRECT.** |
| `services/fee_calculator.py` | `calculate_fee` | 383–436 | dispatcher | Per-recipient province | CRA Place-of-Supply routing. **CORRECT.** |
| `services/fee_calculator.py` | `_iter350_individual` | 440–530 | `tax_on(bp, buyer_prov)` + `tax_on(sc, seller_prov)` | Per-recipient | **CORRECT.** |
| `services/fee_calculator.py` | `_iter350_partner` | 533–618 | `tax_on(bidvex_fee+recovery, partner_prov)` | Partner province | **CORRECT.** |
| `services/fee_calculator.py` | `_iter350_vehicle` | 621–678 | `tax_on(fee+recovery, buyer_prov)` | Buyer province | **CORRECT.** |
| `services/fee_calculator.py` | `_iter350_storage` | 681–760 | `tax_on(bp+recovery, buyer_prov)` | Buyer province (iter443) | **CORRECT.** |
| `services/fee_calculator.py` | `calculate_broker_transaction` | 766–824 | `tax_on(fees+recovery, buyer_prov)` | Buyer province | **CORRECT.** |
| `services/tax_engine.py` | `calculate_taxes_for_recipient` | 697–757 | delegates to `tax_rate_config` | Per-province | **CORRECT.** |

### Legacy / duplicate calculators (STILL WIRED — must be consolidated)
| File | Function | Lines | Formula | Rate | Conditions |
|---|---|---|---|---|---|
| `services/tax_engine.py` | `GST_RATE`/`QST_RATE`/`COMBINED_TAX_RATE` | 37–39 | constants | 5%, 9.975%, 14.975% | QC-only. Imported by `vehicle_pricing.py`, `connect_payment_engine.py`. |
| `services/tax_engine.py` | `calculate_tax` | 288–308 | `amt × 0.05` + `amt × 0.09975` | 14.975% (QC-only) | **DUPLICATE** of `fee_calculator.tax_on(...,"QC")`. Ignores province. |
| `services/tax_engine.py` | `calculate_general_payment` | 421–637 | full two-pass calc | 14.975% (QC-only) | **DUPLICATE** of `_iter350_individual`. Only used by legacy paths. |
| `services/tax_engine.py` | `calculate_vehicle_payment` | 311–418 | full calc | 14.975% (QC-only) | **DUPLICATE** of `_iter350_vehicle`. Legacy. |
| `services/tax_engine.py` | `calculate_gst_qst` | 684–694 | delegate w/ `"QC"` hardcode | QC 14.975% | **SILENT DEFAULT to QC.** Called by templates. |
| `services/tax_engine.py` | `invoice_tax_lines` | 767–792 | delegate | Passes `currency`, ignores province | Only emits GST/QST rows (never HST). Falsely reports 0 for non-CAD. |
| `services/tax_engine.py` | `get_tax_rates_for_currency` | 760–764 | `if currency == "CAD": GST+QST else 0` | 5% + 9.975% | **Broken for non-QC CAD provinces.** |
| `services/fee_calculator.py` | `TAX_RATES` dict | 907–931 | static dict | 13 provinces | **DUPLICATE** of `BOOTSTRAP_RATES` — divergent (`US` mapped instead of `INTL`). |
| `services/fee_calculator.py` | `_PROVINCE_TAX_REGIME` (+ alias `PROVINCE_TAX_REGIME`) | 843–858 | static dict | 13 provinces | **DUPLICATE** #2. iter211 legacy snapshot. |
| `services/fee_calculator.py` | `calculate_partner_taxes` | 861–874 | `amount × regime["combined"]` | Per-province from `_PROVINCE_TAX_REGIME` | Legacy shim; unknown → QC via `_resolve_province`. |
| `services/fee_calculator.py` | `QC_GST_RATE` / `QC_QST_RATE` | 99–100 | constants | 5% / 9.975% | Unused by iter350; module-level dead weight. |
| `services/fee_calculator.py` | `FeeCalculator.calculate_buyer_total` | 950–1138 | pre-tax + tax logic branching on `TAX_RATES.get(region, TAX_RATES["QC"])` | Per-province | **STILL called from `routes/auctions.py:417`** (email-side platform-fee estimate). Fails open to QC. |
| `services/fee_calculator.py` | `PricingManager.non_vehicle_stripe` | 1393–1464 | uses `vehicle_pricing.calculate_taxes` | Per-province | Called by `payment_collection.py`, `receipts.py`, `stripe_connect_service.py`. |
| `services/fee_calculator.py` | `PricingManager.non_vehicle_cash` | 1467–~1560 | uses `vehicle_pricing.calculate_taxes` | Per-province | Same as above. |
| `services/fee_calculator.py` | `PricingManager.vehicle_auction` | 1351–1391 | uses `vehicle_pricing.calculate_taxes` | Per-province | Same. |
| `services/vehicle_pricing.py` | `TAX_RATES_BY_PROVINCE` | 73–92 | dict | 13 provinces | **DUPLICATE #3** of BOOTSTRAP_RATES. Imports `GST_RATE` from `tax_engine.py`. |
| `services/vehicle_pricing.py` | `calculate_taxes` | (bottom) | province lookup | Per-province | **DUPLICATE** calculator used by every `PricingManager.*` call. |
| `services/storage_pricing.py` | `TAX_RATES` (nested tuple) | 46–59 | dict | 13 provinces | **DUPLICATE #4** — includes bogus alias `PEI` ↔ `PE`. |
| `services/storage_pricing.py` | tax calc branch | ~ | `amt × combined` | Per-province | Independent path — does NOT go through `tax_rate_config`. |
| `services/broker_fee_engine.py` | `GST_RATE` / `QST_RATE` constants | 37–38 | constants | 5% / 9.975% | Hardcoded QC. |
| `services/broker_fee_engine.py` | tax calc | 150–151 | `subtotal × 0.05` + `× 0.09975 if QC else 0` | QC-only | **CRITICAL: under-collects HST provinces.** |
| `services/connect_payment_engine.py` | tax calc | 104–105 | `amt × 0.05` + `amt × 0.09975` | 14.975% hardcoded | Ignores province. |
| `services/connect_payment_engine.py` | fn signature default | 59, 634, 722 | `province: str = "QC"` | — | **Silent default.** |
| `services/subscription_service.py` | (implicit) | 57–60 | `+ taxes` labels | None | Displays "+ taxes" but no computed tax in this file. |
| `routes/broker_compliance.py` | line 146 | 146 | `commission × 0.09975 if buyer_prov=="QC" else 0` | QC-only QST | Same as broker_fee_engine — under-collects HST. |
| `routes/auctions.py` | line 941 (multi-item lot BP notice) | 941 | `bidAmount × 0.025` inline | 2.5% | Not a tax but a hardcoded platform-fee percent leaking into UX. |
| `services/auction_settlement.py` | `settle_cash_or_etransfer` / `settle_stripe_full` | 257–258, 627–628 | `buyer_prov = user.province or user.business_province or "QC"` | — | **SILENT DEFAULT to QC.** Two locations. |
| `services/stripe_connect_service.py` | line 523 | 523, 619, 702 | `partner_province: str = "QC"` | — | **SILENT DEFAULT to QC.** Three locations. |
| `routes/invoices.py` | lines 203, 608 | — | `... or "QC"` | — | **SILENT DEFAULT to QC.** Two locations. |
| `routes/payments.py` | lines 936, 1080 | — | `... or "QC"` | — | **SILENT DEFAULT to QC.** |
| `routes/fees.py` | line 60 | 60 | `... or "QC"` | — | **SILENT DEFAULT to QC.** |
| `routes/partner_card.py` | lines 233, 270 | — | `... or "QC"` | — | **SILENT DEFAULT to QC.** |
| `routes/auctions_bids.py` | line 1851 | 1851 | `... or "QC"` | — | **SILENT DEFAULT to QC.** |
| `services/invoice_generator.py` | (whole file) | 353–617 | hardcoded `GST/TPS #` labels | QC-only | Invoices always show GST + QST labels regardless of buyer province. |
| `services/invoice_service.py` | line 160 | 160 | `if province == "QC": use 9.975% else 0%` | Per-province | Only QC branch shows QST. Non-QC never shows PST. |

### Non-auction paths NOT wired to any tax engine
| Area | Files | Behaviour |
|---|---|---|
| **Subscriptions** | `services/subscription_service.py` | Publishes prices as `"$180 CAD/year + taxes"` but no computed tax value ever attached to the Stripe subscription. |
| **Marketing invoices** | `services/email_marketing.py` (empty grep for gst/qst/hst) | No tax computed. Legal review required — see §5. |
| **Bidding deposits** | `services/deposit_auto_capture.py`, `services/deposit_refund_queue.py` | No tax field. Deposits treated as security; refunded 1:1. Confirm legal treatment. |
| **Storage deposits** | (same collections) | Same. |
| **Vehicle deposits** | `services/broker_deposit_service.py` | No tax. Same. |
| **Penalties** | (grep empty) | No tax. Legal review required. |
| **Escrow** | (grep empty for tax) | No tax. Escrow releases go through settlement pipeline which does compute tax — but the release itself is not a taxable event. Confirm. |
| **Contractor commissions** | `services/contractor_commission.py` | No tax computed. |
| **Affiliate commissions** | `routes/affiliate.py` | No tax computed. |
| **Ad campaigns** | `routes/ad_campaigns.py` | Legacy percentage math — no per-province tax. |

---

## 2. Duplicate Formula Inventory

### 2a — GST/QST/HST rate constants duplicated
The **7-way duplication** of Canadian tax rates:
1. `services/tax_rate_config.py::BOOTSTRAP_RATES` (canonical, DB-backed)
2. `services/tax_engine.py` constants `GST_RATE` / `QST_RATE` / `COMBINED_TAX_RATE` (QC-only)
3. `services/fee_calculator.py::TAX_RATES` (13 provinces + US)
4. `services/fee_calculator.py::_PROVINCE_TAX_REGIME` (13 provinces, iter211 snapshot)
5. `services/fee_calculator.py::QC_GST_RATE` / `QC_QST_RATE` module constants
6. `services/vehicle_pricing.py::TAX_RATES_BY_PROVINCE` (13 provinces)
7. `services/storage_pricing.py::TAX_RATES` (13 provinces)
8. `services/broker_fee_engine.py::GST_RATE` / `QST_RATE` (QC-only, no HST branch)

Any CRA rate change (e.g. Manitoba adds a provincial layer, PEI moves off HST)
requires ALL 8 to be edited in lockstep. Miss one → cent drift across
invoices, statements, PDFs, and admin dashboards.

### 2b — Two-pass Stripe gross-up implemented in TWO places
- `services/tax_engine.py::calculate_general_payment` lines 483–494 (`_stripe_gross_up` legacy import path)
- `services/fee_calculator.py::PricingManager.non_vehicle_stripe` lines 1410–1416 (identical two-pass math)
Both perform: `sr = gross_up(hp+bp) → tax on (bp+sr) → sr = gross_up(hp+bp+tax) → tax on (bp+sr)`. Identical algorithm; different call sites.

### 2c — Buyer premium / seller commission tier tables duplicated
- `services/tax_engine.py::BUYER_PREMIUM_RATES` / `SELLER_COMMISSION_RATES` (5 tiers)
- `services/fee_calculator.py::INDIVIDUAL_BUYER_RATES` / `INDIVIDUAL_SELLER_RATES` (3 tiers)
- `services/fee_calculator.py::BUYER_PREMIUM_RATES` / `SELLER_COMMISSION_RATES` (7 tiers, PricingManager)
- `services/fee_calculator.py::SUBSCRIPTION_FEES` (4 tiers)
- `services/fee_calculation_engine.py::BUYER_PREMIUM_RATES` / `SELLER_COMMISSION_RATES` (5 tiers)
- `services/vehicle_pricing.py::BUYER_PREMIUM_RATES` (3 tiers)
- `services/subscription_service.py::BUYER_PREMIUM_RATES` (2 tiers, line 65)
**7 divergent tier tables** — some carry premium 3.0% for vip, others 3.5%.
Selecting the wrong one caps buyer premium incorrectly.

### 2d — Stripe processing fee constants duplicated
- `services/fee_calculator.py::STRIPE_PROCESSING_RATE` / `STRIPE_FIXED_FEE` (2.9% + $0.30, canonical)
- `services/fee_calculator.py::STRIPE_PCT` / `STRIPE_FIXED` (PricingManager, same values)
- `services/fee_calculator.py::STRIPE_DOMESTIC_PCT` / `_INTERNATIONAL_PCT` / `_CONVERSION_PCT`
- `services/fee_calculator.py::STRIPE_RATES` dict (identical)
- `services/tax_engine.py::_stripe_gross_up` reads from `STRIPE_RATES`
- `services/broker_fee_engine.py` — hardcoded 2.9% inline

### 2e — Full calculator duplicates
- `services/tax_engine.py::calculate_general_payment` ≈ `services/fee_calculator.py::_iter350_individual` — both do buyer + seller two-pass, but tax_engine hardcodes QC.
- `services/fee_calculation_engine.py::calculate_fees` — separate "hybrid" engine that omits tax entirely. Only exists for one caller path (`routes/fees.py` fee preview). **The whole module is a duplicate.**

---

## 3. Silent Default Audit
Every location where a missing province, tax status, or business flag falls
back to a hardcoded value instead of erroring.

### 3a — Silent default province → "QC" (over-collection risk)
| Location | Line | Behaviour |
|---|---|---|
| `services/auction_settlement.py::settle_cash_or_etransfer` | 257 | `buyer_prov = user.province or business_province or "QC"` |
| `services/auction_settlement.py::settle_cash_or_etransfer` | 258 | `seller_prov = user.province or business_province or "QC"` |
| `services/auction_settlement.py::settle_stripe_full` | 627 | Same as 257. |
| `services/auction_settlement.py::settle_stripe_full` | 628 | Same as 258. |
| `services/stripe_connect_service.py` | 523 | fn default `partner_province: str = "QC"` |
| `services/stripe_connect_service.py` | 619 | `partner_prov = (partner_province or "QC").strip().upper()` |
| `services/stripe_connect_service.py` | 702 | `jurisdiction=(partner_prov or "QC")` |
| `services/connect_payment_engine.py` | 59 | fn default `province: str = "QC"` |
| `services/connect_payment_engine.py` | 634, 722 | fn default `buyer_province: str = "QC"` |
| `services/fee_calculator.py::_resolve_province` | 832–837 | `unknown → "QC"` (legacy shim) |
| `services/fee_calculator.py::FeeCalculator.calculate_buyer_total` | 996, 1118 | `TAX_RATES.get(region, TAX_RATES["QC"])` |
| `services/tax_engine.py::calculate_gst_qst` | 693–694 | Hardcodes `"QC"` regardless of input. |
| `routes/auctions.py` | 417, 452 | `buyer_province or "QC"` (email-side platform fee) |
| `routes/auctions_bids.py` | 1851 | `... or "QC"` |
| `routes/broker_compliance.py` | 146 | `... == "QC"` branch, else QST=0 |
| `routes/fees.py` | 60 | `... or "QC"` |
| `routes/invoices.py` | 203, 608 | `... or "QC"` |
| `routes/partner_card.py` | 233, 270 | `... or "QC"` |
| `routes/payments.py` | 936, 1080 | `... or "QC"` |
| `services/invoice_service.py` | 160 | `if province == "QC": use 9.975 else 0` (never emits HST) |

### 3b — Silent registration-status default
| Location | Line | Behaviour |
|---|---|---|
| `services/fee_calculator.py::FeeCalculator.calculate_buyer_total` | 955 | `seller_is_business: bool = False` (default = private / no hammer tax) |
| `services/auction_settlement.py` | 334 | `"seller_is_tax_registered": False` (hardcoded, ignores DB field) |
| `services/invoice_generator.py` | 750 | `is_business = seller.get("is_tax_registered", False)` — silent False if key missing |
| `services/invoice_generator.py` | 752 | `gst_number = tax_id if is_tax_registered else None` — silent hide if unset |

### 3c — Silent partner / vehicle_dealer / storage detection
| Location | Line | Behaviour |
|---|---|---|
| `services/seller_type_resolver.py` | (whole file) | Raises `SellerTypeUnresolved` when ambiguous. **CORRECT** — fails closed on the hot settle path. |
| Legacy shim in `fee_calculator._resolve_province` | 832 | Falls back to `"QC"` on unknown → over-taxes. |

---

## 4. Fail-Closed Compliance Audit

### 4a — Correctly fails closed
| Location | Behaviour |
|---|---|
| `services/tax_rate_config.py::normalize_province` line 118 | Unknown → `INTL` (0%) with warning log. **CORRECT.** |
| `services/tax_rate_config.py::get_tax_rate_sync` line 122 | Missing cache entry → BOOTSTRAP fallback, never None. |
| `services/seller_type_resolver.py` | Raises `SellerTypeUnresolved` on ambiguous seller → settle_auction returns `{"settled": False, "reason": "seller_type_unresolved"}`. |
| `services/fee_calculator.py::calculate_fee` line 407 | Raises `ValueError` on `hammer_price < 0`. |
| `services/fee_calculator.py::_iter350_partner` line 545 | Raises `ValueError` on `partner_bp_rate < 0`. |
| `services/fee_calculator.py::calculate_broker_transaction` line 785 | Raises `ValueError` on `hammer_price < 0`. |
| `services/fee_calculator.py::calculate_fee` line 436 | Raises `ValueError` on unknown `seller_account_type`. |

### 4b — INCORRECTLY fails open (P0 defects for legal review)
| Location | Behaviour | Risk |
|---|---|---|
| `services/auction_settlement.py:257,258,627,628` | Missing buyer/seller province → QC (14.975%) | Over-collection on non-QC user. |
| `services/stripe_connect_service.py:523,619,702` | Missing partner_province → QC (14.975%) | Over-collection on non-QC partner. |
| `services/connect_payment_engine.py:59,634,722` | Missing province → QC (14.975%) | Over-collection. |
| `services/fee_calculator.py::_resolve_province:832` | Explicit legacy contract: unknown → QC | Over-collection. |
| `services/fee_calculator.py::FeeCalculator.calculate_buyer_total:996` | Unknown region → `TAX_RATES["QC"]` | Over-collection. |
| `services/tax_engine.py::calculate_gst_qst:693` | Hardcodes QC — ignores caller's province | Over-collection. |
| `services/tax_engine.py::calculate_general_payment:466–469` | Missing `seller_is_business` → no hammer tax | Under-collection if seller IS business but flag missing. |
| `services/broker_fee_engine.py:151` | `QST × amount if QC else 0` — no HST branch | Under-collection on ON/NS/NB/NL/PE. |
| `routes/broker_compliance.py:146` | Same as broker_fee_engine — QST-or-zero | Under-collection on HST provinces. |
| `services/invoice_service.py:160` | `9.975% if QC else 0%` — no HST branch | Non-QC invoices show 0 tax even if HST applies. |
| `services/connect_payment_engine.py:104-105` | Tax computed at 5% + 9.975% ignoring province | Over-collection on non-QC. |

---

## 5. Legal Review Collection (see `LEGAL_TAX_REVIEW_REQUIRED.md`)

Findings collected in the separate legal review file. Summary:
- Interprovincial supply — CRA §142.1 Place-of-Supply — currently applied
  correctly for BP (buyer prov) + SC (seller prov) but INVERTED in some
  legacy paths (fees taxed at buyer prov instead of seller prov).
- Marketplace facilitator obligations (Bill C-30 / ETA §211) — not
  addressed anywhere.
- Deposits, penalties, escrow, subscriptions — no tax computed. Legal
  review required to confirm each is non-taxable or that omission is
  a defect.

---

## Risk Assessment (financial impact)

| Risk | Severity | Likelihood | Financial impact (per $100 hammer) |
|---|---|---|---|
| Fail-open QC default (14.975%) on ON buyer (13%) | P0 | HIGH | +$1.97 over-collected per $100 fee |
| Fail-open QC default on AB buyer (5%) | P0 | HIGH | +$9.98 over-collected per $100 fee |
| Broker QST-or-zero on ON HST buyer | P0 | HIGH | −$13 under-collected per $100 fee |
| `calculate_general_payment` ignores province | P0 | MEDIUM | Same as row 1/2 |
| Divergent tier tables (3.0% vs 3.5% for vip) | P1 | LOW | Random ±0.5% swing on buyer premium |
| No tax on subscriptions | P1 | HIGH | Every subscription silently VAT-exempt — likely a defect |
| No tax handling for marketing invoices | P1 | HIGH | Every marketing invoice silently 0-tax — defect if BidVex sells the service |

---

## Recommended Implementation Plan (POST-APPROVAL, NOT NOW)

**Do not implement any of this without explicit approval.**

### Phase P6.1 — Prep (0 risk, no behaviour change)
1. Freeze `services/tax_rate_config.py` as the SINGLE source of truth.
2. Audit-mark every file listed in §1 as `DUPLICATE — SLATED FOR REMOVAL`.
3. Wire a scheduler heartbeat that logs a warning when any legacy path
   is invoked (canary before deletion).

### Phase P6.2 — Consolidation (behaviour-preserving)
1. Replace every hardcoded rate table (`services/vehicle_pricing.TAX_RATES_BY_PROVINCE`, `services/storage_pricing.TAX_RATES`, `services/broker_fee_engine.GST_RATE/QST_RATE`, `services/fee_calculator.TAX_RATES`, `_PROVINCE_TAX_REGIME`, `QC_GST_RATE/QC_QST_RATE`) with `tax_rate_config.get_tax_rate_sync(province)`.
2. Replace `services/tax_engine.calculate_gst_qst`, `calculate_tax`, `calculate_general_payment`, `calculate_vehicle_payment` with thin adapters to `fee_calculator.calculate_fee`.
3. Delete `services/fee_calculation_engine.py` (100% duplicate — move its single caller in `routes/fees.py` to `calculate_fee`).
4. Convert every `... or "QC"` silent default to raise `MissingProvince` — caller (route or scheduler) MUST provide it or explicitly opt into INTL (0%).
5. Add ONE bilingual invoice renderer that reads the province off the FeeResult (fixes `invoice_generator.py`'s hardcoded GST/QST labels).

### Phase P6.3 — Non-auction path tax coverage (blocked on legal review)
Only after §5 legal review decisions:
- Subscriptions — attach tax_amount to every Stripe subscription create.
- Marketing invoices — bring under `calculate_fee` or a new `calculate_marketing_service_tax`.
- Penalties — decide taxable/non-taxable; if taxable, attach.
- Escrow releases — confirm non-taxable event; annotate the settlement.

### Phase P6.4 — Regression protection
- Add ≥200 exact-cent test cases across (QC, ON, AB, BC) × (registered, unregistered) × (partner revenue, buyer premium, BP sharing, platform fee, subscription, marketing, escrow, deposit, penalty).
- Add an "anti-QC-default" static test that fails CI if any of the 21
  `or "QC"` fallbacks reappears in `git diff`.
- Add a lint rule: `git grep -nE '(0\.14975|0\.09975|0\.13\b|0\.15\b)' backend/` must return
  zero hits outside `services/tax_rate_config.py::BOOTSTRAP_RATES`.

### Phase P6.5 — Deployment gate
- Static audit (grep-based) proves zero duplicate rate tables.
- All 88 existing tests + ≥200 new tests green.
- ≥1 canary week in preview with the new engine under production traffic
  simulation before redeploy.

---

## Test-Safety Confirmation
- **88 baseline tests preserved** — audit performed READ-ONLY. Zero files
  modified during this audit.
- No Stripe / fee / payment / escrow / commission / invoice logic
  touched.
