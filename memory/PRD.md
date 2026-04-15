# BidVex — Auction Marketplace PRD

## Completed (April 15, 2026) — Escrow Pickup Code Full UI Flow

### Seller Dashboard — "Escrow & Pickup" Tab
- New tab with Lock icon in Seller Dashboard tab bar
- **SellerEscrowPanel** component: Shows all escrow transactions for the seller
- **Pickup Code Entry UI**: 6-character monospace input (uppercase, filtered A-Z0-9), Confirm button with loading state
- **Status states**: Held (with countdown timer), Released (green confirmation), Auto-Released (blue info), Disputed (red warning)
- **Empty state**: Shield icon + explanatory message

### Buyer Dashboard — "Escrow" Tab
- New tab with Lock icon in Buyer Dashboard tabs
- **BuyerEscrowPanel** component: Shows all escrow transactions for the buyer
- **Pickup Instructions**: Amber-highlighted card telling buyer to check email for pickup code
- **Status states**: Held (with instructions), Released, Auto-Released, Disputed
- **Empty state**: Shield icon + explanatory message

### Legal Page Preservation + Addendum
- **Existing /legal page content**: 100% preserved (all 17+ sections untouched)
- **Addendum appended** at bottom with EN + FR sections:
  - A1. Sticky Card Policy, A2. Cancellation Penalty
  - B1. Escrow & Pickup Code, B2. 48h Auto-Release, B3. Disputes, B4. Data & Privacy
- /terms-of-service → redirects to /legal#terms
- /privacy-policy → redirects to /legal#privacy
- /policies → Seller, Buyer, Partner, Community policies (bilingual)

### Architecture
```
/app/frontend/src/
├── components/
│   ├── EscrowPickupPanel.js         # SellerEscrowPanel + BuyerEscrowPanel
├── pages/
│   ├── SellerDashboard.js           # + Escrow & Pickup tab
│   ├── BuyerDashboard.js            # + Escrow tab
│   ├── LegalPage.js                 # + Addendum (EN+FR) appended
│   ├── PlatformPoliciesPage.js      # Seller/Buyer/Partner/Community
/app/backend/
├── services/
│   ├── stripe_customer_service.py   # Sticky Card, penalty, audit
│   ├── escrow_service.py            # Escrow hold, confirm, auto-release, dispute
├── routes/
│   ├── escrow.py                    # 5 endpoints
│   ├── payments.py                  # Card deletion guard (409)
│   ├── listings.py                  # Payment method guard (402)
│   ├── webhooks.py                  # Escrow hold for non-vehicle payments
```

## Testing: iterations 147 (14/14 backend) + 148 (100% frontend)

## 3rd Party Integrations
- Stripe — Live | SendGrid — Live | Gemini 2.5 Flash — litellm | VAPID Push — Active

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Full dispute resolution workflow
- (Enhancement) Admin offline order management
- (Enhancement) 2FA for high-value bidders
