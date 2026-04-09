# BidVex — Auction Marketplace PRD

## Original Problem Statement
Full-stack auction marketplace (React frontend, FastAPI backend, MongoDB) with vehicle-specific identity routing, real-time WebSocket bidding, self-hosted Web Push notifications (VAPID), predictive AI analytics, and 18 active background schedulers.

## Architecture
```
/app
├── backend/
│   ├── server.py                      # FastAPI, CORS, CDN headers, SPA mount
│   ├── routes/
│   │   ├── admin_ops.py               # Admin CRUD (fixed auctions, finance/transactions)
│   │   ├── trust_safety.py            # Fraud detection (fixed fromisoformat bug)
│   │   ├── invoices.py                # Invoice PDF generation (mock removed, real SendGrid)
│   │   ├── webhooks.py                # Stripe + SendGrid webhook handlers (12 handlers)
│   │   ├── payments.py                # Stripe checkout, payment methods
│   │   ├── payments_fees.py           # Fee calculation + tax compliance sub-router
│   │   ├── push_notifications.py      # VAPID Web Push
│   │   └── auctions_bids.py           # Bidding + outbid push alerts
│   └── services/
│       ├── email_service.py           # Production SendGrid (templates + raw HTML)
│       ├── email_notifications.py     # 17 transactional email triggers
│       ├── fee_calculation_engine.py  # Vehicle vs General fee math
│       ├── tax_engine.py              # Quebec GST/QST compliance
│       ├── scheduled_jobs.py          # 18 background jobs (overdue penalties, invoicing)
│       └── invoice_generator.py       # Bilingual PDF via ReportLab
├── frontend/
│   ├── build/                         # Compiled React SPA
│   └── src/
├── Procfile                           # Railway startup
└── .env.example                       # Sanitized env template
```

## Completed Work

### E2E QA Audit (April 9, 2026)
- Fixed 3 server errors: admin/auctions (NameError), fraud-flags (TypeError), finance/transactions (missing get_db)
- 76 backend API endpoints tested, all critical paths passing
- Full frontend UI testing passed

### SendGrid Production Restoration (April 9, 2026)
- Removed MockEmailService from invoices.py
- Rotated expired SendGrid API keys (4th key validated, 202 Accepted confirmed)
- All 17 email triggers wired to real SendGrid

### Stripe Financial Audit (April 9, 2026)
- **CRITICAL FINDING: Stripe API key (`sk_live_`) is EXPIRED — payment processing blocked**
- Webhook infrastructure: 100% functional (signature verification, 12 event handlers, DB logging)
- Fee calculations: 100% accurate (Vehicle 0% seller commission, General 4%/5% tiers, VIP 2%/3%)
- Quebec tax (GST 5% + QST 9.975%): All math verified to the cent
- Post-payment automation: PDF generator (ReportLab), bilingual invoices, confirmation emails — all wired
- Overdue payment scheduler: 2% monthly penalty with notification system

## Key API Endpoints
- `GET /api/health` — Platform health
- `POST /api/auth/login` — Login
- `GET /api/payments/fees/vehicle?price=X&buyer_tier=Y` — Vehicle fee calc
- `POST /api/payments/fees/calculate` — General fee calc
- `GET /api/payments/tax/vehicle?price=X` — Vehicle tax (Quebec)
- `GET /api/payments/tax/general?price=X` — General tax (Quebec)
- `GET /api/payments/tax/rates` — Tax rate structure
- `POST /api/webhooks/stripe` — Stripe webhook (multi-secret verification)

## 3rd Party Integration Status
- **Stripe** (Payments) — ❌ API KEY EXPIRED (webhook infra ready)
- **SendGrid** (Emails) — ✅ LIVE, 202 sends confirmed
- **Twilio** (SMS/Verify) — Configured
- **Cloudflare R2 / AWS S3** — Configured
- **VAPID Web Push** — Active

## Backlog
- 🔴 (P0) Replace expired Stripe API key
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring and alerting
