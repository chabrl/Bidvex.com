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

## Backend Route Architecture (Post Phase 7)
```
/app/backend/
├── server.py              (~9,623 lines — admin settings, messaging, affiliates, misc)
├── routes/
│   ├── auth.py            # Authentication (login, register, password reset, sessions)
│   ├── admin.py           # Partner/user admin + verified firm toggle + email-preview
│   ├── auctions.py        # Auction lifecycle + bids + anti-sniping + buy-now + auto-bid
│   ├── listings.py        # Single + multi-item CRUD, terms, deletion requests
│   ├── marketplace.py     # Marketplace browsing/search/filter
│   ├── payments.py        # Unified checkout, payment-methods CRUD, subscriptions, fees
│   ├── webhooks.py        # Stripe + SendGrid webhooks, trust verification handlers
│   ├── dashboard.py       # Seller + buyer dashboards
│   ├── profiles.py        # User profiles, ratings, trust score, tax, GDPR, Stripe Connect (NEW)
│   ├── ai_chat.py | fees.py | notifications.py | watchlist.py
│   └── team.py | vehicles.py
├── config/
│   └── email_templates.py # Verified SendGrid template IDs (bilingual EN/FR dicts)
├── deps.py                # User model, shared auth
└── services/
    ├── email_service.py        # SendGrid Dynamic Template sender
    ├── email_notifications.py  # Outlook-safe table-based HTML email templates
    ├── cloud_storage.py        # Local file-based cloud storage mock
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
- Auth → routes/auth.py | Admin → routes/admin.py
- Listings CRUD → routes/listings.py | Auctions/Bidding → routes/auctions.py
- Marketplace → routes/marketplace.py

### P3: Trust & Compliance
- Verified Firm Badge | Bilingual Cookie Consent | Auth Refactor
- Outlook Email Fix (table-based) | SendGrid Template Audit (54 verified IDs)

### Phase 6: Payment/Dashboard Extraction (506 lines)
- Payments dedup | Dashboard extraction | Webhook consolidation | Admin email preview

### Phase 7: Profile Modularization (926 lines, Completed Mar 19, 2026)
- **20 endpoints extracted** to routes/profiles.py:
  - User lookup: GET /users/{id}, /users/{id}/profile-summary
  - Profile update: PUT /users/me (with preferred_language en/fr validation), PUT /profile
  - User stats: GET /users/me/stats
  - Ratings: POST /ratings, GET /users/{id}/ratings
  - Seller: GET /sellers/{id}, GET /sellers/{id}/trust-score
  - Tax: PUT /users/me/tax-profile, GET/PUT /users/me/tax-info
  - Stripe Connect: POST/GET /users/me/stripe-connect/onboard|status|dashboard-link
  - GDPR: POST /user/request-data-deletion, GET /user/data-deletion-status, POST /user/cancel-data-deletion, GET /user/export-data
  - Upload: POST /upload-document

## server.py Size History
- Start: ~11,055 lines
- After Phase 6: 10,549 lines (-506)
- After Phase 7: 9,623 lines (-926)
- **Total extracted: ~1,432 lines**

## Key API Endpoints
- `POST /api/auth/login|register|forgot-password` → routes/auth.py
- `PUT /api/users/me` (name, preferred_language en/fr) → routes/profiles.py
- `GET /api/sellers/{id}/trust-score` → routes/profiles.py
- `GET /api/dashboard/seller|buyer` → routes/dashboard.py
- `POST /api/payments/checkout` → routes/payments.py
- `POST /api/webhooks/stripe` → routes/webhooks.py
- `GET /api/admin/email-preview/{key}?language=en|fr` → routes/admin.py

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`

## Test Reports
- iteration_57.json — P3 Trust & Compliance (100%, 12/12)
- iteration_58.json — Template audit + Outlook fix (100%, 14/14)
- iteration_59.json — Phase 6 Modularization (100%, 21/21)
- iteration_60.json — Phase 7 Profile Modularization (100%, 23/23)

## Upcoming Tasks

### P1 - High Priority
- [ ] Continue refactoring server.py: Extract messaging, affiliates, remaining modules

### P2 - Medium Priority
- [ ] Partner Pro subscription tier
- [ ] Swap local PDF invoice storage mock with real cloud service (S3/GCS)

### P3 - Low Priority
- [ ] "Email to Friend" feature
- [ ] Expand tests/test_emails.py to cover all 40+ templates

## Mocked Services
- Cloud storage for PDF invoices → local directory `/data/invoices/` with HMAC-signed URLs
