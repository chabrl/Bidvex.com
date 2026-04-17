# BidVex — Auction Marketplace PRD

## Latest: About Us Page (April 17, 2026)

### About Us Page (New Feature) - DONE
- High-fidelity bilingual (FR/EN) About Us page at `/about` and `/about-us`
- Hero section with "Your World, Under the Gavel" tagline + CTAs
- Bento grid company story: Vision (2-col), Engineering (dark navy), Mission (full-width)
- Three seller persona cards: Individual, Local Hero, Global Player
- Why Canada section with Toronto skyline + trust messaging
- Dark "Future is Instant" CTA section with cyan accents
- Founder bio: circular avatar with blue ring border, quote block
- Official Business Credentials: Bidvex Inc., Federal 706766367, NEQ 1181780744, Phone, Email
- FR/EN toggle switches all content dynamically
- Added "About Us" link to footer navigation
- Google Fonts: Outfit (headings), DM Sans (body)

### Phase 7: Platform Cleanup & Admin Moderation (P0) - DONE
- Platform Cleanup Manager, Cascade Delete User/Listing, Community Moderation Panel

### Earlier Completed (Phases 1-6)
- Escrow Dispute UI, Penalty Log, Escrow Admin, Seller Escrow Widget, Buyer Timeline
- Sticky Card, Escrow + Pickup Code, Legal Pages, Dark Mode Audit, Community Q&A, Email Marketing

### Testing: iteration_151 — Frontend 100%

## Architecture
```
/app/frontend/src/pages/
├── AboutUsPage.js              # Bilingual About Us with all sections
├── admin/PlatformCleanupManager.js
├── admin/CommunityModerationManager.js
```

## Key Routes
- `/about` and `/about-us` — About Us page (public)
- `/api/admin/platform-cleanup/preview` — Cleanup dry-run
- `/api/admin/platform-cleanup` — Execute cleanup
- `/api/admin/comments/question/{id}` — Delete community question

## Backlog
- (P0) QA Pass on SendGrid Email Templates
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring
- (Enhancement) Full dispute resolution workflow
- (Enhancement) Admin offline order management
