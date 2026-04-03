# BidVex Auction Marketplace - PRD

## Tech Stack
- **Frontend**: React, Tailwind CSS, Shadcn/UI, react-i18next
- **Backend**: FastAPI, MongoDB (Motor), Stripe, SendGrid, APScheduler
- **AI Engine**: Gemini 2.5 Flash (google-genai)
- **Cache**: Upstash Redis with in-memory fallback
- **Storage**: Cloudflare R2 via boto3 (ACL=private default)
- **Deployment**: Railway (single-service monolith serving API + React SPA)

## Credentials
- Admin: `charbeladmin@bidvex.com` / `Admin123!`

## Completed Work

### Messaging UI Refactoring — Bilingual & Partner Features (April 3, 2026)
- **Hybrid Layout**: Flex column (header → messages flex-1 → quick actions → sticky input → footer)
- **AI Chatbot**: Hidden on `/messages` via `AIAssistantWrapper` in App.js
- **PartnerQuickActions** (VIP/Partner Pro only):
  - Bilingual Quick Replies (EN: "Still available?", "Price is firm"… / FR: "Toujours disponible?", "Prix ferme"…)
  - Inspection Scheduler: Calendar date picker via Popover
  - Auction Terms: Shares bilingual terms into chat
- **Language Detection**: `navigator.language` for placeholder and quick reply language
- **visualViewport API**: Mobile keyboard handling + `env(safe-area-inset-bottom)`
- **Footer visible** at absolute bottom on /messages; MobileBottomNav hidden
- Testing: 28/28 passed (15 desktop + 13 mobile)

### Previous Sessions
- Partner & Trust Features (badges, dashboard) — 14/14 tests
- Law 25 Cookie Consent Banner — 11/11 tests
- Tax Report Export — 22/22 tests
- Commercial Readiness (tax engine, PDF invoices, partner service) — 36/36 tests
- Brute Force, Redis Cache, Architecture Refactor, Risk Monitoring

## Backlog
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring (P2)
- [ ] Read receipts / "seen at" timestamps in message bubbles
