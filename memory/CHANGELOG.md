# BidVex Changelog

## March 14, 2026 - Partner Account System Phase 1

### Implemented
- **User Model**: Added `is_partner`, `partner_verification_status`, `partner_company_name`, `partner_neq`, `partner_certifications`, `partner_neq_document`, `partner_applied_at`, `partner_verified_at`, `custom_premium_rate` fields
- **Listing Model**: Added `custom_buyer_premium_rate`, `is_partner_listing` fields
- **Fee Engine**: Net-Zero Stripe fee recovery formula + fee constants (5% buyer, 4% seller, 3% partner)
- **Partner Application**: `POST /api/partner/apply` with mandatory file uploads (NEQ proof + certifications)
- **Admin Management**: `GET /api/admin/partners`, `POST /verify`, `POST /reject`, `PUT /premium-rate`
- **Fee Preview**: `GET /api/partner/fee-preview`, `GET /api/checkout/fee-breakdown`
- **Frontend**: `/become-a-partner` landing page with hero, benefits grid, fee comparison table, application form
- **Admin Panel**: PartnerManager component with stats, filters, search, review dialog
- **Navbar**: "Become a Partner" link in user dropdown

### Fee Calculation Verified
- $10,000 hammer with 18% buyer premium: Platform $300, Premium $1,800, Stripe recovery $361.69, Total $12,461.69
- Partner transfer: $11,800 (hammer + BP), BidVex application fee: $661.69 (3% + stripe)

### Testing
- Backend: 16/16 tests passed (100%)
- Frontend: All UI verified (100%)
- Report: `/app/test_reports/iteration_42.json`

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
