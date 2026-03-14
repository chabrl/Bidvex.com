# BidVex Changelog

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
