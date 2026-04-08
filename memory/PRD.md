# BidVex Auction Marketplace — PRD

## Product Overview
BidVex is a bilingual (EN/FR) production-ready auction marketplace with:
- Real-time bidding (WebSocket), auto-bid bots, anti-sniping extensions
- Vehicle and General marketplace with category isolation
- AI user behavioral tracking for personalization
- Admin dashboard with full moderation
- Push notifications, email marketing (SendGrid), SMS (Twilio)
- Stripe payments, Cloudflare R2 storage, Gemini AI assistant

## Architecture
- Frontend: React (CRA) served as static build via `npx serve -s build`
- Backend: FastAPI (Python) on port 8001
- Database: MongoDB Atlas
- Real-time: WebSocket for bidding + notifications
- Deployment: Prepared for Railway / PaaS

## Completed Features

### Core
- Multi-user bidding with server-side timestamp validation (hard stop 403)
- Auto-bid bot with recursive counter-bidding and personality toasts
- Anti-sniping: 2-minute extensions when bid placed in final minutes
- Zero-latency timer sync via WebSocket TIME_EXTENSION events
- Vehicle category isolation from general marketplace
- Bulk listings (20 items: 10 vehicles, 10 general)

### Retention Phase (Apr 8, 2026)
- **Task 1: Outbid Alert System** — Email (SendGrid) + WebSocket AUTO_BID_EXCEEDED notification when auto-bid max is exceeded. Bot personality toasts ("Beep boop! I'm still the boss here.").
- **Task 2: Service Recovery** — Fixed sidebar filters (category, region, city pass to API), Lots page query, Vehicle timer text changed to white/high-visibility.
- **Task 3: Zero-Latency Extension Sync** — BID_UPDATE.time_extended and TIME_EXTENSION events update timer instantly without page reload.
- **Task 4: Winner's Circle** — "WINNER / GAGNANT" badge on ended auction items. persist_auction_winner() saves to won_auctions collection (30-day TTL). GET /winners/my-wins endpoint.
- **Task 5: Gemini Insight User Profiling** — user_interests collection with event tracking (views, clicks, bids, searches). Batched frontend tracking via useInsightsTracker hook. GET /insights/profile/{user_id} for aggregated profiles.
- **Task 6: Stealth Connection** — Silent WebSocket reconnection (no "Live Connection Lost" toast).

### Bug Fixes (Apr 8, 2026)
- **P0: Vehicle Detail Page blank screen** — Root cause: useTranslation() called inside non-component helper functions in AuctionRulesDisplay.js, PricingCalculator.js, PricingBreakdown.js, LegalDisclaimers.js, SellerDocumentManager.js. Fixed by adding useTranslation hook to actual component functions.

## Key API Endpoints
- GET /api/health
- GET /api/marketplace/items?categories=X&regions=Y&cities=Z
- GET /api/marketplace/filter-counts
- GET /api/vehicles, GET /api/vehicles/:id
- POST /api/bids
- POST /api/insights/track, POST /api/insights/track-batch
- GET /api/insights/profile/:user_id
- GET /api/winners/my-wins
- GET /api/notifications

## DB Collections
- listings, vehicle_listings, multi_item_listings
- users, bids, auto_bids
- user_interests (TTL: 90 days) — behavioral tracking
- won_auctions (TTL: 30 days) — winner persistence
- notifications

## 3rd Party Integrations
- OpenAI GPT-4o (EMERGENT_LLM_KEY / OPENAI_API_KEY)
- Stripe (Payments)
- SendGrid (Emails)
- Twilio (SMS)
- Cloudflare R2 / S3 (Storage via boto3)
- Gemini 2.5 Flash (EMERGENT_LLM_KEY / GEMINI_API_KEY)

## Backlog / Future
- (P2) Cloudflare CDN setup per /app/memory/INFRASTRUCTURE_P2.md
- Post-launch monitoring and alerting
- Real-time performance dashboard
- Automated weekly Lighthouse audits
- Server-side PageSpeed monitoring endpoint
- i18n for EmailMarketingPricing page
- Personalized "Picked for You" email campaigns using user_interests data
