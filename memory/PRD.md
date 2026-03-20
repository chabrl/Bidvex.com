# BidVex Auction Marketplace — Product Requirements Document

## Original Problem Statement
Full-stack auction marketplace (BidVex) with smart localized currency formatting, admin tax dashboard, responsive design, and multi-phase performance engineering.

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
- Comprehensive MongoDB indexes on listings, users, transactions, notifications
- SEO: react-helmet-async, robots.txt, sitemap.xml
- Image lazy loading via CSS
- Debounced search inputs

### Performance Engineering — P2 (Complete — Feb 2026)
- **React Query Migration**: Installed `@tanstack/react-query`, wrapped app in `QueryProvider`, created custom hooks (`useCategories`, `useMarketplaceItems`, `useHomePageData`), migrated `HomePage.js`, `FlattenedMarketplace.js`, `DecomposedMarketplace.js` from manual fetching to React Query hooks
- **Cursor Pagination**: Backend `/api/marketplace/items` now accepts `cursor` param and returns `next_cursor` + `has_more`. Frontend uses `useInfiniteQuery` for seamless "Load More"
- **server.py Refactor**: Extracted ~487 lines into `routes/carousel.py` (152 lines) and `routes/site_config.py` (287 lines). Server reduced from 9,265 to 8,778 lines
- **Cloudflare CDN**: Instructions documented in `INFRASTRUCTURE_P2.md` — requires manual DNS setup by owner

## Prioritized Backlog

### P1 — Upcoming
- Swipeable card carousels on mobile

### P2 — Future
- Premium Comparison view in marketplace
- Replace local PDF invoice mock with cloud storage (S3)
- Partner Pro subscription tier

### P3 — Later
- Expand email template test coverage

## Key DB Collections
- `listings`: Indexed on (status, end_date), (category), (seller_id), (created_at, -1)
- `users`: Indexed on (email, unique), (role)
- `transactions`: Indexed on (status), (created_at, -1), (buyer_id), (seller_id)
- `notifications`: Indexed on (user_id, is_read, created_at, -1)

## API Architecture
- Extracted route modules: analytics, auctions, auth, admin, carousel, dashboard, fees, listings, marketplace, marketing, notifications, partners, payments, profiles, site_config, sms_verification, tax_dashboard, team, users, watchlist, webhooks
- Remaining in server.py: site-mode, subscriptions, invoices, WebSocket handlers, email marketing

## Infrastructure Notes
- Cloudflare CDN setup required (manual DNS change) — see `INFRASTRUCTURE_P2.md`
- PDF invoices stored locally at `/data/invoices/` (MOCKED — not cloud storage)

## Test Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`
