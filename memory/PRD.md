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

## Backlog
- (P2) Cloudflare CDN setup per /app/memory/INFRASTRUCTURE_P2.md
- (P2) Post-launch monitoring and alerting
- (Post-Launch) Configure production secrets (Stripe, SendGrid, webhooks)
