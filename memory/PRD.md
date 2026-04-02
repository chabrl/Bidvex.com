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
│   ├── main.py                 # ASGI Entrypoint (Railway)
│   ├── server.py               # FastAPI setup, middleware, routers, SPA catch-all
│   ├── requirements.txt        # 78 pinned packages
│   ├── routes/
│   │   ├── trust_safety.py     # Risk Monitoring + AI Guard endpoints
│   │   └── ...
│   └── services/
│       ├── ai_assistant_v2.py  # Gemini 2.5 Flash (reads AI_MODEL_ID env)
│       ├── fraud_detection.py  # Gemini 2.5 Flash
│       └── cloud_storage.py    # boto3 R2 (S3_REGION=auto)
├── frontend/
│   ├── build/                  # Compiled React SPA (tracked in Git)
│   ├── src/
│   │   ├── pages/admin/RiskMonitoringDashboard.js  # NEW - Risk Monitoring UI
│   │   └── config.js           # API_BASE = REACT_APP_BACKEND_URL + "/api"
│   └── package.json
└── runtime.txt                 # Python 3.11.x
```

## Key Endpoints
- `GET /health` → `{"status":"ok"}` (Railway health check)
- `GET /api/health` → `{"status":"healthy"}`
- `GET /` → React SPA (served from frontend/build)
- `POST /api/ai-chat/message` → Gemini chatbot
- `GET /api/admin/ai-guard/flags` → AI Guard fraud flags
- `GET /api/admin/risk-monitoring?min_risk=80` → Risk Monitoring (high-risk flags + users)
- `POST /api/admin/risk-monitoring/clear/{flag_id}` → Clear false positive flags

## Completed Work

### Risk Monitoring Dashboard (April 2, 2026)
- Backend: `GET /api/admin/risk-monitoring` — aggregates high-confidence fraud flags (confidence >= threshold/100) and users with low trust scores
- Backend: `POST /api/admin/risk-monitoring/clear/{flag_id}` — quick-clear with admin notes and audit logging
- Frontend: `RiskMonitoringDashboard.js` — full admin page with KPI stats, flag/user dual view, behavioral analysis, threshold selector, search, clear dialog
- Wired into AdminDashboard under Vehicles > Risk Monitoring tab
- Tested: 100% backend (4/4) + 100% frontend pass rate

### Railway Migration Prep (April 2, 2026)
- `S3_REGION=auto` applied in .env (R2/boto3 fix)
- `AI_MODEL_ID=gemini-2.5-flash` added as configurable env var
- CORS now reads from `CORS_ORIGINS` env var (production lockdown with `allow_credentials=True`)
- Full environment manifest generated for Railway AI Agent

### Previous Sessions (Cumulative)
- AI migrated from OpenAI to Gemini 2.5 Flash (google-genai)
- emergentintegrations library fully removed
- All external services wrapped in try/except for safe startup
- frontend/build tracked in Git, served by FastAPI StaticFiles
- Admin Panel (11 sections), Buyer Payment Flow, Email Marketing fixed
- requirements.txt stripped to 78 pinned packages
- Cloudflare R2 storage configured (bidvex-auctions-prod bucket)
- Twilio, Stripe, SendGrid live keys connected and verified
- Google Maps gracefully disabled with UI fallbacks
- Settings page blank issue fixed

## Backlog

### P1 - High Priority
- [ ] server.py Refactor Phase 4: Deduplicate admin user mgmt routes
- [ ] server.py Refactor Phase 5: Extract listings CRUD, bids, multi-item auctions

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
