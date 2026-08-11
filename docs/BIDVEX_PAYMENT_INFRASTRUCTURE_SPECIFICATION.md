# BIDVEX PAYMENT INFRASTRUCTURE SPECIFICATION

**Document version**: 1.0 (Feb 12, 2026)
**Status**: **AS-IS description of live production code**, NOT the target/desired specification. Where the code contradicts the user's stated business rule, both are documented and the delta is flagged 🔴. This is a READ-ONLY audit output — no fixes have been applied.
**Companion document**: `BIDVEX_PAYMENT_AUDIT_REPORT.md` (list of 🟢/🟡/🔴 findings).

---

## 1. Executive Summary

BidVex's payment infrastructure has **6 independent fee-calculation entry points** and **5 distinct Stripe Session builders** distributed across 4 backend services. Each entry point produces different economic outcomes for the same input. There is no single source of truth in production today; the iter478/479/480 fee-schedule work introduced *one more* module (`services/fee_schedule.py`) but explicitly *without* wiring it to any live calculation path (per Phase 1 contract).

The user's authoritative business rule for a Partner listing is:

> Hammer + Partner Buyer Premium is the *only* thing charged to the buyer's card. BidVex's 3% platform fee is a Partner obligation, collected via Stripe Connect application-fee mechanics that don't touch the buyer's line-item total.

**The live production Partner Stripe path does not implement this rule.** See `BIDVEX_PAYMENT_AUDIT_REPORT.md` §2 for proof.

## 2. Business Fee Model (as understood from user directives)

| Seller Type | Buyer Premium (belongs to) | Seller Commission | Platform Fee (BidVex) | Stripe Recovery | Notes |
|---|---|---|---|---|---|
| Individual — standard | 5% (BidVex) | 4% (BidVex) | included in BP | additive on BidVex fees | Two BidVex revenues sourced from same sale |
| Individual — premium | 3.5% (BidVex) | 2.5% (BidVex) | ” | ” | Subscription discount |
| Individual — VIP Elite | 3% (BidVex) | 2% (BidVex) | ” | ” | Highest tier |
| Enterprise | mirrors Individual (per fee_schedule) | mirrors Individual | ” | ” | |
| Partner (default) | 5% or custom per listing (**Partner keeps 100%**) | 0 | 3% of hammer (owed by Partner) | additive on 3% only | User's canonical rule |
| Partner Pro | 3.75% default (Partner keeps 100%) | 3% | matches PricingManager | additive on 3% only | Per fee_schedule (no live checkout path exists — see §4) |
| Vehicle Dealer | 5% (BidVex) — buyer tier | 0 (dealer keeps full hammer) | 2.5% of hammer (BidVex) | additive on `BP + platform_fee` | Hammer paid offline (bank draft) |
| Storage Facility | **5% forced** (BidVex) | 0 (facility keeps full hammer, per iter443) | 5% BP = platform revenue | additive on BP | Iter443 rule |
| Broker | Broker's own custom fee (Broker) | 0 | 2.5% (BidVex) | additive on combined fees | Buyer bears both fees; broker fee is passed through |

## 3. Money Ownership Model

| Component | Owner | Purpose |
|---|---|---|
| `hammer_price` | Seller (or Partner) | Merchandise total |
| `buyer_premium` (Individual/Enterprise/Vehicle/Storage) | BidVex | Platform revenue |
| `buyer_premium` (Partner) | **Partner (100%)** | Auctioneer's fee |
| `seller_commission` (Individual/Enterprise) | BidVex | Platform revenue on seller side |
| `platform_fee` (Partner) | BidVex | 3% of hammer — Partner's obligation |
| `platform_fee` (Vehicle) | BidVex | 2.5% of hammer — buyer's obligation |
| `stripe_recovery` | Recovers Stripe's rail cost | Whichever party bears the fee |
| `taxes` | Ultimately CRA / RQ | Collected at point of sale |
| `application_fee_amount` (Stripe Connect) | BidVex | Retained during destination charge |
| `transfer_data.destination` | Seller / Partner | Connected account receiving `charge − application_fee` |

## 4. Payment Flow — Reference Architecture

### 4.1 High-level actors

```
┌─────────┐          ┌────────────────────────────────┐          ┌────────────┐
│  Buyer  │─payment─▶│ BidVex platform (Stripe        │──payout─▶│ Seller /   │
│         │          │ Connect destination charges)   │          │ Partner /  │
└─────────┘          │                                 │          │ Facility   │
                     │  application_fee_amount → BidVex│          └────────────┘
                     └──────────────┬──────────────────┘
                                    │
                                    │ rail fee 2.9% + $0.30
                                    ▼
                                 ┌───────┐
                                 │Stripe │
                                 │       │
                                 └───────┘
```

### 4.2 Partner Listing Money Flow (AS-IS, live code)

```
Buyer clicks "Pay" in checkout page
         │
         ▼
  POST /api/payments/checkout/auction  (routes/payments.py:840)
         │
         ▼
  is_partner_listing == True  →  branch line 885
         │
         ▼
  breakdown = calculate_partner_listing_checkout(
      hammer_price = listing.current_price,
      custom_buyer_premium_rate = listing.custom_buyer_premium_rate or 0.0,
      partner_is_tax_registered = seller.is_tax_registered,
      include_processing_fee = True,
  )
  (stripe_connect_service.py:356-467)
         │
         │   For hammer=$100, BP_rate=10%, partner NOT registered:
         │     buyer_premium         = $10.00
         │     platform_fee          = $3.00
         │     fees_tax_total        = $0.45  (14.975% × $3)
         │     subtotal_before_proc  = $110.45
         │     gross_amount          = $114.06
         │     processing_fee        = $3.61
         │     buyer_total_cents     = 11406
         │     application_fee_cents = 706   ($7.06)
         │     transfer_amount       = $110.00  (metadata only)
         │
         ▼
  result = create_destination_charge(
      db, listing_id, buyer_id, breakdown, return_url, seller_connect_account_id,
  )
  (stripe_connect_service.py:470-583)
         │
         ▼
  stripe.checkout.Session.create(
      customer = customer_id,
      payment_method_types = ["card"],
      mode = "payment",
      line_items = [{ "unit_amount": 11406, ... }],       ← $114.06 CAD charged
      payment_intent_data = {
          "application_fee_amount": 706,                   ← $7.06 retained by BidVex
          "transfer_data": { "destination": seller_connect_account_id },
          "metadata": {...},
      },
      ...
  )
         │
         ▼
  Buyer redirected to Stripe Checkout URL → pays $114.06 with card
         │
         ▼
  Stripe webhook: checkout.session.completed
         │
         │   [webhook handler location not audited in detail in this pass]
         │
         ▼
  On success:
    • Stripe retains 2.9%+$0.30 = ~$3.61 rail fee from platform (BidVex)
    • BidVex receives:  application_fee $7.06 − rail $3.61 = **$3.45 net revenue**
    • Partner Connect account receives: $114.06 − $7.06 = **$107.00**
    • DB writes:
        db.pending_payments  → status: succeeded
        db.transactions      → new row with pickup_code (payment_collection._ensure_stripe_pickup_code)
        db.receipts          → buyer_receipt row (via issue_transaction_records)
        db.receipts          → seller_statement row
        db.seller_payouts    → (payout_pending queue if not auto-transferred)
```

**Comparison to expected model** (per user directive):
| Field | Actual | Expected | Delta |
|---|---|---|---|
| Buyer charged | $114.06 | $110.00 | +$4.06 🔴 |
| Partner net | $107.00 | $110.00 (then owes BidVex $3.90 separately) | -$3.00 🔴 |
| BidVex net | $3.45 | $3.00 | +$0.45 🔴 |

### 4.3 Individual/Enterprise Listing Money Flow (AS-IS)

```
POST /api/payments/checkout/auction  →  general branch line 936
         ▼
  breakdown = calculate_general_checkout(
      hammer_price, buyer_tier, seller_tier,
      seller_is_tax_registered = seller.is_tax_registered,
      include_processing_fee = True,
      custom_buyer_premium_rate = listing_bp_override,
  )
  (stripe_connect_service.py:133-262)
         │
         │   For hammer=$100, buyer=basic (5%), seller=basic (4%), QC, seller NOT registered:
         │     buyer_premium      = $5.00
         │     seller_commission  = $4.00
         │     bidvex_fees_sub    = $9.00
         │     fees_tax           = $1.35  (14.975% × $9)
         │     sub_before_proc    = $106.35
         │     gross_amount       = $109.84
         │     processing_fee     = $3.49
         │     buyer_total_cents  = 10984
         │     application_fee_cents = 1035  ($10.35 retained by BidVex)
         │     transfer_amount    = $96.00
         │
         ▼
  stripe.checkout.Session.create(...) — same shape as Partner path
         ▼
  Buyer pays $109.84
  Seller Connect account receives $96.00
  BidVex retains $10.35 − rail $3.49 = $6.86 net
```

### 4.4 Vehicle Money Flow (Two-Rail)

```
Rail 1 (Stripe): BidVex fees only
─────────────────────────────────
POST /api/payments/checkout/auction  →  vehicle branch line 917
         ▼
  breakdown = calculate_vehicle_checkout(hammer, buyer_tier)
         │
         │   For hammer=$100, buyer=basic:
         │     buyer_premium (5%) = $5.00
         │     platform_fee (2.5%) = $2.50
         │     fees_sub           = $7.50
         │     fees_tax           = $1.13
         │     buyer_total(Stripe) = $9.20
         │     stripe_transfer    = 0     ← NO destination charge; BidVex keeps all
         │
         ▼
  create_vehicle_payment_session(...)  →  stripe.checkout.Session.create(
      line_items = [{ unit_amount: 920 }],
      payment_intent_data = { metadata: {...} }    ← no transfer_data, no application_fee
  )

Rail 2 (Bank Draft, OFFLINE):
─────────────────────────────
  Buyer sends bank draft directly to dealer for $100 hammer (per instruction message)
  BidVex is not custodian of the hammer
  Deposit ($500 refundable) may be pre-authorized separately via a manual-capture PaymentIntent
```

### 4.5 Storage Money Flow (routed through General checkout)

```
POST /api/payments/checkout/auction  →  general branch (line 936) with listing_bp_override=0.05 (iter445)
         │
         │   custom_buyer_premium_rate=0.05 forced when category or listing_type == storage_locker
         ▼
  Same as §4.3 above but with BP=5%, SC=4% (basic tier default from seller.subscription_tier)
         │
         │   NOTE: seller_commission=4% is applied → storage facility payout = $96 (loses $4)
         │   BUT `_iter350_storage` in fee_calculator.py says seller_commission=0 for storage
         │   TWO CONTRADICTORY RULES 🔴 — see AUDIT REPORT §3.6
```

### 4.6 Cash / E-Transfer Money Flow (via `settle_auction`)

```
When listing.payment_method ∈ {"cash", "etransfer", "e-transfer"}:
─────────────────────────────────────────────────────────
  Auction ends → scheduled_jobs.process_ended_auctions or routes/auctions.py:161
         │
         ▼
  settle_auction(db, auction_id, listing)      (services/auction_settlement.py:794)
         │
         ▼   listing.payment_method → "cash"
         │
  settle_cash_or_etransfer(db, ...)             (line 227)
         │
         │  buyer_prov = buyer.province or "QC"
         │  seller_prov = seller.province or "QC"
         │
         ▼
  fee = calculate_fee(
      hammer_price = 100.0,
      auction_type = "lots",
      seller_account_type = "individual",     ← 🔴 HARDCODED — no Partner branch
      seller_tier = seller.subscription_tier,
      buyer_account_type = "individual",
      buyer_tier = buyer.subscription_tier,
      payment_method = "stripe",
      card_type = "domestic",
      buyer_province = buyer_prov,
      seller_province = seller_prov,
  )
         │
         │   Routes to _iter350_individual
         │
         │   buyer_commission = buyer_premium + tax + stripe_recovery
         │                    = $5 + $0.81 + $0.45 = $6.26
         │   seller_commission_total = $5.08
         │
         ▼
  Off-session PaymentIntent charged on buyer's card for $6.26 (BidVex commission only)
  Off-session PaymentIntent charged on seller's card for $5.08 (seller commission)
  Buyer pays $100 hammer OFFLINE to seller (cash/e-transfer, outside Stripe)
         │
         ▼
  db.receipts → buyer_receipt + seller_statement with itemized breakdown
```

### 4.7 Escrow / Pickup-Code Flow

```
After Stripe payment success (§4.2 / 4.3):
─────────────────────────────────────────
  payment_collection.process_settlement_result_generic
         │
         ▼
  _ensure_stripe_pickup_code(db, ...)          (payment_collection.py:39-88)
         │
         │  Idempotent per (listing_id, lot_number)
         │  Generates BVX-XXXXXXXX 8-char code
         │  Writes db.transactions row with:
         │    commission_already_collected = True
         │    stripe_payment_intent = PI.id
         │    pickup_code = "BVX-XXXXXXXX"
         │
         ▼
  _ensure_escrow_hold_record(db, ...)          (line 91+)
         │
         │  Writes db.escrow_transactions row for buyer/seller/hammer/pickup_code
         │
         ▼
  Buyer collects item → seller uses pickup code in seller dashboard
         │
         ▼
  services/escrow_service.py::release_escrow (blocked by Stripe Sandbox — iter467)
```

## 5. Tax Architecture

### 5.1 Tax rate sources

| Rate | Constant | File |
|---|---|---|
| GST | Decimal("0.05") | `tax_engine.py:37`, `fee_calculator.py:99` |
| QST | Decimal("0.09975") | `tax_engine.py:38`, `fee_calculator.py:100` |
| HST (per province) | Varied | `tax_engine.py`, `tax_rate_config.py::BOOTSTRAP_RATES` |
| Combined | 0.14975 (QC), 0.13 (ON), 0.15 (NB/NL/NS/PE), 0.05 (AB/BC/MB/SK/YT/NT/NU) | `fee_calculator._PROVINCE_TAX_REGIME`, `tax_rate_config` |
| INTL | 0 | Zero-rated per Sched. VI Part V §7 |

**Two authoritative sources**: `services/tax_engine.py` (used by `stripe_connect_service`) and `services/tax_rate_config.py` (used by `fee_calculator`). They agree on QC/HST provinces but the DB-backed `tax_rate_config` is admin-editable while `tax_engine` constants are code-level.

### 5.2 Place-of-supply routing

| Fee | Taxed at | Per code |
|---|---|---|
| Buyer premium (individual/enterprise) | Buyer's province | `_iter350_individual` line 404 |
| Seller commission (individual/enterprise) | Seller's province | `_iter350_individual` line 410 |
| BidVex platform fee (Partner) | Partner's province | `_iter350_partner` line 479 |
| BidVex platform fee (Partner) — LIVE PATH | Buyer's province (mixed in with fees_tax) | `calculate_partner_listing_checkout` line 400 |
| Hammer (Partner, tax-registered) | ambiguous — see conflict below | 🔴 |
| Vehicle platform fee | Buyer's province | `calculate_vehicle_checkout` |
| Storage BP | Buyer's province | `_iter350_storage` line 620 |

### 5.3 Where tax is persisted

| Column | For | File |
|---|---|---|
| `receipts.buyer_premium_gst` / `_qst` | BP tax | `receipts.py:38` |
| `receipts.hammer_gst` / `_qst` | Hammer tax (only if seller/partner tax-registered) | `receipts.py:38` |
| `receipts.seller_commission_gst` / `_qst` | SC tax | `receipts.py:38` |
| `receipts.service_fee_gst` / `_qst` | Reserved (vehicle platform fee tax) | `receipts.py:38` |
| `receipts.bidvex_platform_fee_gst` / `_qst` (iter480) | Duplicate of SC_gst/qst for Partner sales | `receipts.py:56-59` |

## 6. Receipt Architecture (iter476 + iter480)

- Every successful settlement writes exactly ONE `db.receipts` row per (buyer, seller, listing, lot_number). Idempotent per party.
- Row is either `type=buyer_receipt` or `type=seller_statement`.
- Aggregate fields (`hammer_price`, `platform_fee`, `taxes`, `processing_fee`, `total_charged`, `net_payout`) always persisted.
- Itemized fields (per `ITEMIZED_KEYS` in `receipts.py:36-61`) persisted **only** when `issue_transaction_records(itemized=...)` is called with a non-None dict. The dict MUST reconcile per `reconcile_itemized()` (line 74–160); a reconciliation failure drops the itemized block silently but keeps the aggregate row.
- PDF renderers (`services/pdf_generators/*`) READ from these persisted fields and never recompute.

## 7. Invoice Architecture (iter474 / iter475)

- `db.invoices` — cached PDF outputs. Keys: `invoice_type` (e.g., `buyer_receipt`, `seller_statement`, `commission_invoice`, `payment_letter`, `lots_won`, `settlement_statement`), `owner`, `listing_id`.
- `services/cloud_storage.py::generate_signed_url` produces absolute HTTPS signed URLs (iter473 fix).
- PDFs are rendered by `services/pdf_generators/common.py::render_document` from a `DocumentSpec`.
- iter477 added byte-exact reconciliation harness proving 49/49 checks.

## 8. Refund Architecture

**NOT IMPLEMENTED** in production code as of this audit. All refund handling is manual via Stripe Dashboard. See `BIDVEX_PAYMENT_AUDIT_REPORT.md` §9.

## 9. Failed-Payment Architecture

- `services/payment_idempotency.py::mark_charge_failed` — persist `payment_charges` row with `status=failed` + `error` message.
- No exponential-backoff retry queue.
- `payment_collection.py` NO-PM branch — creates Stripe Payment Link, 48-hour deadline email.
- Scheduled cron detects overdue → `payment_status=payment_overdue`.

## 10. Multi-Lot / Quantity Architecture

- `services/hammer_total.py::resolve_hammer_total(listing)` returns `{unit_price, quantity, hammer_total, is_multiplied}`.
- Called by `auction_settlement.settle_auction` (line 817). ✅
- NOT called by `routes/payments.py::create_auction_checkout` (line 883 reads `listing.current_price` directly). ⚠️
- Multi-lot marketplace: `db.multi_item_listings` has `lots[]` array; each lot settles independently through `settle_auction` per iter302.

## 11. Scheduled Settlement Architecture

- `services/scheduled_jobs.py::process_ended_auctions` — marketplace listings.
- `services/scheduled_jobs.py::process_ended_storage_auctions` — storage.
- `services/vehicle_auction_handler.py` — vehicles.
- All invoke `settle_auction` → `settle_cash_or_etransfer` OR `settle_stripe_full`.

## 12. Database Financial Fields — Catalog

### 12.1 `db.receipts` (see AUDIT REPORT §6.1 for full list with ownership annotations)

### 12.2 `db.transactions`
Key financial fields: `hammer_price`, `amount`, `payment_method`, `stripe_payment_intent`, `commission_already_collected`, `pickup_code`. See AUDIT REPORT §6.2.

### 12.3 `db.seller_payouts`
Non-custodial admin manual payout queue per PRD iter302.

### 12.4 `db.invoices`
Cached PDF records.

### 12.5 `db.escrow_transactions`
Pickup code + escrow-hold status for non-vehicle Stripe orders. Blocked on iter467 payout verification.

### 12.6 `db.bidding_deposits` / `db.storage_deposits`
Pre-auth $500 (vehicle) or $1000 (marketplace/storage) via PaymentIntent(capture_method="manual"). Captured on payment success, released on loss.

### 12.7 `db.payment_charges` (from `payment_idempotency`)
Idempotent charge log: `id`, `auction_id`, `user_id`, `charge_type`, `currency`, `amount`, `idempotency_key`, `status`, `stripe_object_id`.

### 12.8 `db.payment_events`
Audit log: `event`, `charge_id`, `stripe_payment_intent_id`, `error`.

### 12.9 `db.pending_payments`
Pre-checkout tracking: `session_id`, `listing_id`, `buyer_id`, `breakdown`.

### 12.10 `db.affiliate_payouts`
15% cash-back on BidVex revenue for referred sellers.

### 12.11 `db.fee_schedules` (iter478 NEW)
Versioned fee rates. **Not consulted by any live calculation path yet** — Phase 1 contract preserved. See PRD.md iter478.

## 13. Fee Schedule Architecture (iter478)

- Single row `id="fee_schedule_v1"`, `version=1`, `is_active=True`.
- Fields: `buyer_premium.*`, `seller_commission.*`, `platform_fees.*`, `stripe.percent`, `stripe.fixed_cad`, `affiliate_commission_rate`, `category_overrides.*`, `tier_aliases`.
- Loader / resolvers in `services/fee_schedule.py`.
- **Zero production calc importers** (Phase 1 T0 test proves this).

## 14. Legacy Code Dependencies

See AUDIT REPORT §10 for the full table. Summary:
- 6 distinct fee calculation entry points, 3 different "3% Partner" constants (`PARTNER_PLATFORM_RATE`, `PARTNER_PLATFORM_FEE_RATE`, `PARTNER_SELLER_COMMISSION_RATE`).
- `PricingManager` (in `fee_calculator.py::1256+`) has 8+ importers.
- `fee_calculation_engine.py` is a separate legacy engine exposed via `/api/fees/v2/preview`.
- `services/category_rules.py::COMMISSION_RATES` — dead code, 0 production consumers.

## 15. Source-of-Truth Map for Every Fee

| Fee | Live Stripe path | Cash/e-transfer path | Legacy engine | PricingManager |
|---|---|---|---|---|
| Partner buyer premium | `calculate_partner_listing_checkout` custom_bp | `_iter350_partner` (dead) | `PricingManager.partner_auction` | ↑ same |
| Partner platform fee (3%) | `tax_engine.PARTNER_PLATFORM_FEE_RATE=0.03` | `fee_calculator.PARTNER_PLATFORM_RATE=0.03` | `fee_calculator.PARTNER_SELLER_COMMISSION_RATE=0.03` | ↑ same |
| Individual BP | `tax_engine.BUYER_PREMIUM_RATES[tier]` | `fee_calculator.INDIVIDUAL_BUYER_RATES[tier]` | `fee_calculator.BUYER_PREMIUM_RATES[tier]` | ↑ same |
| Individual SC | `tax_engine.SELLER_COMMISSION_RATES[tier]` | `fee_calculator.INDIVIDUAL_SELLER_RATES[tier]` | `fee_calculator.SELLER_COMMISSION_RATES[tier]` | ↑ same |
| Vehicle platform fee | `tax_engine.VEHICLE_PLATFORM_FEE_RATE=0.025` | `fee_calculator.VEHICLE_DEALER_BUYER_RATE=0.025` | `fee_calculator.VEHICLE_PLATFORM_FEE_RATE=0.025` (PM) | ↑ same |
| Storage BP | `iter445` forced 0.05 in `routes/payments.py` | `fee_calculator.STORAGE_FACILITY_RATE=0.05` | n/a | n/a |
| Storage SC | `calculate_general_checkout` reads seller.subscription_tier (defaults 4%) 🔴 | `_iter350_storage` says 0 🔴 | n/a | n/a |
| Broker platform fee | not wired to Stripe | `fee_calculator.BROKER_PLATFORM_RATE=0.025` (calculate_broker_transaction) | n/a | n/a |
| Stripe rate | `stripe_connect_service.STRIPE_PERCENTAGE_FEE=0.029`, `STRIPE_FIXED_FEE=0.30` | `fee_calculator.STRIPE_PROCESSING_RATE=0.029`, `STRIPE_FIXED_FEE=0.30` | ↑ same | ↑ same |
| Affiliate rate | `pricing_config.AFFILIATE_COMMISSION_RATE=0.03` | `fee_calculator.AFFILIATE_COMMISSION_RATE=0.03` | ↑ same | ↑ same |

Every rate is duplicated 2-4 times across modules. The `fee_schedules` DB row (iter478) is the intended canonical source, but Phase 3/4 cutover has not been executed.

## 16. Money-Flow Diagrams

See §4.2-§4.7 above for per-flow ASCII diagrams.

## 17. Worked Examples — All Seller Types

### 17.1 Partner ($100 / 10% BP / QC, not registered)

See AUDIT REPORT §2 for the full trace. Buyer charged $114.06 (should be $110). 🔴

### 17.2 Partner ($100 / 15%)

Buyer charged **$119.21** (should be $115). 🔴

### 17.3 Partner ($100 / 18%)

Buyer charged **$125.34** (should be $118). 🔴

### 17.4 Individual — standard tier ($100 / QC / seller not registered)

Buyer charged **$109.84**. Composition:
```
hammer                $100.00
buyer_premium (5%)     $  5.00
fees_tax (14.975%)     $  1.35 (on $9 BidVex fees)
processing_fee         $  3.49
─────────────────────────────
Total                 $109.84
```
Seller receives $96.00 (via `transfer_data`, hammer − 4% SC).
BidVex retains application_fee $10.35, nets $6.86 after rail.

### 17.5 Individual — standard, seller IS tax-registered ($100 / QC)

Buyer charged **$125.26** (adds $14.98 hammer tax + higher gross-up). Seller receives $110.98 with instruction to remit $14.98 hammer tax to CRA/RQ.

### 17.6 Enterprise — same as Individual

Per iter478 fee_schedule bootstrap, Enterprise mirrors Individual rates.

### 17.7 Partner Pro

No live checkout path exists — `routes/payments.py` does not route to a Partner Pro branch. Partner Pro rates only exist in `db.fee_schedules` (iter478 bootstrap) and are not consulted by any live payment code. 🟡

### 17.8 Vehicle Dealer

Buyer charged **$9.20 via Stripe** (fees only) + **$100 hammer offline** = $109.20 total cash outlay. Deposit $500 pre-authorized separately.

### 17.9 Storage Facility

Buyer charged **$109.84** (routed through `calculate_general_checkout` with BP=5% forced). Facility receives **$96** (loses $4 to SC), which contradicts iter443 rule that facility should receive full $100 hammer. 🔴

### 17.10 Broker

No Stripe wiring found. `calculate_broker_transaction` returns a dict but is never converted into a Stripe Session by any production route. 🟡 (Broker check-out might route through a different endpoint not audited — verify.)

## 18. Known Discrepancies

Ranked by severity:

1. **🔴 P0 — Partner Stripe checkout overcharge $4.06 per $100/10% sale.** See AUDIT REPORT §2 + §7.
2. **🔴 P0 — `settle_auction` hardcodes `seller_account_type="individual"`.** Partner cash/e-transfer sales are silently mis-billed. Also affects Storage/Vehicle cash paths. See AUDIT REPORT finding #6.
3. **🔴 P0 — Storage seller_commission dual-truth.** `calculate_general_checkout` deducts 4% SC; `_iter350_storage` says 0. See AUDIT REPORT §3.6.
4. **🔴 P1 — No refund infrastructure.** Manual admin-only via Stripe Dashboard. See AUDIT REPORT §9.
5. **🟡 P1 — Partner hammer-tax rule ambiguity.** Two paths disagree (charge at buyer province vs never charge at BidVex). See PRD iter479 Q2.
6. **🟡 P1 — `_iter350_individual` vs `calculate_general_checkout` produce different buyer totals** ($106.91 vs $109.84 on $100). Two Stripe recovery formulas in use.
7. **🟡 P2 — `routes/payments.py:883` reads `listing.current_price` without `resolve_hammer_total`.** Multi-lot listings may under-bill if `current_price` is per-unit.
8. **🟡 P2 — Partner Pro has no live checkout path.** Fee_schedule entry exists but never consulted.
9. **🟡 P2 — Broker has no Stripe wiring.** `calculate_broker_transaction` returns a dict but no session builder invokes it.
10. **🟡 P3 — 6 fee-calc entry points / 3 "Partner 3%" constants.** Technical debt (Phase 4 target).

## 19. Risks

| Risk | Impact | Likelihood |
|---|---|---|
| Buyer disputes Partner charge for $4.06 overpayment | Financial + reputational + consumer-protection (QC Loi 224/227) | HIGH given the direct disclosure gap |
| Partner discovers $3 shortfall in payout ($107 vs expected $110) | Partner attrition | MODERATE |
| Storage facility discovers unauthorized 4% SC deduction | Storage partner attrition + refund exposure | MODERATE |
| Cash/e-transfer Partner sale silently mis-billed as individual | Depends on whether Partners ever use cash — if seller_type_check fires elsewhere it might be caught | LOW-MODERATE |
| Refund dispute requires manual reconciliation | Ops load, potential $ errors | HIGH |

## 20. Phase 4 Cleanup Recommendations (contingent on P0 repairs)

**Do NOT execute Phase 4 until P0/P1 above are repaired.** Once repaired:

1. Consolidate the 6 fee-calc entry points to a single `services/fee_calculator.calculate_fee()` reading from `db.fee_schedules`.
2. Delete `services/fee_calculation_engine.py` after migrating `/api/fees/v2/preview`.
3. Delete `PricingManager` block after migrating its 8 importers (vehicle_invoice, connect_payment_engine, etc.) — see PRD iter478 §Repository caller/import findings.
4. Delete `services/category_rules.py::COMMISSION_RATES` (dead code).
5. Rename `PARTNER_PLATFORM_RATE` / `PARTNER_PLATFORM_FEE_RATE` / `PARTNER_SELLER_COMMISSION_RATE` → single canonical `bidvex_partner_platform_fee_rate` sourced from `fee_schedules`.
6. Rename `FeeResult.seller_payout` for Partner sales — value is actually "partner_owes_bidvex", not "payout".
7. Rename `FeeResult.seller_commission` for Partner sales to `bidvex_platform_fee` (or set to 0 and use the new iter480 field).
8. Remove hardcoded `seller_account_type="individual"` in `auction_settlement.py`; derive from user record.
9. Wire `services/fee_schedule.py` resolvers into `stripe_connect_service` + `auction_settlement` (Phase 3 cutover).

---

*End of INFRASTRUCTURE SPECIFICATION. This document reflects the AS-IS state of the codebase as of Feb 12, 2026. Any repair to the 🔴 findings will invalidate portions of §4.2 and §17.1-17.3 and will require this document to be revised.*
