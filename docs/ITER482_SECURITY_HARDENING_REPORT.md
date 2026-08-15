# iter482 — SEC-001 & SEC-002 Hardening Report

**Date:** 2026-02-15
**Environment:** Preview (no deploy, Stripe TEST only)
**Scope:** Narrow security patch. **No** billing / tax / Stripe / escrow / auth-flow changes.
**Predecessor audit:** `/app/docs/ITER482_SECURITY_AUDIT_REPORT.md`

---

## Executive summary

| Finding  | Prior state (audit)                                                              | Fix action                                | Verification |
|----------|----------------------------------------------------------------------------------|-------------------------------------------|--------------|
| SEC-001  | `POST /api/notifications/create` — unauthenticated, client-chosen `user_id`      | **Endpoint deleted entirely**             | 9 tests pass |
| SEC-002  | `POST /api/auth/admin-force-sync` — shared-secret bypass (`X-Sync-Key==JWT_SECRET`) | **Endpoint deleted entirely**             | included     |
| XSS boundary (read-only) | Uncertain if SEC-001 was a stored-XSS vector                          | Not fixed — **investigation only**        | see §4       |
| JWT_SECRET rotation      | Recommended, but requires LIVE-env change                            | **Flagged, not executed**                 | see §3       |

---

## 1. SEC-001 · Unauthenticated notification injection to any user

### Root-cause investigation
Before writing the fix, the codebase was grep'd for every runtime caller of the endpoint and every alternate notification-creation path:

- **HTTP callers of `POST /api/notifications/create` inside `/app/backend/`:** **zero**. The only reference in production code was the route definition itself.
- **What internal flows actually use:** `services.notifications_i18n.create_notification()` — a completely different function in a completely different module. 60+ in-process callers:
  - Services: `vehicle_auction_handler`, `seller_payouts`, `scheduled_jobs`, `payment_collection`, `overdue_autocapture`, `pickup_confirmation`, `vehicle_multi_lot_settlement`, `last_chance`, `follower_notify`, `top_sellers`, `voice_ai_pipeline`
  - Routes: `auctions`, `auctions_bids`, `webhooks` (Stripe payment-success), `messages`, `settlement`, `disputes`, `reviews`, `admin_moderation`, `admin_compliance`, `admin_user_management`, `affiliate`
  - Additionally ~30 flows use `db.notifications.insert_one(...)` directly (bids, webhooks, admin actions).
- **The only other file in the repo referencing `/notifications/create`** was `/app/notification_test.py` — a standalone QA harness at repo root (not runtime code) using stale pre-BidVex admin credentials.

### Conclusion
The HTTP endpoint was **orphaned attack surface**. Every real user-facing notification flow (payment-success, auction close/settlement, escrow, outbid alerts, scheduled jobs) already routes through the in-process function. Gating the endpoint admin-only would have left a hardened-but-unused endpoint waiting for the next auth regression; the correct fix is deletion.

### Fix — `backend/routes/notifications.py`

Removed lines 224–255 (the entire `create_notification` HTTP handler). Replaced with a comment explaining the removal and pointing future contributors at the surviving admin-authenticated `/notifications/admin/send` endpoint.

**Before:**
```python
@notifications_router.post("/notifications/create")
async def create_notification(
    user_id: str,
    notification_type: str,
    title: str,
    message: str,
    data: Optional[dict] = None,
    action_url: Optional[str] = None,
    action_type: Optional[str] = None,
):
    """Create a notification (internal use / admin)."""
    db = get_db()
    notification = { ...client-supplied user_id, title, message... }
    await db.notifications.insert_one(notification)
    notification.pop("_id", None)
    return notification
```

**After:**
```python
# iter482 SEC-001 — The former unauthenticated `POST /api/notifications/create`
# endpoint has been REMOVED. It had zero legitimate runtime callers (all internal
# notification flows use `services.notifications_i18n.create_notification()` in
# process). Admin-driven notification creation now goes exclusively through
# `POST /api/notifications/admin/send` below, which requires an authenticated
# admin session. Do NOT reintroduce a public creation endpoint.
```

### Downstream cleanups
- `notification_test.py` — patched to call `/notifications/admin/send` with the correct JSON payload shape (three call sites: `test_create_notification_manually`, `test_mark_all_notifications_read`, `test_outbid_notification_creation`). Stale `admin@bazario.com` credentials updated to the canonical BidVex admin per `/app/memory/test_credentials.md`.
- `backend/tests/test_iter217_phase2_admin_watchlist_badges.py::TestNotificationActionUrlSchema::test_notifications_create_accepts_action_url` — updated to inspect the surviving `admin_send_notification` handler's source instead (it accepts `action_url` and `cta_url` in the payload dict). Renamed to `test_notifications_admin_send_accepts_action_url`.

---

## 2. SEC-002 · Password-reset backdoor gated only by the signing secret

### Fix — `backend/routes/auth.py`

Removed lines 1251–1295 (the entire `admin_force_password_sync` handler). Replaced with a comment.

**Before:**
```python
@auth_router.post("/admin-force-sync")
async def admin_force_password_sync(request: Request):
    """One-time admin password sync endpoint..."""
    body = await request.json()
    email = body.get("email", "").strip().lower()
    new_password = body.get("new_password", "")
    sync_key = request.headers.get("X-Sync-Key", "")

    # Require the JWT_SECRET as the sync key to prevent abuse
    if sync_key != JWT_SECRET:                          # ← non-constant-time compare
        raise HTTPException(status_code=403, detail="Invalid sync key")

    # ... resets password for any email ...
```

**After:**
```python
# iter482 SEC-002 — The former `POST /api/auth/admin-force-sync` endpoint has
# been REMOVED. It reset any account's password when the caller supplied a
# header equal to JWT_SECRET (a shared-secret bypass, not real auth). Proper
# admin-driven password resets already exist via
# `POST /api/admin/users/{user_id}/force-password-reset` which requires an
# authenticated admin session. Do NOT reintroduce shared-secret backdoors.
# NOTE: JWT_SECRET rotation is RECOMMENDED given this endpoint accepted it
# as an out-of-band auth secret; rotation must be performed against the
# LIVE environment (invalidates all sessions/tokens) and is outside the
# scope of this patch.
```

### Shared-secret compare hygiene
After removal, the codebase was re-scanned for any remaining plain-`!=`/`==` comparisons of secrets. **Result: none.** All other `JWT_SECRET` usages in `routes/auth.py`, `routes/reviews.py`, `routes/team.py` are inside `jwt.encode()` / `jwt.decode()` calls, which perform proper cryptographic verification internally — not string comparison. **No `hmac.compare_digest` migration required** because there are no residual secret string comparisons to migrate.

### JWT_SECRET rotation — recommended but out of scope
The audit flagged that `JWT_SECRET` was misused as an out-of-band auth secret. If it was ever exposed in a header value log, a proxy log, or a client-side script, rotation is warranted.

**Log-hit review for prior probing (as of this preview environment):**
```
$ grep -a "admin-force-sync\|force-sync\|X-Sync-Key\|admin_force_password_sync" /var/log/supervisor/backend.*.log
(no results)
```
No hits on this route in any currently-retained supervisor log. Note: Kubernetes container logs rotate; the visible history covers roughly the past few weeks. **Full historical certainty (has this route EVER been hit externally?) requires reviewing edge / CDN logs at Cloudflare, which is a LIVE-env action outside this patch's scope.**

**Recommendation:** Rotate `JWT_SECRET` before the next production launch. Rotation invalidates all sessions and all outstanding signed URLs (invoice HMAC links included) — plan a scheduled logout for all users.

---

## 3. SEC-001 XSS boundary — read-only investigation

**Question:** Does the frontend notification bell render `title` / `message` as raw HTML (via `dangerouslySetInnerHTML` or `innerHTML`), which would have made SEC-001 also a stored-XSS vector?

**Answer:** **No.** All notification-rendering surfaces render title and message as escaped React text.

Files checked (grep'd for `dangerouslySetInnerHTML` and `innerHTML`):
- `frontend/src/components/NotificationCenter.js` — 0 hits
- `frontend/src/components/NotificationDetailModal.jsx` — 0 hits
- `frontend/src/pages/NotificationsPage.jsx` — 0 hits
- `frontend/src/components/admin/NotificationBell.jsx` — 0 hits

The repo does use `dangerouslySetInnerHTML` elsewhere (broker custom-terms HTML, i18n legal pages, static marketing copy) but **not** in any notification-rendering path. **SEC-001 was therefore a phishing / spoofing / DB-flood vector only, not a stored-XSS vector.** No client-side JS execution was possible via injected notifications even during the vulnerable window.

---

## 4. Regression coverage

New test file: `backend/tests/iter482/test_security_hardening.py` (9 tests, all passing).

| Test                                                                        | Purpose                                                                       |
|-----------------------------------------------------------------------------|-------------------------------------------------------------------------------|
| `test_sec001_legacy_create_endpoint_is_removed_anonymous`                   | Anonymous POST to the deleted path must NOT succeed (404/405) + DB not written |
| `test_sec001_legacy_create_endpoint_is_removed_with_admin_token`            | Even with a valid admin token, the removed path must not resurrect            |
| `test_sec001_admin_send_rejects_anonymous`                                  | Surviving `/admin/send` requires auth (401/403 when anonymous)                |
| `test_sec001_admin_send_rejects_non_admin`                                  | Surviving `/admin/send` returns 403 for logged-in non-admins                  |
| `test_sec001_admin_send_accepts_admin`                                      | Surviving `/admin/send` works for real admins (200, `sent_count=1`)           |
| `test_sec002_admin_force_sync_route_is_removed_anonymous`                   | `admin-force-sync` is gone for anonymous callers                              |
| `test_sec002_admin_force_sync_route_is_removed_with_sync_key`               | `admin-force-sync` is gone **even for callers presenting the JWT_SECRET**     |
| `test_sec001_source_no_longer_defines_create_endpoint`                      | Source-level guard against accidental reintroduction                          |
| `test_sec002_source_no_longer_defines_admin_force_sync`                     | Source-level guard against accidental reintroduction + no shared-secret compare |

**Test run output:**
```
$ python -m pytest tests/iter482/test_security_hardening.py -v
============================== 9 passed in 1.95s ===============================
```

**Downstream test (`test_iter217_phase2_admin_watchlist_badges.py::TestNotificationActionUrlSchema`):** re-pointed at `admin_send_notification`, still passes.

**Full iter482 suite regression:** 82 iter482 tests pass. One pre-existing failure (`test_p61_real_stripe_reconciliation.py::test_full_real_stripe_reconciliation` — Stripe TEST key invalid) confirmed to have been failing **before** this patch via `git stash` + baseline re-run. Not caused by this change.

---

## 5. QA-harness end-to-end proof

The `/app/notification_test.py` script (external QA harness) was patched to use `/admin/send`. To prove the replacement flow works, a live curl-based E2E was executed against the running preview backend using the real BidVex admin credentials and the seeded `testbuyer@bidvex.com`:

```
$ curl POST /api/notifications/admin/send  (admin token, JSON body per patched harness)
{"success":true,"sent_count":1}

$ curl GET /api/notifications?limit=5  (buyer token)
→ notification with type='sec482_qa_test' found in buyer's feed
  id, user_id, type, title, message, read, created_at — all present
```

Cleanup: the test notification was deleted post-verification so no residue was left in the preview DB.

---

## 6. Files changed

| File                                                                        | Change                                                    |
|-----------------------------------------------------------------------------|-----------------------------------------------------------|
| `backend/routes/notifications.py`                                           | Deleted `POST /notifications/create` handler (32 lines)   |
| `backend/routes/auth.py`                                                    | Deleted `POST /admin-force-sync` handler (45 lines)       |
| `backend/tests/test_iter217_phase2_admin_watchlist_badges.py`               | Re-pointed action_url schema test at surviving endpoint   |
| `notification_test.py`                                                      | Patched 3 call sites to `/admin/send`, updated creds      |
| `backend/tests/iter482/test_security_hardening.py`                          | New — 9 regression tests                                  |

No changes to any other file. No billing, tax, Stripe, escrow, invoice, receipt, i18n, or frontend code touched.

---

## 7. Deploy status

**Not deployed.** Fix lives in the preview environment only, per the user's standing constraint. Next launch to `https://bidvex.com` should include:

1. This patch (SEC-001 + SEC-002 deletions).
2. `JWT_SECRET` rotation in the LIVE env (recommended but out of scope here).
3. SEC-003 remediation (30-day localStorage refresh tokens + permissive CSP — deferred per prior audit).
4. Pre-existing deployment blockers from PRD (Stripe LIVE keys, FRONTEND_URL swap to `https://bidvex.com`, admin seed pruning, `BILLING_ALERT_EMAIL`).
