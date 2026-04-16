# BidVex — Auction Marketplace PRD

## Latest: Phase 7 Complete - Platform Cleanup & Moderation Controls (April 16, 2026)

### Phase 7: Platform Cleanup & Admin Moderation (P0) - DONE
- **Platform Cleanup Manager**: One-click test data removal with preview, safety protections (protects admin/superadmin), confirms before executing. Targets emails matching: test/demo/qa/fake/spam/example.com/mailinator
- **Cascade Delete User**: Removes user + 16 related collections (listings, bids, messages, notifications, escrows, payment methods, community posts, etc.)
- **Cascade Delete Listing**: Removes listing + bids, watchlist, escrows, notifications, images, reports
- **Cascade Delete Multi-Item Listing**: Removes listing + lots + lot bids + related data
- **Community Moderation Panel**: Admin can search, expand, and delete questions (cascades to replies) and individual replies
- **Delete User Button**: Added to User Management with confirmation modal showing cascade summary

### Phase 6: Buyer Escrow Timeline (P1) - DONE
- 5-step visual timeline: Payment -> Escrow -> Code Issued -> Pickup -> Released
- Green checkmarks for completed steps, timestamps, bilingual labels

### Phase 5: Seller Escrow Widget (P1) - DONE
- Real-time escrow cards with: Held (code input + countdown), Released (green), Auto-Released (blue), Disputed (red disabled)
- Inline 6-char monospace pickup code input

### Phase 3: Escrow Admin Viewer (P0) - DONE
- Admin table: auction_id, buyer, seller, amount, status, pickup_code, created, released
- Status filter + search; 5 stats cards

### Phase 2: Penalty Log Admin (P0) - DONE
- Admin table: seller_id, listing_id, amount, reason, Stripe PI, status, date

### Phase 1: Escrow Dispute UI (P0) - DONE
- Buyer & Seller dashboards show dispute badges, disabled actions, bilingual messages

### Earlier Completed Work
- Sticky Card Enforcement (Stripe Customer, Payment Method attachment, Card Deletion Guard, $50 Cancellation Penalty)
- Escrow + Pickup Code System (non-vehicle items, 6-char pickup code, 48hr auto-release)
- Legal Pages Rebuild (separated Terms/Privacy, documentType prop, bilingual, matching production layout)
- UI/UX Dark Mode Audit (global contrast fixes)
- Community Q&A MVP
- Email Marketing Engine (SendGrid, Abandoned Bid Recovery, Dynamic Segments)
- Tooltip System, CTA Tracking

### Testing: iteration_150 — Backend 88%+, Frontend 100%

## Architecture Summary
```
/app/backend/routes/
├── admin_ops.py           # Cascade deletes, platform cleanup, community moderation
├── escrow.py              # Escrow endpoints (user + admin)
├── community.py           # Community Q&A routes
/app/frontend/src/
├── pages/admin/
│   ├── PlatformCleanupManager.js   # Test data removal with preview grid
│   ├── CommunityModerationManager.js # Question/reply moderation
│   ├── EnhancedUserManager.js       # User management with cascade delete
│   ├── AdminEscrowManager.js        # Escrow/disputes/penalties tabs
├── components/
│   ├── EscrowPickupPanel.js          # Buyer timeline & Seller code input
```

## Key API Endpoints
- `GET /api/admin/platform-cleanup/preview` - Dry-run: count test data
- `POST /api/admin/platform-cleanup` - Execute test data deletion
- `DELETE /api/admin/users/{user_id}` - Cascade delete user
- `DELETE /api/admin/listings/{listing_id}` - Cascade delete listing
- `DELETE /api/admin/multi-item-listings/{listing_id}` - Cascade delete multi listing
- `DELETE /api/admin/comments/question/{id}` - Delete question + replies
- `DELETE /api/admin/comments/reply/{id}` - Delete single reply
- `GET /api/admin/community/questions` - List questions for moderation
- `POST /api/seller/confirm-pickup` - Release escrow via pickup code

## Backlog
- (P0) QA Pass on SendGrid Email Templates
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring
- (Enhancement) Full dispute resolution workflow
- (Enhancement) Admin offline order management
- (Enhancement) 2FA for high-value bidders
