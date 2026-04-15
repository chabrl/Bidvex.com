# BidVex — Auction Marketplace PRD

## Architecture
```
/app
├── backend/
│   ├── services/
│   │   ├── stripe_customer_service.py  # NEW: Sticky Card enforcement, penalty charges, audit
│   │   ├── escrow_service.py           # NEW: Escrow hold, pickup code, auto-release, disputes
│   │   ├── pricing_manager.py          # CORE: All fee calculations
│   │   ├── email_automation.py         # 6 scheduled jobs including escrow auto-release
│   │   └── email_marketing.py          # Campaign CRUD, segments, dashboard stats
│   ├── routes/
│   │   ├── escrow.py                   # NEW: confirm-pickup, status, dispute, admin penalty
│   │   ├── payments.py                 # UPDATED: Card deletion guard (409 with active listings)
│   │   ├── listings.py                 # UPDATED: Payment method validation (402)
│   │   ├── webhooks.py                 # UPDATED: Escrow hold for non-vehicle payments
│   │   └── community.py               # Q&A CRUD
│   ├── lifecycle.py                    # UPDATED: 6 escrow indexes
├── frontend/src/
│   ├── components/legal/
│   │   ├── TermsEN.jsx                 # REWRITTEN: Sticky Card, Escrow, Pickup Code, Penalties
│   │   ├── TermsFR.jsx                 # REWRITTEN: French ToS
│   │   ├── PrivacyEN.jsx               # REWRITTEN: Escrow data, Stripe tokens, retention
│   │   ├── PrivacyFR.jsx               # REWRITTEN: French Privacy
│   ├── pages/
│   │   ├── PlatformPoliciesPage.js     # NEW: Seller/Buyer/Partner/Community policies (FR+EN)
```

## Completed (April 15, 2026) — Sticky Card + Escrow + Legal Rewrite

### System A — Sticky Card Enforcement
- `validate_payment_method_for_listing()`: Blocks listing creation (402) if no valid card on file
- Card Deletion Guard: Blocks DELETE (409) while any active/live/ending_soon listings exist
- `charge_cancellation_penalty()`: $50 CAD flat fee to seller's card for non-delivery
- `audit_stripe_customers()`: Daily cron job flags sellers with missing/expired cards
- Stripe Customer creation already existed in payments.py — reused

### System B — Escrow + Pickup Code (Non-Vehicle Only)
- `create_escrow_hold()`: Creates escrow on payment_intent.succeeded, generates 6-char pickup code
- `confirm_pickup()`: Seller enters code → validates → Stripe Transfer → funds released
- `auto_release_expired_escrows()`: 15-min interval job, releases funds after 48h
- `initiate_dispute()`: Stub for dispute flow (escrow_status = "disputed")
- Failed attempt logging: 5 failures = admin escalation flag
- Pickup code: collision-safe, excludes ambiguous chars (0/O/I/1/L)
- MongoDB: escrow_transactions collection with 6 indexes
- Vehicles excluded (separate settlement flow)

### Legal Documents (All Bilingual FR+EN)
- **Terms of Service**: Sticky Card policy, Cancellation Penalty clause, Escrow system, Vehicle licensing, Marketplace conduct, Stripe Connect authorization
- **Privacy Policy**: Stripe Customer objects, payment tokens, escrow data, pickup code logs, data retention schedules, PIPEDA/Law 25 compliance
- **Platform Policies**: Seller (delivery, penalties, vehicle licensing), Buyer (pickup code, disputes, refunds, timelines), Partner (privileges, restrictions, compliance), Community Q&A (allowed/prohibited content, moderation)

### Testing: iteration_147 — 100% backend (14/14), 100% frontend

## Previous Completions
- (Apr 15) Phase 3: Email Marketing + Automation Engine
- (Apr 15) Final Correction Sprint: Tooltips, CTA routes, Community Q&A
- (Apr 15) 5 Critical UX Gaps
- (Apr 14) Email templates, pricing audit, Stripe Connect, affiliate system

## 3rd Party Integrations
- Stripe — Live | SendGrid — Live | Gemini 2.5 Flash — litellm | VAPID Push — Active

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Admin offline order management
- (Enhancement) 2FA for high-value bidders
- (Enhancement) Full dispute resolution workflow
