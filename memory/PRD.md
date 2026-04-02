# BidVex Auction Marketplace - PRD

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next
- **Backend**: FastAPI, MongoDB (Motor), Stripe, SendGrid, APScheduler
- **AI Engine**: Gemini 2.5 Flash (google-genai) — configurable via `AI_MODEL_ID` env var
- **Cache**: Upstash Redis (`REDIS_URL`) with in-memory fallback
- **Storage**: Cloudflare R2 via boto3 (`S3_REGION=auto`)
- **Deployment**: Railway (single-service monolith serving API + React SPA)

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Architecture
```
/app
├── backend/
│   ├── main.py                     # ASGI Entrypoint (Railway)
│   ├── server.py                   # FastAPI app, CORS, middleware, router registration (402 lines)
│   ├── lifecycle.py                # Startup/shutdown events
│   ├── deps.py                     # Shared deps + require_admin unified gate
│   ├── requirements.txt            # 80 pinned packages (added redis, hiredis)
│   ├── routes/
│   │   ├── marketplace.py          # Marketplace with Redis-backed caching
│   │   ├── carousel.py             # Carousel with Redis-backed caching
│   │   └── ...
│   └── services/
│       ├── api_cache.py            # REWRITTEN: Redis + in-memory fallback
│       ├── scheduled_jobs.py       # All APScheduler job functions
│       ├── listings_service.py     # Listings CRUD business logic
│       └── ...
├── frontend/
│   ├── build/                      # Compiled React SPA (tracked in Git)
│   └── ...
└── runtime.txt                     # Python 3.11.x
```

## Key Endpoints
- `GET /api/cache-stats` → Redis/memory status + key count
- `GET /api/health` → `{"status":"healthy"}`
- `GET /api/marketplace/items` → Redis-cached marketplace listings
- `GET /api/marketplace/filter-counts` → Redis-cached filter aggregations
- `GET /api/categories` → Redis-cached categories
- `GET /api/admin/risk-monitoring` → Risk Monitoring dashboard

## Completed Work

### Redis/Upstash Cache Integration (April 2, 2026)
- Rewrote `services/api_cache.py`: Redis-backed cache via `REDIS_URL` with automatic in-memory fallback
- Pydantic-safe JSON serialization (model_dump() before storing)
- Namespace-based cache keys: `listings:`, `marketplace:`, `categories:`, `filter_counts:`, `mp_items:`
- TTLs: 5min general, 30s marketplace items, 5min filter counts
- Updated `routes/marketplace.py`, `routes/carousel.py`, `routes/misc.py` to use async `cache_get`/`cache_set`
- Added `GET /api/cache-stats` diagnostic endpoint
- **Testing**: 18/18 backend tests passed (100%)

### Backend Architecture Refactor Phase 4 & 5 (April 2, 2026)
- server.py: 759 → 398 lines (-48%). Scheduler → scheduled_jobs.py, lifecycle → lifecycle.py
- admin.py: 285 duplicate routes removed. 56+ admin routes use `require_admin` dependency
- listings.py: CRUD logic extracted to `services/listings_service.py`

### Previous (April 2, 2026)
- Risk Monitoring Dashboard (frontend + backend), 90% Risk Email Alerts
- Railway migration manifest, S3_REGION=auto, AI_MODEL_ID configurable, CORS from env var

## Railway Environment Variables to Add
```
REDIS_URL=<your-upstash-redis-url>
UPSTASH_REDIS_REST_URL=<your-upstash-rest-url>
UPSTASH_REDIS_REST_TOKEN=<your-upstash-rest-token>
```

## Backlog

### P2 - Medium Priority
- [ ] Cloudflare CDN setup
- [ ] Post-launch monitoring & alerting
- [ ] PDF Invoice Cloud Storage
- [ ] Partner Dashboard page

### P3 - Low Priority
- [ ] Partner Pro subscription tier
- [ ] Cookie consent i18n integration
- [ ] "Email to Friend" for vehicle listings
- [ ] "Verified Auction Firm" badge
- [ ] Database indexing on auction_id in bids collection
