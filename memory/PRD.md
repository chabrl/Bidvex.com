# BidVex Auction Marketplace — PRD

## Product Overview
Full-stack auction marketplace with localized currency, tax compliance, 4-tier subscriptions (Free/Premium/Partner Pro/VIP), real-time bidding, and professional seller tools.

## Tech Stack
- **Frontend**: React 19, Tailwind CSS, Shadcn/UI, @tanstack/react-query, embla-carousel-react, react-i18next
- **Backend**: FastAPI (37 route modules), MongoDB, Stripe, SendGrid, Emergent Object Storage, slowapi
- **Architecture**: Modular backend, shared.py for common models, server.py as ~362-line entry point

## Subscription Tiers
| Tier | Price/yr | Original | Annual-Only |
|------|----------|----------|-------------|
| Free | $0 | — | N/A |
| Premium | $180 | $360 | Yes |
| Partner Pro | $240 | $480 | Yes |
| VIP | $300 | $600 | Yes |

## All Completed Features
- Core: JWT auth, admin panel, real-time WS bidding, listing CRUD, marketplace
- Financial: Stripe billing (4 tiers), tax engine, PDF invoices (cloud), commission tracking
- Partner Pro: Branded storefront, CSV bulk import, early access, analytics export, featured listings, trial flow
- UX: Mobile swipeable carousels, comparison view, responsive design, SEO
- Security: Rate limiting (slowapi), Stripe webhook verification, HMAC signed URLs
- Email: 5 Partner Pro lifecycle templates (41 pytest tests)
- Database: Production indexes (27 total across 14 collections)
- **i18n (COMPLETE)**:
  - P1: Migrated 567 keys from 2000-line i18n.js builder into JSON files; i18n.js simplified to 60 lines
  - P2: Fixed 202 hardcoded English strings across 48 source files with real French translations
  - P3: Cleaned 481 provably dead keys; 907 keys remain, EN/FR in perfect sync
  - CI: `yarn predeploy` runs i18n audit, exit code 1 blocks deploy on regressions
  - Audit tool: `yarn i18n:audit` → full report at `scripts/i18n-report.txt`

## Final i18n Audit (March 20, 2026)
| Metric | Result |
|--------|--------|
| Hardcoded strings | **0** |
| Missing keys | **0** |
| EN/FR sync | **100% (907 keys)** |
| Unused keys | **133** (intentionally kept: common utilities, nav, footer, bidErrorGuide) |
| CI gate | **Active** (`yarn predeploy`) |

## Launch Status: GO
- See `/app/memory/LAUNCH_CHECKLIST.md`
- 1 manual item remaining: Cloudflare CDN setup

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`
