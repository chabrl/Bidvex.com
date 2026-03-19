# BidVex Auction Platform - Product Requirements Document

## Last Updated: March 19, 2026

## Original Problem Statement
Build and maintain a sophisticated full-stack auction platform (BidVex) with:
- Real-time bidding capabilities
- Multi-item and single-item auction listings
- Comprehensive admin panel
- Canadian tax compliance system
- Full bilingual support (EN/FR)
- Hybrid Fee Calculation Engine
- Quebec Tax & Invoicing Engine
- Marketplace Engine with Stripe Connect
- Subscription Tier System
- Seller Earnings Dashboard
- Trust Status Verification via SetupIntent
- Enterprise Vehicle Auction Module
- Partner Account System with Stripe Connect
- Admin Command Center with financial reporting
- Sign-up Terms & Policy Consent (Clickwrap)
- Admin RBAC Team Management
- AI Chatbot (Claude Sonnet 4.5)
- Pay-to-Activate Partner Flow ($100 CAD/year recurring)
- Stripe Customer Portal for partner billing

## Architecture
```
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI (Python) — Modular route architecture
Database: MongoDB Atlas (Cloud)
Authentication: JWT + Emergent Google Auth
AI: Claude Sonnet 4.5 via emergentintegrations
Payments: Stripe Connect + Subscriptions + Partner Fee Subscriptions + Customer Portal
Email: SendGrid
Background Jobs: APScheduler
i18n: react-i18next (EN/FR bilingual support)
PDF Generation: ReportLab (bilingual invoices)
```

## Backend Architecture (Modular Routes)
```
/app/backend/
├── server.py              (~13,365 lines — listings CRUD, bids, auth, auctions, etc.)
├── deps.py                (Shared dependencies — User model, auth functions)
├── routes/
│   ├── admin.py           (1,395 lines — User mgmt, partner admin, email settings)
│   ├── marketplace.py     (474 lines — Browse, search, filter, promoted listings)
│   ├── ai_chat.py         (AI chatbot endpoints)
│   ├── fees.py            (Fee calculation endpoints)
│   ├── notifications.py   (Notification endpoints)
│   ├── watchlist.py       (Watchlist endpoints)
│   ├── webhooks.py        (Stripe/SendGrid webhooks — partner activation/deactivation)
│   ├── payments.py        (Stripe Connect payment endpoints)
│   ├── team.py            (RBAC team management)
│   ├── vehicles.py        (Vehicle auction module)
│   └── auctions.py        (Auction lifecycle management)
└── services/
    └── subscription_service.py (Subscription tier logic)
```

## Current Status: ALL P0 FEATURES COMPLETE

### Session Updates (Mar 19, 2026)

**Phase 2 Refactoring — Admin Routes Extraction:**
- Moved partner admin endpoints from server.py to routes/admin.py: verify, reject, toggle, premium-rate, email settings
- Fixed admin.py auth: replaced broken HTTPAuthorizationCredentials proxy with direct JWT decode in require_admin()
- admin.py now contains both user management (pre-existing) and partner management (newly extracted)

**Phase 3 Refactoring — Marketplace Routes Extraction:**
- Created NEW routes/marketplace.py (474 lines)
- Moved: GET /marketplace/items, GET /marketplace/filter-counts, POST /listings/search/location, GET /promoted-listings, POST /marketplace/items/{item_id}/track-click
- server.py reduced from ~14,337 to ~13,365 lines (~970 line reduction)

**Stripe Customer Portal Integration:**
- New endpoint: POST /api/partner/manage-billing
- Generates Stripe Customer Portal session for partners to manage billing, download invoices, update payment methods

**Test Suite Updated:**
- test_new_features_iteration_48.py updated: $213.45/$355.54 monthly → $180/$300 yearly pricing
- Added 11 new tests for partner fee endpoints, marketplace, and webhooks
- All 28 tests pass (iteration_53 — 100%)

### Previous Session (Mar 19, 2026 — Pay-to-Activate)
- Partner verification → $100 CAD/year Stripe recurring subscription
- Webhook handles activation/deactivation/renewal
- Frontend lockdown UI for unpaid partners

## API Endpoints (New/Modified in This Session)
- `POST /api/partner/manage-billing` — Stripe Customer Portal session (NEW)
- All admin partner endpoints now served from routes/admin.py (MOVED)
- All marketplace endpoints now served from routes/marketplace.py (MOVED)

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`

## Upcoming Tasks (Prioritized)

### P1 - High Priority
- [ ] Refactor server.py Phase 4: Remove duplicated admin user mgmt endpoints (now in admin.py but also still in server.py)
- [ ] Refactor server.py Phase 5: Extract listings CRUD, bids, multi-item auctions

### P2 - Medium Priority
- [ ] Cache marketplace filter counts for performance (Redis/in-memory)
- [ ] PDF Invoice cloud storage
- [ ] Partner Dashboard page (subscription status, invoices, payment method management)

### P3 - Low Priority
- [ ] Cookie consent translation (i18n integration)
- [ ] "Email to Friend" feature for vehicle listings
- [ ] Database indexing on `auction_id` in bids collection
- [ ] "Verified Auction Firm" badge on partner listings
