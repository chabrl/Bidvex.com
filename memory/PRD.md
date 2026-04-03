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

### Messaging UI Refactor (April 3, 2026)
- Fixed-bottom input bar (position: fixed, bottom: 0) with pill-shaped field
- Footer + MobileBottomNav hidden on /messages route
- pb-24 padding on message area to prevent content hiding behind fixed input
- visualViewport API for mobile keyboard handling (iOS safe-area-inset)
- MaintenanceGuard allows /messages through
- 16/16 tests passed (desktop + mobile)

### Partner & Trust Features (April 2, 2026)
- PartnerBadge component: gold/blue/green shields with tooltip
- Partner Dashboard: SaaS-style stats grid (Active Listings, Bids, Revenue)
- 14/14 tests passed

### Law 25 Cookie Consent, Tax Report, Commercial Readiness (April 2, 2026)
- Cookie consent banner, multi-province tax engine, bilingual PDF invoices
- Tax report export (CSV/JSON), partner verification service
- 58/58 cumulative tests passed

## Backlog
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring (P2)
