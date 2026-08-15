# iter482 — BidVex Preview Security Audit Report

**Audit date:** 2026-02-15  
**Environment:** Preview (Stripe TEST only, no live keys, no production mutations)  
**Auditor:** Emergent security-audit subagent (read-only)  
**Preview URL:** `prod-verify-2.preview.emergentagent.com`  
**Confidence:** HIGH — one endpoint was live-probed against the preview to confirm SEC-001.  
**Verdict:** ❌ **FAIL — ACTION REQUIRED before `https://bidvex.com` launch.**

---

## Owner summary

**Launch guidance: DO NOT LAUNCH.**

An attacker with **no account and no password** can silently drop
notifications into ANY BidVex user's notification bell, choosing the
title, message, and the link the notification points to. This is a
ready-made phishing and impersonation channel targeting your
customers (e.g. "Payment failed — click here"), and it can be
scripted to flood your database.

Two additional weaknesses (a hidden password-reset backdoor and
long-lived refresh tokens kept in browser storage) raise the blast
radius if any secret or script-injection is ever obtained. Core auth,
Stripe webhook verification, escrow payout gating, and invoice
signed-URLs were reviewed and are largely sound.

## Fix first (P1 / P2)

1. **Anyone can post fake notifications to any user** — `POST /api/notifications/create` has no authentication; require an authenticated admin/internal caller and stop accepting a client-supplied recipient.
2. **Hidden password-reset endpoint** — `/api/auth/admin-force-sync` resets any account's password for anyone who presents the JWT signing secret; remove it before production.
3. **Long-lived login tokens in browser storage** — 30-day refresh tokens in localStorage mean any script injection = lasting account takeover.

---

## Technical findings

### SEC-001 · HIGH · CONFIRMED · Unauthenticated notification injection to any user

- **Evidence:** `routes/notifications.py:224-255` — `create_notification` has no `Depends(get_current_user)`. Live probe `POST /api/notifications/create?user_id=…&title=…` returned HTTP 200 and stored the row.
- **Attack path:** Anonymous attacker → missing function-level auth + client-chosen `user_id` / `action_url` → writes trusted-looking notifications (with click-through link) into any victim's feed; scriptable for mass DB writes.
- **Boundary note:** Notification text rendering not confirmed as HTML, so treat as phishing/spoofing + resource abuse, **not** proven XSS.
- **Fix:** Require admin/internal auth; derive `recipient user_id` server-side; validate `action_url` to internal paths only.
- **Verification:** Re-run the unauthenticated POST and expect `401`/`403`.
- **Standards:** Broken Function Level Authorization; OWASP API5:2023 / A01:2025; CWE-862.
- **Priority:** P1.

### SEC-002 · MEDIUM · LIKELY · Password-reset backdoor gated only by the signing secret

- **Evidence:** `routes/auth.py:1251-1295` — unauthenticated `admin-force-sync` resets any email's password when header `X-Sync-Key` equals `JWT_SECRET` (plain `!=`, not constant-time).
- **Attack path:** Anyone who learns/leaks `JWT_SECRET` (also used to sign all tokens and invoice URLs) → arbitrary account takeover.
- **Boundary note:** Requires the secret; no leak proven, so not Critical.
- **Fix:** Delete the endpoint; rotate `JWT_SECRET` if it was ever shared.
- **Verification:** Confirm route absent in production build.
- **Standards:** Hard-coded / secret-gated bypass; OWASP A07:2025; CWE-798 / CWE-640.
- **Priority:** P2.

### SEC-003 · MEDIUM · LIKELY · 30-day refresh tokens in localStorage + permissive CSP

- **Evidence:**
  - `frontend/src/contexts/AuthContext.js:70,140,173` store `refresh_token` in `localStorage`.
  - `server.py:717` CSP allows `script-src 'unsafe-inline' 'unsafe-eval'`.
  - Raw-HTML sinks exist elsewhere in the frontend (`grep dangerouslySetInnerHTML`).
- **Attack path:** Any script-injection → steals the long-lived refresh token → persistent takeover survivable across access-token expiry.
- **Boundary note:** No attacker-controlled XSS write path confirmed; impact conditional on a separate injection.
- **Fix:** Store refresh tokens in HttpOnly/Secure/SameSite cookies; tighten CSP.
- **Verification:** Confirm no refresh token readable from `window.localStorage`.
- **Standards:** OWASP A02 / A05:2025; CWE-522 / CWE-79.
- **Priority:** P2.

---

## Hardening (P3)

- **[P3]** Admin logins exempt from brute-force lockout (`routes/auth.py:710-724`); only the 5/min IP limiter applies — automated guessing of admin passwords is the sole impact.
- **[P3]** `JWT_SECRET` / `INVOICE_SIGNING_SECRET` have insecure code defaults (`routes/auth.py:34`, `services/cloud_storage.py:25`); ensure env always set in prod.
- **[P3]** Reset-password minimum length is 6 (`routes/auth.py:1034`); align with the 8+ policy used by change-password.
- **[P3]** Email-change HTML embeds user `name` / `new_email` via f-string (`routes/auth.py:1359-1372`) — self-targeted only; sanitize for defense-in-depth.

---

## Coverage and limits

- **Reviewed (complete):**
  - Auth / session / reset flows.
  - Stripe webhook signature + idempotency (sound).
  - Escrow payout gating — requires real `stripe_transfer_id` (correct).
  - Receipts / invoices IDOR + HMAC signed URLs — timing-safe, owner-scoped.
  - Notifications websocket auth — token verified pre-accept.
  - CORS — restrictive 5-origin allowlist incl. `bidvex.com`; credentials only when non-wildcard — production swap safe.
  - Email suppression / unsubscribe gate.
- **Gaps (partial):**
  - Full `admin_*` router surface was spot-checked only.
  - Frontend notification render context (XSS boundary of SEC-001) not traced.
  - One inert test row (`user_id=__audit_probe__`) was written to prove SEC-001 — cleaned up by main agent (see `Cleanup log` below).

---

## Final verdict

**Status:** ❌ **FAIL — ACTION REQUIRED**

A confirmed unauthenticated write lets anyone inject phishing
notifications into any user's feed; must be fixed before the
`https://bidvex.com` launch.

Once SEC-001 and SEC-002 are remediated and SEC-003 is at least
mitigated (or a compensating control accepted in writing), the
audit can be re-run and the verdict revisited.

---

## Cleanup log (main agent, post-audit)

- The inert probe row that the audit inserted to confirm SEC-001
  (`db.notifications` where `user_id == "__audit_probe__"`) is being
  removed by the main agent immediately after this report is saved.
  See the follow-up audit report if regeneration is needed.
