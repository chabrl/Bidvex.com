# BidVex Auction Marketplace - Product Requirements Document

## Overview
BidVex is a full-stack auction marketplace with React frontend, FastAPI backend, and MongoDB. Features include subscription tiers with Stripe billing, Partner Pro trials, real-time bidding via WebSockets, and cloud PDF invoice storage.

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next, @tanstack/react-query
- **Backend**: FastAPI, MongoDB, Stripe, SendGrid, APScheduler
- **Infrastructure**: Kubernetes, Emergent Object Storage

## Core Features
1. Multi-tier subscriptions (Free, Basic, Pro, Partner Pro) with Stripe billing
2. Real-time bidding via WebSockets
3. Multi-item lot auctions with Buy Now functionality
4. Vehicle auctions (hybrid payment)
5. Internationalization (EN/FR) with CI audit pipeline
6. Seller verification and tax registration
7. Partner auction system for professional auctioneers

## Test Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Completed Work

### i18n Overhaul (March 2026)
- Migrated to JSON-based system, fixed 202 strings across 55 files, removed 481 unused keys, CI audit

### E-Commerce Checkout (March 20, 2026)
- BUG 1 FIXED: Buy Now Stripe price (server-side calculation + buyer premium + taxes)
- BUG 2 FIXED: Auction winner flow (email, checkout, idempotency, 14-day deadline, day 10 reminder, day 14 overdue + 2%/month)

### Mobile UI Fixes (March 21, 2026)
- **FIX 1 — Marketplace/Lots Filter Layout**: Removed floating sidebar on mobile. Single inline Filters button + sticky horizontal filter bar. Items full-width on mobile (1 col). No duplicate buttons on Lots page. Applied to: MarketplacePage.js, LotsMarketplacePage.js, FlattenedMarketplace.js, DecomposedMarketplace.js.
- **FIX 2 — Messages Page Mobile**: Full-screen conversation list on mobile. Tap conversation → full-screen chat. No split panel on mobile. Tablet shows 40/60 split. Applied to: MessagesPage.js.
- **FIX 3 — Lot Detail Bid Layout**: Bid input + Place Bid button stack vertically on mobile (full width, min 48px height). No horizontal overflow at 390px. Applied to: MultiItemListingDetailPage.js.
- **FIX 4 — Seller Dashboard Deletion**: Added missing Authorization header. Added loading spinner on Submit. Added error display. Applied to: SellerDashboard.js.
- All 4 fixes: 100% test pass rate at 390px/768px/1280px viewports.

## Backlog / Future Tasks
- (P2) Cloudflare CDN setup per /app/memory/INFRASTRUCTURE_P2.md
- (P2) Post-launch monitoring and alerting
- (P3) Cleanup: Delete temp i18n migration scripts from /app/frontend/scripts/
- (P3) Full regression test of existing general checkout flows
