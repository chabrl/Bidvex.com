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

## User Personas
- **Buyers**: Browse auctions, place bids, manage deposits
- **Sellers**: List items, manage auctions, track earnings
- **Partners**: Professional dealers with Pro license
- **Admins**: Platform oversight, monitoring, configuration

---

## What's Been Implemented

### Phase 1 — Core Platform (Complete)
- Full auction CRUD with real-time bidding via WebSockets
- User auth (JWT + Google OAuth)
- Stripe checkout, Connect splits, subscription tiers
- Admin panel with 15+ management tabs
- Vehicle auction category with specialized flows

### Phase 2 — Production Hardening (Complete)
- Library migration: Removed `emergentintegrations`, replaced with `openai`, `boto3`, `stripe`
- Railway deployment support: `main.py` entry, lazy DB connections, ProxyHeadersMiddleware
- Frontend built as SPA served by FastAPI backend
- PageSpeed & Accessibility fixes (CLS, aria-labels, unused scripts)
- Fixed Admin Panel array normalization across 10+ components

### Phase 3 — Mobile & UI Polish (Complete)
- Mobile Messaging interface rebuilt with `position: fixed; inset: 0` for iOS keyboard
- Legal pages/footer mailing address removal
- Subscription page VIP text color fix (CSS `!important` override)
- Subscription page EN/FR toggle fix (z-index, JSON translations)

### Phase 4 — Subscription Decoupling (Complete)
- `UserTierGrid.js`: 3-column desktop grid for Standard tiers (Starter/Premium/VIP)
- `PartnerLicenseCard.js`: Isolated Partner Pro card for Partner Dashboard
- Deleted deprecated `TrendySubscriptionCards.js`

### Phase 5 — Infrastructure Hardening (Complete - April 7, 2026)
- **$1,000 Deposit Security**: Verified `place_bid` blocks on >$10k listings without deposit
- **System Monitoring Dashboard**: Admin endpoints for errors, webhooks, health checks
- **Error Tracking Middleware**: 500 errors logged to `monitoring_events` collection
- **Webhook Failure Tracking**: Stripe/SendGrid webhook outcomes logged
- **Cloudflare CDN Headers**: Enhanced cache headers for static assets
- **payments.py Refactored**: Split into `payments_fees.py`, `payments_promotions.py`, `payments_shared.py`

### Phase 6 — Bilingual Content & Gemini Translation Engine (Complete - April 7, 2026)
- Automated Gemini 2.5 Flash translation engine for all new listings
- `services/translation_service.py` with dual-SDK: Emergent LLM Key (preview) / `google-generativeai` (Railway)
- `utils/localization.js` with `getLocalized()` helper across all frontend pages
- Extended `en.json` and `fr.json` with 25+ marketplace i18n keys
- Backfill endpoint for existing listings

### Phase 7 — High-Velocity Marketplace Sorting (Complete - April 7, 2026)
- Active items sorted by `auction_end_date` ascending (ending soonest first)
- Compound indexes `[status:1, auction_end_date:1, created_at:-1]`
- "Ending Soon" badge with red pulsing animation when <1 hour remaining

### Production Push — Build Fix, Sorting, Subscription & Refactor (Complete - April 7, 2026)
- Railway build fix: Cleaned `requirements.txt` from Emergent-internal packages
- Subscription UI: 3-column layout (Starter/Premium/VIP) without Partenaire Pro
- Route modularization: `auctions_bids.py` and `vehicles_admin.py` extracted

### Multi-User Sniping Test Setup (Complete - April 8, 2026)
- Created 3 super-verified test users: starter@test.com (free), premium@test.com (premium), partner@test.com (partner)
- All users have full verification flags, mock payment methods, zero permission barriers
- Created 3 test listings: Tesla Model 3 (5 min), Herman Miller Chair (10 min), Breville Espresso (24h)
- Login verified ✅ | Bid placement verified ✅ | Cross-user bidding verified ✅

---

## Architecture

```
/app
├── backend/
│   ├── main.py                     # Railway entrypoint
│   ├── server.py                   # FastAPI setup, middleware, SPA mount
│   ├── routes/
│   │   ├── auctions.py             # Auction CRUD
│   │   ├── auctions_bids.py        # Bid logic (extracted)
│   │   ├── vehicles.py             # Vehicle auction flows
│   │   ├── vehicles_admin.py       # Vehicle admin (extracted)
│   │   ├── payments.py             # Core checkout (1594 lines)
│   │   ├── payments_fees.py        # Fee calculations
│   │   ├── payments_promotions.py  # Promotions
│   │   ├── monitoring.py           # System monitoring
│   │   └── ...
│   └── services/
│       ├── translation_service.py  # Gemini 2.5 Flash EN<->FR
│       ├── pricing_config.py       # Centralized pricing
│       └── brute_force.py          # IP-based login protection
├── frontend/
│   ├── build/                      # Compiled React SPA
│   └── src/
│       ├── config.js               # Centralized API base URL
│       ├── utils/localization.js   # getLocalized() helper
│       ├── locales/                # en.json, fr.json
│       └── pages/
└── runtime.txt
```

---

## Prioritized Backlog

### P0 (Launch Blockers) — None remaining

### P1 (Post-Launch)
- Cloudflare CDN DNS routing (manual setup per INFRASTRUCTURE_P2.md)
- Production monitoring alert notifications (email/Slack on critical errors)

### P2 (Enhancements)
- Real-time performance dashboard
- Automated weekly Lighthouse audits
- Server-side PageSpeed monitoring endpoint
- i18n for EmailMarketingPricing page
- Seller Dashboard translation editor UI

### P3 (Technical Debt)
- Further payments.py decomposition
- server.py decomposition into lifecycle, middleware, routing modules
- Remove E741 lint warnings in dashboard.py

---

## 3rd Party Integrations
| Service | Purpose | Key Required |
|---------|---------|-------------|
| Stripe | Payments & Connect | STRIPE_API_KEY |
| OpenAI GPT-4o | AI Assistant | OPENAI_API_KEY |
| SendGrid | Email Marketing | SENDGRID_API_KEY |
| Twilio | SMS/Verify | TWILIO_* |
| Cloudflare R2 | Object Storage | AWS S3 compatible keys |
| Gemini 2.5 Flash | Auto-Translation EN<->FR | EMERGENT_LLM_KEY / GEMINI_API_KEY |

## Test Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`
- Starter: `starter@test.com` / `TestUser2026!` (free)
- Premium: `premium@test.com` / `TestUser2026!` (premium)
- Partner: `partner@test.com` / `TestUser2026!` (partner)
