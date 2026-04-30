# BidVex Test Credentials

## Admin (email/password)
- Email: charbel911@gmail.com
- Password: Anderosli123!@#
- Role: Admin (full access)

## Test buyer (for vehicle-settlement dispute tests)
- Email: abc@gmail.com
- Password: TestBuyer123!
- Role: user (regular buyer)


## Direct Google OAuth 2.0
- Pixel ID / Google Cloud Project: configured per `/app/backend/.env`
  - `GOOGLE_CLIENT_ID=<REDACTED — see /app/backend/.env>`
  - `GOOGLE_CALLBACK_URL=https://api.bidvex.com/auth/google/callback`
- Authorized JavaScript Origin (Google Console): `https://bidvex.com`
- Authorized Redirect URIs (Google Console): `https://api.bidvex.com/auth/google/callback`
  - For preview testing, ALSO add: `https://prod-verify-2.preview.emergentagent.com/api/auth/google/callback`
- Test the flow by clicking "Continue with Google" → backend `/api/auth/google` → Google consent → backend `/api/auth/google/callback` → frontend `/auth/google/finish#token=…` → `/marketplace`
