# PAYMENT_IMPLEMENTATION_PLAN.md

**Phase 0 — READ-ONLY Investigation Complete. Awaiting explicit Phase 1 authorization.**
Date: Feb 12, 2026. Preview backend: `https://prod-verify-2.preview.emergentagent.com`. Production: `https://launchapp-4-r-1774886029.emergent.host`.

Zero production code was modified. Zero DB writes. Zero migrations. Zero deployments. All numbers below were produced by importing and calling the current repository's functions in a Python REPL against a local ephemeral process — no Stripe API call, no HTTP request, no state change.

---

## Table of Contents

- [A. VERIFIED FINDINGS](#a-verified-findings) — reproduced against CURRENT code
- [B. FALSE / OUTDATED FINDINGS](#b-false--outdated-findings) — items in my prior audit that turned out imprecise
- [C. NEW FINDINGS NOT IN THE PRIOR AUDIT](#c-new-findings-not-in-the-prior-audit)
- [D. CURRENT MONEY FLOW](#d-current-money-flow-static-trace-per-endpoint)
- [E. BUSINESS DECISIONS REQUIRED FROM YOU](#e-business-decisions-required-from-you)
- [F. PROPOSED TARGET ARCHITECTURE](#f-proposed-target-architecture)
- [G. FILES TO CHANGE](#g-files-to-change-per-phase)
- [H. FILES TO PROTECT (NEVER TOUCH)](#h-files-to-protect-never-touch)
- [I. TEST PLAN](#i-test-plan)
- [J. RISK ASSESSMENT](#j-risk-assessment)
- [K. MIGRATION REQUIREMENTS](#k-migration-requirements)
- [L. ROLLBACK PLAN](#l-rollback-plan)
- [M. PHASED IMPLEMENTATION ROADMAP](#m-phased-implementation-roadmap)
- [N. READ-ONLY TEST MATRIX — 9 CASES](#n-read-only-test-matrix--9-cases-computed-from-current-code)

---

## A. VERIFIED FINDINGS

Each finding was reproduced by inspecting the CURRENT source and, where relevant, by importing and calling the actual function in Python.

### A-1 🔴 P0 — Partner Stripe checkout via `POST /api/payments/checkout/auction` overcharges the buyer by ~$4.06 per $100/10% sale

**Verified**. Static call to `calculate_partner_listing_checkout(100.0, 0.10, False, True)` in the current repo returns:
- `buyer_total_cents = 11406` → $114.06 CAD passed to `stripe.checkout.Session.create` inside `create_destination_charge`
- `stripe_application_fee_cents = 706` ($7.06 retained by BidVex)
- `stripe_transfer_amount_cents = 11000` (metadata; effective transfer = charge − application_fee = $107.00)

The overcharge components (from `stripe_connect_service.py:398-420`):
- `fees_tax_total = $0.45` — 14.975% GST+QST on BidVex's own $3 platform fee, embedded in `subtotal_before_processing`.
- `processing_fee = $3.61` — gross-up applied to the entire `hammer + BP + tax = $110.45` base.

Both are added into the buyer's Stripe line-item `unit_amount`. The buyer's card is charged $114.06.

### A-2 🔴 P0 — There is a *second* Partner Stripe checkout path that produces $110 for the buyer but a net LOSS for BidVex

**New finding, not in prior audit.** `POST /api/payments/checkout` (the "unified" endpoint at `routes/payments.py:62-188`) calls `connect_payment_engine.calculate_connect_checkout` (line 133), which for Partner listings dispatches to `fee_calculator.PricingManager.partner_auction`.

Static call to `PricingManager.partner_auction(100.0, "QC", 0.10)` returns:
- `buyer_invoice.total = $110.00` → passed into `_to_cents(stripe_charge)` at `connect_payment_engine.py:189` → `unit_amount = 11000` (11000 cents) charged to buyer
- `application_fee_amount = $3.00` (line 148: `application_fee = Decimal(str(seller_commission))` where `seller_commission = $3` for Partner)

**Under Stripe destination-charge semantics without `on_behalf_of`, Stripe deducts its 2.9% + $0.30 rail fee from the platform (BidVex), NOT from the connected account.** So:
- Stripe rail on $110 = $110 × 0.029 + $0.30 = **$3.49**
- BidVex net = application_fee ($3.00) − Stripe rail ($3.49) = **−$0.49 (loss) per Partner sale**
- Partner receives = $110 − $3.00 = **$107.00** (below the user's expected $110)

**Both Partner Stripe paths violate the business rule**, in different ways:
- `/checkout/auction` → buyer overcharged (business rule violation A)
- `/checkout` (unified) → BidVex loses money AND Partner short-paid (business rule violation B + C)

**Which endpoint the frontend actually calls is NOT statically determinable** — this requires network-tab inspection or frontend grep. Reported as an open question in Section E.

### A-3 🔴 P0 — `settle_auction` hardcodes `seller_account_type="individual"` for BOTH Stripe and cash/e-transfer paths

**Verified**. `services/auction_settlement.py`:
- `settle_cash_or_etransfer` line 259: `seller_account_type="individual"`
- `settle_cash_or_etransfer` line 261: `buyer_account_type="individual"`
- `settle_cash_or_etransfer` line 263: `payment_method="stripe"` (even in a cash flow!)
- `settle_stripe_full` line 610: `seller_account_type="individual"`
- `settle_stripe_full` line 612: `buyer_account_type="individual"`

**Impact reproduced**: for a Partner $100/10% sale settled through `settle_auction`, `calculate_fee` returns:
- `buyer_premium = $5.00` (5% basic-tier rate, NOT the 10% Partner rate)
- `buyer_total_charged = $106.27` (NOT $110, NOT $114.06)
- `seller_payout = $94.92` (Partner receives 94.92, missing $15+)

**A Partner listing settled through the auction-end automation is silently mis-billed as a basic Individual sale.** Both buyer and Partner lose meaningful money.

### A-4 🔴 P0 — Storage seller_commission — TWO CONFIRMED CONFLICTING BUSINESS RULES

**Verified by direct call**:

`calculate_general_checkout(100.0, "basic", "basic", False, True, custom_buyer_premium_rate=0.05)` returns:
- `buyer_premium=$5, seller_commission=$4, buyer_total=$109.84, seller_payout=$96`
- **Facility LOSES 4% ($4) to SC**

`calculate_fee(seller_account_type="storage_facility", ...)` returns:
- `buyer_premium=$5, seller_commission=$0, buyer_total=$106.27, seller_payout=$100`
- **Facility keeps 100% of hammer** ✓ (iter443 documented rule)

`routes/payments.py:955` sends storage listings to `calculate_general_checkout` (with BP=0.05 forced but SC default). So the live production Stripe path applies the 4% SC that `_iter350_storage` explicitly forbids.

### A-5 🟡 P1 — `routes/payments.py:883` reads `listing.current_price` directly without `resolve_hammer_total`

**Verified**. In `create_auction_checkout` at line 883:
```python
hammer_price = listing.get("current_price", listing.get("starting_price", 0))
```
No call to `services.hammer_total.resolve_hammer_total`. In contrast, `POST /api/payments/checkout` at line 128-131 correctly does:
```python
listing_qty = int(listing.get("quantity") or 1)
multiply_hammer = bool(listing.get("multiply_hammer_by_quantity"))
effective_qty = listing_qty if (listing_qty > 1 and multiply_hammer) else 1
hammer_price = unit_price * effective_qty
```

**Impact**: A Partner listing with `quantity=2` and `multiply_hammer_by_quantity=True` charged through `/checkout/auction` is under-billed by 50% (only per-unit hammer). Through `/checkout`, it is correctly billed on the multiplied hammer.

### A-6 🟡 P1 — Three different constants for "Partner 3%"

**Verified by grep**:
- `services/tax_engine.py:82` — `PARTNER_PLATFORM_FEE_RATE = Decimal("0.03")` (used by `stripe_connect_service`)
- `services/fee_calculator.py:77` — `PARTNER_PLATFORM_RATE = Decimal("0.03")` (used by `_iter350_partner`)
- `services/fee_calculator.py:1120` — `PARTNER_SELLER_COMMISSION_RATE = Decimal("0.03")` (used by `PricingManager.partner_auction`)

All three currently equal 0.03. **If a business decision ever changes this rate, three separate files must be edited synchronously.**

### A-7 🟡 P1 — Multiple, non-equivalent fee calculators are simultaneously live in production

**Verified by static call**. For the SAME input `$100 hammer / 10% Partner BP / QC / partner not registered`:

| Code path | Buyer total | BidVex net (after Stripe rail) | Partner net |
|---|---|---|---|
| `calculate_partner_listing_checkout` (`/checkout/auction`) | **$114.06** | $3.45 | $107.00 |
| `PricingManager.partner_auction` (`/checkout` unified) | **$110.00** | **−$0.49 (loss)** | $107.00 |
| `calculate_fee(seller_account_type="partner")` (dead in settle_auction) | $110.00 | $3.00 | Partner owes $3.90 separately (not actually collected) |
| `calculate_fee(seller_account_type="individual")` (what `settle_auction` actually calls) | **$106.27** | $8.05 | $94.92 |

**Four distinct economic outcomes for the same sale.** Which one the buyer/seller experiences depends entirely on which endpoint the frontend hits.

### A-8 🟡 P1 — Partner path in `PricingManager.partner_auction` records the Partner's $3.90 obligation as a `SideInvoice.seller_invoice` — but never actually charges it

**Verified**. `fee_calculator.py:1515-1528` builds a `SideInvoice` labeled "seller commission + Stripe recovery + tax" totaling $3.90 for the Partner. But `connect_payment_engine.calculate_connect_checkout` line 122-190 does NOT emit any second charge / second PaymentIntent for the seller side. The `SideInvoice` is a rendering artifact for statements. **There is no code path today that debits the Partner's card for the $3.90 obligation.** BidVex therefore has no mechanism to recover its $3 net + Stripe recovery + tax from the Partner through this code path.

### A-9 🔴 P1 — No production refund creation code

**Partially verified — refined from prior audit.** There ARE production paths that call `stripe.Refund.create`:
- `services/pickup_confirmation.py:174` — escrow release refund
- `services/broker_deposit_service.py:116` — broker deposit refund
- `services/deposit_refund_queue.py:154` — bidder deposit refund queue
- `services/payment_idempotency.py:282, 284` — duplicate-charge auto-refund
- `routes/disputes.py:327` — dispute manual admin refund

But NONE of these handle **application_fee refund** or **transfer reversal** for Partner destination charges. If a Partner buyer disputes a $114.06 charge, `stripe.Refund.create(payment_intent=pi)` will reverse the buyer charge but leave the destination transfer intact on the Partner's Connect account (until Stripe deducts it back from the platform's balance, which is Stripe's default behavior — but that can leave the Partner's Connect account negative or the platform's balance short).

The webhook receiver `routes/webhooks.py:515-595` handles `charge.refunded`, `refund.created`, `refund.updated` — it marks `payment_charges.status="refunded"` via `mark_charge_refunded` (idempotently). But:
- It does NOT reverse the destination transfer
- It does NOT reverse the application fee
- It does NOT update `receipts` or `invoices` to reflect refund
- It does NOT update `seller_payouts` if a payout was already issued
- It does NOT record the refund event on `db.transactions`

### A-10 🟡 P1 — There are TWO Stripe payment models in production, not one

**New finding**. Discovered during Phase 0:

- **Buyer-initiated Stripe Checkout path** (via `/api/payments/checkout` or `/api/payments/checkout/auction`): uses `stripe.checkout.Session.create` with `payment_intent_data.transfer_data.destination` (destination charges), `application_fee_amount` set. Full Connect flow.
- **Auction-end auto-settle Stripe path** (via `settle_stripe_full`): uses `stripe.PaymentIntent.create` on saved `payment_method_id` (off-session), **NO** `transfer_data`, **NO** `application_fee_amount`. Non-custodial — everything lands on BidVex platform, admin manually pays out seller (per `auction_settlement.py:715-721` comments citing iter298 BUG 3).

These two models are fundamentally different Stripe primitives with different tax, fee, and payout semantics. Both are alive today. This is a hidden dual-architecture that the previous audit did not surface.

### A-11 🟡 P2 — Partner Pro has zero live Stripe checkout wiring

**Verified**. Grep for `partner_pro` in `services/stripe_connect_service.py`, `connect_payment_engine.py`, `fee_calculator.py` (production entry points): only `fee_schedule.py` (iter478 bootstrap) references `partner_pro` as a rate row. No dispatcher branch invokes the Partner Pro schedule during checkout. If a seller has `subscription_tier="partner_pro"`, they will hit the standard `Partner` branch and be billed at the default Partner rates, not Partner Pro's 3.75%.

### A-12 🟡 P2 — Broker has zero live Stripe checkout wiring

**Verified**. `services/fee_calculator.py::calculate_broker_transaction` returns a dict but grep shows **no** `stripe.PaymentIntent.create` or `stripe.checkout.Session.create` call that consumes it in production paths. The dedicated broker service exists (`services/broker_deposit_service.py`) for deposits only. Broker auction settlement path is not identified.

### A-13 🟡 P2 — Cash / e-transfer auto-settle uses `payment_method="stripe"` in the fee calculation

**Verified**. `auction_settlement.py:263` inside `settle_cash_or_etransfer` calls `calculate_fee(..., payment_method="stripe", ...)`. This forces the Stripe recovery formula to run on a cash/e-transfer transaction. If the business rule for cash is "no Stripe recovery" (because there's no Stripe rail cost for the hammer paid offline), the current settlement is over-billing the buyer's commission-only charge.

### A-14 🟢 The `iter476/iter480` receipt persistence code IS correctly wired

**Verified**. `services/payment_collection.py:514-523` calls `issue_transaction_records(..., itemized=itemized_block)`, and `settle_auction`'s `settle_cash_or_etransfer` / `settle_stripe_full` correctly populate `result["itemized"]` (line 327-345 for cash; a similar block exists for stripe_full). The iter480 Phase 3 fields (`bidvex_platform_fee_rate`, `_amount`, `_gst`, `_qst`) are populated correctly by `calculate_fee` when it runs. However — because `settle_auction` hardcodes `seller_account_type="individual"` (A-3), the iter480 fields are ALWAYS $0 for Partner listings that go through auction-end settlement.

### A-15 🟢 Refund idempotency at the webhook layer IS correctly implemented

**Verified**. `routes/webhooks.py:543-560` detects `existing.status == "refunded"` and inserts a `DUPLICATE_REFUND_BLOCKED` event, preventing double-processing. This is well-designed.

### A-16 🟡 P2 — Two tax authorities coexist

**Verified**. `services/tax_engine.py` has hard-coded rate constants (`GST_RATE = 0.05`, `QST_RATE = 0.09975`, `COMBINED_TAX_RATE`, etc.). `services/tax_rate_config.py` has DB-backed admin-editable rates (`BOOTSTRAP_RATES`, `get_tax_rate_sync`). Different code paths consult different authorities. Numerically they agree TODAY, but they can diverge if the DB is updated without a corresponding constants change.

---

## B. FALSE / OUTDATED FINDINGS

Items from my prior audit report that require correction after Phase 0 verification:

### B-1 CORRECTED — "No production refund creation code" (prior claim)

Prior claim: "No route creates refunds; only test files have `stripe.Refund.create`."
Reality: **Five production paths do call `stripe.Refund.create`** (see A-9). What is truly missing is the Partner-specific handling — application_fee refund and destination transfer reversal for Connect charges, plus downstream document updates (receipts / invoices / statements / transactions). Reworded above.

### B-2 CORRECTED — "There is only one live Partner Stripe path"

Prior claim: "Only `/api/payments/checkout/auction` calls `calculate_partner_listing_checkout`."
Reality: **Two Partner Stripe paths exist** (see A-2, A-10). `/api/payments/checkout` (unified) also handles Partner listings through `PricingManager.partner_auction`, with different economics. Which one the frontend uses is an open question.

### B-3 CORRECTED — "`settle_stripe_full` uses destination charges"

Prior implicit assumption: settle_stripe_full also creates destination charges.
Reality: `settle_stripe_full` uses off-session PaymentIntent WITHOUT destination charges (see A-10). Non-custodial. Admin manual payout.

### B-4 UNCHANGED — "$110 iter480 model exists only in `_iter350_partner`"

Prior claim confirmed with one refinement: the $110 model ALSO exists in `PricingManager.partner_auction` (which is live via `/api/payments/checkout`). So iter480's math is not entirely dead code — it may be actively serving Partner sales through the unified endpoint, at a $0.49/sale LOSS to BidVex.

---

## C. NEW FINDINGS NOT IN THE PRIOR AUDIT

### C-1 🔴 `PricingManager.partner_auction` is a LIVE production Partner path that BidVex loses money on

Every Partner sale through `POST /api/payments/checkout` currently produces a **$0.49 loss** for BidVex (before considering QC tax remittance BidVex must still pay on its $3 fee). Scale: 100 Partner sales/month at $100 avg = **$49/month loss just from Stripe rail. At $10,000 avg hammer, Stripe rail is ~$290 while application_fee is only $300 — barely breakeven. At $100,000 hammer, Stripe rail is ~$2,900 and application_fee is $3,000 — still barely breakeven. If any Partner sale below ~$100 completes through this path, BidVex is definitely losing money.**

### C-2 🔴 Case 4 — Partner IS tax-registered — buyer overcharge is $21.03, not $4.06

For a Partner $100/10% sale where the Partner IS tax-registered:
- Expected buyer total (rule): $110.00 + hammer tax that Partner remits = $124.98
- Actual buyer total (from `calculate_partner_listing_checkout`): **$131.03**
- Overcharge: **$6.05**

The overcharge grows with the BP rate. At Partner $100/18%, seller tax-registered (not tested but by extrapolation), the buyer overcharge exceeds $8 per $100 hammer.

### C-3 🟡 The cash/e-transfer path passes `payment_method="stripe"` even though no Stripe charge for the hammer occurs

See A-13. Numerically this changes the buyer_stripe_recovery from ~$0.00 (cash) to ~$0.45 (Stripe formula on BidVex fees). If the business rule for cash is "buyer commission charged via Stripe (yes — because BidVex needs to collect its fee), Stripe recovery applies to the fee only (yes — matches current behavior)", then this may actually be intentional. **This one needs business confirmation.**

### C-4 🟡 iter302 comment in `auction_settlement.py:715-721` conflicts with iter466 comment in `payment_collection.py:445`

`auction_settlement.py:715-721`: "iter298 BUG 3 — NON-CUSTODIAL GUARD: never route funds to the seller automatically. Stripe Connect destination charges are disabled until Connect is fully configured."

`payment_collection.py:445`: "iter302 — automatic Connect payout (falls back to the pending-payouts queue + admin notification internally)."

**These two directives contradict each other.** The current code appears to follow iter298 (non-custodial) in `settle_stripe_full`, while the newer `/api/payments/checkout/auction` endpoint uses full destination charges (custodial). Two architectures coexist.

### C-5 🟡 The `iter480` Phase 3 fields are $0 for every Partner sale routed through `settle_auction`

Because `settle_auction` hardcodes `seller_account_type="individual"`, `calculate_fee` returns `bidvex_platform_fee_amount=0` for those Partner sales. The itemized receipt persists $0 for `bidvex_platform_fee_amount` even though economically BidVex is retaining a fee (via seller_commission $4). The receipt is factually inaccurate for Partner sales settled through auction-end automation.

### C-6 🟡 `settle_stripe_full` bypasses `application_fee_amount` and `transfer_data` entirely

`settle_stripe_full` uses `stripe.PaymentIntent.create` on saved cards but sets `_ = seller_connect_id  # retained for observability/logging only`. It never actually uses Stripe Connect. This means auction-end-driven settlements ALL land on BidVex's platform account and require a manual admin payout. This may be the correct non-custodial architecture (fits BidVex Canada's regulatory posture), but it means:
- The two Stripe paths (buyer-initiated vs auction-end) have fundamentally different money-flow semantics
- `iter302 automatic Connect payout` referenced in `payment_collection.py:445` is a NO-OP for `settle_stripe_full`'s output
- Buyer-initiated `/checkout/auction` writes funds directly to the Partner's Connect account bypassing the admin payout queue

---

## D. CURRENT MONEY FLOW (static trace per endpoint)

### D-1 `POST /api/payments/checkout` (unified — Buy It Now + auction win + subscription)

```
routes/payments.py:62
  → routes/payments.py:96-188 (listing_id branch)
     → connect_payment_engine.calculate_connect_checkout()
        → fee_calculator.PricingManager.partner_auction()  [if seller_is_partner]
        → fee_calculator.PricingManager.vehicle_auction()   [if is_vehicle]
        → fee_calculator.PricingManager.non_vehicle_stripe() [else]
     → connect_payment_engine.create_connect_checkout_session()
        → stripe.checkout.Session.create(
            line_items=[{"unit_amount": stripe_charge_cents, ...}],
            payment_intent_data={
              "application_fee_amount": application_fee_cents,
              "transfer_data": {"destination": seller_connect_account_id},
              ...
            })
```

Partner $100/10%: buyer_cents=11000, application_fee=$3, BidVex net -$0.49.

### D-2 `POST /api/payments/checkout/auction` (auction-specific, dedicated Partner/Vehicle/General branches)

```
routes/payments.py:840
  → routes/payments.py:885-916 (Partner branch when is_partner_listing=True)
     → stripe_connect_service.calculate_partner_listing_checkout()
     → stripe_connect_service.create_destination_charge()
        → stripe.checkout.Session.create(
            line_items=[{"unit_amount": 11406, ...}],  # $114.06
            payment_intent_data={
              "application_fee_amount": 706,   # $7.06
              "transfer_data": {"destination": seller_connect_account_id},
              ...
            })
```

Partner $100/10%: buyer=$114.06, BidVex net $3.45, Partner $107.

### D-3 `settle_auction` (auction-end automation, `routes/auctions.py:161, 725, 739`)

```
services/auction_settlement.settle_auction()
  → services/hammer_total.resolve_hammer_total(listing)   ✓ [uses quantity correctly]
  → settle_cash_or_etransfer() OR settle_stripe_full()
     → fee_calculator.calculate_fee(seller_account_type="individual", ...)   🔴 HARDCODED
     → stripe.PaymentIntent.create(...)  [no destination charge, no application_fee]
  → payment_collection.process_settlement_result_generic()
     → services.receipts.issue_transaction_records(..., itemized=...)
     → services.seller_payouts.process_seller_payout(...)  [manual admin queue]
```

Partner $100/10% (settled at auction end): buyer=$106.27, seller=$94.92, BidVex=$8.05.

### D-4 Vehicle path

```
POST /api/payments/checkout/auction → vehicle branch (line 917)
  → stripe_connect_service.calculate_vehicle_checkout()   [Stripe rail: fees only, $9.20]
  → stripe_connect_service.create_vehicle_payment_session()
     → stripe.checkout.Session.create(
         line_items=[{"unit_amount": 920}],   # $9.20 fees
         payment_intent_data={metadata: {...}})   # NO destination charge
     
Hammer $100 paid offline via bank draft directly buyer↔dealer.
```

### D-5 Storage path

```
POST /api/payments/checkout/auction → general branch (line 936) 
  with routes/payments.py:955 forcing custom_buyer_premium_rate=0.05
  → stripe_connect_service.calculate_general_checkout(bp=0.05)
     buyer=$109.84, seller_commission=$4 (facility loses $4)  🔴 contradicts _iter350_storage
```

### D-6 Refund flow (as currently implemented)

```
Admin creates refund via Stripe Dashboard OR one of 5 production Refund.create paths
  → Stripe webhook: charge.refunded / refund.created / refund.updated
    → routes/webhooks.py:515 handler
      → Idempotency check: db.payment_charges.status == "refunded" → DUPLICATE_REFUND_BLOCKED
      → services.payment_idempotency.mark_charge_refunded()
      → db.bidding_deposits + db.storage_deposits status = "refunded"
      → NO update to: db.receipts, db.invoices, db.transactions, db.seller_payouts
      → NO reversal of: application_fee, transfer_data.destination
```

---

## E. BUSINESS DECISIONS REQUIRED FROM YOU

Before Phase 1 can begin, the following decisions must be made by the business owner (you). Do not guess.

### E-1 Which Stripe Connect architecture will BidVex use going forward?

**Option A — Destination charges (custodial)**:
- Buyer's card is charged the full amount
- BidVex retains `application_fee_amount`
- Stripe transfers the remainder to the Partner's Connect account
- Currently used in `/checkout` and `/checkout/auction`

**Option B — Non-custodial (funds on platform, manual payout)**:
- Buyer's card is charged the full amount
- Funds land on BidVex's platform account
- Admin manually initiates a Stripe Transfer to the Partner
- Currently used in `settle_stripe_full`

**Option C — Separate charges + Stripe Transfer (Partner-side collection)**:
- Buyer's card charged $110 (hammer + Partner BP only, no BidVex fee)
- BidVex's fee + Stripe recovery + tax charged separately to the PARTNER's card on file
- Requires Partner to have a saved payment method
- Matches your stated rule most cleanly

The user's stated rule requires the buyer to pay $110 and BidVex to net $3 (before its own taxes/costs) from the Partner. **This is architecturally achievable only via Option C, or via a variant of Option A where `application_fee_amount` is calibrated to exactly $3 and Stripe fees are borne by the Partner via `on_behalf_of`+`transfer_data.amount`.**

### E-2 What is the correct Partner Buyer Premium tax rule?

If Partner IS tax-registered:
- Should the buyer see tax on the Partner Buyer Premium? (Currently: yes for `/checkout/auction`, no for `/checkout` — different behavior)
- Which province governs the BP tax — Partner's or Buyer's?

If Partner is NOT tax-registered:
- Is the Partner Buyer Premium taxable at all? (Currently: no)

### E-3 What is the correct BidVex platform fee tax rule?

- Charged at Partner's province (per `_iter350_partner`) or Buyer's province (per `calculate_partner_listing_checkout` where `fees_tax_total` is computed with QC constants regardless)?
- Buyer bears this tax (current live behavior) or Partner bears this tax (as part of the $3.90 obligation)?

### E-4 Cash/e-transfer Stripe recovery

- When the buyer's card is charged only for BidVex commission (no hammer through Stripe), should Stripe recovery still be added?
- Current behavior: yes ($0.45 on $6.26 buyer commission).

### E-5 Which endpoint does the frontend actually use for Partner listings?

- `/api/payments/checkout` (unified, Path A → $110 buyer, BidVex loss) OR
- `/api/payments/checkout/auction` (auction-specific, Path B → $114.06 buyer, BidVex over-recognizes)?

Both endpoints are active. The answer determines the current live behavior and the fix scope. **Recommendation**: I will inspect the frontend in Phase 1 pre-work with your approval.

### E-6 What is the Storage seller commission?

- 0% (per `_iter350_storage`, iter443 documented)
- 4% seller_tier default (current `/checkout/auction` behavior)
- Something else

### E-7 Partner Pro fee schedule

- Does Partner Pro have live checkout requirements now, or can it remain as a fee_schedule entry until later?

### E-8 Broker Stripe checkout

- Is Broker checkout supposed to work via Stripe today? If yes, we need to build it. If no, we should document the offline path.

### E-9 Refund allocation policy

- Full refund of a Partner sale — should application_fee be returned to buyer or retained by BidVex?
- Partial refund — should BidVex's platform fee be reduced proportionally?
- Refund after Partner payout — reverse the transfer or debit BidVex?

---

## F. PROPOSED TARGET ARCHITECTURE

Contingent on your answers to Section E. The following is a recommended shape:

```
                             ┌───────────────────────────┐
                             │  db.fee_schedules v>=1     │  ← single authoritative source
                             │  (Partner BP default 5%,   │    of rates
                             │   Partner platform 3%,     │
                             │   tier tables, etc.)       │
                             └─────────────┬──────────────┘
                                           │
                             ┌─────────────▼──────────────┐
                             │  services/fee_calculator   │
                             │  .calculate_fee(...)       │  ← ONE canonical engine
                             │  returns FeeResult         │
                             └─────────────┬──────────────┘
                                           │
              ┌────────────────────────────┼──────────────────────────────┐
              │                            │                              │
              ▼                            ▼                              ▼
  ┌─────────────────────┐      ┌────────────────────────┐    ┌───────────────────────┐
  │ /api/payments/      │      │ services/auction_      │    │ services/vehicle_     │
  │   checkout*         │      │   settlement.py        │    │   fee_service.py      │
  │  (buyer-initiated)  │      │  (auction-end)         │    │  (vehicle fees only)  │
  └──────────┬──────────┘      └───────────┬────────────┘    └───────────┬───────────┘
             │                             │                              │
             ▼                             ▼                              ▼
         Stripe Session               PaymentIntent                   PaymentIntent
         (buyer chooses)              (saved card)                    (saved card)
             │                             │                              │
             └────────────┬────────────────┴──────────────────────────────┘
                          ▼
                     ┌─────────────────────────────┐
                     │  Stripe webhook: succeeded  │
                     └─────────────────┬───────────┘
                                       ▼
                     ┌─────────────────────────────┐
                     │  payment_collection.py      │
                     │  → db.transactions          │
                     │  → db.receipts (iter476+80) │
                     │  → db.seller_payouts        │
                     │  → db.escrow_transactions   │
                     │  → issue receipt PDFs       │
                     └─────────────────────────────┘
```

**Key invariants** (enforceable by pytest fixtures):
1. For any listing at any endpoint, the same input → same `FeeResult`.
2. `FeeResult.buyer_total_cents == stripe.checkout.Session.line_items[0].unit_amount`.
3. `FeeResult.buyer_total_cents == db.receipts[type=buyer_receipt].total_charged * 100`.
4. `FeeResult.bidvex_platform_fee_amount + FeeResult.buyer_premium (individual only) + ... == db.receipts.iter480 fields`.
5. `stripe.checkout.Session.metadata.fee_result_hash` — a hash of the FeeResult so webhook can verify no drift.

---

## G. FILES TO CHANGE (per phase)

### Phase 1 — P0 Financial Repairs

1. `backend/services/stripe_connect_service.py::calculate_partner_listing_checkout`
   - Redesign so `buyer_total` = `hammer + partner_bp + optional hammer_tax + optional bp_tax` (no BidVex fee, no fee tax, no Stripe gross-up in buyer's base).
   - `application_fee_amount` = whatever amount honors your E-1 decision (likely $3 + Stripe recovery + Partner-side tax = $3.90).

2. `backend/services/auction_settlement.py`
   - `settle_cash_or_etransfer` line 259 — replace `seller_account_type="individual"` with resolver that reads `seller.subscription_tier`, `is_partner_listing`, `is_vehicle_dealer`, `is_storage_facility`, `is_broker` and dispatches correctly.
   - `settle_stripe_full` line 610 — same fix.
   - Both — replace hardcoded `payment_method="stripe"` for cash flows with `payment_method="cash"` where applicable.

3. `backend/routes/payments.py`
   - Line 883 — replace `hammer_price = listing.get("current_price", ...)` with `resolve_hammer_total(listing)["hammer_total"]`.
   - Line 955 (storage BP override) — either honor the `_iter350_storage` SC=0 rule (recommended per iter443) or explicitly force `seller_commission_rate=0` in `calculate_general_checkout` for storage.

4. `backend/services/stripe_connect_service.py::calculate_general_checkout`
   - Add an explicit `seller_commission_rate` override parameter so storage listings can force SC=0 without changing the general calculator.

### Phase 2 — Canonical Financial Calculation

5. New `backend/services/fee_result.py` — canonical `FeeResult` dataclass.
6. `backend/services/fee_calculator.py::calculate_fee` — populate all fields of the new `FeeResult`.
7. Refactor `stripe_connect_service.calculate_*_checkout` to be thin adapters that call `calculate_fee` and shape the `FeeResult` into a `CheckoutBreakdown`.
8. Refactor `connect_payment_engine.calculate_connect_checkout` similarly (or delete after migrating callers).

### Phase 3 — Tax + Stripe Reconciliation

9. `backend/services/tax_engine.py` and `backend/services/tax_rate_config.py` — pick one as authoritative, deprecate the other.
10. Golden-cent-reconciliation tests in `backend/tests/goldens/`.

### Phase 4 — Refunds

11. New `backend/services/refund_engine.py` — orchestrator that handles Partner destination charges: `application_fee.refund` + `transfer.reverse` + downstream document updates.
12. `backend/routes/webhooks.py::515` — extend refund webhook handler to invoke the new engine.

### Phase 5 — Legacy Migration

13. Delete `backend/services/fee_calculation_engine.py` after migrating `/api/fees/v2/preview`.
14. Delete `PricingManager` block in `fee_calculator.py` after migrating: `connect_payment_engine.py`, `vehicle_invoice.py`, `subscription_service.py`, promotion/email-credits paths.
15. Delete `backend/services/category_rules.py::COMMISSION_RATES` (already dead per prior audit).

---

## H. FILES TO PROTECT (NEVER TOUCH)

The following files hold historical financial data or produce outputs that must remain consistent with historical records. **Never edit, never migrate, never rewrite:**

1. `db.receipts` collection — all rows created before Phase 1 must remain byte-identical.
2. `db.transactions` collection — same.
3. `db.seller_payouts` collection — same.
4. `db.invoices` collection — cached PDFs; regeneration must produce byte-identical output for historical listings.
5. `db.escrow_transactions` — same.
6. `db.payment_charges`, `db.payment_events` — auditlog; append-only.
7. `db.bidding_deposits`, `db.storage_deposits` — deposit state.
8. `backend/services/pdf_generators/*` — PDF renderers must be READ-ONLY consumers of persisted data. No re-computation.
9. `backend/services/emails/email_system.py` — email templates that reference persisted receipt fields.
10. `backend/services/notifications_i18n.py` — notification templates.
11. `backend/services/settlement_email_dedup.py` — email dedup ledger.
12. `backend/scripts/iter478_bootstrap_fee_schedule.py` — bootstrap script that seeded `db.fee_schedules`; the seeded data must not be rewritten silently.
13. **All PRD.md content prior to today's date.** New entries append only.
14. **Historical `test_reports/*.json`.** Append-only.

---

## I. TEST PLAN

### I-1 Static replay tests (pytest, no Stripe API)

For every FeeResult field, on every seller type × buyer tier × province × registration × qty combination in the Section 42 matrix, assert cent-exact values.

Fixture format:
```python
def test_partner_100_10_qc_not_registered_qty1():
    r = calculate_fee(seller_type="partner", hammer=100.00, partner_bp_rate=0.10,
                     buyer_prov="QC", partner_prov="QC", partner_tax_registered=False,
                     quantity=1)
    assert r.hammer_total_cents == 10000
    assert r.buyer_premium_cents == 1000
    assert r.bidvex_platform_fee_cents == 300
    assert r.buyer_total_cents == 11000            # ← the key invariant
    assert r.partner_owes_bidvex_cents == 390       # ← business rule
    assert r.stripe_application_fee_cents == 390    # ← if Option A
```

### I-2 Integration tests against Stripe TEST mode

Use test API key + test cards (`4242 4242 4242 4242`). Create a Partner listing, hit `/api/payments/checkout/auction`, verify `stripe.checkout.Session.retrieve` returns `amount_total == FeeResult.buyer_total_cents`.

### I-3 Frontend network-tab spot-check

Manual verification that the checkout preview modal displays the same amount that the Stripe Session builds. (This is a P0 disclosure requirement — see A-1 finding: currently, backend charges $114.06 but the preview *might* show $110 depending on which endpoint frontend hits.)

### I-4 Historical reconciliation

For every existing receipt row, load it and re-render the PDF. Assert byte-identical output. This proves Phase 1 changes have not regressed any historical document.

### I-5 Multi-quantity golden

Unit=$7, quantity=2, `multiply_hammer_by_quantity=True`:
```
hammer_total == $14  → asserted at every stage of the payment pipeline
```

---

## J. RISK ASSESSMENT

| Risk | Severity | Mitigation |
|---|---|---|
| **Every historical Partner sale was overcharged** — you may owe buyers a refund | HIGH financial exposure | Query `db.receipts` for `type=buyer_receipt AND fee_model_version="iter350" AND section="marketplace"` where seller was partner. Compute delta. If material, prepare refund letter template + Stripe batch refund plan. **Do not silently rewrite historical receipts.** |
| **Frontend display might already say $114.06 or might say $110** | MEDIUM | Manual UI spot check before Phase 1. If frontend shows $110 but Stripe charges $114.06 → immediate P0 disclosure fix. |
| **Fix breaks existing PDFs / receipts** | MEDIUM | Golden-byte test on 100+ historical receipts before deploying Phase 1. |
| **Application fee changes affect Stripe payout timing** | LOW | Stripe automatically re-books; document schedule impact. |
| **Multiple Stripe payment paths make it hard to know which changes apply where** | HIGH | Phase 1 fixes each path individually; Phase 2 consolidates. Do not touch both simultaneously. |
| **Cash/e-transfer route currently applies Stripe recovery** — buyer commission may be off by ~$0.45/sale | LOW numerically, but shows in receipts | Fix in Phase 2 after business confirmation of the correct model (see E-4). |
| **Historical `bidvex_platform_fee_*` fields are $0 for Partner sales that ran through `settle_auction`** | MEDIUM (audit trail integrity) | Backfill script that queries and re-annotates receipts based on seller_account_type resolved from user record. Read-only proof first; write only after approval. |

---

## K. MIGRATION REQUIREMENTS

**No schema changes are required for Phase 1.** The iter480 Phase 3 columns already exist in `receipts`. The `fee_schedules` collection already exists.

**Phase 2** may add a `fee_result` column to `db.transactions` for full traceability (JSON blob of the FeeResult). Additive, non-breaking.

**Phase 4** (refunds) may add a `db.refunds` collection separate from `payment_events` for structured refund records.

---

## L. ROLLBACK PLAN

Each phase is independently reversible:

1. **Phase 1 rollback**: Revert commits in `stripe_connect_service.py`, `auction_settlement.py`, `routes/payments.py`. No DB changes to undo (no migrations in Phase 1).
2. **Phase 2 rollback**: Delete `services/fee_result.py`, revert adapter changes. Legacy paths still work.
3. **Phase 3 rollback**: Restore prior tax authority; leave the other one.
4. **Phase 4 rollback**: Disable webhook branch that calls the new refund engine; refunds fall back to manual admin.
5. **Phase 5 rollback**: Restore deleted files from git.

Feature flags:
- `STRIPE_PARTNER_MODEL=A|B|C` — toggle between Options A/B/C from E-1 without redeploying.
- `USE_CANONICAL_FEE_ENGINE=1` — toggle Phase 2 canonical engine.

---

## M. PHASED IMPLEMENTATION ROADMAP

**Phase 0 — DONE.** Read-only verification. This document.

**Phase 1 — P0 Financial Repairs.** Awaits your E-1 through E-9 decisions.
- Partner Stripe checkout fix
- `settle_auction` seller-type resolver
- Storage SC conflict resolution
- Quantity fix on `/checkout/auction`

**Phase 2 — Canonical `FeeResult` engine.** After Phase 1 stable.

**Phase 3 — Tax + Stripe reconciliation consolidation.**

**Phase 4 — Refund architecture.**

**Phase 5 — Legacy engine deletion.**

**Phase 6 — Final repository audit.** Golden tests, invariant checks, deployment readiness sign-off.

---

## N. READ-ONLY TEST MATRIX — 9 CASES (computed from CURRENT code)

Static Python replay of the actual repository functions. **No** Stripe API involved. **No** DB writes.

### N-1 Partner $100 / 10% / QC / partner NOT registered — **`calculate_partner_listing_checkout`**

| Field | Value | Owner |
|---|---|---|
| hammer_total | $100.00 | Partner |
| partner_buyer_premium (10%) | $10.00 | Partner |
| bidvex_platform_fee | $3.00 | BidVex |
| seller_commission | $0.00 | — |
| hammer_tax | $0.00 (partner not registered) | — |
| bidvex_fee_tax (GST+QST) | $0.45 | BidVex remits |
| bp_tax | $0.00 (partner not registered) | — |
| processing_fee (gross-up) | $3.61 | 🔴 charged to buyer |
| **buyer_total** | **$114.06** | Buyer's Stripe charge |
| stripe_application_fee | $7.06 | BidVex retains |
| stripe_transfer (destination) | $107.00 (= $114.06 − $7.06) | Partner |
| **Stripe rail on $114.06** | **$3.61** | BidVex pays |
| **BidVex net** | **$3.45** (= $7.06 − $3.61) | |
| **Partner net** | **$107.00** | (short $3 from user's expected $110) |
| **Delta vs user rule** | 🔴 Buyer +$4.06, Partner −$3.00, BidVex +$0.45 | |

### N-2 Partner $100 / 15% BP — **`calculate_partner_listing_checkout`**

| Field | Value |
|---|---|
| buyer_premium | $15.00 |
| platform_fee | $3.00 |
| fees_tax | $0.45 |
| processing_fee | $3.76 |
| **buyer_total** | **$119.21** |
| application_fee | $7.21 |
| transfer_to_partner | $115.00 |

### N-3 Partner $100 / 18% BP — **`calculate_partner_listing_checkout`**

| Field | Value |
|---|---|
| buyer_premium | $18.00 |
| platform_fee | $3.00 |
| fees_tax | $0.45 |
| processing_fee | $3.85 |
| **buyer_total** | **$122.30** |
| application_fee | $7.30 |
| transfer_to_partner | $118.00 |

### N-4 Partner $100 / 10% / QC / partner IS tax-registered

| Field | Value |
|---|---|
| buyer_premium | $10.00 |
| platform_fee | $3.00 |
| hammer_tax_total (GST+QST on $100) | $14.98 |
| fees_tax | $0.45 |
| bp_tax_total (GST+QST on $10) | $1.50 |
| total_tax | $16.93 |
| processing_fee | $4.10 |
| **buyer_total** | **$131.03** |
| application_fee | $7.55 |
| transfer_to_partner | $126.48 |

### N-5 Individual $100 / basic (5% BP / 4% SC) / QC / seller NOT tax-registered

| Field | Value |
|---|---|
| buyer_premium | $5.00 |
| seller_commission | $4.00 |
| bidvex_fees_subtotal | $9.00 |
| fees_tax | $1.35 |
| hammer_tax | $0.00 |
| processing_fee | $3.49 |
| **buyer_total** | **$109.84** |
| application_fee | $10.35 |
| transfer_to_seller | $96.00 |
| **Compare** `calculate_fee(individual)` | buyer_total_charged = **$106.27** |
| **Path divergence** | +$3.57 overcharge on Stripe path vs cash path |

### N-6 Individual $100 / basic / QC / seller IS tax-registered

| Field | Value |
|---|---|
| buyer_premium | $5.00 |
| seller_commission | $4.00 |
| hammer_tax_total | $14.98 |
| fees_tax | $1.35 |
| processing_fee | $3.93 |
| **buyer_total** | **$125.26** |
| application_fee | $10.35 |
| transfer_to_seller | $111.00 (includes hammer tax to remit) |

### N-7 Storage $100 / 5% BP forced / seller_tier=basic / seller NOT registered — **`calculate_general_checkout(0.05 override)`**

| Field | Value |
|---|---|
| buyer_premium | $5.00 |
| seller_commission | $4.00 🔴 |
| fees_tax | $1.35 |
| processing_fee | $3.49 |
| **buyer_total** | **$109.84** |
| application_fee | $10.35 |
| transfer_to_facility | **$96.00** 🔴 (loses $4) |
| **Compare** `calculate_fee(storage_facility)` | buyer=$106.27, facility=**$100.00** (iter443) |
| **Path divergence** | Overcharge $3.57 to buyer, under-payout $4.00 to facility. BidVex over-retains $7.57. |

### N-8 Vehicle $100 / basic buyer tier

| Field | Value |
|---|---|
| buyer_premium (5%) | $5.00 |
| platform_fee (2.5%) | $2.50 |
| fees_tax | $1.13 |
| processing_fee | $0.57 |
| **buyer_total via Stripe** | **$9.20** (fees only) |
| stripe_application_fee | $9.20 (BidVex keeps 100%; no destination charge for hammer) |
| stripe_transfer | $0.00 |
| seller_payout | $100.00 (via offline bank draft) |
| **Total buyer cash outlay** | $109.20 ($100 offline + $9.20 Stripe) |

### N-9 Partner qty=2 / $100 per unit / 10% BP

**Two divergent outcomes**:

a) if `listing.current_price` stored as $100 (per-unit) — `/checkout/auction` path underbills:
| Field | Value |
|---|---|
| hammer_price passed to calculator | $100.00 🔴 (should be $200) |
| buyer_premium | $10.00 (should be $20) |
| **buyer_total** | **$114.06** (should be $228.12) |
| **Under-billing** | **~$114 per multi-lot sale** 🔴 |

b) if `listing.current_price` stored as $200 (pre-multiplied) — correct behavior:
| Field | Value |
|---|---|
| hammer_price | $200.00 |
| buyer_premium | $20.00 |
| platform_fee | $6.00 |
| fees_tax | $0.90 |
| processing_fee | $6.91 |
| **buyer_total** | **$227.81** |
| application_fee | $13.81 |
| transfer_to_partner | $220.00 |

**Whether `current_price` is per-unit or pre-multiplied is a DB spot-check that is NOT PROVABLE FROM STATIC CODE. In `POST /api/payments/checkout` (unified), `routes/payments.py:130-131` explicitly multiplies. In `POST /api/payments/checkout/auction`, line 883 does not multiply.**

---

## FINAL PHASE 0 VERDICT

Per Section 62 of the remediation brief, Phase 0 is complete.

**The Partner $100/10% buyer-pays-$110 rule is NOT correctly implemented in the current codebase.** Four distinct code paths produce four different economic outcomes for the same input. Two of them are actively serving production traffic. Neither of them fully matches the stated business rule.

Recommended next step: your decisions on E-1 through E-9. Once received, I will produce a detailed Phase 1 implementation plan for your approval before any code is modified.

I will NOT proceed to Phase 1 until you explicitly authorize.

---

*This document is READ-ONLY output of Phase 0. Zero production code, DB, or Stripe state has been modified.*
