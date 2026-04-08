# BidVex Auction Marketplace — PRD

## Product Overview
BidVex is a bilingual (EN/FR) production-ready auction marketplace with:
- Real-time bidding (WebSocket), auto-bid bots, anti-sniping extensions
- Vehicle and General marketplace with category isolation
- AI user behavioral tracking for personalization
- OPC-certified seller buyer's premium control
- Multi-payment orchestration (Stripe/Cash/E-Transfer)
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
- Task 1: Outbid Alert System — Email (SendGrid) + WebSocket AUTO_BID_EXCEEDED
- Task 2: Service Recovery — Sidebar filters (category/region/city), Lots page, Vehicle timer white text
- Task 3: Zero-Latency Extension Sync — BID_UPDATE + TIME_EXTENSION events
- Task 4: Winner's Circle — WINNER/GAGNANT badge + persist_auction_winner (30-day TTL)
- Task 5: Gemini Insight User Profiling — user_interests collection, batched tracking
- Task 6: Stealth WebSocket Reconnection

### Dealer Experience Phase (Apr 8, 2026)
- **Task 1: OPC-Certified Seller BP Control** — `is_opc_certified` user flag, BP slider (0-25%) for OPC sellers, "Vendeur Certifie OPC" badge on 0% BP, pricing calculator updated
- **Task 2: Category & Role Restrictions** — Standard users blocked from listing vehicles (403). Only Partner/Admin can list vehicles. Enforced on both single-item and multi-item flows
- **Task 3: Payment Orchestration** — Seller payment method selection (Stripe/Cash/E-Transfer) with legal disclosure for offline methods. Stripe labeled "Recommended"
- **Task 4: High-Priority UI Fixes** — Timer "Loading..." bug FIXED (useVehicleBidding rewritten to use correct WS endpoint + fallback to vehicleData). Terms acceptance fixed (listings collection fallback). Vehicle timer text changed to white high-visibility
- **Task 5: AI & Bulk Data Update** — 12 vehicles set to is_opc_certified:true with 0% BP. Payment preference and OPC interest tracking added to useInsightsTracker

### Bug Fixes
- P0: Vehicle Detail Page blank screen (useTranslation in helper functions)
- P0: Timer "Loading..." hang (useVehicleBidding connected to non-existent WS endpoint)
- Terms acceptance 404 (vehicle in listings collection, not vehicle_listings)

## Key API Endpoints
- GET /api/health
- GET /api/marketplace/items?categories=X&regions=Y&cities=Z
- GET /api/marketplace/filter-counts
- GET /api/vehicles, GET /api/vehicles/:id
- POST /api/vehicles/{id}/accept-terms
- POST /api/bids
- POST /api/listings (with buyers_premium_rate, payment_method, category restrictions)
- POST /api/multi-item-listings (with category restrictions)
- POST /api/insights/track, POST /api/insights/track-batch
- GET /api/insights/profile/:user_id
- GET /api/winners/my-wins

## DB Collections
- listings, vehicle_listings, multi_item_listings
- users (is_opc_certified field)
- bids, auto_bids, notifications
- user_interests (TTL: 90 days)
- won_auctions (TTL: 30 days)

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
- Seller Rating Dashboard (individual reviews + average scores)
