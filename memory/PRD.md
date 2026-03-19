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
Email: SendGrid
Jobs: APScheduler | i18n: react-i18next | PDF: ReportLab
```

## Backend Route Architecture
```
/app/backend/
├── server.py              (~11,000 lines — dashboard, payments, admin settings)
│   ├── routes/
│   │   ├── auth.py           # Authentication (login, register, password reset, sessions)
│   │   ├── admin.py          # Partner/user admin logic + verified firm toggle
│   │   ├── auctions.py       # Auction lifecycle + bids + anti-sniping + buy-now + auto-bid
│   │   ├── listings.py       # Single + multi-item CRUD, terms, deletion requests
│   │   ├── marketplace.py    # Marketplace browsing/search/filter
│   │   ├── ai_chat.py | fees.py | notifications.py | watchlist.py
│   │   ├── webhooks.py       # Partner activation/deactivation via Stripe
│   │   ├── payments.py | team.py | vehicles.py
├── deps.py                (User model, shared auth)
└── services/
    ├── email_notifications.py  # Outlook-safe table-based email templates
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
- **Pay-to-Activate** ($100 CAD/year recurring) with soft-lock on expiry
- **Stripe Customer Portal** for partner billing/invoices/tax receipts
- **Partner Dashboard** (`/partner/dashboard`) — subscription status, billing portal, listing stats, recent activity, account details, soft-lock banner
- **Refactoring**: Phase 1-5 complete (~2,930 lines extracted from server.py)
- **P3 Trust & Compliance**: Verified Firm Badge, Bilingual Cookie Consent, Auth Refactor, Outlook Email Fix

## P3 Trust & Compliance (Completed Mar 19, 2026)
1. **Auth Refactor** — Extracted all auth logic from server.py to routes/auth.py (login, register, forgot-password, reset, sessions, force-reset)
2. **Verified Firm Badge** — Admin toggle endpoint, VerifiedBadge.js component, displayed on listing cards and detail pages
3. **Bilingual Cookie Consent** — i18next-powered EN/FR banner with Accept All, Reject All, Manage Preferences; persists in localStorage
4. **Outlook Email Fix** — Converted all email templates to table-based layouts with inline CSS, replaced linear-gradient with solid background-color

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`

## Test Reports
- iteration_52.json — Pay-to-Activate (100%)
- iteration_53.json — Phase 2/3 refactor + Stripe Portal (100%)
- iteration_54.json — Partner Dashboard (100%, 42 total tests)
- iteration_57.json — P3 Trust & Compliance (100%, 12/12 backend + frontend)

## Upcoming Tasks

### P1 - High Priority
- [x] server.py Phase 4: Deduplicate admin user mgmt routes
- [x] server.py Phase 5: Extract listings CRUD, bids, multi-item auctions
- [ ] Continue refactoring server.py: Extract payments, user dashboards, remaining modules

### P2 - Medium Priority
- [x] Cache marketplace filter counts — 5-min Stale-While-Revalidate in-memory cache
- [x] PDF Invoice cloud storage — HMAC-signed URLs, persistent at /data/invoices/
- [x] Database indexing — background indexes on bids, lot_bids, auto_bids, invoices, subscription_invoices
- [ ] Partner Pro subscription tier
- [ ] Swap local PDF invoice storage mock with real cloud service (S3/GCS)

### P3 - Low Priority
- [x] Cookie consent i18n
- [x] "Verified Auction Firm" badge on partner listings
- [x] Auth refactor to routes/auth.py
- [x] Outlook email template fix (table-based layouts)
- [ ] "Email to Friend" feature
- [ ] Expand tests/test_emails.py to cover all 40+ templates
