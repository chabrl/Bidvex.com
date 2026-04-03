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

### App-Style Mobile Stack & Premium Real-Time Messaging (April 3, 2026)
- **Mobile Stack**: MobileBottomNav re-enabled on `/messages` route; chat input stacks directly above it with `pb-14 lg:pb-0`
- **Frosted Glass Input**: Input bar uses `bg-white/90 backdrop-blur-xl` for clear glass effect, no visual clutter from scrolling messages
- **Footer**: Hidden on `/messages` via FooterWrapper location check
- **Read Receipts**: Vibrant BidVex blue double checkmark (`#38BDF8`) with bilingual "Seen at {{time}}" / "Vu à {{time}}"
- **Typing Indicators**: Bilingual dots animation + text in both chat header and message bubble area
- **Law 25 Compliance**: All read receipts, typing indicators, and mark-as-read gated behind `isAllowed('functionality')` from `useCookieConsent`
- **i18n**: Added `messaging` key to en.json/fr.json (typing, online, offline, seenAt, typeMessage, delivered)
- **Testing**: 14/14 tests passed (iteration_100.json) — 100% backend + 100% frontend

### Messaging UI Refactoring — Bilingual & Partner Features (April 3, 2026)
- **Hybrid Layout**: Flex column (header -> messages flex-1 -> quick actions -> sticky input)
- **AI Chatbot**: Hidden on `/messages` via `AIAssistantWrapper` in App.js
- **PartnerQuickActions** (VIP/Partner Pro only):
  - Bilingual Quick Replies (EN: "Still available?", "Price is firm" / FR: "Toujours disponible?", "Prix ferme")
  - Inspection Scheduler: Calendar date picker via Popover
  - Auction Terms: Shares bilingual terms into chat
- **visualViewport API**: Mobile keyboard handling + `env(safe-area-inset-bottom)`
- Testing: 28/28 passed (15 desktop + 13 mobile)

### Previous Sessions
- Partner & Trust Features (badges, dashboard) — 14/14 tests
- Law 25 Cookie Consent Banner — 11/11 tests
- Tax Report Export — 22/22 tests
- Commercial Readiness (tax engine, PDF invoices, partner service) — 36/36 tests
- Brute Force, Redis Cache, Architecture Refactor, Risk Monitoring

## Backlog
- [ ] Cloudflare CDN setup (P2)
- [ ] Post-launch monitoring and alerting (P2)
- [ ] Real-time performance dashboard (Enhancement)
- [ ] Automated Lighthouse audits weekly (Enhancement)
- [ ] Server-side PageSpeed monitoring endpoint (Enhancement)
- [ ] i18n for EmailMarketingPricing page (Low)
- [ ] Refactor MessagesPage.js (~1000 lines) into smaller components (Tech debt)
