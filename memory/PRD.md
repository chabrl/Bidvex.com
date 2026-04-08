# BidVex — Auction Marketplace PRD

## Original Problem Statement
Full-stack auction marketplace (React frontend, FastAPI backend, MongoDB) with three major development phases:
1. **Retention Phase**: Outbid Alerts, Zero-Latency Timer Extensions, Winner's Circle persistence, AI User Interest tracking, stealth WebSocket reconnect.
2. **Dealer Experience**: OPC-Certified Seller BP Control, Category & Role restrictions, Payment Orchestration (Stripe/Cash/E-Transfer), Timer "Loading..." fix, AI bulk data.
3. **Correcting Vehicle Routing & Analytics**: Vehicle Identity routing, Real-Time Marketplace Sync, Dynamic Buyer's Premium, Seller Rating Dashboard, Payment Transparency, Sidebar Filter auto-fetch, Terms fix.

Additional requirements: PageSpeed optimization, Railway deployment support, removal of `emergentintegrations` library.

## User Personas
- **Buyers**: Browse, bid, and win auctions. Need real-time price updates and transparent pricing.
- **Sellers (Standard)**: List general items. Cannot list vehicles.
- **Sellers (Partner/Admin)**: Can list vehicles, set OPC certification, customize Buyer's Premium.
- **Admin**: Manages platform, monitors fraud, processes invoices.

## Core Requirements
- Live WebSocket bidding with anti-sniping extensions
- Smart routing: vehicles → VehicleDetailView, general → ListingDetailPage
- OPC-certified seller logic with customizable Buyer's Premium (0%–25%)
- Offline payment options (Cash/E-Transfer) with automated admin invoicing
- AI behavioral tracking via `user_interests` collection
- Sidebar filters with sub-second auto-fetch
- Real-time marketplace sync (WebSocket updates propagate to grid cards)

## Architecture
```
/app
├── backend/
│   ├── server.py                # FastAPI setup, CORS, SPA static mount
│   ├── ws_managers.py           # ConnectionManager, MessageConnectionManager, MarketplaceConnectionManager
│   ├── ws_handlers.py           # WebSocket endpoints (listings, messages, marketplace)
│   ├── routes/
│   │   ├── auctions.py          # Auction lifecycle, offline invoice
│   │   ├── auctions_bids.py     # Manual/auto bids, anti-sniping, marketplace broadcasts
│   │   ├── vehicles.py          # Vehicle listings & terms acceptance
│   │   ├── marketplace.py       # General listings & filter logic
│   │   ├── users.py             # User profiles & ratings
│   │   └── user_insights.py     # AI tracking endpoints
│   ├── models/auction_models.py # Pydantic models
│   └── db/indexes.py            # MongoDB index creation
├── frontend/
│   ├── src/
│   │   ├── hooks/useMarketplaceSync.js   # Global marketplace WebSocket hook
│   │   ├── hooks/useHomePageData.js      # React Query hooks for homepage sections
│   │   ├── hooks/useMarketplaceItems.js  # React Query infinite scroll
│   │   ├── components/FlattenedMarketplace.js  # Main grid & filters
│   │   ├── components/vehicles/PricingCalculator.js  # Dynamic BP
│   │   ├── components/vehicles/PricingBreakdown.js   # Payment disclaimers
│   │   ├── pages/HomePage.js             # Smart routing + WS sync
│   │   ├── pages/ListingDetailPage.js    # Identity guard redirect
│   │   ├── pages/SellerDashboard.js      # Ratings panel
│   │   └── pages/CreateMultiItemListing.js # Vehicle category guard
```

## What's Been Implemented

### Phase 1 — Retention (COMPLETE, Tested 100%)
- Outbid Alert System (SendGrid email + Toast)
- AI User Tracking (`user_interests` collection)
- WebSocket stealth reconnection
- Zero-Latency Timer Extensions
- Winner's Circle persistence

### Phase 2 — Dealer Experience (COMPLETE, Tested 100%)
- OPC-Certified Seller BP Control (0%–25%)
- Category restrictions (non-partners blocked from vehicles)
- Payment Orchestration (Stripe, Cash, E-Transfer)
- Timer "Loading..." fix on VehicleDetailPage

### Phase 3 — Vehicle Routing & Analytics (COMPLETE, Tested April 8 2026)
- Vehicle Identity Routing: `/listing/:id` → `/vehicle-auctions/:id` redirect
- Real-Time Marketplace Sync: Global WebSocket (`/api/ws/marketplace`) broadcasts bid/timer updates to all grid cards
- Dynamic Buyer's Premium: PricingCalculator pulls seller-defined `buyers_premium_percent`
- OPC 0% Badge: "Vendeur Certifié OPC : 0 $ de frais d'achat"
- Seller Rating Dashboard: Stars, reviews, completed auctions
- Payment Transparency: "Direct Settlement" disclaimer for offline payments
- Admin Invoice: Auto-created for Cash/E-Transfer auction wins
- Sidebar Filters: onChange auto-fetch with 300ms debounce + MongoDB indexes
- Vehicle Category Guard: Non-partners blocked in both single + multi-item listings
- Accept-Terms: `POST /api/vehicles/{id}/accept-terms` working

### Infrastructure & Deployment (COMPLETE)
- Railway deployment support (runtime.txt, main.py entry point)
- Removed `emergentintegrations` library
- Centralized `config.js` for frontend API base URL
- SPA static mount from FastAPI
- ProxyHeadersMiddleware for Cloudflare
- Lazy DB startup to prevent 520 timeouts

## Key API Endpoints
- `GET /api/health` — Health check
- `POST /api/auth/login` — Authentication
- `GET /api/listings/:id` — Listing detail (with vehicle redirect guard)
- `POST /api/vehicles/:id/accept-terms` — Accept bidding terms
- `GET /api/users/:id/ratings` — Seller ratings
- `POST /api/insights/track` — AI behavioral tracking
- `WS /api/ws/marketplace` — Global marketplace real-time updates
- `WS /api/ws/listings/:id` — Per-listing real-time bidding

## Key DB Schema
- `listings`: status, category, auction_end_date, is_opc_certified, buyers_premium_percent, payment_method
- `vehicle_listings`: Dedicated vehicle collection
- `user_interests`: AI behavioral tracking (TTL: 90 days)
- `won_auctions`: Winner's Circle (TTL: 30 days)
- `seller_invoices`: Offline payment admin invoices

## 3rd Party Integrations
- Stripe (Payments) — User API Key
- SendGrid (Emails) — User API Key
- Twilio (SMS) — User API Key
- Cloudflare R2 / AWS S3 (Object Storage via boto3) — User API Key
- Gemini 2.5 Flash — Emergent LLM Key (local) / GEMINI_API_KEY (prod)

## Backlog
- (P2) Cloudflare CDN setup per `/app/memory/INFRASTRUCTURE_P2.md`
- (P2) Post-launch monitoring and alerting
- (Enhancement) Real-time performance dashboard
- (Enhancement) Automated Lighthouse audits
- (Low) i18n for EmailMarketingPricing page
