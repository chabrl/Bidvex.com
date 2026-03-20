# BidVex Auction Marketplace — PRD

## Product Overview
Full-stack auction marketplace with localized currency, tax compliance, subscriptions, real-time bidding, and seller tools.

## Tech Stack
- **Frontend**: React 19, Tailwind CSS, Shadcn/UI, @tanstack/react-query, embla-carousel-react
- **Backend**: FastAPI (modular routes), MongoDB, Stripe, SendGrid
- **Architecture**: Modular backend (~15 route modules), shared.py for common models, server.py as clean entry point (~300 lines)

## Core Features (Completed)
- User auth (JWT), admin panel, real-time WebSocket bidding
- Smart localized currency formatting, tax compliance engine
- Admin tax dashboard, email marketing system
- Responsive design overhaul, SEO with react-helmet-async
- React Query migration (client-side caching, cursor pagination)
- Massive backend refactor (server.py: 9200→300 lines, 12+ route modules)

## Recently Completed (Session — Mar 20, 2026)

### Step 1: Mobile Swipeable Carousels (P1)
- Created `SwipeableCardRow` component using Embla Carousel
- Mobile (<sm): horizontal swipe carousel with dot indicators
- Desktop (sm+): standard CSS grid, unchanged
- Applied to 6 homepage sections: Live Auctions, Hot Items, Featured, New Listings, Top Sellers, Features

### Step 2: Cloud PDF Invoice Storage (P2)
- Migrated `/app/backend/services/cloud_storage.py` from local `/data/invoices/` to Emergent Object Storage
- Init on startup, HMAC-signed download URLs for secure access
- Updated commission invoice endpoints to use cloud storage

### Step 3: Premium Comparison View (P2)
- New `/compare` page: side-by-side table (desktop), stacked cards (mobile)
- Search overlay to add 2-4 listings for comparison
- Marketplace integration: compare toggle on item cards + floating compare bar

### Step 4: Partner Pro Subscription Tier (P2)
- **Pricing**: $240/yr (50% launch discount from $480/yr)
- **Annual-only** renewal (matching existing tier structure)
- **Tier ladder**: Free ($0) → Premium ($180) → Partner Pro ($240) → VIP ($300)
- **Features built**:
  - Branded storefront page (`/store/:userId`)
  - CSV bulk listing import (`/bulk-import`)
  - Early auction access (2h head start endpoint)
  - Analytics export (CSV/JSON)
  - 10 featured listings/month with tracking
  - Priority chat + email support flag
  - 25% buyer/seller discount
- **Billing**: NOT yet implemented. Awaiting user confirmation that annual-only at $240/yr is final before Stripe integration.

## Subscription Tiers
| Tier | Price/yr | Original | Buyer Discount | Seller Discount |
|------|----------|----------|----------------|-----------------|
| Free | $0 | — | 0% | 0% |
| Premium | $180 | $360 | 30% | 37.5% |
| Partner Pro | $240 | $480 | 25% | 25% |
| VIP | $300 | $600 | 40% | 50% |

## Key API Endpoints
- `GET /api/subscription-plans` — public, returns 4 tiers
- `GET /api/partner-pro/bulk-import/template` — CSV template download
- `POST /api/partner-pro/bulk-import` — upload CSV (Partner Pro+ only)
- `GET /api/partner-pro/analytics/export` — CSV/JSON export (Partner Pro+)
- `GET/POST /api/partner-pro/featured-listings` — manage featured listings
- `GET /api/partner-pro/early-access` — early-window listings
- `GET /api/storefronts/{user_id}` — public storefront
- `PUT /api/partner-pro/storefront` — update storefront (Partner Pro+)
- `GET /api/marketplace/items` — cursor-based pagination
- `GET /api/listings/{id}` — listing detail

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Pending / Backlog
- **P1**: Stripe billing for Partner Pro ($240/yr annual-only) — blocked on user confirmation
- **P3**: Expand email template test coverage
