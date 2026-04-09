# BidVex — Auction Marketplace PRD

## Original Problem Statement
Full-stack auction marketplace (React frontend, FastAPI backend, MongoDB) with vehicle-specific identity routing, real-time WebSocket bidding, self-hosted Web Push notifications (VAPID), predictive AI analytics, and 18 active background schedulers.

## Architecture
```
/app
├── backend/
│   ├── server.py                      # FastAPI, CORS, CDN headers, SPA mount
│   ├── shared.py                      # Pydantic models, constants, utilities
│   ├── models/auction_models.py       # BuyNowPurchase (with payment_method), BuyNowTransaction, Lot models
│   ├── routes/
│   │   ├── auctions_bids.py           # Buy-now with hybrid payment (stripe/cash/etransfer)
│   │   ├── payments.py                # Stripe checkout + offline checkout (Cash/E-Transfer) for single items
│   │   ├── auth.py                    # Login, register, forgot/reset/change password
│   │   ├── admin_config.py            # Marketplace settings, banners
│   │   ├── site_config.py             # Branding, homepage layout, hero banners, social links
│   │   ├── email_marketing_ext.py     # User/Admin marketing contacts & campaigns
│   │   └── webhooks.py               # Stripe + SendGrid webhook handlers
│   └── services/
│       ├── email_service.py           # Production SendGrid
│       ├── user_email_marketing.py    # User contact/campaign management
│       └── scheduled_jobs.py          # 18 background jobs
├── frontend/
│   ├── build/                         # Compiled React SPA
│   └── src/
│       ├── components/Footer.js       # Dynamic social media icons
│       └── pages/
│           ├── MultiItemListingDetailPage.js  # Hybrid payment dialog for lots
│           ├── admin/MarketplaceSettings.js   # Social links admin editor
│           ├── CheckoutPage.js        # 3-way payment for single items
│           └── ProfileSettingsPage.js  # Security tab with Change Password
```

## Completed Features (This Session — April 9, 2026)

### Multi-Item Auction — Hybrid Payment Integration (P0)
- Added `payment_method` field to `BuyNowPurchase` model (stripe/cash/etransfer, default: stripe)
- Backend `/api/buy-now` now handles offline payments: creates `offline_orders` record with status "reserved"/"waiting_for_offline_confirmation"
- Frontend: "Buy Now" opens a payment method selection Dialog with 3 radio options
- Button text dynamically changes: "Pay Now" (Stripe) / "Confirm Order" (Cash) / "Confirm E-Transfer"
- Bilingual (EN/FR) SendGrid emails sent for offline payment instructions (SendGrid 202 confirmed)

### Marketing Contact 500 Error Fix
- Fixed Pydantic model mismatch in shared.py (UserContactCreateRequest, UserContactBulkRequest, UserCampaignCreateRequest)

### Dynamic Social Media Icon Suite & Admin Editor
- GET/PUT /api/site-config/social-links endpoints
- Admin settings card with 5 social link inputs
- Footer renders SVG icons conditionally

## Key API Endpoints
- POST /api/buy-now — Buy Now with hybrid payment (stripe/cash/etransfer)
- POST /api/user/marketing/contacts — Add contact (fixed)
- GET /api/site-config/social-links — Public social links
- PUT /api/admin/site-config/social-links — Admin social links update

## Key DB Schema Changes
- `buy_now_transactions.payment_method`: "stripe" | "cash" | "etransfer"
- `buy_now_transactions.payment_status`: "pending" (stripe) | "waiting_for_offline_confirmation" (offline)
- `offline_orders`: id, listing_id, lot_number, buyer_id, seller_id, payment_method, order_status, payment_status, amount, lot_title, interac_email
- `site_config.social_links`: { x, facebook, instagram, linkedin, tiktok }

## 3rd Party Integration Status
- **Stripe** — Live key active
- **SendGrid** — Live key active (emails sent for offline payment instructions)
- **VAPID Web Push** — Active
- **Twilio** — Configured

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Admin offline order management (confirm receipt, mark paid)
- (Enhancement) Two-factor authentication (2FA)
- (Enhancement) Automated Lighthouse audits
