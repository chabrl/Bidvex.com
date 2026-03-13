# BidVex Roadmap

## P0 - Critical (All Complete)
- [x] Vehicle Auction Module (Phases 1-7)
- [x] Live Stripe Subscription Engine
- [x] Branded PDF Invoices with tax compliance
- [x] Stripe Fee-on-Top Model
- [x] Settings Page UI Overhaul

## P1 - High Priority
- [ ] User live testing of finalized subscription flow on production domain
- [ ] Configure SendGrid API keys for production emails
- [ ] Verify production deployment at www.bidvex.com

## P2 - Medium Priority
- [ ] PDF Invoice Cloud Storage (save to persistent storage, store URL in DB)
- [ ] Refactor server.py into modular routers (auth.py created, needs integration)
- [ ] Refactor i18n.js into namespaces

## P3 - Low Priority
- [ ] Cookie consent translation integration with i18n
- [ ] "Email to Friend" feature for vehicle listings
- [ ] Database indexing on `auction_id` in bids collection
- [ ] Remove /app/frontend/src/pages/CheckboxDemo.js (temp test page)
- [ ] UI for AI Guard Status
