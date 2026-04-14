# BidVex — Auction Marketplace PRD

## Architecture
```
/app
├── backend/
│   ├── server.py                      # FastAPI, CORS, CDN headers, SPA mount
│   ├── routes/
│   │   ├── admin_ops.py               # Admin operations (marketplace, suspend, categories, affiliates)
│   │   ├── admin_config.py            # Admin config, email templates, banners, logs
│   │   ├── admin.py                   # Admin users, team management
│   │   ├── subscriptions.py           # Subscription plans + Coupon CRUD
│   │   ├── auth.py                    # Auth (login block for suspended users)
│   │   ├── email_marketing_ext.py     # Campaign CRUD + Delete/Resend/Clone
│   │   ├── ai_chat.py                 # Master Concierge chatbot
│   │   └── vehicle_settlement.py      # Stripe fee charges and seller contact gating
│   ├── services/
│   │   ├── email_service.py           # SendGrid Dynamic Template sender (78 template IDs)
│   │   ├── email_automation.py        # APScheduler lifecycle jobs
│   │   ├── geo_email_service.py       # Haversine distance-based auction alerts
│   │   ├── vehicle_fee_service.py     # 2.5% net fee calculation
│   │   └── ai_assistant_v2.py         # Gemini 2.5 Flash via litellm + Emergent proxy
│   ├── sendgrid_templates/            # 39 bilingual HTML files + generation scripts
│   │   ├── generate_all_bilingual_templates.py  # Generates 29 new bilingual templates
│   │   ├── generate_bilingual_templates.py      # Generates 10 lifecycle/geo templates
│   │   └── *.html                     # All bilingual template HTML files
│   └── shared.py                      # Central config: DEFAULT_EMAIL_TEMPLATES, EMAIL_TEMPLATE_CATEGORIES
├── frontend/src/
│   ├── pages/admin/
│   │   ├── EmailTemplates.js          # Admin: Template IDs + HTML Preview (iframe/code toggle)
│   │   └── ...
│   ├── components/
│   │   ├── MarketplaceSidebar.js      # Nested category tree
│   │   ├── CategorySelector.js        # 2-step seller category selection
│   │   └── legal/LegalComplianceSections.js # Bilingual legal blocks
```

## Completed (April 14, 2026) — Bulk Migration of Bilingual Email Templates

### 29 New Bilingual HTML Templates Generated
- **Auth (5)**: password_reset, password_changed, email_verification, two_factor, login_alert
- **Admin (2)**: account_suspended, report_received
- **Communication (3)**: announcement, support_ack, platform_updates
- **Financial (4)**: invoice_issued, payment_receipt, payout_sent, invoice_overdue
- **Seller (3)**: new_bid, listing_approved, listing_rejected
- **Auction (3)**: auction_announcement, auction_reminder, auction_results
- **Bid (3)**: outbid, confirmed, winning
- **Affiliate (4)**: monthly_earnings, commission_earned, referral_notification, program_summary
- **Triggers (2)**: auction_ending_soon, cross_border_notice

### Admin Panel Synchronization
- **`EMAIL_TEMPLATE_CATEGORIES`** expanded from 6 to 9 categories: added Lifecycle (8), Geo (2), Triggers (2)
- **`get_email_templates()`** now auto-merges new `DEFAULT_EMAIL_TEMPLATES` keys into MongoDB on load
- **Backend**: `GET /api/admin/email-templates/{key}/preview` returns HTML content for all 39 templates
- **Backend**: `GET /api/admin/email-templates/previews/list` returns all previewable template keys
- **Frontend**: Each template row has a "Preview" button showing rendered HTML in an iframe
- **Frontend**: "HTML Code" toggle switches between visual preview and raw source
- **Frontend**: Bilingual templates (lifecycle/geo/triggers) show "Bilingual" badge and single ID input

### Send Test Email — Draft Invoice
- **`PricingManager`** class (`/app/backend/services/pricing_manager.py`):
  - Wraps `vehicle_pricing.py` tax engine + Stripe fee recovery
  - Calculates dual-sided DraftInvoice: Buyer charges + Seller deductions
  - Province-aware tax: QC (GST 5% + QST 9.975%), ON (HST 13%), BC (GST+PST 12%), AB (GST 5%)
  - Tier-aware fees: Free (5%/4%), Premium (3.5%/2.5%), VIP (3%/2%)
- **Backend**: `POST /api/admin/email-templates/preview-invoice` — generates HTML + pricing breakdown
- **Backend**: `POST /api/admin/email-templates/send-test` — sends bilingual draft invoice via SendGrid
- **Frontend**: "Send Test Email" button in Admin Panel with configurable:
  - Recipient email, hammer price, category, province, buyer tier, seller tier
  - Live pricing breakdown (Buyer Charges + Seller Deductions cards)
  - Inline iframe preview of the bilingual email

### Testing
- Backend: 34/34 tests passed (iterations 135-137)
- Frontend: 100% — all Preview buttons, Bilingual badges, Draft Invoice panel working
- Tax verification: QC 14.975% vs ON 13% confirmed via automated tests

## Completed (April 13, 2026) — Complete Email System Rebuild

### email_service.py Refactored
- `send_template_email()` core with retry logic (3 attempts, exponential backoff)
- 65+ template ID registry with EN/FR language routing
- 15+ typed email functions (welcome, bid_confirmed, outbid, winning, etc.)

### email_automation.py — Lifecycle Sequences
- Onboarding: Day 3, Day 7, Day 14 (subscription pitch + BIENVENUE20 coupon)
- Re-engagement: Day 30, Day 45 (final + RETOUR15 coupon)
- Subscription Expiry: -14d, -7d, -1d reminders, +3d reactivation

### geo_email_service.py — Geo-Targeted Alerts
- Haversine distance + 120+ FSA centroids (QC, ON, Atlantic, Prairies)
- Daily batch sending with 7-day cooldown per user/auction

## Completed (April 12, 2026) — Previous Features
- Admin Panel Full Audit & Repair (8 sections)
- Redis Integration Audit & Hardening
- Category Hierarchy UX Refactor
- Legal Compliance Sprint (Bill 96 / Law 25 / OPC)
- Stripe Intermediary Handshake & Fee Passing (2.5% buyer fee)
- SetupIntent Card Verification
- Email Heartbeat Recovery

## 3rd Party Integrations
- Stripe — Live | SendGrid — Live | Gemini 2.5 Flash — litellm + EMERGENT_LLM_KEY | VAPID Push — Active

## Backlog
- (P2) Cloudflare CDN DNS migration
- (P2) Post-launch monitoring & alerting
- (Enhancement) Admin offline order management
- (Enhancement) 2FA for high-value bidders
- (Enhancement) Automated Lighthouse audits
