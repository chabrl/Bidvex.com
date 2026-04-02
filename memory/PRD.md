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
│   ├── server.py                   # FastAPI app (402 lines)
│   ├── lifecycle.py                # Startup/shutdown events
│   ├── deps.py                     # Shared deps + require_admin
│   ├── routes/
│   │   ├── auth.py                 # Login with brute force protection
│   │   ├── trust_safety.py         # Risk Monitoring + blocked IPs admin
│   │   ├── marketplace.py          # Redis-cached marketplace
│   │   └── ...
│   └── services/
│       ├── brute_force.py          # NEW: IP brute force protection (Redis-backed)
│       ├── api_cache.py            # Redis + in-memory fallback cache
│       ├── scheduled_jobs.py       # APScheduler jobs
│       ├── listings_service.py     # Listings CRUD logic
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

## Completed Work

### Brute Force Protection (April 2, 2026)
- `services/brute_force.py`: Redis-backed IP tracking. 5 failed logins → 24h block
- Login route hooks: check_blocked before auth, record_failure on fail, reset_failures on success
- Progressive warnings at attempts 4-5 ("2 attempts remaining", "1 attempt remaining")
- Admin endpoints: GET /api/admin/blocked-ips, POST /api/admin/blocked-ips/{ip}/unblock
- Testing: 12/12 core tests passed (100%)

### Redis Cache Integration (April 2, 2026)
- Rewrote api_cache.py for Redis with in-memory fallback
- 18/18 tests passed

### Backend Architecture Refactor (April 2, 2026)
- server.py 759→398 lines, admin dedup, listings service extraction
- 20/21 tests passed

### Risk Monitoring + Email Alerts (April 2, 2026)
- Dashboard (frontend+backend), 90% risk email alerts via SendGrid

## Backlog
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring (P2)
- [ ] PDF Invoice Cloud Storage (P2)
- [ ] Partner Dashboard (P2)
- [ ] Partner Pro tier (P3)
- [ ] Cookie consent i18n (P3)
- [ ] "Verified Auction Firm" badge (P3)
