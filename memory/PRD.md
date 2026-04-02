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
│       ├── fraud_detection.py  # Gemini 2.5 Flash + SendGrid risk alerts (>=90%)
│       └── cloud_storage.py    # boto3 R2 (S3_REGION=auto)
├── frontend/
│   ├── build/                  # Compiled React SPA (tracked in Git)
│   ├── src/
│   │   ├── pages/admin/RiskMonitoringDashboard.js  # Risk Monitoring UI
│   │   └── config.js
│   └── package.json
└── runtime.txt                 # Python 3.11.x
```

## Key Endpoints
- `GET /health` → `{"status":"ok"}`
- `GET /api/health` → `{"status":"healthy"}`
- `GET /` → React SPA
- `POST /api/ai-chat/message` → Gemini chatbot
- `GET /api/admin/ai-guard/flags` → AI Guard fraud flags
- `GET /api/admin/risk-monitoring?min_risk=80` → Risk Monitoring dashboard data
- `POST /api/admin/risk-monitoring/clear/{flag_id}` → Clear false positive flags

## Completed Work

### 90% Risk Email Alerts (April 2, 2026)
- `fraud_detection.py` `save_flag()` now fires background email via SendGrid when confidence >= 0.90
- Email sent to `info@bidvex.com` (configurable via `RISK_ALERT_EMAIL` env var)
- Professional HTML email template with flag details, severity, and action link
- Alert logged to `admin_logs` collection for audit trail
- Tested end-to-end: email delivered successfully to info@bidvex.com

### Risk Monitoring Dashboard (April 2, 2026)
- Backend: `GET /api/admin/risk-monitoring` + `POST /api/admin/risk-monitoring/clear/{flag_id}`
- Frontend: Full admin page with KPI stats, flag/user dual view, behavioral analysis, threshold selector, clear dialog
- Wired into Admin Panel under Vehicles > Risk Monitoring
- Tested: 100% pass (iteration_89)

### Railway Migration Prep (April 2, 2026)
- `S3_REGION=auto`, `AI_MODEL_ID=gemini-2.5-flash`, CORS from env var
- Full environment manifest generated

### Previous Sessions (Cumulative)
- AI migrated to Gemini 2.5 Flash, emergentintegrations removed
- All external services wrapped in try/except
- Admin Panel (11 sections), Buyer Payment Flow, Email Marketing fixed
- requirements.txt: 78 pinned packages
- Cloudflare R2, Twilio, Stripe, SendGrid connected

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
