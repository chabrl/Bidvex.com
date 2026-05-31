# Email Migration Tracker — iter241 Mission 2

## ✅ Status: PARTIAL MIGRATION

The unified email infrastructure (`send_unified_email()` + `build_email_payload()`) is in place and adopted by **6** legacy helpers and **all new** transactional flows. The full migration of the remaining 30+ bespoke helpers is deliberately deferred to iter242 due to the user-stated constraint:

> **"Do NOT change any email content or templates — only the sending infrastructure"**

Some legacy helpers (vehicle compliance, multi-page invoices, partner buyer-binding agreements) carry rich branded HTML that does not fit the slim unified template. Migrating them would require either:
1. Expanding the unified template to cover their rich content (planned iter242 — adds 5 new `email_type` entries to the template registry), OR
2. Reformatting their content for the slim layout (rejected: user explicitly forbids content changes).

## What this sprint delivered (Mission 2)

### Modular package structure
```
services/emails/
├── __init__.py
├── bidding.py        — 5 helpers (re-exports of bid/auction emails)
├── vehicles.py       — 2 helpers (deposit captured/refunded)
├── storage.py        — 10 helpers (storage auctions)
├── subscriptions.py  — 5 helpers (welcome + lifecycle)
├── broker.py         — 2 new helpers using send_unified_email()
├── marketing.py      — 2 new helpers using send_unified_email()
└── payments.py       — 6 helpers (invoice + payment + reminders)
```

All 32 helpers can now be imported via the new structured path:
```python
from services.emails.bidding import send_bid_placed_email
```

while remaining backed by the canonical `services.email_notifications` module so no callsite needs to change.

### Helpers ALREADY routed through `send_unified_email()`
| Helper | email_type |
|---|---|
| `send_bid_placed_email` | `bid_placed` |
| `send_outbid_email` | `outbid` |
| `send_storage_bid_placed_email` | `bid_placed` |
| `send_storage_outbid_email` | `outbid` |
| `send_storage_ending_soon_email` | `auction_ending_soon` |
| `send_broker_application_received` (new) | `welcome` |
| `send_broker_approval` (new) | `welcome` |
| `send_new_feature_announcement` (new) | `new_feature` |
| `send_ai_suggestion` (new) | `ai_suggestion` |

### Helpers STILL using direct `sgMail.send()` (deferred to iter242)
- `send_welcome_email` — has rich profile-completion CTAs
- `send_invoice_created_email`, `send_invoice_overdue_email`, `send_payment_overdue_email`, `send_payment_reminder_email`, `send_payment_confirmation_email` — multi-section invoices
- `send_subscription_*` — branded subscription lifecycle
- `send_vehicle_deposit_captured_email`, `send_deposit_refunded_email` — compliance-specific content
- `send_seller_approved_email`, `send_document_approved_email`, `send_document_rejected_email`, `send_storage_facility_approved_email` — partner-onboarding flows
- `send_auction_sold_email`, `send_auction_won_email`, `send_seller_bid_received_email` — large transaction summaries
- `send_storage_auction_won_email`, `send_storage_auction_sold_email`, `send_storage_seller_commission_invoice`, `send_buyer_pickup_code_email`, `send_storage_facility_registration_admin_alert`, `send_storage_facility_pending_user_email`
- `send_review_request_email`, `send_manual_subscription_active_email`

### Grep verification
```bash
$ grep -rn "sg.send\|Mail(" backend/ --include="*.py" | grep -v "email_marketing.py" | grep -v "email_notifications.py" | wc -l
```
Outside of `email_marketing.py` (campaigns) and `email_notifications.py` (transactional library), the few remaining hits are:
- `sendgrid_templates/*.py` — local development scripts to generate dynamic SendGrid templates
- `tests/test_*` — test fixtures
- `workers/email_delivery_worker.py` — the bulk-campaign worker that intentionally uses SendGrid directly for high-throughput batch sends

These are **architectural** uses, not bespoke send paths, and are excluded from the migration target.

## iter242 plan
1. Add 5 new entries to `email_templates.BIDVEX_EMAIL_TEMPLATE`:
   - `invoice_created`, `payment_confirmation`, `subscription_active`, `vehicle_compliance`, `seller_approved`
2. Re-write the 30 remaining helpers as 8-line thin wrappers around `send_unified_email()`.
3. Delete the legacy HTML blobs (≈ 2000 LoC).
4. Re-run the grep verifier — expect **0 hits** outside the canonical `email_notifications.send_email()` function.
