# BidVex Auction Platform - Product Requirements Document

## Last Updated: March 20, 2026

## Original Problem Statement
Build and maintain a sophisticated full-stack auction platform (BidVex) with real-time bidding, multi-item auctions, partner accounts, Stripe Connect payments, admin dashboard, AI chatbot, Canadian tax compliance, and full bilingual support (EN/FR).

## Architecture
```
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI (Python) — Modular route architecture
Database: MongoDB Atlas (Cloud)
Auth: JWT + Emergent Google Auth
AI: Claude Sonnet 4.5 via emergentintegrations
Payments: Stripe Connect + Subscriptions + Partner Fee + Customer Portal
Email: SendGrid (54 verified dynamic templates, bilingual EN/FR)
Jobs: APScheduler | i18n: react-i18next | PDF: ReportLab
```

## Backend Route Architecture (Post Phase 10)
```
/app/backend/
├── server.py              (~9,162 lines — admin settings, affiliates, WebSocket handlers, misc)
├── models/
│   ├── auction_models.py  # Listing, ListingCreate (with buyers_premium_rate, country, postal_code), Bid, AutoBid
│   └── message_models.py  # MessageCreate, Message
├── routes/
│   ├── auth.py | admin.py | auctions.py | listings.py | marketplace.py
│   ├── messages.py | payments.py | webhooks.py | dashboard.py | profiles.py
│   ├── tax.py | tax_reports.py | ai_chat.py | fees.py | notifications.py
│   └── watchlist.py | team.py | vehicles.py
├── config/email_templates.py
├── deps.py
├── scripts/normalize_locations.py  # DB migration for location normalization
└── services/ (tax_engine, vehicle_pricing, vehicle_invoice, email_*, cloud_storage, subscription)
```

## Completed Phases

### P0: Core Platform
- Vehicle Auction | Stripe Subscriptions | PDF Invoices | Partner System | Admin | Marketplace | AI Chatbot

### Refactoring Phases 1-10 (~1,893 lines extracted from server.py)
- Auth, Admin, Listings, Auctions, Marketplace, Payments, Dashboard, Profiles, Tax, Messages

### Phase 8-10: Recent Modularization (Completed Mar 19, 2026)
- Tax Logic Modularization | Listing-Level Buyer's Premium | Messaging Extraction + CRA Mount

### Phase A: Unified Location Architecture (Completed Mar 20, 2026)
- **LocationSelector.js**: Hierarchical combobox (Country → Province → City → Postal Code)
- **locations.json**: CA (13 provinces, 200+ cities, deep QC coverage) + US (50 states, 15-20 cities each)
- **Integrated into 3 sell flows**: CreateListingPage, CreateMultiItemListing, CreateVehicleListingPage
- **Backend models updated**: Added `country` and `postal_code` fields
- **DB migration executed**: "Quebec" → "QC", added country: "CA" to all listings
- Tests: 6/6 backend + frontend (iteration_64)

### Phase B: Mobile-First UX & Geo Pre-filling (Completed Mar 20, 2026)
- **Vertical stacking**: All form groups use `grid-cols-1 md:grid-cols-2` for proper mobile layout
- **Touch-target optimization**: All buttons and inputs min-h-[48px] for fat-finger accessibility
- **Full-width buttons**: Navigation buttons (Previous/Next/Submit) full-width on mobile via `flex-col-reverse sm:flex-row`
- **Input keyboards**: `inputMode="decimal"` on all price fields for numeric keypad on mobile
- **Image grids**: 2-col on mobile, 3-4-col on desktop
- **Responsive steppers**: Multi-item (5-step) and Vehicle (6-step) steppers with `overflow-x-auto`, compact circles on mobile, hidden labels
- **Upload method buttons**: Stack into single column on mobile (`grid-cols-1 sm:grid-cols-3`)
- **useGeoLocation hook**: IP-based detection via ip-api.com, cached in sessionStorage, auto-fills Country + Province in LocationSelector
- **Vehicle form**: Responsive pricing grid (2-col mobile → 4-col desktop), responsive deposit section
- Tests: 100% frontend pass across mobile (390x844) and desktop (1920x800) (iteration_65)

## server.py Size History
- Start: ~11,055 → After Phase 10: 9,162 lines | Total extracted: ~1,893 lines

## Key API Endpoints
- `POST /api/auth/login|register|forgot-password` -> routes/auth.py
- `POST /api/listings` (accepts country, postal_code, buyers_premium_rate) -> routes/listings.py
- `PUT /api/listings/{id}` (allows country, postal_code) -> routes/listings.py
- `POST /api/multi-item-listings` -> routes/listings.py
- `POST /api/messages` -> routes/messages.py
- `POST /api/payments/tax/calculate` -> routes/payments.py
- `GET /api/tax/reports` -> routes/tax_reports.py

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`

## Test Reports
- iteration_61-63 — Phases 8-10 (Tax, Premium, Messaging)
- iteration_64 — Phase A Location Architecture (100%, 6/6 backend + frontend)
- iteration_65 — Phase B Mobile Responsiveness (100%, all viewports)

## Upcoming Tasks

### P0 - High Priority
- [ ] **Phase C**: Full EN/FR-QC multilingual translation for all "Sell" flow labels, placeholders, error messages (known issue: CreateMultiItemListing shows raw i18n keys)

### P1 - Medium Priority
- [ ] Continue refactoring server.py: Extract affiliates, categories, remaining admin modules
- [ ] Admin Tax Dashboard to visualize GST/QST collections
- [ ] Premium Comparison view in marketplace

### P2 - Low Priority
- [ ] Partner Pro subscription tier
- [ ] Swap local PDF invoice storage mock with real cloud service (S3/GCS)
- [ ] Expand email template test coverage

## Mocked Services
- Cloud storage for PDF invoices -> local directory `/data/invoices/` with HMAC-signed URLs
