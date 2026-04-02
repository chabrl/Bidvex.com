# BidVex Auction Marketplace - PRD

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next
- **Backend**: FastAPI, MongoDB (Motor), Stripe, SendGrid, APScheduler
- **AI Engine**: Gemini 2.5 Flash (google-genai) — configurable via `AI_MODEL_ID` env var
- **Storage**: Cloudflare R2 via boto3 (`S3_REGION=auto`)
- **Deployment**: Railway (single-service monolith serving API + React SPA)

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Architecture
```
/app
├── backend/
│   ├── main.py                     # ASGI Entrypoint (Railway)
│   ├── server.py                   # FastAPI app, CORS, middleware, router registration (398 lines)
│   ├── lifecycle.py                # NEW — startup/shutdown events (127 lines)
│   ├── deps.py                     # Shared deps + require_admin unified gate (127 lines)
│   ├── requirements.txt            # 78 pinned packages
│   ├── routes/
│   │   ├── admin.py                # Admin: users, partners, email settings (1276 lines, deduped)
│   │   ├── admin_ops.py            # Admin: listings, auctions, categories, promotions (821 lines)
│   │   ├── admin_config.py         # Admin: settings, templates, banners (588 lines)
│   │   ├── listings.py             # Listings routes — thin controllers (627 lines)
│   │   ├── trust_safety.py         # Risk Monitoring + AI Guard
│   │   └── ...
│   └── services/
│       ├── scheduled_jobs.py       # NEW — all APScheduler job functions (255 lines)
│       ├── listings_service.py     # NEW — listings CRUD business logic (190 lines)
│       ├── ai_assistant_v2.py      # Gemini 2.5 Flash (reads AI_MODEL_ID env)
│       ├── fraud_detection.py      # Gemini 2.5 Flash + SendGrid risk alerts (>=90%)
│       └── cloud_storage.py        # boto3 R2 (S3_REGION=auto)
├── frontend/
│   ├── build/                      # Compiled React SPA (tracked in Git)
│   ├── src/
│   │   ├── pages/admin/RiskMonitoringDashboard.js
│   │   └── config.js
│   └── package.json
└── runtime.txt                     # Python 3.11.x
```

## Key Endpoints
- `GET /health` → `{"status":"ok"}`
- `GET /api/health` → `{"status":"healthy"}`
- `GET /` → React SPA
- `POST /api/ai-chat/message` → Gemini chatbot
- `GET /api/admin/risk-monitoring?min_risk=80` → Risk Monitoring
- `POST /api/admin/risk-monitoring/clear/{flag_id}` → Clear false positives
- `GET /api/marketplace/feature-flags` → Feature flags

## Completed Work

### Phase 4 & 5: Backend Architecture Refactor (April 2, 2026)
- **server.py**: 759 → 398 lines (-48%). Scheduler jobs → `services/scheduled_jobs.py`, lifecycle → `lifecycle.py`
- **admin.py**: 1558 → 1276 lines (-18%). Removed 285 lines of duplicate routes (listings, deletion requests, reports, analytics, logs) already in `admin_ops.py`
- **Unified admin middleware**: All 56+ admin routes across admin_ops.py and admin_config.py now use `Depends(require_admin)` from `deps.py` instead of inline role/email checks
- **listings.py**: 778 → 627 lines (-19%). CRUD business logic extracted to `services/listings_service.py` (validation, agreement, partner tags, promotion, serialization)
- **CORS**: Confirmed `CORS_ORIGINS` env var still respected (server.py lines 87-91)
- **Testing**: 100% frontend, 95% backend (20/21 tests passed; 1 K8s routing issue)

### 90% Risk Email Alerts (April 2, 2026)
- SendGrid email alert on fraud flags with confidence >= 90%, sent to info@bidvex.com
- Configurable via `RISK_ALERT_EMAIL` env var

### Risk Monitoring Dashboard (April 2, 2026)
- Backend + Frontend complete, tested 100%

### Railway Migration Prep (April 2, 2026)
- S3_REGION=auto, AI_MODEL_ID configurable, CORS from env var

### Previous Sessions (Cumulative)
- AI migrated to Gemini 2.5 Flash, emergentintegrations removed
- All external services wrapped in try/except
- Admin Panel (11 sections), Buyer Payment Flow, Email Marketing fixed
- Cloudflare R2, Twilio, Stripe, SendGrid connected

## Backlog

### P2 - Medium Priority
- [ ] Cloudflare CDN setup
- [ ] Post-launch monitoring & alerting
- [ ] Cache marketplace filter counts
- [ ] PDF Invoice Cloud Storage
- [ ] Partner Dashboard page

### P3 - Low Priority
- [ ] Partner Pro subscription tier
- [ ] Cookie consent i18n integration
- [ ] "Email to Friend" for vehicle listings
- [ ] "Verified Auction Firm" badge
- [ ] Database indexing on auction_id in bids collection
- [ ] E741 linting warnings in dashboard.py
