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

## Launch Status
- **GO** — See /app/memory/LAUNCH_CHECKLIST.md
- 2 manual items: Cloudflare CDN setup, MongoDB index creation

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`
