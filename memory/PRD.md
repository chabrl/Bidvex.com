# BidVex Auction Marketplace - PRD

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next
- **Backend**: FastAPI, MongoDB (Motor), Stripe, SendGrid, APScheduler
- **AI Engine**: Gemini 2.5 Flash (google-genai)
- **Cache**: Upstash Redis with in-memory fallback
- **Storage**: Cloudflare R2 via boto3 (ACL=private default)
- **Deployment**: Railway (single-service monolith serving API + React SPA)

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Completed Work

### Multi-Currency Support (CAD/USD) — April 3, 2026
- **Schema**: `Listing` model now includes `currency: str = "CAD"` field; `ListingCreate` accepts optional `currency`
- **Auto-Detection**: Uses `detect_currency_from_location()` — country=CA → CAD, country=US → USD
- **Seller Flow**: Currency Toggle (CAD/USD with flag icons) on `CreateListingPage.js`; warning tooltip about immutability; price labels show dynamic currency code
- **Bilingual Display**: New `formatListingPrice(amount, currency)` in `currencyFormatter.js`: EN → `$5,000.00 CAD` / FR → `5 000,00 $ CAD`
- **Updated Components**: ListingDetailPage, VehicleDetailPage, VehicleAuctionsPage, WatchlistPage, LotsMarketplacePage, HomePage, useRealtimeBidding
- **Bidding**: Bid input shows currency badge ("Bid in USD"); backend includes currency in bid response and WebSocket broadcasts
- **Stripe**: All 4 checkout flows (listing purchase, buy-now, auction-winner, transaction record) use `listing.get("currency", "CAD").lower()` instead of hardcoded `"cad"`
- **i18n**: Added `currency` section to en.json/fr.json (selector, warningTitle, warningBody, bidIn, listedIn)
- **Testing**: iteration_101 — 12/16 backend (4 auth-env related), 100% frontend

### App-Style Mobile Stack & Premium Real-Time Messaging — April 3, 2026
- Mobile Stack: MobileBottomNav visible on `/messages`; chat input stacks above with frosted glass backdrop-blur
- Read Receipts: Vibrant BidVex blue (#38BDF8) double checkmarks; bilingual "Seen at" / "Vu à"
- Typing Indicators: Bilingual dots animation gated by Law 25 functionality consent
- Testing: 14/14 passed (iteration_100)

### Previous Sessions
- Messaging UI Refactoring (Partner Quick Actions, Inspection Scheduler) — 28/28 tests
- Partner & Trust Features (badges, dashboard) — 14/14 tests
- Law 25 Cookie Consent Banner — 11/11 tests
- Tax Report Export — 22/22 tests
- Commercial Readiness (tax engine, PDF invoices) — 36/36 tests
- Brute Force, Redis Cache, Architecture Refactor, Risk Monitoring

## Backlog
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring and alerting (P2)
- [ ] Real-time performance dashboard (Enhancement)
- [ ] Automated Lighthouse audits weekly (Enhancement)
- [ ] Server-side PageSpeed monitoring endpoint (Enhancement)
- [ ] Refactor MessagesPage.js (~1000 lines) into smaller components (Tech debt)
