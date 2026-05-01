# BidVex — Auction Marketplace PRD

## Latest: P0 — Auto-Bid UI Parity Fix (May 1, 2026 / iter174) — 1/1 DONE

User feedback on iter173: the storage detail "Your max bid" + yellow "PRO AUTO-BID" callout was inconsistent with the marketplace bidding sidebar. Replaced with the standardized **Setup Auto-Bid** pattern.

### Changes
1. **Bid input rename** — "Your max bid" → "Your bid · Votre offre" (bilingual). Storage backend still treats every bid as a max_bid intrinsically.
2. **Yellow/blue callouts deleted** — both the amber "PRO AUTO-BID" Premium card and the blue "Auto-Bid Info" upsell card removed from `StorageAuctionDetail`.
3. **NEW `StorageAutoBidModal` component** — mirrors `/app/frontend/src/components/AutoBidModal.js` exactly:
   - Trigger: "Setup Auto-Bid · Configurer Auto-Enchère" outline button below the bid section, with purple `Premium` badge for free-tier (`free`, `partner_basic`) users
   - Modal: bilingual title, current-bid display, bot-increment hint, Max Bid input, "How Auto-Bid Works" callout (4 bullets — every line shows EN + FR), green "Activate Auto-Bid · Activer" submit
   - Premium gating: `premium`, `vip`, `vip_elite`, `partner_pro`, `business` see the activation form; everyone else sees a purple upsell card with "Upgrade to Premium · Passer à Premium" navigating to `/subscription`
   - Submission posts to existing `POST /api/storage-auctions/{id}/bid` with `{max_bid}` — no new backend endpoint needed
4. **Visual parity** — Storage bidding sidebar is now visually + functionally identical to the Marketplace bidding sidebar.

### Verification
- Logged in as VIP admin: Setup Auto-Bid button renders without Premium badge (correct gating). Modal opens, Current Bid $85.00, increments $10.00, all bilingual labels confirmed by screenshot.
- Free-tier upsell variant: purple Premium badge + Upgrade CTA (verified in code path).
- Backend regression: 16/16 storage tests still pass after the UI change (no backend change required).
- Lint: zero issues on `StorageAutoBidModal.js` + `StorageAuctionDetail.js`.

### Files changed (iter174)
- Frontend: `components/StorageAutoBidModal.js` (NEW — 195 lines), `pages/storage/StorageAuctionDetail.js` (label rename + callout deletion + modal wiring)

---

## Latest: P0 — Final Polish Sprint (May 1, 2026 / iter173) — 6/6 DONE

### Spec (6/6 delivered)
1. **QR Code Pickup Integration** — `qrcode==8.2` installed; new `GET /api/storage-auctions/{id}/pickup-qr` returns PNG (ERROR_CORRECT_H, box_size=10) restricted to winner / facility-owner / admin. Winner email now embeds a 180×180 base64 QR alongside the existing `BV-XXXX-XXXX` code with bilingual "Scan at pickup · Show code to staff" caption.
2. **Storage Auto-Bid UI Tier Callout** — `StorageAuctionDetail` sidebar now renders a tier-aware bilingual callout below the bid input: 👑 amber "Pro Auto-Bid · Auto-Enchère Pro" badge for Premium/VIP/VIP_Elite/Partner_Pro/Business; blue "Auto-Bid Info" upsell with "Upgrade to Premium · Passez à Premium" link for free tier. Storage proxy is intrinsic (every bid = max_bid ceiling), so all users still get auto-bidding.
3. **Facility Promotion Modal** — New `PromoteAuctionModal.js` with 3-tier grid (Basic $9.99 / Featured $24.99 / Premium $49.99) → Stripe `confirmCardPayment` flow → activates promotion via existing `/promote` + `/promote/confirm` endpoints. Wired into `StorageDashboard` per-auction "Promote · Promouvoir" button (only on active/upcoming auctions without an existing promotion).
4. **Admin "Create Storage Auction" UI** — New `AdminStorageAuctions.js` admin page with auction list + filters + Create dialog (facility picker, all 11 fields with date-time pickers, payment-method selector, optional deposit). Wired under Admin → Marketplace → "Storage Auctions" secondary tab (data-testid `admin-tab-storage-auctions-admin`).
5. **Vehicle Deposit Flow UI ($500 Manual Capture)** — `SecurityDepositBanner` rewritten: clicking "Authorize Hold" now opens a Stripe Elements modal with `<CardElement>` → `stripe.confirmCardPayment(client_secret)` → new backend endpoint `POST /api/deposits/confirm` syncs the hold status (`requires_capture` = held). OPC-compliant manual capture: card pre-authorized, never charged unless winner defaults on fee invoice.
6. **Pydantic V2 Migration** — Replaced all bare `@validator` decorators in `models/storage_auction.py` with `@field_validator(mode='after')` + `@model_validator(mode='after')`. Replaced `.dict()` calls in `services/subscription_pricing.py`, `services/ai_assistant.py`, `routes/subscriptions.py`, `routes/storage_auctions.py` with `.model_dump()` (with V1 fallback). Tests assert ABSENCE of V1 `@validator` decorator.

### Tests — 33/33 green
- `test_storage_iter173_api.py` (NEW) — 17 tests pass + 2 skipped (env-only, need sold auction with pickup_code)
- Regression: `test_storage_payment_deposit_iter170.py` — 10/10 + `test_storage_proxy_bug_iter172.py` — 6/6
- Pydantic V2 ValidationError correctly raised on invalid `payment_method='bitcoin'` and `deposit_required=True with deposit_amount=0`
- Pickup-QR auth ordering verified: 401 → 404 → 403 in correct sequence

### Files changed (iter173)
- Backend: `routes/storage_auctions.py` (+pickup-qr endpoint, +_generate_pickup_qr_png_bytes, fixed Pydantic V1 dict()), `routes/deposits.py` (+POST /confirm endpoint), `services/email_notifications.py` (QR base64 embed in winner email), `models/storage_auction.py` (Pydantic V2 decorators), `services/subscription_pricing.py` (.model_dump()), `services/ai_assistant.py` (.model_dump() with fallback), `routes/subscriptions.py` (.model_dump() with fallback), `requirements.txt` (+qrcode==8.2)
- Frontend: `pages/storage/PromoteAuctionModal.js` (NEW), `pages/admin/AdminStorageAuctions.js` (NEW), `pages/storage/StorageDashboard.js` (Promote button), `pages/storage/StorageAuctionDetail.js` (Auto-Bid callout), `pages/AdminDashboard.js` (+secondary tab + data-testid), `components/SecurityDepositBanner.js` (REWRITE with Stripe Elements)

### GitHub push
Per Emergent platform policy, please use the **"Save to Github"** button in the chat input.

---

## Latest: P0 — Storage + Vehicle Sprint (May 1, 2026 / iter172) — 11/11 DONE

### 🔴 CRITICAL PROXY-BID BUG — FIXED
**Root cause**: `storage_auction_service.place_bid` was attributing the leader's auto-advance to the SUBMITTER's bid_record. When User B submitted max=$12 against User A (who held max=$25), the system pushed `{bidder_id: B, amount: $13}` — making it look like B auto-outbid themselves from $12 to $13.

**Fix** (services/storage_auction_service.py):
- `bid_record.amount` now ALWAYS equals the submitter's own `max_bid` (their intent)
- Leader auto-advances are never persisted as a separate bid_record — only `current_bid` advances at the auction level
- 2-second dedup window rejects rapid double-click identical submissions (returns `is_duplicate=True`)
- 6 regression tests lock the invariants

### Sprint deliverables (11/11)
1. **Bid-status badges (Item 1)** — StorageAuctionCard renders dual-language Leading/Outbid/No-Buyer-Fees badges based on `user.id` vs `winning_bidder_id`. Always bilingual per Bill 96.
2. **Auto-bid bot (Item 2)** — Marketplace setup_auto_bid already gates Premium/VIP/Partner/Business. Storage proxy is intrinsic to `place_bid` (every bid = max_bid ceiling). Proxy correctness locked in by iter172 tests.
3. **Homepage sections (Item 3)** — `HomepageLiveVehicles` + `HomepageLiveStorage` horizontal-scroll cards with bilingual headings, View All · Voir tout CTAs, skeleton loaders, auto-hide when 0 results.
4. **Facility promotion tiers (Item 4)** — 3 tiers (Basic $9.99/7d, Featured $24.99/14d, Premium $49.99/30d) with Stripe PaymentIntent flow + `/promote` + `/promote/confirm` endpoints.
5. **Promotion infrastructure (Item 5)** — `process_expired_promotions` hourly cron across `listings` + `vehicle_listings` + `storage_auctions`. Admin `grant-promotion` + `revoke-promotion` endpoints. Featured/premium badges render on cards.
6. **AI Concierge platform knowledge (Item 6)** — Injected authoritative truth into `ai_assistant_v2.SYSTEM_INSTRUCTIONS` — 3 auction types, fees per seller-tier + payment-method, subscription tiers, deposit system, pickup, auto-bid gating, Bill 96, contact.
7. **Admin storage controls (Item 7)** — New endpoints: facility reject/suspend/unsuspend/delete (cascades auctions), auction pause/resume/edit/delete/override-winner/force-close.
8. **Deposit payment flow (Item 8)** — Backend: `/api/my-storage-deposits` user endpoint. Frontend: `/storage-auctions/my-deposits` route with bilingual table (Authorized 🔒 / Applied ✅ / Refunded ✔️ / Forfeited ❌).
9. **Digital pickup code (Item 9)** — `generate_pickup_code()` → `BV-XXXX-XXXX`. Auto-generated at auction close. Prominently rendered in winner email. Facility endpoints: `verify-pickup-code` (200/404/409) and `mark-picked-up`. Admin `regenerate-pickup-code` re-sends email.
10. **Admin create auction (Item 10)** — `POST /api/admin/storage-auctions?facility_id=X` bypasses verified-facility guard; reuses same payload validators.
11. **All flows tested** — 72/72 effective tests pass across 4 storage suites; scheduler registers 11 jobs.

### Files changed (iter172)
- Backend: `services/storage_auction_service.py` (REWRITE — correct bid_record attribution + dedup), `services/scheduled_jobs.py` (+process_expired_promotions +generate_pickup_code), `services/scheduler.py` (+job 11), `services/email_notifications.py` (+pickup code block in winner email), `services/ai_assistant_v2.py` (system prompt update), `routes/storage_auctions.py` (+20 endpoints: promotion, admin controls, pickup code, admin create, my deposits)
- Frontend: `pages/storage/StorageAuctionCard.js` (REWRITE — dual-language Leading/Outbid/No-Fees badges + promotion badges), `pages/storage/MyStorageDeposits.js` (NEW), `pages/HomePage.js` (+HomepageLiveVehicles +HomepageLiveStorage), `App.js` (+/storage-auctions/my-deposits route)
- Tests: `tests/test_storage_proxy_bug_iter172.py` (NEW — 6 regression tests for the critical bug), `tests/test_storage_iter172_api.py` (NEW — 35 API tests, created by testing-agent)

### GitHub push
Per Emergent platform policy, please use the **"Save to Github"** button in the chat input to push these changes to your repo. All local commits are in place (auto-commits captured each tool call).

---

## Previous: P0 Storage Auctions — Scheduler + Emails + Admin Deposits + Public Stats + Homepage Promo + Bilingual Rule (May 1, 2026 / iter171) — DONE

### Scope (14/14 delivered)
1. **Auto-close scheduler (5-min cron)** — `scheduler.py:744-755` registers `storage_close_job` with `IntervalTrigger(minutes=5)`. Calls `services/scheduled_jobs.py::process_ended_storage_auctions` which:
   - Soft-close guard: extends `end_time` by `soft_close_extension_minutes` (default 10) when a bid landed within the last 10 min
   - Otherwise: flips status → `sold` (winner) or `unsold` (no bids), releases held deposits (winner→applied, losers→refunded), fires winner + facility emails, queues 5% commission invoice for cash/e-transfer, writes `storage_close_logs`
2. **Winner email bilingual per payment method** — `send_storage_auction_won_email(buyer, auction, facility, pricing)` branches on `auction.payment_method`:
   - Stripe → "BidVex has charged your card ${fee} + you pay ${hammer} via Stripe to facility"
   - Cash → "Pay ${hammer} CASH directly to facility — contact {facility_contact}"
   - E-Transfer → "Send ${hammer} via Interac e-Transfer to {facility_email}, Reference: BidVex Unit #{unit} – {your_name}"
   - All branches include mandatory cleanup-deadline forfeit notice (bilingual)
3. **Facility-sold email** — `send_storage_auction_sold_email(facility, auction, buyer)` with payment-method label + buyer contact
4. **Admin Deposits Dashboard** (`/admin` → Marketplace → Storage Deposits)
   - 4 KPI cards: Active Holds / Applied to Fees / Refunded / Forfeited (all bilingual)
   - Search + table (Bidder / Unit / Facility / Amount / Placed At / Status / Actions)
   - Release (green) + Forfeit (red) per-row buttons with confirmation modal (reason required for forfeit)
   - Backend: `GET /api/admin/storage-deposits` with enrichment (bidder_name / auction_unit_number / facility_name) + status filter
5. **Public stats endpoint** — `GET /api/storage-auctions/stats/public` (unauthenticated) returns `{total_sold, active_facilities, active_auctions, total_bids_placed}` zero-safe
6. **Stats bar on browse page** — Renders under hero when any stat > 0; hides zero cards per spec
7. **Homepage Storage Promo section** — Inserted after LiveAuctions in `HomePage.js`. Features animated padlock + sparkle + particle dots, dual-language badge "NEW FEATURE · NOUVELLE FONCTIONNALITÉ", EN title + italic FR title, 3 trust badges (all dual-language), live inline stats, dual-language CTAs "Browse Storage Auctions → · Parcourir les enchères →"
8. **Bilingual always-visible rule (Quebec Bill 96)** — Applied to all storage pages: Hero renders EN title in white `#FFFFFF` + FR title in cyan `#3FB4CB` directly beneath, every eyebrow/subtitle/CTA/badge shows EN + FR simultaneously. Admin Deposits page also fully bilingual.

### Files
- Backend: `services/scheduler.py` (+10 lines), `services/scheduled_jobs.py` (+180 lines new `process_ended_storage_auctions`), `services/email_notifications.py` (rewrote 2 functions), `routes/storage_auctions.py` (+90 lines for `/stats/public` + `/admin/storage-deposits`)
- Frontend: `pages/storage/StorageHero.{js,css}` (dual-language rewrite), `pages/storage/StorageAuctionsBrowse.js` (stats bar + bilingual banner), `pages/HomePage.js` (new `StorageAuctionsPromo` component), `pages/admin/AdminStorageDeposits.js` (NEW), `pages/AdminDashboard.js` (wired tab + case)

### Testing — 31/31 green
- `test_storage_payment_deposit_iter170.py` — 10/10 unit regression pass
- `test_storage_iter171_api.py` (testing-agent) — 21/21 API integration pass (public stats, admin deposits CRUD, scheduler registration, email coroutine validation per-method, 402 bid-guard regression)
- Zero critical; zero minor (type-hint drift on two email functions fixed post-test via `bool(...)` coercion)
- Live screenshots: bilingual hero + stats bar, homepage promo with inline live stats, admin deposits dashboard with 4 KPIs + bilingual table empty state

### Live verification artifacts
- `/var/log/supervisor/backend.err.log` → "Scheduler initialized with 10 jobs" (job #10 = storage auto-close)
- `GET /api/storage-auctions/stats/public` → `{"total_sold":0,"active_facilities":1,"active_auctions":3,"total_bids_placed":2}`
- Homepage `/` screenshot shows storage promo section below hero with live stats inline
- Storage Browse `/storage-auctions` screenshot shows stats bar `1 Facility / 3 Live / 2 Bids` below bilingual hero

---

## Previous: P0 Storage Auctions — Payment Method Choice + Deposit System (May 1, 2026 / iter170) — DONE

### Spec
Facility chooses payment method per listing (Stripe / Cash / E-Transfer). Optional participation deposit configured per auction. 4 frontend polish fixes (white hero title + bilingual content swap, footer restored, 3-step facility registration, listing-create payment+deposit UI). Backend pricing rewritten for 3 methods + Stripe Connect Express on facility registration + deposit hold/release/forfeit lifecycle + bid guard (HTTP 402 when deposit required).

### Source-of-truth math (3 spec proofs — verified to the cent)
- **Stripe path** ($800 QC + $100 deposit) → buyer pays $874.34, remaining at pickup $774.34, facility receives full $800 hammer
- **Cash path** ($800 QC + $100 deposit) → buyer pays $700 cash to facility, BidVex invoices facility $47.67 (40 fee + 1.46 stripe + 6.21 tax), facility net $752.33
- **E-Transfer** ($1500 ON, no deposit) → buyer pays $1500 e-transfer, facility owes BidVex $87.55 (75 fee + 2.48 stripe + 10.07 HST), facility net $1412.45

### Backend
- **`services/storage_pricing.py`** — Rewritten with branching for Stripe (BidVex collects 5% + stripe + tax from BUYER, facility nets full hammer) vs Cash/E-Transfer (BidVex invoices FACILITY 5% + stripe + tax). All 3 spec proofs assert at module load.
- **`services/storage_deposit_service.py`** (NEW) — `create_deposit_hold` (Stripe PaymentIntent capture_method=manual), `release_deposits_on_close` (winner→applied/canceled, losers→refunded/canceled), `forfeit_deposit` (capture as penalty when winner doesn't pay).
- **`models/storage_auction.py`** — `StorageAuctionCreate` adds single `payment_method` (validator + 422 on invalid), `deposit_required`, `deposit_amount` (validator: required >0 if deposit_required=true with bilingual error). NEW `StorageDepositRequest` model.
- **`routes/storage_auctions.py`**:
  - `POST /storage-facilities/register` now creates Stripe Connect Express account (CA, MCC 4225, transfers+card_payments capabilities) and returns `stripe_onboarding_url`. Graceful degradation if Stripe rejects (returns null URL, doesn't 500). 409 on duplicate with bilingual error.
  - `POST /storage-facilities/auctions` validates payment_method ∈ {stripe,cash,etransfer}, deposit_required+amount, persists single payment_method on the auction doc.
  - `POST /storage-auctions/{id}/bid` → **NEW deposit guard** returns HTTP 402 with `{error, deposit_amount, message_en, message_fr, action: "pay_deposit"}` when deposit required and not paid.
  - `POST /storage-auctions/{id}/deposit` (NEW) — buyer authorizes deposit via Stripe PI manual-capture. Idempotent (returns existing held deposit).
  - `GET /storage-auctions/{id}/pricing` accepts `payment_method` + `deposit_amount` query params, returns the new buyer/facility invoice shape.
  - `POST /admin/storage-auctions/{id}/release-deposits` and `/forfeit-deposit` (NEW) — admin-only manual deposit lifecycle controls.
  - `PUT /admin/storage-auctions/{id}/cancel` now releases held deposits.

### Frontend
- **`pages/storage/StorageHero.{js,css}`** — Title `Trésors cachés. Révélés.` rendered in pure `#FFFFFF` with text-shadow. Removed dual-language secondary lines. Single content map per language (EN/FR) with eyebrow/line1/line2/subtitle/CTAs/4 badges all swapping based on `i18n.language`.
- **`components/Footer.js`** — Removed Storage Auctions section (was 25-line subsection). Global footer restored to `How It Works | About Us | Community | Privacy Policy | Terms of Service | Contact Support | Cookie Settings | Social icons | Copyright`.
- **`pages/storage/StorageFooterBanner.js`** (NEW) — Contextual "Do you manage a storage facility?" banner rendered ONLY on storage routes (Browse, Detail, Dashboard, Policies×3, Register).
- **`pages/storage/StorageAuctionsBrowse.js`** — Updated transparency banner: "No buyer fees on cash/e-transfer auctions. Stripe fee + taxes apply on Stripe-payment auctions."
- **`pages/storage/StorageAuctionCreate.js`** — Replaced multi-checkbox `payment_methods_accepted` with single `payment_method` selector (3 colored cards with bilingual descriptions). Added deposit toggle + amount input with live UX preview of who pays what.
- **`pages/storage/StorageFacilityRegister.js`** — Rewritten as 3-step wizard (Step 1: Facility Info → Step 2: Business Credentials w/ NEQ + OPC permit if QC → Step 3: Stripe Setup + T&C). Submit returns Stripe onboarding URL → redirects user to Stripe.
- **`pages/storage/StoragePolicies.js`** — Updated Section 4 ("No Buyer Fees" → "Buyer Fees Depend on Payment Method") to match new pricing rules. Added `<StorageFooterBanner />` to all 3 exported components.

### Tests
- `/app/backend/tests/test_storage_payment_deposit_iter170.py` — **10/10 unit pass** (3 spec proofs + AB tax + unknown province + 5 Pydantic validation tests)
- `/app/backend/tests/test_storage_iter170_api.py` (testing-agent created) — **16/16 API integration pass**
- Total: **26/26 storage tests green**, zero critical/minor blockers.

### Verification artifacts
- Live screenshots: hero EN white title, hero FR white title (no English bleed), Storage Browse with new banner + storage footer, 3-step register wizard rendering, listing-create payment selector with Cash highlighted + deposit toggle/amount input populated.
- Module-load proofs: all 3 buyer/facility invoice spec values (Proof 1/2/3) match to the cent.

### Files changed
- backend: `services/storage_pricing.py`, `services/storage_deposit_service.py` (NEW), `models/storage_auction.py`, `routes/storage_auctions.py`
- frontend: `pages/storage/StorageHero.{js,css}`, `pages/storage/StorageFooterBanner.js` (NEW), `pages/storage/StorageAuctionsBrowse.js`, `pages/storage/StorageAuctionCreate.js`, `pages/storage/StorageFacilityRegister.js`, `pages/storage/StorageAuctionDetail.js`, `pages/storage/StorageDashboard.js`, `pages/storage/StoragePolicies.js`, `components/Footer.js`

---

## Previous: P3/P2 Final Polish + Live Auctions Pill (Apr 27 PM, 2026) — DONE
- Footer GET /api/site-config/legal-pages: 500 → 200 (defensive isinstance guards + graceful fallback)
- NotificationListener WS: silent error handling, 5-attempt exponential backoff, no console spam
- Vehicle + General invoice PDFs fully bilingual EN/FR (body, line items, tax labels with combined 14.975%, payment instructions, footer)
- New `GET /api/stats/public` + Hero live-auctions pill (renders only when active_auctions > 0)
- Tests: iter159 — 7/7 backend, frontend 100%, zero issues

## Latest: P0 Final Pre-Launch Fixes (Apr 27, 2026 AM) — DONE

### 6/6 P0 fixes shipped (all verified by iter158 — 100% backend + frontend)
1. **Google OAuth + Profile Settings**
   - AuthPage now redirects to `https://auth.emergentagent.com` (no env-var dependency)
   - Profile page adds: read-only Email + "Change Email" button + Province dropdown (13 CA provinces/territories, bilingual)
   - New endpoints: `POST /api/auth/email-change/{request,confirm}` — Law 25 compliant double-opt-in (verification link sent to NEW email, change applied only after click, all sessions invalidated)
2. **AI Chatbot graceful fallback** — 30s hard timeout + amber "Service degraded" banner + auto-recovery on next success + email-support action button
3. **Tap-to-toggle InfoTip** — controlled state, opens on click/hover/focus, closes on outside-pointer-down (mobile-first)
   - Buyer Dashboard: 6 bilingual tooltips (header, 3 stat cards, tabs section, hint)
   - Seller Dashboard: 5 bilingual tooltips (commission rate + 4 stat cards)
4. **Image compression** — `services/image_compression.py` (Pillow 12.1) compresses base64 listing images to JPEG 800px@85% (~60-94% size reduction). Cache-Control 1y already in middleware for image extensions
5. **Farm Equipment deleted** — DB migrated (categories collection + listings + multi_item_listings + nested lots). FilterBar.js + admin_ops CFIA list updated. `/api/categories` cache invalidated.
6. **Hero stats removed** — 50K+ / 10K+ / $2M+ / 99.9% stat cards deleted (Option A: clean hero, no replacement)

### Files changed
- backend/routes/auth.py (+ email-change endpoints, asyncio import)
- backend/routes/profiles.py (province/city/postal_code added to allowed_fields + ProfileUpdate)
- backend/routes/listings.py (compress_image_list applied to single & multi-item)
- backend/routes/admin_ops.py (CFIA list cleaned)
- backend/services/image_compression.py (NEW — Pillow compression)
- backend/scripts/migrate_farm_equipment.py (NEW — one-shot migration, executed)
- frontend/src/pages/{HomePage,ProfileSettingsPage,BuyerDashboard,SellerDashboard,AuthPage}.js
- frontend/src/components/{InfoTip,AIAssistant,FilterBar/FilterBar}.js

### Tests
- iter158: 9/9 backend pass, frontend 100%, no critical/minor issues
- Test file: /app/backend/tests/test_prelaunch_fixes_158.py

---

## Previous: Vehicle Payment OPC Compliance (Feb 15, 2026) — DONE
- BidVex never holds vehicle hammer price; buyer charged only 2.5% fee + Stripe recovery + tax-on-fee
- $500 deposit migrated to Stripe `capture_method="manual"` (true HOLD)
- Tests: 14/14 backend pass (iter153)

## Previous: SendGrid Full Integration (Apr 20, 2026) — DONE
- 88 template IDs (44 keys × EN/FR), Event Webhook with HMAC validation
- Live E2E: 5/5 passed

## Other major shipped items
- Admin Panel Audit & Polish (23 sections)
- Marketplace Filter Bar / Sidebar
- Cloudflare CDN Optimization
- About Us page
- Stripe Connect destination charges for partners
- Subscription lifecycle, branded PDF invoices, price-breakdown UI

## Backlog
- (P1) Marketplace approve/reject status workflow (architecture decision needed)
- (P1) Advanced analytics aggregation (top sellers, conversion rate)
- (P2) Custom date range picker on admin analytics
- (Enhancement) Dispute resolution & admin offline order management
- (Enhancement) Scheduler job to auto-capture $500 deposit when fee invoice goes unpaid past deadline
- (Enhancement) "Recently Sold" rolling ticker beside the Live Auctions pill once you have ~10+ active listings

## Test credentials
- Admin: `charbel911@gmail.com` / `Anderosli123!@#` (role=admin)
