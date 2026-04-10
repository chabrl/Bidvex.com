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
│   │   ├── email_marketing_ext.py     # Marketing campaigns: CRUD + Delete/Resend/Clone
│   │   ├── ai_chat.py                 # Master Concierge chatbot (Emergent LLM Key)
│   │   └── webhooks.py               # Stripe + SendGrid
│   └── services/
│       ├── email_service.py           # Production SendGrid (click tracking disabled)
│       └── ai_assistant_v2.py         # Gemini 2.5 Flash via emergentintegrations
├── frontend/
│   ├── build/                         # Compiled React SPA
│   └── src/
│       ├── components/Footer.js       # Dynamic social media icons
│       └── pages/
│           ├── CreateMultiItemListing.js    # + Payment Method + Buyer's Premium (partner-only)
│           ├── CreateListingPage.js         # Buyer's Premium changed to partner-only
│           ├── MultiItemListingDetailPage.js # Hybrid payment dialog for buyers
│           └── admin/
│               ├── EmailMarketingManager.js  # Campaign management + Delete/Resend/Clone
│               └── MarketplaceSettings.js    # Social links admin editor
```

## Completed Features (This Session — April 10, 2026)

### Email Marketing Dashboard — Delete, Resend, Clone Campaigns
- DELETE /api/admin/marketing/campaigns/{id} — deletes campaigns (blocks sending ones)
- POST /api/admin/marketing/campaigns/{id}/clone — creates draft copy with "(Copy)" suffix
- POST /api/admin/marketing/campaigns/{id}/resend — resets status & re-sends completed/failed campaigns
- Frontend: Clone, Resend (conditional), Delete buttons on every campaign row + detail view
- Fixed CampaignCreateRequest & CampaignUpdateRequest Pydantic models in shared.py
- Fixed F811 lint error (duplicate get_email_templates definition)
- All 9 backend tests + all frontend UI tests passed (iteration_128)

### Master Concierge AI Chatbot Fix
- Replaced leaked Gemini API key with Emergent LLM Key via emergentintegrations library
- ai_assistant_v2.py: Switched from google.genai to emergentintegrations.llm.chat.LlmChat
- ai_chat.py: Changed GEMINI_API_KEY to EMERGENT_LLM_KEY
- Chatbot now responds successfully to both EN and FR queries

## Previous Session Completed Features (April 9, 2026)

### Seller Payment Method + Buyer's Premium for Multi-Item Listings
- Added 3-option Payment Method selector (Stripe/Cash/E-Transfer) to CreateMultiItemListing form
- Added Buyer's Premium input (partner-only) to CreateMultiItemListing form

### Multi-Item Auction — Hybrid Payment Integration (Buyer Side)
- Buy Now dialog with 3 payment methods for lot purchases
- Offline payments (Cash/E-Transfer) create offline_orders with reserved status

### Marketing Contact 500 Error Fix
- Fixed Pydantic model mismatch (UserContactCreateRequest, UserContactBulkRequest, UserCampaignCreateRequest)

### Dynamic Social Media Icon Suite & Admin Editor
- Social links endpoints + admin settings card + footer SVG icons

### Email Deliverability & DNS
- Disabled SendGrid Click Tracking globally (Chrome 'Unsafe Attempt' fix)
- Raw HTML password reset template (bypasses broken SendGrid templates)
- SPF/DKIM/DMARC advisory for GoDaddy DNS

### Sitemap.xml
- Static sitemap with priority routes, proper application/xml MIME type

## Key DB Schema
- `multi_item_listings.payment_method`: "stripe" | "cash" | "e-transfer"
- `multi_item_listings.buyers_premium_rate`: float (0-0.25, partner-only)
- `buy_now_transactions.payment_method`: "stripe" | "cash" | "etransfer"
- `offline_orders`: order_status, payment_status, interac_email
- `site_config.social_links`: { x, facebook, instagram, linkedin, tiktok }
- `email_campaigns`: id, name, subject, status, html_content, audience_filters

## 3rd Party Integration Status
- **Stripe** — Live key active
- **SendGrid** — Live key active (Click Tracking disabled)
- **VAPID Web Push** — Active
- **Twilio** — Configured
- **Emergent LLM (Gemini 2.5 Flash)** — Active via EMERGENT_LLM_KEY

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Admin offline order management (confirm receipt, mark paid)
- (Enhancement) Two-factor authentication (2FA)
- (Enhancement) Automated Lighthouse audits
