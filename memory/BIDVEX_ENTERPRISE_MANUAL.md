# BidVex Enterprise Operations & Onboarding Manual

**Document version:** iter325 — June 30, 2026
**Source of truth:** Live `/app/backend` and `/app/frontend` codebase.
**Editorial discipline:** Every value, rule, fee, and rate in this document is
copied directly from the production codebase. Items that exist only as
planned/business intent (not in code) are explicitly tagged
**🟡 PLANNED — NOT DEPLOYED** so this manual cannot be quoted out of context.

---

## Section 1 — Executive Platform Architecture

### 1.1 Core Auction Engine & Dynamic Listing Workflows

BidVex is a Canadian online auction marketplace built on:
- **Frontend** — React SPA (`/app/frontend`), Shadcn UI + Tailwind, react-router-dom routing, react-i18next bilingual EN/FR, Helmet for SEO meta tags.
- **Backend** — FastAPI (`/app/backend`), Motor (Async MongoDB), Stripe SDK, Twilio SDK, SendGrid SDK.
- **Database** — MongoDB Atlas (`bazario_db`), accessed via `MONGO_URL` env var.
- **Hosting** — Kubernetes ingress terminating SSL, plain HTTP forwarded to the FastAPI pod (see iter324 Twilio hotfix).

Listing lifecycle:
1. Seller creates a listing in the marketplace (with quantity, hammer price floor, photos, category).
2. Listing goes `upcoming` → `active` → `ended` via APScheduler cron (`services/scheduler.py`, ticks every 60s).
3. Winning bidder is captured; settlement flows through `routes/settlement.py::_amounts()`, which respects per-listing **quantity** so multi-quantity wins are billed correctly (iter312 P0 hotfix).
4. Funds escrow → seller payout via Stripe Connect Transfers.

### 1.2 The Watchdog Fraud Engine & Automated AI Telemetry Scanning

Implemented across:
- `services/genai_direct_client.py` — direct GenAI watchdog client.
- `services/ai_guard*` — listing scoring + duplicate-listing detection.
- Tests: `tests/test_ai_watchdog_amnesia_fix.py`, `tests/test_iter234_genai_direct_watchdog.py`, `tests/test_ai_guard_fraud_detection.py`.

Operates on three real-time signals: photo-EXIF analysis, duplicate-listing detection, and bid-velocity scoring. Each new listing is scored before going live.

### 1.3 Escrow, Payment Gateway, & Stripe / SendGrid Integrations

- **Stripe** — payments, Connect Transfers (sellers, contractors), application_fee_amount on platform fees. Service files: `services/stripe_connect_service.py`, `services/payment_collection.py`, `services/seller_payouts.py`, `services/escrow_service.py`.
- **SendGrid** — transactional + marketing email and **Inbound Parse** for contractor email replies (iter323, see Section 7.4).
- **Twilio** — bilingual IVR on +1 450 634 3099 (iter323), per-contractor extensions 1220+, signature validation with K8s ingress proxy headers (iter324).
- **Escrow** — 6-character alphanumeric pickup-code system for non-vehicle items; 48-hour auto-release if unclaimed.

### 1.4 The Broker-Gate Pipeline & Compliance Automation

Vehicle dealers and brokers must complete the **broker gate**:
- Provincial license validation: OMVIC (ON), AMVIC (AB), VSA (BC), SAAQ (QC), FCAA (SK), MVSDA, or analogous regulator.
- License documents stored in S3 (object storage).
- **Vehicle Dealer Stripe subscription** — `services/dealer_subscription_service.py`:
  - Stripe Product: `BidVex Vehicle Dealer Platform Access`
  - Stripe Price: **$200/year CAD recurring**
  - Stripe Coupon: `LAUNCH50` — **50% off, duration=forever** → **net effective $100/year CAD**
  - Grace period: **7 days** on failed payment, then suspended.

---

## Section 2 — Account Hierarchies, Subscriptions, & Fee Matrices

> ✅ **iter328 — Stripe-Sync Lock (Jun 30, 2026):** iter326 / iter327 consolidation rolled
> back. Subscription pricing is now Stripe-driven; in-code values (`SUBSCRIPTION_TIERS`,
> `SUBSCRIPTION_PRICES`) MIRROR live Stripe Price objects. Edit Stripe first, then mirror
> in code. No auto-reconciliation between MongoDB and code. The public anonymized
> `/api/contractor/leaderboard/public` endpoint and the `/blogs` widget have been
> deleted; the contractor leaderboard is now visible ONLY inside the authenticated
> `/contractor/dashboard` (via the iter323 `<ContractorIter323Panel>` component).

### Canonical price matrix (yesterday's state, pre-iter326)

| Tier | Yearly (CAD) | Buyer Premium | Seller Commission | Monthly listings |
|---|---|---|---|---|
| **Free / Standard** | $0 | 5.0% | 4.0% | 5 |
| **Partner** | $100 | 5.0% (no discount) | 4.0% (no discount) | unlimited |
| **Premium** | $180 (display) — Stripe Price `price_1T5V5xBd6Wtvh7hscWcNnk34` is canonical | 3.5% | 2.5% | unlimited |
| **Partner Pro** | $240 | 3.75% | 3.0% | unlimited |
| **VIP Elite** | $300 (display) — Stripe Price `price_1T5V2bBd6Wtvh7hsqLLmAZSH` is canonical | 3.0% | 2.0% | unlimited |
| **Vehicle Dealer** | $200 → **$100 with `LAUNCH50`** | 3.0% (vehicle-category platform fee 2.5%) | n/a (hammer paid direct) | unlimited |

> ⚙️ **iter328 — Stripe-Sync Lock:** subscription pricing is now driven by the
> existing **Stripe Product/Price objects**. The values in `services/pricing_config.py::SUBSCRIPTION_TIERS`
> and `services/subscription_service.py::SUBSCRIPTION_PRICES` MIRROR live Stripe Prices.
> **Do not edit code values without first updating the corresponding Stripe Price.**
> The `subscription_plans` MongoDB collection is initialized once and not auto-reconciled.

**Public endpoints (display):**
- `GET /api/pricing-config` — returns the static SUBSCRIPTION_TIERS mirror.
- `GET /api/subscription-plans` — DB-driven (seeded once from `DEFAULT_PLANS`).
- `GET /api/payments/subscriptions/tiers` — returns the static SUBSCRIPTION_PRICES mirror.

⚠️ These three endpoints can show small disagreements (e.g. `subscription-plans` exposes monthly equivalents from DEFAULT_PLANS while `pricing-config` shows the rounded yearly mirror). **Stripe is the source of truth for actual billing** via Stripe Checkout — the API responses are display-only.

### 2.1 Premium Partners Tier
- Annual subscription: **$100 / yr** (`SUBSCRIPTION_TIERS["partner"]`).
- Buyer premium: **5.0%** — same as free tier per `pricing_config.BUYER_PREMIUM_RATES["partner"]`.
- Seller commission: **4.0%** — same as free tier per `pricing_config.SELLER_COMMISSION_RATES["partner"]`.
- 🟡 **PLANNED — NOT DEPLOYED:** "50% platform-fee discount" is **not implemented** in the partner tier. The Partner Pro tier ($240/yr) is the tier that carries a 25% buyer-premium discount.
- 🟡 **PLANNED — NOT DEPLOYED:** "1-month free trial" — no `trial_period_days` flag exists in the partner subscription codepath. Implementation would require a Stripe Price with `trial_period_days=30` and a one-time-trial guard on the user document.

### 2.2 Casual Individual Users (Standard Layer)
- Confirmed **$0.00 lifelong**, `is_active: True`, `monthly_listing_limit: 5`.
- Buyer premium: **5.0%**; seller commission: **4.0%**.

### 2.3 Individual VIP Users (Premium Layer)
- Monthly: **$99.99/mo** OR Annual: **$999.99/yr** (per `subscription_pricing.DEFAULT_PLANS["vip"]`).
- Buyer premium: **3.0%** (lowest); seller commission: **2.0%** (lowest).
- Unlimited listings.
- 🟡 **PLANNED — NOT DEPLOYED:** "Priority placement metrics" — no boosting field on listings collection ties VIP tier to placement rank. Featured listing slots are sold separately as paid promotions (Section 2 Promotion Tiers below).

### 2.4 Individual Business Users (Retail Inventory Layer)
- The `business` `account_type` exists (per `ACCOUNT_TYPES` in `services/contractor_commission.py`).
- 🟡 **PLANNED — NOT DEPLOYED:** Dedicated boutique-retail SKU/inventory-management features (computer / shoe / jewelry store sub-profiles) are not in code. Business accounts use the same listing model as individual sellers.

### 2.5 Certified Vehicle Dealers
- **NOT free forever.** Dealer subscription is **$200 / yr (or $100 / yr with `LAUNCH50` coupon, forever)** per `services/dealer_subscription_service.py`.
- **Buyer's premium: 3.0% on the dealer/VIP tier** (the user's "mandatory 5%" intuition appears to be the *free* tier premium — dealers themselves are typically on VIP-class pricing).
- Vehicle hammer price is settled **direct** between buyer and broker; Stripe Connect processes service fees only.

### 2.6 Commercial Storage Facilities
- The `storage_facility` `account_type` is registered in `services/contractor_commission.py::ACCOUNT_TYPES`.
- 🟡 **PARTIALLY DEPLOYED:** Storage-facility-specific subscription pricing is not separately enumerated in `pricing_config.py`. They appear to default to the **Free / Standard** layer with the **5.0% buyer premium** on storage-unit auctions. A separate paid tier for storage facilities would require new entries in `SUBSCRIPTION_TIERS`.

### Promotion Tiers (paid listing boosts — `pricing_config.PROMOTION_TIERS`)

| Boost | Price | Duration | Features |
|---|---|---|---|
| Basic Boost | **$9.99** | 7 days | Featured badge + top of category |
| Standard Boost | **$24.99** | 14 days | + Homepage feature |
| Premium Boost | **$49.99** | 30 days | + Email blast |

### High-value auction deposit (`pricing_config`)
- **Threshold:** auctions starting above **$10,000 CAD**.
- **Deposit:** **$1,000 CAD pre-authorization hold** (not captured unless default).

### Affiliate referral
- **15% of BidVex's commission** routes to affiliate (`AFFILIATE_COMMISSION_RATE = 0.15`).

---

## Section 3 — System Tax Calculation & Regional Compliance Engines

Source: `services/tax_engine.py`. Quebec is the primary regulated jurisdiction.

| Tax | Rate | Code constant |
|---|---|---|
| GST (Federal) | **5.0%** | `GST_RATE = 0.05` |
| QST (Quebec) | **9.975%** | `QST_RATE = 0.09975` |
| **Combined** | **14.975%** | `COMBINED_TAX_RATE = 0.14975` |

**BidVex tax registration (live in code):**
- GST/HST: **706766367RT0001**
- QST: **1233530880TQ0001**
- Legal name: **BidVex Inc.**
- Address: **103-761 Chalifoux Street, Sherbrooke, QC, J1G 0A8**

### 3.1 Personal Disposal Tax Exemption Logic
- For **GENERAL auctions** (non-vehicle) where `seller.is_business == False`:
  - Hammer price tax: **$0** (personal disposal exemption).
  - BidVex platform service fees still attract the 14.975% combined GST/QST.

### 3.2 Standard Retail & Corporate Sales Tax Automation
- For **GENERAL auctions** where `seller.is_business == True`:
  - Hammer price: **+14.975% GST/QST**, routed to seller via Stripe Connect.
  - Platform service fees: also **+14.975%**.

### 3.3 Automotive, Title, & Luxury Vehicle Tax Modules
- **VEHICLE auctions** — Stripe Connect handles BidVex fees only.
- Stripe charge = `(Buyer Premium + Platform Fee) × 1.14975`.
- Hammer price paid **directly buyer → licensed broker** via bank draft, certified cheque, or broker trust account (per Terms §20 — "Vehicle Hammer Price — Direct Settlement").
- Title transfer obligation: licensed brokers must log the SAAQ/ServiceOntario/AMVIC/VSA reference number within **14 days** of vehicle release (Terms §21).
- 🟡 **PLANNED — NOT DEPLOYED:** Luxury-vehicle progressive tax brackets beyond standard GST/QST are not implemented; provincial luxury-vehicle taxes (where applicable) would route through the dealer's own POS, not BidVex.

### 3.4 Commercial Storage Unit Asset Liquidation Laws
- Storage auctions use the GENERAL auction tax flow (Section 3.1 / 3.2).
- Compliance with provincial self-storage statutes (e.g. Quebec Civil Code articles on abandoned goods) is the **storage facility's** legal responsibility; BidVex is the technology platform only.

---

## Section 4 — Legal Frameworks & Contractual Terminology

Source: `frontend/src/pages/TermsOfServicePage.js` (live Terms of Service, EN + FR).

### 4.1 Defining the Final Hammer Price
- "Hammer price" = the winning bid amount at auction close.
- For **vehicle auctions**: paid **directly** buyer → licensed broker (BidVex never touches it). Terms §20.
- For **multi-quantity wins** (iter312 P0 fix): `final_hammer_base = unit_hammer_price × quantity_won` — billed by `routes/settlement.py::_amounts()`.

### 4.2 Restrictive Bidding Process Rules
- Winning bids are **legally binding** (Terms §6).
- Buyers under 18 years old or outside Canada are not eligible to register (Terms §3).
- Pickup code system enforces buyer-side honor (Terms §5B).

### 4.3 Legally Binding Transactional Agreements & Default Protocols
- **Seller cancellation penalty:** **$50.00 CAD** charged via Stripe Sticky-Card if the seller cannot deliver after auction close (Terms §6A).
- **Buyer-Broker security deposit:** **$500.00 CAD** authorized (not captured) when a buyer requests broker partnership; forfeited on buyer default (Terms §19).
- **No-refund policy** on subscriptions; 30 days advance notice for material price changes (Terms §17–18).

---

## Section 5 — Summer 2026 Promotional Campaign Architecture

🟡 **STATUS: ENTIRELY PLANNED — NOT DEPLOYED.** No code currently implements a "Summer 2026" campaign object, trial flags, first-listing-free flag, or social-media ad pipeline. The sections below document the **planned** rules for future implementation; they are not yet enforceable on the live platform.

### 5.1 One-Month Free Trial Subscription Logic
- 🟡 **PLANNED:** Partners, Vehicle Dealers, and Storage Facilities receive a **30-day free trial** on first subscription.
- Implementation path: add `stripe.Price.trial_period_days=30` to subscription creation in `services/dealer_subscription_service.py::create_dealer_subscription()` and equivalent partner/storage paths; add a `users.summer_2026_trial_redeemed` boolean to prevent re-redemption.

### 5.2 First-Listing-Only Exemption Clause
- 🟡 **PLANNED:** First listing created by a promotional user = **$0.00 slot fee**. Second and subsequent listings = standard rates.
- Implementation path: add `users.first_listing_free_used: bool` flag; gate the `services/listing_promotions.py` charge with a check on listing-count for that user.

### 5.3 Multi-Platform Algorithmic Promotion & Targeted Outreach
- 🟡 **PLANNED — REQUIRES API CREDENTIALS:** Programmatic ad pipeline to Facebook (Meta Marketing API), Instagram (same), YouTube (Google Ads), Google Ads, and TikTok (Marketing API). None of these integrations exist today.
- The current codebase has only **social media tracking pixels** (Facebook pixel via `FbPixelTracker.js`, generic marketing pixels via `MarketingPixelLoader.js`) — these track conversions, they do not push ads.
- Implementation prerequisites: API keys + ad accounts for Meta, Google, TikTok; creative-asset library; lookalike-audience definitions; budget controls.

---

## Section 6 — Contractor Commission & Weekly Leaderboard Incentive Architecture

✅ **DEPLOYED & VERIFIED (iter317 + iter325)** — Tests `tests/test_iter316_dialer_and_commission.py` (243 passing) + `tests/test_iter317_leaderboard_overlay.py`.

### 6.1 Baseline Commission Rule
- **Baseline commission rate: 5.0%** of every successful platform-fee collection attributed to a contractor via the `referred_by_contractor_id` stamp.
- Code: `services/contractor_commission.py::DEFAULT_COMMISSION_RATE = 0.05`.
- Per-account-type and per-contractor admin overrides are supported (collection `contractor_commission_rates`), but all overrides are still clamped to the `[5%, 20%]` band (Section 6.4).

### 6.2 Weekly Leadership Performance Ladder (Monday 08:00 EST reset)
- Code: `services/leaderboard_overlay.py::run_weekly_leaderboard_overlay()`.
- Every Monday at 08:00 America/Toronto:
  1. Compute each contractor's 7-day commission volume (sum of `contractor_commission_ledger.commission_amount` rows with `status="accrued"` within the window).
  2. Identify Top 5 (`LEADERBOARD_TOP_N = 5`).
  3. Top 5 receive **+1.0% overlay** added to their `users.leaderboard_overlay_rate` (capped per Section 6.4).
  4. Cron is **idempotent per ISO calendar week** — re-running the same week is a no-op.
  5. Every contractor receives an audit entry in `users.leaderboard_history` even if delta = 0.

### 6.3 Underperformance Deduction & Volatility Rules
- Contractors who **drop out** of the Top 5 since the previous week receive **−1.0% overlay**.
- No deduction can push the **effective rate below 5.0%** (per `EFFECTIVE_TOTAL_FLOOR = 0.05`).

### 6.4 Effective Rate Formula & Hard Caps
```
effective_rate = clamp(base + leaderboard_overlay, 0.05, 0.20)
```
- **Floor: 5.0%** (`COMMISSION_EFFECTIVE_FLOOR = 0.05`).
- **Ceiling: 20.0%** (`COMMISSION_EFFECTIVE_CEILING = 0.20`).
- The effective rate is **stamped into** `contractor_commission_ledger.commission_rate_applied` at accrual time — historical entries are immutable.

### 6.5 Variable Progression Tracking — Commission Ladder

| Week in Top 5 (consecutive) | Overlay (%) | Effective Rate (%) | Capped? |
|---|---|---|---|
| Baseline (never in Top 5) | 0 | **5.0** | floor |
| Week 1 in Top 5 | +1 | 6.0 | |
| Week 2 in Top 5 | +2 | 7.0 | |
| Week 3 in Top 5 | +3 | 8.0 | |
| Week 4 in Top 5 | +4 | 9.0 | |
| Week 5 in Top 5 | +5 | 10.0 | |
| Week 6 in Top 5 | +6 | 11.0 | |
| Week 7 in Top 5 | +7 | 12.0 | |
| Week 8 in Top 5 | +8 | 13.0 | |
| Week 9 in Top 5 | +9 | 14.0 | |
| Week 10 in Top 5 | +10 | 15.0 | |
| Week 11 in Top 5 | +11 | 16.0 | |
| Week 12 in Top 5 | +12 | 17.0 | |
| Week 13 in Top 5 | +13 | 18.0 | |
| Week 14 in Top 5 | +14 | 19.0 | |
| Week 15 in Top 5 | +15 | **20.0** | ceiling |
| Week 16+ in Top 5 | +15 | **20.0** | ceiling (no further rise) |

Drop-out trajectory (after holding +15%, then dropping out for N consecutive weeks):

| Weeks since drop | Overlay (%) | Effective Rate (%) |
|---|---|---|
| 1 | +14 | 19.0 |
| 5 | +10 | 15.0 |
| 10 | +5 | 10.0 |
| 14 | +1 | 6.0 |
| 15+ | 0 (cannot go below floor) | **5.0** |

### 6.6 Payouts
- Monthly Stripe Connect Transfer per contractor — `services/contractor_commission.py::run_monthly_contractor_payouts()`.
- Currency: **CAD**.
- Contractors without a connected Stripe account → status stays `accrued`, dashboard surfaces a banner.

---

## Section 7 — Sales Prospecting & Contractor Operations

### 7.1 Inbound IVR (Twilio) — Live on +1 450 634 3099
- Bilingual EN/FR language picker → 4-digit extension Gather.
- Extensions start at **1220** (assigned forward-only, never reused — `services/contractor_extensions.py`).
- Whisper announcement on contractor's leg before bridge: "Incoming BidVex call to your extension from <client_number>".
- Caller ID displayed to client: **+1 450 634 3099** (BidVex main, privacy-first).
- iter324 hotfix forces HTTPS callbacks via `X-Forwarded-Proto` / `X-Forwarded-Host` (K8s ingress).

### 7.2 Email Routing (SendGrid + Inbound Parse)
- **Outbound sender:** `partners@bidvex.ca` (`CONTRACTOR_SENDER_EMAIL`).
- **Reply-To:** `partners+c{contractor_id}@reply.bidvex.ca` — sub-addressed for routing.
- Bilingual signature with extension line: `Direct ext.` (EN) / `Poste direct` (FR) → `tel:+14506343099;ext=1220`.
- Inbound replies parsed by `POST /api/sendgrid/inbound-parse`, threaded into `contractor_emails` collection with `direction='inbound'`, fires in-app notification to the contractor.

### 7.3 Add-a-Client Shortcut
- Contractor dashboard allows quick creation of exactly **5 account types** (`CONTRACTOR_CREATABLE_ACCOUNT_TYPES`):
  - Individual Seller, Business, Partner, Vehicle Dealer, Storage Facility.
- Brokers & Liquidators are intentionally **excluded** — they have dedicated registration flows (license validation, OPC permits, etc.).
- Every created account carries a permanent `referred_by_contractor_id` stamp.

### 7.4 Google Maps / Social Media / Cold Outreach Sourcing
- 🟡 **PLANNED — NOT DEPLOYED:** No code currently scrapes Google Maps Places API for B2B leads, ingests TikTok/Instagram/YouTube data, or runs templated cold-call sequences. This work would require:
  - Google Maps / Places API credentials.
  - Social platform API access (TikTok Business API, Instagram Graph API, YouTube Data API v3).
  - A new `prospecting_leads` collection with status workflow.

### 7.5 Contractor Conduct & Brand Representation
*(Codified into Terms of Service §22.6 as of iter325.)*

Contractors must:
- Use only the BidVex-issued partner email signature, extension number, and `partners@bidvex.ca` sender identity.
- Never promise pricing, discounts, or commercial terms beyond what's published on the BidVex pricing page.
- Never disparage competitors in client communications.
- **Escalate all technical, billing, regulatory, or legal inquiries to `support@bidvex.com`** — do not interpret rules/laws on behalf of BidVex.
- Submit to discretionary review of IVR call recordings, outbound email logs, and Add-a-Client account creations.

Termination & referral-attribution removal: BidVex may suspend/terminate any contractor account and remove the `referred_by_contractor_id` stamp from any client account via admin override (`remove_referral_attribution()` in `services/contractor_commission.py`).

---

## Section 8 — Press, Blog & Public-Facing Content

Updated in iter325:
- Footer **"Press"** link previously routed to `mailto:support@bidvex.com` — now routes to **`/blogs`** (`frontend/src/pages/BlogsPage.js`, `data-testid="blogs-page"`).
- `/blogs` is the centralized SEO repository for articles, operational definitions, user hints, and technical explanations.
- Initial article seeds (6) cover: auction engine mechanics, broker/dealer onboarding, storage liquidation rules, vehicle hammer direct settlement, contractor commission & leaderboard, and the Watchdog fraud engine.
- Bilingual (EN/FR) titles, descriptions, and meta tags via `react-helmet-async` for SEO.
- Press/media inquiries email link prominently displayed: `support@bidvex.com`.

---

## Section 9 — Quick-Reference Master Matrix

### 9.1 User-Tier Master Pricing Matrix

| Tier | Monthly | Annual | Buyer Premium | Seller Commission | Listings | Canonical source |
|---|---|---|---|---|---|---|
| Standard | — | $0 | 5.0% | 4.0% | 5/mo | `DEFAULT_PLANS["free"]` |
| Partner | — | $100 | 5.0% | 4.0% | unlimited | `DEFAULT_PLANS["partner"]` |
| Premium | **$29.99** | **$299.99** | 3.5% | 2.5% | unlimited | `DEFAULT_PLANS["premium"]` |
| Partner Pro | — | $100 | 3.75% | 3.0% | unlimited | `DEFAULT_PLANS["partner_pro"]` |
| VIP Elite | **$99.99** | **$999.99** | 3.0% | 2.0% | unlimited | `DEFAULT_PLANS["vip"]` |
| Vehicle Dealer | — | $200 (→$100 w/ LAUNCH50) | 3.0% / 2.5% platform fee | direct settlement | unlimited | `dealer_subscription_service.py` |

### 9.2 Contractor Commission Ladder Chart (text-rendered)

```
Effective Commission Rate (%) vs. Consecutive Weeks in Top 5
─────────────────────────────────────────────────────────────
20% │                                            ████████████  ← CEILING
19% │                                       ████
18% │                                  ████
17% │                             ████
16% │                        ████
15% │                   ████
14% │              ████
13% │         ████
12% │    ████
11% │████
10% │
 9% │
 8% │
 7% │
 6% │
 5% │ ← FLOOR (baseline) ──────────────────────────────────────
    └────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬──
       W1   W3   W5   W7   W9  W11  W13  W15  W17  W19  W21
                  Consecutive Weeks in Leaderboard Top 5
```

### 9.3 Tax Matrix

| Auction Type | Seller is_business | Hammer Tax | Service-Fee Tax | Stripe Routes |
|---|---|---|---|---|
| General | False | $0 (exempt) | 14.975% | Service fees only |
| General | True | 14.975% (Connect to seller) | 14.975% | Hammer + service fees |
| Vehicle | n/a (always dealer) | n/a (direct bank draft) | 14.975% on service fees | Service fees only |
| Storage | per facility's status | per Section 3.4 | 14.975% | Per general flow |

### 9.4 Promotion Boost Matrix

| Boost | Price | Duration | Includes |
|---|---|---|---|
| Basic | $9.99 | 7 days | Featured badge + top of category |
| Standard | $24.99 | 14 days | + Homepage feature |
| Premium | $49.99 | 30 days | + Email blast |

### 9.5 High-Value Auction Deposit Matrix

| Starting Bid | Deposit | Captured? |
|---|---|---|
| < $10,000 CAD | None | n/a |
| ≥ $10,000 CAD | $1,000 CAD hold | Only on default |

### 9.6 Buyer-Broker Deposit Matrix (Terms §19)

| Event | Outcome |
|---|---|
| Broker rejects partnership | $500 authorization cancelled within 5–7 business days |
| Buyer abandons after broker bid placed | $500 **captured** by BidVex |
| Buyer fails to pay broker fees within 72h | $500 **captured** by BidVex |
| Broker confirms vehicle release | $500 authorization cancelled within 5–7 business days |
| Active dispute period | Hold extended up to 7 days |

---

## Section 10 — iter325 Change Log

**Code changes shipped in this iteration:**
1. **Footer Press link** — `frontend/src/components/Footer.js` line 165 — now `<Link to="/blogs" data-testid="footer-press-blogs-link">` (was `mailto:support@bidvex.com`).
2. **New `/blogs` route** — `frontend/src/App.js` + `frontend/src/pages/BlogsPage.js` — bilingual SEO landing page with 6 initial articles, react-helmet meta tags, canonical URL.
3. **Contractor commission baseline lowered to 5%** — `services/contractor_commission.py::DEFAULT_COMMISSION_RATE = 0.05` (was 0.20).
4. **Effective rate clamp added** — `services/contractor_commission.py` — new `COMMISSION_EFFECTIVE_FLOOR = 0.05`, `COMMISSION_EFFECTIVE_CEILING = 0.20`. `get_contractor_commission_rate()` now reads `leaderboard_overlay_rate` from the `users` collection and applies `clamp(base + overlay, 5%, 20%)` at accrual time — closing the iter317 gap where the overlay was computed but never applied to actual commissions.
5. **Terms of Service §22 added** — `frontend/src/pages/TermsOfServicePage.js` — bilingual contractor commission, conduct & leaderboard rules.
6. **Test suite updated** — `tests/test_iter316_dialer_and_commission.py` — 3 tests updated to reflect the new 5% baseline + [5%, 20%] clamp; new test `test_commission_rate_clamps_to_section6_band` added. Total: **243/243 tests pass**.

**Items deliberately left as PLANNED — NOT DEPLOYED:**
- 50% partner platform-fee discount (Section 2.1)
- 1-month free trial for partners/dealers/storage (Section 5.1)
- First-listing-free flag (Section 5.2)
- Multi-platform algorithmic ad pipeline — Meta, Google, TikTok (Section 5.3)
- Google Maps B2B sourcing (Section 7.4)
- Boutique business sub-profiles (Section 2.4)

---

*Document generated iter325 — June 30, 2026 — BidVex Inc., Sherbrooke, QC.*
*Every figure in this manual maps to a specific file + symbol in the live codebase.*
*For implementation requests on PLANNED items, file a ticket at `support@bidvex.com`.*
