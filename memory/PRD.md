# BidVex Auction Marketplace - PRD

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next
- **Backend**: FastAPI, MongoDB (Motor), Stripe, SendGrid, APScheduler
- **AI Engine**: Gemini 2.5 Flash (google-genai)
- **Cache**: Upstash Redis (`REDIS_URL`) with in-memory fallback
- **Storage**: Cloudflare R2 via boto3 (`S3_REGION=auto`)
- **Deployment**: Railway (single-service monolith serving API + React SPA)

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Architecture
```
/app
├── backend/
│   ├── server.py                   # FastAPI app, middleware, router registration
│   ├── lifecycle.py                # Startup/shutdown events
│   ├── deps.py                     # Shared deps + require_admin
│   ├── routes/
│   │   ├── auth.py                 # Login with brute force protection
│   │   ├── trust_safety.py         # Risk Monitoring + blocked IPs admin
│   │   ├── marketplace.py          # Redis-cached marketplace
│   │   ├── invoices.py             # Invoice generation (bilingual PDF + R2)
│   │   ├── partners.py             # Partner system + stats + badge
│   │   ├── partner_pro.py          # Partner Pro features (CSV, storefront)
│   │   ├── legal.py                # Legal pages + Cookie Consent i18n
│   │   └── ...
│   └── services/
│       ├── brute_force.py          # IP brute force protection (Redis-backed)
│       ├── api_cache.py            # Redis + in-memory fallback cache
│       ├── scheduled_jobs.py       # APScheduler jobs
│       ├── listings_service.py     # Listings CRUD logic
│       ├── invoice_service.py      # Multi-province tax engine + PDF gen
│       ├── partner_service.py      # Partner verification + badge logic
│       ├── cloud_storage.py        # R2 S3 uploads (invoices + images)
│       └── ...
├── frontend/
│   ├── build/                      # Compiled React SPA
│   └── ...
└── runtime.txt
```

## Key Endpoints
- `POST /api/auth/login` → Brute force protected (5 fails → 24h block)
- `GET /api/admin/blocked-ips` → List blocked IPs
- `POST /api/admin/blocked-ips/{ip}/unblock` → Unblock IP
- `GET /api/cache-stats` → Redis/memory status
- `GET /api/admin/risk-monitoring` → Risk Monitoring
- `POST /api/invoices/generate/{transaction_id}` → Bilingual PDF invoice with province tax
- `GET /api/partner/stats` → Aggregated partner metrics (admin/partner)
- `GET /api/partner/badge/{user_id}` → Public badge endpoint
- `GET /api/legal/cookie-policy` → i18n cookie consent (Law 25)

## Completed Work

### Commercial Readiness Phase (April 2, 2026)
- **Multi-Province Tax Engine** in `services/invoice_service.py`:
  - HST provinces (ON 13%, NB/NS/NL/PE 15%)
  - Dual-tax (QC: 5% GST + 9.975% QST on subtotal; BC: 5%+7%; MB: 5%+7%; SK: 5%+6%)
  - GST-only (AB, YT, NT, NU: 5%)
  - QST correctly calculated on subtotal only (not GST-inclusive)
- **Bilingual PDF Invoice Service**: generates EN/FR PDFs, uploads to R2
- **PaymentTransaction** model updated with `invoice_url`, `tax_gst`, `tax_pst_qst`, `tax_hst`, `buyer_province`
- **Partner Service** (`services/partner_service.py`): `is_verified_firm`, `get_badge_type`, `get_partner_stats`
- **Cookie Consent API** (Law 25): `GET /api/legal/cookie-policy` with Accept-Language + ?lang= support
- Testing: 23/23 tests passed (100%)

### Brute Force Protection (April 2, 2026)
- `services/brute_force.py`: Redis-backed IP tracking. 5 failed logins → 24h block
- 12/12 core tests passed (100%)

### Redis Cache Integration (April 2, 2026)
- Rewrote api_cache.py for Redis with in-memory fallback
- 18/18 tests passed

### Backend Architecture Refactor (April 2, 2026)
- server.py 759→398 lines, admin dedup, listings service extraction
- 20/21 tests passed

### Risk Monitoring + Email Alerts (April 2, 2026)
- Dashboard (frontend+backend), 90% risk email alerts via SendGrid

## Backlog
- [ ] Frontend: Partner Pro stats dashboard integration
- [ ] Frontend: Cookie Consent banner (using /api/legal/cookie-policy)
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring (P2)
- [ ] Real-time performance dashboard (Enhancement)
- [ ] Automated Lighthouse audits (Enhancement)
- [ ] Server-side PageSpeed monitoring endpoint (Enhancement)
