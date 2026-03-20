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

## Backend Route Architecture
```
/app/backend/
├── server.py              (~9,162 lines)
├── models/ (auction_models.py, message_models.py)
├── routes/ (auth, admin, auctions, listings, marketplace, messages, payments, webhooks, dashboard, profiles, tax, tax_reports, ai_chat, fees, notifications, watchlist, team, vehicles)
├── config/email_templates.py | deps.py
├── scripts/normalize_locations.py
└── services/ (tax_engine, vehicle_pricing, vehicle_invoice, email_*, cloud_storage, subscription)
```

## Completed Phases

### Core Platform (P0)
- Vehicle Auction | Stripe Subscriptions | PDF Invoices | Partner System | Admin | Marketplace | AI Chatbot

### Refactoring Phases 1-10 (~1,893 lines extracted from server.py)

### Phase 8-10 (Completed Mar 19, 2026)
- Tax Logic Modularization | Listing-Level Buyer's Premium | Messaging Extraction + CRA Mount

### Phase A: Unified Location Architecture (Completed Mar 20, 2026)
- LocationSelector.js: Hierarchical combobox (Country → Province → City → Postal Code)
- locations.json: CA (13 provinces, 200+ cities) + US (50 states, 15-20 cities each)
- Integrated into 3 sell flows, backend models updated (country, postal_code fields)
- DB migration: "Quebec" → "QC", added country: "CA" | Tests: iteration_64 (6/6)

### Phase B: Mobile-First UX & Geo Pre-filling (Completed Mar 20, 2026)
- Vertical stacking on mobile, 48px touch targets, full-width buttons, inputMode="decimal"
- Responsive steppers, 2-col image grids on mobile, responsive upload method buttons
- useGeoLocation hook (ip-api.com, sessionStorage cache) | Tests: iteration_65 (100%)

### Phase C: Full EN/FR-QC Multilingual Refactor (Completed Mar 20, 2026)
- **createListing namespace**: Added ~100 translation keys to both EN and FR-QC in i18n.js
  - All labels, placeholders, validation messages, tooltips, step labels, agreement text
  - Quebecois French: "Téléverser" (not "Uploader"), "Enchère" (not "Vente aux enchères"), etc.
- **locationSelector namespace**: 20 keys in EN/FR with dynamic labels:
  - Province/État based on country selection
  - Code postal/Code ZIP based on country selection
- **vehicleListing namespace**: 80+ keys for vehicle form (VIN, specs, condition, photos, auction, review)
  - FR-QC: NIV (not VIN), Marque, Modèle, Cylindrée, Puissance, etc.
- **CreateListingPage.js**: All hardcoded English replaced with t() calls (Title, Description, Category, Condition, Pricing, Images, Shipping, Visit, Submit)
- **CreateVehicleListingPage.js**: Added useTranslation hook, STEPS array translated, all major labels wrapped
- **common.selectOption**: Added to both EN/FR
- **Zero raw i18n keys** in any sell flow for both EN and FR locales
- **Mobile FR verified**: No text overflow from longer French strings
- Tests: iteration_66 (100% - all 3 forms, both locales, dynamic labels)

## Key DB Schema Changes
- listings: `country: Optional[str] = "CA"`, `postal_code: Optional[str] = None` added
- multi_item_listings: Same additions
- `region` field now stores ISO codes ("QC", "ON") after migration

## Key API Endpoints
- `POST /api/listings` (accepts country, postal_code, buyers_premium_rate)
- `PUT /api/listings/{id}` (allows country, postal_code)
- `POST /api/multi-item-listings`
- Standard auth, auction, marketplace, payment, messaging endpoints

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`

## Test Reports
- iteration_64 — Phase A Location Architecture (100%)
- iteration_65 — Phase B Mobile Responsiveness (100%)
- iteration_66 — Phase C i18n Multilingual (100%)

## Upcoming Tasks

### P1 - Medium Priority
- [ ] Continue refactoring server.py: Extract affiliates, categories, remaining admin modules
- [ ] Admin Tax Dashboard to visualize GST/QST collections
- [ ] Premium Comparison view in marketplace

### P2 - Low Priority
- [ ] Partner Pro subscription tier
- [ ] Swap local PDF invoice storage mock with real cloud service (S3/GCS)
- [ ] Expand email template test coverage
- [ ] Minor UI: Floating chat button overflow on 390px mobile

## Mocked Services
- Cloud storage for PDF invoices -> local directory `/data/invoices/` with HMAC-signed URLs
