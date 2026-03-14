# BidVex Roadmap

## P0 - Critical (All Complete)
- [x] Vehicle Auction Module (Phases 1-7)
- [x] Live Stripe Subscription Engine
- [x] Branded PDF Invoices with tax compliance
- [x] Stripe Fee-on-Top Model
- [x] Settings Page UI Overhaul
- [x] Partner Account System Phase 1 (Model, Onboarding, Admin, Fee Engine)
- [x] Phase 2: Stripe Connect Destination Charges (partner fund routing, checkout preview)
- [x] Phase 2: Partner Page UX Refinement (removed fee table, professional layout)
- [x] Phase 2: Checkout UI Itemization (Hammer, BP, Platform Fee, Secure Processing Fee)
- [x] Phase 2: Email Onboarding Logic (ready, pending live SendGrid keys)

## P1 - High Priority
- [ ] **Task 4: Admin Command Center** — Revenue tracker, transaction logs, auction stats, user CRUD, 'Partners & Finance' tab in admin
- [ ] Provide live SendGrid API keys to activate partner onboarding emails
- [ ] User live testing of partner application + verification flow in production

## P2 - Medium Priority
- [ ] Phase 3: Editable buyer premium in auction creation UI for partners
- [ ] Phase 3: Partner Pro subscription tier
- [ ] Phase 3: "Verified Auction Firm" badge displayed on partner listings
- [ ] PDF Invoice Cloud Storage
- [ ] Refactor server.py into modular routers

## P3 - Low Priority
- [ ] Cookie consent translation integration with i18n
- [ ] "Email to Friend" feature for vehicle listings
- [ ] Database indexing on `auction_id` in bids collection
