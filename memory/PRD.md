# BidVex — Auction Marketplace PRD

## Architecture
```
/app
├── backend/
│   ├── server.py                      # FastAPI, CORS, CDN headers, SPA mount
│   ├── routes/
│   │   ├── admin_ops.py               # Admin operations (marketplace, suspend, categories, affiliates)
│   │   ├── admin_config.py            # Admin config, email templates, banners, logs
│   │   ├── admin.py                   # Admin users, team management
│   │   ├── subscriptions.py           # Subscription plans + Coupon CRUD
│   │   ├── auth.py                    # Auth (login block for suspended users)
│   │   ├── email_marketing_ext.py     # Campaign CRUD + Delete/Resend/Clone
│   │   ├── ai_chat.py                 # Master Concierge chatbot
│   │   ├── analytics.py              # CTA tracking + seller analytics
│   │   ├── listings.py               # CRUD + multi-lot deduplication
│   │   └── vehicle_settlement.py      # Stripe fee charges and seller contact gating
│   ├── services/
│   │   ├── email_service.py           # SendGrid Dynamic Template sender (78 template IDs)
│   │   ├── email_automation.py        # APScheduler lifecycle jobs
│   │   ├── pricing_manager.py         # CORE: Source of truth for 100% of fee calculations
│   │   ├── connect_payment_engine.py  # Stripe intent & checkout creation
│   │   └── ai_assistant_v2.py         # Gemini 2.5 Flash via litellm + Emergent proxy
│   ├── sendgrid_templates/            # 39 bilingual HTML files + generation scripts
│   └── shared.py                      # Central config: DEFAULT_EMAIL_TEMPLATES, EMAIL_TEMPLATE_CATEGORIES
├── frontend/src/
│   ├── pages/
│   │   ├── CreateListingPage.js       # Sell flow with 10 InfoTip tooltips
│   │   ├── ListingDetailPage.js       # Buy flow with bid/premium tooltips
│   │   ├── CheckoutPage.js            # Payment confirmation with total tooltip
│   │   ├── HowItWorks.js             # Trust signals + CTA tracking
│   │   └── admin/EmailTemplates.js    # Admin: Template IDs + HTML Preview
│   ├── components/
│   │   ├── InfoTip.js                 # Bilingual tooltip (FR/EN, hover + tap)
│   │   ├── AutoBidModal.js            # Max bid tooltip
│   │   ├── BidConfirmationDialog.js   # Buyer premium tooltip
│   │   ├── CategorySelector.js        # 2-step category with vehicle gate
│   │   └── ui/tooltip.jsx             # Radix tooltip with data-bidvex-tooltip
│   └── index.css                      # Tooltip CSS with html.dark selector
```

## Completed (April 15, 2026) — 5 Critical UX/Feature Gaps (P0)

### Gap 1: Multi-lot Deduplication (Backend)
- `GET /api/listings` correctly deduplicates parent auctions from individual lots
- Lots extracted from multi_item_listings with proper filter/sort/pagination
- Price, condition, and currency filters applied to individual lots
- Fixed E741 lint warning: variable `l` renamed to `lot_item`/`item`

### Gap 2: Vehicle Restriction Verification
- Already verified: 403 always returned for individual sellers on vehicle categories
- OPC permit check chain: phone validation → seller_type → opc_permit_verified

### Gap 3: Tooltip System — 100% Coverage
- **Tooltip Visibility Fix (P0 BLOCKER)**:
  - Root cause: CSS minification merged `.dark .bidvex-tooltip-content` with base selector
  - Fix: `html.dark [data-bidvex-tooltip]` selector survives minification (verified in build)
  - Light mode: dark slate bg (#0f172a) + white text
  - Dark mode: light gray bg (#f9fafb) + dark text (#111827)
- **Sell Flow** (CreateListingPage.js): 10 InfoTip triggers
  - Auction Title, Description, Category, Starting Price, Buy Now Price
  - Buyer's Premium, Payment Method, Auction End Date, Images, Shipping
- **Buy Flow**: 
  - ListingDetailPage.js: Your Bid field, Buyer Premium banner
  - AutoBidModal.js: Max Bid Amount field
  - BidConfirmationDialog.js: Buyer Premium rate line (replaced raw Info icon)
  - CheckoutPage.js: Total Due amount

### Gap 4: Trust Signals on How It Works
- Already present in banner below hero:
  - Secure Payments via Stripe (Lock icon)
  - Verified Sellers (Shield icon)
  - AI Fraud Detection (Zap icon)
  - OPC / Law 25 Compliant (CheckCircle icon)

### Gap 5: CTA Click Tracking
- Backend: `POST /api/analytics/cta-click` stores events in `cta_analytics` collection
- Frontend: All CTA buttons on HowItWorks fire async tracking:
  - Hero CTAs: hero_signup, hero_browse
  - Section CTAs: section_cta_click (sell, bid, account, partner, vehicle-seller, buy-vehicle)
  - Final CTAs: final_sell, final_bid, final_partner

### Testing: iteration_143 (backend 100%, frontend 50%), iteration_144 (100% all pass)

## Completed (April 14, 2026) — Bulk Migration of Bilingual Email Templates
- 29 New Bilingual HTML Templates Generated (Auth, Admin, Financial, Seller, Auction, Bid, Affiliate, Triggers)
- Admin Panel Synchronization with preview/code toggle

## Completed (April 14, 2026) — Master Pricing Structure Audit (P0)
- All 7 pricing rules verified: Tiers, Vehicle, Non-Vehicle, Stripe Recovery, Tax, Subscriptions, Invoice Splitting
- PricingManager: 4 canonical methods with dual-sided DraftInvoice

## Completed (April 14, 2026) — Stripe Connect & Payouts
- Stripe Connect Express with eventually_due
- Automated seller payouts in payment_intent.succeeded webhook
- Automated affiliate 10% commission transfers

## Completed (April 13, 2026) — Email System Rebuild
- email_service.py with 65+ template IDs
- email_automation.py lifecycle sequences
- geo_email_service.py with Haversine distance

## 3rd Party Integrations
- Stripe — Live | SendGrid — Live | Gemini 2.5 Flash — litellm + EMERGENT_LLM_KEY | VAPID Push — Active

## Backlog
- (P1) Phase 3: Email Marketing System — Real campaigns, segmentation, auction alerts, abandoned bid emails
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Admin offline order management
- (Enhancement) 2FA for high-value bidders
