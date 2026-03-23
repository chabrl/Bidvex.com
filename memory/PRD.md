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
- Reviews, Reputation, Moderation, Emails, Frontend — 38/38 tests pass (Iteration 79)

### Seller Rating on Listing Cards + Detail Pages (March 21, 2026)
- SellerRatingInline, Batch Reputation API, Full Breakdown — 15/15 tests pass (Iteration 80)

### Partner Program Page Fixes (March 21, 2026)
- Translation, Layout, Pricing — 29/29 tests pass (Iteration 81)

### Pre-Launch Platform Audit (March 21, 2026)
- i18n Coverage, Backend Fix, Mobile Layout — 22/22 tests pass (Iteration 82)

### Subscription Pricing Page Redesign (March 21, 2026)
- 2x2 grid, tier-specific design, VIP card — 100% pass (Iteration 83)

### Performance Optimization Sprint (March 23, 2026)
- Keep-alive ping, MongoDB connection pooling, marketplace cache, subscription cache, pre-warming — 100% frontend, 82% backend (Iteration 84)

### PageSpeed Optimization Sprint (March 23, 2026)
- Logo optimization, Google Ads removal, PostHog deferral, critical CSS, cache-control headers, CLS fixes, security headers, accessibility — 100% pass (Iteration 85)

### Critical Production Fixes (March 23, 2026)
- **FIX 1 — Admin Dashboard**: Fixed broken API call from `/admin/stats/revenue` (404) to `/admin/analytics/revenue` (200). Added auth headers to all admin stat requests. Updated data extraction to match response format (`total_gmv`, `active_listings`).
- **FIX 2 — Listing Detail Resilience**: Added 30s TTL in-memory cache for `GET /api/listings/{listing_id}`. Switched read to `get_read_db()` (SECONDARY_PREFERRED). First call ~3.7s, cached call ~0.09s. Added frontend retry mechanism (1 retry after 2s) in both `ListingDetailPage.js` and `MultiItemListingDetailPage.js`.
- **FIX 3 — Server Startup Logging**: Changed outer `except ImportError` to `except Exception` with full traceback. Self-contained router loading now logs `logger.error()` with `traceback.format_exc()` instead of silent `logger.warning()`.
- **FIX 5 — WWW Redirect**: Added FastAPI middleware that 301 redirects any request with `www.` host prefix to non-www equivalent.
- **FIX 6 — CLS Footer**: Increased footer `min-height` from 180px to 220px to match rendered height and reduce CLS. Google Fonts already had `&display=swap`.
- **FIX 7 — Accessibility**: Added `aria-label="Toggle theme"` to Navbar theme button. Added `aria-label="Close"` to close buttons in VerificationRequiredModal, AIAssistant, CookieConsentBanner, NotificationCenter. Standardized all `/terms` links to `/terms-of-service` (SellerDashboard, LegalDisclaimers, CookieConsentBanner). Added `/terms` → `/terms-of-service` redirect in App.js.
- **Testing**: 22/22 backend + 100% frontend — all 7 fixes verified (Iteration 86)

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

## Known Issues
- Intermittent MongoDB `NetworkTimeout` on `/api/site-config` and `/api/admin/site-config` endpoints. Pre-existing infrastructure issue related to MongoDB Atlas connectivity. Not a code regression.

## Backlog
- (P2) Cloudflare CDN setup per /app/memory/INFRASTRUCTURE_P2.md
- (P2) Post-launch monitoring and alerting
- (Post-Launch) Configure production secrets (Stripe, SendGrid, webhooks)
- (Low Priority) Add i18n to internal EmailMarketingPricing page
- (Enhancement) Real-time performance dashboard
- (Enhancement) Automated weekly Lighthouse audits
