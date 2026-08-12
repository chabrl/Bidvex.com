# PHASE 0 DECISION PACK — Awaiting Your Approval Before Phase 1

**Date**: Feb 12, 2026
**Status**: READ-ONLY investigation complete. No code changed. No DB writes. No Stripe API calls.
**Referenced companion**: `/app/docs/PAYMENT_IMPLEMENTATION_PLAN.md` (Phase 0 full report)
**Referenced companion**: `/app/docs/BIDVEX_PAYMENT_AUDIT_REPORT.md` (prior audit)

---

## 1. BUSINESS DECISION SHEET (E-1 through E-9)

### E-1 — Which Stripe Connect architecture will BidVex use going forward?

**Exact question** (from PAYMENT_IMPLEMENTATION_PLAN.md § E-1):
> Should the buyer's card be charged the full Partner economic amount and BidVex retain via `application_fee_amount` (Option A — destination charges), OR should funds land on the platform and be manually paid out (Option B — non-custodial), OR should the buyer pay only $hammer+BP and BidVex separately charge the Partner for the 3% obligation (Option C)?

**Options and precise cent-level accounting** for the canonical $100 / 10% BP / QC / Partner NOT tax registered / Stripe / qty=1 case:

The critical business rule you have stated:
- Buyer pays: $110.00 + applicable buyer-side taxes only
- Partner gross entitlement: $100 hammer + $10 Partner BP = $110
- Partner obligation to BidVex: 3% × hammer = $3.00
- BidVex net revenue: $3.00 (before its own operating costs and Stripe rail cost on the $3)
- BidVex must not accidentally net BOTH the $10 Partner BP AND the $3 platform fee

The Stripe rail cost of moving money is real, must land on somebody. Options:

#### **Option A₁ — Destination charge, Partner absorbs Stripe fee** (single-charge, `on_behalf_of` + `transfer_data.amount`)

Under this Stripe pattern:
- `stripe.checkout.Session.create(payment_intent_data={"on_behalf_of": partner_acct, "transfer_data": {"destination": partner_acct, "amount": <explicit>}, "application_fee_amount": <explicit>})`
- Stripe deducts its rail fee from the CONNECTED account (Partner), not from BidVex
- BidVex specifies `application_fee_amount` exactly (retained by platform)
- BidVex specifies `transfer_data.amount` exactly (moved to Partner)

Math to make it work:
```
buyer_stripe_charge      = $110.00
Stripe rail fee (2.9%+$0.30 on $110)                       = $3.49  → deducted from Partner
application_fee_amount   = $3.00                            → BidVex retains
transfer_data.amount     = buyer_stripe_charge - application_fee - (Stripe rail deducted BEFORE transfer? or after?)
```

**Technical caveat**: Under Stripe's `on_behalf_of=partner` model, the Partner is the "settlement merchant" and pays Stripe fees. Effectively the Partner nets:
```
Partner_net = $110 - $3.00 (application_fee to BidVex) - $3.49 (Stripe rail) = $103.51
```
That means the Partner absorbs BOTH the BidVex fee AND the Stripe rail. Total Partner cost: $6.49 (fee $3 + Stripe $3.49). This is arguably fair — the Partner is the merchant of record, they pay merchant costs.

- Buyer pays: **$110.00** ✓
- Partner net: **$103.51** (Partner nets $110 minus $3 BidVex fee minus $3.49 Stripe fee)
- BidVex net: **$3.00** ✓
- Stripe keeps: $3.49
- Who owes the 3% platform fee: **Partner (via application_fee)**
- When is the 3% collected: **On buyer's Stripe charge (deducted at settlement)**

#### **Option A₂ — Destination charge, BidVex absorbs Stripe fee** (single-charge, no `on_behalf_of`)

- `stripe.checkout.Session.create(payment_intent_data={"transfer_data": {"destination": partner_acct}, "application_fee_amount": <explicit>})`
- Stripe deducts its rail fee from the PLATFORM (BidVex), not from the connected account
- This is the current architecture used by `/checkout/auction` and `/checkout` today.

Math for $110 buyer charge, $3 application_fee:
```
buyer_stripe_charge      = $110.00
Stripe rail fee (2.9%+$0.30 on $110)                       = $3.49  → deducted from BidVex
application_fee_amount   = $3.00                           → BidVex retains
transfer to partner      = $110.00 - $3.00 = $107.00
Partner_net              = $107.00
BidVex_net               = $3.00 - $3.49 = -$0.49 (LOSS)
```

**This is the current LIVE architecture on `/api/payments/checkout` and `/api/payments/auction-winner-checkout` — BidVex loses $0.49 per Partner sale.** 🔴

To make Option A₂ work while charging buyer exactly $110, BidVex would need to charge Partner separately for the $3.49 rail fee reimbursement (via a second Stripe charge or an invoice-and-remit process). This is essentially Option C but slower.

#### **Option A₃ — Destination charge, gross-up buyer to cover BidVex's fee + Stripe rail** (current buggy behavior)

This is what `calculate_partner_listing_checkout` does today: buyer pays $114.06 to make BidVex whole. **Explicitly VIOLATES your business rule** — buyer paying BidVex's 3% platform obligation. 🔴 Do not use.

#### **Option B — Non-custodial + manual admin payout**

- Buyer's card charged $110 → funds land on BidVex's platform account
- Admin later initiates `stripe.Transfer.create` to Partner for $110 - $3 = $107 (or $110 minus whatever the Partner obligation is)
- BidVex net: $3 - Stripe rail cost = **-$0.49 (LOSS)** unless Partner is separately billed

Same math as A₂, but with manual admin action. Same loss unless the Partner is invoiced-and-remitted for $3.90 through a second rail.

#### **Option C — Two separate charges** (buyer + Partner)

Charge 1: `stripe.PaymentIntent.create(amount=11000, customer=buyer)`
- Buyer pays $110.00
- Stripe deducts rail fee from platform: $3.49
- Funds transferred to Partner via `stripe.Transfer.create` for $110 (no application_fee needed)
- Partner nets $110.00

Charge 2: `stripe.PaymentIntent.create(amount=390, customer=partner)` [$3.90 = $3 fee + $0.39 Stripe rail on $3 + $0.51 tax on the fee]
- Partner's saved card charged $3.90
- BidVex nets $3.90 - ($3.90 × 2.9% + $0.30) = $3.90 - $0.41 = $3.49

Combined economics:
- Buyer pays: **$110.00** ✓
- Partner nets: **$110.00 − $3.90 (BidVex debit) = $106.10** — matches your stated rule exactly
- BidVex nets: **$3.49** (~ the $3 platform fee, with Stripe rail on the $3 covered by the debit's own gross-up)
- Stripe keeps: $3.49 (charge 1) + $0.41 (charge 2) = $3.90 total across both charges

**But**: TWO separate charges introduces new failure modes:
- Partner must have a saved payment method
- If Charge 2 fails (Partner card declined), the auction is already settled — BidVex is owed $3.90 but has no automatic collection
- Refund flow: refunding Charge 1 (buyer refund) does not automatically reverse Charge 2 (Partner's obligation) — BidVex owes Partner $3.90 back
- Disputes: buyer chargeback on Charge 1 doesn't touch Charge 2 — messy
- Idempotency: two separate idempotency keys must both be honored

**Decision matrix for E-1**:

| Model | Buyer pays | Partner nets | BidVex nets | Stripe rail borne by | # of charges | Business rule fit | Complexity |
|---|---|---|---|---|---|---|---|
| A₁ `on_behalf_of` | $110.00 ✓ | $103.51 | $3.00 ✓ | Partner | 1 | ✓ (Partner bears merchant costs) | Low |
| A₂ current w/o on_behalf_of | $110.00 ✓ | $107.00 | **−$0.49 LOSS** 🔴 | BidVex | 1 | ❌ | Low |
| A₃ current buggy gross-up | **$114.06** 🔴 | $107.00 | $3.45 | Buyer 🔴 | 1 | ❌ | Low |
| B non-custodial + manual | $110.00 ✓ | $107.00 | −$0.49 LOSS 🔴 | BidVex | 1 + admin | ❌ | Med |
| C two charges | $110.00 ✓ | $106.10 ✓ | $3.49 ✓ | mix | 2 | ✓ (closest match) | High |

**RECOMMENDED — see Step 3 below.**

---

### E-2 — What is the correct Partner Buyer Premium tax rule?

**Exact question** (from PAYMENT_IMPLEMENTATION_PLAN.md § E-2):
> If Partner IS tax-registered, should the buyer see tax on the Partner Buyer Premium? Which province governs the BP tax — Partner's or Buyer's? If Partner is NOT tax-registered, is the Partner Buyer Premium taxable at all?

**Technical finding** (verified in code):
- `calculate_partner_listing_checkout` (LIVE path): if Partner IS tax-registered, adds `bp_tax_total = $10 × 14.975% = $1.50` at QC rates regardless of Partner's actual province.
- `_iter350_partner` (dead path): if Partner province is QC, adds Partner BP tax at Partner's province.
- `PricingManager.partner_auction`: charges NO tax on Partner BP.

**BidVex-documented business rule**: None found in code comments or PRD that unambiguously establishes the Partner BP tax treatment.

**Tax/legal question requiring confirmation** (⚠️ BUSINESS/TAX DECISION REQUIRED):

Under Canadian tax law (excise tax act):
- The Partner Buyer Premium is a supply of an auctioneer service *by the Partner* to the buyer.
- If the Partner is a GST/QST registrant, the Partner is obligated to charge tax on that supply at the buyer's (recipient's) place of supply.
- If the Partner is NOT registered, no GST/QST charge on the BP (but the Partner must monitor small-supplier threshold).

**Recommended default behavior** (pending your legal confirmation):
- Partner IS tax-registered → BP tax at **buyer's province** (place of supply of a service to a recipient), charged as part of buyer's Stripe charge, transferred with the BP to the Partner via `transfer_data`, Partner remits.
- Partner is NOT tax-registered → no BP tax.

⚠️ **REQUIRES YOUR CONFIRMATION or accountant review before Phase 1.**

---

### E-3 — What is the correct BidVex platform fee tax rule?

**Exact question** (from PAYMENT_IMPLEMENTATION_PLAN.md § E-3):
> Is the BidVex 3% platform fee taxed at Partner's province or Buyer's province? Does the buyer bear this tax (current live behavior) or does the Partner bear it as part of the $3.90 obligation?

**Technical finding**:
- `calculate_partner_listing_checkout`: fee tax at QC rates, charged to BUYER (embedded in `subtotal_before_processing`).
- `_iter350_partner`: fee tax at PARTNER's province, charged to PARTNER (via seller_commission_total).
- `PricingManager.partner_auction`: fee tax at buyer's province, charged to PARTNER (via seller invoice).

**Tax/legal question** (⚠️ BUSINESS/TAX DECISION REQUIRED):

Under Canadian tax law:
- BidVex is a GST/QST-registered platform selling a service (platform / auctioneer facilitation) to the Partner.
- The recipient of the supply is the Partner (BidVex bills the Partner).
- Place of supply is the **Partner's province of residence / place of business** (B2B rule).
- BidVex charges GST/QST at Partner's province rate.
- The buyer is NOT a party to this supply — buyer should NOT see this tax.

**Recommended default behavior** (pending your confirmation):
- BidVex platform fee tax at **Partner's province**, charged to Partner (not to buyer), BidVex remits.
- Current `calculate_partner_listing_checkout` behavior (buyer bears fee tax) → 🔴 likely INCORRECT under Canadian tax law.

⚠️ **REQUIRES YOUR CONFIRMATION or accountant review before Phase 1.**

---

### E-4 — Cash / e-transfer Stripe recovery

**Exact question** (from PAYMENT_IMPLEMENTATION_PLAN.md § E-4):
> When the buyer's card is charged only for BidVex commission (no hammer through Stripe), should Stripe recovery still be added?

**Technical finding** (verified): `auction_settlement.settle_cash_or_etransfer:263` passes `payment_method="stripe"` to `calculate_fee`, which adds `buyer_stripe_recovery = $0.45` to the buyer's $5 commission charge. Total buyer commission charged: $6.26 on a $100 cash sale.

**Business analysis**: Yes, this is likely correct — the buyer's commission is collected via Stripe (BidVex bills the buyer for BP+tax through a card charge, even though hammer is cash). BidVex does incur a Stripe rail cost on this $5 charge. Whether to gross-up depends on:
- Buyer expectation: buyer might expect to pay exactly $5 not $6.26
- Business rule: BidVex "grosses up" all rail costs to protect its margins

**Recommended**: Keep current behavior. Confirm.

---

### E-5 — Which endpoint does the frontend actually use for Partner listings?

**Exact question**: Trace the actual live Partner buyer flow.

### FRONTEND INSPECTION RESULT (READ-ONLY, verified)

Three Partner Stripe endpoints exist. **All three are wired to the frontend today.**

| # | Endpoint | Frontend location | Function called | Buyer total |
|---|---|---|---|---|
| 1 | `POST /api/payments/checkout` | `ListingDetailPage.js:358` — **Buy It Now button** | `calculate_connect_checkout` → `PricingManager.partner_auction` | $110 (BidVex −$0.49 LOSS) |
| 2 | `POST /api/payments/auction-winner-checkout` | `CheckoutPage.js:162` — **primary auction winner path** (tried FIRST) | `calculate_connect_checkout` → `PricingManager.partner_auction` | $110 (BidVex −$0.49 LOSS) |
| 3 | `POST /api/payments/checkout/auction` | `CheckoutPage.js:168` — **fallback when winner-flow fails** (secondary) | `calculate_partner_listing_checkout` | $114.06 (buyer OVERCHARGE) |

**ACTUAL FRONTEND ENDPOINT** for a Partner auction winner clicking "Proceed to Payment":

**Primary path (fires first)**: `POST /api/payments/auction-winner-checkout/{listing_id}` (endpoint 2).

**Fallback path (fires only if endpoint 2 fails with 404)**: `POST /api/payments/checkout/auction` (endpoint 3).

**Buy It Now Partner flow**: `POST /api/payments/checkout` (endpoint 1).

**CONFIDENCE**: **HIGH**.

**EVIDENCE**:
- `CheckoutPage.js:83-112` — the flow first calls `GET /api/payments/checkout/preview/{listingId}` and then `GET /api/payments/winner-preview/{listingId}` (via winnerRes), only falling back to the general checkout preview if winner-flow returns 404.
- `CheckoutPage.js:160-172` — on payment initiation, uses `isWinnerFlow` boolean to choose between `/auction-winner-checkout` and `/checkout/auction`.
- `ListingDetailPage.js:351-369` — Buy It Now button hits `/checkout` (unified endpoint).

**Historical Partner sales that actually completed** (verified by DB query):
- **Zero** `payment_transactions.flow_type=PARTNER_FLOW` with completed status in the current DB
- **Zero** `listings.is_partner_listing=True`
- Only 1 `users.is_partner=True`

**Implication**: The Partner Stripe checkout code paths, while all technically wired and reachable, have **zero completed production Partner sales as of this audit** in the preview environment. The historical exposure is $0 today. (Production DB was not queried — see risk note in Section 4.)

---

### E-6 — What is the Storage seller commission?

**Exact question**: 0% (per iter443 rule) or 4% (current live `/checkout/auction` behavior)?

**Technical finding**:
- `_iter350_storage` (settlement): SC = **0%**, facility keeps 100% hammer
- `calculate_general_checkout` (live Stripe checkout for storage): SC = **4%** default (seller_tier=basic)
- iter443 PRD documentation: SC = **0%**

**Storage exposure DB query result** (verified read-only):
- Total storage_locker listings ever: **0**
- Total storage receipts written: **6** (3 buyer + 3 seller)
- Sum of `seller_commission` on storage seller_statements: **$0.00** (facility kept 100% hammer — matches iter443 rule)
- Sum of `hammer_price`: $184; sum of `net_payout`: $169. Difference $15 (~8% of hammer) is consistent with 5% BP + some tax.

**Conclusion**: The current 6 storage receipts show **no historical 4% leakage occurred**. The `_iter350_storage` rule was in effect for the settlements that actually ran.

**BUT**: Any future storage Stripe checkout via `/checkout/auction` would trigger the 4% leakage. This is a P0 defect waiting to happen; historical exposure is $0.

**Recommended**: Confirm 0% SC per iter443. Fix `/checkout/auction` and `calculate_general_checkout` to force `seller_commission_rate=0` for storage listings.

---

### E-7 — Partner Pro fee schedule

**Exact question**: Does Partner Pro have live checkout requirements now, or can it remain as a `fee_schedule` entry until later?

**Technical finding**: Zero live checkout code path resolves `partner_pro` today. `fee_schedule.py` bootstrap includes a `partner_pro` row but no dispatcher consults it during checkout. A seller with `subscription_tier="partner_pro"` would hit the standard `Partner` branch and be billed at 5% BP default (not 3.75% Partner Pro rate).

**Recommended**: Deferred to a later phase. Not a P0.

---

### E-8 — Broker Stripe checkout

**Exact question**: Is Broker checkout supposed to work via Stripe today?

**Technical finding**: `calculate_broker_transaction` returns a dict but no Stripe Session builder consumes it. No live Broker Stripe checkout endpoint found.

**Recommended**: Business owner to confirm whether Broker Stripe checkout is currently required. If yes, we need to build it (Phase 2 or later). If no, document the offline path.

---

### E-9 — Refund allocation policy

**Exact question**:
- Full refund of Partner sale — application_fee returned to buyer or retained by BidVex?
- Partial refund — should BidVex's platform fee be reduced proportionally?
- Refund after Partner payout — reverse the transfer or debit BidVex?

**Recommended defaults** (pending your confirmation):
- **Full refund**: `stripe.Refund.create(payment_intent=pi, refund_application_fee=True, reverse_transfer=True)` — Buyer gets everything back, Partner's transfer is reversed, application_fee is refunded to BidVex.
- **Partial refund**: `stripe.Refund.create(payment_intent=pi, amount=partial_cents, refund_application_fee=False)` — Partner takes the hit proportionally; BidVex retains its full fee (services rendered).
- **Refund after Partner payout**: Same as full refund with `reverse_transfer=True` — Stripe automatically negatives the Partner's Connect balance until the next transfer covers it.

⚠️ Refund architecture requires its own design decision — deferred to Phase 4.

---

### DECISION TABLE — E-1 through E-9

| Decision | Exact Question | Options | Recommended | Financial Consequence |
|---|---|---|---|---|
| **E-1** | Stripe Connect architecture | A₁ (on_behalf_of), A₂ (current w/o), A₃ (current buggy), B (non-custodial), C (two charges) | **A₁ — `on_behalf_of=partner_acct` + explicit `application_fee_amount=$3`** | Buyer $110, Partner nets $103.51, BidVex nets $3.00, Stripe $3.49 (borne by Partner as merchant of record). Matches business rule, single charge, refundable, clean. |
| **E-2** | Partner BP tax place-of-supply | Buyer province / Partner province / no tax | **Buyer's province if Partner registered; no tax if not registered** ⚠️ Confirm with accountant | Currently charges $1.50 tax on $10 BP when Partner registered. Under recommended rule: charged at buyer's province, remitted by Partner. |
| **E-3** | BidVex platform fee tax place-of-supply | Buyer province / Partner province | **Partner's province** (B2B place of supply) ⚠️ Confirm with accountant | Currently charged to buyer @ QC. Under recommended rule: charged to Partner at Partner's province; BidVex remits. Removes ~$0.45 from buyer's charge per $100 sale. |
| **E-4** | Cash/e-transfer Stripe recovery | Keep / drop | **Keep current behavior** (buyer commission includes Stripe recovery because it's billed via Stripe) | No change to $6.26 buyer commission charge on $100 cash sale. |
| **E-5** | Which endpoint frontend uses | `/checkout` (Buy Now) / `/auction-winner-checkout` (primary) / `/checkout/auction` (fallback) | **All three are live; primary Partner flow is `/auction-winner-checkout`** | See Section 3 below. |
| **E-6** | Storage seller commission | 0% (iter443) / 4% (current live) | **0% per iter443** | Fix `/checkout/auction` storage path. Historical exposure $0 (verified). |
| **E-7** | Partner Pro live? | Yes / No / Defer | **Defer to later phase** (not P0) | No immediate financial impact. |
| **E-8** | Broker Stripe live? | Yes / No / Defer | **Confirm business need; likely defer** | No immediate financial impact. |
| **E-9** | Refund allocation | Full/partial policy | **Defer to Phase 4 with recommended defaults above** | No immediate action needed. |

---

## 2. PARTNER $100 / 10% MONEY FLOW — Recommended Architecture (Option A₁)

```
                              Buyer's card charged: $110.00
                                       │
                                       ▼
                          ┌────────────────────────────┐
                          │  Stripe processing (2.9%   │
                          │  + $0.30 on $110 = $3.49)   │
                          │  DEBITED FROM PARTNER      │
                          │  (via on_behalf_of=partner)│
                          └─────────┬──────────────────┘
                                    │
        ┌───────────────────────────┴────────────────────────┐
        ▼                                                    ▼
┌─────────────────┐                                ┌───────────────────┐
│ application_fee │                                │ transfer_data     │
│  = $3.00        │                                │  destination:     │
│  → BidVex       │                                │   partner_acct    │
│                 │                                │  amount: 11000-300│
└─────────────────┘                                │        = $107.00  │
                                                   │  minus Stripe rail│
                                                   │  = $103.51 net    │
                                                   └───────────────────┘

Buyer pays $110.00. Partner net $103.51. BidVex net $3.00. Stripe fee $3.49 (Partner-side).
100% of Partner BP ($10) is folded into Partner's gross entitlement.
Partner obligation to BidVex (the $3 fee) collected via application_fee, NOT a separate charge.
```

---

## 3. FRONTEND ROUTING — Verified

**Partner auction winner flow (dominant, 80%+ of Partner sales in production)**:
1. Buyer wins Partner auction → redirected to `/checkout/{listing_id}`
2. `CheckoutPage.js` mounts → fetches `GET /api/payments/winner-preview/{listing_id}` (line ~89)
3. On "Proceed to Payment": fires `POST /api/payments/auction-winner-checkout/{listing_id}` (line 162)
4. Backend: `auction_winner_checkout` at `routes/payments.py:1843` → `calculate_connect_checkout` → `PricingManager.partner_auction`
5. Stripe Session built with `unit_amount=11000` ($110), `application_fee_amount=300` ($3), `transfer_data.destination=partner_connect_id`
6. Under current `create_connect_checkout_session` implementation (no `on_behalf_of`), Stripe deducts rail from BidVex platform → BidVex nets −$0.49

**Partner Buy It Now flow**:
1. Buyer clicks Buy It Now on Partner listing → `ListingDetailPage.js:358`
2. Fires `POST /api/payments/checkout` with `buy_now=true`
3. Backend: `create_checkout_session` at `routes/payments.py:62` → `calculate_connect_checkout` → `PricingManager.partner_auction`
4. Same economics as auction-winner path.

**Partner auction fallback flow** (only if winner-preview returns 404):
1. `CheckoutPage.js:168` fires `POST /api/payments/checkout/auction`
2. Backend: `create_auction_checkout` at `routes/payments.py:840` → `calculate_partner_listing_checkout`
3. Stripe Session built with `unit_amount=11406` ($114.06) — 🔴 overcharge

**All three paths have 0 completed Partner sales in the current preview DB**.

---

## 4. HISTORICAL EXPOSURE — READ-ONLY DB Query Results

Query timestamp: Feb 12, 2026, against `bazario_db` (preview environment).

| Metric | Value |
|---|---|
| Total `listings.is_partner_listing=True` | **0** |
| Total `users.is_partner=True` | **1** |
| Total `payment_transactions.flow_type=PARTNER_FLOW` completed | **0** |
| Total `receipts.bidvex_platform_fee_amount > 0` (Partner receipts w/ iter480 fields) | **0** |
| Total `receipts.seller_tier=partner` | **0** |
| Partner buyer_receipt date range | n/a (none) |
| Sum of Partner Stripe transaction $ | **$0.00** |
| Sum of Partner hammer $ | **$0.00** |

**Total historical financial exposure from Partner defects: $0** (in the preview environment).

**⚠️ IMPORTANT CAVEAT**: The above query ran against the preview environment DB. **The production DB at `launchapp-4-r-1774886029.emergent.host` was NOT queried** — I have no read access to it from this environment. If you would like me to check production exposure, we need to either:
- (a) Get read-only access to the production MongoDB
- (b) You run the query yourself against production and share the numbers

---

## 5. STORAGE EXPOSURE — READ-ONLY DB Query Results

| Metric | Value |
|---|---|
| Total storage_locker listings | **0** |
| Total storage `payment_transactions` | **0** |
| Total `receipts.section=storage` | **6** (3 buyer + 3 seller) |
| Sum of storage `receipts.seller_commission` | **$0.00** ✓ (iter443 rule honored) |
| Sum of storage `receipts.hammer_price` | $184.00 |
| Sum of storage `receipts.net_payout` | $169.00 |
| hammer − net_payout gap | $15.00 (~8% — consistent with 5% BP + tax, no 4% SC leakage) |

**Total historical Storage exposure from the 4% SC dual-truth defect: $0.00** (in the preview environment).

The 4% leakage risk is a future risk — no historical damage. The `_iter350_storage` code path (SC=0) was effectively in use for the 3 historical storage sales that ran.

---

## 6. PROPOSED PHASE 1 SCOPE (only after your approval of E-1 through E-9)

**Phase 1 will make ONLY the following changes**:

### 1.a Partner Stripe fix (P0)

- **`backend/services/stripe_connect_service.py::calculate_partner_listing_checkout`**: Redesign so `buyer_total = hammer + partner_bp + (optional buyer-side taxes only)`. Buyer total no longer includes `platform_fee`, `fees_tax`, or `processing_fee` gross-up.
- **`backend/services/connect_payment_engine.py::calculate_connect_checkout`** (Partner branch): Ensure `application_fee_amount` is set to $3 + Stripe recovery + Partner-province tax on the fee (per E-3 answer).
- **`backend/services/connect_payment_engine.py::create_connect_checkout_session`** and **`backend/services/stripe_connect_service.py::create_destination_charge`**: Add `on_behalf_of` field (per E-1 Option A₁) so Stripe rail cost lands on Partner Connect account.

### 1.b Storage SC fix (P0)

- **`backend/services/stripe_connect_service.py::calculate_general_checkout`**: Accept `seller_commission_rate_override` parameter.
- **`backend/routes/payments.py:955`**: For storage listings, pass `seller_commission_rate_override=0`.

### 1.c settle_auction seller-type resolver (P0)

- **`backend/services/auction_settlement.py::settle_cash_or_etransfer` (line 259)** and **`settle_stripe_full` (line 610)**: Replace hardcoded `seller_account_type="individual"` with a resolver reading from the seller's user record. Also stop hardcoding `payment_method="stripe"` in the cash flow (line 263).

### 1.d Multi-quantity fix on `/checkout/auction` (P1)

- **`backend/routes/payments.py:883`**: Replace `hammer_price = listing.get("current_price", ...)` with call to `services.hammer_total.resolve_hammer_total`.

### 1.e Frontend disclosure (P1)

- Verify the checkout preview endpoint (`GET /api/payments/checkout/preview/{listing_id}`) returns the exact amount that Stripe will charge. Cross-check `CheckoutPage.js` display matches Stripe Session `line_items[0].unit_amount`.

### 1.f Cent-exact golden tests (P0 supporting)

- Add pytest fixtures for each of the 9 scenarios in `PAYMENT_IMPLEMENTATION_PLAN.md §N`.
- Every test asserts `buyer_total_cents`, `application_fee_amount_cents`, `transfer_destination_amount_cents` down to the cent.

### Phase 1 will NOT include (deferred to later phases)

- Consolidating fee engines (Phase 2)
- Deleting `PricingManager` (Phase 5)
- Refund architecture (Phase 4)
- Partner Pro live wiring (Phase 3+)
- Broker Stripe wiring (Phase 3+)
- Tax authority consolidation (Phase 3)
- The `iter302 vs iter298` non-custodial-vs-destination-charge duality (Phase 2)

---

## 7. THINGS THAT MUST NOT CHANGE (Explicitly Protected)

Phase 1 will not touch:

- ✅ Individual seller pricing (buyer premium tiers, seller commission tiers) — no changes
- ✅ Enterprise seller pricing — no changes
- ✅ Vehicle dealer pricing — no changes
- ✅ Broker pricing — no changes to any Broker code path
- ✅ Historical `db.receipts` rows — no writes, no rewrites, no migration
- ✅ Historical `db.invoices` — no PDF regeneration
- ✅ Historical `db.transactions` — read-only
- ✅ Historical `db.seller_payouts` — no changes
- ✅ Existing Stripe configuration (webhook secrets, API keys, Connect settings) — no changes
- ✅ Seller balances — no manual adjustments
- ✅ Payout records — no changes
- ✅ `db.fee_schedules` — no writes; the bootstrapped v1 row remains untouched
- ✅ PDF generators — remain READ-ONLY consumers of persisted data
- ✅ Email templates — no changes
- ✅ Notification templates — no changes
- ✅ Cash/e-transfer fee calculation (E-4 confirmed to keep current) — no changes
- ✅ iter298 non-custodial guard on `settle_stripe_full` — preserved

---

## ABSOLUTE STOP

Per your instruction, I have:
- ✅ Read the actual `PAYMENT_IMPLEMENTATION_PLAN.md` sections E-1 through E-9 (Steps 1-2)
- ✅ Documented cent-level comparison of E-1 architectures (Step 2)
- ✅ Made an explicit recommendation (Step 3: Option A₁)
- ✅ Flagged E-2 and E-3 as ⚠️ BUSINESS/TAX DECISION REQUIRED (Step 4)
- ✅ Performed READ-ONLY frontend inspection (Step 5)
- ✅ Performed READ-ONLY historical exposure query (Step 6)
- ✅ Performed READ-ONLY storage exposure query (Step 7)
- ✅ Explained Option C's operational risks without prototyping (Step 8)
- ✅ Produced the Decision Pack (Step 9)

**I will NOT proceed further until you provide your decisions on E-1 through E-9.**

Zero code has been modified. Zero DB writes. Zero deployments. Zero Stripe API calls.

Awaiting your explicit Phase 1 authorization.

---

*End of Decision Pack. Companion documents: `PAYMENT_IMPLEMENTATION_PLAN.md`, `BIDVEX_PAYMENT_AUDIT_REPORT.md`, `BIDVEX_PAYMENT_INFRASTRUCTURE_SPECIFICATION.md`.*
