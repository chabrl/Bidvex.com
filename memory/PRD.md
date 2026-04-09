# BidVex — Auction Marketplace PRD

## Original Problem Statement
Full-stack auction marketplace (React frontend, FastAPI backend, MongoDB) with four major development phases:
1. **Retention Phase**: Outbid Alerts, Zero-Latency Timer Extensions, Winner's Circle, AI User Interest tracking.
2. **Dealer Experience**: OPC-Certified Seller BP Control, Category restrictions, Payment Orchestration.
3. **Vehicle Routing & Analytics**: Vehicle Identity routing, Real-Time Marketplace Sync, Dynamic BP, Seller Ratings.
4. **Re-engagement Phase**: Self-Hosted Web Push Notifications, Predictive Seller Analytics, CDN Audit, AI Personalization.

## Architecture
```
/app
├── backend/
│   ├── server.py                      # FastAPI, CORS, CDN headers, SPA mount
│   ├── ws_managers.py                 # Connection managers (listing, message, marketplace)
│   ├── ws_handlers.py                 # WebSocket endpoints
│   ├── routes/
│   │   ├── admin_ops.py               # Admin CRUD (fixed auctions, finance/transactions)
│   │   ├── trust_safety.py            # Fraud detection (fixed fromisoformat bug)
│   │   ├── push_notifications.py      # VAPID Web Push subscribe/send
│   │   ├── user_insights.py           # AI tracking + regional trends
│   │   ├── carousel.py                # AI-personalized ending-soon
│   │   ├── auctions_bids.py           # Bidding + outbid push alerts
│   │   ├── auctions.py                # Auction lifecycle + offline invoices
│   │   └── vehicles.py                # Vehicle listings + terms
│   └── db/indexes.py                  # MongoDB indexes
├── frontend/
│   ├── public/sw.js                   # Service Worker (push + smart routing)
│   ├── src/
│   │   ├── utils/pushNotifications.js # VAPID subscription management
│   │   ├── components/PushNotificationToggle.js  # 3-variant notification UI
│   │   ├── hooks/useMarketplaceSync.js            # Global WS real-time sync
│   │   ├── pages/SellerDashboard.js               # RegionalTrendsPanel
│   │   └── pages/ProfileSettingsPage.js           # Push settings integration
```

## Completed Phases

### Phase 1 — Retention (COMPLETE)
### Phase 2 — Dealer Experience (COMPLETE)
### Phase 3 — Vehicle Routing & Analytics (COMPLETE)
### Phase 4 — Re-engagement (COMPLETE, April 8 2026)
- Web Push Notifications, Predictive Seller Analytics, CDN Readiness, AI Personalization

### E2E QA — Complete (April 9 2026)
- Fixed 3 server errors in admin panel endpoints
- 76 backend API endpoints tested, 67 passed
- Full frontend UI testing passed (Auth, Marketplace, Admin, Vehicle, Lots)

## Key API Endpoints
- `GET /api/health` — Platform health
- `GET /api/site-mode` — Current mode (live/coming_soon)
- `POST /api/auth/login` — Login
- `POST /api/auth/register` — Register
- `GET /api/listings` — Browse listings
- `GET /api/admin/auctions` — Admin auction management
- `GET /api/admin/trust-safety/fraud-flags` — Fraud detection
- `GET /api/admin/finance/transactions` — Transaction logs
- `GET /api/push/vapid-public-key` — VAPID key for push
- `GET /api/insights/regional-trends` — Seller analytics
- `GET /api/carousel/ending-soon` — AI-personalized carousel

## 3rd Party Integrations
- Stripe (Payments) — Live keys configured
- SendGrid (Emails) — API key configured, MOCKED in preview (logged not sent)
- Twilio (SMS/Verify) — Configured
- Cloudflare R2 / AWS S3 (Object Storage via boto3)
- Self-hosted VAPID Web Push (pywebpush)

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring and alerting
- (Enhancement) Automated Lighthouse audits
- (Low) i18n for EmailMarketingPricing page
