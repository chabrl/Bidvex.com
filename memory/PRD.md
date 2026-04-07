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
- Verified via testing agent (iteration_111: 12/12 tests passed)

### Phase 5 — Infrastructure Hardening (Complete - April 7, 2026)
- **$1,000 Deposit Security**: Verified `place_bid` blocks on >$10k listings without deposit in both `auctions.py` and `vehicles.py`. SecurityDepositBanner renders on ListingDetailPage and VehicleDetailPage.
- **System Monitoring Dashboard**: New `routes/monitoring.py` with admin-only endpoints for errors, webhooks, health checks. Frontend dashboard at Admin > Analytics > System Monitoring with real-time metrics (auto-refresh 30s).
- **Error Tracking Middleware**: 500 errors and unhandled exceptions automatically logged to `monitoring_events` MongoDB collection.
- **Webhook Failure Tracking**: Stripe and SendGrid webhook outcomes logged to `webhook_log` collection with success/failure status.
- **Cloudflare CDN Headers**: Enhanced cache headers with `CDN-Cache-Control` for static assets, images (including .avif), and API no-store rules.
- **payments.py Refactored**: Split from 2,293 to 1,594 lines. Extracted `payments_fees.py` (293 lines), `payments_promotions.py` (190 lines), `payments_shared.py` (37 lines).
- **Backend Lint Fixes**: Resolved all warnings in `webhooks.py` (missing timedelta), `partners.py` (undefined db/os, missing helpers), `subscriptions.py` (unused variables, duplicate function name).
- Verified via testing agent (iteration_112: 19/19 backend tests passed, frontend System Monitoring confirmed rendering).

---

## Architecture

```
/app
├── backend/
│   ├── main.py                     # Railway entrypoint
│   ├── server.py                   # FastAPI setup, middleware, SPA mount
│   ├── routes/
│   │   ├── payments.py             # Core checkout, methods, subscriptions (1594 lines)
│   │   ├── payments_fees.py        # Fee calculations & tax endpoints
│   │   ├── payments_promotions.py  # Promotions & email credits
│   │   ├── payments_shared.py      # Shared DI for payment sub-routers
│   │   ├── monitoring.py           # System monitoring & alerting
│   │   ├── auctions.py             # Auction CRUD & bidding
│   │   ├── vehicles.py             # Vehicle auction flows
│   │   ├── deposits.py             # $1k pre-auth deposit management
│   │   ├── webhooks.py             # Stripe/SendGrid webhook handlers
│   │   └── ...
│   └── services/
│       ├── pricing_config.py       # Centralized pricing constants
│       ├── fee_calculation_engine.py
│       └── tax_engine.py
├── frontend/
│   ├── build/                      # Compiled React SPA
│   └── src/
│       ├── config.js               # Centralized API base URL
│       ├── components/
│       │   ├── UserTierGrid.js
│       │   ├── PartnerLicenseCard.js
│       │   └── SecurityDepositBanner.js
│       └── pages/
│           ├── admin/
│           │   └── SystemMonitoringDashboard.js
│           ├── AdminDashboard.js
│           └── ProfileSettingsPage.js
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

### P3 (Technical Debt)
- Further payments.py decomposition (advanced checkout, buy now, seller earnings)
- `server.py` decomposition into lifecycle, middleware, routing modules
- Remove `E741` lint warnings in `dashboard.py`

---

## 3rd Party Integrations
| Service | Purpose | Key Required |
|---------|---------|-------------|
| Stripe | Payments & Connect | STRIPE_API_KEY |
| OpenAI GPT-4o | AI Assistant | OPENAI_API_KEY |
| SendGrid | Email Marketing | SENDGRID_API_KEY |
| Twilio | SMS/Verify | TWILIO_* |
| Cloudflare R2 | Object Storage | AWS S3 compatible keys |

## Test Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`
