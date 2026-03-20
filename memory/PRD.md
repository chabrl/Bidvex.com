# BidVex Auction Marketplace — PRD

## Product Overview
Full-stack auction marketplace with localized currency, tax compliance, 4-tier subscriptions (Free/Premium/Partner Pro/VIP), real-time bidding, and professional seller tools.

## Tech Stack
- **Frontend**: React 19, Tailwind CSS, Shadcn/UI, @tanstack/react-query, embla-carousel-react
- **Backend**: FastAPI (37 route modules), MongoDB, Stripe, SendGrid, Emergent Object Storage
- **Architecture**: Modular backend, shared.py for common models, server.py as ~362-line entry point

## Subscription Tiers
| Tier | Price/yr | Original | Buyer Discount | Seller Discount |
|------|----------|----------|----------------|-----------------|
| Free | $0 | — | 0% | 0% |
| Premium | $180 | $360 | 30% | 37.5% |
| Partner Pro | $240 | $480 | 25% | 25% |
| VIP | $300 | $600 | 40% | 50% |

## Completed Features

### Session 1 (Previous)
- User auth (JWT), admin panel, real-time WebSocket bidding
- Listing CRUD, marketplace with search/filters
- Smart localized currency formatting, tax compliance engine
- Admin tax dashboard, email marketing, SEO
- Full responsive design overhaul

### Session 2 (Previous) 
- React Query migration (client-side caching)
- Cursor-based pagination
- Massive backend refactor (server.py: 9200→300 lines)

### Session 3 (Mar 20, 2026)
- **Step 1**: Mobile Swipeable Carousels (Embla, 6 homepage sections)
- **Step 2**: Cloud PDF Invoice Storage (Emergent Object Storage)
- **Step 3**: Premium Comparison View (/compare page + marketplace integration)
- **Step 4**: Partner Pro Tier — all features built:
  - Branded storefront (/store/:userId)
  - CSV bulk listing import (/bulk-import)
  - Early auction access (2h head start)
  - Analytics export (CSV/JSON)
  - 10 featured listings/month
  - Priority chat + email support flag
- **Stripe Billing**: Partner Pro at $240/yr (annual-only, 50% launch discount)
- **14-Day Free Trial**: No CC, one per account, auto-revert, SendGrid day-10 reminder
- **Production Readiness Report**: /app/memory/PRODUCTION_READINESS_REPORT.md

## Key API Endpoints
- `GET /api/subscription-plans` — 4 tiers
- `POST /api/subscriptions/create` — Stripe checkout (premium, partner_pro, vip)
- `POST /api/partner-pro/trial/start` — Start 14-day trial
- `GET /api/partner-pro/trial/status` — Trial status
- `POST /api/partner-pro/bulk-import` — CSV upload
- `GET /api/partner-pro/analytics/export` — CSV/JSON export
- `GET/POST /api/partner-pro/featured-listings` — Manage featured
- `GET /api/storefronts/{user_id}` — Public storefront
- `PUT /api/partner-pro/storefront` — Update storefront

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Remaining Backlog
- **P3**: Email template test coverage expansion
- **Recommended**: Rate limiting (slowapi), MongoDB indexes, Cloudflare CDN setup
