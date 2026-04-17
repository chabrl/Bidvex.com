# BidVex — Auction Marketplace PRD

## Latest: About Us Page Full Redesign (April 17, 2026)

### About Us Page — Full Redesign (5 Fixes) - DONE
- **FIX 1**: Removed inline language switcher from page body — EN/FR toggle only in global navbar
- **FIX 2**: Canadian city hero image (Toronto CN Tower) with BidVex logo overlay, red tint, hover animation (blue shift + text reveal)
- **FIX 3**: Car lot auction image with Canadian flag + BidVex logo, dark gradient overlay, hover pulse
- **FIX 4**: Footer "About Us" properly translates to "À propos de nous" in French mode
- **FIX 5**: Full layout redesign — dark navy hero (#0B2545), scroll-triggered IntersectionObserver animations, gradient Future section, floating Canadian flag, feature cards with blue top accent + hover lift, founder in clean white card, credentials in card format

### Phase 7: Platform Cleanup & Admin Moderation (P0) - DONE
- Platform Cleanup Manager, Cascade Delete User/Listing, Community Moderation Panel

### Earlier Completed
- Escrow system, Sticky Card, Legal Pages, Dark Mode Audit, Community Q&A, Email Marketing, all phases 1-6

### Testing: iteration_152 — Frontend 100% (17/17 tests passed)

## Key Files
- `/app/frontend/src/pages/AboutUsPage.js` — Full redesigned About Us page
- `/app/frontend/src/index.css` — About page CSS animations (.about-animate, .about-flag-float, etc.)
- `/app/frontend/src/locales/fr.json` / `en.json` — footer.about translation keys

## Backlog
- (P0) QA Pass on SendGrid Email Templates
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring
- (Enhancement) Full dispute resolution workflow
