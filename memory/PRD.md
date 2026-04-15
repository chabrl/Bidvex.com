# BidVex — Auction Marketplace PRD

## Architecture
```
/app
├── backend/
│   ├── server.py                      # FastAPI, scheduler, SPA mount
│   ├── routes/
│   │   ├── email_marketing_ext.py     # Admin + User marketing: campaigns, contacts, dashboard-stats, sync
│   │   ├── marketing.py               # Legacy marketing router (audience preview, parse, etc.)
│   │   ├── community.py               # Community Q&A CRUD + upvotes + best answer
│   │   ├── analytics.py               # CTA tracking + seller analytics
│   │   ├── listings.py                # CRUD + multi-lot deduplication
│   │   └── ...
│   ├── services/
│   │   ├── email_marketing.py         # EmailMarketingService: campaigns, segments, dashboard stats, contact sync
│   │   ├── email_automation.py        # APScheduler: onboarding, re-engagement, subscription expiry, abandoned bid recovery
│   │   ├── email_service.py           # SendGrid template sender (78 template IDs)
│   │   ├── pricing_manager.py         # CORE: All fee calculations
│   │   └── ...
├── frontend/src/
│   ├── pages/admin/
│   │   ├── EmailMarketingManager.js   # 6-card dashboard stats + campaign CRUD + user_role segment
│   ├── pages/
│   │   ├── CommunityPage.js           # Q&A forum
│   │   ├── HowItWorks.js             # Fixed CTA routes + tracking
│   │   └── ...
│   ├── components/
│   │   ├── InfoTip.js                 # Bilingual tooltip system
│   │   └── ...
```

## Completed (April 15, 2026) — Phase 3: Email Marketing + Automation Engine

### System Audit
- Verified: Campaign CRUD (38 campaigns), email sending (SendGrid), CSV import, contact storage all working
- Verified: 12 campaigns sent with 111 total emails delivered

### Contact Management
- **Auto-sync**: `POST /api/admin/marketing/sync-contacts` — Syncs all registered users into marketing_contacts pool with roles (buyer/seller/partner/user)
- **CSV Import**: Existing — supports bulk upload with encoding handling
- **Manual Entry**: Existing — admin can add individual contacts
- **Fields**: email, name, language (EN/FR), user_roles, source, synced_at

### Dynamic Segmentation
- **User Role** filter added: `buyers` (placed bids), `sellers` (created listings), `partners` (is_partner flag)
- Existing: subscription_tier, account_type, region, activity_status, email_engagement, seller_status
- Segments auto-update via live DB queries (not cached)

### Automated Email Flows (APScheduler)
- **Welcome Sequence** (Day 0/3/7/14): ✅ Existing
- **Re-engagement** (Day 30/45): ✅ Existing
- **Ending Soon Alerts** (24h/1h): ✅ Existing
- **Abandoned Bid Recovery** (NEW): Runs daily at 10:00 UTC, finds users who bid 24-72h ago but stopped, sends recovery email once per user
- **Subscription Expiry**: ✅ Existing

### Admin Dashboard Stats
- **`GET /api/admin/marketing/dashboard-stats`**: Returns total_campaigns, total_sent, total_opened, total_clicked, total_bounced, open_rate%, click_rate%, recent_campaigns (5)
- **Frontend**: 6-card stats grid (Total Campaigns, Emails Sent, Open Rate%, Click Rate%, Bounced, Sync Contacts)

### Campaign System
- Create, edit, schedule, send, cancel campaigns ✅
- Select segments (user role, tier, region, activity) ✅
- Test send before blast ✅

### Analytics
- Open/click/bounce tracking via SendGrid webhooks ✅
- Per-campaign stats view ✅
- Aggregate dashboard stats ✅

### Testing: iteration_146 — 100% backend (13/13), 100% frontend

## Previous Completions
- (Apr 15) Final Correction Sprint: Tooltip coverage, HowItWorks CTA fix, Community Q&A
- (Apr 15) 5 Critical UX Gaps: Tooltip visibility, multi-lot dedup, trust signals, CTA tracking
- (Apr 14) Bilingual email templates, pricing audit, Stripe Connect, affiliate system

## 3rd Party Integrations
- Stripe — Live | SendGrid — Live | Gemini 2.5 Flash — litellm | VAPID Push — Active

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Admin offline order management
- (Enhancement) 2FA for high-value bidders
