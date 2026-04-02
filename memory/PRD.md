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

## Architecture
```
/app/backend/
├── server.py                   # FastAPI app, middleware, router registration
├── lifecycle.py                # Startup/shutdown events
├── deps.py                     # Shared deps + auth helpers
├── shared.py                   # Pydantic models (PaymentTransaction, User, etc)
├── routes/
│   ├── auth.py                 # Login with brute force protection
│   ├── admin.py                # Admin: users, tax report, system config
│   ├── trust_safety.py         # Risk Monitoring + blocked IPs
│   ├── marketplace.py          # Redis-cached marketplace
│   ├── invoices.py             # Invoice generation (bilingual PDF + R2)
│   ├── partners.py             # Partner system + stats + badge
│   ├── partner_pro.py          # Partner Pro features
│   ├── legal.py                # Legal pages + Cookie Consent i18n (Law 25)
│   └── ...
└── services/
    ├── brute_force.py          # IP brute force protection (Redis)
    ├── api_cache.py            # Redis + in-memory fallback cache
    ├── listings_service.py     # Listings CRUD logic
    ├── invoice_service.py      # Multi-province tax engine + PDF gen
    ├── partner_service.py      # Partner verification + badge logic
    ├── cloud_storage.py        # R2 uploads (invoices + images, private ACL)
    └── ...
```

## Completed Work

### Tax Report Export (April 2, 2026)
- `GET /api/admin/tax-report` — admin-only, period+province filters, JSON+CSV export
- CSV: Transaction ID, Date, Province, Subtotal, Buyer Premium, GST, PST/QST, HST, Total, Invoice URL + TOTALS row
- 22/22 tests passed (100%)

### Commercial Readiness Phase v2 (April 2, 2026)
- Multi-Province Tax Engine: NS 14% (2026), ON 13%, NB/NL/PE 15%, QC GST+QST, BC/MB/SK GST+PST, AB/YT/NT/NU GST
- Bilingual PDF Invoice with buyer/seller addresses, tax IDs, Vehicle Information section
- Partner Service: is_verified_firm, badge logic, aggregated stats
- Cookie Consent API (Law 25): strictly_necessary/functionality/analytics/marketing + refuse_all/Tout refuser
- 36/36 tests passed (100%)

### Previous Phases
- Brute Force Protection (Redis, 5 fails = 24h block) — 12/12 tests
- Redis Cache Integration (Upstash + in-memory fallback) — 18/18 tests
- Backend Architecture Refactor (server.py 759→398 lines) — 20/21 tests
- Risk Monitoring Dashboard + 90% Risk Email Alerts (SendGrid)

## Backlog
- [ ] Frontend: Cookie Consent banner component
- [ ] Frontend: Partner Pro stats dashboard
- [ ] Frontend: Verified firm badges
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring (P2)
