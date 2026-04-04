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

## Official Fee Schedule (Audited April 3, 2026)

### §7.1 User Tiers
| Tier | Annual Fee | Buyer Premium | Seller Commission |
|------|-----------|---------------|-------------------|
| Standard | Free | 5% | 4% |
| Premium | $180 CAD | 3.5% | 2.5% |
| VIP Elite | $300 CAD | 3% | 2% |
- GST/QST applied to subscription checkout as separate line items

### §7.2 Partner Platform Access ($100 CAD/yr)
- BidVex takes ONLY 3% Hammer Commission (general) / 2.5% (vehicle)
- 0% of Buyer Premium retained by BidVex — 100% flows to Partner

### §7.3 Vehicle Platform Fee
- 2.5% mandatory (overrides standard 3%)

### §7.4 Tax Calculation
- GST (TPS 5%) + QST (TVQ 9.975%) on **(Hammer + Buyer Premium)**
- Separate line items on all Stripe checkouts

### §7.5 Payment Terms
- 14-day payment deadline with day-10 reminder
- 2%/month late penalty via `process_overdue_auction_payments` cron (every 6h)
- Metadata flag: `payment_status: "overdue"`

### Email Credit Rates
| Quantity | Rate/Email |
|----------|-----------|
| 1-1,000 | $0.018 |
| 1,001-5,000 | $0.015 |
| 5,001-10,000 | $0.012 |
| 10,001+ | $0.010 |

## Completed Work

### Fee Schedule Audit — April 3, 2026
- **FIX**: Added GST/QST as separate Stripe line items on subscription checkout (subscriptions.py)
- **FIX**: Aligned frontend EmailCreditPurchase.js tiers to backend ($0.016→$0.015, boundaries corrected)
- 34/34 audit tests passed, all rates verified to 0.0% deviation

### Growth & Monetization — April 3, 2026
- Affiliate Cash-Back Engine (15% of BidVex commission via Stripe Transfer Group)
- Listing Promotion Storefront ($9.99/$24.99/$49.99 + tax)
- Email Marketing Credits (Pay-As-You-Go + tax)
- GST/QST on all digital products
- CSS Polish: French letter-spacing -0.02em

### Two-Tier Economy — April 3, 2026
- Partner vs Standard flow (application_fee logic, metadata tagging)
- Tax base: Hammer + Premium

### Stripe Connect Engine — April 3, 2026
- Itemized line items, $1k deposit, vehicle offline hammer

### Mobile Messaging UI Fixes — April 4, 2026
- Added `viewport-fit=cover` meta tag to `public/index.html` for iOS safe-area-inset support
- Hidden `MobileBottomNav` on `/messages` route (App.js MobileNavWrapper)
- Switched container to `100dvh` full viewport, removed `pb-14` padding hack
- Added `z-20` to message input bar for proper layering above scroll area
- Added `onFocus` scroll-to-bottom on message text input for keyboard visibility
- Refined `visualViewport` API handler with `requestAnimationFrame` scroll + `maxHeight` reset

## Backlog
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring/alerting (P2)
- [ ] Real-time performance dashboard
- [ ] Refactor payments.py into modular routers
- [ ] Clean backend lint warnings (webhooks.py, partners.py, subscriptions.py)
