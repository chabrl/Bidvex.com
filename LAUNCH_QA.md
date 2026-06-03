# BidVex Pre-Launch QA Checklist

> **iter269 launch-prep manual checklist.** Run this end-to-end on the
> preview environment before pushing the final deploy to production.
> Tick each box; capture screenshots/inbox proof for the email rows.

## Auth

- [ ] Register with email — receive welcome email
- [ ] Register with Google — no false error popup
- [ ] Onboarding wizard appears for new Google user
- [ ] Login with email works
- [ ] Forgot password flow works
- [ ] Logout clears session

## Listings

- [ ] Create a marketplace listing (seller)
- [ ] Create a lot auction listing
- [ ] Listing appears in marketplace grid
- [ ] Featured banner shows promoted listing
- [ ] Map search shows listing marker
- [ ] Listing detail page loads with correct data
- [ ] SEO meta tags visible in page source (`view-source:` → `<meta>` tags)

## Bidding

- [ ] Quick Bid modal opens on card click
- [ ] Bid places successfully
- [ ] Outbid email received by previous bidder
- [ ] Bid placed email received by bidder
- [ ] Vehicle listing shows broker gate for individual user
- [ ] Auction end closes correctly + winner notified

## Payments

- [ ] Admin can send payment request to user
- [ ] User receives email with working Pay Now button
- [ ] `/pay/:id` page loads and shows correct amount
- [ ] Stripe checkout opens (with live key)
- [ ] Payment confirmed email sent after success
- [ ] Pending payments show in user dashboard

## Admin

- [ ] Admin panel loads all tabs
- [ ] User management shows all users
- [ ] Compliance alerts scan runs
- [ ] Flagged listings appear in AI review queue
- [ ] Promote listing from admin works
- [ ] Affiliate Payouts tab (Marketing → 💰 Affiliate Payouts) renders
      summary cards + Approve/Reject buttons

## Emails (all must arrive, no `{placeholder}` text)

- [ ] Welcome email
- [ ] Bid placed
- [ ] Outbid alert
- [ ] Auction won
- [ ] Payment request
- [ ] Payment confirmed

## Mobile (test at viewport widths 375px, 414px)

- [ ] Marketplace grid is 1-column on mobile
- [ ] Map search works on mobile
- [ ] Quick Bid modal usable on mobile
- [ ] Navbar hamburger menu works
- [ ] Notification bell + detail modal usable on mobile

## Notifications

- [ ] Bell badge shows unread count (capped at "9+")
- [ ] Clicking a notification opens centered modal (NOT settings page)
- [ ] Admin can request attachment via send-notification form
- [ ] User receives notification + uploads file → admin gets ack
- [ ] Admin downloads attachment via `/api/admin/notifications/{id}/attachment`
- [ ] Admin reset-attachment button clears submission + notifies user
- [ ] WebSocket toast appears instantly when admin sends notification

## Affiliate

- [ ] `/affiliate` dashboard loads with stats
- [ ] Stripe Connect "Connect Account" CTA works for new affiliates
- [ ] Request Payout button creates pending row
- [ ] Admin approves → real Stripe Transfer fires; Stripe Dashboard
      shows it; affiliate receives confirmation email
- [ ] Admin reject with reason → user receives rejection email
- [ ] Failed/reversed transfer (simulate via Stripe Dashboard) →
      admin sees ❌ badge + Re-issue button works

## SEO & Indexing

- [ ] `https://bidvex.com/sitemap.xml` returns valid XML with all
      listing types
- [ ] `https://bidvex.com/robots.txt` lists `sitemap.xml` + `meta-catalog.json`
- [ ] `https://bidvex.com/api/feeds/meta-catalog.json` returns active listings

## Performance

- [ ] Marketplace grid loads under 2s on 4G simulation
- [ ] Listing detail above-fold image loads with `loading="eager"`
- [ ] All other listing images use `loading="lazy"`
- [ ] No layout-shift (CLS) on listing cards (width/height attrs set)

## Security smoke

- [ ] Login rate-limit triggers after 10 attempts/minute
- [ ] Register rate-limit triggers after 5 attempts/minute
- [ ] Bid rate-limit triggers after 30 attempts/minute
- [ ] Admin endpoints reject non-admin tokens with 403
- [ ] CORS rejects requests from unauthorized origins

## Stripe Live-mode

- [ ] `STRIPE_SECRET_KEY` in production starts with `sk_live_`
- [ ] `STRIPE_WEBHOOK_SECRET` configured for `transfer.created`,
      `transfer.paid`, `transfer.failed`, `transfer.reversed`,
      `checkout.session.completed`, `customer.subscription.*`
- [ ] All currency strings = `cad` not `usd`

## Bilingual

- [ ] French toggle persists across reloads (`/api/users/me`
      `preferred_language` field)
- [ ] Navbar/buttons render French
- [ ] Email subjects + bodies render French for FR users
- [ ] Notification modal renders French body when available

---

**Sign-off**

- Tested by: ____________________
- Date: ____________________
- Browser: ____________________
- Result: ☐ PASS / ☐ FAIL
- Notes: ____________________
