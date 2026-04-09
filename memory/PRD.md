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
│   │   ├── invoices.py                # Invoice generation (mock removed, real SendGrid)
│   │   ├── push_notifications.py      # VAPID Web Push
│   │   ├── user_insights.py           # AI tracking + regional trends
│   │   └── auctions_bids.py           # Bidding + outbid push alerts
│   └── services/
│       ├── email_service.py           # Production SendGrid (templates + raw HTML)
│       ├── email_notifications.py     # Transactional emails (17 triggers)
│       └── email_marketing.py         # Marketing campaigns
├── frontend/
│   ├── build/                         # Compiled React SPA (served by backend)
│   └── src/
├── Procfile                           # Railway startup
└── .env.example                       # Sanitized env template
```

## Completed Work

### E2E QA Audit (April 9, 2026)
- Fixed 3 server errors: admin/auctions (NameError), fraud-flags (TypeError), finance/transactions (missing get_db)
- 76 backend API endpoints tested, all critical paths passing
- Full frontend UI testing passed (Auth, Marketplace, Admin, Vehicle, Lots)

### SendGrid Production Restoration (April 9, 2026)
- Removed MockEmailService from invoices.py — replaced with real EmailService.send_raw_html()
- Fixed missing db = get_db() in complete_auction_and_send_documents()
- Rotated expired SendGrid API keys (4th key validated successfully)
- Verified real email delivery: Password Reset → 202 Accepted, message_id confirmed
- All 4 email services initialized: email_service, email_notifications, email_marketing (transactional + marketing)

## Key API Endpoints
- `GET /api/health` — Platform health
- `POST /api/auth/login` — Login (returns access_token)
- `POST /api/auth/forgot-password` — Password reset (sends real SendGrid email)
- `GET /api/listings` — Browse listings
- `GET /api/admin/auctions` — Admin auction management
- `GET /api/admin/trust-safety/fraud-flags` — Fraud detection
- `GET /api/admin/finance/transactions` — Transaction logs
- `GET /api/push/vapid-public-key` — VAPID key for push

## 3rd Party Integrations
- **Stripe** (Payments) — Live keys configured
- **SendGrid** (Emails) — ✅ LIVE, new keys active, 202 sends confirmed
- **Twilio** (SMS/Verify) — Configured
- **Cloudflare R2 / AWS S3** (Object Storage via boto3) — Configured
- **Self-hosted VAPID Web Push** (pywebpush) — Active

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring and alerting
- (Enhancement) Automated Lighthouse audits
- (Low) i18n for EmailMarketingPricing page
