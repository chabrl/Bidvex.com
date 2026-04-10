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
│   │   ├── ai_chat.py                 # Master Concierge chatbot (EMERGENT_LLM_KEY via litellm)
│   │   └── webhooks.py               # Stripe + SendGrid
│   └── services/
│       ├── email_service.py           # Production SendGrid (click tracking disabled)
│       ├── ai_assistant_v2.py         # Gemini 2.5 Flash via litellm + Emergent proxy
│       └── translation_service.py     # EN<->FR via litellm + Emergent proxy
├── frontend/
│   ├── build/                         # Compiled React SPA
│   └── src/
│       ├── config.js                  # API_BASE = REACT_APP_BACKEND_URL + /api
│       ├── components/
│       │   ├── AIAssistant.js         # Chatbot UI (HTTP POST, no WebSocket)
│       │   └── Footer.js             # Dynamic social media icons
│       └── pages/
│           ├── CreateMultiItemListing.js    # + Payment Method + Buyer's Premium (partner-only)
│           ├── MultiItemListingDetailPage.js # Hybrid payment dialog for buyers
│           └── admin/
│               ├── EmailMarketingManager.js  # Campaign management + Delete/Resend/Clone
│               └── MarketplaceSettings.js    # Social links admin editor
```

## Completed Features (April 10, 2026)

### Master Concierge AI Chatbot — Full Fix
- **Root Cause**: Gemini API key `AIzaSy...` was flagged as leaked by Google (403 PERMISSION_DENIED)
- **Fix**: Replaced direct `google.genai` calls with `litellm.completion()` routed through Emergent proxy
- **No emergentintegrations dependency** — uses litellm (already in requirements.txt)
- **How it works**: EMERGENT_LLM_KEY → litellm → Emergent proxy (https://integrations.emergentagent.com/llm) → Gemini 2.5 Flash
- **Frontend verification**: Multi-turn conversation tested via screenshot, chatbot responds with rich action buttons
- **CORS**: bidvex.com, www.bidvex.com, api.bidvex.com all permitted
- **Also fixed**: translation_service.py migrated from emergentintegrations to litellm

### Email Marketing Dashboard — Delete, Resend, Clone Campaigns
- DELETE /api/admin/marketing/campaigns/{id}
- POST /api/admin/marketing/campaigns/{id}/clone — creates draft copy
- POST /api/admin/marketing/campaigns/{id}/resend — resets & re-sends completed/failed campaigns
- Frontend: action buttons on campaign rows + detail view
- Fixed CampaignCreateRequest & CampaignUpdateRequest Pydantic models
- All 9 backend + all frontend UI tests passed (iteration_128)

## Railway Production Deployment Checklist
1. **Save to GitHub** (click "Save to GitHub" button)
2. **Add Railway Env Var**: `EMERGENT_LLM_KEY=sk-emergent-45818088307Fa1bB23`
3. **Verify**: `REACT_APP_BACKEND_URL` points to production domain
4. **No new pip dependencies** — litellm is already in requirements.txt

## 3rd Party Integration Status
- **Stripe** — Live key active
- **SendGrid** — Live key active (Click Tracking disabled)
- **VAPID Web Push** — Active
- **Twilio** — Configured
- **Gemini 2.5 Flash** — Active via litellm + EMERGENT_LLM_KEY (Emergent proxy)

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Admin offline order management (confirm receipt, mark paid)
- (Enhancement) Two-factor authentication (2FA)
- (Enhancement) Automated Lighthouse audits
