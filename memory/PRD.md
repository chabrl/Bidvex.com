# BidVex Auction Marketplace - PRD

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next
- **Backend**: FastAPI, MongoDB (Motor), Stripe, SendGrid, APScheduler
- **Storage**: S3-compatible (boto3)
- **Deployment**: Emergent (backend port 8001, frontend port 3000)

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Completed Work

### Deployment Fix — Pod Cleanup (March 27, 2026)
- Nuked 209 → 75 installed packages (removed chromadb, langchain, numpy, pandas, scipy, onnxruntime, etc.)
- Cleared 309MB pip cache
- Froze requirements.txt to 75 exact pinned versions (deterministic builds)
- Clean startup verified: `Application startup complete.` with zero tracebacks
- `.gitignore` cleaned: removed `.env` blocking patterns for Emergent deployment

### Deployment Hardening (March 27, 2026)
- Google Maps gracefully disabled (reactivates when real key added to env)
- All external service initializations wrapped in try/except (Stripe, MongoDB, WebSocket, APScheduler)

### Settings Page Fix (March 27, 2026)
- Fixed `ProfileSettingsPage.js` — wrong API path for payment-methods

### Previous Session Work
- Admin Panel (11 sections fixed), Buyer Payment Flow, Email Marketing, Platform Health
- Library migration: `emergentintegrations` → `openai`, `boto3`, `stripe`
- Frontend: `npx serve -s build -l 3000`

## Architecture
```
/app
├── backend/
│   ├── main.py                 # ASGI Entrypoint
│   ├── server.py               # FastAPI setup, middleware, routers
│   ├── requirements.txt        # 75 pinned packages (DO NOT BLOAT)
│   ├── routes/
│   └── services/
├── frontend/
│   ├── build/                  # Compiled React SPA
│   ├── src/
│   └── package.json            # start: "npx serve -s build -l 3000"
```

## Key Endpoints
- `GET /api/health` → `{"status": "healthy"}`
- `GET /` → React SPA
- `GET /api/config/google-maps-key` → `{"enabled": false}` until key added

## Backlog
- (P2) Cloudflare CDN setup
- (P2) Post-launch monitoring
- (Enhancement) Performance dashboard, Lighthouse audits
- (Low) i18n for EmailMarketingPricing
