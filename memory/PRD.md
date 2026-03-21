# BidVex Auction Marketplace - Product Requirements Document

## Overview
BidVex is a full-stack auction marketplace with React frontend, FastAPI backend, and MongoDB. Features include subscription tiers with Stripe billing, Partner Pro trials, real-time bidding via WebSockets, and cloud PDF invoice storage.

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next, @tanstack/react-query
- **Backend**: FastAPI, MongoDB, Stripe, SendGrid, APScheduler
- **Infrastructure**: Kubernetes, Emergent Object Storage

## Test Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Completed Work

### Core Platform (Sessions 1-N)
- Full subscription system with Stripe billing (Free/Premium/Partner Pro/VIP)
- Real-time bidding with WebSockets
- Multi-item lot auctions, vehicle auctions
- User verification and trust system, messaging, PDF invoices, notifications

### i18n Overhaul (March 2026)
- JSON-based EN/FR, CI audit gate, 202 strings fixed, 481 unused keys removed

### E-Commerce Checkout (March 20, 2026)
- Buy Now: server-side pricing with buyer premium + taxes, Stripe checkout, webhook → paid
- Auction Winner: email, checkout page, idempotency key, 14-day deadline, late penalty
- Webhook handlers for buy_now and auction_winner payment types
- Price security: all amounts from MongoDB, never trust frontend

### Mobile UI Fixes (March 21, 2026)
- Marketplace/Lots: sticky horizontal filter bar, no floating sidebar on mobile, no duplicates
- Messages: full-screen conversation list on mobile, split panel on tablet/desktop
- Lot Detail: bid input stacks vertically on mobile, min 48px height
- Seller Dashboard: deletion request auth header fix, loading spinner

### Full Regression (March 21, 2026) — 51/51 PASS
- Webhook security (signature validation)
- Buy Now + Auction Winner full payment flows
- Subscription billing lifecycle
- Tax calculations (GST/QST)
- Temp i18n migration scripts cleaned up
- LAUNCH_CHECKLIST.md updated with all verified systems

## Backlog
- (P2) Cloudflare CDN setup per /app/memory/INFRASTRUCTURE_P2.md
- (P2) Post-launch monitoring and alerting
