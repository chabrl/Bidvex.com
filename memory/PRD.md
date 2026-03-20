# BidVex Auction Marketplace — Product Requirements Document

## Original Problem Statement
Full-stack auction marketplace (BidVex) with smart localized currency formatting, admin tax dashboard, responsive design, and multi-phase performance engineering including full server.py refactoring.

## Core Architecture
- **Frontend**: React 18 + Tailwind CSS + Shadcn/UI + React Query
- **Backend**: FastAPI + MongoDB (Motor async driver)
- **Payments**: Stripe
- **Email**: SendGrid
- **SEO**: react-helmet-async
- **State Management**: @tanstack/react-query (client-side caching)

## What's Been Implemented

### Features
- Smart Localized Currency Formatting (EN/FR-QC via `Intl.NumberFormat`)
- Admin Tax Dashboard (aggregation pipeline + CSV export)
- Full Responsive Design Overhaul (mobile-first, hamburger nav, responsive grids)

### Performance Engineering — P0 (Complete)
- Code splitting: All 40+ pages via `React.lazy()` with Suspense fallback
- Backend Gzip compression middleware
- Critical CSS skeleton loader in `index.html`

### Performance Engineering — P1 (Complete)
- In-memory TTL cache (`services/api_cache.py`) on public endpoints
- Comprehensive MongoDB indexes on all major collections
- SEO: react-helmet-async, robots.txt, sitemap.xml
- Image lazy loading via CSS
- Debounced search inputs

### Performance Engineering — P2 (Complete — Feb 2026)
- **React Query Migration**: `@tanstack/react-query` with custom hooks (`useCategories`, `useMarketplaceItems`, `useHomePageData`)
- **Cursor Pagination**: `/api/marketplace/items` accepts `cursor` param, returns `next_cursor` + `has_more`
- **server.py Refactor**: 9,265 lines → **287 lines** (clean entry point only)
  - 12 new route modules: subscriptions, invoices, partners, admin_config, admin_ops, trust_safety, email_marketing_ext, legal, site_mode, misc, carousel, site_config
  - Shared code in `shared.py` (models, constants, helpers), `ws_managers.py`, `ws_handlers.py`
- **Cloudflare CDN**: Instructions in `INFRASTRUCTURE_P2.md` — requires manual DNS setup

## Backend Architecture (Post-Refactor)
```
/app/backend/
├── server.py              (287 lines - entry point only)
├── shared.py              (492 lines - models, constants, helpers)
├── deps.py                (121 lines - DB/auth dependency injection)
├── ws_managers.py          (216 lines - WebSocket connection managers)
├── ws_handlers.py          (220 lines - WebSocket endpoint registration)
├── routes/                 (22,683 lines across 36 modules)
│   ├── admin.py, admin_config.py, admin_ops.py
│   ├── analytics.py, auth.py, auctions.py
│   ├── carousel.py, dashboard.py, email_marketing_ext.py
│   ├── fees.py, invoices.py, legal.py, listings.py
│   ├── marketplace.py, marketing.py, messages.py, misc.py
│   ├── notifications.py, partners.py, payments.py, profiles.py
│   ├── site_config.py, site_mode.py, sms_verification.py
│   ├── subscriptions.py, tax.py, tax_dashboard.py, tax_reports.py
│   ├── team.py, trust_safety.py, users.py, vehicles.py
│   ├── watchlist.py, webhooks.py, ai_chat.py
│   └── __init__.py
└── services/              (email, tax, caching, marketing, etc.)
```

## Prioritized Backlog

### P1 — Upcoming
- Swipeable card carousels on mobile

### P2 — Future
- Premium Comparison view in marketplace
- Replace local PDF invoice mock with cloud storage (S3)
- Partner Pro subscription tier

### P3 — Later
- Expand email template test coverage

## Test Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`
