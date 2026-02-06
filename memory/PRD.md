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
Payments: Stripe (via emergentintegrations)
Email: SendGrid
Background Jobs: APScheduler
```

## Current Status: ✅ VEHICLE AUCTION MODULE COMPLETE (ALL PHASES + FINANCIAL ENGINE + AUTOMATION + CRA TAX REPORTING)

### Session Summary (Feb 6, 2026)
Implemented CRA Tax Reporting Engine, PDF Invoice Generation, Email Notifications, and started Auth router refactoring:

**Phase 8 - CRA Tax Reporting & Compliance: ✅ (NEW - Feb 6, 2026)**
- CRA Tax Reporting Engine:
  - GST/HST Summary Report (GST34-compatible) with provincial breakdown
  - Quebec QST Report for Revenu Québec filing
  - Annual Summary with monthly breakdown and all tax types
  - Seller Payments Report (T5018-style) for payments >= $500
  - XML download with proper CRA-compliant format
  - Business Number, GST, QST registration numbers in all reports
- PDF Invoice Generation:
  - Professional BidVex branded invoices using reportlab
  - Complete line items with tax breakdown
  - Business Number (BN) and GST/HST registration fields (legal requirement)
  - Subscription savings display
  - Payment status and deadline
  - Seller settlement statement PDFs
- Email Notifications (SendGrid):
  - Document approval/rejection emails
  - Seller account approval emails
  - Invoice generated emails
  - Auction won/sold notifications
  - Payment confirmation emails
  - Note: SendGrid key is placeholder - emails logged but not sent
- Auth Router Modularization:
  - Created `/app/backend/routes/auth.py` (ready for integration)
  - Separated auth logic for better maintainability

### Session Summary (Feb 5, 2026)
Implemented complete Enterprise Vehicle Auction Module (Phase 1-7):

**Phase 1 - Database & Core APIs: ✅**
- Created standalone vehicle data models with full VIN validation
- Integrated NHTSA VIN Decoder API (real, not mocked)
- Vehicle listing schema with 30+ structured fields
- Condition report system (mechanical, exterior, interior)
- Media management (min 10 photos required)

**Phase 2 - Seller System: ✅**
- Seller types: Private (1/month limit), Dealer (500/month), Auctioneer (500/month)
- Document upload for verification
- Admin approval workflow with audit logging
- Seller badges (Licensed Dealer, Verified Auctioneer, Private Seller)
- Monthly limit enforcement at backend level

**Phase 3 - Vehicle Listing Flow: ✅**
- Multi-step vehicle submission form (6 steps)
- VIN auto-decode with NHTSA API
- Mandatory 10+ photo upload with categories
- Condition report builder
- Auction settings (pricing, timing, visibility)

**Phase 4 - Bidding Engine: ✅**
- Real-time WebSocket bidding (useVehicleBidding hook)
- Anti-sniping (auto time extension in last 2 minutes)
- Tiered bid increments
- Refundable deposit system
- Reserve price logic

**Phase 5 - Frontend UI: ✅**
- Professional automotive-inspired design
- Vehicle Auctions browse page (/vehicle-auctions)
- Vehicle Detail page with live bidding panel
- Create Vehicle Listing multi-step form
- Seller Registration with type selection
- My Listings dashboard with stats

**Phase 6 - Financial Engine: ✅**
- Complete BidVex Fee Structure:
  - Seller Commission: 4% (Basic), 2.5% (Premium), 2% (VIP Elite)
  - Buyer Premium: 5% (Basic), 3.5% (Premium), 3% (VIP Elite)
  - Platform Fee: 2.5%
- Canadian Provincial Tax Engine:
  - HST: ON 13%, NS/NB/NL/PEI 15%
  - GST+PST: BC 5%+7%, SK 5%+6%, MB 5%+7%
  - GST+QST: QC 5%+9.975%
  - GST Only: AB, YT, NT, NU 5%
- Invoice Generation System:
  - Buyer invoices with full line items
  - Seller settlement documents
  - 14-day payment deadline
  - 2% monthly late penalty

**Phase 7 - Stripe Payments, Scheduler & Document Upload: ✅ (NEW - Feb 5, 2026)**
- Stripe Payment Integration:
  - Invoice checkout (POST /api/vehicle-payments/invoice/{id}/checkout)
  - Deposit checkout (POST /api/vehicle-payments/deposit/{id}/checkout)
  - Payment status polling
  - Webhook handling
- Automated Scheduler (6 Jobs):
  - process_ended_auctions (every minute)
  - activate_scheduled_auctions (every minute)
  - apply_late_penalties (daily at 00:05)
  - cleanup_expired_deposits (hourly)
  - cleanup_expired_sessions (hourly)
  - daily_summary (daily at 23:55)
- Seller Document Upload System:
  - Document types: identity_front, identity_back, business_registration, dealer_license, etc.
  - File validation (PDF, JPG, PNG, WEBP, max 10MB)
  - Secure storage in /app/uploads/seller_documents/
  - Admin review workflow with approve/reject
  - Automatic verification status updates
- Auction End Handler:
  - Automatic winner determination
  - Invoice generation on auction close
  - Deposit credit application
  - Reserve price enforcement
- Financial UI:
  - `/vehicle-auctions/invoices` - Invoice management
  - `/vehicle-auctions/seller/financials` - Seller dashboard
  - PricingEstimate component in bid panel

**Phase 4 - Bidding Engine: ✅**
- Real-time WebSocket bidding (useVehicleBidding hook)
- Anti-sniping (auto time extension in last 2 minutes)
- Tiered bid increments
- Refundable deposit system
- Reserve price logic

**Phase 5 - Frontend UI: ✅**
- Professional automotive-inspired design
- Vehicle Auctions browse page (/vehicle-auctions)
- Vehicle Detail page with live bidding panel
- Create Vehicle Listing multi-step form
- Seller Registration with type selection
- My Listings dashboard with stats

**Backend Files Created:**
- `/app/backend/models/vehicle_models.py` - Pydantic models & enums (400+ lines)
- `/app/backend/services/vin_decoder.py` - NHTSA API integration
- `/app/backend/services/vehicle_pricing.py` - Fee & tax calculation engine
- `/app/backend/services/vehicle_invoice.py` - Invoice generation service
- `/app/backend/services/vehicle_auction_handler.py` - Auction end handler
- `/app/backend/services/vehicle_payment.py` - Stripe payment integration
- `/app/backend/services/seller_documents.py` - Document upload service
- `/app/backend/services/scheduler.py` - Background job scheduler
- `/app/backend/services/cra_tax_reporting.py` - CRA tax XML report generator (NEW)
- `/app/backend/services/pdf_invoice.py` - PDF invoice generation (NEW)
- `/app/backend/services/email_notifications.py` - SendGrid email templates (NEW)
- `/app/backend/routes/vehicles.py` - Full API router (70+ endpoints)
- `/app/backend/routes/auth.py` - Auth routes (modular) (NEW)

**Frontend Files Created:**
- `/app/frontend/src/pages/vehicles/VehicleAuctionsPage.js` - Browse page
- `/app/frontend/src/pages/vehicles/VehicleDetailPage.js` - Detail with bidding
- `/app/frontend/src/pages/vehicles/CreateVehicleListingPage.js` - Multi-step form
- `/app/frontend/src/pages/vehicles/SellerRegistrationPage.js` - Seller onboarding + documents
- `/app/frontend/src/pages/vehicles/MyVehicleListingsPage.js` - Seller dashboard
- `/app/frontend/src/pages/vehicles/VehicleInvoicesPage.js` - Invoice management
- `/app/frontend/src/pages/vehicles/SellerFinancialsPage.js` - Seller financials
- `/app/frontend/src/components/vehicles/PricingBreakdown.js` - Pricing components
- `/app/frontend/src/components/vehicles/SellerDocumentManager.js` - Document upload UI (NEW)
- `/app/frontend/src/contexts/VehicleAuctionContext.js` - State management
- `/app/frontend/src/hooks/useVehicleBidding.js` - WebSocket hook

**Database Collections:**
- `vehicle_sellers` - Seller profiles & verification
- `vehicle_listings` - Vehicle auctions (separate from marketplace)
- `vehicle_bids` - Bidding records
- `vehicle_bid_deposits` - Refundable deposits
- `vehicle_invoices` - Buyer invoices & seller settlements
- `seller_documents` - Uploaded verification documents (NEW)
- `payment_transactions` - Stripe payment tracking (NEW)
- `scheduler_logs` - Background job execution logs (NEW)
- `vehicle_legal_acceptances` - Terms acceptance audit
- `vehicle_audit_logs` - Full admin audit trail
- `vehicle_bid_deposits` - Refundable deposits
- `vehicle_invoices` - Buyer invoices & seller settlements (NEW)
- `vehicle_legal_acceptances` - Terms acceptance audit
- `vehicle_audit_logs` - Full admin audit trail

**Test Results:** 100% pass rate (27/27 backend tests, all frontend pages verified)

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

### P0 - Critical
- [x] Vehicle Auction Module Phase 1: Database & APIs ✅
- [x] Vehicle Auction Module Phase 2: Seller System ✅
- [x] Vehicle Auction Module Phase 3: Vehicle Listing Flow ✅
- [x] Vehicle Auction Module Phase 4: Auction & Bidding Engine ✅
- [x] Vehicle Auction Module Phase 5: Frontend UI ✅
- [x] Admin Dashboard Vehicle Integration ✅
- [x] Vehicle Make Filter ✅

### P1 - High Priority
- [ ] Verify production deployment at www.bidvex.com
- [ ] Hero Banner Title Color (verified in preview)

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
