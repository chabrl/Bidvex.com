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
- Buyer pays: Hammer + Premium + Taxes
- Stripe metadata tagged: `PARTNER_FLOW`

### Standard Flow (is_partner=False)
- BidVex takes BOTH Buyer Premium AND Seller Commission
- Seller receives: Hammer - Seller Commission
- Stripe processing fee passed to buyer
- Buyer pays: Hammer + Premium + Taxes + Processing Fee
- Stripe metadata tagged: `STANDARD_FLOW`

### Tax Calculation (Both Flows)
- GST (TPS 5%) + QST (TVQ 9.975%) on **Total Taxable Amount (Hammer + Premium)**
- Tax registration numbers from env vars PLATFORM_GST_NUMBER / PLATFORM_QST_NUMBER
- GST and QST shown as **separate Stripe checkout line items** for Quebec compliance

### Tier-Based Fees
- Standard: 5% Buyer / 4% Seller
- Premium ($180/yr): 3.5% Buyer / 2.5% Seller
- VIP Elite ($300/yr): 3% Buyer / 2% Seller
- Platform Fee: 3% General / 2.5% Vehicle

## Completed Work

### Two-Tier Marketplace Economy — April 3, 2026
- `calculate_connect_checkout()` now accepts `seller_is_partner` flag
- Partner Flow: application_fee = seller_commission only; $0 Stripe fee to buyer; partner_premium_retained tracked
- Standard Flow: application_fee = buyer_premium + seller_commission + taxes; Stripe fee to buyer
- Tax base changed from (premium + platform_fee) to (Hammer + Premium) for Quebec compliance
- All Stripe metadata tagged PARTNER_FLOW or STANDARD_FLOW
- Partner Dashboard: "Partner Benefit" card showing retained premiums this month
- CheckoutPage: Dynamic flow_type badge, conditional Processing Fee visibility
- Testing: iteration_104 — 16/16 backend, 100% frontend

### Stripe Connect Financial Engine — April 3, 2026
- Tier-Based Fees, Platform Fee, Itemized Line Items (GST/QST separate)
- $1,000 Security Deposit for >$10k auctions with frontend UX
- Vehicle auctions: hammer offline, only fees via Stripe
- Testing: iteration_103 — 16/16 backend, 100% frontend

### Previous Sessions
- Multi-Currency (CAD/USD), French UI fixes, Mobile Messaging, Partner Features
- Law 25 Cookie Consent, Tax Reports, Commercial Readiness, Architecture Refactor

## In Progress
- [ ] Affiliate Cash-Back Payouts (Stripe Transfer Group)
- [ ] Pay-As-You-Go Frontend UIs (Listing Promotions, Email Marketing credits)

## Backlog
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring/alerting (P2)
- [ ] Real-time performance dashboard (Enhancement)
- [ ] Refactor payments.py (~2300 lines) into modular routers (Tech debt)
- [ ] French 'Placer une enchère' button CSS regression monitor
