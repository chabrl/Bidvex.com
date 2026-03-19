# BidVex Auction Platform - Product Requirements Document

## Last Updated: March 19, 2026

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

## Backend Route Architecture (Post Phase 9)
```
/app/backend/
├── server.py              (~9,630 lines — admin settings, messaging, affiliates, misc)
├── models/
│   └── auction_models.py  # Listing, ListingCreate (with buyers_premium_rate), Bid, AutoBid models
├── routes/
│   ├── auth.py            # Authentication (login, register, password reset, sessions)
│   ├── admin.py           # Partner/user admin + verified firm toggle + email-preview
│   ├── auctions.py        # Auction lifecycle + bids + anti-sniping + buy-now + auto-bid
│   ├── listings.py        # Single + multi-item CRUD, terms, deletion requests
│   ├── marketplace.py     # Marketplace browsing/search/filter
│   ├── payments.py        # Unified checkout, payment-methods CRUD, subscriptions, fees + tax calc w/ listing premium
│   ├── webhooks.py        # Stripe + SendGrid webhooks, trust verification handlers
│   ├── dashboard.py       # Seller + buyer dashboards
│   ├── profiles.py        # User profiles, ratings, trust score, tax, GDPR, Stripe Connect
│   ├── tax.py             # Tax calculation API (GST/QST via services/tax_engine.py)
│   ├── tax_reports.py     # CRA compliance and tax report generation (admin only)
│   ├── ai_chat.py | fees.py | notifications.py | watchlist.py
│   └── team.py | vehicles.py
├── config/
│   └── email_templates.py # Verified SendGrid template IDs (bilingual EN/FR dicts) + premium fields
├── deps.py                # User model, shared auth
└── services/
    ├── tax_engine.py            # Authoritative tax engine (Decimal, ROUND_HALF_UP) + listing premium override
    ├── vehicle_pricing.py       # Vehicle pricing (imports GST_RATE from tax_engine)
    ├── vehicle_invoice.py       # Invoice generation (passes listing premium to email)
    ├── email_service.py         # SendGrid Dynamic Template sender
    ├── email_notifications.py   # Outlook-safe table-based HTML email templates + premium breakdown
    ├── cloud_storage.py         # Local file-based cloud storage mock
    └── subscription_service.py
```

## Completed Phases

### P0: Core Platform
- Vehicle Auction Module | Live Stripe Subscription Engine
- PDF Invoices (bilingual, tax compliant) | Stripe Fee-on-Top Model
- Partner Account System | Admin Command Center | Marketplace Sidebar Filter
- AI Chatbot (Claude Sonnet 4.5) | Subscription Pricing ($180/$300/year)
- Pay-to-Activate ($100 CAD/year) | Stripe Customer Portal | Partner Dashboard

### Refactoring Phases 1-5: ~2,930 lines extracted
- Auth -> routes/auth.py | Admin -> routes/admin.py
- Listings CRUD -> routes/listings.py | Auctions/Bidding -> routes/auctions.py
- Marketplace -> routes/marketplace.py

### P3: Trust & Compliance
- Verified Firm Badge | Bilingual Cookie Consent | Auth Refactor
- Outlook Email Fix (table-based) | SendGrid Template Audit (54 verified IDs)

### Phase 6: Payment/Dashboard Extraction (506 lines)
- Payments dedup | Dashboard extraction | Webhook consolidation | Admin email preview

### Phase 7: Profile Modularization (926 lines)
- 20 endpoints extracted to routes/profiles.py

### Phase 8: Tax Logic Modularization (Completed Mar 19, 2026)
- Created `routes/tax.py` with 4 endpoints (calculate, rates, structure, invoice-lines)
- Eliminated all inline float-based tax calcs from server.py
- Removed duplicate GST_RATE from vehicle_pricing.py
- 24/24 tests passed (iteration_61.json)

### Phase 9: Listing-Level Buyer's Premium (Completed Mar 19, 2026)
- **Schema**: Added `buyers_premium_rate` (Optional[float]) to `ListingCreate` model in `models/auction_models.py`
- **Backend**: `routes/listings.py` stores provided rate or falls back to org default (partners) / None (non-partners)
- **Tax Engine**: `services/tax_engine.py` `calculate_vehicle_payment` and `calculate_general_payment` accept `buyer_premium_rate_override` parameter
- **Payments API**: `routes/payments.py` `TaxCalculationRequest` accepts `buyers_premium_rate`, passes through to tax engine
- **Frontend Create Listing**: Added "Buyer's Premium (%)" input field with percent → rate conversion (15 → 0.15) before API call
- **UI Transparency**: Listing detail page shows amber banner "A X% buyer's premium applies to this lot"
- **Bidding Modal**: `BidConfirmationDialog` now shows "Total Estimated Price (Bid + Premium + Taxes)" and passes listing premium to API
- **Price Breakdown**: `PriceBreakdown` component accepts and passes listing premium to API
- **Email Sync**: `config/email_templates.py` auction_won and invoice templates include `buyers_premium_percent` and `buyers_premium_amount`; `email_notifications.py` `send_auction_won_email` shows premium breakdown
- 13/13 backend + 100% frontend tests passed (iteration_62.json)

## Key API Endpoints
- `POST /api/auth/login|register|forgot-password` -> routes/auth.py
- `POST /api/listings` (now accepts buyers_premium_rate) -> routes/listings.py
- `GET /api/listings/{id}` (returns custom_buyer_premium_rate) -> routes/listings.py
- `POST /api/payments/tax/calculate` (accepts buyers_premium_rate) -> routes/payments.py
- `GET /api/payments/tax/vehicle?price=X&buyers_premium_rate=Y` -> routes/payments.py
- `POST /api/tax-calc/calculate` -> routes/tax.py
- `GET /api/tax-calc/rates` -> routes/tax.py

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`

## Test Reports
- iteration_57.json — P3 Trust & Compliance (100%, 12/12)
- iteration_58.json — Template audit + Outlook fix (100%, 14/14)
- iteration_59.json — Phase 6 Modularization (100%, 21/21)
- iteration_60.json — Phase 7 Profile Modularization (100%, 23/23)
- iteration_61.json — Phase 8 Tax Modularization (100%, 24/24)
- iteration_62.json — Phase 9 Listing-Level Premium (100%, 13/13 + frontend)

## Upcoming Tasks

### P1 - High Priority
- [ ] Continue refactoring server.py: Extract messaging, affiliates, remaining modules
- [ ] Mount existing `routes/tax_reports.py` (CRA reporting — currently unmounted)

### P2 - Medium Priority
- [ ] Partner Pro subscription tier
- [ ] Swap local PDF invoice storage mock with real cloud service (S3/GCS)

### P3 - Low Priority
- [ ] Expand tests/test_emails.py to cover all 40+ templates

## Mocked Services
- Cloud storage for PDF invoices -> local directory `/data/invoices/` with HMAC-signed URLs
