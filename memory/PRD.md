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

### French Bid Button Overflow Fix — April 3, 2026
- **Layout**: Lot card bid input + button now stack vertically (`flex-col`) on all viewports to prevent "Placer une enchère" overflow
- **Responsive Text**: Mobile shows compact "Enchérir" (`sm:hidden`), desktop shows full "Placer une enchère" (`hidden sm:inline`)
- **Button Styling**: Full-width (`w-full`), `text-sm` font, consistent padding
- **i18n**: Added `bid.placeBidCompact`, `bid.buyNow`, `bid.biddingEnded`, `bid.buyNowSkip`, `bid.buyNowAvailable` to en.json/fr.json
- **Buy Now**: Localized with i18n (EN: "Buy Now", FR: "Acheter"); proper flex stacking on mobile
- **Testing**: iteration_102 — 100% backend + 100% frontend

### Multi-Currency Support (CAD/USD) — April 3, 2026
- **Schema**: `Listing` model has `currency: str = "CAD"` with auto-detection from location
- **Seller Flow**: Currency Toggle (🇨🇦 CAD / 🇺🇸 USD) with warning tooltip on Create Listing
- **Bilingual Display**: `formatListingPrice()` → EN: `$5,000.00 CAD` / FR: `5 000,00 $ CAD`
- **Updated**: ListingDetailPage, VehicleDetailPage, VehicleAuctionsPage, WatchlistPage, LotsMarketplacePage, HomePage, useRealtimeBidding
- **Stripe**: All 4 checkout flows use dynamic `listing.get("currency","CAD").lower()`
- **Testing**: iteration_101 — 100% frontend

### App-Style Mobile Stack & Premium Messaging — April 3, 2026
- Mobile Stack, Read Receipts, Typing Indicators with Law 25 gating
- Testing: iteration_100 — 14/14 passed

### Previous Sessions
- Messaging UI Refactoring, Partner & Trust Features, Law 25 Cookie Consent, Tax Report Export, Commercial Readiness (tax engine, PDF invoices), Architecture Refactor

## Backlog
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring and alerting (P2)
- [ ] Real-time performance dashboard (Enhancement)
- [ ] Automated Lighthouse audits weekly (Enhancement)
- [ ] Refactor MessagesPage.js (~1000 lines) into smaller components (Tech debt)
