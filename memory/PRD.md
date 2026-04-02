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
- `GET /api/admin/blocked-ips` - List blocked IPs
- `GET /api/admin/risk-monitoring` - Risk Monitoring
- `GET /api/admin/tax-report?period=Q2-2026&province=QC&format=csv` - CRA/RQ tax export
- `POST /api/invoices/generate/{transaction_id}?lang=en&buyer_province=QC` - Bilingual PDF invoice
- `GET /api/partner/stats` - Partner metrics (admin/partner)
- `GET /api/partner/badge/{user_id}` - Public badge endpoint
- `GET /api/legal/cookie-policy?lang=fr` - i18n cookie consent (Law 25)

## Completed Work

### Law 25 Cookie Consent Banner (April 2, 2026)
- `CookieConsentBanner.js`: Fetches `/api/legal/cookie-policy`, renders server-driven bilingual strings
- `useCookieConsent.js` hook: localStorage persistence, `isAllowed()` to gate GA/FB scripts
- Privacy by Default: all non-essential categories OFF by default
- 3 buttons: Accept All, Refuse All (Tout refuser), Customize (with per-category toggles)
- Footer "Cookie Settings" link resets consent and re-shows banner (no reload needed)
- 11/11 tests passed (100%)

### Tax Report Export (April 2, 2026)
- `GET /api/admin/tax-report` — admin-only, period+province filters, JSON+CSV
- 22/22 tests passed (100%)

### Commercial Readiness Phase v2 (April 2, 2026)
- Multi-Province Tax Engine: NS 14% (2026), ON 13%, NB/NL/PE 15%, QC GST+QST, etc.
- Bilingual PDF Invoice with vehicle info, addresses, tax IDs
- Partner Service: is_verified_firm, badge logic, stats
- Cookie Consent API (Law 25): strictly_necessary/functionality/analytics/marketing
- 36/36 tests passed (100%)

### Previous Phases
- Brute Force Protection (Redis, 5 fails = 24h block)
- Redis Cache Integration (Upstash + in-memory fallback)
- Backend Architecture Refactor
- Risk Monitoring Dashboard + 90% Risk Email Alerts

## Backlog
- [ ] Frontend: Partner Pro stats dashboard
- [ ] Frontend: Verified firm badges
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring (P2)
