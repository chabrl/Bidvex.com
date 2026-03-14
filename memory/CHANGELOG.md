# BidVex Changelog

## March 14, 2026 - Bug Fixes: Homepage Translation Keys, Routing & Validation (4 Issues)

### Issue 1: Verify Now Button 404 (FIXED)
- Root cause: Button linked to `/profile/settings?tab=payments` which doesn't exist; correct route is `/settings?tab=payments`
- Fix: Updated navigate call in ListingDetailPage.js

### Issue 2: Rate Seller Missing auction_type (FIXED)
- Root cause: RateSellerModal didn't pass `auction_type` field in payload, backend required it
- Fix: Added `auctionType="single"` prop from ListingDetailPage, default in modal. Added user-friendly error: "You must win at least one item from this seller to leave a rating!" when user hasn't participated. Pydantic error extraction added.

### Issue 3: Homepage Raw Translation Keys (FIXED)
- Root cause: Keys `homepage.hotItems`, `homepage.hotItemsDesc`, `homepage.justListed`, `homepage.freshAuctions`, `homepage.views`, `homepage.new`, `homepage.activeBidding` were referenced in JSX but not defined in i18n.js
- Fix: Added all missing keys to both EN and FR translations. EN: "Trending Now", "Fresh Arrivals", etc. FR: "Tendances", "Nouveautés", etc.

### Issue 4: Homepage Light Mode Polish (FIXED)
- Root cause: HotItemsSection used hardcoded dark gradient via inline `style={{ background: ... }}` — invisible in light mode
- Fix: Replaced with Tailwind `bg-gradient-to-br from-slate-50 via-white to-blue-50 dark:bg-none` + `hidden dark:block` for dark-mode-only gradient overlay. Cards use `bg-white dark:bg-white/5` for proper theming.

### Testing
- Backend: 10/10 tests passed (100%) — iteration_47
- Frontend: All 14 features verified (100%)

---

## March 14, 2026 - Bug Fixes: 6 Marketplace & Partner Page Issues

### Issue 1: React "Objects are not valid as a Child" Error (FIXED)
- Root cause: `confirmBid` in FlattenedMarketplace.js, `handleBid` in VehicleDetailPage.js, and `placeBid` in VehicleAuctionContext.js all passed `error.response.data.detail` directly to toast — when it was a Pydantic validation error array `[{type,loc,msg,input,url}]`, React crashed trying to render the object.
- Fix: All three catch blocks now extract `.msg` string from validation error objects before rendering.

### Issue 2: Marketplace Card Layout Overflow (FIXED)
- Root cause: Card used `space-y-3` with no flex structure, so buttons at bottom could overflow on narrow cards.
- Fix: Card uses `flex flex-col` with `flex-1` spacer to push pricing/actions to bottom. Buttons use `h-9 text-sm` for consistent sizing. Grid reduced to `lg:grid-cols-3` (from `xl:grid-cols-4`) when sidebar is present.

### Issue 3: "Become a Partner" Light Mode Theming (FIXED)
- Root cause: Page was hardcoded with `bg-slate-950` dark background, making it unreadable in light mode.
- Fix: Full rewrite with `bg-white dark:bg-slate-950` + semantic dark/light classes. Benefit cards now use colored borders (`border-emerald-200 dark:border-emerald-500/20`) and light backgrounds (`bg-emerald-50 dark:bg-gradient-to-br`).

### Issue 4: Item Routing Correction (FIXED)
- Root cause: All items linked to `/lots/${item.auction_id}`. Standalone listings (no parent auction) have `auction_id=null`, routing to `/lots/null` (404).
- Fix: Smart routing: `detailLink = item.auction_id ? /lots/${item.auction_id} : /listing/${item.id}`. "Lot #X" parent link only renders when both `auction_id` AND `lot_number` exist.

### Issue 5: Seller Badge Logic (FIXED)
- Root cause: No check for `is_partner_listing` in ItemCard component.
- Fix: Added purple "Verified Partner" badge (`<Badge data-testid="partner-badge">`) when `item.is_partner_listing` is true. Badge stacks vertically with Private Sale/Business badge.

### Issue 6: General Polish (VERIFIED)
- Removed duplicate MarketplaceSidebar rendering in MarketplacePage.js
- Fixed skeleton loader grid to match 3-column layout
- Cleaned up inline styles, replaced with semantic Tailwind dark/light classes
- Card content uses `flex-col flex-1` for consistent bottom-aligned actions

### Testing
- Backend: 9/9 tests passed (100%) — iteration_46
- Frontend: All 6 issues verified (100%)

---

## March 14, 2026 - P1: Email Settings Panel & CSV Export

### Email Settings Admin Panel
- New self-service panel at Admin > Partners & Finance > Email Settings
- SendGrid API key stored in MongoDB `settings` collection with `key: "sendgrid"`
- Status banner shows Connected/Inactive with key source (database/environment)
- API key field with masked display (SG.xx...xxxx), show/hide toggle
- Sender Email and Sender Name configurable
- "Send Test Email" button with recipient input — sends branded verification email
- "Automated Partner Emails" section shows status of 3 triggers: Application Received, Verified, Rejected
- Last test timestamp and pass/fail status displayed

### CSV Transaction Export
- New "Export CSV" button in Transaction Logs tab (next to "Partner Only" filter)
- Downloads all transactions matching current filters (search + partner_only)
- CSV columns: Date, Item, Buyer/Seller Email, Type, Hammer Price, BP, Platform Fee, Processing Fee, Payout, Stripe ID, Partner Company
- Auth-protected download via fetch + blob approach

### DB-Stored SendGrid Configuration
- `_get_sendgrid_config()` async helper checks DB first, then env var fallback
- `_send_partner_email()` updated to use DB-stored key
- Partner application email onboarding (Task 5) now uses `_get_sendgrid_config()` 
- Once admin saves a valid key via the panel, all partner emails auto-activate

### Backend Endpoints Added
- `GET /api/admin/email-settings` — Returns config status with masked key
- `POST /api/admin/email-settings` — Validates SG. prefix, upserts to settings collection
- `POST /api/admin/email-settings/test` — Sends test email, records last_test_at/status
- `GET /api/admin/finance/transactions/export` — CSV export with filters

### Testing
- Backend: 20/20 tests passed (100%) — iteration_45
- Frontend: All UI verified (100%)
- Test file: `/app/backend/tests/test_email_settings_csv_export.py`

---

## March 14, 2026 - Phase 2 Finalization: Admin Command Center & Marketplace Sidebar

### Task 4a: Marketplace Sidebar Filter Integration (LotsMarketplacePage)
- Integrated `MarketplaceSidebar` component into `/lots` (LotsMarketplacePage) with two-column layout
- Replaced 800+ lines of inline filters with reusable sidebar (Auctioneer, Category, Location sections)
- Wired sidebar filter state to `/api/multi-item-listings` API calls
- Added `city` and `seller_id` query params to backend multi-item-listings endpoint
- Grid/List view toggle preserved, market stats bar streamlined
- Sidebar fetches dynamic counts from `/api/marketplace/filter-counts` (60s cache TTL)

### Task 4b: Admin Finance Dashboard Enhancement
- Redesigned `FinanceDashboard.js` with **"Collected Fees (Your Revenue)"** as the #1 hero card
- Clear fee breakdown: 3% Platform Fee vs Stripe Cost Recovery (2.9%+$0.30) vs Subscription Revenue
- Secondary cards: Hammer Volume, Buyer Premiums, Transactions, Active Auctions
- Partner Revenue Breakdown section with 3% Fees from Partners, Buyer Premiums (Partner), Partner Transactions
- User & Auction quick stats: Total, Partners, Pending
- Three sub-tabs: Revenue Overview, Partner Accounts, Transaction Logs
- Partner Accounts: filter by All/Pending/Verified/Rejected, review dialog, toggle/pause/delete actions
- Transaction Logs: searchable, paginated, Partner Only filter, fee split columns

### Testing
- Backend: 19/19 tests passed (100%) — iteration_44
- Frontend: All UI verified (100%)
- Test file: `/app/backend/tests/test_phase2_marketplace_finance.py`

---

## March 14, 2026 - Phase 2: Stripe Migration, Partner UX & Checkout UI

### Task 1: Stripe Connect Destination Charges
- Added `calculate_partner_listing_checkout()` to `stripe_connect_service.py`
- Partner fund routing: `transfer_data[destination]` sends Hammer + BP to connected account
- Application fee: 3% platform fee + Stripe recovery collected by BidVex
- Updated `payments.py` checkout and preview endpoints to detect `is_partner_listing`
- Standard routing (4% seller + 5% buyer + Stripe recovery) preserved for non-partner listings

### Task 2: Partner Page UX Refinement
- Redesigned `/become-a-partner` with professional dark hero, gradient text, dual CTAs
- 4 benefit cards: "Fixed 3% Platform Fee", "Set Your Own Buyer Premium", "Verified Auction Firm Badge", "Direct Stripe Connect Payouts"
- ROI section: "$50,000 liquidation sale → $1,500 BidVex fee vs $4,000-$7,500 elsewhere"
- Removed fee comparison table as requested
- Fully responsive, dark theme consistent

### Task 3: Checkout UI Itemization
- CheckoutPage detects `isPartnerListing` and `partnerCompany` from preview API
- Displays: Hammer Price, Buyer's Premium (custom%), Platform Fee (3% partner / 2.5% vehicle), Secure Processing Fee (2.9% + $0.30), Total
- "Secure Processing Fee" label with "Credit card processing cost — transparent, no markup" description
- Partner company badge with Shield icon shown on partner listing checkouts

### Task 5: Email Onboarding (Ready to Activate)
- Applicant auto-reply: "Thank you... reviewing NEQ... 24-48 hours"
- Internal alert to `partners@bidvex.ca` with application details + document links
- Implemented with SendGrid — placeholder keys, activates when live keys provided

### Testing
- Backend: 13/13 tests passed (100%) — iteration_43
- Frontend: All UI verified (100%)
- Test file: `/app/backend/tests/test_phase2_partner_system.py`

## March 13, 2026 - Billing Finalization & UI Verification

### Verified & Completed
- **Price Breakdown Endpoint**: `GET /api/subscriptions/price-breakdown` correctly calculates:
  - Premium: $180 subtotal + $9.00 GST + $17.96 QST + $6.49 processing fee = $213.45
  - VIP: $300 subtotal + $15.00 GST + $29.93 QST + $10.61 processing fee = $355.54
- **Stripe Fee-on-Top**: Processing fee (2.9% + $0.30) calculated server-side, added to total charge, displayed in invoices
- **Branded PDF Invoices**: Logo, address (103-761 Chalifoux Street, Sherbrooke, QC, J1G 0A8), tax numbers (GST/HSN #706766367RT0001, QST #1233530880TQ0001)
- **Settings Page UI Overhaul**: Glassmorphism aesthetic, responsive tabs, Trust Status card
- **Price Breakdown Display**: Added interactive toggle on Premium/VIP cards showing GST, QST, processing fee, total
- **Badge Overlap Fix**: "BEST VALUE" and "CURRENT PLAN" badges are now mutually exclusive
- **Vehicle Invoice Template Updated**: `pdf_invoice.py` updated with correct official address and tax numbers

### Testing
- Backend: 9/9 tests passed (100%)
- Frontend: All UI features verified (100%)
- Test report: `/app/test_reports/iteration_40.json`
- Test file: `/app/backend/tests/test_price_breakdown_invoice.py`

---

## March 12, 2026 - Subscription Lifecycle & Live Stripe

### Completed
- Live Stripe subscription flow (create, cancel, reactivate)
- PDF invoice generation with tax breakdown
- Subscription management panel (SubscriptionManagement.js)
- TrendySubscriptionCards with dynamic pricing from API
- Invoice list and download endpoints

---

## Earlier Sessions - See PRD.md for full history
