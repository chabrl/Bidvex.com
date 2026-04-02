# BidVex Auction Marketplace - PRD

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next
- **Backend**: FastAPI, MongoDB (Motor), Stripe, SendGrid, APScheduler
- **AI Engine**: Gemini 2.5 Flash (google-genai)
- **Cache**: Upstash Redis (`REDIS_URL`) with in-memory fallback
- **Storage**: Cloudflare R2 via boto3 (`S3_REGION=auto`, ACL=private default)
- **Deployment**: Railway (single-service monolith serving API + React SPA)

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Architecture
```
/app/backend/
├── server.py                   # FastAPI app, middleware, router registration
├── lifecycle.py                # Startup/shutdown events
├── deps.py                     # Shared deps + require_admin
├── routes/
│   ├── auth.py                 # Login with brute force protection
│   ├── trust_safety.py         # Risk Monitoring + blocked IPs admin
│   ├── marketplace.py          # Redis-cached marketplace
│   ├── invoices.py             # Invoice generation (bilingual PDF + R2)
│   ├── partners.py             # Partner system + stats + badge
│   ├── partner_pro.py          # Partner Pro features (CSV, storefront)
│   ├── legal.py                # Legal pages + Cookie Consent i18n (Law 25)
│   └── ...
└── services/
    ├── brute_force.py          # IP brute force protection (Redis-backed)
    ├── api_cache.py            # Redis + in-memory fallback cache
    ├── listings_service.py     # Listings CRUD logic
    ├── invoice_service.py      # Multi-province tax engine + PDF gen
    ├── partner_service.py      # Partner verification + badge logic
    ├── cloud_storage.py        # R2 S3 uploads (invoices + images, private ACL)
    └── ...
```

## Key Endpoints
- `POST /api/auth/login` - Brute force protected (5 fails = 24h block)
- `GET /api/admin/blocked-ips` - List blocked IPs
- `GET /api/admin/risk-monitoring` - Risk Monitoring
- `POST /api/invoices/generate/{transaction_id}` - Bilingual PDF invoice with province tax + vehicle info
- `GET /api/partner/stats` - Partner metrics (admin/partner)
- `GET /api/partner/badge/{user_id}` - Public badge endpoint
- `GET /api/legal/cookie-policy` - i18n cookie consent (Law 25, Privacy by Default)

## Completed Work

### Commercial Readiness Phase — v2 (April 2, 2026)
- **Multi-Province Tax Engine** (CRA/Revenu Quebec compliant):
  - HST: ON 13%, NS 14% (2026 rate), NB/NL/PE 15%
  - Dual-tax: QC 5% GST + 9.975% QST (on subtotal only), BC/MB 5%+7%, SK 5%+6%
  - GST-only: AB/YT/NT/NU 5%
  - DB stores `tax_gst`, `tax_pst_qst`, `tax_hst`, `buyer_province` per transaction
- **Bilingual PDF Invoice Service**:
  - Buyer/seller addresses + tax ID placeholders
  - Vehicle Information section (VIN, Make, Model, Year) when listing has vehicle data
  - Province-aware tax line items
  - R2 upload to private subfolder (`bidvex/invoices/transactions/`)
- **Partner & Verification Service**: `is_verified_firm()`, `get_badge_type()`, `get_partner_stats()`
- **Cookie Consent API (Law 25)**:
  - Categories: strictly_necessary (required), functionality, analytics, marketing
  - Explicit `refuse_all`/"Tout refuser" + `privacy_by_default` messaging
  - Accept-Language header + ?lang= param support
- **R2 Storage**: `_put_object()` defaults to ACL=private
- Testing: 36/36 tests passed (100%)

### Previous Phases (Completed)
- Brute Force Protection (Redis, 5 fails = 24h block) — 12/12 tests
- Redis Cache Integration (Upstash + in-memory fallback) — 18/18 tests
- Backend Architecture Refactor (server.py 759→398 lines) — 20/21 tests
- Risk Monitoring Dashboard + 90% Risk Email Alerts (SendGrid)
- Railway Migration Manifest

## Backlog
- [ ] Frontend: Partner Pro stats dashboard integration
- [ ] Frontend: Cookie Consent banner (using /api/legal/cookie-policy)
- [ ] Frontend: Verified firm badges (using /api/partner/badge/{user_id})
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring (P2)
- [ ] Tax Report Export endpoint (aggregate tax_gst/pst_qst/hst by province for CRA/RQ quarterly filings)
