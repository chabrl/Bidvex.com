# BidVex — Auction Marketplace PRD

## Latest: P0+P1 Finalization + Platform Cleanup (April 16, 2026)

### Phase 1: Escrow Dispute UI (P0)
- **Buyer Dashboard**: Red dispute badge, disabled actions, bilingual message
- **Seller Dashboard**: Red border card, disabled pickup input, bilingual dispute notice
- Both show: "This escrow is under dispute. Funds are temporarily locked."

### Phase 2: Penalty Log Admin (P0)
- Admin table: seller_id, listing_id, amount, reason, Stripe PI, status, date
- Empty state when no penalties

### Phase 3: Escrow Admin Viewer (P0)
- Admin table: auction_id, buyer, seller, amount, status, pickup_code, created, released
- Status filter + search
- 5 stats cards (Total, Held, Released, Disputes, Penalties)

### Phase 5: Seller Escrow Widget (P1)
- Real-time escrow cards with: Held (code input + countdown), Released (green), Auto-Released (blue), Disputed (red disabled)
- Inline 6-char monospace pickup code input

### Phase 6: Buyer Escrow Timeline (P1)
- 5-step visual timeline: Payment → Escrow → Code Issued → Pickup → Released
- Green checkmarks for completed steps, timestamps, bilingual labels

### Phase 7: Platform Cleanup
- DB audit: only `settings` (1 doc) + `vehicle_settlements` (0 docs) exist
- Zero test data found — platform is production-clean

### Testing: iteration_149 — 100% backend, 100% frontend

## Architecture Summary
```
/app/backend/routes/escrow.py      # 8 endpoints (user + admin)
/app/frontend/src/
├── pages/admin/AdminEscrowManager.js  # 3 tabs (escrows/disputes/penalties)
├── components/EscrowPickupPanel.js    # SellerEscrowPanel + BuyerEscrowPanel + BuyerTimeline
```

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring
- (Enhancement) Full dispute resolution workflow
- (Enhancement) Admin offline order management
