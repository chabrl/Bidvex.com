# BidVex Auction Platform - Product Requirements Document

## Last Updated: March 2026

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
├── server.py              (~11,000 lines — dashboard, payments, admin settings)
├── routes/
│   ├── auth.py           # Authentication (login, register, password reset, sessions)
│   ├── admin.py          # Partner/user admin logic + verified firm toggle
│   ├── auctions.py       # Auction lifecycle + bids + anti-sniping + buy-now + auto-bid
│   ├── listings.py       # Single + multi-item CRUD, terms, deletion requests
│   ├── marketplace.py    # Marketplace browsing/search/filter
│   ├── ai_chat.py | fees.py | notifications.py | watchlist.py
│   ├── webhooks.py       # Partner activation/deactivation via Stripe
│   ├── payments.py | team.py | vehicles.py
├── config/
│   └── email_templates.py # Verified SendGrid template IDs (bilingual EN/FR dicts)
├── deps.py               (User model, shared auth)
└── services/
    ├── email_service.py        # SendGrid Dynamic Template sender
    ├── email_notifications.py  # Outlook-safe table-based HTML email templates
    ├── cloud_storage.py        # Local file-based cloud storage mock
    └── subscription_service.py
```

## All Completed Features (P0)
- Vehicle Auction Module | Live Stripe Subscription Engine
- PDF Invoices (bilingual, tax compliant) | Stripe Fee-on-Top Model
- Partner Account System (onboarding, admin, fee engine, Connect)
- Admin Command Center | Marketplace Sidebar Filter
- Sign-up Consent (Clickwrap) | Admin RBAC Team Management
- AI Chatbot (Claude Sonnet 4.5) | Subscription Pricing ($180/$300/year)
- Pay-to-Activate ($100 CAD/year recurring) with soft-lock on expiry
- Stripe Customer Portal for partner billing/invoices/tax receipts
- Partner Dashboard (`/partner/dashboard`)
- Refactoring: Phase 1-5 complete (~2,930 lines extracted from server.py)
- P3 Trust & Compliance: Verified Firm Badge, Bilingual Cookie Consent, Auth Refactor
- Outlook Email Fix: Table-based layouts, solid background-color
- SendGrid Template Audit: Replaced invalid category IDs with 54 verified individual template IDs

## SendGrid Template Config
- **Config file**: `/app/backend/config/email_templates.py`
- **Format**: `EmailTemplates.PASSWORD_RESET = {"en": "d-dbfba...", "fr": "d-9084..."}`
- **Resolution**: `EmailTemplates.get_id(template, language)` with EN fallback
- **Verified list**: `/app/backend/tests/email_test_report.json` (54 templates, all 202)
- **Runtime dict**: `server.py:DEFAULT_EMAIL_TEMPLATES` (lines 82-147)

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`

## Test Reports
- iteration_52.json — Pay-to-Activate (100%)
- iteration_53.json — Phase 2/3 refactor + Stripe Portal (100%)
- iteration_54.json — Partner Dashboard (100%, 42 total tests)
- iteration_57.json — P3 Trust & Compliance (100%, 12/12)
- iteration_58.json — Template audit + Outlook fix (100%, 14/14)

## Upcoming Tasks

### P1 - High Priority
- [ ] Continue refactoring server.py: Extract payments, user dashboards, remaining modules

### P2 - Medium Priority
- [ ] Partner Pro subscription tier
- [ ] Swap local PDF invoice storage mock with real cloud service (S3/GCS)

### P3 - Low Priority
- [ ] "Email to Friend" feature
- [ ] Expand tests/test_emails.py to cover all 40+ templates
