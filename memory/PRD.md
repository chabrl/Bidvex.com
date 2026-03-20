# BidVex Auction Marketplace — PRD

## Product Overview
Full-stack auction marketplace with localized currency, tax compliance, 4-tier subscriptions (Free/Premium/Partner Pro/VIP), real-time bidding, and professional seller tools.

## Tech Stack
- **Frontend**: React 19, Tailwind CSS, Shadcn/UI, @tanstack/react-query, embla-carousel-react
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
- Database: Production indexes (27 total across 14 collections), idempotent script at scripts/apply_indexes.py
- **i18n**: Full EN/FR translation for Seller Dashboard (77+ keys), i18n.js resource builder fixed to merge JSON translation files
- **i18n Audit Tool**: Node.js script at `scripts/i18n-audit.js` — detects hardcoded strings, missing/unused keys, EN/FR sync issues. Run via `yarn i18n:audit`

## i18n Audit Summary (March 20, 2026)
- 539 keys in sync between EN/FR
- 202 hardcoded strings detected across 179 files (full report at scripts/i18n-report.txt)
- 437 keys used via t() but only defined in i18n.js builder (should migrate to JSON)
- 225 potentially unused JSON keys (review before cleanup)
- EN/FR files: perfectly in sync

## Launch Status
- **GO** — See /app/memory/LAUNCH_CHECKLIST.md
- MongoDB indexes: DONE (27 indexes applied, all verified)
- i18n Seller Dashboard: DONE (zero hardcoded English strings, visually verified in FR mode)
- 1 manual item remaining: Cloudflare CDN setup

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`
