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

## Backend Route Architecture (Post Phase 6)
```
/app/backend/
├── server.py              (~10,549 lines — admin settings, user profiles, misc)
├── routes/
│   ├── auth.py            # Authentication (login, register, password reset, sessions)
│   ├── admin.py           # Partner/user admin + verified firm toggle + email-preview
│   ├── auctions.py        # Auction lifecycle + bids + anti-sniping + buy-now + auto-bid
│   ├── listings.py        # Single + multi-item CRUD, terms, deletion requests
│   ├── marketplace.py     # Marketplace browsing/search/filter
│   ├── payments.py        # Unified checkout, payment-methods CRUD, subscriptions, fees
│   ├── webhooks.py        # Stripe + SendGrid webhooks, trust verification handlers
│   ├── dashboard.py       # Seller + buyer dashboards (NEW)
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
- Auth → routes/auth.py
- Admin → routes/admin.py
- Listings CRUD → routes/listings.py
- Auctions/Bidding → routes/auctions.py
- Marketplace → routes/marketplace.py

### P3: Trust & Compliance
- Verified Firm Badge (admin toggle + UI badge)
- Bilingual Cookie Consent (i18next EN/FR)
- Auth Refactor (server.py → routes/auth.py)
- Outlook Email Fix (table-based layouts, solid background-color)
- SendGrid Template Audit (54 verified template IDs, bilingual dict format)

### Phase 6: Modularization (Completed Mar 19, 2026)
- **Payments dedup**: Removed duplicate payment endpoints from server.py; unified /checkout handles both listing purchases + subscriptions; payment-methods CRUD now stores in DB with trust verification
- **Dashboard extraction**: Moved /dashboard/seller and /dashboard/buyer to routes/dashboard.py
- **Webhook consolidation**: Moved _handle_setup_intent_succeeded and _handle_payment_method_attached to routes/webhooks.py; added multi-secret verification
- **Admin email preview**: New GET /api/admin/email-preview/{template_key}?language=en|fr sends test email with mock data to admin's address; supports all 27 template keys (54 total EN/FR)
- **Net reduction**: 506 lines removed from server.py (11,055 → 10,549)

## Key API Endpoints
- `POST /api/auth/login|register|forgot-password` → routes/auth.py
- `GET /api/dashboard/seller|buyer` → routes/dashboard.py
- `POST /api/payments/checkout` (listing_id or price_id) → routes/payments.py
- `GET|POST|DELETE /api/payments/payment-methods` → routes/payments.py
- `POST /api/webhooks/stripe` → routes/webhooks.py (multi-secret)
- `GET /api/admin/email-preview/{key}?language=en|fr` → routes/admin.py

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`

## Test Reports
- iteration_57.json — P3 Trust & Compliance (100%, 12/12)
- iteration_58.json — Template audit + Outlook fix (100%, 14/14)
- iteration_59.json — Phase 6 Modularization (100%, 21/21)

## Upcoming Tasks

### P1 - High Priority
- [ ] Continue refactoring server.py: Extract user profiles, tax, messages, affiliate modules

### P2 - Medium Priority
- [ ] Partner Pro subscription tier
- [ ] Swap local PDF invoice storage mock with real cloud service (S3/GCS)

### P3 - Low Priority
- [ ] "Email to Friend" feature
- [ ] Expand tests/test_emails.py to cover all 40+ templates

## Mocked Services
- Cloud storage for PDF invoices → local directory `/data/invoices/` with HMAC-signed URLs
