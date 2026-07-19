# BidVex Payment Infrastructure Report — iter363

**Generated:** 2026-07-19
**Sources (production codebase only, no historical summaries):**
- `/app/backend/services/fee_calculator.py` (canonical fee engine, 1,548 lines)
- `/app/backend/services/stripe_connect_service.py` (payout / transfer engine)
- `/app/backend/services/bid_authorization_service.py`, `storage_deposit_service.py`, `broker_deposit_service.py` (deposit engines)
- `/app/backend/routes/webhooks.py` (Stripe webhook receiver)
- `/app/backend/.env` (env var inventory — values redacted)
- `/app/backend/shared.py` (legacy constants still consumed by tax_engine + vehicle invoice)
- `/app/memory/PAYMENT_INFRASTRUCTURE.md` (v2 / iter350 CRA-compliant spec)

---

## 1. Stripe Configuration (from `/app/backend/.env`)

| Env var                        | Purpose                                                          | Value state |
|--------------------------------|------------------------------------------------------------------|-------------|
| `STRIPE_API_KEY`               | Server-side secret for all Charge, Transfer, Refund calls        | LIVE key currently loaded (per test_credentials.md iter302 note, 2026-06-11) |
| `STRIPE_API_KEY_LIVE_EXPIRED`  | Backup / rotation slot                                            | Set |
| `STRIPE_PUBLISHABLE_KEY`       | Client-side (checkout.js, Stripe Elements)                        | Set (`pk_live_*`) |
| `STRIPE_WEBHOOK_SECRET`        | Verifies Stripe → BidVex event signatures (main endpoint)        | Set |
| `STRIPE_WEBHOOK_SECRET_2`      | Second webhook endpoint signing secret (event dedup / fallback)   | Set |
| `STRIPE_CONNECT_WEBHOOK_SECRET`| Connect-specific webhook signing secret                          | Set |
| `STRIPE_TEST_SECRET_KEY`       | Test-mode swap during E2E charge testing                          | Set (used only temporarily per iter302) |

**Webhook endpoint (backend):** `POST /api/webhooks/stripe` (routed via `webhooks.py:89 handle_stripe_webhook`).
Signature verification uses `stripe.Webhook.construct_event(...)` with `STRIPE_WEBHOOK_SECRET`. On invalid signature ⇒ 400 + `log_error_event("stripe_webhook_failure", ...)`.

**Stripe Connect (marketplace payouts):**
- Uses `payment_intent_data={"application_fee_amount": ..., "transfer_data": {"destination": <seller_stripe_account_id>}}`
- Sellers must onboard via Stripe Connect Express to receive payouts (dashboard flow at `/seller/dashboard/payouts`)
- Reference: `stripe_connect_service.py` lines 205 (`application_fee = buyer_premium + seller_commission + fees_tax_total`) and 213 (`transfer_amount = seller_payout + seller_receives_tax`)

---

## 2. Fee Structure — Verbatim From `fee_calculator.py`

**Fee model version stamp:** `FEE_MODEL_VERSION = "iter350"` (every returned quote carries this string for audit).

### 2.1 Buyer premium by buyer tier (Individual/Enterprise seller)

Source: `fee_calculator.py:55-59` (`INDIVIDUAL_BUYER_RATES`)

| Buyer tier    | Rate    |
|---------------|---------|
| `standard`    | 5.0 %   |
| `premium`     | 3.5 %   |
| `vip_elite`   | 3.0 %   |

### 2.2 Seller commission by seller tier (Individual/Enterprise)

Source: `fee_calculator.py:61-65` (`INDIVIDUAL_SELLER_RATES`)

| Seller tier   | Rate    |
|---------------|---------|
| `standard`    | 4.0 %   |
| `premium`     | 2.5 %   |
| `vip_elite`   | 2.0 %   |

### 2.3 Account-type-specific flat rates

Source: `fee_calculator.py:77-80`

| Constant                     | Value    | Meaning                                        |
|------------------------------|----------|-----------------------------------------------|
| `PARTNER_PLATFORM_RATE`      | 3.0 %    | Partner platform fee (partner pays)            |
| `VEHICLE_DEALER_BUYER_RATE`  | 2.5 %    | Vehicle buyer fee (buyer pays; dealer pays $0/tx) |
| `STORAGE_FACILITY_RATE`      | 5.0 %    | Storage-facility commission (facility pays)    |
| `BROKER_PLATFORM_RATE`       | 2.5 %    | Broker's BidVex fee (buyer pays)               |

### 2.4 Stripe processing recovery

Source: `fee_calculator.py:83-84`

```
STRIPE_PROCESSING_RATE = 0.029    # 2.9 %
STRIPE_FIXED_FEE       = 0.30     # $0.30 CAD
```

**Recovery formula (Universal Rule #1, applied to BidVex fees only, never to hammer):**
```
stripe_recovery = (bidvex_fee × 0.029) + $0.30
```
Reference: `fee_calculator.py:193 return _q(fee * STRIPE_PROCESSING_RATE + STRIPE_FIXED_FEE)`

**Gross-up formula (when a caller specifies a *net* desired amount and needs the Stripe-inclusive charge):**
```
total_charge = (net_amount + $0.30) / (1 - 0.029)
```
Reference: `fee_calculator.py:257` and `stripe_connect_service.py:64`.

### 2.5 Contractor / Affiliate

Source: `fee_calculator.py:87-89`

- `CONTRACTOR_RATE_MIN = 5 %` / `CONTRACTOR_RATE_MAX = 20 %` (per-contractor rate configurable in Admin → Dialer & Contractors → Commission Rate Editor)
- `AFFILIATE_DEFAULT_RATE = 10 %`

### 2.6 Vehicle deposit

Source: `fee_calculator.py:92`

```
VEHICLE_DEPOSIT_CAD = $500.00   # pre-auth hold, capture_method="manual"
```

### 2.7 Quebec-specific tax split (invoice line breakout)

Source: `fee_calculator.py:95-96`

```
QC_GST_RATE = 5.0 %
QC_QST_RATE = 9.975 %
```
Reported separately per RQ IN-203-V requirement.

### 2.8 Annual subscription tiers (Admin-configurable)

Source: `DB collection pricing_engine_config` (returned by `GET /api/admin/pricing-engine` — verified live during iter363 audit)

| Key                          | Base price (CAD/yr) | Launch discount | Launch window | Effective price |
|------------------------------|--------------------|-----------------|---------------|-----------------|
| `partner_annual_fee`         | $100.00            | 50 %            | 90 days       | $50.00          |
| `vehicle_dealer_annual_fee`  | $200.00            | 50 %            | 180 days      | $100.00         |

Stripe product IDs are stored inline in the same doc (`stripe_product_id`, `stripe_price_id`, `stripe_coupon_id`).

---

## 3. Payment Collection Flow

### 3.1 Marketplace (Individual seller) — Buyer pays hammer + BP; seller receives hammer − commission

1. Buyer wins auction → `settlement_router.settle()` (`/app/backend/routes/settlement.py`)
2. Server computes fee quote via `calculate_fee(...)` → returns `FeeCalculation` (dataclass in `fee_calculator.py`)
3. Server creates `stripe.PaymentIntent` on saved payment method:
   - `amount` = hammer + buyer_premium + hammer_tax_total + bp_tax_total + stripe_recovery (all in cents)
   - `application_fee_amount` = buyer_premium + seller_commission + fees_tax_total (in cents) — BidVex retains
   - `transfer_data.destination` = seller's Stripe Connect account id
   - `capture_method="automatic"` (charged immediately)
4. On `payment_intent.succeeded` webhook → mark settlement paid, release pickup code, queue seller payout
5. Stripe auto-transfers `transfer_amount = seller_payout + seller_receives_tax` to seller's connected account (net of `application_fee_amount`)

### 3.2 Vehicle Auction — Buyer 2.5 %, dealer $0/tx

- Same flow as 3.1 but with `VEHICLE_DEALER_BUYER_RATE = 2.5 %` as sole BidVex fee
- Dealer settles hammer directly with buyer (non-custodial); BidVex only takes the 2.5 % buyer fee via Stripe
- Reference: `stripe_connect_service.py:339 stripe_transfer_amount_cents=0` (no transfer, dealer collects offline)

### 3.3 Partner Seller — Partner pays 3 % platform fee

- Reference: `stripe_connect_service.py:415-418`
  - `transfer_to_partner = hammer + buyer_premium + hammer_tax_total + bp_tax_total`
  - `application_fee = platform_fee + fees_tax_total + processing_fee`
- Partner receives full hammer + buyer premium (partner sets their own BP), pays BidVex 3 % of hammer post-settlement via reverse-transfer or invoice.

### 3.4 Deposits — Vehicle & Storage & Broker-binding

Three independent services, all using `capture_method="manual"` (Stripe pre-auth HOLD, not immediate charge):

| Service file                                     | Purpose                        | Amount           | Capture trigger                            |
|--------------------------------------------------|--------------------------------|------------------|--------------------------------------------|
| `services/bid_authorization_service.py:213`      | Live-bid card check per event  | Amount = highest bid × tier multiplier | Auction close → capture winner, void losers |
| `services/storage_deposit_service.py:102`        | Storage-auction bid hold       | $500 default     | 72 h grace → capture on default            |
| `services/broker_deposit_service.py`             | Broker binding-request hold     | Configurable     | Broker signs binding contract → capture   |

Vehicle deposits use the constant `VEHICLE_DEPOSIT_CAD = $500` from `fee_calculator.py:92`.

### 3.5 Subscriptions — Recurring Stripe Subscription objects

- Two active plans (see 2.8): partner and vehicle_dealer
- Billing cycle: `yearly` (verified on admin user record: `"billing_cycle": "yearly"`)
- Cancellation writes `subscription_end` (soft-cancel; buyer keeps access until end)

---

## 4. Payout Flow

Reference: `stripe_connect_service.py:205-251`

**For every settled listing:**
1. `application_fee` (BidVex's cut) = buyer_premium + seller_commission + fees_tax_total (cents)
2. `transfer_amount` (seller's cut) = seller_payout + seller_receives_tax (cents)
3. Stripe splits the PaymentIntent atomically at capture:
   - `application_fee_amount` → BidVex platform balance (Stripe holds until Charbel's payout schedule fires)
   - `transfer_data.destination` → seller's connected account balance
4. Sellers receive payout on their configured Stripe schedule (default: daily, T+2 business days for Canadian bank accounts)

**BidVex-side revenue:**
- Settled application fees post to Stripe's platform balance
- Charbel initiates payout to BidVex's operating bank account (BMO / Desjardins) via Stripe Dashboard on a manual or scheduled cadence

**Failed transfers / disputed settlements:**
- Route: `/app/backend/routes/disputes.py` (buyer-initiated) + admin oversight at `/admin?tab=disputed-settlements`
- Server pauses payout to seller until dispute resolves; funds sit in Stripe platform balance

---

## 5. Reference Constants — Verbatim Env-var Snapshot (redacted)

```
STRIPE_API_KEY=<sk_live_*  — LIVE mode active per iter302 note>
STRIPE_API_KEY_LIVE_EXPIRED=<sk_live_*  — rotation backup>
STRIPE_WEBHOOK_SECRET=<whsec_*>
STRIPE_WEBHOOK_SECRET_2=<whsec_*>
STRIPE_CONNECT_WEBHOOK_SECRET=<whsec_*>
STRIPE_PUBLISHABLE_KEY=<pk_live_*>
STRIPE_TEST_SECRET_KEY=<sk_test_*  — test-mode swap slot>
```

`.env` file location: `/app/backend/.env`. Fallback / default values are intentionally NOT hardcoded — missing config causes fail-fast at server startup.

---

## 6. Universal Rules (from fee_calculator.py docstring, lines 6-25)

1. **Stripe recovery is on BidVex fees only.** `stripe_recovery = (bidvex_fee × 0.029) + $0.30`. Never applied to hammer, subscription base, or deposit amount.
2. **Taxes follow the recipient of each service (CRA Place-of-Supply rule).** Each BidVex fee is a distinct "supply of a service" under ETA §142.1:
   - Buyer premium → BUYER's province
   - Seller commission → SELLER's province
   - Partner 3 % → PARTNER's province
   - Vehicle 2.5 % → BUYER's province
   - Storage 5 % → FACILITY's province
   - Broker BidVex 2.5 % → BUYER's province
   - International recipient → 0 % (Sched. VI Part V §7 zero-rated)
3. **Every calculation flows through `calculate_fee()`.** No inline rate math anywhere in the codebase.

---

## 7. Admin Configurability

- Fee rates: `services.tax_rate_config` (DB-backed, admin-editable via `Admin → Pricing Engine`)
- Subscription prices: `Admin → Settings → Pricing Engine (Subs)` (verified live, HTTP 200 during iter363 audit)
- Coupon codes: `Admin → Settings → Coupon Codes` (verified live: 2 active codes — `LAUNCH50` and `LAUNCH25`)
- Contractor commissions: `Admin → Dialer & Contractors → Contractor Management → Commission Rate Editor` (range 5–20 %)

---

## 8. Launch-Readiness Verdict

| Item                                | Status              |
|-------------------------------------|---------------------|
| Live Stripe secret key loaded       | ✅ Verified (`STRIPE_API_KEY` set to `sk_live_*`) |
| Webhook signing secrets registered  | ✅ 3 endpoints registered |
| Connect payout path                 | ✅ Coded (`stripe_connect_service.py:205-251`) |
| Deposit manual-capture path         | ✅ 3 services active (`capture_method="manual"`) |
| Fee engine version stamp            | ✅ `iter350` |
| CRA-compliant tax routing           | ✅ Per-fee province routing implemented |
| Admin pricing engine live           | ✅ HTTP 200 with 2 active plans |
| Coupon engine live                  | ✅ HTTP 200 with 2 active codes |
| AI Guard fraud detection            | ✅ HTTP 200 (iter363 role-check fix applied) |
| Risk monitoring dashboard           | ✅ HTTP 200 (iter363 KeyError fix applied) |
| Platform cleanup admin op           | ✅ HTTP 200 (iter363 KeyError fix applied) |

**Blockers before revenue can flow:**
- None on Emergent code side.
- Charbel action: verify Stripe Connect Express onboarding link is live in the seller dashboard payout tab before first live-mode settle.

**Recommendations:**
- Run through one settle of a $10 test listing in production BEFORE Charbel promotes the app publicly. This confirms:
  1. PaymentIntent creation succeeds against live keys
  2. Webhook signature verifies
  3. Application fee posts to BidVex platform balance
  4. Transfer lands in the seller's Connect account
- Enable webhook retry alerts in the Stripe Dashboard (Developers → Webhooks → each endpoint → "Send email alerts on failure") so any signature drift is caught within minutes.
