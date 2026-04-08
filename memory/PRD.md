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
- **Web Push Notifications**: Self-hosted VAPID, outbid alerts + watchlist 5-min expiry, smart routing (vehicle vs listing)
- **Permission UI**: "Enable Notifications" button in Settings + subtle prompt in bid confirmation dialog
- **Predictive Seller Analytics**: "Market Trends" tab with Top Categories, Active Regions, Key Insights from user_interests
- **CDN Readiness**: Cache-Control + CDN-Cache-Control headers, X-Content-Type-Options: nosniff, Vary: Accept-Encoding
- **AI Personalization**: Ending Soon carousel re-sorted by user interest affinity for logged-in users

## Key API Endpoints
- `GET /api/push/vapid-public-key` — VAPID public key for SW subscription
- `POST /api/push/subscribe` — Save push subscription (auth required)
- `DELETE /api/push/unsubscribe` — Remove push subscription
- `GET /api/push/status` — Check subscription status
- `GET /api/insights/regional-trends` — Seller analytics trends
- `GET /api/carousel/ending-soon?user_id=xxx` — AI-personalized carousel
- `WS /api/ws/marketplace` — Global real-time marketplace updates

## 3rd Party Integrations
- Stripe (Payments), SendGrid (Emails), Twilio (SMS)
- Cloudflare R2 / AWS S3 (Object Storage via boto3)
- Self-hosted VAPID Web Push (pywebpush)

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring and alerting
- (Enhancement) Automated Lighthouse audits
- (Low) i18n for EmailMarketingPricing page
