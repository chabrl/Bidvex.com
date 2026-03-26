# BidVex Auction Marketplace - PRD

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next
- **Backend**: FastAPI, MongoDB (Motor), Stripe, SendGrid, APScheduler
- **Storage**: S3-compatible (boto3), Railway deployment

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Platform Remediation (Complete)

### TASK 1 — Admin Panel: All Features Fixed
- **JWT_SECRET mismatch** (ROOT CAUSE of all 401s): `admin.py` default was `"your-secret-key"`, `auth.py` was `"dev-secret-key-change-in-production"`. Fixed across `admin.py`, `profiles.py`, `reviews.py`, `vehicles.py` — all now use same default.
- **Trust Safety Scores 500**: `calculate_trust_score` function was missing. Implemented inline with scoring based on verification, transaction history, fraud flags.
- **AI Guard Stats 500**: `FLAG_TYPES` not imported in `trust_safety.py`. Added import from `fraud_detection.py`.
- **MongoDB tuning**: `maxPoolSize=50`, `serverSelectionTimeoutMS=5000`, `connectTimeoutMS=10000`, `w="majority"`
- **Site-config timeout**: Wrapped in try/except, returns default branding on DB failure.
- **DB indexes**: Created `db/indexes.py` with `hero_banners`, `listings`, `announcements` indexes.
- **33/33 admin endpoints verified** returning 200 with valid token.

### TASK 2 — Buyer Payment Flow: Verified
- Checkout endpoint exists at `/api/payments/checkout` (Stripe session creation)
- Fee calculation at `/api/payments/fees/calculate-buyer-cost` returns `hammer_price`, `buyer_premium`, `platform_fee`
- Webhook handler at `/api/webhooks/stripe` processes `checkout.session.completed`
- Vehicle payments use direct `stripe` SDK (replaced `emergentintegrations`)

### TASK 3 — Email Marketing: Verified
- Campaign management at `/api/admin/marketing/campaigns`
- Email settings at `/api/admin/email-settings`
- Email templates at `/api/admin/email-templates`
- Seller email marketing service exists in `services/user_email_marketing.py`
- SendGrid integration for transactional and marketing emails

### TASK 4 — Platform Health Check: Passed
- Auth & roles: login, registration, role-based access all working
- All admin API endpoints return 200 (tested 33 endpoints)
- Database indexes verified created on startup
- `config.js` uses env var with production fallback
- CORS configured for `bidvex.com`, `www.bidvex.com`, Railway URL
- Error handling: `site-config` returns defaults on DB failure

### Testing: 29/29 backend + frontend tests passed (Iteration 87)

## Environment Variables for Railway
- `MONGO_URL`, `DB_NAME`, `JWT_SECRET`, `STRIPE_API_KEY`, `STRIPE_PUBLISHABLE_KEY`
- `SENDGRID_API_KEY`, `FRONTEND_URL`, `EMERGENT_LLM_KEY` (=OpenAI API key)
- `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `S3_BUCKET_NAME`, `S3_REGION`, `S3_ENDPOINT_URL`

## Backlog
- (P2) Cloudflare CDN setup
- (P2) Post-launch monitoring
- (Post-Launch) Production secrets rotation
