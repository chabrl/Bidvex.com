# P6 — Tax Engine Consolidation Risk Matrix (pre-implementation)
**Status:** BLOCKED. Advisory only. No code changes.
**Purpose:** decision matrix the platform owner uses BEFORE approving any P6 code work.
**Companion documents:**
- `/app/docs/P6_TAX_AUDIT_REPORT.md` — full audit (307 lines).
- `/app/docs/LEGAL_TAX_REVIEW_REQUIRED.md` — legal review checklist.

---

## 1. Executive risk snapshot

| Category | Count | Highest severity |
|---|---|---|
| Tax calculation call-sites | 9 files, 25+ distinct locations | P0 |
| Duplicate rate tables | 8 divergent copies | P0 |
| Duplicate full calculators | 4 pairs | P0 |
| Silent province defaults (`... or "QC"`) | 21 instances | P0 |
| Silent function-signature defaults (`province: str = "QC"`) | 3 instances | P0 |
| Silent business-flag defaults | 2 instances | P1 |
| Fail-open (over/under-collection) findings | 11 instances | P0 |
| Non-auction paths with NO tax computed | 8 paths | P1 |

---

## 2. Financial impact matrix

**Per $100 hammer, single transaction:**

| # | Risk | Direction | Impact | Likelihood | Severity |
|---|---|---|---|---|---|
| 1 | Broker QST-or-zero on ON HST buyer (`broker_fee_engine.py:151`) | 🔻 UNDER | −$13.00 per $100 | HIGH | 🔴 **P0** |
| 2 | Silent QC default on AB buyer (`auction_settlement.py:257`) | 🔺 OVER | +$9.98 per $100 | HIGH | 🔴 **P0** |
| 3 | Silent QC default on ON buyer | 🔺 OVER | +$1.97 per $100 | HIGH | 🔴 **P0** |
| 4 | `invoice_service.py:160` non-QC shows 0 tax (never emits HST) | 🔻 UNDER | −$13–15 per $100 | HIGH | 🔴 **P0** |
| 5 | `tax_engine.calculate_gst_qst` hardcodes QC | 🔺 OVER | +$1.97–9.98 per $100 | MEDIUM | 🔴 **P0** |
| 6 | `connect_payment_engine.py:104` hardcodes 5%+9.975% ignoring province | 🔺 OVER | +$1.97–9.98 per $100 | MEDIUM | 🔴 **P0** |
| 7 | Divergent tier tables (3.0% vs 3.5% vip) | ↕ RANDOM | ±$0.50 per $100 | LOW | 🟠 **P1** |
| 8 | No tax on subscriptions | 🔻 UNDER | −$27 per $180 annual | HIGH | 🟠 **P1** — legal review required |
| 9 | No tax on marketing invoices | 🔻 UNDER | Full VAT missing | HIGH | 🟠 **P1** — legal review |
| 10 | No tax annotation on escrow releases | 🟢 (likely non-event) | $0 (confirm) | HIGH | 🟢 **P2** — legal review |
| 11 | No tax on penalties | 🔻 UNDER | Depends on treatment | UNKNOWN | 🟠 **P1** — legal review |

---

## 3. Change-management risk matrix

| Trigger event | Impact if consolidation NOT done | Impact if consolidation IS done |
|---|---|---|
| CRA raises GST from 5% to 6% | 8 files must be edited in lockstep — miss one and cent totals drift | 1 file (`tax_rate_config.BOOTSTRAP_RATES`) — everything cascades |
| Manitoba adds a provincial layer | 4 duplicate `TAX_RATES` tables must add MB rate manually | DB-backed lookup + one bootstrap constant |
| PE moves off HST → GST+PST | 3 files hardcode PE at 15% HST | Single migration in `tax_rate_config` |
| New province added (hypothetical NU commercial rate) | 6 files need updates | 1 file update |
| Currency mix (USD listing in QC) | `get_tax_rates_for_currency` returns 0 for non-CAD, causing under-collection | Explicit currency-vs-province matrix in canonical engine |

---

## 4. Test-coverage matrix (BEFORE P6 work begins)

### Current coverage — canonical paths (safe to leave alone)
| Path | Test file | Cases | Status |
|---|---|---|---|
| `fee_calculator._iter350_individual` | `test_iter482_p2_payment_cost_engine.py` | 46 | ✅ green |
| `fee_calculator._iter350_partner` | `test_iter482_p4_end_to_end.py` | 14 | ✅ green |
| `fee_calculator._iter350_vehicle` | `test_iter482_p31_reconciliation.py` | 38 | ✅ green |
| `fee_calculator._iter350_storage` | `test_iter482_p2_...` | 40 (golden matrix) | ✅ green |
| `tax_rate_config` bootstrap | `test_iter482_p31_reconciliation.py` | included | ✅ green |
| `payment_cost_engine` gross-up | `test_iter482_p5_payer_bears_fee.py` | 31 | ✅ green |

### Missing coverage — the risky legacy calculators
| Path | Coverage | Risk if refactored blind |
|---|---|---|
| `tax_engine.calculate_general_payment` (QC-hardcoded) | ❌ NONE | Buyer/seller cent drift on unwritten call-sites |
| `tax_engine.calculate_vehicle_payment` (QC-hardcoded) | ❌ NONE | Vehicle rounding drift |
| `broker_fee_engine.py` | ❌ NONE | HST provinces under-collected |
| `vehicle_pricing.calculate_taxes` | ⚠️ Indirect via `PricingManager.non_vehicle_stripe` | Rounding drift on non-QC |
| `storage_pricing.py` | ⚠️ Indirect via storage matrix | Rounding drift on non-QC storage |
| `invoice_service.py:160` | ❌ NONE | Non-QC invoices under-report tax |
| `invoice_generator.py` PDFs | ⚠️ Visual (unittest) only | Label drift ON QC / OFF non-QC |
| `subscription_service.py` labels | ❌ NONE | "+ taxes" label with no computed value |

**Recommendation:** add ≥ 200-case regression matrix (P7 in the plan) BEFORE refactoring — otherwise the consolidation itself becomes the biggest risk on the platform.

---

## 5. Legal review dependencies

Consolidation cannot be safely completed without written answers to:

| # | Legal question | Blocks refactor of |
|---|---|---|
| L1 | Is a subscription to BidVex Pro a taxable supply under CRA §142 place-of-supply rules? Where is BidVex's "place of supply" for online subscriptions? | `subscription_service.py`, `admin fee schedule UI` |
| L2 | Are BidVex marketing invoices (auction promotion) taxable? Which province's rate applies (marketplace HQ vs seller residence)? | `email_marketing.py`, `ad_campaigns.py`, `promotions.py` |
| L3 | Deposits held as security — non-taxable until forfeit? Confirm ITA §168 treatment. | `deposit_auto_capture.py`, `deposit_refund_queue.py`, `broker_deposit_service.py` |
| L4 | Late-payment penalties — taxable service or non-taxable liquidated damages? | penalty engine (currently no tax computed) |
| L5 | Escrow releases — confirm non-taxable event; taxable moment is the underlying sale. | escrow subsystem |
| L6 | Contractor commissions — B2B taxable supply from contractor to BidVex? | `contractor_commission.py` |
| L7 | Affiliate commissions — B2B taxable supply from affiliate to BidVex? | `routes/affiliate.py` |
| L8 | Marketplace Facilitator obligation under Bill C-30 / ETA §211.2 — is BidVex the "supplier of record" for the buyer's tax charge, or a pure intermediary? | **EVERYTHING** — determines whether we remit or the seller does |
| L9 | Cross-border USD listings — Canadian buyer taxed at CAD-equivalent, or exempt? Currently `get_tax_rates_for_currency` returns 0 for non-CAD which under-collects. | `tax_engine.get_tax_rates_for_currency` |
| L10 | Vehicle broker proxy bids — taxable event routes to whom (broker or beneficial buyer)? | `broker_fee_engine.py`, `routes/broker_compliance.py` |

**Owner action:** answer L1–L10 with counsel before any P6 code is written. Store the written responses under `/app/docs/legal/` (folder to be created) so the refactor can cite them line-by-line in the code review PR.

---

## 6. Suggested phase gating (matches P6_TAX_AUDIT_REPORT §Recommended Implementation Plan)

| Phase | Prerequisite | Deliverable | Risk after phase |
|---|---|---|---|
| **P6.0 — Legal review** | L1–L10 answered | `/app/docs/legal/P6_TAX_LEGAL_ANSWERS.md` | ❄ Frozen (no code touched) |
| **P6.1 — Test coverage** | P6.0 complete | ≥ 200-case exact-cent matrix across 13 provinces × 4 seller types × 3 methods | ❄ Frozen |
| **P6.2 — Canary logging** | P6.1 green | Every legacy calc logs `[p6-canary]` before delegating; 1-week soak in preview | Low |
| **P6.3 — Rate-table consolidation** | P6.2 canary clean | Replace 7 duplicate tables with `tax_rate_config` lookups (behaviour-preserving) | Medium — needs full matrix rerun |
| **P6.4 — Fail-closed on missing province** | P6.3 green | Convert 21 `... or "QC"` fallbacks to raise `MissingProvince` | Medium — every caller must be audited for injection point |
| **P6.5 — Non-auction path tax coverage** | P6.4 + L1–L10 | Subscriptions / marketing / penalties / etc. under canonical engine | Medium — new taxable events |
| **P6.6 — Delete legacy modules** | P6.5 green + 2-week canary | Remove `tax_engine.calculate_*`, `fee_calculation_engine.py`, dead constants | Low |
| **P6.7 — Deployment gate** | All above | Static-audit CI check + anti-regression tests + rollback plan | Low |

---

## 7. Rollback protocol (mandatory before P6.3+ starts)

| Component | Rollback strategy |
|---|---|
| Rate table constants | Keep old constants in a `LEGACY_` prefixed module for 90 days. Feature flag `TAX_ENGINE_MODE = "canonical" | "legacy"` toggles at runtime. |
| Silent-default removal | Do not merge until an admin dashboard shows every listing missing `buyer_province` / `seller_province`, so business ops can backfill BEFORE code raises. |
| Invoice PDF generator | Ship the new bilingual renderer behind a flag; run OLD + NEW renderers in parallel and store both for 60 days for audit. |
| Subscription tax attach | Ship as optional field first; only enforce after ≥ 4 weeks of preview parity. |

---

## 8. Decision requested from platform owner

| Decision | Options | Recommended default |
|---|---|---|
| Start P6.0 legal review now? | Yes / Not yet | **Not yet** — payment defect fix has priority. Circle back after §7 rollback protocol is documented. |
| Adopt `tax_rate_config` as SSOT? | Yes / Vote for a new module | **Yes** — already DB-backed, already correct, already covered by tests. |
| Fail-closed on missing province? | Raise 400 / Fall back to INTL (0%) / Keep QC | **Raise 400** on write paths, `INTL (0%)` on read paths (mirrors `normalize_province`). |
| Marketplace facilitator status? | Supplier of record / Pure intermediary | **Legal question L8** — no engineering call. |
| Timeline for P6 completion? | Q1 / Q2 / Q3 / Q4 | **Q3 after P7 (test matrix) lands** — do not consolidate without regression protection. |

---

## 9. Sign-off gate (both required before P6 code begins)

- [ ] Platform owner has answered L1–L10 (legal).
- [ ] Regression matrix (≥ 200 cases) is green in preview.
- [ ] Rollback protocol §7 is documented and reviewed.
- [ ] Anti-regression grep test in CI (`git grep -nE '(0\.14975|0\.09975|0\.13\b|0\.15\b)' backend/` must return zero hits outside `tax_rate_config.BOOTSTRAP_RATES`).
- [ ] Owner explicitly approves the phase-gating plan (§6) before any file is modified.

---

**Guardrails held during audit:** zero files modified. 88 baseline backend tests still green. No Stripe / fee / commission / invoice code touched.
