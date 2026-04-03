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

## Two-Tier Marketplace Economy

### Partner Flow (is_partner=True, $100/yr)
- BidVex takes ONLY Seller Commission (2.5% vehicles / 3.0% general) from Hammer
- 100% of Buyer Premium transferred to Partner's Connect account
- Stripe fees deducted from Partner's payout (NOT charged to buyer)
- Stripe metadata: `PARTNER_FLOW`

### Standard Flow (is_partner=False)
- BidVex takes BOTH Buyer Premium AND Seller Commission
- Seller receives: Hammer - Seller Commission
- Stripe processing fee passed to buyer
- Stripe metadata: `STANDARD_FLOW`

### Tax Calculation (Both Flows)
- GST (TPS 5%) + QST (TVQ 9.975%) on **Total Taxable Amount (Hammer + Premium)**
- Separate Stripe checkout line items for Quebec compliance

### Tier-Based Fees
- Standard: 5% Buyer / 4% Seller
- Premium ($180/yr): 3.5% Buyer / 2.5% Seller
- VIP Elite ($300/yr): 3% Buyer / 2% Seller
- Platform Fee: 3% General / 2.5% Vehicle

## Completed Work

### Growth & Monetization Phase — April 3, 2026
- **Affiliate Cash-Back Engine**: 15% of BidVex commission auto-paid to affiliates via Stripe Transfer Group
  - Standard flow: 15% of (buyer_premium + seller_commission)
  - Partner flow: 15% of seller_commission only
  - transfer_group + affiliate_id in checkout metadata
  - Webhook triggers `process_affiliate_payout()` on successful sale
- **Listing Promotion Storefront**: 3-tier system (Basic $9.99/7d, Standard $24.99/14d, Premium $49.99/30d)
  - `ListingPromotionModal.js` with GST/QST breakdown on each tier
  - Integrated into ListingDetailPage "Promote" button
- **Email Marketing Credits**: Pay-As-You-Go sliding scale ($0.018→$0.010/email)
  - `EmailCreditPurchase.js` with slider, live pricing, and tax breakdown
  - Integrated into PartnerDashboard for active partners
- **GST/QST on Digital Products**: All promotions and email credits now include separate GST/QST line items
- **CSS Polish**: French `letter-spacing: -0.02em` on bid buttons across all 3 detail pages
- Testing: iteration_105 — 23/23 backend, 100% frontend

### Two-Tier Marketplace Economy — April 3, 2026
- Partner vs Standard flow with different application_fee logic
- Tax base changed to (Hammer + Premium) for Quebec compliance
- Partner Dashboard "Partner Benefit" card
- Testing: iteration_104 — 16/16 backend, 100% frontend

### Stripe Connect Financial Engine — April 3, 2026
- Tier-Based Fees, itemized GST/QST line items, $1k security deposit, vehicle offline hammer
- Testing: iteration_103 — 16/16 backend, 100% frontend

### Previous Sessions
- Multi-Currency (CAD/USD), French UI fixes, Mobile Messaging, Partner Features
- Law 25 Cookie Consent, Tax Reports, Commercial Readiness, Architecture Refactor

## In Progress
None

## Backlog
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring/alerting (P2)
- [ ] Real-time performance dashboard (Enhancement)
- [ ] Refactor payments.py (~2300 lines) into modular routers (Tech debt)
- [ ] Automated Lighthouse audits weekly (Enhancement)
