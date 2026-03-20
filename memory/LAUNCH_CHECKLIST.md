# BidVex Launch Checklist
**Date**: March 20, 2026 | **Final Audit**: Iteration 75 (100% pass rate)

---

## GO / NO-GO LAUNCH STATUS: GO

---

| Status | System | Notes |
|--------|--------|-------|
| :white_check_mark: | **Auth & Security** | JWT auth, bcrypt passwords, role-based access control, CORS configured |
| :white_check_mark: | **Rate Limiting** | slowapi: login 10/min, register 5/min, bids 30/min, trial 3/min, default 100/min. Returns 429 + Retry-After |
| :white_check_mark: | **Stripe Billing (Free)** | No payment required, default tier |
| :white_check_mark: | **Stripe Billing (Premium $180/yr)** | Checkout flow + webhook handling verified |
| :white_check_mark: | **Stripe Billing (Partner Pro $240/yr)** | Auto-creates Stripe product/price on first deploy. Annual-only, 50% launch discount from $480 |
| :white_check_mark: | **Stripe Billing (VIP $300/yr)** | Checkout flow + webhook handling verified |
| :white_check_mark: | **Stripe Webhook Security** | construct_event() with signing secret. Unsigned requests rejected with 400. Multi-secret support |
| :white_check_mark: | **Stripe Key Audit** | Zero hardcoded keys. All from env vars. .env.example documented |
| :white_check_mark: | **Partner Pro Trial Flow** | 14-day, no CC, one per account, auto-revert, scheduler running hourly |
| :white_check_mark: | **Email: Trial Started** | SendGrid raw HTML via partner_pro_emails.trial_started |
| :white_check_mark: | **Email: Trial Reminder (Day 10)** | Scheduled email, partner_pro_emails.trial_reminder, 3-day warning |
| :white_check_mark: | **Email: Trial Expired** | partner_pro_emails.trial_expired, sent on auto-revert |
| :white_check_mark: | **Email: Subscription Confirmed** | partner_pro_emails.subscription_confirmed |
| :white_check_mark: | **Email: Invoice Download** | partner_pro_emails.invoice_ready, 1-hour signed URL |
| :white_check_mark: | **Email Template Tests** | 41/41 pytest tests passing |
| :white_check_mark: | **WebSocket (Live Bidding)** | 4 WS endpoints, real-time bid updates |
| :white_check_mark: | **PDF Invoices (Cloud)** | Emergent Object Storage, HMAC-signed download URLs |
| :white_check_mark: | **SEO & Meta Tags** | react-helmet-async, dynamic per-page |
| :white_check_mark: | **Internationalization (i18n)** | EN/FR fully working. Seller Dashboard: 77 translated keys, zero hardcoded strings. i18n.js resource builder properly merges JSON keys |
| :yellow_circle: | **Cloudflare CDN** | MANUAL SETUP — docs at /app/memory/INFRASTRUCTURE_P2.md |
| :white_check_mark: | **MongoDB Indexes** | 27 indexes across 14 collections, applied via idempotent script |
| :white_check_mark: | **Mobile Carousels** | Embla Carousel, 6 homepage sections, dot indicators |
| :white_check_mark: | **Comparison View** | /compare page, 2-4 items, desktop table + mobile stacked |
| :white_check_mark: | **Bulk CSV Import** | /bulk-import, validation, error report, 5MB limit |
| :white_check_mark: | **Branded Storefronts** | /store/:userId, accent color, tagline, banner |
| :white_check_mark: | **Analytics Export** | CSV + JSON, configurable period, Partner Pro+ |
| :white_check_mark: | **Featured Listings** | 10/month for Partner Pro, unlimited for VIP |
| :white_check_mark: | **Early Auction Access** | 2h head start for Partner Pro+ |
| :white_check_mark: | **Tax Compliance** | GST/QST/HST, multi-province Canadian tax |
| :white_check_mark: | **Currency Formatting** | Auto-detect locale, localized display |
| :white_check_mark: | **Backend Architecture** | 37 route modules, 362-line server.py entry point |

---

### Legend
- :white_check_mark: = Verified & working (tested in iteration 75)
- :yellow_circle: = Pending manual setup (not a blocker — deploy first, configure after)

### Pre-Deploy Checklist (5 min)
1. Verify `STRIPE_API_KEY` is a valid live key in production .env
2. Set `INVOICE_SIGNING_SECRET` to a unique 32+ char secret
3. Verify `SENDGRID_API_KEY` and `SENDGRID_FROM_EMAIL` are production-ready
4. Deploy — Partner Pro Stripe price auto-creates on first API call
5. Set up Cloudflare CDN per /app/memory/INFRASTRUCTURE_P2.md
6. Create MongoDB indexes (recommended, not blocking)
