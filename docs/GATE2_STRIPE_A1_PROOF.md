# Gate 2 — Model A₁ Stripe Sandbox Proof

**Status:** ✅ PASS WITH CRITICAL FINDING
**Date:** 2026-02-12 UTC (iter482, Gate 2 only)
**Mode:** Stripe TEST (`livemode=false` confirmed on every object)
**Guardrails honored:** No refunds, no reverse_transfer, no production data touched, no secrets exposed, no code changes made outside test artifacts.

---

## 1. Authentication

| Field | Value |
|---|---|
| Platform account | `acct_1SXA7iBd6Wtvh7hs` |
| Country | CA |
| Default currency | CAD |
| `livemode` | **false** ✓ |

## 2. Canonical Test Scenario

| Input | Value |
|---|---|
| Hammer | $100.00 |
| Partner Buyer Premium | 10% |
| Buyer | Quebec |
| Partner | Quebec |
| Partner tax registered | FALSE |
| Quantity | 1 |
| Buyer tier | Standard |
| Partner listing | YES (E-10 Model 1) |

## 3. Stripe Objects Created (TEST-mode only)

| Object | ID |
|---|---|
| Partner Connect account | `acct_1U3RqWBgXhyoZCGg` (type=custom, CA) |
| PaymentIntent | `pi_3U3RvvBd6Wtvh7hs1L3ffn7A` |
| Charge | `ch_3U3RvvBd6Wtvh7hs1P4KzAdV` |
| Application Fee | `fee_1U3RvyBgXhyoZCGgTa9WNGSK` |
| Transfer | `tr_3U3RvvBd6Wtvh7hs1IqBBmLR` |
| Platform Balance Txn | `txn_3U3RvvBd6Wtvh7hs1cYtxmy7` |
| Partner-side Balance Txn | `txn_1U3RvyBgXhyoZCGg62pD9FrA` |

All objects have `livemode=false`.

## 4. Exact-Cent Reconciliation

| Item | Expected | Actual | Δ | Match |
|---|---:|---:|---:|:---:|
| Buyer charge (PaymentIntent.amount) | 11000 | 11000 | 0 | ✅ |
| Buyer charge (Charge.amount) | 11000 | 11000 | 0 | ✅ |
| Application fee (BidVex retains) | 345 | 345 | 0 | ✅ |
| Destination transfer (mirror of charge) | 11000 | 11000 | 0 | ✅ |
| Partner net BEFORE Stripe rail (transfer − app_fee) | 10655 | 10655 | 0 | ✅ |
| Currency | cad | cad | — | ✅ |
| `livemode` on PI / Charge / Transfer / AppFee | false | false | — | ✅ |
| `PaymentIntent.on_behalf_of` == Partner acct | ✓ | ✓ | — | ✅ |
| `transfer_data.destination` == Partner acct | ✓ | ✓ | — | ✅ |
| `Charge.on_behalf_of` == Partner acct | ✓ | ✓ | — | ✅ |
| `ApplicationFee.account` == Partner acct | ✓ | ✓ | — | ✅ |
| **No BidVex buyer premium added** (buyer_total == 11000) | 11000 | 11000 | 0 | ✅ |
| Stripe processing fee (PLATFORM-side, `type=stripe_fee`) | ≥ 0 | **437** | — | ✅ |

## 5. Ledger Movement Summary

**Platform (BidVex) ledger:**
| Type | Amount | Fee | Net |
|---|---:|---:|---:|
| `charge` | +11000 | **437 (stripe_fee)** | +10563 |
| `transfer` (out to Partner) | −11000 | 0 | −11000 |
| `application_fee` (received) | +345 | 0 | +345 |
| **BidVex net (per this txn)** | | | **−92 cents** |

**Partner ledger:**
| Type | Amount | Fee | Net |
|---|---:|---:|---:|
| `payment` (destination charge) | +11000 | 345 (application_fee) | +10655 |
| **Partner net (per this txn)** | | | **+10655 cents** |

## 6. Verdict

**PASS WITH CRITICAL FINDING.**

All A₁ architectural invariants are proven at runtime:
- Buyer paid **exactly** $110.00 (hammer + Partner BP), NO BidVex buyer premium, NO buyer-tier effect.
- BidVex `application_fee_amount = 345` (= $3.00 platform fee + $0.15 GST on fee + $0.30 QST on fee).
- Partner Connect account is correct destination.
- `on_behalf_of` correctly registers Partner as merchant-of-record.
- All Stripe objects `livemode=false`.

---

## 7. 🚨 CRITICAL FINDING (P0) — Report to User

**Title:** Stripe processing fee is NOT borne by the Partner.

**Evidence (from Stripe TEST-mode ledger):**
- The Stripe processing rail fee of **437 cents ($4.37)** was debited from the PLATFORM (BidVex) balance (`platform_bt.fee_details[0].type == "stripe_fee"`).
- The Partner-side balance transaction shows a "fee" of 345, but its `fee_details[0].type == "application_fee"` — that is BidVex's own application-fee reversal, **not** a Stripe processing fee.
- No `stripe_fee` entry appears in any Partner-side balance transaction.

**Refutes:** the docstring in `stripe_connect_service.calculate_partner_listing_checkout` (lines 391–392, 403–404, 502–504), which states *"Stripe rail cost is borne by the Partner via `on_behalf_of`"*. This is not true for destination charges. Per Stripe API behavior, `on_behalf_of` shifts only tax-reporting / merchant-of-record designation. Processing-fee incidence in a destination charge remains on the PLATFORM balance. The only Stripe topology that shifts processing-fee incidence to the connected account is a **Direct Charge** made against the connected account (with the platform collecting a separate `application_fee_amount`).

**Financial impact on the canonical scenario ($100 hammer, 10% Partner BP):**
| Line | Cents | Dollars |
|---|---:|---:|
| Buyer pays | 11000 | $110.00 |
| BidVex application-fee income | +345 | +$3.45 |
| Stripe rail fee debited from BidVex | −437 | −$4.37 |
| **True BidVex net revenue on this txn** | **−92** | **−$0.92** |
| Partner net | +10655 | +$106.55 |

**BidVex LOSES $0.92 on this canonical Partner sale.** The loss scales roughly with `stripe_fee_rate × buyer_total − platform_fee × (1 + fee_tax)`. For larger hammers, BidVex may still profit, but at low hammer prices BidVex is net-negative.

**Recommendation — DO NOT auto-remediate.** Present these mutually exclusive options to the user + accountant:
- **(A)** Increase the BidVex Partner platform fee (currently 3%) enough to always cover Stripe rail on the smallest expected transaction, AND update the price display / partner agreements accordingly.
- **(B)** Migrate Partner checkouts from **destination charges** to **Direct Charges** on the connected account (major architectural change; changes settlement, refunds, and reporting semantics; requires re-doing Gate 3 refund proof from scratch).
- **(C)** Add a Stripe-rail-cost line item to `application_fee` at charge time (dynamic gross-up using a fee estimator; imprecise because Stripe rail cost varies by card, currency, region).
- **(D)** Accept that BidVex bears the Stripe rail cost on Partner sales and update the financial model / SaaS unit economics accordingly.

**None of options A–D have been implemented.** No code has been changed. This finding blocks the "SAFE TO DEPLOY" gate independent of Gates 3+.

---

## 8. What Gate 2 Proved

- ✅ Functional Stripe TEST authentication (platform account retrievable, `livemode=false`).
- ✅ Model A₁ actual Stripe runtime proof (correct object shape, on_behalf_of, transfer_data.destination, application_fee_amount).
- ✅ Exact-cent Partner economics (buyer=11000, app_fee=345, transfer=11000, partner_net_pre_rail=10655).
- ✅ No BidVex buyer premium on Partner listings.
- ✅ No production Stripe or DB touched.
- ✅ No secrets exposed (only object IDs).
- ✅ No refunds, reverse_transfer, or application_fee_refund performed.

## 9. What Gate 2 Did NOT Prove (deferred)

- Quantity scaling proof (Gate 2 tested Qty = 1 only).
- Buyer-tier neutrality on Partner listings (Standard/Premium/VIP Elite — deferred).
- Refund integration (Gate 3).
- Partial refund + idempotency (Gate 3).
- Webhook replay idempotency (Gate 3).
- Production historical exposure (separate gate).

Awaiting user review of the Critical Finding before proceeding to any additional gate.

---

## Machine-readable artifact

Full JSON reconciliation report: `/app/docs/GATE2_STRIPE_A1_PROOF.json`
Test script (safe, TEST-mode-only, guarded): `/app/backend/tests/gate2_stripe_a1_sandbox_proof.py`
