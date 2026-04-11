# BidVex — Auction Marketplace PRD

## Architecture
```
/app
├── backend/
│   ├── server.py                      # FastAPI, CORS, CDN headers, SPA mount
│   ├── routes/
│   │   ├── admin_ops.py               # Admin operations (marketplace, suspend, categories, affiliates)
│   │   ├── admin.py                   # Admin users, team management
│   │   ├── subscriptions.py           # Subscription plans + Coupon CRUD
│   │   ├── auth.py                    # Auth (login block for suspended users)
│   │   ├── email_marketing_ext.py     # Campaign CRUD + Delete/Resend/Clone
│   │   ├── ai_chat.py                 # Master Concierge chatbot
│   │   └── ...
│   └── services/
│       ├── ai_assistant_v2.py         # Gemini 2.5 Flash via litellm + Emergent proxy
│       └── email_service.py           # SendGrid (click tracking disabled)
├── frontend/src/pages/admin/
│   ├── ManageAllAuctions.js           # Marketplace: Delete/Archive/Pause/Resume (auth'd)
│   ├── EnhancedUserManager.js         # User Mgmt: Verify + Suspend Account (auth'd)
│   ├── DeletionRequestsManager.js     # Approve/Reject with notification (auth'd)
│   ├── CategoryManager.js             # CRUD + Subcategories with parent_id (auth'd)
│   ├── CouponManager.js              # Coupon CRUD (already auth'd)
│   ├── PromotionManager.js           # Feature listings (auth'd)
│   ├── AffiliateManager.js           # Affiliate payouts (auth'd)
│   └── EmailMarketingManager.js      # Campaign Delete/Resend/Clone
```

## Completed (April 11, 2026)

### Admin Panel Full Audit & Repair — 8 Sections
**Backend endpoints created:**
- `PUT /admin/listings/{id}/status` — pause, archive, cancel, activate
- `DELETE /admin/listings/{id}` — permanent deletion
- `PUT /admin/multi-item-listings/{id}/status` — same for multi-item
- `DELETE /admin/multi-item-listings/{id}` — cascade delete with lots
- `PUT /admin/users/{id}/suspend` — suspend/reactivate + session revocation
- `GET /admin/affiliate/payouts` + `PUT /admin/affiliate/payouts/{id}/approve`
- `GET /admin/categories` — includes subcategory support
- Deletion reject notification (creates in-app notification for user)

**Frontend fixes:**
- Added `useAuth` + auth headers to ALL 6 admin components (ManageAllAuctions, EnhancedUserManager, DeletionRequestsManager, PromotionManager, AffiliateManager, CategoryManager)
- Added Suspend Account button with Ban icon to EnhancedUserManager
- Rewrote CategoryManager with subcategory UI (nested display, parent_id dropdown)
- Toast error messages show backend error details

**Auth hardening:**
- Suspended users blocked at login (403)
- User sessions revoked on suspend
- JWT extended to 7 days (configurable)
- Email normalization on all auth paths

**Testing:** 21/21 backend + all frontend UI tests passed (iteration_130)

## Previous Session Completed
- Master Concierge chatbot fix (litellm + Emergent proxy)
- Email Marketing Dashboard: Delete/Resend/Clone
- Password Changed email: raw HTML with "Contact Support" button
- Compare button z-index fix for mobile

## 3rd Party Integrations
- Stripe — Live | SendGrid — Live | Gemini 2.5 Flash — litellm + EMERGENT_LLM_KEY | VAPID Push — Active

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Admin offline order management
- (Enhancement) 2FA for high-value bidders
- (Enhancement) Automated Lighthouse audits
