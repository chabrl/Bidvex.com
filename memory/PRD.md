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
- **Pay-to-Activate Partner Flow** NEW

## Architecture
```
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI (Python) 
Database: MongoDB Atlas (Cloud)
Authentication: JWT + Emergent Google Auth
AI: Claude Sonnet 4.5 via emergentintegrations (upgraded from GPT-4)
Payments: Stripe Connect + SetupIntents + Subscriptions + Tax Engine + Partner Fee Subscriptions
Email: SendGrid
Background Jobs: APScheduler
i18n: react-i18next (EN/FR bilingual support)
PDF Generation: ReportLab (bilingual invoices)
```

## Current Status: ALL P0 FEATURES COMPLETE

### Session Update (Mar 19, 2026 — Pay-to-Activate Partner Feature)

**Pay-to-Activate Implementation:**
- Admin verifies partner → Stripe Checkout Session created for $100 CAD/year recurring subscription
- Email sent with payment link via SendGrid
- Partner marked as `is_partner=True`, `platform_fee_paid=False` until payment
- Webhook handles `checkout.session.completed` → sets `platform_fee_paid=True`
- Webhook handles `customer.subscription.deleted` → soft-locks partner (`platform_fee_paid=False`)
- Webhook handles `invoice.payment_failed` → soft-locks partner
- Webhook handles `invoice.payment_succeeded` → re-activates partner after failed payment
- Listing creation (single + multi-item) blocked for partners with `platform_fee_paid=False`
- Frontend lockdown UI: banner in SellOptionsModal, lockdown pages in CreateListingPage and CreateMultiItemListing
- Partner Manager UI updated with Fee Paid/Fee Pending badges
- New endpoints: `GET /api/partner/payment-status`, `POST /api/partner/create-checkout`

**Bug Fixed:**
- webhooks_router was not mounted in api_router (404 on /api/webhooks/stripe) — FIXED

**Files Modified:**
- `/app/backend/deps.py` — Added `platform_fee_paid`, `partner_subscription_id` to User model
- `/app/backend/server.py` — Modified verify_partner, added _get_or_create_partner_fee_price, partner payment endpoints, listing permission checks, partner toggle updates
- `/app/backend/routes/webhooks.py` — Enhanced all handlers for partner activation/deactivation/renewal
- `/app/frontend/src/components/SellOptionsModal.js` — Partner fee lockdown banner
- `/app/frontend/src/pages/CreateListingPage.js` — Partner fee lockdown page
- `/app/frontend/src/pages/CreateMultiItemListing.js` — Partner fee lockdown page
- `/app/frontend/src/pages/admin/PartnerManager.js` — Fee status badges, updated verify handler

**Testing:** iteration_52 — 100% backend (16/16 passed), frontend code verified

### Previous Session Updates

**Session (Mar 16, 2026 — server.py Modular Refactor Phase 1)**
- Extracted 842 lines from server.py into 5 modular route files + shared deps
- routes/ai_chat.py, routes/fees.py, routes/notifications.py, routes/watchlist.py, deps.py

**Session (Mar 16, 2026 — Subscription Pricing Migration)**
- Premium: $180 CAD/year + taxes, VIP Elite: $300 CAD/year + taxes
- All monthly billing references replaced with yearly

**Session (Mar 16, 2026 — Logic & Legal Sync)**
- 14-day payment window, recommendation opt-out toggle, footer address update

**Session (Mar 16, 2026 — 3 New Features)**
- Sign-up Terms & Policy Consent, Admin RBAC Team Management, AI Chatbot (Claude Sonnet 4.5)

## New API Endpoints (Mar 19, 2026)
- `GET /api/partner/payment-status` — Get partner payment status and checkout URL
- `POST /api/partner/create-checkout` — Create new Stripe Checkout Session for partner fee

## User Schema Updates (Mar 19, 2026)
- `platform_fee_paid` (boolean, default: False) — Whether partner has paid annual fee
- `partner_subscription_id` (string, optional) — Stripe subscription ID for partner fee
- `partner_checkout_session_id` (string) — Last Stripe Checkout Session ID
- `partner_checkout_url` (string) — Last Stripe Checkout URL
- `partner_fee_paid_at` (datetime) — When fee was last paid
- `partner_fee_expired_at` (datetime) — When fee expired

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`

## Upcoming Tasks (Prioritized)

### P1 - High Priority
- [ ] Refactor server.py Phase 2: Move partner admin endpoints to routes/admin.py
- [ ] Refactor server.py Phase 3: Extract listings/marketplace logic

### P2 - Medium Priority
- [ ] Cache marketplace filter counts for performance
- [ ] PDF Invoice cloud storage
- [ ] Update outdated test file (test_new_features_iteration_48.py)

### P3 - Low Priority
- [ ] Cookie consent translation (i18n integration)
- [ ] "Email to Friend" feature for vehicle listings
- [ ] Database indexing on `auction_id` in bids collection
- [ ] "Verified Auction Firm" badge on partner listings
