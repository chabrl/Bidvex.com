# BidVex — Auction Marketplace PRD

## Original Problem Statement
Full-stack auction marketplace (React frontend, FastAPI backend, MongoDB) with vehicle-specific identity routing, real-time WebSocket bidding, self-hosted Web Push notifications (VAPID), predictive AI analytics, and 18 active background schedulers.

## Architecture
```
/app
├── backend/
│   ├── server.py                      # FastAPI, CORS, CDN headers, SPA mount
│   ├── shared.py                      # Pydantic models
│   ├── deps.py                        # Shared auth dependencies (JWT, get_current_user)
│   ├── routes/
│   │   ├── auth.py                    # Auth: login, register, reset, change-password
│   │   ├── email_marketing_ext.py     # Marketing campaigns: CRUD + Delete/Resend/Clone
│   │   ├── ai_chat.py                 # Master Concierge chatbot (EMERGENT_LLM_KEY)
│   │   └── ...
│   └── services/
│       ├── ai_assistant_v2.py         # Gemini 2.5 Flash via litellm + Emergent proxy
│       ├── translation_service.py     # EN<->FR via litellm + Emergent proxy
│       └── email_service.py           # Production SendGrid (click tracking disabled)
├── frontend/
│   └── src/
│       ├── contexts/AuthContext.js     # Auth state management (fixed: 401-only logout)
│       └── components/
│           └── FlattenedMarketplace.js # Compare bar (fixed: z-index above mobile nav)
```

## Completed (April 10-11, 2026)

### Critical Auth Fix — "Daily Password Reset" Bug
- **Root causes identified**: JWT expired after 24h + frontend logout() on ANY error (not just 401)
- **JWT expiration**: Extended from 24h to 7 days (168h), configurable via `JWT_EXPIRATION_HOURS` env var
- **Email normalization**: All auth paths (login, register, forgot-password) now use `.lower().strip()`
- **Frontend resilience**: `AuthContext.js` only calls `logout()` on HTTP 401, not on network timeouts/500s
- **Diagnostic logging**: Every login attempt logged with `[AUTH]` prefix, IP, email, and failure reason
- **NameError fix**: `force_reset_password` endpoint referenced undefined `jwt_secret` → fixed to use `JWT_SECRET`
- **Password field fallback**: Login now checks both `password` and `password_hash` fields (admin-created accounts)
- **All 8 backend + all frontend tests passed** (iteration_129)

### Master Concierge AI Chatbot Fix
- Replaced leaked Gemini API key → litellm + Emergent proxy (no emergentintegrations dependency)
- Also migrated translation_service.py to same approach

### Email Marketing Dashboard — Delete, Resend, Clone
- 3 new endpoints + frontend action buttons
- All tests passed (iteration_128)

### Compare Button Position Fix
- `z-[60]` + `bottom-28` on mobile — above MobileBottomNav

## Railway Deployment Checklist
1. Save to GitHub
2. Add `EMERGENT_LLM_KEY` to Railway env vars
3. Add `JWT_EXPIRATION_HOURS=168` (optional, defaults to 168)
4. Verify `JWT_SECRET` is set (required for production)

## 3rd Party Integrations
- Stripe — Live
- SendGrid — Live (Click Tracking disabled)
- Gemini 2.5 Flash — via litellm + EMERGENT_LLM_KEY
- VAPID Web Push — Active
- Twilio — Configured

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Admin offline order management
- (Enhancement) 2FA for high-value bidders
- (Enhancement) Automated Lighthouse audits
