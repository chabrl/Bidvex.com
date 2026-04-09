# BidVex — Auction Marketplace PRD

## Original Problem Statement
Full-stack auction marketplace (React frontend, FastAPI backend, MongoDB) with vehicle-specific identity routing, real-time WebSocket bidding, self-hosted Web Push notifications (VAPID), predictive AI analytics, and 18 active background schedulers.

## Architecture
```
/app
├── backend/
│   ├── server.py                      # FastAPI, CORS, CDN headers, SPA mount
│   ├── shared.py                      # Pydantic models (fixed marketing models)
│   ├── models/auction_models.py       # BuyNowPurchase (with payment_method)
│   ├── routes/
│   │   ├── auctions_bids.py           # Buy-now with hybrid payment (stripe/cash/etransfer)
│   │   ├── payments.py                # Stripe checkout + offline checkout for single items
│   │   ├── site_config.py             # Social links endpoints
│   │   ├── email_marketing_ext.py     # Marketing contacts & campaigns (fixed models)
│   │   └── webhooks.py               # Stripe + SendGrid
│   └── services/
│       └── email_service.py           # Production SendGrid
├── frontend/
│   ├── build/                         # Compiled React SPA
│   └── src/
│       ├── components/Footer.js       # Dynamic social media icons
│       └── pages/
│           ├── CreateMultiItemListing.js    # + Payment Method + Buyer's Premium (partner-only)
│           ├── CreateListingPage.js         # Buyer's Premium changed to partner-only
│           ├── MultiItemListingDetailPage.js # Hybrid payment dialog for buyers
│           └── admin/MarketplaceSettings.js  # Social links admin editor
```

## Completed Features (This Session — April 9, 2026)

### Seller Payment Method + Buyer's Premium for Multi-Item Listings
- Added 3-option Payment Method selector (Stripe/Cash/E-Transfer) to CreateMultiItemListing form
- Added Buyer's Premium input (partner-only) to CreateMultiItemListing form
- Both fields included in listing creation payload

### Buyer's Premium Access Control Fix (Partner-Only)
- Changed Buyer's Premium from `isOpcCertified` to `isPartner` in BOTH listing forms
- Non-partner users see locked notice: "Buyer's Premium is a Partner-exclusive feature"
- Partners/Admins get editable 0-25% input

### Multi-Item Auction — Hybrid Payment Integration (Buyer Side)
- Buy Now dialog with 3 payment methods for lot purchases
- Offline payments (Cash/E-Transfer) create offline_orders with reserved status
- Bilingual (EN/FR) SendGrid confirmation emails

### Marketing Contact 500 Error Fix
- Fixed Pydantic model mismatch (UserContactCreateRequest, UserContactBulkRequest, UserCampaignCreateRequest)

### Dynamic Social Media Icon Suite & Admin Editor
- Social links endpoints + admin settings card + footer SVG icons

## Key DB Schema
- `multi_item_listings.payment_method`: "stripe" | "cash" | "e-transfer" (seller preference)
- `multi_item_listings.buyers_premium_rate`: float (0-0.25, partner-only)
- `buy_now_transactions.payment_method`: "stripe" | "cash" | "etransfer"
- `offline_orders`: order_status, payment_status, interac_email
- `site_config.social_links`: { x, facebook, instagram, linkedin, tiktok }

## 3rd Party Integration Status
- **Stripe** — Live key active
- **SendGrid** — Live key active
- **VAPID Web Push** — Active
- **Twilio** — Configured

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Admin offline order management (confirm receipt, mark paid)
- (Enhancement) Two-factor authentication (2FA)
- (Enhancement) Automated Lighthouse audits
