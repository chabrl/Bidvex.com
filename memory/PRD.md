# BidVex Auction Platform - Product Requirements Document

## Last Updated: February 5, 2026

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

## Current Status: BANNER MANAGER COMPLETE

### Session Summary (Feb 5, 2026)
Implemented fully customizable Hero Banner Manager:

**Backend Changes:**
- Extended banner schema with styling fields (text_color, font_family, title/subtitle font sizes, overlay_color, overlay_opacity)
- Updated create/update endpoints to support all styling fields
- Enhanced /api/banners/active to return styling with defaults

**Frontend Changes:**
- Created new HeroBannerEditor component with:
  - Color pickers for text and overlay
  - Opacity slider (0-100%)
  - Font family dropdown
  - Font size selectors
  - Live preview
  - Image upload support
- Updated HomepageBanner to render dynamic styles

### Key Files Modified
- `/app/backend/server.py` - Banner schema and API endpoints
- `/app/frontend/src/components/admin/HeroBannerEditor.js` - NEW
- `/app/frontend/src/components/HomepageBanner.js` - Dynamic styling
- `/app/frontend/src/pages/admin/BrandingLayoutManager.js` - Integrated editor

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
- [x] Hero Banner Manager with full styling (DONE)
- [ ] Verify production deployment

### P1 - High Priority
- Enterprise Vehicle Auction Module
- Advanced Banner Customization (carousel-specific features)

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
