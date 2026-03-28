# BidVex Auction Marketplace - PRD

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next
- **Backend**: FastAPI, MongoDB (Motor), Stripe, SendGrid, APScheduler
- **Storage**: S3-compatible (boto3)
- **Deployment**: Emergent (backend port 8001, frontend port 3000)

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Completed Work

### Deployment Hardening (March 27, 2026)
- **Google Maps**: Gracefully disabled — backend returns `{"enabled": false}` when no valid key, frontend shows text fallback. Reactivates automatically when real key is added to env.
- **External Service Wrapping**: All startup initializations (Stripe, MongoDB, WebSocket, APScheduler) wrapped in try/except. No missing/invalid key can crash the server.
- **Clean Startup Verified**: `uvicorn server:app` produces zero tracebacks, logs "Application startup complete."
- **.gitignore Fixed**: Removed overly aggressive `.env` blocking patterns so Emergent deployment can track env files.
- **requirements.txt**: Stays at 28 lean packages.

### Settings Page Blank Fix (March 27, 2026)
- **Root Cause**: `ProfileSettingsPage.js` called `GET /api/payment-methods` but route is `GET /api/payments/payment-methods`.
- **Fix**: Updated 3 API paths, added `Array.isArray()` guard.

### Previous Session Work
- Admin Panel (11 sections fixed), Buyer Payment Flow, Email Marketing, Platform Health
- Library migration: Removed `emergentintegrations`, replaced with `openai`, `boto3`, `stripe`
- Frontend: `npx serve -s build -l 3000` (no webpack dev server)
- Dependency purge: 220+ → 28 packages

## Architecture
```
/app
├── backend/
│   ├── main.py                 # ASGI Entrypoint (imports app from server.py)
│   ├── server.py               # FastAPI setup, middleware, routers, lifecycle
│   ├── requirements.txt        # 28 packages (DO NOT BLOAT)
│   ├── routes/                 # All API routes
│   └── services/               # Business logic services
├── frontend/
│   ├── build/                  # Compiled React SPA
│   ├── src/
│   └── package.json            # start: "npx serve -s build -l 3000"
└── .gitignore                  # Clean, no .env blocking
```

## Key Endpoints
- `GET /api/health` → `{"status": "healthy"}`
- `GET /health` → same
- `GET /` → React SPA (index.html)
- `GET /api/config/google-maps-key` → `{"api_key": "", "enabled": false}` (until key added)

## Backlog
- (P2) Cloudflare CDN setup
- (P2) Post-launch monitoring and alerting
- (Enhancement) Real-time performance dashboard
- (Enhancement) Automated Lighthouse audits
- (Low) i18n for EmailMarketingPricing page
