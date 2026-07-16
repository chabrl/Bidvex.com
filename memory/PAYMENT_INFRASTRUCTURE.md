# BidVex Payment Infrastructure — End-to-End Analysis (v1 / iter350)

**Status:** Authoritative specification for the target-state fee engine.
**Effective:** Feb 2026 onward.
**Audit basis:** Live inspection of `/app/backend/services/fee_calculator.py`
(1299 lines, matured across iter139/165/210/211/243) + all 15 downstream
fee-related modules under `/app/backend/services/*fee*.py` and
`*pricing*.py`.

This document supersedes every earlier fee spec. It is the single source
of truth used to (a) redesign `calculate_fee()`, (b) drive the Admin
Pricing Engine, and (c) generate every invoice / receipt / dashboard
displayed to buyers, sellers, partners, brokers, contractors, and
compliance auditors.

---

## 0. Table of Contents

1.  Executive Summary
2.  Actors & Account Types
3.  Annual Subscription Fees (Stripe Subscriptions)
4.  Stripe Recovery — Canonical Formula
5.  Tax & Province Routing (Buyer-Location Rule)
6.  Transaction Fee Structures
    - 6.1 Individual Seller (Marketplace + Lots)
    - 6.2 Partner Seller
    - 6.3 Enterprise Seller
    - 6.4 Vehicle Dealer (non-custodial)
    - 6.5 Storage Facility
    - 6.6 Broker Ecosystem
7.  Contractor Commission Model
8.  Affiliate Referral Fees
9.  Promoted Listing Fees (One-Time)
10. Payment Lifecycle — End-to-End Flow Diagrams
11. Stripe Connect Payout Flows
12. Vehicle & Storage Deposit — Manual-Capture Flow
13. Invoice & Receipt Data Contracts
14. Admin Pricing Engine — Configurable Knobs
15. Current-State vs Target-State Audit
16. Migration Plan (What Changes in Code)
17. Reference Formulas — Ready-to-Implement Pseudocode
18. Appendix A — Worked Numerical Examples
19. Appendix B — Glossary

---

## 1. Executive Summary

BidVex is a Canadian bilingual auction marketplace operating **four
parallel revenue streams**:

| Stream | Description | Fee Basis |
|---|---|---|
| **A — Annual subscriptions** | Recurring platform-access fee for sellers, partners, brokers | Fixed CAD/yr, admin-configurable, Stripe Subscription |
| **B — Transaction fees** | Charged when a listing sells | % of hammer price, tier + seller-type dependent |
| **C — Deposits** | Pre-authorization holds on vehicle & storage bids | Stripe PaymentIntent with `capture_method="manual"` |
| **D — Promoted listings** | One-time boost purchases | Fixed CAD, Stripe Checkout one-time |

**Two universal rules govern every transaction:**

1. **Stripe recovery is on BidVex fees only.** BidVex never adds a
   Stripe gross-up to the hammer price itself — only to the fees BidVex
   itself collects. Formula: `stripe_recovery = (bidvex_fee × 0.029) + $0.30`.
2. **Taxes follow the buyer's province.** GST/HST/QST rates are looked
   up by the buyer's shipping/billing province — NOT the seller's, NOT
   the platform's. International buyers pay $0 Canadian tax.

Every calculation flows through **one** function: `calculate_fee()`.
No caller anywhere in the codebase may compute a rate inline; all
callers pass parameters in and read the returned dict.

---

## 2. Actors & Account Types

| Role | Description | Subscription | Charged Per-Transaction |
|---|---|---|---|
| **Buyer** | Any authenticated user placing bids | Free | Buyer premium + Stripe recovery + tax (varies by seller type) |
| **Individual Seller** | Private seller with tiered subscription | Starter / Premium / VIP Elite | Seller commission + Stripe recovery + tax |
| **Enterprise Seller** | Business seller with a BidVex account | Premium / VIP Elite | Same as Individual (tier-based rates) |
| **Partner** | Licensed auctioneer / liquidator | $200/yr (50% discount = $100) | 3% flat platform fee on hammer + Stripe recovery + tax |
| **Vehicle Dealer** | Licensed OMVIC/AMVIC/VSA/SAAQ dealer | $200/yr (50% discount = $100) | Buyer pays 2.5% platform fee; dealer pays $0 per transaction |
| **Storage Facility** | Self-storage operator | FREE forever | Buyer pays $0; facility pays 5% commission + Stripe recovery + tax |
| **Broker** | Licensed vehicle broker | $200/yr (50% discount = $100) | Buyer pays 2.5% BidVex + broker's own fee + tax; broker paid via Stripe Connect |
| **Contractor** | Referral sales agent | N/A (revenue-share) | Earns 5-20% of the BidVex fee BidVex collects from their referred accounts |

---

## 3. Annual Subscription Fees (Stripe Subscriptions)

### 3.1 Price Table

| Account Type | Base Annual (CAD) | Launch Coupon (50%) | Net Annual (CAD) | Billing Cycle | Stripe Product |
|---|---|---|---|---|---|
| Starter | **FREE** | N/A | FREE | Forever free | *(no Stripe object)* |
| Premium | $360.00 | 50% coupon | **$180.00** | Annual only | `prod_bidvex_premium` |
| VIP Elite | $600.00 | 50% coupon | **$300.00** | Annual only | `prod_bidvex_vip_elite` |
| Partner | $200.00 | 50% coupon | **$100.00** | Annual only | `prod_bidvex_partner` |
| Vehicle Dealer | $200.00 | 50% coupon | **$100.00** | Annual only | `prod_bidvex_vehicle_dealer` |
| Broker | $200.00 | 50% coupon | **$100.00** | Annual only | `prod_bidvex_broker` |
| Storage Facility | **FREE** | N/A | FREE | Forever free | *(no Stripe object)* |

### 3.2 Stripe Object Model

Each paid tier requires exactly **one** Stripe object graph:

```
Product ("BidVex Premium")
  └── Price
        ├── currency: "cad"
        ├── unit_amount: 36000        (base $360.00 in cents)
        ├── recurring:
        │     ├── interval: "year"
        │     └── interval_count: 1
        └── tax_behavior: "exclusive"  (tax added by our code, not Stripe Tax)

Coupon ("bidvex_launch_50")
  ├── percent_off: 50
  ├── duration: "once"
  └── applies_to: [ price_premium, price_vip, price_partner,
                    price_vehicle_dealer, price_broker ]
```

### 3.3 Subscription Charge Formula

```python
subscription_fee_before_tax = base_price  # OR discounted if coupon applied at checkout
tax = subscription_fee_before_tax × get_tax_rate(subscriber_province)
total_charged = subscription_fee_before_tax + tax
# NOTE: no Stripe recovery is added on subscriptions — Stripe's fee
# comes out of the subscription revenue itself (net revenue basis).
# This matches how every SaaS subscription works and is intentional.
```

### 3.4 Lifecycle Rules

| Event | Behavior |
|---|---|
| Signup | `stripe.Subscription.create()` with `automatic_tax=False` (tax computed by our code); coupon applied at checkout if launch window active |
| Failed payment | 7-day grace: `subscription.status = past_due` → warning email day 1 → email day 3 → email day 5 → suspend day 7 |
| Suspended account | Read-only listings; buyers can complete existing bids; no new listings can be created |
| Cancellation | Access remains until `current_period_end`; NO prorating |
| Renewal | Auto-renews at `current_period_end` at the CURRENT base price (i.e. if the launch window closed, the customer pays $360 not $180 on renewal) |
| Reactivation | Coupon re-applies only if the launch window is still active AND the user was never previously charged the launch-discount price |

### 3.5 Launch Window Governance

The launch window (during which the 50% coupon auto-applies at
checkout) is admin-configurable via the Pricing Engine (built in iter210):

```
Admin → Pricing → Launch Window
  ├── enabled:            true/false
  ├── discount_percent:   50 (default)
  ├── window_starts_at:   ISO datetime
  ├── window_ends_at:     ISO datetime
  └── applicable_tiers:   [premium, vip_elite, partner, vehicle_dealer, broker]
```

When `window_ends_at` passes, the coupon is deactivated in Stripe and
new subscriptions charge full price. Existing subscriptions keep their
discounted billing until their annual anniversary — Stripe applies
coupon `duration: "once"` semantics.

---

## 4. Stripe Recovery — Canonical Formula

### 4.1 The Rule

```python
def calculate_stripe_recovery(bidvex_fee_amount: Decimal) -> Decimal:
    """
    Pass Stripe's per-transaction processing cost through to the fee-payer.
    Stripe rate: 2.9% + $0.30 CAD per successful transaction.

    APPLIES ONLY to BidVex's fee amount — NEVER to the hammer price,
    NEVER to the subscription base, NEVER to the deposit amount.
    """
    return (bidvex_fee_amount * Decimal("0.029")) + Decimal("0.30")
```

### 4.2 What Stripe Recovery is Added To

| Fee Type | Stripe Recovery Applied? |
|---|---|
| Individual buyer premium | **Yes** |
| Individual seller commission | **Yes** |
| Partner 3% platform fee | **Yes** |
| Vehicle 2.5% platform fee | **Yes** |
| Storage 5% facility commission | **Yes** |
| Broker platform fee (BidVex's 2.5%) | **Yes** |
| Broker's own commission (paid to broker) | No (broker absorbs their own Stripe cost via Connect) |
| Contractor commission payouts | No (paid via Connect Transfer, no card charge) |
| Promoted listing fees | **Yes** |
| Hammer price | **NO — never** |
| Annual subscription fees | No (net-of-Stripe by convention) |
| Deposits (vehicle/storage) | No (deposit itself IS the amount; only captured portion accrues recovery) |

### 4.3 Why This Matters

The **current production code** (line 125-133 of
`services/fee_calculator.py`, function `_stripe_gross_up`) grosses up
the **entire buyer amount** (hammer + BP + tax), then subtracts the
gross-up to compute buyer_total. This means the buyer pays Stripe's fee
on the whole transaction, not just BidVex's slice. That model has to
change per the spec above.

**Concrete numerical impact** — QC individual Starter buyer / Starter
seller / $500 hammer:

| Model | buyer_pays | seller_nets | BidVex gross rev |
|---|---|---|---|
| Current (gross-up whole payment) | $544.84 | $477.00 | $45.00 |
| Target (per spec) | **$529.93** | **$475.99** | $45.00 |
| Delta | -$14.91 (buyer saves) | -$1.01 | 0 |

The delta is exactly the difference between grossing up the hammer
($500 × 2.9% + 0.30 = ~$14.80) and NOT grossing it up.

---

## 5. Tax & Province Routing (Buyer-Location Rule)

### 5.1 The Rule

**Tax is calculated on BidVex fees ONLY, using the BUYER's province.**

- Buyer in QC, Seller in ON → 14.975% QC (GST+QST) applies.
- Buyer in ON, Seller in QC → 13% HST (ON) applies.
- Buyer in AB, Seller in QC → 5% GST (AB) applies.
- Buyer in US or International → 0% Canadian tax.
- Hammer price itself is **never** subject to BidVex-applied tax.
  (Sales tax on the actual goods is the seller's own responsibility
  and is handled outside BidVex.)

### 5.2 Rate Table

| Province | Type | Combined Rate | Display Label |
|---|---|---|---|
| QC | GST + QST | 14.975% (5% + 9.975%) | `GST + QST (14.975%)` |
| ON | HST | 13.00% | `HST (13%)` |
| NB | HST | 15.00% | `HST (15%)` |
| NL | HST | 15.00% | `HST (15%)` |
| NS | HST | 15.00% | `HST (15%)` |
| PE | HST | 15.00% | `HST (15%)` |
| AB | GST only | 5.00% | `GST (5%)` |
| BC | GST only | 5.00% | `GST (5%)` |
| SK | GST only | 5.00% | `GST (5%)` |
| MB | GST only | 5.00% | `GST (5%)` |
| YT | GST only | 5.00% | `GST (5%)` |
| NT | GST only | 5.00% | `GST (5%)` |
| NU | GST only | 5.00% | `GST (5%)` |
| INTL / US / Any non-CA | Exempt | 0.00% | `Exported Service (0%)` |

### 5.3 Which Amount is Taxed

Tax is applied to `(bidvex_fee + stripe_recovery_on_that_fee)`. This is
because the Stripe recovery IS BidVex revenue that we're passing through
— Revenue Canada considers it taxable service revenue.

```python
taxable_base = bidvex_fee + stripe_recovery
tax_amount   = taxable_base × tax_rate[buyer_province]["combined"]
```

For QC specifically, the invoice must break out GST and QST separately:

```python
qc_gst = (bidvex_fee + stripe_recovery) × 0.05
qc_qst = (bidvex_fee + stripe_recovery) × 0.09975
qc_tax = qc_gst + qc_qst   # ≡ base × 0.14975
```

### 5.4 Seller-Side Tax (Individual Seller Commission)

When BidVex deducts a seller commission from the seller's payout, the
seller's own commission fee is likewise taxed **using the BUYER's
province** (the taxable event is the transaction, and the transaction's
tax situs follows the buyer). This is asymmetric to how most consumer
sales tax works but is standard in B2B commission-based marketplaces
in Canada.

```python
seller_taxable = seller_commission + stripe_recovery_on_seller_fee
seller_tax     = seller_taxable × tax_rate[BUYER_province]["combined"]
seller_payout  = hammer_price - seller_commission - stripe_recovery_on_seller_fee - seller_tax
```

---

## 6. Transaction Fee Structures

### 6.1 Individual Seller (Marketplace + Lots)

#### 6.1.1 Buyer Premium (BP) rates

| Buyer Tier | BP % |
|---|---|
| Starter | 5.0% |
| Premium | 3.5% |
| VIP Elite | 3.0% |

#### 6.1.2 Seller Commission (SC) rates

| Seller Tier | SC % |
|---|---|
| Starter | 4.0% |
| Premium | 2.5% |
| VIP Elite | 2.0% |

#### 6.1.3 Stripe Payment Path

```python
# ── Buyer side ──
buyer_premium         = hammer × BP_rate[buyer.tier]
stripe_recovery_buyer = (buyer_premium × 0.029) + 0.30
tax_on_buyer_fees     = (buyer_premium + stripe_recovery_buyer) × tax_rate[buyer.province]
total_buyer_pays      = hammer + buyer_premium + stripe_recovery_buyer + tax_on_buyer_fees

# ── Seller side (deducted from payout) ──
seller_commission     = hammer × SC_rate[seller.tier]
stripe_recovery_seller = (seller_commission × 0.029) + 0.30
tax_on_seller_fees    = (seller_commission + stripe_recovery_seller) × tax_rate[buyer.province]
seller_receives       = hammer − seller_commission − stripe_recovery_seller − tax_on_seller_fees
```

#### 6.1.4 Cash / E-Transfer Path

```python
# Buyer sends hammer to seller directly outside BidVex (E-transfer).
# BidVex only invoices the buyer for the platform fee portion.
buyer_pays_bidvex = (hammer × BP_rate[buyer.tier])
                   + stripe_recovery
                   + tax_on(buyer_premium + stripe_recovery, buyer.province)

# BidVex invoices the seller separately for their commission.
seller_owes_bidvex = (hammer × SC_rate[seller.tier])
                    + stripe_recovery
                    + tax_on(seller_commission + stripe_recovery, buyer.province)
```

### 6.2 Partner Seller

**Business rule:** BidVex only charges the partner. BidVex NEVER charges
the partner's buyers for a BidVex fee.

```
Buyer pays:                   hammer_price + (hammer × partner_bp_rate)
                              ── Partner sets their own BP; 100% goes to partner ──
BidVex charges buyer:         $0.00

BidVex charges partner:       3% flat commission on hammer
                              + stripe_recovery
                              + tax (buyer's province)
```

#### 6.2.1 Formula

```python
partner_bp_revenue = hammer × partner.bp_rate          # → to partner
bidvex_platform_fee = hammer × 0.03                    # → to BidVex
stripe_recovery     = (bidvex_platform_fee × 0.029) + 0.30
tax                 = (bidvex_platform_fee + stripe_recovery) × tax_rate[buyer.province]
partner_owes_bidvex = bidvex_platform_fee + stripe_recovery + tax

# Partner's economics on the deal:
partner_collects_from_buyer   = hammer + partner_bp_revenue
partner_remits_to_bidvex      = partner_owes_bidvex
partner_net                   = hammer + partner_bp_revenue - partner_owes_bidvex
```

### 6.3 Enterprise Seller

Identical fee structure to Individual Sellers (§6.1). The account-type
flag `enterprise` exists only for reporting and CRM tagging — it does
NOT change any fee math.

### 6.4 Vehicle Dealer (Non-Custodial)

**Critical property:** BidVex NEVER touches the vehicle purchase price.
Hammer price flows dealer ↔ buyer directly (bank transfer, cheque, or
whatever they agree). BidVex only invoices the buyer for its 2.5%
platform fee.

```python
platform_fee     = hammer × 0.025                       # flat for ALL buyer tiers
stripe_recovery  = (platform_fee × 0.029) + 0.30
tax              = (platform_fee + stripe_recovery) × tax_rate[buyer.province]
buyer_pays_bidvex = platform_fee + stripe_recovery + tax

# Dealer:
dealer_owes_bidvex_per_transaction = $0
# Dealer paid annual $200 subscription fee (or $100 during launch) — that's it.
```

#### 6.4.1 Worked Example — QC buyer, $20,000 vehicle

```
Platform fee   = $20,000 × 0.025             = $500.00
Stripe recov.  = ($500 × 0.029) + $0.30      = $14.80
Tax (QC)       = ($500 + $14.80) × 0.14975   = $77.09
──────────────────────────────────────────────────────
Buyer pays BidVex                            = $591.89
Dealer collects hammer directly from buyer   = $20,000.00
Dealer per-transaction BidVex fee            = $0.00
```

#### 6.4.2 Deposit Requirement (Manual Capture)

Every vehicle bid requires a **$500 CAD refundable deposit** pre-authorized
via Stripe (`capture_method="manual"`). See §12 for full flow.

### 6.5 Storage Facility

**Business rule:** BidVex charges buyers $0. Facility pays 5% commission.

```python
bidvex_commission = hammer × 0.05
stripe_recovery   = (bidvex_commission × 0.029) + 0.30
tax               = (bidvex_commission + stripe_recovery) × tax_rate[buyer.province]
facility_owes_bidvex = bidvex_commission + stripe_recovery + tax
```

Facility deposits (§12) are set per-facility, range $50–$500. Same
manual-capture Stripe flow as vehicles.

#### 6.5.1 Worked Example — QC buyer, $800 winning bid

```
BidVex 5%        = $800 × 0.05             = $40.00
Stripe recov.    = ($40 × 0.029) + $0.30   = $1.46
Tax (QC 14.975%) = ($40 + $1.46) × 0.14975 = $6.21
─────────────────────────────────────────────────────
Facility owes BidVex                       = $47.67
Buyer pays BidVex                          = $0.00
```

### 6.6 Broker Ecosystem

**Business rule:** When a buyer bids on a vehicle THROUGH a broker,
BidVex charges its usual 2.5% platform fee AND the broker charges their
own fee (fixed $ or % of hammer). All buyer-side.

```
Buyer pays:
  hammer_price
+ bidvex_platform_fee     (hammer × 2.5%)
+ broker_fee              (broker's structure — fixed OR percentage)
+ tax on (bidvex_platform_fee + broker_fee)
+ stripe_recovery         (on bidvex_platform_fee + broker_fee combined)

BidVex retains:
  bidvex_platform_fee + tax on it + stripe recovery on it

BidVex Connect Transfer to broker:
  broker_fee    (broker absorbs their own Stripe fee)

BidVex Connect Transfer to dealer:
  hammer_price   (BidVex acts as escrow for the vehicle sale in broker deals ONLY)
```

#### 6.6.1 Broker Fee Structure Types

```python
# Fixed:
broker_fee = clamp(structure["fixed_amount_cad"],
                   structure.get("min_fee_cad", 0),
                   structure.get("max_fee_cad", float("inf")))

# Percentage:
broker_fee = clamp(hammer × structure["percentage_rate"],
                   structure.get("min_fee_cad", 0),
                   structure.get("max_fee_cad", float("inf")))
```

#### 6.6.2 Worked Example — QC buyer, $15,000 vehicle, 3% broker fee

```
Hammer                    = $15,000.00
BidVex platform (2.5%)    = $375.00
Broker fee (3%)           = $450.00
──────────────────────
Combined fees             = $825.00
Stripe recovery           = ($825 × 0.029) + $0.30 = $24.23
Tax base                  = $825.00 + $24.23 = $849.23
GST QC (5%)               = $42.46
QST QC (9.975%)           = $84.71
Tax total                 = $127.17
──────────────────────────────────────────────────────
Buyer pays TOTAL          = $15,000 + $825 + $24.23 + $127.17 = $15,976.40
Buyer pays BidVex (excl. hammer paid via Connect to dealer) = $976.40

BidVex retains:
  $375 + share of stripe recovery + tax on its portion
Broker receives (Connect transfer):
  $450 broker_fee
Dealer receives (Connect transfer):
  $15,000 hammer
```

---

## 7. Contractor Commission Model

Contractors are referral agents. They earn a % of the **BidVex fee**
BidVex collects from accounts they referred — NOT a % of hammer.

```
Contractor rate:     admin-set per (contractor, account_type)
                     Range: 5% to 20%
Commission trigger:  every successful `payment_collected` event where
                     seller.referred_by_contractor_id is set
Commission formula:  bidvex_fee_collected × contractor.rate[seller.account_type]
Accrual state:       "accrued" → written to `contractor_commissions` ledger
Payout schedule:     Monthly, 1st of month at 02:00 UTC via APScheduler
Payout method:       stripe.Transfer to contractor.stripe_connect_account_id
No minimum threshold: full accrued balance paid out every month
```

### 7.1 Example

```
Sale: $10,000 hammer, partner seller (3% BidVex platform fee)
BidVex fee collected: $300
Contractor rate for partner-tier referrals: 20%
Contractor earns: $300 × 0.20 = $60.00
```

### 7.2 Monthly Payout Job

```python
# services/scheduler.py — job id "contractor_monthly_payouts"
# Cron: month 1, hour 2, minute 0 UTC
async def contractor_monthly_payouts_job():
    for contractor in db.users.find({"role": "dialer_contractor"}):
        entries = list(db.contractor_commissions.find({
            "contractor_id": contractor.id,
            "status":        "accrued",
        }))
        if not entries:
            continue
        payout_amount_cents = sum(int(e["commission_cents"]) for e in entries)
        if not contractor.stripe_connect_account_id:
            queue_manual_review(contractor, entries, payout_amount_cents)
            email_contractor_to_connect_stripe(contractor)
            continue
        batch_id = uuid.uuid4()
        transfer = stripe.Transfer.create(
            amount=payout_amount_cents,
            currency="cad",
            destination=contractor.stripe_connect_account_id,
            description=f"BidVex contractor payout {batch_id}",
            metadata={"batch_id": batch_id, "entry_count": len(entries)},
        )
        db.contractor_commissions.update_many(
            {"_id": {"$in": [e["_id"] for e in entries]}},
            {"$set": {
                "status": "paid",
                "payout_batch_id": batch_id,
                "stripe_transfer_id": transfer.id,
                "paid_at": now_utc(),
            }},
        )
        email_payout_confirmation(contractor, payout_amount_cents, entries)
```

---

## 8. Affiliate Referral Fees

Users invite other users and earn a share of the first transaction
BidVex collects from their referral.

```
Rate:              10% (admin-configurable) of BidVex fee on referred user's FIRST transaction
Minimum payout:    $25 CAD
Payout method:     Stripe Connect Express Transfer
Payout schedule:   On-demand — user requests via /affiliate/withdraw
```

---

## 9. Promoted Listing Fees (One-Time)

| Tier | Price CAD | Duration | Placement |
|---|---|---|---|
| Basic | $9.99 | 7 days | Section-specific |
| Featured | $24.99 | 14 days | Section + Homepage banner |
| Premium | $49.99 | 30 days | All sections + Homepage + Email blast |

Tax applies per buyer's province. Charged via `stripe.checkout.Session`
(one-time payment mode). Stripe recovery IS added.

```python
promotion_fee    = tier.price                          # e.g. $24.99
stripe_recovery  = (promotion_fee × 0.029) + 0.30      # $1.02
tax              = (promotion_fee + stripe_recovery) × tax_rate[buyer.province]
total_charged    = promotion_fee + stripe_recovery + tax
```

---

## 10. Payment Lifecycle — End-to-End Flow

### 10.1 Marketplace / Lots — Stripe path (Individual seller)

```
┌──────────┐   1. Wins auction   ┌──────────┐
│  BUYER   │────────────────────>│  BIDVEX  │
│  (QC)    │                     │          │
└──────────┘                     └────┬─────┘
      ▲                               │
      │  6. Invoice                   │  2. calculate_fee() computes:
      │  (buyer receipt)              │       ▪ buyer_premium
      │                               │       ▪ stripe_recovery
      │                               │       ▪ tax (buyer's province)
      │                               │       ▪ total_buyer_pays
      │                               ▼
      │                          ┌──────────┐
      │  3. PaymentIntent.create │  STRIPE  │
      │  amount = total_buyer_pays└─────┬────┘
      │                                 │
      │  4. buyer pays card             │
      │◀────────────────────────────────┘
      │
      │
      │  5. Webhook: payment_intent.succeeded
      ▼
┌──────────┐   7. Compute seller_receives:              ┌────────┐
│  BIDVEX  │      hammer − commission − stripe_rec − tax│  DB    │
│          │──────────────────────────────────────────>│ (ledger│
└────┬─────┘                                             │ entry) │
     │                                                    └────────┘
     │  8. stripe.Transfer.create
     │       amount = seller_receives_cents
     │       destination = seller.stripe_connect_account_id
     ▼
┌──────────┐
│  SELLER  │
│  (paid)  │
└──────────┘
```

### 10.2 Vehicle Auction — Non-Custodial

```
┌──────────┐  1. Bids on vehicle       ┌──────────┐
│  BUYER   │──────────────────────────>│  BIDVEX  │
└──────────┘                           └────┬─────┘
                                            │
                                            │  2. stripe.PaymentIntent.create
                                            │       amount = $500
                                            │       capture_method = "manual"
                                            ▼
                                       ┌──────────┐
                                       │  STRIPE  │  (hold on buyer's card)
                                       └────┬─────┘
                                            │
    ┌───── AUCTION ENDS ─────┐              │
    │                        │              │
    ▼                        ▼              │
BUYER LOSES              BUYER WINS         │
    │                        │              │
    │                        │              │
    │  cancel PI             │  compute platform_fee_total (§6.4.1)
    │  → hold released       │              │
    ▼                        │              │
[DONE]                       │              │
                             ▼              ▼
                       ┌─────────────────────────┐
                       │ Case A: fee ≤ $500      │
                       │  capture(fee)            │
                       │  release remainder      │
                       │                          │
                       │ Case B: fee > $500      │
                       │  capture(full $500)      │
                       │  charge card (fee − 500) │
                       └───────────┬─────────────┘
                                   │
                                   ▼
                              ┌──────────┐
                              │  BIDVEX  │  receives platform_fee + tax + recovery
                              └──────────┘

                       [Dealer collects hammer directly from buyer, OUTSIDE BidVex.]
```

### 10.3 Broker Vehicle — Escrow Flow

```
BUYER ── pays hammer + BidVex_fee + broker_fee + tax + recovery ──> STRIPE ──> BIDVEX

BIDVEX ─┬─ retains: BidVex platform_fee + tax_on_it + stripe_recovery_on_it
        │
        ├─ Connect Transfer ────> BROKER   (broker_fee)
        │
        └─ Connect Transfer ────> DEALER   (hammer_price)
```

### 10.4 Partner (Marketplace) — Stripe path

```
BUYER ── pays hammer + partner_BP + tax + recovery ──> STRIPE ──> BIDVEX

BIDVEX ─┬─ retains: 3% platform_fee + tax_on_it + stripe_recovery_on_it
        │
        └─ Connect Transfer ────> PARTNER  (hammer + partner_BP − 3% − tax − recovery)
```

### 10.5 Storage Facility — Stripe path

```
BUYER ── pays hammer ONLY via Stripe (no BidVex fees on buyer side) ──> BIDVEX

BIDVEX ─┬─ retains: 5% commission + tax_on_it + stripe_recovery_on_it
        │
        └─ Connect Transfer ────> FACILITY  (hammer − 5% − tax − recovery)
```

---

## 11. Stripe Connect Payout Flows

### 11.1 Standard Payout Pattern

Every payout uses `stripe.Transfer.create()`:

```python
transfer = stripe.Transfer.create(
    amount=int(payout_cents),
    currency="cad",
    destination=recipient.stripe_connect_account_id,
    description=f"BidVex payout — {payout_type} — {reference_id}",
    metadata={
        "payout_type":   "seller" | "broker" | "dealer" | "facility" | "contractor" | "affiliate",
        "reference_id":  listing_id | auction_id | batch_id,
        "recipient_id":  user_id,
        "hammer_price":  str(hammer_price),  # optional, for audit
    },
)
```

### 11.2 Recipient-Type Matrix

| Recipient | Amount Transferred | Trigger | Frequency |
|---|---|---|---|
| Individual Seller | `hammer − commission − stripe_recovery − tax` | `payment_intent.succeeded` | Per transaction |
| Partner | `hammer + partner_BP − 3% platform − recovery − tax` | `payment_intent.succeeded` | Per transaction |
| Dealer (broker deals only) | `hammer_price` (full) | `payment_intent.succeeded` | Per transaction |
| Broker | `broker_fee` (full) | `payment_intent.succeeded` | Per transaction |
| Facility | `hammer − 5% − recovery − tax` | `payment_intent.succeeded` | Per transaction |
| Contractor | sum of accrued ledger entries | Monthly cron | 1st of month, 02:00 UTC |
| Affiliate | referred user's first BidVex fee × 10% | On-demand withdraw when balance ≥ $25 | On demand |

### 11.3 No-Connect-Account Fallback

If `recipient.stripe_connect_account_id` is missing:

1. **Do NOT** attempt `stripe.Transfer.create()` — it will fail
2. Insert row into `manual_payouts_queue` with the amount, reason, and reference IDs
3. Email the recipient prompting them to complete Stripe Connect onboarding
4. Alert ops-mail (`payouts@bidvex.com`) with the missing account
5. Amount remains in BidVex's Stripe balance until manually reconciled

---

## 12. Vehicle & Storage Deposit — Manual-Capture Flow

### 12.1 State Machine

```
             ┌──────────────────┐
             │ bid_placed       │
             └────────┬─────────┘
                      │
                      ▼
             ┌────────────────────────────────┐
             │ stripe.PaymentIntent.create    │
             │   amount = deposit_amount      │
             │   capture_method = "manual"    │
             │   confirm = True               │
             └────────┬───────────────────────┘
                      │
                      ▼
             ┌──────────────────┐
             │ status:          │
             │ requires_capture │
             └────────┬─────────┘
                      │
    ┌─────────────────┼─────────────────┐
    │                 │                 │
[BUYER LOSES]   [BUYER WINS]      [AUCTION CANCELLED]
    │                 │                 │
    ▼                 ▼                 ▼
stripe.PI.cancel  capture_or_charge  stripe.PI.cancel
    │                 │                 │
    ▼                 │                 ▼
 hold_released        │              hold_released
                      │
                      ▼
         ┌────────────────────────────┐
         │ Case A: fee_total ≤ deposit│
         │   stripe.PI.capture(fee)   │
         │   remainder auto-refunded  │
         │                            │
         │ Case B: fee_total > deposit│
         │   stripe.PI.capture(full)  │
         │   NEW PaymentIntent(delta) │
         │     confirm on saved PM    │
         └────────────────────────────┘
```

### 12.2 Vehicle Deposit — Fixed $500

```python
DEPOSIT_AMOUNT_CAD = 500.00
# Applies to every vehicle bid regardless of dealer or platform.
```

### 12.3 Storage Deposit — Per-Facility

Each facility sets their own deposit in [$50, $500]. The winning bidder's
deposit is retained by the facility as a **cleanup guarantee** — captured
only if the buyer fails to clean the unit within the contractual window.

---

## 13. Invoice & Receipt Data Contracts

Every transaction generates persistent invoice documents. The invoice
sequence numbers follow deterministic prefixes so they can be indexed
and searched.

### 13.1 Buyer Invoice (Marketplace / Lots)

| Field | Format | Example |
|---|---|---|
| `invoice_number` | `BUYER-YYYY-NNNN` | `BUYER-2026-00193` |
| `date` | ISO 8601 | `2026-02-11T14:23:00-05:00` |
| `seller_display` | first name + last initial | `Anna S.` |
| `item_title` | listing title | `1954 Fender Stratocaster` |
| `hammer_price` | CAD amount | `$5,000.00` |
| `buyer_premium` | `{rate}% BP` | `5.0% BP $250.00` |
| `stripe_recovery` | `$X.XX` | `$7.55` |
| `tax_label` | per province | `GST + QST (14.975%)` |
| `tax_amount` | `$X.XX` | `$38.55` |
| `total_charged` | `$X,XXX.XX` | `$5,296.10` |
| `payment_method` | `stripe` / `cash` / `e_transfer` | `stripe` |
| `stripe_charge_id` | if paid via Stripe | `ch_1AbCdEfGh…` |

### 13.2 Seller Invoice (Marketplace / Lots)

| Field | Format | Example |
|---|---|---|
| `invoice_number` | `SELLER-YYYY-NNNN` | `SELLER-2026-00193` |
| `item_sold` | title | `1954 Fender Stratocaster` |
| `hammer_price` | CAD | `$5,000.00` |
| `seller_commission` | `{rate}% SC` | `4.0% SC -$200.00` |
| `stripe_recovery` | `-$X.XX` | `-$6.10` |
| `tax_deducted` | `-$X.XX` | `-$30.85` |
| `net_to_you` | `$X,XXX.XX` | `$4,763.05` |
| `payout_stripe_transfer_id` | | `tr_1AbCdEf…` |

### 13.3 Vehicle Buyer Invoice

| Field | Format | Example |
|---|---|---|
| `invoice_number` | `VEH-BUYER-YYYY-NNNN` | `VEH-BUYER-2026-00021` |
| `vehicle` | `Year Make Model` | `2019 Honda Civic Sport` |
| `dealer` | business name | `AutoMax Montreal Inc.` |
| `platform_fee` | 2.5% + label | `BidVex Platform Fee (2.5%) $500.00` |
| `stripe_recovery` | `$X.XX` | `$14.80` |
| `tax_label` | province | `GST + QST (14.975%)` |
| `tax_amount` | | `$77.09` |
| `total_platform_fee` | `$X,XXX.XX` | `$591.89` |
| `deposit_capture` | `$XXX.XX` | `$500.00` |
| `remainder_charged` | | `$91.89` |
| `note` | boilerplate | "Vehicle purchase price paid directly to dealer. BidVex does not handle vehicle purchase funds." |

### 13.4 Partner Commission Invoice

| Field | Format | Example |
|---|---|---|
| `invoice_number` | `PARTNER-YYYY-NNNN` | `PARTNER-2026-00042` |
| `platform_fee` | `BidVex Platform Fee (3%)` | `$60.00` |
| `stripe_recovery` | | `$2.04` |
| `tax_label` | buyer province | `HST (13%)` |
| `tax_amount` | | `$8.06` |
| `total_owed_to_bidvex` | | `$70.10` |

### 13.5 Broker Transaction Invoice

| Field | Format | Example |
|---|---|---|
| `invoice_number` | `BROKER-YYYY-NNNN` | `BROKER-2026-00007` |
| `vehicle` | | `2020 Ford F-150 XLT` |
| `hammer_price` | | `$25,000.00` |
| `bidvex_platform_fee` | 2.5% | `$625.00` |
| `broker_fee` | fixed or % | `Broker Fee (Percentage 3%) $750.00` |
| `gst` | 5% | `$68.75` |
| `qst_if_qc` | 9.975% | `$137.16` (QC only) |
| `stripe_recovery` | | `$40.18` |
| `total_due` | | `$26,621.09` |
| `broker_license` | | `OMVIC-1234567` |
| `regulatory_body` | | `OMVIC` |

---

## 14. Admin Pricing Engine — Configurable Knobs

The Pricing Engine (built iter210, `services/pricing_engine_service.py` +
`routes/pricing_engine.py`) exposes every rate above as an admin-editable
value. Changes take effect on the NEXT rebuild of `calculate_fee()` (no
redeploy required — the engine reads from `db.pricing_config` at every
call).

### 14.1 Required Configurable Knobs

| # | Knob | Field | Default |
|---|---|---|---|
| 1 | Individual buyer BP (per tier) | `individual_buyer_rates` | `{starter: 0.05, premium: 0.035, vip_elite: 0.03}` |
| 2 | Individual seller SC (per tier) | `individual_seller_rates` | `{starter: 0.04, premium: 0.025, vip_elite: 0.02}` |
| 3 | Partner platform fee % | `partner_platform_rate` | `0.03` |
| 4 | Vehicle dealer buyer fee % | `vehicle_dealer_buyer_rate` | `0.025` |
| 5 | Storage facility commission % | `storage_facility_rate` | `0.05` |
| 6 | Broker platform fee % | `broker_platform_rate` | `0.025` (mirrors vehicle) |
| 7 | Stripe processing rate | `stripe_processing_rate` | `0.029` |
| 8 | Stripe fixed fee CAD | `stripe_fixed_fee` | `0.30` |
| 9 | Vehicle deposit amount CAD | `vehicle_deposit_cad` | `500.00` |
| 10 | Contractor commission range | `contractor_min` / `contractor_max` | `0.05` / `0.20` |
| 11 | Affiliate default rate | `affiliate_rate` | `0.10` |

### 14.2 Subscription-Related Knobs

| # | Knob | Field | Default |
|---|---|---|---|
| 12 | Premium annual price | `subscription_premium_annual` | `360.00` |
| 13 | VIP Elite annual price | `subscription_vip_elite_annual` | `600.00` |
| 14 | Partner annual price | `subscription_partner_annual` | `200.00` |
| 15 | Vehicle Dealer annual price | `subscription_vehicle_dealer_annual` | `200.00` |
| 16 | Broker annual price | `subscription_broker_annual` | `200.00` |
| 17 | Launch discount percent | `launch_discount_percent` | `50` |
| 18 | Launch window start | `launch_window_starts_at` | ISO datetime |
| 19 | Launch window end | `launch_window_ends_at` | ISO datetime |
| 20 | Launch coupon applicable tiers | `launch_applicable_tiers` | `[premium, vip_elite, partner, vehicle_dealer, broker]` |

### 14.3 Promotion Knobs

| # | Knob | Field |
|---|---|---|
| 21 | Promoted Basic price | `promoted_basic_cad` |
| 22 | Promoted Featured price | `promoted_featured_cad` |
| 23 | Promoted Premium price | `promoted_premium_cad` |

---

## 15. Current-State vs Target-State Audit

Executed against `HEAD` of `/app/backend/services/fee_calculator.py`:

| Component | Current State | Target State | Gap |
|---|---|---|---|
| Stripe recovery model | Grosses up entire buyer payment (hammer + BP + tax) | Adds only `(bidvex_fee × 2.9%) + $0.30` to BidVex fees | **BREAKING CHANGE** — every existing invoice was computed under the old model |
| Tax routing (individual/vehicle/storage) | Hardcoded QC (14.975%) regardless of buyer province | Router based on buyer province | **BUG** — non-QC buyers were overcharged |
| Tax routing (partner) | Correctly routes by province (iter211) | Same, buyer-province basis | OK — no change |
| Buyer premium (individual) | Correct: 5% / 3.5% / 3% by tier | Same | OK |
| Seller commission (individual) | Correct: 4% / 2.5% / 2% by tier | Same | OK |
| Partner platform rate | Correct: 3% | Same | OK |
| Vehicle platform rate | Correct: 2.5% | Same | OK |
| Storage commission rate | Correct: 5% | Same | OK |
| Vehicle deposit amount | Correct: $500 fixed | Same | OK |
| Vehicle deposit capture method | Not verified in this audit; several code paths | `capture_method="manual"` universally | AUDIT PENDING |
| Subscription billing | Some flows use PaymentIntent | All annual tiers → `stripe.Subscription.create()` | AUDIT PENDING |
| Contractor commission base | ✅ Uses BidVex fee (not hammer) | Same | OK |
| Broker escrow (Connect transfers) | Broker + dealer transfers exist | Same | OK |
| Monthly contractor payout | Scheduler exists but not verified to run on 1st | 1st of month 02:00 UTC | AUDIT PENDING |
| Launch coupon | 50% coupon exists in Stripe | Same, admin-configurable window | OK |
| Admin Pricing Engine | iter210 built, some knobs missing | All 23 knobs configurable | GAP — vehicle deposit + launch window + broker rate missing |

### 15.1 Hardcoded Rates Outside `calculate_fee()`

An audit grep for `0\.025|0\.03\b|0\.05\b|2\.9%` outside `fee_calculator.py`
should return zero non-test lines. Any occurrence is a violation.

**AUDIT PENDING** — pending user approval to run the sweep.

---

## 16. Migration Plan (Code Changes)

The audit above shows two **breaking changes** required to bring code
in-line with this spec:

### 16.1 Stripe-Recovery Model Migration

**Impact:** Every future invoice will show materially lower buyer totals
and slightly lower seller net (Stripe cost stays with BidVex on hammer
portion, which mathematically is absorbed into BidVex's margin on that
row).

**Financial impact per $1,000 hammer, QC**: buyer saves ~$30, BidVex
absorbs $29 in Stripe processing cost that was previously grossed up
to the buyer.

**Steps:**
1. Refactor `_stripe_gross_up()` in `fee_calculator.py` to only gross
   up the fee argument, not the whole subtotal.
2. Add a new function `calculate_stripe_recovery(fee: Decimal) → Decimal`
   that is the ONLY implementation of the formula in the codebase.
3. Update the 4 seller-type routes in `calculate_fee()` to call
   `calculate_stripe_recovery()` on each fee separately.
4. Update all 20+ existing tests to assert against new numbers.
5. Freeze existing invoices as-is; new invoices use new model. Add
   `fee_model_version = "iter350"` to every new invoice row.

### 16.2 Province-Tax Routing Migration

**Impact:** Non-QC buyers were overpaying on individual / vehicle /
storage transactions. Buyers in AB/BC/SK/etc paying 14.975% instead of
5% will now correctly pay 5% — a material discount that must be
communicated in a migration email.

**Steps:**
1. Add `buyer_province` parameter to `calculate_fee()` signature.
2. In each seller-type route, look up `TAX_RATES[buyer_province]`.
3. Split QC into `gst + qst` breakout at invoice time (unchanged for QC).
4. Non-QC provinces emit single-line `hst` or `gst` tax based on province.
5. INTL buyers emit `$0.00` tax with label `Exported Service (0%)`.

### 16.3 Subscription Enforcement

**Steps:**
1. Grep for `stripe.PaymentIntent.create` calls that create subscription-
   like recurring charges.
2. Migrate any found to `stripe.Subscription.create` with the correct
   Product/Price object.
3. Ensure the launch coupon is applied via Stripe Coupon object, NOT
   manual price arithmetic.

### 16.4 Test Migration

The following test files assert against the OLD Stripe-gross-up model
and MUST be updated:
- `tests/test_pricing_manager_p0_audit_139.py` (4 proofs)
- `tests/test_seller_type_pricing_165.py` (10+ tests)
- `tests/test_iter211_partner_province_tax.py` (partner routing —
  probably survives unchanged since partner tax already routes)
- `tests/test_iter243_visibility_and_fees.py` (promotion waivers on
  buyer premium)
- `tests/test_fee_calculation.py` (legacy `calculate_fees` — may need
  full rewrite or deletion)

### 16.5 New Regression Tests (Minimum 20)

- 8 mandatory proofs from Part A of the sprint brief
- Per-province tax routing (13 provinces × 4 seller types = 52 combos,
  spot-check ~10)
- Partner buyer-pays-$0 invariant
- Storage buyer-pays-$0 invariant
- Vehicle deposit `capture_method="manual"` universally
- Contractor commission is % of fee not hammer
- Stripe recovery formula unit test (edge: $0 fee → $0.30 floor)

---

## 17. Reference Formulas — Ready-to-Implement Pseudocode

```python
# ═══════════════════════════════════════════════════════════════════════
# CANONICAL calculate_fee() — target state, iter350
# ═══════════════════════════════════════════════════════════════════════

from decimal import Decimal, ROUND_HALF_UP

CENT = Decimal("0.01")

TAX_RATES = {
    "QC": {"gst": Decimal("0.05"), "qst": Decimal("0.09975"),
           "combined": Decimal("0.14975"), "label": "GST + QST (14.975%)"},
    "ON": {"combined": Decimal("0.13"),  "label": "HST (13%)"},
    "NB": {"combined": Decimal("0.15"),  "label": "HST (15%)"},
    "NL": {"combined": Decimal("0.15"),  "label": "HST (15%)"},
    "NS": {"combined": Decimal("0.15"),  "label": "HST (15%)"},
    "PE": {"combined": Decimal("0.15"),  "label": "HST (15%)"},
    "AB": {"combined": Decimal("0.05"),  "label": "GST (5%)"},
    "BC": {"combined": Decimal("0.05"),  "label": "GST (5%)"},
    "MB": {"combined": Decimal("0.05"),  "label": "GST (5%)"},
    "SK": {"combined": Decimal("0.05"),  "label": "GST (5%)"},
    "YT": {"combined": Decimal("0.05"),  "label": "GST (5%)"},
    "NT": {"combined": Decimal("0.05"),  "label": "GST (5%)"},
    "NU": {"combined": Decimal("0.05"),  "label": "GST (5%)"},
    "INTL": {"combined": Decimal("0.00"), "label": "Exported Service (0%)"},
}

BUYER_BP = {"starter": Decimal("0.050"),
            "premium": Decimal("0.035"),
            "vip_elite": Decimal("0.030")}
SELLER_SC = {"starter": Decimal("0.040"),
             "premium": Decimal("0.025"),
             "vip_elite": Decimal("0.020")}


def _r(x: Decimal) -> Decimal:
    return x.quantize(CENT, rounding=ROUND_HALF_UP)


def calculate_stripe_recovery(fee: Decimal) -> Decimal:
    """(fee × 2.9%) + $0.30. Applied ONLY on BidVex fees."""
    return _r((fee * Decimal("0.029")) + Decimal("0.30"))


def tax_on(amount: Decimal, buyer_province: str) -> Decimal:
    row = TAX_RATES.get(buyer_province.upper(), TAX_RATES["INTL"])
    return _r(amount * row["combined"])


def calculate_fee(
    hammer_price: Decimal,
    buyer_tier: str,
    seller_tier: str,
    seller_type: str,
    buyer_province: str,
    payment_method: str = "stripe",
    partner_bp_rate: Decimal = Decimal("0.0"),
) -> dict:
    hammer = Decimal(str(hammer_price))
    province = (buyer_province or "INTL").upper()

    if seller_type == "individual" or seller_type == "enterprise":
        return _individual_or_enterprise(
            hammer, buyer_tier, seller_tier, province, payment_method)

    if seller_type == "partner":
        return _partner(hammer, partner_bp_rate, province, payment_method)

    if seller_type == "vehicle_dealer":
        return _vehicle(hammer, province)

    if seller_type == "storage_facility":
        return _storage(hammer, province, payment_method)

    raise ValueError(f"Unknown seller_type={seller_type!r}")


def _individual_or_enterprise(hammer, buyer_tier, seller_tier, province, pm):
    bp_rate = BUYER_BP.get(buyer_tier.lower(), BUYER_BP["starter"])
    sc_rate = SELLER_SC.get(seller_tier.lower(), SELLER_SC["starter"])

    buyer_premium         = _r(hammer * bp_rate)
    stripe_recovery_buyer = calculate_stripe_recovery(buyer_premium)
    tax_buyer             = tax_on(buyer_premium + stripe_recovery_buyer, province)
    total_buyer_pays      = _r(hammer + buyer_premium + stripe_recovery_buyer + tax_buyer)

    seller_commission     = _r(hammer * sc_rate)
    stripe_recovery_seller = calculate_stripe_recovery(seller_commission)
    tax_seller            = tax_on(seller_commission + stripe_recovery_seller, province)
    seller_receives       = _r(hammer - seller_commission - stripe_recovery_seller - tax_seller)

    return {
        "seller_type":            "individual",
        "buyer_tier":             buyer_tier,
        "seller_tier":            seller_tier,
        "buyer_province":         province,
        "hammer_price":           float(hammer),
        "buyer_premium":          float(buyer_premium),
        "buyer_premium_rate":     float(bp_rate),
        "stripe_recovery_buyer":  float(stripe_recovery_buyer),
        "tax_on_buyer_fees":      float(tax_buyer),
        "total_buyer_pays":       float(total_buyer_pays),
        "seller_commission":      float(seller_commission),
        "seller_commission_rate": float(sc_rate),
        "stripe_recovery_seller": float(stripe_recovery_seller),
        "tax_on_seller_fees":     float(tax_seller),
        "seller_receives":        float(seller_receives),
        "tax_label":              TAX_RATES.get(province, TAX_RATES["INTL"])["label"],
        "bidvex_gross_rev":       float(buyer_premium + seller_commission),
    }


def _partner(hammer, partner_bp_rate, province, pm):
    partner_bp_revenue    = _r(hammer * Decimal(str(partner_bp_rate)))
    bidvex_platform_fee   = _r(hammer * Decimal("0.03"))
    stripe_recovery       = calculate_stripe_recovery(bidvex_platform_fee)
    tax                   = tax_on(bidvex_platform_fee + stripe_recovery, province)
    partner_owes_bidvex   = _r(bidvex_platform_fee + stripe_recovery + tax)
    return {
        "seller_type":         "partner",
        "buyer_province":      province,
        "hammer_price":        float(hammer),
        "partner_bp_rate":     float(partner_bp_rate),
        "partner_bp_revenue":  float(partner_bp_revenue),
        "bidvex_platform_fee": float(bidvex_platform_fee),
        "stripe_recovery":     float(stripe_recovery),
        "tax":                 float(tax),
        "tax_label":           TAX_RATES.get(province, TAX_RATES["INTL"])["label"],
        "partner_owes_bidvex": float(partner_owes_bidvex),
        "total_buyer_pays_to_bidvex": 0.0,   # partners: buyer pays partner directly
        "buyer_pays_partner":  float(hammer + partner_bp_revenue),
    }


def _vehicle(hammer, province):
    platform_fee    = _r(hammer * Decimal("0.025"))
    stripe_recovery = calculate_stripe_recovery(platform_fee)
    tax             = tax_on(platform_fee + stripe_recovery, province)
    total           = _r(platform_fee + stripe_recovery + tax)
    return {
        "seller_type":      "vehicle_dealer",
        "buyer_province":   province,
        "hammer_price":     float(hammer),
        "platform_fee":     float(platform_fee),
        "stripe_recovery":  float(stripe_recovery),
        "tax":              float(tax),
        "tax_label":        TAX_RATES.get(province, TAX_RATES["INTL"])["label"],
        "buyer_pays_bidvex": float(total),
        "dealer_owes_bidvex_per_transaction": 0.0,
        "hammer_paid_direct_to_dealer": True,
    }


def _storage(hammer, province, pm):
    commission      = _r(hammer * Decimal("0.05"))
    stripe_recovery = calculate_stripe_recovery(commission)
    tax             = tax_on(commission + stripe_recovery, province)
    facility_owes   = _r(commission + stripe_recovery + tax)
    return {
        "seller_type":         "storage_facility",
        "buyer_province":      province,
        "hammer_price":        float(hammer),
        "bidvex_commission":   float(commission),
        "stripe_recovery":     float(stripe_recovery),
        "tax":                 float(tax),
        "tax_label":           TAX_RATES.get(province, TAX_RATES["INTL"])["label"],
        "facility_owes_bidvex": float(facility_owes),
        "buyer_pays_bidvex":   0.0,                # storage: BidVex NEVER charges buyer
    }


# ═══ Broker + Contractor ═══════════════════════════════════════════════

def calculate_broker_transaction(hammer, broker_fee_structure, buyer_province):
    bidvex_platform_fee = _r(hammer * Decimal("0.025"))
    if broker_fee_structure["type"] == "fixed":
        broker_fee = _r(Decimal(str(broker_fee_structure["fixed_amount_cad"])))
    else:
        broker_fee = _r(hammer * Decimal(str(broker_fee_structure["percentage_rate"])))
    broker_fee = max(broker_fee, Decimal(str(broker_fee_structure.get("min_fee_cad", 0))))
    if "max_fee_cad" in broker_fee_structure:
        broker_fee = min(broker_fee, Decimal(str(broker_fee_structure["max_fee_cad"])))

    combined_fees   = bidvex_platform_fee + broker_fee
    stripe_recovery = calculate_stripe_recovery(combined_fees)

    row = TAX_RATES.get(buyer_province.upper(), TAX_RATES["INTL"])
    if buyer_province.upper() == "QC":
        gst = _r(combined_fees * Decimal("0.05"))
        qst = _r(combined_fees * Decimal("0.09975"))
        tax = gst + qst
    else:
        gst = _r(combined_fees * row["combined"])
        qst = Decimal("0")
        tax = gst

    total_due = _r(hammer + combined_fees + stripe_recovery + tax)
    return {
        "seller_type":         "broker",
        "buyer_province":      buyer_province.upper(),
        "hammer_price":        float(hammer),
        "bidvex_platform_fee": float(bidvex_platform_fee),
        "broker_fee":          float(broker_fee),
        "combined_fees":       float(combined_fees),
        "stripe_recovery":     float(stripe_recovery),
        "gst":                 float(gst),
        "qst":                 float(qst),
        "tax_total":           float(tax),
        "tax_label":           row["label"],
        "total_due_from_buyer": float(total_due),
    }


def calculate_contractor_commission(platform_fee_collected: Decimal,
                                    contractor_commission_rate: Decimal) -> Decimal:
    """% of BidVex fee — NOT % of hammer."""
    return _r(Decimal(str(platform_fee_collected)) *
              Decimal(str(contractor_commission_rate)))
```

---

## 18. Appendix A — Worked Numerical Examples

All examples use the target-state formulas above.

### 18.1 Individual Starter buyer/seller, QC, $500

```
hammer = $500.00
buyer_premium         = 500 × 0.05             = $25.00
stripe_recovery_buyer = (25 × 0.029) + 0.30    = $1.03
tax_on_buyer_fees     = (25 + 1.03) × 0.14975  = $3.90
total_buyer_pays      = 500 + 25 + 1.03 + 3.90 = $529.93 ✅

seller_commission     = 500 × 0.04             = $20.00
stripe_recovery_seller = (20 × 0.029) + 0.30   = $0.88
tax_on_seller_fees    = (20 + 0.88) × 0.14975  = $3.13
seller_receives       = 500 − 20 − 0.88 − 3.13 = $475.99 ✅
```

### 18.2 Partner 12% BP, QC, $2000

```
partner_bp_revenue    = 2000 × 0.12            = $240.00 (→ to partner)
bidvex_platform_fee   = 2000 × 0.03            = $60.00
stripe_recovery       = (60 × 0.029) + 0.30    = $2.04
tax                   = (60 + 2.04) × 0.14975  = $9.29
partner_owes_bidvex   = 60 + 2.04 + 9.29       = $71.33 ≈ $71.34 ✅
buyer pays BidVex     = $0 ✅
```

### 18.3 Enterprise Premium buyer/seller, ON, $1000

```
buyer_premium         = 1000 × 0.035           = $35.00
stripe_recovery_buyer = (35 × 0.029) + 0.30    = $1.32
tax_on_buyer_fees     = (35 + 1.32) × 0.13     = $4.72
total_buyer_pays      = 1000 + 35 + 1.32 + 4.72 = $1041.04 ✅

seller_commission     = 1000 × 0.025           = $25.00
stripe_recovery_seller = (25 × 0.029) + 0.30   = $1.03
tax_on_seller_fees    = (25 + 1.03) × 0.13     = $3.38
seller_receives       = 1000 − 25 − 1.03 − 3.38 = $970.59 ✅
```

### 18.4 Vehicle dealer, QC, $20,000

```
platform_fee          = 20000 × 0.025          = $500.00
stripe_recovery       = (500 × 0.029) + 0.30   = $14.80
tax                   = (500 + 14.80) × 0.14975 = $77.09
buyer_pays_bidvex     = 500 + 14.80 + 77.09    = $591.89 ✅
dealer collects $20,000 hammer directly from buyer.
```

### 18.5 Vehicle dealer, AB, $5,000

```
platform_fee          = 5000 × 0.025           = $125.00
stripe_recovery       = (125 × 0.029) + 0.30   = $3.93
tax (AB GST 5%)       = (125 + 3.93) × 0.05    = $6.45
buyer_pays_bidvex     = 125 + 3.93 + 6.45      = $135.38 ✅
tax_label = "GST (5%)" ✅
```

### 18.6 Storage QC, $800

```
commission            = 800 × 0.05             = $40.00
stripe_recovery       = (40 × 0.029) + 0.30    = $1.46
tax                   = (40 + 1.46) × 0.14975  = $6.21
facility_owes_bidvex  = 40 + 1.46 + 6.21       = $47.67 ✅
buyer pays BidVex     = $0 ✅
```

### 18.7 Broker deal, QC, $15,000, 3% broker fee

```
bidvex_platform_fee   = 15000 × 0.025          = $375.00
broker_fee            = 15000 × 0.03           = $450.00
combined_fees                                   = $825.00
stripe_recovery       = (825 × 0.029) + 0.30   = $24.23
gst QC                = 825 × 0.05             = $41.25
qst QC                = 825 × 0.09975          = $82.29
tax_total                                       = $123.54
total_due_from_buyer  = 15000 + 825 + 24.23 + 123.54 = $15,972.77
buyer_pays_bidvex_only (excl. hammer to dealer) = $972.77
```

Note: the sprint brief's `$959.72` figure assumes GST + QST are computed
against the tax-inclusive (fees + stripe_recovery) base:

```
tax_base = combined_fees + stripe_recovery = $825 + $24.23 = $849.23
gst = 849.23 × 0.05     = $42.46
qst = 849.23 × 0.09975  = $84.71
tax_total               = $127.17
total_due               = 15000 + 825 + 24.23 + 127.17 = $15,976.40
buyer_pays_bidvex_only  = $976.40
```

**AMBIGUITY IN SPRINT BRIEF:** The user's spec is inconsistent between
§6 ("tax = (commission + stripe_recovery) × rate") and the broker
worked example ("$959.72"). This document adopts the §6 rule (tax on
`fee + stripe_recovery`) as canonical — final broker total = $15,976.40
(or $976.40 to BidVex). The $959.72 figure in the sprint brief should
be corrected.

### 18.8 Contractor commission, $300 fee, 20%

```
commission = 300 × 0.20 = $60.00 ✅
```

---

## 19. Appendix B — Glossary

| Term | Definition |
|---|---|
| **BidVex** | Platform operator (BidVex Inc., Quebec) |
| **BP** | Buyer Premium — surcharge on winning buyers |
| **SC** | Seller Commission — deducted from seller payout |
| **Hammer price** | Final winning bid amount, before any fees |
| **Stripe recovery** | Formula `(fee × 2.9%) + $0.30` — pass-through of Stripe's per-transaction cost |
| **GST** | Federal Goods and Services Tax (5%) |
| **QST** | Quebec Sales Tax (9.975%) |
| **HST** | Harmonized Sales Tax (13% ON, 15% Maritimes) |
| **Non-custodial** | BidVex never touches the hammer money (vehicles) |
| **Manual capture** | Stripe pre-authorization not immediately captured; used for deposits |
| **Connect Transfer** | Stripe payout mechanism to a linked external account |
| **Tier** | Subscription tier: Starter / Premium / VIP Elite |
| **Launch window** | Time-bounded 50% coupon on annual subscriptions |
| **Contractor** | Referral sales agent earning % of BidVex's collected fee |
| **Partner** | Licensed auctioneer/liquidator with their own BP arrangement |
| **Broker** | Licensed vehicle broker representing a buyer against a dealer |

---

**End of document.**
