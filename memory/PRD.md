# BidVex Auction Marketplace - Product Requirements Document

## Overview
BidVex is a full-stack auction marketplace with React frontend, FastAPI backend, and MongoDB. Features include subscription tiers with Stripe billing, Partner Pro trials, real-time bidding via WebSockets, and cloud PDF invoice storage.

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next, @tanstack/react-query
- **Backend**: FastAPI, MongoDB, Stripe, SendGrid, APScheduler
- **Infrastructure**: Kubernetes, Emergent Object Storage

## Core Features
1. **Multi-tier subscriptions** (Free, Basic, Pro, Partner Pro) with Stripe billing
2. **Real-time bidding** via WebSockets
3. **Multi-item lot auctions** with Buy Now functionality
4. **Vehicle auctions** (hybrid payment: BidVex fees online, hammer price via bank draft)
5. **Internationalization** (EN/FR) with CI audit pipeline
6. **Seller verification** and tax registration
7. **Partner auction system** for professional auctioneers

## Test Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## What's Been Implemented (Completed)

### Session 1-N: Core Platform
- Full subscription system with Stripe billing
- Real-time bidding with WebSockets
- Multi-item lot auctions
- Vehicle auction support
- User verification and trust system
- Messaging and handshake system
- PDF invoice generation with cloud storage
- Notification system

### i18n Overhaul (Completed March 2026)
- Migrated to clean JSON-based system (en.json/fr.json)
- Rewrote i18n.js from ~2000 to ~60 lines
- Fixed 202 hardcoded strings across 55 files
- Removed 481 unused translation keys
- Added CI audit script (yarn i18n:audit) in predeploy

### E-Commerce Checkout Fixes (Completed March 20, 2026)
- **BUG 1 FIXED: Buy Now Stripe Price** — New endpoints POST /api/payments/buy-now-preview and POST /api/payments/buy-now-checkout. Server-side price calculation with buyer premium, taxes (GST/QST), processing fee. Frontend shows breakdown modal before Stripe redirect.
- **BUG 2 FIXED: Auction Winner Flow** — New endpoints GET /api/payments/auction-winner-preview/{id} and POST /api/payments/auction-winner-checkout/{id}. Winner gets "You Won!" email via SendGrid. Checkout page shows breakdown with late penalty. Stripe session uses idempotency key (auction_{listingId}_{winnerId}). Payment deadline: 14 days. Day 10 reminder email. Day 14 overdue + 2%/month penalty.
- All prices calculated server-side from MongoDB (never trust frontend)
- 100% test pass rate: 17/17 backend tests, all frontend flows verified

## Key API Endpoints (New)
- `POST /api/payments/buy-now-preview` — Price breakdown for Buy Now (no side effects)
- `POST /api/payments/buy-now-checkout` — Buy Now purchase + Stripe session
- `GET /api/payments/auction-winner-preview/{listing_id}` — Winner checkout preview with late penalty
- `POST /api/payments/auction-winner-checkout/{listing_id}` — Winner Stripe session with idempotency

## Scheduler Jobs (New)
- `send_auction_payment_reminders` — Runs every 6h, sends reminders at day 10
- `process_overdue_auction_payments` — Runs every 6h, marks overdue at day 14, applies 2%/month penalty

## Backlog / Future Tasks
- (P2) Set up Cloudflare CDN per /app/memory/INFRASTRUCTURE_P2.md
- (P2) Post-launch monitoring and alerting
- (P3) Cleanup: Delete temp i18n migration scripts from /app/frontend/scripts/
