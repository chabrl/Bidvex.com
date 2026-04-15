# BidVex — Auction Marketplace PRD

## Architecture
```
/app
├── backend/
│   ├── server.py                      # FastAPI, CORS, CDN headers, SPA mount
│   ├── routes/
│   │   ├── community.py              # NEW: Community Q&A CRUD + upvotes + best answer
│   │   ├── analytics.py              # CTA tracking + seller analytics
│   │   ├── listings.py               # CRUD + multi-lot deduplication
│   │   └── ...
│   ├── services/
│   │   ├── pricing_manager.py         # CORE: Source of truth for 100% of fee calculations
│   │   └── ...
├── frontend/src/
│   ├── pages/
│   │   ├── CommunityPage.js          # NEW: Q&A forum (questions, replies, upvotes, best answer)
│   │   ├── CreateListingPage.js       # Sell flow with 10 InfoTip tooltips
│   │   ├── CreateMultiItemListing.js  # Multi-lot sell with 7+ InfoTip tooltips
│   │   ├── ListingDetailPage.js       # Buy flow with bid/premium tooltips
│   │   ├── SellerDashboard.js         # 4 stat card tooltips
│   │   ├── PartnerDashboard.js        # 3 stat tooltips
│   │   ├── CheckoutPage.js            # Payment confirmation tooltip
│   │   ├── HowItWorks.js             # CTA tracking + trust signals
│   │   └── HowItWorksPage.js         # Wrapper (used by router)
│   ├── components/
│   │   ├── InfoTip.js                 # Bilingual tooltip (FR/EN, hover + tap)
│   │   └── ui/tooltip.jsx             # Radix tooltip with data-bidvex-tooltip
```

## Completed (April 15, 2026) — Final Correction Sprint

### P0: HowItWorks CTA Navigation Fix
- Fixed ALL broken routes in HowItWorks.js AND HowItWorksPage.js:
  - Start Selling: `/sell` → `/create-listing`
  - Sign Up Free: `/register` → `/auth`
  - Apply as Partner: `/partner` → `/become-a-partner`
  - Apply as Vehicle Seller: `/become-vehicle-seller` → `/vehicle-auctions/seller/register`
  - Browse Vehicles: `/marketplace?category=vehicles` → `/vehicle-auctions`

### P0: Tooltip Coverage Extended
- **CreateMultiItemListing**: 7+ InfoTips (title, description, end date, bid increment, buyer premium, payment, lot count)
- **SellerDashboard**: 4 stat cards with tooltips (active, sold, drafts, total sales)
- **PartnerDashboard**: 3 stats with tooltips (active listings, bids received, projected revenue)

### P1: Community Q&A System (NEW)
- **Route**: `/community`
- **Backend** (`/app/backend/routes/community.py`):
  - `GET /api/community/questions` — Public, paginated, searchable, sortable
  - `POST /api/community/questions` — Auth required
  - `GET /api/community/questions/{id}` — With replies
  - `POST /api/community/questions/{id}/replies` — Auth required
  - `POST /api/community/questions/{id}/upvote` — Toggle upvote
  - `POST /api/community/replies/{id}/upvote` — Toggle reply upvote
  - `POST /api/community/questions/{id}/best-reply` — Author-only
- **Frontend** (`/app/frontend/src/pages/CommunityPage.js`):
  - Question list with upvotes, reply count, views, author, time
  - Question detail with reply thread
  - Post question form (logged-in only)
  - Reply form (logged-in only)
  - Upvote system (questions + replies)
  - "Best Answer" marking (question author only)
  - Search + Sort (newest, most replies, most upvoted)
  - Fully bilingual (FR/EN)
  - Guest read access, auth required for posting
- **DB Collections**: `community_questions`, `community_replies`

### Testing: iteration_145 — 100% backend (19/19), 100% frontend

## Completed (April 15, 2026) — 5 Critical UX/Feature Gaps (P0)
- Tooltip Visibility Fix (html.dark CSS selector survives minification)
- Multi-lot Deduplication in GET /api/listings
- Tooltip System 100% coverage (Sell + Buy flows)
- Trust Signals on How It Works page (4 signals)
- CTA Click Tracking (POST /api/analytics/cta-click)

## 3rd Party Integrations
- Stripe — Live | SendGrid — Live | Gemini 2.5 Flash — litellm + EMERGENT_LLM_KEY | VAPID Push — Active

## Backlog
- (P1) Phase 3: Email Marketing System — Real campaigns, segmentation, auction alerts, abandoned bid emails
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Admin offline order management
- (Enhancement) 2FA for high-value bidders
