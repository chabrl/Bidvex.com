# BidVex Auction Platform - Product Requirements Document

## Last Updated: February 2026

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
├── server.py              (~11,300 lines — auth, dashboard, payments, admin settings)
│   ├── routes/
│   │   ├── admin.py          # Partner/user admin logic
│   │   ├── auctions.py       # Auction lifecycle + bids + anti-sniping + buy-now + auto-bid
│   │   ├── listings.py       # Single + multi-item CRUD, terms, deletion requests
│   │   ├── marketplace.py    # Marketplace browsing/search/filter
├── deps.py                (User model, shared auth)
├── routes/
│   ├── admin.py           (1,395 lines — User/partner mgmt, email settings)
│   ├── marketplace.py     (474 lines — Browse, search, filter, promoted)
│   ├── ai_chat.py | fees.py | notifications.py | watchlist.py
│   ├── webhooks.py        (Partner activation/deactivation via Stripe)
│   ├── payments.py | team.py | vehicles.py | auctions.py
└── services/subscription_service.py
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
- **Refactoring**: Phase 1 (AI, Fees, Notifications, Watchlist), Phase 2 (Admin/Partner), Phase 3 (Marketplace), Phase 4 (Admin user mgmt cleanup from server.py), Phase 5 (Listings + Bids extraction) — ~2,930 lines extracted

## Session Log (Mar 19, 2026)
1. Pay-to-Activate Partner Flow — $100 CAD/year recurring Stripe subscription
2. Phase 2 Refactor — Partner admin routes → routes/admin.py
3. Phase 3 Refactor — Marketplace routes → routes/marketplace.py
4. Stripe Customer Portal — POST /api/partner/manage-billing
5. Tests updated — 28 legacy + 14 new partner tests all pass
6. **Partner Dashboard page** — Standalone `/partner/dashboard` with:
   - Subscription & Billing card (Stripe Portal for invoices & tax receipts)
   - Soft Lock banner with Pay Now when fee unpaid
   - Listing Stats grid (active, total, bids, multi-lot)
   - Account Details (company, 3% fee, premium rate, Connect status)
   - Recent Activity feed | Quick Links

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`

## Test Reports
- iteration_52.json — Pay-to-Activate (100%)
- iteration_53.json — Phase 2/3 refactor + Stripe Portal (100%)
- iteration_54.json — Partner Dashboard (100%, 42 total tests)

## Upcoming Tasks

### P1 - High Priority
- [x] server.py Phase 4: Deduplicate admin user mgmt routes (673 lines removed, moved to routes/admin.py)
- [x] server.py Phase 5: Extract listings CRUD, bids, multi-item auctions (1460 lines → routes/listings.py + routes/auctions.py)

### P2 - Medium Priority
- [x] Cache marketplace filter counts — 5-min Stale-While-Revalidate in-memory cache
- [x] PDF Invoice cloud storage — HMAC-signed URLs, persistent at /data/invoices/
- [x] Database indexing — background indexes on bids, lot_bids, auto_bids, invoices, subscription_invoices
- [ ] Partner Pro subscription tier

### P3 - Low Priority
- [ ] Cookie consent i18n | "Email to Friend" | DB indexing on auction_id
- [ ] "Verified Auction Firm" badge on partner listings
