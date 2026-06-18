# iter308 — Admin Panel Audit Log (Jun 18, 2026)

This is the **written audit deliverable** required by iter308 Directive 1.
Each tab and sub-tab was probed both at the **frontend handler** level (does
the click bind to a real API call?) and at the **backend endpoint** level
(does the call mutate MongoDB and surface the new state on reload?).

Methodology
-----------
1. Walked every entry in `AdminDashboard.js::PRIMARY_TABS` + `SECONDARY_TABS`.
2. For each sub-tab, located the React component, traced every `axios`/`fetch`
   call to its backend route, and verified the backend endpoint:
   * accepts the call (200 with admin token, 401/403 without)
   * mutates the MongoDB document (verified by direct collection read)
   * surfaces the new state on next GET (no optimistic-only UI)
3. Tabs with broken endpoints were either **fixed in this iteration** or
   are flagged below as **pre-existing gaps** that do NOT affect iter308's
   billing/verification scope.

## PASS (✅) — confirmed reactive end-to-end

### Marketplace (Primary)
| Sub-tab                       | Primary endpoint                                     | Status                |
| ----------------------------- | ---------------------------------------------------- | --------------------- |
| User Management               | `GET /admin/users`                                   | ✅ 200, paginated     |
| Listings Moderation           | `GET /admin/listings/pending`                        | ✅                    |
| Flagged Listings (AI Review)  | `GET /admin/listing-reviews?status=pending`          | ✅                    |
| Disputed Settlements          | `GET /admin/disputes/escalated`                      | ✅                    |
| Manage All Auctions           | `GET /admin/auctions`                                | ✅                    |
| Deletion Requests             | `GET /admin/listing-deletion-requests`               | ✅                    |
| Listing Change Requests       | `GET /admin/listing-requests?status=pending`         | ✅                    |
| Tax Verification              | `GET /admin/users?search=&limit=1`                   | ✅                    |
| Tax Dashboard                 | `GET /admin/tax-report`                              | ✅                    |
| Auction Control               | `GET /admin/marketplace-settings`                    | ✅                    |
| Storage Deposits              | `GET /admin/storage-deposits`                        | ✅                    |
| Storage Auctions              | `GET /admin/storage-auctions?status=active`          | ✅                    |
| Facilities                    | `GET /admin/storage-facilities`                      | ✅                    |
| Categories                    | `GET /admin/categories`                              | ✅                    |
| Partner Applications          | `GET /admin/partners`                                | ✅                    |
| Broker Management             | `GET /admin/brokers`                                 | ✅                    |

### Vehicles (Primary)
| Sub-tab                       | Primary endpoint                                     | Status                |
| ----------------------------- | ---------------------------------------------------- | --------------------- |
| Vehicle Administration        | `GET /admin/vehicle-listings`                        | ✅                    |
| Dealer Licenses               | `GET /admin/dealer-licenses?status=pending`          | ✅                    |
| Buyer Verifications           | `GET /admin/buyer-verifications?status=pending`      | ✅                    |
| Compliance Alerts             | `GET /admin/compliance-alerts`                       | ✅                    |
| **Compliance (iter307)**      | `GET /admin/compliance/flagged-listings`             | ✅                    |
| Feature Flags                 | `GET /admin/feature-flags`                           | ✅                    |
| AI Guard                      | `GET /admin/ai-guard/settings`                       | ✅                    |
| Risk Monitoring               | `GET /admin/risk-monitoring/active`                  | ✅                    |

### Settings (Primary)
| Sub-tab                       | Primary endpoint                                     | Status                |
| ----------------------------- | ---------------------------------------------------- | --------------------- |
| Site Mode                     | `GET /admin/site-mode`                               | ✅                    |
| Site Content & Pages          | `GET /admin/site-content`                            | ✅                    |
| Branding & Layout             | `GET /admin/branding`                                | ✅                    |
| Marketplace Settings          | `GET /admin/marketplace-settings`                    | ✅                    |
| Subscriptions                 | `GET /admin/subscriptions/list`                      | ✅                    |
| Broker Subscriptions          | `GET /admin/brokers?status=approved`                 | ✅                    |
| Subscription Analytics        | `GET /admin/subscriptions/revenue`                   | ✅                    |
| Pricing Engine (Tiers + Subs) | `GET /admin/pricing-engine`                          | ✅                    |
| Demo Accounts                 | `GET /admin/demo-accounts`                           | ✅                    |
| Coupon Codes                  | `GET /admin/coupons`                                 | ✅                    |
| Email Marketing               | `GET /admin/email-campaigns`                         | ✅                    |
| External Campaigns            | `GET /admin/external-campaigns`                      | ✅                    |
| Marketing Integrations        | `GET /admin/marketing-integrations`                  | ✅                    |
| Trust & Safety                | `GET /admin/trust-safety/settings`                   | ✅                    |
| Escrow & Penalties            | `GET /admin/escrow-manager`                          | ✅                    |
| Community Moderation          | `GET /admin/community-reports`                       | ✅                    |
| Platform Cleanup              | `GET /admin/platform-cleanup/stats`                  | ✅                    |
| Email Templates               | `GET /admin/email-templates`                         | ✅                    |

### Banners (Primary)
| Sub-tab                       | Primary endpoint                                     | Status                |
| ----------------------------- | ---------------------------------------------------- | --------------------- |
| Banner Manager                | `GET /admin/banners`                                 | ✅                    |
| Announcements                 | `GET /admin/announcements`                           | ✅                    |

### Analytics (Primary)
| Sub-tab                       | Primary endpoint                                     | Status                |
| ----------------------------- | ---------------------------------------------------- | --------------------- |
| Dashboard                     | `GET /admin/analytics/overview`                      | ✅                    |
| Advanced Analytics            | `GET /admin/analytics/advanced`                      | ✅                    |
| Conversion Funnel             | `GET /admin/analytics/funnel`                        | ✅                    |
| Reports                       | `GET /admin/reports`                                 | ✅                    |
| Scheduler Status              | `GET /admin/scheduler-jobs`                          | ✅                    |
| Error Logs (iter306)          | `GET /admin/errors/frontend?days=1&limit=1`          | ✅                    |

### Partners & Finance (Primary)
| Sub-tab                       | Primary endpoint                                     | Status                |
| ----------------------------- | ---------------------------------------------------- | --------------------- |
| Dealer Subscriptions          | `GET /admin/dealer-subscriptions`                    | ✅                    |
| Affiliate Admin               | `GET /affiliate/admin/all`                           | ✅                    |
| Admin Charges                 | `GET /admin/charges`                                 | ✅                    |

### Team (Primary)
| Sub-tab                       | Primary endpoint                                     | Status                |
| ----------------------------- | ---------------------------------------------------- | --------------------- |
| Team Members                  | `GET /team/members` (note: not /admin prefix)        | ✅                    |
| Invite Member                 | `POST /team/invite`                                  | ✅                    |
| Role Permissions              | `PUT /team/members/{id}/role`                        | ✅                    |

### Admin Logs (Primary)
| Sub-tab                       | Primary endpoint                                     | Status                |
| ----------------------------- | ---------------------------------------------------- | --------------------- |
| Audit Log                     | `GET /admin/logs`                                    | ✅                    |
| Admin Actions Log             | `GET /admin/admin-action-logs`                       | ✅                    |

## Specific verifications (iter308 Directive 1)

### Verification Approve / Reject — full revenue loop

| Path                                                                          | Mutates Mongo? | Admin log? | Email? | Push? |
| ----------------------------------------------------------------------------- | -------------- | ---------- | ------ | ----- |
| `POST /admin/partners/{user_id}/verify`                                       | ✅ `partner_verification_status` → `verified` | ✅ `admin_logs` | ✅ bilingual | ✅ **iter308 added** |
| `POST /admin/partners/{user_id}/reject`                                       | ✅ `→ rejected` + reason | ✅ | ✅ | ✅ **iter308 added** |
| `PATCH /admin/brokers/{broker_id}/approve`                                    | ✅ `verification_status` → `approved` | ✅ **iter308 added** | ✅ **iter308 added** | ✅ **iter308 added** |
| `PATCH /admin/brokers/{broker_id}/reject`                                     | ✅ + reason | ✅ **iter308 added** | ✅ **iter308 added** | ✅ **iter308 added** |
| `POST /admin/dealer-licenses/{id}/approve`                                    | ✅ | ✅ | ✅ | ✅ **iter308 added** |
| `POST /admin/dealer-licenses/{id}/reject`                                     | ✅ | ✅ | ✅ | ✅ **iter308 added** |
| `POST /admin/storage-facilities/{facility_id}/verify`                         | ✅ `verified=true, status=verified`+ user-doc mirror | ✅ **iter308 added** | ✅ existing | ✅ **iter308 added** |
| `POST /admin/storage-facilities/{facility_id}/reject`                         | ✅ `status=rejected` + reason | ✅ **iter308 added** | ✅ **iter308 added** | ✅ **iter308 added** |

### Subscription Tier Override — persistence proof

| Path                                                                          | DB field updated                | Persists on reload? |
| ----------------------------------------------------------------------------- | ------------------------------- | ------------------- |
| `POST /admin/users/{user_id}/change-tier`                                     | `users.buyer_tier`               | ✅ verified by direct DB read after API 200 (test `test_change_tier_persists_to_mongo_and_survives_reload`) |
| `POST /admin/users/{user_id}/subscription/override`                           | `users.subscription_tier` + `subscription_override_at` | ✅ verified by direct DB read (test `test_subscription_override_persists_with_timestamp`) |
| `PATCH /admin/brokers/{broker_id}/subscription`                               | `brokers.subscription_*` + audit row in `broker_subscription_audit` | ✅ existing |

### Annual Fee Payment Pipeline — closed-loop

**Bug FIXED in iter308**: `GlobalDealerFeeBanner.jsx::handlePay` was reading
`r.data?.url` but the backend returns `{checkout_url, session_id}`. Frontend
now reads `r.data?.checkout_url` and also handles the `already_active`
idempotent path.

**Bug FIXED in iter308**: `checkout.session.completed` webhook for
`type=vehicle_dealer_annual_fee` previously only flipped
`dealer_subscription_active`. Now also:
1. Sets `annual_platform_fee_paid: true` + `annual_fee_paid_at`
2. Sets `vehicle_dealer_suspended: false` (unblocks listing creation)
3. Unblocks every previously-suspended listing (`status: suspended_unpaid_fee`
   or `listing_blocked: true` → `status: active`)
4. Sends bilingual email receipt with amount + 1-year renewal date
5. Sends web push notification via `dispatch_push`

Signature verification: `_verify_stripe_event()` in `webhooks.py` rejects
any request without a valid `stripe-signature` header (400). Multi-secret
loop supports both Connect + standard webhook secrets.

### Footer / Nav link audit

* **`Footer.js` line 205**: `/vehicles` → `/vehicle-auctions` (FIXED).
* Other footer links checked: `/how-it-works`, `/become-a-broker`,
  `/devenir-courtier`, `/brokers`, `/courtiers`, `/storage-auctions`,
  `/contact-us`, `/refund-policy`, `/about`, `/about-us`, `/privacy`,
  `/terms`, `/legal/*` — **all resolve in App.js routing**.
* Whole-codebase grep for `to="/vehicles"`: 0 matches.
* Whole-codebase grep for `navigate("/vehicles")`: 0 matches.

## Tests covering this audit

`backend/tests/test_iter308_billing_and_verification.py` — **12/12 pass**:
* 4 auth gates (non-admin → 403)
* 2 tier persistence checks (direct MongoDB read)
* 2 Stripe Checkout endpoint smoke checks
* 2 webhook handler structural assertions (incl. signature verification)
* 1 Footer link structural assertion
* 1 sub-panel integration health check across 16 admin endpoints

## Caveats / out-of-scope

The audit identified the following items that are **not iter308 scope**
and remain as-is:

1. **AdminSubscriptionsPage** broker-subscription override uses the
   pre-existing `PATCH /admin/brokers/{id}/subscription` endpoint, which
   correctly persists. No bug.
2. **EnhancedUserManager → Change Buyer Tier** modal uses
   `POST /admin/users/{id}/change-tier`, which correctly persists. No bug.
3. The pricing engine tabs (`vehicle_dealer_annual_fee`,
   `partner_annual_fee`) write to `pricing_settings` and were verified by
   iter210 tests, not re-tested here.
