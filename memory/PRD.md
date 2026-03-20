# BidVex Auction Platform - Product Requirements Document

## Last Updated: March 20, 2026

## Original Problem Statement
Build and maintain a sophisticated full-stack auction platform (BidVex) with real-time bidding, multi-item auctions, partner accounts, Stripe Connect payments, admin dashboard, AI chatbot, Canadian tax compliance, and full bilingual support (EN/FR).

## Architecture
```
Frontend: React + TailwindCSS + Shadcn/UI
Backend: FastAPI (Python) — Modular route architecture
Database: MongoDB Atlas (Cloud)
Auth: JWT + Emergent Google Auth
AI: Claude Sonnet 4.5 via emergentintegrations
Payments: Stripe Connect + Subscriptions + Partner Fee + Customer Portal
Email: SendGrid (54 verified dynamic templates, bilingual EN/FR)
Jobs: APScheduler | i18n: react-i18next | PDF: ReportLab
Charts: recharts
```

## Backend Route Architecture
```
/app/backend/
├── server.py              (~9,162 lines)
├── models/ (auction_models.py, message_models.py)
├── routes/ (auth, admin, auctions, listings, marketplace, messages, payments, webhooks, dashboard, profiles, tax, tax_reports, ai_chat, fees, notifications, watchlist, team, vehicles, tax_dashboard)
├── config/email_templates.py | deps.py
├── scripts/normalize_locations.py
└── services/ (tax_engine, vehicle_pricing, vehicle_invoice, email_*, cloud_storage, subscription)
```

## Completed Phases

### Core Platform (P0)
- Vehicle Auction | Stripe Subscriptions | PDF Invoices | Partner System | Admin | Marketplace | AI Chatbot

### Refactoring Phases 1-10 (~1,893 lines extracted from server.py)

### Phase 8-10 (Completed Mar 19, 2026)
- Tax Logic Modularization | Listing-Level Buyer's Premium | Messaging Extraction + CRA Mount

### Phase A: Unified Location Architecture (Completed Mar 20, 2026)
- LocationSelector.js: Hierarchical combobox (Country > Province > City > Postal Code)
- locations.json: CA (13 provinces, 200+ cities) + US (50 states, 15-20 cities each)
- Integrated into 3 sell flows, backend models updated (country, postal_code fields)
- DB migration: "Quebec" > "QC", added country: "CA" | Tests: iteration_64 (6/6)

### Phase B: Mobile-First UX & Geo Pre-filling (Completed Mar 20, 2026)
- Vertical stacking on mobile, 48px touch targets, full-width buttons, inputMode="decimal"
- Responsive steppers, 2-col image grids on mobile, responsive upload method buttons
- useGeoLocation hook (ip-api.com, sessionStorage cache) | Tests: iteration_65 (100%)

### Phase C: Full EN/FR-QC Multilingual Refactor (Completed Mar 20, 2026)
- createListing namespace: ~100 translation keys in EN/FR-QC
- locationSelector namespace: 20 keys with dynamic labels
- vehicleListing namespace: 80+ keys for vehicle form
- Zero raw i18n keys in any sell flow | Tests: iteration_66 (100%)

### Smart Localized Currency Formatting (Completed Mar 20, 2026)
- Created `/app/frontend/src/utils/currencyFormatter.js` with `formatCurrency`, `formatCurrencyCompact`, `formatPercent`
- Uses `Intl.NumberFormat` with i18n-aware locale detection (EN: `$1,250.50` | FR-QC: `1 250,50 $`)
- Applied across 25+ files: HomePage, BuyerDashboard, SellerDashboard, WatchlistPage, CheckoutPage, MessagesPage, PaymentSuccessPage, AffiliateDashboard, SellerProfilePage, EmailMarketingPricing, SubscriptionPricingPage
- Components: RealtimeBiddingPanel, AuctionCarousel, AutoBidModal, DecomposedMarketplace, BidConfirmationDialog, SubscriptionManagement, BuyNowButton, FlattenedMarketplace
- Admin pages: CouponManager, MarketplaceSettings, AffiliateManager, ManageAllAuctions, AnalyticsDashboard, VehicleAdminManager, PricingManager, SubscriptionAnalytics
- Hooks: useRealtimeBidding
- Replaced all local `formatCurrency`/`formatPrice` functions with shared utility
- Tests: iteration_67 (100% backend + frontend)

### Admin Tax Dashboard (Completed Mar 20, 2026)
- Backend: `/app/backend/routes/tax_dashboard.py` with MongoDB aggregation pipeline
  - `GET /api/admin/tax-dashboard/summary` - Aggregated tax data with period filtering
  - `GET /api/admin/tax-dashboard/export-csv` - CSV export for accountants
- Frontend: `/app/frontend/src/pages/AdminTaxDashboard.js`
  - Hero stat cards (GST, QST, HST, Total Tax Liability)
  - Period filter (Current Quarter, Last Quarter, All Time, Custom Range)
  - Tax Type Distribution pie chart (recharts)
  - Tax Revenue by Province bar chart (recharts)
  - Net Cash vs Tax Reserve comparison with progress bar
  - CSV export button
  - Graceful empty state handling
- Route: `/admin/tax-dashboard` (admin-only access)
- Tests: iteration_67 (100% - 10/10 backend, all frontend elements verified)

## Key DB Schema Changes
- listings: `country: Optional[str] = "CA"`, `postal_code: Optional[str] = None` added
- multi_item_listings: Same additions
- `region` field now stores ISO codes ("QC", "ON") after migration
- transactions collection: Used for tax aggregation (commission_amount, buyer_premium_amount, seller_region)

## Key API Endpoints
- `POST /api/listings` (accepts country, postal_code, buyers_premium_rate)
- `PUT /api/listings/{id}` (allows country, postal_code)
- `POST /api/multi-item-listings`
- `GET /api/admin/tax-dashboard/summary` (period, start_date, end_date params)
- `GET /api/admin/tax-dashboard/export-csv` (period, start_date, end_date params)
- Standard auth, auction, marketplace, payment, messaging endpoints

## Test Credentials
- **Admin:** `charbeladmin@bidvex.com` / `Admin123!`

## Test Reports
- iteration_64 — Phase A Location Architecture (100%)
- iteration_65 — Phase B Mobile Responsiveness (100%)
- iteration_66 — Phase C i18n Multilingual (100%)
- iteration_67 — Currency Formatting + Tax Dashboard (100%)
- iteration_68 — Full Responsive Design Fix (100%)
- iteration_69 — Performance Engineering P0+P1 (100%)

### Full Responsive Design Overhaul (Completed Mar 20, 2026)
- **Navbar**: Rewrote to use `lg` breakpoint (1024px) for desktop nav, preventing tablet overflow. Hamburger menu below lg. Mobile: hides theme toggle & messages (accessible in user dropdown). Consistent `max-w-7xl mx-auto px-3 sm:px-4 lg:px-8`.
- **MobileBottomNav**: Changed from `md:hidden` to `lg:hidden` to match navbar. Scaled icon/text sizes for mobile.
- **HomePage**: All grids updated with `sm:grid-cols-2` for tablet. Section padding `px-4 sm:px-6 lg:px-8`. Typography scales `text-2xl sm:text-3xl lg:text-4xl`. Card image heights scale `h-40 sm:h-48`.
- **HeroBanner**: Min-height scales `min-h-[480px] sm:min-h-[560px] lg:min-h-[700px]`. Heading scales `text-3xl sm:text-5xl lg:text-7xl`. CTA buttons `w-full sm:w-auto`. Search bar input scales.
- **AIAssistant**: Chat button `bottom-20 right-4 sm:bottom-24 sm:right-6 lg:bottom-8 lg:right-8`. Chat window responsive width.
- **Global CSS**: Added `overflow-x: hidden` on html element.
- **Active Bidding Label**: Fixed visibility with dedicated `.active-bidding-label` CSS class overriding card span `!important` rule.
- Tests: iteration_68 (100% - all 4 breakpoints verified, no horizontal overflow)

### Performance Engineering Overhaul (Completed Mar 20, 2026)
**P0 — Implemented:**
- **Code Splitting**: All 40+ page imports converted to `React.lazy()` + `Suspense` with branded `PageLoader` fallback. Heavy components (AIAssistant) also lazy-loaded. Eliminates monolithic initial bundle.
- **GZip Compression**: `GZipMiddleware` added to FastAPI (minimum_size=500, compresslevel=5). Compresses all API JSON responses > 500 bytes. K8s ingress also provides transport-level compression.
- **API Response Caching**: TTL-based in-memory cache (`/app/backend/services/api_cache.py`):
  - `/api/categories` → TTL 300s
  - `/api/carousel/new-listings` → TTL 60s
  - `/api/carousel/recently-sold` → TTL 60s
  - `/api/stats/top-sellers` → TTL 60s
  - Auto-invalidation on listing create/update via `invalidate_listing_caches()`
- **MongoDB Indexes**: 15+ new compound indexes on listings, users, transactions, notifications, messages, multi_item_listings. Critical indexes: `(status, created_at)`, `(status, category)`, `(status, auction_end_date)`, `(email, unique)`, `(user_id, is_read, created_at)`.
- **Image Optimization**: Global `content-visibility: auto` on all images. `OptimizedImage` component with native lazy loading, WebP hints, fade-in.

**P1 — Implemented:**
- **Critical CSS Skeleton**: Inline HTML/CSS in `index.html` renders instantly — navbar skeleton + hero skeleton + shimmer animation. Eliminates blank white screen.
- **Debounced Search**: 300ms debounce on search inputs in `FlattenedMarketplace` and `DecomposedMarketplace`. Prevents API call spam.
- **SEO**: `react-helmet-async` with `SEO.js` component, `HelmetProvider` in App. HomePage has JSON-LD WebSite schema. `robots.txt` and `sitemap.xml` in public folder.
- **Cache-Control**: Removed anti-caching meta tags from index.html. CRA hash-based filenames handle cache busting.

**P2 — Documented (Infrastructure):**
- Cloudflare CDN setup guide → `/app/memory/INFRASTRUCTURE_P2.md`
- React Query migration plan (2-3 day effort) → `/app/memory/INFRASTRUCTURE_P2.md`
- Cursor pagination spec for `/api/listings` → `/app/memory/INFRASTRUCTURE_P2.md`
- Tests: iteration_69 (100% - all features verified, no regressions)

## Upcoming Tasks

### P1 - Medium Priority
- [ ] Continue refactoring server.py: Extract affiliates, categories, remaining admin modules
- [ ] Premium Comparison view in marketplace
- [ ] Auto-detect user's province for faster location selection
- [ ] Allow sellers to save location profiles

### P2 - Low Priority
- [ ] Partner Pro subscription tier
- [ ] Swap local PDF invoice storage mock with real cloud service (S3/GCS)
- [ ] Expand email template test coverage
- [ ] Minor UI: Floating chat button overflow on 390px mobile

## Mocked Services
- Cloud storage for PDF invoices -> local directory `/data/invoices/` with HMAC-signed URLs
