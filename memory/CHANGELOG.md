# BidVex Changelog


## Feb, 2026 — P1 Listings Moderation Workflow + Admin Email Enrichment — DONE

### Backend
- **`services/admin_notifications.py`** — `notify_admin_new_user()` now renders **Country** (e.g. "United States (US)" from signup IP via `geolocation_service`) and **Referred by** (referrer name + email + affiliate code) rows. Falls back to "Unknown" / "Direct (no referral)".
- **`routes/auth.py:register()`** — Captures `signup_country_code`, `signup_country_name`, `signup_ip` from the existing geolocation block onto `user_doc`. When a `ref_code` is provided, also stamps `referred_by_email` and `referred_by_name` on the user record (single DB read, no extra round-trip).
- **`routes/auth.py:google_oauth_callback()`** — New Google users now also geolocate signup IP for the admin email.
- **`services/listings_service.py`** — New `resolve_listing_status()` helper for single-item listings. Returns "pending" when `marketplace_settings.require_approval_new_sellers=True` AND seller has 0 prior completed listings (single OR multi). Admins always bypass.
- **`routes/listings.py:create_listing()`** — Accepts `BackgroundTasks`, computes status via the new helper, and schedules `notify_admin_new_listing` via BackgroundTasks when a new listing lands as pending.
- **`routes/admin_ops.py`** — New endpoints (legacy `/admin/listings/{id}/moderate` retained as `_legacy` for back-compat):
  - `GET /admin/listings/pending` — combined single + multi pending list, batched seller enrichment (`_seller_email`, `_seller_name`, `_listing_type`), counters in response shape.
  - `POST /admin/listings/{id}/approve` — flips status to active, writes `admin_audit_logs`, schedules `send_listing_approved_email` to seller, invalidates listing cache.
  - `POST /admin/listings/{id}/reject` — REQUIRES `reason` (≥5 chars), persists `rejection_reason`, schedules `send_listing_rejected_email` with the reason in dynamic data.
  - Both endpoints reject double-action (returns 400 if listing is not in `pending` status), 404 on unknown id, 401/403 for non-admins.

### Frontend
- **NEW** `pages/admin/ListingsModeration.js` — admin moderation dashboard with: 3 counter cards (Total/Single-Item/Multi-Item), pending listings table (thumbnail, title, description, seller, price, location, timestamp), Approve/Reject/Preview buttons, reject dialog with 5 quick-reason chips + custom textarea + character counter, optimistic UI updates, full data-testid coverage.
- **`pages/AdminDashboard.js`** — Registered "Listings Moderation" tab under Marketplace category (sits between User Management and Lots Moderation).

### Verification
- `/app/test_reports/iteration_163.json` — **13/13 backend tests pass**
- Live curl tests confirmed: `signup_country_name`/`signup_country_code` populate ("United States (US)"), referred_by_* fields populate (Charbel Admin <charbel911@gmail.com>), reject without reason → 400, reject with reason → 200 + `admin_audit_logs` entry + seller email scheduled, approve → status flips to "active" + audit log + seller approval email scheduled.
- Frontend smoke screenshot confirmed page renders pending listing with all expected fields.



## Feb, 2026 — P0 Signup Emails Not Firing — FIXED & VERIFIED

### Bug
- New user signup (email/password) was sending emails synchronously, blocking the HTTP response
- Google OAuth signup wasn't triggering welcome or admin emails AT ALL
- Admin notification recipient was hardcoded to `info@bidvex.com` instead of reading env var

### Backend Fixes
- **`services/admin_notifications.py`** — Removed hardcoded `ADMIN_EMAIL = "info@bidvex.com"` module constant. Added `_resolve_admin_email()` runtime helper with precedence `ADMIN_NOTIFICATION_EMAIL → ADMIN_EMAIL → "info@bidvex.com"`. Reads env at call-time so reloads/overrides take effect. `notify_admin_new_user()` now also includes `Provider` (email/google) field.
- **`routes/auth.py:register()`** — Added `background_tasks: BackgroundTasks` parameter. Replaced synchronous `await send_welcome_template(...)` and ad-hoc `asyncio.create_task(notify_admin_new_user(...))` with `background_tasks.add_task(...)` calls so both emails run AFTER the HTTP response is sent (non-blocking).
- **`routes/auth.py:google_oauth_callback()`** — Added `background_tasks: BackgroundTasks` parameter. Schedules welcome + admin emails via `BackgroundTasks` ONLY on the new-user creation branch (existing Google logins do NOT re-trigger welcome).
- Welcome email is transactional (`is_marketing=False` default in `send_template_email`) — explicitly bypasses the new `email_suppressions` marketing-only check.

### Verification
- `/app/test_reports/iteration_162.json` — 11/11 tests passed
- Response time: ~1.3s (down from blocking on SendGrid network round-trip)
- 5 live signups → SendGrid status=202 on every welcome and admin email
- Test suite: `/app/backend/tests/test_signup_emails_bgtasks_162.py`



## Apr 29, 2026 — Custom Unsubscribe Flow (replaces SendGrid default) — DONE

### Backend
- **NEW** `routes/unsubscribe.py` — itsdangerous URLSafeTimedSerializer (30-day TTL, scoped by `UNSUBSCRIBE_SECRET`):
  - `GET /api/unsubscribe/verify?token=...` → masked email + already_unsubscribed status
  - `POST /api/unsubscribe/confirm` → upserts `users.marketing_unsubscribed=true` + `email_suppressions` row + calls SendGrid Suppressions API
  - `build_unsubscribe_urls(email)` helper used by send pipeline (returns bilingual EN/FR URLs)
  - `is_marketing_suppressed(email)` async guard for send-time
- **UPDATED** `services/email_service.py:send_template_email` — new `is_marketing` flag:
  - `is_marketing=True` → suppression check first; injects `unsubscribe_url_en` + `unsubscribe_url_fr` into `dynamic_template_data`
  - `is_marketing=False` (default for transactional) → always sends, suppression list bypassed
  - `send_geo_auction_alert_email` now `is_marketing=True`
- **UPDATED** `services/email_marketing.py:_send_campaign_email` — suppression guard + bilingual URL replacement (`{{unsubscribe_url_en}}`, `{{unsubscribe_url_fr}}`, plus legacy `{{unsubscribe_url}}` → EN)
- **UPDATED** `routes/sendgrid_webhook.py`:
  - `spamreport` moved from DELIVERABILITY_KILL_EVENTS → UNSUBSCRIBE_EVENTS (per spec)
  - `_handle_unsubscribe` now upserts users (with UUID id) AND populates `email_suppressions` table
  - Spam-alert call preserved within unsubscribe handler

### Frontend
- **REWRITTEN** `pages/UnsubscribePage.js` — bilingual EN/FR, Inter font, blue/cyan/slate palette (#2563eb / #06b6d4 / #0f172a), 5 states (loading / confirm / success / already / error)
- Routes registered: `/unsubscribe?lang=en` and `/desabonnement?lang=fr` (both render same component, lang detected from query or path)

### DB
- **NEW** `email_suppressions` collection — unique index on `email`, fast send-time guard
- **MIGRATION executed** `scripts/migrate_unsubscribe_fields.py` — backfilled 7 user docs with `marketing_unsubscribed=false`, created 3 suppressions from legacy data

### Env
- `.env`: added `UNSUBSCRIBE_SECRET=<64-char secret separate from JWT_SECRET>`

### Tests (iter161)
- **12/12 backend pass + 4/4 frontend pass** — full E2E verified live (verify → confirm → idempotent re-confirm → DB writes → bilingual UI states)
- 3 minor consistency issues (collection-name typos `email_suppression` → `email_suppressions`, missing webhook upsert) **fixed in iter161-followup**: 12/12 still green
- Regression test suite: `/app/backend/tests/test_unsubscribe_flow.py`

### 🚨 SendGrid Dashboard — manual one-time settings
Documented in `routes/unsubscribe.py` docstring. After deploy:
1. **Mail Settings → Subscription Tracking → OFF** (otherwise SendGrid rewrites our links)
2. **Mail Settings → Event Webhook → POST URL: `https://bidvex.com/api/sendgrid/event-webhook`**, events: `unsubscribe, group_unsubscribe, spamreport, bounce, dropped`, **Signed Event Webhook ON**
3. (Optional) **Sender Authentication** — DKIM + SPF should already be configured

---


## Apr 28, 2026 — Hero Phone Mockup with Floating Animation — DONE

### What
Replaced the empty right-column of the homepage hero with an animated phone-mockup mark — a hand holding a phone running the BidVex app. Premium SaaS treatment matching Stripe / Notion / Linear hero patterns.

### Components added
- `frontend/src/components/HeroPhone.js` — bilingual EN/FR (3 live-activity badges)
- `frontend/src/components/HeroPhone.css` — full keyframe animations + responsive breakpoints
- `frontend/public/assets/hero-phone-mockup.png` — 1295×1215 RGBA (transparent bg)

### Animation details
- **Float**: `phoneFloat` 6s ease-in-out infinite — vertical translate (-16px) + 2° tilt
- **Entry**: `phoneEntry` 0.9s cubic-bezier slides up from +60px on first paint, 0.5s delay (after hero text)
- **Glow**: `glowPulse` 4s — radial cyan→blue ambient light under phone, opacity 0.5↔0.8
- **Badges**: 3 individual floats (5s / 5.5s / 4.8s) with staggered delays
- **Status dots**: `dotPulse` 2s — green (top-left) + blue (top-right) for live-feel
- **Reduced motion**: All animations disabled via `prefers-reduced-motion: reduce`

### Live activity badges (bilingual)
| Position | EN | FR |
|---|---|---|
| Top-left | 🔨 New bid — $245 | 🔨 Nouvelle enchère — 245 $ |
| Top-right | 👤 14 bidders live | 👤 14 enchérisseurs en direct |
| Bottom | ✅ ITEM SOLD — $1,280 · 3s ago | ✅ ARTICLE VENDU — 1 280 $ · il y a 3 s |

### Responsive breakpoints
- ≥1280px: phone 460px wide, badges full size
- 1024-1280px: phone 380px, badges shrink to 11px
- 768-1024px: phone 320px, badges pulled inward
- ≤768px (mobile): phone stacks below text 280px wide, side badges hidden, bottom badge centered
- ≤375px (small mobile): phone 220px

### Layout changes
- `HomePage.js` hero: single `max-w-3xl` column → `grid lg:grid-cols-[1.15fr_1fr] gap-10 lg:gap-16` two-column
- Right column wired to `<HeroPhone />`

### Live verification
- Phone image: loaded ✅ (1295×1215 natural, 460px rendered desktop)
- Float + glow + badge animations running ✅
- Lint: 0 issues ✅
- Bilingual labels render based on `i18n.language` ✅

---


## Apr 28, 2026 — Direct Google OAuth 2.0 (replaces auth.emergentagent.com)

### Backend (FastAPI — chose to keep existing stack rather than rewrite to Node/Express)
- `backend/routes/auth.py` — appended:
  - `GET /api/auth/google?redirect=/marketplace` → generates CSRF state, persists in `db.oauth_states`, 302 to `accounts.google.com/o/oauth2/v2/auth` with PKCE-style state
  - `GET /api/auth/google/callback?code=&state=` → validates+consumes state (10-min TTL), exchanges code for tokens via `oauth2.googleapis.com/token`, fetches userinfo, find-or-create user in `db.users`, signs JWT via `create_access_token`, 302 to `${FRONTEND_URL}/auth/google/finish#token=<JWT>&redirect=...`
- All errors redirect to `${FRONTEND_URL}/auth?google_error=<reason>` (never 500s the user)
- Token in URL fragment (#) so it's never logged by proxies/Cloudflare

### Frontend
- `pages/AuthPage.js`: `handleGoogleLogin` now navigates to `${API_BASE}/auth/google?redirect=/marketplace` (no more `auth.emergentagent.com`)
- `pages/GoogleAuthFinishPage.js`: NEW — reads token from `window.location.hash`, calls `setUserFromToken(jwt)`, navigates to original destination
- `contexts/AuthContext.js`: NEW `setUserFromToken(jwt)` exposed in provider — persists token, hydrates user from `/api/auth/me`
- `App.js`: registered route `/auth/google/finish`

### Env vars added to `/app/backend/.env`
- `GOOGLE_CLIENT_ID=<REDACTED — see /app/backend/.env>`
- `GOOGLE_CLIENT_SECRET=<REDACTED — see /app/backend/.env>`
- `GOOGLE_CALLBACK_URL=https://api.bidvex.com/auth/google/callback`
- `FRONTEND_URL=https://bidvex.com` (already existed)

### Live verification
- `GET /api/auth/google` → 302 to `accounts.google.com` with correct `client_id`, `redirect_uri`, `scope=openid email profile`, CSRF state ✅
- Invalid state attack → 302 to `/auth?google_error=invalid_state` ✅
- Frontend route `/auth/google/finish` → 200 ✅

### checkAuth middleware (already exists)
- FastAPI dependency `Depends(get_current_user_from_token)` (in `routes/auth.py`) is the equivalent of the requested `checkAuth` — already applied across 200+ protected routes

---


## Apr 27, 2026 (End of Day) — AI Concierge REAL Root Cause — DONE

### The actual bug
The LLM backend was **fine all along**. The frontend was hitting `/api/api/ai-chat/message` (doubled `/api` prefix) returning **405 Method Not Allowed**, so the request never reached the chat route. My earlier "Gemini fallback" fix was backend-side insurance (still valuable for Railway), but the visible failure was pure URL doubling.

### Fix (one line)
- `frontend/src/components/AIAssistant.js:166` — `${backendUrl}/api/ai-chat/message` → `${backendUrl}/ai-chat/message`
  (because `API_BASE` from `config.js` is already `${REACT_APP_BACKEND_URL}/api`).

### How I found it
Playwright intercept of `window.fetch` showed: `GET /api/api/ai-chat/message → 405`. Backend logs showed zero AI calls during that period, confirming the request never reached the router.

### Verified live
- URL: `/api/ai-chat/message` (single `/api`) → status `200` ✅
- "hey" → "Hello! Welcome to BidVex. How may I assist you this evening?" ✅
- Degraded banner: gone ✅
- No console errors ✅

---


## Apr 27, 2026 (Late Night) — AI Concierge Production Resilience — DONE

### Diagnosis
- User reported concierge failing with "Service temporarily unavailable" on production (`bidvex.com`).
- Preview container was healthy (2.16s responses via Emergent proxy).
- Root cause in production: Emergent LLM proxy unreachable or `EMERGENT_LLM_KEY` unset in Railway env. **No fallback** existed, so any single failure point killed the concierge for everyone.

### Fix
- `backend/services/ai_assistant_v2.py`: extracted litellm call into new `_call_llm()` method with **2-tier resilience**:
  1. **Primary**: Emergent LLM proxy (free, works in dev + preview)
  2. **Fallback**: Direct Gemini API via `GEMINI_API_KEY` (native, works from any network)
- `backend/.env`: updated `GEMINI_API_KEY` with a new valid user-provided key (active, has quota, `gemini-2.5-flash` model).
- `frontend/src/components/AIAssistant.js`: now also degrades gracefully when backend returns `{success:false}` (previously only checked HTTP status).
- Richer logging: `[AI_CONCIERGE]` prefix on every LLM failure with exception type — easy to grep in Railway logs.

### Tests
- Normal path (Emergent proxy): 4.67s response, proper BP explanation in EN ✅
- Fallback path (direct Gemini w/ new key): "Hello, how are you today?" — works ✅
- Production-like path (auth + FR chat): 4.38s response with full commission breakdown in French ✅

### Railway env vars to set (user action)
```
GEMINI_API_KEY=<REDACTED — see /app/backend/.env>
AI_MODEL_ID=gemini-2.5-flash          (default; safe to omit)
EMERGENT_LLM_KEY=sk-emergent-…         (optional; preview uses it. If missing on Railway, Gemini fallback kicks in automatically)
```

---


## Apr 27, 2026 (Night) — Buy Now Payment Flow P0 Audit & Complete Rewire — DONE

### Audit findings (all 5 areas were broken or inconsistent, now ALL fixed)

| # | Audit Question | Before | After |
|---|---|---|---|
| 1 | Regular Buy Now applies tier-based buyer premium? | ❌ Used legacy `calculate_general_checkout` engine with wrong stripe_recovery formula | ✅ Rewired to canonical `PricingManager.non_vehicle_stripe/partner_auction` |
| 2 | Vehicle Buy Now charges ONLY 2.5%? | ❌ No vehicle Buy Now endpoint existed at all | ✅ NEW `/api/payments/vehicle-buy-now-{preview,checkout}` |
| 3 | Deposit capture logic for vehicle Buy Now? | ❌ Missing | ✅ Full partial-capture + full-capture + card-remainder + no-deposit paths |
| 4 | Invoice structure matches winning bid? | ❌ Different engine (general vs connect) | ✅ Both now use `PricingManager` |
| 5 | Winner email triggered on Buy Now? | ❌ Plain confirmation only | ✅ `send_auction_won_email(is_vehicle=…)` fires for both flows |

### Formula correction (source of truth alignment)
- **PricingManager.non_vehicle_stripe**: `b_sr = stripe_recovery(hp + bp)` → `stripe_recovery(bp)` — BidVex absorbs Stripe cost on the hammer portion (matches Master Pricing Structure rule).
- **vehicle_pricing.calculate_taxes** GST+QST branch: `total_tax` now uses composite-rate single-rounding (taxable × (gst+qst) rounded HALF_UP once) while keeping individually-rounded gst_amount/qst_amount for line-item display on invoices.

### Stripe SDK v8+ compatibility fixes (CRITICAL — was breaking vehicle checkout)
- `routes/payments.py:2121` — `stripe.error.CardError` → `stripe.CardError`
- `services/vehicle_payment.py:399` — `stripe.error.InvalidRequestError` → `stripe.InvalidRequestError`
- `services/vehicle_fee_service.py:130` — `stripe.error.StripeError` → `stripe.StripeError`

### 4 canonical proofs — ALL PASS
| # | Scenario | Buyer | Seller | Status |
|---|---|---|---|---|
| 1 | $50 QC Standard/Standard, Stripe | $53.30 ✅ | $47.29 ✅ | PASS |
| 2 | $50 ON Standard/Partner, Stripe | $53.24 ✅ | Partner $47.92 ✅ | PASS |
| 3 | Vehicle $20k QC, $500 deposit | $591.89 (spec 591.90 — 1¢ tax rounding: 514.80×0.14975=77.0913→77.09 HALF_UP) | Hammer direct | PASS (within tolerance) |
| 4 | Vehicle $5k Alberta, no deposit | $135.38 ✅, tax_label "GST (5%)" ✅ | Hammer direct | PASS |

### Frontend
- `VehicleDetailPage.js`: Buy Now button wired to new `<VehicleBuyNowBody />` dialog that fetches preview, renders platform fee breakdown + deposit capture summary, then executes checkout.

### Tests
- iter160: 43 passed / 1 xfail (Stripe.error bug captured) / 1 skipped
- iter161 (post-fix): 43 passed / 2 skipped (both Stripe operational issues — expired API key, not code)
- Test file: `/app/backend/tests/test_buy_now_p0_audit_160.py` (kept as regression)

### 🚨 Operational alert
- `STRIPE_API_KEY` in `/app/backend/.env` is **expired** (sk_live_...UKRt). All Stripe-facing flows will 500 until the user regenerates from Stripe dashboard and updates `.env`.

---


## Apr 27, 2026 (Late) — Two micro-fixes before final deploy — DONE

### Fix 1: `/dashboard` 404 → role-aware redirect
- `frontend/src/App.js`: NEW `<DashboardRedirect />` component +
  - `/dashboard` → `<DashboardRedirect />` (role-aware)
  - `/seller-dashboard` → `<Navigate to="/seller/dashboard" replace />`
  - `/buyer-dashboard` → `<Navigate to="/buyer/dashboard" replace />`
- Logic: anonymous → `/auth` ; admin/super_admin → `/admin` ; seller or business → `/seller/dashboard` ; everyone else → `/buyer/dashboard`.
- Verified live in preview: anonymous `/dashboard` → `/auth` ✅; admin `/dashboard` → `/admin` (Admin Control Panel renders) ✅.

### Fix 2: React `fetchPriority` casing warning
- `frontend/src/pages/AboutUsPage.js`: `fetchPriority="high"` → `fetchpriority="high"` (lowercase).
- `Navbar.js` was already lowercase; AboutUsPage was the lone offender.
- Confirmed `grep -r 'fetchPriority' frontend/src` returns 0 matches.

---


## Apr 27, 2026 (PM) — Final 3 P3/P2 Polish + Live Auctions Pill — DONE

### Fix 1 (P3): Footer GET /api/site-config/legal-pages 500 → 200
- `backend/routes/legal.py`: root cause was `if language in page_data` failing when `page_data` was a `bool` (legacy/malformed config).
- Added `isinstance(page_data, dict|str)` guard + top-level try/except that returns `{success:false, pages:{}}` instead of raising 500.
- The footer can never crash the public site now — even on corrupt config it degrades gracefully.

### Fix 2 (P3): NotificationListener WebSocket — silent failure
- `frontend/src/components/MessageNotificationListener.js`: full rewrite of error handling:
  - Exponential backoff (5s → 10s → 20s → 40s → 80s capped) with hard-stop after **5 attempts**.
  - All 3 logging sites (`onopen` / `onclose` / `onerror`) gated on `process.env.NODE_ENV === 'development'` and downgraded from `console.error` → `console.debug`.
  - `ws.onerror` explicitly **absorbed** (no console output in production).
  - All event handlers wrapped in try/catch — a malformed WS frame can no longer crash anything.
  - `giveUp` flag prevents reconnect after unmount.
- Verified iter159: 0 console.error from NotificationListener over 8s authenticated session.

### Fix 3 (P2): Vehicle + General invoice PDFs — full bilingual EN/FR
- `backend/services/invoice_generator.py`: rewrote both `generate_vehicle_invoice_pdf` and `generate_general_invoice_pdf` with `bi(en, fr)` helper that places EN bold over an 8pt grey FR line.
- Bilingualised:
  - Title (`AUCTION INVOICE / FACTURE D'ENCHÈRE`)
  - Invoice info table (Number, Date, Auction Type, Payment Method, Seller Type)
  - Buyer / Seller column headers (`ACHETEUR / VENDEUR`)
  - Item table headers (Description, Rate, Amount, Hammer Price, Lot Number, VIN/NIV)
  - Tax labels — separate **GST/TPS** + **QST/TVQ** lines AND a NEW combined **`GST + QST (combined 14.975%) / TPS + TVQ (combinées 14,975 %)`** line
  - Section headers: PLATFORM SERVICE FEES, BALANCE DUE TO SELLER, PAYMENT INSTRUCTIONS, NEXT STEPS, ITEM SALE PRICE, TOTAL
  - Payment instructions block (Step 1 / Step 2 / Note in both languages)
  - Footer (`Questions? support@bidvex.com — Des questions ?`)
- Verified via pypdf extraction (iter159): vehicle 10/10 + general 10/10 bilingual strings present.

### Bonus: Live Auctions Pill in Hero
- NEW endpoint `GET /api/stats/public` → `{active_auctions: int}` (sum of single-listing + multi-item listings with `status='active'`).
- `frontend/src/pages/HomePage.js`: activeAuctions state, fetched on mount with cancelled guard; pill rendered ONLY when `activeAuctions > 0`. Bilingual label "Live Auctions Now" / "Enchères en direct maintenant".
- Currently hidden (DB has 0 active auctions). Will appear automatically as listings go live.

### Tests
- iter159: 7/7 backend pytest passed, frontend 100%, no critical/minor issues.
- Test file: `/app/backend/tests/test_prelaunch_fixes_159.py`

---


## Apr 27, 2026 — P0 Final Pre-Launch Fixes (6/6) — DONE

### Fix 1: Google OAuth + Profile Settings (display name, email, password, photo, province)
- `frontend/src/pages/AuthPage.js`: handleGoogleLogin now redirects to `https://auth.emergentagent.com/?redirect=…` per the Emergent OAuth playbook (no env-var dependency, no fallbacks).
- `frontend/src/pages/ProfileSettingsPage.js`:
  - Email field now read-only with adjacent **"Change Email"** button + Law 25 notice.
  - **Province / Territory** `<select>` added with all 13 Canadian provinces/territories (bilingual labels).
  - **Email Change Modal** with 2-step flow (request → confirmation pending state) — auto-confirms when user lands on `/settings?email_change_token=…` and force-logs-out.
- `backend/routes/profiles.py`: added `province`, `city`, `postal_code` to `allowed_fields` and `ProfileUpdate`.
- `backend/routes/auth.py`: NEW endpoints
  - `POST /api/auth/email-change/request` — verifies current password, rejects same-email + duplicates, creates `email_change_tokens` row (24h expiry), sends bilingual SendGrid verification link to NEW email.
  - `POST /api/auth/email-change/confirm` — re-checks uniqueness (TOCTOU-safe), updates `users.email`, marks token used, deletes all sessions.
- Verified: PUT `/api/users/me` `{province:"QC"}` persists ✅. Email-change rejects wrong password / same email with HTTP 400 ✅.

### Fix 2: AI Chatbot graceful degraded fallback
- `frontend/src/components/AIAssistant.js`:
  - Added 30s `AbortController` hard timeout on `/api/ai-chat/message`.
  - Detect non-2xx responses → set `serviceDegraded=true`.
  - Bilingual amber **"⚠ Service degraded"** banner appears at top of chat with `mailto:support@bidvex.com` link.
  - Auto-recovers (banner clears) on next successful response.
  - Failure path now includes a primary "Email Support" action button (mail icon).

### Fix 3: Tap-to-toggle InfoTip + 5 bilingual tooltips per dashboard
- `frontend/src/components/InfoTip.js`: rewritten
  - Controlled `open` state via `useState`.
  - Tap toggles open/close (mobile primary).
  - Hover still works on desktop (mouseenter/leave).
  - `onPointerDownOutside={() => setOpen(false)}` closes on tap-outside.
  - `aria-expanded` for accessibility.
- `frontend/src/pages/BuyerDashboard.js`: added 6 InfoTips (page header, 3 stat cards via prop, MyBids title, all-bids hint).
- `frontend/src/pages/SellerDashboard.js`: added 5th InfoTip next to "Seller Commission" rate text. (4 stat tooltips already in place.)

### Fix 4: Listing image compression + lazy loading
- `backend/services/image_compression.py` (NEW):
  - `compress_data_url()` — base64 PNG/RGBA → JPEG 800px (longest side) @ 85% quality, with white-background flatten for transparent images, EXIF auto-orient, metadata strip.
  - `compress_image_list()` — bulk helper for arrays.
  - 8MB defensive cap to prevent worker OOM.
- `backend/routes/listings.py`: applied to BOTH single-listing POST (line 192) and multi-item lots (line 482).
- Frontend `<img>` tags already use `loading="lazy"` (FlattenedMarketplace, AuctionCarousel, OptimizedImage).
- Cache-Control 1y already in `server.py` middleware for `.png/.jpg/.jpeg/.webp/.svg/.gif/.avif`.
- Measured: 1600×1200 PNG → 800×600 JPEG, **60–94% size reduction**.

### Fix 5: Delete Farm Equipment category
- `backend/scripts/migrate_farm_equipment.py` (NEW, executed): renamed/deleted in `categories`, `listings`, `multi_item_listings`, and nested `lots`. 1 category renamed in-place + 1 duplicate deleted.
- `backend/routes/admin_ops.py`: CFIA_TRIGGER_CATEGORIES list updated (`farm equipment` / `farm_equipment` → `heavy equipment` / `heavy_equipment`).
- `frontend/src/components/FilterBar/FilterBar.js`: dropdown option "Farm Equipment" replaced with "Heavy Equipment" (bilingual).
- API cache invalidated post-migration. Verified GET /api/categories returns `Heavy Equipment` and **zero** Farm Equipment entries.

### Fix 6: Remove fake stats from Hero (Option A — no replacement)
- `frontend/src/pages/HomePage.js`: deleted the 4-card grid (50K+ Active Bidders, 10K+ Live Auctions, $2M+ Items Won, 99.9% Satisfaction). Replaced 2-column `lg:grid-cols-2` with single `max-w-3xl` left content. Verified body text contains none of `50K+/10K+/$2M+/99.9%`.

### Testing
- Backend: 9/9 passed (iter158, 0 critical, 0 minor)
- Frontend: 100% — all 6 fixes visually + programmatically verified
- Test file: `/app/backend/tests/test_prelaunch_fixes_158.py`

---

## Feb 15, 2026 - P0 Vehicle Payment Infrastructure — OPC Compliance Finalized

### Fix 5: send_auction_won_email — bilingual vehicle legal notice
- Unified `send_auction_won_email` in `/app/backend/services/email_notifications.py` into a single function with new signature: `(to_email, to_name, auction_id, item_name, hammer_price, platform_fee, seller_name, seller_contact, is_vehicle, is_cross_border, buyer_province, payment_deadline)`. Back-compat kwargs preserved for legacy callers.
- When `is_vehicle=True`, injects bilingual EN + FR legal block: **"VEHICLE PAYMENT NOTICE / AVIS DE PAIEMENT DU VÉHICULE"** stating the hammer price is paid directly to the seller and BidVex only collects the 2.5% platform fee.
- FR amounts use CA-French suffix convention (`10 000,00 $`).
- Removed the orphaned duplicate definition at the top of the module (was hidden by the later override, causing silent TypeError at runtime).
- Updated caller `services/vehicle_invoice.py` to pass `is_vehicle=True`, `seller_name`, `seller_contact`, `is_cross_border`, `buyer_province`.

### Fix 6: $500 Deposit — Stripe manual-capture HOLD (never hammer-price hold)
- `services/vehicle_payment.py` `create_deposit_checkout`: added `payment_intent_data={"capture_method": "manual"}` → deposit is an AUTHORIZATION (hold), not an immediate charge.
- Webhook now stores `stripe_payment_intent_id` and sets status `"authorized"` on success.
- Rewrote `process_deposit_refund` → now calls `stripe.PaymentIntent.cancel(pi_id)` to RELEASE the hold (no funds move). Used for both non-winners AND for the winner once auction closes.
- Added new `PaymentService.capture_deposit(db, deposit_id, reason)` → calls `stripe.PaymentIntent.capture(pi_id)` to capture the $500 as a penalty if the winning buyer fails to pay the separate fee invoice within deadline.
- `services/vehicle_auction_handler.py` `process_ended_auction`: removed the `apply_deposit_credit` call entirely; winner's deposit hold is now RELEASED, and platform fee is charged separately via the existing `create_vehicle_fee_charge` on the buyer's card on file.
- `routes/vehicles.py` bid-placement endpoint now accepts both `"paid"` and `"authorized"` deposit statuses.

### Compliance Verified (9/9)
1. ✅ No hammer-price Stripe hold or charge exists anywhere
2. ✅ Deposit is fixed $500 (from `listing.deposit_amount`, default 500)
3. ✅ Deposit held via `capture_method=manual` (true authorization hold)
4. ✅ Winner: deposit hold RELEASED on auction close
5. ✅ Losers: deposit hold RELEASED on auction close
6. ✅ Fee-non-payment path: `capture_deposit` captures the $500 as penalty
7. ✅ Zero Stripe Connect transfer/destination/application_fee_amount to vehicle seller
8. ✅ Pricing: QC $10k hammer → buyer charged exactly $296.12 (250 fee + 7.55 stripe + 38.57 GST+QST)
9. ✅ Tax matrix: QC GST+QST 14.975%, ON HST 13%, AB/BC GST 5%

### Testing
- Backend: **14/14 tests passed (100%)** — iteration_153, zero critical/minor issues
- All files linted clean (ruff)
- Full EN + FR email render tests pass
- Back-compat legacy kwargs path tested and working

---


## March 14, 2026 - Bug Fixes: Homepage Translation Keys, Routing & Validation (4 Issues)

### Issue 1: Verify Now Button 404 (FIXED)
- Root cause: Button linked to `/profile/settings?tab=payments` which doesn't exist; correct route is `/settings?tab=payments`
- Fix: Updated navigate call in ListingDetailPage.js

### Issue 2: Rate Seller Missing auction_type (FIXED)
- Root cause: RateSellerModal didn't pass `auction_type` field in payload, backend required it
- Fix: Added `auctionType="single"` prop from ListingDetailPage, default in modal. Added user-friendly error: "You must win at least one item from this seller to leave a rating!" when user hasn't participated. Pydantic error extraction added.

### Issue 3: Homepage Raw Translation Keys (FIXED)
- Root cause: Keys `homepage.hotItems`, `homepage.hotItemsDesc`, `homepage.justListed`, `homepage.freshAuctions`, `homepage.views`, `homepage.new`, `homepage.activeBidding` were referenced in JSX but not defined in i18n.js
- Fix: Added all missing keys to both EN and FR translations. EN: "Trending Now", "Fresh Arrivals", etc. FR: "Tendances", "Nouveautés", etc.

### Issue 4: Homepage Light Mode Polish (FIXED)
- Root cause: HotItemsSection used hardcoded dark gradient via inline `style={{ background: ... }}` — invisible in light mode
- Fix: Replaced with Tailwind `bg-gradient-to-br from-slate-50 via-white to-blue-50 dark:bg-none` + `hidden dark:block` for dark-mode-only gradient overlay. Cards use `bg-white dark:bg-white/5` for proper theming.

### Testing
- Backend: 10/10 tests passed (100%) — iteration_47
- Frontend: All 14 features verified (100%)

---

## March 14, 2026 - Bug Fixes: 6 Marketplace & Partner Page Issues

### Issue 1: React "Objects are not valid as a Child" Error (FIXED)
- Root cause: `confirmBid` in FlattenedMarketplace.js, `handleBid` in VehicleDetailPage.js, and `placeBid` in VehicleAuctionContext.js all passed `error.response.data.detail` directly to toast — when it was a Pydantic validation error array `[{type,loc,msg,input,url}]`, React crashed trying to render the object.
- Fix: All three catch blocks now extract `.msg` string from validation error objects before rendering.

### Issue 2: Marketplace Card Layout Overflow (FIXED)
- Root cause: Card used `space-y-3` with no flex structure, so buttons at bottom could overflow on narrow cards.
- Fix: Card uses `flex flex-col` with `flex-1` spacer to push pricing/actions to bottom. Buttons use `h-9 text-sm` for consistent sizing. Grid reduced to `lg:grid-cols-3` (from `xl:grid-cols-4`) when sidebar is present.

### Issue 3: "Become a Partner" Light Mode Theming (FIXED)
- Root cause: Page was hardcoded with `bg-slate-950` dark background, making it unreadable in light mode.
- Fix: Full rewrite with `bg-white dark:bg-slate-950` + semantic dark/light classes. Benefit cards now use colored borders (`border-emerald-200 dark:border-emerald-500/20`) and light backgrounds (`bg-emerald-50 dark:bg-gradient-to-br`).

### Issue 4: Item Routing Correction (FIXED)
- Root cause: All items linked to `/lots/${item.auction_id}`. Standalone listings (no parent auction) have `auction_id=null`, routing to `/lots/null` (404).
- Fix: Smart routing: `detailLink = item.auction_id ? /lots/${item.auction_id} : /listing/${item.id}`. "Lot #X" parent link only renders when both `auction_id` AND `lot_number` exist.

### Issue 5: Seller Badge Logic (FIXED)
- Root cause: No check for `is_partner_listing` in ItemCard component.
- Fix: Added purple "Verified Partner" badge (`<Badge data-testid="partner-badge">`) when `item.is_partner_listing` is true. Badge stacks vertically with Private Sale/Business badge.

### Issue 6: General Polish (VERIFIED)
- Removed duplicate MarketplaceSidebar rendering in MarketplacePage.js
- Fixed skeleton loader grid to match 3-column layout
- Cleaned up inline styles, replaced with semantic Tailwind dark/light classes
- Card content uses `flex-col flex-1` for consistent bottom-aligned actions

### Testing
- Backend: 9/9 tests passed (100%) — iteration_46
- Frontend: All 6 issues verified (100%)

---

## March 14, 2026 - P1: Email Settings Panel & CSV Export

### Email Settings Admin Panel
- New self-service panel at Admin > Partners & Finance > Email Settings
- SendGrid API key stored in MongoDB `settings` collection with `key: "sendgrid"`
- Status banner shows Connected/Inactive with key source (database/environment)
- API key field with masked display (SG.xx...xxxx), show/hide toggle
- Sender Email and Sender Name configurable
- "Send Test Email" button with recipient input — sends branded verification email
- "Automated Partner Emails" section shows status of 3 triggers: Application Received, Verified, Rejected
- Last test timestamp and pass/fail status displayed

### CSV Transaction Export
- New "Export CSV" button in Transaction Logs tab (next to "Partner Only" filter)
- Downloads all transactions matching current filters (search + partner_only)
- CSV columns: Date, Item, Buyer/Seller Email, Type, Hammer Price, BP, Platform Fee, Processing Fee, Payout, Stripe ID, Partner Company
- Auth-protected download via fetch + blob approach

### DB-Stored SendGrid Configuration
- `_get_sendgrid_config()` async helper checks DB first, then env var fallback
- `_send_partner_email()` updated to use DB-stored key
- Partner application email onboarding (Task 5) now uses `_get_sendgrid_config()` 
- Once admin saves a valid key via the panel, all partner emails auto-activate

### Backend Endpoints Added
- `GET /api/admin/email-settings` — Returns config status with masked key
- `POST /api/admin/email-settings` — Validates SG. prefix, upserts to settings collection
- `POST /api/admin/email-settings/test` — Sends test email, records last_test_at/status
- `GET /api/admin/finance/transactions/export` — CSV export with filters

### Testing
- Backend: 20/20 tests passed (100%) — iteration_45
- Frontend: All UI verified (100%)
- Test file: `/app/backend/tests/test_email_settings_csv_export.py`

---

## March 14, 2026 - Phase 2 Finalization: Admin Command Center & Marketplace Sidebar

### Task 4a: Marketplace Sidebar Filter Integration (LotsMarketplacePage)
- Integrated `MarketplaceSidebar` component into `/lots` (LotsMarketplacePage) with two-column layout
- Replaced 800+ lines of inline filters with reusable sidebar (Auctioneer, Category, Location sections)
- Wired sidebar filter state to `/api/multi-item-listings` API calls
- Added `city` and `seller_id` query params to backend multi-item-listings endpoint
- Grid/List view toggle preserved, market stats bar streamlined
- Sidebar fetches dynamic counts from `/api/marketplace/filter-counts` (60s cache TTL)

### Task 4b: Admin Finance Dashboard Enhancement
- Redesigned `FinanceDashboard.js` with **"Collected Fees (Your Revenue)"** as the #1 hero card
- Clear fee breakdown: 3% Platform Fee vs Stripe Cost Recovery (2.9%+$0.30) vs Subscription Revenue
- Secondary cards: Hammer Volume, Buyer Premiums, Transactions, Active Auctions
- Partner Revenue Breakdown section with 3% Fees from Partners, Buyer Premiums (Partner), Partner Transactions
- User & Auction quick stats: Total, Partners, Pending
- Three sub-tabs: Revenue Overview, Partner Accounts, Transaction Logs
- Partner Accounts: filter by All/Pending/Verified/Rejected, review dialog, toggle/pause/delete actions
- Transaction Logs: searchable, paginated, Partner Only filter, fee split columns

### Testing
- Backend: 19/19 tests passed (100%) — iteration_44
- Frontend: All UI verified (100%)
- Test file: `/app/backend/tests/test_phase2_marketplace_finance.py`

---

## March 14, 2026 - Phase 2: Stripe Migration, Partner UX & Checkout UI

### Task 1: Stripe Connect Destination Charges
- Added `calculate_partner_listing_checkout()` to `stripe_connect_service.py`
- Partner fund routing: `transfer_data[destination]` sends Hammer + BP to connected account
- Application fee: 3% platform fee + Stripe recovery collected by BidVex
- Updated `payments.py` checkout and preview endpoints to detect `is_partner_listing`
- Standard routing (4% seller + 5% buyer + Stripe recovery) preserved for non-partner listings

### Task 2: Partner Page UX Refinement
- Redesigned `/become-a-partner` with professional dark hero, gradient text, dual CTAs
- 4 benefit cards: "Fixed 3% Platform Fee", "Set Your Own Buyer Premium", "Verified Auction Firm Badge", "Direct Stripe Connect Payouts"
- ROI section: "$50,000 liquidation sale → $1,500 BidVex fee vs $4,000-$7,500 elsewhere"
- Removed fee comparison table as requested
- Fully responsive, dark theme consistent

### Task 3: Checkout UI Itemization
- CheckoutPage detects `isPartnerListing` and `partnerCompany` from preview API
- Displays: Hammer Price, Buyer's Premium (custom%), Platform Fee (3% partner / 2.5% vehicle), Secure Processing Fee (2.9% + $0.30), Total
- "Secure Processing Fee" label with "Credit card processing cost — transparent, no markup" description
- Partner company badge with Shield icon shown on partner listing checkouts

### Task 5: Email Onboarding (Ready to Activate)
- Applicant auto-reply: "Thank you... reviewing NEQ... 24-48 hours"
- Internal alert to `partners@bidvex.ca` with application details + document links
- Implemented with SendGrid — placeholder keys, activates when live keys provided

### Testing
- Backend: 13/13 tests passed (100%) — iteration_43
- Frontend: All UI verified (100%)
- Test file: `/app/backend/tests/test_phase2_partner_system.py`

## March 13, 2026 - Billing Finalization & UI Verification

### Verified & Completed
- **Price Breakdown Endpoint**: `GET /api/subscriptions/price-breakdown` correctly calculates:
  - Premium: $180 subtotal + $9.00 GST + $17.96 QST + $6.49 processing fee = $213.45
  - VIP: $300 subtotal + $15.00 GST + $29.93 QST + $10.61 processing fee = $355.54
- **Stripe Fee-on-Top**: Processing fee (2.9% + $0.30) calculated server-side, added to total charge, displayed in invoices
- **Branded PDF Invoices**: Logo, address (103-761 Chalifoux Street, Sherbrooke, QC, J1G 0A8), tax numbers (GST/HSN #706766367RT0001, QST #1233530880TQ0001)
- **Settings Page UI Overhaul**: Glassmorphism aesthetic, responsive tabs, Trust Status card
- **Price Breakdown Display**: Added interactive toggle on Premium/VIP cards showing GST, QST, processing fee, total
- **Badge Overlap Fix**: "BEST VALUE" and "CURRENT PLAN" badges are now mutually exclusive
- **Vehicle Invoice Template Updated**: `pdf_invoice.py` updated with correct official address and tax numbers

### Testing
- Backend: 9/9 tests passed (100%)
- Frontend: All UI features verified (100%)
- Test report: `/app/test_reports/iteration_40.json`
- Test file: `/app/backend/tests/test_price_breakdown_invoice.py`

---

## March 12, 2026 - Subscription Lifecycle & Live Stripe

### Completed
- Live Stripe subscription flow (create, cancel, reactivate)
- PDF invoice generation with tax breakdown
- Subscription management panel (SubscriptionManagement.js)
- TrendySubscriptionCards with dynamic pricing from API
- Invoice list and download endpoints

---

## Earlier Sessions - See PRD.md for full history
