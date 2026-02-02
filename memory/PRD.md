# BidVex Auction Platform - Product Requirements Document

## Last Updated: February 2, 2026

## Original Problem Statement
Build and maintain a sophisticated full-stack auction platform (BidVex) with:
- Real-time bidding capabilities
- Multi-item and single-item auction listings
- Comprehensive admin panel
- Canadian tax compliance system
- Full bilingual support (EN/FR)

## Architecture
```
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI (Python) 
Database: MongoDB
Authentication: JWT + Emergent Google Auth
AI: OpenAI GPT-4 via emergentintegrations
Payments: Stripe
Email: SendGrid
```

## Current Status: DEPLOYMENT FIX COMPLETE

### Session Summary (Feb 2, 2026)
Fixed critical deployment issues preventing production deployment:

1. **Added root `/health` endpoint** - Required by Emergent deployment health checks
2. **Fixed `decode_token` undefined errors** - 4 occurrences in AI chat endpoints
3. **Removed hardcoded admin email** - Now uses `ADMIN_EMAIL` env var
4. **Set CORS to `*`** - Allows requests from all origins
5. **Removed duplicate hardcoded API key** - `EMERGENT_LLM_KEY` cleanup

### Key Files Modified
- `/app/backend/server.py` - Health endpoint, decode_token fixes, admin email fix
- `/app/backend/.env` - CORS configuration

## Completed Features

### Core Auction System ✅
- Real-time bidding with WebSocket support
- Single-item and multi-item auction listings
- Anti-sniping protection
- Buyer/seller dashboards

### Admin Panel ✅
- User management with search
- Listing management (all auction types)
- Tax verification queue
- Deletion request workflow
- Announcement system
- Banner manager

### Canadian Tax Compliance ✅
- Seller tax onboarding (Individual vs Business)
- Province-aware logic (QC/non-QC)
- NEQ/QST fields for Quebec businesses
- Admin verification system
- Binding seller agreement with audit trail

### Internationalization ✅
- Full EN/FR translation
- Bilingual legal documents
- Language-aware forms

### Monetization ✅
- Google AdSense integrated
- Stripe payments configured

## Environment Configuration

### Backend (.env)
```
MONGO_URL=<mongodb-connection>
DB_NAME=bazario_db
JWT_SECRET=<secret>
CORS_ORIGINS=*
EMERGENT_LLM_KEY=<key>
SENDGRID_API_KEY=<key>
ADMIN_EMAIL=admin@bidvex.com
```

### Frontend (.env)
```
REACT_APP_BACKEND_URL=<emergent-backend-url>
```

## API Endpoints

### Health (Critical for Deployment)
- `GET /health` - Root health check (NEW)
- `GET /api/health` - API health check

### Authentication
- `POST /api/auth/register`
- `POST /api/auth/login`
- `GET /api/auth/google`

### Marketplace
- `GET /api/marketplace/items`
- `GET /api/listings/{id}`
- `POST /api/listings/{id}/bid`

### Admin
- `GET /api/admin/tax/pending`
- `POST /api/admin/tax/{userId}/approve`
- `GET /api/announcements/active`

## Upcoming Tasks (Prioritized)

### P0 - Critical
- [x] Fix deployment health check (DONE)
- [ ] Verify production deployment works

### P1 - High Priority
- Enterprise Vehicle Auction Module
- Advanced Banner Customization

### P2 - Medium Priority
- CRA Tax Reporting Engine (XML generator)
- Refactor server.py into modular routers
- Refactor i18n.js into namespaces

### P3 - Low Priority
- UI for AI Guard Status
- Legal Pages Layout Refresh

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`
- **Test User:** `pioneer@bidvextest.com` / `test123`

## Known Issues
- SendGrid API key is a placeholder (email won't send until configured)
- Google Maps API key is a placeholder

## Database Schema (Key Collections)
- `users` - User accounts with tax_profile, affiliate_code
- `listings` - Single-item auctions with agreement_metadata
- `multi_item_listings` - Multi-item auctions
- `site_config` - Legal pages, announcements, banners
- `ai_chat_history` - Chatbot conversation history
