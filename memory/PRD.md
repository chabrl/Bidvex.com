# BidVex Auction Marketplace — PRD

## Original Problem Statement
Full-stack bilingual (EN/FR) auction marketplace for high-value vehicles and general items in Quebec, Canada. Built with React frontend, FastAPI backend, and MongoDB.

## Core Requirements
- Bilingual (EN/FR) UI with i18n toggle
- High-value vehicle auctions with $1,000 pre-authorization deposit
- Stripe payments with Connect for seller payouts
- Quebec tax compliance (GST/QST)
- Admin dashboard with monitoring
- Mobile-first responsive design
- Railway deployment ready

---

## What's Been Implemented

### Phase 1-5 — Core Platform + Production Hardening (Complete)
- Full auction CRUD with real-time bidding via WebSockets
- User auth (JWT + Google OAuth), Stripe checkout, subscription tiers
- Admin panel with 15+ management tabs
- Library migration: Removed `emergentintegrations` → `openai`, `boto3`, `stripe`
- Railway deployment: `main.py` entry, lazy DB, ProxyHeadersMiddleware
- Frontend SPA served by FastAPI backend

### Phase 6 — Bilingual Content & Gemini Translation (Complete)
- Automated Gemini 2.5 Flash translation for listings
- `getLocalized()` helper, extended en.json/fr.json

### Phase 7 — High-Velocity Sorting (Complete)
- Active items sorted by ending soonest
- Compound MongoDB indexes
- "Ending Soon" badges with pulsing timers

### Phase 8 — Race Conditions & Logic Fixes (Complete - April 8, 2026)
- **Hard Stop Bidding**: Server-side timestamp validation rejects bids on ended auctions (403)
- **WebSocket Timer Sync**: Fixed key mismatch in ws_managers.py — BID_UPDATE now sends time_extended, new_auction_end, new_auction_end_epoch, server_time_epoch
- **Auto-Bid Bot**: Counter-bid processor triggers after every manual bid. Premium/VIP/Partner only. Exhaustion logic at max_bid.
- **Vehicle Category Isolation**: Vehicles excluded from general marketplace ($nin filter). Vehicle Auctions page merges vehicle_listings + listings[category=vehicles].
- **Quick Bid Fix**: FlattenedMarketplace.js detects single vs multi-item, calls correct endpoint
- **Listing Model Fix**: Made city/region optional to prevent Pydantic validation errors
- **Trust Status Fix**: Set trust_status="verified" on test users for bid eligibility
- **Bulk Listings**: 20 bilingual EN/FR listings created (10 vehicles + 10 general)

---

## Architecture

```
/app
├── backend/
│   ├── main.py                     # Railway entrypoint
│   ├── server.py                   # FastAPI setup, middleware, SPA mount
│   ├── routes/
│   │   ├── auctions.py             # Auction CRUD
│   │   ├── auctions_bids.py        # Bid logic + Auto-bid processor
│   │   ├── vehicles.py             # Vehicle auction flows + merged listing fetch
│   │   ├── vehicles_admin.py       # Vehicle admin (extracted)
│   │   ├── marketplace.py          # General marketplace (excludes vehicles)
│   │   ├── payments.py             # Core checkout
│   │   └── monitoring.py           # System monitoring
│   ├── services/
│   │   └── translation_service.py  # Gemini 2.5 Flash EN<->FR
│   └── ws_managers.py              # WebSocket broadcast with extension sync
├── frontend/
│   ├── build/                      # Compiled React SPA
│   └── src/
│       ├── components/FlattenedMarketplace.js  # Quick Bid with single/multi detect
│       ├── hooks/useRealtimeBidding.js         # Timer sync on BID_UPDATE
│       └── utils/localization.js               # getLocalized() helper
└── runtime.txt
```

---

## Prioritized Backlog

### P0 (Launch Blockers) — None remaining

### P1 (Post-Launch)
- Cloudflare CDN DNS routing
- Production monitoring alert notifications

### P2 (Enhancements)
- Real-time performance dashboard
- Automated weekly Lighthouse audits
- Seller Dashboard translation editor UI

### P3 (Technical Debt)
- server.py decomposition into lifecycle, middleware, routing modules

---

## Test Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`
- Starter: `starter@test.com` / `TestUser2026!` (free)
- Premium: `premium@test.com` / `TestUser2026!` (premium)
- Partner: `partner@test.com` / `TestUser2026!` (partner)
