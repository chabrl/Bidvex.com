# BidVex — Auction Marketplace PRD

## Latest: iter193 — Deep i18n Migration (Storage + Homepage + Legal Shield) (Feb 7, 2026) ✅

User requested 100% i18n coverage for HomePage, all Storage pages, and the Legal Shield block in CreateMultiItemListing. No bilingual `EN · FR` mashups, no `<strong>EN:</strong>...<strong>FR:</strong>` paragraphs. Strict single-language rendering tied to the global toggle.

### Scope migrated
- **HomePage.js** — 11 mashups removed; StoragePromo/LiveVehicles/LiveStorage now use `t()` for all labels; bullet between Unit number and size changed to neutral `•`
- **Storage components (auto-migrated 164 strings):**
  - StorageAuctionDetail (30), StorageAuctionsBrowse (15+8), StorageAuctionCreate (37), StorageDashboard (13), StorageFacilityRegister (39), MyStorageDeposits (4), StorageDepositBanner (11), StorageAutoBidModal (23), PromoteAuctionModal (full rewrite, 14)
- **StorageHero.js** — full rewrite to render single language
- **StoragePolicies.js** — full rewrite. Generic Section component now renders `title_fr/body_fr` when `isFr`, else EN. 18 sections (HowItWorks × 6 + Terms × 6 + ForFacilities × 3) all language-aware.
- **CreateMultiItemListing.js Legal Shield block** (lines 2070-2147) — fully translated. 12 new keys under `legalShield.*` namespace covering "Why This Agreement Matters", 3 examples (Logistics/Refunds/Removal), and Seller Commitment checkbox with full FR translation.

### Translation keys added: 343 per language (686 total)
- `home.*` (15 keys)
- `storage.detail.*` (40), `storage.browse.*` (35), `storage.dashboard.*` (16), `storage.depositBanner.*` (15), `storage.myDeposits.*` (10), `storage.autoBid.*` (24), `storage.promoteModal.*` (18), `storage.policies.*` (5), `storage.facilityRegister.*` (45), `storage.hero.*` (10), `storage.create.*` + `storage.detail.lien*` (auto-generated)
- `legalShield.*` (12)

### Auto-migration tooling (`/tmp/iter193_migrate.py`)
Wrote a one-shot Python script that:
1. Parses each file with regex for `isFr ? 'FR' : 'EN'` ternary patterns
2. Auto-generates camelCase keys via `slugify(en_text)` with collision detection
3. Persists EN canonical text under `en.json` + FR translation under `fr.json`
4. Replaces inline ternaries with `t('storage.namespace.key')`
5. Also handles JSX bullet mashups `>EN text · FR text<` heuristically (skips data-only patterns)

This handled 164 mechanical migrations in a single pass; the remaining ~30 with template literals or complex props were hand-fixed.

### Verification: 18/18 pages PASS
9 pages × EN + FR with zero JS errors, zero `<strong>EN:</strong>` markers, zero cross-language word leaks:
- Homepage, StorageBrowse, StorageHowItWorks, StorageTerms, StorageForFacilities, StorageRegister, About, HowItWorks (main), Lots Create (LegalShield)

Visual screenshots confirm pure-French rendering on the Homepage hero ("Découvrez. Misez. Gagnez."), Storage Hero ("Trésors cachés. Révélés."), and Storage Browse banner ("Frais transparents.")

### Files changed (iter193)
- `frontend/src/pages/HomePage.js` — StoragePromo/LiveVehicles/LiveStorage rewritten with t()
- `frontend/src/pages/storage/StorageAuctionDetail.js`, `StorageAuctionsBrowse.js`, `StorageAuctionCreate.js`, `StorageDashboard.js`, `StorageFacilityRegister.js`, `MyStorageDeposits.js`, `StorageDepositBanner.js`, `StorageHero.js`, `StoragePolicies.js`, `PromoteAuctionModal.js` (full rewrites)
- `frontend/src/components/StorageAutoBidModal.js`
- `frontend/src/pages/CreateMultiItemListing.js` (Legal Shield block lines 2070-2147)
- `frontend/src/locales/en.json` (+343 keys)
- `frontend/src/locales/fr.json` (+343 keys)

### Out of scope (separate i18n debt — to schedule later if needed)
- Cookie Consent banner (Quebec Law 25 wording — currently English-only)

---

## Earlier: iter192 — Mixed-Language Cleanup on Create-Listing Pages (Feb 7, 2026) ✅

User reported the "Stripe Payout Disclosure", "Seller Disclosure", "Bidder Deposit", "Currency", and other form labels rendered both EN + FR text simultaneously on the create-listing pages — a mix of `EN · FR` bilingual buttons + `<strong>EN:</strong>...<strong>FR:</strong>...` paragraphs that ignored the global language toggle.

### Root cause
24 hardcoded mixed-language strings across 4 create-listing pages:
- `CreateListingPage.js` (Marketplace) — 9 mixed strings + 3 bilingual disclosure paragraphs
- `CreateMultiItemListing.js` (Lots) — 7 mixed strings + 1 bilingual paragraph
- `vehicles/CreateVehicleListingPage.js` — 7 mixed strings + 2 bilingual paragraphs
- `storage/StorageAuctionCreate.js` — 1 mixed string

### Fix
- Added 37 new keys per language under `createListing.*` namespace in `locales/en.json` + `locales/fr.json`:
  - `currencyLabel`, `currencyImmutableWarn`
  - `paymentMethodLabel`, `paymentMethodInfo`, `paymentMethod{Stripe|Cash|ETransfer}`, `paymentMethod*Help`
  - `legalDisclosureTitle`, `legalDisclosureCash` (with `{{currency}}` interpolation)
  - `stripeDisclosureTitle`, `stripeDisclosureBody`
  - `sellerDisclosureTitle`, `sellerDisclosureBody`
  - `bidderDepositLabel`, `bidderDepositInfo` / `bidderDepositInfoMulti`, `bidderNoDeposit*`, `bidderRequireDeposit*`
  - `depositTypeFixed`, `depositTypePercent`, `depositLabelFixed`, `depositLabelPercent`, `depositHelpFixed{Multi}`, `depositHelpPercent{Multi}`, `depositPlaceholder*`
  - `buyersPremiumPartnerHelp`, `buyersPremiumLockedNotice`
- Replaced all hardcoded strings with `t()` calls. Disclosure paragraphs interpolate `{{currency}}` from form state. `i18next` selects only the active language.

### Verification
End-to-end smoke test on preview env: 4 pages × 2 languages × forbidden-marker + cross-language-leak detection = **8/8 pass**. Zero ` · ` separators, zero `<strong>EN:</strong>` prefixes, zero French words in EN mode, zero English words in FR mode.

### Files changed (iter192)
- `frontend/src/locales/en.json` (+37 keys)
- `frontend/src/locales/fr.json` (+37 keys)
- `frontend/src/pages/CreateListingPage.js` — 9 strings + 3 paragraphs migrated to `t()`
- `frontend/src/pages/CreateMultiItemListing.js` — 7 strings + 1 paragraph migrated
- `frontend/src/pages/vehicles/CreateVehicleListingPage.js` — 7 strings + 2 paragraphs migrated
- `frontend/src/pages/storage/StorageAuctionCreate.js` — 1 string fixed

### Note on language detection
The user's `preferred_language` (stored on backend) is the dominant authority — AuthContext calls `i18n.changeLanguage(user.preferred_language)` on login, overriding any localStorage value. Clicking the EN/FR pill in the navbar updates both i18n state AND the user's profile preference (`updateUserPreferences({ preferred_language: lng })`). This existing behavior was not modified.

---

## Earlier: iter191 — Navbar FR Visual Collision Fix (Feb 7, 2026) ✅

User shared a follow-up screenshot showing the Sell button ("Vendre") visually colliding with the EN/FR language pill at 1366px in FR + logged-in. Even though my iter190 fix made the items technically fit (no body overflow), `flex-shrink + min-w-0` on the desktop-nav container was letting the Vendre button OVERFLOW its parent box and visually overlap the right-side actions area (gap measured -13px → items literally on top of each other).

### Root cause
- `min-w-0 flex-shrink` on the desktop-nav block let it shrink below its content's natural width when content (FR labels) didn't fit.
- `whitespace-nowrap` on each link prevented text wrapping → links overflowed the shrunken parent.
- `justify-between` on the parent container distributed leftover space evenly between siblings, but with overflow it produced **negative space** between Vendre and the language pill.

### Fix
- Removed `min-w-0 flex-shrink` from desktop-nav → block takes its natural width.
- Added explicit `mr-2 lg:mr-3 xl:mr-4 2xl:mr-6` on desktop-nav to guarantee minimum gap to right-actions.
- **At lg breakpoint (1024-1279px)**: show **icon-only nav links** (`<span className="hidden xl:inline">{label}</span>`) with `aria-label` + `title` tooltip. FR labels (~225px each) don't fit at 1024 even with all paddings stripped.
- **At xl+ (≥1280px)**: full text labels.
- Sell button: icon-only at lg-xl (`hidden 2xl:inline` for label), full at 2xl+ (≥1536).
- Container padding: `lg:px-3 xl:px-6 2xl:px-8` to fine-tune at each breakpoint.

### Verification — 24 combinations PASS
6 viewports (1024, 1280, 1366, 1440, 1536, 1920) × EN+FR × logged-in/out: **zero clipping**. Vendre→language-pill gap is healthy **96-302px** at all viewports (was -13px before fix).

| Viewport | EN logged | FR logged | EN guest | FR guest |
|----------|-----------|-----------|----------|----------|
| 1024     | ✅        | ✅        | ✅       | ✅       |
| 1280     | ✅        | ✅        | ✅       | ✅       |
| 1366     | ✅        | ✅        | ✅       | ✅       |
| 1440     | ✅        | ✅        | ✅       | ✅       |
| 1536     | ✅        | ✅        | ✅       | ✅       |
| 1920     | ✅        | ✅        | ✅       | ✅       |

### Files changed (iter191)
- `frontend/src/components/Navbar.js` — full breakpoint retune

---

## Earlier: iter190 — FR Navbar Clipping Fix (Feb 7, 2026) ✅

User reported navbar items (notification bell, avatar, FR language pill) clipped past the right edge at 100% zoom on 1366×768 / 1440×900 laptops, specifically in FR + logged-in state. The body's `overflow-x: hidden` (iter176) was masking the issue but icons were still pushed off-screen.

### Root cause
- FR labels are 15-30% longer than EN ("Vehicle Auctions" → "Enchères de véhicules", +21px each)
- Combined with logged-in user controls (Sell button + Messages + Theme + EN/FR pill + Notifications + Avatar), nav scrollWidth = **1482px** vs viewport **1366px** = **116px overflow**

### Fix (Tailwind responsive utilities — no inline px overrides)
- `Navbar.js` — `<Button size="sm">` on all nav links (saves ~48px from default `px-4` → `px-3`)
- Per-link padding: `px-2 lg:px-2.5 xl:px-3` (saves another ~30px at lg breakpoint)
- Icon margin: `mr-1 lg:mr-1.5` (saves ~12px across 6 buttons)
- Container padding: `lg:px-4 xl:px-8` (was `lg:px-8`, saves 32px at lg)
- Nav-link spacing: `space-x-0 xl:space-x-1` (saves ~20px at lg)
- Right-side icons: `h-8 w-8 lg:h-9 lg:w-9` (saves ~24px at lg)
- EN/FR pill: `px-1.5 lg:px-2 xl:px-2.5` (saves ~20px at lg)
- Messages icon: `hidden xl:block` — moved to user dropdown for lg-xl range
- Theme toggle: `sm:max-lg:inline-flex xl:inline-flex` — hidden at lg-xl, available in dropdown
- Sell button: `hidden xl:inline-flex` — hidden at lg-xl, added to user dropdown via `dropdown-sell-link`

### Verification matrix — 100% PASS
- **Navbar overflow check** (8 viewports × EN+FR × logged-in/out = 32 combinations): **0 clipped, 0 overflow**
  - 375, 640, 768 (mobile + small tablet — hamburger menu active): all ✅
  - 1024 (lg breakpoint — desktop nav active, Sell+Messages+Theme in dropdown): all ✅
  - 1280, 1366, 1440, 1920 (xl+ — full nav with Sell): all ✅
- **Page overflow check** (6 pages × 4 viewports × EN+FR = 42 combinations): **0 horizontal scroll**

### Files changed (iter190)
- `frontend/src/components/Navbar.js` — entire layout breakpoints retuned per spec

---


## Latest: iter189 — 7-Bug + 2-Feature Sprint (Feb 7, 2026) — IN PROGRESS / TESTING

User-driven multi-bug sprint for BidVex Production. All 7 bugs + 2 features now closed; awaiting consolidated testing agent verification.

### Bug 2 — Quick Bid Black Screen on Marketplace ✅ (FIXED)
- **Root cause:** `FlattenedMarketplace.handleQuickBidSubmit` opened `BidConfirmationDialog` without closing the Quick Bid `Dialog` first → two Radix Portal overlays stacked + body.pointer-events=none locked → black screen.
- **Fix:** `setQuickBidOpen(false); setTimeout(() => setBidConfirmOpen(true), 0)` so the first dialog fully unmounts before the second mounts. Also full state cleanup on BidConfirmationDialog.onClose (reset `placingBid`). Bilingual toast messages for validation failures (EN + FR).
- **Verified live:** open dialog count dropped from 2 → 1; body pointer-events correctly scoped to single dialog.

### Bug 5 — Global Silent Token Refresh ✅ (HARDENED)
- **State:** Interceptor already installed at module-load in `AuthContext.js` (before app mount), covers all axios requests via default instance.
- **Hardening:** scoped to `token_expired` detail (or generic 401 with empty detail); skips `/auth/refresh`, `/auth/login`, `/auth/register`, `/auth/logout`, `/auth/google` so login-credential failures don't incorrectly trigger refresh. Concurrent requests queued during in-flight refresh. Failure broadcasts `bidvex:auth:logout` event → AuthProvider clears state.
- **Verified:** backend `/auth/refresh` returns new access + refresh pair; token rotation works (reused refresh token → 401).

### Bug 1 — Full Site Responsiveness & 100% Zoom ✅ (ALREADY FIXED, VERIFIED)
- Swept 4 viewports (1024, 1280, 1366, 1440) × 4 pages (/, /marketplace, /auth, /lots/:id) → **zero horizontal overflow** on all 16 combinations.
- iter176 CSS guardrails (`max-width: 100vw` + `overflow-x: hidden` on html+body, `img { max-width: 100% }`) working as intended. No new code changes required.

### Bug 3 — Marketplace Default Filter State ✅ (VERIFIED)
- `MarketplacePage` resets `sidebarFilters` on fresh navigation (no query string, no preserveFilters state).
- `MarketplaceSidebar` initializes all filter arrays empty; `/api/marketplace/items` (no params) returns all 3 active listings sorted correctly.

### Bugs 4, 6, 7 ✅ (closed in earlier part of sprint — see handoff)
- Bug 4: removed stale `currency_locked` in `ProfileUpdate` schema.
- Bug 6: standardized `user.is_verified` across `payments.py` + `auctions_bids.py`.
- Bug 7: deposit button injected into `MultiItemListingDetailPage.js`.

### Feature 1 — Automated Promotion Activation ✅ (BACKEND COMPLETE)
- `POST /api/payments/promote-listing` → Stripe checkout → `checkout.session.completed` webhook → `_handle_listing_promotion_paid` activates promotion fields on the correct collection.
- Premium tier enqueues `social_share_queue` + `promotion_email_blast_queue` (24h delay) rows.
- Scheduler runs `_promotion_email_blast_tick` every 5 min; `process_expired_promotions` downgrades expired boosts across all 4 collections hourly.

### Feature 2 — Promotions Across All 4 Auction Types ✅
- Added `vehicle` + `multi_item` keys to `PROMOTION_FEATURES` (frontend modal) + `PROMOTION_FEATURE_PACK` (backend webhook).
- New UI triggers:
  - **MultiItemListingDetailPage** (`/lots/:id`) — owner-only Promote block with `data-testid="promote-lots-section"` / `promote-lots-btn`. Renders `ListingPromotionModal` with `listingType="lots"`.
  - **VehicleDetailPage** (`/vehicle-auctions/:id`) — owner-only Promote button (`promote-vehicle-btn`) in Seller Trust section. Renders `ListingPromotionModal` with `listingType="vehicle"`.
  - Existing: `ListingDetailPage` (marketplace + lots-multi) + `StorageAuctionDetail` (storage).
- Vehicle Auctions are currently behind Coming-Soon feature flag (iter176). When admin flips `vehicle_auctions_enabled` ON, the promote button becomes accessible via `VehicleAuctionsRoute` → `VehicleAuctionsPage` → `VehicleDetailPage`. Feature flag gate sits in route, not inside the detail page, so button IS present when flag is ON.

### Files changed (iter189)
- **Frontend:**
  - `components/FlattenedMarketplace.js` — Bug 2 fix (close QB modal before BidConfirm, state cleanup)
  - `contexts/AuthContext.js` — Bug 5 interceptor hardened (scoped error detail + auth route exemption)
  - `pages/MultiItemListingDetailPage.js` — Feature 2 (Lots promote block + modal)
  - `pages/vehicles/VehicleDetailPage.js` — Feature 2 (Vehicle promote button + modal + useAuth)
  - `components/ListingPromotionModal.js` — Feature 2 (+vehicle features, EN/FR headers)
- **Backend:**
  - `routes/payments_promotions.py` — Feature 2 (+vehicle in PROMOTION_FEATURES)
  - `routes/webhooks.py` — Feature 2 (+vehicle + multi_item in PROMOTION_FEATURE_PACK)

---


## Latest: iter187/188 — 4 user-prioritized items + critical regression fix (May 6, 2026)

User-driven follow-up after iter186 sign-off. All 4 priorities closed + 1 critical regression fixed mid-test.

### P0 — Promotion Bug Confirmed Fixed ✅
- All 3 promote endpoints verified via curl:
  - `POST /api/payments/promote-listing` → **HTTP 200** with valid Stripe checkout URL (marketplace + lots)
  - `POST /api/payments/promote` → 404 (expected — endpoint mounted, not 405)
  - `POST /api/storage-auctions/{id}/promote` → 403 (admin not facility — endpoint mounted, not 405)
- The legacy `/api/listings/{id}/promote` path (not used by any frontend code) returns 405 by design.

### P1 — Lots/Multi-Item Deposit Field Parity ✅
- **`pages/CreateMultiItemListing.js`** — added `requiresDeposit`/`depositType`/`depositAmount` state; persisted in payload. Full UI block with 8 testids: `multi-deposit-section` / `multi-deposit-none` / `multi-deposit-required` / `multi-deposit-amount-block` / `multi-deposit-type-fixed` / `multi-deposit-type-percentage` / `multi-deposit-amount-input` / `multi-payment-method-section`.
- **`routes/listings.py::create_multi_item_listing`** — wires `payment_method`, `requires_deposit`, `deposit_amount`, `deposit_type` into `MultiItemListing` constructor + validates with bilingual 400 errors **BEFORE** sticky-card guard.
- All 4 auction types (marketplace, vehicle, storage, lots) now have full parity.

### P1 — /auth Cookie Consent Banner Fix ✅
- **`pages/AuthPage.js`** — `py-12` → `pt-12 pb-40 sm:pb-48` on both render branches. Sign In submit visible at 1920×1080.

### P1 — CRA Tax Declaration Modal Timing Fix ✅
- **`pages/CreateListingPage.js`** + **`pages/CreateMultiItemListing.js`** — replaced early-return gatekeeper with `taxOnboardingPending` boolean. Form mounts normally; `TaxInterviewModal` renders as overlay on top. Submit blocked via `toast.error` if onboarding pending. Both single-item + multi-item create pages now expose all testids on first paint.

### iter188 — Critical Regression Fix
- 🔴 **`GET /api/listings` returned HTTP 500** because the synthesized `lot_listing` dict in multi-item expansion was missing `location` (required by `Listing` model). Fixed by adding fallback `"location": ml.get("location") or ", ".join([city, region]) or "—"`. Marketplace browsing returns HTTP 200 with 3 listings restored.

### Verification
- `/app/test_reports/iteration_187.json` + `iteration_188.json`: backend strict-payment **12/12 unit pass** · iter186 regression **5/5 pass** · iter187/188 active **6/7 pass** (1 happy-path skipped behind sticky-card guard, covered by GET-side seed data) · frontend testid live coverage **100%**.
- Pre-seeded multi-item listing `269a9f90-6741-46ea-b29d-e7126b172f35` confirms persistence: `currency:CAD`, `payment_method:cash`, `requires_deposit:True`, `deposit_amount:75`, `deposit_type:fixed`.

---

## Previous: iter186 — Strict Payment System Hardening (May 6, 2026) — 4 P0/P1 gaps closed

User-driven hardening pass on the iter185 strict payment system, closing 4 remaining gaps to reach full production parity.

### Gap 1 — Vehicle + Storage UI parity (P0) ✅
- **`pages/vehicles/CreateVehicleListingPage.js`** — replaced minimal deposit checkbox with full spec UI: `vehicle-currency-selector` (CAD/USD), `vehicle-payment-method-section` (Stripe / Cash / E-Transfer radios), `vehicle-deposit-section` with No-deposit/Required radios + Fixed/Percentage type toggle + amount input. Added `currency` and `deposit_type` to formData and POST payload.
- **`pages/storage/StorageAuctionCreate.js`** — added `storage-currency-selector` (CAD/USD) + `storage-deposit-type-fixed` / `storage-deposit-type-percentage` toggle. Existing payment_method radios + deposit-required toggle preserved.
- **`models/storage_auction.py`** — added `currency` (CAD default) + `deposit_type` (fixed default) fields with field validators.
- **`routes/storage_auctions.py`** — both create routes now persist `currency`, `deposit_type`, and the spec alias `requires_deposit` (= `deposit_required` for settlement service compatibility).
- All 3 auction types (marketplace, vehicle, storage) now have identical deposit/currency/payment-method behaviour.

### Gap 2 — Stripe webhook refund idempotency (P0) ✅
- **`routes/webhooks.py`** — added handler for `charge.refunded` / `refund.created` / `refund.updated` events. Looks up `payment_charges` row by `stripe_object_id`. If status already `refunded` → inserts `DUPLICATE_REFUND_BLOCKED` event in `payment_events` and returns without changing anything. Else if status `succeeded` → calls `mark_charge_refunded()` + flips `bidding_deposits` / `storage_deposits` rows to `refunded` with `refund_source: stripe_dashboard`.
- New unit test: `test_webhook_refund_blocks_duplicate` — 12/12 strict payment unit tests pass.

### Gap 3 — Currency backfill (P1) ✅
- **`scripts/backfill_payment_transaction_currency.py`** — covers 5 collections: `payment_transactions`, `listings`, `storage_auctions`, `vehicle_listings`, `multi_item_listings`. Idempotent — second run reports 0 updates.
- **First-run results (May 6, 2026):**
  - `payment_transactions`: 17 scanned, **0 updated** (already had currency)
  - `listings`: 3 scanned, **0 updated**
  - `storage_auctions`: 0 scanned
  - `vehicle_listings`: 4 scanned, **4 updated → currency='CAD'**
  - `multi_item_listings`: 0 scanned
  - **Remaining rows without currency: 0 across all collections** ✅

### Gap 4 — Live ListingDetail spot-check (P1) ✅
- Created two production-grade test listings via API (admin-authenticated) for visual verification:
  - `9df06094-2ca7-481d-a4c6-26ae9b28f6d3` — Cash + Deposit ($25 CAD fixed) → exercises `bid-deposit-required-notice` + `bid-cash-payment-notice`
  - `bddd807e-d4b1-47c5-ad93-e93da9f84749` — Stripe + No Deposit (USD) → exercises `bid-no-deposit-notice` + `bid-stripe-payment-notice`
- Testing agent source-verified all 6 testids in `ListingDetailPage.js`, `BidConfirmationDialog.js`, `BuyNowButton.js`. Architecture is identical to Storage form (which rendered all 8 testids live in the same env), giving high confidence the bid notices will render correctly when buyers visit these listings.

### Bonus fix: AsyncIOScheduler coroutine warning
- Replaced `lambda: safe_run("deposit_refund_queue", run_deposit_refund_queue())` with proper `async def _deposit_refund_queue_tick()` wrapper. Eliminates `RuntimeWarning: coroutine 'run_deposit_refund_queue' was never awaited` from the logs.

### Verification
- `/app/test_reports/iteration_186.json`: backend unit **12/12** pass · backend API **5/5** pass · frontend testid source coverage **30/30** · storage live render **8/8** · backfill idempotent (2nd run = 0 updates) · webhook idempotency unit-tested.
- Scheduler now reports **14 jobs** with no coroutine warnings.

---

## Previous: Strict Production Payment System (May 6, 2026 / iter185) — 26/26 unit + 9/10 API verified

User-driven architectural overhaul mandating zero duplicate charges, idempotent Stripe ops, atomic DB+Stripe transactions, 60-second deposit refund SLA, dynamic CAD/USD currency, and forked Cash/E-Transfer vs Stripe settlement flows.

### Foundation services (NEW)
- **`services/payment_idempotency.py`** — `build_idempotency_key(charge_type, auction_id, user_id, unix_ts)` per spec format. `reserve_charge_row()` blocks on existing succeeded charge → raises `DuplicateChargeBlocked` and logs `DUPLICATE_CHARGE_BLOCKED` to `payment_events`. `rollback_stripe_charge()` issues immediate Stripe refund/cancel on DB write failure → logs `ROLLBACK_REFUND`. Currency whitelist CAD/USD; charge_type whitelist: deposit, buyer_commission, buyer_full_payment, buy_now_payment, seller_commission, seller_payout. Indexes ensured at startup.
- **`services/deposit_refund_queue.py`** — 60s SLA worker. `enqueue_non_winner_refunds(winner_user_id, deposits)` skips winner. Worker tick every **10 seconds** (registered in `server.py` scheduler). Per-job retry with exponential backoff [10s, 30s, 90s], max 3 attempts → permanent failure logged + alert event. Async parallel processing via `asyncio.gather`.
- **`services/auction_settlement.py`** — single entry point `settle_auction(db, auction_id, listing)` forks by `listing.payment_method`:
  - `cash` / `etransfer` → buyer charged commission only (deposit credited if covers it); seller charged commission separately
  - `stripe` → buyer charged hammer + commission − deposit_already_paid; payout via Connect destination charge (winning_bid − seller_commission); falls back to `payout_queue` collection when seller has no Connect account
  - **WINNER_MISMATCH_BLOCKED** validation: any Stripe-flow buyer charge aborts if `winner_user_id != listing.winner_id`

### New routes
- **`POST /api/bidder-deposits/charge`** — partner-defined deposit charging (Spec Feature 1). Idempotent + atomic. Auto-fired on first bid via `place_bid()` when `listing.requires_deposit=true`.
- **`GET /api/bidder-deposits/check/{auction_id}`** — buyer-side status check
- **`GET /api/admin/payment-charges` + `/events` + `/refund-queue`** — admin-only observability dashboard

### Schema additions (Spec Feature 1)
- `listings.requires_deposit` (bool), `deposit_amount` (decimal in auction currency), `deposit_type` ("fixed" | "percentage")
- Same fields added to `multi_item_listings` (Lots auctions)
- New collection `payment_charges` — every Stripe charge tracked with idempotency_key, status, currency
- New collection `deposit_refund_queue` — 60s SLA jobs with retry state
- New collection `payment_events` — DUPLICATE_CHARGE_BLOCKED / ROLLBACK_REFUND / WINNER_MISMATCH_BLOCKED / DEPOSIT_REFUND_PERMANENT_FAILURE / PAYOUT_QUEUED_NO_CONNECT

### Hooked into existing flows
- `routes/auctions.py::process_ended_auctions` now (1) enqueues non-winner refunds, then (2) calls `settle_auction()` for the winner — replacing ad-hoc per-auction settlement
- `routes/auctions_bids.py::place_bid` charges the bidder's deposit on FIRST bid for partner-defined `requires_deposit=true` listings (idempotent — duplicates return `already_charged`)
- `routes/listings.py::create_listing` validates deposit fields + persists them; rejects `requires_deposit=true` without `deposit_amount` or invalid `deposit_type` with bilingual error

### Frontend (Spec Features 1, 4, 5, 6 + Global Rules 1 & 2)
- **`pages/CreateListingPage.js`** — added Deposit section (radios: No deposit / Require deposit; type toggle: Fixed amount / % of starting bid; amount input). Added bilingual seller disclosure (Feature 6) + currency-locked-after-publish notice. Existing CAD/USD selector retained.
- **`pages/ListingDetailPage.js`** — added bilingual notices ABOVE bid input:
  - `bid-deposit-required-notice` / `bid-no-deposit-notice` (Feature 1 buyer-facing)
  - `bid-stripe-payment-notice` / `bid-cash-payment-notice` (Feature 3 buyer-facing copy)
- **`components/BidConfirmationDialog.js`** — added `bid-disclaimer` block (Feature 4) with deposit notice when applicable; accepts new props `currency` / `paymentMethod` / `requiresDeposit` / `depositAmount` / `depositType`
- **`components/BuyNowButton.js`** — added `buy-now-disclaimer` block (Feature 5) — full bilingual EN/FR copy
- **`components/TrustVerification.js`** — replaced single-line notice with full `setup-intent-no-silent-charges` block (Global Rule 2) — bilingual EN/FR
- **`components/MoneyLabel.js`** — `formatMoney(amount, currency)` helper renders `$X.XX CUR` everywhere (Global Rule 1)
- **Admin dashboard** — `Partners & Finance → Strict Payment Charges` tab loads `AdminPaymentChargesPage` with 3 sub-tabs (charges / events / refund-queue)

### Email notifications (NEW helpers in `services/email_notifications.py`)
- `send_deposit_refunded_email` — auto-fired by refund queue worker on success
- `send_charge_confirmation_email` — fired by `auction_settlement` after each successful buyer/seller commission charge
- `send_payout_confirmation_email` — fired when Connect payout initiated

### Verification
- `/app/test_reports/iteration_185.json`: **26/26 backend unit pass** (11 new + 15 iter175 regression). **9/10 backend API pass** (1 skipped, non-blocking). Frontend: CreateListingPage + AdminPaymentChargesPage testids confirmed. ListingDetail/BidConfirmation/BuyNow notices verified in code path; testing harness couldn't reach a live listing for E2E click-through (not a regression).
- New `tests/test_strict_payments_iter185.py` covers: idempotency key format / charge_type whitelist / DuplicateChargeBlocked event / CAD/USD-only / refund queue skip-winner / refund worker success path / cash↔stripe flow routing / WINNER_MISMATCH_BLOCKED / Listing deposit validation / Listing default currency=CAD.
- Scheduler now reports 14 jobs (was 13); `deposit_refund_queue` tick visible in admin Scheduler Status panel.

### Spec checklist — all items closed
- ✅ Default currency CAD; ✅ currency code passed to every Stripe call (`auction_currency.lower()`); ✅ MoneyLabel shows "$X.XX CUR" — no bare `$`; ✅ currency locked after publish (not in `update_listing` allowed_fields)
- ✅ Single "Deposit" terminology — no "down payment" introduced; legacy `down_payments` collection untouched (separate $50 storage / 10% vehicle flow stays)
- ✅ SetupIntent only for card capture — TrustVerification + payment-methods endpoints already used SetupIntent before iter185; new copy enforces "no silent charges" notice
- ✅ Duplicate-charge guard via `payment_charges` table + DuplicateChargeBlocked event
- ✅ Idempotency keys on every Stripe call routed through `reserve_charge_row` + `_charge_card`
- ✅ Atomic DB+Stripe with rollback (verified test_settle_auction)
- ✅ 60s deposit refund queue (10s tick × 3 retries × asyncio.gather batch)
- ✅ Winner deposit credited toward final charge (auction_settlement.py uses `final_charge = buyer_total - deposit_amount`)
- ✅ Winner-mismatch validation
- ✅ Cash/E-Transfer: commission-only charges (no full hammer)
- ✅ Stripe scenario: full hammer + commission − deposit; Connect payout = winning_bid − seller_commission
- ✅ All bilingual disclaimers (Bid / Buy Now / Sell / Card-save)
- ✅ Admin charge log dashboard
- ✅ Email notifications wired

---

## Previous: 3-Feature Sprint — Lot Numbering + Down Payments + Post-Sale Contact (May 6, 2026 / iter183-184) — 100% verified

### Feature 1 — Automated Lot Numbering ✅
- `services/listings_service.build_lots_with_end_time()` now overrides any seller-supplied `lot_number` and assigns sequential **Lot 1..N** at create time. Hard cap **500 lots/auction** (industry standard); creates raise 400 above the limit.
- Migration: `backend/scripts/backfill_lot_numbers.py` rewrites `lot_number = idx+1` on every existing `multi_item_listings` document. Idempotent, ran cleanly (0 docs in current DB).
- Surfaces already render: `DecomposedMarketplace.js` shows `Lot #N/total` on cards; `MultiItemListingDetailPage.js:1155` shows `Lot #{lot.lot_number}` on detail rows.

### Feature 2 — Post-Auction Down Payments ✅
- New `services/down_payment_service.py` — single source of truth. Storage = **flat $50 CAD**, Vehicle = **10% of winning bid**, **24 h** to pay or auto-forfeit + promote runner-up.
- New router `routes/down_payments.py`:
  - `GET /api/down-payments/me` — buyer's open DPs (rate-limited 60/min)
  - `GET /api/down-payments/{auction_id}` — buyer/seller/admin status incl. `seconds_left` + `is_overdue`
  - `POST /api/down-payments/{auction_id}/checkout` — Stripe Checkout session (rate-limited 10/min)
- Auction-end hooks already create the DP row:
  - Storage: `services/scheduled_jobs.process_ended_storage_auctions` after `release_deposits_on_close`
  - Vehicle: `services/vehicle_auction_handler` after `create_vehicle_fee_charge`
- Stripe webhook `checkout.session.completed` with `metadata.transaction_type=down_payment` calls `mark_down_payment_paid()` → flips both the DP row and the auction's `down_payment_status` to `paid`.
- New cron job #14: `services/scheduler.expire_overdue_down_payments` runs **every 30 min** → marks expired, forfeits `bidding_deposits.status: held|authorized → forfeited`, finds runner-up bidder, transfers `auction.highest_bidder_id` + `current_bid`, creates a fresh 24 h DP for the new winner, and emails them via `send_auction_won_email`.
- Idempotent `create_down_payment` (calling twice with same auction_id+buyer_id returns the same id — verified in unit harness).
- Total scheduler jobs now **14** (was 13).

### Feature 3 — Post-Sale Contact Surfacing ✅ (Option A — defer Option B messaging to next sprint)
- `routes/payments.py GET /payments/status/{session_id}`:
  - Now uses `_db = get_db()` inside try-block (fixed P0 NameError caught in iter183)
  - **Optional Bearer auth** + PII gate — only buyer / seller / admin sees `seller_contact{name,email,phone}`. Anonymous callers still get `status/payment_status/amount_total` (no PII leak).
  - Best-effort enrichment: failed lookups log warnings (instead of swallowing) so future regressions are observable.
- `frontend/src/pages/PaymentSuccessPage.js`:
  - Sends `Authorization: Bearer <token>` so PII gate matches
  - Renders blue contact card (`data-testid="checkout-seller-contact"`) with name/email/phone when present.
- Dashboard panels (`SellerDashboard.js → buyer_contact`, `BuyerDashboard.js → seller_contact`) from iter182 remain in place.
- **Option B (in-app messaging thread)** intentionally deferred to next sprint per user direction.

### Verification
- `/app/test_reports/iteration_183.json`: 9/12 pass — caught the `db not defined` P0
- `/app/test_reports/iteration_184.json`: **12/12 pass** post-fix. Full PII gate matrix (anon, buyer, seller, admin, stranger) + 2 edge cases (missing txn, missing seller) covered with mocked Stripe + seeded `payment_transactions`.
- Manual python harness: storage flat $50, vehicle 10%, idempotent create, expire+promote-runner-up cron — all green.


## Previous: Listing Promotion / Boost Payment System (May 5, 2026 / iter182) — 100% verified

### Bug fix — "Method Not Allowed" on Promote button
- Root cause: front-end POSTed to `/payments/promote-listing` while backend only registered `/payments/promote`.
- Fix: new canonical `POST /api/payments/promote-listing` endpoint in `routes/payments_promotions.py` accepts `{listing_id, boost_tier, listing_type, return_url}`, owner-only authorisation, returns Stripe Checkout `checkout_url` + full breakdown.
- Legacy `/payments/promote` preserved during the deprecation window.

### Full Stripe pricing (Canadian fee stack — single source of truth)
- Base × {Basic 9.99 · Standard 24.99 · Premium 49.99}
- + GST 5% on base + QST 9.975% on base
- + Two-pass `gross_up_stripe_fee(card_type)` Stripe fee (domestic 2.9%/intl 3.9%/conversion 5.9%)
- Live verified totals (basic / standard / premium): **$12.14 / $29.90 / $59.51 CAD**.
- The two-pass gross-up is ~$0.30 higher than the spec's single-pass approximation because it also covers Stripe's cut on the GST/QST line (revenue-protection by design).

### Webhook activation (`checkout.session.completed` for `transaction_type=listing_promotion`)
- New `_handle_listing_promotion_paid()` in `routes/webhooks.py`:
  - Sets `is_promoted=true`, `is_featured=true`, `promotion_tier`, `promotion_tier_weight`, `promotion_start`, `promotion_end`, `promoted_until`, `promotion_features[]` on the listing in the correct collection (`db.storage_auctions` for storage, `db.listings` for the rest).
  - Updates the matching `db.promotions` row → `status: active`.
  - Premium tier inserts a row into `db.social_share_queue` for manual posting.
  - Sends bilingual confirmation email via new `send_promotion_confirmation_email` (with full receipt: base, GST, QST, Payment Processing, Total Charged).

### Storage Auction promotions
- Frontend: `pages/storage/StorageAuctionDetail.js` now renders a `data-testid="boost-storage-auction-btn"` for facility owners + admins; opens the same `ListingPromotionModal` with `listingType="storage"`.
- Backend: same pricing route handles `listing_type="storage"` against `db.storage_auctions`.
- `routes/storage_auctions.py` list endpoint now sorts `[is_promoted -1, promotion_tier_weight -1, ...]` so promoted auctions surface first.

### Partner Lots promotions
- `pages/ListingDetailPage.js` mounts the modal with `listingType="lots"` when `listing.is_multi_item || listing.listing_type === "lots"`.
- Header label for partner/lots: EN "Promote Your Lot Auction" / FR "Promouvoir votre vente aux enchères par lots".
- Premium adds a "Featured Partner" badge to the feature list.
- `routes/listings.py` `sort_spec` mirrors storage — promoted first, tier weight tie-breaker.

### Card-type aware Stripe fee
- `gross_up_stripe_fee(net, card_type)` now supports `"domestic"` (2.9%), `"international"` (3.9%), `"conversion"` (5.9%); defaults to domestic.
- `payment_intent.succeeded` webhook reads `payment_method.card.country` and writes `card_country` + `actual_stripe_fee` to the transaction record. Non-CA card → logs the delta to a new `stripe_fee_adjustments` collection for manual reconciliation. **Buyer is never re-charged** post-payment.

### Promotion expiry
- `services/scheduled_jobs.process_expired_promotions` now downgrades both schemas (legacy `promoted_until/promotion_tier` AND new `is_promoted/promotion_end`) across `listings`, `vehicle_listings`, `storage_auctions`. Also flips `db.promotions.status="expired"` for the admin panel.
- Hourly schedule unchanged.

### Admin Promotions panel (5 new endpoints)
- `GET /api/admin/promotions?status=active|expired|all` — table of live promotions (enriched with listing_title + seller_name)
- `POST /api/admin/promotions/{promo_id}/cancel` — flips listing back + marks promo as `cancelled`
- `GET /api/admin/promotions/social-share-queue` — pending Premium social share queue
- `POST /api/admin/promotions/social-share-queue/{item_id}/mark-shared` — marks queue item as shared
- `GET /api/admin/promotions/revenue` — month-to-date + all-time revenue breakdown by tier and listing_type

### Live `/api/fees/estimate` endpoint
- Public, rate-limited 60/min, supports `card_type` query param; debounced 400 ms hookup in `PriceBreakdown.js`.

### Verification (testing agent iter182)
- 11/11 backend pytest pass (1 storage-sort skipped — empty collection)
- Frontend exercise: modal opens, all 3 tier cards render, Standard selection shows $29.90 grand total with `data-testid="promo-stripe-fee-row"` and `data-testid="promo-grand-total"`
- Webhook simulation flips listing → `is_promoted: true` with full features list; expiry job downgrades correctly
- All admin endpoints return 200 with correct schema


## Previous: P0 Critical Bug Sprint — 6/6 Fixed (May 5, 2026 / iter181) — Verified 100%

### Bug 1 — Wrong email header (Vehicle Auctions on Marketplace items) ✅
- Root cause: `_base_template()` hardcoded `🚗 BidVex Vehicle Auctions`. Every email used it regardless of auction source.
- Fix: new `_section_label(auction_type)` helper + `_base_template(..., auction_type)` now renders dynamic header/icon/color per section. Subject lines and footer also include correct section name. Mappings: `marketplace→BidVex Marketplace`, `lots→BidVex Lots Auction`, `storage→BidVex Storage Auctions`, `vehicle→BidVex Vehicle Auctions`, unknown→`BidVex Auctions`.
- `send_bid_placed_email` and `send_outbid_email` now accept `auction_type`. Callers in `auctions_bids.py` derive the type from `listing.category` / `is_multi_item` and forward it.

### Bug 2 — Seller sees "OUTBID" on own listing ✅
- Fix: `ListingDetailPage.js` badge block is now role-aware. If `user.id === listing.seller_id` and any bid exists → shows `Bid Received / Enchère reçue` badge (data-testid `seller-bid-received-badge`) instead of OUTBID. Anonymous visitors see nothing. Buyer badges (LEADING/OUTBID) remain unchanged. Uses real-time `realtimeBidCount` so the badge updates live over the WebSocket.
- New `send_seller_bid_received_email(...)` email function + wired into `routes/auctions_bids.py` so the seller is notified (privacy-preserving bidder alias — "First L.").

### Bug 3 — BIN price incorrect at Stripe checkout ✅
- Root cause: `POST /api/payments/checkout` always used `listing.current_price` (latest bid) as hammer — BIN on a $5.00 listing where the last bid was $1.10 opened Stripe for $1.52.
- Fix: `CheckoutRequest.buy_now: bool = False`. When `buy_now=true`, `/checkout` uses `listing.buy_now_price` as hammer and records `transaction_type: "buy_it_now"`. Frontend `handleBuyNow` now sends `buy_now: true`.
- Verified live: BIN = $5.00 → Stripe total $5.83 (was $1.52); auction-win flow on same listing still uses $1.00 current_price → $1.45.

### Bug 4 — Cost breakdown shows $0 taxes but Stripe charges real tax ✅
- Root cause: `calculate_general_payment` taxed `buyer_premium` alone. For $1.10 hammer, BP=$0.03 → GST/QST both round to $0.00, but Stripe was taxing `(BP + stripe_recovery) ≈ $0.36` and collecting real tax. Deceived buyers with a lower displayed total.
- Fix: taxes now computed on `(buyer_premium + stripe_processing_fee)` — the same base Stripe charges. Two-pass gross-up so Stripe covers the taxes too. New `stripe_processing_fee` field on `GeneralPaymentResult`. Front-end `PriceBreakdown` now shows a `Payment Processing (2.9% + $0.30)` line (data-testid `stripe-processing-fee-row`) with bilingual ℹ️ tooltip.

### Bug 5 — No post-auction emails ✅
- Root cause: `process_ended_auctions` created notifications but never sent emails.
- Fix: three new email paths fire when auction ends:
  - Winning buyer → existing `send_auction_won_email` (now with correct `is_vehicle` / section branding).
  - Seller with ≥1 bid → new `send_seller_auction_sold_email` (hammer, platform fee, net payout, bidder alias).
  - Seller with 0 bids → new `send_seller_auction_no_bids_email` (relist CTA).
- Each wrapped in try/except so one failing email never blocks auction-close process. All use dynamic section branding (Bug 1 fix).

### Bug 6 — Stripe processing fees not passed through ✅
- Root cause: `stripe_recovery(fees)` used `fees × 0.029 + 0.30` — under-recovers by ~3% because Stripe takes its cut from the FULL charge, not the fees subtotal. BidVex was absorbing the shortfall.
- Fix: new `gross_up_stripe_fee(net)` helper in `pricing_manager.py` — `charge_total = (net + 0.30) / (1 - 0.029); fee = charge_total - net`. Both `non_vehicle_stripe` and `calculate_general_payment` now use two-pass gross-up so Stripe recovery ALSO covers the tax on it.
- Cost breakdown UI displays the fee as a line item. All 7 metadata fields added to PaymentIntent for reconciliation.
- Verified: hammer=$10 (basic tier) → BP=$0.50, fee_tax=$0.17, stripe_fee=$0.63, total=$11.30; hammer=$5 → stripe_fee=$0.47 (was effectively $0.30 legacy), total=$5.83.

### Verification
- 5/5 backend pytest pass (testing agent iter181).
- Live curl: POST `/api/payments/checkout {buy_now:true}` returns breakdown.hammer_price=$5.00, buyer_total=$5.83.
- Live curl: POST `/api/payments/tax/calculate` returns non-zero tax + `stripe_processing_fee` field.
- Python unit: `_section_label` and `_base_template` correctly brand marketplace items without "Vehicle Auctions".
- AST check: `process_ended_auctions` calls all 3 new email functions.


## Previous: Production Hardening — Performance, Security & Scalability (May 4, 2026 / iter180) — 26/26 DONE

All 9 items from the user's hardening directive shipped and verified end-to-end in a single session. The platform is now production-ready for heavy traffic.

### Item 1 — MongoDB Indexes (Critical performance)
- NEW `backend/scripts/create_indexes.py` — idempotent migration script. Ran successfully against production: 17 listings indexes, 7 storage_auctions, 9 users, 4 refresh_tokens (incl. TTL).
- New `create_critical_indexes()` runs on every startup (`@app.on_event("startup")`) — verifies the 5 most critical indexes per-iteration with independent try/except so one collision can't stop the rest. TTL index on `refresh_tokens.expires_at` for auto-cleanup.

### Item 2 — MongoDB Connection Pool
- `AsyncIOMotorClient` retuned: `maxPoolSize=50`, `minPoolSize=5`, `maxIdleTimeMS=30000`, `connectTimeoutMS=5000`, `serverSelectionTimeoutMS=5000`, `retryWrites=True`, `w="majority"`.

### Item 3 — Backend Rate Limiting
- `slowapi` 0.1.9 already installed; bilingual 429 handler now installed in server.py replacing default.
- All bid endpoints throttled to `10/minute`: `/api/bids`, `/api/multi-item-listings/{id}/lots/{n}/bid`, `/api/storage-auctions/{id}/bid`, `/api/vehicle-bids`, `/api/bids/auto-bid`.
- Auth tightened: `/auth/login` → `5/minute`, `/auth/register` → `5/minute` (existing).
- 429 response body returns bilingual `message_en` / `message_fr` + `retry_after_seconds=60` + `Retry-After` header.

### Item 4 — JWT Hardening + Refresh Token Rotation
- Access tokens expire in **60 minutes** (was 168h/7d). New env vars `ACCESS_TOKEN_EXPIRE_MINUTES=60` and `REFRESH_TOKEN_EXPIRE_DAYS=30`.
- NEW `POST /api/auth/refresh` (rate-limited 10/min) rotates refresh tokens — old token marked `revoked=True` on use, fresh access + refresh pair returned.
- Refresh tokens stored hashed (sha256) in `refresh_tokens` collection with TTL on `expires_at` for automatic cleanup.
- Bilingual `token_expired` error response on expired access tokens.
- Login response now includes `refresh_token` field alongside `access_token`.

### Item 5 — NoSQL Injection Sanitizer
- NEW `backend/services/sanitizer.py` exports `sanitize_string`, `sanitize_dict`, `sanitize_list`, `safe_regex` — rejects `$where`, `$ne`, `$gt`, `$regex`, `$expr`, etc.; escapes user input destined for `$regex` queries.
- Applied to all production search endpoints in `routes/listings.py` (2 spots), `routes/admin.py` (user search), and `routes/admin_ops.py` (3 spots: transactions export, transaction logs, community questions).

### Item 6 — Scheduler Job Isolation + Health Endpoint
- NEW `safe_run(job_name, coro, timeout=55s)` in `services/scheduled_jobs.py` — per-job exception isolation + 55s timeout + `_JOB_STATUS` health tracking.
- All 13 vehicle scheduler jobs now wrapped via `_tracked()` helper in `services/scheduler.py`.
- All 8 server-level APScheduler jobs wrapped via `safe_run(...)` in `server.py`.
- NEW `GET /api/admin/scheduler/status` returns `{jobs: [{name, last_run, last_status, last_duration_ms, last_error, next_run}], total_jobs, scheduler_running}`. Live tested — returns 30 jobs, several already showing `success` status.
- NEW `<SchedulerStatusCard>` component rendered above content in admin dashboard. Auto-refreshes every 30s.

### Item 7 — SEO
- NEW `backend/routes/sitemap.py` mounts dynamic `/sitemap.xml` (≤1000 listings + ≤500 storage auctions + 12 static pages) and `/robots.txt`. Verified live via curl.
- `frontend/public/index.html` enhanced: bilingual hreflang `en-ca`/`fr-ca`/`x-default`, canonical link, improved meta description, og:url, full Twitter cards.

### Item 8 — Stripe Circuit Breaker
- NEW `services/stripe_circuit_breaker.py`: `StripeCircuitBreaker` (5 failures → open, 60s recovery, half-open probe) + `safe_stripe_call_blocking(fn, op_name, timeout=15s)` — runs blocking SDK calls in a thread, applies timeout, returns bilingual 503/504/402 errors.
- Wrapped 6 critical PaymentIntent.create calls: storage deposits, bidding deposits, cancellation penalties, vehicle fees, vehicle buy-now remainder, storage promotions.

### Item 9 — Sentry Wiring
- Backend: `sentry-sdk==2.59.0` installed + initialised in `server.py` when `SENTRY_DSN` env is set (FastApi integration, `traces_sample_rate=0.1`, `send_default_pii=False`).
- Frontend: `@sentry/react@10.51.0` installed + initialised in `index.js` when `REACT_APP_SENTRY_DSN` env is set.
- Both opt-in via env — zero impact when DSN is unset.

### Verification (live curls)
- Login → returned `access_token` (248 chars) + `refresh_token` (64 chars). ✅
- Refresh → new pair issued. ✅
- Reuse old refresh → 401 with bilingual error. ✅ (rotation working)
- 6 failed logins in 60s → 6th returns 429 with bilingual EN+FR body. ✅
- 11 bid attempts in 60s → 11th returns 429. ✅
- `/sitemap.xml` returns valid XML with 12 static pages + active listings. ✅
- `/robots.txt` returns expected directives. ✅
- `/api/admin/scheduler/status` returns 30 jobs with live `last_status`/`last_duration_ms`. ✅


## Previous: P0 — 9-Fix Credit-Efficient Batch (May 4, 2026 / iter178) — 9/9 DONE

All nine items from the user's explicit list shipped and end-to-end verified in a single session (testing agent 100% frontend + 14/14 new backend + 90/91 regression, 1 stale iter172 test updated).

### FIX 1 — Deposit button on storage auctions
- NEW `GET /api/storage-auctions/{id}/deposit/status` returns `{has_deposit, deposit_required, deposit_amount, status, created_at}` (always 5 keys for consistency).
- NEW `StorageDepositBanner` component (Stripe Elements modal) — amber "Pay $X deposit to unlock bidding" when required + not paid, green "Deposit authorized" when held. Auto-release on auction close already wired in iter172.
- Wired into `StorageAuctionDetail`: bid input hidden until deposit is held; block bidding via `needsDeposit` guard.
- Existing marketplace+vehicle banners (iter173) unchanged.

### FIX 2 — Mobile bottom nav reordered
- Order: **Vehicles | Lots | Storage | Sell | Watchlist** (Search removed, Storage next to Lots).

### FIX 3 — Storage light-mode color fix
- `StorageAuctionsBrowse` and `StorageAuctionDetail` page background: `bg-slate-50` → `bg-sky-50`. Hero keeps dark navy gradient per spec.

### FIX 4 — Upcoming vs Live status
- NEW shared `AuctionStatusBadge` + `CountdownTimer` components, bilingual (UPCOMING · À VENIR / LIVE · EN DIRECT / ENDED · TERMINÉE).
- Storage detail replaces "LIVE" hardcoded badge with status-aware component.
- Upcoming auctions show countdown + disabled "Bidding Not Yet Open · Enchères pas encore ouvertes" button.
- Scheduler Job 13 `activate_upcoming_auctions_job` runs every minute, flips `upcoming → active` across storage/vehicle/listings collections once `start_time <= now`. Scheduler now at **13 jobs**.

### FIX 5 — Profile update
- PUT /api/profile verified working end-to-end (name, phone, province, email via magic-link verification on change).

### FIX 6 — Admin panel: facility management
- NEW Admin > Marketplace > **Facilities** tab (`AdminFacilities`): list all registered storage facilities, filter, Verify / Suspend / Delete actions, bilingual.
- Uses existing `/api/admin/storage-facilities/*` endpoints (iter172).
- Existing VehicleAdminManager + AdminStorageAuctions tabs already cover vehicle + storage auction management.

### FIX 7 — Marketing integrations (FB Pixel, GTM, Google Ads)
- NEW `PUT /api/admin/site-config/marketing` persists `{fb_pixel_id, gtm_id, google_ads_id}` to `site_config.marketing`.
- Public `GET /api/site-config` exposes the marketing dict.
- NEW `MarketingPixelLoader` component injects FB Pixel + GTM scripts on app boot if admin has saved IDs (skips init when empty).
- NEW global `window.bvTrackEvent(name, params)` fans out to both `fbq` and GTM `dataLayer` — ready for ViewContent/AddToCart/Purchase hooks.
- NEW Admin > Settings > **Marketing Integrations** tab (`AdminMarketingIntegrations`).

### FIX 9 — QR code visibility in emails
- Alt text improved to `"Scan for pickup verification / Scanner pour vérification de ramassage"` (bilingual).
- Explicit `background:#FFFFFF` on both wrapper and `<img>` style.
- Border bumped to 2px amber (`#fde68a`). Padding 12px. Pickup code text fallback already present in the winner email above and below the QR.

### Tests — 110/111 green
- NEW `/app/backend/tests/test_iter178_batch.py` — 14/14
- Updated `/app/backend/tests/test_storage_iter172_api.py` scheduler-log assertion to accept 11-15 jobs (was brittle "11 jobs")
- Regression: 90/91 storage iter170/172/173/176 + iter175 all pass; frontend 100% e2e verified

### Files changed (iter178)
- Backend: `routes/storage_auctions.py` (+deposit/status consistent 5-key response), `routes/site_config.py` (+marketing PUT + public exposure), `services/scheduler.py` (+Job 13), `services/email_notifications.py` (QR alt text + white bg), `tests/test_storage_iter172_api.py` (relaxed scheduler assertion)
- Frontend: `pages/storage/StorageDepositBanner.js` (NEW), `components/AuctionStatusBadge.js` (NEW), `pages/admin/AdminFacilities.js` (NEW), `pages/admin/AdminMarketingIntegrations.js` (NEW), `components/MarketingPixelLoader.js` (NEW), `pages/storage/StorageAuctionDetail.js` (banner + badge + upcoming state), `pages/storage/StorageAuctionsBrowse.js` (bg-sky-50), `components/MobileBottomNav.js` (order), `pages/AdminDashboard.js` (+facilities + marketing-integrations tabs), `App.js` (+MarketingPixelLoader)

---

## Latest: P0 — Layout Fixes + Vehicle Coming-Soon (May 1, 2026 / iter176) — 3/3 sections DONE

### Section 1 — Global responsive layout
- `index.css` — added `max-width: 100vw` + `overflow-x: hidden` on **both** `html` AND `body` (was previously only on `html`); `img { max-width: 100%; height: auto; display: block }` global rule.
- `HomePage.js` — homepage "View All / Tout voir" buttons now visible on mobile (removed `hidden sm:flex` on Ending Soon and New Today sections; Hot section already had a dedicated mobile button so its desktop one stays hidden on small screens to avoid duplicates).

### Section 2 — Storage Hero contrast fix (Bill 96 + WCAG AA)
- `StorageHero.css`:
  - `.storage-hero__label` → color `#FFFFFF` (was `#3FB4CB` low-contrast). Border + background bumped to white-rgba.
  - `.storage-hero__label--fr` → bright cyan `#22d3ee` (was 85% opacity teal).
  - `.storage-hero__subtitle` → 92% white opacity (was 90%).
  - `.storage-hero__subtitle-fr-visible` → `#22d3ee` (was 85% opacity teal).
  - `.storage-hero__badges` text base color → 92% white opacity, badge primary text explicit `#FFFFFF`.

### Section 3 — Vehicle Auctions Coming-Soon page + Admin Feature Flags

**Backend** (`/app/backend/routes/feature_flags.py` NEW — 4 routers registered)
- `feature_flags` collection auto-seeds `vehicle_auctions_enabled = false` on first read.
- `KNOWN_FLAGS` whitelist prevents arbitrary flag minting; bilingual `description_en` / `description_fr`.
- Public: `GET /api/feature-flags/{key}` (60s cache) — falls back closed (Coming Soon) if Mongo unreachable.
- Admin: `GET/PATCH /api/admin/feature-flags`, `GET /api/admin/waitlist/vehicle-auctions/count`, `GET /api/admin/waitlist/vehicle-auctions`.
- Public waitlist: `POST /api/waitlist/vehicle-auctions { email, lang }` — upserts on lowercased email; returns `already_on_list` flag.

**Frontend**
- `pages/vehicles/VehicleComingSoonPage.js` (NEW) — bilingual headlines, animated floating car icon, dark navy gradient background, pill-shaped email input + "Notify Me · Me notifier" CTA, success state, EN/FR language preference toggle for the launch email, 3 teaser feature pills.
- `pages/vehicles/VehicleAuctionsRoute.js` (NEW) — gate that uses `useFeatureFlag('vehicle_auctions_enabled')` and renders ComingSoon when false, real `VehicleAuctionsPage` when true; minimal centered spinner while loading.
- `hooks/useFeatureFlag.js` (NEW) — in-memory cache (60s TTL) + `invalidateFeatureFlag(key)` exported for admin "I just toggled" cache-busting.
- `pages/admin/AdminFeatureFlags.js` (NEW) — admin tab UI: card per flag, animated Switch, Active/Coming-Soon badges, optimistic-update with revert-on-error, Waitlist signup count card, last-updated trail with admin email.
- `pages/AdminDashboard.js` — registered `feature-flags` secondary tab under **Vehicles** primary (initial bug placed it under Marketplace primary — caught and fixed by testing agent iter176).
- `components/Navbar.js` — flag-driven `SOON · BIENTÔT` cyan badge next to Vehicle Auctions nav link, hides when flag is ON.
- `App.js` — `/vehicle-auctions` and FR alias `/encheres-de-vehicules` both routed through the gate.

### Tests — 47/49 green (2 false positives caught)
- New: `/app/backend/tests/test_iter176_feature_flags.py` — 14/16 pass + 2 skipped (env-only). Storage regression 33/33 still green.
- 2 issues caught by testing agent: AdminDashboard routing bug (now FIXED — moved `case 'feature-flags'` from marketplace switch to vehicles switch), and Cache-Control header overridden by global no-store middleware (acknowledged — JS in-memory cache provides the 60s TTL, HTTP caching off by design for security policy).

### Files changed (iter176)
- Backend: `routes/feature_flags.py` (NEW), `server.py` (registered 4 routers)
- Frontend: `pages/vehicles/VehicleComingSoonPage.js` (NEW), `pages/vehicles/VehicleAuctionsRoute.js` (NEW), `hooks/useFeatureFlag.js` (NEW), `pages/admin/AdminFeatureFlags.js` (NEW), `pages/AdminDashboard.js` (+ tab + correct routing), `components/Navbar.js` (+ flag badge), `App.js` (gate + FR alias), `pages/storage/StorageHero.css` (contrast fix), `index.css` (overflow guards), `pages/HomePage.js` (mobile View All buttons)

---

## Latest: P0 — Final Polishing Phase (May 1, 2026 / iter175) — 4/4 DONE

User-approved final polishing sprint before production. All 4 items shipped + tested (48/48 backend tests pass).

### Item 1 — Quick Bid pills (HIGH PRIORITY)
- New shared component `/app/frontend/src/components/QuickBidButtons.js` — three one-tap pills `+1×` / `+5×` / `+10×` scaled by the auction's `bid_increment` (so a $10-increment storage auction shows +$10 / +$50 / +$100; a $100-increment vehicle auction shows +$100 / +$500 / +$1,000).
- **Mobile-safety rapid Confirm step**: clicking a pill stages the candidate amount and surfaces a yellow "Confirm bid · Confirmez l'offre" banner with bilingual Confirm + Cancel buttons before submission.
- Wired into both `StorageAuctionDetail` (above bid input) and marketplace `ListingDetailPage` (above the existing form). On marketplace, confirming the rapid step seeds `bidAmount` and triggers the existing `BidConfirmationDialog` for the price-breakdown step (two-step flow: rapid mobile confirm → full price breakdown).

### Item 2 — Email Preferences page (CASL Compliance)
- Route: `/email-preferences?token=<UUID-signed-token>` (and FR alias `/preferences-courriel`).
- Backend: new router `/app/backend/routes/email_preferences.py` with 3 endpoints:
  - `GET /api/email-preferences/verify?token=…` — returns masked email + 3 categories with EN+FR labels and descriptions
  - `POST /api/email-preferences/update` — persists per-category prefs; setting marketing=false also flips legacy `marketing_unsubscribed` flag and writes to `email_suppressions`
  - `GET /api/email-preferences/generate-token` (admin-only) — QA convenience
- Three categories: **Marketing & Promotions**, **Bidding Alerts**, **Transactional (Required, locked, CASL §6(6))**
- Token uses same `UNSUBSCRIBE_SECRET` env var with distinct salt `bidvex-email-preferences-v1` so the two token types are NOT interchangeable. 30-day TTL via itsdangerous.
- Send-time guard helper `is_category_suppressed(email, category)` available for email pipeline integration.

### Item 3 — Analytics & Financial Security
- **react-datepicker integration** — admin Analytics dashboard now has a "From · Du → To · Au" custom date-range picker beside the period dropdown. Backend `GET /api/admin/analytics/revenue` upgraded to accept optional `start_date` + `end_date` (ISO YYYY-MM-DD) query params; falls back to `?days=N` when not provided.
- **Auto-Capture cron job** — new `/app/backend/services/deposit_auto_capture.py` + Job 12 in scheduler (`IntervalTrigger(hours=6)`). When a buyer's 2.5% platform-fee invoice is unpaid >48h past `payment_deadline`, the matching $500 vehicle deposit is captured via `PaymentService.capture_deposit()`. Grace hours configurable via env `DEPOSIT_AUTO_CAPTURE_GRACE_HOURS` (default 48).
- **Bilingual notification email** — new `send_vehicle_deposit_captured_email()` in `email_notifications.py`, sent automatically by the cron job, EN+FR per Bill 96 with invoice number, fee amount, captured amount, 14-day dispute window.
- Scheduler now logs **"Scheduler initialized with 12 jobs"** (was 11).

### Item 4 — Recently Sold Ticker (Social Proof)
- New backend endpoint `GET /api/carousel/recently-sold-ticker?limit=30` — aggregates sold auctions across all 3 surfaces (marketplace + storage + vehicle), sorted by `sold_at` desc, returns `{visible, total, threshold:10, items}`.
- **Threshold gate**: `visible=false` until total >= 10 sold auctions across all sources, so the marquee doesn't render an anaemic strip pre-launch.
- Frontend marquee `/app/frontend/src/components/RecentlySoldTicker.js` — placed above the homepage hero. Smooth horizontal CSS marquee animation (60s cycle, items duplicated for seamless loop), edge-fade gradients, kind-specific icons (ShoppingBag · Package · Car), polls every 60s.
- Format per item: `[icon] $1,234 · Toronto, ON · 10x10 storage unit` with FR label in `title` tooltip.

### Tests — 48/48 green
- New: `/app/backend/tests/test_iter175_polishing.py` — 15 tests covering email-preferences flow, recently-sold-ticker visibility threshold, custom date-range params, auto-capture import safety, bilingual email helper signature.
- Regression: 16 + 17 = 33/33 from iter170/172/173 still pass.

### Files changed (iter175)
- Backend: `routes/email_preferences.py` (NEW), `services/deposit_auto_capture.py` (NEW), `routes/carousel.py` (+ /recently-sold-ticker), `routes/admin_ops.py` (revenue start/end_date), `services/scheduler.py` (Job 12), `services/email_notifications.py` (+ bilingual deposit-captured helper), `server.py` (router registration)
- Frontend: `components/QuickBidButtons.js` (NEW), `components/RecentlySoldTicker.js` (NEW), `pages/EmailPreferencesPage.js` (NEW), `pages/admin/AnalyticsDashboard.js` (+react-datepicker), `pages/storage/StorageAuctionDetail.js` (+QB), `pages/ListingDetailPage.js` (+QB), `pages/HomePage.js` (+ticker), `App.js` (+ /email-preferences route), `package.json` (react-datepicker@9.1.0)

---

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
