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
│   └── message_models.py  # MessageCreate, Message (canonical models for messaging)
├── routes/
│   ├── auth.py            # Authentication (login, register, password reset, sessions)
│   ├── admin.py           # Partner/user admin + verified firm toggle + email-preview
│   ├── auctions.py        # Auction lifecycle + bids + anti-sniping + buy-now + auto-bid
│   ├── listings.py        # Single + multi-item CRUD, terms, deletion requests
│   ├── marketplace.py     # Marketplace browsing/search/filter
│   ├── messages.py        # Internal chat, inbox, conversations, attachments, admin
│   ├── payments.py        # Unified checkout, payment-methods CRUD, subscriptions, fees + tax calc
│   ├── webhooks.py        # Stripe + SendGrid webhooks, trust verification handlers
│   ├── dashboard.py       # Seller + buyer dashboards
│   ├── profiles.py        # User profiles, ratings, trust score, tax, GDPR, Stripe Connect
│   ├── tax.py             # Tax calculation API (GST/QST via services/tax_engine.py)
│   ├── tax_reports.py     # CRA tax reports, GST/QST filing
│   ├── ai_chat.py | fees.py | notifications.py | watchlist.py
│   └── team.py | vehicles.py
├── config/
│   └── email_templates.py # Verified SendGrid template IDs + premium fields
├── deps.py                # User model, shared auth
├── scripts/
│   └── normalize_locations.py  # DB migration for location data normalization
└── services/
    ├── tax_engine.py            # Authoritative tax engine (Decimal, ROUND_HALF_UP) + listing premium override
    ├── vehicle_pricing.py       # Vehicle pricing (imports GST_RATE from tax_engine)
    ├── vehicle_invoice.py       # Invoice generation (passes listing premium to email)
    ├── email_service.py         # SendGrid Dynamic Template sender
    ├── email_notifications.py   # Outlook-safe table-based HTML + premium breakdown
    ├── cloud_storage.py         # Local file-based cloud storage mock
    └── subscription_service.py
```

## Completed Phases

### P0: Core Platform
- Vehicle Auction Module | Live Stripe Subscription Engine
- PDF Invoices (bilingual, tax compliant) | Stripe Fee-on-Top Model
- Partner Account System | Admin Command Center | Marketplace Sidebar Filter
- AI Chatbot (Claude Sonnet 4.5) | Subscription Pricing ($180/$300/year)

### Refactoring Phases 1-5: ~2,930 lines extracted
- Auth -> routes/auth.py | Admin -> routes/admin.py
- Listings -> routes/listings.py | Auctions -> routes/auctions.py
- Marketplace -> routes/marketplace.py

### P3: Trust & Compliance
- Verified Firm Badge | Bilingual Cookie Consent | Auth Refactor
- Outlook Email Fix (table-based) | SendGrid Template Audit (54 verified IDs)

### Phase 6: Payment/Dashboard Extraction (506 lines)
### Phase 7: Profile Modularization (926 lines)

### Phase 8: Tax Logic Modularization (Completed Mar 19, 2026)
- Created routes/tax.py | Eliminated inline float tax calcs | 24/24 tests

### Phase 9: Listing-Level Buyer's Premium (Completed Mar 19, 2026)
- Schema + backend + frontend + email sync for per-listing premium | 13/13 tests

### Phase 10: Messaging Extraction + CRA Mount (Completed Mar 19, 2026)
- Extracted 12 REST endpoints to routes/messages.py (~470 lines removed)
- Mounted routes/tax_reports.py | 16/16 tests

### Phase A: Unified Location Architecture (Completed Mar 20, 2026)
- **Created `/app/frontend/src/data/locations.json`**: Comprehensive CA (13 provinces/territories with 200+ cities, deep QC coverage) + US (50 states with 15-20 cities each)
- **Built `/app/frontend/src/components/LocationSelector.js`**: Reusable hierarchical component with:
  - Country → Province/State → City → Postal Code cascade
  - Searchable comboboxes using Shadcn Command + Popover (cmdk)
  - "Enter manually" toggle for city (escape hatch for unlisted cities)
  - Regex-validated postal/ZIP codes (CA: A1A 1A1, US: 12345)
  - Cascade reset (changing country resets province/city/postal)
- **Integrated into 3 sell flows**: CreateListingPage.js, CreateMultiItemListing.js, CreateVehicleListingPage.js
- **Backend model updates**: Added `country` (Optional[str] = "CA") and `postal_code` (Optional[str]) to ListingCreate, Listing, MultiItemListingCreate, MultiItemListing
- **DB migration executed**: `normalize_locations.py` converted "Quebec" → "QC", added `country: "CA"` to all 5 existing listings
- **All 6/6 backend + frontend tests passed** (iteration_64.json)

## server.py Size History
- Start: ~11,055 lines
- After Phase 6: 10,549 lines (-506)
- After Phase 7: 9,623 lines (-926)
- After Phase 10: 9,162 lines (-470)
- Total extracted: ~1,893 lines

## Key API Endpoints
- `POST /api/auth/login|register|forgot-password` -> routes/auth.py
- `POST /api/listings` (accepts buyers_premium_rate, country, postal_code) -> routes/listings.py
- `PUT /api/listings/{id}` (allows country, postal_code in updates) -> routes/listings.py
- `POST /api/messages` -> routes/messages.py
- `GET /api/conversations` -> routes/messages.py
- `POST /api/payments/tax/calculate` (accepts buyers_premium_rate) -> routes/payments.py
- `GET /api/tax/reports` -> routes/tax_reports.py
- `POST /api/tax-calc/calculate` -> routes/tax.py

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`

## Test Reports
- iteration_59.json — Phase 6 Modularization (100%, 21/21)
- iteration_60.json — Phase 7 Profile Modularization (100%, 23/23)
- iteration_61.json — Phase 8 Tax Modularization (100%, 24/24)
- iteration_62.json — Phase 9 Listing-Level Premium (100%, 13/13 + frontend)
- iteration_63.json — Phase 10 Messaging + CRA Mount (100%, 16/16 + frontend)
- iteration_64.json — Phase A Location Architecture (100%, 6/6 backend + frontend)

## Upcoming Tasks

### P0 - High Priority
- [ ] **Phase B**: Refactor "Sell" multi-step forms to be 100% mobile-responsive (fat-finger proof buttons, vertical stacking)
- [ ] **Phase C**: Implement full EN/FR-QC multilingual translation for all "Sell" flows (labels, placeholders, error messages)

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
