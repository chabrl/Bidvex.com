# BidVex Auction Platform - Product Requirements Document

## Last Updated: February 5, 2026

## Original Problem Statement
Build and maintain a sophisticated full-stack auction platform (BidVex) with:
- Real-time bidding capabilities
- Multi-item and single-item auction listings
- Comprehensive admin panel
- Canadian tax compliance system
- Full bilingual support (EN/FR)
- **Enterprise Vehicle Auction Module** (standalone, Copart/IAA quality)

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

## Current Status: VEHICLE AUCTION MODULE PHASE 1-2 COMPLETE

### Session Summary (Feb 5, 2026)
Implemented Enterprise Vehicle Auction Module (Phase 1 & 2):

**Phase 1 - Database & Core APIs:**
- Created standalone vehicle data models with full VIN validation
- Integrated NHTSA VIN Decoder API (real, not mocked)
- Vehicle listing schema with 30+ structured fields
- Condition report system (mechanical, exterior, interior)
- Media management (min 10 photos required)

**Phase 2 - Seller System:**
- Seller types: Private (1/month limit), Dealer (500/month), Auctioneer (500/month)
- Document upload for verification
- Admin approval workflow with audit logging
- Seller badges (Licensed Dealer, Verified Auctioneer, Private Seller)
- Monthly limit enforcement at backend level

**New Files Created:**
- `/app/backend/models/vehicle_models.py` - Pydantic models & enums
- `/app/backend/services/vin_decoder.py` - NHTSA API integration
- `/app/backend/routes/vehicles.py` - Full API router (45+ endpoints)

**Database Collections:**
- `vehicle_sellers` - Seller profiles & verification
- `vehicle_listings` - Vehicle auctions (separate from marketplace)
- `vehicle_bids` - Bidding records
- `vehicle_bid_deposits` - Refundable deposits
- `vehicle_legal_acceptances` - Terms acceptance audit
- `vehicle_audit_logs` - Full admin audit trail

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
- **Banner Manager with full styling control** (NEW)

### Canadian Tax Compliance ✅
- Seller tax onboarding (Individual vs Business)
- Province-aware logic (QC/non-QC)
- Admin verification system
- Binding seller agreement with audit trail

### Internationalization ✅
- Full EN/FR translation
- Bilingual legal documents

### Monetization ✅
- Google AdSense integrated
- Stripe payments configured

## Banner Schema (Extended)
```json
{
  "id": "uuid",
  "title": "string",
  "subtitle": "string",
  "image_desktop": "url/base64",
  "image_mobile": "url/base64",
  "cta_text": "string",
  "cta_link": "string",
  "text_color": "#FFFFFF",
  "font_family": "Inter",
  "title_font_size": "48px",
  "subtitle_font_size": "18px",
  "overlay_color": "#000000",
  "overlay_opacity": 0.4,
  "active": true,
  "order": 0,
  "created_at": "datetime",
  "updated_at": "datetime"
}
```

## API Endpoints

### Banners
- `GET /api/banners/active` - Public, returns active banners with styling
- `GET /api/admin/hero-banners` - Admin, get all banners
- `POST /api/admin/hero-banners` - Admin, create banner
- `PUT /api/admin/hero-banners/{id}` - Admin, update banner
- `DELETE /api/admin/hero-banners/{id}` - Admin, delete banner

### Health
- `GET /health` - Root health check
- `GET /api/health` - API health check

## Upcoming Tasks (Prioritized)

### P0 - Critical (In Progress)
- [x] Vehicle Auction Module Phase 1: Database & APIs (DONE)
- [x] Vehicle Auction Module Phase 2: Seller System (DONE)
- [ ] Vehicle Auction Module Phase 3: Vehicle Listing Flow (frontend)
- [ ] Vehicle Auction Module Phase 4: Auction & Bidding Engine
- [ ] Vehicle Auction Module Phase 5: Frontend UI

### P1 - High Priority
- [ ] Hero Banner Title Color fix (verified working)
- [ ] Verify production deployment

### P2 - Medium Priority
- [ ] CRA Tax Reporting Engine (XML generator)
- [ ] Refactor server.py into modular routers
- [ ] Refactor i18n.js into namespaces

### P3 - Low Priority
- [ ] UI for AI Guard Status
- [ ] Legal Pages Layout Refresh

## Vehicle Auction API Endpoints (NEW)

### VIN Decoder
- `GET /api/vehicles/decode-vin/{vin}` - Decode VIN using NHTSA API

### Vehicle Sellers
- `POST /api/vehicle-sellers/register` - Register as vehicle seller
- `GET /api/vehicle-sellers/me` - Get own seller profile
- `POST /api/vehicle-sellers/documents` - Upload verification documents
- `GET /api/vehicle-sellers/{id}/public` - Public seller profile with badges

### Vehicle Listings
- `POST /api/vehicles` - Create vehicle listing
- `POST /api/vehicles/{id}/media` - Upload photos/videos
- `POST /api/vehicles/{id}/submit` - Submit for approval
- `GET /api/vehicles` - List public vehicle auctions
- `GET /api/vehicles/{id}` - Get vehicle detail
- `GET /api/vehicles/my/listings` - Seller's own listings

### Bidding
- `POST /api/vehicle-bids` - Place bid
- `POST /api/vehicle-bids/deposit` - Pay bid deposit
- `GET /api/vehicle-bids/my` - User's bid history
- `POST /api/vehicles/{id}/accept-terms` - Accept legal terms

### Admin
- `GET /api/vehicle-admin/pending-sellers` - Pending seller verifications
- `POST /api/vehicle-admin/sellers/{id}/approve` - Approve seller
- `POST /api/vehicle-admin/sellers/{id}/reject` - Reject seller
- `GET /api/vehicle-admin/pending-vehicles` - Pending vehicle approvals
- `POST /api/vehicle-admin/vehicles/{id}/approve` - Approve vehicle
- `POST /api/vehicle-admin/vehicles/{id}/reject` - Reject vehicle
- `POST /api/vehicle-admin/vehicles/{id}/cancel` - Cancel auction
- `POST /api/vehicle-admin/bids/{id}/remove` - Remove bid (with audit)
- `GET /api/vehicle-admin/audit-logs` - Get audit logs

### WebSocket
- `WS /api/ws/vehicle/{id}` - Live auction updates

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`
- **Test User:** `pioneer@bidvextest.com` / `test123`

## Known Issues
- SendGrid API key is a placeholder (email won't send until configured)
- Google Maps API key is a placeholder
