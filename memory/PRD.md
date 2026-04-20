# BidVex — Auction Marketplace PRD

## Latest: Cloudflare CDN Optimization (April 20, 2026)

### Cloudflare CDN DNS Migration (P2) — DONE

**Part A — Code Optimizations:**
- **A1: Cache-Control Headers** — 5-tier strategy in `server.py` middleware:
  - Tier 1: Static JS/CSS → `immutable, max-age=31536000`
  - Tier 2: Images/fonts → `max-age=31536000`
  - Tier 3: HTML → `no-cache`
  - Tier 4: Public APIs (marketplace, site-config, categories) → `s-maxage=300` (5min edge)
  - Tier 5: Private APIs (auth, dashboard, bids) → `no-store`
- **A2: Frontend** — Added preconnect for SendGrid CDN + Unsplash + Stripe, `fetchpriority="high"` on hero image, `dns-prefetch` for Stripe
- **A3: Security Headers** — X-Frame-Options: DENY, X-XSS-Protection, Referrer-Policy, Permissions-Policy, COOP

**Part B — Cloudflare Dashboard Checklist** at `/app/CLOUDFLARE_SETUP_CHECKLIST.md` (14 steps)

### P0 Email Template QA — DONE
### About Us Page — Full Redesign — DONE
### Phase 7: Platform Cleanup & Admin Moderation — DONE
### Phases 1-6: All Complete

## Backlog
- (P2) Post-launch monitoring & alerting
- (Enhancement) Full dispute resolution workflow
- (Enhancement) Admin offline order management
