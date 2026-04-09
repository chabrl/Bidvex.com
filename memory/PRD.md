# BidVex — Auction Marketplace PRD

## Original Problem Statement
Full-stack auction marketplace (React frontend, FastAPI backend, MongoDB) with vehicle-specific identity routing, real-time WebSocket bidding, self-hosted Web Push notifications (VAPID), predictive AI analytics, and 18 active background schedulers.

## Architecture
```
/app
├── backend/
│   ├── server.py                      # FastAPI, CORS, CDN headers, SPA mount
│   ├── shared.py                      # Pydantic models, constants, utilities
│   ├── routes/
│   │   ├── payments.py                # Stripe checkout + offline checkout (Cash/E-Transfer)
│   │   ├── payments_fees.py           # Fee calculation + tax compliance
│   │   ├── auth.py                    # Login, register, forgot/reset/change password
│   │   ├── admin_ops.py               # Admin CRUD
│   │   ├── admin_config.py            # Marketplace settings, banners, templates, logs
│   │   ├── site_config.py             # Branding, homepage layout, hero banners, social links
│   │   ├── email_marketing_ext.py     # User/Admin marketing contacts & campaigns
│   │   ├── trust_safety.py            # Fraud detection
│   │   ├── invoices.py                # Bilingual PDF generation
│   │   └── webhooks.py               # Stripe + SendGrid webhook handlers
│   └── services/
│       ├── email_service.py           # Production SendGrid
│       ├── email_notifications.py     # 17 transactional email triggers
│       ├── user_email_marketing.py    # User contact/campaign management
│       ├── email_marketing.py         # Admin marketing service
│       ├── fee_calculation_engine.py  # Vehicle vs General fee math
│       ├── tax_engine.py              # Quebec GST/QST compliance
│       └── scheduled_jobs.py          # 18 background jobs
├── frontend/
│   ├── build/                         # Compiled React SPA
│   └── src/
│       ├── components/Footer.js       # Dynamic social media icons
│       └── pages/
│           ├── admin/MarketplaceSettings.js  # Social links admin editor
│           ├── CheckoutPage.js        # 3-way payment method (Stripe/Cash/E-Transfer)
│           ├── ProfileSettingsPage.js  # Security tab with Change Password
│           ├── ForgotPasswordPage.js   # Forgot password flow
│           └── ResetPasswordPage.js    # Token-based password reset
```

## Completed Features

### Marketing Contact 500 Error Fix (April 9, 2026)
- Fixed Pydantic model mismatch in shared.py causing AttributeError on POST /api/user/marketing/contacts
- UserContactCreateRequest: added consent_confirmed field
- UserContactBulkRequest: changed from contacts:List[Dict] to emails:List[str] + consent_confirmed
- UserCampaignCreateRequest: added html_content, plain_text_content, auction_id fields

### Dynamic Social Media Icon Suite & Admin Editor (April 9, 2026)
- GET /api/site-config/social-links — Public endpoint for footer icons
- PUT /api/admin/site-config/social-links — Admin-only endpoint to update links
- Social links card in Admin > Settings > Marketplace Settings
- Footer renders SVG icons dynamically with conditional rendering

### E2E QA Audit + Bug Fixes (April 9, 2026)
- Fixed admin/auctions NameError, fraud-flags TypeError, finance/transactions missing get_db

### SendGrid + Stripe Key Rotation (April 9, 2026)
- Both expired keys replaced and verified

### Admin Email Migration (April 9, 2026)
- charbeladmin@bidvex.com → charbel911@gmail.com

### Password Management System (April 9, 2026)
- POST /api/auth/change-password with Security tab in User Settings

### Multi-Item Checkout Expansion (April 9, 2026)
- 3-way payment method selector (Stripe/Cash/E-Transfer)
- POST /api/payments/offline-checkout/{listing_id}

## Key API Endpoints
- POST /api/user/marketing/contacts — Add single contact (fixed)
- POST /api/user/marketing/contacts/bulk — Add multiple contacts (fixed)
- POST /api/user/marketing/campaigns — Create campaign (fixed)
- GET /api/site-config/social-links — Public social links
- PUT /api/admin/site-config/social-links — Admin social links update
- POST /api/auth/change-password — Authenticated password change
- POST /api/payments/offline-checkout/{listing_id} — Cash/E-Transfer checkout

## 3rd Party Integration Status
- **Stripe** — Live key active
- **SendGrid** — Live key active (separate marketing + transactional keys)
- **VAPID Web Push** — Active
- **Twilio** — Configured

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Admin offline order management
- (Enhancement) Two-factor authentication (2FA)
- (Enhancement) Automated Lighthouse audits
