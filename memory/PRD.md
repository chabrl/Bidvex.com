# BidVex Auction Marketplace - Product Requirements Document

## Overview
BidVex is a full-stack auction marketplace with React frontend, FastAPI backend, and MongoDB.

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next, @tanstack/react-query
- **Backend**: FastAPI, MongoDB, Stripe, SendGrid, APScheduler
- **Infrastructure**: Kubernetes, Emergent Object Storage

## Test Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Completed Work

### Core Platform
- Subscriptions (Free/Premium/Partner Pro/VIP), real-time bidding, multi-item lots, vehicles, verification, messaging, PDF invoices, notifications

### i18n Overhaul (March 2026)
- JSON-based EN/FR, CI audit gate, 202 strings fixed, 481 unused keys removed

### E-Commerce Checkout (March 20, 2026)
- Buy Now + Auction Winner flows with server-side pricing, Stripe sessions, webhooks

### Mobile UI Fixes (March 21, 2026)
- Marketplace filters, Messages layout, Bid input, Seller Dashboard deletion

### Full Regression (March 21, 2026)
- Webhooks, subscriptions, tax calculations — 51/51 pass

### Post-Purchase Review System (March 21, 2026)
- **Reviews**: POST /api/reviews/create (1-5 stars + category ratings + comment 20-500 chars). One per transaction, 48h edit window. Server-side ownership validation. Rate limit 10/hr. XSS sanitized.
- **Reputation**: Weighted avg + badge system (New <3, Trusted 4.0+/10+, Top Rated 4.7+/25+). Score hidden <3 reviews. 5-star breakdown bars. Category averages.
- **Moderation**: Admin flag/unflag/remove. Flagged excluded from score. GET /api/reviews/moderation/pending.
- **Emails**: Review request 24h after payment (hourly scheduler). Seller notification on new review.
- **Frontend**: /review/:transactionId page, SellerReputationCard + SellerReviewsList on storefront.
- **Testing**: 38/38 tests pass (Iteration 79)

### Seller Rating on Listing Cards + Detail Pages (March 21, 2026)
- **SellerRatingInline on Marketplace Cards**: Shows star rating + review count for 3+ reviews, "New Seller" label for <3 reviews. Applied to both Items (/items) and Lots (/lots) marketplace grids.
- **Batch Reputation API**: POST /api/reviews/reputation/batch used to avoid N+1 individual API calls.
- **Full Breakdown on Detail Pages**: SellerReputationCard (score + star bars + category averages) + SellerReviewsList (paginated reviews) + "View all reviews" link on /listing/:id and /lots/:id.
- **i18n**: 922 keys in sync EN/FR. `sellerReputation.*` keys added to both locales.
- **Testing**: 15/15 tests pass (Iteration 80)

### Partner Program Page Fixes (March 21, 2026)
- **FIX 1 — Translation**: Rewrote BecomePartnerPage with full i18n (55 `partnerPage.*` keys). All strings display in French when FR mode active, English when EN mode. 977 keys in sync EN/FR.
- **FIX 2 — Layout**: Feature cards 2x2 desktop / 1-col mobile with equal height. Math section side-by-side desktop / stacked mobile. Form max-640px centered desktop, full-width mobile. Submit button full-width mobile / centered desktop. Footer language indicator now shows Canadian flag with current language name (CA Français / CA English).
- **FIX 3 — Pricing**: Partner Pro annual fee updated from $240 to $100 CAD/year (DB + code defaults). Subscription pricing page shows $100 with $200 original price. Price breakdown API confirms subtotal=$100. Partner Pro added to SubscriptionPricingPage PLAN_STYLES and sort order.
- **Testing**: 29/29 tests pass (Iteration 81 — 12 backend + 17 frontend)

### Pre-Launch Platform Audit (March 21, 2026)
- **i18n Coverage**: Extended to MobileBottomNav, TrendyAnnouncementBar, ReviewPage, StorefrontPage, PartnerDashboard, BulkImportPage, ItemsMarketplacePage, LotsMarketplacePage, SubscriptionPricingPage, MyVehicleListingsPage, VehicleInvoicesPage. Total: 1159 keys in sync EN/FR, 0 missing, 0 hardcoded.
- **Backend Fix**: Fixed NameError in email_marketing_ext.py — replaced bare `db` references with `get_db()` calls.
- **Mobile Layout**: Fixed horizontal overflow on /items page at 390px by adding `overflow-x-hidden`.
- **Testing**: 22/22 tests pass (Iteration 82)

## Key API Endpoints (Reviews)
- POST /api/reviews/create — Create review (auth + paid txn required)
- PUT /api/reviews/{id} — Edit within 48h
- GET /api/reviews/seller/{sellerId} — Paginated seller reviews
- GET /api/reviews/transaction/{txnId} — Review for transaction
- GET /api/reviews/details/{txnId} — Item info for review form
- GET /api/reviews/reputation/{sellerId} — Score + badge + breakdown
- POST /api/reviews/reputation/batch — Batch reputations for listing cards
- DELETE /api/reviews/{id} — Admin remove
- POST /api/reviews/{id}/flag — Admin flag
- POST /api/reviews/{id}/unflag — Admin restore
- GET /api/reviews/moderation/pending — Admin flagged list

### Subscription Pricing Page Redesign (March 21, 2026)
- **Layout**: Rewrote SubscriptionPricingPage.js with 2x2 responsive grid (md:grid-cols-2). Card order: [Starter, Premium] top, [Partner Pro, VIP Elite] bottom. Single column on mobile.
- **Card Design**: Tier-specific top accent borders (slate/purple-indigo/teal-cyan/amber-gold), rounded-2xl corners, shadow-md with hover:shadow-lg, p-6 sm:p-8 padding.
- **VIP Elite Card**: Dark charcoal background (#1a1a2e), ALL text white (#FFFFFF) or gold (#FFD700). Fixed global CSS !important override on h3 headings by adding targeted selector in index.css.
- **CTA Buttons**: Tier-specific gradient buttons, greyed-out "Current Plan" for active tier, "CURRENT PLAN" uppercase badge.
- **Account Settings Section**: Shows current plan, billing renewal date, and payment method for logged-in users with link to /settings.
- **Personalized Savings Section**: Shows monthly savings for each paid plan when using yearly billing.
- **i18n**: 30+ new pricingPage keys added (planNames, planTaglines, off, free, yr, mo, saveAmount, processing, goVip, terms, accountSettings, etc.). 1195 keys in sync EN/FR, 0 missing.
- **Display Names**: Free→Starter, VIP→VIP Elite (via i18n planNames keys).
- **Responsive**: Verified at 390px (single col), 768px (2x2), 1280px (2x2). No horizontal overflow at any breakpoint.
- **Testing**: 100% frontend pass (Iteration 83)

## Backlog
- (P2) Cloudflare CDN setup per /app/memory/INFRASTRUCTURE_P2.md
- (P2) Post-launch monitoring and alerting
- (Post-Launch) Configure production secrets (Stripe, SendGrid, webhooks)
- (Low Priority) Add i18n to internal EmailMarketingPricing page
