# BidVex Test Credentials

## Admin (email/password)
- Email: charbel911@gmail.com
- Password: Anderosli123!@#
- Role: Admin (full access)

## Test buyer (for vehicle-settlement dispute tests)
- Email: p0bugtest@example.com
- Password: TestBuyer123!
- Role: user (regular buyer); phone_verified=true, id_verified=true
- Notes: created 2026-05-04 for the iter181 P0 sprint and reused by iter182 promotion tests.

## Legacy test buyer (kept for backward compat — may not log in if password reset on prod)
- Email: abc@gmail.com
- Password: TestBuyer123!


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
