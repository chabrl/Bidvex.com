# BidVex Test Credentials

## 🔒 PERMANENT — Sole Admin (DO NOT CHANGE)
**The admin email is `charbel911@gmail.com` — forever.** This is the only and permanent admin account for BidVex. Any new admin-related feature (compliance digests, alerts, escalations, system notifications, audit emails) must route here unless the user explicitly says otherwise.

## Admin (email/password)
- Email: charbel911@gmail.com
- Password: Anderosli123!@#
- Role: Admin (full access)
- Note (iter212, 2026-05-14): Auto-flagged `is_storage_facility=True` + `account_type=storage_facility` because they own the legacy "Bidvex Inc." storage facility. The `role=admin` override keeps the navbar/route restrictions disabled for them.
- Note (iter226, 2026-02-24): Confirmed permanent sole admin for the platform.

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
- `STRIPE_API_KEY` in /app/backend/.env was TEMPORARILY swapped to the TEST key
  (value of STRIPE_TEST_SECRET_KEY) so settlement charge flows can be tested
  without real money movement. The original LIVE key line is backed up at
  `/tmp/stripe_key_backup.txt` and MUST be restored before any production
  deploy from this workspace. Production (bidvex.com) carries its own env.
