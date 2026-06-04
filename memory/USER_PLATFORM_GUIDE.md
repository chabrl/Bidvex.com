# BidVex — User-Facing Platform Behaviour Guide

**Audience**: any agent / engineer working on BidVex. This is the single source
of truth for *what users experience* and *how the guardrails respond* during
the lifecycle of an account. Backend implementation details live in `PRD.md`
and the per-iteration changelogs — this file describes the system from the
**end-user's perspective**.

Last refreshed: **iter275** (Feb 2026).

---

## 1. Signup & Onboarding

### 1.1 Standard signup
- Routes: `/login` and `/register` (both rendered by `pages/AuthPage.js`).
- A new user provides: email, password, name, mobile, address, `account_type`
  (`personal` | `business`), terms agreement, AI-disclosure consent.
- Email + mobile-number unique constraints are enforced; duplicates surface a
  persistent red overlay linking to `support@bidvex.com`.
- Successful signup → JWT token persisted via `AuthContext` → redirected to
  `/marketplace`.

### 1.2 Promo-unlocked signup (iter274)
When a user lands with `?promo=BVX-TRIAL-XXXXXXXX` in the URL:

1. `AuthPage` calls `GET /api/promotions/coupons/{code}` on mount.
2. If `valid=True`, a **green banner** reads:
   *"Free {30/45/60}-day {dealer/broker/storage} trial unlocked — Code
   `BVX-TRIAL-XXXX` — sign up below and your annual partner fee is waived
   for {duration} days."*
3. The form **lands on the signup tab automatically** (not the login tab).
4. Pre-filled fields (when the coupon was minted with a specific recipient):
   `email`, `name`, `company_name`, `account_type=business`.
5. On submit the register payload carries `promo_code`. Backend atomically
   redeems it: `partner_trials` row inserted + `users.platform_fee_paid=True`
   + `partner_subscription_active=True`. The user **never sees the annual
   $100 fee gate**.

Invalid / expired / already-redeemed codes show an amber "Trial code not
applied — you can still register without the trial" notice. Signup still
succeeds; only the waiver is skipped.

### 1.3 Tax interview (iter273 — SIN compliance enforced)
Triggered automatically the first time a user attempts an action that
requires a verified tax profile (creating a listing, placing a bid, requesting
payout, etc.).

**Individual sellers** are asked for ONLY:
- Legal name
- Date of birth (required for CRA Part XX reporting)
- Principal residential address

**Business sellers** additionally provide:
- Business Number (BN)
- NEQ (Quebec Enterprise Number)
- GST/HST registration number
- QST registration number
- Registered corporation name
- Registered business office address

> **Hard rule**: BidVex **never** requests, stores, or processes a Social
> Insurance Number. The frontend has no SIN field. The backend
> `PUT /users/me/tax-profile` rejects any payload containing `sin`,
> `social_insurance_number`, or `sin_number` with a 400 + `error_code=
> sin_not_accepted`. CRA reporting at year-end is derived from legal name
> + DOB only.

Quebec GST/QST (14.975%) is auto-calculated by the platform on every sale
to a Quebec buyer; sellers see the breakdown in their invoice line items.

### 1.4 Language toggle
EN ↔ FR globally via the header toggle. All transactional emails,
notifications, and invoice PDFs are bilingual where regulations require it
(QC), English-only elsewhere.

---

## 2. Browsing & Bidding

### 2.1 Marketplace surfaces
- **Top homepage carousel** — top-tier active listings (bikes, tools,
  furniture sets, featured vehicles) prominently slide-shown for instant
  reach. Cards link directly to the listing detail.
- **Marketplace grid** (`/marketplace`) — full filterable inventory across:
  - General items (any category)
  - Vehicle auctions (cars, trucks, motorcycles)
  - Multi-lot auctions (storage units, estate cleanouts)
  - Storage auctions (abandoned-unit cleanouts under provincial law)
- **Search / Filters**: province, category, price, distance, condition,
  auction-end-time.

### 2.2 General bidding (no restrictions)
For non-vehicle listings, ANY logged-in user can:
- View the live ascending auction
- Place bids (auto-incremented by the configured minimum step)
- Set proxy bids (maximum amount; the system bids up automatically)
- Receive real-time WebSocket notifications when outbid
- Win → checkout via Stripe Connect → seller's payout flow handles fulfilment

### 2.3 Vehicle-bid lock (Individual tier)
**Strict guardrail**: a user with `account_type=personal` **cannot place
bids on vehicle auctions**. The vehicle detail page surfaces a blocking
modal:

> "Vehicle bidding requires a licensed broker partnership. Bind your
> account with a Licensed Broker partner to participate in this auction."

The CTA links to `/partners/brokers` where the user can browse partner
brokers in their province and request binding. Until bound, the
**Place Bid** button is disabled and styled grey on every vehicle listing.

Cross-border vehicle bidders also pass through a separate
`vehicle_buyer_verification` flow on the first restricted-province bid
attempt.

### 2.4 Storage auctions
Bidding mechanics identical to general auctions, but with two extra
guardrails set by provincial law:
- Pre-auction deposit (refundable if not winning) — typically $100-200
- Pickup window enforcement after winning — failure triggers
  re-listing under the abandoned-property workflow

### 2.5 Featured + Promoted listings
- **Featured** = paid placement in the homepage carousel + category top.
- **Promoted** = inline boost on category browse pages (visual badge,
  higher sort priority).
- Both sold via Stripe Checkout (`Free Promotion Boost` is also one of
  the platform's promotion-engine offers).

---

## 3. Partners & Storage Facilities

### 3.1 Three partner tiers

| Tier              | Free trial | Featured-listing quota | Key perks                                |
|-------------------|-----------:|-----------------------:|------------------------------------------|
| Vehicle Dealer    |   30 days  | 3                      | Verified Dealer badge, real-time analytics, geo-targeted reach |
| Licensed Broker   |   60 days  | Unlimited              | Verified Broker badge, public broker profile, client-referral tools, early access |
| Storage Facility  |   45 days  | 5                      | Facility profile page, tenant-notification tools, compliant abandoned-property workflow |

### 3.2 Trial activation paths

1. **Direct admin activation (iter259)** — Admin opens the Promotions
   Engine → Partner Trial Offers card → "Activate for a User" → searches
   for the registered user → activates the trial with company name /
   licence / province / phone. User gets a `partner_welcome` email + bell
   notification.

2. **Coupon mint for unregistered prospect (iter274)** — Admin clicks
   "🎟️ Generate Coupon" mode → optionally enters recipient email/name →
   `BVX-TRIAL-XXXXXXXX` minted. Admin shares the per-recipient signup
   URL (`https://bidvex.com/register?promo=BVX-TRIAL-...&utm_source=
   external_marketing&utm_campaign=...`). Prospect signs up → annual
   fee waived → trial flag set.

3. **Bulk external campaign attachment (iter271/274)** — Admin creates an
   External Email Campaign → step 1 toggles ☑ "Attach Free Trial Coupon"
   → picks partner type. At send-time, one coupon is minted per recipient
   and `{trial_signup_url}` + `{promo_code}` placeholders in the body
   resolve to unique URLs per recipient.

### 3.3 Storage facility document workflow
- During registration, the facility uploads their business-registration
  proof (PDF / JPG / PNG / WEBP, max 10MB).
- Admin reviews + verifies → `company_registration_verified=True`
  triggers a `partner_welcome` email and unlocks storage-auction
  listing creation.
- **If the document file is lost** (e.g. iter273 redeploy migration
  scenario), the admin sees an upgraded modal with the facility's
  metadata + a **"Request resubmission"** CTA. Clicking it:
  - Resets `company_registration_verified=False`
  - Stamps `resubmission_requested_at`
  - Sends the operator a **bilingual rejection-style email** with a
    direct link to re-upload (`/facility/dashboard` → registration
    section).
  - Idempotent — clicking multiple times doesn't spam the operator.

### 3.4 Annual fee waiver mechanics
- Standard partner annual fee: **$100 CAD** charged via Stripe Checkout.
- Waived automatically when a trial is active (`partner_trial_active=True`)
  AND `partner_fee_paid_via_coupon` is set.
- Renewal: when the trial expires the dashboard surfaces a paywall card;
  payment via Stripe Checkout flips `platform_fee_paid=True` and triggers
  the `record_premium_upgrade` campaign-attribution counter.

---

## 4. Invoicing & Payment Settlement

### 4.1 Admin-initiated payment request
When an administrator requests a balance settlement from a user:

1. **Bell notification**: user sees an unread badge in the header. The
   notification carries `type="payment_request"` and a deep link to the
   payment page.
2. **SendGrid transactional email** sent immediately with the canonical
   `bidvex.com` sender (now fully DKIM/SPF aligned post-iter275 DNS
   update). Subject: "Payment request — BidVex".
3. The email body shows: amount, currency (CAD), admin note, due date,
   and a primary CTA button: **"Pay now → Open secure checkout"**.

### 4.2 One-click checkout
- Clicking the email link OR the bell notification routes the user to
  `/pay/{request_id}`.
- The page renders a **transparent itemized breakdown**:
  - Base amount
  - GST (5%) — Canada-wide
  - QST (9.975%) — only for Quebec users
  - HST equivalents for participating provinces (ON, NB, NS, NL, PE)
  - Admin note (free-text rationale provided by staff)
  - **Total payable**
- Single **"Pay $X.XX CAD"** button → opens Stripe Checkout session.
- On successful payment → Stripe webhook flips `payment_requests.status =
  paid` → user sees confirmation toast + receipt email.

### 4.3 Receipts & history
- Every successful payment generates a downloadable PDF receipt accessible
  from `/account/billing-history`.
- The same screen shows pending payment requests with their due dates and
  one-click pay buttons.

---

## 5. Marketing & Discovery (iter265+)

### 5.1 Meta + Google product feeds
- Every public, active listing (vehicles, general items, multi-lots,
  storage auctions) is automatically serialized into:
  - **Meta product feed** at `GET /api/feeds/meta.json`
  - **Google Merchant feed** at `GET /api/feeds/google.xml`
- Feeds refresh on every listing CRUD event so social-ad retargeting
  campaigns always pull the freshest inventory.
- Sellers don't need to do anything — listing → live → fed.

### 5.2 SEO & sitemap
- Every listing detail page renders structured-data JSON-LD (Product +
  Offer schemas).
- Dynamic `/sitemap.xml` always reflects the current active inventory.
- React Helmet drives per-route meta tags (title, description, OG image,
  Twitter cards) so shared URLs preview correctly.

### 5.3 External email acquisition (auctioneer outreach)
- Admins build acquisition campaigns from `/admin/external-campaigns`.
- 4-step wizard: Content → Recipients → Attachments → Review.
- Compliance-built-in: CASL footer auto-appended if `{unsubscribe_url}`
  placeholder is missing.
- Per-campaign coupon attachment (iter274) lets the admin mint one
  `BVX-TRIAL-*` per recipient.
- Real-time analytics via SendGrid webhook + iter273 ROI dashboard:
  delivered, opened, clicked, registrations, premium upgrades, fallback
  dispatches.
- iter275 coupon-conversion analytics tab compares subject lines by
  actual paid-trial signups — not just opens.

---

## 6. Notifications

Two transports, both kept in sync:

1. **WebSocket bell (`NotificationConnectionManager`)** — live unread
   count + dropdown list in the app header. Polling fallback every 30s
   for closed WebSockets.
2. **Email (SendGrid)** — every important event also dispatches a
   transactional email so users never miss an action item.

Event categories that fire both bell + email:
- Bid placed / outbid
- Auction won / lost
- Payment request received
- Trial activated / extended / revoked
- Storage facility verification result
- Affiliate commission paid out (Stripe Connect Express)
- Partner trial expiry warning (T-7 / T-3 / T-0 days)

Users control per-category opt-outs at `/account/notification-preferences`.

---

## 7. Affiliate / Referral Program

- Every user has a unique `affiliate_code` (e.g. `BVX-ABC123`).
- Sharing `https://bidvex.com/?ref=BVX-ABC123` and the new user signing
  up binds the referral on the new account's `referred_by_code` field.
- When the referred user transacts, the referrer earns a commission
  (configured per category) that accumulates in `affiliate_balance`.
- **Payouts via Stripe Connect Express** — affiliate clicks "Get paid",
  goes through Express onboarding, balance settled to their bank account.

---

## 8. Critical Guardrails Summary

| Behaviour | Trigger | UX Response |
|-----------|---------|-------------|
| Vehicle bid blocked | `account_type=personal` clicks Place Bid on vehicle | Modal: bind broker first; CTA → `/partners/brokers` |
| Annual fee waived | `?promo=BVX-TRIAL-*` signup | Green unlock banner + skip Stripe checkout |
| Tax interview blocks listing | `tax_onboarding_completed=False` + create listing attempt | Modal pops with tax interview form |
| SIN field nonexistent | Any tax form | No SIN input ever rendered; backend rejects key with 400 |
| Storage doc missing | View · Voir click on lost file | Modal with metadata + "Request resubmission" CTA |
| Quebec tax auto-apply | Buyer's province = QC | QST 9.975% added to checkout breakdown |
| External campaign CASL | Body missing `{unsubscribe_url}` | Footer auto-appended on send |
| Bilingual emails | QC user OR `lang=fr` preference | EN + FR sections both rendered |
| Trial expiry T-7 | Daily APScheduler job | Bell + email warning to upgrade |

---

## 9. Workflow Cheat Sheets

### 9.1 New auctioneer onboarding (from acquisition email)
1. Admin builds external campaign with coupon attached → sends to N auctioneers.
2. Recipient receives bilingual email, clicks unique `{trial_signup_url}`.
3. Lands on `/register?promo=BVX-TRIAL-XXXXXXXX` → green banner unlocks.
4. Signs up → coupon redeemed atomically → `partner_trials` row created.
5. Lands on dashboard with trial-active state, featured-listing quota live.
6. T-7 / T-3 / T-0 reminders fire automatically before trial expiry.
7. Trial expires → paywall surfaces → Stripe Checkout → `platform_fee_paid=True`.
8. Admin sees the conversion in iter275 Coupon Analytics → A/B subject wins.

### 9.2 Buyer placing a vehicle bid (personal tier blocked → broker bound)
1. User browses `/marketplace?type=vehicle`.
2. Clicks a vehicle → Place Bid button is greyed out.
3. Modal: "Vehicle bidding requires broker partnership."
4. CTA → `/partners/brokers` → user picks a province broker → requests binding.
5. Broker accepts → `users.bound_broker_id` set → vehicle bid button unlocks.
6. User now bids; cross-province first-attempt triggers `vehicle_buyer_verification` flow.

### 9.3 Payment request → settlement
1. Admin requests balance from user via admin panel.
2. User: bell notification (unread badge) + SendGrid email arrive simultaneously.
3. User opens email → "Pay now" → routed to `/pay/{id}`.
4. Itemized breakdown rendered (Amount + GST/QST/HST + admin note).
5. Stripe Checkout → webhook marks paid → confirmation email + receipt PDF.

### 9.4 Storage facility doc resubmission
1. Operator uploads registration during signup → admin verifies.
2. (Later) admin View · Voir click hits 404 (file lost in redeploy).
3. Modal: facility metadata + "Request resubmission" CTA.
4. Admin clicks → operator gets bilingual email with deep-link to upload.
5. Operator re-uploads → admin re-verifies → status flips green → facility unlocked.

---

## 10. Operational Reference Endpoints

For any agent needing fast lookups:

| Concern | Endpoint | Notes |
|---|---|---|
| Promo preview (public) | `GET /api/promotions/coupons/{code}` | Returns `valid`, `duration_days`, `pre_filled` hints |
| Promo mint (admin) | `POST /api/admin/promotions/activate-trial` | Idempotent per recipient_email + partner_type |
| Trial CRUD (admin) | `/api/admin/partner-trials*` | List, extend +30d, revoke |
| External campaign mgmt | `/api/admin/external-campaigns*` | iter271 4-step wizard |
| External coupon analytics | `/api/admin/promotions/coupons` | Joined with campaigns in iter275 tab |
| Payment request settlement | `/api/payment-requests/{id}` + `/pay/{id}` (FE route) | Stripe Checkout session |
| Storage doc resubmission | `POST /api/admin/storage-facilities/{id}/request-resubmission` | Bilingual operator email |
| Vehicle buyer verification | `/api/vehicle-buyer-verification/*` | First-time restricted-province bid |
| Meta feed | `GET /api/feeds/meta.json` | Auto-refresh on listing CRUD |
| Google feed | `GET /api/feeds/google.xml` | Same source-of-truth |
| Sitemap | `GET /sitemap.xml` | Dynamic from active listings |
| SendGrid webhook | `POST /api/sendgrid/webhook` | Open / click / bounce / unsub events |

---

**End of guide.** This document is the operational memory snapshot for
how BidVex behaves *from the user's chair*. Update it alongside any
sprint that changes user-facing behaviour.
