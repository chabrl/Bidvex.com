# BidVex Roadmap

## Iter302 (2026-06-11) — COMPLETE
- [x] Pre-build legal: bid consent flag + Stripe off_session card saving (verified)
- [x] Directive 1: Seller Winner & Settlement Panel (replaces Promote on ended+winner)
- [x] Directive 2: Buyer Settle Payment + pickup code + Stripe Connect onboarding banner + escrow trust line
- [x] Directive 3: Multi-Lot create page full FR + mobile responsive + 60s per-lot floor (client+server)
- [x] QA: API-level gates (winner PII seller/admin-only; pickup code winner-only), 12-test iter302 suite, regression sweep green, testing agent 9/9

## P0 - Critical (All Complete)
- [x] Vehicle Auction Module (Phases 1-7)
- [x] Live Stripe Subscription Engine
- [x] Branded PDF Invoices with tax compliance
- [x] Stripe Fee-on-Top Model
- [x] Settings Page UI Overhaul
- [x] Partner Account System Phase 1 (Model, Onboarding, Admin, Fee Engine)
- [x] Phase 2: Stripe Connect Destination Charges
- [x] Phase 2: Partner Page UX Refinement
- [x] Phase 2: Checkout UI Itemization
- [x] Phase 2: Email Onboarding Logic
- [x] Phase 2: Admin Command Center
- [x] Phase 2: Marketplace Sidebar Filter
- [x] Sign-up Terms & Policy Consent (Clickwrap)
- [x] Admin RBAC Team Management
- [x] AI Chatbot (Claude Sonnet 4.5)
- [x] Pay-to-Activate Partner Flow ($100 CAD/year)
- [x] Stripe Customer Portal for partner billing
- [x] server.py Refactor Phase 1 (AI Chat, Fees, Notifications, Watchlist)
- [x] server.py Refactor Phase 2 (Partner admin → routes/admin.py)
- [x] server.py Refactor Phase 3 (Marketplace → routes/marketplace.py)
- [x] Test suite updated with current pricing ($180/$300/year, $100 partner fee)

## P1 - High Priority
- [x] Email Settings Admin Panel
- [x] CSV Export for Transaction Logs
- [x] DB-stored SendGrid config
- [ ] server.py Refactor Phase 4: Deduplicate admin user mgmt routes
- [ ] server.py Refactor Phase 5: Extract listings CRUD, bids, multi-item auctions

## P2 - Medium Priority
- [ ] Cache marketplace filter counts (Redis/in-memory)
- [ ] PDF Invoice Cloud Storage
- [ ] Partner Dashboard page (subscription, invoices, payment method)
- [ ] Editable buyer premium in auction creation UI for partners
- [ ] Partner Pro subscription tier

## P3 - Low Priority
- [ ] Cookie consent translation integration with i18n
- [ ] "Email to Friend" feature for vehicle listings
- [ ] Database indexing on `auction_id` in bids collection
- [ ] "Verified Auction Firm" badge on partner listings
