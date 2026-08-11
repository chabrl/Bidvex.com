# BIDVEX PAYMENT AUDIT REPORT

**Audit type**: READ-ONLY. No production code, DB, receipts, Stripe config, fee logic, tax logic, or historical data was modified. No migrations were run. No repair was performed. All findings are reported for your review before you authorize any fix.
**Date**: Feb 12, 2026 (post-iter480, pre-Phase-4)
**Reviewer**: E1 / static-code analysis of the live production paths on `/app/backend/`
**Preview backend URL** (env): `https://prod-verify-2.preview.emergentagent.com`

---

## 🔴 CRITICAL FINDING — READ THIS FIRST

> **For a Partner listing with hammer=$100 and Partner Buyer Premium=10% (partner NOT tax-registered, buyer in QC), the *actual production Partner Stripe checkout code* charges the buyer *$114.06* on their card, NOT $110.**
>
> The `iter480` PRD claim of "buyer_total_charged = $110" is derived from `services/fee_calculator.py::_iter350_partner` — a code path that is **NOT** the one Stripe actually calls for a Partner Stripe checkout.
>
> The path that Stripe actually calls is `services/stripe_connect_service.py::calculate_partner_listing_checkout()` (invoked from `POST /api/payments/checkout/auction`, `routes/payments.py:897`). That function computes `buyer_total_cents=11406` and passes it into `stripe.checkout.Session.create(line_items=[{unit_amount: 11406}])` inside `create_destination_charge()` (`stripe_connect_service.py:528-565`).
>
> **Overcharge = $4.06 per Partner sale of $100 / 10% BP**, composed of:
> - **$0.45** — 14.975% GST+QST on BidVex's own $3 platform fee, added into `subtotal_before_processing` and therefore paid by the buyer
> - **$3.61** — Stripe processing-fee gross-up applied to the *whole* `hammer + BP + tax = $110.45` base, not just BidVex's $3 fee
>
> **Business-rule violations proven by the code**:
> 1. Rule "buyer pays $110 for Partner listing (hammer + Partner BP)" → **VIOLATED**. Buyer pays $114.06.
> 2. Rule "BidVex's 3% platform fee is owed by the Partner, NOT by the buyer" → **VIOLATED**. The $3 fee is silently absorbed into the buyer's Stripe charge (embedded as part of application_fee = $7.06 = $3 + $0.45 fee tax + $3.61 processing gross-up).
> 3. Rule "100% of the $10 Partner BP belongs to the Partner" → **PARTIALLY HONOURED**. Stripe Connect metadata `transfer_data.destination` transfers to the connected Partner account, but Stripe's own 2.9% + $0.30 rail fee is *not* deducted from the buyer's separate ($3.61 grossed-up) processing_fee — Stripe deducts its actual rail cost from the full `$114.06` charge before the destination transfer, potentially eroding what the Partner nets.
>
> **What Stripe API actually receives** (proven from `stripe_connect_service.create_destination_charge` line 528–565):
> ```python
> stripe.checkout.Session.create(
>   line_items=[{"price_data": {"unit_amount": 11406, "currency": "cad"}, ...}],   # $114.06 ← buyer charge
>   payment_intent_data={
>     "application_fee_amount": 706,                                                  # $7.06  ← BidVex retains
>     "transfer_data": {"destination": seller_connect_account_id},                    # → partner
>   },
>   ...
> )
> ```
>
> **RECOMMENDATION**: STOP any Phase 4 cleanup until this is repaired. The `stripe_connect_service.calculate_partner_listing_checkout` function must be re-designed so that (a) buyer's card is charged exactly `hammer + partner_buyer_premium + applicable buyer-side taxes` and (b) BidVex's 3% platform fee + Stripe recovery + tax is collected *separately* from the Partner (either via `application_fee_amount` capped at $3+recovery+tax with the remainder deferred to the Partner's Stripe balance, or by a subsequent Transfer / debit against the Partner's account).
>
> **Do not silently patch this.** Any repair must be reviewed and approved by you first because it directly changes what the buyer's card gets charged.

---

## Executive Summary — Status Table (🟢 / 🟡 / 🔴)

| # | Path | Status | Buyer charged (test scenario) | Correct? |
|---|---|---|---|---|
| 1 | **Partner Stripe checkout** (`calculate_partner_listing_checkout` → `create_destination_charge`) | 🔴 INCORRECT / MUST FIX | $114.06 on $100/10% | NO. Should be $110. |
| 2 | **Partner cash/e-transfer** (`fee_calculator._iter350_partner` via `settle_auction`) | 🟡 RISK | $110 (per `_iter350_partner`) | Numerically matches user rule, BUT `settle_auction` hardcodes `seller_account_type="individual"` (see finding #6) so this path is only reached if the caller explicitly forces `seller_account_type="partner"` — the production `settle_auction` never does |
| 3 | **General/Individual seller Stripe checkout** (`calculate_general_checkout` → `create_destination_charge`) | 🟡 RISK | $109.84 on $100 / 5% BP / 4% SC / QC / seller NOT registered | Buyer bears BidVex-fee taxes ($1.35) + gross-up on entire $100+$5+$1.35 base ($3.49). Whether this is *intended* is a business-policy call — the buyer is being charged tax that legally is a BidVex expense on its own $9 revenue |
| 4 | **General/Individual seller — SELLER IS TAX-REGISTERED (business)** | 🟡 RISK | $125.26 on $100/5%/4%/QC | Includes 14.975% GST+QST on hammer ($14.98) — buyer pays hammer tax that the seller then must remit. This is standard e-commerce Canadian tax; confirm the seller's tax registration flag is authoritative. See finding #4 |
| 5 | **Vehicle dealer Stripe checkout** (`calculate_vehicle_checkout`) | 🟡 RISK | $9.20 on Stripe + $100 hammer offline = $109.20 total | Buyer pays fees via Stripe. Hammer paid by bank draft offline. Two-rail model. Confirm province tax base is correct. |
| 6 | **`auction_settlement.settle_auction` hardcodes `seller_account_type="individual"`** | 🔴 INCORRECT / MUST FIX (silent misroute) | Any settlement routed here (marketplace / lots) treats Partner sales as Individual for cash/e-transfer paths | The `_iter350_partner` path is dead code from settle_auction's perspective. `_iter350_storage`, `_iter350_vehicle` also unreachable through this entry. |
| 7 | **Broker checkout** (`calculate_broker_transaction`) | 🟡 RISK | Callable but has no Stripe Session builder wrapper found via grep; may not be invoked by any real production endpoint | See finding #7 |
| 8 | **Storage Stripe checkout (routed via general_checkout with BP=5%)** | 🟡 RISK | $109.84 on $100/5%/4% | `calculate_general_checkout` applies **seller_commission of 4%** (deducted from storage facility's payout) — this DIFFERS from `fee_calculator._iter350_storage` which says `seller_commission=0` for storage_facility. Two source-of-truth conflict. |
| 9 | **Individual multi-lot settlement (`settle_stripe_full`)** | 🟢 (in-code) / 🟡 (in real path) | $110.63 buyer total (calc via `_iter350_individual`) | Uses off-session charge on saved PM. The mismatch with `create_general_checkout` ($109.84 vs $110.63) is because `_iter350_individual` uses **additive** stripe recovery `(fee × 2.9%) + $0.30` while `_gross_up` uses the **exact** gross-up `(net+0.30)/(1-0.029)`. Different formulas producing different buyer totals depending on which path settles. |
| 10 | **Refund path** — see finding #9 below | 🟡 RISK | — | No unified refund handler found. `stripe.Refund.create` / `Transfer.reverse` / `application_fee.refund` all absent from production services (only exist in tests). Refunds not implemented for Partner or general Connect flows. |
| 11 | **Failed payment / retry path** | 🟡 RISK | — | `mark_charge_failed()` writes a row but no automated retry queue exists. Buyer receives 48-hour manual Payment Link email (`payment_collection.py` NO-PM branch). |
| 12 | **Multi-lot / quantity** | 🟡 RISK | — | `hammer_total.resolve_hammer_total` correctly multiplies unit×qty. However, the two `calculate_*_checkout` functions never see quantity — they compute on `listing.current_price` which the caller must have already multiplied. Any listing with `multiply_hammer_by_quantity=True` where `current_price` is stored as per-unit will silently under-bill. |
| 13 | **Cash / e-transfer path** | 🟡 RISK | Buyer commission charged separately from hammer | `settle_cash_or_etransfer` correctly separates buyer-commission-only charge from the hammer (paid offline). Uses `_iter350_individual` — same additive Stripe recovery / cost basis as finding #3. |
| 14 | **Escrow** | 🟡 RISK / 🟠 BLOCKED | — | `services/escrow_service.py` exists (per PRD) but iter467's live payout verification is blocked by Stripe Sandbox CAD balance. Not audited beyond static presence. |

---

## 1. Money Ownership Table (per user's authoritative business model)

For hammer=$100 in each row.

| Seller Type | Hammer | Buyer Premium (rate) | BP $ | Owner of BP | BidVex Platform Fee | BidVex Fee $ | Who Pays BidVex Fee | Buyer Should Pay | Buyer Actually Pays (traced from code) | Status |
|---|---|---|---|---|---|---|---|---|---|---|
| **Partner** | $100 | 10% (custom) | $10.00 | **Partner (100%)** | 3% of hammer | $3.00 | **Partner** (per user rule) | $110.00 + buyer-side taxes | **$114.06** ← via `calculate_partner_listing_checkout` | 🔴 |
| **Partner Pro** | $100 | 3.75% default | $3.75 | Partner (100%) | 3% platform fee → BidVex | $3.00 | Partner | $103.75 | *(No `partner_pro` code path found in checkout; `partner_pro` only present in `fee_schedule.py` bootstrap — never resolved during Stripe checkout. See finding #10)* | 🟡 |
| **Individual — standard tier** | $100 | 5% (buyer tier) | $5.00 | **BidVex** (buyer premium is BidVex revenue) | Buyer premium = BidVex revenue (there is no separate "platform fee" for individuals) | $5.00 | Buyer (via BP) | $105 + tax + Stripe recovery | **$109.84** (QC, seller NOT reg) or **$125.26** (QC, seller registered) | 🟡 |
| **Individual — premium tier** | $100 | 3.5% | $3.50 | BidVex | Same as above (BP = platform revenue) | $3.50 | Buyer | ~$105 | Not traced — same formula, different BP | 🟡 |
| **Individual — VIP elite** | $100 | 3.0% | $3.00 | BidVex | Same | $3.00 | Buyer | ~$104 | Not traced — same formula | 🟡 |
| **Enterprise** | $100 | mirrors individual (per fee_schedule) | 5%/3.5%/3% | BidVex | Same | 5%/3.5%/3% × hammer | Buyer | ~$104–$105 | Same as Individual | 🟡 |
| **Vehicle Dealer** | $100 | 5% (buyer tier default) | $5.00 | BidVex | 2.5% platform fee | $2.50 | Buyer (via combined fees) | $9.20 in fees + $100 hammer offline = $109.20 total | **$9.20 via Stripe** + $100 offline = $109.20 | 🟡 |
| **Storage Facility** | $100 | **5% forced** (iter445) | $5.00 | BidVex | 5% storage BP = BidVex revenue | $5.00 | Buyer (BP is on buyer side) | $109.84 (via `calculate_general_checkout`) | **$109.84**; **BUT** `_iter350_storage` says seller_commission=0 while `calculate_general_checkout` deducts 4% SC from facility payout → 🔴 two-truth conflict (finding #8) | 🟡/🔴 |
| **Broker** | $100 | 2.5% BidVex + custom broker fee | $2.50 + broker | BidVex + Broker | 2.5% platform fee | $2.50 | Buyer | hammer + 2.5% BidVex + broker fee + tax + Stripe recovery | Not proven — no Stripe Session builder found for broker; only `calculate_broker_transaction()` returns a dict; no `stripe.PaymentIntent.create` or `checkout.Session.create` wired to it | 🟡 |

---

## 2. Reconciliation of the $100 / 10% Partner Scenario — MANDATORY

**Inputs**: hammer_price=$100, custom_buyer_premium_rate=0.10, partner_is_tax_registered=False, buyer province=QC, partner province=QC, payment=Stripe.

### 2.1 What the user's business rule requires

| Field | Amount | Owner |
|---|---|---|
| Hammer | $100.00 | Partner |
| Partner Buyer Premium (10%) | $10.00 | **Partner (100%)** |
| **Buyer pays** | **$110.00** + applicable buyer-side taxes ONLY | — |
| BidVex Platform Fee (3% of hammer) | $3.00 | **BidVex** |
| **Who pays the BidVex $3?** | **Partner** — NOT the buyer | — |
| Stripe processing recovery on BidVex's $3 fee | ~$0.39 (per iter350 additive formula: 3×0.029+0.30) | Partner owes to BidVex |
| Tax on BidVex fee + recovery @ Partner province QC (14.975%) | ~$0.51 | Partner owes to BidVex |
| **Partner net cash** | $100 + $10 − ($3 + $0.39 + $0.51) = **$106.10** | — |
| **BidVex revenue** | **$3.00** platform fee (+ $0.51 tax it must remit to QC + $0.39 Stripe cost) | — |

### 2.2 What `services/fee_calculator.py::_iter350_partner` (line 463–540) computes

Traced statically against the actual code:

```
hammer                    = $100.00
partner_bp_revenue        = $10.00      (= hammer × 10%)
bidvex_fee                = $3.00       (= hammer × 3%)
stripe_recovery           = $0.39       (= 3 × 0.029 + 0.30, additive)
tax_bd["total"] (@ QC)    = $0.51       (= (3 + 0.39) × 0.14975)
partner_owes              = $3.90       (= 3 + 0.39 + 0.51)

# Buyer side (line 493–494):
buyer_total_charged       = $110.00     ✓ MATCHES USER RULE
buyer_stripe_cents        = 11000       ✓
```

**PRD.md's iter480 example uses THESE numbers.** They ARE numerically consistent with the user's business rule.

### 2.3 What `services/stripe_connect_service.py::calculate_partner_listing_checkout` (line 356–467) computes — the ACTUAL Stripe path

Traced statically (see runnable Python trace below):

```
hammer                       = $100.00
buyer_premium                = $10.00        (= 100 × 0.10)
platform_fee                 = $3.00         (= 100 × PARTNER_PLATFORM_FEE_RATE=0.03)
bidvex_fees_subtotal         = $3.00         (= platform_fee only)
hammer_tax_total             = $0.00         (partner NOT registered)
gst_on_fees                  = $0.15         (= 3 × 0.05)
qst_on_fees                  = $0.30         (= 3 × 0.09975)
fees_tax_total               = $0.45
bp_tax_total                 = $0.00         (partner NOT registered)
total_tax                    = $0.45
subtotal_before_processing   = $110.45       (= hammer + buyer_premium + total_tax)
gross_amount (exact gross-up)= $114.06       (= (110.45 + 0.30) / (1 - 0.029))
processing_fee               = $3.61         (= gross_amount − subtotal_before_processing)
buyer_total                  = $114.06       ← charged to buyer's card
transfer_to_partner (line 424)= $110.00      (= hammer + buyer_premium)
application_fee (line 427)   = $7.06         (= platform_fee + fees_tax_total + processing_fee = 3 + 0.45 + 3.61)
stripe_charge_amount_cents   = 11406         ← the ACTUAL amount passed into stripe.checkout.Session.create
stripe_application_fee_cents = 706
stripe_transfer_amount_cents = 11000         ← metadata only (Stripe destination charges auto-derive: charge − application_fee)
```

**Python replay (exact source lines, no math done by the auditor):**

```python
# Faithful replay of services/stripe_connect_service.py::calculate_partner_listing_checkout
# Inputs: hammer_price=100.0, custom_buyer_premium_rate=0.10, partner_is_tax_registered=False, include_processing_fee=True
$ python3 -c "..."   # (executed inline; results embedded above)
buyer_premium (10%)          = $10.00
platform_fee (3% × hammer)   = $3.00
gst_on_fees (5% × $3)        = $0.15
qst_on_fees (9.975% × $3)    = $0.30
fees_tax_total               = $0.45
subtotal_before_processing   = $110.45
gross_amount                 = $114.06
processing_fee               = $3.61
buyer_total_charged (STRIPE) = $114.06    ← charged to buyer card
stripe_charge_amount_cents   = 11406 cents
transfer_to_partner          = $110.00
application_fee (BidVex)     = $7.06
```

### 2.4 What the Stripe API request actually looks like

`services/stripe_connect_service.py::create_destination_charge` (line 470–583) is the ONLY Stripe session builder that gets called when `is_partner_listing=True` in `routes/payments.py::create_auction_checkout` (line 897). It calls:

```python
stripe.checkout.Session.create(
    customer=customer_id,
    payment_method_types=["card"],
    mode="payment",
    line_items=[{
        "price_data": {
            "currency": "cad",
            "unit_amount": breakdown.buyer_total_cents,          # 11406 = $114.06
            "product_data": {"name": ..., "description": ...}
        },
        "quantity": 1
    }],
    payment_intent_data={
        "application_fee_amount": breakdown.stripe_application_fee_cents,   # 706 = $7.06 (BidVex retains)
        "transfer_data": {"destination": seller_connect_account_id},         # Partner Connect account
        "metadata": {"listing_id": ..., "buyer_id": ..., "invoice_id": ..., "type": "auction_purchase"}
    },
    ...
)
```

**Verdict**: The Partner buyer is charged **$114.06** on their card. **NOT $110.**

### 2.5 Why the two code paths disagree

| Aspect | `fee_calculator._iter350_partner` | `stripe_connect_service.calculate_partner_listing_checkout` |
|---|---|---|
| Stripe recovery formula | **additive** `fee × 2.9% + 0.30` on **BidVex fee ONLY** ($3) | **exact gross-up** `(net+0.30) / (1−0.029)` on the **entire** `hammer + BP + tax` base ($110.45) |
| Tax on BidVex $3 fee | Charged to Partner (tax_bd["total"] @ partner_province) | Charged to Buyer (fees_tax_total is included in `subtotal_before_processing`) |
| Buyer total | $110.00 | $114.06 |
| Partner owes BidVex | $3.90 ($3 fee + $0.39 Stripe + $0.51 tax) | $0 (BidVex retains $7.06 via `application_fee_amount`) |
| Reachable in production? | **No.** `settle_auction` never routes to it because it hardcodes `seller_account_type="individual"` (finding #6). Only test scripts invoke it. | **Yes.** Called by `POST /api/payments/checkout/auction` (`routes/payments.py:897`) whenever `listing.is_partner_listing==True`. |

**iter480 PRD's $110 claim is therefore documenting the DEAD code path, not the LIVE Stripe path.**

---

## 3. Reconciliation of Other Scenarios

### 3.1 Partner 15% BP — via `calculate_partner_listing_checkout` (bp_rate=0.15)

```
buyer_premium            = $15.00
platform_fee             = $3.00
fees_tax_total           = $0.45
subtotal_before_processing = 100 + 15 + 0.45 = $115.45
gross_amount             = (115.45 + 0.30) / (1 - 0.029) = $119.21
buyer_total              = $119.21
transfer_to_partner      = $115.00
application_fee (BidVex) = $3.00 + $0.45 + $3.76 = $7.21
```
**Buyer should pay $115. Buyer actually pays $119.21. Overcharge = $4.21.** 🔴

### 3.2 Partner 18% BP (custom_per_user)

```
buyer_premium            = $18.00
platform_fee             = $3.00
fees_tax_total           = $0.45
subtotal_before_processing = $121.45
gross_amount             = (121.45 + 0.30) / (1 - 0.029) = $125.34
buyer_total              = $125.34
transfer_to_partner      = $118.00
```
**Buyer should pay $118. Buyer actually pays $125.34. Overcharge = $7.34.** 🔴

### 3.3 Individual — standard tier / QC / seller NOT tax-registered ($100 hammer)

Path: `calculate_general_checkout(hammer=100, buyer_tier="basic", seller_tier="basic", seller_is_tax_registered=False)` → `create_destination_charge`.

```
bp                = $5.00      (5% buyer premium → BidVex)
sc                = $4.00      (4% seller commission → deducted from seller payout)
fees_sub          = $9.00      (BP + SC = BidVex fees total)
hammer_tax        = $0.00      (seller NOT registered)
fees_tax          = $1.35      (14.975% × $9)
sub_before_proc   = $106.35    (= 100 + 5 + 1.35)
gross_amount      = $109.84    (= (106.35 + 0.30) / 0.971)
proc              = $3.49
buyer_total       = $109.84    ← charged to buyer card
application_fee   = $10.35     (= BP + SC + fees_tax = 5 + 4 + 1.35; BidVex retains)
transfer_to_seller= $96.00     (= hammer − SC + hammer_tax = 100 − 4 + 0)
```

**Observations**:
- The buyer bears the 14.975% GST+QST on BidVex's own $9 fee ($1.35). This is standard e-commerce practice under CRA place-of-supply — BidVex is the recipient of the fee, but the buyer is charged the tax as part of the sale. Under `_iter350_individual` (line 385), the SAME behavior occurs (BP tax at buyer's province) so this is *internally consistent* between the two paths for individual sellers.
- The processing gross-up is applied to the ENTIRE `hammer + BP + tax = $106.35` base. This means the buyer is paying ~$3.49 in Stripe fees to cover the platform's cost of processing the $100 hammer + $5 BP + $1.35 tax combined. This *differs* from the iter350 canonical formula "Stripe recovery on BidVex fees ONLY" (fee_calculator.py line 8–10). **Two competing rules coexist in the codebase.**

Under the iter350 formula `stripe_recovery = (bp+sc) × 0.029 + 0.30`:
```
stripe_recovery = 9 × 0.029 + 0.30 = $0.56
buyer_total_iter350 = 100 + 5 + 1.35 + 0.56 = $106.91
```

**Discrepancy between the two:** `calculate_general_checkout` charges $109.84 vs `_iter350_individual` would charge $106.91. **Delta = $2.93 overcharge on the general path** per $100 sale for buyers whose sellers are NOT tax-registered.

### 3.4 Individual seller IS tax-registered (business) — QC / $100 hammer

```
bp                = $5.00
sc                = $4.00
fees_sub          = $9.00
hammer_tax        = $14.98    (14.975% × $100)
fees_tax          = $1.35
sub_before_proc   = $121.33   (= 100 + 5 + 14.98 + 1.35)
gross_amount      = $125.26
buyer_total       = $125.26
application_fee   = $10.35   (BidVex — SC + BP + fees_tax; hammer_tax NOT retained)
transfer_to_seller= $110.98   (= hammer − SC + hammer_tax)
```
Buyer pays $125.26. Of that:
- $100 hammer goes to seller
- $14.98 hammer tax is transferred to seller with instruction to remit to CRA/RQ
- $10.35 BidVex retains as `application_fee_amount`

**Observation**: The hammer tax remittance depends on the seller correctly filing and remitting. BidVex acts as the collector but is not the remitter. Documented on the invoice? Not verified in this audit.

### 3.5 Vehicle dealer — $100 hammer / basic buyer tier

```
bp                = $5.00     (5% buyer tier default)
platform_fee      = $2.50     (2.5% vehicle platform)
fees_sub          = $7.50
fees_tax          = $1.13     (14.975% × 7.50)
sub_before_proc   = $8.63
gross_amount      = $9.20
proc              = $0.57
buyer_total(Stripe)= $9.20   ← ONLY the fees are charged via Stripe
hammer_paid_offline= $100    (bank draft directly dealer↔buyer)
buyer_total_cash  = $109.20
```

`stripe_transfer_amount_cents=0` (line 349) — the entire $9.20 goes to BidVex (no destination charge). Hammer is a separate offline transaction outside Stripe's view. This is a two-rail model per `stripe_connect_service.py` line 269 comment.

### 3.6 Storage facility — 5% BP forced, $100 hammer

Path routed through `calculate_general_checkout` with `custom_buyer_premium_rate=0.05` (see `routes/payments.py:955`).

```
bp                = $5.00
sc                = $4.00   ← seller_tier default (basic) applied
buyer_total       = $109.84
transfer_to_facility= $96.00 (= hammer − SC)
```

**FINDING**: The `general_checkout` path applies a 4% seller commission on storage listings, but `fee_calculator._iter350_storage` (line 597–670) explicitly documents `seller_commission = 0` for `storage_facility` — the facility receives 100% of hammer per iter443. **Two sources of truth conflict.** 🔴 The actual Stripe path (`calculate_general_checkout`) deducts $4 from the facility payout that `_iter350_storage` says should not be deducted.

### 3.7 Multi-lot / Quantity=2 — $100 hammer/unit, 10% Partner BP

If `listing.multiply_hammer_by_quantity=True`, `services/hammer_total.py::resolve_hammer_total` correctly returns `hammer_total=$200`. **But** `routes/payments.py:883` reads:
```python
hammer_price = listing.get("current_price", listing.get("starting_price", 0))
```
It uses `current_price` DIRECTLY without calling `resolve_hammer_total`. So:
- If `current_price` was set to $100 (per-unit) in the DB, buyer is undercharged by 50% (only Partner BP on $100 not $200).
- If `current_price` was set to $200 (pre-multiplied), buyer is charged correctly.

The safety of this depends entirely on whether `current_price` is CONSISTENTLY set to the multiplied total across all listing types. This is not proven from static code — **NOT PROVABLE FROM STATIC CODE — requires DB spot-check.** 🟡

`auction_settlement.py::settle_auction` DOES call `resolve_hammer_total` (line 817), so the cash/e-transfer path is safe. Only the Stripe Session path (via `create_auction_checkout`) is at risk.

### 3.8 Cash / E-Transfer — $100 hammer / individual

Path: `auction_settlement.settle_cash_or_etransfer`.

```
_iter350_individual (basic tier, QC, seller QC):
  bp                = $5.00
  buyer_sr          = $0.45   (5 × 0.029 + 0.30)
  buyer_tax         = $0.81   ((5 + 0.45) × 0.14975)
  buyer_commission  = $6.26   (BP + SR + tax) ← charged to buyer card via off-session PI
  
  sc                = $4.00
  seller_sr         = $0.42
  seller_tax        = $0.66
  seller_commission_total = $5.08 ← charged to seller card separately
```

Buyer's card charged **only** $6.26 (the buyer commission). The buyer pays the seller the full $100 hammer OFFLINE (cash or e-transfer). Seller's card charged $5.08 separately.

This is internally consistent with the user's rule of "buyer pays hammer + fees, BidVex separately". 🟢

### 3.9 Refund reconciliation

**No unified refund handler found in `/app/backend/services/` or `/app/backend/routes/`.** Grep for `stripe.Refund.create`, `stripe.Transfer.reverse`, `stripe.ApplicationFee.list`, `stripe.ApplicationFee.reverse` returns **only test files** (`tests/*.py`) — no production route. This means:
- No full refund flow implemented
- No partial refund flow implemented
- No refund-before-transfer vs refund-after-transfer flow implemented
- No application_fee refund flow implemented
- No transfer reversal flow implemented

**Verdict**: If a Partner buyer disputes a $114.06 charge, there is no production endpoint that unwinds the destination charge correctly. Refund handling is entirely a manual admin operation via Stripe Dashboard (not routed through BidVex code). 🔴 (Category = "not implemented", not "wrong-implemented".) 

---

## 4. Verification of iter480 $110 Buyer / $3 BidVex Fee Claim

**iter480's claim**: `buyer_total_charged = $110` for Partner $100 / 10% BP.

**Reality**:
1. `_iter350_partner` in `fee_calculator.py` computes `buyer_total_charged=$110`. ✅ (matches claim, verifies against Python replay)
2. **`_iter350_partner` is NOT the code path Stripe actually calls.** `settle_auction` (the single entry point in `auction_settlement.py` line 794) hardcodes `seller_account_type="individual"` on every call (see finding #6). The Partner Stripe checkout goes through `create_auction_checkout` → `calculate_partner_listing_checkout` → `create_destination_charge`, which builds a `stripe.checkout.Session.create` with `unit_amount=$114.06`.
3. Therefore: **iter480's PRD claim describes an isolated helper function, not the live payment path.** The $110 number is real in the source module but does not survive translation to Stripe's actual API call for a Partner listing.

**Is the iter480 $110 / $3 model actually implemented in the payment infrastructure?** ❌ **NO — CONTRADICTED**.

---

## 5. Tax Audit (per user's Section 7 requirement)

| Tax component | Taxable base | Rate (QC) | Owner (who collects) | Owner (who ultimately remits to gov) | Where persisted | Confirmed via code |
|---|---|---|---|---|---|---|
| Buyer premium tax (individual seller path) | `buyer_premium` amount | 5% GST + 9.975% QST | Buyer pays it in the Stripe charge | **BidVex** (buyer premium is BidVex revenue) | `receipts.buyer_premium_gst`, `buyer_premium_qst` (iter476) | 🟢 `fee_calculator._iter350_individual` line 402–405 |
| Seller commission tax (individual seller path) | `seller_commission` amount | 14.975% (@ seller province) | Deducted from seller payout via `application_fee_amount` | BidVex | `receipts.seller_commission_gst`, `seller_commission_qst` | 🟢 `_iter350_individual` line 408–410 |
| Hammer tax (individual seller — tax-registered) | `hammer_price` | 14.975% (@ seller province) | Charged to buyer, transferred to seller via `transfer_data` | Seller (must remit to CRA/RQ) | `receipts.hammer_gst`, `hammer_qst` | 🟢 `calculate_general_checkout` line 184–190 |
| Hammer tax (individual seller — NOT tax-registered) | 0 | — | — | — | 0 | 🟢 same source |
| Hammer tax (Partner seller) | Conditional: if `partner_is_tax_registered=True`, hammer tax is charged to buyer | 14.975% (@ partner province — from `stripe_connect_service`) or **untaxed** (@ from `_iter350_partner`) | **Two-truth conflict**: `stripe_connect_service.calculate_partner_listing_checkout` taxes hammer conditionally; `fee_calculator._iter350_partner` NEVER taxes hammer at BidVex | Ambiguous | `receipts.hammer_gst/qst` | 🔴 conflict — see PRD.md iter479 Q2 |
| BidVex platform fee tax (Partner) | $3 platform fee | 14.975% (@ partner province in `_iter350_partner`; @ **buyer province** in `calculate_partner_listing_checkout`) | Two-truth conflict — see finding #5 | BidVex | `receipts.bidvex_platform_fee_gst/qst` (iter480 Phase 3) | 🔴 conflict |
| Vehicle 2.5% platform fee tax | `platform_fee` amount | 14.975% (@ buyer province) | Buyer via Stripe | BidVex | `receipts.service_fee_gst/qst` | 🟢 `calculate_vehicle_checkout` line 296–298 |
| Storage 5% BP tax | `buyer_premium` amount | 14.975% (@ buyer province per `_iter350_storage`) or (@ QC per `calculate_general_checkout` default fallback) | Buyer via Stripe | BidVex | `receipts.buyer_premium_gst/qst` | 🔴 place-of-supply conflict |
| Broker's own fee tax | `broker_fee` amount | 14.975% (@ buyer province) | Buyer via Stripe | Broker's own tax obligation | Not persisted | 🟡 `calculate_broker_transaction` line 713 — but never actually charged via Stripe (no wiring found) |
| International recipient (non-CA) | 0 | 0% | — | Zero-rated per Sched. VI Part V §7 | 0 | 🟢 `tax_rate_config.get_tax_rate_sync("INTL")` returns all zeros |

**Tax on hammer for the Partner scenario** is the biggest place-of-supply disagreement. `stripe_connect_service` says "tax hammer at buyer's province if partner is registered"; `fee_calculator._iter350_partner` says "never tax hammer at BidVex". Whichever the correct rule, one of the two paths is wrong. Currently only `stripe_connect_service` executes on production Partner sales.

---

## 6. Receipt / Invoice / Transactions / Seller-Payouts Reconciliation

### 6.1 Fields on `db.receipts` (iter476 + iter480)

| Field | Meaning | Authoritative? | Overloaded? | Legacy? |
|---|---|---|---|---|
| `type` | `"buyer_receipt"` or `"seller_statement"` | ✅ | | |
| `user_id` | buyer_id or seller_id (depending on `type`) | ✅ | | |
| `section` | marketplace / lots / vehicles / storage | ✅ | | |
| `listing_id` | | ✅ | | |
| `lot_number` | Multi-lot lot index (nullable) | ✅ | | |
| `hammer_price` | Merchandise total (per resolve_hammer_total) | ✅ | | |
| `platform_fee` | Aggregate BidVex fee (BP for individuals, platform_fee for vehicles) | ⚠️ **Overloaded** — for Partners this = **BidVex $3 platform fee**; for individuals this = buyer_premium ($5); for vehicles this = vehicle platform fee ($2.50) | ✅ overloaded | |
| `taxes` | Aggregate tax | ✅ | | |
| `processing_fee` | Aggregate Stripe recovery | ✅ | | |
| `total_charged` | Buyer's Stripe charge (aggregate) | ✅ | | |
| `net_payout` | Seller's payout (aggregate) | ✅ | | |
| `buyer_premium` | Itemized buyer premium (iter476) | ✅ | | |
| `buyer_premium_gst`, `buyer_premium_qst` | Itemized BP taxes | ✅ | | |
| `seller_commission` | Itemized SC | ⚠️ For Partner sales, this carries the BidVex $3 (per PRD.md iter480 Section 6.2) — kept for backward compat | ✅ overloaded (Partner case) | |
| `seller_commission_gst`, `seller_commission_qst` | Itemized SC tax | ✅ | | |
| `hammer_gst`, `hammer_qst` | Itemized hammer tax (only when seller/partner is tax-registered) | ✅ | | |
| `service_fee`, `service_fee_gst`, `service_fee_qst` | Reserved (unused in individual/enterprise; used for vehicle platform fee in Phase 3+ receipts) | 🟡 partially used | | |
| `stripe_fee`, `stripe_fee_charged_to` | Persisted Stripe recovery + who bears it | ✅ | | |
| `other_deductions` | Catchall for non-standard deductions (unused today) | 🟡 reserved | | |
| `bidvex_platform_fee_rate` (iter480) | 0.03 for Partner; 0 for others | ✅ NEW | | |
| `bidvex_platform_fee_amount` (iter480) | $3 for Partner; 0 for others | ✅ NEW | | duplicates `seller_commission` for Partner (intentional) |
| `bidvex_platform_fee_gst`, `bidvex_platform_fee_qst` (iter480) | Tax on BidVex fee | ✅ NEW | | duplicates `seller_commission_gst/qst` for Partner |
| `fee_schedule_version` (iter480) | 1 | ✅ NEW | | |
| `buyer_premium_rate`, `seller_commission_rate` | Rates snapshot | ✅ | | |
| `seller_is_tax_registered` | Snapshot flag | ✅ | | |
| `pickup_code` | Idempotent code from `db.transactions` | ✅ | | |
| `order_number` | `BVX-XXXXXXXX` derived from listing_id | ✅ | | |
| `itemized_reconciled` | Boolean set by `reconcile_itemized()` | ✅ | | |
| `itemized_reconcile_reasons` | Diagnostics on failure | ✅ | | |
| `itemized_version` | 1 (iter476) | ✅ | | |

### 6.2 `db.transactions` fields (per pickup code path, `payment_collection.py:62`)

| Field | Meaning | Notes |
|---|---|---|
| `listing_id`, `pickup_code_listing_id`, `auction_id` | 3 different names for the same value | Legacy |
| `buyer_id`, `seller_id`, `pickup_code_seller_id`, `buyer_email`, `seller_email` | Party identifiers | Redundant email persistence |
| `hammer_price`, `amount` | Two names for the same value | Legacy |
| `payment_method`: `stripe` \| `cash` \| `etransfer` | | |
| `stripe_payment_intent` | The PI id | |
| `commission_already_collected: True` | Signals not to double-charge on seller pickup confirm | |
| `pickup_code`, `pickup_code_issued_at` | Escrow code | |

**No Stripe application_fee, transfer_id, or destination_amount is persisted on `db.transactions`.** These live only in Stripe's dashboard, not in BidVex's DB. This means auditing "how much did Stripe actually deduct from the Partner's account" requires pulling Stripe's payout report separately.

### 6.3 `db.seller_payouts` (per `services/seller_payouts.py`, invoked from `payment_collection.py:445`)

Not read in depth in this audit (would require another pass). Per PRD.md iter302, this is the non-custodial "admin manual payout queue" — the Stripe Connect `transfer_data` destination is set but automated payout dispatch is disabled per `payment_collection.py:715` comment.

### 6.4 `db.invoices` (iter474 / iter475)

Contains the cached PDF invoice / receipt / statement records. Purely a document-caching layer — no financial semantic beyond `invoice_type` + `owner`.

---

## 7. Stripe Connect Architecture Findings

### 7.1 Destination charges vs separate transfers — which is used?

**Destination charges** are used everywhere:
- `create_destination_charge` (line 470–583) — Partner + general listings
- `create_connect_checkout_session` (`connect_payment_engine.py:326`) — parallel Connect helper (used by promotions + some legacy code paths)

**Separate transfers** are used for:
- Affiliate payouts (`connect_payment_engine.py::process_affiliate_payout`, line 833 `stripe.Transfer.create`)
- Manual admin payouts from `seller_payouts` queue (per PRD.md, not audited in this pass)

### 7.2 `application_fee_amount` semantics

- Partner (`calculate_partner_listing_checkout`): `application_fee_amount = platform_fee + fees_tax_total + processing_fee = $3 + $0.45 + $3.61 = $7.06`. BidVex retains $7.06 (which includes tax on its own $3 fee **and** the buyer-paid Stripe gross-up).
- Individual (`calculate_general_checkout`): `application_fee_amount = buyer_premium + seller_commission + fees_tax_total = $5 + $4 + $1.35 = $10.35`. BidVex retains $10.35. The Stripe processing gross-up ($3.49) is **NOT** included in application_fee. Instead, it's baked into the buyer's line item, and Stripe deducts its own rail cost from the connected account's transfer.

**Important — Stripe rail cost accounting under destination charges**:

In Stripe Connect destination charges, when `on_behalf_of` is not set (which is the case here — grep confirms no `on_behalf_of` param), **Stripe deducts its 2.9% + $0.30 rail fee from the platform's application_fee first, then transfers `charge − application_fee` to the connected account**. This means:
- Partner: BidVex nets `$7.06 − Stripe_fee_on_$114.06` = `$7.06 − ($114.06 × 0.029 + $0.30)` = `$7.06 − $3.61` = **$3.45**. Partner gets $114.06 − $7.06 = $107.00. But the user's rule says Partner should get $110 (hammer + Partner BP). **$3 shortfall from the Partner's expected net.**
- Individual: BidVex nets `$10.35 − $3.49` = **$6.86**. Seller receives `$96.00`. Buyer paid $109.84.

Actually — re-reading Stripe docs and the code — with `application_fee_amount` set and no `on_behalf_of`, the platform (BidVex) is charged Stripe's rail fee, NOT the connected account. The connected account receives `charge − application_fee` = **exactly** the transfer amount specified. So for the Partner scenario, the Partner Connect account receives `$114.06 − $7.06 = $107.00`.

**Partner nets $107.00**, but the user's business rule says Partner should net **$110** (hammer + Partner BP; then $3 BidVex fee owed separately).

**BidVex retains $7.06 in application_fee** (but pays Stripe's $3.61 rail fee out of it) → **net BidVex revenue = $3.45**, not $3. BidVex is over-retaining by $0.45 (the tax on its own $3 fee) — this is a place-of-supply issue: BidVex is de-facto collecting the tax on its BP from the buyer AND retaining it, when the buyer should not have paid this tax at all if the fee is owed by the Partner.

**Bottom line for Partner Stripe path**:
```
Buyer charged:                                     $114.06
├─ Partner gets (Stripe transfer):                  $107.00   ← user rule says $110
├─ BidVex gets (application_fee):                   $  7.06
│  ├─ BidVex owes Stripe (rail fee):                $  3.61   ← out of application_fee
│  └─ BidVex net revenue:                           $  3.45   ← user rule says $3.00
```

vs the user's expected model:
```
Buyer charged:                                     $110.00
├─ Partner nets:                                    $110.00   ← full amount
Partner owes BidVex (separate):                    $  3.90    ($3 + Stripe recovery + tax @ partner province)
├─ BidVex nets:                                     $  3.00
├─ Stripe rail on Partner's payment method:         $  0.39   (2.9% × $3 + $0.30, additive)
└─ Tax on BidVex fee (Partner remits at their prov):$  0.51
```

**Two very different economics.** The current live Partner Stripe checkout is BOTH overcharging the buyer AND under-paying the Partner AND (marginally) over-retaining at BidVex. 🔴

### 7.3 Are there paths where BidVex could accidentally collect the 3% twice?

Grep for `PARTNER_PLATFORM_FEE_RATE` and `Decimal("0.03")` across production code:
- `tax_engine.py:82` — the constant `PARTNER_PLATFORM_FEE_RATE = 0.03`
- `stripe_connect_service.py:383` — used in `calculate_partner_listing_checkout` (via `PARTNER_PLATFORM_FEE_RATE` imported from tax_engine)
- `fee_calculator.py:77` — `PARTNER_PLATFORM_RATE = 0.03` (separate constant, note the different name)
- `fee_calculator.py:1120` — `PARTNER_SELLER_COMMISSION_RATE = 0.03` (in PricingManager)
- `fee_calculator.py:1509` — `sc = _pm_round(hp * PARTNER_SELLER_COMMISSION_RATE)` (in `PricingManager.partner_auction`)

**Three separate constants** representing the same 3% (`PARTNER_PLATFORM_FEE_RATE`, `PARTNER_PLATFORM_RATE`, `PARTNER_SELLER_COMMISSION_RATE`). Each is used by a different code path:
- Live Stripe Session: `calculate_partner_listing_checkout` uses `tax_engine.PARTNER_PLATFORM_FEE_RATE`.
- Fee calc dispatcher `_iter350_partner`: uses `fee_calculator.PARTNER_PLATFORM_RATE`.
- Legacy `PricingManager.partner_auction` (used by `connect_payment_engine.calculate_connect_checkout` when `seller_is_partner=True`): uses `PARTNER_SELLER_COMMISSION_RATE`.

`connect_payment_engine.calculate_connect_checkout` and `create_connect_checkout_session` are ALSO Stripe session builders and ARE callable. They handle `seller_is_partner=True` (line 80, 142). If any route calls this instead of `calculate_partner_listing_checkout`, that's a THIRD Partner code path. Grep for `create_connect_checkout_session`:

```
backend/routes/payments_promotions.py: (yes — used for promotion checkout, not auction)
backend/services/vehicle_payment.py: (uses its own path)
```

`create_connect_checkout_session` is *not* wired to `POST /api/payments/checkout/auction`. So it's not the third Partner path today — but the "partner_auction" branch in `calculate_connect_checkout` (line 80-81) suggests it was intended to be. **Dead-ish code** — flagged for Phase 4.

### 7.4 Could the BidVex 3% be charged twice?

For a Partner listing settled via `create_auction_checkout`:
- `application_fee_amount = platform_fee + fees_tax + processing_fee = $7.06` → BidVex retains $7.06 out of the buyer's $114.06 charge.
- No second charge, no `Transfer.create`, no `application_fee.refund` — the Stripe destination charge is one-shot.
- **No, the 3% is charged once (as $3 inside the $7.06 application_fee).** However, it's charged to the BUYER's card, not to the PARTNER — that's the ownership violation.

### 7.5 Could the Partner accidentally pay the 3% twice?

For the live Partner Stripe checkout — no. The Partner receives `$114.06 − $7.06 = $107.00` (short of the expected $110 by exactly $3). So the Partner effectively pays the 3% once (embedded in the difference between $110 expected net and $107 actual net).

For the mythical Partner cash/e-transfer path (through `_iter350_partner`) — the Partner would owe `$3.90 = 3 + Stripe + tax` to BidVex, charged separately to their card on file. Buyer paid seller $110 offline. But this path is NOT reachable from `settle_auction` (finding #6), so it doesn't run in production today.

### 7.6 Could the buyer accidentally pay the 3% in addition to the 10% BP?

**YES.** This is the 🔴 finding. Buyer pays $10 (10% BP) + $3 (BidVex fee) + $0.45 (tax on $3 fee) + $3.61 (Stripe gross-up on all) = extra $4.06 above the user-expected $110.

---

## 8. Failed Payment & Retry Architecture

- `services/auction_settlement.py::mark_charge_failed` — writes a `payment_charges` row with `status="failed"`.
- `services/payment_collection.py` NO-PM branch — creates a Stripe Payment Link, emails buyer with 48-hour deadline.
- `services/scheduled_jobs.py` (not audited in detail — mentioned in imports) — presumably runs overdue detection.
- No automated retry queue. Failed charges are surfaced to admin via notification + email.

**Verdict**: Failed-payment path is 🟡 minimal but functional; no exponential-backoff retry, no automated card-updater flow.

---

## 9. Refund Architecture Findings

**Missing** in production code (0 grep hits in `/app/backend/services/` or `/app/backend/routes/`):
- `stripe.Refund.create` — no route creates refunds
- `stripe.Transfer.reverse` — no route reverses destination transfers
- `stripe.ApplicationFee.create_refund` — no route refunds application fees
- Partial refund logic
- Refund before/after transfer logic

**Existing** in test code only (`tests/*.py`) — proves the primitives are known but not wired.

**Verdict**: If a Partner buyer disputes a $114.06 charge:
- BidVex's Stripe Dashboard user would manually create the refund
- Stripe would reverse the destination charge and reclaim funds from the connected account
- BidVex's DB would have NO record of the refund event (no webhook handler for `charge.refunded` was found on quick scan — grep hit only in tests)

🟡 **Recommendation**: The refund path is a P0 gap. In the current Partner scenario where the buyer is OVERCHARGED $4.06 per sale, buyers will inevitably dispute. Without automated refund handling, every dispute becomes a manual admin+Stripe operation.

---

## 10. Legacy / Duplicate Code Discovery

| Location | Name | Purpose | Status |
|---|---|---|---|
| `services/fee_calculator.py::calculate_fee` | Dispatcher | iter350 canonical (per PRD) | Used by `settle_auction` (hardcoded to `individual`) — Partner branch effectively dead |
| `services/fee_calculator.py::_iter350_partner` | Partner-specific fee calc | Canonical partner economics per PRD | Dead — unreachable through `settle_auction` |
| `services/fee_calculator.py::_iter350_storage` | Storage-specific fee calc | iter443 model (facility SC=0) | Dead — unreachable through `settle_auction`, contradicted by `calculate_general_checkout` |
| `services/fee_calculator.py::_iter350_vehicle` | Vehicle-specific fee calc | | Dead — vehicles use `calculate_vehicle_checkout` |
| `services/fee_calculator.py::PricingManager` (class, line 1256+) | Legacy pricing engine | Used by `connect_payment_engine.py`, `vehicle_invoice.py`, several routes | Active — 8+ importers per PRD iter478 findings |
| `services/fee_calculation_engine.py` | Separate legacy engine | Exposed via `routes/payments_fees.py::/api/fees/v2/preview` | Active for API preview endpoint |
| `services/stripe_connect_service.py::calculate_partner_listing_checkout` | Live Partner Stripe path | Used by `POST /api/payments/checkout/auction` | Active — **CONTAINS THE 🔴 BUG** |
| `services/stripe_connect_service.py::calculate_general_checkout` | Live General Stripe path | Used by `POST /api/payments/checkout/auction` | Active |
| `services/stripe_connect_service.py::calculate_vehicle_checkout` | Live Vehicle Stripe path | Used by `POST /api/payments/checkout/auction` | Active |
| `services/connect_payment_engine.py::calculate_connect_checkout` | Parallel Stripe helper | Uses `PricingManager` | Active (used by promotions, some legacy) |
| `services/vehicle_pricing.py`, `services/storage_pricing.py` | Constants + tax helpers | Imported by PricingManager | Active |
| `services/broker_fee_engine.py` | Broker-specific fee | Used by `calculate_broker_transaction` in `fee_calculator.py` | Isolated — no Stripe wiring found for broker checkout |
| `services/vehicle_fee_service.py` | Vehicle-specific settlement | Used by `services/vehicle_payment.py` | Active |
| `services/category_rules.py::COMMISSION_RATES` | Category-specific SC | Grep says 0 consumers in settlement paths | Dead code |
| `services/pricing_config.py` (imported in `connect_payment_engine.py`) | Rate constants | Alternate source of truth | Active parallel to `fee_calculator.py` |

**Total distinct fee calculation entry points found**: 6 (`calculate_fee`, `calculate_general_checkout`, `calculate_vehicle_checkout`, `calculate_partner_listing_checkout`, `calculate_broker_transaction`, `calculate_connect_checkout`). They do NOT all produce the same numbers. This is the technical debt Phase 4 is meant to consolidate.

---

## 11. Frontend Displayed Amount vs Actual Charged Amount

**Not audited in this pass.** The Partner listing UI (frontend) may show a $110 total to the user (matching the user's business rule), but the backend charges $114.06 via Stripe. If frontend truly displays $110, this is **a P0 disclosure/consent issue** — buyer sees $110 in the UI but is charged $114.06 on their card. Consumer-protection risk (Loi Protection du Consommateur du Québec, articles 219, 224, 227 — misleading business practices).

**Recommendation**: Spot-check the checkout preview `GET /api/payments/checkout/preview/{listing_id}` for a Partner listing. If the frontend shows the `breakdown` object from that endpoint, then it *will* display $114.06 (correctly matching the actual charge), because `calculate_partner_listing_checkout` is the underlying function for both preview and charge. **NOT PROVABLE FROM STATIC CODE — requires UI screenshot verification.**

---

## 12. Final Decision Gate

**MOST IMPORTANT QUESTION**:

> For a Partner listing with $100 hammer + 10% Partner Buyer Premium, does the actual BidVex payment infrastructure charge the buyer $110 (+ applicable buyer taxes), while BidVex separately recovers its $3 platform fee from the Partner?

### ❌ NO — CONTRADICTED

**Proof chain**:
1. `POST /api/payments/checkout/auction` for a `is_partner_listing=True` listing calls `calculate_partner_listing_checkout()` at `routes/payments.py:897`.
2. `calculate_partner_listing_checkout(hammer=100, custom_buyer_premium_rate=0.10, partner_is_tax_registered=False)` computes `buyer_total_cents=11406` (proven by static replay in section 2.3 of this report).
3. `create_destination_charge(...breakdown)` passes `breakdown.buyer_total_cents=11406` into `stripe.checkout.Session.create(line_items=[{"unit_amount": 11406, "currency": "cad"}])` at `stripe_connect_service.py:534`.
4. Stripe therefore charges the buyer's card **$114.06 CAD**, not $110.00 CAD.
5. Stripe transfers `charge − application_fee = $114.06 − $7.06 = $107.00` to the Partner's Connect account (`transfer_data.destination` at line 546).
6. Partner nets **$107.00**, not $110.00.
7. BidVex retains `$7.06 − Stripe rail cost ($3.61) = $3.45` in application_fee, not $3.00.

### Answers to sub-questions A–G

| # | Question | Answer | Evidence |
|---|---|---|---|
| A | Is the Partner $100 / 10% example implemented correctly end-to-end? | ❌ NO | Section 2.3 |
| B | Does the buyer pay exactly $110 before applicable buyer-side taxes, and NOT $113? | ❌ NO — buyer pays **$114.06** | Section 2.3 |
| C | Is the $3 BidVex platform fee actually charged/owed by the Partner rather than the buyer? | ❌ NO — charged to buyer (embedded in `application_fee_amount` which is deducted from buyer's Stripe charge) | Section 2.3, Section 7.2 |
| D | Does 100% of the $10 Partner Buyer Premium belong to the Partner? | ⚠️ PARTIALLY — transfer_data destination is the Partner's Connect account, but the Partner nets only $107.00 (loses $3 to BidVex's 3% + rail cost) | Section 7.2 |
| E | Does BidVex recognize only its $3 platform fee as revenue from that fee component? | ❌ NO — BidVex retains $7.06 (= $3 + $0.45 fee tax + $3.61 Stripe gross-up). Net revenue after Stripe rail is $3.45, over-recognizing by $0.45. | Section 7.2 |
| F | Is the Stripe Connect transfer/application-fee structure consistent with A–E? | ❌ NO — it embeds BidVex's fee inside the buyer's charge instead of separating it | Section 7 |
| G | Is any production payment path currently violating A–F? | ❌ YES — `stripe_connect_service.calculate_partner_listing_checkout` (and its caller `POST /api/payments/checkout/auction`) violates all of A–F for every Partner Stripe checkout. | Section 2, Section 7 |

### RECOMMENDATION — DO NOT PROCEED TO PHASE 4

Repairs required BEFORE Phase 4 cleanup can be safely executed:

**P0 — Partner Stripe checkout redesign** (finding #1):
- Charge the buyer exactly `hammer + partner_buyer_premium (+ hammer_tax if partner is tax-registered + BP_tax if partner is tax-registered)` — do NOT include BidVex platform fee OR its tax OR its Stripe gross-up in the buyer's Stripe charge.
- Recover BidVex's $3 fee + $0.39 Stripe recovery + $0.51 tax = **$3.90** SEPARATELY from the Partner, either via:
  - **Option A**: `application_fee_amount=$3.90` on the buyer's PI (Stripe deducts from the Partner's destination transfer). Buyer's Stripe charge = $110.00. Partner Connect account receives $110.00 − $3.90 = $106.10. This *matches iter480 PRD's math*.
  - **Option B**: Full buyer charge of $110.00 to buyer's card (no destination charge). Partner receives their $10 BP + $100 hammer via a separate Transfer minus a $3.90 application_fee. More complex, more auditable.
  - **Option C**: Buyer pays $110.00 directly to Partner. BidVex separately debits Partner's Connect account for $3.90. Requires separate PaymentIntent on Partner's card.
- Coordinate with iter480 PRD's canonical fields so the new economics land in the same `bidvex_platform_fee_*` receipt columns.

**P0 — settle_auction hardcoded seller_account_type="individual"** (finding #6):
- If any Partner listing is *ever* settled through cash/e-transfer (a business decision), `settle_auction` must be updated to read `seller_account_type` from the seller's actual account_type (`users.subscription_tier == "partner"` → `"partner"`, plus `is_vehicle_dealer`, `is_storage_facility`, etc.). Otherwise, Partners settling via cash/e-transfer would be silently mis-billed as individual.

**P0 — Storage seller_commission conflict** (finding #8):
- Decide which is authoritative: iter443's `_iter350_storage` (SC=0, facility keeps 100% hammer) or `calculate_general_checkout` (4% SC deducted). One of them must be changed. This affects live storage settlements today.

**P1 — Partner hammer-tax rule** (Tax Audit, iter479 Q2):
- Decide: does BidVex tax hammer on the buyer's card when Partner is tax-registered (per `calculate_partner_listing_checkout`)? Or is hammer never taxed at BidVex (per `_iter350_partner`)? Business + tax-policy decision.

**P1 — Frontend disclosure** (Section 11):
- Verify the frontend displays the *actual* Stripe charge amount ($114.06 today) — if not, remedy immediately for consumer-protection compliance.

**P2 — Refund infrastructure** (finding #9):
- Build automated refund + transfer-reversal handlers before Partner sales scale. Currently a manual admin/Stripe Dashboard operation.

**P2 — Multi-lot / quantity for Partner Stripe checkout** (finding #12):
- `routes/payments.py:883` reads `listing.current_price` directly — verify this is always the multiplied total. If any Partner listing has a per-unit `current_price`, buyer is undercharged. Add `resolve_hammer_total` call inside `create_auction_checkout`.

---

## Appendix A — Files & Line Numbers Trace

| Line | File | What it does |
|---|---|---|
| `routes/payments.py:840` | `create_auction_checkout` FastAPI endpoint | Entry point for auction checkout |
| `routes/payments.py:885-916` | Partner branch | Calls `calculate_partner_listing_checkout` + `create_destination_charge` |
| `routes/payments.py:917-935` | Vehicle branch | Calls `calculate_vehicle_checkout` + `create_vehicle_payment_session` |
| `routes/payments.py:936-978` | General branch | Calls `calculate_general_checkout` + `create_destination_charge` |
| `stripe_connect_service.py:356-467` | `calculate_partner_listing_checkout` | 🔴 **The buggy function** |
| `stripe_connect_service.py:410` | `subtotal_before_processing = hammer + buyer_premium + total_tax` | Where BidVex's fee tax leaks into the buyer's base |
| `stripe_connect_service.py:414` | `gross_amount = _gross_up(subtotal_before_processing)` | Where the Stripe gross-up is applied to buyer's WHOLE base, not just BidVex's fee |
| `stripe_connect_service.py:420` | `buyer_total = gross_amount` | The final $114.06 charged |
| `stripe_connect_service.py:427` | `application_fee = platform_fee + fees_tax_total + processing_fee` | Where BidVex retains $7.06 |
| `stripe_connect_service.py:461` | `stripe_charge_amount_cents=_to_cents(buyer_total)` | Cents value passed to Stripe |
| `stripe_connect_service.py:528-566` | `create_destination_charge` — `stripe.checkout.Session.create` | The Stripe API call itself |
| `stripe_connect_service.py:544` | `application_fee_amount: breakdown.stripe_application_fee_cents` | BidVex retention |
| `stripe_connect_service.py:546` | `transfer_data.destination: seller_connect_account_id` | Partner Connect account |
| `fee_calculator.py:463-540` | `_iter350_partner` | The DEAD code path that produces $110 |
| `fee_calculator.py:493` | `buyer_total_charged=_r(hammer + partner_bp_revenue)` | Where the correct $110 is computed (unused in Stripe path) |
| `auction_settlement.py:256-267` | `calculate_fee(..., seller_account_type="individual", ...)` | Where seller_account_type is hardcoded (finding #6) |
| `auction_settlement.py:794-875` | `settle_auction` | Main settlement entry (never sees a Partner seller_type) |
| `payment_collection.py:514-523` | `issue_transaction_records(...itemized=itemized_block)` | Where the receipt gets persisted with iter480 Phase 3 fields |
| `receipts.py:36-61` | `ITEMIZED_KEYS` including `bidvex_platform_fee_*` | Persistence schema |

---

*End of AUDIT REPORT. Do not proceed to Phase 4 until the 🔴 findings above are reviewed and repairs authorized. See `BIDVEX_PAYMENT_INFRASTRUCTURE_SPECIFICATION.md` for the complete money-flow architecture.*
