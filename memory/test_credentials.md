# BidVex Test Credentials

## Admin (email/password)
- Email: charbel911@gmail.com
- Password: Anderosli123!@#
- Role: Admin (full access)

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
