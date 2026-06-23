# BidVex Test Credentials

## 🔒 PERMANENT — Sole Admin (DO NOT CHANGE)
**The admin email is `charbel911@gmail.com` — forever.** This is the only and permanent admin account for BidVex. Any new admin-related feature (compliance digests, alerts, escalations, system notifications, audit emails) must route here unless the user explicitly says otherwise.

## Admin (email/password)
- Email: charbel911@gmail.com
- Password: Anderosli123!@#
- Role: Admin (full access)
- Note (iter212, 2026-05-14): Auto-flagged `is_storage_facility=True` + `account_type=storage_facility` because they own the legacy "Bidvex Inc." storage facility. The `role=admin` override keeps the navbar/route restrictions disabled for them.
- Note (iter226, 2026-02-24): Confirmed permanent sole admin for the platform.

## 🌱 iter306 — Production Demo Seed Users (Jun 15, 2026)
Seeded via `python /app/backend/scripts/seed_production_demo.py --execute` (idempotent — safe to re-run).

### Test Buyer
- Email: testbuyer@bidvex.com
- Password: TestBuyer2026!
- Role: user (individual buyer)
- Province: QC

### Test Seller (trusted)
- Email: testseller@bidvex.com
- Password: TestSeller2026!
- Role: user (trusted_seller=True)
- Province: QC

### Test Vehicle Dealer
- Email: testdealer@bidvex.com
- Password: TestDealer2026!
- Role: user (is_vehicle_dealer=True, vehicle_dealer_verified=True, seller_type=dealer)
- Province: QC
- Preferred language: FR
- **iter313 patch (Jun 22, 2026)**: Now also has an approved `vehicle_sellers` collection record (`business_name='Test Dealer Auto Corp.'`, `verification_status='approved'`) so the dealer-gate on `/vehicle-auctions/create` and `/vehicle-multi-lot/create` passes. Re-seeded by the updated `seed_production_demo.py` script via `upsert_vehicle_seller_profile`.



## Test buyer (for vehicle-settlement dispute tests)
- Email: p0bugtest@example.com
- Password: TestBuyer123!
- Role: user (regular buyer); phone_verified=true, id_verified=true
- Notes: created 2026-05-04 for the iter181 P0 sprint. ⚠️ iter189 testing agent found this login returns 401 on the preview env — password may have rotated. Use the replacement below if it fails.

## iter189 Test buyer (replacement — works on preview env)
- Email: iter189buyer@test.com
- Password: TestBuyer123!
- Role: user; terms_accepted + ai_disclosure_accepted
- Notes: created 2026-02-07 during iter189 consolidated test (id 93aa21c2-4e41-4235-a382-d4b8c8836d41).

## Legacy test buyer (kept for backward compat — may not log in if password reset on prod)
- Email: abc@gmail.com
- Password: TestBuyer123!

## iter189 Buyer Test Account (used by iter201 phase3 buyer-gate tests + iter203 compliance regression)
- Email: `iter189buyer@test.com`
- Password: `TestBuyer123!`
- Role: `buyer` (individual seller_type — non-dealer)
- Re-seeded 2026-02-08 — used for iter203 vehicle compliance live API tests

## iter189 Buyer Test Account 2
- Email: `iter189buyer@bidvex.com`
- Password: `TestBuyer123!`
- Notes: Backup buyer for iter201 phase3 buyer-gate tests


## iter209 Rejected-partner test account (Step 2 resubmission flow)
- Email: `iter209-rej-partner@example.com`
- Password: `Test123!@#`
- Role: user; partner_verification_status=rejected; partner_company_name="Auctioneer Inc"; partner_neq="1234567890"
- Notes: re-seed via `scripts/migrate_doc_urls_to_relative.py` not needed; the testing agent provided a re-seed script in `/app/test_reports/iteration_199.json` if the user gets consumed by a real resubmit.

## iter209 Rejected-dealer test account (Step 2 resubmission flow)
- Email: `iter209-rej-dealer@example.com`
- Password: `Test123!@#`
- Role: user; vehicle_sellers.verification_status=rejected; business_name="ABC Motors"; license_number="OMVIC-555"; license_province="ON"

## Direct Google OAuth 2.0
- Google Cloud Project: configured per `/app/backend/.env`
  - `GOOGLE_CLIENT_ID=<REDACTED — see /app/backend/.env>`
- **Authorized Redirect URIs (Google Console — verified by user 2026-05-05):**
  - Production: `https://bidvex.com/api/auth/google/callback`
  - Preview:    `https://prod-verify-2.preview.emergentagent.com/api/auth/google/callback`
- **Required env var per environment:**
  - Preview `.env`: `GOOGLE_CALLBACK_URL=https://prod-verify-2.preview.emergentagent.com/api/auth/google/callback` (currently set)
  - Production deploy: `GOOGLE_CALLBACK_URL=https://bidvex.com/api/auth/google/callback`
- Test flow: click "Continue with Google" → backend `/api/auth/google` → Google consent → backend `/api/auth/google/callback` → frontend `/auth/google/finish#token=…` → `/marketplace`

## Replacement test buyer (Feature Patch v9 — added 2026-02)
- Email: v9test_1779311352@bidvex.com
- Password: TestBuyer123!
- Role: user (regular buyer/seller)
- Note: created during v9 testing as a working replacement for the now-stale iter189buyer@test.com account. Used by /app/backend/tests/test_feature_patch_v9_live2.py.

## E2E Playwright bypass for cookie consent
Before clicking any button on `/auth`, automation runners should either click `text="Accept All Cookies"` first, OR set in browser context:
```js
localStorage.setItem('bidvex_cookie_consent', JSON.stringify({version: 1, accepted: true}));
```
Otherwise the Law-25 consent banner intercepts the Sign-In click.

## iter225 Buyer Test Account (re-seeded 2026-06-11 — verified working on preview)
- Email: iter225buyer@bidvex.com
- Password: TestBuyer225!
- Role: user (regular buyer)
- Notes: re-registered on this preview DB during iter301 (old account didn't exist → 401). New user id 85b3ce59-f264-4d43-8d12-19b3449ec8b3. Login verified via API on 2026-06-11. phone_verified=true set (phone +15145550199) so /messages UI is reachable for E2E.

## iter302 Buyer Test Account (created 2026-06-11 — settlement flow buyer)
- Email: iter302buyer@test.com
- Password: TestBuyer123!
- Role: user (regular buyer); phone_verified, email_verified, id_verified all true
- User id: eaf07e4e-052c-4ee9-932c-14609fa65743
- Stripe TEST customer cus_UgXyebdBBfbh49 with saved visa •••• 4242 (pm in `payment_methods` collection)
- Notes: This buyer WON the seeded listing `iter302-settle-test` (seller = admin) and already settled it via POST /api/settlement/settle — payment_collected, pickup code BVX-1H1J5GC9, payout queued (payout_pending). Used by the iter302 Directive 2 E2E tests.

## Re-seeded 2026-06-11 (accounts referenced by older suites — now working again on preview)
- p0bugtest@example.com / TestBuyer123! (phone+email+id verified)
- iter189buyer@test.com / TestBuyer123! (phone+email+id verified)

## ⚠️ Stripe key state on PREVIEW (2026-06-11, iter302)
- `STRIPE_API_KEY` in /app/backend/.env is the user's LIVE key (deliberate config since 2026-04-08; production bidvex.com has its own env).
- During iter302 it was TEMPORARILY swapped to the TEST key (STRIPE_TEST_SECRET_KEY) to safely E2E-test the buyer settle charge flow, then RESTORED to the live key the same day. Charges made during the swap were Stripe TEST-mode only.
- The iter302 test buyer's saved card (cus_UgXyebdBBfbh49 / visa 4242) lives on the TEST Stripe account — with the live key active, retrying a settle on seeded data returns a graceful 402 (no real charge possible).
- If future payment-flow testing is needed in preview, swap to the test key first (backup pattern: copy the STRIPE_API_KEY line aside, replace value with STRIPE_TEST_SECRET_KEY's value, restart backend, restore after).

## 🌱 iter308 — Re-seed script (Jun 18, 2026)
If any of the canonical fixture accounts below fail to log in on a fresh
preview DB, run:
```
python /app/backend/scripts/iter308_reseed_test_fixtures.py
```
This is idempotent — it creates missing accounts and password-resets
existing ones so the iter299→iter308 regression suite can run cleanly.

Accounts seeded / reset:
- `iter225buyer@bidvex.com` / `TestBuyer225!`
- `iter302buyer@test.com` / `TestBuyer123!`
- `testbuyer@bidvex.com` / `TestBuyer2026!`
- `testseller@bidvex.com` / `TestSeller2026!`
- `testdealer@bidvex.com` / `TestDealer2026!`

