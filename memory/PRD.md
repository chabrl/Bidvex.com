# BidVex Auction Marketplace - PRD

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next
- **Backend**: FastAPI, MongoDB (Motor), Stripe, SendGrid, APScheduler
- **Storage**: S3-compatible (boto3)
- **Deployment**: Railway (backend + frontend)

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Completed Remediation

### TASK 1 — Admin Panel (All 11 Sections Fixed)
- **JWT_SECRET mismatch** — ROOT CAUSE of all admin 401s. Fixed across `admin.py`, `profiles.py`, `reviews.py`, `vehicles.py`
- **Array normalization** — Fixed 8 admin pages that crashed with `.map is not a function`
- **Missing imports** — `FLAG_TYPES` in trust_safety.py, `calculate_trust_score` function implemented
- **MongoDB tuning** — maxPoolSize=50, serverSelectionTimeoutMS=5000, w="majority"
- **Site-config timeout** — try/except fallback returning defaults on DB failure
- **DB indexes** — hero_banners, listings, announcements indexes via db/indexes.py
- **33/33 admin endpoints verified 200**, 8/8 frontend sections load without errors

### TASK 2 — Buyer Payment Flow (Verified)
- Checkout page loads correctly, validates auction winner access
- Stripe webhook handling operational

### TASK 3 — Email Marketing (Verified)
- Campaign data, SendGrid config, template categories all returning correctly

### TASK 4 — Platform Health Check (Passed)
- Auth, API endpoints, database indexes, CORS all verified
- Iteration 87: 29/29 backend tests passed (100%)
- Iteration 88: 17/17 backend + 8/8 frontend tests passed (100%)

## Bug Fixes

### Settings Page Blank — Fixed (March 27, 2026)
- **Root Cause**: `ProfileSettingsPage.js` called `GET /api/payment-methods` but the backend route is `GET /api/payments/payment-methods` (payments router prefix). SPA catch-all returned HTML (200), causing `.map()` crash.
- **Fix**: Updated 3 API paths in `ProfileSettingsPage.js` to include `/payments/` prefix. Added `Array.isArray()` guard.
- **File**: `/app/frontend/src/pages/ProfileSettingsPage.js` (lines 71, 109, 576)

## Deployment Status

### Confirmed Working
- Backend: Uvicorn on 0.0.0.0:8001 ✅
- Frontend: npx serve -s build on 0.0.0.0:3000 ✅
- requirements.txt: 28 packages (lean) ✅
- build/index.html: EXISTS ✅
- /api/health → 200 ✅
- / → 200 (React SPA) ✅

### Platform Routing Issue (Emergent-side)
- `prod-verify-2.preview.emergentagent.com` → 104.18.10.243 → HTTP 200 ✅
- `prod-verify-2.emergent.host` → 104.18.14.241 → HTTP 520 ❌
- Different Cloudflare zones with different origin IPs
- 520 errors are infrastructure routing, NOT application code

## Environment Variables for Railway
- `MONGO_URL`, `DB_NAME`, `JWT_SECRET` (CRITICAL)
- `STRIPE_API_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
- `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`, `SENDGRID_FROM_NAME`
- `FRONTEND_URL`, `EMERGENT_LLM_KEY`

## Deployment Notes
- Backend entry: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- `main.py` re-exports `app` from `server.py`
- Frontend: `npx serve -s build -l 3000`
- **DO NOT** re-add heavy ML dependencies to requirements.txt
- **DO NOT** refactor server.py (user directive)

## Backlog
- (P2) Cloudflare CDN setup
- (P2) Post-launch monitoring and alerting
- (Enhancement) Real-time performance dashboard
- (Enhancement) Automated Lighthouse audits
- (Enhancement) Server-side PageSpeed monitoring endpoint
- (Low) i18n for EmailMarketingPricing page
