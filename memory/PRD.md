# BidVex Auction Platform - Product Requirements Document

## Original Problem Statement
Build a full-featured auction platform named BidVex with real-time bidding, subscription tiers, fee management, and comprehensive buyer/seller tools.

## Core Architecture
- **Frontend**: React with Tailwind CSS, Shadcn/UI components
- **Backend**: FastAPI (Python) with async support
- **Database**: MongoDB
- **Real-time**: WebSocket for live bidding
- **Payments**: Stripe integration
- **Email**: SendGrid for notifications
- **SMS**: Twilio for verification
- **AI Assistant**: OpenAI GPT-4 via Emergent LLM Key

## Current Status: MASTER DIRECTIVE COMPLETED ✅

### Completed Work (January 2026)

#### 1. Power Bids Feature Purge ✅
- Deleted `/app/frontend/src/components/PowerBidButton.js`
- Removed PowerBidButton imports from:
  - `ListingDetailPage.js`
  - `MultiItemListingDetailPage.js`
- Removed `/api/bids/monster` endpoint from `server.py`
- Removed `monster_bids_used` field from User model
- Cleaned up leftover 'monster' references in toast messages

#### 2. Yearly Billing Migration ✅
- **Premium Tier**: $99.99/year (was $9.99/month)
- **VIP Tier**: $299.99/year (was $29.99/month)
- Added "2 Months Free!" marketing message
- Updated `ProfileSettingsPage.js` subscription table
- Updated `SubscriptionManager.js` admin panel (365-day subscriptions)
- Updated `/api/fees/subscription-benefits` endpoint

#### 3. Tiered Fee Engine (NO CAP) ✅
- **Free Tier**: 4% Seller Commission / 5% Buyer's Premium
- **Premium Tier**: 2.5% Seller / 3.5% Buyer (1.5% reduction)
- **VIP Tier**: 2% Seller / 3% Buyer (2% reduction)
- Updated `services/fee_calculator.py`
- Updated `calculate_buyer_fees()` and `calculate_seller_fees()` in server.py
- Updated `SellerDashboard.js` to display correct commission rates

#### 4. UI/UX Updates ✅
- Added "BEST VALUE" badge on Premium plan header
- Added Seller Tier Badges (`SellerTierBadge.js` component):
  - Premium: Silver/Platinum shield theme
  - VIP: Gold/Diamond crown theme
- Displays on lot detail pages next to seller info
- Updated subscription comparison table with new fee percentages

#### 5. Previous Completed Work
- Critical UI/UX visibility fixes (ghost text issues)
- Seller Obligations flow (creation and display)
- Fee Engine v1 and agreement persistence
- Bilingual Legal pages (T&C, Privacy Policy)
- Cookie consent banner
- Data deletion endpoint (GDPR/PIPEDA)
- Cascaded regional filters

---

## P1 - Upcoming Tasks

### Lot Index Mobile Responsiveness
- Convert sidebar to collapsible drawer on mobile viewports
- Improve buyer experience on smaller devices
- Affects: `MultiItemListingDetailPage.js`

---

## P2 - Future/Backlog Tasks

### RAG AI Indexing Update
- Index AI assistant at individual item level
- Enable specific lot queries

### Disruptor Protocol Features
1. **Seller Trust Score**
   - "BidVex Trusted Seller" badge
   - Historical transaction analysis

2. **Currency Switcher**
   - CAD, USD, EUR support
   - Backend conversion API
   - Frontend header selector

3. **High-Stakes Bidding UI**
   - Pulsing timer in final minutes
   - Visual tension cues

4. **Public Bid History**
   - Tab on lot detail pages
   - Transparency feature

---

## Key API Endpoints

### Fee Calculation
- `GET /api/fees/subscription-benefits` - Public tier info
- `GET /api/fee-calculator` - Calculate fees by tier
- `POST /api/fees/calculate-buyer-cost` - Buyer total
- `POST /api/fees/calculate-seller-net` - Seller payout

### Subscriptions
- `GET /api/subscription/status` - User's current tier

### Removed Endpoints
- `POST /api/bids/monster` - **REMOVED** (Power Bids)

---

## Database Schema Updates

### Users Collection
- Removed: `monster_bids_used: Dict[str, int]`
- Updated subscription fields for yearly billing

### Fee Structure (in multi_item_listings)
```json
{
  "buyer_premium_percentage": 5.0,
  "seller_commission_percentage": 4.0
}
```

---

## Test Credentials
- **Admin**: `charbel@admin.bazario.com` / `Admin123!`
- **Test User 1**: `pioneer@bidvextest.com` (Individual Seller)
- **Test User 2**: `challenger@bidvextest.com` (Business Seller)
- **Password**: `test123`

---

## Tech Stack
- Frontend: React 18, Tailwind CSS, Shadcn/UI
- Backend: FastAPI, Python 3.11
- Database: MongoDB (Motor async driver)
- Auth: JWT tokens
- Payments: Stripe
- Email: SendGrid
- SMS: Twilio
- AI: OpenAI GPT-4 (Emergent LLM Key)

---

## Files Modified in This Session
1. `/app/backend/server.py` - Fee engine, subscription status, removed Power Bids
2. `/app/backend/services/fee_calculator.py` - New percentage-based fees
3. `/app/frontend/src/pages/ProfileSettingsPage.js` - Yearly pricing, fee table
4. `/app/frontend/src/pages/ListingDetailPage.js` - Removed PowerBid import
5. `/app/frontend/src/pages/MultiItemListingDetailPage.js` - Removed PowerBid import, added SellerTierBadge
6. `/app/frontend/src/pages/SellerDashboard.js` - Updated commission display
7. `/app/frontend/src/pages/admin/SubscriptionManager.js` - Yearly revenue calc
8. `/app/frontend/src/components/SellerTierBadge.js` - NEW component
9. `/app/frontend/src/components/PowerBidButton.js` - DELETED

---

*Last Updated: January 9, 2026*
