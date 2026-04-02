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

## Key Endpoints
- `POST /api/auth/login` - Brute force protected (5 fails = 24h block)
- `GET /api/admin/tax-report?period=Q2-2026&province=QC&format=csv` - CRA/RQ tax export
- `POST /api/invoices/generate/{transaction_id}?lang=en&buyer_province=QC` - Bilingual PDF invoice
- `GET /api/partner/stats` - Partner metrics (per-partner + platform-wide)
- `GET /api/partner/badge/{user_id}` - Public badge endpoint
- `GET /api/legal/cookie-policy?lang=fr` - i18n cookie consent (Law 25)

## Completed Work

### Partner & Trust Features (April 2, 2026)
- **PartnerBadge.js**: Reusable component fetching from `/api/partner/badge/{sellerId}`
  - Gold shield for VIP Verified, Blue shield for Verified Firm, Green for Approved Partner
  - Hover tooltip: "BidVex Verified: This firm has met our professional standards..."
  - Integrated into ListingDetailPage and VehicleAuctionsPage
- **Partner Dashboard Enhancement**: SaaS-style 3-card stats grid at top
  - Active Listings (blue), Bids Received (green), Projected Revenue (amber)
  - Fetches from `/api/partner/stats` (returns `my_active_listings`, `my_total_bids_received`, `my_projected_revenue`)
- **MaintenanceGuard**: Updated to allow `/partner/*` routes through
- Testing: 14/14 passed (8 backend, 5 frontend, 1 expected behavior)

### Law 25 Cookie Consent Banner (April 2, 2026)
- CookieConsentBanner.js + useCookieConsent hook
- Privacy by Default, Accept All / Refuse All / Customize
- Footer "Cookie Settings" link for right-to-withdraw
- 11/11 tests passed

### Tax Report Export (April 2, 2026)
- Admin-only CSV/JSON export with period+province filters
- 22/22 tests passed

### Commercial Readiness Phase v2 (April 2, 2026)
- Multi-Province Tax Engine (NS 14% 2026 rate), Bilingual PDF Invoice with vehicle info
- Partner Service, Cookie Consent API (Law 25)
- 36/36 tests passed

## Backlog
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring (P2)
- [ ] Consent analytics endpoint
