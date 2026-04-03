# BidVex Auction Marketplace - PRD

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next
- **Backend**: FastAPI, MongoDB (Motor), Stripe Connect, SendGrid, APScheduler
- **AI Engine**: Gemini 2.5 Flash (google-genai)
- **Cache**: Upstash Redis with in-memory fallback
- **Storage**: Cloudflare R2 via boto3 (ACL=private default)
- **Deployment**: Railway (single-service monolith serving API + React SPA)

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Completed Work

### Stripe Connect Financial Engine — April 3, 2026
- **Tier-Based Fees**: Standard (5% buyer/4% seller), Premium (3.5%/2.5%), VIP Elite (3%/2%)
- **Platform Fee**: 3% general, 2.5% vehicle — deducted via Stripe Connect `application_fee_amount`
- **Tax Compliance (Quebec)**: GST (TPS 5%) and QST (TVQ 9.975%) as **separate Stripe checkout line items** with tax registration numbers
- **Stripe Fee Pass-Through**: Buyer covers 2.9% + $0.30 processing fee
- **Vehicle Auctions**: Hammer paid offline (bank draft); only BidVex fees (premium + platform fee + tax) charged via Stripe
- **General Auctions**: Full amount (hammer + premium + tax + processing) charged via Stripe Connect with seller transfer
- **Itemized Line Items**: `build_itemized_line_items()` generates separate rows for GST/QST visibility
- **Auction Winner Checkout**: Updated to use Connect engine (`create_connect_checkout_session`)
- **$1,000 Security Deposit**: Pre-auth hold required for bidding on >$10k auctions
  - Backend: `deposits.py` route + check in `place_bid` (auctions.py)
  - Frontend: `SecurityDepositBanner` component on ListingDetailPage & VehicleDetailPage
  - Bid input/button disabled until deposit authorized
- **Files**: `connect_payment_engine.py`, `pricing_config.py`, `deposits.py`, `SecurityDepositBanner.js`
- **Testing**: iteration_103 — 16/16 backend, 100% frontend

### French Bid Button Overflow Fix — April 3, 2026
- Layout stacking fix for French "Placer une enchère" overflow
- Testing: iteration_102 — 100%

### Multi-Currency Support (CAD/USD) — April 3, 2026
- Schema, Seller Flow, Bilingual Display, Stripe integration
- Testing: iteration_101 — 100%

### App-Style Mobile Stack & Premium Messaging — April 3, 2026
- Mobile Stack, Read Receipts, Typing Indicators with Law 25 gating
- Testing: iteration_100 — 14/14 passed

### Previous Sessions
- Messaging UI Refactoring, Partner & Trust Features, Law 25 Cookie Consent, Tax Report Export, Commercial Readiness (tax engine, PDF invoices), Architecture Refactor

## In Progress
- [ ] Affiliate Cash-Back Payouts (Stripe Transfer Group logic)
- [ ] Pay-As-You-Go Frontend UIs (Listing Promotions $9.99/$24.99/$49.99, Email Marketing credits)

## Backlog
- [ ] Link QST/HST/GST tax engine into Stripe `line_items` for non-auction checkouts (P1)
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring and alerting (P2)
- [ ] Real-time performance dashboard (Enhancement)
- [ ] Automated Lighthouse audits weekly (Enhancement)
- [ ] Refactor `payments.py` (~2300 lines) into modular routers (Tech debt)
- [ ] Refactor MessagesPage.js (~1000 lines) into smaller components (Tech debt)
