# BidVex — Auction Marketplace PRD

## Original Problem Statement
Full-stack auction marketplace (React frontend, FastAPI backend, MongoDB) with vehicle-specific identity routing, real-time WebSocket bidding, self-hosted Web Push notifications (VAPID), predictive AI analytics, and 18 active background schedulers.

## Architecture
```
/app
├── backend/
│   ├── server.py                      # FastAPI, CORS, CDN headers, SPA mount
│   ├── routes/
│   │   ├── payments.py                # Stripe checkout + offline checkout (Cash/E-Transfer)
│   │   ├── payments_fees.py           # Fee calculation + tax compliance
│   │   ├── auth.py                    # Login, register, forgot/reset/change password
│   │   ├── admin_ops.py               # Admin CRUD
│   │   ├── admin_config.py            # Marketplace settings, banners, templates, logs
│   │   ├── site_config.py             # Branding, homepage layout, hero banners, social links
│   │   ├── trust_safety.py            # Fraud detection
│   │   ├── invoices.py                # Bilingual PDF generation
│   │   └── webhooks.py               # Stripe + SendGrid webhook handlers
│   └── services/
│       ├── email_service.py           # Production SendGrid
│       ├── email_notifications.py     # 17 transactional email triggers
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

### Dynamic Social Media Icon Suite & Admin Editor (April 9, 2026)
- GET /api/site-config/social-links — Public endpoint for footer icons
- PUT /api/admin/site-config/social-links — Admin-only endpoint to update links
- Social links card in Admin > Settings > Marketplace Settings with 5 inputs (X, Facebook, Instagram, LinkedIn, TikTok)
- Footer renders SVG icons dynamically with conditional rendering (empty URLs hidden)
- Icons include target="_blank" rel="noopener noreferrer" and aria-labels

### E2E QA Audit + Bug Fixes (April 9, 2026)
- Fixed admin/auctions NameError, fraud-flags TypeError, finance/transactions missing get_db
- Removed MockEmailService from invoices.py

### SendGrid + Stripe Key Rotation (April 9, 2026)
- Both expired keys replaced and verified (SendGrid 202, Stripe PaymentIntent)

### Admin Email Migration (April 9, 2026)
- charbeladmin@bidvex.com → charbel911@gmail.com (DB + code + env)

### Password Management System (April 9, 2026)
- POST /api/auth/change-password — authenticated with current password verification
- Security tab in User Settings with real-time strength checklist
- Forgot/Reset password flows already existed (SendGrid templates)

### Multi-Item Checkout Expansion (April 9, 2026)
- 3-way payment method selector (Stripe/Cash/E-Transfer)
- POST /api/payments/offline-checkout/{listing_id} — skips Stripe, marks items reserved
- Bilingual confirmation emails with method-specific instructions (Interac email / cash pickup)
- New DB collection: `offline_orders` with payment_method, order_status, payment_status fields

## Key API Endpoints
- GET /api/site-config/social-links — Public social links for footer
- PUT /api/admin/site-config/social-links — Admin social links update
- POST /api/auth/change-password — Authenticated password change
- POST /api/payments/offline-checkout/{listing_id} — Cash/E-Transfer checkout
- GET /api/payments/offline-order/{order_id} — Offline order details
- GET /api/payments/fees/vehicle?price=X&buyer_tier=Y — Vehicle fee calc

## New Database Fields
- `site_config.social_links`: { x, facebook, instagram, linkedin, tiktok } (string URLs)
- `offline_orders` collection: id, listing_id, buyer_id, seller_id, payment_method, order_status, payment_status, breakdown, interac_email, timestamps

## 3rd Party Integration Status
- **Stripe** — Live key active, webhook infrastructure working
- **SendGrid** — Live key active, 202 sends confirmed
- **VAPID Web Push** — Active
- **Twilio** — Configured

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Admin offline order management (confirm receipt, mark paid)
- (Enhancement) Two-factor authentication (2FA)
- (Enhancement) Automated Lighthouse audits
