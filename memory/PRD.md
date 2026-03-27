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
- **Array normalization** — Fixed 8 admin pages that crashed with `.map is not a function`: ManageAllAuctions, AnalyticsDashboard, AdminLogs, MessagingOversight, ReportManager, DeletionRequestsManager, SubscriptionManager, EmailTemplates
- **Missing imports** — `FLAG_TYPES` in trust_safety.py, `calculate_trust_score` function implemented
- **MongoDB tuning** — maxPoolSize=50, serverSelectionTimeoutMS=5000, w="majority"
- **Site-config timeout** — try/except fallback returning defaults on DB failure
- **DB indexes** — hero_banners, listings, announcements indexes via db/indexes.py
- **Admin Logs date fix** — Graceful handling of missing created_at timestamps
- **33/33 admin endpoints verified 200**, 8/8 frontend sections load without errors

### TASK 2 — Buyer Payment Flow (Verified)
- Checkout page loads correctly, validates auction winner access
- POST /api/payments/checkout/auction and /api/payments/auction-winner-checkout/{id} wired
- GET /api/payments/fees/calculate-buyer-cost returns hammer_price + buyer_premium + platform_fee
- Stripe webhook at /api/webhooks/stripe handles checkout.session.completed
- Buy Now redirect → Stripe → return URL properly implemented

### TASK 3 — Email Marketing (Verified)
- GET /api/admin/marketing/campaigns returns campaign data
- GET /api/admin/email-settings returns SendGrid config
- GET /api/admin/email-templates returns template categories
- Seller email marketing service operational via user_email_marketing.py

### TASK 4 — Platform Health Check (Passed)
- Auth: login/registration/role-based access all working
- All API endpoints tested (50+ endpoints returning 200)
- Database indexes verified on startup
- CORS: bidvex.com, www.bidvex.com, Railway URL
- config.js uses env var with Railway production fallback
- Error handling: site-config returns defaults on DB failure

### Testing Results
- Iteration 87: 29/29 backend tests passed (100%)
- Iteration 88: 17/17 backend + 8/8 frontend tests passed (100%)

## Environment Variables for Railway
- `MONGO_URL`, `DB_NAME`, `JWT_SECRET` (CRITICAL - must be set!)
- `STRIPE_API_KEY`, `STRIPE_PUBLISHABLE_KEY`, `STRIPE_WEBHOOK_SECRET`
- `SENDGRID_API_KEY`, `SENDGRID_FROM_EMAIL`, `SENDGRID_FROM_NAME`
- `FRONTEND_URL`, `EMERGENT_LLM_KEY` (=OpenAI API key)
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `S3_REGION`

## Deployment Notes
- Backend entry: `uvicorn main:app --host 0.0.0.0 --port $PORT`
- `main.py` re-exports `app` from `server.py`
- `runtime.txt` specifies `python-3.11.x`
- Git push via "Save to GitHub" button in Emergent chat

## Backlog
- (P2) Cloudflare CDN setup
- (P2) Post-launch monitoring
- (Post-Launch) Production secrets rotation
